"""Customisation universe (with / without AI tag) for the AI-usage indicator.

Holds :class:`CustomElement` and :class:`AIUsageStats`, plus the helpers
that enumerate the customisation/code/low-code population of a snapshot
and combine it with the :class:`AIUsageEntry` list produced by
:mod:`ai_usage_scan` to compute with-tag/without-tag breakdowns. Split out
of :mod:`ai_usage` to keep that module under the repo's 500-line
convention.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.core.ai_usage_scan import AIUsageEntry
from src.core.models import MetadataSnapshot


@dataclass(slots=True, frozen=True)
class CustomElement:
    """A single element belonging to the customisation/code/low-code universe.

    The "AI usage" indicator compares the population of customised elements
    of an org (custom objects, custom fields, validation rules, record
    types, flows, Apex classes/triggers) against the subset that carries an
    AI tag. Each element is identified by the same ``(element_type,
    element_name)`` tuple used by :class:`AIUsageEntry`, which lets us join
    the two collections without ambiguity.
    """

    element_type: str
    element_name: str
    source: str = ""


@dataclass(slots=True)
class AIUsageStats:
    """Aggregate AI-usage figures for the index card and detail page.

    Keeping the lists (rather than just counts) lets the detail page render
    the elements without a tag explicitly, which is what reviewers usually
    want: a checklist of items still to flag or document. ``percent_*``
    helpers return values in the ``[0.0, 100.0]`` range and gracefully
    degrade to ``0.0`` when the universe is empty so callers never have to
    guard against division by zero.
    """

    universe: list[CustomElement] = field(default_factory=list)
    with_tag: list[CustomElement] = field(default_factory=list)
    without_tag: list[CustomElement] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.universe)

    @property
    def with_tag_count(self) -> int:
        return len(self.with_tag)

    @property
    def without_tag_count(self) -> int:
        return len(self.without_tag)

    @property
    def percent_with_tag(self) -> float:
        return (self.with_tag_count / self.total * 100.0) if self.total else 0.0

    @property
    def percent_without_tag(self) -> float:
        return (self.without_tag_count / self.total * 100.0) if self.total else 0.0


# Element types reported in :class:`AIUsageStats`. Profiles, permission sets
# and flow elements are *scanned* by :func:`scan_ai_usage` (so the detail page
# still surfaces tags found there) but they are not part of the
# customisation/code/low-code population the user asked us to evaluate, hence
# they do not appear in the universe.
_UNIVERSE_TYPES: tuple[str, ...] = (
    "Object",
    "Field",
    "RecordType",
    "ValidationRule",
    "Flow",
    "ApexClass",
    "ApexTrigger",
)


def _is_custom_field(field_info, parent_object) -> bool:
    """Return ``True`` for custom fields under standard or custom objects.

    Salesforce marks custom fields with the ``__c`` suffix; we honour the
    parser-provided ``custom`` flag first and fall back to the suffix
    convention so namespaced or managed-package fields are still detected
    when the parser left the flag unset.
    """

    if getattr(field_info, "custom", False):
        return True
    api_name = getattr(field_info, "api_name", "") or ""
    return api_name.endswith("__c")


def enumerate_customization_universe(
    snapshot: MetadataSnapshot,
) -> list[CustomElement]:
    """Return every custom/code/low-code element of the snapshot.

    Includes:

    * Custom objects (``__c``).
    * Custom fields under any object (standard or custom).
    * Record types declared on custom objects (record types on standard
      objects are out-of-scope: they are configuration of a standard
      Salesforce surface, not customisation we own).
    * Validation rules (always considered customisation).
    * Every flow.
    * Every Apex class and trigger.
    """

    universe: list[CustomElement] = []

    for obj in snapshot.objects:
        obj_source = str(obj.source_path) if obj.source_path else ""

        if obj.custom:
            universe.append(
                CustomElement(
                    element_type="Object",
                    element_name=obj.api_name,
                    source=obj_source,
                )
            )

        for field_info in obj.fields:
            if _is_custom_field(field_info, obj):
                universe.append(
                    CustomElement(
                        element_type="Field",
                        element_name=f"{obj.api_name}.{field_info.api_name}",
                        source=obj_source,
                    )
                )

        if obj.custom:
            for record_type in obj.record_types:
                universe.append(
                    CustomElement(
                        element_type="RecordType",
                        element_name=f"{obj.api_name}.{record_type.full_name}",
                        source=obj_source,
                    )
                )

        for validation_rule in obj.validation_rules:
            universe.append(
                CustomElement(
                    element_type="ValidationRule",
                    element_name=f"{obj.api_name}.{validation_rule.full_name}",
                    source=obj_source,
                )
            )

    for flow in snapshot.flows:
        universe.append(
            CustomElement(
                element_type="Flow",
                element_name=flow.name,
                source=str(flow.source_path) if flow.source_path else "",
            )
        )

    for artifact in snapshot.apex_artifacts:
        if artifact.kind == "trigger":
            element_type = "ApexTrigger"
        elif artifact.is_test:
            element_type = "ApexClass (Test)"
        else:
            element_type = "ApexClass"

        universe.append(
            CustomElement(
                element_type=element_type,
                element_name=artifact.name,
                source=str(artifact.source_path) if artifact.source_path else "",
            )
        )

    universe.sort(
        key=lambda item: (item.element_type.casefold(), item.element_name.casefold())
    )
    return universe


def compute_ai_usage_stats(
    snapshot: MetadataSnapshot,
    entries: list[AIUsageEntry],
) -> AIUsageStats:
    """Combine the snapshot universe with detected AI entries.

    A custom Flow is also considered "with tag" when one of its inner
    elements (a ``FlowElement`` entry such as a decision or assignment)
    carries the tag, so a partially generated flow does not slip into the
    "without tag" bucket.
    """

    universe = enumerate_customization_universe(snapshot)
    tagged_keys = {(entry.element_type, entry.element_name) for entry in entries}

    flow_names_with_tagged_children = {
        entry.element_name.split(".", 1)[0]
        for entry in entries
        if entry.element_type == "FlowElement" and "." in entry.element_name
    }

    def _is_tagged(element: CustomElement) -> bool:
        if (element.element_type, element.element_name) in tagged_keys:
            return True
        if (
            element.element_type == "Flow"
            and element.element_name in flow_names_with_tagged_children
        ):
            return True
        return False

    with_tag = [item for item in universe if _is_tagged(item)]
    without_tag = [item for item in universe if not _is_tagged(item)]

    return AIUsageStats(universe=universe, with_tag=with_tag, without_tag=without_tag)
