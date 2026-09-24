"""acoustic-ssw: アコースティック弾き語り風（DESIGN.md §12.7.34）。B4（4ch、Amiga 互換）: カホンとシェイカー、
控えめなベース、指弾き（トラヴィス奏法）のギター、歌のような旋律。"""
from __future__ import annotations

from ..core.composer import RhythmMotif, ScaleRules
from ..core.model import ChordSpec
from ..core.pitch import fold_into_range
from ..profiles.band_common import (
    BandProfile, BassSpec, ChannelDef, CompSpec, LeadSpec, Section, _arp_tones, _scale_vol, hits, preset,
)
from ..profiles.registry import register_profile

C = ChordSpec
CH_PERC, CH_BASS, CH_GTR, CH_VOX = range(4)

CAJON = hits("low", (0, 10), 44) + hits("slap", (4, 12), 38) + hits("shaker", range(2, 16, 4), 18, 0.8)
# 歌の旋律。息継ぎを強めに（各小節の最後の拍は空け、4小節目は BandProfile.lead が後半を休ませる）
LEAD_MOTIFS = {
    "verse": (RhythmMotif((0, 2, 4, 8)), RhythmMotif((0, 4, 6, 8)), RhythmMotif((2, 4, 6, 10))),
    "chorus": (RhythmMotif((0, 4, 8, 10)), RhythmMotif((0, 2, 4, 6, 8)), RhythmMotif((0, 6, 8, 10))),
}
THUMB_REGISTER = (5, 19)                       # 親指（根音と5度）
FINGER_REGISTER = (17, 29)                     # 他の指（上声）
BAND = frozenset({"drums", "bass", "comp"})


@register_profile
class AcousticSswProfile(BandProfile):
    id = "acoustic-ssw"
    category = "style"
    display_name = "Acoustic Singer-songwriter"
    description = "弾き語り風。指弾きのギターと軽いパーカッション、歌のような旋律"
    description_en = "Acoustic singer-songwriter style: fingerpicked guitar, light percussion and a vocal-like melody"
    title = "Acoustic Diary"
    default_filename = "AcousticSSW.mod"
    tempo_choices = (80, 84, 88, 92, 96, 100)

    KIT = (
        ("low", preset("perc_cajon")), ("slap", preset("perc_cajon_slap")), ("shaker", preset("perc_shaker")),
        ("bass", preset("bass_finger")), ("gtr", preset("gtr_acoustic")), ("vox", preset("vox_ooh")),
    )
    CHANNELS = (
        ChannelDef("cajon/shaker", ("low", "slap", "shaker"), (("slap", 3), ("low", 2))),
        ChannelDef("bass", ("bass",)),
        ChannelDef("guitar", ("gtr",)),
        ChannelDef("voice", ("vox",)),
    )
    DRUM_CHANNEL = {"low": CH_PERC, "slap": CH_PERC, "shaker": CH_PERC}
    KEYS = (7, 0, 2, 4)
    PROGRESSIONS = (
        ("I-V-vi-IV", (C(0, "maj", label="I"), C(7, "maj", label="V"), C(9, "min", label="vi"), C(5, "maj", label="IV"))),
        ("vi-IV-I-V", (C(9, "min", label="vi"), C(5, "maj", label="IV"), C(0, "maj", label="I"), C(7, "maj", label="V"))),
        ("I-iii-vi-IV", (C(0, "maj", label="I"), C(4, "min", label="iii"), C(9, "min", label="vi"),
                         C(5, "maj", label="IV"))),
    )
    SECTIONS = {
        "intro": Section("intro", prog=0, intensity=0.5, parts=frozenset({"comp"})),
        "verse": Section("verse", prog=0, intensity=0.6, parts=BAND | {"lead"}),
        "chorus": Section("chorus", prog=1, intensity=0.85, parts=BAND | {"lead"}, lead_motifs="chorus"),
        "bridge": Section("bridge", prog=2, intensity=0.7, parts=frozenset({"comp", "bass", "lead"})),
        "outro": Section("outro", prog=0, intensity=0.45, parts=frozenset({"comp"})),
    }
    FORM = ("intro", "verse", "chorus", "verse", "chorus", "bridge", "chorus", "outro")
    GROOVES = {"main": CAJON}
    BASS = BassSpec("bass", CH_BASS, kind="whole", vol=38)
    COMP = CompSpec("gtr", CH_GTR, kind="fingerpick", vol=40, chordal=False)
    LEAD = LeadSpec("vox", CH_VOX, ScaleRules(leap_probability=0.15, leap_semitones=(3, 4, 5)), LEAD_MOTIFS,
                    vol=44, gate=0.85, vibrato=0x22)

    def comp(self, mctx, sec, rng, buf):
        """トラヴィス奏法: 親指が4分で根音と5度を交互に、他の指が8分裏で上声を弾く。"""
        chord = mctx.chord
        inst = mctx.instruments["gtr"]
        root = fold_into_range(chord.bass, *THUMB_REGISTER)
        fifth = fold_into_range(chord.bass + 7, *THUMB_REGISTER)
        upper = [t for t in _arp_tones(chord, FINGER_REGISTER) if t % 12 != chord.bass % 12] or [chord.harmony + 12]
        vol = _scale_vol(self.COMP.vol, sec)
        for beat in range(4):
            buf.put(beat * 4, CH_GTR, inst.cell(root if beat % 2 == 0 else fifth, vol=vol))
            buf.put(beat * 4 + 2, CH_GTR, inst.cell(upper[(beat + mctx.measure_idx) % len(upper)], vol=max(1, vol - 8)))
