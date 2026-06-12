"""Render the per-Apex-class / per-trigger documentation pages."""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Callable

from src.analyzer.models import Finding
from src.core.models import (
    ApexArtifact,
    MetadataSnapshot,
    PmdViolation,
    ReviewResult,
)
from src.core.utils import html_value, safe_slug, write_text

from src.reporting.html.dependencies import (
    apex_dependencies,
    build_apex_reference_index,
    render_apex_dependency_graph,
    render_apex_dependency_rows,
    trigger_object_name,
)
from src.reporting.html.findings import (
    findings_to_review_improvements,
    render_analyzer_tab,
    render_findings_summary,
    render_pmd_rows,
)
from src.reporting.html.page_shell import (
    index_back_link,
    list_or_empty,
    render_page,
    tabbed_sections,
)


LogCallback = Callable[[str], None]


def render_apex_page(
    artifact: ApexArtifact,
    review: ReviewResult,
    current_path: Path,
    output_dir: Path,
    assets_dir: Path,
    apex_pages: dict[str, Path],
    dependencies: list[dict[str, str]],
    pmd_violations: list[PmdViolation],
    findings: list[Finding] | None = None,
) -> str:
    findings = findings or []
    metrics_list = list(review.metrics)
    metrics_list.append(("Couverture de tests", (f"{artifact.test_coverage:.1f} %") if artifact.test_coverage is not None else "N/A"))
        
    metrics = "".join(
        f"<li><strong>{html_value(label)}:</strong> {html_value(value)}</li>"
        for label, value in metrics_list
    )
    improvements_for_heuristics = list(review.improvements) + findings_to_review_improvements(findings)
    positives = list_or_empty(review.positives, "Aucun point fort automatique detecte.")
    improvements = list_or_empty(improvements_for_heuristics, "Aucun point d'amelioration automatique detecte.")
    analyzer_tab = render_analyzer_tab(findings)
    analyzer_inline_summary = render_findings_summary(findings)
    code_preview = artifact.body

    # Build annotation map: line number → list of annotation dicts
    ann_map: dict[int, list[dict]] = {}
    for finding in findings:
        if finding.line is not None:
            ann_map.setdefault(finding.line, []).append({
                "source": "analyzer",
                "severity": finding.rule.severity,
                "title": finding.rule.title,
                "message": finding.message,
            })
    for pmd in pmd_violations:
        if pmd.begin_line > 0:
            ann_map.setdefault(pmd.begin_line, []).append({
                "source": "pmd",
                "severity": "pmd",
                "title": pmd.rule,
                "message": pmd.message,
                "priority": pmd.priority,
            })
    ann_json = json.dumps(ann_map)

    # Findings without a line number → global banner shown above the code
    global_findings = [f for f in findings if f.line is None]
    global_banners_html = ""
    if global_findings:
        banners = []
        for f in global_findings:
            sev = f.rule.severity.lower()
            banners.append(
                f"<div class='apex-ann apex-ann-{sev} apex-ann-global'>⚠ <strong>{html.escape(f.rule.title)}</strong>"
                f" — {html.escape(f.message)}</div>"
            )
        global_banners_html = (
            "<div style='margin-bottom:8px'>" + "".join(banners) + "</div>"
        )

    code_tab_html = f"""
<style>
  .apex-ann {{
    display: block; font-family: sans-serif; font-style: normal; font-size: 0.8em;
    padding: 3px 8px 3px 2em; margin: 1px 0; border-left: 3px solid; border-radius: 2px;
  }}
  .apex-ann-critical  {{ background: rgba(255,50,50,.15); border-color: #ff4444; color: #ff8888; }}
  .apex-ann-major     {{ background: rgba(255,140,0,.15); border-color: #ff8c00; color: #ffb040; }}
  .apex-ann-minor     {{ background: rgba(240,220,0,.12); border-color: #ccbb00; color: #ddcc44; }}
  .apex-ann-info      {{ background: rgba(0,140,255,.12); border-color: #0088ff; color: #44aaff; }}
  .apex-ann-pmd       {{ background: rgba(170,0,255,.12); border-color: #aa00ff; color: #cc44ff; }}
  /* Global banners displayed on white background need dark text */
  .apex-ann-global.apex-ann-critical {{ color: #b00000; }}
  .apex-ann-global.apex-ann-major    {{ color: #7a3800; }}
  .apex-ann-global.apex-ann-minor    {{ color: #5c4a00; }}
  .apex-ann-global.apex-ann-info     {{ color: #003d99; }}
  .apex-ann-global.apex-ann-pmd      {{ color: #5500aa; }}
</style>
{global_banners_html}<pre class="line-numbers" style="max-height:80vh;overflow:auto;">
<code class="language-java">{html.escape(code_preview)}</code></pre>
<script>
(function() {{
  var ANNOTATIONS = {ann_json};
  function inject() {{
    var code = document.querySelector('pre.line-numbers code.language-java');
    if (!code) return;
    var lines = code.innerHTML.split('\\n');
    var out = [];
    for (var i = 0; i < lines.length; i++) {{
      out.push(lines[i]);
      var anns = ANNOTATIONS[i + 1];
      if (anns) {{
        for (var j = 0; j < anns.length; j++) {{
          var a = anns[j];
          var cls = 'apex-ann apex-ann-' + a.severity.toLowerCase();
          var icon = a.source === 'pmd' ? '🔍' : '⚠';
          var detail = a.priority ? ' [P' + a.priority + ']' : '';
          out.push('<span class="' + cls + '">' + icon + ' <strong>' + a.title + detail + '</strong> — ' + a.message + '</span>');
        }}
      }}
    }}
    code.innerHTML = out.join('\\n');
    if (window.Prism) window.Prism.highlightElement(code);
  }}
  if (document.readyState === 'loading') {{
    document.addEventListener('DOMContentLoaded', inject);
  }} else {{
    inject();
  }}
}})();
</script>
"""
    dependency_rows = render_apex_dependency_rows(dependencies, current_path, apex_pages)
    dependency_graph = render_apex_dependency_graph(artifact, dependencies)
    pmd_rows = render_pmd_rows(pmd_violations)
    summary_html = (
        f"<p>{html_value(review.summary)}</p>"
        "<div class='section'><h3>Alertes analyseur</h3>"
        + analyzer_inline_summary
        + "</div>"
    )
    tabs = tabbed_sections(
        f"apex-{safe_slug(artifact.name)}",
        [
            ("Resume", summary_html),
            ("Metriques", f"<ul>{metrics}</ul>"),
            ("Points forts", positives),
            ("Heuristiques", improvements),
            ("Analyseur", analyzer_tab),
            (
                "PMD",
                f"<table><thead><tr><th>Regle</th><th>Ruleset</th><th>Priorite</th><th>Ligne</th><th>Message</th></tr></thead><tbody>{pmd_rows}</tbody></table>",
            ),
            (
                "Liens",
                f"<table><thead><tr><th>Composant lie</th><th>Categorie</th><th>Sous-type</th><th>Sens</th><th>Nature du lien</th></tr></thead><tbody>{dependency_rows}</tbody></table>",
            ),
            ("Graphe", dependency_graph),
            (
                "Code source",
                code_tab_html,
            ),
        ],
    )
    body = f"""
{index_back_link(current_path, output_dir, "apex-trigger")}
<h1>{html_value(artifact.name)}</h1>
<span class="badge">{html_value(artifact.kind)}</span>
{tabs}
"""
    return render_page(artifact.name, body, current_path, assets_dir, include_prism=True)


