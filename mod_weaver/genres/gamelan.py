"""gamelan: ジャワのガムラン風（旧 genres/gamelan.py の移植。FRAMEWORK_REDESIGN.md §15.3 のグループB）。

6ch: クンダン・ゴング／クンプル・クノン／クトゥッ・サロン（balungan＝骨格の旋律）・プキン（サロンの1オクターブ上、
2倍の密度）・ボナン（4倍の密度の装飾）。

音律はスレンドロとペロッグ（5音）を seed で選ぶ。度数ごとの音高は**小数の音高**（``MicroScale.absolute_cents ÷ 100``）で
書き、finetune ごとの派生サンプルは Realizer が作る（MOD は finetune の変種、他形式は再生レートの変種）。

構造（lancaran）: 1拍＝4 step、1小節＝1 gatra（4拍）、1区間＝1 gongan（16拍）。gong は16拍目、kenong は4拍ごと、
kempul は6・10・14拍目、ketuk は奇数拍。irama II の区間は balungan を半分の密度にして1 gongan を2区間に広げ、装飾の
楽器は細かく刻み続ける。balungan は ``plan()`` で作り、同じ gongan は同じ旋律になる。

旧版との違い: ketuk は旧版では打楽器の型（KENDANG）の中にあったが、旧版の物理チャンネルは「クノンと同じチャンネル」
だったので、colotomic パートの kit（kenong/ketuk の lane）に移した。
"""
from __future__ import annotations

import dataclasses

from ..core.model import ChordSpec, GmVoice
from ..core.pitch import MicroScale
from ..core.synth_presets import PRESETS
from ..framework.context import Generator, MeasureCtx
from ..framework.gens import Groove, hits
from ..framework.genre import Genre, Harmony, Instrument, Kit, Part, Section
from ..framework.plan import SongPlan, default_plan
from ..framework.registry import register_genre

C = ChordSpec

LARAS = {                                      # 音律（主音からのセント）
    "slendro": (0.0, 240.0, 480.0, 720.0, 960.0),
    "pelog": (0.0, 120.0, 270.0, 670.0, 780.0),  # ペロッグの5音（pathet の一つ）
}
STRUCT_DEGREES = (0, 3)                        # kenong・kempul が打つ度数（主音と、その上の構造音）
N = 5                                          # 1オクターブの度数
GONG_OCTAVE = 12                               # gong ageng は主音の1オクターブ下（約 65〜123 Hz）で鳴らす

KENDANG = (hits("dhe", (0, 7), 48) + hits("dhe", (8,), 40, 0.5) + hits("tak", (4, 10, 14), 38)
           + hits("tak", (12,), 30, 0.5))
BUKA = hits("dhe", (0, 6, 8, 11, 12), 46) + hits("tak", (3, 10, 14), 36)
GROOVES = {"main": KENDANG, "buka": BUKA}
KETUK_STEPS = (0, 8)                           # 旧版は KENDANG の中の ``hits("ketuk", (0, 8), 30)``

# 区間 → (balungan の gongan, 1拍の step 数, その区間が gongan の何拍目から始まるか)
LAYOUT = {"buka": ("a", 4, 0), "lanc_a": ("a", 4, 0), "lanc_b": ("b", 4, 0), "irama2_1": ("a", 8, 0),
          "irama2_2": ("a", 8, 8), "suwuk": ("a", 4, 0)}


def _inst(key: str, gm: GmVoice) -> Instrument:
    return Instrument(patch=PRESETS[key], gm=gm)


def _balungan(rng) -> tuple[int, ...]:
    """1 gongan（4 gatra × 4拍）の balungan。度数は 0..5（5＝1オクターブ上の主音）。
    gatra の最後の音（seleh）を構造音にし、順次進行を主に、最後の gatra は主音（0 か 5）で終わる。"""
    notes: list[int] = []
    cur = rng.choice((0, 1, 2))
    for g in range(4):
        for i in range(3):
            step = rng.choice((-1, 1, 1, -2, 2, 0)) if i else rng.choice((-1, 1))
            cur = min(5, max(0, cur + step))
            notes.append(cur)
        if g == 3:
            seleh = 0 if cur <= 2 else 5
        else:
            seleh = min((1, 2, 3, 4), key=lambda s: (abs(s - cur), rng.random()))
        notes.append(seleh)
        cur = seleh
    return tuple(notes)


def _notation(d: int) -> str:
    """ジャワの数字譜風の表記（スレンドロの 1 2 3 5 6 に当てる。上のオクターブは '）。"""
    return ("1", "2", "3", "5", "6")[d % N] + ("'" if d >= N else "")


def _pitch(m: MeasureCtx, degree: int, tonic_note: int) -> float:
    """度数 ``degree`` の書かれた音高（小数。1 = 100 セント）。音律はこの区間の ``extra['laras']``。"""
    scale = MicroScale(m.plan.tonic, LARAS[m.plan.extra["laras"]])
    return scale.absolute_cents(degree, tonic_note) / 100.0


def _beats(m: MeasureCtx) -> tuple[int, int, int, list[int]]:
    ex = m.plan.extra
    rpb = ex["beat_rows"]
    per_measure = m.m.steps // rpb
    first = ex["start"] + m.m.index * per_measure       # この小節の最初の拍（gongan の中の 0 始まり）
    return rpb, per_measure, first, ex["balungan"]


