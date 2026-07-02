"""Salesforce DX metadata parser.

Parses a Salesforce source folder into a :class:`MetadataSnapshot`. The
implementation is split into thematic mixins (exclusion handling, objects,
security, apex, flows, inventory, components, dependencies) assembled by
:class:`SalesforceMetadataParser`. The public API is re-exported here so
existing ``from src.parsers.salesforce_parser import SalesforceMetadataParser``
imports keep working unchanged.
"""

from __future__ import annotations

from src.parsers.salesforce_parser.base import LogCallback
from src.parsers.salesforce_parser.parser import SalesforceMetadataParser

__all__ = ["LogCallback", "SalesforceMetadataParser"]
