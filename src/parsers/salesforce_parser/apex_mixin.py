"""Parsing of Apex classes and triggers with static metrics."""

from __future__ import annotations

import re
from pathlib import Path

from src.core.models import ApexArtifact
from src.core.utils import child_text, parse_xml
from src.parsers.salesforce_parser.apex_helpers import (
    _DML_IN_LOOP_RE,
    _SOQL_IN_LOOP_RE,
    _detect_pattern_in_loop,
)
from src.parsers.salesforce_parser.base import _ParserState


class _ApexMixin(_ParserState):
    """Parse the ``classes/`` and ``triggers/`` folders into artefacts."""

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
            artifact.is_interface = kind == "class" and bool(re.search(r"(?i)\binterface\b", body))
            _soql_loop_line = _detect_pattern_in_loop(body, _SOQL_IN_LOOP_RE)
            artifact.query_in_loop = _soql_loop_line is not None
            artifact.query_in_loop_line = _soql_loop_line
            _dml_loop_line = _detect_pattern_in_loop(body, _DML_IN_LOOP_RE)
            artifact.dml_in_loop = _dml_loop_line is not None
            artifact.dml_in_loop_line = _dml_loop_line
            artifacts.append(artifact)

        return artifacts
