# Dewey — Technical Manual (Parsing &amp; Analysis)

> Bilingual document — **Français** puis **English**.
> Ce manuel couvre exclusivement les deux modules cœur de Dewey : le **parsing** (`src/parsers/salesforce_parser/`) et l'**analyse statique** (`src/analyzer/`). Il ne couvre pas l'interface graphique (`src/ui/`) ni la génération de rapports (`src/reporting/`), qui sont de simples consommateurs de ces deux modules.

---

# 🇫🇷 Partie 1 — Français

## 1. Vue d'ensemble

Dewey analyse un projet Salesforce DX (`force-app/main/default/...`) en deux temps, totalement découplés :

```
Dossier source SFDX
        │
        ▼
┌───────────────────────┐
│   1. PARSING           │   src/parsers/salesforce_parser/
│   XML → dataclasses    │   → produit un MetadataSnapshot
└───────────────────────┘
        │
        ▼
┌───────────────────────┐
│   2. ANALYSE STATIQUE  │   src/analyzer/
│   Snapshot → findings  │   → produit un AnalyzerReport
└───────────────────────┘
        │
        ▼
   Rapports (HTML/Excel/Word en Mode A, Custom Objects Salesforce en Mode B)
```

- Le **parsing** ne fait aucune évaluation qualitative : il transforme du XML/Apex/JS en objets Python structurés (`MetadataSnapshot`), et applique les **exclusions de métadonnées** (composants totalement ignorés).
- L'**analyse** prend ce `MetadataSnapshot` en entrée, applique un **catalogue de règles déclaratif** (`rules.xml`) et retourne un `AnalyzerReport` contenant des `Finding` (violations de règles), en appliquant les **exclusions de règles** (règle désactivée pour un composant donné).

Ces deux modules ne dépendent d'aucun code UI (`tkinter`) : ils peuvent être utilisés en ligne de commande, dans un script, ou dans le mode headless (`assess.py` / `src/core/orchestrator_headless.py`, "Mode B").

## 2. Le module de Parsing

### 2.1 Structure

```
src/parsers/salesforce_parser/
├── parser.py              ← classe SalesforceMetadataParser (point d'entrée)
├── base.py                 ← état partagé (_ParserState) + CATEGORY_ALIASES
├── exclusion_mixin.py       ← chargement + application des exclusions de métadonnées
├── objects_mixin.py         ← parsing des SObjects (champs, record types, VR, DR...)
├── security_mixin.py        ← parsing des Profiles / Permission Sets
├── apex_mixin.py             ← parsing des classes/triggers Apex
├── apex_helpers.py           ← détection SOQL/DML "in loop" (brace-aware)
├── flows_mixin.py            ← parsing des Flows (éléments, profondeur, largeur)
├── components_mixin.py       ← parsing LWC / Aura
├── inventory_mixin.py         ← inventaire générique (tous types de composants)
└── dependencies_mixin.py       ← analyse d'impact + détection d'orphelins
```

`SalesforceMetadataParser` est une classe composée par **héritage multiple de mixins** (chaque mixin porte une responsabilité thématique). C'est un pattern "Mixin composition" : chaque mixin ajoute des méthodes privées (`_parse_objects`, `_parse_apex_folder`, `_parse_flows`, etc.) à un état partagé (`_ParserState`).

### 2.2 Algorithme de parsing (`SalesforceMetadataParser.parse()`)

1. **Résolution des racines de package** (`_resolve_package_roots`) : lecture de `sfdx-project.json` → `packageDirectories`, avec repli sur `force-app/main/default` si absent.
2. Pour chaque racine de package, parsing **dossier par dossier** (objects, profiles, permissionsets, classes, triggers, flows, agents, genAiPromptTemplates, sharingRules, duplicateRules, permissionsetgroups, lwc, aura, flexipages, layouts, tabs, applications, omniScripts, omniIntegrationProcedures, omniUiCards, omniDataTransforms, omniProcesses, aiPredictions, decisionMatrices, expressionSets…).
3. Chaque sous-parseur retourne des **dataclasses** typées (`ObjectInfo`, `ApexArtifact`, `FlowInfo`, `SecurityArtifact`, `LwcInfo`, `AuraInfo`, …) définies dans `src/core/models/`.
4. **Filtrage par exclusion** : après collecte, chaque liste (`objects`, `apex_artifacts`, `flows`, `profiles`, `permission_sets`, `agents`, `gen_ai_prompts`, ainsi que les compteurs d'inventaire comme `flexipages`, `tabs`, `omniScripts`…) est filtrée via `self._is_excluded(category, *names)`.
5. **Calcul des métriques bruts** (`CustomizationMetrics`) : comptages (objets custom, champs custom, classes Apex, flows, etc.) utilisés plus tard pour le scoring No-Code/Low-Code/Pro-Code.
6. **Analyse de dépendances et détection d'orphelins** (`_analyze_dependencies`), voir §2.4.
7. Retour d'un objet unique : `MetadataSnapshot` (voir `src/core/models/snapshot.py`), qui contient absolument tout ce qui a été parsé : objets, profils, permission sets, apex, flows, lwc/aura, agents, prompts IA, sharing/duplicate rules, dépendances, orphelins, métriques, inventaire.

### 2.3 Algorithme d'exclusion des métadonnées

Fichier : `exclusion_mixin.py`. Deux étapes :

**a) Chargement (`_load_exclusion_rules`)**
- Lecture d'un fichier JSON (`exclusion.json`) au format :
  ```json
  { "metadata_exclusions": [
      { "type": "apex", "element": "AsyncFrameworkConfig", "commentaire": "" }
  ]}
  ```
