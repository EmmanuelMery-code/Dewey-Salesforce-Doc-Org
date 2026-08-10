"""Org-listing and web-login helpers for :class:`SalesforceCliService`.

Covers listing connected orgs, interactive web login, and logging out
(removing) an org from the local CLI configuration.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.core.sf_cli_service import OrgSummary


class _OrgMixin:
    def list_orgs(self) -> list[OrgSummary]:
        from src.core.sf_cli_service import OrgSummary

        payload = self._run_json([self.sf_executable, "org", "list", "--json"], label="org list")
        orgs_by_key: dict[tuple[str, str], OrgSummary] = {}

        for section in ("nonScratchOrgs", "sandboxes", "scratchOrgs", "devHubs"):
            for item in payload.get(section, []):
                summary = OrgSummary(
                    alias=item.get("alias") or "",
                    username=item.get("username") or "",
                    display_name=item.get("name") or item.get("instanceName") or "",
                    instance_url=item.get("instanceUrl") or "",
                    login_url=item.get("loginUrl") or "",
                    org_id=item.get("orgId") or "",
                    connected_status=item.get("connectedStatus") or "",
                    is_sandbox=bool(item.get("isSandbox")),
                    is_dev_hub=bool(item.get("isDevHub")),
                    tracks_source=bool(item.get("tracksSource")),
                )
                orgs_by_key[(summary.alias, summary.username)] = summary

        orgs = sorted(
            orgs_by_key.values(),
            key=lambda item: ((item.alias or item.username).lower(), item.username.lower()),
        )
        self._emit_log(f"{len(orgs)} org(s) disponible(s) detectee(s).")
        return orgs

    def login_web(self, alias: str, instance_url: str = "") -> list[OrgSummary]:
        if not alias.strip():
            raise ValueError("Un alias est obligatoire pour la connexion web.")

        command = [self.sf_executable, "org", "login", "web", "--alias", alias.strip()]
        if instance_url.strip():
            command.extend(["--instance-url", instance_url.strip()])

        self._emit_log(f"Ouverture de la connexion web Salesforce pour l'alias `{alias.strip()}`.")
        self._run_streaming(command, label="org login web")
        self._emit_log("Connexion web terminee, actualisation de la liste des orgs.")
        return self.list_orgs()

    def delete_org(
        self,
        target_org: str
    ) -> None:
        command = [
            self.sf_executable,
            "org",
            "logout",
            "--target-org",
            target_org,
            "--no-prompt"
        ]
        self._emit_log(f"Lancement de la suppression (logout) sur `{target_org}`.")
        self._run_streaming(command, cwd=self.workspace_dir, label="org logout")
        self._emit_log(f"Org `{target_org}` retiree avec succes.")
