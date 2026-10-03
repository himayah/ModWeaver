"""新ジャンルの共有部品（先頭 ``_`` なので registry に拾われない。NEW_GENRES_DESIGN.md §3.2）。

- ``OrnamentedLead``: ``Lead`` の出力に装飾（しゃくり・前打音・ロール・こぶし・トレモロ）を後付けする。
- ``Heterophony``: ``follow`` した旋律を、少しずらして簡略化して別楽器で重ねる（異種同音）。
- ``WithTempo``: 任意のジェネレータにテンポの倍率（開始 BPM に対する）を書き足す。
装飾は本命の音の時刻・高さを動かさない（空いている step への前打音、同じ音価の内側での分割だけ）。
"""
from __future__ import annotations

import dataclasses
from typing import Callable, Optional

from ..core.composer import ScaleRules
from ..core.model import GmVoice
from ..core.pitch import fold_into_range
from ..core.synth_presets import PRESETS
from ..framework.context import Generator, MeasureCtx, SectionCtx
from ..framework.genre import Instrument
from ..framework.gens import Lead
from ..framework.gens.tempo import tempo_curve
from ..framework.plan import SectionPlan
from ..framework.score import Glide, NoteEvent, Retrig


def inst(key: str, gm: GmVoice, *, volume: Optional[int] = None, **patch_changes) -> Instrument:
    """プリセット ``key`` の ``Instrument``。``patch_changes`` は ``Patch`` のフィールド（name など）の差し替え。"""
    patch = PRESETS[key]
    if patch_changes:
        patch = dataclasses.replace(patch, **patch_changes)
    return Instrument(patch=patch, gm=gm, volume=volume)


def _tones(ctx: SectionCtx, step: int):
    for m in ctx.plan.measures:
        if m.start <= step < m.start + m.steps:
            return sorted(m.chord.scale_tones)
    return []


class OrnamentedLead(Lead):
    """``scoop``: 低い半音から本命へ ``Glide``（しゃくり・塩梅）。``grace``: 1つ上の音階音を16分で先行。
    ``roll``: 長い音の頭を「本命・上・本命」に割る。``kobushi``: 長い音の末尾に下の音階音を添える。
    ``tremolo``: 音価の間を毎 step の ``Retrig``（tick 数）で埋める（バラライカ等の撥弦トレモロ）。
    各確率は音ごとに独立（乱数はパート固有）。"""

    def __init__(self, inst: str, rules: ScaleRules, motifs, vol: int = 48, gate: float = 0.9, *,
                 vibrato: int = 0, inst_for: Optional[Callable[[SectionPlan], str]] = None,
                 scoop: float = 0.0, grace: float = 0.0, roll: float = 0.0, kobushi: float = 0.0,
                 tremolo: int = 0, scoop_semitones: float = 1.0) -> None:
        super().__init__(inst, rules, motifs, vol, gate, vibrato=vibrato, inst_for=inst_for)
        self.scoop, self.grace, self.roll, self.kobushi = scoop, grace, roll, kobushi
        self.tremolo = tremolo
        self.scoop_semitones = scoop_semitones

    def section(self, ctx: SectionCtx) -> None:
        super().section(ctx)
        events = ctx.own_events()
        notes = sorted((e for e in events if isinstance(e, NoteEvent)), key=lambda e: e.step)
        busy = set()
        for e in notes:
            busy.update(range(e.step, e.step + (e.dur or 1)))
        out: list[NoteEvent] = []
        for e in notes:
            r = ctx.rng.random()      # 音ごとに1回だけ引く（確率の和で排他的に選ぶ）
            r2 = ctx.rng.random()
            tones = _tones(ctx, e.step)
            above = next((t for t in tones if t > e.pitch), None)
            below = next((t for t in reversed(tones) if t < e.pitch), None)
            dur = e.dur or 1
            free_before = e.step - 1 >= 0 and (e.step - 1) not in busy
            if self.scoop and r < self.scoop and dur >= 3 and free_before:
                out.append(NoteEvent(e.step - 1, e.inst, e.pitch - self.scoop_semitones,
                                     max(1, (e.vel or 40) - 12), None, prio=0))
                busy.add(e.step - 1)
                e = dataclasses.replace(e, arts=e.arts + (Glide(1),))
            elif self.grace and r < self.grace and free_before and above is not None:
                out.append(NoteEvent(e.step - 1, e.inst, above, max(1, (e.vel or 40) - 10), 1))
                busy.add(e.step - 1)
            elif self.roll and r < self.roll and dur >= 6 and above is not None:
                out.append(NoteEvent(e.step, e.inst, e.pitch, e.vel, 1, arts=e.arts))
                out.append(NoteEvent(e.step + 1, e.inst, above, max(1, (e.vel or 40) - 10), 1))
                e = dataclasses.replace(e, step=e.step + 2, dur=dur - 2, arts=())
                dur -= 2
            if self.kobushi and r2 < self.kobushi and dur >= 5 and below is not None:
                out.append(NoteEvent(e.step + dur - 1, e.inst, below, max(1, (e.vel or 40) - 8), 1))
                e = dataclasses.replace(e, dur=dur - 1)
                dur -= 1
            if self.tremolo and dur >= 2:
                # 頭の音は元の音価のまま（Heterophony が旋律の骨格として読む）。続きの step の連打は prio=0（骨格ではない印）
                for k in range(1, dur):
                    out.append(NoteEvent(e.step + k, e.inst, e.pitch, max(1, (e.vel or 40) - 8), 1, prio=0,
                                         arts=(Retrig(self.tremolo),)))
                e = dataclasses.replace(e, arts=e.arts + (Retrig(self.tremolo),))
            out.append(e)
        events[:] = [e for e in events if not isinstance(e, NoteEvent)] + out
        events.sort(key=lambda e: e.step)


