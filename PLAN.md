# Dewey — Plan d'Architecture

> Outil d'assessment Salesforce piloté par Claude Code, sans application desktop.
> Référentiel GitHub source : https://github.com/EmmanuelMery-code/Dewey-Salesforce-Doc-Org

---

## Principe

Deux modes coexistent dans le même repo Python :

| Mode | Déclenchement | Config | Output |
|---|---|---|---|
| **A — Windows app** | `app.py` (Tkinter) | `app_settings.json` local | HTML / Excel / Word local |
| **B — Claude Code skill** | `/assess-org` | SF Sandbox (Custom Objects) | Findings dans SF + résumé terminal |

---

## Stratégie d'extension (pas de modification)

### Fichiers Python réutilisés sans modification

| Fichier | Rôle |
|---|---|
| `src/parsers/salesforce_parser.py` | Parsing XML SF DX |
| `src/analyzer/engine.py` | Orchestrateur analyse statique |
| `src/analyzer/apex_analyzer.py` + `flow_analyzer.py` + `lwc_analyzer.py` + `security_analyzer.py` | Analyseurs par type |
| `src/analyzer/rules.xml` | Référence rules → seed CSV (fallback si SF indisponible) |
| `src/core/models.py` | Dataclasses centrales partagées |
| `src/core/customization_metrics.py` | Scoring no/low/pro-code |
| `src/core/pmd_service.py` | Intégration PMD optionnelle |

### Fichiers conservés pour Mode A (non utilisés en Mode B)

`src/ui/`, `src/reporting/`, `src/ai/`, `src/core/history_service.py`, `app.py`

### Nouveaux fichiers (extension uniquement)

```
src/
├── core/
│   ├── sf_config_service.py      ← SOQL sur DeweyRule__c + DeweyConfig__c + DeweyExclusion__c
│   │                                Fallback sur rules.xml si SF indisponible
│   ├── sf_findings_service.py    ← Push OrgAnalysis__c + Finding__c + AnalysisDelta__c
│   └── orchestrator_headless.py  ← Wrapper orchestrator.py sans callbacks UI
assess.py                          ← Point d'entrée Mode B
```

---

## Modèle de données SF (Custom Objects)

### Objets de configuration

#### `DeweyRule__c`
| Champ | Type | Description |
|---|---|---|
| `RuleId__c` | Text(50) ExternalId | Ex : APEX-SEC-001 |
| `Name` | Text | Libellé |
| `Severity__c` | Picklist | Critical / Major / Minor / Info |
| `Category__c` | Picklist | Security / Performance / Quality / Architecture |
| `Subcategory__c` | Text | |
| `IsEnabled__c` | Checkbox | Activer/désactiver sans déploiement |
| `Source__c` | Text | PMD / Dewey / Custom |
| `PmdRuleRef__c` | Text | Référence règle PMD d'origine (pour import) |
| `Message__c` | Text Area | Message affiché dans le finding |
| `Remediation__c` | Long Text Area | Conseil de correction |
| `WellArchitectedRef__c` | URL | Lien Salesforce Well-Architected |

#### `DeweyConfig__c`
| Champ | Type | Description |
|---|---|---|
| `ConfigKey__c` | Text ExternalId | Ex : threshold_apex_complexity |
| `ConfigValue__c` | Text | Valeur (seuil, poids…) |
| `Description__c` | Text | |

#### `DeweyExclusion__c`
| Champ | Type | Description |
|---|---|---|
| `RuleId__c` | Text | Référence DeweyRule__c |
| `ComponentName__c` | Text | Nom exact du composant exclu |
| `Reason__c` | Text Area | Justification |
| `ExpiryDate__c` | Date | Optionnel : date d'expiration de l'exclusion |

### Objets de résultats

#### `OrgAnalysis__c`
| Champ | Type |
|---|---|
| `OrgAlias__c` | Text |
| `AnalysisDate__c` | DateTime |
| `SourcePath__c` | Text |
| `SourceBranch__c` | Text |
| `ScoreGlobal__c` | Number |
| `ScoreAdopt__c` | Number |
| `ScoreAdapt__c` | Number |
| `ApexCount__c` | Number |
| `FlowCount__c` | Number |
| `FindingCritical__c` | Number |
| `FindingMajor__c` | Number |
| `FindingMinor__c` | Number |
| `Status__c` | Picklist (Completed / Failed) |

