"""Data-model customisation statistics (approach A).

Quantifies the *data model footprint* by comparing custom objects/fields
to the standard ones present in the snapshot.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.core.models import MetadataSnapshot


@dataclass(slots=True)
class DataModelCustomisationStats:
    """Counts of standard vs custom items in the snapshot data model.

    The denominator combines objects and fields because, on Salesforce, a
    "100 % custom" answer can come either from many custom objects or
    from many custom fields hanging off a standard object: showing the
    two breakdowns side by side avoids the misleading impression that
    one alone tells the whole story.
    """

    custom_objects: int = 0
    standard_objects: int = 0
    custom_fields: int = 0
    standard_fields: int = 0

    @property
    def total_objects(self) -> int:
        return self.custom_objects + self.standard_objects

    @property
    def total_fields(self) -> int:
        return self.custom_fields + self.standard_fields

    @property
    def percent_custom_objects(self) -> float:
        return (
            self.custom_objects / self.total_objects * 100.0
            if self.total_objects
            else 0.0
        )

    @property
    def percent_custom_fields(self) -> float:
        return (
            self.custom_fields / self.total_fields * 100.0
            if self.total_fields
            else 0.0
        )

    @property
    def percent_custom_global(self) -> float:
        """Global ratio = (custom_objects + custom_fields) / (total + total).

        Treats every object and every field as a single "data model unit".
        Objects therefore count more than they would in a simple field
        ratio, which feels right because adding a custom object is a
        much heavier customisation than adding one field.
        """

        custom = self.custom_objects + self.custom_fields
        total = self.total_objects + self.total_fields
        return custom / total * 100.0 if total else 0.0

    @property
    def percent_standard_global(self) -> float:
        return 100.0 - self.percent_custom_global if self.total_objects + self.total_fields else 0.0


def compute_data_model_stats(snapshot: MetadataSnapshot) -> DataModelCustomisationStats:
    """Aggregate the snapshot's objects and fields into custom/standard counts."""

    stats = DataModelCustomisationStats()
    for obj in snapshot.objects:
        if obj.custom:
            stats.custom_objects += 1
        else:
            stats.standard_objects += 1
        for fld in obj.fields:
            if fld.custom:
                stats.custom_fields += 1
            else:
                stats.standard_fields += 1
    return stats
