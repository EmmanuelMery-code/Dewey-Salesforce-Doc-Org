"""
SfcaService — Mode B
Runs Salesforce Code Analyzer (sf code-analyzer run, or sf scanner run for v4)
and returns violations as PmdViolation objects.

SFCA v5 output (sf code-analyzer run --format json):
  { "violations": [ { "engine": "...", "fileName": "...", "ruleName": "...",
                       "severity": 1, "message": "...", "codeLocations": [...] } ] }

SFCA v4 output (sf scanner run --format json):
  [ { "engine": "...", "fileName": "...",
      "violations": [ { "ruleName": "...", "severity": 1,
                        "normalizedSeverity": 1, "line": 42, "message": "..." } ] } ]

sf code-analyzer / sf scanner exit with code 1 when violations are found — this is normal.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Callable

from src.core.models import PmdViolation

LogCallback = Callable[[str], None]


class SfcaService:
    """
    Runs sf code-analyzer (SFCA v5) or sf scanner (SFCA v4 fallback) against the
    workspace and returns violations as PmdViolation objects.

    Parameters
    ----------
    workspace_dir : Path
        Root of the Salesforce DX project to scan.
    log_callback : callable, optional
        Receives log strings for display.
    """

    def __init__(
        self, workspace_dir: str | Path, log_callback: LogCallback | None = None
    ) -> None:
        self.workspace_dir = Path(workspace_dir).resolve()
        self.log: LogCallback = log_callback or (lambda msg: None)

    # ── Public API ─────────────────────────────────────────────────────────────

    def analyze(self) -> list[PmdViolation]:
        """
        Runs sf code-analyzer run (v5) or falls back to sf scanner run (v4)
        on the full workspace directory.
        Returns a (possibly empty) list of PmdViolation objects.
        """
        if not shutil.which("sf"):
            self.log("sf CLI non détecté — analyse SFCA ignorée.")
            return []

        self._ensure_java_in_path()

        # Try v5 first, fall back to v4
        cmd_v5 = self._build_cmd_v5()
        cmd_v4 = self._build_cmd_v4()

        for cmd_fn, version in ((self._build_cmd_v5, "v5"), (self._build_cmd_v4, "v4")):
            # Quick availability check
            check = subprocess.run(
                cmd_fn()[:2] + ["--help"],
                capture_output=True, text=True,
            )
            if check.returncode != 0:
                continue

            self.log(f"SFCA {version} : scan de {self.workspace_dir.name}…")
            try:
                output, err, rc = self._run(cmd_fn, version)
            except Exception as exc:
                self.log(f"SFCA {version} : exception — {exc}")
                return []

            if output is None:
                if err and ("Java" in err or "java" in err):
                    self.log(f"SFCA {version} : Java introuvable — {err[:200]}")
                elif rc not in (0, 1):
                    self.log(f"SFCA {version} : erreur (code {rc}) — {(err or '')[:300]}")
                else:
                    self.log(f"SFCA {version} : aucune violation détectée.")
                return []

            violations = self._parse(output, version)
            self.log(f"SFCA {version} : {len(violations)} violation(s) détectée(s).")
            return violations

        self.log("SFCA : ni sf code-analyzer ni sf scanner disponibles — analyse ignorée.")
        self.log("  Installez avec : sf plugins install @salesforce/code-analyzer-sf-plugin")
        return []

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _ensure_java_in_path(self) -> None:
        """Prepend Homebrew OpenJDK to PATH if a real JVM is not available."""
        java = shutil.which("java")
        if java:
            r = subprocess.run([java, "-version"], capture_output=True, text=True)
            if "version" in r.stderr.lower() or "version" in r.stdout.lower():
                return
        for candidate in (
            "/opt/homebrew/opt/openjdk/bin",
            "/usr/local/opt/openjdk/bin",
        ):
            if Path(candidate).is_dir():
                os.environ["PATH"] = candidate + os.pathsep + os.environ.get("PATH", "")
                return

    def _run(self, cmd_fn, version: str):
        """
        Runs the analyzer command and returns (output_str | None, stderr_str, returncode).
        v5 writes results to a temp JSON file; v4 writes to stdout.
        """
        if version == "v5":
            with tempfile.NamedTemporaryFile(
                suffix=".json", delete=False, dir=self.workspace_dir
            ) as tmp:
                tmp_path = Path(tmp.name)
            try:
                cmd = cmd_fn(output_file=tmp_path)
                completed = subprocess.run(
                    cmd, cwd=self.workspace_dir,
                    capture_output=True, text=True, encoding="utf-8", errors="replace",
                )
                # rc 0 = no violations, rc 1 = violations found, rc 2+ = error
                if completed.returncode >= 2:
                    return None, completed.stderr, completed.returncode
                if tmp_path.exists() and tmp_path.stat().st_size > 2:
                    output = tmp_path.read_text(encoding="utf-8", errors="replace").strip()
                    return (output or None), completed.stderr, completed.returncode
                return None, completed.stderr, completed.returncode
            finally:
                tmp_path.unlink(missing_ok=True)
        else:
            cmd = cmd_fn()
            completed = subprocess.run(
                cmd, cwd=self.workspace_dir,
                capture_output=True, text=True, encoding="utf-8", errors="replace",
            )
            output = (completed.stdout or "").strip()
            return (output or None), completed.stderr, completed.returncode

    def _build_cmd_v5(self, output_file: Path | None = None) -> list[str]:
        cmd = [
            "sf", "code-analyzer", "run",
            "--target", ".",
            # Limit to engines relevant for org governance: PMD, Graph Engine (FLS/SOQL),
            # and ESLint (LWC). Excludes retire-js, cpd, regex which are less relevant.
            "--rule-selector", "pmd",
            "--rule-selector", "sfge",
            "--rule-selector", "eslint",
        ]
        if output_file:
            cmd += ["--output-file", str(output_file)]
        return cmd

    def _build_cmd_v4(self) -> list[str]:
        return [
            "sf", "scanner", "run",
            "--target", ".",
            "--format", "json",
            "--normalize-severity",
        ]

    # ── Parsing ────────────────────────────────────────────────────────────────

    def _parse(self, output: str, version: str) -> list[PmdViolation]:
        """Dispatches to the appropriate parser based on SFCA version."""
        # Strip any non-JSON prefix lines (progress / warning output)
        for start_char in ("[", "{"):
            start = output.find(start_char)
            if start >= 0:
                try:
                    payload = json.loads(output[start:])
                    if version == "v5" and isinstance(payload, dict):
                        return self._parse_v5(payload)
                    if isinstance(payload, list):
                        return self._parse_v4(payload)
                except json.JSONDecodeError:
                    continue
        return []

    def _parse_v5(self, payload: dict) -> list[PmdViolation]:
        """
        Parses SFCA v5 output.
        Format: { "violations": [ { "rule": "...", "engine": "...", "severity": 1,
                   "locations": [ { "file": "relative/path.cls", "startLine": 42 } ],
                   "primaryLocationIndex": 0, "message": "..." } ] }
        File paths in locations are relative to workspace_dir.
        """
        violations: list[PmdViolation] = []
        for v in payload.get("violations", []):
            rule_name = str(v.get("rule") or v.get("ruleName") or "")
            if not rule_name:
                continue
            locations = v.get("locations") or []
            primary_idx = int(v.get("primaryLocationIndex") or 0)
            loc = locations[primary_idx] if primary_idx < len(locations) else (locations[0] if locations else {})
            rel_path = str(loc.get("file") or "")
            file_path = (self.workspace_dir / rel_path) if rel_path else Path(rel_path)
            violations.append(
                PmdViolation(
                    file_path=file_path,
                    rule=rule_name,
                    ruleset=str(v.get("engine") or ""),
                    priority=str(v.get("severity") or ""),
                    begin_line=int(loc.get("startLine") or 0),
                    end_line=int(loc.get("endLine") or 0),
                    message=str(v.get("message") or ""),
                )
            )
        return violations

    def _parse_v4(self, payload: list) -> list[PmdViolation]:
        """Parses SFCA v4 per-file violations list."""
        violations: list[PmdViolation] = []
        for entry in payload:
            file_name = entry.get("fileName", "")
            engine = entry.get("engine", "")
            for v in entry.get("violations", []):
                rule_name = str(v.get("ruleName") or "")
                if not rule_name:
                    continue
                violations.append(
                    PmdViolation(
                        file_path=Path(file_name),
                        rule=rule_name,
                        ruleset=engine,
                        priority=str(
                            v.get("normalizedSeverity") or v.get("severity") or ""
                        ),
                        begin_line=int(v.get("line") or 0),
                        end_line=int(v.get("endLine") or 0),
                        message=str(v.get("message") or ""),
                    )
                )
        return violations
