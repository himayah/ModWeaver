from __future__ import annotations

import pytest

from mod_weaver.core import pitch
from mod_weaver.errors import PitchRangeError
from tests.conftest import load_reference


def test_periods_match_standard_table():
    ref = load_reference()
    assert len(pitch.PERIODS) == 36 == len(pitch.NOTE_NAMES)
    for nm, period in ref.PERIODS.items():
        assert pitch.PERIODS[pitch.parse(nm)] == period


def test_name_parse_roundtrip():
    for t in range(36):
        assert pitch.parse(pitch.name(t)) == t
    assert pitch.name(0) == "C-1" and pitch.name(35) == "B-3" and pitch.parse("C#2") == 13


@pytest.mark.parametrize("bad", ["", "H-1", "C-4", "c-1", "C#0"])
def test_parse_invalid(bad):
    with pytest.raises(PitchRangeError):
        pitch.parse(bad)


@pytest.mark.parametrize("t", [-1, 36])
def test_name_out_of_range(t):
    with pytest.raises(PitchRangeError):
        pitch.name(t)


def test_period_to_index():
    assert pitch.period_to_index(214) == 24
    with pytest.raises(PitchRangeError):
        pitch.period_to_index(215)


def test_hz():
    assert pitch.hz(0) == pytest.approx(65.4064)
    assert pitch.hz(12) == pytest.approx(130.8128)
    assert pitch.hz(24) == pytest.approx(261.6256, rel=1e-6)


@pytest.mark.parametrize("lo,hi", [(0, 11), (17, 28), (24, 43), (3, 20)])
def test_fold_into_range_invariants(lo, hi):
    for n in range(-30, 80):
        f = pitch.fold_into_range(n, lo, hi)
        assert lo <= f <= hi
        assert (f - n) % 12 == 0
        if lo <= n <= hi:
            assert f == n


def test_fold_narrow_range():
    with pytest.raises(PitchRangeError):
        pitch.fold_into_range(5, 0, 10)


def test_nearest():
    assert pitch.nearest([1, 5, 9], 6) == 5
    assert pitch.nearest([1, 5, 9], 7) == 5  # 同距離は先頭側
    with pytest.raises(PitchRangeError):
        pitch.nearest([], 3)


def test_lowest_note_with_pc():
    for lo, hi in [(0, 11), (17, 28), (24, 35)]:
        for pc in range(12):
            n = pitch.lowest_note_with_pc(pc, lo, hi)
            assert lo <= n <= hi and n % 12 == pc and n - 12 < lo
    with pytest.raises(PitchRangeError):
        pitch.lowest_note_with_pc(0, 0, 5)


def test_notes_with_pcs():
    assert pitch.notes_with_pcs({0, 4, 7}, 0, 11) == [0, 4, 7]
    assert pitch.notes_with_pcs([0], 0, 24) == [0, 12, 24]


def test_scale_notes_in():
    s = pitch.Scale(7, pitch.MODES["ionian"])  # G major
    notes = s.notes_in(0, 11)
    assert {n % 12 for n in notes} == {7, 9, 11, 0, 2, 4, 6}
    assert notes == sorted(notes)


def test_chord_qualities_and_modes():
    assert pitch.CHORD_QUALITIES["dim"] == (0, 3, 6)
    assert len(pitch.MODES["dim_wh"]) == 8
