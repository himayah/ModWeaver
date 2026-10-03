"""suspense-slow・suspense-chase の共通部分（音色・和声・語彙。FRAMEWORK_REDESIGN.md §15.4）。

ジャンルではない（``_`` 始まりなので ``discover()`` は読み込まない）。旧 ``profiles/suspense_common.py`` の移植。
両ジャンルは ``plan()`` と各区間の文法（パートごとのジェネレータ）だけを別に書く。

編成は旧版の4チャンネルそのまま: pulse（kit: heart・anvil・swoosh。優先度 anvil＞swoosh＞heart）、drone、
texture（kit: strings・pizz。pizz が優先）、lead（kit: lead・pizz。pizz が優先）。
"""
from __future__ import annotations

import math
from typing import Optional

from ..core.composer import MelodyGenerator, ScaleRules
from ..core.harmony import Registers, voice
from ..core.model import ChordDef, ChordSpec, GmVoice
from ..core.pitch import MODES, Scale, lowest_note_with_pc
from ..core.synth_presets import PRESETS
from ..framework.context import MeasureCtx
from ..framework.genre import Instrument, Kit, Section
from ..framework.plan import MeasurePlan, Meter, SectionPlan
from ..framework.score import Arpeggio

KEY_PC = 0                                   # 主調 C
BASS_REG = (0, 11)                           # drone（shift −24 → t=24..35）
HARMONY_REG = (17, 28)                       # strings のアルペジオ基音（arp 最大 +7 でも t ≤ 35）
PIZZ_REG = (24, 35)                          # pizz（shift 0）
LEAD_REG = (24, 41)                          # lead（shift +12 → t=12..29）
REGISTERS = Registers(bass=BASS_REG, harmony=HARMONY_REG, melody=LEAD_REG)
PHRYGIAN = Scale(KEY_PC, MODES["phrygian"])
MODE_BY_QUALITY = {"dim": "dim_wh"}
METER = Meter(steps=16, steps_per_beat=4)
MEASURES = 4

# (root, quality, bass) — 主音 C 基準
PROGRESSIONS: dict[str, tuple[str, list[ChordSpec]]] = {
    "pedal": ("Pedal Tone Terror", [
        ChordSpec(0, "dim"), ChordSpec(1, "maj", 0), ChordSpec(0, "dim"), ChordSpec(11, "maj", 0),
    ]),
    "tritone": ("Tritone Nightmare", [
        ChordSpec(0, "min"), ChordSpec(6, "dim"), ChordSpec(5, "min"), ChordSpec(11, "dim"),
    ]),
    "phrygian": ("Phrygian Suspense", [
        ChordSpec(0, "min"), ChordSpec(1, "maj7"), ChordSpec(10, "min"), ChordSpec(0, "maj"),
    ]),
}

SWOOSH_SEC = 0.9        # swoosh の長さ（秒）
SHOCK_GUARD_ROWS = 8    # anvil の直前にこの step 数だけ heart/pizz/lead の発音を置かない
ANVIL_RING_SEC = 0.6    # anvil の余韻としてこの秒数は pulse の lane を心拍で切らない（lane は 1 音しか鳴らせない）


def _inst(key: str, gm: GmVoice) -> Instrument:
    return Instrument(patch=PRESETS[key], gm=gm)


INSTRUMENTS = {
    "heart": _inst("sub_heartbeat", GmVoice(drum_note=35)),
    "anvil": _inst("metal_anvil", GmVoice(program=14)),
    "swoosh": _inst("noise_swoosh", GmVoice(program=122)),
    "drone": _inst("low_drone_bass", GmVoice(program=95)),
    "pizz": _inst("pizz_stab", GmVoice(program=45)),
    "strings": _inst("tension_strings", GmVoice(program=44)),
    "lead": _inst("screaming_lead", GmVoice(program=81)),
}

