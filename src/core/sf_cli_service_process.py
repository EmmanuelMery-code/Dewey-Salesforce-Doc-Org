"""Low-level Salesforce CLI process helpers for :class:`SalesforceCliService`.

Covers resolving the `sf` executable and running subprocess commands
(JSON-returning and streaming), shared by all the other CLI mixins.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Callable


class _ProcessMixin:
    def _resolve_sf_executable(self) -> str:
        for candidate in ("sf", "sf.cmd"):
            resolved = shutil.which(candidate)
            if resolved:
                return resolved

        common_paths = [
            Path(r"C:\Program Files\sf\bin\sf.cmd"),
            Path(r"C:\Program Files\sf\client\bin\sf.cmd"),
            Path.home() / "AppData" / "Local" / "sf" / "client" / "bin" / "sf.cmd",
        ]
        for candidate in common_paths:
            if candidate.exists():
                return str(candidate)

        return ""

    def _emit_log(self, message: str) -> None:
        try:
            self.log(message)
        except UnicodeEncodeError:
            self.log(message.encode("ascii", errors="replace").decode("ascii"))

    def _run_json(self, command: list[str], *, label: str = "sf") -> dict:
        self._track_command(label)
        try:
            completed = subprocess.run(
                command,
                cwd=self.project_dir,
                capture_output=True,
                text=True,
                encoding="utf-8",
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except (FileNotFoundError, OSError) as exc:
            self._emit_log(f"Erreur lors de l'execution de la commande Salesforce CLI : {exc}")
            return {}

        # The sf CLI can exit with a non-zero code purely because it printed a
        # warning to stderr (e.g. "Secrets are now hidden from ..."), even
        # though the command itself succeeded and returned valid JSON with
        # "status": 0. Parse stdout first and trust the JSON payload's own
        # status field; only fall back to the process return code when the
        # output isn't usable JSON.
        stdout = completed.stdout.strip()
        payload: dict | None = None
        if stdout:
            try:
                payload = json.loads(stdout)
            except json.JSONDecodeError:
                payload = None

        if payload is None:
            if completed.returncode != 0:
                raise RuntimeError(completed.stderr.strip() or completed.stdout.strip() or "Commande Salesforce CLI en echec.")
            self._emit_log("Erreur : la sortie de la commande Salesforce CLI n'est pas un JSON valide.")
            return {}

        if payload.get("status", 0) != 0:
            message = payload.get("message") or completed.stderr.strip() or "Commande Salesforce CLI en echec."
            raise RuntimeError(message)

        if completed.returncode != 0:
            warning = completed.stderr.strip()
            if warning:
                self._emit_log(f"Avertissement Salesforce CLI (ignore, commande reussie) : {warning}")

        return payload.get("result", {})

    def _run_streaming(
        self,
        command: list[str],
        cwd: Path | None = None,
        *,
        label: str = "sf",
        success_check: Callable[[], bool] | None = None,
    ) -> None:
        self._track_command(label)
        try:
            process = subprocess.Popen(
                command,
                cwd=(cwd or self.project_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except (FileNotFoundError, OSError) as exc:
            self._emit_log(f"Erreur lors du lancement de la commande Salesforce CLI : {exc}")
            return

        assert process.stdout is not None
        for line in process.stdout:
            stripped = line.rstrip()
            if stripped:
                self._emit_log(stripped)

        return_code = process.wait()
        if return_code != 0:
            # Some sf CLI commands (observed with "project generate manifest"
            # and "project retrieve start") exit with a non-zero code even
            # though the command genuinely succeeded. When the caller can
            # verify success independently (e.g. an expected file/folder was
            # produced), trust that signal over the unreliable exit code.
            if success_check is not None and success_check():
                self._emit_log(
                    f"Avertissement : code de sortie non nul signale par le CLI ({return_code}), "
                    "mais le resultat attendu est present ; poursuite du traitement."
                )
                return
            raise RuntimeError(f"La commande Salesforce CLI a echoue ({return_code}).")
