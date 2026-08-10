"""Delta classification helpers comparing two analysis history entries for Dewey."""

from __future__ import annotations

from src.core.history_service import HistoryEntry


def _classify(old_v, new_v, direction):
    """Return (delta, status) for a metric given its 'good' direction."""
    if old_v is None or new_v is None:
        return None, "neutral"
    delta = new_v - old_v
    if direction == "up_good":
        status = "improvement" if delta > 0 else ("regression" if delta < 0 else "stable")
    elif direction == "down_good":
        status = "improvement" if delta < 0 else ("regression" if delta > 0 else "stable")
    else:
        status = "neutral"
    return delta, status


def _quality_specs(old: HistoryEntry, new: HistoryEntry):
    """Metrics whose degradation is a genuine regression."""
    def ratio(e: HistoryEntry):
        if e.apex_business_classes:
            return e.apex_test_classes / e.apex_business_classes * 100
        return None

    return [
        ("Couverture de tests globale", old.test_coverage, new.test_coverage, "up_good", True, "Majeur"),
        ("Couverture Apex", old.test_coverage_apex, new.test_coverage_apex, "up_good", True, "Majeur"),
        ("Couverture Flows", old.test_coverage_flows, new.test_coverage_flows, "up_good", True, "Mineur"),
        ("Ratio classes de test / métier", ratio(old), ratio(new), "up_good", True, "Mineur"),
        ("Findings critiques", old.findings_critical, new.findings_critical, "down_good", False, "Critique"),
        ("Findings majeurs", old.findings_major, new.findings_major, "down_good", False, "Majeur"),
        ("Findings mineurs", old.findings_minor, new.findings_minor, "down_good", False, "Mineur"),
        ("Findings total", old.findings_total, new.findings_total, "down_good", False, "Mineur"),
    ]