- Le champ `type` est normalisé via un **dictionnaire d'alias de catégories** (`CATEGORY_ALIASES`, dans `base.py`) : par exemple `"object"`, `"objet"`, `"sobject"` sont tous mappés vers la catégorie interne `object`. La catégorie spéciale `"all"` s'applique à **tous les types de composants** (utile pour des motifs génériques comme `*PEG*`).
- Tolérance multi-encodage (`utf-8`, `utf-16`, `latin-1`) et rétro-compatibilité avec un ancien format liste (`"Hors analyse": [[categorie, pattern], ...]`).

**b) Correspondance (`_is_excluded(category, *names)`)** — algorithme de *pattern matching* à 3 niveaux, appliqué à **chaque** motif de la catégorie ciblée + catégorie `all`, contre **chaque** nom candidat (ex : à la fois le nom API et le label) :
1. **Glob match** insensible à la casse via `fnmatch.fnmatch` (supporte les jokers `*`, `?`) ;
2. **Sous-chaîne** insensible à la casse (`pattern in nom`) — permet d'exclure par simple mot-clé sans avoir à écrire de wildcard ;
3. **Match normalisé** : espaces/underscores supprimés des deux côtés (`_normalize_exclusion_token`), pour absorber les variations de nommage (`SF Async` ≈ `SF_Async__c`).

Dès qu'une des trois conditions est vraie pour un couple (motif, nom), le composant est exclu.

### 2.4 Analyse de dépendances et détection d'orphelins (`dependencies_mixin.py`)

