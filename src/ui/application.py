"""Main application window for the Salesforce documentation generator.

The class is intentionally kept small: it owns only the ``__init__``
initialisation logic and the class-level constants.  All behavioural
responsibilities are delegated to focused mixin classes:

* :mod:`src.ui.app_settings_mixin`   — load / save ``app_settings.json``
* :mod:`src.ui.app_language_mixin`   — translations and language switching
* :mod:`src.ui.app_sf_cli_mixin`     — Salesforce CLI actions
* :mod:`src.ui.app_generation_mixin` — documentation generation and coverage
* :mod:`src.ui.app_ai_mixin`         — AI text-expansion feature
* :mod:`src.ui.app_ui_mixin`         — UI construction, menus, pickers, log
"""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from queue import Queue
from threading import Thread
from tkinter import scrolledtext, ttk
from typing import Any

from src.ai import (
    AIMessage,
    CLAUDE_MODELS,
    GEMINI_MODELS,
    build_system_prompt,
    create_service,
)
from src.analyzer.models import Rule
from src.analyzer.rule_catalog import DEFAULT_RULES_PATH
from src.core.customization_metrics import PostureCapabilityConfig
from src.core.index_card_visibility import parse_index_card_visibility
from src.core.models import (
    DEFAULT_ADOPT_ADAPT_THRESHOLDS,
    DEFAULT_SCORING_THRESHOLDS,
    DEFAULT_SCORING_WEIGHTS,
)
from src.core.orchestrator import GenerationResult, SalesforceDocumentationGenerator
from src.core.sf_cli_service import OrgSummary, SalesforceCliService
from src.ui.app_ai_mixin import AppAiMixin
from src.ui.app_generation_mixin import AppGenerationMixin
from src.ui.app_language_mixin import AppLanguageMixin
from src.ui.app_settings_mixin import AppSettingsMixin
from src.ui.app_sf_cli_mixin import AppSfCliMixin
from src.ui.app_ui_mixin import AppUiMixin
from src.ui.constants import (
    AI_PROVIDERS as UI_AI_PROVIDERS,
    LANGUAGES as UI_LANGUAGES,
    LOGIN_TARGETS as UI_LOGIN_TARGETS,
    ORG_CHECK_APP_URL as UI_ORG_CHECK_APP_URL,
    ORG_CHECK_CHOICES as UI_ORG_CHECK_CHOICES,
    ORG_CHECK_GITHUB_URL as UI_ORG_CHECK_GITHUB_URL,
    PMD_DOWNLOAD_URL as UI_PMD_DOWNLOAD_URL,
    SF_CLI_DOWNLOAD_URL as UI_SF_CLI_DOWNLOAD_URL,
)
from src.ui.settings import (
    DEFAULT_AI_USAGE_TAGS,
    default_posture_config,
    parse_ai_tags,
    parse_posture_config,
)
from src.ui.task_manager import TaskManager
from src.ui.translations import TRANSLATIONS as UI_TRANSLATIONS


