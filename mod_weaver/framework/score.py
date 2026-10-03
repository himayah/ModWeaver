"""形式に依存しない楽譜（DESIGN.md §3.3）。

ジャンルのジェネレータが作るのはここまで。``NoteEvent``・``NoteOff``・``Automation``・``TempoEvent`` の
時刻は区間の先頭からの **step**（既定 16分音符）。奏法（``Articulation``）は意味だけを書き、
形式ごとの表現（MOD の `4xy` にするか CC1 にするか等）は Realizer（DESIGN.md §7.6・§7.7）が決める。

単位は DESIGN.md §3.3 のとおり: 音量は 0..64（``None``＝楽器の既定音量）、音高は書かれた音高（整数部＝logical note、
小数部＝セント/100）、パンは 0..255。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional, Union

if TYPE_CHECKING:
    from .plan import SectionPlan

TICKS_PER_BEAT = 24


# ============================================================
# 奏法（Articulation。DESIGN.md §3.3）
# ============================================================

@dataclass(frozen=True)
class Vibrato:
    """MOD `4xy` の param。発音から ``at`` step 後に ``steps`` 個の step で掛ける。"""
    param: int
    at: int = 0
    steps: int = 1


@dataclass(frozen=True)
class Tremolo:
    """MOD `7xy` の param（新しく全形式で使えるようになる）。"""
    param: int
    at: int = 0
    steps: int = 1


@dataclass(frozen=True)
class Arpeggio:
    """`0xy`。発音の step から ``steps`` 個。"""
    x: int
    y: int
    steps: int = 1


@dataclass(frozen=True)
class Glide:
    """同じ lane の直前の音からこの音へ滑らせる。``steps`` で到達時間を指定するか、``param``
    （MOD `3xx` の速さ）を直接指定する。直前の音が鳴り終わっていれば Realizer が普通の発音に変える
    （DESIGN.md §6.8 の trap の規則の一般化）。"""
    steps: Optional[int] = 1
    param: Optional[int] = None


@dataclass(frozen=True)
class Delay:
    """step 内で遅らせる（`EDx`）。``ticks`` はその row の tick 数未満（DESIGN.md §5.2）。"""
    ticks: int


@dataclass(frozen=True)
class Retrig:
    """`E9x`。step 内の連打。"""
    ticks: int


@dataclass(frozen=True)
class Cut:
    """`ECx`。"""
    ticks: int


@dataclass(frozen=True)
class Offset:
    """サンプルの途中から鳴らす（`9xx`）。サンプル長に対する割合（0..1）。"""
    fraction: float


Articulation = Union[Vibrato, Tremolo, Arpeggio, Glide, Delay, Retrig, Cut, Offset]


# ============================================================
# イベント
# ============================================================

@dataclass(frozen=True)
class NoteEvent:
    step: int                        # 区間の先頭からの step
    inst: str                        # Instrument 名（Genre.instruments のキー）
    pitch: Optional[float] = None    # 書かれた音高。音程の無い楽器（Instrument.pitched=False）は None
    vel: Optional[int] = None        # 0..64。None は楽器の既定音量
    dur: Optional[int] = None        # step 数。None は「同じ lane の次の発音まで。ワンショットは自然減衰、
    #                                   ループは区間の終わりまで」
    chord: tuple[int, ...] = ()      # 和音: pitch（根音）からの半音の列。空なら単音
    strum_ms: float = 0.0            # 和音の構成音ごとの鳴り始めの遅れ（ギターのストローク）
    prio: int = 1                    # 同じチャンネルに畳まれたときの優先度（大きいほど勝つ。DESIGN.md §7.6）
    arts: tuple[Articulation, ...] = ()


@dataclass(frozen=True)
class NoteOff:
    """明示的な消音（``dur`` で書けないとき）。この楽器の鳴っている lane を止める。"""
    step: int
    inst: str


@dataclass(frozen=True)
class Automation:
    step: int
    kind: str                        # "volume"（0..64）| "pan"（0..255）| "cutoff"（0..127）
    value: int
    inst: Optional[str] = None       # None はパートの全 lane


@dataclass(frozen=True)
class TempoEvent:
    step: int
    bpm: int                         # 32..255


Event = Union[NoteEvent, NoteOff, Automation]


# ============================================================
# Score
# ============================================================

@dataclass
class SectionScore:
    name: str
    plan: "SectionPlan"              # noqa: F821 (framework.plan.SectionPlan、循環 import を避けて文字列で)
    parts: dict[str, list[Event]] = field(default_factory=dict)   # パート名 → 時刻順のイベント
    tempo: list[TempoEvent] = field(default_factory=list)         # 区間内のテンポ変化

    def mute(self, parts: tuple[str, ...], start: int, end: int) -> None:
        """``finalize_section`` 用: 指定パートの ``[start, end)`` の区間にある NoteEvent/NoteOff を取り除く
        （「決め」で他のパートを一時的に黙らせる等。DESIGN.md §5.1）。Automation は対象外。"""
        for name in parts:
            events = self.parts.get(name)
            if not events:
                continue
            self.parts[name] = [e for e in events if not (isinstance(e, (NoteEvent, NoteOff)) and start <= e.step < end)]

    def add(self, part: str, event: Event) -> None:
        """``finalize_section`` 用: イベントを時刻順を保って挿入する。"""
        events = self.parts.setdefault(part, [])
        i = len(events)
        while i > 0 and events[i - 1].step > event.step:
            i -= 1
        events.insert(i, event)


@dataclass
class Score:
    bpm: int                         # 曲の先頭の BPM
    key_pc: int
    sections: dict[str, SectionScore] = field(default_factory=dict)   # 作成順（＝初出順）
    order: list[str] = field(default_factory=list)                    # 区間名の並び
    summary: list[str] = field(default_factory=list)                  # バナーに出す行
