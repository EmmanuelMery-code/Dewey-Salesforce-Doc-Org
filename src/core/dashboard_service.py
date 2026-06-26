from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional
from src.core.models import MetadataSnapshot

@dataclass
class DashboardWidget:
    id: str
    label: str
    chart_type: str  # 'pie', 'bar', 'kpi', 'line', 'text'
    description: str = ""
    query: str = "" # SQL query for history.db
    text: str = "" # For text widgets
    rich_text: Optional[List[Dict[str, Any]]] = None # For rich text segments
    text_align: str = "left" # 'left', 'center', 'right'
    text_valign: str = "top" # 'top', 'center', 'bottom'
    table_columns: List[str] = field(default_factory=list)
    table_rows: List[str] = field(default_factory=list)
    table_font_name: str = "Arial"
    table_font_size: int = 8
    image_path: str = ""
    image_font_size: int = 50
    image_font_color: str = "#000000"
    emoji: str = ""
    condition: str = "" # SQL condition (e.g. "adoption_pct > 80")
    kpi_decimals: int = 1 # Number of decimals for KPI values
    z_order: int = 0 # Display order (higher is on top)
    linked_dashboard: str = "" # Name of another dashboard to include
    x: int = 0
    y: int = 0
    w: int = 1
    h: int = 1
    color: str = "#3498db"

@dataclass
class DashboardConfig:
    name: str
    widgets: List[DashboardWidget] = field(default_factory=list)

