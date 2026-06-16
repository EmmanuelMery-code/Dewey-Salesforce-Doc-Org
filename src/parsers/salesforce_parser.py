from __future__ import annotations

import fnmatch
import json
import re
from collections import Counter
from pathlib import Path
from typing import Callable

LogCallback = Callable[[str], None]

from src.core.models import (
    AgentInfo,
    ApexArtifact,
    CustomizationMetrics,
    Dependency,
    DuplicateRuleInfo,
    FieldInfo,
    FieldPermission,
    FlowElementInfo,
    FlowInfo,
    GenAiPromptInfo,
    LwcInfo,
    AuraInfo,
    MetadataSnapshot,
    NamedAccess,
    ObjectInfo,
    ObjectPermission,
    OrphanInfo,
    PermissionSetGroupInfo,
    RecordTypeInfo,
    RecordTypeVisibility,
    RedundantFlowGroup,
    RelationshipInfo,
    SecurityArtifact,
    SharingRuleInfo,
    UserPermission,
    ValidationRuleInfo,
    VisibilityItem,
)
from src.core.utils import SF_NS, child_text, child_texts, parse_xml, to_bool

# Security risk analysis constants — shared with src.analyzer.security_analyzer
_SEC_DANGEROUS_USER_PERMS: frozenset[str] = frozenset({"ModifyAllData", "ManageUsers"})
_SEC_SENSITIVE_OBJECTS: frozenset[str] = frozenset({
    "Account", "Contact", "Opportunity", "Lead", "Order",
    "Case", "Contract", "User", "Event", "Task",
})


