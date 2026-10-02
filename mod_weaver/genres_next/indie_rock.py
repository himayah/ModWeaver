"""indie-rock（旧 genres/indie_rock.py の宣言を機械変換したもの。FRAMEWORK_REDESIGN.md §15）。"""
# TODO(F6): 上書きメソッドの移植: drums, plan
from __future__ import annotations

from ..core.composer import RhythmMotif, ScaleRules
from ..core.model import ChordSpec, GmVoice
from ..core.synth_presets import PRESETS
from ..framework.gens import Arp, BassLine, Comp, Echo, Groove, Layer, Lead, hits
from ..framework.genre import Genre, Harmony, Instrument, Kit, Part, Section
from ..framework.registry import register_genre

C = ChordSpec


def _inst(key: str, gm: GmVoice, **changes) -> Instrument:
    patch = PRESETS[key]
    if changes:
        import dataclasses
        patch = dataclasses.replace(patch, **changes)
    return Instrument(patch=patch, gm=gm)

GROOVES = {
    "main": hits("kick", (0, 6, 8), 56) + hits("snare", (4, 12), 50) + hits("tamb", (0, 2, 4, 6, 8, 10, 12, 14), 22),
    "disco": hits("kick", (0, 4, 8, 12), 56) + hits("snare", (4, 12), 50) + hits("hat", (2, 6, 10, 14), 30),
    "fill": hits("snare", (10, 12, 14, 15), 48),
    "crash": hits("crash", (0,), 52),
}
LEAD_MOTIFS = {
    "verse": (RhythmMotif(rows=(0, 4, 8, 12)), RhythmMotif(rows=(0, 3, 6, 8, 12))),
    "chorus": (RhythmMotif(rows=(0, 2, 4, 8, 10, 12)), RhythmMotif(rows=(0, 4, 6, 8, 12, 14))),
}
PROGRESSIONS = (
    ("I-IV-vi-V", (C(0, "maj", label="I"), C(5, "maj", label="IV"), C(9, "min", label="vi"), C(7, "maj", label="V"))),
    ("I-iii-IV-iv", (C(0, "maj", label="I"), C(4, "min", label="iii"), C(5, "maj", label="IV"), C(5, "min", label="iv"))),
    ("vi-IV-I-V", (C(9, "min", label="vi"), C(5, "maj", label="IV"), C(0, "maj", label="I"), C(7, "maj", label="V"))),
)


@register_genre
class IndieRockGenre(Genre):
    id = "indie-rock"
    category = "style"
    display_name = "Indie Rock"
    description = "インディー・ロック風。生音のドラムと鳴り響くギターのアルペジオ、軽い歪み"
    description_en = "Indie rock style: live-sounding drums, ringing guitar arpeggios and light overdrive"
    title = "Indie Rock"
    tempo_choices = (118, 122, 126, 130, 134, 138)

    instruments = {
        "kick": _inst("prog_kick", GmVoice(drum_note=36)),
        "snare": _inst("drum_pop_snare", GmVoice(drum_note=38)),
        "hat": _inst("nostalgic_hihat", GmVoice(drum_note=42)),
        "tamb": _inst("perc_tambourine", GmVoice(drum_note=54)),
        "crash": _inst("march_crash_cymbal", GmVoice(drum_note=49)),
        "bass": _inst("bass_pick", GmVoice(program=34)),
        "arp": _inst("gtr_clean_arp", GmVoice(program=27)),
        "lead": _inst("syn_square_lead", GmVoice(program=80)),
        "gtr2": _inst("gtr_crunch", GmVoice(program=29), volume=34),
        "organ": _inst("keys_organ", GmVoice(program=16), volume=30),
    }
    harmony = Harmony(keys=(7, 2, 9), mode="ionian", progressions=PROGRESSIONS, n_progressions=2)
    sections = {
        "intro": Section(intensity=0.6, parts=frozenset({"arp"})),
        "verse": Section(intensity=0.7, parts=frozenset({"lead", "bass", "drums", "arp"})),
        "chorus": Section(prog=1, intensity=1.0, parts=frozenset({"bass", "drums", "comp", "lead", "arp"}), fill=True, crash=True, motifs="chorus"),
        "bridge": Section(prog=2, intensity=0.6, parts=frozenset({"bass", "drums", "arp"})),
        "outro": Section(intensity=0.6, parts=frozenset({"bass", "arp"})),
    }
    form = ("intro", "verse", "chorus", "verse", "chorus", "bridge", "chorus", "outro")
    parts = (
        Part("drums", Groove(GROOVES), pan=128,
             kit=Kit(groups=(("kick/snare", ("kick", "snare")), ("hat", ("hat", "tamb", "crash"))),
                     priority={"snare": 2, "crash": 3},
                     single_priority={"kick": 3, "snare": 4, "hat": 1, "tamb": 1, "crash": 2},
                     group_pan={"hat": 160})),
        Part("bass", BassLine("bass", kind="root8", vol=54), pan=128),
        Part("arp", Arp("arp", register=(19, 31), steps=(0, 2, 4, 6, 8, 10, 12, 14), vol=38, pattern="updown"), pan=80),
        Part("lead", Lead("lead", ScaleRules(leap_probability=0.2, leap_semitones=(3, 4, 5, 7)), LEAD_MOTIFS,
                   vol=44, gate=0.85), pan=176),
        Part("comp", Comp("gtr2", kind="strum", vol=34, chordal=False), pan=56, min_channels=6),
        Part("lead echo", Echo(delay=3, ratio=0.45), follow="lead", pan=96, min_channels=8),
        Part("organ", Layer("organ", vol=26), follow="lead", pan=160, min_channels=8),
    )
    mod_channels = {4: 1, 6: 2, 8: 1}
