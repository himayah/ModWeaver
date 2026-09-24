"""鍵盤（第３段階の共有音色。DESIGN.md §4.5）。和音サンプルは profiles/band_common.chord_patch で作る。"""
from __future__ import annotations

from ..synth import Loop, OneShot, Patch
from ._common import MID, loop_harmonics, noise, tone
from ._registry import register

KEYS_PIANO = register("keys_piano", Patch(
    "Piano", (tone((1.0, 1.0, 3.2), (2.0, 0.45, 4.5), (3.0, 0.25, 6.0), (4.0, 0.12, 8.0), (5.02, 0.06, 10.0)),
              noise(weight=0.05, decay=300.0)),
    OneShot(1.60), pitched=True, attack_ms=2.0, peak=0.9, rate_note=MID, volume=50),
    "アコースティック・ピアノ。高次倍音ほど速く減衰し、わずかに非調和な第5倍音とハンマーのノイズ。")

KEYS_EP = register("keys_ep", Patch(
    "ElectricPiano", (tone((1.0, 1.0, 2.2), (2.0, 0.18, 3.5), (3.0, 0.08, 6.0), (7.0, 0.12, 25.0)),),
    OneShot(1.40), pitched=True, attack_ms=3.0, peak=0.9, rate_note=MID, volume=48),
    "Rhodes 風のエレクトリック・ピアノ。正弦に近い基音と、打鍵の瞬間だけ鳴る高い「ティン」成分。")

KEYS_ORGAN = register("keys_organ", Patch(
    "Organ", loop_harmonics(6, ((1, 0.8), (2, 1.0), (3, 0.5), (4, 0.3), (6, 0.2), (8, 0.15))),
    Loop(190, attack_samples=30), pitched=True, rate_note=MID, volume=40),
    "ドローバー・オルガン（ループ）。")

KEYS_BELL = register("keys_bell", Patch(
    "Bell", (tone((1.0, 1.0, 3.0), (2.76, 0.5, 5.0), (5.4, 0.3, 8.0), (8.93, 0.15, 12.0)),),
    OneShot(1.80), pitched=True, peak=0.85, rate_note=MID, volume=42),
    "グロッケン／ベル。非調和部分音の長い余韻。")

KEYS_HARP = register("keys_harp", Patch(
    "Harp", (tone((1.0, 1.0, 3.0), (2.0, 0.4, 5.0), (3.0, 0.2, 7.0), (4.0, 0.1, 9.0)),),
    OneShot(1.20), pitched=True, attack_ms=2.0, rate_note=MID, volume=46),
    "ハープ（分散和音用の撥弦）。")

KEYS_HOUSE_STAB = register("keys_house_stab", Patch(
    "HouseStab", (tone((1.0, 1.0, 9.0), (2.0, 0.6, 11.0), (3.0, 0.3, 13.0), (4.0, 0.2, 16.0)),),
    OneShot(0.40), pitched=True, saturate=1.2, rate_note=MID, volume=44),
    "ハウスのオルガン／ピアノ・スタブ（和音サンプルの素材）。")
