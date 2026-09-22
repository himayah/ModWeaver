"""Suspense 共通: 音色・和声・語彙（設計書 §8.2）。

``suspense-slow`` / ``suspense-chase`` が共有する。両者は ``SuspenseBase`` を継承し、
``plan()`` と文法（各 kind の作曲メソッド）だけを別実装する。

音色の数値は初期値（聴感で調整可）。ループ閉合・音域・整数周期などの不変条件はテストで固定している。
"""
from __future__ import annotations

import dataclasses
import functools
import math
import random
from dataclasses import dataclass, field
from typing import Any, Optional

from ..core import dsp
from ..core.composer import MelodyGenerator, ScaleRules
from ..core.harmony import Registers, voice
from ..core.model import (
    CellGrid,
    ChannelRole,
    ChordSlot,
    ChordSpec,
    Instrument,
    MeasureBuffer,
    MeasureCtx,
    Pattern,
    RngStreams,
    SampleSpec,
)
from ..core.pitch import MODES, Scale, hz, lowest_note_with_pc
from .base import GenreProfile

# ============================================================
# 音域・調・進行（設計書 §8.2.1 / §8.2.4）
# ============================================================

KEY_PC = 0                                   # 主調 C
BASS_REG = (0, 11)                           # drone（shift −24 → t=24..35）
HARMONY_REG = (17, 28)                       # strings のアルペジオ基音（arp 最大 +7 でも t ≤ 35）
PIZZ_REG = (24, 35)                          # pizz（shift 0）
LEAD_REG = (24, 41)                          # lead（shift +12 → t=12..29）
REGISTERS = Registers(bass=BASS_REG, harmony=HARMONY_REG, melody=LEAD_REG)
PHRYGIAN = Scale(KEY_PC, MODES["phrygian"])
MODE_BY_QUALITY = {"dim": "dim_wh"}

# (root, quality, bass) — 主音 C 基準
PROGRESSIONS: dict[str, tuple[str, list[ChordSpec]]] = {
    "pedal": ("Pedal Tone Terror", [
        ChordSpec(0, "dim"), ChordSpec(1, "maj", 0), ChordSpec(0, "dim"), ChordSpec(11, "maj", 0),
    ]),
    "tritone": ("Tritone Nightmare", [
        ChordSpec(0, "min"), ChordSpec(6, "dim"), ChordSpec(5, "min"), ChordSpec(11, "dim"),
    ]),
    "phrygian": ("Phrygian Suspense", [
        ChordSpec(0, "min"), ChordSpec(1, "maj7"), ChordSpec(10, "min"), ChordSpec(0, "maj"),
    ]),
}

# ============================================================
# sample 番号 / ChannelPlan（§8.2.3）
# ============================================================

HEART, ANVIL, SWOOSH, DRONE, PIZZ, STRINGS, LEAD = 1, 2, 3, 4, 5, 6, 7
SAMPLE_KEYS = ("heart", "anvil", "swoosh", "drone", "pizz", "strings", "lead")   # sample 番号 1..7

CH_FX, CH_LOW, CH_TEX, CH_LEAD = 0, 1, 2, 3   # Ch1..Ch4（0 起点）

CHANNEL_PLAN = (
    ChannelRole("pulse/fx", frozenset({HEART, ANVIL, SWOOSH}), {ANVIL: 3, SWOOSH: 2, HEART: 1}),
    ChannelRole("low", frozenset({DRONE})),
    ChannelRole("texture", frozenset({STRINGS, PIZZ}), {STRINGS: 1, PIZZ: 2}),
    ChannelRole("lead/accent", frozenset({LEAD, PIZZ}), {LEAD: 1, PIZZ: 2}),
)

SWOOSH_SEC = 0.9        # swoosh の長さ（秒）
SHOCK_GUARD_ROWS = 8    # anvil の直前にこの row 数だけ heart/pizz/lead の発音を置かない
ANVIL_RING_SEC = 0.6    # anvil の余韻としてこの秒数は Ch1 の心拍で切らない（Ch1 は 1 音しか鳴らせない）


# ============================================================
# 音色合成（§8.2.2）
# ============================================================

