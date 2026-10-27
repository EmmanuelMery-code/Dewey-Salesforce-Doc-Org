"""Compte les écrans visibles et les rattache à une squad.

Deux lectures, les mêmes que le classeur produit à la main :

* permission sets dont la description cite une squad ou un périmètre ;
* champ « Squad responsable » du data dictionary (pas « Piloté par »,
  qui est le système source).

Un écran est une page Lightning d'enregistrement, un screen flow actif,
un OmniScript actif qui contient une étape, une FlexCard active, ou un
LWC exposé sur une cible visible par un utilisateur.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from html import unescape
from pathlib import Path
import xml.etree.ElementTree as ET

from src.core.models.security import SecurityArtifact

LIGHTNING = "Lightning Page"
SCREEN_FLOW = "Screen Flow"
OMNI = "OmniScript"
FLEXCARD = "FlexCard"
LWC = "LWC"
TYPE_ORDER = (LIGHTNING, SCREEN_FLOW, OMNI, FLEXCARD, LWC)

SHARED = "Objets partagés"
DICT_MULTI = "Plusieurs squads"
DICT_EMPTY = "Non renseigné"

_PREFERRED = (
    "Parcours de vente",
    "Vision Client",
    "Engagement Client",
    "Support (Engagement Client)",
    "Support",
)
_ALIASES = {
    "parcours de vente": "Parcours de vente",
    "vision client": "Vision Client",
    "engagement client": "Engagement Client",
}
_SQUAD_MENTION = re.compile(
    r"(?i)(?:squad|p[eé]rim[eè]tre)\s+(.+?)(?=\s+aux\b|\s+pour\b|\.|$)"
)
_NOISE = {"User", "RecordType", "Group", "Profile", "Organization"}
_CHILDREN = {
    "QuoteLineItem": "Quote",
    "QuoteLineItemGroupClass": "Quote",
    "OpportunityLineItem": "Opportunity",
    "OpportunityContactRole": "Opportunity",
    "ApplicationFormProduct": "ApplicationForm",
}
_NOT_AN_OBJECT = {"json", "turbo extract"}
_USER_TARGETS = {
    "lightning__RecordPage",
    "lightning__AppPage",
    "lightning__HomePage",
    "lightning__FlowScreen",
    "lightning__Tab",
    "lightning__UrlAddressable",
    "lightningCommunity__Page",
    "lightningCommunity__Default",
}
_BUNDLE_RE = re.compile(r'"bundle"\s*:\s*"([^"]+)"')
_IP_KEY_RE = re.compile(r'"(?:integrationProcedureKey|ipMethod)"\s*:\s*"([^"]+)"')
_SCHEMA_RE = re.compile(r"@salesforce/schema/([A-Za-z][A-Za-z0-9_]*)\.")
_CUSTOM_RE = re.compile(r"\b([A-Za-z][A-Za-z0-9_]*__(?:c|mdt|e))\b")
_DR_VERSION_RE = re.compile(r"^(.*)_(\d+(?:\.\d+)?)$")
_SOQL_FROM_RE = re.compile(r"(?i)\bFROM\s+([A-Za-z][A-Za-z0-9_]*)")
_CARD_FOLDERS = ("omniUiCard", "omniUiCards", "vlocityCards")
_CARD_PATTERNS = ("*.ouc-meta.xml", "*.card-meta.xml")

ExcludedFn = Callable[[str, str], bool]


@dataclass(frozen=True)
class ScreenItem:
    kind: str
    name: str
    label: str
    objects: tuple[str, ...]
    perm_bucket: str
    dict_bucket: str
    piloted_by: str
    consumers: str
    counted: bool
    reason: str


@dataclass(frozen=True)
class ObjectRow:
    name: str
    perm_squads: str
    shared: str
    squad: str
    consumers: str
    piloted_by: str


@dataclass
class ScreenCountResult:
    items: list[ScreenItem] = field(default_factory=list)
    squad_names: list[str] = field(default_factory=list)
    multi_label: str = DICT_MULTI
    objects: list[ObjectRow] = field(default_factory=list)


def canonical_squad(raw: str) -> str:
    text = " ".join(raw.split())
    return _ALIASES.get(text.casefold(), text)


def order_squads(names: Iterable[str]) -> list[str]:
    present = set(names)
    preferred = [name for name in _PREFERRED if name in present]
    rest = sorted(name for name in present if name not in preferred)
    return preferred + rest


def split_squads(raw: str) -> list[str]:
    found: list[str] = []
    for part in raw.split("|"):
        name = canonical_squad(part)
        if not name or name.casefold() == "tous" or name in found:
            continue
        found.append(name)
    return found


def squad_from_description(description: str) -> str:
    match = _SQUAD_MENTION.search(description or "")
    if match is None:
        return ""
    return canonical_squad(match.group(1))


def grants_from_permission_sets(
    artifacts: Sequence[SecurityArtifact],
) -> dict[str, set[str]]:
    """Objets accordés par les permission sets qui nomment une squad."""
    grants: dict[str, set[str]] = {}
    for artifact in artifacts:
        squad = squad_from_description(artifact.description)
        if not squad:
            continue
        names = {
            permission.object_name
            for permission in artifact.object_permissions
            if permission.object_name and not _is_platform(permission.object_name)
        }
        grants.setdefault(squad, set()).update(names)
    return grants


def collect_screens(
    package_roots: Sequence[Path],
    *,
    squad_grants: Mapping[str, set[str]],
    known_objects: set[str] | None = None,
    object_squad: Mapping[str, str] | None = None,
    object_piloted_by: Mapping[str, str] | None = None,
    object_squad_consumer: Mapping[str, str] | None = None,
    is_excluded: ExcludedFn | None = None,
) -> ScreenCountResult:
    """Parcourt les racines de package et classe chaque écran."""
    grants = {canonical_squad(name): set(objs) for name, objs in squad_grants.items()}
    squads = {name: squad for name, squad in object_squad.items()} if object_squad else {}
    piloted = dict(object_piloted_by or {})
    consumers = dict(object_squad_consumer or {})
    known = set(known_objects or ())
    skip = is_excluded or (lambda _category, _name: False)
    squad_names = order_squads(grants)
    multi = (
        "PV et VC"
        if set(squad_names) == {"Parcours de vente", "Vision Client"}
        else DICT_MULTI
    )

    reader = _MetadataReader(package_roots, known, skip)
    raw_items = reader.read()
    items: list[ScreenItem] = []
    seen_objects: set[str] = set()
    for raw in raw_items:
        seen_objects.update(raw.objects)
        if not raw.counted:
            items.append(
                ScreenItem(
                    raw.kind, raw.name, raw.label, raw.objects,
                    "", "", "", "", False, raw.reason,
                )
            )
            continue
        perm = _classify_permission(raw.objects, grants, multi)
        dictionary = _classify_dictionary(raw.objects, squads, consumers)
        items.append(
            ScreenItem(
                raw.kind,
                raw.name,
                raw.label,
                raw.objects,
                perm,
                dictionary,
                _join_values(piloted.get(name, "") for name in raw.objects),
                _join_values(consumers.get(name, "") for name in raw.objects),
                True,
                "",
            )
        )
    items.sort(key=lambda item: (TYPE_ORDER.index(item.kind) if item.kind in TYPE_ORDER else 9, item.name))
    return ScreenCountResult(
        items=items,
        squad_names=squad_names,
        multi_label=multi,
        objects=_object_rows(grants, squads, piloted, consumers, seen_objects),
    )


@dataclass(frozen=True)
class _RawScreen:
    kind: str
    name: str
    label: str
    objects: tuple[str, ...]
    counted: bool
    reason: str


class _MetadataReader:
    def __init__(self, roots: Sequence[Path], known: set[str], skip: ExcludedFn) -> None:
        self.roots = list(roots)
        self.known = known
        self.skip = skip

    def read(self) -> list[_RawScreen]:
        data_raptors = self._data_raptors()
        procedures = self._procedures(data_raptors)
        omnis = self._omniscripts()
        self._attach_omni_objects(omnis, data_raptors, procedures)
        hosts = self._flexipage_hosts()
        items = self._flexipages()
        items.extend(self._flows())
        items.extend(self._chosen_omnis(omnis))
        items.extend(self._flexcards(procedures))
        items.extend(self._lwcs(hosts))
        return items

    def _flexipages(self) -> list[_RawScreen]:
        rows: list[_RawScreen] = []
        for path in self._files("flexipages", "*.flexipage-meta.xml"):
            name = path.name.replace(".flexipage-meta.xml", "")
            if self.skip("flexipage", name):
                continue
            root = _parse(path)
            if root is None:
                continue
            kind = _direct(root, "type")
            label = _direct(root, "masterLabel") or name
            sobject = _direct(root, "sobjectType")
            objects = (sobject,) if sobject else ()
            if kind == "RecordPage":
                rows.append(_RawScreen(LIGHTNING, name, label, objects, True, ""))
            else:
                motif = (
                    "barre d'utilitaires"
                    if kind == "UtilityBar"
                    else "page Lightning autre qu'une page d'enregistrement"
                )
                rows.append(_RawScreen(LIGHTNING, name, label, objects, False, motif))
        return rows

    def _flows(self) -> list[_RawScreen]:
        rows: list[_RawScreen] = []
        for path in self._files("flows", "*.flow-meta.xml"):
            name = path.name.replace(".flow-meta.xml", "")
            if self.skip("flow", name):
                continue
            root = _parse(path)
            if root is None:
                continue
            if _direct(root, "processType") != "Flow":
                continue
            screens = sum(1 for node in root.iter() if _local(node.tag) == "screens")
            if screens == 0:
                continue
            label = _direct(root, "label") or name
            objects = tuple(sorted({text for text in _all_texts(root, "object") if _valid_object(text)}))
            active = _direct(root, "status") == "Active"
            rows.append(
                _RawScreen(
                    SCREEN_FLOW, name, label, objects, active,
                    "" if active else "flow inactif",
                )
            )
        return rows

    def _chosen_omnis(self, versions: list[_OmniVersion]) -> list[_RawScreen]:
        grouped: dict[tuple[str, str, str], list[_OmniVersion]] = {}
        for version in versions:
            grouped.setdefault(version.key, []).append(version)
        rows: list[_RawScreen] = []
        for group in grouped.values():
            chosen = _representative(group)
            for version in group:
                if version.identity == chosen.identity and chosen.active and chosen.has_step:
                    rows.append(
                        _RawScreen(OMNI, chosen.display_name, chosen.label, tuple(sorted(chosen.objects)), True, "")
                    )
                    continue
                if version.identity == chosen.identity and chosen.active and not chosen.has_step:
                    motif = "OmniScript sans étape"
                elif not version.active:
                    motif = "OmniScript inactif ou version antérieure"
                else:
                    motif = "version antérieure"
                rows.append(
                    _RawScreen(OMNI, version.display_name, version.label, tuple(sorted(version.objects)), False, motif)
                )
        return rows

    def _flexcards(self, procedures: dict[str, set[str]]) -> list[_RawScreen]:
        versions: list[_CardVersion] = []
        for folder in _CARD_FOLDERS:
            for pattern in _CARD_PATTERNS:
                for path in self._files(folder, pattern):
                    card = _read_flexcard(path, self.skip, procedures, self.known)
                    if card is not None:
                        versions.append(card)
        grouped: dict[str, list[_CardVersion]] = {}
        for card in versions:
            grouped.setdefault(card.name, []).append(card)
        rows: list[_RawScreen] = []
        for group in grouped.values():
            active = [card for card in group if card.active]
            chosen = max(active or group, key=lambda card: card.version)
            for card in group:
                selected = card.identity == chosen.identity
                if selected and chosen.active and not chosen.child:
                    rows.append(_RawScreen(FLEXCARD, card.display_name, card.label, card.objects, True, ""))
                    continue
                if selected and chosen.active and chosen.child:
                    motif = "FlexCard enfant, affichée dans une carte parente"
                elif not card.active:
                    motif = "FlexCard inactive ou version antérieure"
                else:
                    motif = "version antérieure"
                rows.append(_RawScreen(FLEXCARD, card.display_name, card.label, card.objects, False, motif))
        return rows

    def _lwcs(self, hosts: dict[str, set[str]]) -> list[_RawScreen]:
        rows: list[_RawScreen] = []
        seen: set[str] = set()
        for path in self._files("lwc", "*/*.js-meta.xml"):
            name = path.parent.name
            if name in seen or self.skip("lwc", name):
                continue
            seen.add(name)
            root = _parse(path)
            if root is None:
                continue
            exposed = _direct(root, "isExposed").lower() == "true"
            label = _direct(root, "masterLabel") or name
            targets = set(_all_texts(root, "target"))
            action_types = _record_action_types(root)
            objects = _lwc_objects(path.parent, root, hosts.get(name, set()), self.known)
            if not exposed:
                rows.append(_RawScreen(LWC, name, label, objects, False, "composant non exposé"))
                continue
            if not _user_facing(targets, action_types):
                rows.append(
                    _RawScreen(LWC, name, label, objects, False, "composant sans cible visible")
                )
                continue
            rows.append(_RawScreen(LWC, name, label, objects, True, ""))
        return rows

    def _flexipage_hosts(self) -> dict[str, set[str]]:
        names = {path.parent.name for path in self._files("lwc", "*/*.js-meta.xml")}
        hosts: dict[str, set[str]] = {}
        for path in self._files("flexipages", "*.flexipage-meta.xml"):
            root = _parse(path)
            if root is None or _direct(root, "type") != "RecordPage":
                continue
            sobject = _direct(root, "sobjectType")
            if not sobject:
                continue
            for node in root.iter():
                if _local(node.tag) != "componentName" or not node.text:
                    continue
                lwc = _lwc_name(node.text, names)
                if lwc:
                    hosts.setdefault(lwc, set()).add(sobject)
        return hosts

    def _data_raptors(self) -> dict[str, set[str]]:
        best: dict[str, tuple[float, set[str]]] = {}
        for path in self._files("omniDataTransforms", "*.rpt-meta.xml"):
            stem = path.name.replace(".rpt-meta.xml", "")
            match = _DR_VERSION_RE.match(stem)
            base, version = (match.group(1), float(match.group(2))) if match else (stem, 0.0)
            if self.skip("omni", stem) or self.skip("omni", base):
                continue
            root = _parse(path)
            if root is None:
                continue
            objects = {
                text
                for tag in ("inputObjectName", "outputObjectName")
                for text in _all_texts(root, tag)
                if _valid_object(text)
            }
            current = best.get(base)
            if current is None or version >= current[0]:
                best[base] = (version, objects)
        return {name: objects for name, (_version, objects) in best.items()}

    def _procedures(self, data_raptors: dict[str, set[str]]) -> dict[str, set[str]]:
        raw: list[_Procedure] = []
        for folder, pattern in (
            ("omniIntegrationProcedures", "*.oip-meta.xml"),
            ("omniIntegrationProcedures", "*.ip-meta.xml"),
            ("omniProcesses", "*.omniProcess-meta.xml"),
            ("omniScripts", "*.os-meta.xml"),
        ):
            for path in self._files(folder, pattern):
                root = _parse(path)
                if root is None or not _is_procedure(root):
                    continue
                stem = path.name.split(".oip-")[0].split(".ip-")[0].split(".omniProcess-")[0]
                if self.skip("omni", stem):
                    continue
                raw.append(_procedure_from(root, stem))
        grouped: dict[str, list[_Procedure]] = {}
        for item in raw:
            grouped.setdefault(item.key, []).append(item)
        chosen = {key: max(group, key=lambda item: item.version) for key, group in grouped.items()}
        cache: dict[str, set[str]] = {}

        def resolve(key: str, seen: set[str]) -> set[str]:
            if key in cache:
                return cache[key]
            if key in seen or key not in chosen:
                return set()
            item = chosen[key]
            found: set[str] = set()
            for bundle in item.bundles:
                found |= data_raptors.get(re.sub(r"_\d+$", "", bundle), data_raptors.get(bundle, set()))
            for child in item.calls:
                found |= resolve(child, seen | {key})
            cache[key] = found
            return found

        return {key: resolve(key, set()) for key in chosen}

    def _omniscripts(self) -> list[_OmniVersion]:
        versions: list[_OmniVersion] = []
        patterns = (
            ("omniScripts", "*.os-meta.xml"),
            ("omniProcesses", "*.omniProcess-meta.xml"),
        )
        for folder, pattern in patterns:
            for path in self._files(folder, pattern):
                root = _parse(path)
                if root is None or _is_procedure(root):
                    continue
                if _local(root.tag) not in {"OmniScript", "OmniProcess"} and _direct(root, "omniProcessType") not in {"", "OmniScript"}:
                    continue
                os_type = _direct(root, "type")
                subtype = _direct(root, "subType")
                language = _direct(root, "language")
                if not os_type or not subtype:
                    continue
                stem = path.name.replace(".os-meta.xml", "").replace(".omniProcess-meta.xml", "")
                if self.skip("omni", stem):
                    continue
                version = _version(root)
                text = unescape("\n".join(_all_texts(root, "propertySetConfig")))
                bundles = {name for name in _BUNDLE_RE.findall(text) if name and name != "null"}
                calls = {name for name in _IP_KEY_RE.findall(text) if name and name != "null"}
                embeds = set()
                for key in _all_texts(root, "embeddedOmniScriptKey"):
                    parts = [part.strip() for part in key.split("|")]
                    if len(parts) >= 3:
                        embeds.add((parts[0], parts[1], parts[2]))
                number = int(version) if version == int(version) else version
                versions.append(
                    _OmniVersion(
                        key=(os_type, subtype, language),
                        version=version,
                        active=_direct(root, "isActive").lower() == "true",
                        has_step=any(
                            (node.text or "").strip() == "Step"
                            for node in root.iter()
                            if _local(node.tag) == "type"
                        ),
                        label=_direct(root, "name") or stem,
                        display_name=f"{os_type}_{subtype}_{number}",
                        bundles=bundles,
                        calls=calls,
                        embeds=embeds,
                    )
                )
        return versions

    def _attach_omni_objects(
        self,
        versions: list[_OmniVersion],
        data_raptors: dict[str, set[str]],
        procedures: dict[str, set[str]],
    ) -> None:
        grouped: dict[tuple[str, str, str], list[_OmniVersion]] = {}
        for version in versions:
            grouped.setdefault(version.key, []).append(version)
        chosen = {key: _representative(group) for key, group in grouped.items()}
        cache: dict[tuple[str, str, str], set[str]] = {}

        def resolve(key: tuple[str, str, str], seen: set[tuple[str, str, str]]) -> set[str]:
            if key in cache:
                return cache[key]
            if key in seen or key not in chosen:
                return set()
            item = chosen[key]
            found: set[str] = set()
            for bundle in item.bundles:
                base = re.sub(r"_\d+$", "", bundle)
                found |= data_raptors.get(base, data_raptors.get(bundle, set()))
            for call in item.calls:
                found |= procedures.get(call, set())
            for embed in item.embeds:
                found |= resolve(embed, seen | {key})
            cache[key] = found
            return found

        for key in chosen:
            objects = resolve(key, set())
            for version in grouped[key]:
                if version.identity == chosen[key].identity:
                    version.objects = objects

    def _files(self, folder: str, pattern: str) -> list[Path]:
        found: list[Path] = []
        for root in self.roots:
            base = root / folder
            if base.exists():
                found.extend(base.glob(pattern))
        return sorted(found)


@dataclass(frozen=True)
class _CardVersion:
    name: str
    version: float
    active: bool
    child: bool
    label: str
    display_name: str
    objects: tuple[str, ...]

    @property
    def identity(self) -> tuple[str, float]:
        return (self.name, self.version)


def _read_flexcard(
    path: Path,
    skip: ExcludedFn,
    procedures: Mapping[str, set[str]],
    known: set[str],
) -> _CardVersion | None:
    stem = path.name.replace(".ouc-meta.xml", "").replace(".card-meta.xml", "")
    if skip("omni", stem):
        return None
    root = _parse(path)
    if root is None or _local(root.tag) != "OmniUiCard":
        return None
    name = _direct(root, "name") or stem
    version = _version(root)
    number = int(version) if version == int(version) else version
    text = unescape(
        "\n".join(_all_texts(root, "dataSourceConfig") + _all_texts(root, "propertySetConfig"))
    )
    objects: set[str] = {item for item in _SOQL_FROM_RE.findall(text) if _valid_object(item)}
    for token in _CUSTOM_RE.findall(text):
        if not known or token in known:
            objects.add(token)
    for key in _IP_KEY_RE.findall(text):
        if key and key != "null":
            objects.update(procedures.get(key, set()))
    return _CardVersion(
        name=name,
        version=version,
        active=_direct(root, "isActive").lower() == "true",
        child=_direct(root, "omniUiCardType").casefold() == "child",
        label=_direct(root, "description") or _direct(root, "masterLabel") or name,
        display_name=f"{name}_{number}",
        objects=tuple(sorted(objects)),
    )


@dataclass
class _OmniVersion:
    key: tuple[str, str, str]
    version: float
    active: bool
    has_step: bool
    label: str
    display_name: str
    bundles: set[str]
    calls: set[str]
    embeds: set[tuple[str, str, str]]
    objects: set[str] = field(default_factory=set)

    @property
    def identity(self) -> tuple[tuple[str, str, str], float]:
        return (self.key, self.version)


@dataclass(frozen=True)
class _Procedure:
    key: str
    version: float
    bundles: frozenset[str]
    calls: frozenset[str]


def _procedure_from(root: ET.Element, stem: str) -> _Procedure:
    os_type = _direct(root, "type")
    subtype = _direct(root, "subType")
    key = f"{os_type}_{subtype}" if os_type and subtype else re.sub(r"_[A-Za-z]+_\d+$", "", stem)
    text = unescape("\n".join(_all_texts(root, "propertySetConfig")))
    return _Procedure(
        key=key,
        version=_version(root),
        bundles=frozenset(name for name in _BUNDLE_RE.findall(text) if name and name != "null"),
        calls=frozenset(name for name in _IP_KEY_RE.findall(text) if name and name != "null"),
    )


def _representative(group: Sequence[_OmniVersion]) -> _OmniVersion:
    active = [item for item in group if item.active]
    pool = active or list(group)
    return max(pool, key=lambda item: item.version)


def _classify_permission(
    objects: Sequence[str], grants: Mapping[str, set[str]], multi: str
) -> str:
    expanded: list[str] = []
    for name in objects:
        if _is_platform(name):
            continue
        if not _squads_of(name, grants) and name in _CHILDREN and _squads_of(_CHILDREN[name], grants):
            expanded.append(_CHILDREN[name])
        else:
            expanded.append(name)
    business = [name for name in expanded if name not in _NOISE]
    use = business or expanded
    exclusive = [name for name in use if len(_squads_of(name, grants)) == 1]
    shared = [name for name in use if len(_squads_of(name, grants)) >= 2]
    deciding = exclusive or shared
    found: list[str] = []
    for name in deciding:
        for squad in order_squads(_squads_of(name, grants)):
            if squad not in found:
                found.append(squad)
    if not found:
        return ""
    if not exclusive:
        return SHARED
    if len(found) == 1:
        return found[0]
    return multi


def _classify_dictionary(
    objects: Sequence[str],
    squads: Mapping[str, str],
    consumers: Mapping[str, str],
) -> str:
    specific: list[str] = []
    socle: list[str] = []
    for name in objects:
        names = split_squads(squads.get(name, ""))
        if not names:
            continue
        target = socle if consumers.get(name, "").strip() else specific
        for squad in names:
            if squad not in target:
                target.append(squad)
    deciding = specific or socle
    if not deciding:
        return DICT_EMPTY
    if len(deciding) > 1:
        return DICT_MULTI
    return deciding[0]


def _object_rows(
    grants: Mapping[str, set[str]],
    squads: Mapping[str, str],
    piloted: Mapping[str, str],
    consumers: Mapping[str, str],
    seen: set[str],
) -> list[ObjectRow]:
    names = set(seen) | set(squads) | set(piloted) | set(consumers)
    for objects in grants.values():
        names.update(objects)
    rows: list[ObjectRow] = []
    for name in sorted(names):
        owning = order_squads(squad for squad, objects in grants.items() if name in objects)
        rows.append(
            ObjectRow(
                name=name,
                perm_squads=" | ".join(owning),
                shared="oui" if len(owning) >= 2 else "",
                squad=canonical_squad(squads.get(name, "")) if squads.get(name, "") else "",
                consumers=consumers.get(name, ""),
                piloted_by=piloted.get(name, ""),
            )
        )
    return rows


def _squads_of(name: str, grants: Mapping[str, set[str]]) -> set[str]:
    return {squad for squad, objects in grants.items() if name in objects}


def _is_platform(name: str) -> bool:
    return name.startswith("Omni") or name.startswith("SF_Async")


def _valid_object(name: str) -> bool:
    text = name.strip()
    return bool(text) and " " not in text and text.casefold() not in _NOT_AN_OBJECT


def _user_facing(targets: set[str], action_types: set[str]) -> bool:
    if targets & _USER_TARGETS:
        return True
    return "lightning__RecordAction" in targets and "ScreenAction" in action_types


def _record_action_types(root: ET.Element) -> set[str]:
    found: set[str] = set()
    for node in root.iter():
        if _local(node.tag) != "targetConfig":
            continue
        declared = node.attrib.get("targets", "")
        if "lightning__RecordAction" not in declared:
            continue
        found.update(_all_texts(node, "actionType"))
    return found


def _lwc_objects(folder: Path, root: ET.Element, hosts: set[str], known: set[str]) -> tuple[str, ...]:
    found: set[str] = set(hosts)
    found.update(text for text in _all_texts(root, "object") if _valid_object(text))
    source = []
    for path in list(folder.glob("*.js")) + list(folder.glob("*.html")):
        try:
            source.append(path.read_text(encoding="utf-8"))
        except OSError:
            continue
    text = "\n".join(source)
    found.update(_SCHEMA_RE.findall(text))
    for token in _CUSTOM_RE.findall(text):
        if not known or token in known:
            found.add(token)
    return tuple(sorted(found))


def _lwc_name(raw: str, names: set[str]) -> str:
    token = raw.strip()
    if ":" in token:
        token = token.rsplit(":", 1)[-1]
    if token.startswith("c__"):
        token = token[3:]
    return token if token in names else ""


def _is_procedure(root: ET.Element) -> bool:
    if _local(root.tag) == "OmniIntegrationProcedure":
        return True
    if _direct(root, "isIntegrationProcedure").lower() == "true":
        return True
    return _direct(root, "omniProcessType") == "Integration Procedure"


def _join_values(values: Iterable[str]) -> str:
    found: list[str] = []
    for value in values:
        for part in value.split("|"):
            text = " ".join(part.split())
            if text and text not in found:
                found.append(text)
    return " | ".join(found)


def _version(root: ET.Element) -> float:
    try:
        return float(_direct(root, "versionNumber") or "0")
    except ValueError:
        return 0.0


def _parse(path: Path) -> ET.Element | None:
    try:
        return ET.parse(path).getroot()
    except (ET.ParseError, OSError):
        return None


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _direct(root: ET.Element, name: str) -> str:
    for child in root:
        if _local(child.tag) == name and child.text and child.text.strip():
            return child.text.strip()
    return ""


def _all_texts(root: ET.Element, name: str) -> list[str]:
    return [
        node.text.strip()
        for node in root.iter()
        if _local(node.tag) == name and node.text and node.text.strip()
    ]
