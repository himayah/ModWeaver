"""TrackerRealizer（MOD・S3M・XM・IT。DESIGN.md §7.6）。

``realize(genre, score, plan, target)`` が Score を ``core.native.RealizedSong`` にする。形式の差は
``encode.Codec`` の表と、``Target`` の上限（行数・pattern 数・サンプル数）だけで吸収する。
書き出しは形式ごとの writer（``core/native_*.py``・MOD は ``core/writer.py``）が行う。
"""
from __future__ import annotations

import logging
import math
from typing import TYPE_CHECKING, Optional

from ...core import dsp
from ...core import groove as groovemod
from ...core.model import SampleSpec
from ...core.native import RCell, RealizedSong, RGrid
from ...core.pitch import PERIODS
from ...errors import PlanError
from ..score import Arpeggio, Cut, Delay, Glide, NoteEvent, Offset, Retrig, TempoEvent, Tremolo, Vibrato
from . import lanes as lanesmod
from . import samples as samplesmod
from .encode import PRIORITY, Codec
from .lanes import AutomationPlacement, LaneLayout, Placement

if TYPE_CHECKING:
    from ..genre import Genre
    from ..plan import SectionPlan, SongPlan
    from ..score import Score
    from ..target import Target

log = logging.getLogger("mod_weaver")

_TEMPO_SEARCH_ROWS = 8   # row 0 が全チャンネル埋まっていても、近くの row で空きを探す（DESIGN.md §7.6）


# ============================================================
# 公開エントリポイント
# ============================================================

class _Ctx:
    """区間をまたいで共有する値（読み取り専用）。"""

    def __init__(self, genre: "Genre", layout: LaneLayout, target: "Target", codec: Codec, bpm: int,
                 specs: list[SampleSpec], slot_of: dict, release: tuple) -> None:
        self.genre, self.layout, self.target, self.codec, self.bpm = genre, layout, target, codec, bpm
        self.specs, self.slot_of, self.release = specs, slot_of, release
        self.lane_by_index = {l.index: l for l in layout.lanes}
        control = [l.index for l in layout.lanes if l.role == "control"]
        self.control: Optional[int] = control[0] if control else None


def realize(genre: "Genre", score: "Score", plan: "SongPlan", target: "Target", *,
            level: bool = True) -> RealizedSong:
    """``level=False`` は音量の底上げをしない（``tools/calibrate_native_levels.py`` が測るため）。"""
    if target.kind != "tracker":
        raise PlanError(f"TrackerRealizer cannot realize format {target.format!r}")
    fmt = "it" if target.format == "mp3" else target.format
    codec = Codec(fmt)

    layout = lanesmod.compute_layout(genre, score, target.budget)
    placements_by_section = lanesmod.assign_events(genre, layout, score)
    specs, slot_of, inst_names, release = samplesmod.plan_samples(genre, layout, score, target,
                                                                    placements_by_section)
    ctx = _Ctx(genre, layout, target, codec, plan.bpm, specs, slot_of, release)
    n_ch = layout.budget if fmt == "mod" else len(layout.lanes)

    if not score.order:
        raise PlanError(f"{genre.id}: empty song (score.order is empty)")
    ticks_set = {s.plan.meter.ticks_per_step for s in score.sections.values()}
    any_swing = any(s.plan.swing is not None for s in score.sections.values())
    first_section = score.order[0]

    section_grids: dict[str, RGrid] = {}
    for name, sec_score in score.sections.items():
        sec_plan = sec_score.plan
        placements, autos = placements_by_section[name]
        grid = RGrid(sec_plan.steps, n_ch, exclusive=codec.exclusive_vol_fx)
        _fill_notes(ctx, grid, sec_plan, placements)
        _apply_automation(ctx, grid, autos)
        _apply_sidechain(ctx, grid, sec_score)
        # 区間ごとに Speed が違う（スウィングを含む）ときだけ毎区間の先頭に書く。スウィングの区間は全 row に書く
        write_speed = name == first_section or len(ticks_set) > 1 or any_swing
        _write_tempo(ctx, grid, sec_score, sec_plan.meter.ticks_per_step if write_speed else None, sec_plan.swing)
        section_grids[name] = grid

    patterns: list[RGrid] = []
    pattern_index_of: dict[str, list[int]] = {}
    measure_rows: list[tuple[int, ...]] = []
    for name, sec_score in score.sections.items():
        idxs = []
        for pat, steps in _split_into_patterns(ctx, sec_score.plan, section_grids[name]):
            idxs.append(len(patterns))
            patterns.append(pat)
            measure_rows.append(steps)
        pattern_index_of[name] = idxs

    order: list[int] = []
    for name in score.order:
        order.extend(pattern_index_of[name])
    if len(patterns) > target.max_patterns:
        raise PlanError(f"{genre.id}: {len(patterns)} patterns exceed {target.format}'s limit {target.max_patterns}")
    if len(order) > target.max_orders:
        raise PlanError(f"{genre.id}: order length {len(order)} exceeds {target.format}'s limit {target.max_orders}")

    rs = RealizedSong(
        format=fmt, title=genre.title, samples=specs, patterns=patterns, order=order,
        channel_pans=tuple(l.pan for l in layout.lanes), initial_bpm=plan.bpm, instrument_names=inst_names,
        sample_release=release, measure_rows=tuple(measure_rows),
        rows_per_measure=score.sections[first_section].plan.meter.steps)
    if level:
        from ...core import native_level
        from ..levels import PEAK_DB
        rs = native_level.lift(rs, PEAK_DB.get(genre.id))
    return rs


