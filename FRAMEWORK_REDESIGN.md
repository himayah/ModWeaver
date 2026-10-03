# ModWeaver フレームワーク再設計書（レビュー用）

| 項目 | 内容 |
|:---|:---|
| 対象 | ModWeaver 1.1.0 の作曲フレームワーク（`mod_weaver/profiles/`・`mod_weaver/genres/`・`mod_weaver/core/` の形式層）と全51ジャンル |
| 状態 | **設計確定版（未実装・実装担当者への引き継ぎ用）**。2026-10-01 作成、同日に第三者レビュー（16項目）を反映（§19） |
| 読者 | ① この設計をレビューする人（AI を含む）② 事前知識なしで実装を担当する人 |
| 正とする文書 | 現行の仕様は [DESIGN.md](DESIGN.md)、経緯は [DESIGN_HISTORY.md](DESIGN_HISTORY.md)。本書は**変更点**と**新しい仕組み**を書く。各ジャンルの音楽的な内容（調・進行・リズム・構成・音色）は DESIGN.md §6 を正とし、本書では移し替えの方法だけを書く |
| 実装後の扱い | 実装が終わったら本書の内容を DESIGN.md に統合し、決定の経緯を DESIGN_HISTORY.md に移して本書は削除する（2026-09-24 の統合と同じ運用） |

---

## 0. 読み方

- **レビューする人**: §1（目的と決定事項）→ §3（全体構成）→ §5〜§6（中核のデータとジャンルの書き方）→ §9（Realizer）→ §18（リスクと未確定事項）を読めば、設計の要点と判断の根拠が分かる。§18 に「特に見てほしい点」を挙げた。
- 第三者レビューの指摘と反映は §19。本文はすべて反映済みの内容になっている。
- **実装する人**: §2（現状）で今のコードの形をつかみ、§16（実装計画）の順に作業する。各フェーズで参照する節は §16 に書いた。迷ったら §17（変更の手引き）の原則に戻る。
- 本書のコード片は**インターフェースの仕様**（型・フィールド・意味）であり、そのまま貼れる完成コードではない。名前は本書のものを使うこと（レビューと実装の対応を取りやすくするため）。
- 「要実測」と書いた事項は、仕様書や記憶では確定できず、実装時に実プレイヤー（libopenmpt）で測って決める。測った結果は DESIGN.md に書く。

### 0.1 用語

| 用語 | 意味 |
|:---|:---|
| 形式（format） | `--format` の値。`mod`・`s3m`・`xm`・`it`・`midi`・`mp3` |
| Target | 形式ごとの能力表（チャンネル数・サンプルの解像度・音域・使えるエフェクトなど）。§4 |
| Score | 形式に依存しない楽譜。パートごとの音符（`NoteEvent`）の列と、和声・拍子・テンポの時間軸。§5 |
| Realizer | Score を形式の表現に変える層。トラッカー用（`TrackerRealizer`。MOD/S3M/XM/IT）と MIDI 用（`MidiRealizer`）。§9・§11 |
| Genre | 1ジャンルを表すクラス。宣言とジェネレータで Score を作る。§6 |
| Part（パート） | 役割を持つ声部（ドラム・ベース・和音・旋律・パッド…）。ジャンルが宣言する |
| Generator（ジェネレータ） | 1パートの音符を作るオブジェクト。§6.5・§7 |
| step | 区間の格子の1マス。既定は16分音符。トラッカーの row に当たる |
| tick | 時間の最小単位。**1拍＝24 tick**（現行のトラッカーの約束と同じ）。1 step の tick 数は `24 / steps_per_beat` |
| lane | 1つのチャンネルに載る単音の流れ。パートは1つ以上の lane を持つ（和音を声部に開くと声部ごとに lane、打楽器は楽器ごとに lane） |
| 予算（budget） | その曲で使えるチャンネル数。形式・`--channels`・ジャンルの宣言で決まる。§9.2 |
| 書かれた音高（written pitch） | ジャンルが書く音高。現行の logical note と同じ番号（0＝C2＝65.41 Hz）。小数部はセント/100（微分音） |
| 実音（sounding pitch） | 実際に聞こえる高さ。現行の MOD と同じく、楽器ごとに書かれた音高からずれる（§8.1） |
| 骨格 | 調・進行・各パートの音符の時刻と高さ。形式に依存しない部分（不変条件 I1、§13.1） |

---

## 1. 目的と決定事項

### 1.1 目的

1. **選んだ出力形式の規格を最大限生かした曲を作る。** 今は全形式で MOD の最小構成（8-bit・約 8.3 kHz の合成・36音・31サンプル・1セル1エフェクト・4〜8ch）に合わせて作曲し、それを各形式に変換している。これをやめ、形式を最初に決めて、その形式の能力（チャンネル数・サンプルの解像度・音域・ボリューム列・エンベロープ・MIDI の同時発音など）に合わせて作曲する。
2. **今後の仕様変更のときに、どこをどう直せばよいかの見通しを立てやすくする。** ジャンルは「何をどう鳴らすか」だけを書き、チャンネル番号・pattern・row・エフェクト番号・形式の差はフレームワークが受け持つ。変更の種類ごとに直す場所が1か所に決まるようにする（§17）。

### 1.2 決定事項（ユーザー確認済み。すべて推奨案）

| ID | 決定 | 由来・理由 |
|:---|:---|:---|
| D1 | 出力形式を作曲の前に決める。形式間で同じ曲になること・変換できることは要件にしない | 目的1。FR-2「同じ genre・seed・format・tempo から同じ出力」は維持（format が鍵に入っているため） |
| D2 | ただし**骨格は形式に依存しない**（同じ seed なら、どの形式でも調・進行・各パートの音符の時刻と高さが同じ）。形式で変わるのは、どのパートを入れるか（予算）・和音の鳴らし方・奏法の表現・音色の解像度だけ | 聴き比べと試聴の再現に便利。テストで保証する（I1） |
| D3 | **実音は全形式で現行の MOD と同じ高さ**にする（正確には、`sounding_hz` から求めた平均律の高さ。§8.1）。上げるのは解像度だけ | 全音色は「実音が書かれた音高より上に出る」現行の状態で耳で調整されている。実音を書かれた音高に合わせると全楽器が1オクターブ下がる（§8.1） |
| D4 | MOD のチャンネル数は現状どおり 4／6／8 から選ぶ（`--channels` か seed）。奇数は使わない | 互換性と既存の編成の判断を保つ |
| D5 | S3M のサンプルは 8-bit のまま高レートにする。XM・IT は 16-bit・高レート | 本家 ST3 は 16-bit サンプルを再生できない |
| D6 | XM・IT・S3M では `--channels N` を「予算の上限」とする。MIDI では `--channels` は引数エラー | §14.1 |
| D7 | MP3 は IT（能力の上限）を中継し、320 kbps で符号化する | §12 |
| D8 | MIDI は Score から直接作る（`MidiRealizer`）。和音は本物の同時発音、グライドはピッチベンド | 現行はトラッカーの曲からの変換で、和音サンプルが1音になる等の損がある |
| D9 | **既存の出力との互換は求めない**（MOD のバイト一致も求めない）。nostalgic の旧挙動（DESIGN.md §6.1 の Q1〜Q7、乱数の消費順）も保たない | 互換を保つと、古い挙動を再現する仕掛けが要り、作り直しより高くつく |
| D10 | 移行は**グループ単位で短期間に切り替える**（新旧の枠組みを長く並行させない）。最後に旧コードを削除する | 並行期間が長いと2系統の保守とテストが続く |
| D11 | ジャンル固有の文法はジャンルのファイル内のジェネレータとして書く。部品集（§7）に入れるのは2つ以上のジャンルが使うものだけ | 汎用化の設計に時間をかけない。「知覚寄りのファクトリを core に置かない」（DESIGN.md §4.5）と同じ考え方 |
| D12 | 音楽の値は**現行と同じ単位**で書く（音量 0..64、ビブラート・アルペジオは MOD の param、時刻は step）。形式ごとの換算は Realizer が行う | 耳で調整済みの値をそのまま写せる。移植の誤りを減らす |
| D13 | XM・IT のスライドの設定は現行の検証済みのものを使う（XM は Amiga 周波数表、IT は Amiga スライド＋Old Effects） | グライドとビブラートの深さが実プレイヤーで MOD と一致することを確認済み（DESIGN.md §7.3・§7.5） |
| D14 | 形式の能力は2段階で使う。**自動**（全ジャンルに効く。宣言の変更不要）: 高解像度の音色、和音の声部化、打楽器の分離、予算に応じた任意パートの追加、専用の制御チャンネル。**ジャンルの opt-in**（宣言を足したジャンルだけ）: リリースのエンベロープ、IT のフィルタ、ステレオの重ね、大きな予算でだけ鳴らすパート | 自動の部分で耳の調整が崩れる範囲を限定する。opt-in の候補は §15.5 |

### 1.3 要件の変更（DESIGN.md §1.2 に対して）

| ID | 変更 |
|:---|:---|
| FR-2 | 変更なし。加えて「同じ genre・seed・tempo なら、形式が違っても骨格は同じ」（D2） |
| FR-3 | 変更なし（形式の一覧は同じ） |
| FR-4b | `--channels` の意味を形式ごとに変える（D4・D6）。MOD は 4・6・8、S3M/XM/IT は上限、MIDI は不可 |
| FR-5 | 「ジャンルは `mod_weaver/genres/` に1ファイル置くだけで追加でき、core・engine・cli の変更は不要」を維持。ジャンルは新しい基底クラス `Genre` を継承する |
| FR-9 | `--json` の一覧に、形式ごとのチャンネル数の選択肢を加える（§14.2） |
| 新 FR-11 | 形式の能力を生かす（D14 の自動の部分）。どの形式でも、形式の制約に違反するファイルは書かない（FR-6 と同じ） |
| NFR-3 | 1曲の生成は数秒以内を維持（目安: S3M・XM・IT で 2 秒以内）。高解像度の音色の合成で遅くなるので、音色の合成結果をプロセス内でキャッシュし、F1 の実測で目安を超えるならディスクにもキャッシュする（§8.6） |

---

## 2. 現状（実装担当者向けの要約）

### 2.1 リポジトリの形

```text
modweaver.py, mod_weaver/__main__.py   起動（cli.main へ）
mod_weaver/cli.py                      引数・表示・--json（DESIGN.md §8）
mod_weaver/engine.py                   作曲の実行・テンポ・検査・書込
mod_weaver/profiles/base.py            GenreProfile（現行の基底。廃止予定）
mod_weaver/profiles/band_common.py     BandProfile（39ジャンルの骨格。899行。廃止予定）
mod_weaver/profiles/suspense_common.py suspense 2ジャンルの共通（廃止予定）
mod_weaver/profiles/registry.py        ジャンルの自動検出（残す）
mod_weaver/profiles/levels.py          ジャンル×形式の最大振幅の実測値（作り直す）
mod_weaver/genres/*.py                 51ジャンル（すべて作り直す）
mod_weaver/core/                       pitch, dsp, synth, synth_presets/, harmony, composer, model, ...
                                       writer(MOD/XM), s3m, it, midi, timeline, render(MP3), level, verify, effects
mod_weaver/gui/                        GUI（CLI を子プロセスで呼ぶ。--json だけで情報を受け取る）
tests/                                 unit / profiles / integration / realplayer / regression
tools/calibrate_levels.py              音量の実測
listen_samples.py                      試聴用の曲をまとめて作る
```

### 2.2 今の生成の流れ

`engine.compose_song` が、ジャンルの `plan()` → pattern ごとに `begin_pattern` → measure ごとに `compose_measure(mctx, state, rng, buf)`（ジャンルが `buf.put(row, ch, inst.cell(...))` でセルを書く）→ `finalize_pattern` → `arrange`（論理チャンネルを 4/6/8 の物理チャンネルに畳む）→ 後処理（スウィング・サイドチェイン）→ テンポの挿入、の順に呼ぶ。できた `Song`（MOD のセルの表現）を、各形式のシリアライザが変換して書く。

### 2.3 今の構造の問題（作り直す理由）

| 問題 | 例 |
|:---|:---|
| ジャンルがトラッカーの細部を知っている | `buf.put(row, ch, inst.cell(effect=0x4, ...))` が36ファイル・207か所。チャンネル番号・`shift` を前提にした音域・64 row の pattern・row 0 の空き確保・D00 の空き確保がジャンルの責任 |
| 骨格が3系統 | `BandProfile`（宣言で書く39ジャンル）、`GenreProfile` を直接書いた12ジャンル、`SuspenseBase` |
| 宣言から外れるとセル書きに落ちる | パートの処理（`compose_measure` を含む）を上書きしている BandProfile のジャンルが26。上書きしたとたんにチャンネル・row・エフェクト番号を直接書く |
| 編成がチャンネル基準 | `CHANNELS`・`ARRANGEMENTS`・`Fold` は「何チャンネルに畳むか」を書く。形式ごとに予算が違うと組合せが増えすぎる |
| 形式の能力を使えない | 全形式で MOD の制約（§1.1）。S3M/IT へ変換できない MOD のエフェクト（トレモロ）も使えない |

### 2.4 残すもの・作り直すもの・捨てるもの

| 区分 | 対象 |
|:---|:---|
| **そのまま残す** | `core/pitch.py`（音高・スケール・`MicroScale`）、`core/harmony.py`（`voice()`・`Registers`）、`core/composer.py` の `MelodyGenerator`・`RhythmMotif`・`ScaleRules`（出力を `NoteEvent` に変えるだけ）、`core/synth_presets/`（136個の Patch。値は変えない）、`profiles/registry.py`、`errors.py`、CLI・GUI の大部分、実プレイヤー検査の仕組み（`tests/realplayer/`）、`tools/calibrate_levels.py`（呼び出し方だけ直す） |
| **拡張する** | `core/synth.py`・`core/dsp.py`（高解像度の描画。§8）、`core/model.py`（`SampleSpec` に解像度の情報を足す）、`core/writer.py`・`s3m.py`・`it.py`（16-bit・楽器・ボリューム列・エンベロープ。§10）、`core/verify.py` ほか検査器、`core/level.py`、`core/render.py`（IT 経由・320 kbps）、`core/midi.py`（Score から作る。§11）、`engine.py`、`cli.py`（`--channels`・`--json`） |
| **新しく作る** | `mod_weaver/framework/`（Target・Score・Genre の基底・ジェネレータの部品集・Realizer。§3.2） |
| **作り直す** | `mod_weaver/genres/*.py`（51ジャンル） |
| **捨てる** | `profiles/base.py`、`profiles/band_common.py`、`profiles/suspense_common.py`、`profiles/nostalgic_samples.py`（音色は `synth_presets` へ）、`core/effects.py`（MOD→S3M/IT の変換表。形式ごとのエンコード表に置き換え）、`core/timeline.py`（Score の時間軸に置き換え。ただし検査用に MOD を tick 単位で解釈する機能は `verify` 側に残す）、`CellGrid` の優先度付き `put`・`insert_command` の仕組み（Realizer の内部に移す）、`tests/regression/`（旧出力との一致の検査） |

---

## 3. 新しい全体構成

### 3.1 層と流れ

```text
cli.main
 └─ engine.generate(genre, seed, out, fmt, tempo, channels)
     ├─ target = targets.resolve(fmt, channels, genre, seed)        # §4。予算もここで決める
     ├─ plan   = genre.plan(rng_plan)                               # 形式に依存しない
     ├─ score  = framework.compose(genre, plan, seed, target.features)   # Score（形式に依存しない骨格）
     │           └─ 区間ごと・パートごとに Generator を呼ぶ → genre.finalize_section
     ├─ realized = Realizer(target).realize(genre, score)           # §9（トラッカー）／§11（MIDI）
     │           ├─ 音色の計画と描画（§8）
     │           ├─ パートの選択・lane の割当・チャンネル化（§9.2〜9.4）
     │           ├─ セル化（奏法→エフェクト、音量、リリース、ミックス規則、row コマンド、pattern への詰め込み）
     │           └─ 音量の底上げ（§9.10）
     ├─ data   = writer[target.format](realized)                    # §10。形式のネイティブ表現を書くだけ
     ├─ issues = verifier[target.format](data, realized)            # ERROR ならファイルを書かない
     └─ write_file(out, data)
```

依存の規則:

- `framework` は `core` に依存する。`genres` は `framework` と `core` の音楽系（pitch・harmony・composer・synth・synth_presets）だけに依存し、**`core` の形式系（writer・s3m・it・midi・render・verify・level）を import しない**（テストで検査する）。
- `core` は `framework`・`genres` を import しない。
- Realizer はジャンルのクラスを知らない。宣言（`Instrument`・`Part`）と Score だけを受け取る。
- ジェネレータは Target を直接見ない。見てよいのは `ctx.features`（使える奏法の集合。§6.6）だけで、それも**奏法の付け外しにだけ**使い、乱数の消費や音符の時刻・高さを変えてはならない（不変条件 I1）。

### 3.2 モジュール

| モジュール | 役割 | 新規／既存 |
|:---|:---|:---|
| `framework/target.py` | `Target`・`Features`・形式ごとの能力表・予算の決定 | 新規 |
| `framework/score.py` | `NoteEvent`・`Articulation` 各種・`Automation`・`TempoEvent`・`SectionScore`・`Score` | 新規 |
| `framework/plan.py` | `SongPlan`・`SectionPlan`・`MeasurePlan` と既定の計画（宣言から作る） | 新規（現行 `BandProfile.plan`・`_pattern_plan` を一般化） |
| `framework/genre.py` | `Genre` 基底・宣言の型（`GenreMeta`・`Instrument`・`Harmony`・`Section`・`Meter`・`Swing`・`Part`・`Kit`・`Double`・`MixRule`）・宣言の検査 | 新規 |
| `framework/context.py` | `SectionCtx`・`MeasureCtx`（ジェネレータが使う文脈と、音符を書く API） | 新規 |
| `framework/compose.py` | Score を作る（区間・パートの順序、乱数、依存関係） | 新規 |
| `framework/gens/` | 部品集（§7）: `drums.py`（Groove）・`bass.py`・`comp.py`・`lead.py`・`pad.py`・`arp.py`・`fx.py`・`layer.py`・`echo.py`・`buildup.py` | 新規（現行 `band_common` の型を移す） |
| `framework/realize/samples.py` | 音色の計画（どのサンプルを作るか）と描画の呼び出し、キャッシュ | 新規 |
| `framework/realize/lanes.py` | パートの選択・lane・予算に収める手順（ladder）・チャンネル順・パン | 新規 |
| `framework/realize/tracker.py` | `TrackerRealizer`（セル化・row コマンド・pattern への詰め込み） | 新規（現行 `engine`・`band_common._post`・`mixer`・`groove`・`automation` の処理を集約） |
| `framework/realize/encode.py` | 奏法 → 形式ごとのエフェクト・ボリューム列（形式ごとの表） | 新規（`core/effects.py` を置き換え） |
| `framework/realize/midi.py` | `MidiRealizer` | 新規（`core/midi.py` の書き出し部は残して使う） |
| `core/model.py` | `Cell` を上位集合に拡張（§9.6）、`SampleSpec` に `bits`・`rate_hz` を追加、`GmVoice` を `core/midi.py` から移す（I8） | 既存を拡張 |
| `core/synth.py`・`core/dsp.py` | 高解像度の描画（§8） | 既存を拡張 |
| `core/writer.py`・`s3m.py`・`it.py`・`midi.py`・`render.py`・`verify.py`・`level.py` | 形式の書き出し・検査・音量（§10〜§12） | 既存を拡張 |
| `engine.py` | 上の流れを呼ぶだけの薄い層 | 書き直し |

---

## 4. Target（形式の能力表）

### 4.1 型

```python
@dataclass(frozen=True)
class SampleCaps:
    bits: int                  # 8 | 16
    target_rate: float         # 描画の目標再生レート（Hz）。MOD は 0（＝現行のまま。§8.2）
    max_bytes: int             # 1サンプルの最大バイト数
    max_samples: int           # サンプル（楽器）数の上限

@dataclass(frozen=True)
class Target:
    format: str                # "mod" | "s3m" | "xm" | "it" | "midi" | "mp3"
    kind: str                  # "tracker" | "midi"
    budget: int                # この曲で使えるチャンネル数（§9.2。MIDI は 16）
    sample: Optional[SampleCaps]   # MIDI は None
    note_range: tuple[int, int]    # 形式のノート番号で使える範囲（Realizer が書かれた音高から換算する）
    max_rows: int              # 1 pattern の最大 row 数
    max_patterns: int
    max_orders: int
    features: frozenset[str]   # 使える奏法・機能（§4.3）
```

`targets.resolve(fmt, channels_request, genre, seed) -> Target` が作る。`mp3` は `it` と同じ Target を作り、`format="mp3"` だけ変える（中継に使う。§12）。

### 4.2 形式ごとの値

