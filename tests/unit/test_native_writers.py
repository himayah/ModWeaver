"""``core/native_s3m.py``・``native_xm.py``・``native_it.py``（FRAMEWORK_REDESIGN.md §10）の単体テスト。
読み戻し（パーサ）で値が一致すること、検査器が壊れたファイルを ERROR にすることを確かめる。実プレイヤーでの
再生は ``tests/realplayer/`` が担う（自作 writer と自作 parser が同じ誤解を共有しうるため）。"""
from __future__ import annotations

import math
import struct

import pytest

from mod_weaver.core import it, native, native_it, native_s3m, native_xm, s3m
from mod_weaver.core.model import SampleSpec
from mod_weaver.core.native import NOTE_CUT, NOTE_OFF, RCell, RealizedSong, RGrid
from mod_weaver.core.verify import parse_xm
from mod_weaver.errors import PlanError


def _pcm(bits: int, n: int = 64) -> bytes:
    vals = [round((100 if bits == 8 else 20000) * math.sin(2 * math.pi * i / n)) for i in range(n)]
    return b"".join(struct.pack("<b" if bits == 8 else "<h", v) for v in vals)


def _spec(bits=8, loop=True, rate_hz=44100.0, volume=50, pan=128, name="smp") -> SampleSpec:
    data = _pcm(bits)
    n_words = len(data) // 2
    return SampleSpec(name=name, data=data, volume=volume, loop=(0, n_words) if loop else None,
                      rate_note=24, rate_hz=rate_hz, bits=bits, pan=pan)


def _song(fmt: str, specs, rows: int, cells: dict, release=None, channels=3) -> RealizedSong:
    g = RGrid(rows, channels)
    for (r, ch), c in cells.items():
        g.put(r, ch, c)
    return RealizedSong(format=fmt, title="t", samples=specs, patterns=[g], order=[0],
                        channel_pans=(64, 192, 128)[:channels], initial_bpm=125, initial_speed=6,
                        sample_release=release or (None,) * len(specs))


BASE = {"s3m": 48, "xm": 48, "it": 60}


def _codes(issues, level="ERROR"):
    return {i.code for i in issues if i.level == level}


def _cells(fmt, extra=None):
    cells = {(0, 0): RCell(note=BASE[fmt], sample=1, vol=40),
             (0, 1): RCell(fx=("A", 6) if fmt in ("s3m", "it") else ("F", 6)),
             (0, 2): RCell(fx=("T", 125) if fmt in ("s3m", "it") else ("F", 125)),
             (4, 0): RCell(note=NOTE_CUT if fmt != "xm" else None, vol=0 if fmt == "xm" else None)}
    cells.update(extra or {})
    return cells


# ---- XM ----

@pytest.mark.parametrize("bits", (8, 16))
def test_xm_delta_round_trip(bits):
    data = _pcm(bits)
    decoded = native_xm.delta_decode(native_xm.delta_encode(data, bits), bits)
    expected = list(struct.unpack(f"<{len(data) // (bits // 8)}{'b' if bits == 8 else 'h'}", data))
    assert decoded == expected


def test_xm_tuning_reproduces_the_rate():
    for rate in (8363.0, 22050.0, 44100.0, 44096.3, 100000.0):
        rel, fine = native_xm.tuning(rate)
        assert -64 <= fine <= 64
        assert 8363 * 2 ** ((rel + fine / 128) / 12) == pytest.approx(rate, rel=1e-3)


def test_xm_round_trip_16bit_and_volume_column():
    rs = _song("xm", [_spec(16, pan=200)], 32, _cells("xm", {(2, 0): RCell(note=NOTE_OFF)}))
    data = native_xm.serialize(rs)
    assert native_xm.verify(data) == []
    pm = parse_xm(data)
    inst = pm.instruments[0]
    s = inst.samples[0]
    assert s.sample_type & 0x10 and s.length == len(rs.samples[0].data) and s.pan == 200
    assert native_xm.delta_decode(s.data, 16) == list(struct.unpack("<64h", rs.samples[0].data))
    cell = pm.patterns[0][0][0]
    assert cell.note == 49 and cell.instrument == 1 and cell.volume == 0x10 + 40   # ボリューム列
    assert pm.patterns[0][2][0].note == native_xm.KEY_OFF
    assert pm.patterns[0][0][1].effect == 0xF and pm.patterns[0][0][1].param == 6


def test_xm_release_envelope_is_written_only_for_samples_with_release():
    rs = _song("xm", [_spec(16), _spec(16, name="b")], 32, _cells("xm"), release=(0.5, None))
    pm = parse_xm(native_xm.serialize(rs))
    a, b = pm.instruments
    assert a.vol_type == 0x03 and a.vol_sustain == 0 and a.vol_points == [(0, 64), (round(0.5 / (2.5 / 125)), 0)]
    assert b.vol_type == 0 and b.vol_points == []
    assert _codes(native_xm.verify(native_xm.serialize(rs))) == set()      # 未使用の楽器は INFO だけ


def test_xm_refuses_note_cut():
    rs = _song("xm", [_spec(16)], 32, {(0, 0): RCell(note=NOTE_CUT)})
    with pytest.raises(PlanError):
        native_xm.serialize(rs)


# ---- IT ----

