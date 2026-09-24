"""industrial: インダストリアル（DESIGN.md §6.17）。6ch: 歪んだキック・スネア、金属の打楽器、歪んだ持続ベース、
金属パイプのリフ、歪んだ矩形波のリード、工場の騒音。

音色空間の疎な領域（強い飽和 × 持続・非調和、明るい低音）を使う。"""
from __future__ import annotations

from ..core.composer import RhythmMotif, ScaleRules
from ..core.model import ChordSpec
from ..core.pitch import fold_into_range
from ..profiles.band_common import (
    BandProfile, BassSpec, ChannelDef, FxSpec, LeadSpec, Section, _scale_vol, hits, preset,
)
from ..profiles.registry import register_profile

C = ChordSpec
CH_KS, CH_METAL, CH_BASS, CH_PIPE, CH_LEAD, CH_FX = range(6)

MAIN = (hits("kick", (0, 4, 8, 12), 60) + hits("snare", (4, 12), 52)
        + hits("clang", (2, 10), 40) + hits("clang", (6, 14), 32, 0.6) + hits("hat", range(1, 16, 2), 22, 0.7))
HALF = hits("kick", (0, 10), 58) + hits("snare", (8,), 54) + hits("clang", (3, 6, 14), 36)
METAL = hits("clang", (0, 3, 6, 10, 12), 42) + hits("hat", range(0, 16, 2), 20)
FILL = hits("snare", (8, 10, 12, 14), 50) + hits("clang", (13, 15), 44)
# 金属パイプのリフ（16分の位置と、和音の構成音の並びの番号）。pattern ごとに1つ選んで繰り返す
RIFFS = (((0, 0), (3, 0), (6, 1), (10, 0), (12, 2)), ((0, 0), (2, 1), (6, 0), (8, 2), (11, 1)),
         ((0, 0), (4, 0), (7, 2), (10, 1), (14, 0)))
PIPE_REGISTER = (12, 23)

LEAD_MOTIFS = {"verse": (RhythmMotif((0, 4, 8)), RhythmMotif((0, 3, 6, 12)), RhythmMotif((0, 8, 10)))}
RHYTHM = frozenset({"drums", "bass", "fx", "pipe"})


@register_profile
class IndustrialProfile(BandProfile):
    id = "industrial"
    display_name = "Industrial"
    description = "インダストリアル。歪んだビートと金属の打撃、うなる歪んだベースと工場の騒音"
    description_en = "Industrial: distorted beats and metal clangs, a roaring distorted bass and factory noise"
    title = "Iron Works"
    default_filename = "Industrial.mod"
    tempo_choices = (110, 114, 118, 122, 126, 130)

    KIT = (
        ("kick", preset("ind_kick")), ("snare", preset("ind_snare")), ("clang", preset("ind_metal_clang")),
        ("hat", preset("drum_909_hat")), ("bass", preset("bass_dist")), ("pipe", preset("ind_metal_pipe")),
        ("lead", preset("ind_buzz_lead")), ("noise", preset("fx_factory")),
    )
    CHANNELS = (
        ChannelDef("kick/snare", ("kick", "snare"), (("snare", 2),), pan=128),
        ChannelDef("metal", ("clang", "hat"), (("clang", 2),), pan=170),
        ChannelDef("bass", ("bass",), pan=128),
        ChannelDef("pipe", ("pipe",), pan=84),
        ChannelDef("lead", ("lead",), pan=150),
        ChannelDef("factory", ("noise",), pan=100),
    )
    DRUM_CHANNEL = {"kick": CH_KS, "snare": CH_KS, "clang": CH_METAL, "hat": CH_METAL}
    KEYS = (4, 2, 0, 9)
    MODE = "phrygian"
    PROGRESSIONS = (
        ("i-bII", (C(0, "min", label="i"), C(0, "min", label="i"), C(1, "maj", label="bII"), C(0, "min", label="i"))),
        ("i-bVI-bVII-i", (C(0, "min", label="i"), C(8, "maj", label="bVI"), C(10, "maj", label="bVII"),
                          C(0, "min", label="i"))),
        ("i-iv-bII-i", (C(0, "min", label="i"), C(5, "min", label="iv"), C(1, "maj", label="bII"),
                        C(0, "min", label="i"))),
    )
    SECTIONS = {
        "intro": Section("intro", prog=0, intensity=0.6, parts=frozenset({"drums", "fx", "pipe"}), groove="metal"),
        "a": Section("a", prog=0, intensity=0.85, parts=RHYTHM, fill=True),
        "b": Section("b", prog=1, intensity=1.0, parts=RHYTHM | {"lead"}, fill=True),
        "break": Section("break", prog=0, intensity=0.7, parts=frozenset({"drums", "fx", "pipe"}), groove="half"),
        "outro": Section("outro", prog=0, intensity=0.6, parts=frozenset({"drums", "fx"}), groove="metal"),
    }
    FORM = ("intro", "a", "a", "b", "break", "a", "b", "b", "outro")
    GROOVES = {"main": MAIN, "half": HALF, "metal": METAL, "fill": FILL}
    BASS = BassSpec("bass", CH_BASS, kind="pulse16", vol=44)
    FX = FxSpec("noise", CH_FX, every=2, vol=22)
    LEAD = LeadSpec("lead", CH_LEAD, ScaleRules(leap_probability=0.2, leap_semitones=(1, 3, 5, 7)), LEAD_MOTIFS,
                    vol=40, gate=0.7)

    def begin_pattern(self, pctx, rng):
        st = super().begin_pattern(pctx, rng)
        st.extra["riff"] = rng.harmony.choice(RIFFS)
        return st

    def extra_measure(self, mctx, sec, st, rng, buf):
        """金属パイプのリフ: pattern ごとに選んだ1小節の型を、和音の構成音で繰り返す。"""
        if "pipe" not in sec.parts:
            return
        chord = mctx.chord
        pcs = sorted({t % 12 for t in chord.chord_tones}, key=lambda pc: (pc - chord.bass) % 12)
        pipe = mctx.instruments["pipe"]
        for row, idx in st.extra["riff"]:
            note = fold_into_range(pcs[idx % len(pcs)], *PIPE_REGISTER)
            buf.put(row, CH_PIPE, pipe.cell(note, vol=_scale_vol(40 if row == 0 else 34, sec)))
