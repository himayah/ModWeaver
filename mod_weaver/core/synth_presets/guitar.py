"""ギター（第３段階の共有音色。DESIGN.md §12.4）。ストロークは profiles/band_common.chord_patch(strum=True)。"""
from __future__ import annotations

from ..synth import OneShot, Patch
from ._common import MID, noise, tone
from ._registry import register

GTR_ACOUSTIC = register("gtr_acoustic", Patch(
    "AcousticGtr", (tone((1.0, 1.0, 3.5), (2.0, 0.6, 5.0), (3.0, 0.4, 6.5), (4.0, 0.25, 8.0), (5.0, 0.15, 10.0),
                         (6.0, 0.1, 12.0)), noise(weight=0.08, decay=400.0, hp=True)),
    OneShot(1.20), pitched=True, peak=0.9, rate_note=MID, volume=44),
    "スチール弦のアコースティック・ギター。明るい倍音とピックの擦れ。")

GTR_NYLON = register("gtr_nylon", Patch(
    "NylonGtr", (tone((1.0, 1.0, 3.0), (2.0, 0.4, 4.5), (3.0, 0.2, 6.0), (4.0, 0.1, 8.0)),),
    OneShot(1.30), pitched=True, attack_ms=3.0, peak=0.9, rate_note=MID, volume=44),
    "ナイロン弦（ガット）ギター。柔らかい倍音（bossa・lo-fi）。")

GTR_CLEAN_CUT = register("gtr_clean_cut", Patch(
    "CuttingGtr", (tone((1.0, 1.0, 30.0), (2.0, 0.6, 35.0), (3.0, 0.4, 40.0), (4.0, 0.25, 50.0)),
                   noise(weight=0.2, decay=150.0, hp=True)),
    OneShot(0.12), pitched=True, rate_note=MID, volume=40),
    "カッティング用のミュートしたクリーン・ギター（16分で刻む短い音）。")

GTR_CLEAN_ARP = register("gtr_clean_arp", Patch(
    "CleanGtr", (tone((1.0, 1.0, 2.5), (2.0, 0.5, 3.5), (3.0, 0.35, 4.5), (4.0, 0.2, 6.0), (5.0, 0.1, 8.0)),),
    OneShot(1.50), pitched=True, peak=0.9, rate_note=MID, volume=42),
    "鳴り響くクリーン・ギター（アルペジオ用の長い余韻）。")

GTR_CRUNCH = register("gtr_crunch", Patch(
    "CrunchGtr", (tone((1.0, 1.0, 4.0), (1.5, 0.8, 5.0), (2.0, 0.6, 5.0), (3.0, 0.35, 7.0)),),
    OneShot(0.60), pitched=True, saturate=2.2, rate_note=MID, volume=46),
    "軽く歪ませたパワーコード（root＋5度＋オクターブを1サンプルに）。")
