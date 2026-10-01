"""MOD 向け TrackerRealizer（FRAMEWORK_REDESIGN.md §9.6〜§9.10）。

``realize_mod(genre, score, plan, target)`` が Score を ``core.model.Song`` + ``core.formats.WriteOptions``
にする。以降は既存の ``core.level``／``core.formats.get_format("mod")``／``core.writer`` をそのまま使う
（F3 は MOD のみ。S3M/XM/IT は F4 で、ここに一般化した Cell 表現を足して対応する）。
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from ...core.model import Cell, CellGrid, Instrument as CellInstrument, Pattern, SampleSpec, Song
from ...core import groove as groovemod
from ...errors import PlanError
from ..score import Arpeggio, Cut, Delay, Glide, NoteEvent, Offset, Retrig, TempoEvent, Tremolo, Vibrato
from . import lanes as lanesmod
from . import samples as samplesmod
from .lanes import AutomationPlacement, LaneLayout, Placement

if TYPE_CHECKING:
    from ...core.formats import WriteOptions
    from ..genre import Genre
    from ..plan import SectionPlan, SongPlan
    from ..score import Score
    from ..target import Target


# ============================================================
# 公開エントリポイント
# ============================================================

def realize_mod(genre: "Genre", score: "Score", plan: "SongPlan", target: "Target") -> tuple[Song, "WriteOptions"]:
    from ...core.formats import WriteOptions

    if target.format != "mod":
        raise NotImplementedError(f"realize_mod only supports format='mod' (got {target.format!r}); "
                                   "other tracker formats land in F4")

    layout = lanesmod.compute_layout(genre, score, target.budget)
    specs, slot_of, inst_names = samplesmod.plan_samples(genre, layout, score, target)
    placements_by_section = lanesmod.assign_events(genre, layout, score)
    cell_insts = {slot: CellInstrument(slot, specs[slot - 1]) for slot in slot_of.values()}

    section_grids: dict[str, CellGrid] = {}
    prev_ticks: Optional[int] = None
    for name, sec_score in score.sections.items():
        sec_plan = sec_score.plan
        placements, autos = placements_by_section[name]
        grid = CellGrid(rows=sec_plan.steps, plan=None, strict=False, channels=layout.budget)
        _fill_notes(grid, layout, placements, cell_insts, specs, slot_of)
        _apply_automation(grid, autos)
        _apply_sidechain(grid, genre, layout, sec_score, specs)
        ticks = sec_plan.meter.ticks_per_step
        want_speed = ticks if ticks != prev_ticks else None
        _write_tempo(grid, sec_score, plan.bpm, want_speed)
        prev_ticks = ticks
        section_grids[name] = grid

    patterns: list[Pattern] = []
    pattern_index_of: dict[str, list[int]] = {}    # 区間名 → その区間を構成する pattern index の並び
    measure_rows: list[tuple[int, ...]] = []
    for name, sec_score in score.sections.items():
        chunks = _split_into_patterns(sec_score.plan, section_grids[name], layout.budget)
        idxs = []
        for pat, steps in chunks:
            idxs.append(len(patterns))
            patterns.append(pat)
            measure_rows.append(steps)
        pattern_index_of[name] = idxs

    order: list[int] = []
    for name in score.order:
        order.extend(pattern_index_of[name])
    if not order:
        raise PlanError(f"{genre.id}: empty song (score.order is empty)")

    song = Song(title=genre.title, samples=specs, patterns=patterns, order=order,
                instrument_names=inst_names)

    channel_pans = tuple(l.pan for l in layout.lanes)
    gm_voices = {name: genre.instruments[name].gm for name in dict.fromkeys(inst_names)}
    opts = WriteOptions(channel_pans=channel_pans, initial_bpm=plan.bpm, instrument_names=inst_names,
                         gm_voices=gm_voices, rows_per_measure=score.sections[score.order[0]].plan.meter.steps,
                         measure_rows=tuple(measure_rows))
    return song, opts


# ============================================================
# 音符の書き込み（§9.6・§9.7）
# ============================================================

def _looped(spec: SampleSpec) -> bool:
    return spec.loop is not None


def _offset_param(art: Offset, spec: SampleSpec) -> int:
    length_bytes = len(spec.data)
    return max(0, min(255, round(art.fraction * length_bytes / 256)))


def _trigger_effect(arts: tuple, spec: SampleSpec) -> Optional[tuple[int, int]]:
    """トリガーの行に乗せる (effect, param)。複数あっても Cell は1つしか持てないため、
    宣言順の最初の1つだけを使う（§9.6）。span 型（Vibrato/Tremolo）で ``at>0`` のものは
    トリガー行には乗せない（``_apply_vibrato_tremolo`` が続く行に書く）。"""
    for art in arts:
        if isinstance(art, Delay):
            return 0xE, groovemod.delay_param(art.ticks)
        if isinstance(art, Retrig):
            return 0xE, groovemod.retrigger_param(art.ticks)
        if isinstance(art, Cut):
            if not 1 <= art.ticks <= 15:
                raise PlanError(f"Cut ticks out of range: {art.ticks}")
            return 0xE, 0xC0 | art.ticks
        if isinstance(art, Offset):
            return 0x9, _offset_param(art, spec)
        if isinstance(art, Glide):
            # 直前の tracker note が分からないため厳密な portamento_param は計算できない（score 層は
            # period を知らない）。Glide.param が無指定のときは最小速度にする（現行ジャンルは未使用）。
            return 0x3, art.param if art.param is not None else 1
        if isinstance(art, Vibrato) and art.at == 0:
            return 0x4, art.param
        if isinstance(art, Tremolo) and art.at == 0:
            return 0x7, art.param
        if isinstance(art, Arpeggio):
            return 0x0, (art.x << 4) | art.y
    return None


def _apply_vibrato_tremolo(grid: CellGrid, lane: int, step: int, limit: int, art) -> None:
    effect = 0x4 if isinstance(art, Vibrato) else 0x7
    start = step + art.at
    for row in range(start, min(start + art.steps, limit)):
        if row == step:
            continue   # トリガー行は _trigger_effect が既に書いている（at=0 のとき）
        param = art.param if row == start else 0   # 継続行は「メモリ継続」の 0（PT の規約）
        grid.put(row, lane, Cell(None, 0, effect, param))


def _apply_arpeggio(grid: CellGrid, lane: int, step: int, limit: int, art: Arpeggio) -> None:
    param = (art.x << 4) | art.y
    for row in range(step, min(step + art.steps, limit)):
        if row == step:
            continue
        grid.put(row, lane, Cell(None, 0, 0x0, param))   # 0xy に「継続」短縮形は無いので毎行書く


def _apply_glide(grid: CellGrid, lane: int, step: int, limit: int, art: Glide) -> None:
    steps = art.steps if art.steps is not None else 1
    param = art.param if art.param is not None else 1
    for row in range(step, min(step + steps, limit)):
        if row == step:
            continue
        grid.put(row, lane, Cell(None, 0, 0x3, param))


def _write_note(grid: CellGrid, lane: int, step: int, next_step: Optional[int], p: Placement,
                 inst: CellInstrument, spec: SampleSpec) -> None:
    n = round(p.pitch) if p.pitch is not None else None
    arts = p.arts
    eff = _trigger_effect(arts, spec)
    vol = None if eff is not None else p.vel
    effect, param = eff if eff is not None else (0, 0)
    cell = inst.cell(n, vol=vol, effect=effect, param=param)
    grid.put(step, lane, cell)

    end_step = step + p.dur if p.dur is not None else None
    limit = min(x for x in (next_step, end_step, grid.rows) if x is not None)

    for art in arts:
        if isinstance(art, (Vibrato, Tremolo)):
            _apply_vibrato_tremolo(grid, lane, step, limit, art)
        elif isinstance(art, Arpeggio):
            _apply_arpeggio(grid, lane, step, limit, art)
        elif isinstance(art, Glide):
            _apply_glide(grid, lane, step, limit, art)

    stop_limit = next_step if next_step is not None else grid.rows
    if end_step is not None and end_step < stop_limit and end_step < grid.rows:
        grid.put(end_step, lane, Cell(None, 0, 0, 0, vol=0))


def _fill_notes(grid: CellGrid, layout: LaneLayout, placements: list[Placement],
                 cell_insts: dict[int, CellInstrument], specs: list[SampleSpec],
                 slot_of: dict) -> None:
    by_lane: dict[int, list[Placement]] = {}
    for p in placements:
        by_lane.setdefault(p.lane, []).append(p)

    for lane_idx, events in by_lane.items():
        events.sort(key=lambda p: p.step)
        for i, p in enumerate(events):
            next_step = events[i + 1].step if i + 1 < len(events) else None
            if p.kind == "off":
                grid.put(p.step, lane_idx, Cell(None, 0, 0, 0, vol=0))
                continue
            key = (p.inst, p.chord) if p.chord else (p.inst, ())
            slot = slot_of.get(key)
            if slot is None:
                raise PlanError(f"no sample planned for {key} (lane assignment / sample planning disagree)")
            inst = cell_insts[slot]
            spec = specs[slot - 1]
            _write_note(grid, lane_idx, p.step, next_step, p, inst, spec)

        last = events[-1]
        if last.kind == "note":
            key = (last.inst, last.chord) if last.chord else (last.inst, ())
            slot = slot_of.get(key)
            if slot is not None and last.dur is None and _looped(specs[slot - 1]):
                if grid.rows - 1 > last.step:
                    grid.put(grid.rows - 1, lane_idx, Cell(None, 0, 0, 0, vol=0))


def _apply_automation(grid: CellGrid, autos: list[AutomationPlacement]) -> None:
    """``Automation``（§5）を Cell に落とす。MOD の features（target.py）には pan_automation も
    filter も無いので、"volume" 以外は無視する（§9.8。将来 S3M/XM/IT では使えるようになる）。"""
    for a in autos:
        if a.kind != "volume":
            continue
        for lane in a.lanes:
            if not 0 <= a.step < grid.rows:
                continue
            c = grid.get(a.step, lane)
            if c.has_effect:
                continue   # 効果を使っている行は潰さない（§9.8 と同じ規約）
            grid.replace(a.step, lane, Cell(c.note, c.sample, 0, 0, vol=max(0, min(64, a.value))))


# ============================================================
# サイドチェイン（§9.8）
# ============================================================

def _volume_at(grid: CellGrid, specs: list[SampleSpec], lane: int, row: int) -> int:
    for r in range(row, -1, -1):
        c = grid.get(r, lane)
        if c.vol is not None:
            return c.vol
        if c.note is not None and c.sample:
            return specs[c.sample - 1].volume
    return 0


def _apply_sidechain(grid: CellGrid, genre: "Genre", layout: LaneLayout, sec_score,
                      specs: list[SampleSpec]) -> None:
    if not genre.mix:
        return
    trigger_steps: dict[str, list[int]] = {}
    for part_name, events in sec_score.parts.items():
        for e in events:
            if isinstance(e, NoteEvent):
                trigger_steps.setdefault(e.inst, []).append(e.step)

    for rule in genre.mix:
        steps = sorted({s for trig in rule.triggers for s in trigger_steps.get(trig, ())})
        if not steps:
            continue
        target_lanes = [l.index for name in rule.targets for l in layout.lanes_of(name)]
        for lane in target_lanes:
            for t in steps:
                for row in range(t, min(t + rule.release_steps + 1, grid.rows)):
                    frac = rule.ratio if row == t else rule.ratio * (1 - (row - t) / rule.release_steps)
                    base = _volume_at(grid, specs, lane, row)
                    if base <= 0:
                        continue
                    ducked = max(0, round(base * (1 - frac)))
                    c = grid.get(row, lane)
                    if c.has_effect:
                        continue   # 効果を使っている行は潰さない（ポルタメント等を優先。§9.8）
                    grid.replace(row, lane, Cell(c.note, c.sample, 0, 0, vol=ducked))


# ============================================================
# テンポ（§9.9・EXT-5 流用）
# ============================================================

_TEMPO_SEARCH_ROWS = 8   # row 0 が全チャンネル埋まっていても、近くの row で空きを探す（§9.9）


def _insert_near_start(grid: CellGrid, param: int, label: str) -> None:
    limit = min(_TEMPO_SEARCH_ROWS, grid.rows)
    for row in range(limit):
        if grid.try_insert_command(row, 0x0F, param):
            return
    raise PlanError(f"no free channel in the first {limit} rows for a {label} command")


def _write_tempo(grid: CellGrid, sec_score, song_bpm: int, speed: Optional[int]) -> None:
    if speed is not None:
        _insert_near_start(grid, speed, "Speed")
        _insert_near_start(grid, song_bpm, "Tempo")
    for ev in sec_score.tempo:
        if isinstance(ev, TempoEvent) and 0 <= ev.step < grid.rows:
            grid.try_insert_command(ev.step, 0x0F, ev.bpm)


# ============================================================
# pattern への分割（§9.9）
# ============================================================

def _split_into_patterns(sec_plan: "SectionPlan", grid: CellGrid, budget: int
                          ) -> list[tuple[Pattern, tuple[int, ...]]]:
    from ...core.model import ROWS_PER_PATTERN

    max_rows = ROWS_PER_PATTERN
    chunks: list[list] = [[]]
    total = 0
    for m in sec_plan.measures:
        if total + m.steps > max_rows and chunks[-1]:
            chunks.append([])
            total = 0
        chunks[-1].append(m)
        total += m.steps

    out: list[tuple[Pattern, tuple[int, ...]]] = []
    for chunk in chunks:
        start = chunk[0].start
        length = sum(m.steps for m in chunk)
        pat = Pattern(plan=None, strict=False, rows=max_rows, channels=budget)
        for r in range(length):
            for ch in range(budget):
                cell = grid.get(start + r, ch)
                if not cell.is_empty:
                    pat.put(r, ch, cell)
        if length < max_rows:
            if not pat.try_insert_command(length - 1, 0x0D, 0):
                raise PlanError(f"{sec_plan.name}: no free channel for pattern break at row {length - 1}")
        out.append((pat, tuple(m.steps for m in chunk)))
    return out
