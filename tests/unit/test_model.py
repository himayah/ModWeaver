from __future__ import annotations

import itertools
import random

import pytest

from mod_weaver.core import pitch
from mod_weaver.core.model import (
    Cell, ChannelRole, Instrument, MeasureBuffer, Pattern, SampleSpec, RngStreams, EMPTY_CELL,
)
from mod_weaver.errors import (
    CellConflictError, ChannelConflictError, PitchRangeError, SampleConstraintError,
)
from tests.conftest import load_reference


# ---------------- Cell ----------------

def _legacy(ref, note, sample, effect, param, vol):
    name = "---" if note is None else pitch.NOTE_NAMES[note]
    if vol is not None:
        return ref.cell(name, sample, vol=vol)
    return ref.make_cell(name, sample, effect, param)


def test_cell_serialize_matches_legacy_boundary_product():
    ref = load_reference()
    notes = [None, 0, 1, 12, 24, 35]
    samples = [0, 1, 7, 15, 16, 31]
    effects = [0, 0xC, 0xF, 0x3]
    params = [0, 1, 0x36, 0x7F, 0xFF]
    for note, smp, eff, prm in itertools.product(notes, samples, effects, params):
        assert Cell(note, smp, eff, prm).serialize() == _legacy(ref, note, smp, eff, prm, None)
    for note, smp, vol in itertools.product(notes, samples, [0, 1, 32, 63, 64]):
        assert Cell(note, smp, vol=vol).serialize() == _legacy(ref, note, smp, 0, 0, vol)


def test_cell_serialize_matches_legacy_random():
    ref = load_reference()
    r = random.Random(7)
    for _ in range(10000):
        note = r.choice([None] + list(range(36)))
        smp = r.randint(0, 31)
        if r.random() < 0.5:
            vol = r.randint(0, 64)
            c = Cell(note, smp, vol=vol)
            assert c.serialize() == _legacy(ref, note, smp, 0, 0, vol)
        else:
            eff, prm = r.randint(0, 15), r.randint(0, 255)
            assert Cell(note, smp, eff, prm).serialize() == _legacy(ref, note, smp, eff, prm, None)


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

def _plan():
    return (
        ChannelRole("drums", frozenset({1, 2, 3}), {3: 3, 2: 2, 1: 1}),
        ChannelRole("bass", frozenset({4})),
        ChannelRole("pad", frozenset({5, 6}), {5: 1, 6: 2}),
        ChannelRole("lead", frozenset({7})),
    )


def test_strict_priority_rules():
    buf = MeasureBuffer(8, _plan(), strict=True)
    bd, sd, crash = Cell(24, 1), Cell(24, 2), Cell(35, 3)
    buf.put(0, 0, bd)
    buf.put(0, 0, sd)            # 新 > 既存 → 置換
    assert buf.get(0, 0) == sd
    buf.put(0, 0, bd)            # 新 < 既存 → 書かない
    assert buf.get(0, 0) == sd
    buf.put(0, 0, sd)            # 同一セル → no-op
    assert buf.get(0, 0) == sd
    with pytest.raises(ChannelConflictError):
        buf.put(0, 0, Cell(20, 2))   # 同値で異なるセル
    buf.put(0, 0, crash)
    assert buf.get(0, 0) == crash


def test_strict_off_never_overwrites_note_but_note_replaces_off():
    buf = MeasureBuffer(4, _plan(), strict=True)
    off = Cell(None, 0, vol=0)
    buf.put(1, 1, Cell(10, 4))
    buf.put(1, 1, off)
    assert buf.get(1, 1) == Cell(10, 4)
    buf.put(2, 1, off)
    buf.put(2, 1, Cell(10, 4))
    assert buf.get(2, 1) == Cell(10, 4)


def test_strict_empty_put_is_noop():
    buf = MeasureBuffer(4, _plan(), strict=True)
    buf.put(0, 1, Cell(10, 4))
    buf.put(0, 1, EMPTY_CELL)
    assert buf.get(0, 1) == Cell(10, 4)


def test_replace_always_overwrites():
    buf = MeasureBuffer(4, _plan(), strict=True)
    buf.put(0, 0, Cell(35, 3))
    buf.replace(0, 0, Cell(24, 1))
    assert buf.get(0, 0) == Cell(24, 1)


