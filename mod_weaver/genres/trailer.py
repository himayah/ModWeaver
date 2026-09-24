"""trailer: 映画予告編風（DESIGN.md §6.16.32）。O8（8ch）: 大太鼓と金管の衝撃、刻む弦、合唱で盛り上がる3幕構成。

第1幕は衝撃と無音の間、第2幕は刻みと打楽器が加わり、上昇音のビルドアップを経て、第3幕は半音上で全合奏。
最後は一撃と余韻で終わる。"""
from __future__ import annotations

from ..core.composer import RhythmMotif, ScaleRules
from ..core.model import ChordSpec
from ..core.pitch import fold_into_range
from ..profiles.band_common import (
    BandProfile, BassSpec, ChannelDef, Fold, LeadSpec, PadSpec, Section, _scale_vol, buildup, hits, keep, preset,
)
from ..profiles.registry import register_profile

C = ChordSpec
CH_TAIKO, CH_PERC, CH_BRAAM, CH_SPIC, CH_LOW, CH_CHOIR, CH_HIGH, CH_FX = range(8)

DRIVE = hits("taiko", (0, 6, 8), 58) + hits("taiko", (14,), 44, 0.6)
FULL = hits("taiko", (0, 4, 6, 8, 12, 14), 60)
PULSE = hits("taiko", (0, 4, 8, 12), 54)
SPIC_ACCENTS = (0, 3, 6, 8, 11, 14)           # 3+3+2 のアクセント
TOM_ROWS = (10, 12, 13, 14, 15)                # 第3幕の小節末のタム

LEAD_MOTIFS = {"verse": (RhythmMotif((0, 8)), RhythmMotif((0, 12)), RhythmMotif((0, 4, 8)))}


def _parts(*names: str) -> frozenset[str]:
    return frozenset(names)


