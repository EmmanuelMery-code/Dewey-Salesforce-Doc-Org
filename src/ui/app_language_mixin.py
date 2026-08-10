"""Mixin — translations and language management for :class:`Application`."""

from __future__ import annotations


class AppLanguageMixin:
    """Translation helper and language-change handling."""

    def _t(self, key: str, **kwargs) -> str:
        text = self.TRANSLATIONS.get(self.language, self.TRANSLATIONS["fr"]).get(key, key)
        return text.format(**kwargs)

    def _language_display(self, code: str) -> str:
        return self.LANGUAGES.get(code, "Francais")

    def _language_code_from_display(self, display: str) -> str:
        for code, label in self.LANGUAGES.items():
            if label == display:
                return code
        return "fr"

    def _login_target_display(self, key: str) -> str:
        return self._t(key)

    def _login_target_key_from_display(self, display: str) -> str:
        for key in self.LOGIN_TARGETS:
            if self._login_target_display(key) == display:
                return key
        return "production"

    def _apply_language(self, initial: bool = False) -> None:
        self._build_menu_bar()
        self.title(self._t("window_title"))
        self.title_label.configure(text=self._t("header_title"))
        self.description_label.configure(text=self._t("header_description"))
        self.language_title_label.configure(text=self._t("language"))
        self.cli_frame.configure(text=self._t("salesforce_cli"))
        self.alias_label.configure(text=self._t("alias"))
        self.environment_label.configure(text=self._t("environment"))
        self.instance_url_label.configure(text=self._t("instance_url"))
        self.org_available_label.configure(text=self._t("org_available"))
        self.org_check_frame.configure(text=self._t("org_check"))
        self.org_check_type_label.configure(text=self._t("org_check_type"))
        self.doc_frame.configure(text=self._t("documentation_generation"))
        self.source_folder_widgets["label"].configure(text=self._t("source_folder"))
        self.source_folder_widgets["browse_button"].configure(text=self._t("browse"))
        self.source_folder_widgets["open_button"].configure(text=self._t("open"))
        self.source_folder_widgets["clear_button"].configure(text=self._t("clear_folder"))
        self.output_folder_widgets["label"].configure(text=self._t("output_folder"))
        self.output_folder_widgets["browse_button"].configure(text=self._t("browse"))
        self.output_folder_widgets["open_button"].configure(text=self._t("open"))
        self.output_folder_widgets["clear_button"].configure(text=self._t("clear_folder"))
        self.exclusion_file_widgets["label"].configure(text=self._t("exclusion_file"))
        self.exclusion_file_widgets["browse_button"].configure(text=self._t("browse"))
        self.exclusion_file_widgets["open_button"].configure(text=self._t("open"))
        self.pmd_frame.configure(text=self._t("pmd_quality"))
        self.pmd_enabled_check.configure(text=self._t("pmd_enabled"))
        self.pmd_file_widgets["label"].configure(text=self._t("pmd_ruleset_file"))
        self.pmd_file_widgets["browse_button"].configure(text=self._t("browse"))
        self.pmd_file_widgets["open_button"].configure(text=self._t("open"))
        self.analyzer_rules_file_widgets["label"].configure(
            text=self._t("configuration_rules_file_label")
        )
        self.analyzer_rules_file_widgets["browse_button"].configure(text=self._t("browse"))
        self.analyzer_rules_file_widgets["open_button"].configure(text=self._t("open"))
        self.login_button.configure(text=self._t("web_login"))
        self.refresh_button.configure(text=self._t("refresh"))
        self.generate_manifest_button.configure(text=self._t("generate_manifest"))
        self.retrieve_button.configure(text=self._t("retrieve"))
        self.delete_button.configure(text=self._t("delete"))
        self.full_pipeline_button.configure(text=self._t("full_pipeline"))
        self.org_check_button.configure(text=self._t("generate_org_check_excel"))
        self.generate_button.configure(text=self._t("generate_doc"))
        self.open_index_button.configure(text=self._t("open_index"))
        self.status_var.set(self._t("ready") if initial else self.status_var.get())

        self.main_notebook.tab(self.documentation_tab, text=self._t("tab_documentation"))
        self.main_notebook.tab(self.discussion_tab, text=self._t("tab_discussion"))
        self.discussion_title_label.configure(text=self._t("discussion_title"))
        self.discussion_description_label.configure(text=self._t("discussion_description"))
        self.discussion_provider_label.configure(text=self._t("discussion_provider"))
        self.discussion_history_label.configure(text=self._t("discussion_history"))
        self.discussion_input_label.configure(text=self._t("discussion_input"))
        self.discussion_send_button.configure(text=self._t("discussion_send"))
        self.discussion_clear_button.configure(text=self._t("discussion_clear"))
        self.discussion_summarize_button.configure(text=self._t("discussion_summarize_org"))
        self.discussion_prev_button.configure(text=self._t("discussion_prev"))
        self.discussion_next_button.configure(text=self._t("discussion_next"))
        self.discussion_copy_last_button.configure(text=self._t("discussion_copy_last"))
        self.discussion_copy_current_button.configure(text=self._t("discussion_copy_current"))
        self.discussion_copy_all_button.configure(text=self._t("discussion_copy_all"))
        self.discussion_force_docs_button.configure(
            text=self._t(
                "discussion_force_docs_active"
                if self.discussion_force_existing_docs
                else "discussion_force_docs"
            )
        )
        self.log_clear_button.configure(text=self._t("log_clear"))
        self._update_discussion_context_status()

        self.language_combo["values"] = [
            self._language_display(code) for code in self.LANGUAGES
        ]
        self.language_label_var.set(self._language_display(self.language))
        self.login_target_combo["values"] = [
            self._login_target_display(key) for key in self.LOGIN_TARGETS
        ]
        self.login_target_var.set(self._login_target_display(self.login_target_key))
        self._on_login_target_changed()
        self._apply_pmd_state()

    def _on_language_changed(self, _event=None) -> None:
        new_language = self._language_code_from_display(self.language_label_var.get())
        if new_language == self.language:
            return
        self.language = new_language
        self._apply_language()
        self._save_settings()
        self._append_log(self._t("language_changed"))
