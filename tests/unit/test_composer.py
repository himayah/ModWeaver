from __future__ import annotations

import random

import pytest

from mod_weaver.core.composer import (
    MelodyGenerator, NoteEvent, RhythmMotif, ScaleRules, articulate, fade_cells, ramp,
)
from mod_weaver.core.harmony import Registers, voice
from mod_weaver.core.model import Cell, ChannelRole, ChordSpec, Instrument, MeasureBuffer, SampleSpec
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


# ---------------- ramp / fade_cells ----------------

def test_ramp_endpoints_and_monotonic():
    assert ramp(10, 60, 0, 6) == 10 and ramp(10, 60, 5, 6) == 60
    vals = [ramp(10, 60, i, 11) for i in range(11)]
    assert vals == sorted(vals) and vals[5] == 35
    assert ramp(60, 10, 3, 6) < ramp(60, 10, 0, 6)
    assert ramp(7, 50, 0, 1) == 7 and ramp(7, 50, 0, 0) == 7


PLAN = (ChannelRole("a", frozenset({1})), ChannelRole("b", frozenset({2})),
        ChannelRole("c", frozenset({3})), ChannelRole("d", frozenset({4})))


def test_fade_cells_rewrites_only_vol_cells():
    buf = MeasureBuffer(8, PLAN, strict=False)
    for r in range(8):
        buf.put(r, 0, Cell(24, 1, vol=40))
    buf.put(3, 0, Cell(24, 1, 0, 0x47))          # vol を持たないセルは対象外
    buf.put(5, 0, Cell())                        # 空
    fade_cells(buf, 0, 0, 7, 60, 10)
    vols = [buf.get(r, 0).vol for r in range(8)]
    assert vols[0] == 60 and vols[7] == 10 and vols[3] is None and vols[5] is None
    assert buf.get(3, 0) == Cell(24, 1, 0, 0x47) and buf.get(5, 0).is_empty
    assert buf.get(0, 0).note == 24 and buf.get(0, 0).sample == 1


# ---------------- articulate ----------------

def inst(pitched=True):
    return Instrument(4, SampleSpec("L", bytes(64), 40, loop=(0, 30), shift=0, pitched=pitched))


def test_articulate_places_off_only_for_rests_at_gate_1():
    events = [NoteEvent(0, 30, 50, 3), NoteEvent(4, 32, 40, 4), NoteEvent(8, 31, 40, 8)]
    buf = MeasureBuffer(16, PLAN, strict=True)
    articulate(buf, 3, events, inst())
    assert buf.get(3, 3) == Cell(None, 0, vol=0)                 # 0+3 < 4: 休符 → OFF
    assert buf.get(4, 3) == Cell(30 + 2, 4, vol=40)
    assert buf.get(8, 3).note == 31
    assert buf.get(8, 3) != inst().off() and buf.get(12, 3).is_empty     # 最終音は measure 末まで → OFF なし
    assert sum(1 for r in range(16) if buf.get(r, 3) == inst().off()) == 1


def test_articulate_gate_creates_staccato_off():
    events = [NoteEvent(0, 30, 50, 4), NoteEvent(4, 31, 50, 4), NoteEvent(8, 32, 50, 8)]
    buf = MeasureBuffer(16, PLAN, strict=True)
    articulate(buf, 3, events, inst(), gate=0.5)
    assert buf.get(2, 3) == Cell(None, 0, vol=0) and buf.get(6, 3) == Cell(None, 0, vol=0)
    assert buf.get(12, 3) == Cell(None, 0, vol=0)                # 8*0.5=4 → row 12 < 16
    buf2 = MeasureBuffer(16, PLAN, strict=True)
    articulate(buf2, 3, events, inst(), gate=0.9)                # round(4*0.9)=4 → 次の発音と同位置 → 置かない
    assert buf2.get(4, 3).sample == 4 and not any(buf2.get(r, 3) == inst().off() for r in (3, 4, 5, 6, 7))
    assert buf2.get(8 + 7, 3) == Cell(None, 0, vol=0)            # 8*0.9=7.2→7 → row 15


def test_articulate_min_gate_is_one_row():
    buf = MeasureBuffer(16, PLAN, strict=True)
    articulate(buf, 3, [NoteEvent(0, 30, 50, 1), NoteEvent(4, 31, 50, 4)], inst(), gate=0.1)
    assert buf.get(1, 3) == Cell(None, 0, vol=0)
