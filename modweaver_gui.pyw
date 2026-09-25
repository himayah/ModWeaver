"""ModWeaver の GUI の起動スクリプト。``python -m mod_weaver.gui`` と同機能。

Windows では ``modweaver_gui.bat`` のダブルクリックでコンソール窓なしに起動する（pythonw。
.pyw にアプリが関連付けられていれば .pyw のダブルクリックでも可）。ほかの OS では ``python3 modweaver_gui.pyw``。``--lang=en`` / ``--lang=ja`` で表示言語を指定できる。
"""
import sys

from mod_weaver.gui.app import main

if __name__ == "__main__":
    sys.exit(main())
