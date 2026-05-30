from __future__ import annotations
from typing import Any, Dict, List, Optional
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.gridspec import GridSpec
from matplotlib.patches import Rectangle
from matplotlib.offsetbox import TextArea, HPacker, AnnotationBbox, VPacker
from matplotlib.lines import Line2D
import matplotlib.image as mpimg
from pathlib import Path

class WidgetRenderer:
    """Classe de base pour le rendu d'un widget."""
    def render(self, ax: Any, widget: Dict[str, Any], plot_data: Any, selected: bool = False):
        pass

    def _setup_background(self, ax, color):
        if color == "none":
            ax.set_facecolor('none')
        else:
            try:
                ax.set_facecolor(color)
            except:
                ax.set_facecolor('none')

    def _draw_selection(self, ax):
        for spine in ax.spines.values():
            spine.set_edgecolor('blue')
            spine.set_linewidth(2)
            spine.set_linestyle('--')
        
        handles = [(0,0), (1,0), (0,1), (1,1), (0.5,0), (0.5,1), (0,0.5), (1,0.5)]
        for hx, hy in handles:
            line = Line2D([hx], [hy], marker='s', color='blue', markersize=6, 
                         transform=ax.transAxes, clip_on=False, zorder=100)
            ax.add_line(line)

class TextRenderer(WidgetRenderer):
    def render(self, ax, widget, plot_data, selected=False):
        ax.axis('off')
        color = widget.get('color', '#ffffff')
        if color != "none":
            rect = Rectangle((0,0), 1, 1, transform=ax.transAxes, color=color, zorder=-1)
            ax.add_patch(rect)

        rich = widget.get('rich_text')
        align = widget.get('text_align', 'left')
        valign = widget.get('text_valign', 'top')
        
        if rich:
            lines = []
            current_line_segments = []
            for seg in rich:
                text_parts = seg['text'].split('\n')
                for i, part in enumerate(text_parts):
                    if i > 0:
                        lines.append(current_line_segments)
                        current_line_segments = []
                    if part:
                        props = {
                            "color": seg.get("color", "black"),
                            "fontsize": seg.get("size", 9),
                            "fontweight": "bold" if seg.get("bold") else "normal",
                            "fontstyle": "italic" if seg.get("italic") else "normal",
                            "fontname": seg.get("font", "Arial")
                        }
                        if any(ord(c) > 0xFFFF for c in part):
                            props["fontname"] = "sans-serif"
                            props["fontweight"] = "normal"
                            props["fontstyle"] = "normal"
                        current_line_segments.append(TextArea(part, textprops=props))
                    elif i > 0:
                        current_line_segments.append(TextArea(" "))
            if current_line_segments: lines.append(current_line_segments)
            
            if lines:
                line_boxes = [HPacker(children=l, align="baseline", pad=0, sep=0) for l in lines]
                vbox = VPacker(children=line_boxes, align=align, pad=0, sep=2)
                xy = (0.05, 0.95)
                box_align = (0, 1)
                if align == "center": xy = (0.5, xy[1]); box_align = (0.5, box_align[1])
                elif align == "right": xy = (0.95, xy[1]); box_align = (1, box_align[1])
                if valign == "center": xy = (xy[0], 0.5); box_align = (box_align[0], 0.5)
                elif valign == "bottom": xy = (xy[0], 0.05); box_align = (box_align[0], 0)
                ab = AnnotationBbox(vbox, xy, xycoords='axes fraction', box_alignment=box_align, frameon=False)
                ax.add_artist(ab)
        else:
            tx = 0.5 if align == "center" else (0.95 if align == "right" else 0.05)
            ty = 0.5 if valign == "center" else (0.05 if valign == "bottom" else 0.95)
            ax.text(tx, ty, widget.get('text', ''), va=valign, ha=align, wrap=True, fontsize=9, transform=ax.transAxes)
        
        if selected: self._draw_selection(ax)

class ChartRenderer(WidgetRenderer):
    def _safe_float(self, v):
        try:
            if isinstance(v, str): v = v.replace(',', '.')
            return float(v)
        except: return 0.0

    def render(self, ax, widget, plot_data, selected=False):
        self._setup_background(ax, 'none')
        ax.set_title(widget.get('title', ''), fontsize=10, fontweight='bold')
        ax.set_box_aspect(None)
        if selected: self._draw_selection(ax)

class PieRenderer(ChartRenderer):
    def render(self, ax, widget, plot_data, selected=False, t_func=None):
        super().render(ax, widget, plot_data, selected)
        ax.axis('off')
        valid_data = {str(k): float(v) for k, v in plot_data.items() 
                     if isinstance(v, (int, float, str)) and str(v).replace('.','',1).isdigit() and float(v) > 0}
        if not valid_data:
            msg = t_func("renderer_null_data") if t_func else "Données nulles"
            ax.text(0.5, 0.5, msg, ha='center', va='center')
            return
        colors = widget.get('color', '').split(',') if ',' in widget.get('color', '') else None
        is_donut = widget.get('type') == "donut"
        ax.pie(list(valid_data.values()), labels=list(valid_data.keys()), autopct='%1.1f%%', 
               startangle=140, colors=colors, wedgeprops=dict(width=0.4) if is_donut else None)

