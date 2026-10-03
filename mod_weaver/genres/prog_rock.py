"""prog-rock（旧 genres/prog_rock.py の移植。FRAMEWORK_REDESIGN.md §15.4 のグループC）。

主リフの拍子サイクルは 7/8 + 7/8 + 5/8（16分格子で 14+14+10 = 38 step の3小節）。E aeolian のモーダルなリフに対し、
``chorus`` だけ 4/4（16 step × 4 小節）へ戻り「変拍子↔直進」の対比を作る。小節ごとの step 数は ``Section.measure_steps``、
リフの動機は ``m.steps`` で引く。
"""
from __future__ import annotations

import dataclasses

from ..core.composer import MelodyGenerator, RhythmMotif, ScaleRules
from ..core.harmony import Registers
from ..core.model import ChordSpec, GmVoice
from ..core.synth import OneShot
from ..core.synth_presets import PRESETS
from ..framework.context import Generator, MeasureCtx, SectionCtx
from ..framework.genre import Genre, Harmony, Instrument, Kit, Part, Section
from ..framework.registry import register_genre

KEY_PC = 4                                    # E
BASS_REG = (0, 11)                            # bass_dist（shift=-12 → t=12..23）
GTR_REG = (12, 23)                            # gtr_power の根音（chord.harmony）
LEAD_REG = (24, 35)                           # lead_gtr（chorus 専用）

I_CHORD = ChordSpec(0, "min", label="i")         # Em
BVII_CHORD = ChordSpec(10, "maj", label="bVII")  # D
BVI_CHORD = ChordSpec(8, "maj", label="bVI")     # C

LEAD_RULES = ScaleRules(step_choices=(-1, 1, -2, 2), leap_probability=0.30, leap_semitones=(3, 5, 7),
                         leap_recovery=True, dissonance_weight=0.05)
RIFF_MOTIFS = {
    14: RhythmMotif((0, 2, 4, 6, 8, 10, 12)),   # 7/8（7 eighth）
    10: RhythmMotif((0, 2, 4, 6, 8)),           # 5/8（5 eighth）
}
LEAD_MOTIFS = (
    RhythmMotif((0, 4, 8, 12)),
    RhythmMotif((0, 3, 4, 7, 8, 11, 12, 15)),
    RhythmMotif((0, 4, 6, 8, 12, 14)),
)

# 進行（0: リフ i - bVII - bVI、1: ブレイクダウン bVI と i を交互に、2: コーラス i - bVII - bVI - bVII）
PROGRESSIONS = (
    ("riff", (I_CHORD, BVII_CHORD, BVI_CHORD)),
    ("breakdown", (BVI_CHORD, I_CHORD, BVI_CHORD, I_CHORD, BVI_CHORD, I_CHORD)),
    ("chorus", (I_CHORD, BVII_CHORD, BVI_CHORD, BVII_CHORD)),
)
RIFF_STEPS = (14, 14, 10)      # 7/8 + 7/8 + 5/8
BREAKDOWN_STEPS = (10,) * 6    # 5/8 ×6
CHORUS_STEPS = (16,) * 4       # 4/4 ×4
BAND = frozenset({"drums", "bass", "gtr"})


# ============================================================
# ジャンル内のジェネレータ
# ============================================================

class ProgDrums(Generator):
    def measure(self, m: MeasureCtx) -> None:
        if m.plan.kind == "chorus":              # 4/4 の直進ロック・ビート
            for step in (0, 8):
                m.note(step, "kick", vel=58)
            for step in (4, 12):
                m.note(step, "snare", vel=52)
        else:                                    # リフの各 eighth にキック、真ん中（偶数 step）にスネア
            for step in RIFF_MOTIFS[m.m.steps].rows:
                m.note(step, "kick", vel=56)
            mid = m.m.steps // 2
            m.note(mid - mid % 2, "snare", vel=50)
        if m.m.index == 0:
            m.note(0, "crash", vel=64)           # Kit の優先度でキックに勝つ


class ProgGuitar(Generator):
    def measure(self, m: MeasureCtx) -> None:
        for step in RIFF_MOTIFS[m.m.steps].rows:
            m.note(step, "gtr", m.m.chord.harmony, vel=60 if step == 0 else 46)


