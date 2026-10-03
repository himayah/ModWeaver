"""新ジャンル14（NEW_GENRES_DESIGN.md）の個別検査と、共有部品 ``genres/_ornament.py`` の単体検査。

全ジャンル共通の検査（I1〜I3・全パートが鳴る・全予算×全形式）は ``test_ported_genres_all.py`` が NEW_GENRES を含めて行う。
ここは「そのジャンルらしさの手がかり」（音階・拍子・ハネ・系統・構成・テンポの動き・装飾の規則）を Score の言葉で固定する。
"""
from __future__ import annotations

import pytest

from mod_weaver.core.pitch import MODES
from mod_weaver.framework import registry
from mod_weaver.framework.compose import compose, resolve_plan
from mod_weaver.framework.plan import Meter, Swing
from mod_weaver.framework.score import Arpeggio, Glide, NoteEvent, Retrig
from mod_weaver.genres._ornament import retime
from tests.framework.test_ported_genres_all import NEW_GENRES

registry.discover("mod_weaver.genres")


def _genre(gid):
    return registry.GENRE_REGISTRY[gid]()


def _score(gid, seed=1):
    g = _genre(gid)
    plan = resolve_plan(g, seed=seed)
    return g, plan, compose(g, plan, seed=seed, features=frozenset())


def _notes(score, part, section=None):
    out = []
    for name, sec in score.sections.items():
        if section is None or name == section:
            out += [e for e in sec.parts.get(part, []) if isinstance(e, NoteEvent)]
    return out


def _family_of(gid, family, seeds=range(1, 40)):
    for s in seeds:
        g, plan, score = _score(gid, s)
        if plan.extra.get("family") == family:
            return g, plan, score
    pytest.fail(f"{gid}: family {family!r} never chosen in seeds {seeds}")


# ---------------- 音階（core/pitch.MODES の追加） ----------------

@pytest.mark.parametrize("name", ["ritsu", "ryukyu", "miyakobushi", "phrygian_dominant", "ukrainian_dorian"])
def test_added_modes_are_well_formed(name):
    iv = MODES[name]
    assert iv[0] == 0 and list(iv) == sorted(set(iv)) and iv[-1] < 12


def test_added_modes_have_the_expected_intervals():
    assert MODES["ryukyu"] == (0, 4, 5, 7, 11)
    assert MODES["miyakobushi"] == (0, 1, 5, 7, 8)
    assert MODES["ritsu"] == (0, 2, 5, 7, 9)
    assert MODES["phrygian_dominant"] == (0, 1, 4, 5, 7, 8, 10)


# ---------------- 共有部品 ----------------

@pytest.mark.parametrize("gid", ["enka", "gagaku", "mood-kayo", "rokyoku"])
def test_scoop_pickup_precedes_every_glide_and_is_not_skeleton(gid):
    """Glide の付いた音の直前（1 step 前）に、dur=None・prio=0 の低い音（ピックアップ）が必ずある。"""
    checked = 0
    for seed in (1, 2, 3):
        _g, _plan, score = _score(gid, seed)
        for sec in score.sections.values():
            for events in sec.parts.values():
                notes = [e for e in events if isinstance(e, NoteEvent)]
                by_step = {(e.inst, e.step): e for e in notes}
                for e in notes:
                    if any(isinstance(a, Glide) for a in e.arts):
                        pick = by_step.get((e.inst, e.step - 1))
                        assert pick is not None and pick.dur is None and pick.prio == 0 and pick.pitch < e.pitch
                        checked += 1
    assert checked > 0


def test_tremolo_keeps_the_head_note_and_marks_continuations():
    _g, _plan, score = _family_of("russian-folk", "lyric")
    notes = _notes(score, "lead")
    heads = [e for e in notes if e.prio != 0]
    conts = [e for e in notes if e.prio == 0]
    assert conts and all(e.dur == 1 and any(isinstance(a, Retrig) for a in e.arts) for e in conts)
    assert any(e.dur and e.dur > 1 for e in heads)          # 頭の音は元の音価のまま


