"""Tests: diagramme draw.io du modele de donnees.

Contrats testes :
  build_links(objects) -> list[DataModelLink]
    ne retient que les relations internes au perimetre selectionne, sans
    auto-reference ni doublon.

  normalise_squad(raw) -> str
    absorbe la saisie libre de l'ecran Data Dictionnary (casse, ``(?)``,
    squads multiples separees par ``|``).

  plan_data_model_tabs(objects) -> list[DataModelCluster]
    repartit le perimetre en onglets lisibles : vue d'ensemble, un onglet par
    domaine d'objets lies, les satellites regroupes, puis les objets sans
    relation. Les hubs sont rattaches a chaque domaine qui les reference, donc
    un objet peut apparaitre sur plusieurs onglets.

  DrawioDiagramWriter().write_data_model_diagram(...) -> Path | None
    ecrit un ``.drawio`` valide, un ``<diagram>`` par onglet, les hubs portant
    un style distinctif et les Master-Detail se distinguant des Lookup.

  render_diagram_exports(...) -> str
    liste les diagrammes generes et les onglets qu'ils contiennent.
"""

from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree

from src.core.data_model_graph import (
    DOMAIN,
    OVERVIEW,
    SATELLITE,
    UNRELATED,
    build_links,
    normalise_squad,
    plan_data_model_tabs,
)
from src.core.models import ObjectInfo, RelationshipInfo
from src.reporting.drawio_writer import HUB_STROKE, DrawioDiagramWriter
from src.reporting.html.renderers.index_panels import render_diagram_exports

SALES_SQUAD = "Parcours de vente"


def _obj(
    api_name: str,
    *,
    custom: bool = True,
    squad: str = "",
    relations: tuple[tuple[str, str, str], ...] = (),
) -> ObjectInfo:
    return ObjectInfo(
        api_name=api_name,
        custom=custom,
        dewey_squad=squad,
        relationships=[
            RelationshipInfo(field_name=field, relationship_type=kind, targets=[target])
            for field, kind, target in relations
        ],
    )


def _perimeter() -> list[ObjectInfo]:
    """Perimetre de test : un hub, un domaine, des satellites, un orphelin.

    ``Account`` totalise six relations, ce qui en fait un hub : il est sorti du
    graphe pour laisser apparaitre le domaine des devis, puis rattache aux
    onglets qui le referencent.
    """

    satellites = [
        _obj(f"Sat{index}__c", relations=(("Account__c", "Lookup", "Account"),))
        for index in range(1, 6)
    ]
    return [
        # L'auto-reference et la cible hors perimetre doivent etre ignorees.
        _obj(
            "Account",
            custom=False,
            squad="Fiche Client",
            relations=(
                ("Parent__c", "Lookup", "Account"),
                ("Missing__c", "Lookup", "Absent__c"),
            ),
        ),
        _obj("Quote__c", squad=SALES_SQUAD, relations=(("Account__c", "Lookup", "Account"),)),
        _obj(
            "QuoteLine__c",
            squad="parcours de Vente",
            relations=(
                ("Quote__c", "MasterDetail", "Quote__c"),
                ("Product__c", "Lookup", "Product__c"),
            ),
        ),
        _obj("Product__c", squad=SALES_SQUAD),
        _obj("Orphan__c", squad="Support (?)"),
        *satellites,
    ]


def _tabs() -> dict[str, object]:
    return {cluster.label: cluster for cluster in plan_data_model_tabs(_perimeter())}


class TestSquadNormalisation:
    def test_blank_squad_stays_blank(self) -> None:
        assert normalise_squad("") == ""
        assert normalise_squad("   ") == ""

    def test_uncertainty_marker_is_dropped(self) -> None:
        assert normalise_squad("Support (?)") == "Support"

    def test_only_the_first_of_several_squads_is_kept(self) -> None:
        assert normalise_squad("Fiche Client | Parcours de vente") == "Fiche Client"


