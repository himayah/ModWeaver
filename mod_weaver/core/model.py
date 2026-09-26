"""データモデル（DESIGN.md §3）。

- ``Cell``: 1 セル（note / sample / effect / param / vol）。frozen。
- ``MeasureBuffer`` / ``Pattern``: 行×チャンネルの作業領域（共通基底 ``CellGrid``）。
- ``SampleSpec`` / ``Song`` / ``Instrument``。
- 計画系（``ChordSpec`` … ``RngStreams``）: プロファイルとエンジンの間で受け渡す純粋データ。

行数・チャンネル数は定数 ``ROWS_PER_PATTERN`` / ``NUM_CHANNELS`` を既定値とするだけで、
``CellGrid`` は任意の値を受け付ける（可変小節は ``ChordSlot.rows``／``MeasureCtx.measure_rows``、
多チャンネルは ``ChannelPlan`` の要素数で使っている。DESIGN.md §3.2・§4.7）。
"""
from __future__ import annotations

import copy
import logging
import random
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Optional

from ..errors import (
    CellConflictError,
    ChannelConflictError,
    PitchRangeError,
    SampleConstraintError,
)
from .pitch import NOTE_MAX, NOTE_MIN, PERIODS

log = logging.getLogger("mod_weaver")

ROWS_PER_PATTERN = 64
NUM_CHANNELS = 4
MAX_SAMPLES = 31
MAX_SAMPLE_BYTES = 131070  # 65535 words


# ============================================================
# Cell
# ============================================================

@dataclass(frozen=True)
class Cell:
    note: Optional[int] = None     # tracker note index or None(休)
    sample: int = 0                # 0=指定なし, 1..31
    effect: int = 0                # 0..0xF
    param: int = 0                 # 0..0xFF
    vol: Optional[int] = None      # 0..64。effect/param と排他

    def __post_init__(self) -> None:
        if self.note is not None and not NOTE_MIN <= self.note <= NOTE_MAX:
            raise PitchRangeError(f"note index out of range: {self.note}")
        if not 0 <= self.sample <= MAX_SAMPLES:
            raise CellConflictError(f"sample out of range: {self.sample}")
        if not 0 <= self.effect <= 0xF:
            raise CellConflictError(f"effect out of range: {self.effect}")
        if not 0 <= self.param <= 0xFF:
            raise CellConflictError(f"param out of range: {self.param}")
        if self.vol is not None:
            if not 0 <= self.vol <= 64:
                raise CellConflictError(f"vol out of range: {self.vol}")
            if self.effect != 0 or self.param != 0:
                raise CellConflictError(
                    f"vol and effect cannot share a cell (vol={self.vol}, "
                    f"effect={self.effect:X}, param={self.param:02X})"
                )

    @property
    def has_effect(self) -> bool:
        """アルペジオ（0xy）も「効果あり」とみなす。"""
        return self.effect != 0 or self.param != 0

    @property
    def is_empty(self) -> bool:
        return (
            self.note is None
            and self.sample == 0
            and self.vol is None
            and not self.has_effect
        )

    def serialize(self) -> bytes:
        """ProTracker 4 byte セル。``vol`` は ``0xC vv`` に変換される。"""
        period = 0 if self.note is None else PERIODS[self.note]
        effect, param = (0xC, self.vol) if self.vol is not None else (self.effect, self.param)
        b0 = (((self.sample >> 4) & 0x0F) << 4) | ((period >> 8) & 0x0F)
        b1 = period & 0xFF
        b2 = ((self.sample & 0x0F) << 4) | (effect & 0x0F)
        return bytes([b0, b1, b2, param & 0xFF])


EMPTY_CELL = Cell()


# ============================================================
# ChannelPlan
# ============================================================

@dataclass(frozen=True)
class ChannelRole:
    name: str                              # "drums"/"bass"/"pad"/"lead"
    allowed: frozenset[int]                # 許可する sample 番号（0 は常に可）
    priority: Mapping[int, int] = field(default_factory=dict)  # sample番号→優先度（未記載は 1、sample=0 は 0）


