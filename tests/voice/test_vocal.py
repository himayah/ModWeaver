"""歌声パート（VOCAL_DESIGN.md P3・ヴォカリーズ）: 宣言・作曲・音域合わせ・プリロール・CLI。"""
import ast
import dataclasses
import json
import math
from pathlib import Path

import pytest

from mod_weaver import cli, engine
from mod_weaver.core import pitch as pitchmod
from mod_weaver.errors import PlanError, VoiceNotFoundError, VoiceUnsupportedError
from mod_weaver.framework.compose import compose, resolve_plan
from mod_weaver.framework.genre import Voice
from mod_weaver.framework.realize import lanes as lanesmod
from mod_weaver.framework.realize.encode import Codec
from mod_weaver.framework.realize.voice import FormantBackend, UtauBackend, VoicePlan, logical_of_hz
from mod_weaver.framework.score import NoteEvent
from mod_weaver.framework.target import resolve
from mod_weaver.voice.bank import importer, synthetic
from mod_weaver.voice.phoneme import Syllable, vowel_syllable

VOCAL_GENRES = ["okinawan", "enka", "mood-kayo"]
ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def bank(tmp_path_factory):
    d = tmp_path_factory.mktemp("vb") / "tb"
    synthetic.make_test_bank(d)
    importer.import_bank(d)
    return d


def _score(gid, seed, voice):
    g = engine.get_genre(gid)
    plan = resolve_plan(g, seed)
    feats = resolve("it", None, g, seed).features | ({"voice"} if voice else frozenset())
    return g, compose(g, plan, seed, feats)


# ---- 宣言・作曲 ----

@pytest.mark.parametrize("gid", VOCAL_GENRES)
def test_vocal_part_only_exists_with_voice(gid):
    g, off = _score(gid, 1, False)
    _, on = _score(gid, 1, True)
    assert "vocal" in off.skipped_parts and "vocal" not in on.skipped_parts
    assert not any(e for s in off.sections.values() for e in s.parts.get("vocal", ()))
    sung = [e for s in on.sections.values() for e in s.parts["vocal"] if isinstance(e, NoteEvent)]
    assert sung and all(e.syl is not None for e in sung)
    ducked = {t for part in engine.get_genre(gid).parts for t in part.ducks}
    for name, sec in off.sections.items():          # D4: 他のパートの音符は声の有無で変わらない（音量だけ ducks で下がる）
        for part, events in sec.parts.items():
            if part == "vocal":
                continue
            if part not in ducked:
                assert on.sections[name].parts[part] == events
                continue
            strip = lambda evs: [dataclasses.replace(e, vel=None) if isinstance(e, NoteEvent) else e for e in evs]
            assert strip(on.sections[name].parts[part]) == strip(events)        # 時刻・高さ・長さは同じ
            if on.sections[name].parts["vocal"]:
                vel = lambda evs: [e.vel for e in evs if isinstance(e, NoteEvent)]
                assert all(a is not None and (b is None or a < b) for a, b in
                           zip(vel(on.sections[name].parts[part]), vel(events)) if b is not None)


@pytest.mark.parametrize("gid", VOCAL_GENRES)
def test_voice_notes_follow_lead_and_ignore_the_voice_source(gid, bank):
    a = engine.build(engine.get_genre(gid), 5, "it", voice="formant")
    b = engine.build(engine.get_genre(gid), 5, "it", voice="tb", voices_dir=str(bank.parent))
    notes = lambda built: [(n, e.step, e.pitch, e.dur) for n, s in built.score.sections.items()
                           for e in s.parts["vocal"] if isinstance(e, NoteEvent)]
    assert notes(a) == notes(b) and notes(a)          # V-4: 声の源が違っても時刻・高さは同じ


def test_voice_instrument_requires_the_voice_feature():
    from mod_weaver.framework.genre import Genre, Part
    from mod_weaver.framework.gens import Sing
    base = engine.get_genre("enka")
    with pytest.raises(PlanError, match="requires"):
        type("Bad", (Genre,), dict(id="bad", instruments=base.instruments, harmony=base.harmony,
                                   sections=base.sections, form=base.form, mod_channels=base.mod_channels,
                                   parts=(Part("vocal", Sing("voice"), depends=("lead",)), *base.parts[:-1])))