- **Construction d'un graphe de dépendances** simplifié par scan textuel (pas d'AST complet) : chaque artefact source (classe Apex, trigger, Flow, LWC, Aura, Report) est scanné à la recherche des noms d'objets, de champs (`Objet.Champ`) et de classes Apex connus. Chaque correspondance produit une arête `Dependency(source, target)`.
- **Détection d'orphelins** : un composant est un candidat orphelin si son nom **n'apparaît jamais comme cible** (`target_name`) d'une dépendance — c.-à-d. si rien dans l'org ne le référence. Des règles d'exception s'appliquent (les triggers sont des points d'entrée, les objets standard ne sont jamais orphelins, les classes de test sont ignorées).

## 3. Le module d'Analyse statique (`src/analyzer/`)

### 3.1 Structure

```
src/analyzer/
├── rules.xml            ← catalogue déclaratif des règles (source de vérité)
├── rule_catalog.py       ← chargement XML → Rule, RuleCatalog
├── models.py              ← dataclasses Rule / Finding
├── engine.py               ← AnalyzerEngine : orchestrateur + agrégation (AnalyzerReport)
├── apex_analyzer.py         ← règles APEX-*, TRIG-*
├── flow_analyzer.py          ← règles FLOW-*
├── object_analyzer.py         ← règles OBJ-*, FIELD-*, VR-*, DR-*
├── lwc_analyzer.py             ← règles LWC-*
├── aura_analyzer.py              ← règles AURA-*
├── security_analyzer.py           ← règles SEC-* (Profiles / Permission Sets)
└── omni_analyzer.py                ← règles pour OmniStudio Data Transforms
```

### 3.2 Le catalogue de règles (moteur de type "linter")

Dewey implémente un **moteur de règles déclaratif** inspiré des linters statiques (PMD, ESLint) :
- Chaque règle est définie dans `rules.xml` avec un identifiant unique (ex. `APEX-PERF-001`), un `scope` (apex, flow, object, security…), une `severity` (`Critical`/`Major`/`Minor`/`Info`), une `category` (`Trusted`/`Easy`/`Adaptable`), un titre, une description, une justification (`rationale`) et une remédiation.
- `RuleCatalog` charge ce XML et expose des accesseurs (`.enabled`, `.get(id)`, `.for_scope(scope)`).
- Chaque fonction d'analyse (`analyze_apex_artifact`, `analyze_flow`, `analyze_object`, …) est une suite de **vérifications indépendantes** : elle récupère la règle par son id, vérifie qu'elle est activée, puis évalue une condition métier sur l'artefact et émet un `Finding` (avec message, détails et éventuellement numéro de ligne).
- L'`AnalyzerEngine` orchestre l'appel de toutes ces fonctions sur un `MetadataSnapshot` complet (`analyze_snapshot`), agrège les résultats par type d'artefact dans un `AnalyzerReport`, et fournit des synthèses : `severity_counts()`, `rule_counts()`, `category_counts()`.
- Une **double couche d'exclusion** existe ici aussi : `AnalyzerEngine` charge un second fichier JSON (`rule_exclusions`) qui associe un `rule_id` à un ensemble de noms de métadonnées à exempter de cette règle précise (`_is_rule_applicable`), en plus d'un filtre par version d'API minimale/maximale (`min_api_version` / `max_api_version` déclarés sur la règle).

### 3.3 Algorithmes d'analyse notables

| # | Nom / zone | Fichier | Description de l'algorithme |
|---|---|---|---|
| 1 | **Stripping de commentaires/chaînes** | `apex_analyzer._strip_comments_and_strings`, `apex_helpers._strip_apex_comments` | Automate à état (scan caractère par caractère) qui remplace `//...`, `/*...*/` et le contenu des littéraux `'...'`/`"..."` par des espaces, en préservant les retours à la ligne. Sert de prétraitement obligatoire avant toute recherche par regex pour éviter les faux positifs (ex. un mot-clé SQL cité dans un commentaire). |
| 2 | **Détection SOQL/DML "in loop"** (brace-aware) | `apex_helpers._detect_pattern_in_loop` | Localise chaque boucle (`for`/`while`/`do`), extrait précisément son corps en **comptant les accolades** (profondeur de nesting), puis recherche le motif SOQL (`[SELECT ...]`, `Database.query(`) ou DML (`insert/update/upsert/delete/undelete/merge`) strictement à l'intérieur de ce corps délimité — pas juste "quelque part après le mot `for`". Ignore volontairement le pattern recommandé `for (x : [SELECT ...])`. |
| 3 | **Détection d'auto-récursion Apex** (APEX-REL-002) | `apex_analyzer._detect_self_recursive_methods` | Extrait chaque corps de méthode par comptage d'accolades (`_extract_method_bodies`), puis recherche si le nom de la méthode s'appelle lui-même dans son propre corps. Ignoré si la classe contient déjà un indice de garde de réentrance (`static`, `Set<Id>`, `recursionGuard`, `bypass`, …). |
| 4 | **Détection de récursion de trigger after-save** (TRIG-REL-001) | `apex_analyzer._detect_trigger_after_save_recursion` | Analyse la déclaration du trigger (`trigger X on Y (after insert, ...)`) puis recherche par regex si `Trigger.new`/`Trigger.newMap` (ou un alias assigné via `Object x = Trigger.new`) fait l'objet d'un DML direct — signature classique de boucle infinie. |
| 5 | **Détection d'injection SOQL dynamique** (APEX-SEC-003) | `apex_analyzer._detect_soql_injection` | Repère les appels `Database.query(...)`, examine l'argument : présence de concaténation (`+`) ou d'interpolation (`$`) sans `escapeSingleQuotes` ni variable liée (`:`) → signalé comme risque d'injection. |
| 6 | **Détection de cycles d'appels entre classes Apex** (APEX-REL-003) | `engine._detect_apex_call_cycles` + `engine._find_cycles` | Construit un **graphe d'appels** `{Classe → {Classes mentionnées}}` à partir des identifiants PascalCase présents dans le code (après stripping des commentaires/chaînes), puis applique l'**algorithme de Tarjan** pour extraire les composantes fortement connexes (SCC). Toute composante de taille ≥ 2, ou toute auto-boucle, est remontée comme un cycle de dépendance circulaire entre classes. |
| 7 | **Scoring de complexité de Flow** | `FlowInfo.complexity_score` / `complexity_level` (`src/core/models/automation.py`) | Score pondéré linéaire : `total_elements + decisions×3 + boucles×4 + sous-flows×2 + opérations_de_données×2 + profondeur_max×4 + (largeur_max-1)×2 + éléments_non_documentés`. Le score est ensuite classé en 4 niveaux (`Simple` &lt; 20, `Moyen` &lt; 45, `Complexe` &lt; 80, `Très complexe` sinon). |
| 8 | **Scoring de complexité de Validation Rule** | `ValidationRuleInfo.complexity_score` (`src/core/models/metadata.py`) | Heuristique légère : longueur de la formule / 50 + nombre de parenthèses + occurrences de `IF`/`AND`/`OR`/`CASE`. |
| 9 | **Ratio Profils / Permission Sets** (SEC-005) | `security_analyzer.analyze_org_security` | Calcule `profils_custom / permission_sets × 100` et le compare à un seuil configurable (défaut 60 %) pour détecter une gouvernance de sécurité encore centrée "Profile" plutôt que "Permission Set" (anti-pattern). |
| 10 | **Analyse de dépendances / orphelins** | `dependencies_mixin._analyze_dependencies` | Voir §2.4 — scan textuel multi-source (Apex, Flow, LWC, Aura, Report) construisant un ensemble de couples `(cible, type_cible)`, puis marquage orphelin de tout composant custom jamais référencé. |
| 11 | **Scoring No-Code / Low-Code / Pro-Code et Adopt/Adapt** | `CustomizationMetrics` (`src/core/models/metrics.py`) | Modèle de **scoring pondéré linéaire configurable** : chaque type de métadonnée (objets custom, flows, classes Apex, agents IA, OmniScripts, …) a un poids (`DEFAULT_SCORING_WEIGHTS`), multiplié par son nombre d'occurrences, sommé par famille (`score_no_code`, `score_low_code`, `score_pro_code`) puis globalement (`score`). Le score global est ensuite classé en 4 niveaux via des seuils configurables (`DEFAULT_SCORING_THRESHOLDS`). Un second jeu de poids/seuils (`adopt_adapt_*`) produit une classification "Adopt (Standard)" → "Adapt (High Customization)". |

### 3.4 Exemple de règle (extrait de `rules.xml`)

```xml
<rule id="APEX-PERF-001" enabled="true" scope="apex" category="Adaptable"
      subcategory="Performance" severity="Major" source="Best Practice">
  <title>Requête SOQL potentiellement dans une boucle</title>
  <description>Une requête SOQL est exécutée à l'intérieur d'une boucle.</description>
  <rationale>Risque de dépassement des limites Governor (101 requêtes SOQL par transaction).</rationale>
  <remediation>Sortir la requête de la boucle et utiliser une collection (Map/Set) pour bulkifier.</remediation>
</rule>
```

## 4. Exemples de code (Python)

### 4.1 Parsing seul

```python
from pathlib import Path
from src.parsers.salesforce_parser import SalesforceMetadataParser

parser = SalesforceMetadataParser(
    source_dir=Path("C:/orgs/mon-projet-sfdx"),
    exclusion_config_path=Path("exclusion.json"),   # optionnel
    log_callback=print,                              # optionnel
)
snapshot = parser.parse()

print(f"{len(snapshot.objects)} objets, {len(snapshot.apex_artifacts)} artefacts Apex")
print(f"{len(snapshot.orphans)} composants orphelins détectés")
```

### 4.2 Parsing + Analyse statique complète

```python
from pathlib import Path
from src.parsers.salesforce_parser import SalesforceMetadataParser
from src.analyzer.rule_catalog import RuleCatalog
from src.analyzer.engine import AnalyzerEngine

# 1. Parsing
parser = SalesforceMetadataParser(Path("C:/orgs/mon-projet-sfdx"))
snapshot = parser.parse()

# 2. Chargement du catalogue de règles (rules.xml par défaut, ou chemin custom)
catalog = RuleCatalog.load()

# 3. Analyse
engine = AnalyzerEngine(catalog=catalog, exclusion_path=Path("exclusion.json"))
report = engine.analyze_snapshot(snapshot)

# 4. Synthèses
print(report.severity_counts())   # {'Critical': 2, 'Major': 14, 'Minor': 30, 'Info': 5}
print(report.category_counts())   # {'Trusted': ..., 'Easy': ..., 'Adaptable': ...}

for finding in report.all_findings():
    print(f"[{finding.rule.severity}] {finding.rule.id} — {finding.target_name}: {finding.message}")
```

### 4.3 Scoring de personnalisation (No-Code / Low-Code / Pro-Code)

```python
metrics = snapshot.metrics
print(f"Score global: {metrics.score} ({metrics.level})")
print(f"  No-Code : {metrics.score_no_code}")
print(f"  Low-Code: {metrics.score_low_code}")
print(f"  Pro-Code: {metrics.score_pro_code}")
print(f"Posture Adopt/Adapt: {metrics.adopt_adapt_level}")
```

### 4.4 Mode headless (Mode B — sans UI, ex. skill `/assess-org`)

```python
from pathlib import Path
from src.core.orchestrator_headless import HeadlessOrchestrator
from src.analyzer.rule_catalog import RuleCatalog

orchestrator = HeadlessOrchestrator(
    source_path=Path("/tmp/dewey-clone/mon-org"),
    rule_catalog=RuleCatalog.load(),
    exclusions={},          # rule_id -> {noms de métadonnées exemptés}
    scope="apex",           # "all" | "apex" | "flows" | "security" | "omni"
)
result = orchestrator.run()   # AssessmentResult(snapshot, report, scope)

print(result.report.severity_counts())
```

### 4.5 Filtrer les findings d'une seule classe Apex

```python
apex_findings = report.apex.get("AsyncFrameworkConfig", [])
for f in apex_findings:
    print(f.rule.id, f.severity_rank, f.message)
```

## 5. Récapitulatif — comment les deux modules s'articulent

1. `SalesforceMetadataParser(source_dir, exclusion_config_path).parse()` → **`MetadataSnapshot`** (données brutes filtrées des exclusions de métadonnées).
2. `AnalyzerEngine(catalog, exclusion_path).analyze_snapshot(snapshot)` → **`AnalyzerReport`** (findings filtrés des exclusions de règles).
3. Le `MetadataSnapshot` (via `snapshot.metrics`) porte aussi le **scoring de personnalisation** (No-Code/Low-Code/Pro-Code, Adopt/Adapt), calculé au moment du parsing car il dépend uniquement des comptages, pas des règles de qualité.
4. Ni le parsing ni l'analyse n'écrivent de fichier de rapport : c'est `src/reporting/` (Mode A) ou `src/core/sf_findings_service.py` (Mode B) qui consomme `MetadataSnapshot` + `AnalyzerReport` pour produire la sortie finale.

---

# 🇬🇧 Part 2 — English

## 1. Overview

Dewey analyzes a Salesforce DX project (`force-app/main/default/...`) in two fully decoupled stages:

```
SFDX source folder
        │
        ▼
┌───────────────────────┐
│   1. PARSING           │   src/parsers/salesforce_parser/
│   XML → dataclasses    │   → produces a MetadataSnapshot
└───────────────────────┘
        │
        ▼
┌───────────────────────┐
│   2. STATIC ANALYSIS   │   src/analyzer/
│   Snapshot → findings  │   → produces an AnalyzerReport
└───────────────────────┘
        │
        ▼
   Reports (HTML/Excel/Word in Mode A, Salesforce Custom Objects in Mode B)
```

- **Parsing** performs no qualitative judgment: it turns XML/Apex/JS into structured Python objects (`MetadataSnapshot`), and applies **metadata exclusions** (components fully ignored).
- **Analysis** takes that `MetadataSnapshot` as input, applies a **declarative rule catalog** (`rules.xml`) and returns an `AnalyzerReport` containing `Finding` objects (rule violations), applying **rule-level exclusions** (a rule disabled for a specific component).

Neither module depends on any UI code (`tkinter`): both can be used from the command line, a script, or the headless mode (`assess.py` / `src/core/orchestrator_headless.py`, "Mode B").

## 2. The Parsing Module

### 2.1 Structure

```
src/parsers/salesforce_parser/
├── parser.py              ← SalesforceMetadataParser class (entry point)
├── base.py                 ← shared state (_ParserState) + CATEGORY_ALIASES
├── exclusion_mixin.py       ← loading + applying metadata exclusions
├── objects_mixin.py         ← SObject parsing (fields, record types, VR, DR...)
├── security_mixin.py        ← Profile / Permission Set parsing
├── apex_mixin.py             ← Apex classes/triggers parsing
├── apex_helpers.py           ← brace-aware SOQL/DML "in loop" detection
├── flows_mixin.py            ← Flow parsing (elements, depth, width)
├── components_mixin.py       ← LWC / Aura parsing
├── inventory_mixin.py         ← generic inventory (all component types)
└── dependencies_mixin.py       ← impact analysis + orphan detection
```

`SalesforceMetadataParser` is composed via **multiple mixin inheritance** (each mixin owns one thematic responsibility). This is a "mixin composition" pattern: each mixin adds private methods (`_parse_objects`, `_parse_apex_folder`, `_parse_flows`, etc.) onto a shared state (`_ParserState`).

### 2.2 Parsing algorithm (`SalesforceMetadataParser.parse()`)

1. **Package root resolution** (`_resolve_package_roots`): reads `sfdx-project.json` → `packageDirectories`, falling back to `force-app/main/default` if absent.
2. For each package root, parsing proceeds **folder by folder** (objects, profiles, permissionsets, classes, triggers, flows, agents, genAiPromptTemplates, sharingRules, duplicateRules, permissionsetgroups, lwc, aura, flexipages, layouts, tabs, applications, omniScripts, omniIntegrationProcedures, omniUiCards, omniDataTransforms, omniProcesses, aiPredictions, decisionMatrices, expressionSets…).
3. Each sub-parser returns typed **dataclasses** (`ObjectInfo`, `ApexArtifact`, `FlowInfo`, `SecurityArtifact`, `LwcInfo`, `AuraInfo`, …) defined in `src/core/models/`.
4. **Exclusion filtering**: after collection, every list (`objects`, `apex_artifacts`, `flows`, `profiles`, `permission_sets`, `agents`, `gen_ai_prompts`, plus inventory counters such as `flexipages`, `tabs`, `omniScripts`…) is filtered through `self._is_excluded(category, *names)`.
5. **Raw metrics computation** (`CustomizationMetrics`): counts (custom objects, custom fields, Apex classes, flows, etc.) used later for the No-Code/Low-Code/Pro-Code scoring.
6. **Dependency analysis and orphan detection** (`_analyze_dependencies`), see §2.4.
7. Returns a single object: `MetadataSnapshot` (see `src/core/models/snapshot.py`), holding everything that was parsed: objects, profiles, permission sets, apex, flows, lwc/aura, agents, AI prompts, sharing/duplicate rules, dependencies, orphans, metrics, inventory.

### 2.3 Metadata exclusion algorithm

File: `exclusion_mixin.py`. Two steps:

**a) Loading (`_load_exclusion_rules`)**
- Reads a JSON file (`exclusion.json`) shaped like:
  ```json
  { "metadata_exclusions": [
      { "type": "apex", "element": "AsyncFrameworkConfig", "commentaire": "" }
  ]}
  ```
