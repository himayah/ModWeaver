"""歌声のパート（VOCAL_DESIGN.md §4.3）。``Lead`` と同じ旋律に、音節（P3 は母音だけのヴォカリーズ）を流し込む。

声の源（``--voice``）には問い合わせない。音節は決定的に割り当てる（旋律の乱数は ``Lead`` と同じく動機・旋律にだけ使う）ので、
声の源や母音を変えても音符の時刻・高さは変わらない（V-4）。このパートは ``Part.requires=frozenset({"voice"})`` で宣言する。
"""
from __future__ import annotations

from typing import Mapping, Sequence

from ...core.composer import RhythmMotif, ScaleRules
from ...voice.phoneme import vowel_syllable
from ..context import Generator, MeasureCtx, SectionCtx
from ..score import Glide, NoteEvent, Vibrato
from .lead import Lead


class Vocalise(Lead):
    """母音だけで歌う旋律。``vowels`` を音符ごとに循環する（既定は「あ」）。"""

    def __init__(self, inst: str, rules: ScaleRules, motifs: Mapping[str, tuple[RhythmMotif, ...]],
                 vol: int = 40, gate: float = 0.9, *, vibrato: int = 0x35, vowels: Sequence[str] = ("あ",)) -> None:
        super().__init__(inst, rules, motifs, vol, gate, vibrato=vibrato)
        self.syls = tuple(vowel_syllable(v) for v in vowels)

    def section(self, ctx: SectionCtx) -> None:
        ctx.state["syl_i"] = 0           # 区間ごとに先頭の母音から（区間を繰り返しても同じ歌になる）
        super().section(ctx)

    def measure(self, m: MeasureCtx) -> None:
        for e in self._bar_events(m):
            dur = max(1, round(e.dur * self.gate))
            arts = (Vibrato(self.vibrato, at=2),) if (self.vibrato and e.dur >= 6) else ()
            syl = self.syls[m.state["syl_i"] % len(self.syls)]
            m.state["syl_i"] += 1
            m.note(e.row, self.inst, e.note, vel=e.vol, dur=dur, arts=arts, syl=syl)


class Sing(Generator):
    """別パート（既定は ``lead``）の旋律を歌う（島唄・演歌のように、歌と楽器が同じ旋律をなぞる型）。装飾の短い音（``min_dur`` 未満）は
    歌わない。しゃくり（``Glide``）は引き継ぐ（ビブラートは声のサンプルに焼き込んであるので引き継がない）。母音は ``vowels`` を音符ごとに循環し、**区間の先頭から数え直す**。
    ``Part(..., depends=(source,), requires=frozenset({"voice"}))`` で宣言する。"""

    def __init__(self, inst: str, *, source: str = "lead", vowels: Sequence[str] = ("あ",), min_dur: int = 2,
                 vel_ratio: float = 1.0) -> None:
        self.inst = inst
        self.source = source
        self.syls = tuple(vowel_syllable(v) for v in vowels)
        self.min_dur = min_dur
        self.vel_ratio = vel_ratio

    def section(self, ctx: SectionCtx) -> None:
        notes = sorted((e for e in ctx.events_of(self.source) if isinstance(e, NoteEvent) and e.pitch is not None
                        and not e.chord and (e.dur is None or e.dur >= self.min_dur)), key=lambda e: e.step)
        for i, e in enumerate(notes):
            arts = tuple(a for a in e.arts if isinstance(a, Glide))    # ビブラートはサンプルに焼き込み済み
            vel = None if e.vel is None else max(1, min(64, round(e.vel * self.vel_ratio)))
            ctx.note(e.step, self.inst, e.pitch, vel, dur=e.dur, arts=arts, syl=self.syls[i % len(self.syls)])
