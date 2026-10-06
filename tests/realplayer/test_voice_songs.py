"""歌声つきの曲を実プレイヤー（libopenmpt）で再生する（DESIGN.md §13.6.5・DESIGN_HISTORY.md §17.5 R3）: 音割れしない・歌声が鳴っている・
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
@pytest.mark.parametrize("fmt", ["it", "xm", "s3m"])
@pytest.mark.parametrize("gid", GENRES)
def test_voice_song_does_not_clip_and_is_not_much_quieter(gid, fmt, seed):
    g = engine.get_genre(gid)
    with_v = peak(engine.build(g, seed, fmt, voice="formant").data, f".{fmt}")
    without = peak(engine.build(g, seed, fmt).data, f".{fmt}")
    # R3: 約 -3 dB 以内。XM はマスター音量が無く、声（音量 64・サンプルのピーク 0.85 が上限で、ミキサーが 1 チャンネルぶんしか
    # 通さない）を前に出すために他パートを下げた分（Part.ducks）を持ち上げられないので、約 -8 dB まで許す
    # （バランスは直してあり、音量はプレイヤー側で補える。DESIGN.md §13.6.5・DESIGN_HISTORY.md §17.4.5）
    lo, floor = (0.2, 0.4) if fmt == "xm" else (0.3, 0.7)
    assert lo < with_v < 1.0, f"{gid} {fmt} {seed}: peak {with_v:.3f}"
    assert with_v > without * floor, f"{gid} {fmt} {seed}: voice {with_v:.3f} vs plain {without:.3f}"


@pytest.mark.parametrize("fmt", ["it", "s3m"])
@pytest.mark.parametrize("gid", GENRES)
def test_voice_is_audible(gid, fmt, bank):
    g = engine.get_genre(gid)
    plain = decode(engine.build(g, 2, fmt).data, f".{fmt}")
    for kw in ({"voice": "formant"}, {"voice": "tb", "voices_dir": str(bank.parent)}):
        sung = decode(engine.build(g, 2, fmt, **kw).data, f".{fmt}")
        n = min(len(plain.samples), len(sung.samples))
        diff = sum((a - b) ** 2 for a, b in zip(plain.samples[:n], sung.samples[:n])) / n
        assert diff ** 0.5 > 300, f"{gid} {kw}: voice not audible (rms diff {diff ** 0.5:.0f})"


@pytest.mark.parametrize("fmt", ["it", "s3m"])
def test_choir_is_audible_and_does_not_clip(fmt):
    from tests.voice.test_choir import _choir_genre
    base = engine.build(engine.get_genre("enka"), 3, fmt, voice="formant").data
    with_choir = engine.build(_choir_genre(), 3, fmt, voice="formant").data
    assert 0.3 < peak(with_choir, f".{fmt}") < 1.0
    a, b = decode(base, f".{fmt}"), decode(with_choir, f".{fmt}")
    n = min(len(a.samples), len(b.samples))
    diff = sum((x - y) ** 2 for x, y in zip(a.samples[:n], b.samples[:n])) / n
    assert diff ** 0.5 > 300, f"choir not audible (rms diff {diff ** 0.5:.0f})"
