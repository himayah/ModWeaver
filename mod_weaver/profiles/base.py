"""GenreProfile 抽象基底（DESIGN.md §5.1）。"""
from __future__ import annotations

import random
from abc import ABC, abstractmethod
from types import MappingProxyType
from typing import Any, Callable, Mapping, Optional, Union

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
    description: str                   # 1行の説明（日本語。--list-genres・--help に出す）
    description_en: str                # 同じ説明の英語版（-e / --english のとき使う）
    category: str = "genre"            # 一覧での区分: "mood"（気分）| "genre"（ジャンル）| "style"（〜風）
    title: str                         # 出力ファイルのタイトル欄（ASCII ≤20。全形式共通）
    default_filename: str
    tempo_choices: tuple[int, ...]     # 離散値。値は4分音符の BPM（=tracker の Fxx。1拍=24 tick）
    tempo_range: tuple[int, int] = (32, 255)
    # ↑ --tempo で上書きできる BPM の範囲（両端含む）。BPM から row 数を計算しているジャンル等、極端な
    #   テンポで破綻するものだけ狭める（DESIGN.md §5.5。値は総当たりの実測で決める）
    rows_per_measure: int = 16         # 64 の約数
    rows_per_beat: int = 4             # 表示 BPM の1拍に当たる row 数（16分格子=4、8分格子=2）。
    # ↑ スウィングは Speed の和を 48 / rows_per_beat にする（1拍=24 tick）。テンポの実プレイヤー検査もこの値を使う
    channel_plan: ChannelPlan
    tempo_policy: str = "engine"       # "engine" | "profile"
    rng_mode: str = "streams"          # "single"（Nostalgic）| "streams"
    strict_buffers: bool = True        # False: 無条件上書き（Nostalgic）

    # --- 将来拡張の差込口（DESIGN.md §2.4 の opt-in 方針。既定値では何も変わらない） ---
    channel_pans: Optional[tuple[int, ...]] = None
    # ↑ MOD 以外の形式でのチャンネルごとのパン（0=左、128=中央、255=右）。None なら core/formats.py の
    #   channel_pans() が決める（全サンプル既定パンなら Amiga 風 LRRL、明示パンがあればサンプルから）
    gm_voices: Mapping[str, Any] = MappingProxyType({})
    # ↑ --format midi 用の GM 音色表（build_samples() のキー → core.midi.GmVoice）。全楽器の宣言が必須
    #   （推測はしない。tests/unit/test_midi.py が全ジャンルの網羅を検査する）
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
        の合計）から実際の最終 row を求めること。DESIGN.md §5.1 参照。
        """
