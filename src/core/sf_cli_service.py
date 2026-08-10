"""Salesforce CLI orchestration facade.

Defines :class:`OrgSummary` and :class:`SalesforceCliService`, the latter
composed from sibling mixins that each cover one responsibility area:
org listing/login (``sf_cli_service_orgs``), manifest/retrieve/org-check
(``sf_cli_service_retrieve``), SOQL queries and test coverage
(``sf_cli_service_query``), and low-level CLI process execution
(``sf_cli_service_process``).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from src.core.sf_cli_service_orgs import _OrgMixin
from src.core.sf_cli_service_process import _ProcessMixin
from src.core.sf_cli_service_query import _QueryMixin
from src.core.sf_cli_service_retrieve import _RetrieveMixin

LogCallback = Callable[[str], None]


@dataclass(slots=True)
class OrgSummary:
    alias: str
    username: str
    display_name: str
    instance_url: str
    login_url: str
    org_id: str
    connected_status: str
    is_sandbox: bool
    is_dev_hub: bool
    tracks_source: bool

    @property
    def org_ref(self) -> str:
        return self.alias or self.username

    @property
    def display_label(self) -> str:
        org_type = "Sandbox" if self.is_sandbox else "Org"
        devhub = " / DevHub" if self.is_dev_hub else ""
        alias = self.alias or "(sans alias)"
        return f"{alias} | {self.username} | {org_type}{devhub}"


class SalesforceCliService(_OrgMixin, _RetrieveMixin, _QueryMixin, _ProcessMixin):
    def __init__(
        self, workspace_dir: str | Path, log_callback: LogCallback | None = None
    ) -> None:
        self.workspace_dir = Path(workspace_dir).resolve()
        self.log: LogCallback = log_callback or (lambda message: None)
        self.project_dir = self.workspace_dir / ".sf_cli_project"
        self.sf_executable = self._resolve_sf_executable()
        if not self.sf_executable:
            self._emit_log("Avertissement : Salesforce CLI est introuvable. Les fonctionnalites liees a l'org (retrieve, login, query, etc.) seront indisponibles.")
        self._ensure_project()
        self.command_stats: dict[str, int] = {}

    # ------------------------------------------------------------------ command tracking

    def reset_command_stats(self) -> None:
        """Reset the per-run counters. Call at the start of a generation/pipeline task."""
        self.command_stats = {}

    def get_command_stats(self) -> dict[str, int]:
        """Return a copy of the command counters accumulated since the last reset."""
        return dict(self.command_stats)

    def get_command_stats_total(self) -> int:
        return sum(self.command_stats.values())

    def _track_command(self, label: str) -> None:
        self.command_stats[label] = self.command_stats.get(label, 0) + 1

    def log_command_summary(self) -> None:
        """Emit a formatted summary of the SF CLI commands run since the last reset."""
        total = self.get_command_stats_total()
        sep = "-" * 80
        self._emit_log("")
        self._emit_log(sep)
        self._emit_log(f"COMMANDES SALESFORCE CLI EXECUTEES : {total}")
        self._emit_log(sep)
        if not self.command_stats:
            self._emit_log("Aucune commande Salesforce CLI executee.")
        else:
            for label in sorted(self.command_stats):
                count = self.command_stats[label]
                self._emit_log(f"  {label:<40} {count}")
        self._emit_log(sep)

    def _ensure_project(self) -> None:
        self.project_dir.mkdir(parents=True, exist_ok=True)
        package_dir = self.project_dir / "force-app"
        package_dir.mkdir(parents=True, exist_ok=True)

        project_config = self.project_dir / "sfdx-project.json"
        if not project_config.exists():
            project_config.write_text(
                json.dumps(
                    {
                        "packageDirectories": [{"path": "force-app", "default": True}],
                        "name": "html-doc-generator-cli",
                        "namespace": "",
                        "sfdcLoginUrl": "https://login.salesforce.com",
                        "sourceApiVersion": "65.0",
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
