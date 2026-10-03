"""jrpg（旧 genres/jrpg.py の宣言を機械変換したもの。FRAMEWORK_REDESIGN.md §15）。"""
from __future__ import annotations

from ..core.composer import RhythmMotif, ScaleRules
from ..core.model import ChordSpec, GmVoice
from ..core.synth_presets import PRESETS
from ..framework.gens import Arp, BassLine, Echo, Groove, Layer, Lead, Pad, hits
from ..framework.genre import Genre, Harmony, Instrument, Kit, Part, Section
from ..framework.context import Generator, MeasureCtx
from ..core.pitch import fold_into_range
from ..framework.score import NoteEvent
from ..framework.registry import register_genre

C = ChordSpec


def _inst(key: str, gm: GmVoice, **changes) -> Instrument:
    patch = PRESETS[key]
    if changes:
        import dataclasses
        patch = dataclasses.replace(patch, **changes)
    return Instrument(patch=patch, gm=gm)

GROOVES = {
    "main": hits("snare", (4, 12), 22) + hits("snare", (14, 15), 16, 0.5),
    "fill": hits("snare", (8, 10, 12, 13, 14, 15), 34),
}
LEAD_MOTIFS = {
    "verse": (RhythmMotif(rows=(0, 4, 6, 8, 12)), RhythmMotif(rows=(0, 2, 4, 8, 12)), RhythmMotif(rows=(0, 6, 8, 10, 12))),
    "bridge": (RhythmMotif(rows=(0, 8, 12)), RhythmMotif(rows=(0, 4, 8)), RhythmMotif(rows=(0, 6, 8, 14))),
}
PROGRESSIONS = (
    ("canon I-V-vi-iii", (C(0, "maj", label="I"), C(7, "maj", label="V"), C(9, "min", label="vi"), C(4, "min", label="iii"))),
    ("canon IV-I-IV-V", (C(5, "maj", label="IV"), C(0, "maj", label="I"), C(5, "maj", label="IV"), C(7, "maj", label="V"))),
    ("vi-IV-V-I", (C(9, "min", label="vi"), C(5, "maj", label="IV"), C(7, "maj", label="V"), C(0, "maj", label="I"))),
    ("I-bVII-IV-I", (C(0, "maj", label="I"), C(10, "maj", label="bVII"), C(5, "maj", label="IV"), C(0, "maj", label="I"))),
)


FANFARE = ((0, 2, 3, 4, 8), (0, 4, 8), (0, 2, 3, 4, 8), (0,))   # イントロの金管（小節ごとの step）
COUNTER_REGISTER = (14, 26)


class TimpaniMarch(Groove):
    """行進のスネアに、2小節ごとの和音の変わり目でティンパニ（根音）を足す（旧 extra_measure）。"""

    def measure(self, m: MeasureCtx) -> None:
        super().measure(m)
        if m.is_chord_change and m.m.index % 2 == 0:
            m.note(0, "timp", m.m.chord.bass, vel=m.scale_vol(44))


class SequenceLead(Lead):
    """楽節の2小節目は1小節目の動機を1音階上げて繰り返す（ゼクエンツ）。それ以外は Lead の楽節。
    旧版は書いたばかりの旋律を measure から読み戻していたが、ここでは Score の自分のイベントから拾う。"""

    def measure(self, m: MeasureCtx) -> None:
        if m.m.index % 4 != 1 or "seq" not in m.state:
            super().measure(m)
            if m.m.index % 4 == 0:
                lo = m.m.start
                m.state["seq"] = [(e.step - lo, e) for e in m.own_events()
                                  if isinstance(e, NoteEvent) and lo <= e.step < lo + m.m.steps]
            return
        ladder = m.plan.scale.notes_in(*m.genre.harmony.registers.melody)
        last = None
        for rel, e in m.state.pop("seq"):
            note = round(e.pitch)
            i = ladder.index(note) if note in ladder else None
            last = ladder[i + 1] if i is not None and i + 1 < len(ladder) else note
            m.note(rel, e.inst, last, vel=e.vel, dur=e.dur, arts=e.arts)
        if last is not None:
            m.state["prev"] = last


