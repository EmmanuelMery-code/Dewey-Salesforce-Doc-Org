"""Cartes de synthese affichees sur la page index HTML."""

from __future__ import annotations

from pathlib import Path

from src.core.ai_usage import AIUsageStats
from src.core.customization_metrics import AdoptionStats, DataModelCustomisationStats
from src.core.models import MetadataSnapshot
from src.core.utils import html_value
from src.reporting.html.page_shell import href_relative, tabbed_sections


def render_data_model_card(
    stats: DataModelCustomisationStats | None,
    page_path: Path | None,
    current_path: Path,
) -> str:
    if stats is None or stats.total_objects + stats.total_fields == 0:
        return (
            '  <div class="card adopt-card"><span>Empreinte data model</span>'
            '<span class="value">N/A</span>'
            '<small class="adopt-hint">Mesure non disponible.</small></div>\n'
        )

    custom_count = stats.custom_objects + stats.custom_fields
    standard_count = stats.standard_objects + stats.standard_fields
    total = custom_count + standard_count
    if page_path is not None:
        href = html_value(href_relative(current_path, page_path))
        title_html = f'<a href="{href}">Empreinte data model</a>'
    else:
        title_html = "Empreinte data model"

    return (
        '  <div class="card adopt-card">\n'
        f"    <span>{title_html}</span>\n"
        '    <div class="adopt-grid">\n'
        '      <div class="adopt-stat adopt-stat--adapt">\n'
        '        <span class="adopt-label">Custom</span>\n'
        f'        <span class="value">{custom_count}</span>\n'
        f'        <span class="adopt-percent">{stats.percent_custom_global:.1f} %</span>\n'
        f'        <small class="adopt-hint">{stats.custom_objects} objets, {stats.custom_fields} champs</small>\n'
        "      </div>\n"
        '      <div class="adopt-stat adopt-stat--adopt">\n'
        '        <span class="adopt-label">Standard</span>\n'
        f'        <span class="value">{standard_count}</span>\n'
        f'        <span class="adopt-percent">{stats.percent_standard_global:.1f} %</span>\n'
        f'        <small class="adopt-hint">{stats.standard_objects} objets, {stats.standard_fields} champs</small>\n'
        "      </div>\n"
        "    </div>\n"
        f'    <span class="adopt-hint">Objets+champs analyses : {total}</span>\n'
        "  </div>\n"
    )


def render_adoption_card(
    stats: AdoptionStats | None,
    page_path: Path | None,
    current_path: Path,
) -> str:
    if stats is None or stats.total_count == 0:
        return (
            '  <div class="card adopt-card"><span>Posture Adopt vs Adapt</span>'
            '<span class="value">N/A</span>'
            '<small class="adopt-hint">Mesure non disponible.</small></div>\n'
        )

    if page_path is not None:
        href = html_value(href_relative(current_path, page_path))
        title_html = f'<a href="{href}">Posture Adopt vs Adapt</a>'
    else:
        title_html = "Posture Adopt vs Adapt"

    return (
        '  <div class="card adopt-card">\n'
        f"    <span>{title_html}</span>\n"
        '    <div class="adopt-grid">\n'
        '      <div class="adopt-stat adopt-stat--adopt">\n'
        '        <span class="adopt-label">Adopt</span>\n'
        f'        <span class="value">{stats.adopt_count}</span>\n'
        f'        <span class="adopt-percent">{stats.percent_adoption:.1f} %</span>\n'
        f'        <small class="adopt-hint">No-code (poids {stats.adopt_weight})</small>\n'
        "      </div>\n"
        '      <div class="adopt-stat adopt-stat--adapt">\n'
        '        <span class="adopt-label">Adapt</span>\n'
        f'        <span class="value">{stats.adapt_count}</span>\n'
        f'        <span class="adopt-percent">{stats.percent_adaptation:.1f} %</span>\n'
        f'        <small class="adopt-hint">Low: {stats.adapt_low_count}, Pro: {stats.adapt_high_count} (poids {stats.adapt_weight})</small>\n'
        "      </div>\n"
        "    </div>\n"
        '    <span class="adopt-hint">'
        f"Capacites : {stats.total_count} / poids total {stats.total_weight}"
        "</span>\n"
        "  </div>\n"
    )


