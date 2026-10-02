"""ジェネレータが使う文脈 ``SectionCtx``・``MeasureCtx`` と ``Generator`` 基底（FRAMEWORK_REDESIGN.md §6.5・§6.6）。"""
from __future__ import annotations

import random
from typing import TYPE_CHECKING, Iterator, Optional

from ..errors import PlanError
from .plan import MeasurePlan, SectionPlan, SongPlan
from .score import Articulation, Automation, Cut, Delay, Event, NoteEvent, NoteOff, Retrig, TempoEvent

if TYPE_CHECKING:
    from .genre import Genre, Part


class SectionCtx:
    """1区間・1パートぶんの文脈。``note()``/``off()``/``automate()`` の ``step`` は区間の先頭から。"""

    def __init__(self, genre: "Genre", plan: SectionPlan, song: SongPlan, part: "Part",
                 rng: random.Random, song_state: dict, events: list[Event], tempo: list[TempoEvent],
                 bpm: int) -> None:
        self.genre = genre
        self.plan = plan
        self.song = song
        self.part = part
        self.rng = rng
        self.state: dict = {}
        self.song_state = song_state
        self._events = events          # SectionScore.parts[part.name] への参照（直接追記する）
        self._tempo = tempo             # SectionScore.tempo への参照
        self.bpm = bpm
        self._depends_events: dict[str, list[Event]] = {}

    @property
    def features(self) -> frozenset[str]:
        return self.song.extra.get("features", frozenset())

    # --- 小節への分割 ---
    def measures(self) -> Iterator["MeasureCtx"]:
        n = len(self.plan.measures)
        for m in self.plan.measures:
            yield MeasureCtx(self, m, is_first=m.index == 0, is_last=m.index == n - 1)

    # --- 他パートの既出イベント（depends） ---
    def events_of(self, part: str) -> list[Event]:
        if part not in self.part.depends and part != self.part.follow:
            raise PlanError(f"{self.part.name}: events_of({part!r}) requires it in Part.depends")
        return list(self._depends_events.get(part, ()))

    def _set_depends_events(self, part: str, events: list[Event]) -> None:
        self._depends_events[part] = events

    # --- 時間 ---
    def step_seconds(self, step: int = 1) -> float:
        """スウィングを除いた step の長さ（秒）。1拍=24 tick なので 1 tick = 2.5/bpm 秒。"""
        ticks = step * self.plan.meter.ticks_per_step
        return ticks * 2.5 / self.bpm

    def inst_seconds(self, inst: str) -> Optional[float]:
        """ワンショットが鳴り終わるまでの秒数（Patch.finish.duration。まだ描画していないので正確な
        再生時間ではなく設計上の長さ）。ループ音色は None。"""
        from ..core.synth import OneShot as _OneShot

        finish = self.genre.instruments[inst].patch.finish
        return finish.duration if isinstance(finish, _OneShot) else None

    # --- 音量の換算（§6.6） ---
    def scale_vol(self, vol: int) -> int:
        return max(1, min(64, round(vol * (0.55 + 0.45 * self.plan.intensity))))

    def scale_drum(self, vol: int) -> int:
        return max(1, min(64, round(vol * (0.6 + 0.4 * self.plan.intensity))))

    # --- 検査 ---
    def _local_limit(self) -> int:
        return self.plan.steps

    def _max_ticks(self) -> int:
        swing = self.plan.swing
        if swing is not None:
            return min(swing.long, swing.short)
        return self.plan.meter.ticks_per_step

    def _check_inst(self, inst: str, pitch: Optional[float]) -> None:
        if inst not in self.genre.instruments:
            raise PlanError(f"{self.part.name}: unknown instrument {inst!r}")
        pitched = self.genre.instruments[inst].is_pitched
        if pitched and pitch is None:
            raise PlanError(f"{self.part.name}: {inst!r} is pitched but pitch=None")
        if not pitched and pitch is not None:
            raise PlanError(f"{self.part.name}: {inst!r} is not pitched but pitch={pitch!r}")

    def pitch_for(self, inst: str, pitch: Optional[float]) -> Optional[float]:
        """音程の無い楽器（vocal chop・効果音など）には音高を渡せない（``note()`` は厳格に検査する）ので、部品集が
        「旋律・和音の音高を鳴らすつもりで音程の無い楽器を指定されたとき」に音高を落とすための補助。旧版は黙って
        無視していた（``Instrument.cell`` が ``pitched=False`` で ``n`` を捨てる）。"""
        return pitch if self.genre.instruments[inst].is_pitched else None

    def _check_arts(self, arts: tuple[Articulation, ...]) -> None:
        limit = self._max_ticks()
        for a in arts:
            if isinstance(a, (Delay, Retrig, Cut)) and not 0 <= a.ticks < limit:
                raise PlanError(f"{self.part.name}: {type(a).__name__}.ticks={a.ticks} must be 0..{limit - 1}")

    def _check_step(self, step: int) -> None:
        if not 0 <= step < self._local_limit():
            raise PlanError(f"{self.part.name}: step {step} is outside 0..{self._local_limit() - 1}")

    # --- 音符を書く ---
    def note(self, step: int, inst: str, pitch: Optional[float] = None, vel: Optional[int] = None, *,
              dur: Optional[int] = None, chord: tuple[int, ...] = (), strum_ms: float = 0.0,
              prio: int = 1, arts: tuple[Articulation, ...] = ()) -> None:
        self._check_step(step)
        self._check_inst(inst, pitch)
        if vel is not None and not 0 <= vel <= 64:
            raise PlanError(f"{self.part.name}: vel={vel} must be 0..64")
        if chord and self.part.poly != 1:
            raise PlanError(f"{self.part.name}: a part with poly != 1 cannot also write chords")
        self._check_arts(arts)
        self._events.append(NoteEvent(step=step, inst=inst, pitch=pitch, vel=vel, dur=dur, chord=chord,
                                       strum_ms=strum_ms, prio=prio, arts=arts))

    def off(self, step: int, inst: str) -> None:
        self._check_step(step)
        if inst not in self.genre.instruments:
            raise PlanError(f"{self.part.name}: unknown instrument {inst!r}")
        self._events.append(NoteOff(step=step, inst=inst))

    def automate(self, step: int, kind: str, value: int, inst: Optional[str] = None) -> None:
        self._check_step(step)
        if kind not in ("volume", "pan", "cutoff"):
            raise PlanError(f"{self.part.name}: unknown automation kind {kind!r}")
        if inst is not None and inst not in self.genre.instruments:
            raise PlanError(f"{self.part.name}: unknown instrument {inst!r}")
        self._events.append(Automation(step=step, kind=kind, value=value, inst=inst))

    def tempo(self, step: int, bpm: int) -> None:
        self._check_step(step)
        if not 32 <= bpm <= 255:
            raise PlanError(f"tempo bpm={bpm} must be 32..255")
        self._tempo.append(TempoEvent(step=step, bpm=bpm))


