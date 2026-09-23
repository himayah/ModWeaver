"""future-bass: フューチャーベース / グリッチ（GENRE_DESIGN_V2.md §7）。

1 measure = 16 row = 4/4（標準16分格子）。EXT-4（``core/mixer.py``）のサイドチェイン・ダッキングと
サンプル・スライサーを実証する最初のジャンル。Eb メジャーの I-V-vi-IV を4 measure=1 pattern で回す。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from ..core import mixer, synth, synth_presets
from ..core.harmony import Registers, voice
from ..core.model import (
    Cell,
    ChannelRole,
    ChordSlot,
    ChordSpec,
    MeasureBuffer,
    MeasureCtx,
    Pattern,
    PatternCtx,
    PatternPlan,
    RngStreams,
    SampleSpec,
    SongPlan,
)
from ..core.pitch import MODES, Scale
from .base import GenreProfile
from .registry import register_profile

# ============================================================
# 音域・調・進行（GENRE_DESIGN_V2.md §7.3）
# ============================================================

KEY_PC = 3                                    # Eb
BASS_REG = (0, 11)                            # sub（shift=-12 → t=12..23）
CHORD_REG = (12, 23)                          # supersaw の根音（chord.harmony）
UNUSED_MELODY_REG = (24, 35)                  # Registers の必須フィールド（future-bass では未使用）
REGISTERS = Registers(bass=BASS_REG, harmony=CHORD_REG, melody=UNUSED_MELODY_REG)

# (root, quality) — Eb（KEY_PC）基準の半音オフセット。I - V - vi - IV
PROGRESSION = (ChordSpec(0, "maj"), ChordSpec(7, "maj"), ChordSpec(9, "min"), ChordSpec(5, "maj"))


def voice_progression() -> list[ChordSlot]:
    scale = Scale(KEY_PC, MODES["ionian"])
    return [ChordSlot(voice(spec, KEY_PC, scale, REGISTERS), measures=1) for spec in PROGRESSION]


def progression_summary() -> str:
    chords = " - ".join(s.chord.label for s in voice_progression())
    return f"Drop progression   : I-V-vi-IV -> {chords}"


# ============================================================
# sample 番号 / ChannelPlan（GENRE_DESIGN_V2.md §7.2）
# ============================================================

KICK, SUB, SAW, VOX, CLAP = 1, 2, 3, 4, 5
SAMPLE_KEYS = ("kick", "sub", "saw", "vox", "clap")

CH_KICK, CH_BASS, CH_CHORD, CH_LEAD = 0, 1, 2, 3

CHANNEL_PLAN = (
    ChannelRole("kick", frozenset({KICK, CLAP}), {CLAP: 2, KICK: 1}),
    ChannelRole("bass", frozenset({SUB})),
    ChannelRole("chord", frozenset({SAW})),
    ChannelRole("lead", frozenset({VOX})),
)

FOUR_ON_FLOOR = (0, 4, 8, 12)
CLAP_BACKBEAT = (4, 12)
CLAP_OFFBEAT_8TH = (2, 6, 10, 14)          # buildup のハイハット代用
VOCAL_CHOP_ROWS = (0, 2, 4, 6, 8, 10, 12, 14)
N_SLICES = 6

# EXT-4 サイドチェイン設定（GENRE_DESIGN_V2.md §7.6）
# CH_KICK は kick/clap を優先度共有するチャンネルのため（§7.2）、backbeat（row 4,12）では
# clap が kick を置換して実際のセルには clap しか残らない。ドロップの「4つ打ちポンピング」感を
# 4拍とも保つため、kick と clap の両方をトリガとして登録する（実運用のサイドチェインも通常
# キック単体ではなく「拍の打点」全体をトリガに使う）。
SIDECHAIN_RULES = (
    mixer.SidechainRule(trigger_sample=KICK, target_channel=CH_BASS, duck_ratio=0.25, release_rows=3),
    mixer.SidechainRule(trigger_sample=KICK, target_channel=CH_CHORD, duck_ratio=0.35, release_rows=4),
    mixer.SidechainRule(trigger_sample=CLAP, target_channel=CH_BASS, duck_ratio=0.25, release_rows=3),
    mixer.SidechainRule(trigger_sample=CLAP, target_channel=CH_CHORD, duck_ratio=0.35, release_rows=4),
)


def _apply_sidechain(song, plan) -> None:
    """``post_processors`` エントリ。全 pattern にサイドチェイン・ダッキングを適用する（EXT-4）。"""
    mixer.apply_sidechain(song, SIDECHAIN_RULES)


# ============================================================
# 音色合成（core/synth.py の Patch 方式。core/synth_presets.py 参照）
# ============================================================

def build_future_bass_samples() -> dict[str, SampleSpec]:
    """挿入順 = sample 番号（1..5）。"""
    return {
        "kick": synth.render(synth_presets.FB_KICK),
        "sub": synth.render(synth_presets.FB_SUB),
        "saw": synth.render(synth_presets.FB_SUPERSAW),
        "vox": synth.render(synth_presets.FB_VOCAL_CHOP),
        "clap": synth.render(synth_presets.FB_CLAP),
    }


# ============================================================
# state
# ============================================================

@dataclass
class FutureBassState:
    extra: dict[str, Any] = field(default_factory=dict)


# ============================================================
# プロファイル本体
# ============================================================

@register_profile
class FutureBassProfile(GenreProfile):
    id = "future-bass"
    display_name = "Future Bass"
    description = "フューチャーベース。キック連動サイドチェイン、ヴォーカルチョップ、Eb I-V-vi-IV"
    title = "Future Bass"
    default_filename = "FutureBass.mod"
    tempo_choices = (148, 150, 152, 155, 160)
    rows_per_measure = 16
    channel_plan = CHANNEL_PLAN
    tempo_policy = "engine"
    rng_mode = "streams"
    strict_buffers = True

    post_processors = (_apply_sidechain,)

    grammar = {
        "intro_chop": "_intro_chop", "buildup": "_buildup",
        "drop": "_drop", "breakdown": "_breakdown", "outro": "_breakdown",
    }

    def build_samples(self) -> dict[str, SampleSpec]:
        return build_future_bass_samples()

    # ------------------------------------------------------------ 計画
    def plan(self, rng: RngStreams) -> SongPlan:
        bpm = rng.plan.choice(list(self.tempo_choices))
        slots = voice_progression()
        patterns = [
            PatternPlan("intro_chop", slots, intensity=0.3),
            PatternPlan("buildup", slots, intensity=0.5),
            PatternPlan("drop", slots, intensity=1.0),
            PatternPlan("breakdown", slots, intensity=0.4),
            PatternPlan("outro", slots, intensity=0.25),
        ]
        order = [0, 0, 1, 2, 2, 3, 2, 2, 4]
        return SongPlan(bpm=bpm, patterns=patterns, order=order, key_pc=KEY_PC, summary=[progression_summary()])

    def begin_pattern(self, pctx: PatternCtx, rng: RngStreams) -> FutureBassState:
        return FutureBassState()

    def compose_measure(self, mctx: MeasureCtx, state: FutureBassState, rng: RngStreams, buf: MeasureBuffer) -> None:
        getattr(self, self.grammar[mctx.pattern.kind])(mctx, state, rng, buf)

    def finalize_pattern(self, pctx: PatternCtx, pattern: Pattern, state: FutureBassState, rng: RngStreams) -> None:
        # sub/saw（ループ音色）は次 pattern へ鳴り続けないよう消音する
        pattern.put(pattern.rows - 1, CH_BASS, Cell(None, 0, vol=0))
        pattern.put(pattern.rows - 1, CH_CHORD, Cell(None, 0, vol=0))

    # ------------------------------------------------------------ 各 pattern の文法
    def _intro_chop(self, mctx: MeasureCtx, st: FutureBassState, rng: RngStreams, buf: MeasureBuffer) -> None:
        """VOX のみ。`sample_offset_param()` で長尺サンプルを N_SLICES 個のシラブルに分割して叩く。"""
        vox = mctx.instruments["vox"]
        length_words = vox.spec.length_words
        offsets = [mixer.sample_offset_param(round(length_words * 2 * i / N_SLICES), length_words)
                   for i in range(N_SLICES)]
        for row in VOCAL_CHOP_ROWS:
            if rng.melody.random() < 0.7:
                # vol と effect は同一セルに同居できない（Cell の排他制約）ため、音量は
                # サンプル既定音量（FB_VOCAL_CHOP.volume）に任せる。
                param = rng.melody.choice(offsets)
                buf.put(row, CH_LEAD, vox.cell(effect=9, param=param))

    def _buildup(self, mctx: MeasureCtx, st: FutureBassState, rng: RngStreams, buf: MeasureBuffer) -> None:
        """kick 4つ打ち＋clap をハイハット代わりに8分オフビートへ（密度を増やしていく）。"""
        ins = mctx.instruments
        for row in FOUR_ON_FLOOR:
            buf.put(row, CH_KICK, ins["kick"].cell(vol=56))
        for row in CLAP_OFFBEAT_8TH:
            buf.put(row, CH_KICK, ins["clap"].cell(vol=32))

    def _drop(self, mctx: MeasureCtx, st: FutureBassState, rng: RngStreams, buf: MeasureBuffer) -> None:
        ins, chord, intensity = mctx.instruments, mctx.chord, mctx.pattern.intensity
        for row in FOUR_ON_FLOOR:
            buf.put(row, CH_KICK, ins["kick"].cell(vol=58))
        for row in CLAP_BACKBEAT:
            buf.put(row, CH_KICK, ins["clap"].cell(vol=44))
        vol = round(56 * intensity)
        buf.put(0, CH_BASS, ins["sub"].cell(chord.bass, vol=max(1, vol)))
        buf.put(0, CH_CHORD, ins["saw"].cell(chord.harmony, vol=max(1, vol)))

    def _breakdown(self, mctx: MeasureCtx, st: FutureBassState, rng: RngStreams, buf: MeasureBuffer) -> None:
        """kick 抜き（ダッキングのトリガが無いため自然にダッキングも止まる）。コードのみ柔らかく。"""
        ins, chord, intensity = mctx.instruments, mctx.chord, mctx.pattern.intensity
        vol = max(1, round(48 * intensity))
        buf.put(0, CH_BASS, ins["sub"].cell(chord.bass, vol=vol))
        buf.put(0, CH_CHORD, ins["saw"].cell(chord.harmony, vol=vol))
