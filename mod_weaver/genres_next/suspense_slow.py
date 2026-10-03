"""suspense-slow（旧 genres/suspense_slow.py の移植。FRAMEWORK_REDESIGN.md §15.4 のグループC）。

構成: hush → pedal → phrygian → pedal → shock → aftermath。文法の核は「心拍」「無音→突発アクセント（anvil）」
「ペダルの持続音＋アルペジオ弦」。dropout・anvil・スタブの位置は ``plan()`` が決めて ``SectionPlan.extra`` に置き、
各パートのジェネレータが読む。持続音（drone・strings・lead）を止める無音は、それぞれの持ち主のパートが ``off`` を書く。
"""
from __future__ import annotations

import random

from ..core.composer import RhythmMotif, ScaleRules, ramp
from ..framework.context import Generator, MeasureCtx, SectionCtx
from ..framework.genre import Genre, Part, Section
from ..framework.plan import SongPlan
from ..framework.registry import register_genre
from ..framework.score import Glide, Vibrato
from ._suspense import (
    INSTRUMENTS, KEY_PC, LEAD_KIT, MEASURES, PAN_DRONE, PAN_LEAD, PAN_PULSE, PAN_TEXTURE, PULSE_KIT,
    SHOCK_GUARD_ROWS, TEXTURE_KIT, anvil_clear_row, heartbeat, lead_generator, pizz_root_note, progression_summary,
    section_plan, strings_chord, swoosh_start_row,
)

GLIDE_PARAM = 0x0A          # lead の 3xx（ポルタメント）速度
VIBRATO_PARAM = 0x46        # lead の 4xy（ビブラート）
STAB_ROW = 40               # pedal 区間の突発 pizz スタブの位置（m2 step 8）
STEPS = 16


class SlowPulse(Generator):
    def measure(self, m: MeasureCtx) -> None:
        kind, i, ex = m.plan.kind, m.m.index, m.plan.extra
        if kind == "hush":
            if i >= 2:                                   # m2 から心拍（vol 26→40）
                for b in range(4):
                    lub = ramp(26, 40, (i - 2) * 4 + b, 8)
                    heartbeat(m, range(b * 4, b * 4 + 1), lub, round(lub * 0.7))
        elif kind == "pedal":
            if i != ex["dropout"]:                       # 心拍・持続音が途切れる（無音）
                first = anvil_clear_row(m) if i == ex["anvil"] else 0   # anvil の余韻が切れないよう心拍を遅らせる
                heartbeat(m, range(first, STEPS, 4), 38, 26)
            if i == ex["anvil"]:                         # dropout 直後の衝撃
                m.note(0, "anvil", vel=64)
        elif kind == "phrygian":
            heartbeat(m, range(0, STEPS, 4), 40, 28)
        elif kind == "shock":
            if i == 0:                                   # 心拍加速（vol 40→56、毎拍）
                for b in range(4):
                    lub = ramp(40, 56, b, 4)
                    heartbeat(m, range(b * 4, b * 4 + 1), lub, lub - 12)
            elif i == 2:                                 # 衝撃の直前に終わる swoosh
                m.note(swoosh_start_row(m), "swoosh", vel=50)
            elif i == 3:
                m.note(0, "anvil", vel=64)
        elif kind == "aftermath":
            rows = (0, 8) if i < 3 else (0,)             # 心拍は 2 拍ごと。最終小節は step 0 の lub のみ
            for k, r in enumerate(rows):
                lub = ramp(30, 10, i * 2 + k, 7)
                m.note(r, "heart", vel=lub)
                if i < 3:
                    m.note(r + 2, "heart", vel=max(1, round(lub * 0.7)))


class SlowDrone(Generator):
    def measure(self, m: MeasureCtx) -> None:
        kind, i, ex = m.plan.kind, m.m.index, m.plan.extra
        chord = m.m.chord
        if kind == "pedal":
            if i == ex["dropout"]:
                m.off(0, "drone")
            else:
                m.note(0, "drone", chord.bass, vel=50)
        elif kind == "phrygian":
            m.note(0, "drone", chord.bass, vel=50)
        elif kind == "shock":
            if i == 0:
                m.note(0, "drone", chord.bass, vel=50)   # phrygian から鳴り続けていた持続音（区間は音を持ち越さない）
            elif i == 1:
                m.off(0, "drone")                        # 全 16 step 無音
            elif i == 3:
                m.note(0, "drone", chord.bass, vel=50)
        elif kind == "aftermath":
            m.note(0, "drone", chord.bass, vel=ramp(40, 0, i, 4))


class SlowTexture(Generator):
    def measure(self, m: MeasureCtx) -> None:
        kind, i, ex = m.plan.kind, m.m.index, m.plan.extra
        chord = m.m.chord
        if kind == "hush":
            m.note(0, "strings", chord.harmony, vel=(6, 14, 22, 30)[i])
        elif kind == "pedal":
            if i == ex["dropout"]:
                m.off(0, "strings")
            else:
                strings_chord(m)
        elif kind == "phrygian":
            strings_chord(m)
        elif kind == "shock":
            if i == 0:
                strings_chord(m)
            elif i == 1:
                m.off(0, "strings")
            elif i == 3:                                 # pizz ostinato（vol 30→60）
                steps = list(range(2, STEPS, 2))
                root = pizz_root_note(chord)
                for k, r in enumerate(steps):
                    m.note(r, "pizz", root, vel=ramp(30, 60, k, len(steps)))
        elif kind == "aftermath":
            m.note(0, "strings", chord.harmony, vel=ramp(34, 8, i, 4))


