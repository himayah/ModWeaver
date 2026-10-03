"""maqam（旧 genres/maqam.py の移植。DESIGN.md §6 のグループC）。

maqam Rast（G を主音 qarar とする）。1小節 = 16 step = 4/4。usul（リズム周期）は maqsum（``DUM . TEK . . DUM TEK .``）。
和声は ``voice()`` を経由せず ``ChordDef`` を手組みする（``harmony=None``、``plan()`` を上書き）。

中立音程（中立3度 350 セント・中立7度 1050 セント）は、書かれた音高の**小数部**（``MicroScale.absolute_cents ÷ 100``）で
表す（gamelan と同じ）。旧版の ``oud_n3``・``oud_n7`` という finetune の派生楽器は不要になった（MOD では Realizer が
finetune の変種サンプルを作り、S3M・XM・IT は C5Speed・相対ノートで、MIDI はピッチベンドで出す）。
旧版は finetune の刻みを 7.8125 セントと誤っていたので、微分音の出音が最大 20 セント以上ずれていた（DESIGN_HISTORY.md §15）。
"""
from __future__ import annotations

import random
from typing import Optional

from ..core.model import ChordDef, GmVoice
from ..core.pitch import MODES, MicroScale, Scale, parse
from ..core.synth_presets import PRESETS
from ..framework.context import Generator, MeasureCtx
from ..framework.genre import Genre, Instrument, Kit, Part, Section
from ..framework.plan import MeasurePlan, Meter, SectionPlan, SongPlan
from ..framework.registry import register_genre

KEY_PC = 7                                    # G
QARAR_NOTE = parse("G-2")                     # 主音（qarar）を置く logical note
RAST_ON_G = MicroScale(tonic_pc=KEY_PC, degrees_cents=(0, 200, 350, 500, 700, 900, 1050))
#  度数: 主音(0) - 全音(200) - 中立3度(350) - 完全4度(500) - 完全5度(700) - 全音(900) - 中立7度(1050)
MELODY_DEGREE_RANGE = (-3, 9)                 # maqam_phrase が動く度数の範囲（t が 0..35 に収まる）
MEASURES = 4
METER = Meter(steps=16, steps_per_beat=4)

USUL_MAQSUM = {0: "dum", 4: "tek", 10: "dum", 12: "tek"}
QANUN_ARP_ROWS = (0, 2, 4, 6)


def degree_pitch(degree: int) -> float:
    """度数 -> 書かれた音高（小数。1 = 100 セント）。"""
    return RAST_ON_G.absolute_cents(degree, QARAR_NOTE) / 100.0


def _maqam_chord() -> ChordDef:
    """qarar/ghammaz と7度のジンス全音を手組みする（DESIGN.md §6.10）。"""
    scale_tones = tuple(round(degree_pitch(d)) for d in range(7))
    return ChordDef(label="Rast on G", bass=QARAR_NOTE, harmony=round(degree_pitch(4)), chord_tones=(),
                    scale_tones=scale_tones, arp=None, explicit=True)


def maqam_phrase(rng: random.Random, prev_degree: Optional[int], n_events: int) -> tuple[list[int], int]:
    """順次進行主体、まれに4度・5度の跳躍を混ぜる（DESIGN.md §6.10）。度数列と終端度数を返す。"""
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


# ============================================================
# ジャンル内のジェネレータ
# ============================================================

class Usul(Generator):
    def measure(self, m: MeasureCtx) -> None:
        for step, key in USUL_MAQSUM.items():
            m.note(step, key, vel=54 if key == "dum" else 42)


class OudMelody(Generator):
    """taqsim は区間の各小節に 2〜4 音（自由リズム風）、ostinato_b は固定の4音。coda は最終小節の qarar だけ。"""

    def section(self, ctx) -> None:
        ctx.state["prev"] = None
        super().section(ctx)

    def measure(self, m: MeasureCtx) -> None:
        kind = m.plan.kind
        if kind == "coda":
            if m.is_last:
                m.note(0, "oud", m.m.chord.bass, vel=44)
            return
        if kind == "taqsim":
            steps = sorted(m.rng.sample(range(16), m.rng.choice((2, 3, 4))))
            vol = 46
        else:
            steps, vol = (2, 6, 9, 14), 48
        degrees, m.state["prev"] = maqam_phrase(m.rng, m.state["prev"], len(steps))
        for step, degree in zip(steps, degrees):
            m.note(step, "oud", degree_pitch(degree), vel=vol)