class Application(
    AppUiMixin,
    AppSettingsMixin,
    AppLanguageMixin,
    AppSfCliMixin,
    AppGenerationMixin,
    AppAiMixin,
    tk.Tk,
):
    """Main Tk window — owns only constants and ``__init__``."""

    # ------------------------------------------------------------------ constants

    SF_CLI_DOWNLOAD_URL = UI_SF_CLI_DOWNLOAD_URL
    PMD_DOWNLOAD_URL = UI_PMD_DOWNLOAD_URL
    ORG_CHECK_APP_URL = UI_ORG_CHECK_APP_URL
    ORG_CHECK_GITHUB_URL = UI_ORG_CHECK_GITHUB_URL
    LOGIN_TARGETS = UI_LOGIN_TARGETS
    LANGUAGES = UI_LANGUAGES
    ORG_CHECK_CHOICES = UI_ORG_CHECK_CHOICES
    AI_PROVIDERS = UI_AI_PROVIDERS

    DEFAULT_GEMINI_MODELS = list(GEMINI_MODELS)
    DEFAULT_CLAUDE_MODELS = list(CLAUDE_MODELS)
    DEFAULT_GATEWAY_MODELS = [
        "claude-sonnet-4-20250514",
        "claude-3-7-sonnet-20250219",
        "claude-3-5-sonnet-20241022",
        "gemini-2.5-pro",
        "gemini-2.5-flash",
        "gemini-2.0-flash",
        "gpt-5",
        "gpt-5-mini",
        "gpt-40",
        "gpt-4o-mini",
    ]

    DEFAULT_GEMINI_MODEL = GEMINI_MODELS[0]
    DEFAULT_CLAUDE_MODEL = CLAUDE_MODELS[0]
    DEFAULT_GATEWAY_MODEL = "gpt-5"
    DISCUSSION_MIN_INTERVAL_SECONDS = 5.0
    TRANSLATIONS = UI_TRANSLATIONS

    ANALYZER_SEVERITY_ORDER: list[str] = ["Critical", "Major", "Minor", "Info"]
    ANALYZER_SEVERITY_COLORS: dict[str, str] = {
        "Critical": "#991b1b",
        "Major": "#9a3412",
        "Minor": "#854d0e",
        "Info": "#1e3a8a",
    }

    SCORING_COMPONENTS: list[tuple[str, str, str]] = [
        ("custom_objects", "scoring_component_custom_objects", "scoring_desc_custom_objects"),
        ("custom_fields", "scoring_component_custom_fields", "scoring_desc_custom_fields"),
        ("record_types", "scoring_component_record_types", "scoring_desc_record_types"),
        (
            "validation_rules",
            "scoring_component_validation_rules",
            "scoring_desc_validation_rules",
        ),
        ("layouts", "scoring_component_layouts", "scoring_desc_layouts"),
        ("custom_tabs", "scoring_component_custom_tabs", "scoring_desc_custom_tabs"),
        ("custom_apps", "scoring_component_custom_apps", "scoring_desc_custom_apps"),
        ("flows", "scoring_component_flows", "scoring_desc_flows"),
        ("apex_classes", "scoring_component_apex_classes", "scoring_desc_apex_classes"),
        ("apex_triggers", "scoring_component_apex_triggers", "scoring_desc_apex_triggers"),
        ("omni_scripts", "scoring_component_omni_scripts", "scoring_desc_omni_scripts"),
        (
            "omni_integration_procedures",
            "scoring_component_omni_integration_procedures",
            "scoring_desc_omni_integration_procedures",
        ),
        ("omni_ui_cards", "scoring_component_omni_ui_cards", "scoring_desc_omni_ui_cards"),
        (
            "omni_data_transforms",
            "scoring_component_omni_data_transforms",
            "scoring_desc_omni_data_transforms",
        ),
        (
            "einstein_predictions",
            "scoring_component_einstein_predictions",
            "scoring_desc_einstein_predictions",
        ),
        ("agents", "configuration_card_agents", "scoring_desc_agents"),
        ("gen_ai_prompts", "configuration_card_gen_ai_prompts", "scoring_desc_gen_ai_prompts"),
    ]

    ADOPT_ADAPT_COMPONENTS: list[tuple[str, str, str]] = [
        ("custom_objects", "scoring_component_custom_objects", "scoring_desc_custom_objects"),
        ("custom_fields", "scoring_component_custom_fields", "scoring_desc_custom_fields"),
        ("apex_classes", "scoring_component_apex_classes", "scoring_desc_apex_classes"),
        ("flows", "scoring_component_flows", "scoring_desc_flows"),
        ("lwc", "adopt_adapt_component_lwc", "adopt_adapt_desc_lwc"),
        ("flexipages", "adopt_adapt_component_flexipages", "adopt_adapt_desc_flexipages"),
        (
            "omni_scripts",
            "scoring_component_omni_scripts",
            "adopt_adapt_desc_omni_scripts",
        ),
        (
            "omni_integration_procedures",
            "scoring_component_omni_integration_procedures",
            "adopt_adapt_desc_omni_integration_procedures",
        ),
        (
            "omni_ui_cards",
            "scoring_component_omni_ui_cards",
            "adopt_adapt_desc_omni_ui_cards",
        ),
        (
            "omni_data_transforms",
            "scoring_component_omni_data_transforms",
            "adopt_adapt_desc_omni_data_transforms",
        ),
        (
            "einstein_predictions",
            "scoring_component_einstein_predictions",
            "adopt_adapt_desc_einstein_predictions",
        ),
        ("agents", "configuration_card_agents", "adopt_adapt_desc_agents"),
        (
            "gen_ai_prompts",
            "configuration_card_gen_ai_prompts",
            "adopt_adapt_desc_gen_ai_prompts",
        ),
    ]

    # ------------------------------------------------------------------ init

    def __init__(self) -> None:
        super().__init__()
        self._setup_styles()
        self.geometry("980x760")
        self.minsize(900, 620)
        self.app_dir = Path(__file__).resolve().parent.parent.parent
        self.settings_path = self.app_dir / "app_settings.json"
        self.settings = self._load_settings()
        self.language = self.settings.get("language", "fr")

        self.source_var = tk.StringVar(
            value=self._to_abs_path(self.settings.get("source_folder", ""))
        )
        self.output_var = tk.StringVar(
            value=self._to_abs_path(self.settings.get("output_folder", ""))
        )
        self.exclusion_file_var = tk.StringVar(
            value=self._to_abs_path(self.settings.get("exclusion_file", ""))
        )
        self.technical_debt_file_var = tk.StringVar(
            value=self._to_abs_path(
                self.settings.get("technical_debt_file", "technical_debt.json")
            )
        )
        self.innovation_file_var = tk.StringVar(
            value=self._to_abs_path(self.settings.get("innovation_file", "innovations.json"))
        )
        self.pmd_enabled_var = tk.BooleanVar(value=bool(self.settings.get("pmd_enabled", False)))
        self.pmd_ruleset_var = tk.StringVar(
            value=self._to_abs_path(self.settings.get("pmd_ruleset_file", ""))
        )
        self.analyzer_rules_file_var = tk.StringVar(
            value=self._to_abs_path(
                self.settings.get("analyzer_rules_file", str(DEFAULT_RULES_PATH))
            )
        )
        self.alias_var = tk.StringVar(value=self.settings.get("alias", ""))
        self.language_label_var = tk.StringVar(
            value=self.LANGUAGES.get(self.language, "Francais")
        )
        self.login_target_key = self.settings.get("login_target", "production")
        self.login_target_var = tk.StringVar()
        self.instance_url_var = tk.StringVar(
            value=self.settings.get(
                "instance_url", self.LOGIN_TARGETS["production"]
            )
        )
        self.selected_org_var = tk.StringVar(
            value=self.settings.get("last_selected_org", "")
        )
        org_check_default = self.settings.get("org_check_type", self.ORG_CHECK_CHOICES[0])
        if org_check_default not in self.ORG_CHECK_CHOICES:
            org_check_default = self.ORG_CHECK_CHOICES[0]
        self.org_check_choice_var = tk.StringVar(value=org_check_default)
        self.status_var = tk.StringVar(value=self._t("ready"))

        self.gemini_model_choices = self.settings.get("gemini_models", self.DEFAULT_GEMINI_MODELS)
        self.claude_model_choices = self.settings.get("claude_models", self.DEFAULT_CLAUDE_MODELS)
        self.gateway_model_choices = self.settings.get(
            "gateway_models", self.DEFAULT_GATEWAY_MODELS
        )

        default_provider = self.settings.get("ai_provider", self.AI_PROVIDERS[0])
        if default_provider not in self.AI_PROVIDERS:
            default_provider = self.AI_PROVIDERS[0]
        self.ai_provider_var = tk.StringVar(value=default_provider)
        self.claude_api_key_var = tk.StringVar(value=self.settings.get("claude_api_key", ""))
        self.gemini_api_key_var = tk.StringVar(value=self.settings.get("gemini_api_key", ""))
        self.gateway_api_key_var = tk.StringVar(value=self.settings.get("gateway_api_key", ""))
        self.gateway_cert_path_var = tk.StringVar(
            value=self._to_abs_path(
                self.settings.get(
                    "gateway_cert_path", "config/Salesforce_Internal_Root_CA_3.pem"
                )
            )
        )
        stored_claude_model = str(self.settings.get("claude_model", "") or "").strip()
        if stored_claude_model not in self.claude_model_choices:
            stored_claude_model = self.DEFAULT_CLAUDE_MODEL
        stored_gemini_model = str(self.settings.get("gemini_model", "") or "").strip()
        # Silently migrate retired models to the most recent 2.5 option.
        if stored_gemini_model not in self.gemini_model_choices:
            stored_gemini_model = self.DEFAULT_GEMINI_MODEL
        stored_gateway_model = str(self.settings.get("gateway_model", "") or "").strip()
        if stored_gateway_model not in self.gateway_model_choices:
            stored_gateway_model = self.DEFAULT_GATEWAY_MODEL
        self.claude_model_var = tk.StringVar(value=stored_claude_model)
        self.gemini_model_var = tk.StringVar(value=stored_gemini_model)
        self.gateway_model_var = tk.StringVar(value=stored_gateway_model)

        stored_prompt = self.settings.get("system_prompt")
        if not isinstance(stored_prompt, str) or not stored_prompt.strip():
            stored_prompt = build_system_prompt(self.language)
        self.system_prompt = stored_prompt

        # Analyzer rule widget state (populated by configuration screen)
        self._config_system_prompt_widget: scrolledtext.ScrolledText | None = None
        self._analyzer_rule_vars: dict[str, tk.BooleanVar] = {}
        self._analyzer_rule_min_api_vars: dict[str, tk.StringVar] = {}
        self._analyzer_rule_max_api_vars: dict[str, tk.StringVar] = {}
        self._analyzer_rules_cache: list[Rule] = []
        self._analyzer_rules_file: Path = Path(self.analyzer_rules_file_var.get())
        self._analyzer_rule_rows: list[dict[str, object]] = []
        self._analyzer_rule_count_var: tk.StringVar | None = None
        self._analyzer_rule_detail_widget: scrolledtext.ScrolledText | None = None
        self._analyzer_rule_filter_severity: tk.StringVar | None = None
        self._analyzer_rule_filter_category: tk.StringVar | None = None
        self._analyzer_rule_filter_scope: tk.StringVar | None = None
        self._analyzer_rule_selected_reference: str = ""

        self.generate_excels_var = tk.BooleanVar(
            value=bool(self.settings.get("generate_excels", True))
        )
        self.generate_org_check_reports_var = tk.BooleanVar(
            value=bool(self.settings.get("generate_org_check_reports", False))
        )
        self.generate_data_dictionary_word_var = tk.BooleanVar(
            value=bool(self.settings.get("generate_data_dictionary_word", True))
        )
        self.generate_summary_word_var = tk.BooleanVar(
            value=bool(self.settings.get("generate_summary_word", True))
        )

        # Index card visibility flags
        icv = parse_index_card_visibility(self.settings)
        self.show_card_customization_level_var = tk.BooleanVar(
            value=icv.show_customization_level
        )
        self.show_card_score_var = tk.BooleanVar(value=icv.show_score)
        self.show_card_adopt_vs_adapt_var = tk.BooleanVar(value=icv.show_adopt_vs_adapt)
        self.show_card_adopt_adapt_score_var = tk.BooleanVar(value=icv.show_adopt_adapt_score)
        self.show_card_custom_objects_var = tk.BooleanVar(value=icv.show_custom_objects)
        self.show_card_custom_fields_var = tk.BooleanVar(value=icv.show_custom_fields)
        self.show_card_flows_var = tk.BooleanVar(value=icv.show_flows)
        self.show_card_apex_classes_triggers_var = tk.BooleanVar(
            value=icv.show_apex_classes_triggers
        )
        self.show_card_omni_components_var = tk.BooleanVar(value=icv.show_omni_components)
        self.show_card_findings_var = tk.BooleanVar(value=icv.show_findings)
        self.show_card_ai_usage_var = tk.BooleanVar(value=icv.show_ai_usage)
        self.show_card_data_model_footprint_var = tk.BooleanVar(
            value=icv.show_data_model_footprint
        )
        self.show_card_adopt_adapt_posture_var = tk.BooleanVar(
            value=icv.show_adopt_adapt_posture
        )
        self.show_card_agents_var = tk.BooleanVar(value=icv.show_agents)
        self.show_card_gen_ai_prompts_var = tk.BooleanVar(value=icv.show_gen_ai_prompts)
        self.show_card_einstein_predictions_var = tk.BooleanVar(
            value=icv.show_einstein_predictions
        )
        self.show_card_test_coverage_var = tk.BooleanVar(value=icv.show_test_coverage)
        self.show_card_debt_var = tk.BooleanVar(value=icv.show_debt)
        self.show_card_innovation_var = tk.BooleanVar(value=icv.show_innovation)

        # Window / widget references (set by _build_ui / secondary screens)
        self.hero_image: tk.PhotoImage | None = None
        self.icon_image: tk.PhotoImage | None = None
        self.menu_bar: tk.Menu | None = None
        self.configuration_window: tk.Toplevel | None = None
        self.scoring_window: tk.Toplevel | None = None
        self.adopt_adapt_window: tk.Toplevel | None = None
        self.thresholds_window: tk.Toplevel | None = None
        self.latest_metrics = None
        self.latest_snapshot = None

        # Weights and thresholds
        self.scoring_weights = self._load_scoring_weights(self.settings)
        self.adopt_adapt_weights = self._load_adopt_adapt_weights(self.settings)
        self.scoring_thresholds = self._load_scoring_thresholds(self.settings)
        self.adopt_adapt_thresholds = self._load_adopt_adapt_thresholds(self.settings)
        self.data_model_thresholds = self._load_data_model_thresholds(self.settings)
        self.profiles_thresholds = self._load_profiles_thresholds(self.settings)
        self.profiles_ps_ratio_thresholds = self._load_profiles_ps_ratio_thresholds(self.settings)

        self.ai_usage_tags: list[str] = parse_ai_tags(self.settings)
        self._ai_tags_listbox: tk.Listbox | None = None
        self.posture_config: list[PostureCapabilityConfig] = parse_posture_config(self.settings)
        self._posture_panel_state: dict[str, object] | None = None

        self.task_manager = TaskManager(self)
        self.action_buttons: list[ttk.Button] = []
        self.orgs: list[OrgSummary] = []
        self.orgs_by_label: dict[str, OrgSummary] = {}
        self.cli_service = SalesforceCliService(
            self.app_dir, log_callback=self.task_manager.queue_log
        )

        # Discussion state
        self.discussion_messages: list[AIMessage] = []
        self.discussion_worker: Thread | None = None
        self.discussion_pending: bool = False
        self._discussion_last_send_ts: float = 0.0
        self.discussion_question_index: int | None = None
        self.discussion_question_ranges: list[tuple[str, str]] = []
        self.discussion_force_existing_docs: bool = False

        self._build_ui()
        self._apply_language(initial=True)
        self._load_branding()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(150, self.task_manager.poll_queue)
        self.after(250, lambda: self._refresh_orgs(initial=True))
