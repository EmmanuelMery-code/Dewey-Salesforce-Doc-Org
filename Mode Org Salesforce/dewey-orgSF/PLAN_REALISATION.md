# Plan de Réalisation — Partie Salesforce (Mode B)

> Périmètre : package `dewey-orgSF` déployé sur l'org `ag2rPoc`.
> Ce plan couvre uniquement la partie Salesforce. La partie Python (assess.py, services) est dans `/PLAN.md`.

---

## Vue d'ensemble

```
force-app/main/default/
├── objects/                    ← 6 objets custom (3 config + 3 résultats)
│   ├── DeweyRule__c/
│   ├── DeweyConfig__c/
│   ├── DeweyExclusion__c/
│   ├── OrgAnalysis__c/
│   ├── Finding__c/
│   └── AnalysisDelta__c/
├── permissionsets/
│   └── Dewey_User.permissionset-meta.xml
├── tabs/                       ← Onglets pour les 4 objets principaux
├── applications/
│   └── Dewey.app-meta.xml      ← App Lightning Dewey
├── layouts/                    ← Page layouts par objet
├── reports/
│   └── DeweyReports/           ← 4 rapports standard
├── dashboards/
│   └── DeweyDashboards/        ← 1 dashboard qualité
└── flexipages/
    └── DeweyHome.flexipage-meta.xml  ← Home page de l'app
```

Seed data (hors package, chargé via CLI) :
```
../../seed/
├── DeweyRule.csv
└── DeweyConfig.csv
```

---

## Étape 1 — Objets de configuration

### 1.1 `DeweyRule__c`

Objet central de règles. Lu au démarrage du skill pour piloter l'analyse.

**Fichiers à créer :**
```
objects/DeweyRule__c/
├── DeweyRule__c.object-meta.xml          ← définition objet (label, sharing: ReadWrite, nameField)
└── fields/
    ├── RuleId__c.field-meta-xml           ← Text(50), ExternalId=true, Unique=true, Required
    ├── Severity__c.field-meta.xml         ← Picklist: Critical / Major / Minor / Info
    ├── Category__c.field-meta.xml         ← Picklist: Security / Performance / Quality / Architecture
    ├── Subcategory__c.field-meta.xml      ← Text(100)
    ├── IsEnabled__c.field-meta.xml        ← Checkbox, default=true
    ├── Source__c.field-meta.xml           ← Picklist: Dewey / PMD / Custom
    ├── PmdRuleRef__c.field-meta.xml       ← Text(255)
    ├── Message__c.field-meta.xml          ← TextArea(255)
    ├── Remediation__c.field-meta.xml      ← LongTextArea(32768)
    └── WellArchitectedRef__c.field-meta.xml ← URL
```

**Champ Name standard :** `RuleName` (label "Rule Name"), type Text, Required.

**Règles de validation à prévoir :**
- `RuleId__c` doit correspondre au pattern `[A-Z]+-[A-Z]+-\d{3}` (ex: APEX-SEC-001)

---

### 1.2 `DeweyConfig__c`

Clés de configuration : seuils, poids de scoring, paramètres globaux.

**Fichiers à créer :**
```
objects/DeweyConfig__c/
├── DeweyConfig__c.object-meta.xml        ← sharing: ReadWrite
└── fields/
    ├── ConfigKey__c.field-meta.xml        ← Text(100), ExternalId=true, Unique=true, Required
    ├── ConfigValue__c.field-meta.xml      ← Text(255), Required
    └── Description__c.field-meta.xml     ← Text(255)
```

**Champ Name standard :** `ConfigName` (label "Config Name"), type Text.

**Valeurs seed (DeweyConfig.csv) — à créer :**