def test_syl_only_on_voice_instruments():
    g, score = _score("enka", 1, True)
    assert isinstance(g.instruments["voice"], Voice)
    assert all(e.syl is None for s in score.sections.values() for p, ev in s.parts.items() if p != "vocal"
               for e in ev if isinstance(e, NoteEvent))


# ---- 音域合わせ・音高 ----

@pytest.mark.parametrize("n", range(8, 40))
def test_formant_sample_sounds_at_the_written_pitch(n):
    backend, g = FormantBackend(), engine.get_genre("enka")
    plan = VoicePlan(backend, g, 120)
    syl = vowel_syllable("あ")
    p = lanesmod.Placement(0, 0, "note", "voice", float(n), 40, 4, (), syl=syl)
    slot = plan.slot_for(p, None)
    spec = plan.sample(slot, g.instruments["voice"])
    note = Codec("it").note(spec, n)
    sounding = spec.sounding_hz * (spec.rate_hz / 44100) * 2 ** ((note - Codec("it").n_ref) / 12)
    cents = 1200 * math.log2(sounding / pitchmod.hz(n))
    assert abs(cents) < 60, cents        # 音高帯の代表 F0 からの半音単位のずれ＋周期の丸め（帯は ±3 半音）
    # 帯の中心の音は正確
    c = lanesmod.Placement(0, 0, "note", "voice", float(slot.bucket * 6), 40, 4, (), syl=syl)
    spec_c = plan.sample(plan.slot_for(c, None), g.instruments["voice"])
    note_c = Codec("it").note(spec_c, slot.bucket * 6)
    sounding_c = spec_c.sounding_hz * (spec_c.rate_hz / 44100) * 2 ** ((note_c - 60) / 12)
    assert abs(1200 * math.log2(sounding_c / pitchmod.hz(slot.bucket * 6))) < 12


def test_utau_range_fit_folds_by_octaves(bank):
    b = UtauBackend(bank)
    g = engine.get_genre("enka")
    plan = VoicePlan(b, g, 100)
    syl = vowel_syllable("あ")
    h = logical_of_hz(b.home_hz())
    mk = lambda n: lanesmod.Placement(0, 0, "note", "voice", float(n), 40, 4, (), syl=syl)
    by = {"s": ([mk(30), mk(32), mk(34), mk(36), mk(20)], [])}
    plan.prepare(by, {"s": (6, None)})
    pitches = [p.pitch for p in by["s"][0]]
    assert all(abs(x - h) <= 6.5 + 1e-9 for x in pitches)
    assert plan.octave == round((32 - h) / 12)


def test_unsupported_syllable_is_reported(bank):
    plan = VoicePlan(UtauBackend(bank), engine.get_genre("enka"), 100)
    odd = Syllable("ぬ", onset=("n",), nucleus="M")
    p = lanesmod.Placement(0, 0, "note", "voice", 30.0, 40, 4, (), syl=Syllable("ぱ", onset=("p",), nucleus="a"))
    with pytest.raises(PlanError, match="cannot sing"):
        plan.prepare({"s": ([p], [])}, {"s": (6, None)})


# ---- 生成・形式・CLI ----

@pytest.mark.parametrize("fmt", ["it", "xm"])
@pytest.mark.parametrize("gid", VOCAL_GENRES)
def test_generates_and_verifies_with_voice(gid, fmt):
    built = engine.build(engine.get_genre(gid), 3, fmt, voice="formant")
    assert not [i for i in engine.verify_data(built) if i.level == "ERROR"]
    plain = engine.build(engine.get_genre(gid), 3, fmt)
    assert built.channels == plain.channels + 1 and built.voice.id == "formant" and plain.voice is None
    assert built.data == engine.build(engine.get_genre(gid), 3, fmt, voice="formant").data      # V-3


def test_utau_voice_builds_and_lead_aligns_samples(bank):
    built = engine.build(engine.get_genre("okinawan"), 2, "it", voice="tb", voices_dir=str(bank.parent))
    assert not [i for i in engine.verify_data(built) if i.level == "ERROR"]
    assert built.voice.id == "tb" and len(built.voice.fingerprint) == 64


