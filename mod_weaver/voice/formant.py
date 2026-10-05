"""組込みのフォルマント合成の声（VOCAL_DESIGN.md §5.2）。声のデータは持たず、コードだけで描画する。

声門音源（Rosenberg 風パルスの微分）を、母音ごとの共鳴フィルタ（中心周波数・帯域）に通す。母音のサンプルは
**周期が整数サンプル**になる F0 で描き、定常部をそのままループにする（継ぎ目なし）。音高に追従させない
（フォルマントを動かさない）ため、使われた音高帯ごとに F0 を変えて描き分ける（呼出し側の ``bucket``）。
子音・息成分は後の段階（P4）。値は耳で調整する初期値。
"""
from __future__ import annotations

import math
from dataclasses import dataclass

VOWELS = {   # 日本語の母音（X-SAMPA 風。う は M）: ((中心 Hz, 帯域 Hz), ...)
    "a": ((800, 80), (1200, 90), (2600, 120), (3300, 150)),
    "i": ((300, 60), (2300, 90), (3000, 120), (3400, 150)),
    "M": ((350, 60), (1300, 90), (2400, 120), (3300, 150)),
    "e": ((500, 70), (1900, 90), (2600, 120), (3300, 150)),
    "o": ((500, 70), (900, 80), (2500, 120), (3300, 150)),
}
GAINS = {"i": (1.0, 1.4, 0.8, 0.5)}           # い は F2 が高く弱く聞こえるので持ち上げる（試作で確認）
DEFAULT_GAINS = (1.0, 0.8, 0.5, 0.35)
TIMBRE_SCALE = {"female": 1.15, "male": 1.0, "child": 1.3, "choir": 1.05}   # フォルマントの倍率

PEAK = 0.85
ATTACK_PERIODS, SETTLE_PERIODS, LOOP_PERIODS = 4, 8, 8


@dataclass(frozen=True)
class Rendered:
    data: list[float]                  # -1..1
    rate: int
    loop: tuple[int, int]              # (開始, 長さ)。長さの末尾＝data の末尾
    home_hz: float                     # 実際の基本周波数（周期が整数サンプルになるよう丸めた値）
    pre: int = 0                       # 母音の頭（サンプル）。母音だけなので 0


def resonate(x: list[float], fc: float, bw: float, rate: int) -> list[float]:
    r = math.exp(-math.pi * bw / rate)
    c1, c2 = 2 * r * math.cos(2 * math.pi * fc / rate), -r * r
    g = 1 - c1 - c2
    y1 = y2 = 0.0
    out = []
    for v in x:
        y = g * v + c1 * y1 + c2 * y2
        out.append(y)
        y2, y1 = y1, y
    return out


def _glottal(period: int, n_periods: int) -> list[float]:
    one = []
    for i in range(period):
        ph = i / period
        one.append(0.5 * (1 - math.cos(math.pi * ph / 0.6)) if ph < 0.6 else math.cos(math.pi * (ph - 0.6) / 0.8))
    wave = one * n_periods
    prev = wave[-1]
    out = []
    for v in wave:
        out.append((v - prev) * 12)           # 放射特性（微分）
        prev = v
    return out


def render_vowel(nucleus: str, f0_hz: float, timbre: str = "female", rate: int = 44100) -> Rendered:
    if nucleus not in VOWELS:
        raise ValueError(f"no formant table for nucleus {nucleus!r}")
    period = max(8, round(rate / f0_hz))
    n_periods = SETTLE_PERIODS + LOOP_PERIODS
    src = _glottal(period, n_periods)
    scale = TIMBRE_SCALE.get(timbre, 1.0)
    mix = [0.0] * len(src)
    for (fc, bw), g in zip(VOWELS[nucleus], GAINS.get(nucleus, DEFAULT_GAINS)):
        for i, y in enumerate(resonate(src, fc * scale, bw, rate)):
            mix[i] += y * g
    peak = max(abs(v) for v in mix[SETTLE_PERIODS * period:]) or 1.0
    k = PEAK / peak
    data = [v * k for v in mix]
    fade = ATTACK_PERIODS * period
    for i in range(fade):
        data[i] *= (i + 1) / fade
    return Rendered(data, rate, (SETTLE_PERIODS * period, LOOP_PERIODS * period), rate / period)
