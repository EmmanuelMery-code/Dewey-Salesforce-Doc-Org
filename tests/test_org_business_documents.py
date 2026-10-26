"""Business and maintainability Word documents built from org metadata."""

from __future__ import annotations

from pathlib import Path

from docx import Document

from src.ai.org_document_digest import (
    build_business_brief,
    build_maintainability_skeleton,
)
from src.core.models import (
    ApexArtifact,
    FieldInfo,
    FlowInfo,
    MetadataSnapshot,
    ObjectInfo,
    ValidationRuleInfo,
)
from src.reporting.markdown_docx import (
    document_filename,
    ensure_remaining_section,
    prepare_maintainability_markdown,
    sanitize_alias,
    write_markdown_document,
)


def _snapshot(tmp_path: Path, **kwargs) -> MetadataSnapshot:
    return MetadataSnapshot(source_dir=tmp_path, package_roots=[tmp_path], **kwargs)


def _local_picklist(api_name: str) -> FieldInfo:
    return FieldInfo(
        api_name=api_name,
        label="Canal",
        data_type="Picklist",
        custom=True,
        picklist_values=["Agence", "Web", "Telephone"],
        picklist_api_names=["Agence", "Web", "Telephone"],
    )


def test_document_names_use_the_alias_and_the_day() -> None:
    assert sanitize_alias("ag2r/Poc") == "ag2r_Poc"
    assert sanitize_alias("  ") == "org"
    assert (
        document_filename("business", "ag2rPoc", "20261022")
        == "Description_metier_org_ag2rPoc_20261022.docx"
    )
    assert (
        document_filename("maintainability", "ag2r/Poc", "20261022")
        == "Correction_Maintenabilité_metier_org_ag2r_Poc_20261022.docx"
    )


def test_identical_local_picklists_are_grouped_by_object(tmp_path: Path) -> None:
    account = ObjectInfo(
        api_name="Account",
        label="Compte",
        fields=[_local_picklist("Canal__c")],
    )
    case = ObjectInfo(
        api_name="Case",
        label="Requete",
        custom=False,
        fields=[_local_picklist("CanalRequete__c")],
    )
    skeleton = build_maintainability_skeleton(
        _snapshot(tmp_path, objects=[account, case]),
        None,
        alias="ag2rPoc",
        source_dir=str(tmp_path),
        language="fr",
    )

    assert "## Account — Compte" in skeleton
    assert "## Case — Requete" in skeleton
    assert skeleton.count("### Listes de valeurs identiques non globales") == 2
    assert "Canal__c" in skeleton
    assert "CanalRequete__c" in skeleton
    assert "liste de valeurs globale" in skeleton


def test_global_picklists_with_the_same_values_are_not_flagged(tmp_path: Path) -> None:
    shared = FieldInfo(
        api_name="Canal__c",
        label="Canal",
        data_type="Picklist",
        custom=True,
        picklist_is_global=True,
        picklist_global_name="Canal",
        picklist_values=["Agence", "Web"],
    )
    other = FieldInfo(
        api_name="Origine__c",
        label="Origine",
        data_type="Picklist",
        custom=True,
        picklist_is_global=True,
        picklist_global_name="Canal",
        picklist_values=["Agence", "Web"],
    )
    skeleton = build_maintainability_skeleton(
        _snapshot(
            tmp_path,
            objects=[
                ObjectInfo(api_name="Account", label="Compte", fields=[shared]),
                ObjectInfo(api_name="Case", label="Requete", fields=[other]),
            ],
        ),
        None,
        alias="ag2rPoc",
        source_dir=str(tmp_path),
        language="fr",
    )
    assert "Listes de valeurs identiques non globales" not in skeleton
    assert "Aucun écart de maintenabilité" in skeleton


def test_local_field_matching_a_global_set_is_reported_on_its_object(tmp_path: Path) -> None:
    local = FieldInfo(
        api_name="CanalRequete__c",
        label="Canal requete",
        data_type="Picklist",
        custom=True,
        picklist_values=["Agence", "Web"],
    )
    skeleton = build_maintainability_skeleton(
        _snapshot(
            tmp_path,
            objects=[
                ObjectInfo(
                    api_name="Account",
                    label="Compte",
                    fields=[
                        FieldInfo(
                            api_name="Canal__c",
                            label="Canal",
                            data_type="Picklist",
                            custom=True,
                            picklist_is_global=True,
                            picklist_global_name="Canal",
                            picklist_values=["Agence", "Web"],
                        )
                    ],
                ),
                ObjectInfo(api_name="Case", label="Requete", fields=[local]),
            ],
        ),
        None,
        alias="ag2rPoc",
        source_dir=str(tmp_path),
        language="fr",
    )
    assert "## Case — Requete" in skeleton
    assert "CanalRequete__c" in skeleton
    assert "Canal" in skeleton
    assert "### Listes de valeurs identiques non globales" in skeleton


