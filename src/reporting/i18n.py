"""Libelles localises de la documentation HTML generee.

Le contenu des findings (titre, description, justification, remediation,
message) est deja localise en amont par le catalogue de regles. Ce module ne
porte que l'habillage des pages : titres, en-tetes, etats vides et libelles de
severite.

La langue du rapport en cours de generation est portee par un etat de module,
comme la configuration du graphe One Page : l'orchestrateur appelle
``set_report_language`` avant la generation, et les renderers utilisent ``t``
sans avoir a faire transiter la langue dans chaque signature.
"""

from __future__ import annotations


DEFAULT_LANGUAGE = "fr"
SUPPORTED_LANGUAGES = ("fr", "en")

# Langue du rapport en cours de generation, alimentee par HtmlReportWriter.
CURRENT_LANGUAGE = DEFAULT_LANGUAGE


LABELS: dict[str, dict[str, str]] = {
    "fr": {
        # Severites
        "severity_critical": "Critique",
        "severity_major": "Majeur",
        "severity_minor": "Mineur",
        "severity_info": "Info",
        # Page globale des findings
        "findings_page_title": "Rapport des findings",
        "findings_page_heading": "Rapport global des findings",
        "findings_page_intro": (
            "Cette page regroupe l'ensemble des alertes detectees par l'analyseur "
            "statique sur l'organisation, triees par severite."
        ),
        "findings_empty": "Aucun finding detecte.",
        "findings_written_log": "Rapport global des findings genere : {path}",
        # Bloc finding
        "finding_impacted_item": "Item impacte :",
        "finding_rationale": "Justification :",
        "finding_remediation": "Remediation :",
        "finding_source": "Source :",
        "finding_reference": "Reference :",
        # Onglet Analyseur des pages de detail
        "analyzer_empty": "Aucun point d'alerte detecte par l'analyseur.",
        "analyzer_note": (
            "Regles inspirees de PMD Apex, du Salesforce Well-Architected Framework "
            "et des guides Salesforce Architects / Admins. Chaque regle peut etre "
            "activee ou desactivee dans <code>src/analyzer/rules.xml</code>."
        ),
        "pmd_empty": "Aucune violation PMD detectee.",
        # Panneau Analyseur de la page d'accueil
        "index_analyzer_not_run": "Analyseur non execute.",
        "index_analyzer_all_clear": (
            "Aucun finding : le projet respecte toutes les regles activees."
        ),
        "index_analyzer_severity_empty": "Aucun finding pour cette severite.",
        "index_analyzer_column_kind": "Type",
        "index_analyzer_column_component": "Composant",
        "index_analyzer_column_rules": "Regles impactees",
        "index_analyzer_note": (
            "Analyseur inspire de "
            "<a href='https://docs.pmd-code.org/latest/pmd_rules_apex.html' target='_blank' rel='noopener'>PMD Apex</a>, du "
            "<a href='https://architect.salesforce.com/docs/architect/well-architected/guide/overview.html' target='_blank' rel='noopener'>Salesforce Well-Architected Framework</a>, "
            "des <a href='https://architect.salesforce.com/decision-guides' target='_blank' rel='noopener'>Decision Guides Salesforce</a> et des bonnes pratiques "
            "<a href='https://admin.salesforce.com/' target='_blank' rel='noopener'>Salesforce Admins</a>. "
            "Les regles sont declarees dans <code>src/analyzer/rules.xml</code> et "
            "peuvent etre activees / desactivees via l'attribut <code>enabled</code>."
        ),
    },
    "en": {
        # Severities
        "severity_critical": "Critical",
        "severity_major": "Major",
        "severity_minor": "Minor",
        "severity_info": "Info",
        # Global findings page
        "findings_page_title": "Findings report",
        "findings_page_heading": "Global findings report",
        "findings_page_intro": (
            "This page gathers every alert raised by the static analyzer on the "
            "org, sorted by severity."
        ),
        "findings_empty": "No finding detected.",
        "findings_written_log": "Global findings report generated: {path}",
        # Finding block
        "finding_impacted_item": "Impacted item:",
        "finding_rationale": "Rationale:",
        "finding_remediation": "Remediation:",
        "finding_source": "Source:",
        "finding_reference": "Reference:",
        # Analyzer tab on detail pages
        "analyzer_empty": "No alert raised by the analyzer.",
        "analyzer_note": (
            "Rules inspired by PMD Apex, the Salesforce Well-Architected Framework "
            "and the Salesforce Architects / Admins guides. Each rule can be enabled "
            "or disabled in <code>src/analyzer/rules.xml</code>."
        ),
        "pmd_empty": "No PMD violation detected.",
        # Analyzer panel on the home page
        "index_analyzer_not_run": "Analyzer not run.",
        "index_analyzer_all_clear": (
            "No finding: the project complies with every enabled rule."
        ),
        "index_analyzer_severity_empty": "No finding for this severity.",
        "index_analyzer_column_kind": "Type",
        "index_analyzer_column_component": "Component",
        "index_analyzer_column_rules": "Rules triggered",
        "index_analyzer_note": (
            "Analyzer inspired by "
            "<a href='https://docs.pmd-code.org/latest/pmd_rules_apex.html' target='_blank' rel='noopener'>PMD Apex</a>, the "
            "<a href='https://architect.salesforce.com/docs/architect/well-architected/guide/overview.html' target='_blank' rel='noopener'>Salesforce Well-Architected Framework</a>, "
            "the <a href='https://architect.salesforce.com/decision-guides' target='_blank' rel='noopener'>Salesforce Decision Guides</a> and the "
            "<a href='https://admin.salesforce.com/' target='_blank' rel='noopener'>Salesforce Admins</a> best practices. "
            "The rules are declared in <code>src/analyzer/rules.xml</code> and can be "
            "enabled / disabled through the <code>enabled</code> attribute."
        ),
    },
}


SEVERITY_LABEL_KEYS: dict[str, str] = {
    "Critical": "severity_critical",
    "Major": "severity_major",
    "Minor": "severity_minor",
    "Info": "severity_info",
}


def normalize_language(language: str | None) -> str:
    """Return a supported language code, falling back to French."""
    if language and language.lower() in SUPPORTED_LANGUAGES:
        return language.lower()
    return DEFAULT_LANGUAGE


def translate(language: str | None, key: str, **params: object) -> str:
    """Return the ``key`` label in ``language``, falling back to French."""
    labels = LABELS.get(normalize_language(language), LABELS[DEFAULT_LANGUAGE])
    template = labels.get(key) or LABELS[DEFAULT_LANGUAGE].get(key)
    if template is None:
        return key
    if not params:
        return template
    try:
        return template.format(**params)
    except (KeyError, IndexError):
        return template


def set_report_language(language: str | None) -> None:
    """Declare the language of the documentation being generated."""
    global CURRENT_LANGUAGE
    CURRENT_LANGUAGE = normalize_language(language)


def t(key: str, **params: object) -> str:
    """Return the ``key`` label in the current report language."""
    return translate(CURRENT_LANGUAGE, key, **params)


def severity_label(severity: str, language: str | None = None) -> str:
    """Return the localized label for an analyzer severity."""
    key = SEVERITY_LABEL_KEYS.get(severity)
    if key is None:
        return severity
    return translate(language or CURRENT_LANGUAGE, key)
