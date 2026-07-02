"""Shared regexes for dependency scanning."""

from __future__ import annotations

import re

_METADATA_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*__mdt)\b")
