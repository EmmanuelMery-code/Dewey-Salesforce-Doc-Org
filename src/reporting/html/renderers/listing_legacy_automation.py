"""Listing page for active legacy automation (Process Builder, Workflow Rules, Visualforce pages)."""

from __future__ import annotations

from pathlib import Path

from src.core.models import MetadataSnapshot
from src.core.utils import html_value
from src.reporting.html.page_shell import index_back_link
from src.reporting.html.renderers.listing_tables import LogCallback, _table, _write

# Process Builder est stocke comme un Flow ; ces processType en sont les variantes.
PROCESS_BUILDER_PROCESS_TYPES = frozenset({"Workflow", "CustomEvent", "InvocableProcess"})


def collect_active_legacy_automation(snapshot: MetadataSnapshot) -> list[tuple[str, str, str]]:
    """Return ``(api_name, label, element_type)`` for every active legacy element."""
    items: list[tuple[str, str, str]] = []

    for flow in snapshot.flows:
        if flow.process_type in PROCESS_BUILDER_PROCESS_TYPES and flow.status == "Active":
            items.append((flow.name, flow.label, "Process Builder"))

    for row in snapshot.inventory.get("workflow_rules", []):
        if row.get("Active"):
            rule_name = str(row.get("Regle", ""))
            items.append((f"{row.get('Objet', '')}.{rule_name}", rule_name, "Workflow Rule"))

    for row in snapshot.inventory.get("visualforce_pages", []):
        items.append((str(row.get("Nom", "")), str(row.get("Label", "")), "Page Visualforce"))

    return items


def write_legacy_automation_list_page(
    snapshot: MetadataSnapshot,
    output_dir: Path,
    assets_dir: Path,
    log: LogCallback,
) -> Path | None:
    items = collect_active_legacy_automation(snapshot)
    if not items:
        return None

    path = output_dir / "legacy_automation_list.html"
    back = index_back_link(path, output_dir)

    rows = [
        f"<tr>"
        f"<td>{html_value(api_name)}</td>"
        f"<td>{html_value(label)}</td>"
        f"<td>{html_value(element_type)}</td>"
        f"</tr>"
        for api_name, label, element_type in sorted(items, key=lambda x: (x[2], x[0].lower()))
    ]

    table = _table(["Nom API", "Label", "Type d'élément"], rows)
    body = f"{back}<h1>Automatisations legacy actives ({len(items)})</h1>{table}"
    _write(path, "Automatisations legacy", body, assets_dir)
    log(f"Page liste Automatisations legacy générée : {path}")
    return path
