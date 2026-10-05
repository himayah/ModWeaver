"""歌声を使った曲のクレジット（``<出力>.credits.txt``。VOCAL_DESIGN.md §6.3・V-7）。法的な助言ではない。"""
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
