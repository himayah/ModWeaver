# ModWeaver 設計書

| 項目 | 内容 |
|:---|:---|
| 対象 | ModWeaver 1.1.0（`mod_weaver` パッケージ・`modweaver.py`） |
| 本書の範囲 | **現在の実装がどうなっているか**だけを書く。なぜそうなったか・過去の案・訂正・レビュー記録は [DESIGN_HISTORY.md](DESIGN_HISTORY.md) |
| 最終更新 | 2026-09-24（2026-09-21〜24 に書かれた設計書7本をこの2本に統合。統合前の原文は git 履歴で参照できる） |

---

## 0. 用語

| 用語 | 意味 |
|:---|:---|
| row | パターンの1行。既定の格子では16分音符（Speed 6 の 4 row = 1拍） |
| measure | ジャンルが定める小節。行数は `rows_per_measure`（または `ChordSlot.rows`） |
| pattern | 64 row のまとまり（ProTracker 標準）。可変小節のジャンルは 64 row 未満で `D00` により次へ進む |
| tracker note `t` | Period 表上の音（0=`C-1` … 35=`B-3`）。Cell に入る値 |
| logical note `n` | 意図した音高。`n = t + shift`（§3.1） |
| ジャンル／プロファイル | `GenreProfile` のサブクラス。ジャンル1つ＝`mod_weaver/genres/` の1ファイル |
| 実プレイヤー | ffmpeg 内蔵の libopenmpt（OpenMPT の再生エンジン）。自作ではない第三者の再生実装（§9.2） |

---

## 1. 概要と要件

### 1.1 目的

Python 標準ライブラリだけで、波形合成から作曲・シーケンス・ファイル出力までを行い、トラッカー音楽を自動生成する。
ジャンルごとの音楽理論の制約のもとで毎回違う曲を作り、seed で完全に再現できる。

### 1.2 機能要件

| ID | 要件 |
|:---|:---|
| FR-1 | `--genre` で47ジャンルから選んで生成する（区分: 気分・ジャンル・〜風。§6）。`random` / `r` なら指定できるジャンルからランダムに選ぶ（§8.3） |
| FR-2 | 同じ genre・seed・format・tempo からは常に同じファイルを出力する |
| FR-3 | 出力形式を `mod`（既定）/ `xm` / `s3m` / `it` / `midi` / `mp3` から選べる（§7） |
| FR-4 | テンポを BPM または範囲（範囲内からランダム）で指定できる。未指定ならジャンルが決める（§5.5） |
| FR-5 | ジャンルは `mod_weaver/genres/` に1ファイル置くだけで追加でき、core・engine・cli の変更は不要（§5.6） |
| FR-6 | 生成物を構造検査し、規格違反があればファイルを書かない（§9.1） |
| FR-7 | 引数なしなら使い方を表示する。`--list-genres`（ジャンル一覧）と `--version`（版と GitHub URL）を持つ（§8） |
| FR-8 | 画面表示（使い方・ジャンル一覧・実行結果）は日本語が既定で、`-e` / `--english` で英語になる（§8.5） |

### 1.3 非機能要件

| ID | 要件 |
|:---|:---|
| NFR-1 | 実行時の依存は Python 標準ライブラリのみ。例外は `--format mp3` の外部プログラム ffmpeg（libopenmpt・libmp3lame 入り） |
| NFR-2 | Python 3.10 以上（テストは 3.10 で実施。`str.removeprefix` 等 3.9 以降の機能を使っている） |
| NFR-3 | 1曲の生成は数秒以内（実測 1 秒未満） |
| NFR-4 | トラッカー形式は OpenMPT 等の実プレイヤーで正しく鳴ること（音高・長さ・テンポ・音割れなし）を自動テストで確認する（§9.2） |
| NFR-5 | 開発時の依存は pytest（`requirements-dev.txt`）。実プレイヤー検査には ffmpeg（libopenmpt）が要る（無ければ skip） |

### 1.4 ProTracker 由来の制約（内部表現の前提）

- Song の内部表現は ProTracker の Cell（note・sample・effect・param）を基本にし、他形式へはシリアライザで変換する（§7）。
- note は Period 表の36音（113〜856）。1セルに1エフェクト。sample は最大31、1サンプル ≤ 131070 byte（65535 word）、8-bit signed PCM。
- テンポは Speed（1 row の tick 数、既定 6）と BPM（`Fxx`, xx ≥ 32）。**1拍＝24 tick**（Speed 6 なら 4 row）を前提に BPM を解釈する。
- サンプルの再生レートは `C-3`（Period 214）で `3546895 / (2×214) ≈ 8287.14 Hz`（PAL Paula クロック）。

---

## 2. 全体構成

### 2.1 レイヤーと依存規則

```text
cli.py ──▶ engine.py ──▶ profiles/（仕組み: 基底・登録簿・補助）◀── genres/（ジャンル本体）
   │            │                    │                                    │
   └────────────┴────────────────────┴──────────────▶ core/（不変層）◀─────┘
```

- `core` は `profiles`・`genres`・`engine` を import しない。`genres` は `core` と `profiles`（基底・登録簿・補助）だけに依存する。
- `engine` は `profiles.base` と `core` に依存する。`cli` は `engine` と `profiles` に依存する。
- `core` 内: `pitch`（依存なし）← `dsp` ← `synth` ← `synth_presets`、`model` ← `harmony` ← `composer`。
  形式モジュール（`writer`・`verify`・`s3m`・`it`・`midi`・`render`・`timeline`・`effects`）は `model`・`pitch`・`formats` を参照する。
  `formats` は各形式モジュールを遅延 import する（循環回避）。

### 2.2 モジュール一覧

| モジュール | 役割 |
|:---|:---|
| `modweaver.py` / `mod_weaver/__main__.py` | 起動スクリプト（`cli.main` へ委譲）。`python modweaver.py` と `python -m mod_weaver` は同じ |
| `mod_weaver/__init__.py` | `__version__`（1.1.0）・`__url__` |
| `cli.py` | 引数解析・表示言語・バナー・終了コード（§8） |
| `engine.py` | 作曲の実行・テンポ・検査・書込（§5.3〜5.5） |
| `errors.py` | 例外階層（§8.7） |
| `profiles/base.py` | `GenreProfile` 基底（§5.1） |
| `profiles/registry.py` | 登録簿・`genres/` の自動検出（§5.6） |
| `profiles/nostalgic_samples.py`・`suspense_common.py`・`band_common.py` | ジャンル共通の補助（ジャンルではない）。`band_common` は第３段階の35ジャンルの骨格 `BandProfile`（§6.14） |
| `genres/*.py` | 47ジャンル（§6） |
| `core/pitch.py` | Period 表・音名・スケール・和音の型・微分音（§4.1） |
| `core/model.py` | Cell・CellGrid・SampleSpec・Song・計画系データ（§3） |
| `core/harmony.py` | 和音の具体化 `voice()`（§4.2） |
| `core/composer.py` | 旋律生成・リズム型・配置補助（§4.3） |
| `core/dsp.py` | 再生レート・PCM 化・波形/フィルタ/ループの基本関数（§4.4） |
| `core/synth.py` / `synth_presets/` | 音源合成（Patch 方式）とプリセット集（パッケージ。§4.5） |
| `core/groove.py` | スウィング・リトリガ・ノートディレイ（§4.6） |
| `core/structure.py` | ポリメトリックの行折返し（§4.7） |
| `core/mixer.py` | サイドチェイン・サンプルオフセット（§4.8） |
| `core/automation.py` | テンポカーブ・ポルタメント速度（§4.9） |
| `core/formats.py` | 出力形式の能力表・`WriteOptions`・チャンネルパン（§7.1） |
| `core/writer.py` | MOD・XM シリアライザ、原子的書込（§7.2〜7.3） |
| `core/verify.py` | MOD・XM の独立パーサと構造検査（§9.1） |
| `core/s3m.py` / `it.py` | S3M・IT のシリアライザ／パーサ／検査（§7.4〜7.5） |
| `core/effects.py` | MOD エフェクト → S3M/IT エフェクトの変換表（§7.6） |
| `core/timeline.py` | Song を tick 単位で解釈したイベント列と曲長（§7.7） |
| `core/midi.py` | SMF シリアライザ・`GmVoice`・検査（§7.7） |
| `core/render.py` | ffmpeg による MP3 化（§7.8） |

### 2.3 生成の流れ

```text
cli.main
 └─ engine.generate(profile, seed, out, tempo=, fmt=)
     ├─ formats.check_channels（形式のチャンネル上限）
     ├─ compose_song
     │   ├─ validate_profile → 乱数の用意 → build_samples（Instrument 化）
     │   ├─ plan(rng) →（--tempo があれば BPM を上書き）→ validate_plan
     │   ├─ 各 PatternPlan（作成順）: begin_pattern → 各 measure で compose_measure → blit → finalize_pattern
     │   │                           →（可変小節なら最終 row に D00）
     │   ├─ post_processors（スウィング・サイドチェイン等）
     │   └─ apply_tempo（tempo_policy="engine" のとき）
     ├─ serialize（形式ごと）→ verify（形式ごと。ERROR なら VerificationError、ファイルは書かない）
     └─ write_file（一時ファイル → os.replace の原子的書込）
```

### 2.4 設計原則

1. **Song は純粋データ**。`compose_song()` は I/O を持たず、テストは Song／バイト列を直接検査する。
2. **役割分担**: エンジンはテンポ挿入・pattern への転記・順序表・バイト化・検査・書込を持つ。ジャンルは音色・和声・リズム・フレーズ・パート間の配置を持つ。
3. **競合は宣言的に解決**: チャンネルの占有は `ChannelPlan` の許可サンプルと優先度で決め、暗黙の上書きに頼らない（nostalgic のみ旧来の上書き）。
4. **拡張は opt-in**: 新機能は既定値では何も変えない属性・後処理として足す。既存ジャンルの出力は機能追加で変わらない。
5. **形式中立の中間表現**: 作曲は出力形式を意識しない。形式差はすべてシリアライザが吸収する（§7）。
6. **第三者の実装で検証する**: 自作 writer を自作 parser で読み戻す検査だけでは、両者が同じ誤解を共有すると検出できない。形式の正しさは実プレイヤーで確かめる（§9.2）。
7. **core に固定カテゴリを増やさない**: 音色は直交する要素の組合せで表し（§4.5）、ジャンル固有の判断・参照データはジャンル側に置く。core に置くのは機械的な単位変換だけ。

---

## 3. データモデル（`core/model.py`・`core/pitch.py`）

### 3.1 音高

- **tracker note** `t`: 0=`C-1` … 35=`B-3`（Period 表の並び）。Cell に入る値。
- **logical note** `n`: 意図した音高。`f(n) = 65.4064 × 2^(n/12)` Hz、MIDI ノート番号の目安は `n + 36`。
- サンプルごとの `shift`（半音）で結ぶ: **`n = t + shift`**。発音時は `t = n − shift` が 0..35 に入る必要がある。
  これで「低音サンプルを C-3 で鳴らして 65 Hz を出す（`shift=−24`）」ことができ、36 音の制約を音域から切り離せる。
- **サンプルの内容周波数**: 生成レート `R = CLOCK / (2·PERIODS[rate_note])`。音高のあるサンプルは「`rate_note` の tracker note で発音すると logical note `rate_note + shift` が鳴る」ように波形を作る（内容周波数 `F = f(rate_note + shift)`、1周期のサンプル数 `spc = R/F`。どの n で鳴らしても spc は一定）。打楽器（`pitched=False`）は常に `rate_note` で発音し、内容を絶対 Hz で書く。例（`rate_note=C-3`、R=8287.14 Hz）:

  | サンプル | shift | F | spc | 発音 |
  |:---|:---|:---|:---|:---|
  | drone | −24 | 65.41 Hz | 126.7 | logical 0..11 を t=24..35 で |
  | tuba | −12 | 130.81 Hz | 63.4 | logical 0..11 を t=12..23 で |
  | strings / horn / section / pizz | 0 | 261.63 Hz | 31.68 | t = n |
  | lead / picc | +12 | 523.25 Hz | 15.84 | logical 12..47 を t=0..35 で |
- **実音 `sounding_hz`**: 合成は `dsp.sample_rate()`（実際の Paula 再生レートの半分）を基準に波形を作るため、実際に聞こえる高さは logical note と一致しない（ワンショットは1オクターブ上、ループはループ長に入れた周期数次第）。トラッカー形式は全形式が同じ規約で鳴るので問題にならない。絶対音高を書く MIDI だけは `synth.render()` が記録する `SampleSpec.sounding_hz`（`rate_note` で鳴らしたときの実音）から音高を求める（§7.7）。**`dsp.sample_rate()` を「直す」とトラッカー出力の全ジャンルの音が変わるので変えない。**

### 3.2 セルとグリッド

```python
@dataclass(frozen=True)
class Cell:
    note: Optional[int] = None     # tracker note（None=休符）
    sample: int = 0                # 0=指定なし, 1..31
    effect: int = 0                # 0..0xF
    param: int = 0                 # 0..0xFF
    vol: Optional[int] = None      # 0..64。effect/param と排他（併用は CellConflictError）
```

- `vol` はシリアライズ時に MOD の `Cxx` になる（S3M/IT は volume column）。音量と他のエフェクトは同じセルに置けない。
- `effect=0, param≠0` はアルペジオ（`0xy`）。`t + max(x, y) ≤ 35` を要求する（`Instrument.cell` と検査 V16 の二重検査）。
- `CellGrid`（`MeasureBuffer`・`Pattern` の共通基底）は任意の行数・チャンネル数を持てる。
  - `put(row, ch, cell)`: `strict=False` なら無条件上書き（nostalgic）。`strict=True` なら優先度（`ChannelRole.priority`、未記載 1、sample=0 は 0）で解決: 空なら書く／新>既存なら置換／新<既存なら書かない／同一セルなら何もしない／同値で異なるセルなら `ChannelConflictError`。音量だけのセル（OFF 等、優先度 0）は note を上書きしない。
  - `replace(row, ch, cell)`: 意図的な上書き（優先度を問わない。例: スネアロールが通常のスネアを置き換える）。
  - `insert_command(row, effect, param)`: その row の空きチャンネルにコマンドを書く。①空セルのうち最小番号 ②無ければ note を持つが vol・effect の無いセル（note はそのまま）。どちらも無ければ `ChannelConflictError`。`try_insert_command` は失敗を bool で返す版（§4.10）。
- 全セルの sample は `ChannelRole.allowed` に含まれる必要がある（違反は `ChannelConflictError`、出力では検査 V09）。
- `Pattern.blit(buf, base_row)` が measure の作業領域を pattern に転記する。

### 3.3 サンプル・曲・楽器

```python
@dataclass
class SampleSpec:
    name: str                      # ASCII ≤22
    data: bytes                    # 偶数長 ≥2、8-bit signed PCM（符号なし表現）
    volume: int                    # 0..64（既定音量）
    loop: Optional[tuple[int, int]] = None   # (start_words, length_words)。None はループなし
    rate_note: int = 24            # 生成レートを決める tracker note（既定 C-3）
    shift: int = 0                 # n = t + shift
    pitched: bool = True           # False: 常に rate_note で発音（打楽器）
    finetune: int = 0              # -8..7（1 単位 ≈ 7.8 セント）
    pan: int = 128                 # 0=左, 128=中央, 255=右（MOD 以外で使う）
    sounding_hz: Optional[float] = None   # rate_note で鳴らしたときの実音（§3.1）

@dataclass
class Song:
    title: str                     # ASCII ≤20
    samples: list[SampleSpec]      # 位置 = sample 番号 − 1
    patterns: list[Pattern]
    order: list[int]               # 1..128 エントリ
    instrument_names: tuple[str, ...] = ()   # build_samples() のキー（MIDI の音色表引き用）
```

`Instrument(slot, spec)` はジャンルがセルを作る唯一の入口:
- `cell(n, vol=, effect=, param=)`: 音高のある楽器なら `t = n − shift` を検査してサンプル番号付きのセルを返す。打楽器は n を無視して `rate_note` で鳴らす。`n=None` なら休符、音量/エフェクトだけのセルは原則 sample=0（ポルタメント継続などは slot を付ける）。
- `off()`: ループ音色の消音セル `Cell(vol=0)`。次の発音（サンプル番号付き）で既定音量に戻る。
- note を持つセルは必ずサンプル番号を持つ（プレイヤー間の音量リセットの差を避けるため。検査 V07）。

### 3.4 和声・構造・文脈

| 型 | 主なフィールド | 意味 |
|:---|:---|:---|
| `ChordSpec` | `root`（主音からの半音）, `quality`, `bass`, `label` | 調に依存しない和音記述 |
| `ChordDef` | `label`, `bass`, `harmony`, `chord_tones`, `scale_tones`, `arp`, `explicit` | 具体化済み（logical note）。`explicit=True` は手組み |
| `ChordSlot` | `chord`, `measures=1`, `rows=None` | 和音が何 measure 続くか。`rows` はその measure の行数（可変小節） |
| `PatternPlan` | `kind`, `slots`, `intensity`, `key_offset`, `extra` | pattern 1つの計画 |
| `SongPlan` | `bpm`, `patterns`（作成順）, `order`, `key_pc`, `summary` | 曲の計画。`summary` はバナーに出す行 |
| `PatternCtx` | `kind`, `index`, `bpm`, `key_pc`, `key_offset`, `intensity`, `is_first_in_order`, `extra` | フックに渡す pattern 文脈 |
| `MeasureCtx` | `pattern`, `measure_idx`, `n_measures`, `chord`, `chord_measure_offset`, `is_last`, `instruments`, `measure_rows` | フックに渡す measure 文脈 |
| `RngStreams` | `plan`, `drums`, `bass`, `harmony`, `melody` | 用途別の乱数（§5.2） |
| `ChannelRole` | `name`, `allowed`, `priority` | チャンネルの役割。`ChannelPlan` はその tuple（チャンネル数＝要素数） |