def test_heterophony_ignores_pickups_and_continuations():
    _g, _plan, score = _family_of("russian-folk", "dance")
    lead_steps = {(n, e.step) for n, sec in score.sections.items() for e in sec.parts["lead"]
                  if isinstance(e, NoteEvent) and e.prio != 0}
    for name, sec in score.sections.items():
        for e in sec.parts.get("domra", []):
            if isinstance(e, NoteEvent):
                assert (name, e.step) in lead_steps          # delay=0: 骨格の音の位置にだけ重なる


def test_retime_rebuilds_steps_and_validates_swing():
    g, plan, _score_ = _score("celtic", 1)
    sp = next(iter(plan.sections.values()))
    retime(sp, Meter(12, 6, (6, 8)))
    assert [m.steps for m in sp.measures] == [12] * len(sp.measures)
    assert [m.start for m in sp.measures] == [12 * i for i in range(len(sp.measures))]
    from mod_weaver.errors import PlanError
    with pytest.raises(PlanError):
        retime(sp, Meter(8, 2), Swing(12, 8))               # 8分の格子（steps_per_beat=2）の和は 24 でなければならない


def test_with_tempo_is_relative_to_the_start_bpm_and_follows_tempo_override():
    g = _genre("gagaku")
    for start in (46, 58):
        plan = resolve_plan(g, seed=1)
        plan.bpm = start
        score = compose(g, plan, seed=1, features=frozenset())
        ha = score.sections["ha"].tempo
        assert ha[0].bpm == start and ha[-1].bpm == round(start * 1.2)
        assert all(32 <= t.bpm <= 255 for sec in score.sections.values() for t in sec.tempo)


# ---------------- ジャンル別 ----------------

def test_celtic_families_have_their_meters_and_swing():
    _g, plan, _ = _family_of("celtic", "jig")
    assert all(sp.meter == Meter(12, 6, (6, 8)) and sp.swing is None and all(m.steps == 12 for m in sp.measures)
               for sp in plan.sections.values())
    _g, plan, _ = _family_of("celtic", "hornpipe")
    assert all(sp.swing == Swing(18, 6) and sp.meter.steps == 8 for sp in plan.sections.values())
    _g, plan, _ = _family_of("celtic", "reel")
    assert all(sp.swing is None and sp.meter.steps == 16 for sp in plan.sections.values())


def test_celtic_is_a_set_of_aabb_tunes_with_a_drone():
    g, plan, score = _score("celtic", 2)
    assert plan.order == ["intro", "a", "a", "b", "b", "c", "c", "d", "d", "outro"]
    assert {len(m) for m in (plan.sections[n].measures for n in "abcd")} == {8}
    assert _notes(score, "drone", "a")[0].dur is None


def test_russian_folk_dance_accelerates_each_variation():
    g, plan, score = _family_of("russian-folk", "dance")
    start = plan.bpm
    seq = [score.sections[n].tempo[0].bpm for n in ("theme", "var1", "var2", "var3")]
    assert seq == sorted(seq) and len(set(seq)) == 4 and seq[0] == start
    assert plan.order[-3:] == ["var3", "var3", "outro"]
    _g, plan, _ = _family_of("russian-folk", "lyric")
    assert "var1" not in plan.order and plan.sections["theme"].meter.steps == 12


def test_okinawan_families():
    _g, plan, _ = _family_of("okinawan", "shima")
    assert all(sp.swing is None and sp.meter == Meter(16, 4) for sp in plan.sections.values())
    assert plan.order == ["intro", "a", "a", "b", "a", "outro"] and 76 <= plan.bpm <= 92
    g, plan, score = _family_of("okinawan", "kachashi")
    assert all(sp.swing == Swing(16, 8) for sp in plan.sections.values())
    assert plan.order[-3:] == ["c", "c", "outro"]
    assert score.sections["c"].tempo[0].bpm > score.sections["a"].tempo[0].bpm


