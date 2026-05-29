from __future__ import annotations

import io
from pathlib import Path
from typing import Any, Dict, List

import matplotlib.pyplot as plt
from matplotlib.figure import Figure
import pandas as pd
from pptx import Presentation
from pptx.util import Inches, Pt
from openpyxl import Workbook
from openpyxl.drawing.image import Image as OpenpyxlImage

class DashboardExporter:
    """Service pour l'exportation des tableaux de bord vers différents formats.
    
    Supporte :
    - PDF (via Matplotlib)
    - PNG (avec ou sans transparence)
    - PowerPoint (PPTX)
    - Excel (XLSX)
    - CSV
    """

    def __init__(self, log_callback=None):
        self.log = log_callback or (lambda msg: None)

    def export_to_pdf(self, fig: Figure, output_path: Path):
        """Exporte la figure Matplotlib en PDF."""
        fig.savefig(output_path, format='pdf', bbox_inches='tight')
        self.log(f"Dashboard exporté en PDF : {output_path}")

    def export_to_png(self, fig: Figure, output_path: Path, transparent: bool = False):
        """Exporte la figure Matplotlib en PNG."""
        fig.savefig(output_path, format='png', bbox_inches='tight', transparent=transparent)
        self.log(f"Dashboard exporté en PNG ({'transparent' if transparent else 'opaque'}) : {output_path}")

    def export_to_pptx(self, widgets_data: List[Dict[str, Any]], output_path: Path, title: str = "Salesforce Org Dashboard"):
        """Exporte chaque widget sur une slide PowerPoint séparée."""
        prs = Presentation()
        
        # Slide de titre
        title_slide_layout = prs.slide_layouts[0]
        slide = prs.slides.add_slide(title_slide_layout)
        title_shape = slide.shapes.title
        subtitle_shape = slide.placeholders[1]
        title_shape.text = title
        subtitle_shape.text = f"Généré le {pd.Timestamp.now().strftime('%d/%m/%Y')}"

        for widget in widgets_data:
            # Utiliser un layout avec titre et contenu
            slide_layout = prs.slide_layouts[5] # Title Only
            slide = prs.slides.add_slide(slide_layout)
            
            # Titre de la slide
            slide.shapes.title.text = widget.get('title', 'Composant')
            
            if widget.get('type') == 'text':
                # Ajouter le texte directement dans la slide
                txBox = slide.shapes.add_textbox(Inches(1), Inches(1.5), Inches(8), Inches(5))
                tf = txBox.text_frame
                tf.word_wrap = True
                tf.text = widget.get('text', '')
            else:
                # Générer l'image du graphique pour ce widget seul
                fig = Figure(figsize=(8, 5), dpi=100)
                ax = fig.add_subplot(111)
                self._render_single_widget(ax, widget)
                
                image_stream = io.BytesIO()
                fig.savefig(image_stream, format='png', bbox_inches='tight', dpi=200)
                image_stream.seek(0)
                
                # Centrer l'image
                slide.shapes.add_picture(image_stream, Inches(1), Inches(1.5), width=Inches(8))
                plt.close(fig)

        prs.save(output_path)
        self.log(f"Dashboard exporté en PowerPoint (multi-slides) : {output_path}")

    def _render_single_widget(self, ax, widget):
        """Helper pour rendre un seul widget sur un axe donné."""
        data = widget.get('data', {})
        w_type = widget.get('type')
        color = widget.get('color', '#3498db')
        
        if not data:
            ax.text(0.5, 0.5, "Aucune donnée", ha='center', va='center')
            return

        if w_type == "pie":
            ax.pie(list(data.values()), labels=list(data.keys()), autopct='%1.1f%%', startangle=140)
        elif w_type == "donut":
            ax.pie(list(data.values()), labels=list(data.keys()), autopct='%1.1f%%', startangle=140, wedgeprops=dict(width=0.4))
        elif w_type == "bar":
            ax.bar(list(data.keys()), list(data.values()), color=color)
            ax.tick_params(axis='x', rotation=45, labelsize=8)
        elif w_type == "stacked_bar":
            labels = data.get('labels', [])
            series = data.get('series', {})
            bottom = None
            colors = color.split(',') if ',' in color else [color]
            for i, (name, vals) in enumerate(series.items()):
                c = colors[i % len(colors)]
                ax.bar(labels, vals, bottom=bottom, label=name, color=c)
                if bottom is None: bottom = [0.0] * len(vals)
                bottom = [b + v for b, v in zip(bottom, vals)]
            ax.legend(fontsize=7); ax.tick_params(axis='x', rotation=45, labelsize=8)
        elif w_type == "line":
            ax.plot(list(data.keys()), list(data.values()), marker='o', color=color)
            ax.tick_params(axis='x', rotation=45, labelsize=8)
        elif w_type == "area":
            ax.fill_between(list(data.keys()), list(data.values()), color=color, alpha=0.3)
            ax.plot(list(data.keys()), list(data.values()), color=color, marker='.')
            ax.tick_params(axis='x', rotation=45, labelsize=8)
        elif w_type == "kpi":
            ax.axis('off')
            text = "\n".join([f"{k}: {v}" for k, v in data.items()])
            ax.text(0.5, 0.5, text, ha='center', va='center', fontsize=16, fontweight='bold', 
                    bbox=dict(facecolor='white', alpha=0.3, boxstyle='round'))

    def export_data(self, widgets_data: List[Dict[str, Any]], output_path: Path, format: str = 'excel'):
        """Exporte les données brutes des widgets en Excel ou CSV."""
        # On aplatit les données pour l'export
        flat_data = []
        for widget in widgets_data:
            w_name = widget.get('title', 'Sans titre')
            w_data = widget.get('data', {})
            
            if isinstance(w_data, dict):
                for k, v in w_data.items():
                    flat_data.append({'Widget': w_name, 'Metrique': k, 'Valeur': v})
            elif isinstance(w_data, list):
                for item in w_data:
                    if isinstance(item, dict):
                        row = {'Widget': w_name}
                        row.update(item)
                        flat_data.append(row)
                    else:
                        flat_data.append({'Widget': w_name, 'Valeur': item})

        df = pd.DataFrame(flat_data)
        
        if format == 'excel':
            df.to_excel(output_path, index=False)
            self.log(f"Données du dashboard exportées en Excel : {output_path}")
        else:
            df.to_csv(output_path, index=False, encoding='utf-8-sig')
            self.log(f"Données du dashboard exportées en CSV : {output_path}")