@register_profile
class TrailerProfile(BandProfile):
    id = "trailer"
    category = "style"
    display_name = "Cinematic Trailer"
    description = "映画予告編風。大太鼓と金管の衝撃、刻む弦、合唱で盛り上がる3幕構成"
    description_en = "Cinematic trailer style: taiko and brass hits, driving strings and choir in three acts"
    title = "Trailer: Three Acts"
    default_filename = "Trailer.mod"
    tempo_choices = (90, 92, 94, 96, 98, 100)

    KIT = (
        ("taiko", preset("perc_taiko")), ("tom", preset("drum_tom")), ("snare", preset("march_snare")),
        ("braam", preset("brass_braam")), ("spic", preset("str_spiccato")), ("cello", preset("orch_cello")),
        ("vln", preset("orch_violin")), ("riser", preset("fx_riser")), ("impact", preset("fx_impact")),
    )
    CHORD_KITS = {"choir": (preset("vox_choir", volume=36), 0.0)}
    CHANNELS = (
        ChannelDef("taiko", ("taiko",), pan=128),
        ChannelDef("toms/snare", ("tom", "snare"), (("snare", 2),), pan=150),
        ChannelDef("braam", ("braam",), pan=110),
        ChannelDef("spiccato", ("spic",), pan=80),
        ChannelDef("low strings", ("cello",), pan=128),
        ChannelDef("choir", ("choir",), pan=170),
        ChannelDef("high strings", ("vln",), pan=90),
        ChannelDef("fx", ("riser", "impact"), (("impact", 2),), pan=128),
    )
    DRUM_CHANNEL = {"taiko": CH_TAIKO, "snare": CH_PERC}
    KEYS = (2, 0)
    MODE = "aeolian"
    PROGRESSIONS = (
        ("i-VI-III-VII", (C(0, "min", label="i"), C(8, "maj", label="VI"), C(3, "maj", label="III"),
                          C(10, "maj", label="VII"))),
        ("i-bVI-bVII-i", (C(0, "min", label="i"), C(8, "maj", label="bVI"), C(10, "maj", label="bVII"),
                          C(0, "min", label="i"))),
    )
    SECTIONS = {
        "act1": Section("act1", prog=0, intensity=0.55, parts=_parts("hits")),
        "act2": Section("act2", prog=0, intensity=0.75, parts=_parts("drums", "spic", "bass", "braam")),
        "riser": Section("riser", prog=1, intensity=0.85, parts=_parts("drums", "spic", "bass", "build"), groove="pulse"),
        "act3": Section("act3", prog=1, intensity=1.0,
                        parts=_parts("drums", "spic", "bass", "braam", "pad", "lead", "toms"), groove="full",
                        key_offset=1),
        "final": Section("final", prog=1, intensity=0.9, parts=_parts("hits", "pad", "bass"), key_offset=1),
    }
    FORM = ("act1", "act1", "act2", "act2", "riser", "act3", "act3", "final")
    GROOVES = {"main": DRIVE, "full": FULL, "pulse": PULSE}
    BASS = BassSpec("cello", CH_LOW, kind="half", vol=48)
    PAD = PadSpec("choir", CH_CHOIR, vol=38)
    LEAD = LeadSpec("vln", CH_HIGH, ScaleRules(leap_probability=0.35, leap_semitones=(3, 4, 5, 7, 12)), LEAD_MOTIFS,
                    vol=50, gate=1.0, vibrato=0x24)

    ARRANGEMENTS = {                          # DESIGN.md §6.14: 6ch＝taiko とタム・スネアを1チャンネルに畳み、効果音を省く
        6: (Fold("percussion", ("taiko", "toms/snare"), (("taiko", 3), ("snare", 2), ("tom", 2))),
            *keep("braam", "spiccato", "low strings", "choir", "high strings")),
        8: keep("taiko", "toms/snare", "braam", "spiccato", "low strings", "choir", "high strings", "fx"),
    }
    CHANNEL_WEIGHTS = {6: 1, 8: 2}
    def compose_measure(self, mctx, st, rng, buf):
        sec = self.SECTIONS[mctx.pattern.kind]
        if sec.kind == "final" and mctx.measure_idx > 0:
            # 一撃の後は余韻だけ（持続音は2小節で止める）
            if mctx.measure_idx == 2:
                for ch in (CH_LOW, CH_CHOIR):
                    buf.put(0, ch, mctx.instruments["cello"].off())
            return
        super().compose_measure(mctx, st, rng, buf)

    def extra_measure(self, mctx, sec, st, rng, buf):
        ins = mctx.instruments
        chord = mctx.chord
        parts = sec.parts
        m = mctx.measure_idx
        if "hits" in parts and m % 2 == 0:
            # 衝撃: taiko・braam（・最初は impact）を同時に鳴らし、後は無音の間
            buf.put(0, CH_TAIKO, ins["taiko"].cell(vol=64))
            buf.put(0, CH_BRAAM, ins["braam"].cell(chord.bass, vol=_scale_vol(60, sec)))
            if m == 0:
                buf.put(0, CH_FX, ins["impact"].cell(vol=60))
        if "braam" in parts and m % 2 == 0:
            buf.put(0, CH_BRAAM, ins["braam"].cell(chord.bass, vol=_scale_vol(56, sec)))
        if "spic" in parts:
            spic = ins["spic"]
            root = fold_into_range(chord.bass, 12, 23)
            fifth = fold_into_range(chord.bass + 7, 12, 23)
            for row in range(16):
                accent = row in SPIC_ACCENTS
                note = fifth if row in (6, 14) else root
                buf.put(row, CH_SPIC, spic.cell(note, vol=_scale_vol(44 if accent else 30, sec)))
        if "build" in parts:
            buildup(mctx, buf, CH_PERC, ins["snare"], riser=ins["riser"], fx_ch=CH_FX)
        if "toms" in parts and m % 2 == 1:
            tom = ins["tom"]
            for i, row in enumerate(TOM_ROWS):
                buf.put(row, CH_PERC, tom.cell(fold_into_range(chord.bass + 12 - i * 2, 12, 23), vol=48 + i * 3))
        if sec.kind == "act3" and m == 0:
            buf.put(0, CH_FX, ins["impact"].cell(vol=60))
