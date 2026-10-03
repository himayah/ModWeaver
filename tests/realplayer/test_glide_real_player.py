"""``Glide`` の速さを実プレイヤー（libopenmpt）で確かめる（DESIGN.md §9.2「拡張音域の Glide の速さ」・§16.9）。

``tracker._glide_param`` が求めた ``3xx``/``Gxx`` の速さで、1 オクターブのグライドが指定した step 数で届く
（MOD・S3M・XM・IT。周期は period の線形補間なので、周波数が目標の 97% に達するのは所要時間の約 97% の時点）。
"""
from __future__ import annotations

import pytest

from mod_weaver.core.native import RCell
from mod_weaver.framework.realize.encode import Codec
from mod_weaver.framework.realize.tracker import _glide_param
from tests.realplayer.test_f4_effects import FORMATS, RATE, REF_NOTE, ROW_S, _play, _sample, _song
from tests.realplayer import requires_openmpt

np = pytest.importorskip("numpy")
pytestmark = requires_openmpt

STEPS = 4
TICKS_PER_ROW = 6


def _freq_track(a, win=0.03, hop=0.01):
    n, h = int(win * RATE), int(hop * RATE)
    out = []
    for i in range(0, len(a) - n, h):
        zc = np.count_nonzero(np.diff(np.signbit(a[i:i + n])))
        out.append((i / RATE, zc / 2 / win))
    return out


def _reach_time(fmt: str, interval: int) -> tuple[float, float]:
    """``interval`` 半音のグライドが、目標の周波数の 97% に届くまでの秒数と、`_glide_param` が見込んだ秒数。"""
    codec = Codec(fmt)
    base = REF_NOTE[fmt] - interval
    spec = _sample(8 if fmt in ("mod", "s3m") else 16)
    param = _glide_param(codec, spec, base, spec, base + interval, STEPS * (TICKS_PER_ROW - 1))
    start_row = 8
    cells = {(0, 0): RCell(note=base, sample=1, vol=None if fmt == "mod" else 64),
             (start_row, 0): RCell(note=base + interval, sample=1, fx=codec.glide(param))}
    cells.update({(r, 0): RCell(fx=codec.glide(param)) for r in range(start_row + 1, 60)})
    track = _freq_track(_play(_song(fmt, cells, spec=spec), 7.0))
    t0 = start_row * ROW_S
    f0 = np.median([f for t, f in track if 0.2 < t < t0 - 0.05])
    f1 = np.median([f for t, f in track if t > t0 + 4])
    reach = next(t for t, f in track if t > t0 and f >= 0.97 * f1) - t0
    return reach, STEPS * ROW_S


@pytest.mark.parametrize("fmt", FORMATS)
@pytest.mark.parametrize("interval", (7, 12))
def test_glide_reaches_the_target_in_the_requested_steps(fmt, interval):
    reach, nominal = _reach_time(fmt, interval)
    assert abs(reach - 0.97 * nominal) <= 0.12, (fmt, interval, reach, nominal)