| 項目 | MOD | S3M | XM | IT | MIDI |
|:---|:---|:---|:---|:---|:---|
| 予算 | 4／6／8（`Genre.mod_channels` の重みで seed から選ぶか `--channels`） | 16 | 32 | 64 | 16（MIDI チャンネル。ch 10 は打楽器） |
| サンプルのビット深度 | 8 | 8 | 16 | 16 | ― |
| 描画の目標レート | 現行のまま（§8.2） | 44100 Hz（ただし長さの上限で下げる） | 44100 Hz | 44100 Hz | ― |
| 1サンプルの上限 | 131070 byte | 64000 byte（本家 ST3 の上限） | 実質なし（書き出しでは 4 MiB を上限にする） | 同左 | ― |
| サンプル数の上限 | 31 | 99 | 128（1楽器1サンプル） | 99 | 128音色＋打楽器 |
| ノート範囲 | t＝0..35（Period 表の36音） | C-0..B-7（96音） | 1..96（C-0..B-7） | 0..119（C-0..B-9） | 0..127 |
| 1 pattern の row 数 | 64 固定（短い区間は `D00`） | 64 固定（同左） | 1..256 | 32..200（32未満にはできないので `C00` 相当で切る。§10.4） | ― |
| pattern 数／order 長 | 64／128 | 100／256 | 256／256 | 200／256 | ― |
| 音量の置き場所 | エフェクト `Cxx`（他のエフェクトと排他） | ボリューム列 | ボリューム列（**新**。現行は `Cxx`） | ボリューム列 | velocity・CC11 |
| パン | 固定（L R R L） | チャンネルパン（`S8x` で発音ごとも可） | ボリューム列 `Px`・サンプルパン | ボリューム列のパン・チャンネルパン・サンプルパン | CC10 |
| エンベロープ | なし | なし | 音量・パン | 音量・パン・フィルタ（またはピッチ） | ― |
| フィルタ | なし | なし | なし | 共鳴フィルタ（`Zxx`・楽器の初期値・フィルタエンベロープ） | CC74（音源次第） |
| 新しい発音で前の音を残す | 不可 | 不可 | 不可 | NNA（本設計では使わない。§18.2） | 同時発音 |

値の出典: ProTracker・ST3・FT2・IT2.14 の仕様（OpenMPT のドキュメント）と現行の実装（`core/s3m.py`・`it.py`・`writer.py` の定数）。**XM・IT の 16-bit サンプル、XM のボリューム列、IT の楽器モードとエンベロープ、拡張した音域の音高は、実装時に実プレイヤーで要実測**（§13.4）。

### 4.3 `features`（ジェネレータが見てよい唯一の形式情報）

| 名前 | 意味 | MOD | S3M | XM | IT | MIDI |
|:---|:---|:---|:---|:---|:---|:---|
| `vol_with_effect` | 音量と他の奏法を同じ発音に付けられる | ✕ | ○ | ○ | ○ | ○ |
| `tremolo` | トレモロ（`Tremolo`） | ○ | ○ | ○ | ○ | ✕ |
| `release` | リリースのエンベロープ（`Instrument.release_s`） | 擬似（音量スライド） | 擬似 | ○ | ○ | ○（note off） |
| `filter` | フィルタのオートメーション（`Automation("cutoff")`） | ✕ | ✕ | ✕ | ○ | ○（CC74） |
| `pan_automation` | 発音中のパンの変化 | ✕ | ○ | ○ | ○ | ○ |
| `glide_bend` | グライドを連続的に表せる | ○ | ○ | ○ | ○ | ○（ピッチベンド） |

ジェネレータは `if "filter" in ctx.features:` のように**奏法を足すかどうか**の判断にだけ使う。features に無い奏法を書いても例外にはならず、Realizer が §9.6 の規則で落とす（警告ログ）。こうすれば、ジャンルは形式ごとに分岐しなくても全形式で動く。

---

## 5. Score（形式に依存しない楽譜）

### 5.1 時間・音高・音量の単位

| 量 | 単位 | 理由 |
|:---|:---|:---|
| 時刻 | **step**（区間の先頭から数える整数）。step 未満のずれは奏法 `Delay(ticks)` で表す | ジェネレータは現行の row と同じ感覚で書ける |
| 1 step の長さ | `24 // Meter.steps_per_beat` tick（16分格子なら 6 tick） | 1拍＝24 tick は現行のトラッカーの約束（DESIGN.md §1.4）。MIDI は PPQ 480 なので 1 tick＝20 MIDI tick で割り切れる |
| 音高 | 書かれた音高（float）。整数部は現行の logical note、小数部はセント/100 | 現行の音域定数をそのまま写せる。微分音（maqam・gamelan）は小数で書く |
| 音量 | 0..64 の整数（`None` は楽器の既定音量） | 耳で調整した値をそのまま写す（D12） |
| パン | 0..255（128 が中央） | 現行と同じ |

### 5.2 型

```python
TICKS_PER_BEAT = 24

@dataclass(frozen=True)
class NoteEvent:
    step: int                        # 区間の先頭からの step
    inst: str                        # Instrument 名（Genre.instruments のキー）
    pitch: Optional[float] = None    # 書かれた音高。音程の無い楽器（Instrument.pitched=False）は None
    vel: Optional[int] = None        # 0..64。None は楽器の既定音量
    dur: Optional[int] = None        # step 数。None は「同じ lane の次の発音まで。ワンショットは自然減衰、ループは区間の終わりまで」
    chord: tuple[int, ...] = ()      # 和音: pitch（根音）からの半音の列（例: m9 は (0, 3, 7, 10, 14)）。空なら単音
    strum_ms: float = 0.0            # 和音の構成音ごとの鳴り始めの遅れ（ギターのストローク）
    prio: int = 1                    # 同じチャンネルに畳まれたときの優先度（大きいほど勝つ。§9.3）
    arts: tuple["Articulation", ...] = ()

@dataclass(frozen=True)
class NoteOff:                       # 明示的な消音（dur で書けないとき）
    step: int
    inst: str                        # この楽器の鳴っている lane を止める

@dataclass(frozen=True)
class Automation:
    step: int
    kind: str                        # "volume"（0..64）| "pan"（0..255）| "cutoff"（0..127）
    value: int
    inst: Optional[str] = None       # None はパートの全 lane

@dataclass(frozen=True)
class TempoEvent:
    step: int
    bpm: int                         # 32..255

Event = Union[NoteEvent, NoteOff, Automation]

@dataclass
class SectionScore:
    name: str
    plan: "SectionPlan"
    parts: dict[str, list[Event]]    # パート名 → 時刻順のイベント
    tempo: list[TempoEvent]          # 区間内のテンポ変化（先頭の BPM は Score.bpm か直前の値）

@dataclass
class Score:
    bpm: int                         # 曲の先頭の BPM
    key_pc: int
    sections: dict[str, SectionScore]   # 作成順（＝初出順）
    order: list[str]                    # 区間名の並び（同じ名前は同じ内容を繰り返す）
    summary: list[str]                  # バナーに出す行
```

### 5.3 奏法（Articulation）

奏法は**意味**で書き、値は現行の単位（D12）にする。Realizer が形式ごとに表現する（§9.6・§11.3）。

```python
@dataclass(frozen=True) class Vibrato:   param: int; at: int = 0; steps: int = 1    # MOD 4xy の param。発音から at step 後に steps 個の step で掛ける
@dataclass(frozen=True) class Tremolo:   param: int; at: int = 0; steps: int = 1    # MOD 7xy の param（新しく使えるようになる）
@dataclass(frozen=True) class Arpeggio:  x: int; y: int; steps: int = 1             # 0xy。発音の step から steps 個
@dataclass(frozen=True) class Glide:     steps: Optional[int] = 1; param: Optional[int] = None
    # 同じ lane の直前の音からこの音へ滑らせる。steps で到達時間を指定するか、param（MOD 3xx の速さ）を直接指定する
@dataclass(frozen=True) class Delay:     ticks: int                                  # step 内で遅らせる（EDx）。ticks < その row の tick 数（§6.6）
@dataclass(frozen=True) class Retrig:    ticks: int                                  # E9x。step 内の連打
@dataclass(frozen=True) class Cut:       ticks: int                                  # ECx
@dataclass(frozen=True) class Offset:    fraction: float                             # サンプルの途中から鳴らす（9xx）。サンプル長に対する割合
```

- `Glide` の「直前の音」が鳴り終わっている（ワンショットの自然減衰が済んだ）なら、Realizer はグライドをやめて普通の発音にする（現行 trap の規則を一般化。DESIGN.md §6.8）。
- `Offset` はサンプル長に対する割合で書く。形式によってサンプル長（解像度）が違うため、バイト数では書かない。
- 新しい奏法を足すときの手順は §17.2。

### 5.4 区間の計画（ジェネレータが読む）

```python
@dataclass(frozen=True)
class Meter:
    steps: int = 16                  # 1小節の step 数（4/4 の16分＝16、3/4＝12、2/4＝8、7/8＝14）
    steps_per_beat: int = 4          # 表示 BPM の1拍の step 数（1, 2, 3, 4, 6, 8, 12, 24 のどれか）
    signature: tuple[int, int] = (4, 4)   # MIDI の拍子の表示

@dataclass(frozen=True)
class Swing:
    long: int                        # 2 step の組の前半の tick 数
    short: int                       # 後半の tick 数（long + short == 2 × 24 // steps_per_beat）

@dataclass(frozen=True)
class MeasurePlan:
    index: int                       # 区間の中の小節番号（0..）
    start: int                       # 区間の先頭からの step
    steps: int                       # この小節の step 数（可変拍子なら小節ごとに違う）
    chord: ChordDef                  # 現行 core/harmony.voice() の結果（bass・harmony・chord_tones・scale_tones・arp）
    quality: str                     # 和音の種類（CHORD_QUALITIES のキー）
    chord_offset: int                # 同じ和音の何小節目か（0 なら和音の変わり目）
    next_chord: ChordDef             # 次の小節の和音（区間の最後は区間の先頭へ戻る）

@dataclass
class SectionPlan:
    name: str
    kind: str
    meter: Meter
    measures: tuple[MeasurePlan, ...]
    intensity: float                 # 0..1
    key_offset: int
    tonic: int                       # (key_pc + key_offset) % 12
    scale: Scale
    parts: frozenset[str]            # この区間で鳴らすパート名
    swing: Optional[Swing]
    section: "Section"               # 宣言（groove・fill・crash・motifs・tags を読む）
    extra: dict                      # plan() の上書きでジャンルが足す値（racing-breaks の系統など）

    @property
    def steps(self) -> int: ...      # 区間の長さ（step）

@dataclass
class SongPlan:
    bpm: int
    key_pc: int
    sections: dict[str, SectionPlan]   # 作成順
    order: list[str]
    summary: list[str]
    extra: dict
```

**区間は名前ごとに1回だけ作曲する**（現行の「同じ区間名は同じ pattern」と同じ）。`order` で同じ名前を繰り返すと同じ内容が繰り返される。

---

## 6. ジャンルの書き方（Genre API）

### 6.1 方針

- ジャンルは**宣言**（楽器・和声・区間と構成・パート・編成）と、パートごとの**ジェネレータ**だけを書く。
- ジャンルが書かないもの: チャンネル番号、pattern、64 row、row 0・最終 row の空き、`D00`、エフェクト番号、セル、`off()`（ループ音色の消音は `dur` か `NoteOff`）、サンプル番号、形式ごとの分岐（`ctx.features` での奏法の付け外しを除く）。
- 宣言の誤りは**クラス定義時か、テストの「全ジャンル×全予算」の生成**で見つかるようにする（§13.2）。

### 6.2 基底クラス

```python
class Genre:
    # --- メタ（現行 GenreProfile と同じ意味） ---
    id: str
    aliases: tuple[str, ...] = ()
    category: str = "genre"          # "mood" | "genre" | "style"
    display_name: str
    description: str                 # 日本語1行
    description_en: str              # 英語1行
    title: str                       # ASCII ≤20
    tempo_choices: tuple[int, ...]
    tempo_range: tuple[int, int] = (32, 255)

    # --- 宣言 ---
    instruments: Mapping[str, Instrument]    # 挿入順はサンプルの並びに使う（MIDI のチャンネル割当はパートの並び。§11.2）
    harmony: Optional[Harmony] = None        # None なら plan() を上書きして和音を自分で作る
    sections: Mapping[str, Section]
    form: tuple[str, ...]
    parts: tuple[Part, ...]                  # 並び順＝重要度の順＝チャンネルの並び（§9.3・§9.4）
    swing: Optional[Swing] = None            # 全区間の既定（Section.swing で上書き）
    mod_channels: Mapping[int, int] = {4: 1} # MOD の予算 → 重み（例 {4: 1, 6: 2, 8: 1}）。キーは 4/6/8
    channel_cap: Optional[int] = None        # 美的な上限（chiptune・focus など、厚くしないことが目的のジャンル）
    mix: tuple[MixRule, ...] = ()

    # --- フック（既定の実装あり。必要なときだけ上書きする） ---
    def plan(self, rng: random.Random) -> SongPlan: ...
    def finalize_section(self, sec: SectionPlan, score: SectionScore, rng: random.Random) -> None: ...
```

- `plan()` の既定の実装は §6.7。上書きするときは `super().plan(rng)` を呼んでから `extra` や `summary` を足すのが基本（racing-breaks の系統、gamelan の音階など）。
- `finalize_section()` は区間の全パートを作った後に呼ばれる。**パートをまたぐ編集**（「決め」で他のパートを黙らせる、衝撃音の前を空ける等）はここで行う。`SectionScore.mute(parts, start, end)`・`SectionScore.add(part, event)` を使う。

### 6.3 宣言の型

```python
@dataclass(frozen=True)
class Instrument:
    patch: Patch                     # core/synth の Patch（synth_presets から preset() で取る）
    gm: GmVoice                      # MIDI の音色（GmVoice(program=) か GmVoice(drum_note=)）。必須
    volume: Optional[int] = None     # 既定音量（None は patch.volume）
    tune_cents: float = 0.0          # 音高の固定のずれ（現行の vln2 の finetune +3 ≈ +23 セントなど）
    release_s: Optional[float] = None    # opt-in（D14）: 消音のときに掛けるリリースの秒数。None は即時に止める（現行どおり）
    pan: Optional[int] = None        # 楽器ごとのパン（打楽器を lane に分けたときなど）。None はパートのパン

@dataclass(frozen=True)
class Harmony:
    keys: tuple[int, ...]            # 主音の候補（pc）
    mode: str                        # core/pitch.MODES のキー
    mode_by_quality: Mapping[str, str] = {}
    registers: Registers = Registers(bass=(0, 11), harmony=(12, 23), melody=(19, 33))
    progressions: tuple[tuple[str, tuple[ChordSpec, ...]], ...] = ()
    n_progressions: int = 2
    fixed: bool = False              # True なら選ばず宣言順に全部使う

@dataclass(frozen=True)
class Section:
    prog: int = 0                    # 使う進行の番号
    measures: int = 4                # 小節数（現行: 64 // rows_per_measure。jazz・bossa は 8、classical は 4）
    meter: Meter = Meter()
    measure_steps: Optional[tuple[int, ...]] = None   # 可変拍子: 小節ごとの step 数（prog-rock の 14,14,10 など）。
    #   指定したときは要素数が小節数になり、measures は既定値のままにする（既定値以外を両方書いたら PlanError）
    intensity: float = 0.7
    parts: frozenset[str] = ALL      # 鳴らすパート名（follow を持つパートは書かない。§6.5）
    key_offset: int = 0
    swing: Optional[Swing] = None
    groove: str = "main"             # ドラムの型の名前
    fill: bool = False
    crash: bool = False
    motifs: str = "verse"            # 旋律の動機の組の名前
    tags: frozenset[str] = frozenset()   # ジャンル固有の印（"kime"・"spic" など。現行は parts に混ぜていた）
    kind: str = ""                   # 空なら区間名

@dataclass(frozen=True)
class Part:
    name: str
    gen: "Generator"
    pan: int = 128
    min_channels: int = 0            # 予算がこれ未満の曲では外す（現行の「8ch の編成だけの任意パート」は 8）
    kit: Optional["Kit"] = None      # 打楽器のパート: lane のまとめ方
    poly: int = 1                    # 同時に鳴りうる音の数（lane 数）。ベル・クラスターなど。和音（chord）を書くパートは 1 のまま（両方は PlanError）
    chord_spread: int = 32           # 和音を声部に開いたときのパンの広がり（pan ± spread/2）
    double: Optional["Double"] = None    # opt-in（D14）: デチューンした複製で左右に広げる
    follow: Optional[str] = None     # 付き従うパート。指定すると「follow のパートが鳴る区間」で鳴る（区間の parts には書かない）。
    #   エコー・レイヤー（現行の ECHO・LAYERS）用。指定が無ければ区間の parts に名前がある区間で鳴る
    depends: tuple[str, ...] = ()    # 先に作っておくパート（ctx.events_of で読める）。follow のパートは自動で含まれる

@dataclass(frozen=True)
class Kit:
    groups: tuple[tuple[str, tuple[str, ...]], ...]   # 「まとめた」段階の lane: (lane 名, 楽器名…)
    priority: Mapping[str, int] = {} # 畳むときの優先度（楽器名 → 値、未記載 1）。まとめた段階と1本の段階で使う
    single_priority: Optional[Mapping[str, int]] = None
    #   1本の段階だけの優先度（現行の Fold.priority が ChannelDef.priority と食い違うジャンル用）。None なら priority

@dataclass(frozen=True)
class Double:
    detune_cents: float = 8.0
    spread: int = 64                 # 元と複製を pan ± spread/2 に置く
    vel_ratio: float = 0.7

@dataclass(frozen=True)
class Sidechain:                     # MixRule の唯一の種類（現行 SIDECHAIN）
    triggers: tuple[str, ...]        # トリガの楽器名
    targets: tuple[str, ...]         # 下げるパート名
    ratio: float = 0.3
    release_steps: int = 2
MixRule = Sidechain
```

### 6.4 宣言の例（pop。現行 `genres/pop.py` の写し）

```python
@register_genre
class Pop(Genre):
    id = "pop"; display_name = "Pop"; title = "Bright Pop"
    description = "ポップ。長調の明るいメロディとピアノ、覚えやすいサビ"
    description_en = "Pop: bright major-key melodies, piano and a catchy chorus"
    tempo_choices = (100, 104, 108, 112, 116, 120)

    instruments = {
        "kick": inst("drum_pop_kick"), "snare": inst("drum_pop_snare"), "hat": inst("nostalgic_hihat"),
        "shaker": inst("perc_shaker"), "crash": inst("march_crash_cymbal"), "bass": inst("bass_finger"),
        "lead": inst("vox_ooh"), "line": inst("orch_violin", volume=30),
        "piano": inst("keys_piano"), "pad": inst("pad_warm"),
    }   # inst(key, **changes) = Instrument(preset(key, ...), gm=gm_default(...))
    harmony = Harmony(keys=(0, 2, 5, 7), mode="ionian", progressions=PROGRESSIONS, n_progressions=3)
    sections = {
        "intro": Section(prog=0, intensity=0.4, parts=P("comp", "pad")),
        "verse": Section(prog=1, intensity=0.6, parts=BASE | P("lead"), groove="verse"),
        ...
    }
    form = ("intro", "verse", "pre", "chorus", "verse", "pre", "chorus", "bridge", "chorus", "chorus_up", "outro")
    parts = (
        Part("drums", Groove(GROOVES), kit=Kit(groups=(("kick/snare", ("kick", "snare")),
                                                       ("hat", ("hat", "shaker", "crash"))),
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

現行との対応: `KIT`・`CHORD_KITS` → `instruments`（和音のサンプルは Realizer が使われた和音から作る。§8.4）、`CHANNELS`・`ARRANGEMENTS`・`Fold`・`DRUM_CHANNEL` → `parts` の並び・`min_channels`・`Kit`、`BASS`・`COMP`… → 部品集のジェネレータ、`ECHO`・`LAYERS` → `follow` を持つパート（区間の `parts` には書かない）、`CHANNEL_WEIGHTS` → `mod_channels`。

### 6.5 ジェネレータ

```python
class Generator:
    """1パートの音符を作る。インスタンスはジャンルのクラス属性として共有されるので、状態を self に持たない。
    状態は ctx.state（区間ごと）・ctx.song_state（曲全体）に置く。"""

    def section(self, ctx: SectionCtx) -> None:
        """区間全体を作る。既定は小節ごとに measure() を呼ぶ。区間をまたぐ型（4小節のビルドアップ等）は上書きしてよい。"""
        for m in ctx.measures():
            self.measure(m)

    def measure(self, m: MeasureCtx) -> None:
        ...
```

ジェネレータが呼ばれる区間はフレームワークが判定する: `Part.follow` があれば follow のパートが鳴る区間、無ければ区間の `parts` に自分のパート名がある区間。鳴らない区間でループ音色を止める処理は書かなくてよい（次に鳴らない区間の先頭で Realizer が止める。§9.7）。

### 6.6 文脈（`SectionCtx`・`MeasureCtx`）

```python
class SectionCtx:
    plan: SectionPlan                # 区間の計画（meter・intensity・tonic・scale・section 宣言・extra）
    song: SongPlan
    part: Part
    rng: random.Random               # このパート専用の乱数（§6.8）
    state: dict                      # この区間・このパートの状態（区間ごとに空で始まる）
    song_state: dict                 # このパートの曲全体の状態（区間をまたぐ旋律の流れなど）
    features: frozenset[str]         # §4.3。奏法の付け外しにだけ使う
    bpm: int                         # 曲の BPM（suspense のように秒から step を逆算するジャンル用）
    def measures(self) -> Iterator[MeasureCtx]: ...
    def events_of(self, part: str) -> list[Event]: ...     # depends に書いたパートのこの区間のイベント
    def step_seconds(self, step: int = 1) -> float: ...    # スウィングを除いた step の長さ（秒）
    def inst_seconds(self, inst: str) -> Optional[float]: ...   # ワンショットが鳴り終わるまでの秒数（MOD の再生レートで。ループは None）
    def scale_vol(self, vol: int) -> int: ...      # 現行 _scale_vol: vol × (0.55 + 0.45 × intensity)、1..64
    def scale_drum(self, vol: int) -> int: ...     # 現行ドラム: vol × (0.6 + 0.4 × intensity)、1..64
    # 音符を書く（時刻は区間の先頭からの step）
    def note(self, step: int, inst: str, pitch: Optional[float] = None, vel: Optional[int] = None, *,
             dur: Optional[int] = None, chord: tuple[int, ...] = (), strum_ms: float = 0.0,
             prio: int = 1, arts: tuple[Articulation, ...] = ()) -> None: ...
    def off(self, step: int, inst: str) -> None: ...
    def automate(self, step: int, kind: str, value: int, inst: Optional[str] = None) -> None: ...
    def tempo(self, step: int, bpm: int) -> None: ...    # テンポの変化（free-jazz・nostalgic）

