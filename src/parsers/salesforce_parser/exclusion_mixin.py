"""Exclusion-rule loading and matching."""

from __future__ import annotations

import fnmatch
import json
import re
from pathlib import Path

from src.parsers.salesforce_parser.base import _ParserState


class _ExclusionMixin(_ParserState):
    """Load the exclusion config and decide whether an artefact is excluded."""

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
