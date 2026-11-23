#!/usr/bin/env python3
"""
Редактор карт для ZombieSurvival (вид сверху). Нужен только Python 3 + tkinter (есть в стандартной установке).

Запуск:  python3 tools/map_editor.py

Новое: кнопка «3D вид» (просмотр с вращением), рельеф (холмы/ямы), браши, текстуры, границы, рисование объектами (протягивание),
свойства карты (размер, цвет/текстура земли), контейнеры с лутом, деревья.

Управление:
  ЛКМ по пустому месту  — поставить выбранный объект (инструмент слева)
  ЛКМ по объекту        — выделить / тащить
  Колесо                — масштаб карты;  средняя/правая кнопка (или Пробел+ЛКМ) — двигать вид
  Shift+колесо          — размер выделенного (радиус / ширина)
  R / Shift+R           — повернуть выделенный на +15 / -15 градусов
  Delete                — удалить;  Ctrl+D — дублировать;  Ctrl+Z — отмена;  Ctrl+S — сохранить
  Дорога: два клика (начало и конец).
Карты сохраняются в <проект>/maps/<имя>.json, модели копируются в <проект>/assets/models/maps/.
В игре: Играть -> тип карты -> «★ Своя карта: <имя>».
"""
import copy
import json
import math
import os
import shutil
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(HERE)          # папка ZombieSurvival
WORLD_HALF = 150.0                       # по умолчанию; настраивается в «Свойствах карты»
CONT_SIZE = {"crate": (0.9, 0.7), "barrel": (0.7, 0.7), "cabinet": (0.9, 0.5), "locker": (0.6, 0.5), "fridge": (0.8, 0.7), "car": (1.9, 4.2)}
PAINTABLE = {"house", "panelka", "wall", "forest", "lake", "swamp", "model", "brush", "container", "tree", "loot", "zombie", "hill"}

TOOLS = [
    ("select", "Выбор / двигать"),
    ("house", "Дом"),
    ("panelka", "Панелька (5 этажей)"),
    ("wall", "Стена / забор"),
    ("road", "Дорога"),
    ("forest", "Лес (клещи)"),
    ("lake", "Озеро (комары)"),
    ("swamp", "Болото (споры)"),
    ("brush", "Браш (куб/цилиндр/шар/рампа)"),
    ("container", "Контейнер с лутом"),
    ("tree", "Дерево"),
    ("hill", "Холм (+) / яма (−)"),
    ("border", "Граница (невидимая стена)"),
    ("model", "Своя модель (.glb)"),
    ("loot", "Точка лута"),
    ("zombie", "Зомби"),
    ("spawn", "Старт игроков"),
]

DEFAULTS = {
    "house": {"w": 8.0, "d": 7.0, "rot": 0.0, "color": "#b8a58c", "floors": 0},
    "panelka": {"w": 32.0, "d": 13.0, "rot": 0.0, "color": "#a9a59b", "floors": 5},
    "wall": {"w": 6.0, "d": 0.4, "h": 2.5, "rot": 0.0, "color": "#8a8a8a", "tex": "", "invisible": False},
    "road": {"w": 5.0},
    "forest": {"r": 25.0},
    "lake": {"r": 12.0},
    "swamp": {"r": 18.0},
    "brush": {"shape": "box", "w": 4.0, "d": 4.0, "h": 3.0, "y": 0.0, "rot": 0.0, "color": "#9a9a9a", "tex": "", "solid": True, "flat": False},
    "container": {"kind": "crate", "rot": 0.0},
    "tree": {"s": 1.0},
    "hill": {"r": 30.0, "h": 6.0},
    "model": {"file": "", "y": 0.0, "rot": 0.0, "scale": 1.0, "w": 2.0, "d": 2.0, "h": 2.0, "solid": True, "clear": True},
    "loot": {},
    "zombie": {"kind": "walker"},
}

COLORS = {
    "house": "#c9b79c", "panelka": "#a9a59b", "wall": "#888888", "road": "#8c7355", "forest": "#3f7a2a",
    "lake": "#3a78b5", "swamp": "#5b6b2e", "model": "#d070d0", "loot": "#ffd23f",
    "zombie": "#c0392b", "spawn": "#2ecc71", "brush": "#a0a0b0", "container": "#c08a3a", "tree": "#2e7d32", "hill": "#a58d5a",
}


