"""F6〜F7 で移植したジャンル（``mod_weaver/genres/``）の共通検査（DESIGN.md §10.1・§6.14）。

- I1 骨格の不変・I2 決定性・I3 全予算 × 全形式で生成でき検査に ERROR が無い（MIDI を含む）。
- 全パートが鳴る（宣言したパートが、どの区間でも鳴らないままになっていない。移植の取りこぼしの検出）。
- 編成の対応表（DESIGN.md §6.14）: 旧 ``ARRANGEMENTS`` の各編成（``port_layouts.LAYOUTS``。旧実装を消す前に旧クラスから生成して固定した
  もの）と、新しい ladder の lane の並び・楽器・パン・畳んだときの優先順位。
"""
from __future__ import annotations

import dataclasses

import pytest

from mod_weaver.core import native
from mod_weaver.framework import registry as new_registry
from mod_weaver.framework.compose import compose, resolve_plan
from mod_weaver.framework.realize import lanes as lanesmod
from mod_weaver.framework.realize.midi import realize_midi
from mod_weaver.framework.realize.tracker import realize
from mod_weaver.framework.score import Automation, NoteEvent, NoteOff
from mod_weaver.framework.target import resolve
from tests.framework.port_layouts import LAYOUTS

new_registry.discover("mod_weaver.genres")
IDS = sorted(new_registry.GENRE_REGISTRY)

# F6 で移植するジャンル（A: 宣言だけ 13・B: パートの上書きあり 26）。``discover()`` は壊れたモジュールを警告だけで飛ばすので、
# 登録が黙って抜けないようにここで数える。
PORTED_F6 = {
    "cool", "dreamy", "focus", "hiphop", "house", "lofi-chill", "lofi-hiphop", "melancholic", "neo-soul", "pop",
    "rnb-soul", "synthwave", "warm",
    "acoustic-ssw", "ambient", "ambient-drone", "anime-ost", "bossa-nova", "calm", "chiptune", "cinematic", "city-pop",
    "classical", "dark-tense", "edm", "energetic", "folk", "gamelan", "indie-rock", "industrial", "jazz", "jpop-80s",
    "jrock-90s", "jrpg", "racing-breaks", "rock", "techno", "trailer", "uplifting",
}


# F7 で移植するジャンル（C: 個別実装 12）。
PORTED_F7 = {
    "nostalgic", "suspense-slow", "suspense-chase", "march", "swing-jazz", "prog-rock", "trap", "future-bass",
    "maqam", "free-jazz", "minimalism", "orchestral",
}
PORTED = PORTED_F6 | PORTED_F7


def test_every_f6_genre_is_registered():
    assert PORTED_F6 <= set(IDS), sorted(PORTED_F6 - set(IDS))


def test_every_f7_genre_is_registered_and_all_51_are_ported():
    assert PORTED_F7 <= set(IDS), sorted(PORTED_F7 - set(IDS))
    assert set(IDS) == PORTED and len(IDS) == 51, sorted(set(IDS) ^ PORTED)

# 旧の編成から意図して変えたもの（DESIGN.md §6.14: 一致しない場合は ladder の結果を採用してよいが、差を書く）
# 並びだけが違う（lane の楽器・パンは同じ）ものを記録する。理由: 旧版は打楽器の論理チャンネルが離れていた（例: 6番目に
# tom／shaker）が、新しい編成は打楽器を1つの drums パートにまとめるので打楽器の lane が先頭にまとまる。MOD はパンが
# チャンネル番号で固定（L R R L）なので、並びの違いはステレオの配置がずれる（楽器の音自体は同じ）。
_DRUM_ORDER = "打楽器の論理チャンネルが離れていた旧版と lane の並びだけが違う（楽器・パンは同じ）"
LAYOUT_DIFFS: dict[tuple[str, int], str] = {
    (gid, n): _DRUM_ORDER for gid in ("house", "energetic", "rock") for n in (6, 8)
}
LAYOUT_DIFFS.update({("jrock-90s", n): "dist gtr・clean gtr を1つの guitars パートにしたので、lead gtr との並びが入れ替わる" for n in (6, 8)})
# 全パート検査の除外（確率で鳴らないことがあるパート）。(ジャンル, パート名)
MAY_BE_SILENT: set[tuple[str, str]] = set()


def _genre(gid):
    return new_registry.GENRE_REGISTRY[gid]()


def _score(genre, seed=1, features=frozenset()):
    plan = resolve_plan(genre, seed=seed)
    return plan, compose(genre, plan, seed=seed, features=features)


def _skeleton(score):
    """奏法（arts）を除いた Score（I1 の比較用）。"""
    out = []
    for name in score.order:
        sec = score.sections[name]
        parts = {}
        for p, events in sec.parts.items():
            parts[p] = [dataclasses.replace(e, arts=()) if isinstance(e, NoteEvent) else e for e in events]
        out.append((name, parts, tuple(sec.tempo)))
    return out


