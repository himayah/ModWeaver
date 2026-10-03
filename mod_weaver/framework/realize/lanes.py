"""パートの選択・lane の需要と ladder・チャンネルの並びとパン・イベントの lane への割当
（FRAMEWORK_REDESIGN.md §9.2〜§9.5）。

MOD 専用ではない設計にしてあるが、F3 の時点で実際に使うのは MOD（制御チャンネル・和音の声部化は
B の大きい S3M/XM/IT でこそ本領を発揮する。§9.3 の計算例を参照）。
"""
from __future__ import annotations

import dataclasses as dc
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Mapping, Optional

from ...errors import ChannelCountError, PlanError
from ..score import Automation, Event, NoteEvent, NoteOff

if TYPE_CHECKING:
    from ..genre import Genre, Part
    from ..score import Score


# ============================================================
# lane の種類と需要（§9.3）
# ============================================================

@dataclass
class _PartDemand:
    part: "Part"
    used_instruments: tuple[str, ...] = ()   # kit パート: このパートで実際に使われた楽器名（宣言順）
    max_chord_voices: int = 0                # 和音パート: 観測された最大構成音数（0 なら和音なしの意味）
    chord_shapes: frozenset[tuple[int, ...]] = field(default_factory=frozenset)   # 観測された chord の形
    kit_stage: str = "separate"              # "separate" | "merged" | "single"（kit パートのみ使う）
    chord_stage: str = "voices"              # "voices" | "baked"（和音パートのみ使う）
    has_double: bool = False                 # まだ複製が付いているか（double 宣言パートのみ）

    @property
    def is_kit(self) -> bool:
        return self.part.kit is not None

    @property
    def is_chord(self) -> bool:
        return self.max_chord_voices > 0

    def base_lane_count(self) -> int:
        if self.is_kit:
            if self.kit_stage == "single":
                return 1 if self.used_instruments else 0
            if self.kit_stage == "merged":
                groups = self.part.kit.groups
                used = set(self.used_instruments)
                return sum(1 for _lane, names in groups if used & set(names))
            return len(self.used_instruments)      # "separate"
        if self.is_chord:
            return 1 if self.chord_stage == "baked" else self.max_chord_voices
        return self.part.poly

    def lane_count(self) -> int:
        n = self.base_lane_count()
        return n * 2 if self.has_double else n


def _collect_used_instruments(part: "Part", score: "Score") -> tuple[str, ...]:
    """このパートが全区間を通じて実際に発音した楽器名（宣言順。Kit があればその順、無ければ出現順）。"""
    seen: set[str] = set()
    for sec in score.sections.values():
        for e in sec.parts.get(part.name, ()):
            if isinstance(e, (NoteEvent, NoteOff)):
                seen.add(e.inst)
    if part.kit is not None:
        return tuple(name for name in part.kit.instruments if name in seen)
    return tuple(sorted(seen))   # kit を持たないパートは楽器が1種類のはず（念のため決定的な順に）


def _chord_shapes(part: "Part", score: "Score") -> frozenset[tuple[int, ...]]:
    """このパートで実際に使われた ``NoteEvent.chord`` の形（根音からのオフセット列）の集合。"""
    shapes: set[tuple[int, ...]] = set()
    for sec in score.sections.values():
        for e in sec.parts.get(part.name, ()):
            if isinstance(e, NoteEvent) and e.chord:
                shapes.add(e.chord)
    return frozenset(shapes)


def _build_demands(genre: "Genre", score: "Score") -> dict[str, _PartDemand]:
    demands: dict[str, _PartDemand] = {}
    for part in genre.parts:
        used = _collect_used_instruments(part, score)
        shapes = _chord_shapes(part, score)
        chord_n = max((len(s) for s in shapes), default=0)   # NoteEvent.chord は根音の 0 を含む（score.py）
        demands[part.name] = _PartDemand(
            part=part, used_instruments=used, max_chord_voices=chord_n, chord_shapes=shapes,
            has_double=part.double is not None,
        )
    return demands


# ============================================================
# ladder（§9.3）
# ============================================================

def _total(demands: dict[str, "_PartDemand"], active: list[str]) -> int:
    return sum(demands[name].lane_count() for name in active)


