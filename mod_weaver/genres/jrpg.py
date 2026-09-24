"""jrpg: JRPG のフィールド曲風（DESIGN.md §6.16.29）。B6（6ch）: ティンパニと軽いスネア、ハープの分散和音、
チェロの低音、弦のパッド、旋律（フルート／トランペット）、金管の対旋律とファンファーレ。

旋律が主役: 4小節の楽節の2小節目は1小節目の動機を1音階上げて繰り返す（ゼクエンツ）。主題（a・a2 のカノン型の
8小節）は曲の中で戻ってくる。各区間の和声は役割が決まっているので進行は宣言順に固定する。"""
from __future__ import annotations

import dataclasses

from ..core.composer import NoteEvent, RhythmMotif, ScaleRules, articulate
from ..core.midi import GmVoice
from ..core.model import ChordSpec
from ..core.pitch import MODES, Scale, fold_into_range
from ..profiles.band_common import (
    ArpSpec, BandProfile, BassSpec, ChannelDef, LeadSpec, PadSpec, Section, _scale_vol, hits, preset,
)
from ..profiles.registry import register_profile

C = ChordSpec
CH_PERC, CH_HARP, CH_BASS, CH_STR, CH_LEAD, CH_BRASS = range(6)

MARCH = hits("snare", (4, 12), 22) + hits("snare", (14, 15), 16, 0.5)
FILL = hits("snare", (8, 10, 12, 13, 14, 15), 34)
FANFARE = ((0, 2, 3, 4, 8), (0, 4, 8), (0, 2, 3, 4, 8), (0,))   # イントロの金管（measure ごとの row）
COUNTER_REGISTER = (14, 26)

LEAD_MOTIFS = {
    "verse": (RhythmMotif((0, 4, 6, 8, 12)), RhythmMotif((0, 2, 4, 8, 12)), RhythmMotif((0, 6, 8, 10, 12))),
    "bridge": (RhythmMotif((0, 8, 12)), RhythmMotif((0, 4, 8)), RhythmMotif((0, 6, 8, 14))),
}
P_CANON1, P_CANON2, P_BRIDGE, P_ADVENTURE = range(4)
ORCH = frozenset({"drums", "bass", "arp", "pad"})


