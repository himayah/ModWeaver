"""suspense-slow: 低速・重苦しい緊張（設計書 §8.3）。

構成: hush → pedal → phrygian → pedal → shock → aftermath（``order=[0,1,2,1,3,4]``、約 85 秒）。
文法の核は「心拍」「無音→突発アクセント（anvil）」「ペダルの持続音＋アルペジオ弦」。
"""
from __future__ import annotations

from ..core.composer import RhythmMotif, ScaleRules, articulate, ramp
from ..core.model import Cell, MeasureBuffer, MeasureCtx, Pattern, PatternCtx, PatternPlan, RngStreams, SongPlan
from .registry import register_profile
from .suspense_common import (
    CH_FX, CH_LEAD, CH_LOW, CH_TEX, KEY_PC, SHOCK_GUARD_ROWS,
    PatternState, anvil_clear_row, SuspenseBase, heartbeat, pizz_ostinato, progression_summary, put_oneshot_off,
    silence_run, strings_chord, swoosh_start_row, voice_progression,
)

GLIDE_PARAM = 0x0A          # lead の 3xx（ポルタメント）速度
VIBRATO_PARAM = 0x46        # lead の 4xy（ビブラート）
STAB_ROW = 40               # pedal pattern の突発 pizz スタブの位置（m2 row 8）


