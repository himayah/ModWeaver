"""calm: 穏やかなピアノとパッド（DESIGN.md §6.16.2）。A4（4ch、Amiga 互換）: ピアノの8分の分散和音、パッド、低音、まばらなベル。"""
from __future__ import annotations

from ..core.model import ChordSpec
from ..profiles.band_common import ArpSpec, BandProfile, BassSpec, ChannelDef, PadSpec, Section, preset
from ..profiles.registry import register_profile

C = ChordSpec
CH_PIANO, CH_PAD, CH_BELL, CH_BASS = range(4)
BELL_REGISTER = (24, 35)


@register_profile
class CalmProfile(BandProfile):
    id = "calm"
    category = "mood"
    display_name = "Calm / Relaxed"
    description = "落ち着き。低いテンポで柔らかいパッドとピアノの分散和音"
    description_en = "Calm and relaxed: soft pads and slow piano arpeggios"
    title = "Calm Evening"
    default_filename = "Calm.mod"
    tempo_choices = (68, 70, 72, 74, 76, 78)

    KIT = (
        ("piano", preset("keys_piano")), ("bass", preset("bass_finger")), ("bell", preset("keys_bell")),
    )
    CHORD_KITS = {"pad": (preset("pad_warm"), 0.0)}
    CHANNELS = (
        ChannelDef("piano", ("piano",)),
        ChannelDef("pad", ("pad",)),
        ChannelDef("bell", ("bell",)),
        ChannelDef("bass", ("bass",)),
    )
    KEYS = (0, 5, 7)
    MODE = "lydian"
    ARP_REGISTER = (12, 27)
    # 和音は2小節ごと（2和音の進行を 4小節の pattern に当てる）
    PROGRESSIONS = (
        ("Imaj7-IVmaj7", (C(0, "maj7", label="Imaj7"), C(5, "maj7", label="IVmaj7"))),
        ("Imaj7-vi7", (C(0, "maj7", label="Imaj7"), C(9, "m7", label="vi7"))),
        ("IVmaj7-Vsus4", (C(5, "maj7", label="IVmaj7"), C(7, "sus4", label="Vsus4"))),
    )
    SECTIONS = {
        "intro": Section("intro", prog=0, intensity=0.3, parts=frozenset({"pad", "arp"})),
        "a": Section("a", prog=0, intensity=0.5, parts=frozenset({"pad", "arp", "bass", "fx"})),
        "b": Section("b", prog=1, intensity=0.6, parts=frozenset({"pad", "arp", "bass", "fx"})),
        "outro": Section("outro", prog=0, intensity=0.2, parts=frozenset({"pad", "arp"})),
    }
    FORM = ("intro", "a", "b", "a", "outro")
    BASS = BassSpec("bass", CH_BASS, kind="whole", vol=34)
    PAD = PadSpec("pad", CH_PAD, vol=30)
    ARP = ArpSpec("piano", CH_PIANO, rows=tuple(range(0, 16, 2)), vol=40, pattern="updown")

    def extra_measure(self, mctx, sec, st, rng, buf):
        """ベル: 4小節に1〜2音（1・3小節目の弱拍に、確率で）。"""
        if "fx" not in sec.parts or mctx.measure_idx % 2:
            return
        if rng.melody.random() < (0.9 if mctx.measure_idx == 0 else 0.45):
            lo, hi = BELL_REGISTER
            tones = [t for t in range(lo, hi + 1) if t % 12 in {c % 12 for c in mctx.chord.chord_tones}]
            row = rng.melody.choice((4, 6, 10, 12))
            buf.put(row, CH_BELL, mctx.instruments["bell"].cell(rng.melody.choice(tones), vol=round(30 * sec.intensity + 10)))
