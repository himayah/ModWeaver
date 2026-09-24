"""uplifting: 高揚するシンセ・アンセム（DESIGN.md §6.16.1）。E6（6ch）: 4つ打ち、裏拍のベース、スーパーソウ、16分アルペジオ。"""
from __future__ import annotations

from ..core.composer import RhythmMotif, ScaleRules
from ..core.model import ChordSpec
from ..profiles.band_common import (
    ArpSpec, BandProfile, BassSpec, ChannelDef, EchoSpec, Fold, LayerSpec, LeadSpec, PadSpec, Section, buildup,
    hits, keep, preset,
)
from ..profiles.registry import register_profile

C = ChordSpec
# 7・8 番目の論理チャンネルは 8ch の編成だけで鳴らす任意パート（DESIGN.md §6.14）
CH_KICK, CH_PERC, CH_BASS, CH_CHORD, CH_ARP, CH_LEAD, CH_X_LEAD_ECHO, CH_X_CHOIR = range(8)

FLOOR = hits("kick", (0, 4, 8, 12), 62) + hits("clap", (4, 12), 44) + hits("ohat", (2, 6, 10, 14), 30)
BREAK = hits("ohat", (2, 6, 10, 14), 20)

LEAD_MOTIFS = {"verse": (RhythmMotif((0, 3, 6, 8, 12)), RhythmMotif((0, 2, 4, 8, 10, 12)), RhythmMotif((0, 6, 8, 14)))}
DROP = frozenset({"drums", "bass", "pad", "arp", "lead"})


@register_profile
class UpliftingProfile(BandProfile):
    id = "uplifting"
    category = "mood"
    display_name = "Uplifting"
    description = "上げていく高揚感。4つ打ちとアルペジオ、明るいスーパーソウのコード"
    description_en = "Uplifting anthem: four-on-the-floor, bright arpeggios and supersaw chords"
    title = "Uplifting Anthem"
    default_filename = "Uplifting.mod"
    tempo_choices = (128, 130, 132, 134, 136)

    KIT = (
        ("kick", preset("drum_909_kick")), ("clap", preset("fb_clap")), ("ohat", preset("drum_909_open_hat")),
        ("snare", preset("drum_pop_snare")), ("bass", preset("bass_synth_saw")), ("arp", preset("syn_pluck")),
        ("lead", preset("syn_saw_lead")),
    )
    CHORD_KITS = {"saw": (preset("fb_supersaw"), 0.0), "choir": (preset("vox_choir", volume=30), 0.0)}
    CHANNELS = (
        ChannelDef("kick", ("kick",), pan=128),
        ChannelDef("clap/hat", ("clap", "ohat", "snare"), (("snare", 3), ("clap", 2)), pan=150),
        ChannelDef("bass", ("bass",), pan=128),
        ChannelDef("supersaw", ("saw",), pan=96),
        ChannelDef("arp", ("arp",), pan=176),
        ChannelDef("lead", ("lead",), pan=64),
        ChannelDef("lead echo", ("lead",), pan=96),
        ChannelDef("choir", ("choir",), pan=160),
    )
    DRUM_CHANNEL = {"kick": CH_KICK, "clap": CH_PERC, "ohat": CH_PERC, "snare": CH_PERC}
    KEYS = (2, 4, 5)
    PROGRESSIONS = (
        ("I-V-vi-IV", (C(0, "maj", label="I"), C(7, "maj", label="V"), C(9, "min", label="vi"), C(5, "maj", label="IV"))),
        ("vi-IV-I-V", (C(9, "min", label="vi"), C(5, "maj", label="IV"), C(0, "maj", label="I"), C(7, "maj", label="V"))),
        ("IV-V-iii-vi", (C(5, "maj", label="IV"), C(7, "maj", label="V"), C(4, "min", label="iii"), C(9, "min", label="vi"))),
    )
    SECTIONS = {
        "intro": Section("intro", prog=0, intensity=0.5, parts=frozenset({"drums", "arp"})),
        "build": Section("build", prog=1, intensity=0.7, parts=frozenset({"pad", "arp"})),
        "drop": Section("drop", prog=0, intensity=1.0, parts=DROP),
        "break": Section("break", prog=1, intensity=0.5, parts=frozenset({"drums", "pad", "arp"}), groove="break"),
        "outro": Section("outro", prog=0, intensity=0.5, parts=frozenset({"drums", "arp"})),
    }
    FORM = ("intro", "build", "drop", "drop", "break", "build", "drop", "drop", "outro")
    GROOVES = {"main": FLOOR, "break": BREAK}
    SIDECHAIN = (("kick", CH_BASS, 0.3, 2), ("kick", CH_CHORD, 0.4, 3))
    BASS = BassSpec("bass", CH_BASS, kind="offbeat", vol=52)
    PAD = PadSpec("saw", CH_CHORD, vol=34)
    ARP = ArpSpec("arp", CH_ARP, rows=tuple(range(16)), vol=34)
    LEAD = LeadSpec("lead", CH_LEAD, ScaleRules(leap_probability=0.25, leap_semitones=(4, 5, 7)), LEAD_MOTIFS,
                    vol=44, gate=0.85, vibrato=0x33)

    ECHO = (EchoSpec(CH_LEAD, CH_X_LEAD_ECHO, delay=3, ratio=0.45, offs=True),)
    LAYERS = (LayerSpec("choir", CH_X_CHOIR, follow="pad", vol=26, chordal=True),)
    ARRANGEMENTS = {                          # DESIGN.md §6.14: 4ch＝小編成、6ch＝標準、8ch＝任意パートを足す
        4: (Fold("drums", ("kick", "clap/hat"), (("kick", 4), ("snare", 4), ("clap", 3))),
            *keep("bass", "supersaw", "arp")),
        6: keep("kick", "clap/hat", "bass", "supersaw", "arp", "lead"),
        8: keep("kick", "clap/hat", "bass", "supersaw", "arp", "lead", "lead echo", "choir"),
    }
    def extra_measure(self, mctx, sec, st, rng, buf):
        if sec.kind == "build":
            buildup(mctx, buf, CH_PERC, mctx.instruments["snare"])
