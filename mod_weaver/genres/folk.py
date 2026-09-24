"""folk: フォーク（DESIGN.md §6.16.22）。B4（4ch、Amiga 互換）: 足踏みと手拍子、アップライト・ベース、
アコースティックギターのストローク、フィドル（前打音の装飾つき）。"""
from __future__ import annotations

from ..core.composer import RhythmMotif, ScaleRules
from ..core.midi import GmVoice
from ..core.model import ChordSpec
from ..profiles.band_common import BandProfile, BassSpec, ChannelDef, CompSpec, LeadSpec, Section, hits, preset
from ..profiles.registry import register_profile

C = ChordSpec
CH_PERC, CH_BASS, CH_GTR, CH_FIDDLE = range(4)

STOMP_CLAP = hits("stomp", (0, 8), 56) + hits("clap", (4, 12), 44) + hits("tamb", (2, 6, 10, 14), 20, 0.7)
LEAD_MOTIFS = {
    "verse": (RhythmMotif((0, 2, 4, 6, 8, 12)), RhythmMotif((0, 4, 6, 8, 10, 12)), RhythmMotif((0, 2, 4, 8, 12))),
    "reel": (RhythmMotif(tuple(range(0, 16, 2))), RhythmMotif((0, 2, 4, 6, 8, 10, 12)),
             RhythmMotif((0, 2, 3, 4, 6, 8, 10, 12, 14))),
}
BAND = frozenset({"drums", "bass", "comp"})
GRACE_PROB = 0.3                               # 前打音を付ける確率（直前が空いている音だけ）


@register_profile
class FolkProfile(BandProfile):
    id = "folk"
    display_name = "Folk"
    description = "フォーク。アコースティックギターのストロークとフィドル、素朴な進行"
    description_en = "Folk: strummed acoustic guitar and fiddle over simple progressions"
    title = "Folk Road"
    default_filename = "Folk.mod"
    tempo_choices = (96, 100, 104, 108, 112, 116)

    KIT = (
        ("stomp", preset("perc_stomp")), ("clap", preset("fb_clap")), ("tamb", preset("perc_tambourine")),
        ("bass", preset("swing_walk_bass")), ("fiddle", preset("orch_violin", name="Fiddle", volume=42)),
    )
    CHORD_KITS = {"gtr": (preset("gtr_acoustic"), 14.0)}
    GM = {"fiddle": GmVoice(program=110)}
    CHANNELS = (
        ChannelDef("stomp/clap", ("stomp", "clap", "tamb"), (("clap", 3), ("stomp", 2))),
        ChannelDef("upright bass", ("bass",)),
        ChannelDef("guitar", ("gtr",)),
        ChannelDef("fiddle", ("fiddle",)),
    )
    DRUM_CHANNEL = {"stomp": CH_PERC, "clap": CH_PERC, "tamb": CH_PERC}
    KEYS = (7, 2, 0, 9)
    PROGRESSIONS = (
        ("I-IV-I-V", (C(0, "maj", label="I"), C(5, "maj", label="IV"), C(0, "maj", label="I"), C(7, "maj", label="V"))),
        ("I-V-vi-IV", (C(0, "maj", label="I"), C(7, "maj", label="V"), C(9, "min", label="vi"), C(5, "maj", label="IV"))),
        ("I-bVII-IV-I", (C(0, "maj", label="I"), C(10, "maj", label="bVII"), C(5, "maj", label="IV"),
                         C(0, "maj", label="I"))),
    )
    SECTIONS = {
        "intro": Section("intro", prog=0, intensity=0.6, parts=frozenset({"comp", "drums"})),
        "verse": Section("verse", prog=0, intensity=0.7, parts=BAND | {"lead"}),
        "chorus": Section("chorus", prog=1, intensity=0.9, parts=BAND | {"lead"}),
        "instrumental": Section("instrumental", prog=0, intensity=1.0, parts=BAND | {"lead"}, lead_motifs="reel"),
        "outro": Section("outro", prog=0, intensity=0.6, parts=BAND),
    }
    FORM = ("intro", "verse", "chorus", "verse", "instrumental", "chorus", "outro")
    GROOVES = {"main": STOMP_CLAP}
    BASS = BassSpec("bass", CH_BASS, kind="rootfifth", vol=54)
    COMP = CompSpec("gtr", CH_GTR, kind="pulse8", vol=38)
    LEAD = LeadSpec("fiddle", CH_FIDDLE, ScaleRules(leap_probability=0.12, leap_semitones=(3, 4, 5)), LEAD_MOTIFS,
                    vol=46, gate=0.9, vibrato=0x23)

    def lead(self, mctx, sec, st, rng, buf):
        """フィドルの前打音: 直前の row が空いている音に、確率で1つ上の音階音を16分で先行させる。"""
        super().lead(mctx, sec, st, rng, buf)
        inst = mctx.instruments["fiddle"]
        scale = mctx.chord.scale_tones
        for row in range(1, mctx.measure_rows):
            cell = buf.get(row, CH_FIDDLE)
            if cell.note is None or not buf.get(row - 1, CH_FIDDLE).is_empty or rng.melody.random() >= GRACE_PROB:
                continue
            note = cell.note + inst.spec.shift                 # tracker note → logical note
            above = [t for t in scale if t > note]
            if above:
                buf.put(row - 1, CH_FIDDLE, inst.cell(above[0], vol=max(1, (cell.vol or 40) - 10)))
