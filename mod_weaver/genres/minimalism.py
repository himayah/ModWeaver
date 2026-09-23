"""minimalism: ミニマル / フェーズ音楽（GENRE_DESIGN_V2.md §6）。

4チャンネルそれぞれが異なる固定周期（16/12/8/6 row）で決まった音型を反復する（ライヒの
"Piano Phase" 的な発想）。1 pattern = 1 "measure" = LCM(16,12,8,6) = 48 row（``ChordSlot(rows=48)``、
``variable_meter=True`` で `D00` break。EXT-2②）。CH_PIANO（最速周期）のみ、pattern が進むごとに
参照位置を1 row ずつ右シフトさせ（``structure.polymetric_row()``）、他の固定チャンネルと「ズレて→
揃って戻る」というフェイズ・ミュージックの聴取体験を作る。和声は動かさず、乱数はほぼ使わない
（決定論的な反復が本質）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from ..core import structure, synth, synth_presets
from ..core.model import (
    ChannelRole,
    ChordDef,
    ChordSlot,
    MeasureBuffer,
    MeasureCtx,
    PatternCtx,
    PatternPlan,
    RngStreams,
    SampleSpec,
    SongPlan,
)
from ..core.midi import GmVoice
from ..profiles.base import GenreProfile
from ..profiles.registry import register_profile

# ============================================================
# sample 番号 / ChannelPlan（GENRE_DESIGN_V2.md §6.2）
# ============================================================

PIANO, MARIMBA, VIBES, WOOD = 1, 2, 3, 4
SAMPLE_KEYS = ("piano_pulse", "marimba", "vibraphone", "woodblock")

CH_PIANO, CH_MARIMBA, CH_VIBES, CH_WOOD = 0, 1, 2, 3

CHANNEL_PLAN = (
    ChannelRole("piano", frozenset({PIANO})),
    ChannelRole("marimba", frozenset({MARIMBA})),
    ChannelRole("vibraphone", frozenset({VIBES})),
    ChannelRole("woodblock", frozenset({WOOD})),
)

# 周期（row）: LCM(16,12,8,6) = 48
CYCLE_PIANO, CYCLE_MARIMBA, CYCLE_VIBES, CYCLE_WOOD = 16, 12, 8, 6
LCM_ROWS = 48
N_PHASES = CYCLE_PIANO           # 16段階でCH_PIANOの周期をちょうど1周する

# 固定音型（row -> (logical note or None, vol)）。乱数は使わない（決定論的な反復）。
# CH_WOOD は row0 を意図的に避ける（tempo/D00 挿入のため row0/row47 に空きチャンネルを残す契約。§6.6）。
PIANO_PATTERN: dict[int, tuple[Optional[int], int]] = {
    0: (24, 44), 2: (28, 40), 4: (31, 42), 6: (28, 38),
    8: (24, 44), 10: (28, 40), 12: (31, 42), 14: (28, 38),
}
MARIMBA_PATTERN: dict[int, tuple[Optional[int], int]] = {0: (19, 46), 3: (24, 42), 5: (26, 44), 8: (21, 40)}
VIBES_PATTERN: dict[int, tuple[Optional[int], int]] = {0: (24, 40), 3: (28, 38), 6: (21, 42)}
WOOD_PATTERN: dict[int, tuple[Optional[int], int]] = {1: (None, 50)}

# (ch, cycle_rows, instrument_key, phase_shifted, pattern)
TRACKS = (
    (CH_PIANO, CYCLE_PIANO, "piano_pulse", True, PIANO_PATTERN),
    (CH_MARIMBA, CYCLE_MARIMBA, "marimba", False, MARIMBA_PATTERN),
    (CH_VIBES, CYCLE_VIBES, "vibraphone", False, VIBES_PATTERN),
    (CH_WOOD, CYCLE_WOOD, "woodblock", False, WOOD_PATTERN),
)

STATIC_CHORD = ChordDef(
    label="C pentatonic", bass=12, harmony=24,
    chord_tones=(24, 26, 28, 31, 33), scale_tones=(24, 26, 28, 31, 33), arp=None, explicit=True,
)


# ============================================================
# 音色合成（core/synth.py の Patch 方式。core/synth_presets.py 参照）
# ============================================================

def build_minimalism_samples() -> dict[str, SampleSpec]:
    """挿入順 = sample 番号（1..4）。"""
    return {
        "piano_pulse": synth.render(synth_presets.MIN_PIANO_PULSE),
        "marimba": synth.render(synth_presets.MIN_MARIMBA),
        "vibraphone": synth.render(synth_presets.MIN_VIBRAPHONE),
        "woodblock": synth.render(synth_presets.MIN_WOODBLOCK),
    }


# ============================================================
# プロファイル本体
# ============================================================

GM_VOICES = {                                  # --format midi の GM 音色（core/midi.py）
    "piano_pulse": GmVoice(program=0),
    "marimba": GmVoice(program=12),
    "vibraphone": GmVoice(program=11),
    "woodblock": GmVoice(drum_note=76),
}


@register_profile
class MinimalismProfile(GenreProfile):
    id = "minimalism"
    display_name = "Minimalism"
    description = "ミニマル／フェーズ音楽。16/12/8/6row周期の4パートが少しずつズレて→揃って戻る"
    title = "Phase Process"
    default_filename = "PhaseProcess.mod"
    tempo_choices = (108, 112, 116, 120)
    rows_per_measure = LCM_ROWS            # ChordSlot.rows で上書きするため既定値として使うのみ
    channel_plan = CHANNEL_PLAN
    gm_voices = GM_VOICES
    tempo_policy = "engine"
    rng_mode = "streams"
    strict_buffers = True
    variable_meter = True                  # EXT-2: 48 row（<64）で D00 break

    def build_samples(self) -> dict[str, SampleSpec]:
        return build_minimalism_samples()

    # ------------------------------------------------------------ 計画
    def plan(self, rng: RngStreams) -> SongPlan:
        bpm = rng.plan.choice(list(self.tempo_choices))
        slot = ChordSlot(STATIC_CHORD, measures=1, rows=LCM_ROWS)
        patterns = [PatternPlan(f"phase{i}", [slot], intensity=0.6) for i in range(N_PHASES)]
        order = list(range(N_PHASES))
        return SongPlan(
            bpm=bpm, patterns=patterns, order=order, key_pc=0,
            summary=[f"Phase process      : {N_PHASES} stages, cycles {CYCLE_PIANO}/{CYCLE_MARIMBA}/"
                     f"{CYCLE_VIBES}/{CYCLE_WOOD} row (LCM={LCM_ROWS})"],
        )

    def compose_measure(self, mctx: MeasureCtx, state: Any, rng: RngStreams, buf: MeasureBuffer) -> None:
        phase = int(mctx.pattern.kind.removeprefix("phase"))
        for ch, cycle_rows, key, shifted, pattern in TRACKS:
            shift = phase if shifted else 0
            inst = mctx.instruments[key]
            for row in range(mctx.measure_rows):
                local_row = structure.polymetric_row(row - shift, cycle_rows)
                hit = pattern.get(local_row)
                if hit is None:
                    continue
                note, vol = hit
                buf.put(row, ch, inst.cell(note, vol=vol))
