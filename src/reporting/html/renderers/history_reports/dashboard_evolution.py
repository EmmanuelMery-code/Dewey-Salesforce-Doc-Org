"""Computes the release-over-release evolution charts for the history dashboard."""

from __future__ import annotations

from src.core.history_service import HistoryEntry
from src.reporting.html.renderers.history_reports.dashboard_charts import (
    _render_evolution_chart,
)


def build_evolution_charts(
    sorted_history: list[HistoryEntry],
    show_evolution_tables: bool,
) -> dict[str, str]:
    """Return the evolution bar charts (and optional tables) for each metric family."""
    # Adoption Evolution
    adoption_data = []
    for e in sorted_history:
        adoption_data.append({
            "label": f"R{e.generation_number}",
            "adoption": e.adoption_pct,
            "adaptation": e.adaptation_pct
        })

    adoption_evolution_bars = _render_evolution_chart(
        "Adoption vs Adaptation",
        [dict(d) for d in adoption_data],
        {"adoption": "#68b36b", "adaptation": "#e5534b"}
    )

    adoption_table = ""
    if show_evolution_tables:
        rows = ""
        for d in adoption_data:
            rows += f"<tr><th>{d['label']}</th><td>{d['adoption']:.1f}%</td><td>{d['adaptation']:.1f}%</td></tr>"
        adoption_table = f"""
            <table class="dashboard-table">
                <tr><th></th><th>adoption</th><th>adaptation</th></tr>
                {rows}
            </table>
        """

    # Data Model Evolution
    dm_data = []
    for e in sorted_history:
        dm_data.append({
            "label": f"R{e.generation_number}",
            "standard": e.data_model_standard_pct,
            "custom": e.data_model_custom_pct
        })

    dm_evolution_bars = _render_evolution_chart(
        "Data Model standard vs custom",
        [dict(d) for d in dm_data],
        {"standard": "#68b36b", "custom": "#e5534b"}
    )

    dm_table = ""
    if show_evolution_tables:
        rows = ""
        for d in dm_data:
            rows += f"<tr><th>{d['label']}</th><td>{d['standard']:.1f}%</td><td>{d['custom']:.1f}%</td></tr>"
        dm_table = f"""
            <table class="dashboard-table">
                <tr><th></th><th>standard</th><th>custom</th></tr>
                {rows}
            </table>
        """

    # AI Usage Evolution
    ai_data = []
    for e in sorted_history:
        ai_data.append({
            "label": f"R{e.generation_number}",
            "avec IA": e.ai_usage_pct,
            "sans IA": 100.0 - e.ai_usage_pct
        })

    ai_evolution_bars = _render_evolution_chart(
        "Usage de l'IA",
        [dict(d) for d in ai_data],
        {"avec IA": "#68b36b", "sans IA": "#e5534b"}
    )

    ai_table = ""
    if show_evolution_tables:
        rows = ""
        for d in ai_data:
            rows += f"<tr><th>{d['label']}</th><td>{d['avec IA']:.1f}%</td><td>{d['sans IA']:.1f}%</td></tr>"
        ai_table = f"""
            <table class="dashboard-table">
                <tr><th></th><th>avec IA</th><th>sans IA</th></tr>
                {rows}
            </table>
        """

    # Findings Evolution
    findings_data = []
    max_total_f = max([e.findings_total for e in sorted_history] + [1])
    for e in sorted_history:
        findings_data.append({
            "label": f"R{e.generation_number}",
            "Critique": e.findings_critical,
            "Majeur": e.findings_major,
            "Mineur": e.findings_minor,
            "Info": e.findings_info
        })

    findings_evolution_bars = _render_evolution_chart(
        "Analyzer Findings",
        [dict(d) for d in findings_data],
        {"Critique": "#e53e3e", "Majeur": "#ed8936", "Mineur": "#ecc94b", "Info": "#48bb78"}
    )

    # Test Coverage Evolution
    coverage_data = []
    for e in sorted_history:
        coverage_data.append({
            "label": f"R{e.generation_number}",
            "couverture": e.test_coverage if e.test_coverage is not None else 0.0
        })

    coverage_evolution_bars = _render_evolution_chart(
        "Couverture de tests",
        [dict(d) for d in coverage_data],
        {"couverture": "#3b82f6"}
    )

    findings_table = ""
    if show_evolution_tables:
        rows = ""
        for d in findings_data:
            rows += f"<tr><th>{d['label']}</th><td>{d['Critique']}</td><td>{d['Majeur']}</td><td>{d['Mineur']}</td><td>{d['Info']}</td></tr>"
        findings_table = f"""
            <table class="dashboard-table">
                <tr><th></th><th>Critique</th><th>Majeur</th><th>Mineur</th><th>Info</th></tr>
                {rows}
            </table>
        """

    return {
        "adoption_evolution_bars": adoption_evolution_bars,
        "adoption_table": adoption_table,
        "dm_evolution_bars": dm_evolution_bars,
        "dm_table": dm_table,
        "ai_evolution_bars": ai_evolution_bars,
        "ai_table": ai_table,
        "findings_evolution_bars": findings_evolution_bars,
        "findings_table": findings_table,
        "coverage_evolution_bars": coverage_evolution_bars,
    }
