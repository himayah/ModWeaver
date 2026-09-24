"""第３段階のジャンル（profiles/band_common.BandProfile を使うもの）に共通の検査（DESIGN.md §6.14〜6.16）。

各ジャンル固有の性質は、ジャンルごとの検査関数を ``SPECIFIC`` に足して確かめる。
"""
from __future__ import annotations

import pytest

from mod_weaver import engine, profiles
from mod_weaver.core import formats
from mod_weaver.core.model import Pattern
from mod_weaver.profiles.band_common import BandProfile

STAGE3 = [p.id for p in profiles.list_profiles() if issubclass(p, BandProfile)]
SEEDS = range(1, 21)
TRACKER = ("mod", "xm", "s3m", "it", "midi")


def _cells(pattern: Pattern):
    for r in range(pattern.rows):
        for c in range(pattern.channels):
            yield r, c, pattern.get(r, c)


def test_there_are_stage3_genres():
    assert STAGE3


@pytest.mark.parametrize("genre", STAGE3)
def test_generates_cleanly_in_every_format(genre):
    """20 seed × 全形式で構造検査が ERROR も WARN も出さない。"""
    p = profiles.get_profile(genre)
    for seed in SEEDS:
        song, plan = engine.compose_song(p, seed)
        for fmt in TRACKER:
            data = engine.serialize(p, song, plan, fmt)
            bad = [i for i in formats.get_format(fmt).verify(data, p.channel_plan) if i.level != "INFO"]
            assert not bad, (seed, fmt, bad[:3])


@pytest.mark.parametrize("genre", STAGE3)
def test_declarations(genre):
    cls = profiles.get_profile(genre).__class__
    assert cls.category in ("mood", "genre", "style")
    assert len(cls.channel_plan) in (4, 6, 8) and len(cls.CHANNELS) == len(cls.channel_plan)
    assert set(cls.gm_voices) == set(cls._sample_keys) and len(cls._sample_keys) <= 31
    if len(cls.channel_plan) != 4:
        assert cls.channel_pans is not None and len(cls.channel_pans) == len(cls.channel_plan)
    assert set(cls.FORM) <= set(cls.SECTIONS)


@pytest.mark.parametrize("genre", STAGE3)
def test_deterministic_and_bpm_from_choices(genre):
    p = profiles.get_profile(genre)
    a, plan = engine.compose_song(p, 7)
    b, _ = engine.compose_song(profiles.get_profile(genre), 7)
    assert engine.serialize(p, a, plan, "mod") == engine.serialize(p, b, plan, "mod")
    assert plan.bpm in p.tempo_choices


@pytest.mark.parametrize("genre", STAGE3)
def test_tempo_override_keeps_the_song(genre):
    """--tempo は曲を変えず速さだけを変える（テンポのセル以外が同じ）。"""
    p = profiles.get_profile(genre)
    a, _ = engine.compose_song(p, 5)
    b, _ = engine.compose_song(p, 5, tempo=engine.TempoRequest(100, 100))
    for pa, pb in zip(a.patterns, b.patterns):
        for (r, c, ca), (_r, _c, cb) in zip(_cells(pa), _cells(pb)):
            if ca != cb:
                assert (ca.effect == 0xF and ca.param >= 32) or (cb.effect == 0xF and cb.param >= 32), (r, c, ca, cb)


@pytest.mark.parametrize("genre", STAGE3)
def test_sections_use_their_parts(genre):
    """区間で鳴らさないと宣言したパートのチャンネルに新しい音が出ない。"""
    p = profiles.get_profile(genre)
    cls = p.__class__
    song, plan = engine.compose_song(p, 3)
    part_ch = {}
    for name in ("BASS", "LEAD", "PAD", "ARP", "COMP"):
        spec = getattr(cls, name)
        if spec is not None:
            part_ch.setdefault(spec.channel, set()).add(name.lower())
    for pp, pattern in zip(plan.patterns, song.patterns):
        sec = cls.SECTIONS[pp.kind]
        for ch, names in part_ch.items():
            if names & sec.parts or ch in cls.DRUM_CHANNEL.values():
                continue
            notes = [r for r, c, cell in _cells(pattern) if c == ch and cell.note is not None]
            assert not notes, (pp.kind, ch, names, notes[:5])


def test_last_chorus_modulates_where_declared():
    for genre in ("pop", "jrock-90s"):
        cls = profiles.get_profile(genre).__class__
        assert any(s.key_offset for s in cls.SECTIONS.values()), genre


@pytest.mark.parametrize("genre", [g for g in STAGE3 if profiles.get_profile(g).SWING is not None])
def test_swing_sets_speed_on_every_row(genre):
    """スウィングの Speed が全 row に入る（空きの無い row を飛ばすと表示 BPM からずれる）。"""
    p = profiles.get_profile(genre)
    for seed in (1, 2, 3):
        song, _ = engine.compose_song(p, seed)
        for i, pattern in enumerate(song.patterns):
            missing = [r for r in range(pattern.rows)
                       if not any(pattern.get(r, c).effect == 0xF for c in range(pattern.channels))]
            assert not missing, (seed, i, missing[:5])


def test_classical_is_four_measures_of_three_four():
    """classical は 3/4（12 row）× 4小節＝48 row で、最終 row に D00。"""
    p = profiles.get_profile("classical")
    song, plan = engine.compose_song(p, 1)
    for pp, pattern in zip(plan.patterns, song.patterns):
        assert sum(s.measures for s in pp.slots) == 4
        assert any(pattern.get(47, c).effect == 0xD for c in range(pattern.channels)), pp.kind


def test_pitched_drum_in_groove_needs_a_note():
    """音程のある楽器（タム）を音高なしでドラムの型に書くと、鳴らない音量だけのセルになるのでクラス定義で弾く。"""
    from mod_weaver.errors import PlanError
    from mod_weaver.profiles.band_common import ChannelDef, hits, preset

    with pytest.raises(PlanError, match="pitched 'tom'"):
        class Bad(BandProfile):
            KIT = (("tom", preset("drum_tom")),)
            CHANNELS = (ChannelDef("tom", ("tom",)),)
            GROOVES = {"main": hits("tom", (0,), 50)}


def test_tom_fills_sound():
    """rock・energetic のフィルのタムが音高付きで鳴る（以前は音量だけのセルで無音だった）。"""
    for genre in ("rock", "energetic"):
        p = profiles.get_profile(genre)
        song, _ = engine.compose_song(p, 1)
        ch = p.__class__.DRUM_CHANNEL["tom"]
        assert any(pt.get(r, ch).note is not None for pt in song.patterns for r in range(pt.rows)), genre
