"""racing-breaks: 90年代後半のレースゲーム風（DESIGN.md §6.18）。ドラムンベース／ブレイクビーツ／2ステップの
3系統から曲ごとに1つを選び、エレピの 9th の和音・太いサブベース・声のような旋律を乗せる。"""
from __future__ import annotations

import dataclasses

from ..core.composer import RhythmMotif, ScaleRules
from ..core.midi import GmVoice
from ..core.model import ChordSpec
from ..core.pitch import fold_into_range
from ..core.synth import PitchSweepLayer
from ..profiles.band_common import (
    BandProfile, BassSpec, ChannelDef, CompSpec, EchoSpec, Fold, LayerSpec, LeadSpec, PadSpec, Section, _scale_vol,
    hits, keep, preset,
)
from ..profiles.registry import register_profile

C = ChordSpec
CH_KS, CH_HAT, CH_BASS, CH_EP, CH_PAD, CH_LEAD, CH_X_LEAD_ECHO, CH_X_BRASS = range(8)   # 7・8 番目は 8ch の編成だけ

# リズムの系統（DESIGN.md §6.18）: 名前 → (重み, BPM の候補)。曲ごとに plan() が1つ選ぶ
FAMILIES = {
    "dnb": (3, (166, 168, 170, 172, 174)),
    "breaks": (3, (144, 146, 148)),
    "twostep": (1, (118, 120, 122)),
}
FAMILY_NAMES = {"dnb": "drum'n'bass", "breaks": "breakbeat", "twostep": "2-step"}

HATS8 = hits("hat", (0, 4, 8, 12), 38) + hits("hat", (2, 6, 10, 14), 28)
FILL = hits("snare", (8, 10, 12, 13, 14, 15), 42)
CRASH = hits("crash", (0,), 50)
DRUMS = {
    # ドラムンベース: スネアは2・4拍、キックは1拍目と3拍目の裏（2拍目の裏は確率）、スネアのゴースト
    "dnb:main": (hits("kick", (0, 10), 60) + hits("kick", (6,), 46, 0.35) + hits("snare", (4, 12), 54)
                 + hits("snare", (7, 9, 15), 20, 0.4) + HATS8 + hits("ohat", (14,), 26, 0.3)),
    "dnb:intro": hits("kick", (0,), 50) + HATS8 + hits("ride", (2, 10), 24, 0.6),
    # ブレイクビーツ: 1拍目のキックと、次の拍へ食う16分のキック
    "breaks:main": (hits("kick", (0, 10), 60) + hits("kick", (3,), 44, 0.4) + hits("kick", (15,), 48, 0.6)
                    + hits("snare", (4, 12), 52) + hits("snare", (7, 14), 20, 0.35) + HATS8
                    + hits("ohat", (6,), 26, 0.3)),
    "breaks:intro": hits("kick", (0, 10), 50) + HATS8,
    # 2ステップ: 裏拍のオープン・ハットと、16分の裏の軽いハット、ずれたキック
    "twostep:main": (hits("kick", (0, 10), 58) + hits("kick", (5,), 46, 0.45) + hits("kick", (11,), 42, 0.3)
                     + hits("snare", (4, 12), 50) + hits("ohat", (2, 6, 10, 14), 26)
                     + hits("hat", range(1, 16, 2), 16, 0.7)),
    "twostep:intro": hits("kick", (0, 10), 50) + hits("ohat", (2, 6, 10, 14), 24),
    "fill": FILL,
    "crash": CRASH,
}

# ベースの型（16 row 基準）: (row, 音, 確率)。音は "root"・"fifth"・"octave"・"next"（次の和音の根音へ食う）・
# "approach"（次の和音の根音の半音下。同じ和音が続くなら5度）
BASS_LINES = {
    "dnb": ((0, "root", 1.0), (10, "root", 1.0), (14, "approach", 0.5)),
    "breaks": ((0, "root", 1.0), (3, "root", 0.5), (7, "fifth", 0.5), (10, "root", 1.0), (15, "next", 0.6)),
    "twostep": ((0, "root", 1.0), (3, "octave", 0.4), (6, "root", 1.0), (10, "root", 1.0), (13, "fifth", 0.5)),
}
# エレピの刻み: (row, 強勢か, 確率)
EP_ROWS = {
    "dnb": ((0, True, 1.0), (10, False, 1.0)),
    "breaks": ((0, True, 1.0), (7, False, 0.5), (10, False, 1.0)),
    "twostep": ((0, True, 1.0), (3, False, 0.6), (10, False, 1.0)),
}
EP_WOBBLE = 0x22   # 和音の直後の 4xy（エレピの揺れ。7xy は S3M/IT に変換できないので使わない）

