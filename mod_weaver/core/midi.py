"""General MIDI の Standard MIDI File（SMF format 1）シリアライザと構造検査（DESIGN.md §7.7）。

目的は「ジャンルの意図（音高・リズム・構成・テンポ）を GM 音源で聴ける／DAW に持ち込めること」であり、
サンプル音色の再現は目的外（音色は GM 音源次第）。

- 時間: PPQ=96、tracker 1 tick = MIDI 4 tick、4 分音符 = 24 tracker tick。tempo meta = 60,000,000 / BPM。
  Speed 変化（swing）やノートディレイは tick 数そのものに反映されるので厳密に再現される。
- チャンネル: **楽器単位**で MIDI チャンネルを割り当てる（トラッカーの 1 チャンネルが複数楽器を鳴らすため）。
  ドラム（``GmVoice.drum_note``）は ch10 に集約、旋律楽器は ch1-9, 11-16 を sample 番号順に。
- 音色: プロファイルの ``gm_voices``（楽器名 → ``GmVoice``）による明示宣言のみ。推測はしない。
- 音高: **実際に鳴る高さ**（``SampleSpec.sounding_hz`` と period 比）から求める。論理 note の
  ``pitch.hz(n)`` は合成の基準レートの都合で実音と 1〜2 オクターブずれている音色があるため使わない。
  半音未満のずれ（音色固有の数セント＋finetune。maqam の微分音を含む）は楽器チャンネルの固定ピッチベンド
  （±2 半音レンジ）。
- 近似: 3xx/1xx/2xx はグライドせず目標音へ即時切替、4xy は CC1、発音中の音量変化は CC11
  （その楽器を同時に鳴らしているトラッカーチャンネルが 1 つのときだけ）、9xx は無視。
"""
from __future__ import annotations

import math
import struct
from dataclasses import dataclass
from typing import Optional

from ..errors import PlanError
from . import timeline as tl_mod
from .dsp import CLOCK
from .model import Song
from .pitch import PERIODS

PPQ = 96
TICK_SCALE = PPQ // tl_mod.TICKS_PER_BEAT        # 4
DRUM_CHANNEL = 9
MELODIC_CHANNELS = tuple(c for c in range(16) if c != DRUM_CHANNEL)
MAX_CHANNELS = 64                                 # トラッカー側のチャンネル数上限（MIDI 側は楽器単位で割当）
BEND_CENTER = 8192
BEND_PER_SEMITONE = 4096                          # ±2 半音レンジ
UNPITCHED_NOTE = 60                               # 音高を持たない非ドラム音色（効果音等）の発音 note


@dataclass(frozen=True)
class GmVoice:
    """楽器 1 つの GM 音色。``program``（0..127、旋律楽器）か ``drum_note``（35..81、ch10）のどちらか一方。"""
    program: Optional[int] = None
    drum_note: Optional[int] = None

    def __post_init__(self) -> None:
        if (self.program is None) == (self.drum_note is None):
            raise ValueError("GmVoice needs exactly one of program / drum_note")
        if self.program is not None and not 0 <= self.program <= 127:
            raise ValueError(f"GM program out of range: {self.program}")
        if self.drum_note is not None and not 27 <= self.drum_note <= 87:
            raise ValueError(f"GM drum note out of range: {self.drum_note}")

    @property
    def is_drum(self) -> bool:
        return self.drum_note is not None


# ------------------------------------------------------------
# SMF の低レベル部品
# ------------------------------------------------------------

def _vlq(n: int) -> bytes:
    out = [n & 0x7F]
    n >>= 7
    while n:
        out.append(0x80 | (n & 0x7F))
        n >>= 7
    return bytes(reversed(out))


def _meta(kind: int, data: bytes) -> bytes:
    return bytes([0xFF, kind]) + _vlq(len(data)) + data


def _track(events: list[tuple[int, int, bytes]], end_tick: int = 0) -> bytes:
    """events: (midi_tick, 同 tick 内の順序, メッセージ)。note off → 制御 → note on の順に並べる。
    End of Track は ``end_tick``（最後のイベントより前なら最後のイベント）に置く。"""
    body = bytearray()
    now = 0
    for tick, _prio, msg in sorted(events, key=lambda e: (e[0], e[1])):
        body += _vlq(tick - now) + msg
        now = tick
    body += _vlq(max(0, end_tick - now)) + _meta(0x2F, b"")
    return b"MTrk" + struct.pack(">I", len(body)) + bytes(body)


OFF, CTRL, ON = 0, 1, 2


def _cc(ch: int, num: int, val: int) -> bytes:
    return bytes([0xB0 | ch, num, max(0, min(127, val))])


