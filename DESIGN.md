# ModWeaver 設計書

| 項目 | 内容 |
|:---|:---|
| 対象 | ModWeaver 1.1.0（`mod_weaver` パッケージ・`modweaver.py`・GUI `modweaver_gui.pyw`） |
| 本書の範囲 | **現在の実装がどうなっているか**だけを書く。なぜそうなったか・過去の案・訂正・レビュー記録は [DESIGN_HISTORY.md](DESIGN_HISTORY.md) |
| 最終更新 | 2026-10-03（フレームワークの再設計を統合: 形式を最初に決めて作曲する新しい枠組み〔`framework/`〕と、全51ジャンルの移植、形式ごとの Realizer・書き出し。再設計の決定の経緯と実装中に分かったことは DESIGN_HISTORY.md §15。統合前の原文は git 履歴で参照できる） |

---

## 0. 用語

| 用語 | 意味 |
|:---|:---|
| 形式（format） | `--format` の値。`mod`・`s3m`・`xm`・`it`・`midi`・`mp3` |
| Target | 形式ごとの能力表（チャンネル数・サンプルの解像度・音域・使える奏法など）と、その曲の予算（§3.2） |
| Score | 形式に依存しない楽譜。パートごとの音符（`NoteEvent`）の列と、和声・拍子・テンポの時間軸（§3.3） |
| Realizer | Score を形式の表現に変える層。トラッカー用（`TrackerRealizer`。MOD/S3M/XM/IT）と MIDI 用（`MidiRealizer`）（§7.6・§7.7） |
| ジャンル（Genre） | `framework.genre.Genre` のサブクラス。1ジャンル＝`mod_weaver/genres/` の1ファイル（§5） |
| パート（Part） | 役割を持つ声部（ドラム・ベース・和音・旋律・パッド…）。ジャンルが宣言する |
| ジェネレータ（Generator） | 1パートの音符を作るオブジェクト（§5.2・§5.8） |
| step | 区間の格子の1マス。既定は16分音符。トラッカーの row に当たる |
| tick | 時間の最小単位。**1拍＝24 tick**。1 step の tick 数は `24 / steps_per_beat` |
| lane | 1つのチャンネルに載る単音の流れ。パートは1つ以上の lane を持つ（和音を声部に開くと声部ごとに lane、打楽器は楽器ごとに lane） |
| 予算（budget） | その曲で使えるチャンネル数。形式・`--channels`・ジャンルの宣言で決まる（§7.6） |
| row | パターンの1行。1 row ＝ 1 step |
| pattern | トラッカーの行のまとまり。MOD・S3M は 64 row 固定（短い区間は `D00`／`C00` で切る） |
| tracker note `t` | MOD の Period 表上の音（0=`C-1` … 35=`B-3`） |
| logical note `n` | **書かれた音高**。`n = t + shift`（§3.1）。小数部はセント/100（微分音） |
| 実音（sounding pitch） | 実際に聞こえる高さ。楽器ごとに書かれた音高からずれる（§3.1。全形式で同じ規約） |
| 骨格 | 調・進行・各パートの音符の時刻と高さ。形式に依存しない部分（不変条件 I1、§10） |
| 実プレイヤー | ffmpeg 内蔵の libopenmpt（OpenMPT の再生エンジン）。自作ではない第三者の再生実装（§9.2） |

---

## 1. 概要と要件

### 1.1 目的

Python 標準ライブラリだけで、波形合成から作曲・シーケンス・ファイル出力までを行い、トラッカー音楽を自動生成する。
ジャンルごとの音楽理論の制約のもとで毎回違う曲を作り、seed で完全に再現できる。

**選んだ出力形式の規格を最大限生かして作曲する。** 形式を最初に決め、その形式の能力（チャンネル数・サンプルの解像度・音域・ボリューム列・エンベロープ・MIDI の同時発音など）に合わせて作曲する。ジャンルは「何をどう鳴らすか」だけを書き、チャンネル番号・pattern・row・エフェクト番号・形式の差はフレームワークが受け持つ（§2・§5）。

### 1.2 機能要件

| ID | 要件 |
|:---|:---|
| FR-1 | `--genre` で51ジャンルから選んで生成する（区分: 気分・ジャンル・〜風。§6）。`random` / `r` なら指定できるジャンルからランダムに選ぶ（§8.3） |
| FR-2 | 同じ genre・seed・format・tempo からは常に同じファイルを出力する。加えて、同じ genre・seed・tempo なら、形式が違っても**骨格は同じ**（調・進行・各パートの音符の時刻と高さ。§10 I1） |
| FR-3 | 出力形式を `mod`（既定）/ `xm` / `s3m` / `it` / `midi` / `mp3` から選べる（§7） |
| FR-4 | テンポを BPM または範囲（範囲内からランダム）で指定できる。未指定ならジャンルが決める（§5.5） |
| FR-4b | チャンネル数を `--channels` で指定できる。意味は形式ごとに違う: MOD は 4・6・8（ジャンルが宣言した数のうち）、S3M・XM・IT・MP3 は上限、MIDI は指定不可。未指定なら MOD はジャンルが曲ごとに seed から選び、他の形式は形式の上限（§7.1・§8.1） |
| FR-5 | ジャンルは `mod_weaver/genres/` に1ファイル置くだけで追加でき、core・framework・engine・cli の変更は不要（§5.6） |
| FR-6 | 生成物を構造検査し、規格違反があればファイルを書かない（§9.1）。どの形式でも、形式の制約に違反するファイルは書かない |
| FR-7 | 引数なしなら使い方を表示する。`--list-genres`（ジャンル一覧）と `--version`（版と GitHub URL）を持つ（§8） |
| FR-8 | 画面表示（使い方・ジャンル一覧・実行結果）は日本語が既定で、`-e` / `--english` で英語になる（§8.5） |
| FR-9 | ジャンル一覧と生成結果を機械向けの JSON でも出せる（`--json`。§8.8）。形式ごとのチャンネル数の選択肢も含む |
| FR-10 | CLI の生成機能を GUI からも使える（§12）。GUI はジャンル・形式・チャンネル数の選択肢を起動時に CLI から受け取り、自分では持たない |

### 1.3 非機能要件

| ID | 要件 |
|:---|:---|
| NFR-1 | 実行時の依存は Python 標準ライブラリのみ。例外は `--format mp3` の外部プログラム ffmpeg（libopenmpt・libmp3lame 入り）。GUI は標準ライブラリの tkinter を使う（Linux の一部のディストリビューションでは別パッケージ。例: `python3-tk`） |
| NFR-2 | Python 3.10 以上（テストは 3.10 で実施。`str.removeprefix` 等 3.9 以降の機能を使っている） |
| NFR-3 | 1曲の生成は数秒以内。高解像度の音色の合成は純 Python で重いので、`render()` の結果をプロセス内でキャッシュする（§4.8）。ディスクキャッシュは入れていない（最悪のジャンルで約1.2秒） |
| NFR-4 | トラッカー形式は OpenMPT 等の実プレイヤーで正しく鳴ること（音高・長さ・テンポ・音割れなし）を自動テストで確認する（§9.2） |
| NFR-5 | 開発時の依存は pytest（`requirements-dev.txt`）。実プレイヤー検査には ffmpeg（libopenmpt）が要る（無ければ skip）。MIDI の独立パースの検査には mido（無ければ skip） |

### 1.4 形式ごとの制約（作曲の前提）

形式の制約は Target（§3.2）が持ち、Realizer が吸収する。**MOD の制約が効くのは MOD だけ**:

- MOD: note は Period 表の36音（113〜856）、1セルに1エフェクト（音量も `Cxx` で同じ列）、sample は最大31、1サンプル ≤ 131070 byte、8-bit signed PCM、チャンネルは 4・6・8。
- S3M: 8-bit サンプル（高レートで描画）、ボリューム列、16 チャンネル。XM・IT: 16-bit サンプル、ボリューム列、XM 32／IT 64 チャンネル（IT は楽器モード・エンベロープ）。MIDI: 16 チャンネル（ch10 は打楽器）、同時発音。
- テンポは Speed（1 row の tick 数）と BPM。**1拍＝24 tick**（16分格子なら Speed 6 で 4 row）を前提に BPM を解釈する。
- MOD のサンプルの再生レートは `C-3`（Period 214）で `3546895 / (2×214) ≈ 8287.14 Hz`（PAL Paula クロック）。他の形式はこれを基準の音高にして高レートで描画する（§4.8）。

---

## 2. 全体構成

### 2.1 層と流れ

```text
cli.main
 └─ engine.generate(genre, seed, out, fmt=, tempo=, channels=)
     ├─ target = framework.target.resolve(fmt, channels, genre, seed)     # §3.2。予算もここで決まる
     ├─ plan   = framework.compose.resolve_plan(genre, seed)              # genre.plan()。形式に依存しない
     ├─ score  = framework.compose.compose(genre, plan, seed, target.features)   # Score（形式に依存しない骨格）
     │           └─ 区間ごと・パートごとに Generator を呼ぶ → genre.finalize_section
     ├─ realized = Realizer(target).realize(genre, score)                 # §7.6（トラッカー）／§7.7（MIDI）
     │           ├─ 音色の計画と描画（§4.8）
     │           ├─ パートの選択・lane の割当・チャンネル化
     │           ├─ セル化（奏法→エフェクト、音量、リリース、ミックス規則、row コマンド、pattern への詰め込み）
     │           └─ 音量の底上げ（§7.9）
     ├─ data   = writer[format](realized)                                 # §7.2〜7.5。形式のネイティブ表現を書くだけ
     ├─ issues = verifier[format](data)                                   # ERROR ならファイルを書かない（§9.1）
     └─ write_file(out, data)                                             # 一時ファイル → os.replace の原子的書込
```

依存の規則:

```text
gui/ ┄┄(子プロセス)┄┄▶ modweaver.py
cli.py ──▶ engine.py ──▶ framework/（Target・Score・Genre・部品集・Realizer）◀── genres/（ジャンル本体）
   │            │                    │                                              │
   └────────────┴────────────────────┴───────────────▶ core/（音楽系・形式系）◀────────┘
```

- `core` は `framework`・`genres`・`engine` を import しない。`framework` は `core` に依存する。
- **`genres` は `framework` と `core` の音楽系（pitch・harmony・composer・synth・synth_presets・model の型）だけに依存し、`core` の形式系（writer・s3m・it・midi・render・verify・level）と `framework.realize` を import しない**（テストで ast 検査する。`tests/framework/test_layering.py`）。
- Realizer はジャンルのクラスを知らない。宣言（`Instrument`・`Part`）と Score だけを受け取る。
- ジェネレータは Target を直接見ない。見てよいのは `ctx.features`（使える奏法の集合。§3.2）だけで、それも**奏法の付け外しにだけ**使い、乱数の消費や音符の時刻・高さを変えてはならない（I1）。
- `gui` は `mod_weaver` のほかのモジュールを import しない。CLI を子プロセスとして起動し、`--json` の出力だけで情報を受け取る（§12）。

### 2.2 モジュール一覧

| モジュール | 役割 |
|:---|:---|
| `modweaver.py` / `mod_weaver/__main__.py` | 起動スクリプト（`cli.main` へ委譲）。`python modweaver.py` と `python -m mod_weaver` は同じ |
| `mod_weaver/__init__.py` | `__version__`（1.1.0）・`__url__` |
| `cli.py` | 引数解析・表示言語・バナー・JSON 出力・終了コード（§8） |
| `modweaver_gui.pyw`・`modweaver_gui.bat` / `gui/` | GUI（§12）。`bridge.py`（CLI の呼び出し。tkinter 不使用）・`app.py`（tkinter の画面）・`texts.py`（日英の文言） |
| `engine.py` | 上の流れを呼ぶ薄い層。`build`（I/O なし）・`generate`・テンポ指定（§5.3・§5.5） |
| `errors.py` | 例外階層（§8.7） |
| `framework/target.py` | `Target`・形式ごとの能力表・予算の決定（§3.2） |
| `framework/score.py` | `NoteEvent`・奏法・`Automation`・`TempoEvent`・`SectionScore`・`Score`（§3.3） |
| `framework/plan.py` | `Meter`・`Swing`・`MeasurePlan`・`SectionPlan`・`SongPlan`、既定の `plan()`（§3.3・§5.4） |
| `framework/genre.py` | `Genre` 基底・宣言の型（`Instrument`・`Harmony`・`Section`・`Part`・`Kit`・`Double`・`Sidechain`）・宣言の検査（§5.1） |
| `framework/context.py` | `SectionCtx`・`MeasureCtx`・`Generator`（§5.2） |
| `framework/compose.py` | Score を作る（区間・パートの順序、乱数、依存関係、検査。§5.7） |
| `framework/registry.py` | ジャンルの登録簿・`genres/` の自動検出（§5.6） |
| `framework/gens/` | ジェネレータの部品集（§5.8）: `drums`（Groove）・`bass`・`comp`・`lead`・`pad`・`arp`・`fx`・`layer`・`echo`・`buildup`・`tempo`（`tempo_curve`） |
| `framework/realize/samples.py` | 音色の計画（どのサンプルを作るか）と描画の呼び出し（§4.8・§7.6） |
| `framework/realize/lanes.py` | パートの選択・lane・予算に収める手順（ladder）・チャンネル順・パン（§7.6） |
| `framework/realize/tracker.py` | `TrackerRealizer`（セル化・row コマンド・pattern への詰め込み・`Glide`・スウィング。§7.6） |
| `framework/realize/encode.py` | 奏法 → 形式ごとのエフェクト・ボリューム列（`Codec`。§7.6） |
| `framework/realize/midi.py` | `MidiRealizer`（§7.7） |
| `framework/levels.py` | 音量の底上げの根拠になる、ジャンル × 形式の最大振幅の測定値（§7.9） |
| `genres/*.py` | 51ジャンル（§6）。`_suspense.py` は suspense 2ジャンルの共通部分（ジャンルではない） |
| `core/pitch.py` | Period 表・音名・スケール・和音の型・微分音（§4.1） |
| `core/model.py` | `GmVoice`・`Cell`・`Pattern`・`SampleSpec`・`Song`（MOD の writer が読む表現）・`ChordSpec`・`ChordDef`（§3.4） |
| `core/harmony.py` | 和音の具体化 `voice()`（§4.2） |
| `core/composer.py` | 旋律生成・リズム型（§4.3） |
| `core/dsp.py` | 再生レート・PCM 化・波形/フィルタ/ループの基本関数（§4.4） |
| `core/synth.py` / `synth_presets/` | 音源合成（Patch 方式）と高解像度の描画、プリセット集（§4.5・§4.8） |
| `core/groove.py` | `E9x`・`EDx` の param（§4.6） |
| `core/structure.py` | ポリメトリックの行折返し（§4.7） |
| `core/formats.py` | 出力形式の一覧（名前・拡張子・説明・`--channels` の意味。§7.1） |
| `core/native.py` | `RealizedSong`（Realizer の出力）と、形式ごとの書き出し・検査への振り分け（§7.2〜7.5） |
| `core/writer.py` | MOD シリアライザ、XM の定数、原子的書込（§7.2） |
| `core/native_s3m.py`・`native_xm.py`・`native_it.py`・`native_midi.py` | S3M・XM・IT の書き出しと検査、MIDI の構造検査（§7.3〜7.5・§9.1） |
| `core/s3m.py`・`it.py`・`midi.py` | 形式の定数・補助と、writer とは独立の読み戻し（`parse_s3m`・`parse_it`・`parse_midi`） |
| `core/verify.py` | MOD・XM の独立パーサと MOD の構造検査（§9.1） |
| `core/native_level.py` | 出力音量の底上げ（§7.9） |
| `core/render.py` | ffmpeg による MP3 化と音量調整（§7.8） |

### 2.3 設計原則

1. **ジャンルは宣言とジェネレータだけを書く**。チャンネル番号・pattern・row・エフェクト番号・セル・サンプル番号・形式ごとの分岐はジャンルに出てこない。変更の種類ごとに直す場所が1か所に決まる（§11）。
2. **形式を先に決め、骨格は形式に依存しない**。形式で変わるのは、どのパートを入れるか（予算）・和音の鳴らし方・奏法の表現・音色の解像度だけ。あるパートの音符の乱数は予算で外れても消費する（作って捨てる）ので、骨格が形式に依存しない。
3. **Score は純粋データ**。`compose()` は I/O を持たず、テストは Score／バイト列を直接検査する。
4. **競合は宣言的・決定的に解決する**: 同じ lane・同じ step の発音は `prio` と `Kit.priority` で決まり、暗黙の上書きに頼らない。
5. **音楽の値は MOD の単位で書く**: 音量 0..64、ビブラート・アルペジオは MOD の param、時刻は step。形式ごとの換算は Realizer が行う。
6. **形式の能力は2段階で使う**。**自動**（全ジャンルに効く。宣言の変更不要）: 高解像度の音色、和音の声部化、打楽器の分離、予算に応じた任意パートの追加、専用の制御チャンネル。**ジャンルの opt-in**（宣言を足したジャンルだけ）: リリースのエンベロープ、IT のフィルタ、ステレオの重ね、大きな予算でだけ鳴らすパート。自動の部分で耳の調整が崩れる範囲を限定する。
7. **第三者の実装で検証する**: 自作 writer を自作 parser で読み戻す検査だけでは、両者が同じ誤解を共有すると検出できない。形式の正しさは実プレイヤーで確かめる（§9.2）。
8. **core に固定カテゴリを増やさない**: 音色は直交する要素の組合せで表し（§4.5）、ジャンル固有の判断・参照データはジャンル側に置く。ジャンル固有の文法はジャンルのファイル内のジェネレータとして書き、部品集（§5.8）に入れるのは2つ以上のジャンルが使うものだけ。
9. **拡張は opt-in**: 新機能は既定値では何も変えない属性・部品として足す。

---

## 3. データモデル

### 3.1 音高

- **tracker note** `t`: MOD の Period 表の並び（0=`C-1` … 35=`B-3`）。MOD の Cell に入る値。
- **書かれた音高（logical note）** `n`: ジャンルが書く音高。`f(n) = 65.4064 × 2^(n/12)` Hz（0＝C2）、MIDI ノート番号の目安は `n + 36`。**小数部はセント/100**（微分音。maqam・gamelan）。
- サンプルごとの `shift`（半音）で結ぶ: **`n = t + shift`**。MOD の発音時は `t = n − shift` が 0..35 に入る必要がある。これで「低音サンプルを C-3 で鳴らして 65 Hz を出す（`shift=−24`）」ことができ、36 音の制約を音域から切り離せる。他の形式は音域が広い（S3M・XM は 96 音、IT は 120 音）ので、Realizer が基準ノートから換算する（§7.6）。
- **サンプルの内容周波数**: 生成レート `R = CLOCK / (2·PERIODS[rate_note])`（MOD の描画の基準）。音高のあるサンプルは「`rate_note` の tracker note で発音すると logical note `rate_note + shift` が鳴る」ように波形を作る（内容周波数 `F = f(rate_note + shift)`、1周期のサンプル数 `spc = R/F`。どの n で鳴らしても spc は一定）。打楽器（`pitched=False`）は常に `rate_note` で発音し、内容を絶対 Hz で書く。例（`rate_note=C-3`、R=8287.14 Hz）:

  | サンプル | shift | F | spc | 発音 |
  |:---|:---|:---|:---|:---|
  | drone | −24 | 65.41 Hz | 126.7 | logical 0..11 を t=24..35 で |
  | tuba | −12 | 130.81 Hz | 63.4 | logical 0..11 を t=12..23 で |
  | strings / horn / section / pizz | 0 | 261.63 Hz | 31.68 | t = n |
  | lead / picc | +12 | 523.25 Hz | 15.84 | logical 12..47 を t=0..35 で |
- **実音 `sounding_hz`**: 合成は `dsp.sample_rate()`（実際の Paula 再生レートの半分）を基準に波形を作るため、実際に聞こえる高さは logical note と一致しない（ワンショットは1オクターブ上、ループはループ長に入れた周期数次第）。全音色はこの状態で耳で調整されている。**どの形式でも、書かれた音高 n の音は MOD で n を鳴らしたときと同じ実音・同じ長さで鳴る**ようにする（Realizer が `rate_hz` と基準ノートで合わせる。§4.8・§7.6）。「同じ実音」の基準は、`rate_note` で鳴らしたときの実音 `sounding_hz` から平均律で求めた高さ `sounding_hz × 2^((t − rate_note)/12)`。MOD の Period 表は整数に丸められているので、MOD 自身がこの基準から最大 5.9 セントずれる。S3M・XM・IT は基準どおり（平均律）に鳴らす。MIDI は `sounding_hz` から音高を求める（§7.7）。**`dsp.sample_rate()` を「直す」と全ジャンルの音が変わるので変えない。**

### 3.2 Target（形式の能力表。`framework/target.py`）

```python
@dataclass(frozen=True)
class SampleCaps:
    bits: int                  # 8 | 16
    target_rate: float         # 描画の目標再生レート（Hz）。MOD は 0（＝現行のまま描画。§4.8）
    max_bytes: int             # 1サンプルの最大バイト数
    max_samples: int           # サンプル（楽器）数の上限

@dataclass(frozen=True)
class Target:
    format: str                # "mod" | "s3m" | "xm" | "it" | "midi" | "mp3"
    kind: str                  # "tracker" | "midi"
    budget: int                # この曲で使えるチャンネル数（§7.6。MIDI は 16）
    sample: Optional[SampleCaps]   # MIDI は None
    note_range: tuple[int, int]    # 形式のノート番号で使える範囲（Realizer が書かれた音高から換算する）
    max_rows: int              # 1 pattern の最大 row 数
    max_patterns: int
    max_orders: int
    features: frozenset[str]   # 使える奏法・機能
```

`target.resolve(fmt, channels_request, genre, seed) -> Target` が作る。`mp3` は `it` と同じ Target を作り、`format="mp3"` だけ変える（IT を中継する。§7.8）。

形式ごとの値:

| 項目 | MOD | S3M | XM | IT | MIDI |
|:---|:---|:---|:---|:---|:---|
| 予算 | 4／6／8（`Genre.mod_channels` の重みで seed から選ぶか `--channels`） | 16 | 32 | 64 | 16（MIDI チャンネル。ch 10 は打楽器） |
| サンプルのビット深度 | 8 | 8 | 16 | 16 | ― |
| 描画の目標レート | MOD の Paula のまま（m＝1） | 44100 Hz（長さの上限で下げる） | 44100 Hz | 44100 Hz | ― |
| 1サンプルの上限 | 131070 byte | 64000 byte | 実質なし（書き出しでは 4 MiB） | 同左 | ― |
| サンプル数の上限 | 31 | 99 | 128（1楽器1サンプル） | 99 | ― |
| ノート範囲 | t＝0..35 | C-0..B-7（96音） | 1..96 | 0..119 | 0..127 |
| 1 pattern の row 数 | 64 固定 | 64 固定 | 1..256 | 32..200 | ― |
| pattern 数／order 長 | 64／128 | 100／256 | 256／256 | 200／256 | ― |
| 音量の置き場所 | `Cxx`（他のエフェクトと排他） | ボリューム列 | ボリューム列 | ボリューム列 | velocity・CC11 |
| パン | 固定（L R R L） | チャンネルパン | ボリューム列・サンプルパン | ボリューム列・チャンネルパン・サンプルパン | CC10 |
| エンベロープ | なし | なし | 音量 | 音量 | ― |
| フィルタ | なし | なし | なし | `Zxx`（既定の MIDI マクロ） | CC74 |

`features`（ジェネレータが見てよい唯一の形式情報）:

| 名前 | 意味 | MOD | S3M | XM | IT | MIDI |
|:---|:---|:---|:---|:---|:---|:---|
| `vol_with_effect` | 音量と他の奏法を同じ発音に付けられる | ✕ | ○ | ○ | ○ | ○ |
| `tremolo` | トレモロ（`Tremolo`） | ○ | ○ | ○ | ○ | ✕ |
| `release` | リリースのエンベロープ（`Instrument.release_s`） | 擬似（音量スライド） | 擬似 | ○ | ○ | ○（note off） |
| `filter` | フィルタのオートメーション（`Automation("cutoff")`） | ✕ | ✕ | ✕ | ○ | ○（CC74） |
| `pan_automation` | 発音中のパンの変化 | ✕ | ○ | ○ | ○ | ○ |
| `glide_bend` | グライドを連続的に表せる | ○ | ○ | ○ | ○ | ○（ピッチベンド） |

ジェネレータは `if "filter" in ctx.features:` のように**奏法を足すかどうか**の判断にだけ使う。features に無い奏法を書いても例外にはならず、Realizer が落とす（DEBUG ログ）。こうすれば、ジャンルは形式ごとに分岐しなくても全形式で動く。

### 3.3 Score と区間の計画（`framework/score.py`・`plan.py`）

#### 単位

| 量 | 単位 | 理由 |
|:---|:---|:---|
| 時刻 | **step**（区間の先頭から数える整数）。step 未満のずれは奏法 `Delay(ticks)` で表す | row と同じ感覚で書ける |
| 1 step の長さ | `24 // Meter.steps_per_beat` tick（16分格子なら 6 tick） | 1拍＝24 tick。MIDI は PPQ 480 なので 1 tick＝20 MIDI tick |
| 音高 | 書かれた音高（float）。整数部は logical note、小数部はセント/100 | 微分音は小数で書く |
| 音量 | 0..64 の整数（`None` は楽器の既定音量） | MOD の単位 |
| パン | 0..255（128 が中央） | |

#### 音符・イベント

```python
@dataclass(frozen=True)
class NoteEvent:
    step: int                        # 区間の先頭からの step
    inst: str                        # Instrument 名（Genre.instruments のキー）
    pitch: Optional[float] = None    # 書かれた音高。音程の無い楽器（Instrument.pitched=False）は None
    vel: Optional[int] = None        # 0..64。None は楽器の既定音量
    dur: Optional[int] = None        # step 数。None は「同じ lane の次の発音まで。ワンショットは自然減衰、ループは区間の終わりまで」
    chord: tuple[int, ...] = ()      # 和音: pitch（根音）からの半音の列。**根音を含む**（例: m9 は (0, 3, 7, 10, 14)）。空なら単音
    strum_ms: float = 0.0            # 和音の構成音ごとの鳴り始めの遅れ（ギターのストローク）
    prio: int = 1                    # 同じチャンネルに畳まれたときの優先度（大きいほど勝つ）
    arts: tuple["Articulation", ...] = ()

NoteOff(step, inst)                  # 明示的な消音（dur で書けないとき）。この楽器の鳴っている lane を止める
Automation(step, kind, value, inst=None)   # kind: "volume"（0..64）| "pan"（0..255）| "cutoff"（0..127）
TempoEvent(step, bpm)                # 区間内のテンポの変化（32..255）

@dataclass
class SectionScore:
    name: str; plan: SectionPlan
    parts: dict[str, list[Event]]    # パート名 → 時刻順のイベント
    tempo: list[TempoEvent]
    def mute(self, parts, start, end): ...   # finalize_section 用: 指定パートの [start, end) の NoteEvent/NoteOff を取り除く
    def add(self, part, event): ...          # finalize_section 用: 時刻順を保って挿入

@dataclass
class Score:
    bpm: int; key_pc: int
    sections: dict[str, SectionScore]   # 作成順（＝初出順）
    order: list[str]                    # 区間名の並び（同じ名前は同じ内容を繰り返す）
    summary: list[str]                  # バナーに出す行
```

