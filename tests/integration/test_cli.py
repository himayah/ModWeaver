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
    assert cli.default_output_path("nostalgic", 1) == Path("nostalgic/nostalgic_1.mod")
    assert cli.default_output_path("nostalgic", 1, "mod") == Path("nostalgic/nostalgic_1.mod")
    assert cli.default_output_path("orchestral", 5, "xm") == Path("orchestral/orchestral_5.xm")


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


def test_default_output_path_is_genre_subdir(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    code, *_ = run_cli(["-s", "1"], capsys)
    assert code == 0 and (tmp_path / "nostalgic" / "nostalgic_1.mod").exists()


def test_default_output_path_creates_missing_genre_dir(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    code, *_ = run_cli(["-g", "suspense-chase", "-s", "5"], capsys)
    assert code == 0 and (tmp_path / "suspense-chase" / "suspense-chase_5.mod").exists()


def test_default_format_is_mod_even_for_8ch_genre(tmp_path, capsys, monkeypatch):
    """--format 省略時は全ジャンル mod（8ch の orchestral は FastTracker 系 8CHN）。"""
    monkeypatch.chdir(tmp_path)
    code, stdout, _ = run_cli(["-g", "orchestral", "-s", "5"], capsys)
    out = tmp_path / "orchestral" / "orchestral_5.mod"
    assert code == 0 and out.exists() and out.read_bytes()[1080:1084] == b"8CHN"
    assert "Format      : mod" in stdout and "--format" not in stdout


def test_format_option_sets_extension_and_repro(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    code, stdout, _ = run_cli(["-g", "orchestral", "-s", "5", "-f", "xm"], capsys)
    out = tmp_path / "orchestral" / "orchestral_5.xm"
    assert code == 0 and out.read_bytes()[:17] == b"Extended Module: "
    assert "--genre orchestral --format xm --seed 5" in stdout


def test_unknown_format_exit_2(tmp_path, capsys):
    code, _, err = run_cli(["-f", "wav", "-o", str(tmp_path / "x")], capsys)
    assert code == 2 and "format" in err


def test_list_genres_prints_all_ids_and_exits_0(tmp_path, capsys):
    code, stdout, err = run_cli(["--list-genres"], capsys)
    assert code == 0 and err == ""
    for p in cli.profiles.list_profiles():
        assert p.id in stdout and p.description in stdout
    assert "suspense-slow" in stdout and "suspense" in stdout  # alias も表示される
    assert not (tmp_path / "nostalgic").exists()  # 生成は行われない


def test_genre_listing_appears_in_help(capsys):
    code, stdout, _ = run_cli(["--help"], capsys)
    assert code == 0
    for p in cli.profiles.list_profiles():
        assert p.id in stdout and p.description in stdout


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
