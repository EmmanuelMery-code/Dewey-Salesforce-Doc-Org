"""Mixin — the single documentation task builder shared by every entry point.

Every way of producing documentation goes through
:meth:`AppDocumentationTaskMixin._build_documentation_task`:

* the ``Documentation`` menu and the "Generer la documentation" button
  (``AppGenerationMixin._start_generation``),
* the "Retrieve + Doc" and "Manifest + Retrieve + Doc" buttons
  (``AppSfCliMixin``),
* the ``--action documentation|all|retrivation`` steps, headless or visible
  (``AppCliActionsMixin``).

Keeping a single builder is deliberate: the generator takes some forty
options and the copies that used to exist had silently diverged, so the same
org documented through two different buttons did not yield the same report.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from src.core.data_dictionary_selection import DataDictionarySelection
from src.core.orchestrator import GenerationResult, SalesforceDocumentationGenerator


class AppDocumentationTaskMixin:
    """Builds the callable that runs a documentation generation."""

    def _build_documentation_task(
        self,
        source: Path,
        output: Path,
        org_ref: str,
        has_org: bool,
        exclusion_file: Path | None,
        pmd_ruleset: Path | None,
        *,
        generate_html_override: bool | None = None,
        generate_excels_override: bool | None = None,
        generate_data_dictionary_word_override: bool | None = None,
        generate_summary_word_override: bool | None = None,
        reset_command_stats: bool = True,
    ) -> Callable[[], GenerationResult]:
        """Return the task generating the documentation of ``source``.

        The ``*_override`` arguments let the Documentation menu produce a
        single format without touching the user's saved preferences; left at
        ``None`` they follow the configuration checkboxes.

        ``reset_command_stats`` must be ``False`` when the caller already
        reset them before an earlier step (manifest, retrieve), so the final
        command summary covers the whole pipeline and not just this task.
        """

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
        generate_sarif = bool(self.generate_sarif_var.get())
        generate_dd_excel = bool(self.generate_data_dictionary_excel_var.get())
        generate_findings_excel = bool(self.generate_findings_excel_var.get())
        dd_selection = (
            DataDictionarySelection.from_settings(self.settings)
            if generate_dd_excel
            else None
        )
        generate_org_check = bool(self.generate_org_check_reports_var.get())
        org_check_choice = self.org_check_choice_var.get().strip()
        run_alias = self._run_alias(org_ref)
        findings_paths = self._findings_paths(run_alias)

        def task() -> GenerationResult:
            if reset_command_stats:
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
                generate_sarif=generate_sarif,
                generate_data_dictionary_excel=generate_dd_excel,
                generate_findings_excel=generate_findings_excel,
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
            generator.alias = run_alias
            result = generator.generate()
            self.cli_service.log_command_summary()
            return result

        return task
