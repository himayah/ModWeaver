"""グループC（個別実装）12ジャンルの固有の性質（FRAMEWORK_REDESIGN.md §15.4・§16.9）。

旧 ``tests/profiles/test_<id>.py`` が確かめていた音楽上の約束を、Score と Realizer の言葉で書き直したもの
（チャンネル番号・row・Cell の検査はここには無い）。旧版と同じ seed でも打点は一致しない（D9）ので、構造・音域・規則だけを見る。
"""
from __future__ import annotations

import pytest

from mod_weaver.core import native, pitch
from mod_weaver.errors import ChannelCountError
from mod_weaver.framework.realize import lanes as lanesmod
from mod_weaver.framework.realize.tracker import realize
from mod_weaver.framework.registry import get_genre, resolve_id
from mod_weaver.framework.score import Arpeggio, Automation, Glide, NoteEvent, NoteOff, Offset, Retrig, Vibrato
from mod_weaver.framework.target import resolve
from tests.framework.test_ported_genres_all import _genre, _score

SEEDS = range(1, 9)


def notes(score, section, part, inst=None):
    return [e for e in score.sections[section].parts[part]
            if isinstance(e, NoteEvent) and (inst is None or e.inst == inst)]


def all_notes(score, part, inst=None):
    return [e for s in score.sections.values() for e in s.parts.get(part, ()) if isinstance(e, NoteEvent)
            and (inst is None or e.inst == inst)]


def grid_of(genre, score, plan, fmt="mod", budget=None, seed=1):
    return realize(genre, score, plan, resolve(fmt, budget, genre, seed))


# ---------------------------------------------------------------- minimalism

def test_minimalism_phases_shift_only_the_piano():
    genre = _genre("minimalism")
    _plan, score = _score(genre)
    assert list(score.sections) == [f"phase{i}" for i in range(16)] and score.order == list(score.sections)
    for sec in score.sections.values():
        assert sec.plan.steps == 48 and len(sec.plan.measures) == 1

    def onsets(i, part):
        return tuple(e.step for e in notes(score, f"phase{i}", part))

    assert onsets(0, "piano") != onsets(1, "piano")
    assert onsets(0, "piano") == onsets(8, "piano")            # 周期 16 の半分ずれ＝偶奇一致で同じ step 集合
    for part in ("marimba", "vibes", "wood"):
        assert len({onsets(i, part) for i in range(16)}) == 1   # 他のパートは全位相で固定
    assert {e.step for e in notes(score, "phase0", "wood")} == {1, 7, 13, 19, 25, 31, 37, 43}


def test_minimalism_has_no_randomness_and_breaks_each_pattern_at_row_47():
    genre = _genre("minimalism")
    plan1, score1 = _score(genre, 1)
    plan2, score2 = _score(genre, 99)
    assert [s.parts for s in score1.sections.values()] == [s.parts for s in score2.sections.values()]
    rs = grid_of(genre, score1, plan1)
    assert len(rs.patterns) == 16
    for pat in rs.patterns:
        assert pat.rows == 64 and any(pat.get(47, c).fx == ("D", 0) for c in range(pat.channels))


# ---------------------------------------------------------------- free-jazz

def test_free_jazz_rubato_is_continuous_and_scales_with_the_start_bpm():
    from mod_weaver.genres_next import free_jazz as fj

    genre = _genre("free-jazz")
    assert genre.tempo_range == fj.TEMPO_RANGE and genre.tempo_choices == (96,)
    assert genre.tempo_range[0] <= 96 <= genre.tempo_range[1]
    plan, score = _score(genre)
    assert list(score.sections) == ["movement_a", "movement_b", "climax", "movement_c"] and score.bpm == 96
    last = 96
    for name, sec in score.sections.items():
        assert sec.tempo and sec.tempo[0].step == 0 and sec.tempo[0].bpm == last, name   # 前の区間の終わりから滑らかに続く
        assert all(32 <= t.bpm <= 255 for t in sec.tempo)
        last = sec.tempo[-1].bpm
    assert last == 70 and max(t.bpm for s in score.sections.values() for t in s.tempo) == 150
    # 開始 BPM を倍にすると、カーブ全体が倍になる
    scaled = genre.__class__().plan(__import__("random").Random(1))
    scaled.bpm = 48
    from mod_weaver.framework.compose import compose
    s2 = compose(genre, scaled, seed=1, features=frozenset())
    assert s2.sections["climax"].tempo[-1].bpm == 63 and s2.sections["movement_c"].tempo[-1].bpm == 35


