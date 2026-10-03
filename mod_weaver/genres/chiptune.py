"""chiptune（旧 genres/chiptune.py の宣言を機械変換したもの。DESIGN.md §6）。"""
from __future__ import annotations

from ..core.composer import RhythmMotif, ScaleRules
from ..core.model import ChordSpec, GmVoice
from ..core.synth_presets import PRESETS
from ..framework.gens import BassLine, Groove, Lead, hits
from ..framework.genre import Genre, Harmony, Instrument, Kit, Part, Section
from ..framework.context import Generator, MeasureCtx
from ..core.pitch import CHORD_QUALITIES
from ..framework.score import Arpeggio
from ..framework.registry import register_genre

C = ChordSpec


def _inst(key: str, gm: GmVoice, **changes) -> Instrument:
    patch = PRESETS[key]
    if changes:
        import dataclasses
        patch = dataclasses.replace(patch, **changes)
    return Instrument(patch=patch, gm=gm)

GROOVES = {
    "main": hits("kick", (0, 6, 8), 52) + hits("snare", (4, 12), 46) + hits("hat", (2, 10, 14), 26, 0.8),
    "drive": hits("kick", (0, 3, 6, 8, 11), 52) + hits("snare", (4, 12), 48) + hits("hat", (2, 6, 10, 14), 26),
    "fill": hits("snare", (8, 10, 12, 13, 14, 15), 44),
}
LEAD_MOTIFS = {
    "verse": (RhythmMotif(rows=(0, 2, 4, 6, 8, 12)), RhythmMotif(rows=(0, 3, 6, 8, 10, 12)), RhythmMotif(rows=(0, 2, 4, 8, 10, 14))),
    "chorus": (RhythmMotif(rows=(0, 2, 3, 4, 6, 8, 10, 12, 14)), RhythmMotif(rows=(0, 4, 6, 8, 12, 14)), RhythmMotif(rows=(0, 1, 2, 4, 8, 9, 10, 12))),
}
PROGRESSIONS = (
    ("I-V-vi-IV", (C(0, "maj", label="I"), C(7, "maj", label="V"), C(9, "min", label="vi"), C(5, "maj", label="IV"))),
    ("vi-IV-I-V", (C(9, "min", label="vi"), C(5, "maj", label="IV"), C(0, "maj", label="I"), C(7, "maj", label="V"))),
    ("I-bVII-IV-I", (C(0, "maj", label="I"), C(10, "maj", label="bVII"), C(5, "maj", label="IV"), C(0, "maj", label="I"))),
    ("IV-V-iii-vi", (C(5, "maj", label="IV"), C(7, "maj", label="V"), C(4, "min", label="iii"), C(9, "min", label="vi"))),
)


JUMP_STEP = 12                                 # 区間の最後の小節でジャンプ音を鳴らす step


class PulseChord(Generator):
    """パルス波の和音: 和音の変わり目と 8 step 目に鳴らし直し、その間 Arpeggio で（1 step の中で3音を切り替える）。
    旧版は 0xy と音量が同じセルに書けないので、鳴らし直す音は既定音量だった（vel=None）。"""

    def __init__(self, inst: str) -> None:
        self.inst = inst

    def measure(self, m: MeasureCtx) -> None:
        q = CHORD_QUALITIES[m.m.quality]
        for step in range(0, m.m.steps, 8):
            m.note(step, self.inst, m.m.chord.harmony, arts=(Arpeggio(q[1], q[2], steps=min(8, m.m.steps - step)),))


class ChipDrums(Groove):
    """ノイズチャンネルの打楽器の型に、区間の終わりのジャンプ音を足す。"""

    def measure(self, m: MeasureCtx) -> None:
        super().measure(m)
        if m.plan.section.fill and m.is_last:
            m.note(JUMP_STEP, "jump", vel=40)


@register_genre
class ChiptuneGenre(Genre):
    id = "chiptune"
    category = "style"
    display_name = "Chiptune (8-bit)"
    description = "8bit ゲーム音楽風。パルス波の旋律とアルペジオ、三角波のベース、ノイズの打楽器とジャンプ音"
    description_en = "8-bit chiptune style: pulse-wave melody and arpeggios, triangle bass, noise drums and jump sounds"
    title = "8-Bit Stage 1"
    tempo_choices = (140, 146, 152, 158, 164, 170)

    instruments = {
        "lead": _inst("chip_pulse25", GmVoice(program=80)),
        "arp": _inst("chip_pulse12", GmVoice(program=80)),
        "bass": _inst("chip_triangle", GmVoice(program=38)),
        "kick": _inst("chip_kick", GmVoice(drum_note=36)),
        "snare": _inst("chip_snare", GmVoice(drum_note=38)),
        "hat": _inst("chip_hat", GmVoice(drum_note=42)),
        "jump": _inst("fx_jump", GmVoice(program=98)),
    }
    harmony = Harmony(keys=(0, 2, 5, 7, 9), mode="ionian", progressions=PROGRESSIONS, n_progressions=3)
    sections = {
        "intro": Section(intensity=0.8, parts=frozenset({"bass", "drums", "arp"}), fill=True),
        "a": Section(intensity=0.85, parts=frozenset({"lead", "bass", "drums", "arp"}), fill=True),
        "b": Section(prog=1, intensity=0.95, parts=frozenset({"lead", "bass", "drums", "arp"}), groove="drive", fill=True, motifs="chorus"),
        "bridge": Section(prog=2, intensity=0.7, parts=frozenset({"lead", "bass", "arp"})),
        "outro": Section(intensity=0.8, parts=frozenset({"bass", "drums", "arp"}), fill=True),
    }
    form = ("intro", "a", "a", "b", "a", "bridge", "b", "a", "outro")
    parts = (
        Part("lead", Lead("lead", ScaleRules(leap_probability=0.3, leap_semitones=(3, 4, 5, 7, 12)), LEAD_MOTIFS,
                   vol=42, gate=0.8, vibrato=0x33), pan=128),
        Part("arp", PulseChord("arp"), pan=128),
        Part("bass", BassLine("bass", kind="octave8", vol=54), pan=128),
        Part("drums", ChipDrums(GROOVES), pan=128,
             kit=Kit(groups=(("noise", ("kick", "snare", "hat", "jump")),),
                     priority={"snare": 3, "kick": 2})),
    )
    mod_channels = {4: 1}
    channel_cap = 4          # 厚くしないことがジャンルの性格（どの形式でも4チャンネル）
