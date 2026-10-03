"""free-jazz（旧 genres/free_jazz.py の移植。DESIGN.md §6 のグループC）。

和声は ``voice()`` を経由せず、隣接半音を密集させたトーンクラスターを ``ChordDef`` として直接手組みする
（march・nostalgic・maqam と同じ明示的ボイシング）ので ``harmony=None`` とし ``plan()`` を上書きする。
密なコンポジションルールではなく確率密度でテクスチャを作る（各楽器は intensity に応じた確率で step ごとに鳴らす）。
4区間（movement_a・b・climax・c）を通して部品 ``tempo_curve`` で BPM を連続的にうねらせる（ルバート）。
``--tempo`` は開始 BPM で、カーブ全体を ``開始 BPM / 96`` 倍に相似拡大する（現行どおり）。
"""
from __future__ import annotations

import math
import random

from ..core.model import ChordDef, GmVoice
from ..core.pitch import MODES, Scale, fold_into_range
from ..core.synth_presets import PRESETS
from ..framework.context import Generator, MeasureCtx, SectionCtx
from ..framework.genre import Genre, Instrument, Part, Section
from ..framework.gens import tempo_curve
from ..framework.plan import MeasurePlan, Meter, SectionPlan, SongPlan
from ..framework.registry import register_genre

BASS_REG = (0, 11)                            # arco_bass（shift=-12 → t=12..23）
CLUSTER_REG = (12, 35)                        # piano_cluster／sax_screech（ともに shift=0）
CLUSTER_OFFSETS = (0, 1, 2, -1, -2, 6, 7)

INITIAL_BPM = 96                              # tempo_choices の唯一の値。実テンポ推移は TEMPO_CURVES が決める
METER = Meter(steps=16, steps_per_beat=4)
MEASURES = 4
SECTIONS = ("movement_a", "movement_b", "climax", "movement_c")
INTENSITY = {"movement_a": 0.3, "movement_b": 0.6, "climax": 0.95, "movement_c": 0.2}

# 区間をまたいで滑らかに繋ぐテンポカーブ（start_bpm は直前の区間の end_bpm と一致させる）
TEMPO_CURVES: dict[str, tuple[tuple[int, int, int, int, str], ...]] = {
    "movement_a": ((96, 82, 0, 63, "ease_out"),),
    "movement_b": ((82, 126, 0, 63, "ease_in"),),
    "climax": ((126, 150, 0, 31, "ease_in"), (150, 126, 32, 63, "ease_out")),
    "movement_c": ((126, 70, 0, 63, "linear"),),
}
# 拡大後も全点が Fxx の範囲（32..255）に収まる開始 BPM だけを許す（クランプでカーブの形を崩さない）
_CURVE_POINTS = [b for curves in TEMPO_CURVES.values() for c in curves for b in c[:2]]
TEMPO_RANGE = (math.ceil(32 * INITIAL_BPM / min(_CURVE_POINTS)), math.floor(255 * INITIAL_BPM / max(_CURVE_POINTS)))

DENSITY = {"bass": 0.18, "piano": 0.25, "perc": 0.08}    # 楽器ごとの発音確率（1 step あたり。intensity 倍率を掛ける）
SAX_DENSITY_CLIMAX = 0.12


def _scaled(bpm: int, start_bpm: int) -> int:
    return round(bpm * start_bpm / INITIAL_BPM)


def _rubato_summary() -> str:
    seq = [INITIAL_BPM]
    for name in SECTIONS:
        for _s, end, *_ in TEMPO_CURVES[name]:
            seq.append(end)
    return "Rubato      : " + " -> ".join(f"x{b / INITIAL_BPM:.2f}" for b in seq) + " of start BPM (tempo curve)"


def _cluster_chord(root_pc: int, label: str, rng: random.Random) -> ChordDef:
    """root_pc を中心に隣接半音を2〜4個ランダムに選び、密集クラスターを作る。chord_tones は piano/sax 共有の
    CLUSTER_REG、bass は別途 BASS_REG に折り返す（楽器ごとに shift が異なり有効な音域が違うため）。"""
    offsets = rng.sample(CLUSTER_OFFSETS, k=rng.randint(2, 4))
    tones = sorted({fold_into_range(root_pc + o + 12 * 2, *CLUSTER_REG) for o in offsets})
    bass_note = fold_into_range(root_pc, *BASS_REG)
    return ChordDef(label=label, bass=bass_note, harmony=bass_note, chord_tones=tuple(tones),
                    scale_tones=tuple(tones), arp=None, explicit=True)


# ============================================================
# ジャンル内のジェネレータ（確率密度のテクスチャ）
# ============================================================

