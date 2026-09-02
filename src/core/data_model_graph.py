"""Graphe du modele de donnees : liens, hubs et grappes d'objets lies.

Le diagramme du modele de donnees ne se lit que decoupe. Ce module isole les
grappes d'objets reellement lies entre eux, en mettant a part les hubs
(``Account``, ``User``...) qui, laisses dans le graphe, agregeraient tout le
modele en une seule grappe illisible. Un hub est ensuite rattache a chaque
grappe qui le reference : un objet peut donc apparaitre sur plusieurs onglets.

Les relations viennent du retrieve, comme le reste de la documentation : ce
sont les champs porteurs d'un ``referenceTo``. Les relations standard que le
retrieve ne ramene pas (``Contact.AccountId`` et consorts) sont donc absentes.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Collection, Sequence

from src.core.models import ObjectInfo

#: Nom du fichier de diagramme ecrit dans ``diagrams/``.
DATA_MODEL_DIAGRAM_NAME = "data_model.drawio"

#: A partir de ce nombre de relations, un objet est traite comme un hub :
#: il est sorti du graphe pour laisser apparaitre les domaines, puis rattache
#: a chacun d'eux. Cale sur une org reelle, ou le seuil 6 fait ressortir
#: Account, User, Opportunity et les grosses entites de facturation.
DEFAULT_MIN_HUB_DEGREE = 6

#: Au-dela, un onglet cesse d'etre lisible : le seuil sert a decider s'il faut
#: extraire les hubs plutot qu'a tronquer une grappe.
READABLE_TAB_SIZE = 12

#: Nombre d'objets hors hubs en dessous duquel une grappe ne merite pas son
#: onglet : un objet seul accroche a Account ne raconte rien que la vue
#: d'ensemble ne dise deja. Ces grappes sont regroupees dans l'onglet
#: des satellites.
MIN_DOMAIN_SIZE = 2

OVERVIEW = "overview"
DOMAIN = "domain"
SATELLITE = "satellite"
UNRELATED = "unrelated"


@dataclass(frozen=True, slots=True)
class DataModelLink:
    """Une relation portee par un champ, d'un objet vers un autre."""

    source: str
    target: str
    field_name: str
    relationship_type: str

    @property
    def is_master_detail(self) -> bool:
        return "master" in (self.relationship_type or "").lower()


@dataclass(slots=True)
class DataModelCluster:
    """Un onglet du diagramme : des objets, leurs liens et leur regroupement.

    ``hub_names`` distingue les objets rattaches parce qu'ils sont references
    depuis la grappe, des objets qui en constituent le coeur : le writer leur
    donne un style distinctif pour signaler qu'ils sont dupliques ailleurs.
    """

    kind: str
    label: str
    object_names: list[str] = field(default_factory=list)
    hub_names: set[str] = field(default_factory=set)
    links: list[DataModelLink] = field(default_factory=list)
    #: Objets regroupes par Squad Responsable, dans l'ordre d'affichage.
    zones: list[tuple[str, list[str]]] = field(default_factory=list)


def normalise_squad(raw: str) -> str:
    """Squad Responsable exploitable comme nom de zone.

    La saisie est libre dans l'ecran Data Dictionary : une meme squad s'y
    ecrit avec des casses differentes, parfois suivie d'un ``(?)`` marquant un
    doute, parfois listant plusieurs squads separees par ``|``. Seule la
    premiere est retenue, la casse etant unifiee par le regroupement.
    """

    text = (raw or "").split("|")[0].strip()
    if text.endswith("(?)"):
        text = text[:-3].strip()
    return text


