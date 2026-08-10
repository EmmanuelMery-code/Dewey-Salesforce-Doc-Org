"""CSV row/header builders for the history screen alias export.

Pure formatting helpers extracted from
:func:`src.ui.history_screen.screen.show_history_screen` so the export
logic (translated header row, per-entry data row) can be reused and tested
without pulling in the whole Tkinter window.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.core.history_service import HistoryEntry

if TYPE_CHECKING:
    from src.ui.application import Application


def build_csv_header_row(app: "Application") -> list[str]:
    """Return the translated header row for the alias CSV export."""

    return [
        "#", app._t("history_col_date"), app._t("scoring_overall_score"),
        app._t("adopt_adapt_overall_score"), "Couverture Apex", "Couverture Flows",
        app._t("scoring_component_custom_objects"),
        app._t("scoring_component_custom_fields"), app._t("scoring_component_flows"),
        app._t("configuration_card_apex_classes_triggers"),
        app._t("history_col_apex_triggers"),
        app._t("history_col_apex_test_classes"),
        app._t("history_col_apex_business_classes"),
        "LWC", "Aura", app._t("configuration_card_omni_components"),
        "Sharing Rules", "Duplicate Rules",
        app._t("configuration_card_findings"),
        app._t("configuration_rules_severity_critical"),
        app._t("configuration_rules_severity_major"),
        app._t("configuration_rules_severity_minor"),
        app._t("configuration_rules_severity_info"),
        app._t("configuration_card_ai_usage"),
        app._t("history_col_dm_custom"), app._t("history_col_dm_standard"),
        app._t("history_col_adoption"), app._t("history_col_adaptation"),
        "Commentaire",
    ]


def build_csv_data_row(e: HistoryEntry) -> list:
    """Return a single formatted CSV row for one history entry."""

    return [
        e.generation_number, e.timestamp, e.score, e.adopt_adapt_score,
        f"{e.test_coverage_apex:.1f}%" if e.test_coverage_apex is not None else "N/A",
        f"{e.test_coverage_flows:.1f}%" if e.test_coverage_flows is not None else "N/A",
        e.custom_objects, e.custom_fields, e.flows, e.apex_classes_triggers,
        e.apex_triggers, e.apex_test_classes, e.apex_business_classes,
        e.lwc_count, e.aura_count,
        e.omni_components, e.sharing_rules, e.duplicate_rules, e.findings_total,
        e.findings_critical, e.findings_major, e.findings_minor, e.findings_info,
        f"{e.ai_usage_pct:.1f}%",
        f"{e.data_model_custom_pct:.1f}%", f"{e.data_model_standard_pct:.1f}%",
        f"{e.adoption_pct:.1f}%", f"{e.adaptation_pct:.1f}%",
        e.comment,
    ]
