"""Agentforce ``.agent`` (YAML-ish) file parsing helper."""

from __future__ import annotations

import re
from pathlib import Path

_AGENT_LABEL_RE = re.compile(r"agent_label\s*:\s*['\"]?([^'\"\n]+)['\"]?", re.IGNORECASE)
_AGENT_TYPE_RE = re.compile(r"agent_type\s*:\s*['\"]?([^'\"\n]+)['\"]?", re.IGNORECASE)
_AGENT_DESC_RE = re.compile(r"description\s*:\s*['\"]?([^'\"\n]+)['\"]?", re.IGNORECASE)
_AGENT_DEV_NAME_RE = re.compile(r"developer_name\s*:\s*['\"]?([^'\"\n]+)['\"]?", re.IGNORECASE)


def _parse_dot_agent_file(path: Path) -> tuple[str, str, str, str]:
    """Parse a Salesforce Agentforce ``.agent`` file (YAML-ish format).

    Returns ``(name, label, description, agent_type)``.  Falls back to the
    file stem when a field cannot be extracted.
    """
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        stem = path.stem
        return stem, stem, "", ""

    def _extract(pattern: re.Pattern) -> str:
        m = pattern.search(text)
        return m.group(1).strip() if m else ""

    # The folder / file stem is the API name of the bundle (unique per org).
    # The developer_name inside the file can differ (e.g. duplicate bundles),
    # so we use the stem as the canonical name.
    name = path.stem
    label = _extract(_AGENT_LABEL_RE) or _extract(_AGENT_DEV_NAME_RE) or name
    description = _extract(_AGENT_DESC_RE)
    agent_type = _extract(_AGENT_TYPE_RE)
    return name, label, description, agent_type
