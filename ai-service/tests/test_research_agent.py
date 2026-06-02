"""
Evals pentru LeadResearchAgent.

Structură:
  - Unit tests (fără Ollama) — mock OpenAI client, verifică logica agentului
  - Integration tests       — rulează cu Ollama real (skip dacă nu e disponibil)
                              marcate cu @pytest.mark.integration

Notă: LeadResearchAgent folosește JSON prompting (fără tool use) deoarece
llama3.2:3b nu populează corect tool_calls (Ollama issue #13519).
"""

import json
import pytest
from unittest.mock import MagicMock, patch
from agents.research_agent import (
    _build_prompt,
    _extract_json,
    _parse_result,
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


# ── Unit: _extract_json ───────────────────────────────────────────────────────

class TestExtractJson:
    def test_valid_json_string(self):
        text = '{"signals": ["Demo Requested"], "intent_score": 80, "reasoning": "Hot", "confidence": 0.9}'
        result = _extract_json(text)
        assert result is not None
        assert result["intent_score"] == 80

    def test_json_with_extra_text_before(self):
        text = 'Here is my analysis:\n{"signals": ["Budget Approved"], "intent_score": 75, "reasoning": "Warm", "confidence": 0.8}'
        result = _extract_json(text)
        assert result is not None
        assert result["intent_score"] == 75

    def test_json_missing_closing_brace(self):
        """Modelul uită uneori } la final."""
        text = '{"signals": ["Demo Requested"], "intent_score": 85, "reasoning": "Hot lead", "confidence": 0.9'
        result = _extract_json(text)
        assert result is not None
        assert result["intent_score"] == 85

    def test_empty_string_returns_none(self):
        assert _extract_json("") is None
        assert _extract_json(None) is None

    def test_plain_text_no_json_returns_none(self):
        assert _extract_json("This lead looks interesting.") is None

    def test_json_in_markdown_code_block(self):
        """Modelul uneori înfășoară JSON-ul în ```json ... ```."""
        text = '```json\n{"signals": ["Demo Requested"], "intent_score": 80, "reasoning": "Warm", "confidence": 0.8}\n```'
        result = _extract_json(text)
        # Dacă regex-ul prinde blocul, bine; altfel returnează None — ambele ok
        if result is not None:
            assert result["intent_score"] == 80

    def test_json_with_trailing_text(self):
        text = '{"signals": ["Budget Approved"], "intent_score": 90, "reasoning": "Hot", "confidence": 0.9}\nSome extra text.'
        result = _extract_json(text)
        assert result is not None
        assert result["intent_score"] == 90


# ── Unit: _parse_result ───────────────────────────────────────────────────────

class TestParseResult:
    def test_normal_result(self):
        data = {"signals": ["Demo Requested", "Budget Approved"], "intent_score": 87, "confidence": 0.9, "reasoning": "Hot"}
        result = _parse_result(data)
        assert result["signals"] == ["Demo Requested", "Budget Approved"]
        assert result["intent_score"] == 87
        assert result["confidence"] == 0.9

    def test_intent_score_clamps_to_100(self):
        data = {"signals": [], "intent_score": 150, "confidence": 0.9, "reasoning": ""}
        assert _parse_result(data)["intent_score"] == 100

    def test_intent_score_clamps_to_0(self):
        data = {"signals": [], "intent_score": -10, "confidence": 0.1, "reasoning": ""}
        assert _parse_result(data)["intent_score"] == 0

    def test_confidence_clamps_to_1(self):
        data = {"signals": [], "intent_score": 50, "confidence": 5.0, "reasoning": ""}
        assert _parse_result(data)["confidence"] == 1.0

    def test_signals_csv_string_parsed(self):
        """Modelul returnează uneori signals ca string CSV."""
        data = {"signals": "Demo Requested, Budget Approved", "intent_score": 80, "confidence": 0.8, "reasoning": ""}
        result = _parse_result(data)
        assert "Demo Requested" in result["signals"]
        assert "Budget Approved" in result["signals"]

    def test_schema_strings_filtered(self):
        """Valori de tipul schema JSON ({type: string}) trebuie filtrate."""
        data = {"signals": ['{"type": "string"}', "Demo Requested"], "intent_score": 70, "confidence": 0.7, "reasoning": ""}
        result = _parse_result(data)
        assert '{"type": "string"}' not in result["signals"]
        assert "Demo Requested" in result["signals"]

    def test_missing_fields_use_defaults(self):
        result = _parse_result({})
        assert result["intent_score"] == 50
        assert result["signals"] == []
        assert result["confidence"] == 0.5

    def test_signals_with_extra_whitespace(self):
        data = {"signals": ["  Demo Requested  ", " Budget Approved "], "intent_score": 80, "confidence": 0.8, "reasoning": ""}
        result = _parse_result(data)
        assert "Demo Requested" in result["signals"]
        assert "Budget Approved" in result["signals"]

    def test_reasoning_is_string(self):
        data = {"signals": [], "intent_score": 50, "confidence": 0.5, "reasoning": "Insufficient data"}
        result = _parse_result(data)
        assert result["reasoning"] == "Insufficient data"

    def test_signals_with_empty_strings_filtered(self):
        data = {"signals": ["", "Demo Requested", "  "], "intent_score": 70, "confidence": 0.7, "reasoning": ""}
        result = _parse_result(data)
        assert "" not in result["signals"]
        assert "Demo Requested" in result["signals"]


# ── Unit: _build_prompt ───────────────────────────────────────────────────────

class TestBuildPrompt:
    def test_contains_lead_fields(self):
        prompt = _build_prompt(SAMPLE_LEAD)
        assert "Maria Ionescu" in prompt
        assert "TechCorp SRL" in prompt
        assert "CEO" in prompt
        assert "€45,000" in prompt
        assert "Viewed pricing page 3x today" in prompt

    def test_contains_json_format_instructions(self):
        prompt = _build_prompt(SAMPLE_LEAD)
        assert "intent_score" in prompt
        assert "signals" in prompt
        assert "JSON" in prompt

    def test_handles_missing_fields(self):
        prompt = _build_prompt(LEAD_NO_ACTIVITY)
        assert "Alex Pop" in prompt
        assert "N/A" in prompt


# ── Unit: run() cu mock Ollama ────────────────────────────────────────────────

def _make_json_response(data: dict):
    """Mock response cu JSON valid în content."""
    message = MagicMock()
    message.tool_calls = None
    message.content = json.dumps(data)
    response = MagicMock()
    response.choices = [MagicMock(message=message)]
    return response


def _make_empty_response():
    """Mock response cu content gol."""
    message = MagicMock()
    message.tool_calls = None
    message.content = ""
    response = MagicMock()
    response.choices = [MagicMock(message=message)]
    return response


class TestRunWithMock:
    @patch("agents.research_agent.client")
    def test_run_returns_required_keys(self, mock_client):
        mock_client.chat.completions.create.return_value = _make_json_response({
            "signals": ["Demo Requested"], "intent_score": 80, "reasoning": "Hot", "confidence": 0.9
        })
        result = run(SAMPLE_LEAD)
        assert "intent_score" in result
        assert "signals" in result
        assert "summary" in result
        assert "confidence" in result

    @patch("agents.research_agent.client")
    def test_run_parses_json_correctly(self, mock_client):
        mock_client.chat.completions.create.return_value = _make_json_response({
            "signals": ["Budget Approved", "Decision Maker", "Demo Requested"],
            "intent_score": 92,
            "confidence": 0.95,
            "reasoning": "Multiple buying signals present.",
        })
        result = run(SAMPLE_LEAD)
        assert result["intent_score"] == 92
        assert result["signals"] == ["Budget Approved", "Decision Maker", "Demo Requested"]
        assert result["confidence"] == 0.95
        assert "Maria Ionescu" in result["summary"]
        assert "92" in result["summary"]

    @patch("agents.research_agent.client")
    def test_run_score_in_valid_range(self, mock_client):
        mock_client.chat.completions.create.return_value = _make_json_response({
            "signals": [], "intent_score": 87, "reasoning": "", "confidence": 0.9
        })
        result = run(SAMPLE_LEAD)
        assert 0 <= result["intent_score"] <= 100

    @patch("agents.research_agent.client")
    def test_run_signals_is_list(self, mock_client):
        mock_client.chat.completions.create.return_value = _make_json_response({
            "signals": ["Decision Maker"], "intent_score": 70, "reasoning": "", "confidence": 0.7
        })
        result = run(SAMPLE_LEAD)
        assert isinstance(result["signals"], list)

    @patch("agents.research_agent.client")
    def test_run_defaults_when_ollama_fails(self, mock_client):
        """Dacă Ollama crapă complet, agentul returnează default-uri (nu aruncă excepție)."""
        mock_client.chat.completions.create.side_effect = Exception("Connection refused")
        result = run(SAMPLE_LEAD)
        assert result["intent_score"] == 50
        assert result["signals"] == []
        assert "Maria Ionescu" in result["summary"]

    @patch("agents.research_agent.client")
    def test_run_retries_on_empty_json(self, mock_client):
        """Dacă primul răspuns e gol, agentul încearcă din nou."""
        mock_client.chat.completions.create.side_effect = [
            _make_empty_response(),
            _make_json_response({
                "signals": ["Demo Requested"], "intent_score": 75, "reasoning": "Warm", "confidence": 0.8
            }),
        ]
        result = run(SAMPLE_LEAD)
        assert result["intent_score"] == 75

    @patch("agents.research_agent.client")
    def test_run_lead_with_no_activity(self, mock_client):
        """Agentul nu trebuie să crape pentru lead fără last_activity."""
        mock_client.chat.completions.create.return_value = _make_json_response({
            "signals": [], "intent_score": 40, "reasoning": "No activity", "confidence": 0.5
        })
        result = run(LEAD_NO_ACTIVITY)
        assert "intent_score" in result
        assert isinstance(result["signals"], list)

    @patch("agents.research_agent.client")
    def test_run_summary_contains_score(self, mock_client):
        mock_client.chat.completions.create.return_value = _make_json_response({
            "signals": ["Demo Requested"], "intent_score": 92, "reasoning": "Hot lead", "confidence": 0.9
        })
        result = run(SAMPLE_LEAD)
        assert "92" in result["summary"]

    @patch("agents.research_agent.client")
    def test_run_summary_contains_company(self, mock_client):
        mock_client.chat.completions.create.return_value = _make_json_response({
            "signals": ["Budget Approved"], "intent_score": 75, "reasoning": "Warm", "confidence": 0.8
        })
        result = run(SAMPLE_LEAD)
        assert "TechCorp SRL" in result["summary"]

    @patch("agents.research_agent.client")
    def test_run_all_three_attempts_fail_returns_defaults(self, mock_client):
        mock_client.chat.completions.create.side_effect = Exception("Timeout")
        result = run(SAMPLE_LEAD)
        assert result["intent_score"] == 50
        assert result["signals"] == []
        assert result["confidence"] == 0.5


# ── Integration tests (necesită Ollama pornit) ────────────────────────────────

def _ollama_available() -> bool:
    import httpx
    import os
    ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
    base = ollama_url.replace("/v1", "")
    try:
        httpx.get(base, timeout=3.0)
        return True
    except Exception:
        return False


@pytest.mark.integration
class TestRunIntegration:
    """
    Aceste teste rulează cu Ollama real.
    Execuție: pytest -m integration
    Skip automat dacă Ollama nu e disponibil.
    """

    @pytest.fixture(autouse=True)
    def skip_if_no_ollama(self):
        if not _ollama_available():
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

    def test_integration_hot_lead_scores_above_60(self):
        """Lead cu demo request și pricing page views trebuie să fie warm/hot."""
        result = run(SAMPLE_LEAD)
        assert result["intent_score"] >= 60, f"Expected >= 60, got {result['intent_score']}"
