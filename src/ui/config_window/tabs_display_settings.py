"""Tab builders for the "Index cards" and "Parametrage" configuration tabs.

Extracted from :mod:`src.ui.config_window.tabs` to keep that module under
the repository's line-count budget; both functions are re-exported from
``tabs`` so existing call sites keep working unchanged.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING

from src.ui import theme
from src.ui.config_window.widgets import config_spinbox_row

if TYPE_CHECKING:
    from src.ui.application import Application


def build_index_cards_tab(app: Application, parent: ttk.Frame, edit_vars: dict[str, tk.Variable]) -> None:
    ttk.Label(
        parent,
        text=app._t("configuration_index_cards_title"),
        style=theme.SECTION_LABEL,
    ).pack(anchor="w", pady=(0, theme.SPACE_XS))
    ttk.Label(
        parent,
        text=app._t("configuration_index_cards_description"),
        wraplength=640,
        justify="left",
        style=theme.MUTED_LABEL,
    ).pack(anchor="w", pady=(0, theme.SPACE_MD))

    groups: list[tuple[str, list[tuple[str, str]]]] = [
        (
            "configuration_index_cards_section_description",
            [
                ("show_card_custom_objects", "configuration_card_custom_objects"),
                ("show_card_custom_fields", "configuration_card_custom_fields"),
                ("show_card_flows", "configuration_card_flows"),
                ("show_card_apex_classes_triggers", "configuration_card_apex_classes_triggers"),
                ("show_card_omni_components", "configuration_card_omni_components"),
                ("show_card_einstein_predictions", "configuration_card_einstein_predictions"),
                ("show_card_agents", "configuration_card_agents"),
                ("show_card_gen_ai_prompts", "configuration_card_gen_ai_prompts"),
                ("show_card_sharing_rules", "configuration_card_sharing_rules"),
                ("show_card_duplicate_rules", "configuration_card_duplicate_rules"),
                ("show_card_lwc", "configuration_card_lwc"),
                ("show_card_aura", "configuration_card_aura"),
                ("show_card_picklists", "configuration_card_picklists"),
            ],
        ),
        (
            "configuration_index_cards_section_scoring",
            [
                ("show_card_customization_level", "configuration_card_customization_level"),
                ("show_card_score", "configuration_card_score"),
                ("show_card_adopt_vs_adapt", "configuration_card_adopt_vs_adapt"),
                ("show_card_adopt_adapt_score", "configuration_card_adopt_adapt_score"),
                ("show_card_test_coverage", "configuration_card_test_coverage"),
            ],
        ),
        (
            "configuration_index_cards_section_metrics",
            [
                ("show_card_findings", "configuration_card_findings"),
                ("show_card_ai_usage", "configuration_card_ai_usage"),
                ("show_card_data_model_footprint", "configuration_card_data_model_footprint"),
                ("show_card_adopt_adapt_posture", "configuration_card_adopt_adapt_posture"),
                ("show_card_debt", "configuration_card_debt"),
                ("show_card_innovation", "configuration_card_innovation"),
                ("show_card_dependencies", "configuration_card_dependencies"),
            ],
        ),
        (
            "configuration_index_cards_section_ia",
            [
                ("show_card_einstein_predictions", "configuration_card_einstein_predictions"),
                ("show_card_agents", "configuration_card_agents"),
                ("show_card_gen_ai_prompts", "configuration_card_gen_ai_prompts"),
                ("show_card_ai_usage", "configuration_card_ai_usage"),
            ],
        ),
    ]

    for section_key, toggles in groups:
        container = ttk.LabelFrame(
            parent,
            text=app._t(section_key),
            padding=theme.SPACE_MD,
        )
        container.pack(fill="x", pady=(0, theme.SPACE_SM))
        for var_key, label_key in toggles:
            ttk.Checkbutton(
                container,
                text=app._t(label_key),
                variable=edit_vars[var_key],
            ).pack(anchor="w", pady=(2, 2))


def build_parametrage_tab(app: Application, parent: ttk.Frame, edit_vars: dict[str, tk.Variable]) -> None:
    ttk.Label(
        parent,
        text=app._t("configuration_parametrage_title"),
        style=theme.SECTION_LABEL,
    ).pack(anchor="w", pady=(0, theme.SPACE_XS))
    ttk.Label(
        parent,
        text=app._t("configuration_parametrage_description"),
        wraplength=640,
        justify="left",
        style=theme.MUTED_LABEL,
    ).pack(anchor="w", pady=(0, theme.SPACE_MD))

    one_page = ttk.LabelFrame(
        parent, text=app._t("configuration_parametrage_one_page_section"), padding=theme.SPACE_MD
    )
    one_page.pack(fill="x", pady=(0, theme.SPACE_SM))

    config_spinbox_row(
        one_page,
        app._t("configuration_parametrage_max_depth"),
        edit_vars["one_page_max_depth"],
        from_=1,
        to=6,
    )
    ttk.Label(
        one_page,
        text=app._t("configuration_parametrage_max_depth_hint"),
        wraplength=620,
        justify="left",
        style=theme.MUTED_LABEL,
    ).pack(anchor="w", pady=(0, theme.SPACE_SM))

    config_spinbox_row(
        one_page,
        app._t("configuration_parametrage_hub_threshold"),
        edit_vars["one_page_hub_threshold"],
        from_=2,
        to=100,
    )
    ttk.Label(
        one_page,
        text=app._t("configuration_parametrage_hub_threshold_hint"),
        wraplength=620,
        justify="left",
        style=theme.MUTED_LABEL,
    ).pack(anchor="w", pady=(0, 2))
