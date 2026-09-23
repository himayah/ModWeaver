"""maqam: 中東マカーム / インド古典（GENRE_DESIGN_V2.md §5）。

maqam Rast（G を主音 qarar とする）を EXT-3（``core/pitch.MicroScale``）で表現する最初のジャンル。
1 measure = 16 row = 4/4。usul（リズム周期）は maqsum（``DUM . TEK . . DUM TEK .``）。

和声は `harmony.voice()`／`CHORD_QUALITIES` を経由せず、``ChordDef`` を直接手組みする
（march/nostalgic と同じ「明示的ボイシング」パターン。§8.2 参照）。
"""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import Any, Optional

from ..core import synth, synth_presets
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
from ..core.pitch import MicroScale, parse, resolve_micronote
from .base import GenreProfile
from .registry import register_profile

# ============================================================
# 音律（GENRE_DESIGN_V2.md §5.1）
# ============================================================

KEY_PC = 7                                    # G
QARAR_NOTE = parse("G-2")                     # 主音（qarar）を置く logical note
RAST_ON_G = MicroScale(tonic_pc=KEY_PC, degrees_cents=(0, 200, 350, 500, 700, 900, 1050))
#  度数: 主音(0) - 全音(200) - 中立3度(350) - 完全4度(500) - 完全5度(700) - 全音(900) - 中立7度(1050)
NEUTRAL_DEGREES = {2: "oud_n3", 6: "oud_n7"}  # 度数(mod 7) -> 中立音程用 Instrument 名
MELODY_DEGREE_RANGE = (-3, 9)                 # _maqam_phrase が動く度数の範囲（t が 0..35 に収まる）


def _degree_note(degree: int) -> tuple[int, str]:
    """度数 -> (logical note t, Instrument 名)。t は resolve_micronote() の 12-ET 最近傍。"""
    t, _ft = resolve_micronote(RAST_ON_G.absolute_cents(degree, QARAR_NOTE))
    key = NEUTRAL_DEGREES.get(degree % 7, "oud")
    return t, key


def _neutral_finetune(degree: int) -> int:
    """NEUTRAL_DEGREES の度数の finetune（build_samples() で派生 Instrument を作るのに使う）。
    オクターブが変わっても残差セントは不変（1200セント=12半音は finetune に影響しない）ため、
    基準オクターブ（0..6）で計算した値がそのまま全オクターブで使える。"""
    _t, ft = resolve_micronote(RAST_ON_G.absolute_cents(degree, QARAR_NOTE))
    return ft


def _maqam_chord() -> ChordDef:
    """qarar/ghammaz と7度のジンス全音を手組みする（§5.5）。"""
    scale_tones = tuple(_degree_note(d)[0] for d in range(7))
    return ChordDef(
        label="Rast on G", bass=QARAR_NOTE, harmony=_degree_note(4)[0],
        chord_tones=(), scale_tones=scale_tones, arp=None, explicit=True,
    )


def voice_progression() -> list[ChordSlot]:
    """maqam は転調しないため、全 pattern が同一の chord を参照する（measures=4 で1 pattern分）。"""
    return [ChordSlot(_maqam_chord(), measures=4)]


# ============================================================
# sample 番号 / ChannelPlan（GENRE_DESIGN_V2.md §5.3）
# ============================================================

DUM, TEK, OUD, OUD_N3, OUD_N7, NAY, QANUN = 1, 2, 3, 4, 5, 6, 7
SAMPLE_KEYS = ("dum", "tek", "oud", "oud_n3", "oud_n7", "nay", "qanun")

CH_PERC, CH_OUD, CH_NAY, CH_QANUN = 0, 1, 2, 3

CHANNEL_PLAN = (
    ChannelRole("perc", frozenset({DUM, TEK}), {DUM: 2, TEK: 1}),
    ChannelRole("oud", frozenset({OUD, OUD_N3, OUD_N7})),
    ChannelRole("nay", frozenset({NAY})),
    ChannelRole("qanun", frozenset({QANUN})),
)

USUL_MAQSUM = {0: "dum", 4: "tek", 10: "dum", 12: "tek"}
QANUN_ARP_ROWS = (0, 2, 4, 6)


# ============================================================
# 音色合成（core/synth.py の Patch 方式。core/synth_presets.py 参照）
# ============================================================

def build_maqam_samples() -> dict[str, SampleSpec]:
    """挿入順 = sample 番号（1..7）。中立音程用の oud_n3/oud_n7 は finetune 派生。"""
    oud = synth.render(synth_presets.MAQAM_OUD)
    return {
        "dum": synth.render(synth_presets.MAQAM_DAF_DUM),
        "tek": synth.render(synth_presets.MAQAM_DAF_TEK),
        "oud": oud,
        "oud_n3": dataclasses.replace(oud, finetune=_neutral_finetune(2)),
        "oud_n7": dataclasses.replace(oud, finetune=_neutral_finetune(6)),
        "nay": synth.render(synth_presets.MAQAM_NAY),
        "qanun": synth.render(synth_presets.MAQAM_QANUN),
    }


# ============================================================
# state
# ============================================================

@dataclass
class MaqamState:
    degree_prev: Optional[int] = None
    extra: dict[str, Any] = field(default_factory=dict)


# ============================================================
# プロファイル本体
# ============================================================

