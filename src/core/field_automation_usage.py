"""Which automations reference each field, for the Data Dictionary.

Answers the question a TechLead asks before touching a field: "if I delete or
change this, what breaks?". The answer is derived from the impact analysis
already produced by the parser (``MetadataSnapshot.dependencies``) rather than
from a second scan, so this column can never disagree with the Impact Analysis
pages of the HTML report.

Only automation and code sources are reported. Page Layouts, Lightning Pages
and Reports also reference fields and are present in the dependency graph, but
almost every field sits on at least one layout, which would leave the column
non-empty for nearly every row and therefore worthless as a warning.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Iterable

if TYPE_CHECKING:
    from src.core.models import Dependency, MetadataSnapshot

#: ``Dependency.source_kind`` -> label shown in the workbook. Kinds absent
#: from this mapping are deliberately ignored (see the module docstring).
AUTOMATION_LABELS: dict[str, str] = {
    "Flow": "Flow",
    "trigger": "Apex Trigger",
    "class": "Apex",
    "ValidationRule": "Validation Rule",
    "Formula": "Formule",
    "Omni": "OmniStudio",
    "LWC": "LWC",
    "Aura": "Aura",
}

#: Display order of the labels inside a cell, roughly by how likely the source
#: is to break at runtime. Stable ordering keeps two exports comparable.
_LABEL_ORDER = tuple(AUTOMATION_LABELS.values())


def field_automation_usages(
    dependencies: Iterable["Dependency"],
) -> dict[str, list[str]]:
    """Map a lowercased ``"object.field"`` to the automation types using it.

    Duplicate dependencies (the scan reports one per match, and a Flow may
    reference the same field a dozen times) collapse into a single label.
    """
    by_field: dict[str, set[str]] = {}
    for dependency in dependencies:
        if dependency.target_kind != "Field":
            continue
        label = AUTOMATION_LABELS.get(dependency.source_kind)
        if label is None:
            continue
        by_field.setdefault(dependency.target_name.lower(), set()).add(label)

    return {
        target: [label for label in _LABEL_ORDER if label in labels]
        for target, labels in by_field.items()
    }


def assign_field_automation_usages(snapshot: "MetadataSnapshot") -> None:
    """Store the automation types on every field of ``snapshot``.

    Carried on :class:`~src.core.models.FieldInfo` rather than passed to the
    writers, so it survives the copies the Data Dictionary selection makes and
    reaches every report without threading a new argument through each one.
    """
    usages = field_automation_usages(snapshot.dependencies)
    for obj in snapshot.objects:
        for field in obj.fields:
            field.automation_usages = usages.get(
                f"{obj.api_name}.{field.api_name}".lower(), []
            )
