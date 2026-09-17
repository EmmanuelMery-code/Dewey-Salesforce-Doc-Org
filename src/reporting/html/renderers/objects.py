"""Render the per-object documentation pages."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Callable

from src.analyzer.models import Finding
from src.core.models import MetadataSnapshot, ObjectInfo, Dependency
from src.core.utils import html_value, safe_slug, write_text
from src.reporting.html_mermaid import (
    object_mermaid,
    validation_rule_mermaid,
)

from src.reporting.html.dependencies import (
    object_dependencies,
    field_dependencies,
    render_dependency_rows,
)
from src.reporting.html.findings import (
    render_analyzer_tab,
    render_findings_summary,
    render_security_rows,
    security_rows,
)
from src.reporting.html.one_page import render_one_page_graph
from src.reporting.html.page_shell import (
    index_back_link,
    render_page,
    tabbed_sections,
)
from src.reporting.i18n import t


LogCallback = Callable[[str], None]


# The Data Dictionary screen may hand these renderers objects and fields the
# user only declared as being designed (see
# :class:`~src.core.data_dictionary_selection.DataDictionarySelection`). They
# belong to the Excel and Word dictionaries only, so the HTML site drops them
# before anything is rendered or counted.


def real_objects(objects: list[ObjectInfo]) -> list[ObjectInfo]:
    return [item for item in objects if not item.is_virtual]


def _without_virtual_fields(item: ObjectInfo) -> ObjectInfo:
    if not any(field.is_virtual for field in item.fields):
        return item
    return replace(item, fields=[field for field in item.fields if not field.is_virtual])


def render_object_body(
    item: ObjectInfo,
    snapshot: MetadataSnapshot,
    current_path: Path,
    output_dir: Path,
    assets_dir: Path,
    object_findings: list[Finding] | None = None,
    validation_findings: list[Finding] | None = None,
    all_dependencies: list[Dependency] | None = None,
    link_maps: dict[str, dict[str, Path]] | None = None,
    *,
    include_comment: bool = True,
    include_piloted_by: bool = True,
    include_status: bool = True,
    include_squad: bool = True,
    include_squad_consumer: bool = True,
    concat_description: bool = True,
) -> str:
    object_findings = object_findings or []
    validation_findings = validation_findings or []
    all_dependencies = all_dependencies or []
    link_maps = link_maps or {}
    # Dropped up front so every field table, count and diagram below sees the
    # same list the page actually shows.
    item = _without_virtual_fields(item)

    profiles = security_rows(snapshot.profiles, item.api_name)
    permsets = security_rows(snapshot.permission_sets, item.api_name)
    
    # Impact Analysis (Where it's used)
    used_rows = object_dependencies(item.api_name, all_dependencies)
    impact_table = render_dependency_rows(used_rows, current_path, link_maps)

    fields_rows_list = []
    for field in item.fields:
        field_full_name = f"{item.api_name}.{field.api_name}"
        f_deps = field_dependencies(field_full_name, all_dependencies)
        usage_badge = ""
        if f_deps:
            usage_badge = f" <span class='badge' title='{t('object_field_used_in', count=len(f_deps))}'>⚠ {len(f_deps)}</span>"
        
        fields_rows_list.append(
            f"<tr><td>{html_value(field.api_name)}{usage_badge}</td><td>{html_value(field.label)}</td>"
            f"<td>{html_value(field.data_type)}</td><td>{html_value(field.description)}</td>"
            f"<td>{t('value_yes') if field.required else t('value_no')}</td></tr>"
        )
    fields_rows = "".join(fields_rows_list) or f"<tr><td colspan='5' class='empty'>{t('object_fields_empty')}</td></tr>"

    record_type_rows = "".join(
        f"<tr><td>{html_value(record_type.full_name)}</td><td>{html_value(record_type.label)}</td>"
        f"<td>{html_value(record_type.description)}</td><td>{t('value_yes') if record_type.active else t('value_no')}</td></tr>"
        for record_type in item.record_types
    ) or f"<tr><td colspan='4' class='empty'>{t('object_record_types_empty')}</td></tr>"

    description_rows = [
        (t("object_meta_api_name"), item.api_name),
        ("Label", item.label),
        (t("object_meta_plural_label"), item.plural_label),
        ("Description", item.description),
        ("Deployment status", item.deployment_status),
        ("Sharing model", item.sharing_model),
        (t("object_meta_visibility"), item.visibility),
    ]
    if include_comment:
        comment_value = item.dewey_comment_combined if concat_description else (item.dewey_comment or "")
        description_rows.append((t("object_meta_dewey_comment"), comment_value))
    if include_piloted_by:
        description_rows.append((t("object_meta_piloted_by"), item.dewey_piloted_by))
    if include_status:
        description_rows.append(("Status", item.dewey_status))
    if include_squad:
        description_rows.append((t("object_meta_squad"), item.dewey_squad))
    if include_squad_consumer:
        description_rows.append((t("object_meta_squad_consumer"), item.dewey_squad_consumer))
    description_html = "".join(
        f"<li><strong>{html_value(label)}:</strong> {html_value(value or t('value_not_set'))}</li>"
        for label, value in description_rows
    )

    mermaid = object_mermaid(item)
    validation_rows = "".join(
        f"<tr><td>{html_value(vr.full_name)}</td><td>{t('value_yes') if vr.active else t('value_no')}</td>"
        f"<td>{html_value(vr.description)}</td><td>{html_value(vr.error_display_field)}</td>"
        f"<td>{html_value(vr.error_message)}</td></tr>"
        for vr in item.validation_rules
    ) or f"<tr><td colspan='5' class='empty'>{t('object_validation_rules_empty')}</td></tr>"

    validation_panels = []
    for vr in item.validation_rules:
        formula_html = f"<pre style='background:#f1f5f9; padding:12px; border-radius:6px; overflow:auto;'>{html_value(vr.error_condition_formula)}</pre>"
        mermaid_tree = validation_rule_mermaid(vr)
        validation_panels.append(
            f"<div class='section'><h3>{html_value(vr.full_name)}</h3>"
            f"<p><strong>{t('object_vr_description')}</strong> {html_value(vr.description or t('object_vr_description_not_set'))}</p>"
            f"<p><strong>{t('object_vr_error_message')}</strong> {html_value(vr.error_message)}</p>"
            f"<h4>{t('object_vr_decision_tree')}</h4>{mermaid_tree}"
            f"<h4>{t('object_vr_formula')}</h4>{formula_html}</div>"
        )
    validation_content = "".join(validation_panels) or f"<p class='empty'>{t('object_validation_details_empty')}</p>"

    relation_table = "".join(
        f"<tr><td>{html_value(rel.field_name)}</td><td>{html_value(rel.relationship_type)}</td>"
        f"<td>{html_value(', '.join(rel.targets))}</td></tr>"
        for rel in item.relationships
    ) or f"<tr><td colspan='3' class='empty'>{t('object_relationships_empty')}</td></tr>"

    profile_rows = render_security_rows(profiles, t("object_profiles_empty"))
    permset_rows = render_security_rows(permsets, t("object_permission_sets_empty"))

    one_page_graph = render_one_page_graph(
        item.api_name, "Objet", all_dependencies, safe_slug(item.api_name)
    )

    combined_findings = list(object_findings) + list(validation_findings)
    analyzer_summary_inline = render_findings_summary(combined_findings)
    analyzer_content = render_analyzer_tab(combined_findings)

    synthesis_html = (
        "<ul>" + description_html + "</ul>"
        + f"<div class='section'><h3>{t('detail_analyzer_alerts')}</h3>"
        + analyzer_summary_inline
        + "</div>"
    )

    security_headers = (
        f"<th>{t('security_th_read')}</th><th>{t('security_th_create')}</th>"
        f"<th>{t('security_th_edit')}</th><th>{t('security_th_delete')}</th>"
        f"<th>{t('security_th_visible_fields')}</th><th>{t('security_th_editable_fields')}</th>"
    )
    dependency_headers = (
        f"<th>{t('dependency_th_category')}</th><th>{t('dependency_th_subtype')}</th>"
        f"<th>{t('dependency_th_direction')}</th><th>{t('dependency_th_relation')}</th>"
    )

    tabs = tabbed_sections(
        f"object-{safe_slug(item.api_name)}",
        [
            (t("tab_synthesis"), synthesis_html),
            ("Fields", f"<table><thead><tr><th>Name</th><th>Label</th><th>Type</th><th>Description</th><th>Required</th></tr></thead><tbody>{fields_rows}</tbody></table>"),
            ("Profiles", f"<table><thead><tr><th>Profile</th>{security_headers}</tr></thead><tbody>{profile_rows}</tbody></table>"),
            ("Permission Sets", f"<table><thead><tr><th>Permission Set</th>{security_headers}</tr></thead><tbody>{permset_rows}</tbody></table>"),
            ("Record Types", f"<table><thead><tr><th>{t('object_th_name')}</th><th>Label</th><th>Description</th><th>{t('object_th_active')}</th></tr></thead><tbody>{record_type_rows}</tbody></table>"),
            ("Validation Rules", f"<table><thead><tr><th>{t('object_th_name')}</th><th>{t('object_th_active')}</th><th>Description</th><th>{t('object_th_error_field')}</th><th>{t('object_th_error_message')}</th></tr></thead><tbody>{validation_rows}</tbody></table><hr/>{validation_content}"),
            (t("tab_relationships"), f"{mermaid}<h4>{t('object_outgoing_relationships')}</h4><table><thead><tr><th>{t('object_th_relationship_field')}</th><th>Type</th><th>{t('object_th_relationship_target')}</th></tr></thead><tbody>{relation_table}</tbody></table><h4>{t('object_impact_analysis')}</h4><table><thead><tr><th>{t('dependency_th_component')}</th>{dependency_headers}</tr></thead><tbody>{impact_table}</tbody></table>"),
            ("One Page", one_page_graph),
            (t("tab_analyzer"), analyzer_content),
        ],
    )
    return f"""