#### 奏法（Articulation）

奏法は**意味**で書き、値は MOD の単位にする。Realizer が形式ごとに表現する（§7.6・§7.7）。

| 奏法 | 意味 |
|:---|:---|
| `Vibrato(param, at=0, steps=1)` | MOD `4xy` の param。発音から `at` step 後に `steps` 個の step で掛ける |
| `Tremolo(param, at=0, steps=1)` | MOD `7xy` の param（MOD・XM・S3M・IT で使える） |
| `Arpeggio(x, y, steps=1)` | `0xy`。発音の step から `steps` 個 |
| `Glide(steps=1, param=None)` | 同じ lane の直前の音からこの音へ滑らせる。`steps` で到達時間を指定するか、`param`（MOD `3xx` の速さ）を直接指定する。**直前の音が鳴り終わっていれば普通の発音になる**（§7.6） |
| `Delay(ticks)` | step 内で遅らせる（`EDx`）。`ticks` はその row の tick 数未満 |
| `Retrig(ticks)` | `E9x`。step 内の連打 |
| `Cut(ticks)` | `ECx` |
| `Offset(fraction)` | サンプルの途中から鳴らす（`9xx`）。サンプル長に対する割合（解像度が形式で違うため、バイト数では書かない） |

#### 区間の計画（ジェネレータが読む）

```python
@dataclass(frozen=True)
class Meter:
    steps: int = 16                  # 1小節の step 数（4/4 の16分＝16、3/4＝12、2/4＝8、7/8＝14）
    steps_per_beat: int = 4          # 表示 BPM の1拍の step 数（24 を割り切る値）
    signature: tuple[int, int] = (4, 4)   # MIDI の拍子の表示

@dataclass(frozen=True)
class Swing:
    long: int                        # 2 step の組の前半の tick 数
    short: int                       # 後半の tick 数（long + short == 2 × 24 // steps_per_beat）

@dataclass(frozen=True)
class MeasurePlan:
    index: int; start: int; steps: int       # 区間内の小節番号・先頭の step・この小節の step 数（可変拍子は小節ごとに違う）
    chord: ChordDef; quality: str            # voice() の結果と和音の種類
    chord_offset: int                        # 同じ和音の何小節目か（0 なら和音の変わり目）
    next_chord: ChordDef                     # 次の小節の和音（区間の最後は区間の先頭へ戻る）

@dataclass
class SectionPlan:
    name: str; kind: str; meter: Meter
    measures: tuple[MeasurePlan, ...]
    intensity: float                 # 0..1
    key_offset: int; tonic: int; scale: Scale
    parts: frozenset[str]            # この区間で鳴らすパート名
    swing: Optional[Swing]
    section: Section                 # 宣言（groove・fill・crash・motifs・tags を読む）
    extra: dict                      # plan() の上書きでジャンルが足す値（racing-breaks の系統・suspense の無音の位置など）

@dataclass
class SongPlan:
    bpm: int; key_pc: int
    sections: dict[str, SectionPlan]   # 作成順
    order: list[str]; summary: list[str]; extra: dict
```

**区間は名前ごとに1回だけ作曲する**。`order` で同じ名前を繰り返すと同じ内容が繰り返される（同じ文法で別の内容にしたいときは、区間名を分けて `Section.kind` を共通にする。suspense-chase の `a1`・`a2`）。**区間は音を持ち越さない**（ループ音色は区間の終わりで止まる）。

### 3.4 MOD の曲・サンプル・和声（`core/model.py`）

```python
@dataclass(frozen=True)
class Cell:                        # MOD の1セル
    note: Optional[int] = None     # tracker note（None=休符）
    sample: int = 0                # 0=指定なし, 1..31
    effect: int = 0                # 0..0xF
    param: int = 0                 # 0..0xFF
    vol: Optional[int] = None      # 0..64。effect/param と排他（併用は CellConflictError）

class Pattern: ...                 # 行×チャンネルの領域（put・get・serialize）
@dataclass
class Song: title; samples; patterns; order; instrument_names
```

- `vol` はシリアライズ時に MOD の `Cxx` になる。`Cell`・`Pattern`・`Song` は **MOD の writer が読む表現**で、Realizer は形式を問わず `core/native.py` の `RealizedSong`（`RGrid` の格子）を作り、MOD だけ `native.to_mod_song` でこの表現に直して `writer.serialize` に渡す。
- `GmVoice(program=)` / `GmVoice(drum_note=)`: 楽器の GM 音色（MIDI）。ジャンルの宣言が使うので、形式系ではなくここに置く。

```python
@dataclass
class SampleSpec:
    name: str                      # ASCII ≤22
    data: bytes                    # 偶数長 ≥2。8-bit（符号なし表現）または 16-bit signed PCM
    volume: int                    # 0..64（既定音量）
    loop: Optional[tuple[int, int]] = None   # (start_words, length_words)。"word" は data の2 byte
    rate_note: int = 24            # 生成レートを決める tracker note（既定 C-3）
    shift: int = 0                 # n = t + shift
    pitched: bool = True           # False: 常に rate_note で発音（打楽器）
    finetune: int = 0              # -8..7（1 単位 ＝ 12.5 セント。実プレイヤーで測った値）
    pan: int = 128                 # 0=左, 128=中央, 255=右
    sounding_hz: Optional[float] = None   # rate_note で鳴らしたときの実音（§3.1）。m に依存しない
    bits: int = 8                  # 8 | 16
    rate_hz: Optional[float] = None       # rate_note で鳴らすときに実際に使う再生レート（S3M の C2Spd・IT の C5Speed・XM の relative note と finetune の根拠）
```

| 型 | 主なフィールド | 意味 |
|:---|:---|:---|
| `ChordSpec` | `root`（主音からの半音）, `quality`, `bass`, `label` | 調に依存しない和音記述 |
| `ChordDef` | `label`, `bass`, `harmony`, `chord_tones`, `scale_tones`, `arp`, `explicit` | 具体化済み（logical note）。`explicit=True` は手組み |

---

## 4. core の機能

### 4.1 音高・スケール・微分音（`core/pitch.py`）

- `PERIODS`（36音、標準 PAL 表）、`NOTE_NAMES`、`name(t)` / `parse("C#2")`、`hz(n)`、`fold_into_range(n, lo, hi)`（オクターブ単位で音域へ折返し）、`nearest`、`lowest_note_with_pc`、`notes_with_pcs`、`note_for_hz`。
- `Scale(tonic_pc, intervals)` と `MODES`（ionian / aeolian / dorian / mixolydian / phrygian / dim_wh）。
- `CHORD_QUALITIES`（maj / min / dim / maj7 / m7 / dom7 など。半音オフセット）。
- 微分音: `MicroScale(tonic_pc, degrees_cents)` はセントで定義する音律（`degree_cents`・`absolute_cents(degree, tonic_note)`）。書かれた音高の小数部（`absolute_cents ÷ 100`）が微分音になる。MOD は finetune の変種サンプル（**finetune の刻みは実プレイヤーで測って 12.5 セント**＝-8 で -100、+7 で +87。50 セントのクォータートーンは ±4 で正確に出る）、S3M・IT は再生レートにセントを掛けた変種、XM はサンプルの finetune、MIDI はピッチベンド（§4.8・§7.6・§7.7）。`MOD_FINETUNE_CENTS = 12.5` は `framework/realize/samples.py`。

### 4.2 和音の具体化（`core/harmony.py`）

`voice(spec, tonic_pc, scale, regs, *, arp=False, mode_by_quality=None) -> ChordDef`。`Registers(bass, harmony, melody)` は各声部の logical note の範囲（各 11 半音以上）。

1. `root_pc = (tonic_pc + root) % 12`、`bass_pc` はスラッシュ／ペダルなら `bass`、なければ root。
2. `bass = lowest_note_with_pc(bass_pc, *regs.bass)`、`harmony = lowest_note_with_pc(root_pc, *regs.harmony)`。
3. `chord_tones` = メロディ音域内の構成音、`scale_tones` = スケール音（`mode_by_quality` に該当 quality があればそのモード。例: dim→`dim_wh`）∪ 構成音。
4. `arp=True` なら第3音・第5音のオフセットから `0xy` の param（dim=`0x36`、min=`0x37`、maj/maj7/dom7=`0x47`）。
5. 音域の検査は Realizer が形式ごとに行う（MOD は `t ∈ 0..35`、アルペジオは `t + max(x,y) ≤ 35`）。アルペジオを使うパートの基音は `t ≤ 35 − max(x,y)`（最大 +7 なら t ≤ 28）に収める。

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
- `MelodyGenerator(rules, register, scale, rng, base_vol, beat_rows=4)` と `bar(motif, chord, prev, cadence=, cadence_target=, octave_shift=)` → `(list[NoteEvent], 終端音)`:
  1. 強拍（`row % beat_rows == 0`）は直前音に近いコードトーン（確率 `strong_nearest_prob`、他は次点）
  2. 弱拍は確率 `dissonance_weight` でコード音から `color_semitones` 離れた音、それ以外は順次進行（確率 `1−leap_probability`）か跳躍
  3. 跳躍の後は `leap_recovery` なら逆向きに 1〜2 段
  4. `cadence=True` の最終音は `cadence_target`（無指定なら `chord_tones[0]`）
  5. 全音を `register` へ折返し。音量は強拍＝基準、弱拍＝基準−(4〜12)
- `NoteEvent(row, note, vol, dur)`（旋律生成の内部表現。`row` は step）。ジェネレータが `framework.score.NoteEvent` に変える（`dur = max(1, round(dur × gate))` でスタッカートにする）。
- `ramp(v0, v1, i, n)`（線形補間）。
- nostalgic は `MelodyGenerator` を使わず、旋律の規則をジャンル内に持つ（§6.1）。

### 4.4 DSP 基本関数（`core/dsp.py`）

`CLOCK = 3546895.0`、`sample_rate(rate_note)`（C-3 → 8287.14、B-3 → 15694.2）、`clamp`、`pad_even`、`to_pcm`、`additive`（Nyquist 超の倍音を除外）、`partials_saw/square/triangle`、`exp_decay`、`adsr`、`noise_lp`、`one_pole_lp`、`diff_hp`、完全ループ用の `seamless_loop`（倍率×周期数が整数でなければ `SampleConstraintError`）・`seamless_terms`（整数周期数を直接指定）・`circular`（3周連結してフィルタし中央1周を返す）・`with_attack`（ループ本体末尾に半コサイン窓を掛けたアタック部を前置）・`loop_design`（設計時の補助。実行時は定数を使う）。

ループの設計値（`C-3` 基準）: 261.63 Hz の持続音は K=6 / L=190（+0.49 セント）、65.41 Hz の低音ドローンは K=6 / L=760、1オクターブ上は K=12 / L=190。ループ音色の手順の例（drone）: `seamless_loop(760, 6, partials)` → `circular(one_pole_lp)` → `tanh` → `with_attack(body, 60)` → `SampleSpec(loop=(30, 380))`（`core/synth.py` の `Loop` がこれを行う）。

### 4.5 音源合成（`core/synth.py`・`core/synth_presets/`）

楽器ファミリーで分類せず、直交する要素の組合せで音色を書く。公開するのは `Patch` と `render(patch) -> SampleSpec` だけ。

- **Layer（信号源）**: `ToneLayer`（加算合成。倍音ごとに減衰率）、`PitchSweepLayer`（ピッチが下がる打撃音。絶対 Hz）、`NoiseLayer`（フィルタ付きノイズ。`decay_alpha` で減衰、`rise_power` で上昇）。`WeightedLayer` で重みを付けて混ぜる。`WeightedLayer.offset_ms` はレイヤーの鳴り始めを遅らせる（OneShot のみ。ギターのストローク用、§4.9）。
- **Finish（仕上げ）**: `OneShot(秒)`、`Loop(長さ, attack_samples=0)`（完全ループ。`attack_samples>0` ならアタック窓付き）。
- **Patch**: layers ＋ 後処理（`post_filter` → `decay_alpha` → `attack_ms` → `tail_fade_ms` → 正規化 `peak` → `saturate`）＋ サンプルの素性（`rate_note`・`shift`・`finetune`・`volume`・`pitched`）。
- 減衰・上昇のフィールドは全レイヤーで `Optional[float]`（None＝無効）。判別用の文字列フィールドは持たない。
- **制約**: `Loop` は `ToneLayer` のみ・`mult` は整数サイクル数のみ。`Patch.attack_ms` / `post_filter` / `decay_alpha` / `tail_fade_ms` は `OneShot` 専用。ループ音色の「息・擦弦ノイズ感」はノイズを混ぜず、隣接整数サイクル数のデチューンのうなりで出す。
- `pitched` は自動判定しない。`pitched=False` のとき `ToneLayer` の `mult` は絶対 Hz、True のとき `f0 = hz(rate_note + shift)` への比率（OneShot のみ）。
- **知覚寄りのファクトリ（1つのノブで複数パラメータを連動させる関数）は core に置かない**。連動が欲しければそのジャンルのファイル内にローカルな関数を書く。
- パンは音色ではなく配置の判断なので `Patch` には持たせず、`render()` の結果に `dataclasses.replace(spec, pan=...)` で付ける。
- `synth_presets/`（パッケージ）: 動作・音質を確認済みの `Patch` 136 個（`PRESETS`・`DESCRIPTIONS`、`find(keyword)`。どのモジュールの定数も `synth_presets.<定数名>` で参照できる）。`genre_kits.py` は第３段階より前の12ジャンルの音色（60個。`NOSTALGIC_*`・`SUSPENSE_*`・`MARCH_*`・`SWING_*`・`PROG_*`・`TRAP_*`・`MAQAM_*`・`MIN_*`・`FB_*`・`FREE_*`・`ORCH_*`）。第３段階の共有音色（54個）は**楽器の種類**で命名して系統ごとのモジュールに置き、複数のジャンルで使い回す: `drums.py`（`drum_*`）・`perc.py`（`perc_*`）・`bass.py`（`bass_*`）・`keys.py`（`keys_*`）・`guitar.py`（`gtr_*`）・`synths.py`（`syn_*`）・`pads.py`（`pad_*`・`vox_*`）・`orch.py`（`wind_*`・`str_*`・`brass_*`）・`fx.py`（`fx_*`。ノイズはループにできないので、長い OneShot を小節頭で鳴らし直す）・`metal.py`（`gamelan_*`・`ind_metal_*`。非調和の部分音と長い減衰の金属打楽器）。チップチューン（`chip_*`）・インダストリアル（`ind_*`）の音色は §6.17 のジャンルのために足したもの（計22個）。
- **新しい音色の作り方**: ① `find()` で近いプリセットを探す → ② `dataclasses.replace()` で差分を調整して `render()`・試聴 → ③ 良ければプリセットに登録。無ければ既存の3 Layer・2 Finish の組合せで `Patch` を組む（core に新しい Layer 種別を足さない）。


### 4.6 グルーヴ（`core/groove.py`）

- `retrigger_param(ticks)` → `E9x`（1 row 内の連打。音量は変えられない）、`delay_param(ticks)` → `EDx`。`framework/realize/tracker.py` が奏法の範囲を検査するのに使う。
- スウィング（偶数 step を `long`・奇数 step を `short` tick にする）は `Genre.swing`／`Section.swing`（`Swing(long, short)`）で宣言し、Realizer が書く（§7.6）。**`long + short = 2 × (24 / steps_per_beat)` でなければ表示 BPM どおりに鳴らない**: 8分格子（1拍＝2 step）は和 24（swing-jazz・jazz は 14/10＝1.4:1）、16分格子（1拍＝4 step）は和 12（例 7/5、neo-soul は 8/4）。`validate_swing` が宣言時に検査する。

### 4.7 可変小節とポリメトリック

- 小節の step 数は `Section.meter.steps`（4/4 の16分＝16、3/4＝12、2/4＝8、7/8＝14、trap の32分格子＝32、minimalism＝48）。1小節ごとに変える（可変拍子）ときは `Section.measure_steps`（prog-rock の 14・14・10）。pattern が 64 row に満たない区間の `D00`／`C00` は Realizer が書く（§7.6）。
- `polymetric_row(row, cycle_rows)` = `row % cycle_rows`（`core/structure.py`）。1小節を各パートの周期の最小公倍数の step 数にし、パートごとに周期で折り返して書く（minimalism）。

### 4.8 高解像度の描画（`core/synth.py`・`core/dsp.py`・`framework/realize/samples.py`）

```python
def render(patch: Patch, *, oversample: float = 1.0, bits: int = 8) -> SampleSpec: ...
```

- 倍率 `m = max(1, target_rate / real_rate)`。`real_rate = CLOCK / PERIODS[patch.rate_note]`（`rate_note` で鳴らしたときの実際の再生レート）。**MOD は常に m＝1**（8-bit・Paula のレートのまま）で、MOD の音は高解像度化の影響を受けない。S3M・XM・IT は `target_rate`（44.1 kHz）に近づける。
- 合成の内部レートを `dsp.sample_rate(rate_note) × m` にして描画する。時間（秒）で書かれた値（`OneShot` の長さ、`decay_alpha`、`attack_ms`、`tail_fade_ms`、`offset_ms`）と Hz で書かれた値（`PitchSweepLayer`、`ToneLayer` の基音）はそのまま使い、聞こえ方は変わらない。
- **サンプル数で書かれた値は m 倍する**: `Loop.length`・`Loop.attack_samples`（偶数に丸める）。**サンプル単位の係数は換算する**: `dsp.one_pole_lp(a)` と `noise_lp(a_start, a_end)` の係数は `a' = a^(1/m)`（同じ遮断周波数）。`dsp.diff_hp` は m>1 では同じ遮断周波数の1次 HP に置き換える。
- 加算合成は `nyquist = 内部レート / 2` 以上の部分音を捨てる。m>1 では捨てる部分音が減り、**高域が出るようになる**（これが解像度の改善）。
- 再生レート（`SampleSpec.rate_hz`。`rate_note` で鳴らすときのレート）: ワンショットは `real_rate × m`。ループは m 倍したループ長を整数に丸めるので `real_rate × L'/L`（周期数は変わらず、実音が厳密に一致する）。`sounding_hz` は m に依存しない。
- 量子化: 8-bit は `dsp.to_pcm`。16-bit は `round(x × 32767)` を [−32768, 32767] に切る。長さの上限（`SampleCaps.max_bytes`）を超えるときは m を上限に収まる最大値まで下げる（S3M の長い効果音など）。m＝1 でも超えるなら `SampleConstraintError`。
- キャッシュ: 描画は遅いので `(Patch, oversample, bits)` を鍵にプロセス内でキャッシュする（`functools.lru_cache`。`Patch` は frozen dataclass）。CLI は1回ごとに新しいプロセスだが、1曲の生成は最悪のジャンル（gamelan）の音色の合成で 1.2 秒程度なので、ディスクキャッシュは入れていない（遅くなったら、`(patch, oversample, bits, 描画コードの版)` を鍵にディスクキャッシュを足す余地がある）。
- 実音の一致（I7）: 全プリセットについて、m=1 と m>1 の描画を、m=1 のナイキスト以下の帯域で比べてスペクトルの包絡の相関が閾値以上（`tests/unit/test_synth_hires.py`）。

### 4.9 サンプルの計画と和音の焼き込み（`framework/realize/samples.py`・`core/synth.chord_patch`）

Realizer は Score とパートの選択（§7.6）の結果から、必要なサンプルを決めて番号を振る。

| 種類 | いつ作るか | 作り方 |
|:---|:---|:---|
| 楽器そのもの | 選ばれたパートが鳴らす楽器 | `render(instrument.patch, ...)` |
| 焼き込みの和音 | 和音を声部に開かない（ladder で「焼く」と決まった）パートの、使われた和音の形ごと | `chord_patch(base, intervals, strum_ms)`: `base` の音色で和音を1サンプルに焼き込む（ToneLayer を構成音の数だけ複製して部分音を音程比倍、音量は `1/√構成音数`。打鍵の雑音などのノイズ層は1回だけ）。`intervals` は**根音を含む**半音の列（`(0, 4, 7)`）。`strum_ms > 0` なら構成音ごとに鳴り始めを遅らせてギターのストロークにする（`WeightedLayer.offset_ms`、OneShot のみ）。**ループの素材はサイクル数を整数に丸める**ので、基本サイクル数が大きい素材でないと音程がずれる（誤差 12 セント超は焼けない）。オルガン・ブラス・シンセブラスのループはサイクル数が小さく sus4 しか作れないため、焼かずに声部に開く |
| 微分音・`tune_cents` の変種 | 書かれた音高の小数部（と `tune_cents`）が0でない音 | MOD は finetune の値ごとに変種のサンプル（12.5 セント刻み）、S3M・IT は再生レートにセントを掛けた変種、XM はサンプルの finetune、MIDI は §7.7 |
| パン違い | XM で既定パン以外を楽器に付けるとき、`Instrument.pan` | サンプルパン |

サンプルの並び: 楽器の宣言順 → 各楽器の変種（和音の形の初出順、セントの昇順）。サンプル名は ASCII 22 文字以内（和音の変種は `{patch.name[:13]}{quality}`、形に名前が無いときは `{patch.name[:13]}c{n}`）。数が `max_samples` を超えたら `PlanError`（MOD の 31 が問題になりうる。全ジャンル × 全予算のテストで検出する）。

---

## 5. フレームワークとジャンルの約束事

### 5.1 ジャンルの書き方（`framework/genre.py`）

ジャンルは**宣言**（楽器・和声・区間と構成・パート・編成）と、パートごとの**ジェネレータ**だけを書く。ジャンルが書かないもの: チャンネル番号、pattern、64 row、row 0・最終 row の空き、`D00`、エフェクト番号、セル、`off()`（ループ音色の消音は `dur` か `NoteOff`）、サンプル番号、形式ごとの分岐（`ctx.features` での奏法の付け外しを除く）。宣言の誤りは**クラス定義時**（`Genre.__init_subclass__` の検査）か、全ジャンル × 全予算の生成テストで見つかる。

```python
class Genre:
    # --- メタ ---
    id: str
    aliases: tuple[str, ...] = ()
    category: str = "genre"          # "mood" | "genre" | "style"
    display_name: str
    description: str                 # 日本語1行（--list-genres・--help に出す）
    description_en: str              # 英語1行（-e のとき使う）
    title: str                       # 出力ファイルのタイトル欄（ASCII ≤20。全形式共通）
    tempo_choices: tuple[int, ...]   # ジャンルが選ぶ BPM の候補（4分音符 BPM）
    tempo_range: tuple[int, int] = (32, 255)   # --tempo で上書きできる範囲

    # --- 宣言 ---
    instruments: Mapping[str, Instrument]    # 挿入順がサンプルの並び
    harmony: Optional[Harmony] = None        # None なら plan() を上書きして和音を自分で作る
    sections: Mapping[str, Section]
    form: tuple[str, ...]
    parts: tuple[Part, ...]                  # 並び順＝重要度の順＝チャンネルの並び（§7.6）
    swing: Optional[Swing] = None            # 全区間の既定（Section.swing で上書き）
    mod_channels: Mapping[int, int] = {4: 1} # MOD の予算 → 重み（例 {4: 1, 6: 2, 8: 1}）。キーは 4/6/8
    channel_cap: Optional[int] = None        # 美的な上限（chiptune・focus など、厚くしないことが目的のジャンル）
    mix: tuple[MixRule, ...] = ()            # サイドチェイン

    def plan(self, rng) -> SongPlan: ...     # 既定は §5.4。上書きするときは default_plan() を呼んで extra・summary を足すのが基本
    def finalize_section(self, sec, score, rng) -> None: ...   # 区間の全パートを作った後の、パートをまたぐ編集
```

`finalize_section` は**パートをまたぐ編集**（「決め」で他のパートを黙らせる、衝撃音の前を空ける等）に使う。`SectionScore.mute(parts, start, end)`・`SectionScore.add(part, event)` を使う。

#### 宣言の型

| 型 | フィールド |
|:---|:---|
| `Instrument` | `patch`（`core/synth` の `Patch`。`synth_presets` から取る）、`gm`（`GmVoice`。**必須**）、`volume`（既定音量。None は `patch.volume`）、`tune_cents`（音高の固定のずれ。例: orchestral の vln2 の +37.5）、`release_s`（opt-in: 消音のときのリリースの秒数。None は即時に止める）、`pan`（楽器ごとのパン）、`pitched`（None は `patch.pitched`） |
| `Harmony` | `keys`（主音の候補 pc）、`mode`（`MODES` のキー）、`mode_by_quality`、`registers`（`Registers(bass, harmony, melody)`）、`progressions`（`(名前, (ChordSpec, …))` の列）、`n_progressions`、`fixed`（True なら選ばず宣言順に全部使う）、`arp`（True なら `ChordDef.arp` を求める） |
| `Section` | `prog`、`measures`（既定 4）、`meter`（`Meter`）、`measure_steps`（可変拍子。指定したときは `measures` を既定値のままにする）、`intensity`、`parts`（鳴らすパート名。`follow` を持つパートは書かない。空は「`follow` を持たない宣言済みパートの全部」）、`key_offset`、`swing`、`groove`（ドラムの型の名前）、`fill`、`crash`、`motifs`（旋律の動機の組の名前）、`tags`（ジャンル固有の印。`"kime"`・`"spic"` など）、`kind`（空なら区間名） |
| `Part` | `name`、`gen`（ジェネレータ）、`pan`、`min_channels`（予算がこれ未満の曲では外す。6／8 の任意パート）、`kit`、`poly`（同時に鳴りうる音の数＝lane 数。和音を書くパートは 1 のまま）、`chord_spread`（和音を声部に開いたときのパンの広がり）、`double`（opt-in: デチューンした複製）、`follow`（付き従うパート。「follow のパートが鳴る区間」で鳴る。エコー・レイヤー用）、`depends`（先に作っておくパート。`ctx.events_of` で読める） |
| `Kit` | `groups`（「まとめた」段階の lane: `(lane 名, 楽器名…)`）、`priority`（畳むときの優先度。未記載 1）、`single_priority`（「1本」の段階だけの優先度。None なら `priority`）、`group_pan`（グループ名 → パン。未記載は `Part.pan`）。**打楽器でなくてもよい**（複数の楽器が1つのチャンネルを共有する suspense の texture＝strings＋pizz など） |
| `Double` | `detune_cents`、`spread`、`vel_ratio` |
| `Sidechain` | `triggers`（トリガの楽器名）、`targets`（下げるパート名）、`ratio`、`release_steps` |

検査（クラス定義時）: 全楽器に `gm`、`Kit.groups` の楽器・優先度・パンが宣言済み、`mod_channels` のキー ⊂ {4, 6, 8}、`min_channels` ∈ {0} ∪ `mod_channels` のキー ∪ {最大の予算より大きい値}、`follow`・`depends` の参照先が存在し循環が無い、パート名・楽器名の重複が無い、`Swing` が拍子と整合、`Sidechain` の参照先が存在。

#### 宣言の例（pop の抜粋）

