"""
Tests for SfConfigService and SfConfig.

Contract tested (no implementation read):
  SfConfigService(org_alias)
    .load_rule_catalog() → RuleCatalog  (rules.xml base + SF overrides)
    .load_config()       → SfConfig     (key/value from DeweyConfig__c)
    .load_exclusions()   → dict[str, set[str]]  (rule_id → set of component names)

  SfConfig
    .get(key, default)   → str | None
    .get_int(key, default) → int
    .get_float(key, default) → float
    .as_dict()           → dict[str, str]
"""
import json
from unittest.mock import MagicMock, patch, call

import pytest


# ── Helpers ────────────────────────────────────────────────────────────────────

def _sf_query_response(records: list[dict]) -> MagicMock:
    """Builds a fake subprocess.CompletedProcess whose stdout is a SF query result."""
    m = MagicMock()
    m.stdout = json.dumps({"result": {"records": records, "totalSize": len(records)}})
    return m


def _sf_record(fields: dict) -> dict:
    return {"attributes": {"type": "fake"}, **fields}


# ══════════════════════════════════════════════════════════════════════════════
# SfConfig — pure unit tests (no subprocess)
# ══════════════════════════════════════════════════════════════════════════════

class TestSfConfig:
    def _make(self, raw: dict):
        from src.core.sf_config_service import SfConfig
        return SfConfig(raw)

    def test_get_existing_key_returns_value(self):
        cfg = self._make({"score_weight_apex": "10"})
        assert cfg.get("score_weight_apex") == "10"

    def test_get_missing_key_returns_none_by_default(self):
        cfg = self._make({})
        assert cfg.get("missing") is None

    def test_get_missing_key_returns_provided_default(self):
        cfg = self._make({})
        assert cfg.get("missing", "fallback") == "fallback"

    def test_get_int_parses_integer_string(self):
        cfg = self._make({"threshold": "42"})
        assert cfg.get_int("threshold") == 42

    def test_get_int_missing_key_returns_default(self):
        cfg = self._make({})
        assert cfg.get_int("missing", default=7) == 7

    def test_get_int_invalid_value_returns_default(self):
        cfg = self._make({"bad": "not_a_number"})
        assert cfg.get_int("bad", default=0) == 0

    def test_get_float_parses_float_string(self):
        cfg = self._make({"ratio": "0.75"})
        assert cfg.get_float("ratio") == pytest.approx(0.75)

    def test_get_float_missing_returns_default(self):
        cfg = self._make({})
        assert cfg.get_float("x", default=1.5) == pytest.approx(1.5)

    def test_as_dict_returns_all_pairs(self):
        raw = {"a": "1", "b": "2"}
        cfg = self._make(raw)
        assert cfg.as_dict() == raw

    def test_as_dict_returns_independent_copy(self):
        raw = {"a": "1"}
        cfg = self._make(raw)
        cfg.as_dict()["a"] = "mutated"
        assert cfg.get("a") == "1"


# ══════════════════════════════════════════════════════════════════════════════
# SfConfigService — subprocess is mocked throughout
# ══════════════════════════════════════════════════════════════════════════════

class TestSfConfigServiceLoadRuleCatalog:

    def _service(self):
        from src.core.sf_config_service import SfConfigService
        return SfConfigService("ag2rPoc")

    def test_returns_rule_catalog_instance(self):
        from src.analyzer.rule_catalog import RuleCatalog
        with patch("subprocess.run", return_value=_sf_query_response([])):
            catalog = self._service().load_rule_catalog()
        assert isinstance(catalog, RuleCatalog)

    def test_base_rules_present_when_sf_returns_nothing(self):
        """When SF has no rules, catalog still contains rules.xml rules."""
        with patch("subprocess.run", return_value=_sf_query_response([])):
            catalog = self._service().load_rule_catalog()
        # rules.xml is not empty
        assert len(catalog.all) > 0

    def test_sf_override_changes_severity(self):
        """SF record with Severity__c overrides the rules.xml severity for that rule."""
        from src.analyzer.rule_catalog import RuleCatalog
        base = RuleCatalog.load()
        if not base.all:
            pytest.skip("rules.xml is empty")
        target_rule = base.all[0]

        original_severity = target_rule.severity
        new_severity = "Critical" if original_severity != "Critical" else "Info"

        sf_records = [_sf_record({
            "RuleId__c": target_rule.id,
            "IsEnabled__c": target_rule.enabled,
            "Severity__c": new_severity,
            "Category__c": None,
            "Subcategory__c": None,
            "Source__c": None,
            "Message__c": None,
            "Remediation__c": None,
        })]
        with patch("subprocess.run", return_value=_sf_query_response(sf_records)):
            catalog = self._service().load_rule_catalog()

        overridden = catalog.get(target_rule.id)
        assert overridden is not None
        assert overridden.severity == new_severity

    def test_sf_override_disables_rule(self):
        """SF record with IsEnabled__c=False disables a rule that was enabled in rules.xml."""
        from src.analyzer.rule_catalog import RuleCatalog
        base = RuleCatalog.load()
        enabled_rules = base.enabled
        if not enabled_rules:
            pytest.skip("no enabled rules in rules.xml")
        target = enabled_rules[0]

        sf_records = [_sf_record({
            "RuleId__c": target.id,
            "IsEnabled__c": False,
            "Severity__c": None,
            "Category__c": None,
            "Subcategory__c": None,
            "Source__c": None,
            "Message__c": None,
            "Remediation__c": None,
        })]
        with patch("subprocess.run", return_value=_sf_query_response(sf_records)):
            catalog = self._service().load_rule_catalog()

        overridden = catalog.get(target.id)
        assert overridden is not None
        assert overridden.enabled is False

    def test_sf_only_rule_added_to_catalog(self):
        """A rule in SF but absent from rules.xml is added to the catalog."""
        sf_records = [_sf_record({
            "RuleId__c": "SF-ONLY-99",
            "IsEnabled__c": True,
            "Severity__c": "Major",
            "Category__c": "Trusted",
            "Subcategory__c": "Secure",
            "Source__c": "Custom",
            "Message__c": "Custom SF rule",
            "Remediation__c": "Fix it",
        })]
        with patch("subprocess.run", return_value=_sf_query_response(sf_records)):
            catalog = self._service().load_rule_catalog()

        rule = catalog.get("SF-ONLY-99")
        assert rule is not None
        assert rule.severity == "Major"
        assert rule.enabled is True

    def test_sf_record_with_empty_rule_id_is_skipped(self):
        """Records without RuleId__c do not corrupt the catalog."""
        sf_records = [_sf_record({
            "RuleId__c": "",
            "IsEnabled__c": True,
            "Severity__c": "Critical",
            "Category__c": None,
            "Subcategory__c": None,
            "Source__c": None,
            "Message__c": None,
            "Remediation__c": None,
        })]
        with patch("subprocess.run", return_value=_sf_query_response(sf_records)):
            catalog = self._service().load_rule_catalog()
        # No rule with empty id
        assert catalog.get("") is None