class ClusterBass(Generator):
    def measure(self, m: MeasureCtx) -> None:
        intensity = m.plan.intensity
        for step in range(m.m.steps):
            if m.rng.random() < DENSITY["bass"] * intensity:
                # chord_tones は CLUSTER_REG（piano/sax 用）の音域で arco_bass（shift=-12）には使えないので、
                # 常に chord.bass（BASS_REG に折り返し済み）を鳴らす。
                m.note(step, "arco_bass", m.m.chord.bass, vel=min(64, max(1, round(40 * intensity) + 10)))


class ClusterPiano(Generator):
    """区間のテンポカーブも書く（音を鳴らさない専用のパートを置くと lane を食うので、先頭のパートに同居させる）。"""

    def section(self, ctx: SectionCtx) -> None:
        for start_bpm, end_bpm, start_step, end_step, kind in TEMPO_CURVES[ctx.plan.name]:
            tempo_curve(ctx, _scaled(start_bpm, ctx.bpm), _scaled(end_bpm, ctx.bpm), start_step, end_step, kind)
        super().section(ctx)

    def measure(self, m: MeasureCtx) -> None:
        chord, intensity = m.m.chord, m.plan.intensity
        for step in range(m.m.steps):
            if m.rng.random() < DENSITY["piano"] * intensity:
                m.note(step, "piano_cluster", m.rng.choice(chord.chord_tones or (chord.harmony,)),
                       vel=min(64, max(1, round(45 * intensity) + 8)))


class ClusterSax(Generator):
    def measure(self, m: MeasureCtx) -> None:
        if m.plan.name != "climax":
            return
        chord = m.m.chord
        for step in range(m.m.steps):
            if m.rng.random() < SAX_DENSITY_CLIMAX:
                m.note(step, "sax_screech", m.rng.choice(chord.chord_tones or (chord.harmony,)), vel=54)


class CymbalSwells(Generator):
    def measure(self, m: MeasureCtx) -> None:
        intensity = m.plan.intensity
        for step in range(m.m.steps):
            if m.rng.random() < DENSITY["perc"] * intensity:
                m.note(step, "cymbal_swell", vel=max(1, round(50 * intensity)))


def _inst(key: str, gm: GmVoice) -> Instrument:
    return Instrument(patch=PRESETS[key], gm=gm)


@register_genre
class FreeJazzGenre(Genre):
    id = "free-jazz"
    category = "genre"
    display_name = "Free Jazz"
    description = "フリージャズ。トーンクラスター、確率密度のテクスチャ、ルバート（連続テンポ変化）"
    description_en = "Free jazz: tone clusters, probabilistic density textures, rubato (continuous tempo changes)"
    title = "Free Jazz"
    tempo_choices = (INITIAL_BPM,)
    tempo_range = TEMPO_RANGE

    instruments = {
        "piano_cluster": _inst("free_piano_cluster", GmVoice(program=0)),
        "arco_bass": _inst("free_arco_bass", GmVoice(program=43)),
        "sax_screech": _inst("free_sax_screech", GmVoice(program=66)),
        "cymbal_swell": _inst("free_cymbal_swell", GmVoice(program=119)),
    }
    harmony = None   # 手組みのクラスター。plan() を全面的に上書きする
    sections = {name: Section(meter=METER, measures=MEASURES, intensity=INTENSITY[name]) for name in SECTIONS}
    form = SECTIONS    # 通作形式。ループしない
    parts = (
        Part("piano", ClusterPiano(), pan=64),
        Part("bass", ClusterBass(), pan=192),
        Part("sax", ClusterSax(), pan=192),
        Part("perc", CymbalSwells(), pan=64),
    )
    mod_channels = {4: 1}

    def plan(self, rng: random.Random) -> SongPlan:
        scale = Scale(0, MODES["ionian"])
        sections = {}
        for name in SECTIONS:
            measures = []
            chords = [_cluster_chord(rng.randint(0, 11), f"{name[-1]}{i}", rng) for i in range(MEASURES)]
            for i, chord in enumerate(chords):
                measures.append(MeasurePlan(index=i, start=i * METER.steps, steps=METER.steps, chord=chord,
                                             quality="maj", chord_offset=0, next_chord=chords[(i + 1) % MEASURES]))
            sections[name] = SectionPlan(
                name=name, kind=name, meter=METER, measures=tuple(measures), intensity=INTENSITY[name],
                key_offset=0, tonic=0, scale=scale, parts=frozenset(p.name for p in self.parts), swing=None,
                section=self.sections[name], extra={})
        return SongPlan(bpm=INITIAL_BPM, key_pc=0, sections=sections, order=list(SECTIONS),
                        summary=[_rubato_summary()])
