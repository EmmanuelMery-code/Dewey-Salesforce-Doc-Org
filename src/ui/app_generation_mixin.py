"""Mixin — documentation generation and test coverage for :class:`Application`."""

from __future__ import annotations

from pathlib import Path
from tkinter import messagebox

from src.core.findings_cache import findings_cache_path, save_findings_cache
from src.core.findings_qualification import STORE_FILENAME as QUALIFICATION_STORE
from src.core.orchestrator import GenerationResult


class AppGenerationMixin:
    """Documentation generation, menu shortcuts and test-coverage display."""

    # ------------------------------------------------------------------ findings paths

    def _findings_paths(self, alias: str) -> dict[str, Path]:
        """Stores the generator reads to keep the findings document faithful.

        Every entry point that builds a generator must pass them — the
        documentation menu, the retrieve-then-document pipeline and the
        ``--action`` steps. Going through one helper is deliberate: a missing
        path is invisible, the workbook is still produced, only stripped of
        the qualifications or of the findings of the past runs.

        ``alias`` must be the very alias the run will carry, since the
        history is stored per org.
        """
        return {
            "findings_qualifications_path": self.app_dir / QUALIFICATION_STORE,
            "findings_history_path": findings_cache_path(self.app_dir, alias),
        }

    def _run_alias(self, org_ref: str = "") -> str:
        """Alias a run is filed under: the alias field, else the org ref."""
        return self.alias_var.get().strip() or org_ref

    # ------------------------------------------------------------------ generation result

    def _on_generation_result(self, result: GenerationResult) -> None:
        index_path = result.index
        if index_path is not None:
            self._append_log(self._t("index_log", path=index_path))
        if result.analyzer_report is not None:
            self.latest_analyzer_report = result.analyzer_report
            # The alias of the run itself, so the cache written here is the
            # one the run read its history from.
            alias = result.alias or self.alias_var.get().strip()
            try:
                save_findings_cache(
                    result.analyzer_report,
                    findings_cache_path(self.app_dir, alias),
                    alias=alias,
                )
            except OSError as exc:
                self._append_log(self._t("findings_cache_failed", error=exc))
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
        if not self._apply_source_dir_policy():
            return
        if not self._apply_output_dir_policy():
            return
        source_value = self.source_var.get().strip()
        if not source_value:
            messagebox.showerror(self._t("error_title"), self._t("source_folder_required"))
            return
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

        selected_org = self._selected_org()
        org_ref = selected_org.org_ref if selected_org else self.alias_var.get().strip()
        if selected_org is None and org_ref:
            self._append_log(self._t("generation_last_alias", alias=org_ref))

        task = self._build_documentation_task(
            source,
            output,
            org_ref,
            selected_org is not None,
            exclusion_file,
            pmd_ruleset,
            generate_html_override=generate_html_override,
            generate_excels_override=generate_excels_override,
            generate_data_dictionary_word_override=generate_data_dictionary_word_override,
            generate_summary_word_override=generate_summary_word_override,
        )

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
            self.cli_service.reset_command_stats()
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

            self.cli_service.log_command_summary()

        self.task_manager.start_task(
            status_text="Calcul de la couverture...",
            task=task,
            success_message="Couverture calculee",
        )

    def _fetch_test_coverage(self, target_org: str) -> dict[str, dict]:
        """Fetch test coverage for Apex classes and Flows via Tooling API.

        Thin wrapper around :meth:`SalesforceCliService.fetch_test_coverage`
        (shared with the ``Dewey`` module) — ``cli_service`` already logs to
        the task manager's log window via its ``log_callback``.
        """
        return self.cli_service.fetch_test_coverage(target_org)