ChannelPlan = tuple[ChannelRole, ...]


# ============================================================
# CellGrid / MeasureBuffer / Pattern
# ============================================================

class CellGrid:
    """行×チャンネルのセル領域。put / replace / get の規則を共有する（DESIGN.md §3.2）。"""

    def __init__(
        self,
        rows: int,
        plan: Optional[ChannelPlan] = None,
        strict: bool = False,
        channels: Optional[int] = None,
    ) -> None:
        if rows <= 0:
            raise ValueError(f"rows must be positive: {rows}")
        self.rows = rows
        self.plan = plan
        self.strict = strict
        self.channels = len(plan) if plan is not None else (channels or NUM_CHANNELS)
        self._cells: list[list[Cell]] = [
            [EMPTY_CELL] * self.channels for _ in range(rows)
        ]

    # --- 内部 ---
    def _check_pos(self, row: int, ch: int) -> None:
        if not 0 <= row < self.rows:
            raise ChannelConflictError(f"row out of range: {row} (rows={self.rows})")
        if not 0 <= ch < self.channels:
            raise ChannelConflictError(f"channel out of range: {ch}")

    def _check_allowed(self, row: int, ch: int, cell: Cell) -> None:
        if self.plan is None or cell.sample == 0:
            return
        role = self.plan[ch]
        if cell.sample not in role.allowed:
            raise ChannelConflictError(
                f"sample {cell.sample} not allowed on ch{ch + 1} ({role.name}) at row {row}"
            )

    def _priority(self, ch: int, cell: Cell) -> int:
        if cell.sample == 0 or self.plan is None:
            return 0 if cell.sample == 0 else 1
        return self.plan[ch].priority.get(cell.sample, 1)

    # --- 公開 ---
    def put(self, row: int, ch: int, cell: Cell) -> None:
        """セルを置く。

        strict=False: 無条件上書き（Nostalgic 互換）。
        strict=True : 優先度は ChannelPlan から自動導出（sample=0 は 0）。
            空 → 書く / 新>既存 → 置換 / 新<既存 → 書かない /
            同一セル → no-op / 同値で異なるセル → ChannelConflictError。
        """
        self._check_pos(row, ch)
        self._check_allowed(row, ch, cell)
        if not self.strict:
            self._cells[row][ch] = cell
            return
        existing = self._cells[row][ch]
        if cell.is_empty or cell == existing:
            return
        if existing.is_empty:
            self._cells[row][ch] = cell
            return
        new_p, old_p = self._priority(ch, cell), self._priority(ch, existing)
        if new_p > old_p:
            self._cells[row][ch] = cell
        elif new_p < old_p:
            log.debug("cell dropped by priority at row %d ch%d: %s", row, ch + 1, cell)
        else:
            raise ChannelConflictError(
                f"conflicting cells at row {row} ch{ch + 1}: {existing} vs {cell}"
            )

    def replace(self, row: int, ch: int, cell: Cell) -> None:
        """意図的な上書き（優先度・同値を問わず置換）。"""
        self._check_pos(row, ch)
        self._check_allowed(row, ch, cell)
        self._cells[row][ch] = cell

    def insert_command(self, row: int, effect: int, param: int) -> None:
        """row の空きチャンネルへ ``(effect, param)`` を書き込む（``vol`` は使わない）。

        探索順序（DESIGN.md §3.2）:
          ① is_empty なチャンネルのうち最小番号
          ② なければ、note を持つが vol も effect も持たないチャンネル
             （そのチャンネルの note/sample はそのまま残し、サンプル既定音量で鳴り続ける）
        いずれも無ければ ChannelConflictError。``engine.apply_tempo`` や EXT-1/EXT-5（スウィング・
        テンポカーブ）の row 単位コマンド挿入が共用する（`Song`/プロファイルに依存しないため
        `CellGrid` のメソッドとして持つ。DESIGN_HISTORY.md §7.2）。
        """
        for ch in range(self.channels):
            if self.get(row, ch).is_empty:
                self.replace(row, ch, Cell(None, 0, effect, param))
                return
        for ch in range(self.channels):
            c = self.get(row, ch)
            if c.note is not None and c.vol is None and not c.has_effect:
                self.replace(row, ch, Cell(c.note, c.sample, effect, param))
                return
        raise ChannelConflictError(f"no channel available for row command at row {row}")

    def try_insert_command(self, row: int, effect: int, param: int) -> bool:
        """``insert_command`` の非送出版。装飾的な row コマンド（EXT-1 スウィング／EXT-5 テンポ
        カーブ等、「空きが無ければその row だけ諦めてよい」処理）が共通して使う、失敗を bool で
        返すだけの薄いラッパ（探索ロジック自体は ``insert_command`` のものをそのまま使う）。"""
        try:
            self.insert_command(row, effect, param)
            return True
        except ChannelConflictError:
            return False

    def get(self, row: int, ch: int) -> Cell:
        self._check_pos(row, ch)
        return self._cells[row][ch]

    def mapped(self, fn: Callable[[Cell], Cell]) -> "CellGrid":
        """全セルに ``fn`` を適用した複製（配置を変えない変換用。音量の一律変更など）。"""
        new = copy.copy(self)
        new._cells = [[fn(c) for c in row] for row in self._cells]
        return new

    def serialize(self) -> bytes:
        return b"".join(c.serialize() for r in self._cells for c in r)


