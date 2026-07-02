"""Shared state and category aliases for the Salesforce parser mixins.

The parser is split into thematic mixins (exclusion handling, objects,
security, apex, flows, inventory, components, dependencies). They all read the
same instance attributes set in ``SalesforceMetadataParser.__init__``.
Declaring those here (annotations only) gives the mixins a common,
type-checkable base without duplicating the attribute list in every file.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

LogCallback = Callable[[str], None]

# Security risk analysis constants — shared with src.analyzer.security_analyzer
_SEC_DANGEROUS_USER_PERMS: frozenset[str] = frozenset({"ModifyAllData", "ManageUsers"})
_SEC_SENSITIVE_OBJECTS: frozenset[str] = frozenset({
    "Account", "Contact", "Opportunity", "Lead", "Order",
    "Case", "Contract", "User", "Event", "Task",
})


class _ParserState:
    """Instance attributes shared across the parser mixins.

    Values are assigned in ``SalesforceMetadataParser.__init__``; this class
    only carries the annotations (and the shared ``CATEGORY_ALIASES`` table)
    so ``self.*`` accesses inside the mixins resolve for static analysis.
    """

    source_dir: Path
    exclusion_config_path: Path | None
    log: LogCallback
    exclusion_rules: dict[str, list[str]]

    CATEGORY_ALIASES = {
        "all": "all",
        "global": "all",
        "objet": "object",
        "objets": "object",
        "object": "object",
        "objects": "object",
        "apex": "apex",
        "classe": "apex",
        "classes": "apex",
        "trigger": "apex",
        "triggers": "apex",
        "flow": "flow",
        "flows": "flow",
        "lwc": "lwc",
        "agent": "agent",
        "agents": "agent",
        "prompt": "prompt",
        "prompts": "prompt",
        "validation rule": "validation_rule",
        "validation rules": "validation_rule",
        "vr": "validation_rule",
        "omni": "omni",
        "omnistudio": "omni",
        "layout": "layout",
        "layouts": "layout",
        "flexipage": "flexipage",
        "flexipages": "flexipage",
        "lightning page": "flexipage",
        "lightning pages": "flexipage",
        "report": "report",
        "reports": "report",
        "dashboard": "dashboard",
        "dashboards": "dashboard",
        "profile": "profile",
        "profiles": "profile",
        "permission set": "permission_set",
        "permission sets": "permission_set",
        "permset": "permission_set",
        "permsets": "permission_set",
        "tab": "tab",
        "tabs": "tab",
        "application": "application",
        "applications": "application",
        "app": "application",
        "apps": "application",
        "ai_prediction": "ai_prediction",
        "ai_predictions": "ai_prediction",
        "business_rule": "business_rule",
        "business_rules": "business_rule",
        "bre": "business_rule",
        "field": "field",
        "fields": "field",
        "champ": "field",
        "champs": "field",
        "record_type": "record_type",
        "record_types": "record_type",
        "rt": "record_type",
    }
