"""MidiRealizer（FRAMEWORK_REDESIGN.md §11）: Score から直接 SMF（format 1・PPQ 480）を作る。

トラッカー用の lane・ladder は使わない（予算の考え方が無い）。**全パートを入れる**（``min_channels``・``channel_cap``
は無視する。MIDI は「ジャンルの意図を GM 音源で聴ける」ことが目的で、厚い編成が意図そのもの）。

- 時間: 1 tracker tick（= 1拍の 1/24）= 20 MIDI tick。step の長さは ``24 // steps_per_beat`` tracker tick。
  スウィングは 2 step の組の後ろの step を ``long`` tick 目から始める。
- トラック: パートごとに 1 トラック。打楽器のパート（全楽器が ``GmVoice(drum_note=)``）は MIDI ch10、他は宣言順に
  ch1–9・11–16。足りなければ同じ program のパートで相乗りし、それでも足りなければ ``PlanError``。
- 音高: 実音（§8.1 の基準 ``sounding_hz × 2^((t − rate_note)/12)``）から MIDI ノート番号を求め、整数でない部分と
  ``tune_cents`` はピッチベンド。セントの違う音が重なるパートは、セントの値ごとに別の MIDI チャンネルにする。
- 音量: velocity ＝ ``round(vel/64 × 127)``。曲の最大が 127 になるまで一律に持ち上げる（§9.10）。
"""
from __future__ import annotations

import math
import struct
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

from ...core import dsp, synth
from ...core.midi import _cc, _meta, _track, OFF, CTRL, ON
from ...core.pitch import PERIODS
from ...errors import PlanError
from ..score import Arpeggio, Automation, Cut, Delay, Glide, NoteEvent, NoteOff, Retrig, TempoEvent, Tremolo, Vibrato

if TYPE_CHECKING:
    from ..genre import Genre
    from ..plan import SectionPlan, SongPlan
    from ..score import Score
    from ..target import Target

PPQ = 480
TICK = PPQ // 24                  # 1 tracker tick = 20 MIDI tick
DRUM_CHANNEL = 9
DRUM_KEY = -9999                  # (パート, DRUM_KEY) ＝ そのパートの打楽器の音のチャンネル
MELODIC_CHANNELS = tuple(c for c in range(16) if c != DRUM_CHANNEL)
UNPITCHED_NOTE = 60               # 音高を持たない非ドラム音色の発音 note
BEND_CENTER = 8192
BEND_RANGE_DEFAULT, BEND_RANGE_GLIDE = 2, 12      # ±半音
GLIDE_RAMP_TICKS = TICK           # グライドのピッチベンドを動かす間隔（1 tracker tick）


@dataclass
class _Note:
    """1 つの発音（Score の NoteEvent の構成音 1 つ）。時刻は曲頭からの MIDI tick。"""
    part: str
    inst: str
    start: int
    end: Optional[int]                 # None は未確定（次の発音・自然減衰・区間の終わりから決める）
    section_end: int
    midi: float                        # 小数付きの MIDI ノート番号（ベンド込み）
    vel: int                           # 0..64（tracker の音量。None は楽器の既定音量に解決済み）
    arts: tuple = ()
    step_time: object = None           # step → 絶対 tick（区間の時間割。奏法の位置の計算に使う）
    step: int = 0
    explicit_end: bool = False


@dataclass
class _Voice:
    """書き出す直前の音（アルペジオ・連打は複数の _Voice になる）。"""
    part: str
    inst: str
    start: int
    end: int
    midi: float
    vel: int
    glide_from: Optional[float] = None     # 直前の音からのグライド（半音の差。ベンドで動かす）
    glide_ticks: int = 0
    cc1: list = field(default_factory=list)   # (tick, 値) ビブラートの CC1


class _Info:
    """楽器ごとの実音の情報（描画は oversample 1 のキャッシュを使う）。"""

    def __init__(self, genre: "Genre") -> None:
        self.genre = genre
        self._spec = {}

    def spec(self, inst: str):
        if inst not in self._spec:
            self._spec[inst] = synth.render(self.genre.instruments[inst].patch)
        return self._spec[inst]

    def default_volume(self, inst: str) -> int:
        i = self.genre.instruments[inst]
        return i.volume if i.volume is not None else self.spec(inst).volume

    def midi_pitch(self, inst: str, n: float) -> float:
        """書かれた音高 n（logical note）の実音の MIDI ノート番号（小数）。"""
        i = self.genre.instruments[inst]
        spec = self.spec(inst)
        if spec.sounding_hz is None:
            base = 36.0 + n
        else:
            t = n - spec.shift
            base = 69.0 + 12.0 * math.log2(spec.sounding_hz / 440.0) + (t - spec.rate_note)
        return base + i.tune_cents / 100.0

    def natural_ticks(self, inst: str, n: Optional[float], bpm: int) -> Optional[int]:
        """ワンショットが鳴り終わるまでの MIDI tick（ループは None）。tick への換算は曲の初期テンポ。"""
        spec = self.spec(inst)
        if spec.loop is not None:
            return None
        t = spec.rate_note
        if spec.pitched and n is not None:
            t = n - spec.shift
        rate = dsp.CLOCK / PERIODS[spec.rate_note] * 2 ** ((t - spec.rate_note) / 12)
        seconds = len(spec.data) / rate
        return max(1, round(seconds * bpm / 60 * PPQ))


