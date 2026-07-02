"""One-shot helper used to emit the FR/EN RTF guides next to the drawio
diagrams. Kept simple on purpose: structured content -> RTF tokens.

Run: python process/_build_rtf.py

Outputs:
    process/guide_utilisation_fr.rtf
    process/usage_guide_en.rtf

The RTF token helpers live in ``_rtf_helpers.py`` and the localized content
in ``_rtf_content_fr.py`` / ``_rtf_content_en.py``. This script can safely
be deleted once the RTF files are produced; it is re-executable to refresh
them after edits.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Allow ``python process/_build_rtf.py`` from any working directory by making
# the sibling helper/content modules importable.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _rtf_content_en import english_document
from _rtf_content_fr import french_document


def main() -> None:
    here = Path(__file__).resolve().parent
    fr_path = here / "guide_utilisation_fr.rtf"
    en_path = here / "usage_guide_en.rtf"
    fr_path.write_text(french_document(), encoding="cp1252", errors="replace")
    en_path.write_text(english_document(), encoding="cp1252", errors="replace")
    print("Wrote", fr_path)
    print("Wrote", en_path)


if __name__ == "__main__":
    main()
