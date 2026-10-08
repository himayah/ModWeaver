"""ModWeaver の GUI（tkinter / ttk。DESIGN.md §12）。

画面の組み立てと操作だけを持ち、CLI の呼び出し・引数の組み立て・結果の解釈は ``bridge`` に任せる。
表示言語を切り替えたり、起動時にジャンル一覧を読み終えたりしたら、画面を作り直す（``_build``）。
設定は tk の変数に、作った曲は ``self.songs`` に持つので、作り直しても残る。
"""
from __future__ import annotations

import queue
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from tkinter import font as tkfont
from typing import Callable, Optional

from . import bridge
from .bridge import Catalog, Genre, Outcome, Request, SongResult, Voice
from .texts import LANGUAGES, TEXTS, default_language

POLL_MS = 50


class App(tk.Tk):
    def __init__(self, lang: Optional[str] = None) -> None:
        super().__init__()
        self.lang = tk.StringVar(value=lang or default_language())
        self.catalog: Optional[Catalog] = None
        self.load_error: Optional[str] = None
        self.songs: list[tuple[str, SongResult]] = []     # (時刻, 結果)。新しい順
        self.job: Optional[bridge.Job] = None
        self.events: queue.Queue = queue.Queue()          # 別スレッド → 画面スレッド

        # 設定（画面を作り直しても残る）
        self.genre_id = tk.StringVar()
        self.random_genre = tk.BooleanVar(value=False)
        self.search = tk.StringVar()
        self.category = tk.StringVar(value="")            # "" はすべて
        self.tempo_mode = tk.StringVar(value="auto")      # auto | fixed | range
        self.tempo_fixed = tk.StringVar(value="120")
        self.tempo_lo = tk.StringVar(value="80")
        self.tempo_hi = tk.StringVar(value="120")
        self.channels = tk.StringVar(value="auto")        # auto | チャンネル数（形式による。上限か、MOD の選択肢）
        self.channel_limit = tk.StringVar(value="")       # 上限を指定する形式（XM・S3M・IT・MP3）の入力欄
        self.seed_random = tk.BooleanVar(value=True)
        self.seed = tk.StringVar()
        self.fmt = tk.StringVar()
        self.output_dir = tk.StringVar(value=str(bridge.DEFAULT_OUTPUT_DIR))
        self.status = tk.StringVar()
        self.voices: list[Voice] = []                    # --list-voices --json（取り込み済みの声）
        self.voice = tk.StringVar(value="")              # "" は歌声なし
        self.lyrics = ""                                 # 歌詞の入力（画面を作り直しても残す）

        self.title("ModWeaver")
        self.geometry("1040x760")
        self.minsize(900, 640)
        self._setup_style()
        self.search.trace_add("write", lambda *_: self._fill_genre_tree())
        self.lang.trace_add("write", lambda *_: self._build())
        self.protocol("WM_DELETE_WINDOW", self._quit)

        self._build()
        self._fit_to_content()
        self._load_catalog()
        self.after(POLL_MS, self._poll)

    # ------------------------------------------------------------------
    # 共通
    # ------------------------------------------------------------------

    def _fit_to_content(self) -> None:
        """初期サイズが内容より小さいと下のログ欄が潰れるので、画面に収まる範囲で広げる。"""
        self.update_idletasks()
        w = min(max(1040, self.winfo_reqwidth()), self.winfo_screenwidth() - 80)
        h = min(max(760, self.winfo_reqheight()), self.winfo_screenheight() - 120)
        self.geometry(f"{w}x{h}")

    def t(self, key: str, **kw) -> str:
        text = TEXTS[self.lang.get()][key]
        return text.format(**kw) if kw else text

    def _setup_style(self) -> None:
        style = ttk.Style(self)
        if sys.platform.startswith("linux") and "clam" in style.theme_names():
            style.theme_use("clam")        # Linux の既定テーマ（default）は古く見えるので
        base = tkfont.nametofont("TkDefaultFont")
        self.font_title = base.copy()
        self.font_title.configure(size=base.cget("size") + 4, weight="bold")
        self.font_bold = base.copy()
        self.font_bold.configure(weight="bold")
        style.configure("Title.TLabel", font=self.font_title)
        style.configure("Bold.TLabel", font=self.font_bold)
        style.configure("Muted.TLabel", foreground="gray40")
        style.configure("Warn.TLabel", foreground="#b35900")

    def _post(self, fn: Callable[[], None]) -> None:
        """別スレッドから画面の処理を頼む。"""
        self.events.put(fn)

    def _poll(self) -> None:
        try:
            while True:
                self.events.get_nowait()()
        except queue.Empty:
            pass
        self.after(POLL_MS, self._poll)

    def _quit(self) -> None:
        if self.job is not None:
            self.job.cancel()
        self.destroy()

    # ------------------------------------------------------------------
    # 起動時のジャンル一覧
    # ------------------------------------------------------------------

    def _load_catalog(self) -> None:
        self.status.set(self.t("loading"))

        def work() -> None:
            try:
                catalog, error = bridge.load_catalog(), None
            except Exception as e:                        # CLI が動かない・JSON が壊れている
                catalog, error = None, str(e)
            voices = bridge.load_voices() if catalog is not None and catalog.voice_formats else []
            self._post(lambda: self._on_catalog(catalog, error, voices))

        threading.Thread(target=work, daemon=True).start()

    def _on_catalog(self, catalog: Optional[Catalog], error: Optional[str], voices: Optional[list] = None) -> None:
        self.catalog, self.load_error = catalog, error
        self.voices = list(voices or [])
        if catalog is not None:
            if not self.genre_id.get():
                self.genre_id.set(catalog.default_genre)
                self._apply_genre_tempo()
            if not self.fmt.get():
                self.fmt.set(catalog.default_format)
            self.status.set(self.t("ready"))
        else:
            self.status.set(self.t("load_failed"))
        self._build()
        if error:
            messagebox.showerror(self.t("error"), f"{self.t('load_failed')}\n\n{error}", parent=self)

    # ------------------------------------------------------------------
    # 画面の組み立て
    # ------------------------------------------------------------------

    def _build(self) -> None:
        for w in self.winfo_children():
            w.destroy()
        self.title(self.t("title"))
        self._build_menu()

        root = ttk.Frame(self, padding=8)
        root.pack(fill=tk.BOTH, expand=True)
        paned = ttk.PanedWindow(root, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)
        left = ttk.Frame(paned, padding=(0, 0, 6, 0))
        right = ttk.Frame(paned, padding=(6, 0, 0, 0))
        paned.add(left, weight=1)
        paned.add(right, weight=3)

        self._build_genre_list(left)
        self._build_genre_detail(right)
        self._build_settings(right)
        self._build_actions(right)
        self._build_results(right)

        self._fill_genre_tree()
        self._on_genre_changed()
        self._fill_history()
        self._set_running(self.job is not None)

    def _build_menu(self) -> None:
        menubar = tk.Menu(self)
        m_file = tk.Menu(menubar, tearoff=0)
        m_file.add_command(label=self.t("menu_open_folder"), command=self._open_output_dir)
        m_file.add_separator()
        m_file.add_command(label=self.t("menu_quit"), command=self._quit)
        menubar.add_cascade(label=self.t("menu_file"), menu=m_file)

        m_view = tk.Menu(menubar, tearoff=0)
        m_lang = tk.Menu(m_view, tearoff=0)
        for code, name in LANGUAGES:
            m_lang.add_radiobutton(label=name, value=code, variable=self.lang)
        m_view.add_cascade(label=self.t("menu_language"), menu=m_lang)
        menubar.add_cascade(label=self.t("menu_view"), menu=m_view)

        m_help = tk.Menu(menubar, tearoff=0)
        m_help.add_command(label=self.t("menu_cli_help"), command=self._show_cli_help)
        m_help.add_command(label=self.t("menu_about"), command=self._show_about)
        menubar.add_cascade(label=self.t("menu_help"), menu=m_help)
        self.config(menu=menubar)

    # --- ジャンル一覧（左） ---

    def _build_genre_list(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text=self.t("genres"), style="Bold.TLabel").pack(anchor="w")
        row = ttk.Frame(parent)
        row.pack(fill=tk.X, pady=(4, 2))
        ttk.Label(row, text=self.t("search")).pack(side=tk.LEFT)
        ttk.Entry(row, textvariable=self.search).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 0))

        labels = [self.t("all_categories")]
        ids = [""]
        if self.catalog:
            for cid, ja, en in self.catalog.categories:
                ids.append(cid)
                labels.append(en if self.lang.get() == "en" else ja)
        cat = ttk.Combobox(parent, values=labels, state="readonly")
        cat.current(ids.index(self.category.get()) if self.category.get() in ids else 0)
        cat.bind("<<ComboboxSelected>>", lambda e: (self.category.set(ids[cat.current()]), self._fill_genre_tree()))
        cat.pack(fill=tk.X, pady=(0, 4))

        box = ttk.Frame(parent)
        box.pack(fill=tk.BOTH, expand=True)
        self.genre_tree = ttk.Treeview(box, show="tree", selectmode="browse")
        self.genre_tree.column("#0", width=320)        # 「id — 表示名」が切れない幅
        scroll = ttk.Scrollbar(box, command=self.genre_tree.yview)
        self.genre_tree.configure(yscrollcommand=scroll.set)
        self.genre_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.genre_tree.bind("<<TreeviewSelect>>", self._on_tree_select)

        ttk.Checkbutton(parent, text=self.t("random_genre"), variable=self.random_genre,
                        command=self._on_genre_changed).pack(anchor="w", pady=(6, 0))

    def _fill_genre_tree(self) -> None:
        tree = getattr(self, "genre_tree", None)
        if tree is None or not tree.winfo_exists():
            return
        tree.delete(*tree.get_children())
        if not self.catalog:
            return
        lang, words = self.lang.get(), self.search.get().lower().split()
        for cid, ja, en in self.catalog.categories:
            if self.category.get() not in ("", cid):
                continue
            genres = [g for g in self.catalog.genres if g.category == cid and self._matches(g, words)]
            if not genres:
                continue
            node = tree.insert("", tk.END, iid=f"cat:{cid}", text=en if lang == "en" else ja, open=True)
            for g in genres:
                tree.insert(node, tk.END, iid=g.id, text=f"{g.id}  —  {g.display_name}")
        if tree.exists(self.genre_id.get()):
            tree.selection_set(self.genre_id.get())
            tree.see(self.genre_id.get())

    def _matches(self, g: Genre, words: list[str]) -> bool:
        hay = " ".join((g.id, g.display_name, *g.aliases, g.description, g.description_en)).lower()
        return all(w in hay for w in words)

    def _on_tree_select(self, _event=None) -> None:
        sel = self.genre_tree.selection()
        if sel and not sel[0].startswith("cat:") and sel[0] != self.genre_id.get():
            self.genre_id.set(sel[0])
            self.random_genre.set(False)
            self._apply_genre_tempo()
            self._on_genre_changed()

    # --- ジャンルの説明（右上） ---

    def _build_genre_detail(self, parent: ttk.Frame) -> None:
        box = ttk.Frame(parent)
        box.pack(fill=tk.X)
        self.detail_title = ttk.Label(box, style="Title.TLabel")
        self.detail_title.pack(anchor="w")
        self.detail_meta = ttk.Label(box, style="Muted.TLabel")
        self.detail_meta.pack(anchor="w")
        self.detail_desc = ttk.Label(box, wraplength=640, justify=tk.LEFT)
        self.detail_desc.pack(anchor="w", pady=(4, 0), fill=tk.X)
        box.bind("<Configure>", lambda e: self.detail_desc.configure(wraplength=max(200, e.width - 8)))

    def _current_genre(self) -> Optional[Genre]:
        if self.catalog is None or self.random_genre.get():
            return None
        return self.catalog.genre(self.genre_id.get())

    def _on_genre_changed(self) -> None:
        if not hasattr(self, "detail_title") or not self.detail_title.winfo_exists():
            return
        lang, g = self.lang.get(), self._current_genre()
        if self.catalog is None:
            self.detail_title.configure(text=self.load_error and self.t("load_failed") or self.t("loading"))
            self.detail_meta.configure(text="")
            self.detail_desc.configure(text=self.load_error or "")
        elif self.random_genre.get():
            self.detail_title.configure(text=self.t("random_genre"))
            self.detail_meta.configure(text="")
            self.detail_desc.configure(text=self.t("random_genre_desc"))
        elif g is not None:
            meta = [f"{g.id}", f"{self.t('category')}: {self.catalog.category_label(g.category, lang)}"]
            if g.aliases:
                meta.append(f"{self.t('aliases')}: {', '.join(g.aliases)}")
            meta.append(self.t("usual_tempo", lo=g.usual_tempo[0], hi=g.usual_tempo[1], typ=g.typical_tempo))
            if not self.catalog.is_full_tempo_range(g):
                meta.append(self.t("tempo_limit", lo=g.tempo_range[0], hi=g.tempo_range[1]))
            meta.append(self.t("channel_choices", choices="/".join(map(str, g.mod_channels))))
            self.detail_title.configure(text=g.display_name)
            self.detail_meta.configure(text="   ·   ".join(meta))
            self.detail_desc.configure(text=g.describe(lang))
        self._update_channel_buttons()
        self._update_tempo_bounds()
        self._update_voice_state()

    def _apply_genre_tempo(self) -> None:
        """ユーザーがジャンルを選んだとき、テンポの入力の初期値をそのジャンルに合わせる
        （固定＝代表的なテンポ、範囲＝ふだん使う範囲）。画面の作り直しでは呼ばない（入力を消さないため）。"""
        g = self._current_genre()
        if g is not None:
            self.tempo_fixed.set(str(g.typical_tempo))
            self.tempo_lo.set(str(g.usual_tempo[0]))
            self.tempo_hi.set(str(g.usual_tempo[1]))

    def _update_tempo_bounds(self) -> None:
        """テンポの入力欄の上下限を、ジャンルが受け付ける範囲にする。"""
        if self.catalog is None:
            return
        lo, hi = self.catalog.tempo_bounds(self._current_genre())
        for s in getattr(self, "tempo_spins", ()):
            s.configure(from_=lo, to=hi)

    # --- 設定 ---

    def _build_settings(self, parent: ttk.Frame) -> None:
        box = ttk.LabelFrame(parent, text=self.t("settings"), padding=8)
        box.pack(fill=tk.X, pady=(10, 0))
        box.columnconfigure(1, weight=1)
        lo, hi = (self.catalog.tempo_min, self.catalog.tempo_max) if self.catalog else (32, 255)

        def spin(master, var, width=5):
            return ttk.Spinbox(master, from_=lo, to=hi, textvariable=var, width=width)

        ttk.Label(box, text=self.t("tempo")).grid(row=0, column=0, sticky="w", pady=2)
        row = ttk.Frame(box)
        row.grid(row=0, column=1, sticky="w")
        ttk.Radiobutton(row, text=self.t("auto_genre"), value="auto", variable=self.tempo_mode).pack(side=tk.LEFT)
        ttk.Radiobutton(row, text=self.t("fixed"), value="fixed", variable=self.tempo_mode).pack(side=tk.LEFT,
                                                                                               padx=(12, 2))
        self.tempo_spins = [spin(row, self.tempo_fixed)]
        self.tempo_spins[-1].pack(side=tk.LEFT)
        ttk.Radiobutton(row, text=self.t("range"), value="range", variable=self.tempo_mode).pack(side=tk.LEFT,
                                                                                               padx=(12, 2))
        self.tempo_spins.append(spin(row, self.tempo_lo))
        self.tempo_spins[-1].pack(side=tk.LEFT)
        ttk.Label(row, text="–").pack(side=tk.LEFT, padx=2)
        self.tempo_spins.append(spin(row, self.tempo_hi))
        self.tempo_spins[-1].pack(side=tk.LEFT)

        ttk.Label(box, text=self.t("channels")).grid(row=1, column=0, sticky="w", pady=2)
        self.channel_row = ttk.Frame(box)
        self.channel_row.grid(row=1, column=1, sticky="w")
        self._build_channel_row()
        if not getattr(self, "_fmt_traced", False):
            self.fmt.trace_add("write", lambda *_: (self._build_channel_row(), self._update_voice_state()))
            self._fmt_traced = True

        ttk.Label(box, text=self.t("seed")).grid(row=2, column=0, sticky="w", pady=2)
        row = ttk.Frame(box)
        row.grid(row=2, column=1, sticky="w")
        ttk.Checkbutton(row, text=self.t("seed_random"), variable=self.seed_random,
                        command=self._update_seed_entry).pack(side=tk.LEFT)
        self.seed_entry = ttk.Entry(row, textvariable=self.seed, width=14)
        self.seed_entry.pack(side=tk.LEFT, padx=(12, 0))
        self._update_seed_entry()

        ttk.Label(box, text=self.t("format")).grid(row=3, column=0, sticky="w", pady=2)
        row = ttk.Frame(box)
        row.grid(row=3, column=1, sticky="w")
        for name, _ext in (self.catalog.formats if self.catalog else ()):
            ttk.Radiobutton(row, text=name.upper(), value=name, variable=self.fmt).pack(side=tk.LEFT, padx=(0, 12))
        if self.catalog and not self.catalog.mp3_available:
            ttk.Label(box, text=self.t("mp3_unavailable"), style="Warn.TLabel").grid(row=4, column=1, sticky="w")

        ttk.Label(box, text=self.t("output_dir")).grid(row=5, column=0, sticky="w", pady=(6, 2), padx=(0, 12))
        row = ttk.Frame(box)
        row.grid(row=5, column=1, sticky="ew", pady=(6, 2))
        ttk.Entry(row, textvariable=self.output_dir).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(row, text=self.t("browse"), command=self._browse_output_dir).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(row, text=self.t("open"), command=self._open_output_dir).pack(side=tk.LEFT, padx=(6, 0))

        self._build_voice_rows(box)

    # --- 歌声（--voice / --lyrics。選べるものは CLI が教えた値だけ） ---

    def _build_voice_rows(self, box: ttk.LabelFrame) -> None:
        ttk.Label(box, text=self.t("voice")).grid(row=6, column=0, sticky="nw", pady=(6, 2))
        row = ttk.Frame(box)
        row.grid(row=6, column=1, sticky="w", pady=(6, 2))
        ids = [""] + [v.id for v in self.voices]
        self._voice_ids = ids
        self.voice_combo = ttk.Combobox(row, values=[self.t("voice_none")] + ids[1:], state="readonly", width=22)
        self.voice_combo.current(ids.index(self.voice.get()) if self.voice.get() in ids else 0)
        self.voice_combo.bind("<<ComboboxSelected>>", self._on_voice_selected)
        self.voice_combo.pack(side=tk.LEFT)
        self.voice_note = ttk.Label(row, style="Muted.TLabel")
        self.voice_note.pack(side=tk.LEFT, padx=(10, 0))

        ttk.Label(box, text=self.t("lyrics")).grid(row=7, column=0, sticky="nw", pady=2)
        col = ttk.Frame(box)
        col.grid(row=7, column=1, sticky="ew", pady=2)
        self.lyrics_box = tk.Text(col, height=4, width=48, wrap="word")
        self.lyrics_box.insert("1.0", self.lyrics)
        for ev in ("<KeyRelease>", "<FocusOut>"):
            self.lyrics_box.bind(ev, lambda e: self._read_lyrics())
        self.lyrics_box.pack(fill=tk.X)
        ttk.Label(col, text=self.t("lyrics_hint"), style="Muted.TLabel", wraplength=560, justify="left").pack(anchor="w")
        self._update_voice_state()

    def _read_lyrics(self) -> str:
        box = getattr(self, "lyrics_box", None)
        if box is not None and box.winfo_exists():
            self.lyrics = box.get("1.0", "end-1c")
        return self.lyrics

    def _on_voice_selected(self, _event=None) -> None:
        self.voice.set(self._voice_ids[self.voice_combo.current()])
        self._update_voice_state()

    def _voice_available(self) -> Optional[str]:
        """歌声が使えなければ、その理由の文言キー。使えるなら None（CLI が教えた対応ジャンル・形式で決める）。"""
        if self.catalog is None or not self.catalog.voice_formats:
            return "voice_na_cli"
        if self.random_genre.get():
            return "voice_na_random"
        g = self._current_genre()
        if g is None or not g.vocal:
            return "voice_na_genre"
        if self.fmt.get() not in self.catalog.voice_formats:
            return "voice_na_format"
        return None

    def _update_voice_state(self) -> None:
        if not hasattr(self, "voice_combo") or not self.voice_combo.winfo_exists():
            return
        why = self._voice_available()
        usable = why is None and bool(self.voices)
        self.voice_combo.configure(state="readonly" if usable else tk.DISABLED)
        chosen = next((v for v in self.voices if v.id == self.voice.get()), None)
        self.lyrics_box.configure(state=tk.NORMAL if usable and chosen is not None else tk.DISABLED)
        if why is not None:
            note = self.t(why)
        elif not self.voices:
            note = self.t("voice_none_installed")
        elif chosen is not None and not chosen.terms_checked:
            note = self.t("voice_unchecked")
        elif chosen is not None and chosen.credit:
            note = chosen.credit
        else:
            note = ""
        self.voice_note.configure(text=note, style="Warn.TLabel" if (chosen and not chosen.terms_checked and usable)
                                  else "Muted.TLabel")

    def _build_channel_row(self) -> None:
        """チャンネルの入力欄を、選んでいる形式の ``--channels`` の意味（CLI が教える）で作り直す。
        ``choices``（MOD）はジャンルが選べる数のボタン、``max``（XM・S3M・IT・MP3）は上限の入力欄、``None``（MIDI）は指定不可。"""
        row = getattr(self, "channel_row", None)
        if row is None or not row.winfo_exists():
            return
        for w in row.winfo_children():
            w.destroy()
        self.channel_buttons: dict[int, ttk.Radiobutton] = {}
        self.channel_limit_entry = None
        spec = self.catalog.channel_spec(self.fmt.get()) if self.catalog else None
        if self.channels.get() != "auto" and (spec is None or ("choices" in spec) != self._channels_is_choice):
            self.channels.set("auto")
        ttk.Radiobutton(row, text=self.t("auto_genre"), value="auto", variable=self.channels).pack(side=tk.LEFT)
        if spec is None:
            self.channels.set("auto")
            ttk.Label(row, text=self.t("channels_na"), style="Muted.TLabel").pack(side=tk.LEFT, padx=(12, 0))
        elif "choices" in spec:
            for n in spec["choices"]:
                b = ttk.Radiobutton(row, text=str(n), value=str(n), variable=self.channels)
                b.pack(side=tk.LEFT, padx=(12, 0))
                self.channel_buttons[n] = b
        else:
            ttk.Radiobutton(row, text=self.t("channels_limit"), value="limit", variable=self.channels,
                            command=self._sync_channel_limit).pack(side=tk.LEFT, padx=(12, 0))
            self.channel_limit_entry = ttk.Spinbox(row, from_=1, to=spec["max"], width=4,
                                                   textvariable=self.channel_limit, command=self._sync_channel_limit)
            self.channel_limit_entry.pack(side=tk.LEFT, padx=(6, 0))
            ttk.Label(row, text=self.t("channels_max", n=spec["max"]), style="Muted.TLabel").pack(side=tk.LEFT,
                                                                                                    padx=(6, 0))
        self._channels_is_choice = spec is not None and "choices" in spec
        self._update_channel_buttons()

    _channels_is_choice = True

    def _sync_channel_limit(self) -> None:
        self.channels.set("limit")

    def _update_channel_buttons(self) -> None:
        """ジャンルが選べない MOD のチャンネル数は押せなくし、選ばれていたら「任せる」に戻す。"""
        g = self._current_genre()
        for n, b in getattr(self, "channel_buttons", {}).items():
            ok = g is None or n in g.mod_channels      # ランダムジャンルは CLI が合うジャンルから選ぶ
            b.configure(state=tk.NORMAL if ok else tk.DISABLED)
            if not ok and self.channels.get() == str(n):
                self.channels.set("auto")

    def _update_seed_entry(self) -> None:
        self.seed_entry.configure(state=tk.DISABLED if self.seed_random.get() else tk.NORMAL)

    def _browse_output_dir(self) -> None:
        d = filedialog.askdirectory(parent=self, initialdir=self.output_dir.get() or None, mustexist=False)
        if d:
            self.output_dir.set(d)

    def _open_output_dir(self) -> None:
        d = Path(self.output_dir.get() or bridge.DEFAULT_OUTPUT_DIR)
        try:
            d.mkdir(parents=True, exist_ok=True)
            bridge.reveal(d)
        except OSError as e:
            messagebox.showerror(self.t("error"), str(e), parent=self)

    # --- 生成ボタン ---

    def _build_actions(self, parent: ttk.Frame) -> None:
        row = ttk.Frame(parent)
        row.pack(fill=tk.X, pady=(10, 0))
        self.btn_generate = ttk.Button(row, text=self.t("generate"), command=self._generate)
        self.btn_generate.pack(side=tk.LEFT, ipadx=16, ipady=3)
        self.btn_cancel = ttk.Button(row, text=self.t("cancel"), command=self._cancel)
        self.btn_cancel.pack(side=tk.LEFT, padx=(8, 0))
        self.progress = ttk.Progressbar(row, mode="indeterminate", length=160)
        self.progress.pack(side=tk.LEFT, padx=(12, 0))
        ttk.Label(row, textvariable=self.status, style="Muted.TLabel").pack(side=tk.LEFT, padx=(12, 0))
        self.bind("<Control-Return>", lambda e: self._generate())
        self.bind("<F5>", lambda e: self._generate())

    def _set_running(self, running: bool) -> None:
        if not hasattr(self, "btn_generate") or not self.btn_generate.winfo_exists():
            return
        can_run = self.catalog is not None and not running
        self.btn_generate.configure(state=tk.NORMAL if can_run else tk.DISABLED)
        self.btn_cancel.configure(state=tk.NORMAL if running else tk.DISABLED)
        if running:
            self.progress.configure(mode="indeterminate")
            self.progress.start(12)
        else:
            self.progress.stop()
            self.progress.configure(mode="determinate", value=0)   # 止めた後に塊が残らないように

    def _request(self) -> Optional[Request]:
        """画面の設定を検査して ``Request`` にする。おかしければメッセージを出して None。"""
        cat = self.catalog
        assert cat is not None
        genre = None if self.random_genre.get() else self.genre_id.get()
        if genre is not None and cat.genre(genre) is None:
            return self._invalid("no_genre")
        seed = None
        if not self.seed_random.get():
            seed = bridge.parse_int(self.seed.get())
            if seed is None:
                return self._invalid("invalid_seed")
        tempo = None
        bounds = cat.tempo_bounds(cat.genre(genre) if genre is not None else None)
        if self.tempo_mode.get() == "fixed":
            tempo = bridge.parse_tempo(self.tempo_fixed.get(), self.tempo_fixed.get(), bounds)
        elif self.tempo_mode.get() == "range":
            tempo = bridge.parse_tempo(self.tempo_lo.get(), self.tempo_hi.get(), bounds)
        if self.tempo_mode.get() != "auto" and tempo is None:
            return self._invalid("invalid_tempo", lo=bounds[0], hi=bounds[1])
        channels = None
        if self.channels.get() == "limit":
            channels = bridge.parse_int(self.channel_limit.get())
            spec = cat.channel_spec(self.fmt.get())
            if channels is None or spec is None or not 1 <= channels <= spec.get("max", 0):
                return self._invalid("invalid_channels", n=(spec or {}).get("max", 0))
        elif self.channels.get() != "auto":
            channels = int(self.channels.get())
        out = self.output_dir.get().strip()
        voice = self.voice.get() or None
        if voice is not None and self._voice_available() is not None:
            voice = None                       # このジャンル・形式では使えない（画面でも無効にしてある）
        lyrics = self._read_lyrics() if voice is not None else None
        return Request(genre, seed, self.fmt.get(), tempo, channels, Path(out) if out else None, voice, lyrics)

    def _invalid(self, key: str, **kw) -> None:
        messagebox.showwarning(self.t("error"), self.t(key, **kw), parent=self)
        return None

    def _generate(self, req: Optional[Request] = None) -> None:
        if self.job is not None or self.catalog is None:
            return
        req = req or self._request()
        if req is None:
            return
        args = bridge.build_args(req, self.catalog)
        self._log(f"$ modweaver.py {' '.join(args)}")
        self.status.set(self.t("running"))
        started = time.monotonic()
        self.job = bridge.Job(args, lambda out: self._post(lambda: self._on_done(out, started))).start()
        self._set_running(True)

    def _cancel(self) -> None:
        if self.job is not None:
            self.job.cancel()

    def _on_done(self, out: Outcome, started: float) -> None:
        self.job = None
        self._set_running(False)
        if out.stderr.strip():
            self._log(out.stderr.rstrip())
        if out.cancelled:
            self.status.set(self.t("cancelled"))
            self._log("(cancelled)")
            return
        if out.error is not None:
            self.status.set(self.t("start_failed"))
            self._log(out.error)
            messagebox.showerror(self.t("error"), f"{self.t('start_failed')}\n\n{out.error}", parent=self)
            return
        self._log(f"exit {out.code}  ({time.monotonic() - started:.2f}s)")
        if not out.ok:
            self.status.set(self.t("failed", code=out.code))
            key = bridge.EXIT_KINDS.get(out.code, "exit_unexpected")
            detail = out.stderr.strip().splitlines()[-1] if out.stderr.strip() else ""
            messagebox.showerror(self.t("error"), self.t(key) + (f"\n\n{detail}" if detail else ""), parent=self)
            return
        song = SongResult.from_json(out.json())
        self.songs.insert(0, (time.strftime("%H:%M:%S"), song))
        self._log(f"-> {song.path}")
        self.status.set(self.t("done", name=song.path.name))
        self._fill_history()

    # --- 作った曲・ログ ---

    def _build_results(self, parent: ttk.Frame) -> None:
        nb = ttk.Notebook(parent)
        nb.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

        tab = ttk.Frame(nb, padding=6)
        nb.add(tab, text=self.t("tab_history"))
        cols = ("time", "genre", "seed", "bpm", "channels", "format", "file")
        widths = (70, 150, 80, 50, 40, 60, 220)
        box = ttk.Frame(tab)
        box.pack(fill=tk.BOTH, expand=True)
        self.history = ttk.Treeview(box, columns=cols, show="headings", selectmode="browse", height=6)
        for c, w in zip(cols, widths):
            self.history.heading(c, text=self.t(f"col_{c}"))
            self.history.column(c, width=w, stretch=c == "file", anchor="w")
        scroll = ttk.Scrollbar(box, command=self.history.yview)
        self.history.configure(yscrollcommand=scroll.set)
        self.history.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.history.bind("<<TreeviewSelect>>", lambda e: self._show_song())
        self.history.bind("<Double-1>", lambda e: self._play())

        row = ttk.Frame(tab)
        row.pack(fill=tk.X, pady=(6, 0))
        self.song_buttons = [
            ttk.Button(row, text=self.t("play"), command=self._play),
            ttk.Button(row, text=self.t("show_in_folder"), command=self._reveal_song),
            ttk.Button(row, text=self.t("copy_repro"), command=self._copy_repro),
            ttk.Menubutton(row, text=self.t("export_as")),
            ttk.Button(row, text=self.t("load_settings"), command=self._load_song_settings),
        ]
        export = tk.Menu(self.song_buttons[3], tearoff=0)
        for name, _ext in (self.catalog.formats if self.catalog else ()):
            export.add_command(label=name.upper(), command=lambda n=name: self._export(n))
        self.song_buttons[3]["menu"] = export
        for b in self.song_buttons:
            b.pack(side=tk.LEFT, padx=(0, 6))

        self.song_text = tk.Text(tab, height=6, wrap="word", font="TkFixedFont", relief="flat",
                                 background=self.cget("background"))
        self.song_text.pack(fill=tk.X, pady=(6, 0))
        self.song_text.configure(state=tk.DISABLED)

        tab = ttk.Frame(nb, padding=6)
        nb.add(tab, text=self.t("tab_log"))
        self.log_text = tk.Text(tab, wrap="none", font="TkFixedFont", height=8)
        scroll = ttk.Scrollbar(tab, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scroll.set)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.insert(tk.END, getattr(self, "_log_buffer", ""))
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def _log(self, text: str) -> None:
        self._log_buffer = getattr(self, "_log_buffer", "") + text + "\n"
        if hasattr(self, "log_text") and self.log_text.winfo_exists():
            self.log_text.configure(state=tk.NORMAL)
            self.log_text.insert(tk.END, text + "\n")
            self.log_text.see(tk.END)
            self.log_text.configure(state=tk.DISABLED)

    def _fill_history(self) -> None:
        self.history.delete(*self.history.get_children())
        for i, (when, s) in enumerate(self.songs):
            genre = s.genre + (" *" if s.random_genre else "")
            self.history.insert("", tk.END, iid=str(i),
                                values=(when, genre, s.seed, s.bpm, s.channels, s.format, s.path.name))
        if self.songs:
            self.history.selection_set("0")
        self._show_song()

    def _selected_song(self) -> Optional[SongResult]:
        sel = self.history.selection() if hasattr(self, "history") else ()
        return self.songs[int(sel[0])][1] if sel else None

    def _show_song(self) -> None:
        s = self._selected_song()
        for b in self.song_buttons:
            b.configure(state=tk.NORMAL if s else tk.DISABLED)
        self.song_text.configure(state=tk.NORMAL)
        self.song_text.delete("1.0", tk.END)
        if s:
            lines = [f"{s.display_name}   ({s.genre}, BPM {s.bpm}, {s.channels}ch, {s.format})", *s.summary,
                     str(s.path), s.repro]
            self.song_text.insert(tk.END, "\n".join(lines))
        self.song_text.configure(state=tk.DISABLED)

    def _play(self) -> None:
        s = self._selected_song()
        if s is None:
            return
        if not s.path.exists():
            messagebox.showerror(self.t("error"), self.t("file_missing", path=s.path), parent=self)
            return
        try:
            bridge.open_file(s.path)
        except OSError as e:
            messagebox.showinfo(self.t("play"), f"{self.t('play_failed')}\n\n{e}", parent=self)

    def _reveal_song(self) -> None:
        s = self._selected_song()
        if s is not None:
            bridge.reveal(s.path if s.path.exists() else s.path.parent)

    def _copy_repro(self) -> None:
        s = self._selected_song()
        if s is not None:
            self.clipboard_clear()
            self.clipboard_append(s.repro)
            self.status.set(self.t("copied"))

    def _export(self, fmt: str) -> None:
        s = self._selected_song()
        if s is not None:
            out = self.output_dir.get().strip()
            self._generate(bridge.replay_request(s, fmt, Path(out) if out else None, self.catalog))

    def _load_song_settings(self) -> None:
        """選んだ曲の指定を設定に戻す（シードを固定してテンポや形式だけ変える、などのため）。"""
        s = self._selected_song()
        if s is None:
            return
        self.random_genre.set(False)
        self.genre_id.set(s.genre)
        self.seed_random.set(False)
        self.seed.set(str(s.seed))
        self._update_seed_entry()
        if s.tempo_request is None:
            self.tempo_mode.set("auto")
        else:
            self.tempo_mode.set("fixed")
            self.tempo_fixed.set(str(s.bpm))
        self.voice.set(s.voice or "")
        self.lyrics = s.lyrics or ""
        self.fmt.set(s.format)           # 形式を先に（チャンネルの入力欄が形式で作り直されるため）
        spec = self.catalog.channel_spec(s.format) if self.catalog else None
        if s.channels_request is None:
            self.channels.set("auto")
        elif spec is not None and "max" in spec:
            self.channel_limit.set(str(s.channels_request))
            self.channels.set("limit")
        else:
            self.channels.set(str(s.channels_request))
        self.search.set("")                   # 一覧を作り直して選び直す
        self.category.set("")
        self._build()

    # ------------------------------------------------------------------
    # ヘルプ
    # ------------------------------------------------------------------

    def _show_cli_help(self) -> None:
        out = bridge.run(["--help"] + (["--english"] if self.lang.get() == "en" else []), timeout=60)
        text = out.stdout if out.ok else (out.error or out.stderr)
        win = tk.Toplevel(self)
        win.title(self.t("cli_help_title"))
        win.geometry("760x560")
        txt = tk.Text(win, wrap="none", font="TkFixedFont", padx=8, pady=8)
        scroll = ttk.Scrollbar(win, command=txt.yview)
        txt.configure(yscrollcommand=scroll.set)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        txt.pack(fill=tk.BOTH, expand=True)
        txt.insert(tk.END, text)
        txt.configure(state=tk.DISABLED)

    def _show_about(self) -> None:
        if self.catalog is None:
            return
        messagebox.showinfo(self.t("menu_about"),
                            self.t("about", version=self.catalog.version, url=self.catalog.url), parent=self)


def main(argv: Optional[list[str]] = None) -> int:
    if sys.platform == "win32":
        try:                                   # 高 DPI で文字がぼやけないように
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (AttributeError, OSError):
            pass
    argv = sys.argv[1:] if argv is None else argv
    lang = next((a.split("=", 1)[1] for a in argv if a.startswith("--lang=")), None)
    App(lang if lang in TEXTS else None).mainloop()
    return 0