def _apply_ladder(genre: "Genre", demands: dict[str, "_PartDemand"], active: list[str], budget: int) -> None:
    """``demands`` を書き換えて ``_total(...) <= budget`` に収める（収まらなければ PlanError。§9.3 R5）。
    ``active``（予算未満で外れなかったパート名、宣言順）の範囲でだけ動く。
    """
    if _total(demands, active) <= budget:
        return

    # R1: double を外す（後ろのパートから1つずつ）
    for name in reversed(active):
        pd = demands[name]
        if pd.has_double:
            pd.has_double = False
            if _total(demands, active) <= budget:
                return

    # R2: 全 kit を「まとめる」（まとめて1段階ぶん。個別には進めない）
    changed = False
    for name in active:
        pd = demands[name]
        if pd.is_kit and pd.kit_stage == "separate":
            pd.kit_stage = "merged"
            changed = True
    if changed and _total(demands, active) <= budget:
        return

    # R3: 和音を焼く（後ろのパートから1つずつ。焼けない和音は飛ばす）
    for name in reversed(active):
        pd = demands[name]
        if pd.is_chord and pd.chord_stage == "voices":
            if not _can_bake_chord(genre, pd):
                continue
            pd.chord_stage = "baked"
            if _total(demands, active) <= budget:
                return

    # R4: kit を「1本」にする（後ろのパートから1つずつ）
    for name in reversed(active):
        pd = demands[name]
        if pd.is_kit and pd.kit_stage == "merged":
            pd.kit_stage = "single"
            if _total(demands, active) <= budget:
                return

    total = _total(demands, active)
    if total > budget:
        raise ChannelCountError(f"{genre.id}: {budget} channels cannot hold the declared parts (need {total})")


def _can_bake_chord(genre: "Genre", pd: "_PartDemand") -> bool:
    """この和音パートで実際に使われた全ての和音の形が焼けるか試す（§8.4 の誤差 12 セント規則）。
    1つでも焼けない形があれば、このパートは声部のままにする（measure によって lane 数が変わる
    ような不整合な結果を避けるため）。"""
    from ...core.synth import chord_patch
    from ...errors import SampleConstraintError

    inst_name = getattr(pd.part.gen, "inst", None)
    if inst_name is None or inst_name not in genre.instruments:
        return True   # 和音を持つのにどの楽器か分からない場合は検査できないので許可する（描画時に検出される）
    base_patch = genre.instruments[inst_name].patch
    for shape in pd.chord_shapes:
        try:
            chord_patch(base_patch, shape)
        except SampleConstraintError:
            return False
    return True

# ============================================================
# 物理チャンネル（§9.4）
# ============================================================

@dataclass(frozen=True)
class Lane:
    index: int                                   # 物理チャンネル番号（0 始まり）
    part_name: Optional[str]                     # 制御チャンネルは None
    role: str                                     # "kit" | "chord_voice" | "chord_baked" | "mono" | "control"
    pan: int = 128
    insts: tuple[str, ...] = ()                   # この lane に載る楽器名（kit の merged/single は複数）
    priority: Mapping[str, int] = field(default_factory=dict)   # 楽器名→優先度（kit の衝突解決用）
    voice_index: int = 0                          # chord_voice のときの声部番号（0=最低音）
    voice_count: int = 1                          # chord_voice のときの総声部数
    is_double: bool = False


@dataclass(frozen=True)
class LaneLayout:
    budget: int
    lanes: tuple[Lane, ...]                       # 物理チャンネルの並び（index 順）
    active_parts: frozenset[str]                  # 予算で外れなかったパート名

    def lanes_of(self, part_name: str) -> list[Lane]:
        return [l for l in self.lanes if l.part_name == part_name]


AMIGA_LEFT, AMIGA_RIGHT, CENTER = 64, 192, 128


def _all_pans_default(genre: "Genre") -> bool:
    """全パート・全楽器がパンを宣言していないか（DESIGN.md §7.1 の規則2が要るかの判定）。"""
    return all(i.pan is None for i in genre.instruments.values()) and all(p.pan == 128 for p in genre.parts)


def _base_pan(genre: "Genre", part: "Part", inst_names: tuple[str, ...]) -> int:
    """lane の基準パン: 楽器が1つで ``Instrument.pan`` が宣言されていればそれ、無ければ ``Part.pan``。"""
    if len(inst_names) == 1:
        ip = genre.instruments[inst_names[0]].pan
        if ip is not None:
            return ip
    return part.pan


