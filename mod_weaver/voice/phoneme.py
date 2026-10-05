"""音素と音節（言語共通。純データ。VOCAL_DESIGN.md §3.1）。genres・framework・realize のすべてが import してよい。"""
from __future__ import annotations

from dataclasses import dataclass

# 日本語の母音（X-SAMPA 風。う は M）と、ヴォカリーズで使うかな。前段（voice/lang/ja.py）は P4。
VOWEL_OF_KANA = {"あ": "a", "い": "i", "う": "M", "え": "e", "お": "o"}
KANA_OF_VOWEL = {v: k for k, v in VOWEL_OF_KANA.items()}


@dataclass(frozen=True)
class Syllable:
    text: str                       # 元の表記（表示・MIDI の歌詞・クレジットの確認用）。例 "か"
    lang: str = "ja"                # バンクの引き当て表を選ぶ鍵
    onset: tuple[str, ...] = ()     # 頭子音の音素列。母音だけなら空
    nucleus: str = "a"              # 核（母音、または音節性の鼻音 "N"）
    coda: tuple[str, ...] = ()      # 末尾子音（日本語は空）
    kind: str = "normal"            # "normal" | "geminate" | "extend"

    @property
    def key(self) -> str:
        """サンプルの鍵（onset+nucleus+kind。``lang`` は音源が1言語なので含めない）。"""
        return "".join(self.onset) + self.nucleus + ("" if self.kind == "normal" else f"~{self.kind}")


def vowel_syllable(kana: str) -> Syllable:
    """ヴォカリーズ用の母音の音節（``"あ"`` など）。"""
    if kana not in VOWEL_OF_KANA:
        raise ValueError(f"vocalise syllable must be one of {''.join(VOWEL_OF_KANA)}: {kana!r}")
    return Syllable(text=kana, nucleus=VOWEL_OF_KANA[kana])
