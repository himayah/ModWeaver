"""jpop-80s（旧 genres/jpop_80s.py の宣言を機械変換したもの。DESIGN.md §6）。"""
from __future__ import annotations

from ..core.composer import RhythmMotif, ScaleRules
from ..core.model import ChordSpec, GmVoice
from ..core.synth_presets import PRESETS
from ..framework.gens import BassLine, Comp, Echo, Groove, Layer, Lead, hits
from ..framework.genre import Genre, Harmony, Instrument, Kit, Part, Section
from ..framework.context import Generator, MeasureCtx
from ..core.pitch import CHORD_QUALITIES
from ..framework.registry import register_genre

C = ChordSpec


def _inst(key: str, gm: GmVoice, **changes) -> Instrument:
    patch = PRESETS[key]
    if changes:
        import dataclasses
        patch = dataclasses.replace(patch, **changes)
    return Instrument(patch=patch, gm=gm)

GROOVES = {
    "main": hits("kick", (0, 8, 10), 58) + hits("snare", (4, 12), 54) + hits("hat", (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15), 22, 0.9) + hits("tamb", (4, 12), 26),
    "fill": hits("snare", (8, 10, 12, 13, 14, 15), 50),
    "crash": hits("crash", (0,), 56),
}
LEAD_MOTIFS = {
    "verse": (RhythmMotif(rows=(0, 2, 4, 6, 8, 12)), RhythmMotif(rows=(0, 4, 6, 8, 10, 12))),
    "chorus": (RhythmMotif(rows=(0, 2, 4, 8, 10, 12, 14)), RhythmMotif(rows=(0, 4, 6, 8, 12)), RhythmMotif(rows=(0, 2, 6, 8, 12))),
}
PROGRESSIONS = (
    ("IVmaj7-V7-iii7-vi", (C(5, "maj7", label="IVmaj7"), C(7, "dom7", label="V7"), C(4, "m7", label="iii7"), C(9, "min", label="vi"))),
    ("I-V-vi-iii", (C(0, "maj", label="I"), C(7, "maj", label="V"), C(9, "min", label="vi"), C(4, "min", label="iii"))),
    ("ii7-V7-Imaj7-vi7", (C(2, "m7", label="ii7"), C(7, "dom7", label="V7"), C(0, "maj7", label="Imaj7"), C(9, "m7", label="vi7"))),
)


KIME = (0, 3, 6)                               # ブラスの「決め」（イントロ・サビ頭）


class BrassKime(Generator):
    """シンセブラス: サビ・イントロの頭は「決め」（短い3連打）、それ以外は和音の変わり目に伸ばす（旧 pad）。"""

    def __init__(self, inst: str, vol: int) -> None:
        self.inst = inst
        self.vol = vol

    def measure(self, m: MeasureCtx) -> None:
        chord = m.m.chord
        shape = CHORD_QUALITIES[m.m.quality]
        vol = m.scale_drum(40)
        if m.plan.section.crash and m.m.index == 0:
            for i, step in enumerate(KIME):
                m.note(step, self.inst, chord.harmony, vel=vol, chord=shape,
                       dur=2 if i == len(KIME) - 1 else None)
        elif m.is_chord_change:
            m.note(0, self.inst, chord.harmony, vel=max(1, vol - 6), chord=shape)


@register_genre
class Jpop80sGenre(Genre):
    id = "jpop-80s"
    category = "style"
    display_name = "80s J-Pop"
    description = "80年代 J-POP 風。明るいコードと都会的なブラス、軽快なビートと最後のサビの転調"
    description_en = "80s J-pop style: bright chords, city brass, a light beat and a final key change"
    title = "J-Pop 80s"
    tempo_choices = (120, 124, 128, 132, 136)

    instruments = {
        "kick": _inst("drum_pop_kick", GmVoice(drum_note=36)),
        "snare": _inst("drum_gated_snare", GmVoice(drum_note=40)),
        "hat": _inst("nostalgic_hihat", GmVoice(drum_note=42)),
        "tamb": _inst("perc_tambourine", GmVoice(drum_note=54)),
        "crash": _inst("march_crash_cymbal", GmVoice(drum_note=49)),
        "bass": _inst("bass_finger", GmVoice(program=33)),
        "lead": _inst("syn_square_lead", GmVoice(program=80)),
        "line": _inst("orch_violin", GmVoice(program=48), volume=30),
        "ep": _inst("keys_ep", GmVoice(program=4)),
        "brass": _inst("syn_poly_pad", GmVoice(program=62), name="BrassPad"),
    }
    harmony = Harmony(keys=(0, 2, 4), mode="ionian", progressions=PROGRESSIONS, n_progressions=3)
    sections = {
        "intro": Section(intensity=0.9, parts=frozenset({"pad", "bass", "drums", "comp"}), fill=True, crash=True),
        "a": Section(prog=1, intensity=0.7, parts=frozenset({"lead", "bass", "drums", "comp"})),
        "b": Section(prog=2, intensity=0.8, parts=frozenset({"bass", "drums", "comp", "pad", "lead"}), fill=True),
        "sabi": Section(intensity=1.0, parts=frozenset({"bass", "drums", "comp", "pad", "lead"}), fill=True, crash=True, motifs="chorus"),
        "interlude": Section(intensity=0.8, parts=frozenset({"pad", "bass", "drums", "comp"})),
        "sabi_up": Section(intensity=1.0, parts=frozenset({"bass", "drums", "comp", "pad", "lead"}), key_offset=2, crash=True, motifs="chorus"),
        "outro": Section(intensity=0.8, parts=frozenset({"pad", "bass", "drums", "comp"}), key_offset=2, crash=True),
    }
    form = ("intro", "a", "b", "sabi", "interlude", "a", "b", "sabi", "sabi_up", "outro")
    parts = (
        Part("drums", Groove(GROOVES), pan=128,
             kit=Kit(groups=(("kick/snare", ("kick", "snare")), ("hat", ("hat", "tamb", "crash"))),
                     priority={"snare": 2, "crash": 3, "tamb": 2},
                     single_priority={"kick": 3, "snare": 4, "hat": 1, "tamb": 2, "crash": 2},
                     group_pan={"hat": 164})),
        Part("bass", BassLine("bass", kind="octave8", vol=54), pan=128),
        Part("comp", Comp("ep", kind="half", vol=40), pan=84),
        Part("lead", Lead("lead", ScaleRules(leap_semitones=(3, 4, 5, 7)), LEAD_MOTIFS,
                   vol=46, gate=0.8, vibrato=0x33), pan=172),
        Part("pad", BrassKime("brass", vol=38), pan=56, min_channels=6),
        Part("lead echo", Echo(delay=3, ratio=0.45), follow="lead", pan=96, min_channels=8),
        Part("strings", Layer("line", vol=26, register=(19, 31)), follow="lead", pan=160, min_channels=8),
    )
    mod_channels = {4: 1, 6: 2, 8: 1}
