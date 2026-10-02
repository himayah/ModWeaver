"""edm（旧 genres/edm.py の宣言を機械変換したもの。FRAMEWORK_REDESIGN.md §15）。"""
# TODO(F6): 論理チャンネル ['fx'] を鳴らすパートが宣言に無い（上書きメソッドで鳴らす）
from __future__ import annotations

from ..core.composer import RhythmMotif, ScaleRules
from ..core.model import ChordSpec, GmVoice
from ..core.synth_presets import PRESETS
from ..framework.gens import Arp, BassLine, Echo, Groove, Lead, Pad, hits
from ..framework.genre import Genre, Harmony, Instrument, Kit, Part, Section, Sidechain
from ..framework.registry import register_genre

C = ChordSpec


def _inst(key: str, gm: GmVoice, **changes) -> Instrument:
    patch = PRESETS[key]
    if changes:
        import dataclasses
        patch = dataclasses.replace(patch, **changes)
    return Instrument(patch=patch, gm=gm)

GROOVES = {
    "main": hits("kick", (0, 4, 8, 12), 62) + hits("clap", (4, 12), 48) + hits("hat", (2, 6, 10, 14), 30),
    "intro": hits("kick", (0, 4, 8, 12), 56) + hits("hat", (2, 6, 10, 14), 26),
}
LEAD_MOTIFS = {
    "verse": (RhythmMotif(rows=(0, 3, 6, 8, 11, 12)), RhythmMotif(rows=(0, 2, 4, 6, 8, 12))),
}
PROGRESSIONS = (
    ("VI-iv-i-VII", (C(8, "maj", label="VI"), C(5, "min", label="iv"), C(0, "min", label="i"), C(10, "maj", label="VII"))),
    ("i-VI-III-VII", (C(0, "min", label="i"), C(8, "maj", label="VI"), C(3, "maj", label="III"), C(10, "maj", label="VII"))),
)


@register_genre
class EdmGenre(Genre):
    id = "edm"
    display_name = "EDM"
    description = "EDM。シンセ主体、ビルドアップで溜めてドロップで弾ける"
    description_en = "EDM: synth-driven builds that explode into the drop"
    title = "EDM Drop"
    tempo_choices = (124, 126, 128, 130)

    instruments = {
        "kick": _inst("drum_909_kick", GmVoice(drum_note=36)),
        "clap": _inst("fb_clap", GmVoice(drum_note=39)),
        "hat": _inst("drum_909_hat", GmVoice(drum_note=42)),
        "snare": _inst("drum_pop_snare", GmVoice(drum_note=38)),
        "bass": _inst("bass_synth_saw", GmVoice(program=38)),
        "lead": _inst("fb_supersaw", GmVoice(program=81)),
        "riser": _inst("fx_riser", GmVoice(program=97)),
        "impact": _inst("fx_impact", GmVoice(program=55)),
        "pluck": _inst("syn_pluck", GmVoice(program=84), volume=34),
        "pad": _inst("syn_poly_pad", GmVoice(program=90)),
    }
    harmony = Harmony(keys=(5, 7), mode="aeolian", progressions=PROGRESSIONS, n_progressions=2)
    sections = {
        "intro": Section(intensity=0.6, parts=frozenset({"pad", "drums"}), groove="intro"),
        "build": Section(prog=1, intensity=0.8, parts=frozenset({"fx", "pad"})),
        "drop": Section(intensity=1.0, parts=frozenset({"bass", "drums", "pad", "lead", "fx", "arp"})),
        "break": Section(prog=1, intensity=0.5, parts=frozenset({"pad"})),
        "outro": Section(intensity=0.5, parts=frozenset({"pad", "drums"}), groove="intro"),
    }
    form = ("intro", "build", "drop", "drop", "break", "build", "drop", "drop", "outro")
    parts = (
        Part("drums", Groove(GROOVES), pan=128,
             kit=Kit(groups=(("kick", ("kick",)), ("clap/hat", ("clap", "hat", "snare"))),
                     priority={"snare": 3, "clap": 2},
                     single_priority={"kick": 4, "clap": 3, "hat": 1, "snare": 4},
                     group_pan={"clap/hat": 150})),
        Part("bass", BassLine("bass", kind="offbeat", vol=54), pan=128),
        Part("pad", Pad("pad", vol=34), pan=88),
        Part("lead", Lead("lead", ScaleRules(leap_probability=0.3, leap_semitones=(3, 5, 7)), LEAD_MOTIFS,
                   vol=46, gate=0.7), pan=168),
        # TODO: Part("fx", <ジェネレータ>, pan=128, min_channels=6)  ← 上書きメソッドで鳴らしていた
        Part("lead echo", Echo(delay=3, ratio=0.45), follow="lead", pan=96, min_channels=8),
        Part("arp", Arp("pluck", register=(24, 35), steps=(0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15), vol=28), pan=160, min_channels=8),
    )
    mod_channels = {4: 1, 6: 2, 8: 1}
    mix = (Sidechain(triggers=("kick",), targets=("bass",), ratio=0.25, release_steps=2), Sidechain(triggers=("kick",), targets=("pad",), ratio=0.35, release_steps=3),)
