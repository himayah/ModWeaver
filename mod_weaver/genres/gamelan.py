"""gamelan: ジャワのガムラン風（DESIGN.md §6.17）。6ch: クンダン・ゴング／クンプル・クノン／クトゥッ・サロン
（balungan＝骨格の旋律）・プキン（サロンの1オクターブ上、2倍の密度）・ボナン（4倍の密度の装飾）。

音律はスレンドロとペロッグ（5音）を seed で選ぶ。maqam と同じく ``MicroScale``＋``resolve_micronote`` で度数ごとに
（logical note, finetune）を求め、旋律楽器は finetune の値ごとの派生サンプルを持つ。音色空間の疎な領域
（非調和 × 長い減衰・低音域）を使う。

構造（lancaran）: 1拍＝4 row、1 measure＝1 gatra（4拍）、1 pattern＝1 gongan（16拍）。gong は16拍目、kenong は
4拍ごと、kempul は6・10・14拍目、ketuk は奇数拍。irama II の区間は balungan を半分の密度にして1 gongan を
2 pattern に広げ、装飾の楽器は細かく刻み続ける。balungan は plan() で作り、同じ gongan は同じ旋律になる。
"""
from __future__ import annotations

import dataclasses

from ..core.midi import GmVoice
from ..core.model import ChordSpec
from ..core.pitch import MicroScale, resolve_micronote
from ..profiles.band_common import BandProfile, ChannelDef, Section, _scale_vol, hits, preset
from ..profiles.registry import register_profile

C = ChordSpec
CH_KENDANG, CH_GONG, CH_KENONG, CH_SARON, CH_PEKING, CH_BONANG = range(6)

LARAS = {                                      # 音律（主音からのセント）
    "slendro": (0.0, 240.0, 480.0, 720.0, 960.0),
    "pelog": (0.0, 120.0, 270.0, 670.0, 780.0),  # ペロッグの5音（pathet の一つ）
}
FINETUNES = (-5, -4, -3, 0, 3, 5)              # 両音律の度数が使う finetune の値（DESIGN.md §6.17）
STRUCT_DEGREES = (0, 3)                        # kenong・kempul が打つ度数（主音と、その上の構造音）
N = 5                                          # 1オクターブの度数
GONG_OCTAVE = 12                               # gong ageng は主音の1オクターブ下（約 65〜123 Hz）で鳴らす


def _tag(ft: int) -> str:
    return "0" if ft == 0 else ("p" if ft > 0 else "m") + str(abs(ft))


def _variants(key: str, patch, fts=FINETUNES):
    return tuple((f"{key}_{_tag(ft)}", dataclasses.replace(patch, finetune=ft)) for ft in fts)


def _struct_fts() -> tuple[int, ...]:
    fts = {resolve_micronote(MicroScale(0, cents).degree_cents(d))[1] for cents in LARAS.values() for d in STRUCT_DEGREES}
    return tuple(sorted(fts))


KENDANG = (hits("dhe", (0, 7), 48) + hits("dhe", (8,), 40, 0.5) + hits("tak", (4, 10, 14), 38)
           + hits("tak", (12,), 30, 0.5) + hits("ketuk", (0, 8), 30))
BUKA = hits("dhe", (0, 6, 8, 11, 12), 46) + hits("tak", (3, 10, 14), 36)


