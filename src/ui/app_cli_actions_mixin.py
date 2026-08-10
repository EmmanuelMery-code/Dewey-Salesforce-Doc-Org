"""Mixin — ``--action`` steps (manifest/retrieve/documentation/all) for :class:`Application`.

Two execution modes are provided:

* :meth:`run_cli_action` — fully synchronous, used for ``--silent`` headless
  runs. No Tk main loop is required: every step runs on the calling thread
  and errors/progress are reported via ``print`` (plus the log widget, best
  effort) instead of message boxes.
* :meth:`_run_cli_action_visible` — used when ``--action`` is supplied
  without ``--silent``. The window opens normally and the requested step(s)
  start automatically, chained through the existing threaded
  :class:`~src.ui.task_manager.TaskManager` so the UI stays responsive and
  the log streams live, exactly like a manual button click.

Both modes resolve the target org from the ``alias`` field of the loaded
configuration file directly (no Salesforce org list lookup), and both share
:meth:`_build_documentation_task`, which mirrors the generation task built by
``AppGenerationMixin._start_generation`` but takes an explicit ``org_ref``
instead of a combo-box selected :class:`OrgSummary`.
"""

from __future__ import annotations

from pathlib import Path
from tkinter import messagebox
from typing import Callable

from src.core.orchestrator import GenerationResult, SalesforceDocumentationGenerator

CLI_ACTIONS: tuple[str, ...] = ("manifest", "retrieve", "documentation", "all", "retrivation")

# Steps chained for each multi-step --action value. Single-step actions
# (manifest / retrieve / documentation) are not listed here; see
# `_action_steps()`. "retrivation" relies on `_cli_run_retrieve` /
# `_run_cli_retrieve_visible` auto-generating the manifest when it is
# missing from the source directory, so it does not need its own
# "manifest" step.
_MULTI_STEP_ACTIONS: dict[str, list[str]] = {
    "all": ["manifest", "retrieve", "documentation"],
    "retrivation": ["retrieve", "documentation"],
}


def _action_steps(action: str) -> list[str]:
    return list(_MULTI_STEP_ACTIONS.get(action, [action]))


