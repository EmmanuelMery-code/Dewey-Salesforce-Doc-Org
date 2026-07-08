import json
import csv
import io
import sys
import inspect
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from datetime import datetime

# Ajouter la racine du projet au sys.path pour permettre les imports depuis src
# On remonte de 2 niveaux car on est dans silent/dewey.py
root_path = Path(__file__).resolve().parent.parent
if str(root_path) not in sys.path:
    sys.path.insert(0, str(root_path))

try:
    # Importer les composants nécessaires du projet
    from src.core.orchestrator.generator import SalesforceDocumentationGenerator
    from src.core.history_service import HistoryEntry
    from src.core.customization_metrics import PostureCapabilityConfig
except ImportError as e:
    # Si l'import échoue, on essaie d'ajouter le répertoire courant au cas où
    sys.path.insert(0, str(Path.cwd()))
    from src.core.orchestrator.generator import SalesforceDocumentationGenerator
    from src.core.history_service import HistoryEntry
    from src.core.customization_metrics import PostureCapabilityConfig

def _classify(old_v, new_v, direction):
    """Return (delta, status) for a metric given its 'good' direction."""
    if old_v is None or new_v is None:
        return None, "neutral"
    delta = new_v - old_v
    if direction == "up_good":
        status = "improvement" if delta > 0 else ("regression" if delta < 0 else "stable")
    elif direction == "down_good":
        status = "improvement" if delta < 0 else ("regression" if delta > 0 else "stable")
    else:
        status = "neutral"
    return delta, status

def _quality_specs(old: HistoryEntry, new: HistoryEntry):
    """Metrics whose degradation is a genuine regression."""
    def ratio(e: HistoryEntry):
        if e.apex_business_classes:
            return e.apex_test_classes / e.apex_business_classes * 100
        return None

    return [
        ("Couverture de tests globale", old.test_coverage, new.test_coverage, "up_good", True, "Majeur"),
        ("Couverture Apex", old.test_coverage_apex, new.test_coverage_apex, "up_good", True, "Majeur"),
        ("Couverture Flows", old.test_coverage_flows, new.test_coverage_flows, "up_good", True, "Mineur"),
        ("Ratio classes de test / métier", ratio(old), ratio(new), "up_good", True, "Mineur"),
        ("Findings critiques", old.findings_critical, new.findings_critical, "down_good", False, "Critique"),
        ("Findings majeurs", old.findings_major, new.findings_major, "down_good", False, "Majeur"),
        ("Findings mineurs", old.findings_minor, new.findings_minor, "down_good", False, "Mineur"),
        ("Findings total", old.findings_total, new.findings_total, "down_good", False, "Mineur"),
    ]

