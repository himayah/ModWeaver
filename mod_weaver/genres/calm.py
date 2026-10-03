"""calm（旧 genres/calm.py の宣言を機械変換したもの。DESIGN.md §6）。"""
from __future__ import annotations

from ..core.model import ChordSpec, GmVoice
from ..core.synth_presets import PRESETS
from ..framework.gens import Arp, BassLine, Pad
from ..framework.genre import Genre, Harmony, Instrument, Kit, Part, Section
from ..framework.context import Generator, MeasureCtx
from ..framework.registry import register_genre

C = ChordSpec


def _inst(key: str, gm: GmVoice, **changes) -> Instrument:
    patch = PRESETS[key]
    if changes:
        import dataclasses
        patch = dataclasses.replace(patch, **changes)
    return Instrument(patch=patch, gm=gm)

PROGRESSIONS = (
    ("Imaj7-IVmaj7", (C(0, "maj7", label="Imaj7"), C(5, "maj7", label="IVmaj7"))),
    ("Imaj7-vi7", (C(0, "maj7", label="Imaj7"), C(9, "m7", label="vi7"))),
    ("IVmaj7-Vsus4", (C(5, "maj7", label="IVmaj7"), C(7, "sus4", label="Vsus4"))),
)


BELL_REGISTER = (24, 35)


class CalmBell(Generator):
    """ベル: 4小節に1〜2音（1・3小節目の弱拍に、確率で）。旧 extra_measure（"fx" の区間だけ鳴る）。"""

    def __init__(self, inst: str, register: tuple[int, int]) -> None:
        self.inst = inst
        self.register = register

    def measure(self, m: MeasureCtx) -> None:
        if m.m.index % 2:
            return
        if m.rng.random() < (0.9 if m.m.index == 0 else 0.45):
            lo, hi = self.register
            pcs = {c % 12 for c in m.m.chord.chord_tones}
            tones = [t for t in range(lo, hi + 1) if t % 12 in pcs]
            step = m.rng.choice((4, 6, 10, 12))
            m.note(step, self.inst, m.rng.choice(tones), vel=round(30 * m.plan.intensity + 10))


@register_genre
class CalmGenre(Genre):
    id = "calm"
    category = "mood"
    display_name = "Calm / Relaxed"
    description = "落ち着き。低いテンポで柔らかいパッドとピアノの分散和音"
    description_en = "Calm and relaxed: soft pads and slow piano arpeggios"
    title = "Calm Evening"
    tempo_choices = (68, 70, 72, 74, 76, 78)

    instruments = {
        "piano": _inst("keys_piano", GmVoice(program=0)),
        "bass": _inst("bass_finger", GmVoice(program=33)),
        "bell": _inst("keys_bell", GmVoice(program=9)),
        "pad": _inst("pad_warm", GmVoice(program=89)),
    }
    harmony = Harmony(keys=(0, 5, 7), mode="lydian", progressions=PROGRESSIONS, n_progressions=2)
    sections = {
        "intro": Section(intensity=0.3, parts=frozenset({"pad", "arp"})),
        "a": Section(intensity=0.5, parts=frozenset({"fx", "pad", "bass", "arp"})),
        "b": Section(prog=1, intensity=0.6, parts=frozenset({"fx", "pad", "bass", "arp"})),
        "outro": Section(intensity=0.2, parts=frozenset({"pad", "arp"})),
    }
    form = ("intro", "a", "b", "a", "outro")
    parts = (
        Part("arp", Arp("piano", register=(12, 27), steps=(0, 2, 4, 6, 8, 10, 12, 14), vol=40, pattern="updown"), pan=128),
        Part("pad", Pad("pad", vol=30), pan=128),
        Part("fx", CalmBell("bell", BELL_REGISTER), pan=128),
        Part("bass", BassLine("bass", kind="whole", vol=34), pan=128),
    )
    mod_channels = {4: 1}
