"""``core/native_level.py``（DESIGN.md §7.9）の単体テスト。"""
from __future__ import annotations

import math

import pytest

from mod_weaver.core import native_level as nl
from mod_weaver.core.model import SampleSpec
from mod_weaver.core.native import NOTE_CUT, RCell, RealizedSong, RGrid


def _rs(fmt, vols=(30,), sample_vol=20, channels=4):
    g = RGrid(4, channels)
    for ch, v in enumerate(vols):
        g.put(0, ch, RCell(note=5, sample=1, vol=v))
    spec = SampleSpec("s", bytes(4), sample_vol, rate_hz=44100.0)
    return RealizedSong(format=fmt, title="t", samples=[spec], patterns=[g], order=[0], channel_pans=(128,) * channels,
                        initial_bpm=125)


def test_room_is_limited_by_the_loudest_volume():
    assert nl.volume_room(_rs("xm", vols=(32,), channels=2)) == pytest.approx(2.0)
    assert nl.volume_room(_rs("xm", vols=(64,), channels=2)) == pytest.approx(1.0)


def test_stopped_channel_does_not_count():
    rs = _rs("xm", vols=(60,), channels=2)
    rs.patterns[0].put(1, 0, RCell(note=NOTE_CUT))
    assert nl.volume_room(rs) == pytest.approx(64 / 60)


def test_s3m_and_it_use_the_header_volume_first():
    gain, header = nl.plan(_rs("it", vols=(32,)), peak_db=-2.0 - 20 * math.log10(2))   # 足りない分がちょうど 2 倍
    assert header == 96 and gain == 1.0
    gain, header = nl.plan(_rs("s3m", vols=(32,)), peak_db=-14.0)     # 12 dB = 4 倍 → ヘッダの上限 127 を超える分は音量の値で
    assert header == 127 and gain > 1.0


def test_xm_and_mod_can_only_use_volume_values():
    gain, header = nl.plan(_rs("xm", vols=(32,)), peak_db=-2.0 - 20 * math.log10(2))
    assert header == nl.HEADER_VOLUME and gain == pytest.approx(2.0)
    gain, _ = nl.plan(_rs("xm", vols=(60,)), peak_db=-8.0)
    assert gain == pytest.approx(64 / 60)                             # 余裕の範囲で頭打ち


def test_no_lift_without_a_measurement_or_when_already_loud():
    assert nl.plan(_rs("it"), None) == (1.0, nl.HEADER_VOLUME)
    assert nl.plan(_rs("it"), -1.0) == (1.0, nl.HEADER_VOLUME)


def test_apply_scales_sample_and_cell_volumes_without_exceeding_64():
    rs = nl.apply(_rs("xm", vols=(40,), sample_vol=30), 1.6, 48)
    assert rs.samples[0].volume == 48 and rs.patterns[0].get(0, 0).vol == 64


def test_lift_falls_back_to_the_worst_peak_of_the_same_format():
    rs = _rs("it", vols=(10,), channels=4)
    quiet = nl.lift(rs, {"it16": -10.0, "it18": -6.0})               # it4 は無い → 同形式の最悪（−6）で代用
    assert quiet.mix_volume == int(48 * 10 ** (4 / 20))
    assert nl.lift(rs, {"s3m8": -10.0}).mix_volume == nl.HEADER_VOLUME   # 別形式の値は使わない
