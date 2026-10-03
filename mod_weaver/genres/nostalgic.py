"""nostalgic（旧 genres/nostalgic.py の移植。DESIGN.md §6 のグループC）。

和音は手組みの ``ChordDef(explicit=True)``（白鍵だけのメジャー7th・ドミナント7th）なので ``harmony=None`` とし、
``plan()`` で ``MeasurePlan.chord`` を直接作る（march と同じ）。旋律は旧 ``_melody_bar``（コードトーンと対位法の規則）を
ジェネレータに移した。旧版の挙動 Q1〜Q7（アウトロの row 0 がテンポセルで上書きされる、サビのオクターブシフトの頭打ちなど）は
保たない（D9）が、Q5（サビの旋律が B-3 を超えない）は音域の安全のため残してある。Q4 の未使用の flute は楽器から外した。
Q3（pad のループの −17.6 セント）は音色の値の問題なので本移植では変えない。
"""
from __future__ import annotations

import random
from typing import Optional

from ..core import pitch
from ..core.model import ChordDef, GmVoice
from ..core.pitch import MODES, Scale
from ..core.synth_presets import PRESETS
from ..framework.context import Generator, MeasureCtx, SectionCtx
from ..framework.genre import Genre, Instrument, Kit, Part, Section
from ..framework.plan import MeasurePlan, Meter, SectionPlan, SongPlan
from ..framework.registry import register_genre

C3 = pitch.parse("C-3")
METER = Meter(steps=16, steps_per_beat=4)
MEASURES = 4

# 旧 SCALE_NOTES（C-2..B-3 の白鍵 14 音）。旋律は、このリスト上の位置（音階度数）で距離を測る
SCALE_NOTES = [pitch.parse(n) for n in (
    "C-2", "D-2", "E-2", "F-2", "G-2", "A-2", "B-2",
    "C-3", "D-3", "E-3", "F-3", "G-3", "A-3", "B-3",
)]

_CHORD_SRC = {
    "Fmaj7": ("F-2", "C-3", ["A-2", "C-3", "E-3", "A-3"], ["A-2", "C-3", "D-3", "E-3", "G-3", "A-3"]),
    "Em7": ("E-2", "B-2", ["G-2", "B-2", "D-3", "G-3"], ["B-2", "C-3", "D-3", "E-3", "G-3", "A-3"]),
    "Dm7": ("D-2", "A-2", ["F-2", "A-2", "C-3", "F-3"], ["A-2", "C-3", "D-3", "E-3", "F-3", "A-3"]),
    "Cmaj7": ("C-2", "G-2", ["E-2", "G-2", "B-2", "C-3", "E-3"], ["G-2", "A-2", "B-2", "C-3", "D-3", "E-3", "G-3"]),
    "G7": ("G-2", "D-3", ["B-2", "D-3", "F-3", "G-3"], ["B-2", "C-3", "D-3", "E-3", "F-3", "G-3"]),
    "Am7": ("A-2", "E-3", ["C-3", "E-3", "G-3", "A-3"], ["A-2", "B-2", "C-3", "D-3", "E-3", "G-3", "A-3"]),
}
CHORD_DEFS: dict[str, ChordDef] = {
    name: ChordDef(label=name, bass=pitch.parse(root), harmony=pitch.parse(pad),
                   chord_tones=tuple(pitch.parse(n) for n in ct), scale_tones=tuple(pitch.parse(n) for n in st),
                   explicit=True)
    for name, (root, pad, ct, st) in _CHORD_SRC.items()
}
_QUALITY = {"Fmaj7": "maj7", "Em7": "m7", "Dm7": "m7", "Cmaj7": "maj7", "G7": "dom7", "Am7": "m7"}

PROGRESSION_PRESETS = [
    ("Step-Down (Nostalgic Descent)", ["Fmaj7", "Em7", "Dm7", "Cmaj7"]),
    ("Royal Road (Classic Emotion)", ["Fmaj7", "G7", "Em7", "Am7"]),
    ("Saudade (Sentimental Sunset)", ["Dm7", "G7", "Cmaj7", "Am7"]),
    ("Journey (Memories & Depart)", ["Am7", "Fmaj7", "Cmaj7", "G7"]),
    ("Canon Sunset (Warm Twilight)", ["Cmaj7", "G7", "Am7", "Em7"]),
]
RHYTHM_MOTIFS = [[0, 4, 6, 10, 12], [0, 6, 10, 14], [0, 4, 8, 12], [0, 3, 6, 10, 12], [0, 6, 8, 12]]


