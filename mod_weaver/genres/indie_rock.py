"""indie-rock: インディー・ロック風（DESIGN.md §6.16.31）。B6（6ch）: 生音のドラム・鳴り響くギターのアルペジオ・軽い歪み。"""
from __future__ import annotations

import dataclasses

from ..core.composer import RhythmMotif, ScaleRules
from ..core.model import ChordSpec
from ..profiles.band_common import (
    ArpSpec, BandProfile, BassSpec, ChannelDef, CompSpec, EchoSpec, Fold, LayerSpec, LeadSpec, Section, hits, keep,
    preset,
)
from ..profiles.registry import register_profile

C = ChordSpec
CH_KS, CH_HAT, CH_BASS, CH_ARP, CH_LEAD, CH_GTR2, CH_X_LEAD_ECHO, CH_X_ORGAN = range(8)   # 7・8 番目は 8ch の編成だけ

MAIN = hits("kick", (0, 6, 8), 56) + hits("snare", (4, 12), 50) + hits("tamb", range(0, 16, 2), 22)
DISCO = hits("kick", (0, 4, 8, 12), 56) + hits("snare", (4, 12), 50) + hits("hat", (2, 6, 10, 14), 30)
FILL = hits("snare", (10, 12, 14, 15), 48)
CRASH = hits("crash", (0,), 52)

LEAD_MOTIFS = {
    "verse": (RhythmMotif((0, 4, 8, 12)), RhythmMotif((0, 3, 6, 8, 12))),
    "chorus": (RhythmMotif((0, 2, 4, 8, 10, 12)), RhythmMotif((0, 4, 6, 8, 12, 14))),
}
BAND = frozenset({"drums", "bass", "arp"})


@register_profile
class IndieRockProfile(BandProfile):
    id = "indie-rock"
    category = "style"
    display_name = "Indie Rock"
    description = "インディー・ロック風。生音のドラムと鳴り響くギターのアルペジオ、軽い歪み"
    description_en = "Indie rock style: live-sounding drums, ringing guitar arpeggios and light overdrive"
    title = "Indie Rock"
    default_filename = "IndieRock.mod"
    tempo_choices = (118, 122, 126, 130, 134, 138)

    KIT = (
        ("kick", preset("prog_kick")), ("snare", preset("drum_pop_snare")), ("hat", preset("nostalgic_hihat")),
        ("tamb", preset("perc_tambourine")), ("crash", preset("march_crash_cymbal")), ("bass", preset("bass_pick")),
        ("arp", preset("gtr_clean_arp")), ("lead", preset("syn_square_lead")), ("gtr2", preset("gtr_crunch", volume=34)),
        ("organ", preset("keys_organ", volume=30)),
    )
    CHANNELS = (
        ChannelDef("kick/snare", ("kick", "snare"), (("snare", 2),), pan=128),
        ChannelDef("hat", ("hat", "tamb", "crash"), (("crash", 3),), pan=160),
        ChannelDef("bass", ("bass",), pan=128),
        ChannelDef("clean gtr", ("arp",), pan=80),
        ChannelDef("lead", ("lead",), pan=176),
        ChannelDef("crunch gtr", ("gtr2",), pan=56),
        ChannelDef("lead echo", ("lead",), pan=96),
        ChannelDef("organ", ("organ",), pan=160),
    )
    DRUM_CHANNEL = {"kick": CH_KS, "snare": CH_KS, "hat": CH_HAT, "tamb": CH_HAT, "crash": CH_HAT}
    KEYS = (7, 2, 9)                           # G / D / A
    PROGRESSIONS = (
        ("I-IV-vi-V", (C(0, "maj", label="I"), C(5, "maj", label="IV"), C(9, "min", label="vi"), C(7, "maj", label="V"))),
        ("I-iii-IV-iv", (C(0, "maj", label="I"), C(4, "min", label="iii"), C(5, "maj", label="IV"), C(5, "min", label="iv"))),
        ("vi-IV-I-V", (C(9, "min", label="vi"), C(5, "maj", label="IV"), C(0, "maj", label="I"), C(7, "maj", label="V"))),
    )
    SECTIONS = {
        "intro": Section("intro", prog=0, intensity=0.6, parts=frozenset({"arp"})),
        "verse": Section("verse", prog=0, intensity=0.7, parts=BAND | {"lead"}),
        "chorus": Section("chorus", prog=1, intensity=1.0, parts=BAND | {"lead", "comp"}, crash=True, fill=True,
                          lead_motifs="chorus"),
        "bridge": Section("bridge", prog=2, intensity=0.6, parts=frozenset({"arp", "bass", "drums"})),
        "outro": Section("outro", prog=0, intensity=0.6, parts=frozenset({"arp", "bass"})),
    }
    FORM = ("intro", "verse", "chorus", "verse", "chorus", "bridge", "chorus", "outro")
    GROOVES = {"main": MAIN, "disco": DISCO, "fill": FILL, "crash": CRASH}
    BASS = BassSpec("bass", CH_BASS, kind="root8", vol=54)
    ARP = ArpSpec("arp", CH_ARP, rows=tuple(range(0, 16, 2)), vol=38, pattern="updown")
    ARP_REGISTER = (19, 31)
    COMP = CompSpec("gtr2", CH_GTR2, kind="strum", vol=34, chordal=False)
    LEAD = LeadSpec("lead", CH_LEAD, ScaleRules(leap_probability=0.2, leap_semitones=(3, 4, 5, 7)), LEAD_MOTIFS,
                    vol=44, gate=0.85)

    ECHO = (EchoSpec(CH_LEAD, CH_X_LEAD_ECHO, delay=3, ratio=0.45, offs=True),)
    LAYERS = (LayerSpec("organ", CH_X_ORGAN, follow="lead", vol=26),)
    ARRANGEMENTS = {                          # DESIGN.md §6.14: 4ch＝小編成、6ch＝標準、8ch＝任意パートを足す
        4: (Fold("drums", ("kick/snare", "hat"), (("snare", 4), ("kick", 3), ("crash", 2))),
            *keep("bass", "clean gtr", "lead")),
        6: keep("kick/snare", "hat", "bass", "clean gtr", "lead", "crunch gtr"),
        8: keep("kick/snare", "hat", "bass", "clean gtr", "lead", "crunch gtr", "lead echo", "organ"),
    }
    def plan(self, rng):
        plan = super().plan(rng)
        disco = rng.plan.random() < 0.5            # 半数の seed でダンス寄りの4つ打ち
        for pp in plan.patterns:
            pp.extra["disco"] = disco
        return plan

    def drums(self, mctx, sec, rng, buf):
        if mctx.pattern.extra.get("disco") and sec.groove == "main":
            sec = dataclasses.replace(sec, groove="disco")
        super().drums(mctx, sec, rng, buf)