- The `type` field is normalized through a **category alias dictionary** (`CATEGORY_ALIASES`, in `base.py`): e.g. `"object"`, `"objet"`, `"sobject"` all map to the internal `object` category. The special `"all"` category applies to **every component type** (useful for generic patterns like `*PEG*`).
- Multi-encoding tolerance (`utf-8`, `utf-16`, `latin-1`) and backward compatibility with a legacy list format (`"Hors analyse": [[category, pattern], ...]`).

**b) Matching (`_is_excluded(category, *names)`)** — a 3-tier *pattern matching* algorithm, applied for **every** pattern in the target category + the `all` category, against **every** candidate name (e.g. both API name and label):
1. Case-insensitive **glob match** via `fnmatch.fnmatch` (supports `*`, `?` wildcards);
2. Case-insensitive **substring match** (`pattern in name`) — allows excluding by a simple keyword without writing a wildcard;
3. **Normalized match**: spaces/underscores stripped from both sides (`_normalize_exclusion_token`), to absorb naming variants (`SF Async` ≈ `SF_Async__c`).

As soon as one of the three conditions is true for a (pattern, name) pair, the component is excluded.

### 2.4 Dependency analysis and orphan detection (`dependencies_mixin.py`)

- **Simplified dependency graph construction** via textual scanning (no full AST): every source artifact (Apex class, trigger, Flow, LWC, Aura, Report) is scanned for known object names, field references (`Object.Field`), and Apex class names. Each match produces a `Dependency(source, target)` edge.
- **Orphan detection**: a component is an orphan candidate if its name **never appears as a target** (`target_name`) of any dependency — i.e. nothing in the org references it. Exception rules apply (triggers are entry points, standard objects are never orphans, test classes are ignored).

