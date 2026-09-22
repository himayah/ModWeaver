"""Phase 0 完了条件: 凍結した参照実装のスモークテスト。"""
from __future__ import annotations

from tests.conftest import REFERENCE_SHA256, legacy_mod_bytes, reference_sha256, REGRESSION_SEEDS


def test_reference_is_frozen():
    assert reference_sha256() == REFERENCE_SHA256


def test_reference_generates_valid_mod():
    data = legacy_mod_bytes(42)
    assert data[1080:1084] == b"M.K."
    assert len(data) > 1084


def test_reference_is_deterministic():
    from tests.conftest import load_reference
    import contextlib, io, tempfile, os
    ref = load_reference()
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "x.mod")
        with contextlib.redirect_stdout(io.StringIO()):
            ref.build_procedural_mod(path=p, seed=42)
        assert open(p, "rb").read() == legacy_mod_bytes(42)


def test_regression_seed_count():
    assert len(REGRESSION_SEEDS) == 20
