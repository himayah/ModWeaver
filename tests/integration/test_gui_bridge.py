"""GUI の橋渡し（mod_weaver/gui/bridge.py。DESIGN.md §12.2）。CLI は本物を子プロセスで動かす。"""
from __future__ import annotations

import subprocess
import sys
import threading
from pathlib import Path

import pytest

from mod_weaver import cli
from mod_weaver.gui import bridge
from mod_weaver.gui.bridge import Catalog, Request, SongResult


@pytest.fixture(scope="module")
def catalog() -> Catalog:
    return Catalog.from_json(cli.catalog())


def test_bridge_does_not_import_tkinter_or_the_engine():
    code = ("import sys, mod_weaver.gui.bridge; "
            "bad = [m for m in ('tkinter', 'mod_weaver.cli', 'mod_weaver.engine') if m in sys.modules]; "
            "sys.exit(1 if bad else 0)")
    assert subprocess.run([sys.executable, "-c", code], cwd=bridge.ROOT).returncode == 0


def test_load_catalog_matches_the_cli(catalog):
    loaded = bridge.load_catalog()
    assert loaded == catalog
    assert [g.id for g in loaded.genres] == [g["id"] for g in cli.catalog()["genres"]]
    assert loaded.random_genre == "random" and loaded.default_genre == cli.DEFAULT_GENRE
    assert loaded.extension("midi") == ".mid"
    calm = loaded.genre("calm")
    assert calm.channel_choices == (4,) and loaded.category_label("mood", "en") == "Mood"
    assert loaded.is_full_tempo_range(calm)
    assert calm.tempo_choices == (68, 70, 72, 74, 76, 78)
    assert calm.usual_tempo == (68, 78) and calm.typical_tempo == 72     # 候補の中央（偶数個なら下側）
    racing = loaded.genre("racing-breaks")
    assert racing.typical_tempo in racing.tempo_choices


@pytest.mark.parametrize("req, expected", [
    (Request("calm"), ["--genre", "calm", "--json"]),
    (Request(None), ["--genre", "random", "--json"]),
    (Request("pop", seed=-3, fmt="mod"), ["--genre", "pop", "--seed", "-3", "--json"]),     # 既定の形式は省く
    (Request("pop", fmt="xm", tempo=(120, 120), channels=6, output_dir=Path("d")),
     ["--genre", "pop", "--format", "xm", "--tempo", "120", "--channels", "6", "--output-dir", "d", "--json"]),
    (Request("pop", tempo=(80, 100)), ["--genre", "pop", "--tempo", "80-100", "--json"]),
])
def test_build_args(catalog, req, expected):
    assert bridge.build_args(req, catalog) == expected


def test_parse_tempo_and_int(catalog):
    full = catalog.tempo_bounds(None)
    assert full == (32, 255)
    assert bridge.parse_tempo("80", "100", full) == (80, 100)
    assert bridge.parse_tempo(" 120 ", "120", full) == (120, 120)
    for lo, hi in [("100", "80"), ("31", "80"), ("80", "256"), ("", "80"), ("8x", "90")]:
        assert bridge.parse_tempo(lo, hi, full) is None
    free = catalog.tempo_bounds(catalog.genre("free-jazz"))   # ジャンルが受け付ける範囲で検査する
    assert free == (44, 163) and bridge.parse_tempo("40", "90", free) is None
    assert bridge.parse_int("-7") == -7 and bridge.parse_int("") is None and bridge.parse_int("1.5") is None


def _song(**kw) -> SongResult:
    base = dict(genre="pop", display_name="Pop", random_genre=True, format="mod", seed=5, bpm=111,
                tempo_request=None, channels=6, channels_request=None, summary=(), path=Path("x.mod"),
                repro="python modweaver.py --genre pop --seed 5")
    base.update(kw)
    return SongResult(**base)


