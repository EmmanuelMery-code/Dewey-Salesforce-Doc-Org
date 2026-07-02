"""CSS stylesheets embedded in / written for the HTML documentation site.

Extracted verbatim from the former ``assets.py`` module so the generated
``style.css`` and ``dashboard.css`` stay byte-for-byte identical.
"""

from __future__ import annotations

MAIN_CSS = """
body { font-family: Arial, sans-serif; margin: 0; color: #1f2937; background: #f8fafc; }
.page { max-width: 1400px; margin: 0 auto; padding: 24px; }
.topnav { margin-bottom: 20px; }
.topnav a { text-decoration: none; color: #1d4ed8; }
h1, h2, h3 { color: #0f172a; }
.cards { display: flex; flex-wrap: wrap; gap: 16px; margin: 16px 0 24px; }
.card { background: white; border: 1px solid #cbd5e1; border-radius: 8px; padding: 16px; min-width: 180px; }
.card .value { display: block; font-size: 1.6rem; font-weight: bold; margin-top: 8px; }
table { width: 100%; border-collapse: collapse; background: white; margin: 12px 0 24px; }
th, td { border: 1px solid #cbd5e1; padding: 8px; text-align: left; vertical-align: top; }
th { background: #dbeafe; }
tr:nth-child(even) { background: #f8fbff; }
.badge { display: inline-block; padding: 4px 10px; border-radius: 999px; background: #dbeafe; color: #1e3a8a; }
.badge.complexity-simple { background: #dcfce7; color: #166534; }
.badge.complexity-medium { background: #fef3c7; color: #92400e; }
.badge.complexity-complex { background: #fed7aa; color: #9a3412; }
.badge.complexity-very-complex { background: #fecaca; color: #991b1b; }
.section { margin-bottom: 28px; }
ul { background: white; border: 1px solid #cbd5e1; border-radius: 8px; padding: 16px 32px; }
.empty { color: #64748b; font-style: italic; }
.mermaid { background: white; border: 1px solid #cbd5e1; border-radius: 8px; padding: 12px; overflow: auto; }
.mermaid-container { margin: 14px 0; border: 1px solid #cbd5e1; border-radius: 10px; background: white; overflow: hidden; box-shadow: 0 1px 2px rgba(15,23,42,0.06); width: 100%; box-sizing: border-box; }
.mermaid-toolbar { display: flex; align-items: center; gap: 6px; padding: 6px 10px; border-bottom: 1px solid #e2e8f0; background: #f1f5f9; }
.mermaid-toolbar button.mm-btn { border: 1px solid #94a3b8; background: white; border-radius: 6px; padding: 3px 10px; cursor: pointer; font-weight: 600; color: #1e293b; min-width: 34px; line-height: 1.2; }
.mermaid-toolbar button.mm-btn:hover { background: #dbeafe; border-color: #60a5fa; }
.mermaid-toolbar .mm-hint { margin-left: auto; font-size: 0.78rem; color: #64748b; font-style: italic; }
.mermaid-container .mermaid { border: none; border-radius: 0; padding: 0; margin: 0; width: 100%; height: 720px; max-height: 85vh; overflow: hidden; background: white; user-select: none; box-sizing: border-box; display: block; position: relative; }
.mermaid-container .mermaid svg { width: 100% !important; height: 100% !important; max-width: none !important; display: block; }
.mermaid-container .mermaid g.node { cursor: grab; }
.mermaid-container .mermaid g.node:active { cursor: grabbing; }
.tab-panel .mermaid-container { max-width: 100%; }
code { background: #e2e8f0; padding: 2px 4px; border-radius: 4px; }
.smallcards .card { min-width: 150px; }
.ai-usage-card { min-width: 260px; }
.ai-usage-grid { display: flex; gap: 16px; margin-top: 8px; }
.ai-usage-stat { flex: 1; padding: 8px 12px; border-radius: 6px; background: #f1f5f9; border: 1px solid #e2e8f0; }
.ai-usage-stat--with { background: #ecfdf5; border-color: #6ee7b7; }
.ai-usage-stat--without { background: #fef2f2; border-color: #fca5a5; }
.ai-usage-stat .ai-usage-label { display: block; font-size: 0.78rem; color: #475569; text-transform: uppercase; letter-spacing: 0.04em; }
.ai-usage-stat .value { display: block; font-size: 1.4rem; font-weight: 700; margin-top: 4px; color: #0f172a; }
.ai-usage-stat .ai-usage-percent { display: block; font-size: 0.85rem; color: #334155; margin-top: 2px; }
.ai-usage-card .ai-usage-hint { display: block; margin-top: 10px; font-size: 0.8rem; color: #64748b; font-style: italic; }
.cards.smallcards .ai-usage-stat--with, .cards.smallcards .ai-usage-stat--without { min-width: 150px; }
.adopt-card { min-width: 260px; }
.adopt-grid { display: flex; gap: 16px; margin-top: 8px; }
.adopt-stat { flex: 1; padding: 8px 12px; border-radius: 6px; background: #f1f5f9; border: 1px solid #e2e8f0; }
.adopt-stat--adopt { background: #ecfdf5; border-color: #6ee7b7; }
.adopt-stat--adapt { background: #fff7ed; border-color: #fdba74; }
.adopt-stat--low { background: #fef9c3; border-color: #facc15; }
.adopt-stat--high { background: #fef2f2; border-color: #fca5a5; }
.adopt-stat .adopt-label { display: block; font-size: 0.78rem; color: #475569; text-transform: uppercase; letter-spacing: 0.04em; }
.adopt-stat .value { display: block; font-size: 1.4rem; font-weight: 700; margin-top: 4px; color: #0f172a; }
.adopt-stat .adopt-percent { display: block; font-size: 0.85rem; color: #334155; margin-top: 2px; }
.adopt-card .adopt-hint { display: block; margin-top: 10px; font-size: 0.8rem; color: #64748b; font-style: italic; }
.cards.smallcards .adopt-card { min-width: 220px; }
.cards.smallcards .adopt-card--adopt { background: #ecfdf5; border-color: #6ee7b7; }
.cards.smallcards .adopt-card--adopt-declarative { background: #d1fae5; border-color: #34d399; }
.cards.smallcards .adopt-card--adapt { background: #fff7ed; border-color: #fdba74; }
.cards.smallcards .adopt-card--low { background: #fef9c3; border-color: #facc15; }
.cards.smallcards .adopt-card--high { background: #fef2f2; border-color: #fca5a5; }
.cards.smallcards .adopt-card .adopt-percent { display: block; font-size: 0.85rem; color: #334155; margin-top: 2px; }
.adopt-level { display: inline-block; padding: 2px 10px; border-radius: 999px; font-weight: 600; font-size: 0.82rem; border: 1px solid #cbd5e1; background: white; color: #1e293b; }
.adopt-level--adopt { background: #ecfdf5; border-color: #6ee7b7; color: #065f46; }
.adopt-level--adopt-declarative { background: #d1fae5; border-color: #34d399; color: #047857; }
.adopt-level--low { background: #fef9c3; border-color: #facc15; color: #854d0e; }
.adopt-level--high { background: #fef2f2; border-color: #f87171; color: #991b1b; }
.graph-toolbar { display: flex; gap: 8px; margin-bottom: 10px; }
.graph-toolbar button { border: 1px solid #cbd5e1; background: #f8fafc; border-radius: 6px; padding: 6px 10px; cursor: pointer; }
.graph-toolbar button:hover { background: #e2e8f0; }
.graph-toolbar button.active { background: #dbeafe; border-color: #3b82f6; color: #1d4ed8; font-weight: 600; }
.graph-filters { display: flex; flex-wrap: wrap; gap: 16px; margin-bottom: 10px; }
.graph-filters label { display: inline-flex; align-items: center; gap: 6px; font-size: 0.92rem; color: #334155; }
.dependency-graph { height: 440px; border: 1px solid #cbd5e1; border-radius: 8px; background: #ffffff; }
.graph-legend { display: flex; flex-wrap: wrap; gap: 12px; margin: 8px 0 12px; }
.graph-legend .item { display: inline-flex; align-items: center; gap: 6px; font-size: 0.9rem; }
.findings-summary { display: flex; flex-wrap: wrap; gap: 10px; margin: 0 0 14px; }
.findings-summary .chip { display: inline-flex; align-items: center; gap: 6px; padding: 4px 12px; border-radius: 999px; font-weight: 600; font-size: 0.85rem; border: 1px solid #cbd5e1; background: white; color: #1e293b; }
.findings-summary .chip strong { font-weight: 700; }
.findings-summary .chip.sev-critical { background: #fef2f2; border-color: #f87171; color: #991b1b; }
.findings-summary .chip.sev-major { background: #fff7ed; border-color: #fb923c; color: #9a3412; }
.findings-summary .chip.sev-minor { background: #fefce8; border-color: #eab308; color: #854d0e; }
.findings-summary .chip.sev-info { background: #eff6ff; border-color: #60a5fa; color: #1e3a8a; }
.findings-list { list-style: none; padding: 0; margin: 0; background: white; border: 1px solid #cbd5e1; border-radius: 10px; overflow: hidden; }
.findings-list li.finding { padding: 14px 18px; border-top: 1px solid #e2e8f0; }
.findings-list li.finding:first-child { border-top: none; }
.findings-list li.finding .head { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; margin-bottom: 6px; }
.findings-list li.finding .title { font-weight: 700; color: #0f172a; }
.findings-list li.finding .rule-id { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 0.85rem; color: #475569; }
.findings-list li.finding .sev-badge { display: inline-block; font-size: 0.75rem; padding: 2px 8px; border-radius: 999px; font-weight: 700; letter-spacing: 0.02em; }
.findings-list li.finding .sev-badge.sev-critical { background: #fee2e2; color: #991b1b; }
.findings-list li.finding .sev-badge.sev-major { background: #ffedd5; color: #9a3412; }
.findings-list li.finding .sev-badge.sev-minor { background: #fef9c3; color: #854d0e; }
.findings-list li.finding .sev-badge.sev-info { background: #dbeafe; color: #1e3a8a; }
.findings-list li.finding .category-badge { display: inline-block; font-size: 0.72rem; padding: 2px 8px; border-radius: 999px; background: #e2e8f0; color: #334155; letter-spacing: 0.02em; }
.findings-list li.finding .message { margin: 2px 0 6px; color: #1e293b; }
.findings-list li.finding .metadata { font-size: 0.85rem; color: #475569; margin: 4px 0; }
.findings-list li.finding .metadata dt { font-weight: 600; color: #0f172a; float: left; margin-right: 6px; }
.findings-list li.finding .metadata dd { margin: 0 0 4px; }
.findings-list li.finding .metadata a { color: #1d4ed8; }
.findings-list li.finding ul.details { margin: 6px 0 0; padding-left: 18px; }
.findings-list li.finding ul.details li { list-style: disc; color: #334155; }
.analyzer-summary-card { background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%); border: 1px solid #cbd5e1; border-radius: 12px; padding: 18px 22px; margin: 12px 0; }
.analyzer-summary-card h3 { margin-top: 0; }
.analyzer-summary-card table { width: 100%; border: none; background: transparent; border-collapse: collapse; }
.analyzer-summary-card table th, .analyzer-summary-card table td { border: none; background: transparent; padding: 6px 10px; }
.analyzer-summary-card table tbody tr:nth-child(even) { background: #f1f5f9; }
.graph-legend .dot { width: 12px; height: 12px; border-radius: 999px; border: 1px solid #64748b; display: inline-block; }
.graph-legend .legend-toggle { cursor: pointer; user-select: none; padding: 2px 6px; border-radius: 6px; border: 1px solid transparent; }
.graph-legend .legend-toggle:hover { background: #f1f5f9; border-color: #cbd5e1; }
.graph-legend .legend-toggle.disabled { opacity: 0.4; text-decoration: line-through; }
.graph-context-menu { position: fixed; z-index: 9999; background: #ffffff; border: 1px solid #cbd5e1; border-radius: 6px; box-shadow: 0 4px 12px rgba(15,23,42,0.18); padding: 4px; min-width: 160px; }
.graph-context-menu button { display: block; width: 100%; text-align: left; border: none; background: transparent; padding: 7px 10px; border-radius: 4px; cursor: pointer; font-size: 0.9rem; color: #1e293b; }
.graph-context-menu button:hover { background: #f1f5f9; }
.graph-node-tooltip { position: fixed; z-index: 9998; max-width: 360px; background: #0f172a; color: #f8fafc; border: 1px solid #334155; border-radius: 8px; box-shadow: 0 8px 20px rgba(15,23,42,0.28); padding: 9px 11px; font-size: 0.86rem; line-height: 1.35; pointer-events: none; }
.graph-node-tooltip strong { color: #bfdbfe; }
.tabs { background: white; border: 1px solid #cbd5e1; border-radius: 8px; overflow: hidden; }
.tab-buttons { display: flex; flex-wrap: wrap; gap: 6px; padding: 10px; border-bottom: 1px solid #cbd5e1; background: #f8fafc; }
.tab-button { border: 1px solid #cbd5e1; border-radius: 999px; background: white; color: #334155; padding: 6px 12px; cursor: pointer; }
.tab-button.active { background: #dbeafe; color: #1e3a8a; border-color: #93c5fd; }
.tab-panel { display: none; padding: 14px; }
.tab-panel.active { display: block; }
        """.strip()


