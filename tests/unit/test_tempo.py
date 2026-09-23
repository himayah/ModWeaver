"""--tempo（FORMAT_TEMPO_DESIGN §3）のテスト。"""
from __future__ import annotations

import dataclasses
import logging

import pytest

from mod_weaver import profiles
from mod_weaver.core import writer
from mod_weaver.engine import TempoRequest, compose_song, resolve_tempo, validate_profile
from mod_weaver.errors import PlanError, TempoRangeError


@pytest.mark.parametrize("text, expected", [("120", (120, 120)), ("80-100", (80, 100)), (" 32-255 ", (32, 255))])
def test_parse_valid(text, expected):
    r = TempoRequest.parse(text)
    assert (r.lo, r.hi) == expected


@pytest.mark.parametrize("text", ["", "abc", "80-", "-80", "100-80", "31", "256", "80-300", "1.5", "80-90-100"])
def test_parse_invalid(text):
    with pytest.raises(ValueError):
        TempoRequest.parse(text)


def test_str_round_trip():
    assert str(TempoRequest(90, 90)) == "90" and str(TempoRequest(80, 100)) == "80-100"


def test_resolve_is_deterministic_and_within_range():
    p = profiles.get_profile("nostalgic")
    picks = {resolve_tempo(TempoRequest(80, 100), seed, p) for seed in range(200)}
    assert picks <= set(range(80, 101)) and len(picks) > 10
    assert resolve_tempo(TempoRequest(80, 100), 7, p) == resolve_tempo(TempoRequest(80, 100), 7, p)


def test_resolve_clips_partial_overlap_with_warning(caplog):
    p = profiles.get_profile("free-jazz")          # tempo_range が狭いジャンル
    lo, hi = p.tempo_range
    log = logging.getLogger("mod_weaver")
    log.addHandler(caplog.handler)          # cli が propagate=False にしている場合があるので直接付ける
    try:
        with caplog.at_level(logging.WARNING, logger="mod_weaver"):
            bpm = resolve_tempo(TempoRequest(hi - 5, 255), 1, p)
    finally:
        log.removeHandler(caplog.handler)
    assert hi - 5 <= bpm <= hi
    assert "clipped" in caplog.text


def test_resolve_rejects_disjoint_range():
    p = profiles.get_profile("free-jazz")
    with pytest.raises(TempoRangeError, match="free-jazz"):
        resolve_tempo(TempoRequest(p.tempo_range[1] + 1, 255), 1, p)


# suspense-* は BPM から効果音（swoosh/anvil）の配置 row を秒単位で逆算する設計なので、テンポが変われば
# 配置も意図どおり変わる（乱数消費は変わらない）。
BPM_DEPENDENT_LAYOUT = {"suspense-slow", "suspense-chase"}


@pytest.mark.parametrize("genre", [c.id for c in profiles.list_profiles() if c.id not in BPM_DEPENDENT_LAYOUT])
def test_same_seed_other_tempo_is_same_song(genre):
    """テンポ上書きは他の乱数消費を変えない: テンポ（Fxx≥32）の effect 以外の全セル内容が一致する。"""
    p = profiles.get_profile(genre)
    bpm = max(p.tempo_range[0], min(p.tempo_range[1], max(p.tempo_choices) + 7))
    base, _ = compose_song(p, 424242)
    fast, plan = compose_song(p, 424242, tempo=TempoRequest(bpm, bpm))
    assert plan.bpm == bpm

    def strip(song):
        return [[dataclasses.replace(c, effect=0, param=0) if c.effect == 0x0F and c.param >= 32 else c
                 for r in pat._cells for c in r] for pat in song.patterns]
    assert strip(base) == strip(fast)


def test_no_tempo_keeps_output_byte_identical():
    p = profiles.get_profile("nostalgic")
    assert writer.serialize(compose_song(p, 1)[0]) == writer.serialize(compose_song(p, 1, tempo=None)[0])


def test_tempo_is_written_as_fxx():
    p = profiles.get_profile("march")
    song, _ = compose_song(p, 1, tempo=TempoRequest(97, 97))
    first = song.patterns[song.order[0]]
    assert any(first.get(0, ch).effect == 0x0F and first.get(0, ch).param == 97 for ch in range(first.channels))


def test_free_jazz_curve_scales_with_start_bpm():
    p = profiles.get_profile("free-jazz")
    song, _ = compose_song(p, 1, tempo=TempoRequest(48, 48))
    tempos = [c.param for pat in song.patterns for c in [c for r in pat._cells for c in r] if c.effect == 0x0F and c.param >= 32]
    assert tempos[0] == 48 and min(tempos) >= 32 and max(tempos) == round(48 * 150 / 96)


def test_validate_profile_checks_tempo_range():
    base = profiles.get_profile("nostalgic")
    bad = type("Bad", (type(base),), {"tempo_range": (100, 120)})()   # tempo_choices が範囲外
    with pytest.raises(PlanError, match="tempo_range"):
        validate_profile(bad)


@pytest.mark.parametrize("genre", [c.id for c in profiles.list_profiles()])
def test_whole_tempo_range_generates_clean_output(genre):
    """tempo_range の全域で生成・検査が通る（実装時に 1 BPM 刻み×3 seed で総当たり確認済み。ここは粗い格子）。"""
    from mod_weaver.core import verify

    p = profiles.get_profile(genre)
    lo, hi = p.tempo_range
    for bpm in sorted({lo, hi, *range(lo, hi + 1, 29)}):
        song, _ = compose_song(p, 1, tempo=TempoRequest(bpm, bpm))
        for data, check in ((writer.serialize(song), verify.verify), (writer.serialize_xm(song), verify.verify_xm)):
            assert not verify.has_errors(check(data, p.channel_plan)), (genre, bpm)
