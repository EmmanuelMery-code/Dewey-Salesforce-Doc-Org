"""Flow ``processType`` exclusions for the test-coverage calculation (Mode A only).

Screen flows (``processType == "Flow"`` in the Flow metadata) are, by
default, excluded from the org-level test coverage average: they are
typically validated through manual UI testing rather than by an Apex/Flow
test class, so folding them into the average tends to understate the real
coverage of the flows that actually can be covered by a test class
(autolaunched, record-triggered, scheduled, ...).

The exclusion list is stored as a new ``flow_coverage_exclusions`` key in
the same JSON file already used for metadata/rule exclusions (see
:mod:`src.ui.exclusion_screen`), so the user manages a single exclusion
file. This module is only used by Mode A (desktop app); Mode B (headless
Salesforce skill) is untouched and keeps its previous, unfiltered
behaviour.
"""

from __future__ import annotations

import json
from pathlib import Path

# Raw Salesforce Flow ``processType`` values that can be excluded, in
# display order, paired with the translation key used to show a friendly
# label in the UI (see the "flow_process_type_*" entries in
# src/ui/translations/fr_part2.py and en_part2.py).
FLOW_PROCESS_TYPE_OPTIONS: tuple[tuple[str, str], ...] = (
    ("Flow", "flow_process_type_screen_flow"),
    ("AutoLaunchedFlow", "flow_process_type_autolaunched_flow"),
    ("Workflow", "flow_process_type_workflow"),
    ("CustomEvent", "flow_process_type_platform_event"),
    ("InvocableProcess", "flow_process_type_invocable_process"),
    ("Survey", "flow_process_type_survey"),
    ("Orchestrator", "flow_process_type_orchestrator"),
    ("ActionCadenceAutolaunchedFlow", "flow_process_type_action_cadence"),
    ("LoginFlow", "flow_process_type_login_flow"),
    ("CheckoutFlow", "flow_process_type_checkout_flow"),
)

# Screen flows are excluded out of the box (see module docstring).
DEFAULT_EXCLUDED_FLOW_PROCESS_TYPES: frozenset[str] = frozenset({"Flow"})

_CONFIG_KEY = "flow_coverage_exclusions"


def load_flow_coverage_exclusions(config_path: Path | None) -> set[str]:
    """Return the set of Flow ``processType`` values excluded from coverage.

    Falls back to :data:`DEFAULT_EXCLUDED_FLOW_PROCESS_TYPES` whenever no
    exclusion file is configured, the file doesn't exist yet, or the
    ``flow_coverage_exclusions`` key has never been saved to it — so the
    default behaviour (screen flows excluded) applies out of the box,
    without any manual setup.
    """
    if config_path is None or not config_path.exists():
        return set(DEFAULT_EXCLUDED_FLOW_PROCESS_TYPES)

    data = _read_json_multi_encoding(config_path)
    if _CONFIG_KEY not in data:
        return set(DEFAULT_EXCLUDED_FLOW_PROCESS_TYPES)

    raw = data.get(_CONFIG_KEY)
    if not isinstance(raw, list):
        return set(DEFAULT_EXCLUDED_FLOW_PROCESS_TYPES)
    return {str(item).strip() for item in raw if str(item).strip()}


def save_flow_coverage_exclusions(config_path: Path, excluded_types: set[str]) -> None:
    """Persist ``excluded_types`` under ``flow_coverage_exclusions`` in ``config_path``.

    Preserves any other top-level key already present in the file
    (``metadata_exclusions``, ``rule_exclusions``, ...) so this screen can
    share the same JSON file as the existing exclusion screen without
    clobbering its data.
    """
    data: dict = {}
    if config_path.exists():
        data = _read_json_multi_encoding(config_path)

    data[_CONFIG_KEY] = sorted(str(item) for item in excluded_types)

    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _read_json_multi_encoding(path: Path) -> dict:
    """Best-effort JSON read tolerating utf-8/utf-16/latin-1 encodings.

    Mirrors the loading logic already used by
    :class:`src.parsers.salesforce_parser.exclusion_mixin._ExclusionMixin`
    and :mod:`src.ui.exclusion_screen`, so all three call sites tolerate the
    same set of encodings for this shared file.
    """
    for encoding in ("utf-8", "utf-16", "latin-1"):
        try:
            with open(path, "r", encoding=encoding) as f:
                content = f.read()
        except (UnicodeDecodeError, LookupError):
            continue
        if not content.strip():
            return {}
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            continue
    return {}
