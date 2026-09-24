"""第３段階のジャンルが共有する骨格（DESIGN.md §12.5）。core ではなくジャンル共通の補助（suspense_common と同じ位置づけ）。

多くのジャンルは「ドラム・ベース・和音・旋律・パッド」という同じ骨格を持つ。``BandProfile`` はそれを
宣言（クラス属性）から組み立てる基底クラスで、各ジャンルは楽器・チャンネル・進行・構成・ドラムの型・
各パートの鳴らし方を宣言し、固有の文法だけをフック（``extra_measure`` 等）で足す。

- ``KIT``: ``(サンプル名, Patch)`` の列（挿入順＝サンプル番号）。
- ``CHORD_KITS``: 和音サンプルの素材。``{接頭辞: (Patch, strum_ms)}``。進行に現れる和音の種類ごとに
  ``<接頭辞>_<quality>`` のサンプルを ``chord_patch`` で作り、KIT の後ろに足す。
- ``CHANNELS``: ``ChannelDef`` の列（チャンネル数＝要素数）。``keys`` には KIT の名前か和音の接頭辞を書く。
- ``PROGRESSIONS``: ``(名前, (ChordSpec, ...))`` の列。``plan()`` が区間の数だけ異なる進行を選ぶ。
- ``SECTIONS``・``FORM``: 区間の定義と並び（同じ区間名は同じ pattern を再利用する）。
- ``GROOVES``: ドラムの型（``Groove``）。``BASS``・``COMP``・``LEAD``・``PAD``・``ARP``: 各パートの鳴らし方。

``channel_plan``・``gm_voices``・``channel_pans`` は ``__init_subclass__`` がクラス定義時に宣言から作る。
"""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import Any, Optional, Sequence

from ..core import groove as groove_mod
from ..core import mixer, synth
from ..core.composer import MelodyGenerator, NoteEvent, RhythmMotif, ScaleRules, articulate
from ..core.harmony import PC_NAMES, Registers, voice
from ..core.midi import GmVoice
from ..core.model import (
    Cell,
    ChannelRole,
    ChordDef,
    ChordSlot,
    ChordSpec,
    Instrument,
    MeasureBuffer,
    MeasureCtx,
    Pattern,
    PatternCtx,
    PatternPlan,
    RngStreams,
    SampleSpec,
    SongPlan,
)
from ..core.pitch import CHORD_QUALITIES, MODES, Scale, fold_into_range
from ..core.synth import Loop, Patch, ToneLayer, WeightedLayer
from ..core.synth_presets import PRESETS
from ..errors import PlanError, SampleConstraintError
from .base import GenreProfile

ROWS_PER_PATTERN = 64
ALL_PARTS = frozenset({"drums", "bass", "comp", "lead", "pad", "arp", "fx"})


# ============================================================
# 和音サンプル
# ============================================================

MAX_LOOP_CHORD_CENTS = 12.0   # ループの和音で、構成音のサイクル数を整数に丸めたときに許す音程誤差


def chord_patch(base: Patch, quality: str, *, strum_ms: float = 0.0) -> Patch:
    """``base`` の音色で和音 ``quality`` を1サンプルに焼き込んだ Patch（根音の高さで鳴らす）。

    ToneLayer を構成音の数だけ複製して各部分音を音程比倍する（機械的な変換で美的判断を含まない）。
    PitchSweep・Noise のレイヤー（打鍵の雑音など）は1回だけ残す。``strum_ms`` > 0 なら構成音ごとに
    鳴り始めを遅らせてギターのストロークにする（OneShot のみ）。ループの素材はサイクル数を整数に丸めるので、
    基本サイクル数が大きい（例: K=120）素材でないと音程がずれる（誤差が ``MAX_LOOP_CHORD_CENTS`` を超えたら例外）。
    """
    import math

    intervals = CHORD_QUALITIES[quality]
    is_loop = isinstance(base.finish, Loop)
    gain = 1.0 / math.sqrt(len(intervals))
    layers: list[WeightedLayer] = []
    for i, semi in enumerate(intervals):
        ratio = 2.0 ** (semi / 12.0)
        for wl in base.layers:
            layer = wl.layer
            if isinstance(layer, ToneLayer):
                partials = []
                for mult, weight, alpha in layer.partials:
                    m = mult * ratio
                    if is_loop:
                        rounded = round(m)
                        err = abs(1200.0 * math.log2(rounded / m))
                        if err > MAX_LOOP_CHORD_CENTS:
                            raise SampleConstraintError(
                                f"{base.name}: loop chord {quality} is {err:.1f} cents off (cycle {mult} too small)")
                        m = rounded
                    partials.append((m, weight, alpha))
                layers.append(WeightedLayer(ToneLayer(tuple(partials), layer.filter), wl.weight * gain,
                                            0.0 if is_loop else wl.offset_ms + i * strum_ms))
            elif i == 0:
                layers.append(wl)
    name = f"{base.name[:13]}{quality}"[:22]
    return dataclasses.replace(base, name=name, layers=tuple(layers))


