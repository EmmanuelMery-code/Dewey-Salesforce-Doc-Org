from __future__ import annotations

import tkinter as tk
import json
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import TYPE_CHECKING, Any, Dict, List

if TYPE_CHECKING:
    from src.ui.application import Application


def show_debt_screen(app: Application) -> None:
    """Create and show the technical debt and deviations management window."""
    DebtScreen(app)


class DebtScreen:
    def __init__(self, app: Application) -> None:
        self.app = app
        self.window = tk.Toplevel(app)
        self.window.title(app._t("debt_title"))
        self.window.geometry("1100x750")
        app._configure_secondary_window(self.window)

        self.current_file = tk.StringVar(value=app.technical_debt_file_var.get())
        self.filter_alias_var = tk.StringVar(value=app._t("debt_all_aliases"))
        
        # Data storage: { alias: { "technical_debt": [...], "deviations": [...] } }
        self.full_data: Dict[str, Any] = {}
        # Flat lists for the treeviews: list of tuples (alias, item_dict)
        self.technical_items: List[tuple[str, Dict[str, str]]] = []
        self.deviations_items: List[tuple[str, Dict[str, str]]] = []

        self._build_ui()
        if self.current_file.get():
            self._load_data()

    def _build_ui(self) -> None:
        # Main container
        main_frame = ttk.Frame(self.window, padding=16)
        main_frame.pack(fill="both", expand=True)

        # Header
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill="x", pady=(0, 12))
        
        ttk.Label(
            header_frame,
            text=self.app._t('debt_title'),
            font=("Segoe UI", 14, "bold"),
        ).pack(anchor="w")
        
        ttk.Label(
            header_frame,
            text=self.app._t("debt_description"),
            wraplength=800,
            justify="left",
        ).pack(anchor="w", pady=(4, 0))

        # Filter row
        filter_row = ttk.Frame(main_frame)
        filter_row.pack(fill="x", pady=(0, 10))
        
        ttk.Label(filter_row, text=self.app._t("debt_filter_alias")).pack(side="left", padx=(0, 10))
        
        self.filter_combo = ttk.Combobox(
            filter_row, 
            textvariable=self.filter_alias_var, 
            state="readonly",
            width=40
        )
        self.filter_combo.pack(side="left")
        self.filter_combo.bind("<<ComboboxSelected>>", lambda e: self._refresh_trees())

        # Tabs
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill="both", expand=True)

        self.technical_tab = ttk.Frame(self.notebook, padding=10)
        self.deviations_tab = ttk.Frame(self.notebook, padding=10)
        
        self.notebook.add(self.technical_tab, text=self.app._t("debt_tab_technical"))
        self.notebook.add(self.deviations_tab, text=self.app._t("debt_tab_deviations"))

        self._build_technical_tab()
        self._build_deviations_tab()

        # Footer buttons
        footer_frame = ttk.Frame(main_frame, padding=(0, 12, 0, 0))
        footer_frame.pack(fill="x")
        
        ttk.Button(
            footer_frame,
            text=self.app._t("configuration_close"),
            command=self.window.destroy,
        ).pack(side="right")
        
        ttk.Button(
            footer_frame,
            text=self.app._t("debt_save"),
            command=self._save_data,
        ).pack(side="right", padx=(0, 8))

        # Add/Edit/Delete buttons in the footer
        ttk.Button(
            footer_frame,
            text=self.app._t("debt_delete"),
            command=self._on_delete,
        ).pack(side="left", padx=(0, 8))

        ttk.Button(
            footer_frame,
            text=self.app._t("debt_edit"),
            command=self._on_edit,
        ).pack(side="left", padx=(0, 8))

        ttk.Button(
            footer_frame,
            text=self.app._t("debt_add"),
            command=self._on_add,
        ).pack(side="left")

    def _build_technical_tab(self) -> None:
        columns = ("alias", "label", "date_creation", "date_resolution", "accepted_solution", "target_solution")
        self.technical_tree = ttk.Treeview(self.technical_tab, columns=columns, show="headings")
        
        self.technical_tree.heading("alias", text="Alias")
        for col in columns[1:]:
            self.technical_tree.heading(col, text=self.app._t(f"debt_column_{col}"))
        
        self.technical_tree.column("alias", width=120)
        self.technical_tree.column("label", width=180)
        self.technical_tree.column("date_creation", width=100)
        self.technical_tree.column("date_resolution", width=100)
        self.technical_tree.column("accepted_solution", width=250)
        self.technical_tree.column("target_solution", width=250)
        
        scrollbar = ttk.Scrollbar(self.technical_tab, orient="vertical", command=self.technical_tree.yview)
        self.technical_tree.configure(yscrollcommand=scrollbar.set)
        
        self.technical_tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        self.technical_tree.bind("<Double-1>", lambda e: self._on_edit())

    def _build_deviations_tab(self) -> None:
        columns = ("alias", "label", "date_creation", "explanation")
        self.deviations_tree = ttk.Treeview(self.deviations_tab, columns=columns, show="headings")
        
        self.deviations_tree.heading("alias", text="Alias")
        for col in columns[1:]:
            self.deviations_tree.heading(col, text=self.app._t(f"debt_column_{col}"))
        
        self.deviations_tree.column("alias", width=150)
        self.deviations_tree.column("label", width=200)
        self.deviations_tree.column("date_creation", width=100)
        self.deviations_tree.column("explanation", width=450)
        
        scrollbar = ttk.Scrollbar(self.deviations_tab, orient="vertical", command=self.deviations_tree.yview)
        self.deviations_tree.configure(yscrollcommand=scrollbar.set)
        
        self.deviations_tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        self.deviations_tree.bind("<Double-1>", lambda e: self._on_edit())

    def _load_data(self) -> None:
        path = Path(self.current_file.get())
        if not path.exists():
            self.full_data = {}
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                self.full_data = json.load(f)
            
            self.technical_items.clear()
            self.deviations_items.clear()
            
            for alias, data in self.full_data.items():
                for item in data.get("technical_debt", []):
                    self.technical_items.append((alias, item))
                for item in data.get("deviations", []):
                    self.deviations_items.append((alias, item))
            
            # Update filter dropdown
            aliases = [self.app._t("debt_all_aliases")] + sorted(list(self.full_data.keys()))
            self.filter_combo["values"] = aliases
            
            self._refresh_trees()
        except Exception as e:
            messagebox.showerror(self.app._t("error_title"), f"{self.app._t('debt_load_error')}\n{e}")

    def _refresh_trees(self) -> None:
        filter_alias = self.filter_alias_var.get()
        all_aliases = self.app._t("debt_all_aliases")
        
        self.technical_tree.delete(*self.technical_tree.get_children())
        for alias, item in self.technical_items:
            if filter_alias == all_aliases or alias == filter_alias:
                self.technical_tree.insert("", "end", values=(
                    alias,
                    item.get("label", ""),
                    item.get("date_creation", ""),
                    item.get("date_resolution", ""),
                    item.get("accepted_solution", ""),
                    item.get("target_solution", "")
                ))
            
        self.deviations_tree.delete(*self.deviations_tree.get_children())
        for alias, item in self.deviations_items:
            if filter_alias == all_aliases or alias == filter_alias:
                self.deviations_tree.insert("", "end", values=(
                    alias,
                    item.get("label", ""),
                    item.get("date_creation", ""),
                    item.get("explanation", "")
                ))

    def _on_add(self) -> None:
        filter_alias = self.filter_alias_var.get()
        all_aliases = self.app._t("debt_all_aliases")
        default_alias = filter_alias if filter_alias != all_aliases else None
        
        if self.notebook.index("current") == 0:
            fields = ["alias", "label", "date_creation", "date_resolution", "accepted_solution", "target_solution"]
            initial = {"alias": default_alias} if default_alias else None
            self._edit_dialog(fields, initial, self._add_technical)
        else:
            fields = ["alias", "label", "date_creation", "explanation"]
            initial = {"alias": default_alias} if default_alias else None
            self._edit_dialog(fields, initial, self._add_deviation)

    def _add_technical(self, alias: str, values: Dict[str, str]) -> None:
        self.technical_items.append((alias, values))
        self._refresh_trees()

    def _add_deviation(self, alias: str, values: Dict[str, str]) -> None:
        self.deviations_items.append((alias, values))
        self._refresh_trees()

    def _on_edit(self) -> None:
        is_tech = self.notebook.index("current") == 0
        tree = self.technical_tree if is_tech else self.deviations_tree
        selected = tree.selection()
        if not selected:
            return
        
        item_id = selected[0]
        old_values = tree.item(item_id)["values"]
        
        # Find the correct item in the flat list
        if is_tech:
            fields = ["alias", "label", "date_creation", "date_resolution", "accepted_solution", "target_solution"]
            idx = -1
            for i, (al, item) in enumerate(self.technical_items):
                if (al == old_values[0] and item.get("label") == old_values[1] and 
                    item.get("date_creation") == old_values[2]):
                    idx = i
                    break
            
            def on_save(new_alias, new_vals):
                self.technical_items[idx] = (new_alias, new_vals)
                self._refresh_trees()
        else:
            fields = ["alias", "label", "date_creation", "explanation"]
            idx = -1
            for i, (al, item) in enumerate(self.deviations_items):
                if (al == old_values[0] and item.get("label") == old_values[1] and 
                    item.get("date_creation") == old_values[2]):
                    idx = i
                    break
                    
            def on_save(new_alias, new_vals):
                self.deviations_items[idx] = (new_alias, new_vals)
                self._refresh_trees()
                
        initial_values = {fields[i]: old_values[i] for i in range(len(fields))}
        self._edit_dialog(fields, initial_values, on_save)

    def _on_delete(self) -> None:
        is_tech = self.notebook.index("current") == 0
        tree = self.technical_tree if is_tech else self.deviations_tree
        selected = tree.selection()
        if not selected:
            return
            
        if messagebox.askyesno(self.app._t("info_title"), self.app._t("debt_confirm_delete")):
            for item_id in reversed(selected):
                old_values = tree.item(item_id)["values"]
                if is_tech:
                    self.technical_items = [
                        (al, it) for al, it in self.technical_items 
                        if not (al == old_values[0] and it.get("label") == old_values[1] and it.get("date_creation") == old_values[2])
                    ]
                else:
                    self.deviations_items = [
                        (al, it) for al, it in self.deviations_items 
                        if not (al == old_values[0] and it.get("label") == old_values[1] and it.get("date_creation") == old_values[2])
                    ]
                tree.delete(item_id)

    def _edit_dialog(self, fields: List[str], initial_values: Dict[str, str] | None, on_save: callable) -> None:
        dialog = tk.Toplevel(self.window)
        dialog.title(self.app._t("debt_add") if not initial_values else self.app._t("debt_edit"))
        dialog.geometry("600x600")
        self.app._configure_secondary_window(dialog)
        
        entries = {}
        for i, field in enumerate(fields):
            label_text = "Alias" if field == "alias" else self.app._t(f"debt_column_{field}")
            ttk.Label(dialog, text=label_text).grid(row=i, column=0, padx=10, pady=10, sticky="nw")
            val = initial_values.get(field, "") if initial_values else ""
            
            if field == "alias":
                aliases = sorted([org.alias for org in self.app.orgs if org.alias])
                if not aliases:
                    aliases = [self.app.alias_var.get() or "Default"]
                var = tk.StringVar(value=val or aliases[0])
                combo = ttk.Combobox(dialog, textvariable=var, values=aliases, state="readonly", width=37)
                combo.grid(row=i, column=1, padx=10, pady=10, sticky="ew")
                entries[field] = var
            elif field in ("accepted_solution", "target_solution", "explanation"):
                container = ttk.Frame(dialog)
                container.grid(row=i, column=1, padx=10, pady=10, sticky="ew")
                
                txt = tk.Text(container, height=6, width=50)
                txt.insert("1.0", val)
                txt.pack(fill="both", expand=True)
                
                if self.app.ai_provider_var.get() == "Gateway" and self.app.gateway_api_key_var.get().strip():
                    def expand(t=txt):
                        self.app.ai_expand_text(t.get("1.0", "end-1c").strip(), lambda new_val: [t.delete("1.0", "end"), t.insert("1.0", new_val)])

                    btn = ttk.Button(container, text=self.app._t("ai_expand_button"), command=expand)
                    btn.pack(side="right", pady=(2, 0))
                
                entries[field] = txt
            else:
                var = tk.StringVar(value=val)
                ent = ttk.Entry(dialog, textvariable=var, width=50)
                ent.grid(row=i, column=1, padx=10, pady=10, sticky="ew")
                entries[field] = var
        
        def save(event=None):
            alias = entries["alias"].get()
            result = {}
            for f in fields:
                if f == "alias": continue
                if f in ("accepted_solution", "target_solution", "explanation"):
                    result[f] = entries[f].get("1.0", "end-1c").strip()
                else:
                    result[f] = entries[f].get().strip()
            on_save(alias, result)
            dialog.destroy()
            
        ttk.Button(dialog, text=self.app._t("configuration_save"), command=save).grid(row=len(fields), column=1, pady=20)
        # Note: we don't bind <Return> to save here because we have multiline text fields
        dialog.columnconfigure(1, weight=1)

    def _save_data(self) -> None:
        path = Path(self.current_file.get())
        
        # Rebuild full_data from flat lists
        new_full_data = {}
        
        for alias, item in self.technical_items:
            if alias not in new_full_data:
                new_full_data[alias] = {"technical_debt": [], "deviations": []}
            new_full_data[alias]["technical_debt"].append(item)
            
        for alias, item in self.deviations_items:
            if alias not in new_full_data:
                new_full_data[alias] = {"technical_debt": [], "deviations": []}
            new_full_data[alias]["deviations"].append(item)
        
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(new_full_data, f, indent=2, ensure_ascii=False)
            self.full_data = new_full_data
            messagebox.showinfo(self.app._t("info_title"), self.app._t("debt_saved"))
        except Exception as e:
            messagebox.showerror(self.app._t("error_title"), f"{self.app._t('debt_save_error')}\n{e}")
