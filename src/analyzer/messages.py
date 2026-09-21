"""Catalogue des messages de findings, en francais et en anglais.

Les analyseurs ne construisent plus de chaines litterales : ils demandent une
cle a ce catalogue via ``RuleCatalog.t``. La langue est celle choisie dans
l'interface, portee par le catalogue de regles jusqu'aux analyseurs, de sorte
que les findings sont deja localises quand ils arrivent aux generateurs HTML,
Excel, Word et SARIF.

Les valeurs numeriques sensibles au formatage (pourcentages, ratios) sont
formatees par l'appelant et passees comme chaines : les gabarits restent ainsi
de simples ``{placeholder}``.
"""

from __future__ import annotations


DEFAULT_LANGUAGE = "fr"
SUPPORTED_LANGUAGES = ("fr", "en")


MESSAGES: dict[str, dict[str, str]] = {
    "fr": {
        # ---------------------------------------------------------- Apex classes
        "apex.sharing.message": (
            "Aucune declaration 'with sharing' / 'without sharing' / "
            "'inherited sharing' detectee."
        ),
        "apex.sharing.detail": (
            "Par defaut la classe herite du contexte appelant, ce qui peut "
            "contourner les partages."
        ),
        "apex.hardcoded_id.message": "{count} identifiant(s) Salesforce ecrit(s) en dur detecte(s).",
        "apex.hardcoded_id.detail": "Exemples: {sample}",
        "apex.soql_injection.message": "Risque d'injection SOQL detecte dans une requete dynamique.",
        "apex.soql_injection.detail": (
            "L'utilisation de Database.query() avec des variables concatenees "
            "sans echappement est risquee."
        ),
        "apex.crud_fls.message": "Absence de controle CRUD/FLS explicite detectee.",
        "apex.crud_fls.detail": (
            "La classe effectue des operations de donnees sans utiliser "
            "WITH USER_MODE, Security.stripInaccessible() ou WITH SECURITY_ENFORCED."
        ),
        "apex.no_try_catch.message": "Acces aux donnees sans gestion d'exception (aucun bloc try/catch).",
        "apex.soql_dml_counts.detail": "SOQL = {soql}, DML = {dml}.",
        "apex.soql_in_loop.message": "Une requete SOQL apparait potentiellement dans une boucle.",
        "apex.dml_in_loop.message": "Un DML apparait potentiellement dans une boucle.",
        "apex.callout_in_loop.message": (
            "Un callout HTTP (Http/HttpRequest) apparait potentiellement dans une boucle."
        ),
        "apex.recursion.message": (
            "{count} methode(s) s'invoquent elles-memes sans mecanisme visible "
            "de garde d'arret."
        ),
        "apex.recursion.detail_methods": "Methode(s) concernee(s) : {sample}.",
        "apex.recursion.detail_more": "+ {count} autre(s) methode(s) avec auto-appel.",
        "apex.recursion.detail_no_guard": (
            "Aucune garde de reentrance evidente (Set<Id>/flag static) consultee "
            "dans la methode."
        ),
        "apex.class_length.message": (
            "Classe de {lines} lignes de code hors commentaires (seuil recommande : 500)."
        ),
        "apex.class_length.detail": (
            "{code} lignes de code sur {total} lignes de fichier "
            "(commentaires et lignes vides exclus)."
        ),
        "apex.comment_density.message": "Densite de commentaires = {ratio} (recommande >= 5%).",
        "apex.comment_density.detail": "{commented} lignes commentees sur {total}.",
        "apex.system_debug.message": "{count} appels 'System.debug' presents dans la classe.",
        # ---------------------------------------------------------- Apex triggers
        "trigger.business_logic.message": (
            "Le trigger porte de la logique metier (code substantiel ou "
            "operations de donnees)."
        ),
        "trigger.business_logic.detail_lines": "Lignes de code detectees : {count}.",
        "trigger.after_save_recursion.message": (
            "Le trigger modifie ses propres enregistrements declencheurs dans un "
            "contexte after-save : risque de boucle infinie."
        ),
        "trigger.after_save_recursion.detail_events": "Evenements declares : {events}.",
        "trigger.after_save_recursion.detail_operation": "Operation detectee : {operation}.",
        "trigger.after_save_recursion.detail_no_guard": (
            "Aucune garde de reentrance (Set<Id> static / classe TriggerHandler) "
            "trouvee dans le trigger."
        ),
        "trigger.data_ops_in_loop.message": "Operations de donnees potentiellement dans une boucle : {parts}.",
        "trigger.part.soql_in_loop": "SOQL dans une boucle",
        "trigger.part.dml_in_loop": "DML dans une boucle",
        # ---------------------------------------------------------- Apex call graph
        "apex.cycle.message": "Classe impliquee dans un cycle d'appels avec {others}.",
        "apex.cycle.self": "elle-meme",
        "apex.cycle.detail_classes": "Classes participant au cycle : {classes}.",
        "apex.cycle.detail_chain": "Chaine simplifiee : {chain}.",
        # ---------------------------------------------------------- Flows
        "flow.no_description.message": "Le flow ne porte pas de description globale.",
        "flow.described_ratio.message": "Seulement {ratio} des elements du flow portent une description.",
        "flow.described_ratio.detail": "{described}/{total} elements documentes.",
        "flow.size.message": "Flow comportant {count} elements (seuil recommande : 40).",
        "flow.decisions.message": "{count} decisions detectees dans le flow (seuil recommande : 8).",
        "flow.data_ops.message": "{count} operations de donnees (create/update/delete/lookup) detectees.",
        "flow.data_ops.detail": (
            "Lookups = {lookups}, Creates = {creates}, Updates = {updates}, Deletes = {deletes}."
        ),
        "flow.soql_in_loop.message": "Une operation de lecture (Get Records) apparait dans une boucle.",
        "flow.dml_in_loop.message": "Une operation d'ecriture (Create/Update/Delete) apparait dans une boucle.",
        "flow.api_in_loop.message": (
            "Un appel d'action External Service apparait potentiellement dans une boucle."
        ),
        "flow.api_in_loop.detail": "Action(s) concernee(s) : {actions}.",
        "flow.api_in_loop.unknown_action": "action non identifiee",
        "flow.fault_path.message": (
            "{unprotected} element(s) sur {total} pouvant echouer ne declarent pas "
            "de chemin d'erreur (fault path)."
        ),
        "flow.fault_path.detail": "{kind} '{name}' : aucun chemin d'erreur.",
        "flow.fault_path.detail_more": "... et {count} autre(s) element(s) non protege(s).",
        "flow.depth.message": "Profondeur maximale = {depth} (seuil recommande : 4).",
        "flow.status.message": "Le flow est au statut '{status}'.",
        "flow.status.unknown": "Non renseigne",
        # ---------------------------------------------------------- LWC / Aura
        "lwc.js_size.message": "Composant JS volumineux ({lines} lignes).",
        "lwc.js_size.detail": (
            "Considerez un decoupage en sous-composants ou l'utilisation de "
            "modules de service."
        ),
        "lwc.html_size.message": "Template HTML volumineux ({lines} lignes).",
        "lwc.aura_enabled.message": "Le composant utilise @AuraEnabled pour appeler de l'Apex.",
        "lwc.aura_enabled.detail": (
            "Verifiez que les classes Apex appelees respectent les regles de "
            "securite (CRUD/FLS)."
        ),
        "lwc.console.message": "Presence de console.log ou console.error detectee.",
        "lwc.metadata.message": "Label ou description manquant dans les metadonnees.",
        "aura.size.message": "Composant Aura volumineux.",
        "aura.size.detail_lines": "CMP: {cmp_lines} lignes, JS: {js_lines} lignes.",
        "aura.size.detail_migrate": (
            "Considerez une migration vers LWC pour de meilleures performances et "
            "maintenabilite."
        ),
        # ---------------------------------------------------------- Objects
        "object.no_description.message": "Objet personnalise sans description metadata.",
        "object.too_many_fields.message": "{count} champs personnalises sur l'objet (seuil recommande : 50).",
        "object.too_many_validation_rules.message": (
            "{count} validation rules actives sur l'objet (seuil recommande : 10)."
        ),
        "object.too_many_record_types.message": "{count} record types actifs (seuil recommande : 3).",
        "field.no_description.message": "{count} champ(s) personnalise(s) sans description.",
        "field.no_description.detail": "Champs concernes : {preview}.",
        "validation_rule.no_description.message": "La validation rule ne fournit pas de description.",
        "validation_rule.complexity.message": "Formule complexe (score={score}).",
        "validation_rule.complexity.detail_length": "Longueur: {length} caracteres.",
        "validation_rule.complexity.detail_advice": (
            "Considerez une simplification ou un passage en Apex si la logique "
            "devient trop lourde."
        ),
        "duplicate_rule.no_description.message": "La duplicate rule ne fournit pas de description.",
        "duplicate_rule.sharing.message": "La duplicate rule applique les regles de partage (Sharing Rules).",
        "duplicate_rule.sharing.detail": (
            "Cela peut limiter la detection de doublons si l'utilisateur n'a pas "
            "acces aux enregistrements existants."
        ),
        # ---------------------------------------------------------- Omni
        "omni.no_description.message": "Data Transform sans description metadata.",
        "omni.disabled_items.message": "{count} item(s) desactive(s) subsistent dans la definition.",
        "omni.disabled_items.detail": "Exemples : {sample}",
        "omni.size.message": "Data Transform volumineux : {count} items (seuil recommande : 40).",
        # ---------------------------------------------------------- Security
        "security.modify_all_data.message": "Le profil '{name}' dispose de la permission ModifyAllData.",
        "security.manage_users.message": "Le profil '{name}' dispose de la permission ManageUsers.",
        "security.modify_all_records.message": (
            "Le profil '{name}' a ModifyAllRecords sur {count} objet(s) : {objects}."
        ),
        "security.modify_all_records.more": " (+ {count} autres)",
        "security.permission_set_modify_all_records.message": (
            "Le Permission Set '{name}' a ModifyAllRecords sur {objects}."
        ),
        "security.profile_ratio.message": (
            "Ratio profils custom / Permission Sets = {ratio}% ({profiles} profils "
            "custom, {permission_sets} Permission Sets). Seuil recommande : < {threshold}%."
        ),
        # ---------------------------------------------------------- Agents / prompts
        "agent.no_description.message": "L'agent ne dispose d'aucune description.",
        "prompt.no_description.message": "Le prompt template ne dispose d'aucune description.",
    },
    "en": {
        # ---------------------------------------------------------- Apex classes
        "apex.sharing.message": (
            "No 'with sharing' / 'without sharing' / 'inherited sharing' "
            "declaration detected."
        ),
        "apex.sharing.detail": (
            "By default the class inherits the calling context, which can bypass "
            "sharing rules."
        ),
        "apex.hardcoded_id.message": "{count} hardcoded Salesforce ID(s) detected.",
        "apex.hardcoded_id.detail": "Examples: {sample}",
        "apex.soql_injection.message": "SOQL injection risk detected in a dynamic query.",
        "apex.soql_injection.detail": (
            "Using Database.query() with concatenated variables that are not "
            "escaped is risky."
        ),
        "apex.crud_fls.message": "No explicit CRUD/FLS enforcement detected.",
        "apex.crud_fls.detail": (
            "The class performs data operations without using WITH USER_MODE, "
            "Security.stripInaccessible() or WITH SECURITY_ENFORCED."
        ),
        "apex.no_try_catch.message": "Data access without exception handling (no try/catch block).",
        "apex.soql_dml_counts.detail": "SOQL = {soql}, DML = {dml}.",
        "apex.soql_in_loop.message": "A SOQL query potentially appears inside a loop.",
        "apex.dml_in_loop.message": "A DML statement potentially appears inside a loop.",
        "apex.callout_in_loop.message": (
            "An HTTP callout (Http/HttpRequest) potentially appears inside a loop."
        ),
        "apex.recursion.message": (
            "{count} method(s) call themselves with no visible guard to stop the "
            "recursion."
        ),
        "apex.recursion.detail_methods": "Method(s) involved: {sample}.",
        "apex.recursion.detail_more": "+ {count} more self-calling method(s).",
        "apex.recursion.detail_no_guard": (
            "No obvious reentrancy guard (Set<Id>/static flag) read inside the method."
        ),
        "apex.class_length.message": (
            "Class of {lines} code lines excluding comments (recommended threshold: 500)."
        ),
        "apex.class_length.detail": (
            "{code} code lines out of {total} file lines "
            "(comments and blank lines excluded)."
        ),
        "apex.comment_density.message": "Comment density = {ratio} (recommended >= 5%).",
        "apex.comment_density.detail": "{commented} commented lines out of {total}.",
        "apex.system_debug.message": "{count} 'System.debug' calls present in the class.",
        # ---------------------------------------------------------- Apex triggers
        "trigger.business_logic.message": (
            "The trigger carries business logic (substantial code or data operations)."
        ),
        "trigger.business_logic.detail_lines": "Lines of code detected: {count}.",
        "trigger.after_save_recursion.message": (
            "The trigger updates its own triggering records in an after-save "
            "context: infinite loop risk."
        ),
        "trigger.after_save_recursion.detail_events": "Declared events: {events}.",
        "trigger.after_save_recursion.detail_operation": "Detected operation: {operation}.",
        "trigger.after_save_recursion.detail_no_guard": (
            "No reentrancy guard (static Set<Id> / TriggerHandler class) found in "
            "the trigger."
        ),
        "trigger.data_ops_in_loop.message": "Data operations potentially inside a loop: {parts}.",
        "trigger.part.soql_in_loop": "SOQL inside a loop",
        "trigger.part.dml_in_loop": "DML inside a loop",
        # ---------------------------------------------------------- Apex call graph
        "apex.cycle.message": "Class involved in a call cycle with {others}.",
        "apex.cycle.self": "itself",
        "apex.cycle.detail_classes": "Classes taking part in the cycle: {classes}.",
        "apex.cycle.detail_chain": "Simplified chain: {chain}.",
        # ---------------------------------------------------------- Flows
        "flow.no_description.message": "The flow carries no global description.",
        "flow.described_ratio.message": "Only {ratio} of the flow elements carry a description.",
        "flow.described_ratio.detail": "{described}/{total} documented elements.",
        "flow.size.message": "Flow with {count} elements (recommended threshold: 40).",
        "flow.decisions.message": "{count} decisions detected in the flow (recommended threshold: 8).",
        "flow.data_ops.message": "{count} data operations (create/update/delete/lookup) detected.",
        "flow.data_ops.detail": (
            "Lookups = {lookups}, Creates = {creates}, Updates = {updates}, Deletes = {deletes}."
        ),
        "flow.soql_in_loop.message": "A read operation (Get Records) appears inside a loop.",
        "flow.dml_in_loop.message": "A write operation (Create/Update/Delete) appears inside a loop.",
        "flow.api_in_loop.message": (
            "An External Service action call potentially appears inside a loop."
        ),
        "flow.api_in_loop.detail": "Action(s) involved: {actions}.",
        "flow.api_in_loop.unknown_action": "unidentified action",
        "flow.fault_path.message": (
            "{unprotected} of {total} element(s) that can fail do not declare a "
            "fault path."
        ),
        "flow.fault_path.detail": "{kind} '{name}': no fault path.",
        "flow.fault_path.detail_more": "... and {count} more unprotected element(s).",
        "flow.depth.message": "Maximum depth = {depth} (recommended threshold: 4).",
        "flow.status.message": "The flow status is '{status}'.",
        "flow.status.unknown": "Not set",
        # ---------------------------------------------------------- LWC / Aura
        "lwc.js_size.message": "Large JS component ({lines} lines).",
        "lwc.js_size.detail": (
            "Consider splitting it into sub-components or using service modules."
        ),
        "lwc.html_size.message": "Large HTML template ({lines} lines).",
        "lwc.aura_enabled.message": "The component uses @AuraEnabled to call Apex.",
        "lwc.aura_enabled.detail": (
            "Check that the Apex classes being called enforce the security rules "
            "(CRUD/FLS)."
        ),
        "lwc.console.message": "console.log or console.error found.",
        "lwc.metadata.message": "Missing label or description in the metadata.",
        "aura.size.message": "Large Aura component.",
        "aura.size.detail_lines": "CMP: {cmp_lines} lines, JS: {js_lines} lines.",
        "aura.size.detail_migrate": (
            "Consider migrating to LWC for better performance and maintainability."
        ),
        # ---------------------------------------------------------- Objects
        "object.no_description.message": "Custom object without a metadata description.",
        "object.too_many_fields.message": "{count} custom fields on the object (recommended threshold: 50).",
        "object.too_many_validation_rules.message": (
            "{count} active validation rules on the object (recommended threshold: 10)."
        ),
        "object.too_many_record_types.message": "{count} active record types (recommended threshold: 3).",
        "field.no_description.message": "{count} custom field(s) without a description.",
        "field.no_description.detail": "Fields involved: {preview}.",
        "validation_rule.no_description.message": "The validation rule provides no description.",
        "validation_rule.complexity.message": "Complex formula (score={score}).",
        "validation_rule.complexity.detail_length": "Length: {length} characters.",
        "validation_rule.complexity.detail_advice": (
            "Consider simplifying it, or moving to Apex if the logic becomes too heavy."
        ),
        "duplicate_rule.no_description.message": "The duplicate rule provides no description.",
        "duplicate_rule.sharing.message": "The duplicate rule enforces sharing rules.",
        "duplicate_rule.sharing.detail": (
            "This can limit duplicate detection if the user cannot access the "
            "existing records."
        ),
        # ---------------------------------------------------------- Omni
        "omni.no_description.message": "Data Transform without a metadata description.",
        "omni.disabled_items.message": "{count} disabled item(s) remain in the definition.",
        "omni.disabled_items.detail": "Examples: {sample}",
        "omni.size.message": "Large Data Transform: {count} items (recommended threshold: 40).",
        # ---------------------------------------------------------- Security
        "security.modify_all_data.message": "Profile '{name}' has the ModifyAllData permission.",
        "security.manage_users.message": "Profile '{name}' has the ManageUsers permission.",
        "security.modify_all_records.message": (
            "Profile '{name}' has ModifyAllRecords on {count} object(s): {objects}."
        ),
        "security.modify_all_records.more": " (+ {count} more)",
        "security.permission_set_modify_all_records.message": (
            "Permission Set '{name}' has ModifyAllRecords on {objects}."
        ),
        "security.profile_ratio.message": (
            "Custom profiles / Permission Sets ratio = {ratio}% ({profiles} custom "
            "profiles, {permission_sets} Permission Sets). Recommended threshold: "
            "< {threshold}%."
        ),
        # ---------------------------------------------------------- Agents / prompts
        "agent.no_description.message": "The agent has no description.",
        "prompt.no_description.message": "The prompt template has no description.",
    },
}


def normalize_language(language: str | None) -> str:
    """Return a supported language code, falling back to French."""
    if language and language.lower() in SUPPORTED_LANGUAGES:
        return language.lower()
    return DEFAULT_LANGUAGE


def translate(language: str | None, key: str, **params: object) -> str:
    """Return the ``key`` message in ``language``.

    Falls back to the French catalogue when a key is missing from a
    translation, then to the key itself so a missing entry stays visible
    instead of raising at report generation time.
    """
    catalogue = MESSAGES.get(normalize_language(language), MESSAGES[DEFAULT_LANGUAGE])
    template = catalogue.get(key) or MESSAGES[DEFAULT_LANGUAGE].get(key)
    if template is None:
        return key
    if not params:
        return template
    try:
        return template.format(**params)
    except (KeyError, IndexError):
        return template
