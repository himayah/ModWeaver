# マルチジャンル対応 MOD 生成エンジン 第二段階 core 拡張設計案（Design v2.0）

| 項目 | 内容 |
|:---|:---|
| 対象 | `mod_weaver` core レイヤーの次期拡張（v2.0） |
| 前提ドキュメント | [EXTENSION_DESIGN.md](EXTENSION_DESIGN.md)（Design v1.2 / 第一段階実装仕様。march 実装完了により第一段階は完了） |
| ステータス | **Phase 4a〜4e 全て実装済み（EXT-1〜6・§2 の8ジャンル全て完了）**（§7 ロードマップ）。Phase 4a: §4.0 共通基盤・EXT-1（`core/groove.py`）・EXT-2①（`core/structure.py`）で `swing-jazz`／`prog-rock`。Phase 4b: EXT-4（`core/mixer.py`）・EXT-5①②（`core/automation.py`）で `future-bass`／`trap`。Phase 4c: EXT-3（`core/pitch.py` 追加）で `maqam`／`free-jazz`。Phase 4d: EXT-2②（`structure.polymetric_row()` に初利用者、core 変更なし）で `minimalism`。Phase 4e: EXT-6（`SampleSpec.pan`、`writer.serialize_xm`/`verify.parse_xm`/`verify_xm`）で `orchestral`（8ch, target_format="xm"）。既存11ジャンルは無変更・989→1729件のテストは全緑、回帰なし（§9・§10 の「後方互換」の主張は実測で確認済み）。**EXT-6（XM）のみ、実プレイヤーでの再生確認が未了**（机上実装＋自己無矛盾なラウンドトリップ検証のみ。§11 参照）。実装で判明した設計の修正は §4.1①・§4.5①②・§4.6末尾に追記済み。ジャンルモジュール自体の詳細設計は [GENRE_DESIGN_V2.md](GENRE_DESIGN_V2.md) を参照 |
| 目的 | 現行 core の制約（4ch、16分固定格子、64 row約数、12平均律、静的チャンネル独立）を超え、ジャズ、変拍子、現代ベースミュージック、民族音楽等への拡張を可能にする |

---

## 0. 改訂履歴（v2.0）

- v2.0 Draft（2026 年前半）: §2 のジャンルマッピングと EXT-1〜6 の構想レベルの記述のみ。§8（音源合成基盤）を設計・実装し、既存4ジャンルを移行。
- v2.0（詳細設計版、2026-09-23）: EXT-1〜6 を「実装可能な粒度」まで詳細設計。設計の過程で判明した簡略化（後述）により、当初 draft で想定していたより新規コード量は小さくなった。既存 core（`model.py`/`engine.py`/`writer.py`/`verify.py`/`profiles/base.py`）への具体的な差分（§9）と、既存4ジャンル（nostalgic / suspense-slow / suspense-chase / march）への影響レビュー（§10）を追加。ジャンルモジュール自体の詳細設計は分量の都合で [GENRE_DESIGN_V2.md](GENRE_DESIGN_V2.md) に分離。
- **v2.1（Phase 4a 実装版、2026-09-23）**: §4.0 共通基盤（`CellGrid.insert_command`／`ChordSlot.rows`／`MeasureCtx.measure_rows`／`GenreProfile.variable_meter`）・EXT-1（`core/groove.py`）・EXT-2（`core/structure.py`＋engine 側の可変小節対応）を実装し、`swing-jazz`／`prog-rock` の2ジャンルを追加。§9・§10 で主張していた「既存4ジャンルは無変更・後方互換」を実測（989→1194件のテスト全緑、既存ジャンルの出力バイト列は不変）で確認済み。実装時に判明した設計の修正1件（§4.1① 末尾に追記: 密な編成では row 0 以外でも空きチャンネルが無い row が起こりうるため `apply_swing` は衝突時に例外を送出せず静かにスキップする）。
- **v2.2（Phase 4b 実装版、2026-09-23）**: EXT-4（`core/mixer.py`）・EXT-5①②（`core/automation.py`。`render_tempo_curve` は Phase 4c の free-jazz/maqam まで未使用だが Phase 4b で先行実装、`portamento_param` は trap で使用）を実装し、`future-bass`／`trap` の2ジャンルを追加（1194→1387件のテスト全緑）。実装時に判明した設計の修正2件: ① `automation.portamento_param`/`fine_portamento_param` に渡す period は **tracker note**（`t = 論理note - shift`）の `PERIODS` 添字でなければならず、論理 note をそのまま渡す当初案の例は誤りだった（§4.5②末尾に追記。`trap` の808実装で発覚）。② `future-bass` の kick/clap はチャンネル優先度を共有するため、backbeat では clap が kick を置換してしまい、`SidechainRule.trigger_sample=KICK` 単独では4拍のうち2拍しかダッキングされない（GENRE_DESIGN_V2.md §7.6 に追記: kick と clap の両方をトリガに登録して解決）。
- **v2.3（Phase 4c 実装版、2026-09-23）**: EXT-3（`core/pitch.py` に `MicroScale`／`resolve_micronote`／`fine_portamento_param`／`FINETUNE_CENTS` を追加）を実装し、Phase 4b で先行実装済みだった `automation.render_tempo_curve`（EXT-5①）に初めての利用者（`free-jazz`）が付いた。`maqam`／`free-jazz` の2ジャンルを追加（1387→1551件のテスト全緑）。両ジャンルとも `harmony.voice()`／`CHORD_QUALITIES` を経由しない手組み `ChordDef`（march/nostalgic の `explicit=True` 流儀）を採用し、EXT-3・EXT-5 以外の core 変更は不要だった（設計通り）。実装時に判明した知見: `free-jazz` の複数楽器で異なる `shift` を持つ場合、`ChordDef.chord_tones` を1つの音域に共有させると shift の違う楽器では無効な音域になる（`chord.bass`／`chord.harmony`（単一音）と `chord.chord_tones`（共有音域の楽器専用）を役割分担させて解決。両ジャンルの設計自体は変更不要、実装時の楽器割当の作法として §8.2 に反映）。
- **v2.4（Phase 4d 実装版、2026-09-23）**: EXT-2②（`core/structure.py` は Phase 4a で既に実装済みだった `polymetric_row()` に、初めての利用者 `minimalism` が付いた。core 自体への変更は0）で `minimalism` を追加（1551→1616件のテスト全緑）。実装時に判明した知見: 4チャンネル全てが固定パターンで row 0 に onset を持つ設計だと `apply_tempo`（row0 に1チャンネルの空きが必要）と衝突するため、最長周期チャンネル（woodblock、周期6row）の唯一のアクセントを意図的に row0 でなく row1 に置くことで row0 を常に1チャンネル空けた（§6.6 に既に記載していた「row0/row47 の空きチャンネル契約」の具体的な満たし方）。
- **v2.5（Phase 4e 実装版、2026-09-23）— EXT-1〜6・8ジャンル全て完了**: EXT-6（`SampleSpec.pan` 追加、`core/writer.py::serialize_xm`、`core/verify.py::parse_xm`/`verify_xm` 新設）を実装し `orchestral`（8ch, `target_format="xm"`）を追加（1616→1729件のテスト全緑）。§4.6①②（`SampleSpec.pan`／`engine.validate_profile` の4ch固定検査の条件分岐）は Phase 4a の実装時に既に完了していたことが判明（当時 EXT-6 を先取りして書いていた）。実装時に判明した設計の修正・知見（詳細は §4.6 末尾に追記）: ① header_size の値は設計時点の「276」という記憶に基づく数値が誤りで、実際に書き出すフィールド（8個の word フィールド16byte＋order table 256byte）から計算すると272になる（マジックナンバーではなく計算式で書くよう修正）。② XM の8bitサンプルデータは差分（delta）符号化が**必須**（設計時点の「delta=0でも合法」という想定は誤り。累積差分のデコード規約に従い実装）。③ ヴァイオリン/ヴィオラ/チェロ/コントラバスは同一 Patch を `shift` だけ変えて `dataclasses.replace()` で派生させる設計に簡略化（当初案の「ToneLayer 内部でのアンサンブル・デチューン」は、VLN1/VLN2 間の合奏感演出には使うが、VLA/VC/CB はそもそも別チャンネル・別音域の別楽器なので内部デチューンは不要と判断）。④ 6声の目標音は、§3.3 で設計段階で既に修正済みだった「`mctx.chord` から毎回導出する」方式をそのまま実装、`begin_pattern`/`state` すら不要と判明（`chord.chord_tones` のピッチクラス集合から直接計算できるため）。**実プレイヤーでの再生確認はまだ行っていない**（§11 参照。書込→独立パーサでの読み戻し→自己無矛盾性の検証は全12ジャンル×300 seed で実施済み）。

- **v2.6（実プレイヤー検証後の修正、2026-09-23）**: ユーザーが実際に `orchestral` を OpenMPT で開いたところ「パターンの中身が見えない」と報告。原因は `.xm` 出力の `header_size` の基準オフセットの誤り（詳細は §11-1）。`writer.XM_HEADER_SIZE` を 272→276 に、`verify.parse_xm` のオフセット計算式を `64+header_size`→`60+header_size` に修正。自己ラウンドトリップ検査（parse_xm での読み戻し）は書き手・読み手が同じ誤解を共有していたため終始グリーンのままこのバグを検出できず、外部ツール（OpenMPT）での確認で初めて発覚した。合わせて、実際のバイトオフセットを写経元の規約から独立に検算する回帰テストを追加（`tests/unit/test_writer.py::test_xm_header_size_field_locates_real_pattern_data_offset`）。また同じセッションで CLI 側の別バグ（`cli.py::default_output_path` が `target_format` を無視して常に `.mod` 拡張子を付けていたため、`orchestral` の実体が XM でも `.mod` 名で保存されていた）も発見・修正済み（そちらは中身自体は最初から正しかった）。
- **v2.7（出力形式選択・テンポ指定、2026-09-23）**: [FORMAT_TEMPO_DESIGN.md](FORMAT_TEMPO_DESIGN.md) を実装。`GenreProfile.target_format` を廃止し、出力形式は実行時に `--format`（既定 mod）で選ぶ方式へ（`core/formats.py` の能力表。mod/xm/s3m/it/midi/mp3）。EXT-6 の XM 出力について、実プレイヤー（ffmpeg 内蔵 libopenmpt）で MOD と再生比較した結果 **note 番号が 3 オクターブ低かった**（t+1 → 正しくは t+37）ことが判明し修正（header_size と同じく writer と parse_xm が同じ誤りを共有していたため自己ラウンドトリップでは検出不能だった）。XM の周波数表を linear → Amiga に変更（3xx 等のスライド量を MOD と一致させる）。swing-jazz（EXT-1）が表示 BPM の2倍で鳴っていた件を修正（§4.1 の `SwingConfig` は long+short=24 tick が必要）。以降、トラッカー形式の正しさは `tests/realplayer/`（libopenmpt による形式間の再生比較）で担保する。

### 設計を進める過程で判明した簡略化（要点）

