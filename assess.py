"""
assess.py — Mode B entry point
Runs a headless Dewey assessment and pushes results to a Salesforce org.

Usage:
    python assess.py --org ag2rPoc --source /path/to/sfdx-project [--scope all]
    python assess.py --org ag2rPoc --source https://github.com/... --branch main
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


# ── CLI ────────────────────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Dewey Mode B — headless org assessment")
    p.add_argument("--org",    default="ag2rPoc",  help="SF org alias (default: ag2rPoc)")
    p.add_argument("--source", required=True,       help="Local SFDX path or GitHub URL")
    p.add_argument("--branch",  default=None, help="Branch (remote: to clone; local: auto-detected from git)")
    p.add_argument("--project", default=None, help="Stable project identifier for finding deduplication across runs (e.g. 'xRM'). Defaults to source name if omitted.")
    p.add_argument("--version", default=None, help="Optional version label for this run (e.g. 26.2, 26.2.3). Stored in Analysis record. Left blank if not provided.")
    p.add_argument(
        "--scope",
        default="all",
        choices=["all", "apex", "flows", "security", "omni"],
        help="Analysis scope (default: all)",
    )
    p.add_argument(
        "--pmd-ruleset",
        default=None,
        metavar="PATH",
        help="Path to a PMD ruleset XML file (requires --analyzer pmd or auto-selected when provided).",
    )
    p.add_argument(
        "--analyzer",
        default=None,
        choices=["pmd", "sfca", "none"],
        help=(
            "Static analyzer to use: 'pmd' (PMD, requires --pmd-ruleset), "
            "'sfca' (Salesforce Code Analyzer — Apex + LWC + Aura), "
            "'none' (skip static analysis). "
            "Defaults to 'pmd' when --pmd-ruleset is provided, 'none' otherwise."
        ),
    )
    return p.parse_args()


# ── Helpers ────────────────────────────────────────────────────────────────────

def _is_remote(source: str) -> bool:
    return source.startswith("http://") or source.startswith("https://") or source.startswith("git@")


def _git_project_name(path: Path) -> str:
    """Git project name: from remote URL, or git root folder name, or path name."""
    try:
        r = subprocess.run(
            ["git", "-C", str(path), "remote", "get-url", "origin"],
            capture_output=True, text=True,
        )
        if r.returncode == 0:
            remote = r.stdout.strip().rstrip("/")
            name = remote.split("/")[-1]
            return name.removesuffix(".git")
    except Exception:
        pass
    try:
        r = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "--show-toplevel"],
            capture_output=True, text=True,
        )
        if r.returncode == 0:
            return Path(r.stdout.strip()).name
    except Exception:
        pass
    return path.name


def _git_branch(path: Path) -> str:
    """Active git branch, or 'main' as fallback."""
    try:
        r = subprocess.run(
            ["git", "-C", str(path), "branch", "--show-current"],
            capture_output=True, text=True,
        )
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    except Exception:
        pass
    return "main"


def _project_name_from_url(url: str) -> str:
    """Extract project name from a remote git URL."""
    name = url.rstrip("/").split("/")[-1]
    return name.removesuffix(".git")


def _clone(url: str, branch: str, org_alias: str) -> Path:
    import time
    tmp = Path(tempfile.mkdtemp(prefix=f"dewey-{org_alias}-{int(time.time())}-"))
    print(f"  Cloning {url} (branch: {branch}) → {tmp}")
    subprocess.run(
        ["git", "clone", "--branch", branch, "--depth", "1", url, str(tmp)],
        check=True,
    )
    return tmp


def _top_findings(report, n: int = 5) -> list:
    """Returns up to n findings sorted by severity (Critical first)."""
    severity_order = {"Critical": 0, "Major": 1, "Minor": 2, "Info": 3}
    all_findings: list = []
    for section in (report.apex, report.flows, report.objects,
                    report.validation_rules, report.lwc, report.security,
                    report.data_transforms, report.agents, report.prompts):
        for findings in section.values():
            all_findings.extend(findings)
    all_findings.sort(key=lambda f: severity_order.get(f.rule.severity, 9))
    return all_findings[:n]


def _print_summary(analysis_id: str, report, delta_summary: str | None) -> None:
    counts = report.severity_counts()
    total = sum(counts.values())
    print("\n" + "═" * 60)
    print("  DEWEY ASSESSMENT — RESULTS")
    print("═" * 60)
    print(f"  Analysis ID : {analysis_id}")
    print(f"  Findings    : {total} total")
    print(f"    Critical  : {counts.get('Critical', 0)}")
    print(f"    Major     : {counts.get('Major', 0)}")
    print(f"    Minor     : {counts.get('Minor', 0)}")
    print(f"    Info      : {counts.get('Info', 0)}")
    if delta_summary:
        print(f"  Delta       : {delta_summary}")
    print()
    top = _top_findings(report)
    if top:
        print("  Top findings:")
        for f in top:
            comp = getattr(f, "component_name", "") or ""
            print(f"    [{f.rule.severity:8}] {f.rule.id} — {comp}")
    print("═" * 60 + "\n")


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    args = _parse_args()

    # ── Step 1 : load config from SF ──────────────────────────────────────────
    print(f"[1/5] Loading config from {args.org}…")
    from src.core.sf_config_service import SfConfigService
    cfg_svc = SfConfigService(args.org)
    catalog    = cfg_svc.load_rule_catalog()
    config     = cfg_svc.load_config()
    exclusions = cfg_svc.load_exclusions()
    print(f"      {len(catalog.all)} rules, {sum(len(v) for v in exclusions.values())} exclusions")

    # ── Step 2 : resolve source path + detect git identity ────────────────────
    tmp_dir: Path | None = None
    if _is_remote(args.source):
        branch = args.branch or "main"
        print(f"[2/5] Cloning remote source…")
        tmp_dir = _clone(args.source, branch, args.org)
        source_path = tmp_dir
        source_name = _project_name_from_url(args.source)
        source_branch = branch
    else:
        print(f"[2/5] Using local source: {args.source}")
        source_path = Path(args.source).expanduser().resolve()
        if not source_path.exists():
            print(f"ERROR: source path not found: {source_path}", file=sys.stderr)
            sys.exit(1)
        source_name = _git_project_name(source_path)
        source_branch = args.branch or _git_branch(source_path)
    print(f"      Project: {source_name}  Branch: {source_branch}")

    # Detect git root for relative file paths in findings.
    # Falls back to source_path itself so paths are always relative (never absolute).
    source_root: Path = source_path
    try:
        r = subprocess.run(
            ["git", "-C", str(source_path), "rev-parse", "--show-toplevel"],
            capture_output=True, text=True,
        )
        if r.returncode == 0:
            git_root = Path(r.stdout.strip())
            # Only use git root if it is source_path or a parent of it,
            # to avoid a parent repo swallowing the snapshot subdirectory.
            if source_path == git_root or source_path.is_relative_to(git_root):
                source_root = git_root
    except Exception:
        pass

    # ── Step 3 : run assessment ────────────────────────────────────────────────
    # Resolve analyzer mode: explicit --analyzer takes precedence;
    # if --pmd-ruleset is given without --analyzer, default to "pmd".
    analyzer = args.analyzer or ("pmd" if args.pmd_ruleset else "none")
    print(f"[3/5] Running assessment (scope: {args.scope}, analyzer: {analyzer})…")

    pmd_ref_map: dict = {}
    sfca_ref_map: dict = {}
    pmd_path = None

    if analyzer == "pmd":
        if args.pmd_ruleset:
            pmd_path = Path(args.pmd_ruleset).expanduser().resolve()
            if not pmd_path.exists():
                print(f"WARNING: --pmd-ruleset path not found: {pmd_path}", file=sys.stderr)
                pmd_path = None
                analyzer = "none"
            else:
                pmd_ref_map = cfg_svc.load_pmd_ref_map()
                print(f"      PMD ruleset: {pmd_path.name}  ({len(pmd_ref_map)} mapped rules)")
        else:
            print("WARNING: --analyzer pmd requires --pmd-ruleset. Skipping PMD.", file=sys.stderr)
            analyzer = "none"
    elif analyzer == "sfca":
        sfca_ref_map = cfg_svc.load_sfca_ref_map()
        print(f"      SFCA: {len(sfca_ref_map)} mapped rules")

    posture_signal_map = cfg_svc.load_posture_signal_map()
    print(f"      Posture signals: {len(posture_signal_map)} rules with signal")

    from src.core.orchestrator_headless import HeadlessOrchestrator
    orch = HeadlessOrchestrator(
        source_path=source_path,
        rule_catalog=catalog,
        exclusions=exclusions,
        scope=args.scope,
        config=config,
        pmd_ruleset_path=pmd_path,
        pmd_ref_map=pmd_ref_map,
        analyzer=analyzer,
        sfca_ref_map=sfca_ref_map,
    )
    result = orch.run()
    counts = result.report.severity_counts()
    print(f"      {sum(counts.values())} findings detected")

    # ── Step 4 + 5 : push results ─────────────────────────────────────────────
    print(f"[4/5] Pushing results to {args.org}…")
    from src.core.sf_findings_service import SfFindingsService
    svc = SfFindingsService(args.org)
    project = args.project or source_name
    analysis_id, delta_summary = svc.push(
        result=result,
        source=source_name,
        source_branch=source_branch,
        scope=args.scope,
        source_root=source_root,
        project=project,
        posture_signal_map=posture_signal_map,
        version=args.version or "",
    )
    print(f"      Analysis created: {analysis_id}")

    # ── Step 6 : summary ──────────────────────────────────────────────────────
    print("[5/5] Done.")
    _print_summary(analysis_id, result.report, delta_summary)

    # ── Step 7 : cleanup ──────────────────────────────────────────────────────
    if tmp_dir and tmp_dir.exists():
        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
