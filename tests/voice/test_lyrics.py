"""日本語の歌詞（VOCAL_DESIGN.md P4）: 前段 ``voice.lang.ja``・``--lyrics`` の書式・割当・CLI。"""
import dataclasses

import pytest

from mod_weaver import cli, engine
from mod_weaver.errors import LyricsError
from mod_weaver.framework.score import NoteEvent
from mod_weaver.voice.lang import ja
from mod_weaver.voice.lyrics import parse_lyrics
from mod_weaver.voice.bank import importer, synthetic


def _flat(items):
    return [None if x is None else (x.text, x.onset, x.nucleus, x.kind) for x in items]


def _texts(items):
    return [None if x is None else x.text for x in items]


# ---- 前段 ----

def test_basic_morae():
    got = _flat(ja.parse("かきくけこ"))
    assert got == [("か", ("k",), "a", "normal"), ("き", ("k",), "i", "normal"), ("く", ("k",), "M", "normal"),
                   ("け", ("k",), "e", "normal"), ("こ", ("k",), "o", "normal")]


def test_special_morae():
    got = {x.text: (x.onset, x.nucleus) for x in ja.parse("しちつふじひ")}
    assert got["し"] == (("S",), "i") and got["ち"] == (("tS",), "i") and got["つ"] == (("ts",), "M")
    assert got["ふ"] == (("F",), "M") and got["じ"] == (("dZ",), "i") and got["ひ"] == (("C",), "i")


def test_youon_geminate_nasal_extend():
    got = ja.parse("きゃっとんー")
    assert _flat(got) == [("きゃ", ("ky",), "a", "normal"), ("っ", (), "", "geminate"), ("と", ("t",), "o", "normal"),
                          ("ん", (), "N", "normal"), ("ー", (), "N", "extend")]


def test_small_vowels():
    got = {x.text: (x.onset, x.nucleus) for x in ja.parse("ふぁてぃうぃいぇ")}
    assert got == {"ふぁ": (("F",), "a"), "てぃ": (("t",), "i"), "うぃ": (("w",), "i"), "いぇ": (("j",), "e")}


def test_katakana_and_romaji_normalize_to_hiragana():
    assert _texts(ja.parse("カタカナ")) == list("かたかな")
    assert _texts(ja.parse("konnichiwa")) == list("こんにちわ")
    assert _texts(ja.parse("shashu cho tsu fu")) == ["しゃ", "しゅ", None, "ちょ", None, "つ", None, "ふ"]
    assert _texts(ja.parse("kitte")) == ["き", "っ", "て"]
    assert _texts(ja.parse("kunrei si ti tu")) == ["く", "ん", "れ", "い", None, "し", None, "ち", None, "つ"]
    assert _texts(ja.parse("onna")) == ["お", "ん", "な"]
    assert _texts(ja.parse("kan'i")) == ["か", "ん", "い"]


def test_rests_are_collapsed_and_trimmed():
    assert _texts(ja.parse("  あ、、 い。 ")) == ["あ", None, "い"]


@pytest.mark.parametrize("text", ["夕焼け", "あhoge!x", "a{b|c}", "ー", "あ ー"])
def test_bad_lyrics_raise_with_line(text):
    with pytest.raises(LyricsError, match="line 1"):
        ja.parse(text)


def test_error_reports_the_line_number():
    with pytest.raises(LyricsError, match="line 3"):
        ja.parse("あ\n\nい夕")


# ---- --lyrics の書式 ----

def test_lyrics_string_is_a_stream():
    ly = parse_lyrics("あいう")
    assert not ly.by_section and _texts(ly.stream) == list("あいう")


def test_lyrics_file_sections(tmp_path):
    f = tmp_path / "s.txt"
    f.write_bytes("﻿# comment\r\n[verse]\r\nあいう\r\nえお\r\n[chorus]\r\nらららー\r\n".encode("utf-8"))
    ly = parse_lyrics(f"@{f}")
    assert _texts(ly.by_section["verse"]) == list("あいうえお")
    assert _texts(ly.by_section["chorus"]) == ["ら", "ら", "ら", "ー"]
    assert not ly.stream


def test_lyrics_file_errors(tmp_path):
    f = tmp_path / "s.txt"
    f.write_text("あ\n[verse]\nい\n", encoding="utf-8")
    with pytest.raises(LyricsError, match="mixes"):
        parse_lyrics(f"@{f}")
    f.write_text("[verse]\nあ\n夕\n", encoding="utf-8")
    with pytest.raises(LyricsError, match="line 3"):
        parse_lyrics(f"@{f}")
    with pytest.raises(LyricsError, match="cannot read"):
        parse_lyrics(f"@{tmp_path / 'none.txt'}")


