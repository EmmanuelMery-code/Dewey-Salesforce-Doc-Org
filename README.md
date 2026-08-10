# Dewey : Doc Org - Salesforce

> 🇫🇷 Documentation bilingue Français / 🇬🇧 Bilingual English documentation — see [English version below](#-english).

Dewey propose **trois façons** d'analyser et documenter une org Salesforce / Dewey offers **three ways** to analyze and document a Salesforce org:

| Mode | Déclenchement / Trigger | Interface | Sortie / Output |
|---|---|---|---|
| **A — Application Windows** | `python app.py` | `Tkinter` (desktop) | HTML / Excel / Word en local |
| **B — Skill Claude Code** | `/assess-org` (`assess.py`) | Headless (sans UI) | Findings stockés dans Salesforce (Custom Objects) + résumé terminal |
| **Silent — Module `dewey.py`** | `from silent.dewey import Dewey` | Aucune (librairie Python) | Objet Python / export JSON / CSV |

---

## 🇫🇷 Français

### Vue d'ensemble

- **Mode A** : l'application Windows historique (interface `Tkinter`), pour un usage interactif poste par poste.
- **Mode B** : une extension headless (sans interface), pensée pour être pilotée par le skill Claude Code `/assess-org`. La configuration (règles, seuils, exclusions) et les résultats (scores, findings) sont stockés dans des objets custom Salesforce plutôt que dans des fichiers locaux. Voir `CLAUDE.md` et `PLAN.md` pour l'architecture complète.
- **Module silent (`silent/dewey.py`)** : une troisième façon d'utiliser Dewey, comme une simple librairie Python (classe `Dewey`) intégrable dans n'importe quel script, sans générer de rapports HTML/Excel/Word par défaut. Voir `silent/README.md` pour le manuel technique complet.

Ces trois modes partagent le même cœur d'analyse (`src/analyzer/`, `src/parsers/`, `src/core/`) : les règles métier, les scores de complexité et la posture "Adopt vs Adapt" sont calculés de la même manière quel que soit le mode utilisé.

### Mode A — Application Windows (Tkinter)

Application Python avec interface `Tkinter` pour :
- se connecter a une org Salesforce via Salesforce CLI
- lister les orgs disponibles
- generer un manifest
- lancer un retrieve
- generer une documentation HTML et Excel a partir d'un retrieve Salesforce

#### Prerequis

- Windows
- Python 3.12 ou plus recent recommande
- Salesforce CLI (`sf`) installe et accessible

#### Installation

1. Creer un environnement virtuel :

```bash
python -m venv .venv
```

2. Activer l'environnement virtuel :

```bash
.venv\Scripts\activate
```

3. Installer les dependances Python :

```bash
pip install -r requirements.txt
```

#### Lancement

```bash
python app.py
```

#### Ligne de commande (automatisation)

L'application accepte trois arguments nommes optionnels, utiles pour l'automatiser (tache planifiee, script) sans interaction manuelle :

```bash
python app.py --configuration "C:\chemin\vers\app_settings.json" --action all --silent
```

- `--configuration <chemin>` : fichier `app_settings.json` a utiliser a la place de celui du repertoire de l'application (cree automatiquement s'il n'existe pas).
- `--action {manifest|retrieve|documentation|all}` : declenche au demarrage l'etape demandee pour la derniere org utilisee (champ `alias` du fichier de configuration). `all` enchaine les trois etapes et s'arrete des qu'une echoue.
- `--silent` : execute l'action sans jamais afficher la fenetre (mode automatisation) ; sans effet si `--action` n'est pas fourni. Le processus se termine avec un code de sortie (`0` = succes, different de `0` = echec).

Sans argument, l'application demarre normalement, comme decrit ci-dessus. Voir le chapitre 14 de `MANUEL_UTILISATEUR.rtf` pour le detail complet.

#### Fonctions principales

- Connexion web Salesforce avec alias
- Choix d'environnement `Production` / `Sandbox` / `Custom`
- Choix du fichier de regles d'analyse (`src/analyzer/rules.xml` par defaut)
- Memorisation de la langue de l'interface (`Francais` ou `English`)
- Ouverture rapide des dossiers source et sortie dans l'explorateur Windows
- Pipeline complet :
  - generation du manifest
  - retrieve
  - generation de la documentation
- Assistant IA (Claude, Gemini ou Gateway) pour discuter de l'org documentee

#### Sorties generees

Dans le dossier de sortie, l'application genere notamment :

- `excel/permission_sets.xlsx`
- `excel/profiles.xlsx`
- `html/objects/*.html`
- `html/apex/*.html`
- `html/flows/*.html`
- `html/index.html`
- `word/data_dictionary.docx`
- `word/summary.docx`

#### Notes

- `Tkinter` fait partie de la bibliotheque standard Python sur Windows.
- Les preferences de l'application sont stockees dans `app_settings.json`.

### Mode B — Skill Claude Code `/assess-org` (headless)

Extension headless du même moteur d'analyse, sans application desktop, pilotée par le skill Claude Code `/assess-org`.

- **Point d'entrée** : `assess.py`
- **Configuration** : chargée par SOQL depuis les Custom Objects Salesforce `DeweyRule__c`, `DeweyConfig__c`, `DeweyExclusion__c` (avec fallback sur `src/analyzer/rules.xml` si l'org est indisponible)
- **Analyse** : `src/core/orchestrator_headless.py` orchestre les mêmes analyseurs que le Mode A (`src/analyzer/`), sans callbacks UI
- **Résultats** : poussés dans `OrgAnalysis__c`, `Finding__c` et `AnalysisDelta__c` (delta calculé par rapport à la dernière analyse pour la même org)
- **Couverture de tests (optionnel)** : avec `--coverage`, la couverture Apex + Flows est récupérée via `SalesforceCliService.fetch_test_coverage` (partagé avec le Mode A et le module `silent/dewey.py`) et exposée sur `DeweyAnalysis__c.TestCoveragePct__c` (+ `CoverageDelta__c` vs l'analyse précédente)
- **Paramètres du skill** :

```
/assess-org
  --org        alias SF CLI cible (défaut : ag2rPoc)
  --source     chemin local OU URL GitHub
  --branch     branche GitHub (défaut : main)
  --scope      all | apex | flows | security | omni (défaut : all)
  --coverage   récupère la couverture de tests Apex + Flows via le CLI Salesforce
               (Tooling API) et l'ajoute à l'analyse (nécessite un org connecté)
  --run-tests  lance les tests Apex locaux avant de récupérer la couverture
               (utilisé uniquement avec --coverage)
```

- **Sortie** : résumé terminal (score global, top 5 findings critiques, delta vs analyse précédente) + package Salesforce dédié `dewey-sf-assessment` (objets, permission set, reports, dashboards)

Pour le détail complet du modèle de données Salesforce et du workflow, voir `CLAUDE.md` et `PLAN.md`.

### Module silent — `silent/dewey.py`

`silent/dewey.py` expose une classe `Dewey` utilisable comme une **librairie Python autonome**, sans passer par l'application Windows ni par le skill Claude Code. Elle est conçue pour un fonctionnement silencieux : par défaut, aucun rapport HTML/Excel/Word n'est généré, seules les données sont calculées et exposées en mémoire (ou exportées en JSON/CSV).

```python
from silent.dewey import Dewey

config = {
    "source_dir": "chemin/vers/metadata",
    "alias": "MonProjet",
}

dewey = Dewey(config, verbosity="steps", use_history=True)

# Scoring, description des composants, findings, IA, couverture des flows...
print(dewey.chiffres["index"]["Scoring"]["score"])

# Export
dewey.export(format="json", path="export.json")
dewey.export(format="csv", path="export.csv")
```

- Configuration interne : `silent/dewey.json` (valeurs par défaut + correspondance de clés avec `app_settings.json`)
- Historique et comparaisons via `history.db`, avec l'`alias` comme clé de regroupement
- Niveaux de verbosité : `silent` (aucun log), `steps` (grandes étapes), `details` (détail technique)

Pour le manuel technique complet (dépendances, configuration, accès aux données, comparaisons, couverture de tests par Flow), voir `silent/README.md`.

---

## 🇬🇧 English

### Overview

- **Mode A**: the original Windows desktop application (`Tkinter` UI), for interactive, workstation-based usage.
- **Mode B**: a headless extension (no UI), designed to be driven by the Claude Code skill `/assess-org`. Configuration (rules, thresholds, exclusions) and results (scores, findings) are stored in Salesforce Custom Objects instead of local files. See `CLAUDE.md` and `PLAN.md` for the full architecture reference.
- **Silent module (`silent/dewey.py`)**: a third way to use Dewey, as a plain Python library (`Dewey` class) that can be embedded in any script, without generating HTML/Excel/Word reports by default. See `silent/README.md` for the complete technical manual.

All three modes share the same analysis core (`src/analyzer/`, `src/parsers/`, `src/core/`): business rules, complexity scores and the "Adopt vs Adapt" posture are computed the same way regardless of the mode used.

### Mode A — Windows desktop application (Tkinter)

Python application with a `Tkinter` UI to:
- connect to a Salesforce org through the Salesforce CLI
- list available orgs
- generate a manifest
- run a retrieve
- generate HTML and Excel documentation from a Salesforce retrieve

#### Prerequisites

- Windows
- Python 3.12 or later recommended
- Salesforce CLI (`sf`) installed and accessible

#### Installation

1. Create a virtual environment:

```bash
python -m venv .venv
```

2. Activate the virtual environment:

```bash
.venv\Scripts\activate
```

3. Install Python dependencies:

```bash
pip install -r requirements.txt
```

#### Launch

```bash
python app.py
```

#### Command line (automation)

The application accepts three optional named arguments, useful to automate it (scheduled task, script) without manual interaction:

```bash
python app.py --configuration "C:\path\to\app_settings.json" --action all --silent
```

- `--configuration <path>`: `app_settings.json` file to use instead of the one in the application directory (automatically created if it does not exist yet).
- `--action {manifest|retrieve|documentation|all}`: triggers the requested step at startup for the last used org (the `alias` field of the configuration file). `all` chains the three steps and stops as soon as one fails.
- `--silent`: runs the action without ever showing the window (automation mode); has no effect if `--action` is not supplied. The process exits with a return code (`0` = success, non-zero = failure).

Without any argument, the application starts normally, as described above. See chapter 14 of `USER_MANUAL.rtf` for the full detail.

#### Main features

- Salesforce web login with alias
- Environment selection `Production` / `Sandbox` / `Custom`
- Choice of analysis ruleset file (`src/analyzer/rules.xml` by default)
- UI language memorized (`French` or `English`)
- Quick access to source and output folders from Windows Explorer
- Full pipeline:
  - manifest generation
  - retrieve
  - documentation generation
- AI assistant (Claude, Gemini or Gateway) to chat about the documented org

#### Generated outputs

In the output folder, the application notably generates:

- `excel/permission_sets.xlsx`
- `excel/profiles.xlsx`
- `html/objects/*.html`
- `html/apex/*.html`
- `html/flows/*.html`
- `html/index.html`
- `word/data_dictionary.docx`
- `word/summary.docx`

#### Notes

- `Tkinter` is part of the Python standard library on Windows.
- Application preferences are stored in `app_settings.json`.

### Mode B — Claude Code skill `/assess-org` (headless)

A headless extension of the same analysis engine, with no desktop application, driven by the Claude Code skill `/assess-org`.

- **Entry point**: `assess.py`
- **Configuration**: loaded via SOQL from the Salesforce Custom Objects `DeweyRule__c`, `DeweyConfig__c`, `DeweyExclusion__c` (falls back to `src/analyzer/rules.xml` if the org is unavailable)
- **Analysis**: `src/core/orchestrator_headless.py` orchestrates the same analyzers as Mode A (`src/analyzer/`), without any UI callbacks
- **Results**: pushed to `OrgAnalysis__c`, `Finding__c` and `AnalysisDelta__c` (delta computed against the last analysis for the same org)
- **Test coverage (optional)**: with `--coverage`, Apex + Flow coverage is fetched via `SalesforceCliService.fetch_test_coverage` (shared with Mode A and the `silent/dewey.py` module) and exposed on `DeweyAnalysis__c.TestCoveragePct__c` (+ `CoverageDelta__c` vs the previous analysis)
- **Skill parameters**:

```
/assess-org
  --org        target SF CLI alias (default: ag2rPoc)
  --source     local path OR GitHub URL
  --branch     GitHub branch (default: main)
  --scope      all | apex | flows | security | omni (default: all)
  --coverage   fetch Apex + Flow test coverage via the Salesforce CLI (Tooling
               API) and add it to the assessment (requires a connected org)
  --run-tests  run local Apex tests before fetching coverage (only used
               together with --coverage)
```

- **Output**: terminal summary (global score, top 5 critical findings, delta vs previous analysis) + a dedicated Salesforce package `dewey-sf-assessment` (objects, permission set, reports, dashboards)

See `CLAUDE.md` and `PLAN.md` for the full Salesforce data model and workflow reference.

### Silent module — `silent/dewey.py`

`silent/dewey.py` exposes a `Dewey` class usable as a **standalone Python library**, without going through the Windows application or the Claude Code skill. It is designed to run silently: by default no HTML/Excel/Word report is generated, only data is computed and exposed in memory (or exported to JSON/CSV).

```python
from silent.dewey import Dewey

config = {
    "source_dir": "path/to/metadata",
    "alias": "MyProject",
}

dewey = Dewey(config, verbosity="steps", use_history=True)

# Scoring, component description, findings, AI usage, flow coverage...
print(dewey.chiffres["index"]["Scoring"]["score"])

# Export
dewey.export(format="json", path="export.json")
dewey.export(format="csv", path="export.csv")
```

- Internal configuration: `silent/dewey.json` (defaults + key mapping with `app_settings.json`)
- History and comparisons via `history.db`, keyed by `alias`
- Verbosity levels: `silent` (no logs), `steps` (major steps), `details` (technical detail)

See `silent/README.md` for the complete technical manual (dependencies, configuration, data access, comparisons, per-Flow test coverage).