class TestLinkExtraction:
    def test_only_relations_inside_the_perimeter_are_kept(self) -> None:
        targets = {link.target for link in build_links(_perimeter())}

        assert "Absent__c" not in targets

    def test_self_references_are_dropped(self) -> None:
        assert not [
            link for link in build_links(_perimeter()) if link.source == link.target
        ]

    def test_a_link_carries_its_field_and_relationship_type(self) -> None:
        links = {(link.source, link.target): link for link in build_links(_perimeter())}
        master_detail = links[("QuoteLine__c", "Quote__c")]

        assert master_detail.field_name == "Quote__c"
        assert master_detail.is_master_detail is True
        assert links[("Quote__c", "Account")].is_master_detail is False


class TestTabPlanning:
    def test_the_perimeter_is_split_into_readable_tabs(self) -> None:
        clusters = plan_data_model_tabs(_perimeter())

        assert [cluster.kind for cluster in clusters] == [
            OVERVIEW,
            DOMAIN,
            SATELLITE,
            UNRELATED,
        ]

    def test_the_overview_holds_every_object_carrying_a_relation(self) -> None:
        overview = _tabs()["Vue d'ensemble"]

        assert overview.object_names == [
            "Account",
            "Product__c",
            "Quote__c",
            "QuoteLine__c",
            "Sat1__c",
            "Sat2__c",
            "Sat3__c",
            "Sat4__c",
            "Sat5__c",
        ]
        assert "Orphan__c" not in overview.object_names

    def test_a_domain_is_named_after_its_dominant_squad(self) -> None:
        assert f"Domaine 1 - {SALES_SQUAD}" in _tabs()

    def test_a_hub_is_attached_to_every_tab_that_references_it(self) -> None:
        tabs = _tabs()
        domain = tabs[f"Domaine 1 - {SALES_SQUAD}"]
        satellites = tabs["Objets satellites"]

        assert domain.hub_names == {"Account"}
        assert satellites.hub_names == {"Account"}
        assert "Account" in domain.object_names
        assert "Account" in satellites.object_names

    def test_objects_alone_behind_a_hub_are_grouped_as_satellites(self) -> None:
        satellites = _tabs()["Objets satellites"]

        assert satellites.object_names == [
            "Account",
            "Sat1__c",
            "Sat2__c",
            "Sat3__c",
            "Sat4__c",
            "Sat5__c",
        ]

    def test_objects_without_any_relation_get_their_own_tab(self) -> None:
        unrelated = _tabs()["Objets sans relation"]

        assert unrelated.object_names == ["Orphan__c"]
        assert unrelated.links == []

    def test_squad_spellings_are_merged_into_one_zone(self) -> None:
        zones = dict(_tabs()[f"Domaine 1 - {SALES_SQUAD}"].zones)

        assert zones[SALES_SQUAD] == ["Product__c", "Quote__c", "QuoteLine__c"]
        assert "parcours de Vente" not in zones

    def test_shared_objects_sit_in_their_own_zone(self) -> None:
        zones = dict(_tabs()[f"Domaine 1 - {SALES_SQUAD}"].zones)

        assert zones["Objets partages"] == ["Account"]

    def test_an_empty_perimeter_plans_no_tab(self) -> None:
        assert plan_data_model_tabs([]) == []