@register_profile
class GamelanProfile(BandProfile):
    id = "gamelan"
    display_name = "Gamelan"
    description = "ガムラン風。青銅の鍵盤と壺型ゴングの重なり、周期的なゴングの区切りとスレンドロ／ペロッグ音律"
    description_en = "Gamelan style: interlocking bronze metallophones and gongs in slendro or pelog tuning"
    title = "Gamelan Lancaran"
    default_filename = "Gamelan.mod"
    tempo_choices = (84, 88, 92, 96, 100)

    KIT = (
        ("dhe", preset("gamelan_kendang_dhe")), ("tak", preset("gamelan_kendang_tak")),
        ("ketuk", preset("gamelan_ketuk")), ("gong", preset("gamelan_gong")),
        *_variants("kempul", preset("gamelan_kempul"), _struct_fts()),
        *_variants("kenong", preset("gamelan_kenong"), _struct_fts()),
        *_variants("saron", preset("gamelan_saron")),
        *_variants("bonang", preset("gamelan_bonang")),
    )
    CHANNELS = (
        ChannelDef("kendang", ("dhe", "tak"), (("dhe", 2),), pan=128),
        ChannelDef("gong/kempul", ("gong",) + tuple(k for k, _ in KIT if k.startswith("kempul")),
                   (("gong", 3),), pan=128),
        ChannelDef("kenong/ketuk", ("ketuk",) + tuple(k for k, _ in KIT if k.startswith("kenong")),
                   tuple((k, 2) for k, _ in KIT if k.startswith("kenong")), pan=170),
        ChannelDef("saron", tuple(k for k, _ in KIT if k.startswith("saron")), pan=100),
        ChannelDef("peking", tuple(k for k, _ in KIT if k.startswith("saron")), pan=190),
        ChannelDef("bonang", tuple(k for k, _ in KIT if k.startswith("bonang")), pan=64),
    )
    GM = {**{k: GmVoice(program=11) for k, _ in KIT if k.startswith("saron")},
          **{k: GmVoice(program=114) for k, _ in KIT if k.startswith("bonang")},
          **{k: GmVoice(program=14) for k, _ in KIT if k.startswith(("kenong", "kempul"))}}
    DRUM_CHANNEL = {"dhe": CH_KENDANG, "tak": CH_KENDANG, "ketuk": CH_KENONG}
    KEYS = (0, 2, 4, 5, 7, 9)
    PROGRESSIONS = (("gong tone", (C(0, "maj", label="gong"),)),)   # 和声は持たない（音律と balungan で書く）
    N_PROGRESSIONS = 1
    SECTIONS = {
        "buka": Section("buka", intensity=0.7, parts=frozenset({"drums", "bonang", "gong"}), groove="buka"),
        "lanc_a": Section("lanc_a", intensity=0.8, parts=frozenset({"drums", "colotomic", "saron", "peking", "bonang"})),
        "lanc_b": Section("lanc_b", intensity=0.85, parts=frozenset({"drums", "colotomic", "saron", "peking", "bonang"})),
        "irama2_1": Section("irama2_1", intensity=0.7, parts=frozenset({"drums", "colotomic", "saron", "peking", "bonang"})),
        "irama2_2": Section("irama2_2", intensity=0.7, parts=frozenset({"drums", "colotomic", "saron", "peking", "bonang"})),
        "suwuk": Section("suwuk", intensity=0.6, parts=frozenset({"drums", "colotomic", "saron", "peking", "bonang"})),
    }
    FORM = ("buka", "lanc_a", "lanc_b", "lanc_a", "lanc_b", "irama2_1", "irama2_2", "irama2_1", "irama2_2",
            "lanc_a", "suwuk")
    GROOVES = {"main": KENDANG, "buka": BUKA}
    # 区間 → (balungan の gongan, 1拍の row 数, その pattern が gongan の何拍目から始まるか)
    LAYOUT = {"buka": ("a", 4, 0), "lanc_a": ("a", 4, 0), "lanc_b": ("b", 4, 0), "irama2_1": ("a", 8, 0),
              "irama2_2": ("a", 8, 8), "suwuk": ("a", 4, 0)}

    # --- 計画: 音律と balungan ---
    def plan(self, rng):
        plan = super().plan(rng)
        laras = rng.plan.choice(sorted(LARAS))
        gongans = {"a": _balungan(rng.plan), "b": _balungan(rng.plan)}
        for pp in plan.patterns:
            name, rpb, start = self.LAYOUT[pp.kind]
            pp.extra.update(laras=laras, balungan=gongans[name], beat_rows=rpb, start=start)
        tonic = plan.patterns[0].extra["tonic"]
        summary = [f"Laras       : {laras} (tonic pc {tonic})",
                   "Balungan A  : " + " ".join(_notation(d) for d in gongans["a"]),
                   "Balungan B  : " + " ".join(_notation(d) for d in gongans["b"])]
        return dataclasses.replace(plan, summary=summary)

    # --- 作曲 ---
    def extra_measure(self, mctx, sec, st, rng, buf):
        ex = mctx.pattern.extra
        scale = MicroScale(ex["tonic"], LARAS[ex["laras"]])
        rpb, bal = ex["beat_rows"], ex["balungan"]
        per_measure = mctx.measure_rows // rpb
        first = ex["start"] + mctx.measure_idx * per_measure      # この measure の最初の拍（gongan の中の 0 始まり）
        ins = mctx.instruments
        base = ex["tonic"]                                        # saron の主音の logical note（0..11）

        def play(name: str, degree: int, octave_note: int):
            t, ft = resolve_micronote(scale.absolute_cents(degree, octave_note))
            return ins[f"{name}_{_tag(ft)}"], t

        if sec.kind == "buka":
            # ボナンの独奏で最後の gatra を示し、最後の小節でクンダンが入って gong で本編へ
            if mctx.measure_idx >= 2:
                for i in range(per_measure):
                    d = bal[12 + (mctx.measure_idx - 2) * 2 + i // 2]
                    inst, t = play("bonang", d, base + 12)
                    buf.put(i * rpb, CH_BONANG, inst.cell(t, vol=_scale_vol(40, sec)))
            if mctx.is_last:
                buf.put(12, CH_GONG, ins["gong"].cell(base - GONG_OCTAVE, vol=58))
            return
        for i in range(per_measure):
            k = first + i                                         # 拍（0..15）。16拍目＝k 15
            row = i * rpb
            d = bal[k]
            if "saron" in sec.parts:
                inst, t = play("saron", d, base)
                buf.put(row, CH_SARON, inst.cell(t, vol=_scale_vol(44, sec)))
            if "colotomic" in sec.parts:
                beat = k + 1
                if beat == 16:
                    buf.put(row, CH_GONG, ins["gong"].cell(base - GONG_OCTAVE, vol=60))
                elif beat in (6, 10, 14):
                    s = STRUCT_DEGREES[(d % N) != 0]
                    inst, t = play("kempul", s, base)
                    buf.put(row, CH_GONG, inst.cell(t, vol=_scale_vol(46, sec)))
                if beat % 4 == 0:
                    s = 0 if beat == 16 or d % N == 0 else STRUCT_DEGREES[1]
                    inst, t = play("kenong", s, base + 12)
                    buf.put(row, CH_KENONG, inst.cell(t, vol=_scale_vol(42, sec)))
        # 装飾: 拍の組（a, b）ごとに、プキンは a a b b（2倍）、ボナンは a b a b …（4倍）で先取りして刻む
        for pair in range(0, per_measure, 2):
            a = bal[(first + pair) % 16]
            b = bal[(first + pair + 1) % 16]
            span = 2 * rpb
            if "peking" in sec.parts:
                for j, d in enumerate((a, a, b, b)):
                    inst, t = play("saron", d, base + 12)
                    buf.put(pair * rpb + j * span // 4, CH_PEKING, inst.cell(t, vol=_scale_vol(34, sec)))
            if "bonang" in sec.parts:
                step = max(1, span // 8)
                for j in range(span // step):
                    inst, t = play("bonang", (a, b)[j % 2], base + 12)
                    buf.put(pair * rpb + j * step, CH_BONANG, inst.cell(t, vol=_scale_vol(32 if j % 2 else 36, sec)))


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
