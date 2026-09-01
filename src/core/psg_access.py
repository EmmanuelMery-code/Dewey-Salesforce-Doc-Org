"""Droits effectifs accordes par les Permission Set Groups, objet par objet.

Un Permission Set Group n'accorde aucun droit par lui-meme : ses permissions
sont l'union de celles de ses permission sets membres. Ce calcul est partage
par le sous-onglet "PSet Group Summary", sa page de detail et le classeur
Excel equivalent, qui doivent afficher exactement les memes chiffres.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.core.models import MetadataSnapshot, PermissionSetGroupInfo

#: Nom du classeur Excel equivalent au sous-onglet, ecrit dans ``excel/``.
SUMMARY_WORKBOOK_NAME = "psg_group_summary.xlsx"

CRUD_FLAGS: tuple[tuple[str, str, str], ...] = (
    ("C", "Create (Creation)", "allow_create"),
    ("R", "Read (Lecture)", "allow_read"),
    ("U", "Update (Modification)", "allow_edit"),
    ("D", "Delete (Suppression)", "allow_delete"),
)

SHARING_FLAGS: tuple[tuple[str, str, str], ...] = (
    ("VA", "View All / Voir tout", "view_all_records"),
    ("MA", "Modify All / Modifier tout", "modify_all_records"),
    ("VAF", "View All Fields / Voir tous les champs", "view_all_fields"),
)

ALL_FLAGS = CRUD_FLAGS + SHARING_FLAGS

STATUS_HELP: tuple[tuple[str, str], ...] = (
    (
        "Updated",
        "Le groupe est calcule et a jour : les droits agreges ci-dessous sont "
        "bien ceux appliques aux utilisateurs.",
    ),
    (
        "Outdated",
        "Un permission set membre a change depuis le dernier calcul : les droits "
        "reellement appliques peuvent differer de cette synthese.",
    ),
    (
        "Updating",
        "Recalcul en cours par la plateforme : etat transitoire, a reverifier "
        "apres la fin du recalcul.",
    ),
    (
        "Failed",
        "Le recalcul a echoue : le groupe n'accorde pas les droits attendus, "
        "a corriger dans l'org.",
    ),
)


#: Raisons pour lesquelles un objet est couvert, ou non, par un groupe.
COVERAGE_REASONS: tuple[tuple[str, str], ...] = (
    (
        "Droit accorde par un groupe",
        "L'objet est couvert des qu'un permission set membre declare un droit sur "
        "lui, meme un simple Read.",
    ),
    (
        "Acces accorde par le profil",
        "Les droits portes par les profils ne passent pas par les groupes : l'objet "
        "reste sans aucun droit dans cette synthese bien qu'il soit accessible. La "
        "vue profils + permission sets est le sous-onglet CRUD.",
    ),
    (
        "Acces accorde par un permission set hors groupe",
        "Seuls les permission sets membres d'un groupe sont agreges ici.",
    ),
    (
        "Permission set membre non analyse",
        "Le permission set est reference par le groupe mais absent de la source : "
        "les droits qu'il accorde manquent.",
    ),
    (
        "Objet non retrieve",
        "Un objet peut etre couvert par les permissions sans etre present dans "
        "objects/ : son modele de partage (OWD) reste alors inconnu.",
    ),
    (
        "Objet sans permission explicite",
        "Objets systeme ou objets dont l'acces est derive du parent "
        "(ControlledByParent), pour lesquels Salesforce n'ecrit pas de bloc "
        "objectPermissions.",
    ),
)


@dataclass(slots=True)
class GroupObjectAccess:
    """Droits effectifs d'un groupe sur un objet, avec leur origine."""

    object_name: str
    granted_by: dict[str, list[str]] = field(default_factory=dict)

    def sources(self, attribute: str) -> list[str]:
        return self.granted_by.get(attribute, [])

    def granted(self, attribute: str) -> bool:
        return bool(self.granted_by.get(attribute))

    @property
    def contributors(self) -> list[str]:
        names: list[str] = []
        for sources in self.granted_by.values():
            for name in sources:
                if name not in names:
                    names.append(name)
        return sorted(names, key=str.lower)


@dataclass(slots=True)
class GroupAccess:
    """Droits effectifs d'un Permission Set Group, objet par objet."""

    group: PermissionSetGroupInfo
    objects: dict[str, GroupObjectAccess] = field(default_factory=dict)
    unresolved_permission_sets: list[str] = field(default_factory=list)

    @property
    def resolved_permission_sets(self) -> list[str]:
        unresolved = set(self.unresolved_permission_sets)
        return [name for name in self.group.permission_sets if name not in unresolved]


def build_group_access(snapshot: MetadataSnapshot) -> list[GroupAccess]:
    """Agrege les object permissions des permission sets de chaque groupe."""

    permission_sets = {item.name: item for item in snapshot.permission_sets}
    accesses: list[GroupAccess] = []
    for group in snapshot.permission_set_groups:
        access = GroupAccess(group=group)
        for member_name in group.permission_sets:
            member = permission_sets.get(member_name)
            if member is None:
                if member_name and member_name not in access.unresolved_permission_sets:
                    access.unresolved_permission_sets.append(member_name)
                continue
            for permission in member.object_permissions:
                if not permission.object_name:
                    continue
                entry = access.objects.setdefault(
                    permission.object_name,
                    GroupObjectAccess(object_name=permission.object_name),
                )
                for _code, _label, attribute in ALL_FLAGS:
                    if getattr(permission, attribute, False):
                        sources = entry.granted_by.setdefault(attribute, [])
                        if member.name not in sources:
                            sources.append(member.name)
        accesses.append(access)
    return accesses


def covered_object_names(accesses: list[GroupAccess]) -> set[str]:
    """Objets sur lesquels au moins un groupe accorde un droit."""

    return {name for access in accesses for name in access.objects}


def listed_object_names(
    snapshot: MetadataSnapshot,
    accesses: list[GroupAccess],
) -> list[str]:
    """Objets affiches dans la synthese : tous ceux de l'org, couverts ou non.

    Les objets couverts sont ajoutes meme absents de ``objects/`` : un
    permission set peut porter des droits sur un objet standard que le
    retrieve n'a pas ramene.
    """

    org_objects = {item.api_name for item in snapshot.objects if item.api_name}
    return sorted(covered_object_names(accesses) | org_objects, key=str.lower)


def sharing_context(snapshot: MetadataSnapshot) -> tuple[dict[str, str], dict[str, int]]:
    """Modele de partage (OWD) et nombre de regles de partage, par objet."""

    owd = {item.api_name: item.sharing_model for item in snapshot.objects if item.api_name}
    rule_counts: dict[str, int] = {}
    for rule in snapshot.sharing_rules:
        if rule.object_name:
            rule_counts[rule.object_name] = rule_counts.get(rule.object_name, 0) + 1
    return owd, rule_counts
