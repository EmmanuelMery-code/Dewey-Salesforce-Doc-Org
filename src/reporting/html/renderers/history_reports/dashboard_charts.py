"""Small chart-drawing helpers shared by the printable history dashboard."""

from __future__ import annotations


def _get_pie_css(val1: float, color1: str, color2: str) -> str:
    """Generate CSS for a simple pie chart using conic-gradient."""
    return f"background: conic-gradient({color1} 0% {val1}%, {color2} {val1}% 100%);"


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
