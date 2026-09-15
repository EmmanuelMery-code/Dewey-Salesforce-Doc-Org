from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from src.analyzer.messages import DEFAULT_LANGUAGE, normalize_language, translate
from src.analyzer.models import Rule


DEFAULT_RULES_PATH = Path(__file__).with_name("rules.xml")


def _to_bool(value: str | None, default: bool = True) -> bool:
    if value is None:
        return default
    return value.strip().lower() == "true"


def _child(node: ET.Element, tag: str, default: str = "") -> str:
    child = node.find(tag)
    if child is None or child.text is None:
        return default
    return child.text.strip()


def _to_float(value: str | None) -> float | None:
    if value is None or not value.strip():
        return None
    try:
        return float(value.strip())
    except ValueError:
        return None


def _localized_child(node: ET.Element, tag: str, language: str) -> str:
    """Return ``tag`` in ``language``, falling back to the French wording.

    Translations live in a nested ``<translation lang="xx">`` block so the
    French text stays the readable default of ``rules.xml`` and an untranslated
    rule degrades to French instead of disappearing.
    """
    if language != DEFAULT_LANGUAGE:
        for translation in node.findall("translation"):
            if (translation.get("lang") or "").strip().lower() != language:
                continue
            translated = _child(translation, tag)
            if translated:
                return translated
    return _child(node, tag)


def load_rules(
    path: str | Path | None = None, language: str = DEFAULT_LANGUAGE
) -> list[Rule]:
    """Charge le catalogue de regles depuis le XML.

    Les regles ayant enabled=false sont conservees mais ignorees par l'engine.
    Les libelles sont charges dans ``language`` lorsqu'une traduction existe.
    """
    rules_path = Path(path) if path else DEFAULT_RULES_PATH
    language = normalize_language(language)
    if not rules_path.exists():
        return []

    tree = ET.parse(rules_path)
    root = tree.getroot()

    rules: list[Rule] = []
    for node in root.findall("rule"):
        rule_id = (node.get("id") or "").strip()
        if not rule_id:
            continue
        rules.append(
            Rule(
                id=rule_id,
                enabled=_to_bool(node.get("enabled"), default=True),
                scope=(node.get("scope") or "").strip(),
                category=(node.get("category") or "").strip(),
                subcategory=(node.get("subcategory") or "").strip(),
                severity=(node.get("severity") or "Info").strip(),
                source=(node.get("source") or "").strip(),
                reference=(node.get("reference") or "").strip(),
                title=_localized_child(node, "title", language),
                description=_localized_child(node, "description", language),
                rationale=_localized_child(node, "rationale", language),
                remediation=_localized_child(node, "remediation", language),
                min_api_version=_to_float(node.get("min_api_version")),
                max_api_version=_to_float(node.get("max_api_version")),
            )
        )
    return rules


class RuleCatalog:
    """Accesseur centralise aux regles activees / desactivees."""

    def __init__(self, rules: list[Rule], language: str = DEFAULT_LANGUAGE) -> None:
        self._rules = list(rules)
        self._by_id = {rule.id: rule for rule in self._rules}
        self.language = normalize_language(language)

    @classmethod
    def load(
        cls, path: str | Path | None = None, language: str = DEFAULT_LANGUAGE
    ) -> "RuleCatalog":
        return cls(load_rules(path, language), language)

    def t(self, key: str, **params: object) -> str:
        """Return the finding message ``key`` in the catalogue language."""
        return translate(self.language, key, **params)

    @property
    def all(self) -> list[Rule]:
        return list(self._rules)

    @property
    def enabled(self) -> list[Rule]:
        return [rule for rule in self._rules if rule.enabled]

    def get(self, rule_id: str) -> Rule | None:
        return self._by_id.get(rule_id)

    def is_enabled(self, rule_id: str) -> bool:
        rule = self.get(rule_id)
        return bool(rule and rule.enabled)

    def for_scope(self, scope: str, enabled_only: bool = True) -> list[Rule]:
        return [
            rule
            for rule in self._rules
            if rule.scope == scope and (not enabled_only or rule.enabled)
        ]
