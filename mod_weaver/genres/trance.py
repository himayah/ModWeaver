"""trance（トランス。NEW_GENRES_DESIGN.md §14.1）。

136〜142 BPM の4つ打ち、16分の転がるオフビートのベース、3-3-2 のトランスゲート・パッド、長いブレイク（パッド＋旋律）の後に
ビルドアップからドロップへ。edm（124〜130・短い溜め）・uplifting との違いは、速さ・ゲートのパッド・長い break。
"""
from __future__ import annotations

from ..core.composer import RhythmMotif, ScaleRules
from ..core.model import ChordSpec, GmVoice
from ..core.pitch import CHORD_QUALITIES
from ..framework.context import Generator, MeasureCtx
from ..framework.gens import Arp, BassLine, Buildup, Echo, Groove, Lead, Pad, hits
from ..framework.genre import Genre, Harmony, Kit, Part, Section, Sidechain
from ..framework.registry import register_genre
from ._ornament import inst as _inst

C = ChordSpec

GROOVES = {
    "main": hits("kick", (0, 4, 8, 12), 62) + hits("clap", (4, 12), 46) + hits("ohat", (2, 6, 10, 14), 34)
            + hits("hat", (1, 3, 5, 7, 9, 11, 13, 15), 14, 0.8),
    "intro": hits("kick", (0, 4, 8, 12), 56) + hits("ohat", (2, 6, 10, 14), 28),
}
LEAD_MOTIFS = {
    "verse": (RhythmMotif(rows=(0, 3, 6, 8, 11, 12)), RhythmMotif(rows=(0, 2, 4, 6, 8, 10, 12, 14)),
              RhythmMotif(rows=(0, 4, 6, 8, 12))),
    "break": (RhythmMotif(rows=(0, 8)), RhythmMotif(rows=(0, 6, 8, 12)), RhythmMotif(rows=(0, 4, 8, 12))),
}
PROGRESSIONS = (
    ("i-VI-III-VII", (C(0, "min", label="i"), C(8, "maj", label="VI"), C(3, "maj", label="III"), C(10, "maj", label="VII"))),
    ("VI-VII-i-i", (C(8, "maj", label="VI"), C(10, "maj", label="VII"), C(0, "min", label="i"), C(0, "min", label="i"))),
    ("i-VII-VI-VII", (C(0, "min", label="i"), C(10, "maj", label="VII"), C(8, "maj", label="VI"), C(10, "maj", label="VII"))),
)
GATE_STEPS = (0, 3, 6, 8, 11, 14)                # 3-3-2 のゲート


class BuildupDrums(Groove):
    """通常は打楽器の型。build はスネアのビルドアップ（edm と同じ）。"""

    def __init__(self, grooves, **kw) -> None:
        super().__init__(grooves, **kw)
        self.buildup = Buildup("snare")

    def measure(self, m: MeasureCtx) -> None:
        if m.plan.kind == "build":
            self.buildup.measure(m)
        else:
            super().measure(m)


class GatePad(Generator):
    """トランスゲート: 和音（スーパーソウ）を 3-3-2 で切って鳴らす。"""

    inst = "gate"

    def measure(self, m: MeasureCtx) -> None:
        shape = CHORD_QUALITIES[m.m.quality]
        for i, step in enumerate(GATE_STEPS):
            m.note(step, "gate", m.m.chord.harmony, vel=m.scale_vol(36 if i % 3 == 0 else 28), chord=shape, dur=2)


class RiserImpact(Generator):
    def measure(self, m: MeasureCtx) -> None:
        if m.plan.kind == "build" and m.m.index % 4 == 2:
            m.note(0, "riser", vel=48)
        elif m.plan.kind == "drop" and m.m.index == 0:
            m.note(0, "impact", vel=56)


