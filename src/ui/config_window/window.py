"""Top-level configuration window assembly."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING

from src.ui import (
    ai_tags_panel,
    analyzer_rules_panel,
    posture_capability_panel,
)
from src.ui.config_window.apply import apply_configuration_changes
from src.ui.config_window.tabs import (
    build_discussion_tab,
    build_documentation_tab,
    build_index_cards_tab,
    build_parametrage_tab,
)

if TYPE_CHECKING:
    from src.ui.application import Application


def show_configuration_screen(app: Application) -> None:
    """Create and show the configuration management window."""
    existing = app.configuration_window
    if existing is not None and existing.winfo_exists():
        existing.deiconify()
        existing.lift()
        existing.focus_set()
        return

    window = tk.Toplevel(app)
    window.title(app._t("configuration_title"))
    window.geometry("980x720")
    app._configure_secondary_window(window)

    # Add scrollbar support
    container = ttk.Frame(window)
    container.pack(fill="both", expand=True)

    canvas = tk.Canvas(container, highlightthickness=0)
    scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
    scrollable_frame = ttk.Frame(canvas, padding=16)

    scrollable_frame.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
    )

    canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)

    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    # Mouse wheel support
    def _on_mousewheel(event):
        canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    canvas.bind_all("<MouseWheel>", _on_mousewheel)

    ttk.Label(
        scrollable_frame,
        text=app._t("configuration_title"),
        font=("Segoe UI", 13, "bold"),
    ).pack(anchor="w", pady=(0, 8))

    notebook = ttk.Notebook(scrollable_frame)
    notebook.pack(fill="both", expand=True)

    doc_tab = ttk.Frame(notebook, padding=12)
    discussion_tab = ttk.Frame(notebook, padding=12)
    rules_tab = ttk.Frame(notebook, padding=12)
    ai_tags_tab = ttk.Frame(notebook, padding=12)
    index_cards_tab = ttk.Frame(notebook, padding=12)
    posture_tab = ttk.Frame(notebook, padding=12)
    parametrage_tab = ttk.Frame(notebook, padding=12)
    notebook.add(doc_tab, text=app._t("configuration_tab_documentation"))
    notebook.add(discussion_tab, text=app._t("configuration_tab_discussion"))
    notebook.add(rules_tab, text=app._t("configuration_tab_rules"))
    notebook.add(ai_tags_tab, text=app._t("configuration_tab_ai_tags"))
    notebook.add(index_cards_tab, text=app._t("configuration_tab_index_cards"))
    notebook.add(posture_tab, text=app._t("configuration_tab_posture"))
    notebook.add(parametrage_tab, text=app._t("configuration_tab_parametrage"))

    edit_vars = {
        "language": tk.StringVar(value=app._language_display(app.language)),
        "login_target": tk.StringVar(value=app._login_target_display(app.login_target_key)),
        "instance_url": tk.StringVar(value=app.instance_url_var.get()),
        "alias": tk.StringVar(value=app.alias_var.get()),
        "source": tk.StringVar(value=app.source_var.get()),
        "output": tk.StringVar(value=app.output_var.get()),
        "exclusion_file": tk.StringVar(value=app.exclusion_file_var.get()),
        "technical_debt_file": tk.StringVar(value=app.technical_debt_file_var.get()),
        "pmd_enabled": tk.BooleanVar(value=bool(app.pmd_enabled_var.get())),
        "pmd_ruleset": tk.StringVar(value=app.pmd_ruleset_var.get()),
        "analyzer_rules_file": tk.StringVar(value=app.analyzer_rules_file_var.get()),
        "org_check_type": tk.StringVar(value=app.org_check_choice_var.get()),
        "ai_provider": tk.StringVar(value=app.ai_provider_var.get()),
        "claude_key": tk.StringVar(value=app.claude_api_key_var.get()),
        "gemini_key": tk.StringVar(value=app.gemini_api_key_var.get()),
        "gateway_key": tk.StringVar(value=app.gateway_api_key_var.get()),
        "gateway_cert": tk.StringVar(value=app.gateway_cert_path_var.get()),
        "claude_model": tk.StringVar(value=app.claude_model_var.get()),
        "gemini_model": tk.StringVar(value=app.gemini_model_var.get()),
        "gateway_model": tk.StringVar(value=app.gateway_model_var.get()),
        "generate_excels": tk.BooleanVar(value=bool(app.generate_excels_var.get())),
        "generate_org_check_reports": tk.BooleanVar(
            value=bool(app.generate_org_check_reports_var.get())
        ),
        "generate_data_dictionary_word": tk.BooleanVar(
            value=bool(app.generate_data_dictionary_word_var.get())
        ),
        "generate_summary_word": tk.BooleanVar(
            value=bool(app.generate_summary_word_var.get())
        ),
        "generate_audit_summary_rtf": tk.BooleanVar(
            value=bool(app.generate_audit_summary_rtf_var.get())
        ),
        "generate_html": tk.BooleanVar(
            value=bool(app.generate_html_var.get())
        ),
        "run_tests": tk.BooleanVar(value=bool(app.run_tests_var.get())),
        "calculate_coverage": tk.BooleanVar(value=bool(app.calculate_coverage_var.get())),
        "show_card_customization_level": tk.BooleanVar(
            value=bool(app.show_card_customization_level_var.get())
        ),
        "show_card_score": tk.BooleanVar(
            value=bool(app.show_card_score_var.get())
        ),
        "show_card_adopt_vs_adapt": tk.BooleanVar(
            value=bool(app.show_card_adopt_vs_adapt_var.get())
        ),
        "show_card_adopt_adapt_score": tk.BooleanVar(
            value=bool(app.show_card_adopt_adapt_score_var.get())
        ),
        "show_card_custom_objects": tk.BooleanVar(
            value=bool(app.show_card_custom_objects_var.get())
        ),
        "show_card_custom_fields": tk.BooleanVar(
            value=bool(app.show_card_custom_fields_var.get())
        ),
        "show_card_flows": tk.BooleanVar(
            value=bool(app.show_card_flows_var.get())
        ),
        "show_card_apex_classes_triggers": tk.BooleanVar(
            value=bool(app.show_card_apex_classes_triggers_var.get())
        ),
        "show_card_omni_components": tk.BooleanVar(
            value=bool(app.show_card_omni_components_var.get())
        ),
        "show_card_findings": tk.BooleanVar(
            value=bool(app.show_card_findings_var.get())
        ),
        "show_card_ai_usage": tk.BooleanVar(
            value=bool(app.show_card_ai_usage_var.get())
        ),
        "show_card_data_model_footprint": tk.BooleanVar(
            value=bool(app.show_card_data_model_footprint_var.get())
        ),
        "show_card_adopt_adapt_posture": tk.BooleanVar(
            value=bool(app.show_card_adopt_adapt_posture_var.get())
        ),
        "show_card_agents": tk.BooleanVar(
            value=bool(app.show_card_agents_var.get())
        ),
        "show_card_gen_ai_prompts": tk.BooleanVar(
            value=bool(app.show_card_gen_ai_prompts_var.get())
        ),
        "show_card_einstein_predictions": tk.BooleanVar(
            value=bool(app.show_card_einstein_predictions_var.get())
        ),
        "show_card_test_coverage": tk.BooleanVar(
            value=bool(app.show_card_test_coverage_var.get())
        ),
        "show_card_debt": tk.BooleanVar(
            value=bool(app.show_card_debt_var.get())
        ),
        "show_card_innovation": tk.BooleanVar(
            value=bool(app.show_card_innovation_var.get())
        ),
        "show_card_sharing_rules": tk.BooleanVar(
            value=bool(app.show_card_sharing_rules_var.get())
        ),
        "show_card_duplicate_rules": tk.BooleanVar(
            value=bool(app.show_card_duplicate_rules_var.get())
        ),
        "show_card_lwc": tk.BooleanVar(
            value=bool(app.show_card_lwc_var.get())
        ),
        "show_card_aura": tk.BooleanVar(
            value=bool(app.show_card_aura_var.get())
        ),
        "show_card_dependencies": tk.BooleanVar(
            value=bool(app.show_card_dependencies_var.get())
        ),
        "one_page_max_depth": tk.IntVar(value=int(app.one_page_max_depth_var.get())),
        "one_page_hub_threshold": tk.IntVar(
            value=int(app.one_page_hub_threshold_var.get())
        ),
    }

    build_documentation_tab(app, doc_tab, edit_vars)
    build_discussion_tab(app, discussion_tab, edit_vars)
    analyzer_rules_panel.build_panel(app, rules_tab)
    ai_tags_panel.build_panel(app, ai_tags_tab)
    build_index_cards_tab(app, index_cards_tab, edit_vars)
    posture_capability_panel.build_panel(app, posture_tab)
    build_parametrage_tab(app, parametrage_tab, edit_vars)

    buttons_row = ttk.Frame(scrollable_frame)
    buttons_row.pack(fill="x", pady=(12, 0))
    ttk.Button(
        buttons_row,
        text=app._t("configuration_cancel"),
        command=window.destroy,
    ).pack(side="right")
    ttk.Button(
        buttons_row,
        text=app._t("configuration_save"),
        command=lambda: apply_configuration_changes(app, edit_vars, window),
    ).pack(side="right", padx=(0, 8))

    app.configuration_window = window
    window.focus_set()
