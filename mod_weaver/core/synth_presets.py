"""動作・音質を確認済みの ``synth.Patch`` 値を集めた参照ライブラリ（全12ジャンル・60プリセット）。

ここに集めるのは「型としての分類」ではなく「検索・流用のための参照データ」であり、
``core/synth.py`` の型システムには一切影響しない。新しい音色が欲しいときは、
``find()`` で近い説明のプリセットを探し ``dataclasses.replace(既存Patch, ...)`` で
差分だけ変えて ``synth.render()`` → 試聴し、良ければ ``register()`` で本モジュールへ
追加する（ゼロから ``Patch`` を組み立てない）。

セクションはジャンルごと（下の見出しコメント参照）。各ジャンルの設計意図・実証対象の
core 拡張は GENRE_DESIGN_V2.md の対応する章にまとめてある。
"""
from __future__ import annotations

import dataclasses

from . import dsp
from .synth import FilterSpec, Loop, NoiseLayer, OneShot, Patch, PitchSweepLayer, ToneLayer, WeightedLayer

PRESETS: dict[str, Patch] = {}
DESCRIPTIONS: dict[str, str] = {}


def register(key: str, patch: Patch, description: str) -> Patch:
    """プリセットを登録してそのまま返す。``X = register("x", Patch(...), "...")`` の形で使う。"""
    if key in PRESETS:
        raise ValueError(f"duplicate preset key: {key!r}")
    PRESETS[key] = patch
    DESCRIPTIONS[key] = description
    return patch


def find(keyword: str) -> list[str]:
    """説明文に ``keyword``（大小無視）を含むプリセットの key 一覧。"""
    kw = keyword.lower()
    return [k for k, d in DESCRIPTIONS.items() if kw in d.lower()]


# ============================================================
# 移行済み音色（動作・構造テスト確認済み。移行元は各エントリのコメント参照）
# ============================================================

SUB_HEARTBEAT = register(
    "sub_heartbeat",
    Patch(
        "SubHeartbeat",
        (WeightedLayer(PitchSweepLayer(freq_start=64.0, freq_end=38.0, pitch_decay=45.0, decay_alpha=8.0)),),
        OneShot(0.40),
        pitched=False, attack_ms=4.0, saturate=1.4, rate_note=24, volume=62,
    ),
    "低く沈み込むサブベース心拍/キック。64Hz から 38Hz へ収束するピッチドロップ、"
    "4ms アタック、e^(-8t) 減衰。suspense-slow/suspense-chase の heart 由来。",
)

METAL_ANVIL = register(
    "metal_anvil",
    Patch(
        "MetalAnvil",
        (
            WeightedLayer(ToneLayer((
                (920.0, 1.0, 5.5), (1430.0, 0.8, 7.5), (2150.0, 0.6, 10.0),
                (3370.0, 0.35, 14.0), (5210.0, 0.2, 20.0),
            ))),
            WeightedLayer(NoiseLayer(decay_alpha=1500.0), weight=0.6),
        ),
        OneShot(0.9),
        pitched=False, saturate=1.2, rate_note=35, volume=64, peak=1.0, noise_seed=2,
    ),
    "非整合倍音（920/1430/2150/3370/5210Hz）の金属打撃。約3ms のノイズ transient を伴う。"
    "高域を含むため rate_note=B-3 で生成。suspense-slow/suspense-chase の anvil 由来。",
)

NOISE_SWOOSH = register(
    "noise_swoosh",
    Patch(
        "NoiseSwoosh",
        (WeightedLayer(NoiseLayer(rise_power=2.2, filter=FilterSpec("lp_sweep", a_start=0.65, a_end=0.15))),),
        OneShot(0.9),
        pitched=False, tail_fade_ms=8000.0 / dsp.sample_rate(24), rate_note=24, volume=44, noise_seed=3,
    ),
    "フィルタが開く向き（0.65→0.15）で徐々に立ち上がるノイズの風切り。末尾8サンプルで急減衰し"
    "クリックを防ぐ。suspense-slow/suspense-chase の swoosh 由来。",
)

LOW_DRONE_BASS = register(
    "low_drone_bass",
    Patch(
        "LowDroneBass",
        (WeightedLayer(ToneLayer((
            (6.0, 1.0, None), (18.0, 1.0 / 3, None), (30.0, 0.2, None), (42.0, 1.0 / 7, None), (3.0, 0.6, None),
        ), filter=FilterSpec("lp", a=0.35))),),
        Loop(760, 60),
        pitched=True, saturate=1.1, rate_note=24, shift=-24, volume=60, peak=1.0,
    ),
    "低く唸る持続ベースドローン。奇数倍音(1,3,5,7次)+サブ(3cycle)を循環LPで温かく丸める。"
    "K=6, L=760（65.41Hz基準）。suspense-slow/suspense-chase の drone 由来。",
)

PIZZ_STAB = register(
    "pizz_stab",
    Patch(
        "PizzStab",
        (
            WeightedLayer(ToneLayer((
                (1.0, 1.0, 12.5), (2.0, 0.6, 18.0), (3.0, 0.35, 26.0), (4.0, 0.2, 38.0),
            ))),
            WeightedLayer(NoiseLayer(decay_alpha=2300.0), weight=0.3),
        ),
        OneShot(0.40),
        pitched=True, rate_note=24, shift=0, volume=56, noise_seed=5,
    ),
    "撥弦系のピチカート・スタブ。基音+倍音3つがそれぞれ異なる速さで減衰、2ms程度のクリック transient。"
    "suspense-slow/suspense-chase の pizz 由来。",
)

