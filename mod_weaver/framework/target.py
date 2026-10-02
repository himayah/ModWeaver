"""出力形式の能力表（FRAMEWORK_REDESIGN.md §4）。

Realizer（§9・§11）とジェネレータ（``ctx.features`` 経由。§4.3）が読む、形式ごとの事実の集まり。
値の出典は ProTracker・ST3・FT2・IT2.14 の仕様と現行実装の定数（§4.2 の表）。XM・IT の 16-bit・
ボリューム列・楽器モード・エンベロープ、拡張音域の音高は実装時の要実測（§13.4。F4 で確かめる）。
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from ..errors import ChannelCountError, PlanError

if TYPE_CHECKING:
    from .genre import Genre


@dataclass(frozen=True)
class SampleCaps:
    bits: int                  # 8 | 16
    target_rate: float         # 描画の目標再生レート（Hz）。MOD は 0（＝現行のまま。§8.2）
    max_bytes: int             # 1サンプルの最大バイト数
    max_samples: int           # サンプル（楽器）数の上限


@dataclass(frozen=True)
class Target:
    format: str                # "mod" | "s3m" | "xm" | "it" | "midi" | "mp3"
    kind: str                  # "tracker" | "midi"
    budget: int                # この曲で使えるチャンネル数（MIDI は 16）
    sample: Optional[SampleCaps]   # MIDI は None
    note_range: tuple[int, int]
    max_rows: int
    max_patterns: int
    max_orders: int
    features: frozenset[str]


# ============================================================
# 形式ごとの値（§4.2）
# ============================================================

_FEATURES: dict[str, frozenset[str]] = {
    "mod": frozenset(),
    "s3m": frozenset({"vol_with_effect", "tremolo", "release", "pan_automation", "glide_bend"}),
    "xm": frozenset({"vol_with_effect", "tremolo", "release", "pan_automation", "glide_bend"}),
    "it": frozenset({"vol_with_effect", "tremolo", "release", "filter", "pan_automation", "glide_bend"}),
    "midi": frozenset({"vol_with_effect", "release", "filter", "pan_automation", "glide_bend"}),
}
_FEATURES["mp3"] = _FEATURES["it"]

_NOTE_RANGE = {
    "mod": (0, 35), "s3m": (0, 95), "xm": (0, 95), "it": (0, 119), "midi": (0, 127),
}

_TRACKER_LIMITS = {
    # format: (max_channels, max_rows, max_patterns, max_orders)
    "mod": (32, 64, 64, 128),
    "s3m": (16, 64, 100, 256),
    "xm": (32, 256, 256, 256),
    "it": (64, 200, 200, 256),
}

_SAMPLE_CAPS = {
    "s3m": SampleCaps(bits=8, target_rate=44100.0, max_bytes=64000, max_samples=99),
    "xm": SampleCaps(bits=16, target_rate=44100.0, max_bytes=4 * 1024 * 1024, max_samples=128),
    "it": SampleCaps(bits=16, target_rate=44100.0, max_bytes=4 * 1024 * 1024, max_samples=99),
}
_MOD_SAMPLE_CAPS = SampleCaps(bits=8, target_rate=0.0, max_bytes=131070, max_samples=31)


def _mod_budget(genre: "Genre", channels_request: Optional[int], seed: int) -> int:
    choices = sorted(genre.mod_channels)
    if not choices:
        raise PlanError(f"{genre.id}: mod_channels must not be empty")
    if channels_request is not None:
        if channels_request not in choices:
            raise ChannelCountError(f"--channels {channels_request} not supported by {genre.id} (choices: {choices})")
        return channels_request
    rng = random.Random(f"{seed}:{genre.id}:channels")
    weights = [genre.mod_channels.get(c, 1) for c in choices]
    return rng.choices(choices, weights=weights)[0]


def _tracker_budget(fmt: str, genre: "Genre", channels_request: Optional[int]) -> int:
    fmt_max, *_ = _TRACKER_LIMITS[fmt if fmt != "mp3" else "it"]
    cap = min(fmt_max, genre.channel_cap) if genre.channel_cap else fmt_max
    if channels_request is not None:
        if not 1 <= channels_request <= cap:
            raise ChannelCountError(f"--channels {channels_request} not supported by format {fmt!r} "
                             f"(1..{cap} for {genre.id})")
        return channels_request
    return cap


def resolve(fmt: str, channels_request: Optional[int], genre: "Genre", seed: int) -> Target:
    """``fmt``・``--channels`` の要求・ジャンルの宣言から ``Target`` を作る（§4.1）。"""
    if fmt not in _FEATURES:
        raise PlanError(f"unknown format {fmt!r}. choices: {', '.join(_FEATURES)}")
    if fmt == "midi":
        if channels_request is not None:
            raise ChannelCountError("--channels is not supported for --format midi")
        return Target(format="midi", kind="midi", budget=16, sample=None, note_range=_NOTE_RANGE["midi"],
                      max_rows=0, max_patterns=0, max_orders=0, features=_FEATURES["midi"])

    if fmt == "mod":
        budget = _mod_budget(genre, channels_request, seed)
        sample = _MOD_SAMPLE_CAPS
    else:
        key = "it" if fmt == "mp3" else fmt
        budget = _tracker_budget(fmt, genre, channels_request)
        sample = _SAMPLE_CAPS[key]   # S3M は長さの上限で実際の oversample 倍率を下げる（§8.2。Realizer の仕事）

    lookup = "it" if fmt == "mp3" else fmt
    _max_ch, max_rows, max_patterns, max_orders = _TRACKER_LIMITS[lookup]
    return Target(format=fmt, kind="tracker", budget=budget, sample=sample, note_range=_NOTE_RANGE[lookup],
                  max_rows=max_rows, max_patterns=max_patterns, max_orders=max_orders, features=_FEATURES[fmt])
