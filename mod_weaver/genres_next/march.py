"""march（旧 genres/march.py の移植。FRAMEWORK_REDESIGN.md §15.4 のグループC）。

F3 の試験移植を F7 で本番に昇格した。旧 ``mod_weaver/genres/march.py``（``MarchProfile``）は
``GenreProfile`` の素の機構を直接使う個別実装で、1 つの「区間ぶんの文法」関数が drums・tuba・harm・picc の
4 チャンネルすべてを同時に書いていた。新フレームワークは1パート=1ジェネレータなので、その文法を
``MarchDrums``・``MarchTuba``・``MarchHarm``・``MarchPicc`` の4つに分けて書き直す（§15.4 の想定どおり、
同じ「どの measure で何を鳴らすか」の条件分岐が複数のジェネレータに現れるが、ジャンル固有の文法なので
部品化はしない）。

和声は ``Harmony``/``default_plan()`` を使わず（進行の各和音の小節数が不揃いなため。sousa の最後の和音だけ
2 小節など）、``plan()`` を全面的に上書きして ``SectionPlan`` を直接組み立てる（nostalgic と同じ扱い）。
"""
from __future__ import annotations

import random
from typing import Optional

from ..core.composer import MelodyGenerator, NoteEvent as OldNoteEvent, RhythmMotif, ScaleRules
from ..core.harmony import Registers, voice
from ..core.model import ChordSpec, GmVoice
from ..core.pitch import MODES, Scale, fold_into_range
from ..core.synth_presets import PRESETS
from ..framework.context import Generator, MeasureCtx, SectionCtx
from ..framework.genre import Genre, Instrument, Kit, Part, Section
from ..framework.plan import Meter, MeasurePlan, SectionPlan, SongPlan
from ..framework.registry import register_genre
from ..framework.score import Arpeggio, Vibrato

C = ChordSpec


def _inst(key: str, gm: GmVoice) -> Instrument:
    return Instrument(patch=PRESETS[key], gm=gm)


# ============================================================
# 音域・調・進行（旧 march.py の値をそのまま）
# ============================================================

KEY_CHOICES = (0, 5, 10, 3)
TRIO_OFFSET = 5
BASS_REG = (0, 11)
HARMONY_REG = (17, 28)
MELODY_MAIN = (24, 43)
MELODY_TRIO = (19, 38)
MELODY_TRIO2 = (31, 47)
REGISTERS = Registers(bass=BASS_REG, harmony=HARMONY_REG, melody=MELODY_MAIN)

STRAIN_RULES = ScaleRules(step_choices=(-1, 1, -2, 2), leap_probability=0.30, leap_semitones=(4, 5, 7),
                           leap_recovery=True, dissonance_weight=0.05)
TRIO_RULES = ScaleRules(step_choices=(-1, 1, -2, 2), leap_probability=0.15, leap_semitones=(4, 5, 7),
                         leap_recovery=True, dissonance_weight=0.05, strong_nearest_prob=0.85)

PROGRESSION_TITLES = {"sousa": "Sousa Classic", "heroic": "Heroic Fanfare", "trio": "Trio Uplift"}
PROGRESSIONS: dict[str, list[tuple[ChordSpec, int]]] = {
    "sousa": [
        (C(0, "maj"), 1), (C(7, "dom7"), 1), (C(0, "maj"), 1), (C(5, "maj"), 1),
        (C(0, "maj", bass=7), 1), (C(7, "dom7"), 1), (C(0, "maj"), 2),
    ],
    "heroic": [
        (C(0, "maj"), 1), (C(5, "maj"), 1), (C(7, "maj"), 1), (C(0, "maj"), 1),
        (C(9, "min"), 1), (C(2, "min"), 1), (C(7, "dom7"), 1), (C(0, "maj"), 1),
    ],
    "trio": [
        (C(0, "maj"), 1), (C(0, "maj"), 1), (C(7, "dom7"), 1), (C(0, "maj"), 1),
        (C(5, "maj"), 1), (C(0, "maj"), 1), (C(7, "dom7"), 1), (C(0, "maj"), 1),
    ],
}