TENSION_STRINGS = register(
    "tension_strings",
    Patch(
        "TensionStrings",
        (WeightedLayer(ToneLayer(tuple(
            (float(k), w, None) for k, w in (
                (130, 1.0), (131, 1.0), (138, 0.8), (139, 0.8),
                (260, 0.35), (262, 0.35), (276, 0.28), (278, 0.28),
                (390, 0.15), (393, 0.15), (414, 0.12), (417, 0.12),
            )
        ))),),
        Loop(4144, 200),
        pitched=True, rate_note=24, shift=0, volume=40, peak=0.95,
    ),
    "同音デチューン対2組（130/131, 138/139 cycle）によるうなりを持つ持続ストリングス。"
    "suspense-slow/suspense-chase の strings 由来。",
)

SCREAMING_LEAD = register(
    "screaming_lead",
    Patch(
        "ScreamingLead",
        (WeightedLayer(ToneLayer(tuple((12.0 * h, 1.0 / h ** 0.8, None) for h in range(1, 8)))),),
        Loop(190, 80),
        pitched=True, rate_note=24, shift=12, volume=46, peak=0.95,
    ),
    "鋭く鳴く持続リード。倍音1〜7次、重み1/h^0.8（急峻な減衰カーブ）。"
    "suspense-slow/suspense-chase の lead 由来。",
)

MARCH_BASS_DRUM = register(
    "march_bass_drum",
    Patch(
        "MarchBassDrum",
        (
            WeightedLayer(PitchSweepLayer(freq_start=120.0, freq_end=85.0, pitch_decay=25.0, decay_alpha=14.0)),
            WeightedLayer(NoiseLayer(decay_alpha=2300.0), weight=0.5),
        ),
        OneShot(0.25),
        pitched=False, saturate=1.3, rate_note=24, volume=60, peak=1.0, noise_seed=101,
    ),
    "行進曲の芯のあるバスドラム。120Hzから85Hzへ収束するピッチドロップ、2ms程度のクリック。march の bd 由来。",
)

MARCH_SNARE = register(
    "march_snare",
    Patch(
        "MarchSnare",
        (
            WeightedLayer(ToneLayer(((220.0, 1.0, 30.0),)), weight=0.6),
            WeightedLayer(NoiseLayer(decay_alpha=18.0, filter=FilterSpec("hp")), weight=0.8),
        ),
        OneShot(0.22),
        pitched=False, saturate=1.25, rate_note=24, volume=52, noise_seed=102,
    ),
    "行進曲のスネア。220Hz のヘッドトーン（速い減衰）+ HP ノイズのスナッピー（遅い減衰）。march の sd 由来。",
)

MARCH_CRASH_CYMBAL = register(
    "march_crash_cymbal",
    Patch(
        "CrashCymbal",
        (
            WeightedLayer(ToneLayer(tuple((f, 0.2, 6.0) for f in (2100.0, 3300.0, 4700.0, 6100.0, 7300.0)))),
            WeightedLayer(NoiseLayer(decay_alpha=6.0, filter=FilterSpec("hp")), weight=0.5),
        ),
        OneShot(1.0),
        pitched=False, saturate=1.15, rate_note=35, volume=50, noise_seed=103,
    ),
    "非整合倍音（2100/3300/4700/6100/7300Hz）+ HP ノイズのクラッシュシンバル。全成分が同じ速さ(6.0)で減衰。"
    "march の crash 由来。",
)

MARCH_TUBA_BASS = register(
    "march_tuba_bass",
    Patch(
        "TubaBass",
        (WeightedLayer(ToneLayer(
            tuple((m, 0.6 * w, None) for m, w in dsp.partials_triangle(6))
            + tuple((m, 0.4 * w, None) for m, w in dsp.partials_square(6)),
            filter=FilterSpec("lp", a=0.25),
        )),),
        OneShot(0.35),
        pitched=True, attack_ms=8.0, decay_alpha=7.0, rate_note=24, shift=-12, volume=60,
    ),
    "三角波+矩形波(LP)を混ぜたスタッカートのチューバ。フィルタ後に一律減衰。march の tuba 由来。",
)

MARCH_BRASS_HORN = register(
    "march_brass_horn",
    Patch(
        "BrassHorn",
        (WeightedLayer(ToneLayer(
            tuple((m, w, None) for m, w in dsp.partials_saw(8)), filter=FilterSpec("lp", a=0.2),
        )),),
        OneShot(0.20),
        pitched=True, attack_ms=8.0, decay_alpha=9.0, rate_note=24, shift=0, volume=46,
    ),
    "ノコギリ波近似（h=1..8）+ LP のブラスホルン。フィルタ後に一律減衰。march の horn 由来。",
)

MARCH_BRASS_SECTION = register(
    "march_brass_section",
    Patch(
        "BrassSection",
        (WeightedLayer(ToneLayer(
            tuple((6.0 * h, w, None) for h, w in enumerate((1.0, 0.7, 0.5, 0.35, 0.2, 0.12), start=1))
        )),),
        Loop(190, 100),
        pitched=True, rate_note=24, shift=0, volume=44,
    ),
    "偶数倍音豊富な持続ブラスセクション。K=6, L=190。march の section 由来。",
)

