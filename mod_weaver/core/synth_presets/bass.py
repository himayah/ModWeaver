"""ベース（第３段階の共有音色。DESIGN.md §4.5）。shift=-12（logical 0..11 を t=12..23 で）。"""
from __future__ import annotations

from ..synth import Loop, OneShot, Patch
from ._common import MID, loop_harmonics, noise, tone
from ._registry import register

BASS_FINGER = register("bass_finger", Patch(
    "FingerBass", (tone((1.0, 1.0, 6.0), (2.0, 0.35, 9.0), (3.0, 0.12, 12.0)),),
    OneShot(0.80), pitched=True, attack_ms=5.0, peak=0.9, rate_note=MID, shift=-12, volume=58),
    "指弾きのエレキベース。丸い基音と少しの倍音。")

BASS_SLAP = register("bass_slap", Patch(
    "SlapBass", (tone((1.0, 1.0, 5.0), (2.0, 0.5, 7.0), (3.0, 0.35, 10.0), (4.0, 0.25, 14.0), (6.0, 0.15, 20.0)),
                 noise(weight=0.15, decay=200.0, hp=True)),
    OneShot(0.60), pitched=True, saturate=1.3, rate_note=MID, shift=-12, volume=56),
    "スラップ／明るいフィンガーのベース（city-pop・funk）。高次倍音とアタックのクリック。")

BASS_PICK = register("bass_pick", Patch(
    "PickBass", (tone((1.0, 1.0, 5.0), (2.0, 0.45, 8.0), (3.0, 0.3, 11.0), (4.0, 0.15, 15.0)),
                 noise(weight=0.1, decay=500.0, hp=True)),
    OneShot(0.70), pitched=True, saturate=1.2, rate_note=MID, shift=-12, volume=58),
    "ピック弾きのロック・ベース（8分で刻む）。")

BASS_SYNTH_SAW = register("bass_synth_saw", Patch(
    "SawBass", loop_harmonics(3, tuple((h, 1.0 / h) for h in range(1, 9))),
    Loop(190, attack_samples=20), pitched=True, rate_note=MID, shift=-12, volume=54),
    "ノコギリ波のシンセベース（ループ。edm・synthwave・dark-tense）。")

BASS_SYNTH_SQUARE = register("bass_synth_square", Patch(
    "SquareBass", loop_harmonics(3, ((1, 1.0), (3, 1 / 3), (5, 1 / 5), (7, 1 / 7))),
    Loop(190, attack_samples=16), pitched=True, rate_note=MID, shift=-12, volume=52),
    "矩形波のシンセベース（ループ。techno の短いベース）。")

BASS_DEEP = register("bass_deep", Patch(
    "DeepBass", loop_harmonics(3, ((1, 1.0), (2, 0.2))),
    Loop(190, attack_samples=30), pitched=True, rate_note=MID, shift=-12, volume=58),
    "ディープハウスの丸いベース（正弦＋わずかな第2倍音のループ）。")

BASS_DIST = register("bass_dist", Patch(
    "DistBass", loop_harmonics(3, tuple((h, 1.0 / h) for h in range(1, 9))),
    Loop(190, attack_samples=20), pitched=True, saturate=3.0, rate_note=MID, shift=-12, volume=50),
    "強く歪ませたノコギリ波の持続ベース（インダストリアル。明るい低音）。")
