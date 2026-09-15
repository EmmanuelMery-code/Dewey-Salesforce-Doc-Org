"""Garde-fous d'internationalisation (francais / anglais).

Couvre les sources de texte du rapport :
  - les libelles de regles charges depuis rules.xml,
  - les messages construits par les analyseurs,
  - l'habillage des pages HTML (findings, puis pages de detail).
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from src.analyzer.flow_analyzer import analyze_flow
from src.analyzer.messages import MESSAGES
from src.analyzer.rule_catalog import DEFAULT_RULES_PATH, RuleCatalog
from src.core.models import (
    ApexArtifact,
    Dependency,
    FieldInfo,
    FlowInfo,
    MetadataSnapshot,
    ObjectInfo,
    RelationshipInfo,
    ReviewResult,
    ValidationRuleInfo,
)
from src.core.models.automation import FlowElementInfo
from src.reporting import i18n
from src.reporting.html.findings import render_analyzer_tab
from src.reporting.html.page_shell import complexity_badge_class
from src.reporting.html.renderers.apex import render_apex_page
from src.reporting.html.renderers.flows import render_flow_page
from src.reporting.html.renderers.objects import render_object_page


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


# --------------------------------------------- valeurs de domaine affichees

#: Les tables de correspondance traduisent l'affichage de valeurs qui restent
#: stockees en francais dans le modele.
_DOMAIN_MAPPINGS = (
    i18n.FLOW_COMPLEXITY_LABEL_KEYS,
    i18n.DEPENDENCY_DIRECTION_LABEL_KEYS,
    i18n.DEPENDENCY_CATEGORY_LABEL_KEYS,
    i18n.DEPENDENCY_RELATION_LABEL_KEYS,
)


class TestDomainValueLabels:
    def test_every_mapping_targets_a_declared_key(self) -> None:
        unknown = [
            key
            for mapping in _DOMAIN_MAPPINGS
            for key in mapping.values()
            if key not in i18n.LABELS["fr"]
        ]
        assert unknown == []

    def test_french_display_matches_the_stored_value(self) -> None:
        """En francais l'affichage doit rester celui de la valeur stockee."""
        i18n.set_report_language("fr")
        assert i18n.flow_complexity_label("Tres complexe") == "Tres complexe"
        assert i18n.dependency_direction_label("Entrant") == "Entrant"
        assert i18n.dependency_relation_label("Usage objet") == "Usage objet"
        assert i18n.dependency_category_label("Objet") == "Objet"

    def test_english_display_is_translated(self) -> None:
        i18n.set_report_language("en")
        assert i18n.flow_complexity_label("Tres complexe") == "Very complex"
        assert i18n.dependency_direction_label("Entrant") == "Incoming"
        assert i18n.dependency_relation_label("Usage objet") == "Object usage"
        assert i18n.dependency_category_label("Objet") == "Object"

    def test_unknown_values_pass_through(self) -> None:
        """Une valeur inattendue doit rester lisible plutot que disparaitre."""
        for language in ("fr", "en"):
            i18n.set_report_language(language)
            assert i18n.flow_complexity_label("Inconnu") == "Inconnu"
            assert i18n.dependency_category_label("LWC") == "LWC"
            assert i18n.dependency_relation_label("Nouveau lien") == "Nouveau lien"

    def test_complexity_badge_class_keys_on_the_stored_value(self) -> None:
        """Traduire l'affichage ne doit pas casser la classe CSS du badge."""
        i18n.set_report_language("en")
        assert complexity_badge_class("Moyen") == "complexity-medium"
        assert complexity_badge_class(i18n.flow_complexity_label("Moyen")) == ""


# ----------------------------------------------------- pages de detail HTML


def _object() -> ObjectInfo:
    return ObjectInfo(
        api_name="Contrat__c",
        label="Contrat",
        fields=[FieldInfo(api_name="Montant__c", data_type="Currency", required=True)],
        validation_rules=[
            ValidationRuleInfo(
                full_name="Montant_Positif",
                active=True,
                error_condition_formula="Montant__c <= 0",
            )
        ],
        relationships=[RelationshipInfo("Adherent__c", "Lookup", ["Account"])],
    )


def _apex() -> ApexArtifact:
    return ApexArtifact(
        name="ContratService",
        kind="class",
        body="public class ContratService {}",
        source_path=Path("ContratService.cls"),
        test_coverage=72.5,
    )


