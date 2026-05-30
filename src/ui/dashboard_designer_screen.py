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

    # Configuration du style Toolbutton pour les boutons d'alignement
    style = ttk.Style(window)
    style.configure("Toolbutton", padding=2)

    # Configuration globale des polices Matplotlib pour supporter les émojis
    try:
        import matplotlib.pyplot as plt
        emoji_fonts = ["Segoe UI Emoji", "Apple Color Emoji", "Noto Color Emoji", "Symbola", "Segoe UI Symbol"]
        current_sans = list(plt.rcParams.get('font.sans-serif', []))
        for f in reversed(emoji_fonts):
            if f not in current_sans:
                current_sans.insert(0, f)
        plt.rcParams['font.sans-serif'] = current_sans
        plt.rcParams['font.family'] = 'sans-serif'
        # Désactiver le rendu mathématique qui force souvent DejaVu Sans
        plt.rcParams['mathtext.fontset'] = 'cm' 
        plt.rcParams['axes.unicode_minus'] = False
    except: pass

    service = DashboardService(app.latest_snapshot)
    saved_configs = service.load_configs()
    current_config_name = tk.StringVar(value="Nouveau Dashboard")
    widgets: List[DashboardWidget] = []
    preview_canvas: Optional[FigureCanvasTkAgg] = None
    widget_ui_elements = []
    
    # État interaction souris
    selected_widget_id: Optional[str] = None
    drag_mode: Optional[str] = None # 'move' or 'resize_nw', 'resize_se', etc.
    drag_start_pos: Optional[tuple[float, float]] = None
    drag_start_widget_state: Optional[dict] = None
    
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
    ttk.Button(row_cfg, text="Sauvegarder", command=lambda: [sync_widgets_from_ui(), saved_configs.update({current_config_name.get(): DashboardConfig(name=current_config_name.get(), widgets=widgets)}), service.save_configs(saved_configs), config_list.configure(values=list(saved_configs.keys())), messagebox.showinfo("OK", "Sauvegardé")]).pack(side="left", padx=5)
    
    def delete_config():
        name = current_config_name.get()
        if name in saved_configs:
            if messagebox.askyesno("Confirmation", f"Voulez-vous vraiment supprimer le dashboard '{name}' ?"):
                del saved_configs[name]
                service.save_configs(saved_configs)
                config_list.configure(values=list(saved_configs.keys()))
                config_list.set("")
                current_config_name.set("Nouveau Dashboard")
                nonlocal widgets
                widgets = []
                refresh_widget_list()
                update_preview()
                messagebox.showinfo("OK", "Supprimé")
        else:
            messagebox.showwarning("Attention", "Ce dashboard n'est pas encore sauvegardé.")

    ttk.Button(row_cfg, text="Supprimer", command=delete_config).pack(side="left", padx=5)

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
            type_cb = ttk.Combobox(row1, textvariable=type_var, values=["bar", "pie", "donut", "line", "area", "stacked_bar", "kpi", "text", "table", "image", "dashboard"], width=9, state="readonly")
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
                    ttk.Button(bf, text="Transparent", command=lambda: [var.set("none"), choice_win.destroy(), update_preview()]).pack(side="left", padx=5)

            ttk.Button(row1, text="🎨", width=3, command=pick_color).pack(side="left", padx=2)
            ttk.Button(row1, text="X", width=2, command=lambda idx=i: [widgets.pop(idx), refresh_widget_list(), update_preview()]).pack(side="right")
            
            row2 = ttk.Frame(f); row2.pack(fill="x", pady=5)
            xv, yv, wv, hv, zv = tk.StringVar(value=str(w.x)), tk.StringVar(value=str(w.y)), tk.StringVar(value=str(w.w)), tk.StringVar(value=str(w.h)), tk.StringVar(value=str(w.z_order))
            for lbl, var in [("X:", xv), (" Y:", yv), (" W:", wv), (" H:", hv), (" Z:", zv)]:
                ttk.Label(row2, text=lbl).pack(side="left"); ttk.Entry(row2, textvariable=var, width=3).pack(side="left", padx=2)
            
            q_var = tk.StringVar(value=w.query); q_row = ttk.Frame(f); q_row.pack(fill="x")
            sql_e = ttk.Entry(q_row, textvariable=q_var, font=("Consolas", 8))
            sql_e.pack(side="left", fill="x", expand=True)
            ttk.Button(q_row, text="SQL Builder", command=lambda v=q_var: open_query_builder(v)).pack(side="right", padx=2)
            
            cond_var = tk.StringVar(value=w.condition); cond_row = ttk.Frame(f); cond_row.pack(fill="x", pady=2)
            ttk.Label(cond_row, text="Condition:").pack(side="left")
            ttk.Entry(cond_row, textvariable=cond_var, font=("Consolas", 8)).pack(side="left", fill="x", expand=True)
            
            # KPI Config
            kpi_tools = ttk.Frame(f)
            kpi_dec_var = tk.StringVar(value=str(w.kpi_decimals))
            ttk.Label(kpi_tools, text="Décimales:").pack(side="left")
            kpi_dec_cb = ttk.Combobox(kpi_tools, textvariable=kpi_dec_var, values=["0", "1", "2", "3"], width=3, state="readonly")
            kpi_dec_cb.pack(side="left", padx=2)
            kpi_dec_cb.bind("<<ComboboxSelected>>", lambda e: update_preview())

            # Dashboard Config (Linked)
            dash_tools = ttk.Frame(f)
            linked_dash_var = tk.StringVar(value=w.linked_dashboard)
            ttk.Label(dash_tools, text="Dashboard à inclure:").pack(side="left")
            linked_dash_cb = ttk.Combobox(dash_tools, textvariable=linked_dash_var, values=list(saved_configs.keys()), width=20, state="readonly")
            linked_dash_cb.pack(side="left", padx=2)
            linked_dash_cb.bind("<<ComboboxSelected>>", lambda e: update_preview())

            # Image Config
            image_tools = ttk.Frame(f)
            img_path_var = tk.StringVar(value=w.image_path)
            emoji_var = tk.StringVar(value=w.emoji)
            img_size_var = tk.StringVar(value=str(w.image_font_size))
            img_color_var = tk.StringVar(value=w.image_font_color)
            
            def browse_image():
                path = filedialog.askopenfilename(title="Choisir une image", filetypes=[("Images", "*.png *.jpg *.jpeg *.gif *.bmp")])
                if path: img_path_var.set(path); update_preview()

            row_i1 = ttk.Frame(image_tools); row_i1.pack(fill="x")
            ttk.Button(row_i1, text="📁 Image", command=browse_image).pack(side="left")
            ttk.Label(row_i1, text=" ou ").pack(side="left")
            
            all_emojis = ["☀️", "⛅", "☁️", "🌧️", "⛈️", "😊", "😐", "☹️", "🚀", "📊", "✅", "❌", "⚠️", "💡", "🔥", "⭐", "🎯", "🏆", "⚙️", "🔒", "🌍"]
            emoji_cb = ttk.Combobox(row_i1, textvariable=emoji_var, values=all_emojis, width=3, state="readonly")
            emoji_cb.pack(side="left", padx=2)
            emoji_cb.bind("<<ComboboxSelected>>", lambda e: [img_path_var.set(""), update_preview()])

            row_i2 = ttk.Frame(image_tools); row_i2.pack(fill="x", pady=2)
            ttk.Label(row_i2, text="Taille:").pack(side="left")
            i_size_cb = ttk.Combobox(row_i2, textvariable=img_size_var, values=["10", "20", "30", "40", "50", "60", "80", "100", "120"], width=4, state="readonly")
            i_size_cb.pack(side="left", padx=2)
            i_size_cb.bind("<<ComboboxSelected>>", lambda e: update_preview())
            
            ttk.Label(row_i2, text=" Couleur:").pack(side="left")
            ttk.Entry(row_i2, textvariable=img_color_var, width=10).pack(side="left", padx=2)
            def pick_img_text_color():
                color = colorchooser.askcolor(title="Couleur de l'icône")[1]
                if color: img_color_var.set(color); update_preview()
            ttk.Button(row_i2, text="🎨", width=3, command=pick_img_text_color).pack(side="left", padx=2)

            # Table Config
            table_tools = ttk.Frame(f)
            cols_var = tk.StringVar(value=",".join(w.table_columns))
            rows_var = tk.StringVar(value=",".join(w.table_rows))
            table_font_var = tk.StringVar(value=w.table_font_name)
            table_size_var = tk.StringVar(value=str(w.table_font_size))

            row_t1 = ttk.Frame(table_tools); row_t1.pack(fill="x")
            ttk.Label(row_t1, text="Colonnes:").pack(side="left")
            ttk.Entry(row_t1, textvariable=cols_var, width=15).pack(side="left", padx=2)
            ttk.Label(row_t1, text=" Lignes:").pack(side="left")
            ttk.Entry(row_t1, textvariable=rows_var, width=15).pack(side="left", padx=2)

            row_t2 = ttk.Frame(table_tools); row_t2.pack(fill="x", pady=2)
            ttk.Label(row_t2, text="Police:").pack(side="left")
            t_font_cb = ttk.Combobox(row_t2, textvariable=table_font_var, values=["Arial", "Segoe UI", "Courier New", "Times New Roman", "Verdana"], width=10, state="readonly")
            t_font_cb.pack(side="left", padx=2)
            t_font_cb.bind("<<ComboboxSelected>>", lambda e: update_preview())
            
            ttk.Label(row_t2, text=" Taille:").pack(side="left")
            t_size_cb = ttk.Combobox(row_t2, textvariable=table_size_var, values=["6", "7", "8", "9", "10", "11", "12", "14"], width=3, state="readonly")
            t_size_cb.pack(side="left", padx=2)
            t_size_cb.bind("<<ComboboxSelected>>", lambda e: update_preview())

            # Toolbar Rich Text
            rt_tools = ttk.Frame(f)
            ta = tk.Text(f, height=4, font=("Arial", 10), undo=True, exportselection=False)
            
            # Configuration des tags
            ta.tag_configure("bold", font=("Arial", 10, "bold"))
            ta.tag_configure("italic", font=("Arial", 10, "italic"))
            ta.tag_configure("underline", underline=True)
            ta.tag_configure("strikeout", overstrike=True)

            def insert_emoji(e, target_ta=ta):
                target_ta.insert("insert", e)
                update_preview()

            def show_emoji_picker(target_ta=ta):
                ep = tk.Toplevel(window)
                ep.title("Émoticônes")
                ep.geometry("500x450")
                app._configure_secondary_window(ep)
                
                canvas = tk.Canvas(ep, highlightthickness=0)
                scrollbar = ttk.Scrollbar(ep, orient="vertical", command=canvas.yview)
                scroll_frame = ttk.Frame(canvas)
                
                scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
                canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
                canvas.configure(yscrollcommand=scrollbar.set)
                
                canvas.pack(side="left", fill="both", expand=True)
                scrollbar.pack(side="right", fill="y")
                
                categories = {
                    "Météo": ["☀️", "🌤️", "⛅", "☁️", "🌦️", "🌧️", "⛈️", "🌩️", "❄️", "💨", "🌊"],
                    "Humeurs": ["😊", "🙂", "😐", "☹️", "😡", "👍", "👎", "👌", "👏", "🙌", "🎯", "🏆", "🚩"],
                    "Business": ["🚀", "📊", "📈", "📉", "💡", "⚙️", "🛠️", "🛡️", "🔒", "🔑", "💻", "📱", "🏢", "☁️", "🌍"],
                    "Symboles": ["✅", "❌", "⚠️", "ℹ️", "🔔", "📌", "📝", "🔍", "⭐", "✨", "🔥", "💎"]
                }
                
                for cat_name, emojis_list in categories.items():
                    cat_f = ttk.LabelFrame(scroll_frame, text=cat_name, padding=5)
                    cat_f.pack(fill="x", padx=10, pady=5)
                    
                    r, c = 0, 0
                    for emo in emojis_list:
                        btn = tk.Button(cat_f, text=emo, font=("Arial", 14), width=3, 
                                       command=lambda e=emo, t=target_ta: [insert_emoji(e, t), ep.destroy()])
                        btn.grid(row=r, column=c, padx=2, pady=2)
                        c += 1
                        if c > 7:
                            c = 0
                            r += 1

            def apply_tag(tag_name, target_ta=ta):
                try:
                    if target_ta.tag_ranges("sel"):
                        first = target_ta.index("sel.first")
                        last = target_ta.index("sel.last")
                        if tag_name in target_ta.tag_names(first):
                            target_ta.tag_remove(tag_name, first, last)
                        else:
                            target_ta.tag_add(tag_name, first, last)
                            target_ta.tag_raise(tag_name)
                        update_preview()
                except: pass

            def pick_text_color(target_ta=ta):
                color = colorchooser.askcolor(title="Couleur du texte")[1]
                if color:
                    tag_id = f"color_{color.replace('#', '')}"
                    target_ta.tag_configure(tag_id, foreground=color)
                    apply_tag(tag_id, target_ta)
                    target_ta.tag_raise(tag_id)

            def change_font(event=None, target_ta=ta, f_cb=None, s_cb=None):
                if not f_cb or not s_cb: return
                f_name = f_cb.get()
                f_size = s_cb.get()
                tag_id = f"font_{f_name}_{f_size}"
                target_ta.tag_configure(tag_id, font=(f_name, int(f_size)))
                apply_tag(tag_id, target_ta)
                target_ta.tag_raise(tag_id)
                update_preview()

            # Toolbar elements
            tk.Button(rt_tools, text="😀", width=3, command=lambda t=ta: show_emoji_picker(t), relief="flat", overrelief="raised", takefocus=False).pack(side="left", padx=(0, 5))
            tk.Button(rt_tools, text="B", width=2, command=lambda t=ta: apply_tag("bold", t), font=("Arial", 8, "bold"), relief="flat", overrelief="raised", takefocus=False).pack(side="left")
            tk.Button(rt_tools, text="I", width=2, command=lambda t=ta: apply_tag("italic", t), font=("Arial", 8, "italic"), relief="flat", overrelief="raised", takefocus=False).pack(side="left", padx=2)
            tk.Button(rt_tools, text="U", width=2, command=lambda t=ta: apply_tag("underline", t), font=("Arial", 8, "underline"), relief="flat", overrelief="raised", takefocus=False).pack(side="left", padx=2)
            tk.Button(rt_tools, text="S", width=2, command=lambda t=ta: apply_tag("strikeout", t), font=("Arial", 8, "overstrike"), relief="flat", overrelief="raised", takefocus=False).pack(side="left", padx=2)
            tk.Button(rt_tools, text="🎨", width=3, command=lambda t=ta: pick_text_color(t), relief="flat", overrelief="raised", takefocus=False).pack(side="left", padx=2)
            
            font_cb = ttk.Combobox(rt_tools, values=["Arial", "Segoe UI", "Courier New", "Times New Roman", "Verdana"], width=10, state="readonly", takefocus=False)
            font_cb.set("Arial")
            font_cb.pack(side="left", padx=2)
            
            size_cb = ttk.Combobox(rt_tools, values=["8", "9", "10", "11", "12", "14", "16", "18", "20", "24"], width=3, state="readonly", takefocus=False)
            size_cb.set("10")
            size_cb.pack(side="left", padx=2)

            def on_font_change(event, t=ta, fc=font_cb, sc=size_cb):
                change_font(event, t, fc, sc)

            font_cb.bind("<<ComboboxSelected>>", on_font_change)
            size_cb.bind("<<ComboboxSelected>>", on_font_change)

            # Alignement horizontal
            align_var = tk.StringVar(value=w.text_align)
            for icon, val in [("L", "left"), ("C", "center"), ("R", "right")]:
                tk.Radiobutton(rt_tools, text=icon, value=val, variable=align_var, indicatoron=0, width=2, command=update_preview, takefocus=False).pack(side="left", padx=1)
            
            # Alignement vertical
            valign_var = tk.StringVar(value=w.text_valign)
            for icon, val in [("T", "top"), ("M", "center"), ("B", "bottom")]:
                tk.Radiobutton(rt_tools, text=icon, value=val, variable=valign_var, indicatoron=0, width=2, command=update_preview, takefocus=False).pack(side="left", padx=1)

            # Chargement du texte riche
            if w.rich_text:
                ta.delete("1.0", "end")
                for i, segment in enumerate(w.rich_text):
                    start = ta.index("end-1c")
                    ta.insert("end", segment["text"])
                    end = ta.index("end-1c")
                    
                    # On crée un tag unique pour ce segment pour éviter les collisions
                    tid = f"seg_{i}"
                    
                    # Préparation de la police
                    fn = segment.get("font", "Arial")
                    fs = segment.get("size", 10)
                    font_tuple = [fn, int(fs)]
                    if segment.get("bold"): font_tuple.append("bold")
                    if segment.get("italic"): font_tuple.append("italic")
                    
                    # Configuration du tag
                    tag_props = {"font": tuple(font_tuple)}
                    if segment.get("color"): tag_props["foreground"] = segment["color"]
                    if segment.get("underline"): tag_props["underline"] = True
                    if segment.get("strikeout"): tag_props["overstrike"] = True
                    
                    ta.tag_configure(tid, **tag_props)
                    ta.tag_add(tid, start, end)
                    
                # On s'assure que les tags de l'interface (boutons) sont au-dessus
                for t in ["bold", "italic", "underline", "strikeout"]:
                    ta.tag_raise(t)
                ta.edit_reset()
            elif w.text:
                ta.delete("1.0", "end")
                ta.insert("1.0", w.text)
                ta.edit_reset()

            def toggle_input(_e=None, tv=type_var, se=sql_e, t=ta, rtt=rt_tools, tt=table_tools, it=image_tools, kt=kpi_tools, dt=dash_tools):
                if tv.get() == "text":
                    se.pack_forget(); tt.pack_forget(); it.pack_forget(); kt.pack_forget(); dt.pack_forget(); rtt.pack(fill="x"); t.pack(fill="x")
                elif tv.get() == "table":
                    t.pack_forget(); rtt.pack_forget(); it.pack_forget(); kt.pack_forget(); dt.pack_forget(); se.pack(fill="x"); tt.pack(fill="x")
                elif tv.get() == "image":
                    t.pack_forget(); rtt.pack_forget(); tt.pack_forget(); kt.pack_forget(); dt.pack_forget(); se.pack_forget(); it.pack(fill="x")
                elif tv.get() == "kpi":
                    t.pack_forget(); rtt.pack_forget(); tt.pack_forget(); it.pack_forget(); dt.pack_forget(); se.pack(fill="x"); kt.pack(fill="x")
                elif tv.get() == "dashboard":
                    t.pack_forget(); rtt.pack_forget(); tt.pack_forget(); it.pack_forget(); kt.pack_forget(); se.pack_forget(); dt.pack(fill="x")
                else:
                    t.pack_forget(); rtt.pack_forget(); tt.pack_forget(); it.pack_forget(); kt.pack_forget(); dt.pack_forget(); se.pack(fill="x")
            
            type_cb.bind("<<ComboboxSelected>>", toggle_input)
            toggle_input()
            
            widget_ui_elements.append({
                "widget": w, 
                "title_var": t_var, 
                "type_var": type_var, 
                "color_var": c_var, 
                "x_var": xv, 
                "y_var": yv, 
                "w_var": wv, 
                "h_var": hv, 
                "z_var": zv,
                "query_var": q_var, 
                "cond_var": cond_var,
                "text_area": ta, 
                "align_var": align_var, 
                "valign_var": valign_var,
                "cols_var": cols_var,
                "rows_var": rows_var,
                "table_font_var": table_font_var,
                "table_size_var": table_size_var,
                "img_path_var": img_path_var,
                "emoji_var": emoji_var,
                "img_size_var": img_size_var,
                "img_color_var": img_color_var,
                "linked_dash_var": linked_dash_var,
                "kpi_dec_var": kpi_dec_var
            })

    def sync_widgets_from_ui():
        for el in widget_ui_elements:
            w = el["widget"];             w.label, w.chart_type, w.color = el["title_var"].get(), el["type_var"].get(), el["color_var"].get()
            try: w.x, w.y, w.w, w.h, w.z_order = int(el["x_var"].get()), int(el["y_var"].get()), int(el["w_var"].get()), int(el["h_var"].get()), int(el["z_var"].get())
            except: pass
            w.query = el["query_var"].get()
            w.condition = el.get("cond_var", tk.StringVar()).get()
            w.text_align = el.get("align_var", tk.StringVar(value="left")).get()
            w.text_valign = el.get("valign_var", tk.StringVar(value="top")).get()
            
            w.table_columns = [c.strip() for c in el.get("cols_var", tk.StringVar()).get().split(",") if c.strip()]
            w.table_rows = [r.strip() for r in el.get("rows_var", tk.StringVar()).get().split(",") if r.strip()]
            w.table_font_name = el.get("table_font_var", tk.StringVar(value="Segoe UI")).get()
            try: w.table_font_size = int(el.get("table_size_var", tk.StringVar(value="8")).get())
            except: w.table_font_size = 8
            
            w.image_path = el.get("img_path_var", tk.StringVar()).get()
            w.emoji = el.get("emoji_var", tk.StringVar()).get()
            try: w.image_font_size = int(el.get("img_size_var", tk.StringVar(value="50")).get())
            except: w.image_font_size = 50
            w.image_font_color = el.get("img_color_var", tk.StringVar(value="#000000")).get()
            w.linked_dashboard = el.get("linked_dash_var", tk.StringVar()).get()

            try: w.kpi_decimals = int(el.get("kpi_dec_var", tk.StringVar(value="1")).get())
            except: w.kpi_decimals = 1

            ta = el["text_area"]
            w.text = ta.get("1.0", "end-1c")
            
            # Sérialisation du texte riche
            rich_segments = []
            current_pos = "1.0"
            while True:
                next_pos = ta.index(f"{current_pos} + 1c")
                if ta.compare(current_pos, "==", "end-1c"): break
                
                char = ta.get(current_pos)
                tags = ta.tag_names(current_pos)
                
                segment = {"text": char}
                
                # On extrait les propriétés de TOUS les tags appliqués
                for t in tags:
                    if t == "bold": segment["bold"] = True
                    elif t == "italic": segment["italic"] = True
                    elif t == "underline": segment["underline"] = True
                    elif t == "strikeout": segment["strikeout"] = True
                    elif t.startswith("color_"): segment["color"] = f"#{t.split('_')[1]}"
                    elif t.startswith("font_"):
                        parts = t.split("_")
                        segment["font"] = parts[1]
                        segment["size"] = int(parts[2])
                    elif t.startswith("seg_"):
                        # Tag de chargement initial : on récupère ses propriétés configurées
                        try:
                            f_val = ta.tag_cget(t, "font")
                            # f_val peut être un tuple ou une chaîne
                            import tkinter.font as tkfont
                            try:
                                # Utiliser tkfont pour analyser la police de manière fiable
                                font_obj = tkfont.Font(font=f_val)
                                segment["font"] = font_obj.actual("family")
                                segment["size"] = font_obj.actual("size")
                                if font_obj.actual("weight") == "bold": segment["bold"] = True
                                if font_obj.actual("slant") == "italic": segment["italic"] = True
                            except:
                                if isinstance(f_val, str):
                                    if 'bold' in f_val: segment["bold"] = True
                                    if 'italic' in f_val: segment["italic"] = True
                                else:
                                    if 'bold' in f_val: segment["bold"] = True
                                    if 'italic' in f_val: segment["italic"] = True
                            
                            c_val = ta.tag_cget(t, "foreground")
                            if c_val: segment["color"] = c_val
                            
                            if ta.tag_cget(t, "underline") == '1': segment["underline"] = True
                            if ta.tag_cget(t, "overstrike") == '1': segment["strikeout"] = True
                        except: pass

                # Optimisation : fusionner avec le segment précédent si même format
                if rich_segments and all(rich_segments[-1].get(k) == segment.get(k) for k in ["bold", "italic", "underline", "strikeout", "color", "font", "size"]):
                    rich_segments[-1]["text"] += char
                else:
                    rich_segments.append(segment)
                
                current_pos = next_pos
            w.rich_text = rich_segments

    # --- DROITE : Aperçu ---
    preview_header = ttk.Frame(right_panel); preview_header.pack(fill="x", pady=(0, 5))
    ttk.Label(preview_header, text="Aperçu du Dashboard", font=("Segoe UI", 11, "bold")).pack(side="left")
    ttk.Button(preview_header, text="🔄 Rafraîchir", command=lambda: update_preview()).pack(side="right")
    
    # Conteneur scrollable pour l'aperçu (multi-pages)
    preview_outer = ttk.Frame(right_panel, relief="sunken", borderwidth=1)
    preview_outer.pack(fill="both", expand=True, pady=5)
    
    preview_canvas_widget = tk.Canvas(preview_outer, highlightthickness=0)
    preview_scrollbar = ttk.Scrollbar(preview_outer, orient="vertical", command=preview_canvas_widget.yview)
    preview_container = ttk.Frame(preview_canvas_widget)
    
    preview_container.bind("<Configure>", lambda e: preview_canvas_widget.configure(scrollregion=preview_canvas_widget.bbox("all")))
    preview_canvas_widget.create_window((0, 0), window=preview_container, anchor="nw", width=800) # Largeur fixe pour l'aperçu
    preview_canvas_widget.configure(yscrollcommand=preview_scrollbar.set)
    
    preview_canvas_widget.pack(side="left", fill="both", expand=True)
    preview_scrollbar.pack(side="right", fill="y")

    # Support du scroll à la souris
    def _on_mousewheel(event):
        preview_canvas_widget.yview_scroll(int(-1*(event.delta/120)), "units")
    preview_canvas_widget.bind_all("<MouseWheel>", _on_mousewheel)

    def update_preview():
        nonlocal preview_canvas
        for child in preview_container.winfo_children(): child.destroy()
        
        sync_widgets_from_ui(); alias = app.alias_var.get() or ""
        
        # On sépare les widgets en "pages"
        # Chaque widget de type 'dashboard' crée une nouvelle page
        # Les autres widgets sont regroupés sur la page principale (page 1)
        pages_data = []
        main_page_widgets = []
        
        for w in widgets:
            if w.chart_type == "dashboard" and w.linked_dashboard in saved_configs:
                # Ajouter la page principale si elle contient des widgets
                if main_page_widgets:
                    pages_data.append({"title": "Page Principale", "widgets": main_page_widgets})
                    main_page_widgets = []
                
                # Charger les widgets du dashboard lié
                linked_widgets = saved_configs[w.linked_dashboard].widgets
                linked_data = []
                for lw in linked_widgets:
                    linked_data.append({
                        "id": lw.id, "title": lw.label, "type": lw.chart_type, "color": lw.color,
                        "x": lw.x, "y": lw.y, "w": lw.w, "h": lw.h, "text": lw.text,
                        "rich_text": lw.rich_text, "text_align": lw.text_align, "text_valign": lw.text_valign,
                        "table_columns": lw.table_columns, "table_rows": lw.table_rows,
                        "table_font_name": lw.table_font_name, "table_font_size": lw.table_font_size,
                        "image_path": lw.image_path, "emoji": lw.emoji, "image_font_size": lw.image_font_size,
                        "image_font_color": lw.image_font_color, "kpi_decimals": lw.kpi_decimals,
                        "z_order": lw.z_order, "data": service.get_widget_data(lw, alias=alias)
                    })
                pages_data.append({"title": f"Page : {w.linked_dashboard}", "widgets": linked_data})
            else:
                main_page_widgets.append({
                    "id": w.id, "title": w.label, "type": w.chart_type, "color": w.color,
                    "x": w.x, "y": w.y, "w": w.w, "h": w.h, "text": w.text,
                    "rich_text": w.rich_text, "text_align": w.text_align, "text_valign": w.text_valign,
                    "table_columns": w.table_columns, "table_rows": w.table_rows,
                    "table_font_name": w.table_font_name, "table_font_size": w.table_font_size,
                    "image_path": w.image_path, "emoji": w.emoji, "image_font_size": w.image_font_size,
                    "image_font_color": w.image_font_color, "kpi_decimals": w.kpi_decimals,
                    "z_order": w.z_order, "data": service.get_widget_data(w, alias=alias)
                })
        
        if main_page_widgets:
            pages_data.append({"title": "Page Principale", "widgets": main_page_widgets})

        if not pages_data: return

        # Rendre chaque page
        for p_info in pages_data:
            ttk.Label(preview_container, text=p_info["title"], font=("Segoe UI", 10, "bold")).pack(pady=(10, 0))
            fig = generate_layout_figure(p_info["widgets"], selected_id=selected_widget_id)
            canvas = FigureCanvasTkAgg(fig, master=preview_container)
            canvas.draw()
            canvas.get_tk_widget().pack(fill="x", expand=True, padx=5, pady=5)
            
            # Note: L'interaction souris (drag/drop) ne fonctionnera que sur la dernière page rendue 
            # si on ne gère pas une liste de canvas. Pour l'instant, on garde la simplicité.
            fig.canvas.mpl_connect('button_press_event', on_click)
            fig.canvas.mpl_connect('motion_notify_event', on_motion)
            fig.canvas.mpl_connect('button_release_event', on_release)

    def on_click(event):
        nonlocal selected_widget_id, drag_mode, drag_start_pos, drag_start_widget_state
        if event.inaxes is None: 
            selected_widget_id = None
            update_preview()
            return

        ax = event.inaxes
        wid = getattr(ax, 'widget_id', None)
        if not wid: return

        selected_widget_id = wid
        drag_start_pos = (event.xdata, event.y_data) if hasattr(event, 'y_data') else (event.xdata, event.ydata)
        
        # Trouver le widget
        w = next((w for w in widgets if w.id == wid), None)
        if not w: return
        
        drag_start_widget_state = {"x": w.x, "y": w.y, "w": w.w, "h": w.h}
        
        # Déterminer si on clique sur une poignée
        # event.xdata/ydata sont en coordonnées axes fraction si on regarde ax.transAxes
        # Mais ici on est en coordonnées de données de l'axe.
        # Utilisons les coordonnées relatives à l'axe (0 à 1)
        inv = ax.transAxes.inverted()
        rel_pos = inv.transform((event.x, event.y))
        rx, ry = rel_pos[0], rel_pos[1]
        
        margin = 0.1
        if rx < margin and ry < margin: drag_mode = "resize_nw"
        elif rx > 1-margin and ry < margin: drag_mode = "resize_sw" # Matplotlib Y est inversé par rapport à l'écran ? Non, 0 est en bas.
        elif rx < margin and ry > 1-margin: drag_mode = "resize_nw" # En fait ry=1 est le haut
        elif rx > 1-margin and ry > 1-margin: drag_mode = "resize_ne"
        # Simplifions : coins et bords
        if rx < margin:
            if ry < margin: drag_mode = "resize_sw"
            elif ry > 1-margin: drag_mode = "resize_nw"
            else: drag_mode = "resize_w"
        elif rx > 1-margin:
            if ry < margin: drag_mode = "resize_se"
            elif ry > 1-margin: drag_mode = "resize_ne"
            else: drag_mode = "resize_e"
        elif ry < margin: drag_mode = "resize_s"
        elif ry > 1-margin: drag_mode = "resize_n"
        else: drag_mode = "move"
        
        update_preview()

    def on_motion(event):
        if not selected_widget_id:
            # Changer le curseur si on survole un widget
            if event.inaxes:
                wid = getattr(event.inaxes, 'widget_id', None)
                if wid: window.config(cursor="hand2")
                else: window.config(cursor="")
            else:
                window.config(cursor="")
            return

        if drag_mode:
            if drag_mode == "move": window.config(cursor="fleur")
            elif "resize" in drag_mode: window.config(cursor="sizing")
            return

        if event.inaxes:
            wid = getattr(event.inaxes, 'widget_id', None)
            if wid == selected_widget_id:
                # Déterminer si on est sur une poignée pour changer le curseur
                ax = event.inaxes
                inv = ax.transAxes.inverted()
                rel_pos = inv.transform((event.x, event.y))
                rx, ry = rel_pos[0], rel_pos[1]
                margin = 0.15
                if rx < margin or rx > 1-margin or ry < margin or ry > 1-margin:
                    window.config(cursor="sizing")
                else:
                    window.config(cursor="fleur")
            else:
                window.config(cursor="hand2")
        else:
            window.config(cursor="")
        
    def on_release(event):
        nonlocal drag_mode, drag_start_pos, drag_start_widget_state
        if drag_mode and selected_widget_id:
            # Finaliser le mouvement/redimensionnement
            fig = event.canvas.figure
            
            # Calculer la grille actuelle
            mx = max(1, max(w.x + w.w for w in widgets))
            my = max(1, max(w.y + w.h for w in widgets))
            
            # Coordonnées normalisées dans la figure (0 à 1)
            # On utilise les dimensions du canvas
            w_px, h_px = fig.canvas.get_width_height()
            fx = event.x / w_px
            fy = event.y / h_px
            
            # Grille cible (Snap to grid)
            target_x = int(fx * mx)
            target_y = int((1-fy) * my) # Y inversé (0 en haut dans la grille, 0 en bas dans MPL)
            
            w = next((w for w in widgets if w.id == selected_widget_id), None)
            if w and drag_start_widget_state:
                if drag_mode == "move":
                    # Déplacement simple du coin haut-gauche
                    w.x = max(0, target_x)
                    w.y = max(0, target_y)
                elif drag_mode.startswith("resize"):
                    if "e" in drag_mode: w.w = max(1, target_x - w.x + 1)
                    if "w" in drag_mode:
                        old_right = w.x + w.w
                        w.x = min(old_right - 1, max(0, target_x))
                        w.w = old_right - w.x
                    if "s" in drag_mode: w.h = max(1, target_y - w.y + 1)
                    if "n" in drag_mode:
                        old_bottom = w.y + w.h
                        w.y = min(old_bottom - 1, max(0, target_y))
                        w.h = old_bottom - w.y

            refresh_widget_list()
            update_preview()
            
        drag_mode = None
        drag_start_pos = None
        drag_start_widget_state = None
        window.config(cursor="")

    # --- FOOTER ---
    export_fmt_var = tk.StringVar(value="pptx")
    for text, fmt in [("PowerPoint", "pptx"), ("PDF", "pdf"), ("PNG", "png"), ("Excel", "xlsx")]:
        ttk.Radiobutton(footer, text=text, value=fmt, variable=export_fmt_var).pack(side="left", padx=5)
    def run_export():
        sync_widgets_from_ui(); alias = app.alias_var.get() or ""; fmt = export_fmt_var.get()
        
        # Préparation des pages pour l'export
        pages_to_export = []
        current_page_widgets = []
        
        for w in widgets:
            if w.chart_type == "dashboard" and w.linked_dashboard in saved_configs:
                if current_page_widgets:
                    pages_to_export.append({"title": "Page Principale", "widgets": current_page_widgets})
                    current_page_widgets = []
                
                linked_widgets = saved_configs[w.linked_dashboard].widgets
                linked_data = []
                for lw in linked_widgets:
                    linked_data.append({
                        "title": lw.label, "type": lw.chart_type, "color": lw.color,
                        "x": lw.x, "y": lw.y, "w": lw.w, "h": lw.h, "text": lw.text,
                        "rich_text": lw.rich_text, "text_align": lw.text_align, "text_valign": lw.text_valign,
                        "table_columns": lw.table_columns, "table_rows": lw.table_rows,
                        "table_font_name": lw.table_font_name, "table_font_size": lw.table_font_size,
                        "image_path": lw.image_path, "emoji": lw.emoji, "image_font_size": lw.image_font_size,
                        "image_font_color": lw.image_font_color, "kpi_decimals": lw.kpi_decimals,
                        "z_order": lw.z_order, "data": service.get_widget_data(lw, alias=alias)
                    })
                pages_to_export.append({"title": w.linked_dashboard, "widgets": linked_data})
            else:
                current_page_widgets.append({
                    "title": w.label, "type": w.chart_type, "color": w.color,
                    "x": w.x, "y": w.y, "w": w.w, "h": w.h, "text": w.text,
                    "rich_text": w.rich_text, "text_align": w.text_align, "text_valign": w.text_valign,
                    "table_columns": w.table_columns, "table_rows": w.table_rows,
                    "table_font_name": w.table_font_name, "table_font_size": w.table_font_size,
                    "image_path": w.image_path, "emoji": w.emoji, "image_font_size": w.image_font_size,
                    "image_font_color": w.image_font_color, "kpi_decimals": w.kpi_decimals,
                    "z_order": w.z_order, "data": service.get_widget_data(w, alias=alias)
                })
        
        if current_page_widgets:
            pages_to_export.append({"title": "Page Principale", "widgets": current_page_widgets})

        if not pages_to_export: return
        
        ftypes = {
            "pptx": [("PowerPoint", "*.pptx")],
            "pdf": [("PDF", "*.pdf")],
            "png": [("Image PNG", "*.png")],
            "xlsx": [("Excel", "*.xlsx")]
        }
        file_path = filedialog.asksaveasfilename(defaultextension=f".{fmt}", filetypes=ftypes.get(fmt, [("Tous les fichiers", "*.*")]))
        if not file_path: return

        if fmt == "pptx":
            # Pour PPTX, on aplatit tout en une liste de widgets car l'exporteur fait déjà une slide par widget
            all_widgets = []
            for p in pages_to_export: all_widgets.extend(p["widgets"])
            exporter.export_to_pptx(all_widgets, Path(file_path), title=current_config_name.get())
        elif fmt == "xlsx":
            all_widgets = []
            for p in pages_to_export: all_widgets.extend(p["widgets"])
            exporter.export_data(all_widgets, Path(file_path), format='excel')
        else:
            # Pour PDF/PNG, on génère une figure par page
            # Note: L'exporteur actuel ne gère qu'une seule figure. 
            # Pour le PDF, on pourrait faire un PDF multi-pages.
            if fmt == "pdf":
                from matplotlib.backends.backend_pdf import PdfPages
                with PdfPages(file_path) as pdf:
                    for p in pages_to_export:
                        fig = generate_layout_figure(p["widgets"])
                        pdf.savefig(fig)
                        plt.close(fig)
            else:
                # PNG : on n'exporte que la première page ou on les numérote
                for i, p in enumerate(pages_to_export):
                    fig = generate_layout_figure(p["widgets"])
                    suffix = f"_{i+1}" if len(pages_to_export) > 1 else ""
                    path = Path(file_path).with_stem(Path(file_path).stem + suffix)
                    exporter.export_to_png(fig, path)
                    plt.close(fig)
        
        messagebox.showinfo("Succès", "Export terminé.")
    ttk.Button(footer, text="Générer l'export", command=run_export).pack(side="right", padx=10)
    ttk.Button(footer, text="Fermer", command=window.destroy).pack(side="right")

    if not widgets: widgets = service._init_default_widgets()
    refresh_widget_list(); window.after(500, update_preview)

