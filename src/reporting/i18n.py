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
        # Ossature partagee par toutes les pages
        "back_to_index": "Retour a l'index",
        "global_search_placeholder": "Recherche globale...",
        # Onglets des pages de detail
        "tab_summary": "Resume",
        "tab_synthesis": "Synthese",
        "tab_metrics": "Metriques",
        "tab_strengths": "Points forts",
        "tab_heuristics": "Heuristiques",
        "tab_analyzer": "Analyseur",
        "tab_links": "Liens",
        "tab_graph": "Graphe",
        "tab_source_code": "Code source",
        "tab_relationships": "Relations",
        "tab_chart": "Graphique",
        "tab_breakdown": "Repartition",
        "tab_elements": "Elements",
        # Communs aux pages de detail
        "detail_analyzer_alerts": "Alertes analyseur",
        "detail_no_strengths": "Aucun point fort automatique detecte.",
        "detail_no_improvements": "Aucun point d'amelioration automatique detecte.",
        "detail_test_coverage": "Couverture de tests",
        "value_not_set": "Non renseigne",
        "value_yes": "Oui",
        "value_no": "Non",
        # Page objet
        "object_card_fields": "Champs",
        "object_card_record_types": "Record types",
        "object_card_validation_rules": "Regles de validation",
        "object_card_relationships": "Relations",
        "object_field_used_in": "Utilise dans {count} composant(s)",
        "object_fields_empty": "Aucun champ detecte.",
        "object_record_types_empty": "Aucun record type detecte.",
        "object_validation_rules_empty": "Aucune regle de validation detectee.",
        "object_validation_details_empty": "Aucune regle de validation detaillee.",
        "object_relationships_empty": "Aucune relation detectee.",
        "object_profiles_empty": "Aucun profil avec acces detecte.",
        "object_permission_sets_empty": "Aucun permission set avec acces detecte.",
        "object_meta_api_name": "Nom API",
        "object_meta_plural_label": "Label pluriel",
        "object_meta_visibility": "Visibilite",
        "object_meta_dewey_comment": "Commentaire Dewey",
        "object_meta_piloted_by": "Piloté par",
        "object_meta_squad": "Squad Responsable",
        "object_meta_squad_consumer": "Squad Consommatrice",
        "object_th_name": "Nom",
        "object_th_active": "Actif",
        "object_th_error_field": "Champ d'erreur",
        "object_th_error_message": "Message d'erreur",
        "object_th_relationship_field": "Champ",
        "object_th_relationship_target": "Cible",
        "object_vr_description": "Description:",
        "object_vr_description_not_set": "Non renseignee",
        "object_vr_error_message": "Message d'erreur:",
        "object_vr_decision_tree": "Arbre de decision (Mermaid)",
        "object_vr_formula": "Formule",
        "object_outgoing_relationships": "Relations sortantes (Lookups)",
        "object_impact_analysis": "Analyse d'impact (Ou est-il utilise ?)",
        # En-tetes des tableaux Profils / Permission Sets
        "security_th_read": "Lecture",
        "security_th_create": "Creation",
        "security_th_edit": "Modification",
        "security_th_delete": "Suppression",
        "security_th_visible_fields": "Nb champs visibles",
        "security_th_editable_fields": "Nb champs modifiables",
        # Page Apex
        "apex_th_rule": "Regle",
        "apex_th_priority": "Priorite",
        "apex_th_line": "Ligne",
        "apex_th_message": "Message",
        # Page Flow
        "flow_card_complexity_score": "Score complexite",
        "flow_card_elements": "Elements",
        "flow_card_documented": "Documentes",
        "flow_card_variables": "Variables",
        "flow_card_depth": "Profondeur",
        "flow_card_max_width": "Largeur max",
        "flow_card_min_max_height": "Hauteur min/max",
        "flow_complexity_simple": "Simple",
        "flow_complexity_medium": "Moyen",
        "flow_complexity_complex": "Complexe",
        "flow_complexity_very_complex": "Tres complexe",
        "flow_elements_empty": "Aucun element detecte.",
        "flow_blocks_empty": "Aucun bloc detecte.",
        "flow_th_count": "Nombre",
        "flow_th_label": "Label",
        "flow_th_target": "Cible",
        "flow_th_tested_by": "Teste par",
        "flow_tested_by_title": "Teste par {classes}",
        "flow_tested_yes": "Oui ({count})",
        "flow_coverage_value": "{percent} % ({covered}/{total} blocs API)",
        "flow_coverage_tooltip": (
            "% de blocs testes calcule par l'API Tooling Salesforce (FlowTestCoverage). "
            "Un 'bloc' est plus granulaire qu'un element du flow : chaque branche de decision, "
            "chaque sortie de boucle ou chemin de fault est compte separement, d'ou un total "
            "de blocs generalement superieur au nombre d'elements nommes ci-dessus."
        ),
        "flow_graph_heading": "Représentation graphique",
        "flow_graph_hint": (
            "Utilisez la molette pour zoomer, glissez pour déplacer le graphique ou "
            "les nœuds. Survolez les éléments colorés pour voir les alertes."
        ),
        "flow_graph_start": "Début",
        "flow_graph_improvement": "Amélioration",
        "flow_graph_legend_critical": "Critique (Analyseur)",
        "flow_graph_legend_major": "Majeur / Amélioration (Heuristique)",
        "flow_graph_legend_start": "Début",
        # Barre d'outils Mermaid partagee
        "mermaid_zoom_in": "Zoom avant",
        "mermaid_zoom_out": "Zoom arrière",
        "mermaid_reset": "Réinitialiser",
        # Tableaux et graphe de dependances
        "dependency_empty": "Aucun lien detecte.",
        "dependency_graph_empty": "Aucun graphe a afficher, aucun lien n'a ete detecte.",
        "dependency_th_component": "Composant",
        "dependency_th_linked_component": "Composant lie",
        "dependency_th_category": "Categorie",
        "dependency_th_subtype": "Sous-type",
        "dependency_th_direction": "Sens",
        "dependency_th_relation": "Nature du lien",
        "dependency_graph_fit": "Centrer",
        "dependency_show_incoming": "Afficher entrants",
        "dependency_show_outgoing": "Afficher sortants",
        "dependency_show_classes": "Afficher classes",
        "dependency_show_triggers": "Afficher triggers",
        "dependency_show_objects": "Afficher objets",
        "dependency_show_flows": "Afficher flows",
        "dependency_show_metadata": "Afficher metadata",
        "dependency_legend_center": "Apex/Trigger central",
        "dependency_legend_other_apex": "Autres Apex/Trigger",
        "dependency_legend_objects": "Objets",
        "dependency_legend_flows": "Flows",
        "dependency_legend_metadata": "Metadata",
        # Valeurs de domaine des dependances (affichage uniquement)
        "dependency_direction_incoming": "Entrant",
        "dependency_direction_outgoing": "Sortant",
        "dependency_category_apex": "Apex",
        "dependency_category_object": "Objet",
        "dependency_category_flow": "Flow",
        "dependency_category_field": "Champ",
        "dependency_category_metadata": "Metadata",
        "dependency_category_report": "Rapport",
        "dependency_relation_start_object": "Objet de depart",
        "dependency_relation_apex_reference": "Reference Apex",
        "dependency_relation_code_reference": "Reference code",
        "dependency_relation_flow_reference": "Reference flow",
        "dependency_relation_metadata_reference": "Reference metadata",
        "dependency_relation_field_usage": "Usage champ",
        "dependency_relation_object_usage": "Usage objet",
        "dependency_relation_usage": "Usage",
        "dependency_relation_flow_call": "Appel depuis Flow",
        "dependency_relation_report_source": "Source du rapport",
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
        # Shell shared by every page
        "back_to_index": "Back to index",
        "global_search_placeholder": "Global search...",
        # Detail page tabs
        "tab_summary": "Summary",
        "tab_synthesis": "Overview",
        "tab_metrics": "Metrics",
        "tab_strengths": "Strengths",
        "tab_heuristics": "Heuristics",
        "tab_analyzer": "Analyzer",
        "tab_links": "Links",
        "tab_graph": "Graph",
        "tab_source_code": "Source code",
        "tab_relationships": "Relationships",
        "tab_chart": "Chart",
        "tab_breakdown": "Breakdown",
        "tab_elements": "Elements",
        # Shared across detail pages
        "detail_analyzer_alerts": "Analyzer alerts",
        "detail_no_strengths": "No automatic strength detected.",
        "detail_no_improvements": "No automatic improvement detected.",
        "detail_test_coverage": "Test coverage",
        "value_not_set": "Not set",
        "value_yes": "Yes",
        "value_no": "No",
        # Object page
        "object_card_fields": "Fields",
        "object_card_record_types": "Record types",
        "object_card_validation_rules": "Validation rules",
        "object_card_relationships": "Relationships",
        "object_field_used_in": "Used in {count} component(s)",
        "object_fields_empty": "No field detected.",
        "object_record_types_empty": "No record type detected.",
        "object_validation_rules_empty": "No validation rule detected.",
        "object_validation_details_empty": "No detailed validation rule.",
        "object_relationships_empty": "No relationship detected.",
        "object_profiles_empty": "No profile with access detected.",
        "object_permission_sets_empty": "No permission set with access detected.",
        "object_meta_api_name": "API name",
        "object_meta_plural_label": "Plural label",
        "object_meta_visibility": "Visibility",
        "object_meta_dewey_comment": "Dewey comment",
        "object_meta_piloted_by": "Piloted by",
        "object_meta_squad": "Owning squad",
        "object_meta_squad_consumer": "Consuming squad",
        "object_th_name": "Name",
        "object_th_active": "Active",
        "object_th_error_field": "Error field",
        "object_th_error_message": "Error message",
        "object_th_relationship_field": "Field",
        "object_th_relationship_target": "Target",
        "object_vr_description": "Description:",
        "object_vr_description_not_set": "Not set",
        "object_vr_error_message": "Error message:",
        "object_vr_decision_tree": "Decision tree (Mermaid)",
        "object_vr_formula": "Formula",
        "object_outgoing_relationships": "Outgoing relationships (lookups)",
        "object_impact_analysis": "Impact analysis (where is it used?)",
        # Profiles / Permission Sets table headers
        "security_th_read": "Read",
        "security_th_create": "Create",
        "security_th_edit": "Edit",
        "security_th_delete": "Delete",
        "security_th_visible_fields": "Visible fields",
        "security_th_editable_fields": "Editable fields",
        # Apex page
        "apex_th_rule": "Rule",
        "apex_th_priority": "Priority",
        "apex_th_line": "Line",
        "apex_th_message": "Message",
        # Flow page
        "flow_card_complexity_score": "Complexity score",
        "flow_card_elements": "Elements",
        "flow_card_documented": "Documented",
        "flow_card_variables": "Variables",
        "flow_card_depth": "Depth",
        "flow_card_max_width": "Max width",
        "flow_card_min_max_height": "Min/max height",
        "flow_complexity_simple": "Simple",
        "flow_complexity_medium": "Medium",
        "flow_complexity_complex": "Complex",
        "flow_complexity_very_complex": "Very complex",
        "flow_elements_empty": "No element detected.",
        "flow_blocks_empty": "No block detected.",
        "flow_th_count": "Count",
        "flow_th_label": "Label",
        "flow_th_target": "Target",
        "flow_th_tested_by": "Tested by",
        "flow_tested_by_title": "Tested by {classes}",
        "flow_tested_yes": "Yes ({count})",
        "flow_coverage_value": "{percent} % ({covered}/{total} API blocks)",
        "flow_coverage_tooltip": (
            "% of tested blocks computed by the Salesforce Tooling API "
            "(FlowTestCoverage). A 'block' is more granular than a flow element: each "
            "decision branch, each loop exit and each fault path is counted separately, "
            "hence a block total usually higher than the number of named elements above."
        ),
        "flow_graph_heading": "Graphical representation",
        "flow_graph_hint": (
            "Use the wheel to zoom, drag to move the graph or the nodes. Hover the "
            "coloured elements to see the alerts."
        ),
        "flow_graph_start": "Start",
        "flow_graph_improvement": "Improvement",
        "flow_graph_legend_critical": "Critical (analyzer)",
        "flow_graph_legend_major": "Major / improvement (heuristic)",
        "flow_graph_legend_start": "Start",
        # Shared Mermaid toolbar
        "mermaid_zoom_in": "Zoom in",
        "mermaid_zoom_out": "Zoom out",
        "mermaid_reset": "Reset",
        # Dependency tables and graph
        "dependency_empty": "No link detected.",
        "dependency_graph_empty": "No graph to display, no link was detected.",
        "dependency_th_component": "Component",
        "dependency_th_linked_component": "Linked component",
        "dependency_th_category": "Category",
        "dependency_th_subtype": "Subtype",
        "dependency_th_direction": "Direction",
        "dependency_th_relation": "Link type",
        "dependency_graph_fit": "Fit",
        "dependency_show_incoming": "Show incoming",
        "dependency_show_outgoing": "Show outgoing",
        "dependency_show_classes": "Show classes",
        "dependency_show_triggers": "Show triggers",
        "dependency_show_objects": "Show objects",
        "dependency_show_flows": "Show flows",
        "dependency_show_metadata": "Show metadata",
        "dependency_legend_center": "Central Apex/Trigger",
        "dependency_legend_other_apex": "Other Apex/Trigger",
        "dependency_legend_objects": "Objects",
        "dependency_legend_flows": "Flows",
        "dependency_legend_metadata": "Metadata",
        # Dependency domain values (display only)
        "dependency_direction_incoming": "Incoming",
        "dependency_direction_outgoing": "Outgoing",
        "dependency_category_apex": "Apex",
        "dependency_category_object": "Object",
        "dependency_category_flow": "Flow",
        "dependency_category_field": "Field",
        "dependency_category_metadata": "Metadata",
        "dependency_category_report": "Report",
        "dependency_relation_start_object": "Start object",
        "dependency_relation_apex_reference": "Apex reference",
        "dependency_relation_code_reference": "Code reference",
        "dependency_relation_flow_reference": "Flow reference",
        "dependency_relation_metadata_reference": "Metadata reference",
        "dependency_relation_field_usage": "Field usage",
        "dependency_relation_object_usage": "Object usage",
        "dependency_relation_usage": "Usage",
        "dependency_relation_flow_call": "Called from Flow",
        "dependency_relation_report_source": "Report source",
    },
}


