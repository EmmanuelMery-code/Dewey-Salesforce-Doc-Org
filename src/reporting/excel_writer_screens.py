"""Classeur « écrans par type et par squad ».

Deux tableaux : les squads lues dans les permission sets, puis les squads
responsables saisies dans le data dictionary.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from openpyxl import Workbook
from openpyxl.chart import BarChart, Reference
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from src.reporting.screen_count_collect import (
    DICT_EMPTY,
    DICT_MULTI,
    SHARED,
    TYPE_ORDER,
    ScreenCountResult,
    ScreenItem,
    order_squads,
)

LogCallback = Callable[[str], None]

_HEADER_FILL = PatternFill(fill_type="solid", fgColor="1F4E79")
_HEADER_FONT = Font(name="Calibri", bold=True, color="FFFFFF")
_TITLE_FONT = Font(name="Calibri", bold=True, size=16, color="1F4E79")
_NOTE_FONT = Font(name="Calibri", italic=True, size=10, color="595959")
_TOTAL_FONT = Font(name="Calibri", bold=True)
_TOTAL_FILL = PatternFill(fill_type="solid", fgColor="D6DCE4")
_WRAP = Alignment(wrap_text=True, vertical="center")


def write_screen_count_workbook(
    result: ScreenCountResult,
    output_path: str | Path,
    log_callback: LogCallback | None = None,
) -> Path:
    """Écrit le classeur et retourne son chemin."""
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    counted = [item for item in result.items if item.counted]
    workbook = Workbook()

    summary = workbook.active
    summary.title = "Synthese"
    perm_columns = [*result.squad_names, SHARED, result.multi_label]
    _write_matrix(
        summary,
        counted,
        perm_columns,
        "perm_bucket",
        "Écrans par type et par squad",
        "Squads déduites des objets accordés par les permission sets "
        "dont la description cite une squad ou un périmètre.",
        _perm_notes(result),
    )

    dictionary = workbook.create_sheet("Synthese dictionnaire")
    dict_columns = [
        *order_squads(
            {
                item.dict_bucket
                for item in counted
                if item.dict_bucket not in {DICT_MULTI, DICT_EMPTY}
            }
        ),
        DICT_MULTI,
        DICT_EMPTY,
    ]
    _write_matrix(
        dictionary,
        counted,
        dict_columns,
        "dict_bucket",
        "Écrans par type et par squad responsable",
        "Squad responsable saisie dans Créer un data dictionnary. "
        "Piloté par reste le système source et n'est pas une squad.",
        _dict_notes(),
    )

    _write_detail(
        workbook.create_sheet("Detail dictionnaire"),
        counted,
        (
            "Type d'écran", "Nom", "Label", "Objets",
            "Squad responsable", "Piloté par", "Squad consommatrice",
        ),
        lambda item: (
            item.kind, item.name, item.label, ", ".join(item.objects),
            item.dict_bucket, item.piloted_by, item.consumers,
        ),
    )
    in_scope = [item for item in counted if item.perm_bucket]
    _write_detail(
        workbook.create_sheet("Detail"),
        in_scope,
        ("Type d'écran", "Nom", "Label", "Objets", "Squad"),
        lambda item: (
            item.kind, item.name, item.label, ", ".join(item.objects), item.perm_bucket,
        ),
    )
    outside = [
        item for item in result.items if not item.counted or not item.perm_bucket
    ]
    _write_detail(
        workbook.create_sheet("Hors perimetre"),
        outside,
        ("Type d'écran", "Nom", "Label", "Objets", "Motif"),
        lambda item: (
            item.kind,
            item.name,
            item.label,
            ", ".join(item.objects),
            item.reason or "aucun objet rattaché à une squad",
        ),
    )
    _write_objects(workbook.create_sheet("Objets"), result)
    _write_method(workbook.create_sheet("Methode"), result)

    workbook.save(output)
    log = log_callback or (lambda _message: None)
    log(
        "Comptage des écrans : "
        + ", ".join(f"{kind} {_count(counted, kind)}" for kind in TYPE_ORDER)
        + f" — {output}"
    )
    return output


def _write_matrix(
    worksheet,
    items: list[ScreenItem],
    columns: list[str],
    bucket: str,
    title: str,
    subtitle: str,
    notes: list[str],
) -> None:
    last_col = len(columns) + 2
    worksheet.merge_cells(start_row=1, start_column=1, end_row=1, end_column=last_col)
    worksheet["A1"] = title
    worksheet["A1"].font = _TITLE_FONT
    worksheet.merge_cells(start_row=2, start_column=1, end_row=2, end_column=last_col)
    worksheet["A2"] = subtitle
    worksheet["A2"].font = _NOTE_FONT
    worksheet["A2"].alignment = _WRAP
    worksheet.row_dimensions[2].height = 32

    headers = ["Type d'écran", *columns, "Total"]
    for index, header in enumerate(headers, start=1):
        cell = worksheet.cell(row=4, column=index, value=header)
        cell.fill = _HEADER_FILL
        cell.font = _HEADER_FONT
        cell.alignment = Alignment(horizontal="center", wrap_text=True, vertical="center")

    counts = {kind: {column: 0 for column in columns} for kind in TYPE_ORDER}
    for item in items:
        value = getattr(item, bucket)
        if value in counts.get(item.kind, {}):
            counts[item.kind][value] += 1

    for offset, kind in enumerate(TYPE_ORDER):
        row = 5 + offset
        worksheet.cell(row=row, column=1, value=kind)
        row_total = 0
        for index, column in enumerate(columns, start=2):
            value = counts[kind][column]
            row_total += value
            worksheet.cell(row=row, column=index, value=value)
        worksheet.cell(row=row, column=last_col, value=row_total)

    total_row = 5 + len(TYPE_ORDER)
    worksheet.cell(row=total_row, column=1, value="Total").font = _TOTAL_FONT
    for index in range(2, last_col + 1):
        total = sum(worksheet.cell(row=row, column=index).value or 0 for row in range(5, total_row))
        cell = worksheet.cell(row=total_row, column=index, value=total)
        cell.font = _TOTAL_FONT
        cell.fill = _TOTAL_FILL
    for index in range(1, last_col + 1):
        worksheet.cell(row=total_row, column=index).fill = _TOTAL_FILL
        worksheet.cell(row=total_row, column=index).font = _TOTAL_FONT

    note_row = total_row + 2
    for note in notes:
        worksheet.merge_cells(start_row=note_row, start_column=1, end_row=note_row, end_column=last_col)
        cell = worksheet.cell(row=note_row, column=1, value=note)
        cell.font = _NOTE_FONT
        cell.alignment = _WRAP
        worksheet.row_dimensions[note_row].height = 48 if len(note) > 220 else 32
        note_row += 1

    _chart(worksheet, len(columns), note_row + 1)
    worksheet.auto_filter.ref = f"A4:{get_column_letter(last_col)}{total_row}"
    worksheet.freeze_panes = "A5"
    worksheet.page_setup.orientation = "landscape"
    worksheet.page_setup.fitToPage = True
    worksheet.page_setup.fitToWidth = 1
    worksheet.page_setup.fitToHeight = 1
    worksheet.print_title_rows = "1:4"
    worksheet.page_setup.paperSize = worksheet.PAPERSIZE_A4
    widths = [22, *([18] * len(columns)), 12]
    for index, width in enumerate(widths, start=1):
        worksheet.column_dimensions[get_column_letter(index)].width = width
    worksheet.row_dimensions[1].height = 24
    worksheet.row_dimensions[4].height = 30
    worksheet.sheet_properties.pageSetUpPr.fitToPage = True


def _chart(worksheet, column_count: int, anchor_row: int) -> None:
    if column_count <= 0:
        return
    chart = BarChart()
    chart.type = "col"
    chart.grouping = "clustered"
    chart.title = "Écrans par type"
    chart.y_axis.title = "Nombre d'écrans"
    chart.style = 10
    data = Reference(worksheet, min_col=2, max_col=1 + column_count, min_row=4, max_row=4 + len(TYPE_ORDER))
    categories = Reference(worksheet, min_col=1, min_row=5, max_row=4 + len(TYPE_ORDER))
    chart.add_data(data, from_rows=False, titles_from_data=True)
    chart.set_categories(categories)
    chart.shape = 4
    chart.y_axis.majorGridlines = None
    chart.legend.position = "b"
    worksheet.add_chart(chart, f"A{anchor_row}")


def _write_detail(worksheet, items: list[ScreenItem], headers: tuple[str, ...], values) -> None:
    for index, header in enumerate(headers, start=1):
        cell = worksheet.cell(row=1, column=index, value=header)
        cell.fill = _HEADER_FILL
        cell.font = _HEADER_FONT
    for row, item in enumerate(items, start=2):
        for index, value in enumerate(values(item), start=1):
            worksheet.cell(row=row, column=index, value=value)
    last_row = max(1, 1 + len(items))
    worksheet.auto_filter.ref = f"A1:{get_column_letter(len(headers))}{last_row}"
    worksheet.freeze_panes = "A2"
    worksheet.auto_filter.ref = f"A1:{get_column_letter(len(headers))}{last_row}"
    worksheet.page_setup.orientation = "landscape"
    worksheet.page_setup.fitToPage = True
    worksheet.page_setup.fitToWidth = 1
    worksheet.page_setup.fitToHeight = 0
    worksheet.print_title_rows = "1:1"
    worksheet.page_setup.paperSize = worksheet.PAPERSIZE_A4
    for index, header in enumerate(headers, start=1):
        width = 28 if header in {"Objets", "Motif", "Piloté par", "Squad consommatrice"} else 24
        worksheet.column_dimensions[get_column_letter(index)].width = width
    if items:
        worksheet.auto_filter.ref = f"A1:{get_column_letter(len(headers))}{last_row}"


def _write_objects(worksheet, result: ScreenCountResult) -> None:
    headers = (
        "Objet",
        "Squads des permission sets",
        "Partagé",
        "Squad responsable",
        "Squad consommatrice",
        "Piloté par",
    )
    for index, header in enumerate(headers, start=1):
        cell = worksheet.cell(row=1, column=index, value=header)
        cell.fill = _HEADER_FILL
        cell.font = _HEADER_FONT
    for row, item in enumerate(result.objects, start=2):
        values = (
            item.name, item.perm_squads, item.shared,
            item.squad, item.consumers, item.piloted_by,
        )
        for index, value in enumerate(values, start=1):
            worksheet.cell(row=row, column=index, value=value)
    last_row = max(1, 1 + len(result.objects))
    worksheet.auto_filter.ref = f"A1:F{last_row}"
    worksheet.freeze_panes = "A2"
    worksheet.page_setup.orientation = "landscape"
    worksheet.page_setup.fitToPage = True
    worksheet.page_setup.fitToWidth = 1
    worksheet.page_setup.fitToHeight = 0
    worksheet.print_title_rows = "1:1"
    worksheet.page_setup.paperSize = worksheet.PAPERSIZE_A4
    for index, width in enumerate((32, 36, 12, 28, 36, 24), start=1):
        worksheet.column_dimensions[get_column_letter(index)].width = width


def _write_method(worksheet, result: ScreenCountResult) -> None:
    worksheet["A1"] = "Méthode de comptage"
    worksheet["A1"].font = _TITLE_FONT
    worksheet.column_dimensions["A"].width = 120
    lines = [
        "Un écran est une page Lightning d'enregistrement (Record Page), un screen flow actif, un OmniScript actif qui produit au moins une étape, une FlexCard active, ou un LWC exposé sur une cible visible.",
        "Les barres d'utilitaires, les pages d'application ou d'accueil, les flows inactifs, les OmniScripts sans étape, les FlexCards enfants ou inactives et les composants non exposés ne sont pas comptés. Ils sont listés dans Hors perimetre.",
        "Pour une même FlexCard, seule la version active la plus élevée est comptée. Une carte enfant reste hors comptage : elle s'affiche à l'intérieur d'une carte parente. Ses objets viennent des requêtes SOQL (FROM), des objets personnalisés cités et des procédures d'intégration appelées.",
        "Pour un même OmniScript (type, sous-type, langue), seule la version active la plus élevée est comptée. Les objets viennent des DataRaptors (bundle), des procédures d'intégration appelées, et des OmniScripts embarqués.",
        "Un LWC compte s'il est exposé sur une page Lightning, un écran de flow, une action d'écran, un onglet, une URL ou une page de site. Une action d'enregistrement sans ScreenAction et un composant limité à la barre d'utilitaires restent hors comptage.",
        "Les objets d'un LWC sont ceux déclarés dans sa cible, importés via @salesforce/schema, les jetons personnalisés (__c, __mdt, __e) connus de l'org, et l'objet des pages d'enregistrement où il est déposé.",
        "Tableau Synthese. Un permission set est rattaché à une squad lorsque sa description contient « squad … » ou « périmètre … ». Ses objets lui sont attribués. Un objet présent dans plusieurs squads est partagé : il ne classe un écran que si cet écran n'utilise aucun objet exclusif.",
        "Les objets de plateforme (Omni*, SF_Async*) sont ignorés. User, RecordType, Group, Profile et Organization ne décident pas dès qu'un objet métier est présent. OpportunityLineItem et OpportunityContactRole suivent Opportunity, QuoteLineItem et QuoteLineItemGroupClass suivent Quote, ApplicationFormProduct suit ApplicationForm.",
        f"Lorsque les squads trouvées sont Parcours de vente et Vision Client, la colonne des écrans mixtes s'appelle « {result.multi_label} ».",
        "Tableau Synthese dictionnaire. La squad est le champ Squad responsable du data dictionnary. Piloté par n'est pas utilisé : c'est le système source. Un objet qui a une squad consommatrice est un socle (Account, Contact, AccountContactRelation lorsqu'ils sont renseignés ainsi) : il ne décide que si aucun autre objet de l'écran n'a de squad.",
        "Plusieurs valeurs séparées par | donnent Plusieurs squads. « Tous » ne décide pas. Une squad vide donne Non renseigné. La squad consommatrice ne remplace pas la squad responsable.",
        "Les totaux additionnent toutes les lignes de type, y compris les FlexCards et les LWC.",
        _COMPARISON,
    ]
    if not result.squad_names:
        lines.append(
            "Aucun permission set de squad n'a été trouvé. Le premier tableau reste vide tant qu'une description ne cite pas une squad ou un périmètre."
        )
    for index, line in enumerate(lines, start=3):
        cell = worksheet.cell(row=index, column=1, value=line)
        cell.alignment = _WRAP
        worksheet.row_dimensions[index].height = 60 if len(line) > 220 else 36
    worksheet.page_setup.orientation = "landscape"
    worksheet.page_setup.fitToPage = True
    worksheet.page_setup.fitToWidth = 1
    worksheet.page_setup.fitToHeight = 1
    worksheet.page_setup.paperSize = worksheet.PAPERSIZE_A4
    worksheet.print_area = f"A1:A{2 + len(lines)}"
    worksheet.page_setup.horizontalCentered = True
    worksheet.sheet_properties.pageSetUpPr.fitToPage = True


_COMPARISON = (
    "Différence entre les deux synthèses. La feuille Synthese classe chaque écran "
    "d'après les objets accordés aux squads dans les permission sets : la squad retenue "
    "est celle qui possède seule un objet utilisé par l'écran. La feuille Synthese dictionnaire "
    "classe les mêmes écrans d'après la Squad responsable saisie dans Créer un data dictionnary. "
    "Piloté par n'est pas une squad : c'est le système source (Salesforce, RCU, Alto…). "
    "Un écran peut donc changer de colonne d'une feuille à l'autre. Le dictionnaire compte "
    "aussi les écrans sans objet de permission set : ils apparaissent dans Non renseigné."
)


def _perm_notes(result: ScreenCountResult) -> list[str]:
    squads = ", ".join(result.squad_names) if result.squad_names else "aucune squad détectée"
    return [
        _COMPARISON,
        f"Squads lues dans les descriptions : {squads}. {SHARED} : l'écran n'utilise que des objets présents dans plusieurs squads. {result.multi_label} : l'écran utilise des objets exclusifs de plusieurs squads.",
        "Les enfants standard suivent leur parent exclusif. Un objet partagé ne reclasse pas un écran qui utilise déjà un objet exclusif.",
    ]


def _dict_notes() -> list[str]:
    return [
        _COMPARISON,
        "La squad responsable vient des informations enregistrées dans Créer un data dictionnary. Renseignez Squad responsable avant de compter, sinon la colonne Non renseigné regroupe les écrans.",
        "Un objet socle (squad consommatrice renseignée) ne décide que s'il est le seul objet de l'écran à porter une squad. InsurancePolicy, lorsqu'il est Vision Client | Parcours de vente, donne Plusieurs squads.",
    ]


def _count(items: list[ScreenItem], kind: str) -> int:
    return sum(1 for item in items if item.kind == kind)
