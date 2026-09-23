"""ジャンルモジュール置き場（DESIGN.md §5.6）。

ここに置いた ``.py``（``_`` で始まるものを除く）は ``profiles.registry.discover()`` が起動時にすべて import する。
1ファイル＝1ジャンルで、``@register_profile`` 付きの ``GenreProfile`` サブクラスを1つ定義すること。
補助モジュール（ジャンルではないもの）は ``mod_weaver/profiles/`` に置く。
"""
