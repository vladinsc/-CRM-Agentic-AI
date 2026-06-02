"""
IcpMatchAgent — decides whether a scraped lead matches the user's Ideal Customer
Profile (ICP). Given the lead and the 5 free-text ICP fields, returns:
  - match (bool)
  - score (0-100, how well the lead fits the ICP)
  - reasoning (short explanation)

Uses Ollama via the OpenAI-compatible API, same structured-JSON-prompting
approach as research_agent (llama3.2:3b is unreliable with tool schemas).
Model configured via OLLAMA_MODEL (default: llama3.2:3b).
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

# A lead scoring at or above this is considered a match when the model omits an
# explicit boolean.
MATCH_THRESHOLD = 50


def _build_prompt(lead: dict, icp: dict) -> str:
    def _lval(key: str, fallback: str = "N/A") -> str:
        v = lead.get(key)
        return str(v) if v is not None else fallback

    def _ival(key: str) -> str:
        v = icp.get(key)
        return str(v).strip() if v else "(not specified)"

    website = (lead.get("website_text") or "").strip()
    website_block = (
        f"\n- Company website excerpt: {website[:1500]}\n" if website else "\n"
    )

    return (
        "You are a strict B2B sales qualifier. Decide whether the LEAD matches the "
        "seller's Ideal Customer Profile (ICP). Respond with ONLY a JSON object.\n\n"
        "LEAD:\n"
        f"- Name: {_lval('name')}\n"
        f"- Company: {_lval('company')}\n"
        f"- Role: {_lval('role')}\n"
        f"- Location: {_lval('location')}"
        f"{website_block}"
        "\nIDEAL CUSTOMER PROFILE (what the seller wants):\n"
        f"- Target persona (who buys): {_ival('target_persona')}\n"
        f"- Target company (what kind of company): {_ival('target_company')}\n"
        f"- Core pain solved: {_ival('core_pain')}\n"
        f"- Trigger event: {_ival('trigger_event')}\n"
        f"- Value proposition: {_ival('value_proposition')}\n\n"
        "Respond with ONLY this JSON (no markdown, no extra text):\n"
        "{\n"
        '  "match": true,\n'
        '  "score": 80,\n'
        '  "reasoning": "brief explanation"\n'
        "}\n\n"
        "Rules:\n"
        "- match: true ONLY if the lead's role plausibly fits the target persona AND "
        "the company plausibly fits the target company description. If either clearly "
        "does not fit, match=false.\n"
        "- score: integer 0-100 measuring overall fit. Be critical; do not default to 50.\n"
        "- reasoning: one short sentence.\n"
        "- Return ONLY the JSON object."
    )


def _extract_json(text: str) -> dict | None:
    """Extract the first valid JSON object from the model response.
    Tolerates the common llama3.2:3b case where the closing brace is missing.
    """
    if not text:
        return None
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass
    match = re.search(r'\{[^{}]*"score"[^{}]*\}', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    match = re.search(r"\{.*", text, re.DOTALL)
    if match:
        candidate = match.group().strip()
        for attempt in (candidate, candidate + "}"):
            try:
                return json.loads(attempt)
            except json.JSONDecodeError:
                continue
    return None


def _parse_result(data: dict) -> dict:
    try:
        score = max(0, min(100, int(data.get("score", 0))))
    except (TypeError, ValueError):
        score = 0

    raw_match = data.get("match")
    if isinstance(raw_match, bool):
        match = raw_match
    elif isinstance(raw_match, str):
        match = raw_match.strip().lower() in ("true", "yes", "1")
    else:
        match = score >= MATCH_THRESHOLD

    reasoning = str(data.get("reasoning", "")).strip()
    return {"match": match, "score": score, "reasoning": reasoning}


def run(lead: dict, icp: dict) -> dict:
    """
    Decide whether a lead matches the ICP.

    Args:
        lead: dict with lead fields (name, company, role, location, website_text?)
        icp:  dict with the 5 ICP free-text fields (target_persona, target_company,
              core_pain, trigger_event, value_proposition)

    Returns:
        dict with: match (bool), score (int 0-100), reasoning (str)
    """
    prompt = _build_prompt(lead, icp)
    result = None

    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model=OLLAMA_MODEL,
                messages=[
                    {"role": "system", "content": (
                        "You are a strict B2B qualifier. Always respond with valid JSON only. "
                        "Be critical — only mark match=true when the lead genuinely fits both "
                        "the target persona and the target company."
                    )},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
            )
            content = response.choices[0].message.content or ""
            logger.info(f"ICP-match attempt {attempt + 1} raw: {content[:200]}")

            data = _extract_json(content)
            if data is not None and ("score" in data or "match" in data):
                result = _parse_result(data)
                break
            logger.warning(f"ICP-match attempt {attempt + 1}: no valid JSON from: {content[:100]}")
        except Exception as e:
            logger.error(f"Ollama ICP-match call failed (attempt {attempt + 1}): {e}")

    if not result:
        # Fail-open conservatively: if the model never produced usable output, treat
        # as a non-match with a clear reason so nothing is silently accepted.
        result = {"match": False, "score": 0, "reasoning": "ICP match could not be determined."}

    return result