draft 時点では EXT-2・EXT-3 が「新規 core クラス」として構想されていたが、詳細設計の結果、**大部分は既存のプリミティブ（`MeasureBuffer`／`Cell`／`Instrument`／`SampleSpec.finetune`）の組み合わせで表現でき、真に新規のコード面積はごく小さい**ことが分かった：

- EXT-2 ②「非同期ポリメトリック・バッファ」＝新規クラスは不要。`ChordSlot.rows` オーバーライド（§4.0）で「1 measure ＝ 複数チャンネルの周期の LCM 行数」を作り、各チャンネルは `row % cycle_rows` で自チャンネルの周期に折り返すだけ。`core/structure.py` にはこの折返しの1行ヘルパーのみを置く。
- EXT-3「マイクロチューニング層」＝新規モジュールは不要。`core/pitch.py` に純粋関数を数個追加するだけ（`SampleSpec.finetune` は既に差込口として存在する）。
- EXT-4 ②「サンプル・スライサー」＝新規状態クラスは不要。`9xx` の param 変換をする純粋関数1つ。
- EXT-5 の「808 グライド」＝新規状態クラスは不要。`3xx` の param（ポルタメント速度）を計算する純粋関数1つ。
- EXT-6「マルチチャンネル」＝ `CellGrid` は元から任意チャンネル数を受け付ける設計になっていた（`model.py` の既存コメント参照）。真に必要なのは ①4ch 固定の検査を条件分岐にする ②XM バイナリシリアライザ/パーサを書く ③パンニングを `SampleSpec` に1フィールド足す、の3点のみ。インストゥルメント単位のエンベロープ（当初 draft に記載）は、`core/synth.py` が合成時に既にアタック/減衰を PCM へ焼き込む設計（Patch.attack_ms/decay_alpha）と機能が重複するため、**v2.0 のスコープから明示的に外す**（§4.6・§11 参照）。

新規に「状態を持つクラス」が本当に必要なのは **EXT-1 の `SwingConfig`＋レンダラ**、**EXT-4 の `SidechainRule`＋レンダラ**、**EXT-5 の `TempoCurve`＋レンダラ**、**EXT-6 の XM シリアライザ/パーサ**の4つだけである。

---

## 1. 概要と背景

### 1.1. 現行 core（v1.x）の前提境界と限界
第一段階（v1.x）の設計は、**ProTracker `M.K.` 標準規格（Amiga 4ch）への完全適合**を最優先として確立された（当初は既存 Nostalgic とのバイト完全一致＝bit-exact も要件だったが、サンプル合成を `core/synth.py` の Patch 方式へ移行した際に撤回済み。§8 参照。ProTracker 規格適合の要件は不変）。これにより安定した基盤が得られた一方、以下の構造的境界が存在する：

1. **時間軸の固定性**: Speed 6 固定、4 row = 1 拍（16分音符格子）。スウィング、シャッフル、3連符の表現が不可。
2. **小節構造の硬直性**: 1 パターン = 64 row の約数（16 row または 8 row）のみを小節として許容。変拍子（5/8, 7/8 等）に対応不能。
3. **音響ポリフォニーの限界**: 4 チャンネル固定。アルペジオ（`0xy`）による疑似和音では、5パート以上の独立対位法や分厚いオーケストレーションが物理的に破綻。
4. **調性・音律の制約**: 12平均律（半音 0..35）と固定 Period 表に完全拘束。微分音（クォータートーン等）や非西洋音律が扱えない。
5. **チャンネル間の完全分離**: チャンネルは独立してバッファへ書き込まれ、他チャンネルの発音状況を検知して自チャンネルの音量・音色を動的変化させるリアクティブ機構（サイドチェイン等）が存在しない。

### 1.2. 本書の目的
本書は、これらの制約を解消し、表現可能な音楽語彙を飛躍的に拡張するための **core レイヤー第二段階拡張（v2.0）** のアーキテクチャ、追加データモデル、およびアルゴリズムを、実装に着手できる粒度で体系化するものである。

---

## 2. 対象ジャンルと必要 core 拡張のマッピング

| # | 対象ジャンル | 表現上の必須要件 | 現行 core の壁 | 必要となる core 拡張モジュール |
|:---|:---|:---|:---|:---|
| 1 | **スウィング・ジャズ / ビバップ** (`swing-jazz`) | ハネたリズム、シャッフル、8分/16分3連符 | 16分均等格子、Speed 6 固定 | **EXT-1**: タイムベース＆グルーヴ・エンジン |
| 2 | **変拍子プログレ / マスロック** (`prog-rock`) | 5/8拍子、7/8拍子、小節ごとの拍数変化 | `rows_per_measure` が 64 の約数固定 | **EXT-2**: 可変小節＆パターンブレイク |
| 3 | **フルオーケストラ / 劇伴** (`orchestral`) | 弦5部＋木管＋金管＋打楽器の重層ポリフォニー | 4 チャンネル固定 | **EXT-6**: マルチチャンネル (8〜16ch) |
| 4 | **トラップ / ドリル** (`trap`) | 32分/64分ハイハットロール、808ピッチスライド | 1 row 単位の粗い分解能、独立スライド | **EXT-1**: サブステップ・シーケンサー<br>**EXT-5**: グライド・ジェネレータ |
| 5 | **中東マカーム / インド古典** (`maqam`) | クォータートーン（微分音）、純正調的音程 | 12平均律半音インデックス固定 | **EXT-3**: マイクロチューニング層 |
| 6 | **ミニマル / フェーズ音楽** (`minimalism`) | パートごとに周期が異なるポリメトリック構造 | 全トラック同一小節境界同期 | **EXT-2**: 非同期ポリメトリック・バッファ |
| 7 | **フューチャーベース / グリッチ** (`future-bass`) | キック連動ダッキング（サイドチェイン）、波形細切れ | チャンネル間リアクティブ機構の欠如 | **EXT-4**: パート間リアクティブ・ミキサー |
| 8 | **フリージャズ / 現代無調音楽** (`free-jazz`) | テンポの連続加減速（ルバート）、無調音響 | パターン単位の固定 BPM、調性強制 | **EXT-5**: テンポオートメーション |

各ジャンルの具体的な音色・進行・文法設計は [GENRE_DESIGN_V2.md](GENRE_DESIGN_V2.md) を参照。本書はそれらが依拠する core 側の仕組みのみを扱う。

---

## 3. 第二段階 core 拡張アーキテクチャ

新規モジュールの実体は「状態を持つエンジン」ではなく、大半が **`Song`/`Pattern` を受け取り副作用として書き換える純粋関数群**である（既存の `profile.post_processors` フック、および `finalize_pattern` フックにぶら下がる）。

```mermaid
classDiagram
    direction TB
    class engine_py {
      +compose_song(profile, seed) Song
    }
    class CellGrid {
      <<core.model, 既存クラス>>
      +put(row, ch, cell)
      +replace(row, ch, cell)
      +insert_command(row, effect, param)  §4.0 共通化
    }
    class groove_py {
      <<EXT-1>>
      +SwingConfig
      +apply_swing(song, rows_ch, config)
      +retrigger_param(every_ticks) (effect,param)
      +delay_param(ticks) (effect,param)
    }
    class structure_py {
      <<EXT-2>>
      +polymetric_row(row, cycle_rows) int
      (ChordSlot.rows / MeasureCtx.measure_rows / GenreProfile.variable_meter は model.py/base.py 側)
    }
    class pitch_py_ext {
      <<EXT-3, core/pitch.py への追加>>
      +MicroScale
      +resolve_micronote(cents, ...) (t, finetune_cents_residual)
      +fine_portamento_param(period, cents) int
    }
    class mixer_py {
      <<EXT-4>>
      +SidechainRule
      +apply_sidechain(song, rules)
      +sample_offset_param(offset_samples, length_words) int
    }
    class automation_py {
      <<EXT-5>>
      +TempoCurve
      +render_tempo_curve(pattern, curve)
      +portamento_param(period_start, period_target, rows, ticks_per_row) int
    }
    class writer_verify_xm {
      <<EXT-6>>
      +serialize_xm(song) bytes
      +verify_xm(data, plan) list~Issue~
    }

    engine_py --> CellGrid
    engine_py --> writer_verify_xm
    groove_py --> CellGrid
    mixer_py --> CellGrid
    automation_py --> CellGrid
```

---

## 4.0. 共通基盤（全 EXT が依拠する core 側の変更）

以下は EXT-1〜6 のうち複数が共有する、または最も影響範囲の広い変更。§4.1 以降より先に導入する（依存関係上、これらが土台になる）。

### 4.0.1. `CellGrid.insert_command`（`apply_tempo` の一般化。置き場所の設計判断込み）

現行の `apply_tempo`（`engine.py`）は「`row` の空きチャンネルへ `Fxx` を挿入する」処理を1箇所に持つ。EXT-1（スウィング）・EXT-5（テンポカーブ）も全く同じ「row 単位でグローバルコマンドを1個、空いているチャンネルへ挿入する」操作を必要とするため、共通ヘルパーへ切り出す。

**置き場所**: このヘルパーは `Song`/`SongPlan`/`GenreProfile` のいずれにも依存せず、`CellGrid`（＝`Pattern`）だけで完結する。`engine.py` の自由関数にすると「`core/*.py`（groove/mixer/automation）や `profiles/*.py`（`finalize_pattern` フック経由で `Pattern` を直接受け取るプロファイル）が `engine.py` に依存する」という、既存の層構造（`profiles/*.py` は `core/*.py` にのみ依存し `engine.py` には依存しない。`engine.py` が `profiles.base` に依存する片方向）を壊す逆向き依存を生む。既存の `CellGrid.put`/`replace`/`get`/`serialize` と同じ粒度の操作でもあるため、**`CellGrid` のメソッドとして追加する**のが構造的に対称になる。

```python
# core/model.py: CellGrid に追加
class CellGrid:
    ...
    def insert_command(self, row: int, effect: int, param: int) -> None:
        """row の空きチャンネルへ (effect, param) を書き込む（``vol`` は使わない）。

        探索順序（既存 apply_tempo と同一）:
          ① is_empty なチャンネルのうち最小番号
          ② なければ、note を持つが vol も effect も持たないチャンネル
             （そのチャンネルの note/sample はそのまま残し、サンプル既定音量で鳴り続ける）
        いずれも無ければ ChannelConflictError。
        """
        for ch in range(self.channels):
            if self.get(row, ch).is_empty:
                self.replace(row, ch, Cell(None, 0, effect, param))
                return
        for ch in range(self.channels):
            c = self.get(row, ch)
            if c.note is not None and c.vol is None and not c.has_effect:
                self.replace(row, ch, Cell(c.note, c.sample, effect, param))
                return
        raise ChannelConflictError(f"no channel available for row command at row {row}")
```

```python
# engine.py: apply_tempo はこのメソッドを呼ぶだけになる
def apply_tempo(song: Song, bpm: int) -> None:
    """``order[0]`` の pattern の row 0 に ``F bpm`` を挿入する（tempo_policy="engine"）。"""
    song.patterns[song.order[0]].insert_command(0, 0x0F, bpm)
```

