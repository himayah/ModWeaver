"""cinematic: 映画音楽の情感（DESIGN.md §6.16.21）。O8（8ch）: ピアノのオスティナートから弦とホルンが重なり、
合唱とティンパニでドラマチックに高まる。クライマックスは平行長調の響き（III–VII–i–VI＝長調の I–V–vi–IV）。"""
from __future__ import annotations

from ..core.composer import RhythmMotif, ScaleRules
from ..core.model import ChordSpec
from ..core.pitch import fold_into_range
from ..profiles.band_common import (
    ArpSpec, BandProfile, BassSpec, ChannelDef, LeadSpec, PadSpec, Section, _scale_vol, preset,
)
from ..profiles.registry import register_profile

C = ChordSpec
CH_PIANO, CH_VLN, CH_VLA, CH_VC, CH_CB, CH_HORN, CH_CHOIR, CH_TIMP = range(8)
HORN_REGISTER = (14, 26)

LEAD_MOTIFS = {
    "verse": (RhythmMotif((0, 8)), RhythmMotif((0, 6, 8)), RhythmMotif((0, 4, 8, 12)), RhythmMotif((0, 12))),
}
P_MINOR, P_LIFT, P_MAJOR = range(3)


def _parts(*names: str) -> frozenset[str]:
    return frozenset(names)


@register_profile
class CinematicProfile(BandProfile):
    id = "cinematic"
    display_name = "Cinematic"
    description = "映画音楽。ピアノのオスティナートから弦とホルンが重なり、ドラマチックに高まる"
    description_en = "Cinematic: piano ostinato building to soaring strings and horns"
    title = "Cinematic Rise"
    default_filename = "Cinematic.mod"
    tempo_choices = (70, 72, 76, 80, 84)

    KIT = (
        ("piano", preset("keys_piano", volume=42)), ("vln", preset("orch_violin")), ("vc", preset("orch_cello")),
        ("cb", preset("orch_bass_str")), ("horn", preset("march_brass_section", volume=40)),
        ("timp", preset("orch_timpani")), ("swell", preset("free_cymbal_swell")),
    )
    CHORD_KITS = {"vla": (preset("orch_viola", volume=34), 0.0), "choir": (preset("vox_choir", volume=34), 0.0)}
    CHANNELS = (
        ChannelDef("piano", ("piano",), pan=100),
        ChannelDef("violin", ("vln",), pan=84),
        ChannelDef("viola", ("vla",), pan=160),
        ChannelDef("cello", ("vc",), pan=176),
        ChannelDef("contrabass", ("cb",), pan=150),
        ChannelDef("horn", ("horn",), pan=110),
        ChannelDef("choir", ("choir",), pan=128),
        ChannelDef("timpani", ("timp", "swell"), (("timp", 2),), pan=128),
    )
    KEYS = (0, 2)
    MODE = "aeolian"
    ARP_REGISTER = (12, 27)
    FIXED_PROGRESSIONS = True
    PROGRESSIONS = (
        ("i-VI-III-VII", (C(0, "min", label="i"), C(8, "maj", label="VI"), C(3, "maj", label="III"),
                          C(10, "maj", label="VII"))),
        ("VI-VII-i", (C(8, "maj", label="VI"), C(10, "maj", label="VII"), C(0, "min", label="i"), C(0, "min", label="i"))),
        ("III-VII-i-VI (relative major I-V-vi-IV)", (C(3, "maj", label="III"), C(10, "maj", label="VII"),
                                                     C(0, "min", label="i"), C(8, "maj", label="VI"))),
    )
    SECTIONS = {
        "intro": Section("intro", prog=P_MINOR, intensity=0.5, parts=_parts("arp")),
        "rise1": Section("rise1", prog=P_MINOR, intensity=0.6, parts=_parts("arp", "bass", "viola")),
        "theme": Section("theme", prog=P_MINOR, intensity=0.75, parts=_parts("arp", "bass", "viola", "cb", "lead")),
        "rise2": Section("rise2", prog=P_LIFT, intensity=0.85,
                         parts=_parts("arp", "bass", "viola", "cb", "lead", "horn", "pad", "timp")),
        "climax": Section("climax", prog=P_MAJOR, intensity=1.0,
                          parts=_parts("arp", "bass", "viola", "cb", "lead", "horn", "pad", "timp")),
        "resolve": Section("resolve", prog=P_MINOR, intensity=0.4, parts=_parts("arp")),
    }
    FORM = ("intro", "rise1", "theme", "theme", "rise2", "climax", "climax", "resolve")
    BASS = BassSpec("vc", CH_VC, kind="half", vol=46)
    PAD = PadSpec("choir", CH_CHOIR, vol=34)
    ARP = ArpSpec("piano", CH_PIANO, rows=tuple(range(0, 16, 2)), vol=36, pattern="updown")
    LEAD = LeadSpec("vln", CH_VLN, ScaleRules(leap_probability=0.3, leap_semitones=(3, 4, 5, 7, 8)), LEAD_MOTIFS,
                    vol=48, gate=1.0, vibrato=0x23)

    def extra_measure(self, mctx, sec, st, rng, buf):
        ins = mctx.instruments
        chord = mctx.chord
        change = self._is_chord_change(mctx)
        parts = sec.parts
        # 休む区間では持続音色を先頭で止める（前の区間から鳴り続けないように）
        for part, ch in (("viola", CH_VLA), ("cb", CH_CB), ("horn", CH_HORN)):
            if part not in parts:
                self._silence(buf, ch, part, ins, mctx)
        if "viola" in parts and change:
            buf.put(0, CH_VLA, ins[self._chord_key("vla", mctx)].cell(chord.harmony, vol=_scale_vol(32, sec)))
        if "cb" in parts and change:
            buf.put(0, CH_CB, ins["cb"].cell(chord.bass - 12, vol=_scale_vol(44, sec)))
        if "horn" in parts and change:
            third = sorted({t % 12 for t in chord.chord_tones}, key=lambda pc: (pc - chord.harmony) % 12)[1]
            buf.put(0, CH_HORN, ins["horn"].cell(fold_into_range(third, *HORN_REGISTER), vol=_scale_vol(40, sec)))
        if "timp" in parts:
            timp = ins["timp"]
            if sec.kind == "rise2" and mctx.is_last:
                for row in range(16):                                # 最後の小節はティンパニのロールで高める
                    buf.put(row, CH_TIMP, timp.cell(chord.bass, vol=min(64, 24 + row * 2)))
            elif sec.kind == "rise2" and mctx.measure_idx == 1:
                buf.put(0, CH_TIMP, ins["swell"].cell(vol=40))        # クライマックスの2小節前にシンバルのスウェル
            else:
                buf.put(0, CH_TIMP, timp.cell(chord.bass, vol=_scale_vol(50, sec)))
                if sec.kind == "climax":
                    buf.put(8, CH_TIMP, timp.cell(chord.bass, vol=_scale_vol(40, sec)))
