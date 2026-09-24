"""house: ハウス／ディープハウス（DESIGN.md §12.7.18）。E6（6ch）: 4つ打ちの安定したグルーヴと裏拍のオルガン・スタブ。"""
from __future__ import annotations

from ..core.model import ChordSpec
from ..profiles.band_common import (
    BandProfile, BassSpec, ChannelDef, CompSpec, PadSpec, Section, hits, preset,
)
from ..profiles.registry import register_profile

C = ChordSpec
CH_KICK, CH_PERC, CH_BASS, CH_STAB, CH_PAD, CH_SHAKE = range(6)

DEEP = (hits("kick", (0, 4, 8, 12), 60) + hits("clap", (4, 12), 42) + hits("ohat", (2, 6, 10, 14), 28)
        + hits("shaker", range(1, 16, 2), 18, 0.8) + hits("rim", (7, 15), 24, 0.5))
DRUMS_ONLY = hits("kick", (0, 4, 8, 12), 58) + hits("ohat", (2, 6, 10, 14), 24)


@register_profile
class HouseProfile(BandProfile):
    id = "house"
    display_name = "House / Deep House"
    description = "ハウス。4つ打ちの安定したグルーヴと裏拍のオルガン・スタブ"
    description_en = "House: steady four-on-the-floor groove with offbeat organ stabs"
    title = "Deep House"
    default_filename = "House.mod"
    tempo_choices = (118, 120, 122, 124)

    KIT = (
        ("kick", preset("drum_909_kick")), ("clap", preset("fb_clap")), ("ohat", preset("drum_909_open_hat")),
        ("rim", preset("drum_rim")), ("shaker", preset("perc_shaker")), ("bass", preset("bass_deep")),
    )
    CHORD_KITS = {"stab": (preset("keys_house_stab"), 0.0), "pad": (preset("pad_warm"), 0.0)}
    CHANNELS = (
        ChannelDef("kick", ("kick",), pan=128),
        ChannelDef("clap/hat", ("clap", "ohat", "rim"), (("clap", 3), ("rim", 2)), pan=150),
        ChannelDef("bass", ("bass",), pan=128),
        ChannelDef("stab", ("stab",), pan=96),
        ChannelDef("pad", ("pad",), pan=64),
        ChannelDef("shaker", ("shaker",), pan=184),
    )
    DRUM_CHANNEL = {"kick": CH_KICK, "clap": CH_PERC, "ohat": CH_PERC, "rim": CH_PERC, "shaker": CH_SHAKE}
    KEYS = (9, 2, 7)
    MODE = "dorian"
    PROGRESSIONS = (
        ("im7-IV9", (C(0, "m7", label="im7"), C(5, "dom9", label="IV9"))),
        ("im9-bVIImaj7", (C(0, "m9", label="im9"), C(10, "maj7", label="bVIImaj7"))),
        ("im7-iv7-bVIImaj7-bIIImaj7", (C(0, "m7", label="im7"), C(5, "m7", label="iv7"), C(10, "maj7", label="bVIImaj7"),
                                       C(3, "maj7", label="bIIImaj7"))),
    )
    SECTIONS = {
        "intro": Section("intro", prog=0, intensity=0.6, parts=frozenset({"drums"}), groove="drums"),
        "groove": Section("groove", prog=0, intensity=0.8, parts=frozenset({"drums", "bass", "comp"})),
        "main": Section("main", prog=1, intensity=1.0, parts=frozenset({"drums", "bass", "comp", "pad"})),
        "break": Section("break", prog=2, intensity=0.5, parts=frozenset({"pad", "comp"})),
        "outro": Section("outro", prog=0, intensity=0.6, parts=frozenset({"drums", "bass"}), groove="drums"),
    }
    FORM = ("intro", "groove", "main", "main", "break", "main", "main", "outro")
    GROOVES = {"main": DEEP, "drums": DRUMS_ONLY}
    SIDECHAIN = (("kick", CH_PAD, 0.5, 3),)
    BASS = BassSpec("bass", CH_BASS, kind="house", vol=56)
    COMP = CompSpec("stab", CH_STAB, kind="offbeat", vol=40)
    PAD = PadSpec("pad", CH_PAD, vol=28)
