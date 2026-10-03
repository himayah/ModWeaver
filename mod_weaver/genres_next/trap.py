"""trap（旧 genres/trap.py の移植。FRAMEWORK_REDESIGN.md §15.4 のグループC）。

1小節 = 32 step = 4/4（1 step = 32分音符、1拍 = 8 step。``Meter(32, 4)``）。1小節が8拍で、表示 BPM はハーフタイムの慣習
（DESIGN.md §5.5）。各区間は 2 小節（＝ 64 step）で、進行は "i - VI" の2和音ループ（Cm-Ab）。

808 のグライドは ``Glide(steps=1)``。先行音が鳴り終わっていれば普通の発音に変え、鳴っていれば直前の音の period から
この音の period まで 1 step で届く速さ（``3xx``/``Gxx``）にするのは Realizer の責任（§5.3・§16.9）。ハットのロールは ``Retrig(3)``。
"""
from __future__ import annotations

from ..core.composer import MelodyGenerator, RhythmMotif, ScaleRules
from ..core.harmony import Registers
from ..core.model import ChordSpec, GmVoice
from ..core.pitch import fold_into_range
from ..core.synth_presets import PRESETS
from ..framework.context import Generator, MeasureCtx, SectionCtx
from ..framework.genre import Genre, Harmony, Instrument, Kit, Part, Section
from ..framework.plan import Meter
from ..framework.registry import register_genre
from ..framework.score import Glide, Retrig

KEY_PC = 0                                    # C
BASS_REG = (0, 11)                            # 808（shift=-12 → t=12..23）
LEAD_REG = (24, 35)                           # lead_pluck（hook のみ）
METER = Meter(steps=32, steps_per_beat=4)

I_CHORD = ChordSpec(0, "min", label="i")        # Cm
VI_CHORD = ChordSpec(8, "maj", label="VI")      # Ab

LEAD_RULES = ScaleRules(step_choices=(-1, 1, -2, 2), leap_probability=0.2, leap_semitones=(3, 4, 7),
                         leap_recovery=True, dissonance_weight=0.1)
MOTIF_808_ROWS = (0, 8, 12, 20)                # 拍（8 step 間隔）を基本にしたシンコペーション
HAT_ROWS = tuple(range(0, 32, 4))              # 8分（8箇所）
SNARE_ROWS = (16, 28)                          # 2拍・4拍相当（4拍目はやや後ろにずらす trap の定型）
LEAD_MOTIFS = (
    RhythmMotif((0, 8, 16, 24)),
    RhythmMotif((0, 6, 8, 16, 22, 24)),
    RhythmMotif((0, 8, 14, 16, 24)),
)


# ============================================================
# ジャンル内のジェネレータ
# ============================================================

class Bass808(Generator):
    """拍をシンコペーションさせた 808 パターン。連続する打の間は 1 step のグライドで滑らせる。
    小節の最初の打は頭から鳴らす（vol 60）。outro は区間の頭に 1 発だけ。"""

    def measure(self, m: MeasureCtx) -> None:
        chord = m.m.chord
        if m.plan.kind == "outro":
            m.note(0, "k808", chord.bass, vel=round(60 * m.plan.intensity))
            return
        root, fifth = chord.bass, fold_into_range(chord.bass + 7, *BASS_REG)
        for i, (step, note) in enumerate(zip(MOTIF_808_ROWS, (root, fifth, root, fifth))):
            if i == 0:
                m.note(step, "k808", note, vel=60)
            else:
                m.note(step, "k808", note, arts=(Glide(steps=1),))


class HiHat(Generator):
    """8分刻みのハイハット。小節に1箇所、ロール（``Retrig``）を確率的に差し込む。フレーズ末はオープンハット（Kit の優先度で置換）。"""

    def measure(self, m: MeasureCtx) -> None:
        roll = m.rng.choice(HAT_ROWS)
        for step in HAT_ROWS:
            if step == roll and m.rng.random() < 0.6:
                m.note(step, "hat_c", arts=(Retrig(3),))
            else:
                m.note(step, "hat_c")
        m.note(HAT_ROWS[-1], "hat_o")


class TrapSnare(Generator):
    def measure(self, m: MeasureCtx) -> None:
        for step in SNARE_ROWS:
            m.note(step, "snare", vel=max(1, round(50 * m.plan.intensity)))


class PluckLead(Generator):
    def section(self, ctx: SectionCtx) -> None:
        ctx.state["gen"] = MelodyGenerator(LEAD_RULES, LEAD_REG, ctx.plan.scale, ctx.rng, base_vol=50)
        ctx.state["prev"] = None
        super().section(ctx)

    def measure(self, m: MeasureCtx) -> None:
        motif = m.rng.choice(LEAD_MOTIFS)
        events, m.state["prev"] = m.state["gen"].bar(motif, m.m.chord, m.state["prev"], rows=32, base_vol=48)
        for e in events:
            m.note(e.row, "lead", e.note, vel=e.vol, dur=max(1, round(e.dur * 0.8)))


def _inst(key: str, gm: GmVoice) -> Instrument:
    return Instrument(patch=PRESETS[key], gm=gm)


@register_genre
class TrapGenre(Genre):
    id = "trap"
    category = "style"
    display_name = "Trap"
    description = "トラップ／ドリル。32分ハイハットロールと808グライド、Cm-Ab の2和音ループ"
    description_en = "Trap / drill: 32nd-note hi-hat rolls and 808 glides over a two-chord Cm-Ab loop"
    title = "Trap Beat"
    tempo_choices = (140, 145, 150, 155)      # 32分格子なので実質ハーフタイム（70-77bpm相当）で感じる

    instruments = {
        "k808": _inst("trap_808", GmVoice(program=38)),
        "snare": _inst("trap_snare_clap", GmVoice(drum_note=40)),
        "hat_c": _inst("trap_hat_closed", GmVoice(drum_note=42)),
        "hat_o": _inst("trap_hat_open", GmVoice(drum_note=46)),
        "lead": _inst("trap_lead_pluck", GmVoice(program=80)),
    }
    harmony = Harmony(keys=(KEY_PC,), mode="aeolian", progressions=(("i-VI", (I_CHORD, VI_CHORD)),), n_progressions=1,
                       fixed=True, registers=Registers(bass=BASS_REG, harmony=LEAD_REG, melody=LEAD_REG))
    sections = {
        "intro": Section(measures=2, meter=METER, intensity=0.4, parts=frozenset({"hat"})),
        "verse": Section(measures=2, meter=METER, intensity=0.6, parts=frozenset({"bass808", "hat"})),
        "hook": Section(measures=2, meter=METER, intensity=1.0,
                        parts=frozenset({"bass808", "hat", "snare", "lead"})),
        "half_time": Section(measures=2, meter=METER, intensity=0.5, parts=frozenset({"bass808", "hat"})),
        "outro": Section(measures=2, meter=METER, intensity=0.3, parts=frozenset({"bass808"})),
    }
    form = ("intro", "verse", "verse", "hook", "hook", "half_time", "hook", "hook", "outro")
    parts = (
        Part("bass808", Bass808(), pan=128),
        Part("snare", TrapSnare(), pan=128),
        Part("hat", HiHat(), pan=176,
             kit=Kit(groups=(("hat", ("hat_c", "hat_o")),), priority={"hat_o": 2, "hat_c": 1})),
        Part("lead", PluckLead(), pan=80),
    )
    mod_channels = {4: 1}