def test_free_jazz_texture_rules_and_tempo_commands_reach_the_module():
    genre = _genre("free-jazz")
    plan, score = _score(genre)
    from mod_weaver.genres_next import free_jazz as fj

    for e in all_notes(score, "bass"):
        assert fj.BASS_REG[0] <= e.pitch <= fj.BASS_REG[1]
    for e in all_notes(score, "piano"):
        assert fj.CLUSTER_REG[0] <= e.pitch <= fj.CLUSTER_REG[1]
    assert all_notes(score, "sax") and not [s for s in score.sections if s != "climax" and notes(score, s, "sax")]
    rs = grid_of(genre, score, plan)
    tempo = {c.fx[1] for pat in rs.patterns for r in range(pat.rows) for c in (pat.get(r, ch) for ch in range(pat.channels))
             if c.fx is not None and c.fx[0] == "F" and c.fx[1] >= 32}
    assert len(tempo) >= 20          # 連続的に変わっている（挿入先が無い row を飛ばしても多数残る）


# ---------------------------------------------------------------- orchestral

def test_orchestral_is_eight_channels_only_with_a_detuned_second_violin():
    genre = _genre("orchestral")
    assert genre.mod_channels == {8: 1}
    assert resolve("mod", None, genre, 1).budget == 8
    with pytest.raises(ChannelCountError):
        resolve("mod", 4, genre, 1)
    assert genre.instruments["vln2"].tune_cents == 37.5 and genre.instruments["vln2"].volume == 44
    assert genre.instruments["vla"].patch.shift == -7 and genre.instruments["vc"].patch.shift == -12
    assert genre.instruments["cb"].patch.shift == -24
    _plan, score = _score(genre)
    layout = lanesmod.compute_layout(genre, score, 8)
    assert [l.insts for l in layout.lanes[6:8]] == [("horn", "trumpet"), ("timpani", "cymbal")]


def test_orchestral_sections_add_voices_and_climax_uses_trumpet_timpani_and_cymbal():
    genre = _genre("orchestral")
    _plan, score = _score(genre)
    present = {s: {p for p, ev in sec.parts.items() if any(isinstance(e, NoteEvent) for e in ev)}
               for s, sec in score.sections.items()}
    strings = {"vln1", "vln2", "vla", "vc", "cb"}
    assert present["intro"] == present["resolution"] == strings
    assert present["theme"] == strings | {"ww"} and present["development"] == strings | {"ww", "brass"}
    assert present["climax"] == strings | {"ww", "brass", "perc"}
    assert {e.inst for e in notes(score, "development", "brass")} == {"horn"}
    assert {e.inst for e in notes(score, "climax", "brass")} == {"trumpet"}
    cym = [e for e in notes(score, "climax", "perc") if e.inst == "cymbal"]
    assert [(e.step, e.prio) for e in cym] == [(0, 2)]
    assert sorted(e.step for e in notes(score, "climax", "perc", "timpani")) == [0, 8, 16, 24, 32, 40, 48, 56]


# ---------------------------------------------------------------- maqam

def test_maqam_neutral_degrees_are_written_as_half_semitones_and_reach_finetune_variants():
    genre = _genre("maqam")
    fractions = set()
    for seed in SEEDS:
        plan, score = _score(genre, seed)
        for e in all_notes(score, "oud"):
            fractions.add(round(e.pitch % 1, 3))
    assert fractions == {0.0, 0.5}
    plan, score = _score(genre, 1)
    rs = grid_of(genre, score, plan)
    # 12.5 セント刻みの finetune（±4 ＝ ±50 セント）の変種サンプルが作られ、中立音程の音はそれで鳴る
    assert {s.finetune for s in rs.samples} >= {0} and {s.finetune for s in rs.samples} & {4, -4}


def test_maqam_usul_and_coda():
    genre = _genre("maqam")
    _plan, score = _score(genre)
    perc = notes(score, "ostinato_a", "perc")
    assert {(e.inst, e.step % 16) for e in perc} == {("dum", 0), ("tek", 4), ("dum", 10), ("tek", 12)}
    assert not notes(score, "taqsim", "perc") and not notes(score, "taqsim", "qanun")
    coda = notes(score, "coda", "oud")
    assert [(e.step, e.pitch) for e in coda] == [(48, genre_bass(score))]
    assert [(e.inst, e.step) for e in sorted(notes(score, "coda", "qanun"), key=lambda e: e.step)] == [("qanun", 48)]
    assert genre.form == ("taqsim", "ostinato_a", "ostinato_b", "taqsim", "ostinato_a", "coda")


