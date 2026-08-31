"""Inventory building: flat row lists for every metadata family."""

from __future__ import annotations

from pathlib import Path

from src.core.models import FlowInfo, MetadataSnapshot, ObjectInfo, SecurityArtifact
from src.core.utils import SF_NS, child_text, parse_xml
from src.parsers.salesforce_parser.base import _ParserState


class _InventoryMixin(_ParserState):
    """Produce the ``snapshot.inventory`` dictionary of row lists."""

    def _build_inventory(self, snapshot: MetadataSnapshot) -> dict[str, list[dict[str, object]]]:
        return {
            "record_types": self._inventory_record_types(snapshot.objects),
            "layouts": self._inventory_layouts(snapshot.package_roots),
            "lightning_pages": self._inventory_flexipages(snapshot.package_roots),
            "validation_rules": self._inventory_validation_rules(snapshot.objects),
            "omnistudio": self._inventory_special_files(snapshot.package_roots, category="omnistudio"),
            "business_rules_engine": self._inventory_special_files(
                snapshot.package_roots, category="business_rules_engine"
            ),
            "flows": self._inventory_flows(snapshot.flows),
            "permission_sets": self._inventory_security(snapshot.permission_sets),
            "profiles": self._inventory_security(snapshot.profiles),
            "reports": self._inventory_reports(snapshot.package_roots),
            "dashboards": self._inventory_dashboards(snapshot.package_roots),
        }

    def _inventory_record_types(self, objects: list[ObjectInfo]) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for item in objects:
            for record_type in item.record_types:
                rows.append(
                    {
                        "Objet": item.api_name,
                        "Record Type": record_type.full_name,
                        "Label": record_type.label,
                        "Actif": record_type.active,
                        "Description": record_type.description,
                    }
                )
        return rows

    def _inventory_validation_rules(self, objects: list[ObjectInfo]) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for item in objects:
            for rule in item.validation_rules:
                rows.append(
                    {
                        "Objet": item.api_name,
                        "Regle": rule.full_name,
                        "Active": rule.active,
                        "Description": rule.description,
                        "ChampErreur": rule.error_display_field,
                    }
                )
        return rows

    def _inventory_security(self, artifacts: list[SecurityArtifact]) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for artifact in artifacts:
            rows.append(
                {
                    "Nom": artifact.name,
                    "Label": artifact.label,
                    "Description": artifact.description,
                    "DroitsObjet": len(artifact.object_permissions),
                    "DroitsChamp": len(artifact.field_permissions),
                    "PermissionsSysteme": len(artifact.user_permissions),
                    "Applications": len(artifact.application_visibilities),
                    "Flows": len(artifact.flow_accesses),
                    "RecordTypes": len(artifact.record_type_visibilities),
                    "Source": self._safe_relative_path(artifact.source_path),
                }
            )
        return rows

    def _inventory_flows(self, flows: list[FlowInfo]) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for flow in flows:
            rows.append(
                {
                    "Nom": flow.name,
                    "Label": flow.label,
                    "Type": flow.process_type,
                    "Statut": flow.status,
                    "Objet": flow.start_object,
                    "Declencheur": flow.trigger_type,
                    "Complexite": flow.complexity_level,
                    "Score": flow.complexity_score,
                    "Elements": flow.total_elements,
                    "Source": self._safe_relative_path(flow.source_path),
                }
            )
        return rows

    def _inventory_layouts(self, package_roots: list[Path]) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for package_root in package_roots:
            folder = package_root / "layouts"
            if not folder.exists():
                continue
            for meta_file in sorted(folder.glob("*.layout-meta.xml")):
                name = meta_file.stem.replace(".layout-meta", "")
                if self._is_excluded("layout", name):
                    continue
                root = parse_xml(meta_file)
                rows.append(
                    {
                        "Objet": meta_file.stem.split("-")[0],
                        "Layout": meta_file.stem.replace(".layout-meta", ""),
                        "Sections": len(root.findall("sf:layoutSections", SF_NS)),
                        "RelatedLists": len(root.findall("sf:relatedLists", SF_NS)),
                        "BoutonsExclus": len(root.findall("sf:excludeButtons", SF_NS)),
                        "MiniLayout": root.find("sf:miniLayout", SF_NS) is not None,
                        "Source": self._safe_relative_path(meta_file),
                    }
                )
        return rows

    def _inventory_flexipages(self, package_roots: list[Path]) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for package_root in package_roots:
            folder = package_root / "flexipages"
            if not folder.exists():
                continue
            for meta_file in sorted(folder.glob("*.flexipage-meta.xml")):
                name = meta_file.stem.replace(".flexipage-meta", "")
                if self._is_excluded("flexipage", name):
                    continue
                root = parse_xml(meta_file)
                rows.append(
                    {
                        "NomAPI": meta_file.stem.replace(".flexipage-meta", ""),
                        "Label": child_text(root, "masterLabel"),
                        "Type": child_text(root, "type"),
                        "Objet": child_text(root, "sobjectType"),
                        "Template": child_text(root.find("sf:template", SF_NS), "name")
                        if root.find("sf:template", SF_NS) is not None
                        else "",
                        "Regions": len(root.findall("sf:flexiPageRegions", SF_NS)),
                        "Composants": len(root.findall(".//sf:componentInstance", SF_NS)),
                        "Source": self._safe_relative_path(meta_file),
                    }
                )
        return rows

    def _inventory_reports(self, package_roots: list[Path]) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for package_root in package_roots:
            folder = package_root / "reports"
            if not folder.exists():
                continue
            for meta_file in sorted(folder.rglob("*.report-meta.xml")):
                name = meta_file.stem.replace(".report-meta", "")
                if self._is_excluded("report", name):
                    continue
                root = parse_xml(meta_file)
                relative = meta_file.relative_to(folder)
                rows.append(
                    {
                        "Dossier": str(relative.parent).replace("\\", "/") if str(relative.parent) != "." else "",
                        "Nom": meta_file.stem.replace(".report-meta", ""),
                        "Label": child_text(root, "name") or child_text(root, "fullName"),
                        "Description": child_text(root, "description"),
                        "TypeRapport": child_text(root, "reportType"),
                        "Filtres": len(root.findall("sf:filter", SF_NS)) + len(root.findall("sf:standardFilter", SF_NS)),
                        "Colonnes": len(root.findall("sf:columns", SF_NS)),
                        "Source": self._safe_relative_path(meta_file),
                    }
                )
        return rows

    def _inventory_dashboards(self, package_roots: list[Path]) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for package_root in package_roots:
            folder = package_root / "dashboards"
            if not folder.exists():
                continue
            for meta_file in sorted(folder.rglob("*.dashboard-meta.xml")):
                name = meta_file.stem.replace(".dashboard-meta", "")
                if self._is_excluded("dashboard", name):
                    continue
                root = parse_xml(meta_file)
                relative = meta_file.relative_to(folder)
                rows.append(
                    {
                        "Dossier": str(relative.parent).replace("\\", "/") if str(relative.parent) != "." else "",
                        "Nom": meta_file.stem.replace(".dashboard-meta", ""),
                        "Titre": child_text(root, "title"),
                        "Type": child_text(root, "dashboardType"),
                        "RunningUser": child_text(root, "runningUser"),
                        "Composants": len(root.findall("sf:dashboardGridComponents", SF_NS)),
                        "Source": self._safe_relative_path(meta_file),
                    }
                )
        return rows

    def _inventory_special_files(
        self, package_roots: list[Path], category: str
    ) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        if category == "omnistudio":
            keywords = ("omni", "omnistudio", "datasource", "vlocity")
            known_folders = {
                "omniscripts",
                "omniuicard",
                "omniuicards",
                "vlocitycards",
                "omnidatatransforms",
                "omniprocesses",
                "omniintegrationprocedures",
                "omnistudio",
            }
            label = "OmniStudio"
        else:
            keywords = (
                "decision",
                "expression",
                "calculationmatrix",
                "ruleset",
                "recommendationstrategy",
                "decisionmatrix",
            )
            known_folders = {
                "decisionmatrices",
                "decisionmatrixdefinitions",
                "decisionmatrixdefinitionversions",
                "decisiontables",
                "expressionsets",
                "expressionsetdefinitions",
                "calculationmatrices",
                "recommendationstrategies",
            }
            label = "Business Rules Engine"

        for package_root in package_roots:
            for meta_file in sorted(package_root.rglob("*")):
                if meta_file.is_dir() or meta_file.suffix.lower() != ".xml":
                    continue

                folder_name = meta_file.parent.name.lower()
                file_name = meta_file.name.lower()
                stem = meta_file.stem.lower()
                name = meta_file.stem.split(".")[0]

                if self._is_excluded("omni" if category == "omnistudio" else "business_rule", name):
                    continue

                if folder_name in known_folders or any(token in file_name or token in stem for token in keywords):
                    # For OmniProcesses, we try to determine the exact type
                    sub_type = ""
                    if folder_name == "omniprocesses" or file_name.endswith(".omniprocess-meta.xml"):
                        try:
                            root = parse_xml(meta_file)
                            sub_type = child_text(root, "omniProcessType")
                        except Exception:
                            pass

                    rows.append(
                        {
                            "Nom": meta_file.stem.split(".")[0],
                            "Categorie": label,
                            "Dossier": meta_file.parent.name,
                            "TypeFichier": "".join(meta_file.suffixes),
                            "Source": self._safe_relative_path(meta_file),
                            "SubType": sub_type,
                        }
                    )

        unique_rows: list[dict[str, object]] = []
        seen_sources: set[str] = set()
        for row in rows:
            source = str(row["Source"])
            if source in seen_sources:
                continue
            seen_sources.add(source)
            unique_rows.append(row)
        return unique_rows

    def _safe_relative_path(self, path: Path) -> str:
        try:
            return str(path.relative_to(self.source_dir)).replace("\\", "/")
        except ValueError:
            return str(path)
