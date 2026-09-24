"""ambient: アンビエント（DESIGN.md §6.16.15）。A4（4ch、Amiga 互換）: 2つのパッドが和音の異なる構成音を持続し、
まばらなベルとそのエコーが漂う。打楽器なし。和音は4小節（1 pattern）ごと。"""
from __future__ import annotations

from ..core.model import ChordSpec
from ..core.pitch import fold_into_range
from ..profiles.band_common import BandProfile, ChannelDef, EchoSpec, PadSpec, Section, preset
from ..profiles.registry import register_profile

C = ChordSpec
CH_PAD, CH_GLASS, CH_BELL, CH_ECHO = range(4)
GLASS_REGISTER = (19, 30)
BELL_REGISTER = (24, 35)


@register_profile
class AmbientProfile(BandProfile):
    id = "ambient"
    display_name = "Ambient"
    description = "アンビエント。拍の弱い、重なり合うパッドとまばらなベル"
    description_en = "Ambient: layered pads and sparse bells with little or no beat"
    title = "Ambient Layers"
    default_filename = "Ambient.mod"
    tempo_choices = (60, 64, 68, 72)

    KIT = (("glass", preset("pad_glass")), ("bell", preset("keys_bell")))
    CHORD_KITS = {"pad": (preset("pad_warm"), 0.0)}
    CHANNELS = (
        ChannelDef("pad", ("pad",)),
        ChannelDef("glass pad", ("glass",)),
        ChannelDef("bell", ("bell",)),
        ChannelDef("bell echo", ("bell",)),
    )
    KEYS = (2, 4)
    MODE = "lydian"
    # 1 pattern（4小節）に1和音。区間ごとに別の和音を当てる
    PROGRESSIONS = (
        ("Imaj7", (C(0, "maj7", label="Imaj7"),)),
        ("IVmaj7", (C(5, "maj7", label="IVmaj7"),)),
        ("vi(add9)", (C(9, "m9", label="vi9"),)),
    )
    N_PROGRESSIONS = 3
    SECTIONS = {
        "layer1": Section("layer1", prog=0, intensity=0.3, parts=frozenset({"pad"})),
        "layer2": Section("layer2", prog=1, intensity=0.5, parts=frozenset({"pad", "glass", "bell"})),
        "bloom": Section("bloom", prog=2, intensity=0.8, parts=frozenset({"pad", "glass", "bell"})),
        "drift": Section("drift", prog=0, intensity=0.5, parts=frozenset({"glass", "bell"})),
        "fade": Section("fade", prog=0, intensity=0.2, parts=frozenset({"pad"})),
    }
    FORM = ("layer1", "layer2", "bloom", "layer2", "drift", "fade")
    PAD = PadSpec("pad", CH_PAD, vol=34)
    ECHO = (EchoSpec(CH_BELL, CH_ECHO, delay=5, ratio=0.5, repeats=2),)

    def extra_measure(self, mctx, sec, st, rng, buf):
        ins = mctx.instruments
        vol = round(36 * (0.55 + 0.45 * sec.intensity))
        pcs = sorted({t % 12 for t in mctx.chord.chord_tones}, key=lambda pc: (pc - mctx.chord.harmony) % 12)
        if mctx.measure_idx == 0:
            if "glass" in sec.parts:
                # パッドの根音とは別の構成音（第3音か第7音）を上で伸ばす
                pc = rng.harmony.choice(pcs[1:2] + pcs[3:4]) if len(pcs) > 3 else pcs[-1]
                buf.put(0, CH_GLASS, ins["glass"].cell(fold_into_range(pc, *GLASS_REGISTER), vol=vol))
            else:
                buf.put(0, CH_GLASS, ins["glass"].off())     # 前の区間から鳴り続けないように止める
        if "bell" in sec.parts:
            n = 1 if rng.melody.random() < 0.6 else 0
            if sec.kind == "bloom":
                n += 1
            lo, hi = BELL_REGISTER
            tones = [t for t in range(lo, hi + 1) if t % 12 in set(pcs)]
            for row in sorted(rng.melody.sample((0, 4, 6, 8, 10), k=n)):
                buf.put(row, CH_BELL, ins["bell"].cell(rng.melody.choice(tones), vol=round(vol * 0.9)))