## 3. The Static Analysis Module (`src/analyzer/`)

### 3.1 Structure

```
src/analyzer/
├── rules.xml            ← declarative rule catalog (source of truth)
├── rule_catalog.py       ← XML loading → Rule, RuleCatalog
├── models.py              ← Rule / Finding dataclasses
├── engine.py               ← AnalyzerEngine: orchestrator + aggregation (AnalyzerReport)
├── apex_analyzer.py         ← APEX-*, TRIG-* rules
├── flow_analyzer.py          ← FLOW-* rules
├── object_analyzer.py         ← OBJ-*, FIELD-*, VR-*, DR-* rules
├── lwc_analyzer.py             ← LWC-* rules
├── aura_analyzer.py              ← AURA-* rules
├── security_analyzer.py           ← SEC-* rules (Profiles / Permission Sets)
└── omni_analyzer.py                ← rules for OmniStudio Data Transforms
```

### 3.2 The rule catalog (linter-style engine)

Dewey implements a **declarative rule engine** inspired by static linters (PMD, ESLint):
- Each rule is defined in `rules.xml` with a unique id (e.g. `APEX-PERF-001`), a `scope` (apex, flow, object, security…), a `severity` (`Critical`/`Major`/`Minor`/`Info`), a `category` (`Trusted`/`Easy`/`Adaptable`), a title, description, rationale, and remediation.
- `RuleCatalog` loads that XML and exposes accessors (`.enabled`, `.get(id)`, `.for_scope(scope)`).
- Each analysis function (`analyze_apex_artifact`, `analyze_flow`, `analyze_object`, …) is a sequence of **independent checks**: it fetches the rule by id, verifies it is enabled, evaluates a business condition on the artifact, and emits a `Finding` (with a message, details, and an optional line number).
- `AnalyzerEngine` orchestrates calling all of these functions across a full `MetadataSnapshot` (`analyze_snapshot`), aggregates results per artifact type into an `AnalyzerReport`, and exposes summaries: `severity_counts()`, `rule_counts()`, `category_counts()`.
- A **second exclusion layer** exists here too: `AnalyzerEngine` loads a separate JSON file (`rule_exclusions`) mapping a `rule_id` to a set of metadata names exempted from that specific rule (`_is_rule_applicable`), on top of a min/max API-version filter (`min_api_version` / `max_api_version` declared on the rule).

