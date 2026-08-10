from __future__ import annotations

from pathlib import Path

from src.analyzer.apex_analyzer import analyze_apex_artifact
from src.analyzer.engine_call_graph import _detect_apex_call_cycles
from src.analyzer.engine_rule_exclusions import RuleExclusionMixin
from src.analyzer.flow_analyzer import analyze_flow
from src.analyzer.lwc_analyzer import analyze_lwc
from src.analyzer.aura_analyzer import analyze_aura
from src.analyzer.models import Finding, SEVERITY_ORDER
from src.analyzer.object_analyzer import analyze_object, analyze_validation_rule, analyze_duplicate_rule
from src.analyzer.omni_analyzer import analyze_data_transform
from src.analyzer.rule_catalog import RuleCatalog
from src.analyzer.security_analyzer import (
    analyze_org_security,
    analyze_permission_set,
    analyze_profile,
)
from src.core.models import (
    AgentInfo,
    ApexArtifact,
    AuraInfo,
    DEFAULT_PROFILES_PS_RATIO_THRESHOLDS,
    DuplicateRuleInfo,
    FlowInfo,
    GenAiPromptInfo,
    LwcInfo,
    MetadataSnapshot,
    ObjectInfo,
    ValidationRuleInfo,
)


class AnalyzerEngine(RuleExclusionMixin):
    """Orchestrateur de l'analyse statique ; retourne un ensemble de findings par artefact."""

    def __init__(self, catalog: RuleCatalog | None = None, exclusion_path: Path | str | None = None) -> None:
        self.catalog = catalog or RuleCatalog.load()
        self.rule_exclusions: dict[str, set[str]] = {}  # rule_id -> set of metadata names
        
        if exclusion_path:
            self.exclusion_path = Path(exclusion_path)
        else:
            # On cherche exclusion_PV.json ou exclusion.json
            app_root = Path(__file__).resolve().parent.parent.parent
            candidate_pv = app_root / "exclusion_PV.json"
            candidate_std = app_root / "exclusion.json"
            if candidate_pv.exists():
                self.exclusion_path = candidate_pv
            elif candidate_std.exists():
                self.exclusion_path = candidate_std
            else:
                self.exclusion_path = None
        
        if self.exclusion_path:
            self._load_rule_exclusions()

    # ------------------------------------------------------------------ per-artifact API

    def analyze_apex(self, artifact: ApexArtifact) -> list[Finding]:
        findings = analyze_apex_artifact(artifact, self.catalog)
        filtered = [f for f in findings if self._is_rule_applicable(f.rule, artifact.name, artifact.api_version)]
        return _sorted(filtered)

    def analyze_flow(self, flow: FlowInfo) -> list[Finding]:
        findings = analyze_flow(flow, self.catalog)
        filtered = [f for f in findings if self._is_rule_applicable(f.rule, flow.name, flow.api_version)]
        return _sorted(filtered)

    def analyze_object(self, obj: ObjectInfo) -> list[Finding]:
        findings = analyze_object(obj, self.catalog)
        filtered = [f for f in findings if self._is_rule_applicable(f.rule, obj.api_name, obj.api_version)]
        return _sorted(filtered)

    def analyze_validation_rule(
        self, vr: ValidationRuleInfo, object_name: str
    ) -> list[Finding]:
        findings = analyze_validation_rule(vr, object_name, self.catalog)
        # Pour les VR, on peut exclure soit par "Objet.NomVR", soit juste "NomVR"
        vr_full_name = f"{object_name}.{vr.full_name}"
        filtered = [
            f for f in findings 
            if self._is_rule_applicable(f.rule, vr_full_name, vr.api_version)
            and self._is_rule_applicable(f.rule, vr.full_name, vr.api_version)
        ]
        return _sorted(filtered)

    def analyze_duplicate_rule(
        self, dr: DuplicateRuleInfo, object_name: str
    ) -> list[Finding]:
        findings = analyze_duplicate_rule(dr, object_name, self.catalog)
        dr_full_name = f"{object_name}.{dr.full_name}"
        filtered = [
            f for f in findings 
            if self._is_rule_applicable(f.rule, dr_full_name)
            and self._is_rule_applicable(f.rule, dr.full_name)
        ]
        return _sorted(filtered)

    def analyze_data_transform(
        self, name: str, xml_content: str
    ) -> list[Finding]:
        findings = analyze_data_transform(name, xml_content, self.catalog)
        # On n'a pas forcément la version d'API pour les Data Transforms ici
        filtered = [f for f in findings if self._is_rule_applicable(f.rule, name)]
        return _sorted(filtered)

    def analyze_agent(self, agent: AgentInfo) -> list[Finding]:
        rules = self.catalog.for_scope("agent")
        findings: list[Finding] = []
        for rule in rules:
            if not self._is_rule_applicable(rule, agent.name):
                continue
            if rule.id == "AGENT-READ-001" and not agent.description:
                findings.append(
                    Finding(
                        rule=rule,
                        target_kind="Agent",
                        target_name=agent.name,
                        message="L'agent ne dispose d'aucune description.",
                        source_path=agent.source_path,
                    )
                )
        return _sorted(findings)

    def analyze_prompt(self, prompt: GenAiPromptInfo) -> list[Finding]:
        rules = self.catalog.for_scope("prompt")
        findings: list[Finding] = []
        for rule in rules:
            if not self._is_rule_applicable(rule, prompt.name):
                continue
            if rule.id == "PROMPT-READ-001" and not prompt.description:
                findings.append(
                    Finding(
                        rule=rule,
                        target_kind="GenAiPromptTemplate",
                        target_name=prompt.name,
                        message="Le prompt template ne dispose d'aucune description.",
                        source_path=prompt.source_path,
                    )
                )
        return _sorted(findings)

    def analyze_lwc(self, lwc: LwcInfo) -> list[Finding]:
        findings = analyze_lwc(lwc, self.catalog)
        filtered = [f for f in findings if self._is_rule_applicable(f.rule, lwc.name)]
        return _sorted(filtered)

    def analyze_aura(self, aura: AuraInfo) -> list[Finding]:
        findings = analyze_aura(aura, self.catalog)
        filtered = [f for f in findings if self._is_rule_applicable(f.rule, aura.name)]
        return _sorted(filtered)

    # ------------------------------------------------------------------ snapshot-level API

    def analyze_snapshot(self, snapshot: MetadataSnapshot) -> "AnalyzerReport":
        apex_findings: dict[str, list[Finding]] = {}
        for artifact in snapshot.apex_artifacts:
            apex_findings[artifact.name] = self.analyze_apex(artifact)

        for name, extra in _detect_apex_call_cycles(
            snapshot.apex_artifacts, self.catalog
        ).items():
            apex_findings.setdefault(name, []).extend(extra)
            apex_findings[name] = _sorted(apex_findings[name])

        flow_findings: dict[str, list[Finding]] = {}
        for flow in snapshot.flows:
            flow_findings[flow.name] = self.analyze_flow(flow)

        object_findings: dict[str, list[Finding]] = {}
        validation_findings: dict[str, list[Finding]] = {}
        duplicate_findings: dict[str, list[Finding]] = {}
        for obj in snapshot.objects:
            findings = self.analyze_object(obj)
            object_findings[obj.api_name] = findings
            for vr in obj.validation_rules:
                vr_key = f"{obj.api_name}.{vr.full_name}"
                validation_findings[vr_key] = self.analyze_validation_rule(vr, obj.api_name)
        
        for dr in snapshot.duplicate_rules:
            dr_key = f"{dr.object_name}.{dr.full_name}"
            duplicate_findings[dr_key] = self.analyze_duplicate_rule(dr, dr.object_name)

        omni_findings: dict[str, list[Finding]] = {}
        for row in snapshot.inventory.get("omnistudio", []):
            source = str(row.get("Source") or "")
            folder = str(row.get("Dossier") or "").lower()
            file_type = str(row.get("TypeFichier") or "").lower()
            is_dt = (
                "omnidatatransform" in folder
                or file_type.endswith(".rpt-meta.xml")
            )
            if not (is_dt and source):
                continue
            candidate = snapshot.source_dir / source
            if not candidate.exists() or not candidate.is_file():
                continue
            try:
                xml_text = candidate.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            name = str(row.get("Nom") or candidate.stem)
            omni_findings[name] = self.analyze_data_transform(name, xml_text)

        agent_findings: dict[str, list[Finding]] = {}
        for agent in snapshot.agents:
            agent_findings[agent.name] = self.analyze_agent(agent)

        prompt_findings: dict[str, list[Finding]] = {}
        for prompt in snapshot.gen_ai_prompts:
            prompt_findings[prompt.name] = self.analyze_prompt(prompt)

        lwc_findings: dict[str, list[Finding]] = {}
        for lwc in snapshot.lwc:
            lwc_findings[lwc.name] = self.analyze_lwc(lwc)

        aura_findings: dict[str, list[Finding]] = {}
        for aura in snapshot.aura:
            aura_findings[aura.name] = self.analyze_aura(aura)

        security_findings: dict[str, list[Finding]] = {}
        for profile in snapshot.profiles:
            f = analyze_profile(profile, self.catalog)
            if f:
                security_findings[profile.name] = _sorted(f)
        for ps in snapshot.permission_sets:
            f = analyze_permission_set(ps, self.catalog)
            if f:
                security_findings[ps.name] = _sorted(f)
        _ratio_thresholds = (
            snapshot.metrics.profiles_ps_ratio_thresholds or DEFAULT_PROFILES_PS_RATIO_THRESHOLDS
        )
        ratio_threshold = _ratio_thresholds[0]
        org_findings = analyze_org_security(
            snapshot.profiles, snapshot.permission_sets, self.catalog, ratio_threshold
        )
        if org_findings:
            security_findings["_org_"] = _sorted(org_findings)

        return AnalyzerReport(
            apex=apex_findings,
            flows=flow_findings,
            objects=object_findings,
            validation_rules=validation_findings,
            duplicate_rules=duplicate_findings,
            data_transforms=omni_findings,
            agents=agent_findings,
            prompts=prompt_findings,
            lwc=lwc_findings,
            aura=aura_findings,
            security=security_findings,
            rules_used=self.catalog.enabled,
        )