@register_profile
class JrpgProfile(BandProfile):
    id = "jrpg"
    category = "style"
    display_name = "JRPG Game Music"
    description = "ゲーム音楽風（JRPG）。旋律を重視した冒険のテーマ、ハープと弦とホルン"
    description_en = "JRPG game music style: melodic adventure theme with harp, strings and horn"
    title = "Field of Adventure"
    default_filename = "JRPG.mod"
    tempo_choices = (96, 100, 104, 108, 112, 116, 120)

    KIT = (
        ("timp", preset("orch_timpani")), ("snare", preset("march_snare")), ("harp", preset("keys_harp")),
        ("cello", preset("orch_cello")), ("flute", preset("wind_flute")), ("tpt", preset("orch_trumpet")),
        ("brass", preset("march_brass_section", volume=38)),
    )
    CHORD_KITS = {"str": (preset("orch_violin", name="StringPad", volume=30), 0.0)}
    GM = {"str": GmVoice(program=48)}
    CHANNELS = (
        ChannelDef("timpani/snare", ("timp", "snare"), (("timp", 2),), pan=128),
        ChannelDef("harp", ("harp",), pan=84),
        ChannelDef("cello", ("cello",), pan=128),
        ChannelDef("strings", ("str",), pan=172),
        ChannelDef("melody", ("flute", "tpt"), pan=150),
        ChannelDef("brass", ("brass",), pan=100),
    )
    DRUM_CHANNEL = {"snare": CH_PERC}
    KEYS = (0, 2, 5)
    ARP_REGISTER = (17, 31)
    FIXED_PROGRESSIONS = True
    PROGRESSIONS = (
        ("canon I-V-vi-iii", (C(0, "maj", label="I"), C(7, "maj", label="V"), C(9, "min", label="vi"),
                              C(4, "min", label="iii"))),
        ("canon IV-I-IV-V", (C(5, "maj", label="IV"), C(0, "maj", label="I"), C(5, "maj", label="IV"),
                             C(7, "maj", label="V"))),
        ("vi-IV-V-I", (C(9, "min", label="vi"), C(5, "maj", label="IV"), C(7, "maj", label="V"), C(0, "maj", label="I"))),
        ("I-bVII-IV-I", (C(0, "maj", label="I"), C(10, "maj", label="bVII"), C(5, "maj", label="IV"),
                         C(0, "maj", label="I"))),
    )
    SECTIONS = {
        "intro": Section("intro", prog=P_ADVENTURE, intensity=0.9, parts=ORCH | {"fanfare"}),
        "a": Section("a", prog=P_CANON1, intensity=0.75, parts=ORCH | {"lead"}),
        "a2": Section("a2", prog=P_CANON2, intensity=0.8, parts=ORCH | {"lead"}, fill=True),
        "b": Section("b", prog=P_BRIDGE, intensity=0.85, parts=ORCH | {"lead", "counter"}, lead_motifs="bridge",
                     fill=True),
        "ending": Section("ending", prog=P_ADVENTURE, intensity=0.9, parts=ORCH | {"lead", "counter"}),
    }
    FORM = ("intro", "a", "a2", "b", "a", "a2", "ending")
    GROOVES = {"main": MARCH, "fill": FILL}
    BASS = BassSpec("cello", CH_BASS, kind="half", vol=46)
    PAD = PadSpec("str", CH_STR, vol=28)
    ARP = ArpSpec("harp", CH_HARP, rows=tuple(range(16)), vol=30, pattern="up")
    LEAD = LeadSpec("flute", CH_LEAD, ScaleRules(leap_probability=0.25, leap_semitones=(3, 4, 5, 7)), LEAD_MOTIFS,
                    vol=48, gate=0.9, vibrato=0x23)

    def lead_key(self, sec):
        return "tpt" if sec.kind == "b" else "flute"

    def lead(self, mctx, sec, st, rng, buf):
        """楽節の2小節目は1小節目の動機を1音階上げて繰り返す（ゼクエンツ）。それ以外は BandProfile の楽節。"""
        if mctx.measure_idx % 4 != 1 or "seq" not in st.extra:
            super().lead(mctx, sec, st, rng, buf)
            if mctx.measure_idx % 4 == 0:
                st.extra["seq"] = _read_events(buf, CH_LEAD, mctx.instruments[self.lead_key(sec)], mctx.measure_rows)
            return
        scale = Scale(mctx.pattern.extra["tonic"], MODES[self.MODE])
        lo, hi = self.REGISTERS.melody
        ladder = scale.notes_in(lo, hi)
        events = []
        for e in st.extra.pop("seq"):
            i = ladder.index(e.note) if e.note in ladder else None
            note = ladder[i + 1] if i is not None and i + 1 < len(ladder) else e.note
            events.append(dataclasses.replace(e, note=note))
        if events:
            st.lead_prev = events[-1].note
        articulate(buf, CH_LEAD, events, mctx.instruments[self.lead_key(sec)], gate=self.LEAD.gate)

    def extra_measure(self, mctx, sec, st, rng, buf):
        ins = mctx.instruments
        chord = mctx.chord
        m = mctx.measure_idx
        if self._is_chord_change(mctx) and m % 2 == 0:
            buf.put(0, CH_PERC, ins["timp"].cell(chord.bass, vol=_scale_vol(44, sec)))
        if "fanfare" in sec.parts:
            brass = ins["brass"]
            tones = [t for t in range(*COUNTER_REGISTER) if t % 12 in {c % 12 for c in chord.chord_tones}]
            for i, row in enumerate(FANFARE[m % 4]):
                note = tones[-1] if row == 0 and m % 4 == 3 else tones[min(i, len(tones) - 1)]
                buf.put(row, CH_BRASS, brass.cell(note, vol=_scale_vol(46, sec)))
            if m % 4 != 3:
                buf.put(12, CH_BRASS, brass.off())
        elif "counter" in sec.parts:
            if self._is_chord_change(mctx):
                third = sorted({t % 12 for t in chord.chord_tones}, key=lambda pc: (pc - chord.harmony) % 12)[1]
                buf.put(0, CH_BRASS, ins["brass"].cell(fold_into_range(third, *COUNTER_REGISTER),
                                                       vol=_scale_vol(34, sec)))
        elif m == 0:
            buf.put(0, CH_BRASS, ins["brass"].off())


def _read_events(buf, ch: int, inst, rows: int) -> list[NoteEvent]:
    """書いたばかりの旋律を measure から読み戻す（ゼクエンツの素材）。"""
    starts = [(r, buf.get(r, ch)) for r in range(rows) if buf.get(r, ch).note is not None]
    out = []
    for k, (r, cell) in enumerate(starts):
        end = starts[k + 1][0] if k + 1 < len(starts) else rows
        out.append(NoteEvent(r, cell.note + inst.spec.shift, cell.vol or 40, end - r))
    return out
