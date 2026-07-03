"""History persistence for the documentation generator."""

from __future__ import annotations

import os
from pathlib import Path

from src.analyzer.engine import AnalyzerReport
from src.core.history_service import HistoryEntry, HistoryService
from src.core.models import MetadataSnapshot
from src.core.orchestrator.base import _OrchestratorState
from src.core.orchestrator.result import GenerationResult


class _HistoryMixin(_OrchestratorState):
    """Persist a generation run into the SQLite history database."""

    def _calculate_apex_coverage_avg(self, snapshot: MetadataSnapshot) -> float | None:
        """Calculate average test coverage for Apex classes/triggers (excluding tests)."""
        apex_coverage_avg = 0.0
        apex_count = 0
        for artifact in snapshot.apex_artifacts:
            if not artifact.is_test and artifact.test_coverage is not None:
                apex_coverage_avg += artifact.test_coverage
                apex_count += 1
        if apex_count > 0:
            return apex_coverage_avg / apex_count
        return None

    def _calculate_flows_coverage_avg(self, snapshot: MetadataSnapshot) -> float | None:
        """Calculate average test coverage for Flows."""
        flow_coverage_avg = 0.0
        flow_count = 0
        for flow in snapshot.flows:
            if flow.test_coverage is not None:
                flow_coverage_avg += flow.test_coverage
                flow_count += 1
        if flow_count > 0:
            return flow_coverage_avg / flow_count
        return None

    def _build_history_entry(
        self,
        snapshot: MetadataSnapshot,
        result: GenerationResult,
        analyzer_report: AnalyzerReport,
    ) -> HistoryEntry:
        """Build a HistoryEntry from the current run (without persisting it).

        Extracted so the comparison step can obtain the metrics of the
        generation in progress before it is saved to the database.
        """
        app_root = Path(__file__).resolve().parent.parent.parent.parent

        metrics = snapshot.metrics
        apex_triggers = sum(
            1 for a in snapshot.apex_artifacts if a.kind == "trigger"
        )
        apex_test_classes = sum(
            1 for a in snapshot.apex_artifacts
            if a.kind == "class" and a.is_test
        )
        apex_business_classes = sum(
            1 for a in snapshot.apex_artifacts
            if a.kind == "class" and not a.is_test
        )
        ai_stats = result.ai_usage_stats
        dm_stats = result.data_model_stats
        adoption_stats = result.adoption_stats
        sev_counts = analyzer_report.severity_counts()

        # Convert paths to relative to app_root
        def to_rel(p: Path | str) -> str:
            try:
                rel = os.path.relpath(p, app_root)
                return rel.replace('\\', '/')
            except Exception:
                return str(p).replace('\\', '/')

        return HistoryEntry(
                alias=self.alias,
                source_dir=to_rel(self.source_dir),
                output_dir=to_rel(self.output_dir),
                score=metrics.score,
                score_no_code=metrics.score_no_code,
                score_low_code=metrics.score_low_code,
                score_pro_code=metrics.score_pro_code,
                adopt_adapt_score=metrics.adopt_adapt_score,
                adopt_adapt_score_no_code=metrics.adopt_adapt_score_no_code,
                adopt_adapt_score_low_code=metrics.adopt_adapt_score_low_code,
                adopt_adapt_score_pro_code=metrics.adopt_adapt_score_pro_code,
                custom_objects=dm_stats.custom_objects if dm_stats else metrics.custom_objects,
                standard_objects=dm_stats.standard_objects if dm_stats else 0,
                custom_fields=dm_stats.custom_fields if dm_stats else metrics.custom_fields,
                standard_fields=dm_stats.standard_fields if dm_stats else 0,
                flows=metrics.flows,
                record_types=metrics.record_types,
                validation_rules=metrics.validation_rules,
                page_layouts=metrics.layouts,
                custom_tabs=metrics.custom_tabs,
                custom_apps=metrics.custom_apps,
                total_custom_components=(
                    metrics.custom_objects + metrics.custom_fields + metrics.record_types +
                    metrics.validation_rules + metrics.layouts + metrics.custom_tabs +
                    metrics.custom_apps + metrics.flows + metrics.apex_classes +
                    metrics.apex_triggers + metrics.omni_scripts +
                    metrics.omni_integration_procedures + metrics.omni_ui_cards +
                    metrics.omni_data_transforms + metrics.agents +
                    metrics.gen_ai_prompts + metrics.einstein_predictions +
                    metrics.sharing_rules + metrics.duplicate_rules +
                    metrics.lwc_count + len(snapshot.aura)
                ),
                total_standard_components=(
                    (dm_stats.standard_objects + dm_stats.standard_fields) if dm_stats else 0
                ),
                adopt_ootb_count=adoption_stats.adopt_ootb_count if adoption_stats else 0,
                adopt_decl_count=adoption_stats.adopt_declarative_count if adoption_stats else 0,
                adapt_low_count=adoption_stats.adapt_low_count if adoption_stats else 0,
                adapt_high_count=adoption_stats.adapt_high_count if adoption_stats else 0,
                apex_classes_triggers=metrics.apex_classes + metrics.apex_triggers,
                apex_triggers=apex_triggers,
                apex_test_classes=apex_test_classes,
                apex_business_classes=apex_business_classes,
                omni_components=(
                    metrics.omni_scripts +
                    metrics.omni_integration_procedures +
                    metrics.omni_ui_cards +
                    metrics.omni_data_transforms
                ),
                agents=metrics.agents,
                gen_ai_prompts=metrics.gen_ai_prompts,
                einstein_predictions=metrics.einstein_predictions,
                sharing_rules=metrics.sharing_rules,
                duplicate_rules=metrics.duplicate_rules,
                lwc_count=metrics.lwc_count,
                aura_count=len(snapshot.aura),
                findings_total=len(analyzer_report.all_findings()),
                findings_critical=sev_counts.get("Critical", 0),
                findings_major=sev_counts.get("Major", 0),
                findings_minor=sev_counts.get("Minor", 0),
                findings_info=sev_counts.get("Info", 0),
                ai_usage_pct=ai_stats.percent_with_tag if ai_stats else 0.0,
                data_model_custom_pct=dm_stats.percent_custom_global if dm_stats else 0.0,
                data_model_standard_pct=dm_stats.percent_standard_global if dm_stats else 0.0,
                adoption_pct=adoption_stats.percent_adoption if adoption_stats else 0.0,
                adaptation_pct=adoption_stats.percent_adaptation if adoption_stats else 0.0,
                test_coverage=metrics.test_coverage,
                test_coverage_apex=self._calculate_apex_coverage_avg(snapshot),
                test_coverage_flows=self._calculate_flows_coverage_avg(snapshot),
            )

    def _save_to_history(
        self,
        snapshot: MetadataSnapshot,
        result: GenerationResult,
        analyzer_report: AnalyzerReport,
    ) -> None:
        """Save the generation results to the SQLite history database."""
        if not self.alias:
            return
        try:
            app_root = Path(__file__).resolve().parent.parent.parent.parent
            service = HistoryService(app_root / "history.db")
            entry = self._build_history_entry(snapshot, result, analyzer_report)
            service.add_entry(entry)
            self.log(f"Résultats enregistrés dans l'historique pour l'alias '{self.alias}'.")
        except Exception as exc:
            self.log(f"Erreur lors de l'enregistrement dans l'historique : {exc}")

    def _load_alias_entries(self) -> list[HistoryEntry]:
        """Return existing history entries for the current alias (desc by gen)."""
        if not self.alias:
            return []
        try:
            app_root = Path(__file__).resolve().parent.parent.parent.parent
            service = HistoryService(app_root / "history.db")
            return service.list_entries_for_alias(self.alias)
        except Exception:
            return []

    def _resolve_comparison_old_entry(
        self, entries: list[HistoryEntry]
    ) -> HistoryEntry | None:
        """Pick the generation to compare against (explicit target or previous)."""
        if not entries:
            return None
        target = (getattr(self, "comparison_target", "auto") or "auto").strip()
        if target != "auto" and target.isdigit():
            for entry in entries:
                if entry.generation_number == int(target):
                    return entry
        return entries[0]

    def _generate_comparison_page(
        self,
        snapshot: MetadataSnapshot,
        result: GenerationResult,
        analyzer_report: AnalyzerReport,
    ) -> tuple[Path | None, int | None]:
        """If enabled, render ``html/comparison.html`` vs a previous generation.

        Returns ``(page_path, regression_count)`` or ``(None, None)`` when the
        option is disabled or no previous generation exists for the alias.
        """
        if not getattr(self, "include_comparison", False):
            return None, None

        entries = self._load_alias_entries()
        old = self._resolve_comparison_old_entry(entries)
        if old is None:
            self.log(
                "Comparaison demandée mais aucune génération antérieure "
                f"n'existe pour l'alias '{self.alias}'."
            )
            return None, None

        from datetime import datetime

        from src.core.utils import write_text
        from src.reporting.html.renderers.history_reports import (
            comparison_regression_count,
            render_comparison,
        )

        new_entry = self._build_history_entry(snapshot, result, analyzer_report)
        # The real generation number is assigned at save time; approximate it
        # for display as "latest existing + 1".
        latest = entries[0].generation_number if entries else 0
        new_entry.generation_number = latest + 1
        new_entry.timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        html_dir = self.output_dir / "html"
        html_dir.mkdir(parents=True, exist_ok=True)
        page_path = html_dir / "comparison.html"
        assets_dir = html_dir / "assets"
        try:
            content = render_comparison(new_entry, old, page_path, assets_dir)
            write_text(page_path, content)
            regressions = comparison_regression_count(old, new_entry)
            self.log(
                f"Comparaison avec la génération #{old.generation_number} "
                f"générée ({regressions} régression(s)) : {page_path}"
            )
            return page_path, regressions
        except Exception as exc:
            self.log(f"Echec de la génération de la comparaison : {exc}")
            return None, None