`PatternPlan` の行数: 各 slot の `(rows or rows_per_measure) × measures` の合計が 64（可変小節のジャンルは 1..64）。

---

## 4. core の機能

### 4.1 音高・スケール・微分音（`core/pitch.py`）

- `PERIODS`（36音、標準 PAL 表）、`NOTE_NAMES`、`name(t)` / `parse("C#2")`、`hz(n)`、`fold_into_range(n, lo, hi)`（オクターブ単位で音域へ折返し）、`nearest`、`lowest_note_with_pc`、`notes_with_pcs`、`note_for_hz`。
- `Scale(tonic_pc, intervals)` と `MODES`（ionian / aeolian / dorian / mixolydian / phrygian / dim_wh）。
- `CHORD_QUALITIES`（maj / min / dim / maj7 / m7 / dom7 など。半音オフセット）。
- 微分音: `FINETUNE_CENTS = 100/12.8`（finetune 1 単位 ≈ 7.8125 セント）。`MicroScale(tonic_pc, degrees_cents)` はセントで定義する音律（`degree_cents`・`absolute_cents(degree, tonic_note)`）。`resolve_micronote(cents)` は絶対セント → `(t, finetune)`（12平均律の最近傍＋残差を finetune に量子化）。`fine_portamento_param(period, cents)` は `E1x`/`E2x` の param。
  - finetune は 7.8 セント刻みなので、50 セント（クォータートーン）は近似になる（46.9／54.7 セント）。人の音程の弁別閾（5〜10 セント）から実用上許容する。
  - 恒常的な微分音は finetune 違いの派生サンプル（別の楽器スロット）で出す。`E1x`/`E2x` は一瞬のベンド（装飾）用。

### 4.2 和音の具体化（`core/harmony.py`）

`voice(spec, tonic_pc, scale, regs, *, arp=False, mode_by_quality=None) -> ChordDef`。`Registers(bass, harmony, melody)` は各声部の logical note の範囲（各 11 半音以上）。

1. `root_pc = (tonic_pc + root) % 12`、`bass_pc` はスラッシュ／ペダルなら `bass`、なければ root。
2. `bass = lowest_note_with_pc(bass_pc, *regs.bass)`、`harmony = lowest_note_with_pc(root_pc, *regs.harmony)`。
3. `chord_tones` = メロディ音域内の構成音、`scale_tones` = スケール音（`mode_by_quality` に該当 quality があればそのモード。例: dim→`dim_wh`）∪ 構成音。
4. `arp=True` なら第3音・第5音のオフセットから `0xy` の param（dim=`0x36`、min=`0x37`、maj/maj7/dom7=`0x47`）。
5. 音域の上限検査は `Instrument.cell` が担う。アルペジオを使うチャンネルの基音は `t ≤ 35 − max(x,y)`（最大 +7 なら t ≤ 28）に収める。

例（主音 C、`HARMONY_REG=(17,28)`、`BASS_REG=(0,11)`）:

| ChordSpec | bass | harmony | arp | chord_tones の pc |
|:---|:---|:---|:---|:---|
| `Cdim`（0, dim） | 0（C-1） | 24（C-3） | `0x36` | {0,3,6} |
| `Db/C`（1, maj, bass 0） | 0 | 25（C#3） | `0x47` | {1,5,8} |
| `B/C`（11, maj, bass 0） | 0 | 23（B-2） | `0x47` | {11,3,6} |

手組みの和音（nostalgic・maqam・free-jazz）は `ChordDef(explicit=True)` を直接作る。

### 4.3 作曲補助（`core/composer.py`）

- `RhythmMotif(rows, lengths=None)`: measure 内の発音 row と長さ。`lengths` 省略時は次の発音（または measure 末）まで。
- `ScaleRules`: `step_choices`, `leap_probability`, `leap_semitones`, `max_leap`, `leap_recovery`, `dissonance_weight`, `color_semitones`, `strong_nearest_prob`。
- `MelodyGenerator(rules, register, scale, rng, beat_rows=4)` と `bar(motif, chord, prev, cadence=, cadence_target=, octave_shift=)` → `(list[NoteEvent], 終端音)`:
  1. 強拍（`row % beat_rows == 0`）は直前音に近いコードトーン（確率 `strong_nearest_prob`、他は次点）
  2. 弱拍は確率 `dissonance_weight` でコード音から `color_semitones` 離れた音、それ以外は順次進行（確率 `1−leap_probability`）か跳躍
  3. 跳躍の後は `leap_recovery` なら逆向きに 1〜2 段
  4. `cadence=True` の最終音は `cadence_target`（無指定なら `chord_tones[0]`）
  5. 全音を `register` へ折返し。音量は強拍＝基準、弱拍＝基準−(4〜12)
- `NoteEvent(row, note, vol, dur)`。`articulate(buf, ch, events, inst, gate=1.0)`: ループ音色向けに、音価の終端（`row + max(1, round(dur×gate))`）が measure 内かつ次の発音より前のときだけ `off()` を置く（gate<1 でスタッカート）。
- `ramp(v0, v1, i, n)`（線形補間）、`fade_cells`（既存セルの vol を書換え）。
- nostalgic は `MelodyGenerator` を使わず、旧実装のアルゴリズムを移植したものを使う（§6.1）。

### 4.4 DSP 基本関数（`core/dsp.py`）

`CLOCK = 3546895.0`、`sample_rate(rate_note)`（C-3 → 8287.14、B-3 → 15694.2）、`clamp`、`pad_even`、`to_pcm`、`additive`（Nyquist 超の倍音を除外）、`partials_saw/square/triangle`、`exp_decay`、`adsr`、`noise_lp`、`one_pole_lp`、`diff_hp`、完全ループ用の `seamless_loop`（倍率×周期数が整数でなければ `SampleConstraintError`）・`seamless_terms`（整数周期数を直接指定）・`circular`（3周連結してフィルタし中央1周を返す）・`with_attack`（ループ本体末尾に半コサイン窓を掛けたアタック部を前置）・`loop_design`（設計時の補助。実行時は定数を使う）。

ループの設計値（`C-3` 基準）: 261.63 Hz の持続音は K=6 / L=190（+0.49 セント）、65.41 Hz の低音ドローンは K=6 / L=760、1オクターブ上は K=12 / L=190。ループ音色の手順の例（drone）: `seamless_loop(760, 6, partials)` → `circular(one_pole_lp)` → `tanh` → `with_attack(body, 60)` → `SampleSpec(loop=(30, 380))`（現在は `core/synth.py` の `Loop` がこれを行う）。

### 4.5 音源合成（`core/synth.py`・`core/synth_presets/`）

楽器ファミリーで分類せず、直交する要素の組合せで音色を書く。公開するのは `Patch` と `render(patch) -> SampleSpec` だけ。

- **Layer（信号源）**: `ToneLayer`（加算合成。倍音ごとに減衰率）、`PitchSweepLayer`（ピッチが下がる打撃音。絶対 Hz）、`NoiseLayer`（フィルタ付きノイズ。`decay_alpha` で減衰、`rise_power` で上昇）。`WeightedLayer` で重みを付けて混ぜる。`WeightedLayer.offset_ms` はレイヤーの鳴り始めを遅らせる（OneShot のみ。ギターのストローク用、§6.14）。
- **Finish（仕上げ）**: `OneShot(秒)`、`Loop(長さ, attack_samples=0)`（完全ループ。`attack_samples>0` ならアタック窓付き）。
- **Patch**: layers ＋ 後処理（`post_filter` → `decay_alpha` → `attack_ms` → `tail_fade_ms` → 正規化 `peak` → `saturate`）＋ サンプルの素性（`rate_note`・`shift`・`finetune`・`volume`・`pitched`）。
- 減衰・上昇のフィールドは全レイヤーで `Optional[float]`（None＝無効）。判別用の文字列フィールドは持たない。
- **制約**: `Loop` は `ToneLayer` のみ・`mult` は整数サイクル数のみ。`Patch.attack_ms` / `post_filter` / `decay_alpha` / `tail_fade_ms` は `OneShot` 専用。ループ音色の「息・擦弦ノイズ感」はノイズを混ぜず、隣接整数サイクル数のデチューンのうなりで出す。
- `pitched` は自動判定しない。`pitched=False` のとき `ToneLayer` の `mult` は絶対 Hz、True のとき `f0 = hz(rate_note + shift)` への比率（OneShot のみ）。
- **知覚寄りのファクトリ（1つのノブで複数パラメータを連動させる関数）は core に置かない**。連動が欲しければそのジャンルのファイル内にローカルな関数を書く。
- パンは音色ではなく配置の判断なので `Patch` には持たせず、`render()` の結果に `dataclasses.replace(spec, pan=...)` で付ける。
- `synth_presets/`（パッケージ）: 動作・音質を確認済みの `Patch` 114 個（`PRESETS`・`DESCRIPTIONS`、`find(keyword)`。どのモジュールの定数も `synth_presets.<定数名>` で参照できる）。`genre_kits.py` は第３段階より前の12ジャンルの音色（60個。`NOSTALGIC_*`・`SUSPENSE_*`・`MARCH_*`・`SWING_*`・`PROG_*`・`TRAP_*`・`MAQAM_*`・`MIN_*`・`FB_*`・`FREE_*`・`ORCH_*`）。第３段階の共有音色（54個）は**楽器の種類**で命名して系統ごとのモジュールに置き、複数のジャンルで使い回す: `drums.py`（`drum_*`）・`perc.py`（`perc_*`）・`bass.py`（`bass_*`）・`keys.py`（`keys_*`）・`guitar.py`（`gtr_*`）・`synths.py`（`syn_*`）・`pads.py`（`pad_*`・`vox_*`）・`orch.py`（`wind_*`・`str_*`・`brass_*`）・`fx.py`（`fx_*`。ノイズはループにできないので、長い OneShot を小節頭で鳴らし直す）。
- **新しい音色の作り方**: ① `find()` で近いプリセットを探す → ② `dataclasses.replace()` で差分を調整して `render()`・試聴 → ③ 良ければプリセットに登録。無ければ既存の3 Layer・2 Finish の組合せで `Patch` を組む（core に新しい Layer 種別を足さない）。

### 4.6 グルーヴ（`core/groove.py`）

- `SwingConfig(long_speed, short_speed)`: row の偶奇で Speed（`F0x`）を交互に書いてハネを作る。**`long + short = 48 / rows_per_beat`（1拍＝24 tick）でなければ表示 BPM どおりに鳴らない**: 8分格子（1拍＝2 row）は和 24（swing-jazz・jazz は 14/10＝1.4:1）、16分格子（1拍＝4 row）は和 12（例 7/5、neo-soul は 8/4）。
- `apply_swing(pattern, config)`: 全 row に `try_insert_command` で Speed を書く（空きの無い row はスキップ。§4.10）。`post_processors` から呼ぶ。`apply_tempo` より前に実行されるので、先頭 row には空きが2つ要る。
- `retrigger_param(ticks)` → `E9x`（1 row 内の連打。音量は変えられない）、`delay_param(ticks)` → `EDx`。

### 4.7 可変小節とポリメトリック（`core/structure.py` ほか）

- `GenreProfile.variable_meter=True` のジャンルは、`ChordSlot.rows` で measure ごとの行数を変えられ、pattern の合計が 64 未満でもよい。エンジンが最終 row に `D00`（次 pattern の row 0 へ）を `insert_command` で書く。`rows_per_measure` は「`ChordSlot.rows` 省略時の既定値」になり、64 の約数である必要はない。
- `polymetric_row(row, cycle_rows)` = `row % cycle_rows`。1 measure を各チャンネルの周期の最小公倍数の行数にし、チャンネルごとに周期で折り返して書く（minimalism）。

### 4.8 ミキサー（`core/mixer.py`）

- `SidechainRule(trigger_sample, target_channel, duck_ratio=0.3, release_rows=2)` と `apply_sidechain(song, rules)`: トリガのサンプルが鳴る row で対象チャンネルの音量を下げ、`release_rows` かけて戻す。**vol だけを操作**し、note/sample は保つ。vol 以外のエフェクトを持つセルには触れない。直前の音量が分からない（既定音量で鳴っている）ときはその回をスキップする。`post_processors` から呼ぶ。
- `sample_offset_param(offset_samples, length_words)` → `9xx` の param（256 サンプル単位）。

### 4.9 オートメーション（`core/automation.py`）

- `TempoCurve(start_bpm, end_bpm, start_row, end_row, curve_type="linear"|"ease_in"|"ease_out")` と `render_tempo_curve(pattern, curve)`: BPM が変わる row ごとに `Fxx` を `try_insert_command` で書く（開始 row も含むので初期 BPM の挿入を兼ねる）。`finalize_pattern` から呼び、`tempo_policy="profile"` と組み合わせる。
- `portamento_param(period_start, period_target, rows, ticks_per_row=6)` → `3xx` の速度。**`PERIODS` の添字は tracker note（`t = n − shift`）**で、logical note ではない。

### 4.10 row 単位コマンドの挿入規則

| 挿入するもの | 方法 | 空きが無いとき |
|:---|:---|:---|
| 初期テンポ（`apply_tempo`）、可変小節の `D00` | `insert_command` | `ChannelConflictError`（構造上必須なのでジャンルの不具合として止める） |
| スウィングの Speed、テンポカーブの `Fxx` | `try_insert_command` | その row だけスキップ（直前の値が続く。装飾は基本の生成を壊さない） |

したがってジャンルは、①曲の先頭 pattern の row 0 に1チャンネル（スウィングを使うなら2チャンネル）、②可変小節なら各 pattern の最終 row に1チャンネル、の空き（または note だけで vol・effect の無いセル）を残す責任を持つ。密な編成でも強拍に全パートを同時に置かないと、スキップが減る。

---

## 5. エンジンとジャンルの約束事

### 5.1 `GenreProfile` の属性（`profiles/base.py`）

| 属性 | 既定 | 意味 |
|:---|:---|:---|
| `id` | 必須 | `--genre` に指定する名前。`random` / `r` は予約語で使えない |
| `aliases` | `()` | 別名（例: suspense-slow の `suspense`） |
| `display_name` | 必須 | バナーの見出し |
| `description` | 必須 | **日本語の1行説明**（`--list-genres`・`--help` に出す） |
| `description_en` | 必須 | **英語の1行説明**（`-e` のとき使う） |
| `title` | 必須 | 出力ファイルのタイトル欄（ASCII ≤20。全形式共通） |
| `default_filename` | 必須 | 旧来の既定ファイル名（現在の CLI は使わない） |
| `tempo_choices` | 必須 | ジャンルが選ぶ BPM の候補（4分音符 BPM） |
| `tempo_range` | `(32, 255)` | `--tempo` で上書きできる範囲。極端なテンポで破綻するジャンルだけ狭める |
| `category` | `"genre"` | 一覧での区分: `"mood"`（気分）／`"genre"`（ジャンル）／`"style"`（〜風）。登録時に検査 |
| `rows_per_measure` | 16 | 1 measure の行数（64 の約数。可変小節なら既定値） |
| `rows_per_beat` | 4 | 表示 BPM の1拍に当たる row 数（16分格子＝4、8分格子の swing-jazz・jazz は 2）。スウィングの Speed の和（§4.6）と実プレイヤーのテンポ検査が使う |
| `channel_plan` | 必須 | チャンネル数と各チャンネルの許可サンプル・優先度 |
| `tempo_policy` | `"engine"` | `"engine"`: エンジンが先頭に `Fxx` を入れる／`"profile"`: ジャンルが自分で入れる |
| `rng_mode` | `"streams"` | `"single"`（nostalgic）／`"streams"`（§5.2） |
| `strict_buffers` | True | False なら無条件上書き（nostalgic） |
| `channel_pans` | None | MOD 以外でのチャンネルパン（0..255）。None なら §7.1 の規則 |
| `gm_voices` | `{}` | MIDI 用の GM 音色表（楽器名 → `GmVoice`）。**全楽器ぶんの宣言が必須** |
| `post_processors` | `()` | 全 pattern 作成後・テンポ挿入前に順に呼ぶ後処理 |
| `variable_meter` | False | True で可変小節（§4.7） |

フック（エンジンがこの順で呼ぶ）: `build_samples()`（dict の挿入順＝サンプル番号、キー＝楽器名。seed に依存しない）→ `plan(rng)` → pattern ごとに `begin_pattern(pctx, rng)` → measure ごとに `compose_measure(mctx, state, rng, buf)` → `finalize_pattern(pctx, pattern, state, rng)`。

`finalize_pattern` の `pattern.rows` は常に物理長 64。可変小節のジャンルが「実際に鳴る最終 row」を知りたいときは、自分の `ChordSlot.rows` の合計から求める。

### 5.2 乱数

- `rng_mode="single"`: 全フックに同じ `random.Random(seed)`。nostalgic は旧実装の乱数消費順を厳守する（§6.1）。
- `rng_mode="streams"`: 全フックに `RngStreams`。各ストリームは `random.Random(f"{seed}:{profile.id}:{name}")`（文字列 seed は Python バージョン間で安定）。`plan` 内は `rng.plan`、`compose_measure` 内はパートに応じて `drums`/`bass`/`harmony`/`melody`。**あるパートの変更が別パートの乱数列を変えない**。
- サンプル合成は seed に依存しない（各 Patch の固定 seed）。
- seed 省略時は `random.randint(100000, 999999)`。seed は負値も含む任意の整数。

### 5.3 エンジンの処理（`engine.py`）

- `compose_song(profile, seed, *, tempo=None) -> (Song, SongPlan)`（§2.3 の流れ）。`build_song` は Song だけを返す版。
- `apply_tempo(song, bpm)`: `order[0]` の pattern の row 0 に `F bpm` を `insert_command`。
- `write_options(profile, song, plan)`: 形式中立な付帯情報（チャンネルパン・初期 BPM・楽器名・GM 音色表・拍子）。
- `serialize(profile, song, plan, fmt)`: 検査なしのバイト化。
- `generate(profile, seed, out, *, verify=True, tempo=None, fmt="mod") -> Result`: 検査で ERROR があれば `VerificationError`（ファイルは書かない）。WARN は WARNING ログ。
- `Result(seed, path, song, plan, issues, tempo_request, fmt)`。

