"""dark-tense: 緊張感のある暗いパルス（DESIGN.md §12.7.6）。E6（6ch）: 低音のオスティナート、刻む音、重い打撃と金管。"""
from __future__ import annotations

from ..core.model import ChordSpec
from ..profiles.band_common import BandProfile, BassSpec, ChannelDef, PadSpec, Section, hits, preset
from ..profiles.registry import register_profile

C = ChordSpec
CH_TAIKO, CH_TICK, CH_BASS, CH_STR, CH_BRAAM, CH_FX = range(6)

PULSE = (hits("taiko", (0, 8), 60) + hits("tick", (0, 4, 8, 12), 28)
         + hits("tick", tuple(r for r in range(16) if r % 4), 18))
TICK = hits("tick", range(16), 18)


@register_profile
class DarkTenseProfile(BandProfile):
    id = "dark-tense"
    category = "mood"
    display_name = "Dark / Tense"
    description = "緊張感。低音のオスティナートと刻むパルス、重い打撃"
    description_en = "Dark and tense: low ostinato, ticking pulse and heavy hits"
    title = "Dark Pulse"
    default_filename = "DarkTense.mod"
    tempo_choices = (90, 92, 94, 96, 98, 100)

    KIT = (
        ("taiko", preset("perc_taiko")), ("tick", preset("drum_909_hat")), ("bass", preset("bass_synth_saw")),
        ("str", preset("tension_strings")), ("braam", preset("brass_braam")), ("riser", preset("fx_riser")),
        ("impact", preset("fx_impact")),
    )
    CHANNELS = (
        ChannelDef("taiko", ("taiko",), pan=128),
        ChannelDef("tick", ("tick",), pan=176),
        ChannelDef("bass", ("bass",), pan=128),
        ChannelDef("strings", ("str",), pan=72),
        ChannelDef("braam", ("braam",), pan=110),
        ChannelDef("fx", ("riser", "impact"), (("impact", 2),), pan=150),
    )
    DRUM_CHANNEL = {"taiko": CH_TAIKO, "tick": CH_TICK}
    KEYS = (0, 2)
    MODE = "harmonic_minor"
    PROGRESSIONS = (
        ("i-bII-i-V", (C(0, "min", label="i"), C(1, "maj", label="bII"), C(0, "min", label="i"), C(7, "maj", label="V"))),
        ("i-VI-iv-V", (C(0, "min", label="i"), C(8, "maj", label="VI"), C(5, "min", label="iv"), C(7, "maj", label="V"))),
    )
    SECTIONS = {
        "intro": Section("intro", prog=0, intensity=0.4, parts=frozenset({"drums", "pad"}), groove="tick"),
        "build": Section("build", prog=0, intensity=0.6, parts=frozenset({"drums", "bass", "pad", "fx"}), groove="tick"),
        "pulse": Section("pulse", prog=1, intensity=0.8, parts=frozenset({"drums", "bass", "pad", "lead"})),
        "climax": Section("climax", prog=0, intensity=1.0, parts=frozenset({"drums", "bass", "pad", "lead", "fx"})),
        "collapse": Section("collapse", prog=0, intensity=0.4, parts=frozenset({"pad"})),
    }
    FORM = ("intro", "build", "pulse", "build", "climax", "collapse")
    GROOVES = {"main": PULSE, "tick": TICK}
    BASS = BassSpec("bass", CH_BASS, kind="pulse16", vol=46)
    PAD = PadSpec("str", CH_STR, vol=34, chordal=False)
    REGISTERS = BandProfile.REGISTERS

    def extra_measure(self, mctx, sec, st, rng, buf):
        ins = mctx.instruments
        if "lead" in sec.parts and mctx.measure_idx % 2 == 0:       # 2小節ごとの「ブラーム」
            buf.put(0, CH_BRAAM, ins["braam"].cell(mctx.chord.bass, vol=round(52 * (0.6 + 0.4 * sec.intensity))))
        if "fx" in sec.parts:
            if sec.kind == "build" and mctx.measure_idx == 2:
                buf.put(0, CH_FX, ins["riser"].cell(vol=44))
            if sec.kind == "climax" and mctx.measure_idx == 0:
                buf.put(0, CH_FX, ins["impact"].cell(vol=58))