- 公開シグネチャ `apply_tempo(song, bpm)` は不変（既存テスト・呼出し元に影響なし）。挙動も完全に同一（アルゴリズムを1文字も変えずにメソッド抽出しただけ）。
- `groove.apply_swing`・`automation.render_tempo_curve`（いずれも `core/*.py`）は `pattern.insert_command(...)` を直接呼べる。`profiles/*.py` が `finalize_pattern(pctx, pattern, state, rng)` フック内で `pattern.insert_command(...)` を呼ぶケース（free-jazz の EXT-5 利用。GENRE_DESIGN_V2.md §8.6）も、既存の層構造を一切崩さずに実現できる。
- 受入基準: 既存の回帰テスト（`tests/regression/`, `tests/unit/test_engine.py`）が抽出前後でバイト完全一致すること。

### 4.0.2. 可変小節の下ごしらえ（EXT-2 の核。詳細は §4.2）

`model.ChordSlot` に `rows: Optional[int] = None` を追加し、`engine.compose_song` の measure ループを「固定 `rpm` の等間隔」から「累積オフセット」へ変更する。既存プロファイル（`rows` を指定しない）は数学的に同一の挙動になる（§9.1 で証明）。`GenreProfile.variable_meter: bool = False` を新設し、これが `False`（既定＝全既存ジャンル）のときは現行の「合計が厳密に64 row」という検査をそのまま維持する。

---

## 4. 各拡張モジュールの詳細仕様

### 4.1. EXT-1: タイムベース＆グルーヴ・エンジン (`core/groove.py`)

#### ① スウィング（チック・オルタネーション）

ProTracker では 1 row あたりのチック数（既定 Speed 6）を `F0x`（`effect=0xF, param<32`）で動的に変更できる。**スウィングは「1拍=4row の16分格子」ではなく「1拍=2row（8分音符格子）」を前提に、row の偶奇で Speed を交互に変える**ことで実現する（swing-jazz は `rows_per_measure=8`＝1 measure(4/4)=8row で運用。§ GENRE_DESIGN_V2.md 参照）。

```python
# core/groove.py
@dataclass(frozen=True)
class SwingConfig:
    long_speed: int = 8     # 偶数 row（拍の表）
    short_speed: int = 4    # 奇数 row（拍の裏）。long:short のティック比がスウィング比になる
    # 例: 8:4 = 2:1（純粋3連スウィング）。7:5 = 1.4:1（軽いスウィング、シャッフルではなくハネ弱め）

    def __post_init__(self) -> None:
        for v in (self.long_speed, self.short_speed):
            if not 1 <= v <= 31:
                raise SampleConstraintError(f"SwingConfig speed out of range: {v}")


def apply_swing(pattern: Pattern, config: SwingConfig, *, start_row: int = 0) -> None:
    """pattern の row 0..rows-1 に、偶数 row=long_speed／奇数 row=short_speed の F0x を
    ``CellGrid.insert_command`` で挿入する（row 0 自体が start_row からの相対偶奇で判定される）。

    row 0（かつこの pattern が order[0]、tempo_policy="engine"）は apply_tempo が同じ row に
    Fxx（BPM, param≥32）を挿入するため、プロファイルは row 0 に「別チャンネルの空き」を必ず
    1つ残す必要がある（§9.1 で apply_tempo との整合を検証）。
    """
    for row in range(start_row, pattern.rows):
        speed = config.long_speed if (row - start_row) % 2 == 0 else config.short_speed
        pattern.insert_command(row, 0x0F, speed)
```

- `apply_swing` は `profile.post_processors` に登録する後処理として使う（`Song`全体ではなく対象パターンごとに呼ぶラッパを profile 側で用意: `post_processors = (lambda song, plan: [apply_swing(p, SWING) for p in song.patterns],)`）。
- **呼び出し順序の注意**: `post_processors` は `apply_tempo` より**前**に実行される（`engine.compose_song` 参照）。よって row 0 では、まず `apply_swing` が空きチャンネルへ Speed を書き込み、続いて `apply_tempo` が「row 0 の別の空きチャンネル」を探して BPM を書く。プロファイルは row 0 に **2つ**空き（または note のみで vol/effect なし）のチャンネルを用意する契約になる。GENRE_DESIGN_V2.md の swing-jazz 設計はこれを満たすよう channel plan を組む。
- 曲全体を通して Speed の初期値（row 0 より前の状態）は ProTracker 既定の Speed 6 だが、`apply_swing` が row 0 から必ず明示的に Speed を書くため、初期値には依存しない。
- **実装で判明した修正（swing-jazz 実装時。2026-09-23）**: 4 チャンネル全てが同時に vol/effect を持つ row（例: ride＋walk bass＋melody が全て強拍で onset する row）では `insert_command` の挿入先が無い。row 0 だけでなく**全 row**についてこの問題が起き得ることが、実際に4パート密集編成（swing-jazz の "a"/"b" pattern）を書いて初めて判明した。対応として ``apply_swing`` は ``ChannelConflictError`` を送出せず、その row だけ静かにスキップするよう実装した（直前の Speed が persist するため、その1 row だけスウィングが掛からない程度の軽微な影響に留まる。§6「レイヤーの直交性」＝後処理の装飾は基本生成を汚染しないという方針に沿う）。実測（200 seed）では 1 曲（13 pattern）あたり平均1 row 程度のスキップに収まった。加えて、編成側でも row 0/2/4/6（拍の表）に和声パートの onset を集中させない設計（GENRE_DESIGN_V2.md §1.6 のコンピング・パターン変更）でスキップ頻度自体を下げている。新しいジャンル（trap 等）で `groove.apply_swing`（または将来 EXT-5 の `automation.render_tempo_curve`、同じ理由で同様のスキップ挙動を持つ）を使う場合、同じ配慮（強拍に全パートを同時オンセットさせない）が編成密度を保ちつつ衝突を減らす。
- **trap 用サブステップ**: 32分音符は `rows_per_measure=32`（64 の約数なので EXT-2 なしで既に合法）、64分音符は `rows_per_measure=64` で素直に表現できる。EXT-1 が真に追加するのは、それでも足りない密度（1 row 内で複数打を鳴らす）のための下記2関数のみ：

```python
def retrigger_param(every_ticks: int) -> tuple[int, int]:
    """E9x: ``every_ticks``（1..15）ティックごとに再トリガする。定数音量のロール専用
    （音量を変えたい場合は §4.1① ではなく行グリッドを細かくし composer.ramp で書く）。"""
    if not 1 <= every_ticks <= 15:
        raise SampleConstraintError(f"retrigger ticks out of range: {every_ticks}")
    return (0x0E, 0x90 | every_ticks)


def delay_param(ticks: int) -> tuple[int, int]:
    """EDx: note を ``ticks``（1..15）ティック遅延して発音する。"""
    if not 1 <= ticks <= 15:
        raise SampleConstraintError(f"delay ticks out of range: {ticks}")
    return (0x0E, 0xD0 | ticks)
```

呼び出し側（プロファイル）は `inst.cell(note, effect=e, param=p)` にそのままタプルを展開して渡すだけ（`Instrument.cell` は既存 API、変更不要）。**クレッシェンド・ロール**（打音ごとに音量が変わるロール）は retrigger では表現できない（E9x は音量制御を持たない）ため、行グリッドを細かくして `composer.articulate`＋`composer.ramp` で1打ずつ別 row に置く方式を使う（新規 core 不要、既存 `composer.py` の組み合わせ）。

#### ② 完全3連符タイムベース（1拍=6row）

4/4 で3連符を格子として使いたい場合、`rows_per_measure=24`（4拍×6row）としたいが 24∤64 なので EXT-2（§4.2）の可変小節が前提になる。EXT-1 自体に追加コードはない（§4.2 の仕組みをそのまま使う）。

---

### 4.2. EXT-2: 可変小節＆パターンブレイク (`core/structure.py` ＋ `model.py`/`engine.py` の変更)

#### ① 可変長 Measure と `Dxx` 自動挿入

**データモデル変更**（`core/model.py`）:

```python
@dataclass(frozen=True)
class ChordSlot:
    chord: ChordDef
    measures: int = 1
    rows: Optional[int] = None     # NEW: この slot の1 measureあたりの row数。None=profile.rows_per_measure
```

```python
@dataclass(frozen=True)
class MeasureCtx:
    pattern: PatternCtx
    measure_idx: int
    n_measures: int
    chord: ChordDef
    chord_measure_offset: int
    is_last: bool
    instruments: Mapping[str, Instrument]
    measure_rows: int = 16         # NEW: 現在の measure の実際の row 数（= buf.rows と同値）。
    # 既定値は GenreProfile.rows_per_measure の既定値と揃え、MeasureCtx を直接構築する既存テストの
    # 引数追加を不要にする（engine.compose_song は必ず明示的に渡すため既定値は実際の生成物に影響しない）
```

**`profiles/base.py` の変更**:

```python
class GenreProfile(ABC):
    ...
    variable_meter: bool = False   # NEW: True でパターン合計行数 < 64 を許容し D00 を自動挿入する
```

**`engine.py` の変更**（`compose_song` の measure ループと `validate_plan`/`validate_timebase`）:

```python
def validate_timebase(rows_per_measure: int) -> None:
    """rows_per_measure 単体の制約。variable_meter=True のプロファイルは
    ChordSlot.rows で上書きするため、profile.rows_per_measure はもはや「既定値」に過ぎず、
    この検査（64の約数）は variable_meter=False のときのみ適用する（呼び出し側で分岐）。"""
    if rows_per_measure <= 0 or ROWS_PER_PATTERN % rows_per_measure != 0:
        raise PlanError(f"rows_per_measure must divide {ROWS_PER_PATTERN}: {rows_per_measure}")


def validate_profile(profile: GenreProfile) -> None:
    if not profile.variable_meter:
        validate_timebase(profile.rows_per_measure)
    elif profile.rows_per_measure <= 0:
        raise PlanError(f"{profile.id}: rows_per_measure must be positive: {profile.rows_per_measure}")
    ...  # 他の検査は変更なし


def validate_plan(profile: GenreProfile, plan: SongPlan) -> None:
    where = f"[{profile.id}]"
    ...
    for i, pp in enumerate(plan.patterns):
        total = sum((s.rows if s.rows is not None else profile.rows_per_measure) * s.measures for s in pp.slots)
        if any(s.measures < 1 for s in pp.slots):
            raise PlanError(f"{where} pattern {i} ({pp.kind}): slot with measures < 1")
        if profile.variable_meter:
            if not 1 <= total <= ROWS_PER_PATTERN:
                raise PlanError(f"{where} pattern {i} ({pp.kind}): {total} rows exceeds {ROWS_PER_PATTERN}")
        elif total != ROWS_PER_PATTERN:
            raise PlanError(f"{where} pattern {i} ({pp.kind}): slots cover {total} rows, expected {ROWS_PER_PATTERN}")
    ...  # order 検査は変更なし
```