### 5.4 エンジンが検査する契約

| 検査 | 違反 |
|:---|:---|
| `rows_per_measure` が 64 の約数（可変小節なら正の数）、チャンネル数 1..64、`tempo_policy`・`rng_mode` の値、`tempo_range` ⊂ 32..255、`tempo_choices` ⊂ `tempo_range`、`title` が ASCII ≤20 | `PlanError` |
| BPM が `tempo_choices` 内（`--tempo` 上書き時は `tempo_range` 内）、各 pattern の行数合計（64、可変小節は 1..64）、`measures ≥ 1`、order の長さ 1..128・参照先・pattern 数 ≤ 64 | `PlanError` |
| サンプル: 偶数長・長さ上限・ループ範囲・ASCII 名・音量・パン | `SampleConstraintError` |
| セルの配置（許可サンプル・同値衝突） | `ChannelConflictError` |
| 発音の音域（`t ∈ 0..35`、アルペジオの上限） | `PitchRangeError` |
| 形式のチャンネル上限（例: S3M は 16） | `PlanError` |

### 5.5 テンポ指定

- `--tempo` の値は **4分音符の BPM**（1拍＝24 tick の `Fxx` の値）。全ジャンルがこの値どおりに鳴る（実プレイヤーで検査）。例外として trap は32分格子のハーフタイムなので、表示 BPM は trap の慣習どおり（150 → 体感 75）。free-jazz は開始時の BPM を決める（以降のテンポカーブは同じ比率で拡大縮小）。
- `TempoRequest(lo, hi)`（単一値は lo=hi）。全体の許容は 32..255。構文エラー・範囲外は引数エラー（終了コード 2）。
- `resolve_tempo`: ジャンルの `tempo_range` と重なる部分に切り詰める（一部だけ外れていれば WARNING、重ならなければ `TempoRangeError`＝終了コード 2）。範囲からの選択は専用ストリーム `random.Random(f"{seed}:{profile.id}:tempo")`。
- **ジャンルの `plan()` は従来どおり BPM を引いてから、その値を捨てる**。これで他の乱数消費が変わらず、「同じ seed・別テンポ」は「同じ曲の速さ違い」になる（suspense だけは効果音の配置 row を BPM から逆算するので配置も変わる）。未指定なら出力は変わらない。
- `tempo_range` を狭めているのは free-jazz（44..163。カーブを拡大縮小しても全点が 32..255 に収まる範囲）だけ。全ジャンル × BPM 32..255 × 3 seed の総当たりで、他に構造エラーになるジャンルは無い。

### 5.6 ジャンルの登録と追加

- `profiles/__init__.py` の import 時に `registry.discover()` が `mod_weaver/genres/` 直下の `.py`（`_` で始まるもの・サブパッケージを除く）をすべて import する。`@register_profile` の付いたクラスが登録簿に入る。CLI は起動ごとに新しいプロセスなので、`--list-genres` は毎回ディレクトリを調べ直す。
- import に失敗したファイル、何も登録しないファイルは WARNING を出して無視する（1ファイルの不具合で他のジャンルまで使えなくしない）。検出前から import 済みのモジュールは登録の有無を検査しない（ジャンルモジュールを直接 import すると、その途中で検出が走り、登録前のモジュールが返るため）。
- `register_profile` の検査（違反は `ValueError`）: `id` が空でない、`description`・`description_en` がどちらも空でない1行、`id`・別名が予約語（`random`・`r`）でない、id・別名の重複が無い。
- **1ファイル＝1ジャンル**（テストで検査）。ジャンル以外の補助モジュールは `mod_weaver/profiles/` に置く。
- 新しいジャンルに必要なもの: `@register_profile` 付きの `GenreProfile` サブクラス、日本語・英語の1行説明、全楽器の `gm_voices`、そして全形式で実プレイヤーの音割れ検査に通ること（§9.2）。
- `get_profile(name)`（別名も可。未登録は `ProfileNotFoundError`）、`list_profiles()`（id 順）、`resolve_id(name)`。

---

## 6. ジャンル

47ジャンル。§6.1〜6.13 は第３段階より前の12ジャンル（それぞれ固有の実装）、§6.14〜6.16 は第３段階で追加した35ジャンル（共通の骨格 `BandProfile` の上に宣言で書く）。

第３段階より前の12ジャンルの宣言値（コードから取得。第３段階の35ジャンルは §6.15）:

| id | 表示名 | BPM | 1 measure | ch | テンポ | 乱数 | 構成（order） |
|:---|:---|:---|:---|:---|:---|:---|:---|
| `nostalgic` | TwilightPad Procedural | 88–96（2刻み） | 16 row | 4 | profile | single | intro, a, b, a, outro |
| `suspense-slow`（別名 `suspense`） | Suspense Slow | 64–72（2刻み） | 16 | 4 | engine | streams | hush, pedal, phrygian, pedal, shock, aftermath |
| `suspense-chase` | Suspense Chase | 138–148（2刻み） | 16 | 4 | engine | streams | intro, a1, a2, b, a1, b, climax, outro |
| `march` | Military March | 118–122 | 8（2/4） | 4 | engine | streams | intro, a, a2, a, a2, trio, trio2, trio, trio2, coda |
| `swing-jazz` | Swing Jazz | 152–168（4刻み） | 8（4/4、1 row=8分） | 4 | engine | streams | intro, a, a, b, a, solo_a, solo_a, solo_b, solo_a, a, a, b, out |
| `prog-rock` | Prog Rock | 132–148（4刻み） | 可変（14/10/16） | 4 | engine | streams | intro, verse, verse, chorus, verse, breakdown, chorus, outro |
| `trap` | Trap | 140/145/150/155 | 32（32分格子） | 4 | engine | streams | intro, verse, verse, hook, hook, half_time, hook, hook, outro |
| `future-bass` | Future Bass | 148/150/152/155/160 | 16 | 4 | engine | streams | intro_chop×2, buildup, drop×2, breakdown, drop×2, outro |
| `maqam` | Maqam Rast | 84–96（4刻み） | 16 | 4 | engine | streams | taqsim, ostinato_a, ostinato_b, taqsim, ostinato_a, coda |
| `free-jazz` | Free Jazz | 96（開始値。範囲 44–163） | 16 | 4 | profile | streams | movement_a, movement_b, climax, movement_c |
| `minimalism` | Minimalism | 108–120（4刻み） | 可変（48） | 4 | engine | streams | phase0 … phase15 |
| `orchestral` | Orchestral | 76–88（4刻み） | 16 | 8 | engine | streams | intro, theme, development, climax, resolution |

音色の数値（Patch の値）は `core/synth_presets/` を正とする。以下は設計上の要点。

### 6.1 `nostalgic` — 夕暮れの Lo-Fi ビートとオルゴール

- 最初の実装（`twilight_pad.py`）の作曲ロジックをそのまま移植したジャンル。`tempo_policy="profile"`・`rng_mode="single"`・`strict_buffers=False` で旧来の挙動を保つ。
- **音色**（`nostalgic_samples.py`。全て `shift=0`）: kick（46 Hz へ指数降下するピッチの丸いキック）、snare（175 Hz の胴鳴り＋LP ノイズ）、hihat（金属共鳴＋HP ノイズ）、bass（サイン＋第2倍音）、musicbox（基音＋2・3倍音＋非整数 5.4 倍音の指数減衰）、pad（整数周期ループ K=32 / L=1024）、flute（奇数倍音のループ。定義のみで未使用だが7番を占有）。
- **チャンネル**: 1=drums（kick/snare/hihat）、2=bass、3=pad、4=melody（musicbox）。Amiga の定位 L/R/R/L に合わせ、左にリズムの芯と旋律、右にベースとパッド。
- **和声**: C メジャー／A マイナー。進行プール5種 `Step-Down`（Fmaj7–Em7–Dm7–Cmaj7）、`Royal Road`（Fmaj7–G7–Em7–Am7）、`Saudade`（Dm7–G7–Cmaj7–Am7）、`Journey`（Am7–Fmaj7–Cmaj7–G7）、`Canon Sunset`（Cmaj7–G7–Am7–Em7）。Theme A と B に異なる進行を割り当てる。手組みの `ChordDef(explicit=True)`。
- **構成**: 作成順 `[intro(A), a(A), b(B, サビ), outro(A)]`、order `[0,1,2,1,3]`。
- **`plan()` の乱数消費順（厳守）**: `idx_a = randrange(5)` → `idx_b = (idx_a + randint(1,4)) % 5` → `bpm = choice([88,90,92,94,96])`。`begin_pattern` は毎 pattern で motif を2回 choice → `random() < 0.5`（ゴースト有無）。`compose_measure` はドラム（乱数なし）→ベース（intro/outro 以外で `random() < 0.6`）→パッド→メロディ。
- **旋律**: リズム型から動機を選び、小節1・2で反復（変奏）。強拍はコードトーン（長7度・3度・5度）優先。経過音は 75% 順次進行・25% 跳躍、跳躍後は逆行。フレーズ末は解決音。サビは1オクターブ上。
- **残している旧挙動（直さない）**:
  - Q1 outro の row 0 はフェード用キックで上書きされ、テンポセルが無い（先行 pattern で設定済みなので実害なし）。このため `tempo_policy="profile"`。
  - Q2 intro は row 0 ch1 に「音なし＋`F bpm`」、他の pattern は「キック＋`F bpm`」。
  - Q3 pad・flute のループ（K=32/L=1024）は −17.6 セント低い。musicbox（261.63 Hz）とわずかにうなる。
  - Q4 flute は未使用。Q5 サビのオクターブ上げは `min(3, octave+shift)` で頭打ち。Q6 ゴーストはサビの row 15 のみ、フィルは bar 3 の row 14/15。Q7 曲名 `Twilight Pad`、finetune 0。
  - 移植コードのセルは旧 `cell()` と同じく vol を 0..64 にクランプしてから `Cell` を作る（`_legacy_cell`）。

### 6.2 suspense 共通（`profiles/suspense_common.py`）

suspense-slow と suspense-chase が `SuspenseBase` を継承し、`plan()` と文法だけを別に持つ。

- **調・進行**（主音 C）: `pedal`＝Cdim → Db/C → Cdim → B/C（ベースは C のまま上声が半音でぶつかる）、`tritone`＝Cm → F#dim → Fm → Bdim、`phrygian`＝Cm → Dbmaj7 → Bbm → C。旋律は C フリジアン、dim 上では `dim_wh`。4 slot × 1 measure。
- **音色**（7）: heart（38 Hz へ落ちる心拍。打楽器）、anvil（非調和部分音の金属音。`rate_note=B-3` の高レートで生成）、swoosh（徐々にフィルタが開くノイズの立ち上がり 0.9 秒）、drone（`shift=−24`、奇数倍音＋サブのループ、アタック付き）、pizz（`τ=0.08 s` のピチカート）、strings（同音デチューン対2組 K=(130,131)・(138,139) の大きなループ。C-3 で 2 Hz のうなり、うなりは発音ピッチに比例）、lead（`shift=+12` のループ。ポルタメントとビブラートは文法側で付ける）。
- **チャンネル**: 1=pulse/FX（heart/anvil/swoosh、優先度 anvil>swoosh>heart）、2=low（drone）、3=texture（strings、pizz が優先）、4=lead/accent（lead、pizz が優先）。
- **音域**: `BASS_REG=(0,11)`、`HARMONY_REG=(17,28)`（strings のアルペジオ基音。+7 でも t≤35）、`PIZZ_REG=(24,35)`、`LEAD_REG=(24,41)`。
- **語彙**: silence run（全チャンネルで新規 note を置かず、持続音を `off()`）、shock hit（anvil vol 64。直前 8 row は heart/pizz/lead を鳴らさない）、swoosh は衝撃の直前の measure の row `rows_per_measure − round(0.9 / (15/bpm))` から（slow は row 12、chase は 7〜8）、ostinato crescendo（pizz を2 row 間隔で `ramp`）、strings は `arp` 付き（arp セルは vol を持てないので既定音量）、lead の `3xx` は直前と同じサンプル番号で vol なし、`pedal` 進行では drone は常に C。
- **同時音量**: 左（ch1+ch4）・右（ch2+ch3）の合計を 120 以下に保つよう衝撃場面の値を逆算してある（例: drone 50 + pizz ≤60）。

### 6.3 `suspense-slow` — 低速・重苦しい緊張

A・B の進行を `pedal`/`tritone`/`phrygian` から異なるものとして選ぶ。

| # | kind | 要点 |
|:--|:---|:---|
| 0 | hush | m2 から心拍、strings を小音量から段階的に |
| 1 | pedal | 心拍・drone・strings＋arp。途中の1 measure を dropout（心拍・drone・strings が止まる）し、直後に確率で anvil、pizz のスタブ |
| 2 | phrygian | lead が 1〜2 音/measure（dissonance 0.6、2音目に `3xx`） |
| 3 | shock | 心拍の加速 → 全 16 row 無音 → swoosh → row 0 に anvil、pizz のオスティナート、lead 高音＋ビブラート |
| 4 | aftermath | 心拍・drone・strings が減衰して終わる |

### 6.4 `suspense-chase` — 緊急脱出・追走

A=`pedal`、B=`tritone` 固定。intro（pizz オスティナートのクレッシェンド）→ a1/a2（毎拍の心拍、drone の8分連打、半音・増4度を混ぜた pizz の音型、m2 後半の silence run と m3 の anvil。a1/a2 は dropout とスタブの位置が違う）→ b（strings＋arp、lead）→ climax（各 measure の anvil、pizz の16分クレッシェンド、swoosh）→ outro。

### 6.5 `march` — 行進曲

- **調**: C / F / Bb / Eb から選ぶ。トリオは主調＋5半音（下属調）。スケールは ionian。1 measure = 8 row（2/4、約1秒）。
- **音色**: bd、sd、crash（`rate_note=B-3`）、tuba（`shift=−12`、スタッカート）、horn（後打ち）、section（金管セクションのループ）、picc（`shift=+12` のループ。長音にビブラート）。
- **チャンネル**: 1=drums（crash>sd>bd）、2=tuba、3=horn/section（section が優先）、4=picc。
- **進行**: `sousa`（C G7 C F C/G G7 C。最後の和音を2 measure にして8 measure に収める）、`heroic`（C F G C Am Dm G7 C）、`trio`（トリオ調で I I V7 I IV I V7 I）。
- **構成**: intro（heroic。crash＋section の保持和音→無音→軽いスネア→ oom-pah、ファンファーレ）、a（sousa）、a2（heroic）、trio（軽いドラム、horn は単音、旋律は低め）、trio2（1オクターブ上、section の保持和音、crash、ロール）、coda（最終和音）。
- **文法**: Oom（row 0）＝tuba の根音（同じ和音が続けば根音と5度を交互）＋bd。Pah（row 4）＝horn の和音音＋arp（intensity ≥0.7）＋sd。フレーズ末 measure の row 4–7 はスネアロール（通常のスネアを `replace` で置換）。crash は同 row の bd を優先度で置き換える。picc は `articulate(gate=0.9)`。旋律フレーズは `[a, a', b, c, a, a', b, cad]`（c＝主音→3度→5度→オクターブの分散和音）。

### 6.6 `swing-jazz` — スウィング・ジャズ

- **音色**: ride、brush、walking bass（`shift=−12`）、piano comp（近接デチューン対でコーラス感）、sax（奇数倍音のループ、タンギングのアタック）。
- **チャンネル**: 1=drums（brush>ride）、2=bass、3=piano、4=sax。
- **進行**: Bb、リズムチェンジ AABA。A＝Bb6 G7 Cm7 F7 Bb6 G7 Cm7/F7 Bb6、B＝D7 D7 G7 G7 C7 C7 F7 F7。ドミナント7th はミクソリディアン、m7 はドリアンで経過音を選ぶ（`mode_by_quality`）。
- **文法**（1 measure=8 row、1 row=8分）: ride は ding-ding-a-ding（row 0,2,3,4,6,7、row 0/4 が強拍）、brush はバックビート（row 2,6）、ベースは4分のウォーキング（次の和音の根音を `cadence_target` にして繋ぐ）、ピアノは Charleston（row 0,3）か裏拍2発を選んで arp で刺す（強拍に全パートを集めない）、sax は motif プールから `MelodyGenerator(beat_rows=2)`。ソロは跳躍確率・不協和を上げる。ときどき `E9x` のターン装飾。
- **core**: `SwingConfig(14, 10)` を `post_processors` で全 pattern に適用。intro の row 0 はベース・ピアノを休符にして空きを2つ作る。

### 6.7 `prog-rock` — 変拍子プログレ／マスロック

- **音色**: kick、snare、crash（march の crash を短縮）、distortion bass（`shift=−12`）、power chord guitar（ルート・5度・オクターブを1サンプルに焼き込む）、lead guitar（ループ）。
- **チャンネル**: 1=drums（crash>snare>kick）、2=bass、3=guitar、4=lead。
- **進行**: E エオリアン、i–bVII–bVI–bVII（Em D C D）。和声より拍子の変化が主役。
- **構成**: 1 pattern = 7/8 + 7/8 + 5/8（14+14+10 = 38 row）＋`D00`。chorus は 4/4 × 4（64 row）に戻して対比を作る。breakdown は 5/8 × 6（60 row）。
- **文法**: 拍子ごとのリフの motif を `mctx.measure_rows` で引く。キックはギターのアクセントと同じ row、フレーズ末に crash、ベースはギターのルートをユニゾン、lead は chorus だけ。

### 6.8 `trap` — トラップ／ドリル

