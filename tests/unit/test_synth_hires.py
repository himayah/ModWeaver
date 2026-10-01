"""core/synth.py の高解像度描画（oversample・bits。FRAMEWORK_REDESIGN.md §8）の検査。

I7（§13.1）: 全プリセットについて、m=1 と m>1 の描画を比べる。
- m=1・bits=8 は現行(MOD)の出力とバイト単位で完全に同じこと(既存のジャンル・テストの前提)。
- m>1 にしても、m=1 のナイキスト以下の帯域ではスペクトルの包絡が大きく変わらないこと。

トーン系(ToneLayer/PitchSweepLayer が主、NoiseLayer を持たない)は、同じ連続信号をより高いレートで
サンプリングしているだけなので、相関は非常に高くなるはず(閾値は全136プリセットを実測して 0.9 に決めた。
詳細は該当するテスト関数のコメント)。NoiseLayer を含む音色は ``rng.uniform()`` の消費が内部レートに
応じて時間軸上でずれる(seed は同じでも「経過何秒目のドロー」が変わる)ため、個々のスペクトルの微細構造
までは一致しない。そちらは厳密な相関ではなく、全体のエネルギー(RMS)が大きく変わらないことだけを
確かめる(§13.1 I7)。
"""
from __future__ import annotations

import math

import numpy as np
import pytest

from mod_weaver.core import dsp, synth
from mod_weaver.core.pitch import PERIODS
from mod_weaver.core.synth_presets import PRESETS

OVERSAMPLE = 3.0   # 低い notes で 44.1kHz 相当まで上げる場合に近い、現実的な倍率
N_BANDS = 40


def _is_noisy(patch: synth.Patch) -> bool:
    return any(isinstance(wl.layer, synth.NoiseLayer) for wl in patch.layers)


def _decode_signed(data: bytes, bits: int) -> np.ndarray:
    if bits == 8:
        raw = np.frombuffer(data, dtype=np.uint8).astype(np.int16)
        raw = np.where(raw > 127, raw - 256, raw)
        return raw.astype(np.float64) / 127.0
    raw = np.frombuffer(data, dtype="<i2").astype(np.float64)
    return raw / 32767.0


def _log_band_profile(xs: np.ndarray, rate: float, f_max: float, n_bands: int) -> np.ndarray:
    """[1 Hz, f_max] を対数間隔で n_bands 帯域に分け、各帯域の平均パワー(dB)を返す。"""
    if len(xs) < 8:
        return np.full(n_bands, -120.0)
    spec = np.abs(np.fft.rfft(xs * np.hanning(len(xs))))
    freqs = np.fft.rfftfreq(len(xs), d=1.0 / rate)
    edges = np.geomspace(1.0, max(f_max, 2.0), n_bands + 1)
    out = np.full(n_bands, -120.0)
    for i in range(n_bands):
        mask = (freqs >= edges[i]) & (freqs < edges[i + 1])
        if mask.any():
            p = np.mean(spec[mask] ** 2)
            out[i] = 10 * math.log10(p) if p > 0 else -120.0
    return out


def _rms_db(xs: np.ndarray) -> float:
    r = math.sqrt(float(np.mean(xs ** 2))) if len(xs) else 0.0
    return 20 * math.log10(r) if r > 0 else -120.0


@pytest.mark.parametrize("name", sorted(PRESETS))
def test_oversample_one_is_byte_identical_to_legacy_render(name):
    """既定(oversample=1.0, bits=8)は現行の render(patch) と完全に同じ(全プリセットの回帰)。"""
    patch = PRESETS[name]
    legacy = synth.render(patch)
    explicit = synth.render(patch, oversample=1.0, bits=8)
    assert explicit.data == legacy.data
    assert explicit.loop == legacy.loop
    assert explicit.sounding_hz == legacy.sounding_hz
    assert explicit.bits == 8
    assert explicit.rate_hz == pytest.approx(dsp.CLOCK / PERIODS[patch.rate_note])