def _sec(parts, *, prog=0, intensity=0.8, measures=8, groove="main", motifs="verse", kind="") -> Section:
    return Section(prog=prog, measures=measures, intensity=intensity, parts=frozenset(parts), groove=groove,
                   motifs=motifs, kind=kind)


@register_genre
class TranceGenre(Genre):
    id = "trance"
    category = "genre"
    display_name = "Trance"
    description = "トランス。136〜142 BPM の4つ打ち、転がるベース、3-3-2 のゲート・パッド、長いブレイクからのドロップ"
    description_en = "Trance: 136-142 BPM four-on-the-floor, rolling bass, 3-3-2 gated pads, a long breakdown into the drop"
    title = "Trance Journey"
    tempo_choices = (136, 138, 140, 142)

    instruments = {
        "kick": _inst("drum_909_kick", GmVoice(drum_note=36)),
        "clap": _inst("fb_clap", GmVoice(drum_note=39)),
        "ohat": _inst("drum_909_open_hat", GmVoice(drum_note=46)),
        "hat": _inst("drum_909_hat", GmVoice(drum_note=42)),
        "snare": _inst("drum_pop_snare", GmVoice(drum_note=38)),
        "bass": _inst("bass_synth_saw", GmVoice(program=38)),
        "gate": _inst("fb_supersaw", GmVoice(program=90), name="TranceGate", volume=34),
        "pad": _inst("syn_poly_pad", GmVoice(program=89)),
        "lead": _inst("syn_saw_lead", GmVoice(program=81)),
        "pluck": _inst("syn_pluck", GmVoice(program=84), volume=30),
        "riser": _inst("fx_riser", GmVoice(program=97)),
        "impact": _inst("fx_impact", GmVoice(program=55)),
    }
    harmony = Harmony(keys=(9, 4, 2, 7), mode="aeolian", progressions=PROGRESSIONS, n_progressions=2)
    sections = {
        "intro": _sec({"drums", "bass", "pad"}, intensity=0.55, groove="intro"),
        "break": _sec({"pad", "lead", "arp"}, prog=1, intensity=0.5, measures=16, motifs="break"),
        "build": _sec({"drums", "pad", "gate", "fx"}, intensity=0.85, kind="build"),
        "drop": _sec({"drums", "bass", "gate", "lead", "arp", "fx"}, intensity=1.0, measures=16, kind="drop"),
        "outro": _sec({"drums", "bass", "pad"}, intensity=0.5, groove="intro"),
    }
    form = ("intro", "break", "build", "drop", "break", "build", "drop", "outro")
    parts = (
        Part("drums", BuildupDrums(GROOVES), pan=128,
             kit=Kit(groups=(("kick", ("kick",)), ("clap/hat", ("clap", "ohat", "hat", "snare"))),
                     priority={"snare": 3, "clap": 2, "ohat": 1},
                     single_priority={"kick": 4, "clap": 3, "ohat": 1, "hat": 1, "snare": 4},
                     group_pan={"clap/hat": 150})),
        Part("bass", BassLine("bass", kind="offbeat", vol=54), pan=128),
        Part("pad", Pad("pad", vol=32), pan=88),
        Part("gate", GatePad(), pan=100, min_channels=6),
        Part("lead", Lead("lead", ScaleRules(leap_probability=0.25, leap_semitones=(3, 5, 7)), LEAD_MOTIFS,
                          vol=46, gate=0.8), pan=168),
        Part("fx", RiserImpact(), pan=128, min_channels=6),
        Part("arp", Arp("pluck", register=(24, 35), steps=tuple(range(16)), vol=26), pan=160, min_channels=8),
        Part("lead echo", Echo(delay=3, ratio=0.4), follow="lead", pan=96, min_channels=8),
    )
    mod_channels = {4: 1, 6: 2, 8: 1}
    mix = (Sidechain(triggers=("kick",), targets=("bass",), ratio=0.25, release_steps=2),
           Sidechain(triggers=("kick",), targets=("gate", "pad"), ratio=0.35, release_steps=3))
