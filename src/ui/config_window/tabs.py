"""Tab builders for the configuration window notebook."""

from __future__ import annotations

import tkinter as tk
from tkinter import scrolledtext, ttk
from typing import TYPE_CHECKING

from src.ai import build_system_prompt
from src.ui.config_window.widgets import (
    config_combo_row,
    config_entry_row,
    config_spinbox_row,
)

if TYPE_CHECKING:
    from src.ui.application import Application


def build_documentation_tab(app: Application, parent: ttk.Frame, edit_vars: dict[str, tk.Variable]) -> None:
    general = ttk.LabelFrame(parent, text=app._t("configuration_section_general"), padding=10)
    general.pack(fill="x", pady=(0, 8))
    config_combo_row(
        general,
        app._t("language"),
        edit_vars["language"],
        [app._language_display(code) for code in app.LANGUAGES],
    )

    salesforce = ttk.LabelFrame(parent, text=app._t("configuration_section_salesforce"), padding=10)
    salesforce.pack(fill="x", pady=(0, 8))
    config_entry_row(salesforce, app._t("alias"), edit_vars["alias"])
    config_combo_row(
        salesforce,
        app._t("environment"),
        edit_vars["login_target"],
        [app._login_target_display(key) for key in app.LOGIN_TARGETS],
    )
    config_entry_row(salesforce, app._t("instance_url"), edit_vars["instance_url"])

    paths = ttk.LabelFrame(parent, text=app._t("configuration_section_paths"), padding=10)
    paths.pack(fill="x", pady=(0, 8))
    config_entry_row(paths, app._t("source_folder"), edit_vars["source"])
    config_entry_row(paths, app._t("output_folder"), edit_vars["output"])
    config_entry_row(paths, app._t("exclusion_file"), edit_vars["exclusion_file"])
    config_entry_row(paths, app._t("technical_debt_file"), edit_vars["technical_debt_file"])

    analysis = ttk.LabelFrame(parent, text=app._t("configuration_section_analysis"), padding=10)
    analysis.pack(fill="x", pady=(0, 8))
    ttk.Checkbutton(
        analysis, text=app._t("pmd_enabled"), variable=edit_vars["pmd_enabled"]
    ).pack(anchor="w", pady=(0, 4))
    config_entry_row(analysis, app._t("pmd_ruleset_file"), edit_vars["pmd_ruleset"])
    config_entry_row(analysis, app._t("configuration_rules_file_label"), edit_vars["analyzer_rules_file"])
    config_combo_row(
        analysis,
        app._t("org_check_type"),
        edit_vars["org_check_type"],
        list(app.ORG_CHECK_CHOICES),
    )

    reports = ttk.LabelFrame(parent, text=app._t("configuration_section_reports"), padding=10)
    reports.pack(fill="x", pady=(0, 8))
    ttk.Checkbutton(
        reports,
        text=app._t("menu_generate_html"),
        variable=edit_vars["generate_html"],
    ).pack(anchor="w", pady=(2, 2))
    ttk.Checkbutton(
        reports,
        text=app._t("configuration_generate_excels"),
        variable=edit_vars["generate_excels"],
    ).pack(anchor="w", pady=(2, 2))
    ttk.Checkbutton(
        reports,
        text=app._t("configuration_generate_org_check_reports"),
        variable=edit_vars["generate_org_check_reports"],
    ).pack(anchor="w", pady=(2, 2))
    ttk.Checkbutton(
        reports,
        text=app._t("configuration_generate_data_dictionary_word"),
        variable=edit_vars["generate_data_dictionary_word"],
    ).pack(anchor="w", pady=(2, 2))
    ttk.Checkbutton(
        reports,
        text=app._t("configuration_generate_summary_word"),
        variable=edit_vars["generate_summary_word"],
    ).pack(anchor="w", pady=(2, 2))
    ttk.Checkbutton(
        reports,
        text=app._t("configuration_generate_audit_summary_rtf"),
        variable=edit_vars["generate_audit_summary_rtf"],
    ).pack(anchor="w", pady=(2, 2))

    tests = ttk.LabelFrame(parent, text=app._t("configuration_section_tests"), padding=10)
    tests.pack(fill="x", pady=(0, 8))
    ttk.Checkbutton(
        tests,
        text=app._t("configuration_run_tests"),
        variable=edit_vars["run_tests"],
    ).pack(anchor="w", pady=(2, 2))
    ttk.Checkbutton(
        tests,
        text=app._t("configuration_calculate_coverage"),
        variable=edit_vars["calculate_coverage"],
    ).pack(anchor="w", pady=(2, 2))


