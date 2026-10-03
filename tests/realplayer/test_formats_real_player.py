"""--format の各形式を実プレイヤー（libopenmpt）で再生し、MOD（4ch）／XM（8ch）の再生と
音高・長さ・音量包絡が一致することを検査する（DESIGN.md §9.2「形式間の等価性」）。"""
import pytest

from mod_weaver import engine
from tests.realplayer import correlation, decode, requires_openmpt

pytestmark = requires_openmpt

FOUR_CH = ["nostalgic", "suspense-slow", "trap", "swing-jazz", "maqam", "prog-rock"]   # グライド・スウィング・微分音・可変拍子を含む


def render(genre, fmt, seed=123456):
    return decode(engine.build(engine.get_genre(genre), seed, fmt).data, f".{fmt}")


def assert_equivalent(ref, other, *, envelope=0.75):
    assert other.stderr == ""
    assert abs(other.seconds - ref.seconds) <= 0.01 * ref.seconds + 0.1, (ref.seconds, other.seconds)
    # 音高の精度は I4（tests/realplayer/test_f4_formats.py）が楽器ごとに測る。曲全体の零交差の平均は、XM・IT・S3M の高レートの
    # サンプルが高域を多く含むので MOD とは一致しない（周波数で比べず、長さと音量包絡で見る）。
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
    left, right = decode(engine.build(engine.get_genre("nostalgic"), 123456, fmt).data, f".{fmt}", stereo=True)
    diff = sum(abs(a - b) for a, b in zip(left.samples, right.samples)) / len(left.samples)
    assert diff > 0.1 * left.rms(), "left and right are (almost) identical: panning not applied"


def _vibrato_song(fmt):
    """ループした正弦波に 4xy をかけ続けるだけの合成曲（ビブラート深さの形式間比較用）。"""
    import math

    from mod_weaver.core.model import SampleSpec
    from mod_weaver.core.native import RCell
    from mod_weaver.framework.realize.encode import Codec
    from tests.realplayer.test_f4_effects import REF_NOTE, _song

    from mod_weaver.core import dsp
    from mod_weaver.core.pitch import PERIODS

    codec = Codec(fmt)
    bits = 8 if fmt in ("mod", "s3m") else 16
    scale = 100 if bits == 8 else 25600
    pack = (lambda v: (v & 0xFF).to_bytes(1, "little")) if bits == 8 else (lambda v: (v & 0xFFFF).to_bytes(2, "little"))
    data = b"".join(pack(round(scale * math.sin(2 * math.pi * i / 32))) for i in range(64))
    # どの形式も同じ実音（MOD の note 12＝period 428 の再生レート）で鳴らす。ビブラートの深さは period の絶対量なので、
    # 基準の音高が違うと相対的な深さが変わってしまう
    rate = dsp.CLOCK / PERIODS[12]
    spec = SampleSpec("Sine", data, 64, loop=(0, len(data) // 2), rate_note=12, rate_hz=rate, bits=bits)
    note = 12 if fmt == "mod" else codec.n_ref
    cells = {(0, 0): RCell(note=note, sample=1, vol=None if fmt == "mod" else 64, fx=codec.vibrato(0x48))}
    cells.update({(r, 0): RCell(fx=codec.vibrato(0x48)) for r in range(1, 60)})
    return _song(fmt, cells, spec=spec)


def _freq_spread(d):
    """正方向ゼロ交差の補間間隔から瞬時周波数を求め、5%〜95% 点を返す。"""
    a = d.samples[len(d.samples) // 10:len(d.samples) // 2]
    xs = [i - 1 + (-a[i - 1]) / (a[i] - a[i - 1]) for i in range(1, len(a)) if a[i - 1] < 0 <= a[i]]
    fs = sorted(22050 / (xs[k + 1] - xs[k]) for k in range(len(xs) - 1))
    return fs[len(fs) // 20], fs[len(fs) * 19 // 20]


@pytest.mark.parametrize("fmt", TRACKER_FORMATS)
def test_vibrato_depth_matches_mod(fmt):
    """IT は Old Effects=1 で MOD と同じ深さになる（0 だと半分。実測で確認した）。"""
    from mod_weaver.core import native

    lo_ref, hi_ref = _freq_spread(decode(native.serialize(_vibrato_song("mod")), ".mod"))
    lo, hi = _freq_spread(decode(native.serialize(_vibrato_song(fmt)), f".{fmt}"))
    depth_ref, depth = (hi_ref - lo_ref) / ((hi_ref + lo_ref) / 2), (hi - lo) / ((hi + lo) / 2)   # 基準の音高が形式で違うので比で
    assert abs(depth - depth_ref) <= 0.25 * depth_ref, ((lo_ref, hi_ref), (lo, hi))
