from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from matplotlib.figure import Figure
import pandas as pd

from src.reporting.dashboard_exporter_charts import _DashboardChartsMixin
from src.reporting.dashboard_exporter_pptx import _DashboardPptxMixin

class DashboardExporter(_DashboardChartsMixin, _DashboardPptxMixin):
    """Service pour l'exportation des tableaux de bord vers différents formats.
    
    Supporte :
    - PDF (via Matplotlib)
    - PNG (avec ou sans transparence)
    - PowerPoint (PPTX)
    - Excel (XLSX)
    - CSV

    Le rendu des widgets individuels (graphiques Matplotlib) vit dans
    ``_DashboardChartsMixin`` et l'export PowerPoint dans ``_DashboardPptxMixin``.
    """

    def __init__(self, log_callback=None):
        self.log = log_callback or (lambda msg: None)
        # Configuration globale des polices Matplotlib pour supporter les émojis
        try:
            import matplotlib.pyplot as plt
            emoji_fonts = ["Segoe UI Emoji", "Apple Color Emoji", "Noto Color Emoji", "Symbola", "Segoe UI Symbol"]
            current_sans = list(plt.rcParams.get('font.sans-serif', []))
            for f in reversed(emoji_fonts):
                if f not in current_sans:
                    current_sans.insert(0, f)
            plt.rcParams['font.sans-serif'] = current_sans
            plt.rcParams['font.family'] = 'sans-serif'
            plt.rcParams['mathtext.fontset'] = 'cm'
            plt.rcParams['axes.unicode_minus'] = False
        except: pass

    def export_to_pdf(self, fig: Figure, output_path: Path):
        """Exporte la figure Matplotlib en PDF."""
        fig.savefig(output_path, format='pdf', bbox_inches='tight')
        self.log(f"Dashboard exporté en PDF : {output_path}")

    def export_to_png(self, fig: Figure, output_path: Path, transparent: bool = False):
        """Exporte la figure Matplotlib en PNG."""
        fig.savefig(output_path, format='png', bbox_inches='tight', transparent=transparent)
        self.log(f"Dashboard exporté en PNG ({'transparent' if transparent else 'opaque'}) : {output_path}")

    def export_data(self, widgets_data: List[Dict[str, Any]], output_path: Path, format: str = 'excel'):
        """Exporte les données brutes des widgets en Excel ou CSV."""
        # On aplatit les données pour l'export
        flat_data = []
        for widget in widgets_data:
            w_name = widget.get('title', 'Sans titre')
            w_data = widget.get('data', {})
            
            if isinstance(w_data, dict) and "rows" in w_data:
                for row_dict in w_data["rows"]:
                    row = {'Widget': w_name}
                    row.update(row_dict)
                    flat_data.append(row)
            elif isinstance(w_data, dict):
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
