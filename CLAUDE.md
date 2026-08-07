# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Dewey** is a Salesforce org assessment tool. This repository extends the original Windows desktop tool ([EmmanuelMery-code/Dewey-Salesforce-Doc-Org](https://github.com/EmmanuelMery-code/Dewey-Salesforce-Doc-Org)) with a headless **Mode B** designed to run as a Claude Code skill, storing findings in Salesforce Custom Objects.

Two coexisting modes:
- **Mode A** — Original Windows desktop (Tkinter), triggered via `app.py`, outputs HTML/Excel/Word locally.
- **Mode B** — Headless Claude Code skill (`/assess-org`), config and results in SF Sandbox (`ag2rPoc`).

**Core constraint**: never modify existing Dewey source files. Mode B is an extension only.

---

## Architecture

```
assess.py                            ← Mode B entry point (new)
src/
├── core/
│   ├── sf_config_service.py         ← Load rules via SOQL from DeweyRule__c / DeweyConfig__c / DeweyExclusion__c
│   ├── sf_findings_service.py       ← Push OrgAnalysis__c + Finding__c + AnalysisDelta__c
│   ├── orchestrator_headless.py     ← Wrapper around engine.py without UI callbacks
│   ├── pmd_import_service.py        ← Import PMD ruleset XML → DeweyRule.csv
│   ├── models.py                    ← Shared dataclasses (unchanged)
│   └── customization_metrics.py    ← no/low/pro-code scoring (unchanged)
├── parsers/salesforce_parser.py     ← XML DX parsing (unchanged)
└── analyzer/
    ├── engine.py                    ← Analysis orchestrator (unchanged)
    ├── apex_analyzer.py             ← (unchanged)
    ├── flow_analyzer.py             ← (unchanged)
    ├── lwc_analyzer.py              ← (unchanged)
    ├── security_analyzer.py         ← (unchanged)
    └── rules.xml                    ← Fallback rule source if SF unavailable

dewey-sf-package/                    ← Salesforce Unlocked Package `dewey-sf-assessment`
└── force-app/main/default/
    ├── objects/                     ← 6 custom objects (see Data Model below)
    ├── permissionsets/Dewey_User.permissionset-meta.xml
    ├── reports/                     ← Findings by severity, trend, top components
    └── dashboards/

seed/
├── DeweyRule.csv                    ← Seed rules data
└── DeweyConfig.csv                  ← Seed config data (thresholds, weights)
```

Files under `src/ui/`, `src/reporting/`, `src/ai/`, `src/core/history_service.py`, and `app.py` are Mode A only — do not reference them in Mode B code.

---

## Data Model (Salesforce Custom Objects)

**Configuration objects** (read at skill start):
- `DeweyRule__c` — Rule definitions (`RuleId__c` ExternalId, `Severity__c`, `Category__c`, `IsEnabled__c`, `Message__c`, `Remediation__c`)
- `DeweyConfig__c` — Thresholds and weights (`ConfigKey__c` ExternalId, `ConfigValue__c`)
- `DeweyExclusion__c` — Per-component exclusions with optional `ExpiryDate__c`

**Result objects** (written per run):
- `OrgAnalysis__c` — Run metadata: scores (`ScoreGlobal__c`, `ScoreAdopt__c`, `ScoreAdapt__c`), counts, `Status__c`
- `Finding__c` — Individual findings, linked to `OrgAnalysis__c`, with `IsNew__c` / `IsResolved__c` delta flags
- `AnalysisDelta__c` — Diff between current and previous `OrgAnalysis__c`

---

## `/assess-org` Skill Workflow

```
1. SOQL load: DeweyRule__c + DeweyConfig__c + DeweyExclusion__c from --org
2. If remote source: git clone --branch [branch] --depth 1 [url] /tmp/dewey-[org]-[timestamp]/
3. Run orchestrator_headless.py → parsers → analyzers
4. Fetch last OrgAnalysis__c to compute delta
5. Push OrgAnalysis__c + Finding__c + AnalysisDelta__c
6. Terminal summary: global score, top 5 critical findings, delta vs previous
7. Clean up temp dir if remote clone
```

Parameters: `--org` (default: `ag2rPoc`), `--source` (local path or GitHub URL), `--branch` (default: `main`), `--scope` (`all | apex | flows | security | omni`, default: `all`), `--coverage` (fetch Apex + Flow test coverage via the SF CLI Tooling API and push it to `TestCoveragePct__c`/`CoverageDelta__c`), `--run-tests` (run local Apex tests before `--coverage`)

---

## Salesforce Commands

Deploy the package:
```bash
sf project deploy start -m "CustomObject,PermissionSet" -o ag2rPoc
```

Seed data after first deploy:
```bash
sf data import tree --files seed/DeweyRule.csv -o ag2rPoc
sf data import tree --files seed/DeweyConfig.csv -o ag2rPoc
```

Import rules from an existing PMD ruleset:
```bash
# Generates seed/DeweyRule_pmd.csv from a PMD XML ruleset
python src/core/pmd_import_service.py --ruleset path/to/ruleset.xml
sf data import tree --files seed/DeweyRule_pmd.csv -o ag2rPoc
```

---

## Key Decisions

| Decision | Choice | Reason |
|---|---|---|
| Config storage | Custom Objects (not CMDT) | Admin-editable without deployment; exclusions change frequently |
| Remote source | Shallow git clone to `/tmp/` | Full file access, simple branch handling |
| Trigger | Manual `/assess-org` | Scheduled loop is V2 backlog |
| SF Edition | Unlimited (AG2R) | No license constraints |

See `PLAN.md` for the full architecture reference and backlog.
