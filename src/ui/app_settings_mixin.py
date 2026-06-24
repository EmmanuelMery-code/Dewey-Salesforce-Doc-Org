"""Mixin — persistent settings for :class:`Application`.

Handles loading, validation and saving of ``app_settings.json`` as well
as path conversion helpers (relative ↔ absolute) and the
:class:`IndexCardVisibility` snapshot used by the HTML renderer.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from src.core.index_card_visibility import IndexCardVisibility
from src.core.models import (
    DEFAULT_ADOPT_ADAPT_THRESHOLDS,
    DEFAULT_SCORING_THRESHOLDS,
    DEFAULT_SCORING_WEIGHTS,
)
from src.ui.settings import (
    load_settings,
    parse_thresholds,
    parse_weights,
    save_settings,
    serialize_posture_config,
)


class AppSettingsMixin:
    """Load/save application settings and convert file paths."""

    # ------------------------------------------------------------------ load

    def _load_settings(self) -> dict[str, Any]:
        return load_settings(self.settings_path)

    def _load_scoring_weights(self, settings: dict[str, Any]) -> dict[str, int]:
        return parse_weights(settings, "scoring_weights", DEFAULT_SCORING_WEIGHTS)

    def _load_adopt_adapt_weights(self, settings: dict[str, Any]) -> dict[str, int]:
        from src.core.models import DEFAULT_ADOPT_ADAPT_WEIGHTS
        return parse_weights(settings, "adopt_adapt_weights", DEFAULT_ADOPT_ADAPT_WEIGHTS)

    def _load_scoring_thresholds(self, settings: dict[str, Any]) -> tuple[int, int, int]:
        return parse_thresholds(settings, "scoring_thresholds", DEFAULT_SCORING_THRESHOLDS)

    def _load_adopt_adapt_thresholds(self, settings: dict[str, Any]) -> tuple[int, int, int]:
        return parse_thresholds(settings, "adopt_adapt_thresholds", DEFAULT_ADOPT_ADAPT_THRESHOLDS)

    def _load_data_model_thresholds(self, settings: dict[str, Any]) -> tuple[int, int, int]:
        from src.core.models import DEFAULT_DATA_MODEL_THRESHOLDS
        return parse_thresholds(settings, "data_model_thresholds", DEFAULT_DATA_MODEL_THRESHOLDS)

    def _load_profiles_thresholds(self, settings: dict[str, Any]) -> tuple[int, int, int]:
        from src.core.models import DEFAULT_PROFILES_THRESHOLDS
        return parse_thresholds(settings, "profiles_thresholds", DEFAULT_PROFILES_THRESHOLDS)

    def _load_profiles_ps_ratio_thresholds(self, settings: dict[str, Any]) -> tuple[int, int, int]:
        from src.core.models import DEFAULT_PROFILES_PS_RATIO_THRESHOLDS
        return parse_thresholds(
            settings, "profiles_ps_ratio_thresholds", DEFAULT_PROFILES_PS_RATIO_THRESHOLDS
        )

    def _load_innovation_colors(self, settings: dict[str, Any]) -> dict[str, str]:
        defaults = {
            "positive": "#d4edda",
            "neutral": "#fff3cd",
            "negative": "#f8d7da"
        }
        return settings.get("innovation_colors", defaults)

    # ------------------------------------------------------------------ save

    def _save_settings(self) -> None:
        payload: dict[str, Any] = {
            "language": self.language,
            "login_target": self.login_target_key,
            "instance_url": self.instance_url_var.get().strip(),
            "last_selected_org": self.selected_org_var.get().strip(),
            "alias": self.alias_var.get().strip(),
            "source_folder": self._to_rel_path(self.source_var.get().strip()),
            "output_folder": self._to_rel_path(self.output_var.get().strip()),
            "exclusion_file": self._to_rel_path(self.exclusion_file_var.get().strip()),
            "technical_debt_file": self._to_rel_path(self.technical_debt_file_var.get().strip()),
            "innovation_file": self._to_rel_path(self.innovation_file_var.get().strip()),
            "pmd_enabled": bool(self.pmd_enabled_var.get()),
            "pmd_ruleset_file": self._to_rel_path(self.pmd_ruleset_var.get().strip()),
            "analyzer_rules_file": self._to_rel_path(
                self.analyzer_rules_file_var.get().strip()
            ),
            "org_check_type": self.org_check_choice_var.get().strip(),
            "ai_provider": self.ai_provider_var.get().strip() or self.AI_PROVIDERS[0],
            "claude_api_key": self.claude_api_key_var.get(),
            "gemini_api_key": self.gemini_api_key_var.get(),
            "gateway_api_key": self.gateway_api_key_var.get(),
            "gateway_cert_path": self._to_rel_path(self.gateway_cert_path_var.get()),
            "claude_model": self.claude_model_var.get().strip() or self.DEFAULT_CLAUDE_MODEL,
            "gemini_model": self.gemini_model_var.get().strip() or self.DEFAULT_GEMINI_MODEL,
            "gateway_model": self.gateway_model_var.get().strip() or self.DEFAULT_GATEWAY_MODEL,
            "gemini_models": self.gemini_model_choices,
            "claude_models": self.claude_model_choices,
            "gateway_models": self.gateway_model_choices,
            "system_prompt": self.system_prompt,
            "generate_excels": bool(self.generate_excels_var.get()),
            "generate_org_check_reports": bool(self.generate_org_check_reports_var.get()),
            "generate_data_dictionary_word": bool(self.generate_data_dictionary_word_var.get()),
            "generate_summary_word": bool(self.generate_summary_word_var.get()),
            "generate_audit_summary_rtf": bool(self.generate_audit_summary_rtf_var.get()),
            "generate_html": bool(self.generate_html_var.get()),
            "scoring_weights": dict(self.scoring_weights),
            "adopt_adapt_weights": dict(self.adopt_adapt_weights),
            "scoring_thresholds": list(self.scoring_thresholds),
            "adopt_adapt_thresholds": list(self.adopt_adapt_thresholds),
            "data_model_thresholds": list(self.data_model_thresholds),
            "profiles_thresholds": list(self.profiles_thresholds),
            "profiles_ps_ratio_thresholds": list(self.profiles_ps_ratio_thresholds),
            "innovation_colors": dict(self.innovation_colors),
            "ai_usage_tags": list(self.ai_usage_tags),
            "posture_adopt_adapt": serialize_posture_config(self.posture_config),
            "run_tests": bool(self.run_tests_var.get()),
            "calculate_coverage": bool(self.calculate_coverage_var.get()),
            "dd_html": self.settings.get("dd_html", True),
            "dd_word": self.settings.get("dd_word", True),
            "dd_excel": self.settings.get("dd_excel", True),
            "dd_selected_objects": self.settings.get("dd_selected_objects", []),
        }
        payload.update(self._current_index_card_visibility().to_settings())
        save_settings(self.settings_path, payload)
        self.settings = payload

    # ------------------------------------------------------------------ helpers

    def _current_index_card_visibility(self) -> IndexCardVisibility:
        """Snapshot the current BooleanVar values as an IndexCardVisibility."""
        return IndexCardVisibility(
            show_customization_level=bool(self.show_card_customization_level_var.get()),
            show_score=bool(self.show_card_score_var.get()),
            show_adopt_vs_adapt=bool(self.show_card_adopt_vs_adapt_var.get()),
            show_adopt_adapt_score=bool(self.show_card_adopt_adapt_score_var.get()),
            show_custom_objects=bool(self.show_card_custom_objects_var.get()),
            show_custom_fields=bool(self.show_card_custom_fields_var.get()),
            show_flows=bool(self.show_card_flows_var.get()),
            show_apex_classes_triggers=bool(self.show_card_apex_classes_triggers_var.get()),
            show_omni_components=bool(self.show_card_omni_components_var.get()),
            show_findings=bool(self.show_card_findings_var.get()),
            show_ai_usage=bool(self.show_card_ai_usage_var.get()),
            show_data_model_footprint=bool(self.show_card_data_model_footprint_var.get()),
            show_adopt_adapt_posture=bool(self.show_card_adopt_adapt_posture_var.get()),
            show_agents=bool(self.show_card_agents_var.get()),
            show_gen_ai_prompts=bool(self.show_card_gen_ai_prompts_var.get()),
            show_einstein_predictions=bool(self.show_card_einstein_predictions_var.get()),
            show_test_coverage=bool(self.show_card_test_coverage_var.get()),
            show_debt=bool(self.show_card_debt_var.get()),
            show_innovation=bool(self.show_card_innovation_var.get()),
            show_sharing_rules=bool(self.show_card_sharing_rules_var.get()),
            show_duplicate_rules=bool(self.show_card_duplicate_rules_var.get()),
            show_lwc=bool(self.show_card_lwc_var.get()),
            show_aura=bool(self.show_card_aura_var.get()),
            show_dependencies=bool(self.show_card_dependencies_var.get()),
        )

    def _to_rel_path(self, path_str: str) -> str:
        """Convert an absolute path string to a path relative to app_dir."""
        if not path_str:
            return ""
        try:
            p = Path(path_str)
            if p.is_absolute():
                return os.path.relpath(p, self.app_dir)
        except Exception:
            pass
        return path_str

    def _to_abs_path(self, path_str: str) -> str:
        """Convert a relative path string to an absolute path string."""
        if not path_str:
            return ""
        try:
            p = Path(path_str)
            if not p.is_absolute():
                return str((self.app_dir / p).resolve())
        except Exception:
            pass
        return path_str