class DashboardService:
    """Service pour collecter les données du dashboard et gérer les configurations."""

    QUERY_TEMPLATES = {
        "Synthèse Findings (Dernière)": "SELECT findings_total, findings_critical, findings_major, findings_minor, findings_info FROM history WHERE alias = :alias ORDER BY timestamp DESC LIMIT 1",
        "Évolution du Score (Top 20)": "SELECT timestamp as label, score as value FROM history WHERE alias = :alias ORDER BY timestamp ASC LIMIT 20",
        "Top 10 Objets Custom": "SELECT alias as label, custom_objects as value FROM history WHERE alias = :alias ORDER BY timestamp DESC LIMIT 10",
        "Croissance Metadata (Objets+Champs)": "SELECT timestamp as label, (custom_objects + custom_fields) as value FROM history WHERE alias = :alias ORDER BY timestamp ASC LIMIT 20",
        "Répartition Adoption (Dernière)": "SELECT 'Adoption' as label, adoption_pct as value FROM history WHERE alias = :alias UNION SELECT 'Adaptation', adaptation_pct FROM history WHERE alias = :alias ORDER BY timestamp DESC LIMIT 2",
        "Répartition Objets (Dernière)": "SELECT 'Custom' as label, custom_objects as value FROM (SELECT * FROM history WHERE alias = :alias ORDER BY timestamp DESC LIMIT 1) UNION ALL SELECT 'Standard', standard_objects FROM (SELECT * FROM history WHERE alias = :alias ORDER BY timestamp DESC LIMIT 1)",
        "Répartition Champs (Dernière)": "SELECT 'Custom' as label, custom_fields as value FROM (SELECT * FROM history WHERE alias = :alias ORDER BY timestamp DESC LIMIT 1) UNION ALL SELECT 'Standard', standard_fields FROM (SELECT * FROM history WHERE alias = :alias ORDER BY timestamp DESC LIMIT 1)",
        "Détail Sévérité PMD": "SELECT 'Critique' as label, findings_critical as value FROM history WHERE alias = :alias UNION SELECT 'Majeur', findings_major FROM history WHERE alias = :alias UNION SELECT 'Mineur', findings_minor FROM history WHERE alias = :alias",
        "Évolution Findings (Stacked)": "SELECT timestamp as label, findings_critical, findings_major, findings_minor, findings_info FROM history WHERE alias = :alias ORDER BY timestamp ASC LIMIT 20",
        "Top 4 Findings (Tableau)": "SELECT timestamp as 'Date', findings_critical as 'Critical', findings_major AS 'Major', findings_minor AS 'Minor', findings_info AS 'Info' FROM history WHERE alias = :alias ORDER BY timestamp DESC LIMIT 4",
        "Répartition Score (Dernière)": "SELECT 'No-code' as label, score_no_code as value FROM (SELECT * FROM history WHERE alias = :alias ORDER BY timestamp DESC LIMIT 1) UNION ALL SELECT 'Low-code', score_low_code FROM (SELECT * FROM history WHERE alias = :alias ORDER BY timestamp DESC LIMIT 1) UNION ALL SELECT 'Pro-code', score_pro_code FROM (SELECT * FROM history WHERE alias = :alias ORDER BY timestamp DESC LIMIT 1)",
        "Répartition Adopt vs Adapt (Dernière)": "SELECT 'Adopt (No-code)' as label, adopt_adapt_score_no_code as value FROM (SELECT * FROM history WHERE alias = :alias ORDER BY timestamp DESC LIMIT 1) UNION ALL SELECT 'Adapt (Low-code)', adopt_adapt_score_low_code FROM (SELECT * FROM history WHERE alias = :alias ORDER BY timestamp DESC LIMIT 1) UNION ALL SELECT 'Adapt (Pro-code)', adopt_adapt_score_pro_code FROM (SELECT * FROM history WHERE alias = :alias ORDER BY timestamp DESC LIMIT 1)",
        "Posture d'Adoption (Dernière)": "SELECT 'Adopt (OOTB)' as label, adopt_ootb_count as value FROM (SELECT * FROM history WHERE alias = :alias ORDER BY timestamp DESC LIMIT 1) UNION ALL SELECT 'Adopt (Décl.)', adopt_decl_count FROM (SELECT * FROM history WHERE alias = :alias ORDER BY timestamp DESC LIMIT 1) UNION ALL SELECT 'Adapt (Low)', adapt_low_count FROM (SELECT * FROM history WHERE alias = :alias ORDER BY timestamp DESC LIMIT 1) UNION ALL SELECT 'Adapt (High)', adapt_high_count FROM (SELECT * FROM history WHERE alias = :alias ORDER BY timestamp DESC LIMIT 1)",
        "Évolution Posture d'Adoption (Stacked)": "SELECT timestamp as label, adopt_ootb_count, adopt_decl_count, adapt_low_count, adapt_high_count FROM history WHERE alias = :alias ORDER BY timestamp ASC LIMIT 20",
        "Compteurs Metadata (Dernière)": "SELECT 'Record Types' as label, record_types as value FROM (SELECT * FROM history WHERE alias = :alias ORDER BY timestamp DESC LIMIT 1) UNION ALL SELECT 'Validation Rules', validation_rules FROM (SELECT * FROM history WHERE alias = :alias ORDER BY timestamp DESC LIMIT 1) UNION ALL SELECT 'Page Layouts', page_layouts FROM (SELECT * FROM history WHERE alias = :alias ORDER BY timestamp DESC LIMIT 1) UNION ALL SELECT 'Tabs', custom_tabs FROM (SELECT * FROM history WHERE alias = :alias ORDER BY timestamp DESC LIMIT 1) UNION ALL SELECT 'Apps', custom_apps FROM (SELECT * FROM history WHERE alias = :alias ORDER BY timestamp DESC LIMIT 1)",
        "Exemple Condition: Alerte Findings": "findings_critical > 0",
        "Exemple Condition: Adoption Faible": "adoption_pct < 50",
        "Exemple Condition: Adoption Haute": "adoption_pct > 80",
    }

    def __init__(self, snapshot: Optional[MetadataSnapshot] = None, db_path: Optional[Path] = None):
        self.snapshot = snapshot
        self.db_path = db_path or Path(__file__).resolve().parent.parent.parent / "history.db"
        self.config_path = Path(__file__).resolve().parent.parent.parent / "dashboards.json"
        self.widgets: List[DashboardWidget] = self._init_default_widgets()

    def _init_default_widgets(self) -> List[DashboardWidget]:
        return [
            DashboardWidget("findings_summary", "Synthèse des Findings", "bar", 
                            "Répartition des alertes par sévérité (Dernière analyse)",
                            "SELECT findings_total, findings_critical, findings_major, findings_minor, findings_info FROM history WHERE alias = :alias ORDER BY timestamp DESC LIMIT 1",
                            x=0, y=0, w=2, h=1, color="#e74c3c"),
            DashboardWidget("obj_dist", "Répartition Objets", "pie", "Objets Standards vs Custom",
                            "SELECT 'Custom' as label, custom_objects as value FROM (SELECT * FROM history WHERE alias = :alias ORDER BY timestamp DESC LIMIT 1) UNION ALL SELECT 'Standard', standard_objects FROM (SELECT * FROM history WHERE alias = :alias ORDER BY timestamp DESC LIMIT 1)",
                            x=0, y=1, w=1, h=1),
            DashboardWidget("score_evolution", "Évolution du Score", "line", "Tendance du score global",
                            "SELECT timestamp as label, score as value FROM history WHERE alias = :alias ORDER BY timestamp ASC LIMIT 20",
                            x=1, y=1, w=1, h=1, color="#2ecc71"),
            DashboardWidget("donut_example", "Donut : Objets", "donut", "Exemple de graphique en anneau",
                            "SELECT 'Custom' as label, custom_objects as value FROM history WHERE alias = :alias ORDER BY timestamp DESC LIMIT 1",
                            x=0, y=2, w=1, h=1, color="#9b59b6"),
            DashboardWidget("area_example", "Aire : Croissance", "area", "Exemple de graphique à aires",
                            "SELECT timestamp as label, (custom_objects + custom_fields) as value FROM history WHERE alias = :alias ORDER BY timestamp ASC LIMIT 20",
                            x=1, y=2, w=1, h=1, color="#3498db"),
            DashboardWidget("findings_evolution", "Évolution des Findings", "stacked_bar", "Tendance des alertes par sévérité",
                            "SELECT timestamp as label, findings_critical, findings_major, findings_minor, findings_info FROM history WHERE alias = :alias ORDER BY timestamp ASC LIMIT 20",
                            x=0, y=3, w=2, h=1, color="#e74c3c,#e67e22,#f1c40f,#3498db"),
            DashboardWidget("table_example", "Derniers Findings", "table", "Tableau des dernières alertes",
                            "SELECT timestamp, findings_critical, findings_major, findings_minor FROM history WHERE alias = :alias ORDER BY timestamp DESC LIMIT 5",
                            table_columns=["findings_critical", "findings_major", "findings_minor"],
                            table_rows=["timestamp"],
                            x=0, y=4, w=2, h=1),
        ]

    def load_configs(self) -> Dict[str, DashboardConfig]:
        if not self.config_path.exists():
            return {}
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                configs = {}
                for name, cfg in data.items():
                    widgets = []
                    for w in cfg.get('widgets', []):
                        # Filtrer les clés inconnues pour éviter les erreurs de dataclass
                        valid_keys = DashboardWidget.__dataclass_fields__.keys()
                        filtered_w = {k: v for k, v in w.items() if k in valid_keys}
                        widgets.append(DashboardWidget(**filtered_w))
                    configs[name] = DashboardConfig(name=name, widgets=widgets)
                return configs
        except Exception as e:
            print(f"Erreur chargement configs dashboard: {e}")
            return {}

    def save_configs(self, configs: Dict[str, DashboardConfig]):
        try:
            data = {name: {"name": c.name, "widgets": [asdict(w) for w in c.widgets]} 
                    for name, c in configs.items()}
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Erreur sauvegarde configs dashboard: {e}")

    def get_widget_data(self, widget: DashboardWidget, alias: str = "") -> Dict[str, Any]:
        """Récupère les données soit par SQL soit par Snapshot."""
        # Évaluation de la condition de visibilité
        visible = True
        if widget.condition and self.db_path.exists():
            try:
                # On construit une requête qui renvoie 1 si la condition est vraie sur la dernière entrée
                cond_query = f"SELECT ({widget.condition}) as cond FROM history WHERE alias = :alias ORDER BY timestamp DESC LIMIT 1"
                res = self._execute_sql_raw(cond_query, {"alias": alias})
                if res and not res[0].get('cond'):
                    visible = False
            except Exception as e:
                print(f"Erreur évaluation condition: {e}")

        if not visible:
            return {"visible": False}

        if widget.chart_type == "text":
            return {"text": widget.text, "visible": True}
        
        if widget.chart_type == "table" and widget.query and self.db_path.exists():
            try:
                raw_rows = self._execute_sql_raw(widget.query, {"alias": alias})
                return {"rows": raw_rows, "visible": True}
            except Exception as e:
                print(f"Erreur SQL Table Dashboard: {e}")
                return {"rows": [], "visible": True}

        if widget.query and self.db_path.exists():
            try:
                raw_rows = self._execute_sql_raw(widget.query, {"alias": alias})
                if not raw_rows: return {"visible": True}

                result = {"visible": True}
                if widget.chart_type == "stacked_bar":
                    labels = []
                    series_keys = [k for k in raw_rows[0].keys() if k not in ('label', 'timestamp')]
                    series_data = {k: [] for k in series_keys}
                    for r in raw_rows:
                        labels.append(str(r.get('label') or r.get('timestamp') or ''))
                        for k in series_keys:
                            series_data[k].append(r[k] or 0)
                    result.update({"labels": labels, "series": series_data})
                    return result

                # Fallback pour les autres types (pie, bar, line, area, kpi)
                if len(raw_rows) == 1 and len(raw_rows[0].keys()) >= 2:
                    keys = list(raw_rows[0].keys())
                    if 'label' not in keys or 'value' not in keys:
                        for k, v in raw_rows[0].items():
                            if k not in ('id', 'alias', 'timestamp', 'visible'):
                                result[k] = v if v is not None else 0
                        return result
                
                for row in raw_rows:
                    keys = list(row.keys())
                    # Priorité aux colonnes 'label' ou 'timestamp' pour l'axe X
                    label_key = 'label' if 'label' in keys else ('timestamp' if 'timestamp' in keys else keys[0])
                    
                    if 'value' in keys:
                        val = row['value']
                        result[str(row[label_key])] = val if val is not None else 0
                    elif len(keys) >= 2:
                        # Si on a plusieurs colonnes, on prend la 2ème comme valeur par défaut
                        val_key = keys[1] if label_key == keys[0] else keys[0]
                        result[str(row[label_key])] = row[val_key] if row[val_key] is not None else 0
                    else:
                        result[str(row[label_key])] = row[label_key] if row[label_key] is not None else 0
                return result
            except Exception as e:
                print(f"Erreur SQL Dashboard: {e}")
                return {"visible": True}

        if not self.snapshot:
            return {"visible": True}

        # Logique fallback snapshot
        res = {"visible": True}
        if widget.id == "obj_dist":
            c = len([o for o in self.snapshot.objects if o.custom])
            res.update({"Standard": len(self.snapshot.objects) - c, "Custom": c})
        elif widget.id == "field_dist":
            c = sum(len([f for f in o.fields if f.custom]) for o in self.snapshot.objects)
            s = sum(len([f for f in o.fields if not f.custom]) for o in self.snapshot.objects)
            res.update({"Standard": s, "Custom": c})
        
        return res

    def _execute_sql_raw(self, query: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()
            return [dict(r) for r in rows]