class Colotomic(Generator):
    """ゴング・クンプル・クノン・クトゥッ（周期的な区切り）。buka は最後の小節の頭でゴングだけ（本編へ入る合図）。"""

    def measure(self, m: MeasureCtx) -> None:
        base = m.plan.tonic
        if "buka" in m.plan.section.tags:
            if m.is_last:
                m.note(12, "gong", base - GONG_OCTAVE, vel=58)
            return
        rpb, per_measure, first, bal = _beats(m)
        for step in KETUK_STEPS:
            m.note(step, "ketuk", vel=m.scale_drum(30))
        for i in range(per_measure):
            k = first + i                               # 拍（0..15）。16拍目＝k 15
            step, d, beat = i * rpb, bal[k], k + 1
            if beat == 16:
                m.note(step, "gong", base - GONG_OCTAVE, vel=60)
            elif beat in (6, 10, 14):
                s = STRUCT_DEGREES[(d % N) != 0]
                m.note(step, "kempul", _pitch(m, s, base), vel=m.scale_vol(46))
            if beat % 4 == 0:
                s = 0 if beat == 16 or d % N == 0 else STRUCT_DEGREES[1]
                m.note(step, "kenong", _pitch(m, s, base + 12), vel=m.scale_vol(42))


class Saron(Generator):
    """balungan（骨格の旋律）を拍ごとに打つ。"""

    def measure(self, m: MeasureCtx) -> None:
        rpb, per_measure, first, bal = _beats(m)
        for i in range(per_measure):
            m.note(i * rpb, "saron", _pitch(m, bal[first + i], m.plan.tonic), vel=m.scale_vol(44))


class Peking(Generator):
    """プキン: サロンの1オクターブ上。拍の組（a, b）を a a b b（2倍の密度）で先取りして刻む。"""

    def measure(self, m: MeasureCtx) -> None:
        rpb, per_measure, first, bal = _beats(m)
        base = m.plan.tonic
        for pair in range(0, per_measure, 2):
            a, b = bal[(first + pair) % 16], bal[(first + pair + 1) % 16]
            span = 2 * rpb
            for j, d in enumerate((a, a, b, b)):
                m.note(pair * rpb + j * span // 4, "saron", _pitch(m, d, base + 12), vel=m.scale_vol(34))


class Bonang(Generator):
    """ボナン: 拍の組を a b a b …（4倍の密度）で刻む。buka はボナンの独奏で最後の gatra を示す。"""

    def measure(self, m: MeasureCtx) -> None:
        rpb, per_measure, first, bal = _beats(m)
        base = m.plan.tonic
        if "buka" in m.plan.section.tags:
            if m.m.index >= 2:
                for i in range(per_measure):
                    d = bal[12 + (m.m.index - 2) * 2 + i // 2]
                    m.note(i * rpb, "bonang", _pitch(m, d, base + 12), vel=m.scale_vol(40))
            return
        for pair in range(0, per_measure, 2):
            a, b = bal[(first + pair) % 16], bal[(first + pair + 1) % 16]
            span = 2 * rpb
            step = max(1, span // 8)
            for j in range(span // step):
                m.note(pair * rpb + j * step, "bonang", _pitch(m, (a, b)[j % 2], base + 12),
                       vel=m.scale_vol(32 if j % 2 else 36))


_FULL = frozenset({"drums", "colotomic", "saron", "peking", "bonang"})


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
        "kempul": _inst("gamelan_kempul", GmVoice(program=14)),
        "kenong": _inst("gamelan_kenong", GmVoice(program=14)),
        "saron": _inst("gamelan_saron", GmVoice(program=11)),
        "bonang": _inst("gamelan_bonang", GmVoice(program=114)),
    }
    harmony = Harmony(keys=(0, 2, 4, 5, 7, 9), mode="ionian",
                      progressions=(("gong tone", (C(0, "maj", label="gong"),)),), n_progressions=1)
    sections = {
        "buka": Section(intensity=0.7, parts=frozenset({"drums", "bonang", "colotomic"}), groove="buka",
                        tags=frozenset({"buka"})),
        "lanc_a": Section(intensity=0.8, parts=_FULL),
        "lanc_b": Section(intensity=0.85, parts=_FULL),
        "irama2_1": Section(intensity=0.7, parts=_FULL),
        "irama2_2": Section(intensity=0.7, parts=_FULL),
        "suwuk": Section(intensity=0.6, parts=_FULL),
    }
    form = ("buka", "lanc_a", "lanc_b", "lanc_a", "lanc_b", "irama2_1", "irama2_2", "irama2_1", "irama2_2",
            "lanc_a", "suwuk")
    parts = (
        Part("drums", Groove(GROOVES), pan=128, kit=Kit(groups=(("kendang", ("dhe", "tak")),),
                                                         priority={"dhe": 2})),
        Part("colotomic", Colotomic(), pan=128,
             kit=Kit(groups=(("gong/kempul", ("gong", "kempul")), ("kenong/ketuk", ("ketuk", "kenong"))),
                     priority={"gong": 3, "kenong": 2}, group_pan={"kenong/ketuk": 170})),
        Part("saron", Saron(), pan=100),
        Part("peking", Peking(), pan=190),
        Part("bonang", Bonang(), pan=64),
    )
    mod_channels = {6: 1}

    # --- 計画: 音律と balungan ---
    def plan(self, rng) -> SongPlan:
        base = default_plan(self, rng)
        laras = rng.choice(sorted(LARAS))
        gongans = {"a": _balungan(rng), "b": _balungan(rng)}
        for name, sp in base.sections.items():
            gongan, rpb, start = LAYOUT[name]
            sp.extra = dict(sp.extra, laras=laras, balungan=gongans[gongan], beat_rows=rpb, start=start)
        tonic = next(iter(base.sections.values())).tonic
        base.summary = [f"Laras       : {laras} (tonic pc {tonic})",
                        "Balungan A  : " + " ".join(_notation(d) for d in gongans["a"]),
                        "Balungan B  : " + " ".join(_notation(d) for d in gongans["b"])]
        return base
