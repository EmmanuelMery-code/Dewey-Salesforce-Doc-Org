# dewey-orgSF — Package Salesforce

Package Salesforce Unlocked contenant le modèle de données, les automations, les permissions, les rapports et le dashboard de **Dewey Mode B** — extension headless de l'outil d'audit Salesforce org.

---

## Prérequis

- SF CLI (`sf`) installé et authentifié sur l'org cible
- Python 3.10+, dépendances installées (`pip install -r requirements.txt` à la racine du repo)
- PMD ou Salesforce Code Analyzer si l'analyse statique Apex est souhaitée

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

| Permission Set | Usage |
|---|---|
| `Dewey_User` | Utilisateurs qui exécutent les analyses via `assess.py` — accès complet en lecture/écriture |
| `Dewey_Reader` | Architectes et parties prenantes qui consultent uniquement les résultats — lecture seule |

---

## Lancer une analyse

Depuis la racine du repo Dewey :

```bash
python assess.py --org <alias> --source <chemin-ou-url> [options]
```

### Paramètres

| Paramètre | Requis | Défaut | Description |
|---|---|---|---|
| `--org` | Non | `ag2rPoc` | Alias SF CLI de l'org où pousser les résultats |
| `--source` | **Oui** | — | Chemin local vers un projet SFDX, ou URL GitHub (`https://...`) |
| `--branch` | Non | `main` (remote) ou branche active (local) | Branche à cloner (remote) ou à enregistrer dans l'analyse |
| `--project` | Non | Nom du repo ou dossier source | Identifiant stable du projet pour la déduplication inter-runs (ex. `xRM`) |
| `--version` | Non | — | Label de version facultatif (ex. `26.2`, `26.2.3`), stocké sur l'analyse |
| `--scope` | Non | `all` | Périmètre d'analyse : `all` \| `apex` \| `flows` \| `security` \| `omni` |
| `--analyzer` | Non | `none` (auto `pmd` si `--pmd-ruleset` fourni) | Analyseur statique : `pmd` \| `sfca` \| `none` |
| `--pmd-ruleset` | Non | — | Chemin vers un fichier ruleset PMD XML (requis avec `--analyzer pmd`) |

### Exemples

```bash
# Source locale, scope complet, sans analyse statique
python assess.py --org ag2rPoc --source /path/to/ReleasexRM

# Source locale avec PMD
python assess.py --org ag2rPoc --source /path/to/ReleasexRM \
  --pmd-ruleset /path/to/ruleset.xml

# Source locale avec Salesforce Code Analyzer (Apex + LWC + Aura)
python assess.py --org ag2rPoc --source /path/to/ReleasexRM --analyzer sfca

# Dépôt distant, branche spécifique, version taguée
python assess.py --org ag2rPoc \
  --source https://github.com/org/repo.git \
  --branch release/26.2 \
  --project xRM \
  --version 26.2

# Scope restreint aux flows uniquement
python assess.py --org ag2rPoc --source /path/to/ReleasexRM --scope flows
```

### Ce que fait la commande (étapes internes)

```
1. Charge les règles, config et exclusions depuis DeweyRule__c / DeweyConfig__c / DeweyExclusion__c
2. Si source distante : git clone --depth 1 vers /tmp/dewey-<org>-<timestamp>/
3. Lance les analyseurs : parsers XML DX → moteur de règles (Apex, Flows, LWC, Security, OmniStudio)
4. Pousse les résultats dans l'org SF :
   ├── Crée un DeweyAnalysis__c (statut Running → Completed)
   ├── Crée les DeweyFinding__c (un par violation)
   ├── Crée les DeweyAnalysisFinding__c (jonctions run ↔ finding, avec IsNewInRun__c / IsDisparuInRun__c)
   ├── Crée les DeweyPosture__c (niveaux d'adoption par capability, avec LevelChange__c)
   └── Patche DeweyAnalysis__c avec les champs delta (ScoreDelta__c, NewFindings__c, DisparuFindings__c…)
5. Affiche le résumé terminal : score global, top 5 findings, delta vs run précédent
6. Nettoie le répertoire temporaire si clone distant
```

---

## Modèle de données

### Objets de configuration (lus au démarrage)

| Objet | Rôle | Clé externe |
|---|---|---|
| `DeweyRule__c` | Catalogue de règles (sévérité, catégorie, message, remédiation) | `RuleId__c` |
| `DeweyConfig__c` | Seuils et pondérations de scoring | `ConfigKey__c` |
| `DeweyExclusion__c` | Exclusions par composant avec date d'expiration optionnelle | — |

### Objets de résultats (écrits à chaque run)

| Objet | Rôle |
|---|---|
| `DeweyAnalysis__c` | Métadonnées du run : scores, compteurs, statut, delta vs run précédent |
| `DeweyFinding__c` | Violation individuelle d'une règle — persiste entre les runs |
| `DeweyAnalysisFinding__c` | Jonction run ↔ finding (enregistrement par run où le finding est actif, nouveau ou disparu) |
| `DeweyPosture__c` | Niveau d'adoption par capability pour un run donné |
| `DeweyDelta__c` | Archive diff structuré entre deux runs (complément aux champs delta de `DeweyAnalysis__c`) |

