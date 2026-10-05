"""基本周波数の推定（YIN 系。純 Python）。取り込み時だけ使う。"""
from __future__ import annotations

import math
from typing import Optional


def _decimate(x: list[float], rate: int, target: int = 11025) -> tuple[list[float], int]:
    k = max(1, rate // target)
    if k == 1:
        return x, rate
    return [sum(x[i:i + k]) / k for i in range(0, len(x) - k + 1, k)], rate // k


def yin(x: list[float], rate: int, fmin: float = 70.0, fmax: float = 900.0,
        threshold: float = 0.15) -> Optional[float]:
    """1 フレーム ``x`` の基本周波数（Hz）。周期性が弱ければ None。"""
    tau_min, tau_max = max(2, int(rate / fmax)), int(rate / fmin)
    w = len(x) - tau_max
    if w < tau_max:
        return None
    d = [0.0] * (tau_max + 1)
    for tau in range(1, tau_max + 1):
        s = 0.0
        for i in range(w):
            v = x[i] - x[i + tau]
            s += v * v
        d[tau] = s
    cm, acc = [1.0] * (tau_max + 1), 0.0
    for tau in range(1, tau_max + 1):
        acc += d[tau]
        cm[tau] = d[tau] * tau / acc if acc > 0 else 1.0
    tau = tau_min
    while tau < tau_max:
        if cm[tau] < threshold:
            while tau + 1 < tau_max and cm[tau + 1] < cm[tau]:
                tau += 1
            break
        tau += 1
    else:
        return None
    a, b, c = cm[tau - 1], cm[tau], cm[tau + 1] if tau + 1 <= tau_max else cm[tau]
    den = a - 2 * b + c
    shift = 0.5 * (a - c) / den if den else 0.0
    return rate / (tau + shift)


def estimate_f0(x: list[float], rate: int, frames: int = 3, frame_ms: float = 40.0) -> Optional[float]:
    """区間 ``x``（母音部）の代表 F0（フレームごとの推定の中央値）。"""
    y, r = _decimate(x, rate)
    flen = int(r * frame_ms / 1000) + int(r / 70)
    if len(y) < flen:
        return None
    found = []
    for k in range(frames):
        start = (len(y) - flen) * (k + 1) // (frames + 1)
        f = yin(y[start:start + flen], r)
        if f:
            found.append(f)
    if not found:
        return None
    found.sort()
    return found[len(found) // 2]


def hz_to_midi(hz: float) -> float:
    return 69.0 + 12.0 * math.log2(hz / 440.0)