def build_model_management(
    app: Application,
    parent: ttk.Frame,
    model_var: tk.StringVar,
    choices_list: list[str],
    default_choices: list[str],
    provider_name: str,
) -> None:
    """Add Add/Remove/Reset buttons for AI models."""
    row = ttk.Frame(parent)
    row.pack(fill="x", pady=(2, 5))
    ttk.Label(row, text="", width=22).pack(side="left")

    def add_model():
        from tkinter import simpledialog, messagebox

        name = simpledialog.askstring(
            app._t("configuration_ai_models_add"),
            app._t("configuration_ai_models_prompt"),
            parent=parent,
        )
        if name and name.strip():
            name = name.strip()
            if name in choices_list:
                messagebox.showwarning(
                    app._t("configuration_ai_models_add"),
                    app._t("configuration_ai_models_duplicate"),
                )
                return
            choices_list.append(name)
            # Update the combobox if possible. This is tricky because the combobox
            # is created in config_combo_row which doesn't return the widget.
            # But we can find it by looking at children of parent.
            for child in parent.winfo_children():
                if isinstance(child, ttk.Frame):
                    for subchild in child.winfo_children():
                        if (
                            isinstance(subchild, ttk.Combobox)
                            and subchild.cget("textvariable") == str(model_var)
                        ):
                            subchild["values"] = list(choices_list)
                            break

    def remove_model():
        current = model_var.get()
        if current in choices_list:
            choices_list.remove(current)
            if choices_list:
                model_var.set(choices_list[0])
            else:
                model_var.set("")
            for child in parent.winfo_children():
                if isinstance(child, ttk.Frame):
                    for subchild in child.winfo_children():
                        if (
                            isinstance(subchild, ttk.Combobox)
                            and subchild.cget("textvariable") == str(model_var)
                        ):
                            subchild["values"] = list(choices_list)
                            break

    def reset_models():
        choices_list.clear()
        choices_list.extend(default_choices)
        if choices_list:
            model_var.set(choices_list[0])
        for child in parent.winfo_children():
            if isinstance(child, ttk.Frame):
                for subchild in child.winfo_children():
                    if (
                        isinstance(subchild, ttk.Combobox)
                        and subchild.cget("textvariable") == str(model_var)
                    ):
                        subchild["values"] = list(choices_list)
                        break

    ttk.Button(
        row, text=app._t("configuration_ai_models_add"), command=add_model
    ).pack(side="left", padx=(0, 5))
    ttk.Button(
        row, text=app._t("configuration_ai_models_remove"), command=remove_model
    ).pack(side="left", padx=(0, 5))
    ttk.Button(
        row, text=app._t("configuration_ai_models_reset"), command=reset_models
    ).pack(side="left")


