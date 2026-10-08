"""歌声を使った曲のクレジット（``<出力>.credits.txt``。DESIGN.md §13.7.3・V-7）。法的な助言ではない。"""
from __future__ import annotations

from .. import __version__


def credits_text(info, genre, seed: int, fmt: str) -> str:
    lines = [f"ModWeaver {__version__}  genre={genre.id}  seed={seed}  format={fmt}", ""]
    if info.id == "formant":
        lines += ["Voice: formant (built into ModWeaver; no third-party voice samples)."]
    else:
        lines += [f"Voice: {info.id}  (fingerprint {info.fingerprint[:8]})",
                  f"Credit: {info.credit}" if info.credit else "Credit: (none required)",
                  f"Terms: {info.terms_url}" if info.terms_url else "Terms: (no URL recorded)",
                  f"Terms checked by the user: {'yes' if info.terms_checked else 'NO - please check the voice terms'}",
                  "",
                  "This song contains samples of the voice bank above. The bank's terms apply to publishing "
                  "and commercial use of the song. ModWeaver does not judge the terms."]
    return "\n".join(lines) + "\n"


def credits_message(info, genre, seed: int) -> str:
    """IT の曲メッセージ用の短いクレジット（ASCII のみ。日本語のクレジット文は ``.credits.txt`` を見るよう案内する）。"""
    lines = [f"ModWeaver {__version__}  genre={genre.id}  seed={seed}"]
    if info.id == "formant":
        lines.append("Voice: formant (built in; no third-party samples)")
    else:
        lines.append(f"Voice: {info.id}")
        credit = info.credit or ""
        lines.append(f"Credit: {credit}" if credit and credit.isascii() else
                     "Credit: see the .credits.txt next to this file" if credit else "Credit: (none required)")
        if info.terms_url and info.terms_url.isascii():
            lines.append(f"Terms: {info.terms_url}")
        lines.append("The voice bank's terms apply to publishing and commercial use.")
    return "\n".join(lines)