def _build_lanes(genre: "Genre", demands: "dict[str, _PartDemand]", active: list[str], budget: int) -> tuple[Lane, ...]:
    lanes: list[Lane] = []

    for name in active:
        pd = demands[name]
        part = pd.part
        base_lanes: list[Lane] = []
        if pd.is_kit:
            if pd.kit_stage == "separate":
                groups = [(part.kit.group_of(inst), (inst,)) for inst in pd.used_instruments]
            elif pd.kit_stage == "merged":
                used = set(pd.used_instruments)
                groups = [(lane_name, tuple(n for n in names if n in used))
                          for lane_name, names in part.kit.groups if used & set(names)]
            else:   # "single"
                groups = [(None, pd.used_instruments)] if pd.used_instruments else []
            for group_name, insts in groups:
                prio = {i: part.kit.priority.get(i, 1) for i in insts}
                if pd.kit_stage == "single" and part.kit.single_priority is not None:
                    prio = {i: part.kit.single_priority.get(i, 1) for i in insts}
                pan = part.pan if group_name is None else part.kit.group_pan.get(group_name, part.pan)
                base_lanes.append(Lane(0, name, "kit", pan, insts, prio))
        elif pd.is_chord:
            inst_name = getattr(part.gen, "inst", "")
            insts = (inst_name,) if inst_name else ()
            if pd.chord_stage == "baked":
                base_lanes.append(Lane(0, name, "chord_baked", _base_pan(genre, part, insts), insts))
            else:
                k = pd.max_chord_voices
                base = _base_pan(genre, part, insts)
                spread = part.chord_spread
                for i in range(k):
                    pan = base if k <= 1 else round(base + spread * (i / (k - 1) - 0.5))
                    base_lanes.append(Lane(0, name, "chord_voice", max(0, min(255, pan)), insts,
                                            voice_index=i, voice_count=k))
        else:
            inst_name = getattr(part.gen, "inst", "")
            insts = (inst_name,) if inst_name else ()
            for _i in range(part.poly):
                base_lanes.append(Lane(0, name, "mono", _base_pan(genre, part, insts), insts))

        if pd.has_double and part.double is not None:
            spread = part.double.spread
            with_doubles: list[Lane] = []
            for lane in base_lanes:
                orig_pan = max(0, min(255, lane.pan - spread // 2))
                dup_pan = max(0, min(255, lane.pan + spread // 2))
                with_doubles.append(dc.replace(lane, pan=orig_pan))
                with_doubles.append(dc.replace(lane, pan=dup_pan, is_double=True))
            base_lanes = with_doubles

        lanes.extend(base_lanes)

    n = len(lanes)
    if n < budget:
        lanes.append(Lane(0, None, "control", CENTER))
    elif n > budget:
        raise PlanError(f"{genre.id}: ladder produced {n} lanes for a budget of {budget} (internal error)")

    if _all_pans_default(genre):   # 明示パンが無ければ Amiga 風 L R R L（64/192。DESIGN.md §7.1 の規則2）。
        # double の開き方の意図はこの規則の下では保てないが、全パン未宣言ジャンルは現行どおり LRRL だけを使う
        lanes = [dc.replace(l, pan=AMIGA_LEFT if i % 4 in (0, 3) else AMIGA_RIGHT) for i, l in enumerate(lanes)]
    return tuple(dc.replace(l, index=i) for i, l in enumerate(lanes))


# ============================================================
# イベントの lane への割当（§9.5）
# ============================================================

@dataclass(frozen=True)
class Placement:
    step: int
    lane: int
    kind: str                       # "note" | "off"
    inst: str = ""
    pitch: Optional[float] = None
    vel: Optional[int] = None
    dur: Optional[int] = None
    arts: tuple = ()
    strum_ms: float = 0.0
    chord: tuple[int, ...] = ()     # chord_baked の lane だけ使う（焼いたサンプルを選ぶ鍵）


@dataclass(frozen=True)
class AutomationPlacement:
    step: int
    lanes: tuple[int, ...]
    kind: str
    value: int


def chord_shapes_of(part: "Part", score: "Score") -> frozenset[tuple[int, ...]]:
    """``part`` で実際に使われた和音の形の集合（samples.py が焼くサンプルを決めるのに使う）。"""
    return _chord_shapes(part, score)


def compute_layout(genre: "Genre", score: "Score", budget: int) -> LaneLayout:
    """§9.2〜§9.4: 予算でパートを選び、ladder で lane 数を収め、物理チャンネルの並び・パンを決める。"""
    active = [p.name for p in genre.parts if p.min_channels <= budget]
    demands = _build_demands(genre, score)
    for name in list(demands):
        if name not in active:
            del demands[name]   # 予算で外れたパートは ladder の対象にしない（§9.2）
    _apply_ladder(genre, demands, active, budget)
    lanes = _build_lanes(genre, demands, active, budget)
    return LaneLayout(budget=budget, lanes=lanes, active_parts=frozenset(active))


def _kit_lane_for(lanes: list[Lane], inst: str) -> Optional[Lane]:
    for lane in lanes:
        if inst in lane.insts:
            return lane
    return None


def _resolve_note_conflicts(placements: list[Placement]) -> list[Placement]:
    """同じ lane・同じ step に複数の note があれば、``NoteEvent.prio`` → ``Kit.priority``
    （lane.priority に展開済み）→ 宣言順（先勝ち）で1つに決める（§9.5）。"""
    by_pos: dict[tuple[int, int], list[tuple[int, int, Placement]]] = {}
    others: list[Placement] = []
    for i, p in enumerate(placements):
        if p.kind == "note":
            by_pos.setdefault((p.lane, p.step), []).append((0, i, p))
        else:
            others.append(p)
    out = list(others)
    for _pos, group in by_pos.items():
        if len(group) == 1:
            out.append(group[0][2])
            continue
        # group の並び順＝lane に割り当てた順（kit なら楽器の宣言順）を「先勝ち」の基準にする
        out.append(group[0][2])
    return out


def assign_events(genre: "Genre", layout: LaneLayout, score: "Score"
                   ) -> dict[str, tuple[list[Placement], list[AutomationPlacement]]]:
    """区間ごとに、イベントを lane へ割り当てる（§9.5）。戻り値は区間名 → (Placement の列, Automation の列)。"""
    out: dict[str, tuple[list[Placement], list[AutomationPlacement]]] = {}
    for sec_name, sec_score in score.sections.items():
        placements: list[Placement] = []
        automations: list[AutomationPlacement] = []
        for part_name, events in sec_score.parts.items():
            if part_name not in layout.active_parts or not events:
                continue
            part_lanes = layout.lanes_of(part_name)
            if not part_lanes:
                continue
            role = part_lanes[0].role
            if role == "kit":
                placements.extend(_assign_kit(part_lanes, events))
            elif role == "chord_voice":
                placements.extend(_assign_chord_voices(part_lanes, events))
            elif role == "chord_baked":
                placements.extend(_assign_single(part_lanes[0], events))
            else:   # "mono"（poly=1 なら実質 _assign_single と同じ）
                placements.extend(_assign_poly(part_lanes, events))
            for e in events:
                if isinstance(e, Automation):
                    lanes = tuple(l.index for l in part_lanes if e.inst is None or e.inst in l.insts)
                    if lanes:
                        automations.append(AutomationPlacement(e.step, lanes, e.kind, e.value))
        out[sec_name] = (_dedup_by_lane_step(placements), automations)
    return out


def _dedup_by_lane_step(placements: list[Placement]) -> list[Placement]:
    """同じ lane・同じ step に複数の note が来た場合（kit の衝突）を解決する。既に優先度の高い順で
    追加してあるので、各 (lane, step) の最初の note 以外は捨てる（off は常に残す）。"""
    seen: set[tuple[int, int]] = set()
    out: list[Placement] = []
    for p in sorted(placements, key=lambda p: (p.step, 0 if p.kind == "off" else 1)):
        key = (p.lane, p.step)
        if p.kind == "note":
            if key in seen:
                continue
            seen.add(key)
        out.append(p)
    return sorted(out, key=lambda p: p.step)


def _assign_single(lane: Lane, events: list[Event]) -> list[Placement]:
    """chord_baked の lane 用: 1 lane に全てのイベントが乗る（和音の形は ``chord`` に残す）。"""
    out = []
    for e in events:
        if isinstance(e, NoteEvent):
            out.append(Placement(e.step, lane.index, "note", e.inst, e.pitch, e.vel, e.dur, e.arts,
                                  e.strum_ms, e.chord))
        elif isinstance(e, NoteOff):
            out.append(Placement(e.step, lane.index, "off", e.inst))
    return out


def _assign_kit(lanes: list[Lane], events: list[Event]) -> list[Placement]:
    """同じ lane に複数の楽器が乗り得る（merged/single）。同じ step の衝突は、優先度の高い楽器の
    発音を先に積むことで ``_dedup_by_lane_step`` が自動的に正しい方を残すようにする。"""
    by_lane: dict[int, list[Placement]] = {}
    for e in events:
        if isinstance(e, NoteEvent):
            lane = _kit_lane_for(lanes, e.inst)
            if lane is None:
                continue
            by_lane.setdefault(lane.index, []).append(
                Placement(e.step, lane.index, "note", e.inst, e.pitch, e.vel, e.dur, e.arts, e.strum_ms))
        elif isinstance(e, NoteOff):
            lane = _kit_lane_for(lanes, e.inst)
            if lane is not None:
                by_lane.setdefault(lane.index, []).append(Placement(e.step, lane.index, "off", e.inst))
    out: list[Placement] = []
    for lane in lanes:
        group = by_lane.get(lane.index, [])
        # 同じ step に複数の note があれば楽器の優先度が高い方を先に（_dedup_by_lane_step が残す）
        group.sort(key=lambda p: (p.step, -(lane.priority.get(p.inst, 1) if p.kind == "note" else 0)))
        out.extend(group)
    return out


def _assign_chord_voices(lanes: list[Lane], events: list[Event]) -> list[Placement]:
    """§9.5: NoteEvent 1つを、``pitch + chord[i]`` として声部 i の lane に置く。音量は
    ``round(vel/√k)``。構成音が lane の数より少ない和音は、余った lane を同じ step で止める。
    ``strum_ms`` は声部 i を ``Delay`` で遅らせる（Realizer 側。ここでは情報を残すだけ）。"""
    import math

    k_lanes = len(lanes)
    out: list[Placement] = []
    for e in events:
        if isinstance(e, NoteEvent):
            tones = e.chord if e.chord else (0,)   # NoteEvent.chord は根音の 0 を含む（score.py）
            vel = None if e.vel is None else max(1, round(e.vel / math.sqrt(len(tones))))
            for i in range(k_lanes):
                lane = lanes[i]
                if i < len(tones):
                    pitch = e.pitch + tones[i] if e.pitch is not None else None
                    out.append(Placement(e.step, lane.index, "note", e.inst, pitch, vel, e.dur, e.arts,
                                          strum_ms=e.strum_ms * i))
                else:
                    out.append(Placement(e.step, lane.index, "off", e.inst))
        elif isinstance(e, NoteOff):
            for lane in lanes:
                out.append(Placement(e.step, lane.index, "off", e.inst))
    return out


def _assign_poly(lanes: list[Lane], events: list[Event]) -> list[Placement]:
    """``poly`` の lane への動的割当。空いている（鳴っている音が無い）lane のうち番号の小さいものを
    使う。無ければ最も古い音の lane を奪う（§9.5）。"""
    notes = sorted((e for e in events if isinstance(e, NoteEvent)), key=lambda e: e.step)
    offs = [e for e in events if isinstance(e, NoteOff)]
    # 各 lane の「現在鳴っている音の終了予定 step」（None = ワンショットで自然減衰／ループで継続中）
    busy_until: dict[int, Optional[int]] = {lane.index: None for lane in lanes}
    busy_since: dict[int, int] = {}
    out: list[Placement] = []
    for e in notes:
        free = [lane for lane in lanes if busy_until[lane.index] is not None and busy_until[lane.index] <= e.step]
        free += [lane for lane in lanes if busy_until[lane.index] is None and lane.index not in busy_since]
        if free:
            lane = min(free, key=lambda l: l.index)
        else:
            lane = min(lanes, key=lambda l: busy_since.get(l.index, -1))
        out.append(Placement(e.step, lane.index, "note", e.inst, e.pitch, e.vel, e.dur, e.arts, e.strum_ms))
        busy_since[lane.index] = e.step
        busy_until[lane.index] = e.step + e.dur if e.dur is not None else None
    for e in offs:
        # どの lane が鳴っているかは呼出し側（tracker.py）が楽器名で絞り込む。ここでは全 lane に試す
        for lane in lanes:
            out.append(Placement(e.step, lane.index, "off", e.inst))
    return out