def _shift_octave(note: int, octave_shift: int) -> int:
    """サビのオクターブシフト（``min(3, octave+shift)`` で頭打ち）。"""
    octave, pc = note // 12 + 1, note % 12
    return (min(3, octave + octave_shift) - 1) * 12 + pc


def _scale_pos(note: int) -> int:
    return SCALE_NOTES.index(note)


def _melody_bar(rng: random.Random, chord: ChordDef, rhythm: list[int], prev_note: Optional[int],
                octave_shift: int, is_cadence: bool) -> tuple[list[tuple[int, int, int]], Optional[int]]:
    """コードトーンと対位法ルールに基づく1小節の旋律（旧 ``generate_melody_bar``）。``(step, note, vol)`` の列。"""
    chord_tones = list(chord.chord_tones)
    scale_tones = list(chord.scale_tones)
    if octave_shift > 0:
        chord_tones = [_shift_octave(n, octave_shift) for n in chord_tones]
        scale_tones = [_shift_octave(n, octave_shift) for n in scale_tones]

    notes = []
    current = prev_note
    for idx, row in enumerate(rhythm):
        if idx == 0:
            if current is None:
                note = rng.choice(chord_tones)
            else:
                ranked = sorted(chord_tones, key=lambda n: abs(_scale_pos(n) - _scale_pos(current)))
                note = ranked[0] if rng.random() < 0.75 else ranked[min(1, len(ranked) - 1)]
        elif idx == len(rhythm) - 1 and is_cadence:
            note = chord_tones[0] if chord_tones else C3
        else:
            curr_idx = _scale_pos(current)
            if rng.random() < 0.75:
                step = rng.choice([-1, 1, -2, 2])
                target_idx = max(0, min(len(SCALE_NOTES) - 1, curr_idx + step))
                cand = SCALE_NOTES[target_idx]
                note = cand if cand in scale_tones else min(scale_tones, key=lambda s: abs(_scale_pos(s) - target_idx))
            else:
                note = rng.choice(chord_tones)
        current = note
        notes.append((row, note, 60 if idx == 0 else rng.randint(48, 56)))
    return notes, current


# ============================================================
# ジャンル内のジェネレータ
# ============================================================

class NostalgicDrums(Generator):
    def section(self, ctx: SectionCtx) -> None:
        ctx.state["ghost"] = ctx.rng.random() < 0.5
        super().section(ctx)

    def measure(self, m: MeasureCtx) -> None:
        kind, bar = m.plan.kind, m.m.index
        if kind == "intro":
            return
        if kind == "outro":                  # 静かなキックのみ
            if bar < 2:
                m.note(0, "kick", vel=46 - bar * 10)
                m.note(8, "kick", vel=40 - bar * 10)
            return
        hits: dict[int, tuple[str, int]] = {}     # 同じ step は後から書いたものが勝つ（旧版の上書き）
        for step in range(0, 16, 2):
            if step in (0, 8):
                hits[step] = ("kick", 56)
            elif step in (4, 12):
                hits[step] = ("snare", 50)
            else:
                hits[step] = ("hihat", 40)
            hits[step + 1] = ("hihat", 30)        # 裏拍ハイハット
        if m.state["ghost"] and kind == "b":
            hits[15] = ("hihat", 24)
        if bar == 3:                              # 小節末フィル
            hits[14] = ("hihat", 34)
            hits[15] = ("snare", 46)
        for step, (inst, vol) in sorted(hits.items()):
            m.note(step, inst, vel=vol)


class NostalgicBass(Generator):
    def measure(self, m: MeasureCtx) -> None:
        kind = m.plan.kind
        if kind == "intro":
            return
        chord = m.m.chord
        outro = kind == "outro"
        m.note(0, "bass", chord.bass, vel=60 if not outro else 50 - m.m.index * 8)
        if not outro:
            m.note(8, "bass", chord.bass, vel=54)
            if m.rng.random() < 0.6:
                m.note(12, "bass", chord.chord_tones[0], vel=50)


class NostalgicPad(Generator):
    def measure(self, m: MeasureCtx) -> None:
        outro = m.plan.kind == "outro"
        m.note(0, "pad", m.m.chord.harmony, vel=46 if not outro else max(10, 42 - m.m.index * 8))
        if outro and m.is_last:                   # フェードアウト
            m.automate(8, "volume", 18, inst="pad")
            m.automate(12, "volume", 8, inst="pad")
            m.automate(15, "volume", 0, inst="pad")


