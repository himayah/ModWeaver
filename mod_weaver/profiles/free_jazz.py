"""free-jazz: フリージャズ / 現代無調音楽（GENRE_DESIGN_V2.md §8）。

和声は `harmony.voice()`／`CHORD_QUALITIES` を経由せず、隣接半音を密集させたトーンクラスターを
``ChordDef`` として直接手組みする（march/nostalgic/maqam と同じ「明示的ボイシング」パターン）。
``tempo_policy="profile"`` を宣言し、EXT-5①（``core/automation.py`` の ``TempoCurve``）で
4 pattern を通して連続的にうねる BPM（ルバート）を作る。密なコンポジションルールではなく
確率密度でテクスチャを作る（各楽器は intensity に応じた確率で発音するかどうかを row ごとに判定する）。
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any, Optional

from ..core import automation, synth, synth_presets
from ..core.model import (
    Cell,
    ChannelRole,
    ChordDef,
    ChordSlot,
    MeasureBuffer,
    MeasureCtx,
    Pattern,
    PatternCtx,
    PatternPlan,
    RngStreams,
    SampleSpec,
    SongPlan,
)
from ..core.pitch import fold_into_range
from .base import GenreProfile
from .registry import register_profile

# ============================================================
# 音域・和声（GENRE_DESIGN_V2.md §8.2）
# ============================================================

BASS_REG = (0, 11)                            # arco_bass（shift=-12 → t=12..23）
CLUSTER_REG = (12, 35)                        # piano_cluster／sax_screech（ともに shift=0）
CLUSTER_OFFSETS = (0, 1, 2, -1, -2, 6, 7)

INITIAL_BPM = 96                              # SongPlan.bpm（tempo_choices の唯一の値。実テンポ推移は
                                               # TEMPO_CURVES が決めるため「選択」の意味は薄い）


def _cluster_chord(root_pc: int, label: str, rng: random.Random) -> ChordDef:
    """root_pc を中心に隣接半音を2〜4個ランダムに選び、密集クラスターを作る（explicit=True 相当）。
    chord_tones は piano/sax 共有の CLUSTER_REG、bass は別途 BASS_REG に折り返す
    （楽器ごとに shift が異なり有効な音域が違うため、1つの音域では兼用できない）。
    """
    offsets = rng.sample(CLUSTER_OFFSETS, k=rng.randint(2, 4))
    tones = sorted({fold_into_range(root_pc + o + 12 * 2, *CLUSTER_REG) for o in offsets})
    bass_note = fold_into_range(root_pc, *BASS_REG)
    return ChordDef(
        label=label, bass=bass_note, harmony=bass_note,
        chord_tones=tuple(tones), scale_tones=tuple(tones), arp=None, explicit=True,
    )


def _movement_slots(rng: random.Random, kind: str, n_clusters: int = 4) -> list[ChordSlot]:
    return [ChordSlot(_cluster_chord(rng.randint(0, 11), f"{kind}{i}", rng), measures=1)
            for i in range(n_clusters)]


# ============================================================
# sample 番号 / ChannelPlan（GENRE_DESIGN_V2.md §8.3）
# ============================================================

PIANO_CL, ARCO_BASS, SAX_SCR, CYM_SWELL = 1, 2, 3, 4
SAMPLE_KEYS = ("piano_cluster", "arco_bass", "sax_screech", "cymbal_swell")

CH_PIANO, CH_BASS, CH_SAX, CH_PERC = 0, 1, 2, 3

CHANNEL_PLAN = (
    ChannelRole("piano", frozenset({PIANO_CL})),
    ChannelRole("bass", frozenset({ARCO_BASS})),
    ChannelRole("sax", frozenset({SAX_SCR})),
    ChannelRole("perc", frozenset({CYM_SWELL})),
)

# EXT-5①: pattern 境界をまたいで滑らかに繋ぐテンポカーブ（start_bpm は直前 pattern の end_bpm と一致させる）
TEMPO_CURVES: dict[str, tuple[tuple[int, int, int, int, str], ...]] = {
    "movement_a": ((96, 82, 0, 63, "ease_out"),),
    "movement_b": ((82, 126, 0, 63, "ease_in"),),
    "climax": ((126, 150, 0, 31, "ease_in"), (150, 126, 32, 63, "ease_out")),
    "movement_c": ((126, 70, 0, 63, "linear"),),
}

# 楽器ごとの発音確率（1 row あたり。intensity 倍率を掛ける）
DENSITY = {"bass": 0.18, "piano": 0.25, "perc": 0.08}
SAX_DENSITY_CLIMAX = 0.12


# ============================================================
# 音色合成（core/synth.py の Patch 方式。core/synth_presets.py 参照）
# ============================================================

def build_free_jazz_samples() -> dict[str, SampleSpec]:
    """挿入順 = sample 番号（1..4）。"""
    return {
        "piano_cluster": synth.render(synth_presets.FREE_PIANO_CLUSTER),
        "arco_bass": synth.render(synth_presets.FREE_ARCO_BASS),
        "sax_screech": synth.render(synth_presets.FREE_SAX_SCREECH),
        "cymbal_swell": synth.render(synth_presets.FREE_CYMBAL_SWELL),
    }


# ============================================================
# state
# ============================================================

@dataclass
class FreeJazzState:
    extra: dict[str, Any] = field(default_factory=dict)


# ============================================================
# プロファイル本体
# ============================================================

@register_profile
class FreeJazzProfile(GenreProfile):
    id = "free-jazz"
    display_name = "Free Jazz"
    description = "フリージャズ。トーンクラスター、確率密度のテクスチャ、ルバート（連続テンポ変化）"
    title = "Free Jazz"
    default_filename = "FreeJazz.mod"
    tempo_choices = (INITIAL_BPM,)
    rows_per_measure = 16
    channel_plan = CHANNEL_PLAN
    tempo_policy = "profile"          # apply_tempo をスキップ（TempoCurve が BPM を管理する）
    rng_mode = "streams"
    strict_buffers = True

    grammar = {
        "movement_a": "_texture", "movement_b": "_texture",
        "climax": "_texture", "movement_c": "_texture",
    }

    def build_samples(self) -> dict[str, SampleSpec]:
        return build_free_jazz_samples()

    # ------------------------------------------------------------ 計画
    def plan(self, rng: RngStreams) -> SongPlan:
        patterns = [
            PatternPlan("movement_a", _movement_slots(rng.plan, "a"), intensity=0.3),
            PatternPlan("movement_b", _movement_slots(rng.plan, "b"), intensity=0.6),
            PatternPlan("climax", _movement_slots(rng.plan, "c", n_clusters=4), intensity=0.95),
            PatternPlan("movement_c", _movement_slots(rng.plan, "d"), intensity=0.2),
        ]
        order = [0, 1, 2, 3]              # 通作形式。ループしない
        return SongPlan(
            bpm=INITIAL_BPM, patterns=patterns, order=order, key_pc=None,
            summary=["Rubato            : 96 -> 82 -> 126 -> 150 -> 126 -> 70 (EXT-5 TempoCurve)"],
        )

    def begin_pattern(self, pctx: PatternCtx, rng: RngStreams) -> FreeJazzState:
        return FreeJazzState()

    def compose_measure(self, mctx: MeasureCtx, state: FreeJazzState, rng: RngStreams, buf: MeasureBuffer) -> None:
        getattr(self, self.grammar[mctx.pattern.kind])(mctx, state, rng, buf)

    def finalize_pattern(self, pctx: PatternCtx, pattern: Pattern, state: FreeJazzState, rng: RngStreams) -> None:
        # sustain 楽器（piano_cluster/arco_bass はループではないが sax/perc 含め全て自然減衰）を
        # 念のため消音してから、EXT-5 のテンポカーブを描画する（row 単位の Fxx 挿入。§8.6）。
        for ch in (CH_PIANO, CH_BASS, CH_SAX, CH_PERC):
            pattern.put(pattern.rows - 1, ch, Cell(None, 0, vol=0))
        for start_bpm, end_bpm, start_row, end_row, curve_type in TEMPO_CURVES[pctx.kind]:
            curve = automation.TempoCurve(start_bpm, end_bpm, start_row, end_row, curve_type)
            automation.render_tempo_curve(pattern, curve)

    # ------------------------------------------------------------ 文法（確率密度のテクスチャ）
    def _texture(self, mctx: MeasureCtx, st: FreeJazzState, rng: RngStreams, buf: MeasureBuffer) -> None:
        ins, chord, intensity = mctx.instruments, mctx.chord, mctx.pattern.intensity
        for row in range(mctx.measure_rows):
            if rng.bass.random() < DENSITY["bass"] * intensity:
                # chord.chord_tones は CLUSTER_REG（piano/sax 用）の音域であり arco_bass（shift=-12）
                # には使えないため、常に chord.bass（BASS_REG に折り返し済み）を鳴らす。
                buf.put(row, CH_BASS, ins["arco_bass"].cell(chord.bass, vol=max(1, round(40 * intensity) + 10)))
            if rng.harmony.random() < DENSITY["piano"] * intensity:
                note = rng.harmony.choice(chord.chord_tones or (chord.harmony,))
                buf.put(row, CH_PIANO, ins["piano_cluster"].cell(note, vol=max(1, round(45 * intensity) + 8)))
            if mctx.pattern.kind == "climax" and rng.melody.random() < SAX_DENSITY_CLIMAX:
                note = rng.melody.choice(chord.chord_tones or (chord.harmony,))
                buf.put(row, CH_SAX, ins["sax_screech"].cell(note, vol=54))
            if rng.drums.random() < DENSITY["perc"] * intensity:
                buf.put(row, CH_PERC, ins["cymbal_swell"].cell(vol=max(1, round(50 * intensity))))