class MeasureCtx(SectionCtx):
    """``SectionCtx`` の1小節ぶんの視点。``note()``/``off()``/``automate()`` の ``step`` は小節の先頭から
    （内部で ``m.start`` を足す）。属性は親の ``SectionCtx`` をそのまま使う（委譲）。"""

    def __init__(self, parent: SectionCtx, m: MeasurePlan, *, is_first: bool, is_last: bool) -> None:
        self._parent = parent
        self.m = m
        self.is_first = is_first
        self.is_last = is_last
        self.is_chord_change = m.chord_offset == 0

    def __getattr__(self, name: str):
        return getattr(self._parent, name)

    def _local_limit(self) -> int:
        return self.m.steps

    def note(self, step: int, inst: str, pitch: Optional[float] = None, vel: Optional[int] = None, *,
              dur: Optional[int] = None, chord: tuple[int, ...] = (), strum_ms: float = 0.0,
              prio: int = 1, arts: tuple[Articulation, ...] = ()) -> None:
        self._check_step(step)
        self._parent.note(self.m.start + step, inst, pitch, vel, dur=dur, chord=chord, strum_ms=strum_ms,
                           prio=prio, arts=arts)

    def off(self, step: int, inst: str) -> None:
        self._check_step(step)
        self._parent.off(self.m.start + step, inst)

    def automate(self, step: int, kind: str, value: int, inst: Optional[str] = None) -> None:
        self._check_step(step)
        self._parent.automate(self.m.start + step, kind, value, inst)

    def tempo(self, step: int, bpm: int) -> None:
        self._check_step(step)
        self._parent.tempo(self.m.start + step, bpm)

    def _check_step(self, step: int) -> None:
        if not 0 <= step < self._local_limit():
            raise PlanError(f"{self._parent.part.name}: step {step} is outside 0..{self._local_limit() - 1} "
                             f"of measure {self.m.index}")

    def _max_ticks(self) -> int:
        return self._parent._max_ticks()


class Generator:
    """1パートの音符を作る。インスタンスはジャンルのクラス属性として共有されるので、状態を ``self`` に
    持たない。状態は ``ctx.state``（区間ごと）・``ctx.song_state``（曲全体）に置く。"""

    def section(self, ctx: SectionCtx) -> None:
        """区間全体を作る。既定は小節ごとに ``measure()`` を呼ぶ。区間をまたぐ型は上書きしてよい。"""
        for m in ctx.measures():
            self.measure(m)

    def measure(self, m: MeasureCtx) -> None:
        raise NotImplementedError
