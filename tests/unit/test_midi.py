"""--format midi（DESIGN.md §7.7）。SMF の独立パースには mido（開発専用依存）を使う。"""
import io
import math

import pytest

from mod_weaver import engine, profiles
from mod_weaver.core import midi, timeline
from mod_weaver.core.verify import has_errors
from mod_weaver.errors import PlanError

mido = pytest.importorskip("mido")
GENRES = [c.id for c in profiles.list_profiles()]


def render(genre, seed=123456, **kw):
    p = profiles.get_profile(genre)
    song, plan = engine.compose_song(p, seed, **kw)
    data = engine.serialize(p, song, plan, "midi")
    return p, song, plan, data, mido.MidiFile(file=io.BytesIO(data))


@pytest.mark.parametrize("genre", GENRES)
def test_every_instrument_has_a_gm_voice(genre):
    p = profiles.get_profile(genre)
    assert set(p.gm_voices) == set(p.build_samples()), "gm_voices must cover exactly the genre's instruments"


@pytest.mark.parametrize("genre", GENRES)
def test_midi_is_valid_and_matches_timeline(genre):
    p, song, plan, data, mf = render(genre)
    assert not has_errors(midi.verify_midi(data))
    assert mf.type == 1 and mf.ticks_per_beat == midi.PPQ
    tl = timeline.build(song, plan.bpm)
    assert abs(mf.length - tl.seconds) < 0.05
    tempos = [m.tempo for m in mf.tracks[0] if m.type == "set_tempo"]
    assert tempos[0] == 60_000_000 // plan.bpm
    note_ons = [m for tr in mf.tracks for m in tr if m.type == "note_on" and m.velocity]
    assert note_ons and all(0 <= m.note <= 127 for m in note_ons)
    if any(v.is_drum for v in p.gm_voices.values()):
        assert any(m.channel == midi.DRUM_CHANNEL for m in note_ons)


def test_tempo_option_reaches_midi_tempo():
    *_, mf = render("nostalgic", tempo=engine.TempoRequest(140, 140))
    assert [m.tempo for m in mf.tracks[0] if m.type == "set_tempo"][0] == 60_000_000 // 140


def test_free_jazz_tempo_curve_becomes_tempo_events():
    *_, mf = render("free-jazz")
    assert len([m for m in mf.tracks[0] if m.type == "set_tempo"]) > 20


@pytest.mark.parametrize("genre, sig", [("nostalgic", (4, 4)), ("march", (2, 4)), ("swing-jazz", (4, 4))])
def test_time_signature(genre, sig):
    *_, mf = render(genre)
    ts = [m for m in mf.tracks[0] if m.type == "time_signature"]
    assert (ts[0].numerator, ts[0].denominator) == sig


def test_prog_rock_meter_changes_are_written():
    *_, mf = render("prog-rock")
    sigs = {(m.numerator, m.denominator) for m in mf.tracks[0] if m.type == "time_signature"}
    assert len(sigs) >= 2


def test_microtonal_finetune_becomes_pitch_bend():
    """maqam の oud_n3（finetune +6 = +3/4 半音）は専用チャンネルの固定ベンドになる。"""
    p, song, plan, data, mf = render("maqam")
    names = list(song.instrument_names)
    spec = song.samples[names.index("oud_n3")]
    bends = {m.channel: m.pitch for tr in mf.tracks for m in tr if m.type == "pitchwheel"}
    ch = midi._assign_channels([p.gm_voices[n] for n in names])[names.index("oud_n3")]
    expected = round((midi._pitch_offset(spec) + spec.finetune / 8) * midi.BEND_PER_SEMITONE)
    assert bends[ch] == expected and expected > 2500


def test_missing_gm_voice_is_an_error():
    from mod_weaver.core.formats import WriteOptions

    p = profiles.get_profile("trap")
    song, plan = engine.compose_song(p, 1)
    opts = engine.write_options(p, song, plan)
    partial = dict(opts.gm_voices)
    partial.pop("k808")
    with pytest.raises(PlanError, match="k808"):
        midi.serialize_midi(song, WriteOptions(**{**opts.__dict__, "gm_voices": partial}))


def test_gm_voice_validation():
    with pytest.raises(ValueError):
        midi.GmVoice()
    with pytest.raises(ValueError):
        midi.GmVoice(program=1, drum_note=36)
    with pytest.raises(ValueError):
        midi.GmVoice(program=128)


def test_sounding_hz_matches_sample_data():
    """SampleSpec.sounding_hz（MIDI 音高の根拠）をサンプルデータの自己相関（YIN）で検算する。
    非調和な音色（トーンクラスター、スクリーチ、ベル、ガムランの金属打楽器、金属パイプ）と和音を焼き込んだ音色（パワーコード・第３段階の和音サンプル。
    仮想基音が根音より下に出る）は除く。"""
    np = pytest.importorskip("numpy")
    from mod_weaver.core import dsp
    from mod_weaver.core.pitch import PERIODS

    from mod_weaver.profiles.band_common import BandProfile

    skip_patches = {"FreePianoCluster", "FreeSaxScreech", "ProgGtrPower", "CrunchGtr", "Bell",
                    "MetalPipe", "Saron", "Bonang", "Kenong", "Kempul", "GongAgeng"}

    def chordal(cls, key, spec):
        if spec.name in skip_patches:
            return True
        return issubclass(cls, BandProfile) and key not in dict(cls.KIT)   # CHORD_KITS から作った和音サンプル

    def yin(x, fs, fmin=40, fmax=2000):
        x = x - x.mean()
        w = min(len(x) // 2, 4096)
        tau_max, tau_min = min(int(fs / fmin), len(x) - w - 1), max(2, int(fs / fmax))
        d = np.array([np.sum((x[:w] - x[t:t + w]) ** 2) for t in range(tau_max)])
        cm = np.ones_like(d)
        cm[1:] = d[1:] * np.arange(1, len(d)) / np.cumsum(d[1:])
        for t in range(tau_min, tau_max):
            if cm[t] < 0.15:
                while t + 1 < tau_max and cm[t + 1] < cm[t]:
                    t += 1
                return fs / t
        return fs / (tau_min + int(np.argmin(cm[tau_min:])))

    for cls in profiles.list_profiles():
        for key, spec in cls().build_samples().items():
            if spec.sounding_hz is None or chordal(cls, key, spec):
                continue
            raw = np.array([b - 256 if b > 127 else b for b in spec.data], dtype=float)
            if spec.loop:
                s, l = spec.loop
                body = raw[s * 2:(s + l) * 2]
                x = np.tile(body, max(2, 8192 // len(body) + 2))
            else:
                x = raw[len(raw) // 20:]
            f = yin(x, dsp.CLOCK / PERIODS[spec.rate_note])
            assert abs(1200 * math.log2(f / spec.sounding_hz)) < 50, (cls.id, key, spec.sounding_hz, f)


@pytest.mark.parametrize("genre", ["calm", "orchestral"])
def test_channel_volume_is_full_and_loudest_note_is_velocity_127(genre):
    """音量の底上げ（DESIGN.md §7.9）: 全チャンネルの CC7 が 127、最も大きい音が velocity 127。"""
    *_, mf = render(genre)
    channels = {m.channel for tr in mf.tracks for m in tr if m.type == "note_on"}
    cc7 = {m.channel: m.value for tr in mf.tracks for m in tr if m.type == "control_change" and m.control == 7}
    assert channels <= set(cc7) and set(cc7.values()) == {127}
    assert max(m.velocity for tr in mf.tracks for m in tr if m.type == "note_on") == 127