def test_replay_request_passes_only_what_was_requested():
    # 指定しなかったテンポ・チャンネル数は seed で同じになるので渡さない（再現コマンドと同じ）
    assert bridge.replay_request(_song(), "it", None) == Request("pop", 5, "it", None, None, None)
    req = bridge.replay_request(_song(tempo_request="80-120", channels_request=6), "xm", Path("o"))
    assert req == Request("pop", 5, "xm", (111, 111), 6, Path("o"))


def _run_job(args) -> bridge.Outcome:
    done = threading.Event()
    box = []
    bridge.Job(args, lambda out: (box.append(out), done.set())).start()
    assert done.wait(120)
    return box[0]


def test_job_generates_and_result_parses(tmp_path, catalog):
    out = _run_job(bridge.build_args(Request("pop", 5, "xm", (100, 120), 6, tmp_path), catalog))
    assert out.ok, out.stderr
    song = SongResult.from_json(out.json())
    assert song.path == (tmp_path / "pop_5.xm").resolve() and song.path.exists()
    assert (song.genre, song.seed, song.format, song.channels) == ("pop", 5, "xm", 6)
    assert 100 <= song.bpm <= 120 and song.repro.startswith("python modweaver.py --genre pop")

    # 別の形式で書き出しても同じ曲（テンポ・編成・和声の要約が同じ）
    again = _run_job(bridge.build_args(bridge.replay_request(song, "it", tmp_path), catalog))
    other = SongResult.from_json(again.json())
    assert (other.bpm, other.channels, other.summary) == (song.bpm, song.channels, song.summary)
    assert other.path.suffix == ".it"


def test_job_reports_cli_errors_with_exit_code(tmp_path, catalog):
    out = _run_job(bridge.build_args(Request("calm", channels=8, output_dir=tmp_path), catalog))
    assert out.code == 2 and not out.ok and "cannot use 8 channels" in out.stderr
    assert bridge.EXIT_KINDS[out.code] == "exit_args"


def test_job_cancelled_before_start_does_not_run(tmp_path, catalog):
    box = []
    job = bridge.Job(bridge.build_args(Request("pop", output_dir=tmp_path), catalog), box.append)
    job.cancel()
    job._run()
    assert box[0].cancelled and box[0].code is None and not list(tmp_path.iterdir())


def test_subprocess_uses_utf8_and_hides_console(monkeypatch):
    kw = bridge.popen_kwargs()
    assert kw["env"]["PYTHONUTF8"] == "1" and kw["encoding"] == "utf-8" and kw["cwd"] == str(bridge.ROOT)
    assert bridge.command(["-v"])[1:] == [str(bridge.CLI_SCRIPT), "-v"]


def test_pythonw_is_replaced_by_console_python(tmp_path, monkeypatch):
    (tmp_path / "pythonw.exe").write_text("")
    (tmp_path / "python.exe").write_text("")
    monkeypatch.setattr(sys, "executable", str(tmp_path / "pythonw.exe"))
    assert bridge.python_executable() == str(tmp_path / "python.exe")


@pytest.mark.parametrize("platform, head", [("win32", ["explorer"]), ("darwin", ["open", "-R"]),
                                            ("linux", ["xdg-open"])])
def test_reveal_command_per_platform(tmp_path, monkeypatch, platform, head):
    f = tmp_path / "a.mod"
    f.write_bytes(b"x")
    monkeypatch.setattr(sys, "platform", platform)
    cmd = bridge.reveal_command(f)
    assert cmd[:len(head)] == head
    if platform == "linux":
        assert cmd[-1] == str(tmp_path.resolve())            # xdg-open はファイルを選べないのでフォルダ
    else:
        assert str(f.resolve()) in cmd[-1]


def test_gui_texts_have_the_same_keys():
    from mod_weaver.gui.texts import TEXTS
    assert TEXTS["ja"].keys() == TEXTS["en"].keys()
    assert set(bridge.EXIT_KINDS.values()) <= TEXTS["ja"].keys()
