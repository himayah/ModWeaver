"""新しい枠組み（``framework/``）で書き直したジャンルの置き場所（FRAMEWORK_REDESIGN.md §15・§16.8）。

F6〜F7 の間だけ旧 ``mod_weaver/genres/``（``GenreProfile``）と並べて置く。旧版との「編成の対応表」テスト（§15.1）が
旧クラスと新しいクラスを同じプロセスで読む必要があるため。F8 で旧 ``genres/`` を削除し、このパッケージを
``genres/`` に改名する。1ファイル＝1ジャンル。``framework.registry.discover("mod_weaver.genres_next")`` が登録を起こす。
"""