def _normalized(xs: list[float], peak: float = 0.95) -> list[float]:
    m = max((abs(x) for x in xs), default=0.0)
    return [x * peak / m for x in xs] if m > 0 else xs


def _click(rng: random.Random, i: int, rate: float, ms: float, amp: float) -> float:
    """先頭 ``ms`` ミリ秒のノイズクリック（線形に減衰）。"""
    n = int(ms / 1000.0 * rate)
    return amp * rng.uniform(-1.0, 1.0) * (1.0 - i / n) if i < n else 0.0


def synth_heart() -> SampleSpec:
    """SubHeartbeat: 38Hz へ落ちるサブキック（絶対 Hz。unpitched）。"""
    rate = dsp.sample_rate(24)
    n = int(0.40 * rate)
    xs = []
    for i in range(n):
        t = i / rate
        phase = 2 * math.pi * (38.0 * t + (26.0 / 45.0) * (1.0 - math.exp(-45.0 * t)))
        env = min(1.0, t / 0.004) * math.exp(-8.0 * t)
        xs.append(math.tanh(1.4 * math.sin(phase) * env))
    return SampleSpec("SubHeartbeat", dsp.to_pcm(xs), 62, rate_note=24, pitched=False)


def synth_anvil() -> SampleSpec:
    """MetalAnvil: 非整合部分音の金属打撃。高域を含むため rate_note=B-3（15.7kHz）で生成。"""
    rate = dsp.sample_rate(35)
    n = int(0.9 * rate)
    parts = [(920, 1.0, 5.5), (1430, 0.8, 7.5), (2150, 0.6, 10.0), (3370, 0.35, 14.0), (5210, 0.2, 20.0)]
    rng = random.Random(2)
    raw = []
    for i in range(n):
        t = i / rate
        v = sum(w * math.sin(2 * math.pi * f * t) * math.exp(-a * t) for f, w, a in parts)
        raw.append(v + _click(rng, i, rate, 3.0, 0.6))
    xs = [math.tanh(1.2 * x) for x in _normalized(raw, 1.0)]
    return SampleSpec("MetalAnvil", dsp.to_pcm(xs), 64, rate_note=35, pitched=False)


def synth_swoosh() -> SampleSpec:
    """NoiseSwoosh: フィルタが開く向き（a: 0.65→0.15）で立ち上がるノイズ。末尾 8 sample で急減衰。"""
    rate = dsp.sample_rate(24)
    n = int(SWOOSH_SEC * rate)
    noise = dsp.noise_lp(random.Random(3), n, 0.65, 0.15)
    xs = [noise[i] * (i / n) ** 2.2 for i in range(n)]
    for k in range(8):
        xs[n - 1 - k] *= k / 8.0
    return SampleSpec("NoiseSwoosh", dsp.to_pcm(_normalized(xs)), 44, rate_note=24, pitched=False)


def synth_drone() -> SampleSpec:
    """LowDroneBass: K=6, L=760（126.7 spc）、shift −24（65.41Hz 基準）。奇数倍音＋サブ。"""
    terms = [(6 * h, 1.0 / h) for h in (1, 3, 5, 7)] + [(3, 0.6)]
    body = dsp.seamless_terms(760, terms)
    body = dsp.circular(lambda d: dsp.one_pole_lp(d, 0.35), body)
    body = [math.tanh(1.1 * x) for x in _normalized(body, 1.0)]
    data = dsp.to_pcm(dsp.with_attack(body, 60))
    return SampleSpec("LowDroneBass", data, 60, loop=(30, 380), rate_note=24, shift=-24)


def synth_pizz() -> SampleSpec:
    """PizzStab: 基音の時定数 τ=0.08s の減衰倍音（261.63Hz 基準）。"""
    rate = dsp.sample_rate(24)
    n = int(0.40 * rate)
    f0 = hz(24)
    mults, weights, alphas = (1, 2, 3, 4), (1.0, 0.6, 0.35, 0.2), (12.5, 18.0, 26.0, 38.0)
    rng = random.Random(5)
    raw = []
    for i in range(n):
        t = i / rate
        v = sum(w * math.sin(2 * math.pi * f0 * m * t) * math.exp(-a * t)
                for m, w, a in zip(mults, weights, alphas))
        raw.append(v + _click(rng, i, rate, 2.0, 0.3))
    return SampleSpec("PizzStab", dsp.to_pcm(_normalized(raw)), 56, rate_note=24, shift=0)