# ============================================================
# 音符の書き込み（DESIGN.md §7.6・§7.6）
# ============================================================

def _looped(spec: SampleSpec) -> bool:
    return spec.loop is not None


def _frames(spec: SampleSpec) -> int:
    return len(spec.data) // (spec.bits // 8)


def _candidates(ctx: _Ctx, p: Placement, spec: SampleSpec, step_ticks: int, note: Optional[int]) -> list:
    """トリガーの row に乗せたい (優先度, 種類, fx) の候補（奏法の宣言順）。span 型は ``at == 0`` のものだけ。"""
    codec = ctx.codec
    out: list = []
    for art in p.arts:
        if isinstance(art, Delay):
            groovemod.delay_param(art.ticks)    # 範囲の検査
            out.append((PRIORITY["delay"], "delay", codec.delay(art.ticks)))
        elif isinstance(art, Retrig):
            groovemod.retrigger_param(art.ticks)
            out.append((PRIORITY["retrig"], "retrig", codec.retrig(art.ticks)))
        elif isinstance(art, Cut):
            out.append((PRIORITY["cut"], "cut", codec.cut(art.ticks)))
        elif isinstance(art, Offset):
            xx = round(art.fraction * _frames(spec) / 256)
            out.append((PRIORITY["offset"], "offset", codec.offset(xx)))
        elif isinstance(art, Glide):
            # 直前の tracker note が分からないため厳密な portamento_param は計算できない（score 層は period を
            # 知らない）。Glide.param が無指定のときは最小速度にする（DESIGN_HISTORY.md §15）。
            out.append((PRIORITY["glide"], "glide", codec.glide(art.param if art.param is not None else 1)))
        elif isinstance(art, Arpeggio):
            top = (note or 0) + max(art.x, art.y)
            if top > codec.note_range[1]:
                from ...errors import PitchRangeError
                raise PitchRangeError(f"{spec.name}: arpeggio {art.x:X}{art.y:X} on note {note} exceeds "
                                       f"{codec.note_range[1]}")
            out.append((PRIORITY["arpeggio"], "arpeggio", codec.arpeggio(art.x, art.y)))
        elif isinstance(art, Vibrato) and art.at == 0:
            out.append((PRIORITY["vibrato"], "vibrato", codec.vibrato(art.param)))
        elif isinstance(art, Tremolo) and art.at == 0:
            out.append((PRIORITY["tremolo"], "tremolo", codec.tremolo(art.param)))
    return out


