"""Render the per-flow documentation pages."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from src.analyzer.models import Finding
from src.core.models import FlowInfo, MetadataSnapshot, ReviewResult, Dependency
from src.core.utils import html_value, safe_slug, write_text

from src.reporting.html.dependencies import (
    build_flow_reference_index,
    flow_dependencies,
    get_incoming_dependencies,
    render_component_dependency_graph,
    render_dependency_rows,
)
from src.reporting.html.findings import (
    findings_to_review_improvements,
    render_analyzer_tab,
    render_findings_summary,
)
from src.reporting.html.one_page import render_one_page_graph
from src.reporting.html.page_shell import (
    complexity_badge_class,
    href_relative,
    index_back_link,
    list_or_empty,
    render_page,
    tabbed_sections,
)
from src.reporting.i18n import flow_complexity_label, t


LogCallback = Callable[[str], None]


def render_flow_graph(flow: FlowInfo, findings: list[Finding], improvements: list[str]) -> str:
    """Render a Mermaid.js graph for the flow with zoom, drag and tooltips."""
    if not flow.elements:
        return ""

    lines = ["graph TD"]
    
    # Define styles
    lines.append("classDef critical fill:#fee2e2,stroke:#ef4444,stroke-width:2px")
    lines.append("classDef major fill:#ffedd5,stroke:#f97316,stroke-width:2px")
    lines.append("classDef info fill:#eff6ff,stroke:#3b82f6,stroke-width:1px")
    lines.append("classDef start fill:#f0fdf4,stroke:#22c55e,stroke-width:2px")

    # Collect messages per element
    element_issues = {}
    critical_elements = set()
    major_elements = set()
    
    for element in flow.elements:
        msgs = []
        is_critical = False
        is_major = False
        
        # Check findings
        for f in findings:
            # Match by name or label in message or details
            match = False
            if element.name.lower() in f.message.lower(): match = True
            elif element.label and element.label.lower() in f.message.lower(): match = True
            elif any(element.name.lower() in d.lower() for d in f.details): match = True
            elif element.label and any(element.label.lower() in d.lower() for d in f.details): match = True
            
            if match:
                msgs.append(f"[{f.rule.severity}] {f.message}")
                if f.rule.severity == "Critical":
                    is_critical = True
                else:
                    is_major = True
        
        # Check improvements (heuristics)
        for imp in improvements:
            match = False
            if element.name.lower() in imp.lower(): match = True
            elif element.label and element.label.lower() in imp.lower(): match = True
            
            if match:
                msgs.append(f"[{t('flow_graph_improvement')}] {imp}")
                is_major = True
        
        if msgs:
            element_issues[element.name] = " | ".join(msgs).replace('"', "'")
            if is_critical:
                critical_elements.add(element.name)
            elif is_major:
                major_elements.add(element.name)

    # Map element types to Mermaid shapes
    for element in flow.elements:
        shape_start, shape_end = "[", "]"
        if element.element_type == "decisions":
            shape_start, shape_end = "{", "}"
        elif element.element_type == "loops":
            shape_start, shape_end = "([", "])"
        elif element.element_type == "screens":
            shape_start, shape_end = "[[", "]]"

        clean_label = (element.label or element.name).replace('"', "'")
        label = f"{clean_label}<br/><small>({element.element_type})</small>"
        lines.append(f"{element.name}{shape_start}\"{label}\"{shape_end}")
        
        # Add tooltip if there are issues
        if element.name in element_issues:
            lines.append(f"click {element.name} \"{element_issues[element.name]}\"")

        # Connect to targets with labels
        for conn in element.connectors:
            if conn.label:
                lines.append(f"{element.name} -- \"{conn.label}\" --> {conn.target}")
            else:
                lines.append(f"{element.name} --> {conn.target}")

    # Start node
    if flow.start_node:
        lines.insert(1, f"START(({t('flow_graph_start')})) --> {flow.start_node}")
        lines.append("class START start")

    # Apply classes
    if critical_elements:
        lines.append(f"class {','.join(critical_elements)} critical")
    if major_elements:
        lines.append(f"class {','.join(major_elements)} major")

    mermaid_code = "\n".join(lines)
    
    return f"""
