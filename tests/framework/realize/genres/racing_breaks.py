"""racing-breaks を新フレームワークへ試験移植したもの（DESIGN.md §6.14〜§6.14 のグループB）。

F3 の試験移植その2。旧 ``mod_weaver/genres/racing_breaks.py``（``RacingBreaksProfile``）の
``plan()``・``drums``・``bass``・``comp`` の上書きを、ジャンル内のジェネレータに書き直す。
"""
from __future__ import annotations

import dataclasses

from mod_weaver.core.composer import RhythmMotif, ScaleRules
from mod_weaver.core.model import ChordSpec, GmVoice
from mod_weaver.core.pitch import CHORD_QUALITIES, fold_into_range
from mod_weaver.core.synth import PitchSweepLayer
from mod_weaver.core.synth_presets import PRESETS
from mod_weaver.framework.context import Generator, MeasureCtx
from mod_weaver.framework.gens import Echo, Groove, Layer, Lead, Pad, hits
from mod_weaver.framework.genre import Genre, Harmony, Instrument, Kit, Part, Section
from mod_weaver.framework.plan import SongPlan, default_plan
from mod_weaver.framework.score import Vibrato

C = ChordSpec


def _inst(key: str, gm: GmVoice, **changes) -> Instrument:
    patch = PRESETS[key]
    if changes:
        patch = dataclasses.replace(patch, **changes)
    return Instrument(patch=patch, gm=gm)


FAMILIES = {
    "dnb": (3, (166, 168, 170, 172, 174)),
    "breaks": (3, (144, 146, 148)),
    "twostep": (1, (118, 120, 122)),
}
FAMILY_NAMES = {"dnb": "drum'n'bass", "breaks": "breakbeat", "twostep": "2-step"}

HATS8 = hits("hat", (0, 4, 8, 12), 38) + hits("hat", (2, 6, 10, 14), 28)
FILL = hits("snare", (8, 10, 12, 13, 14, 15), 42)
CRASH = hits("crash", (0,), 50)
DRUMS = {
    "dnb:main": (hits("kick", (0, 10), 60) + hits("kick", (6,), 46, 0.35) + hits("snare", (4, 12), 54)
                 + hits("snare", (7, 9, 15), 20, 0.4) + HATS8 + hits("ohat", (14,), 26, 0.3)),
    "dnb:intro": hits("kick", (0,), 50) + HATS8 + hits("ride", (2, 10), 24, 0.6),
    "breaks:main": (hits("kick", (0, 10), 60) + hits("kick", (3,), 44, 0.4) + hits("kick", (15,), 48, 0.6)
                    + hits("snare", (4, 12), 52) + hits("snare", (7, 14), 20, 0.35) + HATS8
                    + hits("ohat", (6,), 26, 0.3)),
    "breaks:intro": hits("kick", (0, 10), 50) + HATS8,
    "twostep:main": (hits("kick", (0, 10), 58) + hits("kick", (5,), 46, 0.45) + hits("kick", (11,), 42, 0.3)
                     + hits("snare", (4, 12), 50) + hits("ohat", (2, 6, 10, 14), 26)
                     + hits("hat", range(1, 16, 2), 16, 0.7)),
    "twostep:intro": hits("kick", (0, 10), 50) + hits("ohat", (2, 6, 10, 14), 24),
    "fill": FILL,
    "crash": CRASH,
}

BASS_LINES = {
    "dnb": ((0, "root", 1.0), (10, "root", 1.0), (14, "approach", 0.5)),
    "breaks": ((0, "root", 1.0), (3, "root", 0.5), (7, "fifth", 0.5), (10, "root", 1.0), (15, "next", 0.6)),
    "twostep": ((0, "root", 1.0), (3, "octave", 0.4), (6, "root", 1.0), (10, "root", 1.0), (13, "fifth", 0.5)),
}
EP_ROWS = {
    "dnb": ((0, True, 1.0), (10, False, 1.0)),
    "breaks": ((0, True, 1.0), (7, False, 0.5), (10, False, 1.0)),
    "twostep": ((0, True, 1.0), (3, False, 0.6), (10, False, 1.0)),
}
EP_WOBBLE = 0x22

