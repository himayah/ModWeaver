from __future__ import annotations

import pytest

from mod_weaver.core.harmony import Registers, chord_label, voice
from mod_weaver.core.model import ChordSpec
from mod_weaver.core.pitch import CHORD_QUALITIES, MODES, Scale
from mod_weaver.errors import PitchRangeError

REGS = Registers(bass=(0, 11), harmony=(17, 28), melody=(24, 41))
PHRYGIAN = Scale(0, MODES["phrygian"])


def test_design_examples_are_regression_values():
    """DESIGN.md §4.2 の例（主音 C、HARMONY_REG=(17,28)、BASS_REG=(0,11)）。"""
    cdim = voice(ChordSpec(0, "dim"), 0, PHRYGIAN, REGS, arp=True)
    assert (cdim.bass, cdim.harmony, cdim.arp) == (0, 24, 0x36)
    assert {n % 12 for n in cdim.chord_tones} == {0, 3, 6}
    db_c = voice(ChordSpec(1, "maj", 0), 0, PHRYGIAN, REGS, arp=True)
    assert (db_c.bass, db_c.harmony, db_c.arp) == (0, 25, 0x47)
    assert {n % 12 for n in db_c.chord_tones} == {1, 5, 8}
    b_c = voice(ChordSpec(11, "maj", 0), 0, PHRYGIAN, REGS, arp=True)
    assert (b_c.bass, b_c.harmony, b_c.arp) == (0, 23, 0x47)
    assert {n % 12 for n in b_c.chord_tones} == {11, 3, 6}


@pytest.mark.parametrize("tonic", range(12))
@pytest.mark.parametrize("quality", sorted(CHORD_QUALITIES))
def test_all_tonics_and_qualities(tonic, quality):
    for root in (0, 5, 7, 11):
        spec = ChordSpec(root, quality)
        cd = voice(spec, tonic, Scale(tonic, MODES["ionian"]), REGS)
        root_pc = (tonic + root) % 12
        pcs = {(root_pc + i) % 12 for i in CHORD_QUALITIES[quality]}
        assert REGS.bass[0] <= cd.bass <= REGS.bass[1] and cd.bass % 12 == root_pc
        assert REGS.harmony[0] <= cd.harmony <= REGS.harmony[1] and cd.harmony % 12 == root_pc
        assert cd.harmony - 12 < REGS.harmony[0] and cd.bass - 12 < REGS.bass[0]     # 最低音
        assert cd.chord_tones == tuple(sorted(cd.chord_tones))
        assert all(REGS.melody[0] <= n <= REGS.melody[1] and n % 12 in pcs for n in cd.chord_tones)
        assert {n % 12 for n in cd.chord_tones} == pcs
        assert set(cd.chord_tones) <= set(cd.scale_tones) and cd.scale_tones == tuple(sorted(cd.scale_tones))
        assert cd.arp is None and cd.explicit is False


def test_arp_values_per_quality():
    q = lambda name: voice(ChordSpec(0, name), 0, PHRYGIAN, REGS, arp=True).arp
    assert q("dim") == 0x36 and q("min") == 0x37 and q("maj") == 0x47
    assert q("maj7") == 0x47 and q("dom7") == 0x47 and q("m7") == 0x37          # 7th は三和音分のみ


def test_bass_differs_from_root_for_slash_chords():
    cd = voice(ChordSpec(7, "maj", 0), 0, PHRYGIAN, REGS)      # G/C
    assert cd.bass % 12 == 0 and cd.harmony % 12 == 7


def test_mode_by_quality_switches_scale():
    plain = voice(ChordSpec(0, "dim"), 0, PHRYGIAN, REGS)
    wh = voice(ChordSpec(0, "dim"), 0, PHRYGIAN, REGS, mode_by_quality={"dim": "dim_wh"})
    assert {n % 12 for n in wh.scale_tones} == {0, 2, 3, 5, 6, 8, 9, 11}
    assert {n % 12 for n in plain.scale_tones} == {0, 1, 3, 5, 7, 8, 10, 6}    # phrygian + dim の #4 (6)
    other = voice(ChordSpec(0, "min"), 0, PHRYGIAN, REGS, mode_by_quality={"dim": "dim_wh"})
    assert {n % 12 for n in other.scale_tones} <= {0, 1, 3, 5, 7, 8, 10}       # 他 quality は影響を受けない


def test_labels():
    assert voice(ChordSpec(0, "dim"), 0, PHRYGIAN, REGS).label == "Cdim"
    assert voice(ChordSpec(1, "maj", 0), 0, PHRYGIAN, REGS).label == "Db/C"
    assert voice(ChordSpec(0, "m7"), 2, PHRYGIAN, REGS).label == "Dm7"
    assert voice(ChordSpec(0, "maj", label="Home"), 0, PHRYGIAN, REGS).label == "Home"
    assert chord_label(ChordSpec(5, "dom7", 5), 0) == "F7"


def test_registers_and_quality_validation():
    with pytest.raises(PitchRangeError):
        Registers(bass=(0, 10), harmony=(17, 28), melody=(24, 41))
    with pytest.raises(PitchRangeError):
        voice(ChordSpec(0, "sus"), 0, PHRYGIAN, REGS)