@pytest.mark.parametrize("gid", IDS)
def test_skeleton_is_independent_of_format_features(gid):
    """I1: どの形式の features で作っても、奏法を除いた Score は同じ。"""
    genre = _genre(gid)
    feats = [resolve(f, None, genre, 1).features for f in ("mod", "s3m", "it", "midi")]
    base = _skeleton(_score(genre, 1, feats[0])[1])
    for f in feats[1:]:
        assert _skeleton(_score(genre, 1, f)[1]) == base


@pytest.mark.parametrize("gid", IDS)
def test_every_declared_part_plays_somewhere(gid):
    genre = _genre(gid)
    played: set[str] = set()
    for seed in (1, 2, 3):
        _plan, score = _score(genre, seed)
        for sec in score.sections.values():
            for p, events in sec.parts.items():
                if any(isinstance(e, NoteEvent) for e in events):
                    played.add(p)
    silent = {p.name for p in genre.parts} - played
    assert not {(gid, p) for p in silent} - MAY_BE_SILENT, f"parts that never play: {sorted(silent)}"


def _budgets(genre):
    return sorted(genre.mod_channels)


@pytest.mark.parametrize("gid", IDS)
def test_generates_and_verifies_in_every_format(gid):
    """I3: MOD は宣言の全予算、S3M・XM・IT は既定と min(mod_channels) の予算、MIDI。ERROR が無く、決定的。"""
    genre = _genre(gid)
    for seed in (1, 2):
        plan, score = _score(genre, seed)
        for b in _budgets(genre):
            data = native.serialize(realize(genre, score, plan, resolve("mod", b, genre, seed)))
            errors = [i for i in native.verify("mod", data) if i.level == "ERROR"]
            assert not errors, (gid, "mod", b, seed, errors)
        for fmt in ("s3m", "xm", "it"):
            for ch in (None, min(genre.mod_channels)):
                rs = realize(genre, score, plan, resolve(fmt, ch, genre, seed))
                data = native.serialize(rs)
                errors = [i for i in native.verify(fmt, data) if i.level == "ERROR"]
                assert not errors, (gid, fmt, ch, seed, errors)
        midi = realize_midi(genre, score, plan, resolve("midi", None, genre, seed))
        assert not [i for i in native.verify("midi", midi) if i.level == "ERROR"], (gid, "midi", seed)
    # I2
    plan, score = _score(genre, 1)
    a = native.serialize(realize(genre, score, plan, resolve("it", None, genre, 1)))
    plan2, score2 = _score(genre, 1)
    assert a == native.serialize(realize(genre, score2, plan2, resolve("it", None, genre, 1)))


# ---- 編成の対応表（旧 ``ARRANGEMENTS`` から固定した期待値 ``port_layouts.LAYOUTS`` との比較）----

def _expected(gid):
    return LAYOUTS[gid]


@pytest.mark.parametrize("gid", sorted(LAYOUTS))
def test_ladder_matches_the_recorded_arrangement(gid):
    genre = _genre(gid)
    _plan, score = _score(genre, 1)
    for n, (roles, pans) in _expected(gid).items():
        layout = lanesmod.compute_layout(genre, score, n)
        lanes = [l for l in layout.lanes if l.role != "control"]
        if (gid, n) in LAYOUT_DIFFS:      # 並びだけ違う: 楽器とパンの組が同じ集合になる
            pairs = sorted((tuple(sorted(l.insts)), l.pan) for l in lanes if l.insts)
            assert len(lanes) == len(roles), (gid, n)
            for insts, pan in pairs:
                assert any(set(insts) <= set(names) and (pans is None or pan in pans) for names, _ in roles), \
                    (gid, n, insts, pan)
            continue
        assert len(lanes) == len(roles), (gid, n, [l.insts for l in lanes], [r[0] for r in roles])
        for lane, (names, _prio) in zip(lanes, roles):
            if lane.insts:      # Echo などは自分の楽器を持たない
                assert set(lane.insts) <= set(names), (gid, n, lane.insts, names)
        if pans is not None:
            assert [l.pan for l in lanes] == list(pans), (gid, n, [l.pan for l in lanes], pans)


