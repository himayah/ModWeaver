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


TRACKER_FORMATS = ["xm", "s3m"]


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
