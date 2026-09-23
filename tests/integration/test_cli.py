from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from mod_weaver import cli
from mod_weaver.core.verify import has_errors, verify

ROOT = Path(__file__).resolve().parents[2]


def run_cli(args, capsys):
    code = cli.main(args)
    cap = capsys.readouterr()
    return code, cap.out, cap.err


def test_default_output_path_extension_follows_format():
    assert cli.default_output_path("nostalgic", 1) == Path("output/nostalgic_1.mod")
    assert cli.default_output_path("nostalgic", 1, "mod") == Path("output/nostalgic_1.mod")
    assert cli.default_output_path("orchestral", 5, "xm") == Path("output/orchestral_5.xm")


def test_default_genre_generates_file(tmp_path, capsys):
    out = tmp_path / "a.mod"
    code, stdout, err = run_cli(["--seed", "732501", "-o", str(out)], capsys)
    assert code == 0 and err == ""
    assert out.exists() and out.stat().st_size > 0
    assert "Seed        : 732501" in stdout and "Tempo       : BPM 90" in stdout
    assert "Theme A" in stdout and "Theme B" in stdout
    assert "python -m mod_weaver.cli --genre nostalgic --seed 732501" in stdout
    assert not has_errors(verify(out.read_bytes()))


def test_short_options_and_negative_seed(tmp_path, capsys):
    out = tmp_path / "n.mod"
    code, *_ = run_cli(["-g", "nostalgic", "-s", "-7", "-o", str(out)], capsys)
    assert code == 0 and out.exists() and out.stat().st_size > 0
    assert not has_errors(verify(out.read_bytes()))


def test_seed_omitted_uses_random_in_range(tmp_path, capsys):
    code, stdout, _ = run_cli(["-o", str(tmp_path / "r.mod")], capsys)
    assert code == 0
    seed = int(next(l for l in stdout.splitlines() if l.startswith("Seed")).split(":")[1])
    assert 100000 <= seed <= 999999