def render_ai_usage_card(
    stats: AIUsageStats | None,
    page_path: Path | None,
    current_path: Path,
) -> str:
    if stats is None:
        return (
            '  <div class="card ai-usage-card"><span>Usage IA</span>'
            '<span class="value">N/A</span>'
            '<small class="ai-usage-hint">Mesure non disponible.</small></div>\n'
        )

    if page_path is not None:
        href = html_value(href_relative(current_path, page_path))
        title_html = f'<a href="{href}">Usage IA</a>'
    else:
        title_html = "Usage IA"

    return (
        '  <div class="card ai-usage-card">\n'
        f"    <span>{title_html}</span>\n"
        '    <div class="ai-usage-grid">\n'
        '      <div class="ai-usage-stat ai-usage-stat--with">\n'
        '        <span class="ai-usage-label">Avec tag</span>\n'
        f'        <span class="value">{stats.with_tag_count}</span>\n'
        f'        <span class="ai-usage-percent">{stats.percent_with_tag:.1f} %</span>\n'
        "      </div>\n"
        '      <div class="ai-usage-stat ai-usage-stat--without">\n'
        '        <span class="ai-usage-label">Sans tag</span>\n'
        f'        <span class="value">{stats.without_tag_count}</span>\n'
        f'        <span class="ai-usage-percent">{stats.percent_without_tag:.1f} %</span>\n'
        "      </div>\n"
        "    </div>\n"
        f'    <span class="ai-usage-hint">Total customs : {stats.total}</span>\n'
        "  </div>\n"
    )


def render_debt_card(
    snapshot: MetadataSnapshot,
    page_path: Path | None,
    current_path: Path,
) -> str:
    debt_count = len(snapshot.technical_debt)
    deviation_count = len(snapshot.deviations)

    if page_path is not None:
        href = html_value(href_relative(current_path, page_path))
        title_html = f'<a href="{href}">Dette technique & Entorse et PR</a>'
        debt_link = f'<a href="{href}" style="color: inherit; text-decoration: none;">{debt_count}</a>'
        deviation_link = f'<a href="{href}" style="color: inherit; text-decoration: none;">{deviation_count}</a>'
    else:
        title_html = "Dette technique & Entorse et PR"
        debt_link = str(debt_count)
        deviation_link = str(deviation_count)

    return (
        '  <div class="card adopt-card">\n'
        f"    <span>{title_html}</span>\n"
        '    <div class="adopt-grid">\n'
        '      <div class="adopt-stat adopt-stat--adapt">\n'
        '        <span class="adopt-label">Dette technique</span>\n'
        f'        <span class="value">{debt_link}</span>\n'
        "      </div>\n"
        '      <div class="adopt-stat adopt-stat--adapt" style="border-left: 1px solid #e2e8f0;">\n'
        '        <span class="adopt-label">Entorses et PR</span>\n'
        f'        <span class="value">{deviation_link}</span>\n'
        "      </div>\n"
        "    </div>\n"
        "  </div>\n"
    )


