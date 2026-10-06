"""歌声の audition（IT）を実プレイヤー（libopenmpt）で再生し、プリロール整列（DESIGN.md §13.6.3・R2）を実測する:
母音の頭（最初の音＋preutterance）が拍（クリック）から 1 tick（20 ms）以内に来る。"""
import pytest

from mod_weaver.voice.bank import audition, cache, importer, synthetic
from tests.realplayer import RATE, decode, requires_openmpt

pytestmark = requires_openmpt
TICK_S = audition.TICK_MS / 1000


@pytest.fixture(scope="module")
def bank(tmp_path_factory):
    d = tmp_path_factory.mktemp("rp") / "tb"
    synthetic.make_test_bank(d)
    info, _ = importer.import_bank(d)
    return d, info


@pytest.mark.parametrize("text", ["あいうえお", "かきくけこ", "さしすせそ", "まみむめもなにぬねの"])
def test_vowel_onset_lands_on_the_beat(bank, text):
    d, info = bank
    data, _ = audition.render(d, text)
    left, _ = decode(data, ".it", stereo=True)
    x = left.samples
    peak = max(abs(v) for v in x)
    step_rows = audition.ROWS_PER_BEAT * audition.BEATS_PER_SYLLABLE
    errors = []
    for n, ch in enumerate(text):
        beat = (step_rows + n * step_rows) * audition.SPEED * TICK_S
        j = next(i for i in range(int((beat - 0.25) * RATE), len(x)) if abs(x[i]) > 0.06 * peak)
        pre_s = info.syllables[ch].pre / info.rate
        errors.append(j / RATE + pre_s - beat)
    assert max(abs(e) for e in errors) <= TICK_S, [round(e * 1000, 1) for e in errors]


def test_loop_sustains_without_clicks(bank):
    """長く伸ばした母音（ループ）が最後まで鳴り続け、継ぎ目で振幅が落ちない。"""
    d, info = bank
    data, _ = audition.render(d, "あ")
    left, _ = decode(data, ".it", stereo=True)
    beat = 2 * audition.ROWS_PER_BEAT * audition.SPEED * TICK_S
    env = [left.rms(beat + 0.2 + i * 0.1, 0.1) for i in range(4)]       # 母音の頭から 0.2〜0.6 秒（元の母音は約 0.4 秒。0.6 秒でノートカット）
    assert min(env) > 0.5 * max(env), env
