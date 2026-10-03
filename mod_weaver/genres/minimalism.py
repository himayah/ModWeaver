"""minimalism（旧 genres/minimalism.py の移植。DESIGN.md §6 のグループC）。

4つのパートがそれぞれ固定の周期（16/12/8/6 step）で決まった音型を反復し、piano だけが区間（＝位相）ごとに
参照位置を1 step ずつ右へずらす（ライヒの "Piano Phase" 的な発想）。1区間 = 1小節 = LCM(16,12,8,6) = 48 step、
区間は 16 個（``phase0``〜``phase15``）。和声は動かさず、乱数は使わない（決定論的な反復が本質）。
和声が無い（``harmony=None``）ので ``plan()`` を上書きして区間を組む。
"""
from __future__ import annotations

import random
from typing import Optional

from ..core.model import ChordDef, GmVoice
from ..core.pitch import MODES, Scale
from ..core.structure import polymetric_row
from ..core.synth_presets import PRESETS
from ..framework.context import Generator, MeasureCtx
from ..framework.genre import Genre, Instrument, Part, Section
from ..framework.plan import MeasurePlan, Meter, SectionPlan, SongPlan
from ..framework.registry import register_genre

CYCLE_PIANO, CYCLE_MARIMBA, CYCLE_VIBES, CYCLE_WOOD = 16, 12, 8, 6
LCM_STEPS = 48
N_PHASES = CYCLE_PIANO            # 16段階で piano の周期をちょうど1周する
METER = Meter(steps=LCM_STEPS, steps_per_beat=4)

# 固定音型（step -> (logical note or None, vol)）。woodblock は row 0 を避ける（旧版の「row 0 に空きを残す契約」だが、
# 1 step 目の弱いアクセントは音楽上の意味もあるので残す。DESIGN.md §6.14）。
PIANO_PATTERN: dict[int, tuple[Optional[int], int]] = {
    0: (24, 44), 2: (28, 40), 4: (31, 42), 6: (28, 38),
    8: (24, 44), 10: (28, 40), 12: (31, 42), 14: (28, 38),
}
MARIMBA_PATTERN: dict[int, tuple[Optional[int], int]] = {0: (19, 46), 3: (24, 42), 5: (26, 44), 8: (21, 40)}
VIBES_PATTERN: dict[int, tuple[Optional[int], int]] = {0: (24, 40), 3: (28, 38), 6: (21, 42)}
WOOD_PATTERN: dict[int, tuple[Optional[int], int]] = {1: (None, 50)}

STATIC_CHORD = ChordDef(
    label="C pentatonic", bass=12, harmony=24,
    chord_tones=(24, 26, 28, 31, 33), scale_tones=(24, 26, 28, 31, 33), arp=None, explicit=True,
)


class Cycle(Generator):
    """固定周期の音型を反復する。``shifted`` なら区間の番号（位相）だけ参照位置を右へずらす。"""

    def __init__(self, inst: str, cycle: int, pattern: dict[int, tuple[Optional[int], int]],
                 shifted: bool = False) -> None:
        self.inst = inst
        self.cycle = cycle
        self.pattern = pattern
        self.shifted = shifted

    def measure(self, m: MeasureCtx) -> None:
        shift = int(m.plan.name.removeprefix("phase")) if self.shifted else 0
        for step in range(m.m.steps):
            hit = self.pattern.get(polymetric_row(step - shift, self.cycle))
            if hit is None:
                continue
            note, vol = hit
            m.note(step, self.inst, note, vel=vol)


def _inst(key: str, gm: GmVoice) -> Instrument:
    return Instrument(patch=PRESETS[key], gm=gm)


@register_genre
class MinimalismGenre(Genre):
    id = "minimalism"
    category = "genre"
    display_name = "Minimalism"
    description = "ミニマル／フェーズ音楽。16/12/8/6row周期の4パートが少しずつズレて→揃って戻る"
    description_en = "Minimal / phase music: four parts with 16/12/8/6-row cycles drift apart and realign"
    title = "Phase Process"
    tempo_choices = (108, 112, 116, 120)

    instruments = {
        "piano_pulse": _inst("min_piano_pulse", GmVoice(program=0)),
        "marimba": _inst("min_marimba", GmVoice(program=12)),
        "vibraphone": _inst("min_vibraphone", GmVoice(program=11)),
        "woodblock": _inst("min_woodblock", GmVoice(drum_note=76)),
    }
    harmony = None   # 和声は動かさない。plan() を全面的に上書きする（march・nostalgic と同じ）
    sections = {f"phase{i}": Section(meter=METER, measures=1, intensity=0.6) for i in range(N_PHASES)}
    form = tuple(f"phase{i}" for i in range(N_PHASES))
    parts = (
        Part("piano", Cycle("piano_pulse", CYCLE_PIANO, PIANO_PATTERN, shifted=True), pan=64),
        Part("marimba", Cycle("marimba", CYCLE_MARIMBA, MARIMBA_PATTERN), pan=192),
        Part("vibes", Cycle("vibraphone", CYCLE_VIBES, VIBES_PATTERN), pan=192),
        Part("wood", Cycle("woodblock", CYCLE_WOOD, WOOD_PATTERN), pan=64),
    )
    mod_channels = {4: 1}

    def plan(self, rng: random.Random) -> SongPlan:
        bpm = rng.choice(list(self.tempo_choices))
        scale = Scale(0, MODES["ionian"])
        sections = {}
        for name in self.form:
            m = MeasurePlan(index=0, start=0, steps=LCM_STEPS, chord=STATIC_CHORD, quality="maj", chord_offset=0,
                            next_chord=STATIC_CHORD)
            sections[name] = SectionPlan(
                name=name, kind=name, meter=METER, measures=(m,), intensity=0.6, key_offset=0, tonic=0, scale=scale,
                parts=frozenset(p.name for p in self.parts), swing=None, section=self.sections[name], extra={})
        summary = [f"Phase process      : {N_PHASES} stages, cycles {CYCLE_PIANO}/{CYCLE_MARIMBA}/"
                   f"{CYCLE_VIBES}/{CYCLE_WOOD} row (LCM={LCM_STEPS})"]
        return SongPlan(bpm=bpm, key_pc=0, sections=sections, order=list(self.form), summary=summary)