def synth_strings() -> SampleSpec:
    """TensionStrings: 同音デチューン対 2 組（130/131 と 138/139 cycle）。131−130=1 cycle → 基準音で 2.0Hz のうなり。"""
    base = [(130, 1.0), (131, 1.0), (138, 0.8), (139, 0.8)]
    terms = list(base) + [(2 * k, 0.35 * w) for k, w in base] + [(3 * k, 0.15 * w) for k, w in base]
    body = _normalized(dsp.seamless_terms(4144, terms), 0.95)
    data = dsp.to_pcm(dsp.with_attack(body, 200))
    return SampleSpec("TensionStrings", data, 40, loop=(100, 2072), rate_note=24, shift=0)


def synth_lead() -> SampleSpec:
    """ScreamingLead: K=12, L=190（15.83 spc）、shift +12。倍音 1..7、重み 1/h^0.8。"""
    body = _normalized(dsp.seamless_terms(190, [(12 * h, 1.0 / h ** 0.8) for h in range(1, 8)]), 0.95)
    data = dsp.to_pcm(dsp.with_attack(body, 80))
    return SampleSpec("ScreamingLead", data, 46, loop=(40, 95), rate_note=24, shift=12)


@functools.lru_cache(maxsize=1)
def _synth_all() -> tuple[tuple[str, SampleSpec], ...]:
    return (
        ("heart", synth_heart()), ("anvil", synth_anvil()), ("swoosh", synth_swoosh()), ("drone", synth_drone()),
        ("pizz", synth_pizz()), ("strings", synth_strings()), ("lead", synth_lead()),
    )


def build_suspense_samples() -> dict[str, SampleSpec]:
    """挿入順 = sample 番号（1..7）。合成は seed 非依存のため 1 回だけ行い、呼び出しごとに複製を返す。"""
    return {key: dataclasses.replace(spec) for key, spec in _synth_all()}


# ============================================================
# 共通語彙（§8.2.4）
# ============================================================

def row_seconds(bpm: int) -> float:
    """1 row の秒数（Speed 6 固定: 1 row = 15/bpm 秒）。"""
    return 15.0 / bpm


def swoosh_start_row(rows_per_measure: int, bpm: int) -> int:
    """swoosh の開始 row。sample の終わりが measure 末（＝直後の衝撃）に来るように逆算する（T9）。"""
    return rows_per_measure - round(SWOOSH_SEC / row_seconds(bpm))


def anvil_clear_row(bpm: int) -> int:
    """anvil の余韻が済み、Ch1 で心拍を再開してよい measure 内の row（拍頭に揃える）。

    slow（BPM 64〜72）は 4、chase（138〜148）は 8。
    """
    return math.ceil(math.ceil(ANVIL_RING_SEC / row_seconds(bpm)) / 4) * 4


def oneshot_off_row(inst: Instrument, row: int, bpm: int) -> int:
    """減衰系サンプルが鳴り終わる row（この row に OFF を置いても音は切れない）。"""
    spec = inst.spec
    dur = len(spec.data) / dsp.sample_rate(spec.rate_note)
    return row + math.ceil(dur / row_seconds(bpm))


def put_oneshot_off(buf: CellGrid, ch: int, row: int, inst: Instrument, bpm: int) -> None:
    """一発音の後に OFF（vol 0）を置き、同時音量の追跡（V15）を実態に合わせる。"""
    off = oneshot_off_row(inst, row, bpm)
    if off < buf.rows:
        buf.put(off, ch, inst.off())


def heartbeat(buf: CellGrid, heart: Instrument, beat_rows: range, lub: int, dub: int) -> None:
    """心拍語彙: 拍頭に lub、拍頭+2 row に dub（1 拍 = 4 row）。"""
    for r in beat_rows:
        buf.put(r, CH_FX, heart.cell(vol=lub))
        if r + 2 < buf.rows:
            buf.put(r + 2, CH_FX, heart.cell(vol=dub))


