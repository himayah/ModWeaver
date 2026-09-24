"""edm: ビルドアップとドロップ（DESIGN.md §6.16.17）。E6（6ch）: シンセ主体、ビルドアップで溜めてドロップで弾ける。"""
from __future__ import annotations

from ..core.composer import RhythmMotif, ScaleRules
from ..core.model import ChordSpec
from ..profiles.band_common import (
    ArpSpec, BandProfile, BassSpec, ChannelDef, EchoSpec, Fold, LeadSpec, PadSpec, Section, buildup, hits, keep,
    preset,
)
from ..profiles.registry import register_profile

C = ChordSpec
# 7・8 番目の論理チャンネルは 8ch の編成だけで鳴らす任意パート（DESIGN.md §6.14）
CH_KICK, CH_PERC, CH_BASS, CH_CHORD, CH_LEAD, CH_FX, CH_X_LEAD_ECHO, CH_X_PLUCK_ARP = range(8)

FLOOR = hits("kick", (0, 4, 8, 12), 62) + hits("clap", (4, 12), 48) + hits("hat", (2, 6, 10, 14), 30)
INTRO = hits("kick", (0, 4, 8, 12), 56) + hits("hat", (2, 6, 10, 14), 26)

LEAD_MOTIFS = {"verse": (RhythmMotif((0, 3, 6, 8, 11, 12)), RhythmMotif((0, 2, 4, 6, 8, 12)))}


@register_profile
class EdmProfile(BandProfile):
    id = "edm"
    display_name = "EDM"
    description = "EDM。シンセ主体、ビルドアップで溜めてドロップで弾ける"
    description_en = "EDM: synth-driven builds that explode into the drop"
    title = "EDM Drop"
    default_filename = "Edm.mod"
    tempo_choices = (124, 126, 128, 130)

    KIT = (
        ("kick", preset("drum_909_kick")), ("clap", preset("fb_clap")), ("hat", preset("drum_909_hat")),
        ("snare", preset("drum_pop_snare")), ("bass", preset("bass_synth_saw")), ("lead", preset("fb_supersaw")),
        ("riser", preset("fx_riser")), ("impact", preset("fx_impact")),
        ("pluck", preset("syn_pluck", volume=34)),
    )
    CHORD_KITS = {"pad": (preset("syn_poly_pad"), 0.0)}
    CHANNELS = (
        ChannelDef("kick", ("kick",), pan=128),
        ChannelDef("clap/hat", ("clap", "hat", "snare"), (("snare", 3), ("clap", 2)), pan=150),
        ChannelDef("bass", ("bass",), pan=128),
        ChannelDef("chords", ("pad",), pan=88),
        ChannelDef("lead", ("lead",), pan=168),
        ChannelDef("fx", ("riser", "impact"), (("impact", 2),), pan=128),
        ChannelDef("lead echo", ("lead",), pan=96),
        ChannelDef("pluck arp", ("pluck",), pan=160),
    )
    DRUM_CHANNEL = {"kick": CH_KICK, "clap": CH_PERC, "hat": CH_PERC, "snare": CH_PERC}
    KEYS = (5, 7)
    MODE = "aeolian"
    PROGRESSIONS = (
        ("VI-iv-i-VII", (C(8, "maj", label="VI"), C(5, "min", label="iv"), C(0, "min", label="i"), C(10, "maj", label="VII"))),
        ("i-VI-III-VII", (C(0, "min", label="i"), C(8, "maj", label="VI"), C(3, "maj", label="III"), C(10, "maj", label="VII"))),
    )
    SECTIONS = {
        "intro": Section("intro", prog=0, intensity=0.6, parts=frozenset({"drums", "pad"}), groove="intro"),
        "build": Section("build", prog=1, intensity=0.8, parts=frozenset({"pad", "fx"})),
        "drop": Section("drop", prog=0, intensity=1.0, parts=frozenset({"drums", "bass", "pad", "lead", "fx", "arp"})),
        "break": Section("break", prog=1, intensity=0.5, parts=frozenset({"pad"})),
        "outro": Section("outro", prog=0, intensity=0.5, parts=frozenset({"drums", "pad"}), groove="intro"),
    }
    FORM = ("intro", "build", "drop", "drop", "break", "build", "drop", "drop", "outro")
    GROOVES = {"main": FLOOR, "intro": INTRO}
    SIDECHAIN = (("kick", CH_BASS, 0.25, 2), ("kick", CH_CHORD, 0.35, 3))
    BASS = BassSpec("bass", CH_BASS, kind="offbeat", vol=54)
    PAD = PadSpec("pad", CH_CHORD, vol=34)
    LEAD = LeadSpec("lead", CH_LEAD, ScaleRules(leap_probability=0.3, leap_semitones=(3, 5, 7)), LEAD_MOTIFS,
                    vol=46, gate=0.7)

    ARP = ArpSpec("pluck", CH_X_PLUCK_ARP, rows=tuple(range(16)), vol=28)
    ECHO = (EchoSpec(CH_LEAD, CH_X_LEAD_ECHO, delay=3, ratio=0.45, offs=True),)
    ARRANGEMENTS = {                          # DESIGN.md §6.14: 4ch＝小編成、6ch＝標準、8ch＝任意パートを足す
        4: (Fold("drums", ("kick", "clap/hat"), (("kick", 4), ("snare", 4), ("clap", 3))),
            *keep("bass", "chords", "lead")),
        6: keep("kick", "clap/hat", "bass", "chords", "lead", "fx"),
        8: keep("kick", "clap/hat", "bass", "chords", "lead", "fx", "lead echo", "pluck arp"),
    }
    def extra_measure(self, mctx, sec, st, rng, buf):
        ins = mctx.instruments
        if sec.kind == "build":
            buildup(mctx, buf, CH_PERC, ins["snare"], riser=ins["riser"], fx_ch=CH_FX)
        elif sec.kind == "drop" and mctx.measure_idx == 0:
            buf.put(0, CH_FX, ins["impact"].cell(vol=56))       # ドロップの頭の一撃