DASHBOARD_CSS = """
/* Dashboard A4 Printable Styles */
@media print {
    @page {
        size: A4;
        margin: 10mm;
    }
    body {
        background: white !important;
        -webkit-print-color-adjust: exact;
        print-color-adjust: exact;
    }
    .topnav, .no-print {
        display: none !important;
    }
    .page {
        padding: 0 !important;
        max-width: none !important;
    }
    .section {
        page-break-inside: avoid;
    }
}

.dashboard-page {
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    color: #1a202c;
    line-height: 1.4;
    max-width: 1000px;
    margin: 0 auto;
    padding: 20px;
}

.dashboard-header {
    text-align: center;
    border-bottom: 2px solid #2d3748;
    margin-bottom: 20px;
    padding-bottom: 10px;
}

.dashboard-header h1 {
    margin: 0;
    font-size: 24px;
    color: #2d3748;
}

.dashboard-header p {
    margin: 5px 0 0;
    color: #718096;
    font-size: 14px;
}

.dashboard-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 20px;
    margin-bottom: 20px;
}

.dashboard-card {
    background: white;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 15px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
}

.dashboard-card h3 {
    margin: 0 0 15px 0;
    font-size: 16px;
    text-align: center;
    color: #4a5568;
    border-bottom: 1px solid #edf2f7;
    padding-bottom: 8px;
}

.chart-container {
    height: 180px;
    display: flex;
    align-items: center;
    justify-content: center;
    position: relative;
}

.chart-legend {
    display: flex;
    justify-content: center;
    gap: 15px;
    margin-top: 10px;
    font-size: 12px;
}

.legend-item {
    display: flex;
    align-items: center;
    gap: 5px;
}

.legend-dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
}

.dashboard-table {
    width: 100%;
    border-collapse: collapse;
    margin-top: 15px;
    font-size: 12px;
}

.dashboard-table th, .dashboard-table td {
    border: 1px solid #e2e8f0;
    padding: 6px 8px;
    text-align: center;
}

.dashboard-table th {
    background: #f7fafc;
    font-weight: 600;
}

.bar-chart {
    display: flex;
    align-items: flex-end;
    gap: 10px;
    height: 120px;
    padding-bottom: 20px;
    border-bottom: 1px solid #cbd5e0;
    margin: 0 20px;
}

.bar-group {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    height: 100%;
    justify-content: flex-end;
    position: relative;
}

.bar {
    width: 30px;
    border-radius: 4px 4px 0 0;
    transition: height 0.3s;
}

.bar-label {
    position: absolute;
    bottom: -20px;
    font-size: 10px;
    white-space: nowrap;
}

.bar-value {
    font-size: 10px;
    margin-bottom: 2px;
}

/* Colors from the image */
.color-adoption { background-color: #68b36b; }
.color-adaptation { background-color: #e5534b; }
.color-standard { background-color: #68b36b; }
.color-custom { background-color: #e5534b; }
.color-ai-with { background-color: #68b36b; }
.color-ai-without { background-color: #e5534b; }
.color-critique { background-color: #e53e3e; }
.color-majeur { background-color: #ed8936; }
.color-mineur { background-color: #ecc94b; }
.color-info { background-color: #48bb78; }

.pie-chart {
    width: 120px;
    height: 120px;
    border-radius: 50%;
    position: relative;
}
    """