SEVERITY_LABEL_KEYS: dict[str, str] = {
    "Critical": "severity_critical",
    "Major": "severity_major",
    "Minor": "severity_minor",
    "Info": "severity_info",
}

#: Les valeurs ci-dessous restent stockees en francais dans le modele : elles
#: servent de cles (classes CSS, comparaisons d'heuristiques, deduplication des
#: dependances, filtres JavaScript du graphe). Seul leur affichage est traduit.
FLOW_COMPLEXITY_LABEL_KEYS: dict[str, str] = {
    "Simple": "flow_complexity_simple",
    "Moyen": "flow_complexity_medium",
    "Complexe": "flow_complexity_complex",
    "Tres complexe": "flow_complexity_very_complex",
}

DEPENDENCY_DIRECTION_LABEL_KEYS: dict[str, str] = {
    "Entrant": "dependency_direction_incoming",
    "Sortant": "dependency_direction_outgoing",
}

DEPENDENCY_CATEGORY_LABEL_KEYS: dict[str, str] = {
    "Apex": "dependency_category_apex",
    "Objet": "dependency_category_object",
    "Object": "dependency_category_object",
    "Flow": "dependency_category_flow",
    "Field": "dependency_category_field",
    "Metadata": "dependency_category_metadata",
    "Report": "dependency_category_report",
}

