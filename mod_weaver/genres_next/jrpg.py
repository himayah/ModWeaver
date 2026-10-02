"""jrpg（旧 genres/jrpg.py の宣言を機械変換したもの。FRAMEWORK_REDESIGN.md §15）。"""
# TODO(F6): 論理チャンネル ['brass'] を鳴らすパートが宣言に無い（上書きメソッドで鳴らす）
from __future__ import annotations

from ..core.composer import RhythmMotif, ScaleRules
from ..core.model import ChordSpec, GmVoice
from ..core.synth_presets import PRESETS
from ..framework.gens import Arp, BassLine, Echo, Groove, Layer, Lead, Pad, hits
from ..framework.genre import Genre, Harmony, Instrument, Kit, Part, Section
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
        "intro": Section(prog=3, intensity=0.9, parts=frozenset({"bass", "drums", "pad", "fanfare", "arp"})),
        "a": Section(intensity=0.75, parts=frozenset({"bass", "drums", "pad", "lead", "arp"})),
        "a2": Section(prog=1, intensity=0.8, parts=frozenset({"bass", "drums", "pad", "lead", "arp"}), fill=True),
        "b": Section(prog=2, intensity=0.85, parts=frozenset({"counter", "bass", "drums", "pad", "lead", "arp"}), fill=True, motifs="bridge"),
        "ending": Section(prog=3, intensity=0.9, parts=frozenset({"counter", "bass", "drums", "pad", "lead", "arp"})),
    }
    form = ("intro", "a", "a2", "b", "a", "a2", "ending")
    parts = (
        Part("drums", Groove(GROOVES), pan=128,
             kit=Kit(groups=(("timpani/snare", ("snare",)),))),
        Part("arp", Arp("harp", register=(17, 31), steps=(0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15), vol=30), pan=84),
        Part("bass", BassLine("cello", kind="half", vol=46), pan=128),
        Part("pad", Pad("str", vol=28), pan=172, min_channels=6),
        Part("lead", Lead("flute", ScaleRules(leap_semitones=(3, 4, 5, 7)), LEAD_MOTIFS,
                   vol=48, gate=0.9, vibrato=0x23), pan=150),
        # TODO: Part("brass", <ジェネレータ>, pan=100, min_channels=6)  ← 上書きメソッドで鳴らしていた
        Part("melody echo", Echo(delay=3, ratio=0.45), follow="lead", pan=96, min_channels=8),
        Part("choir", Layer("choir", vol=26, chordal=True), follow="pad", pan=160, min_channels=8),
    )
    mod_channels = {4: 1, 6: 2, 8: 1}