MARCH_PICCOLO_LEAD = register(
    "march_piccolo_lead",
    Patch(
        "PiccoloLead",
        (WeightedLayer(ToneLayer(tuple((12.0 * h, 1.0 / h ** 0.9, None) for h in range(1, 8)))),),
        Loop(190, 60),
        pitched=True, rate_note=24, shift=12, volume=50,
    ),
    "鋭く抜けるピッコロリード。倍音1..7、重み1/h^0.9。K=12, L=190。march の picc 由来。",
)

# ------------------------------------------------------------
# nostalgic（旧 gen_* を移行。tanh 前の正規化を行わない流儀のため peak=None が多い）
# ------------------------------------------------------------

NOSTALGIC_KICK = register(
    "nostalgic_kick",
    Patch(
        "LoFiKick",
        (WeightedLayer(PitchSweepLayer(freq_start=110.0, freq_end=46.0, pitch_decay=30.0, decay_alpha=11.5)),),
        OneShot(0.20),
        pitched=False, saturate=1.3, peak=None, rate_note=24, volume=56,
    ),
    "丸く温かい Lo-Fi キック。110Hz から 46Hz へ収束するピッチドロップ。nostalgic の kick 由来。",
)

NOSTALGIC_SNARE = register(
    "nostalgic_snare",
    Patch(
        "SoftSnare",
        (
            WeightedLayer(ToneLayer(((175.0, 1.0, 22.0),)), weight=0.45),
            WeightedLayer(NoiseLayer(decay_alpha=14.0, filter=FilterSpec("lp", a=0.35)), weight=0.55),
        ),
        OneShot(0.18),
        pitched=False, saturate=1.25, peak=None, rate_note=24, volume=50, noise_seed=42,
    ),
    "乾いた柔らかい Lo-Fi スネア。175Hz のヘッドトーン + LP ノイズのボディ。nostalgic の snare 由来。",
)

NOSTALGIC_HIHAT = register(
    "nostalgic_hihat",
    Patch(
        "ClosedHH",
        (
            WeightedLayer(NoiseLayer(), weight=0.85),
            WeightedLayer(ToneLayer(((3200.0, 0.25, None), (4400.0, 0.25, None))), weight=0.85),
        ),
        OneShot(0.045),
        pitched=False, post_filter=FilterSpec("hp"), decay_alpha=65.0, saturate=1.4, peak=None,
        rate_note=24, volume=42, noise_seed=123,
    ),
    "繊細なクローズドハイハット。ノイズ + 2つの金属的なリングトーン(3200/4400Hz)を一括HP。"
    "nostalgic の hihat 由来。",
)

NOSTALGIC_BASS = register(
    "nostalgic_bass",
    Patch(
        "WarmBass",
        (WeightedLayer(ToneLayer(((1.0, 0.80, 3.2), (2.0, 0.20, 3.2)))),),
        OneShot(0.72),
        pitched=True, attack_ms=5.0, saturate=1.25, peak=None, rate_note=24, shift=0, volume=60,
    ),
    "丸みのあるアコースティック風ベース。基音+2倍音、5msアタック。nostalgic の bass 由来。",
)

NOSTALGIC_MUSICBOX = register(
    "nostalgic_musicbox",
    Patch(
        "MusicBox",
        (WeightedLayer(ToneLayer((
            (1.0, 0.55, 2.0), (2.0, 0.25, 3.5), (3.0, 0.12, 5.0), (5.4, 0.08, 12.0),
        ))),),
        OneShot(1.15),
        pitched=True, attack_ms=1.5, saturate=1.1, peak=None, rate_note=24, shift=0, volume=60,
    ),
    "澄んだオルゴール/トイチャイム。4倍音（非整数次含む）がそれぞれ異なる速さで減衰。"
    "nostalgic の musicbox 由来。",
)

NOSTALGIC_PAD = register(
    "nostalgic_pad",
    Patch(
        "TwilightPad",
        (WeightedLayer(ToneLayer((
            (32.0, 0.55, None), (64.0, 0.22, None), (96.0, 0.08, None), (16.0, 0.30, None),
        ))),),
        Loop(1024, 0),
        pitched=True, saturate=0.95, peak=None, rate_note=24, shift=0, volume=46,
    ),
    "温かいアナログ・ストリングスパッド。K=32, L=1024、アタック窓なしで sample 0 から直接ループ。"
    "nostalgic の pad 由来。",
)

NOSTALGIC_FLUTE = register(
    "nostalgic_flute",
    Patch(
        "MellowFlute",
        (WeightedLayer(ToneLayer((
            (32.0, 0.72, None), (96.0, 0.16, None), (160.0, 0.06, None),
        ))),),
        Loop(1024, 0),
        pitched=True, saturate=1.05, peak=None, rate_note=24, shift=0, volume=52,
    ),
    "素朴な木管風リード。奇数倍音(1,3,5次)、K=32, L=1024、アタック窓なし。nostalgic の flute 由来。",
)

# ------------------------------------------------------------
# swing-jazz（GENRE_DESIGN_V2.md §1。EXT-1 スウィングの実証ジャンル）
# ------------------------------------------------------------