| ConfigKey | ConfigValue | Description |
|---|---|---|
| `threshold_apex_complexity` | `10` | Complexité cyclomatique max Apex |
| `threshold_apex_class_lines` | `500` | Lignes max par classe Apex |
| `threshold_flow_elements` | `50` | Éléments max par Flow |
| `weight_score_security` | `0.35` | Poids catégorie Security dans le score global |
| `weight_score_quality` | `0.30` | Poids catégorie Quality |
| `weight_score_performance` | `0.20` | Poids catégorie Performance |
| `weight_score_architecture` | `0.15` | Poids catégorie Architecture |
| `score_critical_penalty` | `10` | Points déduits par finding Critical |
| `score_major_penalty` | `5` | Points déduits par finding Major |
| `score_minor_penalty` | `1` | Points déduits par finding Minor |

---

### 1.3 `DeweyExclusion__c`

Exclusions par composant (ex: ignorer une règle sur une classe legacy).

**Fichiers à créer :**
```
objects/DeweyExclusion__c/
├── DeweyExclusion__c.object-meta.xml     ← sharing: ReadWrite
└── fields/
    ├── RuleId__c.field-meta.xml           ← Text(50), Required — référence à DeweyRule__c.RuleId__c
    ├── ComponentName__c.field-meta.xml    ← Text(255), Required
    ├── Reason__c.field-meta.xml           ← TextArea(255)
    └── ExpiryDate__c.field-meta.xml       ← Date
```

**Champ Name standard :** `ExclusionName` (label "Exclusion"), type Text, AutoNumber format `EXC-{0000}`.

---

## Étape 2 — Objets de résultats

### 2.1 `OrgAnalysis__c`

Un enregistrement par run d'analyse. Point de départ pour tous les findings.

**Fichiers à créer :**
```
objects/OrgAnalysis__c/
├── OrgAnalysis__c.object-meta.xml        ← sharing: ReadWrite, Activities=false, History=false
└── fields/
    ├── OrgAlias__c.field-meta.xml         ← Text(50), Required
    ├── AnalysisDate__c.field-meta.xml     ← DateTime, Required
    ├── SourcePath__c.field-meta.xml       ← Text(255)
    ├── SourceBranch__c.field-meta.xml     ← Text(100)
    ├── Scope__c.field-meta.xml            ← Text(50) — all/apex/flows/security/omni
    ├── ScoreGlobal__c.field-meta.xml      ← Number(5,2)
    ├── ScoreAdopt__c.field-meta.xml       ← Number(5,2) — % no-code / low-code
    ├── ScoreAdapt__c.field-meta.xml       ← Number(5,2) — % custom vs standard
    ├── ApexCount__c.field-meta.xml        ← Number(6,0)
    ├── FlowCount__c.field-meta.xml        ← Number(6,0)
    ├── LwcCount__c.field-meta.xml         ← Number(6,0)
    ├── FindingCritical__c.field-meta.xml  ← Number(6,0)
    ├── FindingMajor__c.field-meta.xml     ← Number(6,0)
    ├── FindingMinor__c.field-meta.xml     ← Number(6,0)
    ├── FindingInfo__c.field-meta.xml      ← Number(6,0)
    ├── FindingTotal__c.field-meta.xml     ← Formula(Number) : somme des 4 compteurs
    ├── Status__c.field-meta.xml           ← Picklist: Running / Completed / Failed
    └── ErrorMessage__c.field-meta.xml    ← LongTextArea(32768) — renseigné si Status=Failed
```

**Champ Name standard :** `AnalysisName` (label "Analysis Name"), type Text, AutoNumber format `DEWEY-{00000}`.

---

### 2.2 `Finding__c`

Un enregistrement par violation détectée, lié à une `OrgAnalysis__c`.