```python
@register_genre
class PopGenre(Genre):
    id = "pop"; display_name = "Pop"; title = "Bright Pop"; category = "genre"
    description = "ポップ。長調の明るいメロディとピアノ、覚えやすいサビ"
    tempo_choices = (100, 104, 108, 112, 116, 120)
    instruments = {"kick": inst("drum_pop_kick", GmVoice(drum_note=36)), ..., "bass": ..., "piano": ..., "pad": ...}
    harmony = Harmony(keys=(0, 2, 5, 7), mode="ionian", progressions=PROGRESSIONS, n_progressions=3)
    sections = {"intro": Section(prog=0, intensity=0.4, parts=P("comp", "pad")),
                "verse": Section(prog=1, intensity=0.6, parts=BASE | P("lead"), groove="verse"), ...}
    form = ("intro", "verse", "pre", "chorus", "verse", "pre", "chorus", "bridge", "chorus", "chorus_up", "outro")
    parts = (
        Part("drums", Groove(GROOVES), kit=Kit(groups=(("kick/snare", ("kick", "snare")), ("hat", ("hat", "shaker", "crash"))),
                                               priority={"snare": 4, "kick": 3, "crash": 3, "hat": 2})),
        Part("bass", BassLine("bass", kind="root8", vol=54)),
        Part("comp", Comp("piano", kind="pulse8", vol=40), pan=88),
        Part("lead", Lead("lead", rules=LEAD_RULES, motifs=LEAD_MOTIFS, vol=50, gate=0.85, vibrato=0x32), pan=168),
        Part("pad", Pad("pad", vol=28), pan=64, min_channels=6),
        Part("lead echo", Echo(delay=3, ratio=0.45), pan=96, min_channels=8, follow="lead"),
        Part("strings", Layer("line", vol=26, register=(19, 31)), pan=160, min_channels=8, follow="lead"),
    )
    mod_channels = {4: 1, 6: 2, 8: 1}
```

**パートの宣言順は「最も厚い編成」の並びに合わせる**。4ch・6ch の並びはその部分列になる（ladder が予算に収まる範囲で後ろのパートから削る。§7.6）。

### 5.2 ジェネレータと文脈（`framework/context.py`）

```python
class Generator:
    """1パートの音符を作る。インスタンスはジャンルのクラス属性として共有されるので、状態を self に持たない。
    状態は ctx.state（区間ごと）・ctx.song_state（曲全体）に置く。"""
    def section(self, ctx: SectionCtx) -> None:   # 区間全体を作る。既定は小節ごとに measure() を呼ぶ
        for m in ctx.measures(): self.measure(m)
    def measure(self, m: MeasureCtx) -> None: ...
```

ジェネレータが呼ばれる区間はフレームワークが判定する: `Part.follow` があれば follow のパートが鳴る区間、無ければ区間の `parts` に自分のパート名がある区間。鳴らない区間でループ音色を止める処理は書かなくてよい（区間は音を持ち越さない。§7.6）。

`SectionCtx` の主な属性・メソッド:

| 名前 | 意味 |
|:---|:---|
| `genre`・`plan`・`song`・`part` | ジャンル・区間の計画（`meter`・`intensity`・`tonic`・`scale`・`section` 宣言・`extra`）・曲の計画・このパート |
| `rng` | このパート専用の乱数（§5.7） |
| `state`・`song_state` | この区間・このパートの状態（区間ごとに空で始まる）／このパートの曲全体の状態 |
| `features` | `Target.features`。奏法の付け外しにだけ使う |
| `bpm` | 曲の BPM（suspense・free-jazz のように秒から step を逆算するジャンル用） |
| `measures()` | 小節ごとの `MeasureCtx` |
| `events_of(part)` | `depends`（と `follow`）に書いたパートのこの区間のイベント |
| `own_events()` | このパートがこの区間で既に書いたイベントそのもの（書き換え可）。部品の `section()` を呼んだ後に加工する（前打音を足す等）ための口 |
| `step_seconds(step=1)` | スウィングを除いた step の長さ（秒） |
| `inst_seconds(inst)` | ワンショットが鳴り終わるまでの秒数（ループは None） |
| `scale_vol(vol)`・`scale_drum(vol)` | `vol × (0.55 + 0.45 × intensity)`・`vol × (0.6 + 0.4 × intensity)`（1..64） |
| `pitch_for(inst, pitch)` | 音程の無い楽器（vocal chop・効果音）には音高を渡せないので、部品が音高を落とすための補助 |
| `note(step, inst, pitch=None, vel=None, *, dur=None, chord=(), strum_ms=0.0, prio=1, arts=())` | 音符を書く（時刻は区間の先頭からの step） |
| `off(step, inst)`・`automate(step, kind, value, inst=None)`・`tempo(step, bpm)` | 消音・オートメーション・テンポの変化 |

`MeasureCtx` は `SectionCtx` を属性委譲で包み、`m`（`MeasurePlan`）・`is_first`・`is_last`・`is_chord_change` を持つ。`note()`/`off()`/`automate()`/`tempo()` の step は小節の先頭から（内部で `m.start` を足す）。

書いた時点の検査（`PlanError`）: `step` が区間（小節）の外、`inst` が宣言に無い、音程のある楽器に `pitch=None`、音程の無い楽器に `pitch` あり、`vel` が 0..64 の外、`Delay`・`Retrig`・`Cut` の ticks が row の tick 数以上（スウィングのある区間では短い側）、`poly != 1` のパートに和音。

### 5.3 エンジンの処理（`engine.py`）

- `build(genre, seed, fmt="mod", *, tempo=None, channels=None) -> Built`: 純粋関数（I/O なし。MP3 だけ ffmpeg を呼ぶ）。`Built` は `genre`・`seed`・`fmt`・`plan`・`score`・`target`・`data`（バイト列）・`channels`（実際に使った数。MIDI は鳴らした MIDI チャンネルの数）・`sample_bits`。`tempo` を渡すと `plan()` が選んだ BPM を上書きする。
- `verify_data(built)`: 形式の検査器（`core.native.verify`）を呼ぶ。MP3 は検査器が無い。
- `generate(genre, seed, out, *, verify=True, tempo=None, fmt="mod", channels=None) -> Result`: 検査で ERROR があれば `VerificationError`（ファイルは書かない）。WARN は WARNING ログ。`Result` は `seed`・`path`・`plan`・`issues`・`genre`・`tempo_request`・`fmt`・`channels_request`・`channels`・`channel_budget`・`sample_bits`。
- `supports_channels(genre, fmt, channels, seed)`: `--channels` の値でこのジャンルをこの形式で作れるか（`--genre random` の候補の絞り込み用。MOD は宣言した数、他の形式は ladder が収まるか）。
- `get_genre(name)`・`list_genres()`・`channel_choices(genre)`（MOD で選べる数）。`import` 時に `registry.discover("mod_weaver.genres")` でジャンルを登録する。

### 5.4 既定の `plan()`（`framework/plan.py`）

1. `bpm = rng.choice(tempo_choices)`（`--tempo` があっても**引いてから捨てる**。§5.5）。
2. `key_pc = rng.choice(harmony.keys)`。
3. 進行: `fixed` なら宣言順に全部、そうでなければ `rng.sample(range(len), k=min(n, len))`。
4. 区間名の初出順に `SectionPlan` を作る。小節への和音の割当は「1和音 `max(1, 小節数 // 和音数)` 小節で、進行を繰り返して小節数を埋める」。和音は `voice(spec, tonic, Scale(tonic, MODES[mode]), registers, arp=harmony.arp, mode_by_quality=...)`。
5. `summary` に調と進行。

進行の和音ごとの小節数が不揃い・手組みの和音・乱数で決まる計画のジャンルは `harmony=None` とし、`plan()` を上書きして `SectionPlan`・`MeasurePlan` を直接組む（march・nostalgic・minimalism・free-jazz・maqam・suspense の2つ）。曲ごとに乱数で決まる計画（無音の位置・クラスターの和音・音律など）は `plan()` が決めて `SectionPlan.extra` に置き、各パートのジェネレータが読む。

### 5.5 乱数とテンポ指定

- **乱数**: 計画は `random.Random(f"{seed}:{genre.id}:plan")`、パートは `random.Random(f"{seed}:{genre.id}:part:{part.name}")`（曲全体で1本。区間は作成順に作る）、予算の選択（MOD）は `...:channels`、テンポ範囲の選択は `...:tempo`、ジャンルが独自の乱数を要るとき（`finalize_section`）は `...:x:{name}`。文字列 seed は Python バージョン間で安定。**あるパートの変更が他のパートの乱数列を変えない**。**予算で外れたパートも作曲はする**（作って捨てる）ので、乱数の消費が予算に依存せず、骨格が形式に依存しない。サンプル合成は seed に依存しない（各 Patch の固定 seed）。seed 省略時は `random.randint(100000, 999999)`。seed は負値も含む任意の整数。
- `--tempo` の値は **4分音符の BPM**（1拍＝24 tick）。全ジャンルがこの値どおりに鳴る（実プレイヤーで検査）。例外として trap は32分格子のハーフタイムなので、表示 BPM は trap の慣習どおり（150 → 体感 75）。free-jazz は開始時の BPM を決める（以降のテンポカーブは `開始 BPM / 96` 倍に相似拡大）。
- `TempoRequest(lo, hi)`（単一値は lo=hi）。全体の許容は 32..255。構文エラー・範囲外は引数エラー（終了コード 2）。`resolve_tempo` は、ジャンルの `tempo_range` と重なる部分に切り詰める（一部だけ外れていれば WARNING、重ならなければ `TempoRangeError`＝終了コード 2）。範囲からの選択は専用ストリーム。
- **ジャンルの `plan()` は従来どおり BPM を引いてから、その値を捨てる**。これで他の乱数消費が変わらず、「同じ seed・別テンポ」は「同じ曲の速さ違い」になる（suspense・free-jazz は BPM から step や曲線を求めるので配置も変わる）。未指定なら出力は変わらない。`tempo_range` を狭めているのは free-jazz（44..163。カーブを拡大縮小しても全点が 32..255 に収まる範囲）だけ。

### 5.6 ジャンルの登録と追加

- `engine` の import 時に `registry.discover("mod_weaver.genres")` が `mod_weaver/genres/` 直下の `.py`（`_` で始まるもの・サブパッケージを除く）をすべて import する。`@register_genre` の付いたクラスが登録簿に入る。CLI は起動ごとに新しいプロセスなので、`--list-genres` は毎回ディレクトリを調べ直す。
- import に失敗したファイル、何も登録しないファイルは WARNING を出して無視する（1ファイルの不具合で他のジャンルまで使えなくしない）。検出前から import 済みのモジュールは登録の有無を検査しない（ジャンルモジュールを直接 import すると、その途中で検出が走り、登録前のモジュールが返るため）。
- `register_genre` の検査（違反は `ValueError`）: `id` が空でない、`description`・`description_en` がどちらも空でない1行、`category` が `mood`・`genre`・`style`、`id`・別名が予約語（`random`・`r`）でない、id・別名の重複が無い。
- **1ファイル＝1ジャンル**（テストで検査）。ジャンル以外の補助モジュールは `_` 始まりのモジュール（`genres/_suspense.py`）に置く。
- 新しいジャンルに必要なもの: `@register_genre` 付きの `Genre` サブクラス、日本語・英語の1行説明、全楽器の `gm`、`tools/calibrate_levels.py` で測った最大振幅（`framework/levels.py`。無いと音量を底上げしない。§7.9）、`tests/regression/golden.json` の更新（`tools/update_golden.py <id>`）、そして全形式で実プレイヤーの音割れ検査に通ること（§9.2）。
- `get_genre(name)`（別名も可。未登録は `ProfileNotFoundError`）、`list_genres()`（id 順）、`resolve_id(name)`。

### 5.7 作曲の順序と検査（`framework/compose.py`）

区間ごと（作成順）に:

1. パートを `depends`（`follow` を含む）で位相整列する（循環はクラス定義時に検査済み）。依存の無いパート同士は宣言順。
2. 各パートについて、鳴る区間（§5.2）なら `gen.section(ctx)` を呼ぶ。`follow` のパートは follow 先の後に作る。
3. `genre.finalize_section(plan, score, rng)` を呼ぶ。
4. `Score` の検査: 同じパート・同じ楽器・同じ step に2つの `NoteEvent` があり、**`prio` が同じ** → `PlanError`（`prio` が違えば高い方を残し、低い方を捨てる。march のスネアロールが通常のスネアを置き換えるのはこの規則）。`poly` を超える同時発音 → `PlanError`。

### 5.8 ジェネレータの部品集（`framework/gens/`）

値（step の表・音量の差・確率）は耳で調整済みのもの。ジェネレータはすべて `ctx.rng` を使う。

| ジェネレータ | 引数 | 動作の要点 |
|:---|:---|:---|
| `Groove(grooves, *, late={}, humanize=4, groove_name=…)` | `grooves: Mapping[str, tuple[Hit, ...]]`。`Hit(row, key, vol, prob, note)`、`hits(key, rows, vol, prob, notes)` で作る | 区間の `groove` の型を鳴らす。`fill` なら最後の小節の後半を `"fill"` に差し替え、`crash` なら最初の小節に `"crash"` を足す。`late` の楽器は確率で `Delay(1〜2)`（音量は既定）、それ以外は音量に ±humanize と `scale_drum` |
| `BassLine(inst, kind, vol)` | kind は `whole`・`half`・`root8`・`octave8`・`offbeat`・`rootfifth`・`bossa`・`walking`・`synco16`・`boombap`・`pulse16`・`house` | 16 step 基準の型を小節の step 数に比例させる |
| `Comp(inst, kind, vol, *, chordal=True, wobble=0, strum_ms=0)` | kind は `comp_rows()` の13種（`whole`・`half`・`pulse4`・`pulse8`・`offbeat`・`charleston`・`strum`・`bossa`・`stab2`・`arp8`・`arp16`・`fingerpick`・`cutting16`） | `chordal` なら `note(step, inst, chord.harmony, chord=QUALITY_INTERVALS[quality], strum_ms=...)`。`wobble` は `Vibrato(wobble, at=1, steps=1)` |
| `Pad(inst, vol, *, chordal=True)` | | 和音の変わり目に `dur=None`（次の発音まで） |
| `Arp(inst, register, steps, vol, *, pattern="up")` | | 指定 step で和音の構成音を `up`／`updown` |
| `Lead(inst, rules, motifs, vol, gate, *, vibrato=0, inst_for=None)` | `inst_for`: 区間 → 楽器名（区間ごとに旋律の楽器を持ち替える） | 区間の先頭で `MelodyGenerator` と動機 A・B を用意し、4小節の楽節（A・A・B・終止）。`gate` は `dur = max(1, round(長さ × gate))`。`vibrato` は 6 step 以上の音に `Vibrato(param, at=2)` |
| `Fx(inst, every, vol)` | | 一定間隔の効果音 |
| `Layer(inst, vol, *, chordal=False, register)` | | `follow` のパートが鳴る区間で、和音の変わり目に和音か第3音の長音。乱数を使わない |
| `Echo(delay, ratio, repeats=1)` | | `follow` のパートの `NoteEvent` を delay step 遅らせ、vel×ratio^k で写す（`dur` も写す）。区間の外に出るものは捨てる |
| `Buildup(inst, riser=None, n_measures=4)` | | 4分→8分→16分→`Retrig(3)` と加速するスネア。最後から2つ目の小節の頭に上昇音 |
| `tempo_curve(ctx, start_bpm, end_bpm, start_step, end_step, kind)` | `kind`: `linear`・`ease_in`・`ease_out` | BPM が変わる step にだけ `ctx.tempo()` を呼ぶ（free-jazz のルバート） |

---

## 6. ジャンル

51ジャンル。§6.1〜6.13 は個別の実装を持つ12ジャンル（文法を `Genre` の宣言とジャンル内のジェネレータとして書いたもの）、§6.14〜6.16 は共通の部品（`framework/gens/`）の上に宣言で書く35ジャンル、§6.17 は音色空間の疎な領域を埋めるために追加した3ジャンル、§6.18 はサウンドトラックの解析から作った1ジャンル。

**用語の対応**: 以降の各ジャンルの記述にある `4xy`・`0xy`・`3xx`・`9xx`・`E9x`・`EDx` は奏法の MOD での表記で、ジャンルは `Vibrato`・`Arpeggio`・`Glide`・`Offset`・`Retrig`・`Delay` として書く（§3.3）。また「チャンネル」「row」「measure」は、それぞれパート・step・小節に当たる。

以降の各ジャンルの記述にある「チャンネル」「論理チャンネル」（1 kick／2 …）は、各ジャンルの `parts` の宣言順（重要度の順）に当たる。物理チャンネルは Realizer が形式・予算から決める（§7.6）。「編成」の「4ch＝…／6ch＝…／8ch＝…」は MOD の予算ごとの ladder の結果で、ジャンルごとのテスト（`tests/framework/port_layouts.py`）が期待値として固定している。

個別の実装を持つ12ジャンルの宣言値:

| id | 表示名 | BPM | 1小節（step） | MOD の予算 | 構成（order） |
|:---|:---|:---|:---|:---|:---|
| `nostalgic` | TwilightPad Procedural | 88–96（2刻み） | 16 | 4 | intro, a, b, a, outro |
| `suspense-slow`（別名 `suspense`） | Suspense Slow | 64–72（2刻み） | 16 | 4 | hush, pedal, phrygian, pedal, shock, aftermath |
| `suspense-chase` | Suspense Chase | 138–148（2刻み） | 16 | 4 | intro, a1, a2, b, a1, b, climax, outro |
| `march` | Military March | 118–122 | 8（2/4） | 4 | intro, a, a2, a, a2, trio, trio2, trio, trio2, coda |
| `swing-jazz` | Swing Jazz | 152–168（4刻み） | 8（4/4、1 step=8分） | 4 | intro, a, a, b, a, solo_a, solo_a, solo_b, solo_a, a, a, b, out |
| `prog-rock` | Prog Rock | 132–148（4刻み） | 可変（14/10/16） | 4 | intro, verse, verse, chorus, verse, breakdown, chorus, outro |
| `trap` | Trap | 140/145/150/155 | 32（32分格子） | 4 | intro, verse, verse, hook, hook, half_time, hook, hook, outro |
| `future-bass` | Future Bass | 148/150/152/155/160 | 16 | 4 | intro_chop×2, buildup, drop×2, breakdown, drop×2, outro |
| `maqam` | Maqam Rast | 84–96（4刻み） | 16 | 4 | taqsim, ostinato_a, ostinato_b, taqsim, ostinato_a, coda |
| `free-jazz` | Free Jazz | 96（開始値。範囲 44–163） | 16 | 4 | movement_a, movement_b, climax, movement_c |
| `minimalism` | Minimalism | 108–120（4刻み） | 48 | 4 | phase0 … phase15 |
| `orchestral` | Orchestral | 76–88（4刻み） | 16 | 8 | intro, theme, development, climax, resolution |

音色の数値（Patch の値）は `core/synth_presets/` を正とする。以下は設計上の要点。これら12ジャンルの `harmony` は `None`（和声を手組みする・小節数が不揃い）か固定の進行で、`plan()` を上書きする（§5.4）。検査は `tests/framework/test_ported_genres_c.py`。

### 6.1 `nostalgic` — 夕暮れの Lo-Fi ビートとオルゴール

- 最初の実装（`twilight_pad.py`）の作曲の考え方を移したジャンル。**旧実装の挙動（バイト一致・乱数の消費順・Q1〜Q7）は保たない**（出力の互換は求めない）。
- **音色**（すべて `shift=0`）: kick（46 Hz へ指数降下するピッチの丸いキック）、snare（175 Hz の胴鳴り＋LP ノイズ）、hihat（金属共鳴＋HP ノイズ）、bass（サイン＋第2倍音）、musicbox（基音＋2・3倍音＋非整数 5.4 倍音の指数減衰）、pad（整数周期ループ K=32 / L=1024。−17.6 セントのわずかなうなりは音色の値として残している）。
- **パート**: drums（kit: kick・snare・hihat）、bass、pad、melody（musicbox）。
- **和声**: C メジャー／A マイナー。進行プール5種 `Step-Down`（Fmaj7–Em7–Dm7–Cmaj7）、`Royal Road`（Fmaj7–G7–Em7–Am7）、`Saudade`（Dm7–G7–Cmaj7–Am7）、`Journey`（Am7–Fmaj7–Cmaj7–G7）、`Canon Sunset`（Cmaj7–G7–Am7–Em7）。Theme A と B に異なる進行を割り当てる。手組みの `ChordDef(explicit=True)`（`harmony=None`、`plan()` で `MeasurePlan` を組む）。
- **構成**: 作成順 `[intro(A), a(A), b(B, サビ), outro(A)]`、order `[intro, a, b, a, outro]`。
- **旋律**: リズム型から動機を選び、小節1・2で反復（変奏）。強拍はコードトーン優先。経過音は 75% 順次進行・25% 跳躍。フレーズ末は解決音。サビは1オクターブ上（`min(3, octave+shift)` で頭打ち。音域 C-2〜B-3 を超えない）。intro は旋律と pad だけ、outro は音量が下がり、pad は `Automation(volume)` で 18→8→0 とフェードアウトする。ゴースト（サビの step 15）・小節末のフィル（bar 3 の step 14/15）は残している。

### 6.2 suspense 共通（`genres/_suspense.py`）

suspense-slow と suspense-chase が共有する音色・進行・語彙。ジャンルごとに `plan()` と文法（パートごとのジェネレータ）だけを別に持つ。

- **調・進行**（主音 C）: `pedal`＝Cdim → Db/C → Cdim → B/C（ベースは C のまま上声が半音でぶつかる）、`tritone`＝Cm → F#dim → Fm → Bdim、`phrygian`＝Cm → Dbmaj7 → Bbm → C。旋律は C フリジアン、dim 上では `dim_wh`。1区間＝4小節、1小節1和音（`voice(arp=True)`）。
- **音色**（7）: heart（38 Hz へ落ちる心拍。打楽器）、anvil（非調和部分音の金属音。`rate_note=B-3` の高レートで生成）、swoosh（徐々にフィルタが開くノイズの立ち上がり 0.9 秒）、drone（`shift=−24`、奇数倍音＋サブのループ、アタック付き）、pizz（`τ=0.08 s` のピチカート）、strings（同音デチューン対2組 K=(130,131)・(138,139) の大きなループ。C-3 で 2 Hz のうなり）、lead（`shift=+12` のループ。ポルタメントとビブラートは文法側で付ける）。
- **パート**: pulse（kit: heart・anvil・swoosh。優先度 anvil>swoosh>heart）、drone、texture（kit: strings・pizz。pizz が優先）、lead（kit: lead・pizz。pizz が優先）。
- **音域**: `BASS_REG=(0,11)`、`HARMONY_REG=(17,28)`（strings のアルペジオ基音）、`PIZZ_REG=(24,35)`、`LEAD_REG=(24,41)`。
- **語彙**: silence run（持続音を止める。drone・strings・lead はそれぞれの持ち主のパートが `off` を書く）、shock hit（anvil vol 64。直前 8 step は heart/pizz/lead を鳴らさない）、swoosh は衝撃の直前の小節の step `steps − round(0.9 / step_seconds)` から（`ctx.step_seconds()` から求める。slow は step 12、chase は 7〜8）、anvil の余韻の間（0.6 秒）は pulse の lane を心拍で切らない、ostinato crescendo（pizz を2 step 間隔で `ramp`）、strings は `Arpeggio`（`chord.arp`）付き（vel を持てない形式があるので既定音量）、`pedal` 進行では drone は常に C。dropout・anvil・スタブの位置は `plan()` が決めて `SectionPlan.extra` に置く。
- **区間は音を持ち越さない**ので、旧実装が pattern をまたいで鳴らし続けていた drone（shock の最初の小節）は区間の頭で鳴らし直す。

### 6.3 `suspense-slow` — 低速・重苦しい緊張

A・B の進行を `pedal`/`tritone`/`phrygian` から異なるものとして選ぶ。

| # | 区間 | 要点 |
|:--|:---|:---|
| 0 | hush | m2 から心拍、strings を小音量から段階的に |
| 1 | pedal | 心拍・drone・strings＋arp。途中の1小節を dropout（心拍・drone・strings が止まる）し、直後に確率で anvil、pizz のスタブ |
| 2 | phrygian | lead が 1〜2 音/小節（dissonance 0.6、2音目に `Glide(param=0x0A)`） |
| 3 | shock | 心拍の加速 → 全 16 step 無音 → swoosh → step 0 に anvil、pizz のオスティナート、lead 高音＋ビブラート |
| 4 | aftermath | 心拍・drone・strings が減衰して終わる |

### 6.4 `suspense-chase` — 緊急脱出・追走

A=`pedal`、B=`tritone` 固定。intro（pizz オスティナートのクレッシェンド）→ a1/a2（毎拍の心拍、drone の8分連打、半音・増4度を混ぜた pizz の音型、m2 後半の silence run と m3 の anvil。**a1/a2 は dropout とスタブの位置が違う**ので区間名を分け、`kind="a"` を共通にする）→ b（strings＋arp、lead）→ climax（各小節の anvil、pizz の16分クレッシェンド、swoosh）→ outro。

### 6.5 `march` — 行進曲

- **調**: C / F / Bb / Eb から選ぶ。トリオは主調＋5半音（下属調）。スケールは ionian。1小節 = 8 step（2/4、`Meter(8, 4, (2, 4))`、約1秒）、1区間 = 8小節。
- **音色**: bd、sd、crash（`rate_note=B-3`）、tuba（`shift=−12`、スタッカート）、horn（後打ち）、section（金管セクションのループ）、picc（`shift=+12` のループ。長音にビブラート）。
- **パート**: drums（kit: bd・sd・crash。crash>sd>bd）、tuba、harm（kit: horn・section。section が優先）、picc。MOD は4ch 専用。
- **進行**: `sousa`（C G7 C F C/G G7 C。最後の和音を2小節にして8小節に収める）、`heroic`（C F G C Am Dm G7 C）、`trio`（トリオ調で I I V7 I IV I V7 I）。和音ごとの小節数が不揃いなので `harmony=None` で `plan()` を組む。
- **構成**: intro（heroic。crash＋section の保持和音→無音→軽いスネア→ oom-pah、ファンファーレ）、a（sousa）、a2（heroic）、trio（軽いドラム、horn は単音、旋律は低め）、trio2（1オクターブ上、section の保持和音、crash、ロール）、coda（最終和音）。
- **文法**: Oom（step 0）＝tuba の根音（同じ和音が続けば根音と5度を交互）＋bd。Pah（step 4）＝horn の和音音＋`Arpeggio`（intensity ≥0.7）＋sd。フレーズ末の小節の step 4–7 はスネアロール（`prio=2` の sd が通常のスネアに勝つ）。crash は同 step の bd に Kit の優先度で勝つ。picc は gate 0.9。旋律フレーズは `[a, a', b, c, a, a', b, cad]`（c＝主音→3度→5度→オクターブの分散和音）。

### 6.6 `swing-jazz` — スウィング・ジャズ