- **音色**: 808（`shift=−12`、ロングテールのサイン）、snare/clap、closed hat、open hat、lead pluck。
- **チャンネル**: 1=808、2=snare、3=hat（open>closed）、4=lead。
- **進行**: C マイナー、i–VI（Cm–Ab）の2和音ループを全区間で固定（32 row の measure が1 pattern に2つしか入らないため）。セクションの違いはドラム編成で出す。
- **文法**: 808 は row (0,8,12,20) で根音と5度を交互に鳴らし、2打目以降は `portamento_param(..., rows=1)` の `3xx` でグライド。**ただし先行音（ワンショット）が鳴り終わっていれば `3xx` ではなく新しい打鍵として書く**（鳴り終わった後の `3xx` は ProTracker では固有の挙動で鳴り直すが、XM/S3M/IT では無音になるため。再生位置は Paula クロック / period の実レートで追跡する）。ハットは8分で、measure に1か所、確率 0.6 で `E9x` のロール。フレーズ末に open hat。snare は row 16・28。lead は hook だけ。

### 6.9 `future-bass` — フューチャーベース

- **音色**: kick、sub（`shift=−12` のループ）、supersaw（隣接整数サイクル数の3層ループ）、vocal chop（`pitched=False` の長いサンプル。`9xx` の offset でシラブルを切り替える）、clap。
- **チャンネル**: 1=kick/clap（clap>kick）、2=sub、3=chord、4=lead（vocal）。
- **進行**: Eb メジャー、I–V–vi–IV。
- **文法**: drop・buildup の kick は4つ打ち。sub・saw は measure 頭で鳴らして持続。**ダッキングは作曲中にはせず** `post_processors` の `apply_sidechain` で行う。kick と clap は同じチャンネルで優先度を共有し、バックビートでは clap が kick を置き換えるので、**kick と clap の両方をトリガに登録**する（bass: duck 0.25 / release 3、chord: 0.35 / 4）。

### 6.10 `maqam` — 中東マカーム（Rast on G）

- **音律**: `MicroScale(tonic_pc=7, degrees_cents=(0, 200, 350, 500, 700, 900, 1050))`。3度と7度が中立音程。qarar（主音）を G-2 に置き、`resolve_micronote` で度数ごとに `(t, finetune)` を求める（モジュール定数として一度だけ計算）。
- **音色**: oud（撥弦のピッチドロップ付き）、その finetune 派生 `oud_n3`・`oud_n7`（中立音程用の別スロット）、nay（ドローン用ループ）、qanun（分散和音）、daf の DUM・TEK。
- **チャンネル**: 1=perc（DUM>TEK）、2=oud（3種）、3=nay、4=qanun。
- **リズム**: usul maqsum（16分格子で DUM row 0,10、TEK row 4,12）。
- **和声の使い方**: `ChordDef` を手組みし、`bass`＝qarar、`harmony`＝ghammaz（5度）、`scale_tones`＝ジンスの音（t のみ）。どの oud スロットを使うかは度数→楽器名の対応表（ジャンル内のローカルな定数）で引く（`ChordDef` にフィールドを足さない）。
- **文法**: oud の旋律は専用の `_maqam_phrase()`（順次進行中心、跳躍は4度・5度のみ）。nay は ostinato で持続、qanun は measure 頭で上行分散和音。taqsim は打楽器なし（テンポは一定、row の粗密で自由リズム感）。

### 6.11 `free-jazz` — フリージャズ

- **音色**: piano cluster（ほぼ半音刻みの5層）、arco bass（`shift=−12`、隣接整数デチューンのループ）、sax screech（高次倍音＋ノイズ）、cymbal swell（上昇するノイズ）。
- **チャンネル**: 各チャンネルに1楽器（piano / bass / sax / perc）。優先度は使わない。
- **和声**: root 付近の隣接半音（`(0,1,2,−1,−2,6,7)` から2〜4個）を密集させた手組みのクラスター和音を pattern ごとに4つ。`chord.bass` は arco bass 専用（`BASS_REG`）、`chord.chord_tones` は piano・sax 共有の `CLUSTER_REG`（shift の違う楽器に同じ音域を渡さない）。
- **文法**: 各楽器が row ごとに intensity に応じた確率で鳴るかを決める（`rng.drums`/`bass`/`melody` を独立に使用）。sax は climax だけ密集。
- **テンポ**: `tempo_policy="profile"`。各 pattern の `finalize_pattern` で `TempoCurve` を描く（96→82 ease_out、82→126 ease_in、126→150→126、126→70 linear。pattern 間で BPM が連続する）。`--tempo` は開始 BPM を決め、カーブ全体を `開始 BPM / 96` 倍する。

### 6.12 `minimalism` — ミニマル／フェーズ音楽

- **音色**: piano pulse、marimba、vibraphone、woodblock（`pitched=False`）。
- **周期**: piano 16 row、marimba 12、vibes 8、wood 6。最小公倍数 48 row を1 measure（`ChordSlot.rows=48`、`variable_meter=True`、pattern 末に `D00`）。
- **構成**: phase0 … phase15（16段階）。piano の音型だけを段階ごとに1 row ずつずらし、「ズレて→揃って戻る」。
- **文法**: 各チャンネルは固定の「周期内 row → (音, 音量)」表を `polymetric_row(row − shift, cycle)` で引く。乱数は使わない（決定論的な反復が本質）。
- **空きの確保**: woodblock のアクセントを row 1 に置いて row 0 に空きを作り、row 47 はどの固定音型の onset とも重ならないので `D00` を置ける。

### 6.13 `orchestral` — フルオーケストラ／劇伴（8ch）

- **チャンネルと音色**:

  | ch | 役割 | 楽器（サンプル） | pan |
  |:---|:---|:---|:---|
  | 1 | 第1ヴァイオリン（旋律） | vln1 | 30 |
  | 2 | 第2ヴァイオリン | vln2（vln1 を finetune +3 した派生） | 80 |
  | 3 | ヴィオラ | vla（vln1 の `shift=−7` 派生） | 150 |
  | 4 | チェロ | vc（`shift=−12` 派生） | 190 |
  | 5 | コントラバス | cb（`shift=−24` 派生） | 210 |
  | 6 | 木管 | ww（nostalgic の flute を流用） | 100 |
  | 7 | 金管 | horn（march の section）、trumpet（section のアタック短縮版。trumpet>horn） | 160 |
  | 8 | 打楽器 | timpani（`shift=−24`）、cymbal（free-jazz の swell を流用。cymbal>timpani） | 128 |

- **和声**: C の I–IV–V–vi を6声（CB・VC・VLA・VLN2・VLN1・BRASS）でボイシング。`voice()` で bass・tenor・旋律候補を求め、残り3声は `mctx.chord.chord_tones` のピッチクラスから毎 measure 導出する（`begin_pattern`/`state` 不要）。6音域はモジュール定数。
- **構成**: intro（弦のみ）→ theme（＋木管）→ development（＋ホルン）→ climax（全8ch・トランペット・ティンパニ・シンバル）→ resolution（弦のみ）。intensity 0.3→0.5→0.7→1.0→0.4 で音量をセクション単位にスケール。通作（ループしない）。
- **出力**: 既定の MOD では `8CHN`（サンプル単位のパンは失われ、プレイヤーの L R R L になる）。XM/S3M/IT/MIDI ではサンプルのパンがチャンネルパンになる（§7.1）。
- **V15 の扱い**: climax の全合奏は V15 の目安（片側合計 ≤120）を超えるが、実プレイヤーでは音割れしない（最大振幅 MOD −5.1 dBFS／XM −1.9／IT −2.3）。V15 は 4ch の曲だけを検査するので orchestral は対象外で、音割れは実測の検査で確かめる（§9.1・§9.2）。

### 6.14 第３段階のジャンルの共通の仕組み（`profiles/band_common.py`）

§6.15・§6.16 の35ジャンル（`次の検討事項.txt` 第３段階）は、どれも `BandProfile` のサブクラスとして書く。

**方針**

- 35ジャンルの多くは「ドラム・ベース・和音・旋律・パッド」という同じ骨格を持つ。`BandProfile`（`profiles/band_common.py`。core ではなくジャンル共通の補助で、`suspense_common` と同じ位置づけ）がその骨格を**宣言（クラス属性）から**作曲し、各ジャンルは宣言と、固有の文法だけをフック（`extra_measure`、各パートのメソッドの上書き）で足す。作曲の枠組み（`GenreProfile`・`compose_measure`・`ChannelPlan`・`MelodyGenerator`・`voice()`）、出力形式、検査は変えていない。
- 音色は楽器名で命名した共有ライブラリ（§4.5）を複数のジャンルで使い回す。
- **チャンネル数はジャンル単位で 4／6／8 から選ぶ**（努力目標「パターン構成に合わせて適切なチャンネル数を選ぶ」への対応。全形式でチャンネル数はファイル単位なので、1曲の中では変えられない）。4ch は既定の MOD で Amiga 互換の `M.K.`、6ch・8ch は `6CHN`・`8CHN`。6ch・8ch は `CHANNELS` の `pan` から `channel_pans` を作る（既定の L R R L だと kick やベースが片側に寄るため）。
- 表示名・説明・id に実在の人名を入れない（原文の「〜系」は音楽的特徴に置き換えた）。旋律はすべて手続き的に作り、既存の曲の旋律は使わない。
- **区分**（`GenreProfile.category`）: `mood`（気分）・`genre`（ジャンル）・`style`（「〜風」）。`--list-genres` と `--help` は区分ごとにまとめる（§8.1）。第３段階より前の12ジャンルは genre＝swing-jazz・prog-rock・trap・future-bass・maqam・free-jazz・minimalism・orchestral・march、style＝nostalgic・suspense-slow・suspense-chase。
- 気分ジャンルの原文にある「相性」（晴れ・夜・雨など）は §6.16 に記録するだけで、属性にはしていない（天気・時間帯から選ぶ機能を作るときに足す）。

**チャンネル構成の型**

| 型 | ch | 構成 | 使うジャンル |
|:---|:---|:---|:---|
| **B4**（4ch バンド） | 4 | 1 ドラム（1チャンネルで優先度により共有）／2 ベース／3 和音／4 旋律 | warm、folk、hiphop、acoustic-ssw、focus（4 はレコードのノイズ）、bossa-nova、jazz（読み替え: ride/brush・bass・piano・trumpet） |
| **B6**（6ch バンド） | 6 | 1 kick/snare／2 hat・perc・cymbal／3 ベース／4 和音（コンプ・ストローク・鍵盤）／5 旋律／6 パッド・対旋律・タム等 | rock、pop、energetic、city-pop、jpop-80s、jrock-90s、indie-rock、rnb-soul、neo-soul、anime-ost、jrpg、lofi-hiphop、lofi-chill |
| **E6**（6ch 電子音楽） | 6 | 1 kick／2 clap・snare・hat／3 ベース／4 和音／5 リード・アルペジオ／6 パッド・FX・エコー | uplifting、edm、house、synthwave、cool、dreamy、dark-tense |
| **A4**（4ch アンビエント） | 4 | パッド・持続音・ベル・エコー・低音の組合せ | calm、ambient、ambient-drone、melancholic（1 旋律ピアノ／2 伴奏ピアノ／3 弦パッド／4 低音に読み替え） |
| **Q4**（弦楽四重奏） | 4 | vln1／vln2／vla／vc | classical |
| **T4**（4ch テクノ） | 4 | 1 kick／2 hat・clap／3 ベース／4 シーケンス | techno |
| **O8**（8ch 管弦楽） | 8 | §6.16 の各項 | cinematic、trailer |

各ジャンルの実際のチャンネルと楽器は §6.16 の「音色」。

**宣言（クラス属性）**

| 属性 | 意味 |
|:---|:---|
| `KIT` | `(楽器名, Patch)` の列。挿入順＝サンプル番号 |
| `CHORD_KITS` | 和音サンプルの素材 `{接頭辞: (Patch, strum_ms)}`。進行に現れる和音の種類ごとに `<接頭辞>_<quality>` のサンプルを `chord_patch` で作り、KIT の後ろに足す（全サンプルは 31 以下。クラス定義時に検査） |
| `CHANNELS` | `ChannelDef(name, keys, priority, pan)` の列（チャンネル数＝要素数）。`keys` は KIT の名前か和音の接頭辞。`channel_plan`・`channel_pans`・`gm_voices` はクラス定義時にここから作る |
| `GM` | GM 音色を既定値（`GM_DEFAULTS`。Patch 名で引く）から変えたい楽器だけ。既定値の無い Patch 名は例外（推測しない） |
| `KEYS`・`MODE`・`MODE_BY_QUALITY` | 主音の候補（`plan()` が1つ選ぶ）、旋律の音階、和音の種類ごとの旋法（和音の根音基準） |
| `REGISTERS`・`ARP_REGISTER` | `voice()` の音域（bass・harmony・melody）とアルペジオの音域 |
| `PROGRESSIONS`・`N_PROGRESSIONS` | `(名前, (ChordSpec, …))` の列。`plan()` が `N_PROGRESSIONS` 個を無作為に選び、区間の `prog` 番号で参照する |
| `FIXED_PROGRESSIONS` | True なら選ばずに宣言順にすべて使う（区間ごとに和声の役割が決まっている classical・cinematic・jrpg） |
| `MEASURES_PER_PATTERN` | 1 pattern の measure 数。None なら `64 // rows_per_measure`（classical の 3/4 は 4） |
| `SECTIONS`・`FORM` | `Section(kind, prog, intensity, parts, groove, key_offset, fill, crash, lead_motifs)` と区間の並び。同じ区間名は同じ pattern を再利用する |
| `GROOVES`・`DRUM_CHANNEL` | ドラムの型（`Hit(row, key, vol, prob)` の列。`hits()` で作る）と、ドラムの楽器 → チャンネル。`"fill"`・`"crash"` は区間の `fill`・`crash` で使う |
| `BASS`・`COMP`・`LEAD`・`PAD`・`ARP`・`FX` | 各パートの鳴らし方（`BassSpec`・`CompSpec`・`LeadSpec`・`PadSpec`・`ArpSpec`・`FxSpec`）。None ならそのパートは無い |
| `ECHO`・`SWING`・`SIDECHAIN`・`LATE`・`HUMANIZE` | エコー（`EchoSpec`）、スウィング、サイドチェイン（トリガの楽器・対象チャンネル・比・戻る row 数）、ドラムを `EDx` で遅らせる確率、ドラムの音量ゆらぎ（±4） |

**作曲の流れ**

1. `plan()`: BPM → 主音 → 進行（無作為に選ぶか宣言順）→ 区間名ごとに `PatternPlan`（進行の和音を measure に均等に割り当てる: 1和音 `max(1, n_measures // 和音数)` measure）→ `FORM` から order。要約行に調と進行を出す。
2. `begin_pattern()`: 旋律がある区間では `MelodyGenerator` と、`LEAD.motifs[区間の lead_motifs]` から動機 A・B を選ぶ。
3. `compose_measure()`: ドラム → ベース → 和音（comp）→ パッド → アルペジオ → FX → 旋律 → `extra_measure()`（ジャンル固有）。区間の `parts` に無いパートは鳴らさず、持続音色（ループ）のパートは pattern の先頭で止める（前の区間から鳴り続けないように）。音量は区間の `intensity` で下げる（ドラムは `0.6 + 0.4×intensity` 倍、他のパートは `0.55 + 0.45×intensity` 倍）。
4. 旋律は4小節の楽節: A・A（反復）・B・終止（4小節目は後半を休み、音を切る）。`LeadSpec.vibrato` があれば 6 row 以上の音に `4xy`。区間ごとに旋律の楽器を持ち替えるジャンルは `lead_key(sec)` を上書きする（anime-ost・jrpg）。
5. `finalize_pattern()`: `ECHO` を書き、スウィングするジャンルでは全 row に Speed を書ける場所を作り（`make_room_for_row_commands`: 空きの無い row では、番号の大きいチャンネルから音を持たないセル（ビブラート・消音）を消し、無ければ効果の無い音の音量を外して `insert_command` が書けるようにする）、曲の先頭 pattern の row 0 にテンポ（スウィングがあればさらに Speed）のための空きチャンネルを作る（`reserve_row0`: 番号の大きいチャンネルから row 0 の音を row 1 へ移す）。
6. 後処理（`post_processors`）: サイドチェイン（`mixer.apply_sidechain`）→ スウィング（`groove.apply_swing`）。

**パートの型**（16 row＝4/4 を基準に書き、measure の行数に比例させる）

- ベース（`bass_line`）: `whole`・`half`・`root8`・`octave8`・`offbeat`（裏拍の8分）・`rootfifth`・`bossa`・`walking`（根音・第3音・5度・半音の経過音）・`synco16`・`boombap`・`pulse16`（根音・短2度・5度の16分）・`house`。
- 和音の刻み（`comp_rows`）: `whole`・`half`・`pulse4`・`pulse8`・`offbeat`・`charleston`・`strum`・`bossa`・`stab2`・`arp8`・`arp16`・`fingerpick`・`cutting16`（強拍以外は確率 0.55）。`CompSpec.chordal=False` なら単音で和音を分散させ、`wobble` があれば和音の直後に `4xy`（テープの揺れ風）。
- アルペジオ（`ArpSpec`）: 指定 row で和音の構成音を `up`／`updown`。

**補助**

- `chord_patch(base, quality, strum_ms=0)`: `base` の音色で和音を1サンプルに焼き込む（ToneLayer を構成音の数だけ複製して部分音を音程比倍、音量は `1/√構成音数`。打鍵の雑音などのノイズ層は1回だけ）。`strum_ms > 0` なら構成音ごとに鳴り始めを遅らせてギターのストロークにする（`WeightedLayer.offset_ms`、OneShot のみ）。**ループの素材はサイクル数を整数に丸める**ので、基本サイクル数が大きい素材でないと音程がずれる（誤差 12 セント超で例外）。オルガン・ブラス・シンセブラスのループはサイクル数が小さく sus4 しか作れないため、和音サンプルには使わず単音で鳴らす。
- `echo(pattern, src, dst, delay, ratio, repeats)`: 発音を `delay` row 遅らせ音量を `ratio` 倍にして別チャンネルの空き row に書く（MOD に残響エフェクトが無いため）。
- `buildup(mctx, buf, ch, snare, riser=, fx_ch=)`: EDM 系のビルドアップ。4小節でスネアが4分→8分→16分→`E9x` と加速し音量が上がる。最後から2つ目の measure の頭に上昇音。
- `GM_DEFAULTS`・`gm_default(patch)`・`preset(key, **changes)`（プリセットを名前で引き、`dataclasses.replace` で差分を当てる）。