def genre_bass(score):
    return score.sections["coda"].plan.measures[-1].chord.bass


# ---------------------------------------------------------------- march

def test_march_structure_and_snare_roll():
    genre = _genre("march")
    assert genre.mod_channels == {4: 1}
    plan, score = _score(genre)
    assert score.order == ["intro", "a", "a2", "a", "a2", "trio", "trio2", "trio", "trio2", "coda"]
    for sec in score.sections.values():
        assert sec.plan.meter.steps == 8 and len(sec.plan.measures) == 8
    assert plan.sections["trio"].key_offset == 5 and plan.sections["a"].key_offset == 0
    sd = [e for e in notes(score, "a", "drums", "sd") if e.step >= 56]
    assert sorted(e.step for e in sd) == [60, 61, 62, 63] and all(e.prio == 2 for e in sd)
    assert [e.vel for e in sorted(sd, key=lambda e: e.step)] == [36, 43, 51, 58]
    horn = [e for e in notes(score, "a", "harm", "horn") if e.arts]
    assert horn and all(isinstance(e.arts[0], Arpeggio) for e in horn)


# ---------------------------------------------------------------- nostalgic

def test_nostalgic_structure_register_and_fade():
    genre = _genre("nostalgic")
    for seed in SEEDS:
        plan, score = _score(genre, seed)
        assert score.order == ["intro", "a", "b", "a", "outro"] and plan.bpm in genre.tempo_choices
        mel = [e.pitch for e in notes(score, "b", "melody")]
        assert mel and pitch.parse("C-2") <= min(mel) and max(mel) <= pitch.parse("B-3")   # サビはオクターブ頭打ち
        assert not notes(score, "intro", "drums") and not notes(score, "intro", "bass")
        assert {e.inst for e in notes(score, "outro", "drums")} == {"kick"}
        fade = [(e.step, e.value) for e in score.sections["outro"].parts["pad"] if isinstance(e, Automation)]
        assert fade == [(56, 18), (60, 8), (63, 0)]
        fills = {(e.inst, e.step % 16) for e in notes(score, "a", "drums") if e.step // 16 == 3 and e.step % 16 >= 14}
        assert fills == {("hihat", 14), ("snare", 15)}
    assert {i for i in _genre("nostalgic").instruments} == {"kick", "snare", "hihat", "bass", "musicbox", "pad"}


# ---------------------------------------------------------------- suspense

def test_suspense_slow_alias_structure_and_shock_grammar():
    assert resolve_id("suspense") == "suspense-slow" and get_genre("suspense").id == "suspense-slow"
    genre = _genre("suspense-slow")
    for seed in SEEDS:
        plan, score = _score(genre, seed)
        assert score.order == ["hush", "pedal", "phrygian", "pedal", "shock", "aftermath"]
        ped = plan.sections["pedal"].extra
        assert ped["dropout"] in (1, 2) and ped["anvil"] in (None, ped["dropout"] + 1)
        anvils = [e.step for e in notes(score, "pedal", "pulse", "anvil")]
        assert anvils == ([] if ped["anvil"] is None else [ped["anvil"] * 16])
        # 衝撃の直前 8 step に heart・pizz・lead の発音を置かない
        for a in anvils:
            for part, inst in (("pulse", "heart"), ("lead", "pizz"), ("lead", "lead")):
                assert not [e for e in notes(score, "pedal", part, inst) if a - 8 <= e.step < a]
        # 心拍・持続音が途切れる小節は、心拍も drone も鳴らない（drone は off）
        d = ped["dropout"] * 16
        assert not [e for e in notes(score, "pedal", "pulse", "heart") if d <= e.step < d + 16]
        assert [e.step for e in score.sections["pedal"].parts["drone"] if isinstance(e, NoteOff)] == [d]
        # shock: 2小節目は全 step 無音（持続音を止める）、3小節目で swoosh、4小節目で anvil
        shock = score.sections["shock"]
        assert not [e for p in shock.parts.values() for e in p if isinstance(e, NoteEvent) and 16 <= e.step < 32]
        assert {(p, e.inst) for p, ev in shock.parts.items() for e in ev if isinstance(e, NoteOff)} \
            == {("drone", "drone"), ("texture", "strings"), ("lead", "lead")}
        sw = notes(score, "shock", "pulse", "swoosh")
        assert [e.step for e in sw] == [32 + 16 - round(0.9 / (15 / plan.bpm))]
        assert [e.step for e in notes(score, "shock", "pulse", "anvil")] == [48]


def test_suspense_slow_portamento_and_vibrato_are_written():
    genre = _genre("suspense-slow")
    glides = vib = 0
    for seed in SEEDS:
        _plan, score = _score(genre, seed)
        glides += sum(1 for e in notes(score, "phrygian", "lead") if any(isinstance(a, Glide) for a in e.arts))
        vib += sum(1 for e in notes(score, "shock", "lead") if any(isinstance(a, Vibrato) for a in e.arts))
    assert glides and vib


def test_suspense_chase_silence_runs_and_stabs():
    genre = _genre("suspense-chase")
    plan, score = _score(genre)
    assert score.order == ["intro", "a1", "a2", "b", "a1", "b", "climax", "outro"]
    assert plan.sections["a1"].kind == plan.sections["a2"].kind == "a"
    assert (plan.sections["a1"].extra["dropout"], plan.sections["a2"].extra["dropout"]) == (2, 1)
    for name in ("a1", "a2"):
        ex = plan.sections[name].extra
        sil, anvil = ex["dropout"], ex["anvil"]
        assert anvil == sil + 1 and len(ex["stabs"]) == 2
        lo, hi = sil * 16 + 8, anvil * 16
        for part in ("pulse", "drone", "texture", "lead"):
            late = [e for e in notes(score, name, part) if lo <= e.step < hi]
            if part != "drone":                       # drone は無音の直前（step 7）に最後の 1 音を寄せる
                assert not late, (name, part)
        for row in ex["stabs"]:
            assert not (hi - 8 <= row < hi + 8) and not (lo <= row < hi)
        assert [e.step for e in notes(score, name, "pulse", "anvil")] == [hi]
        # 余韻の間は心拍を置かない
        assert not [e for e in notes(score, name, "pulse", "heart") if hi < e.step < hi + 8]
    assert [e.step for e in notes(score, "climax", "pulse", "anvil")] == [0, 16, 32, 48]
    assert notes(score, "climax", "pulse", "swoosh") and len(notes(score, "outro", "pulse", "heart")) == 4


# ---------------------------------------------------------------- swing-jazz

def test_swing_jazz_swing_form_and_walking_bass():
    from mod_weaver.framework.plan import Swing

    genre = _genre("swing-jazz")
    assert genre.swing == Swing(14, 10) and genre.mod_channels == {4: 1}
    plan, score = _score(genre)
    assert score.order == ["intro", "a", "a", "b", "a", "solo_a", "solo_a", "solo_b", "solo_a", "a", "a", "b", "out"]
    for sec in score.sections.values():
        assert sec.plan.swing == Swing(14, 10) and sec.plan.steps == 64 and len(sec.plan.measures) == 8
    assert not notes(score, "intro", "drums") and not notes(score, "intro", "sax")
    # 次の和音の根音へ向かう（各小節の最後の音が次の小節の根音に折り返した音）
    from mod_weaver.core.pitch import fold_into_range
    from mod_weaver.genres_next.swing_jazz import BASS_REG

    for name in ("a", "b", "solo_a"):
        sec = score.sections[name]
        for mp in sec.plan.measures:
            last = [e for e in notes(score, name, "bass") if mp.start <= e.step < mp.start + 8][-1]
            assert last.pitch == fold_into_range(mp.next_chord.bass, *BASS_REG)
    # sax の装飾（Retrig）は裏拍にだけ
    ret = [e for e in all_notes(score, "sax") if any(isinstance(a, Retrig) for a in e.arts)]
    assert all(e.step % 2 == 1 for e in ret)
    tag = [e for e in notes(score, "out", "drums") if e.step >= 56]
    assert [(e.inst, e.vel) for e in tag] == [("ride", 64)]


# ---------------------------------------------------------------- prog-rock

def test_prog_rock_odd_meters_and_the_straight_chorus():
    genre = _genre("prog-rock")
    plan, score = _score(genre)
    steps = {n: [m.steps for m in sec.plan.measures] for n, sec in score.sections.items()}
    assert steps["verse"] == steps["intro"] == steps["outro"] == [14, 14, 10]
    assert steps["breakdown"] == [10] * 6 and steps["chorus"] == [16] * 4
    kicks = [e.step for e in notes(score, "verse", "drums", "kick")]
    assert len(kicks) == 7 + 7 + 5 and kicks[:7] == [0, 2, 4, 6, 8, 10, 12]
    assert not notes(score, "chorus", "gtr") and not notes(score, "intro", "drums") and notes(score, "chorus", "lead")
    assert {e.inst for e in notes(score, "verse", "drums")} == {"kick", "snare", "crash"}
    assert [e.step for e in notes(score, "verse", "drums", "snare")] == [6, 20, 32]
    rs = grid_of(genre, score, plan)
    for pat in rs.patterns:
        assert pat.rows == 64


# ---------------------------------------------------------------- trap

def test_trap_meter_hat_rolls_and_808_glides():
    genre = _genre("trap")
    plan, score = _score(genre)
    assert score.order == ["intro", "verse", "verse", "hook", "hook", "half_time", "hook", "hook", "outro"]
    for sec in score.sections.values():
        assert sec.plan.meter.steps == 32 and sec.plan.steps == 64
    assert {p for p, ev in score.sections["intro"].parts.items() if ev} == {"hat"}
    assert {p for p, ev in score.sections["hook"].parts.items() if ev} == {"bass808", "hat", "snare", "lead"}
    bass = notes(score, "hook", "bass808")
    assert [e.step % 32 for e in bass] == [0, 8, 12, 20] * 2
    assert all(any(isinstance(a, Glide) for a in e.arts) == (e.step % 32 != 0) for e in bass)
    assert [e.vel for e in bass if e.step % 32 == 0] == [60, 60]
    rolls = [e for s in score.sections for e in notes(score, s, "hat", "hat_c") if any(isinstance(a, Retrig) for a in e.arts)]
    assert rolls and all(a.ticks == 3 for e in rolls for a in e.arts if isinstance(a, Retrig))
    assert {e.step % 32 for e in notes(score, "hook", "hat", "hat_o")} == {28}
    assert [e.vel for e in notes(score, "outro", "bass808")] == [18, 18]


def test_trap_glides_become_portamento_only_while_the_previous_808_still_sounds():
    from mod_weaver.core.native import RCell  # noqa: F401

    genre = _genre("trap")
    seen_glide = seen_plain = 0
    for fmt, budget in (("mod", 4), ("it", None), ("xm", None), ("s3m", None)):
        plan, score = _score(genre, 1)
        rs = grid_of(genre, score, plan, fmt, budget)
        glide_letter = "3" if fmt in ("mod", "xm") else "G"
        lane = 0
        rows = [(p, r) for p in rs.patterns for r in range(p.rows)]
        for pat, r in rows:
            c = pat.get(r, lane)
            if c.fx is not None and c.fx[0] == glide_letter and c.note is not None:
                seen_glide += 1
                assert 1 <= c.fx[1] <= 255
            elif c.note is not None and c.fx is None:
                seen_plain += 1
    assert seen_glide and seen_plain


# ---------------------------------------------------------------- future-bass

def test_future_bass_sidechain_slices_and_structure():
    from mod_weaver.framework.genre import Sidechain

    genre = _genre("future-bass")
    assert genre.mix == (Sidechain(("kick", "clap"), ("sub",), 0.25, 3), Sidechain(("kick", "clap"), ("chord",), 0.35, 4))
    plan, score = _score(genre)
    assert score.order == ["intro_chop", "intro_chop", "buildup", "drop", "drop", "breakdown", "drop", "drop", "outro"]
    chops = notes(score, "intro_chop", "vox")
    assert chops and all(len(e.arts) == 1 and isinstance(e.arts[0], Offset) and e.vel is None for e in chops)
    assert {round(e.arts[0].fraction * 6) for e in chops} <= set(range(6))
    assert sorted({e.step % 16 for e in notes(score, "drop", "kick", "clap")}) == [4, 12]
    assert {e.step % 16 for e in notes(score, "buildup", "kick", "clap")} == {2, 6, 10, 14}
    assert not notes(score, "breakdown", "kick") and notes(score, "breakdown", "sub")
    drop_vol = {e.vel for e in notes(score, "drop", "sub")}
    out_vol = {e.vel for e in notes(score, "outro", "sub")}
    assert drop_vol == {56} and out_vol == {12}