- **音色**: ride、brush、walking bass（`shift=−12`）、piano comp（近接デチューン対でコーラス感）、sax（奇数倍音のループ、タンギングのアタック）。
- **パート**: drums（kit: ride・brush。brush>ride）、bass、piano、sax。
- **進行**: Bb、リズムチェンジ AABA。A＝Bb6 G7 Cm7 F7 Bb6 G7 Cm7/F7 Bb6、B＝D7 D7 G7 G7 C7 C7 F7 F7。ドミナント7th はミクソリディアン、m7 はドリアンで経過音を選ぶ（`mode_by_quality`）。1区間＝8小節。
- **文法**（`Meter(8, 2)`＝1小節 8 step・1 step＝8分、`swing=Swing(14, 10)`）: ride は ding-ding-a-ding（step 0,2,3,4,6,7、step 0/4 が強拍）、brush はバックビート（step 2,6）、ベースは4分のウォーキングで**終止が次の和音の根音**（`MeasurePlan.next_chord`）、ピアノは裏拍の2発（step 1,3 か 1,5）を選んで `Arpeggio`（intensity ≥0.75）か単音で刺す、sax は motif プールから `MelodyGenerator(beat_rows=2)`。ソロは跳躍確率・不協和を上げる。ときどき裏拍の音に `Retrig(5)` の装飾。intro はリズム隊（bass・piano）だけ、out の最終小節はタグ（全楽器で最終和音を保持）。

### 6.7 `prog-rock` — 変拍子プログレ／マスロック

- **音色**: kick、snare、crash（march の crash を 0.6 秒に短縮した派生）、distortion bass（`shift=−12`）、power chord guitar（ルート・5度・オクターブを1サンプルに焼き込み済み）、lead guitar（ループ）。
- **パート**: drums（kit: kick・snare・crash。crash>snare>kick）、bass、gtr、lead。
- **進行**: E エオリアン、i–bVII–bVI（riff）、bVI/i 交互（breakdown）、i–bVII–bVI–bVII（chorus）。和声より拍子の変化が主役。
- **構成**: リフの区間 = 7/8 + 7/8 + 5/8（`Section.measure_steps=(14, 14, 10)`＝38 step の3小節）。chorus は 4/4 × 4（`(16,)*4`）に戻して対比を作る。breakdown は 5/8 × 6（`(10,)*6`）。
- **文法**: 拍子ごとのリフの動機を `m.steps` で引く。キックはギターのアクセントと同じ step、フレーズ末に crash、ベースはギターのルートをユニゾン、lead は chorus だけ（chorus に gtr は無い）。intro・outro はドラム tacet。

### 6.8 `trap` — トラップ／ドリル

- **音色**: 808（`shift=−12`、ロングテールのサイン）、snare/clap、closed hat、open hat、lead pluck。
- **パート**: bass808、snare、hat（kit: hat_c・hat_o。open が優先）、lead。
- **進行**: C マイナー、i–VI（Cm–Ab）の2和音ループを全区間で固定。`Meter(32, 4)`（32分格子。1小節＝8拍。表示 BPM はハーフタイムの慣習）で各区間2小節＝64 step。セクションの違いはドラム編成で出す。
- **文法**: 808 は step (0,8,12,20) で根音と5度を交互に鳴らし、小節の最初の打は頭から（vol 60）、2打目以降は `Glide(steps=1)`。**グライドの規則は Realizer が持つ**: 先行音（ワンショット）が鳴り終わっていれば `3xx` ではなく新しい打鍵になり、鳴っていれば、直前の音の period から1 step で届く速さの `3xx`/`Gxx`（§7.6）。ハットは8分で、小節に1か所、確率 0.6 で `Retrig(3)` のロール。フレーズ末に open hat（Kit の優先度で closed に勝つ）。snare は step 16・28。lead は hook だけ。

### 6.9 `future-bass` — フューチャーベース

- **音色**: kick、sub（`shift=−12` のループ）、supersaw（隣接整数サイクル数の3層ループ）、vocal chop（`pitched=False` の長いサンプル。`Offset(i / 6)` でシラブルを切り替える）、clap。
- **パート**: kick（kit: kick・clap。clap>kick）、sub、chord、vox。
- **進行**: Eb メジャー、I–V–vi–IV。
- **文法**: drop・buildup の kick は4つ打ち。sub・saw は小節の頭で鳴らして持続。**ダッキングは `Genre.mix` の `Sidechain`**: kick と clap は同じチャンネルで優先度を共有し、バックビートでは clap が kick を置き換えるので、**kick と clap の両方をトリガに登録**する（sub: ratio 0.25 / release 3、chord: 0.35 / 4）。

### 6.10 `maqam` — 中東マカーム（Rast on G）

- **音律**: `MicroScale(tonic_pc=7, degrees_cents=(0, 200, 350, 500, 700, 900, 1050))`。3度と7度が中立音程。qarar（主音）を G-2 に置き、**度数ごとの音高を `MicroScale.absolute_cents ÷ 100` の小数**で書く（中立音程は x.5。`oud_n3`・`oud_n7` のような派生楽器は無い）。MOD は 12.5 セント刻みの finetune の変種サンプル、S3M・XM・IT はレート／finetune、MIDI はピッチベンドで出る（§4.8）。
- **音色**: oud（撥弦のピッチドロップ付き）、nay（ドローン用ループ）、qanun（分散和音）、daf の DUM・TEK。
- **パート**: perc（kit: dum・tek。dum>tek）、oud、nay、qanun。
- **リズム**: usul maqsum（16分格子で DUM step 0,10、TEK step 4,12）。
- **和声の使い方**: `ChordDef` を手組みし、`bass`＝qarar、`harmony`＝ghammaz（5度）、`scale_tones`＝ジンスの音。転調しないので `harmony=None` で `plan()` を組む。
- **文法**: oud の旋律は専用の `maqam_phrase()`（順次進行中心、跳躍は4度・5度のみ）。nay は区間の頭で持続、qanun は小節頭で上行分散和音。taqsim は oud だけ（打楽器なし。step の粗密で自由リズム感）。coda は最終小節の qarar のユニゾン。

### 6.11 `free-jazz` — フリージャズ

- **音色**: piano cluster（ほぼ半音刻みの5層）、arco bass（`shift=−12`、隣接整数デチューンのループ）、sax screech（高次倍音＋ノイズ）、cymbal swell（上昇するノイズ）。
- **パート**: piano、bass、sax、perc。
- **和声**: root 付近の隣接半音（`(0,1,2,−1,−2,6,7)` から2〜4個）を密集させた手組みのクラスター和音を区間ごとに4つ（`plan()` で乱数）。`chord.bass` は arco bass 専用（`BASS_REG`）、`chord.chord_tones` は piano・sax 共有の `CLUSTER_REG`。
- **文法**: 各楽器が step ごとに intensity に応じた確率で鳴るかを決める。sax は climax だけ。
- **テンポ**: 部品 `tempo_curve` で4区間を通して BPM をうねらせる（96→82 ease_out、82→126 ease_in、126→150→126、126→70 linear。区間間で BPM が連続する）。先頭のパート（piano）がテンポカーブも書く。`--tempo` は開始 BPM を決め、カーブ全体を `開始 BPM / 96` 倍する。

### 6.12 `minimalism` — ミニマル／フェーズ音楽

- **音色**: piano pulse、marimba、vibraphone、woodblock（`pitched=False`）。
- **周期**: piano 16 step、marimba 12、vibes 8、wood 6。最小公倍数 48 step を1小節（`Meter(48, 4)`、各区間1小節）。
- **構成**: phase0 … phase15（16区間）。piano の音型だけを区間ごとに1 step ずつずらし、「ズレて→揃って戻る」。
- **文法**: 各パートは固定の「周期内 step → (音, 音量)」表を `polymetric_row(step − shift, cycle)` で引く。乱数は使わない（決定論的な反復が本質）。woodblock のアクセントは step 1（row 0 の空きの名残だが、周期の一部として残している）。`harmony=None`（和声は動かさない）。

### 6.13 `orchestral` — フルオーケストラ／劇伴（8ch）

- **パートと音色**:

  | パート | 役割 | 楽器（`Instrument`） | pan |
  |:---|:---|:---|:---|
  | vln1 | 第1ヴァイオリン（旋律） | vln1 | 30 |
  | vln2 | 第2ヴァイオリン | vln1 と同じ Patch、`tune_cents=+37.5`・`volume=44`（合奏感の軽いデチューン） | 80 |
  | vla | ヴィオラ | orch_viola（`shift=−7`） | 150 |
  | vc | チェロ | orch_cello（`shift=−12`） | 190 |
  | cb | コントラバス | orch_bass_str（`shift=−24`） | 210 |
  | ww | 木管 | nostalgic_flute | 100 |
  | brass | 金管 | kit: horn（march の section）・trumpet。trumpet>horn | 160 |
  | perc | 打楽器 | kit: timpani（`shift=−24`）・cymbal（free-jazz の swell を流用）。cymbal>timpani | 128 |

- **和声**: C の I–IV–V–vi を6声（CB・VC・VLA・VLN2・VLN1・BRASS）でボイシング。`voice()` で bass・tenor・旋律候補を求め、残り3声は `chord_tones` のピッチクラスから小節ごとに導出する。6音域はモジュール定数。
- **構成**: intro（弦のみ）→ theme（＋木管）→ development（＋ホルン）→ climax（全8パート・トランペット・ティンパニ・シンバル）→ resolution（弦のみ）。intensity 0.3→0.5→0.7→1.0→0.4 で音量を区間単位にスケール。通作（ループしない）。
- **予算**: `mod_channels={8: 1}`（MOD は 8CHN 専用。4・6 は `ChannelCountError`）。S3M・XM・IT では8パートが最低限の lane で、予算が小さければ `ChannelCountError`。
- **V15 の扱い**: climax の全合奏は V15 の目安（片側合計 ≤120）を超えるが、実プレイヤーでは音割れしない。V15 は 4ch の MOD だけを検査するので orchestral は対象外で、音割れは実測の検査で確かめる（§9.1・§9.2）。

### 6.14 共通の部品の上に宣言で書く35ジャンルの仕組み

§6.15・§6.16 の35ジャンルは、どれも `Genre` の宣言（§5.1）と、`framework/gens/` の部品（§5.8）の組合せで書く。その上に、ジャンル固有のジェネレータ（`Travis`・`BreaksBass`・`RockRiff` など）を同じファイルに足す。

**方針**

- 35ジャンルの多くは「ドラム・ベース・和音・旋律・パッド」という同じ骨格を持つ。部品が骨格を**宣言から**作曲し、ジャンルは宣言と、固有の文法だけを書く。
- 音色は楽器名で命名した共有ライブラリ（§4.5）を複数のジャンルで使い回す。
- **チャンネル数は MOD ではジャンルごとに 4／6／8 から選び、多くのジャンルは曲ごとにも選ぶ**（下の「編成」）。4ch は既定の MOD で Amiga 互換の `M.K.`、6ch・8ch は `6CHN`・`8CHN`。S3M・XM・IT ではパートがすべて入る（§7.6）。
- 表示名・説明・id に実在の人名を入れない（原文の「〜系」は音楽的特徴に置き換えた）。旋律はすべて手続き的に作り、既存の曲の旋律は使わない。
- **区分**（`Genre.category`）: `mood`（気分）・`genre`（ジャンル）・`style`（「〜風」）。`--list-genres` と `--help` は区分ごとにまとめる（§8.1）。個別実装の12ジャンルは genre＝swing-jazz・prog-rock・trap・future-bass・maqam・free-jazz・minimalism・orchestral・march、style＝nostalgic・suspense-slow・suspense-chase。
- 気分ジャンルの原文にある「相性」（晴れ・夜・雨など）は §6.16 に記録するだけで、属性にはしていない（天気・時間帯から選ぶ機能を作るときに足す）。

**パートの構成の型**（各ジャンルの実際のパートは §6.16 の「音色」と「編成」）

| 型 | 構成 | 使うジャンル |
|:---|:---|:---|
| **B4**（4ch バンド） | drums（1チャンネルで優先度により共有）／bass／和音／旋律 | warm、folk、hiphop、acoustic-ssw、focus、bossa-nova、jazz（ride/brush・bass・piano・trumpet） |
| **B6**（6ch バンド） | kick/snare／hat・perc・cymbal／bass／和音／旋律／パッド・対旋律・タム等 | rock、pop、energetic、city-pop、jpop-80s、jrock-90s、indie-rock、rnb-soul、neo-soul、anime-ost、jrpg、lofi-hiphop、lofi-chill |
| **E6**（6ch 電子音楽） | kick／clap・snare・hat／bass／和音／リード・アルペジオ／パッド・FX・エコー | uplifting、edm、house、synthwave、cool、dreamy、dark-tense |
| **A4**（4ch アンビエント） | パッド・持続音・ベル・エコー・低音の組合せ | calm、ambient、ambient-drone、melancholic |
| **Q4**（弦楽四重奏） | vln1／vln2＋vla（`inner` パート）／vc | classical |
| **T4**（4ch テクノ） | kick／hat・clap／bass／シーケンス | techno |
| **O8**（8ch 管弦楽） | §6.16 の各項 | cinematic、trailer |

**宣言の対応**（旧い `BandProfile` のクラス属性との対応。コードには残っていないが、§6.16 の記述の読み替えに使う）

| 旧い宣言 | 現在 |
|:---|:---|
| `KIT` | `instruments`（`inst(preset_key, gm, **changes)`） |
| `CHORD_KITS = {接頭辞: (Patch, strum_ms)}` | `instruments[接頭辞]` と、和音を鳴らすジェネレータの `strum_ms`。和音サンプルは Realizer が使われた和音から作る（§4.9） |
| `CHANNELS`・`DRUM_CHANNEL`・`ARRANGEMENTS`・`Fold` | `parts` の並び（最も厚い編成の並び）・`min_channels`・`Kit`。打楽器は1つのパートにまとめ、`Kit.groups` で lane のまとまりを宣言する |
| `CHANNEL_WEIGHTS` | `mod_channels`（編成を選ばないジャンルは `{N: 1}`） |
| `Section(kind, prog, intensity, parts, groove, key_offset, fill, crash, lead_motifs)` | `Section(prog, intensity, parts, groove, key_offset, fill, crash, motifs, tags, …)`。パート名でない印（`"kime"`・`"spic"` など）は `tags` |
| `MEASURES_PER_PATTERN`・`rows_per_measure`・`variable_meter` | `Section.measures`・`Section.meter`・`Section.measure_steps` |
| `SWING = SwingConfig(l, s)` | `Genre.swing = Swing(l, s)` |
| `ECHO`・`LAYERS` | `Part("…", Echo(…), follow="…")`・`Part("…", Layer(…), follow="…")` |
| `SIDECHAIN` | `mix = (Sidechain(triggers, targets, ratio, release_steps), …)` |
| `LATE`・`HUMANIZE` | `Groove(..., late=, humanize=)` |
| `extra_measure`・`buf.replace` | ジャンル内のジェネレータ（独立したパート）と `finalize_section`（`mute` → `add`） |
| `begin_pattern` の状態 | `ctx.state`（区間）・`ctx.song_state`（曲全体） |

**作曲の流れ**（§5.4・§5.7）

1. `plan()`: BPM → 主音 → 進行（無作為に選ぶか宣言順）→ 区間名ごとに `SectionPlan`（進行の和音を小節に均等に割り当てる）→ `form` から order。要約行に調と進行を出す。
2. 区間ごと・パートごと（宣言順）に、ジェネレータが音符を書く。区間の `parts` に無いパートは鳴らさない。音量は区間の `intensity` で下げる（ドラムは `0.6 + 0.4×intensity` 倍、他のパートは `0.55 + 0.45×intensity` 倍）。
3. 旋律は4小節の楽節: A・A（反復）・B・終止（4小節目は後半を休み、音を切る）。`Lead(vibrato=…)` があれば 6 step 以上の音に `Vibrato`。区間ごとに旋律の楽器を持ち替えるジャンルは `Lead(inst_for=…)`（anime-ost・jrpg）。
4. `finalize_section`: パートをまたぐ編集（anime-ost の決め、jazz の coda のフェルマータ、trailer の final の余韻）。
5. Realizer が予算に収め、チャンネル・pattern・row コマンドにする（§7.6）。スウィング・サイドチェインも Realizer が書く。

**パートの型**（16 step＝4/4 を基準に書き、小節の step 数に比例させる。§5.8）

- ベース（`BassLine`）: `whole`・`half`・`root8`・`octave8`・`offbeat`（裏拍の8分）・`rootfifth`・`bossa`・`walking`（根音・第3音・5度・半音の経過音）・`synco16`・`boombap`・`pulse16`（根音・短2度・5度の16分）・`house`。
- 和音の刻み（`Comp`）: `whole`・`half`・`pulse4`・`pulse8`・`offbeat`・`charleston`・`strum`・`bossa`・`stab2`・`arp8`・`arp16`・`fingerpick`・`cutting16`（強拍以外は確率 0.55）。`chordal=False` なら単音で和音を分散させ、`wobble` があれば和音の直後に `Vibrato`（テープの揺れ風）。
- アルペジオ（`Arp`）: 指定 step で和音の構成音を `up`／`updown`。

**補助**

- `chord_patch`（§4.9）: 和音を1サンプルに焼き込む。`strum_ms` でギターのストローク。オルガン・ブラス・シンセブラスのループは焼けない。
- `Echo`: 発音を `delay` step 遅らせ音量を `ratio` 倍にして別のパートに写す（MOD に残響エフェクトが無いため。ループ音色の旋律は `dur` も写す）。
- `Buildup`: EDM 系のビルドアップ。4小節でスネアが4分→8分→16分→`Retrig(3)` と加速し音量が上がる。最後から2つ目の小節の頭に上昇音。
- `gm_default(patch)`・`preset(key, **changes)`: プリセットを名前で引き、`dataclasses.replace` で差分を当てる。`Instrument.gm` の既定は Patch 名から引く。

**書くときの注意**

- 音程のある楽器（タム・ティンパニ）を音高なしで置くと `ctx.note()` が `PlanError` にする。ドラムの型（`GROOVES`）に書くときは `hits(..., notes=...)` で打点ごとの音高（`Hit.note`）を与える。和音に合わせて音高を変えるもの（trailer のタム、ティンパニ）はジャンル内のジェネレータで書く。
- 同じパート・同じ楽器・同じ step に `prio` が同じ2つの発音を書くと `PlanError`。「決め」のように他のパートを意図して上書きするときは `finalize_section` で `mute` してから `add` する（anime-ost）。
- 区間は音を持ち越さないので、旧実装にあった「区間頭の停止」「pattern 末の消音」は書かない。

**編成（曲ごとのチャンネル数）**

全形式でチャンネル数はファイル単位なので1曲の中では変えず、**曲ごとに編成を選ぶ**。編成を選ぶことは「その曲で使う任意パート（パッド・対旋律・エコー・打楽器の2系統化）を選ぶ」ことで、チャンネル数はそこから決まる。

- MOD の予算は `mod_channels`（予算 → 重み）から seed で選ぶか `--channels` で指定する。対象は27ジャンル（6ch だった20は 4／6／8、4ch だった5は 4／6、8ch だった2は 6／8）。チャンネル数がジャンルの定義になっているもの（classical・jazz・techno）、変化しないことが目的のもの（focus・ambient-drone）、層を足しても聞き分けにくいもの（calm・ambient・melancholic）と個別実装の12ジャンルは固定。奇数（5ch・7ch）は使わない（MOD の互換性）。既定の重みは3択で 4:1・6:2・8:1。
- **パートで作曲し、予算に収める**: ジャンルは最も厚い編成の全パートを `parts` に宣言し、作曲は常に全パートで行う（外れたパートも乱数を消費する。§5.5）。予算が小さければ Realizer が `min_channels` と ladder（§7.6）で、打楽器を畳み・和音を焼き・任意パートを外して収める。**同じ seed ならどの編成でも同じ音符**になり、編成は厚みとチャンネル数だけを変える。
- **任意パート**は乱数を使わずに書く（他のパートの乱数列を変えないため。パートごとの乱数で既に独立だが、`Layer` は偶然に頼らず決定的）: `Layer`（`follow` のパートが鳴る区間で、和音の変わり目に和音サンプルか第3音の長音を置く対旋律・パッドの層）、`Echo`（旋律のエコー）、既存の `Arp` 等。
- 4ch の打楽器の畳み方の優先度は「snare・clap＞kick・tom＞crash＞hat 類」を基本に、4つ打ちの電子音楽は kick を優先する（`Kit.priority`・`Kit.single_priority`）。
- 各ジャンルの編成は §6.16 の「編成」。ladder の結果（チャンネルの数・楽器・パン・畳んだときの優先度）は `tests/framework/port_layouts.py` が固定している。

**共通の文法**

- **歌もの**（pop・rock・city-pop・jpop-80s・jrock-90s・indie-rock・rnb-soul・neo-soul・acoustic-ssw・energetic）: 1区間＝4小節。form は `intro, verse, pre, chorus, …, outro` を基本にジャンルごとに省略・追加する。旋律は動機を反復し、4小節目の後半を休ませて歌の息継ぎにする。多くは区間頭の crash と区間末のフィルを持つ。
- **電子音楽**（uplifting・edm・house・techno・synthwave・cool）: 1区間＝4小節で、区間ごとにレイヤーを出し入れする。uplifting・edm・house は kick をトリガにサイドチェインを掛ける（`mix`）。
- **アンビエント系**（calm・ambient・ambient-drone・dreamy）: 和音は2〜4小節ごとにしか変えない。音量（intensity、ambient-drone は持続音への `Automation(volume)`）で起伏を作る。
- **スウィング**: `Swing(long, short)` の和は `2 × 24 / steps_per_beat`（1拍＝24 tick）。16分スウィング（focus・lofi-hiphop・lofi-chill・hiphop・rnb-soul・neo-soul）は1拍＝4 step のまま偶奇で Speed を交互にし、和は 12（`Swing(7, 5)`＝1.4:1、neo-soul は `(8, 4)`＝2:1）。8分スウィング（jazz）は swing-jazz と同じ1拍＝2 step・和 24（`(14, 10)`）。
- **拍のよれ**（neo-soul）: `Groove(late=…)` でスネアとハットの一部に `Delay`（1〜2 tick）を確率で付け、グリッドから少し遅らせる。
- **転調**: `Section.key_offset`（march のトリオと同じ）。最後のサビを上げる（pop +1、jpop-80s +2、jrock-90s +1）、jazz の B（+1）、classical の属調（+7）・下属調（+5）、trailer の第3幕（+1）。
- **3/4 拍子**（classical）: 1小節＝12 step（`Meter(12, 4, (3, 4))`）、1区間＝4小節（48 step）。2/4（bossa-nova）は 8 step で8小節。

### 6.15 第３段階のジャンルの宣言値

コードの宣言から取得。区分は §6.14、パートの構成の型は §6.14 の表。ch が複数あるジャンルは MOD で曲ごとに編成を選ぶ（§6.14「編成」、各ジャンルの編成は §6.16。ch は `mod_channels` のキー）。

| id | 区分 | 表示名 | BPM | 拍子（1小節の step） | ch（MOD で選べる数） | 調・旋法 | 構成（order） |
|:---|:---|:---|:---|:---|:---|:---|:---|
| `uplifting` | mood | Uplifting | 128–136 | 4/4（16） | 4/6/8 | D/E/F ionian | intro, build, drop, drop, break, build, drop, drop, outro |
| `calm` | mood | Calm / Relaxed | 68–78 | 4/4（16） | 4 | C/F/G lydian | intro, a, b, a, outro |
| `melancholic` | mood | Melancholic | 66–76 | 4/4（16） | 4 | A/D/E aeolian | intro, a, b, a, b, outro |
| `energetic` | mood | Energetic | 160–176 | 4/4（16） | 4/6/8 | E/A/D ionian | intro, verse, pre, chorus, verse, pre, chorus, bridge, chorus, chorus, outro |
| `dreamy` | mood | Dreamy | 80–92 | 4/4（16） | 4/6/8 | Eb/Ab/Db lydian | intro, a, b, a, b, outro |
| `dark-tense` | mood | Dark / Tense | 90–100 | 4/4（16） | 4/6/8 | C/D harmonic_minor | intro, build, pulse, build, climax, collapse |
| `warm` | mood | Warm | 88–100 | 4/4（16） | 4/6 | G/D/C ionian | intro, a, b, a, b, outro |
| `cool` | mood | Cool | 100–112 | 4/4（16） | 4/6/8 | F#/B/Db dorian | intro, a, b, break, a, b, outro |
| `focus` | mood | Focus | 78–86 | 4/4（16）、スウィング 7:5 | 4 | D/E dorian | intro, loop, loop, loop2, loop2, loop, loop_b, loop_b, loop2, loop2, loop, loop, outro |
| `rock` | genre | Rock | 112–132 | 4/4（16） | 4/6/8 | E/A/D mixolydian | intro, verse, chorus, verse, chorus, solo, chorus, outro |
| `pop` | genre | Pop | 100–120 | 4/4（16） | 4/6/8 | C/D/F/G ionian | intro, verse, pre, chorus, verse, pre, chorus, bridge, chorus, chorus_up, outro |
| `jazz` | genre | Modal Jazz | 120–144 | 4/4（8、1 row＝8分）、スウィング 14:10 | 4 | D dorian | head_a, head_a, head_b, head_a, solo_a, solo_a, solo_b, solo_a, head_a, head_a, head_b, coda |
| `bossa-nova` | genre | Bossa Nova | 120–140 | 2/4（8） | 4/6 | F/C/G/D ionian | intro, a, a, b, a, solo, a, outro |
| `city-pop` | genre | City Pop | 104–120 | 4/4（16） | 4/6/8 | E/A/Db ionian | intro, verse, pre, chorus, interlude, verse, pre, chorus, chorus, outro |
| `ambient` | genre | Ambient | 60–72 | 4/4（16） | 4 | D/E lydian | layer1, layer2, bloom, layer2, drift, fade |
| `lofi-hiphop` | genre | Lo-fi Hip Hop | 72–88 | 4/4（16）、スウィング 7:5 | 4/6/8 | D/F/A/C ionian | intro, a, a, b, a, outro |
| `edm` | genre | EDM | 124–130 | 4/4（16） | 4/6/8 | F/G aeolian | intro, build, drop, drop, break, build, drop, drop, outro |
| `house` | genre | House / Deep House | 118–124 | 4/4（16） | 4/6/8 | A/D/G dorian | intro, groove, main, main, break, main, main, outro |
| `hiphop` | genre | Hip Hop (Boom Bap) | 86–96 | 4/4（16）、スウィング 7:5 | 4/6 | A/E/D/G aeolian | intro, verse, verse, verse, verse, hook, hook, verse, verse, verse, verse, hook, hook, outro |
| `classical` | genre | Classical (String Quartet) | 100–120 | 3/4（12、可変） | 4 | G/D/F/Bb ionian | ante, cons, ante, cons, dom, ret, ante, cons, trio_a, trio_b, trio_a, trio_b, ante, cons, coda |
| `cinematic` | genre | Cinematic | 70–84 | 4/4（16） | 6/8 | C/D aeolian | intro, rise1, theme, theme, rise2, climax, climax, resolve |
| `folk` | genre | Folk | 96–116 | 4/4（16） | 4/6 | G/D/C/A ionian | intro, verse, chorus, verse, instrumental, chorus, outro |
| `rnb-soul` | genre | R&B / Soul | 68–84 | 4/4（16）、スウィング 7:5 | 4/6/8 | Eb/Ab/Db ionian | intro, verse, pre, chorus, verse, pre, chorus, bridge, chorus, outro |
| `synthwave` | genre | Synthwave / Retrowave | 96–112 | 4/4（16） | 4/6/8 | A/E/F# aeolian | intro, verse, chorus, verse, chorus, solo, chorus, outro |
| `techno` | genre | Minimal Techno | 124–132 | 4/4（16） | 4 | A/D aeolian | k1, k2, h1, f1, f2, h1, b1, f3, f2, f3, o1, k1 |
| `jpop-80s` | style | 80s J-Pop | 120–136 | 4/4（16） | 4/6/8 | C/D/E ionian | intro, a, b, sabi, interlude, a, b, sabi, sabi_up, outro |
| `jrock-90s` | style | 90s J-Rock | 140–168 | 4/4（16） | 4/6/8 | E/A/D aeolian | intro, a, b, sabi, a, b, sabi, solo, sabi, sabi_up, outro |
| `anime-ost` | style | Anime Soundtrack | 120–150 | 4/4（16） | 4/6/8 | D/G aeolian | intro, a, b, break, a, b, climax, outro |
| `jrpg` | style | JRPG Game Music | 96–120 | 4/4（16） | 4/6/8 | C/D/F ionian | intro, a, a2, b, a, a2, ending |
| `lofi-chill` | style | Lo-fi Chill | 72–88 | 4/4（16）、スウィング 7:5 | 4/6/8 | C/F/G/Bb ionian | intro, a, a, b, a, outro |
| `indie-rock` | style | Indie Rock | 118–138 | 4/4（16） | 4/6/8 | G/D/A ionian | intro, verse, chorus, verse, chorus, bridge, chorus, outro |
| `trailer` | style | Cinematic Trailer | 90–100 | 4/4（16） | 6/8 | D/C aeolian | act1, act1, act2, act2, riser, act3, act3, final |
| `ambient-drone` | style | Ambient Drone | 60–66 | 4/4（16） | 4 | D/E/A dorian | d1, d2, d2, d3, d3, d4, d4, d5, d5, d6, d6, d7, d8 |
| `acoustic-ssw` | style | Acoustic Singer-songwriter | 80–100 | 4/4（16） | 4/6 | G/C/D/E ionian | intro, verse, chorus, verse, chorus, bridge, chorus, outro |
| `neo-soul` | style | Neo Soul | 80–96 | 4/4（16）、スウィング 8:4 | 4/6/8 | Eb/Ab/F dorian | intro, verse, chorus, verse, chorus, bridge, chorus, outro |

