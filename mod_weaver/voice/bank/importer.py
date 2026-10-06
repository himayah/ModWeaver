"""取り込み（``modweaver_voice.py check`` / ``import``。VOCAL_DESIGN.md §5.3.3）。"""
from __future__ import annotations

import hashlib
import statistics
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from ...errors import VoiceBankError
import dataclasses

from . import cache, credit, otoini, prefixmap
from .cut import cut
from .loopfind import find_loop
from .pitch import estimate_f0, hz_to_midi
from .resample import resample
from .wavio import read_wav

TARGET_RATE = 44100
PEAK_TARGET = 0.85


@dataclass
class CheckResult:
    style: str
    entries: int
    cv: list
    skipped: list = field(default_factory=list)       # (別名, 理由)
    bad_lines: list = field(default_factory=list)
    missing_wavs: list = field(default_factory=list)
    notes: list = field(default_factory=list)


def check(folder: Path) -> CheckResult:
    oto = folder / "oto.ini"
    if not oto.is_file():
        raise VoiceBankError(f"{oto}: oto.ini not found")
    entries, bad = otoini.load(oto)
    cv, skipped, seen = [], [], set()
    for e in entries:
        if not otoini.is_cv_alias(e.alias):
            skipped.append((e.alias, "VCV/CVVC alias (v1 imports CV only)"))
        elif e.alias in seen:
            skipped.append((e.alias, "duplicate alias (first one is used)"))
        else:
            seen.add(e.alias)
            cv.append(e)
    missing = sorted({e.wav for e in cv if not (folder / e.wav).is_file()})
    style = otoini.detect_style([e.alias for e in cv])
    res = CheckResult(style, len(entries), cv, skipped, bad, missing)
    if not cv:
        res.notes.append("no CV aliases: this bank (VCV/CVVC only) is not supported yet")
    if style == "mixed":
        res.notes.append("alias style is mixed; set 'alias_style' / 'alias_map' in modweaver.json")
    return res


def _fingerprint(folder: Path, files: list[str]) -> str:
    h = hashlib.sha256()
    for name in ["oto.ini"] + sorted(set(files)):
        h.update(name.encode("utf-8"))
        h.update(hashlib.sha256((folder / name).read_bytes()).digest())
    return h.hexdigest()


