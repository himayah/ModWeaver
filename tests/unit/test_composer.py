from __future__ import annotations

import random

import pytest

from mod_weaver.core.composer import (
    MelodyGenerator, NoteEvent, RhythmMotif, ScaleRules, ramp,
)
from mod_weaver.core.harmony import Registers, voice
from mod_weaver.core.model import ChordSpec
from mod_weaver.core.pitch import MODES, Scale
from mod_weaver.errors import PlanError

REG = (24, 41)
SCALE = Scale(0, MODES["phrygian"])
CHORD = voice(ChordSpec(0, "min"), 0, SCALE, Registers((0, 11), (17, 28), REG))
MOTIFS = [RhythmMotif((0, 4, 8, 12)), RhythmMotif((0, 3, 6, 10)), RhythmMotif((0, 6, 8, 12)), RhythmMotif((0, 2, 4, 6, 8, 10, 12, 14))]


def run(rules, seed, bars=40, **kw):
    gen = MelodyGenerator(rules, REG, SCALE, random.Random(seed))
    out, prev = [], None
    for b in range(bars):
        ev, prev = gen.bar(MOTIFS[b % len(MOTIFS)], CHORD, prev, **kw)
        out.append(ev)
    return out


# ---------------- RhythmMotif ----------------

def test_motif_durations():
    assert RhythmMotif((0, 6)).durations(16) == (6, 10)
    assert RhythmMotif((0, 3, 4, 7)).durations(8) == (3, 1, 3, 1)
    assert RhythmMotif((0, 4), (3, 3)).durations(16) == (3, 3)      # 明示（休符あり）
    assert RhythmMotif((0,)).durations(8) == (8,)


@pytest.mark.parametrize("args", [((),), ((4, 2),), ((-1, 2),), ((0, 4), (1,)), ((0, 4), (1, 0))])
def test_motif_validation(args):
    with pytest.raises(PlanError):
        RhythmMotif(*args)


def test_motif_row_outside_measure():
    with pytest.raises(PlanError):
        RhythmMotif((0, 8)).durations(8)


# ---------------- MelodyGenerator ----------------

@pytest.mark.parametrize("seed", range(5))
def test_notes_stay_in_register_and_scale_or_color(seed):
    rules = ScaleRules(dissonance_weight=0.5, leap_probability=0.4)
    for bar in run(rules, seed, octave_shift=0) + run(rules, seed, octave_shift=1):
        for ev in bar:
            assert REG[0] <= ev.note <= REG[1] and 1 <= ev.vol <= 64


def test_strong_beats_are_chord_tones_even_with_dissonance():
    tones = {n % 12 for n in CHORD.chord_tones}
    for seed in range(5):
        for bar in run(ScaleRules(dissonance_weight=1.0), seed):
            for ev in bar:
                if ev.row % 4 == 0:
                    assert ev.note % 12 in tones


def test_zero_dissonance_gives_only_scale_or_chord_notes():
    allowed = {n % 12 for n in CHORD.scale_tones}
    for bar in run(ScaleRules(dissonance_weight=0.0), 3):
        assert all(ev.note % 12 in allowed for ev in bar)


def test_dissonance_produces_out_of_chord_weak_notes():
    tones = {n % 12 for n in CHORD.chord_tones}
    weak = [ev.note % 12 for bar in run(ScaleRules(dissonance_weight=1.0, leap_recovery=False), 1) for ev in bar if ev.row % 4]
    assert weak and any(n not in tones for n in weak)


def test_leap_recovery_reverses_direction():
    rules = ScaleRules(leap_probability=1.0, leap_recovery=True)
    checked = 0
    for seed in range(20):
        for bar in run(rules, seed, bars=20):
            for a, b, c in zip(bar, bar[1:], bar[2:]):
                if abs(b.note - a.note) >= 5 and c.row % 4 != 0:
                    d1, d2 = b.note - a.note, c.note - b.note
                    inner = REG[0] < b.note < REG[1]
                    if inner and d2 != 0:
                        assert d1 * d2 < 0
                        checked += 1
    assert checked > 10


def test_leap_semitones_and_max_leap_filters():
    tones = list(CHORD.chord_tones)
    gen = MelodyGenerator(ScaleRules(leap_semitones=(4, 5, 7), max_leap=7), REG, SCALE, random.Random(1))
    found = 0
    for prev in range(REG[0], REG[1] + 1):
        for _ in range(5):
            n = gen._leap(tones, prev)
            if n is not None:
                assert abs(n - prev) in (4, 5, 7) and n in tones
                found += 1
    assert found > 0
    tight = MelodyGenerator(ScaleRules(max_leap=4), REG, SCALE, random.Random(1))
    for prev in range(REG[0], REG[1] + 1):
        n = tight._leap(tones, prev)
        assert n is None or 3 <= abs(n - prev) <= 4
    assert tight._leap([30], 30) is None                    # 候補なし → None（呼び出し側は順次進行に退避）


