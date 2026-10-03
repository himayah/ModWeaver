"""生成エンジン（engine.py。FRAMEWORK_REDESIGN.md §3.1）の検査: build・generate・検査器との接続・エラー。"""
from __future__ import annotations

import logging

import pytest

from mod_weaver import engine
from mod_weaver.core import native
from mod_weaver.core.verify import Issue
from mod_weaver.errors import ChannelCountError, OutputError, PlanError, ProfileNotFoundError, VerificationError
from tests.helpers import make_genre

FORMATS_NO_MP3 = ("mod", "xm", "s3m", "it", "midi")


@pytest.mark.parametrize("fmt", FORMATS_NO_MP3)
def test_build_is_deterministic_and_clean_in_every_format(fmt):
    g = make_genre()
    a, b = engine.build(g, 5, fmt), engine.build(g, 5, fmt)
    assert a.data == b.data and a.plan.bpm == 100 and a.seed == 5 and a.fmt == fmt
    assert not [i for i in engine.verify_data(a) if i.level == "ERROR"]


def test_build_reports_channels_and_sample_bits():
    g = make_genre()
    mod = engine.build(g, 1, "mod")
    assert (mod.channels, mod.target.budget, mod.sample_bits) == (4, 4, 8)
    it = engine.build(g, 1, "it")
    assert it.sample_bits == 16 and it.channels <= it.target.budget == 64
    s3m = engine.build(g, 1, "s3m")
    assert s3m.sample_bits == 8 and s3m.target.budget == 16
    midi = engine.build(g, 1, "midi")
    assert midi.sample_bits is None and midi.channels == 1 and midi.target.budget == 16


def test_channels_request_is_validated_per_format():
    g = make_genre()
    assert engine.build(g, 1, "mod", channels=4).channels == 4
    with pytest.raises(ChannelCountError):
        engine.build(g, 1, "mod", channels=6)                 # MOD はジャンルが宣言した数だけ
    with pytest.raises(ChannelCountError):
        engine.build(g, 1, "midi", channels=4)                # MIDI は指定不可
    with pytest.raises(ChannelCountError):
        engine.build(g, 1, "s3m", channels=17)                # 形式の上限を超える
    assert engine.build(g, 1, "s3m", channels=2).target.budget == 2


def test_supports_channels_filters_by_format_and_ladder():
    orch = engine.get_genre("orchestral")
    assert engine.supports_channels(orch, "mod", 8, 1) and not engine.supports_channels(orch, "mod", 4, 1)
    assert engine.supports_channels(orch, "it", 16, 1) and not engine.supports_channels(orch, "it", 6, 1)
    assert not engine.supports_channels(orch, "midi", 4, 1)


def test_unknown_genre_lists_choices_and_unknown_format_is_rejected(tmp_path):
    with pytest.raises(ProfileNotFoundError, match="choices"):
        engine.get_genre("nope")
    with pytest.raises(PlanError, match="unknown format"):
        engine.build(make_genre(), 1, "wav")


# ---------------- generate ----------------

def test_generate_writes_file_and_returns_result(tmp_path):
    out = tmp_path / "d.mod"
    res = engine.generate(make_genre(), 5, out)
    assert out.exists() and res.path == out and res.seed == 5 and res.plan.bpm == 100
    assert (res.channels, res.channel_budget, res.sample_bits, res.fmt) == (4, 4, 8, "mod")
    assert not [i for i in res.issues if i.level == "ERROR"]


def test_generate_seed_none_uses_default_range(tmp_path):
    res = engine.generate(make_genre(), None, tmp_path / "d.mod")
    assert 100000 <= res.seed <= 999999


def _fail_verify(monkeypatch, level="ERROR", code="V99"):
    monkeypatch.setattr(native, "verify", lambda fmt, data: [Issue(level, code, "boom")])


def test_generate_verification_error_writes_nothing(tmp_path, monkeypatch):
    _fail_verify(monkeypatch)
    out = tmp_path / "bad.mod"
    with pytest.raises(VerificationError) as ei:
        engine.generate(make_genre(), 1, out)
    assert any(i.code == "V99" for i in ei.value.issues)
    assert not out.exists() and list(tmp_path.iterdir()) == []


def test_generate_skip_verify(tmp_path, monkeypatch):
    _fail_verify(monkeypatch)
    res = engine.generate(make_genre(), 1, tmp_path / "x.mod", verify=False)
    assert res.issues == [] and res.path.exists()


def test_generate_logs_warnings(tmp_path, caplog, monkeypatch):
    # cli.main が propagate=False にするため、他テストの実行順に依存しないよう戻す
    monkeypatch.setattr(logging.getLogger("mod_weaver"), "propagate", True)
    _fail_verify(monkeypatch, "WARN", "V15")
    with caplog.at_level(logging.WARNING, logger="mod_weaver"):
        res = engine.generate(make_genre(), 1, tmp_path / "x.mod")
    assert any(i.code == "V15" for i in res.issues)
    assert any("V15" in r.message for r in caplog.records)


def test_generate_output_error(tmp_path):
    with pytest.raises(OutputError):
        engine.generate(make_genre(), 1, tmp_path / "nodir" / "x.mod")


def test_verification_error_message_summarises():
    e = VerificationError([Issue("ERROR", f"V0{i}", "m") for i in range(1, 8)])
    assert "V01" in str(e) and "+2 more" in str(e)


def test_every_registered_genre_builds_with_the_default_seed_and_format():
    for g in engine.list_genres():
        built = engine.build(g, 7)
        assert built.plan.bpm in g.tempo_choices and built.channels in g.mod_channels