**書くときの注意（実装で分かった制約）**

- ドラムの型（`GROOVES`）は音程を持たない楽器だけに使う。音程のある楽器（タム・ティンパニ）を音高なしで置くと休符になるので、`extra_measure` で音高を付けて書く。
- 同じ優先度の別のセルを同じ位置に `put` すると `ChannelConflictError`。「決め」のように他のパートを意図して上書きするときは `buf.replace` を使う（anime-ost）。
- 可変小節（classical）は `D00` を書く最終 row に空きチャンネルが1つ要る。

**共通の文法**

- **歌もの**（pop・rock・city-pop・jpop-80s・jrock-90s・indie-rock・rnb-soul・neo-soul・acoustic-ssw・energetic）: 1 pattern＝4小節。form は `intro, verse, pre, chorus, …, outro` を基本にジャンルごとに省略・追加する。旋律は動機を反復し、4小節目の後半を休ませて歌の息継ぎにする。多くは区間頭の crash と区間末のフィルを持つ。
- **電子音楽**（uplifting・edm・house・techno・synthwave・cool）: 1 pattern＝4小節で、区間ごとにレイヤーを出し入れする。uplifting・edm・house は kick をトリガにサイドチェインを掛ける。
- **アンビエント系**（calm・ambient・ambient-drone・dreamy）: 和音は2〜4小節ごとにしか変えない。音量（intensity、ambient-drone は持続音への音量セル）で起伏を作る。
- **スウィング**: Speed の和は `48 / rows_per_beat`（1拍＝24 tick）。16分スウィング（focus・lofi-hiphop・lofi-chill・hiphop・rnb-soul・neo-soul）は1拍＝4 row のまま row の偶奇で Speed を交互にし、和は 12（`SwingConfig(7, 5)`＝1.4:1、neo-soul は `(8, 4)`＝2:1）。8分スウィング（jazz）は swing-jazz と同じ1拍＝2 row・和 24（`(14, 10)`）。
- **拍のよれ**（neo-soul）: `LATE` でスネアとハットの一部に `EDx`（1〜2 tick）を確率で付け、グリッドから少し遅らせる。
- **転調**: `Section.key_offset`（`PatternPlan.key_offset`。march のトリオと同じ）。最後のサビを上げる（pop +1、jpop-80s +2、jrock-90s +1）、jazz の B（+1）、classical の属調（+7）・下属調（+5）、trailer の第3幕（+1）。
- **3/4 拍子**（classical）: 1 measure＝12 row、`variable_meter=True`、`MEASURES_PER_PATTERN=4`（48 row）＋`D00`。2/4（bossa-nova）は 8 row で 64 row＝8小節なので可変小節は要らない。

### 6.15 第３段階のジャンルの宣言値

コードから取得（`BandProfile` の宣言）。区分は §6.14、チャンネル構成の型は §6.14 の表。

| id | 区分 | 表示名 | BPM | 拍子（rpm） | ch | 調・旋法 | 構成（order） |
|:---|:---|:---|:---|:---|:---|:---|:---|
| `uplifting` | mood | Uplifting | 128–136 | 4/4（16） | 6 | D/E/F ionian | intro, build, drop, drop, break, build, drop, drop, outro |
| `calm` | mood | Calm / Relaxed | 68–78 | 4/4（16） | 4 | C/F/G lydian | intro, a, b, a, outro |
| `melancholic` | mood | Melancholic | 66–76 | 4/4（16） | 4 | A/D/E aeolian | intro, a, b, a, b, outro |
| `energetic` | mood | Energetic | 160–176 | 4/4（16） | 6 | E/A/D ionian | intro, verse, pre, chorus, verse, pre, chorus, bridge, chorus, chorus, outro |
| `dreamy` | mood | Dreamy | 80–92 | 4/4（16） | 6 | Eb/Ab/Db lydian | intro, a, b, a, b, outro |
| `dark-tense` | mood | Dark / Tense | 90–100 | 4/4（16） | 6 | C/D harmonic_minor | intro, build, pulse, build, climax, collapse |
| `warm` | mood | Warm | 88–100 | 4/4（16） | 4 | G/D/C ionian | intro, a, b, a, b, outro |
| `cool` | mood | Cool | 100–112 | 4/4（16） | 6 | F#/B/Db dorian | intro, a, b, break, a, b, outro |
| `focus` | mood | Focus | 78–86 | 4/4（16）、スウィング 7:5 | 4 | D/E dorian | intro, loop, loop, loop2, loop2, loop, loop_b, loop_b, loop2, loop2, loop, loop, outro |
| `rock` | genre | Rock | 112–132 | 4/4（16） | 6 | E/A/D mixolydian | intro, verse, chorus, verse, chorus, solo, chorus, outro |
| `pop` | genre | Pop | 100–120 | 4/4（16） | 6 | C/D/F/G ionian | intro, verse, pre, chorus, verse, pre, chorus, bridge, chorus, chorus_up, outro |
| `jazz` | genre | Modal Jazz | 120–144 | 4/4（8、1 row＝8分）、スウィング 14:10 | 4 | D dorian | head_a, head_a, head_b, head_a, solo_a, solo_a, solo_b, solo_a, head_a, head_a, head_b, coda |
| `bossa-nova` | genre | Bossa Nova | 120–140 | 2/4（8） | 4 | F/C/G/D ionian | intro, a, a, b, a, solo, a, outro |
| `city-pop` | genre | City Pop | 104–120 | 4/4（16） | 6 | E/A/Db ionian | intro, verse, pre, chorus, interlude, verse, pre, chorus, chorus, outro |
| `ambient` | genre | Ambient | 60–72 | 4/4（16） | 4 | D/E lydian | layer1, layer2, bloom, layer2, drift, fade |
| `lofi-hiphop` | genre | Lo-fi Hip Hop | 72–88 | 4/4（16）、スウィング 7:5 | 6 | D/F/A/C ionian | intro, a, a, b, a, outro |
| `edm` | genre | EDM | 124–130 | 4/4（16） | 6 | F/G aeolian | intro, build, drop, drop, break, build, drop, drop, outro |
| `house` | genre | House / Deep House | 118–124 | 4/4（16） | 6 | A/D/G dorian | intro, groove, main, main, break, main, main, outro |
| `hiphop` | genre | Hip Hop (Boom Bap) | 86–96 | 4/4（16）、スウィング 7:5 | 4 | A/E/D/G aeolian | intro, verse, verse, verse, verse, hook, hook, verse, verse, verse, verse, hook, hook, outro |
| `classical` | genre | Classical (String Quartet) | 100–120 | 3/4（12、可変） | 4 | G/D/F/Bb ionian | ante, cons, ante, cons, dom, ret, ante, cons, trio_a, trio_b, trio_a, trio_b, ante, cons, coda |
| `cinematic` | genre | Cinematic | 70–84 | 4/4（16） | 8 | C/D aeolian | intro, rise1, theme, theme, rise2, climax, climax, resolve |
| `folk` | genre | Folk | 96–116 | 4/4（16） | 4 | G/D/C/A ionian | intro, verse, chorus, verse, instrumental, chorus, outro |
| `rnb-soul` | genre | R&B / Soul | 68–84 | 4/4（16）、スウィング 7:5 | 6 | Eb/Ab/Db ionian | intro, verse, pre, chorus, verse, pre, chorus, bridge, chorus, outro |
| `synthwave` | genre | Synthwave / Retrowave | 96–112 | 4/4（16） | 6 | A/E/F# aeolian | intro, verse, chorus, verse, chorus, solo, chorus, outro |
| `techno` | genre | Minimal Techno | 124–132 | 4/4（16） | 4 | A/D aeolian | k1, k2, h1, f1, f2, h1, b1, f3, f2, f3, o1, k1 |
| `jpop-80s` | style | 80s J-Pop | 120–136 | 4/4（16） | 6 | C/D/E ionian | intro, a, b, sabi, interlude, a, b, sabi, sabi_up, outro |
| `jrock-90s` | style | 90s J-Rock | 140–168 | 4/4（16） | 6 | E/A/D aeolian | intro, a, b, sabi, a, b, sabi, solo, sabi, sabi_up, outro |
| `anime-ost` | style | Anime Soundtrack | 120–150 | 4/4（16） | 6 | D/G aeolian | intro, a, b, break, a, b, climax, outro |
| `jrpg` | style | JRPG Game Music | 96–120 | 4/4（16） | 6 | C/D/F ionian | intro, a, a2, b, a, a2, ending |
| `lofi-chill` | style | Lo-fi Chill | 72–88 | 4/4（16）、スウィング 7:5 | 6 | C/F/G/Bb ionian | intro, a, a, b, a, outro |
| `indie-rock` | style | Indie Rock | 118–138 | 4/4（16） | 6 | G/D/A ionian | intro, verse, chorus, verse, chorus, bridge, chorus, outro |
| `trailer` | style | Cinematic Trailer | 90–100 | 4/4（16） | 8 | D/C aeolian | act1, act1, act2, act2, riser, act3, act3, final |
| `ambient-drone` | style | Ambient Drone | 60–66 | 4/4（16） | 4 | D/E/A dorian | d1, d2, d2, d3, d3, d4, d4, d5, d5, d6, d6, d7, d8 |
| `acoustic-ssw` | style | Acoustic Singer-songwriter | 80–100 | 4/4（16） | 4 | G/C/D/E ionian | intro, verse, chorus, verse, chorus, bridge, chorus, outro |
| `neo-soul` | style | Neo Soul | 80–96 | 4/4（16）、スウィング 8:4 | 6 | Eb/Ab/F dorian | intro, verse, chorus, verse, chorus, bridge, chorus, outro |

### 6.16 第３段階の各ジャンル

各項の「区別」は、似たジャンル（既存を含む）とどこで聞き分けられるか。和音の記法は主調に対する度数。「音色」は `チャンネル（楽器＝Patch 名）`。和音サンプル（`CHORD_KITS`）は「〜の和音」と書く。

#### 6.16.1 `uplifting` — 高揚するシンセ・アンセム（mood、E6）

- 説明: 「上げていく高揚感。4つ打ちとアルペジオ、明るいスーパーソウのコード」／"Uplifting anthem: four-on-the-floor, bright arpeggios and supersaw chords"
- 相性（原文）: 晴れ・昼間
- 音色: 1 kick（Kick909）／2 clap/hat（FbClap・OpenHat909・PopSnare）／3 bass（SawBass）／4 supersaw（FbSupersaw の和音）／5 arp（SynthPluck）／6 lead（SawLead）
- 和声: I–V–vi–IV、vi–IV–I–V、IV–V–iii–vi（2 つを選んで区間に割り当てる）
- 文法: kick の4つ打ち＋clap（2・4拍）＋裏拍の open hat。ベースは裏拍の8分（`offbeat`）、スーパーソウの和音を全音符で持続し kick でサイドチェイン（ベース 0.3・和音 0.4）。プラックのアルペジオは16分で上行。drop でリードが動機を反復（`4xy`）。build は `buildup`。
- 区別: edm よりテンポが速めで長調・アルペジオ主体。future-bass より直線的な4つ打ち。

#### 6.16.2 `calm` — 穏やかなピアノとパッド（mood、A4）

- 説明: 「落ち着き。低いテンポで柔らかいパッドとピアノの分散和音」／"Calm and relaxed: soft pads and slow piano arpeggios"
- 音色: 1 piano（Piano）／2 pad（WarmPad の和音）／3 bell（Bell）／4 bass（FingerBass）
- 和声: Imaj7–IVmaj7、Imaj7–vi7、IVmaj7–Vsus4（2 つを選んで区間に割り当てる）
- 文法: ピアノは8分の分散和音（往復）、パッドは和音の変わり目に全音符、ベースは a・b だけ小節頭の根音。ベルは1・3小節目に確率で1音（4小節に1〜2音）。打楽器なし。2和音の進行を4小節に当てるので和音は2小節ごと。
- 区別: ambient より拍がはっきりした（ピアノの8分）穏やかな曲。melancholic は短調でピアノが旋律を持つ。

#### 6.16.3 `melancholic` — 物悲しいピアノ・バラード（mood、A4 読み替え）

- 説明: 「物悲しい。短調のピアノが旋律を歌い、弦のパッドが支える」／"Melancholic piano ballad in a minor key over soft strings"
- 音色: 1 piano melody（Piano）／2 piano accomp（PianoAccomp）／3 strings（StringPad の和音）／4 cello（OrchCello）
- 和声: i–VI–III–VII、i–iv–VII–III、i–VII–VI–V（2 つを選んで区間に割り当てる）
- 文法: 旋律ピアノは4分・2分主体の動機（跳躍の後は逆行）。4小節目の後半は休ませてフレーズ末を長音にする。伴奏ピアノは8分の分散和音（往復）、弦のパッドは b と outro、チェロは2分音符。音階は自然短音階（エオリアン）で、3つ目の進行の V だけ和声的短音階の長三和音。
- 区別: calm は長調・旋律なし。cinematic は8ch の管弦楽で盛り上がりがある。

#### 6.16.4 `energetic` — 元気なドラム主体のロック（mood、B6）

- 説明: 「元気・活動的。速いテンポと強いドラム、8分で刻むギターとベース」／"Energetic: fast, drum-driven rock with driving guitars and bass"
- 音色: 1 kick/snare（ProgKick・ProgSnare）／2 cymbal（ClosedHH・CrashCymbal）／3 bass（PickBass）／4 gtr（CrunchGtr）／5 lead（SquareLead）／6 tom（Tom）
- 和声: I–V–vi–IV、IV–I–V–vi、I–IV–vi–V（2 つを選んで区間に割り当てる）
- 文法: 倍速感のあるビート（kick 0・6・8・14／snare 4・12／ハット8分）、bridge はハーフタイム。ベースは8分の根音、ギターはパワーコードの8分刻み。区間頭に crash、フィルはタム＋スネア。
- 区別: rock より速く（160–176）明るい長調。jrock-90s は J-POP の曲構成と転調・ギターソロを持つ。

#### 6.16.5 `dreamy` — 夢見心地のアルペジオ（mood、E6）

- 説明: 「夢見心地。深い残響感のアルペジオとパッド」／"Dreamy: echoing arpeggios over lush pads"
- 音色: 1 kick/rim（PopKick・Rimshot）／2 sub（FbSub）／3 pad（GlassPad の和音）／4 arp（ArpBell）／5 arp echo（ArpBell）／6 flute（Flute）
- 和声: Imaj7–IVmaj7、Iadd9–iii7–IVmaj7–ivm6（2 つを選んで区間に割り当てる）
- 文法: アルペジオは16分の往復、`echo`（3 row 遅れ・0.5倍・2回）を5ch に書く。ドラムはハーフタイム（kick 0・10、rim 8）。サブベースは全音符、フルートはまばらな長音。
- 区別: ambient は拍が無い。calm はピアノ主体でエコーを使わない。

#### 6.16.6 `dark-tense` — 緊張感のある暗いパルス（mood、E6）

- 説明: 「緊張感。低音のオスティナートと刻むパルス、重い打撃」／"Dark and tense: low ostinato, ticking pulse and heavy hits"
- 音色: 1 taiko（Taiko）／2 tick（Hat909）／3 bass（SawBass）／4 strings（TensionStrings）／5 braam（Braam）／6 fx（Riser・Impact）
- 和声: i–bII–i–V、i–VI–iv–V（2 つを選んで区間に割り当てる）
- 文法: ベースは16分で根音・短2度・5度を往復（`pulse16`）、ハットは16分で途切れない。taiko は1・3拍目、braam は2小節ごと。build で riser、climax の頭に impact。
- 区別: suspense は無音と恐怖の効果音が主役。dark-tense は一定のパルスが途切れない。trailer は3幕構成で最後に壮大化する。

#### 6.16.7 `warm` — 温かいアコースティック（mood、B4）

- 説明: 「温かい。アコースティックギターとピアノ、長調の穏やかな伴奏」／"Warm: acoustic guitar and piano in a gentle major key"
- 音色: 1 cajon/shaker（CajonLow・CajonSlap・Shaker）／2 bass（FingerBass）／3 guitar（AcousticGtr の和音）／4 piano（Piano）
- 和声: I–V–vi–IV、I–IV–ii–V、I–vi–IV–V（2 つを選んで区間に割り当てる）
- 文法: カホン（low 0・8・10、slap 2・4拍）とシェイカー。ギターはストローク（`strum`: 0・4・6・10・12・14。弦ごとに 12 ms ずらした和音サンプル）、ベースは根音と5度、ピアノの旋律は順次進行主体。
- 区別: folk はフィドルと舞曲的なリズム。acoustic-ssw は指弾きのアルペジオと歌の旋律。

#### 6.16.8 `cool` — 涼しげな透明感（mood、E6）

- 説明: 「涼しげ。透明感のあるシンセと軽い2ステップのビート」／"Cool: glassy synths over a light two-step beat"
- 音色: 1 kick/snare（PopKick・Rimshot）／2 hat（Hat909・Clave）／3 sub（FbSub）／4 glass pad（GlassPad の和音）／5 pluck（SynthPluck）／6 echo（SynthPluck）
- 和声: i9–IV9、i7–bVIImaj7–bVImaj7–v7（2 つを選んで区間に割り当てる）
- 文法: `TWO_STEP`（kick 0・10／rim の snare 4・12／裏拍のハット／クラーベ）。グラス・パッドの和音、サブベースは2分音符、プラックの短い動機に `echo`。
- 区別: dreamy より拍がはっきりし速い。house より軽く4つ打ちではない。

#### 6.16.9 `focus` — 集中用のミニマルなローファイ（mood、B4）

