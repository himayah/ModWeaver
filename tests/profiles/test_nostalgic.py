"""Nostalgic 固有の維持挙動（Quirk Q1〜Q7）と補助関数。"""
from __future__ import annotations

import pytest

from mod_weaver import engine
from mod_weaver.core import pitch
from mod_weaver.core.model import Cell
from mod_weaver.core.verify import verify
from mod_weaver.core.writer import serialize
from mod_weaver.profiles import get_profile, nostalgic

profile = get_profile("nostalgic")
SEEDS = [1, 42, 100000, 732501, 999999]


def song(seed):
    return engine.build_song(profile, seed)


def test_declaration():
    assert (profile.title, profile.default_filename) == ("Twilight Pad", "TwilightPad.mod")
    assert profile.tempo_choices == (88, 90, 92, 94, 96)
    assert (profile.tempo_policy, profile.rng_mode, profile.strict_buffers) == ("profile", "single", False)
    assert profile.rows_per_measure == 16
    assert [sorted(r.allowed) for r in profile.channel_plan] == [[1, 2, 3], [4], [6], [5]]


@pytest.mark.parametrize("seed", SEEDS)
def test_q1_q2_tempo_cells(seed):
    s = song(seed)
    bpm = engine.compose_song(profile, seed)[1].bpm
    intro, a, b, outro = s.patterns
    assert intro.get(0, 0) == Cell(None, 0, 0x0F, bpm)              # Q2: 音なし + F bpm
    assert a.get(0, 0) == Cell(pitch.parse("C-3"), 1, 0x0F, bpm)    # Q2: キック + F bpm
    assert b.get(0, 0) == Cell(pitch.parse("C-3"), 1, 0x0F, bpm)
    assert outro.get(0, 0).effect != 0x0F                           # Q1: テンポセルなし
    assert outro.get(0, 0) == Cell(pitch.parse("C-3"), 1, vol=46)


@pytest.mark.parametrize("seed", SEEDS)
def test_q4_flute_is_unused_and_verify_reports_info_only(seed):
    s = song(seed)
    used = {p.get(r, c).sample for p in s.patterns for r in range(64) for c in range(4)}
    assert 7 not in used and used >= {1, 2, 3, 4, 5, 6}
    assert {i.code for i in verify(serialize(s), profile.channel_plan)} == {"V13"}


def test_q3_pad_loop_is_the_original_flat_loop():
    pad = profile.build_samples()["pad"]
    assert len(pad.data) == 1024 and pad.loop == (0, 512)


@pytest.mark.parametrize("seed", SEEDS)
def test_q5_chorus_melody_is_capped_at_octave_3(seed):
    b = song(seed).patterns[2]
    notes = [b.get(r, 3).note for r in range(64) if b.get(r, 3).note is not None]
    assert notes and max(notes) <= pitch.parse("B-3") and min(notes) >= pitch.parse("C-2")


@pytest.mark.parametrize("seed", SEEDS)
def test_q6_ghost_and_fill(seed):
    s = song(seed)
    for pat, chorus in ((s.patterns[1], False), (s.patterns[2], True)):
        assert pat.get(62, 0) == Cell(24, 3, vol=34) and pat.get(63, 0) == Cell(24, 2, vol=46)   # bar3 フィル
        ghosts = [pat.get(m * 16 + 15, 0) for m in range(3)]
        expected = Cell(24, 3, vol=24)
        assert all(g == expected for g in ghosts) or all(g != expected for g in ghosts)
        if not chorus:
            assert all(g != expected for g in ghosts)


def test_outro_fade_cells_and_intro_silence_of_drums():
    s = song(1)
    outro, intro = s.patterns[3], s.patterns[0]
    assert outro.get(56, 2) == Cell(None, 0, vol=18) and outro.get(60, 2) == Cell(None, 0, vol=8)
    assert outro.get(63, 2) == Cell(None, 0, vol=0)
    assert all(intro.get(r, 1).is_empty for r in range(64))                   # イントロにベースなし
    assert [intro.get(r, 0) for r in range(1, 64)] == [Cell()] * 63          # ドラムなし（row0 はテンポのみ）


def test_legacy_cell_clamps_volume_like_old_cell():
    c = nostalgic._legacy_cell(24, 1, -5)
    assert c.vol == 0
    assert nostalgic._legacy_cell(24, 1, 99).vol == 64
    assert nostalgic._legacy_cell(24, 1, 40.9).vol == 40      # int() で切捨て（旧仕様）


def test_shift_octave_caps_at_3():
    assert nostalgic._shift_octave(pitch.parse("A-2"), 1) == pitch.parse("A-3")
    assert nostalgic._shift_octave(pitch.parse("A-3"), 1) == pitch.parse("A-3")
    assert nostalgic._shift_octave(pitch.parse("C-2"), 0) == pitch.parse("C-2")


def test_chord_defs_are_explicit_and_within_scale_notes():
    for name, cd in nostalgic.CHORD_DEFS.items():
        assert cd.explicit and cd.label == name and cd.arp is None
        assert set(cd.chord_tones) <= set(nostalgic.SCALE_NOTES)
        assert set(cd.scale_tones) <= set(nostalgic.SCALE_NOTES)
    assert len(nostalgic.CHORD_DEFS["Cmaj7"].chord_tones) == 5
    assert nostalgic.CHORD_DEFS["Fmaj7"].bass == pitch.parse("F-2")
    assert nostalgic.CHORD_DEFS["Fmaj7"].harmony == pitch.parse("C-3")


def test_melody_bar_edge_cases():
    """短いコードトーン列・カデンツ・音域外の scale_tones でも旧実装どおり動く。"""
    import random
    cd = nostalgic.CHORD_DEFS["G7"]
    notes, last = nostalgic._melody_bar(random.Random(3), cd, [0, 4, 8, 12], None, 0, True)
    assert [n[0] for n in notes] == [0, 4, 8, 12] and notes[-1][1] == cd.chord_tones[0] and last == notes[-1][1]
    assert notes[0][2] == 60 and all(48 <= v <= 56 for _, _, v in notes[1:])