### 3.3 Notable analysis algorithms

| # | Name / area | File | Algorithm description |
|---|---|---|---|
| 1 | **Comment/string stripping** | `apex_analyzer._strip_comments_and_strings`, `apex_helpers._strip_apex_comments` | Character-by-character state machine that blanks out `//...`, `/*...*/` and the contents of `'...'`/`"..."` string literals with spaces while preserving line breaks. Mandatory preprocessing step before any regex search, to avoid false positives (e.g. an SQL keyword quoted inside a comment). |
| 2 | **Brace-aware SOQL/DML "in loop" detection** | `apex_helpers._detect_pattern_in_loop` | Locates each loop (`for`/`while`/`do`), precisely extracts its body by **counting braces** (nesting depth), then searches for the SOQL pattern (`[SELECT ...]`, `Database.query(`) or DML pattern (`insert/update/upsert/delete/undelete/merge`) strictly inside that delimited body — not just "somewhere after the `for` keyword". Deliberately ignores the recommended `for (x : [SELECT ...])` pattern. |
| 3 | **Apex self-recursion detection** (APEX-REL-002) | `apex_analyzer._detect_self_recursive_methods` | Extracts each method body via brace counting (`_extract_method_bodies`), then checks whether the method's own name is called from within its own body. Skipped if the class already contains a recursion-guard hint (`static`, `Set<Id>`, `recursionGuard`, `bypass`, …). |
| 4 | **Trigger after-save recursion detection** (TRIG-REL-001) | `apex_analyzer._detect_trigger_after_save_recursion` | Parses the trigger declaration (`trigger X on Y (after insert, ...)`) then uses regex to check whether `Trigger.new`/`Trigger.newMap` (or an alias assigned via `Object x = Trigger.new`) undergoes a direct DML — the classic infinite-loop signature. |
| 5 | **Dynamic SOQL injection detection** (APEX-SEC-003) | `apex_analyzer._detect_soql_injection` | Finds `Database.query(...)` calls, inspects the argument for string concatenation (`+`) or interpolation (`$`) without `escapeSingleQuotes` or a bind variable (`:`) → flagged as an injection risk. |
| 6 | **Apex class call-cycle detection** (APEX-REL-003) | `engine._detect_apex_call_cycles` + `engine._find_cycles` | Builds a **call graph** `{Class → {mentioned Classes}}` from PascalCase identifiers found in the code (after comment/string stripping), then applies **Tarjan's algorithm** to extract strongly connected components (SCCs). Any component of size ≥ 2, or any self-loop, is reported as a circular dependency cycle between classes. |
| 7 | **Flow complexity scoring** | `FlowInfo.complexity_score` / `complexity_level` (`src/core/models/automation.py`) | Weighted linear score: `total_elements + decisions×3 + loops×4 + subflows×2 + data_operations×2 + max_depth×4 + (max_width-1)×2 + undocumented_elements`. The score is then bucketed into 4 levels (`Simple` &lt; 20, `Moyen` &lt; 45, `Complexe` &lt; 80, `Très complexe` otherwise). |
| 8 | **Validation Rule complexity scoring** | `ValidationRuleInfo.complexity_score` (`src/core/models/metadata.py`) | Lightweight heuristic: formula length / 50 + number of parentheses + occurrences of `IF`/`AND`/`OR`/`CASE`. |
| 9 | **Profiles / Permission Sets ratio** (SEC-005) | `security_analyzer.analyze_org_security` | Computes `custom_profiles / permission_sets × 100` and compares it against a configurable threshold (default 60%) to detect security governance still centered on "Profile" rather than "Permission Set" (anti-pattern). |
| 10 | **Dependency / orphan analysis** | `dependencies_mixin._analyze_dependencies` | See §2.4 — multi-source textual scan (Apex, Flow, LWC, Aura, Report) building a set of `(target, target_kind)` pairs, then flagging as orphan any custom component that is never referenced. |
| 11 | **No-Code / Low-Code / Pro-Code and Adopt/Adapt scoring** | `CustomizationMetrics` (`src/core/models/metrics.py`) | A **configurable weighted linear scoring model**: every metadata type (custom objects, flows, Apex classes, AI agents, OmniScripts, …) has a weight (`DEFAULT_SCORING_WEIGHTS`), multiplied by its occurrence count, summed per family (`score_no_code`, `score_low_code`, `score_pro_code`) and overall (`score`). The overall score is then bucketed into 4 levels via configurable thresholds (`DEFAULT_SCORING_THRESHOLDS`). A second set of weights/thresholds (`adopt_adapt_*`) produces an "Adopt (Standard)" → "Adapt (High Customization)" classification. |

