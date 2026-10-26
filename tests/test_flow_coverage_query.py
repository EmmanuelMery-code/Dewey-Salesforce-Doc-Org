"""Flow test coverage must survive a broken Apex aggregate row.

A null ApexClassOrTrigger or a null line count used to raise at the Apex
total (historically line 94) and skip FlowTestCoverage entirely. The flow
total must also follow the largest row, not the first 0/0 row.
"""

from __future__ import annotations

from src.core.sf_cli_service_query import _QueryMixin


class _FakeQuery(_QueryMixin):
    def __init__(self, responses: dict[str, list[dict]]) -> None:
        self.responses = responses
        self.logs: list[str] = []

    def _emit_log(self, message: str) -> None:
        self.logs.append(message)

    def run_query(self, query: str, target_org: str, use_tooling_api: bool = False, **kwargs):
        if "ApexCodeCoverageAggregate" in query:
            return self.responses.get("apex", [])
        if "FROM FlowTestCoverage" in query:
            return self.responses.get("flows", [])
        if "FROM ApexClass" in query:
            return self.responses.get("classes", [])
        if "FlowElementTestCoverage" in query:
            return self.responses.get("elements", [])
        return []


def test_null_apex_row_does_not_skip_flow_coverage() -> None:
    service = _FakeQuery(
        {
            "apex": [
                {
                    "ApexClassOrTrigger": None,
                    "NumLinesCovered": None,
                    "NumLinesUncovered": None,
                },
                {
                    "ApexClassOrTrigger": {"Name": "AccountService"},
                    "NumLinesCovered": 8,
                    "NumLinesUncovered": 2,
                },
            ],
            "flows": [
                {
                    "Id": "cov0",
                    "ApexTestClassId": "01p000",
                    "FlowVersion": {"Definition": {"DeveloperName": "sfSubmit"}},
                    "NumElementsCovered": 0,
                    "NumElementsNotCovered": 0,
                },
                {
                    "Id": "cov1",
                    "ApexTestClassId": "01p000",
                    "FlowVersion": {"Definition": {"DeveloperName": "sfSubmit"}},
                    "NumElementsCovered": 2,
                    "NumElementsNotCovered": 8,
                },
            ],
            "classes": [],
            "elements": [
                {"FlowTestCoverageId": "cov1", "ElementName": "Decision_1"},
                {"FlowTestCoverageId": "cov1", "ElementName": "Update_1"},
            ],
        }
    )

    coverage = service.fetch_test_coverage("org")

    assert coverage["AccountService"]["percentage"] == 80.0
    flow = coverage["sfSubmit"]
    assert flow["elements_total"] == 10
    assert flow["elements_covered"] == 2
    assert flow["percentage"] == 20.0
    assert flow["element_details"] == {}
