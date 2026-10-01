"""Score を作る（FRAMEWORK_REDESIGN.md §6.8・§6.9）。

``resolve_plan(genre, seed)`` が ``genre.plan()`` を正しい乱数ストリームで呼び、``compose(genre, plan,
seed, features)`` が区間ごと・パートごとに ``Generator`` を呼んで ``Score`` を作る。
"""
from __future__ import annotations

import random
from typing import TYPE_CHECKING

from ..errors import PlanError
from .context import SectionCtx
from .plan import SongPlan
from .score import NoteEvent, Score, SectionScore

if TYPE_CHECKING:
    from .genre import Genre, Part


def resolve_plan(genre: "Genre", seed: int) -> SongPlan:
    """``genre.plan()`` を §6.8 の乱数ストリームで呼ぶ。"""
    rng = random.Random(f"{seed}:{genre.id}:plan")
    return genre.plan(rng)


def _topo_order(genre: "Genre") -> list["Part"]:
    """``depends``（``follow`` を暗黙に含む）で位相整列する。循環は ``Genre`` のクラス定義時に
    検査済みなのでここでは起きない想定だが、念のため検査する（§6.9 の1）。"""
    by_name = {p.name: p for p in genre.parts}

    def edges(p: "Part") -> list[str]:
        out = list(p.depends)
        if p.follow is not None and p.follow not in out:
            out.append(p.follow)
        return out

    order: list["Part"] = []
    seen: set[str] = set()
    visiting: set[str] = set()

    def visit(p: "Part") -> None:
        if p.name in seen:
            return
        if p.name in visiting:
            raise PlanError(f"{genre.id}: cyclic part dependency at {p.name!r}")
        visiting.add(p.name)
        for dep in edges(p):
            visit(by_name[dep])
        visiting.discard(p.name)
        seen.add(p.name)
        order.append(p)

    for p in genre.parts:   # 宣言順を基本の並びにする（依存が無いもの同士は宣言順のまま）
        visit(p)
    return order


def compose(genre: "Genre", plan: SongPlan, seed: int, features: frozenset[str]) -> Score:
    """区間ごと（作成順）・パートごとに ``Generator`` を呼んで ``Score`` を作る（§6.9）。"""
    plan.extra = dict(plan.extra)
    plan.extra["features"] = frozenset(features)

    order = _topo_order(genre)
    part_rngs = {p.name: random.Random(f"{seed}:{genre.id}:part:{p.name}") for p in genre.parts}
    part_song_state: dict[str, dict] = {p.name: {} for p in genre.parts}
    finalize_rng = random.Random(f"{seed}:{genre.id}:finalize")

    score = Score(bpm=plan.bpm, key_pc=plan.key_pc, order=list(plan.order), summary=list(plan.summary))

    for name, sec_plan in plan.sections.items():     # 作成順（SongPlan.sections の挿入順）
        sec_score = SectionScore(name=name, plan=sec_plan, parts={p.name: [] for p in genre.parts}, tempo=[])
        score.sections[name] = sec_score

        participates: dict[str, bool] = {}
        for part in order:
            if part.follow is None:
                participates[part.name] = part.name in sec_plan.parts
            else:
                participates[part.name] = participates.get(part.follow, part.follow in sec_plan.parts)

            if not participates[part.name]:
                continue
            ctx = SectionCtx(genre, sec_plan, plan, part, part_rngs[part.name], part_song_state[part.name],
                              events=sec_score.parts[part.name], tempo=sec_score.tempo, bpm=plan.bpm)
            for dep in set(part.depends) | ({part.follow} if part.follow else set()):
                ctx._set_depends_events(dep, sec_score.parts[dep])
            part.gen.section(ctx)

        genre.finalize_section(sec_plan, sec_score, finalize_rng)
        _validate_section_score(genre, sec_score)

    return score


# ============================================================
# Score の検査（§6.9 の4）
# ============================================================

def _validate_section_score(genre: "Genre", sec_score: SectionScore) -> None:
    by_part = {p.name: p for p in genre.parts}
    for part_name, events in sec_score.parts.items():
        notes = [e for e in events if isinstance(e, NoteEvent)]
        if not notes:
            continue
        part = by_part[part_name]
        by_inst_step: dict[tuple[str, int], list[NoteEvent]] = {}
        for e in notes:
            by_inst_step.setdefault((e.inst, e.step), []).append(e)
        dropped: set[int] = set()        # id(e) の集合（同じ値のイベントが別の場所にあっても誤って
        for (inst, step), group in by_inst_step.items():   # 消さないよう id で管理する）
            if len(group) < 2:
                continue
            best = max(e.prio for e in group)
            winners = [e for e in group if e.prio == best]
            if len(winners) > 1:
                raise PlanError(f"{genre.id}: part {part_name!r} inst {inst!r} step {step}: "
                                 f"{len(winners)} NoteEvents with the same priority {best}")
            dropped.update(id(e) for e in group if e is not winners[0])
        if dropped:
            sec_score.parts[part_name] = events = [e for e in events if id(e) not in dropped]
        if part.poly > 1:
            _check_poly(genre, part, events)


def _check_poly(genre: "Genre", part: "Part", events: list[NoteEvent]) -> None:
    """``poly`` を超える同時発音を検出する。``dur=None`` の発音は次の同じ楽器の発音まで鳴るとみなす
    （lane の実際の割当は Realizer の仕事。ここでは粗い区間の重なりだけ数える）。"""
    notes = sorted((e for e in events if isinstance(e, NoteEvent)), key=lambda e: e.step)
    if not notes:
        return
    ends = []
    for i, e in enumerate(notes):
        if e.dur is not None:
            ends.append(e.step + e.dur)
        else:
            nxt = next((n.step for n in notes[i + 1:] if n.inst == e.inst), None)
            ends.append(nxt if nxt is not None else e.step + 1)
    points = sorted({e.step for e in notes} | {end for end in ends})
    for t in points:
        active = sum(1 for e, end in zip(notes, ends) if e.step <= t < end)
        if active > part.poly:
            raise PlanError(f"{genre.id}: part {part.name!r}: {active} simultaneous notes exceed poly={part.poly} "
                             f"at step {t}")
