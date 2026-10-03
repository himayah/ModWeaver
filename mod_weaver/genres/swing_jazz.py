"""swing-jazz（旧 genres/swing_jazz.py の移植。FRAMEWORK_REDESIGN.md §15.4 のグループC）。

1小節 = 8 step = 4/4（1 step = 8分音符、``Meter(8, 2)``）。``swing=Swing(14, 10)``（14:10 = 1.4:1、合計 24 tick = 1拍）。
Bb のリズムチェンジ形式 AABA（8小節ずつ）で、Head → Solo → Head-out（タグエンディング）と進む。進行は "Rhythm Changes" の簡略形
（A section 7小節目の Cm7/F7 半々の turnaround は Cm7 のみに簡略化）。

ウォーキングベースは次の和音の根音へ向かって終わる（``MeasurePlan.next_chord``。旧版は現在の和音の根音で終わっていた）。
旧版の「intro でドラムを休む」「row 0 に空きチャンネルを残すためコンピングを裏拍に置く」工夫のうち、前者は音楽上の意味
（リズム隊だけのヴァンプ）なので残し、後者は Realizer の責任なので外した（コンピングの位置は音楽上そのまま）。
"""
from __future__ import annotations

import random

from ..core.composer import MelodyGenerator, RhythmMotif, ScaleRules
from ..core.harmony import Registers
from ..core.model import ChordSpec, GmVoice
from ..core.pitch import MODES, Scale, fold_into_range
from ..core.synth_presets import PRESETS
from ..framework.context import Generator, MeasureCtx, SectionCtx
from ..framework.genre import Genre, Harmony, Instrument, Kit, Part, Section
from ..framework.plan import Meter, SongPlan, Swing, default_plan
from ..framework.registry import register_genre
from ..framework.score import Arpeggio, Retrig

KEY_PC = 10                                   # Bb
BASS_REG = (0, 11)                            # walk_bass（shift=-12 → t=12..23）
HARM_REG = (12, 23)                           # piano_comp（アルペジオ最大+7でも t<=30）
MELODY_REG = (24, 35)                         # sax_lead
MODE_BY_QUALITY = {"dom7": "mixolydian", "m7": "dorian"}
METER = Meter(steps=8, steps_per_beat=2)
SWING = Swing(long=14, short=10)

HEAD_RULES = ScaleRules(step_choices=(-1, 1, -2, 2), leap_probability=0.30, leap_semitones=(3, 4, 5, 7),
                         leap_recovery=True, dissonance_weight=0.05)
SOLO_RULES = ScaleRules(step_choices=(-1, 1, -2, 2), leap_probability=0.45, leap_semitones=(3, 4, 5, 7, 8),
                         leap_recovery=True, dissonance_weight=0.12)
WALK_RULES = ScaleRules(step_choices=(-1, 1, -2, 2), leap_probability=0.35, leap_semitones=(3, 4, 5, 7),
                         leap_recovery=True, dissonance_weight=0.0, strong_nearest_prob=0.6)

PROGRESSION_TITLES = {"a": "Rhythm Changes A", "b": "Rhythm Changes Bridge"}
# (root, quality) — Bb（KEY_PC）基準の半音オフセット。1小節 1和音
PROGRESSIONS = {
    "a": (ChordSpec(0, "maj"), ChordSpec(9, "dom7"), ChordSpec(2, "m7"), ChordSpec(7, "dom7"),
          ChordSpec(0, "maj"), ChordSpec(9, "dom7"), ChordSpec(2, "m7"), ChordSpec(0, "maj")),
    "b": (ChordSpec(4, "dom7"), ChordSpec(4, "dom7"), ChordSpec(9, "dom7"), ChordSpec(9, "dom7"),
          ChordSpec(2, "dom7"), ChordSpec(2, "dom7"), ChordSpec(7, "dom7"), ChordSpec(7, "dom7")),
}