SWING_RIDE = register(
    "swing_ride",
    Patch(
        "SwingRide",
        (
            WeightedLayer(ToneLayer((
                (3150.0, 0.5, 5.0), (4450.0, 0.4, 7.0), (5900.0, 0.3, 9.5), (7600.0, 0.2, 13.0),
            ))),
            WeightedLayer(NoiseLayer(decay_alpha=7.5, filter=FilterSpec("hp")), weight=0.35),
        ),
        OneShot(0.9),
        pitched=False, post_filter=FilterSpec("hp"), saturate=1.1, rate_note=35, volume=46, noise_seed=201,
    ),
    "スウィングジャズのライドシンバル。非整合倍音(3150/4450/5900/7600Hz、各異なる減衰)+HPノイズを"
    "全体HPで締める。march の crash より短く・明るい「ディン」。swing-jazz の ride 由来。",
)

SWING_BRUSH_SNARE = register(
    "swing_brush_snare",
    Patch(
        "SwingBrushSnare",
        (WeightedLayer(NoiseLayer(decay_alpha=22.0, filter=FilterSpec("lp", a=0.4))),),
        OneShot(0.12),
        pitched=False, attack_ms=3.0, saturate=1.1, rate_note=24, volume=42, noise_seed=202,
    ),
    "ブラシで叩く柔らかいバックビート・スネア。LPノイズ単層、3msの緩いアタック。swing-jazz の brush 由来。",
)

SWING_WALK_BASS = register(
    "swing_walk_bass",
    Patch(
        "SwingWalkBass",
        (WeightedLayer(ToneLayer(((1.0, 0.8, 7.0), (2.0, 0.2, 10.0)))),),
        OneShot(0.32),
        pitched=True, attack_ms=6.0, saturate=1.15, rate_note=24, shift=-12, volume=58,
    ),
    "撥弦の温かみを持つウォーキングベース（アップライト風）。基音+2倍音、6msアタックで撥弦の頭を作る。"
    "swing-jazz の walk_bass 由来。",
)

SWING_PIANO_COMP = register(
    "swing_piano_comp",
    Patch(
        "SwingPianoComp",
        (WeightedLayer(ToneLayer((
            (1.0, 1.0, 9.0), (1.006, 0.9, 9.0), (2.0, 0.5, 13.0), (2.012, 0.45, 13.0),
            (3.0, 0.25, 18.0), (3.02, 0.22, 18.0), (4.0, 0.12, 24.0),
        ), filter=FilterSpec("lp", a=0.45))),),
        OneShot(0.45),
        pitched=True, rate_note=24, shift=0, volume=42, peak=0.9,
    ),
    "刺すようなピアノ・コンピング和音。近接デチューン対(約10セント)による軽いうなり、LPで丸め、"
    "各倍音が異なる速さで減衰。swing-jazz の piano_comp 由来。",
)

SWING_SAX_LEAD = register(
    "swing_sax_lead",
    Patch(
        "SwingSaxLead",
        (WeightedLayer(ToneLayer(tuple((12.0 * h, 1.0 / h, None) for h in (1, 3, 5, 7)))),),
        Loop(190, 70),
        pitched=True, rate_note=24, shift=0, volume=48,
    ),
    "リード管楽器らしいサックス/トランペット系リード。奇数次倍音(1,3,5,7次)のみ、重み1/h。"
    "K=12*h, L=190、アタック窓70サンプル。swing-jazz の sax_lead 由来。",
)

# ------------------------------------------------------------
# prog-rock（GENRE_DESIGN_V2.md §2。EXT-2 可変小節の実証ジャンル）
# ------------------------------------------------------------

PROG_KICK = register(
    "prog_kick",
    Patch(
        "ProgKick",
        (
            WeightedLayer(PitchSweepLayer(freq_start=140.0, freq_end=48.0, pitch_decay=28.0, decay_alpha=13.0)),
            WeightedLayer(NoiseLayer(decay_alpha=2600.0), weight=0.15),
        ),
        OneShot(0.22),
        pitched=False, saturate=1.5, rate_note=24, volume=60, noise_seed=301,
    ),
    "締まった現代ロックキック。140Hzから48Hzへ収束するピッチドロップ、軽いクリック。"
    "prog-rock の kick 由来。",
)

PROG_SNARE = register(
    "prog_snare",
    Patch(
        "ProgSnare",
        (
            WeightedLayer(ToneLayer(((190.0, 1.0, 25.0),)), weight=0.5),
            WeightedLayer(NoiseLayer(decay_alpha=16.0, filter=FilterSpec("hp")), weight=0.7),
        ),
        OneShot(0.20),
        pitched=False, saturate=1.6, rate_note=24, volume=54, noise_seed=302,
    ),
    "パンチのあるスネア。190Hzのヘッドトーン + HPノイズ、march の snare よりさらに歪ませる。"
    "prog-rock の snare 由来。",
)

PROG_BASS_DIST = register(
    "prog_bass_dist",
    Patch(
        "ProgBassDist",
        (WeightedLayer(ToneLayer(
            tuple((m, w, None) for m, w in dsp.partials_square(5)), filter=FilterSpec("lp", a=0.3),
        )),),
        OneShot(0.5),
        pitched=True, decay_alpha=5.0, saturate=2.2, rate_note=24, shift=-12, volume=58,
    ),
    "矩形波近似(5項)+LP のディストーションベース。フィルタ後に一律減衰、強めのサチュレーション。"
    "prog-rock の bass_dist 由来。",
)