# 低音（DESIGN.md §6.18）: 合成は実音が1オクターブ上になる（§3.1）ので、OST の太い低音（120 Hz 未満に
# エネルギーの約半分）に近づけるため、キックは掃引を半分の周波数で書き（実音 180→52 Hz）、ベースは shift=0 で
# 1オクターブ下の tracker note（t=0..11、実音 65〜123 Hz）で鳴らす
SUB_KICK = dataclasses.replace(
    preset("drum_909_kick"), name="RacingKick",
    layers=tuple(dataclasses.replace(wl, layer=dataclasses.replace(wl.layer, freq_start=90.0, freq_end=26.0))
                 if isinstance(wl.layer, PitchSweepLayer) else wl for wl in preset("drum_909_kick").layers))
SUB_BASS = preset("bass_deep", name="RacingSub", shift=0)

LEAD_MOTIFS = {
    "verse": (RhythmMotif((0, 6, 10)), RhythmMotif((0, 4, 8, 12)), RhythmMotif((2, 6, 10, 12))),
    "chorus": (RhythmMotif((0, 3, 6, 8, 12)), RhythmMotif((0, 4, 6, 10, 14))),
}
GROOVE = frozenset({"drums", "bass", "comp", "pad"})


@register_profile
class RacingBreaksProfile(BandProfile):
    id = "racing-breaks"
    category = "style"
    display_name = "90s Racing Game Breaks"
    description = "90年代後半のレースゲーム風。ドラムンベース／ブレイクビーツに 9th のエレピと太いサブベース"
    description_en = "Late-90s racing game style: drum'n'bass / breakbeat with 9th-chord e.piano and deep sub bass"
    title = "Night Circuit Breaks"
    default_filename = "RacingBreaks.mod"
    tempo_choices = tuple(sorted(b for _w, bpms in FAMILIES.values() for b in bpms))

    KIT = (
        ("kick", SUB_KICK), ("snare", preset("drum_pop_snare")), ("hat", preset("drum_909_hat")),
        ("ohat", preset("drum_909_open_hat")), ("ride", preset("swing_ride")), ("crash", preset("march_crash_cymbal")),
        ("bass", SUB_BASS), ("vox", preset("vox_ooh")),
    )
    CHORD_KITS = {"ep": (preset("keys_ep"), 0.0), "pad": (preset("pad_warm"), 0.0),
                  "brass": (preset("march_brass_horn", volume=36), 0.0)}
    GM = {"kick": GmVoice(drum_note=36), "bass": GmVoice(program=38), "brass": GmVoice(program=61)}
    CHANNELS = (
        ChannelDef("kick/snare", ("kick", "snare"), (("snare", 2),), pan=128),
        ChannelDef("hat/ride", ("hat", "ohat", "ride", "crash"), (("crash", 3), ("ohat", 2), ("ride", 2)), pan=164),
        ChannelDef("bass", ("bass",), pan=128),
        ChannelDef("e.piano", ("ep",), pan=88),
        ChannelDef("pad", ("pad",), pan=64),
        ChannelDef("lead", ("vox",), pan=160),
        ChannelDef("lead echo", ("vox",), pan=96),
        ChannelDef("brass", ("brass",), pan=184),
    )
    DRUM_CHANNEL = {"kick": CH_KS, "snare": CH_KS, "hat": CH_HAT, "ohat": CH_HAT, "ride": CH_HAT, "crash": CH_HAT}
    KEYS = (9, 10, 4, 0, 5)
    MODE = "aeolian"
    MODE_BY_QUALITY = {"m9": "dorian", "maj9": "lydian", "7sus4": "mixolydian"}
    PROGRESSIONS = (
        ("i9-iv9", (C(0, "m9", label="im9"), C(5, "m9", label="ivm9"))),
        ("i9-bVImaj9", (C(0, "m9", label="im9"), C(8, "maj9", label="bVImaj9"))),
        ("i9-bIImaj9", (C(0, "m9", label="im9"), C(1, "maj9", label="bIImaj9"))),
        ("bIIImaj9-bVImaj9-i9-v7sus4", (C(3, "maj9", label="bIIImaj9"), C(8, "maj9", label="bVImaj9"),
                                        C(0, "m9", label="im9"), C(7, "7sus4", label="v7sus4"))),
        ("i9-bVIImaj9-bVImaj9-v7sus4", (C(0, "m9", label="im9"), C(10, "maj9", label="bVIImaj9"),
                                        C(8, "maj9", label="bVImaj9"), C(7, "7sus4", label="v7sus4"))),
    )
    SECTIONS = {
        "intro": Section("intro", prog=0, intensity=0.55, parts=frozenset({"drums", "pad"}), groove="intro"),
        "groove": Section("groove", prog=0, intensity=0.75, parts=GROOVE),
        "a": Section("a", prog=0, intensity=0.85, parts=GROOVE | {"lead"}),
        "b": Section("b", prog=1, intensity=1.0, parts=GROOVE | {"lead"}, crash=True, fill=True,
                     lead_motifs="chorus"),
        "break": Section("break", prog=1, intensity=0.5, parts=frozenset({"comp", "pad"})),
        "build": Section("build", prog=0, intensity=0.7, parts=frozenset({"drums", "bass", "pad"}), groove="intro",
                         fill=True),
        "outro": Section("outro", prog=0, intensity=0.6, parts=frozenset({"drums", "bass", "pad"})),
    }
    FORM = ("intro", "groove", "groove", "a", "a", "b", "b", "groove", "a", "a", "b", "b", "break", "break", "build",
            "b", "b", "outro", "outro")
    GROOVES = DRUMS
    BASS = BassSpec("bass", CH_BASS, vol=50)
    COMP = CompSpec("ep", CH_EP, vol=42, wobble=EP_WOBBLE)
    PAD = PadSpec("pad", CH_PAD, vol=26)
    LEAD = LeadSpec("vox", CH_LEAD, ScaleRules(leap_probability=0.2, leap_semitones=(3, 4, 5, 7),
                                               dissonance_weight=0.1), LEAD_MOTIFS, vol=44, gate=0.9, vibrato=0x33)
    ECHO = (EchoSpec(CH_LEAD, CH_X_LEAD_ECHO, delay=3, ratio=0.45, offs=True),)
    LAYERS = (LayerSpec("brass", CH_X_BRASS, follow="lead", vol=30, chordal=True),)
    ARRANGEMENTS = {                          # DESIGN.md §6.14: 4ch＝小編成、6ch＝標準、8ch＝任意パートを足す
        4: (Fold("drums", ("kick/snare", "hat/ride"), (("snare", 4), ("kick", 3), ("crash", 2))),
            *keep("bass", "e.piano", "lead")),
        6: keep("kick/snare", "hat/ride", "bass", "e.piano", "pad", "lead"),
        8: keep("kick/snare", "hat/ride", "bass", "e.piano", "pad", "lead", "lead echo", "brass"),
    }

    # --- 計画: 曲ごとにリズムの系統を選ぶ ---
    def plan(self, rng):
        names = list(FAMILIES)
        family = rng.plan.choices(names, weights=[FAMILIES[n][0] for n in names])[0]
        base = super().plan(rng)
        bpm = rng.plan.choice(FAMILIES[family][1])
        for pp in base.patterns:
            pp.extra["family"] = family
        summary = [f"Rhythm      : {FAMILY_NAMES[family]}", *base.summary]
        return dataclasses.replace(base, bpm=bpm, summary=summary)

    def _pattern_plan(self, sec, progs, key_pc):
        """measure ごとの根音（ベースが次の和音へ食うため）を ``extra["roots"]`` に足す。"""
        pp = super()._pattern_plan(sec, progs, key_pc)
        pp.extra["roots"] = tuple(slot.chord.bass for slot in pp.slots for _ in range(slot.measures))
        return pp

    # --- 各パート ---
    def drums(self, mctx, sec, rng, buf):
        family = mctx.pattern.extra["family"]
        super().drums(mctx, dataclasses.replace(sec, groove=f"{family}:{sec.groove}"), rng, buf)

    def bass(self, mctx, sec, rng, buf):
        """系統ごとの型。次の和音の根音へ半音で近づく／16分前に食う音を確率で入れる。"""
        lo, hi = self.REGISTERS.bass
        root = mctx.chord.bass
        roots = mctx.pattern.extra["roots"]
        nxt = roots[(mctx.measure_idx + 1) % len(roots)]
        tones = {
            "root": root,
            "fifth": fold_into_range(root + 7, lo, hi),
            "octave": root + 12,
            "next": nxt,
            "approach": fold_into_range(nxt - 1 if nxt != root else root + 7, lo, hi),
        }
        inst = mctx.instruments[self.BASS.key]
        for row, tone, prob in BASS_LINES[mctx.pattern.extra["family"]]:
            if row >= mctx.measure_rows or (prob < 1.0 and rng.bass.random() >= prob):
                continue
            vol = self.BASS.vol if row == 0 else self.BASS.vol - 6
            buf.put(row, CH_BASS, inst.cell(tones[tone], vol=_scale_vol(vol, sec)))

    def comp(self, mctx, sec, rng, buf):
        """エレピの和音を系統ごとの位置で鳴らし、強拍の直後に揺れ（4xy）を付ける。"""
        c = self.COMP
        inst = mctx.instruments[self._chord_key(c.key, mctx)]
        for row, accent, prob in EP_ROWS[mctx.pattern.extra["family"]]:
            if row >= mctx.measure_rows or (prob < 1.0 and rng.harmony.random() >= prob):
                continue
            buf.put(row, c.channel, inst.cell(mctx.chord.harmony, vol=_scale_vol(c.vol if accent else c.vol - 10, sec)))
            if accent and row + 1 < mctx.measure_rows and buf.get(row + 1, c.channel).is_empty:
                buf.put(row + 1, c.channel, inst.cell(effect=0x4, param=c.wobble))
