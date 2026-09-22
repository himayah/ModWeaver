"""動作・音質を確認済みの ``synth.Patch`` 値を集めた参照ライブラリ。

ここに集めるのは「型としての分類」ではなく「検索・流用のための参照データ」であり、
``core/synth.py`` の型システムには一切影響しない。新しい音色が欲しいときは、
``find()`` で近い説明のプリセットを探し ``dataclasses.replace(既存Patch, ...)`` で
差分だけ変えて ``synth.render()`` → 試聴し、良ければ ``register()`` で本モジュールへ
追加する（ゼロから ``Patch`` を組み立てない）。

nostalgic / suspense / march を ``Patch`` 方式へ1ジャンルずつ移行する作業の中で、
動作確認が取れたものから順に追加していく（現時点では空の骨組み）。
"""
from __future__ import annotations

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
