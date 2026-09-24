"""classical: 古典派の弦楽四重奏（DESIGN.md §12.7.20）。Q4（4ch、Amiga 互換）: vln1・vln2・vla・vc。

3/4 拍子（1 measure＝12 row、``variable_meter``）で 1 pattern＝4小節（48 row）＋``D00``。メヌエットとトリオ:
前楽節（半終止）・後楽節（完全終止）、属調の中間部（V/V を含む）、下属調のトリオ、コーダ。各区間の和声は
役割が決まっているので進行は宣言順に固定する（``FIXED_PROGRESSIONS``）。"""
from __future__ import annotations

from ..core.composer import RhythmMotif, ScaleRules
from ..core.midi import GmVoice
from ..core.model import Cell, ChordSpec
from ..core.pitch import fold_into_range
from ..profiles.band_common import BandProfile, ChannelDef, LeadSpec, Section, _scale_vol, preset
from ..profiles.registry import register_profile

C = ChordSpec
CH_VLN1, CH_VLN2, CH_VLA, CH_VC = range(4)
ROWS = 12                                      # 3/4 の1小節

LEAD_MOTIFS = {
    "minuet": (RhythmMotif((0, 4, 8)), RhythmMotif((0, 2, 4, 8)), RhythmMotif((0, 4, 6, 8)), RhythmMotif((0, 6, 8))),
    "trio": (RhythmMotif((0, 8)), RhythmMotif((0, 4, 8)), RhythmMotif((0, 2, 4, 6, 8))),
}
VLN2_REGISTER = (17, 28)
VLA_REGISTER = (10, 21)
QUARTET = frozenset({"lead", "inner", "bass"})

P_ANTE, P_CONS, P_B, P_RET, P_TRIO_A, P_TRIO_B, P_CODA = range(7)


