"""Main history management window."""

from __future__ import annotations

import csv
import os
import webbrowser
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import TYPE_CHECKING

from src.core.history_service import HistoryService, GeneratedReport
from src.reporting.html.renderers.history_reports import (
    render_dashboard,
    render_comparison,
    write_history_report,
)
from src.ui.history_screen.columns import build_entry_columns_config, build_entry_row_values
from src.ui.history_screen.csv_export import build_csv_data_row, build_csv_header_row
from src.ui.history_screen.dialogs import show_edit_dialog, show_entry_detail_dialog
from src.ui import theme

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

    # The paned window fills the whole window so its content (alias list and
    # entry table) resizes together with the window. Each tree keeps its own
    # scrollbars to handle overflow when the window is too small.
    paned = ttk.PanedWindow(window, orient="horizontal")
    paned.pack(fill="both", expand=True, padx=theme.SPACE_MD, pady=theme.SPACE_MD)

    # Left side: Alias list
    left_frame = ttk.Frame(paned)
    paned.add(left_frame, weight=1)

    ttk.Label(left_frame, text=app._t("history_aliases_title"), style=theme.SECTION_LABEL).pack(anchor="w", pady=(0, theme.SPACE_SM))

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
                writer.writerow(build_csv_header_row(app))
                for e in entries:
                    writer.writerow(build_csv_data_row(e))
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

    ttk.Label(right_frame, text=app._t("history_entries_title"), style=theme.SECTION_LABEL).pack(anchor="w", pady=(0, theme.SPACE_SM))

    entry_container = ttk.Frame(right_frame)
    entry_container.pack(fill="both", expand=True)

    columns = (
        "num", "timestamp", "score", "adopt_adapt", "coverage_apex", "coverage_flows", "objects", "fields",
        "flows", "apex", "apex_triggers", "apex_test_classes", "apex_business_classes", "lwc", "aura", "omni", "sharing_rules", "duplicate_rules", "findings", "crit", "maj", "min", "inf", "ai", "dm_custom", "dm_standard",
        "adoption", "adaptation", "comment"
    )
    entry_tree = ttk.Treeview(entry_container, columns=columns, show="headings", selectmode="extended")

    # Configure columns
    col_config = build_entry_columns_config(app)

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
    button_row.pack(fill="x", pady=(theme.SPACE_MD, 0))

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

    def on_export_csv():
        selected = alias_tree.selection()
        if not selected:
            messagebox.showwarning(
                app._t("info_title"), app._t("history_select_alias_to_export")
            )
            return
        item = alias_tree.item(selected[0])
        # If a report node is selected, fall back to its parent alias so the
        # export button works regardless of which node is highlighted.
        if item.get("tags") and "report" in item["tags"]:
            parent_id = alias_tree.parent(selected[0])
            if parent_id:
                alias_tree.selection_set(parent_id)
        export_alias_csv()

    delete_btn = ttk.Button(button_row, text=app._t("delete"), command=on_delete, style=theme.DANGER_BUTTON)
    delete_btn.pack(side="right", padx=theme.SPACE_SM)

    edit_btn = ttk.Button(button_row, text=app._t("configuration_ai_tags_edit"), command=on_edit)
    edit_btn.pack(side="right", padx=theme.SPACE_SM)

    export_btn = ttk.Button(button_row, text=app._t("history_export_csv"), command=on_export_csv, style=theme.PRIMARY_BUTTON)
    export_btn.pack(side="left", padx=theme.SPACE_SM)

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
            entry_tree.insert("", "end", values=build_entry_row_values(e))

    alias_tree.bind("<<TreeviewSelect>>", refresh_entries)
    alias_tree.tag_configure("report", foreground=theme.COLOR_ACCENT)

    refresh_aliases()
    if alias_tree.get_children():
        alias_tree.selection_set(alias_tree.get_children()[0])
