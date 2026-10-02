"""F6〜F7 で移植したジャンル（``mod_weaver/genres_next/``）の共通検査（FRAMEWORK_REDESIGN.md §13.1・§15.1）。

- I1 骨格の不変・I2 決定性・I3 全予算 × 全形式で生成でき検査に ERROR が無い（MIDI を含む）。
- 全パートが鳴る（宣言したパートが、どの区間でも鳴らないままになっていない。移植の取りこぼしの検出）。
- 編成の対応表（§15.1）: 旧 ``ARRANGEMENTS`` の各編成と、新しい ladder の lane の並び・楽器・パン・畳んだときの優先順位。
  旧クラスを読むので、旧 ``mod_weaver/genres/`` が残っている間だけ動く（F8 で旧を消すときに、この表を「新しい編成の期待値」
  のテストに書き換える）。
"""
from __future__ import annotations

import dataclasses

import pytest

from mod_weaver import profiles
from mod_weaver.core import native
from mod_weaver.framework import registry as new_registry
from mod_weaver.framework.compose import compose, resolve_plan
from mod_weaver.framework.realize import lanes as lanesmod
from mod_weaver.framework.realize.midi import realize_midi
from mod_weaver.framework.realize.tracker import realize, realize_mod
from mod_weaver.framework.score import Automation, NoteEvent, NoteOff
from mod_weaver.framework.target import resolve
from mod_weaver.profiles.registry import PROFILE_REGISTRY

new_registry.discover("mod_weaver.genres_next")
profiles.discover("mod_weaver.genres")
IDS = sorted(new_registry.GENRE_REGISTRY)

# 旧の編成から意図して変えたもの（§15.1: 一致しない場合は ladder の結果を採用してよいが、差を書く）
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
            song, opts = realize_mod(genre, score, plan, resolve("mod", b, genre, seed))
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


# ---- 編成の対応表（旧との比較）----

_QUALITY_SUFFIXES = {"maj", "min", "m7", "maj7", "dom7", "sus4", "sus2", "m9", "maj9", "dim", "aug", "7", "9",
                     "add9", "m6", "6", "7sus4", "dom9", "dim7", "m7b5", "mmaj7", "m11", "maj13", "13", "11"}


def _base(name: str) -> str:
    head, _, tail = name.rpartition("_")
    return head if head and tail in _QUALITY_SUFFIXES else name


def _old_arrangements(gid):
    old = PROFILE_REGISTRY[gid]
    out = {}
    for n, (phys, pans, sources, _gains, _to_phys) in sorted(old._arr.items()):
        out[n] = [(sorted({_base(old._sample_keys[s - 1]) for s in r.allowed}),
                   {_base(old._sample_keys[s - 1]): pr for s, pr in r.priority.items()}) for r in phys], pans
    return out


@pytest.mark.parametrize("gid", [g for g in IDS if g in PROFILE_REGISTRY])
def test_ladder_matches_the_old_arrangement(gid):
    genre = _genre(gid)
    old = _old_arrangements(gid)
    if not old:      # 編成を選ばない旧ジャンル（論理チャンネル＝物理チャンネル）
        pytest.skip("fixed channel plan")
    _plan, score = _score(genre, 1)
    for n, (roles, pans) in old.items():
        layout = lanesmod.compute_layout(genre, score, n)
        lanes = [l for l in layout.lanes if l.role != "control"]
        if (gid, n) in LAYOUT_DIFFS:      # 並びだけ違う: 楽器とパンの組が同じ集合になる
            pairs = sorted((tuple(sorted(l.insts)), l.pan) for l in lanes if l.insts)
            assert len(lanes) == len(roles), (gid, n)
            for insts, pan in pairs:
                assert any(set(insts) <= set(names) and (pans is None or pan in pans) for names, _ in roles),                     (gid, n, insts, pan)
            continue
        assert len(lanes) == len(roles), (gid, n, [l.insts for l in lanes], [r[0] for r in roles])
        for lane, (names, _prio) in zip(lanes, roles):
            if lane.insts:      # Echo などは自分の楽器を持たない
                assert set(lane.insts) <= set(names), (gid, n, lane.insts, names)
        if pans is not None:
            assert [l.pan for l in lanes] == list(pans), (gid, n, [l.pan for l in lanes], pans)


@pytest.mark.parametrize("gid", [g for g in IDS if g in PROFILE_REGISTRY])
def test_folded_drum_priorities_match_the_old_ones(gid):
    """同じ lane に畳まれた打楽器の2つが同じ row に来たとき、どちらが残るかが旧と同じ（優先度の表の写し間違いの検出）。"""
    genre = _genre(gid)
    old = _old_arrangements(gid)
    _plan, score = _score(genre, 1)
    for n, (roles, _pans) in old.items():
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


def test_no_unported_override_is_left_behind():
    """変換ツール（tools/port_band_genre.py）が残した TODO（上書きメソッドの未移植）が無い。"""
    import pathlib

    root = pathlib.Path(__file__).resolve().parents[2] / "mod_weaver" / "genres_next"
    left = [f.name for f in sorted(root.glob("*.py")) if "TODO" in f.read_text(encoding="utf-8")]
    assert not left, left
