from __future__ import annotations

import tkinter as tk
import json
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import TYPE_CHECKING, Any, Dict, List

from src.ui import theme

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
        main_frame = ttk.Frame(self.window, padding=theme.SPACE_LG)
        main_frame.pack(fill="both", expand=True)

        # 1. Header (Title + Description)
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill="x", pady=(0, theme.SPACE_MD))
        
        ttk.Label(
            header_frame,
            text=self.app._t('innovation_title'),
            style=theme.TITLE_LABEL,
        ).pack(anchor="w")
        
        ttk.Label(
            header_frame,
            text=self.app._t("innovation_description"),
            wraplength=1000,
            justify="left",
        ).pack(anchor="w", pady=(4, 0))

        # 2. Filter row
        filter_row = ttk.Frame(main_frame)
        filter_row.pack(fill="x", pady=(0, theme.SPACE_MD))
        
        ttk.Label(filter_row, text=self.app._t("innovation_filter_alias")).pack(side="left", padx=(0, theme.SPACE_MD))
        
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

        columns = ("alias", "label", "theme", "not_started", "color", "date_start", "date_end", "date_presentation", "description", "conclusion")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings")
        
        self.tree.heading("alias", text="Alias")
        for col in columns[1:]:
            self.tree.heading(col, text=self.app._t(f"innovation_column_{col}"))
        
        self.tree.column("alias", width=100, anchor="w")
        self.tree.column("label", width=150, anchor="w")
        self.tree.column("theme", width=100, anchor="w")
        self.tree.column("not_started", width=100, anchor="center")
        self.tree.column("color", width=100, anchor="center")
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
        footer_frame = ttk.Frame(main_frame, padding=(0, theme.SPACE_MD, 0, 0))
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
            style=theme.PRIMARY_BUTTON,
        ).pack(side="right", padx=(0, theme.SPACE_SM))

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
        ).pack(side="left", padx=(theme.SPACE_SM, 0))

        ttk.Button(
            footer_frame,
            text=self.app._t("innovation_delete"),
            command=self._on_delete,
            style=theme.DANGER_BUTTON,
        ).pack(side="left", padx=(theme.SPACE_SM, 0))

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
        
        # Configure default alternating row colors (can be overridden by user colors)
        self.tree.tag_configure("oddrow", background="#f2f2f2")
        self.tree.tag_configure("evenrow", background="#ffffff")
        
        display_count = 0
        for alias, item in self.items:
            if filter_alias == all_aliases or alias == filter_alias:
                not_started_val = "X" if item.get("not_started") else ""
                color_key = item.get("color", "")
                color_label = ""
                if color_key:
                    color_label = self.app._t(f"innovation_color_{color_key}")
                
                # Get hex color for background
                bg_color = ""
                if color_key and color_key in self.app.innovation_colors:
                    bg_color = self.app.innovation_colors[color_key]
                
                tags = []
                if bg_color:
                    # User-defined color tag
                    tag_name = f"color_{color_key}"
                    self.tree.tag_configure(tag_name, background=bg_color)
                    tags.append(tag_name)
                else:
                    # Default alternating colors for rows without a specific color
                    tags.append("evenrow" if display_count % 2 == 0 else "oddrow")

                self.tree.insert("", "end", values=(
                    alias,
                    item.get("label", ""),
                    item.get("theme", ""),
                    not_started_val,
                    color_label,
                    item.get("date_start", ""),
                    item.get("date_end", ""),
                    item.get("date_presentation", ""),
                    item.get("description", ""),
                    item.get("conclusion", "")
                ), tags=tuple(tags))
                display_count += 1

    def _on_add(self) -> None:
        filter_alias = self.filter_alias_var.get()
        all_aliases = self.app._t("innovation_all_aliases")
        default_alias = filter_alias if filter_alias != all_aliases else None
        
        fields = ["alias", "label", "theme", "not_started", "color", "date_start", "date_end", "date_presentation", "description", "conclusion"]
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
        
        idx = -1
        for i, (al, item) in enumerate(self.items):
            # We compare alias, label and theme to find the item
            if (str(al) == str(old_values[0]) and 
                str(item.get("label")) == str(old_values[1]) and 
                str(item.get("theme")) == str(old_values[2])):
                idx = i
                break
        
        if idx == -1: return

        def on_save(new_alias, new_vals):
            self.items[idx] = (new_alias, new_vals)
            self._refresh_tree()
        
        alias, item = self.items[idx]
        initial_values = dict(item)
        initial_values["alias"] = alias
            
        fields = ["alias", "label", "theme", "not_started", "color", "date_start", "date_end", "date_presentation", "description", "conclusion"]
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
            ttk.Label(dialog, text=label_text).grid(row=i, column=0, padx=theme.SPACE_MD, pady=theme.SPACE_MD, sticky="nw")
            val = initial_values.get(field, "") if initial_values else ""
            
            if field == "alias":
                aliases = sorted([org.alias for org in self.app.orgs if org.alias])
                if not aliases:
                    aliases = [self.app.alias_var.get() or "Default"]
                var = tk.StringVar(value=val or aliases[0])
                combo = ttk.Combobox(dialog, textvariable=var, values=aliases, state="readonly", width=37)
                combo.grid(row=i, column=1, padx=theme.SPACE_MD, pady=theme.SPACE_MD, sticky="ew")
                entries[field] = var
            elif field == "not_started":
                var = tk.BooleanVar(value=bool(val))
                chk = ttk.Checkbutton(dialog, variable=var)
                chk.grid(row=i, column=1, padx=theme.SPACE_MD, pady=theme.SPACE_MD, sticky="w")
                entries[field] = var
            elif field == "color":
                color_keys = ["", "positive", "neutral", "negative"]
                # Get translated labels with hardcoded fallbacks to ensure the list is never empty
                c_none = self.app._t("innovation_color_none") or "Pas de couleur"
                c_pos = self.app._t("innovation_color_positive") or "Positif (Vert)"
                c_neu = self.app._t("innovation_color_neutral") or "Neutre (Orange)"
                c_neg = self.app._t("innovation_color_negative") or "Négatif (Rouge)"
                
                color_labels = [c_none, c_pos, c_neu, c_neg]
                
                combo = ttk.Combobox(dialog, values=color_labels, state="readonly", width=37)
                combo.grid(row=i, column=1, padx=theme.SPACE_MD, pady=theme.SPACE_MD, sticky="ew")
                
                # Set current selection based on the stored key
                try:
                    if val in color_keys:
                        idx = color_keys.index(val)
                        combo.current(idx)
                    else:
                        combo.current(0)
                except Exception:
                    # Fallback to first item if current() fails
                    if color_labels:
                        combo.current(0)
                
                entries[field] = combo
            elif field in ("description", "conclusion"):
                container = ttk.Frame(dialog)
                container.grid(row=i, column=1, padx=theme.SPACE_MD, pady=theme.SPACE_MD, sticky="ew")
                
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
                ent.grid(row=i, column=1, padx=theme.SPACE_MD, pady=theme.SPACE_MD, sticky="ew")
                entries[field] = var
        
        def save(event=None):
            alias = entries["alias"].get()
            result = {}
            for f in fields:
                if f == "alias": continue
                if f in ("description", "conclusion"):
                    result[f] = entries[f].get("1.0", "end-1c").strip()
                elif f == "not_started":
                    result[f] = entries[f].get()
                elif f == "color":
                    label = entries[f].get()
                    color_keys = ["", "positive", "neutral", "negative"]
                    # Use the same labels as in the UI to ensure a match
                    c_none = self.app._t("innovation_color_none") or "Pas de couleur"
                    c_pos = self.app._t("innovation_color_positive") or "Positif (Vert)"
                    c_neu = self.app._t("innovation_color_neutral") or "Neutre (Orange)"
                    c_neg = self.app._t("innovation_color_negative") or "Négatif (Rouge)"
                    color_labels = [c_none, c_pos, c_neu, c_neg]
                    
                    try:
                        idx = color_labels.index(label)
                        result[f] = color_keys[idx]
                    except (ValueError, IndexError):
                        result[f] = ""
                else:
                    result[f] = entries[f].get().strip()
            on_save(alias, result)
            dialog.destroy()
            
        ttk.Button(dialog, text=self.app._t("configuration_save"), command=save).grid(row=len(fields), column=1, pady=theme.SPACE_XL)
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
