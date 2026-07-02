"""Printable A4 dashboard renderer for a selected history entry."""

from __future__ import annotations

from pathlib import Path

from src.core.history_service import HistoryEntry
from src.core.utils import html_value
from src.reporting.html.page_shell import href_relative, index_back_link


def render_dashboard(
    selected: HistoryEntry,
    history: list[HistoryEntry],
    current_path: Path,
    assets_dir: Path,
) -> str:
    """Render a printable A4 dashboard with current status and evolution trend."""

    def _get_pie_css(val1: float, color1: str, color2: str) -> str:
        """Generate CSS for a simple pie chart using conic-gradient."""
        return f"background: conic-gradient({color1} 0% {val1}%, {color2} {val1}% 100%);"

    # Calculations for Status (Selected Generation)
    adoption_pct = selected.adoption_pct
    adaptation_pct = selected.adaptation_pct
    dm_standard_pct = selected.data_model_standard_pct
    dm_custom_pct = selected.data_model_custom_pct
    ai_with_pct = selected.ai_usage_pct
    ai_without_pct = 100.0 - ai_with_pct

    # Findings totals
    f_total = selected.findings_total
    f_crit = selected.findings_critical
    f_maj = selected.findings_major
    f_min = selected.findings_minor
    f_inf = selected.findings_info

    # Max finding for bar scaling
    max_f = max(f_crit, f_maj, f_min, f_inf, 1)

    # Test Coverage
    test_coverage = selected.test_coverage
    test_coverage_pct = test_coverage if test_coverage is not None else 0.0

    # Evolution data: sort history by generation number ascending
    sorted_history = sorted(history, key=lambda e: e.generation_number)

    # Heuristic: if we have more than 5 releases, the tables might make the page too long
    # especially when printing on A4.
    show_evolution_tables = len(sorted_history) <= 5

    def _render_evolution_chart(title: str, data_points: list[dict], colors: dict) -> str:
        bars = ""
        # Filter out non-numeric values (like 'label') before finding max
        numeric_values = []
        for p in data_points:
            numeric_values.extend([v for k, v in p.items() if k != "label" and isinstance(v, (int, float))])
        max_val = max(numeric_values + [1])

        for p in data_points:
            label = p.get("label", "")
            bar_group = ""
            for key, val in p.items():
                if key == "label" or not isinstance(val, (int, float)):
                    continue
                height = (val / max_val) * 100 if max_val > 0 else 0
                color = colors.get(key, "#cbd5e0")
                bar_group += f'<div class="bar" style="background-color: {color}; height: {height}%; width: 15px;" title="{key}: {val}"></div>'

            bars += f"""
                <div class="bar-group" style="flex-direction: row; gap: 2px; align-items: flex-end; justify-content: center;">
                    {bar_group}
                    <div class="bar-label">{label}</div>
                </div>
            """
        return bars

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

    html_content = f"""
    <style>
        /* Inlined CSS for Dashboard to ensure it works even if assets fail */
        .dashboard-page {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            color: #1a202c;
            line-height: 1.4;
            max-width: 1000px;
            margin: 0 auto;
            padding: 20px;
            background: white;
        }}
        .dashboard-header {{
            text-align: center;
            border-bottom: 2px solid #2d3748;
            margin-bottom: 20px;
            padding-bottom: 10px;
        }}
        .dashboard-header h1 {{ margin: 0; font-size: 24px; color: #2d3748; }}
        .dashboard-header p {{ margin: 5px 0 0; color: #718096; font-size: 14px; }}
        .dashboard-grid {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 20px;
            margin-bottom: 20px;
        }}
        .dashboard-card {{
            background: white;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            padding: 15px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }}
        .dashboard-card h3 {{
            margin: 0 0 15px 0;
            font-size: 16px;
            text-align: center;
            color: #4a5568;
            border-bottom: 1px solid #edf2f7;
            padding-bottom: 8px;
        }}
        .chart-container {{
            height: 180px;
            display: flex;
            align-items: center;
            justify-content: center;
            position: relative;
        }}
        .pie-chart {{
            width: 120px;
            height: 120px;
            border-radius: 50%;
            position: relative;
        }}
        .chart-legend {{
            display: flex;
            justify-content: center;
            gap: 15px;
            margin-top: 10px;
            font-size: 12px;
        }}
        .legend-item {{ display: flex; align-items: center; gap: 5px; }}
        .legend-dot {{ width: 10px; height: 10px; border-radius: 50%; }}
        .dashboard-table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
            font-size: 12px;
        }}
        .dashboard-table th, .dashboard-table td {{
            border: 1px solid #e2e8f0;
            padding: 6px 8px;
            text-align: center;
        }}
        .dashboard-table th {{ background: #f7fafc; font-weight: 600; }}
        .bar-chart {{
            display: flex;
            align-items: flex-end;
            gap: 10px;
            height: 120px;
            padding-bottom: 20px;
            border-bottom: 1px solid #cbd5e0;
            margin: 0 20px;
            width: 100%;
        }}
        .bar-group {{
            flex: 1;
            display: flex;
            flex-direction: column;
            align-items: center;
            height: 100%;
            justify-content: flex-end;
            position: relative;
        }}
        .bar {{
            width: 30px;
            border-radius: 4px 4px 0 0;
            transition: height 0.3s;
        }}
        .bar-label {{
            position: absolute;
            bottom: -20px;
            font-size: 10px;
            white-space: nowrap;
        }}
        .bar-value {{ font-size: 10px; margin-bottom: 2px; }}
        .color-adoption {{ background-color: #68b36b; }}
        .color-adaptation {{ background-color: #e5534b; }}
        .color-standard {{ background-color: #68b36b; }}
        .color-custom {{ background-color: #e5534b; }}
        .color-ai-with {{ background-color: #68b36b; }}
        .color-ai-without {{ background-color: #e5534b; }}
        .color-critique {{ background-color: #e53e3e; }}
        .color-majeur {{ background-color: #ed8936; }}
        .color-mineur {{ background-color: #ecc94b; }}
        .color-info {{ background-color: #48bb78; }}
        .color-coverage {{ background-color: #3b82f6; }}
        
        @media print {{
            .no-print {{ display: none !important; }}
            body {{ background: white !important; }}
            .dashboard-page {{ padding: 0; width: 100%; }}
            .page-break {{ page-break-before: always; }}
        }}
    </style>
    <div class="dashboard-page">
        {index_back_link(current_path, current_path.parent)}
        
        <div class="dashboard-header">
            <h1>Status de la release : {html_value(selected.alias)}</h1>
            <p>Génération #{selected.generation_number} - {selected.timestamp}</p>
        </div>

        <div class="dashboard-grid">
            <!-- Adoption vs Adaptation -->
            <div class="dashboard-card">
                <h3>Adoption vs Adaptation</h3>
                <div class="chart-container">
                    <div class="pie-chart" style="{_get_pie_css(adoption_pct, '#68b36b', '#e5534b')}"></div>
                </div>
                <div class="chart-legend">
                    <div class="legend-item"><div class="legend-dot color-adoption"></div> Adoption {adoption_pct:.1f}%</div>
                    <div class="legend-item"><div class="legend-dot color-adaptation"></div> Adaptation {adaptation_pct:.1f}%</div>
                </div>
                <table class="dashboard-table">
                    <tr><th>Adoption</th><td>{adoption_pct:.1f}%</td></tr>
                    <tr><th>Adaptation</th><td>{adaptation_pct:.1f}%</td></tr>
                </table>
            </div>

            <!-- Data Model -->
            <div class="dashboard-card">
                <h3>Data Model Adoption vs Adaptation</h3>
                <div class="chart-container">
                    <div class="pie-chart" style="{_get_pie_css(dm_standard_pct, '#68b36b', '#e5534b')}"></div>
                </div>
                <div class="chart-legend">
                    <div class="legend-item"><div class="legend-dot color-standard"></div> Standard {dm_standard_pct:.1f}%</div>
                    <div class="legend-item"><div class="legend-dot color-custom"></div> Custom {dm_custom_pct:.1f}%</div>
                </div>
                <table class="dashboard-table">
                    <tr><th>Standard</th><td>{dm_standard_pct:.1f}%</td></tr>
                    <tr><th>Custom</th><td>{dm_custom_pct:.1f}%</td></tr>
                </table>
            </div>

            <!-- AI Usage -->
            <div class="dashboard-card">
                <h3>Usage de l'IA</h3>
                <div class="chart-container">
                    <div class="pie-chart" style="{_get_pie_css(ai_with_pct, '#68b36b', '#e5534b')}"></div>
                </div>
                <div class="chart-legend">
                    <div class="legend-item"><div class="legend-dot color-ai-with"></div> Construit avec IA {ai_with_pct:.1f}%</div>
                    <div class="legend-item"><div class="legend-dot color-ai-without"></div> Construit sans IA {ai_without_pct:.1f}%</div>
                </div>
                <table class="dashboard-table">
                    <tr><th>Avec IA</th><td>{ai_with_pct:.1f}%</td></tr>
                    <tr><th>Sans IA</th><td>{ai_without_pct:.1f}%</td></tr>
                </table>
            </div>

            <!-- Findings -->
            <div class="dashboard-card">
                <h3>Analyzer Findings</h3>
                <div class="chart-container">
                    <div class="bar-chart">
                        <div class="bar-group">
                            <div class="bar-value">{f_crit}</div>
                            <div class="bar color-critique" style="height: {(f_crit/max_f)*100}%;"></div>
                            <div class="bar-label">Critique</div>
                        </div>
                        <div class="bar-group">
                            <div class="bar-value">{f_maj}</div>
                            <div class="bar color-majeur" style="height: {(f_maj/max_f)*100}%;"></div>
                            <div class="bar-label">Majeur</div>
                        </div>
                        <div class="bar-group">
                            <div class="bar-value">{f_min}</div>
                            <div class="bar color-mineur" style="height: {(f_min/max_f)*100}%;"></div>
                            <div class="bar-label">Mineur</div>
                        </div>
                        <div class="bar-group">
                            <div class="bar-value">{f_inf}</div>
                            <div class="bar color-info" style="height: {(f_inf/max_f)*100}%;"></div>
                            <div class="bar-label">Info</div>
                        </div>
                    </div>
                </div>
                <table class="dashboard-table">
                    <thead>
                        <tr><th>Critique</th><th>Majeur</th><th>Mineur</th><th>Info</th></tr>
                    </thead>
                    <tbody>
                        <tr><td>{f_crit}</td><td>{f_maj}</td><td>{f_min}</td><td>{f_inf}</td></tr>
                        <tr><th colspan="2">Total</th><td colspan="2"><strong>{f_total}</strong></td></tr>
                    </tbody>
                </table>
            </div>

            <!-- Test Coverage -->
            <div class="dashboard-card">
                <h3>Couverture de tests</h3>
                <div class="chart-container">
                    <div class="pie-chart" style="{_get_pie_css(test_coverage_pct, '#3b82f6', '#e5e7eb')}"></div>
                </div>
                <div class="chart-legend">
                    <div class="legend-item"><div class="legend-dot color-coverage"></div> Couvert {test_coverage_pct:.1f}%</div>
                </div>
                <table class="dashboard-table">
                    <tr><th>Couverture</th><td>{test_coverage_pct:.1f}%</td></tr>
                </table>
            </div>
        </div>

        <div class="page-break"></div>

        <div class="dashboard-header" style="margin-top: 20px;">
            <h1>Evolution des releases : {html_value(selected.alias)}</h1>
        </div>

        <div class="dashboard-grid">
            <!-- Evolution Adoption -->
            <div class="dashboard-card">
                <h3>Adoption and Adaptation</h3>
                <div class="chart-container">
                    <div class="bar-chart">
                        {adoption_evolution_bars}
                    </div>
                </div>
                <div class="chart-legend">
                    <div class="legend-item"><div class="legend-dot color-adoption"></div> adoption</div>
                    <div class="legend-item"><div class="legend-dot color-adaptation"></div> adaptation</div>
                </div>
                {adoption_table}
            </div>

            <!-- Evolution Data Model -->
            <div class="dashboard-card">
                <h3>Data Model standard vs custom</h3>
                <div class="chart-container">
                    <div class="bar-chart">
                        {dm_evolution_bars}
                    </div>
                </div>
                <div class="chart-legend">
                    <div class="legend-item"><div class="legend-dot color-standard"></div> standard</div>
                    <div class="legend-item"><div class="legend-dot color-custom"></div> custom</div>
                </div>
                {dm_table}
            </div>

            <!-- Evolution AI -->
            <div class="dashboard-card">
                <h3>Construit Avec ou Sans IA</h3>
                <div class="chart-container">
                    <div class="bar-chart">
                        {ai_evolution_bars}
                    </div>
                </div>
                <div class="chart-legend">
                    <div class="legend-item"><div class="legend-dot color-ai-with"></div> avec IA</div>
                    <div class="legend-item"><div class="legend-dot color-ai-without"></div> sans IA</div>
                </div>
                {ai_table}
            </div>

            <!-- Evolution Findings -->
            <div class="dashboard-card">
                <h3>Analyzer Findings</h3>
                <div class="chart-container">
                    <div class="bar-chart">
                        {findings_evolution_bars}
                    </div>
                </div>
                <div class="chart-legend">
                    <div class="legend-item"><div class="legend-dot color-critique"></div> Critique</div>
                    <div class="legend-item"><div class="legend-dot color-majeur"></div> Majeur</div>
                    <div class="legend-item"><div class="legend-dot color-mineur"></div> Mineur</div>
                    <div class="legend-item"><div class="legend-dot color-info"></div> Info</div>
                </div>
                {findings_table}
            </div>

            <!-- Evolution Coverage -->
            <div class="dashboard-card">
                <h3>Couverture de tests</h3>
                <div class="chart-container">
                    <div class="bar-chart">
                        {coverage_evolution_bars}
                    </div>
                </div>
                <div class="chart-legend">
                    <div class="legend-item"><div class="legend-dot color-coverage"></div> couverture</div>
                </div>
            </div>
        </div>
    </div>
    """
    # We use a custom shell for the dashboard to avoid the standard page overhead
    style_href = href_relative(current_path, assets_dir / "style.css")
    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <title>Dashboard {html_value(selected.alias)}</title>
    <link rel="stylesheet" href="{style_href}">
    <style>
        @page {{ size: A4; margin: 0; }}
        body {{ margin: 0; padding: 0; background: #f0f2f5; }}
    </style>
</head>
<body>
    {html_content}
</body>
</html>"""
