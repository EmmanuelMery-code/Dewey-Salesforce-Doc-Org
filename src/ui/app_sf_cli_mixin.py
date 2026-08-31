"""Mixin — Salesforce CLI operations for :class:`Application`.

Covers: org listing, web login, manifest generation, metadata retrieval,
full pipeline, org-check Excel export, and related UI helpers.
"""

from __future__ import annotations

from pathlib import Path
from threading import Thread
from tkinter import messagebox
from typing import Callable

from src.core.data_dictionary_selection import DataDictionarySelection
from src.core.orchestrator import GenerationResult, SalesforceDocumentationGenerator
from src.core.sf_cli_service import OrgSummary


class AppSfCliMixin:
    """Salesforce CLI actions (orgs, retrieve, pipeline, org-check)."""

    # ------------------------------------------------------------------ orgs

    def _login_web(self) -> None:
        alias = self.alias_var.get().strip()
        if not alias:
            messagebox.showerror(self._t("error_title"), self._t("alias_required"))
            return
        instance_url = self.instance_url_var.get().strip()
        self.task_manager.start_task(
            status_text=self._t("web_login_in_progress"),
            task=lambda: self.cli_service.login_web(alias, instance_url),
            success_message=self._t("web_login_done", alias=alias),
            on_success=self._on_orgs_loaded,
        )

    def _refresh_orgs(self, initial: bool = False) -> None:
        self.task_manager.start_task(
            status_text=self._t("loading_orgs"),
            task=self.cli_service.list_orgs,
            success_message=self._t("org_list_refreshed"),
            on_success=self._on_orgs_loaded,
            notify=not initial,
        )

    def _load_orgs_in_background(self) -> None:
        """Load the org list without blocking the UI buttons.

        Used at startup so the user can immediately generate documentation
        for the last used alias even when listing the Salesforce orgs is very
        slow. Runs in its own daemon thread (outside the single-task worker)
        and only refreshes the combo box once finished.
        """
        if getattr(self, "_orgs_bg_loading", False):
            return
        self._orgs_bg_loading = True
        self._append_log(self._t("loading_orgs_background"))

        def worker() -> None:
            try:
                orgs = self.cli_service.list_orgs()
                self.task_manager.queue.put(("orgs_loaded_bg", orgs))
            except Exception as exc:  # noqa: BLE001 - reported to the UI log
                self.task_manager.queue.put(("orgs_load_error_bg", str(exc)))

        Thread(target=worker, daemon=True).start()

    def _on_orgs_loaded(self, orgs: list[OrgSummary]) -> None:
        current = self.selected_org_var.get()
        self.orgs = orgs
        self.orgs_by_label = {org.display_label: org for org in orgs}
        labels = [org.display_label for org in orgs]
        self.org_combo["values"] = labels
        if current in self.orgs_by_label:
            self.selected_org_var.set(current)
            self._on_org_selected()
        else:
            self.selected_org_var.set("")
            self._on_org_selected()
        self._append_log(self._t("orgs_loaded", count=len(orgs)))

    def _selected_org(self) -> OrgSummary | None:
        label = self.selected_org_var.get().strip()
        return self.orgs_by_label.get(label)

    def _on_org_selected(self, _event=None) -> None:
        org = self._selected_org()
        if org:
            self.alias_var.set(org.alias or "")
            self.login_target_key = "sandbox" if org.is_sandbox else "production"
            self.login_target_var.set(self._login_target_display(self.login_target_key))
            self.instance_url_var.set(
                org.instance_url or self.LOGIN_TARGETS[self.login_target_key]
            )
            state = "normal" if self.login_target_key == "custom" else "readonly"
            self.instance_url_entry.configure(state=state)
            self._save_settings()
            self._append_log(self._t("org_selected_log", alias=org.alias))
        else:
            self.alias_var.set("")
            self.login_target_var.set("")
            self.instance_url_var.set("")
            self._save_settings()

    # ------------------------------------------------------------------ validation

    def _validate_source_for_cli(
        self, report_error: Callable[[str], None] | None = None
    ) -> Path | None:
        if report_error is None:
            report_error = lambda msg: messagebox.showerror(self._t("error_title"), msg)
        source_value = self.source_var.get().strip()
        if not source_value:
            report_error(self._t("source_folder_required"))
            return None
        source = Path(source_value)
        if source.exists() and source.is_file():
            report_error(self._t("source_must_be_dir"))
            return None
        return source

    def _validate_output_dir(
        self, report_error: Callable[[str], None] | None = None
    ) -> Path | None:
        if report_error is None:
            report_error = lambda msg: messagebox.showerror(self._t("error_title"), msg)
        output_value = self.output_var.get().strip()
        if not output_value:
            report_error(self._t("output_folder_required"))
            return None
        output = Path(output_value)
        if output.exists() and output.is_file():
            report_error(self._t("output_must_be_dir"))
            return None
        return output

    # ------------------------------------------------------------------ CLI actions

    def _generate_manifest(self) -> None:
        if not self._apply_source_dir_policy():
            return
        source = self._validate_source_for_cli()
        if source is None:
            return
        selected_org = self._selected_org()
        if selected_org is None:
            messagebox.showerror(self._t("error_title"), self._t("select_org_manifest"))
            return
        self.task_manager.start_task(
            status_text=self._t("manifest_in_progress"),
            task=lambda: self.cli_service.generate_manifest(selected_org.org_ref, source),
            success_message=self._t("manifest_done"),
            on_success=lambda p: self._append_log(self._t("manifest_ready", path=p)),
        )

    def _delete(self) -> None:
        selected_org = self._selected_org()
        if selected_org is None:
            messagebox.showerror(self._t("error_title"), self._t("select_delete"))
            return
        if messagebox.askyesno(self._t("confirmation_delete"), self._t("message_delete")):
            self.task_manager.start_task(
                status_text=self._t("delete_in_progress"),
                task=lambda: self.cli_service.delete_org(selected_org.org_ref),
                success_message=self._t("delete_done"),
                on_success=lambda _: self._refresh_orgs(initial=True),
            )

    def _retrieve_from_selected_org(self) -> None:
        if not self._apply_source_dir_policy():
            return
        source = self._validate_source_for_cli()
        if source is None:
            return
        selected_org = self._selected_org()
        if selected_org is None:
            messagebox.showerror(self._t("error_title"), self._t("select_org_retrieve"))
            return
        manifest_path = source / "manifest" / "package.xml"
        if manifest_path.exists():
            task = lambda: self.cli_service.retrieve_from_org(
                selected_org.org_ref, source, manifest_path
            )
            success_message = self._t("retrieve_done")
        else:
            if not messagebox.askyesno(
                self._t("manifest_missing_title"), self._t("manifest_missing_message")
            ):
                return

            def task() -> Path:
                generated = self.cli_service.generate_manifest(selected_org.org_ref, source)
                return self.cli_service.retrieve_from_org(selected_org.org_ref, source, generated)

            success_message = self._t("manifest_retrieve_done")

        self.task_manager.start_task(
            status_text=self._t("retrieve_in_progress"),
            task=task,
            success_message=success_message,
            on_success=lambda p: self.source_var.set(str(p)),
        )

    def _run_retrieve_and_doc(self) -> None:
        """Retrieve then generate the documentation, reusing an existing manifest.

        The manifest is never regenerated here, so the source folder policy is
        deliberately not applied: emptying or relocating the source folder would
        discard the very manifest this action is meant to reuse.
        """
        source = self._validate_source_for_cli()
        if source is None:
            return
        manifest_path = source / "manifest" / "package.xml"
        if not manifest_path.exists():
            messagebox.showerror(
                self._t("manifest_required_title"),
                self._t("manifest_required_message", path=manifest_path),
            )
            return
        selected_org = self._selected_org()
        if selected_org is None:
            messagebox.showerror(self._t("error_title"), self._t("select_org_retrieve_doc"))
            return
        if not self._apply_output_dir_policy():
            return
        output = self._validate_output_dir()
        if output is None:
            return
        exclusion_file = self._selected_exclusion_file()
        if self.exclusion_file_var.get().strip() and exclusion_file is None:
            return
        pmd_ruleset = (
            self._selected_pmd_ruleset_file() if self.pmd_enabled_var.get() else None
        )
        if self.pmd_enabled_var.get() and self.pmd_ruleset_var.get().strip() and pmd_ruleset is None:
            return

        org_ref = selected_org.org_ref
        self._append_log(self._t("retrieve_doc_log", org=org_ref))
        self._append_log(self._t("manifest_reused_log", path=manifest_path))
        self._append_log(self._t("source_log", path=source))
        self._append_log(self._t("output_log", path=output))

        documentation_task = self._build_documentation_task(
            source, output, org_ref, True, exclusion_file, pmd_ruleset
        )

        def task() -> GenerationResult:
            self.cli_service.retrieve_from_org(org_ref, source, manifest_path)
            return documentation_task()

        self.task_manager.start_task(
            status_text=self._t("retrieve_doc_in_progress"),
            task=task,
            success_message=self._t("retrieve_doc_done"),
            on_success=self._on_generation_result,
        )

    def _run_full_pipeline(self) -> None:
        if not self._apply_source_dir_policy():
            return
        if not self._apply_output_dir_policy():
            return
        source = self._validate_source_for_cli()
        if source is None:
            return
        output = self._validate_output_dir()
        if output is None:
            return
        selected_org = self._selected_org()
        if selected_org is None:
            messagebox.showerror(self._t("error_title"), self._t("select_org_pipeline"))
            return

        self._append_log(self._t("pipeline_log", org=selected_org.org_ref))
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

        generate_excels = bool(self.generate_excels_var.get())
        generate_dd_excel = bool(self.generate_data_dictionary_excel_var.get())
        dd_selection = (
            DataDictionarySelection.from_settings(self.settings)
            if generate_dd_excel
            else None
        )
        generate_org_check = bool(self.generate_org_check_reports_var.get())
        org_check_choice = self.org_check_choice_var.get().strip()
        org_ref = selected_org.org_ref
        run_alias = self._run_alias(org_ref)
        findings_paths = self._findings_paths(run_alias)

        def task() -> GenerationResult:
            self.cli_service.reset_command_stats()
            manifest_path = self.cli_service.generate_manifest(selected_org.org_ref, source)
            retrieved_path = self.cli_service.retrieve_from_org(
                selected_org.org_ref, source, manifest_path
            )
            self.task_manager.queue_log("Recuperation de la couverture de tests...")
            test_coverage = self._fetch_test_coverage(selected_org.org_ref)
            self._run_org_check_pre_step(output, generate_org_check, org_check_choice, org_ref)
            generator = SalesforceDocumentationGenerator(
                retrieved_path,
                output,
                exclusion_config_path=exclusion_file,
                pmd_enabled=bool(self.pmd_enabled_var.get()),
                pmd_ruleset_path=pmd_ruleset,
                generate_excels=generate_excels,
                generate_data_dictionary_word=bool(self.generate_data_dictionary_word_var.get()),
                generate_summary_word=bool(self.generate_summary_word_var.get()),
                generate_sarif=bool(self.generate_sarif_var.get()),
                generate_data_dictionary_excel=generate_dd_excel,
                generate_findings_excel=bool(self.generate_findings_excel_var.get()),
                **findings_paths,
                data_dictionary_selection=dd_selection,
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
                analyzer_rules_path=self.analyzer_rules_file_var.get().strip(),
                index_card_visibility=self._current_index_card_visibility(),
                language=self.language,
                include_comparison=bool(self.include_comparison_var.get()),
                comparison_target=self.comparison_target_var.get().strip() or "auto",
                log_callback=self.task_manager.queue_log,
            )
            generator.alias = run_alias
            result = generator.generate()
            self.cli_service.log_command_summary()
            return result

        self.task_manager.start_task(
            status_text=self._t("pipeline_in_progress"),
            task=task,
            success_message=self._t("pipeline_done"),
            on_success=self._on_generation_result,
        )

    def _run_org_check_excel(self) -> None:
        selected_org = self._selected_org()
        if selected_org is None:
            messagebox.showerror(self._t("error_title"), self._t("select_org_org_check"))
            return
        check_choice = self.org_check_choice_var.get().strip()
        if not check_choice:
            messagebox.showerror(self._t("error_title"), self._t("org_check_choice_required"))
            return
        if not self._apply_output_dir_policy():
            return
        output = self._validate_output_dir()
        if output is None:
            return
        excel_path = output / "excel" / f"{check_choice}.xlsx"
        self._append_log(self._t("output_log", path=output / "excel"))
        self.task_manager.start_task(
            status_text=self._t("org_check_in_progress"),
            task=lambda: self.cli_service.generate_org_check_excel(
                check_choice, selected_org.org_ref, excel_path
            ),
            success_message=self._t("org_check_done"),
            on_success=lambda p: self._append_log(self._t("org_check_ready", path=p)),
        )

    def _run_org_check_pre_step(
        self, output: Path, enabled: bool, check_choice: str, org_ref: str
    ) -> None:
        if not enabled:
            return
        if not check_choice:
            self.task_manager.queue_log(self._t("org_check_choice_required"))
            return
        if not org_ref:
            self.task_manager.queue_log(self._t("select_org_org_check"))
            return
        excel_path = output / "excel" / f"{check_choice}.xlsx"
        try:
            self.task_manager.queue_log(self._t("org_check_in_progress"))
            generated_path = self.cli_service.generate_org_check_excel(
                check_choice, org_ref, excel_path
            )
            self.task_manager.queue_log(self._t("org_check_ready", path=generated_path))
        except Exception as exc:
            self.task_manager.queue_log(f"Echec Org Check: {exc}")