PROG_GTR_POWER = register(
    "prog_gtr_power",
    Patch(
        "ProgGtrPower",
        (WeightedLayer(ToneLayer((
            (1.0, 1.0, 7.0), (1.5, 0.7, 9.0), (2.0, 0.5, 9.0), (3.0, 0.3, 12.0),
        ))),),
        OneShot(0.4),
        pitched=True, saturate=2.6, rate_note=24, shift=0, volume=56,
    ),
    "パワーコード（root+5th+oct+複合5th）を1サンプルに焼き込んだリフ用ギター。強いサチュレーション、"
    "各倍音が異なる速さで減衰（パームミュート風の締まり）。prog-rock の gtr_power 由来。",
)

PROG_LEAD_GTR = register(
    "prog_lead_gtr",
    Patch(
        "ProgLeadGtr",
        (WeightedLayer(ToneLayer(tuple((6.0 * h, w, None) for h, w in
            enumerate((1.0, 0.55, 0.7, 0.3, 0.4, 0.18), start=1)))),),
        Loop(190, 50),
        pitched=True, saturate=1.8, rate_note=24, shift=0, volume=50,
    ),
    "歪ませたリードギター。奇数次を強調した6倍音構成（K=6*h, L=190）、アタック窓50サンプル。"
    "prog-rock の lead_gtr 由来（chorus セクション専用）。",
)

# ------------------------------------------------------------
# future-bass（GENRE_DESIGN_V2.md §7。EXT-4 サイドチェインの実証ジャンル）
# ------------------------------------------------------------

FB_KICK = register(
    "fb_kick",
    Patch(
        "FbKick",
        (
            WeightedLayer(PitchSweepLayer(freq_start=150.0, freq_end=45.0, pitch_decay=28.0, decay_alpha=12.0)),
            WeightedLayer(NoiseLayer(decay_alpha=2800.0), weight=0.1),
        ),
        OneShot(0.25),
        pitched=False, saturate=1.5, rate_note=24, volume=60, noise_seed=401,
    ),
    "サイドチェインのトリガ音源になるキック。150Hzから45Hzへ収束するピッチドロップ、軽いクリック。"
    "future-bass の kick 由来。",
)

FB_SUB = register(
    "fb_sub",
    Patch(
        "FbSub",
        (WeightedLayer(ToneLayer(((3.0, 1.0, None),))),),
        Loop(190, 0),
        pitched=True, rate_note=24, shift=-12, volume=58,
    ),
    "正弦単層のサブベース。K=3, L=190（130.8Hz基準、shift=-12）。アタック窓なし、ダッキング対象。"
    "future-bass の sub 由来。",
)

FB_SUPERSAW = register(
    "fb_supersaw",
    Patch(
        "FbSupersaw",
        (
            WeightedLayer(ToneLayer(
                tuple((120.0 * h, 1.0 / h, None) for h in range(1, 9)), filter=FilterSpec("lp", a=0.3),
            )),
            WeightedLayer(ToneLayer(
                tuple((120.0 * h + 1, 0.8 / h, None) for h in range(1, 9)), filter=FilterSpec("lp", a=0.3),
            ), weight=0.8),
            WeightedLayer(ToneLayer(
                tuple((120.0 * h - 1, 0.8 / h, None) for h in range(1, 9)), filter=FilterSpec("lp", a=0.3),
            ), weight=0.8),
        ),
        Loop(3800, 0),
        pitched=True, rate_note=24, shift=0, volume=44,
    ),
    "3層デチューン（中央 K=120*h／隣接整数 K±1）ののこぎり波近似スーパーソウ。``Finish=Loop`` は"
    "``mult`` が整数サイクル数でなければならない制約のため、隣接整数（``TENSION_STRINGS`` と同じ技法）で"
    "デチューンを表現する（比率での±0.4%指定は非整数 K になり構築時エラーになるため不可。K が大きい"
    "L=3800 を使うことで、隣接整数差＝約0.8%(h=1)〜0.1%(h=8)の実用的なうなり幅になる）。各層に個別の"
    "LP フィルタ（``Patch.post_filter`` は ``OneShot`` 専用のため ``Loop`` では使えない）。ダッキング対象。"
    "future-bass の supersaw 由来。",
)

FB_VOCAL_CHOP = register(
    "fb_vocal_chop",
    Patch(
        "FbVocalChop",
        (
            WeightedLayer(ToneLayer(tuple((h, w, None) for h, w in
                enumerate((1.0, 0.7, 0.5, 0.6, 0.3, 0.4, 0.2, 0.25, 0.12, 0.15), start=1)))),
            WeightedLayer(NoiseLayer(decay_alpha=None), weight=0.08),
        ),
        OneShot(1.6),
        pitched=False, saturate=1.1, rate_note=24, volume=52, noise_seed=402,
    ),
    "フォルマント風の不均一倍音（h=1..10）+ 微小ノイズの長尺ヴォーカルチョップ素材。"
    "pitched=False（9xx オフセットのみでシラブルを切り替え、音高は rate_note 固定）。"
    "future-bass の vocal_chop 由来。",
)

