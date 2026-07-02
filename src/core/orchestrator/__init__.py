"""Orchestrate metadata parsing, analysis, and report generation.

The :class:`SalesforceDocumentationGenerator` glues the parsers, analyzers
and writers together. It takes user configuration (output flags, language,
weights, exclusion files) and returns a fully populated
:class:`GenerationResult` so callers can introspect what was produced
without poking at a stringly-typed dictionary.

This package splits the implementation across thematic modules; the public
API (``SalesforceDocumentationGenerator`` and ``GenerationResult``) is
re-exported here so existing ``from src.core.orchestrator import ...`` call
sites keep working unchanged.
"""

from __future__ import annotations

from src.core.orchestrator.base import LogCallback
from src.core.orchestrator.generator import SalesforceDocumentationGenerator
from src.core.orchestrator.result import GenerationResult

__all__ = [
    "GenerationResult",
    "LogCallback",
    "SalesforceDocumentationGenerator",
]
