"""orchestral（旧 genres/orchestral.py の移植。FRAMEWORK_REDESIGN.md §15.4 のグループC）。

8チャンネル専用（``mod_channels={8: 1}``）のフルオーケストラ。6声（bass/tenor/alto/soprano1/soprano2/descant）の
和声を、``voice()`` が返す標準の bass/harmony/chord_tones に、残り3声（alto/soprano1/descant）を
``chord_tones`` のピッチクラス集合から小節ごとに導出して表す。区間の音量は intensity をそのまま掛ける
（現行どおり。``scale_vol`` の式ではない）。

旧版は ``SampleSpec.pan``・``finetune`` でチャンネルごとの定位とデチューンを固定していた。新版は ``Part.pan`` と
``Instrument(tune_cents=+37.5)``（finetune 3 × 12.5 セント）で表す。
"""
from __future__ import annotations

from ..core.harmony import Registers
from ..core.model import ChordDef, ChordSpec, GmVoice
from ..core.pitch import lowest_note_with_pc
from ..core.synth_presets import PRESETS
from ..framework.context import Generator, MeasureCtx
from ..framework.genre import Genre, Harmony, Instrument, Kit, Part, Section
from ..framework.registry import register_genre

BASS_REG = (-12, -1)                          # CB（shift=-24 → t=12..23）
TENOR_REG = (0, 11)                           # VC（shift=-12 → t=12..23）
ALTO_REG = (7, 18)                            # VLA（shift=-7 → t=14..25）
SOP1_REG = (12, 23)                           # VLN2（shift=0）
SOP2_REG = (19, 30)                           # VLN1（旋律、shift=0）
DESCANT_REG = (24, 35)                        # BRASS（shift=0）

PROGRESSION = (ChordSpec(0, "maj"), ChordSpec(5, "maj"), ChordSpec(7, "maj"), ChordSpec(9, "min"))   # I - IV - V - vi

STRINGS = frozenset({"vln1", "vln2", "vla", "vc", "cb"})


def _extra_voices(chord: ChordDef) -> tuple[int, int, int, int]:
    """alto/sop1/descant/sop2（旋律）を ``chord.chord_tones`` のピッチクラス集合から導出する。"""
    pcs = sorted({t % 12 for t in chord.chord_tones}) or [chord.bass % 12]
    alto = lowest_note_with_pc(pcs[1 % len(pcs)], *ALTO_REG)
    sop1 = lowest_note_with_pc(pcs[2 % len(pcs)], *SOP1_REG)
    descant = lowest_note_with_pc(pcs[0], *DESCANT_REG)
    sop2 = chord.chord_tones[-1] if chord.chord_tones else chord.bass
    return alto, sop1, descant, sop2


class Strings(Generator):
    """区間の各小節の頭で、声部ごとに全音符を弾く。``voice`` は 'vln1'・'vln2'・'vla'・'vc'・'cb'。"""

    BASE_VOL = {"vln1": 48, "vln2": 44, "vla": 42, "vc": 46, "cb": 50}

    def __init__(self, voice: str) -> None:
        self.voice = voice

    def measure(self, m: MeasureCtx) -> None:
        chord = m.m.chord
        alto, sop1, _descant, sop2 = _extra_voices(chord)
        note = {"vln1": sop2, "vln2": sop1, "vla": alto, "vc": chord.harmony, "cb": chord.bass}[self.voice]
        m.note(0, self.voice, note, vel=max(1, round(self.BASE_VOL[self.voice] * m.plan.intensity)))


class Woodwind(Generator):
    def measure(self, m: MeasureCtx) -> None:
        sop2 = _extra_voices(m.m.chord)[3]
        m.note(0, "ww", sop2, vel=max(1, round(40 * m.plan.intensity)))


class Brass(Generator):
    """development は horn、climax はトランペット（Kit の優先度で horn に勝つ）。"""

    def measure(self, m: MeasureCtx) -> None:
        descant = _extra_voices(m.m.chord)[2]
        inst = "trumpet" if m.plan.name == "climax" else "horn"
        m.note(0, inst, descant, vel=max(1, round(44 * m.plan.intensity)))


class Percussion(Generator):
    """climax のティンパニ連打（row 0・8）と、区間の先頭のシンバル・スウェル（timpani に勝つ）。"""

    def measure(self, m: MeasureCtx) -> None:
        for step in (0, 8):
            m.note(step, "timpani", m.m.chord.bass, vel=56)
        if m.m.index == 0:
            m.note(0, "cymbal", vel=60, prio=2)


def _inst(key: str, gm: GmVoice, **changes) -> Instrument:
    return Instrument(patch=PRESETS[key], gm=gm, **changes)


@register_genre
class OrchestralGenre(Genre):
    id = "orchestral"
    category = "style"
    display_name = "Orchestral"
    description = "フルオーケストラ／劇伴。8chマルチチャンネル、6声の弦+木管+金管+ティンパニ"
    description_en = "Full orchestra / film score: 8 channels, six-voice strings + woodwinds + brass + timpani"
    title = "Orchestral Suite"
    tempo_choices = (76, 80, 84, 88)

    instruments = {
        "vln1": _inst("orch_violin", GmVoice(program=40)),
        "vln2": _inst("orch_violin", GmVoice(program=40), volume=44, tune_cents=37.5),   # 合奏感の軽いデチューン
        "vla": _inst("orch_viola", GmVoice(program=41)),
        "vc": _inst("orch_cello", GmVoice(program=42)),
        "cb": _inst("orch_bass_str", GmVoice(program=43)),
        "ww": _inst("nostalgic_flute", GmVoice(program=73)),
        "horn": _inst("march_brass_section", GmVoice(program=60)),
        "trumpet": _inst("orch_trumpet", GmVoice(program=56)),
        "timpani": _inst("orch_timpani", GmVoice(program=47)),
        "cymbal": _inst("free_cymbal_swell", GmVoice(program=119)),
    }
    harmony = Harmony(keys=(0,), mode="ionian", progressions=(("I-IV-V-vi", PROGRESSION),), n_progressions=1,
                       fixed=True, registers=Registers(bass=BASS_REG, harmony=TENOR_REG, melody=SOP2_REG))
    sections = {
        "intro": Section(intensity=0.3, parts=STRINGS),
        "theme": Section(intensity=0.5, parts=STRINGS | {"ww"}),
        "development": Section(intensity=0.7, parts=STRINGS | {"ww", "brass"}),
        "climax": Section(intensity=1.0, parts=STRINGS | {"ww", "brass", "perc"}),
        "resolution": Section(intensity=0.4, parts=STRINGS),
    }
    form = ("intro", "theme", "development", "climax", "resolution")    # 通作形式。ループしない
    parts = (
        Part("vln1", Strings("vln1"), pan=30),
        Part("vln2", Strings("vln2"), pan=80),
        Part("vla", Strings("vla"), pan=150),
        Part("vc", Strings("vc"), pan=190),
        Part("cb", Strings("cb"), pan=210),
        Part("ww", Woodwind(), pan=100),
        Part("brass", Brass(), pan=160,
             kit=Kit(groups=(("brass", ("horn", "trumpet")),), priority={"trumpet": 2, "horn": 1})),
        Part("perc", Percussion(), pan=128,
             kit=Kit(groups=(("timp", ("timpani", "cymbal")),), priority={"cymbal": 2, "timpani": 1})),
    )
    mod_channels = {8: 1}
