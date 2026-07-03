"""Persist the configuration window edits back onto the application."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from typing import TYPE_CHECKING

from src.ai import build_system_prompt
from src.ui import (
    ai_tags_panel,
    analyzer_rules_panel,
    posture_capability_panel,
)
from src.ui.settings import DEFAULT_AI_USAGE_TAGS

if TYPE_CHECKING:
    from src.ui.application import Application


def _canonical_comparison_target(display: str) -> str:
    """Convert a combo display string to a stored value ("auto" or a number).

    Accepts both display labels ("#16 — 2026-... — retrieve") and already
    canonical values ("auto", "16").
    """
    text = (display or "").strip()
    if text.startswith("#"):
        text = text[1:]
    token = text.split()[0] if text.split() else ""
    return token if token.isdigit() else "auto"


def apply_configuration_changes(app: Application, edit_vars: dict[str, tk.Variable], window: tk.Toplevel) -> None:
    new_language = app._language_code_from_display(edit_vars["language"].get())
    language_changed = new_language != app.language
    app.language = new_language

    new_login_target = app._login_target_key_from_display(edit_vars["login_target"].get())
    app.login_target_key = new_login_target

    app.instance_url_var.set(edit_vars["instance_url"].get().strip())
    app.alias_var.set(edit_vars["alias"].get().strip())
    app.source_var.set(edit_vars["source"].get().strip())
    app.output_var.set(edit_vars["output"].get().strip())
    app.exclusion_file_var.set(edit_vars["exclusion_file"].get().strip())
    app.technical_debt_file_var.set(edit_vars["technical_debt_file"].get().strip())
    app.pmd_enabled_var.set(bool(edit_vars["pmd_enabled"].get()))
    app.pmd_ruleset_var.set(edit_vars["pmd_ruleset"].get().strip())
    app.analyzer_rules_file_var.set(edit_vars["analyzer_rules_file"].get().strip())
    app._analyzer_rules_file = Path(edit_vars["analyzer_rules_file"].get().strip())

    org_check_choice = edit_vars["org_check_type"].get().strip()
    if org_check_choice:
        app.org_check_choice_var.set(org_check_choice)

    provider = edit_vars["ai_provider"].get().strip()
    if provider in app.AI_PROVIDERS:
        app.ai_provider_var.set(provider)

    app.claude_api_key_var.set(edit_vars["claude_key"].get())
    app.gemini_api_key_var.set(edit_vars["gemini_key"].get())
    app.gateway_api_key_var.set(edit_vars["gateway_key"].get())
    app.gateway_cert_path_var.set(edit_vars["gateway_cert"].get())

    claude_model_choice = edit_vars["claude_model"].get().strip()
    if claude_model_choice in app.claude_model_choices:
        app.claude_model_var.set(claude_model_choice)
    gemini_model_choice = edit_vars["gemini_model"].get().strip()
    if gemini_model_choice in app.gemini_model_choices:
        app.gemini_model_var.set(gemini_model_choice)
    gateway_model_choice = edit_vars["gateway_model"].get().strip()
    if gateway_model_choice in app.gateway_model_choices:
        app.gateway_model_var.set(gateway_model_choice)
    app.generate_excels_var.set(bool(edit_vars["generate_excels"].get()))
    app.generate_org_check_reports_var.set(
        bool(edit_vars["generate_org_check_reports"].get())
    )
    app.generate_data_dictionary_word_var.set(
        bool(edit_vars["generate_data_dictionary_word"].get())
    )
    app.generate_summary_word_var.set(
        bool(edit_vars["generate_summary_word"].get())
    )
    app.generate_audit_summary_rtf_var.set(
        bool(edit_vars["generate_audit_summary_rtf"].get())
    )
    app.generate_html_var.set(
        bool(edit_vars["generate_html"].get())
    )
    app.run_tests_var.set(bool(edit_vars["run_tests"].get()))
    app.calculate_coverage_var.set(bool(edit_vars["calculate_coverage"].get()))
    app.include_comparison_var.set(bool(edit_vars["include_comparison"].get()))
    app.comparison_target_var.set(
        _canonical_comparison_target(edit_vars["comparison_target"].get())
    )
    app.show_card_customization_level_var.set(
        bool(edit_vars["show_card_customization_level"].get())
    )
    app.show_card_score_var.set(
        bool(edit_vars["show_card_score"].get())
    )
    app.show_card_adopt_vs_adapt_var.set(
        bool(edit_vars["show_card_adopt_vs_adapt"].get())
    )
    app.show_card_adopt_adapt_score_var.set(
        bool(edit_vars["show_card_adopt_adapt_score"].get())
    )
    app.show_card_custom_objects_var.set(
        bool(edit_vars["show_card_custom_objects"].get())
    )
    app.show_card_custom_fields_var.set(
        bool(edit_vars["show_card_custom_fields"].get())
    )
    app.show_card_flows_var.set(
        bool(edit_vars["show_card_flows"].get())
    )
    app.show_card_apex_classes_triggers_var.set(
        bool(edit_vars["show_card_apex_classes_triggers"].get())
    )
    app.show_card_omni_components_var.set(
        bool(edit_vars["show_card_omni_components"].get())
    )
    app.show_card_findings_var.set(
        bool(edit_vars["show_card_findings"].get())
    )
    app.show_card_ai_usage_var.set(
        bool(edit_vars["show_card_ai_usage"].get())
    )
    app.show_card_data_model_footprint_var.set(
        bool(edit_vars["show_card_data_model_footprint"].get())
    )
    app.show_card_adopt_adapt_posture_var.set(
        bool(edit_vars["show_card_adopt_adapt_posture"].get())
    )
    app.show_card_agents_var.set(
        bool(edit_vars["show_card_agents"].get())
    )
    app.show_card_gen_ai_prompts_var.set(
        bool(edit_vars["show_card_gen_ai_prompts"].get())
    )
    app.show_card_einstein_predictions_var.set(
        bool(edit_vars["show_card_einstein_predictions"].get())
    )
    app.show_card_test_coverage_var.set(
        bool(edit_vars["show_card_test_coverage"].get())
    )
    app.show_card_debt_var.set(
        bool(edit_vars["show_card_debt"].get())
    )
    app.show_card_innovation_var.set(
        bool(edit_vars["show_card_innovation"].get())
    )
    app.show_card_sharing_rules_var.set(
        bool(edit_vars["show_card_sharing_rules"].get())
    )
    app.show_card_duplicate_rules_var.set(
        bool(edit_vars["show_card_duplicate_rules"].get())
    )
    app.show_card_lwc_var.set(
        bool(edit_vars["show_card_lwc"].get())
    )
    app.show_card_aura_var.set(
        bool(edit_vars["show_card_aura"].get())
    )
    app.show_card_dependencies_var.set(
        bool(edit_vars["show_card_dependencies"].get())
    )

    try:
        max_depth = int(edit_vars["one_page_max_depth"].get())
    except (tk.TclError, ValueError):
        max_depth = 3
    try:
        hub_threshold = int(edit_vars["one_page_hub_threshold"].get())
    except (tk.TclError, ValueError):
        hub_threshold = 8
    app.one_page_max_depth_var.set(max(1, min(6, max_depth)))
    app.one_page_hub_threshold_var.set(max(2, hub_threshold))

    if app._config_system_prompt_widget is not None:
        prompt_text = app._config_system_prompt_widget.get("1.0", "end").strip()
        app.system_prompt = prompt_text or build_system_prompt(app.language)
    app._config_system_prompt_widget = None

    analyzer_rules_panel.persist_changes(app)
    analyzer_rules_panel.reset_state(app)

    raw_tags = ai_tags_panel.collect_tags(app)
    cleaned_tags: list[str] = []
    seen_tags: set[str] = set()
    for value in raw_tags:
        text = value.strip()
        if not text:
            continue
        key = text.casefold()
        if key in seen_tags:
            continue
        seen_tags.add(key)
        cleaned_tags.append(text)
    app.ai_usage_tags = cleaned_tags or list(DEFAULT_AI_USAGE_TAGS)
    ai_tags_panel.reset_state(app)

    app.posture_config = posture_capability_panel.collect_config(app)
    posture_capability_panel.reset_state(app)

    app._save_settings()

    if language_changed:
        app._apply_language()
    else:
        app._apply_pmd_state()
        app._on_login_target_changed()

    app._append_log(app._t("configuration_saved"))
    window.destroy()
