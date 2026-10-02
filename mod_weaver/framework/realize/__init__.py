"""Score → 形式ネイティブなバイト列（FRAMEWORK_REDESIGN.md §9〜§11）。

- ``tracker.py``: TrackerRealizer（MOD・S3M・XM・IT。MP3 は IT の ``RealizedSong`` を ``core.render`` が変換）
- ``encode.py``: 形式ごとの奏法・音高・コマンドの表（``Codec``）
- ``lanes.py``・``samples.py``: lane と ladder、サンプルの計画と描画

書き出しは ``core.native.serialize(rs)``、検査は ``core.native.verify(fmt, data)``。MidiRealizer は F5。
"""
