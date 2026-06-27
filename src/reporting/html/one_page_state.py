"""Configuration partagee du graphe One Page."""

from __future__ import annotations


# Profondeur maximale de propagation de l'arbre des relations.
ONE_PAGE_MAX_DEPTH = 3
# Un noeud reference par au moins ce nombre de composants distincts est traite
# comme un "hub" (bruit potentiel) et n'est pas etendu.
ONE_PAGE_HUB_THRESHOLD = 8

# Bornes de securite pour les valeurs configurees par l'utilisateur.
_MIN_MAX_DEPTH = 1
_MAX_MAX_DEPTH = 6
_MIN_HUB_THRESHOLD = 2

# Donnees de contexte alimentees par l'orchestrateur avant la generation HTML.
TEST_NODE_NAMES: set[str] = set()
INACTIVE_FLOW_NAMES: set[str] = set()
NODE_DESCRIPTIONS: dict[str, str] = {}


def configure_one_page(
    max_depth: int | None = None, hub_threshold: int | None = None
) -> None:
    """Met a jour la configuration globale de l'algorithme One Page."""
    global ONE_PAGE_MAX_DEPTH, ONE_PAGE_HUB_THRESHOLD
    if max_depth is not None:
        ONE_PAGE_MAX_DEPTH = max(_MIN_MAX_DEPTH, min(_MAX_MAX_DEPTH, int(max_depth)))
    if hub_threshold is not None:
        ONE_PAGE_HUB_THRESHOLD = max(_MIN_HUB_THRESHOLD, int(hub_threshold))


def set_one_page_test_names(names: set[str] | list[str] | None) -> None:
    """Declare les noms des classes Apex de test pour le graphe One Page."""
    global TEST_NODE_NAMES
    TEST_NODE_NAMES = {n for n in (names or set()) if n}


def set_one_page_inactive_flow_names(names: set[str] | list[str] | None) -> None:
    """Declare les noms des flows non actifs pour le graphe One Page."""
    global INACTIVE_FLOW_NAMES
    INACTIVE_FLOW_NAMES = {n for n in (names or set()) if n}


def set_one_page_node_descriptions(descriptions: dict[str, str] | None) -> None:
    """Declare les descriptions affichees dans les tooltips One Page."""
    global NODE_DESCRIPTIONS
    NODE_DESCRIPTIONS = {
        name: text.strip()
        for name, text in (descriptions or {}).items()
        if name and isinstance(text, str) and text.strip()
    }
