"""Parsing of agents, GenAI prompts, LWC/Aura components and sharing/dup rules."""

from __future__ import annotations

from pathlib import Path

from src.core.models import (
    AgentInfo,
    AuraInfo,
    DuplicateRuleInfo,
    GenAiPromptInfo,
    LwcInfo,
    SharingRuleInfo,
)
from src.core.utils import SF_NS, child_text, child_texts, parse_xml, to_bool
from src.parsers.salesforce_parser.agent_helpers import _parse_dot_agent_file
from src.parsers.salesforce_parser.base import _ParserState


class _ComponentsMixin(_ParserState):
    """Parse agents, prompts, Lightning components and sharing/duplicate rules."""

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
                description=child_text(root, "description"),
                security_enforcement=child_text(root, "securityEnforcementConfiguration"),
            ))
        return rules
