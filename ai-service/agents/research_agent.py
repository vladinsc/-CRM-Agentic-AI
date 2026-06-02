"""
LeadResearchAgent — analyzes a lead and returns:
  - intent_score (0-100)
  - signals (detected buying signals)
  - summary (human-readable description)
  - confidence (0.0-1.0)

Uses Ollama via OpenAI-compatible API.
llama3.2:3b does not reliably follow tool parameter schemas, so this agent
uses structured JSON prompting (no tool use) and extracts the result from
the model's text response.
Model configured via OLLAMA_MODEL env var in docker-compose.yml (default: llama3.2:3b).
"""

import os
import json
import re
import logging
from openai import OpenAI

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434/v1")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")

client = OpenAI(base_url=OLLAMA_BASE_URL, api_key="ollama")


def _build_prompt(lead: dict) -> str:
    def _val(key: str, fallback: str = "N/A") -> str:
        v = lead.get(key)
        return str(v) if v is not None else fallback

    website = (lead.get("website_text") or "").strip()
    website_block = (
        f"- Company website excerpt: {website[:2000]}\n" if website else ""
    )

    return (
        "You are a sales analyst. Analyze the lead below and respond with ONLY a JSON object.\n\n"
        f"Lead:\n"
        f"- Name: {_val('name')}\n"
        f"- Company: {_val('company')}\n"
        f"- Role: {_val('role')}\n"
        f"- Deal value: {_val('deal_value_display')}\n"
        f"- Last activity: {_val('last_activity_description', 'unknown')}\n"
        f"{website_block}"
        "\nRespond with ONLY this JSON (no markdown, no explanation, no extra text):\n"
        "{\n"
        '  "signals": ["signal1", "signal2"],\n'
        '  "intent_score": 75,\n'
        '  "reasoning": "brief explanation",\n'
        '  "confidence": 0.8\n'
        "}\n\n"
        "Rules:\n"
        "- signals: 2-4 short labels describing what you observe — can be POSITIVE or NEGATIVE.\n"
        "  Positive examples: 'Demo Requested', 'Budget Approved', 'Decision Maker', 'Trial Active', 'Actively Researching'\n"
        "  Negative examples: 'Negative Sentiment', 'Competitor Preferred', 'Budget Frozen', 'Unresponsive', 'Churned'\n"
        "  Use negative signals when last activity contains complaints, rejection, or disinterest.\n"
        "- intent_score: integer 0-100. Be realistic and critical:\n"
        "  90-100: extremely hot, explicitly ready to buy now\n"
        "  70-89: warm, clear buying intent but not urgent\n"
        "  40-69: neutral or mixed signals\n"
        "  10-39: cold, negative signals or low engagement\n"
        "  0-9: strongly negative (hates company, rejected, churned)\n"
        "  IMPORTANT: negative last activity (complaints, hate, rejection) MUST result in score below 40.\n"
        "  IMPORTANT: no last activity or unknown activity should result in score below 60.\n"
        "- confidence: decimal 0.0-1.0\n"
        "- Return ONLY the JSON object, nothing else."
    )


def _extract_json(text: str) -> dict | None:
    """Extrage primul obiect JSON valid din răspunsul modelului.
    Gestionează cazul frecvent la llama3.2:3b unde JSON-ul e tăiat (lipsește } final).
    """
    if not text:
        return None
    # 1. Încearcă direct dacă textul e JSON pur
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass
    # 2. Caută blocul care conține intent_score (mai specific)
    match = re.search(r'\{[^{}]*"intent_score"[^{}]*\}', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    # 3. Caută orice bloc JSON — încearcă și cu } adăugat (modelul uită closing brace)
    match = re.search(r'\{.*', text, re.DOTALL)
    if match:
        candidate = match.group().strip()
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass
        try:
            return json.loads(candidate + "}")
        except json.JSONDecodeError:
            pass
    return None


def _parse_result(data: dict) -> dict:
    """Extrage și validează câmpurile din JSON-ul modelului."""
    # signals — acceptă list sau string CSV
    raw_signals = data.get("signals", [])
    if isinstance(raw_signals, list):
        signals = [str(s).strip() for s in raw_signals if str(s).strip() and not str(s).startswith("{")]
    elif isinstance(raw_signals, str):
        signals = [s.strip() for s in raw_signals.split(",") if s.strip()]
    else:
        signals = []

    # intent_score
    try:
        intent_score = max(0, min(100, int(data.get("intent_score", 50))))
    except (TypeError, ValueError):
        intent_score = 50

    # confidence
    try:
        confidence = max(0.0, min(1.0, float(data.get("confidence", 0.5))))
    except (TypeError, ValueError):
        confidence = 0.5

    reasoning = str(data.get("reasoning", "")).strip()

    return {
        "signals": signals,
        "intent_score": intent_score,
        "confidence": confidence,
        "reasoning": reasoning,
    }


def run(lead: dict) -> dict:
    """
    Run the LeadResearchAgent for a lead, cu până la 3 încercări.

    Args:
        lead: dict with lead fields (name, company, role, etc.)

    Returns:
        dict with: intent_score, signals, summary, confidence
    """
    prompt = _build_prompt(lead)
    result = None

    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model=OLLAMA_MODEL,
                messages=[
                    {"role": "system", "content": (
                        "You are a brutally honest sales analyst. "
                        "Always respond with valid JSON only. "
                        "You MUST use the full 0-100 range: cold leads with bounced emails, "
                        "inactive companies, or negative sentiment MUST score below 15. "
                        "Leads with locked competitor contracts MUST score below 25. "
                        "Never give a negative lead more than 35. "
                        "Never default to 50 or 75 — every score must reflect the actual signals."
                    )},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
            )
            content = response.choices[0].message.content or ""
            logger.info(f"Attempt {attempt + 1} raw response: {content[:200]}")

            data = _extract_json(content)
            if data:
                parsed = _parse_result(data)
                if parsed["intent_score"] != 50 or parsed["signals"]:
                    result = parsed
                    break
                # Scorul e 50 și no signals — poate fi corect pentru lead rece,
                # dar acceptăm doar dacă avem reasoning
                if parsed["reasoning"]:
                    result = parsed
                    break
            logger.warning(f"Attempt {attempt + 1} could not extract valid JSON from: {content[:100]}")
        except Exception as e:
            logger.error(f"Ollama call failed (attempt {attempt + 1}): {e}")

    if not result:
        result = {"signals": [], "intent_score": 50, "reasoning": "", "confidence": 0.5}

    # ── Build summary ────────────────────────────────────────────────────────
    signals_text = ", ".join(result["signals"]) if result["signals"] else "no signals detected"
    summary = (
        f"Researched prospect {lead.get('name', 'N/A')} "
        f"({lead.get('company', 'N/A')}) — "
        f"score: {result['intent_score']}, "
        f"signals: {signals_text}. "
        f"{result['reasoning']}"
    ).strip()

    return {
        "intent_score": result["intent_score"],
        "signals": result["signals"],
        "summary": summary,
        "confidence": result["confidence"],
    }
