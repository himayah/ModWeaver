"""trap: トラップ / ドリル（GENRE_DESIGN_V2.md §4）。

1 measure = 32 row = 4/4（1 row = 32分音符。1拍=8row）。32 は64の約数のため EXT-2 なしで合法。
EXT-1（``core/groove.py`` のサブステップ・リトリガ）と EXT-5（``core/automation.py`` の808グライド）
を実証する。

**設計時からの簡略化**: 当初案の "i - VI - VII - i" 4和音進行は、``rows_per_measure=32`` では
1 pattern（64 row）に2 measure しか収まらず、4和音を1 pattern に収めることができない
（``variable_meter`` を使わずに解決する場合の制約。GENRE_DESIGN_V2.md 執筆時点の見落とし）。
実際の trap は2和音ループ（例: Cm-Ab）が非常に一般的であるため、"i - VI" の2和音ループ
（2 measure=64 row でちょうど収まる）に簡略化している。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from ..core import automation, groove, synth, synth_presets
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
from ..core.pitch import MODES, PERIODS, Scale, fold_into_range
from .base import GenreProfile
from .registry import register_profile

# ============================================================
# 音域・調・進行（GENRE_DESIGN_V2.md §4.3）
# ============================================================

KEY_PC = 0                                    # C
BASS_REG = (0, 11)                            # 808（shift=-12 → t=12..23）
LEAD_REG = (24, 35)                           # lead_pluck（hook のみ）
REGISTERS = Registers(bass=BASS_REG, harmony=LEAD_REG, melody=LEAD_REG)

I_CHORD = ChordSpec(0, "min", label="i")        # Cm
VI_CHORD = ChordSpec(8, "maj", label="VI")      # Ab

LEAD_RULES = ScaleRules(
    step_choices=(-1, 1, -2, 2), leap_probability=0.2, leap_semitones=(3, 4, 7),
    leap_recovery=True, dissonance_weight=0.1,
)


def voice_progression() -> list[ChordSlot]:
    scale = Scale(KEY_PC, MODES["aeolian"])
    return [ChordSlot(voice(spec, KEY_PC, scale, REGISTERS), measures=1) for spec in (I_CHORD, VI_CHORD)]


def progression_summary() -> str:
    chords = " - ".join(s.chord.label for s in voice_progression())
    return f"Loop               : i-VI -> {chords}"


# ============================================================
# sample 番号 / ChannelPlan（GENRE_DESIGN_V2.md §4.2）
# ============================================================

K808, SNARE, HAT_C, HAT_O, LEAD = 1, 2, 3, 4, 5
SAMPLE_KEYS = ("k808", "snare", "hat_c", "hat_o", "lead")

CH_808, CH_SNARE, CH_HAT, CH_LEAD = 0, 1, 2, 3

CHANNEL_PLAN = (
    ChannelRole("808", frozenset({K808})),
    ChannelRole("snare", frozenset({SNARE})),
    ChannelRole("hat", frozenset({HAT_C, HAT_O}), {HAT_O: 2, HAT_C: 1}),
    ChannelRole("lead", frozenset({LEAD})),
)

MOTIF_808_ROWS = (0, 8, 12, 20)                # 拍(8row間隔)を基本にしたシンコペーション
HAT_ROWS = tuple(range(0, 32, 4))              # 8分（8箇所）
SNARE_ROWS = (16, 28)                          # 2拍・4拍相当（4拍目はやや後ろにずらす trap の定型）
LEAD_MOTIFS = (
    RhythmMotif((0, 8, 16, 24)),
    RhythmMotif((0, 6, 8, 16, 22, 24)),
    RhythmMotif((0, 8, 14, 16, 24)),
)


# ============================================================
# 音色合成（core/synth.py の Patch 方式。core/synth_presets.py 参照）
# ============================================================

def build_trap_samples() -> dict[str, SampleSpec]:
    """挿入順 = sample 番号（1..5）。"""
    return {
        "k808": synth.render(synth_presets.TRAP_808),
        "snare": synth.render(synth_presets.TRAP_SNARE_CLAP),
        "hat_c": synth.render(synth_presets.TRAP_HAT_CLOSED),
        "hat_o": synth.render(synth_presets.TRAP_HAT_OPEN),
        "lead": synth.render(synth_presets.TRAP_LEAD_PLUCK),
    }


# ============================================================
# state
# ============================================================

@dataclass
class TrapState:
    lead_prev: Optional[int] = None
    extra: dict[str, Any] = field(default_factory=dict)


# ============================================================
# プロファイル本体
# ============================================================

@register_profile
class TrapProfile(GenreProfile):
    id = "trap"
    display_name = "Trap"
    description = "トラップ／ドリル。32分ハイハットロールと808グライド、Cm-Ab の2和音ループ"
    title = "Trap Beat"
    default_filename = "Trap.mod"
    tempo_choices = (140, 145, 150, 155)      # 32分格子なので実質ハーフタイム（70-77bpm相当）で感じる
    rows_per_measure = 32
    channel_plan = CHANNEL_PLAN
    tempo_policy = "engine"
    rng_mode = "streams"
    strict_buffers = True

    grammar = {
        "intro": "_intro", "verse": "_verse", "hook": "_hook",
        "half_time": "_half_time", "outro": "_outro",
    }

    def build_samples(self) -> dict[str, SampleSpec]:
        return build_trap_samples()

    # ------------------------------------------------------------ 計画
    def plan(self, rng: RngStreams) -> SongPlan:
        bpm = rng.plan.choice(list(self.tempo_choices))
        slots = voice_progression()
        patterns = [
            PatternPlan("intro", slots, intensity=0.4),
            PatternPlan("verse", slots, intensity=0.6),
            PatternPlan("hook", slots, intensity=1.0),
            PatternPlan("half_time", slots, intensity=0.5),
            PatternPlan("outro", slots, intensity=0.3),
        ]
        order = [0, 1, 1, 2, 2, 3, 2, 2, 4]
        return SongPlan(bpm=bpm, patterns=patterns, order=order, key_pc=KEY_PC, summary=[progression_summary()])

    def begin_pattern(self, pctx: PatternCtx, rng: RngStreams) -> TrapState:
        st = TrapState()
        if pctx.kind in ("hook",):
            scale = Scale(KEY_PC, MODES["aeolian"])
            st.extra["lead_gen"] = MelodyGenerator(LEAD_RULES, LEAD_REG, scale, rng.melody, base_vol=50)
        return st

    def compose_measure(self, mctx: MeasureCtx, state: TrapState, rng: RngStreams, buf: MeasureBuffer) -> None:
        getattr(self, self.grammar[mctx.pattern.kind])(mctx, state, rng, buf)

    def finalize_pattern(self, pctx: PatternCtx, pattern: Pattern, state: TrapState, rng: RngStreams) -> None:
        pattern.put(pattern.rows - 1, CH_LEAD, Cell(None, 0, vol=0))

    # ------------------------------------------------------------ 共通の部品
    @staticmethod
    def _808_bass(buf: MeasureBuffer, ins, chord) -> None:
        """拍をシンコペーションさせた808パターン。連続する打の間は 3xx グライドで滑らせる（EXT-5）。"""
        k808 = ins["k808"]
        shift = k808.spec.shift          # logical note -> tracker note（t = n - shift）は PERIODS の添字に必要
        root, fifth = chord.bass, fold_into_range(chord.bass + 7, *BASS_REG)
        notes = [root, fifth, root, fifth]
        prev: Optional[int] = None
        for row, note in zip(MOTIF_808_ROWS, notes):
            if prev is None:
                buf.put(row, CH_808, k808.cell(note, vol=60))
            else:
                p = automation.portamento_param(PERIODS[prev - shift], PERIODS[note - shift], rows=1)
                buf.put(row, CH_808, k808.cell(note, effect=3, param=p))
            prev = note

    @staticmethod
    def _hihat(buf: MeasureBuffer, ins, rng: RngStreams) -> None:
        """8分刻みのハイハット。measure に1箇所、ロール区間（E9x リトリガ）を確率的に差し込む（EXT-1）。"""
        roll_row = rng.drums.choice(HAT_ROWS)
        for row in HAT_ROWS:
            if row == roll_row and rng.drums.random() < 0.6:
                buf.put(row, CH_HAT, ins["hat_c"].cell(effect=0x0E, param=groove.retrigger_param(3)))
            else:
                buf.put(row, CH_HAT, ins["hat_c"].cell())
        buf.put(HAT_ROWS[-1], CH_HAT, ins["hat_o"].cell())   # フレーズ末はオープンハット（優先度で置換）

    @staticmethod
    def _snare(buf: MeasureBuffer, ins, intensity: float) -> None:
        vol = round(50 * intensity)
        for row in SNARE_ROWS:
            buf.put(row, CH_SNARE, ins["snare"].cell(vol=max(1, vol)))

    def _lead(self, buf: MeasureBuffer, ins, st: TrapState, rng: RngStreams, mctx: MeasureCtx) -> None:
        gen: MelodyGenerator = st.extra["lead_gen"]
        motif = rng.melody.choice(LEAD_MOTIFS)
        events, st.lead_prev = gen.bar(motif, mctx.chord, st.lead_prev, rows=32, base_vol=48)
        articulate(buf, CH_LEAD, events, ins["lead"], gate=0.8)

    # ------------------------------------------------------------ 各 pattern の文法
    def _intro(self, mctx: MeasureCtx, st: TrapState, rng: RngStreams, buf: MeasureBuffer) -> None:
        """ハイハットロールのビルドのみ。808/スネアなし。"""
        self._hihat(buf, mctx.instruments, rng)

    def _verse(self, mctx: MeasureCtx, st: TrapState, rng: RngStreams, buf: MeasureBuffer) -> None:
        """スパース。808 パターン中心、ハイハットのみ（スネアなし）。"""
        ins = mctx.instruments
        self._808_bass(buf, ins, mctx.chord)
        self._hihat(buf, ins, rng)

    def _hook(self, mctx: MeasureCtx, st: TrapState, rng: RngStreams, buf: MeasureBuffer) -> None:
        """フル編成。808＋ハイハット＋スネア＋リード。"""
        ins, intensity = mctx.instruments, mctx.pattern.intensity
        self._808_bass(buf, ins, mctx.chord)
        self._hihat(buf, ins, rng)
        self._snare(buf, ins, intensity)
        self._lead(buf, ins, st, rng, mctx)

    def _half_time(self, mctx: MeasureCtx, st: TrapState, rng: RngStreams, buf: MeasureBuffer) -> None:
        """ブリッジ。808＋ハイハットのみ、密度半分（スネア・リードなし）。"""
        ins = mctx.instruments
        self._808_bass(buf, ins, mctx.chord)
        self._hihat(buf, ins, rng)

    def _outro(self, mctx: MeasureCtx, st: TrapState, rng: RngStreams, buf: MeasureBuffer) -> None:
        """フェード。808 のみ残す。"""
        ins, chord = mctx.instruments, mctx.chord
        buf.put(0, CH_808, ins["k808"].cell(chord.bass, vol=round(60 * mctx.pattern.intensity)))
