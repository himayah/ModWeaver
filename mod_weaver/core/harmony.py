"""和音の具体化 ``ChordSpec`` → ``ChordDef``（DESIGN.md §4.2）。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional

from ..errors import PitchRangeError
from .model import ChordDef, ChordSpec
from .pitch import (
    CHORD_QUALITIES,
    MODES,
    Scale,
    lowest_note_with_pc,
    notes_with_pcs,
)

PC_NAMES = ("C", "Db", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B")
_QUALITY_SUFFIX = {"maj": "", "min": "m", "dim": "dim", "maj7": "maj7", "m7": "m7", "dom7": "7"}


@dataclass(frozen=True)
class Registers:
    """logical note の音域。各 ``hi−lo ≥ 11``（1 オクターブ以上）。"""

    bass: tuple[int, int]
    harmony: tuple[int, int]
    melody: tuple[int, int]

    def __post_init__(self) -> None:
        for name in ("bass", "harmony", "melody"):
            lo, hi = getattr(self, name)
            if hi - lo < 11:
                raise PitchRangeError(f"register {name}=({lo},{hi}) must span at least an octave")


def chord_label(spec: ChordSpec, tonic_pc: int) -> str:
    root_pc = (tonic_pc + spec.root) % 12
    label = PC_NAMES[root_pc] + _QUALITY_SUFFIX.get(spec.quality, spec.quality)
    if spec.bass is not None:
        bass_pc = (tonic_pc + spec.bass) % 12
        if bass_pc != root_pc:
            label += "/" + PC_NAMES[bass_pc]
    return label


def voice(
    spec: ChordSpec,
    tonic_pc: int,
    scale: Scale,
    regs: Registers,
    *,
    arp: bool = False,
    mode_by_quality: Optional[Mapping[str, str]] = None,
) -> ChordDef:
    """調・音域を適用して和音を具体化する。

    ``tonic_pc`` は ``(key_pc + PatternPlan.key_offset) % 12``。規則:

    1. ``root_pc``、``bass_pc``（``spec.bass`` なら根音と別）、構成音の pc 集合を求める
    2. ``bass`` = ``regs.bass`` 内で ``bass_pc`` の最低音
    3. ``harmony`` = ``regs.harmony`` 内で ``root_pc`` の最低音（上声の根音）
    4. ``chord_tones`` = ``regs.melody`` 内の構成音（昇順）
    5. ``scale_tones`` = （``mode_by_quality`` があれば根音基準のそのモード、なければ ``scale``）の音域内の音 ∪ chord_tones
    6. ``arp=True``: ``(第3音オフセット << 4) | 第5音オフセット``（7th 和音も三和音分のみ）
    7. ``label``: ``spec.label`` があればそれ、なければ pc 名＋quality（＋スラッシュ）
    """
    if spec.quality not in CHORD_QUALITIES:
        raise PitchRangeError(f"unknown chord quality: {spec.quality!r}")
    q = CHORD_QUALITIES[spec.quality]
    root_pc = (tonic_pc + spec.root) % 12
    bass_pc = (tonic_pc + (spec.root if spec.bass is None else spec.bass)) % 12
    tone_pcs = {(root_pc + i) % 12 for i in q}

    bass = lowest_note_with_pc(bass_pc, *regs.bass)
    harmony = lowest_note_with_pc(root_pc, *regs.harmony)
    chord_tones = notes_with_pcs(tone_pcs, *regs.melody)

    active = scale
    if mode_by_quality and spec.quality in mode_by_quality:
        active = Scale(root_pc, MODES[mode_by_quality[spec.quality]])
    scale_tones = sorted(set(active.notes_in(*regs.melody)) | set(chord_tones))

    arp_param = ((q[1] << 4) | q[2]) if arp else None
    return ChordDef(
        label=spec.label or chord_label(spec, tonic_pc),
        bass=bass,
        harmony=harmony,
        chord_tones=tuple(chord_tones),
        scale_tones=tuple(scale_tones),
        arp=arp_param,
        explicit=False,
    )
