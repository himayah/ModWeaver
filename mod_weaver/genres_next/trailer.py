"""trailer（旧 genres/trailer.py の宣言を機械変換したもの。FRAMEWORK_REDESIGN.md §15）。"""
# TODO(F6): 論理チャンネル ['braam', 'spiccato', 'fx'] を鳴らすパートが宣言に無い（上書きメソッドで鳴らす）
from __future__ import annotations

from ..core.composer import RhythmMotif, ScaleRules
from ..core.model import ChordSpec, GmVoice
from ..core.synth_presets import PRESETS
from ..framework.gens import BassLine, Groove, Lead, Pad, hits
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
    "main": hits("taiko", (0, 6, 8), 58) + hits("taiko", (14,), 44, 0.6),
    "full": hits("taiko", (0, 4, 6, 8, 12, 14), 60),
    "pulse": hits("taiko", (0, 4, 8, 12), 54),
}
LEAD_MOTIFS = {
    "verse": (RhythmMotif(rows=(0, 8)), RhythmMotif(rows=(0, 12)), RhythmMotif(rows=(0, 4, 8))),
}
PROGRESSIONS = (
    ("i-VI-III-VII", (C(0, "min", label="i"), C(8, "maj", label="VI"), C(3, "maj", label="III"), C(10, "maj", label="VII"))),
    ("i-bVI-bVII-i", (C(0, "min", label="i"), C(8, "maj", label="bVI"), C(10, "maj", label="bVII"), C(0, "min", label="i"))),
)


@register_genre
class TrailerGenre(Genre):
    id = "trailer"
    category = "style"
    display_name = "Cinematic Trailer"
    description = "映画予告編風。大太鼓と金管の衝撃、刻む弦、合唱で盛り上がる3幕構成"
    description_en = "Cinematic trailer style: taiko and brass hits, driving strings and choir in three acts"
    title = "Trailer: Three Acts"
    tempo_choices = (90, 92, 94, 96, 98, 100)

    instruments = {
        "taiko": _inst("perc_taiko", GmVoice(program=116)),
        "tom": _inst("drum_tom", GmVoice(drum_note=45)),
        "snare": _inst("march_snare", GmVoice(drum_note=38)),
        "braam": _inst("brass_braam", GmVoice(program=61)),
        "spic": _inst("str_spiccato", GmVoice(program=48)),
        "cello": _inst("orch_cello", GmVoice(program=42)),
        "vln": _inst("orch_violin", GmVoice(program=48)),
        "riser": _inst("fx_riser", GmVoice(program=97)),
        "impact": _inst("fx_impact", GmVoice(program=55)),
        "choir": _inst("vox_choir", GmVoice(program=52), volume=36),
    }
    harmony = Harmony(keys=(2, 0), mode="aeolian", progressions=PROGRESSIONS, n_progressions=2)
    sections = {
        "act1": Section(intensity=0.55, parts=frozenset({"hits"})),
        "act2": Section(intensity=0.75, parts=frozenset({"braam", "spic", "bass", "drums"})),
        "riser": Section(prog=1, intensity=0.85, parts=frozenset({"build", "spic", "bass", "drums"}), groove="pulse"),
        "act3": Section(prog=1, intensity=1.0, parts=frozenset({"braam", "bass", "drums", "pad", "spic", "toms", "lead"}), groove="full", key_offset=1),
        "final": Section(prog=1, intensity=0.9, parts=frozenset({"hits", "bass", "pad"}), key_offset=1),
    }
    form = ("act1", "act1", "act2", "act2", "riser", "act3", "act3", "final")
    parts = (
        Part("drums", Groove(GROOVES), pan=128,
             kit=Kit(groups=(("taiko", ("taiko",)), ("toms/snare", ("snare",))),
                     priority={"snare": 2},
                     single_priority={"taiko": 3, "snare": 2},
                     group_pan={"toms/snare": 150})),
        # TODO: Part("braam", <ジェネレータ>, pan=110)  ← 上書きメソッドで鳴らしていた
        # TODO: Part("spiccato", <ジェネレータ>, pan=80)  ← 上書きメソッドで鳴らしていた
        Part("bass", BassLine("cello", kind="half", vol=48), pan=128),
        Part("pad", Pad("choir", vol=38), pan=170),
        Part("lead", Lead("vln", ScaleRules(leap_probability=0.35, leap_semitones=(3, 4, 5, 7, 12)), LEAD_MOTIFS,
                   vol=50, gate=1.0, vibrato=0x24), pan=90),
        # TODO: Part("fx", <ジェネレータ>, pan=128, min_channels=8)  ← 上書きメソッドで鳴らしていた
    )
    mod_channels = {6: 1, 8: 2}