- 説明: 「集中。ほとんど変化しないローファイのループと一定のテンポ」／"Focus: minimal lo-fi loop with a steady, unchanging groove"
- 音色: 1 drums（BoomBapKick・BoomBapSnare・ClosedHH）／2 bass（FingerBass）／3 e.piano（ElectricPiano の和音）／4 vinyl（VinylNoise）
- 和声: im7–IVmaj7、ii7–V7、Imaj7–vi7（1つを選び曲全体で使う）
- 文法: ブーンバップの型を曲全体で保ち、2和音のループを固定。旋律なし。8小節（2 pattern）ごとにハットの密度（4分／8分）だけが変わり、loop_b はキックを抜く。エレピは2拍ごとに和音＋`4xy` の揺れ、レコードのノイズを2小節ごとに鳴らし直す。16分スウィング 7:5。
- 区別: lofi-hiphop・lofi-chill は旋律と区間の変化がある。focus は意図的に変化を抑える。

#### 6.16.10 `rock` — ギター主体のロック（genre、B6）

- 説明: 「ロック。ギターのリフと8ビート、4/4 の中〜速いテンポ」／"Rock: guitar riffs over a straight eight-beat"
- 音色: 1 kick/snare（ProgKick・ProgSnare）／2 cymbal（ClosedHH・SwingRide・CrashCymbal）／3 bass（PickBass）／4 rhythm gtr（CrunchGtr）／5 lead gtr（ProgLeadGtr）／6 tom（Tom）
- 和声: I–bVII–IV–I、I–IV–V–IV、i–bVI–bVII–i（2 つを選んで区間に割り当てる）
- 文法: `BACKBEAT`（kick 0・8・10／snare 4・12／ハット8分）、サビはライドに替える。リフは根音の8分刻みから2小節ごとに5度・短7度へ動く（ミクソリディアン）。ソロ区間はリードギターが跳躍多めの旋律を `4xy` 付きで弾く。区間頭に crash、フィルはタム＋スネア。
- 区別: prog-rock は変拍子。energetic は速い長調のパンク寄り。indie-rock は軽い歪みとアルペジオ。

#### 6.16.11 `pop` — 明るいポップ（genre、B6）

- 説明: 「ポップ。長調の明るいメロディとピアノ、覚えやすいサビ」／"Pop: bright major-key melodies, piano and a catchy chorus"
- 音色: 1 kick/snare（PopKick・PopSnare）／2 hat（ClosedHH・Shaker・CrashCymbal）／3 bass（FingerBass）／4 piano（Piano の和音）／5 lead（VoxOoh）／6 pad（WarmPad の和音）
- 和声: I–V–vi–IV、vi–IV–I–V、I–vi–IV–V、IVmaj7–V–iii7–vi（3 つを選んで区間に割り当てる）
- 文法: §6.14 の歌もの。ピアノの和音を8分で刻み、verse はシェイカー主体の軽いビート。旋律は VoxOoh。最後から2つ目のサビ（chorus_up）で半音上げる。
- 区別: jpop-80s は80年代の音色（ゲートスネア・シンセブラス）と王道進行。city-pop はテンションコードとカッティング。

#### 6.16.12 `jazz` — モーダル・ジャズ（genre、B4 読み替え）

- 説明: 「ジャズ。ドリアンのモーダルなヴァンプ、4度堆積のピアノとミュート・トランペット」／"Modal jazz: dorian vamps, quartal piano voicings and muted trumpet"
- 音色: 1 ride/brush（SwingRide・SwingBrushSnare）／2 bass（SwingWalkBass）／3 piano（Piano の和音）／4 trumpet（MuteTrumpet）
- 和声: i11–i11–i11–ii11（1つを選び曲全体で使う）
- 文法: 8分格子（1 measure＝8 row、1拍＝2 row）と `SwingConfig(14, 10)`。和音は4度堆積（`quartal`: 根音から完全4度を4つ重ねた m11 の響き）の i11 に2小節ごとの ii11 を挟むヴァンプ。1 pattern＝8小節で AABA（B は半音上のドリアン、`key_offset=1`）。ベースは4分のウォーキング、ピアノはチャールストン、ミュート・トランペットは head で長音主体、solo で細かい動機。coda の7小節目で全員が長い和音を伸ばして終わる。
- 区別: **swing-jazz（既存）はビバップのリズムチェンジで速い**。jazz は和音がほとんど動かないモーダル（別ジャンルとして作ると決定。DESIGN_HISTORY.md §12.5）。

#### 6.16.13 `bossa-nova` — ボサノバ（genre、B4）

- 説明: 「ボサノバ。2/4 の柔らかいガットギターと軽いパーカッション」／"Bossa nova: soft nylon guitar and light percussion in 2/4"
- 音色: 1 rim/perc（Rimshot・Shaker・Surdo）／2 bass（FingerBass）／3 guitar（NylonGtr の和音）／4 flute（Flute）
- 和声: Imaj7–II7–iim7–V7、iim7–V7–Imaj7–VI7、im7–IV7、iim7b5–V7–im7–im7（2 つを選んで区間に割り当てる）
- 文法: 2/4（1 measure＝8 row）。リズムは2小節周期: リムのクラーベ（偶数小節 0・3・6、奇数小節 2・5）、ギターの和音（0・3・6／2・4・6）。ベースは付点4分＋8分（row 0 に根音、row 6 に5度）、スルドは2拍目。旋法は和音の種類ごと（m7→ドリアン、dom7→ミクソリディアン、m7b5→ロクリアン）。
- 区別: jazz・swing-jazz はスウィングする。bossa-nova はストレートな16分と2小節周期のクラーベ。

#### 6.16.14 `city-pop` — 80年代シティポップ（genre、B6）

- 説明: 「シティポップ。テンションコードのエレピ、跳ねるベースとギターのカッティング」／"City pop: jazzy electric piano, bouncy bass and funky guitar cutting"
- 音色: 1 kick/snare（PopKick・PopSnare）／2 hat（ClosedHH・Tambourine・CrashCymbal）／3 bass（SlapBass）／4 e.piano（ElectricPiano の和音）／5 lead（SynthBrass）／6 cutting gtr（CuttingGtr の和音）
- 和声: IVmaj7–III7–vi7–v7、ii7–V7–Imaj7–VI7、IVmaj7–V9–iii7–vi9（3 つを選んで区間に割り当てる）
- 文法: ベースは `synco16`（オクターブの跳躍を含む16分のシンコペーション）、ギターは `cutting16`（ミュートと本音の混在）、エレピは2拍ごとにテンションコード、ハット8分＋タンバリン。旋律はシンセブラス。
- 区別: jpop-80s は王道進行とブラスの決めで明るく速い。neo-soul は拍のよれと複雑なテンション。

#### 6.16.15 `ambient` — アンビエント（genre、A4）

- 説明: 「アンビエント。拍の弱い、重なり合うパッドとまばらなベル」／"Ambient: layered pads and sparse bells with little or no beat"
- 音色: 1 pad（WarmPad の和音）／2 glass pad（GlassPad）／3 bell（Bell）／4 bell echo（Bell）
- 和声: Imaj7、IVmaj7、vi9（3 つを選んで区間に割り当てる）
- 文法: 1 pattern に1和音（区間ごとに別の和音）。温かいパッドが和音を持続し、グラス・パッドは第3音か第7音を上で伸ばす。ベルは小節に0〜1音（bloom は1音多い）で、`echo`（5 row 遅れ・2回）を4ch に書く。打楽器なし。
- 区別: ambient-drone は和音がほぼ変わらない持続音。calm はピアノの分散和音の拍がある。

#### 6.16.16 `lofi-hiphop` — ローファイ・ヒップホップ（genre、B6）

- 説明: 「ローファイ・ヒップホップ。よれたビート、ジャジーなエレピ、レコードのノイズ」／"Lo-fi hip hop: swung beats, jazzy electric piano and vinyl noise"
- 音色: 1 kick/snare（BoomBapKick・BoomBapSnare）／2 hat（ClosedHH）／3 bass（FingerBass）／4 e.piano（ElectricPiano の和音）／5 lead（SwingSaxLead）／6 vinyl（VinylNoise）
- 和声: ii9–V13–Imaj9–vi7、Imaj7–iii7–vi7–IVmaj7、IVmaj9–iii7–ii9–Imaj9（2 つを選んで区間に割り当てる）
- 文法: `BOOMBAP`＋16分スウィング 7:5。エレピはチャールストンの和音＋`4xy` の揺れ、ベースはブーンバップの型、サックスの旋律は短い動機、レコードのノイズを2小節ごとに鳴らし直す。
- 区別: nostalgic（既存）はストレートな16分とオルゴール。lofi-chill はギター・フルートとサイドチェインのうねり。focus は旋律なし。

#### 6.16.17 `edm` — ビルドアップとドロップ（genre、E6）

- 説明: 「EDM。シンセ主体、ビルドアップで溜めてドロップで弾ける」／"EDM: synth-driven builds that explode into the drop"
- 音色: 1 kick（Kick909）／2 clap/hat（FbClap・Hat909・PopSnare）／3 bass（SawBass）／4 chords（PolyPad の和音）／5 lead（FbSupersaw）／6 fx（Riser・Impact）
- 和声: VI–iv–i–VII、i–VI–III–VII（2 つを選んで区間に割り当てる）
- 文法: 4つ打ち＋clap＋裏拍のハット。build は `buildup`（スネアが4分→8分→16分→`E9x`、音量上昇、riser）、ドロップの頭に impact、ドロップはスーパーソウのリードが2小節のフックを反復。ベースは裏拍の8分、ベースと和音に kick のサイドチェイン。
- 区別: uplifting はアルペジオ主体で長調の高揚。house はビルドアップが無く一定のグルーヴ。

#### 6.16.18 `house` — ハウス／ディープハウス（genre、E6）

- 説明: 「ハウス。4つ打ちの安定したグルーヴと裏拍のオルガン・スタブ」／"House: steady four-on-the-floor groove with offbeat organ stabs"
- 音色: 1 kick（Kick909）／2 clap/hat（FbClap・OpenHat909・Rimshot）／3 bass（DeepBass）／4 stab（HouseStab の和音）／5 pad（WarmPad の和音）／6 shaker（Shaker）
- 和声: im7–IV9、im9–bVIImaj7、im7–iv7–bVIImaj7–bIIImaj7（2 つを選んで区間に割り当てる）
- 文法: `DEEP_HOUSE`（kick 4つ打ち、clap 2・4拍、裏拍の open hat、シェイカー、リム）。スタブは裏拍、ベースは16分のシンコペーション（`house`）。パッドに kick のサイドチェイン。intro・outro はドラムだけ。
- 区別: edm はビルドアップとドロップの起伏。techno は和音をほとんど持たない。

#### 6.16.19 `hiphop` — ブーンバップ・ヒップホップ（genre、B4）

- 説明: 「ヒップホップ。ラップが乗る余白を残したブーンバップのビートとサンプル風ループ」／"Hip hop: boom-bap beats and sample-style loops that leave room for rap"
- 音色: 1 drums（BoomBapKick・BoomBapSnare・ClosedHH）／2 bass（FingerBass）／3 loop（Piano の和音）／4 horn（BrassHorn）
- 和声: i–VI–i–VI、i–iv–i–iv、im7–im7–bVImaj7–bVImaj7（1つを選び曲全体で使う）
- 文法: ブーンバップ＋16分スウィング 7:5。和音ループ（ピアノのチャールストン）を曲全体で固定。verse は中音域の旋律を置かずループとドラムだけ（ラップの余白）、hook でホーンの短い決めの動機が入る（hook は同じ pattern を再利用するので毎回同じ）。
- 区別: trap（既存）は 808 のグライドと32分のハイハット。hiphop はブーンバップのループとラップの余白（原文の「HipHop / Trap」の trap 部分は既存の trap が受け持つ）。

#### 6.16.20 `classical` — 古典派の弦楽四重奏（genre、Q4）

- 説明: 「クラシック。古典派のメヌエット風の弦楽四重奏、明確な和声と終止」／"Classical: a Classical-era minuet for string quartet with clear cadences"
- 音色: 1 violin 1（OrchViolin）／2 violin 2（OrchViolin2）／3 viola（OrchViola）／4 cello（OrchCello）
- 和声: I–IV–ii6–V、I–IV–V7–I、I–V/V–V7–I、I–vi–V/V–V、I–V7–V7–I、IV–I–V7–I、IV–V7–I–I（宣言順にすべて使う）
- 文法: 3/4（1 measure＝12 row、`variable_meter`）で 1 pattern＝4小節（48 row）＋`D00`（`MEASURES_PER_PATTERN=4`）。区間ごとに和声の役割が決まっているので進行は宣言順に固定（`FIXED_PROGRESSIONS`）: 前楽節（I–IV–ii6–V の半終止）、後楽節（I–IV–V7–I の完全終止）、属調の中間部（`key_offset=7`、V/V を含む）、復帰（V で止める）、下属調のトリオ（`key_offset=5`）、コーダ。vln1 が楽節の旋律、vln2・vla は2・3拍目に和音を刻み（直前の音に最も近い構成音で声部を滑らかにつなぐ）、vc は1拍目の低音（トリオは3拍目に5度も）。D00 を書く最終 row には空きチャンネルを1つ残す。
- 区別: orchestral（既存）は8ch の劇伴。classical は4ch の室内楽で、古典的な楽節構造と終止を持つ。

#### 6.16.21 `cinematic` — 映画音楽の情感（genre、O8）

- 説明: 「映画音楽。ピアノのオスティナートから弦とホルンが重なり、ドラマチックに高まる」／"Cinematic: piano ostinato building to soaring strings and horns"
- 音色: 1 piano（Piano）／2 violin（OrchViolin）／3 viola（OrchViola の和音）／4 cello（OrchCello）／5 contrabass（OrchBassStr）／6 horn（BrassSection）／7 choir（Choir の和音）／8 timpani（OrchTimpani・FreeCymbalSwell）
- 和声: i–VI–III–VII、VI–VII–i–i、III–VII–i–VI（宣言順にすべて使う）
- 文法: ピアノの8分の分散和音（往復）が全体を通し、区間ごとに層を足す: rise1＝チェロ・ヴィオラの和音、theme＝ヴァイオリンの旋律・コントラバス、rise2＝ホルン（和音の第3音）・合唱・ティンパニ（最後の小節はロール、2小節目にシンバルのスウェル）、climax＝全8ch（ティンパニは1・3拍目）。クライマックスは平行長調の響きを III–VII–i–VI（＝長調の I–V–vi–IV）で作る（`key_offset` を使わないので旋律の音階がそのまま合う）。進行は宣言順に固定。
- 区別: orchestral は古典的な機能和声で木管を含む。trailer は打楽器と金管の衝撃で、3幕の構成。

#### 6.16.22 `folk` — フォーク（genre、B4）

- 説明: 「フォーク。アコースティックギターのストロークとフィドル、素朴な進行」／"Folk: strummed acoustic guitar and fiddle over simple progressions"
- 音色: 1 stomp/clap（Stomp・FbClap・Tambourine）／2 upright bass（SwingWalkBass）／3 guitar（AcousticGtr の和音）／4 fiddle（Fiddle）
- 和声: I–IV–I–V、I–V–vi–IV、I–bVII–IV–I（2 つを選んで区間に割り当てる）
- 文法: 足踏み（1・3拍）と手拍子（2・4拍）＋タンバリン。アップライト・ベースは根音と5度、ギターは8分のストローク（弦ごとに 14 ms ずらした和音サンプル）。フィドルは8分の順次進行で、直前が空いている音に確率 0.3 で1つ上の音階音の前打音（16分）を付ける。instrumental はフィドルの細かい動機。
- 区別: warm はピアノの旋律と穏やかな伴奏。acoustic-ssw は指弾き。

#### 6.16.23 `rnb-soul` — R&B／ソウル（genre、B6）

- 説明: 「R&B／ソウル。滑らかなテンションコードと歌うような旋律のスロー・ジャム」／"R&B / soul: smooth extended chords and a singing melody in a slow jam"
- 音色: 1 kick/snare（PopKick・PopSnare）／2 hat（ClosedHH・Rimshot）／3 bass（FingerBass）／4 e.piano（ElectricPiano の和音）／5 vocal（VoxOoh）／6 strings（WarmPad の和音）
- 和声: IVmaj7–iii7–ii7–Imaj7、ii9–V13–Imaj9–Imaj9、vi9–ii9–V7sus4–Imaj9（3 つを選んで区間に割り当てる）
- 文法: 軽い16分スウィング 7:5。エレピは2分音符の和音＋`4xy` の揺れ、弦のパッド、ベースはブーンバップの型、旋律（VoxOoh）は長音主体で `4xy`。
- 区別: neo-soul は拍のよれと EP 中心・より複雑なテンション。city-pop は速くカッティングがある。

#### 6.16.24 `synthwave` — シンセウェイブ（genre、E6）

- 説明: 「シンセウェイブ。80年代のシンセとゲートスネア、8分で脈打つベース」／"Synthwave: 80s synths, gated snare and a pulsing eighth-note bass"
- 音色: 1 kick/snare（PopKick・GatedSnare）／2 hat（ClosedHH）／3 bass（SawBass）／4 poly pad（PolyPad の和音）／5 lead（SawLead）／6 arp（ArpBell）
- 和声: i–VI–III–VII、VI–VII–i–i、i–iv–VI–V（2 つを選んで区間に割り当てる）
- 文法: kick 1・3拍、ゲートスネア 2・4拍、16分のハット。ベースは8分のオクターブ、ポリシンセのパッド、アルペジオは8分の往復、ソーのリードは `4xy`。
- 区別: jpop-80s は明るい長調の歌もの。synthwave は短調でリードとアルペジオが主役。

#### 6.16.25 `techno` — ミニマル・テクノ（genre、T4）