def test_leap_branch_falls_back_to_step_when_no_candidate():
    from mod_weaver.core.model import ChordDef
    one = ChordDef("x", 0, 24, (30,), (28, 30, 31), None, True)
    gen = MelodyGenerator(ScaleRules(leap_probability=1.0), REG, SCALE, random.Random(4))
    ev, _ = gen.bar(RhythmMotif((0, 2, 3)), one, None)
    assert [e.note for e in ev][0] == 30 and all(e.note in (28, 30, 31) for e in ev)


def test_same_seed_same_melody_and_different_seed_differs():
    r = ScaleRules(dissonance_weight=0.3)
    assert run(r, 7) == run(r, 7)
    assert run(r, 7) != run(r, 8)


def test_cadence_resolves_to_target_or_first_chord_tone():
    gen = MelodyGenerator(ScaleRules(), REG, SCALE, random.Random(1))
    ev, last = gen.bar(RhythmMotif((0, 4, 8, 12)), CHORD, None, cadence=True)
    assert ev[-1].note == CHORD.chord_tones[0] and last == ev[-1].note
    ev, _ = gen.bar(RhythmMotif((0, 4, 8, 12)), CHORD, None, cadence=True, cadence_target=31)
    assert ev[-1].note == 31
    ev, _ = gen.bar(RhythmMotif((0, 4)), CHORD, None, cadence=True, cadence_target=31 - 24, octave_shift=2)
    assert REG[0] <= ev[-1].note <= REG[1]


def test_note_event_durations_come_from_motif():
    gen = MelodyGenerator(ScaleRules(), REG, SCALE, random.Random(1))
    ev, _ = gen.bar(RhythmMotif((0, 6)), CHORD, None)
    assert [(e.row, e.dur) for e in ev] == [(0, 6), (6, 10)]
    ev, _ = gen.bar(RhythmMotif((0, 4), (3, 3)), CHORD, None, rows=8)
    assert [e.dur for e in ev] == [3, 3]
    ev, _ = gen.bar(RhythmMotif((0, 4)), CHORD, None, rows=8)
    assert [e.dur for e in ev] == [4, 4]


def test_volumes_strong_is_base_weak_is_lower():
    gen = MelodyGenerator(ScaleRules(), REG, SCALE, random.Random(9), base_vol=50)
    ev, _ = gen.bar(RhythmMotif((0, 3, 4, 7)), CHORD, None)
    assert ev[0].vol == 50 and ev[2].vol == 50
    assert all(38 <= e.vol <= 46 for e in (ev[1], ev[3]))
    ev, _ = gen.bar(RhythmMotif((0, 3)), CHORD, None, base_vol=30)
    assert ev[0].vol == 30 and 18 <= ev[1].vol <= 26


def test_octave_shift_moves_melody_up():
    lo = [e.note for b in run(ScaleRules(), 2, bars=10, octave_shift=0) for e in b]
    hi = [e.note for b in run(ScaleRules(), 2, bars=10, octave_shift=1) for e in b]
    assert sum(hi) / len(hi) >= sum(lo) / len(lo)


def test_single_tone_pool_edge_cases():
    """コードトーンが 1 音でも例外にならない（強拍の次点なし）。"""
    from mod_weaver.core.model import ChordDef
    one = ChordDef("x", 0, 24, (30,), (30,), None, True)
    gen = MelodyGenerator(ScaleRules(dissonance_weight=1.0, leap_probability=1.0), REG, SCALE, random.Random(1))
    ev, _ = gen.bar(MOTIFS[1], one, 30)
    assert all(REG[0] <= e.note <= REG[1] for e in ev)


# ---------------- ramp ----------------

def test_ramp_endpoints_and_monotonic():
    assert ramp(10, 60, 0, 6) == 10 and ramp(10, 60, 5, 6) == 60
    vals = [ramp(10, 60, i, 11) for i in range(11)]
    assert vals == sorted(vals) and vals[5] == 35
    assert ramp(60, 10, 3, 6) < ramp(60, 10, 0, 6)
    assert ramp(7, 50, 0, 1) == 7 and ramp(7, 50, 0, 0) == 7
