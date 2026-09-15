"""Classeur Excel "dette technique et entorse".

Reprend les deux tableaux de la page HTML ``debt.html`` : un onglet pour la
dette technique, un onglet pour les entorses et points remarquables. Les
lignes viennent du meme fichier JSON que la page, soit via le snapshot d'un
run complet, soit directement depuis l'ecran de gestion de la dette qui
exporte ce qu'il affiche sans relancer la documentation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from openpyxl import Workbook

from src.core.models import DeviationItem, TechnicalDebtItem

DEBT_WORKBOOK_NAME = "dette technique et entorse.xlsx"

TECHNICAL_DEBT_SHEET = "Dette technique"
DEVIATIONS_SHEET = "Entorses"

_TECHNICAL_DEBT_HEADERS = [
    "Libelle",
    "Date creation",
    "Date resolution",
    "Solution acceptee comme dette technique",
    "Solution Cible",
]
_DEVIATIONS_HEADERS = ["Libelle", "Date creation", "Explication"]

#: En-tete de la colonne ajoutee quand l'export couvre plusieurs orgs.
ALIAS_HEADER = "Alias"


class _ExcelDebtMixin:
    """Ajoute ``write_debt_workbook`` a :class:`ExcelReportWriter`."""

    def write_debt_workbook(
        self,
        technical_debt: Sequence[tuple[str, TechnicalDebtItem]],
        deviations: Sequence[tuple[str, DeviationItem]],
        output_path: str | Path,
        *,
        include_alias: bool = False,
    ) -> Path:
        """Ecrit le classeur de la dette technique et des entorses.

        Chaque entree est couplee a l'alias de l'org dont elle vient.
        ``include_alias`` ajoute cet alias en premiere colonne : un run
        documente une seule org et n'en a pas besoin, alors qu'un export
        depuis l'ecran de gestion peut melanger plusieurs orgs.
        """

        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        alias_column = [ALIAS_HEADER] if include_alias else []

        workbook = Workbook()
        technical_sheet = workbook.active
        technical_sheet.title = TECHNICAL_DEBT_SHEET
        self._write_sheet(
            technical_sheet,
            alias_column + _TECHNICAL_DEBT_HEADERS,
            [
                [
                    *([alias] if include_alias else []),
                    item.label,
                    item.date_creation,
                    item.date_resolution,
                    item.accepted_solution,
                    item.target_solution,
                ]
                for alias, item in technical_debt
            ],
        )

        self._write_sheet(
            workbook.create_sheet(DEVIATIONS_SHEET),
            alias_column + _DEVIATIONS_HEADERS,
            [
                [
                    *([alias] if include_alias else []),
                    item.label,
                    item.date_creation,
                    item.explanation,
                ]
                for alias, item in deviations
            ],
        )

        workbook.save(output)
        self.log(
            f"Classeur dette technique et entorses genere "
            f"({len(technical_debt)} element(s) de dette, "
            f"{len(deviations)} entorse(s)): {output}"
        )
        return output
