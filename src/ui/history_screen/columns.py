"""Treeview column configuration and row builders for the history screen.

Pure data helpers extracted from
:func:`src.ui.history_screen.screen.show_history_screen`: the entries
Treeview column definitions (label + width per column id) and the row
values tuple inserted for each :class:`~src.core.history_service.HistoryEntry`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.core.history_service import HistoryEntry

if TYPE_CHECKING:
    from src.ui.application import Application


def build_entry_columns_config(app: "Application") -> dict[str, tuple[str, int]]:
    """Return the ``{column_id: (label, width)}`` mapping for the entries tree."""

    return {
        "num": ("#", 40),
        "timestamp": (app._t("history_col_date"), 130),
        "score": (app._t("scoring_overall_score"), 60),
        "adopt_adapt": (app._t("adopt_adapt_overall_score"), 80),
        "coverage_apex": ("Couverture Apex", 90),
        "coverage_flows": ("Couverture Flows", 90),
        "objects": (app._t("scoring_component_custom_objects"), 70),
        "fields": (app._t("scoring_component_custom_fields"), 70),
        "flows": (app._t("scoring_component_flows"), 60),
        "apex": (app._t("configuration_card_apex_classes_triggers"), 80),
        "apex_triggers": (app._t("history_col_apex_triggers"), 70),
        "apex_test_classes": (app._t("history_col_apex_test_classes"), 90),
        "apex_business_classes": (app._t("history_col_apex_business_classes"), 90),
        "lwc": ("LWC", 60),
        "aura": ("Aura", 60),
        "omni": (app._t("configuration_card_omni_components"), 80),
        "sharing_rules": ("Sharing Rules", 80),
        "duplicate_rules": ("Duplicate Rules", 90),
        "findings": (app._t("configuration_card_findings"), 70),
        "crit": (app._t("configuration_rules_severity_critical"), 50),
        "maj": (app._t("configuration_rules_severity_major"), 50),
        "min": (app._t("configuration_rules_severity_minor"), 50),
        "inf": (app._t("configuration_rules_severity_info"), 50),
        "ai": (app._t("configuration_card_ai_usage"), 60),
        "dm_custom": (app._t("history_col_dm_custom"), 80),
        "dm_standard": (app._t("history_col_dm_standard"), 80),
        "adoption": (app._t("history_col_adoption"), 80),
        "adaptation": (app._t("history_col_adaptation"), 80),
        "comment": ("Commentaire", 160),
    }


def build_entry_row_values(e: HistoryEntry) -> tuple:
    """Return the Treeview row values tuple (including the hidden id) for ``e``."""

    return (
        e.generation_number,
        e.timestamp,
        e.score,
        e.adopt_adapt_score,
        f"{e.test_coverage_apex:.1f}%" if e.test_coverage_apex is not None else "N/A",
        f"{e.test_coverage_flows:.1f}%" if e.test_coverage_flows is not None else "N/A",
        e.custom_objects,
        e.custom_fields,
        e.flows,
        e.apex_classes_triggers,
        e.apex_triggers,
        e.apex_test_classes,
        e.apex_business_classes,
        e.lwc_count,
        e.aura_count,
        e.omni_components,
        e.sharing_rules,
        e.duplicate_rules,
        e.findings_total,
        e.findings_critical,
        e.findings_major,
        e.findings_minor,
        e.findings_info,
        f"{e.ai_usage_pct:.1f}%",
        f"{e.data_model_custom_pct:.1f}%",
        f"{e.data_model_standard_pct:.1f}%",
        f"{e.adoption_pct:.1f}%",
        f"{e.adaptation_pct:.1f}%",
        (e.comment[:45] + "…") if len(e.comment) > 45 else e.comment,
        e.id,
    )
