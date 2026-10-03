"""focus（旧 genres/focus.py の宣言を機械変換したもの。FRAMEWORK_REDESIGN.md §15）。"""
from __future__ import annotations

from ..core.model import ChordSpec, GmVoice
from ..core.synth_presets import PRESETS
from ..framework.gens import BassLine, Comp, Fx, Groove, hits
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
    "main": hits("kick", (0, 7, 10), 58) + hits("snare", (4, 12), 48) + hits("hat", (0, 2, 4, 6, 8, 10, 12, 14), 22),
    "sparse": hits("kick", (0, 7, 10), 58) + hits("snare", (4, 12), 48) + hits("hat", (0, 4, 8, 12), 22),
    "nokick": hits("snare", (4, 12), 44) + hits("hat", (0, 2, 4, 6, 8, 10, 12, 14), 22),
}
PROGRESSIONS = (
    ("im7-IVmaj7", (C(0, "m7", label="im7"), C(5, "maj7", label="IVmaj7"))),
    ("ii7-V7", (C(2, "m7", label="ii7"), C(7, "dom7", label="V7"))),
    ("Imaj7-vi7", (C(0, "maj7", label="Imaj7"), C(9, "m7", label="vi7"))),
)


@register_genre
class FocusGenre(Genre):
    id = "focus"
    category = "mood"
    display_name = "Focus"
    description = "集中。ほとんど変化しないローファイのループと一定のテンポ"
    description_en = "Focus: minimal lo-fi loop with a steady, unchanging groove"
    title = "Focus Loop"
    tempo_choices = (78, 80, 82, 84, 86)

    instruments = {
        "kick": _inst("drum_boombap_kick", GmVoice(drum_note=36)),
        "snare": _inst("drum_boombap_snare", GmVoice(drum_note=38)),
        "hat": _inst("nostalgic_hihat", GmVoice(drum_note=42)),
        "bass": _inst("bass_finger", GmVoice(program=33)),
        "vinyl": _inst("fx_vinyl", GmVoice(program=122)),
        "ep": _inst("keys_ep", GmVoice(program=4)),
    }
    harmony = Harmony(keys=(2, 4), mode="dorian", progressions=PROGRESSIONS, n_progressions=1)
    sections = {
        "intro": Section(intensity=0.5, parts=frozenset({"comp", "fx"})),
        "loop": Section(intensity=0.7, parts=frozenset({"comp", "bass", "drums", "fx"}), groove="sparse"),
        "loop2": Section(intensity=0.7, parts=frozenset({"comp", "bass", "drums", "fx"})),
        "loop_b": Section(intensity=0.7, parts=frozenset({"comp", "bass", "drums", "fx"}), groove="nokick"),
        "outro": Section(intensity=0.5, parts=frozenset({"comp", "fx"})),
    }
    form = ("intro", "loop", "loop", "loop2", "loop2", "loop", "loop_b", "loop_b", "loop2", "loop2", "loop", "loop", "outro")
    parts = (
        Part("drums", Groove(GROOVES), pan=128,
             kit=Kit(groups=(("drums", ("kick", "snare", "hat")),),
                     priority={"snare": 3, "kick": 2})),
        Part("bass", BassLine("bass", kind="boombap", vol=52), pan=128),
        Part("comp", Comp("ep", kind="half", vol=40, wobble=34), pan=128),
        Part("fx", Fx("vinyl", every=2, vol=22), pan=128),
    )
    swing = Swing(7, 5)
    mod_channels = {4: 1}