# ------------------------------------------------------------
# 変換
# ------------------------------------------------------------

@dataclass
class _Active:
    midi_ch: int
    midi_note: int
    sample: int
    volume: int
    natural_end: Optional[int]       # tracker tick。ループサンプルは None（止められるまで鳴る）


def _voices(song: Song, opts) -> list[GmVoice]:
    names = song.instrument_names or tuple(s.name for s in song.samples)
    missing = [n for n in names if n not in opts.gm_voices]
    if missing:
        raise PlanError(f"no GM voice declared for instrument(s): {', '.join(missing)} "
                        f"(add them to the genre's gm_voices)")
    return [opts.gm_voices[n] for n in names]


def _assign_channels(voices: list[GmVoice]) -> list[int]:
    """sample 番号順に MIDI チャンネルを割り当てる。15 を超えたら同じ program の楽器を相乗りさせる。"""
    chans: list[int] = []
    by_program: dict[int, int] = {}
    free = list(MELODIC_CHANNELS)
    melodic = [v for v in voices if not v.is_drum]
    share = len(melodic) > len(MELODIC_CHANNELS)
    for v in voices:
        if v.is_drum:
            chans.append(DRUM_CHANNEL)
        elif share and v.program in by_program:
            chans.append(by_program[v.program])
        elif free:
            ch = free.pop(0)
            by_program.setdefault(v.program, ch)
            chans.append(ch)
        else:
            raise PlanError(f"too many distinct melodic GM programs for 15 MIDI channels: {len(melodic)}")
    return chans


def _natural_length(song: Song, sample: int, t: int) -> Optional[float]:
    """ワンショットサンプルが鳴り終わるまでの秒数（ループサンプルは None）。再生レート＝Paula クロック/period。"""
    spec = song.samples[sample - 1]
    if spec.loop is not None:
        return None
    t = t if spec.pitched else spec.rate_note
    return len(spec.data) / (CLOCK / PERIODS[max(0, min(len(PERIODS) - 1, t))])


def _midi_pitch(spec, t: int) -> float:
    """tracker note t で鳴らしたときの実音の MIDI ノート番号（小数。finetune は含まない）。"""
    if spec.sounding_hz is None:                  # synth.render() 以外で作った音色（現状なし）の近似
        return 48.0 + t + spec.shift
    f = spec.sounding_hz * PERIODS[spec.rate_note] / PERIODS[t]
    return 69.0 + 12.0 * math.log2(f / 440.0)


def _pitch_offset(spec) -> float:
    """音色固有の半音未満のずれ（-0.5..0.5 半音）。楽器チャンネルの固定ベンドにする。"""
    p = _midi_pitch(spec, spec.rate_note)
    return p - round(p)


def _time_signature(ticks: int) -> Optional[tuple[int, int]]:
    for denom, unit in ((4, 24), (8, 12), (16, 6)):
        if ticks % unit == 0 and 1 <= ticks // unit <= 32:
            return ticks // unit, denom
    return None


