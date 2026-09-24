"""energetic: 元気なドラム主体のロック（DESIGN.md §12.7.4）。B6（6ch）。速い長調、倍速のビート。"""
from __future__ import annotations

from ..core.composer import RhythmMotif, ScaleRules
from ..core.model import ChordSpec
from ..profiles.band_common import BandProfile, BassSpec, ChannelDef, CompSpec, LeadSpec, Section, hits, preset
from ..profiles.registry import register_profile

C = ChordSpec
CH_KS, CH_CYM, CH_BASS, CH_GTR, CH_LEAD, CH_TOM = range(6)

DOUBLE = hits("kick", (0, 6, 8, 14), 60) + hits("snare", (4, 12), 56) + hits("hat", range(0, 16, 2), 34)
HALF = hits("kick", (0, 10), 58) + hits("snare", (8,), 56) + hits("hat", range(0, 16, 2), 28)
FILL = hits("tom", (8, 9, 10, 11), 52) + hits("snare", (12, 13, 14, 15), 54)
CRASH = hits("crash", (0,), 60)

LEAD_MOTIFS = {
    "verse": (RhythmMotif((0, 2, 4, 8, 10, 12)), RhythmMotif((0, 4, 6, 8, 12, 14))),
    "chorus": (RhythmMotif((0, 4, 8, 12)), RhythmMotif((0, 2, 4, 6, 8, 12))),
}
BAND = frozenset({"drums", "bass", "comp"})


@register_profile
class EnergeticProfile(BandProfile):
    id = "energetic"
    category = "mood"
    display_name = "Energetic"
    description = "元気・活動的。速いテンポと強いドラム、8分で刻むギターとベース"
    description_en = "Energetic: fast, drum-driven rock with driving guitars and bass"
    title = "Energetic Run"
    default_filename = "Energetic.mod"
    tempo_choices = (160, 164, 168, 172, 176)

    KIT = (
        ("kick", preset("prog_kick")), ("snare", preset("prog_snare")), ("hat", preset("nostalgic_hihat")),
        ("crash", preset("march_crash_cymbal")), ("tom", preset("drum_tom")), ("bass", preset("bass_pick")),
        ("gtr", preset("gtr_crunch")), ("lead", preset("syn_square_lead")),
    )
    CHANNELS = (
        ChannelDef("kick/snare", ("kick", "snare"), (("snare", 2),), pan=128),
        ChannelDef("cymbal", ("hat", "crash"), (("crash", 3),), pan=150),
        ChannelDef("bass", ("bass",), pan=128),
        ChannelDef("gtr", ("gtr",), pan=76),
        ChannelDef("lead", ("lead",), pan=180),
        ChannelDef("tom", ("tom",), pan=110),
    )
    DRUM_CHANNEL = {"kick": CH_KS, "snare": CH_KS, "hat": CH_CYM, "crash": CH_CYM, "tom": CH_TOM}
    KEYS = (4, 9, 2)
    PROGRESSIONS = (
        ("I-V-vi-IV", (C(0, "maj", label="I"), C(7, "maj", label="V"), C(9, "min", label="vi"), C(5, "maj", label="IV"))),
        ("IV-I-V-vi", (C(5, "maj", label="IV"), C(0, "maj", label="I"), C(7, "maj", label="V"), C(9, "min", label="vi"))),
        ("I-IV-vi-V", (C(0, "maj", label="I"), C(5, "maj", label="IV"), C(9, "min", label="vi"), C(7, "maj", label="V"))),
    )
    SECTIONS = {
        "intro": Section("intro", prog=0, intensity=0.8, parts=BAND, crash=True, fill=True),
        "verse": Section("verse", prog=1, intensity=0.8, parts=BAND | {"lead"}, fill=True),
        "pre": Section("pre", prog=2, intensity=0.9, parts=BAND | {"lead"}, fill=True),
        "chorus": Section("chorus", prog=0, intensity=1.0, parts=BAND | {"lead"}, crash=True, fill=True,
                          lead_motifs="chorus"),
        "bridge": Section("bridge", prog=2, intensity=0.7, parts=BAND | {"lead"}, groove="half"),
        "outro": Section("outro", prog=0, intensity=0.9, parts=BAND, crash=True),
    }
    FORM = ("intro", "verse", "pre", "chorus", "verse", "pre", "chorus", "bridge", "chorus", "chorus", "outro")
    GROOVES = {"main": DOUBLE, "half": HALF, "fill": FILL, "crash": CRASH}
    BASS = BassSpec("bass", CH_BASS, kind="root8", vol=58)
    COMP = CompSpec("gtr", CH_GTR, kind="pulse8", vol=44, chordal=False)
    LEAD = LeadSpec("lead", CH_LEAD, ScaleRules(leap_probability=0.25, leap_semitones=(4, 5, 7)), LEAD_MOTIFS,
                    vol=46, gate=0.8)

    def comp(self, mctx, sec, rng, buf):
        """パワーコードを8分で刻む（強拍を強く）。"""
        inst = mctx.instruments["gtr"]
        for i, row in enumerate(range(0, 16, 2)):
            vol = 46 if i % 2 == 0 else 38
            buf.put(row, CH_GTR, inst.cell(mctx.chord.harmony, vol=round(vol * (0.6 + 0.4 * sec.intensity))))