MARCH_MOTIFS = (RhythmMotif((0, 6)), RhythmMotif((0, 3, 4, 7)), RhythmMotif((0, 2, 4, 6)), RhythmMotif((0, 4)))
HOLD_MOTIF = RhythmMotif((0,))
PHRASE_SLOTS = ("a", "a2", "b", "c", "a", "a2", "b", "cad")
VIBRATO_PARAM = 0x46


def _voice_progression(name: str, tonic_pc: int):
    """``PROGRESSIONS[name]`` を具体化し、小節ごとの ``(ChordDef, chord_offset)`` の列にする
    （同じ和音が続く小節数ぶん複製する。和音の変わり目が ``chord_offset=0``）。"""
    scale = Scale(tonic_pc, MODES["ionian"])
    chords = []
    offsets = []
    for spec, measures in PROGRESSIONS[name]:
        chord = voice(spec, tonic_pc, scale, REGISTERS, arp=True)
        chords.extend([chord] * measures)
        offsets.extend(range(measures))
    return chords, offsets


def _progression_summary(label: str, name: str, tonic_pc: int) -> str:
    scale = Scale(tonic_pc, MODES["ionian"])
    chords = " - ".join(voice(spec, tonic_pc, scale, REGISTERS, arp=True).label for spec, _m in PROGRESSIONS[name])
    return f"{label:<16}: {PROGRESSION_TITLES[name]} -> {chords}"


def _section_plan(name: str, kind: str, prog_name: str, intensity: float, key_offset: int, tonic: int,
                   section_decl: Section) -> SectionPlan:
    chords, offsets = _voice_progression(prog_name, tonic)
    n = len(chords)
    measures = []
    start = 0
    for i in range(n):
        nxt = chords[(i + 1) % n]
        spec_quality = PROGRESSIONS[prog_name][0][0].quality   # 表示用。実査読では使わない
        measures.append(MeasurePlan(index=i, start=start, steps=8, chord=chords[i], quality=spec_quality,
                                     chord_offset=offsets[i], next_chord=nxt))
        start += 8
    scale = Scale(tonic, MODES["ionian"])
    return SectionPlan(name=name, kind=kind, meter=Meter(steps=8, steps_per_beat=4, signature=(2, 4)),
                        measures=tuple(measures), intensity=intensity, key_offset=key_offset, tonic=tonic,
                        scale=scale, parts=frozenset({"drums", "tuba", "harm", "picc"}), swing=None,
                        section=section_decl, extra={})


# ============================================================
# ジャンル内のジェネレータ（drums・tuba・harm・picc。§15.4）
# ============================================================

class MarchDrums(Generator):
    def measure(self, m: MeasureCtx) -> None:
        kind = m.plan.kind
        if kind == "intro":
            if m.m.index == 0:
                m.note(0, "crash", vel=64)
            elif m.m.index == 3:
                m.note(4, "sd", vel=30)
            elif m.m.index >= 4:
                m.note(0, "bd", vel=60)
                m.note(4, "sd", vel=50)
            return
        if kind in ("a", "a2"):
            m.note(0, "bd", vel=60)
            m.note(4, "sd", vel=50)
            if m.is_first:
                m.note(0, "crash", vel=64)
            if m.is_last:
                self._snare_roll(m)
            return
        if kind == "trio":
            m.note(0, "bd", vel=48)
            m.note(4, "sd", vel=38)
            return
        if kind == "trio2":
            m.note(0, "bd", vel=60)
            m.note(4, "sd", vel=50)
            if m.m.index == 4:
                m.note(0, "crash", vel=64)
            if m.is_last:
                self._snare_roll(m)
            return
        if kind == "coda":
            m.note(0, "bd", vel=60)                 # 最終 measure は crash が Kit.priority で勝つ
            if m.is_last:
                m.note(0, "crash", vel=64)
            else:
                m.note(4, "sd", vel=50)
                if m.is_first:
                    m.note(0, "crash", vel=64)
            return
        raise ValueError(kind)

    @staticmethod
    def _snare_roll(m: MeasureCtx) -> None:
        """フレーズ末の4連打（vol 36→58）。row4 の通常スネアと同じ (inst, step) に ``prio=2`` で
        勝つ（§9.5・§15.4: 現行の ``buf.replace`` に相当）。"""
        for i, row in enumerate(range(4, 8)):
            vol = round(36 + (58 - 36) * i / 3)
            m.note(row, "sd", vel=vol, prio=2)


