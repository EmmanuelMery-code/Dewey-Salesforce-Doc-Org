"""Renderer for the global findings report page."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from src.analyzer.engine import AnalyzerReport
from src.analyzer.models import Finding
from src.core.utils import html_value, write_text
from src.reporting.html.assets import SEVERITY_CSS_CLASS, SEVERITY_LABEL
from src.reporting.html.page_shell import (
    href_relative,
    index_back_link,
    render_page,
)


LogCallback = Callable[[str], None]


def render_findings_report_page(
    analyzer_report: AnalyzerReport,
    current_path: Path,
    output_dir: Path,
    assets_dir: Path,
    object_pages: dict[str, Path],
    apex_pages: dict[str, Path],
    flow_pages: dict[str, Path],
    agent_pages: dict[str, Path] | None = None,
    prompt_pages: dict[str, Path] | None = None,
    omni_pages: dict[str, list[dict[str, object]]] | None = None,
) -> str:
    """Render the global findings report page."""

    back_link = index_back_link(current_path, output_dir)
    all_findings = analyzer_report.all_findings()

    # Flatten omni_pages for easier lookup: name -> Path
    omni_lookup: dict[str, Path] = {}
    if omni_pages:
        for category in omni_pages.values():
            for item in category:
                name = str(item.get("name", ""))
                page = item.get("page")
                if name and isinstance(page, Path):
                    omni_lookup[name] = page

    # Sort findings: Severity first, then target kind, then target name
    all_findings.sort(key=lambda f: (
        f.severity_rank,
        f.target_kind.lower(),
        f.target_name.lower()
    ))

    items: list[str] = []
    for finding in all_findings:
        rule = finding.rule
        severity_css = SEVERITY_CSS_CLASS.get(rule.severity, "sev-info")
        severity_label = SEVERITY_LABEL.get(rule.severity, rule.severity)
        
        # Link to the impacted item if possible
        target_href = ""
        kind_lower = finding.target_kind.lower()
        target_name = finding.target_name
        
        if "apex" in kind_lower:
            page = apex_pages.get(target_name)
            if page:
                target_href = href_relative(current_path, page)
        elif "flow" in kind_lower:
            page = flow_pages.get(target_name)
            if page:
                target_href = href_relative(current_path, page)
        elif "object" in kind_lower or "objet" in kind_lower:
            page = object_pages.get(target_name)
            if page:
                target_href = href_relative(current_path, page)
        elif "validation" in kind_lower:
            # Validation rules are usually named "ObjectName.RuleName"
            if "." in target_name:
                obj_name = target_name.split(".")[0]
                page = object_pages.get(obj_name)
                if page:
                    target_href = href_relative(current_path, page)
        elif "agent" in kind_lower:
            if agent_pages:
                page = agent_pages.get(target_name)
                if page:
                    target_href = href_relative(current_path, page)
        elif "prompt" in kind_lower:
            if prompt_pages:
                page = prompt_pages.get(target_name)
                if page:
                    target_href = href_relative(current_path, page)
        elif "transform" in kind_lower or "omni" in kind_lower:
            page = omni_lookup.get(target_name)
            if page:
                target_href = href_relative(current_path, page)
        
        target_display = html_value(target_name)
        if target_href:
            target_display = f"<a href='{target_href}'>{target_display}</a>"

        reference = ""
        if rule.reference:
            reference = (
                f"<dt>Reference:</dt><dd><a href='{html_value(rule.reference)}' target='_blank' rel='noopener'>{html_value(rule.reference)}</a></dd>"
            )
        
        details_html = ""
        if finding.details:
            detail_items = "".join(
                f"<li>{html_value(detail)}</li>" for detail in finding.details
            )
            details_html = f"<ul class='details'>{detail_items}</ul>"
            
        subcat = f" - {html_value(rule.subcategory)}" if rule.subcategory else ""
        
        items.append(
            "<li class='finding'>"
            "<div class='head'>"
            f"<span class='sev-badge {severity_css}'>{html_value(severity_label)}</span>"
            f"<span class='category-badge'>{html_value(rule.category)}{subcat}</span>"
            f"<span class='rule-id'>{html_value(rule.id)}</span>"
            f"<span class='title'>{html_value(rule.title)}</span>"
            "</div>"
            f"<div class='target-info' style='margin-bottom: 8px; font-size: 0.9rem; color: #475569;'>"
            f"<strong>Item impacté :</strong> {html_value(finding.target_kind)} - {target_display}</div>"
            f"<div class='message'>{html_value(finding.message or rule.description)}</div>"
            "<dl class='metadata'>"
            f"<dt>Justification:</dt><dd>{html_value(rule.rationale)}</dd>"
            f"<dt>Remediation:</dt><dd>{html_value(rule.remediation)}</dd>"
            f"<dt>Source:</dt><dd>{html_value(rule.source)}</dd>"
            f"{reference}"
            "</dl>"
            f"{details_html}"
            "</li>"
        )

    findings_list = "<ul class='findings-list'>" + "".join(items) + "</ul>" if items else "<p class='empty'>Aucun finding détecté.</p>"

    body = f"""
    {back_link}
    <h1>Rapport global des findings</h1>
    <p>Cette page regroupe l'ensemble des alertes détectées par l'analyseur statique sur l'organisation, triées par sévérité.</p>
    {findings_list}
    """

    return render_page("Rapport des findings", body, current_path, assets_dir, include_mermaid=False)


def write_findings_report_page(
    analyzer_report: AnalyzerReport,
    output_dir: Path,
    assets_dir: Path,
    log: LogCallback,
    object_pages: dict[str, Path],
    apex_pages: dict[str, Path],
    flow_pages: dict[str, Path],
    agent_pages: dict[str, Path] | None = None,
    prompt_pages: dict[str, Path] | None = None,
    omni_pages: dict[str, list[dict[str, object]]] | None = None,
) -> Path:
    """Write findings_report.html and return its path."""
    path = output_dir / "findings_report.html"
    write_text(path, render_findings_report_page(
        analyzer_report, path, output_dir, assets_dir, 
        object_pages, apex_pages, flow_pages,
        agent_pages=agent_pages,
        prompt_pages=prompt_pages,
        omni_pages=omni_pages
    ))
    log(f"Rapport global des findings généré : {path}")
    return path