DEPENDENCY_RELATION_LABEL_KEYS: dict[str, str] = {
    "Objet de depart": "dependency_relation_start_object",
    "Reference Apex": "dependency_relation_apex_reference",
    "Reference code": "dependency_relation_code_reference",
    "Reference flow": "dependency_relation_flow_reference",
    "Reference metadata": "dependency_relation_metadata_reference",
    "Usage champ": "dependency_relation_field_usage",
    "Usage objet": "dependency_relation_object_usage",
    "Usage": "dependency_relation_usage",
    "Appel depuis Flow": "dependency_relation_flow_call",
    "Source du rapport": "dependency_relation_report_source",
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


def report_language() -> str:
    """Return the language code of the documentation being generated."""
    return CURRENT_LANGUAGE


def t(key: str, **params: object) -> str:
    """Return the ``key`` label in the current report language."""
    return translate(CURRENT_LANGUAGE, key, **params)


def severity_label(severity: str, language: str | None = None) -> str:
    """Return the localized label for an analyzer severity."""
    key = SEVERITY_LABEL_KEYS.get(severity)
    if key is None:
        return severity
    return translate(language or CURRENT_LANGUAGE, key)


def _domain_label(mapping: dict[str, str], value: str) -> str:
    """Translate a domain ``value`` for display, leaving unknown values untouched."""
    key = mapping.get(value)
    if key is None:
        return value
    return t(key)


def flow_complexity_label(level: str) -> str:
    """Localize a flow complexity level for display only.

    ``FlowInfo.complexity_level`` is a domain value: it keys the badge CSS class
    and drives the heuristics comparisons, so it must never be translated at the
    source.
    """
    return _domain_label(FLOW_COMPLEXITY_LABEL_KEYS, level)


def dependency_direction_label(direction: str) -> str:
    """Localize a dependency direction for display only."""
    return _domain_label(DEPENDENCY_DIRECTION_LABEL_KEYS, direction)


def dependency_category_label(category: str) -> str:
    """Localize a dependency category for display only."""
    return _domain_label(DEPENDENCY_CATEGORY_LABEL_KEYS, category)


def dependency_relation_label(relation: str) -> str:
    """Localize a dependency relation for display only."""
    return _domain_label(DEPENDENCY_RELATION_LABEL_KEYS, relation)