class MeasureBuffer(CellGrid):
    """rows_per_measure × チャンネルの作業領域。"""


class Pattern(CellGrid):
    """64 row パターン（既定）。``finalize_pattern`` 用に put / replace / get を持つ。"""

    def __init__(
        self,
        plan: Optional[ChannelPlan] = None,
        strict: bool = False,
        rows: int = ROWS_PER_PATTERN,
        channels: Optional[int] = None,
    ) -> None:
        super().__init__(rows, plan, strict, channels)

    def blit(self, buf: CellGrid, base_row: int) -> None:
        """``buf`` の非空セルを ``base_row`` 以降へ転記する（buf 側で検査済みのため直接コピー）。"""
        if base_row < 0 or base_row + buf.rows > self.rows:
            raise ChannelConflictError(
                f"blit out of range: base_row={base_row}, rows={buf.rows}, pattern rows={self.rows}"
            )
        if buf.channels != self.channels:
            raise ChannelConflictError("blit channel count mismatch")
        for r in range(buf.rows):
            for c in range(buf.channels):
                cell = buf.get(r, c)
                if not cell.is_empty:
                    self._cells[base_row + r][c] = cell


# ============================================================
# SampleSpec / Song / Instrument
# ============================================================

@dataclass
class SampleSpec:
    name: str                      # ASCII ≤22
    data: bytes                    # 偶数長 ≥2、符号なし表現の 8bit signed PCM
    volume: int                    # 0..64
    loop: Optional[tuple[int, int]] = None   # (start_words, length_words) length>1。None は (0,1)
    rate_note: int = 24            # 生成レートを決める tracker note（既定 C-3）
    shift: int = 0                 # n = t + shift（DESIGN.md §3.1）
    pitched: bool = True           # False: 常に rate_note で発音（打楽器）
    finetune: int = 0
    pan: int = 128                 # EXT-6: 0=左、128=中央、255=右。MOD の serialize() は参照しない
    sounding_hz: Optional[float] = None
    # ↑ tracker note ``rate_note``（finetune 0）で鳴らしたときに実際に聞こえる基本周波数（Hz）。
    #   synth.render() が記録する。音高を持たない音色は None。MIDI 出力が実音の高さを求めるのに使う
    #   （合成は dsp.sample_rate()＝実際の Paula 再生レートの半分を基準に波形を作るため、論理 note の
    #   pitch.hz(n) とは一致しない。DESIGN.md §3.1）

    @property
    def length_words(self) -> int:
        return len(self.data) // 2

    @property
    def loop_header(self) -> tuple[int, int]:
        """ヘッダに書く (loop_start, loop_length)（words）。"""
        return self.loop if self.loop is not None else (0, 1)

    def validate(self) -> None:
        """サンプル制約を検査する。違反は SampleConstraintError。"""
        n = self.name
        if len(n) > 22 or not n.isascii():
            raise SampleConstraintError(f"sample name must be ASCII and <=22 chars: {n!r}")
        if len(self.data) < 2 or len(self.data) % 2 != 0:
            raise SampleConstraintError(f"sample {n!r}: length must be even and >=2 (got {len(self.data)})")
        if len(self.data) > MAX_SAMPLE_BYTES:
            raise SampleConstraintError(f"sample {n!r}: length {len(self.data)} exceeds {MAX_SAMPLE_BYTES}")
        if not 0 <= self.volume <= 64:
            raise SampleConstraintError(f"sample {n!r}: volume out of range: {self.volume}")
        if not NOTE_MIN <= self.rate_note <= NOTE_MAX:
            raise SampleConstraintError(f"sample {n!r}: rate_note out of range: {self.rate_note}")
        if not -8 <= self.finetune <= 7:
            raise SampleConstraintError(f"sample {n!r}: finetune out of range: {self.finetune}")
        if not 0 <= self.pan <= 255:
            raise SampleConstraintError(f"sample {n!r}: pan out of range: {self.pan}")
        if self.loop is not None:
            start, length = self.loop
            if start < 0 or length <= 1 or start + length > self.length_words:
                raise SampleConstraintError(
                    f"sample {n!r}: loop {self.loop} out of range (length={self.length_words} words)"
                )