def test_it_is_written_in_instrument_mode_with_16bit_samples():
    rs = _song("it", [_spec(16, rate_hz=44096.0), _spec(16, name="b")], 32, _cells("it"))
    data = native_it.serialize(rs)
    assert native_it.verify(data) == []
    pm = it.parse_it(data)
    assert pm.flags & native_it.FLAG_INSTRUMENTS and pm.flags & it.FLAG_OLD_EFFECTS
    assert len(pm.instruments) == 2 == len(pm.samples)
    assert pm.instruments[1].keyboard == [(k, 2) for k in range(120)]     # 全ノートが同じ番号のサンプルへ
    assert pm.instruments[0].nna == 0
    s = pm.samples[0]
    assert s.flags & it.SAMPLE_FLAG_16BIT and s.length == 64 and len(s.data) == 128 and s.c5speed == 44096
    assert s.loop_begin == 0 and s.loop_end == 64                          # ループは「サンプル数」単位
    assert s.cvt & it.CVT_SIGNED and s.dfp & 0x80 == 0                     # パンは使わない（ヘッダのチャンネルパン）


def test_it_note_cut_and_note_off_bytes():
    rs = _song("it", [_spec(16)], 32, _cells("it", {(2, 0): RCell(note=NOTE_OFF)}))
    pm = it.parse_it(native_it.serialize(rs))
    assert pm.patterns[0][2][0].note == 255 and pm.patterns[0][4][0].note == 254


def test_it_release_envelope_has_sustain_and_release_nodes():
    rs = _song("it", [_spec(16)], 32, _cells("it"), release=(0.25,))
    ins = it.parse_it(native_it.serialize(rs)).instruments[0]
    assert ins.vol_env_flags == native_it.ENV_FLAG_ON | native_it.ENV_FLAG_SUSTAIN
    assert ins.vol_env_points[0] == (0, 64) and ins.vol_env_points[1][1] == 0 and ins.vol_env_sustain == (0, 0)


def test_it_rejects_patterns_shorter_than_32_rows():
    rs = _song("it", [_spec(16)], 16, _cells("it"))
    with pytest.raises(PlanError):
        native_it.serialize(rs)


# ---- S3M ----

def test_s3m_round_trip():
    rs = _song("s3m", [_spec(8, rate_hz=44100.0)], 64, _cells("s3m", {(1, 0): RCell(note=48 + 14, sample=1)}))
    data = native_s3m.serialize(rs)
    assert native_s3m.verify(data) == []
    pm = s3m.parse_s3m(data)
    assert pm.samples[0].c2spd == 44100 and pm.samples[0].length == 64
    assert pm.patterns[0][0][0].note == 0x40 and pm.patterns[0][1][0].note == 0x52     # C-4 と D-5
    assert pm.patterns[0][0][0].volume == 40
    assert pm.patterns[0][4][0].note == 254                                           # ^^^


def test_s3m_rejects_16bit_and_oversized_samples():
    with pytest.raises(PlanError):
        native_s3m.serialize(_song("s3m", [_spec(16)], 64, _cells("s3m")))
    big = _spec(8)
    big.data = bytes(64002)
    with pytest.raises(PlanError):
        native_s3m.serialize(_song("s3m", [big], 64, _cells("s3m")))


def test_s3m_requires_64_row_patterns():
    with pytest.raises(PlanError):
        native_s3m.serialize(_song("s3m", [_spec(8)], 32, _cells("s3m")))


# ---- 検査器が壊れたものを見つける ----

def test_verifiers_flag_missing_sample_number_and_missing_tempo():
    for fmt, rows in (("s3m", 64), ("xm", 32), ("it", 32)):
        bits = 8 if fmt == "s3m" else 16
        cells = {(0, 0): RCell(note=BASE[fmt])}                     # sample 番号の無い発音・テンポ無し
        data = native.serialize(_song(fmt, [_spec(bits)], rows, cells))
        assert {"V07", "V10"} <= _codes(native.verify(fmt, data)), fmt


def test_verifiers_flag_unknown_sample_and_bad_volume():
    for fmt, rows in (("s3m", 64), ("xm", 32), ("it", 32)):
        bits = 8 if fmt == "s3m" else 16
        cells = _cells(fmt, {(1, 0): RCell(note=BASE[fmt], sample=5)})
        assert "V06" in _codes(native.verify(fmt, native.serialize(_song(fmt, [_spec(bits)], rows, cells)))), fmt


def test_verifiers_flag_truncated_files():
    for fmt, rows in (("s3m", 64), ("xm", 32), ("it", 32)):
        bits = 8 if fmt == "s3m" else 16
        data = native.serialize(_song(fmt, [_spec(bits)], rows, _cells(fmt)))
        assert _codes(native.verify(fmt, data[: len(data) // 2])), fmt
        magic = {"s3m": 44, "xm": 0, "it": 0}[fmt]
        broken = data[:magic] + b"junk" + data[magic + 4:]
        assert "V02" in _codes(native.verify(fmt, broken)), fmt          # マジック不正


def test_s3m_and_it_warn_on_very_low_playback_rate():
    low = _spec(8, rate_hz=500.0)
    assert "V18" in _codes(native_s3m.verify(native_s3m.serialize(_song("s3m", [low], 64, _cells("s3m")))), "WARN")
    low16 = _spec(16, rate_hz=500.0)
    assert "V18" in _codes(native_it.verify(native_it.serialize(_song("it", [low16], 32, _cells("it")))), "WARN")


def test_xm_verifier_flags_bad_volume_column_and_envelope():
    rs = _song("xm", [_spec(16)], 32, _cells("xm"), release=(0.5,))
    data = bytearray(native_xm.serialize(rs))
    pm = parse_xm(bytes(data))
    assert native_xm.verify(bytes(data)) == []
    # 音量エンベロープの2点目の tick を 0 にして単調増加を壊す
    inst_pos = len(data) - sum(len(i.samples[0].data) for i in pm.instruments) - 40 - 243
    data[inst_pos + 129 + 4:inst_pos + 129 + 6] = struct.pack("<H", 0)
    assert "V19" in _codes(native_xm.verify(bytes(data)))
