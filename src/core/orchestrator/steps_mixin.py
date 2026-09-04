"""Report-generation pipeline steps (Excel, PMD, Word, HTML)."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from src.analyzer.engine import AnalyzerReport
from src.analyzer.models import Finding
from src.core.audit_generator import generate_audit_summary_rtf
from src.core.data_dictionary_selection import data_dictionary_filename_base
from src.core.data_model_graph import DATA_MODEL_DIAGRAM_NAME
from src.core.findings_cache import load_findings_cache, merge_history
from src.core.findings_qualification import (
    FindingQualification,
    QualificationKey,
    load_qualifications,
    store_alias,
)
from src.core.models import MetadataSnapshot, PmdViolation
from src.core.orchestrator.base import _OrchestratorState
from src.core.orchestrator.result import GenerationResult
from src.core.pmd_service import PmdService
from src.core.psg_access import SUMMARY_WORKBOOK_NAME
from src.core.utils import safe_slug
from src.reporting.drawio_writer import DrawioDiagramWriter
from src.reporting.excel_writer import ExcelReportWriter
from src.reporting.excel_writer_findings import (
    FindingsExcelWriter,
    findings_workbook_path,
)
from src.reporting.html_writer import HtmlReportWriter
from src.reporting.sarif_writer import write_sarif_report
from src.reporting.word_writer import WordReportWriter


class _StepsMixin(_OrchestratorState):
    """Individual report writers, isolated so one failure does not abort the run."""

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
        result.picklists_excel = self._safe_run(
            "picklists.xlsx",
            lambda: excel_writer.write_picklists_workbook(
                snapshot.objects, excel_dir / "picklists.xlsx"
            ),
        )
        result.psg_summary_excel = self._safe_run(
            SUMMARY_WORKBOOK_NAME,
            lambda: excel_writer.write_psg_summary_workbook(
                snapshot,
                excel_dir / SUMMARY_WORKBOOK_NAME,
                selected_objects=(
                    self.data_dictionary_selection.objects
                    if self.data_dictionary_selection is not None
                    else None
                ),
            ),
        )

    def _generate_selected_data_dictionary_excel(
        self,
        snapshot: MetadataSnapshot,
        excel_writer: ExcelReportWriter,
        excel_dir: Path,
        result: GenerationResult,
    ) -> None:
        """Write the Data Dictionary restricted to the objects picked in the
        Data Dictionary screen, with the Dewey extra info entered there."""
        selection = self.data_dictionary_selection
        if selection is None or not selection.objects:
            self.log(
                "Data Dictionary des objets selectionnes : aucun objet "
                "selectionne dans l'ecran Data Dictionnary, generation ignoree."
            )
            return
        objects = selection.apply(snapshot.objects)
        if not objects:
            self.log(
                "Data Dictionary des objets selectionnes : les objets "
                "selectionnes sont absents de la source analysee."
            )
            return
        filename_base = data_dictionary_filename_base()
        self.log(
            f"Generation du Data Dictionary pour {len(objects)} objet(s) selectionne(s)."
        )
        result.selected_data_dictionary_excels = (
            self._safe_run(
                f"{filename_base}.xlsx",
                lambda: excel_writer.write_data_dictionary_workbooks(
                    objects,
                    excel_dir,
                    filename_base=filename_base,
                    **selection.workbook_options(),
                ),
            )
            or []
        )

    def _generate_data_model_diagram(
        self,
        snapshot: MetadataSnapshot,
        result: GenerationResult,
    ) -> None:
        """Write the draw.io data model diagram of the selected objects.

        The perimeter is the Data Dictionary selection, as the diagram is meant
        to document the objects the user chose to document, and the relations
        come from the retrieve like the rest of the documentation.
        """
        selection = self.data_dictionary_selection
        if selection is None or not selection.objects:
            self.log(
                "Diagramme du modele de donnees : aucun objet selectionne dans "
                "l'ecran Data Dictionnary, generation ignoree."
            )
            return
        objects = selection.apply(snapshot.objects)
        if not objects:
            self.log(
                "Diagramme du modele de donnees : les objets selectionnes sont "
                "absents de la source analysee."
            )
            return
        result.data_model_drawio = self._safe_run(
            DATA_MODEL_DIAGRAM_NAME,
            lambda: DrawioDiagramWriter(
                log_callback=self.log
            ).write_data_model_diagram(
                objects,
                self.output_dir / "diagrams" / DATA_MODEL_DIAGRAM_NAME,
            ),
        )

    def _generate_findings_excel(
        self,
        analyzer_report: AnalyzerReport,
        result: GenerationResult,
    ) -> None:
        target = findings_workbook_path(self.output_dir / "excel", self.alias)
        findings, resolved = self._findings_with_history(analyzer_report)
        qualifications = self._stored_findings_qualifications()
        result.findings_excel = self._safe_run(
            target.name,
            lambda: FindingsExcelWriter(log_callback=self.log).write_findings_workbook(
                findings,
                target,
                alias=self.alias,
                qualifications=qualifications,
                resolved_keys=resolved,
            ),
        )

    def _findings_with_history(
        self, analyzer_report: AnalyzerReport
    ) -> tuple[list[Finding], set[QualificationKey]]:
        """Findings of this run plus the ones earlier runs had reported.

        A finding that disappears is not dropped from the document: it stays
        with the qualification attached to it, marked as resolved, so the
        TechLead reads that it was closed instead of wondering where it went.
        """
        current = analyzer_report.all_findings()
        path = self.findings_history_path
        previous = load_findings_cache(path) if path is not None else None
        findings, resolved = merge_history(
            current, previous.findings if previous is not None else []
        )
        if resolved:
            self.log(
                f"Document des findings : {len(resolved)} finding(s) des runs "
                "precedents ne sont plus detecte(s), export en statut resolu."
            )
        return findings, resolved

    def _stored_findings_qualifications(
        self,
    ) -> dict[QualificationKey, FindingQualification]:
        """TechLead columns already imported for this org.

        A full run overwrites the findings workbook, so without this the
        qualification and US columns would silently go back to empty every
        time the documentation is regenerated.
        """
        path = self.findings_qualifications_path
        if path is None:
            return {}
        stored = load_qualifications(path).get(store_alias(self.alias), {})
        if stored:
            self.log(
                f"Document des findings : {len(stored)} qualification(s) "
                "reprise(s) du dernier import."
            )
        return stored

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

    def _generate_sarif(
        self,
        analyzer_report: AnalyzerReport,
        result: GenerationResult,
    ) -> None:
        self.log("Generation de l'export SARIF (integration CI/CD).")
        result.sarif_path = self._safe_run(
            "dewey.sarif",
            lambda: write_sarif_report(
                analyzer_report,
                self.output_dir / "dewey.sarif",
                source_root=self.source_dir,
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
        from src.reporting.html.one_page import (
            configure_one_page,
            set_one_page_inactive_flow_names,
            set_one_page_node_descriptions,
            set_one_page_test_names,
        )
        configure_one_page(self.one_page_max_depth, self.one_page_hub_threshold)
        set_one_page_test_names(
            {art.name for art in snapshot.apex_artifacts if art.is_test}
        )
        set_one_page_inactive_flow_names(
            {
                flow.name
                for flow in snapshot.flows
                if (flow.status or "").strip()
                and (flow.status or "").strip().lower() != "active"
            }
        )
        node_descriptions: dict[str, str] = {}
        for obj in snapshot.objects:
            if obj.description:
                node_descriptions[obj.api_name] = obj.description
            for field in obj.fields:
                if field.description:
                    node_descriptions[f"{obj.api_name}.{field.api_name}"] = field.description
        for flow in snapshot.flows:
            if flow.description:
                node_descriptions[flow.name] = flow.description
        for component in (
            list(snapshot.lwc)
            + list(snapshot.aura)
            + list(snapshot.inventory.get("reports", []))
        ):
            if isinstance(component, dict):
                name = str(component.get("Nom") or component.get("Name") or "")
                description = str(component.get("Description") or "")
            else:
                name = getattr(component, "name", "")
                description = getattr(component, "description", "")
            if name and description:
                node_descriptions[name] = description
        set_one_page_node_descriptions(node_descriptions)
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
            snapshot,
            result.data_model_stats,
            usage_stats=result.selected_usage_stats,
        )
        result.adoption_page = html_writer.write_adoption_page(
            snapshot, result.adoption_stats
        )
        result.debt_page = html_writer.write_debt_page(snapshot)
        result.innovation_page = html_writer.write_innovation_page(snapshot)
        result.picklists_page = html_writer.write_picklists_page(snapshot)
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
        comparison_page, comparison_regressions = self._generate_comparison_page(
            snapshot, result, analyzer_report
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
            picklists_page=result.picklists_page,
            findings_report_page=result.findings_report_page,
            card_visibility=self.index_card_visibility,
            alias=self.alias,
            comparison_page=comparison_page,
            comparison_regressions=comparison_regressions,
            data_dictionary_objects=(
                self.data_dictionary_selection.objects
                if self.data_dictionary_selection is not None
                else None
            ),
        )
