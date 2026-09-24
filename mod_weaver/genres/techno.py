"""techno: ミニマル・テクノ（DESIGN.md §6.16.25）。T4（4ch、Amiga 互換）: 4つ打ちと少しずつ変わるシーケンス。"""
from __future__ import annotations

from ..core.model import ChordSpec
from ..profiles.band_common import BandProfile, BassSpec, ChannelDef, Section, hits, preset
from ..profiles.registry import register_profile

C = ChordSpec
CH_KICK, CH_PERC, CH_BASS, CH_SEQ = range(4)

FULL = hits("kick", (0, 4, 8, 12), 60) + hits("ohat", (2, 6, 10, 14), 30) + hits("clap", (4, 12), 40)
HATS = hits("kick", (0, 4, 8, 12), 60) + hits("hat", range(0, 16), 22, 0.7) + hits("ohat", (2, 6, 10, 14), 28)
KICK = hits("kick", (0, 4, 8, 12), 58)

BASE_SEQ = (0, 3, 6, 10, 11, 14)               # シーケンスの初期の発音位置（16分）


@register_profile
class TechnoProfile(BandProfile):
    id = "techno"
    display_name = "Minimal Techno"
    description = "テクノ。繰り返しの中で少しずつ変わるシーケンスと4つ打ち"
    description_en = "Minimal techno: a hypnotic four-on-the-floor with slowly mutating sequences"
    title = "Minimal Techno"
    default_filename = "Techno.mod"
    tempo_choices = (124, 126, 128, 130, 132)

    KIT = (
        ("kick", preset("drum_909_kick")), ("hat", preset("drum_909_hat")), ("ohat", preset("drum_909_open_hat")),
        ("clap", preset("fb_clap")), ("bass", preset("bass_synth_square")), ("seq", preset("syn_stab")),
    )
    CHANNELS = (
        ChannelDef("kick", ("kick",)),
        ChannelDef("hats/clap", ("hat", "ohat", "clap"), (("clap", 3), ("ohat", 2))),
        ChannelDef("bass", ("bass",)),
        ChannelDef("sequence", ("seq",)),
    )
    DRUM_CHANNEL = {"kick": CH_KICK, "hat": CH_PERC, "ohat": CH_PERC, "clap": CH_PERC}
    KEYS = (9, 2)
    MODE = "aeolian"
    PROGRESSIONS = (("i7", (C(0, "m7", label="i7"),)), ("i7-bVII", (C(0, "m7", label="i7"), C(10, "maj", label="bVII"))))
    N_PROGRESSIONS = 1
    SECTIONS = {
        "k1": Section("k1", intensity=0.6, parts=frozenset({"drums"}), groove="kick"),
        "k2": Section("k2", intensity=0.7, parts=frozenset({"drums", "bass"}), groove="kick"),
        "h1": Section("h1", intensity=0.8, parts=frozenset({"drums", "bass", "comp"}), groove="hats"),
        "f1": Section("f1", intensity=1.0, parts=frozenset({"drums", "bass", "comp"})),
        "f2": Section("f2", intensity=1.0, parts=frozenset({"drums", "bass", "comp"})),
        "b1": Section("b1", intensity=0.6, parts=frozenset({"comp", "bass"})),
        "f3": Section("f3", intensity=1.0, parts=frozenset({"drums", "bass", "comp"})),
        "o1": Section("o1", intensity=0.6, parts=frozenset({"drums"}), groove="hats"),
    }
    FORM = ("k1", "k2", "h1", "f1", "f2", "h1", "b1", "f3", "f2", "f3", "o1", "k1")
    GROOVES = {"main": FULL, "hats": HATS, "kick": KICK}
    BASS = BassSpec("bass", CH_BASS, kind="offbeat", vol=48)
    COMP = None

    def extra_measure(self, mctx, sec, st, rng, buf):
        """シーケンス: 4小節ごとに16分の発音位置を1つずつ入れ替える（和音はほぼ固定）。"""
        if "comp" not in sec.parts:
            return
        rows = list(BASE_SEQ)
        shift = (mctx.pattern.index * 4 + mctx.measure_idx // 4) % 16
        rows[shift % len(rows)] = (rows[shift % len(rows)] + 1 + shift) % 16
        inst = mctx.instruments["seq"]
        tones = sorted({t for t in mctx.chord.chord_tones if 19 <= t <= 31}) or [mctx.chord.harmony + 12]
        for i, row in enumerate(sorted(set(rows))):
            note = tones[(i + mctx.measure_idx) % len(tones)]
            buf.put(row, CH_SEQ, inst.cell(note, vol=38 if row % 4 == 0 else 30))
