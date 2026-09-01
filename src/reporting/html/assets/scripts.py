"""JavaScript snippets embedded in the HTML documentation pages.

Extracted verbatim from the former ``assets.py`` module so the byte-for-byte
HTML output stays unchanged after the refactor.
"""

from __future__ import annotations

MERMAID_RUNTIME_SCRIPT = r"""
<script src="https://cdn.jsdelivr.net/npm/mermaid@10.9.5/dist/mermaid.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/svg-pan-zoom@3.6.1/dist/svg-pan-zoom.min.js"></script>
<script>
(function(){
  function isVisible(el){
    var p = el.parentElement;
    while(p && p !== document.body){
      if(p.classList && p.classList.contains("tab-panel") && !p.classList.contains("active")){
        return false;
      }
      p = p.parentElement;
    }
    return true;
  }
  function captureSource(el){
    if(!el.hasAttribute("data-mermaid-source")){
      el.setAttribute("data-mermaid-source", el.textContent);
    }
  }
  function parseTranslate(str){
    if(!str) return {x:0,y:0};
    var m = str.match(/translate\(\s*([-\d.eE+]+)\s*[, ]\s*([-\d.eE+]+)\s*\)/);
    if(!m) return {x:0,y:0};
    return {x: parseFloat(m[1]), y: parseFloat(m[2])};
  }
  function centerOfNode(node){
    var tr = parseTranslate(node.getAttribute("transform"));
    return {x: tr.x, y: tr.y};
  }
  function shiftPathEndpoints(path, startDelta, endDelta){
    var d = path.getAttribute("d");
    if(!d) return;
    var numberRe = /-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?/g;
    var nums = d.match(numberRe);
    if(!nums || nums.length < 4) return;
    if(startDelta){
      nums[0] = String(parseFloat(nums[0]) + startDelta.x);
      nums[1] = String(parseFloat(nums[1]) + startDelta.y);
    }
    if(endDelta){
      nums[nums.length-2] = String(parseFloat(nums[nums.length-2]) + endDelta.x);
      nums[nums.length-1] = String(parseFloat(nums[nums.length-1]) + endDelta.y);
    }
    var i = 0;
    var newD = d.replace(numberRe, function(){ return nums[i++]; });
    path.setAttribute("d", newD);
  }
  function nodeNameFromId(id){
    if(!id) return "";
    var m = id.match(/^flowchart-(.+?)-\d+$/);
    return m ? m[1] : id;
  }
  function findConnectedEdges(svg, nodeName){
    if(!nodeName) return {outgoing: [], incoming: []};
    var outgoing = [];
    var incoming = [];
    var paths = svg.querySelectorAll("g.edgePaths path, path.flowchart-link");
    paths.forEach(function(p){
      var cls = (p.getAttribute("class") || "").split(/\s+/);
      var fromCls = null, toCls = null;
      cls.forEach(function(c){
        if(c.indexOf("LS-") === 0){ fromCls = c.substring(3); }
        else if(c.indexOf("LE-") === 0){ toCls = c.substring(3); }
      });
      if(fromCls === nodeName){ outgoing.push(p); }
      if(toCls === nodeName){ incoming.push(p); }
    });
    return {outgoing: outgoing, incoming: incoming};
  }
  function moveEdgeLabel(svg, nodeName, delta){
    // labels are usually in g.edgeLabels and have labels per edge; we skip to avoid breakage.
  }
  function enableNodeDrag(svg, panZoom){
    var nodes = svg.querySelectorAll("g.node");
    nodes.forEach(function(node){
      if(node.dataset.mmDragEnabled === "true") return;
      node.dataset.mmDragEnabled = "true";
      var nodeName = nodeNameFromId(node.getAttribute("id"));
      var dragging = false;
      var startClient = null;
      var startOffset = null;
      var edges = null;
      var panEnabledBefore = true;
      node.addEventListener("mousedown", function(ev){
        if(ev.button !== 0) return;
        dragging = true;
        startClient = {x: ev.clientX, y: ev.clientY};
        startOffset = parseTranslate(node.getAttribute("transform"));
        edges = findConnectedEdges(svg, nodeName);
        try { panEnabledBefore = panZoom.isPanEnabled(); panZoom.disablePan(); } catch(e){}
        ev.stopPropagation();
        ev.preventDefault();
      });
      var lastDelta = {x:0,y:0};
      function onMove(ev){
        if(!dragging) return;
        var zoom = 1;
        try { zoom = panZoom.getZoom() || 1; } catch(e){}
        var dx = (ev.clientX - startClient.x) / zoom;
        var dy = (ev.clientY - startClient.y) / zoom;
        node.setAttribute("transform", "translate(" + (startOffset.x + dx) + "," + (startOffset.y + dy) + ")");
        var frameDelta = {x: dx - lastDelta.x, y: dy - lastDelta.y};
        if(edges){
          edges.outgoing.forEach(function(p){ shiftPathEndpoints(p, frameDelta, null); });
          edges.incoming.forEach(function(p){ shiftPathEndpoints(p, null, frameDelta); });
        }
        lastDelta = {x: dx, y: dy};
      }
      function onUp(){
        if(!dragging) return;
        dragging = false;
        lastDelta = {x:0, y:0};
        if(panEnabledBefore){ try { panZoom.enablePan(); } catch(e){} }
      }
      document.addEventListener("mousemove", onMove);
      document.addEventListener("mouseup", onUp);
    });
  }
  function enhanceContainer(container){
    if(container.dataset.mmEnhanced === "true") return;
    var mermaidDiv = container.querySelector(".mermaid");
    if(!mermaidDiv) return;
    if(mermaidDiv.getAttribute("data-processed") !== "true") return;
    var svg = mermaidDiv.querySelector("svg");
    if(!svg) return;
    container.dataset.mmEnhanced = "true";
    svg.removeAttribute("height");
    svg.removeAttribute("width");
    svg.style.width = "100%";
    svg.style.height = "100%";
    svg.style.maxWidth = "100%";
    var panZoom = null;
    try {
      panZoom = svgPanZoom(svg, {
        zoomEnabled: true,
        controlIconsEnabled: false,
        fit: true,
        center: true,
        minZoom: 0.2,
        maxZoom: 10,
        zoomScaleSensitivity: 0.35,
        dblClickZoomEnabled: false,
        preventMouseEventsDefault: false
      });
    } catch(err){
      console.error("svg-pan-zoom init failed", err);
      return;
    }
    var toolbar = container.querySelector(".mermaid-toolbar");
    if(toolbar){
      toolbar.addEventListener("click", function(ev){
        var btn = ev.target.closest("[data-mermaid-action]");
        if(!btn) return;
        var action = btn.getAttribute("data-mermaid-action");
        if(action === "zoom-in"){ panZoom.zoomBy(1.25); }
        else if(action === "zoom-out"){ panZoom.zoomBy(0.8); }
        else if(action === "reset"){ panZoom.resetZoom(); panZoom.center(); panZoom.fit(); }
      });
    }
    svg.addEventListener("dblclick", function(ev){
      if(ev.shiftKey){ panZoom.zoomBy(0.7); }
      else { panZoom.zoomBy(1.4); }
      ev.preventDefault();
    });
    enableNodeDrag(svg, panZoom);
  }
  function enhanceAll(scope){
    var containers = (scope || document).querySelectorAll(".mermaid-container");
    containers.forEach(enhanceContainer);
  }
  window.__enhanceMermaid = enhanceAll;
  window.__renderMermaid = function(root){
    if(!window.mermaid){return;}
    var scope = root || document;
    var nodes = Array.prototype.slice.call(scope.querySelectorAll(".mermaid"));
    var targets = nodes.filter(function(n){
      captureSource(n);
      if(!isVisible(n)){return false;}
      return n.getAttribute("data-processed") !== "true";
    });
    if(!targets.length){ enhanceAll(scope); return; }
    try{
      var result = window.mermaid.run({nodes: targets});
      if(result && typeof result.then === "function"){
        result.then(function(){ enhanceAll(scope); })
              .catch(function(e){ console.error("mermaid run", e); });
      } else {
        setTimeout(function(){ enhanceAll(scope); }, 50);
      }
    }
    catch(e){ console.error("mermaid run", e); }
  };
  function boot(){
    if(!window.mermaid){return;}
    try{
      window.mermaid.initialize({startOnLoad:false,securityLevel:"loose",theme:"default",flowchart:{htmlLabels:true,curve:"basis"}});
    }catch(e){ console.error("mermaid init", e); }
    Array.prototype.forEach.call(document.querySelectorAll(".mermaid"), captureSource);
    window.__renderMermaid();
  }
  if(document.readyState==="loading"){ document.addEventListener("DOMContentLoaded", boot); }
  else{ boot(); }
})();
</script>
""".strip()


