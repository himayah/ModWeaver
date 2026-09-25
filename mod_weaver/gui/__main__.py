"""``python -m mod_weaver.gui``（app.main へ委譲）。"""
import sys

from .app import main

sys.exit(main())
