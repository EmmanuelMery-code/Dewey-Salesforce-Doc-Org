# dewey-orgSF — Package Salesforce

Package Salesforce Unlocked contenant le modèle de données, les permissions, les flows, les rapports et le dashboard de l'outil Dewey (Mode B).

---

## Déploiement initial

```bash
cd "Mode Org Salesforce/dewey-orgSF"

# 1. Déployer le package complet
sf project deploy start --source-dir force-app/ --ignore-conflicts -o <alias>

# 2. Charger les données de référence (règles et config)
sf data import tree --files ../../seed/DeweyRule.csv -o <alias>
sf data import tree --files ../../seed/DeweyConfig.csv -o <alias>
```

### Permission sets à affecter

| Permission Set | Profil cible |
|---|---|
| `Dewey_User` | Utilisateurs qui exécutent les analyses (`sf.py`) |
| `Dewey_Reader` | Architectes et parties prenantes qui consultent les résultats |

---

## Modèle de données

### Objets de configuration (lus au démarrage de l'analyse)

| Objet | Rôle | Clé externe |
|---|---|---|
| `DeweyRule__c` | Catalogue de règles (sévérité, catégorie, message, remédiation) | `RuleId__c` |
| `DeweyConfig__c` | Seuils et pondérations de scoring | `ConfigKey__c` |
| `DeweyExclusion__c` | Exclusions par composant, avec date d'expiration optionnelle | — |

### Objets de résultats (écrits à chaque run)

| Objet | Rôle | Parent |
|---|---|---|
| `DeweyAnalysis__c` | Métadonnées du run : scores, compteurs, statut | — |
| `DeweyFinding__c` | Violation individuelle d'une règle | `DeweyAnalysis__c` (Master-Detail) |
| `DeweyDelta__c` | Diff entre le run courant et le précédent | `DeweyAnalysis__c` (Master-Detail) |

### Champs clés — `DeweyAnalysis__c`

| Champ | Type | Description |
|---|---|---|
| `OrgAlias__c` | Text | Alias SF CLI de l'org analysée |
| `AnalysisDate__c` | DateTime | Horodatage du run |
| `ScoreGlobal__c` | Number | Score pondéré global (somme brute) |
| `ScoreAdopt__c` | Number | Score d'adoption no-code/low-code |
| `ScoreAdapt__c` | Number | Score d'adaptation plateforme |
| `FindingCritical__c` | Number | Nombre de findings critiques |
| `FindingTotal__c` | Formula | Total tous niveaux |
| `Status__c` | Picklist | `Running` / `Completed` / `Failed` |
| `Scope__c` | Picklist | Périmètre analysé (`all`, `apex`, `flows`, `security`, `omni`) |

### Champs clés — `DeweyFinding__c`

| Champ | Type | Description |
|---|---|---|
| `DeweyAnalysis__c` | Master-Detail | Run parent |
| `RuleId__c` | Text | Identifiant de la règle |
| `Severity__c` | Picklist | `Critical` / `Major` / `Minor` / `Info` |
| `ComponentType__c` | Picklist | `Apex` / `Flow` / `LWC` / `Object` / `Security` / `OmniStudio` / `Other` |
| `ComponentName__c` | Text | Nom du composant en défaut |
| `IsNew__c` | Checkbox | True si absent du run précédent |
| `IsResolved__c` | Checkbox | True si présent dans le run précédent mais absent du run courant |
| `IsAssigned__c` | Checkbox | True si une tâche de remédiation a été affectée |
| `Message__c` | LongTextArea | Description du problème |
| `Remediation__c` | LongTextArea | Conseil de remédiation |

---

## Flows

Trois flows Record-Triggered actifs sur `DeweyFinding__c` :

| Flow | Déclencheur | Action |
|---|---|---|
| `DeweyFinding_SetAssignedFromTask` | Création d'une Task avec `WhatId` non null | Passe `IsAssigned__c = true` sur le Finding lié |
| `DeweyFinding_PropagateAssigned` | `IsAssigned__c` passe à `true` | Propage `IsAssigned__c = true` à tous les findings avec le même `RuleId__c + ComponentName__c` (toutes analyses) |
| `DeweyFinding_InheritAssigned` | Création d'un nouveau finding avec `IsAssigned__c = false` | Hérite `IsAssigned__c = true` si un finding identique existe déjà avec ce flag |

### Workflow d'affectation

1. Ouvrir un `DeweyFinding__c` → créer une **Task** (related list Activités)
2. Assigner la Task à un **User** ou une **File d'attente** (`OwnerId` standard est polymorphique)
3. `IsAssigned__c` passe automatiquement à `true` sur ce finding
4. Le flag se propage à tous les findings identiques des analyses précédentes et sera hérité par les analyses futures

> Note sur la limitation platform : un champ lookup custom ne peut référencer qu'un seul type d'objet. La Task standard (champ `OwnerId`) est le seul mécanisme natif Salesforce permettant d'affecter du travail à un User **ou** une Queue dans un même champ.

---

## Rapports et Dashboard

**Dossier :** `DeweyReports`

| Rapport | Type de rapport | Description |
|---|---|---|
| Findings by Severity | `DeweyFindingRT__c` | Findings groupés par sévérité |
| Top Components by Findings | `DeweyFindingRT__c` | Composants les plus en défaut (Critical + Major) |
| New Findings — Open | `DeweyFindingRT__c` | Nouveaux findings non résolus |
| Score Trend | `DeweyAnalysisRT__c` | Évolution du score global dans le temps |

**Dashboard :** `Dewey — Org Quality` — agrège les 4 rapports.

---

## App Lightning

**Nom :** `Dewey — Org Assessment`  
Onglets : Dewey Analyses · Dewey Findings · Dewey Rules · Dewey Exclusions · Dewey Config · Reports · Dashboards

---

## Structure du package

```
force-app/main/default/
├── objects/
│   ├── DeweyAnalysis__c/        ← Runs d'analyse
│   ├── DeweyFinding__c/         ← Findings individuels
│   ├── DeweyDelta__c/           ← Diff entre deux runs
│   ├── DeweyRule__c/            ← Catalogue de règles
│   ├── DeweyConfig__c/          ← Configuration / seuils
│   └── DeweyExclusion__c/       ← Exclusions par composant
├── flows/
│   ├── DeweyFinding_SetAssignedFromTask.flow-meta.xml
│   ├── DeweyFinding_PropagateAssigned.flow-meta.xml
│   └── DeweyFinding_InheritAssigned.flow-meta.xml
├── permissionsets/
│   ├── Dewey_User.permissionset-meta.xml
│   └── Dewey_Reader.permissionset-meta.xml
├── applications/Dewey.app-meta.xml
├── tabs/
├── layouts/
├── reports/DeweyReports/
├── reportTypes/
├── dashboards/DeweyDashboards/
└── flexipages/DeweyHome.flexipage-meta.xml
```
