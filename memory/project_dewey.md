---
name: Dewey — Org Assessment Tool
description: Outil d'assessment Salesforce piloté par Claude Code — architecture, décisions, backlog
type: project
---

## Concept

Extension de Dewey (https://github.com/EmmanuelMery-code/Dewey-Salesforce-Doc-Org) en Mode B : pas d'application desktop, Claude Code lit directement le repo local ou GitHub, stocke les findings dans une SF Sandbox, sans modifier le code existant (extension uniquement).

**Why:** Dewey est un bon outil mais Windows-only avec une app Tkinter. La valeur réelle est dans les analyseurs et les règles, pas dans l'UI. En mode headless + SF storage, l'outil devient cross-platform, intégrable dans un workflow Claude Code, avec reporting SF natif.

**How to apply:** Référencer PLAN.md pour toutes les décisions d'architecture. Ne jamais modifier les fichiers Dewey existants — toujours étendre.

---

## Répertoire

`/Users/svaroteaux/Documents/Dev/AG2R/Dewey/`

---

## Décisions clés

- **Config** : Custom Objects (DeweyRule__c, DeweyConfig__c, DeweyExclusion__c) — pas CMDT. Flexibilité admin sans déploiement, exclusions changeantes.
- **Sandbox cible** : alias SF CLI `ag2rPoc`
- **Source distante** : git clone local temporaire avec sélection de branche
- **Déclenchement** : manuel via `/assess-org`
- **Scope V1** : complet (= périmètre Dewey) — Apex + Flows + LWC + OmniStudio + Security
- **Reports/Dashboards** : dans l'Unlocked Package `dewey-sf-assessment`
- **AG2R est sur Unlimited** — pas de contrainte de licence SF

---

## PMD Integration

Utility `pmd_import_service.py` pour importer un ruleset PMD XML vers DeweyRule__c via CSV.
La plupart des entreprises ont PMD dans leur pipeline CI/CD — ce pont évite de ressaisir les règles.

---

## Backlog futur (hors V1)

- **Top-of-top** : 5 métriques clés synthétiques en tête de résumé (à définir)
- **Loop périodique** : déclenchement automatique `/assess-org` sur schedule
- **CRM Analytics** : dataset + recettes pour analytics avancées
- **Multi-org** : comparer plusieurs orgs sur les mêmes règles
