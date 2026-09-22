"""``python -m mod_weaver``（cli.main へ委譲）。"""
import sys

from .cli import main

sys.exit(main())
