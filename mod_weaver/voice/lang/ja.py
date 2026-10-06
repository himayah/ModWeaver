"""日本語の歌詞の前段: かな（ひらがな・カタカナ・ローマ字）→ モーラ → ``Syllable``（VOCAL_DESIGN.md §4.1・§4.2）。

この層が知っているのは「かな → 音素」までで、声の源（UTAU の別名）は知らない。出力は ``Syllable`` と休符の印 ``None`` の列。
``Syllable.text`` は常にひらがな（ローマ字・カタカナで書いても正規化する）。母音の無声化・連母音の融合・アクセントは扱わない。
"""
from __future__ import annotations

import re
from typing import Optional

from ...errors import LyricsError
from ..phoneme import Syllable

REST_CHARS = set(" \t　、。，．,.!?！？…・")
RESERVED = set("{|}")                     # 将来のルビ記法 {夕焼け|ゆうやけ} のために予約
SMALL_VOWELS = {"ぁ": "a", "ぃ": "i", "ぅ": "M", "ぇ": "e", "ぉ": "o"}
SMALL_YA = {"ゃ": "a", "ゅ": "M", "ょ": "o"}
VOWELS = {"あ": "a", "い": "i", "う": "M", "え": "e", "お": "o"}

# 行 → (頭子音, かな5つ。あ・い・う・え・お段)。し・ち・つ・ふ・じ などは個別に onset を上書きする。
_ROWS = {
    "k": "かきくけこ", "s": "さしすせそ", "t": "たちつてと", "n": "なにぬねの", "h": "はひふへほ", "m": "まみむめも",
    "r": "らりるれろ", "g": "がぎぐげご", "z": "ざじずぜぞ", "d": "だぢづでど", "b": "ばびぶべぼ", "p": "ぱぴぷぺぽ",
}
_ONSET_OVERRIDE = {"し": "S", "ち": "tS", "つ": "ts", "じ": "dZ", "ぢ": "dZ", "づ": "dz", "ひ": "C", "ふ": "F"}
# 拗音の頭子音（き＋ゃ → ky+a。し・ち・じ は単独の onset のまま）
_YOUON_ONSET = {"き": "ky", "に": "ny", "ひ": "hy", "み": "my", "り": "ry", "ぎ": "gy", "び": "by", "ぴ": "py",
                "し": "S", "ち": "tS", "じ": "dZ", "ぢ": "dZ"}

MORA: dict[str, tuple[str, str]] = {}          # かな1文字 → (onset, nucleus)
for _k, _v in VOWELS.items():
    MORA[_k] = ("", _v)
for _c, _kana in _ROWS.items():
    for _ch, _v in zip(_kana, "aiMeo"):
        MORA[_ch] = (_ONSET_OVERRIDE.get(_ch, _c), _v)
MORA.update({"や": ("j", "a"), "ゆ": ("j", "M"), "よ": ("j", "o"), "わ": ("w", "a"), "ゐ": ("", "i"), "ゑ": ("", "e"),
             "を": ("", "o"), "ゔ": ("v", "M")})

# ---- ローマ字 → かな ----
_ROMAJI: dict[str, str] = {"a": "あ", "i": "い", "u": "う", "e": "え", "o": "お", "wo": "を", "nn": "ん"}
for _c, _kana in _ROWS.items():
    for _v, _ch in zip("aiueo", _kana):
        _ROMAJI[_c + _v] = _ch
for _c, _kana in {"y": "やいゆえよ", "w": "わゐうゑを"}.items():
    for _v, _ch in zip("aiueo", _kana):
        if _c + _v not in ("yi", "ye", "wu", "wi", "we", "wo"):
            _ROMAJI[_c + _v] = _ch
_ROMAJI.update({"wi": "うぃ", "we": "うぇ", "si": "し", "shi": "し", "ti": "ち", "chi": "ち", "tu": "つ", "tsu": "つ",
                "hu": "ふ", "fu": "ふ", "zi": "じ", "ji": "じ", "di": "ぢ", "du": "づ", "vu": "ゔ", "xn": "ん"})
for _pre, _base in {"ky": "き", "gy": "ぎ", "sh": "し", "sy": "し", "ch": "ち", "ty": "ち", "cy": "ち", "ny": "に", "hy": "ひ",
                    "my": "み", "ry": "り", "by": "び", "py": "ぴ", "j": "じ", "jy": "じ", "zy": "じ", "dy": "ぢ"}.items():
    for _v, _s in (("a", "ゃ"), ("u", "ゅ"), ("o", "ょ")):
        _ROMAJI[_pre + _v] = _base + _s
for _pre, _base in {"sh": "し", "ch": "ち", "j": "じ", "ts": "つ", "f": "ふ", "v": "ゔ", "w": "う"}.items():
    for _v, _s in (("a", "ぁ"), ("i", "ぃ"), ("e", "ぇ"), ("o", "ぉ")):
        _ROMAJI.setdefault(_pre + _v, _base + _s)