def generate_layout_figure(widgets_data: List[Dict[str, Any]], selected_id: Optional[str] = None) -> Figure:
    if not widgets_data: return Figure()
    
    # Trier les widgets par z_order pour la superposition
    widgets_data = sorted(widgets_data, key=lambda x: x.get('z_order', 0))

    mx, my = max(1, max(w['x'] + w['w'] for w in widgets_data)), max(1, max(w['y'] + w['h'] for w in widgets_data))
    # On ajoute une marge pour voir les poignées de redimensionnement si besoin
    fig = Figure(figsize=(10, 2 * my if my < 5 else 1.5 * my), dpi=90)
    from matplotlib.gridspec import GridSpec
    gs = GridSpec(my, mx, figure=fig)
    for w in widgets_data:
        try:
            # Vérifier la visibilité (condition)
            # On ignore la vérification de visibilité si c'est un dictionnaire vide ou None
            widget_data = w.get('data')
            if isinstance(widget_data, dict) and not widget_data.get('visible', True):
                continue

            ax = fig.add_subplot(gs[w['y']:w['y']+w['h'], w['x']:w['x']+w['w']])
            t, wt, d, c = w['title'], w['type'], w['data'], w.get('color', '#3498db')
            
            # Nettoyer les données pour le rendu (enlever la clé technique 'visible')
            plot_data = {k: v for k, v in d.items() if k != 'visible'} if isinstance(d, dict) else d
            
            # LOGGING pour débogage
            print(f"Rendu widget {w.get('id')} ({wt}): data={plot_data}")

            # Gestion intelligente de la couleur de fond
            # Pour les graphiques, le fond doit rester neutre pour que les données soient visibles
            # Pour text, image et kpi, la couleur est celle du fond.
            if wt in ["text", "image", "kpi"] and ',' not in c:
                bg_color = c
            else:
                bg_color = "none"

            if bg_color == "none":
                ax.set_facecolor('none')
            else:
                try:
                    ax.set_facecolor(bg_color)
                except:
                    ax.set_facecolor('none')

            # Identifiant pour l'interaction
            ax.widget_id = w.get('id')

            if wt == "text":
                ax.axis('off')
                if c != "none":
                    from matplotlib.patches import Rectangle
                    rect = Rectangle((0,0), 1, 1, transform=ax.transAxes, color=c, zorder=-1)
                    ax.add_patch(rect)

                rich = w.get('rich_text')
                align = w.get('text_align', 'left')
                valign = w.get('text_valign', 'top')
                
                if rich:
                    from matplotlib.offsetbox import TextArea, HPacker, AnnotationBbox, VPacker
                    lines = []
                    current_line_segments = []
                    
                    for seg in rich:
                        text_parts = seg['text'].split('\n')
                        for i, part in enumerate(text_parts):
                            if i > 0:
                                lines.append(current_line_segments)
                                current_line_segments = []
                            
                            if part:
                                props = {
                                    "color": seg.get("color", "black"),
                                    "fontsize": seg.get("size", 9),
                                    "fontweight": "bold" if seg.get("bold") else "normal",
                                    "fontstyle": "italic" if seg.get("italic") else "normal",
                                    "fontname": seg.get("font", "Arial")
                                }
                                
                                # Support des émojis dans le texte riche
                                if any(ord(c) > 0xFFFF for c in part):
                                    # On laisse le fallback global gérer l'émoji
                                    props["fontname"] = "sans-serif"
                                    props["fontweight"] = "normal"
                                    props["fontstyle"] = "normal"
                                
                                current_line_segments.append(TextArea(part, textprops=props))
                            elif i > 0:
                                # Ligne vide : on ajoute un espace pour maintenir la hauteur
                                current_line_segments.append(TextArea(" "))
                    
                    if current_line_segments:
                        lines.append(current_line_segments)
                    
                    if lines:
                        # Horizontal alignment of segments within each line
                        line_boxes = [HPacker(children=l, align="baseline", pad=0, sep=0) for l in lines]
                        # Horizontal alignment of lines within the vertical box
                        vbox = VPacker(children=line_boxes, align=align, pad=0, sep=2)
                        
                        # Position and box_alignment for global alignment
                        xy = (0.05, 0.95)
                        box_align = (0, 1)
                        
                        if align == "center":
                            xy = (0.5, xy[1])
                            box_align = (0.5, box_align[1])
                        elif align == "right":
                            xy = (0.95, xy[1])
                            box_align = (1, box_align[1])
                            
                        if valign == "center":
                            xy = (xy[0], 0.5)
                            box_align = (box_align[0], 0.5)
                        elif valign == "bottom":
                            xy = (xy[0], 0.05)
                            box_align = (box_align[0], 0)
                        
                        ab = AnnotationBbox(vbox, xy, xycoords='axes fraction', box_alignment=box_align, frameon=False)
                        ax.add_artist(ab)
                else:
                    ha = align
                    va = valign
                    
                    # Correction des coordonnées pour ax.text
                    tx = 0.05
                    if ha == "center": tx = 0.5
                    elif ha == "right": tx = 0.95
                    
                    ty = 0.95
                    if va == "center": ty = 0.5
                    elif va == "bottom": ty = 0.05
                    
                    # Support des émojis pour le texte simple
                    ax.text(tx, ty, w['text'], va=va, ha=ha, wrap=True, fontsize=9, transform=ax.transAxes)
            elif not plot_data and wt != "image":
                ax.axis('off')
                ax.text(0.5, 0.5, "Pas de données", ha='center', va='center')
            else:
                if wt == "pie" or wt == "donut": 
                    ax.axis('off')
                    # S'assurer que les valeurs sont numériques et > 0
                    valid_data = {str(k): float(v) for k, v in plot_data.items() 
                                 if isinstance(v, (int, float, str)) and str(v).replace('.','',1).isdigit() and float(v) > 0}
                    
                    labels = list(valid_data.keys())
                    values = list(valid_data.values())
                    
                    print(f"  Plotting {wt}: labels={labels}, values={values}")
                    if not values:
                        ax.text(0.5, 0.5, "Données nulles", ha='center', va='center')
                    else:
                        colors = c.split(',') if ',' in c else None
                        try:
                            if wt == "pie":
                                ax.pie(values, labels=labels, autopct='%1.1f%%', startangle=140, colors=colors)
                            else:
                                ax.pie(values, labels=labels, autopct='%1.1f%%', startangle=140, colors=colors, wedgeprops=dict(width=0.4))
                        except Exception as e:
                            print(f"  Erreur ax.pie: {e}")
                            ax.text(0.5, 0.5, f"Erreur graphique", ha='center', va='center')
                
                elif wt == "bar": 
                    labels = [str(k) for k in plot_data.keys()]
                    values = [float(v) if isinstance(v, (int, float, str)) and str(v).replace('.','',1).isdigit() else 0.0 for v in plot_data.values()]
                    print(f"  Plotting bar: labels={labels}, values={values}")
                    if not values or all(v == 0 for v in values):
                         ax.text(0.5, 0.5, "Données nulles", ha='center', va='center')
                    else:
                        colors = c.split(',') if ',' in c else c
                        try:
                            x_indices = list(range(len(labels)))
                            ax.bar(x_indices, values, color=colors)
                            ax.set_xticks(x_indices)
                            ax.set_xticklabels(labels, rotation=45, ha='right', fontsize=7)
                        except Exception as e:
                            print(f"  Erreur ax.bar: {e}")
                            ax.text(0.5, 0.5, f"Erreur graphique", ha='center', va='center')
                
                elif wt == "stacked_bar":
                    labels = plot_data.get('labels', [])
                    series = plot_data.get('series', {})
                    print(f"  Plotting stacked_bar: labels={labels}, series_keys={list(series.keys())}")
                    if not labels or not series:
                        ax.text(0.5, 0.5, "Données nulles", ha='center', va='center')
                    else:
                        try:
                            x_indices = list(range(len(labels)))
                            bottom = None
                            colors = c.split(',') if ',' in c else [c]
                            for i, (name, vals) in enumerate(series.items()):
                                color = colors[i % len(colors)]
                                clean_vals = [float(v) if isinstance(v, (int, float, str)) and str(v).replace('.','',1).isdigit() else 0.0 for v in vals]
                                ax.bar(x_indices, clean_vals, bottom=bottom, label=name, color=color)
                                if bottom is None: bottom = [0.0] * len(clean_vals)
                                bottom = [b + v for b, v in zip(bottom, clean_vals)]
                            
                            ax.legend(fontsize=7)
                            ax.set_xticks(x_indices)
                            step = max(1, len(labels) // 6)
                            display_labels = [l if i % step == 0 else "" for i, l in enumerate(labels)]
                            ax.set_xticklabels(display_labels, rotation=45, ha='right', fontsize=7)
                        except Exception as e:
                            print(f"  Erreur ax.bar (stacked): {e}")
                            ax.text(0.5, 0.5, f"Erreur graphique", ha='center', va='center')
                
                elif wt == "line" or wt == "area":
                    labels = [str(k) for k in plot_data.keys()]
                    
                    def safe_float(v):
                        try:
                            if isinstance(v, str):
                                v = v.replace(',', '.')
                            return float(v)
                        except:
                            return 0.0
                            
                    values = [safe_float(v) for v in plot_data.values()]
                    print(f"  Plotting {wt}: labels={labels}, values={values}")
                    
                    if not labels:
                        ax.text(0.5, 0.5, "Pas de données", ha='center', va='center')
                    else:
                        try:
                            # Utiliser une seule couleur pour la ligne/aire
                            line_color = c.split(',')[0] if ',' in c else c
                            if line_color == "none": line_color = "#3498db"
                            
                            # Pour les graphiques temporels, on utilise des indices pour éviter les erreurs de catégories
                            x_indices = list(range(len(labels)))
                            
                            if wt == "line":
                                ax.plot(x_indices, values, marker='o', color=line_color, linewidth=2)
                            else:
                                ax.fill_between(x_indices, values, color=line_color, alpha=0.3)
                                ax.plot(x_indices, values, color=line_color, marker='.', linewidth=1)
                            
                            # Configurer les étiquettes de l'axe X
                            ax.set_xticks(x_indices)
                            # On ne garde qu'une étiquette sur 2 ou 3 si il y en a trop
                            step = max(1, len(labels) // 5)
                            display_labels = [l if i % step == 0 else "" for i, l in enumerate(labels)]
                            ax.set_xticklabels(display_labels, rotation=30, ha='right', fontsize=7)
                            
                            # Grille et limites
                            ax.grid(True, linestyle='--', alpha=0.6)
                            if values:
                                v_min, v_max = min(values), max(values)
                                margin = (v_max - v_min) * 0.1 if v_max > v_min else 1.0
                                ax.set_ylim(min(0, v_min - margin), v_max + margin)
                            
                        except Exception as e:
                            print(f"  Erreur ax.plot/fill: {e}")
                            ax.text(0.5, 0.5, f"Erreur graphique", ha='center', va='center')
                
                elif wt == "kpi":
                    ax.axis('off')
                    # Formater les nombres
                    dec = w.get('kpi_decimals', 1)
                    lines = []
                    for k, v in plot_data.items():
                        if isinstance(v, (int, float)):
                            lines.append(f"{k}: {v:.{dec}f}")
                        else:
                            lines.append(f"{k}: {v}")
                    txt = "\n".join(lines)
                    
                    bbox_props = dict(facecolor='white', alpha=0.2, boxstyle='round')
                    if c == "none":
                        bbox_props['alpha'] = 0.0
                    
                    ax.text(0.5, 0.5, txt, ha='center', va='center', fontweight='bold', bbox=bbox_props)
            
            ax.set_title(t, fontsize=10, fontweight='bold')
            ax.set_box_aspect(None) # S'assurer que le graphique s'étire
            
            if wt == "table":
                ax.axis('off')
                rows = d.get('rows', [])
                if not rows:
                    ax.text(0.5, 0.5, "Pas de données", ha='center', va='center')
                else:
                    # Déterminer les colonnes à afficher
                    cols_to_show = w.get('table_columns', [])
                    row_keys = w.get('table_rows', [])
                    
                    if not cols_to_show and rows:
                        cols_to_show = [k for k in rows[0].keys() if k not in row_keys]
                    
                    all_cols = row_keys + cols_to_show
                    
                    # Vérification de la validité des colonnes par rapport au résultat SQL
                    if rows:
                        actual_keys = list(rows[0].keys())
                        # Filtrer pour ne garder que ce qui existe vraiment dans le résultat
                        valid_cols = [c for c in all_cols if c in actual_keys]
                        
                        # Si aucune colonne demandée n'existe (ex: renommage via AS), 
                        # on prend tout ce qui est disponible dans le résultat
                        if not valid_cols:
                            all_cols = actual_keys
                        else:
                            all_cols = valid_cols

                    table_data = []
                    for r in rows[:15]: # Limiter à 15 lignes pour l'aperçu
                        table_data.append([str(r.get(c, '')) for c in all_cols])
                    
                    if table_data:
                        tab = ax.table(cellText=table_data, colLabels=all_cols, loc='center', cellLoc='center', bbox=[0, 0, 1, 1])
                        tab.auto_set_font_size(False)
                        tab.set_fontsize(w.get('table_font_size', 7))
                        # Appliquer la police choisie
                        font_name = w.get('table_font_name', 'Arial')
                        
                        for cell in tab.get_celld().values():
                            cell.set_text_props(fontfamily=font_name)
                        
                        # Ajuster les colonnes
                        tab.auto_set_column_width(col=list(range(len(all_cols))))
            
            if wt == "image":
                ax.axis('off')
                if c != "none":
                    from matplotlib.patches import Rectangle
                    rect = Rectangle((0,0), 1, 1, transform=ax.transAxes, color=c, zorder=-1)
                    ax.add_patch(rect)
                
                img_path = w.get('image_path')
                emoji = w.get('emoji')
                
                if img_path and Path(img_path).exists():
                    try:
                        import matplotlib.image as mpimg
                        img = mpimg.imread(img_path)
                        ax.imshow(img, aspect='equal', extent=[0.1, 0.9, 0.1, 0.9])
                    except:
                        ax.text(0.5, 0.5, "Erreur image", ha='center', va='center')
                elif emoji:
                    # On utilise le fallback global via sans-serif
                    ax.text(0.5, 0.5, emoji, ha='center', va='center', 
                            fontsize=w.get('image_font_size', 50), 
                            color=w.get('image_font_color', '#000000'),
                            fontfamily="sans-serif")
                else:
                    ax.text(0.5, 0.5, "Aucune image", ha='center', va='center')

            # Dessiner la sélection
            if selected_id and ax.widget_id == selected_id:
                for spine in ax.spines.values():
                    spine.set_edgecolor('blue')
                    spine.set_linewidth(2)
                    spine.set_linestyle('--')
                
                # Points de redimensionnement (coins et milieux)
                from matplotlib.lines import Line2D
                handles = [(0,0), (1,0), (0,1), (1,1), (0.5,0), (0.5,1), (0,0.5), (1,0.5)]
                for hx, hy in handles:
                    line = Line2D([hx], [hy], marker='s', color='blue', markersize=6, 
                                 transform=ax.transAxes, clip_on=False, zorder=100)
                    ax.add_line(line)
        except Exception as e:
            print(f"Erreur rendu widget {w.get('id')} ({w.get('type')}): {e}")
            import traceback
            traceback.print_exc()
    
    try:
        fig.tight_layout()
    except:
        pass
    return fig
