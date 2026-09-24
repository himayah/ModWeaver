"""hiphop: ブーンバップ・ヒップホップ（DESIGN.md §12.7.19）。B4（4ch、Amiga 互換）: ブーンバップのビート、ベース、
ピアノの和音ループ、フックのホーン。ラップ向けの構成（verse は旋律を置かず余白を残す）。"""
from __future__ import annotations

from ..core import groove
from ..core.composer import RhythmMotif, ScaleRules
from ..core.model import ChordSpec
from ..profiles.band_common import BandProfile, BassSpec, ChannelDef, CompSpec, LeadSpec, Section, hits, preset
from ..profiles.registry import register_profile

C = ChordSpec
CH_DRUMS, CH_BASS, CH_LOOP, CH_HORN = range(4)

BOOMBAP = (hits("kick", (0, 7, 10), 60) + hits("snare", (4, 12), 52)
           + hits("hat", range(0, 16, 2), 22) + hits("kick", (15,), 44, 0.3))
SPARSE = hits("kick", (0, 10), 56) + hits("snare", (4, 12), 48)
# ホーンのスタブ（短い決めの動機。hook は同じ pattern を再利用するので毎回同じ決めになる）
LEAD_MOTIFS = {"hook": (RhythmMotif((0, 3, 6)), RhythmMotif((0, 3, 10)), RhythmMotif((0, 6, 8, 11)))}
BEAT = frozenset({"drums", "bass", "comp"})


@register_profile
class HiphopProfile(BandProfile):
    id = "hiphop"
    display_name = "Hip Hop (Boom Bap)"
    description = "ヒップホップ。ラップが乗る余白を残したブーンバップのビートとサンプル風ループ"
    description_en = "Hip hop: boom-bap beats and sample-style loops that leave room for rap"
    title = "Boom Bap Cypher"
    default_filename = "Hiphop.mod"
    tempo_choices = (86, 88, 90, 92, 94, 96)

    KIT = (
        ("kick", preset("drum_boombap_kick")), ("snare", preset("drum_boombap_snare")),
        ("hat", preset("nostalgic_hihat")), ("bass", preset("bass_finger")), ("horn", preset("march_brass_horn")),
    )
    CHORD_KITS = {"loop": (preset("keys_piano", volume=42), 0.0)}
    CHANNELS = (
        ChannelDef("drums", ("kick", "snare", "hat"), (("snare", 3), ("kick", 2))),
        ChannelDef("bass", ("bass",)),
        ChannelDef("loop", ("loop",)),
        ChannelDef("horn", ("horn",)),
    )
    DRUM_CHANNEL = {"kick": CH_DRUMS, "snare": CH_DRUMS, "hat": CH_DRUMS}
    KEYS = (9, 4, 2, 7)
    MODE = "aeolian"
    # 1〜2小節の短調ループを曲全体で固定する（サンプルを繰り返す作り方）
    PROGRESSIONS = (
        ("i-VI", (C(0, "min", label="i"), C(8, "maj", label="VI"), C(0, "min", label="i"), C(8, "maj", label="VI"))),
        ("i-iv", (C(0, "min", label="i"), C(5, "min", label="iv"), C(0, "min", label="i"), C(5, "min", label="iv"))),
        ("im7-bVImaj7", (C(0, "m7", label="im7"), C(0, "m7", label="im7"), C(8, "maj7", label="bVImaj7"),
                         C(8, "maj7", label="bVImaj7"))),
    )
    N_PROGRESSIONS = 1
    SECTIONS = {
        "intro": Section("intro", intensity=0.6, parts=frozenset({"comp", "drums"}), groove="sparse"),
        "verse": Section("verse", intensity=0.75, parts=BEAT),
        "hook": Section("hook", intensity=0.95, parts=BEAT | {"lead"}, lead_motifs="hook"),
        "outro": Section("outro", intensity=0.6, parts=frozenset({"comp", "drums"}), groove="sparse"),
    }
    # intro 4小節、verse 16小節、hook 8小節、verse 16小節、hook 8小節、outro
    FORM = ("intro", "verse", "verse", "verse", "verse", "hook", "hook",
            "verse", "verse", "verse", "verse", "hook", "hook", "outro")
    GROOVES = {"main": BOOMBAP, "sparse": SPARSE}
    SWING = groove.SwingConfig(long_speed=7, short_speed=5)
    BASS = BassSpec("bass", CH_BASS, kind="boombap", vol=56)
    COMP = CompSpec("loop", CH_LOOP, kind="charleston", vol=40)
    LEAD = LeadSpec("horn", CH_HORN, ScaleRules(leap_probability=0.3, leap_semitones=(3, 5, 7)), LEAD_MOTIFS,
                    vol=46, gate=0.6)
