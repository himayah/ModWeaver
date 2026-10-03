"""suspense-chase（旧 genres/suspense_chase.py の移植。FRAMEWORK_REDESIGN.md §15.4 のグループC）。

構成: intro → a1 → a2 → b → a1 → b → climax → outro。進行は A=pedal / B=tritone 固定（増 4 度の追走が主役）。
文法の核は「毎拍の心拍＋8 分連打の drone＋半音・増 4 度を混ぜた pizz オスティナート」と、silence run（無音）から
anvil への落差。旧版は A を2つの pattern（A1・A2）に分けていた（無音の位置・スタブの位置が違う）ので、新版も
``a1``・``a2`` の2つの区間（``kind="a"``）にする。無音・anvil・スタブの位置は ``plan()`` が決めて ``SectionPlan.extra`` に置く。
"""
from __future__ import annotations

import random

from ..core.composer import RhythmMotif, ScaleRules, ramp
from ..core.pitch import fold_into_range
from ..framework.context import Generator, MeasureCtx, SectionCtx
from ..framework.genre import Genre, Part, Section
from ..framework.plan import SongPlan
from ..framework.registry import register_genre
from ._suspense import (
    INSTRUMENTS, KEY_PC, LEAD_KIT, MEASURES, PAN_DRONE, PAN_LEAD, PAN_PULSE, PAN_TEXTURE, PIZZ_REG, PULSE_KIT,
    SHOCK_GUARD_ROWS, TEXTURE_KIT, anvil_clear_row, lead_generator, pizz_root_note, progression_summary,
    section_plan, strings_chord, swoosh_start_row, LEAD_REG,
)

RPM = 16                                   # steps per measure
OSTINATO_SHAPE = (0, 0, 1, 0, 0, 0, 6, 0)  # 半音・増 4 度を混ぜた音型（8 分音符 8 個分の根音からの半音差）
HEART_VOL, DUB_VOL = 56, 34
DRONE_VOLS = (52, 44)                      # 8 分連打の音量（交互）
STAB_VOL = 60
STAB_COUNT = 2
LEAD_RULES = ScaleRules(dissonance_weight=0.5, leap_probability=0.4, color_semitones=(1, 6))
LEAD_MOTIFS = (RhythmMotif((0, 3, 6, 10)), RhythmMotif((0, 2, 4, 8, 10, 12)))
CLIMAX_LEAD_REG = (30, 41)                 # climax の lead は高音域


def _ostinato_note(chord, offset: int) -> int:
    """PIZZ_REG 内の根音（bass の pitch class）に半音差を足し、音域へ折り返す。"""
    return fold_into_range(pizz_root_note(chord, chord.bass % 12) + offset, *PIZZ_REG)


def _draw_stabs(rng: random.Random, silent: int) -> dict[int, int]:
    """突発 pizz スタブの位置 {区間内 step: 根音からの半音差}。silence run と anvil の直前 8 step・余韻中には置かない。"""
    anvil_row = (silent + 1) * RPM
    quiet_from = silent * RPM + RPM // 2
    candidates = [
        m * RPM + r for m in range(4) for r in (6, 10, 14)
        if not (quiet_from <= m * RPM + r < anvil_row)
        and not (anvil_row - SHOCK_GUARD_ROWS <= m * RPM + r < anvil_row)
        and not (anvil_row <= m * RPM + r < anvil_row + 8)          # anvil の余韻中は避ける
    ]
    rows = sorted(rng.sample(candidates, STAB_COUNT))
    return {r: rng.choice((1, 6)) for r in rows}