# ============================================================
# 宣言の型
# ============================================================

@dataclass(frozen=True)
class ChannelDef:
    name: str
    keys: tuple[str, ...]                     # KIT の名前、または CHORD_KITS の接頭辞
    priority: tuple[tuple[str, int], ...] = ()  # (名前, 優先度)。未記載は 1
    pan: int = 128


@dataclass(frozen=True)
class Hit:
    row: int
    key: str
    vol: int
    prob: float = 1.0


Groove = tuple[Hit, ...]


def hits(key: str, rows: Sequence[int], vol: int, prob: float = 1.0) -> tuple[Hit, ...]:
    return tuple(Hit(r, key, vol, prob) for r in rows)


@dataclass(frozen=True)
class Section:
    kind: str
    prog: int = 0                              # 使う進行の番号（plan() が選んだ A=0、B=1 …）
    intensity: float = 0.7
    parts: frozenset[str] = ALL_PARTS
    groove: str = "main"
    key_offset: int = 0
    fill: bool = False                         # 最後の measure の後半を GROOVES["fill"] に差し替える
    crash: bool = False                        # 先頭で GROOVES["crash"] を鳴らす
    lead_motifs: str = "verse"                 # LeadSpec.motifs の組の名前


@dataclass(frozen=True)
class BassSpec:
    key: str
    channel: int
    kind: str = "root8"                        # §12.5 bass_line の型
    vol: int = 54


@dataclass(frozen=True)
class CompSpec:
    key: str                                   # 和音サンプルの接頭辞（CHORD_KITS）か単音の KIT 名
    channel: int
    kind: str = "whole"                        # §12.5 comp の型
    vol: int = 44
    chordal: bool = True                       # True: 和音サンプルを鳴らす／False: 単音で和音を分散させる
    wobble: int = 0                            # 和音の直後に付ける 4xy（テープの揺れ・トレモロ風）。0 なら付けない


@dataclass(frozen=True)
class FxSpec:
    key: str                                   # 長い OneShot（fx_vinyl・fx_rain 等）
    channel: int
    every: int = 2                             # 何 measure ごとに鳴らし直すか
    vol: int = 20


@dataclass(frozen=True)
class LeadSpec:
    key: str
    channel: int
    rules: ScaleRules
    motifs: dict[str, tuple[RhythmMotif, ...]]
    vol: int = 48
    gate: float = 0.9
    vibrato: int = 0                           # 長音（≥ 6 row）に付ける 4xy の param（0 なら付けない）


@dataclass(frozen=True)
class PadSpec:
    key: str                                   # 和音サンプルの接頭辞か単音の KIT 名
    channel: int
    vol: int = 36
    chordal: bool = True


@dataclass(frozen=True)
class ArpSpec:
    key: str
    channel: int
    rows: tuple[int, ...] = tuple(range(0, 16, 2))   # 発音する row
    vol: int = 38
    pattern: str = "up"                        # "up" | "updown"


@dataclass(frozen=True)
class EchoSpec:
    src: int
    dst: int
    delay: int = 3
    ratio: float = 0.5
    repeats: int = 1


@dataclass
class BandState:
    lead_prev: Optional[int] = None
    lead_gen: Optional[MelodyGenerator] = None
    extra: dict[str, Any] = field(default_factory=dict)


# ============================================================
# BandProfile
# ============================================================

