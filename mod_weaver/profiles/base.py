"""GenreProfile 抽象基底（設計書 §7）。"""
from __future__ import annotations

import random
from abc import ABC, abstractmethod
from typing import Any, Callable, Union

from ..core.model import (
    ChannelPlan,
    MeasureBuffer,
    MeasureCtx,
    Pattern,
    PatternCtx,
    RngStreams,
    SampleSpec,
    Song,
    SongPlan,
)

Rng = Union[random.Random, RngStreams]


class GenreProfile(ABC):
    # --- 宣言的属性 ---
    id: str
    aliases: tuple[str, ...] = ()
    display_name: str
    description: str
    title: str                         # 出力ファイルのタイトル欄（ASCII ≤20。mod/xm 共通）
    default_filename: str
    tempo_choices: tuple[int, ...]     # 離散値
    rows_per_measure: int = 16         # 64 の約数
    channel_plan: ChannelPlan
    tempo_policy: str = "engine"       # "engine" | "profile"
    rng_mode: str = "streams"          # "single"（Nostalgic）| "streams"
    strict_buffers: bool = True        # False: 無条件上書き（Nostalgic）

    # --- 将来拡張の差込口（CORE_EXTENSION_DESIGN の Opt-in 方針。既定値では何も変わらない） ---
    target_format: str = "mod"         # writer.WRITERS / verify.VERIFIERS のキー
    post_processors: tuple[Callable[[Song, SongPlan], None], ...] = ()
    # ↑ 全 pattern 作成後・テンポ挿入前に順に適用する後処理（サイドチェイン等の装飾用）
    variable_meter: bool = False        # EXT-2: True で pattern 合計行数 < 64 rows を許容し D00 を自動挿入する
    # ↑ True のとき rows_per_measure は「ChordSlot.rows 省略時の既定値」に過ぎなくなり、64 の約数である
    #   必要はなくなる（validate_timebase をスキップ）。ChordSlot.rows で measure ごとに行数を上書きできる。

    # --- 生成フック（エンジンがこの順で呼ぶ） ---
    @abstractmethod
    def build_samples(self) -> dict[str, SampleSpec]:
        """挿入順=sample 番号(1..)、キー=Instrument 名。seed に依存しない。"""

    @abstractmethod
    def plan(self, rng: Rng) -> SongPlan:
        """tempo・調・構成・進行の選択。"""

    def begin_pattern(self, pctx: PatternCtx, rng: Rng) -> Any:
        """pattern 内で共有する状態（motif 等）を返す。"""
        return None

    @abstractmethod
    def compose_measure(self, mctx: MeasureCtx, state: Any, rng: Rng, buf: MeasureBuffer) -> None:
        ...

    def finalize_pattern(self, pctx: PatternCtx, pattern: Pattern, state: Any, rng: Rng) -> None:
        """フェード等の後処理。

        ``pattern.rows`` は常に物理パターン長（64）であり、``variable_meter=True`` の pattern が
        ``D00`` で途中終了する場合の「実際に再生される最終 row」（エンジンが挿入する `D00` の行）とは
        異なりうる。そのため `variable_meter=True` のプロファイルで「曲の末尾で持続音を消音する」
        処理をここで行いたい場合は、``pattern.rows - 1`` ではなく自分の ``PatternPlan``（``ChordSlot.rows``
        の合計）から実際の最終 row を求めること。CORE_EXTENSION_DESIGN §4.2 参照。
        """
