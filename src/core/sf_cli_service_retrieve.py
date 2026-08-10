"""Manifest generation, metadata retrieve and org-check helpers for
:class:`SalesforceCliService`.
"""

from __future__ import annotations

import json
from pathlib import Path


class _RetrieveMixin:
    def generate_manifest(self, target_org: str, source_dir: str | Path) -> Path:
        source_path = Path(source_dir).resolve()
        source_path.mkdir(parents=True, exist_ok=True)
        manifest_dir = source_path / "manifest"
        manifest_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = manifest_dir / "package.xml"

        command = [
            self.sf_executable,
            "project",
            "generate",
            "manifest",
            "--from-org",
            target_org,
            "--output-dir",
            str(manifest_dir),
        ]
        self._emit_log(f"Generation du manifest pour l'org `{target_org}`.")
        self._run_streaming(
            command,
            label="project generate manifest",
            success_check=lambda: manifest_path.exists(),
        )
        if not manifest_path.exists():
            raise RuntimeError("Le manifest n'a pas ete genere au chemin attendu.")
        self._emit_log(f"Manifest genere: {manifest_path}")
        return manifest_path

    def retrieve_from_org(
        self,
        target_org: str,
        source_dir: str | Path,
        manifest_path: str | Path | None = None,
    ) -> Path:
        source_path = Path(source_dir).resolve()
        source_path.mkdir(parents=True, exist_ok=True)

        effective_manifest = (
            Path(manifest_path).resolve()
            if manifest_path is not None
            else source_path / "manifest" / "package.xml"
        )
        if not effective_manifest.exists():
            raise FileNotFoundError(f"Manifest introuvable: {effective_manifest}")

        project_root = self._ensure_retrieve_project(source_path)
        command = [
            self.sf_executable,
            "project",
            "retrieve",
            "start",
            "--target-org",
            target_org,
            "--manifest",
            str(effective_manifest.relative_to(project_root)),
            "--wait",
            "33",
            "--ignore-conflicts"
        ]
        retrieved_dir = project_root / "force-app" / "main" / "default"
        self._emit_log(f"Debut du retrieve depuis l'org `{target_org}` vers `{source_path}`.")
        self._run_streaming(
            command,
            cwd=project_root,
            label="project retrieve start",
            success_check=lambda: any(retrieved_dir.rglob("*")),
        )
        self._emit_log(f"Retrieve termine dans {source_path}")
        return source_path

    def generate_org_check_excel(
        self,
        check_name: str,
        target_org: str,
        output_file: str | Path,
    ) -> Path:
        output_path = Path(output_file).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        command = [
            self.sf_executable,
            "check",
            check_name,
            "--target-org",
            target_org,
            "--xlsx-file",
            str(output_path),
        ]
        self._emit_log(
            f"Lancement org check `{check_name}` sur `{target_org}` vers `{output_path}`."
        )
        self._run_streaming(command, cwd=self.workspace_dir, label=f"check {check_name}")
        if not output_path.exists():
            raise RuntimeError("Le fichier Excel Org Check n'a pas ete genere au chemin attendu.")
        self._emit_log(f"Org check termine: {output_path}")
        return output_path

    def _ensure_retrieve_project(self, source_path: Path) -> Path:
        source_path.mkdir(parents=True, exist_ok=True)
        package_dir = source_path / "force-app" / "main" / "default"
        package_dir.mkdir(parents=True, exist_ok=True)

        project_config = source_path / "sfdx-project.json"
        if not project_config.exists():
            project_config.write_text(
                json.dumps(
                    {
                        "packageDirectories": [{"path": "force-app", "default": True}],
                        "name": "html-doc-generator-retrieve",
                        "namespace": "",
                        "sfdcLoginUrl": "https://login.salesforce.com",
                        "sourceApiVersion": "65.0",
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
        return source_path
