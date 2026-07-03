"""Mixin — documentation generation and test coverage for :class:`Application`."""

from __future__ import annotations

from tkinter import messagebox

from src.core.orchestrator import GenerationResult, SalesforceDocumentationGenerator


class AppGenerationMixin:
    """Documentation generation, menu shortcuts and test-coverage display."""

    # ------------------------------------------------------------------ generation result

    def _on_generation_result(self, result: GenerationResult) -> None:
        index_path = result.index
        if index_path is not None:
            self._append_log(self._t("index_log", path=index_path))
        snapshot = result.snapshot
        metrics = getattr(snapshot, "metrics", None)
        if metrics is not None:
            self.latest_metrics = metrics
        if snapshot is not None:
            self.latest_snapshot = snapshot
            self._update_discussion_context_status()
            self._append_discussion_line(self._t("discussion_context_loaded"))

    # ------------------------------------------------------------------ generation

    def _start_generation(
        self,
        *,
        generate_html_override: bool | None = None,
        generate_excels_override: bool | None = None,
        generate_data_dictionary_word_override: bool | None = None,
        generate_summary_word_override: bool | None = None,
    ) -> None:
        source_value = self.source_var.get().strip()
        if not source_value:
            messagebox.showerror(self._t("error_title"), self._t("source_folder_required"))
            return
        from pathlib import Path
        source = Path(source_value)
        output = self._validate_output_dir()
        if output is None:
            return
        if not source.exists():
            messagebox.showerror(self._t("error_title"), self._t("source_folder_missing"))
            return
        if source.is_file():
            messagebox.showerror(self._t("error_title"), self._t("source_must_be_dir"))
            return

        self._append_log(self._t("source_log", path=source))
        self._append_log(self._t("output_log", path=output))
        exclusion_file = self._selected_exclusion_file()
        if self.exclusion_file_var.get().strip() and exclusion_file is None:
            return
        pmd_ruleset = (
            self._selected_pmd_ruleset_file() if self.pmd_enabled_var.get() else None
        )
        if self.pmd_enabled_var.get() and self.pmd_ruleset_var.get().strip() and pmd_ruleset is None:
            return

        generate_excels = (
            bool(self.generate_excels_var.get())
            if generate_excels_override is None
            else generate_excels_override
        )
        generate_html = (
            bool(self.generate_html_var.get())
            if generate_html_override is None
            else generate_html_override
        )
        generate_dd_word = (
            bool(self.generate_data_dictionary_word_var.get())
            if generate_data_dictionary_word_override is None
            else generate_data_dictionary_word_override
        )
        generate_summary_word = (
            bool(self.generate_summary_word_var.get())
            if generate_summary_word_override is None
            else generate_summary_word_override
        )
        generate_audit_summary_rtf = bool(self.generate_audit_summary_rtf_var.get())
        generate_org_check = bool(self.generate_org_check_reports_var.get())
        org_check_choice = self.org_check_choice_var.get().strip()
        selected_org = self._selected_org()
        org_ref = selected_org.org_ref if selected_org else self.alias_var.get().strip()
        if selected_org is None and org_ref:
            self._append_log(self._t("generation_last_alias", alias=org_ref))

        def task() -> GenerationResult:
            test_coverage = None
            if selected_org:
                if self.run_tests_var.get():
                    self.task_manager.queue_log("")
                    self.task_manager.queue_log("=" * 80)
                    self.task_manager.queue_log("EXECUTION DES TESTS APEX (RunLocalTests)")
                    self.task_manager.queue_log(
                        "Vous pouvez suivre l'avancement dans votre org :"
                    )
                    self.task_manager.queue_log(
                        "  Configuration > Apex > Execution des tests Apex"
                    )
                    self.task_manager.queue_log("=" * 80)
                    self.task_manager.queue_log("")
                    self.cli_service.run_apex_tests(selected_org.org_ref)
                
                if self.calculate_coverage_var.get():
                    self.task_manager.queue_log("")
                    self.task_manager.queue_log(
                        "Recuperation de la couverture de tests..."
                    )
                    test_coverage = self._fetch_test_coverage(selected_org.org_ref)

            self._run_org_check_pre_step(
                output, generate_org_check, org_check_choice, org_ref
            )
            generator = SalesforceDocumentationGenerator(
                source,
                output,
                exclusion_config_path=exclusion_file,
                pmd_enabled=bool(self.pmd_enabled_var.get()),
                pmd_ruleset_path=pmd_ruleset,
                generate_excels=generate_excels,
                generate_html=generate_html,
                generate_data_dictionary_word=generate_dd_word,
                generate_summary_word=generate_summary_word,
                generate_audit_summary_rtf=generate_audit_summary_rtf,
                scoring_weights=dict(self.scoring_weights),
                adopt_adapt_weights=dict(self.adopt_adapt_weights),
                scoring_thresholds=tuple(self.scoring_thresholds),
                adopt_adapt_thresholds=tuple(self.adopt_adapt_thresholds),
                data_model_thresholds=tuple(self.data_model_thresholds),
                profiles_thresholds=tuple(self.profiles_thresholds),
                profiles_ps_ratio_thresholds=tuple(self.profiles_ps_ratio_thresholds),
                ai_usage_tags=list(self.ai_usage_tags),
                posture_config=list(self.posture_config),
                test_coverage_data=test_coverage,
                technical_debt_path=self.technical_debt_file_var.get().strip(),
                innovation_path=self.innovation_file_var.get().strip(),
                innovation_colors=dict(self.innovation_colors),
                analyzer_rules_path=self.analyzer_rules_file_var.get().strip(),
                index_card_visibility=self._current_index_card_visibility(),
                one_page_max_depth=int(self.one_page_max_depth_var.get()),
                one_page_hub_threshold=int(self.one_page_hub_threshold_var.get()),
                language=self.language,
                include_comparison=bool(self.include_comparison_var.get()),
                comparison_target=self.comparison_target_var.get().strip() or "auto",
                log_callback=self.task_manager.queue_log,
            )
            generator.alias = self.alias_var.get().strip() or org_ref
            return generator.generate()

        self.task_manager.start_task(
            status_text=self._t("doc_in_progress"),
            task=task,
            success_message=self._t("doc_done"),
            on_success=self._on_generation_result,
        )

    def _menu_generate_documentation(self) -> None:
        self._start_generation()

    def _menu_generate_excels(self) -> None:
        self._start_generation(
            generate_html_override=False,
            generate_excels_override=True,
            generate_data_dictionary_word_override=False,
            generate_summary_word_override=False,
        )

    def _menu_generate_html(self) -> None:
        self._start_generation(
            generate_html_override=True,
            generate_excels_override=False,
            generate_data_dictionary_word_override=False,
            generate_summary_word_override=False,
        )

    def _menu_generate_word(self) -> None:
        self._start_generation(
            generate_html_override=False,
            generate_excels_override=False,
            generate_data_dictionary_word_override=True,
            generate_summary_word_override=True,
        )

    # ------------------------------------------------------------------ coverage

    def _menu_calculate_coverage(self) -> None:
        self._clear_log()
        selected_org = self._selected_org()
        if selected_org is None:
            self.task_manager.queue_log(self._t("select_org_first"))
            return
        org_ref = selected_org.org_ref

        def task() -> None:
            sep = "=" * 120
            self.task_manager.queue_log("")
            self.task_manager.queue_log(sep)
            self.task_manager.queue_log("CALCUL DE LA COUVERTURE DE TESTS")
            self.task_manager.queue_log(sep)
            self.task_manager.queue_log("")
            
            if self.run_tests_var.get():
                self.task_manager.queue_log(sep)
                self.task_manager.queue_log("EXECUTION DES TESTS APEX (RunLocalTests)")
                self.task_manager.queue_log(
                    "Vous pouvez suivre l'avancement dans votre org :"
                )
                self.task_manager.queue_log(
                    "  Configuration > Apex > Execution des tests Apex"
                )
                self.task_manager.queue_log(sep)
                self.task_manager.queue_log("")
                self.cli_service.run_apex_tests(org_ref)
                self.task_manager.queue_log("")
            
            self.task_manager.queue_log(
                "Recuperation des resultats de couverture..."
            )
            self.task_manager.queue_log("")

            coverage_data = self._fetch_test_coverage(org_ref)
            thin = "-" * 120

            self.task_manager.queue_log("")
            self.task_manager.queue_log(thin)
            self.task_manager.queue_log("APEX CLASSES / TRIGGERS - TABLEAU RECAPITULATIF")
            self.task_manager.queue_log(thin)
            self.task_manager.queue_log("")
            header = (
                f"{'Nom de la classe/trigger':<60} "
                f"{'Lignes testées':<20} {'Total lignes':<20} {'Couverture':<20}"
            )
            self.task_manager.queue_log(header)
            self.task_manager.queue_log(thin)
            for name in sorted(coverage_data):
                info = coverage_data[name]
                if "lines_total" in info:
                    covered = info.get("lines_covered", 0)
                    total = info.get("lines_total", 0)
                    pct = info.get("percentage", 0)
                    cov_str = f"{pct:.1f}%" if total > 0 else "N/A"
                    line_str = "N/A" if total == 0 else f"{covered}/{total}"
                    self.task_manager.queue_log(
                        f"{name:<60} {line_str:<20} {total:<20} {cov_str:<20}"
                    )

            self.task_manager.queue_log("")
            self.task_manager.queue_log(thin)
            self.task_manager.queue_log("FLOWS - TABLEAU RECAPITULATIF")
            self.task_manager.queue_log(thin)
            self.task_manager.queue_log("")
            header = (
                f"{'Nom du flow':<60} "
                f"{'Blocs testes':<20} {'Total blocs':<20} {'Couverture':<20}"
            )
            self.task_manager.queue_log(header)
            self.task_manager.queue_log(thin)
            for name in sorted(coverage_data):
                info = coverage_data[name]
                if "elements_total" in info:
                    covered = info.get("elements_covered", 0)
                    total = info.get("elements_total", 0)
                    pct = info.get("percentage", 0)
                    cov_str = f"{pct:.1f}%" if total > 0 else "N/A"
                    block_str = "N/A" if total == 0 else f"{covered}/{total}"
                    self.task_manager.queue_log(
                        f"{name:<60} {block_str:<20} {total:<20} {cov_str:<20}"
                    )

            self.task_manager.queue_log("")
            self.task_manager.queue_log(sep)

        self.task_manager.start_task(
            status_text="Calcul de la couverture...",
            task=task,
            success_message="Couverture calculee",
        )

    def _fetch_test_coverage(self, target_org: str) -> dict[str, dict]:
        """Fetch test coverage for Apex classes and Flows via Tooling API."""
        coverage_data: dict[str, dict] = {}
        try:
            apex_query = (
                "SELECT ApexClassOrTrigger.Name, NumLinesCovered, NumLinesUncovered "
                "FROM ApexCodeCoverageAggregate"
            )
            self.task_manager.queue_log(f"[APEX] Requete SOQL: {apex_query}")
            apex_records = self.cli_service.run_query(
                apex_query, target_org, use_tooling_api=True
            )
            self.task_manager.queue_log(
                f"[APEX] Recupere {len(apex_records)} enregistrement(s) de couverture Apex."
            )
            if apex_records:
                self.task_manager.queue_log("[APEX] Resultats detailles:")
                for idx, record in enumerate(apex_records, 1):
                    name = record.get("ApexClassOrTrigger", {}).get("Name")
                    covered = record.get("NumLinesCovered", 0)
                    uncovered = record.get("NumLinesUncovered", 0)
                    total = covered + uncovered
                    pct = (covered / total) * 100 if total > 0 else 0.0
                    self.task_manager.queue_log(
                        f"  {idx}. {name}: {covered}/{total} lignes couvertes ({pct:.1f}%)"
                    )
                    if name:
                        coverage_data[name] = {
                            "percentage": pct,
                            "lines_covered": covered,
                            "lines_uncovered": uncovered,
                            "lines_total": total,
                        }
            else:
                self.task_manager.queue_log(
                    "[APEX] AUCUN enregistrement de couverture Apex trouve!"
                )

            flow_query = (
                "SELECT FlowVersion.Definition.DeveloperName, "
                "NumElementsCovered, NumElementsNotCovered FROM FlowTestCoverage"
            )
            self.task_manager.queue_log(f"[FLOW] Requete SOQL: {flow_query}")
            flow_records = self.cli_service.run_query(
                flow_query, target_org, use_tooling_api=True
            )
            self.task_manager.queue_log(
                f"[FLOW] Recupere {len(flow_records)} enregistrement(s) de couverture Flow."
            )
            if flow_records:
                self.task_manager.queue_log("[FLOW] Resultats detailles:")
                for idx, record in enumerate(flow_records, 1):
                    fv = record.get("FlowVersion") or {}
                    defn = fv.get("Definition") or {}
                    name = defn.get("DeveloperName") or fv.get("DeveloperName") or fv.get("FullName")
                    covered = record.get("NumElementsCovered", 0)
                    uncovered = record.get("NumElementsNotCovered", 0)
                    total = (covered or 0) + (uncovered or 0)
                    pct = (covered / total) * 100 if total > 0 else 0.0
                    self.task_manager.queue_log(
                        f"  {idx}. {name}: {covered}/{total} elements couverts ({pct:.1f}%)"
                    )
                    if name:
                        coverage_data[name] = {
                            "percentage": pct,
                            "elements_covered": covered,
                            "elements_uncovered": uncovered,
                            "elements_total": total,
                        }
            else:
                self.task_manager.queue_log(
                    "[FLOW] AUCUN enregistrement de couverture Flow trouve!"
                )
            self.task_manager.queue_log(
                f"[RESUME] Total elements analyses pour couverture: {len(coverage_data)}"
            )
        except Exception as exc:
            self.task_manager.queue_log(
                f"Avertissement : impossible de recuperer la couverture de tests : {exc}"
            )
        return coverage_data
