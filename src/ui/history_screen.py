"""Screen to view and manage generation history."""

from __future__ import annotations

import csv
import os
import webbrowser
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import TYPE_CHECKING

from src.core.history_service import HistoryEntry, HistoryService, GeneratedReport
from src.reporting.html.renderers.history_reports import (
    render_dashboard,
    render_comparison,
    write_history_report,
)

if TYPE_CHECKING:
    from src.ui.application import Application


def show_history_screen(app: Application) -> None:
    """Create and show the history management window."""
    
    db_path = app.app_dir / "history.db"
    service = HistoryService(db_path)
    
    window = tk.Toplevel(app)
    window.title(app._t("history_title"))
    window.geometry("1100x600")
    app._configure_secondary_window(window)
    
    # Main container with scrollbars for the whole window
    main_container = ttk.Frame(window)
    main_container.pack(fill="both", expand=True)
    
    canvas = tk.Canvas(main_container, highlightthickness=0)
    v_scroll = ttk.Scrollbar(main_container, orient="vertical", command=canvas.yview)
    h_scroll = ttk.Scrollbar(main_container, orient="horizontal", command=canvas.xview)
    
    scrollable_frame = ttk.Frame(canvas)
    scrollable_frame.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
    )
    
    canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
    canvas.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)
    
    v_scroll.pack(side="right", fill="y")
    h_scroll.pack(side="bottom", fill="x")
    canvas.pack(side="left", fill="both", expand=True)

    # Mouse wheel support for the main canvas
    def _on_mousewheel(event):
        canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
    canvas.bind_all("<MouseWheel>", _on_mousewheel)

    # PanedWindow for left (aliases) and right (entries) inside the scrollable frame
    paned = ttk.PanedWindow(scrollable_frame, orient="horizontal")
    paned.pack(fill="both", expand=True, padx=10, pady=10)
    
    # Force a minimum size for the paned window to ensure scrollbars appear if window is too small
    scrollable_frame.update_idletasks()
    paned.configure(width=1050, height=550)
    
    # Left side: Alias list
    left_frame = ttk.Frame(paned)
    paned.add(left_frame, weight=1)
    
    ttk.Label(left_frame, text=app._t("history_aliases_title"), font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(0, 5))
    
    alias_container = ttk.Frame(left_frame)
    alias_container.pack(fill="both", expand=True)

    alias_tree = ttk.Treeview(alias_container, columns=("label",), show="tree headings", selectmode="browse")
    alias_tree.heading("#0", text=app._t("alias"))
    alias_tree.heading("label", text="Rapports")
    alias_tree.column("#0", width=150)
    alias_tree.column("label", width=150)
    
    # Scrollbars for alias_tree
    alias_vscroll = ttk.Scrollbar(alias_container, orient="vertical", command=alias_tree.yview)
    alias_hscroll = ttk.Scrollbar(alias_container, orient="horizontal", command=alias_tree.xview)
    alias_tree.configure(yscrollcommand=alias_vscroll.set, xscrollcommand=alias_hscroll.set)
    
    alias_vscroll.pack(side="right", fill="y")
    alias_hscroll.pack(side="bottom", fill="x")
    alias_tree.pack(side="left", fill="both", expand=True)

    # Context menu for alias_tree
    alias_menu = tk.Menu(window, tearoff=0)
    
    def export_alias_csv():
        selected = alias_tree.selection()
        if not selected:
            return
        item = alias_tree.item(selected[0])
        if item.get("tags") and "report" in item["tags"]:
            return # Don't export from report node
        alias = item["text"]
        entries = service.list_entries_for_alias(alias)
        if not entries:
            return
            
        file_path = filedialog.asksaveasfilename(
            title=app._t("history_export_title"),
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            initialfile=f"history_{alias}.csv"
        )
        if not file_path:
            return
            
        try:
            with open(file_path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f, delimiter=";")
                # Header
                writer.writerow([
                    "#", app._t("history_col_date"), app._t("scoring_overall_score"), 
                    app._t("adopt_adapt_overall_score"), "Couverture Apex", "Couverture Flows",
                    app._t("scoring_component_custom_objects"),
                    app._t("scoring_component_custom_fields"), app._t("scoring_component_flows"),
                    app._t("configuration_card_apex_classes_triggers"), app._t("configuration_card_omni_components"),
                    "Sharing Rules",
                    app._t("configuration_card_findings"), 
                    app._t("configuration_rules_severity_critical"),
                    app._t("configuration_rules_severity_major"),
                    app._t("configuration_rules_severity_minor"),
                    app._t("configuration_rules_severity_info"),
                    app._t("configuration_card_ai_usage"),
                    app._t("history_col_dm_custom"), app._t("history_col_dm_standard"),
                    app._t("history_col_adoption"), app._t("history_col_adaptation"),
                    "Commentaire"
                ])
                for e in entries:
                    writer.writerow([
                        e.generation_number, e.timestamp, e.score, e.adopt_adapt_score,
                        f"{e.test_coverage_apex:.1f}%" if e.test_coverage_apex is not None else "N/A",
                        f"{e.test_coverage_flows:.1f}%" if e.test_coverage_flows is not None else "N/A",
                        e.custom_objects, e.custom_fields, e.flows, e.apex_classes_triggers,
                        e.omni_components, e.sharing_rules, e.findings_total, 
                        e.findings_critical, e.findings_major, e.findings_minor, e.findings_info,
                        f"{e.ai_usage_pct:.1f}%",
                        f"{e.data_model_custom_pct:.1f}%", f"{e.data_model_standard_pct:.1f}%",
                        f"{e.adoption_pct:.1f}%", f"{e.adaptation_pct:.1f}%",
                        e.comment
                    ])
            messagebox.showinfo(app._t("success_title"), app._t("history_export_done"))
        except Exception as exc:
            messagebox.showerror(app._t("error_title"), f"Erreur export : {exc}")

    def delete_alias_full():
        selected = alias_tree.selection()
        if not selected:
            return
        item = alias_tree.item(selected[0])
        if item.get("tags") and "report" in item["tags"]:
            return
        alias = item["text"]
        if messagebox.askyesno(app._t("confirmation_delete"), app._t("history_confirm_delete_alias").format(alias=alias)):
            service.delete_alias(alias)
            refresh_aliases()
            entry_tree.delete(*entry_tree.get_children())

    def delete_report_action():
        selected = alias_tree.selection()
        if not selected:
            return
        item = alias_tree.item(selected[0])
        if not (item.get("tags") and "report" in item["tags"]):
            return
        
        report_label = item["text"]
        report_path = item["values"][0]
        report_id = item["values"][1] # ID is stored as second value

        if messagebox.askyesno(app._t("confirmation_delete"), f"Voulez-vous vraiment supprimer le rapport '{report_label}' ?"):
            try:
                # Delete file
                p = Path(report_path)
                if not p.is_absolute():
                    p = (app.app_dir / p).resolve()
                    
                if p.exists():
                    p.unlink()
                
                # Delete from DB
                service.delete_report(report_id)
                
                refresh_aliases()
            except Exception as exc:
                messagebox.showerror(app._t("error_title"), f"Erreur lors de la suppression : {exc}")

    alias_menu.add_command(label=app._t("history_menu_export_csv"), command=export_alias_csv)
    alias_menu.add_command(label=app._t("history_menu_delete_alias"), command=delete_alias_full)
    alias_menu.add_command(label="Supprimer ce rapport", command=delete_report_action)

    def show_alias_context_menu(event):
        item_id = alias_tree.identify_row(event.y)
        if item_id:
            item = alias_tree.item(item_id)
            alias_tree.selection_set(item_id)
            
            # Show/hide menu items based on selection
            alias_menu.delete(0, "end")
            if item.get("tags") and "report" in item["tags"]:
                alias_menu.add_command(label="Supprimer ce rapport", command=delete_report_action)
            else:
                alias_menu.add_command(label=app._t("history_menu_export_csv"), command=export_alias_csv)
                alias_menu.add_command(label=app._t("history_menu_delete_alias"), command=delete_alias_full)
                
            alias_menu.post(event.x_root, event.y_root)

    alias_tree.bind("<Button-3>", show_alias_context_menu) # Right click Windows/Linux
    alias_tree.bind("<Button-2>", show_alias_context_menu) # Right click macOS
    
    def on_alias_double_click(event):
        selected = alias_tree.selection()
        if not selected:
            return
        item = alias_tree.item(selected[0])
        if item.get("tags") and "report" in item["tags"]:
            path_str = item["values"][0]
            path = Path(path_str)
            if not path.is_absolute():
                path = (app.app_dir / path).resolve()
                
            if path.exists():
                try:
                    if hasattr(os, 'startfile'):
                        os.startfile(str(path))
                    else:
                        webbrowser.open_new_tab(path.as_uri())
                except Exception as exc:
                    webbrowser.open_new_tab(path.as_uri())
            else:
                messagebox.showerror(app._t("error_title"), app._t("history_report_not_found"))

    alias_tree.bind("<Double-1>", on_alias_double_click)

    # Right side: Entry list
    right_frame = ttk.Frame(paned)
    paned.add(right_frame, weight=4)
    
    ttk.Label(right_frame, text=app._t("history_entries_title"), font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(0, 5))
    
    entry_container = ttk.Frame(right_frame)
    entry_container.pack(fill="both", expand=True)

    columns = (
        "num", "timestamp", "score", "adopt_adapt", "coverage_apex", "coverage_flows", "objects", "fields", 
        "flows", "apex", "omni", "sharing_rules", "findings", "crit", "maj", "min", "inf", "ai", "dm_custom", "dm_standard",
        "adoption", "adaptation", "comment"
    )
    entry_tree = ttk.Treeview(entry_container, columns=columns, show="headings", selectmode="extended")
    
    # Configure columns
    col_config = {
        "num": ("#", 40),
        "timestamp": (app._t("history_col_date"), 130),
        "score": (app._t("scoring_overall_score"), 60),
        "adopt_adapt": (app._t("adopt_adapt_overall_score"), 80),
        "coverage_apex": ("Couverture Apex", 90),
        "coverage_flows": ("Couverture Flows", 90),
        "objects": (app._t("scoring_component_custom_objects"), 70),
        "fields": (app._t("scoring_component_custom_fields"), 70),
        "flows": (app._t("scoring_component_flows"), 60),
        "apex": (app._t("configuration_card_apex_classes_triggers"), 80),
        "omni": (app._t("configuration_card_omni_components"), 80),
        "sharing_rules": ("Sharing Rules", 80),
        "findings": (app._t("configuration_card_findings"), 70),
        "crit": (app._t("configuration_rules_severity_critical"), 50),
        "maj": (app._t("configuration_rules_severity_major"), 50),
        "min": (app._t("configuration_rules_severity_minor"), 50),
        "inf": (app._t("configuration_rules_severity_info"), 50),
        "ai": (app._t("configuration_card_ai_usage"), 60),
        "dm_custom": (app._t("history_col_dm_custom"), 80),
        "dm_standard": (app._t("history_col_dm_standard"), 80),
        "adoption": (app._t("history_col_adoption"), 80),
        "adaptation": (app._t("history_col_adaptation"), 80),
        "comment": ("Commentaire", 160),
    }
    
    for col, (label, width) in col_config.items():
        entry_tree.heading(col, text=label)
        entry_tree.column(col, width=width, anchor="center", stretch=False) # stretch=False to allow horizontal scroll
    
    # Scrollbars for entry_tree
    entry_vscroll = ttk.Scrollbar(entry_container, orient="vertical", command=entry_tree.yview)
    entry_hscroll = ttk.Scrollbar(entry_container, orient="horizontal", command=entry_tree.xview)
    entry_tree.configure(yscrollcommand=entry_vscroll.set, xscrollcommand=entry_hscroll.set)
    
    entry_vscroll.pack(side="right", fill="y")
    entry_hscroll.pack(side="bottom", fill="x")
    entry_tree.pack(side="left", fill="both", expand=True)
    
    # Context menu for entry_tree
    entry_menu = tk.Menu(window, tearoff=0)
    
    def create_dashboard_action():
        selected = entry_tree.selection()
        if len(selected) != 1:
            return
        
        entry_id = entry_tree.item(selected[0])["values"][-1]
        alias = alias_tree.item(alias_tree.selection()[0])["text"]
        entries = service.list_entries_for_alias(alias)
        selected_entry = next((e for e in entries if e.id == entry_id), None)
        
        # Get all entries for this alias to show trend
        history = service.list_entries_for_alias(alias)
        
        if selected_entry:
            # Resolve relative paths
            output_dir = Path(selected_entry.output_dir)
            if not output_dir.is_absolute():
                output_dir = app.app_dir / output_dir
            
            assets_dir = output_dir / "html" / "assets"
            filename = f"dashboard_{selected_entry.generation_number}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
            content = render_dashboard(selected_entry, history, output_dir / "html" / filename, assets_dir)
            path = write_history_report(selected_entry, "dashboard", content, filename)
            
            service.add_report(GeneratedReport(
                alias=alias,
                type="dashboard",
                path=str(path),
                label=f"Dashboard Gen #{selected_entry.generation_number}"
            ))
            refresh_aliases()
            messagebox.showinfo(app._t("success_title"), app._t("history_dashboard_created"))

    def compare_generations_action():
        selected = entry_tree.selection()
        if len(selected) != 2:
            return
        
        id1 = entry_tree.item(selected[0])["values"][-1]
        id2 = entry_tree.item(selected[1])["values"][-1]
        alias = alias_tree.item(alias_tree.selection()[0])["text"]
        entries = service.list_entries_for_alias(alias)
        e1 = next((e for e in entries if e.id == id1), None)
        e2 = next((e for e in entries if e.id == id2), None)
        
        if e1 and e2:
            # Sort by generation number
            new, old = (e1, e2) if e1.generation_number > e2.generation_number else (e2, e1)
            
            # Resolve relative paths
            new_output_dir = Path(new.output_dir)
            if not new_output_dir.is_absolute():
                new_output_dir = app.app_dir / new_output_dir
                
            assets_dir = new_output_dir / "html" / "assets"
            filename = f"compare_{old.generation_number}_to_{new.generation_number}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
            content = render_comparison(new, old, new_output_dir / "html" / filename, assets_dir)
            path = write_history_report(new, "comparison", content, filename)
            
            service.add_report(GeneratedReport(
                alias=alias,
                type="comparison",
                path=str(path),
                label=f"Comparaison #{old.generation_number} vs #{new.generation_number}"
            ))
            refresh_aliases()
            messagebox.showinfo(app._t("success_title"), app._t("history_comparison_created"))

    entry_menu.add_command(label=app._t("history_menu_create_dashboard"), command=create_dashboard_action)
    entry_menu.add_command(label=app._t("history_menu_compare_generations"), command=compare_generations_action)

    def show_entry_context_menu(event):
        item_id = entry_tree.identify_row(event.y)
        if item_id:
            # If the right-clicked item is not in the current selection, 
            # select only this item. Otherwise, keep the multi-selection.
            if item_id not in entry_tree.selection():
                entry_tree.selection_set(item_id)
                
        selected = entry_tree.selection()
        if not selected:
            return
        
        entry_menu.delete(0, "end")
        if len(selected) == 1:
            entry_menu.add_command(label=app._t("history_menu_create_dashboard"), command=create_dashboard_action)
        elif len(selected) == 2:
            entry_menu.add_command(label=app._t("history_menu_compare_generations"), command=compare_generations_action)
        
        if len(selected) > 0:
            if entry_menu.index("end") is not None:
                entry_menu.add_separator()
            entry_menu.add_command(label=app._t("delete"), command=on_delete)
        
        if entry_menu.index("end") is not None:
            entry_menu.post(event.x_root, event.y_root)

    entry_tree.bind("<Button-3>", show_entry_context_menu)
    entry_tree.bind("<Button-2>", show_entry_context_menu)

    def on_entry_double_click(event):
        item_id = entry_tree.identify_row(event.y)
        if not item_id:
            return
        entry_id = entry_tree.item(item_id)["values"][-1]
        sel = alias_tree.selection()
        if not sel:
            return
        alias = alias_tree.item(sel[0])["text"]
        entries = service.list_entries_for_alias(alias)
        entry = next((e for e in entries if e.id == entry_id), None)
        if entry:
            show_entry_detail_dialog(app, window, entry, service, refresh_entries)

    entry_tree.bind("<Double-1>", on_entry_double_click)

    # Buttons
    button_row = ttk.Frame(right_frame)
    button_row.pack(fill="x", pady=(10, 0))
    
    def on_delete():
        selected = entry_tree.selection()
        if not selected:
            messagebox.showwarning(app._t("info_title"), app._t("history_select_to_delete"))
            return
        
        if messagebox.askyesno(app._t("confirmation_delete"), app._t("history_confirm_delete")):
            for item in selected:
                entry_id = entry_tree.item(item)["values"][-1]
                service.delete_entry(entry_id)
            refresh_entries()
            
    def on_edit():
        selected = entry_tree.selection()
        if len(selected) != 1:
            messagebox.showwarning(app._t("info_title"), app._t("history_select_to_edit"))
            return
        
        # Simple edit dialog for score and alias
        entry_id = entry_tree.item(selected[0])["values"][-1]
        # Find entry in current list
        alias = alias_tree.item(alias_tree.selection()[0])["text"]
        entries = service.list_entries_for_alias(alias)
        entry = next((e for e in entries if e.id == entry_id), None)
        
        if entry:
            show_edit_dialog(app, window, entry, service, refresh_entries)

    delete_btn = ttk.Button(button_row, text=app._t("delete"), command=on_delete)
    delete_btn.pack(side="right", padx=5)
    
    edit_btn = ttk.Button(button_row, text=app._t("configuration_ai_tags_edit"), command=on_edit)
    edit_btn.pack(side="right", padx=5)
    
    # Data loading
    def refresh_aliases():
        # Remember selection
        current_sel = alias_tree.selection()
        current_alias = alias_tree.item(current_sel[0])["text"] if current_sel else None
        
        alias_tree.delete(*alias_tree.get_children())
        for alias in service.list_aliases():
            parent = alias_tree.insert("", "end", text=alias, open=True)
            reports = service.list_reports_for_alias(alias)
            for r in reports:
                alias_tree.insert(parent, "end", text=r.label, values=(r.path, r.id), tags=("report",))
            
            if alias == current_alias:
                alias_tree.selection_set(parent)
            
    def refresh_entries(_event=None):
        entry_tree.delete(*entry_tree.get_children())
        selected = alias_tree.selection()
        if not selected:
            return
        
        item = alias_tree.item(selected[0])
        if item.get("tags") and "report" in item["tags"]:
            return

        alias = item["text"]
        for e in service.list_entries_for_alias(alias):
            entry_tree.insert("", "end", values=(
                e.generation_number,
                e.timestamp,
                e.score,
                e.adopt_adapt_score,
                f"{e.test_coverage_apex:.1f}%" if e.test_coverage_apex is not None else "N/A",
                f"{e.test_coverage_flows:.1f}%" if e.test_coverage_flows is not None else "N/A",
                e.custom_objects,
                e.custom_fields,
                e.flows,
                e.apex_classes_triggers,
                e.omni_components,
                e.sharing_rules,
                e.findings_total,
                e.findings_critical,
                e.findings_major,
                e.findings_minor,
                e.findings_info,
                f"{e.ai_usage_pct:.1f}%",
                f"{e.data_model_custom_pct:.1f}%",
                f"{e.data_model_standard_pct:.1f}%",
                f"{e.adoption_pct:.1f}%",
                f"{e.adaptation_pct:.1f}%",
                (e.comment[:45] + "…") if len(e.comment) > 45 else e.comment,
                e.id # Hidden ID
            ))

    alias_tree.bind("<<TreeviewSelect>>", refresh_entries)
    alias_tree.tag_configure("report", foreground="blue")
    
    refresh_aliases()
    if alias_tree.get_children():
        alias_tree.selection_set(alias_tree.get_children()[0])


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
    row(sec, 1, "Composants OmniStudio", entry.omni_components)
    row(sec, 2, "Agents IA", entry.agents)
    row(sec, 3, "Gen AI Prompts", entry.gen_ai_prompts)
    row(sec, 4, "Einstein Predictions", entry.einstein_predictions)
    row(sec, 5, "Sharing Rules", entry.sharing_rules)

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
