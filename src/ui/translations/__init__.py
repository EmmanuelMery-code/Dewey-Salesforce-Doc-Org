"""UI translation strings.

This package was split from a single ``translations.py`` module for
readability. Each language dictionary is spread over two fragment files
(``*_part1`` / ``*_part2``) that are merged here into the ``TRANSLATIONS``
mapping so that ``from src.ui.translations import TRANSLATIONS`` keeps
working unchanged.
"""

from __future__ import annotations

from src.ui.translations.en_part1 import EN_PART1
from src.ui.translations.en_part2 import EN_PART2
from src.ui.translations.fr_part1 import FR_PART1
from src.ui.translations.fr_part2 import FR_PART2

TRANSLATIONS: dict[str, dict[str, str]] = {
    "fr": {**FR_PART1, **FR_PART2},
    "en": {**EN_PART1, **EN_PART2},
}

__all__ = ["TRANSLATIONS"]
