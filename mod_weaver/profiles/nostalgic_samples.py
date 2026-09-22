"""Nostalgic のサンプル合成（旧 twilight_pad.py の gen_* を式・定数とも無改変で移設。設計書 D11）。

浮動小数の演算順序が変わるとバイト同一性が崩れるため、新 DSP プリミティブへの置換はしない。
"""
from __future__ import annotations

import math
import random

from ..core.dsp import clamp, pad_even, sample_rate

SR = sample_rate(24)  # ~8287.1378 Hz（C-3 再生レート基準。旧 SR と同値）

# ============================================================
# サンプル音源生成 (ノスタルジック・高音質設計)
# ============================================================

def gen_kick():
    """Lo-Fi Warm Kick: 深く温かみのある丸いキック"""
    length = int(0.20 * SR)
    data = []
    for i in range(length):
        t = i / SR
        phase = 2 * math.pi * (46 * t + (64.0 / 30.0) * (1.0 - math.exp(-30.0 * t)))
        env = math.exp(-11.5 * t)
        v = math.sin(phase) * env
        v = math.tanh(v * 1.3)
        data.append(clamp(v * 127) & 0xFF)
    return pad_even(bytes(data))

def gen_snare():
    """Nostalgic Soft Snare: 乾いたレトロな質感の柔らかいスネア"""
    r = random.Random(42)  # サンプル波形は常に安定した高品質
    length = int(0.18 * SR)
    data = []
    lp = 0.0
    for i in range(length):
        t = i / SR
        tone = math.sin(2 * math.pi * 175 * t) * math.exp(-22.0 * t)
        raw_noise = r.uniform(-1.0, 1.0)
        lp = lp * 0.35 + raw_noise * 0.65
        noise = lp * math.exp(-14.0 * t)
        v = tone * 0.45 + noise * 0.55
        v = math.tanh(v * 1.25)
        data.append(clamp(v * 127) & 0xFF)
    return pad_even(bytes(data))

def gen_hihat():
    """Closed Hi-Hat: 繊細で小気味よいLo-Fiクローズドハット"""
    r = random.Random(123)
    length = int(0.045 * SR)
    data = []
    prev = 0.0
    for i in range(length):
        t = i / SR
        raw = r.uniform(-1.0, 1.0)
        ring = (math.sin(2 * math.pi * 3200 * t) + math.sin(2 * math.pi * 4400 * t)) * 0.25
        hp = (raw + ring) - prev
        prev = raw + ring
        env = math.exp(-65.0 * t)
        v = hp * env * 0.85
        v = math.tanh(v * 1.4)
        data.append(clamp(v * 127) & 0xFF)
    return pad_even(bytes(data))

def gen_bass():
    """Warm Mellow Bass: 豊かで丸みのあるアコースティック風ベース (実音 C4基準)"""
    length = int(0.72 * SR)
    f0 = 261.63
    data = []
    for i in range(length):
        t = i / SR
        v1 = math.sin(2 * math.pi * f0 * t) * 0.80
        v2 = math.sin(2 * math.pi * 2 * f0 * t) * 0.20
        attack = min(1.0, t / 0.005)
        env = attack * math.exp(-3.2 * t)
        v = math.tanh((v1 + v2) * env * 1.25)
        data.append(clamp(v * 127) & 0xFF)
    return pad_even(bytes(data))

def gen_musicbox():
    """Nostalgic Music Box / Chime: 郷愁を誘う澄んだオルゴール/トイチャイム音"""
    length = int(1.15 * SR)
    f0 = 261.63
    data = []
    for i in range(length):
        t = i / SR
        v1 = math.sin(2 * math.pi * f0 * t) * math.exp(-2.0 * t) * 0.55
        v2 = math.sin(2 * math.pi * 2 * f0 * t) * math.exp(-3.5 * t) * 0.25
        v3 = math.sin(2 * math.pi * 3 * f0 * t) * math.exp(-5.0 * t) * 0.12
        v4 = math.sin(2 * math.pi * 5.4 * f0 * t) * math.exp(-12.0 * t) * 0.08
        attack = min(1.0, t / 0.0015)
        v = (v1 + v2 + v3 + v4) * attack
        v = math.tanh(v * 1.1)
        data.append(clamp(v * 127) & 0xFF)
    return pad_even(bytes(data))

def gen_pad():
    """Twilight Ambient Pad: 完全ループ対応の温かいアナログ・ストリングスパッド"""
    length = 1024
    K = 32
    data = []
    for i in range(length):
        phase = 2 * math.pi * K * i / length
        h1 = math.sin(phase) * 0.55
        h2 = math.sin(2 * phase) * 0.22
        h3 = math.sin(3 * phase) * 0.08
        sub = math.sin(0.5 * phase) * 0.30
        v = h1 + h2 + h3 + sub
        v = math.tanh(v * 0.95)
        data.append(clamp(v * 127) & 0xFF)
    return pad_even(bytes(data))

def gen_flute():
    """Mellow Flute / Lead: 哀愁漂う素朴な木管風リード (完全ループ)"""
    length = 1024
    K = 32
    data = []
    for i in range(length):
        phase = 2 * math.pi * K * i / length
        s1 = math.sin(phase) * 0.72
        s3 = math.sin(3 * phase) * 0.16
        s5 = math.sin(5 * phase) * 0.06
        v = s1 + s3 + s5
        v = math.tanh(v * 1.05)
        data.append(clamp(v * 127) & 0xFF)
    return pad_even(bytes(data))