def build_links(objects: Sequence[ObjectInfo]) -> list[DataModelLink]:
    """Relations internes au perimetre, dedoublonnees et ordonnees.

    Un lien n'est retenu que si sa cible fait partie du perimetre : sinon le
    diagramme ferait apparaitre des objets que l'utilisateur n'a pas
    selectionnes. Les auto-references sont ecartees, une boite pointant sur
    elle-meme n'apportant rien au diagramme.
    """

    in_scope = {obj.api_name for obj in objects if obj.api_name}
    links: list[DataModelLink] = []
    seen: set[tuple[str, str, str]] = set()
    for obj in objects:
        if not obj.api_name:
            continue
        for relationship in obj.relationships:
            for target in relationship.targets:
                if target not in in_scope or target == obj.api_name:
                    continue
                key = (obj.api_name, target, relationship.field_name)
                if key in seen:
                    continue
                seen.add(key)
                links.append(
                    DataModelLink(
                        source=obj.api_name,
                        target=target,
                        field_name=relationship.field_name,
                        relationship_type=relationship.relationship_type,
                    )
                )
    return sorted(links, key=lambda link: (link.source.lower(), link.target.lower(), link.field_name.lower()))


def link_degrees(links: Collection[DataModelLink]) -> Counter[str]:
    """Nombre de relations touchant chaque objet, sens confondus."""

    degrees: Counter[str] = Counter()
    for link in links:
        degrees[link.source] += 1
        degrees[link.target] += 1
    return degrees


def _adjacency(links: Collection[DataModelLink]) -> dict[str, set[str]]:
    adjacency: dict[str, set[str]] = defaultdict(set)
    for link in links:
        adjacency[link.source].add(link.target)
        adjacency[link.target].add(link.source)
    return adjacency


def _components(names: Collection[str], adjacency: dict[str, set[str]], excluded: set[str]) -> list[list[str]]:
    """Composantes connexes, les objets exclus coupant les chemins."""

    seen = set(excluded)
    components: list[list[str]] = []
    for name in sorted(names, key=str.lower):
        if name in seen:
            continue
        seen.add(name)
        stack = [name]
        group: list[str] = []
        while stack:
            current = stack.pop()
            group.append(current)
            for neighbour in adjacency.get(current, ()):
                if neighbour not in seen:
                    seen.add(neighbour)
                    stack.append(neighbour)
        components.append(sorted(group, key=str.lower))
    return sorted(components, key=lambda group: (-len(group), group[0].lower()))


def _zones(
    names: Sequence[str],
    squads: dict[str, str],
    hubs: set[str],
) -> list[tuple[str, list[str]]]:
    """Objets regroupes par Squad, les hubs mis a part car partages.

    Les squads sont regroupees sans tenir compte de la casse, et la zone
    porte l'orthographe la plus utilisee dans le perimetre.
    """

    shared = [name for name in names if name in hubs]
    spellings: dict[str, Counter[str]] = defaultdict(Counter)
    members: dict[str, list[str]] = defaultdict(list)
    for name in names:
        if name in hubs:
            continue
        squad = normalise_squad(squads.get(name, ""))
        key = squad.casefold()
        spellings[key][squad] += 1
        members[key].append(name)

    zones = [
        (spellings[key].most_common(1)[0][0] or "Squad non renseignee", sorted(group, key=str.lower))
        for key, group in members.items()
    ]
    zones.sort(key=lambda zone: (zone[0] == "Squad non renseignee", -len(zone[1]), zone[0].lower()))
    if shared:
        zones.append(("Objets partages", sorted(shared, key=str.lower)))
    return zones


def _links_within(links: Collection[DataModelLink], names: Collection[str]) -> list[DataModelLink]:
    scope = set(names)
    return [link for link in links if link.source in scope and link.target in scope]


def _domain_label(index: int, names: Sequence[str], squads: dict[str, str], hubs: set[str]) -> str:
    """Nom d'onglet : la squad dominante, numerotee pour rester unique."""

    counts: Counter[str] = Counter()
    for name in names:
        if name in hubs:
            continue
        squad = normalise_squad(squads.get(name, ""))
        if squad:
            counts[squad] += 1
    if not counts:
        return f"Domaine {index}"
    return f"Domaine {index} - {counts.most_common(1)[0][0]}"


