"""march: 行進曲（設計書 §8.5）。

構成: intro（heroic）→ a（sousa）→ a2（heroic）→ trio → trio2 → coda（heroic）。
``order=[0, 1, 2, 1, 2, 3, 4, 3, 4, 5]``（10 pattern × 8 measure × 8 row ≈ 80 秒）。
トリオは主調 +5 半音（下属調）。文法の核は「Oom-Pah（tuba+bd / horn+sd）」「フレーズ末のスネアロール」
「crash による強拍アクセント」「ファンファーレ分散和音とスケール旋律フレーズ」。
"""
from __future__ import annotations

import dataclasses
import functools
from dataclasses import dataclass, field
from typing import Any, Optional

from ..core import synth, synth_presets
from ..core.composer import MelodyGenerator, NoteEvent, RhythmMotif, ScaleRules, articulate, ramp
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
# 音域・調・進行（§8.5、8.5.3）
# ============================================================

KEY_CHOICES = (0, 5, 10, 3)                  # C / F / Bb / Eb
TRIO_OFFSET = 5                              # トリオは主調 +5 半音（下属調）
BASS_REG = (0, 11)                           # tuba（shift −12 → t=12..23）
HARMONY_REG = (17, 28)                       # horn/section のアルペジオ基音（arp 最大 +7 でも t ≤ 35）
MELODY_MAIN = (24, 43)                       # 主旋律（intro/a/a2）
MELODY_TRIO = (19, 38)                       # トリオ（低め）
MELODY_TRIO2 = (31, 47)                      # トリオ2／コーダ（1 オクターブ上）
REGISTERS = Registers(bass=BASS_REG, harmony=HARMONY_REG, melody=MELODY_MAIN)

STRAIN_RULES = ScaleRules(
    step_choices=(-1, 1, -2, 2), leap_probability=0.30, leap_semitones=(4, 5, 7),
    leap_recovery=True, dissonance_weight=0.05,
)
TRIO_RULES = ScaleRules(
    step_choices=(-1, 1, -2, 2), leap_probability=0.15, leap_semitones=(4, 5, 7),
    leap_recovery=True, dissonance_weight=0.05, strong_nearest_prob=0.85,
)

PROGRESSION_TITLES = {"sousa": "Sousa Classic", "heroic": "Heroic Fanfare", "trio": "Trio Uplift"}

# (root, quality, bass, measures) — 主音基準
PROGRESSIONS: dict[str, list[tuple[ChordSpec, int]]] = {
    "sousa": [
        (ChordSpec(0, "maj"), 1), (ChordSpec(7, "dom7"), 1), (ChordSpec(0, "maj"), 1),
        (ChordSpec(5, "maj"), 1), (ChordSpec(0, "maj", bass=7), 1), (ChordSpec(7, "dom7"), 1),
        (ChordSpec(0, "maj"), 2),
    ],
    "heroic": [
        (ChordSpec(0, "maj"), 1), (ChordSpec(5, "maj"), 1), (ChordSpec(7, "maj"), 1),
        (ChordSpec(0, "maj"), 1), (ChordSpec(9, "min"), 1), (ChordSpec(2, "min"), 1),
        (ChordSpec(7, "dom7"), 1), (ChordSpec(0, "maj"), 1),
    ],
    "trio": [
        (ChordSpec(0, "maj"), 1), (ChordSpec(0, "maj"), 1), (ChordSpec(7, "dom7"), 1),
        (ChordSpec(0, "maj"), 1), (ChordSpec(5, "maj"), 1), (ChordSpec(0, "maj"), 1),
        (ChordSpec(7, "dom7"), 1), (ChordSpec(0, "maj"), 1),
    ],
}


def voice_march_progression(name: str, tonic_pc: int) -> list[ChordSlot]:
    scale = Scale(tonic_pc, MODES["ionian"])
    return [
        ChordSlot(voice(spec, tonic_pc, scale, REGISTERS, arp=True), measures=measures)
        for spec, measures in PROGRESSIONS[name]
    ]


def progression_summary(label: str, name: str, tonic_pc: int) -> str:
    chords = " - ".join(c.chord.label for c in voice_march_progression(name, tonic_pc))
    return f"{label:<16}: {PROGRESSION_TITLES[name]} -> {chords}"


# ============================================================
# sample 番号 / ChannelPlan（§8.5.1〜8.5.2）
# ============================================================

