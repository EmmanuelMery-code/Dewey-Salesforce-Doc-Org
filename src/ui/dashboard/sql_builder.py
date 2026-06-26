import tkinter as tk
from tkinter import ttk
import sqlite3
from typing import Any

def open_query_builder(window, app, service, target_var: tk.StringVar):
    """Ouvre la fenêtre du Query Builder."""
    qb = tk.Toplevel(window)
    qb.title(app._t("qb_title"))
    qb.geometry("800x600")
    app._configure_secondary_window(qb)
    
    main_f = ttk.Frame(qb, padding=10)
    main_f.pack(fill="both", expand=True)
    
    # Templates (Gauche)
    tpl_f = ttk.LabelFrame(main_f, text=app._t("qb_templates"), padding=5)
    tpl_f.pack(side="left", fill="both", expand=True)
    tpl_list = tk.Listbox(tpl_f, font=("Segoe UI", 9))
    tpl_list.pack(fill="both", expand=True)
    for name in service.QUERY_TEMPLATES:
        tpl_list.insert("end", name)
    
    # Colonnes (Milieu)
    col_f = ttk.LabelFrame(main_f, text=app._t("qb_columns"), padding=5)
    col_f.pack(side="left", fill="both", expand=True, padx=10)
    col_list = tk.Listbox(col_f, selectmode="multiple", font=("Segoe UI", 9))
    col_list.pack(fill="both", expand=True)
    try:
        with sqlite3.connect(service.db_path) as conn:
            for col in conn.execute("PRAGMA table_info(history)").fetchall():
                col_list.insert("end", col[1])
    except:
        pass

    # Preview (Bas)
    prev_v = tk.StringVar(value=target_var.get())
    prev_e = ttk.Entry(qb, textvariable=prev_v, font=("Consolas", 10))
    prev_e.pack(fill="x", padx=10, pady=5)

    def apply_tpl(_e=None):
        sel = tpl_list.curselection()
        if sel:
            name = tpl_list.get(sel[0])
            prev_v.set(service.QUERY_TEMPLATES[name])

    def build_query():
        sel = col_list.curselection()
        if sel:
            cols = [col_list.get(i) for i in sel]
            prev_v.set(f"SELECT {', '.join(cols)} FROM history WHERE alias = :alias ORDER BY timestamp DESC LIMIT 1")

    tpl_list.bind("<<ListboxSelect>>", apply_tpl)
    ttk.Button(col_f, text=app._t("qb_generate_select"), command=build_query).pack(fill="x")
    
    btn_f = ttk.Frame(qb, padding=10)
    btn_f.pack(fill="x")
    ttk.Button(btn_f, text=app._t("qb_use_query"), 
               command=lambda: [target_var.set(prev_v.get()), qb.destroy()]).pack(side="right")