def _span(ctx: _Ctx, grid: RGrid, lane: int, start: int, count: int, limit: int, first, rest) -> None:
    """``start`` から ``count`` 行、``first`` を最初の行に、``rest`` を残りの行に書く（``limit`` 未満の row だけ）。
    既に fx のある row（別の奏法）は潰さない。"""
    for k, row in enumerate(range(start, min(start + count, limit))):
        c = grid.get(row, lane)
        if c.fx is not None:
            continue
        fx = first if k == 0 else rest
        grid.put(row, lane, RCell(c.note, c.sample, c.vol, fx))


def _write_note(ctx: _Ctx, grid: RGrid, lane: int, step: int, next_step: Optional[int], p: Placement,
                 slot: int, spec: SampleSpec, step_ticks: int) -> None:
    codec = ctx.codec
    note = codec.note(spec, round(p.pitch) if p.pitch is not None else None,
                       where=f" (step {step}, lane {lane})")

    arts = list(p.arts)
    if p.strum_ms > 0 and not p.chord:       # 和音の声部（DESIGN.md §7.6）: 声部 i を Delay で遅らせる
        tick_ms = 2500.0 / ctx.bpm
        ticks = min(step_ticks - 1, round(p.strum_ms / tick_ms))
        if ticks >= 1 and not any(isinstance(a, Delay) for a in arts):
            arts.insert(0, Delay(min(ticks, 15)))
    p = _with_arts(p, arts)

    cands = _candidates(ctx, p, spec, step_ticks, note)
    best = min(cands, key=lambda c: c[0]) if cands else None
    vol = p.vel
    shifted: set[str] = set()                # トリガー行を取れなかった span 型（次の row へ移す）
    if codec.exclusive_vol_fx and best is not None:
        if vol is None or vol == spec.volume:
            vol = None                       # 既定音量と同じなので書かなくてよい（発音で既定に戻る）
        elif best[1] in ("vibrato", "tremolo"):
            shifted.add(best[1])             # 音量を残して、奏法は次の row へ（DESIGN.md §7.6 の2）
            best = None
        else:
            vol = None                       # Delay・Glide・Retrig・Cut・Arpeggio・Offset: エフェクトを残す
    for c in cands:
        if c is not best and c[1] in ("vibrato", "tremolo"):
            shifted.add(c[1])
        elif c is not best:
            log.debug("articulation %s dropped at step %d lane %d (cell conflict)", c[1], step, lane)
    fx = best[2] if best is not None else None
    grid.put(step, lane, RCell(note, slot, vol, fx))

    end_step = step + p.dur if p.dur is not None else None
    limit = min(x for x in (next_step, end_step, grid.rows) if x is not None)

    for art in p.arts:
        if isinstance(art, (Vibrato, Tremolo)):
            kind = "vibrato" if isinstance(art, Vibrato) else "tremolo"
            mk = codec.vibrato if kind == "vibrato" else codec.tremolo
            if art.at > 0:
                _span(ctx, grid, lane, step + art.at, art.steps, limit, mk(art.param), mk(0))
            elif kind in shifted:
                _span(ctx, grid, lane, step + 1, art.steps, limit, mk(art.param), mk(0))
            else:
                _span(ctx, grid, lane, step + 1, art.steps - 1, limit, mk(0), mk(0))   # 継続は「メモリ継続」の 0
        elif isinstance(art, Arpeggio):
            fxv = codec.arpeggio(art.x, art.y)
            _span(ctx, grid, lane, step + 1, art.steps - 1, limit, fxv, fxv)   # 0xy に継続の短縮形は無い
        elif isinstance(art, Glide):
            param = art.param if art.param is not None else 1
            _span(ctx, grid, lane, step + 1, (art.steps if art.steps is not None else 1) - 1, limit,
                  codec.glide(param), codec.glide(param))

    stop_limit = next_step if next_step is not None else grid.rows
    if end_step is not None and end_step < stop_limit and end_step < grid.rows:
        _put_stop(ctx, grid, lane, end_step, stop_limit, ctx.release[slot - 1], step_ticks)