FB_CLAP = register(
    "fb_clap",
    Patch(
        "FbClap",
        (
            WeightedLayer(NoiseLayer(decay_alpha=35.0, filter=FilterSpec("hp"))),
            WeightedLayer(NoiseLayer(decay_alpha=14.0, filter=FilterSpec("hp")), weight=0.6),
        ),
        OneShot(0.18),
        pitched=False, saturate=1.3, rate_note=24, volume=50, noise_seed=403,
    ),
    "2層の HP ノイズ（速い/遅い減衰）を重ねて多重発音のクラップ感を近似。"
    "（Patch.noise_seed は1つの乱数列を全レイヤーが順番に消費するため、層ごとに別 seed を持つ"
    "フィールドは無いが、順次消費により各層は自動的に独立したノイズ列になる）。future-bass の clap 由来。",
)

# ------------------------------------------------------------
# trap（GENRE_DESIGN_V2.md §4。EXT-1 サブステップ／EXT-5 808グライドの実証ジャンル）
# ------------------------------------------------------------

TRAP_808 = register(
    "trap_808",
    Patch(
        "Trap808",
        (WeightedLayer(ToneLayer(((1.0, 1.0, 1.2),))),),
        OneShot(0.9),
        pitched=True, saturate=1.3, rate_note=24, shift=-12, volume=62,
    ),
    "ロングテールのサブ808。正弦単層、ゆるやかな減衰（e^(-1.2t)）。3xx グライドで滑らせる前提のため"
    "倍音は持たせない。trap の 808 由来。",
)

TRAP_SNARE_CLAP = register(
    "trap_snare_clap",
    Patch(
        "TrapSnareClap",
        (
            WeightedLayer(NoiseLayer(decay_alpha=30.0, filter=FilterSpec("hp"))),
            WeightedLayer(NoiseLayer(decay_alpha=45.0, filter=FilterSpec("hp")), weight=0.7),
        ),
        OneShot(0.15),
        pitched=False, saturate=1.4, rate_note=24, volume=54, noise_seed=501,
    ),
    "2層の HP ノイズ（減衰速度違い）で多重発音のクラップ的スネアを近似。trap の snare_clap 由来。",
)

TRAP_HAT_CLOSED = register(
    "trap_hat_closed",
    Patch(
        "TrapHatClosed",
        (WeightedLayer(NoiseLayer(decay_alpha=90.0, filter=FilterSpec("hp"))),),
        OneShot(0.05),
        pitched=False, saturate=1.2, rate_note=24, volume=40, noise_seed=502,
    ),
    "短いクローズドハイハット。HPノイズ単層、急減衰。E9x リトリガでロールを作る前提。trap の hat_closed 由来。",
)

TRAP_HAT_OPEN = register(
    "trap_hat_open",
    Patch(
        "TrapHatOpen",
        (WeightedLayer(NoiseLayer(decay_alpha=18.0, filter=FilterSpec("hp"))),),
        OneShot(0.16),
        pitched=False, saturate=1.2, rate_note=24, volume=42, noise_seed=502,
    ),
    "trap_hat_closed の decay_alpha を緩め・尺を伸ばした派生（フレーズ末のオープンハイハット）。"
    "trap の hat_open 由来。",
)

TRAP_LEAD_PLUCK = register(
    "trap_lead_pluck",
    Patch(
        "TrapLeadPluck",
        (WeightedLayer(ToneLayer(((1.0, 1.0, 10.0), (2.0, 0.6, 14.0), (4.0, 0.3, 20.0)),
                                  filter=FilterSpec("lp", a=0.3))),),
        OneShot(0.5),
        pitched=True, rate_note=24, shift=0, volume=48,
    ),
    "ダークなメロディック・パーカッシブ・リード。基音+2/4倍音、LPで丸め、各倍音が異なる速さで減衰。"
    "trap の lead_pluck 由来。",
)

# ------------------------------------------------------------
# maqam（GENRE_DESIGN_V2.md §5。EXT-3 マイクロチューニングの実証ジャンル）
# ------------------------------------------------------------

MAQAM_OUD = register(
    "maqam_oud",
    Patch(
        "MaqamOud",
        (
            WeightedLayer(ToneLayer(tuple((float(h), 1.0 / h, 8.0 + h) for h in range(1, 7)))),
            WeightedLayer(PitchSweepLayer(freq_start=340.0, freq_end=270.0, pitch_decay=60.0, decay_alpha=30.0),
                          weight=0.15),
        ),
        OneShot(0.6),
        pitched=True, saturate=1.15, rate_note=24, shift=0, volume=50, noise_seed=601,
    ),
    "撥弦のウード。基音+5倍音（各異なる速さで減衰）+ 微小なピッチドロップ（撥弦アタック）。shift=0 のため"
    "resolve_micronote() の tracker note をそのまま logical note として使える。maqam の oud 由来。"
    "中立音程は finetune 分散スロット（maqam_oud_n3／maqam_oud_n7。build_samples() で dataclasses.replace"
    "して追加登録する）。",
)

