"""歌声の音源（UTAU 形式）の取り込み（DESIGN.md §13.5.3・§9）。実音源に依存しない（合成した試験用バンクを使う）。"""
import json
import math
import struct
import subprocess
import wave
from pathlib import Path

import pytest

from mod_weaver import voice_cli
from mod_weaver.errors import VoiceBankError, VoiceNotFoundError
from mod_weaver.voice.bank import audition, cache, credit, discover, importer, otoini, synthetic
from mod_weaver.voice.bank.cut import cut_range
from mod_weaver.voice.bank.loopfind import find_loop
from mod_weaver.voice.bank.pitch import estimate_f0
from mod_weaver.voice.bank.resample import resample
from mod_weaver.voice.bank.wavio import read_wav

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def bank(tmp_path_factory):
    d = tmp_path_factory.mktemp("voices") / "tb"
    synthetic.make_test_bank(d)
    info, _ = importer.import_bank(d)
    return d, info


def sine(hz, rate, sec, amp=0.5):
    return [amp * math.sin(2 * math.pi * hz * i / rate) for i in range(int(rate * sec))]


# ---- oto.ini ----

def test_oto_parse_basic_and_defaults():
    entries, bad = otoini.parse("a.wav=あ,10,50,-20,30,15\nka.wav=,0,1,2,3,4\n# junk\nx=bad,1\n")
    assert [e.alias for e in entries] == ["あ", "ka"]            # 別名が空なら wav 名
    assert entries[0].cutoff == -20 and entries[0].preutterance == 30
    assert len(bad) == 2


@pytest.mark.parametrize("enc", ["utf-8", "cp932"])
def test_oto_encodings(tmp_path, enc):
    (tmp_path / "oto.ini").write_bytes("あ.wav=あ,0,1,2,3,4\n".encode(enc))
    entries, _ = otoini.load(tmp_path / "oto.ini")
    assert entries[0].alias == "あ"


def test_oto_undecodable():
    with pytest.raises(VoiceBankError):
        otoini.decode(b"\xff\xfe\x81")


def test_cv_alias_and_style():
    assert otoini.is_cv_alias("か") and not otoini.is_cv_alias("a か") and not otoini.is_cv_alias("- か")
    assert otoini.detect_style(["あ", "か"]) == "hiragana" and otoini.detect_style(["a", "ka"]) == "romaji"


# ---- wav ----

def _write_raw_wav(path, width, vals, channels=1, rate=8000):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(width)
        w.setframerate(rate)
        w.writeframes(vals)


@pytest.mark.parametrize("width,pack", [(1, lambda v: bytes([int(v * 127) + 128])),
                                        (2, lambda v: struct.pack("<h", int(v * 32767))),
                                        (3, lambda v: int(v * 8388607).to_bytes(3, "little", signed=True)),
                                        (4, lambda v: struct.pack("<i", int(v * 2147483647)))])
def test_read_wav_widths(tmp_path, width, pack):
    vals = [0.5, -0.5, 0.25]
    _write_raw_wav(tmp_path / "w.wav", width, b"".join(pack(v) for v in vals))
    rate, x = read_wav(tmp_path / "w.wav")
    assert rate == 8000 and x == pytest.approx(vals, abs=0.02)


def test_read_wav_stereo_mixed_to_mono(tmp_path):
    _write_raw_wav(tmp_path / "s.wav", 2, struct.pack("<4h", 16384, -16384, 8192, 8192), channels=2)
    _, x = read_wav(tmp_path / "s.wav")
    assert x == pytest.approx([0.0, 0.25], abs=0.001)


def test_read_wav_float_is_rejected_with_filename(tmp_path):
    hdr = b"RIFF" + struct.pack("<I", 36 + 8) + b"WAVEfmt " + struct.pack("<IHHIIHH", 16, 3, 1, 8000, 32000, 4, 32)
    (tmp_path / "f.wav").write_bytes(hdr + b"data" + struct.pack("<I", 8) + bytes(8))
    with pytest.raises(VoiceBankError, match="f.wav"):
        read_wav(tmp_path / "f.wav")