### 6.16 第３段階の各ジャンル

各項の「区別」は、似たジャンル（既存を含む）とどこで聞き分けられるか。和音の記法は主調に対する度数。「音色」は `パート（楽器＝Patch 名）`（番号は `parts` の宣言順。物理チャンネルは Realizer が決める）。和音を1サンプルに焼き込む楽器（旧 `CHORD_KITS`）は「〜の和音」と書く（焼く・声部に開くは Realizer が予算で決める。§4.9・§7.6）。「編成」の 4ch／6ch／8ch は MOD の予算ごとの ladder の結果で、`tests/framework/port_layouts.py` が固定している。

#### 6.16.1 `uplifting` — 高揚するシンセ・アンセム（mood、E6）

- 説明: 「上げていく高揚感。4つ打ちとアルペジオ、明るいスーパーソウのコード」／"Uplifting anthem: four-on-the-floor, bright arpeggios and supersaw chords"
- 相性（原文）: 晴れ・昼間
- 音色: 1 kick（Kick909）／2 clap/hat（FbClap・OpenHat909・PopSnare）／3 bass（SawBass）／4 supersaw（FbSupersaw の和音）／5 arp（SynthPluck）／6 lead（SawLead）
- 編成: 4ch＝drums（kick＋clap/hat）・bass・supersaw・arp／6ch＝kick・clap/hat・bass・supersaw・arp・lead／8ch＝kick・clap/hat・bass・supersaw・arp・lead・lead echo・choir（名前は「音色」の論理チャンネル。重み {4: 1, 6: 2, 8: 1}）
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
- 編成: 4ch＝drums（kick/snare＋cymbal＋tom）・bass・gtr・lead／6ch＝kick/snare・cymbal・bass・gtr・lead・tom／8ch＝kick/snare・cymbal・bass・gtr・lead・tom・lead echo・synth brass（名前は「音色」の論理チャンネル。重み {4: 1, 6: 2, 8: 1}）
- 和声: I–V–vi–IV、IV–I–V–vi、I–IV–vi–V（2 つを選んで区間に割り当てる）
- 文法: 倍速感のあるビート（kick 0・6・8・14／snare 4・12／ハット8分）、bridge はハーフタイム。ベースは8分の根音、ギターはパワーコードの8分刻み。区間頭に crash、フィルはタム＋スネア。
- 区別: rock より速く（160–176）明るい長調。jrock-90s は J-POP の曲構成と転調・ギターソロを持つ。

#### 6.16.5 `dreamy` — 夢見心地のアルペジオ（mood、E6）

- 説明: 「夢見心地。深い残響感のアルペジオとパッド」／"Dreamy: echoing arpeggios over lush pads"
- 音色: 1 kick/rim（PopKick・Rimshot）／2 sub（FbSub）／3 pad（GlassPad の和音）／4 arp（ArpBell）／5 arp echo（ArpBell）／6 flute（Flute）
- 編成: 4ch＝kick/rim・sub・pad・arp／6ch＝kick/rim・sub・pad・arp・arp echo・flute／8ch＝kick/rim・sub・pad・arp・arp echo・flute・flute echo・voice（名前は「音色」の論理チャンネル。重み {4: 1, 6: 2, 8: 1}）
- 和声: Imaj7–IVmaj7、Iadd9–iii7–IVmaj7–ivm6（2 つを選んで区間に割り当てる）
- 文法: アルペジオは16分の往復、`echo`（3 row 遅れ・0.5倍・2回）を5ch に書く。ドラムはハーフタイム（kick 0・10、rim 8）。サブベースは全音符、フルートはまばらな長音。
- 区別: ambient は拍が無い。calm はピアノ主体でエコーを使わない。

#### 6.16.6 `dark-tense` — 緊張感のある暗いパルス（mood、E6）

- 説明: 「緊張感。低音のオスティナートと刻むパルス、重い打撃」／"Dark and tense: low ostinato, ticking pulse and heavy hits"
- 音色: 1 taiko（Taiko）／2 tick（Hat909）／3 bass（SawBass）／4 strings（TensionStrings）／5 braam（Braam）／6 fx（Riser・Impact）
- 編成: 4ch＝percussion（taiko＋tick）・bass・strings・braam／6ch＝taiko・tick・bass・strings・braam・fx／8ch＝taiko・tick・bass・strings・braam・fx・choir・braam echo（名前は「音色」の論理チャンネル。重み {4: 1, 6: 2, 8: 1}）
- 和声: i–bII–i–V、i–VI–iv–V（2 つを選んで区間に割り当てる）
- 文法: ベースは16分で根音・短2度・5度を往復（`pulse16`）、ハットは16分で途切れない。taiko は1・3拍目、braam は2小節ごと。build で riser、climax の頭に impact。
- 区別: suspense は無音と恐怖の効果音が主役。dark-tense は一定のパルスが途切れない。trailer は3幕構成で最後に壮大化する。

#### 6.16.7 `warm` — 温かいアコースティック（mood、B4）

- 説明: 「温かい。アコースティックギターとピアノ、長調の穏やかな伴奏」／"Warm: acoustic guitar and piano in a gentle major key"
- 音色: 1 cajon/shaker（CajonLow・CajonSlap・Shaker）／2 bass（FingerBass）／3 guitar（AcousticGtr の和音）／4 piano（Piano）
- 編成: 4ch＝cajon/shaker（cajon＋shaker）・bass・guitar・piano／6ch＝cajon・shaker・bass・guitar・piano・flute（名前は「音色」の論理チャンネル。重み {4: 2, 6: 1}）
- 和声: I–V–vi–IV、I–IV–ii–V、I–vi–IV–V（2 つを選んで区間に割り当てる）
- 文法: カホン（low 0・8・10、slap 2・4拍）とシェイカー。ギターはストローク（`strum`: 0・4・6・10・12・14。弦ごとに 12 ms ずらした和音サンプル）、ベースは根音と5度、ピアノの旋律は順次進行主体。
- 区別: folk はフィドルと舞曲的なリズム。acoustic-ssw は指弾きのアルペジオと歌の旋律。

#### 6.16.8 `cool` — 涼しげな透明感（mood、E6）

- 説明: 「涼しげ。透明感のあるシンセと軽い2ステップのビート」／"Cool: glassy synths over a light two-step beat"
- 音色: 1 kick/snare（PopKick・Rimshot）／2 hat（Hat909・Clave）／3 sub（FbSub）／4 glass pad（GlassPad の和音）／5 pluck（SynthPluck）／6 echo（SynthPluck）
- 編成: 4ch＝drums（kick/snare＋hat）・sub・glass pad・pluck／6ch＝kick/snare・hat・sub・glass pad・pluck・echo／8ch＝kick/snare・hat・sub・glass pad・pluck・echo・voice・bell（名前は「音色」の論理チャンネル。重み {4: 1, 6: 2, 8: 1}）
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
- 編成: 4ch＝drums（kick/snare＋cymbal＋tom）・bass・rhythm gtr・lead gtr／6ch＝kick/snare・cymbal・bass・rhythm gtr・lead gtr・tom／8ch＝kick/snare・cymbal・bass・rhythm gtr・lead gtr・tom・lead echo・organ（名前は「音色」の論理チャンネル。重み {4: 1, 6: 2, 8: 1}）
- 和声: I–bVII–IV–I、I–IV–V–IV、i–bVI–bVII–i（2 つを選んで区間に割り当てる）
- 文法: `BACKBEAT`（kick 0・8・10／snare 4・12／ハット8分）、サビはライドに替える。フィルはハイタム→ロータム→スネア。リフは根音の8分刻みから2小節ごとに5度・短7度へ動く（ミクソリディアン）。ソロ区間はリードギターが跳躍多めの旋律を `4xy` 付きで弾く。区間頭に crash、フィルはタム＋スネア。
- 区別: prog-rock は変拍子。energetic は速い長調のパンク寄り。indie-rock は軽い歪みとアルペジオ。

#### 6.16.11 `pop` — 明るいポップ（genre、B6）

- 説明: 「ポップ。長調の明るいメロディとピアノ、覚えやすいサビ」／"Pop: bright major-key melodies, piano and a catchy chorus"
- 音色: 1 kick/snare（PopKick・PopSnare）／2 hat（ClosedHH・Shaker・CrashCymbal）／3 bass（FingerBass）／4 piano（Piano の和音）／5 lead（VoxOoh）／6 pad（WarmPad の和音）
- 編成: 4ch＝drums（kick/snare＋hat）・bass・piano・lead／6ch＝kick/snare・hat・bass・piano・lead・pad／8ch＝kick/snare・hat・bass・piano・lead・pad・lead echo・strings（名前は「音色」の論理チャンネル。重み {4: 1, 6: 2, 8: 1}）
- 和声: I–V–vi–IV、vi–IV–I–V、I–vi–IV–V、IVmaj7–V–iii7–vi（3 つを選んで区間に割り当てる）
- 文法: §6.14 の歌もの。ピアノの和音を8分で刻み、verse はシェイカー主体の軽いビート。旋律は VoxOoh。最後から2つ目のサビ（chorus_up）で半音上げる。
- 区別: jpop-80s は80年代の音色（ゲートスネア・シンセブラス）と王道進行。city-pop はテンションコードとカッティング。

#### 6.16.12 `jazz` — モーダル・ジャズ（genre、B4 読み替え）

- 説明: 「ジャズ。ドリアンのモーダルなヴァンプ、4度堆積のピアノとミュート・トランペット」／"Modal jazz: dorian vamps, quartal piano voicings and muted trumpet"
- 音色: 1 ride/brush（SwingRide・SwingBrushSnare）／2 bass（SwingWalkBass）／3 piano（Piano の和音）／4 trumpet（MuteTrumpet）
- 和声: i11–i11–i11–ii11（1つを選び曲全体で使う）
- 文法: 8分格子（1 measure＝8 row、1拍＝2 row）と `Swing(14, 10)`。和音は4度堆積（`quartal`: 根音から完全4度を4つ重ねた m11 の響き）の i11 に2小節ごとの ii11 を挟むヴァンプ。1 pattern＝8小節で AABA（B は半音上のドリアン、`key_offset=1`）。ベースは4分のウォーキング、ピアノはチャールストン、ミュート・トランペットは head で長音主体、solo で細かい動機。coda の7小節目で全員が長い和音を伸ばして終わる。
- 区別: **swing-jazz（既存）はビバップのリズムチェンジで速い**。jazz は和音がほとんど動かないモーダル（別ジャンルとして作ると決定。DESIGN_HISTORY.md §12.5）。

#### 6.16.13 `bossa-nova` — ボサノバ（genre、B4）

- 説明: 「ボサノバ。2/4 の柔らかいガットギターと軽いパーカッション」／"Bossa nova: soft nylon guitar and light percussion in 2/4"
- 音色: 1 rim/perc（Rimshot・Shaker・Surdo）／2 bass（FingerBass）／3 guitar（NylonGtr の和音）／4 flute（Flute）
- 編成: 4ch＝rim/perc（rim/surdo＋shaker）・bass・guitar・flute／6ch＝rim/surdo・shaker・bass・guitar・flute・e.piano（名前は「音色」の論理チャンネル。重み {4: 2, 6: 1}）
- 和声: Imaj7–II7–iim7–V7、iim7–V7–Imaj7–VI7、im7–IV7、iim7b5–V7–im7–im7（2 つを選んで区間に割り当てる）
- 文法: 2/4（1 measure＝8 row）。リズムは2小節周期: リムのクラーベ（偶数小節 0・3・6、奇数小節 2・5）、ギターの和音（0・3・6／2・4・6）。ベースは付点4分＋8分（row 0 に根音、row 6 に5度）、スルドは2拍目。旋法は和音の種類ごと（m7→ドリアン、dom7→ミクソリディアン、m7b5→ロクリアン）。
- 区別: jazz・swing-jazz はスウィングする。bossa-nova はストレートな16分と2小節周期のクラーベ。

#### 6.16.14 `city-pop` — 80年代シティポップ（genre、B6）

- 説明: 「シティポップ。テンションコードのエレピ、跳ねるベースとギターのカッティング」／"City pop: jazzy electric piano, bouncy bass and funky guitar cutting"
- 音色: 1 kick/snare（PopKick・PopSnare）／2 hat（ClosedHH・Tambourine・CrashCymbal）／3 bass（SlapBass）／4 e.piano（ElectricPiano の和音）／5 lead（SynthBrass）／6 cutting gtr（CuttingGtr の和音）
- 編成: 4ch＝drums（kick/snare＋hat）・bass・e.piano・lead／6ch＝kick/snare・hat・bass・e.piano・lead・cutting gtr／8ch＝kick/snare・hat・bass・e.piano・lead・cutting gtr・lead echo・strings（名前は「音色」の論理チャンネル。重み {4: 1, 6: 2, 8: 1}）
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
- 編成: 4ch＝drums（kick/snare＋hat）・bass・e.piano・lead／6ch＝kick/snare・hat・bass・e.piano・lead・vinyl／8ch＝kick/snare・hat・bass・e.piano・lead・vinyl・lead echo・pad（名前は「音色」の論理チャンネル。重み {4: 1, 6: 2, 8: 1}）
- 和声: ii9–V13–Imaj9–vi7、Imaj7–iii7–vi7–IVmaj7、IVmaj9–iii7–ii9–Imaj9（2 つを選んで区間に割り当てる）
- 文法: `BOOMBAP`＋16分スウィング 7:5。エレピはチャールストンの和音＋`4xy` の揺れ、ベースはブーンバップの型、サックスの旋律は短い動機、レコードのノイズを2小節ごとに鳴らし直す。
- 区別: nostalgic（既存）はストレートな16分とオルゴール。lofi-chill はギター・フルートとサイドチェインのうねり。focus は旋律なし。

#### 6.16.17 `edm` — ビルドアップとドロップ（genre、E6）

- 説明: 「EDM。シンセ主体、ビルドアップで溜めてドロップで弾ける」／"EDM: synth-driven builds that explode into the drop"
- 音色: 1 kick（Kick909）／2 clap/hat（FbClap・Hat909・PopSnare）／3 bass（SawBass）／4 chords（PolyPad の和音）／5 lead（FbSupersaw）／6 fx（Riser・Impact）
- 編成: 4ch＝drums（kick＋clap/hat）・bass・chords・lead／6ch＝kick・clap/hat・bass・chords・lead・fx／8ch＝kick・clap/hat・bass・chords・lead・fx・lead echo・pluck arp（名前は「音色」の論理チャンネル。重み {4: 1, 6: 2, 8: 1}）
- 和声: VI–iv–i–VII、i–VI–III–VII（2 つを選んで区間に割り当てる）
- 文法: 4つ打ち＋clap＋裏拍のハット。build は `buildup`（スネアが4分→8分→16分→`E9x`、音量上昇、riser）、ドロップの頭に impact、ドロップはスーパーソウのリードが2小節のフックを反復。ベースは裏拍の8分、ベースと和音に kick のサイドチェイン。
- 区別: uplifting はアルペジオ主体で長調の高揚。house はビルドアップが無く一定のグルーヴ。

#### 6.16.18 `house` — ハウス／ディープハウス（genre、E6）

- 説明: 「ハウス。4つ打ちの安定したグルーヴと裏拍のオルガン・スタブ」／"House: steady four-on-the-floor groove with offbeat organ stabs"
- 音色: 1 kick（Kick909）／2 clap/hat（FbClap・OpenHat909・Rimshot）／3 bass（DeepBass）／4 stab（HouseStab の和音）／5 pad（WarmPad の和音）／6 shaker（Shaker）
- 編成: 4ch＝drums（kick＋clap/hat＋shaker）・bass・stab・pad／6ch＝kick・clap/hat・bass・stab・pad・shaker／8ch＝kick・clap/hat・bass・stab・pad・shaker・stab echo・vocal chop（名前は「音色」の論理チャンネル。重み {4: 1, 6: 2, 8: 1}）
- 和声: im7–IV9、im9–bVIImaj7、im7–iv7–bVIImaj7–bIIImaj7（2 つを選んで区間に割り当てる）
- 文法: `DEEP_HOUSE`（kick 4つ打ち、clap 2・4拍、裏拍の open hat、シェイカー、リム）。スタブは裏拍、ベースは16分のシンコペーション（`house`）。パッドに kick のサイドチェイン。intro・outro はドラムだけ。
- 区別: edm はビルドアップとドロップの起伏。techno は和音をほとんど持たない。

#### 6.16.19 `hiphop` — ブーンバップ・ヒップホップ（genre、B4）

- 説明: 「ヒップホップ。ラップが乗る余白を残したブーンバップのビートとサンプル風ループ」／"Hip hop: boom-bap beats and sample-style loops that leave room for rap"
- 音色: 1 drums（BoomBapKick・BoomBapSnare・ClosedHH）／2 bass（FingerBass）／3 loop（Piano の和音）／4 horn（BrassHorn）
- 編成: 4ch＝drums（kick/snare＋hat）・bass・loop・horn／6ch＝kick/snare・hat・bass・loop・horn・strings（名前は「音色」の論理チャンネル。重み {4: 2, 6: 1}）
- 和声: i–VI–i–VI、i–iv–i–iv、im7–im7–bVImaj7–bVImaj7（1つを選び曲全体で使う）
- 文法: ブーンバップ＋16分スウィング 7:5。和音ループ（ピアノのチャールストン）を曲全体で固定。verse は中音域の旋律を置かずループとドラムだけ（ラップの余白）、hook でホーンの短い決めの動機が入る（hook は同じ pattern を再利用するので毎回同じ）。
- 区別: trap（既存）は 808 のグライドと32分のハイハット。hiphop はブーンバップのループとラップの余白（原文の「HipHop / Trap」の trap 部分は既存の trap が受け持つ）。

#### 6.16.20 `classical` — 古典派の弦楽四重奏（genre、Q4）

- 説明: 「クラシック。古典派のメヌエット風の弦楽四重奏、明確な和声と終止」／"Classical: a Classical-era minuet for string quartet with clear cadences"
- 音色: 1 violin 1（OrchViolin）／2 violin 2（OrchViolin2）／3 viola（OrchViola）／4 cello（OrchCello）
- 和声: I–IV–ii6–V、I–IV–V7–I、I–V/V–V7–I、I–vi–V/V–V、I–V7–V7–I、IV–I–V7–I、IV–V7–I–I（宣言順にすべて使う）
- 文法: 3/4（`Meter(12, 4, (3, 4))`＝1小節12 step）で 1区間＝4小節（48 step。pattern は `D00` で切る）。区間ごとに和声の役割が決まっているので進行は宣言順に固定（`Harmony(fixed=True)`）: 前楽節（I–IV–ii6–V の半終止）、後楽節（I–IV–V7–I の完全終止）、属調の中間部（`key_offset=7`、V/V を含む）、復帰（V で止める）、下属調のトリオ（`key_offset=5`）、コーダ。vln1 が楽節の旋律、vln2・vla は2・3拍目に和音を刻み（直前の音に最も近い構成音で声部を滑らかにつなぐ）、vc は1拍目の低音（トリオは3拍目に5度も）。vln2・vla は1つの `inner` パート（kit の2 lane）。
- 区別: orchestral（既存）は8ch の劇伴。classical は4ch の室内楽で、古典的な楽節構造と終止を持つ。

#### 6.16.21 `cinematic` — 映画音楽の情感（genre、O8）

- 説明: 「映画音楽。ピアノのオスティナートから弦とホルンが重なり、ドラマチックに高まる」／"Cinematic: piano ostinato building to soaring strings and horns"
- 音色: 1 piano（Piano）／2 violin（OrchViolin）／3 viola（OrchViola の和音）／4 cello（OrchCello）／5 contrabass（OrchBassStr）／6 horn（BrassSection）／7 choir（Choir の和音）／8 timpani（OrchTimpani・FreeCymbalSwell）
- 編成: 6ch＝piano・violin・cello・horn・choir・timpani／8ch＝piano・violin・viola・cello・contrabass・horn・choir・timpani（名前は「音色」の論理チャンネル。重み {6: 1, 8: 2}）
- 和声: i–VI–III–VII、VI–VII–i–i、III–VII–i–VI（宣言順にすべて使う）
- 文法: ピアノの8分の分散和音（往復）が全体を通し、区間ごとに層を足す: rise1＝チェロ・ヴィオラの和音、theme＝ヴァイオリンの旋律・コントラバス、rise2＝ホルン（和音の第3音）・合唱・ティンパニ（最後の小節はロール、2小節目にシンバルのスウェル）、climax＝全8ch（ティンパニは1・3拍目）。クライマックスは平行長調の響きを III–VII–i–VI（＝長調の I–V–vi–IV）で作る（`key_offset` を使わないので旋律の音階がそのまま合う）。進行は宣言順に固定。
- 区別: orchestral は古典的な機能和声で木管を含む。trailer は打楽器と金管の衝撃で、3幕の構成。

#### 6.16.22 `folk` — フォーク（genre、B4）

- 説明: 「フォーク。アコースティックギターのストロークとフィドル、素朴な進行」／"Folk: strummed acoustic guitar and fiddle over simple progressions"
- 音色: 1 stomp/clap（Stomp・FbClap・Tambourine）／2 upright bass（SwingWalkBass）／3 guitar（AcousticGtr の和音）／4 fiddle（Fiddle）
- 編成: 4ch＝stomp/clap（stomp/clap＋tambourine）・upright bass・guitar・fiddle／6ch＝stomp/clap・tambourine・upright bass・guitar・fiddle・whistle（名前は「音色」の論理チャンネル。重み {4: 2, 6: 1}）
- 和声: I–IV–I–V、I–V–vi–IV、I–bVII–IV–I（2 つを選んで区間に割り当てる）
- 文法: 足踏み（1・3拍）と手拍子（2・4拍）＋タンバリン。アップライト・ベースは根音と5度、ギターは8分のストローク（弦ごとに 14 ms ずらした和音サンプル）。フィドルは8分の順次進行で、直前が空いている音に確率 0.3 で1つ上の音階音の前打音（16分）を付ける。instrumental はフィドルの細かい動機。
- 区別: warm はピアノの旋律と穏やかな伴奏。acoustic-ssw は指弾き。

#### 6.16.23 `rnb-soul` — R&B／ソウル（genre、B6）

- 説明: 「R&B／ソウル。滑らかなテンションコードと歌うような旋律のスロー・ジャム」／"R&B / soul: smooth extended chords and a singing melody in a slow jam"
- 音色: 1 kick/snare（PopKick・PopSnare）／2 hat（ClosedHH・Rimshot）／3 bass（FingerBass）／4 e.piano（ElectricPiano の和音）／5 vocal（VoxOoh）／6 strings（WarmPad の和音）
- 編成: 4ch＝drums（kick/snare＋hat）・bass・e.piano・vocal／6ch＝kick/snare・hat・bass・e.piano・vocal・strings／8ch＝kick/snare・hat・bass・e.piano・vocal・strings・vocal echo・flute（名前は「音色」の論理チャンネル。重み {4: 1, 6: 2, 8: 1}）
- 和声: IVmaj7–iii7–ii7–Imaj7、ii9–V13–Imaj9–Imaj9、vi9–ii9–V7sus4–Imaj9（3 つを選んで区間に割り当てる）
- 文法: 軽い16分スウィング 7:5。エレピは2分音符の和音＋`4xy` の揺れ、弦のパッド、ベースはブーンバップの型、旋律（VoxOoh）は長音主体で `4xy`。
- 区別: neo-soul は拍のよれと EP 中心・より複雑なテンション。city-pop は速くカッティングがある。

#### 6.16.24 `synthwave` — シンセウェイブ（genre、E6）

- 説明: 「シンセウェイブ。80年代のシンセとゲートスネア、8分で脈打つベース」／"Synthwave: 80s synths, gated snare and a pulsing eighth-note bass"
- 音色: 1 kick/snare（PopKick・GatedSnare）／2 hat（ClosedHH）／3 bass（SawBass）／4 poly pad（PolyPad の和音）／5 lead（SawLead）／6 arp（ArpBell）
- 編成: 4ch＝drums（kick/snare＋hat）・bass・poly pad・lead／6ch＝kick/snare・hat・bass・poly pad・lead・arp／8ch＝kick/snare・hat・bass・poly pad・lead・arp・lead echo・arp echo（名前は「音色」の論理チャンネル。重み {4: 1, 6: 2, 8: 1}）
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
- 編成: 4ch＝drums（kick/snare＋hat）・bass・e.piano・lead／6ch＝kick/snare・hat・bass・e.piano・lead・synth brass／8ch＝kick/snare・hat・bass・e.piano・lead・synth brass・lead echo・strings（名前は「音色」の論理チャンネル。重み {4: 1, 6: 2, 8: 1}）
- 和声: IVmaj7–V7–iii7–vi、I–V–vi–iii、ii7–V7–Imaj7–vi7（3 つを選んで区間に割り当てる）
- 文法: kick 0・8・10、ゲートスネア、16分のハット、タンバリン。ベースは8分のオクターブ、エレピは2分音符。シンセブラスはイントロ・サビの頭で「決め」（0・3・6 の3連打）、それ以外は和音を伸ばす。最後のサビ（sabi_up）と outro で全音上げる。
- 区別: city-pop はより遅く、丸サ進行とカッティング中心。pop は現代的な音色。

