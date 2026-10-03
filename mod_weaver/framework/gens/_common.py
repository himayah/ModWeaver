"""ジェネレータ部品が共有する小さな補助（DESIGN.md §5.8）。"""
from __future__ import annotations

from ...core.model import ChordDef
from ...core.pitch import fold_into_range


def arp_tones(chord: ChordDef, register: tuple[int, int]) -> list[int]:
    """和音の構成音を ``register`` に折り返した音高の列（現行 ``band_common._arp_tones`` と同じ）。"""
    pcs = sorted({t % 12 for t in chord.chord_tones}, key=lambda pc: (pc - chord.harmony) % 12)
    lo, hi = register
    notes = sorted({fold_into_range(lo + ((pc - lo) % 12), lo, hi) for pc in pcs})
    return notes or [fold_into_range(chord.harmony, lo, hi)]


def scaled_step(step16: float, steps: int) -> int:
    """16 step（4/4 の16分）基準の位置を、実際の小節の step 数に比例させる。"""
    return min(steps - 1, int(round(step16 * steps / 16.0)))
