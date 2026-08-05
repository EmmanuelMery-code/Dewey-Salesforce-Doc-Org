from __future__ import annotations

import json
import re
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

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


class SalesforceCliService:
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

    def list_orgs(self) -> list[OrgSummary]:
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
        self._run_streaming(command, label="project generate manifest")
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
        self._emit_log(f"Debut du retrieve depuis l'org `{target_org}` vers `{source_path}`.")
        self._run_streaming(command, cwd=project_root, label="project retrieve start")
        self._emit_log(f"Retrieve termine dans {source_path}")
        return source_path
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

    def run_query(
        self,
        query: str,
        target_org: str,
        use_tooling_api: bool = False,
        *,
        max_retries: int = 3,
        retry_delay_seconds: float = 2.0,
    ) -> list[dict]:
        """Run a SOQL query, retrying transient failures up to ``max_retries`` times.

        Failures are logged as warnings; after exhausting the retries, an empty list
        is returned instead of raising, so a single flaky query does not abort the
        whole caller (e.g. test coverage computation).
        """
        command = [
            self.sf_executable,
            "data",
            "query",
            "--query",
            query,
            "--target-org",
            target_org,
            "--json",
        ]
        if use_tooling_api:
            command.append("--use-tooling-api")

        match = re.search(r"\bFROM\s+([A-Za-z0-9_]+)", query, re.IGNORECASE)
        object_name = match.group(1) if match else "?"
        label = f"data query ({object_name})"

        for attempt in range(1, max(1, max_retries) + 1):
            attempt_suffix = f" - tentative {attempt}/{max_retries}" if attempt > 1 else ""
            self._emit_log(
                f"Execution de la requete SOQL sur `{target_org}` (tooling={use_tooling_api}){attempt_suffix}."
            )
            try:
                payload = self._run_json(command, label=label)
                records = payload.get("records", [])
                self._emit_log(f"{len(records)} enregistrement(s) recupere(s).")
                return records
            except Exception as exc:
                if attempt < max_retries:
                    self._emit_log(
                        f"[AVERTISSEMENT] Echec de la requete SOQL ({object_name}), "
                        f"tentative {attempt}/{max_retries} : {exc}. Nouvelle tentative dans "
                        f"{retry_delay_seconds:.0f}s..."
                    )
                    time.sleep(retry_delay_seconds)
                else:
                    self._emit_log(
                        f"[ERREUR] Echec definitif de la requete SOQL ({object_name}) apres "
                        f"{max_retries} tentative(s) : {exc}. La requete est ignoree."
                    )

        return []

    def fetch_test_coverage(self, target_org: str) -> dict[str, dict]:
        """Fetch test coverage for Apex classes and Flows via the Tooling API.

        Shared by the desktop app (:class:`AppGenerationMixin`) and the ``Dewey``
        module (``silent/dewey.py``), so both get identical, minimal-request
        coverage data without duplicating the SOQL/joins logic.
        """
        coverage_data: dict[str, dict] = {}
        try:
            apex_query = (
                "SELECT ApexClassOrTrigger.Name, NumLinesCovered, NumLinesUncovered "
                "FROM ApexCodeCoverageAggregate"
            )
            self._emit_log(f"[APEX] Requete SOQL: {apex_query}")
            apex_records = self.run_query(apex_query, target_org, use_tooling_api=True)
            self._emit_log(
                f"[APEX] Recupere {len(apex_records)} enregistrement(s) de couverture Apex."
            )
            if apex_records:
                self._emit_log("[APEX] Resultats detailles:")
                for idx, record in enumerate(apex_records, 1):
                    name = record.get("ApexClassOrTrigger", {}).get("Name")
                    covered = record.get("NumLinesCovered", 0)
                    uncovered = record.get("NumLinesUncovered", 0)
                    total = covered + uncovered
                    pct = (covered / total) * 100 if total > 0 else 0.0
                    self._emit_log(
                        f"  {idx}. {name}: {covered}/{total} lignes couvertes ({pct:.1f}%)"
                    )
                    if name:
                        coverage_data[name] = {
                            "percentage": pct,
                            "lines_covered": covered,
                            "lines_uncovered": uncovered,
                            "lines_total": total,
                        }
            else:
                self._emit_log("[APEX] AUCUN enregistrement de couverture Apex trouve!")

            # Step 1 — FlowTestCoverage: aggregate coverage + lookup tables for element join
            # Id                 → used as key to join FlowElementTestCoverage.FlowTestCoverageId
            # ApexTestClassId    → resolved to a class name via a separate ApexClass query below
            #                      (ApexTestClass.Name relationship traversal is NOT reliable on
            #                      this object, unlike FlowVersion.Definition.DeveloperName)
            # FlowVersion.Definition.DeveloperName → canonical flow API name
            flow_query = (
                "SELECT Id, ApexTestClassId, FlowVersion.Definition.DeveloperName, "
                "NumElementsCovered, NumElementsNotCovered FROM FlowTestCoverage"
            )
            self._emit_log(f"[FLOW] Requete SOQL: {flow_query}")
            flow_records = self.run_query(flow_query, target_org, use_tooling_api=True)
            self._emit_log(
                f"[FLOW] Recupere {len(flow_records)} enregistrement(s) de couverture Flow."
            )

            # Resolve ApexTestClassId -> class name via a dedicated ApexClass query, only if
            # there is anything to resolve (keeps the number of API calls minimal).
            class_id_to_name: dict[str, str] = {}
            if flow_records:
                class_ids = sorted({
                    record.get("ApexTestClassId")
                    for record in flow_records
                    if record.get("ApexTestClassId")
                })
                if class_ids:
                    ids_literal = ", ".join(f"'{cid}'" for cid in class_ids)
                    class_query = f"SELECT Id, Name FROM ApexClass WHERE Id IN ({ids_literal})"
                    self._emit_log(f"[FLOW] Requete SOQL: {class_query}")
                    class_records = self.run_query(class_query, target_org, use_tooling_api=True)
                    class_id_to_name = {
                        record.get("Id"): record.get("Name")
                        for record in class_records
                        if record.get("Id") and record.get("Name")
                    }

            # Lookup: FlowTestCoverage.Id → flow_name and apex_class_name
            cov_id_to_flow: dict[str, str] = {}
            cov_id_to_class: dict[str, str] = {}

            # For each flow: record elements_total (constant across all test-class records)
            # using the first record seen. Do NOT sum — each record is per test class.
            for record in flow_records:
                fv = record.get("FlowVersion") or {}
                defn = fv.get("Definition") or {}
                flow_name = defn.get("DeveloperName") or fv.get("DeveloperName") or fv.get("FullName")
                apex_class = class_id_to_name.get(record.get("ApexTestClassId"))
                cov_id = record.get("Id")
                covered = record.get("NumElementsCovered") or 0
                uncovered = record.get("NumElementsNotCovered") or 0

                if flow_name and cov_id:
                    cov_id_to_flow[cov_id] = flow_name
                if apex_class and cov_id:
                    cov_id_to_class[cov_id] = apex_class

                if flow_name and flow_name not in coverage_data:
                    # Record the total bloc count from the first record for this flow.
                    # All records for the same flow agree on NumElementsCovered+NumElementsNotCovered.
                    total = covered + uncovered
                    coverage_data[flow_name] = {
                        "percentage": 0.0,       # Recalculated after FlowElementTestCoverage
                        "elements_covered": 0,   # Recalculated after FlowElementTestCoverage
                        "elements_uncovered": total,
                        "elements_total": total,
                        "element_details": {},
                        "_covered_set": set(),   # Temp: distinct element names covered
                    }

            flow_names_found = {k for k in cov_id_to_flow.values()}
            if not flow_records:
                self._emit_log(
                    "[FLOW] AUCUN enregistrement de couverture Flow trouve "
                    "(la requete FlowTestCoverage n'a renvoye aucune ligne)."
                )
            elif not flow_names_found:
                self._emit_log(
                    f"[FLOW] {len(flow_records)} enregistrement(s) recupere(s) mais aucun nom de "
                    "flow n'a pu etre resolu. Premier enregistrement brut : "
                    f"{flow_records[0]}"
                )
            else:
                self._emit_log(
                    f"[FLOW] {len(flow_names_found)} flow(s) distinct(s) identifie(s) dans "
                    "FlowTestCoverage."
                )

            # Step 2 — FlowElementTestCoverage: per-element detail
            # ElementName        → API name of the flow element (matches XML <name> tag)
            # FlowTestCoverageId → join key → flow name + Apex class name
            elem_query = (
                "SELECT FlowVersionId, ElementName, FlowTestCoverageId "
                "FROM FlowElementTestCoverage"
            )
            self._emit_log(f"[FLOW-ELEM] Requete SOQL: {elem_query}")
            elem_records = self.run_query(elem_query, target_org, use_tooling_api=True)
            self._emit_log(
                f"[FLOW-ELEM] Recupere {len(elem_records)} enregistrement(s) d'elements Flow."
            )

            # Case-insensitive index for canonical key resolution
            coverage_keys_lower = {k.lower(): k for k in coverage_data}

            for record in elem_records:
                cov_id = record.get("FlowTestCoverageId")
                elem_name = record.get("ElementName")
                flow_name = cov_id_to_flow.get(cov_id) if cov_id else None
                test_class = cov_id_to_class.get(cov_id) if cov_id else None

                if not (flow_name and elem_name and test_class):
                    continue

                canonical_key = coverage_keys_lower.get(flow_name.lower())
                if canonical_key is None:
                    total = 0
                    coverage_data[flow_name] = {
                        "percentage": 0.0,
                        "elements_covered": 0,
                        "elements_uncovered": 0,
                        "elements_total": total,
                        "element_details": {},
                        "_covered_set": set(),
                    }
                    canonical_key = flow_name
                    coverage_keys_lower[flow_name.lower()] = flow_name

                data = coverage_data[canonical_key]
                elem_key = elem_name.lower()

                # Track distinct covered elements (deduplicates across test classes)
                data["_covered_set"].add(elem_key)

                # Record which test classes cover each element
                details = data.setdefault("element_details", {})
                if elem_key not in details:
                    details[elem_key] = []
                if test_class not in details[elem_key]:
                    details[elem_key].append(test_class)

            # Step 3 — Recalculate aggregate percentages from distinct element counts
            # NOTE: coverage_data also holds Apex entries (keyed by class name, with
            # "lines_*" keys) inserted earlier. Only touch entries created by the Flow
            # queries above, identified by the presence of "_covered_set".
            for flow_name, data in coverage_data.items():
                if "_covered_set" not in data:
                    continue
                covered_set = data.pop("_covered_set", set())
                distinct_covered = len(covered_set)
                total = data["elements_total"]
                data["elements_covered"] = distinct_covered
                data["elements_uncovered"] = max(0, total - distinct_covered)
                data["percentage"] = (distinct_covered / total * 100) if total > 0 else 0.0
                self._emit_log(
                    f"[FLOW] {flow_name}: {distinct_covered}/{total} blocs couverts ({data['percentage']:.1f}%)"
                )

            self._emit_log(f"[RESUME] Couverture enregistree pour {len(coverage_data)} flow(s).")
        except Exception as exc:
            self._emit_log(f"Avertissement : impossible de recuperer la couverture de tests : {exc}")
        return coverage_data

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

        if completed.returncode != 0:
            raise RuntimeError(completed.stderr.strip() or completed.stdout.strip() or "Commande Salesforce CLI en echec.")

        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError:
            self._emit_log("Erreur : la sortie de la commande Salesforce CLI n'est pas un JSON valide.")
            return {}

        if payload.get("status", 0) != 0:
            message = payload.get("message") or completed.stderr.strip() or "Commande Salesforce CLI en echec."
            raise RuntimeError(message)
        return payload.get("result", {})

    def _run_streaming(self, command: list[str], cwd: Path | None = None, *, label: str = "sf") -> None:
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
            raise RuntimeError(f"La commande Salesforce CLI a echoue ({return_code}).")

    def run_apex_tests(self, org_ref: str, wait_minutes: int = 60) -> None:
        """Execute all local Apex tests and stream output to the log.

        Blocks until the test run completes (or ``wait_minutes`` is exceeded).
        Failures are logged as warnings and do not interrupt the caller.
        """
        command = [
            self.sf_executable, "apex", "run", "test",
            "--test-level", "RunLocalTests",
            "--result-format", "human",
            "--wait", str(wait_minutes),
            "--target-org", org_ref,
        ]
        try:
            self._run_streaming(command, label="apex run test")
        except Exception as exc:
            self._emit_log(f"[AVERTISSEMENT] L'execution des tests a echoue ({exc}). L'execution continue.")
