"""--format の各形式を実プレイヤー（libopenmpt）で再生し、MOD（4ch）／XM（8ch）の再生と
音高・長さ・音量包絡が一致することを検査する（FORMAT_TEMPO_DESIGN §7「形式間の等価性」）。"""
import pytest

from mod_weaver import engine, profiles
from tests.realplayer import correlation, decode, requires_openmpt

pytestmark = requires_openmpt

FOUR_CH = ["nostalgic", "suspense-slow", "trap", "swing-jazz", "maqam", "prog-rock"]   # グライド・スウィング・微分音・可変拍子を含む


def render(genre, fmt, seed=123456):
    p = profiles.get_profile(genre)
    song, plan = engine.compose_song(p, seed)
    return decode(engine.serialize(p, song, plan, fmt), p and f".{fmt}")


def assert_equivalent(ref, other, *, envelope=0.8):
    assert other.stderr == ""
    assert abs(other.seconds - ref.seconds) <= 0.01 * ref.seconds + 0.1, (ref.seconds, other.seconds)
    f_ref, f_other = ref.mean_freq(0, 20), other.mean_freq(0, 20)
    assert abs(f_other - f_ref) <= 0.05 * f_ref, (f_ref, f_other)
    assert correlation(ref.envelope(), other.envelope()) > envelope


TRACKER_FORMATS = ["xm", "s3m", "it"]


@pytest.mark.parametrize("fmt", TRACKER_FORMATS)
@pytest.mark.parametrize("genre", FOUR_CH)
def test_format_matches_mod(genre, fmt):
    assert_equivalent(render(genre, "mod"), render(genre, fmt))


@pytest.mark.parametrize("fmt", ["mod"] + [f for f in TRACKER_FORMATS if f != "xm"])
def test_orchestral_plays_like_xm(fmt):
    """既定形式 mod では orchestral は 8CHN。パン以外は XM と同じ音で鳴る。"""
    assert_equivalent(render("orchestral", "xm"), render("orchestral", fmt))


@pytest.mark.parametrize("fmt", TRACKER_FORMATS)
def test_channel_pans_give_stereo_image_for_4ch_genre(fmt):
    """全サンプルが既定パンの 4ch ジャンルでも LRRL のステレオになる（XM: vol column Px、S3M/IT: ヘッダ）。"""
    p = profiles.get_profile("nostalgic")
    song, plan = engine.compose_song(p, 123456)
    left, right = decode(engine.serialize(p, song, plan, fmt), f".{fmt}", stereo=True)
    diff = sum(abs(a - b) for a, b in zip(left.samples, right.samples)) / len(left.samples)
    assert diff > 0.1 * left.rms(), "left and right are (almost) identical: panning not applied"


def _vibrato_song():
    """ループした正弦波に 4xy をかけ続けるだけの合成曲（ビブラート深さの形式間比較用）。"""
    import math

    from mod_weaver.core.model import Cell, Pattern, SampleSpec, Song

    data = bytes(round(100 * math.sin(2 * math.pi * i / 32)) & 0xFF for i in range(64))
    pat = Pattern(None, channels=4)
    pat.put(0, 0, Cell(12, 1, 0xF, 125))
    for r in range(1, 64):
        pat.put(r, 0, Cell(None, 0, 0x4, 0x48))
    return Song("Vib", [SampleSpec("Sine", data, 64, loop=(0, 32))], [pat], [0])


def _freq_spread(d):
    """正方向ゼロ交差の補間間隔から瞬時周波数を求め、5%〜95% 点を返す。"""
    a = d.samples[len(d.samples) // 10:len(d.samples) // 2]
    xs = [i - 1 + (-a[i - 1]) / (a[i] - a[i - 1]) for i in range(1, len(a)) if a[i - 1] < 0 <= a[i]]
    fs = sorted(22050 / (xs[k + 1] - xs[k]) for k in range(len(xs) - 1))
    return fs[len(fs) // 20], fs[len(fs) * 19 // 20]


@pytest.mark.parametrize("fmt", TRACKER_FORMATS)
def test_vibrato_depth_matches_mod(fmt):
    """IT は Old Effects=1 で MOD と同じ深さになる（0 だと半分。実測で確認した）。"""
    from mod_weaver.core import formats, writer

    song = _vibrato_song()
    opts = formats.WriteOptions(channel_pans=(128,) * 4, initial_bpm=125)
    lo_ref, hi_ref = _freq_spread(decode(writer.serialize(song), ".mod"))
    lo, hi = _freq_spread(decode(formats.get_format(fmt).serialize(song, opts), f".{fmt}"))
    assert abs((hi - lo) - (hi_ref - lo_ref)) <= 0.25 * (hi_ref - lo_ref), ((lo_ref, hi_ref), (lo, hi))