class ProgBass(Generator):
    def measure(self, m: MeasureCtx) -> None:
        chord = m.m.chord
        if m.plan.kind == "chorus":
            for step in (0, 4, 8, 12):
                m.note(step, "bass", chord.bass, vel=50)
            return
        for step in RIFF_MOTIFS[m.m.steps].rows:
            m.note(step, "bass", chord.bass, vel=54 if step == 0 else 42)


class ChorusLead(Generator):
    """4/4 の直進コーラスに載るリードギター（LEAD_MOTIFS、標準16分格子）。"""

    def section(self, ctx: SectionCtx) -> None:
        ctx.state["gen"] = MelodyGenerator(LEAD_RULES, LEAD_REG, ctx.plan.scale, ctx.rng, base_vol=52)
        ctx.state["prev"] = None
        super().section(ctx)

    def measure(self, m: MeasureCtx) -> None:
        motif = m.rng.choice(LEAD_MOTIFS)
        events, m.state["prev"] = m.state["gen"].bar(motif, m.m.chord, m.state["prev"], rows=16, base_vol=52,
                                                      cadence=m.is_last)
        for e in events:
            m.note(e.row, "lead", e.note, vel=e.vol, dur=max(1, round(e.dur * 0.85)))


def _inst(key: str, gm: GmVoice, **changes) -> Instrument:
    patch = PRESETS[key]
    if changes:
        patch = dataclasses.replace(patch, **changes)
    return Instrument(patch=patch, gm=gm)


@register_genre
class ProgRockGenre(Genre):
    id = "prog-rock"
    category = "genre"
    display_name = "Prog Rock"
    description = "変拍子プログレ／マスロック。7/8+7/8+5/8 のリフ、4/4 のコーラスとの対比"
    description_en = "Odd-meter prog / math rock: a 7/8+7/8+5/8 riff contrasted with a 4/4 chorus"
    title = "Prog Rock"
    tempo_choices = (132, 136, 140, 144, 148)

    instruments = {
        "kick": _inst("prog_kick", GmVoice(drum_note=36)),
        "snare": _inst("prog_snare", GmVoice(drum_note=38)),
        "crash": _inst("march_crash_cymbal", GmVoice(drum_note=49), finish=OneShot(0.6)),   # march の crash を短縮
        "bass": _inst("prog_bass_dist", GmVoice(program=34)),
        "gtr": _inst("prog_gtr_power", GmVoice(program=30)),
        "lead": _inst("prog_lead_gtr", GmVoice(program=29)),
    }
    harmony = Harmony(keys=(KEY_PC,), mode="aeolian", progressions=PROGRESSIONS, fixed=True,
                       registers=Registers(bass=BASS_REG, harmony=GTR_REG, melody=LEAD_REG))
    sections = {
        "intro": Section(prog=0, measure_steps=RIFF_STEPS, intensity=0.5, parts=frozenset({"bass", "gtr"})),
        "verse": Section(prog=0, measure_steps=RIFF_STEPS, intensity=0.8, parts=BAND),
        "chorus": Section(prog=2, measure_steps=CHORUS_STEPS, intensity=0.9, parts=frozenset({"drums", "bass", "lead"})),
        "breakdown": Section(prog=1, measure_steps=BREAKDOWN_STEPS, intensity=0.6, parts=BAND),
        "outro": Section(prog=0, measure_steps=RIFF_STEPS, intensity=0.4, parts=frozenset({"bass", "gtr"})),
    }
    form = ("intro", "verse", "verse", "chorus", "verse", "breakdown", "chorus", "outro")
    parts = (
        Part("drums", ProgDrums(), pan=128,
             kit=Kit(groups=(("drums", ("kick", "snare", "crash")),), priority={"crash": 3, "snare": 2, "kick": 1})),
        Part("bass", ProgBass(), pan=128),
        Part("gtr", ProgGuitar(), pan=96),
        Part("lead", ChorusLead(), pan=176),
    )
    mod_channels = {4: 1}