<h1>{html_value(item.api_name)}</h1>
<div class="cards">
  <div class="card"><span>{t('object_card_fields')}</span><span class="value">{len(item.fields)}</span></div>
  <div class="card"><span>{t('object_card_record_types')}</span><span class="value">{len(item.record_types)}</span></div>
  <div class="card"><span>{t('object_card_validation_rules')}</span><span class="value">{len(item.validation_rules)}</span></div>
  <div class="card"><span>{t('object_card_relationships')}</span><span class="value">{len(item.relationships)}</span></div>
</div>
{tabs}
"""


def render_object_page(
    item: ObjectInfo,
    snapshot: MetadataSnapshot,
    current_path: Path,
    output_dir: Path,
    assets_dir: Path,
    object_findings: list[Finding] | None = None,
    validation_findings: list[Finding] | None = None,
    all_dependencies: list[Dependency] | None = None,
    link_maps: dict[str, dict[str, Path]] | None = None,
    *,
    include_comment: bool = True,
    include_piloted_by: bool = True,
    include_status: bool = True,
    include_squad: bool = True,
    include_squad_consumer: bool = True,
    concat_description: bool = True,
) -> str:
    body = f"""
{index_back_link(current_path, output_dir, "objets")}
{render_object_body(
        item,
        snapshot,
        current_path,
        output_dir,
        assets_dir,
        object_findings,
        validation_findings,
        all_dependencies,
        link_maps,
        include_comment=include_comment,
        include_piloted_by=include_piloted_by,
        include_status=include_status,
        include_squad=include_squad,
        include_squad_consumer=include_squad_consumer,
        concat_description=concat_description,
    )}
