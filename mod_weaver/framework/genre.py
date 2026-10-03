"""``Genre`` 基底クラスと宣言の型（DESIGN.md §5.1・§5.1）。

ジャンルは**宣言**（楽器・和声・区間と構成・パート・編成）と、パートごとの**ジェネレータ**だけを書く。
チャンネル番号・pattern・row・エフェクト番号・セル・サンプル番号・形式ごとの分岐はここでは一切出てこない
（それらは Realizer、DESIGN.md §7.6・§7.7、の責任）。
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Mapping, Optional

from ..core.harmony import Registers
from ..core.model import ChordSpec, GmVoice
from ..core.synth import Patch
from ..errors import PlanError
from .plan import Meter, SongPlan, Swing, default_plan, validate_swing
from .score import SectionScore

if TYPE_CHECKING:
    from .context import Generator

ALL_PARTS = frozenset()
# ↑ Section.parts の既定値。空は「follow を持たない宣言済みパートを全部」という意味の予約値で、
# plan.default_plan() が SectionPlan を作るときに Genre.parts から展開する（Section 単体では
# ジャンルの parts 宣言を知らないため、ここでは具体的な名前の集合を持てない）。


# ============================================================
# 宣言の型（DESIGN.md §5.1）
# ============================================================

@dataclass(frozen=True)
class Instrument:
    patch: Patch                     # core/synth の Patch（synth_presets から preset() で取る）
    gm: GmVoice                      # MIDI の音色。必須
    volume: Optional[int] = None     # 既定音量（None は patch.volume）
    tune_cents: float = 0.0          # 音高の固定のずれ
    release_s: Optional[float] = None    # opt-in: 消音のときに掛けるリリースの秒数。None は即時に止める
    pan: Optional[int] = None        # 楽器ごとのパン。None はパートのパン
    pitched: Optional[bool] = None   # None は patch.pitched をそのまま使う（上書きしたい場合だけ指定）

    @property
    def is_pitched(self) -> bool:
        return self.patch.pitched if self.pitched is None else self.pitched


@dataclass(frozen=True)
class Harmony:
    keys: tuple[int, ...]            # 主音の候補（pc）
    mode: str                        # core/pitch.MODES のキー
    mode_by_quality: Mapping[str, str] = field(default_factory=dict)
    registers: Registers = field(
        default_factory=lambda: Registers(bass=(0, 11), harmony=(12, 23), melody=(19, 33)))
    progressions: tuple[tuple[str, tuple[ChordSpec, ...]], ...] = ()
    n_progressions: int = 2
    fixed: bool = False               # True なら選ばず宣言順に全部使う
    arp: bool = False                 # True なら ChordDef.arp（0xy 用の第3音・第5音のオフセット）を求める

    def __post_init__(self) -> None:
        if not self.progressions:
            raise PlanError("Harmony.progressions must not be empty")


@dataclass(frozen=True)
class Section:
    prog: int = 0                    # 使う進行の番号
    measures: int = 4                # 小節数
    meter: Meter = field(default_factory=Meter)
    measure_steps: Optional[tuple[int, ...]] = None   # 可変拍子: 小節ごとの step 数
    intensity: float = 0.7
    parts: frozenset[str] = ALL_PARTS   # 鳴らすパート名（follow を持つパートは書かない）
    key_offset: int = 0
    swing: Optional[Swing] = None
    groove: str = "main"              # ドラムの型の名前
    fill: bool = False
    crash: bool = False
    motifs: str = "verse"             # 旋律の動機の組の名前
    tags: frozenset[str] = frozenset()   # ジャンル固有の印
    kind: str = ""                    # 空なら区間名

    def __post_init__(self) -> None:
        if self.measure_steps is not None and self.measures != 4:
            raise PlanError("Section: measure_steps and a non-default measures cannot both be set")
        if not 0.0 <= self.intensity <= 1.0:
            raise PlanError(f"Section.intensity must be 0..1: {self.intensity}")


@dataclass(frozen=True)
class Double:
    detune_cents: float = 8.0
    spread: int = 64                 # 元と複製を pan ± spread/2 に置く
    vel_ratio: float = 0.7


@dataclass(frozen=True)
class Kit:
    groups: tuple[tuple[str, tuple[str, ...]], ...]   # 「まとめた」段階の lane: (lane名, 楽器名…)
    priority: Mapping[str, int] = field(default_factory=dict)   # 楽器名 → 優先度（未記載 1）
    single_priority: Optional[Mapping[str, int]] = None         # 1本の段階だけの優先度。None なら priority
    group_pan: Mapping[str, int] = field(default_factory=dict)  # グループ名 → パン（未記載は Part.pan。
    # 「分ける」段階は楽器の属するグループのパンを引く。「1本」の段階は Part.pan）

    @property
    def instruments(self) -> tuple[str, ...]:
        return tuple(name for _lane, names in self.groups for name in names)

    def group_of(self, inst: str) -> Optional[str]:
        for lane, names in self.groups:
            if inst in names:
                return lane
        return None


@dataclass(frozen=True)
class Part:
    name: str
    gen: "Generator"
    pan: int = 128
    min_channels: int = 0             # 予算がこれ未満の曲では外す
    kit: Optional[Kit] = None         # 打楽器のパート: lane のまとめ方
    poly: int = 1                     # 同時に鳴りうる音の数（lane 数）
    chord_spread: int = 32            # 和音を声部に開いたときのパンの広がり
    double: Optional[Double] = None   # opt-in: デチューンした複製で左右に広げる
    follow: Optional[str] = None      # 付き従うパート
    depends: tuple[str, ...] = ()     # 先に作っておくパート


@dataclass(frozen=True)
class Sidechain:                      # MixRule の唯一の種類
    triggers: tuple[str, ...]         # トリガの楽器名
    targets: tuple[str, ...]          # 下げるパート名
    ratio: float = 0.3
    release_steps: int = 2


MixRule = Sidechain


# ============================================================
# Genre
# ============================================================

class Genre:
    # --- メタ ---
    id: str
    aliases: tuple[str, ...] = ()
    category: str = "genre"           # "mood" | "genre" | "style"
    display_name: str
    description: str                  # 日本語1行
    description_en: str               # 英語1行
    title: str                        # ASCII ≤20
    tempo_choices: tuple[int, ...]
    tempo_range: tuple[int, int] = (32, 255)

    # --- 宣言 ---
    instruments: Mapping[str, Instrument] = {}
    harmony: Optional[Harmony] = None
    sections: Mapping[str, Section] = {}
    form: tuple[str, ...] = ()
    parts: tuple[Part, ...] = ()
    swing: Optional[Swing] = None
    mod_channels: Mapping[int, int] = {4: 1}
    channel_cap: Optional[int] = None
    mix: tuple[MixRule, ...] = ()

    def __init_subclass__(cls, **kw: Any) -> None:
        super().__init_subclass__(**kw)
        if not getattr(cls, "parts", None):
            return   # 宣言の無い中間クラス（将来の共通基底）は検査しない
        _validate_declaration(cls)

    # --- フック ---
    def plan(self, rng: random.Random) -> SongPlan:
        return default_plan(self, rng)

    def finalize_section(self, sec, score: SectionScore, rng: random.Random) -> None:
        """パートをまたぐ編集（区間の全パートが出来た後に呼ばれる）。既定は何もしない。"""


# ============================================================
# 宣言の検査（DESIGN.md §10.1 I9。クラス定義時）
# ============================================================

def _validate_declaration(cls: type) -> None:
    part_names = [p.name for p in cls.parts]
    if len(part_names) != len(set(part_names)):
        raise PlanError(f"{cls.id}: duplicate part name in parts: {part_names}")
    name_set = set(part_names)

    for inst_name, inst in cls.instruments.items():
        if not isinstance(inst, Instrument) or inst.gm is None:
            raise PlanError(f"{cls.id}: instrument {inst_name!r} needs a GmVoice (Instrument.gm)")

    if not set(cls.mod_channels) <= {4, 6, 8}:
        raise PlanError(f"{cls.id}: mod_channels keys must be a subset of {{4, 6, 8}}: {set(cls.mod_channels)}")
    max_budget = max(cls.mod_channels, default=0)

    for part in cls.parts:
        if part.follow is not None and part.follow not in name_set:
            raise PlanError(f"{cls.id}: part {part.name!r} follows unknown part {part.follow!r}")
        for dep in part.depends:
            if dep not in name_set:
                raise PlanError(f"{cls.id}: part {part.name!r} depends on unknown part {dep!r}")
        if not (part.min_channels == 0 or part.min_channels in cls.mod_channels or part.min_channels > max_budget):
            raise PlanError(
                f"{cls.id}: part {part.name!r}.min_channels={part.min_channels} must be 0, one of "
                f"{set(cls.mod_channels)}, or > {max_budget}")
        if part.kit is not None:
            _validate_kit(cls, part)
        if part.poly != 1 and part.chord_spread != 32:
            pass  # 組合せ自体は許す（poly と和音は別々の機構）。実際の和音は NoteEvent.chord で書くため
    _check_no_cycle(cls, part_names)

    for name, sec in cls.sections.items():
        validate_swing(sec.swing if sec.swing is not None else cls.swing, sec.meter)   # ジャンルの swing は区間の既定

    for rule in cls.mix:
        for trig in rule.triggers:
            if trig not in cls.instruments:
                raise PlanError(f"{cls.id}: Sidechain trigger {trig!r} is not a declared instrument")
        for tgt in rule.targets:
            if tgt not in name_set:
                raise PlanError(f"{cls.id}: Sidechain target {tgt!r} is not a declared part")


def _validate_kit(cls: type, part: Part) -> None:
    kit = part.kit
    seen: dict[str, str] = {}
    for lane, names in kit.groups:
        for n in names:
            if n not in cls.instruments:
                raise PlanError(f"{cls.id}: part {part.name!r} kit group {lane!r} references unknown "
                                 f"instrument {n!r}")
            if n in seen:
                raise PlanError(f"{cls.id}: part {part.name!r}: instrument {n!r} is in two kit groups "
                                 f"({seen[n]!r} and {lane!r})")
            seen[n] = lane
    for mapping, label in ((kit.priority, "priority"), (kit.single_priority or {}, "single_priority")):
        for n in mapping:
            if n not in seen:
                raise PlanError(f"{cls.id}: part {part.name!r} kit.{label} references instrument {n!r} "
                                 f"not in any group")
    group_names = {lane for lane, _names in kit.groups}
    for lane in kit.group_pan:
        if lane not in group_names:
            raise PlanError(f"{cls.id}: part {part.name!r} kit.group_pan references unknown group {lane!r}")


def _check_no_cycle(cls: type, part_names: list[str]) -> None:
    by_name = {p.name: p for p in cls.parts}

    def edges(name: str) -> list[str]:
        p = by_name[name]
        out = list(p.depends)
        if p.follow is not None:
            out.append(p.follow)
        return out

    WHITE, GRAY, BLACK = 0, 1, 2
    color = {n: WHITE for n in part_names}

    def visit(n: str, stack: list[str]) -> None:
        color[n] = GRAY
        for m in edges(n):
            if color[m] == GRAY:
                raise PlanError(f"{cls.id}: cyclic part dependency: {' -> '.join(stack + [m])}")
            if color[m] == WHITE:
                visit(m, stack + [m])
        color[n] = BLACK

    for n in part_names:
        if color[n] == WHITE:
            visit(n, [n])