RIDE_ROWS = (0, 2, 3, 4, 6, 7)          # "ding-ding-a-ding"
RIDE_STRONG_ROWS = (0, 4)
BACKBEAT_ROWS = (2, 6)
COMP_A = (1, 3)
COMP_B = (1, 5)

SWING_MOTIFS = (RhythmMotif((0, 2, 4, 6)), RhythmMotif((0, 1, 3, 5, 6)), RhythmMotif((0, 2, 3, 5, 6)),
                RhythmMotif((0, 1, 2, 4, 5, 7)))
WALK_MOTIF = RhythmMotif((0, 2, 4, 6))
HOLD_MOTIF = RhythmMotif((0,))
SAX_RETRIG_TICKS = 5        # 裏拍（short=10 tick）の中ほどで1回だけ再発音する装飾


def _arp(chord) -> tuple:
    return (Arpeggio(chord.arp >> 4, chord.arp & 0xF),) if chord.arp else ()


# ============================================================
# ジャンル内のジェネレータ
# ============================================================

class SwingDrums(Generator):
    """ライド（強拍は vol 58、弱拍はサンプル既定音量）とブラシのバックビート（Kit の優先度でライドに勝つ）。tag は強いライド1発。"""

    def measure(self, m: MeasureCtx) -> None:
        if m.plan.kind == "out" and m.is_last:
            m.note(0, "ride", vel=64)
            return
        for r in RIDE_ROWS:
            m.note(r, "ride", vel=58 if r in RIDE_STRONG_ROWS else None)
        for r in BACKBEAT_ROWS:
            m.note(r, "brush", vel=40)


class WalkingBass(Generator):
    def section(self, ctx: SectionCtx) -> None:
        ctx.state["gen"] = MelodyGenerator(WALK_RULES, BASS_REG, ctx.plan.scale, ctx.rng, base_vol=52, beat_rows=2)
        ctx.state["prev"] = None
        super().section(ctx)

    def measure(self, m: MeasureCtx) -> None:
        chord = m.m.chord
        if m.plan.kind == "intro":
            m.note(0, "bass", chord.bass, vel=46)
            m.note(4, "bass", fold_into_range(chord.bass + 7, *BASS_REG), vel=42)
            return
        if m.plan.kind == "out" and m.is_last:
            m.note(0, "bass", chord.bass, vel=60)
            return
        target = fold_into_range(m.m.next_chord.bass, *BASS_REG)     # 次の和音の根音へ向かう
        events, m.state["prev"] = m.state["gen"].bar(WALK_MOTIF, chord, m.state["prev"], cadence=True,
                                                      cadence_target=target, rows=8, base_vol=52)
        for e in events:
            m.note(e.row, "bass", e.note, vel=e.vol, dur=max(1, round(e.dur * 0.9)))


class CharlestonComp(Generator):
    """2種のシンコペ・コンピング（どちらも裏拍）をランダムに選び刺す。intensity>=0.75 は arp 付き（既定音量）、それ未満は単音。"""

    def measure(self, m: MeasureCtx) -> None:
        chord = m.m.chord
        if m.plan.kind == "intro":
            if m.m.index % 2 == 0:
                m.note(0, "piano", chord.harmony, arts=_arp(chord))
            return
        if m.plan.kind == "out" and m.is_last:
            m.note(0, "piano", chord.harmony, arts=_arp(chord))
            return
        rows = COMP_A if m.rng.random() < 0.5 else COMP_B
        for r in rows:
            if m.plan.intensity >= 0.75:
                m.note(r, "piano", chord.harmony, arts=_arp(chord))
            else:
                m.note(r, "piano", chord.harmony, vel=34)


