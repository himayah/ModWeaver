"""依存の規則（FRAMEWORK_REDESIGN.md §13.1 I8）の検査。``ast`` でモジュールの import 文を調べる。

``mod_weaver/framework/`` 自身が ``core`` の形式系（writer・s3m・it・midi・render・verify・level）と
``framework.realize``（まだ存在しない。F3 以降で作る）を import しないことを確かめる。``genres/*.py`` 側の
検査（新しい ``Genre`` を使うジャンルが同じ規則を守ること）は、そのジャンルが実際に書き直される F6・F7 で
対象ファイルを広げる（今はまだ旧 ``GenreProfile`` のジャンルしか無く、旧ジャンルはこの規則の対象外）。
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


def test_framework_realize_package_does_not_exist_yet() -> None:
    """F3 で ``framework/realize/`` を作ったら、このテストを更新してその中身も検査対象に含める。"""
    assert not (FRAMEWORK_DIR / "realize").exists(), (
        "framework/realize/ now exists -- extend this test's scope to include it per §13.1 I8"
    )