class AppCliActionsMixin:
    """Executes ``--action`` steps, either headlessly or through the GUI."""

    # ------------------------------------------------------------------ shared task builder

    def _build_documentation_task(
        self,
        source: Path,
        output: Path,
        org_ref: str,
        has_org: bool,
        exclusion_file: Path | None,
        pmd_ruleset: Path | None,
    ) -> Callable[[], GenerationResult]:
        generate_excels = bool(self.generate_excels_var.get())
        generate_html = bool(self.generate_html_var.get())
        generate_dd_word = bool(self.generate_data_dictionary_word_var.get())
        generate_summary_word = bool(self.generate_summary_word_var.get())
        generate_audit_summary_rtf = bool(self.generate_audit_summary_rtf_var.get())
        generate_org_check = bool(self.generate_org_check_reports_var.get())
        org_check_choice = self.org_check_choice_var.get().strip()

        def task() -> GenerationResult:
            self.cli_service.reset_command_stats()
            test_coverage = None
            if has_org:
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
                    self.cli_service.run_apex_tests(org_ref)

                if self.calculate_coverage_var.get():
                    self.task_manager.queue_log("")
                    self.task_manager.queue_log("Recuperation de la couverture de tests...")
                    test_coverage = self._fetch_test_coverage(org_ref)

            self._run_org_check_pre_step(output, generate_org_check, org_check_choice, org_ref)
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
            result = generator.generate()
            self.cli_service.log_command_summary()
            return result

        return task

    # ------------------------------------------------------------------ headless (--silent) step helpers

    def _cli_run_manifest(
        self, alias: str, report_error: Callable[[str], None]
    ) -> Path | None:
        if not self._apply_source_dir_policy(report_error=report_error):
            return None
        source = self._validate_source_for_cli(report_error=report_error)
        if source is None:
            return None
        try:
            return self.cli_service.generate_manifest(alias, source)
        except Exception as exc:  # noqa: BLE001 - reported to the caller
            report_error(str(exc))
            return None

    def _cli_run_retrieve(
        self, alias: str, report_error: Callable[[str], None]
    ) -> Path | None:
        if not self._apply_source_dir_policy(report_error=report_error):
            return None
        source = self._validate_source_for_cli(report_error=report_error)
        if source is None:
            return None
        manifest_path = source / "manifest" / "package.xml"
        try:
            if not manifest_path.exists():
                report_error("Manifest absent, generation automatique avant le retrieve...")
                manifest_path = self.cli_service.generate_manifest(alias, source)
            retrieved = self.cli_service.retrieve_from_org(alias, source, manifest_path)
        except Exception as exc:  # noqa: BLE001
            report_error(str(exc))
            return None
        self.source_var.set(str(retrieved))
        return retrieved

    def _cli_run_documentation(
        self, alias: str, report_error: Callable[[str], None]
    ) -> GenerationResult | None:
        if not self._apply_source_dir_policy(report_error=report_error):
            return None
        if not self._apply_output_dir_policy(report_error=report_error):
            return None
        source_value = self.source_var.get().strip()
        if not source_value:
            report_error(self._t("source_folder_required"))
            return None
        source = Path(source_value)
        output = self._validate_output_dir(report_error=report_error)
        if output is None:
            return None
        if not source.exists():
            report_error(self._t("source_folder_missing"))
            return None
        if source.is_file():
            report_error(self._t("source_must_be_dir"))
            return None
        exclusion_file = self._selected_exclusion_file(report_error=report_error)
        if self.exclusion_file_var.get().strip() and exclusion_file is None:
            return None
        pmd_ruleset = (
            self._selected_pmd_ruleset_file(report_error=report_error)
            if self.pmd_enabled_var.get()
            else None
        )
        if (
            self.pmd_enabled_var.get()
            and self.pmd_ruleset_var.get().strip()
            and pmd_ruleset is None
        ):
            return None

        task = self._build_documentation_task(source, output, alias, True, exclusion_file, pmd_ruleset)
        try:
            result = task()
        except Exception as exc:  # noqa: BLE001
            report_error(str(exc))
            return None
        self._on_generation_result(result)
        return result

    # ------------------------------------------------------------------ headless (--silent) entry point

    def _cli_headless_log(self, message: str) -> None:
        print(message)
        try:
            self._append_log(message)
        except Exception:
            pass

    def run_cli_action(self, action: str) -> int:
        """Run ``action`` synchronously without the Tk main loop.

        Used for ``--silent`` invocations. Returns a process exit code:
        ``0`` on success, ``1`` if any requested step failed.
        """
        self.cli_service.log = self._cli_headless_log
        self.task_manager.queue_log = self._cli_headless_log

        alias = self.alias_var.get().strip()
        if not alias:
            self._cli_headless_log(
                "Erreur : aucun alias d'org n'est defini dans le fichier de configuration utilise."
            )
            return 1

        steps = _action_steps(action)
        self._cli_headless_log(f"[CLI] Org : {alias} | Action demandee : {action}")
        for step in steps:
            self._cli_headless_log(f"[CLI] Etape : {step}...")
            if step == "manifest":
                ok = self._cli_run_manifest(alias, self._cli_headless_log) is not None
            elif step == "retrieve":
                ok = self._cli_run_retrieve(alias, self._cli_headless_log) is not None
            else:
                ok = self._cli_run_documentation(alias, self._cli_headless_log) is not None
            if not ok:
                self._cli_headless_log(f"[CLI] Echec a l'etape '{step}'.")
                return 1
            self._cli_headless_log(f"[CLI] Etape '{step}' terminee avec succes.")
        self._cli_headless_log(
            "[CLI] Toutes les etapes demandees se sont terminees avec succes."
        )
        return 0

    # ------------------------------------------------------------------ visible (GUI) auto-run

    def _run_cli_action_visible(self, action: str) -> None:
        """Auto-start ``action`` right after the window opens (no ``--silent``).

        Chains the requested step(s) through the normal threaded task
        manager so the UI stays responsive, matching a manual button click.
        """
        alias = self.alias_var.get().strip()
        if not alias:
            messagebox.showerror(self._t("error_title"), self._t("alias_required"))
            return
        steps = _action_steps(action)
        self._append_log(f"[CLI] Org : {alias} | Action demandee : {action}")
        self._run_cli_visible_step(steps, alias, 0)

    def _run_cli_visible_step(self, steps: list[str], alias: str, index: int) -> None:
        if index >= len(steps):
            self._append_log("[CLI] Toutes les etapes demandees se sont terminees avec succes.")
            return
        step = steps[index]

        def advance(_result: object = None) -> None:
            self._run_cli_visible_step(steps, alias, index + 1)

        if step == "manifest":
            self._run_cli_manifest_visible(alias, advance)
        elif step == "retrieve":
            self._run_cli_retrieve_visible(alias, advance)
        else:
            self._run_cli_documentation_visible(alias, advance)

    def _run_cli_manifest_visible(self, alias: str, advance: Callable[[], None]) -> None:
        if not self._apply_source_dir_policy():
            return
        source = self._validate_source_for_cli()
        if source is None:
            return

        def on_success(path: Path) -> None:
            self._append_log(self._t("manifest_ready", path=path))
            advance()

        self.task_manager.start_task(
            status_text=self._t("manifest_in_progress"),
            task=lambda: self.cli_service.generate_manifest(alias, source),
            success_message=self._t("manifest_done"),
            on_success=on_success,
        )

    def _run_cli_retrieve_visible(self, alias: str, advance: Callable[[], None]) -> None:
        if not self._apply_source_dir_policy():
            return
        source = self._validate_source_for_cli()
        if source is None:
            return
        manifest_path = source / "manifest" / "package.xml"
        if manifest_path.exists():
            task = lambda: self.cli_service.retrieve_from_org(alias, source, manifest_path)
            success_message = self._t("retrieve_done")
        else:
            def task() -> Path:
                generated = self.cli_service.generate_manifest(alias, source)
                return self.cli_service.retrieve_from_org(alias, source, generated)

            success_message = self._t("manifest_retrieve_done")

        def on_success(path: Path) -> None:
            self.source_var.set(str(path))
            advance()

        self.task_manager.start_task(
            status_text=self._t("retrieve_in_progress"),
            task=task,
            success_message=success_message,
            on_success=on_success,
        )

    def _run_cli_documentation_visible(self, alias: str, advance: Callable[[], None]) -> None:
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
        pmd_ruleset = self._selected_pmd_ruleset_file() if self.pmd_enabled_var.get() else None
        if (
            self.pmd_enabled_var.get()
            and self.pmd_ruleset_var.get().strip()
            and pmd_ruleset is None
        ):
            return

        task = self._build_documentation_task(source, output, alias, True, exclusion_file, pmd_ruleset)

        def on_success(result: GenerationResult) -> None:
            self._on_generation_result(result)
            advance()

        self.task_manager.start_task(
            status_text=self._t("doc_in_progress"),
            task=task,
            success_message=self._t("doc_done"),
            on_success=on_success,
        )
