"""Snippets JavaScript utilises par le rendu One Page."""

INACTIVE_FLOW_STYLE_JS = r"""
  const applyInactiveFlowStyle = (node) => {
    if (!node.isInactiveFlow) return node;
    return {
      ...node,
      shape: "custom",
      ctxRenderer: ({ ctx, id, x, y, state, style, label }) => {
        const text = String(label || id || "");
        ctx.font = (style && style.font) || "13px Arial";
        const textWidth = ctx.measureText(text).width;
        const width = Math.max(110, textWidth + 28);
        const height = 34;
        return {
          drawNode: () => {
            const left = x - width / 2;
            const top = y - height / 2;
            const radius = 6;
            const roundedRect = (l, t, w, h, r) => {
              ctx.beginPath();
              ctx.moveTo(l + r, t);
              ctx.lineTo(l + w - r, t);
              ctx.quadraticCurveTo(l + w, t, l + w, t + r);
              ctx.lineTo(l + w, t + h - r);
              ctx.quadraticCurveTo(l + w, t + h, l + w - r, t + h);
              ctx.lineTo(l + r, t + h);
              ctx.quadraticCurveTo(l, t + h, l, t + h - r);
              ctx.lineTo(l, t + r);
              ctx.quadraticCurveTo(l, t, l + r, t);
              ctx.closePath();
            };
            ctx.save();
            roundedRect(left, top, width, height, radius);
            ctx.fillStyle = "#ffedd5";
            ctx.fill();

            ctx.save();
            const inset = 2;
            roundedRect(
              left + inset,
              top + inset,
              width - inset * 2,
              height - inset * 2,
              Math.max(0, radius - inset)
            );
            ctx.clip();
            ctx.strokeStyle = "rgba(194, 65, 12, 0.35)";
            ctx.lineWidth = 1;
            for (let i = -height; i < width + height; i += 8) {
              ctx.beginPath();
              ctx.moveTo(left + inset + i, top + height - inset);
              ctx.lineTo(left + inset + i + height, top + inset);
              ctx.stroke();
            }
            ctx.restore();

            roundedRect(left, top, width, height, radius);
            ctx.strokeStyle = state && state.selected ? "#1d4ed8" : "#f97316";
            ctx.lineWidth = state && state.selected ? 3 : (node.borderWidth || 1);
            ctx.stroke();

            ctx.fillStyle = "#1e293b";
            ctx.font = (style && style.font) || "13px Arial";
            ctx.textAlign = "center";
            ctx.textBaseline = "middle";
            ctx.fillText(text, x, y);
            ctx.restore();
          },
          nodeDimensions: { width, height },
        };
      },
    };
  };
  fullNodes = fullNodes.map((node) => applyInactiveFlowStyle(node));
"""