class Dewey:
    """
    Objet Dewey permettant d'extraire les chiffres et métriques de l'analyse Salesforce
    sans générer les pages HTML, tout en offrant des capacités d'export.
    """

    def __init__(
        self,
        config: Union[str, Path, Dict[str, Any]],
        source_dir: Optional[Union[str, Path]] = None,
        output_dir: Optional[Union[str, Path]] = None,
        alias: Optional[str] = None,
        verbosity: str = "silent",  # "silent", "steps", "details"
        use_history: bool = True
    ):
        self.verbosity = verbosity.lower()
        self.use_history = use_history
        self.params = {}
        
        # Charger la configuration interne de Dewey
        dewey_json_path = Path(__file__).resolve().parent / "dewey.json"
        with open(dewey_json_path, 'r', encoding='utf-8') as f:
            self.internal_config = json.load(f)

        if isinstance(config, (str, Path)):
            with open(config, 'r', encoding='utf-8') as f:
                self.params = json.load(f)
        elif isinstance(config, dict):
            self.params = config.copy()
            
        if source_dir:
            self.params['source_dir'] = str(source_dir)
        if output_dir:
            self.params['output_dir'] = str(output_dir)
        if alias:
            self.params['alias'] = alias

        # Si l'historique est désactivé, on force certains paramètres
        if not self.use_history:
            self.params['include_comparison'] = False

        # Appliquer le mapping configuré dans dewey.json
        mapping = self.internal_config.get('mapping', {})
        for old_key, new_key in mapping.items():
            if old_key in self.params and new_key not in self.params:
                self.params[new_key] = self.params.pop(old_key)

        if 'source_dir' not in self.params:
            raise ValueError("Le paramètre 'source_dir' (ou 'source_folder') est requis pour l'analyse.")
            
        # Appliquer les paramètres par défaut configurés dans dewey.json
        defaults = self.internal_config.get('defaults', {})
        for key, value in defaults.items():
            self.params.setdefault(key, value)

        # Filtrer les paramètres pour ne passer que ceux acceptés par SalesforceDocumentationGenerator
        sig = inspect.signature(SalesforceDocumentationGenerator.__init__)
        valid_params = [p.name for p in sig.parameters.values() if p.name != 'self']
        
        filtered_params = {k: v for k, v in self.params.items() if k in valid_params}
        
        # Gérer les types spécifiques (tuples pour les seuils)
        for key in ['scoring_thresholds', 'adopt_adapt_thresholds', 'data_model_thresholds', 
                    'profiles_thresholds', 'profiles_ps_ratio_thresholds']:
            if key in filtered_params and isinstance(filtered_params[key], list):
                filtered_params[key] = tuple(filtered_params[key])

        # Gérer posture_config (doit être une liste de PostureCapabilityConfig)
        if 'posture_config' in filtered_params and isinstance(filtered_params['posture_config'], dict):
            capabilities = filtered_params['posture_config'].get('capabilities', [])
            from src.core.customization_metrics import PostureCapabilityConfig, CapabilityLevel
            
            p_configs = []
            for c in capabilities:
                # Convertir le niveau (str) en Enum CapabilityLevel si présent
                if c.get('level'):
                    try:
                        c['level'] = CapabilityLevel(c['level'])
                    except ValueError:
                        # Si la valeur n'est pas reconnue, on laisse l'assesseur décider
                        c['level'] = None
                p_configs.append(PostureCapabilityConfig(**c))
            
            filtered_params['posture_config'] = p_configs

        # Configurer le callback de log en fonction de la verbosité
        filtered_params['log_callback'] = self._log_callback

        self._generator = SalesforceDocumentationGenerator(**filtered_params)
        
        # Désactiver la sauvegarde en base de données si demandé
        if not self.use_history:
            self._generator._save_to_history = lambda *args, **kwargs: None

        self._result = None
        self._data = {}

    def _log_callback(self, message: str):
        """Gère l'affichage des messages en fonction de la verbosité."""
        if self.verbosity == "silent":
            return
            
        # Détection heuristique des étapes majeures
        major_steps = [
            "Debut de l'analyse",
            "Lecture des metadata terminee",
            "Catalogue analyzer",
            "Usage IA",
            "Empreinte data model",
            "Posture Adopt vs Adapt",
            "Generation terminee"
        ]
        
        is_major = any(step in message for step in major_steps)
        
        if self.verbosity == "steps" and is_major:
            print(f"[Dewey] {message}")
        elif self.verbosity == "details":
            print(f"[Dewey] {message}")

    def _run_analysis(self):
        """Exécute l'analyse si ce n'est pas déjà fait."""
        if self._result is not None:
            return
            
        try:
            self._result = self._generator.generate()
            self._collect_data()
        except Exception as e:
            import traceback
            if self.verbosity != "silent":
                print(f"DEBUG: Erreur lors de generate(): {e}")
                traceback.print_exc()
            raise

    def _flow_elements_coverage(self, flows) -> List[Dict[str, Any]]:
        """
        Construit, pour chaque flow, le detail de la couverture de tests par element
        (quel(s) element(s) sont testes et par quelle(s) classe(s) Apex).

        Cette information n'est disponible que si la generation de la couverture de
        tests a ete activee (voir 'test_coverage' dans la configuration).
        """
        result = []
        for flow in flows:
            elements = flow.elements or []
            total = len(elements)
            covered_elements = [e for e in elements if e.covered_by]
            covered = len(covered_elements)
            pct = (covered / total * 100) if total > 0 else None

            result.append({
                "flow": flow.name,
                "couverture_globale_pct": flow.test_coverage,
                "blocs_couverts": flow.test_coverage_elements_covered,
                "blocs_total": (
                    flow.test_coverage_elements_covered + flow.test_coverage_elements_uncovered
                ),
                "elements_total": total,
                "elements_couverts": covered,
                "elements_couverts_pct": pct,
                "elements": [
                    {
                        "nom": e.name,
                        "type": e.element_type,
                        "label": e.label,
                        "teste": bool(e.covered_by),
                        "classes_test": list(e.covered_by),
                    }
                    for e in elements
                ],
            })
        return result

    def _collect_data(self):
        """Collecte toutes les informations exposées dans les différentes pages du rapport."""
        snapshot = self._result.snapshot
        metrics = snapshot.metrics
        report = self._result.analyzer_report
        
        from dataclasses import asdict

        def _to_dict(obj):
            if obj is None:
                return {}
            try:
                return asdict(obj)
            except TypeError:
                # Si ce n'est pas une dataclass, on essaie __dict__ ou on retourne l'objet tel quel
                return getattr(obj, '__dict__', str(obj))

        # --- 1. Comparaison (comparaison.html) ---
        comparison = {}
        if self.params.get('include_comparison'):
            entries = self._generator._load_alias_entries()
            old = self._generator._resolve_comparison_old_entry(entries)
            if old:
                new_entry = self._generator._build_history_entry(snapshot, self._result, report)
                regressions = []
                for label, old_v, new_v, direction, is_pct, severity in _quality_specs(old, new_entry):
                    delta, status = _classify(old_v, new_v, direction)
                    if status == "regression":
                        regressions.append({
                            "indicateur": label,
                            "ancien": old_v,
                            "nouveau": new_v,
                            "ecart": delta,
                            "severite": severity
                        })
                comparison = {
                    "regressions_count": len(regressions),
                    "regressions": regressions,
                    "comparaison_avec_generation": old.generation_number,
                    "date_precedente": old.timestamp,
                    "source_precedente": old.source_dir
                }

        # --- 2. Index (index.html) ---
        index_sections = {
            "Description": {
                "custom_objects": metrics.custom_objects,
                "custom_fields": metrics.custom_fields,
                "flows": metrics.flows,
                "apex_classes": metrics.apex_classes,
                "apex_triggers": metrics.apex_triggers,
                "lwc": metrics.lwc_count,
                "aura": len(snapshot.aura),
                "omni_components": (
                    metrics.omni_scripts + metrics.omni_integration_procedures +
                    metrics.omni_ui_cards + metrics.omni_data_transforms +
                    metrics.bre_decision_matrices + metrics.bre_expression_sets
                ),
                "einstein_predictions": metrics.einstein_predictions,
                "agents": metrics.agents,
                "prompts": metrics.gen_ai_prompts,
                "sharing_rules": metrics.sharing_rules,
                "duplicate_rules": metrics.duplicate_rules,
                # Détails pour Description
                "details": {
                    "objects": [_to_dict(o) for o in snapshot.objects],
                    "lwc": [_to_dict(l) for l in snapshot.lwc],
                    "aura": [_to_dict(a) for a in snapshot.aura]
                }
            },
            "Scoring": {
                "score": metrics.score,
                "score_no_code": metrics.score_no_code,
                "score_low_code": metrics.score_low_code,
                "score_pro_code": metrics.score_pro_code,
                "niveau": metrics.level,
                "adopt_vs_adapt_score": metrics.adopt_adapt_score,
                "adopt_vs_adapt_niveau": metrics.adopt_adapt_level
            },
            "Métriques": {
                "findings_total": len(report.all_findings()) if report else 0,
                "ai_usage_pct": self._result.ai_usage_stats.percent_with_tag if self._result.ai_usage_stats else 0,
                "data_model_custom_pct": self._result.data_model_stats.percent_custom_global if self._result.data_model_stats else 0,
                "adoption_pct": self._result.adoption_stats.percent_adoption if self._result.adoption_stats else 0,
                "test_coverage": metrics.test_coverage
            },
            "IA": {
                "usage_stats": _to_dict(self._result.ai_usage_stats),
                "predictions": metrics.einstein_predictions,
                "agents": metrics.agents,
                "prompts": metrics.gen_ai_prompts,
                "details": {
                    "agents": [_to_dict(a) for a in snapshot.agents],
                    "prompts": [_to_dict(p) for p in snapshot.gen_ai_prompts]
                }
            },
            "Profile & PS": {
                "custom_profiles": metrics.custom_profiles_count,
                "permission_sets": metrics.permission_sets_count,
                "ratio_ps_profiles": metrics.profiles_ps_ratio_score,
                "niveau_securite": metrics.profiles_ps_ratio_level,
                "details": {
                    "profiles": [_to_dict(p) for p in snapshot.profiles],
                    "permission_sets": [_to_dict(ps) for ps in snapshot.permission_sets]
                }
            },
            "sharing rules": {
                "count": metrics.sharing_rules,
                "items": [_to_dict(sr) for sr in snapshot.sharing_rules]
            },
            "Apex Trigger": {
                "count": metrics.apex_classes + metrics.apex_triggers,
                "items": [_to_dict(a) for a in snapshot.apex_artifacts]
            },
            "Flow": {
                "count": metrics.flows,
                "items": [_to_dict(f) for f in snapshot.flows],
                # Couverture des elements de flow par classe(s) de test Apex
                # (equivalent de la colonne "Teste par" des pages HTML de flow)
                "couverture_elements": self._flow_elements_coverage(snapshot.flows)
            },
            "omni BRE": (
                metrics.omni_scripts + metrics.omni_integration_procedures +
                metrics.omni_ui_cards + metrics.omni_data_transforms +
                metrics.bre_decision_matrices + metrics.bre_expression_sets
            ),
            "prompt": {
                "count": metrics.gen_ai_prompts,
                "items": [_to_dict(p) for p in snapshot.gen_ai_prompts]
            },
            "agents": {
                "count": metrics.agents,
                "items": [_to_dict(a) for a in snapshot.agents]
            },
            "dépendances": {
                "count": len(snapshot.dependencies),
                "items": [_to_dict(d) for d in snapshot.dependencies]
            },
            "Améliorations": {
                "count": len(snapshot.deviations),
                "items": [_to_dict(d) for d in snapshot.deviations]
            },
            "Qualité PMD": {
                "summary": snapshot.findings_summary,
            },
            "Com Orphelin": {
                "count": len(snapshot.orphans),
                "items": [_to_dict(o) for o in snapshot.orphans]
            }
        }

        self._data = {
            "comparaison": comparison,
            "index": index_sections,
            "findings_report": {
                "total": len(report.all_findings()) if report else 0,
                "counts": report.severity_counts() if report else {},
                "findings": [_to_dict(f) for f in report.all_findings()] if report else []
            },
            "ai_usage": {
                "stats": _to_dict(self._result.ai_usage_stats),
                "entries": [_to_dict(e) for e in self._result.ai_usage_entries]
            },
            "customisation": _to_dict(self._result.data_model_stats),
            "adoption": _to_dict(self._result.adoption_stats),
            "debt": {
                "total_items": len(snapshot.technical_debt),
                "items": [_to_dict(d) for d in snapshot.technical_debt]
            },
            "innovation": {
                "total_items": len(snapshot.innovations),
                "items": [_to_dict(i) for i in snapshot.innovations]
            }
        }

    @property
    def comparaison(self) -> Dict[str, Any]:
        self._run_analysis()
        return self._data["comparaison"]

    @property
    def index(self) -> Dict[str, Any]:
        self._run_analysis()
        return self._data["index"]

    @property
    def findings_report(self) -> Dict[str, Any]:
        self._run_analysis()
        return self._data["findings_report"]

    @property
    def ai_usage(self) -> Dict[str, Any]:
        self._run_analysis()
        return self._data["ai_usage"]

    @property
    def customisation(self) -> Dict[str, Any]:
        self._run_analysis()
        return self._data["customisation"]

    @property
    def adoption(self) -> Dict[str, Any]:
        self._run_analysis()
        return self._data["adoption"]

    @property
    def debt(self) -> Dict[str, Any]:
        self._run_analysis()
        return self._data["debt"]

    @property
    def innovation(self) -> Dict[str, Any]:
        self._run_analysis()
        return self._data["innovation"]

    @property
    def chiffres(self) -> Dict[str, Any]:
        """Retourne l'ensemble des chiffres collectés."""
        self._run_analysis()
        return self._data

    def export(self, format: str = "json", path: Optional[Union[str, Path]] = None) -> str:
        """
        Exporte les données au format JSON ou CSV.
        """
        self._run_analysis()
        
        if format.lower() == "json":
            content = json.dumps(self._data, indent=4, default=str)
        elif format.lower() == "csv":
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(["Page/Section", "Indicateur", "Valeur"])
            
            if self._data["comparaison"]:
                writer.writerow(["comparaison", "regressions_count", self._data["comparaison"]["regressions_count"]])
                for reg in self._data["comparaison"]["regressions"]:
                    writer.writerow(["comparaison/regression", reg["indicateur"], f"{reg['ancien']} -> {reg['nouveau']} ({reg['severite']})"])

            for section, values in self._data["index"].items():
                if isinstance(values, dict):
                    for k, v in values.items():
                        writer.writerow([f"index/{section}", k, v])
                else:
                    writer.writerow(["index", section, values])
            
            for page in ["ai_usage", "customisation", "adoption"]:
                for k, v in self._data[page].items():
                    if not isinstance(v, (dict, list)):
                        writer.writerow([page, k, v])
            
            for sev, count in self._data["findings_report"]["counts"].items():
                writer.writerow(["findings_report", sev, count])
                    
            content = output.getvalue()
        else:
            raise ValueError("Le format doit être 'json' ou 'csv'.")
            
        if path:
            with open(path, 'w', encoding='utf-8', newline='') as f:
                f.write(content)
                
        return content
