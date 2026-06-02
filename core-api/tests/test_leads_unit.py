"""
Unit tests pentru helper functions din app/routers/leads.py:
  - _format_deal_value
  - _map_row
Nu necesită DB sau TestClient.
"""

from decimal import Decimal
from unittest.mock import MagicMock, patch

with patch("sqlalchemy.create_engine", return_value=MagicMock()):
    from app.routers.leads import _format_deal_value, _map_row


# ── _format_deal_value ────────────────────────────────────────────────────────

class TestFormatDealValue:
    def test_eur_symbol(self):
        assert _format_deal_value(Decimal("45000"), "EUR") == "€45,000"

    def test_usd_symbol(self):
        assert _format_deal_value(Decimal("10000"), "USD") == "$10,000"

    def test_gbp_symbol(self):
        assert _format_deal_value(Decimal("5000"), "GBP") == "£5,000"

    def test_ron_prefix(self):
        result = _format_deal_value(Decimal("20000"), "RON")
        assert result == "RON 20,000"

    def test_none_returns_none(self):
        assert _format_deal_value(None, "EUR") is None

    def test_zero_value(self):
        assert _format_deal_value(Decimal("0"), "EUR") == "€0"

    def test_large_number_has_commas(self):
        result = _format_deal_value(Decimal("1000000"), "EUR")
        assert result == "€1,000,000"

    def test_unknown_currency_uses_code(self):
        result = _format_deal_value(Decimal("5000"), "CHF")
        assert "5,000" in result
        assert "CHF" in result

    def test_small_value(self):
        assert _format_deal_value(Decimal("100"), "USD") == "$100"


# ── _map_row ──────────────────────────────────────────────────────────────────

class TestMapRow:
    def test_standard_fields_mapped(self):
        row = {
            "name": "Maria Ionescu",
            "company": "TechCorp",
            "email": "maria@techcorp.ro",
            "role": "CEO",
        }
        result = _map_row(row)
        assert result["name"] == "Maria Ionescu"
        assert result["company"] == "TechCorp"
        assert result["email"] == "maria@techcorp.ro"
        assert result["role"] == "CEO"

    def test_combines_first_and_last_name(self):
        row = {"first name": "Maria", "last name": "Ionescu", "email": "m@x.com"}
        result = _map_row(row)
        assert result["name"] == "Maria Ionescu"

    def test_explicit_name_overrides_first_last(self):
        row = {
            "name": "Maria Ionescu",
            "first name": "Alt",
            "last name": "Nume",
            "email": "m@x.com",
        }
        result = _map_row(row)
        assert result["name"] == "Maria Ionescu"

    def test_skips_empty_string_values(self):
        row = {"name": "Maria", "email": "m@x.com", "company": "   ", "phone": ""}
        result = _map_row(row)
        assert "phone" not in result
        assert "company" not in result

    def test_case_insensitive_column_keys(self):
        row = {"Name": "Maria", "EMAIL": "m@x.com", "COMPANY": "Corp"}
        result = _map_row(row)
        assert result.get("name") == "Maria"
        assert result.get("email") == "m@x.com"

    def test_alias_job_title_maps_to_role(self):
        row = {"name": "Ion", "email": "i@x.com", "job title": "CTO"}
        result = _map_row(row)
        assert result["role"] == "CTO"

    def test_alias_amount_maps_to_deal_value(self):
        row = {"name": "Ion", "email": "i@x.com", "amount": "50000"}
        result = _map_row(row)
        assert result["deal_value"] == "50000"

    def test_alias_notes_maps_to_last_activity(self):
        row = {"name": "Ion", "email": "i@x.com", "notes": "Interested in demo"}
        result = _map_row(row)
        assert result["last_activity_description"] == "Interested in demo"

    def test_alias_organization_maps_to_company(self):
        row = {"name": "Ion", "email": "i@x.com", "organization": "BigCorp"}
        result = _map_row(row)
        assert result["company"] == "BigCorp"

    def test_unknown_columns_ignored(self):
        row = {"name": "Ion", "email": "i@x.com", "linkedin_url": "https://..."}
        result = _map_row(row)
        assert "linkedin_url" not in result

    def test_no_name_fields_produces_no_name(self):
        row = {"email": "m@x.com", "company": "X"}
        result = _map_row(row)
        assert "name" not in result

    def test_values_are_stripped(self):
        row = {"name": "  Maria  ", "email": "  m@x.com  "}
        result = _map_row(row)
        assert result["name"] == "Maria"
        assert result["email"] == "m@x.com"