class SalesforceMetadataParser:
    """Parse a Salesforce DX source folder into a :class:`MetadataSnapshot`.

    Walks the well-known Salesforce metadata layout (objects, classes,
    triggers, flows, profiles, permission sets, etc.), produces structured
    Python dataclasses and applies an optional exclusion file so the caller
    can opt out of specific artefacts.
    """

    CATEGORY_ALIASES = {
        "all": "all",
        "global": "all",
        "objet": "object",
        "objets": "object",
        "object": "object",
        "objects": "object",
        "apex": "apex",
        "classe": "apex",
        "classes": "apex",
        "trigger": "apex",
        "triggers": "apex",
        "flow": "flow",
        "flows": "flow",
        "lwc": "lwc",
        "agent": "agent",
        "agents": "agent",
        "prompt": "prompt",
        "prompts": "prompt",
        "validation rule": "validation_rule",
        "validation rules": "validation_rule",
        "vr": "validation_rule",
        "omni": "omni",
        "omnistudio": "omni",
        "layout": "layout",
        "layouts": "layout",
        "flexipage": "flexipage",
        "flexipages": "flexipage",
        "lightning page": "flexipage",
        "lightning pages": "flexipage",
        "report": "report",
        "reports": "report",
        "dashboard": "dashboard",
        "dashboards": "dashboard",
        "profile": "profile",
        "profiles": "profile",
        "permission set": "permission_set",
        "permission sets": "permission_set",
        "permset": "permission_set",
        "permsets": "permission_set",
        "tab": "tab",
        "tabs": "tab",
        "application": "application",
        "applications": "application",
        "app": "application",
        "apps": "application",
        "ai_prediction": "ai_prediction",
        "ai_predictions": "ai_prediction",
        "business_rule": "business_rule",
        "business_rules": "business_rule",
        "bre": "business_rule",
        "field": "field",
        "fields": "field",
        "champ": "field",
        "champs": "field",
        "record_type": "record_type",
        "record_types": "record_type",
        "rt": "record_type",
    }

    def __init__(
        self,
        source_dir: str | Path,
        exclusion_config_path: str | Path | None = None,
        log_callback: LogCallback | None = None,
    ) -> None:
        self.source_dir = Path(source_dir).resolve()
        
        if exclusion_config_path:
            self.exclusion_config_path = Path(exclusion_config_path).resolve()
        else:
            # Default to exclusion.json in the app directory if it exists
            app_root = Path(__file__).resolve().parent.parent.parent
            candidate = app_root / "exclusion.json"
            self.exclusion_config_path = candidate.resolve() if candidate.exists() else None

        self.log: LogCallback = log_callback or (lambda message: None)
        self.exclusion_rules: dict[str, list[str]] = self._load_exclusion_rules(
            self.exclusion_config_path
        )

    def parse(self) -> MetadataSnapshot:
        package_roots = self._resolve_package_roots()
        snapshot = MetadataSnapshot(source_dir=self.source_dir, package_roots=package_roots)

        objects: dict[str, ObjectInfo] = {}
        profiles: list[SecurityArtifact] = []
        permission_sets: list[SecurityArtifact] = []
        apex_artifacts: list[ApexArtifact] = []
        flows: list[FlowInfo] = []
        agents: list[AgentInfo] = []
        gen_ai_prompts: list[GenAiPromptInfo] = []
        sharing_rules: list[SharingRuleInfo] = []
        duplicate_rules: list[DuplicateRuleInfo] = []
        metrics = CustomizationMetrics()

        for package_root in package_roots:
            self.log(f"Analyse du package {package_root}")
            objects_found = self._parse_objects(package_root)
            self.log(f"  - {len(objects_found)} objet(s) trouve(s)")
            objects.update(objects_found)
            
            profiles_found = self._parse_security_folder(package_root / "profiles", "profile")
            self.log(f"  - {len(profiles_found)} profil(s) trouve(s)")
            profiles.extend(profiles_found)
            
            permsets_found = self._parse_security_folder(package_root / "permissionsets", "permission_set")
            self.log(f"  - {len(permsets_found)} permission set(s) trouve(s)")
            permission_sets.extend(permsets_found)
            
            classes_found = self._parse_apex_folder(package_root / "classes", "class")
            self.log(f"  - {len(classes_found)} classe(s) Apex trouvee(s)")
            apex_artifacts.extend(classes_found)
            
            triggers_found = self._parse_apex_folder(package_root / "triggers", "trigger")
            self.log(f"  - {len(triggers_found)} trigger(s) Apex trouve(s)")
            apex_artifacts.extend(triggers_found)
            
            flows_found = self._parse_flows(package_root / "flows")
            self.log(f"  - {len(flows_found)} flow(s) trouve(s)")
            flows.extend(flows_found)

            agents_found = self._parse_agents(package_root)
            self.log(f"  - {len(agents_found)} agent(s) trouve(s)")
            agents.extend(agents_found)

            prompts_found = self._parse_gen_ai_prompts(package_root / "genAiPromptTemplates")
            self.log(f"  - {len(prompts_found)} prompt(s) trouve(s)")
            gen_ai_prompts.extend(prompts_found)

            sr_found = self._parse_sharing_rules(package_root / "sharingRules")
            self.log(f"  - {len(sr_found)} sharing rule(s) trouve(e)s")
            sharing_rules.extend(sr_found)
            metrics.sharing_rules += len(sr_found)

            dr_found = self._parse_duplicate_rules(package_root / "duplicateRules")
            self.log(f"  - {len(dr_found)} duplicate rule(s) trouve(e)s")
            duplicate_rules.extend(dr_found)
            metrics.duplicate_rules += len(dr_found)

            psg_found = self._parse_permission_set_groups(package_root / "permissionsetgroups")
            self.log(f"  - {len(psg_found)} permission set group(s) trouve(s)")
            snapshot.permission_set_groups.extend(psg_found)

            lwc_found = self._parse_lwc(package_root / "lwc")
            self.log(f"  - {len(lwc_found)} LWC trouve(s)")
            snapshot.lwc.extend(lwc_found)
            metrics.lwc_count += len(lwc_found)

            aura_found = self._parse_aura(package_root / "aura")
            self.log(f"  - {len(aura_found)} Aura trouve(s)")
            snapshot.aura.extend(aura_found)

            metrics.flexipage_count += len(
                [
                    path
                    for path in (package_root / "flexipages").glob("*.flexipage-meta.xml")
                    if not self._is_excluded("flexipage", path.stem.replace(".flexipage-meta", ""))
                ]
            )
            metrics.layouts += len(
                [
                    path
                    for path in (package_root / "layouts").glob("*.layout-meta.xml")
                    if not self._is_excluded("layout", path.stem.replace(".layout-meta", ""))
                ]
            )
            metrics.custom_tabs += len(
                [
                    path
                    for path in (package_root / "tabs").glob("*.tab-meta.xml")
                    if "__" in path.stem and not self._is_excluded("tab", path.stem.replace(".tab-meta", ""))
                ]
            )
            metrics.custom_apps += len(
                [
                    path
                    for path in (package_root / "applications").glob("*.app-meta.xml")
                    if not path.stem.startswith("standard__") and not self._is_excluded("application", path.stem.replace(".app-meta", ""))
                ]
            )
            metrics.omni_scripts += len(
                [
                    path
                    for path in (package_root / "omniScripts").glob("*.os-meta.xml")
                    if not self._is_excluded("omni", path.stem.replace(".os-meta", ""))
                ]
            )
            metrics.omni_data_transforms += len(
                [
                    path
                    for path in (package_root / "omniDataTransforms").glob("*.rpt-meta.xml")
                    if not self._is_excluded("omni", path.stem.replace(".rpt-meta", ""))
                ]
            )
            metrics.einstein_predictions += len(
                [
                    path
                    for path in (package_root / "aiPredictions").glob("*.aiPrediction-meta.xml")
                    if not self._is_excluded("ai_prediction", path.stem.replace(".aiPrediction-meta", ""))
                ]
            )
            metrics.bre_decision_matrices += len(
                [
                    path
                    for path in (package_root / "decisionMatrices").glob("*.decisionMatrix-meta.xml")
                    if not self._is_excluded("business_rule", path.stem.replace(".decisionMatrix-meta", ""))
                ]
            )
            metrics.bre_expression_sets += len(
                [
                    path
                    for path in (package_root / "expressionSets").glob("*.expressionSet-meta.xml")
                    if not self._is_excluded("business_rule", path.stem.replace(".expressionSet-meta", ""))
                ]
            )

        snapshot.objects = sorted(objects.values(), key=lambda item: item.api_name.lower())
        snapshot.profiles = sorted(profiles, key=lambda item: item.name.lower())
        snapshot.permission_sets = sorted(permission_sets, key=lambda item: item.name.lower())
        snapshot.apex_artifacts = sorted(apex_artifacts, key=lambda item: item.name.lower())
        snapshot.flows = sorted(flows, key=lambda item: item.name.lower())
        snapshot.agents = sorted(agents, key=lambda item: item.name.lower())
        snapshot.gen_ai_prompts = sorted(gen_ai_prompts, key=lambda item: item.name.lower())
        snapshot.sharing_rules = sorted(sharing_rules, key=lambda item: (item.object_name.lower(), item.full_name.lower()))
        snapshot.duplicate_rules = sorted(duplicate_rules, key=lambda item: (item.object_name.lower(), item.full_name.lower()))

        snapshot.profiles = [
            item
            for item in snapshot.profiles
            if not self._is_excluded("profile", item.name, item.label)
        ]
        snapshot.permission_sets = [
            item
            for item in snapshot.permission_sets
            if not self._is_excluded("permission_set", item.name, item.label)
        ]
        snapshot.objects = [
            item
            for item in snapshot.objects
            if not self._is_excluded("object", item.api_name, item.label)
        ]
        snapshot.apex_artifacts = [
            item
            for item in snapshot.apex_artifacts
            if not self._is_excluded("apex", item.name)
        ]
        snapshot.flows = [
            item
            for item in snapshot.flows
            if not self._is_excluded("flow", item.name, item.label)
        ]
        snapshot.agents = [
            item
            for item in snapshot.agents
            if not self._is_excluded("agent", item.name, item.label)
        ]
        snapshot.gen_ai_prompts = [
            item
            for item in snapshot.gen_ai_prompts
            if not self._is_excluded("prompt", item.name, item.label)
        ]
        snapshot.inventory = self._build_inventory(snapshot)

        metrics.custom_objects = sum(1 for item in snapshot.objects if item.custom)
        metrics.custom_fields = sum(1 for item in snapshot.objects for field in item.fields if field.custom)
        metrics.record_types = sum(len(item.record_types) for item in snapshot.objects)
        metrics.validation_rules = sum(len(item.validation_rules) for item in snapshot.objects)
        metrics.flows = len(snapshot.flows)
        metrics.apex_classes = sum(1 for item in snapshot.apex_artifacts if item.kind == "class")
        metrics.apex_triggers = sum(1 for item in snapshot.apex_artifacts if item.kind == "trigger")
        metrics.agents = len(snapshot.agents)
        metrics.gen_ai_prompts = len(snapshot.gen_ai_prompts)
        metrics.profiles_count = len(snapshot.profiles)

        # ── Security risk metrics ─────────────────────────────────────────
        custom_profiles = [p for p in snapshot.profiles if p.is_custom]
        metrics.custom_profiles_count = len(custom_profiles)
        metrics.permission_sets_count = len(snapshot.permission_sets)

        metrics.dangerous_profiles_count = sum(
            1 for p in custom_profiles
            if any(
                up.enabled and up.name in _SEC_DANGEROUS_USER_PERMS
                for up in p.user_permissions
            )
        )
        metrics.profiles_with_modify_all = sum(
            1 for p in custom_profiles
            if any(op.modify_all_records for op in p.object_permissions)
        )
        metrics.perm_sets_with_modify_all = sum(
            1 for ps in snapshot.permission_sets
            if any(
                op.modify_all_records and op.object_name in _SEC_SENSITIVE_OBJECTS
                for op in ps.object_permissions
            )
        )
        # ── end security metrics ──────────────────────────────────────────

        snapshot.metrics = metrics
        self._analyze_dependencies(snapshot)
        return snapshot

    def _load_exclusion_rules(
        self, config_path: Path | None
    ) -> dict[str, list[str]]:
        rules: dict[str, list[str]] = {
            val: [] for val in set(self.CATEGORY_ALIASES.values())
        }
        if "all" not in rules:
            rules["all"] = []
        
        if config_path is None:
            return rules
        if not config_path.exists():
            self.log(f"Fichier de configuration hors analyse introuvable: {config_path}")
            return rules

        try:
            data = {}
            # Try different encodings to be robust
            for encoding in ("utf-8", "utf-16", "latin-1"):
                try:
                    with open(config_path, "r", encoding=encoding) as f:
                        data = json.load(f)
                    break # Success
                except (UnicodeDecodeError, json.JSONDecodeError):
                    continue
            
            if not data:
                self.log(f"Le fichier d'exclusions {config_path} est vide ou invalide.")
                return rules
            
            # The JSON structure expected is:
            # {
            #   "metadata_exclusions": [
            #     {"type": "...", "element": "...", "commentaire": "..."},
            #     ...
            #   ]
            # }
            
            exclusions = data.get("metadata_exclusions", [])
            # Fallback for old format or different naming
            if not exclusions and "Hors analyse" in data:
                # Handle the list of lists format if necessary, but we prefer the new object format
                raw_list = data["Hors analyse"]
                for item in raw_list:
                    if isinstance(item, list) and len(item) >= 2:
                        category = self.CATEGORY_ALIASES.get(str(item[0]).lower(), "all")
                        pattern = str(item[1]).strip()
                        if pattern and pattern not in rules[category]:
                            rules[category].append(pattern)
                return rules

            for entry in exclusions:
                if not isinstance(entry, dict):
                    continue
                
                category_raw = str(entry.get("type", "")).lower()
                category = self.CATEGORY_ALIASES.get(category_raw, "all")
                
                # 'element' is the primary field for the pattern
                pattern = str(entry.get("element", "")).strip()
                if not pattern:
                    continue
                
                if pattern not in rules[category]:
                    rules[category].append(pattern)

        except Exception as e:
            self.log(f"Erreur lors du chargement des exclusions JSON: {e}")

        total = sum(len(items) for items in rules.values())
        if total:
            self.log(f"{total} regle(s) hors analyse chargee(s) depuis {config_path}.")
        return rules

    def _is_excluded(self, category: str, *names: str) -> bool:
        candidates = self.exclusion_rules.get(category, []) + self.exclusion_rules.get("all", [])
        if not candidates:
            return False
        targets = [name for name in names if name]
        if not targets:
            return False
        
        lowered_targets = [target.lower() for target in targets]
        normalized_targets = [self._normalize_exclusion_token(target) for target in targets]
        
        for pattern in candidates:
            lowered_pattern = pattern.lower()
            normalized_pattern = self._normalize_exclusion_token(pattern)
            
            for lowered_target, normalized_target in zip(lowered_targets, normalized_targets):
                # Exact match or glob match
                if fnmatch.fnmatch(lowered_target, lowered_pattern):
                    return True
                # Substring match (case insensitive)
                if lowered_pattern in lowered_target:
                    return True
                # Normalized match (removes spaces/underscores)
                if normalized_pattern and (normalized_pattern == normalized_target or normalized_pattern in normalized_target):
                    return True
        return False

    @staticmethod
    def _normalize_exclusion_token(value: str) -> str:
        return re.sub(r"[\s_]+", "", value or "").lower()

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

    def _resolve_package_roots(self) -> list[Path]:
        config_path = self.source_dir / "sfdx-project.json"
        package_roots: list[Path] = []

        if config_path.exists():
            config = json.loads(config_path.read_text(encoding="utf-8"))
            for entry in config.get("packageDirectories", []):
                package_path = self.source_dir / entry.get("path", "")
                default_root = package_path / "main" / "default"
                if default_root.exists():
                    package_roots.append(default_root)
                elif package_path.exists():
                    package_roots.append(package_path)

        fallback = self.source_dir / "force-app" / "main" / "default"
        if fallback.exists() and fallback not in package_roots:
            package_roots.append(fallback)

        if not package_roots:
            self.log(f"Aucun packageDirectory trouve dans sfdx-project.json, utilisation de {self.source_dir}")
            package_roots.append(self.source_dir)

        return package_roots

    def _parse_objects(self, package_root: Path) -> dict[str, ObjectInfo]:
        objects_dir = package_root / "objects"
        parsed: dict[str, ObjectInfo] = {}
        if not objects_dir.exists():
            return parsed

        for object_dir in sorted(path for path in objects_dir.iterdir() if path.is_dir()):
            api_name = object_dir.name
            object_file = object_dir / f"{api_name}.object-meta.xml"
            info = ObjectInfo(api_name=api_name, custom="__" in api_name, source_path=object_file if object_file.exists() else object_dir)

            if object_file.exists():
                root = parse_xml(object_file)
                info.label = child_text(root, "label")
                info.plural_label = child_text(root, "pluralLabel")
                info.description = child_text(root, "description")
                info.deployment_status = child_text(root, "deploymentStatus")
                info.sharing_model = child_text(root, "sharingModel") or child_text(root, "externalSharingModel")
                info.visibility = child_text(root, "visibility")
                # Sometimes apiVersion is in the object file (though rare)
                info.api_version = child_text(root, "apiVersion")

            fields_dir = object_dir / "fields"
            if fields_dir.exists():
                for field_file in sorted(fields_dir.glob("*.field-meta.xml")):
                    field_info = self._parse_field(field_file)
                    if not self._is_excluded("field", f"{api_name}.{field_info.api_name}", field_info.api_name):
                        info.fields.append(field_info)

            record_types_dir = object_dir / "recordTypes"
            if record_types_dir.exists():
                for record_type_file in sorted(record_types_dir.glob("*.recordType-meta.xml")):
                    rt_info = self._parse_record_type(record_type_file)
                    if not self._is_excluded("record_type", f"{api_name}.{rt_info.full_name}", rt_info.full_name):
                        info.record_types.append(rt_info)

            validation_rules_dir = object_dir / "validationRules"
            if validation_rules_dir.exists():
                for validation_rule_file in sorted(validation_rules_dir.glob("*.validationRule-meta.xml")):
                    vr = self._parse_validation_rule(validation_rule_file)
                    if not self._is_excluded("validation_rule", f"{api_name}.{vr.full_name}", vr.full_name):
                        info.validation_rules.append(vr)

            info.relationships = [
                RelationshipInfo(
                    field_name=field.api_name,
                    relationship_type=field.data_type,
                    targets=field.reference_to,
                )
                for field in info.fields
                if field.reference_to
            ]
            parsed[api_name] = info

        return parsed

    def _parse_field(self, field_file: Path) -> FieldInfo:
        root = parse_xml(field_file)
        api_name = child_text(root, "fullName") or field_file.stem.replace(".field-meta", "")
        return FieldInfo(
            api_name=api_name,
            label=child_text(root, "label"),
            data_type=child_text(root, "type"),
            description=child_text(root, "description"),
            required=to_bool(child_text(root, "required")),
            custom="__" in api_name,
            reference_to=child_texts(root, "referenceTo"),
            relationship_name=child_text(root, "relationshipName"),
        )

    def _parse_record_type(self, record_type_file: Path) -> RecordTypeInfo:
        root = parse_xml(record_type_file)
        return RecordTypeInfo(
            full_name=child_text(root, "fullName") or record_type_file.stem.replace(".recordType-meta", ""),
            label=child_text(root, "label"),
            description=child_text(root, "description"),
            active=to_bool(child_text(root, "active")),
        )

    def _parse_validation_rule(self, validation_rule_file: Path) -> ValidationRuleInfo:
        root = parse_xml(validation_rule_file)
        return ValidationRuleInfo(
            full_name=child_text(root, "fullName")
            or validation_rule_file.stem.replace(".validationRule-meta", ""),
            active=to_bool(child_text(root, "active")),
            description=child_text(root, "description"),
            error_display_field=child_text(root, "errorDisplayField"),
            error_message=child_text(root, "errorMessage"),
            error_condition_formula=child_text(root, "errorConditionFormula"),
            api_version=child_text(root, "apiVersion"),
        )

    def _parse_security_folder(self, folder: Path, kind: str) -> list[SecurityArtifact]:
        artifacts: list[SecurityArtifact] = []
        if not folder.exists():
            return artifacts

        for meta_file in sorted(folder.glob("*.xml")):
            root = parse_xml(meta_file)
            artifact = SecurityArtifact(
                name=meta_file.name.split(".")[0],
                label=child_text(root, "label") or child_text(root, "fullName"),
                kind=kind,
                is_custom=to_bool(child_text(root, "custom") or "false"),
                description=child_text(root, "description"),
                source_path=meta_file,
            )

            for node in root.findall("sf:objectPermissions", SF_NS):
                artifact.object_permissions.append(
                    ObjectPermission(
                        object_name=child_text(node, "object"),
                        allow_read=to_bool(child_text(node, "allowRead")),
                        allow_create=to_bool(child_text(node, "allowCreate")),
                        allow_edit=to_bool(child_text(node, "allowEdit")),
                        allow_delete=to_bool(child_text(node, "allowDelete")),
                        view_all_records=to_bool(child_text(node, "viewAllRecords")),
                        modify_all_records=to_bool(child_text(node, "modifyAllRecords")),
                    )
                )

            for node in root.findall("sf:fieldPermissions", SF_NS):
                artifact.field_permissions.append(
                    FieldPermission(
                        field_name=child_text(node, "field"),
                        readable=to_bool(child_text(node, "readable")),
                        editable=to_bool(child_text(node, "editable")),
                    )
                )

            for node in root.findall("sf:userPermissions", SF_NS):
                artifact.user_permissions.append(
                    UserPermission(
                        name=child_text(node, "name"),
                        enabled=to_bool(child_text(node, "enabled")),
                    )
                )

            for node in root.findall("sf:applicationVisibilities", SF_NS):
                artifact.application_visibilities.append(
                    VisibilityItem(
                        name=child_text(node, "application"),
                        visible=child_text(node, "visible"),
                        default=child_text(node, "default"),
                    )
                )

            for node in root.findall("sf:tabVisibilities", SF_NS) + root.findall("sf:tabSettings", SF_NS):
                artifact.tab_visibilities.append(
                    VisibilityItem(
                        name=child_text(node, "tab"),
                        visible=child_text(node, "visibility"),
                        default=child_text(node, "default"),
                    )
                )

            for node in root.findall("sf:classAccesses", SF_NS):
                artifact.class_accesses.append(
                    NamedAccess(
                        name=child_text(node, "apexClass"),
                        enabled=to_bool(child_text(node, "enabled")),
                    )
                )

            for node in root.findall("sf:flowAccesses", SF_NS):
                artifact.flow_accesses.append(
                    NamedAccess(
                        name=child_text(node, "flow"),
                        enabled=to_bool(child_text(node, "enabled")),
                    )
                )

            for node in root.findall("sf:pageAccesses", SF_NS):
                artifact.page_accesses.append(
                    NamedAccess(
                        name=child_text(node, "apexPage"),
                        enabled=to_bool(child_text(node, "enabled")),
                    )
                )

            for node in root.findall("sf:customPermissions", SF_NS):
                artifact.custom_permissions.append(
                    NamedAccess(
                        name=child_text(node, "name"),
                        enabled=to_bool(child_text(node, "enabled")),
                    )
                )

            for node in root.findall("sf:recordTypeVisibilities", SF_NS):
                artifact.record_type_visibilities.append(
                    RecordTypeVisibility(
                        record_type=child_text(node, "recordType"),
                        visible=to_bool(child_text(node, "visible")),
                        default=to_bool(child_text(node, "default")),
                    )
                )

            artifacts.append(artifact)

        return artifacts

    def _parse_permission_set_groups(self, folder: Path) -> list[PermissionSetGroupInfo]:
        groups: list[PermissionSetGroupInfo] = []
        if not folder.exists():
            return groups

        for meta_file in sorted(folder.glob("*.permissionsetgroup-meta.xml")):
            root = parse_xml(meta_file)
            if root is None:
                continue

            ps_list = []
            for node in root.findall("sf:permissionSets", SF_NS):
                ps_list.append(node.text)

            groups.append(PermissionSetGroupInfo(
                name=meta_file.name.split(".")[0],
                label=child_text(root, "label") or meta_file.name.split(".")[0],
                description=child_text(root, "description"),
                status=child_text(root, "status"),
                permission_sets=ps_list,
                source_path=meta_file,
            ))
        return groups

        # 5. Flow redundancy detection
        self.log("Analyse de redondance des Flows...")
        # Group flows by object and trigger type
        flow_groups: dict[tuple[str, str], list[FlowInfo]] = {}
        for flow in snapshot.flows:
            if flow.status != "Active":
                continue
            if not flow.start_object or not flow.trigger_type:
                continue
            key = (flow.start_object, flow.trigger_type)
            flow_groups.setdefault(key, []).append(flow)
        
        for (obj, trigger), flows in flow_groups.items():
            if len(flows) > 1:
                snapshot.redundant_flows.append(RedundantFlowGroup(
                    object_name=obj,
                    trigger_type=trigger,
                    flows=[f.name for f in flows]
                ))
                
    def _parse_apex_folder(self, folder: Path, kind: str) -> list[ApexArtifact]:
        artifacts: list[ApexArtifact] = []
        pattern = "*.cls" if kind == "class" else "*.trigger"
        if not folder.exists():
            return artifacts

        for source_file in sorted(folder.glob(pattern)):
            body = source_file.read_text(encoding="utf-8")
            meta_file = source_file.with_name(f"{source_file.name}-meta.xml")
            api_version = ""
            status = ""
            if meta_file.exists():
                root = parse_xml(meta_file)
                api_version = child_text(root, "apiVersion")
                status = child_text(root, "status")

            artifact = ApexArtifact(
                name=source_file.stem,
                kind=kind,
                body=body,
                source_path=source_file,
                api_version=api_version,
                status=status,
            )
            artifact.line_count = len(body.splitlines())
            artifact.method_count = len(
                re.findall(
                    r"(?mi)^\s*(?:public|private|protected|global)\s+(?:static\s+)?[\w<>\[\],]+\s+\w+\s*\(",
                    body,
                )
            )
            artifact.soql_count = len(re.findall(r"\[\s*SELECT\b|Database\.query\s*\(", body, re.IGNORECASE))
            artifact.sosl_count = len(re.findall(r"\[\s*FIND\b|Search\.query\s*\(", body, re.IGNORECASE))
            artifact.dml_count = len(
                re.findall(
                    r"(?i)\b(?:insert|update|upsert|delete|undelete|merge)\b|Database\.(?:insert|update|upsert|delete|undelete|merge)\s*\(",
                    body,
                )
            )
            artifact.comment_line_count = sum(
                1 for line in body.splitlines() if line.strip().startswith(("//", "/*", "*"))
            )
            artifact.system_debug_count = len(re.findall(r"System\.debug\s*\(", body))
            artifact.has_try_catch = "try" in body and "catch" in body
            sharing_match = re.search(
                r"(?i)\b(with sharing|without sharing|inherited sharing)\b", body
            )
            artifact.sharing_declaration = sharing_match.group(1) if sharing_match else ""
            artifact.is_test = bool(re.search(r"(?i)@isTest\b|\btestMethod\b", body))
            _soql_loop_line = _detect_pattern_in_loop(body, _SOQL_IN_LOOP_RE)
            artifact.query_in_loop = _soql_loop_line is not None
            artifact.query_in_loop_line = _soql_loop_line
            _dml_loop_line = _detect_pattern_in_loop(body, _DML_IN_LOOP_RE)
            artifact.dml_in_loop = _dml_loop_line is not None
            artifact.dml_in_loop_line = _dml_loop_line
            artifacts.append(artifact)

        return artifacts

    def _parse_flows(self, folder: Path) -> list[FlowInfo]:
        flows: list[FlowInfo] = []
        if not folder.exists():
            return flows

        interesting_tags = [
            "actionCalls",
            "assignments",
            "collectionProcessors",
            "decisions",
            "formulas",
            "loops",
            "recordCreates",
            "recordDeletes",
            "recordLookups",
            "recordUpdates",
            "screens",
            "subflows",
            "transforms",
            "waits",
        ]

        for flow_file in sorted(folder.glob("*.flow-meta.xml")):
            root = parse_xml(flow_file)
            element_counts = Counter()
            elements: list[FlowElementInfo] = []
            described = 0
            undocumented = 0
            adjacency: dict[str, list[str]] = {}
            structural_types = {"decisions", "loops", "subflows"}
            nodes_by_name: dict[str, str] = {}

            for tag in interesting_tags:
                for node in root.findall(f"sf:{tag}", SF_NS):
                    element_counts[tag] += 1
                    description = child_text(node, "description")
                    if description:
                        described += 1
                    else:
                        undocumented += 1

                    name = child_text(node, "name")
                    if name:
                        nodes_by_name[name] = tag
                        adjacency.setdefault(name, [])

                    target = ""
                    connector = node.find("sf:connector/sf:targetReference", SF_NS)
                    if connector is not None and connector.text:
                        target = connector.text.strip()
                        if name:
                            adjacency[name].append(target)

                    if tag == "decisions":
                        for rule in node.findall("sf:rules", SF_NS):
                            rule_connector = rule.find("sf:connector", SF_NS)
                            rule_target = (
                                child_text(rule_connector, "targetReference") if rule_connector is not None else ""
                            )
                            if name and rule_target:
                                adjacency[name].append(rule_target)
                        default_connector = node.find("sf:defaultConnector", SF_NS)
                        default_target = (
                            child_text(default_connector, "targetReference")
                            if default_connector is not None
                            else ""
                        )
                        if name and default_target:
                            adjacency[name].append(default_target)
                    elif tag == "loops":
                        next_connector = node.find("sf:nextValueConnector", SF_NS)
                        next_target = (
                            child_text(next_connector, "targetReference") if next_connector is not None else ""
                        )
                        if name and next_target:
                            adjacency[name].append(next_target)
                        end_connector = node.find("sf:noMoreValuesConnector", SF_NS)
                        end_target = (
                            child_text(end_connector, "targetReference") if end_connector is not None else ""
                        )
                        if name and end_target:
                            adjacency[name].append(end_target)

                    fault_connector = node.find("sf:faultConnector", SF_NS)
                    fault_target = (
                        child_text(fault_connector, "targetReference") if fault_connector is not None else ""
                    )
                    if name and fault_target:
                        adjacency[name].append(fault_target)

                    elements.append(
                        FlowElementInfo(
                            element_type=tag,
                            name=name,
                            label=child_text(node, "label"),
                            description=description,
                            target=target,
                        )
                    )

            variables = root.findall("sf:variables", SF_NS)
            variable_total = len(variables)
            variable_input = 0
            variable_output = 0
            for variable in variables:
                if to_bool(child_text(variable, "isInput")):
                    variable_input += 1
                if to_bool(child_text(variable, "isOutput")):
                    variable_output += 1

            start_node = ""
            start = root.find("sf:start", SF_NS)
            if start is not None:
                start_connector = start.find("sf:connector", SF_NS)
                start_node = child_text(start_connector, "targetReference") if start_connector is not None else ""

            max_width = 1
            for decision in root.findall("sf:decisions", SF_NS):
                width = len(decision.findall("sf:rules", SF_NS))
                if decision.find("sf:defaultConnector", SF_NS) is not None:
                    width += 1
                max_width = max(max_width, width)

            min_height = 0
            max_height = 0
            max_depth = 0
            dml_in_loop = False
            soql_in_loop = False

            if start_node and start_node in nodes_by_name:
                paths = self._flow_paths(start_node, adjacency)
                if paths:
                    min_height = min(len(path) for path in paths)
                    max_height = max(len(path) for path in paths)
                    for path in paths:
                        depth = sum(
                            1
                            for node_name in path
                            if nodes_by_name.get(node_name) in structural_types
                        )
                        max_depth = max(max_depth, depth)

            # Check for DML/SOQL in loops
            dml_ops = {"recordCreates", "recordUpdates", "recordDeletes"}
            soql_ops = {"recordLookups"}
            
            for loop_node in root.findall("sf:loops", SF_NS):
                loop_name = child_text(loop_node, "name")
                next_connector = loop_node.find("sf:nextValueConnector", SF_NS)
                next_target = child_text(next_connector, "targetReference") if next_connector is not None else ""
                
                if next_target:
                    if self._is_node_reachable(next_target, dml_ops, loop_name, nodes_by_name, adjacency):
                        dml_in_loop = True
                    if self._is_node_reachable(next_target, soql_ops, loop_name, nodes_by_name, adjacency):
                        soql_in_loop = True
                
                if dml_in_loop and soql_in_loop:
                    break

            flow = FlowInfo(
                name=flow_file.stem.replace(".flow-meta", ""),
                label=child_text(root, "label"),
                description=child_text(root, "description"),
                process_type=child_text(root, "processType"),
                status=child_text(root, "status"),
                api_version=child_text(root, "apiVersion"),
                trigger_type=child_text(root.find("sf:start", SF_NS), "triggerType")
                if root.find("sf:start", SF_NS) is not None
                else "",
                start_object=child_text(root.find("sf:start", SF_NS), "object")
                if root.find("sf:start", SF_NS) is not None
                else "",
                source_path=flow_file,
                element_counts=dict(element_counts),
                described_elements=described,
                undocumented_elements=undocumented,
                total_elements=sum(element_counts.values()),
                variable_total=variable_total,
                variable_input=variable_input,
                variable_output=variable_output,
                max_width=max_width,
                min_height=min_height,
                max_height=max_height,
                max_depth=max_depth,
                elements=elements,
                dml_in_loop=dml_in_loop,
                soql_in_loop=soql_in_loop,
            )
            flows.append(flow)

        return flows

    def _flow_paths(self, start_node: str, adjacency: dict[str, list[str]]) -> list[list[str]]:
        paths: list[list[str]] = []
        stack: list[tuple[str, list[str]]] = [(start_node, [start_node])]
        safeguard = 0

        while stack and safeguard < 5000:
            safeguard += 1
            current, path = stack.pop()
            neighbors = adjacency.get(current, [])
            if not neighbors:
                paths.append(path)
                continue

            advanced = False
            for neighbor in neighbors:
                if neighbor and neighbor not in path:
                    stack.append((neighbor, [*path, neighbor]))
                    advanced = True
            if not advanced:
                paths.append(path)

        return paths

    def _is_node_reachable(
        self,
        start_node: str,
        target_types: set[str],
        end_node: str,
        nodes_by_name: dict[str, str],
        adjacency: dict[str, list[str]],
    ) -> bool:
        if not start_node or start_node not in nodes_by_name:
            return False

        visited = set()
        stack = [start_node]

        while stack:
            current = stack.pop()
            if current == end_node:
                continue
            if current in visited:
                continue
            visited.add(current)

            if nodes_by_name.get(current) in target_types:
                return True

            for neighbor in adjacency.get(current, []):
                if neighbor:
                    stack.append(neighbor)

        return False

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
                "omniuicards",
                "omnidatatransforms",
                "omniprocesses",
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
                    rows.append(
                        {
                            "Nom": meta_file.stem.split(".")[0],
                            "Categorie": label,
                            "Dossier": meta_file.parent.name,
                            "TypeFichier": "".join(meta_file.suffixes),
                            "Source": self._safe_relative_path(meta_file),
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

    def _parse_agents(self, package_root: Path) -> list[AgentInfo]:
        """Parse agents from all known Salesforce metadata locations:

        * ``aiAuthoringBundles/`` — Agentforce agents stored as YAML ``.agent``
          files (one per sub-folder, e.g. ``aiAuthoringBundles/MyAgent/MyAgent.agent``).
        * ``bots/`` — Einstein / Service-Cloud bots stored as XML
          ``.bot-meta.xml`` files (one per sub-folder).
        * ``agents/`` — legacy location using ``.agent-meta.xml`` XML files.
        """
        agents: list[AgentInfo] = []

        # --- aiAuthoringBundles (Agentforce, .agent YAML) ---
        ai_bundles_folder = package_root / "aiAuthoringBundles"
        if ai_bundles_folder.exists():
            for agent_file in sorted(ai_bundles_folder.rglob("*.agent")):
                name, label, description, agent_type = _parse_dot_agent_file(agent_file)
                agents.append(
                    AgentInfo(
                        name=name,
                        label=label,
                        description=description,
                        agent_type=agent_type,
                        source_path=agent_file,
                    )
                )

        # --- bots (Einstein / Service bots, .bot-meta.xml XML) ---
        bots_folder = package_root / "bots"
        if bots_folder.exists():
            for bot_file in sorted(bots_folder.rglob("*.bot-meta.xml")):
                root = parse_xml(bot_file)
                if root is None:
                    continue
                # Label / name are under <botMlDomain>
                bot_ml = root.find("{http://soap.sforce.com/2006/04/metadata}botMlDomain")
                if bot_ml is not None:
                    label = child_text(bot_ml, "label")
                    name = child_text(bot_ml, "name")
                else:
                    name = bot_file.stem.replace(".bot-meta", "")
                    label = name
                agent_type = child_text(root, "agentType") or "Bot"
                agents.append(
                    AgentInfo(
                        name=name or bot_file.stem.replace(".bot-meta", ""),
                        label=label,
                        description="",
                        agent_type=agent_type,
                        source_path=bot_file,
                    )
                )

        # --- agents/ (legacy XML .agent-meta.xml) ---
        legacy_folder = package_root / "agents"
        if legacy_folder.exists():
            for agent_file in sorted(legacy_folder.glob("*.agent-meta.xml")):
                root = parse_xml(agent_file)
                agents.append(
                    AgentInfo(
                        name=agent_file.stem.replace(".agent-meta", ""),
                        label=child_text(root, "label"),
                        description=child_text(root, "description"),
                        agent_type="",
                        source_path=agent_file,
                    )
                )

        return agents

    def _parse_gen_ai_prompts(self, folder: Path) -> list[GenAiPromptInfo]:
        prompts: list[GenAiPromptInfo] = []
        if not folder.exists():
            return prompts
        for prompt_file in sorted(folder.glob("*.genAiPromptTemplate-meta.xml")):
            root = parse_xml(prompt_file)
            prompts.append(
                GenAiPromptInfo(
                    name=prompt_file.stem.replace(".genAiPromptTemplate-meta", ""),
                    label=child_text(root, "masterLabel"),
                    description=child_text(root, "description"),
                    source_path=prompt_file,
                )
            )
        return prompts

    def _parse_lwc(self, folder: Path) -> list[LwcInfo]:
        components: list[LwcInfo] = []
        if not folder.exists():
            return components

        for component_dir in sorted(path for path in folder.iterdir() if path.is_dir()):
            name = component_dir.name
            if self._is_excluded("lwc", name):
                continue

            meta_file = component_dir / f"{name}.js-meta.xml"
            info = LwcInfo(name=name, source_path=component_dir)

            if meta_file.exists():
                root = parse_xml(meta_file)
                info.label = child_text(root, "masterLabel")
                info.description = child_text(root, "description")
                info.api_version = child_text(root, "apiVersion")
                info.is_exposed = to_bool(child_text(root, "isExposed"))
                info.targets = child_texts(root.find("sf:targets", SF_NS), "target")

            js_file = component_dir / f"{name}.js"
            if js_file.exists():
                try:
                    js_content = js_file.read_text(encoding="utf-8")
                    info.line_count_js = len(js_content.splitlines())
                    info.has_aura_enabled = "@AuraEnabled" in js_content
                except OSError:
                    pass

            html_file = component_dir / f"{name}.html"
            if html_file.exists():
                try:
                    html_content = html_file.read_text(encoding="utf-8")
                    info.line_count_html = len(html_content.splitlines())
                except OSError:
                    pass

            components.append(info)

        return components

    def _parse_aura(self, folder: Path) -> list[AuraInfo]:
        components: list[AuraInfo] = []
        if not folder.exists():
            return components

        for component_dir in sorted(path for path in folder.iterdir() if path.is_dir()):
            name = component_dir.name
            if self._is_excluded("aura", name):
                continue

            info = AuraInfo(name=name, source_path=component_dir)

            meta_file = component_dir / f"{name}.cmp-meta.xml"
            if meta_file.exists():
                root = parse_xml(meta_file)
                info.api_version = child_text(root, "apiVersion")

            cmp_file = component_dir / f"{name}.cmp"
            if cmp_file.exists():
                try:
                    cmp_content = cmp_file.read_text(encoding="utf-8")
                    info.line_count_cmp = len(cmp_content.splitlines())
                except OSError:
                    pass

            for js_suffix in ("Controller.js", "Helper.js"):
                js_file = component_dir / f"{name}{js_suffix}"
                if js_file.exists():
                    try:
                        js_content = js_file.read_text(encoding="utf-8")
                        info.line_count_js += len(js_content.splitlines())
                    except OSError:
                        pass

            components.append(info)

        return components

    def _parse_sharing_rules(self, folder: Path) -> list[SharingRuleInfo]:
        """Parse all .sharingRules-meta.xml files, skipping empty ones."""
        rules: list[SharingRuleInfo] = []
        if not folder.exists():
            return rules

        TYPE_MAP = {
            "sharingCriteriaRules": "criteria",
            "sharingOwnerRules": "owner",
            "sharingGuestRules": "guest",
            "sharingTerritoryRules": "territory",
        }

        for sr_file in sorted(folder.glob("*.sharingRules-meta.xml")):
            object_name = sr_file.name.replace(".sharingRules-meta.xml", "")
            root = parse_xml(sr_file)
            if root is None:
                continue
            # Skip files whose root element has no children (= empty sharing rules)
            if len(list(root)) == 0:
                continue
            for xml_tag, rule_type in TYPE_MAP.items():
                for rule_el in root.findall(f"sf:{xml_tag}", SF_NS):
                    full_name = child_text(rule_el, "fullName") or child_text(rule_el, "label") or ""
                    label = child_text(rule_el, "label") or ""
                    description = child_text(rule_el, "description") or ""
                    if not full_name:
                        continue
                    rules.append(
                        SharingRuleInfo(
                            full_name=full_name,
                            object_name=object_name,
                            rule_type=rule_type,
                            label=label,
                            description=description,
                        )
                    )
        return rules

    def _parse_duplicate_rules(self, folder: Path) -> list[DuplicateRuleInfo]:
        rules: list[DuplicateRuleInfo] = []
        if not folder.exists():
            return rules

        for dr_file in sorted(folder.glob("*.duplicateRule-meta.xml")):
            object_name = dr_file.name.replace(".duplicateRule-meta.xml", "")
            root = parse_xml(dr_file)
            if root is None:
                continue
            
            rules.append(DuplicateRuleInfo(
                full_name=child_text(root, "fullName") or dr_file.stem.replace(".duplicateRule-meta", ""),
                object_name=object_name,
                action_on_insert=child_text(root, "actionOnInsert"),
                action_on_update=child_text(root, "actionOnUpdate"),
                active=to_bool(child_text(root, "isActive")),
            ))
        return rules

    def _analyze_dependencies(self, snapshot: MetadataSnapshot) -> None:
        """Perform a basic dependency analysis by scanning metadata for references."""
        self.log("Analyse des dependances (Impact Analysis)...")
        
        object_names = {obj.api_name for obj in snapshot.objects}
        apex_names = {art.name for art in snapshot.apex_artifacts}
        
        # Pre-calculate field names for scanning
        all_fields = []
        for obj in snapshot.objects:
            for field in obj.fields:
                all_fields.append((obj.api_name, field.api_name))

        # 1. Scan Apex for Object, Class and Field dependencies
        for artifact in snapshot.apex_artifacts:
            body_lower = artifact.body.lower()
            for obj_name in object_names:
                if obj_name.lower() in body_lower:
                    snapshot.dependencies.append(Dependency(
                        source_name=artifact.name,
                        source_kind=artifact.kind,
                        target_name=obj_name,
                        target_kind="Object"
                    ))
            for other_apex in apex_names:
                if other_apex != artifact.name and other_apex.lower() in body_lower:
                    snapshot.dependencies.append(Dependency(
                        source_name=artifact.name,
                        source_kind=artifact.kind,
                        target_name=other_apex,
                        target_kind="Apex"
                    ))
            
            # Field scanning (limited to common patterns: Obj.Field or [SELECT ... Field ...])
            for obj_name, field_name in all_fields:
                pattern = f"{obj_name}.{field_name}".lower()
                if pattern in body_lower:
                    snapshot.dependencies.append(Dependency(
                        source_name=artifact.name,
                        source_kind=artifact.kind,
                        target_name=f"{obj_name}.{field_name}",
                        target_kind="Field"
                    ))

        # 2. Scan Flows for Object dependencies
        for flow in snapshot.flows:
            if flow.start_object:
                snapshot.dependencies.append(Dependency(
                    source_name=flow.name,
                    source_kind="Flow",
                    target_name=flow.start_object,
                    target_kind="Object"
                ))
            
            # Scan elements for object references
            for element in flow.elements:
                if element.element_type in ("recordLookups", "recordCreates", "recordUpdates", "recordDeletes"):
                    # We don't store the object name in FlowElementInfo yet, but we could parse it
                    pass
                
                if element.element_type == "actionCalls":
                    # Check for Apex actions
                    # The Apex class name is often in the 'actionName' attribute or child node
                    pass
            
            # Simple text scan of Flow XML for Apex class names
            try:
                flow_xml = flow.source_path.read_text(encoding="utf-8", errors="ignore")
                for apex_name in apex_names:
                    if f">{apex_name}<" in flow_xml or f"/{apex_name}<" in flow_xml:
                        snapshot.dependencies.append(Dependency(
                            source_name=flow.name,
                            source_kind="Flow",
                            target_name=apex_name,
                            target_kind="Apex"
                        ))
            except Exception:
                pass

        # 3. Scan Reports for Object dependencies
        for row in snapshot.inventory.get("reports", []):
            source = str(row.get("Source") or "")
            if not source:
                continue
            candidate = self.source_dir / source
            if not candidate.exists():
                continue
            try:
                content = candidate.read_text(encoding="utf-8", errors="ignore")
                for obj_name in object_names:
                    if f"<reportType>{obj_name}</reportType>" in content or f"<reportType>{obj_name}_" in content:
                        snapshot.dependencies.append(Dependency(
                            source_name=str(row.get("Nom")),
                            source_kind="Report",
                            target_name=obj_name,
                            target_kind="Object"
                        ))
            except OSError:
                continue
        
        # 4. Orphan detection
        self.log("Detection des composants orphelins...")
        used_targets = {(d.target_name, d.target_kind) for d in snapshot.dependencies}
        
        # Apex orphans
        for artifact in snapshot.apex_artifacts:
            if artifact.is_test:
                continue
            if (artifact.name, "Apex") not in used_targets:
                # Check if it's a trigger (triggers are entry points)
                if artifact.kind == "trigger":
                    continue
                snapshot.orphans.append(OrphanInfo(
                    name=artifact.name,
                    kind="Apex Class",
                    source_path=artifact.source_path
                ))
        
        # Object orphans (standard objects are never orphans)
        for obj in snapshot.objects:
            if not obj.custom:
                continue
            if (obj.api_name, "Object") not in used_targets:
                snapshot.orphans.append(OrphanInfo(
                    name=obj.api_name,
                    kind="Custom Object",
                    source_path=obj.source_path
                ))
                
        # Field orphans
        for obj in snapshot.objects:
            for field in obj.fields:
                if not field.custom:
                    continue
                field_full_name = f"{obj.api_name}.{field.api_name}"
                if (field_full_name, "Field") not in used_targets:
                    snapshot.orphans.append(OrphanInfo(
                        name=field_full_name,
                        kind="Custom Field",
                        source_path=obj.source_path
                    ))
        
        # Flow orphans
        for flow in snapshot.flows:
            if (flow.name, "Flow") not in used_targets:
                # Flows can be entry points (Screen flows, scheduled flows)
                if flow.process_type in ("Flow", "AutoLaunchedFlow") and not flow.trigger_type:
                    # Potential orphan if not called by anything
                    snapshot.orphans.append(OrphanInfo(
                        name=flow.name,
                        kind="Flow",
                        source_path=flow.source_path
                    ))

    def _safe_relative_path(self, path: Path) -> str:
        try:
            return str(path.relative_to(self.source_dir)).replace("\\", "/")
        except ValueError:
            return str(path)


# ---------------------------------------------------------------------------
# Agent YAML parser helper
# ---------------------------------------------------------------------------

_AGENT_LABEL_RE = re.compile(r"agent_label\s*:\s*['\"]?([^'\"\n]+)['\"]?", re.IGNORECASE)
_AGENT_TYPE_RE = re.compile(r"agent_type\s*:\s*['\"]?([^'\"\n]+)['\"]?", re.IGNORECASE)
_AGENT_DESC_RE = re.compile(r"description\s*:\s*['\"]?([^'\"\n]+)['\"]?", re.IGNORECASE)
_AGENT_DEV_NAME_RE = re.compile(r"developer_name\s*:\s*['\"]?([^'\"\n]+)['\"]?", re.IGNORECASE)


def _parse_dot_agent_file(path: Path) -> tuple[str, str, str, str]:
    """Parse a Salesforce Agentforce ``.agent`` file (YAML-ish format).

    Returns ``(name, label, description, agent_type)``.  Falls back to the
    file stem when a field cannot be extracted.
    """
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        stem = path.stem
        return stem, stem, "", ""

    def _extract(pattern: re.Pattern) -> str:
        m = pattern.search(text)
        return m.group(1).strip() if m else ""

    # The folder / file stem is the API name of the bundle (unique per org).
    # The developer_name inside the file can differ (e.g. duplicate bundles),
    # so we use the stem as the canonical name.
    name = path.stem
    label = _extract(_AGENT_LABEL_RE) or _extract(_AGENT_DEV_NAME_RE) or name
    description = _extract(_AGENT_DESC_RE)
    agent_type = _extract(_AGENT_TYPE_RE)
    return name, label, description, agent_type


# ---------------------------------------------------------------------------
# Brace-aware DML/SOQL-in-loop detection helpers
# ---------------------------------------------------------------------------

_SOQL_IN_LOOP_RE = re.compile(
    r"\[\s*SELECT\b|Database\.query\s*\(", re.IGNORECASE
)
_DML_IN_LOOP_RE = re.compile(
    r"\b(?:insert|update|upsert|delete|undelete|merge)\b"
    r"|Database\.(?:insert|update|upsert|delete|undelete|merge)\s*\(",
    re.IGNORECASE,
)
_LOOP_KEYWORD_RE = re.compile(r"\b(for|while|do)\b", re.IGNORECASE)


def _strip_apex_comments(body: str) -> str:
    """Return *body* with comments (// and /* */) and string literals replaced
    by spaces, preserving newlines so that line numbers stay correct."""
    out = list(body)
    i = 0
    n = len(body)
    while i < n:
        ch = body[i]
        nxt = body[i + 1] if i + 1 < n else ""
        if ch == "/" and nxt == "/":
            # single-line comment: blank to end of line
            while i < n and body[i] != "\n":
                out[i] = " "
                i += 1
        elif ch == "/" and nxt == "*":
            # block comment
            out[i] = " "
            i += 1
            out[i] = " "
            i += 1
            while i < n:
                if body[i] == "*" and i + 1 < n and body[i + 1] == "/":
                    out[i] = " "
                    i += 1
                    out[i] = " "
                    i += 1
                    break
                elif body[i] != "\n":
                    out[i] = " "
                i += 1
        elif ch in ('"', "'"):
            quote = ch
            out[i] = " "
            i += 1
            while i < n and body[i] != quote:
                if body[i] == "\\" and i + 1 < n:
                    out[i] = " "
                    i += 1
                    out[i] = " "
                    i += 1
                elif body[i] != "\n":
                    out[i] = " "
                    i += 1
                else:
                    i += 1
            if i < n:
                out[i] = " "
                i += 1
        else:
            i += 1
    return "".join(out)


def _detect_pattern_in_loop(body: str, pattern: re.Pattern) -> int | None:
    """Return the 1-based line number of the first *pattern* match found
    inside an Apex loop body (for / while / do-while), or ``None``.

    The search is brace-aware: it extracts the exact body delimited by the
    matching closing brace before searching, so a DML/SOQL statement written
    *after* a loop (but within a few hundred characters) is **not** reported
    as a false positive.

    The function also ignores matches in the loop header itself — e.g. the
    SOQL written directly in ``for (SObject s : [SELECT ...])`` is skipped
    because that is the recommended pattern and does not cause governor issues.
    """
    clean = _strip_apex_comments(body)
    n = len(clean)
    i = 0

    while i < n:
        m = _LOOP_KEYWORD_RE.search(clean, i)
        if not m:
            break

        keyword = m.group(1).lower()
        pos = m.end()

        if keyword == "do":
            # do { ... } while (...)
            while pos < n and clean[pos] in " \t\r\n":
                pos += 1
            if pos >= n or clean[pos] != "{":
                i = m.end()
                continue
        else:
            # for / while: skip the condition (...)
            while pos < n and clean[pos] in " \t\r\n":
                pos += 1
            if pos >= n or clean[pos] != "(":
                i = m.end()
                continue
            # skip the entire condition, counting nested parens
            depth = 1
            pos += 1
            while pos < n and depth > 0:
                if clean[pos] == "(":
                    depth += 1
                elif clean[pos] == ")":
                    depth -= 1
                pos += 1
            # skip whitespace/newlines to reach the loop body {
            while pos < n and clean[pos] in " \t\r\n":
                pos += 1
            if pos >= n or clean[pos] != "{":
                # No braces: single-statement loop — still check it
                # by scanning to end of statement (next ;)
                stmt_start = pos
                stmt_end = clean.find(";", pos)
                if stmt_end == -1:
                    i = m.end()
                    continue
                hit = pattern.search(clean, stmt_start, stmt_end + 1)
                if hit:
                    return clean[: hit.end()].count("\n") + 1
                i = stmt_end + 1
                continue

        # Found the loop body opening brace — extract body by depth
        body_start = pos + 1
        depth = 1
        pos += 1
        while pos < n and depth > 0:
            if clean[pos] == "{":
                depth += 1
            elif clean[pos] == "}":
                depth -= 1
            pos += 1
        body_end = pos - 1  # exclusive; points at char after '}'

        hit = pattern.search(clean, body_start, body_end)
        if hit:
            return clean[: hit.end()].count("\n") + 1

        # Move past this loop and continue (handles nested / sequential loops)
        i = pos

    return None
