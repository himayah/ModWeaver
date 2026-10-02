"""gamelan（旧 genres/gamelan.py の宣言を機械変換したもの。FRAMEWORK_REDESIGN.md §15）。"""
# TODO(F6): 論理チャンネル ['gong/kempul', 'saron', 'peking', 'bonang'] を鳴らすパートが宣言に無い（上書きメソッドで鳴らす）
from __future__ import annotations

from ..core.model import ChordSpec, GmVoice
from ..core.synth_presets import PRESETS
from ..framework.gens import Groove, hits
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
    "main": hits("dhe", (0, 7), 48) + hits("dhe", (8,), 40, 0.5) + hits("tak", (4, 10, 14), 38) + hits("tak", (12,), 30, 0.5) + hits("ketuk", (0, 8), 30),
    "buka": hits("dhe", (0, 6, 8, 11, 12), 46) + hits("tak", (3, 10, 14), 36),
}
PROGRESSIONS = (
    ("gong tone", (C(0, "maj", label="gong"),)),
)


@register_genre
class GamelanGenre(Genre):
    id = "gamelan"
    display_name = "Gamelan"
    description = "ガムラン風。青銅の鍵盤と壺型ゴングの重なり、周期的なゴングの区切りとスレンドロ／ペロッグ音律"
    description_en = "Gamelan style: interlocking bronze metallophones and gongs in slendro or pelog tuning"
    title = "Gamelan Lancaran"
    tempo_choices = (84, 88, 92, 96, 100)

    instruments = {
        "dhe": _inst("gamelan_kendang_dhe", GmVoice(drum_note=64)),
        "tak": _inst("gamelan_kendang_tak", GmVoice(drum_note=62)),
        "ketuk": _inst("gamelan_ketuk", GmVoice(drum_note=77)),
        "gong": _inst("gamelan_gong", GmVoice(program=14)),
        "kempul_m4": _inst("gamelan_kempul", GmVoice(program=14), finetune=-4),
        "kempul_0": _inst("gamelan_kempul", GmVoice(program=14)),
        "kempul_p3": _inst("gamelan_kempul", GmVoice(program=14), finetune=3),
        "kenong_m4": _inst("gamelan_kenong", GmVoice(program=14), finetune=-4),
        "kenong_0": _inst("gamelan_kenong", GmVoice(program=14)),
        "kenong_p3": _inst("gamelan_kenong", GmVoice(program=14), finetune=3),
        "saron_m5": _inst("gamelan_saron", GmVoice(program=11), finetune=-5),
        "saron_m4": _inst("gamelan_saron", GmVoice(program=11), finetune=-4),
        "saron_m3": _inst("gamelan_saron", GmVoice(program=11), finetune=-3),
        "saron_0": _inst("gamelan_saron", GmVoice(program=11)),
        "saron_p3": _inst("gamelan_saron", GmVoice(program=11), finetune=3),
        "saron_p5": _inst("gamelan_saron", GmVoice(program=11), finetune=5),
        "bonang_m5": _inst("gamelan_bonang", GmVoice(program=114), finetune=-5),
        "bonang_m4": _inst("gamelan_bonang", GmVoice(program=114), finetune=-4),
        "bonang_m3": _inst("gamelan_bonang", GmVoice(program=114), finetune=-3),
        "bonang_0": _inst("gamelan_bonang", GmVoice(program=114)),
        "bonang_p3": _inst("gamelan_bonang", GmVoice(program=114), finetune=3),
        "bonang_p5": _inst("gamelan_bonang", GmVoice(program=114), finetune=5),
    }
    harmony = Harmony(keys=(0, 2, 4, 5, 7, 9), mode="ionian", progressions=PROGRESSIONS, n_progressions=1)
    sections = {
        "buka": Section(intensity=0.7, parts=frozenset({"bonang", "gong", "drums"}), groove="buka"),
        "lanc_a": Section(intensity=0.8, parts=frozenset({"bonang", "drums", "colotomic", "saron", "peking"})),
        "lanc_b": Section(intensity=0.85, parts=frozenset({"bonang", "drums", "colotomic", "saron", "peking"})),
        "irama2_1": Section(intensity=0.7, parts=frozenset({"bonang", "drums", "colotomic", "saron", "peking"})),
        "irama2_2": Section(intensity=0.7, parts=frozenset({"bonang", "drums", "colotomic", "saron", "peking"})),
        "suwuk": Section(intensity=0.6, parts=frozenset({"bonang", "drums", "colotomic", "saron", "peking"})),
    }
    form = ("buka", "lanc_a", "lanc_b", "lanc_a", "lanc_b", "irama2_1", "irama2_2", "irama2_1", "irama2_2", "lanc_a", "suwuk")
    parts = (
        Part("drums", Groove(GROOVES), pan=128,
             kit=Kit(groups=(("kendang", ("dhe", "tak")), ("kenong/ketuk", ("ketuk",))),
                     priority={"dhe": 2},
                     group_pan={"kenong/ketuk": 170})),
        # TODO: Part("gong/kempul", <ジェネレータ>, pan=128)  ← 上書きメソッドで鳴らしていた
        # TODO: Part("saron", <ジェネレータ>, pan=100)  ← 上書きメソッドで鳴らしていた
        # TODO: Part("peking", <ジェネレータ>, pan=190)  ← 上書きメソッドで鳴らしていた
        # TODO: Part("bonang", <ジェネレータ>, pan=64)  ← 上書きメソッドで鳴らしていた
    )
    mod_channels = {6: 1}