def _put_stop(ctx: _Ctx, grid: RGrid, lane: int, row: int, limit: int, release_s: Optional[float],
              step_ticks: int) -> None:
    """lane の音を ``row`` で止める（DESIGN.md §7.6）。``release_s`` が無ければ即時に止める。ある場合、XM・IT はキーオフ
    （エンベロープがリリースする）、MOD・S3M は音量スライド（``Axy``／``Dxy``）を ``release_s`` の間 row ごとに置き、
    終わりで止める（``limit`` 未満の、空いている row だけ）。"""
    codec = ctx.codec
    if release_s is not None and not codec.has_release_env and step_ticks > 1:
        base = _volume_at(ctx, grid, lane, row)
        n = max(1, math.ceil(release_s / (step_ticks * 2.5 / ctx.bpm)))
        if base > 0:
            per_tick = max(1, min(15, round(base / (n * (step_ticks - 1)))))
            end = min(row + n, limit, grid.rows)
            for r in range(row, end):
                c = grid.get(r, lane)
                if c.fx is None and c.note is None:
                    grid.put(r, lane, RCell(fx=codec.volume_slide_down(per_tick)))
            if end < min(limit, grid.rows) and grid.get(end, lane).is_empty:
                grid.put(end, lane, codec.stop_cell())
            return
    grid.put(row, lane, codec.stop_cell(release_s))


def _note_freq(codec: Codec, spec: SampleSpec, note: int) -> float:
    """tracker note で鳴るサンプルの再生レート（Hz）。MOD は period 表（Paula のクロック ÷ period。``dsp.sample_rate()`` は
    合成時の基準レートで別物）、他の形式は基準ノートで ``rate_hz``、1 半音ごとに 2^(1/12)。"""
    if codec.fmt == "mod":
        return dsp.CLOCK / PERIODS[max(0, min(len(PERIODS) - 1, note))]
    return spec.rate_hz * 2 ** ((note - codec.n_ref) / 12)


def _glide_param(codec: Codec, prev_spec: SampleSpec, prev_note: int, spec: SampleSpec, note: int,
                 active_ticks: int) -> int:
    """直前の音の period から目標の period まで ``active_ticks`` 個の tick で届く ``3xx``/``Gxx`` の速さ。

    スライドは row の最初の tick には掛からない（MOD・S3M・XM・IT 共通）ので、``active_ticks`` は ``steps × (row の tick 数 − 1)``。
    速さ 1 につき tick あたり「Amiga 換算の period（クロック ÷ 2 ÷ 再生レート）」が 1 動くことを、4 形式とも実プレイヤーで
    測って確かめた（S3M・IT は period の単位が 4 倍だがスライドも 4 倍なので換算は同じ。
    ``tests/realplayer/test_glide_real_player.py``）。"""
    delta = abs(dsp.CLOCK / _note_freq(codec, prev_spec, prev_note) - dsp.CLOCK / _note_freq(codec, spec, note))
    return max(1, min(255, round(delta / max(1, active_ticks))))


def _prev_sounding(ctx: _Ctx, prev: Optional[Placement], prev_spec: Optional[SampleSpec], prev_note: Optional[int],
                   p: Placement, step_ticks: int) -> bool:
    """``p`` の発音の時点で、同じ lane の直前の音がまだ鳴っているか（鳴り終わっていれば滑らせる音が無い。DESIGN.md §3.3）。"""
    if prev is None or prev.kind != "note" or prev_spec is None or prev_note is None:
        return False
    if prev.dur is not None and prev.step + prev.dur <= p.step:
        return False
    if _looped(prev_spec):
        return True
    elapsed = (p.step - prev.step) * step_ticks * 2.5 / ctx.bpm
    return elapsed < _frames(prev_spec) / _note_freq(ctx.codec, prev_spec, prev_note)


