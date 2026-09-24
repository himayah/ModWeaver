"""suspense-chase: 緊急脱出・追走（DESIGN.md §6.4）。

構成: intro → a → a → b → a → b → climax → outro（``order=[0,1,2,3,1,3,4,5]``、約 53 秒）。
進行は A=pedal / B=tritone 固定（増 4 度の追走が主役）。文法の核は「毎拍の心拍＋8 分連打の drone＋
半音・増 4 度を混ぜた pizz オスティナート」と、silence run（無音）から anvil への落差。
"""
from __future__ import annotations

from ..core.composer import RhythmMotif, ScaleRules, articulate, ramp
from ..core.model import Cell, MeasureBuffer, MeasureCtx, Pattern, PatternCtx, PatternPlan, RngStreams, SongPlan
from ..core.pitch import fold_into_range
from ..profiles.registry import register_profile
from ..profiles.suspense_common import (
    CH_FX, CH_LEAD, CH_LOW, CH_TEX, KEY_PC, PIZZ_REG, SHOCK_GUARD_ROWS,
    PatternState, SuspenseBase, anvil_clear_row, progression_summary, put_oneshot_off, silence_run,
    strings_chord, swoosh_start_row, voice_progression,
)

RPM = 16                                   # rows per measure
OSTINATO_SHAPE = (0, 0, 1, 0, 0, 0, 6, 0)  # 半音・増 4 度を混ぜた音型（8 分音符 8 個分の根音からの半音差）
HEART_VOL, DUB_VOL = 56, 34
DRONE_VOLS = (52, 44)                      # 8 分連打の音量（交互）
STAB_VOL = 60
STAB_COUNT = 2
LEAD_RULES = ScaleRules(dissonance_weight=0.5, leap_probability=0.4, color_semitones=(1, 6))
LEAD_MOTIFS = (RhythmMotif((0, 3, 6, 10)), RhythmMotif((0, 2, 4, 8, 10, 12)))
CLIMAX_LEAD_REG = (30, 41)                 # climax の lead は高音域