def test_midi_with_voice_has_a_choir_channel():
    built = engine.build(engine.get_genre("enka"), 2, "midi", voice="formant")
    plain = engine.build(engine.get_genre("enka"), 2, "midi")
    assert built.channels == plain.channels + 1


@pytest.mark.parametrize("fmt", ["mod", "s3m"])
def test_voice_on_unsupported_format_is_an_error(fmt):
    with pytest.raises(VoiceUnsupportedError):
        engine.build(engine.get_genre("enka"), 1, fmt, voice="formant")


def test_voice_on_genre_without_vocal_is_an_error():
    with pytest.raises(VoiceUnsupportedError, match="enka"):
        engine.build(engine.get_genre("pop"), 1, "it", voice="formant")


def test_unknown_voice_is_an_error(tmp_path):
    with pytest.raises(VoiceNotFoundError):
        engine.build(engine.get_genre("enka"), 1, "it", voice="nope", voices_dir=str(tmp_path))


def test_cli_exit_codes_and_credits(tmp_path, bank, capsys):
    out = tmp_path / "s.it"
    base = ["--genre", "enka", "--seed", "4", "--format", "it", "-o", str(out)]
    assert cli.main(base + ["--voice", "tb", "--voices-dir", str(bank.parent)]) == 0
    text = (tmp_path / "s.it.credits.txt").read_text(encoding="utf-8")
    assert "Synthetic test bank" in text and "Voice: tb" in text
    assert cli.main(["--genre", "enka", "--format", "mod", "--voice", "formant", "-o", str(tmp_path / "m.mod")]) == 2
    assert cli.main(["--genre", "pop", "--format", "it", "--voice", "formant", "-o", str(tmp_path / "p.it")]) == 2
    assert cli.main(base + ["--voice", "missing", "--voices-dir", str(tmp_path)]) == 2
    capsys.readouterr()
    assert cli.main(base + ["--voice", "formant", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["voice"]["id"] == "formant"
    assert cli.main(["--list-voices", "--voices-dir", str(bank.parent), "--json"]) == 0
    ids = [r["id"] for r in json.loads(capsys.readouterr().out)]
    assert ids == ["formant", "tb"]


def test_catalog_marks_vocal_genres():
    cat = cli.catalog()
    assert {g["id"] for g in cat["genres"] if g["vocal"]} == set(VOCAL_GENRES)
    assert cat["voice_formats"] == ["it", "xm", "mp3", "midi"]


# ---- 層の検査（VOCAL_DESIGN.md §2.1） ----

def _imports(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out = []
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom):
            out.append(("." * n.level) + (n.module or "") + " " + ",".join(a.name for a in n.names))
        elif isinstance(n, ast.Import):
            out += [a.name for a in n.names]
    return out


def test_genres_do_not_import_voice_backends_or_realize():
    for f in (ROOT / "mod_weaver" / "genres").glob("*.py"):
        bad = [i for i in _imports(f) if "voice.bank" in i or "voice.formant" in i or "realize" in i]
        assert not bad, f"{f.name}: {bad}"


def test_phoneme_module_is_pure_data():
    bad = [i for i in _imports(ROOT / "mod_weaver" / "voice" / "phoneme.py")
           if any(w in i for w in ("wave", "os", "pathlib", "open", "json"))]
    assert not bad


# ---- プリロール（VOCAL_DESIGN.md §5.6・R2） ----

@pytest.mark.parametrize("swing", [None, "2:1", "3:1"])
@pytest.mark.parametrize("bpm", [60, 84, 140, 200])
def test_preroll_places_the_vowel_exactly_on_the_beat(bank, swing, bpm):
    from mod_weaver.framework.plan import Swing
    from mod_weaver.framework.score import Delay
    sw = {None: None, "2:1": Swing(16, 8), "3:1": Swing(18, 6)}[swing]
    tps = 12 if sw is None else 0
    row_len = (lambda i: 6) if sw is None else (lambda i: sw.long if i % 2 == 0 else sw.short)
    t = lambda step: sum(row_len(i) for i in range(step))             # step の頭の tick（区間の先頭から）
    plan = VoicePlan(UtauBackend(bank), engine.get_genre("okinawan"), bpm)
    syl = vowel_syllable("あ")
    origs = [lanesmod.Placement(s, 0, "note", "voice", 30.0, 40, 3, (), syl=syl) for s in (0, 3, 5, 9, 17, 30)]
    by = {"s": (list(origs), [])}
    plan.prepare(by, {"s": (6, sw)})
    assert plan.lead_ticks >= 1
    for o, n in zip(origs, by["s"][0]):
        d = next((a.ticks for a in n.arts if isinstance(a, Delay)), 0)
        want = t(o.step) - plan.lead_ticks
        if want >= 0:
            assert t(n.step) + d == want, (o.step, n.step, d)
        else:
            assert n.step == 0 and d == 0                              # 区間の頭より前は行 0・Delay 0
        assert d < row_len(n.step)                                     # Delay はその row の tick 数未満
        assert n.step + n.dur == o.step + o.dur                        # 音の終わりは変わらない


def test_preroll_collision_at_section_start_keeps_one_note(bank):
    plan = VoicePlan(UtauBackend(bank), engine.get_genre("okinawan"), 84)
    syl = vowel_syllable("あ")
    by = {"s": ([lanesmod.Placement(s, 0, "note", "voice", 30.0, 40, 1, (), syl=syl) for s in (0, 1, 4)], [])}
    plan.prepare(by, {"s": (6, None)})
    assert [p.step for p in by["s"][0]] == [0, 3]        # 0 と 1 は行 0 に重なるので後の音を捨てる


# ---- 組込みの声の質（試聴で「楽器に聞こえる」と指摘されたため、揺れの焼き込みと母音の差を検査する） ----

@pytest.mark.parametrize("timbre", ["female", "male", "choir"])
@pytest.mark.parametrize("vowel", ["a", "i", "M", "e", "o"])
def test_formant_loop_is_seamless_and_periodic_in_loop_length(vowel, timbre):
    from mod_weaver.voice import formant
    r = formant.render_vowel(vowel, 262.0, timbre)
    start, length = r.loop
    assert start + length == len(r.data)
    biggest = max(abs(r.data[i + 1] - r.data[i]) for i in range(start, len(r.data) - 1))
    assert abs(r.data[start] - r.data[-1]) <= biggest                     # ループ末尾→始点の飛びが、ループ内の最大の隣接差以内
    cycles = r.home_hz * length / r.rate
    assert abs(cycles - round(cycles)) < 1e-6                              # ループ長に整数周期


def test_formant_is_not_a_static_waveform():
    """ビブラート・シマーを焼き込んであるので、ループ内で振幅の包絡と周期が揺れる（静的な周期波形はオルガンに聞こえる）。"""
    from mod_weaver.voice import formant
    r = formant.render_vowel("a", 262.0, "female")
    s, n = r.loop
    period = round(r.rate / r.home_hz)
    peaks = [max(abs(v) for v in r.data[s + i:s + i + period]) for i in range(0, n - period, period)]
    assert max(peaks) / min(peaks) > 1.03                                  # シマー
    zc = [i for i in range(s + 1, s + n) if r.data[i - 1] < 0 <= r.data[i]]
    gaps = [b - a for a, b in zip(zc, zc[1:])]
    assert max(gaps) - min(gaps) >= 3                                      # ビブラート・ジッタによる周期の揺れ


def test_formant_vowels_have_distinct_spectra():
    np = pytest.importorskip("numpy")
    from mod_weaver.voice import formant

    def curve(v, f0):
        r = formant.render_vowel(v, f0, "female")
        seg = np.array(r.data[2205:2205 + 16384], float) * np.hanning(16384)
        sp, f = np.abs(np.fft.rfft(seg)), np.fft.rfftfreq(16384, 1 / r.rate)
        ks = range(1, int(3800 / r.home_hz))
        db = [20 * np.log10(sp[(f > k * r.home_hz * .97) & (f < k * r.home_hz * 1.03)].max() + 1e-9) for k in ks]
        c = np.interp(np.arange(300, 3800, 100), [k * r.home_hz for k in ks], db)
        return c - c.mean()

    for f0 in (196, 262, 330):
        cs = {v: curve(v, f0) for v in "aiMeo"}
        worst = min(float(np.sqrt(np.mean((cs[a] - cs[b]) ** 2))) for a in "aiMeo" for b in "aiMeo" if a < b)
        assert worst > 4.0, (f0, worst)               # どの母音の組も包絡が 4 dB(RMS) 以上違う
