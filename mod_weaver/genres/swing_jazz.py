"""swing-jazz: スウィング・ジャズ / ビバップ（GENRE_DESIGN_V2.md §1）。

1 measure = 8 row = 4/4（1 row = 8分音符）。EXT-1（``core/groove.py``）のスウィング（row 偶奇で
Speed を交互に変える）を実証する最初のジャンル。Bb のリズムチェンジ形式 AABA（32 measure = 4 pattern
×8 measure）で、Head（2コーラス目相当）→ Solo → Head-out（タグエンディング）と進む。

進行は実際の "Rhythm Changes" の簡略形（A section 7小節目の Cm7/F7 半々の turnaround は、
1 measure=1和音という本エンジンの ``ChordSlot`` の粒度に合わせて Cm7 のみに簡略化している）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from ..core import groove, synth, synth_presets
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
from ..core.pitch import MODES, Scale, fold_into_range
from ..core.midi import GmVoice
from ..profiles.base import GenreProfile
from ..profiles.registry import register_profile

# ============================================================
# 音域・調・進行（GENRE_DESIGN_V2.md §1.3）
# ============================================================

KEY_PC = 10                                   # Bb
BASS_REG = (0, 11)                            # walk_bass（shift=-12 → t=12..23）
HARM_REG = (12, 23)                           # piano_comp（アルペジオ最大+7でも t<=30）
MELODY_REG = (24, 35)                         # sax_lead
REGISTERS = Registers(bass=BASS_REG, harmony=HARM_REG, melody=MELODY_REG)
MODE_BY_QUALITY = {"dom7": "mixolydian", "m7": "dorian"}

HEAD_RULES = ScaleRules(
    step_choices=(-1, 1, -2, 2), leap_probability=0.30, leap_semitones=(3, 4, 5, 7),
    leap_recovery=True, dissonance_weight=0.05,
)
SOLO_RULES = ScaleRules(
    step_choices=(-1, 1, -2, 2), leap_probability=0.45, leap_semitones=(3, 4, 5, 7, 8),
    leap_recovery=True, dissonance_weight=0.12,
)
WALK_RULES = ScaleRules(
    step_choices=(-1, 1, -2, 2), leap_probability=0.35, leap_semitones=(3, 4, 5, 7),
    leap_recovery=True, dissonance_weight=0.0, strong_nearest_prob=0.6,
)

PROGRESSION_TITLES = {"a": "Rhythm Changes A", "b": "Rhythm Changes Bridge"}

# (root, quality, measures) — Bb（KEY_PC）基準の半音オフセット
PROGRESSIONS: dict[str, list[tuple[ChordSpec, int]]] = {
    "a": [
        (ChordSpec(0, "maj"), 1), (ChordSpec(9, "dom7"), 1), (ChordSpec(2, "m7"), 1), (ChordSpec(7, "dom7"), 1),
        (ChordSpec(0, "maj"), 1), (ChordSpec(9, "dom7"), 1), (ChordSpec(2, "m7"), 1), (ChordSpec(0, "maj"), 1),
    ],
    "b": [
        (ChordSpec(4, "dom7"), 1), (ChordSpec(4, "dom7"), 1), (ChordSpec(9, "dom7"), 1), (ChordSpec(9, "dom7"), 1),
        (ChordSpec(2, "dom7"), 1), (ChordSpec(2, "dom7"), 1), (ChordSpec(7, "dom7"), 1), (ChordSpec(7, "dom7"), 1),
    ],
}


def voice_progression(name: str) -> list[ChordSlot]:
    scale = Scale(KEY_PC, MODES["ionian"])
    return [
        ChordSlot(voice(spec, KEY_PC, scale, REGISTERS, arp=True, mode_by_quality=MODE_BY_QUALITY), measures=m)
        for spec, m in PROGRESSIONS[name]
    ]


def progression_summary(label: str, name: str) -> str:
    chords = " - ".join(c.chord.label for c in voice_progression(name))
    return f"{label:<18}: {PROGRESSION_TITLES[name]} -> {chords}"


# ============================================================
# sample 番号 / ChannelPlan（GENRE_DESIGN_V2.md §1.2）
# ============================================================

RIDE, BRUSH, BASS, PIANO, SAX = 1, 2, 3, 4, 5
SAMPLE_KEYS = ("ride", "brush", "bass", "piano", "sax")

CH_DRUM, CH_BASS, CH_HARM, CH_MEL = 0, 1, 2, 3

CHANNEL_PLAN = (
    ChannelRole("drums", frozenset({RIDE, BRUSH}), {BRUSH: 2, RIDE: 1}),
    ChannelRole("bass", frozenset({BASS})),
    ChannelRole("harmony", frozenset({PIANO})),
    ChannelRole("melody", frozenset({SAX})),
)

RIDE_ROWS = (0, 2, 3, 4, 6, 7)          # "ding-ding-a-ding"
RIDE_STRONG_ROWS = (0, 4)
BACKBEAT_ROWS = (2, 6)
# どちらも row 0/2/4/6（ride の強拍・walk bass の全拍）を避け、swing（EXT-1）が row 0 に必要とする
# 空きチャンネルを piano 側が確実に残す（GENRE_DESIGN_V2 §1.6 の row0 契約を全 measure に一般化）。
COMP_A = (1, 3)
COMP_B = (1, 5)

SWING_MOTIFS = (
    RhythmMotif((0, 2, 4, 6)),
    RhythmMotif((0, 1, 3, 5, 6)),
    RhythmMotif((0, 2, 3, 5, 6)),
    RhythmMotif((0, 1, 2, 4, 5, 7)),
)
WALK_MOTIF = RhythmMotif((0, 2, 4, 6))
HOLD_MOTIF = RhythmMotif((0,))

SAX_RETRIG_TICKS = 5        # 裏拍（short_speed=10 tick）の中ほどで1回だけ再発音する装飾
SWING_CONFIG = groove.SwingConfig(long_speed=14, short_speed=10)  # 14:10 = 1.4:1、合計24 tick＝1拍（GENRE_DESIGN_V2 §10 試聴調整対象）
# ↑ 以前は 7:5（合計12 tick/拍）で、tempo_choices の2倍（約 300〜340 BPM）で鳴っていた。FORMAT_TEMPO_DESIGN §1.3


def _apply_swing_to_all(song, plan) -> None:
    """``post_processors`` エントリ。全 pattern にスウィングを適用する（EXT-1）。"""
    for pattern in song.patterns:
        groove.apply_swing(pattern, SWING_CONFIG)


# ============================================================
# 音色合成（core/synth.py の Patch 方式。core/synth_presets.py 参照）
# ============================================================

def build_swing_jazz_samples() -> dict[str, SampleSpec]:
    """挿入順 = sample 番号（1..5）。"""
    return {
        "ride": synth.render(synth_presets.SWING_RIDE),
        "brush": synth.render(synth_presets.SWING_BRUSH_SNARE),
        "bass": synth.render(synth_presets.SWING_WALK_BASS),
        "piano": synth.render(synth_presets.SWING_PIANO_COMP),
        "sax": synth.render(synth_presets.SWING_SAX_LEAD),
    }


# ============================================================
# state
# ============================================================

@dataclass
class SwingState:
    melody_prev: Optional[int] = None
    bass_prev: Optional[int] = None
    extra: dict[str, Any] = field(default_factory=dict)


# ============================================================
# プロファイル本体
# ============================================================

GM_VOICES = {                                  # --format midi の GM 音色（core/midi.py）
    "ride": GmVoice(drum_note=51),
    "brush": GmVoice(drum_note=38),
    "bass": GmVoice(program=32),
    "piano": GmVoice(program=0),
    "sax": GmVoice(program=65),
}


@register_profile
class SwingJazzProfile(GenreProfile):
    id = "swing-jazz"
    display_name = "Swing Jazz"
    description = "スウィング・ジャズ。ライド＋ウォーキングベース＋ピアノコンピング、Bbリズムチェンジ AABA"
    description_en = "Swing jazz: ride cymbal, walking bass and piano comping over Bb rhythm changes (AABA)"
    title = "Swing Jazz"
    default_filename = "SwingJazz.mod"
    tempo_choices = (152, 156, 160, 164, 168)
    rows_per_measure = 8                  # 1 row = 8分音符（swing timebase。EXT-1）
    channel_plan = CHANNEL_PLAN
    gm_voices = GM_VOICES
    tempo_policy = "engine"
    rng_mode = "streams"
    strict_buffers = True

    post_processors = (_apply_swing_to_all,)

    grammar = {
        "intro": "_intro", "a": "_head", "b": "_head",
        "solo_a": "_solo", "solo_b": "_solo", "out": "_out",
    }

    def build_samples(self) -> dict[str, SampleSpec]:
        return build_swing_jazz_samples()

    # ------------------------------------------------------------ 計画
    def plan(self, rng: RngStreams) -> SongPlan:
        bpm = rng.plan.choice(list(self.tempo_choices))
        a_slots, b_slots = voice_progression("a"), voice_progression("b")
        patterns = [
            PatternPlan("intro", a_slots, intensity=0.4),
            PatternPlan("a", a_slots, intensity=0.70),
            PatternPlan("b", b_slots, intensity=0.65),
            PatternPlan("solo_a", a_slots, intensity=0.85),
            PatternPlan("solo_b", b_slots, intensity=0.80),
            PatternPlan("out", a_slots, intensity=1.0),
        ]
        order = [0, 1, 1, 2, 1, 3, 3, 4, 3, 1, 1, 2, 5]
        return SongPlan(
            bpm=bpm, patterns=patterns, order=order, key_pc=KEY_PC,
            summary=[progression_summary("A section", "a"), progression_summary("Bridge", "b")],
        )

    def begin_pattern(self, pctx: PatternCtx, rng: RngStreams) -> SwingState:
        st = SwingState()
        melody_rules = SOLO_RULES if pctx.kind in ("solo_a", "solo_b") else HEAD_RULES
        scale = Scale(KEY_PC, MODES["ionian"])
        st.extra["melody_gen"] = MelodyGenerator(
            melody_rules, MELODY_REG, scale, rng.melody, base_vol=48, beat_rows=2,
        )
        st.extra["bass_gen"] = MelodyGenerator(
            WALK_RULES, BASS_REG, scale, rng.bass, base_vol=52, beat_rows=2,
        )
        return st

    def compose_measure(self, mctx: MeasureCtx, state: SwingState, rng: RngStreams, buf: MeasureBuffer) -> None:
        getattr(self, self.grammar[mctx.pattern.kind])(mctx, state, rng, buf)

    def finalize_pattern(self, pctx: PatternCtx, pattern: Pattern, state: SwingState, rng: RngStreams) -> None:
        # sax（ループ音色）は次 pattern へ鳴り続けないよう消音する
        pattern.put(pattern.rows - 1, CH_MEL, Cell(None, 0, vol=0))

    # ------------------------------------------------------------ 共通の部品
    @staticmethod
    def _ride(buf: MeasureBuffer, ins) -> None:
        """強拍(0,4)は vol=58 の明示アクセント、弱拍は vol を指定せずサンプル既定音量で鳴らす
        （vol 無し＝``CellGrid.insert_command`` の2番目の探索対象になれる。swing の row 挿入余地を
        増やす。GENRE_DESIGN_V2 §1.6）。"""
        for r in RIDE_ROWS:
            if r in RIDE_STRONG_ROWS:
                buf.put(r, CH_DRUM, ins["ride"].cell(vol=58))
            else:
                buf.put(r, CH_DRUM, ins["ride"].cell())

    @staticmethod
    def _backbeat(buf: MeasureBuffer, ins) -> None:
        for r in BACKBEAT_ROWS:
            buf.put(r, CH_DRUM, ins["brush"].cell(vol=40))

    @staticmethod
    def _walk_bass(buf: MeasureBuffer, ins, chord, st: SwingState, rng: RngStreams) -> None:
        gen: MelodyGenerator = st.extra["bass_gen"]
        target = fold_into_range(chord.bass, *BASS_REG)
        events, st.bass_prev = gen.bar(
            WALK_MOTIF, chord, st.bass_prev, cadence=True, cadence_target=target,
            rows=8, base_vol=52,
        )
        articulate(buf, CH_BASS, events, ins["bass"], gate=0.9)

    @staticmethod
    def _comp(buf: MeasureBuffer, ins, chord, intensity: float, rng: RngStreams) -> None:
        """2種のシンコペ・コンピングパターン（どちらも row 0/2/4/6 を避ける）をランダムに選び刺す。
        intensity>=0.75 は arp 付き（既定音量）、それ未満は単音・控えめな vol
        （march の ``_pah`` と同じ流儀）。"""
        rows = COMP_A if rng.harmony.random() < 0.5 else COMP_B
        for r in rows:
            if intensity >= 0.75:
                buf.put(r, CH_HARM, ins["piano"].cell(chord.harmony, param=chord.arp or 0))
            else:
                buf.put(r, CH_HARM, ins["piano"].cell(chord.harmony, vol=34))

    def _melody_measure(self, buf: MeasureBuffer, ins, st: SwingState, rng: RngStreams, mctx: MeasureCtx,
                         *, gate: float = 0.85, cadence: bool = False) -> None:
        gen: MelodyGenerator = st.extra["melody_gen"]
        chord = mctx.chord
        if cadence:
            events, st.melody_prev = gen.bar(
                HOLD_MOTIF, chord, st.melody_prev, cadence=True,
                cadence_target=chord.chord_tones[0], rows=8, base_vol=54,
            )
        else:
            motif = rng.melody.choice(SWING_MOTIFS)
            events, st.melody_prev = gen.bar(motif, chord, st.melody_prev, rows=8, base_vol=50)
        articulate(buf, CH_MEL, events, ins["sax"], gate=gate)
        if events and rng.melody.random() < 0.25:
            last = events[-1]
            if last.row % 2 == 1:                     # swung 8th（裏拍）の onset にのみ装飾を足す
                buf.replace(last.row, CH_MEL,
                            ins["sax"].cell(last.note, effect=0x0E, param=groove.retrigger_param(SAX_RETRIG_TICKS)))

    # ------------------------------------------------------------ 各 pattern の文法
    def _intro(self, mctx: MeasureCtx, st: SwingState, rng: RngStreams, buf: MeasureBuffer) -> None:
        """リズム隊のみのヴァンプ。ドラム tacet（row 0 に3チャンネル分の空きを残す＝swing/tempo 挿入の余地）。"""
        ins, chord = mctx.instruments, mctx.chord
        buf.put(0, CH_BASS, ins["bass"].cell(chord.bass, vol=46))
        buf.put(4, CH_BASS, ins["bass"].cell(fold_into_range(chord.bass + 7, *BASS_REG), vol=42))
        if mctx.measure_idx % 2 == 0:
            buf.put(0, CH_HARM, ins["piano"].cell(chord.harmony, param=chord.arp or 0))

    def _head(self, mctx: MeasureCtx, st: SwingState, rng: RngStreams, buf: MeasureBuffer) -> None:
        ins, chord, intensity = mctx.instruments, mctx.chord, mctx.pattern.intensity
        self._ride(buf, ins)
        self._backbeat(buf, ins)
        self._walk_bass(buf, ins, chord, st, rng)
        self._comp(buf, ins, chord, intensity, rng)
        self._melody_measure(buf, ins, st, rng, mctx, gate=0.85, cadence=mctx.is_last)

    def _solo(self, mctx: MeasureCtx, st: SwingState, rng: RngStreams, buf: MeasureBuffer) -> None:
        ins, chord, intensity = mctx.instruments, mctx.chord, mctx.pattern.intensity
        self._ride(buf, ins)
        self._backbeat(buf, ins)
        self._walk_bass(buf, ins, chord, st, rng)
        self._comp(buf, ins, chord, intensity, rng)
        self._melody_measure(buf, ins, st, rng, mctx, gate=0.75, cadence=mctx.is_last)

    def _out(self, mctx: MeasureCtx, st: SwingState, rng: RngStreams, buf: MeasureBuffer) -> None:
        """head と同じだが最終 measure はタグ（全楽器で最終和音を保持）。"""
        ins, chord, intensity = mctx.instruments, mctx.chord, mctx.pattern.intensity
        if mctx.is_last:
            buf.put(0, CH_DRUM, ins["ride"].cell(vol=64))
            buf.put(0, CH_BASS, ins["bass"].cell(chord.bass, vol=60))
            buf.put(0, CH_HARM, ins["piano"].cell(chord.harmony, param=chord.arp or 0))
            self._melody_measure(buf, ins, st, rng, mctx, cadence=True)
            return
        self._ride(buf, ins)
        self._backbeat(buf, ins)
        self._walk_bass(buf, ins, chord, st, rng)
        self._comp(buf, ins, chord, intensity, rng)
        self._melody_measure(buf, ins, st, rng, mctx, gate=0.85)
