"""Customization metrics dataclass and default scoring configuration."""

from __future__ import annotations

from dataclasses import dataclass


DEFAULT_SCORING_WEIGHTS: dict[str, int] = {
    "custom_objects": 8,
    "custom_fields": 1,
    "record_types": 2,
    "validation_rules": 2,
    "layouts": 1,
    "custom_tabs": 3,
    "custom_apps": 4,
    "flows": 3,
    "apex_classes": 3,
    "apex_triggers": 3,
    "omni_scripts": 4,
    "omni_integration_procedures": 4,
    "omni_ui_cards": 3,
    "omni_data_transforms": 2,
    "agents": 5,
    "gen_ai_prompts": 4,
    "einstein_predictions": 5,
    "bre_decision_matrices": 4,
    "bre_expression_sets": 4,
}

DEFAULT_ADOPT_ADAPT_WEIGHTS: dict[str, int] = {
    "custom_objects": 20,
    "custom_fields": 10,
    "apex_classes": 30,
    "flows": 25,
    "lwc": 25,
    "flexipages": 15,
    "omni_scripts": 20,
    "omni_integration_procedures": 20,
    "omni_ui_cards": 20,
    "omni_data_transforms": 15,
    "bre_decision_matrices": 20,
    "bre_expression_sets": 20,
    "agents": 30,
    "gen_ai_prompts": 25,
    "einstein_predictions": 30,
}


# Score breakpoints used to derive a textual level from the raw score. The
# tuple stores ``(low, medium, high)``: a score strictly below the first
# value is the lowest level, and so on. Four levels are produced.
DEFAULT_SCORING_THRESHOLDS: tuple[int, int, int] = (50, 150, 350)
DEFAULT_ADOPT_ADAPT_THRESHOLDS: tuple[int, int, int] = (100, 300, 600)
# Data model personalisation: based on the custom_objects count.
# 30 / 60 / 90 custom objects is a meaningful low / medium / high threshold
# for a typical Salesforce org.
DEFAULT_DATA_MODEL_THRESHOLDS: tuple[int, int, int] = (30, 60, 90)
# Profiles personalisation: based on the profiles count.
# 10 / 30 / 60 profiles is a meaningful low / medium / high threshold
# for a typical Salesforce org.
DEFAULT_PROFILES_THRESHOLDS: tuple[int, int, int] = (10, 30, 60)
# Profiles vs Permission Sets ratio (profiles / PS * 100 as integer %).
# < 30 = good (PS-first approach), 30-60 = attention, 60-100 = risky,
# > 100 = critical (more profiles than PS).
DEFAULT_PROFILES_PS_RATIO_THRESHOLDS: tuple[int, int, int] = (30, 60, 100)