# ---- 切り出し・リサンプリング・F0・ループ ----

def test_cut_cutoff_sign_convention():
    from mod_weaver.voice.bank.otoini import OtoEntry
    rate, n = 1000, 1000                                        # 1 sample = 1 ms
    assert cut_range(OtoEntry("w", "a", 100, 0, 200, 0, 0), n, rate) == (100, 800)    # 正: 末尾から 200 ms 捨てる（実音源で確認）
    assert cut_range(OtoEntry("w", "a", 100, 0, -300, 0, 0), n, rate) == (100, 400)   # 負: offset から 300 ms
    assert cut_range(OtoEntry("w", "a", 100, 0, 0, 0, 0), n, rate) == (100, 1000)
    assert cut_range(OtoEntry("w", "a", 900, 0, 200, 0, 0), n, rate) == (0, 0)         # 逆転は空
    assert cut_range(OtoEntry("w", "a", 24, 56, 73, 5, 20), 28762, 44100) == (1058, 25543)   # 重音テト「あ」の実測値


@pytest.mark.parametrize("src,dst", [(22050, 44100), (48000, 44100), (44100, 22050)])
def test_resample_length_and_frequency(src, dst):
    y = resample(sine(440, src, 0.1), src, dst)
    assert len(y) == pytest.approx(0.1 * dst, abs=2)
    mid = y[len(y) // 4: 3 * len(y) // 4]
    rising = sum(1 for i in range(1, len(mid)) if mid[i - 1] < 0 <= mid[i])
    assert rising / (len(mid) / dst) == pytest.approx(440, rel=0.05)


@pytest.mark.parametrize("hz", [110, 220, 330, 440])
def test_f0_estimate(hz):
    assert estimate_f0(sine(hz, 44100, 0.4), 44100) == pytest.approx(hz, rel=0.01)


def test_f0_none_for_noise():
    import random
    rng = random.Random(1)
    assert estimate_f0([rng.uniform(-1, 1) for _ in range(20000)], 44100) is None


def test_loop_seam_is_continuous():
    rate, hz = 44100, 220.0
    x = sine(hz, rate, 0.6) + []
    r = find_loop(x, rate, 0, hz)
    assert r.loop is not None and r.mismatch < 0.05
    start, length = r.loop
    assert start + length == len(r.data)
    seam = abs(r.data[-1] - r.data[start - 1 + 0]) if start else 0
    step = max(abs(r.data[i + 1] - r.data[i]) for i in range(start, start + 200))
    assert abs(r.data[start] - r.data[-1]) <= 3 * step + seam      # ループ末尾→始点の飛びは通常の隣接差の範囲内


def test_loop_rejects_short_and_aperiodic():
    assert find_loop(sine(220, 44100, 0.1), 44100, 0, 220.0).loop is None      # 安定部が短い
    assert find_loop(sine(220, 44100, 0.6), 44100, 0, None).loop is None       # F0 なし


# ---- 取り込み ----

def test_import_synthetic_bank(bank):
    d, info = bank
    assert len(info.syllables) == 25 and info.rate == 44100
    assert info.home_hz == pytest.approx(synthetic.F0, rel=0.02)
    assert all(s.loop for s in info.syllables.values())
    assert all(s.mismatch < 0.2 for s in info.syllables.values())
    assert all(s.f0 == pytest.approx(synthetic.F0, rel=0.03) for s in info.syllables.values())
    assert (d / ".modweaver" / "report.txt").read_text(encoding="utf-8").startswith("voice: tb")


def test_import_is_deterministic(bank, tmp_path):
    d, info = bank
    d2 = tmp_path / "tb"
    synthetic.make_test_bank(d2)
    info2, _ = importer.import_bank(d2)
    assert info2.fingerprint == info.fingerprint
    assert (d2 / ".modweaver" / "seg" / "0003.pcm").read_bytes() == (d / ".modweaver" / "seg" / "0003.pcm").read_bytes()


def test_import_cp932_oto(tmp_path):
    d = tmp_path / "cp"
    synthetic.make_test_bank(d, encoding="cp932")
    info, _ = importer.import_bank(d)
    assert "あ" in info.syllables


def test_import_skips_vcv_and_reports(tmp_path):
    d = tmp_path / "mix"
    synthetic.make_test_bank(d)
    oto = d / "oto.ini"
    oto.write_text(oto.read_text(encoding="utf-8") + "ka.wav=a か,30,60,-25,25,20\nka.wav=- か,30,60,-25,25,20\n",
                   encoding="utf-8")
    res = importer.check(d)
    assert len(res.cv) == 25 and len(res.skipped) == 2


def test_import_missing_wav_is_warned_not_fatal(tmp_path):
    d = tmp_path / "mw"
    synthetic.make_test_bank(d)
    (d / "ka.wav").unlink()
    info, report = importer.import_bank(d)
    assert "か" not in info.syllables and "missing wav: ka.wav" in report


def test_import_requires_credit(tmp_path):
    d = tmp_path / "nocredit"
    synthetic.make_test_bank(d)
    meta = json.loads((d / "modweaver.json").read_text(encoding="utf-8"))
    meta["credit"] = ""
    (d / "modweaver.json").write_text(json.dumps(meta), encoding="utf-8")
    with pytest.raises(VoiceBankError, match="credit"):
        importer.import_bank(d)
    meta["credit_required"] = False                                  # 不要なら明示すれば取り込める
    (d / "modweaver.json").write_text(json.dumps(meta), encoding="utf-8")
    importer.import_bank(d)


def test_import_creates_template_when_json_missing(tmp_path):
    d = tmp_path / "nojson"
    synthetic.make_test_bank(d)
    (d / "modweaver.json").unlink()
    with pytest.raises(VoiceBankError, match="template"):
        importer.import_bank(d)
    assert (d / credit.FILE).is_file()


def test_voice_id_must_be_ascii(tmp_path):
    d = tmp_path / "歌声"
    synthetic.make_test_bank(d)
    meta = json.loads((d / "modweaver.json").read_text(encoding="utf-8"))
    meta["id"] = ""
    (d / "modweaver.json").write_text(json.dumps(meta), encoding="utf-8")
    with pytest.raises(VoiceBankError, match="ASCII"):
        importer.import_bank(d)
    info, _ = importer.import_bank(d, id_override="utagoe")
    assert info.id == "utagoe"


# ---- キャッシュ・探索 ----

def test_cache_roundtrip_and_corruption(bank, tmp_path):
    d, info = bank
    loaded = cache.load_info(d)
    assert loaded.syllables["あ"] == info.syllables["あ"] and loaded.fingerprint == info.fingerprint
    s = loaded.syllables["あ"]
    assert len(cache.load_pcm(d, s)) == s.n * 2
    broken = tmp_path / "br"
    (broken / ".modweaver").mkdir(parents=True)
    (broken / ".modweaver" / "bank.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(VoiceBankError):
        cache.load_info(broken)


def test_discover_order_and_not_found(bank, tmp_path):
    d, _ = bank
    assert discover.find("tb", [d.parent]) == d
    with pytest.raises(VoiceNotFoundError):
        discover.find("nope", [d.parent])
    env = {"MODWEAVER_VOICES": f"{tmp_path}{__import__('os').pathsep}{d.parent}"}
    assert discover.search_dirs(environ=env)[:2] == [tmp_path, d.parent]
    assert discover.search_dirs("x", environ=env) == [Path("x")]            # --voices-dir はそこだけ


# ---- audition・CLI ----

def test_audition_produces_valid_it(bank):
    from mod_weaver.core.native_it import verify
    d, _ = bank
    data, notes = audition.render(d, "あいうえおカキク")
    assert data[:4] == b"IMPM" and not [i for i in verify(data) if i.level == "ERROR"]
    assert any("preroll" in n for n in notes)
    with pytest.raises(VoiceBankError):
        audition.render(d, "xyz")


def test_audition_reports_unknown_syllable(bank):
    _, notes = audition.render(bank[0], "あ?い")
    assert any("'?'" in n for n in notes)


def test_cli_end_to_end(tmp_path, capsys):
    tb = tmp_path / "v" / "tb"
    assert voice_cli.main(["make-test-bank", str(tb)]) == 0
    assert voice_cli.main(["check", str(tb)]) == 0
    assert voice_cli.main(["import", str(tb)]) == 0
    capsys.readouterr()
    assert voice_cli.main(["--voices-dir", str(tb.parent), "list", "--json"]) == 0
    listed = json.loads(capsys.readouterr().out)
    assert [r["id"] for r in listed] == ["tb"] and listed[0]["syllables"] == 25
    out = tmp_path / "a.it"
    assert voice_cli.main(["--voices-dir", str(tb.parent), "audition", "tb", "--out", str(out)]) == 0
    assert out.read_bytes()[:4] == b"IMPM"
    assert voice_cli.main(["--voices-dir", str(tb.parent), "info", "tb"]) == 0


def test_cli_error_exit_codes(tmp_path, capsys):
    assert voice_cli.main(["--voices-dir", str(tmp_path), "audition", "nope"]) == 2
    assert voice_cli.main(["check", str(tmp_path)]) == 3                   # oto.ini が無い


# ---- 声のデータを git に入れない（NV-4。D1） ----

def test_no_voice_data_in_git():
    try:
        files = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split("\n")
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("git not available")
    bad = [f for f in files if f.endswith((".wav", ".pcm", "oto.ini", "bank.json"))
           or f.startswith("voices/") or "/.modweaver/" in f]
    assert not bad, f"voice data must not be committed (D1): {bad}"
    ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "/voices/" in ignore and ".modweaver/" in ignore


# ---- prefix.map（多音高。P5） ----

def test_prefix_map_parse_and_split():
    from mod_weaver.voice.bank import prefixmap
    ents, bad = prefixmap.parse("C3\t\t_L\r\nA3\t\t_M\nE4\t↑\t\nxx\t\t\n\nC5\t\t\n")
    assert [(e.midi, e.prefix, e.suffix) for e in ents] == [(48, "", "_L"), (57, "", "_M"), (64, "↑", "")]   # 空の行は捨てる
    assert len(bad) == 1 and "xx" in bad[0]
    assert prefixmap.split_alias("あ_L", ents) == ("あ", 48)
    assert prefixmap.split_alias("↑か", ents) == ("か", 64)
    assert prefixmap.split_alias("さ", ents) == ("さ", None)                       # どれにも当たらない＝既定の高さ
    assert prefixmap.split_alias("_L", ents) == ("_L", None)                        # 基の別名が空になる当たり方は採らない
    assert prefixmap.note_to_midi("C4") == 60 and prefixmap.note_to_midi("A#2") == 46 and prefixmap.note_to_midi("Bb2") == 46
    assert prefixmap.note_to_midi("H4") is None


@pytest.fixture(scope="module")
def multi_bank(tmp_path_factory):
    d = tmp_path_factory.mktemp("mb") / "mpb"
    synthetic.make_test_bank(d, pitches=synthetic.MULTI_PITCH)
    info, report = importer.import_bank(d)
    return d, info, report


def test_multi_pitch_import_groups_variants(multi_bank):
    d, info, report = multi_bank
    assert info.pitches == (48, 57, 64) and len(info.syllables) == 25 and len(info.variants) == 75
    assert [round(h) for h in info.pitch_hz] == [164, 219, 328] or all(abs(h - t) < 8 for h, t in zip(info.pitch_hz, (165, 220, 330)))
    assert info.syllables["あ"].pitch == 57                                          # 単一音高として見せる版は中央の音域
    assert info.variants["か@48"].f0 < info.variants["か@57"].f0 < info.variants["か@64"].f0
    assert "pitch ranges" in report
    again = cache.load_info(d)
    assert again.pitches == info.pitches and again.variants.keys() == info.variants.keys()


def test_single_pitch_bank_has_no_variants(bank):
    info = bank[1]
    assert info.pitches == () and info.variants == {}