class MeasureCtx(SectionCtx):
    m: MeasurePlan                   # index・start・steps・chord・quality・chord_offset・next_chord
    is_first: bool
    is_last: bool
    is_chord_change: bool            # m.chord_offset == 0
    # note()/off()/automate() の step は「小節の先頭から」。内部で m.start を足す
```

検査（書いた時点で `PlanError`）: `step` が区間（小節）の外、`inst` が宣言に無い、音程のある楽器に `pitch=None`、音程の無い楽器に `pitch` あり、`vel` が 0..64 の外、`Delay.ticks` が row の tick 数以上（スウィングのある区間では短い側 `min(long, short)`、無ければ `24 // steps_per_beat`）。`Retrig`・`Cut` の ticks も同じ上限。

### 6.7 既定の `plan()`（現行 `BandProfile.plan` と同じ規則）

1. `bpm = rng.choice(tempo_choices)`（`--tempo` があっても**引いてから捨てる**。DESIGN.md §5.5 の約束を維持）。
2. `key_pc = rng.choice(harmony.keys)`。
3. 進行: `fixed` なら宣言順に全部、そうでなければ `rng.sample(range(len), k=min(n, len))`。
4. 区間名の初出順に `SectionPlan` を作る。小節への和音の割当は現行どおり「1和音 `max(1, 小節数 // 和音数)` 小節で、進行を繰り返して小節数を埋める」。和音は `voice(spec, tonic, Scale(tonic, MODES[mode]), registers, mode_by_quality=...)`。
5. `summary` に調と進行（現行と同じ書式）。

### 6.8 乱数

- 計画: `random.Random(f"{seed}:{genre.id}:plan")`。
- パート: `random.Random(f"{seed}:{genre.id}:part:{part.name}")`。曲全体で1本（区間をまたいで続けて消費する）。区間は**作成順**（`SongPlan.sections` の順）に作る。
- 予算の選択（MOD）: `random.Random(f"{seed}:{genre.id}:channels")`（現行と同じ）。テンポ範囲の選択: `...:tempo`（現行と同じ）。
- ジャンルが独自の乱数を要るとき（`finalize_section` など）: `random.Random(f"{seed}:{genre.id}:x:{name}")`。
- **あるパートの変更が他のパートの乱数列を変えない**（現行の5本より細かく分かれる）。**予算で外れたパートも作曲はする**（作って捨てる）。乱数の消費が予算に依存しないので、骨格が形式に依存しない（I1）。

### 6.9 作曲の順序（`framework/compose.py`）

区間ごと（作成順）に:

1. パートを `depends` で位相整列する（循環は `PlanError`）。依存の無いパート同士は宣言順。
2. 各パートについて、鳴る区間（§6.5。`follow` か区間の `parts`）なら `gen.section(ctx)` を呼ぶ。`follow` のパートは follow 先の後に作る。
3. `genre.finalize_section(plan, score, rng)` を呼ぶ。
4. `Score` の検査: 同じパート・同じ楽器・同じ step に2つの `NoteEvent` があり、**`prio` が同じ** → `PlanError`（`prio` が違えば高い方を残し、低い方を捨てる。march のスネアロールが通常のスネアを置き換えるのはこの規則。和音は1つの NoteEvent なので該当しない）。`poly` を超える同時発音 → `PlanError`。

---

## 7. ジェネレータの部品集（`framework/gens/`）

現行 `band_common` の型をそのまま移す。値（row の表・音量の差・確率）は**現行と同じ**にする（`band_common.py` の該当関数を写す）。ジェネレータはすべて `ctx.rng` を使う（現行の `rng.drums`/`bass`/`harmony`/`melody` の区別は、パートごとの乱数で置き換わる）。

| ジェネレータ | 引数 | 現行の対応 | 動作の要点 |
|:---|:---|:---|:---|
| `Groove(grooves)` | `grooves: Mapping[str, tuple[Hit, ...]]`、`late: Mapping[str, float] = {}`、`humanize: int = 4`、`groove_name: Callable[[SectionPlan], str] = 既定` | `BandProfile.drums`・`GROOVES`・`LATE`・`HUMANIZE` | 区間の `groove` の型を鳴らす。`fill` なら最後の小節の後半を `"fill"` に差し替え、`crash` なら最初の小節に `"crash"` を足す。`late` の楽器は確率で `Delay(1〜2)`（音量は既定）、それ以外は音量に ±humanize と `scale_drum`。`Hit(row, key, vol, prob, note)` はそのまま使う（row は step） |
| `BassLine(inst, kind, vol)` | kind は `whole`・`half`・`root8`・`octave8`・`offbeat`・`rootfifth`・`bossa`・`walking`・`synco16`・`boombap`・`pulse16`・`house` | `bass_line()` | 16 step 基準の型を小節の step 数に比例させる（現行どおり） |
| `Comp(inst, kind, vol, chordal=True, wobble=0, strum_ms=0)` | kind は `comp_rows()` の13種 | `BandProfile.comp`・`comp_rows()` | `chordal` なら `note(step, inst, chord.harmony, chord=QUALITY_INTERVALS[quality], strum_ms=...)`。`wobble` は `Vibrato(wobble, at=1, steps=1)`（現行は「直後の row が空いていれば 4xy」） |
| `Pad(inst, vol, chordal=True)` | | `BandProfile.pad` | 和音の変わり目に `dur=None`（次の発音まで） |
| `Arp(inst, steps, vol, pattern="up", register)` | | `BandProfile.arp` | |
| `Lead(inst, rules, motifs, vol, gate, vibrato=0, inst_for=None)` | `inst_for`: 区間 → 楽器名（現行 `lead_key` の上書き） | `BandProfile.lead`・`begin_pattern` | 区間の先頭で `MelodyGenerator` と動機 A・B を用意し、4小節の楽節（A・A・B・終止）。`gate` は `dur = max(1, round(長さ × gate))`。`vibrato` は 6 step 以上の音に `Vibrato(param, at=2)` |
| `Fx(inst, every, vol)` | | `FxSpec` | |
| `Layer(inst, vol, chordal=False, register)` | | `LayerSpec` | パートの `follow` で鳴る区間を決め、和音の変わり目に置く。乱数を使わない |
| `Echo(delay, ratio, repeats=1)` | | `EchoSpec`・`echo()` | パートの `follow` のパートの NoteEvent を delay step 遅らせ、vel×ratio^k で写す。区間の外に出るものは捨てる。`dur` も写す（現行の `offs=True` に当たる。常にそうする） |
| `Buildup(inst, riser=None, n_measures=4)` | | `buildup()` | 現行どおり（4分→8分→16分→`Retrig(3)`） |

`MelodyGenerator.bar()` は現行の `(row, note, vol, dur)` の列を返す。部品の `Lead` がそれを `NoteEvent` に変える（`composer.py` は変えない）。

---

## 8. 音色の描画（`core/synth.py`・`core/dsp.py`・`framework/realize/samples.py`）

### 8.1 実音の約束（D3）

現行の合成は `dsp.sample_rate(rate_note)`（Paula の実際の再生レートの半分）を基準に波形を作り、プレイヤーは `CLOCK / PERIODS[t]` で再生するので、**ワンショットは書かれた音高の1オクターブ上**で鳴り、長さは半分になる。ループは周期数とループ長で決まる高さで鳴る（`synth._sounding_hz`）。全音色はこの状態で耳で調整されている。

新しい設計でも、**どの形式でも、書かれた音高 n の音は、現行の MOD で n を鳴らしたときと同じ実音・同じ長さで鳴る**ようにする。MIDI も現行どおり実音（`sounding_hz`）から音高を求める。

**基準の定義**: 「同じ実音」は、`rate_note` で鳴らしたときの実音 `sounding_hz` から平均律で求めた高さ `sounding_hz × 2^((t − rate_note)/12)`（t は tracker note）とする。MOD の Period 表は整数に丸められているので、MOD 自身がこの基準から最大 5.9 セントずれる（実測）。S3M・XM・IT は基準どおり（平均律）に鳴らす。検査 I4 はこの基準と比べる。

### 8.2 高解像度の描画

- 倍率 `m = max(1, target_rate / real_rate)`。`real_rate = CLOCK / PERIODS[patch.rate_note]`（`rate_note` で鳴らしたときの実際の再生レート）。MOD は常に m＝1（現行と同じ描画）。
- 合成の内部レートを `dsp.sample_rate(rate_note) × m` にして描画する。時間（秒）で書かれた値（`OneShot` の長さ、`decay_alpha`、`attack_ms`、`tail_fade_ms`、`offset_ms`）と Hz で書かれた値（`PitchSweepLayer`、`ToneLayer` の基音）はそのまま使えば、聞こえ方は変わらない。
- **サンプル数で書かれた値は m 倍する**: `Loop.length`・`Loop.attack_samples`（偶数に丸める）。
- **サンプル単位の係数は換算する**: `dsp.one_pole_lp(a)` と `dsp.noise_lp(a_start, a_end)` の係数 a（`y = a·y + (1−a)·x`）は `a' = a^(1/m)`（同じ遮断周波数）。`dsp.diff_hp`（一次差分）は換算できないので、m>1 では「m=1 のときの −3 dB 点と同じ遮断周波数の1次 HP」に置き換える（要実測で音を確かめる。§18.1）。
- 加算合成は `nyquist = 内部レート / 2` 以上の部分音を捨てる（現行の規則）。m>1 では捨てる部分音が減り、**高域が出るようになる**（これが解像度の改善）。
- 再生レート（`SampleSpec.rate_hz`。`rate_note` で鳴らすときのレート）:
  - ワンショット: `rate_hz = real_rate × m`。
  - ループ: m 倍したループ長を整数に丸めるので、`rate_hz = real_rate × L'/L`（L は元のループ長、L' は丸めた長さ）。これで周期数は変わらず、実音が厳密に一致する。
- 量子化: 8-bit は現行の `dsp.to_pcm`。16-bit は `round(x × 32767)` を [−32768, 32767] に切る（偶数長の規則は16-bit では不要だが、ループ境界はサンプル単位）。
- 長さの上限（`SampleCaps.max_bytes`）を超えるときは、m を上限に収まる最大値まで下げる（S3M の長い効果音など）。m＝1 でも超えるなら `SampleConstraintError`。

### 8.3 `render()` の新しい形

```python
def render(patch: Patch, *, oversample: float = 1.0, bits: int = 8) -> SampleSpec: ...
```

`SampleSpec` に `bits: int = 8` と `rate_hz: Optional[float] = None`（None は MOD の Period から決まる）を足す。`sounding_hz` は m に依存しない（同じ値になることをテストで確かめる）。

### 8.4 サンプルの計画（Realizer が描画の前に行う）

Score とパートの選択（§9.2）の結果から、必要なサンプルを決めて番号を振る。

| 種類 | いつ作るか | 作り方 |
|:---|:---|:---|
| 楽器そのもの | 選ばれたパートが鳴らす楽器 | `render(instrument.patch, ...)` |
| 焼き込みの和音 | 和音を声部に開かない（§9.3 の手順で「焼く」と決まった）パートの、使われた和音の形ごと | 現行 `chord_patch(base, quality, strum_ms)` を `core/synth.py` に移し、`intervals` で受けるように一般化した `chord_patch(base, intervals, strum_ms)` で Patch を作って描画。ループ音色で音程誤差が 12 セントを超える形は焼けない（現行どおり）。その場合は声部に開く（§9.3） |
| 微分音・`tune_cents` の変種 | 書かれた音高の小数部（と `tune_cents`）が0でない音 | MOD: 現行 `pitch.resolve_micronote` で (t, finetune) を求め、finetune の値ごとに変種のサンプル。S3M・IT: 再生レートにセントを掛けた変種（`rate_hz × 2^(cents/1200)`）。XM: サンプルの finetune（1/128 半音）。MIDI: §11.3 |
| パン違い | XM で既定パン以外を楽器に付けるとき | 現行どおりサンプルパン |

サンプルの並び: 楽器の宣言順 → 各楽器の変種（和音の形の初出順、セントの昇順）。数が `max_samples` を超えたら `PlanError`（MOD の 31 が実際に問題になる。全ジャンル×全予算のテストで検出する）。

### 8.5 楽器の名前

サンプル名は現行どおり ASCII 22 文字以内。和音の変種は `{patch.name[:13]}{quality}`（現行と同じ）、形に名前が無いときは `{patch.name[:13]}c{n}`。

### 8.6 キャッシュ

描画は遅い（純 Python）。`(Patch, oversample, bits)` を鍵にプロセス内でキャッシュする（`functools.lru_cache` 相当。`Patch` は frozen dataclass なのでハッシュできる）。テストの総当たりで効く。

CLI は1回ごとに新しいプロセスなので、プロセス内のキャッシュは効かない。**F1 で1曲の生成時間を測り**（現行は racing-breaks の音色の合成だけで 0.26 秒。倍率 m≈2.66 ではサンプル数と描画する部分音の数がともに増える）、S3M・XM・IT で 2 秒（NFR-3 の目安）を超えるなら、次のディスクキャッシュを入れる。超えなければ入れない（コードを増やさない）。

- 置き場所: 環境変数 `MODWEAVER_CACHE_DIR`、無ければ OS のユーザーキャッシュ（Windows `%LOCALAPPDATA%\ModWeaver\cache`、それ以外 `~/.cache/modweaver`）。`MODWEAVER_NO_CACHE=1` で使わない。
- 鍵: `repr(patch)`・oversample・bits・描画コードの版（`synth.RENDER_VERSION`。描画の結果が変わる変更をしたら上げる）の SHA-256。値はサンプルのバイト列と付帯情報。
- 読めない・壊れているときは黙って描画し直す（キャッシュは正しさに影響しない）。

---

## 9. TrackerRealizer（MOD・S3M・XM・IT）

### 9.1 手順の全体

```text
realize(genre, score, target):
  1. パートの選択（予算と min_channels）                         §9.2
  2. lane の需要を数え、予算に収まるまで段階的に減らす（ladder）       §9.3
  3. lane をチャンネルに並べ、パンを決める                          §9.4
  4. イベントを lane に割り当てる（和音の声部化、打楽器の振り分け、複製）  §9.5
  5. サンプルを計画して描画する                                    §8.4
  6. lane ごとにセルを作る（音高→ノート番号、音量、奏法→エフェクト）     §9.6
  7. 音の終わり（dur・NoteOff・ループの区間頭での停止・リリース）      §9.7
  8. ミックス規則（サイドチェイン）・オートメーション                 §9.8
  9. 時間軸（Speed・スウィング・テンポ）と row コマンド、pattern への詰め込み  §9.9
 10. 音量の底上げ                                                §9.10
```

### 9.2 予算とパートの選択

- 予算 `B`:
  - MOD: `--channels` があればその値（`Genre.mod_channels` のキーに無ければ `ChannelCountError`、終了コード 2）。無ければ `random.Random(f"{seed}:{id}:channels")` で `mod_channels` の重みから選ぶ（現行 `resolve_channels` と同じ）。
  - S3M・XM・IT（と MP3）: `min(形式の上限, channel_cap, --channels)`（指定の無いものは除く）。
  - どの形式でも `channel_cap` があれば `B ≤ channel_cap`（MOD で `mod_channels` に cap を超えるキーを書くのは宣言の誤り）。
- パート `p` を選ぶ条件: `p.min_channels ≤ B`。選ばれなかったパートのイベントは捨てる（作曲はしてある。§6.8）。

### 9.3 lane の需要と ladder

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
| R2 | 全 kit を「まとめる」 |
| R3 | 和音を焼く（後ろのパートから1つずつ） |
| R4 | kit を「1本」にする（後ろのパートから1つずつ） |
| R5 | まだ収まらなければ `PlanError("<genre>: <B> channels cannot hold ...")`。宣言の誤りで、全ジャンル×全予算のテスト（§13.2）で見つける |

最後に `lanes < B` なら1本を**制御チャンネル**（音を置かず、Speed・テンポ・`D00` などの row コマンドだけを書く）にする。

和音を焼けない（ループ音色で音程誤差が 12 セントを超える。§8.4）パートは R3 で飛ばす。そのため R5 で止まることがある。

**計算例（pop。§6.4 の宣言）**: 打楽器の楽器は5（kick・snare・hat・shaker・crash）、piano と pad の和音は最大4音とする。

| 予算 | L0 | R2 の後 | R3 の後 | R4 の後 | 結果（チャンネルの並び） |
|:---|:---|:---|:---|:---|:---|
| MOD 4 | 5+1+4+1 = 11（pad・echo・strings は外す） | 2+1+4+1 = 8 | 2+1+1+1 = 5 | 1+1+1+1 = 4 | drums・bass・piano・lead（現行の 4ch と同じ） |
| MOD 6 | 5+1+4+1+4 = 15 | 12 | pad を焼く 9 → piano を焼く 6 | ― | kick/snare・hat・bass・piano・lead・pad（現行の 6ch と同じ） |
| MOD 8 | 15+1+1 = 17 | 14 | 11 → 8 | ― | 上＋lead echo・strings（現行の 8ch と同じ） |
| S3M 16 | 17 | 14 → 制御チャンネルを足して 15 | ― | ― | 打楽器は2本、和音は声部 |
| XM 32・IT 64 | 17 → 制御チャンネルを足して 18 | ― | ― | ― | 打楽器は5本、和音は声部 |

### 9.4 チャンネルの並びとパン

- 並び: パートの宣言順。パートの中は、kit の lane（グループ順、グループ内は楽器の順）、和音の声部（低い声部から）、`poly` の lane、`double` の複製（元の lane の直後）。制御チャンネルは最後。
- **パートの宣言順は、現行で最も厚い編成（8ch など）の `ARRANGEMENTS` の並びに合わせる**（4ch・6ch の並びはその部分列になる。§15.1）。
- パン（S3M・XM・IT）: lane のパンは `Instrument.pan`、無ければ `Part.pan`。和音の声部は `pan + spread × (i/(k−1) − 0.5)`（k は声部数）、`double` は `pan ± spread/2`。どのパートも `pan` を宣言していない（全部 128）ジャンルは、現行の規則2（L R R L を 64/192 で繰り返す。DESIGN.md §7.1）を使う。
- MOD: パンはプレイヤーの固定（L R R L）。並びだけが効く。

### 9.5 イベントの lane への割当

- **kit**: 楽器の lane（段階に応じて楽器・グループ・1本）。同じ lane の同じ step に2つの発音があれば、`NoteEvent.prio` が大きい方、同じなら `Kit.priority`（1本の段階では `Kit.single_priority` があればそれ）が大きい方、それも同じなら kit の並びで先の楽器を残す（現行の `ChannelConflictError` はやめる。決定的に解決する）。
- **単音のパート**（`poly=1`）: 1本の lane。同じ step に2つあれば上と同じ規則で1つを残す。
- **`poly>1`**: 空いている lane（鳴っている音が無い。`dur` が分かっていれば終わった、ワンショットなら自然減衰が終わった）のうち番号の小さいもの。無ければ最も古い音の lane を奪う。
- **和音・声部**: NoteEvent 1つを、`pitch + chord[i]` の音として声部 i の lane に置く。音量は `round(vel / √k)`（k は構成音数。焼いた和音の `1/√k` に合わせる。試聴で調整する値。§18）。構成音が lane の数より少ない和音では、余った lane を同じ step で止める（焼いた和音の「次の和音が前の和音を切る」挙動に合わせる）。`strum_ms` は声部 i を `Delay(round(i × strum_ms / tick_ms))` で遅らせる（step の tick 数 −1 で頭打ち）。
- **和音・焼く**: NoteEvent 1つを、和音の形の変種サンプルで `pitch` の高さに1音として置く（現行と同じ）。
- **double**: 元の lane のイベントを、`pitch + detune_cents/100`（変種サンプル）・`vel × vel_ratio` で複製の lane に写す。

### 9.6 セル化と奏法の表現

#### セルの表現（`core/model.Cell` を上位集合に拡張）

```python
@dataclass(frozen=True)
class Cell:
    note: Optional[int] = None        # 形式のノート番号（Realizer が換算済み）か NOTE_CUT / NOTE_OFF
    sample: int = 0                   # 1..max_samples
    vol: Optional[int] = None         # 0..64（MOD は Cxx、他はボリューム列）
    pan: Optional[int] = None         # 0..255（XM/IT のボリューム列。vol と同じ列なので排他）
    fx: Optional[tuple[str, int]] = None   # (コマンド, param)。コマンドは形式の表記（"4", "H", "SD" など）
```

セルは Realizer の内部表現で、ジャンルは触らない。MOD の書き出しは `vol` と `fx` が両方あれば例外にする（下の規則で解決済みのはず）。

#### 音高 → ノート番号

- MOD: `t = round(n) − shift`（`shift` は楽器の Patch の値）。0..35 の外は `PitchRangeError`（現行と同じ）。微分音は変種サンプルの finetune。
- S3M・XM・IT: 楽器ごとに基準ノート `N_ref` を決め、`N = N_ref + (round(n) − shift − rate_note)`。サンプルの再生レートは「`N_ref` で鳴らすと `rate_hz`」になるように書く（S3M: C2Spd、IT: C5Speed、XM: relative note と finetune。§10）。`N_ref` は形式の音域の中央付近（S3M・XM は C-4、IT は C-5）。`N` が形式の音域の外なら `PitchRangeError`。**音域の制約は形式ごとに Realizer が検査し、ジャンルは MOD の 36 音を意識しなくてよい**（ただし MOD で鳴らすジャンルは MOD の範囲に収める必要があるので、音域の宣言は現行のままにする。§18.1）。
- 音程の無い楽器: 常に `rate_note` の位置（MOD は t=rate_note、他は `N_ref`）。

