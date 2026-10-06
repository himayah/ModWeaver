"""音源だけを鳴らす最小の曲（IT）を作る（``modweaver_voice.py audition``。DESIGN.md §13.7.2）。

音節の聴き比べ・母音ループ・プリロール整列（§5.6）の確認が目的。声のチャンネルと、拍の頭にクリックを鳴らす
チャンネルの 2ch。母音の頭がクリックと揃って聞こえれば、プリロール整列が効いている。
"""
from __future__ import annotations

import math
import random
import struct
from pathlib import Path

from ...core.model import SampleSpec
from ...core.native import NOTE_CUT, RCell, RealizedSong, RGrid
from ...core.native_it import serialize
from ...errors import VoiceBankError
from . import cache

SPEED, BPM, ROWS_PER_BEAT = 6, 125, 4
TICK_MS = 2500 / BPM
BEATS_PER_SYLLABLE = 2
ROWS = 64
C5 = 60                       # IT: ノート 60（C-5）で ``rate_hz`` のレート＝録音どおりの音高


def kata_to_hira(s: str) -> str:
    return "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in s)


def _click() -> SampleSpec:
    rng = random.Random(1)
    n = 882
    x = [rng.uniform(-1, 1) * math.exp(-i / 120) * 0.6 for i in range(n)]
    return SampleSpec("click", struct.pack(f"<{n}h", *[round(v * 32767) for v in x]), 40,
                      rate_note=24, pitched=False, bits=16, rate_hz=22050.0)


def render(folder: Path, text: str, *, align: bool = True) -> tuple[bytes, list[str]]:
    """(IT のバイト列, 注意の一覧)。``align=False`` はプリロール整列をしない（比較用）。"""
    info = cache.load_info(folder)
    notes: list[str] = []
    seq = []
    for ch in kata_to_hira(text):
        if ch.isspace():
            continue
        if ch in info.syllables:
            seq.append(ch)
        else:
            notes.append(f"'{ch}' is not in the bank (skipped)")
    if not seq:
        raise VoiceBankError("nothing to play: no syllable of the text is in the bank")
    used = sorted(set(seq), key=seq.index)
    ms_per = 1000.0 / info.rate
    pre_ms = {a: info.syllables[a].pre * ms_per for a in used}
    lead_ticks = math.ceil(max(pre_ms.values()) / TICK_MS) if align else 0
    k_rows = math.ceil(lead_ticks / SPEED) if lead_ticks else 0
    delay = k_rows * SPEED - lead_ticks
    samples = [_click()]
    index = {}
    for a in used:
        s = info.syllables[a]
        pad = round(max(0.0, lead_ticks * TICK_MS - pre_ms[a]) / ms_per) if align else 0
        data = bytes(2 * pad) + cache.load_pcm(folder, s)
        loop = (s.loop[0] + pad, s.loop[1]) if s.loop else None
        samples.append(SampleSpec(f"v:{info.id[:8]}:{len(index):02d}", data, 64, loop=loop, bits=16,
                                  rate_hz=float(info.rate), sounding_hz=info.home_hz))
        index[a] = len(samples)
    step = ROWS_PER_BEAT * BEATS_PER_SYLLABLE
    lead_rows = step
    total = lead_rows + step * len(seq) + step
    n_pat = math.ceil(total / ROWS)
    grids = [RGrid(ROWS, 2) for _ in range(n_pat)]

    def put(row: int, ch: int, cell: RCell) -> None:
        grids[row // ROWS].put(row % ROWS, ch, cell)

    for r in range(0, n_pat * ROWS, ROWS_PER_BEAT):
        put(r, 1, RCell(note=C5, sample=1, vol=40))
    for i, a in enumerate(seq):
        beat_row = lead_rows + i * step
        fx = ("S", 0xD0 | delay) if delay else None
        put(beat_row - k_rows, 0, RCell(note=C5, sample=index[a], vol=64, fx=fx))
        put(beat_row + step - k_rows - 2, 0, RCell(note=NOTE_CUT))      # 音節ごとに切る（隣と混ざらず聴き分けやすい）
    grids[0].put(0, 0, RCell(fx=("T", BPM)))
    rs = RealizedSong("it", "ModWeaver audition", samples, grids, list(range(n_pat)), (64, 192),
                      BPM, SPEED, instrument_names=tuple(s.name for s in samples),
                      sample_release=tuple(None for _ in samples))
    if lead_ticks:
        notes.append(f"preroll: vowel onset lead = {lead_ticks} ticks ({lead_ticks * TICK_MS:.0f} ms), "
                     f"notes placed {k_rows} row(s) early with SD{delay}")
    return serialize(rs), notes
