"""ModWeaver の音源管理コマンド（check / import / list / info / audition / make-test-bank）。DESIGN.md §13.7.2。"""
import sys

from mod_weaver.voice_cli import main

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