def test_okinawan_uses_only_the_ryukyu_scale_and_chord_tones():
    g, plan, score = _score("okinawan", 3)
    sp = plan.sections["a"]
    allowed = {(sp.tonic + i) % 12 for i in MODES["ryukyu"]}
    for m in sp.measures:
        allowed |= {t % 12 for t in m.chord.chord_tones}
    for e in _notes(score, "lead", "a"):
        if e.prio != 0 and e.dur != 1:
            assert round(e.pitch) % 12 in allowed


def test_enka_final_chorus_modulates_up_a_whole_tone_and_aizuchi_is_in_the_last_bar():
    g, plan, score = _score("enka", 1)
    assert (plan.sections["chorus2"].tonic - plan.sections["chorus"].tonic) % 12 == 2
    assert plan.order.index("chorus2") == len(plan.order) - 2
    sec = score.sections["verse"]
    steps = [e.step for e in sec.parts["aizuchi"] if isinstance(e, NoteEvent)]
    last = sec.plan.measures[-1]
    assert steps and all(last.start + 10 <= s < last.start + last.steps for s in steps)


def test_rokyoku_has_melody_gaps_and_a_wide_tempo_swing():
    g, plan, score = _score("rokyoku", 1)
    for name in ("tanka1", "tanka2", "maku"):
        assert not _notes(score, "lead", name)
    assert _notes(score, "lead", "fushi1") and _notes(score, "taiko", "fushi3")
    tempi = [t.bpm for sec in score.sections.values() for t in sec.tempo]
    assert max(tempi) / min(tempi) > 1.5


def test_gagaku_sho_is_a_sustained_chord_and_tempo_rises_jo_ha_kyu():
    g, plan, score = _score("gagaku", 1)
    sho = _notes(score, "sho", "jo")
    assert sho and all(e.chord and e.dur is None for e in sho)
    assert plan.order == ["jo", "ha", "kyu", "outro"]
    end = {n: score.sections[n].tempo[-1].bpm for n in plan.order[:3]}
    assert end["jo"] < end["ha"] < end["kyu"]
    assert len({e.step for e in _notes(score, "drums", "jo")}) <= 8 + 1          # 序は拍が疎


def test_gagaku_scale_choice_covers_ryo_and_ritsu():
    seen = set()
    for seed in range(1, 30):
        _g, plan, _ = _score("gagaku", seed)
        seen.add(plan.summary[1].split(":")[1].strip().split(" ")[0])
    assert seen == {"Ryo", "Ritsu"}


def test_mood_kayo_last_chorus_goes_up_a_semitone_and_families_differ_in_tempo():
    _g, plan, _ = _family_of("mood-kayo", "rumba")
    assert 92 <= plan.bpm <= 108
    assert (plan.sections["chorus2"].tonic - plan.sections["chorus"].tonic) % 12 == 1
    _g, plan, _ = _family_of("mood-kayo", "chacha")
    assert 112 <= plan.bpm <= 124


def test_trance_range_and_gate_rhythm():
    g, plan, score = _score("trance", 1)
    assert 136 <= plan.bpm <= 142
    gate = _notes(score, "gate", "drop")
    steps = {e.step % 16 for e in gate}
    assert steps == {0, 3, 6, 8, 11, 14}
    kicks = {e.step % 16 for e in _notes(score, "drums", "drop") if e.inst == "kick"}
    assert kicks == {0, 4, 8, 12}


def test_gospel_shout_swing_shout_changes_and_double_time_vamp():
    g, plan, score = _score("gospel-shout", 1)
    assert all(sp.swing == Swing(16, 8) for sp in plan.sections.values())
    assert score.sections["vamp"].tempo[0].bpm >= round(plan.bpm * 1.2)
    claps = {e.step % 8 for e in _notes(score, "drums", "verse") if e.inst == "clap"}
    assert claps == {2, 6}


def test_klezmer_uses_freygish_and_ukrainian_dorian_and_accelerates_in_the_coda():
    g, plan, score = _score("klezmer", 1)
    assert g.harmony.mode == "phrygian_dominant" and g.harmony.mode_by_quality == {"min": "ukrainian_dorian"}
    assert score.sections["coda"].tempo[-1].bpm > round(plan.bpm * 1.25)
    assert score.sections["intro"].tempo[0].bpm < plan.bpm                         # ドイナ風の導入はゆっくり
    assert all(sp.meter == Meter(8, 4, (2, 4)) for sp in plan.sections.values())