**Fichiers à créer :**
```
objects/Finding__c/
├── Finding__c.object-meta.xml            ← sharing: ControlledByParent (via OrgAnalysis__c)
└── fields/
    ├── OrgAnalysis__c.field-meta.xml      ← Lookup(OrgAnalysis__c), Required, CascadeDelete
    ├── RuleId__c.field-meta.xml           ← Text(50), Required
    ├── Severity__c.field-meta.xml         ← Picklist: Critical / Major / Minor / Info
    ├── ComponentType__c.field-meta.xml    ← Picklist: Apex / Flow / LWC / Object / Security / OmniStudio / Other
    ├── ComponentName__c.field-meta.xml    ← Text(255)
    ├── FilePath__c.field-meta.xml         ← Text(255)
    ├── LineNumber__c.field-meta.xml       ← Number(6,0)
    ├── Message__c.field-meta.xml          ← TextArea(255)
    ├── Remediation__c.field-meta.xml      ← LongTextArea(32768)
    ├── IsNew__c.field-meta.xml            ← Checkbox — apparu depuis la dernière analyse
    ├── IsResolved__c.field-meta.xml       ← Checkbox — résolu depuis la dernière analyse
    ├── ResolvedDate__c.field-meta.xml     ← Date
    └── AssignedTo__c.field-meta.xml       ← Lookup(User)
```

**Champ Name standard :** `FindingName` (label "Finding"), type Text, AutoNumber format `FIND-{000000}`.

---

### 2.3 `AnalysisDelta__c`

Diff entre deux analyses successives. Créé automatiquement par le skill.

**Fichiers à créer :**
```
objects/AnalysisDelta__c/
├── AnalysisDelta__c.object-meta.xml
└── fields/
    ├── CurrentAnalysis__c.field-meta.xml  ← Lookup(OrgAnalysis__c), Required
    ├── PreviousAnalysis__c.field-meta.xml ← Lookup(OrgAnalysis__c)
    ├── NewFindings__c.field-meta.xml      ← Number(6,0)
    ├── ResolvedFindings__c.field-meta.xml ← Number(6,0)
    ├── ScoreDelta__c.field-meta.xml       ← Number(5,2) — positif = amélioration
    ├── CriticalDelta__c.field-meta.xml    ← Number(5,0)
    ├── MajorDelta__c.field-meta.xml       ← Number(5,0)
    └── Summary__c.field-meta.xml          ← LongTextArea(32768) — résumé texte du delta
```

**Champ Name standard :** `DeltaName` (label "Delta"), type Text, AutoNumber format `DELTA-{00000}`.

---

## Étape 3 — Permission Set

**Fichier :** `permissionsets/Dewey_User.permissionset-meta.xml`

Droits à accorder :
- **6 objets** : CRUD complet pour tous les utilisateurs du skill
- **Tous les champs** des 6 objets : Read + Edit
- **Tab visibility** : DefaultOn pour les 4 onglets principaux

> Aucun profil modifié — tout passe par le permission set.

---

## Étape 4 — Onglets et Application

### 4.1 Onglets (tabs/)

4 onglets à créer :
```
tabs/
├── DeweyRule__c.tab-meta.xml        ← icône: custom:custom18 (règles)
├── OrgAnalysis__c.tab-meta.xml      ← icône: custom:custom53 (analyse)
├── Finding__c.tab-meta.xml          ← icône: standard:outcome (résultats)
└── DeweyExclusion__c.tab-meta.xml   ← icône: custom:custom52 (exclusions)
```

### 4.2 Application Lightning (applications/)

**Fichier :** `applications/Dewey.app-meta.xml`

- Label : `Dewey — Org Assessment`
- Navigation : `standard-navigation`
- Tabs inclus : DeweyRule__c, OrgAnalysis__c, Finding__c, DeweyExclusion__c, DeweyConfig__c

---

## Étape 5 — Page Layouts

Un layout par objet (minimal mais utilisable) :

```
layouts/
├── DeweyRule__c-Rule Layout.layout-meta.xml
├── DeweyConfig__c-Config Layout.layout-meta.xml
├── DeweyExclusion__c-Exclusion Layout.layout-meta.xml
├── OrgAnalysis__c-Analysis Layout.layout-meta.xml
├── Finding__c-Finding Layout.layout-meta.xml
└── AnalysisDelta__c-Delta Layout.layout-meta.xml
```

