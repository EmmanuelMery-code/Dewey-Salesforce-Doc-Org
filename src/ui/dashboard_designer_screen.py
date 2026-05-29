from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext, colorchooser
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Any, Optional
import uuid
import json
from dataclasses import dataclass, field, asdict

from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt
from src.core.dashboard_service import DashboardService, DashboardWidget, DashboardConfig
from src.reporting.dashboard_exporter import DashboardExporter
from src.ui.scrollable_window import build_scrollable_window
from src.parsers.salesforce_parser import SalesforceMetadataParser

if TYPE_CHECKING:
    from src.ui.application import Application

def show_dashboard_designer_screen(app: Application) -> None:
    """Affiche la fenêtre de conception avancée avec interaction souris et Query Builder."""
    
    window = tk.Toplevel(app)
    window.title("Studio de Dashboard Salesforce")
    window.geometry("1400x950")
    app._configure_secondary_window(window)

    service = DashboardService(app.latest_snapshot)
    exporter = DashboardExporter(log_callback=app.task_manager.queue_log)
    
    # État local
    saved_configs = service.load_configs()
    current_config_name = tk.StringVar(value="Nouveau Dashboard")
    widgets: List[DashboardWidget] = []
    preview_canvas: Optional[FigureCanvasTkAgg] = None
    widget_ui_elements = []
    
    def load_from_source():
        # Fenêtre de choix : Dossier ou Alias
        choice_win = tk.Toplevel(window)
        choice_win.title("Choisir la source")
        choice_win.geometry("400x300")
        app._configure_secondary_window(choice_win)
        
        ttk.Label(choice_win, text="Comment voulez-vous charger les données ?", font=("Segoe UI", 10, "bold")).pack(pady=20)
        
        def from_folder():
            choice_win.destroy()
            folder = filedialog.askdirectory(title="Sélectionner le dossier source (metadata)")
            if not folder: return
            try:
                parser = SalesforceMetadataParser(folder)
                app.latest_snapshot = parser.parse()
                window.destroy(); show_dashboard_designer_screen(app)
            except Exception as e: messagebox.showerror("Erreur", str(e))

        def from_alias():
            choice_win.destroy()
            alias_win = tk.Toplevel(window)
            alias_win.title("Sélectionner un Alias Salesforce")
            alias_win.geometry("500x400")
            app._configure_secondary_window(alias_win)
            
            ttk.Label(alias_win, text="Sélectionnez une organisation connectée :", font=("Segoe UI", 10)).pack(pady=10)
            
            lb = tk.Listbox(alias_win, font=("Segoe UI", 9))
            lb.pack(fill="both", expand=True, padx=10, pady=10)
            
            orgs = app.cli_service.list_orgs()
            for org in orgs:
                lb.insert("end", f"{org.alias or '(sans alias)'} - {org.username}")

            def confirm_alias():
                sel = lb.curselection()
                if sel:
                    alias_name = orgs[sel[0]].alias or orgs[sel[0]].username
                    app.alias_var.set(alias_name)
                    # On ne charge pas de snapshot ici, on bascule sur le mode SQL History
                    app.latest_snapshot = None # Forcer le mode SQL
                    alias_win.destroy()
                    window.destroy(); show_dashboard_designer_screen(app)

            ttk.Button(alias_win, text="Utiliser cet Alias (Mode Historique)", command=confirm_alias).pack(pady=10)

        ttk.Button(choice_win, text="📂 Dossier de métadonnées (Snapshot)", command=from_folder).pack(fill="x", padx=50, pady=5)
        ttk.Button(choice_win, text="☁️ Alias Salesforce (Historique SQL)", command=from_alias).pack(fill="x", padx=50, pady=5)

    # --- Structure ---
    footer = ttk.Frame(window, padding=(16, 8, 16, 12)); footer.pack(side="bottom", fill="x")
    paned = tk.PanedWindow(window, orient="horizontal", sashrelief="raised", sashwidth=4)
    paned.pack(fill="both", expand=True)
    left_panel = ttk.Frame(paned, padding=10); right_panel = ttk.Frame(paned, padding=10)
    paned.add(left_panel, width=550); paned.add(right_panel)

    # --- GAUCHE : Source & Configs ---
    source_frame = ttk.LabelFrame(left_panel, text="Données & Modèles", padding=10); source_frame.pack(fill="x", pady=(0, 10))
    alias = app.alias_var.get() or "Inconnu"
    ttk.Label(source_frame, text=f"Org : {alias}", font=("Segoe UI", 10, "bold")).pack(side="left")
    s_btns = ttk.Frame(source_frame); s_btns.pack(side="right")
    ttk.Button(s_btns, text="Source", command=load_from_source).pack(side="left", padx=2)

    mgmt_frame = ttk.LabelFrame(left_panel, text="Gestion des Dashboards", padding=10); mgmt_frame.pack(fill="x", pady=(0, 10))
    config_list = ttk.Combobox(mgmt_frame, values=list(saved_configs.keys()), state="readonly"); config_list.pack(fill="x", pady=2)
    def load_selected_config(_e=None):
        name = config_list.get()
        if name in saved_configs:
            current_config_name.set(name); nonlocal widgets
            widgets = [DashboardWidget(**asdict(w)) for w in saved_configs[name].widgets]
            refresh_widget_list(); update_preview()
    config_list.bind("<<ComboboxSelected>>", load_selected_config)
    
    row_cfg = ttk.Frame(mgmt_frame); row_cfg.pack(fill="x", pady=5)
    ttk.Entry(row_cfg, textvariable=current_config_name).pack(side="left", fill="x", expand=True)
    ttk.Button(row_cfg, text="Sauvegarder", command=lambda: [sync_widgets_from_ui(), saved_configs.update({current_config_name.get(): DashboardConfig(name=current_config_name.get(), widgets=widgets)}), service.save_configs(saved_configs), config_list.configure(values=list(saved_configs.keys())), messagebox.showinfo("OK", "Sauvegardé")]).pack(side="right", padx=5)

    # --- GAUCHE : Liste Widgets ---
    list_header = ttk.Frame(left_panel); list_header.pack(fill="x", pady=(10, 5))
    ttk.Label(list_header, text="Composants", font=("Segoe UI", 11, "bold")).pack(side="left")
    def add_widget():
        ny = max([w.y + w.h for w in widgets] + [0])
        widgets.append(DashboardWidget(id=str(uuid.uuid4())[:8], label="Nouveau", chart_type="bar", description="", x=0, y=ny, w=2, h=1))
        refresh_widget_list(); update_preview()
    ttk.Button(list_header, text="+ Ajouter", command=add_widget).pack(side="right")

    w_container = ttk.Frame(left_panel); w_container.pack(fill="both", expand=True)
    w_canvas = tk.Canvas(w_container, highlightthickness=0); w_scrollbar = ttk.Scrollbar(w_container, orient="vertical", command=w_canvas.yview)
    w_list_inner = ttk.Frame(w_canvas); w_list_inner.bind("<Configure>", lambda e: w_canvas.configure(scrollregion=w_canvas.bbox("all")))
    w_canvas.create_window((0, 0), window=w_list_inner, anchor="nw", width=500); w_canvas.configure(yscrollcommand=w_scrollbar.set)
    w_canvas.pack(side="left", fill="both", expand=True); w_scrollbar.pack(side="right", fill="y")

    def open_query_builder(target_var: tk.StringVar):
        qb = tk.Toplevel(window); qb.title("Query Builder & Templates"); qb.geometry("800x600")
        app._configure_secondary_window(qb)
        
        main_f = ttk.Frame(qb, padding=10); main_f.pack(fill="both", expand=True)
        
        # Templates (Gauche)
        tpl_f = ttk.LabelFrame(main_f, text="Requêtes Modèles", padding=5); tpl_f.pack(side="left", fill="both", expand=True)
        tpl_list = tk.Listbox(tpl_f, font=("Segoe UI", 9))
        tpl_list.pack(fill="both", expand=True)
        for name in service.QUERY_TEMPLATES: tpl_list.insert("end", name)
        
        # Colonnes (Milieu)
        col_f = ttk.LabelFrame(main_f, text="Colonnes (Table History)", padding=5); col_f.pack(side="left", fill="both", expand=True, padx=10)
        col_list = tk.Listbox(col_f, selectmode="multiple", font=("Segoe UI", 9))
        col_list.pack(fill="both", expand=True)
        try:
            import sqlite3
            with sqlite3.connect(service.db_path) as conn:
                for col in conn.execute("PRAGMA table_info(history)").fetchall(): col_list.insert("end", col[1])
        except: pass

        # Preview (Bas)
        prev_v = tk.StringVar(value=target_var.get())
        prev_e = ttk.Entry(qb, textvariable=prev_v, font=("Consolas", 10)); prev_e.pack(fill="x", padx=10, pady=5)

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
        ttk.Button(col_f, text="Générer SELECT", command=build_query).pack(fill="x")
        
        btn_f = ttk.Frame(qb, padding=10); btn_f.pack(fill="x")
        ttk.Button(btn_f, text="Utiliser cette requête", command=lambda: [target_var.set(prev_v.get()), qb.destroy()]).pack(side="right")

    def refresh_widget_list():
        for child in w_list_inner.winfo_children(): child.destroy()
        widget_ui_elements.clear()
        for i, w in enumerate(widgets):
            f = ttk.LabelFrame(w_list_inner, text=f"Widget #{i+1} - {w.label}", padding=5); f.pack(fill="x", pady=5, padx=5)
            row1 = ttk.Frame(f); row1.pack(fill="x")
            t_var = tk.StringVar(value=w.label); ttk.Entry(row1, textvariable=t_var, width=20).pack(side="left")
            type_var = tk.StringVar(value=w.chart_type)
            type_cb = ttk.Combobox(row1, textvariable=type_var, values=["bar", "pie", "donut", "line", "area", "stacked_bar", "kpi", "text"], width=9, state="readonly")
            type_cb.pack(side="left", padx=5)
            c_var = tk.StringVar(value=w.color); ttk.Entry(row1, textvariable=c_var, width=12).pack(side="left")
            
            def pick_color(var=c_var):
                color = colorchooser.askcolor(title="Choisir une couleur")[1]
                if color:
                    choice_win = tk.Toplevel(window)
                    choice_win.title("Action couleur")
                    choice_win.geometry("300x150")
                    app._configure_secondary_window(choice_win)
                    ttk.Label(choice_win, text=f"Couleur : {color}").pack(pady=10)
                    bf = ttk.Frame(choice_win); bf.pack(pady=10)
                    ttk.Button(bf, text="Remplacer", command=lambda: [var.set(color), choice_win.destroy(), update_preview()]).pack(side="left", padx=5)
                    ttk.Button(bf, text="Ajouter", command=lambda: [var.set(f"{var.get()},{color}" if var.get() else color), choice_win.destroy(), update_preview()]).pack(side="left", padx=5)

            ttk.Button(row1, text="🎨", width=3, command=pick_color).pack(side="left", padx=2)
            ttk.Button(row1, text="X", width=2, command=lambda idx=i: [widgets.pop(idx), refresh_widget_list(), update_preview()]).pack(side="right")
            
            row2 = ttk.Frame(f); row2.pack(fill="x", pady=5)
            xv, yv, wv, hv = tk.StringVar(value=str(w.x)), tk.StringVar(value=str(w.y)), tk.StringVar(value=str(w.w)), tk.StringVar(value=str(w.h))
            for lbl, var in [("X:", xv), (" Y:", yv), (" W:", wv), (" H:", hv)]:
                ttk.Label(row2, text=lbl).pack(side="left"); ttk.Entry(row2, textvariable=var, width=3).pack(side="left", padx=2)
            
            q_var = tk.StringVar(value=w.query); q_row = ttk.Frame(f); q_row.pack(fill="x")
            sql_e = ttk.Entry(q_row, textvariable=q_var, font=("Consolas", 8))
            sql_e.pack(side="left", fill="x", expand=True)
            ttk.Button(q_row, text="SQL Builder", command=lambda v=q_var: open_query_builder(v)).pack(side="right", padx=2)
            
            # Toolbar Rich Text
            rt_tools = ttk.Frame(f)
            ta = tk.Text(f, height=4, font=("Segoe UI", 10), undo=True)
            ta.insert("1.0", w.text)
            
            def make_bold():
                try: ta.tag_add("bold", "sel.first", "sel.last")
                except: pass
            def make_italic():
                try: ta.tag_add("italic", "sel.first", "sel.last")
                except: pass
            
            ta.tag_configure("bold", font=("Segoe UI", 10, "bold"))
            ta.tag_configure("italic", font=("Segoe UI", 10, "italic"))
            
            ttk.Button(rt_tools, text="B", width=3, command=make_bold).pack(side="left")
            ttk.Button(rt_tools, text="I", width=3, command=make_italic).pack(side="left", padx=2)

            def toggle_input(_e=None, tv=type_var, se=sql_e, t=ta, rtt=rt_tools):
                if tv.get() == "text":
                    se.pack_forget(); rtt.pack(fill="x"); t.pack(fill="x")
                else:
                    t.pack_forget(); rtt.pack_forget(); se.pack(fill="x")
            
            type_cb.bind("<<ComboboxSelected>>", toggle_input)
            toggle_input()
            
            widget_ui_elements.append({"widget": w, "title_var": t_var, "type_var": type_var, "color_var": c_var, "x_var": xv, "y_var": yv, "w_var": wv, "h_var": hv, "query_var": q_var, "text_area": ta})

    def sync_widgets_from_ui():
        for el in widget_ui_elements:
            w = el["widget"]; w.label, w.chart_type, w.color = el["title_var"].get(), el["type_var"].get(), el["color_var"].get()
            try: w.x, w.y, w.w, w.h = int(el["x_var"].get()), int(el["y_var"].get()), int(el["w_var"].get()), int(el["h_var"].get())
            except: pass
            w.query, w.text = el["query_var"].get(), el["text_area"].get("1.0", "end-1c")

    # --- DROITE : Aperçu ---
    preview_header = ttk.Frame(right_panel); preview_header.pack(fill="x", pady=(0, 5))
    ttk.Label(preview_header, text="Aperçu du Dashboard", font=("Segoe UI", 11, "bold")).pack(side="left")
    ttk.Button(preview_header, text="🔄 Rafraîchir", command=lambda: update_preview()).pack(side="right")
    
    preview_container = ttk.Frame(right_panel, relief="sunken", borderwidth=1); preview_container.pack(fill="both", expand=True, pady=5)

    def update_preview():
        nonlocal preview_canvas
        if preview_canvas: preview_canvas.get_tk_widget().destroy()
        sync_widgets_from_ui(); alias = app.alias_var.get() or ""
        data_to_render = []
        for w in widgets:
            data_to_render.append({"title": w.label, "type": w.chart_type, "color": w.color, "x": w.x, "y": w.y, "w": w.w, "h": w.h, "text": w.text, "data": service.get_widget_data(w, alias=alias)})
        if not data_to_render: return
        fig = generate_layout_figure(data_to_render)
        preview_canvas = FigureCanvasTkAgg(fig, master=preview_container)
        preview_canvas.draw(); preview_canvas.get_tk_widget().pack(fill="both", expand=True)

    # --- FOOTER ---
    export_fmt_var = tk.StringVar(value="pptx")
    for text, fmt in [("PowerPoint", "pptx"), ("PDF", "pdf"), ("PNG", "png"), ("Excel", "xlsx")]:
        ttk.Radiobutton(footer, text=text, value=fmt, variable=export_fmt_var).pack(side="left", padx=5)
    def run_export():
        sync_widgets_from_ui(); alias = app.alias_var.get() or ""; fmt = export_fmt_var.get()
        data_to_render = []
        for w in widgets: data_to_render.append({"title": w.label, "type": w.chart_type, "color": w.color, "x": w.x, "y": w.y, "w": w.w, "h": w.h, "text": w.text, "data": service.get_widget_data(w, alias=alias)})
        
        ftypes = {
            "pptx": [("PowerPoint", "*.pptx")],
            "pdf": [("PDF", "*.pdf")],
            "png": [("Image PNG", "*.png")],
            "xlsx": [("Excel", "*.xlsx")]
        }
        file_path = filedialog.asksaveasfilename(defaultextension=f".{fmt}", filetypes=ftypes.get(fmt, [("Tous les fichiers", "*.*")]))
        if file_path:
            if fmt == "pptx": exporter.export_to_pptx(data_to_render, Path(file_path), title=current_config_name.get())
            elif fmt == "xlsx": exporter.export_data(data_to_render, Path(file_path), format='excel')
            else:
                fig = generate_layout_figure(data_to_render)
                if fmt == "pdf": exporter.export_to_pdf(fig, Path(file_path))
                else: exporter.export_to_png(fig, Path(file_path))
                plt.close(fig)
            messagebox.showinfo("Succès", "Export terminé.")
    ttk.Button(footer, text="Générer l'export", command=run_export).pack(side="right", padx=10)
    ttk.Button(footer, text="Fermer", command=window.destroy).pack(side="right")

    if not widgets: widgets = service._init_default_widgets()
    refresh_widget_list(); window.after(500, update_preview)