class Fanfare(Generator):
    """金管: "fanfare" の区間はイントロの決め（4小節で型が変わる）、"counter" の区間は和音の変わり目に第3音を伸ばす。"""

    def __init__(self, inst: str) -> None:
        self.inst = inst

    def measure(self, m: MeasureCtx) -> None:
        tags = m.plan.section.tags
        chord = m.m.chord
        pcs = {c % 12 for c in chord.chord_tones}
        if "fanfare" in tags:
            tones = [t for t in range(*COUNTER_REGISTER) if t % 12 in pcs]
            phase = m.m.index % 4
            rows = FANFARE[phase]
            for i, step in enumerate(rows):
                note = tones[-1] if step == 0 and phase == 3 else tones[min(i, len(tones) - 1)]
                dur = 12 - step if (phase != 3 and i == len(rows) - 1) else None     # 最後の音は 12 step 目で止める
                m.note(step, self.inst, note, vel=m.scale_vol(46), dur=dur)
        elif "counter" in tags and m.is_chord_change:
            third = sorted({t % 12 for t in chord.chord_tones}, key=lambda pc: (pc - chord.harmony) % 12)[1]
            m.note(0, self.inst, fold_into_range(third, *COUNTER_REGISTER), vel=m.scale_vol(34))


@register_genre
class JrpgGenre(Genre):
    id = "jrpg"
    category = "style"
    display_name = "JRPG Game Music"
    description = "ゲーム音楽風（JRPG）。旋律を重視した冒険のテーマ、ハープと弦とホルン"
    description_en = "JRPG game music style: melodic adventure theme with harp, strings and horn"
    title = "Field of Adventure"
    tempo_choices = (96, 100, 104, 108, 112, 116, 120)

    instruments = {
        "timp": _inst("orch_timpani", GmVoice(program=47)),
        "snare": _inst("march_snare", GmVoice(drum_note=38)),
        "harp": _inst("keys_harp", GmVoice(program=46)),
        "cello": _inst("orch_cello", GmVoice(program=42)),
        "flute": _inst("wind_flute", GmVoice(program=73)),
        "tpt": _inst("orch_trumpet", GmVoice(program=56)),
        "brass": _inst("march_brass_section", GmVoice(program=61), volume=38),
        "str": _inst("orch_violin", GmVoice(program=48), name="StringPad", volume=30),
        "choir": _inst("vox_choir", GmVoice(program=52), volume=30),
    }
    harmony = Harmony(keys=(0, 2, 5), mode="ionian", progressions=PROGRESSIONS, n_progressions=2, fixed=True)
    sections = {
        "intro": Section(prog=3, intensity=0.9, parts=frozenset({"brass", "bass", "drums", "pad", "arp"}), tags=frozenset({"fanfare"})),
        "a": Section(intensity=0.75, parts=frozenset({"bass", "drums", "pad", "lead", "arp"})),
        "a2": Section(prog=1, intensity=0.8, parts=frozenset({"bass", "drums", "pad", "lead", "arp"}), fill=True),
        "b": Section(prog=2, intensity=0.85, parts=frozenset({"brass", "bass", "drums", "pad", "lead", "arp"}), fill=True, motifs="bridge", tags=frozenset({"counter"})),
        "ending": Section(prog=3, intensity=0.9, parts=frozenset({"brass", "bass", "drums", "pad", "lead", "arp"}), tags=frozenset({"counter"})),
    }
    form = ("intro", "a", "a2", "b", "a", "a2", "ending")
    parts = (
        Part("drums", TimpaniMarch(GROOVES), pan=128,
             kit=Kit(groups=(("timpani/snare", ("timp", "snare")),))),
        Part("arp", Arp("harp", register=(17, 31), steps=(0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15), vol=30), pan=84),
        Part("bass", BassLine("cello", kind="half", vol=46), pan=128),
        Part("pad", Pad("str", vol=28), pan=172, min_channels=6),
        Part("lead", SequenceLead("flute", ScaleRules(leap_semitones=(3, 4, 5, 7)), LEAD_MOTIFS,
                   vol=48, gate=0.9, vibrato=0x23,
                   inst_for=lambda sp: "tpt" if sp.kind == "b" else "flute"), pan=150),
        Part("brass", Fanfare("brass"), pan=100, min_channels=6),
        Part("melody echo", Echo(delay=3, ratio=0.45), follow="lead", pan=96, min_channels=8),
        Part("choir", Layer("choir", vol=26, chordal=True), follow="pad", pan=160, min_channels=8),
    )
    mod_channels = {4: 1, 6: 2, 8: 1}