def _attached_cluster(
    kind: str,
    label: str,
    core: Sequence[str],
    hubs: set[str],
    adjacency: dict[str, set[str]],
    links: Collection[DataModelLink],
    squads: dict[str, str],
) -> DataModelCluster:
    """Grappe complete : son coeur, plus les hubs qu'elle reference.

    Les hubs sont rattaches et non fusionnes : ils reapparaissent sur chaque
    onglet qui les reference, ce qui evite de les laisser tout agreger.
    """

    attached = sorted(
        {hub for name in core for hub in adjacency.get(name, ()) if hub in hubs},
        key=str.lower,
    )
    names = sorted(set(core) | set(attached), key=str.lower)
    return DataModelCluster(
        kind=kind,
        label=label,
        object_names=names,
        hub_names=set(attached),
        links=_links_within(links, names),
        zones=_zones(names, squads, set(attached)),
    )


def plan_data_model_tabs(
    objects: Sequence[ObjectInfo],
    min_hub_degree: int = DEFAULT_MIN_HUB_DEGREE,
) -> list[DataModelCluster]:
    """Repartit le perimetre en onglets, du plus global au plus isole.

    La vue d'ensemble reprend tous les objets relies, comme un MDD global.
    Chaque domaine est une grappe d'objets lies entre eux hors hubs, les hubs
    qu'elle reference lui etant rattaches. Les objets qui n'ont qu'un hub pour
    voisin ne meritent pas un onglet chacun et sont regroupes en satellites.
    Les objets sans aucune relation finissent dans un dernier onglet.
    """

    named = [obj for obj in objects if obj.api_name]
    squads = {obj.api_name: obj.dewey_squad for obj in named}
    links = build_links(named)
    adjacency = _adjacency(links)
    connected = {name for name in adjacency if adjacency[name]}
    unrelated = sorted(
        (obj.api_name for obj in named if obj.api_name not in connected),
        key=str.lower,
    )

    clusters: list[DataModelCluster] = []
    if connected:
        overview = sorted(connected, key=str.lower)
        clusters.append(
            DataModelCluster(
                kind=OVERVIEW,
                label="Vue d'ensemble",
                object_names=overview,
                links=_links_within(links, overview),
                zones=_zones(overview, squads, set()),
            )
        )

        degrees = link_degrees(links)
        hubs = {name for name, degree in degrees.items() if degree >= min_hub_degree}
        # Sortir les hubs n'a de sens que si cela fait apparaitre plusieurs
        # domaines : sur un petit modele, mieux vaut garder la grappe entiere.
        components = _components(connected, adjacency, hubs)
        if len(components) < 2 and len(connected) <= READABLE_TAB_SIZE:
            hubs = set()
            components = _components(connected, adjacency, hubs)

        domains = [group for group in components if len(group) >= MIN_DOMAIN_SIZE]
        satellites = sorted(
            (group[0] for group in components if len(group) < MIN_DOMAIN_SIZE),
            key=str.lower,
        )

        for index, domain in enumerate(domains, start=1):
            cluster = _attached_cluster(
                kind=DOMAIN,
                label=_domain_label(index, domain, squads, hubs),
                core=domain,
                hubs=hubs,
                adjacency=adjacency,
                links=links,
                squads=squads,
            )
            if cluster.object_names != overview:
                clusters.append(cluster)

        if satellites:
            cluster = _attached_cluster(
                kind=SATELLITE,
                label="Objets satellites",
                core=satellites,
                hubs=hubs,
                adjacency=adjacency,
                links=links,
                squads=squads,
            )
            if cluster.object_names != overview:
                clusters.append(cluster)

    if unrelated:
        clusters.append(
            DataModelCluster(
                kind=UNRELATED,
                label="Objets sans relation",
                object_names=unrelated,
                zones=_zones(unrelated, squads, set()),
            )
        )
    return clusters
