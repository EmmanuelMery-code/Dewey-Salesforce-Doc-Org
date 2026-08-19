"""Small standalone helpers shared by the Data Dictionary screen mixins."""

from __future__ import annotations

import unicodedata


def _normalize_csv_header(value: str) -> str:
    """Accent/case-insensitive normalization used to recognize CSV columns
    regardless of the exact casing/accents used by whoever prepared the
    file (e.g. "Piloté Par" vs "piloté par" vs "Pilote Par")."""
    ascii_value = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode("ascii")
    return ascii_value.strip().lower()
