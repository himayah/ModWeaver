"""第三者の実プレイヤー（ffmpeg 内蔵の libopenmpt＝OpenMPT の再生エンジン）で出力を検証する補助
（DESIGN.md §9.2）。

自作 writer を自作 parser で読み戻すだけの検査は、仕様の誤解を writer・parser が共有していると検出できない
（XM header_size・XM 音高の2件がまさにそれだった）。ここでは独立した実装で実際に再生し、
「開ける・鳴る・MOD と同じ高さ／長さで鳴る」ことを確かめる。ffmpeg が無い環境では skip する。
"""
from __future__ import annotations

import array
import math
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from functools import lru_cache

import pytest

RATE = 22050


@lru_cache(maxsize=1)
def ffmpeg_with_openmpt() -> str | None:
    exe = os.environ.get("MODWEAVER_FFMPEG") or shutil.which("ffmpeg")
    if not exe:
        return None
    try:
        out = subprocess.run([exe, "-hide_banner", "-demuxers"], capture_output=True, text=True, timeout=30).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    return exe if "libopenmpt" in out else None


requires_openmpt = pytest.mark.skipif(ffmpeg_with_openmpt() is None, reason="ffmpeg with libopenmpt not available")


@dataclass
class Decoded:
    samples: array.array        # mono s16
    stderr: str

    @property
    def seconds(self) -> float:
        return len(self.samples) / RATE

    def mean_freq(self, start: float = 0.0, length: float | None = None) -> float:
        """ゼロ交差法による平均周波数（粗いが、形式間で同じ音高かどうかの比較には十分）。"""
        a = self._window(start, length)
        zc = sum(1 for i in range(1, len(a)) if (a[i - 1] < 0) != (a[i] < 0))
        return zc / (len(a) / RATE) / 2 if a else 0.0

    def rms(self, start: float = 0.0, length: float | None = None) -> float:
        a = self._window(start, length)
        return math.sqrt(sum(x * x for x in a) / len(a)) if a else 0.0

    def envelope(self, block: float = 0.25) -> list[float]:
        n = int(block * RATE)
        return [self.rms(i / RATE, block) for i in range(0, len(self.samples) - n, n)]

    def _window(self, start: float, length: float | None):
        lo = int(start * RATE)
        hi = len(self.samples) if length is None else lo + int(length * RATE)
        return self.samples[lo:hi]


def decode(data: bytes, ext: str, *, demuxer: str | None = "libopenmpt", stereo: bool = False):
    """``stereo=True`` なら (left, right) の Decoded の組を返す。"""
    exe = ffmpeg_with_openmpt()
    assert exe, "ffmpeg with libopenmpt required"
    with tempfile.TemporaryDirectory() as d:
        src = os.path.join(d, f"song{ext}")
        with open(src, "wb") as f:
            f.write(data)
        cmd = [exe, "-hide_banner", "-nostdin", "-loglevel", "error"]
        if demuxer:
            cmd += ["-f", demuxer]
        cmd += ["-i", src, "-ac", "2" if stereo else "1", "-ar", str(RATE), "-f", "s16le", "-"]
        proc = subprocess.run(cmd, capture_output=True, timeout=300)
    assert proc.returncode == 0, proc.stderr.decode(errors="replace")
    a = array.array("h")
    a.frombytes(proc.stdout[: len(proc.stdout) // 4 * 4])
    err = proc.stderr.decode(errors="replace")
    if stereo:
        return Decoded(a[0::2], err), Decoded(a[1::2], err)
    return Decoded(a, err)


def peak(data: bytes, ext: str) -> float:
    """実プレイヤーで再生した最大振幅（1.0 = 0 dBFS）。float のまま・リサンプリングなしで読むので、
    1.0 以上なら整数 PCM に変換した時点で音割れする。"""
    exe = ffmpeg_with_openmpt()
    assert exe, "ffmpeg with libopenmpt required"
    with tempfile.TemporaryDirectory() as d:
        src = os.path.join(d, f"song{ext}")
        with open(src, "wb") as f:
            f.write(data)
        proc = subprocess.run([exe, "-hide_banner", "-nostdin", "-loglevel", "error", "-f", "libopenmpt",
                               "-i", src, "-ac", "2", "-f", "f32le", "-"], capture_output=True, timeout=300)
    assert proc.returncode == 0, proc.stderr.decode(errors="replace")
    a = array.array("f")
    a.frombytes(proc.stdout[: len(proc.stdout) // 4 * 4])
    return max(max(a), -min(a)) if a else 0.0


def correlation(x: list[float], y: list[float]) -> float:
    n = min(len(x), len(y))
    x, y = x[:n], y[:n]
    mx, my = sum(x) / n, sum(y) / n
    sxy = sum((a - mx) * (b - my) for a, b in zip(x, y))
    sx = math.sqrt(sum((a - mx) ** 2 for a in x))
    sy = math.sqrt(sum((b - my) ** 2 for b in y))
    return sxy / (sx * sy) if sx and sy else 0.0