class MarchTuba(Generator):
    def __init__(self, inst: str = "tuba") -> None:
        self.inst = inst

    def measure(self, m: MeasureCtx) -> None:
        if m.plan.kind == "intro" and m.m.index < 4:
            return
        chord = m.m.chord
        note = chord.bass if m.m.chord_offset % 2 == 0 else fold_into_range(chord.bass + 7, *BASS_REG)
        m.note(0, self.inst, note, vel=60)


class MarchHarm(Generator):
    def measure(self, m: MeasureCtx) -> None:
        kind = m.plan.kind
        chord = m.m.chord
        intensity = m.plan.intensity
        if kind == "intro":
            if m.m.index == 0:
                self._section(m, chord)
            elif m.m.index >= 4:
                self._horn(m, chord, intensity)
            return
        if kind in ("a", "a2", "trio"):
            self._horn(m, chord, intensity)
            return
        if kind == "trio2":
            self._horn(m, chord, intensity)
            if m.m.index <= 3:
                self._section(m, chord)
            return
        if kind == "coda":
            if m.is_last:
                self._section(m, chord)
            else:
                self._horn(m, chord, intensity)
            return
        raise ValueError(kind)

    @staticmethod
    def _horn(m: MeasureCtx, chord, intensity: float) -> None:
        if intensity >= 0.7 and chord.arp:
            x, y = chord.arp >> 4, chord.arp & 0xF
            m.note(4, "horn", chord.harmony, arts=(Arpeggio(x, y),))
        elif intensity >= 0.7:
            m.note(4, "horn", chord.harmony)
        else:
            m.note(4, "horn", chord.harmony, vel=34)

    @staticmethod
    def _section(m: MeasureCtx, chord) -> None:
        if chord.arp:
            x, y = chord.arp >> 4, chord.arp & 0xF
            m.note(0, "section", chord.harmony, dur=None, arts=(Arpeggio(x, y),))
        else:
            m.note(0, "section", chord.harmony, dur=None)


def _fanfare_events(chord, reg: tuple[int, int], vol: int) -> list[OldNoteEvent]:
    """rows (0,2,4,6) で主音→3度→5度→オクターブ上を駆け上がる（register を超えないよう clamp）。"""
    lo, hi = reg
    base = fold_into_range(chord.chord_tones[0], lo, hi)
    notes = [min(base + iv, hi) for iv in (0, 4, 7, 12)]
    return [OldNoteEvent(r, n, vol, 2) for r, n in zip((0, 2, 4, 6), notes)]


class MarchPicc(Generator):
    def __init__(self, inst: str = "picc") -> None:
        self.inst = inst

    def section(self, ctx: SectionCtx) -> None:
        kind = ctx.plan.kind
        if kind == "intro":
            for m in ctx.measures():
                self._emit(m, _fanfare_events(m.m.chord, MELODY_MAIN, vol=52))
            return

        reg, rules = {"trio": (MELODY_TRIO, TRIO_RULES),
                      "trio2": (MELODY_TRIO2, STRAIN_RULES),
                      "coda": (MELODY_TRIO2, STRAIN_RULES)}.get(kind, (MELODY_MAIN, STRAIN_RULES))
        gen = MelodyGenerator(rules, reg, ctx.plan.scale, ctx.rng, base_vol=50)
        prev: Optional[int] = None
        last_a_motif: Optional[RhythmMotif] = None
        for m in ctx.measures():
            slot = PHRASE_SLOTS[m.m.index]
            chord = m.m.chord
            if slot == "c":
                events = _fanfare_events(chord, reg, vol=54)
                prev = events[-1].note
            elif slot == "cad":
                events, prev = gen.bar(HOLD_MOTIF, chord, prev, cadence=True,
                                        cadence_target=chord.chord_tones[0], rows=8)
            else:
                if slot == "a2" and last_a_motif is not None:
                    motif = last_a_motif
                else:
                    motif = ctx.rng.choice(MARCH_MOTIFS)
                    if slot == "a":
                        last_a_motif = motif
                events, prev = gen.bar(motif, chord, prev, rows=8)
            self._emit(m, events)

    def _emit(self, m: MeasureCtx, events: list[OldNoteEvent]) -> None:
        for ev in events:
            dur = max(1, round(ev.dur * 0.9))   # gate=0.9（現行の articulate と同じ）
            arts = (Vibrato(VIBRATO_PARAM),) if ev.dur >= 4 else ()
            m.note(ev.row, self.inst, ev.note, vel=ev.vol, dur=dur, arts=arts)