@pytest.mark.parametrize("gid", sorted(LAYOUTS))
def test_folded_drum_priorities_match_the_recorded_ones(gid):
    """同じ lane に畳まれた打楽器の2つが同じ row に来たとき、どちらが残るかが旧と同じ（優先度の表の写し間違いの検出）。"""
    genre = _genre(gid)
    _plan, score = _score(genre, 1)
    for n, (roles, _pans) in _expected(gid).items():
        layout = lanesmod.compute_layout(genre, score, n)
        lanes = [l for l in layout.lanes if l.role == "kit"]
        old_kit = [r for r in roles if len(r[0]) > 1 and any(k in genre.instruments and genre.instruments[k].gm.is_drum
                                                              for k in r[0])]
        for lane in lanes:
            if len(lane.insts) < 2:
                continue
            ref = next((r for r in old_kit if set(lane.insts) <= set(r[0])), None)
            if ref is None:
                continue
            for i, a in enumerate(lane.insts):
                for b in lane.insts[i + 1:]:
                    new_win = a if lane.priority.get(a, 1) >= lane.priority.get(b, 1) else b
                    old_win = a if ref[1].get(a, 1) >= ref[1].get(b, 1) else b
                    assert new_win == old_win, (gid, n, a, b, lane.priority, ref[1])


# ============================================================
# ジャンル固有の性質（旧 tests/profiles/test_stage3_genres.py を Score・Realizer の言葉で書き直したもの）
# ============================================================

@pytest.mark.parametrize("gid", IDS)
def test_only_participating_parts_have_events(gid):
    """区間で鳴らさないと宣言したパート（と、その follow）には音が出ない。"""
    genre = _genre(gid)
    _plan, score = _score(genre, 3)
    by_name = {p.name: p for p in genre.parts}
    for name, sec in score.sections.items():
        playing = set(sec.plan.parts)
        for part in genre.parts:
            if part.follow is not None:
                continue
        for pname, events in sec.parts.items():
            if not any(isinstance(e, NoteEvent) for e in events):
                continue
            root = pname
            while by_name[root].follow is not None:
                root = by_name[root].follow
            assert root in playing or pname in playing or sec.plan.section.tags, (gid, name, pname)


@pytest.mark.parametrize("gid", IDS)
def test_tempo_is_one_of_the_choices_and_seed_changes_only_declared_things(gid):
    genre = _genre(gid)
    plan, score = _score(genre, 7)
    assert plan.bpm in genre.tempo_choices
    assert _skeleton(_score(genre, 7)[1]) == _skeleton(score)


@pytest.mark.parametrize("gid", IDS)
def test_mod_channel_count_is_chosen_by_seed_and_unsupported_counts_are_rejected(gid):
    from mod_weaver.errors import ChannelCountError

    genre = _genre(gid)
    chosen = {resolve("mod", None, genre, seed).budget for seed in range(1, 61)}
    assert chosen == set(genre.mod_channels)
    with pytest.raises(ChannelCountError):
        resolve("mod", 5, genre, 1)


def test_classical_is_four_measures_of_three_four_with_a_pattern_break():
    genre = _genre("classical")
    plan, score = _score(genre, 1)
    for sec in score.sections.values():
        assert sec.plan.steps == 48 and len(sec.plan.measures) == 4 and sec.plan.meter.signature == (3, 4)
    rs = realize(genre, score, plan, resolve("mod", 4, genre, 1))
    for pat in rs.patterns:
        assert pat.rows == 64 and any(pat.get(47, c).fx == ("D", 0) for c in range(pat.channels))


@pytest.mark.parametrize("gid", ["rock", "energetic"])
def test_tom_fills_sound(gid):
    """rock・energetic のフィルのタムが音高付きで鳴る（旧版は一時期、音量だけのセルで無音だった）。"""
    genre = _genre(gid)
    _plan, score = _score(genre, 1)
    toms = [e for s in score.sections.values() for ev in s.parts.values() for e in ev
            if isinstance(e, NoteEvent) and e.inst == "tom"]
    assert toms and all(e.pitch is not None for e in toms)


def test_swing_sets_speed_on_every_row_in_every_format():
    """スウィングの Speed が全 row に入る（空きの無い row を飛ばすと表示 BPM からずれる）。"""
    genre = _genre("jazz")
    for seed in (1, 2, 3):
        plan, score = _score(genre, seed)
        for fmt, ch in (("mod", 4), ("s3m", None), ("xm", None), ("it", None)):
            rs = realize(genre, score, plan, resolve(fmt, ch, genre, seed))
            speed = "F" if fmt in ("mod", "xm") else "A"
            for i, pat in enumerate(rs.patterns):
                missing = [r for r in range(8 * 8) if r < pat.rows and not any(
                    pat.get(r, c).fx is not None and pat.get(r, c).fx[0] == speed and pat.get(r, c).fx[1] < 32
                    for c in range(pat.channels))]
                # 先頭の pattern break（空の row を使う D00・C00）の後ろは見ない
                assert not [r for r in missing if r < 64], (fmt, seed, i, missing[:5])


def test_last_chorus_modulates_where_declared():
    for gid in ("pop", "jrock-90s"):
        assert any(s.key_offset for s in _genre(gid).sections.values()), gid