#### `Finding__c`
| Champ | Type |
|---|---|
| `OrgAnalysis__c` | Lookup(OrgAnalysis__c) |
| `RuleId__c` | Text |
| `Severity__c` | Picklist |
| `ComponentType__c` | Picklist (Apex / Flow / LWC / Object / Security / OmniStudio…) |
| `ComponentName__c` | Text |
| `Message__c` | Text Area |
| `LineNumber__c` | Number |
| `IsNew__c` | Checkbox (delta vs analyse précédente) |
| `IsResolved__c` | Checkbox |
| `ResolvedDate__c` | Date |
| `AssignedTo__c` | Lookup(User) |

#### `AnalysisDelta__c`
| Champ | Type |
|---|---|
| `CurrentAnalysis__c` | Lookup(OrgAnalysis__c) |
| `PreviousAnalysis__c` | Lookup(OrgAnalysis__c) |
| `NewFindings__c` | Number |
| `ResolvedFindings__c` | Number |
| `ScoreDelta__c` | Number |

---

## Skill `/assess-org`

### Paramètres
```
/assess-org
  --org        alias SF CLI cible (défaut : ag2rPoc)
  --source     chemin local OU URL GitHub
  --branch     branche GitHub (défaut : main)
  --scope      all | apex | flows | security | omni (défaut : all)
```

### Workflow
```
1. Charger config depuis --org (SOQL DeweyRule__c, DeweyConfig__c, DeweyExclusion__c)
2. Si source distante :
   a. Proposer : clone local dans /tmp/dewey-[org]-[timestamp]/
   b. Demander confirmation branche (défaut : main)
   c. git clone --branch [branch] --depth 1 [url] [tmp_dir]
3. Lancer orchestrator_headless.py → parsers → analyzers
4. Récupérer dernière OrgAnalysis__c pour calculer le delta
5. Pousser OrgAnalysis__c + Finding__c + AnalysisDelta__c
6. Résumé terminal : score global, top 5 findings critiques, delta vs précédente analyse
7. Nettoyer le dossier temporaire si clone distant
```

---

## PMD Import Utility

Capacité à importer les règles PMD d'un pipeline existant vers DeweyRule__c :

```
src/core/pmd_import_service.py   ← Lit un ruleset PMD XML et génère le CSV DeweyRule.csv
```

Workflow :
1. Pointer vers le fichier `ruleset.xml` PMD du projet
2. Parser les règles `<rule ref="...">` avec leurs propriétés
3. Générer `seed/DeweyRule_pmd.csv`
4. `sf data import tree --files seed/DeweyRule_pmd.csv -o ag2rPoc`

---

## Unlocked Package `dewey-sf-assessment`

```
dewey-sf-package/
├── force-app/main/default/
│   ├── objects/
│   │   ├── DeweyRule__c/
│   │   ├── DeweyConfig__c/
│   │   ├── DeweyExclusion__c/
│   │   ├── OrgAnalysis__c/
│   │   ├── Finding__c/
│   │   └── AnalysisDelta__c/
│   ├── permissionsets/
│   │   └── Dewey_User.permissionset-meta.xml
│   ├── reports/         ← Findings par sévérité, tendance, top composants
│   └── dashboards/      ← Dashboard qualité org (basé sur Dewey existant)
└── sfdx-project.json
```

Data init :
```bash
sf data import tree --files seed/DeweyRule.csv -o ag2rPoc
sf data import tree --files seed/DeweyConfig.csv -o ag2rPoc
```

---

## Décisions arrêtées

| Décision | Choix | Raison |
|---|---|---|
| Config | Custom Objects | Flexibilité admin, exclusions changeantes, pas de deploy pour modifier |
| Source distante | git clone local temporaire | Accès complet aux fichiers, gestion de branche simple |
| Déclenchement | Manuel (`/assess-org`) | Loop à évaluer plus tard |
| Scope V1 | Complet (= périmètre Dewey) | Apex + Flows + LWC + OmniStudio + Security + Scoring |
| Reports/Dashboards | Dans le package | Templates SF natifs ; CRM Analytics = V2 |

---

## Backlog futur (hors V1)

- **Top-of-top** : scoring synthétique "5 métriques clés" affiché en tête de résumé — à définir avec l'équipe (ex. % Critical résolus, score Adopt, coverage, complexité moyenne)
- **Loop périodique** : déclenchement automatique `/assess-org` sur schedule (hebdo ?) avec diff automatique
- **CRM Analytics** : dataset + recettes pour analytics avancées sur les tendances de dette
- **Multi-org** : comparer plusieurs orgs (xRM vs pRM) sur les mêmes règles