class QanunArp(Generator):
    """ジンスを上行分散和音として弾く（度数 0,1,2,3）。coda は最終小節の qarar だけ。"""

    def measure(self, m: MeasureCtx) -> None:
        if m.plan.kind == "coda":
            if m.is_last:
                m.note(0, "qanun", m.m.chord.bass, vel=34)
            return
        for i, step in enumerate(QANUN_ARP_ROWS):
            m.note(step, "qanun", degree_pitch(i), vel=38)


class NayDrone(Generator):
    def measure(self, m: MeasureCtx) -> None:
        if m.plan.kind == "coda":
            if m.is_last:
                m.note(0, "nay", m.m.chord.harmony, vel=30)
        elif m.m.index == 0:
            m.note(0, "nay", m.m.chord.bass, vel=36)


def _inst(key: str, gm: GmVoice) -> Instrument:
    return Instrument(patch=PRESETS[key], gm=gm)


@register_genre
class MaqamGenre(Genre):
    id = "maqam"
    category = "genre"
    display_name = "Maqam Rast"
    description = "中東マカーム（Rast on G）。ウードのタクシームとマクスーム usul、中立音程"
    description_en = "Middle Eastern maqam (Rast on G): oud taqsim and maqsum usul with neutral intervals"
    title = "Maqam Rast"
    tempo_choices = (84, 88, 92, 96)

    instruments = {
        "dum": _inst("maqam_daf_dum", GmVoice(drum_note=64)),
        "tek": _inst("maqam_daf_tek", GmVoice(drum_note=63)),
        "oud": _inst("maqam_oud", GmVoice(program=24)),
        "nay": _inst("maqam_nay", GmVoice(program=77)),
        "qanun": _inst("maqam_qanun", GmVoice(program=15)),
    }
    harmony = None   # 手組みの Rast。転調しない。plan() を全面的に上書きする
    sections = {
        "taqsim": Section(measures=MEASURES, intensity=0.3, parts=frozenset({"oud"})),
        "ostinato_a": Section(measures=MEASURES, intensity=0.6, parts=frozenset({"perc", "qanun", "nay"})),
        "ostinato_b": Section(measures=MEASURES, intensity=0.85, parts=frozenset({"perc", "qanun", "nay", "oud"})),
        "coda": Section(measures=MEASURES, intensity=1.0, parts=frozenset({"oud", "qanun", "nay"})),
    }
    form = ("taqsim", "ostinato_a", "ostinato_b", "taqsim", "ostinato_a", "coda")
    parts = (
        Part("perc", Usul(), pan=128,
             kit=Kit(groups=(("perc", ("dum", "tek")),), priority={"dum": 2, "tek": 1})),
        Part("oud", OudMelody(), pan=64),
        Part("nay", NayDrone(), pan=192),
        Part("qanun", QanunArp(), pan=192),
    )
    mod_channels = {4: 1}

    def plan(self, rng: random.Random) -> SongPlan:
        bpm = rng.choice(list(self.tempo_choices))
        chord = _maqam_chord()
        scale = Scale(KEY_PC, MODES["ionian"])
        sections = {}
        for name in dict.fromkeys(self.form):
            sec = self.sections[name]
            measures = tuple(
                MeasurePlan(index=i, start=i * METER.steps, steps=METER.steps, chord=chord, quality="maj",
                            chord_offset=i, next_chord=chord) for i in range(sec.measures))
            sections[name] = SectionPlan(
                name=name, kind=name, meter=METER, measures=measures, intensity=sec.intensity, key_offset=0,
                tonic=KEY_PC, scale=scale, parts=sec.parts, swing=None, section=sec, extra={})
        return SongPlan(bpm=bpm, key_pc=KEY_PC, sections=sections, order=list(self.form),
                        summary=[f"Maqam            : Rast on G -> {chord.label}"])