def _resolve_glide(ctx: _Ctx, lane, prev: Optional[Placement], p: Placement, step_ticks: int) -> Placement:
    """``Glide`` を実際の速さに直す。直前の音が鳴り終わっていれば ``Glide`` を外して普通の発音にする。
    ``Glide.param`` を明示してあればそのまま使う（鳴り終わっていたときの扱いは同じ）。"""
    glide = next((a for a in p.arts if isinstance(a, Glide)), None)
    if glide is None:
        return p
    codec = ctx.codec
    prev_spec = prev_note = None
    if prev is not None and prev.kind == "note":
        prev_slot = ctx.slot_of.get(samplesmod.sample_key(codec.fmt, ctx.genre, prev, lane))
        if prev_slot is not None:
            prev_spec = ctx.specs[prev_slot - 1]
            prev_note = codec.note(prev_spec, round(prev.pitch) if prev.pitch is not None else None)
    if not _prev_sounding(ctx, prev, prev_spec, prev_note, p, step_ticks):
        return _with_arts(p, [a for a in p.arts if a is not glide])
    if glide.param is not None:
        return p
    slot = ctx.slot_of[samplesmod.sample_key(codec.fmt, ctx.genre, p, lane)]
    spec = ctx.specs[slot - 1]
    note = codec.note(spec, round(p.pitch) if p.pitch is not None else None)
    steps = glide.steps if glide.steps is not None else 1
    param = _glide_param(codec, prev_spec, prev_note, spec, note, steps * (step_ticks - 1))
    return _with_arts(p, [Glide(glide.steps, param) if a is glide else a for a in p.arts])


def _with_arts(p: Placement, arts: list) -> Placement:
    import dataclasses
    return p if tuple(arts) == p.arts else dataclasses.replace(p, arts=tuple(arts))


def _fill_notes(ctx: _Ctx, grid: RGrid, sec_plan: "SectionPlan", placements: list[Placement]) -> None:
    codec = ctx.codec
    step_ticks = sec_plan.meter.ticks_per_step
    by_lane: dict[int, list[Placement]] = {}
    for p in placements:
        by_lane.setdefault(p.lane, []).append(p)

    for lane_idx, events in by_lane.items():
        events.sort(key=lambda p: p.step)
        lane = ctx.lane_by_index[lane_idx]
        for i, p in enumerate(events):
            next_step = events[i + 1].step if i + 1 < len(events) else None
            if p.kind == "off":
                _put_stop(ctx, grid, lane_idx, p.step, next_step if next_step is not None else grid.rows,
                          _release_of_inst(ctx, p.inst), step_ticks)
                continue
            p = _resolve_glide(ctx, lane, events[i - 1] if i > 0 else None, p, step_ticks)
            key = samplesmod.sample_key(codec.fmt, ctx.genre, p, lane)
            slot = ctx.slot_of.get(key)
            if slot is None:
                raise PlanError(f"no sample planned for {key} (lane assignment / sample planning disagree)")
            _write_note(ctx, grid, lane_idx, p.step, next_step, p, slot, ctx.specs[slot - 1], step_ticks)

        last = events[-1]
        if last.kind == "note" and last.dur is None:
            key = samplesmod.sample_key(codec.fmt, ctx.genre, last, lane)
            slot = ctx.slot_of.get(key)
            if slot is not None and _looped(ctx.specs[slot - 1]) and grid.rows - 1 > last.step:
                # 区間の終わりのループ停止: スライドは次の区間にはみ出せないので、MOD・S3M は即時に止める
                rel = ctx.release[slot - 1] if codec.has_release_env else None
                _put_stop(ctx, grid, lane_idx, grid.rows - 1, grid.rows, rel, step_ticks)


def _release_of_inst(ctx: _Ctx, inst_name: str) -> Optional[float]:
    return ctx.genre.instruments[inst_name].release_s


