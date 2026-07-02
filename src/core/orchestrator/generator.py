"""High-level entry point that produces every report from a metadata folder."""

from __future__ import annotations

from pathlib import Path

from src.analyzer.engine import AnalyzerEngine
from src.analyzer.rule_catalog import RuleCatalog
from src.core.ai_usage import compute_ai_usage_stats, scan_ai_usage
from src.core.customization_metrics import (
    PostureCapabilityConfig,
    compute_adoption_stats,
    compute_data_model_stats,
)
from src.core.index_card_visibility import IndexCardVisibility
from src.core.models import PmdViolation
from src.core.orchestrator.base import LogCallback
from src.core.orchestrator.data_loading_mixin import _DataLoadingMixin
from src.core.orchestrator.history_mixin import _HistoryMixin
from src.core.orchestrator.result import GenerationResult
from src.core.orchestrator.steps_mixin import _StepsMixin
from src.parsers.salesforce_parser import SalesforceMetadataParser
from src.reporting.excel_writer import ExcelReportWriter
from src.reviewers.heuristics import review_apex_artifact, review_flow


class SalesforceDocumentationGenerator(
    _HistoryMixin, _StepsMixin, _DataLoadingMixin
):
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
        innovation_colors: dict[str, str] | None = None,
        index_card_visibility: IndexCardVisibility | None = None,
        one_page_max_depth: int | None = None,
        one_page_hub_threshold: int | None = None,
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
        self.ai_usage_tags = [
            tag.strip()
            for tag in (ai_usage_tags or [])
            if isinstance(tag, str) and tag.strip()
        ]
        self.posture_config = list(posture_config or [])
        self.test_coverage_data = test_coverage_data or {}
        self.technical_debt_path = (
            Path(technical_debt_path).resolve() if technical_debt_path else None
        )
        self.innovation_path = (
            Path(innovation_path).resolve() if innovation_path else None
        )
        self.innovation_colors = innovation_colors or {}
        self.one_page_max_depth = one_page_max_depth
        self.one_page_hub_threshold = one_page_hub_threshold
        self.index_card_visibility = (
            index_card_visibility
            if index_card_visibility is not None
            else IndexCardVisibility()
        )
        # Language drives the localisation of the Word documents we generate
        # (data dictionary + summary). Falls back to French if the value is
        # not one of the supported codes.
        self.language = language if language in {"fr", "en"} else "fr"
        self.log = log_callback or (lambda message: None)
        self.alias = ""  # Will be set by the caller if needed for history

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def generate(self) -> GenerationResult:
        import time
        start_time = time.time()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.log("Debut de l'analyse Salesforce.")

        try:
            parser = SalesforceMetadataParser(
                self.source_dir,
                exclusion_config_path=self.exclusion_config_path,
                log_callback=self.log,
            )
            snapshot = parser.parse()
        except (FileNotFoundError, OSError) as exc:
            self.log(f"Erreur critique lors de la lecture des metadata : {exc}")
            # On retourne un résultat vide mais on ne bloque pas totalement si possible
            return GenerationResult()
        except Exception as exc:
            self.log(f"Erreur inattendue lors de l'analyse : {exc}")
            return GenerationResult()

        self._apply_snapshot_config(snapshot)
        self._apply_test_coverage(snapshot)
        self._load_technical_debt(snapshot)
        self._load_innovations(snapshot)

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
