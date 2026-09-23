"""prog-rock: 変拍子プログレ / マスロック（GENRE_DESIGN_V2.md §2）。

主リフの拍子サイクルは 7/8 + 7/8 + 5/8（合計 19/8。``rows_per_measure`` 既定16の16分格子で
14+14+10=38 row）。1 pattern = リフサイクル1回（38 row）＋ ``D00`` 自動挿入（EXT-2。
``ChordSlot.rows`` オーバーライド＋``variable_meter=True``）。E aeolian のモーダルなリフに対し、
``chorus`` セクションだけ 4/4（16 row×4 measure=64、割り込み無し）へ戻り「変拍子↔直進」の対比を作る。
"""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import Any, Optional

from ..core import synth, synth_presets
from ..core.composer import MelodyGenerator, RhythmMotif, ScaleRules, articulate
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
# 音域・調・進行（GENRE_DESIGN_V2.md §2.3）
# ============================================================

KEY_PC = 4                                    # E
BASS_REG = (0, 11)                            # bass_dist（shift=-12 → t=12..23）
GTR_REG = (12, 23)                            # gtr_power の根音（chord.harmony）
LEAD_REG = (24, 35)                           # lead_gtr（chorus 専用）
REGISTERS = Registers(bass=BASS_REG, harmony=GTR_REG, melody=LEAD_REG)

I_CHORD = ChordSpec(0, "min", label="i")       # Em
BVII_CHORD = ChordSpec(10, "maj", label="bVII")  # D
BVI_CHORD = ChordSpec(8, "maj", label="bVI")     # C

LEAD_RULES = ScaleRules(
    step_choices=(-1, 1, -2, 2), leap_probability=0.30, leap_semitones=(3, 5, 7),
    leap_recovery=True, dissonance_weight=0.05,
)

RIFF_MOTIFS: dict[int, RhythmMotif] = {
    14: RhythmMotif((0, 2, 4, 6, 8, 10, 12)),   # 7/8（7 eighth）
    10: RhythmMotif((0, 2, 4, 6, 8)),           # 5/8（5 eighth）
}
LEAD_MOTIFS = (
    RhythmMotif((0, 4, 8, 12)),
    RhythmMotif((0, 3, 4, 7, 8, 11, 12, 15)),
    RhythmMotif((0, 4, 6, 8, 12, 14)),
)


def _scale() -> Scale:
    return Scale(KEY_PC, MODES["aeolian"])


def riff_slots() -> list[ChordSlot]:
    """7/8 + 7/8 + 5/8（14+14+10=38 row）。i - bVII - bVI。"""
    scale = _scale()
    return [
        ChordSlot(voice(spec, KEY_PC, scale, REGISTERS), measures=1, rows=rows)
        for spec, rows in ((I_CHORD, 14), (BVII_CHORD, 14), (BVI_CHORD, 10))
    ]


def breakdown_slots() -> list[ChordSlot]:
    """5/8 のみ ×6（60 row）。bVI と i を交互に。"""
    scale = _scale()
    seq = (BVI_CHORD, I_CHORD, BVI_CHORD, I_CHORD, BVI_CHORD, I_CHORD)
    return [ChordSlot(voice(spec, KEY_PC, scale, REGISTERS), measures=1, rows=10) for spec in seq]


def chorus_slots() -> list[ChordSlot]:
    """4/4 ×4（16×4=64 row。break 不要）。i - bVII - bVI - bVII。"""
    scale = _scale()
    seq = (I_CHORD, BVII_CHORD, BVI_CHORD, BVII_CHORD)
    return [ChordSlot(voice(spec, KEY_PC, scale, REGISTERS), measures=1, rows=16) for spec in seq]


def progression_summary() -> str:
    riff = " - ".join(s.chord.label for s in riff_slots())
    chorus = " - ".join(s.chord.label for s in chorus_slots())
    return f"riff(7/8+7/8+5/8): {riff}  |  chorus(4/4x4): {chorus}"


# ============================================================
# sample 番号 / ChannelPlan（GENRE_DESIGN_V2.md §2.2）
# ============================================================

KICK, SNARE, CRASH, BASS, GTR, LEAD = 1, 2, 3, 4, 5, 6
SAMPLE_KEYS = ("kick", "snare", "crash", "bass", "gtr", "lead")

CH_DRUM, CH_BASS, CH_GTR, CH_LEAD = 0, 1, 2, 3

CHANNEL_PLAN = (
    ChannelRole("drums", frozenset({KICK, SNARE, CRASH}), {CRASH: 3, SNARE: 2, KICK: 1}),
    ChannelRole("bass", frozenset({BASS})),
    ChannelRole("gtr", frozenset({GTR})),
    ChannelRole("lead", frozenset({LEAD})),
)


# ============================================================
# 音色合成（core/synth.py の Patch 方式。core/synth_presets.py 参照）
# ============================================================

def build_prog_rock_samples() -> dict[str, SampleSpec]:
    """挿入順 = sample 番号（1..6）。crash は march の crash を短縮して流用（新規合成不要）。"""
    crash = dataclasses.replace(synth_presets.MARCH_CRASH_CYMBAL, finish=synth_presets.OneShot(0.6))
    return {
        "kick": synth.render(synth_presets.PROG_KICK),
        "snare": synth.render(synth_presets.PROG_SNARE),
        "crash": synth.render(crash),
        "bass": synth.render(synth_presets.PROG_BASS_DIST),
        "gtr": synth.render(synth_presets.PROG_GTR_POWER),
        "lead": synth.render(synth_presets.PROG_LEAD_GTR),
    }


# ============================================================
# state
# ============================================================