def generate_layout_figure(widgets_data: List[Dict[str, Any]]) -> Figure:
    if not widgets_data: return Figure()
    mx, my = max(1, max(w['x'] + w['w'] for w in widgets_data)), max(1, max(w['y'] + w['h'] for w in widgets_data))
    fig = Figure(figsize=(10, 3.5 * my), dpi=90, layout='constrained')
    from matplotlib.gridspec import GridSpec
    gs = GridSpec(my, mx, figure=fig)
    for w in widgets_data:
        try:
            ax = fig.add_subplot(gs[w['y']:w['y']+w['h'], w['x']:w['x']+w['w']])
            t, wt, d, c = w['title'], w['type'], w['data'], w.get('color', '#3498db')
            if wt == "text":
                ax.axis('off'); ax.text(0.05, 0.95, w['text'], va='top', ha='left', wrap=True, fontsize=9)
            elif not d:
                ax.text(0.5, 0.5, "Pas de données", ha='center', va='center')
            else:
                if wt == "pie": ax.pie(list(d.values()), labels=list(d.keys()), autopct='%1.1f%%', startangle=140)
                elif wt == "donut": 
                    ax.pie(list(d.values()), labels=list(d.keys()), autopct='%1.1f%%', startangle=140, wedgeprops=dict(width=0.4))
                elif wt == "bar": ax.bar(list(d.keys()), list(d.values()), color=c); ax.tick_params(axis='x', rotation=45, labelsize=7)
                elif wt == "stacked_bar":
                    labels = d.get('labels', [])
                    series = d.get('series', {})
                    bottom = None
                    colors = c.split(',') if ',' in c else [c]
                    for i, (name, vals) in enumerate(series.items()):
                        color = colors[i % len(colors)]
                        ax.bar(labels, vals, bottom=bottom, label=name, color=color)
                        if bottom is None: bottom = [0.0] * len(vals)
                        bottom = [b + v for b, v in zip(bottom, vals)]
                    ax.legend(fontsize=7); ax.tick_params(axis='x', rotation=45, labelsize=7)
                elif wt == "line": ax.plot(list(d.keys()), list(d.values()), marker='o', color=c); ax.tick_params(axis='x', rotation=45, labelsize=7)
                elif wt == "area":
                    ax.fill_between(list(d.keys()), list(d.values()), color=c, alpha=0.3)
                    ax.plot(list(d.keys()), list(d.values()), color=c, marker='.')
                    ax.tick_params(axis='x', rotation=45, labelsize=7)
                elif wt == "kpi":
                    ax.axis('off'); txt = "\n".join([f"{k}: {v}" for k, v in d.items()])
                    ax.text(0.5, 0.5, txt, ha='center', va='center', fontweight='bold', bbox=dict(facecolor='white', alpha=0.2, boxstyle='round'))
            ax.set_title(t, fontsize=10, fontweight='bold')
        except: pass
    return fig
