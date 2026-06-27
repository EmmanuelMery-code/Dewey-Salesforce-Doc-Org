"""Construction de la legende dynamique One Page."""

from __future__ import annotations


def build_one_page_legend_html(
    nodes: list[dict[str, object]], center_name: str
) -> str:
    """Retourne les entrees de legende correspondant aux categories presentes."""
    present_categories = {
        node.get("category")
        for node in nodes
        if node.get("id") != center_name
    }
    legend_items = [
        ("Apex", "#dbeafe", "Apex"),
        ("Objet", "#dcfce7", "Objets"),
        ("Field", "#fef9c3", "Champs"),
        ("LWC", "#cffafe", "LWC"),
        ("Aura", "#e0e7ff", "Aura"),
        ("Report", "#fae8ff", "Rapports"),
        ("Metadata", "#f3e8ff", "Metadata"),
    ]
    legend_toggles = "".join(
        f'\n  <span class="item legend-toggle" data-category="{category}" '
        f'role="button" tabindex="0" title="Masquer / afficher : {label}">'
        f'<span class="dot" style="background:{color}"></span>{label}</span>'
        for category, color, label in legend_items
        if category in present_categories
    )
    active_flow_legend = (
        '\n  <span class="item legend-toggle" data-flow-state="active" '
        'role="button" tabindex="0" title="Masquer / afficher : Flows actifs">'
        '<span class="dot" style="background:#ffedd5"></span>Flows</span>'
        if any(
            node.get("category") == "Flow" and not node.get("isInactiveFlow")
            for node in nodes
            if node.get("id") != center_name
        )
        else ""
    )
    inactive_flow_legend = (
        '\n  <span class="item legend-toggle" data-flow-state="inactive" '
        'role="button" tabindex="0" title="Masquer / afficher : Flows inactifs">'
        '<span class="dot" style="background:repeating-linear-gradient(135deg,#ffedd5 0,#ffedd5 4px,#fdba74 4px,#fdba74 6px)"></span>'
        'Flow inactif</span>'
        if any(
            node.get("isInactiveFlow")
            for node in nodes
            if node.get("id") != center_name
        )
        else ""
    )
    return legend_toggles + active_flow_legend + inactive_flow_legend
