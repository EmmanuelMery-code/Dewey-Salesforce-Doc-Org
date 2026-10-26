"""SOQL query, Apex/Flow test-coverage and local test-run helpers for
:class:`SalesforceCliService`.
"""

from __future__ import annotations

import re
import time


def _as_count(value: object) -> int:
    """Coerce a Tooling API count, including JSON null, to an int."""
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _related_name(record: dict, key: str) -> str:
    """Name of a relationship field. A null relationship must not raise."""
    related = record.get(key) or {}
    if not isinstance(related, dict):
        return ""
    return str(related.get("Name") or "")


class _QueryMixin:
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
                records = payload.get("records", []) or []
                if payload.get("done") is False:
                    self._emit_log(
                        f"[AVERTISSEMENT] La requete SOQL ({object_name}) est tronquee "
                        f"({len(records)} lignes, done=false). Le resultat est incomplet."
                    )
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
                    # A deleted class leaves ApexClassOrTrigger null, and the line
                    # counts can be JSON null. Either used to raise here and abort
                    # the Flow coverage that follows.
                    name = _related_name(record, "ApexClassOrTrigger")
                    covered = _as_count(record.get("NumLinesCovered"))
                    uncovered = _as_count(record.get("NumLinesUncovered"))
                    total = covered + uncovered
                    pct = (covered / total) * 100 if total > 0 else 0.0
                    self._emit_log(
                        f"  {idx}. {name or '(sans nom)'}: {covered}/{total} lignes couvertes ({pct:.1f}%)"
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
        except Exception as exc:
            self._emit_log(
                f"Avertissement : impossible de recuperer la couverture Apex : {exc}"
            )

        try:
            self._collect_flow_coverage(target_org, coverage_data)
        except Exception as exc:
            self._emit_log(
                f"Avertissement : impossible de recuperer la couverture des flows : {exc}"
            )
        self._emit_log(f"[RESUME] Couverture enregistree pour {len(coverage_data)} composant(s).")
        return coverage_data

    def _collect_flow_coverage(self, target_org: str, coverage_data: dict[str, dict]) -> None:
        """Fill ``coverage_data`` with one entry per flow that has test coverage.

        ``FlowTestCoverage`` has one row per test class. The bloc total is the
        same on every row, but the first row seen can be 0/0, so the total kept
        is the largest sum. Covered blocs are the distinct element names; an
        element still counts when its test class name cannot be resolved.
        """
        flow_query = (
            "SELECT Id, ApexTestClassId, FlowVersion.Definition.DeveloperName, "
            "NumElementsCovered, NumElementsNotCovered FROM FlowTestCoverage"
        )
        self._emit_log(f"[FLOW] Requete SOQL: {flow_query}")
        flow_records = self.run_query(flow_query, target_org, use_tooling_api=True)
        self._emit_log(
            f"[FLOW] Recupere {len(flow_records)} enregistrement(s) de couverture Flow."
        )

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

        cov_id_to_flow: dict[str, str] = {}
        cov_id_to_class: dict[str, str] = {}

        for record in flow_records:
            fv = record.get("FlowVersion") or {}
            defn = fv.get("Definition") or {} if isinstance(fv, dict) else {}
            flow_name = ""
            if isinstance(defn, dict):
                flow_name = defn.get("DeveloperName") or ""
            if isinstance(fv, dict):
                flow_name = flow_name or fv.get("DeveloperName") or fv.get("FullName") or ""
            apex_class = class_id_to_name.get(record.get("ApexTestClassId"))
            cov_id = record.get("Id")
            covered = _as_count(record.get("NumElementsCovered"))
            uncovered = _as_count(record.get("NumElementsNotCovered"))
            total = covered + uncovered

            if flow_name and cov_id:
                cov_id_to_flow[cov_id] = flow_name
            if apex_class and cov_id:
                cov_id_to_class[cov_id] = apex_class
            if not flow_name:
                continue

            existing = coverage_data.get(flow_name)
            if existing is not None and "_covered_set" not in existing:
                continue
            if existing is None:
                coverage_data[flow_name] = {
                    "percentage": 0.0,
                    "elements_covered": 0,
                    "elements_uncovered": total,
                    "elements_total": total,
                    "element_details": {},
                    "_covered_set": set(),
                    "_max_covered": covered,
                }
                continue
            if total > existing["elements_total"]:
                existing["elements_total"] = total
            existing["_max_covered"] = max(existing.get("_max_covered", 0), covered)

        flow_names_found = set(cov_id_to_flow.values())
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

        elem_query = (
            "SELECT FlowVersionId, ElementName, FlowTestCoverageId "
            "FROM FlowElementTestCoverage"
        )
        self._emit_log(f"[FLOW-ELEM] Requete SOQL: {elem_query}")
        elem_records = self.run_query(elem_query, target_org, use_tooling_api=True)
        self._emit_log(
            f"[FLOW-ELEM] Recupere {len(elem_records)} enregistrement(s) d'elements Flow."
        )

        coverage_keys_lower = {k.lower(): k for k in coverage_data}
        for record in elem_records:
            cov_id = record.get("FlowTestCoverageId")
            elem_name = record.get("ElementName")
            flow_name = cov_id_to_flow.get(cov_id) if cov_id else None
            test_class = cov_id_to_class.get(cov_id) if cov_id else None
            if not (flow_name and elem_name):
                continue

            canonical_key = coverage_keys_lower.get(flow_name.lower())
            if canonical_key is None or "_covered_set" not in coverage_data.get(canonical_key, {}):
                coverage_data[flow_name] = {
                    "percentage": 0.0,
                    "elements_covered": 0,
                    "elements_uncovered": 0,
                    "elements_total": 0,
                    "element_details": {},
                    "_covered_set": set(),
                    "_max_covered": 0,
                }
                canonical_key = flow_name
                coverage_keys_lower[flow_name.lower()] = flow_name

            data = coverage_data[canonical_key]
            elem_key = elem_name.lower()
            data["_covered_set"].add(elem_key)
            if not test_class:
                continue
            details = data.setdefault("element_details", {})
            if elem_key not in details:
                details[elem_key] = []
            if test_class not in details[elem_key]:
                details[elem_key].append(test_class)

        for flow_name, data in coverage_data.items():
            if "_covered_set" not in data:
                continue
            covered_set = data.pop("_covered_set", set())
            max_covered = data.pop("_max_covered", 0)
            distinct_covered = len(covered_set) or max_covered
            total = data["elements_total"]
            if distinct_covered > total:
                total = distinct_covered
                data["elements_total"] = total
            data["elements_covered"] = distinct_covered
            data["elements_uncovered"] = max(0, total - distinct_covered)
            data["percentage"] = (distinct_covered / total * 100) if total > 0 else 0.0
            self._emit_log(
                f"[FLOW] {flow_name}: {distinct_covered}/{total} blocs couverts ({data['percentage']:.1f}%)"
            )

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
