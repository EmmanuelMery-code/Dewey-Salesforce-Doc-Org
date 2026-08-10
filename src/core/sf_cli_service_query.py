"""SOQL query, Apex/Flow test-coverage and local test-run helpers for
:class:`SalesforceCliService`.
"""

from __future__ import annotations

import re
import time


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
