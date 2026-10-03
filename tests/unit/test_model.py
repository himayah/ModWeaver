from __future__ import annotations

import itertools
import random

import pytest

from mod_weaver.core import pitch
from mod_weaver.core.model import (
    Cell, Pattern, SampleSpec, EMPTY_CELL,
)
from mod_weaver.errors import (
    CellConflictError, ChannelConflictError, PitchRangeError, SampleConstraintError,
)


# ---------------- Cell ----------------

def _mod_cell(note, sample, effect, param, vol):
    """ProTracker の 4 バイトのセル（MOD の仕様どおり）。音量は ``Cxx``。"""
    if vol is not None:
        effect, param = 0xC, vol
    period = 0 if note is None else pitch.PERIODS[note]
    return bytes([(sample & 0xF0) | (period >> 8), period & 0xFF, ((sample & 0x0F) << 4) | effect, param])


def test_cell_serialize_matches_the_mod_spec_boundary_product():
    notes = [None, 0, 1, 12, 24, 35]
    samples = [0, 1, 7, 15, 16, 31]
    effects = [0, 0xC, 0xF, 0x3]
    params = [0, 1, 0x36, 0x7F, 0xFF]
    for note, smp, eff, prm in itertools.product(notes, samples, effects, params):
        assert Cell(note, smp, eff, prm).serialize() == _mod_cell(note, smp, eff, prm, None)
    for note, smp, vol in itertools.product(notes, samples, [0, 1, 32, 63, 64]):
        assert Cell(note, smp, vol=vol).serialize() == _mod_cell(note, smp, 0, 0, vol)


def test_cell_serialize_matches_the_mod_spec_random():
    r = random.Random(7)
    for _ in range(10000):
        note = r.choice([None] + list(range(36)))
        smp = r.randint(0, 31)
        if r.random() < 0.5:
            vol = r.randint(0, 64)
            assert Cell(note, smp, vol=vol).serialize() == _mod_cell(note, smp, 0, 0, vol)
        else:
            eff, prm = r.randint(0, 15), r.randint(0, 255)
            assert Cell(note, smp, eff, prm).serialize() == _mod_cell(note, smp, eff, prm, None)


def test_cell_vol_and_effect_conflict():
    with pytest.raises(CellConflictError):
        Cell(0, 1, effect=0xF, param=90, vol=10)
    with pytest.raises(CellConflictError):
        Cell(0, 1, param=0x47, vol=10)   # アルペジオも排他


@pytest.mark.parametrize("kw,exc", [
    (dict(note=36), PitchRangeError), (dict(note=-1), PitchRangeError),
    (dict(sample=32), CellConflictError), (dict(effect=16), CellConflictError),
    (dict(param=256), CellConflictError), (dict(vol=65), CellConflictError),
    (dict(vol=-1), CellConflictError),
])
def test_cell_range_errors(kw, exc):
    with pytest.raises(exc):
        Cell(**kw)


def test_cell_has_effect_and_is_empty():
    assert not Cell().has_effect and Cell().is_empty
    assert Cell(param=0x47).has_effect and not Cell(param=0x47).is_empty   # アルペジオも効果
    assert Cell(effect=0xF, param=0x5A).has_effect
    assert not Cell(None, 0, vol=0).is_empty                              # OFF は空でない
    assert not Cell(None, 3).is_empty


# ---------------- MeasureBuffer / Pattern ----------------


# ---------------- CellGrid.insert_command (DESIGN.md §3.2) ----------------


# ---------------- SampleSpec / Instrument ----------------

def _spec(**kw):
    base = dict(name="Test", data=bytes(64), volume=40)
    base.update(kw)
    return SampleSpec(**base)


def test_sample_validate_ok_and_errors():
    _spec().validate()
    _spec(loop=(2, 10)).validate()
    for bad in [
        dict(name="x" * 23), dict(name="日本語"), dict(data=b""), dict(data=b"abc"),
        dict(data=bytes(131072)), dict(volume=65), dict(rate_note=36), dict(finetune=8),
        dict(loop=(0, 1)), dict(loop=(30, 3)), dict(loop=(-1, 4)),
    ]:
        with pytest.raises(SampleConstraintError):
            _spec(**bad).validate()
    assert _spec().loop_header == (0, 1) and _spec(loop=(3, 9)).loop_header == (3, 9)
    assert _spec().length_words == 32


