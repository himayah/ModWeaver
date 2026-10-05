"""歌声つきの曲を実プレイヤー（libopenmpt）で再生する（VOCAL_DESIGN.md P3・R3）: 音割れしない・歌声が鳴っている・
音量が歌声なしの曲と大きくは違わない。"""
import pytest

from mod_weaver import engine
from mod_weaver.voice.bank import importer, synthetic
from tests.realplayer import decode, peak, requires_openmpt

pytestmark = requires_openmpt
GENRES = ["okinawan", "enka", "mood-kayo"]


@pytest.fixture(scope="module")
def bank(tmp_path_factory):
    d = tmp_path_factory.mktemp("rpv") / "tb"
    synthetic.make_test_bank(d)
    importer.import_bank(d)
    return d


@pytest.mark.parametrize("seed", [1, 2, 3])
@pytest.mark.parametrize("fmt", ["it", "xm"])
@pytest.mark.parametrize("gid", GENRES)
def test_voice_song_does_not_clip_and_is_not_much_quieter(gid, fmt, seed):
    g = engine.get_genre(gid)
    with_v = peak(engine.build(g, seed, fmt, voice="formant").data, f".{fmt}")
    without = peak(engine.build(g, seed, fmt).data, f".{fmt}")
    assert 0.3 < with_v < 1.0, f"{gid} {fmt} {seed}: peak {with_v:.3f}"
    assert with_v > without * 0.7, f"{gid} {fmt} {seed}: voice {with_v:.3f} vs plain {without:.3f}"   # R3: 約 -3 dB 以内


@pytest.mark.parametrize("gid", GENRES)
def test_voice_is_audible(gid, bank):
    g = engine.get_genre(gid)
    plain = decode(engine.build(g, 2, "it").data, ".it")
    for kw in ({"voice": "formant"}, {"voice": "tb", "voices_dir": str(bank.parent)}):
        sung = decode(engine.build(g, 2, "it", **kw).data, ".it")
        n = min(len(plain.samples), len(sung.samples))
        diff = sum((a - b) ** 2 for a, b in zip(plain.samples[:n], sung.samples[:n])) / n
        assert diff ** 0.5 > 300, f"{gid} {kw}: voice not audible (rms diff {diff ** 0.5:.0f})"