class BarRenderer(ChartRenderer):
    def render(self, ax, widget, plot_data, selected=False, t_func=None):
        super().render(ax, widget, plot_data, selected)
        labels = [str(k) for k in plot_data.keys()]
        values = [self._safe_float(v) for v in plot_data.values()]
        if not values or all(v == 0 for v in values):
            msg = t_func("renderer_null_data") if t_func else "Données nulles"
            ax.text(0.5, 0.5, msg, ha='center', va='center')
            return
        color = widget.get('color', '#3498db')
        colors = color.split(',') if ',' in color else color
        x_indices = list(range(len(labels)))
        ax.bar(x_indices, values, color=colors)
        ax.set_xticks(x_indices)
        ax.set_xticklabels(labels, rotation=45, ha='right', fontsize=7)

class StackedBarRenderer(ChartRenderer):
    def render(self, ax, widget, plot_data, selected=False, t_func=None):
        super().render(ax, widget, plot_data, selected)
        labels = plot_data.get('labels', [])
        series = plot_data.get('series', {})
        if not labels or not series:
            msg = t_func("renderer_null_data") if t_func else "Données nulles"
            ax.text(0.5, 0.5, msg, ha='center', va='center')
            return
        x_indices = list(range(len(labels)))
        bottom = None
        color_str = widget.get('color', '#3498db')
        colors = color_str.split(',') if ',' in color_str else [color_str]
        for i, (name, vals) in enumerate(series.items()):
            c = colors[i % len(colors)]
            clean_vals = [self._safe_float(v) for v in vals]
            ax.bar(x_indices, clean_vals, bottom=bottom, label=name, color=c)
            if bottom is None: bottom = [0.0] * len(clean_vals)
            bottom = [b + v for b, v in zip(bottom, clean_vals)]
        ax.legend(fontsize=7)
        ax.set_xticks(x_indices)
        step = max(1, len(labels) // 6)
        ax.set_xticklabels([l if i % step == 0 else "" for i, l in enumerate(labels)], rotation=45, ha='right', fontsize=7)

class LineRenderer(ChartRenderer):
    def render(self, ax, widget, plot_data, selected=False, t_func=None):
        super().render(ax, widget, plot_data, selected)
        labels = [str(k) for k in plot_data.keys()]
        values = [self._safe_float(v) for v in plot_data.values()]
        if not labels:
            msg = t_func("renderer_no_data") if t_func else "Pas de données"
            ax.text(0.5, 0.5, msg, ha='center', va='center')
            return
        color_str = widget.get('color', '#3498db')
        line_color = color_str.split(',')[0] if ',' in color_str else color_str
        if line_color == "none": line_color = "#3498db"
        x_indices = list(range(len(labels)))
        if widget.get('type') == "line":
            ax.plot(x_indices, values, marker='o', color=line_color, linewidth=2)
        else: # area
            ax.fill_between(x_indices, values, color=line_color, alpha=0.3)
            ax.plot(x_indices, values, color=line_color, marker='.', linewidth=1)
        ax.set_xticks(x_indices)
        step = max(1, len(labels) // 5)
        ax.set_xticklabels([l if i % step == 0 else "" for i, l in enumerate(labels)], rotation=30, ha='right', fontsize=7)
        ax.grid(True, linestyle='--', alpha=0.6)
        if values:
            v_min, v_max = min(values), max(values)
            margin = (v_max - v_min) * 0.1 if v_max > v_min else 1.0
            ax.set_ylim(min(0, v_min - margin), v_max + margin)

class KpiRenderer(WidgetRenderer):
    def render(self, ax, widget, plot_data, selected=False, t_func=None):
        ax.axis('off')
        dec = widget.get('kpi_decimals', 1)
        lines = [f"{k}: {v:.{dec}f}" if isinstance(v, (int, float)) else f"{k}: {v}" for k, v in plot_data.items()]
        txt = "\n".join(lines)
        color = widget.get('color', 'none')
        bbox_props = dict(facecolor='white', alpha=0.2 if color != "none" else 0.0, boxstyle='round')
        ax.text(0.5, 0.5, txt, ha='center', va='center', fontweight='bold', bbox=bbox_props)
        ax.set_title(widget.get('title', ''), fontsize=10, fontweight='bold')
        if selected: self._draw_selection(ax)

class TableRenderer(WidgetRenderer):
    def render(self, ax, widget, plot_data, selected=False, t_func=None):
        ax.axis('off')
        rows = plot_data.get('rows', []) if isinstance(plot_data, dict) else []
        if not rows:
            msg = t_func("renderer_no_data") if t_func else "Pas de données"
            ax.text(0.5, 0.5, msg, ha='center', va='center')
        else:
            cols_to_show = widget.get('table_columns', [])
            row_keys = widget.get('table_rows', [])
            all_cols = row_keys + cols_to_show
            actual_keys = list(rows[0].keys())
            valid_cols = [c for c in all_cols if c in actual_keys]
            all_cols = valid_cols if valid_cols else actual_keys
            table_data = [[str(r.get(c, '')) for c in all_cols] for r in rows[:15]]
            if table_data:
                tab = ax.table(cellText=table_data, colLabels=all_cols, loc='center', cellLoc='center', bbox=[0, 0, 1, 1])
                tab.auto_set_font_size(False)
                tab.set_fontsize(widget.get('table_font_size', 7))
                font_name = widget.get('table_font_name', 'Arial')
                for cell in tab.get_celld().values(): cell.set_text_props(fontfamily=font_name)
                tab.auto_set_column_width(col=list(range(len(all_cols))))
        ax.set_title(widget.get('title', ''), fontsize=10, fontweight='bold')
        if selected: self._draw_selection(ax)

class ImageRenderer(WidgetRenderer):
    def render(self, ax, widget, plot_data, selected=False, t_func=None):
        ax.axis('off')
        color = widget.get('color', '#ffffff')
        if color != "none":
            rect = Rectangle((0,0), 1, 1, transform=ax.transAxes, color=color, zorder=-1)
            ax.add_patch(rect)
        img_path = widget.get('image_path')
        emoji = widget.get('emoji')
        if img_path and Path(img_path).exists():
            try:
                img = mpimg.imread(img_path)
                ax.imshow(img, aspect='equal', extent=[0.1, 0.9, 0.1, 0.9])
            except:
                msg = t_func("renderer_img_error") if t_func else "Erreur image"
                ax.text(0.5, 0.5, msg, ha='center', va='center')
        elif emoji:
            ax.text(0.5, 0.5, emoji, ha='center', va='center', fontsize=widget.get('image_font_size', 50), 
                    color=widget.get('image_font_color', '#000000'), fontfamily="sans-serif")
        else:
            msg = t_func("renderer_no_img") if t_func else "Aucune image"
            ax.text(0.5, 0.5, msg, ha='center', va='center')
        ax.set_title(widget.get('title', ''), fontsize=10, fontweight='bold')
        if selected: self._draw_selection(ax)

class DashboardRenderer(WidgetRenderer):
    def render(self, ax, widget, plot_data, selected=False, t_func=None):
        ax.axis('off')
        linked = widget.get('linked_dashboard', '')
        msg_prefix = t_func("renderer_linked_dash") if t_func else "Dashboard lié :"
        ax.text(0.5, 0.5, f"{msg_prefix}\n{linked}", ha='center', va='center', 
                bbox=dict(facecolor='lightgrey', alpha=0.5, boxstyle='round'))
        ax.set_title(widget.get('title', ''), fontsize=10, fontweight='bold')
        if selected: self._draw_selection(ax)

class RendererFactory:
    _renderers = {
        "text": TextRenderer(),
        "pie": PieRenderer(),
        "donut": PieRenderer(),
        "bar": BarRenderer(),
        "stacked_bar": StackedBarRenderer(),
        "line": LineRenderer(),
        "area": LineRenderer(),
        "kpi": KpiRenderer(),
        "table": TableRenderer(),
        "image": ImageRenderer(),
        "dashboard": DashboardRenderer()
    }

    @classmethod
    def get_renderer(cls, widget_type: str) -> WidgetRenderer:
        return cls._renderers.get(widget_type, ChartRenderer())

def generate_layout_figure(widgets_data: List[Dict[str, Any]], selected_id: Optional[str] = None, t_func=None) -> Figure:
    if not widgets_data: return Figure()
    widgets_data = sorted(widgets_data, key=lambda x: x.get('z_order', 0))
    mx = max(1, max(w['x'] + w['w'] for w in widgets_data))
    my = max(1, max(w['y'] + w['h'] for w in widgets_data))
    fig_h = 2 * my if my < 5 else 1.5 * my
    fig = Figure(figsize=(10, fig_h), dpi=90)
    gs = GridSpec(my, mx, figure=fig)
    
    for w in widgets_data:
        try:
            widget_data = w.get('data')
            if isinstance(widget_data, dict) and not widget_data.get('visible', True): continue
            
            ax = fig.add_subplot(gs[w['y']:w['y']+w['h'], w['x']:w['x']+w['w']])
            ax.widget_id = w.get('id')
            
            wt = w['type']
            d = w['data']
            plot_data = {k: v for k, v in d.items() if k != 'visible'} if isinstance(d, dict) else d
            
            renderer = RendererFactory.get_renderer(wt)
            renderer.render(ax, w, plot_data, selected=(selected_id == ax.widget_id), t_func=t_func)
            
        except Exception as e:
            print(f"Erreur rendu widget {w.get('id')} ({w.get('type')}): {e}")
    
    try: fig.tight_layout()
    except: pass
    return fig
