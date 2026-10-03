"""ジャンルモジュール置き場（DESIGN.md §5.6）。

ここに置いた ``.py``（``_`` で始まるものを除く）は ``framework.registry.discover()`` が起動時にすべて import する。
1ファイル＝1ジャンルで、``@register_genre`` 付きの ``framework.genre.Genre`` サブクラスを1つ定義すること。
ジャンルの共通部分（ジャンルではないもの）は ``_`` 始まりのモジュール（``_suspense.py`` など）に置く。
"""