def test_tango_marcato_and_chan_chan_ending():
    g, plan, score = _score("tango", 1)
    bass = {e.step % 16 for e in _notes(score, "bass", "a")}
    assert bass == {0, 4, 8, 12}
    last = plan.sections["outro"].measures[-1]
    final = [e for e in _notes(score, "bando", "outro") if last.start <= e.step < last.start + last.steps]
    assert [e.step - last.start for e in final] == [0, 6] and all(e.vel >= 60 for e in final)


def test_fado_has_no_drums_and_slows_down_at_the_end():
    g, plan, score = _score("fado", 1)
    assert not any(p.kit for p in g.parts)
    assert score.sections["outro"].tempo[-1].bpm < plan.bpm


def test_baroque_melody_is_a_descending_sequence_and_the_coda_ends_with_a_trill():
    g, plan, score = _score("baroque", 1)
    a = [e for e in _notes(score, "lead", "a")]
    per_bar = [[e.pitch for e in a if m.start <= e.step < m.start + m.steps] for m in plan.sections["a"].measures]
    assert all(len(b) == 8 for b in per_bar)
    firsts = [b[0] for b in per_bar[:6]]
    assert firsts == sorted(firsts, reverse=True) and firsts[0] > firsts[-1]
    last = [e for e in _notes(score, "lead", "coda") if e.arts]
    assert last and isinstance(last[-1].arts[0], Arpeggio)
    # 強弱は区間ごとの段階（a は強、b は弱）
    assert plan.sections["a"].intensity > plan.sections["b"].intensity


def test_baroque_circle_of_fifths_progression():
    g, plan, _ = _score("baroque", 1)
    assert [m.chord.label for m in plan.sections["coda"].measures] == ["i", "iv", "VII", "III", "VI", "iio", "V7", "i"]


def test_debayashi_has_no_chords_and_speeds_up_on_each_repeat():
    g, plan, score = _score("debayashi", 1)
    assert len({m.chord.label for sp in plan.sections.values() for m in sp.measures}) == 1
    assert not any(e.chord for sec in score.sections.values() for ev in sec.parts.values()
                   for e in ev if isinstance(e, NoteEvent))
    seq = [score.sections[n].tempo[0].bpm for n in ("a1", "a2", "a3")]
    assert seq == sorted(seq) and len(set(seq)) == 3
    assert plan.sections["a1"].kind == plan.sections["a3"].kind == "a"
    hish = _notes(score, "hishigi", "intro")
    assert any(isinstance(a, Glide) for e in hish for a in e.arts)                # ヒシギは上昇音


# ---------------- 新ジャンル全体 ----------------

@pytest.mark.parametrize("gid", sorted(NEW_GENRES))
def test_new_genre_metadata_and_wording(gid):
    g = _genre(gid)
    assert g.category in ("genre", "style") and g.description and g.description_en and len(g.title) <= 20
    # 実在の曲・流派・人名を名乗らない（説明文は一般名だけ）。「風」「style」などで再現ではないことを示すか、素材名だけを挙げる
    assert any(w in g.description for w in ("風", "演歌", "トランス", "ゴスペル", "タンゴ", "バロック", "ファド", "ケルト", "クレズマー")) \
        or gid in ("trance", "enka", "fado", "tango", "baroque", "klezmer")


@pytest.mark.parametrize("gid", sorted(NEW_GENRES))
def test_new_genre_is_deterministic_and_varies_with_the_seed(gid):
    _g, _p, a = _score(gid, 5)
    _g, _p, b = _score(gid, 5)
    _g, _p, c = _score(gid, 6)
    def flat(s):
        return [(n, p, e) for n, sec in s.sections.items() for p, ev in sec.parts.items() for e in ev]
    assert flat(a) == flat(b) and flat(a) != flat(c)