#### 奏法 → エフェクト（`framework/realize/encode.py`）

param は MOD の単位で受け取り（D12）、形式の表記に変える。表は現行 `core/effects.py` で実プレイヤーにより確認済みのものを引き継ぐ。

| 奏法 | MOD | S3M | XM | IT | 注 |
|:---|:---|:---|:---|:---|:---|
| `Vibrato(p)` | `4xy` | `Hxy` | `4xy` | `Hxy` | IT は Old Effects=1 で深さが一致（確認済み） |
| `Tremolo(p)` | `7xy` | `Rxy` | `7xy` | `Rxy` | **新しく使う**。深さの一致は要実測 |
| `Arpeggio(x, y)` | `0xy` | `Jxy` | `0xy` | `Jxy` | |
| `Glide` | `3xx` | `Gxx` | `3xx` | `Gxx` | 速さは「直前の音の period から目標の period まで steps 個の step で届く」値（現行 `automation.portamento_param`）。MOD の Period 表の外の音（拡張音域）の period は `P(n) = P_ref × 2^(−(n−ref)/12)` で求める（要実測） |
| `Delay(t)` | `EDx` | `SDx` | `EDx` | `SDx` | |
| `Retrig(t)` | `E9x` | `Q0x` | `E9x` | `Q0x` | |
| `Cut(t)` | `ECx` | `SCx` | `ECx` | `SCx` | |
| `Offset(f)` | `9xx` | `Oxx` | `9xx` | `Oxx`（64 KiB を超える位置は `SAx` を併用） | xx = `round(f × サンプル長 / 256)`。XM で 65280 byte を超える位置は表せないので最も近い表せる位置 |
| Speed / テンポ | `Fxx` | `Axx` / `Txx` | `Fxx` | `Axx` / `Txx` | |
| pattern の途中終了 | `D00` | `C00` | （不要。pattern 長で表す） | （同左） | |
| 音量 | `Cxx` | ボリューム列 | ボリューム列 `0x10+v` | ボリューム列 0..64 | XM は現行の `Cxx` からボリューム列に変える |
| 音量スライド（擬似リリース） | `Axy` | `Dxy` | ボリューム列のスライド | ボリューム列のスライド | §9.7 |
| パン | ― | `S8x` | ボリューム列 `Px` | ボリューム列のパン | |
| カットオフ | ― | ― | ― | `Zxx`（既定の MIDI マクロ） | 要実測 |

#### 1セルに入りきらないときの規則

トラッカーは全形式でエフェクトの列が1つしかない。MOD はさらに音量もエフェクトの列を使う。1つの lane・1つの row に複数の要求が重なったら次の順で解決する（決定的。落としたものは DEBUG ログ）。

1. エフェクトの優先順位: row コマンド（制御チャンネルが無いとき。§9.9）＞ `Delay` ＞ `Glide` ＞ `Retrig`・`Cut` ＞ `Arpeggio` ＞ `Offset` ＞ `Vibrato`・`Tremolo` ＞ 音量スライド ＞ カットオフ。負けた `Vibrato`・`Tremolo`・カットオフは、同じ lane の次の row が空いていればそこへ移し、空いていなければ落とす。それ以外は落とす。
2. MOD の音量（`Cxx`）とエフェクトが重なったとき: 音量が楽器の既定音量に等しい（か `vel=None`）なら音量を書かない（発音で既定音量に戻るので同じ）。違うときは、`Delay`・`Glide`・`Retrig`・`Cut`・`Arpeggio`・`Offset` ならエフェクトを残して音量を落とす（現行の挙動と同じ: ドラムの `LATE`・march のアルペジオは既定音量で鳴る）。`Vibrato`・`Tremolo` なら音量を残して、奏法を次の row へ移す（空いていなければ落とす）。
3. S3M・XM・IT の音量とパン（XM・IT はどちらもボリューム列）: 音量を残し、パンを次の空いた row へ移す。

### 9.7 音の終わり

- `dur` がある NoteEvent: `step + dur` の row で lane を止める（その row までに同じ lane で次の発音があれば何もしない）。楽器の種類を問わない（現行の `articulate` はワンショットにも消音を置いていた）。
- `NoteOff`: その step で、その楽器が鳴っている lane を止める。
- `dur=None` のループ音色: 同じ lane の次の発音まで鳴る。**区間の先頭（step 0）で発音の無いループの lane は、区間の先頭で止める**（区間は別の区間の後にも置かれるので、前の区間のループを止める責任は後の区間の先頭にある）。止めるセルは優先度が最も低く、曲の先頭の pattern で row コマンドの場所が足りなければ最初に外す（曲の先頭では何も鳴っていないので害が無い。その pattern が曲の途中でも使われる場合は、pattern を複製して先頭だけ外す）。
- 止め方:
  - `Instrument.release_s` が無い（既定）: 即時に止める。MOD は `Cxx 00`（現行の `off()`）、S3M・IT はノートカット（`^^^`）、XM はボリューム列の音量 0。
  - `release_s` がある（opt-in）: XM・IT は楽器の音量エンベロープ（サステイン点＋リリース）を作り、キーオフ（XM はノート 97、IT は `===`）を置く。MOD・S3M は音量スライド（`Axy`／`Dxy`）を `release_s` の間 row ごとに置く（lane の row が空いている間だけ）。MIDI は note off（リリースは音源に任せる）。

### 9.8 ミックス規則とオートメーション

- **サイドチェイン**（`Sidechain`）: トリガの楽器の発音がある step ごとに（**トリガは lane への割当の後に残った発音**。打楽器を畳んで優先度で消えた発音はトリガにならない。現行も書かれたセルで判定している。MIDI は畳まないので Score の発音がそのままトリガ）、対象パートで鳴っている lane の音量を `ratio` 倍にし、`release_steps` かけて戻す音量のセルを置く。現行 `core/mixer.apply_sidechain` の規則（音量だけを書く、他のエフェクトのセルには触れない、直前の音量が分からなければその回は飛ばす）を lane に対して適用する。
- **`Automation("volume")`**: その step で、対象の lane（`inst` 指定ならその楽器が鳴っている lane、無ければパートの全 lane）に音量だけのセル。
- **`Automation("pan")`**: S3M・XM・IT だけ。MOD は無視。
- **`Automation("cutoff")`**: IT だけ（`Zxx`）。他は無視。

### 9.9 時間軸・row コマンド・pattern

- **row と step**: 1 row ＝ 1 step。Speed（1 row の tick 数）＝ `24 // steps_per_beat`。区間ごとに steps_per_beat が違うジャンルでは、各区間の pattern の row 0 に Speed を書く。
- **スウィング**: 区間の `swing` があれば、row の偶奇で Speed を `long`・`short` に交互に書く（現行 `groove.apply_swing`）。
- **テンポ**: 曲の先頭の row 0 に BPM（形式のヘッダにも初期 BPM と初期 Speed を書く。MOD はヘッダが無いので row 0 の `Fxx` だけ）。`TempoEvent` はその row に。曲が `TempoEvent` を持つ場合は、各区間の row 0 にその区間に入るときの BPM を書く（order を辿って求める。同じ区間が違う BPM で入られるなら pattern を複製する）。
- **row コマンドの置き場所**: 制御チャンネルがあればそこ。1つの row に2つ以上のコマンドが要るとき（曲の先頭の Speed とテンポなど）と、制御チャンネルが無いときは、現行の規則で音のチャンネルに入れる（DESIGN.md §4.10。空のセル→音量・エフェクトの無い発音のセル。場所が無ければ現行の `reserve_row0`・`make_room_for_row_commands` の手順で作る）。この処理は Realizer の中にあり、ジャンルは関与しない。
- **pattern への詰め込み**: 区間の row 数 S が `max_rows` 以下なら1つの pattern。超えるときは小節の境目で `max_rows` 以下に分ける。MOD・S3M で 64 未満の pattern は最後の row に `D00`／`C00`（row コマンドとして置く）。XM・IT は pattern の長さをそのまま S にする（IT は 32 row 未満を作れないので、32 row にして最後の実際の row に `C00`。要確認）。
- **order**: 区間の並び（`Score.order`）を pattern の並びに展開する。内容が同じ pattern は1つにまとめる。order 長・pattern 数の上限を超えたら `PlanError`。

### 9.10 音量の底上げ

現行 `core/level.py` の方針（DESIGN.md §7.9）を引き継ぐ。変更点:

- 実測値（`profiles/levels.py` の `PEAK_DB`）は**全ジャンル×全形式で作り直す**（チャンネル数・解像度・和音の鳴らし方が変わるため）。MOD は全予算の最悪値。
- XM の音量はボリューム列になるが、倍率の考え方は同じ（全ての音量の値を同じ倍率で上げ、最大が 64 まで）。
- チャンネル数の多い IT では大きすぎることがありうるので、**下げる方向も許す**（mix volume を 48 未満にする）。
- MOD 4ch の V15（左右の同時合計 ≤120）の検査は残す。

---

## 10. 形式ごとの書き出しの変更（`core/writer.py`・`s3m.py`・`it.py`）

各 writer の入力は Realizer の出力（`RealizedSong`: サンプル・pattern（`Cell` の格子）・order・チャンネルのパン・初期 BPM と Speed・楽器の付帯情報（エンベロープ・基準ノート））。writer は**換算をしない**（換算は Realizer）。各 writer に対応する parser・検査器も同じだけ直す（自作 writer と自作 parser が同じ誤解を共有しないよう、実プレイヤーの検査を必ず足す。DESIGN.md §2.4 の原則6）。

### 10.1 MOD

現行どおり。変更は、`Cell` の新しい表現からの書き出しと、新しく使うエフェクト（`7xy`・`Axy`）の許可だけ。

### 10.2 S3M

- サンプル: 8-bit unsigned（現行どおり）。**C2Spd ＝ その楽器の `N_ref`（C-4）での再生レート**（`rate_hz`。現行は finetune から求めた 8363 基準）。最大 65535。
- 1サンプルの長さは 64000 byte 以下（超えないよう §8.2 で倍率を下げる）。
- ノートカット `^^^`（254）を使う。新しいエフェクト: `Rxy`・`Dxy`・`S8x`。
- 上限: 16 チャンネル、99 サンプル、100 pattern、64 row。

### 10.3 XM

- **音量をボリューム列に移す**（`0x10 + vol`。現行はエフェクト `C`）。エフェクトの列が空くので、音量とビブラートなどを同じセルに書ける。
- **16-bit サンプル**: サンプルヘッダの type の bit 4、長さ・ループはバイト単位、データは 16-bit の差分（delta）符号化。
- 再生レート: 基準ノート C-4（ノート番号 49）で `rate_hz` になるよう、`relative note + finetune/128 = 12 × log2(rate_hz / 8363)` を整数部と 1/128 の端数に分けて書く（Amiga 周波数表のまま。D13）。**拡張音域で音高が合うことを要実測**（§13.4）。
- エンベロープ: `release_s` のある楽器だけ、音量エンベロープを有効にし（サステイン点で止まり、キーオフでリリース）、フェードアウトの値を `release_s` から決める。点の値と tick の換算は要実測。
- キーオフ: ノート 97。
- 上限: 32 チャンネル、128 楽器、256 pattern、1..256 row。

### 10.4 IT

- **楽器モードにする**（フラグの bit 2）。1サンプル＝1楽器、楽器のキーボード表は全ノートをそのサンプルの同じノートに対応させる。NNA は Note Cut（0）、DCT はなし（本設計では NNA を使わない。§18.2）。
- **16-bit サンプル**: サンプルのフラグの bit 1、Cvt の bit 0（signed）、非圧縮。
- **C5Speed ＝ 基準ノート C-5 での再生レート**（`rate_hz`）。
- エンベロープ: `release_s` のある楽器だけ音量エンベロープを有効にし、ノートオフ（`===`）でリリースする。
- フィルタ: `Zxx`（既定の MIDI マクロでカットオフ。埋め込みのマクロは書かない）。楽器の初期カットオフは使わない。**libopenmpt で効くことを要実測**。
- スライドの設定（Amiga スライド・Old Effects=1）は現行どおり（D13）。
- 上限: 64 チャンネル、99 楽器・99 サンプル、200 pattern、32..200 row（32 未満の扱いは §9.9）。

### 10.5 検査器（verify）の追加項目

| 形式 | 追加 |
|:---|:---|
| S3M | C2Spd の範囲、サンプル長 ≤ 64000、新しいエフェクトの param の範囲 |
| XM | ボリューム列の値の範囲、16-bit サンプル（長さが偶数バイト、delta の復号でループ境界が滑らか）、エンベロープの点の数と単調増加 |
| IT | 楽器ヘッダ（キーボード表がサンプル番号の範囲内）、16-bit サンプル、エンベロープ、pattern の row 数 32..200 |
| 共通 | ノート番号が形式の範囲内、サンプル番号が範囲内、全 lane の最初の発音にサンプル番号がある（現行 V07） |

---

## 11. MidiRealizer

### 11.1 方針

Score から直接 SMF を作る。トラッカー用の lane・ladder は使わない（予算の考え方が無い。全パートを入れる。ただし `channel_cap` は無視する）。`min_channels` に関係なく全パートを入れるかどうか: **入れる**（MIDI は「ジャンルの意図を GM 音源で聴ける」ことが目的で、厚い編成が意図そのもの）。

### 11.2 構造

- SMF format 1、**PPQ 480**（1 tick ＝ 20 MIDI tick）。Track 0: 曲名・テンポ（`TempoEvent` から）・拍子（区間の `Meter.signature`、可変拍子は小節ごと）。
- パートごとに1トラック。打楽器のパート（全楽器が `GmVoice(drum_note=)`）は MIDI ch 10。他はパートの宣言順に ch 1–9・11–16。足りなければ同じ program のパートで相乗りし、それでも足りなければ `PlanError`（現行と同じ）。
- 各チャンネルの頭で CC7＝127、ピッチベンドの幅（RPN 0）を ±2 半音。そのチャンネルに `Glide` があれば ±12 半音。

### 11.3 変換

| Score | MIDI |
|:---|:---|
| 音高 | `n + 36 + offset(楽器)`。`offset = 12 × log2(sounding_hz / hz(rate_note + shift))`（実音。現行 `midi._midi_pitch` と同じ）＋ `tune_cents`。整数でない部分はピッチベンド |
| 微分音 | 単音のパート: 発音ごとにピッチベンドを設定。和音や `poly>1` のパートでセントの違う音が重なる: セントの値ごとに別の MIDI チャンネル |
| 和音 | 構成音をすべて同時に発音（ストロークは tick をずらす） |
| 音量 | velocity ＝ `round(vel / 64 × 127)`（最小 1）。§9.10 と同じく最大が 127 になるまで持ち上げる |
| 長さ | `dur` があればそれ。無ければ同じ楽器の次の発音、ワンショットの自然減衰の長さ（MOD での秒数）、区間の終わり（ループ）のうち最も早いもの |
| スウィング | 奇数番目の step の発音を `long − 24 // steps_per_beat` tick 遅らせる（長さも調整） |
| `Vibrato` | CC1（深さに比例。現行の式）、次の発音で 0 |
| `Tremolo` | 無視 |
| `Arpeggio` | tick ごとに音を切り替える（現行 `timeline` の処理を移す） |
| `Glide` | ピッチベンドを到達時間で線形に動かす（**新**。現行は即時切替） |
| `Delay`・`Retrig`・`Cut` | 発音の時刻・再発音・note off |
| `Offset` | 無視（頭から鳴る） |
| `Automation volume` | CC11（パートが1チャンネルを占有するとき） |
| `Automation pan` | CC10 |
| `Automation cutoff` | CC74 |
| `Instrument.pan`・`Part.pan` | CC10 |
| サイドチェイン | 対象パートの CC11 |

検査: 現行 `midi.verify_midi` に加えて、同時発音数が GM1 の保証する 24 を超えたら WARN。

---

## 12. MP3

- Target は IT と同じ（予算 64・16-bit・44.1 kHz）で作り、IT のバイト列を一時ファイルに書いて ffmpeg に渡す（現行は XM）。
- コマンド: `ffmpeg -f libopenmpt -sample_rate 44100 -i tmp.it -af <音量> -c:a libmp3lame -b:a 320k -compression_level 0 out.mp3`。`compression_level 0` は LAME の `-q 0`（最も丁寧な符号化）。libopenmpt のオプション名は実装時に `ffmpeg -h demuxer=libopenmpt` で確かめる。
- 2パスの音量調整（DESIGN.md §7.8）はそのまま。

---

## 13. 検証とテスト

### 13.1 不変条件（テストで常に保証する）

| ID | 内容 | テストの置き場所 |
|:---|:---|:---|
| I1 | **骨格の不変**: 同じ genre・seed・tempo なら、どの形式の features で作っても、Score から奏法（`arts`）を除いたものが一致する | `tests/framework/test_invariants.py`（全ジャンル × seed 1〜3） |
| I2 | **決定性**: 同じ入力から同じバイト列 | 同上 |
| I3 | **全ジャンル × 全予算 × 全形式で生成でき、検査に ERROR が無い**: MOD は `mod_channels` の全キー、S3M・XM・IT は既定の予算と、`--channels` の上限をそのジャンルの `mod_channels` の最小値にした場合、MIDI は既定 | `tests/framework/test_all_genres.py`（ffmpeg 不要） |
| I4 | **実音の一致**: 全楽器について、音域の両端と中央の音を1音ずつ鳴らす曲を MOD・S3M・XM・IT で作り、libopenmpt で鳴らした基本周波数が §8.1 の基準（平均律）と 7 セント以内で一致する（MOD の Period の丸めが最大 5.9 セントなので、全形式で同じ許容値にする） | `tests/realplayer/test_pitch.py` |
| I5 | **テンポと長さ**: 各形式の曲を libopenmpt で鳴らした長さが Score の時間軸の長さと一致する（現行のテンポ検査を形式ごとに） | `tests/realplayer/test_tempo_real_player.py` |
| I6 | **音割れなし**: 全ジャンル×全形式で最大振幅 ≤ −0.5 dBFS（現行の検査を全形式に） | `tests/realplayer/test_clipping.py` |
| I7 | **高解像度の描画の同等性**: 全プリセットについて、m=1 と m>1 の描画を、m=1 のナイキスト以下の帯域で比べて、スペクトルの包絡の相関が閾値以上（閾値は実装時に決める） | `tests/unit/test_synth_hires.py` |
| I8 | **依存の規則**: `GmVoice` は `core/midi.py` から `core/model.py` に移す（`core/midi` は `core/model` から import する。互換のための再 export はしない）。そのうえで `genres/*.py` が `core` の形式系（writer・s3m・it・midi・render・verify・level）と `framework.realize` を import しない | `tests/framework/test_layering.py`（ast で検査） |
| I9 | **宣言の検査**: 全楽器に `gm`、`Kit.groups` が kit の全楽器を覆う、`mod_channels` のキー ⊂ {4, 6, 8}、`min_channels` ∈ {0} ∪ キー ∪ {それより大きい値}、`depends` に循環が無い | `Genre` のクラス定義時 |

### 13.2 テストの新旧対応

| 現行 | 扱い |
|:---|:---|
| `tests/unit/`（pitch・harmony・composer・dsp・synth・groove・automation） | 残す。synth は高解像度の描画のテストを足す |
| `tests/unit/test_engine.py`・`test_effects.py`・`test_it.py`・`test_s3m.py` ほか形式系 | 新しい writer・検査器に合わせて直す。`test_effects.py` は `encode.py` のテストに |
| `tests/profiles/test_*.py`（ジャンル固有の文法） | **Score を検査する形に書き直す**（形式に依存しないので、チャンネル番号や row ではなくパート名と step で書ける）。検査する内容（例: swing-jazz のライドの位置、march のスネアロール）は現行と同じ |
| `tests/profiles/test_stage3_genres.py` | `test_all_genres.py` と、ジャンルごとの「現行の MOD の編成と新しい編成の対応表」（§15.1）の検査に |
| `tests/regression/`（旧出力との一致） | 削除（D9）。代わりに F8 で**新しい出力の基準**を作る: 全ジャンル×全形式（MOD は全予算、MP3 は除く）× seed 1 の出力の SHA-256 を `tests/regression/golden.json` に保存し、一致を検査する。意図して出力を変えたときは `python tools/update_golden.py` で更新し、そのコミットで理由を書く |
| `tests/realplayer/` | 形式ごとの検査に組み替える（I4〜I6）。「MOD と他形式を比べる」検査は I4（実音）だけに残す |
| `tests/integration/`（CLI・GUI） | `--channels` の意味の変更と `--json` の追加項目に合わせて直す |
| 新規 | `tests/framework/`: ladder の単体テスト（§9.3 の計算例を含む）、lane の割当、row コマンドの置き場所、pattern の詰め込み、奏法の表現（形式ごと）、セルの衝突の規則（§9.6）、ループの停止（§9.7） |

### 13.3 試聴

- 移行の前に、現行の main で `listen_samples.py` を全形式で実行して**基準の曲**を保存する（`output/ref-main/`。git の管理外）。移植したジャンルは同じ seed の新しい曲と聴き比べる。
- 試聴の観点: 音色の印象（高解像度で明るくなりすぎていないか）、和音を声部に開いたときの音量の釣り合い、打楽器を分けたときの音量、予算で増えたパートの釣り合い。

### 13.4 要実測の一覧（実装の最初の段階で確かめる）

最初の3項目は F0 の段階で、残りは F4 で確かめた（結果は下の表の3列目）。