STATIC_GRAPH_ANALYSIS_JS = r"""
  const installOnePageStaticAnalyzer = ({ button, network, nodes, edges, centerId }) => {
    if (!button) return;
    const esc = (value) => String(value ?? "")
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    const pct = (value) => Math.round(value * 100);
    const severityLabel = { high: "Point critique", medium: "Point d'attention", info: "Information" };

    const categoryLabel = (cat) => ({
      Apex: "Apex", Objet: "Objets", Field: "Champs", Flow: "Flows",
      LWC: "LWC", Aura: "Aura", Report: "Rapports", Metadata: "Metadata"
    }[cat] || cat || "Autre");

    const addFinding = (items, severity, title, message, recommendation) => {
      items.push({ severity, title, message, recommendation });
    };

    const buildMetrics = () => {
      const visibleNodes = nodes.get();
      const visibleEdges = edges.get();
      const byId = new Map(visibleNodes.map((node) => [node.id, node]));
      const degree = new Map(visibleNodes.map((node) => [node.id, { in: 0, out: 0 }]));
      const categories = {};
      let inactiveFlows = 0;
      let maxRank = 0;
      visibleNodes.forEach((node) => {
        categories[node.category] = (categories[node.category] || 0) + 1;
        if (node.category === "Flow" && node.isInactiveFlow) inactiveFlows += 1;
        maxRank = Math.max(maxRank, Number(node.depth || 0));
      });
      visibleEdges.forEach((edge) => {
        if (degree.has(edge.from)) degree.get(edge.from).out += 1;
        if (degree.has(edge.to)) degree.get(edge.to).in += 1;
      });
      const n = visibleNodes.length;
      const density = n > 1 ? visibleEdges.length / (n * (n - 1)) : 0;
      const indirectEdges = visibleEdges.filter((edge) => edge.dashes || edge.label === "(indirect)");
      const central = degree.get(centerId) || { in: 0, out: 0 };
      const topConnected = visibleNodes
        .map((node) => ({ node, total: (degree.get(node.id)?.in || 0) + (degree.get(node.id)?.out || 0) }))
        .filter((item) => item.node.id !== centerId)
        .sort((a, b) => b.total - a.total)
        .slice(0, 5);
      return {
        visibleNodes, visibleEdges, byId, degree, categories, inactiveFlows, maxRank,
        density, indirectEdges, centralDegree: central.in + central.out, topConnected,
      };
    };

    const analyze = () => {
      const m = buildMetrics();
      const findings = [];
      const flowCount = m.categories.Flow || 0;
      const apexCount = m.categories.Apex || 0;
      const objectCount = m.categories.Objet || 0;
      const indirectRatio = m.visibleEdges.length ? m.indirectEdges.length / m.visibleEdges.length : 0;

      if (m.visibleNodes.length > 35) {
        addFinding(findings, "high", "Graphe difficile à gouverner",
          `La vue affiche ${m.visibleNodes.length} éléments. Un administrateur risque de manquer des dépendances importantes.`,
          "Réduire la vue aux rangs proches, puis analyser les zones les plus connectées séparément.");
      } else if (m.visibleNodes.length > 20) {
        addFinding(findings, "medium", "Graphe riche",
          `La vue affiche ${m.visibleNodes.length} éléments. Elle reste lisible, mais demande une revue attentive.`,
          "Commencer par les éléments de rang 1 puis vérifier les dépendances indirectes.");
      }
      if (m.density > 0.10) {
        addFinding(findings, "high", "Couplage élevé",
          "Beaucoup de liens existent entre les éléments visibles. Une modification locale peut avoir un impact large.",
          "Identifier les responsabilités métier et isoler les automatisations trop transverses.");
      } else if (m.density > 0.05) {
        addFinding(findings, "medium", "Couplage à surveiller",
          "Le graphe contient plusieurs chemins entre composants, signe d'une dépendance fonctionnelle notable.",
          "Documenter les dépendances principales avant toute évolution.");
      }
      if (m.centralDegree >= 10) {
        addFinding(findings, "high", "Composant central très sollicité",
          `Le composant central possède ${m.centralDegree} liens visibles. Il est probablement critique pour les impacts de changement.`,
          "Prévoir une analyse d'impact et des tests de non-régression avant modification.");
      } else if (m.centralDegree >= 6) {
        addFinding(findings, "medium", "Composant central important",
          `Le composant central possède ${m.centralDegree} liens visibles.`,
          "Vérifier les dépendances entrantes et sortantes avant déploiement.");
      }
      if (flowCount > 0 && apexCount > 0 && objectCount > 0) {
        addFinding(findings, "medium", "Automatisations mixtes Flow et Apex",
          "La vue combine objets, flows et Apex. L'ordre d'exécution Salesforce peut devenir difficile à anticiper.",
          "Comparer les responsabilités Flow/Apex et éviter les doublons d'automatisation sur le même objet.");
      }
      if (m.inactiveFlows > 0) {
        addFinding(findings, "medium", "Flows inactifs visibles",
          `${m.inactiveFlows} flow(s) inactif(s) apparaissent dans la vue.`,
          "Confirmer s'ils sont conservés volontairement, sinon les archiver ou documenter leur remplacement.");
      }
      if (indirectRatio > 0.35) {
        addFinding(findings, "medium", "Dépendances masquées par des filtres",
          `${pct(indirectRatio)} % des liens visibles sont indirects. Certains éléments intermédiaires sont masqués.`,
          "Réactiver temporairement les catégories masquées pour comprendre le chemin réel de dépendance.");
      }
      if (m.maxRank >= 3) {
        addFinding(findings, "info", "Impact indirect de rang 3",
          "La vue contient des relations éloignées du composant central.",
          "Traiter ces éléments comme des impacts potentiels, pas comme des dépendances immédiates.");
      }
      const veryConnected = m.topConnected.filter((item) => item.total >= Math.max(4, Math.ceil(m.visibleNodes.length * 0.18)));
      if (veryConnected.length) {
        addFinding(findings, "medium", "Éléments très connectés",
          veryConnected.map((item) => `${esc(item.node.label || item.node.id)} (${item.total} liens)`).join(", "),
          "Ces éléments peuvent être des points de passage fonctionnels ou techniques à sécuriser par des tests.");
      }
      if (!findings.length) {
        addFinding(findings, "info", "Situation lisible",
          "Le graphe visible ne présente pas de signal fort de complexité ou de risque.",
          "Conserver cette vue comme support d'analyse d'impact lors des prochaines évolutions.");
      }
      return { metrics: m, findings };
    };

    const renderModal = ({ metrics, findings }) => {
      const categories = Object.entries(metrics.categories)
        .sort((a, b) => b[1] - a[1])
        .map(([cat, count]) => `<span>${esc(categoryLabel(cat))}<strong>${count}</strong></span>`)
        .join("");
      const cards = [
        ["Éléments visibles", metrics.visibleNodes.length],
        ["Relations visibles", metrics.visibleEdges.length],
        ["Liens indirects", metrics.indirectEdges.length],
        ["Rang max", metrics.maxRank],
      ].map(([label, value]) => `<div class="graph-analysis-card"><span>${label}</span><strong>${value}</strong></div>`).join("");
      const items = findings.map((finding) => `
        <article class="graph-analysis-finding ${finding.severity}">
          <div><span>${severityLabel[finding.severity]}</span><h4>${esc(finding.title)}</h4></div>
          <p>${finding.message}</p><p><strong>Conseil :</strong> ${finding.recommendation}</p>
        </article>`).join("");
      const modal = document.createElement("div");
      modal.className = "graph-analysis-modal";
      modal.innerHTML = `
        <style>
          .graph-analysis-modal{position:fixed;inset:0;z-index:10000;background:rgba(15,23,42,.45);display:flex;align-items:center;justify-content:center;padding:24px}
          .graph-analysis-dialog{max-width:920px;max-height:88vh;overflow:auto;background:#fff;border-radius:16px;box-shadow:0 24px 70px rgba(15,23,42,.35);border:1px solid #cbd5e1;color:#0f172a}
          .graph-analysis-head{padding:20px 24px;background:linear-gradient(135deg,#eff6ff,#f8fafc);border-bottom:1px solid #dbeafe;display:flex;justify-content:space-between;gap:16px}
          .graph-analysis-head h3{margin:0 0 6px;font-size:1.25rem}.graph-analysis-head p{margin:0;color:#475569}.graph-analysis-close{border:1px solid #cbd5e1;background:#fff;border-radius:999px;padding:6px 12px;cursor:pointer;height:34px}
          .graph-analysis-body{padding:20px 24px}.graph-analysis-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(145px,1fr));gap:12px;margin-bottom:14px}
          .graph-analysis-card{border:1px solid #e2e8f0;border-radius:12px;background:#f8fafc;padding:12px}.graph-analysis-card span{display:block;color:#64748b;font-size:.78rem;text-transform:uppercase}.graph-analysis-card strong{font-size:1.45rem}
          .graph-analysis-cats{display:flex;flex-wrap:wrap;gap:8px;margin:8px 0 18px}.graph-analysis-cats span{border:1px solid #cbd5e1;border-radius:999px;padding:4px 10px;background:#fff}.graph-analysis-cats strong{margin-left:6px}
          .graph-analysis-finding{border-left:5px solid #60a5fa;background:#eff6ff;border-radius:12px;padding:13px 16px;margin:12px 0}.graph-analysis-finding.medium{border-color:#f59e0b;background:#fffbeb}.graph-analysis-finding.high{border-color:#ef4444;background:#fef2f2}
          .graph-analysis-finding span{font-size:.75rem;font-weight:700;text-transform:uppercase;color:#475569}.graph-analysis-finding h4{margin:2px 0 8px}.graph-analysis-finding p{margin:6px 0;line-height:1.45}
        </style>
        <section class="graph-analysis-dialog" role="dialog" aria-modal="true" aria-label="Analyse du graphe One Page">
          <header class="graph-analysis-head"><div><h3>Analyse du graphe visible</h3><p>Lecture orientée Salesforce, sans jargon de théorie des graphes.</p></div><button class="graph-analysis-close" type="button">Fermer</button></header>
          <div class="graph-analysis-body"><div class="graph-analysis-grid">${cards}</div><div class="graph-analysis-cats">${categories}</div>${items}</div>
        </section>`;
      modal.querySelector(".graph-analysis-close").addEventListener("click", () => modal.remove());
      modal.addEventListener("click", (event) => { if (event.target === modal) modal.remove(); });
      document.addEventListener("keydown", function onEsc(event) {
        if (event.key === "Escape") { modal.remove(); document.removeEventListener("keydown", onEsc); }
      });
      document.body.appendChild(modal);
    };

    button.addEventListener("click", () => {
      renderModal(analyze());
    });
  };
"""