@dataclass
class ProgState:
    lead_prev: Optional[int] = None
    extra: dict[str, Any] = field(default_factory=dict)


# ============================================================
# プロファイル本体
# ============================================================

@register_profile
class ProgRockProfile(GenreProfile):
    id = "prog-rock"
    display_name = "Prog Rock"
    description = "変拍子プログレ／マスロック。7/8+7/8+5/8 のリフ、4/4 のコーラスとの対比"
    title = "Prog Rock"
    default_filename = "ProgRock.mod"
    tempo_choices = (132, 136, 140, 144, 148)
    rows_per_measure = 16                 # ChordSlot.rows で measure ごとに上書きする（EXT-2）
    channel_plan = CHANNEL_PLAN
    tempo_policy = "engine"
    rng_mode = "streams"
    strict_buffers = True
    variable_meter = True                 # EXT-2: リフパターンは38/60 row（<64）で D00 break

    grammar = {
        "intro": "_riff_light", "outro": "_riff_light",
        "verse": "_riff_full", "breakdown": "_riff_full",
        "chorus": "_chorus",
    }

    def build_samples(self) -> dict[str, SampleSpec]:
        return build_prog_rock_samples()

    # ------------------------------------------------------------ 計画
    def plan(self, rng: RngStreams) -> SongPlan:
        bpm = rng.plan.choice(list(self.tempo_choices))
        patterns = [
            PatternPlan("intro", riff_slots(), intensity=0.5),
            PatternPlan("verse", riff_slots(), intensity=0.8),
            PatternPlan("chorus", chorus_slots(), intensity=0.9),
            PatternPlan("breakdown", breakdown_slots(), intensity=0.6),
            PatternPlan("outro", riff_slots(), intensity=0.4),
        ]
        order = [0, 1, 1, 2, 1, 3, 2, 4]
        return SongPlan(bpm=bpm, patterns=patterns, order=order, key_pc=KEY_PC, summary=[progression_summary()])

    def begin_pattern(self, pctx: PatternCtx, rng: RngStreams) -> ProgState:
        st = ProgState()
        if pctx.kind == "chorus":
            st.extra["lead_gen"] = MelodyGenerator(LEAD_RULES, LEAD_REG, _scale(), rng.melody, base_vol=52)
        return st

    def compose_measure(self, mctx: MeasureCtx, state: ProgState, rng: RngStreams, buf: MeasureBuffer) -> None:
        getattr(self, self.grammar[mctx.pattern.kind])(mctx, state, rng, buf)

    def finalize_pattern(self, pctx: PatternCtx, pattern: Pattern, state: ProgState, rng: RngStreams) -> None:
        # lead_gtr（ループ音色）は次 pattern へ鳴り続けないよう消音する
        pattern.put(pattern.rows - 1, CH_LEAD, Cell(None, 0, vol=0))

    # ------------------------------------------------------------ 共通の部品
    @staticmethod
    def _riff_motif(measure_rows: int) -> RhythmMotif:
        return RIFF_MOTIFS[measure_rows]

    @staticmethod
    def _gtr_bass(buf: MeasureBuffer, ins, chord, motif: RhythmMotif) -> None:
        for row in motif.rows:
            accent = row == 0
            buf.put(row, CH_GTR, ins["gtr"].cell(chord.harmony, vol=60 if accent else 46))
            buf.put(row, CH_BASS, ins["bass"].cell(chord.bass, vol=54 if accent else 42))

    # ------------------------------------------------------------ 各 pattern の文法
    def _riff_light(self, mctx: MeasureCtx, st: ProgState, rng: RngStreams, buf: MeasureBuffer) -> None:
        """ドラム tacet（intro/outro）。row 0 に2チャンネル分の空きを残す。"""
        motif = self._riff_motif(mctx.measure_rows)
        self._gtr_bass(buf, mctx.instruments, mctx.chord, motif)

    def _riff_full(self, mctx: MeasureCtx, st: ProgState, rng: RngStreams, buf: MeasureBuffer) -> None:
        ins, motif = mctx.instruments, self._riff_motif(mctx.measure_rows)
        self._gtr_bass(buf, ins, mctx.chord, motif)
        for row in motif.rows:
            buf.put(row, CH_DRUM, ins["kick"].cell(vol=56))
        mid = mctx.measure_rows // 2
        mid -= mid % 2
        buf.put(mid, CH_DRUM, ins["snare"].cell(vol=50))
        if mctx.measure_idx == 0:
            buf.put(0, CH_DRUM, ins["crash"].cell(vol=64))

    def _chorus(self, mctx: MeasureCtx, st: ProgState, rng: RngStreams, buf: MeasureBuffer) -> None:
        """4/4 の直進ロック・ビート＋リードギターのメロディ（LEAD_MOTIFS、標準16分格子）。"""
        ins, chord = mctx.instruments, mctx.chord
        for row in (0, 8):
            buf.put(row, CH_DRUM, ins["kick"].cell(vol=58))
        for row in (4, 12):
            buf.put(row, CH_DRUM, ins["snare"].cell(vol=52))
        if mctx.measure_idx == 0:
            buf.put(0, CH_DRUM, ins["crash"].cell(vol=64))
        for row in (0, 4, 8, 12):
            buf.put(row, CH_BASS, ins["bass"].cell(chord.bass, vol=50))
        gen: MelodyGenerator = st.extra["lead_gen"]
        motif = rng.melody.choice(LEAD_MOTIFS)
        events, st.lead_prev = gen.bar(
            motif, chord, st.lead_prev, rows=16, base_vol=52, cadence=mctx.is_last,
        )
        articulate(buf, CH_LEAD, events, ins["lead"], gate=0.85)
