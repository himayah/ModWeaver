"""Nostalgic プロファイル: 旧 ``twilight_pad.py`` のロジックの等価移植（設計書 §8.1）。

作曲ロジック（plan・pattern の Cell 配置）は旧実装とバイト単位で同一（回帰テスト CP3〜CP4）。
サンプル合成は core/synth.py の Patch 方式へ移行済みのため、波形バイトの完全一致はもはや
目標ではない（CP2・CP5 は構造的な近さのみ確認する。core/synth_presets.py 参照）。
作曲ロジック側では次の旧挙動（Quirk）を意図的に保存している:

- Q1 アウトロ pattern の row 0 はフェード用キックで上書きされ、テンポセルが存在しない
- Q2 イントロは row 0 ch0 に「音なし＋F bpm」、それ以外は「キック(smp1)＋F bpm」
- Q3 Pad / Flute のループは K=32/L=1024 で −17.6 cent フラット（D1。修正は別変更 F1）
- Q4 MellowFlute は定義のみで未使用（sample 番号 7 を占有）
- Q5 サビのオクターブシフトは ``min(3, octave+shift)`` で頭打ち
- Q6 ゴーストノートは ``has_ghost and is_chorus`` の row 15 のみ、フィルは bar 3 の row 14/15
- Q7 曲名 ``Twilight Pad``、finetune=0、restart=0x7F

乱数は単一の ``random.Random(seed)`` を旧実装と同じ順序で消費する（D9）。
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Optional

from ..core import pitch
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
    SampleSpec,
    SongPlan,
)
from . import nostalgic_samples as smp
from ..core.midi import GmVoice
from .base import GenreProfile
from .registry import register_profile

# sample 番号（build_samples の挿入順と一致させる）
KICK, SNARE, HIHAT, BASS, MUSICBOX, PAD, FLUTE = 1, 2, 3, 4, 5, 6, 7

C3 = pitch.parse("C-3")

TEMPO_CHOICES = (88, 90, 92, 94, 96)

# 旧 SCALE_NOTES（C-2..B-3 の白鍵 14 音）。旧実装はこのリスト上の位置（音階度数）で距離を測る
SCALE_NOTES = [pitch.parse(n) for n in (
    "C-2", "D-2", "E-2", "F-2", "G-2", "A-2", "B-2",
    "C-3", "D-3", "E-3", "F-3", "G-3", "A-3", "B-3",
)]

# 旧 CHORD_DEFS（手書きボイシング）
_CHORD_SRC = {
    "Fmaj7": ("F-2", "C-3", ["A-2", "C-3", "E-3", "A-3"], ["A-2", "C-3", "D-3", "E-3", "G-3", "A-3"]),
    "Em7": ("E-2", "B-2", ["G-2", "B-2", "D-3", "G-3"], ["B-2", "C-3", "D-3", "E-3", "G-3", "A-3"]),
    "Dm7": ("D-2", "A-2", ["F-2", "A-2", "C-3", "F-3"], ["A-2", "C-3", "D-3", "E-3", "F-3", "A-3"]),
    "Cmaj7": ("C-2", "G-2", ["E-2", "G-2", "B-2", "C-3", "E-3"], ["G-2", "A-2", "B-2", "C-3", "D-3", "E-3", "G-3"]),
    "G7": ("G-2", "D-3", ["B-2", "D-3", "F-3", "G-3"], ["B-2", "C-3", "D-3", "E-3", "F-3", "G-3"]),
    "Am7": ("A-2", "E-3", ["C-3", "E-3", "G-3", "A-3"], ["A-2", "B-2", "C-3", "D-3", "E-3", "G-3", "A-3"]),
}

CHORD_DEFS: dict[str, ChordDef] = {
    name: ChordDef(
        label=name,
        bass=pitch.parse(root),
        harmony=pitch.parse(pad),
        chord_tones=tuple(pitch.parse(n) for n in ct),
        scale_tones=tuple(pitch.parse(n) for n in st),
        explicit=True,
    )
    for name, (root, pad, ct, st) in _CHORD_SRC.items()
}

# ノスタルジックさを担保するコード進行プール
PROGRESSION_PRESETS = [
    ("Step-Down (Nostalgic Descent)", ["Fmaj7", "Em7", "Dm7", "Cmaj7"]),
    ("Royal Road (Classic Emotion)", ["Fmaj7", "G7", "Em7", "Am7"]),
    ("Saudade (Sentimental Sunset)", ["Dm7", "G7", "Cmaj7", "Am7"]),
    ("Journey (Memories & Depart)", ["Am7", "Fmaj7", "Cmaj7", "G7"]),
    ("Canon Sunset (Warm Twilight)", ["Cmaj7", "G7", "Am7", "Em7"]),
]

RHYTHM_MOTIFS = [
    [0, 4, 6, 10, 12],
    [0, 6, 10, 14],
    [0, 4, 8, 12],
    [0, 3, 6, 10, 12],
    [0, 6, 8, 12],
]

CHANNEL_PLAN = (
    ChannelRole("drums", frozenset({KICK, SNARE, HIHAT})),
    ChannelRole("bass", frozenset({BASS})),
    ChannelRole("pad", frozenset({PAD})),
    ChannelRole("melody", frozenset({MUSICBOX})),
)


def _legacy_cell(note: Optional[int], sample: int, vol: int) -> Cell:
    """旧 ``cell()`` と同じく ``vol`` を 0..64 にクランプして Cell を作る（範囲外を例外とする Cell の吸収）。"""
    return Cell(note, sample, vol=max(0, min(64, int(vol))))


def _shift_octave(note: int, octave_shift: int) -> int:
    """旧実装のオクターブシフト（``min(3, octave+shift)`` で頭打ち。Q5）。"""
    octave, pc = note // 12 + 1, note % 12
    return (min(3, octave + octave_shift) - 1) * 12 + pc


def _scale_pos(note: int) -> int:
    return SCALE_NOTES.index(note)


def _melody_bar(
    rng: random.Random,
    chord: ChordDef,
    rhythm: list[int],
    prev_note: Optional[int],
    octave_shift: int,
    is_cadence: bool,
) -> tuple[list[tuple[int, int, int]], Optional[int]]:
    """コードトーンと対位法ルールに基づき、1 小節分のメロディを生成（旧 ``generate_melody_bar``）。"""
    chord_tones = list(chord.chord_tones)
    scale_tones = list(chord.scale_tones)

    if octave_shift > 0:
        chord_tones = [_shift_octave(n, octave_shift) for n in chord_tones]
        scale_tones = [_shift_octave(n, octave_shift) for n in scale_tones]

    notes = []
    current_note = prev_note

    for idx, row in enumerate(rhythm):
        if idx == 0:
            # 強拍はコードトーンから選択
            if current_note is None:
                note = rng.choice(chord_tones)
            else:
                sorted_tones = sorted(
                    chord_tones,
                    key=lambda n: abs(_scale_pos(n) - _scale_pos(current_note)),
                )
                note = sorted_tones[0] if rng.random() < 0.75 else sorted_tones[min(1, len(sorted_tones) - 1)]
        elif idx == len(rhythm) - 1 and is_cadence:
            # フレーズ末尾の終止（解決音）
            note = chord_tones[0] if chord_tones else C3
        else:
            # 経過音: 75% で順次進行、25% で跳躍進行
            curr_idx = _scale_pos(current_note)
            if rng.random() < 0.75:
                step = rng.choice([-1, 1, -2, 2])
                target_idx = max(0, min(len(SCALE_NOTES) - 1, curr_idx + step))
                cand = SCALE_NOTES[target_idx]
                note = cand if cand in scale_tones else min(
                    scale_tones, key=lambda s: abs(_scale_pos(s) - target_idx)
                )
            else:
                note = rng.choice(chord_tones)

        current_note = note
        vol = 60 if idx == 0 else rng.randint(48, 56)
        notes.append((row, note, vol))

    return notes, current_note


@dataclass
class _State:
    """pattern 内で共有する状態（旧 build_procedural_pattern の局所変数）。"""

    rhythms: list[list[int]]
    has_ghost: bool
    melody_prev: Optional[int] = None


GM_VOICES = {                                  # --format midi の GM 音色（core/midi.py）
    "kick": GmVoice(drum_note=36),
    "snare": GmVoice(drum_note=38),
    "hihat": GmVoice(drum_note=42),
    "bass": GmVoice(program=33),
    "musicbox": GmVoice(program=10),
    "pad": GmVoice(program=89),
    "flute": GmVoice(program=73),
}


@register_profile
class NostalgicProfile(GenreProfile):
    id = "nostalgic"
    display_name = "TwilightPad Procedural"
    description = "夕暮れの郷愁を誘う Lo-Fi ビートとオルゴール（従来の TwilightPad）"
    title = "Twilight Pad"
    default_filename = "TwilightPad.mod"
    tempo_choices = TEMPO_CHOICES
    rows_per_measure = 16
    channel_plan = CHANNEL_PLAN
    gm_voices = GM_VOICES
    tempo_policy = "profile"
    rng_mode = "single"
    strict_buffers = False

    def build_samples(self) -> dict[str, SampleSpec]:
        # gen_* は core/synth.py の Patch 方式へ移行済み（core/synth_presets.py）。完成した SampleSpec を返す。
        return {
            "kick": smp.gen_kick(),
            "snare": smp.gen_snare(),
            "hihat": smp.gen_hihat(),
            "bass": smp.gen_bass(),
            "musicbox": smp.gen_musicbox(),
            "pad": smp.gen_pad(),
            "flute": smp.gen_flute(),
        }

    # --- 計画 ---
    def plan(self, rng: random.Random) -> SongPlan:
        # 乱数消費順（厳守）: randrange → randint → choice
        idx_a = rng.randrange(len(PROGRESSION_PRESETS))
        idx_b = (idx_a + rng.randint(1, len(PROGRESSION_PRESETS) - 1)) % len(PROGRESSION_PRESETS)
        name_a, prog_a = PROGRESSION_PRESETS[idx_a]
        name_b, prog_b = PROGRESSION_PRESETS[idx_b]
        bpm = rng.choice(list(TEMPO_CHOICES))

        def slots(prog: list[str]) -> list[ChordSlot]:
            return [ChordSlot(CHORD_DEFS[c]) for c in prog]

        # 作成順 [intro(A), A, B(chorus), outro(A)]、曲順 [0,1,2,1,3]
        patterns = [
            PatternPlan("intro", slots(prog_a)),
            PatternPlan("a", slots(prog_a)),
            PatternPlan("b", slots(prog_b)),
            PatternPlan("outro", slots(prog_a)),
        ]
        return SongPlan(
            bpm=bpm,
            patterns=patterns,
            order=[0, 1, 2, 1, 3],
            summary=[
                f"Theme A     : {name_a} -> {' - '.join(prog_a)}",
                f"Theme B     : {name_b} -> {' - '.join(prog_b)}",
            ],
        )

    def begin_pattern(self, pctx: PatternCtx, rng: random.Random) -> _State:
        # 乱数消費順（厳守）: choice ×2 → random（has_ghost）
        motif_a = rng.choice(RHYTHM_MOTIFS)
        motif_b = rng.choice(RHYTHM_MOTIFS)
        rhythms = [motif_a, motif_a, motif_b, [0, 6, 10, 14] if pctx.kind != "outro" else [0, 8]]
        has_ghost = rng.random() < 0.5
        return _State(rhythms, has_ghost)

    # --- 作曲 ---
    def compose_measure(self, mctx: MeasureCtx, state: _State, rng: random.Random, buf: MeasureBuffer) -> None:
        kind = mctx.pattern.kind
        is_intro, is_outro, is_chorus = kind == "intro", kind == "outro", kind == "b"
        bar = mctx.measure_idx
        chord = mctx.chord

        # テンポ指定（pattern 先頭。Q1/Q2: アウトロは後続のキックで上書きされる）
        if bar == 0:
            if is_intro:
                buf.put(0, 0, Cell(None, 0, 0x0F, mctx.pattern.bpm))
            else:
                buf.put(0, 0, Cell(C3, KICK, 0x0F, mctx.pattern.bpm))

        self._drums(buf, bar, is_intro, is_outro, is_chorus, state.has_ghost)
        self._bass(buf, bar, chord, is_intro, is_outro, rng)
        self._pad(buf, bar, chord, is_outro)
        self._melody(buf, bar, chord, state, is_intro, is_outro, is_chorus, rng)

    @staticmethod
    def _drums(buf, bar, is_intro, is_outro, is_chorus, has_ghost) -> None:
        if is_intro:
            return
        if is_outro:
            # アウトロは静かなキックのみ
            if bar < 2:
                buf.put(0, 0, _legacy_cell(C3, KICK, 46 - bar * 10))
                buf.put(8, 0, _legacy_cell(C3, KICK, 40 - bar * 10))
            return
        for step in range(0, 16, 2):
            if step in (0, 8):
                if not (step == 0 and bar == 0):   # Row 0 はテンポセルで処理済み
                    buf.put(step, 0, _legacy_cell(C3, KICK, 56))
            elif step in (4, 12):
                buf.put(step, 0, _legacy_cell(C3, SNARE, 50))
            else:
                buf.put(step, 0, _legacy_cell(C3, HIHAT, 40))
            buf.put(step + 1, 0, _legacy_cell(C3, HIHAT, 30))   # 裏拍ハイハット
        if has_ghost and is_chorus:                              # ゴーストノート（Q6）
            buf.put(15, 0, _legacy_cell(C3, HIHAT, 24))
        if bar == 3:                                             # 小節末フィル（Q6）
            buf.put(14, 0, _legacy_cell(C3, HIHAT, 34))
            buf.put(15, 0, _legacy_cell(C3, SNARE, 46))

    @staticmethod
    def _bass(buf, bar, chord, is_intro, is_outro, rng) -> None:
        if is_intro:
            return
        root = chord.bass
        buf.put(0, 1, _legacy_cell(root, BASS, 60 if not is_outro else 50 - bar * 8))
        if not is_outro:
            buf.put(8, 1, _legacy_cell(root, BASS, 54))
            if rng.random() < 0.6:
                buf.put(12, 1, _legacy_cell(chord.chord_tones[0], BASS, 50))

    @staticmethod
    def _pad(buf, bar, chord, is_outro) -> None:
        pad_vol = 46 if not is_outro else max(10, 42 - bar * 8)
        buf.put(0, 2, _legacy_cell(chord.harmony, PAD, pad_vol))

    @staticmethod
    def _melody(buf, bar, chord, state, is_intro, is_outro, is_chorus, rng) -> None:
        oct_shift = 1 if is_chorus else 0
        is_cadence = bar == 3
        bar_melody, state.melody_prev = _melody_bar(
            rng, chord, state.rhythms[bar], state.melody_prev, oct_shift, is_cadence
        )
        for m_row, m_note, m_vol in bar_melody:
            if is_intro:
                m_vol = max(38, m_vol - 6)
            elif is_outro:
                m_vol = max(30, m_vol - bar * 5)
            buf.put(m_row, 3, _legacy_cell(m_note, MUSICBOX, m_vol))

    def finalize_pattern(self, pctx: PatternCtx, pattern: Pattern, state: _State, rng: random.Random) -> None:
        # アウトロのフェードアウト処理
        if pctx.kind == "outro":
            pattern.put(56, 2, Cell(None, 0, vol=18))
            pattern.put(60, 2, Cell(None, 0, vol=8))
            pattern.put(63, 2, Cell(None, 0, vol=0))
