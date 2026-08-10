"""Construction et rendu du graphe "One Page".

L'onglet "One Page" complete l'onglet de relations de premier rang : au lieu de
n'afficher que les voisins directs, il construit l'arbre des relations transitives
(jusqu'a :data:`ONE_PAGE_MAX_DEPTH` rangs) a partir du graphe global de dependances
(``snapshot.dependencies``), puis applique l'algorithme "One Page" qui elague le
bruit afin de garder une vue lisible sur une seule page.

Algorithme "One Page" (elagage du bruit) :

1. Construction d'un graphe oriente a partir des dependances globales, avec une
   adjacence non orientee pour la propagation.
2. Calcul du nombre de references entrantes (in-degree) de chaque noeud afin de
   reperer les "hubs" : composants extremement references (classes utilitaires,
   constantes, objets standards reutilises partout) qui noient le graphe.
3. Parcours en largeur (BFS) depuis le composant central jusqu'a N rangs, SANS
   jamais propager *a travers* un hub :
   - un hub atteint au 1er rang est conserve comme noeud terminal (relation
     directe legitime) mais n'est pas etendu ;
   - un hub atteint au-dela du 1er rang est supprime (bruit).
4. Elagage des feuilles (une passe) : on retire les noeuds de rang >= 2 qui n'ont
   qu'une seule connexion (feuilles faiblement connectees, loin du centre). Une
   seule passe est volontaire : elle supprime les feuilles peripheriques reelles
   sans derouler les chaines transitives legitimes (qui constituent la "relation
   plus large" recherchee).
"""

from __future__ import annotations

from src.core.models import Dependency
from src.reporting.html import one_page_state as state
from src.reporting.html.one_page_graph import build_one_page_graph
from src.reporting.html.one_page_legend import build_one_page_legend_html
from src.reporting.html.one_page_script import build_one_page_script
from src.reporting.html.one_page_state import (
    configure_one_page,
    set_one_page_inactive_flow_names,
    set_one_page_node_descriptions,
    set_one_page_test_names,
)


def render_one_page_graph(
    center_name: str,
    center_category: str,
    all_dependencies: list[Dependency],
    key_suffix: str,
    *,
    max_depth: int | None = None,
    hub_threshold: int | None = None,
) -> str:
    """Construit et rend le graphe One Page interactif (vis-network)."""

    max_depth = state.ONE_PAGE_MAX_DEPTH if max_depth is None else max_depth
    hub_threshold = (
        state.ONE_PAGE_HUB_THRESHOLD if hub_threshold is None else hub_threshold
    )

    nodes, edges = build_one_page_graph(
        center_name,
        center_category,
        all_dependencies,
        max_depth=max_depth,
        hub_threshold=hub_threshold,
    )
    if len(nodes) <= 1:
        return (
            "<p class='empty'>Aucune relation etendue significative apres elagage "
            "du bruit (hubs et feuilles isolees).</p>"
        )

    has_tests = any(node.get("isTest") for node in nodes)

    network_id = f"onepage-network-{key_suffix}"
    zoom_in_id = f"{network_id}-zoom-in"
    zoom_out_id = f"{network_id}-zoom-out"
    fit_id = f"{network_id}-fit"
    optimize_id = f"{network_id}-optimize"
    analyze_id = f"{network_id}-analyze"
    export_png_id = f"{network_id}-export-png"
    hide_sel_id = f"{network_id}-hide-sel"
    restore_id = f"{network_id}-restore"
    hide_disconnected_id = f"{network_id}-hide-disconnected"
    rank2_id = f"{network_id}-rank2"
    rank3_id = f"{network_id}-rank3"
    hide_tests_id = f"{network_id}-hide-tests"
    legend_id = f"{network_id}-legend"

    hide_tests_filter = (
        f'<label><input id="{hide_tests_id}" type="checkbox" checked>'
        "Masquer les classes de test Apex</label>"
        if has_tests
        else ""
    )

    legend_toggles_html = build_one_page_legend_html(nodes, center_name)

    intro = (
        f"<p class='hint'>Vue consolidee des relations jusqu'a {max_depth} rangs, "
        "apres elagage du bruit (hubs tres references et feuilles isolees). "
        "Le rang indique la distance au composant central.</p>"
    )

    head = f"""
{intro}
<div class="graph-toolbar">
  <button id="{zoom_in_id}" type="button">Zoom +</button>
  <button id="{zoom_out_id}" type="button">Zoom -</button>
  <button id="{fit_id}" type="button">Centrer</button>
  <button id="{optimize_id}" type="button" title="Reorganise les elements pour faciliter la lecture">Optimiser le placement</button>
  <button id="{analyze_id}" type="button" title="Analyser le graphe actuellement affiche">Analyser le graphe</button>
  <button id="{export_png_id}" type="button" title="Exporter le graphe affiche en PNG">Exporter PNG</button>
  <button id="{hide_disconnected_id}" type="button" title="Masquer / afficher les elements sans lien visuel avec le composant central">Masquer les isoles</button>
  <button id="{hide_sel_id}" type="button" title="Masquer le(s) element(s) selectionne(s)" disabled>Masquer la selection</button>
  <button id="{restore_id}" type="button" title="Reafficher les elements masques manuellement" disabled>Reafficher les masques</button>
</div>
<div class="graph-filters">
  <label><input id="{rank2_id}" type="checkbox" checked>Afficher rang 2+</label>
  <label><input id="{rank3_id}" type="checkbox" checked>Afficher rang 3+</label>
  {hide_tests_filter}
</div>
<p class="hint">Astuce : cliquez un element pour le selectionner (Ctrl ou Maj + clic pour en selectionner plusieurs), puis « Masquer la selection ».</p>
<div class="graph-legend" id="{legend_id}">
  <span class="item"><span class="dot" style="background:#bfdbfe"></span>Composant central</span>{legend_toggles_html}
</div>
<div id="{network_id}" class="dependency-graph"></div>
"""
    return head + build_one_page_script(
        network_id=network_id,
        center_name=center_name,
        nodes=nodes,
        edges=edges,
        key_suffix=key_suffix,
        zoom_in_id=zoom_in_id,
        zoom_out_id=zoom_out_id,
        fit_id=fit_id,
        optimize_id=optimize_id,
        analyze_id=analyze_id,
        export_png_id=export_png_id,
        hide_sel_id=hide_sel_id,
        restore_id=restore_id,
        hide_disconnected_id=hide_disconnected_id,
        rank2_id=rank2_id,
        rank3_id=rank3_id,
        hide_tests_id=hide_tests_id,
        legend_id=legend_id,
    )
