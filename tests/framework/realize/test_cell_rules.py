"""セル化の規則（DESIGN.md §7.6〜§7.6）を ``tracker._write_note`` / ``_put_stop`` に直接当てて確かめる。"""
from __future__ import annotations

import types

import pytest

from mod_weaver.core.model import SampleSpec
from mod_weaver.core.native import NOTE_CUT, NOTE_OFF, RCell, RGrid
from mod_weaver.framework.realize import tracker
from mod_weaver.framework.realize.encode import Codec
from mod_weaver.framework.realize.lanes import Placement
from mod_weaver.framework.score import Arpeggio, Delay, Offset, Tremolo, Vibrato

SPEC = SampleSpec(name="x", data=bytes(512), volume=40, rate_note=24, rate_hz=44100.0)
LOOPED = SampleSpec(name="y", data=bytes(512), volume=40, loop=(0, 100), rate_note=24, rate_hz=44100.0)


def _ctx(fmt, release=(None,), bpm=125, specs=(SPEC,)):
    codec = Codec(fmt)
    return types.SimpleNamespace(codec=codec, bpm=bpm, release=release, specs=list(specs))


def _grid(fmt, rows=16):
    return RGrid(rows, 1, exclusive=Codec(fmt).exclusive_vol_fx)


def _note(fmt, p, rows=16, next_step=None, spec=SPEC, release=(None,)):
    ctx = _ctx(fmt, release=release, specs=(spec,))
    g = _grid(fmt, rows)
    tracker._write_note(ctx, g, 0, p.step, next_step, p, 1, spec, step_ticks=6)
    return g


def _p(**kw):
    base = dict(step=0, lane=0, kind="note", inst="x", pitch=24, vel=50, arts=())
    base.update(kw)
    return Placement(**base)


@pytest.mark.parametrize("fmt", ("s3m", "xm", "it"))
def test_extended_formats_keep_volume_and_effect_together(fmt):
    g = _note(fmt, _p(arts=(Delay(2),)))
    c = g.get(0, 0)
    assert c.vol == 50 and c.fx == Codec(fmt).delay(2)


def test_mod_drops_volume_for_a_trigger_effect():
    c = _note("mod", _p(arts=(Delay(2),))).get(0, 0)
    assert c.fx == ("E", 0xD2) and c.vol is None            # DESIGN.md §7.6 の2: エフェクトを残して音量を落とす


def test_mod_omits_volume_equal_to_sample_default():
    c = _note("mod", _p(vel=40, arts=(Offset(0.5),))).get(0, 0)
    assert c.vol is None and c.fx[0] == "9"


def test_mod_keeps_volume_and_moves_vibrato_to_next_row():
    g = _note("mod", _p(vel=50, arts=(Vibrato(0x44, at=0, steps=3),)))
    assert g.get(0, 0).vol == 50 and g.get(0, 0).fx is None
    assert g.get(1, 0).fx == ("4", 0x44)                    # 次の row へ
    assert g.get(2, 0).fx == ("4", 0)                       # 継続は「メモリ継続」の 0


@pytest.mark.parametrize("fmt", ("s3m", "xm", "it"))
def test_extended_formats_keep_vibrato_on_the_trigger_row(fmt):
    g = _note(fmt, _p(vel=50, arts=(Vibrato(0x44, at=0, steps=3),)))
    c = Codec(fmt)
    assert g.get(0, 0).vol == 50 and g.get(0, 0).fx == c.vibrato(0x44)
    assert g.get(1, 0).fx == c.vibrato(0) and g.get(2, 0).fx == c.vibrato(0)


def test_effect_priority_delay_beats_offset_and_vibrato():
    g = _note("it", _p(arts=(Vibrato(0x44), Offset(0.1), Delay(2))))
    assert g.get(0, 0).fx == ("S", 0xD2)
    assert g.get(1, 0).fx == ("H", 0x44)                    # 負けたビブラートは次の row へ移る


def test_tremolo_is_used_by_extended_formats():
    assert _note("xm", _p(arts=(Tremolo(0x34, at=1, steps=2),))).get(1, 0).fx == ("7", 0x34)
    assert _note("s3m", _p(arts=(Tremolo(0x34, at=1, steps=2),))).get(1, 0).fx == ("R", 0x38)   # 深さを 2 倍


def test_arpeggio_runs_for_its_steps_and_stops_at_next_note():
    g = _note("it", _p(arts=(Arpeggio(3, 7, steps=4),)), next_step=3)
    assert [g.get(r, 0).fx for r in range(4)] == [("J", 0x37)] * 3 + [None]


def test_arpeggio_above_the_note_range_is_an_error():
    from mod_weaver.errors import PitchRangeError

    with pytest.raises(PitchRangeError):
        _note("mod", _p(pitch=24 + 11, arts=(Arpeggio(0, 7),)))   # t=35 + 7 > 35


def test_strum_becomes_a_delay_proportional_to_tick_length():
    # 125 BPM → 1 tick = 20 ms。60 ms → 3 tick
    c = _note("it", _p(strum_ms=60.0)).get(0, 0)
    assert c.fx == ("S", 0xD3)
    assert _note("it", _p(strum_ms=1000.0)).get(0, 0).fx == ("S", 0xD5)   # row 内（step の tick 数 − 1）に頭打ち
    assert _note("it", _p(strum_ms=0.0)).get(0, 0).fx is None


def test_baked_chord_is_not_strummed_by_delay():
    assert _note("it", _p(strum_ms=60.0, chord=(0, 4, 7))).get(0, 0).fx is None


@pytest.mark.parametrize("fmt, stop", [("mod", RCell(vol=0)), ("xm", RCell(vol=0)),
                                         ("s3m", RCell(note=NOTE_CUT)), ("it", RCell(note=NOTE_CUT))])
def test_duration_ends_with_the_formats_stop_cell(fmt, stop):
    assert _note(fmt, _p(dur=4)).get(4, 0) == stop


def test_no_stop_when_next_note_comes_first():
    assert _note("it", _p(dur=4), next_step=4).get(4, 0).is_empty


@pytest.mark.parametrize("fmt", ("xm", "it"))
def test_release_uses_key_off_in_envelope_formats(fmt):
    assert _note(fmt, _p(dur=4), release=(0.3,)).get(4, 0) == RCell(note=NOTE_OFF)


@pytest.mark.parametrize("fmt, slide", [("mod", "A"), ("s3m", "D")])
def test_release_is_a_volume_slide_in_mod_and_s3m(fmt, slide):
    g = _note(fmt, _p(dur=4, vel=40), rows=16, release=(0.3,))
    # 125 BPM・6 tick/row → 1 row = 120 ms → 0.3 秒 = 3 row
    assert [g.get(r, 0).fx[0] if g.get(r, 0).fx else None for r in range(4, 7)] == [slide] * 3
    param = g.get(4, 0).fx[1]
    assert 0 < param <= 15                                   # 下げる量は下位ニブル
    assert g.get(7, 0) == Codec(fmt).stop_cell()             # 終わりで確実に止める


def test_release_slide_does_not_run_past_next_note():
    g = _note("mod", _p(dur=2, vel=40), next_step=4, release=(1.0,))
    assert g.get(2, 0).fx and g.get(3, 0).fx and g.get(4, 0).is_empty