def import_bank(folder: Path, *, id_override: str = "", rate: int = TARGET_RATE,
                progress: Optional[Callable[[str], None]] = None) -> tuple[cache.BankInfo, str]:
    """取り込んで ``.modweaver/`` を書く。戻り値: (情報, report.txt の本文)。"""
    meta = credit.load_meta(folder, id_override)
    res = check(folder)
    if not res.cv:
        raise VoiceBankError("no importable CV aliases in oto.ini")
    wavs: dict[str, tuple[int, list[float]]] = {}
    syls: dict[str, cache.Syl] = {}
    pcms: dict[str, list[float]] = {}
    found: list[tuple[str, Optional[int], cache.Syl]] = []      # (基の別名, prefix.map の音域, Syl)
    pm_entries: list = []
    pm_path = folder / "prefix.map"
    pm_bad: list[str] = []
    if pm_path.is_file():
        pm_entries, pm_bad = prefixmap.parse(otoini.decode(pm_path.read_bytes(), "prefix.map"))
    report = [f"voice: {meta.id}", f"alias style: {res.style}"]
    warn = [f"missing wav: {w}" for w in res.missing_wavs]
    warn += [f"oto.ini {b}" for b in res.bad_lines]
    unloop, f0s, quality = [], [], []
    for e in res.cv:
        if e.wav in res.missing_wavs:
            continue
        if e.wav not in wavs:
            wavs[e.wav] = read_wav(folder / e.wav)
        src_rate, x = wavs[e.wav]
        seg, pre = cut(x, src_rate, e)
        if len(seg) < 2:
            warn.append(f"{e.alias}: empty after cut (offset/cutoff)")
            continue
        if src_rate != rate:
            seg = resample(seg, src_rate, rate)
            pre = round(pre * rate / src_rate)
        pre = min(pre, len(seg) - 1)
        vowel = seg[pre:]
        peak = max((abs(v) for v in vowel), default=0.0) or max(abs(v) for v in seg) or 1.0
        gain = PEAK_TARGET / peak
        seg = [v * gain for v in seg]
        f0 = estimate_f0(seg[pre:], rate)
        lr = find_loop(seg, rate, pre, f0)
        data = lr.data
        key = f"{len(pcms):04d}.pcm"
        base, pid = prefixmap.split_alias(e.alias, pm_entries) if pm_entries else (e.alias, None)
        found.append((base, pid, cache.Syl(base, key, len(data), pre, lr.loop, f0, round(peak, 5), lr.mismatch)))
        pcms[key] = data
        if f0:
            f0s.append(f0)
        if lr.loop is None:
            unloop.append(f"{e.alias} ({lr.reason})")
        elif lr.mismatch is not None and lr.mismatch > 0.35:
            quality.append(f"{e.alias} (mismatch {lr.mismatch:.2f})")
        if progress:
            progress(e.alias)
    if not found:
        raise VoiceBankError("nothing could be imported:\n  " + "\n  ".join(warn))
    warn += pm_bad
    pitches, pitch_hz, variants = _group_pitches(found, syls)
    home = statistics.median(f0s) if f0s else None
    info = cache.BankInfo(meta.id, meta.lang, rate, home, _fingerprint(folder, list(wavs) + (["prefix.map"] if pm_entries else [])),
                          meta.credit, meta.credit_required, meta.terms_url, meta.terms_checked, syls,
                          pitches, pitch_hz, variants)
    report.append(f"imported: {len(syls)} syllables @ {rate} Hz")
    if pitches:
        report.append("pitch ranges (prefix.map): " + ", ".join(f"MIDI {p} ({hz:.0f} Hz)" for p, hz in zip(pitches, pitch_hz)))
    report.append("home F0: " + (f"{home:.1f} Hz (MIDI {hz_to_midi(home):.1f})" if home else "unknown"))
    report.append(f"skipped aliases: {len(res.skipped)}")
    report += [f"  {a}: {why}" for a, why in res.skipped[:50]]
    report.append(f"no loop (one-shot): {len(unloop)}")
    report += [f"  {u}" for u in unloop]
    if quality:
        report.append(f"loop quality poor: {len(quality)}")
        report += [f"  {q}" for q in quality]
    if warn:
        report.append("warnings:")
        report += [f"  {w}" for w in warn]
    text = "\n".join(report) + "\n"
    cache.save(folder, info, pcms, text)
    return info, text


def _group_pitches(found, syls: dict) -> tuple[tuple, tuple, dict]:
    """取り込んだ (基の別名, 音域, Syl) から、``syls``（基の別名 → Syl）を埋め、多音高なら (pitches, pitch_hz, variants) を返す。
    多音高 = 音域が 2 種類以上ある（prefix.map に当たらない別名は「既定」の 1 つの音域）。単一音高は ``((), (), {})``。"""
    pids = {pid for _b, pid, _s in found}
    if len(pids) < 2:
        for base, _pid, s in found:
            syls.setdefault(base, s)
        return (), (), {}
    f0_of: dict = {}
    for _b, pid, s in found:
        if s.f0:
            f0_of.setdefault(pid, []).append(s.f0)
    med = {pid: statistics.median(v) for pid, v in f0_of.items()}
    # 既定の音域（pid=None）は、代表 f0 に近い MIDI note を名前にする（prefix.map の音域と重なれば同じ音域として扱う）
    ids = {pid: (pid if pid is not None else round(hz_to_midi(med[pid])) if pid in med else 0) for pid in pids}
    order = sorted(pids, key=lambda p: med.get(p, 0.0))
    pitches = tuple(ids[p] for p in order)
    pitch_hz = tuple(med.get(p, 0.0) for p in order)
    variants = {}
    for base, pid, s in found:
        s = dataclasses.replace(s, pitch=ids[pid])
        variants[f"{base}@{ids[pid]}"] = s
    mid = len(pitches) // 2                                          # 単一音高として使う版（audition・一覧）は中央の音域
    have: dict[str, dict[int, cache.Syl]] = {}
    for base, pid, _s in found:
        have.setdefault(base, {})[pitches.index(ids[pid])] = variants[f"{base}@{ids[pid]}"]
    for base, by_idx in have.items():
        syls[base] = by_idx[min(by_idx, key=lambda i: abs(i - mid))]
    return pitches, pitch_hz, variants