SUB_KICK = dataclasses.replace(
    PRESETS["drum_909_kick"], name="RacingKick",
    layers=tuple(dataclasses.replace(wl, layer=dataclasses.replace(wl.layer, freq_start=90.0, freq_end=26.0))
                 if isinstance(wl.layer, PitchSweepLayer) else wl for wl in PRESETS["drum_909_kick"].layers))
SUB_BASS = dataclasses.replace(PRESETS["bass_deep"], name="RacingSub", shift=0)

LEAD_MOTIFS = {
    "verse": (RhythmMotif((0, 6, 10)), RhythmMotif((0, 4, 8, 12)), RhythmMotif((2, 6, 10, 12))),
    "chorus": (RhythmMotif((0, 3, 6, 8, 12)), RhythmMotif((0, 4, 6, 10, 14))),
}
PROGRESSIONS = (
    ("i9-iv9", (C(0, "m9", label="im9"), C(5, "m9", label="ivm9"))),
    ("i9-bVImaj9", (C(0, "m9", label="im9"), C(8, "maj9", label="bVImaj9"))),
    ("i9-bIImaj9", (C(0, "m9", label="im9"), C(1, "maj9", label="bIImaj9"))),
    ("bIIImaj9-bVImaj9-i9-v7sus4", (C(3, "maj9", label="bIIImaj9"), C(8, "maj9", label="bVImaj9"),
                                    C(0, "m9", label="im9"), C(7, "7sus4", label="v7sus4"))),
    ("i9-bVIImaj9-bVImaj9-v7sus4", (C(0, "m9", label="im9"), C(10, "maj9", label="bVIImaj9"),
                                    C(8, "maj9", label="bVImaj9"), C(7, "7sus4", label="v7sus4"))),
)
GROOVE = frozenset({"drums", "bass", "comp", "pad"})


# ============================================================
# ジャンル内のジェネレータ（DESIGN.md §6.14: racing-breaks）
# ============================================================

class BreaksBass(Generator):
    def __init__(self, inst: str, vol: int = 50) -> None:
        self.inst = inst
        self.vol = vol

    def measure(self, m: MeasureCtx) -> None:
        lo, hi = m.genre.harmony.registers.bass
        root = m.m.chord.bass
        nxt = m.m.next_chord.bass
        tones = {
            "root": root,
            "fifth": fold_into_range(root + 7, lo, hi),
            "octave": root + 12,
            "next": nxt,
            "approach": fold_into_range(nxt - 1 if nxt != root else root + 7, lo, hi),
        }
        family = m.song.extra["family"]
        for row, tone, prob in BASS_LINES[family]:
            if row >= m.m.steps or (prob < 1.0 and m.rng.random() >= prob):
                continue
            vol = self.vol if row == 0 else self.vol - 6
            m.note(row, self.inst, tones[tone], vel=m.scale_vol(vol))


class BreaksComp(Generator):
    def __init__(self, inst: str, vol: int = 42, wobble: int = EP_WOBBLE) -> None:
        self.inst = inst
        self.vol = vol
        self.wobble = wobble

    def measure(self, m: MeasureCtx) -> None:
        family = m.song.extra["family"]
        chord = m.m.chord
        intervals = CHORD_QUALITIES[m.m.quality]
        for row, accent, prob in EP_ROWS[family]:
            if row >= m.m.steps or (prob < 1.0 and m.rng.random() >= prob):
                continue
            vol = self.vol if accent else self.vol - 10
            arts = (Vibrato(self.wobble, at=1, steps=1),) if accent else ()
            m.note(row, self.inst, chord.harmony, vel=m.scale_vol(vol), chord=intervals, arts=arts)