### 3.4 Rule example (excerpt from `rules.xml`)

```xml
<rule id="APEX-PERF-001" enabled="true" scope="apex" category="Adaptable"
      subcategory="Performance" severity="Major" source="Best Practice">
  <title>SOQL query potentially inside a loop</title>
  <description>A SOQL query is executed inside a loop.</description>
  <rationale>Risk of exceeding Governor Limits (101 SOQL queries per transaction).</rationale>
  <remediation>Move the query out of the loop and use a collection (Map/Set) to bulkify.</remediation>
</rule>
```

## 4. Code Examples (Python)

### 4.1 Parsing only

```python
from pathlib import Path
from src.parsers.salesforce_parser import SalesforceMetadataParser

parser = SalesforceMetadataParser(
    source_dir=Path("C:/orgs/my-sfdx-project"),
    exclusion_config_path=Path("exclusion.json"),   # optional
    log_callback=print,                              # optional
)
snapshot = parser.parse()

print(f"{len(snapshot.objects)} objects, {len(snapshot.apex_artifacts)} Apex artifacts")
print(f"{len(snapshot.orphans)} orphan components detected")
```

### 4.2 Parsing + full static analysis

```python
from pathlib import Path
from src.parsers.salesforce_parser import SalesforceMetadataParser
from src.analyzer.rule_catalog import RuleCatalog
from src.analyzer.engine import AnalyzerEngine

# 1. Parsing
parser = SalesforceMetadataParser(Path("C:/orgs/my-sfdx-project"))
snapshot = parser.parse()

# 2. Load the rule catalog (default rules.xml, or a custom path)
catalog = RuleCatalog.load()

# 3. Analysis
engine = AnalyzerEngine(catalog=catalog, exclusion_path=Path("exclusion.json"))
report = engine.analyze_snapshot(snapshot)

# 4. Summaries
print(report.severity_counts())   # {'Critical': 2, 'Major': 14, 'Minor': 30, 'Info': 5}
print(report.category_counts())   # {'Trusted': ..., 'Easy': ..., 'Adaptable': ...}

for finding in report.all_findings():
    print(f"[{finding.rule.severity}] {finding.rule.id} — {finding.target_name}: {finding.message}")
```