- 説明: 「テクノ。繰り返しの中で少しずつ変わるシーケンスと4つ打ち」／"Minimal techno: a hypnotic four-on-the-floor with slowly mutating sequences"
- 音色: 1 kick（Kick909）／2 hats/clap（Hat909・OpenHat909・FbClap）／3 bass（SquareBass）／4 sequence（SynthStab）
- 和声: i7、i7–bVII（1つを選び曲全体で使う）
- 文法: 4つ打ち。区間ごとにドラム・ベース・シーケンスを出し入れ（intensity）。シーケンスは1和音（m7）をほぼ固定し、4小節ごとに16分の発音位置を1つずつ入れ替える。ベースは裏拍。
- 区別: minimalism（既存）は電子音ではない位相音楽。house は和音のスタブと温かさがある。

#### 6.16.26 `jpop-80s` — 80年代 J-POP 風（style、B6）

- 説明: 「80年代 J-POP 風。明るいコードと都会的なブラス、軽快なビートと最後のサビの転調」／"80s J-pop style: bright chords, city brass, a light beat and a final key change"
- 音色: 1 kick/snare（PopKick・GatedSnare）／2 hat（ClosedHH・Tambourine・CrashCymbal）／3 bass（FingerBass）／4 e.piano（ElectricPiano の和音）／5 lead（SquareLead）／6 synth brass（BrassPad の和音）
- 和声: IVmaj7–V7–iii7–vi、I–V–vi–iii、ii7–V7–Imaj7–vi7（3 つを選んで区間に割り当てる）
- 文法: kick 0・8・10、ゲートスネア、16分のハット、タンバリン。ベースは8分のオクターブ、エレピは2分音符。シンセブラスはイントロ・サビの頭で「決め」（0・3・6 の3連打）、それ以外は和音を伸ばす。最後のサビ（sabi_up）と outro で全音上げる。
- 区別: city-pop はより遅く、丸サ進行とカッティング中心。pop は現代的な音色。

#### 6.16.27 `jrock-90s` — 90年代 J-ROCK 風（style、B6）

- 説明: 「90年代 J-ROCK 風。歪んだギターが前に出る速いビートとギターソロ、最後のサビで転調」／"90s J-rock style: loud guitars over a fast beat, a guitar solo and a final key change"
- 音色: 1 kick/snare（ProgKick・ProgSnare）／2 cymbal（ClosedHH・CrashCymbal）／3 bass（PickBass）／4 dist gtr（CrunchGtr）／5 lead gtr（ProgLeadGtr）／6 clean gtr（CleanGtr）
- 和声: bVI–iv–v–i、i–VI–VII–i、VI–VII–v–i（3 つを選んで区間に割り当てる）
- 文法: kick 0・3・8・10（サビは 0・2・8・10 で前のめり）、歪んだパワーコードの8分刻み、ベースは8分の根音。Aメロはクリーンギターの8分アルペジオ、ソロはリードギター（`4xy` 深め）。最後のサビ（sabi_up）で半音上げる。
- 区別: rock は洋楽的なリフ中心の構成。energetic は長調のパンク寄りで転調しない。

#### 6.16.28 `anime-ost` — アニメの劇伴風（style、B6）

- 説明: 「アニメ劇伴風。刻むストリングスとジャズの和声、ブラスの決め」／"Anime soundtrack style: driving strings with jazz harmony and brass hits"
- 音色: 1 kick/snare（ProgKick・SwingBrushSnare）／2 ride/crash（SwingRide・CrashCymbal）／3 bass（SwingWalkBass）／4 piano（Piano の和音）／5 lead（SwingSaxLead・OrchViolin・BrassSection）／6 strings/brass（Spiccato・BrassSection）
- 和声: im7–ivm7–VII7–IIImaj7、iim7b5–V7–im7–im7、VImaj7–V7–im7–im7（3 つを選んで区間に割り当てる）
- 文法: kick＋ブラシのスネア、ライド、ウォーキング・ベース、ピアノはチャールストンの7th。主題はサックス（a）とヴァイオリン（b）が持ち替え、climax はブラスが歌う（`lead_key`）。ストリングスは16分の刻み（3+3+2 のアクセント）。intro・break・outro はブラス・ピアノ・ベース・キック・クラッシュの「決め」（16分の 3+3）を2小節ごとに入れ、最後は決めで終わる（決めは他のパートより優先して置き換える）。
- 区別: swing-jazz は小編成のジャズそのもの。anime-ost は弦と管の劇伴にジャズの和声を混ぜる。

#### 6.16.29 `jrpg` — JRPG のフィールド曲風（style、B6）

- 説明: 「ゲーム音楽風（JRPG）。旋律を重視した冒険のテーマ、ハープと弦とホルン」／"JRPG game music style: melodic adventure theme with harp, strings and horn"
- 音色: 1 timpani/snare（OrchTimpani・MarchSnare）／2 harp（Harp）／3 cello（OrchCello）／4 strings（StringPad の和音）／5 melody（Flute・OrchTrumpet）／6 brass（BrassSection）
- 和声: I–V–vi–iii、IV–I–IV–V、vi–IV–V–I、I–bVII–IV–I（宣言順にすべて使う）
- 文法: ハープは16分の上行分散和音、弦のパッド、チェロは2分音符、ティンパニは和音の変わり目、スネアは軽い行進風。旋律はフルート（b はトランペット）で、4小節の楽節の2小節目は1小節目の動機を1音階上げて繰り返す（ゼクエンツ。音域の上端を超える音はそのまま）。intro は金管のファンファーレ、b と ending は金管の対旋律（和音の第3音の長音）。進行は宣言順に固定: 主題はカノン型の8小節（a＋a2）。
- 区別: march は軍楽の行進曲。orchestral・cinematic は旋律より響き中心。jrpg は覚えやすい主旋律が主役。

#### 6.16.30 `lofi-chill` — ローファイ・プロデューサー風のチル（style、B6）

- 説明: 「ローファイ・チル。柔らかいギターとフルート、うねるサイドチェインと雨音」／"Lo-fi chill: soft guitar and flute, pumping sidechain and rain ambience"
- 音色: 1 kick/rim（BoomBapKick・Rimshot）／2 shaker（Shaker）／3 bass（FingerBass）／4 guitar（NylonGtr の和音）／5 flute（Flute）／6 rain（Rain）
- 和声: Imaj7–iii7–vi7–IVmaj7、IVmaj7–ivm7–Imaj7–vi7、Imaj9–IVmaj9（2 つを選んで区間に割り当てる）
- 文法: 16分スウィング 7:5。kick とリム（スネアの代わり）、シェイカー。ナイロンギターの和音（弦ごとに 18 ms ずらす）は2分音符、kick をトリガにギターと雨音にサイドチェイン（うねり）。フルートの旋律は `4xy`。
- 区別: lofi-hiphop はジャジーなエレピとブーンバップ。focus は旋律なし。lofi-chill はギター・フルート・雨音とサイドチェインのうねりで区別する。

#### 6.16.31 `indie-rock` — インディー・ロック風（style、B6）

- 説明: 「インディー・ロック風。生音のドラムと鳴り響くギターのアルペジオ、軽い歪み」／"Indie rock style: live-sounding drums, ringing guitar arpeggios and light overdrive"
- 音色: 1 kick/snare（ProgKick・PopSnare）／2 hat（ClosedHH・Tambourine・CrashCymbal）／3 bass（PickBass）／4 clean gtr（CleanGtr）／5 lead（SquareLead）／6 crunch gtr（CrunchGtr）
- 和声: I–IV–vi–V、I–iii–IV–iv、vi–IV–I–V（2 つを選んで区間に割り当てる）
- 文法: 半数の seed でキックを4つ打ち（ダンス寄り、`plan()` で決める）、それ以外は kick 0・6・8＋タンバリン。クリーンギターは8分のアルペジオ（往復）、サビで軽い歪みのギターがストロークを足す。ベースは8分。
- 区別: rock はパワーコードのリフ。jrock-90s は強い歪みと速さ。

#### 6.16.32 `trailer` — 映画予告編風（style、O8）

- 説明: 「映画予告編風。大太鼓と金管の衝撃、刻む弦、合唱で盛り上がる3幕構成」／"Cinematic trailer style: taiko and brass hits, driving strings and choir in three acts"
- 音色: 1 taiko（Taiko）／2 toms/snare（Tom・MarchSnare）／3 braam（Braam）／4 spiccato（Spiccato）／5 low strings（OrchCello）／6 choir（Choir の和音）／7 high strings（OrchViolin）／8 fx（Riser・Impact）
- 和声: i–VI–III–VII、i–bVI–bVII–i（2 つを選んで区間に割り当てる）
- 文法: 第1幕: 2小節ごとに taiko・braam（最初は impact も）の一撃と無音の間。第2幕: taiko の型、スピッカートの16分の刻み（3+3+2 のアクセント）、低弦、braam は2小節ごと。riser: taiko の4分、`buildup`（スネア）と上昇音。第3幕（半音上、`key_offset=1`）: 全合奏＋合唱＋高弦の旋律、奇数小節の末にタム、頭に impact。final は最初の一撃の後は余韻だけ。
- 区別: dark-tense は一定のパルスで起伏が少ない。cinematic は情感の旋律。trailer は衝撃・無音・加速で3段階に盛り上がる。

#### 6.16.33 `ambient-drone` — アンビエント・ドローン風（style、A4）

- 説明: 「ドローン。長く伸びる持続音がゆっくり移ろう、変化の少ない響き」／"Ambient drone: long sustained tones that shift very slowly"
- 音色: 1 drone（LowDroneBass）／2 fifth（DroneReed）／3 upper（GlassPad）／4 swell（FreeCymbalSwell）
- 和声: i（1つを選び曲全体で使う）
- 文法: 旋律・打楽器なし。低い主音のドローンと5度の持続音を通して保ち、上の音だけ8小節（2 pattern）ごとにドリアンの音階の段を1つ変える（最初と最後は無し）。音量は区間の大きな弧（intensity 0.2→0.8→0.2）に、4小節周期の余弦のうねり（持続音への音量セルを1小節に3回）を掛ける。3小節目の頭にシンバルのスウェル（intensity ≥ 0.5 の区間）。
- 区別: ambient は和音が変わりベルがある。ambient-drone はほとんど変化しない。

#### 6.16.34 `acoustic-ssw` — アコースティック弾き語り風（style、B4）

- 説明: 「弾き語り風。指弾きのギターと軽いパーカッション、歌のような旋律」／"Acoustic singer-songwriter style: fingerpicked guitar, light percussion and a vocal-like melody"
- 音色: 1 cajon/shaker（CajonLow・CajonSlap・Shaker）／2 bass（FingerBass）／3 guitar（AcousticGtr）／4 voice（VoxOoh）
- 和声: I–V–vi–IV、vi–IV–I–V、I–iii–vi–IV（2 つを選んで区間に割り当てる）
- 文法: トラヴィス奏法: 親指が4分で根音と5度を交互に、他の指が8分裏で上声を弾く（1チャンネルの単音）。カホンとシェイカーは軽く、ベースは全音符で弱く。旋律（VoxOoh）は息継ぎを強めに（動機の多くが最後の拍を空け、4小節目は後半を休む）。intro・outro はギターのみ。
- 区別: folk はストロークとフィドル。warm はピアノの旋律。

#### 6.16.35 `neo-soul` — ネオ・ソウル風（style、B6）

- 説明: 「ネオソウル風。よれたビートとエレピ主体の豊かなテンションコード」／"Neo soul style: laid-back off-grid beats and lush electric piano chords"
- 音色: 1 kick/snare（BoomBapKick・PopSnare）／2 hat（ClosedHH・Rimshot）／3 bass（FingerBass）／4 e.piano（ElectricPiano の和音）／5 vocal（VoxOoh）／6 e.piano 2（ElectricPiano の和音）
- 和声: bIIImaj9–ii7–iv9–i11、ii9–V13–iii7–VI9、i11–IV9（2 つを選んで区間に割り当てる）
- 文法: 強い16分スウィング 8:4。スネアとハットの一部を `EDx`（1〜2 tick）で遅らせる（スネア 0.35・ハット 0.25 の確率、§6.14）。エレピ2台（3ch は裏拍のスタブ＋`4xy`、6ch は持続）、ベースは16分のシンコペーション。
- 区別: rnb-soul はきれいなグリッドのスロー・ジャムと弦。neo-soul は拍のよれと EP の複雑な和音。

---

## 7. 出力形式

### 7.1 能力表・付帯情報・チャンネルパン（`core/formats.py`）

| `--format` | 拡張子 | チャンネル数 | 音量 | パン | 検査 |
|:---|:---|:---|:---|:---|:---|
| `mod`（既定） | `.mod` | 4 → `M.K.`、他は `xCHN`/`xxCH`（1..32） | effect `C` | プレイヤー固定（L R R L） | `verify.verify` |
| `xm` | `.xm` | 1..32 | effect `C` | サンプル pan ＋ vol column `Px` | `verify.verify_xm` |
| `s3m` | `.s3m` | 1..16 | volume column | ヘッダのチャンネルパン | `s3m.verify_s3m` |
| `it` | `.it` | 1..64 | volume column | ヘッダのチャンネルパン＋サンプル既定パン | `it.verify_it` |
| `midi` | `.mid` | 制限なし（楽器単位で MIDI チャンネルを割当） | velocity／CC11 | CC10 | `midi.verify_midi` |
| `mp3` | `.mp3` | XM に準ずる（1..32） | ― | ― | なし（ffmpeg の出力） |

- `OutputFormat(name, extension, max_channels, serialize, verify, description)`。全シリアライザは `(Song, WriteOptions) -> bytes`。
- `WriteOptions(channel_pans, initial_bpm, instrument_names, gm_voices, rows_per_measure, measure_rows)` はジャンル由来の形式中立な情報（Song 本体には持たせない）。
- **チャンネルパン**（0=左…255=右）: ①ジャンルの `channel_pans` 宣言 ②全サンプルが既定パン（128）なら Amiga 風 L R R L を 64/192 に緩めて繰り返す（0/255 の完全分離は耳障り）③明示パンのあるサンプルがあれば、各チャンネルで再生順に最初に鳴るサンプルの pan。
- エフェクトは次のものだけを使う。変換表に無いエフェクトは各 writer が例外で止める（新しいジャンルが未知のエフェクトを使っても黙って化けない）: `0xy` アルペジオ、`1xx`/`2xx` ポルタメント、`3xx` トーンポルタメント、`4xy` ビブラート、`9xx` サンプルオフセット、`Cxx` 音量（`Cell.vol`）、`D00` パターンブレイク、`E1x`/`E2x` 微小ポルタメント、`E9x` リトリガ、`EDx` ノートディレイ、`ECx` ノートカット、`Fxx`（<0x20 Speed、≥0x20 BPM）。

### 7.2 MOD（`writer.serialize`）

20 byte タイトル／31 × 30 byte サンプルヘッダ（長さ・ループは word、finetune、volume）／曲長／`0x7F`／order 128 byte／マジック（4ch は `M.K.`、1–9ch は `{n}CHN`、10–32ch は `{n:02d}CH`）／パターン（`max(order)+1` 個、1セル4 byte、row 優先）／サンプルデータ。4ch 以外は本家 ProTracker・Amiga 実機では再生できない（OpenMPT・MilkyTracker・libxmp 等は可）。`write_file` は同じディレクトリの一時ファイルに書いて `os.replace`（失敗時は一時ファイルを消して `OutputError`）。

### 7.3 XM（`writer.serialize_xm`）

- 1 楽器スロット＝1 XM instrument＝1 sample。エンベロープ・複数サンプルのキーマップ・vol column と effect の同時使用は使わない（音色の包絡は PCM に焼き込み済み、Cell の排他制約はそのまま）。
- **note = `t + 37`**（t=0＝period 856＝FT2 の C-3）。周波数表は **Amiga**（MOD と同じ period 単位で `1xx`/`2xx`/`3xx` を効かせる）。
- `header_size` = 276（`header_size` フィールド自身を含めて order 表の終わりまで。読み手はパターンの開始を `60 + header_size` とする）。
- 8-bit サンプルは**差分（delta）符号化が必須**。
- チャンネルパンは、既定パン（128）のサンプルを鳴らすセルの vol column に `Px`（`0xC0 | pan>>4`）で書く（XM は発音のたびにサンプル既定パンへ戻るため）。明示パンのサンプルはサンプル pan。
- ヘッダの初期 BPM は曲の BPM（先頭 row の `Fxx` を読まないプレイヤー対策）。

### 7.4 S3M（`core/s3m.py`）

- `SCRM`、`Cwt/v=0x1320`、`ffi=2`（unsigned サンプル）、初期 speed 6・tempo=曲の BPM、ステレオ。チャンネル設定はパン ≤128 を左（L1–L8）、それ以外を右（R1–R8）に割り当て、チャンネルパン表（`0x20 | pan>>4`、`dp=0xFC`）も書く。**上限 16 チャンネル**。
- サンプルは 8-bit unsigned（signed ^ 0x80）、`C2Spd = round(8363 × 2^(finetune/96))`。
- note = `((t // 12) + 3) << 4 | (t % 12)`（t=12＝period 428＝ST3 の C-4）。音量は volume column（S3M に音量エフェクトは無い）。パターンは 64 row・パック形式・16 byte 境界のパラポインタ。

### 7.5 IT（`core/it.py`）

- サンプルモード（インストゥルメント不使用）。1 楽器スロット＝1 IT sample。エンベロープ・NNA は使わない。
- `Cmwt=0x0214`、stereo、**linear slides=0**（Amiga スライドで MOD と同じ）、**Old Effects=1**（ビブラート深さが MOD と一致。0 だと半分になる）、初期 speed 6・tempo=曲の BPM、global volume 128、mix volume 48。
- チャンネルパン（0–64、未使用は +128 で無効）、チャンネル音量 64。サンプルは 8-bit signed・非圧縮、`C5Speed = round(8363 × 2^(finetune/96))`、既定パンは明示パンのあるサンプルだけ。
- note = `t + 48`（t=12 → C-5）。音量は volume column、パターンはチャンネルマスク方式のパック形式。

### 7.6 エフェクト変換（`core/effects.py`。S3M/IT 共通）