| 項目 | 確かめ方 | F0 の結果 |
|:---|:---|:---|
| XM・IT の 16-bit サンプルの読み込みと音量 | 同じ波形の 8-bit と 16-bit を libopenmpt で鳴らして振幅を比べる | **確認済み**。手組みの 16-bit XM・IT（1 サンプル・ループ）を libopenmpt で再生し、全音域で意図した高さ・振幅で鳴ることを確認した（下記2項目の測定がそのまま振幅・波形の健全性も示す）。XM は 16-bit でもサンプルデータの delta 符号化が必要（8-bit と同じ規約を 16-bit 語で適用。`core/writer._xm_delta_encode` は 8-bit 専用なので F4 で 16-bit 版を足す） |
| XM の relative note・finetune による再生レート、拡張音域の音高 | I4 の仕組みで、音域の端の音を含めて測る | **確認済み**。Amiga 周波数表のまま、relative_note（-24..+24 半音）・finetune（-128..127 の全域）・XM note（1..96 の全域）を振り、FFT（窓 1 秒、放物線補間）で測定。67 点中、音域の上端（XM note 96）と finetune の極値付近で最大 5.7 セントの誤差、残りは 3 セント未満。**全点が I4 の許容 7 セント以内**（放物線補間を使った自前の測定スクリプトは `tests/realplayer` の既存のゼロ交差法より精度が高い。本番の検査 I4 もこの精度の測定に変える） |
| S3M の C2Spd・IT の C5Speed を任意の値にしたときの音高 | 同上 | **IT で確認済み**（C5Speed 100〜65535、IT note 0..119 の全域で測定。最大誤差 2.1 セント）。S3M の C2Spd は IT の C5Speed と同じ関数（`s3m.c2spd`）を使っているので同じ結果が見込まれるが、**S3M は F4 で測った（§16.6 の「S3M の音高」）**。**設計への影響はない注意点が1件**: C5Speed を実用上あり得ない値（100 Hz 相当。本設計の `rate_hz` は常に `dsp.sample_rate()×oversample` 由来で実用域は約 4 kHz〜300 kHz）にすると、libopenmpt 側の下限処理と見られる挙動で意図しない高さが出た。実用域（4 kHz 以上）では再現しないので設計を変える必要はないが、F4 で IT・S3M の検査器に「C5Speed/C2Spd の実用下限（例 1 kHz）を下回ったら警告」を足すことを検討する |
| `Tremolo` の深さが形式間で一致するか | 長い音にトレモロを掛け、振幅の変動を比べる | **F4 で測定済み**。MOD・XM は一致。**S3M・IT は深さが正確に半分**（深さのニブル 2〜15 で比例）。`encode.Codec.tremolo` が S3M・IT の深さを 2 倍（上限 15）にして合わせる。MOD の深さ 8 以上は S3M・IT で頭打ち |
| 拡張音域の `Glide` の速さ | 1オクターブのグライドの到達時間 | **F7 で測定済み**。速さ 1 につき tick あたり「Amiga 換算の period（クロック ÷ 再生レート）」が 1 動く（MOD・S3M・XM・IT で同じ。S3M・IT は period の単位が 4 倍だがスライドも 4 倍）。1 オクターブ・7 半音のグライドが指定の step 数で届くことを 4 形式で確認した（誤差 0.12 秒以内。`tests/realplayer/test_glide_real_player.py`）。MOD の note は 0..35 の範囲なので「拡張音域」の外挿は要らない。詳細は §16.9 |
| XM・IT のエンベロープ（リリース）の時間 | キーオフから無音までの時間 | **F4 で測定済み**。点 `(0,64)`（サステイン）と `(release_s ÷ (2.5/BPM) tick, 0)` で、キーオフから振幅が 5% に落ちるまでが `release_s` に ±0.02 秒で一致（0.12・0.36・0.72 秒）。tick の換算は曲の**初期テンポ**で行うので、途中でテンポが変わる曲では長さがずれる |
| IT の `Zxx` が既定のマクロで効くか | 白色雑音にカットオフを掛けて帯域を測る | **F4 で確認済み**。`Z127`→`Z32` で重心周波数が 10.8 kHz → 3.2 kHz → 1.6 kHz → 0.8 kHz と単調に下がる（埋め込みマクロは不要） |
| IT の pattern の最小 row 数 | 16 row の pattern を書いて libopenmpt と OpenMPT で開く | **F4 で測定済み（libopenmpt のみ）**。12・16 row の pattern も正しい長さで再生できる。ただし IT の仕様の下限は 32 row なので、書き出しは設計どおり 32 row に詰めて最後の実際の row に `C00` を置く（OpenMPT・Schism での確認はしていない） |
| XM のキーオフ（エンベロープ無し）で音が止まるか | 長いループ音にキーオフ | **F4 で測定済み**。XM は止まる（次の 50 ms で 0）。**IT の `===` はエンベロープ無しでは止まらない**（振幅が変わらない）。したがって Realizer は `release_s` のある楽器だけに `NOTE_OFF` を使い、他は `NOTE_CUT`（IT・S3M）／音量 0（XM・MOD）で止める |

---

## 14. CLI・GUI・周辺

### 14.1 `--channels`

| 形式 | 指定できる値 | 意味 |
|:---|:---|:---|
| mod | 4・6・8（ジャンルの `mod_channels` のキー） | 予算そのもの。ジャンルに無い値は `ChannelCountError`（終了コード 2） |
| s3m・xm・it・mp3 | 1〜形式の上限 | 予算の上限。ladder がその中に収める（R5 で収まらなければ `ChannelCountError` として「このジャンルは N チャンネル以上が要る」と表示） |
| midi | 指定不可 | 引数エラー（終了コード 2） |

- `argparse` の `choices` は外し、値の検査は形式が決まった後に行う。
- `--genre random` と `--channels` の組合せ: MOD なら `mod_channels` に値を持つジャンルだけから選ぶ（現行と同じ）。他の形式なら、その上限で R5 に達しないジャンルだけから選ぶ。
- バナーには実際に使ったチャンネル数と予算を出す（例: `Channels   : 15 (limit 16)`）。再現コマンドには指定があったときだけ `--channels` を付ける（現行どおり）。

### 14.2 `--json`

- ジャンル一覧の各ジャンルに `"mod_channels": [4, 6, 8]`（選べる数）と `"channel_cap"` を足す。
- 形式の一覧に `"channels": {"choices": [4, 6, 8]}`（mod）／`{"max": 16}`（s3m）などを足す。
- 生成結果に `"channels"`（使った数）・`"channel_budget"`（予算）・`"sample_bits"` を足す。
- **GUI はこれらを読んでチャンネルの選択肢を作る**（形式を変えたら選択肢を作り直す）。GUI にジャンルや形式の値を書かない（DESIGN.md §12 の方針）。

### 14.3 その他

| 対象 | 変更 |
|:---|:---|
| `listen_samples.py` | 編成の項目（`<ジャンル>_<seed>_<数>ch`）は MOD だけで作る。`FMT` は現行どおり |
| `tools/calibrate_levels.py` | 新しい engine を呼ぶ。全ジャンル×{MOD の全予算, S3M, XM, IT}。IT はチャンネルが多く時間がかかるので、ジャンルを指定して部分的に作り直せる現行の機能を保つ |
| README（日・英） | MP3 が 320 kbps になったこと、XM・IT のサンプルが 16-bit・高レートになったこと、`--channels` の意味が形式で変わること |
| DESIGN.md | 実装後に本書を統合する（§2・§3・§4・§5・§6.14・§7 を書き直し、§6 の各ジャンルの「チャンネル」「編成」の記述を新しい宣言に合わせる） |

---

## 15. 各ジャンルの移植

### 15.1 移植の共通規則（現行 → 新）

| 現行 | 新 |
|:---|:---|
| `KIT` の項目 | `instruments`（`inst(preset_key, **changes)` で作る） |
| `CHORD_KITS = {prefix: (patch, strum_ms)}` | `instruments[prefix] = Instrument(patch)` とし、和音を鳴らすジェネレータに `strum_ms` を渡す。和音サンプルは Realizer が作る |
| `CHANNELS`・`DRUM_CHANNEL` | `parts` の並び（**現行の最も厚い編成の `ARRANGEMENTS` の並び**）。打楽器の論理チャンネル（`DRUM_CHANNEL` の行き先）は1つの Part にまとめ、`Kit.groups` を現行の論理チャンネルの区切りにする。`ChannelDef.priority` と `Fold.priority` は `Kit.priority` に1つにまとめる（グループの中の順序と、全部を1本にしたときの順序の両方が現行と同じになるように値を選ぶ） |
| 複数の役割が1チャンネルを共有（suspense の texture＝strings＋pizz など） | 1つの Part にして `Kit` で楽器ごとの lane を宣言する（打楽器でなくてもよい） |
| `ARRANGEMENTS` の 4/6/8 | 6ch・8ch で初めて現れるパートに `min_channels=6`／`8`。**ladder の結果が現行の編成と一致することを、ジャンルごとのテストで確かめる**（下の「編成の対応表」）。一致しない場合は、ladder の結果を採用してよい（D9）が、差をジャンルの移植メモに書き、試聴で確かめる |
| `CHANNEL_WEIGHTS` | `mod_channels`（編成を選ばないジャンルは `{N: 1}`） |
| `Section(kind, prog, intensity, parts, groove, key_offset, fill, crash, lead_motifs)` | `Section(prog=, intensity=, parts=, groove=, key_offset=, fill=, crash=, motifs=)`。`parts` に混ぜていたパート名でない印（`"kime"`・`"spic"`・`"glass"` など）は `tags` に移すか、独立した Part にする |
| `rows_per_measure`・`MEASURES_PER_PATTERN`・`variable_meter`・`ChordSlot.rows` | `Section.meter`・`Section.measures`・`Section.measure_steps` |
| `rows_per_beat`・`SWING = SwingConfig(l, s)` | `Meter.steps_per_beat`・`Genre.swing = Swing(l, s)` |
| `ECHO = (EchoSpec(src, dst, ...),)`・`LAYERS = (LayerSpec(key, ch, follow=...),)` | `Part("<名前>", Echo(delay, ratio, repeats), follow="<src のパート名>", min_channels=…)`・`Part("<名前>", Layer(key, ...), follow="<follow>", min_channels=…)`。`EchoSpec.offs` は常に真として扱う（§7） |
| `SIDECHAIN = ((key, ch, ratio, rel), ...)` | `mix = (Sidechain(triggers=(key,), targets=(パート名,), ratio, rel), ...)` |
| `LATE`・`HUMANIZE` | `Groove(..., late=, humanize=)` |
| `extra_measure` | 独立した Part とジャンル内のジェネレータ（推奨）。パートをまたぐ編集だけ `finalize_section` |
| `buf.replace(...)`（他のパートを上書きする「決め」など） | `finalize_section` で `score.mute(parts, start, end)` してから `score.add(...)` |
| `inst.off()`・`_silence` | `dur`・`ctx.off`。区間の頭の停止は不要（§9.7） |
| `inst.cell(effect=0x4, param=p)` | `arts=(Vibrato(p, at=…),)` |
| `groove.delay_param(t)`（EDx） | `Delay(t)` |
| `groove.retrigger_param(t)`（E9x） | `Retrig(t)` |
| `automation.portamento_param(...)`（3xx） | `Glide(steps=…)`（鳴り終わった先行音の扱いは Realizer。§5.3） |
| `inst.cell(n, effect=0, param=chord.arp)`（0xy） | `Arpeggio(x, y)` |
| `mixer.sample_offset_param(...)`（9xx） | `Offset(fraction)` |
| 音量だけのセル `Cell(None, 0, vol=v)` | `ctx.automate(step, "volume", v)` |
| `TempoCurve`・`render_tempo_curve` | 部品 `tempo_curve(ctx, start_bpm, end_bpm, start_step, end_step, kind)`（`ctx.tempo` を step ごとに呼ぶ） |
| `resolve_micronote` と finetune ごとの派生サンプル（maqam・gamelan） | 書かれた音高の小数部（`MicroScale.absolute_cents` から求める補助 `pitch_from_cents`） |
| `dataclasses.replace(spec, pan=...)`・`finetune=` の派生（orchestral の vln2 など） | `Instrument(pan=…, tune_cents=…)`。finetune 1 単位＝12.5 セント（1/8 半音） |
| `shift` を変えた派生（orchestral の vla・vc・cb） | `Instrument(dataclasses.replace(patch, shift=…))`（現行と同じ） |
| row 0・最終 row の空きを作る工夫（classical の `finalize_pattern`、swing-jazz の intro の休符、minimalism の row 1 のアクセント） | 削除してよい（Realizer の責任）。音楽上の意味もある場合（minimalism）は残す |
| `GM`・`GM_DEFAULTS` | `Instrument.gm`（`inst()` が `gm_default(patch)` で既定値を入れる。上書きは引数で） |

**編成の対応表のテスト**: 移植の間だけ、ジャンルごとに「現行の `ARRANGEMENTS` の各編成のチャンネル名の並び」と「新しい ladder の lane の並び」を対応させた表を `tests/framework/port_layouts.py` に書き、一致を検査する（差を認めたジャンルはその旨を表に書く）。**並びに加えて、畳んだ結果も比べる**: 同じ seed の打楽器のパートについて、現行の MOD の各編成で打楽器のチャンネルに残った（楽器, row）の集合と、新しい Realizer の lane に残った集合が一致すること（優先度の表の写し間違いを見つけるため。`Kit.single_priority` が要るジャンルはこれで分かる）。移行が終わったら、表は「新しい編成の期待値」のテストとして残す。

### 15.2 グループと作業の性質

| グループ | ジャンル（数） | 作業 |
|:---|:---|:---|
| A: 宣言だけ | cool, dreamy, focus, hiphop, house, lofi-chill, lofi-hiphop, melancholic, neo-soul, pop, rnb-soul, synthwave, warm（13） | §15.1 の規則で宣言を写す。半ば機械的にできる |
| B: パートの上書きあり | acoustic-ssw, ambient, ambient-drone, anime-ost, bossa-nova, calm, chiptune, cinematic, city-pop, classical, dark-tense, edm, energetic, folk, gamelan, indie-rock, industrial, jazz, jpop-80s, jrock-90s, jrpg, racing-breaks, rock, techno, trailer, uplifting（26） | 宣言を写し、上書きしていたメソッドをジャンル内のジェネレータ（または部品の引数）に書き直す（§15.3） |
| C: 個別実装 | nostalgic, suspense-slow, suspense-chase, march, swing-jazz, prog-rock, trap, future-bass, maqam, free-jazz, minimalism, orchestral（12） | 文法をジャンル内のジェネレータに移す（§15.4） |

### 15.3 グループ B の移植メモ

| ジャンル | 現行の上書き | 新しい書き方 |
|:---|:---|:---|
| acoustic-ssw | `comp`: トラヴィス奏法（親指が根音と5度、他の指が裏で上声） | ジェネレータ `Travis`（ジャンル内） |
| ambient | `extra_measure`: glass（区間頭に3度か7度の長音）、bell（確率で1〜2音） | Part `glass`（`tags` の `"glass"` で鳴らすかを決める）・Part `bell` |
| ambient-drone | `compose_measure` を全部置き換え: drone・5度・上声の長音と、4小節周期のうねり（音量だけのセル） | Part `drone`・`fifth`・`upper`・`swell`。うねりは `ctx.automate("volume")` |
| anime-ost | `lead_key`（区間で楽器を持ち替え）、`compose_measure`（outro の最後を決めで終わる）、`extra_measure`（決め・スピッカート・ブラスの停止） | `Lead(inst_for=…)`。決めは Part `kime`（brass）と `finalize_section` で bass・comp・drums の該当 step を `mute` して決めの音を `add` |
| bossa-nova | `drums`（クラーベの rim を足す）、`bass`（付点4分＋8分）、`comp`（2小節で異なるギターの型） | `Groove` に rim の型を足す、ジャンル内 `BossaBass`・`BossaComp`。2/4（`Meter(8, 4, (2, 4))`、`measures=8`） |
| calm | `extra_measure`: ベル | Part `bell` |
| chiptune | `extra_measure`: パルス波の和音を全 row の `0xy` で、区間末のジャンプ音 | Part `arp`（`Arpeggio(x, y, steps=…)`。和音の種類の構成音から x・y）、Part `jump`。`channel_cap=4`（厚くしないことがジャンルの性格） |
| cinematic | `extra_measure`: viola（和音）・cb・horn（3度）・timp（ロール・スウェル） | Part `viola`（`Pad` で chordal）・`cb`・`horn`・`timp` |
| city-pop | `pad`: エレピを2拍ごと | `Comp(kind="half")` 相当の引数で済むか確認し、済まなければジャンル内 |
| classical | `compose_measure`（vc の低音、vln2・vla の刻みを直前の音に近い構成音で）、`finalize_pattern`（D00 の空き） | Part `vc`・`vln2`・`vla` のジャンル内ジェネレータ（状態は `ctx.state`）。`finalize_pattern` は削除。`Meter(12, 4, (3, 4))`、`measures=4` |
| dark-tense | `extra_measure`: braam・riser・impact | Part `braam`・`fx` |
| edm・uplifting | `extra_measure`: ビルドアップ（`buildup`）、ドロップの impact | 部品 `Buildup` を Part `perc` に、Part `fx` |
| energetic・jrock-90s | `comp`: パワーコードの8分 | ジャンル内 `PowerChop`（和音 `(0, 7, 12)` の NoteEvent にすると、大きな予算で声部に開かれる） |
| rock | `comp`: パワーコードのリフ（根音を刻み、2小節ごとに5度・短7度へ） | ジャンル内 `RockRiff` |
| folk | `lead`: フィドルの前打音（直前の row が空いている音に確率で1つ上の音階音） | `Lead` の後処理として `GraceNotes(prob)` を部品化（2ジャンル以上で使う見込みがあれば部品集へ。今は folk 内） |
| gamelan | `plan`（音階・balungan を選ぶ）、`extra_measure`（saron・peking・bonang・kenong・kempul・gong を度数から） | `plan()` の上書きはそのまま。各楽器を Part にし、音高は `pitch_from_cents`（finetune の派生サンプルは不要になる） |
| indie-rock | `plan`（半数の seed で4つ打ち）、`drums`（groove の差し替え） | `plan()` の上書きで `extra["disco"]`、`Groove(groove_name=…)` |
| industrial | `begin_pattern`（リフを選ぶ）、`extra_measure`（金属パイプのリフ） | Part `pipe`（区間頭でリフを選んで `ctx.state` に） |
| jazz | `compose_measure`（coda のフェルマータ） | 各パートのジェネレータが `section.kind == "coda"` を見る代わりに、`finalize_section` で coda の後半を `mute` してフェルマータの和音を `add` |
| jpop-80s | `pad`: シンセブラスの決め（短い3連打）と伸ばし | ジャンル内 `BrassKime` |
| jrpg | `lead_key`、`lead`（2小節目は1小節目を1音階上げる）、`extra_measure`（timpani・fanfare・counter） | `Lead` を継承したジャンル内 `SequenceLead`（前の小節の音符は `ctx.state` に持つ。現行のように buf から読み戻さない）、Part `timp`・`brass` |
| racing-breaks | `plan`（系統）、`_pattern_plan`（次の和音の根音）、`drums`・`bass`・`comp` | `plan()` の上書きで `extra["family"]`。次の和音の根音は `MeasurePlan.next_chord` で読めるので `_pattern_plan` は不要。`Groove(groove_name=lambda sec: f"{family}:{sec.groove}")`、ジャンル内 `BreaksBass`・`BreaksComp`（`wobble` は `Vibrato(0x22, at=1)`） |
| techno | `extra_measure`: 4小節ごとに発音位置を入れ替えるシーケンス | Part `seq` のジャンル内ジェネレータ（`pattern.index` の代わりに区間の作成順の番号を `ctx.plan` から） |
| trailer | `compose_measure`（final の2小節目で持続音を止める）、`extra_measure`（taiko・braam・impact・スピッカート・ビルドアップ・タム） | `finalize_section` で final の後半を `mute`、各要素を Part に |

### 15.4 グループ C の移植メモ

いずれも DESIGN.md §6.1〜6.13 の音楽的な内容を保つ。乱数の消費順は変わってよい（D9）。

