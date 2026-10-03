"""形式ごとの奏法の表現を実プレイヤー（libopenmpt）で確かめる（DESIGN.md §9.2 の F4 の実測項目）。

- ``Tremolo``: 深さが形式間で一致する（S3M・IT は深さのニブルを 2 倍にして合わせている。``encode.Codec.tremolo``）。
- リリース（``Instrument.release_s``）: XM・IT は音量エンベロープ＋キーオフ、MOD・S3M は音量スライドで、
  ``release_s`` 秒で無音になる。
- IT の ``Zxx``（既定の MIDI マクロ）でカットオフが効く。
- キーオフの挙動の事実: XM はエンベロープ無しでも止まるが、IT の ``===`` はエンベロープ無しでは止まらない
  （だから Realizer は ``release_s`` のある楽器だけに ``NOTE_OFF`` を使う）。
"""
from __future__ import annotations

import math
import random
import struct
import types

import pytest

from mod_weaver.core.model import SampleSpec
from mod_weaver.core.native import NOTE_OFF, RCell, RealizedSong, RGrid, serialize
from mod_weaver.framework.realize import tracker
from mod_weaver.framework.realize.encode import Codec
from tests.realplayer import decode_f32, requires_openmpt

np = pytest.importorskip("numpy")
pytestmark = requires_openmpt

RATE = 48000
FORMATS = ("mod", "s3m", "xm", "it")
SPEED, BPM = 6, 125
ROW_S = SPEED * 2.5 / BPM            # 0.12 秒
REF_NOTE = {"mod": 24, "s3m": 48, "xm": 48, "it": 60}