class Editor:
    def __init__(self, root):
        self.root = root
        root.title("Редактор карт — ZombieSurvival")
        root.geometry("1280x800")
        self.project = PROJECT
        self.name = "моя_карта"
        self.data = {"name": self.name, "spawn": [0.0, 0.0], "objects": []}
        self.tool = tk.StringVar(value="house")
        self.snap = tk.BooleanVar(value=True)
        self.grid_step = 5.0
        self.zoom = 4.0            # пикселей на метр
        self.off = [0.0, 0.0]      # смещение вида (в пикселях)
        self.sel = None
        self.undo_stack = []
        self.drag = None
        self.pending_road = None
        self.model_file = ""
        self.pan_start = None
        self.space = False
        self.mouse = (0.0, 0.0)
        self.dirty = False
        self.cur_shape = tk.StringVar(value="box")
        self.cur_kind = tk.StringVar(value="crate")
        self.cur_tex = ""
        self.paint = tk.BooleanVar(value=False)
        self.paint_step = tk.StringVar(value="6")
        self.painting = False
        self.last_paint = None
        self.view3d = False
        self.cam = {"yaw": 0.6, "pitch": 0.55, "dist": 220.0, "tx": 0.0, "ty": 0.0, "tz": 0.0}
        self.drag3d = None
        self._build_ui()
        self.center_view()
        self.redraw()

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        r = self.root
        outer = ttk.Frame(r)
        outer.pack(side="left", fill="y")
        lc = tk.Canvas(outer, width=250, highlightthickness=0)
        sb = ttk.Scrollbar(outer, orient="vertical", command=lc.yview)
        lc.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        lc.pack(side="left", fill="y", expand=True)
        left = ttk.Frame(lc, padding=6)
        lc.create_window((0, 0), window=left, anchor="nw")
        left.bind("<Configure>", lambda e: lc.configure(scrollregion=lc.bbox("all")))
        lc.bind("<Enter>", lambda e: (lc.bind_all("<MouseWheel>", lambda ev: lc.yview_scroll(-1 if ev.delta > 0 else 1, "units")), lc.bind_all("<Button-4>", lambda ev: lc.yview_scroll(-1, "units")), lc.bind_all("<Button-5>", lambda ev: lc.yview_scroll(1, "units"))))
        lc.bind("<Leave>", lambda e: (lc.unbind_all("<MouseWheel>"), lc.unbind_all("<Button-4>"), lc.unbind_all("<Button-5>")))
        ttk.Label(left, text="Инструменты", font=("", 11, "bold")).pack(anchor="w")
        for key, label in TOOLS:
            ttk.Radiobutton(left, text=label, value=key, variable=self.tool, command=self._tool_changed).pack(anchor="w")
        ttk.Checkbutton(left, text="Привязка к сетке", variable=self.snap).pack(anchor="w", pady=(8, 0))
        pf = ttk.Frame(left)
        pf.pack(anchor="w")
        ttk.Checkbutton(pf, text="Рисовать объектами, шаг:", variable=self.paint).pack(side="left")
        ttk.Entry(pf, textvariable=self.paint_step, width=4).pack(side="left")
        ttk.Label(left, text="Форма браша:").pack(anchor="w", pady=(6, 0))
        ttk.Combobox(left, textvariable=self.cur_shape, values=["box", "cylinder", "sphere", "ramp"], state="readonly", width=14).pack(anchor="w")
        ttk.Label(left, text="Тип контейнера:").pack(anchor="w")
        ttk.Combobox(left, textvariable=self.cur_kind, values=list(CONT_SIZE.keys()), state="readonly", width=14).pack(anchor="w")
        ttk.Button(left, text="Текстура для новых…", command=self.pick_cur_tex).pack(fill="x", pady=(4, 0))
        self.tex_lbl = ttk.Label(left, text="текстура: —", wraplength=180)
        self.tex_lbl.pack(anchor="w")
        ttk.Button(left, text="Свойства карты…", command=self.map_props).pack(fill="x", pady=(6, 0))
        self.btn3d = ttk.Button(left, text="3D вид (просмотр)", command=self.toggle3d)
        self.btn3d.pack(fill="x", pady=(2, 0))
        ttk.Button(left, text="Выбрать .glb для модели…", command=self.pick_model).pack(fill="x", pady=(10, 2))
        self.model_lbl = ttk.Label(left, text="модель: —", wraplength=180)
        self.model_lbl.pack(anchor="w")
        ttk.Separator(left).pack(fill="x", pady=8)
        ttk.Button(left, text="Новая карта", command=self.new_map).pack(fill="x")
        ttk.Button(left, text="Открыть…", command=self.open_map).pack(fill="x")
        ttk.Button(left, text="Сохранить (Ctrl+S)", command=self.save_map).pack(fill="x")
        ttk.Button(left, text="Папка проекта…", command=self.pick_project).pack(fill="x", pady=(6, 0))
        self.proj_lbl = ttk.Label(left, text=self.project, wraplength=180, foreground="#666")
        self.proj_lbl.pack(anchor="w")
        ttk.Separator(left).pack(fill="x", pady=8)
        ttk.Label(left, text="Свойства", font=("", 11, "bold")).pack(anchor="w")
        self.props = ttk.Frame(left)
        self.props.pack(fill="x")
        self.status = ttk.Label(left, text="", wraplength=190, foreground="#444")
        self.status.pack(anchor="w", pady=4)

        self.canvas = tk.Canvas(r, bg="#2b3a2b", highlightthickness=0)
        self.canvas.pack(side="left", fill="both", expand=True)
        c = self.canvas
        c.bind("<Button-1>", self.on_down)
        c.bind("<B1-Motion>", self.on_move)
        c.bind("<ButtonRelease-1>", self.on_up)
        c.bind("<Motion>", self.on_hover)
        for b in ("<Button-2>", "<Button-3>"):
            c.bind(b, self.pan_down)
        for b in ("<B2-Motion>", "<B3-Motion>"):
            c.bind(b, self.pan_move)
        c.bind("<MouseWheel>", self.on_wheel)
        c.bind("<Button-4>", lambda e: self.on_wheel(e, 1))
        c.bind("<Button-5>", lambda e: self.on_wheel(e, -1))
        c.bind("<Configure>", lambda e: self.redraw())
        r.bind("<Delete>", lambda e: self.delete_sel())
        r.bind("<Control-s>", lambda e: self.save_map())
        r.bind("<Control-z>", lambda e: self.undo())
        r.bind("<Control-d>", lambda e: self.duplicate())
        r.bind("<r>", lambda e: self.rotate_sel(15))
        r.bind("<R>", lambda e: self.rotate_sel(-15))
        r.bind("<KeyPress-space>", lambda e: setattr(self, "space", True))
        r.bind("<KeyRelease-space>", lambda e: setattr(self, "space", False))
        r.bind("<Escape>", lambda e: self.cancel())
        r.protocol("WM_DELETE_WINDOW", self.on_close)

    def set_status(self, t):
        self.status.config(text=t)

    def _tool_changed(self):
        self.pending_road = None
        self.set_status("Инструмент: " + dict(TOOLS)[self.tool.get()])
        self.redraw()

    def cancel(self):
        self.pending_road = None
        self.sel = None
        self.rebuild_props()
        self.redraw()

    def bound(self):
        return float(self.data.get("bounds", WORLD_HALF))

    # ------------------------------------------------------------------ текстуры / свойства карты
    def textures_dir(self):
        return os.path.join(self.project, "assets", "textures")

    def copy_texture(self, src):
        os.makedirs(self.textures_dir(), exist_ok=True)
        dst = os.path.join(self.textures_dir(), os.path.basename(src))
        if os.path.abspath(src) != os.path.abspath(dst):
            shutil.copy2(src, dst)
        return os.path.basename(src)

    def ask_texture(self):
        p = filedialog.askopenfilename(title="Текстура (PNG/JPG)", filetypes=[("Изображения", "*.png *.jpg *.jpeg *.webp"), ("Все", "*.*")])
        return self.copy_texture(p) if p else ""

    def pick_cur_tex(self):
        t = self.ask_texture()
        self.cur_tex = t
        self.tex_lbl.config(text="текстура: " + (t or "—"))

    def map_props(self):
        d = self.data
        win = tk.Toplevel(self.root)
        win.title("Свойства карты")
        win.transient(self.root)
        vars_ = {}
        rows = [("bounds", "Размер: половина стороны, м", str(d.get("bounds", 150))),
                ("ground_a", "Цвет земли A (#rrggbb)", d.get("ground_a", "#335722")),
                ("ground_b", "Цвет земли B (#rrggbb)", d.get("ground_b", "#476e2b")),
                ("ground_tex", "Текстура земли (файл)", d.get("ground_tex", ""))]
        for i, (k, label, val) in enumerate(rows):
            ttk.Label(win, text=label).grid(row=i, column=0, sticky="w", padx=6, pady=3)
            v = tk.StringVar(value=val)
            vars_[k] = v
            ttk.Entry(win, textvariable=v, width=24).grid(row=i, column=1, padx=6)
        ttk.Button(win, text="Выбрать текстуру…", command=lambda: vars_["ground_tex"].set(self.ask_texture() or vars_["ground_tex"].get())).grid(row=3, column=2)
        scatter = tk.BooleanVar(value=bool(d.get("scatter", True)))
        ttk.Checkbutton(win, text="Случайные деревья по всей карте", variable=scatter).grid(row=4, column=0, columnspan=2, sticky="w", padx=6)

        def ok():
            self.push_undo()
            try:
                d["bounds"] = max(40.0, float(vars_["bounds"].get().replace(",", ".")))
            except ValueError:
                pass
            for k in ("ground_a", "ground_b", "ground_tex"):
                d[k] = vars_[k].get().strip()
            d["scatter"] = scatter.get()
            win.destroy()
            self.redraw()
        ttk.Button(win, text="OK", command=ok).grid(row=5, column=1, pady=8)

    # ------------------------------------------------------------------ координаты
    def center_view(self):
        w = max(self.canvas.winfo_width(), 800)
        h = max(self.canvas.winfo_height(), 600)
        self.off = [w / 2, h / 2]

    def w2s(self, x, z):
        return x * self.zoom + self.off[0], z * self.zoom + self.off[1]

    def s2w(self, sx, sz):
        return (sx - self.off[0]) / self.zoom, (sz - self.off[1]) / self.zoom

    def snapv(self, v):
        if self.snap.get():
            return round(v / self.grid_step) * self.grid_step
        return round(v, 2)

    # ------------------------------------------------------------------ отмена
    def push_undo(self):
        self.undo_stack.append(copy.deepcopy(self.data))
        if len(self.undo_stack) > 100:
            self.undo_stack.pop(0)
        self.dirty = True

    def undo(self):
        if self.undo_stack:
            self.data = self.undo_stack.pop()
            self.sel = None
            self.rebuild_props()
            self.redraw()

    # ------------------------------------------------------------------ геометрия объектов
    @staticmethod
    def rect_corners(o):
        w, d = o.get("w", 2.0), o.get("d", 2.0)
        a = math.radians(o.get("rot", 0.0))
        ca, sa = math.cos(a), math.sin(a)
        pts = []
        for lx, lz in ((-w / 2, -d / 2), (w / 2, -d / 2), (w / 2, d / 2), (-w / 2, d / 2)):
            pts.append((o["x"] + lx * ca + lz * sa, o["z"] - lx * sa + lz * ca))
        return pts

    def hit(self, o, wx, wz):
        t = o["t"]
        if t in ("forest", "lake", "swamp"):
            return math.hypot(wx - o["x"], wz - o["z"]) <= o["r"]
        if t == "hill":
            return math.hypot(wx - o["x"], wz - o["z"]) <= o["r"] * 0.5
        if t == "tree":
            return math.hypot(wx - o["x"], wz - o["z"]) <= 1.8 * o.get("s", 1.0)
        if t == "container":
            cw, cd = CONT_SIZE.get(o.get("kind", "crate"), (1, 1))
            o2 = {"x": o["x"], "z": o["z"], "w": cw, "d": cd, "rot": o.get("rot", 0.0)}
            return self.hit_rect(o2, wx, wz)
        if t in ("house", "panelka", "wall", "model", "brush"):
            a = math.radians(o.get("rot", 0.0))
            dx, dz = wx - o["x"], wz - o["z"]
            lx = dx * math.cos(a) - dz * math.sin(a)
            lz = dx * math.sin(a) + dz * math.cos(a)
            return abs(lx) <= o.get("w", 2) / 2 + 0.3 and abs(lz) <= o.get("d", 2) / 2 + 0.3
        if t == "road":
            ax, az, bx, bz = o["x"], o["z"], o["x2"], o["z2"]
            vx, vz = bx - ax, bz - az
            L2 = vx * vx + vz * vz or 1.0
            k = max(0.0, min(1.0, ((wx - ax) * vx + (wz - az) * vz) / L2))
            return math.hypot(wx - (ax + k * vx), wz - (az + k * vz)) <= max(o["w"] / 2, 1.5)
        return math.hypot(wx - o["x"], wz - o["z"]) <= 2.0

    @staticmethod
    def hit_rect(o, wx, wz):
        a = math.radians(o.get("rot", 0.0))
        dx, dz = wx - o["x"], wz - o["z"]
        lx = dx * math.cos(a) - dz * math.sin(a)
        lz = dx * math.sin(a) + dz * math.cos(a)
        return abs(lx) <= o["w"] / 2 + 0.3 and abs(lz) <= o["d"] / 2 + 0.3

    def pick(self, wx, wz):
        # сверху вниз; маленькие объекты приоритетнее больших зон
        order = {"loot": 0, "zombie": 0, "tree": 0, "container": 0, "model": 1, "house": 1, "panelka": 1, "wall": 1, "brush": 1, "road": 2, "forest": 3, "lake": 3, "swamp": 3, "hill": 4}
        cands = [o for o in self.data["objects"] if self.hit(o, wx, wz)]
        if math.hypot(wx - self.data["spawn"][0], wz - self.data["spawn"][1]) <= 2.5:
            return {"t": "spawn", "x": self.data["spawn"][0], "z": self.data["spawn"][1], "_spawn": True}
        cands.sort(key=lambda o: order.get(o["t"], 5))
        return cands[0] if cands else None

    # ------------------------------------------------------------------ события мыши
    def on_hover(self, e):
        self.mouse = (e.x, e.y)
        if self.pending_road is not None or self.tool.get() != "select":
            self.redraw()
        wx, wz = self.s2w(e.x, e.y)
        self.set_status("x=%.1f  z=%.1f" % (wx, wz))

    def on_down(self, e):
        self.canvas.focus_set()
        if self.view3d:
            self.drag3d = ("orbit", e.x, e.y, dict(self.cam))
            return
        if self.space:
            self.pan_down(e)
            return
        wx, wz = self.s2w(e.x, e.y)
        tool = self.tool.get()
        hit = self.pick(wx, wz)
        if tool == "select" or (hit is not None and tool != "road" and hit["t"] == tool):
            self.sel = hit
            if hit is not None:
                self.push_undo()
                self.drag = (wx - hit["x"], wz - hit["z"])
            self.rebuild_props()
            self.redraw()
            return
        self.place(tool, wx, wz)
        if self.paint.get() and tool in PAINTABLE:
            self.painting = True
            self.last_paint = (wx, wz)

    def place(self, tool, wx, wz, keep_sel=False):
        x, z = self.snapv(wx), self.snapv(wz)
        if tool == "spawn":
            self.push_undo()
            self.data["spawn"] = [x, z]
            self.sel = {"t": "spawn", "x": x, "z": z, "_spawn": True}
        elif tool in ("road", "border"):
            if self.pending_road is None:
                self.pending_road = (x, z)
                self.set_status("Кликните конечную точку (Esc — отмена)")
                return
            self.push_undo()
            ax, az = self.pending_road
            if tool == "road":
                o = {"t": "road", "x": ax, "z": az, "x2": x, "z2": z}
                o.update(DEFAULTS["road"])
            else:
                length = max(0.5, math.hypot(x - ax, z - az))
                o = {"t": "wall", "x": round((ax + x) / 2, 2), "z": round((az + z) / 2, 2), "w": round(length, 2), "d": 1.0, "h": 30.0,
                     "rot": round(math.degrees(math.atan2(-(z - az), x - ax)), 1), "color": "#ff4444", "tex": "", "invisible": True}
            self.data["objects"].append(o)
            self.pending_road = None
            self.sel = o
        else:
            if tool == "model" and not self.model_file:
                self.pick_model()
                if not self.model_file:
                    return
            self.push_undo()
            o = {"t": tool, "x": x, "z": z}
            o.update(copy.deepcopy(DEFAULTS[tool]))
            if tool == "model":
                o["file"] = self.model_file
            elif tool == "brush":
                o["shape"] = self.cur_shape.get()
                o["tex"] = self.cur_tex
            elif tool == "container":
                o["kind"] = self.cur_kind.get()
            elif tool == "tree" and self.paint.get():
                o["s"] = round(0.8 + (hash((x, z)) % 60) / 100.0, 2)
            if "rot" in o and self.paint.get():
                o["rot"] = float((hash((x, z)) % 360))
            self.data["objects"].append(o)
            self.sel = o
        if not keep_sel:
            self.rebuild_props()
        self.redraw()

    def on_move(self, e):
        if self.view3d:
            self.on_move3d(e)
            return
        if self.painting and self.paint.get() and self.last_paint is not None:
            wx, wz = self.s2w(e.x, e.y)
            try:
                step = max(1.0, float(self.paint_step.get().replace(",", ".")))
            except ValueError:
                step = 6.0
            if math.hypot(wx - self.last_paint[0], wz - self.last_paint[1]) >= step:
                self.last_paint = (wx, wz)
                self.place(self.tool.get(), wx, wz, keep_sel=True)
            return
        if self.pan_start is not None:
            self.pan_move(e)
            return
        if self.sel is not None and self.drag is not None:
            wx, wz = self.s2w(e.x, e.y)
            nx, nz = self.snapv(wx - self.drag[0]), self.snapv(wz - self.drag[1])
            if self.sel.get("_spawn"):
                self.data["spawn"] = [nx, nz]
                self.sel["x"], self.sel["z"] = nx, nz
            else:
                if self.sel["t"] == "road":
                    dx, dz = nx - self.sel["x"], nz - self.sel["z"]
                    self.sel["x2"] += dx
                    self.sel["z2"] += dz
                self.sel["x"], self.sel["z"] = nx, nz
            self.rebuild_props()
            self.redraw()

    def on_up(self, e):
        self.drag = None
        self.pan_start = None
        self.painting = False
        self.drag3d = None

    def pan_down(self, e):
        if self.view3d:
            self.drag3d = ("pan", e.x, e.y, dict(self.cam))
            return
        self.pan_start = (e.x, e.y, self.off[0], self.off[1])

    def pan_move(self, e):
        if self.view3d:
            self.on_move3d(e)
            return
        if self.pan_start is None:
            return
        self.off = [self.pan_start[2] + e.x - self.pan_start[0], self.pan_start[3] + e.y - self.pan_start[1]]
        self.redraw()

    def on_wheel(self, e, delta=None):
        d = delta if delta is not None else (1 if e.delta > 0 else -1)
        if self.view3d:
            self.cam["dist"] = max(10.0, min(900.0, self.cam["dist"] * (0.88 if d > 0 else 1.14)))
            self.redraw()
            return
        if (e.state & 0x1) and self.sel is not None:      # Shift: размер
            self.resize_sel(d)
            return
        wx, wz = self.s2w(e.x, e.y)
        self.zoom = max(0.6, min(40.0, self.zoom * (1.15 if d > 0 else 1 / 1.15)))
        self.off = [e.x - wx * self.zoom, e.y - wz * self.zoom]
        self.redraw()

    # ------------------------------------------------------------------ действия над выделенным
    def delete_sel(self):
        if self.sel is None or self.sel.get("_spawn"):
            return
        self.push_undo()
        self.data["objects"] = [o for o in self.data["objects"] if o is not self.sel]
        self.sel = None
        self.rebuild_props()
        self.redraw()

    def duplicate(self):
        if self.sel is None or self.sel.get("_spawn"):
            return
        self.push_undo()
        o = copy.deepcopy(self.sel)
        o["x"] += 4
        o["z"] += 4
        if o["t"] == "road":
            o["x2"] += 4
            o["z2"] += 4
        self.data["objects"].append(o)
        self.sel = o
        self.rebuild_props()
        self.redraw()

    def rotate_sel(self, deg):
        if self.sel is not None and "rot" in self.sel:
            self.push_undo()
            self.sel["rot"] = (self.sel["rot"] + deg) % 360
            self.rebuild_props()
            self.redraw()

    def resize_sel(self, d):
        o = self.sel
        k = 1.1 if d > 0 else 1 / 1.1
        if "r" in o:
            o["r"] = round(max(2.0, o["r"] * k), 1)
        elif o["t"] == "hill":
            o["h"] = round(o["h"] + (1.0 if d > 0 else -1.0), 1)
        elif o["t"] == "tree":
            o["s"] = round(max(0.3, o["s"] * k), 2)
        elif o["t"] in ("house", "panelka", "wall", "model", "brush"):
            o["w"] = round(max(0.5, o["w"] * k), 1)
            if o["t"] != "wall":
                o["d"] = round(max(0.5, o["d"] * k), 1)
        elif o["t"] == "road":
            o["w"] = round(max(1.0, o["w"] * k), 1)
        self.rebuild_props()
        self.redraw()

    # ------------------------------------------------------------------ панель свойств
    def rebuild_props(self):
        for w in self.props.winfo_children():
            w.destroy()
        o = self.sel
        if o is None:
            ttk.Label(self.props, text="ничего не выбрано").pack(anchor="w")
            return
        ttk.Label(self.props, text=dict(TOOLS + [("spawn", "Старт игроков")]).get(o["t"], o["t"]), foreground="#06c").pack(anchor="w")
        keys = [k for k in o.keys() if k not in ("t", "_spawn", "tex")]
        for k in keys:
            row = ttk.Frame(self.props)
            row.pack(fill="x", pady=1)
            ttk.Label(row, text=k, width=7).pack(side="left")
            v = o[k]
            if isinstance(v, bool):
                var = tk.BooleanVar(value=v)
                ttk.Checkbutton(row, variable=var, command=lambda k=k, var=var: self.set_prop(k, var.get())).pack(side="left")
            elif k in ("kind", "shape"):
                var = tk.StringVar(value=v)
                vals = ["walker", "runner", "spore"] if (k == "kind" and o["t"] == "zombie") else (list(CONT_SIZE.keys()) if k == "kind" else ["box", "cylinder", "sphere", "ramp"])
                cb = ttk.Combobox(row, textvariable=var, values=vals, width=10, state="readonly")
                cb.pack(side="left")
                cb.bind("<<ComboboxSelected>>", lambda e, k=k, var=var: self.set_prop(k, var.get()))
            elif k == "color":
                var = tk.StringVar(value=v)
                ent = ttk.Entry(row, textvariable=var, width=9)
                ent.pack(side="left")
                ent.bind("<Return>", lambda e, k=k, var=var: self.set_prop(k, var.get()))
                ttk.Button(row, text="…", width=2, command=lambda k=k: self.pick_color(k)).pack(side="left")
            else:
                var = tk.StringVar(value=str(v))
                ent = ttk.Entry(row, textvariable=var, width=12)
                ent.pack(side="left")
                ent.bind("<Return>", lambda e, k=k, var=var: self.set_prop(k, var.get()))
                ent.bind("<FocusOut>", lambda e, k=k, var=var: self.set_prop(k, var.get()))
        if o["t"] == "model":
            ttk.Button(self.props, text="Сменить модель…", command=self.change_model).pack(fill="x", pady=2)
        if "tex" in o:
            ttk.Button(self.props, text="Текстура…", command=self.change_tex).pack(fill="x", pady=2)

    def set_prop(self, k, val):
        o = self.sel
        if o is None:
            return
        old = o.get(k)
        try:
            if isinstance(old, bool):
                new = bool(val)
            elif isinstance(old, float) or isinstance(old, int):
                new = float(str(val).replace(",", "."))
            else:
                new = str(val)
        except ValueError:
            return
        if new == old:
            return
        self.push_undo()
        o[k] = new
        if o.get("_spawn") and k in ("x", "z"):
            self.data["spawn"] = [o["x"], o["z"]]
        self.redraw()

    def change_tex(self):
        t = self.ask_texture()
        if t and self.sel is not None:
            self.push_undo()
            self.sel["tex"] = t
            self.rebuild_props()
            self.redraw()

    def pick_color(self, k):
        from tkinter import colorchooser
        c = colorchooser.askcolor(color=self.sel.get(k, "#888888"))[1]
        if c:
            self.set_prop(k, c)
            self.rebuild_props()

    # ------------------------------------------------------------------ модели
    def models_dir(self):
        return os.path.join(self.project, "assets", "models", "maps")

    def copy_model(self, src):
        os.makedirs(self.models_dir(), exist_ok=True)
        dst = os.path.join(self.models_dir(), os.path.basename(src))
        if os.path.abspath(src) != os.path.abspath(dst):
            shutil.copy2(src, dst)
        # .bin/.png рядом с .gltf тоже нужны
        base = os.path.splitext(src)[0]
        if src.lower().endswith(".gltf"):
            for ext in (".bin",):
                if os.path.exists(base + ext):
                    shutil.copy2(base + ext, self.models_dir())
        return "maps/" + os.path.basename(src)

    def pick_model(self):
        p = filedialog.askopenfilename(title="Модель", filetypes=[("3D модели", "*.glb *.gltf"), ("Все", "*.*")])
        if not p:
            return
        self.model_file = self.copy_model(p)
        self.model_lbl.config(text="модель: " + self.model_file)
        self.tool.set("model")
        self.set_status("Модель скопирована в проект. Кликните на карте, чтобы поставить.")

    def change_model(self):
        p = filedialog.askopenfilename(title="Модель", filetypes=[("3D модели", "*.glb *.gltf")])
        if p and self.sel is not None:
            self.push_undo()
            self.sel["file"] = self.copy_model(p)
            self.rebuild_props()
            self.redraw()

    # ------------------------------------------------------------------ файлы
    def maps_dir(self):
        d = os.path.join(self.project, "maps")
        os.makedirs(d, exist_ok=True)
        return d

    def pick_project(self):
        d = filedialog.askdirectory(title="Папка проекта (где project.godot)", initialdir=self.project)
        if d:
            self.project = d
            self.proj_lbl.config(text=d)

    def new_map(self):
        if self.dirty and not messagebox.askyesno("Новая карта", "Несохранённые изменения будут потеряны. Продолжить?"):
            return
        self.data = {"name": "моя_карта", "spawn": [0.0, 0.0], "bounds": 150.0, "objects": []}
        self.name = "моя_карта"
        self.sel = None
        self.undo_stack.clear()
        self.dirty = False
        self.rebuild_props()
        self.redraw()

    def open_map(self):
        p = filedialog.askopenfilename(initialdir=self.maps_dir(), filetypes=[("Карты", "*.json")])
        if not p:
            return
        try:
            with open(p, encoding="utf-8") as f:
                d = json.load(f)
            d.setdefault("spawn", [0.0, 0.0])
            d.setdefault("objects", [])
        except Exception as ex:
            messagebox.showerror("Ошибка", str(ex))
            return
        self.data = d
        self.name = os.path.splitext(os.path.basename(p))[0]
        self.sel = None
        self.undo_stack.clear()
        self.dirty = False
        self.rebuild_props()
        self.redraw()
        self.set_status("Открыто: " + self.name)

    def save_map(self):
        name = simpledialog.askstring("Сохранить", "Имя карты (латиница/цифры, без пробелов лучше):", initialvalue=self.name, parent=self.root)
        if not name:
            return
        self.name = name.strip()
        self.data["name"] = self.name
        path = os.path.join(self.maps_dir(), self.name + ".json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=1)
        self.dirty = False
        self.set_status("Сохранено: " + path)
        messagebox.showinfo("Сохранено", "Карта сохранена:\n%s\n\nВ игре: Играть → Тип карты → «★ Своя карта: %s»" % (path, self.name))

    def on_close(self):
        if self.dirty and not messagebox.askyesno("Выход", "Есть несохранённые изменения. Выйти?"):
            return
        self.root.destroy()

    # ------------------------------------------------------------------ рельеф + 3D вид
    def gh_raw(self, x, z):
        h = 0.0
        for o in self.data["objects"]:
            if o["t"] == "hill":
                d = math.hypot(x - o["x"], z - o["z"])
                if d < o["r"]:
                    t = 1.0 - d / o["r"]
                    h += o["h"] * t * t * (3 - 2 * t)
        return h

    def build_flats(self):
        self._flats = []
        for o in self.data["objects"]:
            if o["t"] in ("house", "panelka") or (o["t"] == "brush" and o.get("flat")):
                rr = max(o["w"], o["d"]) * 0.75 + 2.0
                self._flats.append((o["x"], o["z"], rr, self.gh_raw(o["x"], o["z"])))

    def gh(self, x, z):
        for fx, fz, fr, fh in self._flats:
            d = math.hypot(x - fx, z - fz)
            if d < fr:
                return fh
            if d < fr + 5.0:
                k = (d - fr) / 5.0
                return fh + (self.gh_raw(x, z) - fh) * k * k * (3 - 2 * k)
        return self.gh_raw(x, z)

    def toggle3d(self):
        self.view3d = not self.view3d
        self.btn3d.config(text="2D вид (редактирование)" if self.view3d else "3D вид (просмотр)")
        if self.view3d:
            self.cam["dist"] = max(120.0, self.bound() * 1.5)
            self.set_status("3D: ЛКМ — вращать, ПКМ/СКМ — двигать, колесо — приближение. Редактирование — в 2D виде.")
        self.redraw()

    def on_move3d(self, e):
        if self.drag3d is None:
            return
        kind, x0, y0, cam0 = self.drag3d
        dx, dy = e.x - x0, e.y - y0
        if kind == "orbit":
            self.cam["yaw"] = cam0["yaw"] - dx * 0.008
            self.cam["pitch"] = max(0.05, min(1.5, cam0["pitch"] + dy * 0.008))
        else:
            k = cam0["dist"] * 0.0016
            cy = cam0["yaw"]
            self.cam["tx"] = cam0["tx"] - (math.cos(cy) * dx + math.sin(cy) * dy) * k
            self.cam["tz"] = cam0["tz"] + (math.sin(cy) * dx - math.cos(cy) * dy) * k
        self.redraw()

    # --- проекция
    def _cam_setup(self):
        cm = self.cam
        cp, sp = math.cos(cm["pitch"]), math.sin(cm["pitch"])
        pos = (cm["tx"] + cm["dist"] * cp * math.sin(cm["yaw"]), cm["ty"] + cm["dist"] * sp, cm["tz"] + cm["dist"] * cp * math.cos(cm["yaw"]))
        fw = (cm["tx"] - pos[0], cm["ty"] - pos[1], cm["tz"] - pos[2])
        fl = math.sqrt(sum(v * v for v in fw))
        fw = tuple(v / fl for v in fw)
        rt = (-fw[2], 0.0, fw[0])            # fw × up(0,1,0), нормируем
        rl = math.hypot(rt[0], rt[2]) or 1.0
        rt = (rt[0] / rl, 0.0, rt[2] / rl)
        up = (rt[1] * fw[2] - rt[2] * fw[1], rt[2] * fw[0] - rt[0] * fw[2], rt[0] * fw[1] - rt[1] * fw[0])
        up = (-up[0], -up[1], -up[2]) if up[1] < 0 else up
        self._cp = (pos, fw, rt, up)

    def proj(self, p):
        pos, fw, rt, up = self._cp
        v = (p[0] - pos[0], p[1] - pos[1], p[2] - pos[2])
        z = v[0] * fw[0] + v[1] * fw[1] + v[2] * fw[2]
        if z < 1.0:
            return None
        x = v[0] * rt[0] + v[1] * rt[1] + v[2] * rt[2]
        y = v[0] * up[0] + v[1] * up[1] + v[2] * up[2]
        H = max(self.canvas.winfo_height(), 300)
        W = max(self.canvas.winfo_width(), 300)
        f = H * 0.95
        return (W / 2 + x / z * f, H / 2 - y / z * f, z)

    @staticmethod
    def _shade(col, k):
        try:
            r, g, b = int(col[1:3], 16), int(col[3:5], 16), int(col[5:7], 16)
        except (ValueError, TypeError):
            r, g, b = 150, 150, 150
        k = max(0.25, min(1.3, k))
        return "#%02x%02x%02x" % (min(255, int(r * k)), min(255, int(g * k)), min(255, int(b * k)))

    def _poly(self, out, pts3, color, light=1.0, cull=True, bias=0.0, outline=""):
        pr = [self.proj(p) for p in pts3]
        if any(p is None for p in pr):
            return
        # отсечение задних граней (по порядку обхода на экране)
        if cull:
            area = 0.0
            for i in range(len(pr)):
                x1, y1, _ = pr[i]
                x2, y2, _ = pr[(i + 1) % len(pr)]
                area += x1 * y2 - x2 * y1
            if area > 0:
                return
        depth = sum(p[2] for p in pr) / len(pr) - bias
        out.append((depth, [c for p in pr for c in p[:2]], self._shade(color, light), outline))

    def _box3(self, out, cx, cz, y0, w, d, h, rot_deg, color, bias=2.0):
        a = math.radians(rot_deg)
        ca, sa = math.cos(a), math.sin(a)

        def P(lx, ly, lz):
            return (cx + lx * ca + lz * sa, y0 + ly, cz - lx * sa + lz * ca)
        hx, hz = w / 2, d / 2
        v = {n: P(*c) for n, c in {"a": (-hx, 0, -hz), "b": (hx, 0, -hz), "c": (hx, 0, hz), "d": (-hx, 0, hz),
                                   "A": (-hx, h, -hz), "B": (hx, h, -hz), "C": (hx, h, hz), "D": (-hx, h, hz)}.items()}
        faces = [("ABCD", 1.15), ("abBA", 0.8), ("bcCB", 0.65), ("cdDC", 0.75), ("daAD", 0.6)]
        for names, light in faces:
            self._poly(out, [v[n] for n in names], color, light, True, bias, "#202020")

    def _prism3(self, out, cx, cz, y0, r, h, color, seg=10, top_r=None, bias=2.0):
        top_r = r if top_r is None else top_r
        for i in range(seg):
            a0, a1 = 2 * math.pi * i / seg, 2 * math.pi * (i + 1) / seg
            p0 = (cx + r * math.cos(a0), y0, cz + r * math.sin(a0))
            p1 = (cx + r * math.cos(a1), y0, cz + r * math.sin(a1))
            q1 = (cx + top_r * math.cos(a1), y0 + h, cz + top_r * math.sin(a1))
            q0 = (cx + top_r * math.cos(a0), y0 + h, cz + top_r * math.sin(a0))
            self._poly(out, [p0, q0, q1, p1], color, 0.7 + 0.5 * math.cos(a0 - 0.8), True, bias)
        if top_r > 0.01:
            self._poly(out, [(cx + top_r * math.cos(2 * math.pi * i / seg), y0 + h, cz + top_r * math.sin(2 * math.pi * i / seg)) for i in range(seg)], color, 1.15, True, bias)

    def draw3d(self):
        import random
        c = self.canvas
        W, H = c.winfo_width(), c.winfo_height()
        c.create_rectangle(0, 0, W, H, fill="#9fc3e8", outline="")
        c.create_rectangle(0, H * 0.5, W, H, fill="#b9d6ee", outline="")
        self.build_flats()
        self._cam_setup()
        out = []
        bd = self.bound()
        ga = self.data.get("ground_a") if self._ok_color(self.data.get("ground_a")) else "#335722"
        gb = self.data.get("ground_b") if self._ok_color(self.data.get("ground_b")) else "#476e2b"
        step = max(4.0, bd / 28.0)
        n = int(bd * 2 / step)
        hs = [[self.gh(-bd + i * step, -bd + j * step) for i in range(n + 1)] for j in range(n + 1)]
        for j in range(n):
            for i in range(n):
                x0, z0 = -bd + i * step, -bd + j * step
                p = [(x0, hs[j][i], z0), (x0 + step, hs[j][i + 1], z0), (x0 + step, hs[j + 1][i + 1], z0 + step), (x0, hs[j + 1][i], z0 + step)]
                slope = (hs[j][i + 1] - hs[j][i]) * 0.25 + (hs[j + 1][i] - hs[j][i]) * 0.1
                avg = sum(q[1] for q in p) / 4.0
                base = ga if (i + j) % 2 == 0 else gb
                self._poly(out, p, base, 1.0 - slope + avg * 0.02, False, -4.0)
        # зоны
        def disc(o, color, y, bias, seg=28):
            pts = [(o["x"] + o["r"] * math.cos(2 * math.pi * i / seg), max(y, self.gh(o["x"] + o["r"] * math.cos(2 * math.pi * i / seg), o["z"] + o["r"] * math.sin(2 * math.pi * i / seg)) + 0.15), o["z"] + o["r"] * math.sin(2 * math.pi * i / seg)) for i in range(seg)]
            self._poly(out, pts, color, 1.0, False, bias)
        rnd = random.Random(1)
        for o in self.data["objects"]:
            t = o["t"]
            gy = self.gh(o["x"], o["z"])
            if t == "lake":
                disc(o, "#3a78b5", 0.12, 3.0)
            elif t == "swamp":
                disc(o, "#4d5a2a", 0.12, 3.5)
            elif t == "forest":
                disc(o, "#2f5a22", 0.1, 3.5)
                cnt = min(60, int(math.pi * o["r"] ** 2 / 60))
                for _ in range(cnt):
                    a, rr = rnd.random() * 6.283, math.sqrt(rnd.random()) * o["r"]
                    tx, tz = o["x"] + math.cos(a) * rr, o["z"] + math.sin(a) * rr
                    ty = self.gh(tx, tz)
                    self._prism3(out, tx, tz, ty, 1.6, 5.0, "#2e7d32", 6, 0.0)
            elif t == "road":
                L = math.hypot(o["x2"] - o["x"], o["z2"] - o["z"]) or 1.0
                segs = max(1, int(L / 6))
                dx, dz = (o["x2"] - o["x"]) / L, (o["z2"] - o["z"]) / L
                hw = o["w"] / 2
                for k in range(segs):
                    a0, a1 = L * k / segs, L * (k + 1) / segs
                    pa = (o["x"] + dx * a0, o["z"] + dz * a0)
                    pb = (o["x"] + dx * a1, o["z"] + dz * a1)
                    quad = []
                    for (px, pz), sgn in ((pa, 1), (pb, 1), (pb, -1), (pa, -1)):
                        qx, qz = px - dz * hw * sgn, pz + dx * hw * sgn
                        quad.append((qx, self.gh(qx, qz) + 0.2, qz))
                    self._poly(out, quad, "#8c7355", 1.0, False, 2.5)
            elif t == "house":
                w, d = o["w"], o["d"]
                self._box3(out, o["x"], o["z"], gy, w, d, 3.0, o["rot"], o.get("color", "#c9b79c"))
                self._box3(out, o["x"], o["z"], gy + 3.0, w + 0.6, d + 0.6, 0.5, o["rot"], "#5a3a2a")
            elif t == "panelka":
                fl = int(o.get("floors", 5))
                self._box3(out, o["x"], o["z"], gy, o["w"], o["d"], 3.0 * fl, o["rot"], o.get("color", "#a9a59b"))
            elif t == "wall":
                col = "#ff6666" if o.get("invisible") else o.get("color", "#888888")
                self._box3(out, o["x"], o["z"], gy, o["w"], o["d"], min(o["h"], 12.0), o["rot"], col)
            elif t == "brush":
                y0 = gy + o.get("y", 0.0)
                col = o.get("color", "#9a9a9a")
                sh = o.get("shape", "box")
                if sh == "cylinder":
                    self._prism3(out, o["x"], o["z"], y0, o["w"] / 2, o["h"], col, 12)
                elif sh == "sphere":
                    self._prism3(out, o["x"], o["z"], y0, o["w"] / 2, o["w"], col, 10, o["w"] * 0.22)
                elif sh == "ramp":
                    self._ramp3(out, o, y0, col)
                else:
                    self._box3(out, o["x"], o["z"], y0, o["w"], o["d"], o["h"], o["rot"], col)
            elif t == "container":
                cw, cd = CONT_SIZE.get(o.get("kind", "crate"), (1, 1))
                hh = {"crate": 0.7, "barrel": 0.9, "cabinet": 1.7, "locker": 1.8, "fridge": 1.7, "car": 1.35}.get(o.get("kind"), 1.0)
                self._box3(out, o["x"], o["z"], gy, cw, cd, hh, o.get("rot", 0.0), "#c08a3a", 1.0)
            elif t == "tree":
                s_ = o.get("s", 1.0)
                self._prism3(out, o["x"], o["z"], gy, 0.3 * s_, 1.5 * s_, "#5a3a1a", 6, bias=1.0)
                self._prism3(out, o["x"], o["z"], gy + 1.2 * s_, 1.8 * s_, 4.0 * s_, "#2e7d32", 8, 0.0, 1.0)
            elif t == "model":
                self._box3(out, o["x"], o["z"], gy + o.get("y", 0.0), o["w"], o["d"], o.get("h", 2.0), o.get("rot", 0.0), "#d070d0")
            elif t == "zombie":
                self._prism3(out, o["x"], o["z"], gy, 0.4, 1.8, {"walker": "#c0392b", "runner": "#e67e22", "spore": "#a4c639"}.get(o.get("kind"), "#c0392b"), 6, bias=1.0)
            elif t == "loot":
                self._box3(out, o["x"], o["z"], gy, 0.5, 0.5, 0.5, 0, "#ffd23f", 1.0)
        sx, sz = self.data["spawn"]
        self._prism3(out, sx, sz, self.gh(sx, sz), 1.2, 6.0, "#2ecc71", 8, 0.0, 1.0)
        out.sort(key=lambda e: -e[0])
        for depth, pts, fill, outline in out:
            c.create_polygon(pts, fill=fill, outline=outline or fill)
        c.create_text(10, H - 10, anchor="sw", fill="#222", text="3D просмотр  |  ЛКМ — вращать, ПКМ/СКМ — двигать, колесо — приближать  |  объектов: %d" % len(self.data["objects"]))

    def _ramp3(self, out, o, y0, col):
        a = math.radians(o.get("rot", 0.0))
        ca, sa = math.cos(a), math.sin(a)
        w, d, h = o["w"], o["d"], o["h"]

        def P(lx, ly, lz):
            return (o["x"] + lx * ca + lz * sa, y0 + ly, o["z"] - lx * sa + lz * ca)
        A, B, C, D = P(-w / 2, 0, -d / 2), P(w / 2, 0, -d / 2), P(w / 2, 0, d / 2), P(-w / 2, 0, d / 2)
        At, Bt = P(-w / 2, h, -d / 2), P(w / 2, h, -d / 2)
        for pts, light in (([At, Bt, C, D], 1.15), ([A, At, Bt, B], 0.7), ([A, D, At], 0.6), ([B, Bt, C], 0.65)):
            self._poly(out, pts, col, light, False, 2.0, "#202020")

    # ------------------------------------------------------------------ отрисовка
    def redraw(self):
        c = self.canvas
        c.delete("all")
        W, H = c.winfo_width(), c.winfo_height()
        if self.view3d:
            self.draw3d()
            return
        bd = self.bound()
        x0, z0 = self.w2s(-bd, -bd)
        x1, z1 = self.w2s(bd, bd)
        c.create_rectangle(x0, z0, x1, z1, fill=self.data.get("ground_a", "#3c5a32") if self._ok_color(self.data.get("ground_a")) else "#3c5a32", outline="#e0c060", width=2)
        # сетка
        step = 10.0 if self.zoom >= 2.5 else 50.0
        k = -bd
        while k <= bd:
            sx, sz = self.w2s(k, k)
            major = abs(k) % 50 < 0.01
            c.create_line(sx, z0, sx, z1, fill="#4d7040" if major else "#436638")
            c.create_line(x0, sz, x1, sz, fill="#4d7040" if major else "#436638")
            k += step
        sx, sz = self.w2s(0, 0)
        c.create_line(sx, z0, sx, z1, fill="#7aa86a")
        c.create_line(x0, sz, x1, sz, fill="#7aa86a")
        # объекты: сначала зоны/дороги, потом остальное
        layers = {"hill": -1, "forest": 0, "swamp": 0, "lake": 1, "road": 2}
        for o in sorted(self.data["objects"], key=lambda o: layers.get(o["t"], 3)):
            self.draw_obj(o, o is self.sel)
        # старт
        sx, sz = self.w2s(*self.data["spawn"])
        sel = self.sel is not None and self.sel.get("_spawn")
        c.create_oval(sx - 9, sz - 9, sx + 9, sz + 9, fill=COLORS["spawn"], outline="white" if sel else "black", width=3 if sel else 1)
        c.create_text(sx, sz, text="S", font=("", 10, "bold"))
        # превью дороги
        if self.pending_road is not None:
            ax, az = self.w2s(*self.pending_road)
            c.create_line(ax, az, self.mouse[0], self.mouse[1], fill="#ffd9a0", dash=(4, 3), width=3)
        c.create_text(10, H - 10, anchor="sw", fill="#dddddd", text="масштаб %.1f px/м    объектов: %d" % (self.zoom, len(self.data["objects"])))

    @staticmethod
    def _ok_color(c):
        try:
            return bool(c) and len(c) == 7 and c.startswith("#") and int(c[1:], 16) >= 0
        except ValueError:
            return False

    def draw_obj(self, o, selected):
        c = self.canvas
        t = o["t"]
        outline = "white" if selected else "#222222"
        width = 3 if selected else 1
        sx, sz = self.w2s(o["x"], o["z"])
        col = COLORS.get(t, "#fff")
        if t in ("forest", "lake", "swamp"):
            r = o["r"] * self.zoom
            c.create_oval(sx - r, sz - r, sx + r, sz + r, fill=col, outline=outline, width=width, stipple="gray50" if t == "forest" else "")
            c.create_text(sx, sz, text={"forest": "лес", "lake": "озеро", "swamp": "болото"}[t], fill="white")
        elif t == "hill":
            neg = o["h"] < 0
            for f in (1.0, 0.66, 0.33):
                r = o["r"] * self.zoom * f
                c.create_oval(sx - r, sz - r, sx + r, sz + r, outline="#3b2a15" if neg else "#e0c890", width=width if f == 1.0 else 1, dash=(3, 3) if neg else None)
            c.create_text(sx, sz, text="%+.0f м" % o["h"], fill="white")
        elif t == "tree":
            r = max(3.0, 1.6 * o.get("s", 1.0) * self.zoom)
            c.create_oval(sx - r, sz - r, sx + r, sz + r, fill="#2e7d32", outline=outline, width=width)
        elif t == "container":
            cw, cd = CONT_SIZE.get(o.get("kind", "crate"), (1, 1))
            pts = []
            for px, pz in self.rect_corners({"x": o["x"], "z": o["z"], "w": cw, "d": cd, "rot": o.get("rot", 0.0)}):
                pts.extend(self.w2s(px, pz))
            c.create_polygon(pts, fill=COLORS["container"], outline=outline, width=width)
            if self.zoom > 3:
                c.create_text(sx, sz, text=o.get("kind", ""), fill="#111", font=("", 7))
        elif t in ("house", "panelka", "wall", "model", "brush"):
            pts = []
            for px, pz in self.rect_corners(o):
                pts.extend(self.w2s(px, pz))
            fill = o.get("color", col) if t not in ("model",) else col
            if t == "wall" and o.get("invisible"):
                fill = "#ff4444"
            if not self._ok_color(fill):
                fill = col
            c.create_polygon(pts, fill=fill, outline=outline, width=width)
            label = {"house": "дом", "panelka": "панелька", "wall": "", "brush": o.get("shape", ""), "model": os.path.basename(o.get("file", "")) or "модель?"}[t]
            if label and self.zoom > 2:
                c.create_text(sx, sz, text=label, fill="#111", font=("", 8))
            if t in ("house", "panelka"):   # «дверь» — направление поворота
                a = math.radians(o.get("rot", 0.0))
                fx, fz = o["x"] + math.sin(a) * o["d"] / 2, o["z"] + math.cos(a) * o["d"] / 2
                px, pz = self.w2s(fx, fz)
                c.create_oval(px - 3, pz - 3, px + 3, pz + 3, fill="#553311")
        elif t == "road":
            bx, bz = self.w2s(o["x2"], o["z2"])
            c.create_line(sx, sz, bx, bz, fill="white" if selected else col, width=max(2, o["w"] * self.zoom), capstyle="butt")
        elif t == "loot":
            c.create_rectangle(sx - 5, sz - 5, sx + 5, sz + 5, fill=col, outline=outline, width=width)
        elif t == "zombie":
            fill = {"walker": "#c0392b", "runner": "#e67e22", "spore": "#a4c639"}.get(o.get("kind"), col)
            c.create_oval(sx - 6, sz - 6, sx + 6, sz + 6, fill=fill, outline=outline, width=width)
            c.create_text(sx, sz, text="Z", fill="white", font=("", 8, "bold"))


def main():
    root = tk.Tk()
    Editor(root)
    root.mainloop()


if __name__ == "__main__":
    main()