def _pulse(m: MeasureCtx, start: int, end: int) -> None:
    """毎拍の心拍（vol 56）＋奇数拍に dub（step+2, vol 34）。``[start, end)`` の拍頭に置く。"""
    for r in range(start, end, 4):
        m.note(r, "heart", vel=HEART_VOL)
        if (r // 4) % 2 == 1 and r + 2 < end:
            m.note(r + 2, "heart", vel=DUB_VOL)


def _eighths(m: MeasureCtx, end: int, vols=DRONE_VOLS) -> None:
    """drone の 8 分連打（``[0, end)``）。音量は交互。``end < RPM``（silence run で早期に打ち切る）場合、本来 ``end`` 以降に
    来るはずだった次の 1 音を落とさず ``end - 1``（無音直前の step）へ引き寄せる。"""
    bass = m.m.chord.bass
    i = 0
    for r in range(0, RPM, 2):
        if r < end:
            m.note(r, "drone", bass, vel=vols[i % len(vols)])
            i += 1
        elif end < RPM:
            m.note(end - 1, "drone", bass, vel=vols[i % len(vols)])
            break


class ChasePulse(Generator):
    def measure(self, m: MeasureCtx) -> None:
        kind, i, ex = m.plan.kind, m.m.index, m.plan.extra
        if kind == "intro":
            if i >= 2:                                   # m2 から拍頭に heart（vol 36）
                for r in range(0, RPM, 4):
                    m.note(r, "heart", vel=36)
        elif kind == "a":
            silent = i == ex["dropout"]                  # この小節の後半（step 8–15）は全消音
            after = i == ex["anvil"]
            _pulse(m, anvil_clear_row(m) if after else 0, RPM // 2 if silent else RPM)
            if after:
                m.note(0, "anvil", vel=64)
        elif kind == "b":
            _pulse(m, 0, RPM)
        elif kind == "climax":
            m.note(0, "anvil", vel=64)                   # 各小節先頭の衝撃
            if m.is_last:                                # 最終小節: swoosh が区間の終端へ接続（心拍は止める）
                m.note(swoosh_start_row(m), "swoosh", vel=50)
            else:
                _pulse(m, anvil_clear_row(m), RPM)
        elif kind == "outro":
            if i == 0:
                m.note(0, "anvil", vel=64)
            hits = {(1, 0): 0, (1, 8): 1, (2, 4): 2, (3, 4): 3}      # step 16, 24, 36, 52 の heart（vol 40→14）
            for (mm, r), k in hits.items():
                if mm == i:
                    m.note(r, "heart", vel=ramp(40, 14, k, 4))


class ChaseDrone(Generator):
    def measure(self, m: MeasureCtx) -> None:
        kind, i, ex = m.plan.kind, m.m.index, m.plan.extra
        if kind == "a":
            silent = i == ex["dropout"]
            end = RPM // 2 if silent else RPM
            _eighths(m, end)
            if silent:
                m.off(RPM // 2, "drone")
        elif kind == "b":
            _eighths(m, RPM)
        elif kind == "climax":
            _eighths(m, RPM, vols=(52,))


class ChaseTexture(Generator):
    def measure(self, m: MeasureCtx) -> None:
        kind, i, ex = m.plan.kind, m.m.index, m.plan.extra
        chord = m.m.chord
        if kind == "intro":                              # root 固執の pizz オスティナート（区間全体で crescendo）
            note = _ostinato_note(chord, 0)
            for k, r in enumerate(range(0, RPM, 2)):
                m.note(r, "pizz", note, vel=ramp(16, 56, i * 8 + k, 32))
        elif kind == "a":
            end = RPM // 2 if i == ex["dropout"] else RPM
            for k, off in enumerate(OSTINATO_SHAPE):     # 音型は 8 分音符 8 個（= 1 小節）で 1 周
                r = k * 2
                if r < end:
                    m.note(r, "pizz", _ostinato_note(chord, off), vel=56 if r % 4 == 0 else 44)   # 拍頭アクセント
        elif kind == "b":
            strings_chord(m)                             # ostinato を退避し、持続和音（arp）へ
        elif kind == "climax":                           # pizz 16 分（毎 step）の crescendo
            note = _ostinato_note(chord, 0)
            for r in range(RPM):
                m.note(r, "pizz", note, vel=ramp(30, 60, i * RPM + r, 64))
        elif kind == "outro":
            if i == 0:
                m.note(0, "strings", chord.harmony, vel=20)
            elif i == 2:
                m.note(0, "strings", chord.harmony, vel=10)


class ChaseLead(Generator):
    def section(self, ctx: SectionCtx) -> None:
        if ctx.plan.kind in ("b", "climax"):
            reg = CLIMAX_LEAD_REG if ctx.plan.kind == "climax" else LEAD_REG
            ctx.state["gen"] = lead_generator(ctx.rng, LEAD_RULES, ctx.plan, register=reg)
            ctx.state["prev"] = None
        super().section(ctx)

    def measure(self, m: MeasureCtx) -> None:
        kind, i = m.plan.kind, m.m.index
        chord = m.m.chord
        if kind == "a":
            for row, off in m.plan.extra["stabs"].items():   # 突発スタブ
                if row // RPM == i:
                    note = fold_into_range(pizz_root_note(chord, chord.bass % 12) + off, *PIZZ_REG)
                    m.note(row % RPM, "pizz", note, vel=STAB_VOL)
        elif kind in ("b", "climax"):
            motif = LEAD_MOTIFS[m.rng.randrange(len(LEAD_MOTIFS))]
            events, m.state["prev"] = m.state["gen"].bar(motif, chord, m.state["prev"], rows=RPM)
            for e in events:
                m.note(e.row, "lead", e.note, vel=e.vol, dur=max(1, round(e.dur * 0.9)))


@register_genre
class SuspenseChaseGenre(Genre):
    id = "suspense-chase"
    category = "style"
    display_name = "Suspense Chase"
    description = "緊急脱出・追走。毎拍の心拍と 8 分連打、無音からの衝撃"
    description_en = "Emergency escape / pursuit: heartbeat on every beat, driving eighth notes, impacts out of silence"
    title = "Suspense Chase"
    tempo_choices = (138, 140, 142, 144, 146, 148)

    instruments = INSTRUMENTS
    harmony = None   # 和声は区間ごとに手組み（voice(arp=True)）。plan() を全面的に上書きする
    _FULL = frozenset({"pulse", "drone", "texture", "lead"})
    sections = {
        "intro": Section(measures=MEASURES, intensity=0.3, parts=frozenset({"pulse", "texture"})),
        "a1": Section(measures=MEASURES, intensity=0.7, parts=_FULL, kind="a"),
        "a2": Section(measures=MEASURES, intensity=0.7, parts=_FULL, kind="a"),
        "b": Section(measures=MEASURES, intensity=0.8, parts=_FULL),
        "climax": Section(measures=MEASURES, intensity=1.0, parts=frozenset({"pulse", "drone", "texture", "lead"})),
        "outro": Section(measures=MEASURES, intensity=0.1, parts=frozenset({"pulse", "texture"})),
    }
    form = ("intro", "a1", "a2", "b", "a1", "b", "climax", "outro")
    parts = (
        Part("pulse", ChasePulse(), pan=PAN_PULSE, kit=PULSE_KIT),
        Part("drone", ChaseDrone(), pan=PAN_DRONE),
        Part("texture", ChaseTexture(), pan=PAN_TEXTURE, kit=TEXTURE_KIT),
        Part("lead", ChaseLead(), pan=PAN_LEAD, kit=LEAD_KIT),
    )
    mod_channels = {4: 1}

    def plan(self, rng: random.Random) -> SongPlan:
        bpm = rng.choice(list(self.tempo_choices))

        def sec(name: str, prog: str, **extra):
            decl = self.sections[name]
            return section_plan(name, prog, decl, decl.parts, **extra)

        def a_section(name: str, silent: int):
            # a1 は m2、a2 は m1 の後半を無音にし、次の小節の頭で anvil を鳴らす
            return sec(name, "pedal", dropout=silent, anvil=silent + 1, stabs=_draw_stabs(rng, silent))

        sections = {
            "intro": sec("intro", "pedal"),
            "a1": a_section("a1", 2),
            "a2": a_section("a2", 1),
            "b": sec("b", "tritone"),
            "climax": sec("climax", "tritone"),
            "outro": sec("outro", "pedal"),
        }
        return SongPlan(bpm=bpm, key_pc=KEY_PC, sections=sections, order=list(self.form),
                        summary=[progression_summary("Theme A", "pedal"), progression_summary("Theme B", "tritone")])
