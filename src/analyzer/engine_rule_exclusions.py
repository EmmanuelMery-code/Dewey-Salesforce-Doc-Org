"""Mixin providing JSON-based per-component rule exclusion loading and applicability
checks, used by ``AnalyzerEngine`` in ``src.analyzer.engine``.
"""
from __future__ import annotations

import json

from src.analyzer.models import Rule


class RuleExclusionMixin:
    """Loads/applies per-metadata rule exclusions and API-version filters.

    Expects the including class to set ``self.exclusion_path`` (``Path | None``) and
    ``self.rule_exclusions`` (``dict[str, set[str]]``) before calling
    :meth:`_load_rule_exclusions`.
    """

    def _load_rule_exclusions(self) -> None:
        """Charge les exclusions de règles spécifiques par métadonnée depuis le JSON.

        Structure JSON attendue :
        {
          "rule_exclusions": [
            {"type": "...", "metadata_name": "...", "rule_id": "...", "commentaire": "..."},
            ...
          ]
        }
        """
        if not self.exclusion_path or not self.exclusion_path.exists():
            return

        try:
            data = {}
            # Try different encodings to be robust
            for encoding in ("utf-8", "utf-16", "latin-1"):
                try:
                    with open(self.exclusion_path, "r", encoding=encoding) as f:
                        data = json.load(f)
                    break # Success
                except (UnicodeDecodeError, json.JSONDecodeError):
                    continue
            
            if not data:
                return

            exclusions = data.get("rule_exclusions", [])
            # Fallback for old format or different naming
            if not exclusions and "Exclusions regles" in data:
                raw_list = data["Exclusions regles"]
                for item in raw_list:
                    if isinstance(item, list) and len(item) >= 3:
                        metadata_name = str(item[1]).strip()
                        rule_id = str(item[2]).strip()
                        if metadata_name and rule_id:
                            self.rule_exclusions.setdefault(rule_id, set()).add(metadata_name.lower())
                return

            for entry in exclusions:
                if not isinstance(entry, dict):
                    continue
                
                metadata_name = str(entry.get("metadata_name", "")).strip()
                rule_id = str(entry.get("rule_id", "")).strip()
                
                if metadata_name and rule_id:
                    self.rule_exclusions.setdefault(rule_id, set()).add(metadata_name.lower())
                    
        except Exception:
            # On ignore silencieusement les erreurs de lecture JSON pour ne pas bloquer l'analyse
            pass

    def _is_rule_applicable(self, rule: Rule, metadata_name: str, api_version: str | None = None) -> bool:
        """Vérifie si une règle doit être appliquée à une métadonnée donnée."""
        # 1. Vérification de l'exclusion spécifique
        if rule.id in self.rule_exclusions:
            if metadata_name.lower() in self.rule_exclusions[rule.id]:
                return False
        
        # 2. Vérification de la version d'API
        if api_version:
            try:
                version = float(api_version)
                if rule.min_api_version is not None and version < rule.min_api_version:
                    return False
                if rule.max_api_version is not None and version > rule.max_api_version:
                    return False
            except (ValueError, TypeError):
                pass
                
        return True
