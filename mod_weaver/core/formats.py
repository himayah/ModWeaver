"""出力形式の一覧（CLI の ``--format`` の値・拡張子・説明・``--channels`` の意味。DESIGN.md §3.2・§8）。

各形式の能力（行数・pattern 数・サンプルの上限・機能）は ``framework/target.py``、書き出しは ``framework/realize/``
（Realizer）と ``core/native*.py``（writer・検査器）。ここは「どんな形式があるか」の表だけを持つ。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..errors import PlanError

DEFAULT_FORMAT = "mod"


@dataclass(frozen=True)
class OutputFormat:
    name: str            # CLI の値
    extension: str       # ".mod" など（midi だけ名前と拡張子が違う）
    description: str
    channels: str        # ``--channels`` の意味: "choices"（ジャンルが宣言した数から選ぶ）| "max"（上限）| "none"（指定不可）


_FORMATS = (
    OutputFormat("mod", ".mod", "ProTracker MOD (4ch: M.K.; other channel counts: FastTracker xCHN)", "choices"),
    OutputFormat("xm", ".xm", "FastTracker II Extended Module (16-bit samples)", "max"),
    OutputFormat("s3m", ".s3m", "Scream Tracker 3", "max"),
    OutputFormat("it", ".it", "Impulse Tracker (16-bit samples)", "max"),
    OutputFormat("midi", ".mid", "Standard MIDI File (General MIDI)", "none"),
    OutputFormat("mp3", ".mp3", "MP3 audio, 320 kbps (requires ffmpeg with libopenmpt and libmp3lame)", "max"),
)


def get_formats() -> dict[str, OutputFormat]:
    return {f.name: f for f in _FORMATS}


def get_format(name: str) -> OutputFormat:
    try:
        return get_formats()[name]
    except KeyError:
        raise PlanError(f"unknown format {name!r}. choices: {', '.join(get_formats())}") from None


def format_names() -> tuple[str, ...]:
    return tuple(f.name for f in _FORMATS)


def channel_limit(fmt: str) -> Optional[int]:
    """形式の ``--channels`` の上限（``choices``・``none`` の形式は None）。"""
    from ..framework.target import tracker_limits

    return tracker_limits(fmt)[0] if get_format(fmt).channels == "max" else None
