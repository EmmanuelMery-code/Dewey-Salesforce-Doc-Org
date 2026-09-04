"""Usage of the data model measured against the Data Dictionary selection.

The objects picked in the Data Dictionary screen are the ones the reviewer
recognised as actually used by the business. Restricting the snapshot to
them answers a different question from the raw custom-vs-standard
footprint: not "how much was built" but "what does the part that is
actually used look like".

Percentages therefore split the *used* population rather than measuring
how much of the org is covered:

* objects: custom and standard share the same 100 %, so the two lines read
  as "of the objects in use, x % are custom";
* fields: only the fields hanging off standard objects are split, because
  a custom object is custom by construction and its fields would drown the
  ratio that matters, namely how far standard objects were extended.

Custom metadata types stay out of both denominators. They carry
configuration rather than business data, and an org can hold dozens of
them without that saying anything about the usage of its data model.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from src.core.models import MetadataSnapshot, ObjectInfo

CUSTOM_METADATA_SUFFIX = "__mdt"


def is_custom_metadata(obj: ObjectInfo) -> bool:
    """Whether ``obj`` is a custom metadata type rather than a real object."""

    return obj.api_name.endswith(CUSTOM_METADATA_SUFFIX)


@dataclass(slots=True)
class UsageBucket:
    """One "used vs present" line of the *Ce qui est utilise* section."""

    label: str
    used: int = 0
    total: int = 0
    #: Whether the line takes part in the split its table displays. Lines
    #: left out are shown for information only, with no ratio.
    in_percent_base: bool = False


@dataclass(slots=True)
class UsageTable:
    """A table of the section: its lines and the split they share."""

    caption: str
    #: Header of the ratio column, which spells out the denominator.
    percent_caption: str
    total_label: str
    buckets: list[UsageBucket] = field(default_factory=list)

    @property
    def base(self) -> int:
        """Used items the percentages are shares of."""

        return sum(bucket.used for bucket in self.buckets if bucket.in_percent_base)

    def percent(self, bucket: UsageBucket) -> float | None:
        """Share of ``bucket`` in the table split, or ``None`` when excluded."""

        if not bucket.in_percent_base or not self.base:
            return None
        return bucket.used / self.base * 100.0

    @property
    def total(self) -> UsageBucket:
        """Closing line summing every bucket that feeds the split."""

        return UsageBucket(
            self.total_label,
            used=self.base,
            total=sum(
                bucket.total for bucket in self.buckets if bucket.in_percent_base
            ),
            in_percent_base=True,
        )


@dataclass(slots=True)
class SelectedUsageStats:
    """What the Data Dictionary selection looks like inside the snapshot."""

    #: Selected objects found in the snapshot. A selection saved before the
    #: last retrieve can name objects that are gone, and counting those would
    #: contradict the tables below.
    matched_count: int = 0
    objects: UsageTable | None = None
    fields: UsageTable | None = None


def compute_selected_usage_stats(
    snapshot: MetadataSnapshot,
    selected_objects: Iterable[str] | None,
) -> SelectedUsageStats | None:
    """Split the snapshot between selected ("used") and unselected metadata.

    Returns ``None`` when nothing was selected in the Data Dictionary
    screen: there is no usage reference to compare against, and that is how
    the renderer knows to skip the section entirely.
    """

    selected = {str(name) for name in selected_objects or ()}
    if not selected:
        return None

    custom_objects = UsageBucket("Objets custom (__c)", in_percent_base=True)
    standard_objects = UsageBucket("Objets standard", in_percent_base=True)
    custom_metadata = UsageBucket("Custom metadata (__mdt)")

    custom_object_fields = UsageBucket("Champs des objets custom (__c)")
    standard_custom_fields = UsageBucket(
        "Champs custom des objets standard", in_percent_base=True
    )
    standard_standard_fields = UsageBucket(
        "Champs standard des objets standard", in_percent_base=True
    )
    custom_metadata_fields = UsageBucket("Champs des custom metadata (__mdt)")

    matched = 0
    for obj in snapshot.objects:
        used = obj.api_name in selected
        matched += used
        if is_custom_metadata(obj):
            _count(custom_metadata, used)
            _count(custom_metadata_fields, used, len(obj.fields))
        elif obj.custom:
            _count(custom_objects, used)
            _count(custom_object_fields, used, len(obj.fields))
        else:
            _count(standard_objects, used)
            custom_count = sum(1 for fld in obj.fields if fld.custom)
            _count(standard_custom_fields, used, custom_count)
            _count(
                standard_standard_fields, used, len(obj.fields) - custom_count
            )

    return SelectedUsageStats(
        matched_count=matched,
        objects=UsageTable(
            caption="Objets",
            percent_caption="% des objets utilises",
            total_label="Total objets utilises (hors custom metadata)",
            buckets=[custom_objects, standard_objects, custom_metadata],
        ),
        fields=UsageTable(
            caption="Champs",
            percent_caption="% des champs des objets standard utilises",
            total_label="Total champs des objets standard utilises",
            buckets=[
                custom_object_fields,
                standard_custom_fields,
                standard_standard_fields,
                custom_metadata_fields,
            ],
        ),
    )


def _count(bucket: UsageBucket, used: bool, amount: int = 1) -> None:
    bucket.total += amount
    if used:
        bucket.used += amount
