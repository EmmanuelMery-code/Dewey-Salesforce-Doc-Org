"""Data model metadata dataclasses (objects, fields, record types, rules)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class FieldInfo:
    api_name: str
    label: str = ""
    data_type: str = ""
    description: str = ""
    required: bool = False
    custom: bool = False
    reference_to: list[str] = field(default_factory=list)
    relationship_name: str = ""
    picklist_values: list[str] = field(default_factory=list)
    picklist_api_names: list[str] = field(default_factory=list)
    picklist_is_global: bool = False
    picklist_global_name: str = ""

    @property
    def is_picklist(self) -> bool:
        return self.data_type in ("Picklist", "MultiselectPicklist")


@dataclass(slots=True)
class RecordTypeInfo:
    full_name: str
    label: str = ""
    description: str = ""
    active: bool = False


@dataclass(slots=True)
class ValidationRuleInfo:
    full_name: str
    active: bool = False
    description: str = ""
    error_display_field: str = ""
    error_message: str = ""
    error_condition_formula: str = ""
    api_version: str = ""

    @property
    def complexity_score(self) -> int:
        if not self.error_condition_formula:
            return 0
        # Basic complexity: length + number of functions/operators
        score = len(self.error_condition_formula) // 50
        score += self.error_condition_formula.count("(")
        score += self.error_condition_formula.count("IF")
        score += self.error_condition_formula.count("AND")
        score += self.error_condition_formula.count("OR")
        score += self.error_condition_formula.count("CASE")
        return score


@dataclass(slots=True)
class RelationshipInfo:
    field_name: str
    relationship_type: str
    targets: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ObjectInfo:
    api_name: str
    label: str = ""
    plural_label: str = ""
    description: str = ""
    deployment_status: str = ""
    sharing_model: str = ""
    visibility: str = ""
    custom: bool = False
    api_version: str = ""
    fields: list[FieldInfo] = field(default_factory=list)
    record_types: list[RecordTypeInfo] = field(default_factory=list)
    validation_rules: list[ValidationRuleInfo] = field(default_factory=list)
    relationships: list[RelationshipInfo] = field(default_factory=list)
    source_path: Path | None = None
    dewey_comment: str = ""
    dewey_piloted_by: str = ""
    dewey_status: str = "-"
    dewey_squad: str = ""

    @property
    def dewey_comment_combined(self) -> str:
        """Concatenation of the metadata ``description`` and the user-entered
        "Commentaire Dewey" free text, in that order.

        Report writers should use this instead of ``dewey_comment`` directly
        whenever they render the "Commentaire Dewey" column/row so the
        metadata description is not lost when a user comment is also
        present. Callers that need the concatenation to be optional (e.g. a
        UI checkbox) should choose between this property and the raw
        ``dewey_comment`` themselves rather than changing this property,
        since other callers (e.g. the full-run orchestrator) always expect
        the concatenated behaviour.
        """
        parts = [part.strip() for part in (self.description, self.dewey_comment) if part and part.strip()]
        return " ".join(parts)