@dataclass
class Song:
    title: str                     # ASCII ≤20
    samples: list[SampleSpec]      # 位置=sample番号-1
    patterns: list[Pattern]
    order: list[int]               # 1..128 エントリ
    instrument_names: tuple[str, ...] = ()   # build_samples() のキー（sample 番号順）。MIDI の音色表引き用


@dataclass(frozen=True)
class Instrument:
    """プロファイルが Cell を作る唯一の入口（DESIGN.md §3.3）。"""

    slot: int                      # 1..31
    spec: SampleSpec

    def cell(
        self,
        n: Optional[int] = None,
        *,
        vol: Optional[int] = None,
        effect: int = 0,
        param: int = 0,
        keep_sample: bool = False,
    ) -> Cell:
        """logical note ``n`` を発音する Cell を作る。

        - pitched=False: ``n`` は無視され ``rate_note`` で発音（sample=slot）
        - pitched=True で ``n`` あり: ``t = n - shift``。``t`` が 0..35 外なら PitchRangeError。
          アルペジオ（effect=0, param≠0）は ``t + max(X, Y) ≤ 35`` も検査
        - pitched=True で ``n`` なし: 休符 / 効果・音量専用セル。原則 sample=0。
          ``keep_sample=True``（ポルタメント継続など）のとき sample=slot
        """
        spec = self.spec
        if not spec.pitched:
            return Cell(spec.rate_note, self.slot, effect, param, vol)
        if n is None:
            sample = self.slot if keep_sample else 0
            return Cell(None, sample, effect, param, vol)
        t = n - spec.shift
        if not NOTE_MIN <= t <= NOTE_MAX:
            raise PitchRangeError(
                f"{spec.name}: logical note {n} -> tracker note {t} out of range (shift={spec.shift})"
            )
        if effect == 0 and param != 0:
            top = t + max(param >> 4, param & 0xF)
            if top > NOTE_MAX:
                raise PitchRangeError(
                    f"{spec.name}: arpeggio {param:02X} on tracker note {t} exceeds {NOTE_MAX}"
                )
        return Cell(t, self.slot, effect, param, vol)

    def off(self) -> Cell:
        """持続（ループ）音色の消音セル ``Cell(None, 0, vol=0)``。"""
        return Cell(None, 0, vol=0)