_ROMAJI["she"], _ROMAJI["che"], _ROMAJI["je"] = "しぇ", "ちぇ", "じぇ"
_ROMAJI["fa"], _ROMAJI["fi"], _ROMAJI["fe"], _ROMAJI["fo"] = "ふぁ", "ふぃ", "ふぇ", "ふぉ"
_ROMAJI["va"], _ROMAJI["vi"], _ROMAJI["ve"], _ROMAJI["vo"] = "ゔぁ", "ゔぃ", "ゔぇ", "ゔぉ"
_MAXLEN = max(map(len, _ROMAJI))
_LATIN = re.compile(r"[A-Za-z']+")


def _romaji_to_kana(run: str, line: int, col: int) -> str:
    s = run.lower()
    out: list[str] = []
    i = 0
    while i < len(s):
        c = s[i]
        if c == "'":
            i += 1
            continue
        nxt = s[i + 1] if i + 1 < len(s) else ""
        if c == "n" and nxt not in tuple("aiueoy"):    # ん（nn・n' は2文字で1つ。ただし nna の nn は ん＋な）
            out.append("ん")
            if nxt == "'" or (nxt == "n" and s[i + 2:i + 3] not in tuple("aiueoy")):
                i += 1
            i += 1
            continue
        if c == nxt and c not in "aiueon'":            # kk・tt・ss … → っ
            out.append("っ")
            i += 1
            continue
        for n in range(min(_MAXLEN, len(s) - i), 0, -1):
            kana = _ROMAJI.get(s[i:i + n])
            if kana:
                out.append(kana)
                i += n
                break
        else:
            raise LyricsError(f"line {line}: cannot read romaji {run!r} at {s[i:i + 3]!r} (column {col + i})")
    return "".join(out)


def normalize(text: str, line: int = 1) -> str:
    """カタカナ → ひらがな、ローマ字 → ひらがなにそろえる（ほかの文字はそのまま）。"""
    out: list[str] = []
    pos = 0
    for m in _LATIN.finditer(text):
        out.append(_kata(text[pos:m.start()]))
        out.append(_romaji_to_kana(m.group(), line, m.start() + 1))
        pos = m.end()
    out.append(_kata(text[pos:]))
    return "".join(out)


def _kata(s: str) -> str:
    return "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in s)


def parse_line(text: str, line: int = 1) -> list[Optional[Syllable]]:
    """1行を ``Syllable`` と休符の印 ``None`` の列にする。連続する休符は1つにまとめ、先頭の休符は捨てる。"""
    s = normalize(text, line)
    out: list[Optional[Syllable]] = []
    i = 0
    while i < len(s):
        c = s[i]
        if c in RESERVED:
            raise LyricsError(f"line {line}: {c!r} is reserved (ruby notation is not supported yet)")
        if c in REST_CHARS:
            if out and out[-1] is not None:
                out.append(None)
            i += 1
            continue
        if c == "っ":
            out.append(Syllable("っ", "ja", nucleus="", kind="geminate"))
            i += 1
            continue
        if c == "ー":
            prev = next((x for x in reversed(out) if x is not None), None)
            if prev is None or prev.kind == "geminate" or (out and out[-1] is None):
                raise LyricsError(f"line {line}: 'ー' needs a preceding syllable (column {i + 1})")
            out.append(Syllable("ー", "ja", nucleus=prev.nucleus, kind="extend"))
            i += 1
            continue
        if c == "ん":
            out.append(Syllable("ん", "ja", nucleus="N"))
            i += 1
            continue
        if c in MORA:
            onset, nuc = MORA[c]
            text_ = c
            nxt = s[i + 1] if i + 1 < len(s) else ""
            if nxt in SMALL_YA and c in _YOUON_ONSET:
                onset, nuc, text_ = _YOUON_ONSET[c], SMALL_YA[nxt], c + nxt
                i += 1
            elif nxt in SMALL_YA and c in "い":                      # いゃ などは扱わない
                raise LyricsError(f"line {line}: unsupported combination {c + nxt!r} (column {i + 1})")
            elif nxt in SMALL_VOWELS:
                base = {"い": "j", "う": "w"}.get(c, onset)
                onset, nuc, text_ = base, SMALL_VOWELS[nxt], c + nxt
                i += 1
            out.append(Syllable(text_, "ja", onset=(onset,) if onset else (), nucleus=nuc))
            i += 1
            continue
        if c == "\n":
            i += 1
            continue
        raise LyricsError(f"line {line}: cannot sing {c!r} (column {i + 1}); use hiragana, katakana or romaji")
    while out and out[-1] is None:
        out.pop()
    return out


def parse(text: str) -> list[Optional[Syllable]]:
    """複数行の歌詞。行の切れ目は音節の列としては区切りにしない（休符にしたい所は句読点か空白を書く）。"""
    out: list[Optional[Syllable]] = []
    for n, line in enumerate(text.splitlines(), 1):
        out.extend(parse_line(line, n))
    return _squash(out)


def _squash(items: list[Optional[Syllable]]) -> list[Optional[Syllable]]:
    out: list[Optional[Syllable]] = []
    for x in items:
        if x is None and (not out or out[-1] is None):
            continue
        out.append(x)
    while out and out[-1] is None:
        out.pop()
    return out