<div class="section">
    <h3>{t('flow_graph_heading')}</h3>
    <div class="mermaid-container">
        <div class="mermaid-toolbar">
            <button class="mm-btn" data-mermaid-action="zoom-in" title="{t('mermaid_zoom_in')}">+</button>
            <button class="mm-btn" data-mermaid-action="zoom-out" title="{t('mermaid_zoom_out')}">-</button>
            <button class="mm-btn" data-mermaid-action="reset" title="{t('mermaid_reset')}">Reset</button>
            <span class="mm-hint">{t('flow_graph_hint')}</span>
        </div>
        <div class="mermaid">
{mermaid_code}
        </div>
    </div>
    <div class="legend" style="margin-top: 10px; font-size: 0.9rem;">
        <span style="display: inline-block; width: 15px; height: 15px; background: #fee2e2; border: 1px solid #ef4444; margin-right: 5px;"></span> {t('flow_graph_legend_critical')}
        <span style="display: inline-block; width: 15px; height: 15px; background: #ffedd5; border: 1px solid #f97316; margin-left: 15px; margin-right: 5px;"></span> {t('flow_graph_legend_major')}
        <span style="display: inline-block; width: 15px; height: 15px; background: #f0fdf4; border: 1px solid #22c55e; margin-left: 15px; margin-right: 5px;"></span> {t('flow_graph_legend_start')}
    </div>
</div>
"""


def render_flow_page(
    flow: FlowInfo,
    review: ReviewResult,
    current_path: Path,
    output_dir: Path,
    assets_dir: Path,
    dependencies: list[dict[str, str]],
    flow_pages: dict[str, Path],
    object_pages: dict[str, Path],
    apex_pages: dict[str, Path],
    all_dependencies: list[Dependency] | None = None,
    findings: list[Finding] | None = None,
) -> str:
    findings = findings or []
    all_dependencies = all_dependencies or []
    
    # Merge with incoming dependencies
    incoming = get_incoming_dependencies(flow.name, "Flow", all_dependencies)
    for inc in incoming:
        if not any(d["name"] == inc["name"] and d["direction"] == "Entrant" for d in dependencies):
            dependencies.append(inc)
            
    metrics_list = list(review.metrics)
    coverage_metric_label = t("detail_test_coverage")
    if flow.test_coverage is not None:
        covered = flow.test_coverage_elements_covered
        total = flow.test_coverage_elements_covered + flow.test_coverage_elements_uncovered
        coverage_label = t(
            "flow_coverage_value",
            percent=f"{flow.test_coverage:.1f}",
            covered=covered,
            total=total,
        )
    else:
        coverage_label = "N/A"
    metrics_list.append((coverage_metric_label, coverage_label))

    metric_tooltips = {
        coverage_metric_label: t("flow_coverage_tooltip"),
    }
    metrics = "".join(
        (
            f"<li title=\"{metric_tooltips[label]}\"><strong>{html_value(label)}:</strong> {html_value(value)}</li>"
            if label in metric_tooltips
            else f"<li><strong>{html_value(label)}:</strong> {html_value(value)}</li>"
        )
        for label, value in metrics_list
    )
    has_coverage = flow.test_coverage is not None
    
    header_extra = f"<th>{t('flow_th_tested_by')}</th>" if has_coverage else ""
    
    def render_element_row(element):
        coverage_cell = ""
        if has_coverage:
            if element.covered_by:
                classes = ", ".join(element.covered_by)
                coverage_cell = (
                    f"<td style='color: #16a34a;' title='{t('flow_tested_by_title', classes=classes)}'>"
                    f"{t('flow_tested_yes', count=len(element.covered_by))}</td>"
                )
            else:
                coverage_cell = f"<td style='color: #dc2626;'>{t('value_no')}</td>"
        
        return (
            f"<tr><td>{html_value(element.element_type)}</td><td>{html_value(element.name)}</td>"
            f"<td>{html_value(element.label)}</td><td>{html_value(element.description)}</td>"
            f"<td>{html_value(element.target)}</td>{coverage_cell}</tr>"
        )

    elements_rows = "".join(
        render_element_row(element)
        for element in flow.elements
    ) or f"<tr><td colspan='{6 if has_coverage else 5}' class='empty'>{t('flow_elements_empty')}</td></tr>"

    count_rows = "".join(
        f"<tr><td>{html_value(name)}</td><td>{count}</td></tr>"
        for name, count in sorted(flow.element_counts.items())
    ) or f"<tr><td colspan='2' class='empty'>{t('flow_blocks_empty')}</td></tr>"
    relation_rows = render_dependency_rows(
        dependencies,
        current_path,
        {"Flow": flow_pages, "Objet": object_pages, "Apex": apex_pages},
    )
    relation_graph = render_component_dependency_graph(flow.name, "Flow", dependencies, safe_slug(flow.name))
    one_page_graph = render_one_page_graph(
        flow.name, "Flow", all_dependencies, safe_slug(flow.name)
    )
    analyzer_tab = render_analyzer_tab(findings)
    analyzer_inline_summary = render_findings_summary(findings)
    improvements_augmented = list(review.improvements) + findings_to_review_improvements(findings)
    
    flow_graph = render_flow_graph(flow, findings, improvements_augmented)
    
    description_html = (
        f"<div class='section'><h3>Description</h3><p>{html_value(flow.description)}</p></div>"
        if (flow.description or "").strip()
        else ""
    )
    summary_html = (
        description_html
        + f"<p>{html_value(review.summary)}</p>"
        f"<div class='section'><h3>{t('detail_analyzer_alerts')}</h3>"
        + analyzer_inline_summary
        + "</div>"
    )
    tabs = tabbed_sections(
        f"flow-{safe_slug(flow.name)}",
        [
            (t("tab_summary"), summary_html),
            (t("tab_chart"), flow_graph),
            (t("tab_metrics"), f"<ul>{metrics}</ul>"),
            (t("tab_breakdown"), f"<table><thead><tr><th>Type</th><th>{t('flow_th_count')}</th></tr></thead><tbody>{count_rows}</tbody></table>"),
            (t("tab_strengths"), list_or_empty(review.positives, t("detail_no_strengths"))),
            (t("tab_heuristics"), list_or_empty(improvements_augmented, t("detail_no_improvements"))),
            (t("tab_analyzer"), analyzer_tab),
            (
                t("tab_relationships"),
                f"<table><thead><tr><th>{t('dependency_th_linked_component')}</th><th>{t('dependency_th_category')}</th><th>{t('dependency_th_subtype')}</th><th>{t('dependency_th_direction')}</th><th>{t('dependency_th_relation')}</th></tr></thead><tbody>{relation_rows}</tbody></table>{relation_graph}",
            ),
            ("One Page", one_page_graph),
            (
                t("tab_elements"),
                f"<div class='table-scroll'><table><thead><tr><th>Type</th><th>{t('object_th_name')}</th><th>{t('flow_th_label')}</th><th>Description</th><th>{t('flow_th_target')}</th>{header_extra}</tr></thead><tbody>{elements_rows}</tbody></table></div>",
            ),
        ],
    )
    body = f"""
{index_back_link(current_path, output_dir, "flows")}
<h1>{html_value(flow.name)}</h1>
<span class="badge">{html_value(flow.process_type or 'Flow')}</span>
<span class="badge {complexity_badge_class(flow.complexity_level)}">{html_value(flow_complexity_label(flow.complexity_level))}</span>
<div class="cards smallcards">
  <div class="card"><span>{t('flow_card_complexity_score')}</span><span class="value">{flow.complexity_score}</span></div>
  <div class="card"><span>{t('flow_card_elements')}</span><span class="value">{flow.total_elements}</span></div>
  <div class="card"><span>{t('flow_card_documented')}</span><span class="value">{flow.described_elements}</span></div>
  <div class="card"><span>{t('flow_card_variables')}</span><span class="value">{flow.variable_total}</span></div>
  <div class="card"><span>{t('flow_card_depth')}</span><span class="value">{flow.max_depth}</span></div>
  <div class="card"><span>{t('flow_card_max_width')}</span><span class="value">{flow.max_width}</span></div>
  <div class="card"><span>{t('flow_card_min_max_height')}</span><span class="value">{flow.min_height}/{flow.max_height}</span></div>