### Champs clés — `DeweyAnalysis__c`

| Champ | Type | Description |
|---|---|---|
| `Source__c` | Text | Nom du projet analysé |
| `SourceBranch__c` | Text | Branche git |
| `Version__c` | Text | Label de version (`--version`) |
| `AnalysisDate__c` | DateTime | Horodatage du run |
| `ScoreGlobal__c` | Number | Score pondéré brut |
| `ScoreMax__c` | Number | Score maximum théorique |
| `ScoreRatio__c` | Formula | Score en % (`ScoreGlobal / ScoreMax × 100`) |
| `ScoreAdopt__c` | Number | % du poids des capabilities au niveau "Adopt" |
| `ScoreAdapt__c` | Number | % du poids des capabilities au niveau "Adapt" |
| `ScoreDelta__c` | Number(6,1) | Δ ScoreRatio vs run précédent (points de %) |
| `FindingCritical__c` | Number | Findings critiques |
| `FindingMajor__c` | Number | Findings majeurs |
| `FindingMinor__c` | Number | Findings mineurs |
| `FindingInfo__c` | Number | Findings informatifs |
| `FindingTotal__c` | Formula | Total tous niveaux |
| `NewFindings__c` | Number | Nouveaux findings détectés dans ce run |
| `DisparuFindings__c` | Number | Findings disparus (résolus) dans ce run |
| `CriticalDelta__c` | Number | Δ findings critiques vs run précédent |
| `MajorDelta__c` | Number | Δ findings majeurs vs run précédent |
| `PreviousAnalysis__c` | Lookup | Lien vers l'analyse précédente de la même source |
| `Status__c` | Picklist | `Running` / `Completed` / `Failed` |
| `Scope__c` | Picklist | Périmètre analysé |

### Champs clés — `DeweyFinding__c`

| Champ | Type | Description |
|---|---|---|
| `RuleId__c` | Text | Identifiant de la règle |
| `Severity__c` | Picklist | `Critical` / `Major` / `Minor` / `Info` |
| `ComponentType__c` | Picklist | `Apex` / `Flow` / `LWC` / `Object` / `Security` / `OmniStudio` / `Other` |
| `ComponentName__c` | Text | Nom du composant en défaut |
| `FilePath__c` | Text | Chemin relatif du fichier (ex. `/force-app/main/default/classes/Foo.cls`) |
| `LineNumber__c` | Number | Ligne dans le fichier |
| `Message__c` | LongTextArea | Description du problème |
| `Remediation__c` | LongTextArea | Conseil de remédiation |
| `Status__c` | Picklist | `Open` / `In Progress` / `Resolved` / `Accepted Risk` |
| `FirstSeenDate__c` | Date | Date du premier run où ce finding est apparu |

### Champs clés — `DeweyAnalysisFinding__c` (jonction)

| Champ | Type | Description |
|---|---|---|
| `DeweyAnalysis__c` | Lookup | Run parent |
| `DeweyFinding__c` | Lookup | Finding associé |
| `IsNewInRun__c` | Checkbox | True si ce finding est apparu pour la première fois dans ce run |
| `IsDisparuInRun__c` | Checkbox | True si ce finding était actif dans le run précédent mais absent de ce run (résolu) |

### Champs clés — `DeweyPosture__c`

| Champ | Type | Description |
|---|---|---|
| `DeweyAnalysis__c` | Lookup | Run parent |
| `CapabilityId__c` | Text | Identifiant de la capability (ex. `automation`) |
| `CapabilityLabel__c` | Text | Libellé affiché (ex. `Automatisation`) |
| `Level__c` | Picklist | Niveau détecté : `Adopt (OOTB)` / `Adopt declaratif` / `Adapt (declaratif)` / `Adapt (code)` |
| `PreviousLevel__c` | Picklist | Niveau du run précédent |
| `LevelChange__c` | Picklist | `Amélioré` / `Dégradé` / `Stable` / `Premier run` |
| `Weight__c` | Number | Poids de la capability dans le score (total = 20) |
| `Evidence__c` | LongTextArea | Détail des éléments détectés qui justifient le niveau |

---

## Automations (Record-Triggered Flows)

Deux flows Before Save actifs, déclenchés à la **création** des records :

| Flow | Objet déclencheur | Action |
|---|---|---|
| `Dewey - Assign Finding to Queue` | `DeweyFinding__c` | Affecte `OwnerId` à la queue `Findings_to_be_assigned` |
| `Dewey - Assign Posture to Queue` | `DeweyPosture__c` | Affecte `OwnerId` à la queue `Findings_to_be_assigned` |

### Pourquoi une queue ?

