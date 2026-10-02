"""新しい MidiRealizer（PPQ 480。``framework/realize/midi.py``）の出力の構造検査（FRAMEWORK_REDESIGN.md §11.3）。

読み戻しは ``core.midi.parse_midi``（PPQ に依存しない）。旧 ``midi.verify_midi``（PPQ 96）の検査に、同時発音数
（GM1 が保証する 24 を超えたら WARN）・ドラムの音域・メロディのチャンネルの program 指定を加えた。
"""
from __future__ import annotations

import struct

from .midi import MidiParseError, parse_midi
from .verify import Issue, _Report

PPQ = 480
GM1_POLYPHONY = 24

_DESCRIPTIONS = {
    "V01": "SMF として読めない",
    "V02": "ヘッダが不正（format 1／PPQ 480）",
    "V03": "トラックが End of Track で終わっていない",
    "V04": "note on と note off の対応が合わない",
    "V05": "テンポ設定がない",
    "V06": "ノート番号・velocity が範囲外",
    "V07": "メロディのチャンネルで program 指定の前に発音している",
    "V08": "ドラム（ch10）の音が GM の打楽器の範囲（27..87）外",
    "V09": "同時発音数が GM1 の保証する 24 を超える",
}


def verify(data: bytes) -> list[Issue]:
    try:
        pm = parse_midi(data)
    except (MidiParseError, IndexError, struct.error) as e:
        return [Issue("ERROR", "V01", str(e))]
    rep = _Report()
    if pm.format != 1 or pm.ppq != PPQ:
        rep.add("ERROR", "V02", f"format={pm.format} ppq={pm.ppq}")
    timeline: list[tuple[int, int]] = []
    for i, tr in enumerate(pm.tracks):
        if not tr or tr[-1][1][:2] != b"\xFF\x2F":
            rep.add("ERROR", "V03", f"track {i}")
        on: dict[tuple[int, int], int] = {}
        programmed: set[int] = set()
        for tick, msg in tr:
            kind, ch = msg[0] & 0xF0, msg[0] & 0x0F
            if kind == 0xC0:
                programmed.add(ch)
            elif kind == 0x90 and msg[2]:
                if msg[1] > 127 or msg[2] > 127:
                    rep.add("ERROR", "V06", f"track {i}")
                if ch != 9 and ch not in programmed:
                    rep.add("ERROR", "V07", f"track {i} ch{ch + 1}")
                if ch == 9 and not 27 <= msg[1] <= 87:
                    rep.add("ERROR", "V08", f"track {i} note {msg[1]}")
                on[(ch, msg[1])] = on.get((ch, msg[1]), 0) + 1
                timeline.append((tick, 1))
            elif kind == 0x80 or (kind == 0x90 and not msg[2]):
                on[(ch, msg[1])] = on.get((ch, msg[1]), 0) - 1
                timeline.append((tick, -1))
        if any(n != 0 for n in on.values()):
            rep.add("ERROR", "V04", f"track {i}")
    if not (pm.tracks and any(msg[:2] == b"\xFF\x51" for _t, msg in pm.tracks[0])):
        rep.add("ERROR", "V05", "conductor track")
    active = peak = 0
    for _tick, d in sorted(timeline, key=lambda e: (e[0], e[1])):      # 同じ tick は off が先
        active += d
        peak = max(peak, active)
    if peak > GM1_POLYPHONY:
        rep.add("WARN", "V09", f"peak {peak}")
    return rep.issues(_DESCRIPTIONS)
