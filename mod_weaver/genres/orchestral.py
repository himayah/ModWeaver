"""orchestral: フルオーケストラ / 劇伴（GENRE_DESIGN_V2.md §3）。

8チャンネル（EXT-6。MOD では FastTracker 系の ``8CHN``、XM/S3M/IT ではサンプルパンでステレオ配置）の実証ジャンル。6声（bass/tenor/alto/soprano1/
soprano2/descant）の和声を、``harmony.voice()`` が返す標準4フィールド（bass/harmony/chord_tones）
に、残り3声（alto/soprano1/descant）を ``mctx.chord.chord_tones`` のピッチクラス集合から都度
導出する方式で表現する（§3.3 設計レビュー: 6声データを ``PatternPlan.extra`` や ``state`` に
持たせる必要はなく、``mctx.chord`` だけから毎回計算できる。既存 core は無変更）。
"""
from __future__ import annotations

import dataclasses
from typing import Any

from ..core import synth, synth_presets
from ..core.harmony import Registers, voice
from ..core.model import (
    Cell,
    ChannelRole,
    ChordDef,
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
from ..core.pitch import MODES, Scale, lowest_note_with_pc
from ..core.midi import GmVoice
from ..profiles.base import GenreProfile
from ..profiles.registry import register_profile

# ============================================================
# 音域・6声・進行（GENRE_DESIGN_V2.md §3.3）
# ============================================================

KEY_PC = 0                                    # C
BASS_REG = (-12, -1)                          # CB（shift=-24 → t=12..23）
TENOR_REG = (0, 11)                           # VC（shift=-12 → t=12..23）
ALTO_REG = (7, 18)                            # VLA（shift=-7 → t=14..25）
SOP1_REG = (12, 23)                           # VLN2（shift=0）
SOP2_REG = (19, 30)                           # VLN1（旋律、shift=0）
DESCANT_REG = (24, 35)                        # BRASS（shift=0）
REGISTERS = Registers(bass=BASS_REG, harmony=TENOR_REG, melody=SOP2_REG)

# (root, quality) — C（KEY_PC）基準の半音オフセット。I - IV - V - vi
PROGRESSION = (
    ChordSpec(0, "maj"), ChordSpec(5, "maj"), ChordSpec(7, "maj"), ChordSpec(9, "min"),
)


def voice_progression() -> list[ChordSlot]:
    scale = Scale(KEY_PC, MODES["ionian"])
    return [ChordSlot(voice(spec, KEY_PC, scale, REGISTERS), measures=1) for spec in PROGRESSION]


def progression_summary() -> str:
    chords = " - ".join(s.chord.label for s in voice_progression())
    return f"Progression        : I-IV-V-vi -> {chords}"


def _extra_voices(chord: ChordDef) -> tuple[int, int, int, int]:
    """alto/sop1/descant/sop2(旋律) を ``chord.chord_tones`` のピッチクラス集合から導出する。
    ``begin_pattern``/``state`` を使わず、``mctx.chord`` のみから毎回再計算できる（§3.3 参照）。
    """
    pcs = sorted({t % 12 for t in chord.chord_tones}) or [chord.bass % 12]
    alto = lowest_note_with_pc(pcs[1 % len(pcs)], *ALTO_REG)
    sop1 = lowest_note_with_pc(pcs[2 % len(pcs)], *SOP1_REG)
    descant = lowest_note_with_pc(pcs[0], *DESCANT_REG)
    sop2 = chord.chord_tones[-1] if chord.chord_tones else chord.bass
    return alto, sop1, descant, sop2


# ============================================================
# sample 番号 / ChannelPlan（GENRE_DESIGN_V2.md §3.1）
# ============================================================

VLN1, VLN2, VLA, VC, CB, WW, HORN, TRUMPET, TIMPANI, CYMBAL = range(1, 11)
SAMPLE_KEYS = ("vln1", "vln2", "vla", "vc", "cb", "ww", "horn", "trumpet", "timpani", "cymbal")

CH_VLN1, CH_VLN2, CH_VLA, CH_VC, CH_CB, CH_WW, CH_BRASS, CH_TIMP = range(8)

CHANNEL_PLAN = (
    ChannelRole("vln1", frozenset({VLN1})),
    ChannelRole("vln2", frozenset({VLN2})),
    ChannelRole("vla", frozenset({VLA})),
    ChannelRole("vc", frozenset({VC})),
    ChannelRole("cb", frozenset({CB})),
    ChannelRole("ww", frozenset({WW})),
    ChannelRole("brass", frozenset({HORN, TRUMPET}), {TRUMPET: 2, HORN: 1}),
    ChannelRole("timp", frozenset({TIMPANI, CYMBAL}), {CYMBAL: 2, TIMPANI: 1}),
)


# ============================================================
# 音色合成（core/synth.py の Patch 方式。core/synth_presets.py 参照）
# ============================================================

def build_orchestral_samples() -> dict[str, SampleSpec]:
    """挿入順 = sample 番号（1..10）。``SampleSpec.pan``（EXT-6）でチャンネルごとの定位を固定する。"""
    vln1 = dataclasses.replace(synth.render(synth_presets.ORCH_VIOLIN), pan=30)
    return {
        "vln1": vln1,
        "vln2": dataclasses.replace(vln1, finetune=3, volume=44, pan=80),  # 合奏感の軽いデチューン
        "vla": dataclasses.replace(synth.render(synth_presets.ORCH_VIOLA), pan=150),
        "vc": dataclasses.replace(synth.render(synth_presets.ORCH_CELLO), pan=190),
        "cb": dataclasses.replace(synth.render(synth_presets.ORCH_BASS_STR), pan=210),
        "ww": dataclasses.replace(synth.render(synth_presets.NOSTALGIC_FLUTE), pan=100),
        "horn": dataclasses.replace(synth.render(synth_presets.MARCH_BRASS_SECTION), pan=160),
        "trumpet": dataclasses.replace(synth.render(synth_presets.ORCH_TRUMPET), pan=160),
        "timpani": dataclasses.replace(synth.render(synth_presets.ORCH_TIMPANI), pan=128),
        "cymbal": dataclasses.replace(synth.render(synth_presets.FREE_CYMBAL_SWELL), pan=128),
    }


# ============================================================
# プロファイル本体
# ============================================================

GM_VOICES = {                                  # --format midi の GM 音色（core/midi.py）
    "vln1": GmVoice(program=40),
    "vln2": GmVoice(program=40),
    "vla": GmVoice(program=41),
    "vc": GmVoice(program=42),
    "cb": GmVoice(program=43),
    "ww": GmVoice(program=73),
    "horn": GmVoice(program=60),
    "trumpet": GmVoice(program=56),
    "timpani": GmVoice(program=47),
    "cymbal": GmVoice(program=119),
}


@register_profile
class OrchestralProfile(GenreProfile):
    id = "orchestral"
    display_name = "Orchestral"
    description = "フルオーケストラ／劇伴。8chマルチチャンネル、6声の弦+木管+金管+ティンパニ"
    title = "Orchestral Suite"
    default_filename = "OrchestralSuite.xm"
    tempo_choices = (76, 80, 84, 88)
    rows_per_measure = 16
    channel_plan = CHANNEL_PLAN
    gm_voices = GM_VOICES
    tempo_policy = "engine"
    rng_mode = "streams"
    strict_buffers = True

    grammar = {
        "intro": "_intro", "theme": "_theme", "development": "_development",
        "climax": "_climax", "resolution": "_resolution",
    }

    def build_samples(self) -> dict[str, SampleSpec]:
        return build_orchestral_samples()

    # ------------------------------------------------------------ 計画
    def plan(self, rng: RngStreams) -> SongPlan:
        bpm = rng.plan.choice(list(self.tempo_choices))
        slots = voice_progression()
        patterns = [
            PatternPlan("intro", slots, intensity=0.3),
            PatternPlan("theme", slots, intensity=0.5),
            PatternPlan("development", slots, intensity=0.7),
            PatternPlan("climax", slots, intensity=1.0),
            PatternPlan("resolution", slots, intensity=0.4),
        ]
        order = [0, 1, 2, 3, 4]              # 通作形式。ループしない
        return SongPlan(bpm=bpm, patterns=patterns, order=order, key_pc=KEY_PC, summary=[progression_summary()])

    def compose_measure(self, mctx: MeasureCtx, state: Any, rng: RngStreams, buf: MeasureBuffer) -> None:
        getattr(self, self.grammar[mctx.pattern.kind])(mctx, state, rng, buf)

    def finalize_pattern(self, pctx: PatternCtx, pattern: Pattern, state: Any, rng: RngStreams) -> None:
        # 弦楽器・木管・金管（すべてループ音色）は次 pattern へ鳴り続けないよう消音する
        for ch in (CH_VLN1, CH_VLN2, CH_VLA, CH_VC, CH_CB, CH_WW, CH_BRASS):
            pattern.put(pattern.rows - 1, ch, Cell(None, 0, vol=0))

    # ------------------------------------------------------------ 共通の部品
    @staticmethod
    def _strings(buf: MeasureBuffer, ins, chord: ChordDef, vol_scale: float) -> tuple[int, int]:
        alto, sop1, descant, sop2 = _extra_voices(chord)
        buf.put(0, CH_VLN1, ins["vln1"].cell(sop2, vol=max(1, round(48 * vol_scale))))
        buf.put(0, CH_VLN2, ins["vln2"].cell(sop1, vol=max(1, round(44 * vol_scale))))
        buf.put(0, CH_VLA, ins["vla"].cell(alto, vol=max(1, round(42 * vol_scale))))
        buf.put(0, CH_VC, ins["vc"].cell(chord.harmony, vol=max(1, round(46 * vol_scale))))
        buf.put(0, CH_CB, ins["cb"].cell(chord.bass, vol=max(1, round(50 * vol_scale))))
        return sop2, descant

    @staticmethod
    def _woodwind(buf: MeasureBuffer, ins, sop2: int, vol_scale: float) -> None:
        buf.put(0, CH_WW, ins["ww"].cell(sop2, vol=max(1, round(40 * vol_scale))))

    @staticmethod
    def _brass(buf: MeasureBuffer, ins, descant: int, vol_scale: float, *, use_trumpet: bool) -> None:
        key = "trumpet" if use_trumpet else "horn"
        buf.put(0, CH_BRASS, ins[key].cell(descant, vol=max(1, round(44 * vol_scale))))

    @staticmethod
    def _timpani(buf: MeasureBuffer, ins, chord: ChordDef, rows: tuple[int, ...], vol: int) -> None:
        for r in rows:
            buf.put(r, CH_TIMP, ins["timpani"].cell(chord.bass, vol=vol))

    @staticmethod
    def _cymbal_swell(buf: MeasureBuffer, ins, vol: int) -> None:
        buf.put(0, CH_TIMP, ins["cymbal"].cell(vol=vol))     # 優先度2でtimpaniを置換

    # ------------------------------------------------------------ 各 pattern の文法
    def _intro(self, mctx: MeasureCtx, st: Any, rng: RngStreams, buf: MeasureBuffer) -> None:
        """弦楽器のみ。row 0 に CH_WW/CH_BRASS/CH_TIMP の空きを残す（apply_tempo の契約）。"""
        ins, chord, intensity = mctx.instruments, mctx.chord, mctx.pattern.intensity
        self._strings(buf, ins, chord, intensity)

    def _theme(self, mctx: MeasureCtx, st: Any, rng: RngStreams, buf: MeasureBuffer) -> None:
        ins, chord, intensity = mctx.instruments, mctx.chord, mctx.pattern.intensity
        sop2, _descant = self._strings(buf, ins, chord, intensity)
        self._woodwind(buf, ins, sop2, intensity)

    def _development(self, mctx: MeasureCtx, st: Any, rng: RngStreams, buf: MeasureBuffer) -> None:
        ins, chord, intensity = mctx.instruments, mctx.chord, mctx.pattern.intensity
        sop2, descant = self._strings(buf, ins, chord, intensity)
        self._woodwind(buf, ins, sop2, intensity)
        self._brass(buf, ins, descant, intensity, use_trumpet=False)

    def _climax(self, mctx: MeasureCtx, st: Any, rng: RngStreams, buf: MeasureBuffer) -> None:
        """フル編成。トランペット（優先度高）、ティンパニ連打、フレーズ先頭にシンバル・スウェル。"""
        ins, chord, intensity = mctx.instruments, mctx.chord, mctx.pattern.intensity
        sop2, descant = self._strings(buf, ins, chord, intensity)
        self._woodwind(buf, ins, sop2, intensity)
        self._brass(buf, ins, descant, intensity, use_trumpet=True)
        self._timpani(buf, ins, chord, (0, 8), 56)
        if mctx.measure_idx == 0:
            self._cymbal_swell(buf, ins, 60)

    def _resolution(self, mctx: MeasureCtx, st: Any, rng: RngStreams, buf: MeasureBuffer) -> None:
        """弦楽器のみで静かに終える（intensity=0.4 が intro より柔らかい着地を作る）。"""
        ins, chord, intensity = mctx.instruments, mctx.chord, mctx.pattern.intensity
        self._strings(buf, ins, chord, intensity)