class TestSfConfigServiceLoadConfig:

    def _service(self):
        from src.core.sf_config_service import SfConfigService
        return SfConfigService("ag2rPoc")

    def test_returns_sfconfig_instance(self):
        from src.core.sf_config_service import SfConfig
        with patch("subprocess.run", return_value=_sf_query_response([])):
            cfg = self._service().load_config()
        assert isinstance(cfg, SfConfig)

    def test_config_contains_loaded_keys(self):
        records = [
            _sf_record({"ConfigKey__c": "score_weight_apex", "ConfigValue__c": "10"}),
            _sf_record({"ConfigKey__c": "threshold_critical", "ConfigValue__c": "5"}),
        ]
        with patch("subprocess.run", return_value=_sf_query_response(records)):
            cfg = self._service().load_config()
        assert cfg.get("score_weight_apex") == "10"
        assert cfg.get("threshold_critical") == "5"

    def test_empty_sf_returns_empty_config(self):
        with patch("subprocess.run", return_value=_sf_query_response([])):
            cfg = self._service().load_config()
        assert cfg.as_dict() == {}

    def test_record_without_config_key_is_skipped(self):
        records = [
            _sf_record({"ConfigKey__c": None, "ConfigValue__c": "orphan"}),
            _sf_record({"ConfigKey__c": "valid_key", "ConfigValue__c": "42"}),
        ]
        with patch("subprocess.run", return_value=_sf_query_response(records)):
            cfg = self._service().load_config()
        assert "valid_key" in cfg.as_dict()
        assert len(cfg.as_dict()) == 1


class TestSfConfigServiceLoadExclusions:

    def _service(self):
        from src.core.sf_config_service import SfConfigService
        return SfConfigService("ag2rPoc")

    def test_returns_dict(self):
        with patch("subprocess.run", return_value=_sf_query_response([])):
            excl = self._service().load_exclusions()
        assert isinstance(excl, dict)

    def test_empty_sf_returns_empty_dict(self):
        with patch("subprocess.run", return_value=_sf_query_response([])):
            excl = self._service().load_exclusions()
        assert excl == {}

    def test_single_exclusion_parsed_correctly(self):
        records = [_sf_record({
            "RuleId__c": "APEX-001",
            "ComponentName__c": "MyClass",
        })]
        with patch("subprocess.run", return_value=_sf_query_response(records)):
            excl = self._service().load_exclusions()
        assert "APEX-001" in excl
        assert "MyClass" in excl["APEX-001"]

    def test_multiple_components_for_same_rule_grouped(self):
        records = [
            _sf_record({"RuleId__c": "APEX-001", "ComponentName__c": "ClassA"}),
            _sf_record({"RuleId__c": "APEX-001", "ComponentName__c": "ClassB"}),
        ]
        with patch("subprocess.run", return_value=_sf_query_response(records)):
            excl = self._service().load_exclusions()
        assert excl["APEX-001"] == {"ClassA", "ClassB"}

    def test_different_rules_kept_separate(self):
        records = [
            _sf_record({"RuleId__c": "APEX-001", "ComponentName__c": "ClassA"}),
            _sf_record({"RuleId__c": "FLOW-002", "ComponentName__c": "MyFlow"}),
        ]
        with patch("subprocess.run", return_value=_sf_query_response(records)):
            excl = self._service().load_exclusions()
        assert "APEX-001" in excl
        assert "FLOW-002" in excl

    def test_record_with_empty_rule_id_is_skipped(self):
        records = [_sf_record({"RuleId__c": "", "ComponentName__c": "Whatever"})]
        with patch("subprocess.run", return_value=_sf_query_response(records)):
            excl = self._service().load_exclusions()
        assert excl == {}

    def test_record_with_empty_component_name_is_skipped(self):
        records = [_sf_record({"RuleId__c": "APEX-001", "ComponentName__c": ""})]
        with patch("subprocess.run", return_value=_sf_query_response(records)):
            excl = self._service().load_exclusions()
        assert excl == {}

    def test_soql_includes_expiry_filter(self):
        """The SOQL sent to SF must filter on ExpiryDate__c to ignore expired exclusions."""
        with patch("subprocess.run", return_value=_sf_query_response([])) as mock_run:
            self._service().load_exclusions()
        soql_arg = mock_run.call_args[0][0]  # first positional arg = command list
        soql = " ".join(soql_arg)
        assert "ExpiryDate__c" in soql