MAQAM_NAY = register(
    "maqam_nay",
    Patch(
        "MaqamNay",
        (
            WeightedLayer(ToneLayer(tuple((120.0 * h, 1.0 / h, None) for h in (1, 3, 5)))),
            WeightedLayer(ToneLayer(tuple((120.0 * h + 1, 0.8 / h, None) for h in (1, 3, 5))), weight=0.8),
        ),
        Loop(3800, 0),
        pitched=True, rate_note=24, shift=0, volume=46,
    ),
    "通奏低音ドローンの葦笛。奇数次倍音（h=1,3,5）を中心・隣接整数(K,K+1)デチューンした2層で息の"
    "揺らぎを近似（fb_supersaw と同じ技法。Finish=Loop は NoiseLayer 不可・整数サイクル数のみのため）。"
    "K=120*h, L=3800。maqam の nay 由来。",
)

MAQAM_QANUN = register(
    "maqam_qanun",
    Patch(
        "MaqamQanun",
        (WeightedLayer(ToneLayer(tuple((float(h), 1.0 / h, 14.0 + 3.0 * h) for h in range(1, 5)))),),
        OneShot(0.35),
        pitched=True, saturate=1.1, rate_note=24, shift=0, volume=48, noise_seed=602,
    ),
    "分散和音的伴奏のカーヌーン。基音+3倍音、速めの減衰（各倍音で速さを変える）。maqam の qanun 由来。",
)

MAQAM_DAF_DUM = register(
    "maqam_daf_dum",
    Patch(
        "MaqamDafDum",
        (WeightedLayer(ToneLayer(((1.0, 1.0, 16.0), (2.0, 0.3, 22.0)))),),
        OneShot(0.32),
        pitched=False, saturate=1.2, rate_note=24, volume=56, noise_seed=603,
    ),
    "フレームドラム（ダフ）の低音打 DUM。基音+2倍音の低い減衰音。maqam の daf_dum 由来。",
)

MAQAM_DAF_TEK = register(
    "maqam_daf_tek",
    Patch(
        "MaqamDafTek",
        (WeightedLayer(NoiseLayer(decay_alpha=55.0, filter=FilterSpec("hp"))),),
        OneShot(0.12),
        pitched=False, saturate=1.2, rate_note=24, volume=46, noise_seed=604,
    ),
    "フレームドラム（ダフ）の高音打 TEK。HPノイズの短い減衰。maqam の daf_tek 由来。",
)

# ------------------------------------------------------------
# free-jazz（GENRE_DESIGN_V2.md §8。EXT-5① テンポカーブの実証ジャンル）
# ------------------------------------------------------------

FREE_PIANO_CLUSTER = register(
    "free_piano_cluster",
    Patch(
        "FreePianoCluster",
        (WeightedLayer(ToneLayer((
            (1.0, 0.8, 10.0), (1.06, 0.7, 12.0), (1.13, 0.65, 14.0), (1.19, 0.6, 16.0), (1.26, 0.55, 20.0),
        ))),),
        OneShot(0.6),
        pitched=True, saturate=1.1, rate_note=24, shift=0, volume=48, noise_seed=701,
    ),
    "隣接半音を密集させたトーンクラスター（通常の3度堆積和音ではない）。5層、比率デチューン"
    "（OneShot のため mult は整数サイクル数制約を受けない）、各層が異なる速さで減衰。"
    "free-jazz の piano_cluster 由来。",
)

FREE_ARCO_BASS = register(
    "free_arco_bass",
    Patch(
        "FreeArcoBass",
        (
            WeightedLayer(ToneLayer(((60.0, 1.0, None),))),
            WeightedLayer(ToneLayer(((61.0, 0.8, None),)), weight=0.8),
        ),
        Loop(3800, 0),
        pitched=True, rate_note=24, shift=-12, volume=44,
    ),
    "持続的なアルコ（弓弾き）ベース。K=60/61（隣接整数デチューン。fb_supersaw と同じ技法）、"
    "L=3800（130.8Hz基準、shift=-12）。擦弦ノイズは NoiseLayer ではなくデチューンのうなりで近似"
    "（Finish=Loop は ToneLayer のみ許可という core/synth.py 制約のため）。free-jazz の arco_bass 由来。",
)

FREE_SAX_SCREECH = register(
    "free_sax_screech",
    Patch(
        "FreeSaxScreech",
        (
            WeightedLayer(ToneLayer(tuple((float(h), 1.0 / h, 6.0 + h) for h in range(3, 13)))),
            WeightedLayer(NoiseLayer(decay_alpha=10.0, filter=FilterSpec("hp")), weight=0.5),
        ),
        OneShot(0.5),
        pitched=True, saturate=1.6, rate_note=24, shift=0, volume=50, noise_seed=702,
    ),
    "アルティッシモの絶叫的サックス。高次倍音優勢（h=3..12、不均一な減衰）+ HPノイズ。"
    "free-jazz の sax_screech 由来。",
)

FREE_CYMBAL_SWELL = register(
    "free_cymbal_swell",
    Patch(
        "FreeCymbalSwell",
        (WeightedLayer(NoiseLayer(rise_power=1.5, filter=FilterSpec("hp"))),),
        OneShot(2.0),
        pitched=False, saturate=1.1, rate_note=24, volume=46, noise_seed=703,
    ),
    "立ち上がりクレッシェンドのシンバル・スウェル。個々の打点ではなく持続的な高揚に使う。"
    "free-jazz の cymbal_swell 由来。",
)

# ------------------------------------------------------------
# minimalism（GENRE_DESIGN_V2.md §6。EXT-2② ポリメトリックの実証ジャンル）
# ------------------------------------------------------------