class TestDrawioWriter:
    def _write(self, tmp_path: Path, objects: list[ObjectInfo] | None = None) -> Path:
        path = DrawioDiagramWriter().write_data_model_diagram(
            _perimeter() if objects is None else objects,
            tmp_path / "diagrams" / "data_model.drawio",
        )
        assert path is not None
        return path

    @staticmethod
    def _diagrams(path: Path) -> dict[str, ElementTree.Element]:
        root = ElementTree.parse(path).getroot()
        return {diagram.get("name") or "": diagram for diagram in root.iter("diagram")}

    def test_one_diagram_tab_per_planned_cluster(self, tmp_path: Path) -> None:
        names = list(self._diagrams(self._write(tmp_path)))

        assert names == [
            "Vue d'ensemble",
            f"Domaine 1 - {SALES_SQUAD}",
            "Objets satellites",
            "Objets sans relation",
        ]

    def test_the_file_is_a_valid_mxfile(self, tmp_path: Path) -> None:
        content = self._write(tmp_path).read_text(encoding="utf-8")
        root = ElementTree.fromstring(content)

        assert root.tag == "mxfile"
        # Chaque onglet porte le calque racine attendu par draw.io.
        for diagram in root.iter("diagram"):
            ids = [cell.get("id") for cell in diagram.iter("mxCell")]
            assert ids[:2] == ["0", "1"]

    def test_cell_ids_are_unique_within_each_tab(self, tmp_path: Path) -> None:
        for diagram in self._diagrams(self._write(tmp_path)).values():
            ids = [cell.get("id") for cell in diagram.iter("mxCell")]

            assert len(ids) == len(set(ids))

    def test_a_shared_object_is_drawn_on_several_tabs(self, tmp_path: Path) -> None:
        diagrams = self._diagrams(self._write(tmp_path))
        drawn = [
            name
            for name, diagram in diagrams.items()
            if any(
                "<b>Account</b>" in (cell.get("value") or "")
                for cell in diagram.iter("mxCell")
            )
        ]

        assert len(drawn) == 3

    def test_a_shared_object_carries_a_distinctive_style(self, tmp_path: Path) -> None:
        domain = self._diagrams(self._write(tmp_path))[f"Domaine 1 - {SALES_SQUAD}"]
        boxes = {
            (cell.get("value") or "").split("</b>")[0].removeprefix("<b>"): cell
            for cell in domain.iter("mxCell")
            if cell.get("vertex")
        }

        assert HUB_STROKE in boxes["Account"].get("style", "")
        assert "strokeWidth=3" in boxes["Account"].get("style", "")
        assert HUB_STROKE not in boxes["Quote__c"].get("style", "")

    def test_master_detail_and_lookup_links_are_told_apart(self, tmp_path: Path) -> None:
        domain = self._diagrams(self._write(tmp_path))[f"Domaine 1 - {SALES_SQUAD}"]
        edges = {
            cell.get("value"): cell.get("style", "")
            for cell in domain.iter("mxCell")
            if cell.get("edge")
        }

        assert "dashed=0" in edges["Quote__c"]
        assert "dashed=1" in edges["Account__c"]

    def test_an_edge_is_labelled_with_the_field_carrying_the_relation(
        self, tmp_path: Path
    ) -> None:
        overview = self._diagrams(self._write(tmp_path))["Vue d'ensemble"]
        labels = {
            cell.get("value") for cell in overview.iter("mxCell") if cell.get("edge")
        }

        assert "Product__c" in labels

    def test_the_unrelated_tab_holds_no_link(self, tmp_path: Path) -> None:
        unrelated = self._diagrams(self._write(tmp_path))["Objets sans relation"]

        assert not [cell for cell in unrelated.iter("mxCell") if cell.get("edge")]

    def test_no_file_is_written_for_an_empty_perimeter(self, tmp_path: Path) -> None:
        path = DrawioDiagramWriter().write_data_model_diagram(
            [], tmp_path / "diagrams" / "data_model.drawio"
        )

        assert path is None
        assert not (tmp_path / "diagrams" / "data_model.drawio").exists()


class TestDiagramListing:
    def test_generated_diagrams_are_listed_with_their_tabs(self, tmp_path: Path) -> None:
        DrawioDiagramWriter().write_data_model_diagram(
            _perimeter(), tmp_path / "diagrams" / "data_model.drawio"
        )

        listing = render_diagram_exports(tmp_path, tmp_path / "html" / "index.html")

        assert "<a href='../diagrams/data_model.drawio'>data_model.drawio</a>" in listing
        assert f"Domaine 1 - {SALES_SQUAD}" in listing
        assert "Objets sans relation" in listing

    def test_the_listing_explains_why_it_is_empty(self, tmp_path: Path) -> None:
        listing = render_diagram_exports(tmp_path, tmp_path / "html" / "index.html")

        assert "Aucun diagramme genere" in listing
        assert "Data Dictionnary" in listing