```python
def compose_song(profile: GenreProfile, seed: int) -> tuple[Song, SongPlan]:
    ...
    for idx, pp in enumerate(plan.patterns):
        pctx = PatternCtx(...)  # 変更なし
        state = profile.begin_pattern(pctx, rng)
        pattern = Pattern(profile.channel_plan, profile.strict_buffers)
        n_measures = sum(s.measures for s in pp.slots)
        m = 0
        row = 0                                            # NEW: 累積オフセット（旧: m * rpm）
        for slot in pp.slots:
            measure_rows = slot.rows if slot.rows is not None else profile.rows_per_measure   # NEW
            for k in range(slot.measures):
                mctx = MeasureCtx(
                    pattern=pctx, measure_idx=m, n_measures=n_measures, chord=slot.chord,
                    chord_measure_offset=k, is_last=(m == n_measures - 1), instruments=instruments,
                    measure_rows=measure_rows,                                                  # NEW
                )
                buf = MeasureBuffer(measure_rows, profile.channel_plan, profile.strict_buffers)  # CHANGED
                profile.compose_measure(mctx, state, rng, buf)
                pattern.blit(buf, row)                                                          # CHANGED
                row += measure_rows                                                             # CHANGED
                m += 1
        profile.finalize_pattern(pctx, pattern, state, rng)
        if profile.variable_meter and row < ROWS_PER_PATTERN:
            pattern.insert_command(row - 1, 0x0D, 0x00)    # NEW: D00（次 pattern の row0 へ break）
        patterns.append(pattern)
    ...
```

- `variable_meter=False`（既定）のとき: 全 `slot.rows is None` なら `measure_rows == profile.rows_per_measure` が全 measure で成立し、`row` は常に `m * profile.rows_per_measure` と数学的に一致する。`validate_plan` も従来通り `total == 64` を要求する。→ **既存4ジャンルの挙動・出力バイト列は不変**（§9.1）。
- `D00` の挿入先チャンネルは `CellGrid.insert_command`（§4.0.1）が担うため、プロファイルは最終 measure の最終 row に1チャンネルの空きを残す契約になる（`finalize_pattern` 実行後、かつ `post_processors`／`apply_tempo` 実行前）。
- 64 row を超える合計（`row > 64`）は `validate_plan` で弾く（プロファイルのバグ）。

#### ② 非同期ポリメトリック（minimalism 向け）

新規クラスは導入しない。「1 measure = 複数チャンネルの周期の最小公倍数（LCM）行数」を `ChordSlot(rows=lcm)` として1回だけ与え、`compose_measure` 内でチャンネルごとに周期で折り返して書く。唯一のヘルパー:

```python
# core/structure.py
def polymetric_row(row: int, cycle_rows: int) -> int:
    """row をチャンネル固有の周期 cycle_rows に折り返す（row % cycle_rows）。
    「周期ごとに用意した生成関数へ渡す行インデックス」を求めるためだけの1行関数。"""
    if cycle_rows <= 0:
        raise PlanError(f"cycle_rows must be positive: {cycle_rows}")
    return row % cycle_rows
```

具体的な周期・生成ロジックは GENRE_DESIGN_V2.md の `minimalism` 節を参照（例: ch1=16row周期、ch2=12row周期、ch3=18row周期 → LCM=144 は64を超えるため、実際は測定可能な小さい周期の組（例: 16/12/8, LCM=48）を選ぶ設計にする）。

---

### 4.3. EXT-3: マイクロチューニング (`core/pitch.py` への追加。新規ファイルなし)

12平均律のグリッド自体（`PERIODS` 36 音）は変更しない。差込口は既存の `SampleSpec.finetune`（±8ステップ、1ステップ≈7.8125セント）と、Cell の `effect=0xE` 系（`E1x`/`E2x` = fine portamento、1回だけ効く微小ピッチシフト）であり、どちらも**既に Cell/SampleSpec で表現可能**。EXT-3 が core に足すのは次の純粋関数・データのみ：