BD, SD, CRASH, TUBA, HORN, SECTION, PICC = 1, 2, 3, 4, 5, 6, 7
SAMPLE_KEYS = ("bd", "sd", "crash", "tuba", "horn", "section", "picc")

CH_DRUM, CH_BASS, CH_HARM, CH_MEL = 0, 1, 2, 3

CHANNEL_PLAN = (
    ChannelRole("drums", frozenset({BD, SD, CRASH}), {CRASH: 3, SD: 2, BD: 1}),
    ChannelRole("bass", frozenset({TUBA})),
    ChannelRole("harmony", frozenset({HORN, SECTION}), {HORN: 1, SECTION: 2}),
    ChannelRole("melody", frozenset({PICC})),
)

VIBRATO_PARAM = 0x46          # picc の 4xy（長音のビブラート）


# ============================================================
# 音色合成（§8.5.1）。core/synth.py の Patch 方式へ移行済み（core/synth_presets.py 参照）。
# ============================================================

def synth_bd() -> SampleSpec:
    """MarchBassDrum: f(t)=85+35e^(−25t) の位相積分サイン、減衰 e^(−14t)、2ms クリック、tanh(1.3x)、0.25s。"""
    return synth.render(synth_presets.MARCH_BASS_DRUM)


def synth_sd() -> SampleSpec:
    """MarchSnare: ヘッド 220Hz e^(−30t) ＋スナッピー（HP ノイズ）e^(−18t)、tanh(1.25x)、0.22s。"""
    return synth.render(synth_presets.MARCH_SNARE)


def synth_crash() -> SampleSpec:
    """CrashCymbal: 非整合部分音 (2100,3300,4700,6100,7300Hz) ＋ HP ノイズ、e^(−6t)、1.0s。rate_note=B-3。"""
    return synth.render(synth_presets.MARCH_CRASH_CYMBAL)


def synth_tuba() -> SampleSpec:
    """TubaBass: 三角波＋LP 矩形波（additive、h≤6）、アタック 8ms、e^(−7t) 減衰のスタッカート、0.35s。shift=−12。"""
    return synth.render(synth_presets.MARCH_TUBA_BASS)


def synth_horn() -> SampleSpec:
    """BrassHorn: ノコギリ近似（h=1..8、重み 1/h）＋LP、アタック 8ms、e^(−9t)、0.20s。"""
    return synth.render(synth_presets.MARCH_BRASS_HORN)


def synth_section() -> SampleSpec:
    """BrassSection: K=6, L=190, attack 100。偶数倍音豊富（h=1..6、重み 1,.7,.5,.35,.2,.12）。"""
    return synth.render(synth_presets.MARCH_BRASS_SECTION)


def synth_picc() -> SampleSpec:
    """PiccoloLead: K=12, L=190, attack 60。h=1..7、重み 1/h^0.9。shift=+12。"""
    return synth.render(synth_presets.MARCH_PICCOLO_LEAD)


@functools.lru_cache(maxsize=1)
def _synth_all() -> tuple[tuple[str, SampleSpec], ...]:
    return (
        ("bd", synth_bd()), ("sd", synth_sd()), ("crash", synth_crash()), ("tuba", synth_tuba()),
        ("horn", synth_horn()), ("section", synth_section()), ("picc", synth_picc()),
    )


def build_march_samples() -> dict[str, SampleSpec]:
    """挿入順 = sample 番号（1..7）。合成は seed 非依存のため 1 回だけ行い、呼び出しごとに複製を返す。"""
    return {key: dataclasses.replace(spec) for key, spec in _synth_all()}


# ============================================================
# 文法の語彙（§8.5.5）
# ============================================================

# RhythmMotif: (0,6)=付点4分+8分 / (0,3,4,7)=付点8分+16分x2 / (0,2,4,6)=8分x4 / (0,4)=4分x2
MARCH_MOTIFS = (RhythmMotif((0, 6)), RhythmMotif((0, 3, 4, 7)), RhythmMotif((0, 2, 4, 6)), RhythmMotif((0, 4)))
HOLD_MOTIF = RhythmMotif((0,))                              # 2 拍（1 measure 全体）の保持

# 8 measure = [a, a', b, c, a, a', b, cad]（"a2" は "a'" を表す）
PHRASE_SLOTS = ("a", "a2", "b", "c", "a", "a2", "b", "cad")