Layout `OrgAnalysis__c` : sections Scores / Counts / Status / Related Lists (Findings, Deltas).
Layout `Finding__c` : sections Identification / Details / Assignment / Delta flags.

---

## Étape 6 — Rapports

Dossier : `reports/DeweyReports/`

| Fichier | Type | Contenu |
|---|---|---|
| `DeweyReports-meta.xml` | Folder | Dossier rapports |
| `findings_by_severity.report-meta.xml` | Summary | Findings groupés par Severity, comptés par ComponentType |
| `findings_by_component.report-meta.xml` | Summary | Top composants par nombre de findings Critical/Major |
| `score_trend.report-meta.xml` | Summary | ScoreGlobal__c + FindingCritical__c par date (OrgAnalysis__c) |
| `new_findings_open.report-meta.xml` | Tabular | Findings IsNew=true, non résolus, triés par Severity |

---

## Étape 7 — Dashboard

Dossier : `dashboards/DeweyDashboards/`

| Fichier | Contenu |
|---|---|
| `DeweyDashboards-meta.xml` | Dossier dashboard |
| `DeweyQualityDashboard.dashboard-meta.xml` | Dashboard 3 colonnes — voir détail ci-dessous |

**Composants du dashboard :**
1. Score global actuel (gauge ou metric) — dernière `OrgAnalysis__c`
2. Évolution du score dans le temps (line chart — `score_trend`)
3. Répartition findings par sévérité (donut — `findings_by_severity`)
4. Top 10 composants avec le plus de findings (bar chart — `findings_by_component`)
5. Findings nouveaux non résolus (metric — `new_findings_open`)

---

## Étape 8 — Home Page (FlexiPage)

**Fichier :** `flexipages/DeweyHome.flexipage-meta.xml`

- Type : `AppPage`
- App : `Dewey`
- Composants : `flowOrchestrationWorkGuide` (si applicable), liste récente `OrgAnalysis__c`, metric ScoreGlobal

---

## Ordre de déploiement

```
1. Objets config (DeweyRule__c, DeweyConfig__c, DeweyExclusion__c)
2. Objets résultats (OrgAnalysis__c, Finding__c, AnalysisDelta__c)
3. Permission Set (Dewey_User)
4. Tabs + Application
5. Layouts
6. Reports + Dashboard
7. FlexiPage
```

Commande de déploiement global :
```bash
sf project deploy start \
  -d force-app/main/default \
  --ignore-conflicts \
  -o ag2rPoc
```

Seed data après premier déploiement :
```bash
sf data import tree --files ../../seed/DeweyRule.csv -o ag2rPoc
sf data import tree --files ../../seed/DeweyConfig.csv -o ag2rPoc
```

---

## Checklist de validation post-déploiement

- [ ] 6 objets visibles dans Setup > Object Manager
- [ ] Permission Set `Dewey_User` assignable à un utilisateur
- [ ] App `Dewey — Org Assessment` visible dans App Launcher
- [ ] 4 onglets accessibles
- [ ] SOQL de test : `SELECT Id, RuleId__c FROM DeweyRule__c LIMIT 5` retourne des données (après seed)
- [ ] SOQL de test : `SELECT Id, ConfigKey__c, ConfigValue__c FROM DeweyConfig__c` retourne les 10 clés
- [ ] Création manuelle d'un `OrgAnalysis__c` + `Finding__c` lié → relationship fonctionne
- [ ] Rapports s'ouvrent sans erreur
- [ ] Dashboard s'affiche sans erreur

---

## Backlog SF (hors V1)

- **FlexiPage avancée** : composant LWC dédié avec score visuel et top findings inline
- **CRM Analytics** : dataset Dewey + recette de transformation pour tendances longues durées
- **Approval / Assignment** : Flow d'assignation automatique des findings Critical à une queue
- **Scheduled Apex** : déclenchement automatique du skill (V2 — hors périmètre Mode B initial)
