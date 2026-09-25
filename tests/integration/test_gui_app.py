"""GUI の画面（mod_weaver/gui/app.py。DESIGN.md §12）の通し確認。画面が出せない環境では skip。"""
from __future__ import annotations

import time

import pytest

tk = pytest.importorskip("tkinter")


@pytest.fixture
def app():
    from mod_weaver.gui.app import App
    try:
        a = App(lang="ja")
    except tk.TclError as e:                     # DISPLAY が無い等
        pytest.skip(f"no display: {e}")
    a.withdraw()
    yield a
    a.destroy()


def _pump(app, until, timeout=120.0):
    end = time.monotonic() + timeout
    while not until():
        assert time.monotonic() < end, "timed out"
        app.update()
        time.sleep(0.02)


def test_gui_loads_catalog_generates_and_exports(app, tmp_path):
    _pump(app, lambda: app.catalog is not None or app.load_error is not None)
    assert app.load_error is None
    assert len(app.genre_tree.get_children()) == len(app.catalog.categories)   # 区分ごとの見出し
    assert sum(len(app.genre_tree.get_children(c)) for c in app.genre_tree.get_children()) == \
        len(app.catalog.genres)

    app.search.set("jazz")                       # 検索で絞り込める
    shown = [i for c in app.genre_tree.get_children() for i in app.genre_tree.get_children(c)]
    assert 0 < len(shown) < len(app.catalog.genres)
    assert all(app._matches(app.catalog.genre(i), ["jazz"]) for i in shown)
    app.search.set("")

    app.genre_id.set("pop")
    app.channels.set("6")
    app.output_dir.set(str(tmp_path))
    app.fmt.set("xm")
    app._build()
    app._generate()
    _pump(app, lambda: app.job is None and app.songs)
    song = app.songs[0][1]
    assert song.genre == "pop" and song.channels == 6 and song.path.exists()

    app._export("it")
    _pump(app, lambda: app.job is None and len(app.songs) == 2)
    assert app.songs[0][1].path.suffix == ".it" and app.songs[0][1].seed == song.seed

    # ジャンルが選べないチャンネル数は「任せる」に戻る
    app.genre_id.set("calm")
    app._on_genre_changed()
    assert app.channels.get() == "auto" and str(app.channel_buttons[8].cget("state")) == "disabled"

    # 言語を切り替えても設定と作った曲は残る
    app.lang.set("en")
    assert app.btn_generate.cget("text") == "Generate" and len(app.history.get_children()) == 2
    assert app.genre_id.get() == "calm"


def test_gui_rejects_bad_seed_and_tempo(app, monkeypatch):
    _pump(app, lambda: app.catalog is not None)
    shown = []
    monkeypatch.setattr("tkinter.messagebox.showwarning", lambda title, msg, **kw: shown.append(msg))
    app.seed_random.set(False)
    app.seed.set("abc")
    assert app._request() is None
    app.seed.set("12")
    app.tempo_mode.set("range")
    app.tempo_lo.set("150")
    app.tempo_hi.set("100")
    assert app._request() is None
    app.tempo_hi.set("160")
    req = app._request()
    assert req.seed == 12 and req.tempo == (150, 160) and len(shown) == 2
