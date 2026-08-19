"""Central design system for the Tkinter UI (Mode A).

Single source of truth for spacing, typography, colors and named ``ttk``
styles, so every screen references the same constants instead of each
window re-inventing its own magic numbers, font tuples and hex colors (see
``AMELIORATIONS_UX.md`` for the audit that motivated this module).

Usage::

    from src.ui import theme

    frame = ttk.Frame(parent, padding=theme.SPACE_MD)
    ttk.Label(frame, text="Title", style=theme.TITLE_LABEL).pack(
        anchor="w", pady=(0, theme.SPACE_SM)
    )

:func:`register_styles` must be called once (from
``AppUiMixin._setup_styles``, on every platform, not only macOS) before the
named styles below are used; it is idempotent so it is safe to import this
module anywhere without worrying about call order.
"""

from __future__ import annotations

from tkinter import ttk

FONT_FAMILY = "Segoe UI"
FONT_FAMILY_MONO = "Consolas"

# ---------------------------------------------------------------------------
# Spacing scale — use these instead of raw ints (5, 10, 20, ...) for padding,
# padx and pady throughout the UI.
# ---------------------------------------------------------------------------
SPACE_XS = 4
SPACE_SM = 8
SPACE_MD = 12
SPACE_LG = 16
SPACE_XL = 24

# ---------------------------------------------------------------------------
# Typography scale — 3 heading levels + body/small/mono text. A window or
# secondary screen's page title is always FONT_TITLE; a section heading
# inside that page (a LabelFrame-style block) is always FONT_SECTION; an
# optional third level for a heading nested inside a section is
# FONT_SUBSECTION. This replaces the ~5 different title sizes (16/14/13/12/11
# bold) previously scattered across screens.
# ---------------------------------------------------------------------------
FONT_TITLE = (FONT_FAMILY, 16, "bold")
FONT_SECTION = (FONT_FAMILY, 13, "bold")
FONT_SUBSECTION = (FONT_FAMILY, 11, "bold")
FONT_LABEL = (FONT_FAMILY, 10)
FONT_LABEL_BOLD = (FONT_FAMILY, 10, "bold")
FONT_SMALL = (FONT_FAMILY, 9)
FONT_SMALL_ITALIC = (FONT_FAMILY, 9, "italic")
FONT_MONO = (FONT_FAMILY_MONO, 9)

# ---------------------------------------------------------------------------
# Semantic color palette. COLOR_DANGER / COLOR_WARNING / COLOR_CAUTION /
# COLOR_INFO deliberately reuse the same hex values as
# ``Application.ANALYZER_SEVERITY_COLORS`` (Critical/Major/Minor/Info) so
# there is a single palette, not two parallel ones. The remaining colors
# consolidate the hex codes already repeated across >10 modules
# (discussion_panel, analyzer_rules_panel, posture_capability_panel, ...).
# ---------------------------------------------------------------------------
COLOR_DANGER = "#991b1b"  # == Application.ANALYZER_SEVERITY_COLORS["Critical"]
COLOR_WARNING = "#9a3412"  # == Application.ANALYZER_SEVERITY_COLORS["Major"]
COLOR_CAUTION = "#854d0e"  # == Application.ANALYZER_SEVERITY_COLORS["Minor"]
COLOR_INFO = "#1e3a8a"  # == Application.ANALYZER_SEVERITY_COLORS["Info"]

COLOR_SUCCESS = "#047857"
COLOR_ACCENT = "#1d4ed8"
COLOR_MUTED = "#475569"
COLOR_MUTED_LIGHT = "#6b7280"
COLOR_TEXT = "#1f2937"
COLOR_HIGHLIGHT_BG = "#fde68a"

# ---------------------------------------------------------------------------
# Named ttk styles — configured once by register_styles(). Widgets opt in via
# style=theme.XXX instead of repeating font=/foreground= at each call site.
# ---------------------------------------------------------------------------
TITLE_LABEL = "Title.TLabel"
SECTION_LABEL = "Section.TLabel"
SECTION_LABELFRAME = "Section.TLabelframe"
SUBSECTION_LABEL = "Subsection.TLabel"
MUTED_LABEL = "Muted.TLabel"
MONO_LABEL = "Mono.TLabel"
PRIMARY_BUTTON = "Primary.TButton"
DANGER_BUTTON = "Danger.TButton"

_styles_registered = False


def register_styles(style: ttk.Style) -> None:
    """Create the named styles above on ``style``. Safe to call more than once
    (e.g. if several ``Toplevel`` windows each instantiate their own
    ``ttk.Style()`` handle to the same underlying Tk interpreter): the second
    and later calls are no-ops.
    """
    global _styles_registered
    if _styles_registered:
        return

    style.configure(TITLE_LABEL, font=FONT_TITLE)
    style.configure(SECTION_LABEL, font=FONT_SECTION)
    style.configure(f"{SECTION_LABELFRAME}.Label", font=FONT_SECTION)
    style.configure(SUBSECTION_LABEL, font=FONT_SUBSECTION)
    style.configure(MUTED_LABEL, font=FONT_LABEL, foreground=COLOR_MUTED)
    style.configure(MONO_LABEL, font=FONT_MONO)

    style.configure(PRIMARY_BUTTON, font=FONT_LABEL_BOLD)

    # NB: on Windows' native "vista" ttk theme, buttons are drawn by the
    # platform and can partially ignore foreground/background overrides;
    # this remains the best-effort, single place to express "this is a
    # destructive action" rather than repeating the color at each call site.
    style.configure(DANGER_BUTTON, foreground=COLOR_DANGER)
    style.map(DANGER_BUTTON, foreground=[("disabled", COLOR_MUTED)])

    _styles_registered = True