# ============================================================
# ジャンル本体
# ============================================================

GM_VOICES = {
    "bd": GmVoice(drum_note=36), "sd": GmVoice(drum_note=38), "crash": GmVoice(drum_note=49),
    "tuba": GmVoice(program=58), "horn": GmVoice(program=60), "section": GmVoice(program=61),
    "picc": GmVoice(program=72),
}


@register_genre
class MarchGenre(Genre):
    id = "march"
    category = "style"
    display_name = "Military March"
    description = "行進曲。Oom-Pah とスネアロール、ファンファーレ、トリオへの転調"
    description_en = "Military march: oom-pah and snare rolls, fanfares, modulation into the trio"
    title = "Military March"
    tempo_choices = (118, 119, 120, 121, 122)

    instruments = {
        "bd": _inst("march_bass_drum", GM_VOICES["bd"]),
        "sd": _inst("march_snare", GM_VOICES["sd"]),
        "crash": _inst("march_crash_cymbal", GM_VOICES["crash"]),
        "tuba": _inst("march_tuba_bass", GM_VOICES["tuba"]),
        "horn": _inst("march_brass_horn", GM_VOICES["horn"]),
        "section": _inst("march_brass_section", GM_VOICES["section"]),
        "picc": _inst("march_piccolo_lead", GM_VOICES["picc"]),
    }
    harmony = None   # 和声は進行ごとに小節数が不揃いなので plan() を全面的に上書きする（nostalgic と同じ）
    sections = {name: Section(meter=Meter(steps=8, steps_per_beat=4, signature=(2, 4)))
                for name in ("intro", "a", "a2", "trio", "trio2", "coda")}
    form = ("intro", "a", "a2", "a", "a2", "trio", "trio2", "trio", "trio2", "coda")
    parts = (
        Part("drums", MarchDrums(), pan=128,
             kit=Kit(groups=(("drums", ("bd", "sd", "crash")),), priority={"crash": 3, "sd": 2})),
        Part("tuba", MarchTuba("tuba"), pan=128),
        Part("harm", MarchHarm(), pan=160,
             kit=Kit(groups=(("harm", ("horn", "section")),), priority={"section": 2})),
        Part("picc", MarchPicc("picc"), pan=96),
    )
    mod_channels = {4: 1}   # 現行どおり 4ch 専用（§15.4。6ch・8ch 用の追加パートは本移植の範囲外）

    def plan(self, rng: random.Random) -> SongPlan:
        key_pc = rng.choice(KEY_CHOICES)
        bpm = rng.choice(list(self.tempo_choices))
        trio_pc = (key_pc + TRIO_OFFSET) % 12

        sections = {
            "intro": _section_plan("intro", "intro", "heroic", 0.8, 0, key_pc, self.sections["intro"]),
            "a": _section_plan("a", "a", "sousa", 0.7, 0, key_pc, self.sections["a"]),
            "a2": _section_plan("a2", "a2", "heroic", 0.75, 0, key_pc, self.sections["a2"]),
            "trio": _section_plan("trio", "trio", "trio", 0.5, TRIO_OFFSET, trio_pc, self.sections["trio"]),
            "trio2": _section_plan("trio2", "trio2", "trio", 0.85, TRIO_OFFSET, trio_pc, self.sections["trio2"]),
            "coda": _section_plan("coda", "coda", "heroic", 1.0, 0, key_pc, self.sections["coda"]),
        }
        order = ["intro", "a", "a2", "a", "a2", "trio", "trio2", "trio", "trio2", "coda"]
        summary = [
            _progression_summary("Strain (Sousa)", "sousa", key_pc),
            _progression_summary("Strain (Heroic)", "heroic", key_pc),
            _progression_summary("Trio", "trio", trio_pc),
        ]
        return SongPlan(bpm=bpm, key_pc=key_pc, sections=sections, order=order, summary=summary)
