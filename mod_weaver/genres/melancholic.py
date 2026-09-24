"""melancholic: 物悲しいピアノ・バラード（DESIGN.md §12.7.3）。A4 の読み替え（4ch、Amiga 互換）:
旋律ピアノ・伴奏ピアノ・弦のパッド・チェロの低音。"""
from __future__ import annotations

from ..core.composer import RhythmMotif, ScaleRules
from ..core.midi import GmVoice
from ..core.model import ChordSpec
from ..profiles.band_common import ArpSpec, BandProfile, BassSpec, ChannelDef, LeadSpec, PadSpec, Section, preset
from ..profiles.registry import register_profile

C = ChordSpec
CH_LEAD, CH_ACC, CH_STR, CH_BASS = range(4)

# 4分・2分主体。フレーズ末は長音（BandProfile.lead の終止小節が後半を休ませる）
LEAD_MOTIFS = {
    "verse": (RhythmMotif((0, 8)), RhythmMotif((0, 4, 8)), RhythmMotif((0, 6, 8, 12)), RhythmMotif((0, 4, 12))),
}


@register_profile
class MelancholicProfile(BandProfile):
    id = "melancholic"
    category = "mood"
    display_name = "Melancholic"
    description = "物悲しい。短調のピアノが旋律を歌い、弦のパッドが支える"
    description_en = "Melancholic piano ballad in a minor key over soft strings"
    title = "Grey Winter"
    default_filename = "Melancholic.mod"
    tempo_choices = (66, 68, 70, 72, 74, 76)

    KIT = (
        ("piano", preset("keys_piano")), ("accomp", preset("keys_piano", name="PianoAccomp", volume=38)),
        ("cello", preset("orch_cello")),
    )
    CHORD_KITS = {"str": (preset("orch_violin", name="StringPad", volume=34), 0.0)}
    GM = {"accomp": GmVoice(program=0), "str": GmVoice(program=48)}
    CHANNELS = (
        ChannelDef("piano melody", ("piano",)),
        ChannelDef("piano accomp", ("accomp",)),
        ChannelDef("strings", ("str",)),
        ChannelDef("cello", ("cello",)),
    )
    KEYS = (9, 2, 4)
    MODE = "aeolian"
    ARP_REGISTER = (12, 24)
    PROGRESSIONS = (
        ("i-VI-III-VII", (C(0, "min", label="i"), C(8, "maj", label="VI"), C(3, "maj", label="III"),
                          C(10, "maj", label="VII"))),
        ("i-iv-VII-III", (C(0, "min", label="i"), C(5, "min", label="iv"), C(10, "maj", label="VII"),
                          C(3, "maj", label="III"))),
        ("i-VII-VI-V", (C(0, "min", label="i"), C(10, "maj", label="VII"), C(8, "maj", label="VI"),
                        C(7, "maj", label="V"))),   # V は和声的短音階の長三和音
    )
    SECTIONS = {
        "intro": Section("intro", prog=0, intensity=0.4, parts=frozenset({"arp"})),
        "a": Section("a", prog=0, intensity=0.6, parts=frozenset({"arp", "lead", "bass"})),
        "b": Section("b", prog=1, intensity=0.8, parts=frozenset({"arp", "lead", "bass", "pad"})),
        "outro": Section("outro", prog=0, intensity=0.4, parts=frozenset({"arp", "pad"})),
    }
    FORM = ("intro", "a", "b", "a", "b", "outro")
    BASS = BassSpec("cello", CH_BASS, kind="half", vol=40)
    PAD = PadSpec("str", CH_STR, vol=30)
    ARP = ArpSpec("accomp", CH_ACC, rows=tuple(range(0, 16, 2)), vol=34, pattern="updown")
    LEAD = LeadSpec("piano", CH_LEAD, ScaleRules(leap_probability=0.3, leap_semitones=(3, 4, 5, 7, 8)), LEAD_MOTIFS,
                    vol=48, gate=1.0)