class SaxLead(Generator):
    def section(self, ctx: SectionCtx) -> None:
        rules = SOLO_RULES if ctx.plan.kind in ("solo_a", "solo_b") else HEAD_RULES
        ctx.state["gen"] = MelodyGenerator(rules, MELODY_REG, ctx.plan.scale, ctx.rng, base_vol=48, beat_rows=2)
        ctx.state["prev"] = None
        super().section(ctx)

    def measure(self, m: MeasureCtx) -> None:
        chord, kind = m.m.chord, m.plan.kind
        gate = 0.75 if kind in ("solo_a", "solo_b") else 0.85
        if m.is_last:       # フレーズ末の終止（out の最終小節はタグ。ゲートは既定）
            events, m.state["prev"] = m.state["gen"].bar(HOLD_MOTIF, chord, m.state["prev"], cadence=True,
                                                          cadence_target=chord.chord_tones[0], rows=8, base_vol=54)
            if kind == "out":
                gate = 0.85
        else:
            motif = m.rng.choice(SWING_MOTIFS)
            events, m.state["prev"] = m.state["gen"].bar(motif, chord, m.state["prev"], rows=8, base_vol=50)
        decorate = bool(events) and m.rng.random() < 0.25 and events[-1].row % 2 == 1   # 裏拍の onset にだけ装飾
        for i, e in enumerate(events):
            arts = (Retrig(SAX_RETRIG_TICKS),) if decorate and i == len(events) - 1 else ()
            m.note(e.row, "sax", e.note, vel=e.vol, dur=max(1, round(e.dur * gate)), arts=arts)


def _inst(key: str, gm: GmVoice) -> Instrument:
    return Instrument(patch=PRESETS[key], gm=gm)


@register_genre
class SwingJazzGenre(Genre):
    id = "swing-jazz"
    category = "genre"
    display_name = "Swing Jazz"
    description = "スウィング・ジャズ。ライド＋ウォーキングベース＋ピアノコンピング、Bbリズムチェンジ AABA"
    description_en = "Swing jazz: ride cymbal, walking bass and piano comping over Bb rhythm changes (AABA)"
    title = "Swing Jazz"
    tempo_choices = (152, 156, 160, 164, 168)
    swing = SWING

    instruments = {
        "ride": _inst("swing_ride", GmVoice(drum_note=51)),
        "brush": _inst("swing_brush_snare", GmVoice(drum_note=38)),
        "bass": _inst("swing_walk_bass", GmVoice(program=32)),
        "piano": _inst("swing_piano_comp", GmVoice(program=0)),
        "sax": _inst("swing_sax_lead", GmVoice(program=65)),
    }
    harmony = Harmony(keys=(KEY_PC,), mode="ionian", mode_by_quality=MODE_BY_QUALITY,
                       registers=Registers(bass=BASS_REG, harmony=HARM_REG, melody=MELODY_REG),
                       progressions=(("a", PROGRESSIONS["a"]), ("b", PROGRESSIONS["b"])), fixed=True, arp=True)
    sections = {
        "intro": Section(prog=0, measures=8, meter=METER, intensity=0.4, parts=frozenset({"bass", "piano"})),
        "a": Section(prog=0, measures=8, meter=METER, intensity=0.70),
        "b": Section(prog=1, measures=8, meter=METER, intensity=0.65),
        "solo_a": Section(prog=0, measures=8, meter=METER, intensity=0.85),
        "solo_b": Section(prog=1, measures=8, meter=METER, intensity=0.80),
        "out": Section(prog=0, measures=8, meter=METER, intensity=1.0),
    }
    form = ("intro", "a", "a", "b", "a", "solo_a", "solo_a", "solo_b", "solo_a", "a", "a", "b", "out")
    parts = (
        Part("drums", SwingDrums(), pan=128,
             kit=Kit(groups=(("drums", ("ride", "brush")),), priority={"brush": 2, "ride": 1})),
        Part("bass", WalkingBass(), pan=96),
        Part("piano", CharlestonComp(), pan=160),
        Part("sax", SaxLead(), pan=128),
    )
    mod_channels = {4: 1}

    def plan(self, rng: random.Random) -> SongPlan:
        base = default_plan(self, rng)
        base.summary = [
            f"{label:<18}: {PROGRESSION_TITLES[name]} -> "
            + " - ".join(mp.chord.label for mp in base.sections[name].measures)
            for label, name in (("A section", "a"), ("Bridge", "b"))]
        return base
