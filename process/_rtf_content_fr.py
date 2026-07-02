"""French content for the Lucie usage guide RTF."""
from __future__ import annotations

from _rtf_helpers import (
    bullets,
    build_document,
    code_block,
    h1,
    h2,
    numbered,
    page_break,
    paragraph,
    placeholder,
    quote,
)


def french_document() -> str:
    parts: list[str] = []

    parts.append(h1("Dewey : Doc Org - Salesforce"))
    parts.append(h1("Guide d'utilisation pour Squads, Tech Leads et Design Review"))
    parts.append(
        paragraph(
            "Ce document explique pas \u00e0 pas comment les Squads, les Tech "
            "Leads et le Design Review s'appuient sur Lucie pour produire, "
            "partager et exploiter une documentation Salesforce de qualit\u00e9. "
            "Il met l'accent sur les b\u00e9n\u00e9fices apport\u00e9s par "
            "l'outil et sur l'aspect collaboratif au sein de l'\u00e9quipe."
        )
    )
    parts.append(page_break())

    # ---------- 1. Vue d'ensemble
    parts.append(h1("1. Vue d'ensemble"))
    parts.append(
        paragraph(
            "Lucie est un outil interne qui analyse une org Salesforce et "
            "produit en sortie : une documentation HTML compl\u00e8te (objets, "
            "Apex, Flows, OmniStudio, permissions), des classeurs Excel "
            "d\u00e9taill\u00e9s (data dictionary, profils, permission sets, "
            "inventaire, violations PMD) et deux documents Word (un "
            "dictionnaire de donn\u00e9es et un r\u00e9sum\u00e9 contenant des "
            "conseils pri\u00f4ris\u00e9s)."
        )
    )
    parts.append(paragraph("Trois publics utilisent Lucie :"))
    parts.append(
        bullets(
            [
                "Les Squads : pour explorer rapidement la m\u00e9tadonn\u00e9e, "
                "pr\u00e9parer une story ou v\u00e9rifier l'impact d'une "
                "livraison.",
                "Les Tech Leads : pour piloter la qualit\u00e9 technique, "
                "suivre l'\u00e9volution d'une org sprint apr\u00e8s sprint et "
                "alimenter les revues transverses.",
                "Le Design Review : pour disposer d'un support standardis\u00e9 "
                "permettant d'arbitrer et de pri\u00f4riser les actions \u00e0 "
                "mener.",
            ]
        )
    )
    parts.append(
        paragraph(
            "La documentation produite est centralis\u00e9e dans un "
            "r\u00e9pertoire commun afin que tout le monde travaille sur la "
            "m\u00eame base de connaissances."
        )
    )

    # ---------- 2. Avantages cl\u00e9s
    parts.append(h1("2. Avantages cl\u00e9s"))
    parts.append(
        bullets(
            [
                "Documentation automatique standardis\u00e9e : plus besoin de "
                "maintenir manuellement le data dictionary, les pages "
                "Apex/Flow ou la liste des permission sets.",
                "Conseils pri\u00f4ris\u00e9s : le r\u00e9sum\u00e9 Word liste "
                "les actions \u00e0 mener, tri\u00e9es par s\u00e9v\u00e9rit\u00e9 "
                "puis par nombre d'occurrences. Les actions les plus "
                "impactantes apparaissent en premier.",
                "Score Adopt vs Adapt : un indicateur synth\u00e9tique "
                "permettant de comparer le niveau de personnalisation entre "
                "orgs ou dans le temps.",
                "D\u00e9tection d'anti-patterns : r\u00e8gles d'analyse "
                "statique inspir\u00e9es de PMD, du Salesforce "
                "Well-Architected Framework et des Architect Decision Guides.",
                "Multilingue : g\u00e9n\u00e9ration en fran\u00e7ais ou en "
                "anglais selon la langue de l'interface.",
                "Assistant IA int\u00e9gr\u00e9 : possibilit\u00e9 de "
                "dialoguer avec Claude ou Gemini sur l'org analys\u00e9e.",
                "Collaboration native : configuration partageable (poids, "
                "r\u00e8gles, exclusions), r\u00e9pertoire de sortie commun, "
                "format adapt\u00e9 aux comptes rendus de r\u00e9union.",
            ]
        )
    )

    # ---------- 3. Pr\u00e9paration et configuration commune
    parts.append(h1("3. Pr\u00e9paration et configuration commune"))
    parts.append(
        paragraph(
            "Avant de distribuer Lucie aux Squads, le pilote technique met en "
            "place une configuration de r\u00e9f\u00e9rence partag\u00e9e."
        )
    )

    parts.append(h2("3.1 Installation"))
    parts.append(
        numbered(
            [
                "Cloner le d\u00e9p\u00f4t.",
                "Installer les d\u00e9pendances : pip install -r requirements.txt.",
                "(Optionnel) Installer Salesforce CLI (sf) et PMD pour les "
                "fonctions int\u00e9gr\u00e9es.",
                "Lancer l'application : python app.py.",
            ]
        )
    )

    parts.append(h2("3.2 Configuration partag\u00e9e"))
    parts.append(paragraph("Dans l'\u00e9cran de configuration, l'\u00e9quipe s'accorde sur :"))
    parts.append(
        bullets(
            [
                "Le dossier de sortie commun (chemin r\u00e9seau, OneDrive ou "
                "SharePoint partag\u00e9 par toutes les Squads).",
                "Le fichier d'exclusions (exclusion.xlsx) versionn\u00e9 et "
                "utilis\u00e9 par toutes les Squads pour homog\u00e9n\u00e9iser "
                "les r\u00e9sultats.",
                "Le ruleset PMD (optionnel), versionn\u00e9 dans le m\u00eame "
                "d\u00e9p\u00f4t.",
                "Les r\u00e8gles d'analyse statique (rules.xml) : valider la "
                "liste des r\u00e8gles activ\u00e9es via l'onglet "
                "\u00ab R\u00e8gles d'analyse \u00bb.",
                "Les poids de scoring et Adopt vs Adapt : standards, sinon les "
                "scores ne sont plus comparables d'une Squad \u00e0 l'autre.",
                "La langue de l'interface (FR ou EN) qui d\u00e9finit la "
                "langue des documents Word produits.",
                "Les options \u00ab G\u00e9n\u00e9rer le Data Dictionary "
                "Word \u00bb et \u00ab G\u00e9n\u00e9rer le r\u00e9sum\u00e9 "
                "Word \u00bb : coch\u00e9es par d\u00e9faut, \u00e0 laisser "
                "actives pour le partage avec le Design Review.",
                "Les cl\u00e9s API IA (Claude, Gemini) : individuelles, \u00e0 "
                "laisser dans la configuration personnelle de chaque "
                "utilisateur.",
            ]
        )
    )
    parts.append(
        quote(
            "Astuce : versionner exclusion.xlsx, rules.xml et le ruleset PMD "
            "dans un d\u00e9p\u00f4t Git commun garantit l'homog\u00e9n\u00e9it\u00e9 "
            "des analyses entre toutes les Squads."
        )
    )

    parts.append(page_break())

    # ---------- 4. Squads
    parts.append(h1("4. Mode op\u00e9ratoire pour les Squads"))
    parts.append(
        paragraph(
            "Chaque Squad utilise Lucie pour ses besoins du quotidien : "
            "exploration de l'org, pr\u00e9paration d'une story, audit avant "
            "livraison."
        )
    )

    parts.append(h2("4.1 Lancement classique"))
    parts.append(
        numbered(
            [
                "Ouvrir Dewey via la commande python app.py.",
                "S\u00e9lectionner le dossier source (r\u00e9sultat d'un "
                "retrieve Salesforce ou clone du repo de la Squad).",
                "S\u00e9lectionner le dossier de sortie commun, dans un "
                "sous-dossier propre \u00e0 la Squad et dat\u00e9 (ex. "
                "\\\\share\\dewey\\squad-alpha\\2026-04-25).",
                "Charger l'org Salesforce : via Web login + alias puis "
                "G\u00e9n\u00e9rer manifest et Faire retrieve, ou directement "
                "via le bouton Manifest + Retrieve + Doc qui encha\u00eene "
                "tout en une fois.",
                "Cliquer sur G\u00e9n\u00e9rer la documentation.",
                "Ouvrir l'index HTML et explorer la documentation g\u00e9n\u00e9r\u00e9e.",
            ]
        )
    )

    parts.append(h2("4.2 Cas d'usage recommand\u00e9s"))
    parts.append(
        bullets(
            [
                "Onboarding d'un nouvel arrivant : la documentation HTML "
                "offre une cartographie imm\u00e9diate de l'org (objets, "
                "flows, classes Apex, permissions).",
                "Pr\u00e9paration d'une story : ouvrir le data dictionary "
                "Word ou la page de l'objet impact\u00e9 pour identifier les "
                "champs, record types et r\u00e8gles d\u00e9j\u00e0 en place.",
                "Audit avant livraison : g\u00e9n\u00e9rer la doc avant la "
                "livraison et comparer le r\u00e9sum\u00e9 Word avec la "
                "g\u00e9n\u00e9ration pr\u00e9c\u00e9dente pour rep\u00e9rer "
                "les nouveaux findings.",
                "V\u00e9rification rapide : utiliser l'assistant IA (onglet "
                "Discussion) pour poser des questions sur l'org sans devoir "
                "naviguer dans le code.",
            ]
        )
    )

    parts.append(h2("4.3 Conseils Squad"))
    parts.append(
        bullets(
            [
                "Lancer la g\u00e9n\u00e9ration avant chaque sprint review "
                "pour disposer d'un point de r\u00e9f\u00e9rence stable.",
                "Stocker la documentation dans le r\u00e9pertoire commun : "
                "les autres Squads et le Design Review s'appuieront dessus.",
                "R\u00e9agir rapidement aux findings Critical et Major du "
                "r\u00e9sum\u00e9 Word ; ce sont eux qui remontent le plus "
                "vite en Design Review.",
            ]
        )
    )

    placeholder1 = (
        "[PLACEHOLDER DIAGRAMME 1 : Workflow Squad - "
        "ins\u00e9rer ici l'export PNG ou PDF du fichier "
        "squad_workflow.drawio.]"
    )
    parts.append(placeholder(placeholder1))

    parts.append(page_break())

    # ---------- 5. Tech Leads
    parts.append(h1("5. Mode op\u00e9ratoire pour les Tech Leads"))
    parts.append(
        paragraph(
            "Le Tech Lead pilote la qualit\u00e9 technique de sa Squad et "
            "alimente les revues transverses anim\u00e9es par le manager."
        )
    )

    parts.append(h2("5.1 Responsabilit\u00e9s outillage"))
    parts.append(
        bullets(
            [
                "Maintenir la configuration commune (r\u00e8gles d'analyse, "
                "fichier d'exclusions, poids de scoring).",
                "S'assurer que la Squad g\u00e9n\u00e8re la documentation au "
                "moins une fois par sprint.",
                "V\u00e9rifier les findings remont\u00e9s et organiser leur "
                "traitement avec la Squad.",
                "Remonter au manager les sujets qui d\u00e9passent le "
                "p\u00e9rim\u00e8tre de la Squad et m\u00e9ritent un Design "
                "Review.",
            ]
        )
    )

    parts.append(h2("5.2 Workflow type sur un sprint"))
    parts.append(
        numbered(
            [
                "En d\u00e9but de sprint : r\u00e9cup\u00e9rer la derni\u00e8re "
                "g\u00e9n\u00e9ration stock\u00e9e dans le r\u00e9pertoire "
                "commun pour servir de point de r\u00e9f\u00e9rence.",
                "Pendant le sprint : lancer une analyse interm\u00e9diaire "
                "lors d'une refonte importante (nouvel objet, refactor "
                "Apex, migration Flow).",
                "En fin de sprint : g\u00e9n\u00e9rer la documentation "
                "compl\u00e8te et l'archiver dans le r\u00e9pertoire commun "
                "(sous-dossier dat\u00e9).",
                "Pr\u00e9parer la r\u00e9tro / sprint review : extraire les "
                "3 \u00e0 5 actions les plus prioritaires du r\u00e9sum\u00e9 "
                "Word.",
                "Pr\u00e9parer le Design Review : faire remonter au manager "
                "les findings transverses et les sujets d'arbitrage.",
            ]
        )
    )

    parts.append(h2("5.3 Indicateurs \u00e0 suivre"))
    parts.append(
        bullets(
            [
                "\u00c9volution du score de personnalisation sprint apr\u00e8s "
                "sprint.",
                "\u00c9volution du score Adopt vs Adapt.",
                "Volume de findings par s\u00e9v\u00e9rit\u00e9 (Critical, "
                "Major, Minor, Info).",
                "Top 5 des r\u00e8gles d\u00e9clench\u00e9es, visible dans le "
                "chapitre Conseils du r\u00e9sum\u00e9 Word.",
                "Nombre d'objets et de champs documentaires r\u00e9ellement "
                "exploit\u00e9s (data dictionary).",
            ]
        )
    )

    parts.append(page_break())

    # ---------- 6. Design Review
    parts.append(h1("6. Utilisation en Design Review"))
    parts.append(
        paragraph(
            "Le Design Review combine les sorties produites par chaque Squad "
            "afin de prendre des d\u00e9cisions d'architecture coordonn\u00e9es. "
            "C'est le moment o\u00f9 le r\u00e9sum\u00e9 Word et son chapitre "
            "Conseils prennent toute leur valeur."
        )
    )

    parts.append(h2("6.1 Avant la r\u00e9union"))
    parts.append(
        numbered(
            [
                "Le manager (animateur du Design Review) rassemble dans le "
                "r\u00e9pertoire commun les summary.docx de chaque Squad, les "
                "data_dictionary.docx correspondants et l'index HTML pour "
                "les d\u00e9tails techniques.",
                "Lecture pr\u00e9liminaire du chapitre Conseils de chaque "
                "r\u00e9sum\u00e9.",
                "S\u00e9lection des actions \u00e0 d\u00e9battre, en priorit\u00e9 "
                "celles class\u00e9es Critical et Major.",
                "Pr\u00e9paration de l'ordre du jour \u00e0 partir de cette "
                "s\u00e9lection.",
            ]
        )
    )

    parts.append(h2("6.2 Pendant la r\u00e9union"))
    parts.append(
        numbered(
            [
                "Pr\u00e9senter le r\u00e9sum\u00e9 Word : page de garde, "
                "vue d'ensemble, m\u00e9triques de personnalisation, puis "
                "chapitre Conseils.",
                "Pour chaque action prioritaire, discuter du constat avec "
                "la Squad concern\u00e9e.",
                "D\u00e9cider l'action : corriger maintenant, exception "
                "document\u00e9e ou report avec deadline.",
                "D\u00e9signer la Squad responsable et le porteur de l'action.",
                "Si n\u00e9cessaire, ouvrir le data dictionary Word ou la "
                "documentation HTML pour v\u00e9rifier un d\u00e9tail technique.",
                "Capturer chaque d\u00e9cision dans le compte rendu en citant "
                "l'identifiant de la r\u00e8gle (par exemple APEX-SEC-001).",
            ]
        )
    )

    parts.append(h2("6.3 Apr\u00e8s la r\u00e9union"))
    parts.append(
        bullets(
            [
                "Stocker le compte rendu \u00e0 c\u00f4t\u00e9 de la "
                "documentation analys\u00e9e dans le r\u00e9pertoire commun.",
                "Le compte rendu fait r\u00e9f\u00e9rence aux findings du "
                "r\u00e9sum\u00e9 Word, ce qui rend les d\u00e9cisions "
                "rejouables.",
                "Au Design Review suivant, v\u00e9rifier la d\u00e9croissance "
                "du nombre d'occurrences pour chaque finding trait\u00e9 et "
                "f\u00e9liciter les Squads qui ont avanc\u00e9.",
            ]
        )
    )

    placeholder2 = (
        "[PLACEHOLDER DIAGRAMME 2 : Workflow Design Review - "
        "ins\u00e9rer ici l'export PNG ou PDF du fichier "
        "design_review_workflow.drawio.]"
    )
    parts.append(placeholder(placeholder2))

    parts.append(page_break())

    # ---------- 7. Aspect collaboratif
    parts.append(h1("7. Aspect collaboratif et r\u00e9pertoire commun"))
    parts.append(
        paragraph(
            "L'outil prend tout son sens lorsqu'il est partag\u00e9 et que "
            "tous les acteurs travaillent depuis le m\u00eame r\u00e9pertoire "
            "de r\u00e9f\u00e9rence."
        )
    )

    parts.append(h2("7.1 Arborescence type"))
    parts.append(
        code_block(
            [
                "\\\\share\\dewey\\",
                "+-- _config\\",
                "|   +-- exclusion.xlsx",
                "|   +-- rules.xml",
                "|   +-- pmd_ruleset.xml",
                "+-- squad-alpha\\",
                "|   +-- 2026-04-11\\",
                "|   |   +-- index.html",
                "|   |   +-- excel\\...",
                "|   |   +-- word\\data_dictionary.docx",
                "|   |   +-- word\\summary.docx",
                "|   +-- 2026-04-25\\",
                "+-- squad-beta\\",
                "+-- design-review\\",
                "    +-- 2026-04-15-CR.docx",
                "    +-- 2026-04-29-CR.docx",
            ]
        )
    )

    parts.append(h2("7.2 B\u00e9n\u00e9fices collaboratifs"))
    parts.append(
        bullets(
            [
                "Vision unique : tout le monde regarde les m\u00eames "
                "donn\u00e9es et les m\u00eames r\u00e8gles.",
                "Capitalisation : l'historique des g\u00e9n\u00e9rations sert "
                "de m\u00e9moire collective de l'org.",
                "Comparaison : les Tech Leads peuvent comparer leur Squad aux "
                "autres sur des bases \u00e9quivalentes.",
                "D\u00e9cision trac\u00e9e : le compte rendu de Design Review "
                "fait r\u00e9f\u00e9rence aux identifiants de r\u00e8gles, "
                "rendant les arbitrages rejouables.",
                "Communication facilit\u00e9e : les documents Word sont "
                "diffusables aux parties prenantes non techniques (Product "
                "Owners, Architectes, Sponsors).",
            ]
        )
    )

    placeholder3 = (
        "[PLACEHOLDER DIAGRAMME 3 : Vue collaborative - "
        "ins\u00e9rer ici l'export PNG ou PDF du fichier "
        "collaboration_overview.drawio.]"
    )
    parts.append(placeholder(placeholder3))

    parts.append(h1("8. Bonnes pratiques"))
    parts.append(
        bullets(
            [
                "Mettre \u00e0 jour la doc apr\u00e8s chaque \u00e9volution "
                "majeure (nouveau module, refonte d'objet, batch important).",
                "Versionner la configuration commune (exclusion.xlsx, "
                "rules.xml, pmd_ruleset.xml).",
                "Nommer les sous-r\u00e9pertoires de g\u00e9n\u00e9ration avec "
                "une date ISO YYYY-MM-DD pour faciliter le tri.",
                "Limiter l'usage du fichier d'exclusion : il doit refl\u00e9ter "
                "des choix d'architecture, pas masquer des probl\u00e8mes.",
                "Discuter en amont des poids de scoring : un score n'a de "
                "valeur que compar\u00e9 \u00e0 un r\u00e9f\u00e9rentiel "
                "partag\u00e9.",
                "Stocker le compte rendu de Design Review \u00e0 c\u00f4t\u00e9 "
                "de la documentation analys\u00e9e pour la tra\u00e7abilit\u00e9.",
                "Refaire un cycle complet (g\u00e9n\u00e9ration + Design "
                "Review + correction) au moins une fois par release.",
            ]
        )
    )

    parts.append(h1("9. Annexes - sch\u00e9mas associ\u00e9s"))
    parts.append(
        paragraph(
            "Trois diagrammes drawio sont fournis dans ce r\u00e9pertoire et "
            "sont \u00e0 ins\u00e9rer aux emplacements signal\u00e9s par les "
            "blocs PLACEHOLDER ci-dessus :"
        )
    )
    parts.append(
        bullets(
            [
                "squad_workflow.drawio : workflow d'une Squad sur un sprint.",
                "design_review_workflow.drawio : d\u00e9roul\u00e9 d'un Design "
                "Review.",
                "collaboration_overview.drawio : vue d'ensemble de la "
                "collaboration entre Squads, Tech Leads et Design Review.",
            ]
        )
    )
    parts.append(
        paragraph(
            "Pour les ouvrir : utilisez https://app.diagrams.net ou "
            "l'extension Visual Studio Code Draw.io Integration. Exportez "
            "ensuite en PNG ou PDF puis remplacez les blocs PLACEHOLDER de "
            "ce document par l'image correspondante."
        )
    )

    return build_document(parts)