def write_apex_pages(
    snapshot: MetadataSnapshot,
    reviews: dict[str, ReviewResult],
    pmd_results: dict[str, list[PmdViolation]],
    apex_dir: Path,
    output_dir: Path,
    assets_dir: Path,
    log: LogCallback,
    *,
    analyzer_report=None,
) -> dict[str, Path]:
    artifacts = snapshot.apex_artifacts
    output: dict[str, Path] = {}
    for artifact in artifacts:
        filename = f"{safe_slug(artifact.name)}.html"
        output[artifact.name] = apex_dir / filename

    reference_index = build_apex_reference_index(artifacts)
    trigger_objects = {artifact.name: trigger_object_name(artifact) for artifact in artifacts}
    object_names = [item.api_name for item in snapshot.objects]
    flow_names = [item.name for item in snapshot.flows]
    apex_findings = getattr(analyzer_report, "apex", {}) if analyzer_report else {}
    for artifact in artifacts:
        path = output[artifact.name]
        dependencies = apex_dependencies(
            artifact,
            artifacts,
            reference_index,
            trigger_objects,
            object_names,
            flow_names,
        )
        write_text(
            path,
            render_apex_page(
                artifact,
                reviews[artifact.name],
                path,
                output_dir,
                assets_dir,
                output,
                dependencies,
                pmd_results.get(artifact.name, []),
                apex_findings.get(artifact.name, []),
            ),
        )
    log(f"{len(output)} page(s) Apex/Trigger generee(s).")
    return output