L'affectation à une queue permet à une équipe de prendre en charge les findings et postures sans les attribuer individuellement à un utilisateur dès la création. Les membres de la queue voient les records dans la vue **"Findings to be assigned"** (disponible sur les deux objets) et peuvent se les assigner depuis la liste.

### Fonctionnement du flow

```
Déclencheur : DeweyFinding__c / DeweyPosture__c — Before Save — Create
  │
  ├─ Get Queue — cherche le Group de type Queue avec DeveloperName = Findings_to_be_assigned
  │
  ├─ Decision : Queue Found ?
  │     ├─ Yes → Assign Owner : $Record.OwnerId = Get_Queue.Id
  │     └─ Not Found → (no-op, finding créé sans affectation de queue)
```

L'affectation est faite **Before Save** (pas d'update DML supplémentaire) — aucun governor limit consommé pour cette opération.

> Note : la queue `Findings_to_be_assigned` doit exister dans l'org avant le premier run. Elle est créée via l'UI Salesforce (Setup > Queues) ou via l'API REST — le fichier `queues/Findings_to_be_assigned.queue-meta.xml` sert de documentation mais ne peut pas être déployé via Metadata API (limitation connue de l'API pour les queues sans objet standard).

---

## Scoring — ScoreAdopt et ScoreAdapt

Les scores d'adoption sont calculés sur 9 capabilities (poids total = 20) :

| Capability | Poids | Adopt (OOTB) | Adopt declaratif | Adapt (declaratif) | Adapt (code) |
|---|---|---|---|---|---|
| Modèle de données | 3 | Peu d'objets custom | Quelques objets | Nombreux objets | Très nombreux |
| Sécurité | 3 | Peu de profils custom | Quelques profils | Nombreux profils | Très nombreux |
| Automatisation | 3 | Aucun flow ni trigger | — | Flows uniquement | Au moins 1 trigger |
| Validation métier | 2 | Aucune règle | — | Validation Rules | Apex addError |
| UI / Layout | 2 | Aucun LWC ni FlexiPage | — | FlexiPages uniquement | Au moins 1 LWC |
| Intégration | 2 | Aucun callout | — | — | Apex callouts |
| Reporting | 2 | Aucun rapport | — | Rapports uniquement | Dashboards |
| Notifications | 2 | Aucune alerte | — | Email Alerts | Messaging.sendEmail |
| OmniStudio | 1 | Rien | — | UI Cards / DataRaptors | OmniScripts / IPs |

- **`ScoreAdopt__c`** = `(somme des poids des capabilities à niveau "Adopt") / 20 × 100`
- **`ScoreAdapt__c`** = `100 − ScoreAdopt__c`

---

## Rapports et Dashboard

**Dossier :** `DeweyReports`

| Rapport | Description |
|---|---|
| Findings by Severity | Findings groupés par sévérité |
| Findings by Component | Composants les plus en défaut (Critical + Major) |
| Score Trend | Évolution du ScoreRatio dans le temps par source |
| Open Findings by Assignee | Findings ouverts répartis par propriétaire |
| Findings par analyse | Détail des findings pour un run sélectionné |

**Dashboard :** `Dewey — Org Quality` — KPI cards (score, delta, critiques), évolution temporelle, répartition par composant.

**Home app :** `DeweyHome` — page d'accueil Lightning intégrant le dashboard et des raccourcis vers les objets.

---

## App Lightning

**Nom :** `Dewey — Org Assessment`  
Onglets : Dewey Analyses · Dewey Findings · Dewey Postures · Dewey Rules · Dewey Exclusions · Dewey Config · Reports · Dashboards

---

## Structure du package

```
force-app/main/default/
├── objects/
│   ├── DeweyAnalysis__c/        ← Runs d'analyse + champs delta
│   ├── DeweyFinding__c/         ← Violations individuelles
│   ├── DeweyAnalysisFinding__c/ ← Jonction run ↔ finding (IsNewInRun, IsDisparuInRun)
│   ├── DeweyPosture__c/         ← Niveaux d'adoption par capability
│   ├── DeweyDelta__c/           ← Archive diff structuré
│   ├── DeweyRule__c/            ← Catalogue de règles
│   ├── DeweyConfig__c/          ← Configuration / seuils
│   └── DeweyExclusion__c/       ← Exclusions par composant
├── flows/
│   ├── Dewey_AssignFindingToQueue.flow-meta.xml
│   └── Dewey_AssignPostureToQueue.flow-meta.xml
├── queues/
│   └── Findings_to_be_assigned.queue-meta.xml  ← documentation uniquement
├── permissionsets/
│   ├── Dewey_User.permissionset-meta.xml
│   └── Dewey_Reader.permissionset-meta.xml
├── applications/Dewey.app-meta.xml
├── layouts/
├── reportTypes/
├── reports/DeweyReports/
├── dashboards/DeweyDashboards/
└── flexipages/DeweyHome.flexipage-meta.xml
```