"""
    return render_page(item.api_name, body, current_path, assets_dir)


def render_combined_objects_page(
    snapshot: MetadataSnapshot,
    current_path: Path,
    output_dir: Path,
    assets_dir: Path,
    *,
    analyzer_report=None,
    include_comment: bool = True,
    include_piloted_by: bool = True,
    include_status: bool = True,
    include_squad: bool = True,
    include_squad_consumer: bool = True,
    concat_description: bool = True,
) -> str:
    object_findings = getattr(analyzer_report, "objects", {}) if analyzer_report else {}
    validation_findings = getattr(analyzer_report, "validation_rules", {}) if analyzer_report else {}
    
    bodies = []
    for item in real_objects(snapshot.objects):
        vr_findings_for_object: list[Finding] = []
        for vr in item.validation_rules:
            key = f"{item.api_name}.{vr.full_name}"
            vr_findings_for_object.extend(validation_findings.get(key, []))
            
        bodies.append(
            render_object_body(
                item,
                snapshot,
                current_path,
                output_dir,
                assets_dir,
                object_findings.get(item.api_name, []),
                vr_findings_for_object,
                include_comment=include_comment,
                include_piloted_by=include_piloted_by,
                include_status=include_status,
                include_squad=include_squad,
                include_squad_consumer=include_squad_consumer,
                concat_description=concat_description,
            )
        )
        bodies.append("<hr style='margin: 40px 0; border: 0; border-top: 2px solid #e2e8f0;'/>")
        
    body = "\n".join(bodies)
    return render_page("Data Dictionary", body, current_path, assets_dir)


def write_object_pages(
    snapshot: MetadataSnapshot,
    objects_dir: Path,
    output_dir: Path,
    assets_dir: Path,
    log: LogCallback,
    *,
    analyzer_report=None,
    apex_pages: dict[str, Path] | None = None,
    flow_pages: dict[str, Path] | None = None,
    include_comment: bool = True,
    include_piloted_by: bool = True,
    include_status: bool = True,
    include_squad: bool = True,
    include_squad_consumer: bool = True,
    concat_description: bool = True,
) -> dict[str, Path]:
    output: dict[str, Path] = {}
    object_findings = getattr(analyzer_report, "objects", {}) if analyzer_report else {}
    validation_findings = getattr(analyzer_report, "validation_rules", {}) if analyzer_report else {}
    
    link_maps = {
        "Apex": apex_pages or {},
        "Flow": flow_pages or {},
    }
    
    rendered_objects = real_objects(snapshot.objects)
    total = len(rendered_objects)
    for index, item in enumerate(rendered_objects):
        path = objects_dir / f"{item.api_name}.html"
        
        if index % 20 == 0:
            log(f"Generation HTML : objet {index + 1}/{total} ({item.api_name})")
            
        vr_findings_for_object: list[Finding] = []
        for vr in item.validation_rules:
            key = f"{item.api_name}.{vr.full_name}"
            vr_findings_for_object.extend(validation_findings.get(key, []))
        content = render_object_page(
            item,
            snapshot,
            path,
            output_dir,
            assets_dir,
            object_findings.get(item.api_name, []),
            vr_findings_for_object,
            all_dependencies=snapshot.dependencies,
            link_maps=link_maps,
            include_comment=include_comment,
            include_piloted_by=include_piloted_by,
            include_status=include_status,
            include_squad=include_squad,
            include_squad_consumer=include_squad_consumer,
            concat_description=concat_description,
        )
        write_text(path, content)
        output[item.api_name] = path
    log(f"{len(output)} page(s) objet generee(s).")
    return output
