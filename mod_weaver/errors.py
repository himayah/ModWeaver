"""例外階層（設計書 §10.1）。"""
from __future__ import annotations

from typing import Any, Sequence


class ModGenError(Exception):
    """本パッケージが送出する例外の基底クラス。"""


class ProfileNotFoundError(ModGenError):
    """未登録の genre が指定された。"""


class PitchRangeError(ModGenError):
    """note が 0..35 外、音名パース失敗、アルペジオで上限超過。"""


class CellConflictError(ModGenError):
    """vol と effect の併用、param 範囲外など、Cell 単体の矛盾。"""


class ChannelConflictError(ModGenError):
    """同 row の衝突、許可外サンプル、テンポ挿入先なし。"""


class SampleConstraintError(ModGenError):
    """奇数長・loop 範囲外・整数周期違反・ASCII 違反・長さ超過。"""


class PlanError(ModGenError):
    """64 row 不一致、order 不正、pattern 数超過、tempo が tempo_choices 外。"""


class VerificationError(ModGenError):
    """verify が ERROR を検出した。"""

    def __init__(self, issues: Sequence[Any]):
        self.issues = list(issues)
        lines = "; ".join(f"{i.code}: {i.message}" for i in self.issues[:5])
        more = "" if len(self.issues) <= 5 else f" (+{len(self.issues) - 5} more)"
        super().__init__(f"verification failed: {lines}{more}")


class OutputError(ModGenError):
    """I/O 失敗（OSError をラップ）。"""