| ジャンル | パート（並び＝重要度） | ジャンル内のジェネレータ・要点 |
|:---|:---|:---|
| nostalgic | drums（kit: kick・snare・hihat）、bass、pad、melody | 和音は手組みの `ChordDef(explicit=True)` なので `harmony=None` とし `plan()` で `MeasurePlan.chord` を作る。旋律は現行 `_melody_bar` をジェネレータに移す。旧挙動 Q1〜Q7 は保たない（Q4 の未使用の flute は楽器から外す。Q3 の pad の −17.6 セントは音色の値の問題なので本移植では変えない）。`tempo_policy="profile"`・`rng_mode="single"`・`strict_buffers=False` の概念は無くなる |
| suspense-slow・suspense-chase | pulse（kit: heart・anvil・swoosh。優先度 anvil＞swoosh＞heart）、drone、texture（kit: strings・pizz。pizz が優先）、lead（kit: lead・pizz。pizz が優先） | 共通の補助（音色・進行・語彙）は `profiles/suspense.py` に移す（ジャンルではない）。dropout・スタブ・衝撃の位置は `plan()` の上書きで決めて `SectionPlan.extra` に置き、各パートが読む。silence run と「衝撃の前 8 row は鳴らさない」は `finalize_section` の `mute`。swoosh の開始 step・anvil の消音の step は `ctx.bpm`・`ctx.step_seconds()`・`ctx.inst_seconds()` から（現行 `swoosh_start_row`・`anvil_clear_row`・`oneshot_off_row` の式） |
| march | drums（kit: bd・sd・crash。crash＞sd＞bd）、tuba、harm（kit: horn・section。section が優先）、picc | Oom・Pah・ファンファーレ・フレーズ（`[a, a', b, c, a, a', b, cad]`）をジェネレータに。スネアロールは `prio=2` の sd で通常のスネアに勝たせる（現行の `replace`）。horn の `0xy` は `Arpeggio`（`chord.arp` から）。pattern 末の消音は不要。`Meter(8, 4, (2, 4))`、`measures=8` |
| swing-jazz | drums（kit: ride・brush）、bass、piano、sax | `Meter(8, 2)`、`swing=Swing(14, 10)`、`measures=8`。ウォーキング（次の和音の根音へ。`MeasurePlan.next_chord`）、Charleston のコンプ（`Arpeggio` で刺す）、sax の `Retrig(5)`。intro の row 0 を空ける工夫は削除 |
| prog-rock | drums（kit: kick・snare・crash）、bass、gtr、lead | `Section.measure_steps=(14, 14, 10)`（verse 等）、chorus は `(16,)*4`、breakdown は `(10,)*6`。リフの動機は `m.steps` で引く。パワーコードは和音 `(0, 7, 12)` の NoteEvent（大きな予算では声部に開かれる） |
| trap | k808、snare、hat（kit: hat_c・hat_o。open が優先）、lead | `Meter(32, 4)`（現行は `rows_per_measure=32`・`rows_per_beat=4`（既定）。1小節が8拍で、表示 BPM はハーフタイムの慣習。DESIGN.md §5.5）、各区間 2 小節（＝64 step）。808 のグライドは `Glide(steps=1)`（先行音が鳴り終わっていれば発音に変える規則は Realizer。§5.3）。ハットのロールは `Retrig(3)` |
| future-bass | kick（kit: kick・clap。clap が優先）、sub、chord、vox | vocal chop は `Offset(i / N_SLICES)`。サイドチェインは `Sidechain(("kick", "clap"), ("sub",), 0.25, 3)` と `Sidechain(("kick", "clap"), ("chord",), 0.35, 4)` |
| maqam | perc（kit: dum・tek）、oud、nay、qanun | 中立音程は `pitch_from_cents(RAST_ON_G.absolute_cents(...))`。`oud_n3`・`oud_n7` の派生は不要（Realizer の変種）。`_maqam_phrase` をそのまま使う |
| free-jazz | piano、bass、sax、perc | 密度の確率で step ごとに鳴らす。テンポカーブは部品 `tempo_curve` で、`--tempo` は開始 BPM（カーブ全体を `開始 BPM / 96` 倍。現行どおり）。`tempo_range` は現行の値 |
| minimalism | piano、marimba、vibes、wood | `Meter(48, 4)`、各区間 1 小節（16 区間）。周期の表を `polymetric_row` で引く（乱数なし）。woodblock の row 1 のアクセントは残す |
| orchestral | vln1、vln2（`tune_cents=+37.5`）、vla（`shift=−7`）、vc（`shift=−12`）、cb（`shift=−24`）、ww、brass（kit: horn・trumpet。trumpet が優先）、perc（kit: timpani・cymbal。cymbal が優先） | 6声のボイシング（`voice()`＋残り3声の導出）を区間ごとのジェネレータで。intensity で区間の音量。`mod_channels={8: 1}` |

### 15.5 移植の後に検討する opt-in の候補（本作業の範囲外）

移植が終わり、試聴で基準と比べてから、ジャンルごとに足すかどうかを決める（D14）。

| 候補 | ジャンルの例 | 使う機能 |
|:---|:---|:---|
| フィルタのスイープ | racing-breaks・edm・house・techno | IT の `Automation("cutoff")` |
| エレピのトレモロ（現行の `4xy` の揺れの代わり） | racing-breaks・city-pop・neo-soul | `Tremolo`（全形式で使えるようになった） |
| パッド・弦のリリース | ambient・calm・dreamy・cinematic・orchestral | `Instrument.release_s` |
| リードのステレオの重ね | synthwave・uplifting・edm | `Part.double` |
| 大きな予算でだけ鳴らす声部（ディヴィジ、対旋律、パーカッションの追加） | cinematic・trailer・orchestral・jrpg | `min_channels=12` などのパート |
| 長い音の持続的なビブラート（現行は1 row だけ） | 旋律のある全ジャンル | `Vibrato(steps=…)` を大きくする |

---

## 16. 実装計画

### 16.1 ブランチと切り替え

- 作業はブランチ `framework-redesign` で行う。main は移行が終わるまで現行のまま（main への部分的なマージはしない）。
- ブランチの中では、新しいフレームワークを `mod_weaver/framework/` に、作り直したジャンルを `mod_weaver/genres/` に置き換えていく。移植の途中は、`engine` が「新しい `Genre` なら新しい経路、古い `GenreProfile` なら古い経路」で呼び分ける（ブランチの中だけの一時的な分岐。F8 で削除）。
- 各フェーズの終わりにテストがすべて通ること。

### 16.2 フェーズ

| フェーズ | 内容 | 参照 | 完了の条件 |
|:---|:---|:---|:---|
| F0 準備（**完了**） | ブランチを作る。現行 main で全形式の試聴用の曲を作って保存（§13.3）。§13.4 の要実測のうち、XM・IT の 16-bit と再生レートの実験を先に行う（設計の前提が崩れないかの確認） | §13.3・§13.4 | 基準の曲がある。16-bit・任意の再生レートが libopenmpt で意図どおり鳴る。**結果: 両方とも確認済み（§13.4）** |
| F1 core（**完了**） | `SampleSpec` の拡張、`synth.render(oversample, bits)`、`dsp` の係数の換算、`chord_patch` の移動と一般化、`GmVoice` の `core/model.py` への移動、描画のキャッシュ | §8・§13.1 I8 | I7 が通る。既存の synth のテストが通る。**全プリセットの描画時間を m=1 と S3M・XM・IT の倍率で測り、1曲の生成時間を見積もってディスクキャッシュの要否を決める**（§8.6）。**結果: I7・既存テストとも通過。44.1kHz 相当（m≈2.66・bits=16）での全39 BandProfile ジャンルのサンプル合成時間を実測し、最悪値は gamelan の 1.15〜1.2秒（22 楽器、ゴング等の長い減衰音が複数）。NFR-3 の目安 2 秒を下回るので、ディスクキャッシュは入れない（プロセス内キャッシュのみ実装）。挙動が変わって遅くなった場合は §8.6 の設計のまま追加できる** |
| F2 framework（作曲側、**完了**） | `target.py`・`score.py`・`plan.py`・`genre.py`・`context.py`・`compose.py`・部品集 `gens/` | §4〜§7 | 架空の小さなジャンルで Score が作れる。部品のテスト（現行 `band_common` の型と同じ row・音量・確率が出る）。**結果: 両方とも確認済み（§16.4）** |
| F3 TrackerRealizer（MOD）（**完了**） | lanes・ladder・セル化・音の終わり・ミックス・row コマンド・pattern。MOD の writer の対応。試験的に pop（A）・racing-breaks（B）・march（C）を移植 | §9・§10.1 | 3ジャンルが MOD の全予算で生成・検査に通る。§9.3 の計算例のテスト。基準の曲と聴き比べて問題が無い。**結果: `mod_weaver/framework/realize/`（lanes.py・samples.py・tracker.py）を実装。pop・racing-breaks は 4/6/8ch、march は現行どおり 4ch 専用で全て生成・検査（0 ERROR）が通る（seed 1〜5 で確認）。ladder の結果が現行 ARRANGEMENTS のチャンネル数と一致（§16.5）。`output/f3-trial/*.mod` を生成済み、ユーザーの試聴待ち。詳細・設計の隙間は §16.5** |
| F4 S3M・XM・IT・MP3（**完了**） | writer・parser・検査器の拡張、Realizer の形式ごとの表現、IT 経由の MP3 | §9.6〜9.7・§10・§12 | 3ジャンルで I3〜I6 が通る。**結果: 3ジャンル × S3M・XM・IT（MOD は F3 と同じ経路に載せ替え）で I2・I3・I5・I6 が通り、I4（実音）は全プリセットのうち測れる34音色 × 4形式で通る（許容は XM・IT 7 セント、MOD 9、S3M 12。理由は §16.6）。MP3 は IT 経由 320 kbps。§13.4 の F4 の実測項目は Glide を除き完了。`output/f4-trial/` に試聴用を生成済み（ユーザーの試聴待ち）。詳細・設計の隙間は §16.6** |
| F5 MIDI（**実装完了・GM 音源での試聴待ち**） | `MidiRealizer` | §11 | 3ジャンルの MIDI が検査に通り、DAW（または GM 音源）で鳴らして意図どおり。**結果: `framework/realize/midi.py`・`core/native_midi.py`。3ジャンルが検査（ERROR 無し）・決定性・長さ（Score の時間軸と tick 単位で一致）を満たし、音高の式は実プレイヤーで測った実音と一致する（34音色）。この環境に GM 音源が無いので実際に鳴らしての確認は未実施（`output/f5-trial/*.mid` を生成済み）。詳細は §16.7** |
| F6 A・B の移植（**実装完了・試聴待ち**） | 37ジャンル（試験の2つを除く） | §15.1〜15.3 | I1〜I3、編成の対応表のテスト、ジャンル固有の文法のテスト（Score で書き直したもの）。**結果: A 13・B 26（試験の pop・racing-breaks を含む）の計 39 ジャンルを `mod_weaver/genres_next/` に移植し、`tests/framework/test_ported_genres_all.py`（I1・I2・I3・全パートが鳴る・編成の対応表・折り畳みの優先度・旧版のジャンル別テストの書き直し）と `tests/realplayer/test_ported_genres_real_player.py`（I5・I6）が通る。旧版との差と、F6 で足したフレームワークの機能は §16.8** |
| F7 C の移植（**実装完了・試聴待ち**） | 12ジャンル（試験の march を本番に昇格した分を含む） | §15.4 | 同上。**結果: 12 ジャンルを `mod_weaver/genres_next/` に移植し、全 51 ジャンルが新しい枠組みに載った。F6 の共通検査（I1〜I3・全パートが鳴る・I5・I6）に加えて、ジャンル固有の性質（`tests/framework/test_ported_genres_c.py`）、`Glide` の速さを 4 形式の実プレイヤーで測る検査（`tests/realplayer/test_glide_real_player.py`）が通る。F7 で足したフレームワークの機能と旧版との差は §16.9** |
| F8 仕上げ | engine・cli を新しい経路だけにし、旧コード（§2.4 の「捨てる」）を削除。音量の実測（`calibrate_levels.py`）、出力の基準（`golden.json`。§13.2）、`listen_samples.py`、GUI、README、DESIGN.md への統合と DESIGN_HISTORY.md への経緯の記録、本書の削除 | §14 | 全テスト（realplayer を含む）が通る。全ジャンルを試聴し、ユーザーの確認を得てから main にマージ |

### 16.3 作業量の見積もり

このプロジェクトのこれまでの進み方（35ジャンルと BandProfile を設計を含めて1日、全体で約5日）を基準に、**約 8〜11 日**（F1〜F2 で 2〜3 日、F3 で 1〜1.5 日、F4〜F5 で 2〜3 日（3形式の writer・parser・検査器の拡張と §13.4 の要実測9項目、MIDI Realizer）、F6 で 1〜1.5 日、F7 で 1.5〜2 日、テストと文書は各フェーズに含む）。これとは別に、試聴にユーザーの時間がかかる（51ジャンル×3曲×約2.3分で、1形式あたり約6時間）。

### 16.4 F2 の実装で埋めた設計の隙間

本章・§4〜§7 のコード片は「インターフェースの仕様」（§0）であり、実装時に次の点を具体化した。F3 以降で
同じ名前・考え方を前提にしてよい。

- **`SectionCtx`/`MeasureCtx` に `genre: Genre` を持たせた**。§6.6 の属性一覧には無いが、``ctx.note()`` が
  楽器の存在・音程の有無を検査する（`genre.instruments`）のに必須で、`BassLine`・`Comp`（非和音）・`Lead`
  が音域を引く（`genre.harmony.registers.*`）のにも使う。
- **`Section.parts` の既定値 `ALL`**（§6.3）は具体的な名前の集合を持てない（`Section` 単体はジャンルの
  `parts` 宣言を知らない）ので、空の frozenset を予約値にし、`plan.default_plan()` が
  `Genre.parts` から「`follow` を持たないパート名の全部」に展開する。
- **`framework/registry.py` を新設**した。§2.4 の「そのまま残す」は現行 `profiles/registry.py`
  （`GenreProfile` 用）を指しており、`Genre` 用の登録簿はそれとは別に要る（移行が終わるまで2つの登録簿が
  並行する。F8 で旧い方を削除する）。
- **`MeasureCtx` は `SectionCtx` を属性委譲で包む**実装にした（独自の `__init__` を持ち、`plan`・`song`・
  `rng`・`state` 等は `__getattr__` で親に委譲し、`note`/`off`/`automate`/`tempo`/`_check_step` だけ
  ``m.start`` を足して上書きする）。`state`・`song_state` は辞書への参照なので、委譲経由でも書き込みが
  正しく親に反映される。
- **Score の検査（§6.9 の4）のうち `poly` 超過の判定**は、`dur=None` の発音を「次の同じ楽器の発音まで」と
  見なす区間重なりの掃引で行う（lane の実際の割当は F3 の Realizer の仕事なので、ここでは粗い近似）。
- **部品の一部に、表の引数名と違う名前を付けた**（表は「インターフェースの仕様」であって逐語的なシグネチャ
  ではない。§0）: `Arp` は表の `steps`（打点の row 集合）と `MeasurePlan.steps`（小節の step 数）が紛らわし
  いので `steps: tuple[int,...]` のまま残しつつ、本文中の表記は変えず実装側のコメントで区別した。
  `Groove` は `grooves: Mapping[str, GroovePattern]` とし、`Hit` の列の型エイリアスは `GroovePattern`
  という別名にした（ジェネレータのクラス名 `Groove` と型名が同じだと Python の名前空間で衝突するため）。
- **`Layer`・`Echo` は `Part.follow` を自分では読まない**（フレームワークが「鳴る区間」を判定するので、
  `Echo.section()` は `ctx.part.follow` からソースのパート名を引いて `ctx.events_of()` するだけで書ける）。

### 16.5 F3 の実装で埋めた設計の隙間

`mod_weaver/framework/realize/`（`lanes.py`・`samples.py`・`tracker.py`）として実装した。F4 以降も
同じ名前・考え方を前提にしてよい。

- **Cell の表現は F3 では一般化しなかった**。§9.6 の形式ごとの汎用 Cell は作らず、既存の
  `core.model.Cell`/`Pattern`/`Song` をそのまま使い、`TrackerRealizer.realize_mod()` は
  `(Song, WriteOptions)` を返すところまでを担う。実際の `serialize()`/`verify()`/`write_file()` は
  呼び出し側が既存の `core.formats`/`core.writer` で行う（F3 は MOD 専用なので、MOD 固有の型を直接
  使うほうが単純で、無用な抽象化を避けられる。汎用化は S3M/XM/IT が実際に必要になる F4 で行う）。
- **`NoteEvent.chord` は根音（オフセット0）を含む**。§5.1 の説明文は「根音からの半音の列」とだけ
  書いてあり、根音自体を含むかどうかが曖昧だったが、既存の `gens/comp.py` 等が
  `chord=CHORD_QUALITIES[quality]`（例 `(0, 4, 7)`）をそのまま渡す実装になっていたため、「含む」で
  統一した（和音の声部数は `len(chord)`。`len(chord)+1` ではない）。`core.synth.chord_patch()` の
  `intervals` も同じ規約（根音を含む）。
- **`Kit` に `group_pan: Mapping[str, int]` を追加**した。§6.3 の `Kit` にはグループごとのパンが無く、
  「分ける」段階の lane のパンが全部 `Part.pan` 頼みになってしまう（pop の hat 系を kick/snare 系と
  別のパンに振れない）。グループ名→パンの表を足し、「分ける」段階は楽器の属するグループのパン、
  「1本」の段階は `Part.pan` を使う。
- **sample 番号の上限（31。MOD）を `samples.py` で検査する**。§9.3 の ladder は**チャンネル**予算だけを
  扱い、サンプル予算は別の制約として `plan_samples()` の最後で `len(order) > target.sample.max_samples`
  を見て `PlanError` にした（ladder の段階を遡ってサンプル数を減らす仕組みは作っていない。F3 の3ジャンル
  はどの予算でも十分少ないため実害は無いが、将来多楽器のジャンルで31を超えたら、ジャンル側で
  `Kit` のグループをまとめるか和音を減らす必要がある）。
- **MOD の音高は整数の tracker note に丸める**。`NoteEvent.pitch` の小数部（セント）は、MOD の
  `Cell.note` が標準の36音の Period 表しか持てないため実現できない（S3M/XM の fine `instrument`
  単位での微調整や、IT の高分解能な note は F4 で検討する）。F3 の3ジャンルはいずれも整数の音高しか
  使わないため実害は無い。
- **row 0 にテンポ／Speed を書けない区間への対策**: §9.9 の想定どおり row 0 の全チャンネルが
  埋まっていることがあり得るため（密な打楽器編成等）、`_insert_near_start()` が先頭 8 row の中から
  空きを探す（旧 `core/groove.py` の「row 0 に空きを残す契約」は新フレームワークのジャンルには課さない）。
- **サイドチェインのダッキングは簡略化した**: `_apply_sidechain()` は、ダッキング対象の各 row で
  「今その lane に設定されている音量」を遡って求め、それを `ratio`/`release_steps` で減衰させる。
  トリガーが密集する（ダッキングの区間が重なる）ジャンルでは、2つ目のトリガーが「既にダッキング済みの
  音量」を基準にさらに下げてしまい、意図より下がりすぎることがある（racing-breaks はトリガーの間隔が
  十分あるため実害は無い）。本当の「元の音量を基準にした重ね合わせ」が要るジャンルが出たら、
  重ならないよう `release_steps` を調整するか、ここを拡張する。
- **`Glide` の速度が指定なしのときの既定値**: `Glide.param` が `None` のとき、本来は直前の音の
  period から `automation.portamento_param()` で計算すべきだが、Score 層は period を持たない
  （lane に実際に割り当てるまで前の tracker note が決まらない）。F3 時点でどのジャンルも `Glide` を
  使わないため、最小値（1）を既定にするだけに留めた。**F7 で解決した（§16.9: lane 割当後に直前の音から計算する）**。
- **`follow` 先を持たないジェネレータ（`Echo` 等）の lane は `insts=()` になる**。`Echo` は
  自分の楽器を持たず、写した元のイベントの楽器名をそのまま使うため、lane 構築時に `Part.gen.inst`
  を引けない。実際の発音は `Placement.inst`（イベントごとの実際の楽器名）で解決するので実害は無いが、
  `samples.py`・`lanes.py` の「lane の insts からサンプル／パンを引く」経路はこの種の lane では
  空振りする（follow 元の楽器が既に自分の lane で同じサンプルを持っているので問題にならない）。
- **march は `Harmony`/`default_plan()` を使わない**。進行の和音ごとの小節数が不揃い（sousa の最後の
  和音だけ2小節）で、`default_plan()` は小節数を和音の数で均等に割る前提のため使えない。nostalgic と
  同様 `harmony=None` とし、`plan()` を全面的に上書きして `SectionPlan` を直接組み立てる
  （§15.4 に明記はなかったが、suspense 系も同じ理由で同じ扱いになる見込み）。
- **試験移植した3ジャンルは `mod_weaver/genres/` に置かず、`tests/framework/realize/genres/`
  に置いた**。旧 `GenreProfile` 版と id が同じだが、新旧で登録簿が別なので実害は無い。F6・F7 で
  本物の移植をするときに、この3ファイルを本番の場所へ移して書き直す（置き場所の都合で書いた
  コードなので、そのまま昇格はしない）。
- **ladder の R2（kit を「まとめる」）は全 kit パートをまとめて1段階で適用する**。§9.3 の表が
  R1・R3・R4 とだけ「後ろから一つずつ」と書き、R2 にはその注記が無いことを文字どおりに解釈した
  （pop・racing-breaks は kit パートが1つしか無くこの解釈でしか検証できていないので、複数の kit
  パートを持つジャンルが出たら、ladder の結果を見て意図どおりか確かめること）。
- **3ジャンルの生成例と検査結果**: `tests/framework/realize/test_ported_genres.py`
  （`test_generate_reference_files_for_listening`）が `output/f3-trial/*.mod` を書き出す。ユーザーが
  実際に試聴して確認する（ffmpeg が使えるサンドボックスでは同じ内容を `.mp3` にも変換できる）。

### 16.6 F4 の実装で埋めた設計の隙間

S3M・XM・IT・MP3 を `core/native*.py` と `framework/realize/{encode,tracker,samples}.py` として実装した。F5 以降も
同じ名前・考え方を前提にしてよい。

**構成**

- **MOD も同じ経路に載せ替えた**。`tracker.realize()` が全トラッカー形式で `core.native.RealizedSong`（サンプル・
  `RGrid` の pattern・order・パン・初期 BPM と Speed・`sample_release`）を返す。MOD は `native.to_mod_song()` で
  既存の `model.Song` に変換して既存の `core/writer.serialize` に渡す（`realize_mod()` は F3 の形を保つ薄い入口）。
  §9.6 の汎用 Cell は `core/native.py` の `RCell`（`note`・`sample`・`vol`・`fx`）として実装した。旧 `model.Cell`・旧 writer・
  旧パーサ（`s3m.py`・`it.py`・`writer.serialize_xm`・`verify.py`）は F8 まで並行して残る（パーサは新しい検査器が再利用する
  ので、IT の楽器と 16-bit の長さ、XM の音量エンベロープを読めるよう加算的に拡張した）。
- **`RCell.note` は 0 始まりの半音番号**（C-0 = 0）。基準ノートは S3M・XM が C-4（48）、IT が C-5（60）で、`rate_hz` で
  鳴る。writer が形式の表記（S3M の `(octave<<4)|semitone`、XM の +1）に直す。MOD だけは tracker note（0..35）のまま。
  特別な値は `NOTE_CUT`（S3M・IT の `^^^`）と `NOTE_OFF`（XM の 97・IT の `===`）。
