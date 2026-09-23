"""Song を tick 単位で再生解釈する（DESIGN.md §7.7）。

トラッカーの再生規則（ProTracker 準拠）で order を辿り、テンポ・Speed・パターンブレイク・ノートディレイ・
ノートカット・リトリガ・アルペジオを解決して、チャンネルごとのイベント列と曲長を返す純粋関数。
MIDI writer（core/midi.py）と曲長の検証で使う。トラッカー形式の writer は使わない（プレイヤーが解釈する）。

時間の単位は tracker tick（Speed 6 で 1 row＝6 tick、1 拍＝24 tick。1 tick＝2.5/BPM 秒）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .model import Song

DEFAULT_SPEED = 6
DEFAULT_BPM = 125
TICKS_PER_BEAT = 24


@dataclass(frozen=True)
class NoteOn:
    tick: int
    channel: int
    sample: int                  # 1 始まり
    note: int                    # tracker note t（アルペジオ中は切替後の音）
    volume: int                  # 0..64（発音時の音量）
    retrigger: bool = True       # False: 3xx による目標音への切替（MIDI では即時切替として扱う）


@dataclass(frozen=True)
class VolumeChange:
    tick: int
    channel: int
    volume: int


@dataclass(frozen=True)
class NoteCut:
    tick: int
    channel: int


@dataclass(frozen=True)
class Vibrato:
    tick: int
    channel: int
    depth: int                   # 0..15（0 で終了）


@dataclass(frozen=True)
class TempoChange:
    tick: int
    bpm: int


@dataclass(frozen=True)
class RowStart:
    tick: int
    order_index: int
    pattern: int
    row: int


@dataclass
class Timeline:
    events: list = field(default_factory=list)          # 上記イベントを tick 順に
    tempos: list[TempoChange] = field(default_factory=list)
    rows: list[RowStart] = field(default_factory=list)
    end_tick: int = 0

    def seconds_at(self, tick: int) -> float:
        """tick → 曲頭からの秒数（テンポ変化を積分）。"""
        sec, prev_tick, bpm = 0.0, 0, DEFAULT_BPM
        for t in self.tempos:
            if t.tick >= tick:
                break
            sec += (t.tick - prev_tick) * 2.5 / bpm
            prev_tick, bpm = t.tick, t.bpm
        return sec + (tick - prev_tick) * 2.5 / bpm

    def tick_at(self, seconds: float) -> int:
        """秒数 → tick（``seconds_at`` の逆関数。切り上げ）。"""
        sec, prev_tick, bpm = 0.0, 0, DEFAULT_BPM
        for t in self.tempos:
            seg = (t.tick - prev_tick) * 2.5 / bpm
            if sec + seg >= seconds:
                break
            sec += seg
            prev_tick, bpm = t.tick, t.bpm
        return prev_tick + max(0, -int(-(seconds - sec) * bpm // 2.5))

    @property
    def seconds(self) -> float:
        return self.seconds_at(self.end_tick)


def build(song: Song, initial_bpm: int = DEFAULT_BPM) -> Timeline:
    tl = Timeline()
    tl.tempos.append(TempoChange(0, initial_bpm))
    speed, bpm = DEFAULT_SPEED, initial_bpm
    tick = 0
    n_channels = song.patterns[0].channels if song.patterns else 0
    playing_note: list[Optional[int]] = [None] * n_channels     # 3xx の「現在の音」、アルペジオの基音
    vibrato_on = [False] * n_channels
    order_index = 0
    start_row = 0
    visited: set[tuple[int, int]] = set()

    while order_index < len(song.order):
        pattern_no = song.order[order_index]
        pat = song.patterns[pattern_no]
        next_order, next_row = order_index + 1, 0
        row = start_row
        while row < pat.rows:
            if (order_index, row) in visited:          # 後方ジャンプのループは1周で打ち切る
                next_order = len(song.order)
                break
            visited.add((order_index, row))
            cells = [pat.get(row, c) for c in range(n_channels)]
            pattern_delay = 0
            jump = None
            # 1) 行頭でテンポ・Speed・フロー制御を確定させる（トラッカーは tick 0 で全エフェクトを処理する）
            for cell in cells:
                if cell.effect == 0xF and cell.param:
                    if cell.param < 0x20:
                        speed = cell.param
                    elif cell.param != bpm:
                        bpm = cell.param
                        tl.tempos.append(TempoChange(tick, bpm))
                elif cell.effect == 0xD:
                    jump = (order_index + 1, (cell.param >> 4) * 10 + (cell.param & 0x0F))
                elif cell.effect == 0xB:
                    jump = (cell.param, 0)
                elif cell.effect == 0xE and cell.param >> 4 == 0xE:
                    pattern_delay = cell.param & 0x0F
            tl.rows.append(RowStart(tick, order_index, pattern_no, row))
            row_ticks = speed * (1 + pattern_delay)
            # 2) チャンネルごとの発音イベント
            for ch, cell in enumerate(cells):
                _channel_events(tl, song, ch, cell, tick, speed, row_ticks, playing_note, vibrato_on)
            tick += row_ticks
            if jump is not None:
                next_order, next_row = jump
                break
            row += 1
        order_index, start_row = next_order, next_row

    tl.end_tick = tick
    tl.events.sort(key=lambda e: e.tick)
    return tl


def _channel_events(tl, song, ch, cell, tick, speed, row_ticks, playing_note, vibrato_on) -> None:
    effect, param = cell.effect, cell.param
    sub = param >> 4 if effect == 0xE else None
    delay = param & 0x0F if sub == 0xD else 0
    if delay >= speed:                               # ディレイが行長以上なら発音しない（PT/FT2 と同じ）
        return
    start = tick + delay
    sample = cell.sample
    if cell.note is not None and sample:
        vol = cell.vol if cell.vol is not None else song.samples[sample - 1].volume
        is_porta = effect == 0x3 and playing_note[ch] is not None
        tl.events.append(NoteOn(start, ch, sample, cell.note, vol, retrigger=not is_porta))
        playing_note[ch] = cell.note
        if sub == 0x9 and param & 0x0F:              # E9x: x tick ごとに再発音
            step = param & 0x0F
            for t in range(step, speed, step):
                tl.events.append(NoteOn(start + t, ch, sample, cell.note, vol))
        if effect == 0x0 and param:                  # 0xy: tick ごとに 基音/+x/+y を巡回
            offsets = (0, param >> 4, param & 0x0F)
            for t in range(1, row_ticks):
                off = offsets[t % 3]
                prev = offsets[(t - 1) % 3]
                if off != prev:
                    tl.events.append(NoteOn(start + t, ch, sample, cell.note + off, vol, retrigger=False))
            if offsets[(row_ticks - 1) % 3] != 0:      # 次の row の頭で基音に戻る
                tl.events.append(NoteOn(tick + row_ticks, ch, sample, cell.note, vol, retrigger=False))
    elif sample and cell.note is None:               # サンプル番号のみ: 音量をサンプル既定値に戻す
        tl.events.append(VolumeChange(start, ch, cell.vol if cell.vol is not None else song.samples[sample - 1].volume))
    elif cell.vol is not None:
        if cell.vol == 0:
            tl.events.append(NoteCut(start, ch))
            playing_note[ch] = None
        else:
            tl.events.append(VolumeChange(start, ch, cell.vol))
    if sub == 0xC:                                   # ECx: x tick 目で消音
        cut = param & 0x0F
        if cut < speed:
            tl.events.append(NoteCut(tick + cut, ch))
    if effect == 0x4:
        vibrato_on[ch] = True
        tl.events.append(Vibrato(tick, ch, param & 0x0F))
    elif vibrato_on[ch]:
        vibrato_on[ch] = False
        tl.events.append(Vibrato(tick, ch, 0))
