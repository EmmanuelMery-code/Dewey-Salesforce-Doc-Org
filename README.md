# Dewey — Salesforce Org Assessment

Outil d'analyse et de documentation d'orgs Salesforce. Deux modes coexistent dans le même dépôt.

---

## Modes

| Mode | Déclenchement | Config | Sortie |
|---|---|---|---|
| **A — Application desktop** | `python app.py` (Windows / Tkinter) | `app_settings.json` local | HTML, Excel, Word |
| **B — Assessment headless** | `python sf.py --org <alias> --source <path>` | Custom Objects SF (DeweyRule__c, DeweyConfig__c) | Findings dans l'org SF + résumé terminal |

---

## Mode A — Application desktop (Windows)

Interface graphique Tkinter pour documenter une org Salesforce.

### Prérequis

- Windows
- Python 3.12+
- Salesforce CLI (`sf`) installé et accessible

### Installation

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### Lancement

```bash
python app.py
```

### Fonctions principales

- Connexion à une org Salesforce via SF CLI (alias)
- Choix du fichier de règles (`src/analyzer/rules.xml` par défaut)
- Pipeline complet : génération du manifest → retrieve → documentation
- Sorties : `html/`, `excel/`, `word/` (permission sets, profils, objets, Apex, Flows, dictionnaire de données)

---

## Mode B — Assessment headless

Analyse un projet DX Salesforce (local ou GitHub) et pousse les résultats (findings, scores, delta) dans des Custom Objects d'une org cible. Conçu pour s'intégrer dans des pipelines CI/CD ou être lancé manuellement.

### Prérequis

- Python 3.12+
- Salesforce CLI (`sf`) installé, org cible authentifiée
- Package `dewey-orgSF` déployé sur l'org cible (voir `Mode Org Salesforce/dewey-orgSF/`)

### Lancement

```bash
# Analyse d'un projet DX local
python sf.py --org ag2rPoc --source ./mon-projet-dx

# Analyse d'un dépôt GitHub (branche spécifique)
python sf.py --org ag2rPoc --source https://github.com/org/repo --branch develop

# Périmètre réduit (apex | flows | security | omni | all)
python sf.py --org ag2rPoc --source ./mon-projet-dx --scope apex
```

### Pipeline d'exécution

```
1. Chargement config   → DeweyRule__c + DeweyConfig__c + DeweyExclusion__c (SOQL)
2. Analyse             → parsers + analyzers sur les sources DX
3. Push Salesforce     → DeweyAnalysis__c + DeweyFinding__c (batches 200) + DeweyDelta__c
4. Résumé terminal     → score global, top 5 critiques, delta vs analyse précédente
```

### Sortie terminal

```
[1/4] Loading config from org: ag2rPoc
      49 rules enabled, 0 exclusion(s) active
[2/4] Analysing: /chemin/vers/projet
      2974 finding(s) — Critical: 281, Major: 1129, Minor: 1334, Info: 230
[3/4] Pushing results to org: ag2rPoc
      DeweyAnalysis__c: a7Sbd00000016kvEAA
[4/4] Done.

────────────────────────────────────────────────────────────────
  Dewey — assessment complete
  DeweyAnalysis__c : a7Sbd00000016kvEAA
  Score global   : 16601
  Critical       : 281  |  Major : 1129  |  Minor : 1334  |  Info : 230
  Top critical findings :
    1. [APEX-SEC-001] MonClasse — Aucune déclaration 'with sharing' ...
────────────────────────────────────────────────────────────────
```

---

## Architecture Mode B

```
sf.py                                ← Point d'entrée Mode B
src/
├── core/
│   ├── sf_config_service.py         ← Charge règles/config/exclusions via SOQL
│   ├── sf_findings_service.py       ← Pousse OrgAnalysis + Findings + Delta via REST
│   ├── orchestrator_headless.py     ← Encapsule engine.py sans callbacks UI
│   ├── pmd_import_service.py        ← Import ruleset PMD XML → DeweyRule.csv
│   └── models.py                    ← Dataclasses partagés
├── parsers/salesforce_parser.py     ← Parsing XML DX
└── analyzer/
    ├── engine.py                    ← Orchestrateur d'analyse
    ├── apex_analyzer.py
    ├── flow_analyzer.py
    ├── lwc_analyzer.py
    ├── security_analyzer.py
    └── rules.xml                    ← Règles de fallback (si SF indisponible)

Mode Org Salesforce/dewey-orgSF/     ← Package Salesforce Unlocked
seed/
├── DeweyRule.csv                    ← Données de règles à charger après premier déploiement
└── DeweyConfig.csv                  ← Seuils et pondérations

tests/                               ← Tests unitaires (pytest)
```

---

## Tests unitaires

```bash
pytest tests/ -v
```

Couverture : `SfConfigService`, `HeadlessOrchestrator`, `SfFindingsService` (51 tests).

---

## Import de règles PMD

Pour alimenter `DeweyRule__c` depuis un ruleset PMD existant :

```bash
python src/core/pmd_import_service.py --ruleset path/to/ruleset.xml
sf data import tree --files seed/DeweyRule_pmd.csv -o ag2rPoc
```

---

## Notes

- Mode A et Mode B coexistent sans conflit. `app.py` et `sf.py` sont des points d'entrée indépendants.
- Les fichiers sous `src/ui/`, `src/reporting/`, `src/ai/` et `src/core/history_service.py` sont Mode A uniquement — ne pas les référencer en Mode B.
- La précision des scores (`ScoreGlobal__c`, `ScoreAdopt__c`, `ScoreAdapt__c`) est une somme pondérée brute, non normalisée sur 100. Elle peut dépasser 10 000 sur de grandes orgs.