- **`RCell` に `pan` を持たせなかった**（§9.6 の定義から外した）。XM は発音のたびにサンプルのパンへ戻るので、
  **lane のパンごとに別のサンプル**（`samples.SampleKey` の4つ目の要素。名前に `@<pan>` が付く）にして、セルごとの
  `Px` をやめた（ボリューム列は音量だけに使える）。S3M・IT のパンはヘッダ（IT は楽器・サンプルの既定パンを使わない）。
  `Automation("pan")` はエフェクトで表す（S3M `S8x`・XM `8xx`・IT `Xxx`。優先順位が最も低く、他の効果があれば落とす）。
  XM では、パンのオートメーションの後に同じ lane が次に発音すると、サンプルのパンへ戻る。
- **コマンド文字は形式の表記**（`RCell.fx = ("H", param)`）。表は `encode.Codec` の1か所だけ。`Codec` は音高（`note()`）、
  各奏法、Speed・テンポ・pattern の中断、音量スライド、パン、カットオフ、止めるセル（`stop_cell()`）を持つ。

**セル化の規則（§9.6）の具体化**

- 1セルに入りきらないときの優先順位は `encode.PRIORITY`（Delay > Glide > Retrig・Cut > Arpeggio > Offset > Vibrato・Tremolo >
  音量スライド > パン・カットオフ）。トリガーの row を取れなかった Vibrato・Tremolo は次の row へ移す。他は落とす（DEBUG ログ）。
- **MOD の音量とエフェクトの排他（§9.6 の2）を設計書どおりに実装した。F3 の挙動が変わる**: F3 は「トリガーのエフェクトが
  あれば音量を常に落とす」だったが、今は音量が楽器の既定音量と等しければ書かず、違えば Delay・Glide・Retrig・Cut・Arpeggio・
  Offset ではエフェクトを残して音量を落とし、Vibrato・Tremolo では**音量を残して奏法を次の row へ移す**。
- **`strum_ms`（和音の声部のストローク。§9.5）を実装した**。F3 は未実装だった（記録も漏れていた）。声部 i の `strum_ms` を
  `Delay(round(strum_ms ÷ 1 tick の ms))`（1 tick ＝ 2500/BPM ms、step の tick 数 − 1 で頭打ち）にする。MOD では Delay と
  同じセルの音量が落ちる（§9.6 の2）ので、ストロークのある和音の声部は既定音量で鳴る。
- `Offset` は**フレーム数**（16-bit は 2 byte で 1 フレーム）に対する割合で `xx = round(f × フレーム数 / 256)`、255 で頭打ち。
  IT の 64 KiB を超える位置の `SAx` は使っていない。
- **Speed・テンポ**は、全区間の `ticks_per_step` が同じなら曲の最初の区間（`order[0]`）にだけ、違うなら全区間の先頭に書く
  （F3 は `score.sections` の作成順の最初に書いており、`order[0]` と違うと V10 に落ちる不具合の素だった）。row コマンドの場所は
  制御チャンネルを最優先し（`RGrid.try_insert_command(prefer=)`）、埋まっていれば空のセル、音量・エフェクトの無い発音のセル。
  非 MOD は音量が別の列なので、音量のある発音のセルにも相乗りできる。
- **pattern**: MOD・S3M は 64 row 固定、IT は max(実際の長さ, 32) で足りない分は `C00`、XM は実際の長さ。上限（`max_rows`）を
  超える区間は小節の境目で分ける。pattern 数・order 長の上限を超えたら `PlanError`。**同じ内容の pattern の統合はしていない**
  （区間の繰り返しは同じ pattern 番号の繰り返しで足りている）。
- チャンネル数は、MOD は予算（4/6/8）、他形式は実際の lane の数（制御チャンネル込み）。

**サンプル（§8.4）**

- `SampleKey = (楽器名, 和音の形, セント, パン)`。**実際に使われた鍵だけ**サンプルを作る（F3 は lane の `insts` を全部作った）。
  並びは「楽器の宣言順の素の楽器 → 和音の形の変種」。
- 微分音・`tune_cents`: MOD 以外で、書かれた音高の小数部と `Instrument.tune_cents` から整数セントを求め、**同じ波形で再生レートに
  `2^(cents/1200)` を掛けた別サンプル**にする（S3M・IT は C2Spd・C5Speed、XM は relative note と finetune）。MOD は従来どおり
  整数の tracker note に丸め、セントは無視する（MOD の finetune 変種は未実装。F7 の maqam・gamelan までに）。
- `Instrument.pitched`（`None` 以外）の上書きをサンプルの `pitched` に反映するようにした（F3 は無視していた）。
- 描画の倍率 m ＝ `max(1, target_rate ÷ 実際の再生レート)`。1サンプルの上限（S3M の 64000 byte）を超えたら m を下げて描き直す
  （最大4回）。S3M の全サンプルが 64000 byte 以下・約 44.1 kHz になることをテストで確かめている。

**書き出し（§10）**

- XM: ボリューム列は `0x10 + vol`、16-bit サンプルは語単位の delta、relative note と finetune は `12 log2(rate_hz/8363)` を
  1/128 半音に丸めて分ける（Amiga 周波数表。F0 の測定どおり）。リリースのエンベロープは 2 点（サステイン点＋0 へ落ちる点）。
- IT: 楽器モード・NNA=Note Cut・キーボード表は全ノートをそのサンプルへ・楽器ヘッダ 554 byte。サンプルの長さとループは
  「サンプル数」単位（16-bit は byte ÷ 2）。リリースのエンベロープは XM と同じ2点（サステインループ付き）。
- S3M: 8-bit・C2Spd ＝ `round(rate_hz)`（65535 以下）。`Instrument.release_s` のある楽器の `NOTE_OFF` は使えないので音量スライド。
- **検査器**（`native_s3m.verify`・`native_xm.verify`・`native_it.verify`）: §10.5 の項目に加えて、XM の音量列の範囲（0x10..0x50）、
  XM のエンベロープ（点数・tick の単調増加）、IT の楽器モードのフラグ・キーボード表・NNA、pattern の row 数、
  C2Spd・C5Speed が 1000 Hz を下回ったら WARN（V18。F0 の注意点）。コードは旧検査器と同じ番号体系で、新しく V17〜V22。
- **MP3**: `render.render_mp3_from_it()`。`ffmpeg -f libopenmpt -i x.it ... -c:a libmp3lame -b:a 320k -compression_level 0`
  （2パスの音量調整は旧と共通の `encode_mp3()`）。旧 `render_mp3()`（XM・192 kbps）は F8 まで残す。

**リリース（§9.7）**

- `release_s` のある楽器: XM・IT は `NOTE_OFF`＋エンベロープ、MOD・S3M は音量スライド（`Axy`／`Dxy`）を `ceil(release_s ÷ 1 row の秒数)`
  個の row に置き、最後に止める（スライド量は `round(今の音量 ÷ (row 数 × (tick − 1)))`、1..15）。区間の終わりのループ停止だけは、
  スライドが次の区間にはみ出せないので MOD・S3M では即時に止める。XM・IT の tick の換算は曲の初期テンポ。
- 実測で、**IT の `===` はエンベロープの無い楽器では止まらない**ので、`release_s` の無い楽器は `NOTE_CUT`（IT）／音量 0（XM）で止める。

**S3M の音高（I4 の許容を形式ごとに変えた理由）**

- libopenmpt の S3M は ST3 の整数の周期表を再現しており、音高の誤差は基準オクターブで最大 ±5.6 セント、C2Spd が 44.1 kHz だと
  周期が小さくなる高いオクターブで 8〜12 セントになる（実測: ノート 24..71 の全域。C2Spd を 22.05 kHz にしても 65・69 番で
  8.7・9.4 セント）。これは形式固有でファイル側では直せない。
- よって I4（`tests/realplayer/test_pitch.py`）の許容を **XM・IT 7 セント（設計書どおり）、MOD 9 セント（Period 表の丸め 5.9 に
  FFT の測定誤差が乗る）、S3M 12 セント**とした。
- I4 の対象は、基本周波数が一意に測れる持続音（ループ）の34プリセット。除外は `fb_supersaw`・`tension_strings`（複数の声を
  ずらして重ねる音色。MOD でも同じ理由で外れる）。ワンショットは減衰が速く窓で測れないので対象外。最低音は期待周波数が 170 Hz
  以上になる音まで（窓 0.8 秒の FFT 分解能。pad 系が 130 Hz で測れなかった）。

**まだ無いもの（意図して持ち越し）**

- **スウィング（§9.9）**: F3 から未実装（`SectionPlan.swing` を Realizer が読んでいない）。最初のスウィングのジャンルを移植する
  F6 の前に入れる。入れるときは、スウィングのある曲では全区間の先頭に Speed を明示すること（直前の区間の Speed が残らないように）。
- `Glide` の period 計算と拡張音域の速さ（§13.4 の表）、MOD の finetune 変種（微分音）、`Offset` の IT `SAx`。いずれも該当する
  ジャンルの移植（F7）で。**→ Glide は F7（§16.9）、finetune 変種は F6（§16.8）で入れた。**
- **音量の底上げ（§9.10）は F4 の後に前倒しで実装した**（ユーザーの指摘: MP3 に比べて他形式が小さい）。`core/native_level.py`
  （音量の値を一律に倍 ＋ S3M・IT のマスター音量。旧 `level.py` の `RealizedSong` 版）、実測表 `framework/levels.py`
  （形式＋チャンネル数ごとの最悪の最大振幅。鍵が無いチャンネル数は同形式の最悪値で代用）、較正ツール
  `tools/calibrate_native_levels.py`。`realize(level=True)` が既定で持ち上げる。**効果は形式で違う**: S3M・IT は
  マスター音量（127/128 まで）で約 −2〜−3.5 dBFS まで上がった（以前は −4〜−6）。**XM と MOD は上がらない**（XM −4〜−5、
  MOD 8ch −7〜−8、MOD 4ch −3.5 前後）: ヘッダのマスター音量が無く、音量の値は最大の発音（kick・bass が 59〜61）が
  すでに上限 64 に近く、サンプル波形の最大値も 0.9〜0.95 で余裕がほぼ無いため。MP3 は ffmpeg の平均音量合わせ＋リミッタ
  （平均 −14 dB）を通るので、ピークだけを揃える他形式より大きく聞こえる。全ジャンルの実測表は F8（表は今は3ジャンルだけ）。
- 旧 `engine`・`cli`・`formats.py` の登録簿への接続（`--format` から新しい経路を呼ぶこと）は F8。F4 の時点で新経路は
  `native.serialize(realize(...))` を直接呼ぶ。

### 16.7 F5 の実装で埋めた設計の隙間

`framework/realize/midi.py`（`realize_midi(genre, score, plan, target) -> bytes`）と、新しい検査器 `core/native_midi.py`
（PPQ 480。`native.verify("midi", data)`）。旧 `core/midi.py`（PPQ 96・`Song` 用）は F8 まで残し、低水準の部品
（`_track`・`_meta`・`_cc`）と `parse_midi` だけ再利用した。

- **時間**: 1 tracker tick ＝ 20 MIDI tick。区間ごとの step→tick の写像（`_step_time`）がスウィング
  （2 step の組の後ろの step を `long` tick 目から）を含む。TempoEvent は時刻順にそのまま置き、拍子は小節ごとに
  `step 数 × tick` から求める（求まらなければ `Meter.signature`）。
  **MIDI はスウィングを実装済みだが、トラッカー側の Realizer は未実装のまま（§16.6）**。
- **音高**: `midi = 69 + 12 log2(sounding_hz/440) + (t − rate_note) + tune_cents/100`（t ＝ 書かれた音高 − shift）。
  設計書 §11.3 の `n + 36 + offset` と同じ実音を指す（§8.1 の基準から直接導いた形）。整数でない部分はピッチベンド
  （±2 半音。`Glide` のあるパートは ±12）。**セントの違う音が重なるパートはセントの値ごとに別チャンネル**
  （重ならないパートは1チャンネルで発音ごとにベンド）。チャンネルが足りなければ同じ program の単一楽器パートが相乗り、
  それでも足りなければ `PlanError`。打楽器と旋律の混在するパートは `PlanError`。
- **終わり（§11.3 の「長さ」）**: `dur` ＞（ループ: 区間の終わり／ワンショット: 自然減衰の長さ）と、同じパート・同じ楽器の
  次の発音のうち早いもの。自然減衰は曲の初期テンポで tick に換算する（テンポ変化のある曲では少しずれる）。`NoteOff`・`Cut`
  で短くなり、曲の終わりを超えない。同じチャンネル・同じ音高の重なりは次の発音の頭で切る（止まらない音を作らない）。
- **奏法**: `Delay`＝発音を遅らせる、`Retrig`＝間隔ごとの再発音、`Arpeggio`＝1 tracker tick ごとに音を切り替え（終わった後は
  基の音が続く。トラッカーと同じ）、`Vibrato`＝CC1（深さのニブル × 8、終わりで 0）、`Glide`＝**直前の音が鳴っているときだけ**、
  新しい音を直前の音の高さのベンドから 1 tracker tick ごとに目標へ動かす（直前の音が終わっていれば普通の発音。差が 12
  半音を超えるときも普通の発音）、`Tremolo`・`Offset` は無視。和音は構成音を同時に発音し、`strum_ms` は tick にして遅らせる
  （velocity は和音でも `1/√k` にしない）。
- **ミキシング**: velocity ＝ `round(vel/64 × 127)` を、曲の最大が 127 になるまで一律に持ち上げる。`Automation`＝CC11（その
  時点の発音の音量に対する比）・CC10・CC74、`Sidechain`＝対象パートの CC11（トリガーの発音ごとに下げて戻す）。
  `Instrument.pan`／`Part.pan` は CC10（楽器が変わるたびに program change と一緒に出す）。
- **検査（`native_midi.verify`）**: 旧検査（読める・EOT・note on/off の対応・テンポ）に、PPQ 480、velocity・ノート範囲、
  メロディのチャンネルの program 指定、ドラムの音域（27..87）、**同時発音数が GM1 の保証する 24 を超えたら WARN** を加えた。
- **まだ無いもの**: GM 音源で鳴らしての聴感の確認（この環境に音源が無い）。`Tremolo`（CC1 とは別の表現が無いので無視）。

### 16.8 F6 の実装で埋めた設計の隙間

**置き場所（§16.1 からの変更）**: 移植したジャンルは旧 `mod_weaver/genres/` を置き換えず、**`mod_weaver/genres_next/`**
に置いた。理由は2つ: ①編成の対応表のテスト（§15.1）が旧クラスと新クラスを同じプロセスで読む必要がある、②旧パイプライン
（CLI・GUI・engine）が移行の間も動いたままで、旧版の出力と比べ続けられる。F8 で旧 `genres/` を削除し、`genres_next/` を
`genres/` に改名する（`git mv`）。**engine・CLI の新旧の呼び分けは作っていない**（§16.1 の「一時的な分岐」は F8 でまとめて）。
新しいジャンルは `framework.registry.discover("mod_weaver.genres_next")` で登録され、`native.serialize(realize(...))`・
`realize_midi(...)` を直接呼んで書き出せる。

**変換ツール `tools/port_band_genre.py`**: 旧 `BandProfile` のクラス属性（KIT・CHORD_KITS・CHANNELS・ARRANGEMENTS・SECTIONS・
GROOVES・各 Spec・SIDECHAIN …）を読み、§15.1 の表のとおりに新しい `Genre` の宣言を書き出す。A の 13 ジャンルは
無修正で通り、**編成・パン・折り畳みの優先度が旧と一致する**（`house` を除く。下）。B は骨格だけをツールが作り、上書き
していたメソッド（§15.3）を手で書いた。ツールが残した `TODO` が1つでもあるとテストが落ちる
（`test_no_unported_override_is_left_behind`）。ジャンルを足すときの出発点にも使える。

**B の手書き部分の書き方**（§15.3 の方針どおり。乱数の消費順は変わる＝D9）:

- 区間の `parts` に混ぜていた役割の名前（`"kime"`・`"spic"`・`"fanfare"`・`"counter"`・`"hits"`・`"build"`・`"toms"`・`"clean"`）は
  `Section.tags` に移した。同じチャンネルを共有する役割は1つの Part にして `Kit` で lane を宣言し（anime-ost の
  `strings`＝spic＋brass、jrock-90s の `guitars`＝歪み＋クリーン、classical の `inner`＝vln2＋vla、jrpg・trailer の drums）、
  ジェネレータが `m.plan.section.tags` を読む。
- パートをまたぐ編集は `finalize_section`（`score.mute` → `score.add`）: anime-ost の決め、jazz の coda のフェルマータ、
  trailer の final の余韻。旧版の `buf.replace`（他のパートの特定の row だけを置き換える）は、該当する楽器・step だけを
  取り除いて足す形にした。
- 区間をまたぐ状態は `ctx.state`（classical の声部の滑らかな進行、jrpg のゼクエンツ）。`plan()` の上書きは
  `default_plan()` の結果の `SectionPlan.extra` に値を足す（indie-rock の disco・gamelan の音律と balungan）。
- 音が出た後に加工するものは `SectionCtx.own_events()`（**新設**。部品の `section()` を呼んだ後に自分のイベントを書き換える）:
  folk の前打音、jrpg のゼクエンツ。
- 旧版の `finalize_pattern`（D00 の空き作り）・`_silence`（区間頭の停止）・`inst.off()` は書かない（Realizer の責任）。

**旧版との違い（意図したもの）**:

| ジャンル | 違い |
|:---|:---|
| house・energetic・rock | 打楽器の論理チャンネルが離れていた（shaker・tom が6番目）が、新しい編成は打楽器を1つの `drums` パートにまとめるので、打楽器の lane が先頭にまとまる。楽器・パンは同じ。**MOD はパンがチャンネル番号で固定（L R R L）なので、ステレオの配置が少しずれる** |
| jrock-90s | 歪みギターとクリーンギターを1つの `guitars` パート（`Kit`）にした。lead gtr との並びが入れ替わる（楽器・パンは同じ）。4ch で2本が1チャンネルに畳まれる挙動は保たれる |
| dark-tense | 旧版は区間の目印 `"lead"` で braam・choir の鳴る区間を決めていたので、パートを実在の `braam` に付け替えた（`choir` は `braam` に付き従う） |
| gamelan | ketuk を打楽器の型から外し、**colotomic パートの kit（kenong/ketuk の lane）に移した**（旧版の物理チャンネルが「クノンと同じ」だったため）。音律は小数の音高で書き、MOD の finetune の変種は Realizer が作る |
| chiptune | `channel_cap = 4`（厚くしないことがジャンルの性格）。ジャンプ音を打楽器の kit に入れた |
| edm・uplifting | `build` の区間にも `drums` を入れ、ドラムのジェネレータがスネアのビルドアップを鳴らす（旧版は他のチャンネルのスネアを extra_measure が打楽器のチャンネルに書いていた） |
| racing-breaks | F3 の試験移植の写し間違い2件を直した（パートの並びが pad → lead の順、折り畳み時の優先度に ohat・ride が抜けていた） |

**F6 で足したフレームワークの機能**（いずれも §16.4〜§16.7 の続き）:

- **MOD の微分音（finetune の変種）**: 書かれた音高の小数部と `tune_cents` から finetune（-8..7）を求め、同じ波形で finetune だけ
  違うサンプルにする（`samples.sample_key`）。**実プレイヤーで finetune の刻みを測ると 12.5 セント（-8 で -100、+7 で +87）で、
  旧 `core.pitch.FINETUNE_CENTS = 7.8125` は誤り**だった（旧パイプラインの maqam・gamelan の微分音は、残差が大きいほど
  最大で 20 セント以上ずれて出力されていた）。新しい Realizer は `samples.MOD_FINETUNE_CENTS = 12.5` を使う。旧定数は旧版の
  テストが依存するので触らず、F8 で旧と一緒に消える。
- **スウィング（トラッカー）**: F3 から未実装だったものを実装した（§16.6 の「まだ無いもの」を回収）。スウィングのある区間は偶数 step を
  `long`・奇数 step を `short` の Speed にして**全 row** に書く（制御チャンネル優先。場所が無い row は旧版と同じ手順
  `_make_room` で作る）。スウィングがある曲は、全区間の先頭に Speed を明示する。
- `Genre.swing` は、自前の `swing` を持たない区間の既定として `default_plan()` が適用する（それまでは宣言だけで使われておらず、
  検証も既定の拍子と比べて誤って落ちていた）。検証は区間ごとの拍子で行う。
- `SectionCtx.pitch_for(inst, pitch)`: 音程の無い楽器（vocal chop・効果音）に部品集が音高を渡さないための補助
  （旧版は黙って無視していた。`ctx.note()` は厳格な検査のまま）。
- **MIDI**: 打楽器と旋律の楽器が混在するパート（chiptune のジャンプ音）は、打楽器の音を ch10、他を旋律のチャンネルに分ける。
- `--channels` が範囲外のときは `ChannelCountError`（終了コード 2。設計書 §9.2 のとおり。それまでは `PlanError` だった）。
- 音量の較正表（`framework/levels.py`）を全39ジャンル＋march 分に作り直した（`tools/calibrate_native_levels.py`）。

**検査**（`tests/framework/test_ported_genres_all.py`・`tests/realplayer/test_ported_genres_real_player.py`）:
I1（骨格の不変）・I2（決定性）・I3（MOD の全予算、S3M・XM・IT の既定と `min(mod_channels)`、MIDI）・全パートが鳴る・
**編成の対応表**（旧 `ARRANGEMENTS` の各編成と、新しい ladder の lane の数・楽器・パンが一致。差は `LAYOUT_DIFFS` に理由つきで記録）・
**折り畳みの優先度**（同じ lane に畳まれた打楽器の2つのうち残る方が旧と同じ）・旧 `test_stage3_genres.py` の書き直し
（区間で鳴らさないパートが鳴らない・テンポ・seed によるチャンネル数の選択と範囲外の拒否・classical の 3/4・タムのフィル・
スウィングが全 row に入る）・I5・I6。**設計書 §15.1 の「畳んだ結果の (楽器, row) の集合の一致」は、乱数の消費順が変わる
（D9）ため同じ seed でも打点が一致しないので、優先度の表そのものの一致で代えた。**

