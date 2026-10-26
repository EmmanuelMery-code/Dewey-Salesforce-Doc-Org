"""Facts pulled from the source folder and the generated documentation.

The Discussion documents do not ask the model to browse the disk. Dewey
reads the two folders configured on the Documentation tab, then hands the
model a bounded brief it can actually ground its answer on.
"""

from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from src.core.models import (
    ApexArtifact,
    FieldInfo,
    FlowInfo,
    MetadataSnapshot,
    ObjectInfo,
    ValidationRuleInfo,
)
from src.core.utils import child_text, parse_xml

_MAX_BUSINESS_FACTS = 48_000
_MAX_DOC_EXCERPT = 12_000
_MAX_SKELETON = 48_000
_MAX_FINDINGS = 120

_BYPASS_RE = re.compile(
    r"bypass|by_pass|skipvalidation|skiptrigger|mutetrigger|"
    r"automationbypass|isbypassed|\$permission\.|\$setup\.",
    re.IGNORECASE,
)
_TRIGGER_ON_RE = re.compile(r"\btrigger\s+\w+\s+on\s+(\w+)", re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")
_SCRIPT_RE = re.compile(r"<(script|style)\b[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)

FAMILY_PICKLIST = "picklist"
FAMILY_FLOW = "flow"
FAMILY_APEX = "apex"
FAMILY_VALIDATION = "validation"
FAMILY_BYPASS = "bypass"
FAMILY_OTHER = "other"
_FAMILY_ORDER = (
    FAMILY_PICKLIST,
    FAMILY_FLOW,
    FAMILY_APEX,
    FAMILY_VALIDATION,
    FAMILY_BYPASS,
    FAMILY_OTHER,
)

_FAMILY_LABELS = {
    "fr": {
        FAMILY_PICKLIST: "Listes de valeurs identiques non globales",
        FAMILY_FLOW: "Flows",
        FAMILY_APEX: "Apex",
        FAMILY_VALIDATION: "Règles de validation",
        FAMILY_BYPASS: "Bypass",
        FAMILY_OTHER: "Autres",
    },
    "en": {
        FAMILY_PICKLIST: "Identical picklists that are not global",
        FAMILY_FLOW: "Flows",
        FAMILY_APEX: "Apex",
        FAMILY_VALIDATION: "Validation rules",
        FAMILY_BYPASS: "Bypass",
        FAMILY_OTHER: "Other",
    },
}


@dataclass
class BusinessBrief:
    """Grounding text for the business document, plus gaps for the fallback."""

    digest: str
    gaps: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class _Finding:
    object_api: str
    object_label: str
    family: str
    fact: str


def _english(language: str) -> bool:
    return (language or "").lower().startswith("en")


def _msg(language: str, french: str, english: str, **values: object) -> str:
    template = english if _english(language) else french
    return template.format(**values)


def _family_label(language: str, family: str) -> str:
    labels = _FAMILY_LABELS["en" if _english(language) else "fr"]
    return labels[family]


def documentation_ready(documentation_dir: str | Path | None) -> bool:
    """True when the output folder already holds generated HTML."""

    path = _as_dir(documentation_dir)
    if path is None:
        return False
    if (path / "html" / "index.html").is_file():
        return True
    objects = path / "html" / "objects"
    return objects.is_dir() and any(objects.glob("*.html"))


def read_documentation_excerpt(documentation_dir: str | Path | None, language: str = "fr") -> str:
    """Plain-text sample of the generated HTML, bounded for the model."""

    path = _as_dir(documentation_dir)
    if path is None:
        return _msg(
            language,
            "Dossier de sortie introuvable.",
            "Output folder not found.",
        )
    if not documentation_ready(path):
        inventory = _output_inventory(path)
        return _msg(
            language,
            "Documentation HTML absente du dossier de sortie ({inventory}).",
            "Generated HTML is missing from the output folder ({inventory}).",
            inventory=inventory,
        )

    chunks: list[str] = [_output_inventory(path)]
    used = len(chunks[0])
    index_text = _html_file_text(path / "html" / "index.html", 3500)
    if index_text:
        chunks.append("index.html : " + index_text)
        used += len(chunks[-1])

    for folder, per_file, file_cap in (
        ("objects", 900, 20),
        ("flows", 700, 8),
        ("apex", 500, 6),
    ):
        directory = path / "html" / folder
        if not directory.is_dir():
            continue
        for html_path in sorted(directory.glob("*.html"))[:file_cap]:
            if used >= _MAX_DOC_EXCERPT:
                break
            text = _html_file_text(html_path, per_file)
            if not text:
                continue
            piece = f"{folder}/{html_path.name} : {text}"
            chunks.append(piece)
            used += len(piece)
    excerpt = "\n".join(chunks).strip()
    if len(excerpt) > _MAX_DOC_EXCERPT:
        excerpt = excerpt[:_MAX_DOC_EXCERPT] + "\n[...]"
    return excerpt


def build_business_brief(
    snapshot: MetadataSnapshot,
    documentation_dir: str | Path | None,
    *,
    alias: str,
    source_dir: str,
    language: str = "fr",
) -> BusinessBrief:
    """Describe the org in business terms, from metadata plus generated HTML."""

    gaps = collect_business_gaps(
        snapshot,
        documentation_ready=documentation_ready(documentation_dir),
        language=language,
    )
    parts: list[str] = [
        _msg(
            language,
            "Alias : {alias}\nDossier source : {source}\nDossier de sortie : {output}",
            "Alias: {alias}\nSource folder: {source}\nOutput folder: {output}",
            alias=alias,
            source=source_dir or "-",
            output=str(documentation_dir or "-"),
        ),
        _metrics_line(snapshot, language),
        _applications_block(snapshot, language),
        _objects_block(snapshot, language, gaps),
        _flows_block(snapshot, language),
        _msg(language, "## Documentation générée", "## Generated documentation"),
        read_documentation_excerpt(documentation_dir, language),
        _msg(language, "## Lacunes repérées", "## Detected gaps"),
    ]
    if gaps:
        parts.extend(f"- {gap}" for gap in gaps)
    else:
        parts.append(
            _msg(
                language,
                "- Aucune lacune automatique.",
                "- No automatic gap.",
            )
        )
    digest = "\n\n".join(part for part in parts if part.strip())
    if len(digest) > _MAX_BUSINESS_FACTS + _MAX_DOC_EXCERPT:
        digest = digest[: _MAX_BUSINESS_FACTS + _MAX_DOC_EXCERPT] + "\n\n[...]"
    return BusinessBrief(digest=digest, gaps=gaps)


def build_maintainability_skeleton(
    snapshot: MetadataSnapshot,
    documentation_dir: str | Path | None,
    *,
    alias: str,
    source_dir: str,
    language: str = "fr",
) -> str:
    """Outline corrections by object, then by family, before the model rewrites it."""

    findings = _collect_findings(snapshot, language)
    title = _msg(
        language,
        f"# Corrections de maintenabilité — {alias}",
        f"# Maintainability corrections — {alias}",
    )
    intro = _msg(
        language,
        "Faits extraits du dossier source `{source}` et du dossier de sortie `{output}`. "
        "Ne corriger que ce qui est listé.",
        "Facts extracted from the source folder `{source}` and the output folder `{output}`. "
        "Only correct what is listed.",
        source=source_dir or "-",
        output=str(documentation_dir or "-"),
    )
    lines = [title, "", intro, ""]
    if not findings:
        lines.append(_object_heading("Transverse" if not _english(language) else "Cross-cutting", ""))
        lines.append(f"### {_family_label(language, FAMILY_OTHER)}")
        lines.append(
            "- "
            + _msg(
                language,
                "Aucun écart de maintenabilité n'a été détecté automatiquement "
                "(listes locales dupliquées, flows, Apex, validations, bypass).",
                "No maintainability gap was detected automatically "
                "(duplicated local picklists, flows, Apex, validations, bypass).",
            )
        )
    else:
        grouped: dict[str, dict[str, list[_Finding]]] = defaultdict(lambda: defaultdict(list))
        labels: dict[str, str] = {}
        for finding in findings[:_MAX_FINDINGS]:
            grouped[finding.object_api][finding.family].append(finding)
            labels[finding.object_api] = finding.object_label
        for api in sorted(grouped, key=_object_sort_key):
            lines.append(_object_heading(api, labels.get(api, "")))
            families = grouped[api]
            for family in _FAMILY_ORDER:
                items = families.get(family) or []
                if not items:
                    continue
                lines.append(f"### {_family_label(language, family)}")
                for item in items:
                    lines.append(f"- {item.fact}")
            lines.append("")
        if len(findings) > _MAX_FINDINGS:
            lines.append(
                _msg(
                    language,
                    f"_Extrait limité aux {_MAX_FINDINGS} premiers constats._",
                    f"_Excerpt limited to the first {_MAX_FINDINGS} findings._",
                )
            )
    skeleton = "\n".join(lines).strip() + "\n"
    if len(skeleton) > _MAX_SKELETON:
        skeleton = skeleton[:_MAX_SKELETON] + "\n\n[...]\n"
    return skeleton


def collect_business_gaps(
    snapshot: MetadataSnapshot,
    *,
    documentation_ready: bool,
    language: str = "fr",
) -> list[str]:
    """Concrete openings the remaining-work section can cite."""

    gaps: list[str] = []
    if not documentation_ready:
        gaps.append(
            _msg(
                language,
                "La documentation HTML (index.html) est absente du dossier de sortie.",
                "The generated HTML (index.html) is missing from the output folder.",
            )
        )
    undescribed_flows = [flow.name for flow in snapshot.flows if not (flow.description or "").strip()]
    if undescribed_flows:
        sample = ", ".join(undescribed_flows[:8])
        gaps.append(
            _msg(
                language,
                "{count} flow(s) sans description, dont {sample}.",
                "{count} flow(s) have no description, including {sample}.",
                count=len(undescribed_flows),
                sample=sample,
            )
        )
    for obj in snapshot.objects:
        if len(gaps) >= 30:
            break
        if obj.is_virtual:
            gaps.append(
                _msg(
                    language,
                    "L'objet {api} est encore en conception.",
                    "Object {api} is still being designed.",
                    api=obj.api_name,
                )
            )
        if (obj.deployment_status or "").lower() in {"indevelopment", "in development"}:
            gaps.append(
                _msg(
                    language,
                    "L'objet {api} est encore au statut InDevelopment.",
                    "Object {api} is still InDevelopment.",
                    api=obj.api_name,
                )
            )
        if obj.custom and not (obj.description or obj.dewey_comment or "").strip():
            gaps.append(
                _msg(
                    language,
                    "L'objet {api} ({label}) n'a pas de description métier.",
                    "Object {api} ({label}) has no business description.",
                    api=obj.api_name,
                    label=obj.label or obj.api_name,
                )
            )
    return gaps[:30]


def _collect_findings(snapshot: MetadataSnapshot, language: str) -> list[_Finding]:
    findings: list[_Finding] = []
    findings.extend(_picklist_findings(snapshot, language))
    findings.extend(_validation_findings(snapshot, language))
    findings.extend(_flow_findings(snapshot, language))
    findings.extend(_apex_findings(snapshot, language))
    return findings


def _picklist_findings(snapshot: MetadataSnapshot, language: str) -> list[_Finding]:
    locals_by_sig: dict[tuple[str, ...], list[tuple[ObjectInfo, FieldInfo]]] = defaultdict(list)
    globals_by_sig: dict[tuple[str, ...], set[str]] = defaultdict(set)
    for obj in snapshot.objects:
        for field_info in obj.fields:
            if not field_info.is_picklist:
                continue
            signature = _picklist_signature(field_info)
            if len(signature) < 2:
                continue
            if field_info.picklist_is_global:
                globals_by_sig[signature].add(field_info.picklist_global_name or "?")
            else:
                locals_by_sig[signature].append((obj, field_info))

    findings: list[_Finding] = []
    for signature, group in locals_by_sig.items():
        global_names = globals_by_sig.get(signature, set())
        if len(group) < 2 and not global_names:
            continue
        for obj, field_info in group:
            peers = [
                f"{other.api_name}.{other_field.api_name}"
                for other, other_field in group
                if not (other.api_name == obj.api_name and other_field.api_name == field_info.api_name)
            ]
            shown = (field_info.picklist_values or list(signature))[:10]
            values = ", ".join(shown)
            if len(field_info.picklist_values or signature) > 10:
                values += ", ..."
            if peers:
                fact = _msg(
                    language,
                    "Le champ {field} ({label}) porte une liste locale ({values}) identique à {peers}. "
                    "Elle devrait être une liste de valeurs globale partagée.{global_note}",
                    "Field {field} ({label}) carries a local picklist ({values}) identical to {peers}. "
                    "It should be a shared global value set.{global_note}",
                    field=field_info.api_name,
                    label=field_info.label or field_info.api_name,
                    values=values,
                    peers=", ".join(peers),
                    global_note=(
                        _msg(
                            language,
                            " Les mêmes valeurs existent aussi dans {names}.",
                            " The same values also exist in {names}.",
                            names=", ".join(sorted(global_names)),
                        )
                        if global_names
                        else ""
                    ),
                )
            else:
                fact = _msg(
                    language,
                    "Le champ {field} ({label}) redéfinit en local les valeurs ({values}) "
                    "déjà portées par la liste globale {names}. Il faut référencer cette liste globale.",
                    "Field {field} ({label}) redefines locally the values ({values}) "
                    "already carried by the global value set {names}. Reference that global set instead.",
                    field=field_info.api_name,
                    label=field_info.label or field_info.api_name,
                    values=values,
                    names=", ".join(sorted(global_names)),
                )
            findings.append(
                _Finding(obj.api_name, obj.label or obj.api_name, FAMILY_PICKLIST, fact)
            )
    return findings


def _validation_findings(snapshot: MetadataSnapshot, language: str) -> list[_Finding]:
    findings: list[_Finding] = []
    for obj in snapshot.objects:
        kept = 0
        for rule in obj.validation_rules:
            if not rule.active or kept >= 4:
                continue
            fact = _validation_fact(rule, language)
            if not fact:
                continue
            family = FAMILY_BYPASS if _BYPASS_RE.search(rule.error_condition_formula or "") else FAMILY_VALIDATION
            findings.append(_Finding(obj.api_name, obj.label or obj.api_name, family, fact))
            kept += 1
    return findings


def _validation_fact(rule: ValidationRuleInfo, language: str) -> str:
    formula = rule.error_condition_formula or ""
    message = (rule.error_message or rule.description or "").strip()[:180]
    if _BYPASS_RE.search(formula):
        snippet = " ".join(formula.split())[:240]
        return _msg(
            language,
            "Règle {name} : contournement codé dans la formule ({snippet}). Message : {message}.",
            "Rule {name}: bypass encoded in the formula ({snippet}). Message: {message}.",
            name=rule.full_name,
            snippet=snippet or "-",
            message=message or "-",
        )
    if rule.complexity_score >= 8:
        return _msg(
            language,
            "Règle {name} : formule difficile à maintenir (score {score}). Message : {message}.",
            "Rule {name}: formula that is hard to maintain (score {score}). Message: {message}.",
            name=rule.full_name,
            score=rule.complexity_score,
            message=message or "-",
        )
    return ""


def _flow_findings(snapshot: MetadataSnapshot, language: str) -> list[_Finding]:
    ranked = sorted(snapshot.flows, key=lambda flow: flow.complexity_score, reverse=True)
    findings: list[_Finding] = []
    for flow in ranked:
        if len(findings) >= 25:
            break
        issues = _flow_issues(flow, language)
        if not issues:
            continue
        api = flow.start_object or ("Transverse" if not _english(language) else "Cross-cutting")
        label = api
        for obj in snapshot.objects:
            if obj.api_name == api:
                label = obj.label or api
                break
        findings.append(
            _Finding(
                api,
                label,
                FAMILY_BYPASS if any("bypass" in issue.lower() for issue in issues) else FAMILY_FLOW,
                _msg(
                    language,
                    "Flow {name} ({label}) sur {object}, type {process}, statut {status} : {issues}.",
                    "Flow {name} ({label}) on {object}, type {process}, status {status}: {issues}.",
                    name=flow.name,
                    label=flow.label or flow.name,
                    object=flow.start_object or "-",
                    process=flow.process_type or "-",
                    status=flow.status or "-",
                    issues=" ; ".join(issues),
                ),
            )
        )
    return findings


def _flow_issues(flow: FlowInfo, language: str) -> list[str]:
    issues: list[str] = []
    if flow.complexity_level in {"Complexe", "Tres complexe"}:
        issues.append(
            _msg(
                language,
                "complexité {level} (score {score})",
                "complexity {level} (score {score})",
                level=flow.complexity_level,
                score=flow.complexity_score,
            )
        )
    unprotected = len(flow.unprotected_fault_elements)
    if unprotected:
        issues.append(
            _msg(
                language,
                "{count} élément(s) sans chemin d'erreur",
                "{count} element(s) without a fault path",
                count=unprotected,
            )
        )
    if flow.dml_in_loop:
        issues.append(_msg(language, "DML dans une boucle", "DML inside a loop"))
    if flow.soql_in_loop:
        issues.append(_msg(language, "lecture d'enregistrements dans une boucle", "record lookup inside a loop"))
    blob = " ".join(
        [flow.name, flow.label, flow.description]
        + [f"{element.name} {element.label} {element.description}" for element in flow.elements[:40]]
    )
    if _BYPASS_RE.search(blob):
        issues.append(
            _msg(
                language,
                "le nom, la description ou un élément évoque un bypass à cadrer",
                "the name, description or an element points to a bypass that should be tightened",
            )
        )
    return issues


def _apex_findings(snapshot: MetadataSnapshot, language: str) -> list[_Finding]:
    findings: list[_Finding] = []
    known = {obj.api_name for obj in snapshot.objects}
    classes = [
        artifact
        for artifact in snapshot.apex_artifacts
        if artifact.kind == "class" and not artifact.is_test and not artifact.is_interface
    ]
    no_sharing = [artifact for artifact in classes if not (artifact.sharing_declaration or "").strip()]
    if no_sharing:
        names = ", ".join(artifact.name for artifact in no_sharing[:12])
        findings.append(
            _Finding(
                "Transverse" if not _english(language) else "Cross-cutting",
                "",
                FAMILY_APEX,
                _msg(
                    language,
                    "{count} classe(s) sans déclaration de partage : {names}.",
                    "{count} class(es) with no sharing declaration: {names}.",
                    count=len(no_sharing),
                    names=names,
                ),
            )
        )

    emitted = 0
    for artifact in snapshot.apex_artifacts:
        if artifact.is_test or emitted >= 25:
            continue
        target = _apex_object(artifact, known, language)
        label = target
        for obj in snapshot.objects:
            if obj.api_name == target:
                label = obj.label or target
                break
        if artifact.query_in_loop or artifact.dml_in_loop:
            issue = _msg(
                language,
                "requête SOQL dans une boucle" if artifact.query_in_loop else "DML dans une boucle",
                "SOQL query inside a loop" if artifact.query_in_loop else "DML inside a loop",
            )
            if artifact.query_in_loop and artifact.dml_in_loop:
                issue = _msg(
                    language,
                    "SOQL et DML dans une boucle",
                    "SOQL and DML inside a loop",
                )
            findings.append(
                _Finding(
                    target,
                    label,
                    FAMILY_APEX,
                    _msg(
                        language,
                        "{kind} {name} : {issue}.",
                        "{kind} {name}: {issue}.",
                        kind=artifact.kind,
                        name=artifact.name,
                        issue=issue,
                    ),
                )
            )
            emitted += 1
        snippet = _bypass_snippet(artifact)
        if snippet:
            findings.append(
                _Finding(
                    target,
                    label,
                    FAMILY_BYPASS,
                    _msg(
                        language,
                        "{kind} {name} : contournement repéré ({snippet}).",
                        "{kind} {name}: bypass found ({snippet}).",
                        kind=artifact.kind,
                        name=artifact.name,
                        snippet=snippet,
                    ),
                )
            )
            emitted += 1
    return findings


def _apex_object(artifact: ApexArtifact, known: set[str], language: str) -> str:
    fallback = "Transverse" if not _english(language) else "Cross-cutting"
    if artifact.kind == "trigger":
        match = _TRIGGER_ON_RE.search((artifact.body or "")[:800])
        if match:
            return match.group(1)
    for api in sorted(known, key=len, reverse=True):
        if api and api in artifact.name:
            return api
    return fallback


def _bypass_snippet(artifact: ApexArtifact) -> str:
    hits: list[str] = []
    for line in (artifact.body or "").splitlines():
        if _BYPASS_RE.search(line):
            hits.append(line.strip()[:180])
            if len(hits) >= 2:
                break
    return " | ".join(hits)


def _picklist_signature(field_info: FieldInfo) -> tuple[str, ...]:
    raw = field_info.picklist_values or field_info.picklist_api_names
    return tuple(sorted({value.strip().casefold() for value in raw if value and value.strip()}))


def _object_heading(api: str, label: str) -> str:
    if not label or label == api or api in {"Transverse", "Cross-cutting"}:
        return f"## {api}"
    return f"## {api} — {label}"


def _object_sort_key(api: str) -> tuple[int, str]:
    if api in {"Transverse", "Cross-cutting"}:
        return (2, api.lower())
    if api.endswith("__c") or api.endswith("__mdt") or api.endswith("__e"):
        return (0, api.lower())
    return (1, api.lower())


def _metrics_line(snapshot: MetadataSnapshot, language: str) -> str:
    metrics = snapshot.metrics
    custom = sum(1 for obj in snapshot.objects if obj.custom)
    return _msg(
        language,
        "Volumes : {objects} objet(s) dont {custom} personnalisé(s), {flows} flow(s), "
        "{apex} artefact(s) Apex, {rules} règle(s) de validation.",
        "Volumes: {objects} object(s) including {custom} custom, {flows} flow(s), "
        "{apex} Apex artifact(s), {rules} validation rule(s).",
        objects=len(snapshot.objects),
        custom=custom,
        flows=len(snapshot.flows) or metrics.flows,
        apex=len(snapshot.apex_artifacts) or metrics.apex_classes,
        rules=sum(len(obj.validation_rules) for obj in snapshot.objects) or metrics.validation_rules,
    )


def _applications_block(snapshot: MetadataSnapshot, language: str) -> str:
    lines = [_msg(language, "## Applications", "## Applications")]
    seen: set[Path] = set()
    roots = list(snapshot.package_roots) or [snapshot.source_dir]
    found = False
    for root in roots:
        for path in sorted(Path(root).glob("applications/*.app-meta.xml")):
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            try:
                node = parse_xml(path)
            except (OSError, ValueError, ET.ParseError):
                continue
            label = child_text(node, "label") or path.name
            description = child_text(node, "description")
            line = f"- {label}"
            if description:
                line += f" : {description.strip()[:240]}"
            lines.append(line)
            found = True
    if not found:
        lines.append(_msg(language, "- Aucune application personnalisée lue.", "- No custom application was read."))
    return "\n".join(lines)


def _objects_block(snapshot: MetadataSnapshot, language: str, gaps: list[str]) -> str:
    lines = [_msg(language, "## Objets", "## Objects")]
    detailed: list[ObjectInfo] = []
    listed: list[ObjectInfo] = []
    for obj in snapshot.objects:
        if obj.api_name.endswith("__mdt") or obj.api_name.endswith("__e"):
            listed.append(obj)
            continue
        custom_fields = [item for item in obj.fields if item.custom]
        if obj.custom or obj.is_virtual or custom_fields or obj.record_types or obj.validation_rules:
            detailed.append(obj)
    if listed:
        names = ", ".join(obj.api_name for obj in listed[:30])
        lines.append(
            _msg(
                language,
                "Métadonnées personnalisées et événements (liste courte) : {names}.",
                "Custom metadata and events (short list): {names}.",
                names=names,
            )
        )
    used = 0
    shown = 0
    for obj in detailed:
        if used > 32_000 or shown >= 60:
            remaining = len(detailed) - shown
            if remaining > 0:
                note = _msg(
                    language,
                    "{count} objet(s) supplémentaire(s) n'ont pas été détaillés dans l'extrait.",
                    "{count} further object(s) were not detailed in the excerpt.",
                    count=remaining,
                )
                lines.append(note)
                if note not in gaps and len(gaps) < 30:
                    gaps.append(note)
            break
        block = _format_object(obj, language)
        lines.append(block)
        used += len(block)
        shown += 1
    if shown == 0:
        lines.append(_msg(language, "Aucun objet métier détaillé.", "No business object was detailed."))
    return "\n\n".join(lines)


def _format_object(obj: ObjectInfo, language: str) -> str:
    lines = [_object_heading(obj.api_name, obj.label).replace("## ", "### ", 1)]
    description = (obj.description or obj.dewey_comment or "").strip()
    lines.append(
        _msg(
            language,
            "Description : {text}",
            "Description: {text}",
            text=(description[:500] if description else _msg(language, "(absente)", "(missing)")),
        )
    )
    if obj.record_types:
        labels = ", ".join(_record_label(record, language) for record in obj.record_types[:12])
        lines.append(_msg(language, "Types d'enregistrement : {labels}", "Record types: {labels}", labels=labels))
    custom_fields = [item for item in obj.fields if item.custom or item.is_picklist or item.reference_to]
    if custom_fields:
        lines.append(_msg(language, "Champs utiles :", "Useful fields:"))
        ordered = sorted(custom_fields, key=lambda item: (not bool(item.description), item.api_name))
        for field_info in ordered[:20]:
            lines.append("- " + _format_field(field_info, language))
        extra = len(ordered) - 20
        if extra > 0:
            lines.append(
                _msg(language, "- ... {count} autres champs", "- ... {count} more fields", count=extra)
            )
    active_rules = [rule for rule in obj.validation_rules if rule.active]
    if active_rules:
        lines.append(_msg(language, "Messages de règles :", "Rule messages:"))
        for rule in active_rules[:6]:
            message = (rule.error_message or rule.description or rule.full_name).strip()[:200]
            lines.append(f"- {rule.full_name} : {message}")
    return "\n".join(lines)


def _record_label(record, language: str) -> str:
    label = record.label or record.full_name
    if record.active:
        return label
    suffix = " [inactive]" if _english(language) else " [inactif]"
    return label + suffix


def _format_field(field_info: FieldInfo, language: str) -> str:
    extra = ""
    if field_info.reference_to:
        extra = " -> " + ", ".join(field_info.reference_to)
    elif field_info.is_picklist:
        values = ", ".join((field_info.picklist_values or [])[:8])
        if field_info.picklist_is_global:
            scope = _msg(
                language,
                "liste globale {name}",
                "global value set {name}",
                name=field_info.picklist_global_name or "?",
            )
        else:
            scope = _msg(language, "liste locale", "local picklist")
        extra = f" {scope} [{values}]"
    description = f" — {field_info.description.strip()[:160]}" if field_info.description else ""
    return (
        f"{field_info.label or field_info.api_name} "
        f"({field_info.api_name}, {field_info.data_type or '?'}{extra}){description}"
    )


def _flows_block(snapshot: MetadataSnapshot, language: str) -> str:
    lines = [_msg(language, "## Parcours (flows)", "## Journeys (flows)")]
    if not snapshot.flows:
        lines.append(_msg(language, "- Aucun flow.", "- No flow."))
        return "\n".join(lines)
    ordered = sorted(
        snapshot.flows,
        key=lambda flow: (not bool((flow.description or "").strip()), flow.name.lower()),
    )
    for flow in ordered[:40]:
        line = _msg(
            language,
            "- {label} ({name}) sur {object}, type {process}, statut {status}",
            "- {label} ({name}) on {object}, type {process}, status {status}",
            label=flow.label or flow.name,
            name=flow.name,
            object=flow.start_object or "-",
            process=flow.process_type or "-",
            status=flow.status or "-",
        )
        if (flow.description or "").strip():
            line += ". " + flow.description.strip()[:240]
        lines.append(line)
    hidden = len(snapshot.flows) - min(len(snapshot.flows), 40)
    if hidden > 0:
        lines.append(_msg(language, "- ... {count} autres flows", "- ... {count} more flows", count=hidden))
    return "\n".join(lines)


def _output_inventory(path: Path) -> str:
    bits: list[str] = []
    for name in ("html", "excel", "word"):
        folder = path / name
        if not folder.is_dir():
            continue
        count = 0
        for _file in folder.rglob("*"):
            if _file.is_file():
                count += 1
                if count >= 5000:
                    break
        bits.append(f"{name}/ : {count} fichier(s)")
    index = path / "html" / "index.html"
    bits.append("index.html présent" if index.is_file() else "index.html absent")
    return " ; ".join(bits) if bits else "dossier de sortie vide"


def _html_file_text(path: Path, limit: int) -> str:
    if not path.is_file():
        return ""
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")[:150_000]
    except OSError:
        return ""
    return _html_to_text(raw, limit)


def _html_to_text(raw: str, limit: int) -> str:
    raw = _SCRIPT_RE.sub(" ", raw)
    text = html.unescape(_TAG_RE.sub(" ", raw))
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def _as_dir(value: str | Path | None) -> Path | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    path = Path(text)
    if not path.is_dir():
        return None
    return path