@pytest.mark.parametrize("name", sorted(PRESETS))
def test_sounding_hz_is_independent_of_oversample(name):
    """sounding_hz は m に依存しない(FRAMEWORK_REDESIGN.md §8.1・§8.3)。"""
    patch = PRESETS[name]
    base = synth.render(patch, oversample=1.0, bits=8)
    high = synth.render(patch, oversample=OVERSAMPLE, bits=16)
    assert high.sounding_hz == base.sounding_hz


@pytest.mark.parametrize("name", sorted(p for p in PRESETS if not _is_noisy(PRESETS[p])))
def test_tonal_presets_keep_their_spectral_envelope_under_oversample(name):
    """ノイズ層を持たない(決定的な)プリセットは、m=1 のナイキスト以下で高い相関を保つ(I7)。

    bit 深度は両方とも 16 にして固定する(本番で S3M/XM/IT が使う深度)。8-bit と比べると
    量子化雑音の床の高さそのものが ~48dB 違うので、bit 深度を変えながら比べると「oversample で
    スペクトルの形が変わったか」ではなく「量子化雑音の床が変わったか」を測ってしまう(実測して気付いた。
    量子化雑音が減ること自体は意図した改善であり、ここで検査したいことではない)。
    """
    patch = PRESETS[name]
    base = synth.render(patch, oversample=1.0, bits=16)
    high = synth.render(patch, oversample=OVERSAMPLE, bits=16)
    base_rate = dsp.sample_rate(patch.rate_note)
    nyquist = base_rate / 2.0
    xs_base = _decode_signed(base.data, 16)
    xs_high = _decode_signed(high.data, 16)
    # Loop は 1 周期ぶんのデータがそのままスペクトル(周期境界をまたいで繰り返しても同じ)
    prof_base = _log_band_profile(xs_base, base_rate, nyquist, N_BANDS)
    prof_high = _log_band_profile(xs_high, base_rate * OVERSAMPLE, nyquist, N_BANDS)
    # 最下帯域(ほぼ直流)は除く: アタックの立ち上がり等の過渡成分の漏れ込みが N(サンプル数)に敏感で、
    # 可聴域の形とは無関係に相関を崩す(brass_braam で実測して気付いた。RMS はどちらもほぼ完全に一致して
    # いたので、聴こえる差ではない)。両方とも「床」(-100dB、実質無音)の帯域も除く: そこでの数値の違いは
    # 聴こえない差で、Pearson 相関に外れ値として乗ってしまう。
    prof_base, prof_high = prof_base[2:], prof_high[2:]
    keep = (prof_base > -100.0) | (prof_high > -100.0)
    corr = np.corrcoef(prof_base[keep], prof_high[keep])[0, 1]
    # 閾値 0.9 は全136プリセットを実測して決めた(最悪値は検出位相の合う free_arco_bass で 0.935。
    # 残りは概ね 0.98 以上。実装に誤りがあれば 0.9 よりずっと低くなる見込み)
    assert corr >= 0.9, f"{name}: correlation {corr:.3f} below threshold (band profiles: "\
                         f"base={prof_base.round(1)} high={prof_high.round(1)})"


@pytest.mark.parametrize("name", sorted(p for p in PRESETS if _is_noisy(PRESETS[p])))
def test_noisy_presets_keep_similar_energy_under_oversample(name):
    """ノイズ層を含むプリセットは乱数の消費が内部レートに応じてずれるため、スペクトルの細部までは
    一致しない。全体のエネルギー(RMS)が大きく変わらないことだけを確かめる(I7。閾値は実測して決めた)。
    bit 深度を固定する理由は上の関数と同じ。"""
    patch = PRESETS[name]
    base = synth.render(patch, oversample=1.0, bits=16)
    high = synth.render(patch, oversample=OVERSAMPLE, bits=16)
    xs_base = _decode_signed(base.data, 16)
    xs_high = _decode_signed(high.data, 16)
    db_base, db_high = _rms_db(xs_base), _rms_db(xs_high)
    assert abs(db_base - db_high) <= 6.0, f"{name}: RMS level changed by {db_high - db_base:+.1f} dB"
