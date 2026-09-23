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
    """奇数長・loop 範囲外・整数周期違反・ASCII 違反・長さ超過。

    より広くは、``core/synth.py`` の ``Patch``/``Layer`` や ``core/groove.py`` の ``SwingConfig`` 等、
    構築時に自身のフィールド範囲を検査する設定用データクラス・ヘルパー関数の「宣言が構築不能」
    エラー全般に使う（Cell 単体の矛盾は ``CellConflictError``、pattern/plan 全体の構造不整合は
    ``PlanError`` と使い分ける）。"""


class TempoRangeError(ModGenError):
    """``--tempo`` の要求範囲がジャンルの許容範囲（``GenreProfile.tempo_range``）と重ならない。"""


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


class ExternalToolError(ModGenError):
    """必要な外部ツール（mp3 出力の ffmpeg）が無い・機能不足・実行失敗。"""
