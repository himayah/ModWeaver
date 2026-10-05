"""歌声の Realizer 側の処理（VOCAL_DESIGN.md §5.1・§5.4〜§5.6）。

``VoiceBackend``（声の源）が音節を波形にし、``VoicePlan`` が曲全体の整合をとる:

1. 音域合わせ（§5.5）: 歌声パートの音高の中央値を声の源の自然な高さに合わせてオクターブ単位で移し、範囲を超える個別の音だけ
   1 オクターブ折り返す。**Score の ``pitch`` は変えず**、Placement の音高だけを物理的な音高に直す（V-4）。
2. プリロール整列（§5.6）: 音節の母音の頭（``pre``）が拍に乗るよう、各サンプルの先頭に無音を足し、音符を ``L`` tick 先に置く。
   ``L`` は曲の初期 BPM とスウィングなしの tick 長で求める（スウィング・テンポ変化のずれは許容）。
3. サンプル: 音節 × 音高帯ごとに 16-bit のサンプルを作る（``VoiceSlot``）。
"""
from __future__ import annotations

import dataclasses
import math
import statistics
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Optional, Protocol

from ...core import pitch as pitchmod
from ...core.model import SampleSpec
from ...errors import PlanError
from ...voice import formant
from ...voice.bank import cache
from ...voice.phoneme import KANA_OF_VOWEL, Syllable
from .lanes import Placement

if TYPE_CHECKING:
    from ...framework.genre import Genre, Voice
    from ..target import Target

FOLD_LIMIT_SEMITONES = 6.5
BUCKET_SEMITONES = 6                 # formant の音高帯の幅（半オクターブ）
LOGICAL_C1_HZ = 65.4064


@dataclass(frozen=True)
class VoiceSlot:
    """歌声のサンプルの鍵（``SampleKey`` の 4 要素とは別の型。VOCAL_DESIGN.md §5.4）。"""
    inst: str
    syl: str
    bucket: int
    pan: Optional[int] = None


@dataclass(frozen=True)
class VoiceSample:
    data: list[float]                 # -1..1
    rate: int
    loop: Optional[tuple[int, int]]   # (開始, 長さ)（サンプル単位）
    home_hz: float                    # 録音（描画）どおりに鳴らしたときの基本周波数
    pre: int                          # 母音の頭（サンプル）


@dataclass(frozen=True)
class VoiceInfo:
    id: str
    credit: str = ""
    credit_required: bool = False
    terms_url: str = ""
    terms_checked: bool = True
    fingerprint: str = ""
    fixed_pitch: bool = False         # True: 録音の高さが決まっている（音域合わせが要る）。formant は False


class VoiceBackend(Protocol):
    info: VoiceInfo

    def covers(self, syl: Syllable) -> bool: ...
    def bucket(self, pitch: float) -> int: ...
    def render(self, syl: Syllable, bucket: int, timbre: str) -> VoiceSample: ...
    def home_hz(self) -> Optional[float]: ...


class FormantBackend:
    info = VoiceInfo(id="formant", credit="", credit_required=False, terms_checked=True)

    def covers(self, syl: Syllable) -> bool:
        return not syl.onset and syl.nucleus in formant.VOWELS

    def bucket(self, pitch: float) -> int:
        return round(pitch / BUCKET_SEMITONES)

    def home_hz(self) -> Optional[float]:
        return None

    def render(self, syl: Syllable, bucket: int, timbre: str) -> VoiceSample:
        r = formant.render_vowel(syl.nucleus, pitchmod.hz(bucket * BUCKET_SEMITONES), timbre)
        return VoiceSample(r.data, r.rate, r.loop, r.home_hz, r.pre)


class UtauBackend:
    """取り込み済みの UTAU 形式の音源（``voice/bank/cache``）。P3 は単独の音（CV）の母音・音節を引く。"""

    def __init__(self, folder: Path) -> None:
        self.folder = folder
        bank = cache.load_info(folder)
        self.bank = bank
        self.info = VoiceInfo(id=bank.id, credit=bank.credit, credit_required=bank.credit_required,
                              terms_url=bank.terms_url, terms_checked=bank.terms_checked,
                              fingerprint=bank.fingerprint, fixed_pitch=True)

    def alias(self, syl: Syllable) -> Optional[str]:
        for cand in (syl.text, KANA_OF_VOWEL.get(syl.nucleus, "") if not syl.onset else ""):
            if cand and cand in self.bank.syllables:
                return cand
        return None

    def covers(self, syl: Syllable) -> bool:
        return self.alias(syl) is not None

    def bucket(self, pitch: float) -> int:
        return 0

    def home_hz(self) -> Optional[float]:
        return self.bank.home_hz

    def render(self, syl: Syllable, bucket: int, timbre: str) -> VoiceSample:
        s = self.bank.syllables[self.alias(syl)]
        raw = cache.load_pcm(self.folder, s)
        data = [v / 32767.0 for v in struct.unpack(f"<{s.n}h", raw)]
        return VoiceSample(data, self.bank.rate, s.loop, s.f0 or self.bank.home_hz or 220.0, s.pre)


def logical_of_hz(hz: float) -> float:
    """周波数 → logical note（小数）。``pitch.hz`` の逆関数。"""
    return 12.0 * math.log2(hz / LOGICAL_C1_HZ)


