"""--tempo（DESIGN.md §5.5）のテスト。"""
from __future__ import annotations

import dataclasses
import logging

import pytest

from mod_weaver import engine
from mod_weaver.core import native
from mod_weaver.engine import TempoRequest, build, get_genre, resolve_tempo
from mod_weaver.errors import TempoRangeError
from mod_weaver.framework.compose import compose, resolve_plan
from mod_weaver.framework.realize.tracker import realize
from mod_weaver.framework.score import NoteEvent
from mod_weaver.framework.target import resolve


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
    g = get_genre("nostalgic")
    picks = {resolve_tempo(TempoRequest(80, 100), seed, g) for seed in range(200)}
    assert picks <= set(range(80, 101)) and len(picks) > 10
    assert resolve_tempo(TempoRequest(80, 100), 7, g) == resolve_tempo(TempoRequest(80, 100), 7, g)


def test_resolve_clips_partial_overlap_with_warning(caplog):
    g = get_genre("free-jazz")          # tempo_range が狭いジャンル
    lo, hi = g.tempo_range
    log = logging.getLogger("mod_weaver")
    log.addHandler(caplog.handler)          # cli が propagate=False にしている場合があるので直接付ける
    try:
        with caplog.at_level(logging.WARNING, logger="mod_weaver"):
            bpm = resolve_tempo(TempoRequest(hi - 5, 255), 1, g)
    finally:
        log.removeHandler(caplog.handler)
    assert hi - 5 <= bpm <= hi
    assert "clipped" in caplog.text


def test_resolve_rejects_disjoint_range():
    g = get_genre("free-jazz")
    with pytest.raises(TempoRangeError, match="free-jazz"):
        resolve_tempo(TempoRequest(g.tempo_range[1] + 1, 255), 1, g)


# suspense-* は BPM から効果音（swoosh/anvil）の配置 step を秒単位で逆算する設計、free-jazz はテンポカーブを書くので、
# テンポが変われば Score も意図どおり変わる（乱数消費は変わらない）。
BPM_DEPENDENT = {"suspense-slow", "suspense-chase", "free-jazz"}
IDS = [g.id for g in engine.list_genres()]


def _skeleton(score):
    return [(name, {p: ev for p, ev in sec.parts.items()}) for name, sec in score.sections.items()]


@pytest.mark.parametrize("genre", [g for g in IDS if g not in BPM_DEPENDENT])
def test_same_seed_other_tempo_is_same_song(genre):
    """テンポ上書きは他の乱数消費を変えない: テンポ以外の Score が一致する（同じ seed・別テンポ＝同じ曲の速さ違い）。"""
    g = get_genre(genre)
    bpm = max(g.tempo_range[0], min(g.tempo_range[1], max(g.tempo_choices) + 7))
    base = build(g, 424242)
    fast = build(g, 424242, tempo=TempoRequest(bpm, bpm))
    assert fast.plan.bpm == bpm and fast.score.bpm == bpm
    assert _skeleton(base.score) == _skeleton(fast.score)


def test_no_tempo_keeps_output_byte_identical():
    g = get_genre("nostalgic")
    assert build(g, 1).data == build(g, 1, tempo=None).data


def test_tempo_is_written_into_the_module():
    g = get_genre("march")
    plan = resolve_plan(g, 1)
    plan.bpm = 97
    score = compose(g, plan, 1, frozenset())
    rs = realize(g, score, plan, resolve("mod", None, g, 1))
    first = rs.patterns[rs.order[0]]
    assert rs.initial_bpm == 97 and any(first.get(r, ch).fx == ("F", 97) for r in range(8) for ch in range(first.channels))


def test_free_jazz_curve_scales_with_start_bpm():
    g = get_genre("free-jazz")
    score = build(g, 1, tempo=TempoRequest(48, 48)).score
    tempos = [t.bpm for sec in score.sections.values() for t in sec.tempo]
    assert tempos[0] == 48 and min(tempos) >= 32 and max(tempos) == round(48 * 150 / 96)


@pytest.mark.parametrize("genre", IDS)
def test_whole_tempo_range_generates_clean_output(genre):
    """tempo_range の全域で生成・検査が通る（粗い格子。MOD と IT）。"""
    g = get_genre(genre)
    lo, hi = g.tempo_range
    for bpm in sorted({lo, hi, *range(lo, hi + 1, 83)}):
        for fmt in ("mod", "it"):
            built = build(g, 1, fmt, tempo=TempoRequest(bpm, bpm))
            errors = [i for i in native.verify(fmt, built.data) if i.level == "ERROR"]
            assert not errors, (genre, fmt, bpm, errors)


def test_swing_never_overwrites_the_tempo_command():
    """全チャンネルが埋まった row に Speed を作るとき（スウィング）、先頭の Tempo のセルを消さない（jazz・seed 4・90 BPM で再現した不具合）。"""
    g = get_genre("jazz")
    built = build(g, 4, "mod", tempo=TempoRequest(90, 90))
    assert not [i for i in native.verify("mod", built.data) if i.level == "ERROR"]