def strings_chord(buf: CellGrid, strings: Instrument, row: int, chord) -> None:
    """持続和音: ``harmony`` 音に ``arp``（vol と排他のためサンプル既定音量で鳴る。D3・T17）。"""
    buf.put(row, CH_TEX, strings.cell(chord.harmony, param=chord.arp or 0))


def pizz_ostinato(buf: CellGrid, pizz: Instrument, ch: int, rows: list[int], notes: list[int], vols: list[int]) -> None:
    for r, n, v in zip(rows, notes, vols):
        buf.put(r, ch, pizz.cell(n, vol=v))


def silence_run(buf: CellGrid, row: int, insts: dict[str, Instrument]) -> None:
    """持続中の drone / strings / lead を消音する（Silence run。全 ch で新規 note を置かない区間の先頭）。"""
    buf.put(row, CH_LOW, insts["drone"].off())
    buf.put(row, CH_TEX, insts["strings"].off())
    buf.put(row, CH_LEAD, insts["lead"].off())


def voice_progression(name: str, key_offset: int = 0) -> list[ChordSlot]:
    tonic = (KEY_PC + key_offset) % 12
    return [
        ChordSlot(voice(spec, tonic, PHRYGIAN, REGISTERS, arp=True, mode_by_quality=MODE_BY_QUALITY))
        for spec in PROGRESSIONS[name][1]
    ]


def progression_summary(label: str, name: str) -> str:
    chords = " - ".join(c.chord.label for c in voice_progression(name))
    return f"{label:<12}: {PROGRESSIONS[name][0]} -> {chords}"


# ============================================================
# 基底クラス
# ============================================================

@dataclass
class PatternState:
    """pattern 内で共有する状態。乱数の決定は begin_pattern に集約する（ストリーム消費の安定のため）。"""

    dropout: Optional[int] = None        # 心拍・持続音が途切れる measure
    anvil_measure: Optional[int] = None  # anvil を鳴らす measure（row 0）
    stab_row: Optional[int] = None       # 突発 pizz スタブの pattern 内 row
    lead_prev: Optional[int] = None      # lead 旋律の直前音
    extra: dict[str, Any] = field(default_factory=dict)


class SuspenseBase(GenreProfile):
    """Suspense 2 プロファイルの共通部。"""

    rows_per_measure = 16
    channel_plan = CHANNEL_PLAN
    tempo_policy = "engine"
    rng_mode = "streams"
    strict_buffers = True

    def build_samples(self) -> dict[str, SampleSpec]:
        return build_suspense_samples()

    # kind → 作曲メソッド名（サブクラスが定義）
    grammar: dict[str, str] = {}

    def compose_measure(self, mctx: MeasureCtx, state: PatternState, rng: RngStreams, buf: MeasureBuffer) -> None:
        method = self.grammar.get(mctx.pattern.kind)
        if method is None:
            raise KeyError(f"{self.id}: no grammar for pattern kind {mctx.pattern.kind!r}")
        getattr(self, method)(mctx, state, rng, buf)

    # --- 共通の補助 ---
    def lead_generator(self, rng: RngStreams, rules: ScaleRules, base_vol: int = 46) -> MelodyGenerator:
        return MelodyGenerator(rules, LEAD_REG, PHRYGIAN, rng.melody, base_vol=base_vol)

    def close_lead(self, pattern: Pattern, lead: Instrument) -> None:
        """pattern 末で lead を消音する（次の pattern へ鳴り続けるのを防ぐ）。"""
        pattern.put(pattern.rows - 1, CH_LEAD, lead.off())

    @staticmethod
    def pizz_root_note(chord, root_pc: Optional[int] = None) -> int:
        """PIZZ_REG 内の根音（pitch class は harmony 音の pc）。"""
        pc = chord.harmony % 12 if root_pc is None else root_pc
        return lowest_note_with_pc(pc, *PIZZ_REG)