@dataclass
class MarchState:
    melody_prev: Optional[int] = None
    extra: dict[str, Any] = field(default_factory=dict)


# ============================================================
# プロファイル本体
# ============================================================

GM_VOICES = {                                  # --format midi の GM 音色（core/midi.py）
    "bd": GmVoice(drum_note=36),
    "sd": GmVoice(drum_note=38),
    "crash": GmVoice(drum_note=49),
    "tuba": GmVoice(program=58),
    "horn": GmVoice(program=60),
    "section": GmVoice(program=61),
    "picc": GmVoice(program=72),
}


@register_profile
class MarchProfile(GenreProfile):
    id = "march"
    display_name = "Military March"
    description = "行進曲。Oom-Pah とスネアロール、ファンファーレ、トリオへの転調"
    title = "Military March"
    default_filename = "MilitaryMarch.mod"
    tempo_choices = (118, 119, 120, 121, 122)
    rows_per_measure = 8
    channel_plan = CHANNEL_PLAN
    gm_voices = GM_VOICES
    tempo_policy = "engine"
    rng_mode = "streams"
    strict_buffers = True

    grammar = {
        "intro": "_intro", "a": "_strain", "a2": "_strain",
        "trio": "_trio", "trio2": "_trio2", "coda": "_coda",
    }

    def build_samples(self) -> dict[str, SampleSpec]:
        return build_march_samples()

    # ------------------------------------------------------------ 計画
    def plan(self, rng: RngStreams) -> SongPlan:
        key_pc = rng.plan.choice(KEY_CHOICES)
        bpm = rng.plan.choice(list(self.tempo_choices))
        trio_pc = (key_pc + TRIO_OFFSET) % 12
        patterns = [
            PatternPlan("intro", voice_march_progression("heroic", key_pc), intensity=0.8),
            PatternPlan("a", voice_march_progression("sousa", key_pc), intensity=0.7),
            PatternPlan("a2", voice_march_progression("heroic", key_pc), intensity=0.75),
            PatternPlan("trio", voice_march_progression("trio", trio_pc), intensity=0.5, key_offset=TRIO_OFFSET),
            PatternPlan("trio2", voice_march_progression("trio", trio_pc), intensity=0.85, key_offset=TRIO_OFFSET),
            PatternPlan("coda", voice_march_progression("heroic", key_pc), intensity=1.0),
        ]
        return SongPlan(
            bpm=bpm, patterns=patterns, order=[0, 1, 2, 1, 2, 3, 4, 3, 4, 5], key_pc=key_pc,
            summary=[
                progression_summary("Strain (Sousa)", "sousa", key_pc),
                progression_summary("Strain (Heroic)", "heroic", key_pc),
                progression_summary("Trio", "trio", trio_pc),
            ],
        )

    def begin_pattern(self, pctx: PatternCtx, rng: RngStreams) -> MarchState:
        st = MarchState()
        if pctx.kind == "intro":
            return st
        if pctx.kind == "trio":
            reg, rules = MELODY_TRIO, TRIO_RULES
        elif pctx.kind in ("trio2", "coda"):
            reg, rules = MELODY_TRIO2, STRAIN_RULES
        else:
            reg, rules = MELODY_MAIN, STRAIN_RULES
        tonic = ((pctx.key_pc or 0) + pctx.key_offset) % 12
        st.extra["gen"] = MelodyGenerator(rules, reg, Scale(tonic, MODES["ionian"]), rng.melody, base_vol=50)
        return st

    def compose_measure(self, mctx: MeasureCtx, state: MarchState, rng: RngStreams, buf: MeasureBuffer) -> None:
        getattr(self, self.grammar[mctx.pattern.kind])(mctx, state, rng, buf)

    def finalize_pattern(self, pctx: PatternCtx, pattern: Pattern, state: MarchState, rng: RngStreams) -> None:
        # picc（旋律）／section（保持和音）は共にループ音色なので、次の pattern へ鳴り続けないよう消音する
        pattern.put(pattern.rows - 1, CH_MEL, Cell(None, 0, vol=0))
        pattern.put(pattern.rows - 1, CH_HARM, Cell(None, 0, vol=0))

    # ------------------------------------------------------------ 共通の部品（Oom-Pah・crash・roll）
    @staticmethod
    def _oom(buf: MeasureBuffer, ins, chord, offset: int, *, bd_vol: int = 60, tuba_vol: int = 60) -> None:
        """row 0: tuba が根音（同一和音が複数 measure 続く場合は根音→5度を交互）、bd を同時。"""
        note = chord.bass if offset % 2 == 0 else fold_into_range(chord.bass + 7, *BASS_REG)
        buf.put(0, CH_BASS, ins["tuba"].cell(note, vol=tuba_vol))
        buf.put(0, CH_DRUM, ins["bd"].cell(vol=bd_vol))

    @staticmethod
    def _pah(buf: MeasureBuffer, ins, chord, intensity: float, *, sd_vol: int = 50, horn_vol: int = 34) -> None:
        """row 4: horn が harmony 音＋arp（intensity<0.7 では arp なし・単音 vol）、sd を同時。"""
        if intensity >= 0.7:
            buf.put(4, CH_HARM, ins["horn"].cell(chord.harmony, param=chord.arp or 0))
        else:
            buf.put(4, CH_HARM, ins["horn"].cell(chord.harmony, vol=horn_vol))
        buf.put(4, CH_DRUM, ins["sd"].cell(vol=sd_vol))

    @staticmethod
    def _crash(buf: MeasureBuffer, ins) -> None:
        """row 0 の crash（vol 64）。ChannelPlan の優先度により同 row の bd を自動的に置き換える。"""
        buf.put(0, CH_DRUM, ins["crash"].cell(vol=64))

    @staticmethod
    def _snare_roll(buf: MeasureBuffer, ins) -> None:
        """row 4-7 の sd 4 連打（vol 36→58）。row 4 の通常スネアは意図的に replace で上書きする。"""
        for i, r in enumerate(range(4, 8)):
            buf.replace(r, CH_DRUM, ins["sd"].cell(vol=ramp(36, 58, i, 4)))

    # ------------------------------------------------------------ 旋律（ファンファーレ・フレーズ）
    @staticmethod
    def _fanfare_events(chord, reg: tuple[int, int], vol: int) -> list[NoteEvent]:
        """rows (0,2,4,6) で「主音→3度→5度→オクターブ上」を駆け上がる（register を超えないよう clamp）。"""
        lo, hi = reg
        base = fold_into_range(chord.chord_tones[0], lo, hi)
        notes = [min(base + iv, hi) for iv in (0, 4, 7, 12)]
        return [NoteEvent(r, n, vol, 2) for r, n in zip((0, 2, 4, 6), notes)]

    @staticmethod
    def _apply_vibrato(buf: MeasureBuffer, events, inst) -> None:
        """長音（≥4 row）に 4xy ビブラートを付与する（vol と排他のため既定音量で鳴る）。"""
        for ev in events:
            if ev.dur >= 4:
                buf.replace(ev.row, CH_MEL, inst.cell(ev.note, effect=4, param=VIBRATO_PARAM, keep_sample=True))

    def _phrase_measure(self, buf, ins, st: MarchState, rng, mctx: MeasureCtx, reg, rules, *, gate: float) -> None:
        """8 measure = [a, a', b, c, a, a', b, cad] の 1 measure 分を picc で鳴らす。"""
        slot = PHRASE_SLOTS[mctx.measure_idx]
        chord = mctx.chord
        gen: MelodyGenerator = st.extra["gen"]
        gen.register, gen.rules = reg, rules
        if slot == "c":
            events = self._fanfare_events(chord, reg, vol=54)
            st.melody_prev = events[-1].note
        elif slot == "cad":
            events, st.melody_prev = gen.bar(
                HOLD_MOTIF, chord, st.melody_prev,
                cadence=True, cadence_target=chord.chord_tones[0], rows=self.rows_per_measure,
            )
        else:
            if slot == "a2":
                motif = st.extra.get("last_a_motif")
                if motif is None:
                    motif = rng.melody.choice(MARCH_MOTIFS)
            else:
                motif = rng.melody.choice(MARCH_MOTIFS)
                if slot == "a":
                    st.extra["last_a_motif"] = motif
            events, st.melody_prev = gen.bar(motif, chord, st.melody_prev, rows=self.rows_per_measure)
        articulate(buf, CH_MEL, events, ins["picc"], gate=gate)
        self._apply_vibrato(buf, events, ins["picc"])

    # ------------------------------------------------------------ 各 pattern の文法
    def _intro(self, mctx: MeasureCtx, st: MarchState, rng: RngStreams, buf: MeasureBuffer) -> None:
        ins, m, chord, intensity = mctx.instruments, mctx.measure_idx, mctx.chord, mctx.pattern.intensity
        if m == 0:                                            # crash＋section 保持和音（bd/sd なし）
            self._crash(buf, ins)
            buf.put(0, CH_HARM, ins["section"].cell(chord.harmony, param=chord.arp or 0))
        elif m == 3:                                          # 軽いスネアのみ
            buf.put(4, CH_DRUM, ins["sd"].cell(vol=30))
        elif m >= 4:                                          # m4 から oom-pah
            self._oom(buf, ins, chord, mctx.chord_measure_offset)
            self._pah(buf, ins, chord, intensity)
        # m1, m2: ドラムなし
        events = self._fanfare_events(chord, MELODY_MAIN, vol=52)
        articulate(buf, CH_MEL, events, ins["picc"], gate=0.9)
        self._apply_vibrato(buf, events, ins["picc"])

    def _strain(self, mctx: MeasureCtx, st: MarchState, rng: RngStreams, buf: MeasureBuffer) -> None:
        """a（sousa）/ a2（heroic）: フル oom-pah、m0 に crash、フレーズ末に snare roll。"""
        ins, m, chord, intensity = mctx.instruments, mctx.measure_idx, mctx.chord, mctx.pattern.intensity
        self._oom(buf, ins, chord, mctx.chord_measure_offset)
        self._pah(buf, ins, chord, intensity)
        if m == 0:
            self._crash(buf, ins)
        if m == mctx.n_measures - 1:
            self._snare_roll(buf, ins)
        self._phrase_measure(buf, ins, st, rng, mctx, MELODY_MAIN, STRAIN_RULES, gate=0.9)

    def _trio(self, mctx: MeasureCtx, st: MarchState, rng: RngStreams, buf: MeasureBuffer) -> None:
        """軽いドラム（bd 48 / sd 38）、horn は非 arp の単音、旋律は低め・跳躍少なめ、roll/crash なし。"""
        ins, chord, intensity = mctx.instruments, mctx.chord, mctx.pattern.intensity
        self._oom(buf, ins, chord, mctx.chord_measure_offset, bd_vol=48)
        self._pah(buf, ins, chord, intensity, sd_vol=38)
        self._phrase_measure(buf, ins, st, rng, mctx, MELODY_TRIO, TRIO_RULES, gate=0.9)

    def _trio2(self, mctx: MeasureCtx, st: MarchState, rng: RngStreams, buf: MeasureBuffer) -> None:
        """旋律は1オクターブ上、m0-3 に section 保持和音、m4 に crash、フレーズ末に roll。"""
        ins, m, chord, intensity = mctx.instruments, mctx.measure_idx, mctx.chord, mctx.pattern.intensity
        self._oom(buf, ins, chord, mctx.chord_measure_offset)
        self._pah(buf, ins, chord, intensity)
        if m <= 3:
            buf.put(0, CH_HARM, ins["section"].cell(chord.harmony, param=chord.arp or 0))
        if m == 4:
            self._crash(buf, ins)
        if m == mctx.n_measures - 1:
            self._snare_roll(buf, ins)
        self._phrase_measure(buf, ins, st, rng, mctx, MELODY_TRIO2, STRAIN_RULES, gate=0.9)

    def _coda(self, mctx: MeasureCtx, st: MarchState, rng: RngStreams, buf: MeasureBuffer) -> None:
        """m0 に crash、最終 measure は「crash＋tuba＋section＋picc 主音の長音」の最終和音（bd は crash に置換）。"""
        ins, m, chord, intensity = mctx.instruments, mctx.measure_idx, mctx.chord, mctx.pattern.intensity
        self._oom(buf, ins, chord, mctx.chord_measure_offset)
        if m == mctx.n_measures - 1:
            buf.put(0, CH_HARM, ins["section"].cell(chord.harmony, param=chord.arp or 0))
            self._crash(buf, ins)
        else:
            self._pah(buf, ins, chord, intensity)
            if m == 0:
                self._crash(buf, ins)
        self._phrase_measure(buf, ins, st, rng, mctx, MELODY_TRIO2, STRAIN_RULES, gate=0.9)
