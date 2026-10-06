"""歌声のパート（VOCAL_DESIGN.md §4.3）。``Lead`` と同じ旋律に、音節（P3 は母音だけのヴォカリーズ）を流し込む。

声の源（``--voice``）には問い合わせない。音節は決定的に割り当てる（旋律の乱数は ``Lead`` と同じく動機・旋律にだけ使う）ので、
声の源や母音を変えても音符の時刻・高さは変わらない（V-4）。このパートは ``Part.requires=frozenset({"voice"})`` で宣言する。
"""
from __future__ import annotations

import logging
from typing import Mapping, Optional, Sequence

from ...core.composer import RhythmMotif, ScaleRules
from ...voice.phoneme import KANA_OF_VOWEL, Syllable, vowel_syllable
from ..context import Generator, MeasureCtx, SectionCtx
from ..score import Glide, NoteEvent, Vibrato
from .lead import Lead

log = logging.getLogger(__name__)


class Vocalise(Lead):
    """母音だけで歌う旋律。``vowels`` を音符ごとに循環する（既定は「あ」）。"""

    def __init__(self, inst: str, rules: ScaleRules, motifs: Mapping[str, tuple[RhythmMotif, ...]],
                 vol: int = 40, gate: float = 0.9, *, vibrato: int = 0x35, vowels: Sequence[str] = ("あ",)) -> None:
        super().__init__(inst, rules, motifs, vol, gate, vibrato=vibrato)
        self.syls = tuple(vowel_syllable(v) for v in vowels)

    def section(self, ctx: SectionCtx) -> None:
        ctx.state["syl_i"] = 0           # 区間ごとに先頭の母音から（区間を繰り返しても同じ歌になる）
        super().section(ctx)

    def measure(self, m: MeasureCtx) -> None:
        for e in self._bar_events(m):
            dur = max(1, round(e.dur * self.gate))
            arts = (Vibrato(self.vibrato, at=2),) if (self.vibrato and e.dur >= 6) else ()
            syl = self.syls[m.state["syl_i"] % len(self.syls)]
            m.state["syl_i"] += 1
            m.note(e.row, self.inst, e.note, vel=e.vol, dur=dur, arts=arts, syl=syl)


class Sing(Generator):
    """別パート（既定は ``lead``）の旋律を歌う（島唄・演歌のように、歌と楽器が同じ旋律をなぞる型）。装飾の短い音（``min_dur`` 未満）は
    歌わない。しゃくり（``Glide``）は引き継ぐ（ビブラートは声のサンプルに焼き込んであるので引き継がない）。母音は ``vowels`` を音符ごとに循環し、**区間の先頭から数え直す**。
    ``Part(..., depends=(source,), requires=frozenset({"voice"}))`` で宣言する。"""

    def __init__(self, inst: str, *, source: str = "lead", vowels: Sequence[str] = ("あ",), min_dur: int = 2,
                 vel_ratio: float = 1.0) -> None:
        self.inst = inst
        self.source = source
        self.syls = tuple(vowel_syllable(v) for v in vowels)
        self.min_dur = min_dur
        self.vel_ratio = vel_ratio

    def section(self, ctx: SectionCtx) -> None:
        notes = sorted((e for e in ctx.events_of(self.source) if isinstance(e, NoteEvent) and e.pitch is not None
                        and not e.chord and (e.dur is None or e.dur >= self.min_dur)), key=lambda e: e.step)
        lyrics = ctx.song.extra.get("lyrics")
        queue = self._queue(ctx, lyrics) if lyrics is not None else None
        if queue is None:
            sung = [(e, self.syls[i % len(self.syls)], e.dur) for i, e in enumerate(notes)]
        else:
            sung, used = self._assign(notes, queue)
            if lyrics.by_section:
                left = sum(1 for x in queue[used:] if x is not None and x.kind != "geminate")
                if left:
                    log.warning("lyrics for section %r: %d syllable(s) do not fit the melody and are dropped",
                                ctx.plan.name, left)
            else:
                ctx.song_state["lyric_pos"] = ctx.song_state.get("lyric_pos", 0) + used
        for e, syl, dur in sung:
            arts = tuple(a for a in e.arts if isinstance(a, Glide))    # ビブラートはサンプルに焼き込み済み
            vel = None if e.vel is None else max(1, min(64, round(e.vel * self.vel_ratio)))
            ctx.note(e.step, self.inst, e.pitch, vel, dur=dur, arts=arts, syl=syl)

    # ---- 歌詞（VOCAL_DESIGN.md §4.3）----
    def _queue(self, ctx: SectionCtx, lyrics) -> Optional[list]:
        """この区間で歌う音節列（``None`` は休符）。歌詞が無い区間は ``None``（ヴォカリーズ）。"""
        name = ctx.plan.name
        if lyrics.by_section:
            return list(lyrics.by_section[name]) if name in lyrics.by_section else None
        pos = ctx.song_state.get("lyric_pos", 0)             # 区間を指定しない歌詞: 歌う区間へ出現順に流し込む
        if pos >= len(lyrics.stream):
            return None
        return list(lyrics.stream[pos:])

    def _assign(self, notes: list[NoteEvent], queue: list):
        """音符へ音節を割り当てる（乱数なし）。1音符＝1音節。休符 ``None`` は音符を1つ飛ばし、促音は直前の音符を1 step 詰め、
        長音は同じ母音の音符にする。音節が尽きたら残りの音符は歌わない（同じ母音の連打になるメリスマにはしない。VOCAL_DESIGN.md §4.3）。
        戻り値は (音符, 音節, dur) の列と、使った音節数。"""
        out: list[list] = []          # [event, syl, dur]
        i = 0
        for idx, e in enumerate(notes):
            while i < len(queue) and queue[i] is not None and queue[i].kind == "geminate":
                if out:
                    prev = out[-1]
                    pdur = prev[2] if prev[2] is not None else max(1, e.step - prev[0].step)
                    prev[2] = max(1, pdur - 1) if pdur > 1 else pdur
                i += 1
            if i >= len(queue):                                     # 歌詞が尽きた: 残りの音符は歌わない
                break
            syl = queue[i]
            i += 1
            if syl is None:                                         # 休符: この音符は歌わない
                continue
            if syl.kind == "extend":
                syl = _vowel_of(syl)
            out.append([e, syl, e.dur])
        return [tuple(x) for x in out], i

def _vowel_of(syl: Syllable) -> Syllable:
    """子音を除いた母音だけの音節（長音・メリスマ用）。"""
    kana = KANA_OF_VOWEL.get(syl.nucleus, "ん")
    return Syllable(kana, syl.lang, nucleus=syl.nucleus)
