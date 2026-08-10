"""Builds the ``<script>`` block that drives the interactive One Page vis-network graph.

This is the client-side counterpart of :func:`src.reporting.html.one_page.render_one_page_graph`:
it wires up zoom/fit/optimize controls, rank/test filters, the legend toggles, node
hide/restore actions, the context menu, hover tooltips and the PNG export button.
"""

from __future__ import annotations

import json

from src.reporting.html.one_page_client_snippets import (
    INACTIVE_FLOW_STYLE_JS,
    STATIC_GRAPH_ANALYSIS_JS,
)


def build_one_page_script(
    *,
    network_id: str,
    center_name: str,
    nodes: list[dict],
    edges: list[dict],
    key_suffix: str,
    zoom_in_id: str,
    zoom_out_id: str,
    fit_id: str,
    optimize_id: str,
    analyze_id: str,
    export_png_id: str,
    hide_sel_id: str,
    restore_id: str,
    hide_disconnected_id: str,
    rank2_id: str,
    rank3_id: str,
    hide_tests_id: str,
    legend_id: str,
) -> str:
    """Return the vis-network script tags for the One Page graph."""
    return f"""<script src="https://unpkg.com/vis-network@9.1.9/dist/vis-network.min.js"></script>
<script>
(() => {{
  const container = document.getElementById({json.dumps(network_id)});
  if (!container || typeof vis === "undefined") return;
  const centerId = {json.dumps(center_name)};
  let fullNodes = {json.dumps(nodes)};
  const fullEdges = {json.dumps(edges)};
{INACTIVE_FLOW_STYLE_JS}
  const nodeMap = new Map(fullNodes.map((node) => [node.id, node]));
  const nodes = new vis.DataSet(fullNodes);
  const edges = new vis.DataSet(fullEdges);
  const network = new vis.Network(container, {{ nodes, edges }}, {{
    nodes: {{ borderWidth: 1, font: {{ face: "Arial", size: 13 }} }},
    edges: {{ color: "#94a3b8", arrows: "to", smooth: {{ type: "dynamic" }}, font: {{ align: "middle", size: 10 }} }},
    physics: {{ stabilization: true, barnesHut: {{ springLength: 140 }} }},
    interaction: {{
      hover: true,
      zoomView: true,
      dragView: true,
      dragNodes: true,
      multiselect: true
    }}
  }});

  const zoomStep = 1.2;
  const zoomIn = document.getElementById({json.dumps(zoom_in_id)});
  const zoomOut = document.getElementById({json.dumps(zoom_out_id)});
  const fit = document.getElementById({json.dumps(fit_id)});
  const optimize = document.getElementById({json.dumps(optimize_id)});
  const analyzeBtn = document.getElementById({json.dumps(analyze_id)});
  const exportPngBtn = document.getElementById({json.dumps(export_png_id)});
  const hideSelBtn = document.getElementById({json.dumps(hide_sel_id)});
  const restoreBtn = document.getElementById({json.dumps(restore_id)});
  const hideDisconnectedBtn = document.getElementById({json.dumps(hide_disconnected_id)});
  const filterRank2 = document.getElementById({json.dumps(rank2_id)});
  const filterRank3 = document.getElementById({json.dumps(rank3_id)});
  const filterHideTests = document.getElementById({json.dumps(hide_tests_id)});
  const legendEl = document.getElementById({json.dumps(legend_id)});
  const legendToggles = legendEl ? legendEl.querySelectorAll(".legend-toggle") : [];
  const disabledCategories = new Set();
  const disabledFlowStates = new Set();
  const hiddenNodeIds = new Set();
  let hideDisconnected = false;
{STATIC_GRAPH_ANALYSIS_JS}
  installOnePageStaticAnalyzer({{ button: analyzeBtn, network, nodes, edges, centerId }});

  const maxRank = () => {{
    if (filterRank2 && !filterRank2.checked) return 1;
    if (filterRank3 && !filterRank3.checked) return 2;
    return Infinity;
  }};

  const adjacency = new Map();
  for (const edge of fullEdges) {{
    if (!adjacency.has(edge.from)) adjacency.set(edge.from, []);
    adjacency.get(edge.from).push(edge);
  }}
  const directEdgeKeys = new Set(fullEdges.map((e) => e.from + "\\u0000" + e.to));

  // Reconnecte les noeuds visibles en "traversant" les noeuds masques :
  // un lien indirect (pointilles) remplace une chaine passant par des noeuds
  // filtres, afin que les fleches ne disparaissent pas quand on masque une
  // categorie intermediaire.
  const buildVisibleEdges = (visibleNodeIds) => {{
    const result = [];
    const seenPairs = new Set();
    for (const startId of visibleNodeIds) {{
      const visited = new Set([startId]);
      const queue = (adjacency.get(startId) || []).map(
        (e) => ({{ node: e.to, label: e.label }})
      );
      while (queue.length) {{
        const cur = queue.shift();
        if (visited.has(cur.node)) continue;
        visited.add(cur.node);
        if (visibleNodeIds.has(cur.node)) {{
          const key = startId + "\\u0000" + cur.node;
          if (cur.node !== startId && !seenPairs.has(key)) {{
            seenPairs.add(key);
            const isDirect = directEdgeKeys.has(key);
            const edgeObj = {{
              from: startId,
              to: cur.node,
              arrows: "to",
              label: isDirect ? (cur.label || "") : "(indirect)",
            }};
            if (!isDirect) {{
              edgeObj.dashes = true;
              edgeObj.color = {{ color: "#cbd5e1" }};
            }}
            result.push(edgeObj);
          }}
          continue;
        }}
        for (const e of (adjacency.get(cur.node) || [])) {{
          queue.push({{ node: e.to, label: e.label }});
        }}
      }}
    }}
    return result;
  }};

  const connectedToCenter = (visibleNodeIds, visibleEdges) => {{
    const connected = new Set();
    if (!visibleNodeIds.has(centerId)) return connected;
    const visualAdjacency = new Map();
    for (const id of visibleNodeIds) {{
      visualAdjacency.set(id, []);
    }}
    for (const edge of visibleEdges) {{
      if (!visibleNodeIds.has(edge.from) || !visibleNodeIds.has(edge.to)) continue;
      visualAdjacency.get(edge.from).push(edge.to);
      visualAdjacency.get(edge.to).push(edge.from);
    }}
    const queue = [centerId];
    connected.add(centerId);
    while (queue.length) {{
      const current = queue.shift();
      for (const next of (visualAdjacency.get(current) || [])) {{
        if (connected.has(next)) continue;
        connected.add(next);
        queue.push(next);
      }}
    }}
    return connected;
  }};

  const optimizeLayout = (animation = true) => {{
    network.setOptions({{
      physics: {{
        enabled: true,
        stabilization: true,
        barnesHut: {{ springLength: 140 }}
      }}
    }});
    network.stabilize();
    network.once("stabilizationIterationsDone", () => {{
      network.setOptions({{ physics: false }});
      network.fit({{ animation }});
    }});
  }};

  const applyFilters = () => {{
    const limit = maxRank();
    const hideTests = filterHideTests && filterHideTests.checked;
    const visibleNodeIds = new Set();
    for (const node of fullNodes) {{
      if ((node.depth || 0) > limit) continue;
      if (hideTests && node.isTest && node.id !== centerId) continue;
      if (node.id !== centerId && node.category === "Flow") {{
        const flowState = node.isInactiveFlow ? "inactive" : "active";
        if (disabledFlowStates.has(flowState)) continue;
      }}
      if (node.id !== centerId && node.category !== "Flow" && disabledCategories.has(node.category)) continue;
      if (node.id !== centerId && hiddenNodeIds.has(node.id)) continue;
      visibleNodeIds.add(node.id);
    }}
    let filteredEdges = buildVisibleEdges(visibleNodeIds);
    if (hideDisconnected) {{
      const connectedIds = connectedToCenter(visibleNodeIds, filteredEdges);
      visibleNodeIds.clear();
      connectedIds.forEach((id) => visibleNodeIds.add(id));
      filteredEdges = filteredEdges.filter(
        (edge) => visibleNodeIds.has(edge.from) && visibleNodeIds.has(edge.to)
      );
    }}
    const filteredNodes = fullNodes.filter((node) => visibleNodeIds.has(node.id));
    nodes.clear();
    edges.clear();
    nodes.add(filteredNodes);
    edges.add(filteredEdges);
    optimizeLayout(false);
  }};

  [filterRank2, filterRank3, filterHideTests].forEach((input) => {{
    if (input) input.addEventListener("change", applyFilters);
  }});

  const toggleCategory = (el) => {{
    const flowState = el.getAttribute("data-flow-state");
    if (flowState) {{
      if (disabledFlowStates.has(flowState)) {{
        disabledFlowStates.delete(flowState);
        el.classList.remove("disabled");
      }} else {{
        disabledFlowStates.add(flowState);
        el.classList.add("disabled");
      }}
      applyFilters();
      return;
    }}
    const category = el.getAttribute("data-category");
    if (!category) return;
    if (disabledCategories.has(category)) {{
      disabledCategories.delete(category);
      el.classList.remove("disabled");
    }} else {{
      disabledCategories.add(category);
      el.classList.add("disabled");
    }}
    applyFilters();
  }};

  legendToggles.forEach((el) => {{
    el.addEventListener("click", () => toggleCategory(el));
    el.addEventListener("keydown", (event) => {{
      if (event.key === "Enter" || event.key === " ") {{
        event.preventDefault();
        toggleCategory(el);
      }}
    }});
  }});

  const updateActionButtons = () => {{
    if (restoreBtn) {{
      restoreBtn.disabled = hiddenNodeIds.size === 0;
      restoreBtn.textContent = hiddenNodeIds.size
        ? "Reafficher les masques (" + hiddenNodeIds.size + ")"
        : "Reafficher les masques";
    }}
    if (hideSelBtn) {{
      const selection = network.getSelectedNodes().filter((id) => id !== centerId);
      hideSelBtn.disabled = selection.length === 0;
    }}
  }};

  network.on("select", updateActionButtons);

  if (hideDisconnectedBtn) {{
    hideDisconnectedBtn.addEventListener("click", () => {{
      hideDisconnected = !hideDisconnected;
      hideDisconnectedBtn.classList.toggle("active", hideDisconnected);
      hideDisconnectedBtn.textContent = hideDisconnected
        ? "Afficher les isoles"
        : "Masquer les isoles";
      applyFilters();
      updateActionButtons();
    }});
  }}

  // Menu contextuel (clic droit) : "Masquer cet element".
  let contextMenuEl = null;
  const closeContextMenu = () => {{
    if (contextMenuEl) {{
      contextMenuEl.remove();
      contextMenuEl = null;
    }}
  }};
  const openContextMenu = (clientX, clientY, nodeId) => {{
    closeContextMenu();
    const menu = document.createElement("div");
    menu.className = "graph-context-menu";
    const item = document.createElement("button");
    item.type = "button";
    item.textContent = "Masquer cet element";
    item.addEventListener("click", () => {{
      hiddenNodeIds.add(nodeId);
      network.unselectAll();
      applyFilters();
      updateActionButtons();
      closeContextMenu();
    }});
    menu.appendChild(item);
    menu.style.left = clientX + "px";
    menu.style.top = clientY + "px";
    document.body.appendChild(menu);
    contextMenuEl = menu;
  }};

  network.on("oncontext", (params) => {{
    if (params.event) params.event.preventDefault();
    const nodeId = network.getNodeAt(params.pointer.DOM);
    if (nodeId === undefined || nodeId === null || nodeId === centerId) {{
      closeContextMenu();
      return;
    }}
    const evt = params.event;
    openContextMenu(evt.clientX, evt.clientY, nodeId);
  }});
  document.addEventListener("click", closeContextMenu);
  network.on("dragStart", closeContextMenu);
  network.on("zoom", closeContextMenu);

  // Tooltip au survol prolonge. Le tooltip natif de vis-network peut etre
  // peu fiable avec les noeuds custom canvas (flows inactifs hachures), donc
  // on gere explicitement l'affichage.
  let tooltipTimer = null;
  let tooltipEl = null;
  const closeNodeTooltip = () => {{
    if (tooltipTimer) {{
      clearTimeout(tooltipTimer);
      tooltipTimer = null;
    }}
    if (tooltipEl) {{
      tooltipEl.remove();
      tooltipEl = null;
    }}
  }};
  const openNodeTooltip = (nodeId, clientX, clientY) => {{
    closeNodeTooltip();
    const node = nodeMap.get(nodeId);
    const content = node && node.title ? String(node.title) : "";
    if (!content) return;
    tooltipTimer = setTimeout(() => {{
      const tooltip = document.createElement("div");
      tooltip.className = "graph-node-tooltip";
      tooltip.innerHTML = content;
      tooltip.style.left = (clientX + 12) + "px";
      tooltip.style.top = (clientY + 12) + "px";
      document.body.appendChild(tooltip);
      tooltipEl = tooltip;
    }}, 650);
  }};
  network.on("hoverNode", (params) => {{
    const evt = params.event && params.event.srcEvent;
    const rect = container.getBoundingClientRect();
    const clientX = evt ? evt.clientX : rect.left + params.pointer.DOM.x;
    const clientY = evt ? evt.clientY : rect.top + params.pointer.DOM.y;
    openNodeTooltip(params.node, clientX, clientY);
  }});
  network.on("blurNode", closeNodeTooltip);
  network.on("dragStart", closeNodeTooltip);
  network.on("zoom", closeNodeTooltip);
  container.addEventListener("mouseleave", closeNodeTooltip);
  container.addEventListener("mousedown", closeNodeTooltip);

  network.on("dragStart", () => {{
    container.style.cursor = "grabbing";
  }});
  network.on("dragEnd", () => {{
    container.style.cursor = "grab";
  }});
  container.style.cursor = "grab";

  if (hideSelBtn) {{
    hideSelBtn.addEventListener("click", () => {{
      const selection = network.getSelectedNodes().filter((id) => id !== centerId);
      if (!selection.length) return;
      selection.forEach((id) => hiddenNodeIds.add(id));
      network.unselectAll();
      applyFilters();
      updateActionButtons();
    }});
  }}
  if (restoreBtn) {{
    restoreBtn.addEventListener("click", () => {{
      if (!hiddenNodeIds.size) return;
      hiddenNodeIds.clear();
      applyFilters();
      updateActionButtons();
    }});
  }}

  if (zoomIn) {{
    zoomIn.addEventListener("click", () => {{
      const scale = network.getScale();
      network.moveTo({{ scale: scale * zoomStep }});
    }});
  }}
  if (zoomOut) {{
    zoomOut.addEventListener("click", () => {{
      const scale = network.getScale();
      network.moveTo({{ scale: scale / zoomStep }});
    }});
  }}
  if (fit) {{
    fit.addEventListener("click", () => network.fit({{ animation: true }}));
  }}
  if (optimize) {{
    optimize.addEventListener("click", () => optimizeLayout(true));
  }}
  if (exportPngBtn) {{
    exportPngBtn.addEventListener("click", () => {{
      closeContextMenu();
      closeNodeTooltip();
      network.redraw();
      setTimeout(() => {{
        const sourceCanvas =
          container.querySelector("canvas") ||
          (network.canvas && network.canvas.frame && network.canvas.frame.canvas);
        if (!sourceCanvas) return;
        const exportCanvas = document.createElement("canvas");
        exportCanvas.width = sourceCanvas.width;
        exportCanvas.height = sourceCanvas.height;
        const ctx = exportCanvas.getContext("2d");
        ctx.fillStyle = "#ffffff";
        ctx.fillRect(0, 0, exportCanvas.width, exportCanvas.height);
        ctx.drawImage(sourceCanvas, 0, 0);
        const link = document.createElement("a");
        link.download = {json.dumps(f"one-page-{key_suffix}.png")};
        link.href = exportCanvas.toDataURL("image/png");
        document.body.appendChild(link);
        link.click();
        link.remove();
      }}, 80);
    }});
  }}
  network.on("doubleClick", (params) => {{
    const scale = network.getScale();
    const evt = params && params.event && params.event.srcEvent;
    const shift = !!(evt && evt.shiftKey);
    const factor = shift ? (1 / zoomStep) : zoomStep;
    network.moveTo({{ scale: scale * factor, animation: {{ duration: 150 }} }});
  }});
  network.once("stabilizationIterationsDone", () => {{
    network.setOptions({{ physics: false }});
  }});
  applyFilters();
  updateActionButtons();
}})();
</script>
"""
