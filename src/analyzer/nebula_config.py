"""Reglages de detection Nebula Logger (format de message et tags)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping


DEFAULT_NEBULA_LOG_FORMAT = (
    r"^\[[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*\]\s+\S"
)

DEFAULT_NEBULA_TAGS: tuple[str, ...] = (
    "Sales",
    "Service",
    "Billing",
    "Batch",
    "Trigger",
    "Flow",
    "LWC",
    "API",
    "Integration-*",
)

_SENSITIVE_RE = re.compile(
    r"\b(?:password|passwd|pwd|secret|token|api[_-]?key|authorization|bearer|"
    r"iban|credit[_-]?card|card[_-]?number|cvv|ssn|nir|social[_-]?security)\b",
    re.IGNORECASE,
)

_FRENCH_RE = re.compile(
    r"\b(?:erreur|echec|échec|debut|début|traitement|introuvable|impossible|"
    r"utilisateur|enregistrement|échoué|echoue|demarre|démarré|aucun|aucune)\b",
    re.IGNORECASE,
)

_TRAILING_PUNCT_RE = re.compile(r"[.!?]$")


@dataclass(frozen=True)
class NebulaConfig:
    """Format, tags et interrupteur global transmis a l'analyseur."""

    enabled: bool
    log_format: str
    tags: tuple[str, ...]

    @classmethod
    def disabled(cls) -> "NebulaConfig":
        return cls.from_values(False, None, None)

    @classmethod
    def from_values(
        cls,
        enabled: bool,
        log_format: str | None,
        tags: list[str] | tuple[str, ...] | None,
    ) -> "NebulaConfig":
        return cls(
            enabled=bool(enabled),
            log_format=valid_log_format(log_format),
            tags=tuple(normalize_tags(tags)),
        )

    def compiled_format(self) -> re.Pattern[str]:
        try:
            return re.compile(self.log_format)
        except re.error:
            return re.compile(DEFAULT_NEBULA_LOG_FORMAT)


def valid_log_format(value: str | None) -> str:
    """Return ``value`` when it is a compilable regex, otherwise the default."""

    if not isinstance(value, str):
        return DEFAULT_NEBULA_LOG_FORMAT
    text = value.strip()
    if not text:
        return DEFAULT_NEBULA_LOG_FORMAT
    try:
        re.compile(text)
    except re.error:
        return DEFAULT_NEBULA_LOG_FORMAT
    return text


def normalize_tags(values: list[str] | tuple[str, ...] | None) -> list[str]:
    """Return a de-duplicated tag list, falling back to the standard list."""

    if not isinstance(values, (list, tuple)):
        return list(DEFAULT_NEBULA_TAGS)
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not isinstance(value, str):
            continue
        text = value.strip()
        if not text:
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(text)
    if not cleaned:
        return list(DEFAULT_NEBULA_TAGS)
    return cleaned


def parse_nebula_enabled(settings: Mapping[str, Any]) -> bool:
    return bool(settings.get("nebula_rules_enabled", False))


def parse_nebula_format(settings: Mapping[str, Any]) -> str:
    raw = settings.get("nebula_log_format")
    if not isinstance(raw, str):
        return DEFAULT_NEBULA_LOG_FORMAT
    return valid_log_format(raw)


def parse_nebula_tags(settings: Mapping[str, Any]) -> list[str]:
    raw = settings.get("nebula_tags")
    if not isinstance(raw, list):
        return list(DEFAULT_NEBULA_TAGS)
    return normalize_tags(raw)


def tag_allowed(value: str, tags: tuple[str, ...]) -> bool:
    """True when ``value`` matches an exact tag or a ``prefix*`` pattern."""

    text = value.strip()
    if not text:
        return False
    folded = text.casefold()
    for pattern in tags:
        token = pattern.strip()
        if not token:
            continue
        if token.endswith("*"):
            prefix = token[:-1].casefold()
            if prefix and folded.startswith(prefix):
                return True
            continue
        if folded == token.casefold():
            return True
    return False


def message_matches(message: str, pattern: re.Pattern[str]) -> bool:
    return pattern.search(message) is not None


def sensitive_terms(text: str) -> list[str]:
    return sorted({match.group(0) for match in _SENSITIVE_RE.finditer(text)})


def language_issues(message: str) -> list[str]:
    """Return the French words or the trailing punctuation found in ``message``."""

    issues = [match.group(0) for match in _FRENCH_RE.finditer(message)]
    if _TRAILING_PUNCT_RE.search(message.strip()):
        issues.append(message.strip()[-1])
    return issues
