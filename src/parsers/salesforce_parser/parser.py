"""Main :class:`SalesforceMetadataParser` assembling the thematic mixins."""

from __future__ import annotations

import json
from pathlib import Path

from src.core.models import (
    AgentInfo,
    ApexArtifact,
    CustomizationMetrics,
    DuplicateRuleInfo,
    FlowInfo,
    GenAiPromptInfo,
    MetadataSnapshot,
    ObjectInfo,
    SecurityArtifact,
    SharingRuleInfo,
)
from src.core.utils import child_text, parse_xml
from src.parsers.salesforce_parser.apex_mixin import _ApexMixin
from src.parsers.salesforce_parser.base import (
    LogCallback,
    _SEC_DANGEROUS_USER_PERMS,
    _SEC_SENSITIVE_OBJECTS,
)
from src.parsers.salesforce_parser.components_mixin import _ComponentsMixin
from src.parsers.salesforce_parser.dependencies_mixin import _DependenciesMixin
from src.parsers.salesforce_parser.exclusion_mixin import _ExclusionMixin
from src.parsers.salesforce_parser.flows_mixin import _FlowsMixin
from src.parsers.salesforce_parser.inventory_mixin import _InventoryMixin
from src.parsers.salesforce_parser.objects_mixin import _ObjectsMixin
from src.parsers.salesforce_parser.security_mixin import _SecurityMixin


class SalesforceMetadataParser(
    _ExclusionMixin,
    _ObjectsMixin,
    _SecurityMixin,
    _ApexMixin,
    _FlowsMixin,
    _InventoryMixin,
    _ComponentsMixin,
    _DependenciesMixin,
):
    """Parse a Salesforce DX source folder into a :class:`MetadataSnapshot`.

    Walks the well-known Salesforce metadata layout (objects, classes,
    triggers, flows, profiles, permission sets, etc.), produces structured
    Python dataclasses and applies an optional exclusion file so the caller
    can opt out of specific artefacts.
    """

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
            app_root = Path(__file__).resolve().parent.parent.parent.parent
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
            metrics.omni_integration_procedures += len(
                [
                    path
                    for path in (package_root / "omniIntegrationProcedures").glob("*.ip-meta.xml")
                    if not self._is_excluded("omni", path.stem.replace(".ip-meta", ""))
                ]
            )
            metrics.omni_ui_cards += len(
                [
                    path
                    for path in (package_root / "omniUiCards").glob("*.ouc-meta.xml")
                    if not self._is_excluded("omni", path.stem.replace(".ouc-meta", ""))
                ]
            )
            metrics.omni_ui_cards += len(
                [
                    path
                    for path in (package_root / "omniUiCards").glob("*.card-meta.xml")
                    if not self._is_excluded("omni", path.stem.replace(".card-meta", ""))
                ]
            )
            metrics.omni_ui_cards += len(
                [
                    path
                    for path in (package_root / "vlocityCards").glob("*.ouc-meta.xml")
                    if not self._is_excluded("omni", path.stem.replace(".ouc-meta", ""))
                ]
            )
            metrics.omni_data_transforms += len(
                [
                    path
                    for path in (package_root / "omniDataTransforms").glob("*.rpt-meta.xml")
                    if not self._is_excluded("omni", path.stem.replace(".rpt-meta", ""))
                ]
            )
            # Support for newer OmniStudio format (omniProcesses)
            for path in (package_root / "omniProcesses").glob("*.omniProcess-meta.xml"):
                name = path.stem.replace(".omniProcess-meta", "")
                if self._is_excluded("omni", name):
                    continue
                try:
                    root = parse_xml(path)
                    process_type = child_text(root, "omniProcessType")
                    if process_type == "Integration Procedure":
                        metrics.omni_integration_procedures += 1
                    elif process_type == "OmniScript":
                        metrics.omni_scripts += 1
                except Exception:
                    pass
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
