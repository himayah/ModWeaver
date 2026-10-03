"""``Glide`` の Realizer 側の規則（DESIGN.md §3.3・DESIGN_HISTORY.md §15）: 速さの計算と、先行音が鳴り終わっているかの判定。"""
from __future__ import annotations

import types

import pytest

from mod_weaver.core.model import SampleSpec
from mod_weaver.framework.realize import tracker
from mod_weaver.framework.realize.encode import Codec
from mod_weaver.framework.realize.lanes import Placement

ONE_SHOT = SampleSpec(name="x", data=bytes(2000), volume=40, rate_note=24, rate_hz=2000.0)      # 8-bit 2000 frames
LOOPED = SampleSpec(name="y", data=bytes(2000), volume=40, loop=(0, 100), rate_note=24, rate_hz=2000.0)


def _p(step, kind="note", dur=None):
    return Placement(step=step, lane=0, kind=kind, inst="x", pitch=24, dur=dur)


def test_mod_octave_glide_speed_is_the_period_difference_per_active_tick():
    # period 428 -> 214 を 1 step（6 tick のうち、スライドが掛かるのは 5 tick）で
    assert tracker._glide_param(Codec("mod"), ONE_SHOT, 12, ONE_SHOT, 24, 5) == round(214 / 5)
    assert tracker._glide_param(Codec("mod"), ONE_SHOT, 12, ONE_SHOT, 24, 20) == round(214 / 20)


@pytest.mark.parametrize("fmt", ("s3m", "xm", "it"))
def test_extended_formats_use_the_same_amiga_equivalent_period_scale(fmt):
    c = Codec(fmt)
    spec = SampleSpec(name="x", data=bytes(2000), volume=40, rate_note=24, rate_hz=44100.0)
    # 44100 Hz の基準ノートの 1 オクターブ下から基準ノートへ: Amiga 換算の period は 2 × (クロック / 44100) → (クロック / 44100)
    expected = round(3546895.0 / 44100 / 20)
    assert tracker._glide_param(c, spec, c.n_ref - 12, spec, c.n_ref, 20) == expected


def test_glide_speed_is_clamped_to_one_byte_and_at_least_one():
    assert tracker._glide_param(Codec("mod"), ONE_SHOT, 0, ONE_SHOT, 35, 1) == 255
    assert tracker._glide_param(Codec("mod"), ONE_SHOT, 12, ONE_SHOT, 12, 5) == 1


def _ctx(bpm=150):
    return types.SimpleNamespace(codec=Codec("mod"), bpm=bpm)


def test_previous_one_shot_that_has_finished_playing_is_not_glided_from():
    # note 24（period 214）で 2000 frame の再生にかかる時間は 2000 / (3546895/214) = 0.1207 秒。
    # 1 step = 6 tick = 6 × 2.5 / 150 = 0.1 秒。
    ctx = _ctx()
    prev = _p(0)
    assert tracker._prev_sounding(ctx, prev, ONE_SHOT, 24, _p(1), 6)
    assert not tracker._prev_sounding(ctx, prev, ONE_SHOT, 24, _p(2), 6)


def test_looped_previous_note_sounds_until_it_is_stopped():
    ctx = _ctx()
    assert tracker._prev_sounding(ctx, _p(0), LOOPED, 24, _p(40), 6)
    assert tracker._prev_sounding(ctx, _p(0, dur=40), LOOPED, 24, _p(39), 6)
    assert not tracker._prev_sounding(ctx, _p(0, dur=8), LOOPED, 24, _p(8), 6)


def test_no_previous_note_or_a_stop_means_nothing_to_glide_from():
    ctx = _ctx()
    assert not tracker._prev_sounding(ctx, None, None, None, _p(1), 6)
    assert not tracker._prev_sounding(ctx, _p(0, kind="off"), LOOPED, 24, _p(1), 6)
