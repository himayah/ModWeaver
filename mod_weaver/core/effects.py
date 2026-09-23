"""MOD 形式のエフェクト（Cell.effect/param）を Scream Tracker 3／Impulse Tracker のエフェクト
（A=1 … Z=26 の文字コマンド）へ変換する（FORMAT_TEMPO_DESIGN §4.3 の表）。

``Cell.vol``（MOD では effect C）は S3M/IT では volume column に置くため、ここでは扱わない。
変換表に無いエフェクトは黙って落とさず ``CellConflictError`` で止める（将来のジャンルが新しい
エフェクトを使い始めたとき、別形式で音が化けたことに気づかないまま出力されるのを防ぐ）。
"""
from __future__ import annotations

from ..errors import CellConflictError


def letter(ch: str) -> int:
    """``"A"`` → 1 … ``"Z"`` → 26。"""
    return ord(ch) - ord("A") + 1


# E 系サブコマンド（上位ニブル）→ (S3M/IT の文字, 下位ニブルに付ける上位ニブル)
_EXTENDED = {
    0x1: ("F", 0xF0),   # E1x fine porta up   → FFx
    0x2: ("E", 0xF0),   # E2x fine porta down → EFx
    0x6: ("S", 0xB0),   # E6x pattern loop    → SBx
    0x9: ("Q", 0x00),   # E9x retrigger       → Q0x（音量変化なし）
    0xC: ("S", 0xC0),   # ECx note cut        → SCx
    0xD: ("S", 0xD0),   # EDx note delay      → SDx
    0xE: ("S", 0xE0),   # EEx pattern delay   → SEx
}

MAX_COARSE_SLIDE = 0xDF   # S3M/IT の Exx/Fxx は 0xE0 以上を fine/extra-fine と解釈する


def to_st(effect: int, param: int) -> tuple[int, int]:
    """MOD の (effect, param) → S3M/IT の (command, info)。effect=param=0 は (0, 0)。"""
    if effect == 0:
        return (letter("J"), param) if param else (0, 0)
    if effect == 0x1:
        return letter("F"), min(param, MAX_COARSE_SLIDE)
    if effect == 0x2:
        return letter("E"), min(param, MAX_COARSE_SLIDE)
    if effect == 0x3:
        return letter("G"), param
    if effect == 0x4:
        return letter("H"), param
    if effect == 0x9:
        return letter("O"), param
    if effect == 0xA:
        # MOD Axy は x(上げ) を優先する。S3M/IT の Dxy は片方が 0 のときだけ同じ意味になる
        up, down = param >> 4, param & 0x0F
        return letter("D"), (up << 4) if up else down
    if effect == 0xB:
        return letter("B"), param
    if effect == 0xD:
        if param != 0:
            raise CellConflictError(f"pattern break to a row other than 0 is not supported: D{param:02X}")
        return letter("C"), 0
    if effect == 0xE:
        sub = param >> 4
        if sub not in _EXTENDED:
            raise CellConflictError(f"no S3M/IT equivalent for MOD effect E{param:02X}")
        ch, hi = _EXTENDED[sub]
        return letter(ch), hi | (param & 0x0F)
    if effect == 0xF:
        return (letter("A"), param) if param < 0x20 else (letter("T"), param)
    raise CellConflictError(f"no S3M/IT equivalent for MOD effect {effect:X}{param:02X}")