class NostalgicMelody(Generator):
    def section(self, ctx: SectionCtx) -> None:
        motif_a = ctx.rng.choice(RHYTHM_MOTIFS)
        motif_b = ctx.rng.choice(RHYTHM_MOTIFS)
        ctx.state["rhythms"] = [motif_a, motif_a, motif_b, [0, 6, 10, 14] if ctx.plan.kind != "outro" else [0, 8]]
        ctx.state["prev"] = None
        super().section(ctx)

    def measure(self, m: MeasureCtx) -> None:
        kind, bar = m.plan.kind, m.m.index
        notes, m.state["prev"] = _melody_bar(m.rng, m.m.chord, m.state["rhythms"][bar], m.state["prev"],
                                              1 if kind == "b" else 0, bar == 3)
        for step, note, vol in notes:
            if kind == "intro":
                vol = max(38, vol - 6)
            elif kind == "outro":
                vol = max(30, vol - bar * 5)
            m.note(step, "musicbox", note, vel=vol)


def _inst(key: str, gm: GmVoice) -> Instrument:
    return Instrument(patch=PRESETS[key], gm=gm)


@register_genre
class NostalgicGenre(Genre):
    id = "nostalgic"
    category = "style"
    display_name = "TwilightPad Procedural"
    description = "夕暮れの郷愁を誘う Lo-Fi ビートとオルゴール（従来の TwilightPad）"
    description_en = "Lo-fi beat and music box evoking nostalgia at dusk (the original TwilightPad)"
    title = "Twilight Pad"
    tempo_choices = (88, 90, 92, 94, 96)

    instruments = {
        "kick": _inst("nostalgic_kick", GmVoice(drum_note=36)),
        "snare": _inst("nostalgic_snare", GmVoice(drum_note=38)),
        "hihat": _inst("nostalgic_hihat", GmVoice(drum_note=42)),
        "bass": _inst("nostalgic_bass", GmVoice(program=33)),
        "musicbox": _inst("nostalgic_musicbox", GmVoice(program=10)),
        "pad": _inst("nostalgic_pad", GmVoice(program=89)),
    }
    harmony = None   # 和音は手組みの ChordDef。plan() を全面的に上書きする
    sections = {
        "intro": Section(meter=METER, measures=MEASURES, intensity=0.5, parts=frozenset({"pad", "melody"})),
        "a": Section(meter=METER, measures=MEASURES),
        "b": Section(meter=METER, measures=MEASURES),
        "outro": Section(meter=METER, measures=MEASURES, intensity=0.5),
    }
    form = ("intro", "a", "b", "a", "outro")
    parts = (
        Part("drums", NostalgicDrums(), pan=128,
             kit=Kit(groups=(("drums", ("kick", "snare", "hihat")),), priority={"snare": 2, "kick": 2, "hihat": 1})),
        Part("bass", NostalgicBass(), pan=128),
        Part("pad", NostalgicPad(), pan=80),
        Part("melody", NostalgicMelody(), pan=176),
    )
    mod_channels = {4: 1}

    def plan(self, rng: random.Random) -> SongPlan:
        # 乱数の消費順: randrange → randint → choice
        idx_a = rng.randrange(len(PROGRESSION_PRESETS))
        idx_b = (idx_a + rng.randint(1, len(PROGRESSION_PRESETS) - 1)) % len(PROGRESSION_PRESETS)
        name_a, prog_a = PROGRESSION_PRESETS[idx_a]
        name_b, prog_b = PROGRESSION_PRESETS[idx_b]
        bpm = rng.choice(list(self.tempo_choices))
        scale = Scale(0, MODES["ionian"])
        everything = frozenset(p.name for p in self.parts)

        def section(name: str, prog: list[str]) -> SectionPlan:
            sec = self.sections[name]
            chords = [CHORD_DEFS[c] for c in prog]
            measures = tuple(
                MeasurePlan(index=i, start=i * METER.steps, steps=METER.steps, chord=chords[i], quality=_QUALITY[prog[i]],
                            chord_offset=0, next_chord=chords[(i + 1) % len(chords)]) for i in range(len(chords)))
            return SectionPlan(name=name, kind=name, meter=METER, measures=measures, intensity=sec.intensity,
                               key_offset=0, tonic=0, scale=scale, parts=sec.parts or everything, swing=None,
                               section=sec, extra={})

        sections = {"intro": section("intro", prog_a), "a": section("a", prog_a), "b": section("b", prog_b),
                    "outro": section("outro", prog_a)}
        summary = [f"Theme A     : {name_a} -> {' - '.join(prog_a)}",
                   f"Theme B     : {name_b} -> {' - '.join(prog_b)}"]
        return SongPlan(bpm=bpm, key_pc=0, sections=sections, order=list(self.form), summary=summary)
