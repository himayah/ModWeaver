# F0 実験（使い捨てスクリプト）

`FRAMEWORK_REDESIGN.md` §16.2 の F0（準備）フェーズで、§13.4 の要実測のうち最初の2行
（XM・IT の 16-bit サンプルと、任意の再生レートでの音高）を実装前に確かめたスクリプトと、
その実行結果。

- `f0_hires_pitch_experiment.py`: 16-bit の XM・IT ファイルを手組みで作り（`core/model.Cell` や
  既存の writer は使わない。現行の 36 音の制約を受けないことを確かめるのが目的なので）、
  libopenmpt（ffmpeg）で再生し、FFT（窓1秒・放物線補間）で実音を測る。
- `f0_hires_pitch_experiment.output.txt`: 実行結果。1件だけ `FAIL`（`it C5Speed=100 (re-check)`）
  があるが、これは測定方法ではなく実用上あり得ない値（本設計の `rate_hz` は常に数 kHz〜300 kHz
  の実用域）を試した結果で、設計への影響はない。詳細は `FRAMEWORK_REDESIGN.md` §13.4 の表。

結果のまとめは `FRAMEWORK_REDESIGN.md` §13.4 に転記済み。このディレクトリは記録として残すだけで、
F1 以降の実装はここのコードを再利用しない（本番の 16-bit 対応は `core/writer.py`・`core/it.py` に
正しく作り込む。§16.2 F4）。
