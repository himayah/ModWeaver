"""lofi-hiphop（旧 genres/lofi_hiphop.py の宣言を機械変換したもの。DESIGN.md §6）。"""
from __future__ import annotations

from ..core.composer import RhythmMotif, ScaleRules
from ..core.model import ChordSpec, GmVoice
from ..core.synth_presets import PRESETS
from ..framework.gens import BassLine, Comp, Echo, Fx, Groove, Layer, Lead, hits
from ..framework.genre import Genre, Harmony, Instrument, Kit, Part, Section
from ..framework.plan import Meter, Swing
from ..framework.registry import register_genre

C = ChordSpec


def _inst(key: str, gm: GmVoice, **changes) -> Instrument:
    patch = PRESETS[key]
    if changes:
        import dataclasses
        patch = dataclasses.replace(patch, **changes)
    return Instrument(patch=patch, gm=gm)

GROOVES = {
    "main": hits("kick", (0, 7, 10), 60) + hits("snare", (4, 12), 50) + hits("hat", (0, 2, 4, 6, 8, 10, 12, 14), 24) + hits("hat", (3, 11), 14, 0.4),
}
LEAD_MOTIFS = {
    "verse": (RhythmMotif(rows=(0, 3, 6, 10)), RhythmMotif(rows=(2, 4, 8, 12)), RhythmMotif(rows=(0, 6, 8, 11, 14))),
}
PROGRESSIONS = (
    ("ii9-V13-Imaj9-vi7", (C(2, "m9", label="ii9"), C(7, "dom13", label="V13"), C(0, "maj9", label="Imaj9"), C(9, "m7", label="vi7"))),
    ("Imaj7-iii7-vi7-IVmaj7", (C(0, "maj7", label="Imaj7"), C(4, "m7", label="iii7"), C(9, "m7", label="vi7"), C(5, "maj7", label="IVmaj7"))),
    ("IVmaj9-iii7-ii9-Imaj9", (C(5, "maj9", label="IVmaj9"), C(4, "m7", label="iii7"), C(2, "m9", label="ii9"), C(0, "maj9", label="Imaj9"))),
)


@register_genre
class LofiHiphopGenre(Genre):
    id = "lofi-hiphop"
    display_name = "Lo-fi Hip Hop"
    description = "ローファイ・ヒップホップ。よれたビート、ジャジーなエレピ、レコードのノイズ"
    description_en = "Lo-fi hip hop: swung beats, jazzy electric piano and vinyl noise"
    title = "Lo-fi Study Beat"
    tempo_choices = (72, 76, 80, 84, 88)

    instruments = {
        "kick": _inst("drum_boombap_kick", GmVoice(drum_note=36)),
        "snare": _inst("drum_boombap_snare", GmVoice(drum_note=38)),
        "hat": _inst("nostalgic_hihat", GmVoice(drum_note=42)),
        "bass": _inst("bass_finger", GmVoice(program=33)),
        "lead": _inst("swing_sax_lead", GmVoice(program=65), volume=38),
        "vinyl": _inst("fx_vinyl", GmVoice(program=122)),
        "padline": _inst("pad_warm", GmVoice(program=89), volume=30),
        "ep": _inst("keys_ep", GmVoice(program=4)),
    }
    harmony = Harmony(keys=(2, 5, 9, 0), mode="ionian", progressions=PROGRESSIONS, n_progressions=2)
    sections = {
        "intro": Section(intensity=0.4, parts=frozenset({"comp", "fx"})),
        "a": Section(intensity=0.7, parts=frozenset({"comp", "lead", "fx", "drums", "bass"})),
        "b": Section(prog=1, intensity=0.7, parts=frozenset({"comp", "lead", "fx", "drums", "bass"})),
        "outro": Section(intensity=0.4, parts=frozenset({"comp", "bass", "fx"})),
    }
    form = ("intro", "a", "a", "b", "a", "outro")
    parts = (
        Part("drums", Groove(GROOVES), pan=128,
             kit=Kit(groups=(("kick/snare", ("kick", "snare")), ("hat", ("hat",))),
                     priority={"snare": 2},
                     single_priority={"kick": 3, "snare": 4, "hat": 1},
                     group_pan={"hat": 164})),
        Part("bass", BassLine("bass", kind="boombap", vol=56), pan=128),
        Part("comp", Comp("ep", kind="charleston", vol=42, wobble=34), pan=90),
        Part("lead", Lead("lead", ScaleRules(leap_probability=0.2, leap_semitones=(3, 4, 5), dissonance_weight=0.1), LEAD_MOTIFS,
                   vol=40, gate=0.8), pan=170),
        Part("fx", Fx("vinyl", every=2, vol=22), pan=128, min_channels=6),
        Part("lead echo", Echo(delay=3, ratio=0.45), follow="lead", pan=96, min_channels=8),
        Part("pad layer", Layer("padline", vol=24, register=(19, 31)), follow="lead", pan=160, min_channels=8),
    )
    swing = Swing(7, 5)
    mod_channels = {4: 1, 6: 2, 8: 1}
