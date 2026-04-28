"""
LeadResearchAgent — analyzes a lead and returns:
  - intent_score (0-100)
  - signals (detected buying signals)
  - summary (human-readable description)
  - confidence (0.0-1.0)

Uses Ollama via OpenAI-compatible API with tool use.
Model configured via OLLAMA_MODEL env var (default: llama3.1:8b).
"""

import os
import json
import logging
from openai import OpenAI

logger = logging.getLogger(__name__)

# ── Config — set OLLAMA_MODEL in .env or docker-compose ──────────────────────
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434/v1")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
MAX_RETRIES = 2

client = OpenAI(base_url=OLLAMA_BASE_URL, api_key="ollama")

# ── Tool definitions ──────────────────────────────────────────────────────────
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "extract_signals",
            "description": (
                "Analyze a lead's profile and extract buying signals — "
                "indicators that the lead is ready to buy now. "
                "Examples: 'Budget Approved', 'Decision Maker', 'Competitor Churn', "
                "'Demo Requested', 'Actively Researching', 'Q1 Budget', 'Fast-Mover'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "signals": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of detected buying signals (2-4 short signals).",
                    }
                },
                "required": ["signals"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "score_intent",
            "description": (
                "Based on the signals and lead profile, calculate a purchase intent score "
                "between 0 and 100. "
                "80-100 = hot (ready to buy), 60-79 = warm (interested), "
                "0-59 = cool (needs nurturing)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "intent_score": {
                        "type": "integer",
                        "description": "Intent score between 0 and 100.",
                    },
                    "reasoning": {
                        "type": "string",
                        "description": "Short explanation (1-2 sentences) for the score given.",
                    },
                    "confidence": {
                        "type": "number",
                        "description": "Confidence level in the score, between 0.0 and 1.0.",
                    },
                },
                "required": ["intent_score", "reasoning", "confidence"],
            },
        },
    },
]


def _build_system_prompt() -> str:
    return (
        "You are an AI agent specialized in sales lead analysis. "
        "Your mission: analyze a lead's profile and determine how ready they are to buy. "
        "Use the available tools in order: first extract_signals, then score_intent. "
        "Be concise and practical."
    )


def _build_user_prompt(lead: dict) -> str:
    def _val(key: str, fallback: str = "N/A") -> str:
        v = lead.get(key)
        return str(v) if v is not None else fallback

    return (
        f"Analyze this lead:\n\n"
        f"Name: {_val('name')}\n"
        f"Company: {_val('company')}\n"
        f"Role: {_val('role')}\n"
        f"Email: {_val('email')}\n"
        f"Deal value: {_val('deal_value_display')}\n"
        f"Last activity: {_val('last_activity_description', 'unknown')}\n\n"
        f"Use the tools to extract buying signals and calculate the intent score."
    )


def _extract_list(arguments: dict, key: str) -> list:
    """Extract a list from arguments, with fallback for models that nest under 'object'."""
    value = arguments.get(key)
    if isinstance(value, list):
        return value
    # Some models (e.g. llama3.2:3b) return {"object": {"signals": [...]}}
    nested = arguments.get("object", {})
    if isinstance(nested, dict):
        value = nested.get(key)
        if isinstance(value, list):
            return value
    return []


def _handle_tool_call(tool_name: str, arguments: dict, state: dict) -> str:
    """Process a tool call and update agent state."""
    if tool_name == "extract_signals":
        state["signals"] = _extract_list(arguments, "signals")
        return json.dumps({"status": "ok", "signals_detected": len(state["signals"])})

    if tool_name == "score_intent":
        raw_score = arguments.get("intent_score") or (arguments.get("object") or {}).get("intent_score", 50)
        raw_conf = arguments.get("confidence") or (arguments.get("object") or {}).get("confidence", 0.5)
        raw_reasoning = arguments.get("reasoning") or (arguments.get("object") or {}).get("reasoning", "")
        state["intent_score"] = max(0, min(100, int(raw_score)))
        state["reasoning"] = raw_reasoning
        state["confidence"] = max(0.0, min(1.0, float(raw_conf)))
        return json.dumps({"status": "ok"})

    return json.dumps({"error": f"Unknown tool: {tool_name}"})


def run(lead: dict) -> dict:
    """
    Run the LeadResearchAgent for a lead.

    Args:
        lead: dict with lead fields (name, company, role, etc.)

    Returns:
        dict with: intent_score, signals, summary, confidence
    """
    state = {"signals": [], "intent_score": 50, "reasoning": "", "confidence": 0.5}

    messages = [
        {"role": "system", "content": _build_system_prompt()},
        {"role": "user", "content": _build_user_prompt(lead)},
    ]

    # ── Agent loop — max 6 iterations (tool use + final response) ───────────
    for iteration in range(6):
        try:
            response = client.chat.completions.create(
                model=OLLAMA_MODEL,
                messages=messages,
                tools=TOOLS,
                tool_choice="auto",
                temperature=0.3,
            )
        except Exception as e:
            logger.error(f"Ollama call failed (iteration {iteration}): {e}")
            break

        message = response.choices[0].message

        # If the model wants to call tools
        if message.tool_calls:
            messages.append(message)
            for tool_call in message.tool_calls:
                try:
                    args = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    args = {}

                result = _handle_tool_call(tool_call.function.name, args, state)
                logger.info(f"Tool called: {tool_call.function.name} → {result}")

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                })
            continue  # continue loop with tool results

        # Model finished — exit loop
        break

    # ── Build summary ────────────────────────────────────────────────────────
    signals_text = ", ".join(state["signals"]) if state["signals"] else "no signals detected"
    summary = (
        f"Researched prospect {lead.get('name', 'N/A')} "
        f"({lead.get('company', 'N/A')}) — "
        f"score: {state['intent_score']}, "
        f"signals: {signals_text}. "
        f"{state['reasoning']}"
    ).strip()

    return {
        "intent_score": state["intent_score"],
        "signals": state["signals"],
        "summary": summary,
        "confidence": state["confidence"],
    }
