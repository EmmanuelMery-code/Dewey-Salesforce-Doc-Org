"""
Dewey — Mode B entry point.
Headless org assessment: analyse a Salesforce DX source, store results in a SF org.

Usage:
    python sf.py --org <sf-cli-alias>
                 [--source <local-path|github-url>]  (default: current directory)
                 [--branch <branch>]                  (default: main, remote only)
                 [--scope all|apex|flows|security|omni] (default: all)

Examples:
    python sf.py --org ag2rPoc
    python sf.py --org ag2rPoc --source ./my-dx-project
    python sf.py --org ag2rPoc --source https://github.com/org/repo --branch develop
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Dewey — headless org assessment stored in Salesforce"
    )
    p.add_argument(
        "--org", required=True,
        help="SF CLI org alias (e.g. ag2rPoc)",
    )
    p.add_argument(
        "--source", default=".",
        help="Local path or GitHub URL to analyse (default: current directory)",
    )
    p.add_argument(
        "--branch", default="main",
        help="Git branch to clone (remote source only, default: main)",
    )
    p.add_argument(
        "--scope", default="all",
        choices=["all", "apex", "flows", "security", "omni"],
        help="Analysis scope (default: all)",
    )
    return p.parse_args()


def _clone_remote(url: str, branch: str, org: str) -> Path:
    import time
    tmp = Path(tempfile.mkdtemp(prefix=f"dewey-{org}-{int(time.time())}-"))
    print(f"  Cloning {url}  (branch: {branch})")
    subprocess.run(
        ["git", "clone", "--branch", branch, "--depth", "1", url, str(tmp)],
        check=True,
    )
    return tmp


def _print_summary(result: object, analysis_id: str, delta_summary: str | None) -> None:
    report = result.report  # type: ignore[attr-defined]
    counts = report.severity_counts()
    score = result.snapshot.metrics.score  # type: ignore[attr-defined]

    sep = "─" * 64
    print()
    print(sep)
    print(f"  Dewey — assessment complete")
    print(f"  DeweyAnalysis__c : {analysis_id}")
    print(sep)
    print(f"  Score global   : {score}")
    print(f"  Critical       : {counts.get('Critical', 0)}")
    print(f"  Major          : {counts.get('Major', 0)}")
    print(f"  Minor          : {counts.get('Minor', 0)}")
    print(f"  Info           : {counts.get('Info', 0)}")
    if delta_summary:
        print(f"  Delta          : {delta_summary}")
    print(sep)

    criticals = [f for f in report.all_findings() if f.rule.severity == "Critical"][:5]
    if criticals:
        print("  Top critical findings :")
        for i, f in enumerate(criticals, 1):
            msg = (f.message or f.rule.description or "")[:72]
            print(f"    {i}. [{f.rule.id}] {f.target_name} — {msg}")
        print(sep)


def main() -> None:
    args = _parse_args()

    from src.core.sf_config_service import SfConfigService
    from src.core.orchestrator_headless import HeadlessOrchestrator
    from src.core.sf_findings_service import SfFindingsService

    # ── Step 0 : resolve source ────────────────────────────────────────────
    source = args.source
    tmp_dir: Path | None = None

    if source.startswith("http"):
        tmp_dir = _clone_remote(source, args.branch, args.org)
        source_path = tmp_dir
    else:
        source_path = Path(source).resolve()
        if not source_path.exists():
            print(f"[ERROR] Source path not found: {source_path}", file=sys.stderr)
            sys.exit(1)

    try:
        # ── Step 1 : load config from Salesforce ───────────────────────────
        print(f"[1/4] Loading config from org: {args.org}")
        config_service = SfConfigService(org_alias=args.org)
        rule_catalog = config_service.load_rule_catalog()
        sf_config = config_service.load_config()
        exclusions = config_service.load_exclusions()
        n_rules = len(rule_catalog.enabled)
        n_excl = sum(len(v) for v in exclusions.values())
        print(f"      {n_rules} rules enabled, {n_excl} exclusion(s) active")

        # ── Step 2 : run analysis ──────────────────────────────────────────
        print(f"[2/4] Analysing: {source_path}")
        orchestrator = HeadlessOrchestrator(
            source_path=source_path,
            rule_catalog=rule_catalog,
            exclusions=exclusions,
            scope=args.scope,
            config=sf_config,
        )
        result = orchestrator.run()
        counts = result.report.severity_counts()
        total = sum(counts.values())
        print(
            f"      {total} finding(s) — "
            f"Critical: {counts.get('Critical', 0)}, "
            f"Major: {counts.get('Major', 0)}, "
            f"Minor: {counts.get('Minor', 0)}, "
            f"Info: {counts.get('Info', 0)}"
        )

        # ── Step 3 : push to Salesforce ────────────────────────────────────
        print(f"[3/4] Pushing results to org: {args.org}")
        findings_service = SfFindingsService(org_alias=args.org)
        analysis_id, delta_summary = findings_service.push(
            result=result,
            org_alias=args.org,
            source_path=str(args.source),
            source_branch=args.branch if source.startswith("http") else "",
            scope=args.scope,
        )
        print(f"      DeweyAnalysis__c: {analysis_id}")

        # ── Step 4 : summary ───────────────────────────────────────────────
        print("[4/4] Done.")
        _print_summary(result, analysis_id, delta_summary)

    except subprocess.CalledProcessError as exc:
        print(f"\n[ERROR] SF CLI command failed: {exc}", file=sys.stderr)
        if exc.stderr:
            print(exc.stderr[:500], file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"\n[ERROR] {exc}", file=sys.stderr)
        raise
    finally:
        if tmp_dir and tmp_dir.exists():
            shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
