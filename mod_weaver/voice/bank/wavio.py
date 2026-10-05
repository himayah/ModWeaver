"""wav の読み書き（標準ライブラリの ``wave``）。PCM 8/16/24/32-bit・任意のレート・モノラル／ステレオ。"""
from __future__ import annotations

import struct
import wave
from pathlib import Path

from ...errors import VoiceBankError


def read_wav(path: Path) -> tuple[int, list[float]]:
    """(レート, モノラルの -1..1 のサンプル列)。ステレオは平均。浮動小数点・圧縮 wav は VoiceBankError。"""
    try:
        with wave.open(str(path), "rb") as w:
            ch, width, rate, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
            raw = w.readframes(n)
    except (wave.Error, EOFError) as e:
        raise VoiceBankError(f"{path.name}: unsupported wav (PCM only; float/compressed not supported): {e}") from e
    if ch not in (1, 2):
        raise VoiceBankError(f"{path.name}: {ch} channels not supported")
    count = len(raw) // width
    if width == 1:
        vals = [(b - 128) / 128.0 for b in raw[:count]]
    elif width == 2:
        vals = [v / 32768.0 for v in struct.unpack(f"<{count}h", raw[:count * 2])]
    elif width == 3:
        vals = [int.from_bytes(raw[i * 3:i * 3 + 3], "little", signed=True) / 8388608.0 for i in range(count)]
    elif width == 4:
        vals = [v / 2147483648.0 for v in struct.unpack(f"<{count}i", raw[:count * 4])]
    else:
        raise VoiceBankError(f"{path.name}: sample width {width} not supported")
    if ch == 2:
        vals = [(vals[i] + vals[i + 1]) / 2 for i in range(0, len(vals) - 1, 2)]
    return rate, vals


def write_wav16(path: Path, rate: int, x: list[float]) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"".join(struct.pack("<h", max(-32768, min(32767, round(v * 32767)))) for v in x))