def _sample(bits: int, *, noise: bool = False, release=None) -> SampleSpec:
    n = 256 if noise else 64
    rnd = random.Random(1)
    vals = [(rnd.uniform(-1, 1) if noise else math.sin(2 * math.pi * i / n)) * 0.5 for i in range(n)]
    data = b"".join(struct.pack("<b", round(v * 127)) if bits == 8 else struct.pack("<h", round(v * 32767))
                    for v in vals)
    return SampleSpec("s", data, 64, loop=(0, len(data) // 2), rate_note=24, rate_hz=44100.0, bits=bits)


def _song(fmt: str, cells: dict, *, spec=None, rows=64, release=None) -> RealizedSong:
    codec = Codec(fmt)
    spec = spec or _sample(8 if fmt in ("mod", "s3m") else 16)
    n_rows = {"mod": 64, "s3m": 64, "xm": rows, "it": max(rows, 32)}[fmt]
    g = RGrid(n_rows, 3, exclusive=codec.exclusive_vol_fx)
    g.put(0, 1, RCell(fx=codec.speed(SPEED)))
    g.put(0, 2, RCell(fx=codec.tempo(BPM)))
    for (r, ch), c in cells.items():
        g.put(r, ch, c)
    return RealizedSong(format=fmt, title="fx", samples=[spec], patterns=[g], order=[0],
                        channel_pans=(128, 128, 128), initial_bpm=BPM, initial_speed=SPEED,
                        sample_release=(release,))


def _rms(a, block=0.02):
    n = int(block * RATE)
    return np.array([np.sqrt(np.mean(a[i:i + n] ** 2)) for i in range(0, len(a) - n, n)])


def _play(rs: RealizedSong, seconds: float):
    return decode_f32(serialize(rs), "." + rs.format, RATE)[:int(seconds * RATE)]


# ---- Tremolo ----

def _tremolo_swing(fmt: str, param: int) -> float:
    c = Codec(fmt)
    cells = {(0, 0): RCell(note=REF_NOTE[fmt], sample=1, vol=64 if fmt != "mod" else None, fx=c.tremolo(param))}
    cells.update({(r, 0): RCell(fx=c.tremolo(param)) for r in range(1, 40)})
    e = _rms(_play(_song(fmt, cells), 4.0))[10:]
    return 1 - e.min() / e.max()


@pytest.mark.parametrize("param", (0x82, 0x84, 0x86, 0x87))      # 深さ 7 まで（S3M・IT は 2 倍して 15 で頭打ち）
def test_tremolo_depth_matches_mod_in_every_format(param):
    ref = _tremolo_swing("mod", param)
    for fmt in ("s3m", "xm", "it"):
        assert _tremolo_swing(fmt, param) == pytest.approx(ref, abs=0.06), (fmt, param)


# ---- リリース ----

def _time_to_fade(fmt: str, release_s: float, off_row: int = 8) -> float:
    spec = _sample(8 if fmt in ("mod", "s3m") else 16)
    cells = {(0, 0): RCell(note=REF_NOTE[fmt], sample=1, vol=64 if fmt != "mod" else None)}
    rs = _song(fmt, cells, spec=spec, release=release_s)
    ctx = types.SimpleNamespace(codec=Codec(fmt), bpm=BPM, release=(release_s,), specs=[spec])
    tracker._put_stop(ctx, rs.patterns[0], 0, off_row, 64, release_s, SPEED)
    e = _rms(_play(rs, 6.0))
    t_off = off_row * ROW_S
    base = e[int(0.3 / 0.02):int((t_off - 0.05) / 0.02)].mean()
    after = e[int(t_off / 0.02):]
    below = np.where(after < 0.05 * base)[0]
    assert len(below), "never faded out"
    return below[0] * 0.02


@pytest.mark.parametrize("fmt", FORMATS)
@pytest.mark.parametrize("release_s", (0.36, 0.72))
def test_release_takes_release_s_seconds_to_fade(fmt, release_s):
    assert _time_to_fade(fmt, release_s) == pytest.approx(release_s, abs=0.08)


# ---- IT の Zxx ----

def _centroid(a) -> float:
    w = a[int(0.5 * RATE):int(2.0 * RATE)]
    sp = np.abs(np.fft.rfft(w * np.hanning(len(w))))
    return float((sp * np.fft.rfftfreq(len(w), 1 / RATE)).sum() / sp.sum())


def test_it_cutoff_zxx_lowers_the_spectral_centroid_monotonically():
    spec = _sample(16, noise=True)
    cents = []
    for z in (None, 96, 64, 32):
        cells = {(0, 0): RCell(note=60, sample=1, vol=64, fx=("Z", z) if z is not None else None)}
        cents.append(_centroid(_play(_song("it", cells, spec=spec), 2.2)))
    assert all(a > b * 1.3 for a, b in zip(cents, cents[1:])), cents


# ---- キーオフの挙動の事実 ----

def _level_after_key_off(fmt: str) -> tuple[float, float]:
    cells = {(0, 0): RCell(note=REF_NOTE[fmt], sample=1, vol=64), (8, 0): RCell(note=NOTE_OFF)}
    e = _rms(_play(_song(fmt, cells), 3.0), 0.05)
    t_off = 8 * ROW_S
    return float(e[int(0.3 / 0.05):int((t_off - 0.05) / 0.05)].mean()), float(e[int(t_off / 0.05) + 2:][:3].mean())


def test_xm_key_off_without_envelope_stops_the_note():
    before, after = _level_after_key_off("xm")
    assert after < 0.05 * before


def test_it_note_off_without_envelope_does_not_stop_the_note():
    """だから IT でも ``release_s`` の無い楽器には NOTE_CUT（^^^）を使う（encode.Codec.stop_cell）。"""
    before, after = _level_after_key_off("it")
    assert after > 0.9 * before


@pytest.mark.parametrize("rows", (12, 16))
def test_libopenmpt_plays_it_patterns_shorter_than_32_rows(rows):
    """IT の仕様上の下限は 32 row なので書き出しは 32 row に詰める（DESIGN.md §7.6）が、libopenmpt は短い pattern も正しく
    扱う（要実測の結果）。"""
    from mod_weaver.core import native_it

    native_it.MIN_ROWS, saved = 1, native_it.MIN_ROWS
    try:
        g = RGrid(rows, 3)
        g.put(0, 0, RCell(note=60, sample=1, vol=64))
        g.put(0, 1, RCell(fx=("A", SPEED)))
        g.put(0, 2, RCell(fx=("T", BPM)))
        rs = RealizedSong(format="it", title="r", samples=[_sample(16)], patterns=[g], order=[0] * 4,
                          channel_pans=(128,) * 3, initial_bpm=BPM, initial_speed=SPEED, sample_release=(None,))
        seconds = len(decode_f32(serialize(rs), ".it", RATE)) / RATE
    finally:
        native_it.MIN_ROWS = saved
    assert seconds == pytest.approx(4 * rows * ROW_S, abs=0.3)