**まだ無いもの**: engine・CLI・GUI・`--json` への接続（F8）。§15.5 の opt-in（フィルタのスイープ・Tremolo・release_s・double・
12ch 以上の追加パート）は、試聴で基準と比べてから。実際に聴いての確認（`output/f6-trial/`）。

---

### 16.9 F7 の実装で埋めた設計の隙間

**置き場所**: 12 ジャンルとも `mod_weaver/genres_next/`（F6 と同じ。F8 で `genres/` に改名）。試験の march は
`tests/framework/realize/genres/` から `genres_next/march.py` に昇格した（F3 の試験用のクラス名 `MarchToy` は `MarchGenre`。
`tools/calibrate_native_levels.py`・`test_all_formats.py`・`test_ported_genres.py` の march の特別扱いは外した）。suspense の2ジャンルの
共通部分（音色・和声・語彙）は `genres_next/_suspense.py`（`_` 始まりなので `discover()` はジャンルとして読まない）。
`tools/port_band_genre.py`（変換ツール）は C には使えない（旧版が `BandProfile` ではない）ので、旧 `genres/<id>.py` と旧テストを見ながら手で書いた。

**共通の書き方**: 和声が手組み・不揃いのジャンル（march・nostalgic・minimalism・free-jazz・maqam・suspense の2つ）は `harmony=None` とし、
`plan()` を上書きして `SectionPlan`・`MeasurePlan` を直接組む（`kind`・`quality` は表示用で Realizer は読まない）。dropout・anvil・スタブ・
クラスターの和音のような「曲ごとに乱数で決まる計画」は `plan()` が決めて `SectionPlan.extra` に置き、各パートが読む。同じ文法の区間が
曲の中に2つある場合（suspense-chase の A1・A2）は、区間名を分けて `Section.kind` を共通にする（`a1`・`a2`、`kind="a"`）。
持続音を止める無音は、その楽器の持ち主のパートが `off` を書く（他のパートの lane は書けない）。旧版の `finalize_pattern`・`_silence`・
`inst.off()` による「区間末の消音」「区間頭の停止」は書かない（Realizer の責任。ループ音色は区間の終わりで止まる）。**区間は音を持ち越さない**ので、
旧版が pattern をまたいで鳴らし続けていた持続音（suspense-slow の shock の最初の小節の drone）は、区間の頭で鳴らし直す。

**F7 で足したフレームワークの機能**:

- **`Glide` の実装（Realizer。§5.3・§13.4）**: `tracker._resolve_glide`。同じ lane の直前の音について、(1) 鳴り終わっていれば（ワンショットの
  再生時間 ＝ フレーム数 ÷ 再生レートが、音の間隔より短い／明示の `dur` が尽きた／消音がある）`Glide` を外して普通の発音にする、
  (2) 鳴っていて `Glide.param` が無指定なら、直前の音の period から目標の period まで `steps × (row の tick 数 − 1)` 個の tick（スライドは
  row の最初の tick には掛からない）で届く速さを `3xx`/`Gxx` に書く。速さは **Amiga 換算の period の差 ÷ tick 数**
  （Amiga 換算の period ＝ `dsp.CLOCK` ÷ 再生レート。MOD は period 表、他は `rate_hz × 2^((note − 基準) / 12)`）。1 が tick あたり period 1
  という対応は、MOD・S3M・XM・IT の4形式を libopenmpt で測って確かめた（S3M・IT は period の単位が 4 倍だが `Gxx` のスライドも 4 倍で相殺する）。
  最初のノートの発音のとき（前の音が無い）は何もしない。MIDI は従来どおり「直前の音が鳴っているときだけ」ピッチベンド（§16.7）。
- **`gens/tempo.py` の `tempo_curve(ctx, start_bpm, end_bpm, start_step, end_step, kind)`**（free-jazz のルバート）: 旧 `automation.TempoCurve`
  と同じ式（`linear`・`ease_in`・`ease_out`）で、BPM が変わる step にだけ `ctx.tempo()` を呼ぶ。音を鳴らさないパートを置くと lane を食うので、
  free-jazz は先頭のパート（piano）が区間のテンポカーブも書く。
- **`Harmony.arp`**: `True` なら `voice(arp=True)` で `ChordDef.arp`（`0xy` 用の第3音・第5音のオフセット）を求める（`default_plan()` が渡す）。
  swing-jazz のコンピングの刺し。

**旧版との違い（意図したもの）**:

| ジャンル | 違い |
|:---|:---|
| nostalgic | 旧版の挙動 Q1〜Q7（アウトロの row 0 がテンポセルで上書きされる、テンポセルがイントロだけ音なし、など）は保たない（D9）。Q5（サビの旋律のオクターブ頭打ち）と、曲名・テンポの候補・進行のプール・旋律の規則は同じ。Q4 の未使用の flute は楽器から外した。pad のフェードアウトは `Automation(volume)` の 3 点（18・8・0）。ドラム・ベース・pad・旋律のパンは旧 MOD の LRRL ではなく、パートごとの値（ドラム 128・ベース 128・pad 80・旋律 176） |
| suspense-slow・chase | 編成・優先度（anvil＞swoosh＞heart、pizz が優先）は旧と同じ。heart・anvil・swoosh・pizz の消音（`put_oneshot_off`）は書かない（ワンショットは自然に鳴り終わる）。swoosh の開始 step と anvil の余韻の長さは `ctx.step_seconds()` から（旧 `swoosh_start_row`・`anvil_clear_row` と同じ式） |
| swing-jazz | ウォーキングベースの終止が「現在の和音の根音」から「次の和音の根音」（`MeasurePlan.next_chord`）に変わった（§15.4 の指定。リズムチェンジの小節ごとの進行がつながって聞こえる）。ドラム tacet の intro は音楽上の意味があるので残し、row 0 に空きを残す工夫（コンピングを裏拍に置く）は音楽上そのまま残るが、目的は無くなった |
| maqam | 中立 3 度・中立 7 度は、旧版の finetune の派生楽器（`oud_n3`・`oud_n7`）ではなく、書かれた音高の小数部（350・1050 セント → x.5）で表す。MOD の finetune の刻みを 12.5 セントとして求める（旧 7.8125 は誤り。§16.8）ので、旧版より正確に ±50 セントで出る。S3M・XM・IT は微分音を C5Speed・相対ノートで直接出す |
| free-jazz | `--tempo` は開始 BPM（96 から外れた値は、カーブ全体を 開始 BPM ÷ 96 倍に相似拡大。`tempo_range` は旧と同じ値）。テンポの変化は piano のパートが `tempo_curve` で書く。クラスターの和音は旧と同じ規則（`plan()` で乱数）だが、乱数の消費順が変わるので同じ seed でも別の和音になる |
| orchestral | `SampleSpec.pan`・`finetune` による定位・デチューンは `Part.pan`（30・80・150・190・210・100・160・128）と `Instrument(tune_cents=+37.5, volume=44)`（finetune 3 × 12.5 セント）で表す。brass（horn・trumpet。trumpet が優先）と perc（timpani・cymbal。cymbal が優先）は Kit の優先度 |
| minimalism | 乱数を使わない（旧と同じ）。woodblock の step 1 のアクセントは残した（フェイズ音楽の周期の一部）。16 区間・各 1 小節 48 step |
| prog-rock | `Section.measure_steps`（14・14・10／10×6／16×4）で小節ごとの step 数を宣言。gtr の `PROG_GTR_POWER` はパワーコード込みの音色なので、和音（`(0, 7, 12)`）にはしない。crash は march の crash を 0.6 秒に短縮した派生（旧版と同じ） |
| trap | 808 のグライドは `Glide(steps=1)`。先行音が鳴り終わっていれば発音に変わる規則と速さの計算が Realizer に入った（旧版は trap だけが自前で period を追跡していた）。旧版は MOD 専用の period で追跡していたが、新版は 4 形式で同じ規則 |
| future-bass | サイドチェインは `Genre.mix`（kick・clap をトリガ）。vocal chop は `Offset(i / 6)`（旧 `9xx` の param は `sample_offset_param` で割合から求めていた） |
| march | F3 の試験移植のまま昇格（変更なし） |

**検査**: `tests/framework/test_ported_genres_all.py`（全 51 ジャンルが対象。**`PORTED_F7`・「51 ジャンルが揃っている」の検査を追加**。編成の対応表と折り畳みの優先度は旧 `BandProfile` のあるジャンルだけ）、
`tests/framework/test_ported_genres_c.py`（C のジャンル固有: minimalism の位相ずれ・D00、free-jazz のルバートの連続性と相似拡大、orchestral の 8ch 専用・trumpet の優先・cymbal、maqam の x.5 の音高と finetune 変種・usul・coda、march の構造とスネアロール、nostalgic の音域とフェード、suspense の無音・anvil・スタブ・衝撃の直前 8 step、swing-jazz のスウィングと次の和音への終止、prog-rock の変拍子、trap の Retrig とグライド、future-bass のサイドチェインとスライス）、
`tests/framework/realize/test_glide.py`（速さの式と、先行音が鳴っているかの判定）、
`tests/realplayer/test_glide_real_player.py`（4 形式 × 7・12 半音のグライドが指定の step 数で届く）、
`tests/realplayer/test_ported_genres_real_player.py`（I5・I6 を全 51 ジャンルに。**I5 の期待長は、テンポの変化（free-jazz）を含めて計算するようにした**）。
試聴用の MOD・MIDI・MP3 は `output/f7-trial/`（git の管理外）。音量の較正表（`framework/levels.py`）は全 51 ジャンルで作り直した。

**まだ無いもの**: engine・CLI・GUI・`--json` への接続（F8）。試聴でのユーザーの確認（`output/f7-trial/`。特に maqam の中立音程・trap の 808 グライド・free-jazz のルバート・swing-jazz の終止・suspense の無音の位置）。

---

## 17. 変更の手引き（今後の仕様変更のとき）

### 17.1 原則

1. **ジャンルは「何をどう鳴らすか」だけ**。チャンネル・row・pattern・エフェクト番号・形式の差を書いたら設計の違反（I8 で一部を機械的に検出）。
2. **形式の差は Realizer の表に閉じる**。新しい形式の能力を使うときは、まず Score の語彙（奏法・オートメーション・Instrument の属性）として意味で定義し、各形式での表現を表に足す。
3. **骨格は形式に依存しない**（I1）。形式の能力による違いは、パートの有無・和音の鳴らし方・奏法・解像度だけ。
4. **宣言で書けることは宣言で**。ジェネレータに書くのは、宣言で書けない文法だけ。2つ以上のジャンルが使うようになったら部品集へ移す。
5. **値の単位は現行と同じ**（D12）。耳で調整した値を変える変更と、仕組みの変更を同じコミットに混ぜない。

### 17.2 変更の種類と直す場所

| 変更 | 直す場所 | 確かめること |
|:---|:---|:---|
| 新しいジャンル | `genres/<id>.py` を1つ（宣言＋必要ならジャンル内のジェネレータ）。音量の実測を `profiles/levels.py` に | I1〜I3・I6、ジャンル固有の文法のテスト、試聴 |
| ジャンルの音楽の内容（進行・リズム・構成） | そのジャンルのファイルの宣言 | ジャンルのテスト、試聴、音量の実測のやり直し |
| 音色 | `core/synth_presets/` のプリセット（共有なら使っている全ジャンルに影響。`find()` で探す）か、ジャンルの `instruments` での差分 | I4・I7、試聴、音量の実測 |
| 新しい奏法（例: ピッチベンドの揺れ） | `framework/score.py` に型、`realize/encode.py` に形式ごとの表現、`realize/midi.py` に MIDI の表現、§4.3 の features | 形式ごとの表現のテスト、要実測の項目を §13.4 の手順で |
| 新しい形式 | `framework/target.py` に能力表、`core/` に writer・parser・検査器、`realize/encode.py` に表現の表、`core/formats.py` に登録 | I3〜I6 を新しい形式に広げる |
| 既存の形式の能力を新しく使う（例: IT の NNA） | Realizer（lane の扱い）と writer。ジャンルに見せるなら features に足し、ジャンルは opt-in | 不変条件 I1 が崩れないこと |
| チャンネル数の方針（ladder の順序など） | `realize/lanes.py` だけ | ladder のテスト、全ジャンルの編成の期待値のテスト（変わったジャンルを確認） |
| CLI・GUI の選択肢 | `cli.py` の `--json`（GUI は読むだけ） | integration テスト |

---

## 18. リスクと未確定事項（レビューで特に見てほしい点）

### 18.1 リスク

| リスク | 影響 | 対策 |
|:---|:---|:---|
| 高解像度で音色の印象が変わる（m>1 で捨てていた部分音が出て明るくなる、`diff_hp` の置き換え） | 耳で調整した音色の性格が変わる | I7 で m=1 の帯域の同等性を検査。試聴で問題があれば、`Patch` に「描画の上限周波数」を足して部分音を絞る（opt-out） |
| 和音を声部に開いたときの音量（`vel/√k`）と、打楽器を分けたときの音量が、焼いた・畳んだときと釣り合わない | 和音・打楽器が大きすぎ／小さすぎ | 試聴で係数を調整。音量の実測を作り直す |
| ladder の結果が現行の編成と違うジャンルがある（例: rock の 6ch の tom は現行では6番目のチャンネルだが、新しい並びでは打楽器の隣になる。MOD の L R R L の左右が変わる） | MOD の定位が変わる | 編成の対応表のテストで差を一覧にし、試聴で判断（D9 で互換は求めない） |
| 区間の頭でのループの停止（§9.7）で、row 0 が混む | MOD の曲の先頭で row コマンドの場所が足りない | 停止のセルを最初に外す規則。全ジャンル×全予算のテスト（I3） |
| `poly`・和音の声部が多い曲で、IT のチャンネル数が増え、libopenmpt の合成で音が大きくなる | 音割れ | 音量の実測を全形式で作り直し、IT は下げる方向も許す（§9.10） |
| テストの総当たり（51ジャンル×予算×形式×seed。I3 だけで約900回の生成）の実行時間 | 開発が遅くなる | 描画のキャッシュ（§8.6。テストは1プロセスなのでプロセス内のキャッシュが効く）。realplayer の総当たりは既定では一部の seed だけにし、全数は手動で |
| 移植の途中の新旧の並行 | 保守が二重になる | ブランチの中だけで、フェーズ F8 で一括して削除（D10） |
| MOD の音域（36音）に収まらない音を、ジャンルが XM・IT 向けに書いてしまう | MOD で `PitchRangeError` | 音域の宣言は MOD に合わせたままにする規則（§9.6）。I3 で MOD を必ず生成する |

### 18.2 意図して範囲外にしたもの

| 項目 | 理由 |
|:---|:---|
| IT の NNA（新しい発音で前の音を残す） | lane の考え方（1 lane ＝ 1チャンネル ＝ 単音）が単純になる。NNA を使うと、Realizer の音の終わりの計算と MIDI の対応が複雑になる。将来 features に足せる（§17.2） |
| XM・IT の複数サンプルの楽器（音域ごとに別サンプル） | 描画を音域ごとに行えば高音の折り返し歪みは減るが、サンプル数とキーマップの設計が要る。§15.5 の後の課題 |
| 形式ごとに作曲の内容（音符）を変えること | 骨格の不変（I1）と矛盾する。形式で変えたい音楽は「大きな予算でだけ鳴らすパート」で表す |
| MIDI の GM 以外（GS・XG・GM2） | 要件外 |
| WAV 出力・自前の再生エンジン | 現行どおり範囲外（DESIGN_HISTORY.md §13） |

### 18.3 未確定事項

| 項目 | 現在の案 | 決め方 |
|:---|:---|:---|
| §13.4 の要実測の各項目 | 最初の3項目は F0 で実測し確認済み（結果は §13.4 の表）。残り6項目は仕様からの推定のまま | F4 で実測し、結果で本書を直してから先へ進む |
| 和音の声部の音量の係数 | `1/√k` | 試聴 |
| `diff_hp` の高解像度での置き換え | 同じ −3 dB 点の1次 HP | I7 と試聴 |
| ladder の順序（R2「打楽器をまとめる」を R3「和音を焼く」より先にする） | 先にする（現行の 6ch・8ch の編成と一致する） | 計算例（§9.3）と編成の対応表で確認。別の順序の方がよいジャンルが多ければ見直す |
| MIDI で `min_channels` のパートを全部入れるか | 入れる | ユーザーの確認 |
| S3M の予算の扱い（16ch を和音の声部と打楽器のどちらに優先して使うか） | ladder の順序のまま（打楽器を先にまとめる） | 試聴 |

### 18.4 既存の文書の誤り（ついでに見つけたもの）

- DESIGN.md §3.3 の `SampleSpec.finetune` の注「1 単位 ≈ 7.8 セント」は、コード（`s3m.c2spd`・`it.c5speed` の `2^(finetune/96)`）と ProTracker の仕様（1/8 半音＝12.5 セント）に合わない。DESIGN.md の統合のときに直す。

---

## 19. 第三者レビューの反映（2026-10-01）

設計案に対する第三者の視点のレビュー（16項目）を、すべて推奨案で反映した。推奨案が無かった項目は「コードの見通しの良さ」「実行時の資源の節約」を優先して決めた（その判断を「決め方」に書く）。

| # | 重さ | 指摘 | 反映 | 決め方 | 反映した節 |
|:---|:---|:---|:---|:---|:---|
| 1 | 重大 | エコー・レイヤーのパートが区間の `parts` に無く、一度も呼ばれない | `Part.follow` を追加。follow があれば follow 先が鳴る区間で鳴る | 推奨案 | §6.3・§6.4・§6.5・§6.9・§7・§15.1 |
| 2 | 重大 | 「同じ楽器・同じ step は PlanError」と march のスネアロール（prio で置換）が矛盾 | prio が同じときだけ PlanError、違えば高い方を残す | 推奨案 | §6.9 |
| 3 | 中 | 依存の規則 I8 が `core/midi` の import を禁じるが、`GmVoice` がそこにある | `GmVoice` を `core/model.py` に移す。再 export はしない | 推奨案（移動先は依存の向きが core 内で閉じる `core/model.py`。再 export しないのは見通しのため） | §3.2・§13.1・§16.2 |
| 4 | 中 | 実音の基準があいまいで、MOD の Period の丸め（最大 5.9 セント）が I4 の許容 5 セントを超える | 基準を「`sounding_hz` から求めた平均律」と定義し、I4 は全形式をその基準と 7 セント以内で比べる | 推奨案 | §1.2 D3・§8.1・§13.1 |
| 5 | 中 | スウィングの短い row で `Delay` が Speed 以上になり鳴らない | 上限を `min(long, short)` に。`Retrig`・`Cut` も同じ | 推奨案 | §5.3・§6.6 |
| 6 | 中 | 1つの優先度の表では現行の Fold の優先度を表せないジャンルがある | `Kit.single_priority` を追加。編成の対応表のテストで畳んだ結果も比べる | 推奨案 | §6.3・§9.5・§15.1 |
| 7 | 中 | 旧出力との一致を捨てた後、意図しない変化を検出できない | F8 で新しい出力のハッシュを基準として保存（`golden.json`）、更新は専用ツールで | 推奨案 | §13.2・§16.2 |
| 8 | 中 | 作業量の見積もりが追加した範囲を反映していない | 8〜11 日に修正 | 推奨案 | §16.3 |
| 9 | 中 | 高解像度の合成で遅くなる。CLI ではプロセス内のキャッシュが効かない | F1 で実測し、2 秒を超えるときだけディスクキャッシュを入れる（設計は §8.6） | 推奨案（「必要なら」を、資源の節約と見通しの両立のため「実測で超えたときだけ」に具体化） | §1.3 NFR-3・§8.6・§16.2 |
| 10 | 軽微 | features の `true_chords` は予算に依存し、使われていない | 削除 | 推奨案 | §4.3 |
| 11 | 軽微 | MIDI のチャンネル割当の基準が2か所で食い違う | パートの宣言順に統一（`instruments` の順はサンプルの並びだけ） | 推奨案が無かった。トラッカーのチャンネルの並びと同じ基準にそろえる方が見通しが良いのでパートの順 | §6.2・§11.2 |
| 12 | 軽微 | `measures` と `measure_steps` の優先が未定義 | `measure_steps` があればその要素数が小節数。両方を既定値以外で書いたら PlanError | 推奨案 | §6.3 |
| 13 | 軽微 | 和音のパートの lane 数「＋poly − 1」の意味が不明 | 和音を書くパートは `poly=1` に限る（両方は PlanError）。lane 数は最大の構成音数、焼けば1本 | 推奨案が無かった。組合せを禁じる方が lane の計算が単純で見通しが良い | §6.3・§9.3 |
| 14 | 軽微 | 上書きしているジャンルの数が 24 と 26 で食い違う | 26 に統一 | 推奨案 | §2.3 |
| 15 | 軽微 | trap の Meter が「現行を写す」とだけ | `Meter(32, 4)`、各区間 2 小節と明記 | 推奨案 | §15.4 |
| 16 | 軽微 | サイドチェインのトリガの判定時点が不明 | lane への割当の後に残った発音（現行と同じ）。MIDI は Score の発音 | 推奨案が無かった。現行の挙動と同じにする方が、試聴で調整した値の意味が変わらない | §9.8 |

あわせて、§6.5 の「区間の終わりで Realizer が止める」という記述が §9.7（次に鳴らない区間の先頭で止める）と食い違っていたので、§9.7 に合わせた。