TABS_SCRIPT = """
<script>
(() => {
  const renderMermaidIn = (panel) => {
    if (!panel) return;
    const fn = window.__renderMermaid;
    if (typeof fn === "function") {
      fn(panel);
      return;
    }
    if (!window.mermaid) return;
    const nodes = Array.from(panel.querySelectorAll('.mermaid:not([data-processed="true"])'));
    if (!nodes.length) return;
    try {
      window.mermaid.run({ nodes });
    } catch (err) {
      console.error("mermaid run (tab)", err);
    }
  };
  const activatePanel = (panel) => {
    if (!panel) return false;
    const group = panel.getAttribute("data-tab-panel");
    if (!group) return false;
    document.querySelectorAll(`[data-tab-group="${group}"]`).forEach((item) => item.classList.remove("active"));
    document.querySelectorAll(`[data-tab-panel="${group}"]`).forEach((item) => item.classList.remove("active"));
    panel.classList.add("active");
    const button = document.querySelector(`[data-tab-group="${group}"][data-tab-target="${panel.id}"]`);
    if (button) button.classList.add("active");
    // A nested panel stays hidden unless its ancestors are activated too,
    // so a link pointing straight at a sub-tab shows nothing.
    const parent = panel.parentElement
      ? panel.parentElement.closest("[data-tab-panel]")
      : null;
    if (parent) activatePanel(parent);
    renderMermaidIn(panel);
    return true;
  };
  document.querySelectorAll("[data-tab-group]").forEach((button) => {
    button.addEventListener("click", () => {
      const target = button.getAttribute("data-tab-target");
      if (!target) return;
      activatePanel(document.getElementById(target));
    });
  });
  const applyHash = () => {
    const hash = window.location.hash.slice(1);
    if (!hash) return;
    activatePanel(document.getElementById(hash));
  };
  window.addEventListener("hashchange", applyHash);
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", applyHash);
  } else {
    applyHash();
  }
})();
</script>
""".strip()


SEARCH_SCRIPT = """
<script>
(() => {
  window.addEventListener('DOMContentLoaded', () => {
    // Global Search (simple version: filter tables and lists)
    const searchInput = document.getElementById('global-search');
    if (searchInput) {
      searchInput.addEventListener('input', (e) => {
        const term = e.target.value.toLowerCase();
        const items = document.querySelectorAll('table tbody tr, .findings-list li.finding, .card');
        items.forEach(item => {
          const text = item.textContent.toLowerCase();
          item.style.display = text.includes(term) ? '' : 'none';
        });
      });
    }
  });
})();
</script>
""".strip()
