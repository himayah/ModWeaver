"""パッドと声（第３段階の共有音色。DESIGN.md §4.5）。息のノイズは入れずデチューンのうなりで表す（§4.5）。"""
from __future__ import annotations

from ..synth import Loop, Patch
from ._common import MID, loop_harmonics
from ._registry import register

PAD_GLASS = register("pad_glass", Patch(
    "GlassPad", loop_harmonics(120, ((1, 1.0), (2, 0.5), (4, 0.35), (6, 0.2)), detune=0.6),
    Loop(3800, attack_samples=800), pitched=True, rate_note=MID, volume=34),
    "透明感のあるガラスのようなパッド（高い倍音＋うなり）。")

PAD_WARM = register("pad_warm", Patch(
    "WarmPad", loop_harmonics(120, ((1, 1.0), (2, 0.35), (3, 0.15)), detune=0.8),
    Loop(3800, attack_samples=800), pitched=True, rate_note=MID, volume=36),
    "温かいアナログ・パッド（nostalgic_pad の音程を直した版。K=120/L=3800）。")

VOX_OOH = register("vox_ooh", Patch(
    "VoxOoh", loop_harmonics(120, ((1, 1.0), (2, 0.5), (3, 0.15), (4, 0.05)), detune=0.5),
    Loop(3800, attack_samples=300), pitched=True, rate_note=MID, volume=42),
    "「ウー」という声のような旋律音色（歌もののリード）。")

VOX_CHOIR = register("vox_choir", Patch(
    "Choir", loop_harmonics(120, ((1, 0.8), (2, 0.6), (3, 0.9), (4, 0.5), (5, 0.3), (6, 0.2)), detune=0.7),
    Loop(3800, attack_samples=900), pitched=True, rate_note=MID, volume=38),
    "「アー」という合唱のパッド（cinematic・trailer）。")