@register_profile
class SuspenseSlowProfile(SuspenseBase):
    id = "suspense-slow"
    aliases = ("suspense",)
    display_name = "Suspense Slow"
    description = "低速・重苦しい緊張。心拍と無音、突発の金属音"
    title = "Suspense Slow"
    default_filename = "SuspenseSlow.mod"
    tempo_choices = (64, 66, 68, 70, 72)

    grammar = {
        "hush": "_hush", "pedal": "_pedal", "phrygian": "_phrygian", "shock": "_shock", "aftermath": "_aftermath",
    }
    # 進行 A・B の候補（異なるものを plan ストリームで選ぶ）
    progression_names = ("pedal", "tritone", "phrygian")

    # ------------------------------------------------------------ 計画
    def plan(self, rng: RngStreams) -> SongPlan:
        names = list(self.progression_names)
        ia = rng.plan.randrange(len(names))
        ib = (ia + rng.plan.randint(1, len(names) - 1)) % len(names)
        a, b = names[ia], names[ib]
        bpm = rng.plan.choice(list(self.tempo_choices))
        patterns = [
            PatternPlan("hush", voice_progression(a), intensity=0.2),
            PatternPlan("pedal", voice_progression(a), intensity=0.5),
            PatternPlan("phrygian", voice_progression(b), intensity=0.6),
            PatternPlan("shock", voice_progression(b), intensity=0.9),
            PatternPlan("aftermath", voice_progression(a), intensity=0.1),
        ]
        return SongPlan(
            bpm=bpm, patterns=patterns, order=[0, 1, 2, 1, 3, 4], key_pc=KEY_PC,
            summary=[progression_summary("Theme A", a), progression_summary("Theme B", b)],
        )

    def begin_pattern(self, pctx: PatternCtx, rng: RngStreams) -> PatternState:
        st = PatternState()
        if pctx.kind == "pedal":
            # 乱数は他パートへ影響しないよう、使う・使わないに関わらず固定順で引く
            st.dropout = rng.drums.choice([1, 2])
            if rng.drums.random() < 0.5:
                st.anvil_measure = st.dropout + 1
            if rng.melody.random() < 0.5:
                st.stab_row = STAB_ROW
            anvil_row = None if st.anvil_measure is None else st.anvil_measure * self.rows_per_measure
            if anvil_row is not None and st.stab_row is not None and anvil_row - SHOCK_GUARD_ROWS <= st.stab_row < anvil_row:
                st.stab_row = None        # Shock hit の直前 8 row に pizz を置かない
        elif pctx.kind == "phrygian":
            st.extra["gen"] = self.lead_generator(rng, ScaleRules(dissonance_weight=0.6, leap_probability=0.35))
        return st

    def finalize_pattern(self, pctx: PatternCtx, pattern: Pattern, state: PatternState, rng: RngStreams) -> None:
        # lead を使う pattern は末尾で消音する（次の pattern へ鳴り続けない）
        if pctx.kind in ("phrygian", "shock"):
            pattern.put(pattern.rows - 1, CH_LEAD, Cell(None, 0, vol=0))

    # ------------------------------------------------------------ 各 pattern の文法
    def _hush(self, mctx: MeasureCtx, st: PatternState, rng: RngStreams, buf: MeasureBuffer) -> None:
        ins, m = mctx.instruments, mctx.measure_idx
        buf.put(0, CH_TEX, ins["strings"].cell(mctx.chord.harmony, vol=(6, 14, 22, 30)[m]))
        if m >= 2:                                   # m2 から心拍（vol 26→40）
            for b in range(4):
                lub = ramp(26, 40, (m - 2) * 4 + b, 8)
                heartbeat(buf, ins["heart"], range(b * 4, b * 4 + 1), lub, round(lub * 0.7))

    def _pedal(self, mctx: MeasureCtx, st: PatternState, rng: RngStreams, buf: MeasureBuffer) -> None:
        ins, m, bpm, chord = mctx.instruments, mctx.measure_idx, mctx.pattern.bpm, mctx.chord
        if m == st.dropout:                          # 心拍・持続音が途切れる（無音）
            buf.put(0, CH_LOW, ins["drone"].off())
            buf.put(0, CH_TEX, ins["strings"].off())
        else:
            first = anvil_clear_row(bpm) if m == st.anvil_measure else 0     # anvil の余韻が切れないよう心拍を遅らせる
            heartbeat(buf, ins["heart"], range(first, 16, 4), 38, 26)
            buf.put(0, CH_LOW, ins["drone"].cell(chord.bass, vol=50))
            strings_chord(buf, ins["strings"], 0, chord)
        if m == st.anvil_measure:                    # dropout 直後の衝撃
            buf.put(0, CH_FX, ins["anvil"].cell(vol=64))
        if st.stab_row is not None and st.stab_row // self.rows_per_measure == m:
            r = st.stab_row % self.rows_per_measure
            buf.put(r, CH_LEAD, ins["pizz"].cell(self.pizz_root_note(chord), vol=64))
            put_oneshot_off(buf, CH_LEAD, r, ins["pizz"], bpm)

    def _phrygian(self, mctx: MeasureCtx, st: PatternState, rng: RngStreams, buf: MeasureBuffer) -> None:
        ins, chord = mctx.instruments, mctx.chord
        heartbeat(buf, ins["heart"], range(0, 16, 4), 40, 28)
        buf.put(0, CH_LOW, ins["drone"].cell(chord.bass, vol=50))
        strings_chord(buf, ins["strings"], 0, chord)
        # lead: 1〜2 音/measure（2 音目はポルタメント）
        gen, lead = st.extra["gen"], ins["lead"]
        two = rng.melody.random() < 0.5
        motif = RhythmMotif((0, 8)) if two else RhythmMotif((0,))
        events, st.lead_prev = gen.bar(motif, chord, st.lead_prev, rows=self.rows_per_measure)
        if two:
            articulate(buf, CH_LEAD, events, lead, gate=1.0)
            e2 = events[1]
            buf.replace(e2.row, CH_LEAD, lead.cell(e2.note, effect=3, param=GLIDE_PARAM, keep_sample=True))
            buf.put(self.rows_per_measure - 1, CH_LEAD, lead.off())
        else:
            articulate(buf, CH_LEAD, events, lead, gate=0.9)

    def _shock(self, mctx: MeasureCtx, st: PatternState, rng: RngStreams, buf: MeasureBuffer) -> None:
        ins, m, bpm, chord = mctx.instruments, mctx.measure_idx, mctx.pattern.bpm, mctx.chord
        rpm = self.rows_per_measure
        if m == 0:                                   # 心拍加速（vol 40→56、毎拍）
            for b in range(4):
                lub = ramp(40, 56, b, 4)
                heartbeat(buf, ins["heart"], range(b * 4, b * 4 + 1), lub, lub - 12)
            strings_chord(buf, ins["strings"], 0, chord)
        elif m == 1:                                 # 全 16 row 無音（持続音を消す）
            silence_run(buf, 0, ins)
        elif m == 2:                                 # 衝撃の直前に終わる swoosh
            buf.put(swoosh_start_row(rpm, bpm), CH_FX, ins["swoosh"].cell(vol=50))
        else:                                        # 衝撃: anvil、drone、pizz ostinato、高音 lead
            buf.put(0, CH_FX, ins["anvil"].cell(vol=64))
            buf.put(0, CH_LOW, ins["drone"].cell(chord.bass, vol=50))
            rows = list(range(2, rpm, 2))
            root = self.pizz_root_note(chord)
            pizz_ostinato(buf, ins["pizz"], CH_TEX, rows, [root] * len(rows),
                          [ramp(30, 60, i, len(rows)) for i in range(len(rows))])
            buf.put(0, CH_LEAD, ins["lead"].cell(max(chord.chord_tones), effect=4, param=VIBRATO_PARAM))

    def _aftermath(self, mctx: MeasureCtx, st: PatternState, rng: RngStreams, buf: MeasureBuffer) -> None:
        ins, m, chord = mctx.instruments, mctx.measure_idx, mctx.chord
        heart = ins["heart"]
        rows = (0, 8) if m < 3 else (0,)             # 心拍は 2 拍ごと。最終 measure は row 0 の lub のみ
        for i, r in enumerate(rows):
            lub = ramp(30, 10, m * 2 + i, 7)
            buf.put(r, CH_FX, heart.cell(vol=lub))
            if m < 3:
                buf.put(r + 2, CH_FX, heart.cell(vol=max(1, round(lub * 0.7))))
        buf.put(0, CH_LOW, ins["drone"].cell(chord.bass, vol=ramp(40, 0, m, 4)))
        buf.put(0, CH_TEX, ins["strings"].cell(chord.harmony, vol=ramp(34, 8, m, 4)))