# ============================================================
# オートメーション（DESIGN.md §7.6）
# ============================================================

def _apply_automation(ctx: _Ctx, grid: RGrid, autos: list[AutomationPlacement]) -> None:
    codec = ctx.codec
    for a in autos:
        if not 0 <= a.step < grid.rows:
            continue
        for lane in a.lanes:
            c = grid.get(a.step, lane)
            if a.kind == "volume":
                if codec.exclusive_vol_fx and c.fx is not None:
                    continue   # 効果を使っている行は潰さない（DESIGN.md §7.6）
                grid.put(a.step, lane, RCell(c.note, c.sample, max(0, min(64, a.value)), c.fx))
            else:
                fx = codec.pan(a.value) if a.kind == "pan" else codec.cutoff(a.value)
                if fx is None or c.fx is not None:
                    continue   # 表せない形式（MOD のパン、IT 以外のカットオフ）は無視。他の効果は潰さない
                grid.put(a.step, lane, RCell(c.note, c.sample, c.vol, fx))


# ============================================================
# サイドチェイン（DESIGN.md §7.6）
# ============================================================

def _volume_at(ctx: _Ctx, grid: RGrid, lane: int, row: int) -> int:
    for r in range(row, -1, -1):
        c = grid.get(r, lane)
        if c.vol is not None:
            return c.vol
        if c.note is not None and c.note >= 0 and c.sample:
            return ctx.specs[c.sample - 1].volume
        if c.note is not None and c.note < 0:
            return 0           # 止められている
    return 0


def _apply_sidechain(ctx: _Ctx, grid: RGrid, sec_score) -> None:
    genre = ctx.genre
    if not genre.mix:
        return
    trigger_steps: dict[str, list[int]] = {}
    for _part, events in sec_score.parts.items():
        for e in events:
            if isinstance(e, NoteEvent):
                trigger_steps.setdefault(e.inst, []).append(e.step)

    for rule in genre.mix:
        steps = sorted({s for trig in rule.triggers for s in trigger_steps.get(trig, ())})
        if not steps:
            continue
        target_lanes = [l.index for name in rule.targets for l in ctx.layout.lanes_of(name)]
        for lane in target_lanes:
            for t in steps:
                for row in range(t, min(t + rule.release_steps + 1, grid.rows)):
                    frac = rule.ratio if row == t else rule.ratio * (1 - (row - t) / rule.release_steps)
                    base = _volume_at(ctx, grid, lane, row)
                    if base <= 0:
                        continue
                    ducked = max(0, round(base * (1 - frac)))
                    c = grid.get(row, lane)
                    if ctx.codec.exclusive_vol_fx and c.fx is not None:
                        continue   # 効果を使っている行は潰さない（ポルタメント等を優先。DESIGN.md §7.6）
                    if c.note is not None and c.note < 0:
                        continue   # 止めるセルの音量は触らない
                    grid.put(row, lane, RCell(c.note, c.sample, ducked, c.fx))


# ============================================================
# テンポ（DESIGN.md §7.6）
# ============================================================

def _insert_near_start(ctx: _Ctx, grid: RGrid, fx, label: str) -> None:
    limit = min(_TEMPO_SEARCH_ROWS, grid.rows)
    for row in range(limit):
        if grid.try_insert_command(row, fx, ctx.control):
            return
    raise PlanError(f"no free channel in the first {limit} rows for a {label} command")


def _write_tempo(ctx: _Ctx, grid: RGrid, sec_score, speed_ticks: Optional[int], swing=None) -> None:
    codec = ctx.codec
    if speed_ticks is not None:
        if swing is None:
            _insert_near_start(ctx, grid, codec.speed(speed_ticks), "Speed")
        _insert_near_start(ctx, grid, codec.tempo(ctx.bpm), "Tempo")
    if swing is not None:
        _write_swing(ctx, grid, swing)
    for ev in sec_score.tempo:
        if isinstance(ev, TempoEvent) and 0 <= ev.step < grid.rows:
            grid.try_insert_command(ev.step, codec.tempo(ev.bpm), ctx.control)


