"""Orchestrate metadata parsing, analysis, and report generation.

The :class:`SalesforceDocumentationGenerator` glues the parsers, analyzers
and writers together. It takes user configuration (output flags, language,
weights, exclusion files) and returns a fully populated
:class:`GenerationResult` so callers can introspect what was produced
without poking at a stringly-typed dictionary.
"""

from __future__ import annotations

import os
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from src.analyzer.engine import AnalyzerEngine, AnalyzerReport
from src.analyzer.rule_catalog import RuleCatalog
from src.core.ai_usage import (
    AIUsageEntry,
    AIUsageStats,
    compute_ai_usage_stats,
    scan_ai_usage,
)
from src.core.audit_generator import generate_audit_summary_rtf
from src.core.customization_metrics import (
    AdoptionStats,
    DataModelCustomisationStats,
    PostureCapabilityConfig,
    compute_adoption_stats,
    compute_data_model_stats,
)
from src.core.history_service import HistoryEntry, HistoryService
from src.core.index_card_visibility import IndexCardVisibility
from src.core.models import MetadataSnapshot, PmdViolation, TechnicalDebtItem, DeviationItem, InnovationItem
from src.core.utils import safe_slug
from src.core.pmd_service import PmdService
from src.parsers.salesforce_parser import SalesforceMetadataParser
from src.reporting.excel_writer import ExcelReportWriter
from src.reporting.html_writer import HtmlReportWriter
from src.reporting.word_writer import WordReportWriter
from src.reviewers.heuristics import review_apex_artifact, review_flow

LogCallback = Callable[[str], None]


@dataclass
class GenerationResult:
    """Structured payload returned by :meth:`SalesforceDocumentationGenerator.generate`.

    Every field is optional because the user can disable individual outputs
    (Excel, HTML, Word). Callers should check for ``None`` / empty mappings
    before reading.
    """

    snapshot: MetadataSnapshot | None = None
    analyzer_report: AnalyzerReport | None = None
    permission_excel: Path | None = None
    profile_excel: Path | None = None
    inventory_excel: Path | None = None
    data_dictionary_excels: list[Path] = field(default_factory=list)
    pmd_excel: Path | None = None
    data_dictionary_word: Path | None = None
    summary_word: Path | None = None
    index: Path | None = None
    ai_usage_page: Path | None = None
    ai_usage_entries: list[AIUsageEntry] = field(default_factory=list)
    ai_usage_stats: AIUsageStats | None = None
    data_model_stats: DataModelCustomisationStats | None = None
    adoption_stats: AdoptionStats | None = None
    customisation_page: Path | None = None
    adoption_page: Path | None = None
    debt_page: Path | None = None
    innovation_page: Path | None = None
    methodology_page: Path | None = None
    findings_report_page: Path | None = None
    object_pages: dict = field(default_factory=dict)
    apex_pages: dict = field(default_factory=dict)
    flow_pages: dict = field(default_factory=dict)
    omni_pages: dict = field(default_factory=dict)
    agent_pages: dict = field(default_factory=dict)
    prompt_pages: dict = field(default_factory=dict)
    listing_pages: dict = field(default_factory=dict)
    security_pages: dict = field(default_factory=dict)
    excel_preview_pages: dict = field(default_factory=dict)

    # The UI historically consumed this object via ``result["index"]``-style
    # subscripts. The two helpers below keep that contract working without
    # forcing every existing call site to migrate at once.
    def __getitem__(self, item: str):
        return getattr(self, item)

    def get(self, item: str, default=None):
        return getattr(self, item, default)


