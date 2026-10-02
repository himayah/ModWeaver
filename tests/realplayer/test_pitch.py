"""I4（FRAMEWORK_REDESIGN.md §13.1）: 実音の一致。全形式で、同じ楽器の同じ音が §8.1 の基準（平均律）の高さで鳴る。

1 サンプルだけの曲を各形式で作り、音域の両端と中央の音を1音ずつ、libopenmpt で鳴らして FFT で基本周波数を測る。
基準は ``sounding_hz × 2^((t − rate_note)/12)``（t は tracker note）。許容は XM・IT が 7 セント（設計書どおり）、
MOD・S3M は形式固有の丸めがあるので下の ``TOLERANCE_CENTS`` のとおり。
"""
from __future__ import annotations

import pytest

from mod_weaver.core import synth
from mod_weaver.core.native import RCell, RealizedSong, RGrid, serialize
from mod_weaver.core.synth_presets import PRESETS
from mod_weaver.framework.realize.encode import Codec
from mod_weaver.framework.realize.samples import render_for
from mod_weaver.framework.target import resolve
from tests.framework.test_realize_mod import make_genre
from tests.realplayer import cents_between, decode_f32, fft_freq, requires_openmpt

pytestmark = requires_openmpt

TOLERANCE_CENTS = {"mod": 9.0, "xm": 7.0, "it": 7.0, "s3m": 12.0}
# MOD が 9 なのは、Period 表の丸め（最大 5.9 セント）に FFT の測定誤差（窓 0.8 秒で数セント）が乗るため。
# S3M が 12 なのは: ST3 の周期表は整数（基準オクターブで最大 ±5.6 セント）で、C2Spd を 44.1 kHz にすると
# 周期が小さく（上のオクターブで）整数への丸めが効く（実測で最大 11.9 セント。libopenmpt の ST3 の再現）。
# 音域の中心（基準 ±12 半音）では 9.4 セント以内。
RATE = 48000
SPEED, BPM = 31, 64                      # 1 row ≈ 1.21 秒
ROW_S = SPEED * 2.5 / BPM
# 基本周波数が測れる持続音（ループ）の全プリセット（ワンショットは減衰が速く、窓の中で測れない）
# 除外: 複数の声を数十セントずらして重ねる音色（スーパーソー・弦のアンサンブル）は基本周波数が一意に測れない
# （MOD でも同じ理由で外れるので、形式の問題ではない）。
UNMEASURABLE = {"fb_supersaw", "tension_strings"}
TONAL = sorted(k for k, p in PRESETS.items()
               if p.pitched and isinstance(p.finish, synth.Loop) and k not in UNMEASURABLE)


LOWEST_HZ = 170.0     # 窓 0.8 秒の FFT の分解能（約 1.25 Hz）では、これより低いと ±7 セントを判定できない


def _tones(patch, sounding_hz):
    """測る tracker note: MOD の範囲 0..35 の下端（測れる最低音）・基準（``rate_note``）・上端。
    他形式は同じ相対位置の音を鳴らす。"""
    low = next((t for t in range(0, patch.rate_note + 1)
                if sounding_hz * 2 ** ((t - patch.rate_note) / 12) >= LOWEST_HZ), patch.rate_note)
    return [low, patch.rate_note, 35]


def _song(fmt: str, spec, notes: list[int]) -> RealizedSong:
    codec = Codec(fmt)
    rows = 4 * len(notes)
    # 1 row ごとに 1 音（row 0, 4, 8 ... でなく、1 音 = 1 row で十分な長さを取る）
    g = RGrid(len(notes) + 1, 3, exclusive=codec.exclusive_vol_fx)
    g.put(0, 1, RCell(fx=codec.speed(SPEED)))
    g.put(0, 2, RCell(fx=codec.tempo(BPM)))
    for i, t in enumerate(notes):
        g.put(i, 0, RCell(note=t, sample=1, vol=None))
    patterns = [g]
    # 形式ごとの pattern の row 数規則
    if fmt in ("mod", "s3m"):
        full = RGrid(64, 3, exclusive=codec.exclusive_vol_fx)
        for r in range(g.rows):
            for ch in range(3):
                if not g.get(r, ch).is_empty:
                    full.put(r, ch, g.get(r, ch))
        full.put(g.rows, 0, RCell(vol=0) if fmt == "mod" else RCell(note=-1))
        full.put(g.rows, 1, RCell(fx=codec.pattern_break()))
        patterns = [full]
    elif fmt == "it":
        full = RGrid(32, 3)
        for r in range(g.rows):
            for ch in range(3):
                if not g.get(r, ch).is_empty:
                    full.put(r, ch, g.get(r, ch))
        full.put(g.rows, 1, RCell(fx=codec.pattern_break()))
        patterns = [full]
    return RealizedSong(format=fmt, title="pitch", samples=[spec], patterns=patterns, order=[0],
                        channel_pans=(128, 128, 128), initial_bpm=BPM, initial_speed=SPEED,
                        instrument_names=("x",), sample_release=(None,))


@pytest.mark.parametrize("fmt", ["mod", "s3m", "xm", "it"])
@pytest.mark.parametrize("key", TONAL)
def test_pitch_matches_sounding_hz(fmt, key):
    patch = PRESETS[key]
    genre = make_genre()
    target = resolve(fmt, 4 if fmt == "mod" else None, genre, seed=1)
    spec = render_for(patch, target)
    assert spec.sounding_hz
    codec = Codec(fmt)
    ts = _tones(patch, spec.sounding_hz)
    notes = [t if fmt == "mod" else codec.n_ref + (t - patch.rate_note) for t in ts]
    data = serialize(_song(fmt, spec, notes))
    audio = decode_f32(data, "." + fmt, RATE)
    for i, t in enumerate(ts):
        expected = spec.sounding_hz * 2 ** ((t - patch.rate_note) / 12)
        got = fft_freq(audio, RATE, i * ROW_S + 0.25, 0.8, expected)
        assert abs(cents_between(got, expected)) <= TOLERANCE_CENTS[fmt], (fmt, key, t, got, expected)


@pytest.mark.parametrize("fmt", ["s3m", "xm", "it"])
@pytest.mark.parametrize("cents", [-37, 12, 50])
def test_cents_variant_shifts_the_pitch_by_exactly_that_much(fmt, cents):
    """微分音・``tune_cents`` の変種（再生レートに 2^(cents/1200) を掛ける。§8.4）が、その分だけ高さをずらす。"""
    import dataclasses

    patch = PRESETS["keys_organ"]
    target = resolve(fmt, None, make_genre(), seed=1)
    base = render_for(patch, target)
    spec = dataclasses.replace(base, rate_hz=base.rate_hz * 2 ** (cents / 1200))
    codec = Codec(fmt)
    notes = [codec.n_ref + d for d in (0, 7)]
    audio = decode_f32(serialize(_song(fmt, spec, notes)), "." + fmt, RATE)
    for i, d in enumerate((0, 7)):
        expected = base.sounding_hz * 2 ** ((d * 100 + cents) / 1200)
        got = fft_freq(audio, RATE, i * ROW_S + 0.25, 0.8, expected)
        assert abs(cents_between(got, expected)) <= TOLERANCE_CENTS[fmt], (fmt, cents, d, got, expected)