def render_innovation_card(
    snapshot: MetadataSnapshot,
    page_path: Path | None,
    current_path: Path,
) -> str:
    total_count = len(snapshot.innovations)
    not_started_count = len([item for item in snapshot.innovations if item.not_started])
    started_count = total_count - not_started_count

    if page_path is not None:
        href = html_value(href_relative(current_path, page_path))
        title_html = f'<a href="{href}">POC et Innovation</a>'
        started_link = f'<a href="{href}" style="color: inherit; text-decoration: none;">{started_count}</a>'
        not_started_link = f'<a href="{href}" style="color: inherit; text-decoration: none;">{not_started_count}</a>'
        total_link = f'<a href="{href}" style="color: inherit; text-decoration: none;">{total_count}</a>'
    else:
        title_html = "POC et Innovation"
        started_link = str(started_count)
        not_started_link = str(not_started_count)
        total_link = str(total_count)

    return (
        '  <div class="card adopt-card">\n'
        f"    <span>{title_html}</span>\n"
        '    <div class="adopt-grid">\n'
        '      <div class="adopt-stat adopt-stat--adapt">\n'
        '        <span class="adopt-label">En cours ou Terminés</span>\n'
        f'        <span class="value">{started_link}</span>\n'
        "      </div>\n"
        '      <div class="adopt-stat adopt-stat--adapt" style="border-left: 1px solid #e2e8f0;">\n'
        '        <span class="adopt-label">Non Commencé</span>\n'
        f'        <span class="value">{not_started_link}</span>\n'
        "      </div>\n"
        '      <div class="adopt-stat adopt-stat--adapt" style="border-left: 1px solid #e2e8f0;">\n'
        '        <span class="adopt-label">Total</span>\n'
        f'        <span class="value">{total_link}</span>\n'
        "      </div>\n"
        "    </div>\n"
        "  </div>\n"
    )


def render_picklists_card(
    snapshot: MetadataSnapshot,
    page_path: Path | None,
    current_path: Path,
) -> str:
    picklist_count = sum(
        1
        for obj in snapshot.objects
        for item in obj.fields
        if item.data_type in ("Picklist", "MultiselectPicklist")
    )
    global_count = sum(
        1 for obj in snapshot.objects for item in obj.fields if item.picklist_is_global
    )

    if page_path is not None:
        href = html_value(href_relative(current_path, page_path))
        title_html = f'<a href="{href}" style="color: inherit; text-decoration: none;">Champs Picklist</a>'
        picklist_link = f'<a href="{href}" style="color: inherit; text-decoration: none;">{picklist_count}</a>'
        global_link = f'<a href="{href}" style="color: inherit; text-decoration: none;">{global_count}</a>'
    else:
        title_html = "Champs Picklist"
        picklist_link = str(picklist_count)
        global_link = str(global_count)

    return (
        '  <div class="card adopt-card">\n'
        f"    <span>{title_html}</span>\n"
        '    <div class="adopt-grid">\n'
        '      <div class="adopt-stat adopt-stat--adapt" style="background: transparent;">\n'
        '        <span class="adopt-label">Champs Picklist</span>\n'
        f'        <span class="value">{picklist_link}</span>\n'
        "      </div>\n"
        '      <div class="adopt-stat adopt-stat--adapt" style="background: transparent; border-left: 1px solid #e2e8f0;">\n'
        '        <span class="adopt-label">Picklists Globales</span>\n'
        f'        <span class="value">{global_link}</span>\n'
        "      </div>\n"
        "    </div>\n"
        "  </div>\n"
    )


def render_summary_tabs(
    *,
    description_cards: list[str],
    scoring_cards: list[str],
    metric_cards: list[str],
    ia_business_cards: list[str],
    ia_admin_card: str,
) -> str:
    """Assemble les cartes de synthese en onglets."""
    sections: list[tuple[str, str]] = []
    desc_content = "".join(description_cards)
    if desc_content.strip():
        sections.append(("Description", f'<div class="cards">{desc_content}</div>'))

    scoring_content = "".join(scoring_cards)
    if scoring_content.strip():
        sections.append(("Scoring", f'<div class="cards">{scoring_content}</div>'))

    metrics_content = "".join(metric_cards)
    if metrics_content.strip():
        sections.append(("Metriques", f'<div class="cards">{metrics_content}</div>'))

    ia_content = ""
    ia_business_content = "".join(ia_business_cards)
    if ia_business_content.strip():
        ia_content += f'<h3>IA pour le metier</h3><div class="cards">{ia_business_content}</div>'
    if ia_admin_card.strip():
        ia_content += f'<h3>IA pour les Admin et dev</h3><div class="cards">{ia_admin_card}</div>'
    if ia_content:
        sections.append(("IA", ia_content))

    return tabbed_sections("summary-tabs", sections) if sections else ""
