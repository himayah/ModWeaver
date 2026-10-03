"""anime-ost（旧 genres/anime_ost.py の宣言を機械変換したもの。FRAMEWORK_REDESIGN.md §15）。"""
from __future__ import annotations

from ..core.composer import RhythmMotif, ScaleRules
from ..core.model import ChordSpec, GmVoice
from ..core.synth_presets import PRESETS
from ..framework.gens import BassLine, Comp, Echo, Groove, Layer, Lead, hits
from ..framework.genre import Genre, Harmony, Instrument, Kit, Part, Section
from ..framework.context import Generator, MeasureCtx
from ..core.pitch import CHORD_QUALITIES, fold_into_range
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
    "main": hits("kick", (0, 10), 56) + hits("snare", (4, 12), 46) + hits("snare", (7, 15), 22, 0.5) + hits("ride", (0, 4, 6, 8, 12, 14), 30),
    "break": hits("kick", (0, 3, 6, 10), 58) + hits("snare", (4, 12), 52) + hits("snare", (9, 13, 14, 15), 36, 0.8) + hits("ride", (0, 6, 8, 14), 30),
    "fill": hits("snare", (8, 10, 12, 13, 14, 15), 48),
    "crash": hits("crash", (0,), 56),
}
LEAD_MOTIFS = {
    "verse": (RhythmMotif(rows=(0, 3, 6, 8, 12)), RhythmMotif(rows=(0, 2, 4, 6, 10)), RhythmMotif(rows=(0, 4, 6, 8, 10, 14))),
    "climax": (RhythmMotif(rows=(0, 6, 8)), RhythmMotif(rows=(0, 4, 8, 12)), RhythmMotif(rows=(0, 3, 6, 12))),
}
PROGRESSIONS = (
    ("i-iv-VII-III", (C(0, "m7", label="im7"), C(5, "m7", label="ivm7"), C(10, "dom7", label="VII7"), C(3, "maj7", label="IIImaj7"))),
    ("iim7b5-V7-i", (C(2, "m7b5", label="iim7b5"), C(7, "dom7", label="V7"), C(0, "m7", label="im7"), C(0, "m7", label="im7"))),
    ("VImaj7-V7-i", (C(8, "maj7", label="VImaj7"), C(7, "dom7", label="V7"), C(0, "m7", label="im7"), C(0, "m7", label="im7"))),
)


KIME = (0, 3, 6)                               # 決めのリズム（16分の 3+3）
SPIC_ACCENTS = (0, 3, 6, 8, 11, 14)
LEAD_BY_SECTION = {"b": "vln", "climax": "brass"}