def _flow_page_model() -> FlowInfo:
    return FlowInfo(
        name="Contrat_Validation",
        process_type="AutoLaunchedFlow",
        start_node="Decision_Montant",
        element_counts={"decisions": 1},
        total_elements=1,
        elements=[
            FlowElementInfo(
                element_type="decisions",
                name="Decision_Montant",
                label="Montant valide ?",
                covered_by=["ContratServiceTest"],
            )
        ],
        test_coverage=50.0,
        test_coverage_elements_covered=1,
        test_coverage_elements_uncovered=1,
    )


#: Un lien entrant et un lien sortant, pour couvrir les deux sens affichés.
_DEPENDENCY_ROWS = [
    {
        "name": "Contrat__c",
        "category": "Objet",
        "subtype": "sObject",
        "direction": "Sortant",
        "relation": "Usage objet",
    },
    {
        "name": "ContratService",
        "category": "Apex",
        "subtype": "class",
        "direction": "Entrant",
        "relation": "Reference code",
    },
]


def _render_detail_pages(language: str, tmp_path: Path) -> dict[str, str]:
    """Render one page of each kind in ``language``."""
    i18n.set_report_language(language)
    obj, artifact, flow = _object(), _apex(), _flow_page_model()
    review = ReviewResult(summary="Resume.", positives=[], improvements=[])
    snapshot = MetadataSnapshot(
        source_dir=tmp_path,
        package_roots=[tmp_path],
        objects=[obj],
        apex_artifacts=[artifact],
        flows=[flow],
        dependencies=[Dependency("ContratService", "Apex", "Contrat__c", "Object")],
    )
    assets = tmp_path / "assets"
    return {
        "object": render_object_page(
            obj, snapshot, tmp_path / "o.html", tmp_path, assets
        ),
        "apex": render_apex_page(
            artifact,
            review,
            tmp_path / "a.html",
            tmp_path,
            assets,
            {},
            list(_DEPENDENCY_ROWS),
            [],
        ),
        "flow": render_flow_page(
            flow,
            review,
            tmp_path / "f.html",
            tmp_path,
            assets,
            list(_DEPENDENCY_ROWS),
            {},
            {},
            {},
        ),
    }


class TestDetailPagesChrome:
    def test_french_chrome(self, tmp_path: Path) -> None:
        pages = _render_detail_pages("fr", tmp_path)
        assert "Retour a l'index" in pages["object"]
        assert ">Synthese<" in pages["object"]
        assert "Analyse d'impact (Ou est-il utilise ?)" in pages["object"]
        assert ">Code source<" in pages["apex"]
        assert "Nature du lien" in pages["apex"]
        assert "Score complexite" in pages["flow"]
        assert "Représentation graphique" in pages["flow"]

    def test_english_chrome(self, tmp_path: Path) -> None:
        pages = _render_detail_pages("en", tmp_path)
        assert "Back to index" in pages["object"]
        assert ">Overview<" in pages["object"]
        assert "Impact analysis (where is it used?)" in pages["object"]
        assert ">Source code<" in pages["apex"]
        assert "Link type" in pages["apex"]
        assert "Complexity score" in pages["flow"]
        assert "Graphical representation" in pages["flow"]

    def test_page_lang_attribute_follows_the_language(self, tmp_path: Path) -> None:
        for language, expected in (("fr", 'lang="fr"'), ("en", 'lang="en"')):
            for page in _render_detail_pages(language, tmp_path).values():
                assert expected in page

    def test_english_pages_drop_the_french_chrome(self, tmp_path: Path) -> None:
        pages = _render_detail_pages("en", tmp_path)
        for label in ("Retour a l'index", "Recherche globale", "Nature du lien"):
            for kind, page in pages.items():
                assert label not in page, f"{label!r} subsiste dans la page {kind}"

    def test_dependency_table_translates_only_the_display(
        self, tmp_path: Path
    ) -> None:
        """Le graphe JavaScript filtre sur la valeur brute, pas sur l'affichage."""
        apex_page = _render_detail_pages("en", tmp_path)["apex"]
        assert "<td>Incoming</td>" in apex_page
        assert "<td>Code reference</td>" in apex_page
        assert '"direction": "Entrant"' in apex_page

    def test_empty_states_follow_the_language(self, tmp_path: Path) -> None:
        bare = ObjectInfo(api_name="Vide__c")
        snapshot = MetadataSnapshot(source_dir=tmp_path, package_roots=[tmp_path])
        for language, expected in (
            ("fr", "Aucun champ detecte."),
            ("en", "No field detected."),
        ):
            i18n.set_report_language(language)
            page = render_object_page(
                bare, snapshot, tmp_path / "v.html", tmp_path, tmp_path / "assets"
            )
            assert expected in page
