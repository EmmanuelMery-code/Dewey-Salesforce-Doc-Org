from __future__ import annotations

import tkinter as tk
import json
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import TYPE_CHECKING, Any, Dict, List

if TYPE_CHECKING:
    from src.ui.application import Application


def show_innovation_screen(app: Application) -> None:
    """Create and show the POC and innovations management window."""
    InnovationScreen(app)


class InnovationScreen:
    def __init__(self, app: Application) -> None:
        self.app = app
        self.window = tk.Toplevel(app)
        self.window.title(app._t("innovation_title"))
        self.window.geometry("1100x750")
        app._configure_secondary_window(self.window)

        self.current_file = tk.StringVar(value=app.innovation_file_var.get())
        self.filter_alias_var = tk.StringVar(value=app._t("innovation_all_aliases"))
        
        # Data storage: { alias: [...] }
        self.full_data: Dict[str, List[Dict[str, str]]] = {}
        # Flat list for the treeview: list of tuples (alias, item_dict)
        self.items: List[tuple[str, Dict[str, str]]] = []

        self._build_ui()
        if self.current_file.get():
            self._load_data()

    def _build_ui(self) -> None:
        # Main container
        main_frame = ttk.Frame(self.window, padding=16)
        main_frame.pack(fill="both", expand=True)

        # 1. Header (Title + Description)
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill="x", pady=(0, 10))
        
        ttk.Label(
            header_frame,
            text=self.app._t('innovation_title'),
            font=("Segoe UI", 14, "bold"),
        ).pack(anchor="w")
        
        ttk.Label(
            header_frame,
            text=self.app._t("innovation_description"),
            wraplength=1000,
            justify="left",
        ).pack(anchor="w", pady=(4, 0))

        # 2. Filter row
        filter_row = ttk.Frame(main_frame)
        filter_row.pack(fill="x", pady=(0, 10))
        
        ttk.Label(filter_row, text=self.app._t("innovation_filter_alias")).pack(side="left", padx=(0, 10))
        
        self.filter_combo = ttk.Combobox(
            filter_row, 
            textvariable=self.filter_alias_var, 
            state="readonly",
            width=40
        )
        self.filter_combo.pack(side="left")
        self.filter_combo.bind("<<ComboboxSelected>>", lambda e: self._refresh_tree())

        # 3. Treeview container (List + Scrollbar)
        tree_frame = ttk.Frame(main_frame)
        tree_frame.pack(fill="both", expand=True)

        columns = ("alias", "label", "theme", "date_start", "date_end", "date_presentation", "description", "conclusion")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings")
        
        self.tree.heading("alias", text="Alias")
        for col in columns[1:]:
            self.tree.heading(col, text=self.app._t(f"innovation_column_{col}"))
        
        self.tree.column("alias", width=100, anchor="w")
        self.tree.column("label", width=150, anchor="w")
        self.tree.column("theme", width=100, anchor="w")
        self.tree.column("date_start", width=80, anchor="center")
        self.tree.column("date_end", width=80, anchor="center")
        self.tree.column("date_presentation", width=100, anchor="center")
        self.tree.column("description", width=200, anchor="w")
        self.tree.column("conclusion", width=200, anchor="w")
        
        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        self.tree.bind("<Double-1>", lambda e: self._on_edit())
        
        # Context menu
        self.context_menu = tk.Menu(self.window, tearoff=0)
        self.context_menu.add_command(label=self.app._t("innovation_edit"), command=self._on_edit)
        self.context_menu.add_command(label=self.app._t("innovation_delete"), command=self._on_delete)
        self.tree.bind("<Button-3>", self._show_context_menu)

        # 4. Footer buttons (Actions)
        footer_frame = ttk.Frame(main_frame, padding=(0, 12, 0, 0))
        footer_frame.pack(fill="x")
        
        # Right aligned buttons
        ttk.Button(
            footer_frame,
            text=self.app._t("configuration_close"),
            command=self.window.destroy,
        ).pack(side="right")
        
        ttk.Button(
            footer_frame,
            text=self.app._t("innovation_save"),
            command=self._save_data,
        ).pack(side="right", padx=(0, 8))

        # Left aligned buttons
        ttk.Button(
            footer_frame,
            text=self.app._t("innovation_add"),
            command=self._on_add,
        ).pack(side="left")

        ttk.Button(
            footer_frame,
            text=self.app._t("innovation_edit"),
            command=self._on_edit,
        ).pack(side="left", padx=(8, 0))

        ttk.Button(
            footer_frame,
            text=self.app._t("innovation_delete"),
            command=self._on_delete,
        ).pack(side="left", padx=(8, 0))

    def _show_context_menu(self, event) -> None:
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            self.context_menu.post(event.x_root, event.y_root)

    def _load_data(self) -> None:
        path = Path(self.current_file.get())
        if not path.exists():
            self.full_data = {}
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                self.full_data = json.load(f)
            
            self.items.clear()
            for alias, data_list in self.full_data.items():
                for item in data_list:
                    self.items.append((alias, item))
            
            # Update filter dropdown
            aliases = [self.app._t("innovation_all_aliases")] + sorted(list(self.full_data.keys()))
            self.filter_combo["values"] = aliases
            
            self._refresh_tree()
        except Exception as e:
            messagebox.showerror(self.app._t("error_title"), f"{self.app._t('innovation_load_error')}\n{e}")

    def _refresh_tree(self) -> None:
        filter_alias = self.filter_alias_var.get()
        all_aliases = self.app._t("innovation_all_aliases")
        
        self.tree.delete(*self.tree.get_children())
        for alias, item in self.items:
            if filter_alias == all_aliases or alias == filter_alias:
                self.tree.insert("", "end", values=(
                    alias,
                    item.get("label", ""),
                    item.get("theme", ""),
                    item.get("date_start", ""),
                    item.get("date_end", ""),
                    item.get("date_presentation", ""),
                    item.get("description", ""),
                    item.get("conclusion", "")
                ))

    def _on_add(self) -> None:
        filter_alias = self.filter_alias_var.get()
        all_aliases = self.app._t("innovation_all_aliases")
        default_alias = filter_alias if filter_alias != all_aliases else None
        
        fields = ["alias", "label", "theme", "date_start", "date_end", "date_presentation", "description", "conclusion"]
        initial = {"alias": default_alias} if default_alias else None
        self._edit_dialog(fields, initial, self._add_item)

    def _add_item(self, alias: str, values: Dict[str, str]) -> None:
        self.items.append((alias, values))
        self._refresh_tree()

    def _on_edit(self) -> None:
        selected = self.tree.selection()
        if not selected:
            return
        
        item_id = selected[0]
        old_values = self.tree.item(item_id)["values"]
        
        fields = ["alias", "label", "theme", "date_start", "date_end", "date_presentation", "description", "conclusion"]
        idx = -1
        for i, (al, item) in enumerate(self.items):
            if (str(al) == str(old_values[0]) and 
                str(item.get("label")) == str(old_values[1]) and 
                str(item.get("theme")) == str(old_values[2])):
                idx = i
                break
        
        if idx == -1: return

        def on_save(new_alias, new_vals):
            self.items[idx] = (new_alias, new_vals)
            self._refresh_tree()
                
        initial_values = {fields[i]: old_values[i] for i in range(len(fields))}
        self._edit_dialog(fields, initial_values, on_save)

    def _on_delete(self) -> None:
        selected = self.tree.selection()
        if not selected:
            return
            
        if messagebox.askyesno(self.app._t("info_title"), self.app._t("innovation_confirm_delete")):
            for item_id in reversed(selected):
                old_values = self.tree.item(item_id)["values"]
                self.items = [
                    (al, it) for al, it in self.items 
                    if not (str(al) == str(old_values[0]) and 
                           str(it.get("label")) == str(old_values[1]) and 
                           str(it.get("theme")) == str(old_values[2]))
                ]
                self.tree.delete(item_id)

    def _edit_dialog(self, fields: List[str], initial_values: Dict[str, str] | None, on_save: callable) -> None:
        dialog = tk.Toplevel(self.window)
        dialog.title(self.app._t("innovation_add") if not initial_values else self.app._t("innovation_edit"))
        dialog.geometry("600x700")
        self.app._configure_secondary_window(dialog)
        
        entries = {}
        for i, field in enumerate(fields):
            label_text = "Alias" if field == "alias" else self.app._t(f"innovation_column_{field}")
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
            elif field in ("description", "conclusion"):
                container = ttk.Frame(dialog)
                container.grid(row=i, column=1, padx=10, pady=10, sticky="ew")
                
                txt = tk.Text(container, height=6, width=50)
                txt.insert("1.0", val)
                txt.pack(fill="both", expand=True)
                
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
                if f in ("description", "conclusion"):
                    result[f] = entries[f].get("1.0", "end-1c").strip()
                else:
                    result[f] = entries[f].get().strip()
            on_save(alias, result)
            dialog.destroy()
            
        ttk.Button(dialog, text=self.app._t("configuration_save"), command=save).grid(row=len(fields), column=1, pady=20)
        dialog.columnconfigure(1, weight=1)

    def _save_data(self) -> None:
        path = Path(self.current_file.get())
        
        # Rebuild full_data from flat list
        new_full_data = {}
        for alias, item in self.items:
            if alias not in new_full_data:
                new_full_data[alias] = []
            new_full_data[alias].append(item)
        
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(new_full_data, f, indent=2, ensure_ascii=False)
            self.full_data = new_full_data
            messagebox.showinfo(self.app._t("info_title"), self.app._t("innovation_saved"))
        except Exception as e:
            messagebox.showerror(self.app._t("error_title"), f"{self.app._t('innovation_save_error')}\n{e}")
