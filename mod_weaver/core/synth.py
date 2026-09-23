"""音源合成: 直交レイヤー方式（``Patch`` → ``SampleSpec``）。

楽器ファミリー（打楽器/金属/持続音/撥弦 等）で分類せず、信号源（``Layer``）・仕上げ方
（``Finish``）・飽和・アタック窓という直交する要素の組み合わせとして音色を記述する。
core が公開するのは ``Patch`` と ``render()`` のみで、「楽器の種類ごとに専用関数を増やす」
設計は取らない（固定カテゴリだとティンパニ/808 のような「音程を持つ打楽器」やスネアのような
「トーン層＋ノイズ層を別々の減衰率で混ぜる」音色を無理に押し込むことになるため）。

Layer は3種類:

- ``ToneLayer``: 加算合成（倍音の重み付き和）。倍音ごとに減衰率を持てる。
- ``PitchSweepLayer``: 瞬時周波数が時間変化するサイン（打撃音のピッチドロップ）。絶対 Hz 指定。
- ``NoiseLayer``: フィルタ付きノイズ（``decay_alpha`` で減衰、``rise_power`` で上昇の包絡）。

減衰・上昇を表すフィールドは全レイヤーで ``Optional[float]``、``None`` が「無効」を表す規約に統一する
（``ToneLayer.partials`` の decay_alpha、``PitchSweepLayer.decay_alpha``、``NoiseLayer.decay_alpha``/
``rise_power``、``Patch.decay_alpha`` すべて共通）。判別用の文字列フィールド（``shape`` 等）は持たない。

Finish は2種類:

- ``OneShot``: 指定秒数で鳴り切る一発音。
- ``Loop``: 完全ループ（``ToneLayer`` のみ、減衰なし）。``attack_samples>0`` なら ``dsp.with_attack``
  でアタック窓を頭に足す。``attack_samples=0``（既定）なら窓なしで sample 0 から直接ループする
  （nostalgic の pad/flute のような、アタックを持たない純粋な周期波形向け）。

「クリック」のような短い過渡音は専用フィールドを持たず、``NoiseLayer(decay_alpha=大)`` を
小さい重みで ``layers`` に加えるだけで表現する（概念を増やさない）。

減衰には2段階ある。レイヤー内（``ToneLayer.partials`` の ``decay_alpha`` 等）はフィルタより前・
声部ごとに独立の速さで減衰させる場合に使う（anvil の5倍音がそれぞれ違う速さで減衰する等）。
``Patch.decay_alpha`` は全レイヤーを混合・（``post_filter`` があればそれも掛けた）後に一律で掛ける
減衰で、フィルタ済み信号全体が滑らかに減衰する音色（tuba/horn の「フィルタ→減衰」の順）に使う。
両者は独立で併用できる。

フィルタにも2段階ある。レイヤー内（``ToneLayer``/``PitchSweepLayer`` の ``filter``）はそのレイヤー
単体（＝1つの信号源）にだけ掛かる。``Patch.post_filter`` は全レイヤーを混合した**後**に掛かるので、
型の異なるレイヤーの合算（例: ノイズ＋決定的なトーンの和を一括で HP に通す。hihat の例）に使う。

``peak`` はピーク正規化の目標値（既定 0.95）。``None`` にすると正規化をせず生の混合信号をそのまま
使う（合成時の重み自体で音量バランスを作り込み、``tanh`` の効き具合を直接コントロールしたい音色向け。
nostalgic の大半の音色がこの流儀）。

``pitched`` は自動導出しない（ToneLayer＋NoiseLayer 混合の打楽器等で判定が破綻するため）。
``Patch.pitched=False`` のとき ``ToneLayer.partials`` の ``mult`` は絶対 Hz、``True`` のとき
``f0 = hz(rate_note + shift)`` に対する比率として解釈される（``OneShot`` のみ。``Loop`` は常に
整数サイクル数）。

プリセット（動作・音質を確認済みの ``Patch`` 値）は ``core/synth_presets.py`` に集約する。
新しい音色が欲しいときは、まず近いプリセットを探し ``dataclasses.replace()`` で差分だけ調整して
``render()`` → 試聴し、良ければプリセットへ追加する運用とする（ゼロから Patch を組み立てない）。

**知覚寄りファクトリは core に置かない**（一度試して撤回。§下記）。複数の技術パラメータを1つの
ノブに連動させる（例: 「締まり」1つで pitch_decay と decay_alpha を同時に動かす）のはコントローラ数を
減らす一方でサンプル音源の設計自由度を犠牲にする。しかも連動のさせ方自体が美的判断（どのジャンルの
どんな音か）であり、ジャンルをまたいで正しい連動の仕方は1つに決まらない。そのため：

- core が公開するのは全パラメータが独立に操作できる ``Patch``/``Layer`` のみ（本モジュール）。
- 連動ノブが欲しいジャンルモジュールは、そのジャンルの profiles/*.py 内に**ローカルな**ヘルパー
  関数を自分で定義し、そこで初めて「このジャンルではこう連動させる」という判断をする。
- 機械的（美的判断を含まない）単位変換だけは core に置いてよい。例: ``pitch.note_for_hz()``
  （目標 Hz に最も近い logical note）。ある音色を「概ね target_hz で鳴らしたい」ときの
  ``shift = pitch.note_for_hz(target_hz) - rate_note`` の計算に使う。

将来の参考設計（未実装）: ``Patch`` の1フィールドだけを範囲内で振って複数バリエーションを
一括生成し聴き比べる「オーディション・ツール」。目的が音色探索の効率化であり本モジュールの
責務（Patch → SampleSpec の変換）から外れるため、別ツールとして切り出す想定で今は実装しない。
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Callable, Optional, Sequence, Union

from ..errors import SampleConstraintError
from . import dsp
from .model import SampleSpec
from .pitch import PERIODS, hz

TWO_PI = dsp.TWO_PI


# ============================================================
# Layer（信号源）
# ============================================================

@dataclass(frozen=True)
class FilterSpec:
    """layer の後処理／ノイズ生成方式。

    ``kind``: ``"none"`` | ``"lp"``（静的 ``one_pole_lp``。``a`` を使う）|
    ``"hp"``（``diff_hp``）| ``"lp_sweep"``（``noise_lp``。``NoiseLayer`` 専用、``a_start``/``a_end``
    を使う。``ToneLayer``/``PitchSweepLayer`` に指定すると SampleConstraintError）。
    """

    kind: str = "none"
    a: float = 0.0
    a_start: float = 0.0
    a_end: float = 0.0

    def __post_init__(self) -> None:
        if self.kind not in ("none", "lp", "hp", "lp_sweep"):
            raise SampleConstraintError(f"unknown filter kind: {self.kind!r}")


NO_FILTER = FilterSpec()


@dataclass(frozen=True)
class ToneLayer:
    """加算合成の1声部。

    ``partials``: ``(倍率 mult, weight, decay_alpha)`` の列。``decay_alpha=None`` は減衰なし
    （``Finish=Loop`` でのみ許可。``OneShot`` で None を混ぜると ``Patch`` 構築時に
    SampleConstraintError）。``mult`` は ``Finish=OneShot`` かつ ``Patch.pitched=True`` のとき
    f0（``hz(rate_note+shift)``）に対する比率、``pitched=False`` のとき絶対 Hz、``Finish=Loop``
    のとき整数サイクル数として解釈される。
    """

    partials: tuple[tuple[float, float, Optional[float]], ...]
    filter: FilterSpec = NO_FILTER


@dataclass(frozen=True)
class PitchSweepLayer:
    """打撃音の位相積分サイン。瞬時周波数 ``f(t) = freq_end + (freq_start-freq_end)*e^(-pitch_decay*t)``。

    ``OneShot`` 専用。周波数は常に絶対 Hz（打撃音は音程を持たない一発音の想定）。``decay_alpha=None``
    は減衰なし（``ToneLayer.partials`` の decay_alpha と同じ規約）。
    """

    freq_start: float
    freq_end: float
    pitch_decay: float
    decay_alpha: Optional[float] = None
    filter: FilterSpec = NO_FILTER


@dataclass(frozen=True)
class NoiseLayer:
    """フィルタ付きノイズ。既定（``decay_alpha``/``rise_power`` ともに None）は無包絡（一定振幅）。

    ``decay_alpha``: 減衰の速さ（``e^(-alpha*t)``）。``rise_power``: 立ち上がりの速さ
    （``(i/n)^power``。swoosh 等の上昇包絡用）。両方を同時に指定すると SampleConstraintError
    （他の decay_alpha と同じく「None＝無効」の規約に統一するため、``shape`` のような判別フィールドは持たない）。
    """

    decay_alpha: Optional[float] = None
    rise_power: Optional[float] = None
    filter: FilterSpec = NO_FILTER

    def __post_init__(self) -> None:
        if self.decay_alpha is not None and self.rise_power is not None:
            raise SampleConstraintError("NoiseLayer: decay_alpha and rise_power are mutually exclusive")


Layer = Union[ToneLayer, PitchSweepLayer, NoiseLayer]


@dataclass(frozen=True)
class WeightedLayer:
    layer: Layer
    weight: float = 1.0


# ============================================================
# Finish（仕上げ）
# ============================================================

@dataclass(frozen=True)
class OneShot:
    duration: float             # 秒


@dataclass(frozen=True)
class Loop:
    length: int                     # L（サンプル数、偶数）
    attack_samples: int = 0          # dsp.with_attack のアタック長（偶数、≤ length）。0 ならアタック窓なし
    # （loop=(0, length//2) で sample 0 から直接ループする。pad/flute のような純粋な周期波形向け。
    #  ループ本体の末尾から窓がけして借用する処理のため、Patch.attack_ms とは異なりサンプル数で指定する）


Finish = Union[OneShot, Loop]


# ============================================================
# Patch
# ============================================================

@dataclass(frozen=True)
class Patch:
    name: str
    layers: tuple[WeightedLayer, ...]
    finish: Finish
    pitched: bool

    # --- 後処理パイプライン（render() が適用する順。OneShot 専用の4つは post_filter→decay_alpha→
    #     attack_ms→tail_fade_ms、peak/saturate は OneShot・Loop 共通で末尾に適用） ---
    post_filter: Optional[FilterSpec] = None  # 全レイヤーを混合した後に掛けるフィルタ（"lp"/"hp" のみ）。
    # 異なる型のレイヤー（例: ノイズ＋決定的なトーン）をまとめて濾したいとき用。単一レイヤーで足りるなら
    # layer 側の filter で十分（hihat の例を参照）
    decay_alpha: Optional[float] = None  # 全レイヤーを混合・（post_filter があればそれも掛けた）後に
    # 一律で掛ける減衰 e^(-alpha*t)。レイヤー個別の decay_alpha はフィルタより前・声部ごとに独立の速さで
    # 減衰させる場合に使う（anvil の5倍音等）。こちらはフィルタ後・全体に一律（tuba/horn の「フィルタ→減衰」）。
    # 両者は独立で併用できる
    attack_ms: float = 0.0               # 頭の直線窓（ミリ秒。0 なら即座に立ち上がる）
    tail_fade_ms: float = 0.0            # 末尾をこのミリ秒だけ線形に 0 へ落とす（swoosh 等。0 なら無効）
    peak: Optional[float] = 0.95         # ピーク正規化の目標値。None なら正規化せず生の混合信号を使う
    saturate: Optional[float] = None     # tanh(drive * x) の drive。None なら飽和なし

    # --- サンプルの素性 ---
    rate_note: int = 24
    shift: int = 0
    finetune: int = 0                    # EXT-3 マイクロチューニングの差込口（SampleSpec へそのまま）
    volume: int = 50
    noise_seed: int = 0

    def __post_init__(self) -> None:
        if not self.layers:
            raise SampleConstraintError(f"{self.name}: patch must have at least one layer")
        if self.post_filter is not None and self.post_filter.kind not in ("none", "lp", "hp"):
            raise SampleConstraintError(f"{self.name}: post_filter kind {self.post_filter.kind!r} is not valid")
        if isinstance(self.finish, Loop):
            if self.post_filter is not None or self.decay_alpha is not None \
                    or self.attack_ms > 0 or self.tail_fade_ms > 0:
                raise SampleConstraintError(
                    f"{self.name}: post_filter/decay_alpha/attack_ms/tail_fade_ms are OneShot-only"
                )
            for wl in self.layers:
                if not isinstance(wl.layer, ToneLayer):
                    raise SampleConstraintError(
                        f"{self.name}: Loop finish only supports ToneLayer (got {type(wl.layer).__name__})"
                    )
                if any(alpha is not None for _, _, alpha in wl.layer.partials):
                    raise SampleConstraintError(f"{self.name}: Loop finish cannot decay (partial alpha must be None)")


# ============================================================
# render
# ============================================================

def _filter_fn(f: FilterSpec) -> Callable[[list[float]], list[float]]:
    """``FilterSpec`` に対応する信号列 → 信号列の関数。"lp_sweep" はノイズ生成に内蔵の時変フィルタ
    （``dsp.noise_lp``）であり、既存信号への後処理としては無効。

    ``_apply_post_filter``（そのまま適用）と ``_render_loop_body``（``dsp.circular`` で包んで適用）が共用する。
    """
    if f.kind == "none":
        return lambda xs: xs
    if f.kind == "lp":
        return lambda xs: dsp.one_pole_lp(xs, f.a)
    if f.kind == "hp":
        return dsp.diff_hp
    raise SampleConstraintError(f"filter kind {f.kind!r} is only valid as noise generation (lp_sweep)")


def _apply_post_filter(xs: list[float], f: FilterSpec) -> list[float]:
    """既存の信号列へのフィルタ。ToneLayer/PitchSweepLayer の filter と Patch.post_filter が共用する。"""
    return _filter_fn(f)(xs)


def _render_tone_oneshot(layer: ToneLayer, f0: float, rate: float, n: int) -> list[float]:
    out = [0.0] * n
    for mult, weight, alpha in layer.partials:
        f = f0 * mult
        for i in range(n):
            t = i / rate
            env = 1.0 if alpha is None else math.exp(-alpha * t)
            out[i] += weight * math.sin(TWO_PI * f * t) * env
    return _apply_post_filter(out, layer.filter)


def _render_pitch_sweep(layer: PitchSweepLayer, rate: float, n: int) -> list[float]:
    fs, fe, k = layer.freq_start, layer.freq_end, layer.pitch_decay
    out = []
    for i in range(n):
        t = i / rate
        phase = TWO_PI * (fe * t + (fs - fe) / k * (1.0 - math.exp(-k * t)))
        env = 1.0 if layer.decay_alpha is None else math.exp(-layer.decay_alpha * t)
        out.append(math.sin(phase) * env)
    return _apply_post_filter(out, layer.filter)


def _render_noise(layer: NoiseLayer, rng: random.Random, rate: float, n: int) -> list[float]:
    if layer.filter.kind == "lp_sweep":
        raw = dsp.noise_lp(rng, n, layer.filter.a_start, layer.filter.a_end)
    else:
        raw = [rng.uniform(-1.0, 1.0) for _ in range(n)]
        if layer.filter.kind == "hp":
            raw = dsp.diff_hp(raw)
        elif layer.filter.kind == "lp":
            raw = dsp.one_pole_lp(raw, layer.filter.a)
    out = []
    for i, x in enumerate(raw):
        if layer.decay_alpha is not None:
            env = math.exp(-layer.decay_alpha * i / rate)
        elif layer.rise_power is not None:
            env = (i / max(1, n - 1)) ** layer.rise_power
        else:
            env = 1.0
        out.append(x * env)
    return out


def _render_loop_body(layer: ToneLayer, length: int) -> list[float]:
    """Loop 仕上げ用の1周期本体。フィルタは境界の連続性を保つため ``dsp.circular`` で包んで適用する。"""
    terms = [(mult, weight) for mult, weight, _ in layer.partials]
    body = dsp.seamless_terms(length, terms)
    return dsp.circular(_filter_fn(layer.filter), body)


def _normalized(xs: Sequence[float], peak: float) -> list[float]:
    m = max((abs(x) for x in xs), default=0.0)
    return [x * peak / m for x in xs] if m > 0 else list(xs)


def _ms_to_samples(ms: float, rate: float) -> int:
    return max(1, round(ms / 1000.0 * rate))


def render(patch: Patch) -> SampleSpec:
    """``Patch`` から ``SampleSpec`` を合成する（core/synth.py の唯一の公開エントリ）。"""
    rate = dsp.sample_rate(patch.rate_note)
    rng = random.Random(patch.noise_seed)
    f0 = hz(patch.rate_note + patch.shift) if patch.pitched else 1.0

    if isinstance(patch.finish, OneShot):
        n = max(2, round(patch.finish.duration * rate))
        mix = [0.0] * n
        for wl in patch.layers:
            layer = wl.layer
            if isinstance(layer, ToneLayer):
                sig = _render_tone_oneshot(layer, f0, rate, n)
            elif isinstance(layer, PitchSweepLayer):
                sig = _render_pitch_sweep(layer, rate, n)
            elif isinstance(layer, NoiseLayer):
                sig = _render_noise(layer, rng, rate, n)
            else:
                raise SampleConstraintError(f"{patch.name}: unknown layer type {type(layer).__name__}")
            for i in range(n):
                mix[i] += wl.weight * sig[i]
        if patch.post_filter is not None:
            mix = _apply_post_filter(mix, patch.post_filter)
        if patch.decay_alpha is not None:
            for i in range(n):
                mix[i] *= math.exp(-patch.decay_alpha * i / rate)
        if patch.attack_ms > 0:
            attack_n = _ms_to_samples(patch.attack_ms, rate)
            for i in range(min(attack_n, n)):
                mix[i] *= i / attack_n
        if patch.tail_fade_ms > 0:
            tf = min(_ms_to_samples(patch.tail_fade_ms, rate), n)
            for k in range(tf):
                mix[n - 1 - k] *= k / tf
        xs = _normalized(mix, patch.peak) if patch.peak is not None else mix
        if patch.saturate is not None:
            xs = [math.tanh(patch.saturate * x) for x in xs]
        data = dsp.to_pcm(xs)
        loop = None
    else:
        assert isinstance(patch.finish, Loop)
        length, attack_samples = patch.finish.length, patch.finish.attack_samples
        body = [0.0] * length
        for wl in patch.layers:
            layer_body = _render_loop_body(wl.layer, length)   # type は Patch.__post_init__ が保証
            for i in range(length):
                body[i] += wl.weight * layer_body[i]
        xs = _normalized(body, patch.peak) if patch.peak is not None else body
        if patch.saturate is not None:
            xs = [math.tanh(patch.saturate * x) for x in xs]
        if attack_samples > 0:
            data = dsp.to_pcm(dsp.with_attack(xs, attack_samples))
            loop = (attack_samples // 2, length // 2)
        else:
            data = dsp.to_pcm(xs)
            loop = (0, length // 2)

    return SampleSpec(
        patch.name, data, patch.volume, loop=loop, rate_note=patch.rate_note,
        shift=patch.shift, pitched=patch.pitched, finetune=patch.finetune,
        sounding_hz=_sounding_hz(patch, f0, rate),
    )


def _sounding_hz(patch: Patch, f0: float, rate: float) -> Optional[float]:
    """``rate_note`` で実際に鳴らしたときの基本周波数（``SampleSpec.sounding_hz``）。

    プレイヤーは tracker note t のサンプルを Paula クロック / period[t] で再生する。合成時の基準レート
    ``rate``（dsp.sample_rate）はその半分なので、ワンショットの f0 は実際には 2 倍の高さで鳴る。
    ループは「ループ長 L に K サイクル」なので、最小の K が基本周波数を決める。"""
    if not patch.pitched:
        return None
    real_rate = dsp.CLOCK / PERIODS[patch.rate_note]
    if isinstance(patch.finish, Loop):
        k = min(mult for wl in patch.layers for mult, _w, _a in wl.layer.partials)
        return k * real_rate / patch.finish.length
    tones = [wl for wl in patch.layers if isinstance(wl.layer, ToneLayer)]
    if tones:
        return f0 * real_rate / rate
    sweeps = [wl for wl in patch.layers if isinstance(wl.layer, PitchSweepLayer)]
    if sweeps:
        main = max(sweeps, key=lambda wl: wl.weight)
        return main.layer.freq_end * real_rate / rate
    return None
