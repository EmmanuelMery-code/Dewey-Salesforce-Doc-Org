"""Snapshot post-processing: config, test coverage, debt and innovations."""

from __future__ import annotations

import json

from src.core.models import (
    DeviationItem,
    InnovationItem,
    MetadataSnapshot,
    TechnicalDebtItem,
)
from src.core.orchestrator.base import _OrchestratorState


class _DataLoadingMixin(_OrchestratorState):
    """Enrich a parsed :class:`MetadataSnapshot` with user-provided data."""

    def _apply_snapshot_config(self, snapshot: MetadataSnapshot) -> None:
        """Apply scoring weights / thresholds and innovation colours."""
        snapshot.innovation_colors = dict(self.innovation_colors)
        if self.scoring_weights:
            snapshot.metrics.weights = dict(self.scoring_weights)
        if self.adopt_adapt_weights:
            snapshot.metrics.adopt_adapt_weights = dict(self.adopt_adapt_weights)
        if self.scoring_thresholds:
            snapshot.metrics.scoring_thresholds = tuple(self.scoring_thresholds)
        if self.adopt_adapt_thresholds:
            snapshot.metrics.adopt_adapt_thresholds = tuple(self.adopt_adapt_thresholds)
        if self.data_model_thresholds:
            snapshot.metrics.data_model_thresholds = tuple(self.data_model_thresholds)
        if self.profiles_thresholds:
            snapshot.metrics.profiles_thresholds = tuple(self.profiles_thresholds)
        if self.profiles_ps_ratio_thresholds:
            snapshot.metrics.profiles_ps_ratio_thresholds = tuple(self.profiles_ps_ratio_thresholds)

    def _apply_test_coverage(self, snapshot: MetadataSnapshot) -> None:
        """Populate per-artifact coverage and the org-level average."""
        total_covered = 0.0
        count = 0

        # Collect coverage data for non-test artifacts
        for artifact in snapshot.apex_artifacts:
            if artifact.name in self.test_coverage_data:
                coverage_info = self.test_coverage_data[artifact.name]
                if isinstance(coverage_info, dict):
                    # New format with detailed coverage info
                    artifact.test_coverage = coverage_info.get("percentage")
                    artifact.test_coverage_lines_covered = coverage_info.get("lines_covered", 0)
                    artifact.test_coverage_lines_uncovered = coverage_info.get("lines_uncovered", 0)
                else:
                    # Old format (just percentage) - fallback for compatibility
                    artifact.test_coverage = coverage_info
                    artifact.test_coverage_lines_covered = 0
                    artifact.test_coverage_lines_uncovered = 0

                if not artifact.is_test and artifact.test_coverage is not None:
                    total_covered += artifact.test_coverage
                    count += 1

        for flow in snapshot.flows:
            if flow.name in self.test_coverage_data:
                coverage_info = self.test_coverage_data[flow.name]
                if isinstance(coverage_info, dict):
                    # New format with detailed coverage info
                    flow.test_coverage = coverage_info.get("percentage")
                    flow.test_coverage_elements_covered = coverage_info.get("elements_covered", 0)
                    flow.test_coverage_elements_uncovered = coverage_info.get("elements_uncovered", 0)
                else:
                    # Old format (just percentage) - fallback for compatibility
                    flow.test_coverage = coverage_info
                    flow.test_coverage_elements_covered = 0
                    flow.test_coverage_elements_uncovered = 0

                if flow.test_coverage is not None:
                    total_covered += flow.test_coverage
                    count += 1

        # Calculate org-level test coverage
        if count > 0:
            # Coverage data found for some components
            snapshot.metrics.test_coverage = total_covered / count
            self.log(f"Couverture de tests org calculee : {snapshot.metrics.test_coverage:.1f} % ({count} composants).")
        else:
            # No coverage data found - default to 0
            snapshot.metrics.test_coverage = 0.0
            self.log("Aucune donnee de couverture de tests trouvee.")

        if snapshot.metrics.test_coverage is not None:
            self.log(f"Couverture de tests finale : {snapshot.metrics.test_coverage:.1f} %.")

    def _load_technical_debt(self, snapshot: MetadataSnapshot) -> None:
        """Load technical debt and deviations from the configured JSON file."""
        if not self.technical_debt_path:
            return
        if not self.technical_debt_path.exists():
            self.log(f"Avertissement : le fichier de dette technique {self.technical_debt_path} n'existe pas.")
            return
        try:
            with open(self.technical_debt_path, "r", encoding="utf-8") as f:
                debt_data = json.load(f)

            alias = (self.alias or "").strip()
            self.log(f"Recherche de la dette technique pour l'alias '{alias}' dans {self.technical_debt_path}...")

            # 1. Try exact match
            alias_data = debt_data.get(alias)

            # 2. Try flexible match if not found
            if alias_data is None and alias:
                for key in debt_data.keys():
                    if key.strip().lower() == alias.lower():
                        alias_data = debt_data[key]
                        self.log(f"Alias '{alias}' trouve via correspondance flexible avec '{key}' pour la dette.")
                        break

            # 3. If still not found, partial match
            if alias_data is None and alias:
                for key in debt_data.keys():
                    if key.lower() in alias.lower() or alias.lower() in key.lower():
                        alias_data = debt_data[key]
                        self.log(f"Alias '{alias}' trouve via correspondance partielle avec '{key}' pour la dette.")
                        break

            if alias_data and isinstance(alias_data, dict):
                technical_items = alias_data.get("technical_debt", [])
                for item in technical_items:
                    snapshot.technical_debt.append(TechnicalDebtItem(
                        label=item.get("label", ""),
                        date_creation=item.get("date_creation", ""),
                        date_resolution=item.get("date_resolution", ""),
                        accepted_solution=item.get("accepted_solution", ""),
                        target_solution=item.get("target_solution", "")
                    ))

                deviation_items = alias_data.get("deviations", [])
                for item in deviation_items:
                    snapshot.deviations.append(DeviationItem(
                        label=item.get("label", ""),
                        date_creation=item.get("date_creation", ""),
                        explanation=item.get("explanation", "")
                    ))

                self.log(f"Charge {len(snapshot.technical_debt)} element(s) de dette technique et {len(snapshot.deviations)} entorse(s) pour l'alias '{alias}'.")
            else:
                self.log(f"Aucune donnee de dette trouvee pour l'alias '{alias}' dans le fichier JSON.")
                if debt_data:
                    self.log(f"Alias disponibles dans le fichier de dette : {', '.join(debt_data.keys())}")
        except Exception as e:
            self.log(f"Avertissement : impossible de charger la dette technique : {e}")

    def _load_innovations(self, snapshot: MetadataSnapshot) -> None:
        """Load innovations from the configured JSON file."""
        if not self.innovation_path:
            return
        if not self.innovation_path.exists():
            self.log(f"Avertissement : le fichier d'innovations {self.innovation_path} n'existe pas.")
            return
        try:
            with open(self.innovation_path, "r", encoding="utf-8") as f:
                innovation_data = json.load(f)

            alias = (self.alias or "").strip()
            self.log(f"Recherche des innovations pour l'alias '{alias}' (longueur {len(alias)}) dans {self.innovation_path}...")

            # 1. Try exact match
            innovation_items = innovation_data.get(alias)

            # 2. Try flexible match if not found
            if innovation_items is None and alias:
                for key in innovation_data.keys():
                    if key.strip().lower() == alias.lower():
                        innovation_items = innovation_data[key]
                        self.log(f"Alias '{alias}' trouve via correspondance flexible avec '{key}'.")
                        break

            # 3. If still not found, maybe the key is a substring or vice versa
            if innovation_items is None and alias:
                for key in innovation_data.keys():
                    if key.lower() in alias.lower() or alias.lower() in key.lower():
                        innovation_items = innovation_data[key]
                        self.log(f"Alias '{alias}' trouve via correspondance partielle avec '{key}'.")
                        break

            if innovation_items:
                if isinstance(innovation_items, list):
                    for item in innovation_items:
                        snapshot.innovations.append(InnovationItem(
                            label=item.get("label", ""),
                            theme=item.get("theme", ""),
                            date_start=item.get("date_start", ""),
                            date_end=item.get("date_end", ""),
                            date_presentation=item.get("date_presentation", ""),
                            description=item.get("description", ""),
                            conclusion=item.get("conclusion", ""),
                            not_started=item.get("not_started", False),
                            color=item.get("color", ""),
                        ))
                    self.log(f"Charge {len(snapshot.innovations)} element(s) d'innovation pour l'alias '{alias}'.")
                else:
                    self.log(f"Avertissement : les innovations pour '{alias}' ne sont pas au format liste.")
            else:
                self.log(f"Aucune innovation trouvee pour l'alias '{alias}' dans le fichier JSON.")
                if innovation_data:
                    self.log(f"Alias disponibles dans le fichier : {', '.join(innovation_data.keys())}")
        except Exception as e:
            self.log(f"Avertissement : impossible de charger les innovations : {e}")