### 4.3 Customization scoring (No-Code / Low-Code / Pro-Code)

```python
metrics = snapshot.metrics
print(f"Overall score: {metrics.score} ({metrics.level})")
print(f"  No-Code : {metrics.score_no_code}")
print(f"  Low-Code: {metrics.score_low_code}")
print(f"  Pro-Code: {metrics.score_pro_code}")
print(f"Adopt/Adapt posture: {metrics.adopt_adapt_level}")
```

### 4.4 Headless mode (Mode B — no UI, e.g. `/assess-org` skill)

```python
from pathlib import Path
from src.core.orchestrator_headless import HeadlessOrchestrator
from src.analyzer.rule_catalog import RuleCatalog

orchestrator = HeadlessOrchestrator(
    source_path=Path("/tmp/dewey-clone/my-org"),
    rule_catalog=RuleCatalog.load(),
    exclusions={},          # rule_id -> {exempted metadata names}
    scope="apex",           # "all" | "apex" | "flows" | "security" | "omni"
)
result = orchestrator.run()   # AssessmentResult(snapshot, report, scope)

print(result.report.severity_counts())
```

### 4.5 Filtering findings for a single Apex class

```python
apex_findings = report.apex.get("AsyncFrameworkConfig", [])
for f in apex_findings:
    print(f.rule.id, f.severity_rank, f.message)
```

## 5. Summary — how the two modules fit together

1. `SalesforceMetadataParser(source_dir, exclusion_config_path).parse()` → **`MetadataSnapshot`** (raw data, already filtered by metadata exclusions).
2. `AnalyzerEngine(catalog, exclusion_path).analyze_snapshot(snapshot)` → **`AnalyzerReport`** (findings filtered by rule-level exclusions).
3. The `MetadataSnapshot` (via `snapshot.metrics`) also carries the **customization scoring** (No-Code/Low-Code/Pro-Code, Adopt/Adapt), computed at parse time since it only depends on raw counts, not on quality rules.
4. Neither parsing nor analysis writes any report file: it is `src/reporting/` (Mode A) or `src/core/sf_findings_service.py` (Mode B) that consumes `MetadataSnapshot` + `AnalyzerReport` to produce the final output.