@register_profile
class ClassicalProfile(BandProfile):
    id = "classical"
    display_name = "Classical (String Quartet)"
    description = "クラシック。古典派のメヌエット風の弦楽四重奏、明確な和声と終止"
    description_en = "Classical: a Classical-era minuet for string quartet with clear cadences"
    title = "Minuet and Trio"
    default_filename = "Classical.mod"
    tempo_choices = (100, 104, 108, 112, 116, 120)
    rows_per_measure = ROWS
    variable_meter = True

    KIT = (
        ("vln1", preset("orch_violin")), ("vln2", preset("orch_violin", name="OrchViolin2", volume=38)),
        ("vla", preset("orch_viola", volume=38)), ("vc", preset("orch_cello")),
    )
    GM = {"vln2": GmVoice(program=40)}
    CHANNELS = (
        ChannelDef("violin 1", ("vln1",)),
        ChannelDef("violin 2", ("vln2",)),
        ChannelDef("viola", ("vla",)),
        ChannelDef("cello", ("vc",)),
    )
    KEYS = (7, 2, 5, 10)
    FIXED_PROGRESSIONS = True
    MEASURES_PER_PATTERN = 4
    PROGRESSIONS = (
        ("antecedent I-IV-ii6-V", (C(0, "maj", label="I"), C(5, "maj", label="IV"), C(2, "min", bass=5, label="ii6"),
                                   C(7, "maj", label="V"))),
        ("consequent I-IV-V7-I", (C(0, "maj", label="I"), C(5, "maj", label="IV"), C(7, "dom7", label="V7"),
                                  C(0, "maj", label="I"))),
        ("dominant I-V/V-V7-I", (C(0, "maj", label="I"), C(2, "dom7", label="V/V"), C(7, "dom7", label="V7"),
                                 C(0, "maj", label="I"))),
        ("return I-vi-V/V-V", (C(0, "maj", label="I"), C(9, "min", label="vi"), C(2, "dom7", label="V/V"),
                               C(7, "maj", label="V"))),
        ("trio I-V7-V7-I", (C(0, "maj", label="I"), C(7, "dom7", label="V7"), C(7, "dom7", label="V7"),
                            C(0, "maj", label="I"))),
        ("trio IV-I-V7-I", (C(5, "maj", label="IV"), C(0, "maj", label="I"), C(7, "dom7", label="V7"),
                            C(0, "maj", label="I"))),
        ("coda IV-V7-I-I", (C(5, "maj", label="IV"), C(7, "dom7", label="V7"), C(0, "maj", label="I"),
                            C(0, "maj", label="I"))),
    )
    SECTIONS = {
        "ante": Section("ante", prog=P_ANTE, intensity=0.7, parts=QUARTET, lead_motifs="minuet"),
        "cons": Section("cons", prog=P_CONS, intensity=0.75, parts=QUARTET, lead_motifs="minuet"),
        "dom": Section("dom", prog=P_B, intensity=0.85, parts=QUARTET, key_offset=7, lead_motifs="minuet"),
        "ret": Section("ret", prog=P_RET, intensity=0.8, parts=QUARTET, lead_motifs="minuet"),
        "trio_a": Section("trio_a", prog=P_TRIO_A, intensity=0.55, parts=frozenset({"lead", "bass", "inner"}),
                          key_offset=5, lead_motifs="trio"),
        "trio_b": Section("trio_b", prog=P_TRIO_B, intensity=0.6, parts=frozenset({"lead", "bass", "inner"}),
                          key_offset=5, lead_motifs="trio"),
        "coda": Section("coda", prog=P_CODA, intensity=0.8, parts=QUARTET, lead_motifs="minuet"),
    }
    # メヌエット（A: 前楽節＋後楽節を反復、B: 属調→復帰→A）、トリオ、メヌエットの再現、コーダ
    FORM = ("ante", "cons", "ante", "cons", "dom", "ret", "ante", "cons",
            "trio_a", "trio_b", "trio_a", "trio_b", "ante", "cons", "coda")
    LEAD = LeadSpec("vln1", CH_VLN1, ScaleRules(leap_probability=0.2, leap_semitones=(3, 4, 5, 7, 8, 12)),
                    LEAD_MOTIFS, vol=46, gate=0.9, vibrato=0x22)

    def compose_measure(self, mctx, st, rng, buf):
        super().compose_measure(mctx, st, rng, buf)
        sec = self.SECTIONS[mctx.pattern.kind]
        ins = mctx.instruments
        chord = mctx.chord
        final = sec.kind == "coda" and mctx.is_last
        # vc: 1拍目に低音（終止の小節は付点2分で伸ばす）。トリオは3拍目にも5度
        vc = ins["vc"]
        buf.put(0, CH_VC, vc.cell(chord.bass, vol=_scale_vol(48, sec)))
        if sec.lead_motifs == "trio" and not final:
            buf.put(8, CH_VC, vc.cell(fold_into_range(chord.bass + 7, *self.REGISTERS.bass), vol=_scale_vol(40, sec)))
        # vln2・vla: 2・3拍目に和音を刻む（メヌエットの伴奏型）。最後の小節は1拍目に和音を伸ばす
        tones = sorted({t % 12 for t in chord.chord_tones})
        upper = self._nearest(st, "vln2", tones, VLN2_REGISTER)
        inner = self._nearest(st, "vla", tones, VLA_REGISTER, avoid=upper % 12)
        rows = (0,) if final else (4, 8)
        for row in rows:
            buf.put(row, CH_VLN2, ins["vln2"].cell(upper, vol=_scale_vol(34, sec)))
            buf.put(row, CH_VLA, ins["vla"].cell(inner, vol=_scale_vol(34, sec)))
        if not final:
            for ch in (CH_VLN2, CH_VLA):
                buf.put(ROWS - 1, ch, Cell(None, 0, vol=0))        # 刻みの切れ目（次の小節の1拍目の前で止める）

    @staticmethod
    def _nearest(st, name, pcs, register, avoid=None) -> int:
        """直前の音に最も近い構成音（声部の滑らかな進行）。"""
        lo, hi = register
        cands = [n for n in range(lo, hi + 1) if n % 12 in pcs and n % 12 != avoid] or \
                [n for n in range(lo, hi + 1) if n % 12 in pcs]
        prev = st.extra.get(name, (lo + hi) // 2)
        note = min(cands, key=lambda n: (abs(n - prev), n))
        st.extra[name] = note
        return note

    def finalize_pattern(self, pctx, pattern, st, rng):
        super().finalize_pattern(pctx, pattern, st, rng)
        last = self.MEASURES_PER_PATTERN * ROWS - 1           # D00 を書く row に空きチャンネルを1つ残す
        if not any(pattern.get(last, c).is_empty for c in range(pattern.channels)):
            pattern.replace(last, CH_VLA, Cell())