def test_bypass_flow_and_validation_are_filed_on_their_object(tmp_path: Path) -> None:
    account = ObjectInfo(
        api_name="Account",
        label="Compte",
        validation_rules=[
            ValidationRuleInfo(
                full_name="Bloquer_sans_nom",
                active=True,
                error_message="Le nom est obligatoire",
                error_condition_formula="AND(NOT($Permission.Bypass_VR), ISBLANK(Name))",
            )
        ],
    )
    snapshot = _snapshot(
        tmp_path,
        objects=[account],
        flows=[
            FlowInfo(
                name="Account_Before",
                label="Avant enregistrement",
                start_object="Account",
                process_type="AutoLaunchedFlow",
                status="Active",
                total_elements=100,
            )
        ],
        apex_artifacts=[
            ApexArtifact(
                name="AccountTrigger",
                kind="trigger",
                body=(
                    "trigger AccountTrigger on Account (before insert) {\n"
                    "  if (Bypass__c.getInstance().Skip__c) { return; }\n"
                    "}\n"
                ),
                source_path=tmp_path / "AccountTrigger.trigger",
            )
        ],
    )
    skeleton = build_maintainability_skeleton(
        snapshot,
        None,
        alias="ag2rPoc",
        source_dir=str(tmp_path),
        language="fr",
    )
    assert "## Account — Compte" in skeleton
    assert "### Bypass" in skeleton
    assert "$Permission.Bypass_VR" in skeleton
    assert "AccountTrigger" in skeleton
    assert "### Flows" in skeleton
    assert "Account_Before" in skeleton


def test_business_brief_uses_source_facts_output_html_and_gaps(tmp_path: Path) -> None:
    output = tmp_path / "out"
    (output / "html").mkdir(parents=True)
    (output / "html" / "index.html").write_text(
        "<html><body><p>Parcours client prioritaire pour la souscription.</p></body></html>",
        encoding="utf-8",
    )
    account = ObjectInfo(
        api_name="Contrat__c",
        label="Contrat",
        custom=True,
        description="Contrat d'assurance souscrit en agence.",
        fields=[
            FieldInfo(
                api_name="Produit__c",
                label="Produit",
                data_type="Text",
                custom=True,
                description="Produit commercial vendu.",
            )
        ],
    )
    bare = ObjectInfo(api_name="Avenant__c", label="Avenant", custom=True)
    brief = build_business_brief(
        _snapshot(tmp_path, objects=[account, bare]),
        output,
        alias="ag2rPoc",
        source_dir=str(tmp_path),
        language="fr",
    )
    assert "Contrat d'assurance souscrit en agence." in brief.digest
    assert "Produit commercial vendu." in brief.digest
    assert "Parcours client prioritaire" in brief.digest
    assert any("Avenant__c" in gap for gap in brief.gaps)
    assert any("description métier" in gap for gap in brief.gaps)


def test_remaining_work_section_is_added_when_the_model_omits_it() -> None:
    completed = ensure_remaining_section(
        "# Description métier\n\n## Finalité\n\nTexte.",
        ["L'objet Avenant__c n'a pas de description métier."],
        "fr",
    )
    assert "# Reste à faire" in completed
    assert "Avenant__c" in completed

    already = ensure_remaining_section(
        "# Description\n\n# Reste à faire\n\n- Confirmer le parcours agence.\n",
        ["autre"],
        "fr",
    )
    assert already.count("Reste à faire") == 1


def test_maintainability_reply_keeps_the_object_outline() -> None:
    skeleton = "## Account — Compte\n### Bypass\n- Regle existante.\n"
    rewritten = prepare_maintainability_markdown(
        skeleton,
        "```markdown\nIntro libre sans les titres.\n```",
    )
    assert rewritten.startswith("## Account — Compte")
    assert "# Analyse complémentaire de l'IA" in rewritten

    kept = prepare_maintainability_markdown(
        skeleton,
        "## Account — Compte\n### Bypass\n- Regle existante.\n  Correction : utiliser une custom permission.\n",
    )
    assert "Correction : utiliser une custom permission." in kept
    assert "Analyse complémentaire" not in kept


def test_word_document_contains_the_remaining_work_heading(tmp_path: Path) -> None:
    markdown = ensure_remaining_section(
        "# Description métier — ag2rPoc\n\n## Finalité\n\nL'org gère la **souscription**.",
        ["Décrire l'objet Avenant__c."],
        "fr",
    )
    path = write_markdown_document(
        markdown,
        tmp_path / "word" / "Description_metier_org_ag2rPoc_20261022.docx",
        title="Description métier de l'organisation",
        subtitle="ag2rPoc — 2026-10-22",
        details="Source : C:/source\nSortie : C:/out",
        language="fr",
    )
    document = Document(path)
    texts = [paragraph.text for paragraph in document.paragraphs]
    assert any("Description métier de l'organisation" in text for text in texts)
    assert any(text.strip() == "Reste à faire" for text in texts)
    assert any("souscription" in text for text in texts)
    assert any("Avenant__c" in text for text in texts)
