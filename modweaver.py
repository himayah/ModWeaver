"""ModWeaver のトップレベル起動スクリプト。``python -m mod_weaver`` と同機能。

引数なしで起動すると usage を表示して終了する（``--help`` と同じ）。何か引数があって ``--genre`` を
省略した場合は既定の ``nostalgic`` を生成し、出力 .mod は旧実装（tests/reference/twilight_pad_v1.py、
旧 twilight_pad.py）とバイト単位で同一。
"""
import sys

from mod_weaver.cli import main

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:], prog="modweaver.py", invocation="python modweaver.py"))
