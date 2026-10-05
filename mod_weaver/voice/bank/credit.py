"""``modweaver.json``（利用者が書く・音源ごとのクレジットと規約メモ。VOCAL_DESIGN.md §5.3.2）。
ModWeaver は規約の内容を判断しない。"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from ...errors import VoiceBankError

FILE = "modweaver.json"
ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")

TEMPLATE = {
    "id": "",
    "lang": "ja",
    "alias_style": "auto",
    "credit": "",
    "credit_required": True,
    "terms_url": "",
    "terms_checked": False,
    "notes": "",
    "alias_map": {},
}


@dataclass(frozen=True)
class VoiceMeta:
    id: str
    lang: str = "ja"
    alias_style: str = "auto"
    credit: str = ""
    credit_required: bool = True
    terms_url: str = ""
    terms_checked: bool = False
    notes: str = ""
    alias_map: dict = field(default_factory=dict)


def write_template(folder: Path) -> Path:
    path = folder / FILE
    tmpl = dict(TEMPLATE, id=folder.name if ID_RE.match(folder.name) else "")
    path.write_text(json.dumps(tmpl, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def load_meta(folder: Path, id_override: str = "") -> VoiceMeta:
    path = folder / FILE
    if not path.is_file():
        write_template(folder)
        raise VoiceBankError(f"{FILE} was missing; a template was created at {path}. "
                             f"Fill in 'credit' (and 'id' if the folder name is not ASCII), then import again.")
    try:
        d = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as e:
        raise VoiceBankError(f"{path}: {e}") from e
    vid = id_override or d.get("id") or folder.name
    if not ID_RE.match(vid):
        raise VoiceBankError(f"voice id {vid!r} must be ASCII letters, digits, '-' or '_' (use --id or set 'id' in {FILE})")
    required = bool(d.get("credit_required", True))
    credit = str(d.get("credit", "")).strip()
    if required and not credit:
        raise VoiceBankError(f"{path}: 'credit' is empty. Write the credit text, or set "
                             f"\"credit\": \"\" together with \"credit_required\": false if none is needed.")
    return VoiceMeta(id=vid, lang=str(d.get("lang", "ja")), alias_style=str(d.get("alias_style", "auto")),
                     credit=credit, credit_required=required, terms_url=str(d.get("terms_url", "")),
                     terms_checked=bool(d.get("terms_checked", False)), notes=str(d.get("notes", "")),
                     alias_map=dict(d.get("alias_map") or {}))
