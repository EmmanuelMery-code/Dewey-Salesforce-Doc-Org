"""Matplotlib rendering for individual dashboard widgets.

Draws a single widget (text, KPI, pie/bar/line chart, table, or image) onto
a given Matplotlib axis. Extracted from ``dashboard_exporter.py`` since it
is shared by the PNG/PDF exports and the per-slide PowerPoint rendering.
"""

from __future__ import annotations

from pathlib import Path


class _DashboardChartsMixin:
    """Adds single-widget chart rendering to ``DashboardExporter``."""

    def _render_single_widget(self, ax, widget):
        """Helper pour rendre un seul widget sur un axe donné."""
        data = widget.get('data', {})
        w_type = widget.get('type')
        color = widget.get('color', '#3498db')
        
        # Gestion intelligente de la couleur de fond
        if w_type in ["text", "image", "kpi"] and ',' not in color:
            bg_color = color
        else:
            bg_color = "none"

        if bg_color == "none":
            ax.set_facecolor('none')
            if hasattr(ax, 'figure'):
                ax.figure.patch.set_alpha(0.0)
        else:
            try:
                ax.set_facecolor(bg_color)
            except:
                ax.set_facecolor('none')

        if w_type == "text":
            ax.axis('off')
            if color != "none":
                from matplotlib.patches import Rectangle
                rect = Rectangle((0,0), 1, 1, transform=ax.transAxes, color=color, zorder=-1)
                ax.add_patch(rect)
            
            rich = widget.get('rich_text')
            align = widget.get('text_align', 'left')
            valign = widget.get('text_valign', 'top')
            
            if rich:
                from matplotlib.offsetbox import TextArea, HPacker, AnnotationBbox, VPacker
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
                                "fontsize": seg.get("size", 10),
                                "fontweight": "bold" if seg.get("bold") else "normal",
                                "fontstyle": "italic" if seg.get("italic") else "normal",
                                "fontname": seg.get("font", "Arial")
                            }
                            
                            # Support des émojis dans le texte riche
                            if any(ord(c) > 0xFFFF for c in part):
                                # On laisse le fallback global gérer l'émoji
                                props["fontname"] = "sans-serif"
                                props["fontweight"] = "normal"
                                props["fontstyle"] = "normal"

                            current_line_segments.append(TextArea(part, textprops=props))
                        elif i > 0:
                            # Ligne vide : on ajoute un espace pour maintenir la hauteur
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
                ha = align
                va = valign
                xy = (0.05, 0.95)
                if ha == "center": xy = (0.5, 0.5 if va == "center" else (0.05 if va == "bottom" else 0.95))
                elif ha == "right": xy = (0.95, 0.5 if va == "center" else (0.05 if va == "bottom" else 0.95))
                # Support des émojis pour le texte simple
                ax.text(xy[0], xy[1], widget.get('text', ''), va=va, ha=ha, wrap=True, fontsize=10, transform=ax.transAxes)
            return

        elif w_type == "dashboard":
            ax.axis('off')
            linked = widget.get('linked_dashboard', '')
            ax.text(0.5, 0.5, f"Dashboard lié :\n{linked}", ha='center', va='center', 
                    bbox=dict(facecolor='lightgrey', alpha=0.5, boxstyle='round'))
            return
            
        # Nettoyer les données pour le rendu (enlever la clé technique 'visible')
        plot_data = {k: v for k, v in data.items() if k != 'visible'} if isinstance(data, dict) else data
        
        if not plot_data and w_type != "image":
            ax.axis('off')
            ax.text(0.5, 0.5, "Aucune donnée", ha='center', va='center')
            return

        if w_type == "pie" or w_type == "donut":
            ax.axis('off')
            valid_data = {str(k): float(v) for k, v in plot_data.items() 
                         if isinstance(v, (int, float, str)) and str(v).replace('.','',1).isdigit() and float(v) > 0}
            
            labels = list(valid_data.keys())
            values = list(valid_data.values())
            
            if not values:
                ax.text(0.5, 0.5, "Données nulles", ha='center', va='center')
            else:
                colors = color.split(',') if ',' in color else None
                if w_type == "pie":
                    ax.pie(values, labels=labels, autopct='%1.1f%%', startangle=140, colors=colors)
                else:
                    ax.pie(values, labels=labels, autopct='%1.1f%%', startangle=140, colors=colors, wedgeprops=dict(width=0.4))
        elif w_type == "bar":
            labels = [str(k) for k in plot_data.keys()]
            values = [float(v) if isinstance(v, (int, float, str)) and str(v).replace('.','',1).isdigit() else 0.0 for v in plot_data.values()]
            if not values or all(v == 0 for v in values):
                ax.text(0.5, 0.5, "Données nulles", ha='center', va='center')
            else:
                try:
                    colors = color.split(',') if ',' in color else color
                    x_indices = list(range(len(labels)))
                    ax.bar(x_indices, values, color=colors)
                    ax.set_xticks(x_indices)
                    ax.set_xticklabels(labels, rotation=45, ha='right', fontsize=8)
                except Exception as e:
                    print(f"Erreur export bar: {e}")
                    ax.text(0.5, 0.5, "Erreur graphique", ha='center', va='center')
        elif w_type == "stacked_bar":
            labels = plot_data.get('labels', [])
            series = plot_data.get('series', {})
            if not labels or not series:
                ax.text(0.5, 0.5, "Données nulles", ha='center', va='center')
            else:
                try:
                    x_indices = list(range(len(labels)))
                    bottom = None
                    colors = color.split(',') if ',' in color else [color]
                    for i, (name, vals) in enumerate(series.items()):
                        c = colors[i % len(colors)]
                        clean_vals = [float(v) if isinstance(v, (int, float, str)) and str(v).replace('.','',1).isdigit() else 0.0 for v in vals]
                        ax.bar(x_indices, clean_vals, bottom=bottom, label=name, color=c)
                        if bottom is None: bottom = [0.0] * len(clean_vals)
                        bottom = [b + v for b, v in zip(bottom, clean_vals)]
                    
                    ax.legend(fontsize=7)
                    ax.set_xticks(x_indices)
                    step = max(1, len(labels) // 6)
                    display_labels = [l if i % step == 0 else "" for i, l in enumerate(labels)]
                    ax.set_xticklabels(display_labels, rotation=45, ha='right', fontsize=8)
                except Exception as e:
                    print(f"Erreur export stacked_bar: {e}")
                    ax.text(0.5, 0.5, "Erreur graphique", ha='center', va='center')
        elif w_type == "line" or w_type == "area":
            labels = [str(k) for k in plot_data.keys()]
            def safe_float(v):
                try:
                    if isinstance(v, str): v = v.replace(',', '.')
                    return float(v)
                except: return 0.0
            values = [safe_float(v) for v in plot_data.values()]
            if not labels:
                ax.text(0.5, 0.5, "Pas de données", ha='center', va='center')
            else:
                try:
                    line_color = color.split(',')[0] if ',' in color else color
                    if line_color == "none": line_color = "#3498db"
                    x_indices = list(range(len(labels)))
                    
                    if w_type == "line":
                        ax.plot(x_indices, values, marker='o', color=line_color, linewidth=2)
                    else:
                        ax.fill_between(x_indices, values, color=line_color, alpha=0.3)
                        ax.plot(x_indices, values, color=line_color, marker='.', linewidth=1)
                    
                    ax.set_xticks(x_indices)
                    step = max(1, len(labels) // 5)
                    display_labels = [l if i % step == 0 else "" for i, l in enumerate(labels)]
                    ax.set_xticklabels(display_labels, rotation=30, ha='right', fontsize=8)
                    ax.grid(True, linestyle='--', alpha=0.6)
                except Exception as e:
                    print(f"Erreur export line/area: {e}")
                    ax.text(0.5, 0.5, "Erreur graphique", ha='center', va='center')
        elif w_type == "kpi":
            ax.axis('off')
            # Formater les nombres
            dec = widget.get('kpi_decimals', 1)
            lines = []
            for k, v in plot_data.items():
                if isinstance(v, (int, float)):
                    lines.append(f"{k}: {v:.{dec}f}")
                else:
                    lines.append(f"{k}: {v}")
            text = "\n".join(lines)
            
            bbox_props = dict(facecolor='white', alpha=0.3, boxstyle='round')
            if color == "none":
                bbox_props['alpha'] = 0.0
                
            ax.text(0.5, 0.5, text, ha='center', va='center', fontsize=16, fontweight='bold', 
                    bbox=bbox_props)
        elif w_type == "table":
            ax.axis('off')
            rows = data.get('rows', [])
            if rows:
                cols_to_show = widget.get('table_columns', [])
                row_keys = widget.get('table_rows', [])
                if not cols_to_show:
                    cols_to_show = [k for k in rows[0].keys() if k not in row_keys]
                all_cols = row_keys + cols_to_show
                
                # Vérification de la validité des colonnes (renommage via AS)
                actual_keys = list(rows[0].keys())
                valid_cols = [c for c in all_cols if c in actual_keys]
                if not valid_cols:
                    all_cols = actual_keys
                else:
                    all_cols = valid_cols

                table_data = [[str(r.get(c, '')) for c in all_cols] for r in rows[:20]]
                tab = ax.table(cellText=table_data, colLabels=all_cols, loc='center', cellLoc='center', bbox=[0, 0, 1, 1])
                tab.auto_set_font_size(False)
                
                font_name = widget.get('table_font_name', 'Segoe UI')
                font_size = widget.get('table_font_size', 8)
                tab.set_fontsize(font_size)
                
                for cell in tab.get_celld().values():
                    cell.set_text_props(fontfamily=font_name)
                
                tab.auto_set_column_width(col=list(range(len(all_cols))))
        elif w_type == "image":
            ax.axis('off')
            if color != "none":
                from matplotlib.patches import Rectangle
                rect = Rectangle((0,0), 1, 1, transform=ax.transAxes, color=color, zorder=-1)
                ax.add_patch(rect)
            
            img_path = widget.get('image_path')
            emoji = widget.get('emoji')
            
            if img_path and Path(img_path).exists():
                try:
                    import matplotlib.image as mpimg
                    img = mpimg.imread(img_path)
                    ax.imshow(img, aspect='equal', extent=[0.1, 0.9, 0.1, 0.9])
                except:
                    ax.text(0.5, 0.5, "Erreur image", ha='center', va='center')
            elif emoji:
                # On utilise le fallback global via sans-serif
                ax.text(0.5, 0.5, emoji, ha='center', va='center', 
                        fontsize=widget.get('image_font_size', 60), 
                        color=widget.get('image_font_color', '#000000'),
                        fontfamily="sans-serif")
            else:
                ax.text(0.5, 0.5, "Aucune image", ha='center', va='center')