PULSE_KIT = Kit(groups=(("pulse", ("heart", "anvil", "swoosh")),), priority={"anvil": 3, "swoosh": 2, "heart": 1})
TEXTURE_KIT = Kit(groups=(("texture", ("strings", "pizz")),), priority={"strings": 1, "pizz": 2})
LEAD_KIT = Kit(groups=(("lead", ("lead", "pizz")),), priority={"lead": 1, "pizz": 2})

PAN_PULSE, PAN_DRONE, PAN_TEXTURE, PAN_LEAD = 128, 128, 176, 80


# ============================================================
# 計画の補助
# ============================================================

def voice_progression(name: str) -> list[ChordDef]:
    return [voice(spec, KEY_PC, PHRYGIAN, REGISTERS, arp=True, mode_by_quality=MODE_BY_QUALITY)
            for spec in PROGRESSIONS[name][1]]


def progression_summary(label: str, name: str) -> str:
    chords = " - ".join(c.label for c in voice_progression(name))
    return f"{label:<12}: {PROGRESSIONS[name][0]} -> {chords}"


def section_plan(name: str, prog: str, section: Section, parts: frozenset[str], **extra) -> SectionPlan:
    """進行 ``prog`` を 1 小節 1 和音で並べた ``SectionPlan``（和声は手組みの ``voice(arp=True)``）。"""
    chords = voice_progression(prog)
    specs = PROGRESSIONS[prog][1]
    measures = tuple(
        MeasurePlan(index=i, start=i * METER.steps, steps=METER.steps, chord=chords[i], quality=specs[i].quality,
                    chord_offset=0, next_chord=chords[(i + 1) % len(chords)]) for i in range(len(chords)))
    return SectionPlan(name=name, kind=section.kind or name, meter=METER, measures=measures,
                       intensity=section.intensity, key_offset=0, tonic=KEY_PC, scale=PHRYGIAN, parts=parts,
                       swing=None, section=section, extra=dict(extra))


# ============================================================
# 共通語彙（DESIGN.md §6.2）
# ============================================================

def swoosh_start_row(m: MeasureCtx) -> int:
    """swoosh の開始 step。sample の終わりが小節末（＝直後の衝撃）に来るように逆算する。"""
    return m.m.steps - round(SWOOSH_SEC / m.step_seconds())


def anvil_clear_row(m: MeasureCtx) -> int:
    """anvil の余韻が済み、pulse の lane で心拍を再開してよい小節内の step（拍頭に揃える）。
    slow（BPM 64〜72）は 4、chase（138〜148）は 8。"""
    return math.ceil(math.ceil(ANVIL_RING_SEC / m.step_seconds()) / 4) * 4


def heartbeat(m: MeasureCtx, beat_rows, lub: int, dub: int) -> None:
    """心拍語彙: 拍頭に lub、拍頭+2 step に dub（1 拍 = 4 step）。"""
    for r in beat_rows:
        m.note(r, "heart", vel=lub)
        if r + 2 < m.m.steps:
            m.note(r + 2, "heart", vel=dub)


def strings_chord(m: MeasureCtx, step: int = 0) -> None:
    """持続和音: ``harmony`` 音に ``arp``（サンプル既定音量で鳴る）。"""
    chord = m.m.chord
    arts = (Arpeggio(chord.arp >> 4, chord.arp & 0xF),) if chord.arp else ()
    m.note(step, "strings", chord.harmony, arts=arts)


def pizz_root_note(chord: ChordDef, root_pc: Optional[int] = None) -> int:
    """PIZZ_REG 内の根音（pitch class は harmony 音の pc）。"""
    pc = chord.harmony % 12 if root_pc is None else root_pc
    return lowest_note_with_pc(pc, *PIZZ_REG)


def lead_generator(rng, rules: ScaleRules, plan: SectionPlan, register=LEAD_REG, base_vol: int = 46) -> MelodyGenerator:
    return MelodyGenerator(rules, register, PHRYGIAN, rng, base_vol=base_vol)