def serialize_midi(song: Song, opts) -> bytes:
    """Song を SMF（format 1）のバイト列へ変換する。``opts`` は ``formats.WriteOptions``。"""
    voices = _voices(song, opts)
    chans = _assign_channels(voices)
    tl = tl_mod.build(song, opts.initial_bpm)
    tracks: dict[int, list] = {ch: [] for ch in sorted(set(chans))}
    conductor: list = [(0, CTRL, _meta(0x03, song.title.encode("ascii")))]

    # ---- テンポと拍子 ----
    for t in tl.tempos:
        conductor.append((t.tick * TICK_SCALE, CTRL, _meta(0x51, (60_000_000 // t.bpm).to_bytes(3, "big"))))
    measure_starts = _measure_start_ticks(tl, opts)
    prev_sig = None
    for i, start in enumerate(measure_starts):
        end = measure_starts[i + 1] if i + 1 < len(measure_starts) else tl.end_tick
        sig = _time_signature(end - start)
        if sig and sig != prev_sig:
            num, den = sig
            conductor.append((start * TICK_SCALE, CTRL, _meta(0x58, bytes([num, den.bit_length() - 1, 24, 8]))))
            prev_sig = sig

    # ---- 楽器チャンネルの初期設定（音色・ベンドレンジ・finetune・パン） ----
    first_channel: dict[int, int] = {}
    for ev in tl.events:
        if isinstance(ev, tl_mod.NoteOn):
            first_channel.setdefault(ev.sample, ev.channel)
    setup_done: set[int] = set()
    for idx, (voice, ch) in enumerate(zip(voices, chans), start=1):
        if ch in setup_done:
            continue
        setup_done.add(ch)
        spec = song.samples[idx - 1]
        name = (song.instrument_names[idx - 1] if song.instrument_names else spec.name).encode("ascii")
        ev = tracks[ch]
        ev.append((0, CTRL, _meta(0x03, b"Drums" if voice.is_drum else name)))
        if voice.is_drum:
            ev.append((0, CTRL, _cc(ch, 10, 64)))
            continue
        ev.append((0, CTRL, bytes([0xC0 | ch, voice.program])))
        for num, val in ((101, 0), (100, 0), (6, 2), (38, 0), (101, 127), (100, 127)):   # ベンドレンジ ±2 半音
            ev.append((0, CTRL, _cc(ch, num, val)))
        semis = (_pitch_offset(spec) if spec.pitched else 0.0) + spec.finetune / 8
        bend = max(0, min(16383, BEND_CENTER + round(semis * BEND_PER_SEMITONE)))
        ev.append((0, CTRL, bytes([0xE0 | ch, bend & 0x7F, bend >> 7])))
        pan = spec.pan if spec.pan != 128 else opts.channel_pans[first_channel.get(idx, 0)]
        ev.append((0, CTRL, _cc(ch, 10, round(pan * 127 / 255))))

    # ---- ノート ----
    active: dict[int, _Active] = {}
    expression: dict[int, int] = {}                  # MIDI ch → 現在の CC11
    modwheel: dict[int, int] = {}

    def end_note(tch: int, tick: int) -> None:
        a = active.pop(tch, None)
        if a is not None:
            stop = tick if a.natural_end is None else min(tick, a.natural_end)
            tracks[a.midi_ch].append((stop * TICK_SCALE, OFF, bytes([0x80 | a.midi_ch, a.midi_note, 0])))

    def expire(tick: int) -> None:
        for tch in [c for c, a in active.items() if a.natural_end is not None and a.natural_end <= tick]:
            end_note(tch, tick)

    for ev in tl.events:
        expire(ev.tick)
        tch = ev.channel
        if isinstance(ev, tl_mod.NoteOn):
            prev = active.get(tch)
            end_note(tch, ev.tick)
            voice, mch = voices[ev.sample - 1], chans[ev.sample - 1]
            spec = song.samples[ev.sample - 1]
            if voice.is_drum:
                note = voice.drum_note
            elif not spec.pitched:
                note = UNPITCHED_NOTE
            else:
                note = round(_midi_pitch(spec, ev.note) - _pitch_offset(spec))
            note = max(0, min(127, note))
            if ev.retrigger or prev is None or prev.sample != ev.sample:
                length = _natural_length(song, ev.sample, ev.note)
                natural_end = None if length is None else tl.tick_at(tl.seconds_at(ev.tick) + length)
            else:                                     # 3xx・アルペジオ: 同じ発音の続き（減衰の終わりは変わらない）
                natural_end = prev.natural_end
            if natural_end is not None and natural_end <= ev.tick:
                continue
            if expression.get(mch, 127) != 127 and not voice.is_drum:
                tracks[mch].append((ev.tick * TICK_SCALE, CTRL, _cc(mch, 11, 127)))
                expression[mch] = 127
            velocity = max(1, round(ev.volume * 127 / 64))
            tracks[mch].append((ev.tick * TICK_SCALE, ON, bytes([0x90 | mch, note, velocity])))
            active[tch] = _Active(mch, note, ev.sample, max(1, ev.volume), natural_end)
        elif isinstance(ev, tl_mod.NoteCut):
            end_note(tch, ev.tick)
        elif isinstance(ev, tl_mod.VolumeChange):
            a = active.get(tch)
            if a is None or a.midi_ch == DRUM_CHANNEL:
                continue
            sharing = any(o.midi_ch == a.midi_ch for c, o in active.items() if c != tch)
            if not sharing:
                val = min(127, round(127 * ev.volume / a.volume))
                if expression.get(a.midi_ch, 127) != val:
                    tracks[a.midi_ch].append((ev.tick * TICK_SCALE, CTRL, _cc(a.midi_ch, 11, val)))
                    expression[a.midi_ch] = val
        elif isinstance(ev, tl_mod.Vibrato):
            a = active.get(tch)
            if a is None or a.midi_ch == DRUM_CHANNEL:
                continue
            val = ev.depth * 8
            if modwheel.get(a.midi_ch, 0) != val:
                tracks[a.midi_ch].append((ev.tick * TICK_SCALE, CTRL, _cc(a.midi_ch, 1, val)))
                modwheel[a.midi_ch] = val
    for tch in list(active):
        end_note(tch, tl.end_tick)

    end = tl.end_tick * TICK_SCALE
    chunks = [_track(conductor, end)] + [_track(tracks[ch], end) for ch in sorted(tracks)]
    header = b"MThd" + struct.pack(">IHHH", 6, 1, len(chunks), PPQ)
    return header + b"".join(chunks)


def _measure_start_ticks(tl: tl_mod.Timeline, opts) -> list[int]:
    """再生順の各小節の開始 tick（``WriteOptions.measure_rows`` による。無ければ rows_per_measure 固定）。"""
    starts = []
    for rs in tl.rows:
        lengths = opts.measure_rows[rs.pattern] if rs.pattern < len(opts.measure_rows) else ()
        if lengths:
            boundaries, acc = set(), 0
            for n in lengths:
                boundaries.add(acc)
                acc += n
            is_start = rs.row in boundaries
        else:
            is_start = rs.row % max(1, opts.rows_per_measure) == 0
        if is_start:
            starts.append(rs.tick)
    return starts


# ============================================================
# 構造検査（writer とは独立に SMF を読む）
# ============================================================

@dataclass
class ParsedMidi:
    format: int
    ppq: int
    tracks: list[list[tuple[int, bytes]]]           # 各トラックの (絶対 tick, メッセージ)


class MidiParseError(PlanError):
    pass


def parse_midi(data: bytes) -> ParsedMidi:
    if data[:4] != b"MThd" or len(data) < 14:
        raise MidiParseError("missing MThd")
    hlen, fmt, ntrks, ppq = struct.unpack(">IHHH", data[4:14])
    pos = 8 + hlen
    tracks = []
    for _ in range(ntrks):
        if data[pos:pos + 4] != b"MTrk":
            raise MidiParseError(f"missing MTrk at {pos}")
        (length,) = struct.unpack(">I", data[pos + 4:pos + 8])
        body = data[pos + 8:pos + 8 + length]
        if len(body) != length:
            raise MidiParseError("track truncated")
        pos += 8 + length
        events, p, now, status = [], 0, 0, 0
        while p < len(body):
            delta = 0
            while True:
                b = body[p]
                p += 1
                delta = (delta << 7) | (b & 0x7F)
                if not b & 0x80:
                    break
            now += delta
            if body[p] == 0xFF:
                n, q = 0, p + 2
                while True:
                    b = body[q]
                    q += 1
                    n = (n << 7) | (b & 0x7F)
                    if not b & 0x80:
                        break
                events.append((now, body[p:q + n]))
                p = q + n
                continue
            if body[p] & 0x80:
                status = body[p]
                p += 1
            size = 1 if status & 0xF0 in (0xC0, 0xD0) else 2
            events.append((now, bytes([status]) + body[p:p + size]))
            p += size
        tracks.append(events)
    if pos != len(data):
        raise MidiParseError(f"trailing bytes: {len(data) - pos}")
    return ParsedMidi(fmt, ppq, tracks)


_DESCRIPTIONS = {
    "V01": "SMF として読めない",
    "V02": "ヘッダが不正（format 1／PPQ）",
    "V03": "トラックが End of Track で終わっていない",
    "V04": "note on に対応する note off がない",
    "V05": "テンポ設定がない",
}


def verify_midi(data: bytes, plan=None) -> list:
    from .verify import Issue, _Report

    try:
        pm = parse_midi(data)
    except (MidiParseError, IndexError, struct.error) as e:
        return [Issue("ERROR", "V01", str(e))]
    rep = _Report()
    if pm.format != 1 or pm.ppq != PPQ:
        rep.add("ERROR", "V02", f"format={pm.format} ppq={pm.ppq}")
    for i, tr in enumerate(pm.tracks):
        if not tr or tr[-1][1][:2] != b"\xFF\x2F":
            rep.add("ERROR", "V03", f"track {i}")
        on: dict[tuple[int, int], int] = {}
        for _t, msg in tr:
            kind = msg[0] & 0xF0
            if kind == 0x90 and msg[2]:
                on[(msg[0] & 0x0F, msg[1])] = on.get((msg[0] & 0x0F, msg[1]), 0) + 1
            elif kind == 0x80 or (kind == 0x90 and not msg[2]):
                key = (msg[0] & 0x0F, msg[1])
                on[key] = on.get(key, 0) - 1
        for (ch, note), n in on.items():
            if n > 0:
                rep.add("ERROR", "V04", f"track {i} ch{ch + 1} note {note}")
    has_tempo = bool(pm.tracks) and any(msg[:2] == b"\xFF\x51" for _t, msg in pm.tracks[0])
    if not has_tempo:
        rep.add("ERROR", "V05", "conductor track")
    return rep.issues(_DESCRIPTIONS)