class RacingBreaksToy(Genre):
    id = "racing-breaks"
    category = "style"
    display_name = "90s Racing Game Breaks"
    description = "90年代後半のレースゲーム風。ドラムンベース／ブレイクビーツに 9th のエレピと太いサブベース"
    description_en = "Late-90s racing game style: drum'n'bass / breakbeat with 9th-chord e.piano and deep sub bass"
    title = "Night Circuit Breaks"
    tempo_choices = tuple(sorted(b for _w, bpms in FAMILIES.values() for b in bpms))

    instruments = {
        "kick": Instrument(patch=SUB_KICK, gm=GmVoice(drum_note=36)),
        "snare": _inst("drum_pop_snare", GmVoice(drum_note=38)),
        "hat": _inst("drum_909_hat", GmVoice(drum_note=42)),
        "ohat": _inst("drum_909_open_hat", GmVoice(drum_note=46)),
        "ride": _inst("swing_ride", GmVoice(drum_note=51)),
        "crash": _inst("march_crash_cymbal", GmVoice(drum_note=49)),
        "bass": Instrument(patch=SUB_BASS, gm=GmVoice(program=38)),
        "vox": _inst("vox_ooh", GmVoice(program=53)),
        "ep": _inst("keys_ep", GmVoice(program=4)),
        "pad": _inst("pad_warm", GmVoice(program=89)),
        "brass": _inst("march_brass_horn", GmVoice(program=61), volume=36),
    }
    harmony = Harmony(keys=(9, 10, 4, 0, 5), mode="aeolian", progressions=PROGRESSIONS, n_progressions=2,
                       mode_by_quality={"m9": "dorian", "maj9": "lydian", "7sus4": "mixolydian"})
    sections = {
        "intro": Section(prog=0, intensity=0.55, parts=frozenset({"drums", "pad"}), groove="intro"),
        "groove": Section(prog=0, intensity=0.75, parts=GROOVE),
        "a": Section(prog=0, intensity=0.85, parts=GROOVE | {"lead"}),
        "b": Section(prog=1, intensity=1.0, parts=GROOVE | {"lead"}, crash=True, fill=True, motifs="chorus"),
        "break": Section(prog=1, intensity=0.5, parts=frozenset({"comp", "pad"})),
        "build": Section(prog=0, intensity=0.7, parts=frozenset({"drums", "bass", "pad"}), groove="intro",
                          fill=True),
        "outro": Section(prog=0, intensity=0.6, parts=frozenset({"drums", "bass", "pad"})),
    }
    form = ("intro", "groove", "groove", "a", "a", "b", "b", "groove", "a", "a", "b", "b", "break", "break",
            "build", "b", "b", "outro", "outro")
    parts = (
        Part("drums", Groove(DRUMS, groove_name=lambda sp: f"{sp.extra['family']}:{sp.section.groove}"),
             pan=128, kit=Kit(groups=(("kick_snare", ("kick", "snare")),
                                       ("hat_ride", ("hat", "ohat", "ride", "crash"))),
                              priority={"snare": 2, "crash": 3, "ohat": 2, "ride": 2},
                              single_priority={"snare": 4, "kick": 3, "crash": 2},
                              group_pan={"hat_ride": 164})),
        Part("bass", BreaksBass("bass", vol=50), pan=128),
        Part("comp", BreaksComp("ep", vol=42, wobble=EP_WOBBLE), pan=88),
        Part("lead", Lead("vox", ScaleRules(leap_probability=0.2, leap_semitones=(3, 4, 5, 7),
                                              dissonance_weight=0.1), LEAD_MOTIFS, vol=44, gate=0.9,
                           vibrato=0x33), pan=160),
        Part("pad", Pad("pad", vol=26), pan=64, min_channels=6),
        Part("lead echo", Echo(delay=3, ratio=0.45), follow="lead", pan=96, min_channels=8),
        Part("brass", Layer("brass", vol=30, chordal=True), follow="lead", pan=184, min_channels=8),
    )
    mod_channels = {4: 1, 6: 1, 8: 1}

    def plan(self, rng) -> SongPlan:
        names = list(FAMILIES)
        family = rng.choices(names, weights=[FAMILIES[n][0] for n in names])[0]
        base = default_plan(self, rng)
        base.bpm = rng.choice(FAMILIES[family][1])
        base.summary = [f"Rhythm      : {FAMILY_NAMES[family]}", *base.summary]
        base.extra = dict(base.extra, family=family)
        for sp in base.sections.values():
            sp.extra = dict(sp.extra, family=family)
        return base
