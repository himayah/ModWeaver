"""focus: 集中用のミニマルなローファイ（DESIGN.md §12.7.9）。B4（4ch、Amiga 互換）: ブーンバップのビート、
ベース、エレピの2和音ループ、レコードのノイズ。旋律を持たず、変化は8小節ごとのハットの密度だけ。"""
from __future__ import annotations

from ..core import groove
from ..core.model import ChordSpec
from ..profiles.band_common import BandProfile, BassSpec, ChannelDef, CompSpec, FxSpec, Section, hits, preset
from ..profiles.registry import register_profile

C = ChordSpec
CH_DRUMS, CH_BASS, CH_EP, CH_FX = range(4)

KICK_SNARE = hits("kick", (0, 7, 10), 58) + hits("snare", (4, 12), 48)
SPARSE = KICK_SNARE + hits("hat", range(0, 16, 4), 22)
EIGHTHS = KICK_SNARE + hits("hat", range(0, 16, 2), 22)
NO_KICK = hits("snare", (4, 12), 44) + hits("hat", range(0, 16, 2), 22)
LOOP = frozenset({"drums", "bass", "comp", "fx"})


@register_profile
class FocusProfile(BandProfile):
    id = "focus"
    category = "mood"
    display_name = "Focus"
    description = "集中。ほとんど変化しないローファイのループと一定のテンポ"
    description_en = "Focus: minimal lo-fi loop with a steady, unchanging groove"
    title = "Focus Loop"
    default_filename = "Focus.mod"
    tempo_choices = (78, 80, 82, 84, 86)

    KIT = (
        ("kick", preset("drum_boombap_kick")), ("snare", preset("drum_boombap_snare")),
        ("hat", preset("nostalgic_hihat")), ("bass", preset("bass_finger")), ("vinyl", preset("fx_vinyl")),
    )
    CHORD_KITS = {"ep": (preset("keys_ep"), 0.0)}
    CHANNELS = (
        ChannelDef("drums", ("kick", "snare", "hat"), (("snare", 3), ("kick", 2))),
        ChannelDef("bass", ("bass",)),
        ChannelDef("e.piano", ("ep",)),
        ChannelDef("vinyl", ("vinyl",)),
    )
    DRUM_CHANNEL = {"kick": CH_DRUMS, "snare": CH_DRUMS, "hat": CH_DRUMS}
    KEYS = (2, 4)
    MODE = "dorian"
    # 曲全体で1つの2和音ループに固定する
    PROGRESSIONS = (
        ("im7-IVmaj7", (C(0, "m7", label="im7"), C(5, "maj7", label="IVmaj7"))),
        ("ii7-V7", (C(2, "m7", label="ii7"), C(7, "dom7", label="V7"))),
        ("Imaj7-vi7", (C(0, "maj7", label="Imaj7"), C(9, "m7", label="vi7"))),
    )
    N_PROGRESSIONS = 1
    SECTIONS = {
        "intro": Section("intro", intensity=0.5, parts=frozenset({"comp", "fx"})),
        "loop": Section("loop", intensity=0.7, parts=LOOP, groove="sparse"),
        "loop2": Section("loop2", intensity=0.7, parts=LOOP),
        "loop_b": Section("loop_b", intensity=0.7, parts=LOOP, groove="nokick"),
        "outro": Section("outro", intensity=0.5, parts=frozenset({"comp", "fx"})),
    }
    # 8小節（2 pattern）ごとにハットの密度だけが変わる
    FORM = ("intro", "loop", "loop", "loop2", "loop2", "loop", "loop_b", "loop_b",
            "loop2", "loop2", "loop", "loop", "outro")
    GROOVES = {"main": EIGHTHS, "sparse": SPARSE, "nokick": NO_KICK}
    SWING = groove.SwingConfig(long_speed=7, short_speed=5)
    BASS = BassSpec("bass", CH_BASS, kind="boombap", vol=52)
    COMP = CompSpec("ep", CH_EP, kind="half", vol=40, wobble=0x22)
    FX = FxSpec("vinyl", CH_FX, every=2, vol=22)