# ---- 割当・生成 ----

@pytest.fixture(scope="module")
def bank(tmp_path_factory):
    d = tmp_path_factory.mktemp("vb") / "tb"
    synthetic.make_test_bank(d)
    importer.import_bank(d)
    return d


def _vocal(built, section=None):
    secs = [built.score.sections[section]] if section else built.score.sections.values()
    return [e for s in secs for e in s.parts["vocal"] if isinstance(e, NoteEvent)]


def _build(bank, lyrics, gid="enka", seed=3, fmt="it"):
    return engine.build(engine.get_genre(gid), seed, fmt, voice=bank.name, voices_dir=str(bank.parent), lyrics=lyrics)


def test_lyrics_are_sung_in_order(bank):
    b = _build(bank, "かきくけこ")
    sung = [e.syl.text for e in _vocal(b, "verse")]
    assert sung[:5] == list("かきくけこ") and len(sung) == 5          # 歌詞が尽きたら残りの音符は歌わない
    assert {e.syl.text for e in _vocal(b, "chorus")} == {"あ"}          # 歌詞が尽きた後の区間はヴォカリーズ


def test_named_sections_and_vocalise_elsewhere(bank, tmp_path):
    f = tmp_path / "l.txt"
    f.write_text("[chorus]\nかきくけこ\n", encoding="utf-8")
    b = _build(bank, f"@{f}")
    assert [e.syl.text for e in _vocal(b, "chorus")][:5] == list("かきくけこ")
    assert {e.syl.text for e in _vocal(b, "verse")} == {"あ"}


def test_lyrics_do_not_change_pitch_or_timing_of_sung_notes(bank):
    base = _vocal(_build(bank, None), "verse")
    lyr = _vocal(_build(bank, "かきくけこ"), "verse")
    assert [(e.step, e.pitch) for e in lyr] == [(e.step, e.pitch) for e in base][:len(lyr)]


def test_rest_geminate_and_extend(bank, tmp_path):
    base = _vocal(_build(bank, None), "verse")
    texts = [e.syl.text for e in _vocal(_build(bank, "かっきーく"), "verse")]
    assert texts == ["か", "き", "い", "く"]                               # っ は音符を使わず、ー は母音の音符
    first, second = _vocal(_build(bank, "かっきーく"), "verse")[:2]
    src = {e.step: e for e in base}
    base_dur = src[first.step].dur if src[first.step].dur is not None else second.step - first.step
    assert first.dur == max(1, base_dur - 1)                                # 直前の音符を 1 step 詰める
    rested = _vocal(_build(bank, "か き"), "verse")                        # 空白＝休符: 音符を 1 つ飛ばす
    assert [e.syl.text for e in rested] == ["か", "き"]
    assert rested[0].step == base[0].step and rested[1].step == base[2].step


def test_unknown_section_name_is_an_error(bank, tmp_path):
    f = tmp_path / "l.txt"
    f.write_text("[nope]\nあ\n", encoding="utf-8")
    with pytest.raises(LyricsError, match="nope"):
        _build(bank, f"@{f}")


def test_lyrics_need_voice():
    with pytest.raises(LyricsError, match="needs --voice"):
        engine.build(engine.get_genre("enka"), 1, "it", lyrics="あ")


def test_missing_syllables_are_replaced_in_a_real_build(bank, caplog):
    b = _build(bank, "ぽぽぽ")                  # 試験バンクに無い音節（ぱ行）
    assert b.data


@pytest.mark.parametrize("fmt", ["it", "xm", "mid"])
def test_lyrics_build_in_every_voice_format(bank, fmt):
    _build(bank, "ゆうやけこやけ", fmt="midi" if fmt == "mid" else fmt)


def test_cli_lyrics_exit_codes(bank, tmp_path, capsys):
    out = tmp_path / "x.it"
    base = ["--genre", "enka", "--seed", "3", "--format", "it", "--voice", bank.name, "--voices-dir", str(bank.parent),
            "-o", str(out)]
    assert cli.main(base + ["--lyrics", "ゆうやけ"]) == 0
    assert "--lyrics" in capsys.readouterr().out
    assert cli.main(base + ["--lyrics", "夕焼け"]) == 2
    assert "cannot sing" in capsys.readouterr().err
    assert cli.main(["--genre", "enka", "--lyrics", "あ", "-o", str(out)]) == 2
