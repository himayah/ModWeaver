"""出力の基準（tests/regression/golden.json）を作り直す。

    python tools/update_golden.py [ジャンル id ...]     # 省略時は全ジャンル

出力を意図して変えたときだけ実行し、そのコミットで理由を書く（tests/regression/golden_lib.py の docstring 参照）。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from mod_weaver import engine  # noqa: E402
from tests.regression import golden_lib  # noqa: E402


def main(argv: list[str]) -> int:
    genres = [engine.get_genre(a) for a in argv] if argv else engine.list_genres()
    data = golden_lib.load() if argv and golden_lib.GOLDEN_PATH.exists() else {}
    for g in genres:
        data[g.id] = golden_lib.hashes_for(g)
        print(f"{g.id}: {len(data[g.id])} outputs", flush=True)
    golden_lib.save(data)
    print(f"wrote {golden_lib.GOLDEN_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
