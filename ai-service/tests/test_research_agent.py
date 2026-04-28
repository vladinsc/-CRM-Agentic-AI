"""
Evals pentru LeadResearchAgent.

Structură:
  - Unit tests (fără Ollama) — mock OpenAI client, verifică logica agentului
  - Integration tests       — rulează cu Ollama real (skip dacă nu e disponibil)
                              marcate cu @pytest.mark.integration
"""

import json
import pytest
from unittest.mock import MagicMock, patch
from agents.research_agent import (
    _extract_list,
    _handle_tool_call,
    _build_user_prompt,
    run,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

SAMPLE_LEAD = {
    "id": 1,
    "name": "Maria Ionescu",
    "company": "TechCorp SRL",
    "role": "CEO",
    "email": "maria@techcorp.ro",
    "deal_value_display": "€45,000",
    "last_activity_description": "Viewed pricing page 3x today",
}

LEAD_NO_ACTIVITY = {
    "id": 2,
    "name": "Alex Pop",
    "company": "StartUp SRL",
    "role": "CTO",
    "email": "alex@startup.ro",
    "deal_value_display": None,
    "last_activity_description": None,
}


# ── Unit: _extract_list ───────────────────────────────────────────────────────

class TestExtractList:
    def test_normal_list(self):
        args = {"signals": ["Budget Approved", "Decision Maker"]}
        assert _extract_list(args, "signals") == ["Budget Approved", "Decision Maker"]

    def test_nested_object(self):
        """llama3.2:3b returnează uneori {"object": {"signals": [...]}}"""
        args = {"object": {"signals": ["Fast-Mover", "Demo Requested"]}}
        assert _extract_list(args, "signals") == ["Fast-Mover", "Demo Requested"]

    def test_empty_arguments(self):
        assert _extract_list({}, "signals") == []

    def test_wrong_type_falls_back(self):
        """Dacă signals e string în loc de list, returnează []"""
        args = {"signals": "Budget Approved"}
        assert _extract_list(args, "signals") == []

    def test_nested_empty(self):
        args = {"object": {}}
        assert _extract_list(args, "signals") == []


# ── Unit: _handle_tool_call ───────────────────────────────────────────────────

class TestHandleToolCall:
    def test_extract_signals_updates_state(self):
        state = {"signals": [], "intent_score": 50, "reasoning": "", "confidence": 0.5}
        result = _handle_tool_call(
            "extract_signals",
            {"signals": ["Budget Approved", "Decision Maker"]},
            state,
        )
        assert state["signals"] == ["Budget Approved", "Decision Maker"]
        assert json.loads(result)["signals_detected"] == 2

    def test_score_intent_clamps_to_100(self):
        state = {"signals": [], "intent_score": 50, "reasoning": "", "confidence": 0.5}
        _handle_tool_call("score_intent", {"intent_score": 150, "confidence": 0.9, "reasoning": "test"}, state)
        assert state["intent_score"] == 100

    def test_score_intent_clamps_to_0(self):
        state = {"signals": [], "intent_score": 50, "reasoning": "", "confidence": 0.5}
        _handle_tool_call("score_intent", {"intent_score": -10, "confidence": 0.1, "reasoning": "test"}, state)
        assert state["intent_score"] == 0

    def test_confidence_clamps_to_1(self):
        state = {"signals": [], "intent_score": 50, "reasoning": "", "confidence": 0.5}
        _handle_tool_call("score_intent", {"intent_score": 80, "confidence": 5.0, "reasoning": "test"}, state)
        assert state["confidence"] == 1.0

    def test_score_nested_object(self):
        """Fallback pentru llama3.2:3b care pune valorile sub 'object'"""
        state = {"signals": [], "intent_score": 50, "reasoning": "", "confidence": 0.5}
        _handle_tool_call(
            "score_intent",
            {"object": {"intent_score": 85, "confidence": 0.8, "reasoning": "Hot lead"}},
            state,
        )
        assert state["intent_score"] == 85
        assert state["confidence"] == 0.8

    def test_unknown_tool_returns_error(self):
        state = {}
        result = json.loads(_handle_tool_call("unknown_tool", {}, state))
        assert "error" in result


# ── Unit: _build_user_prompt ──────────────────────────────────────────────────

class TestBuildUserPrompt:
    def test_contains_lead_fields(self):
        prompt = _build_user_prompt(SAMPLE_LEAD)
        assert "Maria Ionescu" in prompt
        assert "TechCorp SRL" in prompt
        assert "CEO" in prompt
        assert "€45,000" in prompt
        assert "Viewed pricing page 3x today" in prompt

    def test_handles_missing_fields(self):
        """Nu trebuie să crape dacă lipsesc câmpuri opționale"""
        prompt = _build_user_prompt(LEAD_NO_ACTIVITY)
        assert "Alex Pop" in prompt
        assert "N/A" in prompt or "necunoscută" in prompt


# ── Unit: run() cu mock Ollama ────────────────────────────────────────────────

def _make_tool_call_message(tool_name: str, arguments: dict):
    """Construiește un mock message cu tool_calls."""
    tool_call = MagicMock()
    tool_call.id = "call_123"
    tool_call.function.name = tool_name
    tool_call.function.arguments = json.dumps(arguments)

    message = MagicMock()
    message.tool_calls = [tool_call]
    return message


def _make_text_message(content: str = "Done."):
    """Construiește un mock message fără tool_calls (răspuns final)."""
    message = MagicMock()
    message.tool_calls = None
    message.content = content
    return message


class TestRunWithMock:
    def _make_response(self, message):
        response = MagicMock()
        response.choices = [MagicMock(message=message)]
        return response

    @patch("agents.research_agent.client")
    def test_run_returns_required_keys(self, mock_client):
        """Output-ul agentului trebuie să aibă toate cheile necesare."""
        mock_client.chat.completions.create.return_value = self._make_response(
            _make_text_message()
        )
        result = run(SAMPLE_LEAD)
        assert "intent_score" in result
        assert "signals" in result
        assert "summary" in result
        assert "confidence" in result

    @patch("agents.research_agent.client")
    def test_run_score_in_valid_range(self, mock_client):
        """Scorul trebuie să fie între 0 și 100 indiferent ce returnează LLM-ul."""
        # Simulează agent care returnează tool calls + răspuns final
        mock_client.chat.completions.create.side_effect = [
            self._make_response(_make_tool_call_message("extract_signals", {"signals": ["Budget Approved"]})),
            self._make_response(_make_tool_call_message("score_intent", {"intent_score": 87, "confidence": 0.9, "reasoning": "Hot"})),
            self._make_response(_make_text_message()),
        ]
        result = run(SAMPLE_LEAD)
        assert 0 <= result["intent_score"] <= 100

    @patch("agents.research_agent.client")
    def test_run_signals_is_list(self, mock_client):
        """signals trebuie să fie întotdeauna o listă."""
        mock_client.chat.completions.create.side_effect = [
            self._make_response(_make_tool_call_message("extract_signals", {"signals": ["Decision Maker", "Q1 Budget"]})),
            self._make_response(_make_text_message()),
        ]
        result = run(SAMPLE_LEAD)
        assert isinstance(result["signals"], list)

    @patch("agents.research_agent.client")
    def test_run_uses_default_state_when_ollama_fails(self, mock_client):
        """Dacă Ollama crapă complet, agentul returnează default-uri (nu aruncă excepție)."""
        mock_client.chat.completions.create.side_effect = Exception("Connection refused")
        result = run(SAMPLE_LEAD)
        assert result["intent_score"] == 50  # default
        assert result["signals"] == []       # default
        assert "Maria Ionescu" in result["summary"]

    @patch("agents.research_agent.client")
    def test_run_full_tool_flow(self, mock_client):
        """Test scenariul complet: extract_signals → score_intent → done."""
        mock_client.chat.completions.create.side_effect = [
            self._make_response(_make_tool_call_message("extract_signals", {
                "signals": ["Budget Approved", "Decision Maker", "Demo Requested"]
            })),
            self._make_response(_make_tool_call_message("score_intent", {
                "intent_score": 92,
                "confidence": 0.95,
                "reasoning": "Multiple buying signals present.",
            })),
            self._make_response(_make_text_message("Analysis complete.")),
        ]
        result = run(SAMPLE_LEAD)
        assert result["intent_score"] == 92
        assert result["signals"] == ["Budget Approved", "Decision Maker", "Demo Requested"]
        assert result["confidence"] == 0.95
        assert "Maria Ionescu" in result["summary"]
        assert "92" in result["summary"]

    @patch("agents.research_agent.client")
    def test_run_lead_with_no_activity(self, mock_client):
        """Agentul nu trebuie să crape pentru lead fără last_activity."""
        mock_client.chat.completions.create.return_value = self._make_response(
            _make_text_message()
        )
        result = run(LEAD_NO_ACTIVITY)
        assert "intent_score" in result
        assert isinstance(result["signals"], list)


# ── Integration tests (necesită Ollama pornit) ────────────────────────────────

@pytest.mark.integration
class TestRunIntegration:
    """
    Aceste teste rulează cu Ollama real.
    Execuție: pytest -m integration
    Skip automat dacă Ollama nu e disponibil.
    """

    @pytest.fixture(autouse=True)
    def skip_if_no_ollama(self):
        import httpx, os
        ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
        base = ollama_url.replace("/v1", "")
        try:
            httpx.get(base, timeout=3.0)
        except Exception:
            pytest.skip("Ollama not available")

    def test_integration_output_schema(self):
        result = run(SAMPLE_LEAD)
        assert isinstance(result["intent_score"], int)
        assert 0 <= result["intent_score"] <= 100
        assert isinstance(result["signals"], list)
        assert isinstance(result["summary"], str)
        assert len(result["summary"]) > 10
        assert isinstance(result["confidence"], float)
        assert 0.0 <= result["confidence"] <= 1.0

    def test_integration_summary_contains_lead_name(self):
        result = run(SAMPLE_LEAD)
        assert "Maria Ionescu" in result["summary"]
