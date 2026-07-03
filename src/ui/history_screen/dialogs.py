"""Modal dialogs used by the history screen (edit + read-only detail)."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import TYPE_CHECKING

from src.core.history_service import HistoryEntry, HistoryService

if TYPE_CHECKING:
    from src.ui.application import Application


def show_edit_dialog(app: Application, parent: tk.Toplevel, entry: HistoryEntry, service: HistoryService, callback: callable) -> None:
    dialog = tk.Toplevel(parent)
    dialog.title(app._t("history_edit_title"))
    dialog.geometry("400x300")
    app._configure_secondary_window(dialog)

    frame = ttk.Frame(dialog, padding=20)
    frame.pack(fill="both", expand=True)

    # Only allow editing some fields for simplicity
    ttk.Label(frame, text=app._t("alias")).grid(row=0, column=0, sticky="w", pady=5)
    alias_var = tk.StringVar(value=entry.alias)
    ttk.Entry(frame, textvariable=alias_var).grid(row=0, column=1, sticky="ew", pady=5)

    ttk.Label(frame, text=app._t("scoring_overall_score")).grid(row=1, column=0, sticky="w", pady=5)
    score_var = tk.StringVar(value=str(entry.score))
    ttk.Entry(frame, textvariable=score_var).grid(row=1, column=1, sticky="ew", pady=5)

    ttk.Label(frame, text=app._t("adopt_adapt_overall_score")).grid(row=2, column=0, sticky="w", pady=5)
    aa_score_var = tk.StringVar(value=str(entry.adopt_adapt_score))
    ttk.Entry(frame, textvariable=aa_score_var).grid(row=2, column=1, sticky="ew", pady=5)

    def save():
        try:
            entry.alias = alias_var.get().strip()
            entry.score = int(score_var.get())
            entry.adopt_adapt_score = int(aa_score_var.get())
            service.update_entry(entry)
            callback()
            dialog.destroy()
        except ValueError:
            messagebox.showerror(app._t("error_title"), app._t("scoring_invalid_weight").format(component="Score"))

    ttk.Button(frame, text=app._t("configuration_save"), command=save).grid(row=3, column=0, columnspan=2, pady=20)
    frame.columnconfigure(1, weight=1)


def show_entry_detail_dialog(
    app: "Application",
    parent: tk.Toplevel,
    entry: HistoryEntry,
    service: HistoryService,
    refresh_callback: callable,
) -> None:
    """Open a read-only detail sheet for a history entry with an editable comment."""
    dialog = tk.Toplevel(parent)
    dialog.title(f"Génération #{entry.generation_number} — {entry.alias}")
    dialog.geometry("900x680")
    app._configure_secondary_window(dialog)

    # Scrollable area
    outer = ttk.Frame(dialog)
    outer.pack(fill="both", expand=True)

    canvas = tk.Canvas(outer, highlightthickness=0)
    vscroll = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
    inner = ttk.Frame(canvas)
    inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas_win = canvas.create_window((0, 0), window=inner, anchor="nw")
    canvas.configure(yscrollcommand=vscroll.set)

    def _resize_inner(event):
        canvas.itemconfig(canvas_win, width=event.width)
    canvas.bind("<Configure>", _resize_inner)

    def _on_mw(event):
        canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
    dialog.bind("<MouseWheel>", _on_mw)

    vscroll.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)

    # ── Two-column layout ────────────────────────────────────────
    # Each pair of sections shares a row; Comment stays full-width.
    cols_frame = ttk.Frame(inner)
    cols_frame.pack(fill="x", padx=8, pady=(8, 0))
    cols_frame.columnconfigure(0, weight=1, uniform="col")
    cols_frame.columnconfigure(1, weight=1, uniform="col")

    # Left and right column containers
    left = ttk.Frame(cols_frame)
    left.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
    right = ttk.Frame(cols_frame)
    right.grid(row=0, column=1, sticky="nsew", padx=(4, 0))

    def section(parent_col: ttk.Frame, title: str) -> ttk.LabelFrame:
        lf = ttk.LabelFrame(parent_col, text=title, padding=(10, 6))
        lf.pack(fill="x", pady=(0, 8))
        lf.columnconfigure(1, weight=1)
        return lf

    def row(frame: ttk.LabelFrame, r: int, label: str, value) -> None:
        ttk.Label(frame, text=label + " :", foreground="gray").grid(
            row=r, column=0, sticky="w", padx=(0, 10), pady=2
        )
        txt = str(value) if value is not None else "N/A"
        ttk.Label(frame, text=txt, wraplength=300, justify="left").grid(
            row=r, column=1, sticky="w", pady=2
        )

    # ── LEFT COLUMN ──────────────────────────────────────────────
    # Identification
    sec = section(left, "Identification")
    row(sec, 0, "Alias", entry.alias)
    row(sec, 1, "N° génération", entry.generation_number)
    row(sec, 2, "Date", entry.timestamp)
    row(sec, 3, "Répertoire source", entry.source_dir)
    row(sec, 4, "Répertoire de sortie", entry.output_dir)

    # Posture
    sec = section(left, "Posture Adopt / Adapt")
    row(sec, 0, "Adopt (OOTB)", entry.adopt_ootb_count)
    row(sec, 1, "Adopt (déclaratif)", entry.adopt_decl_count)
    row(sec, 2, "Adapt (déclaratif)", entry.adapt_low_count)
    row(sec, 3, "Adapt (code)", entry.adapt_high_count)
    row(sec, 4, "Taux adoption", f"{entry.adoption_pct:.1f}%")
    row(sec, 5, "Taux adaptation", f"{entry.adaptation_pct:.1f}%")

    # Composants
    sec = section(left, "Composants")
    row(sec, 0, "Objets custom", entry.custom_objects)
    row(sec, 1, "Objets standard", entry.standard_objects)
    row(sec, 2, "Champs custom", entry.custom_fields)
    row(sec, 3, "Champs standard", entry.standard_fields)
    row(sec, 4, "Flows", entry.flows)
    row(sec, 5, "Record Types", entry.record_types)
    row(sec, 6, "Validation Rules", entry.validation_rules)
    row(sec, 7, "Page Layouts", entry.page_layouts)
    row(sec, 8, "Onglets custom", entry.custom_tabs)
    row(sec, 9, "Apps custom", entry.custom_apps)
    row(sec, 10, "Total composants custom", entry.total_custom_components)
    row(sec, 11, "Total composants standard", entry.total_standard_components)

    # ── RIGHT COLUMN ─────────────────────────────────────────────
    # Scores
    cov_apex = f"{entry.test_coverage_apex:.1f}%" if entry.test_coverage_apex is not None else "N/A"
    cov_flows = f"{entry.test_coverage_flows:.1f}%" if entry.test_coverage_flows is not None else "N/A"
    sec = section(right, "Scores")
    row(sec, 0, "Score global", entry.score)
    row(sec, 1, "Score Adopt/Adapt", entry.adopt_adapt_score)
    row(sec, 2, "Couverture Apex", cov_apex)
    row(sec, 3, "Couverture Flows", cov_flows)

    # Code & Intégration
    sec = section(right, "Code & Intégration")
    row(sec, 0, "Classes Apex / Triggers", entry.apex_classes_triggers)
    row(sec, 1, "Triggers Apex", entry.apex_triggers)
    row(sec, 2, "Classes de test", entry.apex_test_classes)
    row(sec, 3, "Classes hors test / hors trigger", entry.apex_business_classes)
    row(sec, 4, "Composants LWC", entry.lwc_count)
    row(sec, 5, "Composants Aura", entry.aura_count)
    row(sec, 6, "Composants OmniStudio", entry.omni_components)
    row(sec, 7, "Agents IA", entry.agents)
    row(sec, 8, "Gen AI Prompts", entry.gen_ai_prompts)
    row(sec, 9, "Einstein Predictions", entry.einstein_predictions)
    row(sec, 10, "Sharing Rules", entry.sharing_rules)
    row(sec, 11, "Duplicate Rules", entry.duplicate_rules)

    # Analyseur
    sec = section(right, "Analyseur")
    row(sec, 0, "Findings total", entry.findings_total)
    row(sec, 1, "Critique", entry.findings_critical)
    row(sec, 2, "Majeur", entry.findings_major)
    row(sec, 3, "Mineur", entry.findings_minor)
    row(sec, 4, "Info", entry.findings_info)

    # Métriques
    sec = section(right, "Métriques")
    row(sec, 0, "Usage IA", f"{entry.ai_usage_pct:.1f}%")
    row(sec, 1, "Data Model custom %", f"{entry.data_model_custom_pct:.1f}%")
    row(sec, 2, "Data Model standard %", f"{entry.data_model_standard_pct:.1f}%")

    # ── Commentaire — pleine largeur ──────────────────────────────
    sec_comment = ttk.LabelFrame(inner, text="Commentaire", padding=(10, 6))
    sec_comment.pack(fill="x", padx=8, pady=(0, 4))
    comment_text = tk.Text(sec_comment, height=5, wrap="word", font=("Segoe UI", 9))
    comment_text.pack(fill="x", padx=2, pady=(4, 2))
    comment_text.insert("1.0", entry.comment or "")

    # Boutons
    btn_frame = ttk.Frame(inner)
    btn_frame.pack(fill="x", padx=8, pady=(0, 12))

    def save_comment() -> None:
        new_comment = comment_text.get("1.0", "end-1c").strip()
        entry.comment = new_comment
        service.update_comment(entry.id, new_comment)
        refresh_callback()
        messagebox.showinfo("Sauvegardé", "Commentaire sauvegardé.", parent=dialog)

    ttk.Button(btn_frame, text="Fermer", command=dialog.destroy).pack(side="right", padx=5)
    ttk.Button(btn_frame, text="Sauvegarder le commentaire", command=save_comment).pack(side="right")
