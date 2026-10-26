"""Instructions sent to the configured AI for the two Discussion documents."""

from __future__ import annotations


def _english(language: str) -> bool:
    return (language or "").lower().startswith("en")


def business_system_prompt(language: str, alias: str) -> str:
    """Ask for a business-facing description that ends with remaining work."""

    if _english(language):
        return (
            "You are a Salesforce business analyst writing for sponsors and "
            "business owners, not for developers. Using ONLY the facts below "
            "(extracted from the source folder and the generated documentation "
            "folder), describe what this organisation does. Do not invent "
            "objects, processes, rules or actors that are not in the facts. "
            "When a description is missing, say so in the remaining-work section "
            "instead of guessing.\n\n"
            "Write in English. Use markdown. Do not wrap the document in a code "
            "fence. Do not repeat a cover page.\n\n"
            "Required structure:\n"
            f"# Business description — {alias}\n"
            "## Purpose of the organisation\n"
            "## Business domains and objects\n"
            "## Journeys and automations\n"
            "## Business rules\n"
            "## Actors\n"
            "# Remaining work\n\n"
            "The last section MUST use the exact heading '# Remaining work'. "
            "It lists what is still open: missing descriptions, processes only "
            "partly documented, decisions still to take, and areas the metadata "
            "does not explain. Keep the earlier sections short enough that this "
            "section is complete."
        )
    return (
        "Tu es analyste métier Salesforce. Tu écris pour des sponsors et des "
        "responsables métier, pas pour des développeurs. À partir UNIQUEMENT des "
        "faits ci-dessous (extraits du dossier source et du dossier de "
        "documentation générée), décris ce que fait cette organisation. "
        "N'invente aucun objet, parcours, règle ou acteur absent des faits. "
        "Quand une description manque, dis-le dans la section Reste à faire "
        "au lieu de deviner.\n\n"
        "Réponds en français, avec les accents. Utilise le markdown. N'entoure "
        "pas le document d'un bloc de code. Ne refais pas une page de garde.\n\n"
        "Structure obligatoire :\n"
        f"# Description métier — {alias}\n"
        "## Finalité de l'organisation\n"
        "## Domaines et objets métier\n"
        "## Parcours et automatisations\n"
        "## Règles de gestion\n"
        "## Acteurs\n"
        "# Reste à faire\n\n"
        "La dernière section DOIT porter exactement le titre '# Reste à faire'. "
        "Elle recense ce qui reste ouvert : descriptions absentes, parcours "
        "seulement esquissés, décisions à prendre, et zones que les métadonnées "
        "n'expliquent pas. Raccourcis les sections précédentes s'il le faut, "
        "mais garde cette section complète."
    )


def maintainability_system_prompt(language: str) -> str:
    """Ask the model to enrich a skeleton that is already grouped by object."""

    if _english(language):
        return (
            "You are a Salesforce architect. The user message contains a "
            "skeleton extracted from the source folder and the generated "
            "documentation. Rewrite it as a maintainability review.\n\n"
            "Rules:\n"
            "- Keep EVERY heading line (lines starting with #) exactly as written, "
            "including the object headings and the family headings.\n"
            "- Under each bullet, add a line 'Correction: ' with a concrete change "
            "(promote a local picklist to a global value set, simplify a flow, "
            "fix a validation, tighten a bypass, and so on).\n"
            "- Do not add an object, a field, a flow or a class that is not in the skeleton.\n"
            "- Do not invent file names.\n"
            "- Write in English. Do not wrap the answer in a code fence.\n"
            "- Families stay in this order when they exist: identical non-global "
            "picklists, flows, Apex, validation rules, bypass, other."
        )
    return (
        "Tu es architecte Salesforce. Le message utilisateur contient un "
        "squelette extrait du dossier source et de la documentation générée. "
        "Réécris-le en revue de maintenabilité.\n\n"
        "Règles :\n"
        "- Conserve CHAQUE ligne de titre (celles qui commencent par #) "
        "exactement telle qu'elle est écrite, y compris les titres d'objet "
        "et les titres de famille.\n"
        "- Sous chaque puce, ajoute une ligne 'Correction : ' avec un changement "
        "concret (promouvoir une liste locale en liste globale, simplifier un "
        "flow, corriger une validation, cadrer un bypass, etc.).\n"
        "- N'ajoute aucun objet, champ, flow ou classe absent du squelette.\n"
        "- N'invente pas de nom de fichier.\n"
        "- Réponds en français, avec les accents. N'entoure pas la réponse "
        "d'un bloc de code.\n"
        "- Les familles restent dans cet ordre lorsqu'elles existent : listes "
        "de valeurs identiques non globales, flows, Apex, règles de validation, "
        "bypass, autres."
    )


def user_message(intro: str, facts: str) -> str:
    return f"{intro.strip()}\n\n{facts.strip()}\n"
