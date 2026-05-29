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
    description: str
    query: str = "" # SQL query for history.db
    text: str = "" # For text widgets
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
        "Détail Sévérité PMD": "SELECT 'Critique' as label, findings_critical as value FROM history WHERE alias = :alias UNION SELECT 'Majeur', findings_major FROM history WHERE alias = :alias UNION SELECT 'Mineur', findings_minor FROM history WHERE alias = :alias",
        "Évolution Findings (Stacked)": "SELECT timestamp as label, findings_critical, findings_major, findings_minor, findings_info FROM history WHERE alias = :alias ORDER BY timestamp ASC LIMIT 20",
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
                            "SELECT 'Custom' as label, custom_objects as value FROM history WHERE alias = :alias ORDER BY timestamp DESC LIMIT 1",
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
        if widget.chart_type == "text":
            return {"text": widget.text}

        if widget.query and self.db_path.exists():
            try:
                raw_rows = self._execute_sql_raw(widget.query, {"alias": alias})
                if not raw_rows: return {}

                if widget.chart_type == "stacked_bar":
                    labels = []
                    series_keys = [k for k in raw_rows[0].keys() if k not in ('label', 'timestamp')]
                    series_data = {k: [] for k in series_keys}
                    for r in raw_rows:
                        labels.append(str(r.get('label') or r.get('timestamp') or ''))
                        for k in series_keys:
                            series_data[k].append(r[k] or 0)
                    return {"labels": labels, "series": series_data}

                # Fallback pour les autres types (pie, bar, line, area, kpi)
                if len(raw_rows) == 1 and len(raw_rows[0].keys()) > 2:
                    return {k: raw_rows[0][k] for k in raw_rows[0].keys() if raw_rows[0][k] is not None}
                
                result = {}
                for row in raw_rows:
                    keys = list(row.keys())
                    if 'label' in keys and 'value' in keys:
                        result[str(row['label'])] = row['value']
                    elif len(keys) >= 2:
                        result[str(row[keys[0]])] = row[keys[1]]
                    elif len(keys) == 1:
                        result[keys[0]] = row[keys[0]]
                return result
            except Exception as e:
                print(f"Erreur SQL Dashboard: {e}")
                return {}

        if not self.snapshot:
            return {}

        # Logique fallback snapshot
        if widget.id == "obj_dist":
            c = len([o for o in self.snapshot.objects if o.custom])
            return {"Standard": len(self.snapshot.objects) - c, "Custom": c}
        if widget.id == "field_dist":
            c = sum(len([f for f in o.fields if f.custom]) for o in self.snapshot.objects)
            s = sum(len([f for f in o.fields if not f.custom]) for o in self.snapshot.objects)
            return {"Standard": s, "Custom": c}
        
        return {}

    def _execute_sql_raw(self, query: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()
            return [dict(r) for r in rows]