#### 6.16.27 `jrock-90s` — 90年代 J-ROCK 風（style、B6）

- 説明: 「90年代 J-ROCK 風。歪んだギターが前に出る速いビートとギターソロ、最後のサビで転調」／"90s J-rock style: loud guitars over a fast beat, a guitar solo and a final key change"
- 音色: 1 kick/snare（ProgKick・ProgSnare）／2 cymbal（ClosedHH・CrashCymbal）／3 bass（PickBass）／4 dist gtr（CrunchGtr）／5 lead gtr（ProgLeadGtr）／6 clean gtr（CleanGtr）
- 編成: 4ch＝drums（kick/snare＋cymbal）・bass・guitars（dist gtr＋clean gtr）・lead gtr／6ch＝kick/snare・cymbal・bass・dist gtr・lead gtr・clean gtr／8ch＝kick/snare・cymbal・bass・dist gtr・lead gtr・clean gtr・lead echo・strings（名前は「音色」の論理チャンネル。重み {4: 1, 6: 2, 8: 1}）
- 和声: bVI–iv–v–i、i–VI–VII–i、VI–VII–v–i（3 つを選んで区間に割り当てる）
- 文法: kick 0・3・8・10（サビは 0・2・8・10 で前のめり）、歪んだパワーコードの8分刻み、ベースは8分の根音。Aメロはクリーンギターの8分アルペジオ、ソロはリードギター（`4xy` 深め）。最後のサビ（sabi_up）で半音上げる。
- 区別: rock は洋楽的なリフ中心の構成。energetic は長調のパンク寄りで転調しない。

#### 6.16.28 `anime-ost` — アニメの劇伴風（style、B6）

- 説明: 「アニメ劇伴風。刻むストリングスとジャズの和声、ブラスの決め」／"Anime soundtrack style: driving strings with jazz harmony and brass hits"
- 音色: 1 kick/snare（ProgKick・SwingBrushSnare）／2 ride/crash（SwingRide・CrashCymbal）／3 bass（SwingWalkBass）／4 piano（Piano の和音）／5 lead（SwingSaxLead・OrchViolin・BrassSection）／6 strings/brass（Spiccato・BrassSection）
- 編成: 4ch＝drums（kick/snare＋ride/crash）・bass・piano・lead／6ch＝kick/snare・ride/crash・bass・piano・lead・strings/brass／8ch＝kick/snare・ride/crash・bass・piano・lead・strings/brass・lead echo・violin line（名前は「音色」の論理チャンネル。重み {4: 1, 6: 2, 8: 1}）
- 和声: im7–ivm7–VII7–IIImaj7、iim7b5–V7–im7–im7、VImaj7–V7–im7–im7（3 つを選んで区間に割り当てる）
- 文法: kick＋ブラシのスネア、ライド、ウォーキング・ベース、ピアノはチャールストンの7th。主題はサックス（a）とヴァイオリン（b）が持ち替え、climax はブラスが歌う（`lead_key`）。ストリングスは16分の刻み（3+3+2 のアクセント）。intro・break・outro はブラス・ピアノ・ベース・キック・クラッシュの「決め」（16分の 3+3）を2小節ごとに入れ、最後は決めで終わる（決めは他のパートより優先して置き換える）。
- 区別: swing-jazz は小編成のジャズそのもの。anime-ost は弦と管の劇伴にジャズの和声を混ぜる。

#### 6.16.29 `jrpg` — JRPG のフィールド曲風（style、B6）

- 説明: 「ゲーム音楽風（JRPG）。旋律を重視した冒険のテーマ、ハープと弦とホルン」／"JRPG game music style: melodic adventure theme with harp, strings and horn"
- 音色: 1 timpani/snare（OrchTimpani・MarchSnare）／2 harp（Harp）／3 cello（OrchCello）／4 strings（StringPad の和音）／5 melody（Flute・OrchTrumpet）／6 brass（BrassSection）
- 編成: 4ch＝timpani/snare・harp・cello・melody／6ch＝timpani/snare・harp・cello・strings・melody・brass／8ch＝timpani/snare・harp・cello・strings・melody・brass・melody echo・choir（名前は「音色」の論理チャンネル。重み {4: 1, 6: 2, 8: 1}）
- 和声: I–V–vi–iii、IV–I–IV–V、vi–IV–V–I、I–bVII–IV–I（宣言順にすべて使う）
- 文法: ハープは16分の上行分散和音、弦のパッド、チェロは2分音符、ティンパニは和音の変わり目、スネアは軽い行進風。旋律はフルート（b はトランペット）で、4小節の楽節の2小節目は1小節目の動機を1音階上げて繰り返す（ゼクエンツ。音域の上端を超える音はそのまま）。intro は金管のファンファーレ、b と ending は金管の対旋律（和音の第3音の長音）。進行は宣言順に固定: 主題はカノン型の8小節（a＋a2）。
- 区別: march は軍楽の行進曲。orchestral・cinematic は旋律より響き中心。jrpg は覚えやすい主旋律が主役。

#### 6.16.30 `lofi-chill` — ローファイ・プロデューサー風のチル（style、B6）

- 説明: 「ローファイ・チル。柔らかいギターとフルート、うねるサイドチェインと雨音」／"Lo-fi chill: soft guitar and flute, pumping sidechain and rain ambience"
- 音色: 1 kick/rim（BoomBapKick・Rimshot）／2 shaker（Shaker）／3 bass（FingerBass）／4 guitar（NylonGtr の和音）／5 flute（Flute）／6 rain（Rain）
- 編成: 4ch＝drums（kick/rim＋shaker）・bass・guitar・flute／6ch＝kick/rim・shaker・bass・guitar・flute・rain／8ch＝kick/rim・shaker・bass・guitar・flute・rain・flute echo・e.piano（名前は「音色」の論理チャンネル。重み {4: 1, 6: 2, 8: 1}）
- 和声: Imaj7–iii7–vi7–IVmaj7、IVmaj7–ivm7–Imaj7–vi7、Imaj9–IVmaj9（2 つを選んで区間に割り当てる）
- 文法: 16分スウィング 7:5。kick とリム（スネアの代わり）、シェイカー。ナイロンギターの和音（弦ごとに 18 ms ずらす）は2分音符、kick をトリガにギターと雨音にサイドチェイン（うねり）。フルートの旋律は `4xy`。
- 区別: lofi-hiphop はジャジーなエレピとブーンバップ。focus は旋律なし。lofi-chill はギター・フルート・雨音とサイドチェインのうねりで区別する。

#### 6.16.31 `indie-rock` — インディー・ロック風（style、B6）

- 説明: 「インディー・ロック風。生音のドラムと鳴り響くギターのアルペジオ、軽い歪み」／"Indie rock style: live-sounding drums, ringing guitar arpeggios and light overdrive"
- 音色: 1 kick/snare（ProgKick・PopSnare）／2 hat（ClosedHH・Tambourine・CrashCymbal）／3 bass（PickBass）／4 clean gtr（CleanGtr）／5 lead（SquareLead）／6 crunch gtr（CrunchGtr）
- 編成: 4ch＝drums（kick/snare＋hat）・bass・clean gtr・lead／6ch＝kick/snare・hat・bass・clean gtr・lead・crunch gtr／8ch＝kick/snare・hat・bass・clean gtr・lead・crunch gtr・lead echo・organ（名前は「音色」の論理チャンネル。重み {4: 1, 6: 2, 8: 1}）
- 和声: I–IV–vi–V、I–iii–IV–iv、vi–IV–I–V（2 つを選んで区間に割り当てる）
- 文法: 半数の seed でキックを4つ打ち（ダンス寄り、`plan()` で決める）、それ以外は kick 0・6・8＋タンバリン。クリーンギターは8分のアルペジオ（往復）、サビで軽い歪みのギターがストロークを足す。ベースは8分。
- 区別: rock はパワーコードのリフ。jrock-90s は強い歪みと速さ。

#### 6.16.32 `trailer` — 映画予告編風（style、O8）

- 説明: 「映画予告編風。大太鼓と金管の衝撃、刻む弦、合唱で盛り上がる3幕構成」／"Cinematic trailer style: taiko and brass hits, driving strings and choir in three acts"
- 音色: 1 taiko（Taiko）／2 toms/snare（Tom・MarchSnare）／3 braam（Braam）／4 spiccato（Spiccato）／5 low strings（OrchCello）／6 choir（Choir の和音）／7 high strings（OrchViolin）／8 fx（Riser・Impact）
- 編成: 6ch＝percussion（taiko＋toms/snare）・braam・spiccato・low strings・choir・high strings／8ch＝taiko・toms/snare・braam・spiccato・low strings・choir・high strings・fx（名前は「音色」の論理チャンネル。重み {6: 1, 8: 2}）
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
- 編成: 4ch＝cajon/shaker（cajon＋shaker）・bass・guitar・voice／6ch＝cajon・shaker・bass・guitar・voice・voice echo（名前は「音色」の論理チャンネル。重み {4: 2, 6: 1}）
- 和声: I–V–vi–IV、vi–IV–I–V、I–iii–vi–IV（2 つを選んで区間に割り当てる）
- 文法: トラヴィス奏法: 親指が4分で根音と5度を交互に、他の指が8分裏で上声を弾く（1チャンネルの単音）。カホンとシェイカーは軽く、ベースは全音符で弱く。旋律（VoxOoh）は息継ぎを強めに（動機の多くが最後の拍を空け、4小節目は後半を休む）。intro・outro はギターのみ。
- 区別: folk はストロークとフィドル。warm はピアノの旋律。

#### 6.16.35 `neo-soul` — ネオ・ソウル風（style、B6）

- 説明: 「ネオソウル風。よれたビートとエレピ主体の豊かなテンションコード」／"Neo soul style: laid-back off-grid beats and lush electric piano chords"
- 音色: 1 kick/snare（BoomBapKick・PopSnare）／2 hat（ClosedHH・Rimshot）／3 bass（FingerBass）／4 e.piano（ElectricPiano の和音）／5 vocal（VoxOoh）／6 e.piano 2（ElectricPiano の和音）
- 編成: 4ch＝drums（kick/snare＋hat）・bass・e.piano・vocal／6ch＝kick/snare・hat・bass・e.piano・vocal・e.piano 2／8ch＝kick/snare・hat・bass・e.piano・vocal・e.piano 2・vocal echo・guitar（名前は「音色」の論理チャンネル。重み {4: 1, 6: 2, 8: 1}）
- 和声: bIIImaj9–ii7–iv9–i11、ii9–V13–iii7–VI9、i11–IV9（2 つを選んで区間に割り当てる）
- 文法: 強い16分スウィング 8:4。スネアとハットの一部を `EDx`（1〜2 tick）で遅らせる（スネア 0.35・ハット 0.25 の確率、§6.14）。エレピ2台（3ch は裏拍のスタブ＋`4xy`、6ch は持続）、ベースは16分のシンコペーション。
- 区別: rnb-soul はきれいなグリッドのスロー・ジャムと弦。neo-soul は拍のよれと EP の複雑な和音。


### 6.17 音色空間の疎な領域を埋める3ジャンル（gamelan・chiptune・industrial）

2026-09-24 の検討（DESIGN_HISTORY.md §12.7）で、47ジャンルが使う音色 115 種を core の `Patch` のパラメータから導いた軸（信号源の構成・減衰・非調和度・音域・倍音の重心・音程の動き・立ち上がり・飽和）に置いたところ、「整数倍音・中音域・即時の立ち上がり・音程が動かない」に偏り、次の領域が疎だった。core には手を入れず（トーンの上昇包絡の追加は見送り）、疎の領域の音色が主役になる3ジャンルを足した。

| 疎の領域 | 実数（115種中） | 埋めるジャンル |
|:---|:---|:---|
| A. 非調和 × 長い減衰・低音域（ゴング・鐘） | 0（非調和の7種はシンバル類で高音・短い） | `gamelan` |
| B. 上昇する音程 | 1（fx_riser） | `chiptune` |
| D. 強い飽和 × 持続・非調和 | 強い飽和 8、持続 1、非調和 0 | `industrial` |
| E. 明るい × 低音域・高音域 | 明るい 6（低音 2・高音 0） | `chiptune`・`industrial` |

#### 6.17.1 `gamelan` — ジャワのガムラン風（genre、6ch）

- 音律: スレンドロ（0・240・480・720・960 セント）とペロッグの5音（0・120・270・670・780）を seed で選ぶ。maqam と同じく `MicroScale.absolute_cents ÷ 100` の**小数の音高**で書く（finetune の派生楽器は不要になった。MOD は Realizer が 12.5 セント刻みの finetune の変種サンプルを作り、他の形式はレート／finetune で出す。§4.8）。
- 音色（新規、`synth_presets/metal.py`）: saron（鍵盤。部分音 1・2.71・5.2、中程度の減衰）、bonang（壺型ゴング。1・1.52・2.34・3.4）、kenong（大きな壺。近い部分音のうなり、長い減衰）、kempul（吊りゴング）、gong ageng（1・1.006 のうなりと 1.53・2.34・2.83・3.67 の非調和部分音、5秒の減衰。主音の1オクターブ下＝約 65〜123 Hz で鳴らす）、ketuk（短く止めた壺）、kendang（太鼓の低音 dhe・高音 tak）。saron・bonang は finetune 6種の派生、kenong・kempul は構造音（主音とその上の4番目の度数）だけを打つので3種の派生を持つ（計22サンプル）。
- チャンネル: 1 kendang／2 gong ageng・kempul／3 kenong・ketuk／4 saron（balungan）／5 peking（saron の1オクターブ上、2倍の密度）／6 bonang（4倍の密度の装飾）。
- 構造: 1拍＝4 row、1 measure＝1 gatra（4拍）、1 pattern＝1 gongan（16拍）。lancaran の打ち分け: gong は16拍目、kenong は4拍ごと、kempul は6・10・14拍目、ketuk は奇数拍。irama II（balungan が半分の密度、装飾は16分）の区間を挟む。balungan は gatra の最後の音（seleh）を構造音にした順次進行主体の旋律で、gongan の最後は主音。
- 装飾: 拍の組（a, b）ごとに、peking は a a b b（balungan の2倍の密度）、bonang は a b a b …（4倍の密度）で刻む。kenong は4拍ごとに構造音（16拍目は主音）、kempul は balungan の音が主音なら主音・それ以外なら構造音。
- 構成: buka（bonang の独奏で最後の gatra を示し、kendang が入って gong）→ gongan A・B（irama I）×2 → gongan A（irama II。2 pattern で1 gongan）×2 → gongan A → suwuk。balungan は `plan()` が作り、要約行に数字譜風（1 2 3 5 6）で出す。

#### 6.17.2 `chiptune` — 8bit ゲーム音楽風（style、4ch）

- 音色（新規、`synth_presets/synths.py`・`fx.py`）: パルス波 25%（旋律）・12.5%（アルペジオ。細く明るい）、三角波（ベース）、ノイズのキック・スネア・ハット、上昇ピッチの「ジャンプ音」（2本の上昇スイープ）。
- チャンネル（ファミコンの音源の割り当て）: 1 パルス（旋律）／2 パルス（和音を `0xy` のアルペジオで）／3 三角波（ベース）／4 ノイズ（ドラム・効果音）。
- 文法: 速いテンポ（140–170）、和音は `0xy` アルペジオを毎 row 書く（和音の変わり目と 8 row 目に鳴らし直す。音量と効果は同じセルに書けないので、鳴らし直す音はサンプルの既定音量）、旋律は `4xy` ビブラート、ベースは8分のオクターブ、区間の終わりにスネアのフィルとジャンプ音。長調（I–bVII–IV–I の進行も使う）。
- 区別: jrpg は管弦楽の音色、chiptune は矩形波・三角波・ノイズだけ。

#### 6.17.3 `industrial` — インダストリアル（genre、6ch）

- 音色（新規）: 強く歪んだキック・スネア、金属の打撃（非調和部分音＋強い飽和）、音程のある金属音（リフ用）、工場の騒音（一定のノイズ＋低いうなり）、強く歪んだ持続ベース（明るい低音）、歪んだ矩形波リード。
- チャンネル: 1 kick/snare／2 金属の打楽器／3 歪んだベース（16分の反復）／4 金属のリフ／5 リード／6 騒音。
- 文法: フリジアン、110–130 BPM、機械的な16分の反復（ベースは根音・短2度・5度の `pulse16`）、金属の打楽器は裏拍の型、金属パイプのリフは pattern ごとに選んだ1小節の型を和音の構成音で繰り返す、工場の騒音は2小節ごとに鳴らし直す。
- 区別: dark-tense はシネマティックな弦と braam、industrial は歪みと金属音の反復。techno はクリーンな電子音。

#### 6.17.4 共通

- 3ジャンルとも §6.14 の部品の上に宣言で書く。編成（§6.14）は固定（gamelan・industrial は 6ch、chiptune は 4ch＝`channel_cap=4`）。
- 新しい音色は全て今の core の組合せで作る（非調和の部分音、開始 < 終了の `PitchSweepLayer`、`saturate`）。
- 検査は既存の共通検査（第３段階のジャンル）がそのまま掛かる。非調和の音程楽器（saron・bonang・kenong・kempul・gong ageng・金属パイプ）は MIDI 音高の YIN 検算の対象外（ベルと同じ）。

### 6.18 `racing-breaks` — 90年代後半のレースゲーム風（style、4/6/8ch）

2026-09-25 に追加（経緯は DESIGN_HISTORY.md §12.8）。特定の作品のサウンドトラック（R4 の BGM 13曲）を音声解析して得た特徴を宣言値にした。id・表示名・説明に作品名は入れない（§6.14 の人名と同じ扱い）。§6.14 の部品の上に宣言で書き、core は変えていない。

**解析で分かった特徴**（librosa による自動推定。和音の 9th は判定の偏りで多めに出ている可能性がある）

| 観点 | 結果 |
|:---|:---|
| テンポとリズム | ドラムンベース 166〜175 BPM（6曲）、ブレイクビーツ 144〜148（4曲。うち1曲は4つ打ち）、2ステップ／ブロークンビーツ 約120（2曲）。どれもスネアは2・4拍、ハットは真っすぐの8分（スウィングしない） |
| キック | ドラムンベースは1拍目と3拍目の裏（2拍目の裏が混じる）、ブレイクビーツは1拍目と次の拍へ食う16分、2ステップは16分単位で不規則にずれる |
| 調と和音 | 13曲中10曲が短調。和音は m9・maj9・7sus4 がほとんどで三和音はほぼ無い。1〜2小節ごとの2和音の往復（i m9–iv m9 が最多、i–♭VImaj9、i–♭IImaj9 など） |
| 音色 | 120 Hz 未満にエネルギーの 43〜75%（サブベース）。16分のオクターブ跳躍は少ない（スラップではない）。調波成分が打楽器の 3〜5 倍、スペクトル重心 2〜3 kHz |
| 構成 | 短いイントロから盛り上がり、中盤にドラムの抜けるブレイクダウン、8・16小節単位 |

**宣言**

- 説明: 「90年代後半のレースゲーム風。ドラムンベース／ブレイクビーツに 9th のエレピと太いサブベース」／"Late-90s racing game style: drum'n'bass / breakbeat with 9th-chord e.piano and deep sub bass"
- **リズムの系統**: `plan()` が曲ごとに `rng.plan` から1つ選び（重み ドラムンベース 3：ブレイクビーツ 3：2ステップ 1）、系統の BPM 候補（166〜174／144〜148／118〜122、2刻み）から BPM を引き直す。`tempo_choices` は3系統の和。系統は要約行（`Rhythm`）に出し、`PatternPlan.extra["family"]` で各フックに渡す。`--tempo` は系統を変えない（同じ seed・別テンポは同じ曲の速さ違い。§5.5）。
- 音色: 1 kick/snare（RacingKick・PopSnare）／2 hat/ride（Hat909・OpenHat909・SwingRide・CrashCymbal）／3 bass（RacingSub）／4 e.piano（ElectricPiano の和音）／5 pad（WarmPad の和音）／6 lead（VoxOoh）／7 lead echo／8 brass（BrassHorn の和音。任意パート）
- **低音**: 合成の実音は1オクターブ上になる（§3.1）ので、そのままでは 120 Hz 未満がほぼ出ない（初版の実測 1〜2%）。ジャンルのファイル内で、キックは `drum_909_kick` の掃引を半分の周波数（90→26 Hz、実音 180→52 Hz）にした `RacingKick`、ベースは `bass_deep` を `shift=0` にした `RacingSub`（t=0..11 で鳴り、実音 65〜123 Hz）にした。生成曲の 120 Hz 未満は 61〜75%。
- 編成: 4ch＝drums（kick/snare＋hat/ride）・bass・e.piano・lead／6ch＝kick/snare・hat/ride・bass・e.piano・pad・lead／8ch＝6ch＋lead echo・brass（重み {4: 1, 6: 2, 8: 1}）
- 調・和声: 主音 A・B♭・E・C・F、aeolian（和音ごとに m9＝dorian、maj9＝lydian、7sus4＝mixolydian）。進行は i m9–iv m9、i m9–♭VImaj9、i m9–♭IImaj9、♭IIImaj9–♭VImaj9–i m9–v7sus4、i m9–♭VIImaj9–♭VImaj9–v7sus4 から2つ。和音の種類が3つ（m9・maj9・7sus4）なので和音サンプルは3×3、全17サンプル。
- ドラム（`GROOVES` は `<系統>:<区間の groove>`。`drums()` の上書きで区間の groove 名に系統を前置する。fill・crash は共通）:

  | 系統 | キック | スネア | ハット類 |
  |:---|:---|:---|:---|
  | ドラムンベース | 0・10（6 は 0.35） | 4・12、ゴースト 7・9・15（0.4） | 8分（表拍を強く）、14 にオープン（0.3） |
  | ブレイクビーツ | 0・10、3（0.4）・15（0.6） | 4・12、ゴースト 7・14（0.35） | 8分、6 にオープン（0.3） |
  | 2ステップ | 0・10、5（0.45）・11（0.3） | 4・12 | 裏拍のオープン（2・6・10・14）と16分の裏のハット（0.7） |

  intro・build は各系統の軽い型（キックとハットだけ。ドラムンベースはライドを足す）。
- ベース（ジャンル内の `BreaksBass`。サブの持続音）: ドラムンベース＝0・10 に根音、14 に次の和音の根音の半音下（0.5）／ブレイクビーツ＝0・10 に根音、3 に根音（0.5）・7 に5度（0.5）、15 で次の和音の根音へ食う（0.6）／2ステップ＝0・6・10 に根音、3 にオクターブ上（0.4）・13 に5度（0.5）。次の和音の根音は `MeasurePlan.next_chord` から引く（pattern の最後は先頭へ戻る）。
- エレピ（ジャンル内の `BreaksComp`）: ドラムンベース 0・10、ブレイクビーツ 0・7（0.5）・10、2ステップ 0・3（0.6）・10。強拍の直後に `4xy`（0x22）の揺れ。トレモロ（`Tremolo`）は使っていない（以前は S3M・IT に変換できなかったが、今は全形式で使える。§7.6）。
- 旋律: VoxOoh、ビブラート 0x33、gate 0.9。区間 a・b で鳴らし、lead echo（3 row、0.45）を 8ch で足す。brass は旋律のある区間の和音の変わり目に和音サンプル（8ch だけ）。
- 構成: intro（drums・pad）, groove ×2, a ×2, b ×2（crash・fill）, groove, a ×2, b ×2, break ×2（comp・pad だけ）, build（fill）, b ×2, outro ×2（19 区間。ドラムンベースで約 1分50秒、2ステップで約 2分30秒）
- 区別: house・techno は4つ打ち、lofi-hiphop・hiphop はスウィングする遅いビート。racing-breaks は速い真っすぐのブレイクビーツと短調の 9th の2和音の往復、太いサブベース。
- 表現できないもの: フィルタのスイープ（MOD・S3M・XM にフィルタが無い。IT では `Automation("cutoff")` で表せるが使っていない）、高域の明るさ（トラッカーの再生レートの制約で 2 kHz 以上が OST より少ない）、ボーカル（`VoxOoh` の旋律で代える）。

---

## 7. 出力形式

### 7.1 形式の一覧と `--channels`（`core/formats.py`・`framework/target.py`）

`core/formats.py` は形式の名前・拡張子・説明と、`--channels` の意味（`choices`＝ジャンルが宣言した数から選ぶ／`max`＝上限／`none`＝指定不可）の表を持つ。形式の能力（行数・pattern 数・サンプルの上限・機能）は `framework/target.py`（§3.2）。

| 形式 | 拡張子 | `--channels` | チャンネル数 | 備考 |
|:---|:---|:---|:---|:---|
| `mod`（既定） | `.mod` | ジャンルが宣言した 4・6・8（それ以外は `ChannelCountError`＝終了コード 2） | 予算そのもの | 4ch は `M.K.`、他は FastTracker 系の `6CHN`・`8CHN`（本家 ProTracker／Amiga 実機では再生不可）。定位はプレイヤー固定（L R R L） |
| `xm` | `.xm` | 上限（1〜32） | 実際の lane 数（制御チャンネル込み） | 16-bit サンプル・ボリューム列 |
| `s3m` | `.s3m` | 上限（1〜16） | 同上 | 8-bit サンプル（高レート） |
| `it` | `.it` | 上限（1〜64） | 同上 | 楽器モード・16-bit サンプル |
| `midi` | `.mid` | 指定不可（引数エラー） | 鳴らした MIDI チャンネルの数 | General MIDI の SMF（format 1、PPQ 480） |
| `mp3` | `.mp3` | 上限（1〜64。IT と同じ） | IT と同じ | ffmpeg が必要。320 kbps |

- 予算が小さすぎてジャンルのパートが収まらないとき（ladder の最後でも超える）は `ChannelCountError`（「このジャンルは N チャンネル以上が要る」）。
- `--genre random` と `--channels` の組合せ: その値でこの形式を作れるジャンル（`engine.supports_channels`）だけから選ぶ。
- バナーには実際に使ったチャンネル数と、MOD・MIDI 以外では上限を出す（例: `Channels   : 15 (limit 16)`）。`--json` の `channels`（使った数）・`channel_budget`（予算）・`sample_bits`（§8.8）。

### 7.2 MOD（`core/writer.py`）

ProTracker `M.K.`（4ch）／`xCHN`（6・8ch）。1サンプル ≤ 131070 byte、8-bit signed。`Cell.serialize()` が4バイトのセルを作る。Realizer（§7.6）が作った `RealizedSong` を `native.to_mod_song` で `Song` に直して `writer.serialize` に渡す。MOD にはチャンネルパン・初期テンポの欄が無い（テンポは先頭 row の `Fxx`）。**MOD の描画は m＝1（8-bit・Paula のレート）のままなので、再設計の前後で音色の解像度は変わらない**（出力の互換は求めない: §6.1 の nostalgic の旧挙動も保っていない）。

### 7.3 XM（`core/native_xm.py`）

