"""旧 ``BandProfile`` 系ジャンルの**宣言部**を新しい ``Genre`` の宣言に機械変換する（FRAMEWORK_REDESIGN.md §15.1・§15.2）。

旧クラスを実行時に読み込み、クラス属性（KIT・CHORD_KITS・CHANNELS・ARRANGEMENTS・SECTIONS・GROOVES・各 Spec …）から
``mod_weaver/genres_next/<module>.py`` のソースを生成する。**上書きしたメソッド（extra_measure・compose_measure 等。
グループ B）は変換しない**。生成後に手で書く（ファイル先頭の TODO 行に上書きしたメソッドを列挙する）。

    python tools/port_band_genre.py pop cool dreamy      # 指定した id を変換
    python tools/port_band_genre.py --all-declarative     # 上書きの無いジャンルをすべて

変換の規則は設計書 §15.1 の表。パートの並びは CHANNELS（最も厚い編成）の並び、``min_channels`` は ``ARRANGEMENTS`` で
そのパートが初めて現れる編成、打楽器の論理チャンネルは 1 つの Part（``Kit.groups``＝論理チャンネル）にまとめる。
"""
from __future__ import annotations

import argparse
import dataclasses
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from mod_weaver import profiles  # noqa: E402
from mod_weaver.core.synth_presets import PRESETS  # noqa: E402
from mod_weaver.profiles import band_common as bc  # noqa: E402
from mod_weaver.profiles.registry import PROFILE_REGISTRY  # noqa: E402

OUT = ROOT / "mod_weaver" / "genres_next"
SPEC_PART = {"BASS": "bass", "COMP": "comp", "LEAD": "lead", "PAD": "pad", "ARP": "arp", "FX": "fx"}


# ============================================================
# 値 → ソース
# ============================================================

def code(v) -> str:
    """Python のリテラル／dataclass を、既定値と同じ項目を省いて書く。"""
    if isinstance(v, bc.ChordSpec):
        extra = "".join(f", {k}={code(getattr(v, k))}" for k in ("bass", "label") if getattr(v, k) not in (None, ""))
        return f"C({v.root}, {v.quality!r}{extra})".replace("'", '"')
    if dataclasses.is_dataclass(v) and not isinstance(v, type):
        parts = []
        for f in dataclasses.fields(v):
            val = getattr(v, f.name)
            if f.default is not dataclasses.MISSING and val == f.default:
                continue
            if f.default_factory is not dataclasses.MISSING and val == f.default_factory():
                continue
            parts.append(f"{f.name}={code(val)}")
        return f"{type(v).__name__}({', '.join(parts)})"
    if isinstance(v, frozenset):
        return "frozenset({" + ", ".join(code(x) for x in sorted(v, key=repr)) + "})" if v else "frozenset()"
    if isinstance(v, dict):
        return "{" + ", ".join(f"{code(k)}: {code(x)}" for k, x in v.items()) + "}"
    if isinstance(v, tuple):
        inner = ", ".join(code(x) for x in v)
        return f"({inner},)" if len(v) == 1 else f"({inner})"
    if isinstance(v, list):
        return "[" + ", ".join(code(x) for x in v) + "]"
    if isinstance(v, str):
        return '"' + v.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return repr(v)


def hit_runs(groove) -> str:
    """打点の列を ``hits(...)`` の連結に戻す（連続する同じ (楽器, 音量, 確率, 音高の有無) をまとめる。順序は保つ）。"""
    runs, cur = [], None
    for h in groove:
        key = (h.key, h.vol, h.prob, h.note is not None)
        if cur and cur[0] == key:
            cur[1].append(h)
        else:
            cur = (key, [h])
            runs.append(cur)
    out = []
    for (key, vol, prob, has_note), hs in runs:
        rows = tuple(h.row for h in hs)
        args = [code(key), code(rows), code(vol)]
        if prob != 1.0 or has_note:
            args.append(code(prob))
        if has_note:
            args.append("notes=" + code(tuple(h.note for h in hs)))
        out.append("hits(" + ", ".join(args) + ")")
    return " + ".join(out) if out else "()"


