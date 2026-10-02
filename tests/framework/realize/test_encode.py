"""``encode.Codec``（形式ごとの奏法・音高・コマンドの表。FRAMEWORK_REDESIGN.md §9.6）と、
その表を使うセル化の規則（優先順位・MOD の音量とエフェクトの排他・止め方）。"""
from __future__ import annotations

import pytest

from mod_weaver.core.model import SampleSpec
from mod_weaver.core.native import NOTE_CUT, NOTE_OFF, RCell, RGrid
from mod_weaver.errors import PitchRangeError, PlanError
from mod_weaver.framework.realize.encode import Codec

FORMATS = ("mod", "s3m", "xm", "it")


def _spec(**kw) -> SampleSpec:
    base = dict(name="x", data=bytes(4), volume=40, rate_note=24, shift=0, pitched=True, rate_hz=44100.0)
    base.update(kw)
    return SampleSpec(**base)


# ---- 音高 ----

def test_mod_note_is_tracker_note_minus_shift():
    c = Codec("mod")
    assert c.note(_spec(shift=12), 30) == 18
    with pytest.raises(PitchRangeError):
        c.note(_spec(), 40)


@pytest.mark.parametrize("fmt", ("s3m", "xm", "it"))
def test_extended_formats_use_reference_note_at_rate_note(fmt):
    c = Codec(fmt)
    spec = _spec(rate_note=24, shift=3)
    assert c.note(spec, 24 + 3) == c.n_ref           # t == rate_note → 基準ノート（rate_hz で鳴る）
    assert c.note(spec, 24 + 3 + 12) == c.n_ref + 12
    assert c.note(_spec(pitched=False), None) == c.n_ref


@pytest.mark.parametrize("fmt, ref", [("s3m", 48), ("xm", 48), ("it", 60)])
def test_reference_notes(fmt, ref):
    assert Codec(fmt).n_ref == ref


@pytest.mark.parametrize("fmt", ("s3m", "xm", "it"))
def test_extended_formats_check_their_own_range(fmt):
    c = Codec(fmt)
    lo, hi = c.note_range
    with pytest.raises(PitchRangeError):
        c.note(_spec(rate_note=0), hi + 100)
    assert c.note(_spec(rate_note=0), hi - c.n_ref) == hi


# ---- コマンドの表（§9.6）----

@pytest.mark.parametrize("fmt, expected", [
    ("mod", ("4", 0x35)), ("s3m", ("H", 0x35)), ("xm", ("4", 0x35)), ("it", ("H", 0x35))])
def test_vibrato(fmt, expected):
    assert Codec(fmt).vibrato(0x35) == expected


@pytest.mark.parametrize("fmt, expected", [
    ("mod", ("7", 0x24)), ("s3m", ("R", 0x28)), ("xm", ("7", 0x24)), ("it", ("R", 0x28))])
def test_tremolo(fmt, expected):
    """S3M・IT は深さが半分で再生される（実測。tests/realplayer/test_f4_effects.py）ので深さのニブルを 2 倍にする。"""
    assert Codec(fmt).tremolo(0x24) == expected


def test_tremolo_depth_saturates_at_15_for_s3m_and_it():
    assert Codec("it").tremolo(0x4C) == ("R", 0x4F)


@pytest.mark.parametrize("fmt, delay, retrig, cut", [
    ("mod", ("E", 0xD3), ("E", 0x93), ("E", 0xC3)),
    ("xm", ("E", 0xD3), ("E", 0x93), ("E", 0xC3)),
    ("s3m", ("S", 0xD3), ("Q", 0x03), ("S", 0xC3)),
    ("it", ("S", 0xD3), ("Q", 0x03), ("S", 0xC3))])
def test_extended_subcommands(fmt, delay, retrig, cut):
    c = Codec(fmt)
    assert (c.delay(3), c.retrig(3), c.cut(3)) == (delay, retrig, cut)


@pytest.mark.parametrize("fmt, speed, tempo, brk", [
    ("mod", ("F", 6), ("F", 125), ("D", 0)), ("xm", ("F", 6), ("F", 125), ("D", 0)),
    ("s3m", ("A", 6), ("T", 125), ("C", 0)), ("it", ("A", 6), ("T", 125), ("C", 0))])
def test_speed_tempo_break(fmt, speed, tempo, brk):
    c = Codec(fmt)
    assert (c.speed(6), c.tempo(125), c.pattern_break()) == (speed, tempo, brk)


def test_pan_and_cutoff_only_where_expressible():
    assert Codec("mod").pan(100) is None
    assert Codec("s3m").pan(0xA0) == ("S", 0x8A)
    assert Codec("xm").pan(0xA0) == ("8", 0xA0)
    assert Codec("it").pan(0xA0) == ("X", 0xA0)
    assert [Codec(f).cutoff(64) for f in FORMATS] == [None, None, None, ("Z", 64)]


def test_offset_is_clamped_to_one_byte():
    assert Codec("it").offset(9999) == ("O", 255)


def test_cut_ticks_validated():
    with pytest.raises(PlanError):
        Codec("mod").cut(0)


# ---- 止め方（§9.7）----

def test_stop_cell_per_format():
    assert Codec("mod").stop_cell() == RCell(vol=0)          # Cxx 00
    assert Codec("xm").stop_cell() == RCell(vol=0)           # ボリューム列 0
    assert Codec("s3m").stop_cell() == RCell(note=NOTE_CUT)  # ^^^
    assert Codec("it").stop_cell() == RCell(note=NOTE_CUT)


def test_release_uses_key_off_only_where_envelopes_exist():
    assert Codec("xm").stop_cell(0.3) == RCell(note=NOTE_OFF)
    assert Codec("it").stop_cell(0.3) == RCell(note=NOTE_OFF)
    assert Codec("mod").stop_cell(0.3) == RCell(vol=0)       # MOD・S3M のスライドは tracker 側（_put_stop）
    assert Codec("s3m").stop_cell(0.3) == RCell(note=NOTE_CUT)


# ---- RGrid ----

def test_mod_grid_refuses_vol_and_fx_in_one_cell():
    g = RGrid(4, 2, exclusive=True)
    with pytest.raises(Exception):
        g.put(0, 0, RCell(note=1, sample=1, vol=10, fx=("4", 1)))
    RGrid(4, 2).put(0, 0, RCell(note=1, sample=1, vol=10, fx=("4", 1)))   # 他形式は同居できる


def test_try_insert_command_prefers_control_lane_then_empty_then_bare_note():
    g = RGrid(2, 3)
    g.put(0, 0, RCell(note=5, sample=1, vol=30))
    g.put(0, 1, RCell(note=5, sample=1, fx=("4", 1)))
    assert g.try_insert_command(0, ("F", 6), prefer=2)
    assert g.get(0, 2).fx == ("F", 6)
    assert g.try_insert_command(0, ("F", 125), prefer=2)        # 制御チャンネルは埋まった → 発音のセルに相乗り
    assert g.get(0, 0).fx == ("F", 125) and g.get(0, 0).note == 5 and g.get(0, 0).vol == 30   # 他形式は音量があっても可
    assert not g.try_insert_command(0, ("F", 1), prefer=2)       # もう場所が無い


def test_try_insert_command_in_mod_cannot_share_a_cell_with_volume():
    g = RGrid(1, 1, exclusive=True)
    g.put(0, 0, RCell(note=5, sample=1, vol=30))
    assert not g.try_insert_command(0, ("F", 6))