def build_discussion_tab(app: Application, parent: ttk.Frame, edit_vars: dict[str, tk.Variable]) -> None:
    ai_frame = ttk.LabelFrame(parent, text=app._t("configuration_section_ai"), padding=10)
    ai_frame.pack(fill="x", pady=(0, 8))

    # Active provider selection
    provider_row = ttk.Frame(ai_frame)
    provider_row.pack(fill="x", pady=(0, 10))
    ttk.Label(provider_row, text=app._t("configuration_ai_provider"), width=22).pack(side="left")

    for p in app.AI_PROVIDERS:
        ttk.Radiobutton(
            provider_row,
            text=p,
            variable=edit_vars["ai_provider"],
            value=p
        ).pack(side="left", padx=10)

    # Claude (Anthropic)
    claude_frame = ttk.LabelFrame(ai_frame, text="Claude (Anthropic)", padding=10)
    claude_frame.pack(fill="x", pady=5)
    config_entry_row(
        claude_frame, app._t("configuration_claude_key"), edit_vars["claude_key"], show="*"
    )
    config_combo_row(
        claude_frame,
        app._t("configuration_claude_model"),
        edit_vars["claude_model"],
        list(app.claude_model_choices),
    )
    build_model_management(
        app,
        claude_frame,
        edit_vars["claude_model"],
        app.claude_model_choices,
        app.DEFAULT_CLAUDE_MODELS,
        "Claude",
    )

    # Gemini (Google)
    gemini_frame = ttk.LabelFrame(ai_frame, text="Gemini (Google)", padding=10)
    gemini_frame.pack(fill="x", pady=5)
    config_entry_row(
        gemini_frame, app._t("configuration_gemini_key"), edit_vars["gemini_key"], show="*"
    )
    config_combo_row(
        gemini_frame,
        app._t("configuration_gemini_model"),
        edit_vars["gemini_model"],
        list(app.gemini_model_choices),
    )
    build_model_management(
        app,
        gemini_frame,
        edit_vars["gemini_model"],
        app.gemini_model_choices,
        app.DEFAULT_GEMINI_MODELS,
        "Gemini",
    )

    # LLM Gateway (Salesforce)
    gateway_frame = ttk.LabelFrame(ai_frame, text="LLM Gateway (Salesforce)", padding=10)
    gateway_frame.pack(fill="x", pady=5)
    config_entry_row(
        gateway_frame, app._t("configuration_gateway_key"), edit_vars["gateway_key"], show="*"
    )
    config_combo_row(
        gateway_frame,
        app._t("configuration_gateway_model"),
        edit_vars["gateway_model"],
        list(app.gateway_model_choices),
    )
    build_model_management(
        app,
        gateway_frame,
        edit_vars["gateway_model"],
        app.gateway_model_choices,
        app.DEFAULT_GATEWAY_MODELS,
        "Gateway",
    )
    config_entry_row(
        gateway_frame, app._t("configuration_gateway_cert"), edit_vars["gateway_cert"]
    )

    ttk.Label(
        ai_frame,
        text=app._t("configuration_model_hint"),
        wraplength=640,
        justify="left",
        foreground="#475569",
    ).pack(anchor="w", pady=(6, 0))

    prompt_frame = ttk.LabelFrame(
        parent, text=app._t("configuration_section_prompt"), padding=10
    )
    prompt_frame.pack(fill="both", expand=True, pady=(0, 8))

    ttk.Label(
        prompt_frame,
        text=app._t("configuration_system_prompt_description"),
        wraplength=640,
        justify="left",
    ).pack(anchor="w", pady=(0, 6))

    prompt_widget = scrolledtext.ScrolledText(
        prompt_frame, wrap="word", height=10, font=("Segoe UI", 10)
    )
    prompt_widget.pack(fill="both", expand=True)
    prompt_widget.insert("1.0", app.system_prompt)
    app._config_system_prompt_widget = prompt_widget

    button_row = ttk.Frame(prompt_frame)
    button_row.pack(fill="x", pady=(6, 0))

    def reset_prompt():
        default_prompt = build_system_prompt(app.language)
        prompt_widget.delete("1.0", "end")
        prompt_widget.insert("1.0", default_prompt)

    ttk.Button(
        button_row,
        text=app._t("configuration_system_prompt_reset"),
        command=reset_prompt,
    ).pack(side="right")


def build_index_cards_tab(app: Application, parent: ttk.Frame, edit_vars: dict[str, tk.Variable]) -> None:
    ttk.Label(
        parent,
        text=app._t("configuration_index_cards_title"),
        font=("Segoe UI", 11, "bold"),
    ).pack(anchor="w", pady=(0, 4))
    ttk.Label(
        parent,
        text=app._t("configuration_index_cards_description"),
        wraplength=640,
        justify="left",
        foreground="#475569",
    ).pack(anchor="w", pady=(0, 10))

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
            padding=10,
        )
        container.pack(fill="x", pady=(0, 8))
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
        font=("Segoe UI", 11, "bold"),
    ).pack(anchor="w", pady=(0, 4))
    ttk.Label(
        parent,
        text=app._t("configuration_parametrage_description"),
        wraplength=640,
        justify="left",
        foreground="#475569",
    ).pack(anchor="w", pady=(0, 10))

    one_page = ttk.LabelFrame(
        parent, text=app._t("configuration_parametrage_one_page_section"), padding=10
    )
    one_page.pack(fill="x", pady=(0, 8))

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
        foreground="#475569",
    ).pack(anchor="w", pady=(0, 8))

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
        foreground="#475569",
    ).pack(anchor="w", pady=(0, 2))