</div>
{tabs}
"""
    return render_page(flow.name, body, current_path, assets_dir, include_mermaid=True)


def write_flow_pages(
    snapshot: MetadataSnapshot,
    reviews: dict[str, ReviewResult],
    object_pages: dict[str, Path],
    apex_pages: dict[str, Path],
    flows_dir: Path,
    output_dir: Path,
    assets_dir: Path,
    log: LogCallback,
    *,
    analyzer_report=None,
) -> dict[str, Path]:
    flows = snapshot.flows
    output: dict[str, Path] = {}
    for flow in flows:
        path = flows_dir / f"{safe_slug(flow.name)}.html"
        output[flow.name] = path

    flow_bodies = {
        flow.name: flow.source_path.read_text(encoding="utf-8", errors="ignore")
        if flow.source_path and flow.source_path.exists()
        else ""
        for flow in flows
    }
    flow_ref_index = build_flow_reference_index(flows, flow_bodies)
    object_names = [item.api_name for item in snapshot.objects]
    apex_names = [item.name for item in snapshot.apex_artifacts]
    flow_findings = getattr(analyzer_report, "flows", {}) if analyzer_report else {}

    total = len(flows)
    for index, flow in enumerate(flows):
        path = output[flow.name]
        
        if index % 20 == 0:
            log(f"Generation HTML : Flow {index + 1}/{total} ({flow.name})")
            
        dependencies = flow_dependencies(
            flow,
            flow_ref_index,
            flow_bodies.get(flow.name, ""),
            object_names,
            apex_names,
        )
        write_text(
            path,
            render_flow_page(
                flow,
                reviews[flow.name],
                path,
                output_dir,
                assets_dir,
                dependencies,
                output,
                object_pages,
                apex_pages,
                all_dependencies=snapshot.dependencies,
                findings=flow_findings.get(flow.name, []),
            ),
        )
    log(f"{len(output)} page(s) Flow generee(s).")
    return output