class SalesforceDocumentationGenerator:
    """High-level entry point that produces every report from a metadata folder."""

    def __init__(
        self,
        source_dir: str | Path,
        output_dir: str | Path,
        exclusion_config_path: str | Path | None = None,
        pmd_enabled: bool = False,
        pmd_ruleset_path: str | Path | None = None,
        generate_excels: bool = True,
        generate_html: bool = True,
        generate_data_dictionary_word: bool = True,
        generate_summary_word: bool = True,
        generate_audit_summary_rtf: bool = True,
        scoring_weights: dict[str, int] | None = None,
        adopt_adapt_weights: dict[str, int] | None = None,
        scoring_thresholds: tuple[int, int, int] | None = None,
        adopt_adapt_thresholds: tuple[int, int, int] | None = None,
        data_model_thresholds: tuple[int, int, int] | None = None,
        profiles_thresholds: tuple[int, int, int] | None = None,
        profiles_ps_ratio_thresholds: tuple[int, int, int] | None = None,
        analyzer_rules_path: str | Path | None = None,
        ai_usage_tags: list[str] | tuple[str, ...] | None = None,
        posture_config: list[PostureCapabilityConfig] | None = None,
        test_coverage_data: dict[str, float] | None = None,
        technical_debt_path: str | Path | None = None,
        innovation_path: str | Path | None = None,
        index_card_visibility: IndexCardVisibility | None = None,
        language: str = "fr",
        log_callback: LogCallback | None = None,
    ) -> None:
        self.source_dir = Path(source_dir).resolve()
        self.output_dir = Path(output_dir).resolve()
        self.exclusion_config_path = (
            Path(exclusion_config_path).resolve() if exclusion_config_path else None
        )
        self.pmd_enabled = pmd_enabled
        self.pmd_ruleset_path = (
            Path(pmd_ruleset_path).resolve() if pmd_ruleset_path else None
        )
        self.generate_excels = generate_excels
        self.generate_html = generate_html
        self.generate_data_dictionary_word = generate_data_dictionary_word
        self.generate_summary_word = generate_summary_word
        self.generate_audit_summary_rtf = generate_audit_summary_rtf
        self.scoring_weights = scoring_weights
        self.adopt_adapt_weights = adopt_adapt_weights
        self.scoring_thresholds = scoring_thresholds
        self.adopt_adapt_thresholds = adopt_adapt_thresholds
        self.data_model_thresholds = data_model_thresholds
        self.profiles_thresholds = profiles_thresholds
        self.profiles_ps_ratio_thresholds = profiles_ps_ratio_thresholds
        self.analyzer_rules_path = (
            Path(analyzer_rules_path).resolve() if analyzer_rules_path else None
        )
        self.ai_usage_tags: list[str] = [
            tag.strip()
            for tag in (ai_usage_tags or [])
            if isinstance(tag, str) and tag.strip()
        ]
        self.posture_config: list[PostureCapabilityConfig] = list(posture_config or [])
        self.test_coverage_data = test_coverage_data or {}
        self.technical_debt_path = (
            Path(technical_debt_path).resolve() if technical_debt_path else None
        )
        self.innovation_path = (
            Path(innovation_path).resolve() if innovation_path else None
        )
        self.index_card_visibility: IndexCardVisibility = (
            index_card_visibility
            if index_card_visibility is not None
            else IndexCardVisibility()
        )
        # Language drives the localisation of the Word documents we generate
        # (data dictionary + summary). Falls back to French if the value is
        # not one of the supported codes.
        self.language = language if language in {"fr", "en"} else "fr"
        self.log: LogCallback = log_callback or (lambda message: None)
        self.alias = ""  # Will be set by the caller if needed for history

    # ------------------------------------------------------------------
    # History persistence
    # ------------------------------------------------------------------

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
            app_root = Path(__file__).resolve().parent.parent.parent
            db_path = app_root / "history.db"
            service = HistoryService(db_path)
            
            metrics = snapshot.metrics
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

            entry = HistoryEntry(
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
            
            service.add_entry(entry)
            self.log(f"Résultats enregistrés dans l'historique pour l'alias '{self.alias}'.")
        except Exception as exc:
            self.log(f"Erreur lors de l'enregistrement dans l'historique : {exc}")

    # ------------------------------------------------------------------
    # Safe wrappers
    # ------------------------------------------------------------------

    def _safe_run(self, label: str, producer: Callable[[], object]) -> object | None:
        """Run ``producer`` and surface any failure via the log callback.

        Used to isolate Excel/Word writer failures so a single broken
        artefact does not abort the whole generation.
        """

        try:
            return producer()
        except Exception as exc:
            self.log(f"Echec generation {label}: {exc}")
            return None

    # ------------------------------------------------------------------
    # Pipeline steps
    # ------------------------------------------------------------------

    def _generate_excels(
        self,
        snapshot: MetadataSnapshot,
        excel_writer: ExcelReportWriter,
        excel_dir: Path,
        result: GenerationResult,
    ) -> None:
        self.log("Generation des classeurs Excel de documentation.")
        result.permission_excel = self._safe_run(
            "permission_sets.xlsx",
            lambda: excel_writer.write_security_workbook(
                snapshot.permission_sets,
                excel_dir / "permission_sets.xlsx",
                "Classeur Permission Sets",
            ),
        )
        result.profile_excel = self._safe_run(
            "profiles.xlsx",
            lambda: excel_writer.write_security_workbook(
                snapshot.profiles,
                excel_dir / "profiles.xlsx",
                "Classeur Profiles",
            ),
        )
        result.inventory_excel = self._safe_run(
            "metadata_inventory.xlsx",
            lambda: excel_writer.write_inventory_workbook(
                snapshot.inventory,
                excel_dir / "metadata_inventory.xlsx",
            ),
        )
        result.data_dictionary_excels = (
            self._safe_run(
                "data_dictionary.xlsx",
                lambda: excel_writer.write_data_dictionary_workbooks(
                    snapshot.objects, excel_dir
                ),
            )
            or []
        )

    def _run_pmd(
        self,
        snapshot: MetadataSnapshot,
        excel_writer: ExcelReportWriter,
        excel_dir: Path,
        result: GenerationResult,
        pmd_by_artifact: dict[str, list[PmdViolation]],
    ) -> None:
        pmd_service = PmdService(self.source_dir, log_callback=self.log)
        pmd_result = pmd_service.analyze_apex(
            snapshot.apex_artifacts,
            ruleset_path=self.pmd_ruleset_path,
        )
        for violation in pmd_result.violations:
            for artifact in snapshot.apex_artifacts:
                if artifact.source_path.resolve() == violation.file_path.resolve():
                    pmd_by_artifact.setdefault(artifact.name, []).append(violation)
                    break
        if self.generate_excels:
            result.pmd_excel = self._safe_run(
                "pmd_violations.xlsx",
                lambda: excel_writer.write_pmd_workbook(
                    pmd_by_artifact,
                    excel_dir / "pmd_violations.xlsx",
                ),
            )

    def _generate_word(
        self,
        snapshot: MetadataSnapshot,
        analyzer_report: AnalyzerReport,
        result: GenerationResult,
    ) -> None:
        self.log("Generation des documents Word.")
        word_dir = self.output_dir / "word"
        word_dir.mkdir(parents=True, exist_ok=True)
        word_writer = WordReportWriter(language=self.language, log_callback=self.log)

        if self.generate_data_dictionary_word:
            result.data_dictionary_word = self._safe_run(
                "data_dictionary.docx",
                lambda: word_writer.write_data_dictionary_document(
                    snapshot, word_dir / "data_dictionary.docx"
                ),
            )
        
        if self.generate_summary_word:
            result.summary_word = self._safe_run(
                "summary.docx",
                lambda: word_writer.write_summary_document(
                    snapshot, analyzer_report, word_dir / "summary.docx"
                ),
            )

        # Generate RTF Audit Summary
        if self.generate_audit_summary_rtf:
            self._safe_run(
                "audit_summary.rtf",
                lambda: generate_audit_summary_rtf(
                    snapshot, snapshot.metrics, word_dir / "audit_summary.rtf"
                ),
            )


    def _generate_html(
        self,
        snapshot: MetadataSnapshot,
        analyzer_report: AnalyzerReport,
        apex_reviews: dict,
        flow_reviews: dict,
        pmd_by_artifact: dict[str, list[PmdViolation]],
        result: GenerationResult,
    ) -> None:
        self.log("Generation des pages HTML.")
        html_writer = HtmlReportWriter(self.output_dir, log_callback=self.log)
        html_writer.write_assets()

        # Pre-calculate predictable paths for circular linking
        apex_pages = {
            art.name: html_writer.apex_dir / f"{safe_slug(art.name)}.html"
            for art in snapshot.apex_artifacts
        }
        flow_pages = {
            flow.name: html_writer.flows_dir / f"{safe_slug(flow.name)}.html"
            for flow in snapshot.flows
        }
        object_pages = {
            obj.api_name: html_writer.objects_dir / f"{obj.api_name}.html"
            for obj in snapshot.objects
        }

        result.object_pages = html_writer.write_object_pages(
            snapshot, 
            analyzer_report=analyzer_report,
            apex_pages=apex_pages,
            flow_pages=flow_pages,
        )
        result.apex_pages = html_writer.write_apex_pages(
            snapshot,
            apex_reviews,
            pmd_by_artifact,
            analyzer_report=analyzer_report,
        )
        result.flow_pages = html_writer.write_flow_pages(
            snapshot,
            flow_reviews,
            result.object_pages,
            result.apex_pages,
            analyzer_report=analyzer_report,
        )
        result.omni_pages = html_writer.write_omni_pages(
            snapshot, analyzer_report=analyzer_report
        )
        result.agent_pages, result.prompt_pages = html_writer.write_ai_pages(
            snapshot, analyzer_report=analyzer_report
        )
        result.excel_preview_pages = html_writer.write_excel_preview_pages()
        result.ai_usage_page = html_writer.write_ai_usage_page(
            result.ai_usage_entries,
            tags=self.ai_usage_tags,
            stats=result.ai_usage_stats,
        )
        result.customisation_page = html_writer.write_customisation_page(
            snapshot, result.data_model_stats
        )
        result.adoption_page = html_writer.write_adoption_page(
            snapshot, result.adoption_stats
        )
        result.debt_page = html_writer.write_debt_page(snapshot)
        result.innovation_page = html_writer.write_innovation_page(snapshot)
        result.security_pages = html_writer.write_security_pages(
            snapshot, analyzer_report=analyzer_report
        )
        result.methodology_page = html_writer.write_methodology_page(
            posture_config=self.posture_config,
            data_model_thresholds=self.data_model_thresholds,
            profiles_thresholds=self.profiles_thresholds,
        )
        result.findings_report_page = html_writer.write_findings_report_page(
            analyzer_report,
            result.object_pages,
            result.apex_pages,
            result.flow_pages,
            agent_pages=result.agent_pages,
            prompt_pages=result.prompt_pages,
            omni_pages=result.omni_pages,
        )
        result.listing_pages = html_writer.write_listing_pages(
            snapshot,
            result.object_pages,
            result.apex_pages,
            result.flow_pages,
            result.omni_pages,
            result.agent_pages,
            result.prompt_pages,
        )
        result.security_pages = html_writer.write_security_pages(
            snapshot,
            analyzer_report=analyzer_report,
        )
        result.index = html_writer.write_index(
            snapshot,
            result.object_pages,
            result.apex_pages,
            result.flow_pages,
            apex_reviews,
            flow_reviews,
            pmd_by_artifact,
            omni_pages=result.omni_pages,
            agent_pages=result.agent_pages,
            prompt_pages=result.prompt_pages,
            listing_pages=result.listing_pages,
            security_pages=result.security_pages,
            analyzer_report=analyzer_report,
            ai_usage_entries=result.ai_usage_entries,
            ai_usage_page=result.ai_usage_page,
            ai_usage_stats=result.ai_usage_stats,
            data_model_stats=result.data_model_stats,
            adoption_stats=result.adoption_stats,
            customisation_page=result.customisation_page,
            adoption_page=result.adoption_page,
            debt_page=result.debt_page,
            innovation_page=result.innovation_page,
            findings_report_page=result.findings_report_page,
            card_visibility=self.index_card_visibility,
            alias=self.alias,
        )

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def generate(self) -> GenerationResult:
        import time
        start_time = time.time()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.log("Debut de l'analyse Salesforce.")

        parser = SalesforceMetadataParser(
            self.source_dir,
            exclusion_config_path=self.exclusion_config_path,
            log_callback=self.log,
        )
        snapshot = parser.parse()
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

        # Apply test coverage data
        has_test_classes = any(a.is_test for a in snapshot.apex_artifacts)
        has_components = (len(snapshot.flows) > 0 or any(not a.is_test for a in snapshot.apex_artifacts))
        
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

        # Load technical debt and deviations
        if self.technical_debt_path:
            if self.technical_debt_path.exists():
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
            else:
                self.log(f"Avertissement : le fichier de dette technique {self.technical_debt_path} n'existe pas.")

        # Load innovations
        if self.innovation_path:
            if self.innovation_path.exists():
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
                                    not_started=item.get("not_started", False)
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
            else:
                self.log(f"Avertissement : le fichier d'innovations {self.innovation_path} n'existe pas.")

        self.log("Lecture des metadata terminee.")

        result = GenerationResult(snapshot=snapshot)

        excel_writer = ExcelReportWriter(log_callback=self.log)
        excel_dir = self.output_dir / "excel"

        if self.generate_excels:
            self._generate_excels(snapshot, excel_writer, excel_dir, result)
        else:
            self.log("Generation des Excels desactivee dans la configuration.")

        if not self.generate_html:
            self.log("Generation HTML desactivee dans la configuration.")

        apex_reviews = {
            artifact.name: review_apex_artifact(artifact)
            for artifact in snapshot.apex_artifacts
        }
        flow_reviews = {flow.name: review_flow(flow) for flow in snapshot.flows}
        pmd_by_artifact: dict[str, list[PmdViolation]] = {
            artifact.name: [] for artifact in snapshot.apex_artifacts
        }

        if self.pmd_enabled:
            self._run_pmd(
                snapshot, excel_writer, excel_dir, result, pmd_by_artifact
            )

        self.log("Chargement du catalogue de regles analyzer.")
        analyzer_catalog = RuleCatalog.load(self.analyzer_rules_path)
        enabled_count = len(analyzer_catalog.enabled)
        total_count = len(analyzer_catalog.all)
        self.log(
            f"Catalogue analyzer : {enabled_count}/{total_count} regles actives."
        )
        analyzer_engine = AnalyzerEngine(analyzer_catalog, exclusion_path=self.exclusion_config_path)
        analyzer_report = analyzer_engine.analyze_snapshot(snapshot)
        result.analyzer_report = analyzer_report
        snapshot.findings_summary = analyzer_report.severity_counts()
        self.log(
            f"Analyseur : {len(analyzer_report.all_findings())} finding(s) detecte(s)."
        )

        if self.ai_usage_tags:
            result.ai_usage_entries = scan_ai_usage(snapshot, self.ai_usage_tags)
            self.log(
                "Usage IA : "
                f"{len(result.ai_usage_entries)} occurrence(s) de tag detectee(s) "
                f"(tags suivis : {', '.join(self.ai_usage_tags)})."
            )
        else:
            result.ai_usage_entries = []
            self.log("Usage IA : aucun tag configure, evaluation par defaut (0 tagge).")

        result.ai_usage_stats = compute_ai_usage_stats(
            snapshot, result.ai_usage_entries
        )
        snapshot.ai_usage_stats = result.ai_usage_stats
        stats = result.ai_usage_stats
        self.log(
            "Univers personnalisation/code/lowcode : "
            f"{stats.total} element(s), "
            f"avec tag IA = {stats.with_tag_count} ({stats.percent_with_tag:.1f} %), "
            f"sans tag IA = {stats.without_tag_count} ({stats.percent_without_tag:.1f} %)."
        )

        result.data_model_stats = compute_data_model_stats(snapshot)
        snapshot.data_model_stats = result.data_model_stats
        dm_stats = result.data_model_stats
        self.log(
            "Empreinte data model : "
            f"objets custom = {dm_stats.custom_objects}/{dm_stats.total_objects} "
            f"({dm_stats.percent_custom_objects:.1f} %), "
            f"champs custom = {dm_stats.custom_fields}/{dm_stats.total_fields} "
            f"({dm_stats.percent_custom_fields:.1f} %), "
            f"global custom = {dm_stats.percent_custom_global:.1f} %."
        )

        result.adoption_stats = compute_adoption_stats(
            snapshot, self.posture_config or None
        )
        snapshot.adoption_stats = result.adoption_stats
        adoption = result.adoption_stats
        self.log(
            "Posture Adopt vs Adapt : "
            f"adoption = {adoption.percent_adoption:.1f} % "
            f"({adoption.adopt_count}/{adoption.total_count} capacites), "
            f"adaptation = {adoption.percent_adaptation:.1f} % "
            f"(low {adoption.adapt_low_count}, high {adoption.adapt_high_count})."
        )

        self._generate_word(snapshot, analyzer_report, result)

        if self.generate_html:
            self._generate_html(
                snapshot,
                analyzer_report,
                apex_reviews,
                flow_reviews,
                pmd_by_artifact,
                result,
            )

        self._save_to_history(snapshot, result, analyzer_report)

        end_time = time.time()
        duration = end_time - start_time
        minutes = int(duration // 60)
        seconds = int(duration % 60)
        time_str = f"{minutes} min {seconds} s" if minutes > 0 else f"{seconds} s"
        
        self.log(f"Generation terminee en {time_str}.")
        return result