class VoicePlan:
    def __init__(self, backend: VoiceBackend, genre: "Genre", bpm: int) -> None:
        self.backend = backend
        self.genre = genre
        self.bpm = bpm
        self.lead_ticks = 0
        self.octave = 0                 # 音域合わせで移したオクターブ数（物理 = 書かれた音高 − 12×octave）
        self.notes: list[str] = []      # バナー・report 用の注意
        self._cache: dict = {}
        self._syl_of: dict = {}

    # ---- Placement の前処理 ----
    def prepare(self, placements_by_section: dict, tick_for_step: dict) -> None:
        """歌声の Placement の音高を物理的な音高に直し、プリロールの先行を掛ける（その場で書き換える）。
        ``tick_for_step``: 区間名 → (1 step の tick 数, ``Swing`` または None)。"""
        voice_ps = [p for ps, _a in placements_by_section.values() for p in ps if p.kind == "note" and p.syl is not None]
        if not voice_ps:
            return
        for p in voice_ps:
            if not self.backend.covers(p.syl):
                raise PlanError(f"voice {self.backend.info.id!r} cannot sing syllable {p.syl.text!r} "
                                f"(VOCAL_DESIGN.md §5.1 fallback is not implemented yet)")
        home = self.backend.home_hz()
        if home:
            self._fold(placements_by_section, voice_ps, logical_of_hz(home))
            voice_ps = [p for ps, _a in placements_by_section.values() for p in ps
                        if p.kind == "note" and p.syl is not None]
        self._lead(placements_by_section, voice_ps, tick_for_step)

    def _fold(self, by_section: dict, voice_ps: list[Placement], h: float) -> None:
        m = statistics.median(p.pitch for p in voice_ps)
        self.octave = round((m - h) / 12)
        folded = 0
        remap: dict[int, Placement] = {}
        for p in voice_ps:
            n = p.pitch - 12 * self.octave
            if n - h > FOLD_LIMIT_SEMITONES:
                n -= 12
                folded += 1
            elif h - n > FOLD_LIMIT_SEMITONES:
                n += 12
                folded += 1
            remap[id(p)] = dataclasses.replace(p, pitch=n)
        for name, (ps, autos) in by_section.items():
            by_section[name] = ([remap.get(id(p), p) for p in ps], autos)
        if folded:
            self.notes.append(f"voice range: {folded} note(s) folded by an octave (home {home_name(h)})")

    def _lead(self, by_section: dict, voice_ps: list[Placement], tick_for_step: dict[str, int]) -> None:
        ms_tick = 2500.0 / self.bpm
        pre_ms = max(vs.pre / vs.rate * 1000.0 for vs in (self._render(p.syl, self.backend.bucket(p.pitch)) for p in voice_ps))
        self.lead_ticks = math.ceil(pre_ms / ms_tick - 1e-9) if pre_ms > 0 else 0
        if not self.lead_ticks:
            return
        from ..score import Delay
        for name, (ps, autos) in by_section.items():
            tps, swing = tick_for_step[name]

            def row_len(i: int) -> int:
                return tps if swing is None else (swing.long if i % 2 == 0 else swing.short)

            out, seen = [], set()
            for p in ps:
                if p.kind == "note" and p.syl is not None:
                    row, elapsed = p.step, 0
                    while elapsed < self.lead_ticks and row > 0:      # 母音の頭の L tick 前の row を探す（スウィングは row ごとの長さ）
                        row -= 1
                        elapsed += row_len(row)
                    delay = elapsed - self.lead_ticks
                    if delay < 0:                    # 区間の頭より前: 行 0・Delay 0（母音が遅れる。VOCAL_DESIGN.md §5.6-4）
                        delay = 0
                    arts = p.arts + ((Delay(delay),) if delay else ())
                    p = dataclasses.replace(p, step=row, arts=arts,
                                            dur=None if p.dur is None else p.dur + (p.step - row))
                    if (p.lane, p.step) in seen:
                        continue
                    seen.add((p.lane, p.step))
                out.append(p)
            by_section[name] = (sorted(out, key=lambda q: q.step), autos)
        self.notes.append(f"voice preroll: {self.lead_ticks} tick(s) ({self.lead_ticks * ms_tick:.0f} ms)")

    # ---- サンプル ----
    def _render(self, syl: Syllable, bucket: int) -> VoiceSample:
        key = (syl.key, bucket)
        if key not in self._cache:
            timbre = next((i.timbre for i in self.genre.instruments.values() if hasattr(i, "timbre")), "female")
            self._cache[key] = self.backend.render(syl, bucket, timbre)
        return self._cache[key]

    def slot_for(self, p: Placement, pan: Optional[int]) -> VoiceSlot:
        slot = VoiceSlot(p.inst, p.syl.key, self.backend.bucket(p.pitch), pan)
        self._syl_of[slot] = p.syl
        return slot

    def sample(self, slot: VoiceSlot, inst: "Voice") -> SampleSpec:
        vs = self._render(self._syl_of[slot], slot.bucket)
        ms_tick = 2500.0 / self.bpm
        pad = max(0, round(self.lead_ticks * ms_tick / 1000.0 * vs.rate) - vs.pre)
        data = [0.0] * pad + vs.data
        pcm = struct.pack(f"<{len(data)}h", *[max(-32768, min(32767, round(v * 32767))) for v in data])
        h = logical_of_hz(vs.home_hz)
        s_note = round(h)
        rate_note = 24
        rate_hz = vs.rate * 2 ** ((s_note - h) / 12)
        loop = (vs.loop[0] + pad, vs.loop[1]) if vs.loop else None
        name = f"v:{self.backend.info.id[:6]}:{slot.syl}.{slot.bucket}"
        return SampleSpec(name=name.encode("ascii", "replace").decode("ascii")[:22], data=pcm,
                          volume=inst.volume if inst.volume is not None else 48, loop=loop, rate_note=rate_note,
                          shift=s_note - rate_note, pitched=True, pan=slot.pan if slot.pan is not None else 128,
                          sounding_hz=vs.home_hz, bits=16, rate_hz=rate_hz)


def home_name(h: float) -> str:
    return f"{LOGICAL_C1_HZ * 2 ** (h / 12):.0f} Hz"
