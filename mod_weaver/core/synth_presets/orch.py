"""管・弦（第３段階の共有音色。DESIGN.md §12.4）。既存の orch_*・march_brass_* と組み合わせて使う。"""
from __future__ import annotations

from ..synth import Loop, OneShot, Patch
from ._common import MID, loop_harmonics, noise, tone
from ._registry import register

WIND_FLUTE = register("wind_flute", Patch(
    "Flute", loop_harmonics(120, ((1, 1.0), (3, 0.2), (5, 0.05)), detune=0.3),
    Loop(3800, attack_samples=200), pitched=True, rate_note=MID, volume=44),
    "フルート／ホイッスル（nostalgic_flute の音程を直した版）。")

STR_SPICCATO = register("str_spiccato", Patch(
    "Spiccato", (tone((1.0, 1.0, 14.0), (2.0, 0.6, 16.0), (3.0, 0.4, 18.0), (4.0, 0.3, 22.0), (5.0, 0.2, 26.0)),
                 noise(weight=0.1, decay=60.0, hp=True)),
    OneShot(0.18), pitched=True, rate_note=MID, volume=46),
    "弓を弾ませる短い弦（16分の刻み。trailer・anime-ost）。")

BRASS_BRAAM = register("brass_braam", Patch(
    "Braam", (tone((1.0, 1.0, 1.2), (2.0, 0.8, 1.4), (3.0, 0.6, 1.6), (4.0, 0.5, 2.0), (1.007, 0.8, 1.2)),),
    OneShot(2.0), pitched=True, attack_ms=60.0, saturate=2.4, rate_note=MID, shift=-24, volume=60),
    "映画予告編の低い金管の「ブラーム」（強く飽和させた低音クラスタ）。")