- **音量をボリューム列に置く**（`0x10 + vol`）。エフェクトの列が空くので、音量とビブラートなどを同じセルに書ける。
- **16-bit サンプル**: サンプルヘッダの type の bit 4、長さ・ループはバイト単位、データは語単位の delta 符号化。
- 再生レート: 基準ノート C-4（XM note 49）で `rate_hz` になるよう、`relative note + finetune/128 = 12 × log2(rate_hz / 8363)` を整数部と 1/128 の端数に分けて書く（Amiga 周波数表。`header_size` は自身を含め pattern order table の終端まで＝276）。
- `RCell.note` は 0 始まりの半音番号（C-0 = 0）で、writer が XM の表記（+1）に直す。特別な値は `NOTE_OFF`（97）。**キーオフはエンベロープ無しでも止まる**（実測）。
- エンベロープ: `release_s` のある楽器だけ、音量エンベロープ（サステイン点＋0 へ落ちる点の2点）を有効にし、キーオフでリリースする。キーオフからの振幅が `release_s` に ±0.02 秒で一致する（tick の換算は曲の初期テンポ）。
- パン: **lane のパンごとに別のサンプル**（サンプルパン）にする（XM は発音のたびにサンプルのパンへ戻るため、セルごとの `Px` をやめた）。`Automation("pan")` は `8xx`。
- 上限: 32 チャンネル、128 楽器、256 pattern、1..256 row。

### 7.4 S3M（`core/native_s3m.py`）

- 8-bit unsigned（`ffi=2`）。**C2Spd ＝ `round(rate_hz)`**（基準ノート C-4＝note 48 で鳴る再生レート）。最大 65535、C2Spd が 1000 Hz を下回ったら検査器が WARN（V18。libopenmpt の下限処理で意図しない高さになる）。
- 1サンプルの長さは 64000 byte 以下（超えないよう描画の倍率 m を下げる。§4.8）。
- ノートカット `^^^`（254）。パンはヘッダのチャンネル設定（L1..L8／R1..R8）＋パンテーブル（`dp=0xFC`）。
- **S3M の音高には ST3 固有の周期表の誤差がある**: libopenmpt の S3M は ST3 の整数の周期表を再現しており、誤差は基準オクターブで最大 ±5.6 セント、C2Spd が 44.1 kHz だと周期が小さくなる高いオクターブで 8〜12 セントになる（実測）。ファイル側では直せないので、音高の検査（I4）の許容は S3M だけ 12 セント（XM・IT は 7、MOD は 9）。
- 上限: 16 チャンネル、99 サンプル、100 pattern、64 row 固定。

### 7.5 IT（`core/native_it.py`）

- **楽器モード**（1サンプル＝1楽器。NNA は Note Cut、キーボード表は全ノートをそのサンプルへ。楽器ヘッダ 554 byte）。**16-bit サンプル**（サンプルフラグの bit 1・Cvt の bit 0＝signed・非圧縮）。長さとループは「サンプル数」単位。
- **C5Speed ＝ 基準ノート C-5（IT note 60）での再生レート**（`rate_hz`）。
- フラグ: stereo、Amiga slides（linear slides=0。MOD と同じ period 単位のスライド）、Old Effects=1（ビブラート深さ等を MOD 互換にする）。
- エンベロープ: `release_s` のある楽器だけ、XM と同じ2点の音量エンベロープ（サステインループ付き）。ノートオフ `===`。**IT の `===` はエンベロープの無い楽器では止まらない**（実測）ので、`release_s` の無い楽器は `NOTE_CUT`（`^^^`）で止める。
- フィルタ: `Zxx`（既定の MIDI マクロでカットオフ。埋め込みのマクロは書かない。`Z127`→`Z32` で単調に帯域が下がることを実測）。
- 上限: 64 チャンネル、99 楽器・99 サンプル、200 pattern、32..200 row（IT は 32 row 未満の pattern を作れないので、32 row にして最後の実際の row に `C00`）。

### 7.6 TrackerRealizer（`framework/realize/`。MOD・S3M・XM・IT）

`realize(genre, score, plan, target) -> RealizedSong`（`level=True` で音量の底上げまで行う）。手順:

```text
 1. パートの選択（予算と min_channels）
 2. lane の需要を数え、予算に収まるまで段階的に減らす（ladder）
 3. lane をチャンネルに並べ、パンを決める
 4. イベントを lane に割り当てる（和音の声部化、打楽器の振り分け、複製）
 5. サンプルを計画して描画する（§4.8・§4.9）
 6. lane ごとにセルを作る（音高→ノート番号、音量、奏法→エフェクト）
 7. 音の終わり（dur・NoteOff・ループの区間頭での停止・リリース）
 8. ミックス規則（サイドチェイン）・オートメーション
 9. 時間軸（Speed・スウィング・テンポ）と row コマンド、pattern への詰め込み
10. 音量の底上げ（§7.9）
```

#### 予算とパートの選択

- 予算 `B`: MOD は `--channels`（`Genre.mod_channels` のキーに無ければ `ChannelCountError`）か、`random.Random(f"{seed}:{id}:channels")` で `mod_channels` の重みから選ぶ。S3M・XM・IT（と MP3）は `min(形式の上限, channel_cap, --channels)`。
- パート `p` を選ぶ条件: `p.min_channels ≤ B`。選ばれなかったパートのイベントは捨てる（作曲はしてある）。

#### lane の需要と ladder（`lanes.py`）

各パートの lane の数:

| パートの種類 | 「分ける」段階 | 「まとめる」段階 | 「1本」段階 |
|:---|:---|:---|:---|
| `kit` を持つ | 使われた楽器ごとに1本 | `Kit.groups` のグループごとに1本（使われたグループだけ） | 1本 |
| 和音（`chord` が空でない NoteEvent）を含む | 声部: 曲中の最大の構成音数 | ― | 焼く: 1本 |
| それ以外 | `poly` 本 | ― | ― |
| `double` を持つ | 上の数の2倍 | ― | 元の数（複製をやめる） |

ladder（`B` に収まった時点で止める。**順序は固定**で、ジャンルの宣言の並びだけで決まる）:

| 段階 | 処理 |
|:---|:---|
| L0 | 全 kit を「分ける」、和音を声部に開く、double を入れる |
| R1 | double を外す（後ろのパートから1つずつ） |
| R2 | 全 kit を「まとめる」（全 kit パートを1段階でまとめて適用する） |
| R3 | 和音を焼く（後ろのパートから1つずつ。焼けないパートは飛ばす） |
| R4 | kit を「1本」にする（後ろのパートから1つずつ） |
| R5 | まだ収まらなければ `ChannelCountError`（宣言の誤りは全ジャンル × 全予算のテストで見つける） |

最後に `lanes < B` なら1本を**制御チャンネル**（音を置かず、Speed・テンポ・`D00` などの row コマンドだけを書く）にする。例（pop）: MOD 4ch は drums・bass・piano・lead、6ch は kick/snare・hat・bass・piano・lead・pad、8ch は上＋lead echo・strings、S3M は打楽器2本＋和音は声部、XM・IT は打楽器5本＋和音は声部。

**チャンネルの並び**: パートの宣言順。パートの中は、kit の lane（グループ順、グループ内は楽器の順）、和音の声部（低い声部から）、`poly` の lane、`double` の複製。制御チャンネルは最後。**パン**（S3M・XM・IT）: lane のパンは `Instrument.pan`、無ければ `Kit.group_pan`／`Part.pan`。和音の声部は `pan + spread × (i/(k−1) − 0.5)`、`double` は `pan ± spread/2`。全部 128 のジャンルは L R R L（64/192 の繰り返し）。MOD はパンがプレイヤー固定なので並びだけが効く（打楽器の lane が先頭にまとまる house・energetic・rock・jrock-90s は、旧実装より定位が少しずれる）。

#### イベントの lane への割当

- **kit**: 楽器の lane（段階に応じて楽器・グループ・1本）。同じ lane の同じ step に2つの発音があれば、`NoteEvent.prio` が大きい方、同じなら `Kit.priority`（1本の段階では `single_priority`）が大きい方、それも同じなら kit の並びで先の楽器を残す（決定的）。
- **単音のパート**（`poly=1`）: 1本の lane。**`poly>1`**: 空いている lane のうち番号の小さいもの。無ければ最も古い音の lane を奪う。
- **和音・声部**: NoteEvent 1つを、`pitch + chord[i]` の音として声部 i の lane に置く。音量は `round(vel / √k)`。構成音が lane の数より少ない和音では、余った lane を同じ step で止める。`strum_ms` は声部 i を `Delay` で遅らせる（step の tick 数 −1 で頭打ち）。
- **和音・焼く**: 和音の形の変種サンプルで `pitch` の高さに1音として置く。**double**: 元の lane のイベントを `pitch + detune_cents/100`・`vel × vel_ratio` で複製の lane に写す。

#### セル化と奏法の表現（`tracker.py`・`encode.py`）

- **音高 → ノート番号**: MOD は `t = round(n) − shift`（0..35 の外は `PitchRangeError`。微分音は finetune の変種サンプル）。S3M・XM・IT は基準ノート `N_ref`（S3M・XM は C-4＝48、IT は C-5＝60）から `N = N_ref + (round(n) − shift − rate_note)`。形式の音域の外なら `PitchRangeError`（MOD で鳴らすジャンルは MOD の範囲に収める）。音程の無い楽器は常に基準の位置。
- **奏法 → エフェクト**（`encode.Codec` の1つの表。param は MOD の単位で受け取る）:

| 奏法 | MOD | S3M | XM | IT | 注 |
|:---|:---|:---|:---|:---|:---|
| `Vibrato(p)` | `4xy` | `Hxy` | `4xy` | `Hxy` | IT は Old Effects=1 で深さが MOD と一致 |
| `Tremolo(p)` | `7xy` | `Rxy` | `7xy` | `Rxy` | **S3M・IT は深さが正確に半分で再生される**（実測）ので深さのニブルを 2 倍にして合わせる（上限 15） |
| `Arpeggio(x, y)` | `0xy` | `Jxy` | `0xy` | `Jxy` | |
| `Glide` | `3xx` | `Gxx` | `3xx` | `Gxx` | 下の「Glide」 |
| `Delay(t)` | `EDx` | `SDx` | `EDx` | `SDx` | |
| `Retrig(t)` | `E9x` | `Q0x` | `E9x` | `Q0x` | |
| `Cut(t)` | `ECx` | `SCx` | `ECx` | `SCx` | |
| `Offset(f)` | `9xx` | `Oxx` | `9xx` | `Oxx` | `xx = round(f × フレーム数 / 256)`、255 で頭打ち |
| Speed / テンポ | `Fxx` | `Axx` / `Txx` | `Fxx` | `Axx` / `Txx` | |
| pattern の途中終了 | `D00` | `C00` | （pattern 長で表す） | `C00`（32 row 未満） | |
| 音量 | `Cxx` | ボリューム列 | ボリューム列 `0x10+v` | ボリューム列 0..64 | |
| パン | ― | ヘッダ・`S8x` | サンプルパン・`8xx` | ヘッダ・`Xxx` | |
| カットオフ | ― | ― | ― | `Zxx` | |

- **1セルに入りきらないとき**（トラッカーはエフェクトの列が1つ）: 優先順位は row コマンド ＞ `Delay` ＞ `Glide` ＞ `Retrig`・`Cut` ＞ `Arpeggio` ＞ `Offset` ＞ `Vibrato`・`Tremolo` ＞ 音量スライド ＞ パン・カットオフ。負けた `Vibrato`・`Tremolo` は次の row へ移す（空いていなければ落とす）。他は落とす（DEBUG ログ）。MOD の音量（`Cxx`）とエフェクトが重なったとき: 音量が楽器の既定音量に等しいなら音量を書かない。違うときは、`Delay`・`Glide`・`Retrig`・`Cut`・`Arpeggio`・`Offset` ならエフェクトを残して音量を落とし（ドラムの `late`・march のアルペジオは既定音量で鳴る）、`Vibrato`・`Tremolo` なら音量を残して奏法を次の row へ移す。
- **`Glide`**（`tracker._resolve_glide`）: 同じ lane の直前の音について、(1) 鳴り終わっていれば（ワンショットの再生時間＝フレーム数÷再生レートが音の間隔より短い／明示の `dur` が尽きた／消音がある）`Glide` を外して普通の発音にする、(2) 鳴っていて `Glide.param` が無指定なら、直前の音の period から目標の period まで `steps × (row の tick 数 − 1)` 個の tick（スライドは row の最初の tick には掛からない）で届く速さを `3xx`/`Gxx` に書く。速さ ＝ **Amiga 換算の period の差 ÷ tick 数**（Amiga 換算の period ＝ `dsp.CLOCK` ÷ 再生レート。MOD は period 表、他は `rate_hz × 2^((note − 基準) / 12)`）。速さ 1 につき tick あたり period 1 が動くことは MOD・S3M・XM・IT の4形式で実測して確かめた（S3M・IT は period の単位が 4 倍だがスライドも 4 倍で相殺する）。1 オクターブ・7 半音のグライドが指定の step 数で届く（誤差 0.12 秒以内）。
- **音の終わり**: `dur` がある NoteEvent は `step + dur` の row で lane を止める（その row までに同じ lane で次の発音があれば何もしない）。`NoteOff` はその step で、その楽器が鳴っている lane を止める。`dur=None` のループは同じ lane の次の発音まで鳴り、**区間の終わりで止まる**（区間は音を持ち越さない）。止め方: `release_s` が無い（既定）なら即時（MOD は `Cxx 00`、S3M・IT は `^^^`、XM はボリューム列の音量 0）。`release_s` がある（opt-in）なら、XM・IT は音量エンベロープ＋キーオフ、MOD・S3M は音量スライド（`Axy`／`Dxy`）を `release_s` の間 row ごとに置き最後に止める（区間の終わりのループ停止だけは即時）。
- **ミックス**: `Sidechain` は、トリガの楽器の発音がある step ごとに（トリガは lane への割当の後に残った発音）、対象パートで鳴っている lane の音量を `ratio` 倍にし、`release_steps` かけて戻す音量のセルを置く（音量だけを書く、他のエフェクトのセルには触れない、直前の音量が分からなければその回は飛ばす。トリガが密集すると、2つ目が既にダッキング済みの音量を基準にさらに下げる簡略化がある）。`Automation("volume")` はその step の対象 lane に音量のセル、`"pan"` は S3M・XM・IT、`"cutoff"` は IT だけ。
- **サンプルの変種**: `SampleKey = (楽器名, 和音の形, セント, パン)`。実際に使われた鍵だけサンプルを作る。微分音・`tune_cents` は、MOD は finetune の変種（12.5 セント刻み）、S3M・IT は再生レートにセントを掛けた変種、XM は finetune。
- **時間軸**: 1 row ＝ 1 step。Speed（1 row の tick 数）＝ `24 // steps_per_beat`。**スウィング**は、区間の `swing` があれば、偶数 step を `long`・奇数 step を `short` の Speed にして**全 row** に書く（制御チャンネル優先。場所が無い row は、他のエフェクトだけのセルを消して作る。ただし Speed・テンポ・pattern の中断のセルは消さない）。スウィングのある曲は全区間の先頭に Speed を明示する。**テンポ**は、曲の先頭に BPM（形式のヘッダにも初期 BPM と Speed。MOD はヘッダが無いので先頭 row の `Fxx` だけ）、`TempoEvent` はその row に。row コマンドの場所は制御チャンネルを最優先し、1つの row に2つ以上要るとき・制御チャンネルが無いときは先頭 8 row の空きを探して、空のセル、音量・エフェクトの無い発音のセルの順に入れる。
- **pattern**: 区間の row 数が `max_rows` 以下なら1つの pattern、超えるときは小節の境目で分ける。MOD・S3M で 64 未満の pattern は最後の row に `D00`／`C00`。XM は実際の長さ、IT は 32 以上（足りない分は `C00`）。order 長・pattern 数の上限を超えたら `PlanError`。同じ内容の pattern の統合はしていない（区間の繰り返しは同じ pattern 番号の繰り返しで足りる）。
- **MOD の拡張音域は無い**（note は 0..35）。拡張した音域の `Glide` の外挿は不要で、S3M・XM・IT は基準ノートからの半音差だけで周期を求める。

### 7.7 MIDI（`framework/realize/midi.py`・`core/native_midi.py`）

Score から直接 SMF（format 1、**PPQ 480**。1 tracker tick ＝ 20 MIDI tick）を作る。トラッカー用の lane・ladder は使わない（**全パートを入れる**。MIDI は「ジャンルの意図を GM 音源で聴ける」ことが目的で、厚い編成が意図そのもの。`channel_cap` も無視）。

- **構造**: Track 0＝曲名・テンポ（`TempoEvent` から）・拍子（`Meter.signature`、可変拍子は小節ごと）。パートごとに1トラック。打楽器のパート（全楽器が `GmVoice(drum_note=)`）は MIDI ch 10、他はパートの宣言順に ch 1–9・11–16。足りなければ同じ program の単一楽器パートが相乗りし、それでも足りなければ `PlanError`。打楽器と旋律の楽器が混在するパートは打楽器の音を ch10、他を旋律のチャンネルに分ける。各チャンネルの頭で CC7＝127、ピッチベンドの幅を ±2 半音（`Glide` のあるパートは ±12）。
- **音高**: `midi = 69 + 12 log2(sounding_hz/440) + (t − rate_note) + tune_cents/100`（t ＝ 書かれた音高 − shift）＝実音。整数でない部分はピッチベンド。**セントの違う音が重なるパートはセントの値ごとに別チャンネル**。和音は構成音をすべて同時に発音（`strum_ms` は tick をずらす）。
- **長さ**: `dur` ＞（ループ: 区間の終わり／ワンショット: 自然減衰の長さ）と、同じパート・同じ楽器の次の発音のうち早いもの。`NoteOff`・`Cut` で短くなり、曲の終わりを超えない。同じチャンネル・同じ音高の重なりは次の発音の頭で切る。
- **奏法**: `Delay`＝発音を遅らせる、`Retrig`＝間隔ごとの再発音、`Arpeggio`＝1 tracker tick ごとに音を切り替え、`Vibrato`＝CC1（深さのニブル × 8、終わりで 0）、`Glide`＝直前の音が鳴っているときだけ、直前の音の高さのベンドから目標へ動かす（終わっていれば、差が 12 半音を超えれば普通の発音）、`Tremolo`・`Offset` は無視。
- **スウィング**: 奇数番目の step の発音を `long − 24 // steps_per_beat` tick 遅らせる。
- **ミキシング**: velocity ＝ `round(vel/64 × 127)` を、曲の最大が 127 になるまで一律に持ち上げる。`Automation`＝CC11・CC10・CC74、`Sidechain`＝対象パートの CC11。`Instrument.pan`／`Part.pan` は CC10。
- **検査**（`native_midi.verify`）: 読める・PPQ 480・EOT・note on/off の対応・テンポ・velocity とノート範囲・メロディのチャンネルの program 指定・ドラムの音域（27..87）、**同時発音数が GM1 の保証する 24 を超えたら WARN**。GM 音源での聴感の確認はこの環境では未実施。

### 7.8 MP3（`core/render.py`）

Realizer が **IT と同じ Target（64ch・16-bit・44.1 kHz）で作った IT** を一時ファイルに書いて ffmpeg に渡す: `ffmpeg -f libopenmpt -i x.it -af <音量> -c:a libmp3lame -b:a 320k -compression_level 0 ... out.mp3`（`-compression_level 0` は LAME の `-q 0`）。音量は2パス: 1回目に `volumedetect` で平均（RMS）と最大振幅を測り、2回目に平均が `TARGET_MEAN_DB`（−14 dBFS）に近づくだけ持ち上げてリミッタで `LIMIT_DB`（−1 dBFS）に抑える。リミッタで削る量は `MAX_LIMITING_DB`（4 dB）まで（ピークの多い曲は目標の平均に届かなくても潰しすぎない）。

**実行環境に ffmpeg が必要**（libopenmpt と libmp3lame を有効にしてビルドされたもの）。PATH 上の `ffmpeg`、または環境変数 `MODWEAVER_FFMPEG`。無い・機能不足なら `ExternalToolError`（終了コード 5）。`--list-genres --json` の `mp3` に可否を出す。

### 7.9 出力音量の底上げ（`core/native_level.py`・`framework/levels.py`）

トラッカー形式は、ミックスの音量をジャンルが決めた発音の音量とサンプルの波形が決める。生成したままだと形式・ジャンルによって最大振幅が −3〜−8 dBFS と小さく、MP3（2パスの音量調整）や MIDI より小さく聞こえる。そこで**ジャンルごと・形式ごとの測定値**から倍率を決めて書き出す。

- `framework/levels.py` の `PEAK_DB[ジャンル][形式+チャンネル数]` は、そのジャンルを複数の seed・全予算（MOD）・既定と最小の予算（S3M・XM・IT）で、**底上げなしで**作って libopenmpt で再生し、最大振幅の最悪値を記録した表（`tools/calibrate_levels.py` が作る。ffmpeg が要る）。鍵が無いチャンネル数は同形式の最悪値で代用する。
- 目標は最悪値が `TARGET_PEAK_DB`（−2 dBFS）になること。`realize(level=True)`（既定）が持ち上げる。**効果は形式で違う**: S3M・IT はヘッダのマスター音量（S3M 127・IT 128 まで）で約 −2〜−3.5 dBFS まで上がる。**XM と MOD は上がらない**: ヘッダのマスター音量が無く、音量の値は最大の発音（kick・bass が 59〜61）がすでに上限 64 に近く、サンプル波形の最大値も 0.9〜0.95 で余裕がほぼ無いため（XM −4〜−5、MOD 8ch −7〜−8、MOD 4ch −3.5 前後）。
- MIDI は velocity を曲の最大が 127 になるまで一律に持ち上げ、全チャンネルの CC7 を 127 にする（§7.7）。MP3 は §7.8。
- MOD 4ch の V15（左右の同時合計 ≤120。§9.1）の検査は残す。測定値が古くなると、実プレイヤーの音割れ検査（§9.2）が失敗して気付ける。
- 新しいジャンルを足したら `tools/calibrate_levels.py` で再測定する（全ジャンルの再測定は時間がかかるので、表は全部入れ直す形）。

---

## 8. CLI（`cli.py`）

### 8.1 オプション

| オプション | 短縮 | 既定 | 説明 |
|:---|:---|:---|:---|
| `--genre` | `-g` | `nostalgic` | ジャンル id（別名可）。`random` / `r` でランダム |
| `--seed` | `-s` | 100000〜999999 の乱数 | 任意の整数 |
| `--format` | `-f` | `mod` | `mod` / `xm` / `s3m` / `it` / `midi` / `mp3` |
| `--output` | `-o` | `output/<genre>_<seed>.<拡張子>` | 明示すればそのパスへ書く（存在しない親フォルダはエラー） |
| `--output-dir` | – | `output` | `--output` を省略したときの出力フォルダ（無ければ作る）。`--output` とは同時に使えない（終了コード 2） |
| `--tempo` | `-t` | ジャンルが決める | `120` または `80-100`（§5.5） |
| `--channels` | `-c` | MOD はジャンルが曲ごとに決める。他の形式は形式の上限 | 意味は形式ごと（§7.1）: MOD はジャンルが宣言した 4・6・8 のうちの数（それ以外はエラー＝終了コード 2）、S3M・XM・IT・MP3 は上限（ladder がその中に収める。収まらなければ終了コード 2）、MIDI は指定不可（終了コード 2） |
| `--list-genres` | – | – | 全ジャンルの id・別名・1行説明を区分（気分・ジャンル・〜風）ごとに表示して終了 |
| `--json` | – | – | `--list-genres` と生成結果を機械向けの JSON で出す（§8.8） |
| `--english` | `-e` | – | 表示を英語にする（§8.5） |
| `--version` | `-v` | – | `ModWeaver <版>` と GitHub URL を表示して終了（他の引数より優先） |
| `--help` | `-h` | – | 使い方を表示して終了。末尾は区分ごとのジャンル id だけ（説明は `--list-genres`） |

### 8.2 起動の分岐

1. `-e` / `--english`（`--eng` などの省略形を含む）を解析前に探し、表示言語を決める（usage の言語は解析前に要るため）。`-es 5` のようにまとめた場合は解析後の値で英語にする（この書き方で usage を出すときだけ日本語になる）。
2. `-e` 以外の引数が無ければ、`--help` と同じ usage を stdout に出して終了コード 0。
3. `--list-genres` はジャンル一覧（`--json` があればカタログの JSON。§8.8）を出して 0。`--version` は argparse の version アクション。
4. それ以外は生成（§2.1）。結果はバナー（§8.6）、`--json` があれば結果の JSON（§8.8）。

### 8.3 `--genre random`

- 候補は登録済みの**正規 id**（別名は数えない。suspense-slow が2倍選ばれないように）。`--tempo` があれば `tempo_range` が要求と重なるジャンルだけを候補にし、1つも無ければ `TempoRangeError`（終了コード 2）。
- `--channels` があれば、その数でこの形式を作れるジャンル（`engine.supports_channels`。MOD は宣言した数、他の形式は ladder が収まるもの）だけを候補にする（1つも無ければ `ChannelCountError`、終了コード 2）。
- 選択は seed と独立（`random` モジュール）。再現はバナーの再現コマンド（選ばれたジャンル名が入る）で行う。
- 大文字小文字は区別する（`Random` は未登録ジャンル）。

### 8.4 出力先

`--output` 省略時は `output/<genre>_<seed><拡張子>`（カレントディレクトリの `output` フォルダ。`--output-dir` があればそのフォルダ。どちらも無ければ作る）。拡張子は形式に合わせる（`midi` は `.mid`）。中身と拡張子が食い違うとプレイヤーが読み込みに失敗するため。

### 8.5 表示言語

- 既定は日本語、`-e` で英語。対象は usage（説明・オプション説明・見出し `使い方:`／`オプション:`／`ジャンル一覧:`）、`--list-genres` とヘルプ末尾の一覧（`description` / `description_en`、`別名:` / `alias:`）、実行結果のバナー（見出し・成功メッセージ・`(ランダム)`・`(指定 80-100)`）。文言は `cli.MESSAGES` の ja/en 表。
- 変えないもの: ジャンルが出す要約行（`plan.summary`。コード進行名などの音楽用語）、`--version` の出力、stderr のエラー・警告、生成される曲。
- argparse は `len()` で折り返すので全角が2桁ぶんはみ出す。ヘルプは表示幅（全角＝2桁）で折り返し、英数字の語（`free-jazz,` 等）は分割せず、句読点・閉じ括弧を行頭に置かない（`_wrap`）。
- バナーの見出しは表示幅で 12 桁に揃える（`ジャンル    : ` と `Genre       : ` の `:` が同じ桁）。

### 8.6 バナーと再現コマンド

区切り線・`ModWeaver: <display_name>`・ジャンル（random なら `(ランダム)`）・出力形式・シード・テンポ（範囲指定なら要求範囲も）・チャンネル数（実際に使った数。MOD で `--channels` 指定なら `(指定)`、MOD・MIDI 以外は `(上限 N)` で予算を出す。例: `チャンネル  : 15 (上限 16)`）・`plan.summary` の各行・出力ファイル・再現コマンド。再現コマンドは `<起動方法> --genre <id>`、指定されたときだけ `--format <形式>`・`--tempo <確定した BPM>`（範囲ではなく確定値）・`--channels <数>`（指定しなければ、MOD は seed で同じ編成になり、他の形式は形式の上限になる）、最後に `--seed <seed>`。起動方法は `modweaver.py` なら `python modweaver.py`、それ以外は `python -m mod_weaver.cli`。

### 8.7 終了コード・例外・ログ