| MOD | S3M/IT | 備考 |
|:---|:---|:---|
| `0xy` | `Jxy` | |
| `1xx` / `2xx` | `Fxx` / `Exx` | xx ≥ 0xE0 は fine と解釈されるので 0xDF にクランプ |
| `3xx` | `Gxx` | |
| `4xy` | `Hxy` | IT は Old Effects=1 で深さを合わせる |
| `9xx` | `Oxx` | |
| `D00` | `C00` | 行 0 のみ使うので BCD/HEX の差は問題にならない |
| `Axy` | `Dxy` | MOD は上げ（x）を優先するので片方だけにして渡す |
| `Bxx` | `Bxx` | |
| `E1x` / `E2x` | `FFx` / `EFx` | fine ポルタメント |
| `E9x` | `Q0x` | 音量変化なしのリトリガ |
| `E6x` / `ECx` / `EDx` / `EEx` | `SBx` / `SCx` / `SDx` / `SEx` | |
| `Fxx`（<0x20）/（≥0x20） | `Axx` / `Txx` | Speed / Tempo |
| その他 | 例外 | 黙って落とさない |

### 7.7 MIDI（`core/timeline.py`・`core/midi.py`）

- `timeline`: Song を tick 単位で解釈し、order を辿って `Fxx`・`D00`・`EDx`・`E9x`・`0xy` を処理したイベント列（tick・絶対秒・チャンネル・発音/音量/停止）と曲長を返す。MIDI の生成と曲長の検査で使う。
- **SMF format 1、PPQ=96**（1 tracker tick = 4 MIDI tick、4分音符 = 24 tracker tick）。tempo meta = 60,000,000 / BPM。Speed の変化（スウィング）や `EDx` は tick 数の違いとして厳密に再現され、テンポカーブは tempo meta の列になる。
- Track 0: 曲名・テンポ・拍子（可変拍子は measure ごと）。以降は**楽器ごとに1トラック**。ドラム楽器は MIDI ch 10、旋律楽器は sample 番号順に ch 1–9・11–16。足りなければ同じ GM program の楽器を相乗りさせ、それでも足りなければエラー。
- **GM 音色**: `GmVoice(program=)` か `GmVoice(drum_note=)` を各ジャンルが楽器ごとに `gm_voices` で宣言する。楽器名からの推測はしない（全ジャンルの全楽器に宣言があることをテストで保証）。
- 変換規則:

  | トラッカー | MIDI | 精度 |
  |:---|:---|:---|
  | 音高 | `sounding_hz` × period 比から求めた実音（§3.1） | 厳密 |
  | 半音未満のずれ・finetune（maqam の微分音含む） | 楽器チャンネル単位の固定ピッチベンド（±2半音レンジ） | 厳密 |
  | 発音時の音量 | velocity = round(vol/64×127)（最小 1） | 厳密 |
  | 発音中の音量変化（サイドチェイン等） | CC11（その楽器を鳴らすトラッカーチャンネルが1つのとき） | 近似 |
  | 音の終わり | 次の発音／vol 0／`ECx`／ワンショットの自然減衰長／曲末のうち最も早いもの | 厳密 |
  | `EDx`・Speed 変化・`E9x`・`0xy` | tick 位置・再発音・tick ごとの音高切替 | 厳密 |
  | `1xx`/`2xx`/`3xx` | 目標音へ即時切替（グライドしない） | 近似 |
  | `4xy` | CC1（深さに比例、次の発音で 0） | 近似 |
  | `9xx` | 無視（頭から鳴る） | 非対応 |
  | チャンネルパン | CC10 | 近似 |

- MIDI の目的は「ジャンルの意図を GM 音源で聴ける／DAW に持ち込める」こと。サンプル音色の再現は目的外。

### 7.8 MP3（`core/render.py`）

曲を XM にして一時ファイルに書き、`ffmpeg -f libopenmpt -i tmp.xm -c:a libmp3lame -b:a 192k`（44.1 kHz ステレオ）で符号化する。ModWeaver は再生エンジンを持たない（自前の再生エンジンは大きく、しかも自作 writer を自作 player で検証する自己一致の罠に陥るため）。ffmpeg は PATH か環境変数 `MODWEAVER_FFMPEG` で探す。ffmpeg が無い、`-demuxers` に libopenmpt が無い、`-encoders` に libmp3lame が無い場合は、何が足りないかを示して `ExternalToolError`（終了コード 5、ファイルは作らない）。

---

## 8. CLI（`cli.py`）

### 8.1 オプション

| オプション | 短縮 | 既定 | 説明 |
|:---|:---|:---|:---|
| `--genre` | `-g` | `nostalgic` | ジャンル id（別名可）。`random` / `r` でランダム |
| `--seed` | `-s` | 100000〜999999 の乱数 | 任意の整数 |
| `--format` | `-f` | `mod` | `mod` / `xm` / `s3m` / `it` / `midi` / `mp3` |
| `--output` | `-o` | `output/<genre>_<seed>.<拡張子>` | 明示すればそのパスへ書く（存在しない親フォルダはエラー） |
| `--tempo` | `-t` | ジャンルが決める | `120` または `80-100`（§5.5） |
| `--list-genres` | – | – | 全ジャンルの id・別名・1行説明を区分（気分・ジャンル・〜風）ごとに表示して終了 |
| `--english` | `-e` | – | 表示を英語にする（§8.5） |
| `--version` | `-v` | – | `ModWeaver <版>` と GitHub URL を表示して終了（他の引数より優先） |
| `--help` | `-h` | – | 使い方を表示して終了。末尾は区分ごとのジャンル id だけ（説明は `--list-genres`） |

### 8.2 起動の分岐

1. `-e` / `--english`（`--eng` などの省略形を含む）を解析前に探し、表示言語を決める（usage の言語は解析前に要るため）。`-es 5` のようにまとめた場合は解析後の値で英語にする（この書き方で usage を出すときだけ日本語になる）。
2. `-e` 以外の引数が無ければ、`--help` と同じ usage を stdout に出して終了コード 0。
3. `--list-genres` はジャンル一覧を出して 0。`--version` は argparse の version アクション。
4. それ以外は生成（§2.3）。

### 8.3 `--genre random`

- 候補は登録済みの**正規 id**（別名は数えない。suspense-slow が2倍選ばれないように）。`--tempo` があれば `tempo_range` が要求と重なるジャンルだけを候補にし、1つも無ければ `TempoRangeError`（終了コード 2）。
- 選択は seed と独立（`random` モジュール）。再現はバナーの再現コマンド（選ばれたジャンル名が入る）で行う。
- 大文字小文字は区別する（`Random` は未登録ジャンル）。

### 8.4 出力先

`--output` 省略時は `output/<genre>_<seed><拡張子>`（カレントディレクトリの `output` フォルダ。無ければ作る）。拡張子は形式に合わせる（`midi` は `.mid`）。中身と拡張子が食い違うとプレイヤーが読み込みに失敗するため。

### 8.5 表示言語

- 既定は日本語、`-e` で英語。対象は usage（説明・オプション説明・見出し `使い方:`／`オプション:`／`ジャンル一覧:`）、`--list-genres` とヘルプ末尾の一覧（`description` / `description_en`、`別名:` / `alias:`）、実行結果のバナー（見出し・成功メッセージ・`(ランダム)`・`(指定 80-100)`）。文言は `cli.MESSAGES` の ja/en 表。
- 変えないもの: ジャンルが出す要約行（`plan.summary`。コード進行名などの音楽用語）、`--version` の出力、stderr のエラー・警告、生成される曲。
- argparse は `len()` で折り返すので全角が2桁ぶんはみ出す。ヘルプは表示幅（全角＝2桁）で折り返し、英数字の語（`free-jazz,` 等）は分割せず、句読点・閉じ括弧を行頭に置かない（`_wrap`）。
- バナーの見出しは表示幅で 12 桁に揃える（`ジャンル    : ` と `Genre       : ` の `:` が同じ桁）。

### 8.6 バナーと再現コマンド

区切り線・`ModWeaver: <display_name>`・ジャンル（random なら `(ランダム)`）・出力形式・シード・テンポ（範囲指定なら要求範囲も）・`plan.summary` の各行・出力ファイル・再現コマンド。再現コマンドは `<起動方法> --genre <id>`、指定されたときだけ `--format <形式>` と `--tempo <確定した BPM>`（範囲ではなく確定値）、最後に `--seed <seed>`。起動方法は `modweaver.py` なら `python modweaver.py`、それ以外は `python -m mod_weaver.cli`。

### 8.7 終了コード・例外・ログ

| コード | 意味 | 例外 |
|:---|:---|:---|
| 0 | 成功（引数なし・`--help`・`--list-genres`・`--version` を含む） | |
| 2 | 引数エラー、未登録ジャンル、対応できないテンポ | argparse、`ProfileNotFoundError`、`TempoRangeError` |
| 3 | 生成・検査エラー | `PlanError`・`VerificationError` ほか `ModGenError` |
| 4 | 出力エラー | `OutputError` |
| 5 | mp3 の外部ツール不足 | `ExternalToolError` |
| 1 | 想定外の例外（スタックトレースを出す） | その他 |

例外階層: `ModGenError` ← `ProfileNotFoundError`・`PitchRangeError`・`CellConflictError`・`ChannelConflictError`・`SampleConstraintError`・`TempoRangeError`・`PlanError`・`VerificationError(issues)`・`OutputError`・`ExternalToolError`。

ログは `logging.getLogger("mod_weaver")`。ハンドラは cli だけが設定し（stderr、WARNING 以上）、ライブラリ層は設定しない。検査の WARN は WARNING として出る。バナーは stdout。

---

## 9. 検査

### 9.1 構造検査（生成のたびに実行）

書き手と独立に実装したパーサで読み戻して検査する。ERROR があればファイルを書かない。

**MOD（`verify.verify`）**

| コード | 検査 | レベル |
|:---|:---|:---|
| V01 | ファイルサイズ = ヘッダ + パターン × 数 + Σサンプル長 | ERROR |
| V02 | マジック（`M.K.`/`xCHN`/`xxCH`）、タイトルが ASCII | ERROR |
| V03 | 曲長 1..128、restart=0x7F、order < パターン数 | ERROR |
| V04 | サンプル: 偶数長、volume ≤64、ループが範囲内 | ERROR |
| V05 | period が Period 表にある | ERROR |
| V06 | サンプル番号が定義済み | ERROR |
| V07 | note を持つセルにサンプル番号がある | ERROR |
| V08 | `Cxx` ≤ 64、`F00` でない | ERROR |
| V09 | チャンネルの許可サンプル（ChannelPlan を渡したとき） | ERROR |
| V10 | `order[0]` の pattern に BPM 設定（`Fxx`, xx ≥32）がある | ERROR |
| V11 | ループ境界の段差 ≤ max(2.0, 1.5 × ループ内最大の隣接差)（クリックの恐れ） | WARN |
| V12 | pattern 数 ≤ 64 | ERROR |
| V13 | 未使用のサンプル（nostalgic の flute は既知） | INFO |
| V14 | note の無い無効果セルにサンプル番号 | WARN |
| V15 | 4ch の曲だけ: チャンネル音量を追跡し、左（ch1+ch4）・右（ch2+ch3）の同時合計が 120 を超える row | WARN |
| V16 | アルペジオが Period 表の上限を超える | ERROR |

- **XM（`verify.verify_xm`）**: 同じ番号体系。V01 は宣言された各サイズの積算との比較、V05 は note が本プロジェクトの音域内、V15 はパンで加重した左右合計（左 = vol×(255−pan)/255）。
- **S3M / IT**: V01 構造・V02 マジック・V03 order・V04 サンプル・V05 音域・V06/V07 番号・V08 音量とテンポ値・V09 許可・V10 `Txx`（≥32）。
- **MIDI**: V01 読めるか・V02 ヘッダ（format 1／PPQ）・V03 End of Track・V04 note on/off の対応・V05 テンポ設定。
- **V15 は目安**: チャンネル音量の単純合計で、再生エンジンのミキシング（チャンネル数に応じたヘッドルーム、サンプル波形の振幅）を考えない。Amiga の 4ch 前提の目安で、多チャンネルでは割れなくても超えるため 6ch・8ch の曲は検査しない。音割れは全ジャンルを実測で検査する（§9.2）。

### 9.2 実プレイヤーによる検査（`tests/realplayer/`）

自作の writer と parser が同じ誤解を共有していると、読み戻しの検査は常に通ってしまう（実際に XM の `header_size` と音高で起きた。[DESIGN_HISTORY.md](DESIGN_HISTORY.md) §8）。そのため形式の正しさは第三者の実装（ffmpeg 内蔵の libopenmpt）で再生して確かめる。ffmpeg が無い環境では skip。時間がかかるので `slow` の印を付けてあり、普段は `-m "not slow"` で省略できる（マージ前は全部流す）。

| 検査 | 内容 |
|:---|:---|
| 形式間の等価性 | 同じ Song を MOD と XM/S3M/IT で再生し、曲長（±1%＋0.1 秒）・平均周波数（ゼロ交差法 ±5%）・RMS 包絡の相関（>0.8）が一致。orchestral は XM を基準に MOD/S3M/IT を比較 |
| テンポ | 全ジャンルが表示 BPM どおりの再生時間で鳴る（±2%＋0.3 秒）。`timeline` の曲長が実再生の長さと一致（0〜0.2 秒） |
| 音割れ | 全ジャンル × MOD/XM/S3M/IT × 2 seed の最大振幅 < 0 dBFS（float のまま・リサンプルなしで読む）。振幅最大の矩形波に差し替えた曲では失敗すること（検査が見逃さないこと）も確認 |
| MP3 | 作れること、デコードした長さ（±0.5 秒）・ステレオ・無音でないこと・音割れ率 < 0.1% |

### 9.3 目で・耳で確かめること（自動化の対象外）

OpenMPT 等で開けること、ループ境界のクリック、スウィングやサイドチェインの聴感、orchestral の定位。試聴で詰める数値は §11。

---

## 10. テスト

| 層 | 場所 | 主な検査 |
|:---|:---|:---|
| 単体 | `tests/unit/` | pitch・dsp・synth・model（Cell の直列化、put の規則、Instrument の範囲検査）・writer（レイアウト・原子的書込）・verify（ミューテーションで各コードが出る）・harmony・composer・engine（`apply_tempo`・契約検査・V15 は 4ch だけ）・registry（自動検出・登録時の検査）・各形式・timeline・midi |
| ジャンル | `tests/profiles/` | 文法・音域・ChannelPlan・決定性・構成（例: suspense の shock 前 8 row に発音が無い、march の Oom-Pah・ロール、全 arp が上限内）。第３段階の35ジャンルは `test_stage3_genres.py` が共通に検査（20 seed × 全形式で構造検査の ERROR・WARN なし、宣言の整合、決定性、`--tempo` で曲が変わらない、区間で鳴らさないパートに音が無い、最後のサビの転調） |
| 結合 | `tests/integration/` | CLI（終了コード、引数なし、random、`-e`、`--version`、出力先、各形式、mp3 の ffmpeg 不足） |
| 回帰 | `tests/regression/` | nostalgic を凍結した旧実装 `tests/reference/twilight_pad_v1.py`（SHA-256 固定）と 20 seed で比較。作曲（`plan()` の結果と pattern のセル配置）はバイト一致、サンプル波形は長さ・ピークが近いこと、ファイル全体は検査が通ること |
| 実プレイヤー | `tests/realplayer/` | §9.2 |

- 実行: `python -m pytest -q`（3054 件。実プレイヤー検査を含むと数分〜十数分かかる。ffmpeg が無ければ実プレイヤー検査は skip）。普段は `python -m pytest -q -m "not slow"`（2549 件）で実プレイヤー検査を省略し、マージ前に全部流す。
- 新しいジャンルは、全形式・複数 seed で構造検査が通ること、実プレイヤーの音割れ検査に通ること、`gm_voices` が全楽器ぶんあること、1ファイル1ジャンルであることがテストで自動的に確かめられる。

---

## 11. 未確定・試聴で調整する項目と将来課題

| 項目 | 現在の値 | 状態 |
|:---|:---|:---|
| swing-jazz のスウィング比 | 14:10（1.4:1） | 試聴で再調整可 |
| trap のロール確率・808 グライド速度 | 0.6、`portamento_param(rows=1)` | 同上 |
| future-bass のダッキング | bass 0.25/3、chord 0.35/4 | 同上 |
| maqam の旋律の跳躍確率 | 0.15 | 同上。Rast 以外のマカーム（Bayati 等）は未実装 |
| minimalism の音型 | 固定の4音型 | 同上 |
| free-jazz の密度 | bass 0.18、piano 0.25、perc 0.08、sax（climax）0.12 | 同上 |
| orchestral のボイシング・音量変化 | 度数の固定割当、セクション単位の音量 | 同上。measure 内のクレッシェンドは未実装 |
| prog-rock の lead のビブラート | なし | 必要なら march 相当のヘルパーを足す |
| nostalgic の pad/flute の −17.6 セント | K=32/L=1024 のまま | 直すなら K=6/L=190（+0.49 セント）。出力が変わるので回帰基準の更新とセット |
| MIDI のグライド | 目標音へ即時切替 | ピッチベンドでの近似は将来課題 |
| 第３段階の35ジャンルの音量・音色の釣り合い | 構造検査と実プレイヤーの音割れ検査に通る初期値（耳での調整は未実施） | 試聴で調整 |
| folk の前打音の確率、neo-soul の「よれ」の確率 | 0.3、スネア 0.35・ハット 0.25 | 同上 |
| jrpg のゼクエンツ | 音域の上端の音は上げずにそのまま | 動機ごとオクターブ下げるなどは将来課題 |
| 気分ジャンルの「相性」（晴れ・夜など） | §6.16 に記録するだけ | 天気・時間帯から選ぶ機能を作るときに属性（例: `affinity`）を足す |
| 外部ジャンルのプラグイン読込、WAV レンダラ | なし | 要件外 |
