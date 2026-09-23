"""Nostalgic のサンプル合成。

旧 twilight_pad.py の gen_* を core/synth.py の Patch 方式へ移行済み（core/synth_presets.py 参照）。
式・定数は移行前と同一（peak, len は数サンプル程度の丸め差のみ。バイト単位の互換性は要求しないため許容。DESIGN_HISTORY.md §4 D15）。
"""
from __future__ import annotations

from ..core import synth, synth_presets
from ..core.model import SampleSpec


def gen_kick() -> SampleSpec:
    """Lo-Fi Warm Kick: 深く温かみのある丸いキック"""
    return synth.render(synth_presets.NOSTALGIC_KICK)


def gen_snare() -> SampleSpec:
    """Nostalgic Soft Snare: 乾いたレトロな質感の柔らかいスネア"""
    return synth.render(synth_presets.NOSTALGIC_SNARE)


def gen_hihat() -> SampleSpec:
    """Closed Hi-Hat: 繊細で小気味よいLo-Fiクローズドハット"""
    return synth.render(synth_presets.NOSTALGIC_HIHAT)


def gen_bass() -> SampleSpec:
    """Warm Mellow Bass: 豊かで丸みのあるアコースティック風ベース (実音 C4基準)"""
    return synth.render(synth_presets.NOSTALGIC_BASS)


def gen_musicbox() -> SampleSpec:
    """Nostalgic Music Box / Chime: 郷愁を誘う澄んだオルゴール/トイチャイム音"""
    return synth.render(synth_presets.NOSTALGIC_MUSICBOX)


def gen_pad() -> SampleSpec:
    """Twilight Ambient Pad: 完全ループ対応の温かいアナログ・ストリングスパッド"""
    return synth.render(synth_presets.NOSTALGIC_PAD)


def gen_flute() -> SampleSpec:
    """Mellow Flute / Lead: 哀愁漂う素朴な木管風リード (完全ループ)"""
    return synth.render(synth_presets.NOSTALGIC_FLUTE)