def _make_room(ctx: _Ctx, grid: RGrid, row: int) -> bool:
    """全チャンネルが埋まった row に、row コマンドを書ける場所を1つ作る（旧 ``make_room_for_row_commands``）。
    番号の大きいチャンネルから、①発音もボリュームも無い効果だけのセル（ビブラートの継続など）を消し、②MOD では
    効果の無い発音の音量を外す（その音はサンプルの既定音量で鳴る）。作れたら True。"""
    codec = ctx.codec
    control = {codec.speed(0)[0], codec.tempo(0)[0]}      # Speed・Tempo（Fxx／Axx・Txx）は row コマンドそのもの。消さない
    for ch in reversed(range(grid.channels)):
        c = grid.get(row, ch)
        if (c.note is None and not c.sample and c.vol is None and c.fx is not None
                and c.fx[0] not in control and c.fx != codec.pattern_break()):
            grid.put(row, ch, RCell())
            return True
    if ctx.codec.exclusive_vol_fx:
        for ch in reversed(range(grid.channels)):
            c = grid.get(row, ch)
            if c.note is not None and c.note >= 0 and c.fx is None and c.vol is not None:
                grid.put(row, ch, RCell(c.note, c.sample))
                return True
    return False


def _write_swing(ctx: _Ctx, grid: RGrid, swing) -> None:
    """スウィング（DESIGN.md §7.6）: 偶数 step を ``long``、奇数 step を ``short`` tick の Speed にする（全 row に書く）。
    表示 BPM どおりに鳴らすには全 row に要るので、場所が無い row は作る。それでも作れなければその row だけ飛ばす
    （直前の Speed が続く。DEBUG ログ）。"""
    for row in range(grid.rows):
        fx = ctx.codec.speed(swing.long if row % 2 == 0 else swing.short)
        if grid.try_insert_command(row, fx, ctx.control):
            continue
        if _make_room(ctx, grid, row) and grid.try_insert_command(row, fx, ctx.control):
            continue
        log.debug("swing: no room for a Speed command at row %d", row)


# ============================================================
# pattern への分割（DESIGN.md §7.6）
# ============================================================

def _pattern_rows(codec: Codec, length: int) -> int:
    """pattern の row 数。MOD・S3M は 64 固定、IT は 32 以上、XM は実際の長さそのまま。"""
    if codec.fmt in ("mod", "s3m"):
        return 64
    if codec.fmt == "it":
        return max(length, 32)
    return length


def _split_into_patterns(ctx: _Ctx, sec_plan: "SectionPlan", grid: RGrid) -> list[tuple[RGrid, tuple[int, ...]]]:
    codec, max_rows = ctx.codec, ctx.target.max_rows
    chunks: list[list] = [[]]
    total = 0
    for m in sec_plan.measures:
        if total + m.steps > max_rows and chunks[-1]:
            chunks.append([])
            total = 0
        chunks[-1].append(m)
        total += m.steps

    out: list[tuple[RGrid, tuple[int, ...]]] = []
    for chunk in chunks:
        start = chunk[0].start
        length = sum(m.steps for m in chunk)
        if length > max_rows:
            raise PlanError(f"{sec_plan.name}: measure of {length} steps exceeds {max_rows} rows per pattern")
        rows = _pattern_rows(codec, length)
        pat = RGrid(rows, grid.channels, exclusive=grid.exclusive)
        for r in range(length):
            for ch in range(grid.channels):
                cell = grid.get(start + r, ch)
                if not cell.is_empty:
                    pat.put(r, ch, cell)
        if length < rows:
            if not pat.try_insert_command(length - 1, codec.pattern_break(), ctx.control):
                raise PlanError(f"{sec_plan.name}: no free channel for pattern break at row {length - 1}")
        out.append((pat, tuple(m.steps for m in chunk)))
    return out