# ============================================================
# 和声・構造データ（計画系）
# ============================================================

@dataclass(frozen=True)
class ChordSpec:                   # 調非依存の和音記述（度数ではなく半音オフセット）
    root: int                      # 主音からの半音 0..11
    quality: str                   # CHORD_QUALITIES のキー
    bass: Optional[int] = None     # スラッシュ／ペダル用（主音からの半音）。None=root
    label: str = ""


@dataclass(frozen=True)
class ChordDef:                    # 具体化済み（調・音域適用後）
    label: str
    bass: int                      # ベース logical note
    harmony: int                   # パッド/持続用の代表音
    chord_tones: tuple[int, ...]   # 強拍用（メロディ音域）
    scale_tones: tuple[int, ...]   # 経過音用
    arp: Optional[int] = None      # 0xy の param（新ジャンルのみ）
    explicit: bool = False         # True: 手書きボイシング（Nostalgic）


@dataclass(frozen=True)
class ChordSlot:
    chord: ChordDef
    measures: int = 1              # 何 measure この和音が続くか
    rows: Optional[int] = None     # この slot の1 measureあたりの row 数。None=profile.rows_per_measure
                                    # （EXT-2 可変小節。variable_meter=False のプロファイルは常に None）


@dataclass
class PatternPlan:
    kind: str                      # "intro"|"a"|"b"|"outro"|"trio"|"climax"|…（プロファイル定義）
    slots: list[ChordSlot]         # Σ(measures) × rows_per_measure == 64
    intensity: float = 0.5         # 0..1（音量・密度の目安）
    key_offset: int = 0            # 転調（半音、トリオ用）
    extra: dict = field(default_factory=dict)


@dataclass
class SongPlan:
    bpm: int
    patterns: list[PatternPlan]    # 作成順（旧実装の rng 消費順を規定）
    order: list[int]               # PatternPlan の index 列
    key_pc: Optional[int] = None
    summary: list[str] = field(default_factory=list)   # バナー表示用の行
    channel_plan: Optional[ChannelPlan] = None   # 曲ごとの物理チャンネル構成（GenreProfile.arrange が決める）。None ならジャンルの宣言
    channel_pans: Optional[tuple[int, ...]] = None   # channel_plan と組になるパン（None なら §7.1 の規則）


@dataclass(frozen=True)
class PatternCtx:
    kind: str                      # "intro"|"a"|"b"|"outro"|...
    index: int                     # PatternPlan 作成順のインデックス
    bpm: int
    key_pc: Optional[int]
    key_offset: int
    intensity: float
    is_first_in_order: bool        # 曲順 order[0] に配置されるパターンか
    extra: Mapping[str, Any] = field(default_factory=dict)   # PatternPlan.extra の写し


@dataclass(frozen=True)
class MeasureCtx:
    pattern: PatternCtx
    measure_idx: int               # pattern 内 0..
    n_measures: int
    chord: ChordDef
    chord_measure_offset: int      # 現和音内での位置
    is_last: bool                  # pattern 最終 measure
    instruments: Mapping[str, Instrument]
    measure_rows: int = 16         # 現在の measure の実際の row 数（= buf.rows と同値。EXT-2）


@dataclass(frozen=True)
class RngStreams:                  # 用途別乱数ストリーム（D9・T18）
    plan: random.Random
    drums: random.Random
    bass: random.Random
    harmony: random.Random
    melody: random.Random

    STREAM_NAMES = ("plan", "drums", "bass", "harmony", "melody")

    @classmethod
    def for_seed(cls, seed: int, profile_id: str) -> "RngStreams":
        """``random.Random(f"{seed}:{profile_id}:{name}")``（文字列シードは Python バージョン間で安定）。"""
        return cls(**{n: random.Random(f"{seed}:{profile_id}:{n}") for n in cls.STREAM_NAMES})
