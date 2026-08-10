"""Scan a :class:`MetadataSnapshot` for AI usage tags.

The "AI usage" indicator counts metadata elements that mention one of the
configured tag values (e.g. ``@IAgenerated``, ``@IAassisted``) in their
description (objects, fields, validation rules, record types, flows, flow
elements, profiles, permission sets) or in source comments (Apex classes
and triggers).

The scanner is intentionally pure: it takes a snapshot plus the list of
tag strings and returns a list of :class:`AIUsageEntry` objects. Rendering
and persistence are handled elsewhere so this module stays trivial to
unit-test.

This module is a thin façade: the scanning logic lives in the sibling
:mod:`ai_usage_scan` module and the customisation-universe helpers live in
:mod:`ai_usage_universe`. Everything is re-exported here so existing
imports (``from src.core.ai_usage import ...``) keep working unchanged.
"""

from __future__ import annotations

from src.core.ai_usage_scan import (
    AIUsageEntry,
    count_unique_elements,
    scan_ai_usage,
)
from src.core.ai_usage_universe import (
    AIUsageStats,
    CustomElement,
    compute_ai_usage_stats,
    enumerate_customization_universe,
)

__all__ = [
    "AIUsageEntry",
    "CustomElement",
    "AIUsageStats",
    "scan_ai_usage",
    "count_unique_elements",
    "enumerate_customization_universe",
    "compute_ai_usage_stats",
]
