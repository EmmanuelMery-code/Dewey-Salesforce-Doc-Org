"""Tests: OmniUiCard components are documented under a FlexCards subsection.

Contract tested:
  SalesforceMetadataParser(...).parse() -> MetadataSnapshot
    snapshot.inventory["omnistudio"] contains one row per OmniUiCard found in
    the `omniUiCard` Metadata API folder (singular), and
    snapshot.metrics.omni_ui_cards counts them.

  write_omni_pages(...) -> dict[label, entries]
    groups those rows under the "FlexCards" label and writes one detail page
    per card, so the index panel can link to each card's analysis page.
"""

from __future__ import annotations

from pathlib import Path

from src.parsers.salesforce_parser import SalesforceMetadataParser
from src.reporting.html.renderers.index_panels import render_index_omni_panel
from src.reporting.html.renderers.omni import write_omni_pages

FLEXCARD = """<?xml version="1.0" encoding="UTF-8"?>
<OmniUiCard xmlns="http://soap.sforce.com/2006/04/metadata">
    <authorName>Ada Lovelace</authorName>
    <isActive>true</isActive>
    <masterLabel>Account Overview</masterLabel>
    <name>AccountOverview</name>
    <omniUiCardType>Parent</omniUiCardType>
    <versionNumber>3</versionNumber>
</OmniUiCard>
"""


def _build_source(tmp_path: Path) -> Path:
    source = tmp_path / "source"
    cards_dir = source / "omniUiCard"
    cards_dir.mkdir(parents=True, exist_ok=True)
    (cards_dir / "AccountOverview.ouc-meta.xml").write_text(FLEXCARD, encoding="utf-8")
    return source


class TestFlexCardParsing:
    def test_card_is_added_to_the_omnistudio_inventory(self, tmp_path: Path) -> None:
        snapshot = SalesforceMetadataParser(_build_source(tmp_path)).parse()

        rows = snapshot.inventory.get("omnistudio") or []
        names = {str(row.get("Nom")) for row in rows}

        assert "AccountOverview" in names
        card_row = next(row for row in rows if row.get("Nom") == "AccountOverview")
        assert str(card_row.get("Dossier")) == "omniUiCard"

    def test_card_is_counted_in_the_customization_metrics(self, tmp_path: Path) -> None:
        snapshot = SalesforceMetadataParser(_build_source(tmp_path)).parse()

        assert snapshot.metrics.omni_ui_cards == 1


class TestFlexCardDocumentation:
    def _write_pages(self, tmp_path: Path) -> tuple[dict, Path]:
        snapshot = SalesforceMetadataParser(_build_source(tmp_path)).parse()
        output_dir = tmp_path / "html"
        omni_pages = write_omni_pages(
            snapshot,
            output_dir / "omni",
            output_dir,
            output_dir / "assets",
            log=lambda _message: None,
        )
        return omni_pages, output_dir

    def test_cards_are_grouped_under_a_flexcards_subsection(self, tmp_path: Path) -> None:
        omni_pages, _ = self._write_pages(tmp_path)

        assert "FlexCards" in omni_pages
        assert [entry["name"] for entry in omni_pages["FlexCards"]] == ["AccountOverview"]

    def test_each_card_gets_its_own_analysis_page(self, tmp_path: Path) -> None:
        omni_pages, _ = self._write_pages(tmp_path)

        page = omni_pages["FlexCards"][0]["page"]
        assert page.exists()
        content = page.read_text(encoding="utf-8")
        assert "Analyseur" in content
        assert "Account Overview" in content
        assert "Ada Lovelace" in content

    def test_index_panel_links_to_the_card_page(self, tmp_path: Path) -> None:
        omni_pages, output_dir = self._write_pages(tmp_path)

        panel = render_index_omni_panel(omni_pages, output_dir / "index.html")

        assert "FlexCards (1)" in panel
        assert "omni/flexcards/accountoverview.html" in panel