| コード | 意味 | 例外 |
|:---|:---|:---|
| 0 | 成功（引数なし・`--help`・`--list-genres`・`--version` を含む） | |
| 2 | 引数エラー、未登録ジャンル、対応できないテンポ・チャンネル数 | argparse、`ProfileNotFoundError`、`TempoRangeError`、`ChannelCountError` |
| 3 | 生成・検査エラー | `PlanError`・`VerificationError` ほか `ModGenError` |
| 4 | 出力エラー | `OutputError` |
| 5 | mp3 の外部ツール不足 | `ExternalToolError` |
| 1 | 想定外の例外（スタックトレースを出す） | その他 |

例外階層: `ModGenError` ← `ProfileNotFoundError`（未登録のジャンル）・`PitchRangeError`・`CellConflictError`・`ChannelConflictError`・`SampleConstraintError`・`TempoRangeError`・`ChannelCountError`（`--channels` が形式・ジャンルに合わない、ladder が予算に収まらない）・`PlanError`・`VerificationError(issues)`・`OutputError`・`ExternalToolError`。

ログは `logging.getLogger("mod_weaver")`。ハンドラは cli だけが設定し（stderr、WARNING 以上）、ライブラリ層は設定しない。検査の WARN は WARNING として出る。バナーは stdout。

### 8.8 JSON 出力（`--json`）

GUI など、ほかのプログラムから CLI を呼ぶための出力。人向けの表示（バナー・一覧）は読み取りに使わない（言語で文言が変わり、形も変わりうるため）。

- stdout に JSON を1つだけ出す。非 ASCII は `\uXXXX` にする（Windows でパイプの文字コードが cp932 でも化けない）。
- エラーは今までどおり stderr と終了コード（§8.7）。そのとき stdout には何も出さない。`-e` は JSON の中身を変えない。
- `--list-genres --json`（カタログ）: `version`・`url`・`default_genre`・`random_genre`（`["random", "r"]`）・`default_format`・`formats`（`name`・`extension`・`description`・`channels`＝`--channels` の意味: `{"choices": [4, 6, 8]}`（MOD。ジャンルが選べる数の和集合）／`{"max": 16}`（S3M・XM・IT・MP3。上限）／`null`（MIDI。指定不可））・`tempo`（`min`・`max`）・`seed_range`・`categories`（`id`・`ja`・`en`。区分の表示名）・`genres`（`id`・`display_name`・`category`・`aliases`・`description`・`description_en`・`tempo_range`（`--tempo` で指定できる範囲）・`tempo_choices`（ジャンルが自分で選ぶテンポの候補。昇順）・`mod_channels`（MOD で選べるチャンネル数）・`channel_cap`（ジャンルの美的な上限。なければ null））・`mp3`（`available`・`ffmpeg`（パス）・`error`。`render.check_ffmpeg` と同じ検査）。ジャンルの並びは `--list-genres` と同じ（区分順・id 順）。
- 生成時の `--json`（結果）: `genre`・`display_name`・`random_genre`・`format`・`seed`・`bpm`・`tempo_request`（`"80-100"` など。指定なしは null）・`channels`（実際に使った数）・`channel_budget`（予算＝選べた最大数）・`sample_bits`（サンプルのビット数。MIDI は null）・`channels_request`（指定なしは null）・`summary`（バナーの要約行）・`path`（絶対パス）・`repro`（`--seed` まで含む再現コマンド）。

---

## 9. 検査

### 9.1 構造検査（生成のたびに実行）

書き手と独立に実装したパーサで読み戻して検査する。ERROR があればファイルを書かない。

**MOD（`core/verify.verify`）**

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
| V10 | `order[0]` の pattern に BPM 設定（`Fxx`, xx ≥32）がある | ERROR |
| V11 | ループ境界の段差 ≤ max(2.0, 1.5 × ループ内最大の隣接差)（クリックの恐れ） | WARN |
| V12 | pattern 数 ≤ 64 | ERROR |
| V13 | 未使用のサンプル | INFO |
| V14 | note の無い無効果セルにサンプル番号 | WARN |
| V15 | 4ch の曲だけ: チャンネル音量を追跡し、左（ch1+ch4）・右（ch2+ch3）の同時合計が 120 を超える row | WARN |
| V16 | アルペジオが Period 表の上限を超える | ERROR |

- **S3M（`native_s3m.verify`）**: V01 構造・V02 マジック・V03 order・V04 サンプルヘッダ（音量・長さ・ループ・C2Spd の範囲）・V05 音域・V06/V07 番号・V08 音量とテンポ値・V10 `Txx`（≥32）・V17 サンプル長 ≤ 64000 byte・V18 C2Spd が 1000 Hz 未満（WARN）。
- **XM（`native_xm.verify`）**: V01 宣言された各サイズの積算との比較・V02〜V08（V05 は note 1..96 とキーオフ 97、V08 は音量列が 0x10..0x50）・V10 `Fxx`（≥32）・V11 ループ境界・V12 pattern 数・V13 未使用の楽器・V19 エンベロープ（点数・tick の単調増加・値の範囲）・V20 チャンネル数と row 数の範囲。
- **IT（`native_it.verify`）**: V01〜V08・V10 `Txx`・V18 C5Speed が 1000 Hz 未満（WARN）・V19 エンベロープ・V21 楽器ヘッダ（楽器モードのフラグ・キーボード表・NNA）・V22 pattern の row 数が 32..200 の外。
- **MIDI（`native_midi.verify`）**: V01 読めるか・V02 ヘッダ（format 1／PPQ 480）・V03 End of Track・V04 note on/off の対応・V05 テンポ設定・V06 ノート番号と velocity・V07 メロディのチャンネルの program 指定・V08 ドラムの音域（27..87）・V09 同時発音数が 24 を超える（WARN）。
- 読み戻しは writer とは独立に実装したパーサ（`verify.parse_mod`・`parse_xm`、`s3m.parse_s3m`、`it.parse_it`、`midi.parse_midi`）で行う。
- **V15 は目安**: チャンネル音量の単純合計で、再生エンジンのミキシング（チャンネル数に応じたヘッドルーム、サンプル波形の振幅）を考えない。Amiga の 4ch 前提の目安で、多チャンネルでは割れなくても超えるため 6ch・8ch の曲は検査しない（編成を選ぶジャンルの 4ch の編成は検査の対象で、全て通る）。音割れは全ジャンルを実測で検査する（§9.2）。

### 9.2 実プレイヤーによる検査（`tests/realplayer/`）

自作の writer と parser が同じ誤解を共有していると、読み戻しの検査は常に通ってしまう（実際に XM の `header_size` と音高で起きた。[DESIGN_HISTORY.md](DESIGN_HISTORY.md) §8）。そのため形式の正しさは第三者の実装（ffmpeg 内蔵の libopenmpt）で再生して確かめる。ffmpeg が無い環境では skip。時間がかかる（全体で 30 分前後）ので `slow` の印を付けてあり、普段は `-m "not slow"` で省略できる（マージ前は全部流す）。

| 検査 | 内容 |
|:---|:---|
| 音高（I4） | 全プリセットのうち基本周波数が一意に測れる持続音（34音色）について、音域の両端と中央の音を MOD・S3M・XM・IT で鳴らし、FFT（放物線補間）で測った基本周波数が §3.1 の基準（平均律）と一致する。許容は XM・IT 7 セント、MOD 9、S3M 12（§7.4）。MOD の finetune の変種が 12.5 セント刻みで音高を動かすことも測る |
| 形式間の等価性 | 同じ曲を MOD と XM/S3M/IT で再生し、曲長（±1%＋0.1 秒）・RMS 包絡の相関（>0.75）が一致。ビブラートの深さが形式で一致（同じ実音で比べる）。orchestral は XM を基準に MOD/S3M/IT を比較。曲全体の零交差の平均周波数は、形式でサンプルの高域が違うので比べない（音高は I4） |
| テンポと長さ（I5） | 全51ジャンルの MOD（最大の予算）と IT を libopenmpt で鳴らした長さが Score の時間軸（テンポの変化〔free-jazz〕・スウィングを含む）と一致する（±0.5%＋0.2 秒） |
| `Glide`（§7.6） | MOD・S3M・XM・IT で 7・12 半音のグライドが、`tracker._glide_param` が見込んだ step 数で届く（97% 到達の時刻が ±0.12 秒） |
| 音割れ（I6） | 全51ジャンル × MOD/XM/S3M/IT × 3 seed（1 つは音量の測定に使っていない seed）、および編成を選ぶジャンルの全編成 × MOD/XM の最大振幅 < 0 dBFS（float のまま・リサンプルなしで読む）。全ジャンルの MOD・IT は −0.5 dBFS 以下。振幅最大の矩形波に差し替えた曲では失敗すること（検査が見逃さないこと）も確認。S3M/IT は底上げが効いていること（最大振幅 > −8 dBFS）も見る |
| MP3 | 作れること、デコードした長さ（±0.5 秒）・ステレオ・無音でないこと・音割れ率 < 0.1%。静かなジャンルも平均が目標（−14 dBFS）の 4 dB 以内に上がり、0 dBFS を超えないこと |

### 9.3 目で・耳で確かめること（自動化の対象外）

OpenMPT 等で開けること、ループ境界のクリック、スウィングやサイドチェインの聴感、orchestral の定位。試聴で詰める数値は §11。§11 の試聴項目を確かめる曲は、リポジトリ直下の `listen_samples.py`（Windows は `listen_samples.bat` でも可）でまとめて作れる（§11）。

---

## 10. テスト

### 10.1 不変条件（テストで常に保証する）

| ID | 内容 | テストの置き場所 |
|:---|:---|:---|
| I1 | **骨格の不変**: 同じ genre・seed・tempo なら、どの形式の features で作っても、Score から奏法（`arts`）を除いたものが一致する | `tests/framework/test_ported_genres_all.py`（全ジャンル） |
| I2 | **決定性**: 同じ入力から同じバイト列 | 同上 |
| I3 | **全ジャンル × 全予算 × 全形式で生成でき、検査に ERROR が無い**: MOD は `mod_channels` の全キー、S3M・XM・IT は既定の予算と、`--channels` の上限をそのジャンルの `mod_channels` の最小値にした場合、MIDI は既定 | 同上（ffmpeg 不要） |
| I4 | **実音の一致**（§9.2） | `tests/realplayer/test_pitch.py` |
| I5 | **テンポと長さ**（§9.2） | `tests/realplayer/test_ported_genres_real_player.py` |
| I6 | **音割れなし**（§9.2） | 同上・`test_clipping.py` |
| I7 | **高解像度の描画の同等性**（§4.8） | `tests/unit/test_synth_hires.py` |
| I8 | **依存の規則**: `genres/*.py` が `core` の形式系（writer・s3m・it・midi・render・verify・level）と `framework.realize` を import しない | `tests/framework/test_layering.py`（ast で検査） |
| I9 | **宣言の検査**: 全楽器に `gm`、`Kit.groups` が kit の全楽器を覆う、`mod_channels` のキー ⊂ {4, 6, 8}、`min_channels` ∈ {0} ∪ キー ∪ {それより大きい値}、`depends` に循環が無い | `Genre` のクラス定義時（`test_genre_declaration.py`） |

### 10.2 層ごと

| 層 | 場所 | 主な検査 |
|:---|:---|:---|
| 単体 | `tests/unit/` | pitch・dsp・synth（高解像度）・model（Cell の直列化、範囲検査）・writer（MOD のレイアウト・原子的書込）・verify（ミューテーションで各コードが出る）・harmony・composer・groove・engine（build・generate・検査器との接続・`--channels` の検証）・tempo（`--tempo` の確定、同じ seed・別テンポ＝同じ曲、全ジャンル × `tempo_range` の全域で生成できる）・registry（自動検出・登録時の検査）・native_writers（S3M・XM・IT の書き出しと検査器）・native_level |
| フレームワーク | `tests/framework/` | 宣言・Score・部品の値（`BassLine`・`Comp`・`Groove` が耳で調整した値どおり）・ladder の単体テスト・lane の割当・セルの衝突の規則・`Glide` の速さと鳴り終わりの判定・MIDI（`tests/framework/realize/`）。**全51ジャンルの共通検査**（`test_ported_genres_all.py`: I1〜I3・全パートが鳴る・編成の対応表〔`port_layouts.py`〕・畳んだ打楽器の優先度・区間で鳴らさないパートに音が無い・`--tempo`・seed による編成の選択と範囲外の拒否・classical の 3/4・swing の Speed が全 row）と、**個別実装の12ジャンルの固有の性質**（`test_ported_genres_c.py`: 位相ずれ・ルバート・中立音程・usul・無音の位置・次の和音へのウォーキング・変拍子・グライドとロール・サイドチェイン） |
| 結合 | `tests/integration/` | CLI（終了コード、引数なし、random、`-e`、`--version`、出力先、各形式、mp3 の ffmpeg 不足、`--json`・`--output-dir`、`--channels` の形式ごとの意味）。全ジャンルの MIDI（mido で独立にパース）。試聴用の曲の一覧（`listen_samples.py` がジャンルの編成の宣言とずれていない）。GUI の `bridge`（本物の CLI を子プロセスで動かす）と画面の通し確認（画面が出せない環境では skip） |
| 回帰 | `tests/regression/` | **出力の基準**: 全ジャンル × 全形式（MOD は宣言された全予算、MP3 は除く）× seed 1 の出力の SHA-256 を `golden.json` に保存し、一致を検査する。意図して出力を変えたとき（音色・生成規則・Realizer の変更）は `python tools/update_golden.py [ジャンル id …]` で更新し、そのコミットで理由を書く。浮動小数点を使う合成なので、別の OS・Python の版では値が違うことがある |
| 実プレイヤー | `tests/realplayer/` | §9.2 |

- 実行: `python -m pytest -q`（ffmpeg が無ければ実プレイヤー検査は skip。実プレイヤー検査を含むと全体で 30 分前後かかる）。普段は `python -m pytest -q -m "not slow"` で実プレイヤー検査を省略し、マージ前に全部流す。
- 新しいジャンルは、全形式・複数 seed で検査が通ること、実プレイヤーの音割れ検査に通ること、全楽器に `gm` があること、1ファイル1ジャンルであることがテストで自動的に確かめられる。

### 10.3 変更の手引き（どこを直すか）

| 変更 | 直す場所 |
|:---|:---|
| ジャンルを足す・音を変える | `genres/<id>.py` だけ（宣言とジェネレータ）。測定値（`tools/calibrate_levels.py`）と golden（`tools/update_golden.py`）を更新 |
| 新しい形式の能力の表（行数・サンプルの上限など） | `framework/target.py` |
| 新しい奏法を足す | `framework/score.py`（型）→ `framework/realize/encode.py`（形式ごとの表現）→ `tracker.py`・`midi.py`（セル化・変換）→ 検査器 |
| 形式の書き出しの仕様 | `core/native_s3m.py`・`native_xm.py`・`native_it.py`・`writer.py`（MOD）と、対応する検査器 |
| 音色の解像度・サンプルの計画 | `core/synth.py`（描画）・`framework/realize/samples.py`（計画） |
| チャンネルの収め方（予算・ladder・パン） | `framework/realize/lanes.py` |
| ジェネレータの部品の型 | `framework/gens/`（値は耳で調整済みなので、変えるときは試聴で確かめる） |

---

## 11. 未確定・試聴で調整する項目と将来課題

「試聴で調整」の項目（下表の状態が「試聴で再調整可」「同上」「試聴で調整」のもの）は、リポジトリ直下の **`listen_samples.py`**（`python listen_samples.py`。Windows は **`listen_samples.bat`** のダブルクリックでも可）で確かめる曲をまとめて作れる。項目・見出し・曲の一覧は `listen_samples.py` の `ITEMS` にあり、バッチは Python を起動するだけ（ASCII だけで書く。§12 と同じ）。

- 出力先は `output\listen\<番号_項目>\<ジャンル>_<シード>.<拡張子>`（`output\` は git の管理外）。シードは 101・202・303 に固定しているので、何度作っても同じ曲になる（調整の前後で同じ曲を聴き比べられる）。
- 項目ごとに3例（racing-breaks はリズムの系統ごとに1例になるよう、シードを 101・102・113 にしている）。複数のジャンルにまたがる項目（第３段階の35ジャンルの釣り合い、新しい3ジャンル）はジャンルごとに3例、編成はジャンルごとに3例 × 選べる編成（同じシードの曲をチャンネル数だけ変えて `<ジャンル>_<シード>_<数>ch` で出す）。全 375 曲。
- 環境変数 `FMT`（`mod`〜`mp3`。既定 `mod`）で形式を、`PY`（バッチだけ。既定 `python`）で Python を変えられる。曲は同じプロセスで `cli.main` を呼んで作る。最後に成功・失敗の件数を出す（失敗があれば終了コード 1）。
- 下表に試聴の項目を足したら、`listen_samples.py` の `ITEMS` にも足す。

| 項目 | 現在の値 | 状態 |
|:---|:---|:---|
| swing-jazz のスウィング比 | 14:10（1.4:1） | 試聴で再調整可 |
| trap のロール確率・808 グライド速度 | 0.6、`Glide(steps=1)`（1 step で届く速さ） | 同上 |
| future-bass のダッキング | bass 0.25/3、chord 0.35/4 | 同上 |
| maqam の旋律の跳躍確率 | 0.15 | 同上。Rast 以外のマカーム（Bayati 等）は未実装 |
| minimalism の音型 | 固定の4音型 | 同上 |
| free-jazz の密度 | bass 0.18、piano 0.25、perc 0.08、sax（climax）0.12 | 同上 |
| orchestral のボイシング・音量変化 | 度数の固定割当、セクション単位の音量 | 同上。measure 内のクレッシェンドは未実装 |
| prog-rock の lead のビブラート | なし | 必要なら march 相当のヘルパーを足す |
| nostalgic の pad の −17.6 セント | K=32/L=1024 のまま | 直すなら K=6/L=190（+0.49 セント）。出力が変わるので golden の更新とセット |
| MIDI のグライド・GM 音源での聴感 | `Glide` はピッチベンド（直前の音が鳴っているときだけ）。この環境に GM 音源が無く、聴感の確認は未実施 | 試聴で調整 |
| maqam の中立音程（350・1050 セント） | 小数の音高（MOD は 12.5 セント刻みの finetune の変種） | 試聴で確認（旧版は finetune の刻みを誤っていて最大 20 セント以上ずれていた） |
| swing-jazz のウォーキングベースの終止 | 次の和音の根音へ向かう | 試聴で確認 |
| suspense の無音の位置・drone の鳴らし直し（shock の最初の小節） | 区間が音を持ち越さないので区間の頭で鳴らし直す | 試聴で確認 |
| 全形式の実音の許容 | XM・IT 7 セント、MOD 9、S3M 12（§7.4） | 形式固有の誤差。ファイル側では直せない |
| XM・MOD の音量が上がらない（§7.9） | 同上 | 同上 |
| MOD/XM の音量（§7.9。最大の音量が 64 のジャンルは上がらない） | 音量の値の一律の倍率だけ | 大きくするなら、音量の値を圧縮する（大きい音を 64 で頭打ちにし小さい音を上げる）か、OpenMPT の拡張（サンプルのプリアンプ）を書く。前者はジャンルの音量の設計を変え、後者は OpenMPT 系のプレイヤーでしか効かない |
| 第３段階の35ジャンルの音量・音色の釣り合い | 構造検査と実プレイヤーの音割れ検査に通る初期値（耳での調整は未実施） | 試聴で調整 |
| folk の前打音の確率、neo-soul の「よれ」の確率 | 0.3、スネア 0.35・ハット 0.25 | 同上 |
| jrpg のゼクエンツ | 音域の上端の音は上げずにそのまま | 動機ごとオクターブ下げるなどは将来課題 |
| 曲ごとの編成（4ch で省くパート、8ch で足す任意パートの音色・音量）、S3M・XM・IT・MIDI で全パートが入ったときの釣り合い（和音の声部の音量 `1/√k` など） | §6.16 の「編成」（省くパートはジャンルごとに決めた初期値） | 試聴で調整 |
| 形式の能力の opt-in（リリースのエンベロープ・IT のフィルタ・ステレオの重ね・12ch 以上の追加パート） | どのジャンルも宣言していない（`Instrument.release_s`・`Double`・`Part.min_channels` > 8 は部品として使える） | 試聴で基準と比べてから、ジャンルごとに足す |
| gamelan・chiptune・industrial の音量・音色（ガムランの音律と装飾の密度、チップチューンのアルペジオとジャンプ音、インダストリアルの歪み） | §6.17 の初期値 | 同上 |
| racing-breaks の3系統のドラム・ベースの型、低音の量（キックの掃引・サブベースの音量）、エレピの揺れ | §6.18 の初期値（120 Hz 未満の割合だけ解析値に合わせた） | 同上 |
| 気分ジャンルの「相性」（晴れ・夜など） | §6.16 に記録するだけ | 天気・時間帯から選ぶ機能を作るときに属性（例: `affinity`）を足す |
| 外部ジャンルのプラグイン読込、WAV レンダラ、IT の NNA（本設計では使わない） | なし | 要件外 |

---

## 12. GUI（`modweaver_gui.pyw`・`mod_weaver/gui/`）

CLI の機能を画面から使うためのもの。起動は `modweaver_gui.pyw` か `python -m mod_weaver.gui`。Windows では `modweaver_gui.bat` のダブルクリック（`start "" pythonw modweaver_gui.pyw`。`.pyw` にアプリが関連付けられていない環境でも動く。Python は環境変数 `PYW` で変えられる）。リポジトリのバッチはすべて ASCII だけで書く（cmd は UTF-8 の複数バイトの行を読み違える）。`--lang=ja` / `--lang=en` で表示言語を指定でき、省略時は OS のロケール（日本語なら ja、それ以外は en）。画面は tkinter / ttk（NFR-1）。

### 12.1 方針

- **CLI を子プロセスで呼ぶ**。GUI は `mod_weaver` のほかのモジュールを import しない。生成が長引いても画面が固まらず、中止（子プロセスを kill）もできる。
- **CLI で選べるものは起動時に CLI から受け取る**（`--list-genres --json`。§8.8）。ジャンルの数・名前・説明・区分、形式、テンポの上下限、形式ごとのチャンネル数の意味（`formats[].channels`）、ジャンルごとの MOD のチャンネル数、mp3 が使えるかを GUI に書き込まない。ジャンルを足しても GUI は変えなくてよい。
- **結果は `--json` で受け取る**。バナーの文章は読み取らない。
- 見た目は各 OS の ttk 標準テーマに任せる（Linux だけ `clam`）。色やフォントを固定しない。Windows では起動時に高 DPI 対応を宣言する（`SetProcessDpiAwareness`。文字がぼやけないように）。
- GUI の表示言語は GUI の文言だけを切り替え、CLI には `-e` を渡さない（JSON は言語で変わらず、ジャンルの説明はカタログに日英とも入っている）。

### 12.2 構成

| モジュール | 役割 |
|:---|:---|
| `gui/bridge.py` | tkinter を使わない部分。カタログ・結果のデータ型、画面の設定 → 引数（`build_args`）、入力の検査、子プロセスの起動（`Job`。別スレッドで待ち、中止できる）、関連付けアプリで開く（Windows `os.startfile`、macOS `open`、Linux `xdg-open`）・フォルダで表示（Windows `explorer /select,`、macOS `open -R` でファイルを選んだ状態、Linux は `xdg-open` でフォルダ）。テストは画面なしで動く |
| `gui/app.py` | 画面。設定は tk の変数、作った曲は一覧で持ち、言語の切替やカタログの読込後は画面を作り直す。別スレッドの結果はキュー経由で画面スレッドへ渡す |
| `gui/texts.py` | 日英の文言表（`cli.MESSAGES` と同じ考え方）。ジャンルの文言は持たない |

子プロセスは `python modweaver.py …`（再現コマンドが `python modweaver.py` になる）。`PYTHONUTF8=1` で起動し（stderr の文字化け対策）、Windows ではコンソール窓を出さない。GUI が pythonw.exe で動いているときは隣の python.exe で CLI を起動する。

### 12.3 画面

- 左: ジャンル一覧（区分ごとの木。検索欄は id・表示名・別名・説明の日英を対象にし、区分でも絞れる）と「ジャンルもランダムに選ぶ」（`--genre random`。候補はテンポ・チャンネル数の指定に合うジャンルだけになる。§8.3）。
- 右上: 選んだジャンルの表示名・区分・別名・ふだんのテンポ（`tempo_choices` の最小〜最大と代表値）・指定できるテンポ（全域でないジャンルだけ）・MOD で選べるチャンネル数・説明。
- 設定: テンポ（ジャンルに任せる／固定／範囲。ユーザーがジャンルを選ぶと、固定の初期値を代表値＝`tempo_choices` の中央（偶数個なら下側）に、範囲の初期値を `tempo_choices` の最小〜最大にする。画面の作り直しや「設定に読み込む」では入力を変えない。入力欄の上下限と入力の検査はジャンルの `tempo_range`（ランダムジャンルなら CLI の全域））、チャンネル数（**形式で入力欄が変わる**: MOD はジャンルが選べる数のボタン〔選べない数は押せない。選んでいた数が使えないジャンルに替えたら「任せる」に戻す〕、XM・S3M・IT・MP3 は上限の入力欄〔1〜形式の上限〕、MIDI は指定不可。形式を替えると作り直し、合わない指定は「任せる」に戻す）、シード（毎回ランダム／固定）、形式（mp3 が使えなければ注意を出す）、保存フォルダ（`--output-dir`。既定はリポジトリの `output`）。ファイル名は CLI の既定（`<genre>_<seed>.<拡張子>`）に任せる。
- 生成（Ctrl+Enter・F5）・中止・状態表示。入力がおかしければ CLI を呼ばずに知らせる。CLI が失敗したら終了コードごとの説明と stderr の最終行を出す。起動時のジャンル一覧の読み込みに失敗したら理由を出し、生成は押せないままにする。
- 「作った曲」: その回に作った曲の一覧（新しい順。ランダムに選ばれたジャンルは名前に ` *` を付ける）。再生（OS の関連付け。関連付けが無ければ OpenMPT などの案内）、フォルダで表示、再現コマンドのコピー、**別の形式でも書き出す**（同じ seed で、指定があったテンポ・チャンネル数だけ渡す＝同じ曲。チャンネル数は形式で意味が違うので、元の形式と同じ意味の形式〔上限どうしなど〕にだけ引き継ぎ、MIDI など指定できない形式へは渡さない）、**設定に読み込む**（seed を固定してテンポや形式だけ変える等）。選んだ曲の要約行・パス・再現コマンドを下に出す。
- 「ログ」: 実行した引数、stderr（警告・想定外の例外のスタックトレース）、終了コードと所要時間。
- メニュー: ファイル（保存フォルダを開く・終了）、表示（言語: 日本語／English）、ヘルプ（CLI の使い方＝`--help` の出力を別窓で表示、ModWeaver について＝カタログの版と GitHub URL）。

### 12.4 将来課題

- 動作を確かめたのは Windows 11（Python 3.12。画面・pythonw 起動・mp3 書き出し）と Linux（WSLg、Python 3.10。自動テストの画面の通し確認）。macOS の実機では未確認。

- 設定の保存（保存フォルダ・言語・最後の設定）、複数曲の一括生成、アプリ内での再生（標準ライブラリだけでは MOD 等を鳴らせない。現状は OS の関連付けアプリで開く）。