class SpicStrings(Generator):
    """刻むスピッカート（旧 extra_measure）。"spic" の印の区間だけ。"kime" の印の区間の偶数小節は決め
    （place_kime が finalize_section で置く）なので鳴らさない。"""

    def __init__(self, inst: str) -> None:
        self.inst = inst

    def measure(self, m: MeasureCtx) -> None:
        tags = m.plan.section.tags
        if "spic" not in tags or ("kime" in tags and m.m.index % 2 == 0):
            return
        root = fold_into_range(m.m.chord.bass, 12, 23)
        tones = [root, root, fold_into_range(m.m.chord.bass + 7, 12, 23), root + 12 if root + 12 <= 30 else root]
        for step in range(min(16, m.m.steps)):
            vol = m.scale_vol(40 if step in SPIC_ACCENTS else 26)
            m.note(step, self.inst, tones[(step // 2) % len(tones)] if step % 2 == 0 else root, vel=vol)


def _drop(score, part: str, pred) -> None:
    score.parts[part] = [e for e in score.parts.get(part, []) if not pred(e)]


def place_kime(sec, score) -> None:
    """ブラス・ピアノ（和音のある区間だけ）・ベース・キック・クラッシュの決め（16分の 3+3）。他のパートより優先して
    置き換える（旧 _kime の buf.replace）。outro の最後の小節は、他のパートを全部止めて決めだけで終わる
    （3つ目のブラスを伸ばす）。"""
    if "kime" not in sec.section.tags:
        return
    chord_parts = tuple(score.parts)
    last = len(sec.measures) - 1

    def sv(v: int) -> int:
        return max(1, min(64, round(v * (0.55 + 0.45 * sec.intensity))))

    for m in sec.measures:
        final = sec.name == "outro" and m.index == last
        if not (m.index % 2 == 0 or final):
            continue
        if final:
            score.mute(chord_parts, m.start, m.start + m.steps)
        chord = m.chord
        top = fold_into_range(chord.harmony + 7, 14, 26)
        for row in KIME:
            at = m.start + row
            if not final:
                score.mute(("comp", "bass"), at, at + 1)
                _drop(score, "drums", lambda e, at=at: isinstance(e, NoteEvent) and e.step == at
                      and e.inst in ("kick", "snare"))
            dur = 2 if (not final and row == KIME[-1]) else None
            score.add("strings", NoteEvent(at, "brass", top, sv(50), dur=dur))
            if "comp" in sec.parts:
                score.add("comp", NoteEvent(at, "piano", chord.harmony, sv(46), chord=CHORD_QUALITIES[m.quality]))
            score.add("bass", NoteEvent(at, "bass", chord.bass, sv(54)))
            score.add("drums", NoteEvent(at, "kick", None, 56))
        if not final:
            _drop(score, "drums", lambda e, at=m.start: isinstance(e, NoteEvent) and e.step == at
                  and e.inst in ("ride", "crash"))
        score.add("drums", NoteEvent(m.start, "crash", None, 56))


@register_genre
class AnimeOstGenre(Genre):
    id = "anime-ost"
    category = "style"
    display_name = "Anime Soundtrack"
    description = "アニメ劇伴風。刻むストリングスとジャズの和声、ブラスの決め"
    description_en = "Anime soundtrack style: driving strings with jazz harmony and brass hits"
    title = "Anime Soundtrack"
    tempo_choices = (120, 126, 132, 138, 144, 150)

    instruments = {
        "kick": _inst("prog_kick", GmVoice(drum_note=36)),
        "snare": _inst("swing_brush_snare", GmVoice(drum_note=38)),
        "ride": _inst("swing_ride", GmVoice(drum_note=51)),
        "crash": _inst("march_crash_cymbal", GmVoice(drum_note=49)),
        "bass": _inst("swing_walk_bass", GmVoice(program=32)),
        "sax": _inst("swing_sax_lead", GmVoice(program=65)),
        "vln": _inst("orch_violin", GmVoice(program=48)),
        "brass": _inst("march_brass_section", GmVoice(program=61)),
        "spic": _inst("str_spiccato", GmVoice(program=48), volume=40),
        "piano": _inst("keys_piano", GmVoice(program=0), volume=42),
    }
    harmony = Harmony(keys=(2, 7), mode="aeolian", progressions=PROGRESSIONS, n_progressions=3)
    sections = {
        "intro": Section(intensity=0.8, parts=frozenset({"bass", "drums", "comp", "strings"}), crash=True, tags=frozenset({"kime", "spic"})),
        "a": Section(intensity=0.75, parts=frozenset({"lead", "bass", "drums", "comp"}), fill=True),
        "b": Section(prog=1, intensity=0.85, parts=frozenset({"bass", "drums", "comp", "strings", "lead"}), fill=True, tags=frozenset({"spic"})),
        "break": Section(prog=2, intensity=0.9, parts=frozenset({"strings", "bass", "drums"}), groove="break", crash=True, tags=frozenset({"kime"})),
        "climax": Section(prog=2, intensity=1.0, parts=frozenset({"bass", "drums", "comp", "strings", "lead"}), crash=True, motifs="climax", tags=frozenset({"spic"})),
        "outro": Section(intensity=0.9, parts=frozenset({"bass", "drums", "comp", "strings"}), tags=frozenset({"kime", "spic"})),
    }
    form = ("intro", "a", "b", "break", "a", "b", "climax", "outro")
    parts = (
        Part("drums", Groove(GROOVES), pan=128,
             kit=Kit(groups=(("kick/snare", ("kick", "snare")), ("ride/crash", ("ride", "crash"))),
                     priority={"snare": 2, "crash": 2},
                     single_priority={"kick": 3, "snare": 4, "ride": 1, "crash": 2},
                     group_pan={"ride/crash": 170})),
        Part("bass", BassLine("bass", kind="walking", vol=54), pan=128),
        Part("comp", Comp("piano", kind="charleston", vol=40), pan=88),
        Part("lead", Lead("sax", ScaleRules(leap_probability=0.3, leap_semitones=(3, 4, 5, 7)), LEAD_MOTIFS,
                   vol=46, gate=0.85, vibrato=0x23, inst_for=lambda sp: LEAD_BY_SECTION.get(sp.kind, "sax")), pan=150),
        Part("strings", SpicStrings("spic"), pan=64, min_channels=6,
             kit=Kit(groups=(("strings/brass", ("spic", "brass")),), priority={"brass": 2})),
        Part("lead echo", Echo(delay=3, ratio=0.45), follow="lead", pan=96, min_channels=8),
        Part("violin line", Layer("vln", vol=26, register=(19, 31)), follow="lead", pan=160, min_channels=8),
    )
    mod_channels = {4: 1, 6: 2, 8: 1}

    def finalize_section(self, sec, score, rng) -> None:
        place_kime(sec, score)
