from mod_weaver.core import timeline
from mod_weaver.core.model import Cell, Pattern, SampleSpec, Song


def song(cells, rows=64):
    pat = Pattern(None, rows=rows, channels=2)
    for r, c, cell in cells:
        pat.put(r, c, cell)
    return Song("T", [SampleSpec("S", bytes(64), 40)], [pat], [0])


def test_length_and_tempo_integration():
    tl = timeline.build(song([(0, 0, Cell(None, 0, 0xF, 120)), (32, 0, Cell(None, 0, 0xF, 60))]), 125)
    assert tl.end_tick == 64 * 6
    assert abs(tl.seconds - (32 * 6 * 2.5 / 120 + 32 * 6 * 2.5 / 60)) < 1e-9
    assert tl.tick_at(tl.seconds_at(200)) == 200


def test_speed_change_and_pattern_break():
    tl = timeline.build(song([(0, 0, Cell(None, 0, 0xF, 3)), (9, 1, Cell(None, 0, 0xD, 0))]))
    assert tl.end_tick == 10 * 3


def test_delay_retrigger_cut_and_volume_events():
    tl = timeline.build(song([
        (0, 0, Cell(12, 1, 0xE, 0xD2)),        # 2 tick 遅れて発音
        (1, 0, Cell(12, 1, 0xE, 0x92)),        # 2 tick ごとに再発音（0,2,4）
        (2, 0, Cell(None, 0, vol=20)),
        (3, 0, Cell(None, 0, vol=0)),
        (4, 1, Cell(5, 1, 0xE, 0xC3)),         # 3 tick 目で消音
    ]))
    ons = [(e.tick, e.channel) for e in tl.events if isinstance(e, timeline.NoteOn)]
    assert ons == [(2, 0), (6, 0), (8, 0), (10, 0), (24, 1)]
    assert [e.tick for e in tl.events if isinstance(e, timeline.VolumeChange)] == [12]
    assert [(e.tick, e.channel) for e in tl.events if isinstance(e, timeline.NoteCut)] == [(18, 0), (27, 1)]


def test_arpeggio_and_portamento():
    tl = timeline.build(song([(0, 0, Cell(12, 1, 0x0, 0x47)), (1, 0, Cell(14, 1, 0x3, 0x10))]))
    notes = [(e.tick, e.note, e.retrigger) for e in tl.events if isinstance(e, timeline.NoteOn)]
    assert notes[:4] == [(0, 12, True), (1, 16, False), (2, 19, False), (3, 12, False)]
    assert notes[-1] == (6, 14, False)                  # 3xx は目標音への切替（再発音しない）
