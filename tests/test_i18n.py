"""Garde-fous d'internationalisation (francais / anglais).

Couvre les trois sources de texte d'un finding :
  - les libelles de regles charges depuis rules.xml,
  - les messages construits par les analyseurs,
  - l'habillage des pages HTML.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from src.analyzer.flow_analyzer import analyze_flow
from src.analyzer.messages import MESSAGES
from src.analyzer.rule_catalog import DEFAULT_RULES_PATH, RuleCatalog
from src.core.models import FlowInfo
from src.reporting import i18n
from src.reporting.html.findings import render_analyzer_tab


_PLACEHOLDER_RE = re.compile(r"\{(\w+)\}")
_RULE_TEXT_TAGS = ("title", "description", "rationale", "remediation")


def _placeholders(template: str) -> set[str]:
    return set(_PLACEHOLDER_RE.findall(template))


@pytest.fixture(autouse=True)
def _reset_report_language():
    """Keep the module-level report language from leaking across tests."""
    previous = i18n.CURRENT_LANGUAGE
    yield
    i18n.set_report_language(previous)


# --------------------------------------------------------------- rules.xml


class TestRulesXmlTranslations:
    def _rule_nodes(self) -> list[ET.Element]:
        return ET.parse(DEFAULT_RULES_PATH).getroot().findall("rule")

    def test_every_rule_declares_an_english_translation(self) -> None:
        missing = [
            node.get("id")
            for node in self._rule_nodes()
            if not any(
                (child.get("lang") or "").lower() == "en"
                for child in node.findall("translation")
            )
        ]
        assert missing == []

    def test_english_translations_are_complete(self) -> None:
        incomplete: list[str] = []
        for node in self._rule_nodes():
            translation = next(
                child
                for child in node.findall("translation")
                if (child.get("lang") or "").lower() == "en"
            )
            for tag in _RULE_TEXT_TAGS:
                child = translation.find(tag)
                if child is None or not (child.text or "").strip():
                    incomplete.append(f"{node.get('id')}/{tag}")
        assert incomplete == []

    def test_english_catalog_differs_from_french(self) -> None:
        french = RuleCatalog.load()
        english = RuleCatalog.load(language="en")
        assert len(english.all) == len(french.all)

        untranslated = [
            rule.id
            for rule in english.all
            for tag in _RULE_TEXT_TAGS
            if getattr(rule, tag) == getattr(french.get(rule.id), tag)
        ]
        assert untranslated == []

    def test_unknown_language_falls_back_to_french(self) -> None:
        french = RuleCatalog.load()
        fallback = RuleCatalog.load(language="de")
        assert fallback.language == "fr"
        assert fallback.get("FLOW-READ-001").title == french.get("FLOW-READ-001").title


# --------------------------------------------------- analyzer message catalog


class TestAnalyzerMessageCatalog:
    def test_french_and_english_declare_the_same_keys(self) -> None:
        assert set(MESSAGES["fr"]) == set(MESSAGES["en"])

    def test_placeholders_match_across_languages(self) -> None:
        mismatched = [
            key
            for key, french in MESSAGES["fr"].items()
            if _placeholders(french) != _placeholders(MESSAGES["en"][key])
        ]
        assert mismatched == []

    def test_catalog_translates_messages(self) -> None:
        key = "flow.no_description.message"
        assert RuleCatalog.load().t(key) == MESSAGES["fr"][key]
        assert RuleCatalog.load(language="en").t(key) == MESSAGES["en"][key]

    def test_unknown_key_is_returned_verbatim(self) -> None:
        assert RuleCatalog.load().t("does.not.exist") == "does.not.exist"


# ------------------------------------------------------- analyzer findings


def _flow() -> FlowInfo:
    return FlowInfo(
        name="Order_Sync",
        description="",
        total_elements=45,
        described_elements=4,
        status="Draft",
        max_depth=6,
        api_call_in_loop=True,
        api_call_in_loop_actions=["Call_External_Service"],
    )


class TestFindingsAreLocalized:
    def test_flow_findings_use_the_catalog_language(self) -> None:
        flow = _flow()
        french = {f.rule.id: f for f in analyze_flow(flow, RuleCatalog.load())}
        english = {
            f.rule.id: f for f in analyze_flow(flow, RuleCatalog.load(language="en"))
        }

        assert french.keys() == english.keys()
        assert french["FLOW-READ-001"].message == (
            "Le flow ne porte pas de description globale."
        )
        assert english["FLOW-READ-001"].message == (
            "The flow carries no global description."
        )

    def test_finding_details_are_localized(self) -> None:
        flow = _flow()
        french = next(
            f
            for f in analyze_flow(flow, RuleCatalog.load())
            if f.rule.id == "FLOW-PERF-004"
        )
        english = next(
            f
            for f in analyze_flow(flow, RuleCatalog.load(language="en"))
            if f.rule.id == "FLOW-PERF-004"
        )
        assert french.details == ["Action(s) concernee(s) : Call_External_Service."]
        assert english.details == ["Action(s) involved: Call_External_Service."]

    def test_dynamic_values_survive_translation(self) -> None:
        """Counts interpolated into a message must appear in both languages."""
        flow = _flow()
        for language in ("fr", "en"):
            finding = next(
                f
                for f in analyze_flow(flow, RuleCatalog.load(language=language))
                if f.rule.id == "FLOW-MAINT-001"
            )
            assert "45" in finding.message


# ----------------------------------------------------------- HTML chrome


class TestHtmlFindingsChrome:
    def _tab(self, language: str) -> str:
        flow = _flow()
        findings = analyze_flow(flow, RuleCatalog.load(language=language))
        i18n.set_report_language(language)
        return render_analyzer_tab(findings)

    def test_severity_chips_and_metadata_labels_follow_the_language(self) -> None:
        french = self._tab("fr")
        assert "Critique" in french
        assert "Justification :" in french

        english = self._tab("en")
        assert "Critical" in english
        assert "Rationale:" in english
        assert "Justification" not in english

    def test_empty_state_follows_the_language(self) -> None:
        i18n.set_report_language("fr")
        assert "Aucun point d'alerte" in render_analyzer_tab([])
        i18n.set_report_language("en")
        assert "No alert raised by the analyzer." in render_analyzer_tab([])

    def test_reporting_labels_declare_the_same_keys(self) -> None:
        assert set(i18n.LABELS["fr"]) == set(i18n.LABELS["en"])

    def test_reporting_placeholders_match_across_languages(self) -> None:
        mismatched = [
            key
            for key, french in i18n.LABELS["fr"].items()
            if _placeholders(french) != _placeholders(i18n.LABELS["en"][key])
        ]
        assert mismatched == []
