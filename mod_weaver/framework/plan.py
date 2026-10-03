"""区間の計画（FRAMEWORK_REDESIGN.md §5.4）。``default_plan()`` は既定の ``Genre.plan()``（§6.7）。"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

from ..core.harmony import PC_NAMES, voice
from ..core.model import ChordDef
from ..core.pitch import MODES, Scale
from ..errors import PlanError

if TYPE_CHECKING:
    from .genre import Genre, Section


@dataclass(frozen=True)
class Meter:
    steps: int = 16                  # 1小節の step 数（4/4 の16分＝16、3/4＝12、2/4＝8、7/8＝14）
    steps_per_beat: int = 4          # 表示 BPM の1拍の step 数（1, 2, 3, 4, 6, 8, 12, 24 のどれか）
    signature: tuple[int, int] = (4, 4)   # MIDI の拍子の表示

    def __post_init__(self) -> None:
        if self.steps <= 0:
            raise PlanError(f"Meter.steps must be positive: {self.steps}")
        if 24 % self.steps_per_beat != 0:
            raise PlanError(f"Meter.steps_per_beat must divide 24 (ticks/beat): {self.steps_per_beat}")

    @property
    def ticks_per_step(self) -> int:
        return 24 // self.steps_per_beat


@dataclass(frozen=True)
class Swing:
    long: int                        # 2 step の組の前半の tick 数
    short: int                       # 後半の tick 数

    def __post_init__(self) -> None:
        if self.long <= 0 or self.short <= 0:
            raise PlanError(f"Swing.long/short must be positive: {self.long}/{self.short}")


def validate_swing(swing: Optional[Swing], meter: Meter) -> None:
    """``long + short == 2 * ticks_per_step`` を検査する（DESIGN.md §4.6 の規則）。"""
    if swing is None:
        return
    expected = 2 * meter.ticks_per_step
    if swing.long + swing.short != expected:
        raise PlanError(
            f"Swing({swing.long}, {swing.short}) must sum to {expected} for steps_per_beat={meter.steps_per_beat}")


@dataclass(frozen=True)
class MeasurePlan:
    index: int                       # 区間の中の小節番号（0..）
    start: int                       # 区間の先頭からの step
    steps: int                       # この小節の step 数（可変拍子なら小節ごとに違う）
    chord: ChordDef
    quality: str                     # 和音の種類（CHORD_QUALITIES のキー）
    chord_offset: int                # 同じ和音の何小節目か（0 なら和音の変わり目）
    next_chord: ChordDef             # 次の小節の和音（区間の最後は区間の先頭へ戻る）


@dataclass
class SectionPlan:
    name: str
    kind: str
    meter: Meter
    measures: tuple[MeasurePlan, ...]
    intensity: float                 # 0..1
    key_offset: int
    tonic: int                       # (key_pc + key_offset) % 12
    scale: Scale
    parts: frozenset[str]            # この区間で鳴らすパート名
    swing: Optional[Swing]
    section: "Section"                # 宣言（groove・fill・crash・motifs・tags を読む）
    extra: dict = field(default_factory=dict)   # plan() の上書きでジャンルが足す値

    @property
    def steps(self) -> int:
        return sum(m.steps for m in self.measures)


@dataclass
class SongPlan:
    bpm: int
    key_pc: int
    sections: dict[str, SectionPlan] = field(default_factory=dict)   # 作成順
    order: list[str] = field(default_factory=list)
    summary: list[str] = field(default_factory=list)
    extra: dict = field(default_factory=dict)


# ============================================================
# 既定の plan()（FRAMEWORK_REDESIGN.md §6.7）
# ============================================================

def default_plan(genre: "Genre", rng: random.Random) -> SongPlan:
    """既定の ``Genre.plan()``。現行 ``BandProfile.plan`` と同じ規則（§6.7）。

    1. ``bpm = rng.choice(tempo_choices)``（``--tempo`` があっても引いてから捨てる。DESIGN.md §5.5）。
    2. ``key_pc = rng.choice(harmony.keys)``。
    3. 進行: ``fixed`` なら宣言順に全部、そうでなければ ``rng.sample(range(len), k=min(n, len))``。
    4. 区間名の初出順に ``SectionPlan`` を作る。小節への和音の割当は「1和音 ``max(1, 小節数 // 和音数)``
       小節で、進行を繰り返して小節数を埋める」。和音は ``voice()``。
    5. ``summary`` に調と進行。
    """
    harmony = genre.harmony
    if harmony is None:
        raise PlanError(f"{genre.id}: default plan() needs Genre.harmony (or override plan())")
    bpm = rng.choice(list(genre.tempo_choices))
    key_pc = rng.choice(list(harmony.keys))
    if harmony.fixed:
        progs = list(harmony.progressions)
    else:
        n = min(harmony.n_progressions, len(harmony.progressions))
        chosen = rng.sample(range(len(harmony.progressions)), k=n)
        progs = [harmony.progressions[i] for i in chosen]

    default_parts = frozenset(p.name for p in genre.parts if p.follow is None)
    sections: dict[str, SectionPlan] = {}
    for name in dict.fromkeys(genre.form):          # 初出順、重複を除く
        sec = genre.sections[name]
        sections[name] = _plan_section(name, sec, progs, key_pc, harmony, default_parts, genre.swing)
    order = list(genre.form)

    summary = [f"Key         : {PC_NAMES[key_pc]} {harmony.mode}"]
    for i, (pname, specs) in enumerate(progs):
        chords = " - ".join(s.label or "?" for s in specs)
        summary.append(f"Progression {chr(ord('A') + i)}: {pname} ({chords})")
    return SongPlan(bpm=bpm, key_pc=key_pc, sections=sections, order=order, summary=summary)


def _plan_section(name: str, sec: "Section", progs, key_pc: int, harmony,
                   default_parts: frozenset[str], genre_swing: Optional[Swing] = None) -> SectionPlan:
    _pname, specs = progs[sec.prog % len(progs)]
    tonic = (key_pc + sec.key_offset) % 12
    scale = Scale(tonic, MODES[harmony.mode])

    if sec.measure_steps is not None:
        measure_steps = list(sec.measure_steps)
    else:
        measure_steps = [sec.meter.steps] * sec.measures
    n_measures = len(measure_steps)
    per = max(1, n_measures // len(specs))

    chords: list[ChordDef] = []
    qualities: list[str] = []
    offsets: list[int] = []
    m = 0
    while m < n_measures:
        for spec in specs:
            if m >= n_measures:
                break
            k = min(per, n_measures - m)
            chord = voice(spec, tonic, scale, harmony.registers, arp=harmony.arp,
                          mode_by_quality=harmony.mode_by_quality or None)
            chords.extend([chord] * k)
            qualities.extend([spec.quality] * k)
            offsets.extend(range(k))
            m += k

    measures = []
    start = 0
    for i in range(n_measures):
        nxt = chords[(i + 1) % n_measures]
        measures.append(MeasurePlan(index=i, start=start, steps=measure_steps[i], chord=chords[i],
                                     quality=qualities[i], chord_offset=offsets[i], next_chord=nxt))
        start += measure_steps[i]

    parts = sec.parts if sec.parts else default_parts
    return SectionPlan(name=name, kind=sec.kind or name, meter=sec.meter, measures=tuple(measures),
                        intensity=sec.intensity, key_offset=sec.key_offset, tonic=tonic, scale=scale,
                        parts=parts, swing=sec.swing if sec.swing is not None else genre_swing, section=sec,
                        extra={})
