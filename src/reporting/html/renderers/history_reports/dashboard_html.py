"""Builds the printable HTML body (CSS + status/evolution grids) of the history dashboard."""

from __future__ import annotations

from pathlib import Path

from src.core.history_service import HistoryEntry
from src.core.utils import html_value
from src.reporting.html.page_shell import index_back_link
from src.reporting.html.renderers.history_reports.dashboard_charts import _get_pie_css


def build_dashboard_content(
    selected: HistoryEntry,
    current_path: Path,
    *,
    adoption_pct: float,
    adaptation_pct: float,
    dm_standard_pct: float,
    dm_custom_pct: float,
    ai_with_pct: float,
    ai_without_pct: float,
    f_total: int,
    f_crit: int,
    f_maj: int,
    f_min: int,
    f_inf: int,
    max_f: int,
    test_coverage_pct: float,
    evolution: dict[str, str],
) -> str:
    """Return the ``<style>`` + dashboard grids HTML for the current status and evolution."""
    adoption_evolution_bars = evolution["adoption_evolution_bars"]
    adoption_table = evolution["adoption_table"]
    dm_evolution_bars = evolution["dm_evolution_bars"]
    dm_table = evolution["dm_table"]
    ai_evolution_bars = evolution["ai_evolution_bars"]
    ai_table = evolution["ai_table"]
    findings_evolution_bars = evolution["findings_evolution_bars"]
    findings_table = evolution["findings_table"]
    coverage_evolution_bars = evolution["coverage_evolution_bars"]

    return f"""
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