@register_profile
class MaqamProfile(GenreProfile):
    id = "maqam"
    display_name = "Maqam Rast"
    description = "中東マカーム（Rast on G）。ウードのタクシームとマクスーム usul、中立音程"
    title = "Maqam Rast"
    default_filename = "MaqamRast.mod"
    tempo_choices = (84, 88, 92, 96)
    rows_per_measure = 16
    channel_plan = CHANNEL_PLAN
    tempo_policy = "engine"
    rng_mode = "streams"
    strict_buffers = True

    grammar = {
        "taqsim": "_taqsim", "ostinato_a": "_ostinato_a",
        "ostinato_b": "_ostinato_b", "coda": "_coda",
    }

    def build_samples(self) -> dict[str, SampleSpec]:
        return build_maqam_samples()

    # ------------------------------------------------------------ 計画
    def plan(self, rng: RngStreams) -> SongPlan:
        bpm = rng.plan.choice(list(self.tempo_choices))
        slots = voice_progression()
        patterns = [
            PatternPlan("taqsim", slots, intensity=0.3),
            PatternPlan("ostinato_a", slots, intensity=0.6),
            PatternPlan("ostinato_b", slots, intensity=0.85),
            PatternPlan("coda", slots, intensity=1.0),
        ]
        order = [0, 1, 2, 0, 1, 3]
        return SongPlan(
            bpm=bpm, patterns=patterns, order=order, key_pc=KEY_PC,
            summary=[f"Maqam            : Rast on G -> {_maqam_chord().label}"],
        )

    def begin_pattern(self, pctx: PatternCtx, rng: RngStreams) -> MaqamState:
        return MaqamState()

    def compose_measure(self, mctx: MeasureCtx, state: MaqamState, rng: RngStreams, buf: MeasureBuffer) -> None:
        getattr(self, self.grammar[mctx.pattern.kind])(mctx, state, rng, buf)

    def finalize_pattern(self, pctx: PatternCtx, pattern: Pattern, state: MaqamState, rng: RngStreams) -> None:
        # nay（ループ音色）は次 pattern へ鳴り続けないよう消音する
        pattern.put(pattern.rows - 1, CH_NAY, Cell(None, 0, vol=0))

    # ------------------------------------------------------------ 共通の部品
    @staticmethod
    def _maqam_phrase(rng: RngStreams, prev_degree: Optional[int], n_events: int) -> tuple[list[int], int]:
        """順次進行主体、まれに4度・5度の跳躍を混ぜる（§5.5）。度数列と終端度数を返す。"""
        lo, hi = MELODY_DEGREE_RANGE
        degree = prev_degree if prev_degree is not None else 0
        out = []
        for _ in range(n_events):
            if rng.random() < 0.15:
                step = rng.choice((-4, -3, 3, 4))
            else:
                step = rng.choice((-2, -1, 1, 1, 2))
            degree = max(lo, min(hi, degree + step))
            out.append(degree)
        return out, degree

    @staticmethod
    def _usul(buf: MeasureBuffer, ins) -> None:
        for row, key in USUL_MAQSUM.items():
            buf.put(row, CH_PERC, ins[key].cell(vol=54 if key == "dum" else 42))

    @staticmethod
    def _qanun_arp(buf: MeasureBuffer, ins, chord: ChordDef) -> None:
        """ジンスを上行分散和音として弾く（度数0,1,2,3。qanun は常に固定音色）。"""
        for i, row in enumerate(QANUN_ARP_ROWS):
            t, _key = _degree_note(i)
            buf.put(row, CH_QANUN, ins["qanun"].cell(t, vol=38))

    @staticmethod
    def _nay_drone(buf: MeasureBuffer, ins, chord: ChordDef, mctx: MeasureCtx) -> None:
        if mctx.measure_idx == 0:
            buf.put(0, CH_NAY, ins["nay"].cell(chord.bass, vol=36))

    def _oud_melody(self, buf: MeasureBuffer, ins, st: MaqamState, rng: RngStreams, rows, base_vol: int) -> None:
        degrees, st.degree_prev = self._maqam_phrase(rng, st.degree_prev, len(rows))
        for row, degree in zip(rows, degrees):
            t, key = _degree_note(degree)
            buf.put(row, CH_OUD, ins[key].cell(t, vol=base_vol))

    # ------------------------------------------------------------ 各 pattern の文法
    def _taqsim(self, mctx: MeasureCtx, st: MaqamState, rng: RngStreams, buf: MeasureBuffer) -> None:
        """打楽器なし、oud 単独のフレーズ（自由リズム風。onset の粗密で表現）。"""
        n = rng.melody.choice((2, 3, 4))
        rows = sorted(rng.melody.sample(range(16), n))
        self._oud_melody(buf, mctx.instruments, st, rng.melody, rows, base_vol=46)

    def _ostinato_a(self, mctx: MeasureCtx, st: MaqamState, rng: RngStreams, buf: MeasureBuffer) -> None:
        ins, chord = mctx.instruments, mctx.chord
        self._usul(buf, ins)
        self._qanun_arp(buf, ins, chord)
        self._nay_drone(buf, ins, chord, mctx)

    def _ostinato_b(self, mctx: MeasureCtx, st: MaqamState, rng: RngStreams, buf: MeasureBuffer) -> None:
        ins, chord = mctx.instruments, mctx.chord
        self._usul(buf, ins)
        self._qanun_arp(buf, ins, chord)
        self._nay_drone(buf, ins, chord, mctx)
        self._oud_melody(buf, ins, st, rng.melody, (2, 6, 9, 14), base_vol=48)

    def _coda(self, mctx: MeasureCtx, st: MaqamState, rng: RngStreams, buf: MeasureBuffer) -> None:
        """最終 measure のみ、qarar のユニゾンで静かに終える。"""
        ins, chord = mctx.instruments, mctx.chord
        if mctx.is_last:
            buf.put(0, CH_OUD, ins["oud"].cell(chord.bass, vol=44))
            buf.put(0, CH_QANUN, ins["qanun"].cell(chord.bass, vol=34))
            buf.put(0, CH_NAY, ins["nay"].cell(chord.harmony, vol=30))