class AnalyzerReport:
    """Agrege les findings par type d'artefact et fournit des helpers de synthese."""

    def __init__(
        self,
        apex: dict[str, list[Finding]] | None = None,
        flows: dict[str, list[Finding]] | None = None,
        objects: dict[str, list[Finding]] | None = None,
        validation_rules: dict[str, list[Finding]] | None = None,
        duplicate_rules: dict[str, list[Finding]] | None = None,
        data_transforms: dict[str, list[Finding]] | None = None,
        agents: dict[str, list[Finding]] | None = None,
        prompts: dict[str, list[Finding]] | None = None,
        lwc: dict[str, list[Finding]] | None = None,
        aura: dict[str, list[Finding]] | None = None,
        security: dict[str, list[Finding]] | None = None,
        rules_used: list | None = None,
    ) -> None:
        self.apex = apex or {}
        self.flows = flows or {}
        self.objects = objects or {}
        self.validation_rules = validation_rules or {}
        self.duplicate_rules = duplicate_rules or {}
        self.data_transforms = data_transforms or {}
        self.agents = agents or {}
        self.prompts = prompts or {}
        self.lwc = lwc or {}
        self.aura = aura or {}
        self.security = security or {}
        self.rules_used = rules_used or []

    def all_findings(self) -> list[Finding]:
        collected: list[Finding] = []
        for group in (
            self.apex,
            self.flows,
            self.objects,
            self.validation_rules,
            self.duplicate_rules,
            self.data_transforms,
            self.agents,
            self.prompts,
            self.lwc,
            self.aura,
            self.security,
        ):
            for findings in group.values():
                collected.extend(findings)
        return collected

    def severity_counts(self) -> dict[str, int]:
        counts = {"Critical": 0, "Major": 0, "Minor": 0, "Info": 0}
        for finding in self.all_findings():
            key = finding.rule.severity
            counts[key] = counts.get(key, 0) + 1
        return counts

    def rule_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for finding in self.all_findings():
            counts[finding.rule.id] = counts.get(finding.rule.id, 0) + 1
        return counts

    def category_counts(self) -> dict[str, int]:
        counts = {"Trusted": 0, "Easy": 0, "Adaptable": 0}
        for finding in self.all_findings():
            counts[finding.rule.category] = counts.get(finding.rule.category, 0) + 1
        return counts


# ---------------------------------------------------------------------------- helpers


def _sorted(findings: list[Finding]) -> list[Finding]:
    return sorted(findings, key=lambda f: (SEVERITY_ORDER.get(f.rule.severity, 99), f.rule.id))
