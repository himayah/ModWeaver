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
ARRANGED = [g for g in STAGE3 if profiles.get_profile(g).channel_choices]
# (ジャンル, チャンネル数)。編成を選ぶジャンル（DESIGN.md §6.14）は編成ごとに検査する
GENRE_CHANNELS = [(g, n) for g in STAGE3 for n in engine.channel_choices(profiles.get_profile(g))]
SEEDS = range(1, 21)
TRACKER = ("mod", "xm", "s3m", "it", "midi")


def _cells(pattern: Pattern):
    for r in range(pattern.rows):
        for c in range(pattern.channels):
            yield r, c, pattern.get(r, c)


def test_there_are_stage3_genres():
    assert STAGE3


@pytest.mark.parametrize("genre,channels", GENRE_CHANNELS)
def test_generates_cleanly_in_every_format(genre, channels):
    """20 seed（編成を選ぶジャンルは編成ごとに 10 seed）× 全形式で構造検査が ERROR も WARN も出さない。"""
    p = profiles.get_profile(genre)
    for seed in SEEDS if not p.channel_choices else range(1, 11):
        song, plan = engine.compose_song(p, seed, channels=channels)
        physical = engine.effective_channel_plan(p, plan)
        assert len(physical) == channels and all(pt.channels == channels for pt in song.patterns)
        for fmt in TRACKER:
            data = engine.serialize(p, song, plan, fmt)
            bad = [i for i in formats.get_format(fmt).verify(data, physical) if i.level != "INFO"]
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
    assert set(engine.channel_choices(cls)) <= {4, 6, 8}


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


@pytest.mark.parametrize("genre,channels", GENRE_CHANNELS)
def test_sections_use_their_parts(genre, channels):
    """区間で鳴らさないと宣言したパートのチャンネルに新しい音が出ない（編成に畳んだ後の物理チャンネルで）。"""
    p = profiles.get_profile(genre)
    cls = p.__class__
    song, plan = engine.compose_song(p, 3, channels=channels)
    to_phys = plan.patterns[0].extra.get("channel_map") or tuple(range(len(cls.CHANNELS)))
    part_ch = {}
    for name in ("BASS", "LEAD", "PAD", "ARP", "COMP"):
        spec = getattr(cls, name)
        if spec is not None:
            part_ch.setdefault(spec.channel, set()).add(name.lower())
    for layer in cls.LAYERS:
        part_ch.setdefault(layer.channel, set()).add(layer.follow)
    for e in cls.ECHO:                          # エコーは元のパートと同じ区間でだけ鳴る
        part_ch.setdefault(e.dst, set()).update(part_ch.get(e.src, set()))
    shared = {to_phys[c] for c in cls.DRUM_CHANNEL.values()}
    phys_parts = {}                             # 物理チャンネル → そこに畳んだパート（どれかが鳴る区間なら音があってよい）
    for ch, names in part_ch.items():
        if to_phys[ch] is not None:
            phys_parts.setdefault(to_phys[ch], set()).update(names)
    folded = {to_phys[c] for c in range(len(cls.CHANNELS)) if to_phys[c] is not None and c not in part_ch}
    for pp, pattern in zip(plan.patterns, song.patterns):
        sec = cls.SECTIONS[pp.kind]
        for phys, names in phys_parts.items():
            if not names or names & sec.parts or phys in shared or phys in folded:
                continue
            notes = [r for r, c, cell in _cells(pattern) if c == phys and cell.note is not None]
            assert not notes, (pp.kind, phys, names, notes[:5])


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


# --- 曲ごとのチャンネル数（DESIGN.md §6.14） ---

@pytest.mark.parametrize("genre", ARRANGED)
def test_every_arrangement_plays_the_same_notes(genre):
    """編成は厚みとチャンネル数だけを変える: そのまま写す物理チャンネルの音符は、どの編成でも同じ論理チャンネルの音符。
    例外は曲の先頭 row 0・1（テンポのコマンドの場所を作るために、チャンネル数によって音が row 1 へ移るか消える）。"""
    p = profiles.get_profile(genre)
    cls = p.__class__
    names = [cd.name for cd in cls.CHANNELS]

    def notes(n):
        song, plan = engine.compose_song(p, 4, channels=n)
        out = {}
        for fold, pattern_ch in zip(cls.ARRANGEMENTS[n], range(n)):
            if len(fold.sources) == 1:
                out[fold.sources[0]] = [(i, r, c.note, song.instrument_names[c.sample - 1])
                                        for i, pt in enumerate(song.patterns) for r in range(pt.rows)
                                        for c in [pt.get(r, pattern_ch)]
                                        if c.note is not None and not (i == song.order[0] and r < 2)]
        return out

    per = {n: notes(n) for n in cls.ARRANGEMENTS}
    for name in names:
        seen = [v[name] for v in per.values() if name in v]
        assert all(x == seen[0] for x in seen), name


@pytest.mark.parametrize("genre", ARRANGED)
def test_arrangement_is_chosen_by_seed_and_kept_by_tempo(genre):
    """--channels が無ければ seed から選ぶ（全候補が現れる・同じ seed なら同じ）。--tempo を付けても変わらない。"""
    p = profiles.get_profile(genre)
    chosen = {}
    for seed in range(1, 41):
        _song, plan = engine.compose_song(p, seed)
        chosen[seed] = len(engine.effective_channel_plan(p, plan))
    assert set(chosen.values()) == set(p.channel_choices)
    _song, plan = engine.compose_song(p, 7, tempo=engine.TempoRequest(100, 100))
    assert len(engine.effective_channel_plan(p, plan)) == chosen[7]


def test_unsupported_channel_count_is_rejected():
    from mod_weaver.errors import ChannelCountError

    with pytest.raises(ChannelCountError, match="supports 4/6/8"):
        engine.compose_song(profiles.get_profile("pop"), 1, channels=5)
    with pytest.raises(ChannelCountError, match="supports 4"):
        engine.compose_song(profiles.get_profile("calm"), 1, channels=6)


def test_arrangement_cannot_fold_looping_sounds():
    """ループの音色を別のチャンネルと畳むと途中で切れるので、クラス定義で弾く。"""
    from mod_weaver.errors import PlanError
    from mod_weaver.profiles.band_common import ChannelDef, Fold, preset

    with pytest.raises(PlanError, match="folds looping sounds"):
        class Bad(BandProfile):
            KIT = (("kick", preset("drum_pop_kick")), ("pad", preset("pad_warm")))
            CHANNELS = (ChannelDef("kick", ("kick",)), ChannelDef("pad", ("pad",)))
            ARRANGEMENTS = {1: (Fold("all", ("kick", "pad")),)}
