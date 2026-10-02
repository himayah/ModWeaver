"""奏法・音高・row コマンドの形式ごとの表現（FRAMEWORK_REDESIGN.md §9.6 の表）。

形式の差はこのファイルの表に閉じ込める（§17.1 の原則2）。Realizer（``tracker.py``）は ``Codec`` を
通してしか形式の表記に触れない。コマンドは ``(1文字, param)``。param は MOD の単位で受け取り、
形式の表記に変えるだけ（D12）。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ...core.model import SampleSpec
from ...core.native import NOTE_CUT, NOTE_OFF, RCell
from ...errors import PitchRangeError, PlanError

# 形式ごとの表（kind → コマンド文字）。E 系のサブコマンドは別に扱う。
_LETTER = {
    #            mod   s3m  xm   it
    "vibrato":  ("4", "H", "4", "H"),
    "tremolo":  ("7", "R", "7", "R"),
    "arpeggio": ("0", "J", "0", "J"),
    "glide":    ("3", "G", "3", "G"),
    "offset":   ("9", "O", "9", "O"),
}
_FMT_INDEX = {"mod": 0, "s3m": 1, "xm": 2, "it": 3}

# 基準ノート（0 始まり。C-0 = 0）: ``rate_hz`` で鳴る音（§9.6）。MOD は使わない
_N_REF = {"s3m": 48, "xm": 48, "it": 60}
_NOTE_RANGE = {"mod": (0, 35), "s3m": (0, 95), "xm": (0, 95), "it": (0, 119)}

# 1セルに入りきらないときのエフェクトの優先順位（§9.6。小さいほど強い）
PRIORITY = {"delay": 1, "glide": 2, "retrig": 3, "cut": 3, "arpeggio": 4, "offset": 5,
            "vibrato": 6, "tremolo": 6, "volslide": 7, "pan": 8, "cutoff": 8}


@dataclass(frozen=True)
class Codec:
    fmt: str                      # "mod" | "s3m" | "xm" | "it"

    # ---- 形式の事実 ----
    @property
    def n_ref(self) -> int:
        return _N_REF[self.fmt]

    @property
    def note_range(self) -> tuple[int, int]:
        return _NOTE_RANGE[self.fmt]

    @property
    def exclusive_vol_fx(self) -> bool:
        """音量とエフェクトが同じセルに置けない（MOD だけ。音量が Cxx なので）。"""
        return self.fmt == "mod"

    @property
    def has_release_env(self) -> bool:
        """音量エンベロープでリリースを表せる形式（§9.7）。"""
        return self.fmt in ("xm", "it")

    # ---- 音高 ----
    def note(self, spec: SampleSpec, rounded_pitch: Optional[int], *, where: str = "") -> int:
        """書かれた音高（整数に丸め済み）→ ``RCell.note``。音程の無い楽器は常に基準の位置。"""
        lo, hi = self.note_range
        if self.fmt == "mod":
            t = spec.rate_note if not spec.pitched or rounded_pitch is None else rounded_pitch - spec.shift
            if not lo <= t <= hi:
                raise PitchRangeError(f"{spec.name}: logical note {rounded_pitch} -> tracker note {t} out of "
                                       f"range (shift={spec.shift}){where}")
            return t
        if not spec.pitched or rounded_pitch is None:
            return self.n_ref
        n = self.n_ref + (rounded_pitch - spec.shift - spec.rate_note)
        if not lo <= n <= hi:
            raise PitchRangeError(f"{spec.name}: logical note {rounded_pitch} -> {self.fmt} note {n} out of "
                                   f"range {lo}..{hi}{where}")
        return n

    # ---- コマンド ----
    def letter(self, kind: str) -> str:
        return _LETTER[kind][_FMT_INDEX[self.fmt]]

    def vibrato(self, p: int):
        return self.letter("vibrato"), p

    def tremolo(self, p: int):
        """S3M・IT のトレモロ深さは MOD・XM の半分（実測。深さのニブルに比例して正確に 1/2）なので、深さを 2 倍にして
        合わせる（上限 15。MOD の深さ 8 以上は S3M・IT では頭打ちになる）。"""
        if self.fmt in ("s3m", "it"):
            return self.letter("tremolo"), (p & 0xF0) | min(15, 2 * (p & 0x0F))
        return self.letter("tremolo"), p

    def arpeggio(self, x: int, y: int):
        return self.letter("arpeggio"), (x << 4) | y

    def glide(self, p: int):
        return self.letter("glide"), p

    def offset(self, xx: int):
        return self.letter("offset"), max(0, min(255, xx))

    def delay(self, ticks: int):
        return ("S", 0xD0 | ticks) if self.fmt in ("s3m", "it") else ("E", 0xD0 | ticks)

    def retrig(self, ticks: int):
        return ("Q", ticks) if self.fmt in ("s3m", "it") else ("E", 0x90 | ticks)

    def cut(self, ticks: int):
        if not 1 <= ticks <= 15:
            raise PlanError(f"Cut ticks out of range: {ticks}")
        return ("S", 0xC0 | ticks) if self.fmt in ("s3m", "it") else ("E", 0xC0 | ticks)

    def speed(self, ticks: int):
        return ("A", ticks) if self.fmt in ("s3m", "it") else ("F", ticks)

    def tempo(self, bpm: int):
        return ("T", bpm) if self.fmt in ("s3m", "it") else ("F", bpm)

    def pattern_break(self):
        return ("C", 0) if self.fmt in ("s3m", "it") else ("D", 0)

    def volume_slide_down(self, amount: int):
        return ("D", amount) if self.fmt in ("s3m", "it") else ("A", amount)

    def pan(self, value: int):
        """None は表せない形式（MOD）。"""
        if self.fmt == "s3m":
            return "S", 0x80 | (value >> 4)
        if self.fmt == "xm":
            return "8", value
        if self.fmt == "it":
            return "X", value
        return None

    def cutoff(self, value: int):
        return ("Z", value) if self.fmt == "it" else None

    # ---- セル ----
    def stop_cell(self, release_s: Optional[float] = None) -> RCell:
        """その lane の音を止めるセル。``release_s`` があり、エンベロープでリリースできる形式ならキーオフ。"""
        if release_s is not None and self.has_release_env:
            return RCell(note=NOTE_OFF)
        if self.fmt in ("s3m", "it"):
            return RCell(note=NOTE_CUT)
        return RCell(vol=0)      # MOD: Cxx 00、XM: ボリューム列 0
