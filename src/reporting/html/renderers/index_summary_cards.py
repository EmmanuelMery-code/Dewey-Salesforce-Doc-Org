"""Builds the summary card tabs (Description, Scoring, Metriques, IA) of index.html."""

from __future__ import annotations

from pathlib import Path

from src.core.ai_usage import AIUsageStats
from src.core.customization_metrics import AdoptionStats, DataModelCustomisationStats
from src.core.index_card_visibility import IndexCardVisibility
from src.core.models import MetadataSnapshot
from src.core.utils import html_value
from src.reporting.html.page_shell import href_relative
from src.reporting.html.renderers.index_cards import (
    render_adoption_card,
    render_ai_usage_card,
    render_data_model_card,
    render_debt_card,
    render_innovation_card,
    render_picklists_card,
    render_summary_tabs,
)


def render_index_summary_tabs(
    snapshot: MetadataSnapshot,
    current_path: Path,
    listing: dict[str, Path],
    visibility: IndexCardVisibility,
    analyzer_report,
    findings_report_page: Path | None,
    ai_usage_stats: AIUsageStats | None,
    ai_usage_page: Path | None,
    data_model_stats: DataModelCustomisationStats | None,
    customisation_page: Path | None,
    adoption_stats: AdoptionStats | None,
    adoption_page: Path | None,
    debt_page: Path | None,
    innovation_page: Path | None,
    picklists_page: Path | None,
) -> str:
    """Build the summary card tabs shown above the main tabbed section."""
    metrics = snapshot.metrics

    def _listing_link(key: str, title: str, count: int) -> str:
        """Wrap title in a link to the listing page when count > 0 and page exists."""
        page = listing.get(key)
        if count > 0 and page:
            return f"<a href='{href_relative(current_path, page)}' style='color:inherit;text-decoration:none;'>{title}</a>"
        return title

    omni_total = (
        metrics.omni_scripts
        + metrics.omni_integration_procedures
        + metrics.omni_ui_cards
        + metrics.omni_data_transforms
        + metrics.bre_decision_matrices
        + metrics.bre_expression_sets
    )
    findings_card = ""
    if analyzer_report is not None and visibility.show_findings:
        findings = analyzer_report.all_findings()
        findings_total = len(findings)
        
        counts = {"Critical": 0, "Major": 0, "Minor": 0, "Info": 0}
        for f in findings:
            counts[f.rule.severity] = counts.get(f.rule.severity, 0) + 1
            
        severity_html = (
            f'<div class="ai-usage-grid" style="margin-top: 10px;">'
            f'  <div class="ai-usage-stat sev-critical" style="background: #fef2f2; border-color: #fca5a5; padding: 4px 8px;">'
            f'    <span style="font-size: 0.7rem; color: #991b1b;">CRITIQUE</span>'
            f'    <span style="font-size: 1.1rem; font-weight: 700; color: #991b1b;">{counts["Critical"]}</span>'
            f'  </div>'
            f'  <div class="ai-usage-stat sev-major" style="background: #fff7ed; border-color: #fdba74; padding: 4px 8px;">'
            f'    <span style="font-size: 0.7rem; color: #9a3412;">MAJEUR</span>'
            f'    <span style="font-size: 1.1rem; font-weight: 700; color: #9a3412;">{counts["Major"]}</span>'
            f'  </div>'
            f'  <div class="ai-usage-stat sev-minor" style="background: #fefce8; border-color: #facc15; padding: 4px 8px;">'
            f'    <span style="font-size: 0.7rem; color: #854d0e;">MINEUR</span>'
            f'    <span style="font-size: 1.1rem; font-weight: 700; color: #854d0e;">{counts["Minor"]}</span>'
            f'  </div>'
            f'  <div class="ai-usage-stat sev-info" style="background: #eff6ff; border-color: #93c5fd; padding: 4px 8px;">'
            f'    <span style="font-size: 0.7rem; color: #1e3a8a;">INFO</span>'
            f'    <span style="font-size: 1.1rem; font-weight: 700; color: #1e3a8a;">{counts["Info"]}</span>'
            f'  </div>'
            f'</div>'
        )

        if findings_report_page is not None:
            href = html_value(href_relative(current_path, findings_report_page))
            title_html = f'<a href="{href}">Findings analyseur</a>'
        else:
            title_html = 'Findings analyseur'

        findings_card = (
            f'  <div class="card" style="min-width: 320px;">'
            f'    <span>{title_html}</span>'
            f'    <span class="value">{findings_total}</span>'
            f'    {severity_html}'
            f'  </div>\n'
        )

    ai_usage_card = (
        render_ai_usage_card(ai_usage_stats, ai_usage_page, current_path)
        if visibility.show_ai_usage
        else ""
    )
    data_model_card = (
        render_data_model_card(data_model_stats, customisation_page, current_path)
        if visibility.show_data_model_footprint
        else ""
    )
    adoption_card = (
        render_adoption_card(adoption_stats, adoption_page, current_path)
        if visibility.show_adopt_adapt_posture
        else ""
    )
    debt_card = (
        render_debt_card(snapshot, debt_page, current_path)
        if visibility.show_debt
        else ""
    )
    innovation_card = (
        render_innovation_card(snapshot, innovation_page, current_path)
        if visibility.show_innovation
        else ""
    )
    picklists_card = (
        render_picklists_card(snapshot, picklists_page, current_path)
        if visibility.show_picklists
        else ""
    )
    
    # Calculate Apex and Flow coverage averages
    apex_covered = 0
    apex_to_cover = 0
    for artifact in snapshot.apex_artifacts:
        if not artifact.is_test and artifact.test_coverage is not None:
            apex_covered += artifact.test_coverage_lines_covered
            apex_to_cover += artifact.test_coverage_lines_covered + artifact.test_coverage_lines_uncovered
    apex_coverage_avg = (apex_covered / apex_to_cover * 100) if apex_to_cover > 0 else None
    
    flow_covered = 0
    flow_to_cover = 0
    for flow in snapshot.flows:
        if flow.test_coverage is not None:
            flow_covered += flow.test_coverage_elements_covered
            flow_to_cover += flow.test_coverage_elements_covered + flow.test_coverage_elements_uncovered
    flow_coverage_avg = (flow_covered / flow_to_cover * 100) if flow_to_cover > 0 else None
    
    # Build coverage detail string - show only Apex and Flows, no org average
    apex_str = f"Apex: {apex_coverage_avg:.1f}%" if apex_coverage_avg is not None else "Apex: N/A"
    flow_str = f"Flow: {flow_coverage_avg:.1f}%" if flow_coverage_avg is not None else "Flow: N/A"
    coverage_details = f"{apex_str} | {flow_str}"
    
    test_coverage_card = (
        f'  <div class="card"><span>Couverture de tests</span>'
        f'<span class="value">{coverage_details}</span>'
        f'<small style="color: #64748b; font-weight: normal;">Par type (Apex + Flows)</small></div>\n'
        if visibility.show_test_coverage
        else ""
    )

    customization_level_card = (
        f'  <div class="card"><span>Niveau de customisation</span>'
        f'<span class="value">{html_value(metrics.level)}</span></div>\n'
        if visibility.show_customization_level
        else ""
    )
    score_card = (
        f'  <div class="card"><span>Score</span>'
        f'<span class="value">{metrics.score}</span>'
        f'<div style="display: flex; gap: 8px; margin-top: 4px; font-size: 0.75rem; color: #64748b;">'
        f'<span>No: {metrics.custom_objects * metrics._weight("custom_objects") + metrics.custom_fields * metrics._weight("custom_fields") + metrics.record_types * metrics._weight("record_types") + metrics.validation_rules * metrics._weight("validation_rules") + metrics.layouts * metrics._weight("layouts") + metrics.custom_tabs * metrics._weight("custom_tabs") + metrics.custom_apps * metrics._weight("custom_apps") + metrics.einstein_predictions * metrics._weight("einstein_predictions")}</span>'
        f'<span>Low: {metrics.flows * metrics._weight("flows") + metrics.omni_scripts * metrics._weight("omni_scripts") + metrics.omni_integration_procedures * metrics._weight("omni_integration_procedures") + metrics.omni_ui_cards * metrics._weight("omni_ui_cards") + metrics.omni_data_transforms * metrics._weight("omni_data_transforms") + metrics.bre_decision_matrices * metrics._weight("bre_decision_matrices") + metrics.bre_expression_sets * metrics._weight("bre_expression_sets") + metrics.gen_ai_prompts * metrics._weight("gen_ai_prompts")}</span>'
        f'<span>Pro: {metrics.apex_classes * metrics._weight("apex_classes") + metrics.apex_triggers * metrics._weight("apex_triggers") + metrics.agents * metrics._weight("agents")}</span>'
        f'</div></div>\n'
        if visibility.show_score
        else ""
    )
    adopt_vs_adapt_card = (
        f'  <div class="card"><span>Adopt vs Adapt</span>'
        f'<span class="value">{html_value(metrics.adopt_adapt_level)}</span></div>\n'
        if visibility.show_adopt_vs_adapt
        else ""
    )
    adopt_adapt_score_card = (
        f'  <div class="card"><span>Score Adopt vs Adapt</span>'
        f'<span class="value">{metrics.adopt_adapt_score}</span>'
        f'<div style="display: flex; gap: 8px; margin-top: 4px; font-size: 0.75rem; color: #64748b;">'
        f'<span>No: {metrics.custom_objects * metrics._aa_weight("custom_objects") + metrics.custom_fields * metrics._aa_weight("custom_fields") + metrics.einstein_predictions * metrics._aa_weight("einstein_predictions")}</span>'
        f'<span>Low: {metrics.flows * metrics._aa_weight("flows") + metrics.lwc_count * metrics._aa_weight("lwc") + metrics.flexipage_count * metrics._aa_weight("flexipages") + metrics.omni_scripts * metrics._aa_weight("omni_scripts") + metrics.omni_integration_procedures * metrics._aa_weight("omni_integration_procedures") + metrics.omni_ui_cards * metrics._aa_weight("omni_ui_cards") + metrics.omni_data_transforms * metrics._aa_weight("omni_data_transforms") + metrics.bre_decision_matrices * metrics._aa_weight("bre_decision_matrices") + metrics.bre_expression_sets * metrics._aa_weight("bre_expression_sets") + metrics.gen_ai_prompts * metrics._aa_weight("gen_ai_prompts")}</span>'
        f'<span>Pro: {metrics.apex_classes * metrics._aa_weight("apex_classes") + metrics.agents * metrics._aa_weight("agents")}</span>'
        f'</div></div>\n'
        if visibility.show_adopt_adapt_score
        else ""
    )
    custom_objects_card = (
        f'  <div class="card"><span>{_listing_link("objects", "Objets custom", metrics.custom_objects)} <small style="color: #64748b; font-weight: normal;">(No-code)</small></span>'
        f'<span class="value">{metrics.custom_objects}</span></div>\n'
        if visibility.show_custom_objects
        else ""
    )
    custom_fields_card = (
        f'  <div class="card"><span>{_listing_link("fields", "Champs custom", metrics.custom_fields)} <small style="color: #64748b; font-weight: normal;">(No-code)</small></span>'
        f'<span class="value">{metrics.custom_fields}</span></div>\n'
        if visibility.show_custom_fields
        else ""
    )
    flows_card = (
        f'  <div class="card"><span>{_listing_link("flows", "Flows", metrics.flows)} <small style="color: #64748b; font-weight: normal;">(Low-code)</small></span>'
        f'<span class="value">{metrics.flows}</span></div>\n'
        if visibility.show_flows
        else ""
    )
    apex_classes_triggers_card = (
        f'  <div class="card"><span>{_listing_link("apex", "Classes / Triggers", metrics.apex_classes + metrics.apex_triggers)} <small style="color: #64748b; font-weight: normal;">(Pro-code)</small></span>'
        f'<span class="value">{metrics.apex_classes + metrics.apex_triggers}</span></div>\n'
        if visibility.show_apex_classes_triggers
        else ""
    )
    omni_components_card = (
        f'  <div class="card"><span>{_listing_link("omni", "Composants Omni", omni_total)} <small style="color: #64748b; font-weight: normal;">(Low-code)</small></span>'
        f'<span class="value">{omni_total}</span></div>\n'
        if visibility.show_omni_components
        else ""
    )
    predictions_card = (
        f'  <div class="card"><span>Einstein Predictions <small style="color: #64748b; font-weight: normal;">(No-code)</small></span>'
        f'<span class="value">{metrics.einstein_predictions}</span></div>\n'
        if visibility.show_einstein_predictions
        else ""
    )
    agents_card = (
        f'  <div class="card"><span>{_listing_link("agents", "Agents", metrics.agents)} <small style="color: #64748b; font-weight: normal;">(Pro-code)</small></span>'
        f'<span class="value">{metrics.agents}</span></div>\n'
        if visibility.show_agents
        else ""
    )
    prompts_card = (
        f'  <div class="card"><span>{_listing_link("prompts", "Prompts", metrics.gen_ai_prompts)} <small style="color: #64748b; font-weight: normal;">(Low-code)</small></span>'
        f'<span class="value">{metrics.gen_ai_prompts}</span></div>\n'
        if visibility.show_gen_ai_prompts
        else ""
    )
    lwc_card = (
        f'  <div class="card"><span>{_listing_link("lwc", "Composants LWC", metrics.lwc_count)} <small style="color: #64748b; font-weight: normal;">(Pro-code)</small></span>'
        f'<span class="value">{metrics.lwc_count}</span></div>\n'
        if metrics.lwc_count > 0
        else ""
    )
    aura_card = (
        f'  <div class="card"><span>{_listing_link("aura", "Composants Aura", len(snapshot.aura))} <small style="color: #64748b; font-weight: normal;">(Pro-code)</small></span>'
        f'<span class="value">{len(snapshot.aura)}</span></div>\n'
        if len(snapshot.aura) > 0
        else ""
    )
    duplicate_rules_card = (
        f'  <div class="card"><span>{_listing_link("duplicate_rules", "Duplicate Rules", metrics.duplicate_rules)} <small style="color: #64748b; font-weight: normal;">(No-code)</small></span>'
        f'<span class="value">{metrics.duplicate_rules}</span></div>\n'
        if metrics.duplicate_rules > 0
        else ""
    )
    sharing_rules_card = (
        f'  <div class="card"><span>{_listing_link("sharing_rules", "Sharing Rules", metrics.sharing_rules)} <small style="color: #64748b; font-weight: normal;">(No-code)</small></span>'
        f'<span class="value">{metrics.sharing_rules}</span></div>\n'
        if visibility.show_sharing_rules
        else ""
    )

    return render_summary_tabs(
        description_cards=[
            custom_objects_card, custom_fields_card, flows_card, apex_classes_triggers_card,
            lwc_card, aura_card, omni_components_card, predictions_card, agents_card,
            prompts_card, sharing_rules_card, duplicate_rules_card, picklists_card,
        ],
        scoring_cards=[
            customization_level_card, score_card, adopt_vs_adapt_card,
            adopt_adapt_score_card, test_coverage_card,
        ],
        metric_cards=[
            findings_card, ai_usage_card, data_model_card, adoption_card, debt_card,
            innovation_card,
        ],
        ia_business_cards=[predictions_card, agents_card, prompts_card],
        ia_admin_card=ai_usage_card,
    )