MIN_PIANO_PULSE = register(
    "min_piano_pulse",
    Patch(
        "MinPianoPulse",
        (WeightedLayer(ToneLayer(tuple((float(h), 1.0 / h, 16.0 + 4.0 * h) for h in range(1, 6)))),),
        OneShot(0.25),
        pitched=True, saturate=1.05, rate_note=24, shift=0, volume=48, noise_seed=801,
    ),
    "16row周期（最速）を担当するピアノ・パルス。基音+4倍音、速めの減衰。minimalism の piano_pulse 由来。",
)

MIN_MARIMBA = register(
    "min_marimba",
    Patch(
        "MinMarimba",
        (
            WeightedLayer(ToneLayer(((1.0, 1.0, 12.0), (2.0, 0.3, 18.0)))),
            WeightedLayer(PitchSweepLayer(freq_start=520.0, freq_end=440.0, pitch_decay=90.0, decay_alpha=40.0),
                          weight=0.1),
        ),
        OneShot(0.35),
        pitched=True, saturate=1.1, rate_note=24, shift=0, volume=50, noise_seed=802,
    ),
    "12row周期のマリンバ。基音+2倍音＋マレットアタックの微小ピッチドロップ。minimalism の marimba 由来。",
)

MIN_VIBRAPHONE = register(
    "min_vibraphone",
    Patch(
        "MinVibraphone",
        (WeightedLayer(ToneLayer(tuple((float(h), 1.0 / h, 3.0 + h) for h in range(1, 5)))),),
        OneShot(1.2),
        pitched=True, saturate=1.0, rate_note=24, shift=0, volume=44,
    ),
    "8row周期のヴィブラフォン。基音+3倍音、長い余韻（decay_alpha が小さい）。minimalism の vibraphone 由来。",
)

MIN_WOODBLOCK = register(
    "min_woodblock",
    Patch(
        "MinWoodblock",
        (WeightedLayer(ToneLayer(((1.0, 1.0, 70.0),))),),
        OneShot(0.08),
        pitched=False, saturate=1.2, rate_note=24, volume=42,
    ),
    "6row周期（最長周期）のウッドブロック・アクセント。単一倍音、非常に速い減衰。"
    "minimalism の woodblock 由来。",
)

# ------------------------------------------------------------
# orchestral（GENRE_DESIGN_V2.md §3。EXT-6 マルチチャンネル/XM の実証ジャンル）
# ------------------------------------------------------------

ORCH_VIOLIN = register(
    "orch_violin",
    Patch(
        "OrchViolin",
        (WeightedLayer(ToneLayer(tuple((120.0 * h, 1.0 / h ** 0.8, None) for h in range(1, 9)))),),
        Loop(3800, 300),
        pitched=True, rate_note=24, shift=0, volume=46,
    ),
    "第1ヴァイオリン。K=120*h(h=1..8), L=3800（261.6Hz基準、0.49%偏差）、弓の起動をアタック窓300"
    "サンプルで表現。orchestral の violin 由来。ヴィオラ/チェロ/コントラバスはこの Patch を"
    "``shift`` のみ変えて `dataclasses.replace()` で派生させる（弦楽器族の音色が近いため）。",
)

ORCH_VIOLA = register(
    "orch_viola",
    dataclasses.replace(ORCH_VIOLIN, name="OrchViola", shift=-7, volume=44),
    "ヴィオラ。orch_violin を shift=-7 で派生。orchestral の viola 由来。",
)

ORCH_CELLO = register(
    "orch_cello",
    dataclasses.replace(ORCH_VIOLIN, name="OrchCello", shift=-12, volume=48),
    "チェロ。orch_violin を shift=-12 で派生。orchestral の cello 由来。",
)

ORCH_BASS_STR = register(
    "orch_bass_str",
    dataclasses.replace(ORCH_VIOLIN, name="OrchBassStr", shift=-24, volume=52),
    "コントラバス。orch_violin を shift=-24 で派生。orchestral の bass_str 由来。",
)

ORCH_TRUMPET = register(
    "orch_trumpet",
    dataclasses.replace(MARCH_BRASS_SECTION, name="OrchTrumpet", finish=Loop(190, 20)),
    "トランペット。march の brass_section を `Loop.attack_samples` を短縮（100→20）して鋭いアタックに"
    "した派生（``Patch.attack_ms`` は Loop では使えないため `Loop.attack_samples` で表現する）。"
    "orchestral の trumpet 由来。金管は march の horn/section 資産を流用・拡張する設計方針どおり。",
)

ORCH_TIMPANI = register(
    "orch_timpani",
    Patch(
        "OrchTimpani",
        (
            WeightedLayer(ToneLayer(((1.0, 1.0, 8.0), (2.0, 0.4, 12.0), (3.0, 0.2, 16.0)))),
            WeightedLayer(PitchSweepLayer(freq_start=90.0, freq_end=65.0, pitch_decay=35.0, decay_alpha=10.0),
                          weight=0.2),
        ),
        OneShot(1.1),
        pitched=True, saturate=1.15, rate_note=24, shift=-24, volume=54, noise_seed=901,
    ),
    "音程を持つティンパニ。基音+2倍音（各異なる速さで減衰）+ 打面の微小ピッチドロップ。"
    "march の bd と違い明確な音程を持つ点が核心の差。orchestral の timpani 由来。",
)
