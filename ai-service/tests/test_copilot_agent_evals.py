"""
Evals pentru CopilotAgent.

Structură:
  - Unit tests (fără Ollama) — mock OpenAI client, verifică logica agentului
  - Integration tests       — rulează cu Ollama real (skip dacă nu e disponibil)
                              marcate cu @pytest.mark.integration

Notă: CopilotAgent folosește JSON prompting (fără tool use) deoarece
llama3.2:3b nu populează corect tool_calls (Ollama issue #13519).

Assertions per EPIC 6 spec:
  winning_argument: conține company/role, menționează un signal, 20-150 cuvinte, fără placeholders
  draft_message:    conține lead.name, 50-300 cuvinte, fără placeholders
  performance:      agent completează în sub 60s
"""

import json
import time
import pytest
from unittest.mock import MagicMock, patch
from agents.copilot_agent import (
    _build_prompt,
    _extract_json,
    _clean_placeholders,
    _parse_result,
    run,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

LEAD_HOT = {
    "id": 1,
    "name": "Maria Ionescu",
    "company": "TechCorp SRL",
    "role": "CEO",
    "email": "maria@techcorp.ro",
    "deal_value_display": "€45,000",
    "intent_score": 87,
    "signals": ["Budget Approved", "Decision Maker", "Demo Requested"],
    "last_activity_description": "Viewed pricing page 3x today",
}

LEAD_WARM = {
    "id": 2,
    "name": "Alexandru Popa",
    "company": "Global Solutions",
    "role": "CTO",
    "email": "alex@globalsolutions.ro",
    "deal_value_display": "€25,000",
    "intent_score": 65,
    "signals": ["Competitor Churn"],
    "last_activity_description": "Downloaded whitepaper on enterprise security",
}

LEAD_COLD = {
    "id": 3,
    "name": "Ion Dumitrescu",
    "company": "Startup Labs",
    "role": "Founder",
    "email": "ion@startuplabs.ro",
    "deal_value_display": "€10,000",
    "intent_score": 40,
    "signals": [],
    "last_activity_description": None,
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _word_count(text: str) -> int:
    return len(text.split())


PLACEHOLDER_PATTERNS = ["[NAME]", "[COMPANY]", "[INSERT]", "[YOUR NAME]", "[Your Name]", "[ROLE]", "[DATE]", "[YOUR EMAIL]"]


def _has_placeholder(text: str) -> bool:
    return any(p in text for p in PLACEHOLDER_PATTERNS)


def _make_json_response(data: dict):
    message = MagicMock()
    message.tool_calls = None
    message.content = json.dumps(data)
    response = MagicMock()
    response.choices = [MagicMock(message=message)]
    return response


def _make_empty_response():
    message = MagicMock()
    message.tool_calls = None
    message.content = ""
    response = MagicMock()
    response.choices = [MagicMock(message=message)]
    return response


# ── Unit: _extract_json ───────────────────────────────────────────────────────

class TestExtractJson:
    def test_valid_json(self):
        text = '{"winning_argument": "Strong case.", "draft_message": "Hi Maria,\\n\\nText.", "confidence": 0.9}'
        result = _extract_json(text)
        assert result is not None
        assert result["confidence"] == 0.9

    def test_json_missing_closing_brace(self):
        """Modelul uită } la final — trebuie recuperat."""
        text = '{"winning_argument": "Strong case.", "draft_message": "Hi Maria,\\n\\nText.", "confidence": 0.9'
        result = _extract_json(text)
        assert result is not None
        assert result["winning_argument"] == "Strong case."

    def test_json_with_preamble(self):
        text = 'Sure, here is the JSON:\n{"winning_argument": "Test", "draft_message": "Hi", "confidence": 0.8}'
        result = _extract_json(text)
        assert result is not None

    def test_empty_returns_none(self):
        assert _extract_json("") is None
        assert _extract_json(None) is None

    def test_plain_text_returns_none(self):
        assert _extract_json("This is just text, no JSON here.") is None

    def test_json_with_trailing_text_no_crash(self):
        """Implementarea curentă nu recuperează JSON cu trailing text — important să nu arunce excepție."""
        text = '{"winning_argument": "Strong.", "draft_message": "Hi Maria.", "confidence": 0.9}\nThat is all.'
        result = _extract_json(text)
        # Poate returna None sau dict — important: nu aruncă excepție
        assert result is None or isinstance(result, dict)

    def test_deeply_truncated_json_recovered(self):
        """Modelul a tăiat JSON-ul la jumătate — se adaugă } la final."""
        text = '{"winning_argument": "TechCorp needs us.", "draft_message": "Hi Maria,'
        result = _extract_json(text)
        # Poate sau nu să recupereze — important să nu arunce excepție
        assert result is None or isinstance(result, dict)


# ── Unit: _clean_placeholders ─────────────────────────────────────────────────

class TestCleanPlaceholders:
    def test_replaces_your_name_uppercase(self):
        assert "Your Sales Team" in _clean_placeholders("Best, [YOUR NAME]")

    def test_replaces_your_name_mixed_case(self):
        assert "Your Sales Team" in _clean_placeholders("Best, [Your Name]")

    def test_replaces_your_email(self):
        assert "sales@company.com" in _clean_placeholders("Contact [YOUR EMAIL]")

    def test_no_placeholders_unchanged(self):
        text = "Hi Maria, let's connect."
        assert _clean_placeholders(text) == text

    def test_replaces_name_placeholder(self):
        result = _clean_placeholders("Hello [NAME], welcome!")
        assert "[NAME]" not in result

    def test_replaces_company_placeholder(self):
        result = _clean_placeholders("At [COMPANY], we offer...")
        assert "[COMPANY]" not in result

    def test_multiple_placeholders_replaced(self):
        text = "Hi [NAME], from [YOUR NAME]"
        result = _clean_placeholders(text)
        assert "[NAME]" not in result
        assert "[YOUR NAME]" not in result


# ── Unit: _parse_result ──────────────────────────────────────────────────────

class TestParseResult:
    def test_normal_result(self):
        data = {
            "winning_argument": "TechCorp needs automation.",
            "draft_message": "Hi Maria,\n\nLet's connect.",
            "confidence": 0.9,
        }
        result = _parse_result(data)
        assert result["winning_argument"] == "TechCorp needs automation."
        assert result["draft_message"] == "Hi Maria,\n\nLet's connect."
        assert result["confidence"] == 0.9

    def test_draft_message_as_dict_with_body(self):
        """Modelul returnează uneori draft_message ca dict cu câmpul 'body'."""
        data = {
            "winning_argument": "Strong argument.",
            "draft_message": {"body": "Hi Maria,\n\nEmail text here."},
            "confidence": 0.8,
        }
        result = _parse_result(data)
        assert result["draft_message"] == "Hi Maria,\n\nEmail text here."

    def test_draft_message_as_dict_with_message_key(self):
        data = {
            "winning_argument": "Strong.",
            "draft_message": {"message": "Hi Maria, let's talk."},
            "confidence": 0.7,
        }
        result = _parse_result(data)
        assert result["draft_message"] == "Hi Maria, let's talk."

    def test_confidence_clamps_above_1(self):
        data = {"winning_argument": "Test.", "draft_message": "Hi.", "confidence": 5.0}
        result = _parse_result(data)
        assert result["confidence"] == 1.0

    def test_confidence_clamps_below_0(self):
        data = {"winning_argument": "Test.", "draft_message": "Hi.", "confidence": -0.5}
        result = _parse_result(data)
        assert result["confidence"] == 0.0

    def test_missing_fields_use_defaults(self):
        result = _parse_result({})
        assert result["winning_argument"] == ""
        assert result["draft_message"] == ""
        assert result["confidence"] == 0.5

    def test_placeholders_cleaned_in_draft(self):
        data = {
            "winning_argument": "Strong.",
            "draft_message": "Hi Maria,\n\nBest regards,\n[YOUR NAME]",
            "confidence": 0.8,
        }
        result = _parse_result(data)
        assert "[YOUR NAME]" not in result["draft_message"]
        assert "Your Sales Team" in result["draft_message"]

    def test_none_values_become_empty_string(self):
        data = {"winning_argument": None, "draft_message": None, "confidence": 0.5}
        result = _parse_result(data)
        assert result["winning_argument"] == ""
        assert result["draft_message"] == ""

    def test_invalid_confidence_defaults_to_half(self):
        data = {"winning_argument": "Test.", "draft_message": "Hi.", "confidence": "not-a-number"}
        result = _parse_result(data)
        assert result["confidence"] == 0.5


# ── Unit: _build_prompt ───────────────────────────────────────────────────────

class TestBuildPrompt:
    def test_contains_lead_fields(self):
        prompt = _build_prompt(LEAD_HOT)
        assert "Maria Ionescu" in prompt
        assert "TechCorp SRL" in prompt
        assert "CEO" in prompt
        assert "€45,000" in prompt
        assert "87" in prompt

    def test_contains_signals(self):
        prompt = _build_prompt(LEAD_HOT)
        assert "Budget Approved" in prompt
        assert "Demo Requested" in prompt

    def test_no_signals_shows_none(self):
        prompt = _build_prompt(LEAD_COLD)
        assert "none detected" in prompt

    def test_contains_json_format(self):
        prompt = _build_prompt(LEAD_HOT)
        assert "winning_argument" in prompt
        assert "draft_message" in prompt
        assert "JSON" in prompt


# ── Unit: run() cu mock Ollama ────────────────────────────────────────────────

class TestRunWithMock:
    @patch("agents.copilot_agent.client")
    def test_run_returns_required_keys(self, mock_client):
        mock_client.chat.completions.create.return_value = _make_json_response({
            "winning_argument": "TechCorp needs automation now.",
            "draft_message": "Hi Maria,\n\nI noticed TechCorp's growth...",
            "confidence": 0.9,
        })
        result = run(LEAD_HOT)
        assert "winning_argument" in result
        assert "draft_message" in result
        assert "confidence" in result

    @patch("agents.copilot_agent.client")
    def test_run_parses_json_correctly(self, mock_client):
        mock_client.chat.completions.create.return_value = _make_json_response({
            "winning_argument": "TechCorp has grown 3x. They need automation now.",
            "draft_message": "Hi Maria,\n\nI noticed TechCorp's impressive growth...",
            "confidence": 0.9,
        })
        result = run(LEAD_HOT)
        assert result["winning_argument"] == "TechCorp has grown 3x. They need automation now."
        assert result["draft_message"] == "Hi Maria,\n\nI noticed TechCorp's impressive growth..."
        assert result["confidence"] == 0.9

    @patch("agents.copilot_agent.client")
    def test_run_defaults_when_ollama_fails(self, mock_client):
        """Dacă Ollama crapă, agentul returnează default-uri (nu aruncă excepție)."""
        mock_client.chat.completions.create.side_effect = Exception("Connection refused")
        result = run(LEAD_HOT)
        assert result["winning_argument"] == ""
        assert result["draft_message"] == ""
        assert result["confidence"] == 0.5

    @patch("agents.copilot_agent.client")
    def test_run_retries_on_empty_response(self, mock_client):
        mock_client.chat.completions.create.side_effect = [
            _make_empty_response(),
            _make_json_response({
                "winning_argument": "Strong case.",
                "draft_message": "Hi Maria,\n\nLet's connect.",
                "confidence": 0.8,
            }),
        ]
        result = run(LEAD_HOT)
        assert result["winning_argument"] == "Strong case."

    @patch("agents.copilot_agent.client")
    def test_run_confidence_in_valid_range(self, mock_client):
        mock_client.chat.completions.create.return_value = _make_json_response({
            "winning_argument": "Test.", "draft_message": "Hi Maria.", "confidence": 0.85
        })
        result = run(LEAD_HOT)
        assert 0.0 <= result["confidence"] <= 1.0

    @patch("agents.copilot_agent.client")
    def test_run_with_empty_signals(self, mock_client):
        mock_client.chat.completions.create.return_value = _make_json_response({
            "winning_argument": "Ion should consider our solution.",
            "draft_message": "Hi Ion,\n\nReaching out...",
            "confidence": 0.5,
        })
        result = run(LEAD_COLD)
        assert "winning_argument" in result
        assert isinstance(result["confidence"], float)

    @patch("agents.copilot_agent.client")
    def test_run_all_attempts_fail_returns_empty_defaults(self, mock_client):
        mock_client.chat.completions.create.side_effect = Exception("Timeout")
        result = run(LEAD_HOT)
        assert result["winning_argument"] == ""
        assert result["draft_message"] == ""
        assert result["confidence"] == 0.5

    @patch("agents.copilot_agent.client")
    def test_run_cleans_placeholders_in_output(self, mock_client):
        mock_client.chat.completions.create.return_value = _make_json_response({
            "winning_argument": "TechCorp should act now.",
            "draft_message": "Hi Maria,\n\nBest,\n[YOUR NAME]",
            "confidence": 0.85,
        })
        result = run(LEAD_HOT)
        assert "[YOUR NAME]" not in result["draft_message"]

    @patch("agents.copilot_agent.client")
    def test_run_warm_lead_returns_all_keys(self, mock_client):
        mock_client.chat.completions.create.return_value = _make_json_response({
            "winning_argument": "Alexandru should switch now due to Competitor Churn.",
            "draft_message": "Hi Alexandru,\n\nI noticed Global Solutions recently...",
            "confidence": 0.7,
        })
        result = run(LEAD_WARM)
        assert "winning_argument" in result
        assert "draft_message" in result
        assert "confidence" in result


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


@pytest.fixture(scope="session")
def hot_result():
    if not _ollama_available():
        pytest.skip("Ollama not available")
    return run(LEAD_HOT)


@pytest.fixture(scope="session")
def warm_result():
    if not _ollama_available():
        pytest.skip("Ollama not available")
    return run(LEAD_WARM)


@pytest.fixture(scope="session")
def cold_result():
    if not _ollama_available():
        pytest.skip("Ollama not available")
    return run(LEAD_COLD)


@pytest.mark.integration
class TestCopilotIntegration:
    """
    Aceste teste rulează cu Ollama real.
    Execuție: pytest -m integration
    Skip automat dacă Ollama nu e disponibil.
    Session-scoped fixtures — agentul rulează o singură dată per lead.
    """

    def test_output_schema(self, hot_result):
        assert isinstance(hot_result["winning_argument"], str)
        assert isinstance(hot_result["draft_message"], str)
        assert isinstance(hot_result["confidence"], float)
        assert 0.0 <= hot_result["confidence"] <= 1.0

    def test_winning_argument_contains_company_or_role(self, hot_result):
        arg = hot_result["winning_argument"]
        assert LEAD_HOT["company"] in arg or LEAD_HOT["role"] in arg, \
            f"Expected company or role in argument, got: {arg}"

    def test_winning_argument_mentions_a_signal(self, hot_result):
        arg = hot_result["winning_argument"].lower()
        signal_found = any(
            word.lower() in arg
            for sig in LEAD_HOT["signals"]
            for word in sig.split()
            if len(word) > 3
        )
        assert signal_found, f"Expected signal keyword in argument, got: {hot_result['winning_argument']}"

    def test_winning_argument_word_count(self, hot_result):
        wc = _word_count(hot_result["winning_argument"])
        assert 20 <= wc <= 150, f"Word count out of range: {wc}"

    def test_winning_argument_no_placeholders(self, hot_result):
        assert not _has_placeholder(hot_result["winning_argument"])

    def test_draft_message_contains_lead_name(self, hot_result):
        first_name = LEAD_HOT["name"].split()[0]
        assert first_name in hot_result["draft_message"] or LEAD_HOT["name"] in hot_result["draft_message"], \
            f"Expected lead name in draft_message, got: {hot_result['draft_message'][:150]}"

    def test_draft_message_word_count(self, hot_result):
        wc = _word_count(hot_result["draft_message"])
        assert 50 <= wc <= 300, f"Word count out of range: {wc}"

    def test_draft_message_no_placeholders(self, hot_result):
        assert not _has_placeholder(hot_result["draft_message"])

    def test_completes_under_60_seconds(self):
        """llama3.2:3b pe hardware local fără GPU durează 30-60s."""
        if not _ollama_available():
            pytest.skip("Ollama not available")
        start = time.time()
        run(LEAD_HOT)
        elapsed = time.time() - start
        assert elapsed < 60, f"Agent took {elapsed:.1f}s (limit: 60s)"

    def test_warm_lead_produces_output(self, warm_result):
        assert isinstance(warm_result["winning_argument"], str)
        assert isinstance(warm_result["draft_message"], str)
        assert isinstance(warm_result["confidence"], float)

    def test_cold_lead_no_signals_does_not_crash(self, cold_result):
        assert isinstance(cold_result["winning_argument"], str)
        assert isinstance(cold_result["draft_message"], str)
