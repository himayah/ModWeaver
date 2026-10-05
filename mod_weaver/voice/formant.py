"""組込みのフォルマント合成の声（VOCAL_DESIGN.md §5.2）。声のデータは持たず、コードだけで描画する。

声門音源（Rosenberg 風パルスの微分）を、母音ごとの共鳴フィルタ（中心周波数・帯域）に通す。静的な周期波形は
「声」ではなくオルガンのように聞こえる（P3 の試聴で確認）ので、サンプルに**声らしい揺れを焼き込む**:
ビブラート・ジッタ・シマー・息の雑音を、すべて**ループ長 L に整数周期入る**形で作る。すると定常部は厳密に L 周期で、
ループが継ぎ目なしになる（クロスフェード不要）。基本周波数は ``L`` の間に整数周期入る値に丸める（呼出し側が ``home_hz`` と
再生レートで補正する）。``choir`` はわずかに離調・位相をずらした 3 声の重ね（合唱のア〜）。
フォルマントは音高に追従させず、使われた音高帯ごとに描き分ける（呼出し側の ``bucket``）。値は耳で調整する初期値。
"""
from __future__ import annotations

import math
import random
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
TIMBRE_SCALE = {"female": 1.15, "male": 1.0, "child": 1.3, "choir": 1.08}   # フォルマントの倍率

PEAK = 0.85
LOOP_SECONDS = 0.4                  # ループ長。ビブラート 2 周期ぶん
VIBRATO_HZ = 5.0                    # LOOP_SECONDS に整数周期（2）入る
VIBRATO_DEPTH = 0.011               # ±1.1%（約 ±19 セント）
ATTACK_SECONDS = 0.05
BREATH = 0.05
CHOIR_DETUNE_STEPS = (-1, 0, 1)     # 1 ステップ = rate/L Hz（約 2.5 Hz）


@dataclass(frozen=True)
class Rendered:
    data: list[float]                  # -1..1
    rate: int
    loop: tuple[int, int]              # (開始, 長さ)。長さの末尾＝data の末尾
    home_hz: float                     # 実際の基本周波数（ループに整数周期入るよう丸めた値）
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


def _periodic_wobble(n: int, rng: random.Random, count: int, lo: int, hi: int) -> list[float]:
    """``n`` サンプルに整数周期入る正弦波の和（振幅の合計が 1）。ジッタ・シマー用。"""
    parts = [(rng.randint(lo, hi), rng.uniform(0, 2 * math.pi), rng.uniform(0.5, 1.0)) for _ in range(count)]
    total = sum(a for _c, _p, a in parts)
    return [sum(a * math.sin(2 * math.pi * c * i / n + p) for c, p, a in parts) / total for i in range(n)]


def _source(f0: float, n_loop: int, repeats: int, rate: int, rng: random.Random, vib_phase: float) -> list[float]:
    """``repeats`` 回ぶん（ループ長 ``n_loop`` の周期信号）の声門音源。"""
    vib = [VIBRATO_DEPTH * math.sin(2 * math.pi * VIBRATO_HZ * i / rate + vib_phase) for i in range(n_loop)]
    jit = [0.003 * v for v in _periodic_wobble(n_loop, rng, 3, 7, 23)]
    shim = [1 + 0.05 * v for v in _periodic_wobble(n_loop, rng, 3, 3, 9)]
    noise = [rng.uniform(-1, 1) for _ in range(n_loop)]
    ph, prev, out = 0.0, 0.0, []
    for r in range(repeats):
        for i in range(n_loop):
            ph += f0 * (1 + vib[i] + jit[i]) / rate
            ph -= math.floor(ph)
            p = 0.5 * (1 - math.cos(math.pi * ph / 0.6)) if ph < 0.6 else math.cos(math.pi * (ph - 0.6) / 0.8)
            out.append(((p - prev) * 12 + BREATH * noise[i]) * shim[i])
            prev = p
    return out


def _voice(nucleus: str, f0: float, scale: float, n_loop: int, rate: int, seed: int, vib_phase: float) -> list[float]:
    rng = random.Random(seed)
    src = _source(f0, n_loop, 3, rate, rng, vib_phase)
    mix = [0.0] * len(src)
    prev_fc = 0.0
    for k, ((fc, bw), g) in enumerate(zip(VOWELS[nucleus], GAINS.get(nucleus, DEFAULT_GAINS))):
        fc = fc * scale
        if k == 0:
            fc = max(fc, 1.1 * f0)                  # 高い音では F1 を基本周波数の少し上へ（歌手のフォルマントチューニング）
        fc = max(fc, prev_fc + 150) if k else fc
        prev_fc = fc
        for i, y in enumerate(resonate(src, fc, bw, rate)):
            mix[i] += y * g
    return mix[2 * n_loop:]                          # 3 回目の周期（定常部）


def render_vowel(nucleus: str, f0_hz: float, timbre: str = "female", rate: int = 44100) -> Rendered:
    if nucleus not in VOWELS:
        raise ValueError(f"no formant table for nucleus {nucleus!r}")
    n_loop = round(LOOP_SECONDS * rate)
    step_hz = rate / n_loop
    f0 = max(1, round(f0_hz / step_hz)) * step_hz       # ループにちょうど整数周期入る基本周波数
    scale = TIMBRE_SCALE.get(timbre, 1.0)
    seed = (ord(nucleus) * 7919 + round(f0)) & 0xFFFF
    if timbre == "choir":
        voices = [_voice(nucleus, f0 + d * step_hz, scale, n_loop, rate, seed + 31 * j, 2.1 * j)
                  for j, d in enumerate(CHOIR_DETUNE_STEPS)]
        body = [sum(v[i] for v in voices) for i in range(n_loop)]
    else:
        body = _voice(nucleus, f0, scale, n_loop, rate, seed, 0.0)
    attack = round(ATTACK_SECONDS * rate)
    peak = max(abs(v) for v in body) or 1.0
    k = PEAK / peak
    body = [v * k for v in body]
    head = body[-attack:]                                # ループ末尾（周期なので直前の続き）をフェードインして頭にする
    head = [v * (0.5 - 0.5 * math.cos(math.pi * (i + 1) / attack)) for i, v in enumerate(head)]
    return Rendered(head + body, rate, (attack, n_loop), f0)
