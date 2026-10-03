"""uplifting（旧 genres/uplifting.py の宣言を機械変換したもの。DESIGN.md §6）。"""
from __future__ import annotations

from ..core.composer import RhythmMotif, ScaleRules
from ..core.model import ChordSpec, GmVoice
from ..core.synth_presets import PRESETS
from ..framework.gens import Arp, BassLine, Buildup, Echo, Groove, Layer, Lead, Pad, hits
from ..framework.genre import Genre, Harmony, Instrument, Kit, Part, Section, Sidechain
from ..framework.context import Generator, MeasureCtx
from ..framework.registry import register_genre

C = ChordSpec


def _inst(key: str, gm: GmVoice, **changes) -> Instrument:
    patch = PRESETS[key]
    if changes:
        import dataclasses
        patch = dataclasses.replace(patch, **changes)
    return Instrument(patch=patch, gm=gm)

GROOVES = {
    "main": hits("kick", (0, 4, 8, 12), 62) + hits("clap", (4, 12), 44) + hits("ohat", (2, 6, 10, 14), 30),
    "break": hits("ohat", (2, 6, 10, 14), 20),
}
LEAD_MOTIFS = {
    "verse": (RhythmMotif(rows=(0, 3, 6, 8, 12)), RhythmMotif(rows=(0, 2, 4, 8, 10, 12)), RhythmMotif(rows=(0, 6, 8, 14))),
}
PROGRESSIONS = (
    ("I-V-vi-IV", (C(0, "maj", label="I"), C(7, "maj", label="V"), C(9, "min", label="vi"), C(5, "maj", label="IV"))),
    ("vi-IV-I-V", (C(9, "min", label="vi"), C(5, "maj", label="IV"), C(0, "maj", label="I"), C(7, "maj", label="V"))),
    ("IV-V-iii-vi", (C(5, "maj", label="IV"), C(7, "maj", label="V"), C(4, "min", label="iii"), C(9, "min", label="vi"))),
)


class BuildupDrums(Groove):
    """通常は打楽器の型。build の区間ではスネアのビルドアップ（4分→8分→16分→連打と加速し、音量が上がる）。"""

    def __init__(self, grooves, **kw) -> None:
        super().__init__(grooves, **kw)
        self.buildup = Buildup("snare")

    def measure(self, m: MeasureCtx) -> None:
        if m.plan.kind == "build":
            self.buildup.measure(m)
        else:
            super().measure(m)


@register_genre
class UpliftingGenre(Genre):
    id = "uplifting"
    category = "mood"
    display_name = "Uplifting"
    description = "上げていく高揚感。4つ打ちとアルペジオ、明るいスーパーソウのコード"
    description_en = "Uplifting anthem: four-on-the-floor, bright arpeggios and supersaw chords"
    title = "Uplifting Anthem"
    tempo_choices = (128, 130, 132, 134, 136)

    instruments = {
        "kick": _inst("drum_909_kick", GmVoice(drum_note=36)),
        "clap": _inst("fb_clap", GmVoice(drum_note=39)),
        "ohat": _inst("drum_909_open_hat", GmVoice(drum_note=46)),
        "snare": _inst("drum_pop_snare", GmVoice(drum_note=38)),
        "bass": _inst("bass_synth_saw", GmVoice(program=38)),
        "arp": _inst("syn_pluck", GmVoice(program=84)),
        "lead": _inst("syn_saw_lead", GmVoice(program=81)),
        "saw": _inst("fb_supersaw", GmVoice(program=81)),
        "choir": _inst("vox_choir", GmVoice(program=52), volume=30),
    }
    harmony = Harmony(keys=(2, 4, 5), mode="ionian", progressions=PROGRESSIONS, n_progressions=2)
    sections = {
        "intro": Section(intensity=0.5, parts=frozenset({"drums", "arp"})),
        "build": Section(prog=1, intensity=0.7, parts=frozenset({"pad", "arp", "drums"})),
        "drop": Section(intensity=1.0, parts=frozenset({"bass", "drums", "pad", "lead", "arp"})),
        "break": Section(prog=1, intensity=0.5, parts=frozenset({"pad", "drums", "arp"}), groove="break"),
        "outro": Section(intensity=0.5, parts=frozenset({"drums", "arp"})),
    }
    form = ("intro", "build", "drop", "drop", "break", "build", "drop", "drop", "outro")
    parts = (
        Part("drums", BuildupDrums(GROOVES), pan=128,
             kit=Kit(groups=(("kick", ("kick",)), ("clap/hat", ("clap", "ohat", "snare"))),
                     priority={"snare": 3, "clap": 2},
                     single_priority={"kick": 4, "clap": 3, "ohat": 1, "snare": 4},
                     group_pan={"clap/hat": 150})),
        Part("bass", BassLine("bass", kind="offbeat", vol=52), pan=128),
        Part("pad", Pad("saw", vol=34), pan=96),
        Part("arp", Arp("arp", register=(24, 35), steps=(0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15), vol=34), pan=176),
        Part("lead", Lead("lead", ScaleRules(leap_semitones=(4, 5, 7)), LEAD_MOTIFS,
                   vol=44, gate=0.85, vibrato=0x33), pan=64, min_channels=6),
        Part("lead echo", Echo(delay=3, ratio=0.45), follow="lead", pan=96, min_channels=8),
        Part("choir", Layer("choir", vol=26, chordal=True), follow="pad", pan=160, min_channels=8),
    )
    mod_channels = {4: 1, 6: 2, 8: 1}
    mix = (Sidechain(triggers=("kick",), targets=("bass",), ratio=0.3, release_steps=2), Sidechain(triggers=("kick",), targets=("pad",), ratio=0.4, release_steps=3),)