```python
# core/pitch.py に追加
FINETUNE_CENTS = 100.0 / 12.8   # 1 finetune ステップ ≈ 7.8125 セント（-8..+7 の等間隔仕様。ProTracker規格）

@dataclass(frozen=True)
class MicroScale:
    """cents 単位（tonic からの相対）で定義する音律。度数ごとに 12-ET から外れてよい。
    具体的な音律定義（maqam rast 等）は GENRE_DESIGN_V2.md 側に置く（本書はデータ構造のみ）。"""
    tonic_pc: int
    degrees_cents: tuple[float, ...]   # 度数0=主音(0.0)から始まる、主音からの相対セント列

    def degree_cents(self, degree: int, octave: int = 0) -> float:
        """``degree``（0始まり、スケール外は自動でオクターブ折返し）の、tonic からの相対セント。"""
        return self.degrees_cents[degree % len(self.degrees_cents)] + 1200.0 * (
            octave + degree // len(self.degrees_cents)
        )

    def absolute_cents(self, degree: int, tonic_note: int, octave: int = 0) -> float:
        """``degree`` の、logical note 0（C-1）からの絶対セント（``resolve_micronote()`` へそのまま渡せる）。

        ``tonic_note``: この音律を実際に鳴らす主音の logical note（例: qarar を G3 に置くなら
        ``pitch.parse("G-3")` 等で求めた値）。``tonic_pc`` は音律の「相対的な形」を表すだけで、
        実際にどのオクターブへ主音を置くかは呼出し側（プロファイル）が決める。
        """
        return tonic_note * 100.0 + self.degree_cents(degree, octave)


def resolve_micronote(cents_from_c0: float) -> tuple[int, int]:
    """logical note 0（C-1）からの絶対セント量 → (tracker/logical note t, finetune)。

    t = round(cents/100) の 12-ET 最近傍。残差 = cents - t*100 を finetune ステップに量子化
    （round(残差 / FINETUNE_CENTS)、-8..7 にクランプ）。t は呼出し側で NOTE_MIN..NOTE_MAX を検査する
    （既存 PitchRangeError を流用。本関数はクランプしない＝機械的単位変換のみ）。
    """
    t = round(cents_from_c0 / 100.0)
    residual = cents_from_c0 - t * 100.0
    ft = max(-8, min(7, round(residual / FINETUNE_CENTS)))
    return t, ft


def fine_portamento_param(period: int, cents: float) -> int:
    """現在の period に対し、目標セント差 ``cents`` に最も近づく E1x/E2x の param（0..15）を返す。
    符号は呼出し側（0x1=up/0x2=down）が選ぶ。1単位の効果は period 依存で非一様なため、
    目標 period（隣接 Period 表エントリからの線形補間）との差を都度計算する。
    """
    target_period = period * (2.0 ** (-cents / 1200.0))
    delta = abs(period - target_period)
    return max(0, min(15, round(delta)))   # PERIODS の隣接差は概ね数〜十数なので実用上 0..15 に収まる
```

- **finetune 経由（推奨・既定）**: マイクロトーン音を出す度数ごとに、`resolve_micronote()` で `(t, ft)` を求め、`dataclasses.replace(base_spec, finetune=ft)` で派生 `SampleSpec`（＝別 `Instrument` スロット）をジャンル側の `build_samples()` で事前登録する。1音律あたり最大 7〜8 派生（度数の異なる finetune 値の種類数）。`maqam` の設計（GENRE_DESIGN_V2.md）はこの方式を採用。
- **E1x/E2x 経由（装飾・ベンド用）**: 発音直後のセルに `Cell(effect=0xE, param=0x10|fine_portamento_param(...))` を重ねて、一瞬だけ微分音へベンドする演出（アプローチ音、擦弦楽器のポルタメント風味）に使う。恒常的な音律には使わない（1回きりの離散的シフトのため、以後の発音には影響しない）。
- `finetune` は7.8125セント刻みのため、正確な50セント（クォータートーン）は表現できない（最近傍は finetune=6 で 46.875セント、finetune=7 で 54.6875セント）。この近似誤差は GENRE_DESIGN_V2.md の maqam 設計に明記し、要件として許容する（人間の音程知覚の弁別閾はおよそ5〜10セントであり、実用上問題ない）。

---

### 4.4. EXT-4: パート間リアクティブ・ミキサー (`core/mixer.py`)

#### ① サイドチェイン・ダッキング

`post_processors` フックへ登録する後処理。**`SidechainRule.trigger_sample` はプロファイルが `build_samples()` で自ら決めている固定のサンプル番号（march.py の `BD, SD, ... = 1, 2, ...` と同じ慣習）を直接指定する**ため、`post_processors` のシグネチャ（`Callable[[Song, SongPlan], None]`）は変更不要。

```python
# core/mixer.py
@dataclass(frozen=True)
class SidechainRule:
    trigger_sample: int        # build_samples() 挿入順で決まるサンプル番号（プロファイルの定数）
    target_channel: int        # ducking 対象のチャンネル index（0始まり）
    duck_ratio: float = 0.3    # 元音量に対する比率（0..1）
    release_rows: int = 2      # トリガ後、元の音量へ線形復帰させる row 数

    def __post_init__(self) -> None:
        if not 1 <= self.trigger_sample <= 31:
            raise SampleConstraintError(f"trigger_sample out of range: {self.trigger_sample}")
        if not 0.0 <= self.duck_ratio <= 1.0:
            raise SampleConstraintError(f"duck_ratio out of range: {self.duck_ratio}")
        if self.release_rows < 0:
            raise SampleConstraintError(f"release_rows must be >= 0: {self.release_rows}")


def apply_sidechain(song: Song, rules: Sequence[SidechainRule]) -> None:
    for pattern in song.patterns:
        for rule in rules:
            _duck_pattern(pattern, rule)


def _trigger_rows(pattern: Pattern, trigger_sample: int) -> list[int]:
    return [
        r for r in range(pattern.rows)
        if any(pattern.get(r, c).sample == trigger_sample and pattern.get(r, c).note is not None
               for c in range(pattern.channels))
    ]


def _running_volume(pattern: Pattern, ch: int, upto_row: int, fallback: Optional[int]) -> Optional[int]:
    """target channel の ``upto_row`` 直前までを走査し、直近の実効音量を求める（verify._check_volume_sum
    と同じ後方追跡）。note+sample のみ（vol/effect なし）のセルはサンプル既定音量＝不明のため None（安全側でスキップ）。"""
    vol = fallback
    for r in range(upto_row):
        cell = pattern.get(r, ch)
        if cell.vol is not None:
            vol = cell.vol
        elif cell.note is not None and cell.sample and not cell.has_effect:
            vol = None
    return vol


def _duck_pattern(pattern: Pattern, rule: SidechainRule) -> None:
    ch = rule.target_channel
    triggers = _trigger_rows(pattern, rule.trigger_sample)
    vol = None
    for i, t_row in enumerate(triggers):
        vol = _running_volume(pattern, ch, t_row, vol)
        if vol is None:
            continue   # このトリガ直前の音量が不明 → 安全側で ducking をスキップ
        base_vol = vol
        _set_vol_preserving_effect(pattern, ch, t_row, round(base_vol * rule.duck_ratio))
        vol = round(base_vol * rule.duck_ratio)
        next_trigger = triggers[i + 1] if i + 1 < len(triggers) else pattern.rows
        release_end = min(t_row + rule.release_rows, next_trigger - 1, pattern.rows - 1)
        n = release_end - t_row
        for k in range(1, n + 1):
            r = t_row + k
            v = ramp(vol, base_vol, k, n + 1)     # composer.ramp を再利用
            if not _set_vol_preserving_effect(pattern, ch, r, v):
                break   # 既存の非vol effectセルに当たったら release を打ち切る（それを壊さない）
            vol = v


def _set_vol_preserving_effect(pattern: Pattern, ch: int, row: int, v: int) -> bool:
    """row の既存セルが note を持てば vol だけ差し替え、空セルなら vol-only セルを新設する。
    既に（vol以外の）effect を持つセルには手を出さない（False を返す）。"""
    cell = pattern.get(row, ch)
    if cell.is_empty:
        pattern.replace(row, ch, Cell(vol=max(0, min(64, v))))
        return True
    if cell.vol is not None or (cell.note is not None and not cell.has_effect):
        pattern.replace(row, ch, dataclasses.replace(cell, vol=max(0, min(64, v)), effect=0, param=0))
        return True
    return False
```

- `future-bass` はこれを `post_processors = (lambda song, plan: mixer.apply_sidechain(song, RULES),)` の形で使う。
- ducking は **`vol` フィールドのみを操作**し、note/sample を含むセルはそれを保った上で `vol` を差し替える（`0xC` へ変換されるのは serialize 時であり、Cell モデルの vol/effect 排他制約はそのまま守られる＝新しい Cell フィールドは不要）。
- 既存の非 vol effect セルは一切上書きしない（ducking が「勝手に他の演出を壊す」事故を構造的に防ぐ）。

#### ② サンプル・スライサー（`9xx`）

```python
def sample_offset_param(offset_samples: int, length_words: int) -> int:
    """9xx の param（オフセット = param*256サンプル）。offset_samples に最も近い 256 の倍数を
    0..255 にクランプして返す（長尺ブレイクビーツの特定位置を叩くため）。"""
    if offset_samples < 0:
        raise SampleConstraintError(f"offset_samples must be >= 0: {offset_samples}")
    if offset_samples > length_words * 2:
        raise SampleConstraintError(
            f"offset_samples {offset_samples} exceeds sample length ({length_words * 2} samples)"
        )
    param = round(offset_samples / 256.0)
    if param > 255:
        raise SampleConstraintError(
            f"offset {offset_samples} needs param {param} > 255 (sample too short for this offset)"
        )
    return param
```
**実装時の修正**: 当初案は `length_words` 引数を受け取りながら本体で一度も使っていなかった（デッドパラメータ）。実装時に `offset_samples` がサンプルの実際の長さを超えていないかの検査に使うよう修正した（`core/mixer.py` の実装と一致）。

新規クラスは不要（呼出し側がスライス名→`sample_offset_param(...)`の辞書をジャンルモジュール内にローカルに持てばよい。これは `synth_presets.py` の `find()` と同じ「参照データはローカルに置く」設計原則に合致する）。

---

### 4.5. EXT-5: テンポ＆ダイナミクス・オートメーション (`core/automation.py`)

#### ① テンポカーブ・レンダラ

`Pattern` への直接アクセスを持つ既存フック **`finalize_pattern(pctx, pattern, state, rng)`** から呼ぶ（新規フックは不要）。`tempo_policy="profile"`（既存の宣言的属性。既に `apply_tempo` をスキップする契約として実装済み）と組み合わせて使う。

```python
# core/automation.py
@dataclass(frozen=True)
class TempoCurve:
    start_bpm: int
    end_bpm: int
    start_row: int
    end_row: int
    curve_type: str = "linear"     # "linear" | "ease_in"（frac**2） | "ease_out"（1-(1-frac)**2）

    def __post_init__(self) -> None:
        for b in (self.start_bpm, self.end_bpm):
            if not 32 <= b <= 255:
                raise SampleConstraintError(f"bpm out of range for Fxx: {b}")
        if not 0 <= self.start_row < self.end_row:
            raise PlanError(f"TempoCurve rows must satisfy 0 <= start_row < end_row: {self}")
        if self.curve_type not in ("linear", "ease_in", "ease_out"):
            raise PlanError(f"unknown curve_type: {self.curve_type!r}")


def _frac(curve: TempoCurve, row: int) -> float:
    x = (row - curve.start_row) / (curve.end_row - curve.start_row)
    if curve.curve_type == "ease_in":
        return x * x
    if curve.curve_type == "ease_out":
        return 1.0 - (1.0 - x) ** 2
    return x


def render_tempo_curve(pattern: Pattern, curve: TempoCurve) -> None:
    prev_bpm: Optional[int] = None
    for row in range(curve.start_row, curve.end_row + 1):
        bpm = round(curve.start_bpm + (curve.end_bpm - curve.start_bpm) * _frac(curve, min(row, curve.end_row)))
        bpm = max(32, min(255, bpm))
        if bpm != prev_bpm:
            try:
                pattern.insert_command(row, 0x0F, bpm)
            except ChannelConflictError:
                log.debug("render_tempo_curve: no free channel at row %d, skipping (previous BPM persists)", row)
                continue
            prev_bpm = bpm
```

- `free-jazz`（ルバート）は `tempo_policy="profile"` を宣言し、`plan()` 内で最初の BPM を、最初の pattern を `finalize_pattern` した際に `pattern.insert_command(0, 0x0F, start_bpm)` で明示し、各 pattern の `finalize_pattern` で `render_tempo_curve` を1回以上呼ぶ設計になる（曲全体で連続的にうねる BPM を、pattern 境界をまたいで滑らかに繋ぐため、各 pattern の `start_bpm` は直前 pattern の `end_bpm` に一致させる。GENRE_DESIGN_V2.md 参照）。
- `CellGrid.insert_command` は「空きな最小番号チャンネル」を選ぶため、`TempoCurve` を使うプロファイルは対象行に必ず1チャンネルの空きを残す契約になる（swingと同様の制約。free-jazz は元々パート数を絞ったテクスチャなので両立しやすい）。
- **EXT-1 実装（`groove.apply_swing`）で判明した知見を反映**: 密な編成では row 0 以外でも4チャンネル全てが埋まる row が起こりうる（§4.1① 末尾）。`render_tempo_curve` も同じ理由で `ChannelConflictError` を送出せず、その row だけ静かにスキップする（直前の BPM が persist）。`apply_swing`（`core/groove.py`）と全く同じパターンであり、`core/automation.py` も `logging.getLogger("mod_weaver")` を使う同じ流儀にする。

#### ② 808 グライド（ポルタメント追従）

```python
def portamento_param(period_start: int, period_target: int, rows: int, ticks_per_row: int = 6) -> int:
    """3xx（Tone Portamento）の speed param。rows 行かけて period_start→period_target に到達する
    ように、1 tick あたりの period 変化量を概算する（PT のポルタメントは tick 毎に period を
    ±param だけ動かす）。"""
    total_ticks = max(1, rows * ticks_per_row)
    delta = abs(period_start - period_target)
    return max(1, min(255, round(delta / total_ticks)))
```

- 呼出し例: `shift = ins["kick808"].spec.shift` として `ins["kick808"].cell(note_low, effect=3, param=portamento_param(PERIODS[note_low - shift], PERIODS[note_high - shift], rows=2))` のように、既存 `Instrument.cell()` へそのまま渡す。新規 Cell フィールドは不要。**`PERIODS` の添字は tracker note（`t = n - shift`）であり logical note ではない**ことに注意（`chord.bass` 等はいずれも logical note。`profiles/trap.py` の実装で判明。§4.3 の `resolve_micronote()` が返す `t` も同様に tracker note なので、これは元々 PERIODS の添字だけがそのまま使える）。
- 3xx は目的 period を「直前に鳴らした note」から引き継ぐ ProTracker の仕様（3xx セルの note は「目的音高」、実際に鳴っている音からそこへ向けてスライドする）ため、直前セルで目的音を鳴らしてから 3xx へ切り替えるという既存の一般的な運用を GENRE_DESIGN_V2.md の trap 節で踏襲する。

---

### 4.6. EXT-6: マルチチャンネル＆ XM フォーマット拡張 (`core/writer.py` / `core/verify.py` / `model.py` / `engine.py`)

#### ① データモデル変更

```python
# core/model.py: SampleSpec に1フィールド追加
@dataclass
class SampleSpec:
    ...
    pan: int = 128    # NEW: 0=左、128=中央、255=右。MOD の serialize() は参照しない（既定値は無害）

    def validate(self) -> None:
        ...
        if not 0 <= self.pan <= 255:
            raise SampleConstraintError(f"sample {n!r}: pan out of range: {self.pan}")
```

Cell 自体は変更しない。パンニングは「サンプル（＝楽器）に固定」する設計とする（弦楽器セクションを左、金管を右、のような静的な配置が§2の要件の実体であり、行ごとに動的にパンを振る要求は8ジャンルのいずれにもない）。これにより Cell の vol/effect 排他制約（既存の不変条件）に一切触れずに済む。

#### ② 4ch 固定検査の条件分岐（`engine.py`）

```python
def validate_profile(profile: GenreProfile) -> None:
    if not profile.variable_meter:
        validate_timebase(profile.rows_per_measure)
    ...
    if profile.target_format == "mod":
        if len(profile.channel_plan) != NUM_CHANNELS:
            raise PlanError(f"{profile.id}: channel_plan must have {NUM_CHANNELS} roles for target_format=mod")
    else:
        if not 1 <= len(profile.channel_plan) <= writer.XM_MAX_CHANNELS:   # 32
            raise PlanError(f"{profile.id}: channel_plan must have 1..{writer.XM_MAX_CHANNELS} roles for XM")
    ...
```

`CellGrid`/`MeasureBuffer`/`Pattern`/`Pattern.blit` は既に任意チャンネル数を受け付ける実装になっている（`model.py` 冒頭のコメント通り）ため、これ以外のモデル層変更は不要。

#### ③ XM シリアライザ（`core/writer.py::serialize_xm`）

FastTracker II `.xm` 形式（バイナリレイアウトは公開仕様に準拠。§11 に実装時の検証手順を明記）。**v2.0 のスコープはチャンネル数拡張と固定パンニングのみ**とし、以下は明示的にスコープ外とする（§0 の簡略化の続き）:

- インストゥルメント音量/パンエンベロープ（`core/synth.py` の `Patch.attack_ms`/`decay_alpha`/`tail_fade_ms` が PCM に直接焼き込む設計と機能が重複するため不要。envelope フィールドは「無効」で書き出す）。
- XM ネイティブの「vol column と effect column の同時使用」（`Cell` の vol/effect 排他制約をそのまま流用し、XM の優越機能は使わない。1 セル1コマンドという既存の作曲文法をチャンネル数以外は変えない）。
- 複数サンプルを1インストゥルメントにキーマップする機能（1 `Instrument` スロット＝1 XM instrument＝1 sample の1:1対応のみ）。

概略構造（詳細フィールド順は実装時に `writer.py` 内のバイトレイアウト表として明文化する）:

1. モジュールヘッダ（ID "Extended Module: " + タイトル20byte + 0x1A + トラッカー名20byte + version + header_size + song_length + restart_pos + `n_channels=len(channel_plan)` + n_patterns + n_instruments + flags(linear周波数table採用) + default_tempo(=6) + default_bpm + order table）
2. パターンごとのヘッダ（header_length, packing_type=0, n_rows=64固定, packed_data_size）＋ XM のパック済みセル列（各セルは note/instrument/vol/effect/param を持ち、値が既定なら該当バイトを省略するビットフラグ方式。`Cell` → XM セルへのマッピングは「note+1（0=無音）」「instrument=sample番号」「vol column は常に未使用（0）」「effect/param はそのまま」）
3. インストゥルメントごとのヘッダ（instrument_header_size, name, type=0, n_samples=1）＋サンプルヘッダ（length, loop_start, loop_length, volume, finetune, sample_type(bit4=16bit未使用/ループ種別), panning=`SampleSpec.pan`, relative_note, name）
4. 全サンプルの PCM データ（XM は差分（delta）符号化が既定だが、**delta=0 の生 PCM でも合法**であるため、符号なし→符号付き変換以外の変換はしない差分無しモードを採用し実装を単純化する）。

`writer.WRITERS["xm"] = serialize_xm` として登録する（`WRITERS` の型は既存のまま）。

#### ④ XM 検査（`core/verify.py::parse_xm` / `verify_xm`）

`verify_mod` と同じ設計方針（独立パーサ、`struct` で直接読む）で XM 版を新設する。既存 V-code のうち転用できるもの: V04（サンプルヘッダ）, V06（未定義サンプル参照）, V07（note に sample 無し）, V13（未使用サンプル）。V15（左右音量合計）は「左右」から「パン0..255の加重和」へ一般化する（`weight_left=(255-pan)/255, weight_right=pan/255`）。V02（マジック）は `"Extended Module: "` の照合に、V01（ファイルサイズ）は可変長パターンデータのため「ヘッダから宣言された各サイズを積算した期待値」と比較する方式に変える。`verify.VERIFIERS["xm"] = verify_xm` として登録する。

---

## 5. データモデル拡張の最終形（差分一覧）

既存フィールドは一切変更しない（全て追加、かつ既定値ありで後方互換）。

| ファイル | 追加箇所 | 追加内容 | 既定値 | 由来 EXT |
|:---|:---|:---|:---|:---|
| `core/model.py` | `ChordSlot` | `rows: Optional[int]` | `None` | EXT-2 |
| `core/model.py` | `MeasureCtx` | `measure_rows: int`（engine が常に明示的に設定する） | `16` | EXT-2 |
| `core/model.py` | `SampleSpec` | `pan: int` | `128` | EXT-6 |
| `core/pitch.py` | モジュール直下 | `FINETUNE_CENTS`, `MicroScale`, `resolve_micronote()`, `fine_portamento_param()` | — | EXT-3 |
| `profiles/base.py` | `GenreProfile` | `variable_meter: bool` | `False` | EXT-2 |
| `core/model.py` | `CellGrid` | `insert_command()` メソッド | — | EXT-1/2/5（共通基盤） |
| 新規 `core/groove.py` | — | `SwingConfig`, `apply_swing()`, `retrigger_param()`, `delay_param()` | — | EXT-1 |
| 新規 `core/structure.py` | — | `polymetric_row()` | — | EXT-2 |
| 新規 `core/mixer.py` | — | `SidechainRule`, `apply_sidechain()`, `sample_offset_param()` | — | EXT-4 |
| 新規 `core/automation.py` | — | `TempoCurve`, `render_tempo_curve()`, `portamento_param()` | — | EXT-5 |
| `core/writer.py` | モジュール直下 | `serialize_xm()`, `XM_MAX_CHANNELS=32`, `WRITERS["xm"]` 登録 | — | EXT-6 |
| `core/verify.py` | モジュール直下 | `parse_xm()`, `verify_xm()`, `VERIFIERS["xm"]` 登録 | — | EXT-6 |

`Cell`（`note`/`sample`/`effect`/`param`/`vol`）は**一切変更しない**。EXT-1〜6 の全機能は、既存 Cell の5フィールドと `SampleSpec` への2フィールド追加のみで表現できる。これは §8.1 に既に述べられている「固定カテゴリを増やさない・機械的な単位変換のみ core に置く」という設計原則が、EXT-1〜6 でも一貫して成立したことを意味する。

---

## 6. 下位互換性（Backward Compatibility）戦略

**バイト単位の完全一致（bit-exact）は要件としない**（Nostalgic のサンプル合成を `core/synth.py` へ移行した際に撤回済み。§8）。本拡張を導入する際に維持するのは、**第一段階（v1.x）で作成された Nostalgic / Suspense / March の構造的な健全性と作曲ロジックの安定性**であり、以下の基本方針で担保する（§9 に既存4ジャンルへの影響の具体的な証明を記載）。**Phase 4a で追加した `swing-jazz`／`prog-rock` も、以後の Phase 4b〜4e（EXT-3〜6）にとっては「既存ジャンル」として同じ保護対象に加わる**（§10.5 で EXT-3〜6 がこの2ジャンルにも影響しないことを個別に確認する）：

1. **デフォルト挙動の維持 (Opt-in方式)**:
   - 新機能（スウィング、可変小節、サイドチェイン、XM出力等）はすべて Profile 側の明示的な宣言による Opt-in とする。
   - `strict_buffers=False` かつ標準宣言の Profile（Nostalgic）は、従来の `MeasureBuffer` とシリアライザをそのまま通過し、乱数消費順も一切変動させない（作曲ロジック＝`plan()`/`compose_measure()` は本拡張・§8 のいずれでも無変更）。
   - `variable_meter=False`（既定）のプロファイルは、§4.2 で証明した通り measure ループが数学的に旧実装と同一になる。
2. **レイヤーの直交性**:
   - EXT-1（`core/groove.py`）や EXT-4（`core/mixer.py`）は、基本生成が完了した後の「装飾・後処理パイプライン」として `post_processors`／`finalize_pattern` に差し込み、既存の生成フック（`compose_measure`）の純粋性を汚染しない（実装済みの EXT-1 で確認: `groove.apply_swing` はクラスではなく `Pattern` を受け取る関数として実装した。§4.1）。
3. **独立した検証ルール**:
   - 拡張フォーマット（XM）や変拍子パターンに対しては、`verify.py` に対応する拡張バリデータ（`verify_xm`）を独立新設し、現行の V01〜V16 ルールセットを破壊しない。
4. **`verify()` による構造検査は常にクリーン**:
   - バイト完全一致は求めないが、生成物が ProTracker 規格として妥当であること（`verify()` にエラーが無いこと）は全ジャンル・全 seed で維持する。

---

## 7. 段階的ロードマップ（Phase 4 以降）

第一段階（Phase 1〜3）の完了・安定稼働後、以下のステップで順次拡張を検証・実装する。**Phase 4a〜4e 全て実装済み**（下表）。EXT-1〜6・§2 の8ジャンル全てが完了した（残るのは EXT-6 の実プレイヤーでの再生確認のみ。§11）。

| マイルストーン | 拡張内容 | 実証ジャンル | 前提として先に要る core 変更 | 状態 |
|:---|:---|:---|:---|:---|
| **Phase 4a** | EXT-1（スウィング＆3連符）＋ EXT-2（可変小節＆Pattern Break） | `swing-jazz`<br>`prog-rock` | §4.0（`CellGrid.insert_command`／`ChordSlot.rows`／`variable_meter`） | **実装済み** |
| **Phase 4b** | EXT-4（サイドチェイン＆スライス）＋ EXT-1（サブステップ） | `future-bass`<br>`trap` | Phase 4a の `CellGrid.insert_command`（trap の EXT-5 グライドは Phase 4c 先取りで実装済み） | **実装済み** |
| **Phase 4c** | EXT-3（マイクロチューニング）＋ EXT-5（テンポオートメーション） | `maqam`<br>`free-jazz` | なし（§4.3・§4.5 は独立。EXT-5 は Phase 4b で実装済み） | **実装済み** |
| **Phase 4d** | EXT-2②（ポリメトリック） | `minimalism` | Phase 4a の `ChordSlot.rows` | **実装済み** |
| **Phase 4e** | EXT-6（FastTracker II `.xm` シリアライザ/パーサ） | `orchestral` | なし（独立。ただし工数最大・§11 の検証事項あり） | **実装済み**（実プレイヤーでの再生確認は未了。§11） |

実装順を Phase 4a→4e の順にした理由: (1) `CellGrid.insert_command` の抽出は最初に行い以後の全 EXT がそれに乗る、(2) EXT-6（XM）はコード量・検証コストが最大かつ他 EXT と依存関係がないため最後に回してリスクを隔離する。

---

## 8. 音源合成基盤（実装済み・EXT-1〜6 の前提条件）

§2 の8ジャンルはいずれも新しいサンプル音色を必要とするが、ジャンルごとにベタ書き DSP コードを増やしていくと `core` が「特定ジャンル専用の音色コレクション」で肥大化する（実際、march 追加時に顕在化した）。EXT-1〜6 の実装に着手する前に、この音源合成の基盤を別途設計・実装し、nostalgic / suspense-slow / suspense-chase / march の既存18音色（全て）をこの方式へ移行済み。

### 8.1. 設計方針: 直交レイヤー方式（固定カテゴリではない）

楽器ファミリー（打楽器／金属／持続音／撥弦 等）で分類するアプローチは、ティンパニや808サブベースのような「音程を持つ打楽器」、スネアのような「トーン層＋ノイズ層を別々の減衰率で混ぜる」音色を無理に押し込むことになり、検討の初期段階で撤回した。代わりに `core/synth.py` は次の直交する要素だけを公開する：

- **`Layer`**（信号源）: `ToneLayer`（加算合成、倍音ごとに減衰率を持てる）／`PitchSweepLayer`（打撃音のピッチドロップ）／`NoiseLayer`（フィルタ付きノイズ、減衰 or 上昇の包絡）
- **`Finish`**（仕上げ方）: `OneShot`（一発音）／`Loop`（完全ループ、アタック窓の有無を選べる）
- **`Patch`**: `layers` の重み付き合成＋後処理パイプライン（`post_filter` → `decay_alpha` → `attack_ms` → `tail_fade_ms` → 正規化 → `saturate`）＋サンプルの素性（`rate_note`/`shift`/`finetune`/`volume`）
- **`render(patch) -> SampleSpec`**: core が公開する唯一のエントリ

減衰・上昇を表すフィールドは全レイヤーで `Optional[float]`（`None`＝無効）に統一し、判別用の文字列フィールド（`shape` 等）は持たない。「知覚寄りの少数パラメータでパッチを組み立てるファクトリ関数」は一度試したが、複数の技術パラメータを1ノブに連動させる設計は**サンプル音源の設計自由度を犠牲にする**ため撤回した（連動が必要なら、その判断はジャンルモジュール側のローカルなヘルパー関数に置く）。詳細な設計原則は `core/synth.py` の module docstring を正とする。

### 8.2. プリセット・ライブラリ（`core/synth_presets.py`）

「望む音色から逆算してパラメータを探索するのが難しい」という懸念に対し、動作・音質を確認済みの `Patch` 値を集めた参照ライブラリを用意した。新しい音色が欲しいときは、まず `find(keyword)` で近い説明のプリセットを探し、`dataclasses.replace()` で差分だけ調整して `render()` → 試聴し、良ければ新しいプリセットとして追加する（ゼロから `Patch` を組み立てない）。これは型としての分類ではなく検索用の参照データであり、§8.1 の直交設計とは矛盾しない。

nostalgic 7・suspense 7・march 7 の計21プリセットが登録済み（`PRESETS`/`DESCRIPTIONS`）。EXT-1〜6 の実証ジャンル（swing-jazz 等）で新しい音色が必要になったら、ここに追加していく（GENRE_DESIGN_V2.md の各ジャンル節に、追加すべきプリセット名と Patch 構成の設計を記載済み）。

### 8.3. 既存ジャンルへの適用状況

nostalgic / suspense-slow / suspense-chase / march の全音色（nostalgic 7、suspense 7 ── suspense-slow/suspense-chase で共有、march 7。計21で §8.2 のプリセット数と一致）を Patch 方式へ移行済み。移行は1音色ずつ、実際にレンダリングして構造検査（`SampleSpec.validate()`）・ヘッドルーム・ループ境界等を確認しながら進めた。移行の過程で、既存コードだけを見ていては気付けなかった `core/synth.py` 側の不足（`Patch.tail_fade_ms`・`Loop` の循環フィルタ・`Patch.decay_alpha`・`Patch.peak=None`・`Patch.post_filter`）が判明し、その都度 core を直してから移行を続けた。最終的に `Patch`/`Layer` の命名・パラメータ設計の一貫性（`Optional[float]` の統一、単位をフィールド名に明記する等）を見直すリファクタも行っている。

**バイト完全一致は要件から外れた**（§6）。移行前後で数式・定数は同一値を用いており、ピーク振幅は全音色で一致、長さは秒数→サンプル数の丸め方式の違いにより数サンプル程度の差にとどまる（実測で確認済み）。作曲ロジック（`plan()`/`compose_measure()`）は一切変更していないため、Cell 配置は旧実装とバイト単位で今も一致する。

### 8.4. EXT-1〜6 実装時の指針

EXT-1〜6（本書 §4）で新しいジャンルプロファイルを追加する際、新規サンプル音色は次の順で検討する：

1. `core/synth_presets.py` の `find()` で近い音色を探す
2. 無ければ `core/synth.py` の `Patch`/`Layer` を直接組み立てる（新しい Layer 種別やカテゴリを core に追加しない。既存の3 Layer 型の組み合わせで大抵の音色は表現できることを§8.1・§8.3の移行作業で確認済み）
3. 動作確認が取れたら `core/synth_presets.py` にプリセットとして追加する

EXT-3（マイクロチューニング）は `Patch.finetune` フィールドが差込口として既にある。EXT-1/EXT-5（グルーヴ・オートメーション）が必要とするエフェクト（`E9x` リトリガ、ポルタメント、テンポカーブ等）は `core/synth.py` の管轄外（Cell/effect レベルの話であり、`core/composer.py` や各プロファイルの文法メソッドが担当する）。EXT-6 の `SampleSpec.pan` は `synth.render()` の戻り値に対して `dataclasses.replace(spec, pan=...)` で後付けする（`Patch` 自体にパンフィールドは持たせない。パンは「同じ音色をどのチャンネルへ置くか」というオーケストレーションの判断であり、音色合成そのものの関心事ではないため）。

---

## 9. 影響レビュー: 既存 core への変更点一覧と正当性

本セクションは、§4・§4.0 で提示した各変更が「既存コードの挙動を変えないこと」を個別に確認する（ユーザ指示: 「core への追加が必要なものは既存との一貫性・対称性を考慮した構造にする」の裏付け）。

### 9.1. `engine.py`

| 変更 | 既存挙動への影響 | 根拠 |
|:---|:---|:---|
| `apply_tempo` を `CellGrid.insert_command` 呼び出しへリファクタ | **なし** | アルゴリズムを1行も変えずにメソッド抽出。公開シグネチャ不変。既存回帰テストで確認する。 |
| `validate_timebase` の呼び出しを `variable_meter` で条件分岐 | **なし（既存4ジャンルは全て `variable_meter=False`）** | `False` のときは分岐が旧コードと同一の呼び出しになる。 |
| `validate_plan` の合計行数検査を `variable_meter` で条件分岐 | **なし** | `False` の分岐は `total != ROWS_PER_PATTERN` で従来と同一。 |
| `compose_song` の measure ループ（`row` 累積オフセット化） | **なし（数学的に同一）** | 全 `ChordSlot.rows is None` のとき `measure_rows = profile.rows_per_measure` が全 measure で成立し、`row` は `m * rpm` に一致。`MeasureBuffer(measure_rows, ...)` も旧 `MeasureBuffer(rpm, ...)` と同一引数になる。 |
| `validate_profile` の channel_plan 長検査を `target_format` で分岐 | **なし（既存4ジャンルは全て `target_format="mod"`）** | `"mod"` の分岐は `len(...) != NUM_CHANNELS` で従来と同一。**実装時の追加修正**: `target_format` 自体が `writer.WRITERS` に存在するかの検査を、この分岐より**前**に置くよう並び替えた（未対応 `target_format` を指定したとき、無関係な channel_plan 検査のエラーメッセージが先に出てしまう不整合を避けるため。既存4ジャンルは全て `target_format="mod"`＝`WRITERS` に存在するため、この並び替え自体は既存4ジャンルの挙動に影響しない）。 |

### 9.2. `core/model.py`

| 変更 | 既存挙動への影響 |
|:---|:---|
| `ChordSlot.rows: Optional[int] = None` 追加 | **なし**。既存の位置引数／キーワード引数呼び出し（`ChordSlot(chord, measures=n)`）は影響を受けない（末尾に既定値付きで追加）。 |
| `MeasureCtx.measure_rows: int = 16` 追加 | **なし**。末尾に既定値付きで追加（既定値は `GenreProfile.rows_per_measure` の既定値と揃えた）。`engine.py` 内の唯一の実運用構築箇所（`compose_song`）は明示的に渡す。`MeasureCtx(...)` を位置引数で直接構築しているテスト（`tests/profiles/test_suspense_common.py`）も既定値により無改修で通る（§10.4 で確認済み）。プロファイル本体のコードは `MeasureCtx` を構築しない（受け取るだけ）ため無影響。 |
| `SampleSpec.pan: int = 128` 追加 | **なし**。`writer.serialize()`（MOD）は `pan` を参照しない。`validate()` の新規検査は既定値 128 が常に通過する。 |
| `CellGrid.insert_command()` メソッド追加 | **なし**。新規公開メソッドの追加のみで、`put`/`replace`/`get`/`serialize`/`blit` 等の既存メソッドは無変更。§4.0.1 の通り `engine.apply_tempo` の内部実装がこれを呼ぶよう変わるが、公開挙動は同一。 |

### 9.3. `profiles/base.py`

`GenreProfile.variable_meter: bool = False` の追加のみ。既存4ジャンルは明示宣言しないため既定値 `False` が適用され、**無影響**。

### 9.4. `core/pitch.py` / `core/writer.py` / `core/verify.py`

いずれも「新しい公開関数・登録エントリの追加」のみで、既存の公開関数のシグネチャ・挙動は変更しない。`WRITERS`/`VERIFIERS` 辞書への `"xm"` キー追加は、既存の `"mod"` キーの値・参照方法に影響しない。

### 9.5. Phase 4a 実装で判明し、本書の当初案になかった追加変更（`core/composer.py` / `core/pitch.py`）

以下2点は設計段階（v2.0 詳細設計版）では想定しておらず、`swing-jazz` の実装中に必要と判明して追加した。いずれも既存4ジャンルへの影響がないことを個別に確認する：

| 変更 | 既存挙動への影響 | 根拠 |
|:---|:---|:---|
| `composer.MelodyGenerator.__init__` に `beat_rows: int = BEAT_ROWS`（=4）を追加し、`bar()` 内の `strong = row % BEAT_ROWS == 0` を `row % self.beat_rows == 0` に変更 | **なし**。既定値 `BEAT_ROWS`（モジュール定数、変更なし）と等しいキーワード引数を末尾に追加しただけ。既存4ジャンルは `MelodyGenerator(...)` 呼出し時に `beat_rows` を渡さないため、常に既定値＝旧コードと同じ `BEAT_ROWS` が使われ、`bar()` の分岐結果は旧実装とビット単位で同一になる。 | swing-jazz は 1拍=2row（8分音符 timebase）のため `beat_rows=2` を明示的に渡す。既存4ジャンルは全て 1拍=4row（16分音符格子）を前提にしており、`BEAT_ROWS=4` の既定値のままで正しい。 |
| `core/pitch.MODES` に `"dorian"`／`"mixolydian"` の2エントリを追加 | **なし**。辞書への追加のみで既存キー（`"ionian"`/`"aeolian"`/`"phrygian"`/`"dim_wh"`）は無変更。既存4ジャンルのモード参照は文字列キーで固定されており、新規キーの存在に依存する分岐は無い。 | swing-jazz が `harmony.voice()` の `mode_by_quality` 引数（既存の差込口。§6.6、D14）でドミナント7th＝ミクソリディアン、マイナー7th＝ドリアンの経過音を選ぶために使用。 |

いずれも「後方互換な追加のみで既存4ジャンルを変更しない」という §6 の Opt-in 方針に沿っており、EXT-1〜6 の当初設計（Cell 5フィールド＋SampleSpec 2フィールドで全て表現できるという§5の主張）にも矛盾しない（`beat_rows`/`MODES` はどちらも Cell/SampleSpec とは独立した「作曲補助ロジックのパラメータ化」であり、新規データモデルフィールドではない）。

---

## 10. 影響レビュー: 既存ジャンル・モジュールへの影響

対象（Phase 4a 実装前に存在した4ジャンル。§10.1〜§10.4）: `profiles/nostalgic.py`、`profiles/suspense_common.py`（`suspense-slow`/`suspense-chase` 共有）、`profiles/march.py`。Phase 4a で追加された `profiles/swing_jazz.py`／`prog_rock.py`（EXT-3〜6 の観点での影響）は §10.5 で別途確認する。

### 10.1. 結論

**4ジャンルとも、コード変更は不要（0行）。** §9 で示した通り、全ての core 変更が `variable_meter=False` / `target_format="mod"` / `ChordSlot.rows=None` という「既存4ジャンルが宣言している値そのもの」を既定値として後方互換になるよう設計されているため。**Phase 4a 実装後に実測で確認済み**（`profiles/nostalgic.py`・`march.py`・`suspense_common.py` 等は本改修で1行も変更していない）。

### 10.2. 出力（.mod バイト列）への影響

**影響なし。** §9.1 の「数学的に同一」の証明により、`compose_song` が生成する `Pattern`/`Cell` の列は EXT-2 の core 変更前後で完全に同一になる。§6 で既に「bit-exact は要件でない」ことが撤回済みだが、本改修ではその緩い基準すら使う必要がなく、**旧実装とバイト完全一致のままである**（§8.3 で述べた「合成後の音色移行に伴う数サンプル程度の差」は本改修とは無関係の既往事象であり、本改修自体は追加でその差分すら生まない）。既存の回帰テスト（`tests/regression/`）が改修前後で変更なく全て緑であることで確認済み。

### 10.3. `post_processors` の非利用について

既存4ジャンルとも `post_processors` を宣言していない（既定の空タプル）ままであり、本改修でも変更していない。EXT-4（サイドチェイン）・EXT-1（スウィング）が同フックを使うのは新規ジャンル側（`swing-jazz` が `apply_swing` を `post_processors` 経由で実際に使用。§4.1①）であり、**フックの実行自体（`for post in profile.post_processors: post(song, plan)`）は既存コードにあり変更しない**ため、既存4ジャンルの空タプルには何も起きない。

### 10.4. 実装時に必要な機械的な追随作業（設計判断を含まないハウスキーピング）

以下は「設計」ではなく、コード変更に伴う機械的な追随のみ。実装フェーズのタスクリストとして記録する（本書の設計自体はこれらを前提に完結している）：

1. ~~`tests/profiles/test_suspense_common.py` 内で直接構築している `MeasureCtx(...)` 呼び出しに `measure_rows=` キーワード引数を追加する~~ →
   **実装時に不要と判明**: `MeasureCtx.measure_rows` は（本書の当初案「既定値なし」から変更し）`= 16`
   をデフォルト値として実装した（`GenreProfile.rows_per_measure` の既定値と揃えた）。これにより
   `MeasureCtx(...)` を7引数の位置引数で直接構築している既存テストコードは無改修のまま通る。実際の
   合成経路（`engine.compose_song`）は毎回明示的に `measure_rows=` を渡すため、この既定値が実際の生成物
   へ影響することはない。
2. `tests/unit/test_engine.py` の `apply_tempo` テストは公開シグネチャ・挙動が不変のため変更不要だった
   （`CellGrid.insert_command` のリファクタ後も同一テストで検証が成立することを実装で確認済み）。
3. EXT-6 で `writer.WRITERS`/`verify.VERIFIERS` に `"xm"` を追加した後、`engine.validate_profile` が `target_format` 未対応値を弾く既存の検査（`if profile.target_format not in writer.WRITERS`）は変更不要（`"xm"` が候補に増えるだけ）。実装時の追加知見: この検査は他の検査（channel_plan 長など）より**先に**実行する必要がある（§9.1 参照。未対応 `target_format` に対して誤った理由のエラーメッセージを出さないため）。

### 10.5. Phase 4b で追加された EXT-4／EXT-5 の実装が既存6ジャンルに与えた影響（実測）

Phase 4a で追加された `swing-jazz`／`prog-rock` も、Phase 4b 以降にとっては「既存ジャンル」であり同じ後方互換の保護対象になる（§6）。EXT-4（`core/mixer.py`）・EXT-5①②（`core/automation.py`）は Phase 4b で実際に実装済みのため、他の5ジャンル（nostalgic/suspense-slow/suspense-chase/march/swing-jazz/prog-rock）への影響は実測で確認した：

| 追加 | 既存5ジャンルへの影響 | 根拠 |
|:---|:---|:---|
| 新規 `core/mixer.py`（`SidechainRule`/`apply_sidechain`/`sample_offset_param`） | **なし（実測確認済み）** | いずれも `post_processors` に `mixer` を参照するエントリを持たない（`future-bass` のみが使う）。新規ファイルのため import しない限り無関係。 |
| 新規 `core/automation.py`（`TempoCurve`/`render_tempo_curve`/`portamento_param`） | **なし（実測確認済み）** | 全て `tempo_policy="engine"` で `automation` を参照しない（`trap` のみが `portamento_param` を使う）。新規ファイルのため無関係。 |
| `core/groove.py`／`core/structure.py` 自体への変更 | なし（Phase 4b はこの2ファイルを変更していない） | `swing-jazz` が使う `apply_swing`／`SwingConfig` はそのまま。 |

989（Phase 4a 前）→1194（Phase 4a 後）→**1387（Phase 4b 後）**件のテストが全緑であり、既存6ジャンルのコード自体は Phase 4b で1行も変更していない。

### 10.6. Phase 4c で追加された EXT-3 の実装が既存8ジャンルに与えた影響（実測）

Phase 4c で `core/pitch.py` に `MicroScale`／`resolve_micronote()`／`fine_portamento_param()`／`FINETUNE_CENTS` を追加したが、いずれのジャンルも `finetune`／マイクロトーン機能を使わない（`maqam` のみが使用）ため既存7ジャンルへの影響は**なし（実測確認済み）**。1387（Phase 4b 後）→**1551（Phase 4c 後）**件のテストが全緑であり、既存7ジャンル（Phase 4a・4b で追加された4ジャンルを含む）のコード自体は Phase 4c で1行も変更していない。

### 10.7. Phase 4d で EXT-2② に付いた初利用者が既存9ジャンルに与えた影響（実測）

Phase 4d は `core/structure.polymetric_row()`（Phase 4a で実装済みだったが Phase 4b・4c では未使用のまま）に `minimalism` という初めての利用者が付いただけで、**`core/structure.py` 自体への変更は一切無い**。既存9ジャンル（Phase 4a〜4c で追加された6ジャンルを含む）への影響は**なし（実測確認済み）**。1551（Phase 4c 後）→**1616（Phase 4d 後）**件のテストが全緑であり、既存9ジャンルのコード自体は Phase 4d で1行も変更していない。

### 10.8. Phase 4e で追加された EXT-6 の実装が既存10ジャンルに与えた影響（実測。全 Phase の最終確認）

Phase 4d で追加された `minimalism` も同様に「既存ジャンル」として保護対象に加わった。EXT-6 実装
（`SampleSpec.pan` 追加、`writer.serialize_xm`/`verify.parse_xm`/`verify_xm` 新設、`WRITERS["xm"]`/
`VERIFIERS["xm"]` 登録）の既存10ジャンルへの影響は**なし（実測確認済み）**。全ジャンルとも
`target_format="mod"`（既定値のまま）であり、`SampleSpec.pan` は末尾に既定値付きで追加のため
各ジャンルの `build_samples()` は無改修で動く。`WRITERS`/`VERIFIERS` への `"xm"` キー追加は `"mod"`
キーの参照に影響しない。1616（Phase 4d 後）→**1729（Phase 4e 後）**件のテストが全緑であり、既存10
ジャンルのコード自体は Phase 4e で1行も変更していない。

**Phase 4a〜4e 全体を通しての結論**: EXT-1〜6 はいずれも「新規ファイル追加」「既存データクラスへの
末尾デフォルト付きフィールド追加」「既存フックの初利用」のいずれかであり、Phase 4a 開始前に存在した
4ジャンル（nostalgic/suspense-slow/suspense-chase/march）を含む**全12ジャンルに対して、5フェーズを
通じて一切のコード変更・出力変化が発生していない**（§6 で立てた Opt-in 方針が最後まで一貫して守られた）。

---

## 11. 実装時の要検証事項（設計時点では確定できない／経験的確認が必要な項目）

本書の EXT-1〜5 は既存コードベースの規約（Period 表、Cell の4バイト構造、既存エフェクト番号）に基づく机上検証で確度が高いが、以下は**実装時に実物（実機/エミュレータ/トラッカーソフト等）で確認する必要がある**:

1. **XM バイナリレイアウト（EXT-6）— 実プレイヤー(OpenMPT)で「パターンが空に見える」不具合を発見・修正済み**: `writer.serialize_xm`／`verify.parse_xm`／`verify_xm` を実装し、(c)「独立パーサでの自己検査」は完了していた（全12ジャンル×300 seed で `parse_xm` の消費バイト数がファイルサイズと一致し `verify_xm` に ERROR が出ないことを確認済み）が、それだけでは不十分だった。実装中に発見・修正した誤りは3箇所:
   ① `header_size` の**基準オフセットの誤り**（2026-09-23、実プレイヤー(OpenMPT)で発見）。実際の FT2/XM 規約は「`header_size` フィールド自身（offset 60、4byte）を含めて」order table 終端までの長さを書き、読み手は pattern データの開始位置を `60 + header_size` として求める。実装当初はこれを「`header_size` フィールドの直後（offset 64）を起点」と誤解し、`header_size=272`（`60+276`ではなく`64+272`で辻褄を合わせた値）を書いていた。`writer.serialize_xm` と `verify.parse_xm` の両方が同じ誤った規約で書いて読んでいたため、**自己ラウンドトリップ検査ではこのズレを検出できなかった**（両者が同じ間違った基準を共有していたため常に一致していた）。実プレイヤーは正しい `60+header_size` 規約で読むため、書き出された272という値では実際のパターンデータ開始位置(336byte目)より4byte手前から読み始めてしまい、パターン先頭が完全に文字化けし「パターンの中身が見えない」症状になっていた。`header_size=276`（`4 + 8*2 + 256`）に修正し、`verify.parse_xm` 側も `60 + header_size` を使うよう修正、さらに実際のバイトオフセットを独立に検算する回帰テスト（`test_xm_header_size_field_locates_real_pattern_data_offset`）を追加した。**この種の「書き手と読み手が同じ誤解を共有していると自己検査だけでは検出できない」バグは、実プレイヤー等の第三者実装での検証がなぜ省略できないかを示す実例**。
   ② `header_size` の値そのもの（①とは独立に、設計時点の記憶に基づく数値「276」を実装当初に一度272へ「修正」してしまっていた——結果的に①の誤りと組み合わさって当初の276という記憶値は正しかったことが判明）。
   ③ XM の8bitサンプルデータは「差分（delta）符号化不要（delta=0でも合法）」という想定が誤りで、**差分符号化は必須**（各バイトが直前サンプル値との差分。デコードは累積和）と判明し実装した（これは実プレイヤーではなく仕様の再読で判明、修正済み）。
   **(b) 波形・パンニングの実プレイヤーでの目視確認はまだ未実施**: パターン内容が見える状態にはなったが、実際に音が正しく鳴るか（波形・音程・パンニング）はユーザーの実プレイヤー環境での確認待ち。
2. **スウィングの聴感**（EXT-1①）: `SwingConfig(long_speed, short_speed)` の比率と実際に聴いた際の「シャッフル感」の対応は、机上のティック比計算通りに知覚されるとは限らない（BPM とテンポ知覚の非線形性）。GENRE_DESIGN_V2.md の swing-jazz 実装時に複数比率を試聴して初期値を確定する。
3. **サイドチェイン・リリースの聴感**（EXT-4①）: `duck_ratio`/`release_rows` の初期値は GENRE_DESIGN_V2.md の future-bass 節に暫定値を記載しているが、試聴による微調整が前提（§8.3 の音色移行と同じ「動作確認しながら詰める」運用）。
4. **`fine_portamento_param` の実効セント数**（EXT-3）: E1x/E2x の1単位あたりの実効セント量は period 依存で理論式は §4.3 に記載したが、実機・実エミュレータでの検証は未実施。maqam 実装時に確認する。