@dataclass(slots=True)
class CustomizationMetrics:
    custom_objects: int = 0
    custom_fields: int = 0
    record_types: int = 0
    validation_rules: int = 0
    layouts: int = 0
    custom_tabs: int = 0
    custom_apps: int = 0
    flows: int = 0
    apex_classes: int = 0
    apex_triggers: int = 0
    omni_scripts: int = 0
    omni_integration_procedures: int = 0
    omni_ui_cards: int = 0
    omni_data_transforms: int = 0
    bre_decision_matrices: int = 0
    bre_expression_sets: int = 0
    agents: int = 0
    gen_ai_prompts: int = 0
    einstein_predictions: int = 0
    sharing_rules: int = 0
    duplicate_rules: int = 0
    lwc_count: int = 0
    flexipage_count: int = 0
    test_coverage: float | None = None  # Global org test coverage
    weights: dict[str, int] | None = None
    adopt_adapt_weights: dict[str, int] | None = None
    scoring_thresholds: tuple[int, int, int] | None = None
    adopt_adapt_thresholds: tuple[int, int, int] | None = None
    data_model_thresholds: tuple[int, int, int] | None = None
    profiles_count: int = 0
    profiles_thresholds: tuple[int, int, int] | None = None
    # Security analysis metrics
    custom_profiles_count: int = 0
    dangerous_profiles_count: int = 0
    profiles_with_modify_all: int = 0
    perm_sets_with_modify_all: int = 0
    permission_sets_count: int = 0
    profiles_ps_ratio_thresholds: tuple[int, int, int] | None = None

    def _weight(self, key: str) -> int:
        if self.weights is not None:
            value = self.weights.get(key)
            if isinstance(value, int):
                return value
            if isinstance(value, str) and value.strip().lstrip("-").isdigit():
                return int(value.strip())
        return DEFAULT_SCORING_WEIGHTS[key]

    def _aa_weight(self, key: str) -> int:
        if self.adopt_adapt_weights is not None:
            value = self.adopt_adapt_weights.get(key)
            if isinstance(value, int):
                return value
            if isinstance(value, str) and value.strip().lstrip("-").isdigit():
                return int(value.strip())
        return DEFAULT_ADOPT_ADAPT_WEIGHTS.get(key, 0)

    @property
    def score(self) -> int:
        return (
            self.score_no_code
            + self.score_low_code
            + self.score_pro_code
        )

    @property
    def score_no_code(self) -> int:
        return (
            self.custom_objects * self._weight("custom_objects")
            + self.custom_fields * self._weight("custom_fields")
            + self.record_types * self._weight("record_types")
            + self.validation_rules * self._weight("validation_rules")
            + self.layouts * self._weight("layouts")
            + self.custom_tabs * self._weight("custom_tabs")
            + self.custom_apps * self._weight("custom_apps")
            + self.einstein_predictions * self._weight("einstein_predictions")
        )

    @property
    def score_low_code(self) -> int:
        return (
            self.flows * self._weight("flows")
            + self.omni_scripts * self._weight("omni_scripts")
            + self.omni_integration_procedures * self._weight("omni_integration_procedures")
            + self.omni_ui_cards * self._weight("omni_ui_cards")
            + self.omni_data_transforms * self._weight("omni_data_transforms")
            + self.bre_decision_matrices * self._weight("bre_decision_matrices")
            + self.bre_expression_sets * self._weight("bre_expression_sets")
            + self.gen_ai_prompts * self._weight("gen_ai_prompts")
        )

    @property
    def score_pro_code(self) -> int:
        return (
            self.apex_classes * self._weight("apex_classes")
            + self.apex_triggers * self._weight("apex_triggers")
            + self.agents * self._weight("agents")
        )

    @property
    def level(self) -> str:
        low, medium, high = self.scoring_thresholds or DEFAULT_SCORING_THRESHOLDS
        score = self.score
        if score < low:
            return "Faible"
        if score < medium:
            return "Moyen"
        if score < high:
            return "Eleve"
        return "Tres eleve"

    @property
    def adopt_adapt_score(self) -> int:
        """Calculates the Adopt vs Adapt score based on customization level."""
        return (
            self.adopt_adapt_score_no_code
            + self.adopt_adapt_score_low_code
            + self.adopt_adapt_score_pro_code
        )

    @property
    def adopt_adapt_score_no_code(self) -> int:
        return (
            self.custom_objects * self._aa_weight("custom_objects")
            + self.custom_fields * self._aa_weight("custom_fields")
            + self.flexipage_count * self._aa_weight("flexipages")
        )

    @property
    def adopt_adapt_score_low_code(self) -> int:
        return (
            self.flows * self._aa_weight("flows")
            + self.omni_scripts * self._aa_weight("omni_scripts")
            + self.omni_integration_procedures * self._aa_weight("omni_integration_procedures")
            + self.omni_ui_cards * self._aa_weight("omni_ui_cards")
            + self.omni_data_transforms * self._aa_weight("omni_data_transforms")
            + self.bre_decision_matrices * self._aa_weight("bre_decision_matrices")
            + self.bre_expression_sets * self._aa_weight("bre_expression_sets")
        )

    @property
    def adopt_adapt_score_pro_code(self) -> int:
        return (
            self.apex_classes * self._aa_weight("apex_classes")
            + self.lwc_count * self._aa_weight("lwc")
            + self.agents * self._aa_weight("agents")
            + self.gen_ai_prompts * self._aa_weight("gen_ai_prompts")
            + self.einstein_predictions * self._aa_weight("einstein_predictions")
        )

    @property
    def adopt_adapt_level(self) -> str:
        low, medium, high = (
            self.adopt_adapt_thresholds or DEFAULT_ADOPT_ADAPT_THRESHOLDS
        )
        score = self.adopt_adapt_score
        if score < low:
            return "Adopt (Standard)"
        if score < medium:
            return "Adapt (Low Customization)"
        if score < high:
            return "Adapt (Medium Customization)"
        return "Adapt (High Customization)"

    @property
    def data_model_score(self) -> int:
        """Nombre d'objets custom — indicateur de personnalisation du data model."""
        return self.custom_objects

    @property
    def data_model_level(self) -> str:
        low, medium, high = (
            self.data_model_thresholds or DEFAULT_DATA_MODEL_THRESHOLDS
        )
        score = self.data_model_score
        if score < low:
            return "Bas"
        if score < medium:
            return "Moyen"
        if score < high:
            return "Haut"
        return "Tres haut"

    @property
    def profiles_score(self) -> int:
        """Nombre de profils — indicateur de personnalisation de la sécurité."""
        return self.profiles_count

    @property
    def profiles_level(self) -> str:
        low, medium, high = (
            self.profiles_thresholds or DEFAULT_PROFILES_THRESHOLDS
        )
        score = self.profiles_score
        if score < low:
            return "Bas"
        if score < medium:
            return "Moyen"
        if score < high:
            return "Haut"
        return "Tres haut"

    @property
    def profiles_ps_ratio_score(self) -> int:
        """Ratio profils custom / permission sets exprimé en % (0-200+)."""
        return min(200, int(self.custom_profiles_count / max(1, self.permission_sets_count) * 100))

    @property
    def profiles_ps_ratio_level(self) -> str:
        low, medium, high = (
            self.profiles_ps_ratio_thresholds or DEFAULT_PROFILES_PS_RATIO_THRESHOLDS
        )
        score = self.profiles_ps_ratio_score
        if score < low:
            return "Bon"
        if score < medium:
            return "Attention"
        if score < high:
            return "Risque"
        return "Critique"