@register_profile
class SuspenseChaseProfile(SuspenseBase):
    id = "suspense-chase"
    display_name = "Suspense Chase"
    description = "緊急脱出・追走。毎拍の心拍と 8 分連打、無音からの衝撃"
    description_en = "Emergency escape / pursuit: heartbeat on every beat, driving eighth notes, impacts out of silence"
    category = "style"
    title = "Suspense Chase"
    default_filename = "SuspenseChase.mod"
    tempo_choices = (138, 140, 142, 144, 146, 148)

    grammar = {
        "intro": "_intro", "a": "_a", "b": "_b", "climax": "_climax", "outro": "_outro",
    }

    # ------------------------------------------------------------ 計画
    def plan(self, rng: RngStreams) -> SongPlan:
        bpm = rng.plan.choice(list(self.tempo_choices))
        patterns = [
            PatternPlan("intro", voice_progression("pedal"), intensity=0.3),
            PatternPlan("a", voice_progression("pedal"), intensity=0.7),      # A1
            PatternPlan("a", voice_progression("pedal"), intensity=0.7),      # A2（silence 位置・スタブ位置が異なる）
            PatternPlan("b", voice_progression("tritone"), intensity=0.8),
            PatternPlan("climax", voice_progression("tritone"), intensity=1.0),
            PatternPlan("outro", voice_progression("pedal"), intensity=0.1),
        ]
        return SongPlan(
            bpm=bpm, patterns=patterns, order=[0, 1, 2, 3, 1, 3, 4, 5], key_pc=KEY_PC,
            summary=[progression_summary("Theme A", "pedal"), progression_summary("Theme B", "tritone")],
        )

    def begin_pattern(self, pctx: PatternCtx, rng: RngStreams) -> PatternState:
        st = PatternState()
        if pctx.kind == "a":
            # A1（index 1）は m2、A2（index 2）は m1 の後半を無音にし、次の measure 先頭で anvil を鳴らす
            silent = 2 if pctx.index % 2 == 1 else 1
            st.dropout = silent
            st.anvil_measure = silent + 1
            st.extra["stabs"] = self._draw_stabs(rng, silent)
        elif pctx.kind == "b":
            st.extra["gen"] = self.lead_generator(rng, LEAD_RULES)
        elif pctx.kind == "climax":
            gen = self.lead_generator(rng, LEAD_RULES)
            gen.register = CLIMAX_LEAD_REG
            st.extra["gen"] = gen
        return st

    @staticmethod
    def _draw_stabs(rng: RngStreams, silent: int) -> dict[int, int]:
        """突発 pizz スタブの位置 {pattern 内 row: 根音からの半音差}。silence run と anvil の直前 8 row には置かない。"""
        anvil_row = (silent + 1) * RPM
        quiet_from = silent * RPM + RPM // 2
        candidates = [
            m * RPM + r for m in range(4) for r in (6, 10, 14)
            if not (quiet_from <= m * RPM + r < anvil_row + 0)
            and not (anvil_row - SHOCK_GUARD_ROWS <= m * RPM + r < anvil_row)
            and not (anvil_row <= m * RPM + r < anvil_row + 8)          # anvil の余韻中は避ける
        ]
        rows = sorted(rng.melody.sample(candidates, STAB_COUNT))
        return {r: rng.melody.choice((1, 6)) for r in rows}

    def finalize_pattern(self, pctx: PatternCtx, pattern: Pattern, state: PatternState, rng: RngStreams) -> None:
        if pctx.kind in ("b", "climax"):
            pattern.put(pattern.rows - 1, CH_LEAD, Cell(None, 0, vol=0))     # lead を pattern 末で消音

    # ------------------------------------------------------------ 共通の部品
    @staticmethod
    def _pulse(buf: MeasureBuffer, ins, start: int, end: int) -> None:
        """毎拍の心拍（vol 56）＋奇数拍に dub（row+2, vol 34）。``[start, end)`` の拍頭に置く。"""
        for r in range(start, end, 4):
            buf.put(r, CH_FX, ins["heart"].cell(vol=HEART_VOL))
            if (r // 4) % 2 == 1 and r + 2 < end:
                buf.put(r + 2, CH_FX, ins["heart"].cell(vol=DUB_VOL))

    @staticmethod
    def _eighths(buf: MeasureBuffer, ins, chord, end: int, vols=DRONE_VOLS) -> None:
        """drone の 8 分連打（``[0, end)``）。音量は交互。

        ``end < RPM``（silence run で早期に打ち切る）場合、本来 ``end`` 以降に来るはずだった
        次の 1 音を落とさず ``end - 1``（無音直前の row）へ引き寄せる。持続音が尻切れにならず、
        無音の切迫感を保ったまま最後まで鳴らす。
        """
        i = 0
        for r in range(0, RPM, 2):
            if r < end:
                buf.put(r, CH_LOW, ins["drone"].cell(chord.bass, vol=vols[i % len(vols)]))
                i += 1
            elif end < RPM:
                buf.put(end - 1, CH_LOW, ins["drone"].cell(chord.bass, vol=vols[i % len(vols)]))
                break

    def _ostinato_note(self, chord, offset: int) -> int:
        """PIZZ_REG 内の根音（bass の pitch class）に半音差を足し、音域へ折り返す。"""
        root = self.pizz_root_note(chord, chord.bass % 12)
        return fold_into_range(root + offset, *PIZZ_REG)

    # ------------------------------------------------------------ 各 pattern の文法
    def _intro(self, mctx: MeasureCtx, st: PatternState, rng: RngStreams, buf: MeasureBuffer) -> None:
        ins, m, chord = mctx.instruments, mctx.measure_idx, mctx.chord
        if m >= 2:                                    # m2 から拍頭に heart（vol 36）
            for r in range(0, RPM, 4):
                buf.put(r, CH_FX, ins["heart"].cell(vol=36))
        note = self._ostinato_note(chord, 0)          # root 固執の pizz オスティナート（pattern 全体で crescendo）
        for step, r in enumerate(range(0, RPM, 2)):
            buf.put(r, CH_TEX, ins["pizz"].cell(note, vol=ramp(16, 56, m * 8 + step, 32)))

    def _a(self, mctx: MeasureCtx, st: PatternState, rng: RngStreams, buf: MeasureBuffer) -> None:
        ins, m, bpm, chord = mctx.instruments, mctx.measure_idx, mctx.pattern.bpm, mctx.chord
        silent = m == st.dropout                      # この measure の後半（row 8–15）は全消音
        after = m == st.anvil_measure
        end = RPM // 2 if silent else RPM
        first_pulse = anvil_clear_row(bpm) if after else 0
        self._pulse(buf, ins, first_pulse, end)
        self._eighths(buf, ins, chord, end)
        for step, off in enumerate(OSTINATO_SHAPE):    # 音型は 8 分音符 8 個（= 1 measure）で 1 周
            r = step * 2
            if r < end:
                vol = 56 if r % 4 == 0 else 44          # 拍頭アクセント
                buf.put(r, CH_TEX, ins["pizz"].cell(self._ostinato_note(chord, off), vol=vol))
        for row, off in st.extra["stabs"].items():      # 突発スタブ
            if row // RPM == m:
                r = row % RPM
                note = fold_into_range(self.pizz_root_note(chord, chord.bass % 12) + off, *PIZZ_REG)
                buf.put(r, CH_LEAD, ins["pizz"].cell(note, vol=STAB_VOL))
                put_oneshot_off(buf, CH_LEAD, r, ins["pizz"], bpm)
        if silent:
            silence_run(buf, RPM // 2, ins)
        if after:
            buf.put(0, CH_FX, ins["anvil"].cell(vol=64))

    def _b(self, mctx: MeasureCtx, st: PatternState, rng: RngStreams, buf: MeasureBuffer) -> None:
        ins, chord = mctx.instruments, mctx.chord
        self._pulse(buf, ins, 0, RPM)
        self._eighths(buf, ins, chord, RPM)
        strings_chord(buf, ins["strings"], 0, chord)   # ostinato を退避し、持続和音（arp）へ
        self._lead(buf, ins, st, rng, chord)

    def _lead(self, buf, ins, st: PatternState, rng: RngStreams, chord) -> None:
        motif = LEAD_MOTIFS[rng.melody.randrange(len(LEAD_MOTIFS))]
        events, st.lead_prev = st.extra["gen"].bar(motif, chord, st.lead_prev, rows=RPM)
        articulate(buf, CH_LEAD, events, ins["lead"], gate=0.9)

    def _climax(self, mctx: MeasureCtx, st: PatternState, rng: RngStreams, buf: MeasureBuffer) -> None:
        ins, m, bpm, chord = mctx.instruments, mctx.measure_idx, mctx.pattern.bpm, mctx.chord
        buf.put(0, CH_FX, ins["anvil"].cell(vol=64))    # 各 measure 先頭の衝撃
        if m == mctx.n_measures - 1:                    # 最終 measure: swoosh が pattern 終端へ接続（心拍は止める）
            buf.put(swoosh_start_row(RPM, bpm), CH_FX, ins["swoosh"].cell(vol=50))
        else:
            self._pulse(buf, ins, anvil_clear_row(bpm), RPM)
        self._eighths(buf, ins, chord, RPM, vols=(52,))
        note = self._ostinato_note(chord, 0)            # pizz 16 分（毎 row）の crescendo
        for r in range(RPM):
            buf.put(r, CH_TEX, ins["pizz"].cell(note, vol=ramp(30, 60, m * RPM + r, 64)))
        self._lead(buf, ins, st, rng, chord)

    def _outro(self, mctx: MeasureCtx, st: PatternState, rng: RngStreams, buf: MeasureBuffer) -> None:
        ins, m = mctx.instruments, mctx.measure_idx
        if m == 0:
            buf.put(0, CH_FX, ins["anvil"].cell(vol=64))
            buf.put(0, CH_LOW, ins["drone"].off())       # climax から鳴り続ける drone を止める
            buf.put(0, CH_TEX, ins["strings"].cell(mctx.chord.harmony, vol=20))
        if m == 2:
            buf.put(0, CH_TEX, ins["strings"].cell(mctx.chord.harmony, vol=10))
        hits = {(1, 0): 0, (1, 8): 1, (2, 4): 2, (3, 4): 3}      # row 16, 24, 36, 52 の heart（vol 40→14）
        for (mm, r), i in hits.items():
            if mm == m:
                buf.put(r, CH_FX, ins["heart"].cell(vol=ramp(40, 14, i, 4)))
