import tkinter as tk
from tkinter import ttk, colorchooser, filedialog
from typing import List, Dict, Any, Optional
from src.core.dashboard_service import DashboardWidget
from src.ui.dashboard.sql_builder import open_query_builder

def build_widget_editor(container, widgets, saved_configs, service, app, window, update_preview_callback, refresh_callback):
    """Construit l'éditeur de propriétés des widgets sur la gauche."""
    widget_ui_elements = []
    
    for i, w in enumerate(widgets):
        f = ttk.LabelFrame(container, text=app._t("designer_widget_label", i=i+1, label=w.label), padding=5)
        f.pack(fill="x", pady=5, padx=5)
        
        row1 = ttk.Frame(f); row1.pack(fill="x")
        t_var = tk.StringVar(value=w.label)
        ttk.Entry(row1, textvariable=t_var, width=20).pack(side="left")
        
        type_var = tk.StringVar(value=w.chart_type)
        type_cb = ttk.Combobox(row1, textvariable=type_var, 
                               values=["bar", "pie", "donut", "line", "area", "stacked_bar", "kpi", "text", "table", "image", "dashboard"], 
                               width=9, state="readonly")
        type_cb.pack(side="left", padx=5)
        
        c_var = tk.StringVar(value=w.color)
        ttk.Entry(row1, textvariable=c_var, width=12).pack(side="left")
        
        def pick_color(var=c_var):
            color = colorchooser.askcolor(title=app._t("language"))[1] # Using language as a proxy for "Color" if no specific key
            if color:
                choice_win = tk.Toplevel(window)
                choice_win.title(app._t("designer_color_action_title"))
                choice_win.geometry("300x150")
                app._configure_secondary_window(choice_win)
                ttk.Label(choice_win, text=app._t("designer_color_label", color=color)).pack(pady=10)
                bf = ttk.Frame(choice_win); bf.pack(pady=10)
                ttk.Button(bf, text=app._t("designer_color_replace"), command=lambda: [var.set(color), choice_win.destroy(), update_preview_callback()]).pack(side="left", padx=5)
                ttk.Button(bf, text=app._t("designer_color_append"), command=lambda: [var.set(f"{var.get()},{color}" if var.get() else color), choice_win.destroy(), update_preview_callback()]).pack(side="left", padx=5)
                ttk.Button(bf, text=app._t("designer_color_transparent"), command=lambda: [var.set("none"), choice_win.destroy(), update_preview_callback()]).pack(side="left", padx=5)

        ttk.Button(row1, text="🎨", width=3, command=pick_color).pack(side="left", padx=2)
        ttk.Button(row1, text="X", width=2, command=lambda idx=i: [widgets.pop(idx), refresh_callback(), update_preview_callback()]).pack(side="right")
        
        row2 = ttk.Frame(f); row2.pack(fill="x", pady=5)
        xv, yv, wv, hv, zv = (tk.StringVar(value=str(w.x)), tk.StringVar(value=str(w.y)), 
                              tk.StringVar(value=str(w.w)), tk.StringVar(value=str(w.h)), 
                              tk.StringVar(value=str(w.z_order)))
        for lbl, var in [("X:", xv), (" Y:", yv), (" W:", wv), (" H:", hv), (" Z:", zv)]:
            ttk.Label(row2, text=lbl).pack(side="left")
            ttk.Entry(row2, textvariable=var, width=3).pack(side="left", padx=2)
        
        q_var = tk.StringVar(value=w.query); q_row = ttk.Frame(f); q_row.pack(fill="x")
        ttk.Entry(q_row, textvariable=q_var, font=("Consolas", 8)).pack(side="left", fill="x", expand=True)
        ttk.Button(q_row, text=app._t("designer_sql_builder"), command=lambda v=q_var: open_query_builder(window, app, service, v)).pack(side="right", padx=2)
        
        cond_var = tk.StringVar(value=w.condition); cond_row = ttk.Frame(f); cond_row.pack(fill="x", pady=2)
        ttk.Label(cond_row, text=app._t("designer_condition")).pack(side="left")
        ttk.Entry(cond_row, textvariable=cond_var, font=("Consolas", 8)).pack(side="left", fill="x", expand=True)
        
        # Outils spécifiques selon type
        kpi_tools = ttk.Frame(f)
        kpi_dec_var = tk.StringVar(value=str(w.kpi_decimals))
        ttk.Label(kpi_tools, text=app._t("designer_decimals")).pack(side="left")
        ttk.Combobox(kpi_tools, textvariable=kpi_dec_var, values=["0", "1", "2", "3"], width=3, state="readonly").pack(side="left", padx=2)

        dash_tools = ttk.Frame(f)
        linked_dash_var = tk.StringVar(value=w.linked_dashboard)
        ttk.Label(dash_tools, text=app._t("designer_dashboard_linked")).pack(side="left")
        ttk.Combobox(dash_tools, textvariable=linked_dash_var, values=list(saved_configs.keys()), width=20, state="readonly").pack(side="left", padx=2)

        image_tools = ttk.Frame(f)
        img_path_var = tk.StringVar(value=w.image_path)
        emoji_var = tk.StringVar(value=w.emoji)
        img_size_var = tk.StringVar(value=str(w.image_font_size))
        img_color_var = tk.StringVar(value=w.image_font_color)
        
        def browse_image(v=img_path_var):
            path = filedialog.askopenfilename(filetypes=[("Images", "*.png *.jpg *.jpeg *.gif *.bmp")])
            if path: v.set(path); update_preview_callback()

        row_i1 = ttk.Frame(image_tools); row_i1.pack(fill="x")
        ttk.Button(row_i1, text=app._t("designer_image_btn"), command=browse_image).pack(side="left")
        all_emojis = ["☀️", "⛅", "☁️", "🌧️", "⛈️", "😊", "😐", "☹️", "🚀", "📊", "✅", "❌", "⚠️", "💡", "🔥", "⭐", "🎯", "🏆", "⚙️", "🔒", "🌍"]
        ttk.Combobox(row_i1, textvariable=emoji_var, values=all_emojis, width=3, state="readonly").pack(side="left", padx=2)

        table_tools = ttk.Frame(f)
        t_font_var = tk.StringVar(value=w.table_font_name)
        t_size_var = tk.StringVar(value=str(w.table_font_size))
        ttk.Label(table_tools, text=app._t("designer_font")).pack(side="left")
        ttk.Combobox(table_tools, textvariable=t_font_var, values=["Arial", "Courier New", "Verdana", "Times New Roman"], width=10).pack(side="left", padx=2)
        ttk.Combobox(table_tools, textvariable=t_size_var, values=["6", "7", "8", "9", "10", "12"], width=3).pack(side="left", padx=2)

        text_tools = ttk.Frame(f)
        def open_rich_text():
            from src.ui.dashboard_designer_screen import open_rich_text_editor
            open_rich_text_editor(window, app, w, update_preview_callback)
        ttk.Button(text_tools, text=app._t("designer_rich_text_btn"), command=open_rich_text).pack(fill="x")

        def show_tools(*args):
            for t in [kpi_tools, dash_tools, image_tools, table_tools, text_tools]: t.pack_forget()
            vt = type_var.get()
            if vt == "kpi": kpi_tools.pack(fill="x", pady=2)
            elif vt == "dashboard": dash_tools.pack(fill="x", pady=2)
            elif vt == "image": image_tools.pack(fill="x", pady=2)
            elif vt == "table": table_tools.pack(fill="x", pady=2)
            elif vt == "text": text_tools.pack(fill="x", pady=2)
        
        type_var.trace_add("write", show_tools)
        show_tools()

        widget_ui_elements.append({
            "widget": w, "t_var": t_var, "type_var": type_var, "c_var": c_var,
            "xv": xv, "yv": yv, "wv": wv, "hv": hv, "zv": zv, "q_var": q_var,
            "cond_var": cond_var, "kpi_dec_var": kpi_dec_var, "linked_dash_var": linked_dash_var,
            "img_path_var": img_path_var, "emoji_var": emoji_var, "img_size_var": img_size_var,
            "img_color_var": img_color_var, "t_font_var": t_font_var, "t_size_var": t_size_var
        })
        
    return widget_ui_elements

def sync_widgets(widget_ui_elements):
    """Synchronise les objets DashboardWidget avec les variables de l'UI."""
    for el in widget_ui_elements:
        w = el["widget"]
        w.label = el["t_var"].get()
        w.chart_type = el["type_var"].get()
        w.color = el["c_var"].get()
        try:
            w.x, w.y, w.w, w.h, w.z_order = (int(el["xv"].get()), int(el["yv"].get()), 
                                            int(el["wv"].get()), int(el["hv"].get()), 
                                            int(el["zv"].get()))
        except: pass
        w.query = el["q_var"].get()
        w.condition = el["cond_var"].get()
        try: w.kpi_decimals = int(el["kpi_dec_var"].get())
        except: pass
        w.linked_dashboard = el["linked_dash_var"].get()
        w.image_path = el["img_path_var"].get()
        w.emoji = el["emoji_var"].get()
        try: w.image_font_size = int(el["img_size_var"].get())
        except: pass
        w.image_font_color = el["img_color_var"].get()
        w.table_font_name = el["t_font_var"].get()
        try: w.table_font_size = int(el["t_size_var"].get())
        except: pass