def preset_source(patch) -> tuple[str, str]:
    """(プリセットのキー, 差分の引数列)。"""
    for k, p in PRESETS.items():
        if p == patch:
            return k, ""
    fields = [f.name for f in dataclasses.fields(patch)]
    best = min(PRESETS.items(), key=lambda kp: sum(getattr(patch, n) != getattr(kp[1], n) for n in fields))
    k, p = best
    diff = {n: getattr(patch, n) for n in fields if getattr(patch, n) != getattr(p, n)}
    if len(diff) > 4:
        raise SystemExit(f"no close preset for patch {patch.name!r} (closest {k!r}, {len(diff)} fields differ)")
    return k, ", " + ", ".join(f"{n}={code(v)}" for n, v in diff.items())


def _safe(name: str, suffix: str) -> str:
    """エコー・層のパート名が標準のパート名（pad など）と衝突しないようにする。"""
    return name + suffix if name in (*SPEC_PART.values(), "drums") else name


# ============================================================
# 変換
# ============================================================

def convert(cls) -> str:
    gid = cls.id
    chans = list(cls.CHANNELS)
    names = [c.name for c in chans]
    arrs = {n: [(f.name, f.sources, dict(f.priority)) for f in folds] for n, folds in cls.ARRANGEMENTS.items()}
    budgets = sorted(arrs)

    # ---- 論理チャンネル → パート ----
    owner: dict[int, str] = {}
    for spec_attr, part in SPEC_PART.items():
        spec = getattr(cls, spec_attr)
        if spec is not None:
            owner[spec.channel] = part
    drum_idx = sorted(set(cls.DRUM_CHANNEL.values()))
    for i in drum_idx:
        owner[i] = "drums"
    echo_parts = {}
    for e in cls.ECHO:
        echo_parts[e.dst] = e
        owner[e.dst] = _safe(chans[e.dst].name, " echo")
    layer_parts = {}
    for l in cls.LAYERS:
        layer_parts[l.channel] = l
        owner[l.channel] = _safe(chans[l.channel].name, " layer")
    missing_idx = [i for i in range(len(chans)) if i not in owner]
    missing = [names[i] for i in missing_idx]
    todo = [f"論理チャンネル {missing} を鳴らすパートが宣言に無い（上書きメソッドで鳴らす）"] if missing else []
    # 上書きメソッドで鳴らすチャンネルは、チャンネル名のパートとして土台だけ作る（ジェネレータは手で書く）
    for i in missing_idx:
        owner[i] = names[i]

    def part_min(idxs) -> int:
        if not arrs:
            return 0
        first = None
        for n in budgets:
            if any(names[i] in src for i in idxs for _nm, src, _p in arrs[n]):
                first = n
                break
        if first is None:
            return budgets[-1] + 1
        return 0 if first == budgets[0] else first

    part_idxs: dict[str, list[int]] = {}
    for i in range(len(chans)):
        part_idxs.setdefault(owner[i], []).append(i)

    # ---- 楽器 ----
    gm = cls.gm_voices
    lines_inst = []
    for k, patch in cls.KIT:
        key, diff = preset_source(patch)
        lines_inst.append(f'        "{k}": _inst("{key}", {code(gm[k])}{diff}),')
    for prefix, (patch, _strum) in cls.CHORD_KITS.items():
        key, diff = preset_source(patch)
        any_q = next(k for k in cls._sample_keys if k.startswith(prefix + "_"))
        lines_inst.append(f'        "{prefix}": _inst("{key}", {code(gm[any_q])}{diff}),')

    imports_gens = {"Groove", "hits"} if cls.DRUM_CHANNEL else set()
    parts_src = []

    def pan_of(i):
        return chans[i].pan

    order = sorted(part_idxs, key=lambda p: min(part_idxs[p]))
    for p in order:
        idxs = part_idxs[p]
        mc = part_min(idxs)
        mcs = f", min_channels={mc}" if mc else ""
        if p == "drums":
            groups, prio, group_pan = [], {}, {}
            for i in idxs:
                keys = tuple(k for k in chans[i].keys if cls.DRUM_CHANNEL.get(k) == i)
                groups.append((chans[i].name, keys))
                prio.update({k: v for k, v in chans[i].priority if k in keys})
            part_pan = pan_of(idxs[0])
            group_pan = {chans[i].name: pan_of(i) for i in idxs if pan_of(i) != part_pan}
            single = None
            for n in budgets:
                for fname, src, fp in arrs[n]:
                    if len([s for s in src if s in [names[i] for i in idxs]]) > 1:
                        base = {k: prio.get(k, 1) for _g, ks in groups for k in ks}
                        single = {**base, **{k: v for k, v in fp.items() if k in base}}
            kit = f"kit=Kit(groups={code(tuple(groups))}"
            if prio:
                kit += f",\n                     priority={code(prio)}"
            if single is not None:
                kit += f",\n                     single_priority={code(single)}"
            if group_pan:
                kit += f",\n                     group_pan={code(group_pan)}"
            kit += ")"
            late = dict(cls.LATE)
            extra = ""
            if late:
                extra += f", late={code(late)}"
            if cls.HUMANIZE != 4:
                extra += f", humanize={cls.HUMANIZE}"
            parts_src.append(f'        Part("drums", Groove(GROOVES{extra}), pan={part_pan},\n'
                              f'             {kit}{mcs}),')
            continue
        i = idxs[0]
        pan = pan_of(i)
        if p in SPEC_PART.values() and getattr(cls, next(a for a, n in SPEC_PART.items() if n == p)) is None \
                and i not in echo_parts and i not in layer_parts:
            parts_src.append(f'        # TODO: Part("{p}", <ジェネレータ>, pan={pan}{mcs})  ← 上書きメソッドで鳴らしていた')
            continue
        if p == "bass":
            s = cls.BASS
            gen = f'BassLine("{s.key}", kind="{s.kind}", vol={s.vol})'
            imports_gens.add("BassLine")
        elif p == "comp":
            s = cls.COMP
            strum = cls.CHORD_KITS[s.key][1] if s.key in cls.CHORD_KITS else 0.0
            extra = (f", chordal=False" if not s.chordal else "") + (f", wobble={s.wobble}" if s.wobble else "") \
                + (f", strum_ms={strum}" if strum else "")
            gen = f'Comp("{s.key}", kind="{s.kind}", vol={s.vol}{extra})'
            imports_gens.add("Comp")
        elif p == "lead":
            s = cls.LEAD
            extra = (f", vibrato={s.vibrato:#04x}" if s.vibrato else "")
            gen = (f'Lead("{s.key}", {code(s.rules)}, LEAD_MOTIFS,\n'
                   f'                   vol={s.vol}, gate={s.gate}{extra})')
            imports_gens.add("Lead")
        elif p == "pad":
            s = cls.PAD
            gen = f'Pad("{s.key}", vol={s.vol}' + (", chordal=False" if not s.chordal else "") + ")"
            imports_gens.add("Pad")
        elif p == "arp":
            s = cls.ARP
            gen = f'Arp("{s.key}", register={code(cls.ARP_REGISTER)}, steps={code(tuple(s.rows))}, vol={s.vol}' \
                + (f', pattern="{s.pattern}"' if s.pattern != "up" else "") + ")"
            imports_gens.add("Arp")
        elif p == "fx":
            s = cls.FX
            gen = f'Fx("{s.key}", every={s.every}, vol={s.vol})'
            imports_gens.add("Fx")
        elif i in echo_parts:
            e = echo_parts[i]
            src_part = owner[e.src]
            gen = f"Echo(delay={e.delay}, ratio={e.ratio}" + (f", repeats={e.repeats}" if e.repeats != 1 else "") + ")"
            parts_src.append(f'        Part("{p}", {gen}, follow="{src_part}", pan={pan}{mcs}),')
            imports_gens.add("Echo")
            continue
        elif i in layer_parts:
            l = layer_parts[i]
            extra = (", chordal=True" if l.chordal else "") + \
                (f", register={code(l.register)}" if l.register != (14, 26) else "")
            gen = f'Layer("{l.key}", vol={l.vol}{extra})'
            parts_src.append(f'        Part("{p}", {gen}, follow="{l.follow}", pan={pan}{mcs}),')
            imports_gens.add("Layer")
            continue
        else:
            parts_src.append(f'        # TODO: Part("{p}", <ジェネレータ>, pan={pan}{mcs})  ← 上書きメソッドで鳴らしていた')
            continue
        parts_src.append(f'        Part("{p}", {gen}, pan={pan}{mcs}),')

    # ---- 区間 ----
    rpm, rpb = cls.rows_per_measure, cls.rows_per_beat
    beats = rpm / rpb
    sig = (int(beats), 4) if beats == int(beats) else (4, 4)
    meter_default = (rpm, rpb) == (16, 4)
    measures = cls.MEASURES_PER_PATTERN or 64 // rpm
    sec_lines = []
    for name, s in cls.SECTIONS.items():
        args = []
        if s.prog:
            args.append(f"prog={s.prog}")
        args.append(f"intensity={s.intensity}")
        if s.parts != bc.ALL_PARTS:
            ps = sorted(s.parts)
            args.append(f"parts=frozenset({code(set(ps))})" if ps else "parts=frozenset()")
            if args[-1].startswith("parts=frozenset({'"):
                args[-1] = args[-1].replace("'", '"')
        if s.groove != "main":
            args.append(f'groove="{s.groove}"')
        if s.key_offset:
            args.append(f"key_offset={s.key_offset}")
        if s.fill:
            args.append("fill=True")
        if s.crash:
            args.append("crash=True")
        if s.lead_motifs != "verse":
            args.append(f'motifs="{s.lead_motifs}"')
        if s.kind != name:
            args.append(f'kind="{s.kind}"')
        if not meter_default:
            args.append("meter=METER")
        if measures != 4:
            args.append(f"measures={measures}")
        sec_lines.append(f'        "{name}": Section({", ".join(args)}),')

    # ---- 組み立て ----
    h = cls
    imports_gens |= {"hits"} if cls.GROOVES else set()
    hdr = [f'"""{gid}（旧 genres/{Path(sys.modules[cls.__module__].__file__).name} の宣言を機械変換したもの。'
           f'FRAMEWORK_REDESIGN.md §15）。"""']
    hdr.append("from __future__ import annotations\n")
    if h.LEAD is not None:
        hdr.append("from ..core.composer import RhythmMotif, ScaleRules")
    hdr.append("from ..core.model import ChordSpec, GmVoice")
    hdr.append("from ..core.synth_presets import PRESETS")
    if imports_gens:
        hdr.append(f"from ..framework.gens import {', '.join(sorted(imports_gens))}")
    hdr.append("from ..framework.genre import Genre, Harmony, Instrument, Kit, Part, Section" +
               (", Sidechain" if cls.SIDECHAIN else ""))
    if not meter_default or cls.SWING:
        hdr.append("from ..framework.plan import Meter" + (", Swing" if cls.SWING else ""))
    hdr.append("from ..framework.registry import register_genre")
    body = ["", "C = ChordSpec", ""]
    body += ['', "def _inst(key: str, gm: GmVoice, **changes) -> Instrument:",
             "    patch = PRESETS[key]", "    if changes:", "        import dataclasses", "        patch = dataclasses.replace(patch, **changes)",
             "    return Instrument(patch=patch, gm=gm)", ""]
    if cls.GROOVES:
        body.append("GROOVES = {")
        for gname, gr in cls.GROOVES.items():
            body.append(f'    "{gname}": {hit_runs(gr)},')
        body.append("}")
    if h.LEAD is not None:
        body.append("LEAD_MOTIFS = {")
        for mname, ms in h.LEAD.motifs.items():
            body.append(f'    "{mname}": {code(tuple(ms))},')
        body.append("}")
    if not meter_default:
        body.append(f"METER = Meter({rpm}, {rpb}, {sig})")
    body.append("PROGRESSIONS = (")
    for pname, specs in cls.PROGRESSIONS:
        body.append(f'    ("{pname}", {code(tuple(specs))}),')
    body.append(")")
    reg = cls.REGISTERS
    reg_src = ""
    if reg != bc.BandProfile.REGISTERS:
        reg_src = f",\n        registers=Registers(bass={code(reg.bass)}, harmony={code(reg.harmony)}, melody={code(reg.melody)})"
    harmony = (f"Harmony(keys={code(cls.KEYS)}, mode=\"{cls.MODE}\"" +
               (f", mode_by_quality={code(cls.MODE_BY_QUALITY)}" if cls.MODE_BY_QUALITY else "") +
               f", progressions=PROGRESSIONS, n_progressions={cls.N_PROGRESSIONS}" +
               (", fixed=True" if cls.FIXED_PROGRESSIONS else "") + reg_src + ")")
    if reg_src:
        hdr.insert(2, "from ..core.harmony import Registers")
    cname = "".join(w.capitalize() for w in gid.replace("-", "_").split("_")) + "Genre"
    cls_lines = ["", "", "@register_genre", f"class {cname}(Genre):", f'    id = "{gid}"']
    if cls.aliases:
        cls_lines.append(f"    aliases = {code(cls.aliases)}")
    if cls.category != "genre":
        cls_lines.append(f'    category = "{cls.category}"')
    cls_lines += [f"    display_name = {code(cls.display_name)}", f"    description = {code(cls.description)}",
                  f"    description_en = {code(cls.description_en)}", f"    title = {code(cls.title)}",
                  f"    tempo_choices = {code(cls.tempo_choices)}"]
    if cls.tempo_range != (32, 255):
        cls_lines.append(f"    tempo_range = {code(cls.tempo_range)}")
    cls_lines += ["", "    instruments = {"] + lines_inst + ["    }", f"    harmony = {harmony}", "    sections = {"] + \
        sec_lines + ["    }", f"    form = {code(cls.FORM)}", "    parts = ("] + parts_src + ["    )"]
    if cls.SWING:
        s = cls.SWING
        cls_lines.append(f"    swing = Swing({s.long_speed}, {s.short_speed})")
    mod = dict(cls.channel_weights) if cls.ARRANGEMENTS else {len(chans): 1}
    cls_lines.append(f"    mod_channels = {code(mod)}")
    if cls.SIDECHAIN:
        rules = []
        for key, ch, ratio, rel in cls.SIDECHAIN:
            rules.append(f'Sidechain(triggers=("{key}",), targets=("{owner[ch]}",), ratio={ratio}, release_steps={rel})')
        cls_lines.append("    mix = (" + ", ".join(rules) + ",)")
    if todo:
        hdr.insert(1, "# TODO(F6): " + "; ".join(todo))
    return "\n".join(hdr + body + cls_lines) + "\n"


def overridden(cls) -> list[str]:
    base = {n for n, v in vars(bc.BandProfile).items() if callable(v) and not n.startswith("__")}
    return sorted(n for n, v in vars(cls).items() if callable(v) and not n.startswith("__") and n in base)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ids", nargs="*")
    ap.add_argument("--all-declarative", action="store_true")
    args = ap.parse_args()
    profiles.discover("mod_weaver.genres")
    ids = args.ids
    if args.all_declarative:
        ids = [g for g, c in PROFILE_REGISTRY.items()
               if issubclass(c, bc.BandProfile) and not overridden(c)]
    OUT.mkdir(exist_ok=True)
    for gid in ids:
        cls = PROFILE_REGISTRY[gid]
        ov = overridden(cls)
        src = convert(cls)
        if ov:
            src = src.replace('"""\nfrom __future__', f'"""\n# TODO(F6): 上書きメソッドの移植: {", ".join(ov)}\nfrom __future__', 1)
        path = OUT / (Path(sys.modules[cls.__module__].__file__).name)
        path.write_text(src, encoding="utf-8")
        print(f"{gid:16} -> {path.relative_to(ROOT)}" + (f"   (overrides: {', '.join(ov)})" if ov else ""))


if __name__ == "__main__":
    main()
