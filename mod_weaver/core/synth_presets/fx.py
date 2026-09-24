"""効果音（第３段階の共有音色。DESIGN.md §12.4）。ノイズはループにできないので、長い OneShot を小節頭で鳴らし直す。"""
from __future__ import annotations

from ..synth import OneShot, Patch
from ._common import MID, noise, sweep
from ._registry import register

FX_VINYL = register("fx_vinyl", Patch(
    "VinylNoise", (noise(weight=0.8, lp=0.6), noise(weight=0.25, hp=True)),
    OneShot(3.0), pitched=False, attack_ms=30.0, tail_fade_ms=30.0, rate_note=MID, volume=14),
    "レコードのヒスノイズ（lo-fi の背景）。2小節ほどで鳴らし直す。")

FX_RAIN = register("fx_rain", Patch(
    "Rain", (noise(lp=0.8),), OneShot(3.0), pitched=False, attack_ms=50.0, tail_fade_ms=50.0,
    rate_note=MID, volume=16),
    "雨音のような柔らかい LP ノイズ（lo-fi chill の環境音）。")

FX_RISER = register("fx_riser", Patch(
    "Riser", (noise(weight=0.8, rise=2.5, hp=True), sweep(200.0, 1400.0, 0.8, None, weight=0.4)),
    OneShot(2.0), pitched=False, tail_fade_ms=20.0, rate_note=MID, volume=44),
    "盛り上げの上昇音（上昇する HP ノイズ＋上がっていく音程）。")

FX_IMPACT = register("fx_impact", Patch(
    "Impact", (sweep(120.0, 35.0, 6.0, 2.5), noise(weight=0.6, decay=4.0, lp=0.5)),
    OneShot(2.0), pitched=False, saturate=1.5, rate_note=MID, volume=64),
    "低い衝撃音（ドロップ頭・予告編の一撃）。")
