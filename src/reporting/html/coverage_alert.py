"""Seuil d'alerte sur la couverture de tests des classes Apex."""

from __future__ import annotations


# Pourcentage en dessous duquel une classe Apex est signalee dans les rapports.
COVERAGE_ALERT_THRESHOLD = 75.0


def configure_coverage_alert(threshold: float | None = None) -> None:
    """Met a jour le seuil global d'alerte de couverture."""
    global COVERAGE_ALERT_THRESHOLD
    if threshold is None:
        return
    try:
        value = float(threshold)
    except (TypeError, ValueError):
        return
    COVERAGE_ALERT_THRESHOLD = max(0.0, min(100.0, value))


def coverage_alert_marker(coverage: float | None) -> str:
    """Retourne le pictogramme d'alerte a accoler au nom d'une classe.

    Chaine vide si la couverture est inconnue ou au-dessus du seuil.
    """
    if coverage is None:
        return ""
    try:
        value = float(coverage)
    except (TypeError, ValueError):
        return ""
    if value >= COVERAGE_ALERT_THRESHOLD:
        return ""
    title = (
        f"Couverture de {value:.1f}% inferieure au seuil configure "
        f"de {COVERAGE_ALERT_THRESHOLD:g}%"
    )
    return (
        f" <span class='coverage-alert' title=\"{title}\" "
        "style='color:#dc2626;font-weight:700'>&#9888;</span>"
    )
