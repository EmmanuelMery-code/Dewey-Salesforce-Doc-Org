"""Tests: links to the finding lines next to the class / trigger badge.

Contracts tested:
  render_findings_lines(findings)
    one link per source line carrying a finding, sorted and deduplicated,
    each with a tooltip "Ligne N : <titre(s)>"; the list starts hidden (the
    page script only shows it on the "Code source" tab) and is empty when
    no finding is tied to a line.
  render_apex_page
    puts the list right after the kind badge, above the tabs, and "</" is
    escaped in the embedded annotations so a message cannot close the script.
"""

from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path

from src.analyzer.models import Finding, Rule
from src.core.models import ApexArtifact, ReviewResult
from src.reporting.html.renderers.apex import render_apex_page, render_findings_lines


def _finding(line: int | None, title: str = "Regle", message: str = "msg") -> Finding:
    rule = Rule(
        id="APEX-PERF-001",
        enabled=True,
        scope="apex_class",
        category="Performance",
        subcategory="",
        severity="Major",
        source="Dewey",
        reference="",
        title=title,
        description="",
        rationale="",
        remediation="",
    )
    return Finding(
        rule=rule, target_kind="ApexClass", target_name="AccountService", message=message, line=line
    )


class _Links(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.span: dict[str, str | None] = {}
        self.links: list[tuple[str | None, str | None]] = []

    def handle_starttag(self, tag, attrs) -> None:
        attributes = dict(attrs)
        if tag == "span" and attributes.get("id") == "apex-findings-lines":
            self.span = attributes
        if tag == "a":
            self.links.append((attributes.get("href"), attributes.get("title")))


def _parse(markup: str) -> _Links:
    parser = _Links()
    parser.feed(markup)
    return parser


def _page(tmp_path: Path, findings: list[Finding]) -> str:
    artifact = ApexArtifact(
        name="AccountService",
        kind="class",
        body="public class AccountService {\n}\n",
        source_path=Path("AccountService.cls"),
    )
    return render_apex_page(
        artifact,
        ReviewResult(summary=""),
        tmp_path / "apex" / "AccountService.html",
        tmp_path,
        tmp_path / "assets",
        {},
        [],
        [],
        findings=findings,
    )


class TestRenderFindingsLines:
    def test_one_link_per_line_with_number_and_titles_in_the_tooltip(self) -> None:
        parsed = _parse(
            render_findings_lines(
                [
                    _finding(10, "SOQL dynamique"),
                    _finding(7, "DML dans boucle"),
                    _finding(7, "Pas de bulk"),
                    _finding(7, "DML dans boucle"),
                    _finding(None, "Globale"),
                ]
            )
        )

        assert "hidden" in parsed.span
        assert parsed.links == [
            ("#apex-L7", "Ligne 7 : DML dans boucle / Pas de bulk"),
            ("#apex-L10", "Ligne 10 : SOQL dynamique"),
        ]

    def test_titles_are_escaped_in_the_tooltip(self) -> None:
        markup = render_findings_lines([_finding(3, "a' onmouseover='x")])

        assert "onmouseover='x" not in markup
        assert _parse(markup).links == [("#apex-L3", "Ligne 3 : a' onmouseover='x")]

    def test_nothing_without_line_bound_findings(self) -> None:
        assert render_findings_lines([_finding(None)]) == ""


class TestApexPage:
    def test_list_sits_after_the_badge_above_the_tabs(self, tmp_path: Path) -> None:
        page = _page(tmp_path, [_finding(1)])

        badge = page.index("<span class=\"badge\">class</span>")
        assert badge < page.index("id='apex-findings-lines'") < page.index("<div class='tabs'>")

    def test_messages_cannot_close_the_script_tag(self, tmp_path: Path) -> None:
        page = _page(tmp_path, [_finding(1, message="</script><b>x</b>")])

        assert "</script><b>" not in page