def test_default_output_path_is_output_dir(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    code, *_ = run_cli(["-s", "1"], capsys)
    assert code == 0 and (tmp_path / "output" / "nostalgic_1.mod").exists()


def test_default_output_path_creates_missing_output_dir(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    code, *_ = run_cli(["-g", "suspense-chase", "-s", "5"], capsys)
    assert code == 0 and (tmp_path / "output" / "suspense-chase_5.mod").exists()


def test_default_format_is_mod_even_for_8ch_genre(tmp_path, capsys, monkeypatch):
    """--format 省略時は全ジャンル mod（8ch の orchestral は FastTracker 系 8CHN）。"""
    monkeypatch.chdir(tmp_path)
    code, stdout, _ = run_cli(["-g", "orchestral", "-s", "5"], capsys)
    out = tmp_path / "output" / "orchestral_5.mod"
    assert code == 0 and out.exists() and out.read_bytes()[1080:1084] == b"8CHN"
    assert "Format      : mod" in stdout and "--format" not in stdout


def test_format_option_sets_extension_and_repro(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    code, stdout, _ = run_cli(["-g", "orchestral", "-s", "5", "-f", "xm"], capsys)
    out = tmp_path / "output" / "orchestral_5.xm"
    assert code == 0 and out.read_bytes()[:17] == b"Extended Module: "
    assert "--genre orchestral --format xm --seed 5" in stdout


def test_unknown_format_exit_2(tmp_path, capsys):
    code, _, err = run_cli(["-f", "wav", "-o", str(tmp_path / "x")], capsys)
    assert code == 2 and "format" in err


def test_list_genres_prints_all_ids_and_exits_0(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    code, stdout, err = run_cli(["--list-genres"], capsys)
    assert code == 0 and err == ""
    for p in cli.profiles.list_profiles():
        assert p.id in stdout and p.description in stdout
    assert "suspense-slow" in stdout and "suspense" in stdout  # alias も表示される
    assert not (tmp_path / "output").exists()  # 生成は行われない


def test_genre_listing_appears_in_help(capsys):
    code, stdout, _ = run_cli(["--help"], capsys)
    assert code == 0
    for p in cli.profiles.list_profiles():
        assert p.id in stdout and p.description in stdout


def test_no_arguments_prints_help_and_exits_0(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _, help_out, _ = run_cli(["--help"], capsys)
    code, stdout, err = run_cli([], capsys)
    assert code == 0 and err == "" and stdout == help_out and stdout.startswith("usage:")
    assert list(tmp_path.iterdir()) == []             # 生成は行われない


def test_no_arguments_via_script_prints_usage(tmp_path):
    r = subprocess.run([sys.executable, str(ROOT / "modweaver.py")], capture_output=True, text=True, cwd=tmp_path)
    assert r.returncode == 0 and r.stdout.startswith("usage: modweaver.py") and r.stderr == ""
    assert list(tmp_path.iterdir()) == []


def test_any_argument_still_generates_default_genre(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    code, stdout, _ = run_cli(["-s", "3"], capsys)
    assert code == 0 and "Genre       : nostalgic" in stdout and (tmp_path / "output" / "nostalgic_3.mod").exists()


@pytest.mark.parametrize("name", ["random", "r"])
def test_random_genre_generates_registered_genre(tmp_path, capsys, monkeypatch, name):
    monkeypatch.chdir(tmp_path)
    code, stdout, _ = run_cli(["-g", name, "-s", "11"], capsys)   # stderr は選ばれたジャンル次第で検査 WARNING が出うる
    assert code == 0
    genre_line = next(l for l in stdout.splitlines() if l.startswith("Genre"))
    gid = genre_line.split(":")[1].split()[0]
    assert genre_line.endswith(" (random)") and gid in [p.id for p in cli.profiles.list_profiles()]
    assert f"--genre {gid} --seed 11" in stdout                          # 再現コマンドは決まったジャンル
    assert (tmp_path / "output" / f"{gid}_11.mod").exists()


def test_random_genre_picks_among_canonical_ids(tmp_path, capsys, monkeypatch):
    seen = []
    monkeypatch.setattr(cli.random, "choice", lambda c: seen.append(list(c)) or "trap")
    code, stdout, _ = run_cli(["-g", "r", "-s", "1", "-o", str(tmp_path / "x.mod")], capsys)
    assert code == 0 and "Genre       : trap (random)" in stdout
    assert seen == [[p.id for p in cli.profiles.list_profiles()]]       # 別名（suspense）は含まない


def test_random_genre_with_tempo_excludes_genres_that_cannot_play_it(tmp_path, capsys, monkeypatch):
    seen = []
    monkeypatch.setattr(cli.random, "choice", lambda c: seen.append(list(c)) or c[0])
    code, stdout, err = run_cli(["-g", "random", "-t", "200", "-s", "1", "-o", str(tmp_path / "x.mod")], capsys)
    assert code == 0 and "Tempo       : BPM 200" in stdout and err == ""
    ids = [p.id for p in cli.profiles.list_profiles()]
    assert "free-jazz" in ids and seen == [[i for i in ids if i != "free-jazz"]]   # free-jazz は 44-163


def test_random_genre_with_unsupported_tempo_exit_2(tmp_path, capsys, monkeypatch):
    fj = cli.profiles.get_profile("free-jazz").__class__
    monkeypatch.setattr(cli.profiles, "list_profiles", lambda: [fj])
    code, out, err = run_cli(["-g", "r", "-t", "200", "-o", str(tmp_path / "x.mod")], capsys)
    assert code == 2 and "no genre supports tempo 200" in err and out == ""
    assert not (tmp_path / "x.mod").exists()


def test_random_names_match_registry_reserved_names():
    from mod_weaver.profiles import registry
    assert set(cli.RANDOM_GENRE) == registry.RESERVED_NAMES


@pytest.mark.parametrize("flag", ["--version", "-v"])
def test_version_prints_version_and_url(capsys, flag):
    import mod_weaver
    code, stdout, err = run_cli([flag], capsys)
    assert code == 0 and err == ""
    assert stdout == f"ModWeaver {mod_weaver.__version__}\nhttps://github.com/himayah/ModWeaver\n"


def test_version_wins_over_other_arguments(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    code, stdout, _ = run_cli(["-g", "nostalgic", "-s", "1", "-v"], capsys)
    assert code == 0 and stdout.startswith("ModWeaver ") and list(tmp_path.iterdir()) == []


def test_unknown_genre_exit_2(tmp_path, capsys):
    code, out, err = run_cli(["--genre", "bogus", "-o", str(tmp_path / "x.mod")], capsys)
    assert code == 2 and "unknown genre" in err and "nostalgic" in err and out == ""
    assert not (tmp_path / "x.mod").exists()


def test_argparse_error_exit_2(capsys):
    code, _, err = run_cli(["--seed", "abc"], capsys)
    assert code == 2 and "invalid int value" in err
    assert cli.main(["--help"]) == 0


def test_output_error_exit_4(tmp_path, capsys):
    code, _, err = run_cli(["-s", "1", "-o", str(tmp_path / "no" / "dir" / "x.mod")], capsys)
    assert code == 4 and "cannot write" in err


def test_generation_error_exit_3(monkeypatch, tmp_path, capsys):
    from mod_weaver.errors import PlanError

    def boom(*a, **k):
        raise PlanError("bad plan")

    monkeypatch.setattr(cli, "generate", boom)
    code, _, err = run_cli(["-o", str(tmp_path / "x.mod")], capsys)
    assert code == 3 and "bad plan" in err


def test_unexpected_exception_exit_1(monkeypatch, tmp_path, capsys):
    def boom(*a, **k):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(cli, "generate", boom)
    code, _, err = run_cli(["-o", str(tmp_path / "x.mod")], capsys)
    assert code == 1 and "Traceback" in err and "kaboom" in err


def test_custom_invocation_used_in_repro_line(tmp_path, capsys):
    code, stdout, _ = run_cli(["-s", "1", "-o", str(tmp_path / "x.mod")], capsys)  # baseline (default invocation)
    assert code == 0 and "python -m mod_weaver.cli --genre nostalgic --seed 1" in stdout
    code = cli.main(["-s", "1", "-o", str(tmp_path / "y.mod")], prog="modweaver.py", invocation="python modweaver.py")
    assert code == 0 and "python modweaver.py --genre nostalgic --seed 1" in capsys.readouterr().out


def test_python_dash_m_forms_produce_identical_output(tmp_path):
    a, b = tmp_path / "a.mod", tmp_path / "b.mod"
    for mod, out in (("mod_weaver", a), ("mod_weaver.cli", b)):
        r = subprocess.run([sys.executable, "-m", mod, "--seed", "42", "-o", str(out)],
                           capture_output=True, text=True, cwd=ROOT)
        assert r.returncode == 0, r.stderr
    assert a.read_bytes() == b.read_bytes()             # 両起動形式は互いに同一（旧実装とのバイト一致は求めない）
    assert not has_errors(verify(a.read_bytes()))


def test_exit_code_of_module_invocation_for_unknown_genre(tmp_path):
    r = subprocess.run([sys.executable, "-m", "mod_weaver", "-g", "zzz"], capture_output=True, text=True, cwd=ROOT)
    assert r.returncode == 2


# ---------------- --tempo（FORMAT_TEMPO_DESIGN §3） ----------------

def test_tempo_single_value(tmp_path, capsys):
    out = tmp_path / "t.mod"
    code, stdout, err = run_cli(["-s", "1", "-t", "123", "-o", str(out)], capsys)
    assert code == 0 and err == ""
    assert "Tempo       : BPM 123\n" in stdout
    assert "--genre nostalgic --tempo 123 --seed 1" in stdout


def test_tempo_range_picks_within_and_repro_uses_resolved_value(tmp_path, capsys):
    code, stdout, _ = run_cli(["-s", "5", "--tempo", "80-100", "-o", str(tmp_path / "r.mod")], capsys)
    assert code == 0
    line = next(l for l in stdout.splitlines() if l.startswith("Tempo"))
    bpm = int(line.split("BPM")[1].split()[0])
    assert 80 <= bpm <= 100 and "(requested 80-100)" in line
    assert f"--tempo {bpm} --seed 5" in stdout


def test_tempo_omitted_keeps_repro_unchanged(tmp_path, capsys):
    _, stdout, _ = run_cli(["-s", "5", "-o", str(tmp_path / "r.mod")], capsys)
    assert "--tempo" not in stdout


@pytest.mark.parametrize("bad", ["fast", "100-80", "20", "300", "80-"])
def test_tempo_invalid_syntax_exit_2(tmp_path, capsys, bad):
    code, _, err = run_cli(["-t", bad, "-o", str(tmp_path / "x.mod")], capsys)
    assert code == 2 and "tempo" in err


def test_tempo_outside_genre_range_exit_2(tmp_path, capsys):
    code, _, err = run_cli(["-g", "free-jazz", "-t", "250", "-o", str(tmp_path / "x.mod")], capsys)
    assert code == 2 and "free-jazz" in err and not (tmp_path / "x.mod").exists()


# ---------------- --format（FORMAT_TEMPO_DESIGN §2・§5） ----------------

@pytest.mark.parametrize("fmt, magic", [
    ("mod", lambda b: b[1080:1084] == b"M.K."), ("xm", lambda b: b[:17] == b"Extended Module: "),
    ("s3m", lambda b: b[44:48] == b"SCRM"), ("it", lambda b: b[:4] == b"IMPM"), ("midi", lambda b: b[:4] == b"MThd"),
])
def test_each_tracker_and_midi_format(tmp_path, capsys, monkeypatch, fmt, magic):
    monkeypatch.chdir(tmp_path)
    code, stdout, err = run_cli(["-g", "nostalgic", "-s", "3", "-f", fmt], capsys)
    ext = {"midi": ".mid"}.get(fmt, f".{fmt}")
    out = tmp_path / "output" / f"nostalgic_3{ext}"
    assert code == 0 and err == "" and magic(out.read_bytes())
    assert f"Format      : {fmt}" in stdout


def test_mp3_without_ffmpeg_exits_5(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("MODWEAVER_FFMPEG", str(tmp_path / "no-such-ffmpeg"))
    code, _, err = run_cli(["-f", "mp3", "-s", "1", "-o", str(tmp_path / "x.mp3")], capsys)
    assert code == 5 and "ffmpeg" in err and not (tmp_path / "x.mp3").exists()


def test_mp3_with_ffmpeg_lacking_libopenmpt_exits_5(tmp_path, capsys, monkeypatch):
    fake = tmp_path / "ffmpeg"
    fake.write_text("#!/bin/sh\necho ' D  mp3  MP3'\n")
    fake.chmod(0o755)
    monkeypatch.setenv("MODWEAVER_FFMPEG", str(fake))
    code, _, err = run_cli(["-f", "mp3", "-s", "1", "-o", str(tmp_path / "x.mp3")], capsys)
    assert code == 5 and "libopenmpt" in err and "libmp3lame" in err
