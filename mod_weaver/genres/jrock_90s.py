"""jrock-90s: 90年代 J-ROCK 風（DESIGN.md §6.16.27）。B6（6ch）: 歪んだギター、速いビート、ギターソロ、最後のサビで転調。"""
from __future__ import annotations

from ..core.composer import RhythmMotif, ScaleRules
from ..core.model import ChordSpec
from ..profiles.band_common import (
    ArpSpec, BandProfile, BassSpec, ChannelDef, CompSpec, LeadSpec, Section, hits, preset,
)
from ..profiles.registry import register_profile

C = ChordSpec
CH_KS, CH_CYM, CH_BASS, CH_GTR, CH_LEAD, CH_ARP = range(6)

MAIN = hits("kick", (0, 3, 8, 10), 60) + hits("snare", (4, 12), 56) + hits("hat", range(0, 16, 2), 34)
DRIVE = hits("kick", (0, 2, 8, 10), 60) + hits("snare", (4, 12), 58) + hits("hat", range(0, 16, 2), 36)
FILL = hits("snare", (8, 10, 11, 12, 13, 14, 15), 54)
CRASH = hits("crash", (0,), 60)

LEAD_MOTIFS = {
    "verse": (RhythmMotif((0, 2, 4, 6, 8, 12)), RhythmMotif((0, 4, 6, 8, 10, 12))),
    "chorus": (RhythmMotif((0, 4, 8, 12)), RhythmMotif((0, 2, 4, 8, 12, 14))),
    "solo": (RhythmMotif((0, 1, 2, 3, 4, 6, 8, 10, 12, 13, 14)), RhythmMotif((0, 2, 3, 4, 8, 9, 10, 12))),
}
BAND = frozenset({"drums", "bass", "comp"})


@register_profile
class JRock90sProfile(BandProfile):
    id = "jrock-90s"
    category = "style"
    display_name = "90s J-Rock"
    description = "90年代 J-ROCK 風。歪んだギターが前に出る速いビートとギターソロ、最後のサビで転調"
    description_en = "90s J-rock style: loud guitars over a fast beat, a guitar solo and a final key change"
    title = "J-Rock 90s"
    default_filename = "JRock90s.mod"
    tempo_choices = (140, 146, 152, 158, 164, 168)

    KIT = (
        ("kick", preset("prog_kick")), ("snare", preset("prog_snare")), ("hat", preset("nostalgic_hihat")),
        ("crash", preset("march_crash_cymbal")), ("bass", preset("bass_pick")),
        ("gtr", preset("gtr_crunch", saturate=2.8)), ("lead", preset("prog_lead_gtr")), ("arp", preset("gtr_clean_arp")),
    )
    CHANNELS = (
        ChannelDef("kick/snare", ("kick", "snare"), (("snare", 2),), pan=128),
        ChannelDef("cymbal", ("hat", "crash"), (("crash", 3),), pan=150),
        ChannelDef("bass", ("bass",), pan=128),
        ChannelDef("dist gtr", ("gtr",), pan=72),
        ChannelDef("lead gtr", ("lead",), pan=184),
        ChannelDef("clean gtr", ("arp",), pan=96),
    )
    DRUM_CHANNEL = {"kick": CH_KS, "snare": CH_KS, "hat": CH_CYM, "crash": CH_CYM}
    KEYS = (4, 9, 2)
    MODE = "aeolian"
    PROGRESSIONS = (
        ("bVI-iv-v-i", (C(8, "maj", label="bVI"), C(5, "min", label="iv"), C(7, "min", label="v"),
                             C(0, "min", label="i"))),
        ("i-VI-VII-i", (C(0, "min", label="i"), C(8, "maj", label="VI"), C(10, "maj", label="VII"), C(0, "min", label="i"))),
        ("VI-VII-v-i", (C(8, "maj", label="VI"), C(10, "maj", label="VII"), C(7, "min", label="v"),
                               C(0, "min", label="i"))),
    )
    N_PROGRESSIONS = 3
    SECTIONS = {
        "intro": Section("intro", prog=1, intensity=0.9, parts=BAND | {"lead"}, crash=True, fill=True,
                         lead_motifs="chorus"),
        "a": Section("a", prog=1, intensity=0.7, parts=frozenset({"drums", "bass", "arp"}) | {"lead"}),
        "b": Section("b", prog=2, intensity=0.85, parts=BAND | {"lead"}, fill=True),
        "sabi": Section("sabi", prog=0, intensity=1.0, parts=BAND | {"lead"}, groove="drive", crash=True, fill=True,
                        lead_motifs="chorus"),
        "solo": Section("solo", prog=1, intensity=0.95, parts=BAND | {"lead"}, groove="drive", lead_motifs="solo",
                        fill=True),
        "sabi_up": Section("sabi_up", prog=0, intensity=1.0, parts=BAND | {"lead"}, groove="drive", key_offset=1,
                           crash=True, lead_motifs="chorus"),
        "outro": Section("outro", prog=1, intensity=0.9, parts=BAND, key_offset=1, crash=True),
    }
    FORM = ("intro", "a", "b", "sabi", "a", "b", "sabi", "solo", "sabi", "sabi_up", "outro")
    GROOVES = {"main": MAIN, "drive": DRIVE, "fill": FILL, "crash": CRASH}
    BASS = BassSpec("bass", CH_BASS, kind="root8", vol=58)
    COMP = CompSpec("gtr", CH_GTR, kind="pulse8", vol=46, chordal=False)
    ARP = ArpSpec("arp", CH_ARP, rows=tuple(range(0, 16, 2)), vol=34)
    ARP_REGISTER = (19, 31)
    LEAD = LeadSpec("lead", CH_LEAD, ScaleRules(leap_probability=0.3, leap_semitones=(3, 5, 7)), LEAD_MOTIFS,
                    vol=48, gate=0.9, vibrato=0x46)

    def comp(self, mctx, sec, rng, buf):
        """歪んだパワーコードの8分の刻み。"""
        inst = mctx.instruments["gtr"]
        for i, row in enumerate(range(0, 16, 2)):
            vol = 48 if i % 2 == 0 else 40
            buf.put(row, CH_GTR, inst.cell(mctx.chord.harmony, vol=round(vol * (0.6 + 0.4 * sec.intensity))))