def _step_time(base: int, sec_plan: "SectionPlan"):
    """区間の step → 絶対 tick（スウィングを含む）。"""
    tps = sec_plan.meter.ticks_per_step * TICK
    swing = sec_plan.swing

    def at(step: int) -> int:
        if swing is None:
            return base + step * tps
        return base + (step // 2) * 2 * tps + (swing.long * TICK if step % 2 else 0)
    return at


def _time_signature(ticks: int, fallback: tuple[int, int]) -> tuple[int, int]:
    for denom, unit in ((4, 24), (8, 12), (16, 6)):
        if ticks % unit == 0 and 1 <= ticks // unit <= 32:
            return ticks // unit, denom
    return fallback


# ============================================================
# 公開エントリポイント
# ============================================================

def realize_midi(genre: "Genre", score: "Score", plan: "SongPlan", target: "Target") -> bytes:
    if target.kind != "midi":
        raise PlanError(f"MidiRealizer cannot realize format {target.format!r}")
    info = _Info(genre)
    bpm = score.bpm

    notes: list[_Note] = []
    automations: list[tuple[int, str, Automation]] = []          # (tick, part, event)
    noteoffs: list[tuple[int, str, str]] = []                    # (tick, part, inst)
    conductor: list = [(0, CTRL, _meta(0x03, genre.title.encode("ascii"))),
                       (0, CTRL, _meta(0x51, (60_000_000 // bpm).to_bytes(3, "big")))]
    base = 0
    prev_sig = None
    section_starts: list[tuple[int, str, object]] = []
    for name in score.order:
        sec = score.sections[name]
        sp = sec.plan
        tm = _step_time(base, sp)
        tps = sp.meter.ticks_per_step * TICK
        sec_end = base + sp.steps * tps
        section_starts.append((base, name, tm))
        for m in sp.measures:
            sig = _time_signature(m.steps * sp.meter.ticks_per_step, sp.meter.signature)
            if sig != prev_sig:
                conductor.append((tm(m.start), CTRL, _meta(0x58, bytes([sig[0], sig[1].bit_length() - 1, 24, 8]))))
                prev_sig = sig
        for ev in sec.tempo:
            if isinstance(ev, TempoEvent):
                conductor.append((tm(ev.step), CTRL, _meta(0x51, (60_000_000 // ev.bpm).to_bytes(3, "big"))))
        for part_name, events in sec.parts.items():
            for e in events:
                if isinstance(e, NoteEvent):
                    notes.extend(_expand_event(info, part_name, e, tm, sec_end, bpm))
                elif isinstance(e, NoteOff):
                    noteoffs.append((tm(e.step), part_name, e.inst))
                elif isinstance(e, Automation):
                    automations.append((tm(e.step), part_name, e))
        base = sec_end
    end_tick = base

    _resolve_ends(info, notes, noteoffs, bpm, end_tick)
    voices_by_part = _build_voices(genre, notes)
    return _write(genre, score, info, conductor, voices_by_part, automations, section_starts, end_tick)


# ============================================================
# 1: NoteEvent → _Note
# ============================================================

def _expand_event(info: _Info, part: str, e: NoteEvent, tm, sec_end: int, bpm: int) -> list[_Note]:
    inst = info.genre.instruments[e.inst]
    gm = inst.gm
    vel = e.vel if e.vel is not None else info.default_volume(e.inst)
    delay = sum(a.ticks for a in e.arts if isinstance(a, Delay)) * TICK
    start0 = tm(e.step) + delay
    end = tm(e.step + e.dur) if e.dur is not None else None
    tones = e.chord if e.chord else (0,)
    ms_per_tick = 60000.0 / (bpm * PPQ)
    out = []
    for i, tone in enumerate(tones):
        if gm.is_drum:
            midi = float(gm.drum_note)
        elif not inst.is_pitched or e.pitch is None:
            midi = float(UNPITCHED_NOTE)
        else:
            midi = info.midi_pitch(e.inst, e.pitch + tone)
        start = start0 + (round(i * e.strum_ms / ms_per_tick) if e.strum_ms else 0)
        out.append(_Note(part, e.inst, start, None if end is None else max(end, start + 1), sec_end, midi, vel,
                         e.arts, tm, e.step, explicit_end=e.dur is not None))
    return out


# ============================================================
# 2: 終わりの決定（dur・次の発音・自然減衰・区間の終わり・NoteOff・Cut）
# ============================================================

def _resolve_ends(info: _Info, notes: list[_Note], noteoffs, bpm: int, end_tick: int) -> None:
    onsets: dict[tuple[str, str], list[int]] = {}
    for n in notes:
        onsets.setdefault((n.part, n.inst), []).append(n.start)
    for v in onsets.values():
        v.sort()
    import bisect

    for n in notes:
        if n.end is None:
            cands = [n.section_end]
            nat = info.natural_ticks(n.inst, n.midi, bpm) if not info.genre.instruments[n.inst].gm.is_drum else \
                info.natural_ticks(n.inst, None, bpm)
            if nat is not None:
                cands = [n.start + nat]       # ワンショットは自然減衰（区間をまたいでよい）
            lst = onsets[(n.part, n.inst)]
            k = bisect.bisect_right(lst, n.start)
            if k < len(lst):
                cands.append(lst[k])           # 同じ楽器の次の発音で切れる
            n.end = min(cands)
    for tick, part, inst in noteoffs:
        for n in notes:
            if n.part == part and n.inst == inst and n.start < tick < n.end:
                n.end = tick
    for n in notes:
        for a in n.arts:
            if isinstance(a, Cut):
                n.end = min(n.end, n.start + a.ticks * TICK)
        n.end = max(n.start + 1, min(n.end, end_tick))


# ============================================================
# 3: _Note → _Voice（アルペジオ・連打・ビブラート・グライド）
# ============================================================

def _build_voices(genre: "Genre", notes: list[_Note]) -> dict[str, list[_Voice]]:
    by_part: dict[str, list[_Voice]] = {}
    last: dict[str, _Voice] = {}                     # パートごとの直前の音（グライドの元）
    for n in sorted(notes, key=lambda n: (n.start, n.midi)):
        voices = _segments(n)
        glide = next((a for a in n.arts if isinstance(a, Glide)), None)
        prev = last.get(n.part)
        if glide is not None and prev is not None and prev.end > n.start and abs(prev.midi - n.midi) <= 12:
            steps = glide.steps if glide.steps is not None else 1
            first = voices[0]
            first.glide_from = prev.midi - first.midi
            first.glide_ticks = max(GLIDE_RAMP_TICKS, n.step_time(n.step + steps) - n.step_time(n.step))
        for a in n.arts:
            if isinstance(a, Vibrato):
                t0 = n.step_time(n.step + a.at)
                t1 = min(n.end, n.step_time(n.step + a.at + a.steps))
                if t0 < n.end:
                    voices[0].cc1 += [(t0, min(127, (a.param & 0x0F) * 8)), (t1, 0)]
        by_part.setdefault(n.part, []).extend(voices)
        last[n.part] = voices[-1]
    return by_part


def _segments(n: _Note) -> list[_Voice]:
    def v(start, end, midi):
        return _Voice(n.part, n.inst, start, end, midi, n.vel)

    arp = next((a for a in n.arts if isinstance(a, Arpeggio)), None)
    retrig = next((a for a in n.arts if isinstance(a, Retrig)), None)
    if arp is not None:
        span_end = min(n.end, n.step_time(n.step + arp.steps))
        out, t, k = [], n.start, 0
        while t < span_end:
            off = (0, arp.x, arp.y)[k % 3]
            out.append(v(t, min(t + TICK, span_end), n.midi + off))
            t += TICK
            k += 1
        if span_end < n.end:
            out.append(v(span_end, n.end, n.midi))        # 奏法の後は基の音が続く（トラッカーと同じ）
        return out
    if retrig is not None:
        step = retrig.ticks * TICK
        starts = list(range(n.start, n.end, step))
        return [v(s, min(s + step, n.end), n.midi) for s in starts]
    return [v(n.start, n.end, n.midi)]


# ============================================================
# 4: チャンネル割当と書き出し
# ============================================================

def _bend_semis(midi: float) -> float:
    return midi - round(midi)


def _polyphonic(voices: list[_Voice]) -> bool:
    ends = sorted((v.start, v.end) for v in voices)
    latest = -1
    for s, e in ends:
        if s < latest:
            return True
        latest = max(latest, e)
    return False


def _assign_channels(genre: "Genre", voices_by_part: dict[str, list[_Voice]]):
    """(part, セント) → MIDI チャンネル、パートごとのベンド範囲を返す。"""
    pool = list(MELODIC_CHANNELS)
    by_program: dict[int, int] = {}
    chan: dict[tuple[str, int], int] = {}
    ranges: dict[str, int] = {}
    parts = [p.name for p in genre.parts if p.name in voices_by_part]
    melodic_groups = 0
    plans = []
    for name in parts:
        all_vs = voices_by_part[name]
        is_drum = {i: genre.instruments[i].gm.is_drum for i in {v.inst for v in all_vs}}
        if any(is_drum.values()):
            chan[(name, DRUM_KEY)] = DRUM_CHANNEL     # 打楽器の音は ch10。同じパートの旋律の音（効果音など）は別のチャンネル
        vs = [v for v in all_vs if not is_drum[v.inst]]
        ranges[name] = BEND_RANGE_DEFAULT
        if not vs:
            continue
        glide = any(v.glide_from is not None for v in vs)
        ranges[name] = BEND_RANGE_GLIDE if glide else BEND_RANGE_DEFAULT
        cents = sorted({round(100 * _bend_semis(v.midi)) for v in vs})
        groups = cents if (len(cents) > 1 and not glide and _polyphonic(vs)) else [None]
        plans.append((name, vs, groups))
        melodic_groups += len(groups)
    share = melodic_groups > len(pool)
    for name, vs, groups in plans:
        program = genre.instruments[vs[0].inst].gm.program
        for g in groups:
            key = (name, 0 if g is None else g)
            if share and program in by_program and len(groups) == 1:
                chan[key] = by_program[program]
            elif pool:
                chan[key] = pool.pop(0)
                by_program.setdefault(program, chan[key])
            else:
                raise PlanError(f"{genre.id}: too many MIDI channels needed (15 melodic channels available)")
    return chan, ranges


def _write(genre, score, info: _Info, conductor, voices_by_part, automations, section_starts, end_tick: int) -> bytes:
    chan, ranges = _assign_channels(genre, voices_by_part)
    peak = max((v.vel for vs in voices_by_part.values() for v in vs), default=64) or 64
    lift = 64 / peak if peak < 64 else 1.0
    tracks: dict[str, list] = {}
    parts = {p.name: p for p in genre.parts}

    def velocity(native: int) -> int:
        return max(1, min(127, round(native * lift / 64 * 127)))

    part_channels: dict[str, list[int]] = {}
    for (name, _g), ch in chan.items():
        part_channels.setdefault(name, []).append(ch)

    for name, vs in voices_by_part.items():
        ev: list = []
        tracks[name] = ev
        ev.append((0, CTRL, _meta(0x03, name.encode("ascii", "replace"))))
        groups = sorted(g for (n, g) in chan if n == name)
        single = len([g for g in groups if g != DRUM_KEY]) <= 1
        state: dict[int, dict] = {}
        for g in groups:
            ch = chan[(name, g)]
            state[ch] = {"bend": BEND_CENTER, "inst": None, "exp": 127, "mod": 0}
            ev.append((0, CTRL, _cc(ch, 7, 127)))
            if ch != DRUM_CHANNEL:
                rng = ranges[name]
                for num, val in ((101, 0), (100, 0), (6, rng), (38, 0), (101, 127), (100, 127)):
                    ev.append((0, CTRL, _cc(ch, num, val)))
                ev.append((0, CTRL, bytes([0xE0 | ch, BEND_CENTER & 0x7F, BEND_CENTER >> 7])))
        # 同じチャンネル・同じ音高の重なりを避ける（止まらない音を作らない）
        placed: list[tuple[_Voice, int, int]] = []
        for v in sorted(vs, key=lambda v: (v.start, v.midi)):
            if genre.instruments[v.inst].gm.is_drum:
                ch = chan[(name, DRUM_KEY)]
                note = int(round(v.midi))
            else:
                g = round(100 * _bend_semis(v.midi)) if not single else 0
                ch = chan[(name, g)]
                note = max(0, min(127, round(v.midi)))
            placed.append((v, ch, note))
        nxt: dict[tuple[int, int], int] = {}
        ends: dict[int, int] = {}
        for i in range(len(placed) - 1, -1, -1):
            v, ch, note = placed[i]
            e = min(v.end, nxt.get((ch, note), v.end))
            ends[i] = max(v.start + 1, e)
            nxt[(ch, note)] = v.start
        for i, (v, ch, note) in enumerate(placed):
            st = state[ch]
            if ch != DRUM_CHANNEL:
                if st["inst"] != v.inst:
                    inst = genre.instruments[v.inst]
                    ev.append((v.start, CTRL, bytes([0xC0 | ch, inst.gm.program])))
                    pan = inst.pan if inst.pan is not None else parts[name].pan
                    ev.append((v.start, CTRL, _cc(ch, 10, round(pan * 127 / 255))))
                    st["inst"] = v.inst
                rng = ranges[name]
                semis = _bend_semis(v.midi) if v.glide_from is None else _bend_semis(v.midi) + v.glide_from
                if v.glide_from is not None:
                    note = max(0, min(127, round(v.midi)))
                    semis = v.glide_from + (v.midi - note)
                bend = max(0, min(16383, BEND_CENTER + round(semis * 8192 / rng)))
                if v.glide_from is not None or bend != st["bend"]:
                    ev.append((v.start, CTRL, bytes([0xE0 | ch, bend & 0x7F, bend >> 7])))
                    st["bend"] = bend
                if v.glide_from is not None:
                    final = max(0, min(16383, BEND_CENTER + round((v.midi - note) * 8192 / rng)))
                    k = max(1, v.glide_ticks // GLIDE_RAMP_TICKS)
                    for j in range(1, k + 1):
                        b = round(bend + (final - bend) * j / k)
                        ev.append((v.start + j * GLIDE_RAMP_TICKS, CTRL, bytes([0xE0 | ch, b & 0x7F, b >> 7])))
                    st["bend"] = final
            elif st["inst"] != v.inst:
                ev.append((v.start, CTRL, _cc(ch, 10, round(parts[name].pan * 127 / 255))))
                st["inst"] = v.inst
            for t, val in v.cc1:
                if ch != DRUM_CHANNEL and st["mod"] != val:
                    ev.append((t, CTRL, _cc(ch, 1, val)))
                    st["mod"] = val
            if st["exp"] != 127 and ch != DRUM_CHANNEL:
                ev.append((v.start, CTRL, _cc(ch, 11, 127)))
                st["exp"] = 127
            ev.append((v.start, ON, bytes([0x90 | ch, note, velocity(v.vel)])))
            ev.append((ends[i], OFF, bytes([0x80 | ch, note, 0])))

    _controllers(genre, tracks, part_channels, automations, voices_by_part,
                 score.sections[score.order[0]].plan.meter.ticks_per_step * TICK)
    for name in parts:
        if name in tracks and name not in voices_by_part:
            del tracks[name]
    order = [n for n in (p.name for p in genre.parts) if n in tracks]
    chunks = [_track(conductor, end_tick)] + [_track(tracks[n], end_tick) for n in order]
    return b"MThd" + struct.pack(">IHHH", 6, 1, len(chunks), PPQ) + b"".join(chunks)


def _controllers(genre, tracks, part_channels, automations, voices_by_part, step_ticks: int) -> None:
    """Automation（CC11・CC10・CC74）とサイドチェイン（対象パートの CC11）。"""
    for tick, part, a in automations:
        if part not in tracks or part not in part_channels:
            continue
        for ch in part_channels[part]:
            if ch == DRUM_CHANNEL and a.kind != "pan":
                continue
            if a.kind == "volume":
                ref = next((v.vel for v in sorted(voices_by_part[part], key=lambda v: -v.start) if v.start <= tick), 64)
                tracks[part].append((tick, CTRL, _cc(ch, 11, min(127, round(127 * a.value / max(1, ref))))))
            elif a.kind == "pan":
                tracks[part].append((tick, CTRL, _cc(ch, 10, round(a.value * 127 / 255))))
            elif a.kind == "cutoff":
                tracks[part].append((tick, CTRL, _cc(ch, 74, min(127, a.value))))
    # サイドチェイン: トリガの発音ごとに対象パートの CC11 を ratio だけ下げ、release_steps かけて戻す
    for rule in genre.mix:
        trig = sorted({v.start for vs in voices_by_part.values() for v in vs if v.inst in rule.triggers})
        for target in rule.targets:
            if target not in tracks or target not in part_channels:
                continue
            for t in trig:
                for k in range(rule.release_steps + 1):
                    frac = rule.ratio if k == 0 else rule.ratio * (1 - k / rule.release_steps)
                    for ch in part_channels[target]:
                        if ch != DRUM_CHANNEL:
                            tracks[target].append((t + k * step_ticks, CTRL, _cc(ch, 11, round(127 * (1 - frac)))))