class BandProfile(GenreProfile):
    """宣言から作曲する第３段階ジャンルの基底。サブクラスは下のクラス属性を定義する。"""

    KIT: tuple[tuple[str, Patch], ...] = ()
    CHORD_KITS: dict[str, tuple[Patch, float]] = {}
    CHANNELS: tuple[ChannelDef, ...] = ()
    GM: dict[str, GmVoice] = {}                # 既定値（GM_DEFAULTS）を上書きしたい楽器だけ
    KEYS: tuple[int, ...] = (0,)
    MODE: str = "ionian"
    MODE_BY_QUALITY: dict[str, str] = {}
    REGISTERS = Registers(bass=(0, 11), harmony=(12, 23), melody=(19, 33))
    ARP_REGISTER: tuple[int, int] = (24, 35)
    PROGRESSIONS: tuple[tuple[str, tuple[ChordSpec, ...]], ...] = ()
    N_PROGRESSIONS: int = 2
    SECTIONS: dict[str, Section] = {}
    FORM: tuple[str, ...] = ()
    GROOVES: dict[str, Groove] = {}
    DRUM_CHANNEL: dict[str, int] = {}          # ドラムの KIT 名 → チャンネル
    BASS: Optional[BassSpec] = None
    COMP: Optional[CompSpec] = None
    LEAD: Optional[LeadSpec] = None
    PAD: Optional[PadSpec] = None
    ARP: Optional[ArpSpec] = None
    FX: Optional[FxSpec] = None
    ECHO: tuple[EchoSpec, ...] = ()
    SWING: Optional[groove_mod.SwingConfig] = None
    SIDECHAIN: tuple[tuple[str, int, float, int], ...] = ()   # (トリガの KIT 名, 対象チャンネル, 比, 戻る row 数)
    LATE: tuple[tuple[str, float], ...] = ()   # (ドラムの KIT 名, EDx で遅らせる確率)
    HUMANIZE: int = 4                          # ドラムの音量ゆらぎ（±）
    tempo_policy = "engine"
    rng_mode = "streams"
    strict_buffers = True

    # --- クラス定義時に宣言から作る属性 ---
    def __init_subclass__(cls, **kw):
        super().__init_subclass__(**kw)
        if not cls.KIT:
            return
        cls._qualities = _qualities(cls.PROGRESSIONS)
        cls._sample_keys = [k for k, _ in cls.KIT] + [
            f"{prefix}_{q}" for prefix in cls.CHORD_KITS for q in cls._qualities]
        if len(cls._sample_keys) > 31:
            raise PlanError(f"{cls.__name__}: {len(cls._sample_keys)} samples (max 31)")
        slot = {k: i + 1 for i, k in enumerate(cls._sample_keys)}
        roles = []
        for cd in cls.CHANNELS:
            names = [k for key in cd.keys for k in cls._expand(key)]
            pr = dict(cd.priority)
            priority = {slot[n]: pr.get(n, pr.get(n.rsplit("_", 1)[0], 1)) for n in names if n in slot}
            roles.append(ChannelRole(cd.name, frozenset(slot[n] for n in names), priority))
        cls.channel_plan = tuple(roles)
        cls.channel_pans = tuple(cd.pan for cd in cls.CHANNELS) if len(cls.CHANNELS) != 4 else None
        base_patch = dict(cls.KIT) | {p: pt for p, (pt, _s) in cls.CHORD_KITS.items()}
        cls.gm_voices = {k: cls.GM.get(k) or cls.GM.get(k.rsplit("_", 1)[0]) or gm_default(base_patch[_base_key(cls, k)])
                         for k in cls._sample_keys}
        cls._slot = slot
        if cls.SWING is not None or cls.SIDECHAIN:
            cls.post_processors = (cls._post,)

    @classmethod
    def _expand(cls, key: str) -> list[str]:
        if key in cls.CHORD_KITS:
            return [f"{key}_{q}" for q in cls._qualities]
        return [key]

    # --- 音色 ---
    def build_samples(self) -> dict[str, SampleSpec]:
        out = {k: synth.render(p) for k, p in self.KIT}
        for prefix, (patch, strum) in self.CHORD_KITS.items():
            for q in self._qualities:
                out[f"{prefix}_{q}"] = synth.render(chord_patch(patch, q, strum_ms=strum))
        return out

    # --- 計画 ---
    def plan(self, rng: RngStreams) -> SongPlan:
        bpm = rng.plan.choice(list(self.tempo_choices))
        key_pc = rng.plan.choice(list(self.KEYS))
        chosen = rng.plan.sample(range(len(self.PROGRESSIONS)), k=min(self.N_PROGRESSIONS, len(self.PROGRESSIONS)))
        progs = [self.PROGRESSIONS[i] for i in chosen]
        names = list(dict.fromkeys(self.FORM))
        patterns = [self._pattern_plan(self.SECTIONS[n], progs, key_pc) for n in names]
        order = [names.index(n) for n in self.FORM]
        summary = [f"Key         : {PC_NAMES[key_pc]} {self.MODE}"]
        for i, (pname, specs) in enumerate(progs):
            chords = " - ".join(s.label or "?" for s in specs)
            summary.append(f"Progression {chr(ord('A') + i)}: {pname} ({chords})")
        return SongPlan(bpm=bpm, patterns=patterns, order=order, key_pc=key_pc, summary=summary)

    def _pattern_plan(self, sec: Section, progs, key_pc: int) -> PatternPlan:
        rpm = self.rows_per_measure
        n_measures = ROWS_PER_PATTERN // rpm
        _pname, specs = progs[sec.prog % len(progs)]
        per = max(1, n_measures // len(specs))
        tonic = (key_pc + sec.key_offset) % 12
        scale = Scale(tonic, MODES[self.MODE])
        slots, qualities = [], []
        m = 0
        while m < n_measures:
            for spec in specs:
                if m >= n_measures:
                    break
                k = min(per, n_measures - m)
                chord = voice(spec, tonic, scale, self.REGISTERS, mode_by_quality=self.MODE_BY_QUALITY or None)
                slots.append(ChordSlot(chord, measures=k))
                qualities.extend([spec.quality] * k)
                m += k
        return PatternPlan(sec.kind, slots, intensity=sec.intensity, key_offset=sec.key_offset,
                           extra={"qualities": tuple(qualities), "tonic": tonic})

    # --- 作曲 ---
    def begin_pattern(self, pctx: PatternCtx, rng: RngStreams) -> BandState:
        st = BandState()
        sec = self.SECTIONS[pctx.kind]
        if self.LEAD is not None and "lead" in sec.parts:
            scale = Scale(pctx.extra["tonic"], MODES[self.MODE])
            st.lead_gen = MelodyGenerator(self.LEAD.rules, self.REGISTERS.melody, scale, rng.melody,
                                          base_vol=self.LEAD.vol, beat_rows=self.rows_per_beat)
            st.extra["motif_a"] = rng.melody.choice(self.LEAD.motifs[sec.lead_motifs])
            st.extra["motif_b"] = rng.melody.choice(self.LEAD.motifs[sec.lead_motifs])
        return st

    def compose_measure(self, mctx: MeasureCtx, st: BandState, rng: RngStreams, buf: MeasureBuffer) -> None:
        sec = self.SECTIONS[mctx.pattern.kind]
        ins = mctx.instruments
        parts = sec.parts
        if "drums" in parts:
            self.drums(mctx, sec, rng, buf)
        if self.BASS is not None:
            if "bass" in parts:
                self.bass(mctx, sec, rng, buf)
            else:
                self._silence(buf, self.BASS.channel, self.BASS.key, ins, mctx)
        if self.COMP is not None and "comp" in parts:
            self.comp(mctx, sec, rng, buf)
        if self.PAD is not None:
            if "pad" in parts:
                self.pad(mctx, sec, rng, buf)
            else:
                self._silence(buf, self.PAD.channel, self.PAD.key, ins, mctx)
        if self.ARP is not None and "arp" in parts:
            self.arp(mctx, sec, rng, buf)
        if self.FX is not None and "fx" in parts and mctx.measure_idx % self.FX.every == 0:
            buf.put(0, self.FX.channel, mctx.instruments[self.FX.key].cell(vol=_scale_vol(self.FX.vol, sec)))
        if self.LEAD is not None:
            if "lead" in parts and st.lead_gen is not None:
                self.lead(mctx, sec, st, rng, buf)
            else:
                self._silence(buf, self.LEAD.channel, self.LEAD.key, ins, mctx)
        self.extra_measure(mctx, sec, st, rng, buf)

    def extra_measure(self, mctx: MeasureCtx, sec: Section, st: BandState, rng: RngStreams,
                      buf: MeasureBuffer) -> None:
        """ジャンル固有の追加（既定は何もしない）。"""

    def finalize_pattern(self, pctx: PatternCtx, pattern: Pattern, st: BandState, rng: RngStreams) -> None:
        for e in self.ECHO:
            echo(pattern, e.src, e.dst, e.delay, e.ratio, e.repeats)
        if pctx.is_first_in_order:
            need = 2 if self.SWING is not None else 1
            reserve_row0(pattern, need)

    # --- 各パート（サブクラスで上書きしてよい） ---
    def _chord_key(self, prefix: str, mctx: MeasureCtx) -> str:
        return f"{prefix}_{mctx.pattern.extra['qualities'][mctx.measure_idx]}"

    def _is_chord_change(self, mctx: MeasureCtx) -> bool:
        return mctx.chord_measure_offset == 0

    def _silence(self, buf, ch: int, key: str, ins, mctx: MeasureCtx) -> None:
        """鳴らさない区間ではループ音色を先頭で止める（前の pattern から鳴り続けないように）。"""
        if mctx.measure_idx == 0:
            buf.put(0, ch, Cell(None, 0, vol=0))

    def drums(self, mctx: MeasureCtx, sec: Section, rng: RngStreams, buf: MeasureBuffer) -> None:
        rows = mctx.measure_rows
        groove = list(self.GROOVES[sec.groove])
        if sec.fill and mctx.is_last and "fill" in self.GROOVES:
            half = rows // 2
            groove = [h for h in groove if h.row < half] + list(self.GROOVES["fill"])
        if sec.crash and mctx.measure_idx == 0 and "crash" in self.GROOVES:
            groove += list(self.GROOVES["crash"])
        late = dict(self.LATE)
        for h in groove:
            if h.row >= rows or (h.prob < 1.0 and rng.drums.random() >= h.prob):
                continue
            inst = mctx.instruments[h.key]
            if h.key in late and rng.drums.random() < late[h.key]:
                cell = inst.cell(effect=0x0E, param=groove_mod.delay_param(rng.drums.randint(1, 2)))   # EDx: 1〜2 tick 遅らせる
            else:
                j = rng.drums.randint(-self.HUMANIZE, self.HUMANIZE) if self.HUMANIZE else 0
                vol = max(1, min(64, round((h.vol + j) * (0.6 + 0.4 * sec.intensity))))
                cell = inst.cell(vol=vol)
            buf.put(h.row, self.DRUM_CHANNEL[h.key], cell)

    def bass(self, mctx: MeasureCtx, sec: Section, rng: RngStreams, buf: MeasureBuffer) -> None:
        b = self.BASS
        inst = mctx.instruments[b.key]
        for row, note, vol in bass_line(b.kind, mctx.chord, mctx.measure_rows, self.REGISTERS.bass, rng.bass, b.vol):
            buf.put(row, b.channel, inst.cell(note, vol=_scale_vol(vol, sec)))

    def comp(self, mctx: MeasureCtx, sec: Section, rng: RngStreams, buf: MeasureBuffer) -> None:
        c = self.COMP
        rows = comp_rows(c.kind, mctx.measure_rows, rng.harmony)
        if c.chordal:
            inst = mctx.instruments[self._chord_key(c.key, mctx)]
            for row, accent in rows:
                vol = _scale_vol(c.vol if accent else max(1, c.vol - 10), sec)
                buf.put(row, c.channel, inst.cell(mctx.chord.harmony, vol=vol))
                if c.wobble and row + 1 < mctx.measure_rows and buf.get(row + 1, c.channel).is_empty:
                    buf.put(row + 1, c.channel, inst.cell(effect=0x4, param=c.wobble))
        else:
            inst = mctx.instruments[c.key]
            tones = _arp_tones(mctx.chord, self.REGISTERS.harmony)
            for i, (row, accent) in enumerate(rows):
                vol = _scale_vol(c.vol if accent else max(1, c.vol - 10), sec)
                buf.put(row, c.channel, inst.cell(tones[i % len(tones)], vol=vol))

    def pad(self, mctx: MeasureCtx, sec: Section, rng: RngStreams, buf: MeasureBuffer) -> None:
        p = self.PAD
        if not self._is_chord_change(mctx):
            return
        if p.chordal:
            inst = mctx.instruments[self._chord_key(p.key, mctx)]
        else:
            inst = mctx.instruments[p.key]
        buf.put(0, p.channel, inst.cell(mctx.chord.harmony, vol=_scale_vol(p.vol, sec)))

    def arp(self, mctx: MeasureCtx, sec: Section, rng: RngStreams, buf: MeasureBuffer) -> None:
        a = self.ARP
        inst = mctx.instruments[a.key]
        tones = _arp_tones(mctx.chord, self.ARP_REGISTER)
        if a.pattern == "updown" and len(tones) > 2:
            tones = tones + tones[-2:0:-1]
        for i, row in enumerate(r for r in a.rows if r < mctx.measure_rows):
            vol = _scale_vol(a.vol if i % 4 == 0 else max(1, a.vol - 6), sec)
            buf.put(row, a.channel, inst.cell(tones[i % len(tones)], vol=vol))

    def lead(self, mctx: MeasureCtx, sec: Section, st: BandState, rng: RngStreams, buf: MeasureBuffer) -> None:
        """4小節の楽節: A・A（反復）・B・終止（後半は息継ぎの休符）。"""
        spec = self.LEAD
        phrase_pos = mctx.measure_idx % 4
        motif = st.extra["motif_a"] if phrase_pos in (0, 1) else st.extra["motif_b"]
        cadence = phrase_pos == 3
        if cadence:
            half = mctx.measure_rows // 2
            motif = RhythmMotif(tuple(r for r in motif.rows if r < half) or (0,))
        events, st.lead_prev = st.lead_gen.bar(
            motif, mctx.chord, st.lead_prev, cadence=cadence, rows=mctx.measure_rows,
            base_vol=_scale_vol(spec.vol, sec))
        if cadence:
            events = [dataclasses.replace(e, dur=min(e.dur, mctx.measure_rows // 2 - e.row)) for e in events]
            events = [e for e in events if e.dur > 0]
        articulate(buf, spec.channel, events, mctx.instruments[spec.key], gate=spec.gate)
        if spec.vibrato:
            for e in events:
                if e.dur >= 6 and e.row + 2 < mctx.measure_rows and buf.get(e.row + 2, spec.channel).is_empty:
                    buf.put(e.row + 2, spec.channel,
                            mctx.instruments[spec.key].cell(effect=0x4, param=spec.vibrato))

    # --- 後処理（スウィング・サイドチェイン） ---
    @classmethod
    def _post(cls, song, plan) -> None:
        if cls.SIDECHAIN:
            rules = [mixer.SidechainRule(cls._slot[k], ch, ratio, rel) for k, ch, ratio, rel in cls.SIDECHAIN]
            mixer.apply_sidechain(song, rules)
        if cls.SWING is not None:
            for pattern in song.patterns:
                groove_mod.apply_swing(pattern, cls.SWING)


# ============================================================
# 補助関数
# ============================================================

def _qualities(progressions) -> tuple[str, ...]:
    seen: dict[str, None] = {}
    for _name, specs in progressions:
        for s in specs:
            seen.setdefault(s.quality, None)
    return tuple(seen)


def _base_key(cls, key: str) -> str:
    if key in dict(cls.KIT):
        return key
    return key.rsplit("_", 1)[0]


def _scale_vol(vol: int, sec: Section) -> int:
    return max(1, min(64, round(vol * (0.55 + 0.45 * sec.intensity))))


def _arp_tones(chord: ChordDef, register: tuple[int, int]) -> list[int]:
    pcs = sorted({t % 12 for t in chord.chord_tones}, key=lambda pc: (pc - chord.harmony) % 12)
    lo, hi = register
    notes = sorted({fold_into_range(lo + ((pc - lo) % 12), lo, hi) for pc in pcs})
    return notes or [fold_into_range(chord.harmony, lo, hi)]


def bass_line(kind: str, chord: ChordDef, rows: int, register: tuple[int, int], rng, vol: int
              ) -> list[tuple[int, int, int]]:
    """``(row, logical note, vol)`` の列。16 row（4/4）基準の型を measure の行数に比例させる。"""
    root = chord.bass
    fifth = fold_into_range(root + 7, *register)
    octave = root + 12 if root + 12 <= register[1] + 12 else root
    scale = rows / 16.0

    def at(r16: float) -> int:
        return min(rows - 1, int(round(r16 * scale)))

    if kind == "whole":
        return [(0, root, vol)]
    if kind == "half":
        return [(0, root, vol), (at(8), fifth if rng.random() < 0.4 else root, vol - 4)]
    if kind == "root8":
        return [(at(r), root, vol if r % 4 == 0 else vol - 8) for r in range(0, 16, 2)]
    if kind == "octave8":
        return [(at(r), root if (r // 2) % 2 == 0 else fold_into_range(root + 12, register[0], register[1] + 12),
                 vol if r % 4 == 0 else vol - 6) for r in range(0, 16, 2)]
    if kind == "offbeat":
        return [(at(r), root, vol) for r in (2, 6, 10, 14)]
    if kind == "rootfifth":
        return [(0, root, vol), (at(8), fifth, vol - 4)]
    if kind == "bossa":
        return [(0, root, vol), (at(6), fifth, vol - 6), (at(8), fifth, vol - 4), (at(14), root, vol - 8)]
    if kind == "walking":
        tones = sorted({t % 12 for t in chord.chord_tones})
        third = fold_into_range(root + ((tones[1] - root) % 12 if len(tones) > 1 else 4), *register)
        approach = fold_into_range(root + (1 if rng.random() < 0.5 else -1) + 7, *register)
        return [(at(0), root, vol), (at(4), third, vol - 6), (at(8), fifth, vol - 4), (at(12), approach, vol - 8)]
    if kind == "synco16":
        pat = [(0, root), (3, octave), (6, root), (8, fifth), (11, octave), (14, root)]
        return [(at(r), fold_into_range(n, register[0], register[1] + 12), vol if r in (0, 8) else vol - 8)
                for r, n in pat if r in (0, 8) or rng.random() < 0.75]
    if kind == "boombap":
        return [(0, root, vol), (at(3), root, vol - 10), (at(10), fifth if rng.random() < 0.5 else root, vol - 4)]
    if kind == "pulse16":
        b2 = fold_into_range(root + 1, *register)
        cycle = (root, root, b2, root, fifth, root, b2, root)
        return [(r, cycle[i % len(cycle)], vol if r % 4 == 0 else vol - 10) for i, r in enumerate(range(0, rows))]
    if kind == "house":
        return [(at(r), n, vol if r == 0 else vol - 6)
                for r, n in ((0, root), (3, octave), (7, root), (10, fifth), (14, root))]
    raise PlanError(f"unknown bass kind: {kind!r}")


def comp_rows(kind: str, rows: int, rng) -> list[tuple[int, bool]]:
    """和音を鳴らす ``(row, 強勢か)`` の列。16 row 基準の型を measure の行数に比例させる。"""
    scale = rows / 16.0

    def at(r16: float) -> int:
        return min(rows - 1, int(round(r16 * scale)))

    table = {
        "whole": [(0, True)],
        "half": [(0, True), (8, False)],
        "pulse4": [(0, True), (4, False), (8, True), (12, False)],
        "pulse8": [(r, r % 8 == 0) for r in range(0, 16, 2)],
        "offbeat": [(r, True) for r in (2, 6, 10, 14)],
        "charleston": [(0, True), (6, False)],
        "strum": [(0, True), (4, True), (6, False), (10, False), (12, True), (14, False)],
        "bossa": [(0, True), (3, False), (6, False), (10, True), (12, False)],
        "stab2": [(3, True), (10, True)],
        "arp8": [(r, r % 8 == 0) for r in range(0, 16, 2)],
        "arp16": [(r, r % 4 == 0) for r in range(16)],
        "fingerpick": [(r, r % 4 == 0) for r in range(0, 16, 2)],
    }
    if kind == "cutting16":
        return [(at(r), r in (4, 12)) for r in range(16) if r in (4, 12) or rng.random() < 0.55]
    if kind not in table:
        raise PlanError(f"unknown comp kind: {kind!r}")
    return [(at(r), a) for r, a in table[kind]]


def echo(pattern: Pattern, src: int, dst: int, delay: int, ratio: float, repeats: int = 1) -> None:
    """``src`` の発音を ``delay`` row 遅らせ、音量を ``ratio`` 倍にして ``dst`` の空き row に書く（残響の代わり）。"""
    for row in range(pattern.rows):
        cell = pattern.get(row, src)
        if cell.note is None or not cell.sample:
            continue
        vol = cell.vol if cell.vol is not None else 40
        for k in range(1, repeats + 1):
            r = row + delay * k
            if r >= pattern.rows:
                break
            if pattern.get(r, dst).is_empty:
                v = max(1, round(vol * ratio ** k))
                pattern.replace(r, dst, Cell(cell.note, cell.sample, vol=v))


def reserve_row0(pattern: Pattern, need: int) -> None:
    """曲の先頭 row 0 に、テンポ（とスウィング）のコマンドを書く空きチャンネルを ``need`` 個作る。

    足りなければ番号の大きいチャンネル（パッド・効果音など、後ろのチャンネルほど重要度が低い並び）から
    row 0 の音を row 1 へ（空いていれば）移し、空いていなければ消す。"""
    def empties() -> int:
        return sum(1 for c in range(pattern.channels) if pattern.get(0, c).is_empty)

    for ch in reversed(range(pattern.channels)):
        if empties() >= need:
            return
        cell = pattern.get(0, ch)
        if cell.is_empty:
            continue
        if pattern.rows > 1 and pattern.get(1, ch).is_empty:
            pattern.replace(1, ch, cell)
        pattern.replace(0, ch, Cell())


# ============================================================
# GM 音色の既定値（DESIGN.md §12.4）
# ============================================================

def _gm(**kw) -> GmVoice:
    return GmVoice(**kw)


GM_DEFAULTS: dict[str, GmVoice] = {
    # 既存プリセット（Patch 名）
    "LoFiKick": _gm(drum_note=36), "SoftSnare": _gm(drum_note=38), "ClosedHH": _gm(drum_note=42),
    "WarmBass": _gm(program=33), "MusicBox": _gm(program=10), "TwilightPad": _gm(program=89),
    "MellowFlute": _gm(program=73), "ProgKick": _gm(drum_note=36), "ProgSnare": _gm(drum_note=38),
    "ProgBassDist": _gm(program=34), "ProgGtrPower": _gm(program=29), "ProgLeadGtr": _gm(program=30),
    "CrashCymbal": _gm(drum_note=49), "MarchBassDrum": _gm(drum_note=36), "MarchSnare": _gm(drum_note=38),
    "TubaBass": _gm(program=58), "BrassHorn": _gm(program=60), "BrassSection": _gm(program=61),
    "PiccoloLead": _gm(program=72), "SwingRide": _gm(drum_note=51), "SwingBrushSnare": _gm(drum_note=38),
    "SwingWalkBass": _gm(program=32), "SwingPianoComp": _gm(program=0), "SwingSaxLead": _gm(program=65),
    "FbKick": _gm(drum_note=36), "FbSub": _gm(program=38), "FbSupersaw": _gm(program=81),
    "FbVocalChop": _gm(program=53), "FbClap": _gm(drum_note=39), "Trap808": _gm(program=38),
    "TrapSnareClap": _gm(drum_note=40), "TrapHatClosed": _gm(drum_note=42), "TrapHatOpen": _gm(drum_note=46),
    "TrapLeadPluck": _gm(program=80), "OrchViolin": _gm(program=48), "OrchViola": _gm(program=48),
    "OrchCello": _gm(program=42), "OrchBassStr": _gm(program=43), "OrchTrumpet": _gm(program=56),
    "OrchTimpani": _gm(program=47), "FreeCymbalSwell": _gm(program=119), "FreeArcoBass": _gm(program=43),
    "LowDroneBass": _gm(program=38), "TensionStrings": _gm(program=49), "PizzStab": _gm(program=45),
    "MaqamNay": _gm(program=77), "SubHeartbeat": _gm(drum_note=35), "NoiseSwoosh": _gm(program=122),
    "MetalAnvil": _gm(program=14), "ScreamingLead": _gm(program=81), "MinMarimba": _gm(program=12),
    "MinVibraphone": _gm(program=11), "MinPianoPulse": _gm(program=0), "MinWoodblock": _gm(drum_note=76),
    # 第３段階の共有音色
    "PopKick": _gm(drum_note=36), "PopSnare": _gm(drum_note=38), "GatedSnare": _gm(drum_note=40),
    "Kick909": _gm(drum_note=36), "Hat909": _gm(drum_note=42), "OpenHat909": _gm(drum_note=46),
    "Rimshot": _gm(drum_note=37), "Tom": _gm(drum_note=45), "BoomBapKick": _gm(drum_note=36),
    "BoomBapSnare": _gm(drum_note=38), "Shaker": _gm(drum_note=70), "Tambourine": _gm(drum_note=54),
    "Conga": _gm(drum_note=63), "Clave": _gm(drum_note=75), "CajonLow": _gm(drum_note=36),
    "CajonSlap": _gm(drum_note=38), "Surdo": _gm(drum_note=35), "Taiko": _gm(program=116),
    "Stomp": _gm(drum_note=35), "FingerBass": _gm(program=33), "SlapBass": _gm(program=36),
    "PickBass": _gm(program=34), "SawBass": _gm(program=38), "SquareBass": _gm(program=39),
    "DeepBass": _gm(program=38), "Piano": _gm(program=0), "ElectricPiano": _gm(program=4),
    "Organ": _gm(program=16), "Bell": _gm(program=9), "Harp": _gm(program=46), "HouseStab": _gm(program=16),
    "AcousticGtr": _gm(program=25), "NylonGtr": _gm(program=24), "CuttingGtr": _gm(program=28),
    "CleanGtr": _gm(program=27), "CrunchGtr": _gm(program=29), "SawLead": _gm(program=81),
    "SquareLead": _gm(program=80), "SynthPluck": _gm(program=84), "ArpBell": _gm(program=98),
    "SynthBrass": _gm(program=62), "SynthStab": _gm(program=62), "PolyPad": _gm(program=90),
    "GlassPad": _gm(program=88), "WarmPad": _gm(program=89), "VoxOoh": _gm(program=53),
    "Choir": _gm(program=52), "Flute": _gm(program=73), "Spiccato": _gm(program=48),
    "Braam": _gm(program=61), "VinylNoise": _gm(program=122), "Rain": _gm(program=122),
    "Riser": _gm(program=97), "Impact": _gm(program=55),
}


def gm_default(patch: Patch) -> GmVoice:
    """音色の Patch 名から GM 音色の既定値を引く（無ければ例外。推測はしない）。"""
    try:
        return GM_DEFAULTS[patch.name]
    except KeyError:
        raise PlanError(f"no GM voice for patch {patch.name!r}; declare it in the genre's GM") from None


def preset(key: str, **changes) -> Patch:
    """プリセットを名前で引き、必要なら ``dataclasses.replace`` で差分を当てる。"""
    p = PRESETS[key]
    return dataclasses.replace(p, **changes) if changes else p