def test_non_strict_overwrites_unconditionally():
    buf = MeasureBuffer(4, _plan(), strict=False)
    buf.put(0, 0, Cell(35, 3))
    buf.put(0, 0, Cell(24, 1))
    assert buf.get(0, 0) == Cell(24, 1)


def test_disallowed_sample_and_bad_position():
    buf = MeasureBuffer(4, _plan(), strict=False)
    with pytest.raises(ChannelConflictError):
        buf.put(0, 1, Cell(10, 1))          # ch2 に drums サンプル
    buf.put(0, 1, Cell(None, 0, vol=10))     # sample 0 は常に可
    with pytest.raises(ChannelConflictError):
        buf.put(4, 0, Cell())
    with pytest.raises(ChannelConflictError):
        buf.get(0, 4)


def test_pattern_blit_and_serialize():
    plan = _plan()
    buf = MeasureBuffer(16, plan, strict=True)
    buf.put(3, 3, Cell(20, 7))
    pat = Pattern(plan, strict=True)
    pat.blit(buf, 16)
    assert pat.get(19, 3) == Cell(20, 7)
    data = pat.serialize()
    assert len(data) == 1024
    assert data[(19 * 4 + 3) * 4:(19 * 4 + 3) * 4 + 4] == Cell(20, 7).serialize()
    with pytest.raises(ChannelConflictError):
        pat.blit(buf, 56)                   # はみ出し
    with pytest.raises(ChannelConflictError):
        pat.blit(MeasureBuffer(16, None, channels=8), 0)   # チャンネル数不一致


def test_grid_is_generic_in_rows_and_channels():
    g = Pattern(None, rows=32, channels=8)
    assert g.channels == 8 and len(g.serialize()) == 32 * 8 * 4
    with pytest.raises(ValueError):
        MeasureBuffer(0)


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


def test_instrument_pitched_shift_and_range():
    inst = Instrument(4, _spec(shift=-24))
    assert inst.cell(0) == Cell(24, 4)                 # logical 0 → t=24
    assert inst.cell(11, vol=50) == Cell(35, 4, vol=50)
    with pytest.raises(PitchRangeError):
        inst.cell(12)                                   # t=36
    with pytest.raises(PitchRangeError):
        inst.cell(-25)                                  # t=-1
    hi = Instrument(7, _spec(shift=12))
    assert hi.cell(12) == Cell(0, 7)
    with pytest.raises(PitchRangeError):
        hi.cell(11)


def test_instrument_arpeggio_range():
    inst = Instrument(6, _spec())
    assert inst.cell(28, param=0x47) == Cell(28, 6, 0, 0x47)     # 28+7=35
    with pytest.raises(PitchRangeError):
        inst.cell(29, param=0x47)
    assert inst.cell(29, effect=0x4, param=0x47).effect == 4      # arp でなければ検査しない
    with pytest.raises(CellConflictError):
        inst.cell(20, vol=30, param=0x37)


def test_instrument_unpitched_ignores_n():
    inst = Instrument(1, _spec(pitched=False, rate_note=35))
    assert inst.cell() == Cell(35, 1)
    assert inst.cell(3, vol=50) == Cell(35, 1, vol=50)


def test_instrument_no_note_cells():
    inst = Instrument(7, _spec())
    assert inst.cell() == Cell(None, 0) and inst.cell().is_empty            # 休符
    assert inst.cell(vol=20) == Cell(None, 0, vol=20)                        # 音量専用は sample=0
    assert inst.cell(effect=3, param=8, keep_sample=True) == Cell(None, 7, 3, 8)
    assert inst.off() == Cell(None, 0, vol=0)


def test_rng_streams_deterministic_and_independent():
    a, b = RngStreams.for_seed(5, "march"), RngStreams.for_seed(5, "march")
    assert [a.melody.random() for _ in range(3)] == [b.melody.random() for _ in range(3)]
    c = RngStreams.for_seed(5, "march")
    for _ in range(10):
        c.drums.random()   # drums を消費しても melody は変わらない
    e = RngStreams.for_seed(5, "march")
    assert c.melody.random() == e.melody.random()
    d = RngStreams.for_seed(5, "suspense-slow")
    assert RngStreams.for_seed(5, "march").plan.random() != d.plan.random()
