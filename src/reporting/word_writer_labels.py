"""Localized labels and constants for the Word report writer.

Extracted from ``word_writer.py`` to keep that module focused on the
document-building logic. These strings are intentionally local to the
Word writer (rather than the shared UI translations) so new keys can be
added without touching the front end.
"""

from __future__ import annotations


LABELS: dict[str, dict[str, str]] = {
    "fr": {
        "data_dictionary_doc_title": "Data Dictionary",
        "data_dictionary_subtitle": "Data Dictionary a la date du {date}",
        "table_of_contents": "Table des matieres",
        "table_of_contents_hint": (
            "(Ouvrez ce document dans Word puis appuyez sur F9 ou cliquez "
            "droit \"Mettre a jour les champs\" pour rafraichir la table.)"
        ),
        "object_chapter_title": "{label} ({api_name})",
        "object_chapter_title_simple": "{api_name}",
        "section_information": "Informations",
        "section_fields": "Champs",
        "info_api_name": "API Name",
        "info_label": "Label",
        "info_plural_label": "Label pluriel",
        "info_custom": "Objet personnalise",
        "info_sharing_model": "Modele de partage",
        "info_deployment_status": "Statut de deploiement",
        "info_visibility": "Visibilite",
        "info_record_types": "Nombre de record types",
        "info_validation_rules": "Nombre de validation rules",
        "info_relationships": "Nombre de relations",
        "info_field_count": "Nombre de champs",
        "info_custom_field_count": "Nombre de champs custom",
        "info_description": "Description",
        "yes": "Oui",
        "no": "Non",
        "value_unspecified": "Non renseigne",
        "field_column_label": "Label",
        "field_column_api_name": "API Name",
        "field_column_type": "Type",
        "field_column_description": "Description",
        "field_no_description": "Aucune description fournie.",
        "no_objects": (
            "Aucun objet n'a ete documente : la liste de metadata est vide "
            "ou tous les objets sont presents dans le fichier d'exclusion."
        ),
        "summary_doc_title": "Resume de l'analyse",
        "summary_subtitle": "Resume genere le {date}",
        "section_overview": "Vue d'ensemble",
        "section_metrics": "Metriques de personnalisation",
        "section_findings": "Etat de l'analyse statique",
        "section_advice": "Conseils",
        "advice_intro": (
            "Les actions ci-dessous sont triees de la plus prioritaire a la "
            "moins prioritaire. La priorite combine la severite de la regle "
            "et le nombre d'occurrences detectees."
        ),
        "advice_no_findings": (
            "Aucune action critique a signaler : l'analyse statique n'a "
            "remonte aucun finding pour les regles activees."
        ),
        "advice_action": "Action {index} - {title}",
        "advice_severity": "Severite",
        "advice_occurrences": "Occurrences detectees",
        "advice_examples": "Exemples concernes",
        "advice_examples_more": "... et {count} autre(s).",
        "advice_description": "Constat",
        "advice_rationale": "Pourquoi c'est important",
        "advice_remediation": "Action recommandee",
        "overview_metrics_intro": (
            "Cette section presente les principaux indicateurs collectes "
            "lors de l'analyse de l'org."
        ),
        "metric_objects": "Objets analyses",
        "metric_custom_objects": "Objets personnalises",
        "metric_custom_fields": "Champs personnalises",
        "metric_record_types": "Record types",
        "metric_validation_rules": "Validation rules",
        "metric_layouts": "Page layouts",
        "metric_custom_tabs": "Onglets custom",
        "metric_custom_apps": "Applications custom",
        "metric_flows": "Flows",
        "metric_apex_classes": "Classes Apex",
        "metric_apex_triggers": "Triggers Apex",
        "metric_lwc": "Composants LWC",
        "metric_flexipages": "Pages Lightning (FlexiPages)",
        "metric_omni_scripts": "OmniScripts",
        "metric_omni_integration_procedures": "Integration Procedures",
        "metric_omni_ui_cards": "UI Cards / FlexCards",
        "metric_omni_data_transforms": "Data Transforms",
        "metric_score": "Score de personnalisation",
        "metric_level": "Niveau",
        "metric_adopt_adapt_score": "Score Adopt vs Adapt",
        "metric_adopt_adapt_level": "Niveau Adopt vs Adapt",
        "metric_findings_total": "Findings totaux",
        "metric_findings_critical": "Findings Critical",
        "metric_findings_major": "Findings Major",
        "metric_findings_minor": "Findings Minor",
        "metric_findings_info": "Findings Info",
        "overview_intro": (
            "Ce document presente une vue d'ensemble de l'org Salesforce "
            "apres l'analyse complete et la creation de la documentation. "
            "Il couvre les principales metriques, l'etat de l'analyse "
            "statique et les actions recommandees."
        ),
        "severity_critical": "Critique",
        "severity_major": "Majeur",
        "severity_minor": "Mineur",
        "severity_info": "Info",
    },
    "en": {
        "data_dictionary_doc_title": "Data Dictionary",
        "data_dictionary_subtitle": "Data Dictionary as of {date}",
        "table_of_contents": "Table of contents",
        "table_of_contents_hint": (
            "(Open this document in Word and press F9 or right-click "
            "\"Update Field\" to refresh the table.)"
        ),
        "object_chapter_title": "{label} ({api_name})",
        "object_chapter_title_simple": "{api_name}",
        "section_information": "Information",
        "section_fields": "Fields",
        "info_api_name": "API Name",
        "info_label": "Label",
        "info_plural_label": "Plural label",
        "info_custom": "Custom object",
        "info_sharing_model": "Sharing model",
        "info_deployment_status": "Deployment status",
        "info_visibility": "Visibility",
        "info_record_types": "Record type count",
        "info_validation_rules": "Validation rule count",
        "info_relationships": "Relationship count",
        "info_field_count": "Field count",
        "info_custom_field_count": "Custom field count",
        "info_description": "Description",
        "yes": "Yes",
        "no": "No",
        "value_unspecified": "Not specified",
        "field_column_label": "Label",
        "field_column_api_name": "API Name",
        "field_column_type": "Type",
        "field_column_description": "Description",
        "field_no_description": "No description provided.",
        "no_objects": (
            "No object has been documented: the metadata list is empty or "
            "every object is filtered by the exclusion file."
        ),
        "summary_doc_title": "Analysis summary",
        "summary_subtitle": "Summary generated on {date}",
        "section_overview": "Overview",
        "section_metrics": "Customization metrics",
        "section_findings": "Static analysis status",
        "section_advice": "Advice",
        "advice_intro": (
            "The actions below are ordered from highest to lowest priority. "
            "Priority combines the rule severity with the number of "
            "detected occurrences."
        ),
        "advice_no_findings": (
            "No critical action to flag: static analysis did not raise any "
            "finding for the enabled rules."
        ),
        "advice_action": "Action {index} - {title}",
        "advice_severity": "Severity",
        "advice_occurrences": "Detected occurrences",
        "advice_examples": "Affected items",
        "advice_examples_more": "... and {count} more.",
        "advice_description": "Finding",
        "advice_rationale": "Why it matters",
        "advice_remediation": "Recommended action",
        "overview_metrics_intro": (
            "This section presents the main indicators captured while "
            "analysing the org."
        ),
        "metric_objects": "Analysed objects",
        "metric_custom_objects": "Custom objects",
        "metric_custom_fields": "Custom fields",
        "metric_record_types": "Record types",
        "metric_validation_rules": "Validation rules",
        "metric_layouts": "Page layouts",
        "metric_custom_tabs": "Custom tabs",
        "metric_custom_apps": "Custom apps",
        "metric_flows": "Flows",
        "metric_apex_classes": "Apex classes",
        "metric_apex_triggers": "Apex triggers",
        "metric_lwc": "LWC components",
        "metric_flexipages": "Lightning pages (FlexiPages)",
        "metric_omni_scripts": "OmniScripts",
        "metric_omni_integration_procedures": "Integration Procedures",
        "metric_omni_ui_cards": "UI Cards / FlexCards",
        "metric_omni_data_transforms": "Data Transforms",
        "metric_score": "Customization score",
        "metric_level": "Level",
        "metric_adopt_adapt_score": "Adopt vs Adapt score",
        "metric_adopt_adapt_level": "Adopt vs Adapt level",
        "metric_findings_total": "Total findings",
        "metric_findings_critical": "Critical findings",
        "metric_findings_major": "Major findings",
        "metric_findings_minor": "Minor findings",
        "metric_findings_info": "Info findings",
        "overview_intro": (
            "This document provides an overview of the Salesforce org "
            "after the full analysis and documentation generation. It "
            "covers the main metrics, the static analysis status, and the "
            "recommended actions."
        ),
        "severity_critical": "Critical",
        "severity_major": "Major",
        "severity_minor": "Minor",
        "severity_info": "Info",
    },
}


# How many affected items we list per advice action - longer lists make the
# document hard to read and add little value once the user reproduces the
# pattern locally.
ADVICE_TARGET_LIMIT = 8
