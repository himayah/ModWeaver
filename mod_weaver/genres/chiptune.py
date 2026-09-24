"""chiptune: 8bit ゲーム音楽風（DESIGN.md §6.17）。4ch（Amiga 互換）をファミコンの音源の割り当てに使う:
パルス波の旋律・パルス波の和音（``0xy`` アルペジオ）・三角波のベース・ノイズの打楽器と効果音。

音色空間の疎な領域（上昇する音程＝ジャンプ音、明るい高音＝パルス波、純音に近い低音＝三角波）を使う。"""
from __future__ import annotations

from ..core.composer import RhythmMotif, ScaleRules
from ..core.model import Cell, ChordSpec
from ..core.pitch import CHORD_QUALITIES
from ..profiles.band_common import BandProfile, BassSpec, ChannelDef, LeadSpec, Section, hits, preset
from ..profiles.registry import register_profile

C = ChordSpec
CH_LEAD, CH_ARP, CH_BASS, CH_NOISE = range(4)

MAIN = hits("kick", (0, 6, 8), 52) + hits("snare", (4, 12), 46) + hits("hat", (2, 10, 14), 26, 0.8)
DRIVE = hits("kick", (0, 3, 6, 8, 11), 52) + hits("snare", (4, 12), 48) + hits("hat", range(2, 16, 4), 26)
FILL = hits("snare", (8, 10, 12, 13, 14, 15), 44)
JUMP_ROW = 12                                  # 区間の最後の小節でジャンプ音を鳴らす row

LEAD_MOTIFS = {
    "verse": (RhythmMotif((0, 2, 4, 6, 8, 12)), RhythmMotif((0, 3, 6, 8, 10, 12)), RhythmMotif((0, 2, 4, 8, 10, 14))),
    "chorus": (RhythmMotif((0, 2, 3, 4, 6, 8, 10, 12, 14)), RhythmMotif((0, 4, 6, 8, 12, 14)),
               RhythmMotif((0, 1, 2, 4, 8, 9, 10, 12))),
}
BAND = frozenset({"drums", "bass", "arp"})


@register_profile
class ChiptuneProfile(BandProfile):
    id = "chiptune"
    category = "style"
    display_name = "Chiptune (8-bit)"
    description = "8bit ゲーム音楽風。パルス波の旋律とアルペジオ、三角波のベース、ノイズの打楽器とジャンプ音"
    description_en = "8-bit chiptune style: pulse-wave melody and arpeggios, triangle bass, noise drums and jump sounds"
    title = "8-Bit Stage 1"
    default_filename = "Chiptune.mod"
    tempo_choices = (140, 146, 152, 158, 164, 170)

    KIT = (
        ("lead", preset("chip_pulse25")), ("arp", preset("chip_pulse12")), ("bass", preset("chip_triangle")),
        ("kick", preset("chip_kick")), ("snare", preset("chip_snare")), ("hat", preset("chip_hat")),
        ("jump", preset("fx_jump")),
    )
    CHANNELS = (
        ChannelDef("pulse 1", ("lead",)),
        ChannelDef("pulse 2", ("arp",)),
        ChannelDef("triangle", ("bass",)),
        ChannelDef("noise", ("kick", "snare", "hat", "jump"), (("jump", 4), ("snare", 3), ("kick", 2))),
    )
    DRUM_CHANNEL = {"kick": CH_NOISE, "snare": CH_NOISE, "hat": CH_NOISE}
    KEYS = (0, 2, 5, 7, 9)
    PROGRESSIONS = (
        ("I-V-vi-IV", (C(0, "maj", label="I"), C(7, "maj", label="V"), C(9, "min", label="vi"), C(5, "maj", label="IV"))),
        ("vi-IV-I-V", (C(9, "min", label="vi"), C(5, "maj", label="IV"), C(0, "maj", label="I"), C(7, "maj", label="V"))),
        ("I-bVII-IV-I", (C(0, "maj", label="I"), C(10, "maj", label="bVII"), C(5, "maj", label="IV"),
                         C(0, "maj", label="I"))),
        ("IV-V-iii-vi", (C(5, "maj", label="IV"), C(7, "maj", label="V"), C(4, "min", label="iii"),
                         C(9, "min", label="vi"))),
    )
    N_PROGRESSIONS = 3
    SECTIONS = {
        "intro": Section("intro", prog=0, intensity=0.8, parts=BAND, fill=True),
        "a": Section("a", prog=0, intensity=0.85, parts=BAND | {"lead"}, fill=True),
        "b": Section("b", prog=1, intensity=0.95, parts=BAND | {"lead"}, groove="drive", fill=True,
                     lead_motifs="chorus"),
        "bridge": Section("bridge", prog=2, intensity=0.7, parts=frozenset({"arp", "bass", "lead"})),
        "outro": Section("outro", prog=0, intensity=0.8, parts=BAND, fill=True),
    }
    FORM = ("intro", "a", "a", "b", "a", "bridge", "b", "a", "outro")
    GROOVES = {"main": MAIN, "drive": DRIVE, "fill": FILL}
    BASS = BassSpec("bass", CH_BASS, kind="octave8", vol=54)
    LEAD = LeadSpec("lead", CH_LEAD, ScaleRules(leap_probability=0.3, leap_semitones=(3, 4, 5, 7, 12)), LEAD_MOTIFS,
                    vol=42, gate=0.8, vibrato=0x33)

    def extra_measure(self, mctx, sec, st, rng, buf):
        ins = mctx.instruments
        if "arp" in sec.parts:
            # パルス波の和音: 和音の変わり目と 8 row 目に鳴らし直し、全 row に 0xy（1 row の中で3音を切り替える）。
            # 音量と効果は同じセルに書けないので、鳴らし直す音はサンプルの既定音量で鳴る
            q = CHORD_QUALITIES[mctx.pattern.extra["qualities"][mctx.measure_idx]]
            param = (q[1] << 4) | q[2]
            arp = ins["arp"]
            for row in range(mctx.measure_rows):
                if row % 8 == 0:
                    buf.put(row, CH_ARP, arp.cell(mctx.chord.harmony, effect=0, param=param))
                else:
                    buf.put(row, CH_ARP, Cell(None, 0, 0, param))
        elif mctx.measure_idx == 0:
            buf.put(0, CH_ARP, ins["arp"].off())
        if sec.fill and mctx.is_last:
            buf.put(JUMP_ROW, CH_NOISE, ins["jump"].cell(vol=40))          # 区間の終わりのジャンプ音