class Heterophony(Generator):
    """``follow`` した旋律を ``delay``（step 数、または ``SectionCtx`` を取る関数）だけ遅らせ、短い音（dur が ``min_dur`` 未満。装飾音）を落とし、確率 ``drop`` で音を省き、
    ``shift`` 半音ずらして重ねる。``Part.follow`` に旋律のパートを指定して使う。"""

    def __init__(self, inst: str, *, delay=1, drop: float = 0.15, shift: int = 0, vol_ratio: float = 0.8,
                 lo: int = 0, hi: int = 35, min_dur: int = 2) -> None:
        self.inst, self.delay, self.drop, self.shift = inst, delay, drop, shift
        self.vol_ratio, self.lo, self.hi, self.min_dur = vol_ratio, lo, hi, min_dur

    def section(self, ctx: SectionCtx) -> None:
        src = [e for e in ctx.events_of(ctx.part.follow) if isinstance(e, NoteEvent) and e.pitch is not None and e.prio != 0]
        limit = ctx.plan.steps
        delay = self.delay(ctx) if callable(self.delay) else self.delay
        for e in sorted(src, key=lambda e: e.step):
            keep = ctx.rng.random() >= self.drop
            step = e.step + delay
            if not keep or (e.dur is not None and e.dur < self.min_dur) or step >= limit:
                continue
            pitch = e.pitch + self.shift
            while pitch > self.hi:
                pitch -= 12
            while pitch < self.lo:
                pitch += 12
            dur = None if e.dur is None else max(1, min(e.dur, limit - step))
            arts = tuple(a for a in e.arts if not isinstance(a, (Glide, Retrig)))
            ctx.note(step, self.inst, ctx.pitch_for(self.inst, pitch), vel=max(1, round((e.vel or 40) * self.vol_ratio)),
                     dur=dur, arts=arts)


class WithTempo(Generator):
    """``inner`` の前に、区間のテンポを書く。``schedule(plan)`` が ``(開始倍率, 終了倍率)`` を返す（``None`` なら書かない）。
    倍率は ``ctx.bpm``（曲の開始 BPM。``--tempo`` で上書きされた後の値）に対する。1つの曲でテンポを書くパートは1つだけにする
    （同じ step に複数のパートが書くと重複する）。"""

    def __init__(self, inner: Generator, schedule: Callable[[SectionPlan], Optional[tuple[float, float]]],
                 kind: str = "linear") -> None:
        self.inner, self.schedule, self.kind = inner, schedule, kind

    @property
    def inst(self):
        """和音を焼けるかの検査（Realizer の ladder）が ``gen.inst`` を読むので、包んだ側の楽器名を見せる。"""
        return getattr(self.inner, "inst", None)

    def section(self, ctx: SectionCtx) -> None:
        mult = self.schedule(ctx.plan)
        if mult is not None:
            a, b = mult
            if a == b or ctx.plan.steps < 2:
                ctx.tempo(0, max(32, min(255, round(ctx.bpm * a))))
            else:
                tempo_curve(ctx, round(ctx.bpm * a), round(ctx.bpm * b), 0, ctx.plan.steps - 1, self.kind)
        self.inner.section(ctx)

    def measure(self, m: MeasureCtx) -> None:       # section() を上書きしているので通常は呼ばれない
        self.inner.measure(m)


def retime(sp: SectionPlan, meter, swing=None, measure_steps: Optional[tuple[int, ...]] = None) -> None:
    """``plan()`` の上書きで、系統（family）に応じて区間の拍子・スウィング・小節の長さを差し替える。
    和音の割当（``default_plan`` が作った）はそのまま、各小節の ``start``・``steps`` と区間の ``meter``・``swing`` だけ換える。"""
    from ..framework.plan import validate_swing

    validate_swing(swing, meter)
    start = 0
    ms = []
    for i, m in enumerate(sp.measures):
        steps = measure_steps[i % len(measure_steps)] if measure_steps else meter.steps
        ms.append(dataclasses.replace(m, start=start, steps=steps))
        start += steps
    sp.measures = tuple(ms)
    sp.meter = meter
    sp.swing = swing


class Drone(Generator):
    """区間の頭で主音の持続音を鳴らし直す（区間は音を持ち越さないので毎区間）。``register`` 省略時は低音域。
    """

    def __init__(self, inst: str, vol: int = 30, *, register: Optional[tuple[int, int]] = None) -> None:
        self.inst, self.vol, self.register = inst, vol, register

    def measure(self, m: MeasureCtx) -> None:
        if m.is_first:
            reg = self.register or m.genre.harmony.registers.bass
            m.note(0, self.inst, fold_into_range(m.plan.tonic, *reg), vel=m.scale_vol(self.vol), dur=None)
