"""依存の規則（DESIGN.md §10.1 I8）の検査。``ast`` でモジュールの import 文を調べる。

``mod_weaver/framework/`` 自身（``framework/realize/`` を除く）が ``core`` の形式系（writer・s3m・it・
midi・render・verify・level）を import しないことを確かめる。``framework/realize/`` は Realizer そのもの
なので対象外（F3 で実装。意図的に形式系を import する）。``genres/*.py`` 側の検査（新しい ``Genre`` を
使うジャンルが同じ規則を守ること）は、そのジャンルが実際に書き直される F6・F7 で対象ファイルを広げる
（今はまだ旧 ``GenreProfile`` のジャンルしか無く、旧ジャンルはこの規則の対象外）。
"""
from __future__ import annotations

import ast
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2] / "mod_weaver"
FRAMEWORK_DIR = ROOT / "framework"

FORBIDDEN_CORE_MODULES = {"writer", "s3m", "it", "midi", "render", "verify", "level"}


def _forbidden_imports(path: pathlib.Path) -> list[str]:
    """このファイルの import 文のうち、``FORBIDDEN_CORE_MODULES`` のどれかを対象にしているものの一覧
    （相対 import・絶対 import・``from X import Y`` のどの書き方でも検出する）。"""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if any(p in FORBIDDEN_CORE_MODULES for p in alias.name.split(".")):
                    found.append(f"import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module_parts = (node.module or "").split(".")
            if any(p in FORBIDDEN_CORE_MODULES for p in module_parts):
                found.append(f"from {'.' * node.level}{node.module or ''} import ...")
            for alias in node.names:
                if alias.name in FORBIDDEN_CORE_MODULES:
                    found.append(f"from {'.' * node.level}{node.module or ''} import {alias.name}")
    return found


def _framework_py_files() -> list[pathlib.Path]:
    return sorted(p for p in FRAMEWORK_DIR.rglob("*.py") if "realize" not in p.parts)


@pytest.mark.parametrize("path", _framework_py_files(), ids=lambda p: str(p.relative_to(ROOT)))
def test_framework_does_not_import_core_format_modules(path: pathlib.Path) -> None:
    bad = _forbidden_imports(path)
    assert not bad, f"{path.relative_to(ROOT)} imports forbidden core format module(s): {bad}"


def test_framework_realize_package_is_excluded_and_not_empty() -> None:
    """``framework/realize/`` は Realizer 自身なので、上の検査の対象外（I8 の例外）。空のまま
    放置されていないことだけ確認する（実際に形式系を import するかどうかは Realizer の設計次第。
    ``tracker.py`` は ``RealizedSong`` を作るところまでが責務で、実際の serialize/verify/write は
    呼び出し側（``engine``）が ``core.native`` に任せているため、``writer``/``level`` 等を直接 import する義務は無い）。"""
    realize_files = sorted((FRAMEWORK_DIR / "realize").glob("*.py"))
    assert realize_files
