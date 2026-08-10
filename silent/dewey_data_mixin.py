"""Data collection, page-shaped accessors, and export logic mixed into Dewey."""

from __future__ import annotations

import csv
import io
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from .dewey_comparison import _classify, _quality_specs


class DeweyDataMixin:
    """Collects analysis results into page-shaped dictionaries and exposes export()."""

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