class SlowLead(Generator):
    def section(self, ctx: SectionCtx) -> None:
        if ctx.plan.kind == "phrygian":
            ctx.state["gen"] = lead_generator(ctx.rng, ScaleRules(dissonance_weight=0.6, leap_probability=0.35),
                                              ctx.plan)
            ctx.state["prev"] = None
        super().section(ctx)

    def measure(self, m: MeasureCtx) -> None:
        kind, i, ex = m.plan.kind, m.m.index, m.plan.extra
        chord = m.m.chord
        if kind == "pedal":
            stab = ex["stab"]
            if stab is not None and stab // STEPS == i:      # 突発 pizz スタブ
                m.note(stab % STEPS, "pizz", pizz_root_note(chord), vel=64)
        elif kind == "phrygian":                             # 1〜2 音/小節（2 音目はポルタメント）
            two = m.rng.random() < 0.5
            motif = RhythmMotif((0, 8)) if two else RhythmMotif((0,))
            events, m.state["prev"] = m.state["gen"].bar(motif, chord, m.state["prev"], rows=STEPS)
            if two:
                m.note(events[0].row, "lead", events[0].note, vel=events[0].vol, dur=events[0].dur)
                e2 = events[1]
                m.note(e2.row, "lead", e2.note, vel=e2.vol, dur=STEPS - 1 - e2.row, arts=(Glide(param=GLIDE_PARAM),))
            else:
                e = events[0]
                m.note(e.row, "lead", e.note, vel=e.vol, dur=max(1, round(e.dur * 0.9)))
        elif kind == "shock":
            if i == 1:
                m.off(0, "lead")
            elif i == 3:                                     # 高音 lead（区間の終わりまで伸ばす）
                m.note(0, "lead", max(chord.chord_tones), arts=(Vibrato(VIBRATO_PARAM),))


@register_genre
class SuspenseSlowGenre(Genre):
    id = "suspense-slow"
    aliases = ("suspense",)
    category = "style"
    display_name = "Suspense Slow"
    description = "低速・重苦しい緊張。心拍と無音、突発の金属音"
    description_en = "Slow, heavy tension: heartbeat and silence, sudden metallic hits"
    title = "Suspense Slow"
    tempo_choices = (64, 66, 68, 70, 72)

    instruments = INSTRUMENTS
    harmony = None   # 和声は区間ごとに手組み（voice(arp=True)）。plan() を全面的に上書きする
    sections = {
        "hush": Section(measures=MEASURES, intensity=0.2, parts=frozenset({"pulse", "texture"})),
        "pedal": Section(measures=MEASURES, intensity=0.5, parts=frozenset({"pulse", "drone", "texture", "lead"})),
        "phrygian": Section(measures=MEASURES, intensity=0.6, parts=frozenset({"pulse", "drone", "texture", "lead"})),
        "shock": Section(measures=MEASURES, intensity=0.9, parts=frozenset({"pulse", "drone", "texture", "lead"})),
        "aftermath": Section(measures=MEASURES, intensity=0.1, parts=frozenset({"pulse", "drone", "texture"})),
    }
    form = ("hush", "pedal", "phrygian", "pedal", "shock", "aftermath")
    parts = (
        Part("pulse", SlowPulse(), pan=PAN_PULSE, kit=PULSE_KIT),
        Part("drone", SlowDrone(), pan=PAN_DRONE),
        Part("texture", SlowTexture(), pan=PAN_TEXTURE, kit=TEXTURE_KIT),
        Part("lead", SlowLead(), pan=PAN_LEAD, kit=LEAD_KIT),
    )
    mod_channels = {4: 1}

    progression_names = ("pedal", "tritone", "phrygian")   # 進行 A・B の候補（異なるものを plan で選ぶ）

    def plan(self, rng: random.Random) -> SongPlan:
        names = list(self.progression_names)
        ia = rng.randrange(len(names))
        ib = (ia + rng.randint(1, len(names) - 1)) % len(names)
        a, b = names[ia], names[ib]
        bpm = rng.choice(list(self.tempo_choices))

        # pedal の dropout・anvil・スタブ。乱数は使う・使わないに関わらず固定の順で引く
        dropout = rng.choice([1, 2])
        anvil = dropout + 1 if rng.random() < 0.5 else None
        stab = STAB_ROW if rng.random() < 0.5 else None
        if anvil is not None and stab is not None and anvil * STEPS - SHOCK_GUARD_ROWS <= stab < anvil * STEPS:
            stab = None                  # 衝撃の直前 8 step に pizz を置かない

        def sec(name: str, prog: str, **extra):
            decl = self.sections[name]
            return section_plan(name, prog, decl, decl.parts, **extra)

        sections = {
            "hush": sec("hush", a),
            "pedal": sec("pedal", a, dropout=dropout, anvil=anvil, stab=stab),
            "phrygian": sec("phrygian", b),
            "shock": sec("shock", b),
            "aftermath": sec("aftermath", a),
        }
        return SongPlan(bpm=bpm, key_pc=KEY_PC, sections=sections, order=list(self.form),
                        summary=[progression_summary("Theme A", a), progression_summary("Theme B", b)])
