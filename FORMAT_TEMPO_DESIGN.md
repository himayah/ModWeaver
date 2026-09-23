# 出力形式選択・テンポ指定 設計書（第１段階）

| 項目 | 内容 |
|:---|:---|
| 対象 | `次の検討事項.txt` 第１段階（① 出力形式の指定、② テンポの指定） |
| 前提ドキュメント | [CORE_EXTENSION_DESIGN.md](CORE_EXTENSION_DESIGN.md)（v2.6。EXT-6＝XM 出力）、[GENRE_DESIGN_V2.md](GENRE_DESIGN_V2.md) |
| ステータス | **実装済み**（branch `stage1-format-tempo`）。§9 の決定事項は確定済み、実装で判明した修正は §10 |
| 作成日 | 2026-09-23 |

---

## 0. 要求（原文の整理）

- **R1 出力形式**: `.mod`／`.it`／`.xm`／`.s3m`／`.mp3`／`.midi`（General MIDI）を指定できる。**指定が無ければ `.mod`**。
- **R2 テンポ**: BPM を指定できる。`80-100` のような範囲指定なら、その範囲からランダムに決める。
  指定が無ければ従来どおりジャンルごとにプログラムが決める。

---

## 1. 調査で判明した前提事項（設計に影響するもの）

### 1.1 既存 XM 出力は 3 オクターブ低く鳴っている（既存バグ・実測で確定）

`writer._pack_xm_cell()` は tracker note `t`（0=ProTracker の C-1＝period 856）を XM note `t+1`（FT2 の
C-0）として書いているが、period 856 に相当する FT2 の音は **C-3（XM note 37）**。
同じ Song を MOD と XM に書き出し、sandbox の ffmpeg 内蔵 **libopenmpt**（＝OpenMPT の再生エンジン、
第三者の実プレイヤー）で再生して比較した結果:

| 出力 | 平均周波数（ゼロ交差法、nostalgic seed=123456 先頭20秒） |
|:---|---:|
| MOD | 600.4 Hz |
| XM（現行） | 118.8 Hz |
| XM（note +36 に修正） | 605.7 Hz |

→ `orchestral` の `.xm` は現在 3 オクターブ低く鳴っている。**今回 XM を全ジャンルで選べるようにする以上、
本段階で必ず修正する**（§4.2）。`verify.parse_xm` 側も同じ規約で読んでいるため自己ラウンドトリップ検査では
検出できなかった（header_size バグと同じ構造。CORE_EXTENSION_DESIGN §11 の教訓の再発）。

### 1.2 実プレイヤーが sandbox で使える

`/usr/bin/ffmpeg`（4.4.2）が `libopenmpt` デマルチプレクサと `libmp3lame` エンコーダを内蔵している。
これにより:

- MOD/XM/S3M/IT を**第三者の実プレイヤーでデコードする自動テスト**が書ける（本段階の検証戦略の柱。§7）。
- MP3 は「トラッカー形式 → ffmpeg(libopenmpt) → mp3」で生成できる（§5）。

### 1.3 「BPM」の単位はジャンルごとに体感テンポと一致しない場合がある

`tempo_choices`／バナーの `BPM` は tracker の `Fxx`（≥0x20）の値そのもの。1拍＝24 tick（Speed 6 で 4 row）
を前提とした値なので、1拍の row 数が 4 でないジャンルでは体感テンポとずれる。libopenmpt で実測した再生時間:

| ジャンル | tracker BPM | 1拍の row 数 | 実測（4分音符換算） | 備考 |
|:---|---:|---:|---:|:---|
| nostalgic | 90 | 4 | 89.9 | 一致 |
| trap | 150 | 8 | 75 | 設計どおりのハーフタイム（trap は慣習的に「140」と呼ぶので妥当） |
| swing-jazz | 168 | 2 | **336** | GENRE_DESIGN_V2 の「ミディアムスウィング 152–168」の意図と 2 倍ずれている疑い |

→ **ユーザー判断により修正済み**（§9 Q3）。swing-jazz の Speed を 7/5 → 14/10（同じ 1.4:1、1拍=24 tick）に変更し、
表示 BPM どおりに鳴るようにした。全ジャンルの「表示 BPM どおりの再生時間」を libopenmpt で検査するテストを追加
（`tests/realplayer/test_tempo_real_player.py`）。trap は表示 BPM＝trap の慣習的な数え方（ハーフタイムの倍）で妥当と判断し変更なし。

### 1.4 使用中のエフェクト（変換表の対象）

全ジャンル・core を grep した結果、Cell に現れうるエフェクトは次のとおり（これ以外は変換不要。
未知のエフェクトが来たら各 writer は例外で止める＝将来ジャンル追加時に黙って化けない）:

`0xy`（アルペジオ）、`3xx`（ポルタメント）、`4xy`（ビブラート）、`9xx`（サンプルオフセット）、
`Cxx`（音量＝`Cell.vol`）、`D00`（パターンブレイク）、`E9x`（リトリガ）、`EDx`（ノートディレイ）、
`Fxx`（<0x20＝Speed、≥0x20＝Tempo）。加えて `pitch.fine_portamento_param` 由来の `1xx`/`2xx`（maqam で使用の可能性）。

---

## 2. 全体方針

`engine.compose_song()` が作る `Song`（Cell＝MOD 風のエフェクト表現）を**形式中立の中間表現**として扱い、
出力形式ごとの差はすべて writer 層で吸収する。作曲ロジック（profiles/*）は形式を一切意識しない。

```
profile.plan() ─▶ compose_song() ─▶ Song ─┬─▶ serialize()       → .mod（4ch=M.K. / N ch=xCHN）
       ▲ tempo override (§3)              ├─▶ serialize_xm()    → .xm
                                          ├─▶ serialize_s3m()   → .s3m   （新規）
                                          ├─▶ serialize_it()    → .it    （新規）
                                          ├─▶ serialize_midi()  → .mid   （新規、core/timeline.py 経由）
                                          └─▶ render_mp3()      → .mp3   （新規、XM → ffmpeg/libopenmpt）
```

### 2.1 `target_format` の扱い

- 出力形式は **CLI/engine 引数で決める**。`GenreProfile.target_format` は廃止する（唯一の利用者
  `orchestral` の `target_format="xm"` も削除）。
- 代わりに `engine.validate_profile()` の「チャンネル数 × 形式」検査を**形式側の能力表**に置き換える（§2.2）。
  プロファイルは「自分は何チャンネルか」だけを宣言し、形式との整合は engine が生成前に検査する。

### 2.2 形式の能力表（`core/formats.py`、新規）

| format | 拡張子 | チャンネル数 | 音量の置き場 | パン | 備考 |
|:---|:---|:---|:---|:---|:---|
| `mod` | `.mod` | 4 → `M.K.`、1–32 → `xCHN`/`xxCH` | effect `C` | プレイヤー固定（LRRL…） | 既定。orchestral(8ch) は `8CHN` になる（§9 Q1） |
| `xm` | `.xm` | 1–32 | effect `C`（現行どおり） | sample pan＋vol column `Px` | §4.2 |
| `s3m` | `.s3m` | 1–16（PCM は L1–L8／R1–R8 まで） | vol column（S3M に音量エフェクトは無い） | ヘッダのチャンネルパン | §4.3 |
| `it` | `.it` | 1–64 | vol column | ヘッダのチャンネルパン＋sample 既定パン | §4.4 |
| `midi` | `.mid` | 制限なし（MIDI 16ch は楽器単位で割当） | velocity／CC11 | CC10 | §6 |
| `mp3` | `.mp3` | XM に準ずる（1–32） | ― | ― | §5 |

```python
@dataclass(frozen=True)
class OutputFormat:
    name: str                      # "mod" など（CLI の値）
    extension: str                 # ".mod"、".mid" など（midi だけ名前と拡張子が違う）
    max_channels: int
    serialize: Callable[[Song, WriteOptions], bytes]    # mp3 も ffmpeg の出力をバイト列で返す（書込は共通の原子的書込）
    verify: Callable[[bytes, ChannelPlan], list[Issue]] | None

FORMATS: dict[str, OutputFormat]   # 既存の writer.WRITERS / verify.VERIFIERS はこれに統合する
```

`WriteOptions` は profile 由来の形式中立な付帯情報（チャンネルパン、GM 音色表、初期 BPM）を運ぶ。
`Song` 本体は変えない。

### 2.3 チャンネルパン（新概念、形式中立）

MOD はプレイヤーが LRRL を強制するが、他形式では自前で決める必要がある。`engine` が次の規則で
`channel_pans: tuple[int, ...]`（0=左、128=中央、255=右）を決め `WriteOptions` に入れる:

1. プロファイルが `channel_pans` を宣言していればそれを使う（新規の任意属性。既定 `None`）。
2. 宣言が無く、全サンプルの `SampleSpec.pan` が既定の 128 なら、Amiga 風 **L R R L** を繰り返す
   （ただし 0/255 の完全分離は耳障りなので **64/192** 程度に緩める。§9 Q5）。
3. 宣言が無く、明示的なサンプルパンがある（＝orchestral）なら、各チャンネルで最初に鳴るサンプルの pan を
   そのチャンネルのパンとする（orchestral はチャンネル＝楽器固定なのでこれで意図どおりになる）。

各形式での使い方: S3M/IT はヘッダへ、XM は「サンプルパンが既定(128)のサンプルを鳴らすセル」の
vol column に `Px` を書く（XM は発音のたびにサンプル既定パンへ戻るため）、MIDI は CC10、MOD は無視。

---

## 3. テンポ指定（R2）

### 3.1 BPM の単位

`--tempo` の値は **4分音符の BPM**（＝tracker の Fxx 値。1拍＝24 tick）とし、全ジャンルがその値どおりに
鳴るようにした（§9 Q3 の決定。ずれていた swing-jazz を修正）。

- `tempo_choices`・バナーの `BPM`・再現コマンドの `--tempo` はすべて同じ単位。
- trap だけは 32分格子のハーフタイムなので、表示 BPM は trap の慣習的な数え方（例: 150 → 体感 75）。README に明記。

### 3.2 CLI

```
--tempo, -t  BPM | MIN-MAX     例: -t 120 / -t 80-100
```

- 整数のみ。`MIN<=MAX`。全体の許容範囲は **32–255**（`Fxx` で Tempo と解釈される範囲。32 未満は Speed になる）。
- 構文エラー・範囲外は argparse エラー（終了コード 2）。

### 3.3 ジャンルごとの許容範囲

一部のジャンルは BPM から row 数を計算している（suspense の `swoosh_start_row`／`anvil_clear_row`、
free-jazz のテンポカーブ）。極端な BPM で破綻しないよう `GenreProfile.tempo_range: tuple[int, int]`
（既定 `(32, 255)`）を追加し、該当ジャンルだけ狭める。具体値は**実装時に 32–255 × 複数 seed を総当たりして
PlanError／verify ERROR が出ない範囲を実測で決める**（机上で決めない）。

要求範囲と `tempo_range` の関係:

| 状況 | 動作 |
|:---|:---|
| 要求範囲が `tempo_range` に完全に含まれる | そのまま |
| 一部だけ重なる | 重なり部分に切り詰め、WARNING を出す |
| 重ならない | エラー（終了コード 2）。メッセージにそのジャンルの許容範囲を出す |

### 3.4 乱数と再現性

- 範囲からの選択は**専用ストリーム** `random.Random(f"{seed}:{profile.id}:tempo")`（`RngStreams.for_seed`
  と同じ命名規約）で行う。
- プロファイルの `plan()` は従来どおり自分で `tempo_choices` から BPM を引く（**引いた値は捨てる**）。
  こうすると他の乱数消費が一切変わらないため、**「同じ seed・別テンポ」＝「同じ曲が速さだけ違う」**になる。
  nostalgic（`rng_mode="single"`）でも乱数列がずれない。
- `--tempo` 未指定時は何も変わらない（既存出力はバイト単位で不変）。

### 3.5 engine の変更

```python
def compose_song(profile, seed, *, tempo: TempoRequest | None = None) -> tuple[Song, SongPlan]:
    ...
    plan = profile.plan(rng)
    if tempo is not None:
        plan = dataclasses.replace(plan, bpm=resolve_tempo(tempo, seed, profile))
    validate_plan(profile, plan, tempo_overridden=tempo is not None)
```

- `validate_plan`: 上書き時は「`bpm in tempo_choices`」の代わりに「`bpm in tempo_range`」を検査する。
- テンポを使う箇所はすべて `plan.bpm`→`PatternCtx.bpm`/`MeasureCtx.pattern.bpm` 経由なので自動で追従する
  （nostalgic の自前 `F bpm` 挿入、suspense の row 計算、engine の `apply_tempo` を確認済み）。
- **free-jazz だけ要修正**: `TEMPO_CURVES` が絶対値（96→82…150…70）なので、`pctx.bpm / INITIAL_BPM` 倍に
  スケールする。クランプでカーブの形を崩さないよう、拡大後も全点が 32–255 に収まる開始 BPM（44–163）だけを
  `tempo_range` として許す。未指定時は倍率 1.0 で従来と完全一致。バナーのカーブ表示は開始 BPM に対する倍率にした。
- `SongPlan.bpm` の型・意味は変えない。

### 3.6 表示と再現コマンド

```
Tempo       : BPM 92 (requested 80-100)
...
  modweaver --genre nostalgic --tempo 92 --format it --seed 123456
```

再現コマンドには、指定されたときだけ `--tempo <確定値>` と `--format` を付ける（範囲ではなく確定値を出す）。

---

## 4. トラッカー形式の writer

### 4.1 MOD（既存を拡張）

- 4ch は従来どおり `M.K.`（既存出力はバイト単位で不変）。
- 4ch 以外は FastTracker 系の多チャンネル MOD: 1–9ch は `"{n}CHN"`、10–32ch は `"{n:02d}CH"`。
  パターンは既存の `Pattern.serialize()`（4 byte/cell を row 優先でチャンネル数ぶん並べる）がそのまま使える。
- 注意: 本家 ProTracker/Amiga では 4ch 以外は再生不可。OpenMPT／MilkyTracker／libxmp 等は対応。
  orchestral のステレオ配置（サンプル pan）は MOD では失われる（プレイヤーの LRRL になる）。
- `verify_mod` をチャンネル数可変に一般化する（現在は 4ch・`M.K.` 前提）。

### 4.2 XM（既存を修正・拡張）

1. **音高修正（§1.1）**: XM note = `t + 37`（1始まり。t=0 → C-3）。`verify.parse_xm` の逆変換も同時に直す。
   回帰テストは「libopenmpt で MOD と XM を再生して周波数が一致する」ことを検査する（自己ラウンドトリップで
   はなく第三者の再生結果で検査する。§7）。
2. **チャンネルパン**: §2.3 の規則で vol column `Px`（`0xC0 | pan>>4`）を、サンプル既定パンが 128 の
   サンプルを発音するセルに付ける。音量は従来どおり effect `C`（Cell の vol/effect 排他制約をそのまま流用）。
3. ヘッダの初期 BPM を 125 固定から `plan.bpm` に変更（先頭 row の `Fxx` を読まないプレイヤー対策。既定値の改善）。

### 4.3 S3M（新規 `writer.serialize_s3m`）

- ヘッダ `SCRM`、`Cwt/v`=0x1320、`ffi`=2（unsigned サンプル）、初期 speed 6 / tempo=`plan.bpm`、
  master volume はステレオ bit を立てる。チャンネル設定: パン≤128 → 左（0–7）、それ以外 → 右（8–15）。
  さらに channel pan テーブル（`0x20 | pan>>4`）を書き、`dp`=0xFC で有効化する。
- サンプル: 8bit **unsigned**（signed ^ 0x80）、`C2Spd = round(8363 × 2^(finetune/96))`（finetune 1 単位＝1/8 半音）。
  ループは `SampleSpec.loop` からバイト単位で。
- 音高: S3M note = `((t // 12) + 3) << 4 | (t % 12)`（t=12＝period 428＝ST3 の C-4）。
- 音量: `Cell.vol` → volume column（S3M には Set Volume エフェクトが無いため必須）。
- エフェクト変換:

  | MOD | S3M/IT | 備考 |
  |:---|:---|:---|
  | `0xy` | `Jxy` | |
  | `1xx`/`2xx` | `Fxx`/`Exx` | xx ≥ 0xE0 は fine/extra-fine と解釈されるので 0xDF にクランプ |
  | `3xx` | `Gxx` | |
  | `4xy` | `Hxy` | IT は深さの解釈が異なる（§4.4） |
  | `9xx` | `Oxx` | |
  | `D00` | `C00` | 行番号 0 のみ使用のため BCD/HEX の差は問題にならない |
  | `E9x` | `Q0x` | 音量変化なしリトリガ |
  | `EDx` | `SDx` | |
  | `ECx` | `SCx` | 現状未使用だが変換表には入れる |
  | `Fxx` (<0x20) | `Axx` | Speed |
  | `Fxx` (≥0x20) | `Txx` | Tempo |
  | その他 | 例外 | 黙って落とさない |

- パターンは 64 row 固定・パック形式、パラポインタ（16byte 境界）。

### 4.4 IT（新規 `writer.serialize_it`）

- **サンプルモード**（Flags bit2=0、インストゥルメント不使用）で書く。1 Instrument = 1 IT sample。
  エンベロープ・NNA 等 IT 固有機能は使わない（XM と同じスコープ方針）。
- `Cmwt`=0x0214、Flags: stereo=1、linear slides=**0**（Amiga slide で MOD と同じ挙動）、
  Old Effects=**1**（ビブラート深さ等を MOD 互換にする。§7 の聴感比較で最終確認）。
- 初期 speed 6 / tempo=`plan.bpm`、global volume 128、mix volume 48（実装時に音量バランスを MOD と比較調整）。
- チャンネルパン 64 byte（0–64 スケール、未使用チャンネルは +128 で無効）、チャンネル音量 64。
- サンプル: 8bit signed（Cvt bit0=1）、非圧縮、`C5Speed = round(8363 × 2^(finetune/96))`、
  既定パン（DfP、bit7 で有効）は明示パンのあるサンプル（orchestral）だけ設定。
- 音高: IT note = `t + 48`（t=12 → C-5＝C5Speed で再生）。
- 音量: vol column、エフェクト: §4.3 の表と同じ文字。パターンはチャンネルマスク方式のパック形式。

---

## 5. MP3（新規）

### 5.1 方式: 外部 ffmpeg（libopenmpt＋libmp3lame）に委譲する（推奨）

1. 内部で XM バイト列を生成（§4.2 修正後。任意チャンネル数とサンプルパンを保持できる最も忠実な既存形式）
2. 一時ファイルに書き、`ffmpeg -f libopenmpt -i tmp.xm -c:a libmp3lame -b:a 192k -metadata title=... out.mp3`
3. 一時ファイルを削除。書込は既存 `write_file` と同じく一時名→`os.replace` で原子的に。

**理由**: 自前のトラッカー再生エンジン（ミキサー＋全エフェクトの tick 処理＋リサンプリング）は大きく、
しかも「自作 writer を自作 player で検証」という §1.1 と同じ自己一致の罠に陥る。libopenmpt は OpenMPT
そのものの再生エンジンなので音質・互換性が最も高い。Python の実行時依存は増えない（現状どおりゼロ）。

**代償**: 利用者の環境に「libopenmpt 入りの ffmpeg」が必要（Windows なら gyan.dev の full build 等。
essentials build に libopenmpt が入っているかは要確認）。

- 起動時チェック: `ffmpeg` が PATH に無い／`-demuxers` に `libopenmpt` が無い／`-encoders` に `libmp3lame`
  が無い場合は、何が足りないかを明示したエラーで終了（新しい `ExternalToolError`、終了コード **5**）。
- ffmpeg のパスは環境変数 `MODWEAVER_FFMPEG` で上書き可能にする。
- 代替案（不採用理由）: ① 自前レンダラ＋`lameenc` → 巨大・自己一致の罠・numpy 無しでは遅い。
  ② pure Python MP3 エンコーダ → 現実的でない。

### 5.2 検証

生成した mp3 を ffmpeg でデコードし、長さが `core/timeline.py`（§6.1）の計算した曲長と ±0.5 秒以内、
無音でないこと、クリップ率が閾値以下であることを検査する。

---

## 6. MIDI（General MIDI、新規）

### 6.1 共通基盤: `core/timeline.py`（新規）

Song を **tick 単位で再生解釈**する純粋関数。order を辿り、`Fxx`（Speed/Tempo）・`D00`・`EDx`・`E9x`・
`0xy` を処理して、`(tick, 絶対秒, channel, 発音/音量変化/停止, …)` のイベント列と曲長を返す。
MIDI writer と MP3 の長さ検証、将来の verify の曲長チェックで共有する（トラッカー writer は不要）。

### 6.2 SMF の構成

- **SMF format 1、PPQ=96**。1 tracker tick = 4 MIDI tick、4分音符 = 24 tracker tick
  （Speed 6 の 4 row）。tempo meta = `60,000,000 / bpm` µs/4分音符。
  → Speed 変化（swing-jazz の 7/5 交互）や `EDx` は**tick 数そのものが変わるだけで厳密に再現**される。
  テンポカーブ（free-jazz）は tempo meta イベントの列になる。
- Track 0: 曲名（`Song.title`）、tempo、拍子（`rows_per_measure/4` 拍の 4/4 等。可変拍子ジャンルは
  `ChordSlot.rows` から小節ごとに出す）。
- 以降: **楽器（Instrument）ごとに1トラック**。MIDI チャンネルは楽器単位で割り当てる
  （トラッカーの1チャンネルが複数楽器を鳴らす＝ドラムチャンネル等に対応するため）。
  - ドラム楽器 → MIDI ch 10（index 9）に集約
  - 旋律楽器 → ch 1–9, 11–16 を sample 番号順に。15 を超えたら同じ GM program の楽器を同一チャンネルに相乗り。
    それでも足りなければエラー（現行12ジャンルは全て収まる）。

### 6.3 GM 音色表（プロファイルの新しい宣言）

```python
@dataclass(frozen=True)
class GmVoice:
    program: int | None = None       # 0..127（旋律楽器）
    drum_note: int | None = None     # 35..81（GM ドラム。指定時は ch10・音高固定）
    # どちらか一方だけを指定

class SwingJazzProfile(GenreProfile):
    gm_voices = {
        "ride": GmVoice(drum_note=51), "brush": GmVoice(drum_note=38),
        "bass": GmVoice(program=32),   "piano": GmVoice(program=0), "sax": GmVoice(program=65),
    }
```

- 楽器名からの推測（キーワード表）はしない。明示宣言のみとし、**全登録ジャンルの全楽器に宣言があること**を
  テストで保証する（第３段階で約35ジャンル追加されるため、推測に頼ると誤変換が静かに増える）。
- 本段階で既存12ジャンル分の `gm_voices` を全て書く。

### 6.4 変換規則

| トラッカー | MIDI | 精度 |
|:---|:---|:---|
| 音高 | **実際に鳴る高さ**から求める（§10-4）。`SampleSpec.sounding_hz`（rate_note で鳴らしたときの実音）× period 比 | 厳密 |
| 音色固有の半音未満のずれ＋finetune（maqam の微分音含む） | 楽器チャンネル単位の固定ピッチベンド（±2半音レンジ） | 厳密（楽器単位割当なので可能） |
| 発音時の音量（`Cell.vol` or sample 既定音量） | velocity = `round(vol/64×127)`、最小 1 | 厳密 |
| 発音中の音量変化（`vol` のみのセル、サイドチェイン等） | CC11。その楽器を同時に鳴らしているトラッカーチャンネルが1つのときのみ | 近似 |
| 音の終わり | 同チャンネルの次の発音／`vol=0`（`Instrument.off()`）／`ECx`／**ワンショットサンプルの自然減衰長**（サンプル長÷再生レート）／曲末 の最も早いもの | 厳密 |
| `EDx`／Speed 変化 | tick 位置に反映 | 厳密 |
| `E9x` | x tick ごとの再発音 | 厳密 |
| `0xy` | tick ごとの音高切替（note on/off） | 厳密 |
| `3xx`／`1xx`／`2xx` | 本段階では**グライドせず目標音へ即時切替**（ピッチベンド近似は将来課題） | 近似 |
| `4xy` | CC1（モジュレーション）を深さに比例させ、次の発音で 0 に戻す | 近似 |
| `9xx` | 無視（MIDI に相当機能なし。future-bass のヴォーカルチョップは頭から鳴る） | 非対応 |
| チャンネルパン | CC10（楽器チャンネル単位。§2.3 の値のうちその楽器を最初に鳴らしたチャンネルのもの） | 近似 |

MIDI は「ジャンルの意図を GM 音源で聴ける／DAW に持ち込める」ことが目的であり、サンプル音色の再現は
目的外（音色は GM 音源次第）であることを README に明記する。

---

## 7. 検証戦略（本段階の最重要事項）

CORE_EXTENSION_DESIGN §11 と §1.1 の教訓: **自作 writer を自作 parser で読み戻すだけの検査は、仕様の誤解を
検出できない**。新形式はすべて第三者の実装で検証する。

| 検査 | 方法 | 対象 |
|:---|:---|:---|
| 構造 | 既存方式の自己ラウンドトリップ（各形式の parse＋verify） | mod/xm/s3m/it |
| **実プレイヤー再生** | ffmpeg(libopenmpt) でデコードでき、エラー出力が空、無音でない | mod/xm/s3m/it/mp3 |
| **形式間の等価性** | 同じ Song を MOD と各形式で libopenmpt 再生し、① 曲長（±1%）② 平均周波数（±3%、§1.1 の方法）③ RMS 包絡の相関 が一致 | xm/s3m/it（MOD を基準） |
| 曲長 | `core/timeline.py` の計算値と libopenmpt 再生長の一致 | 全ジャンル（timeline 自体の検証を兼ねる） |
| MIDI | SMF を独立パーサ（開発依存に `mido` を追加）で読み、ノート数・音高範囲・曲長が timeline と一致 | midi |
| MIDI の音高の根拠 | `SampleSpec.sounding_hz` をサンプルデータの自己相関（YIN）で検算 | 全ジャンルの音高のある音色 |
| timeline | 曲長が libopenmpt の再生時間と一致 | 全ジャンル |
| GM 宣言 | 全ジャンルの全楽器に `gm_voices` がある | midi |
| テンポ | `-t` 指定時、曲長が BPM に反比例する（libopenmpt 実測）／未指定時に既存出力がバイト不変 | 全ジャンル |

- libopenmpt を使うテストは ffmpeg が無い環境では skip（`pytest.mark.requires_ffmpeg`）。
- 12ジャンル × 6形式 × 複数 seed を CI 相当で回す（従来の 300 seed 総当たりは構造検査のみ、実再生は数 seed）。
- 自動テストに加え、ユーザーに OpenMPT での実機確認（開ける・音高・パン・スウィング）を依頼するチェックリストを
  実装完了時に出す。MIDI は GM 音源（Windows 標準の Microsoft GS Wavetable Synth 等）での試聴を依頼する。

---

## 8. 変更一覧と実装順序

### 8.1 変更ファイル

| ファイル | 変更 |
|:---|:---|
| `core/formats.py` | **新規**。`OutputFormat`／`FORMATS`／`WriteOptions`／`channel_pans` 決定規則 |
| `core/writer.py` | MOD の xCHN 対応、XM 音高修正・vol column パン・初期 BPM、`serialize_s3m`／`serialize_it` 追加 |
| `core/midi.py` | **新規**。SMF writer、`GmVoice` |
| `core/timeline.py` | **新規**。tick 解釈と曲長計算 |
| `core/render.py` | **新規**。ffmpeg 呼出し（検出・mp3 生成） |
| `core/verify.py` | MOD の N ch 化、XM 音高逆変換修正、S3M/IT の parse＋verify 追加 |
| `engine.py` | `generate(..., fmt=, tempo=)`、`resolve_tempo`、`validate_profile` の形式能力表化、`validate_plan` の上書き対応 |
| `profiles/base.py` | `target_format` 削除、`tempo_range`・`channel_pans`・`gm_voices` 追加 |
| `profiles/*.py` | 全12ジャンルに `gm_voices`、必要なジャンルに `tempo_range`、orchestral の `target_format` 削除、free-jazz のカーブスケール |
| `cli.py` | `--format/-f`、`--tempo/-t`、既定出力パスの拡張子を `FORMATS[fmt].extension` から、バナー・再現コマンド |
| `errors.py` | `ExternalToolError`（終了コード 5） |
| `README.md`・`CORE_EXTENSION_DESIGN.md` | 使い方、形式ごとの制約、BPM の単位の注記、改訂履歴 |
| `requirements-dev.txt` | `mido`（テスト専用） |

### 8.2 実装順序（各ステップで全テスト緑を保ってコミット）

1. **XM 音高修正**（§4.2-1）＋ libopenmpt による形式間等価性テスト基盤（§7）。既存バグなので最初に単独コミット。
2. テンポ指定（§3）。形式と独立しており小さい。
3. `core/formats.py` 導入と `target_format` 廃止、`--format`、MOD xCHN、XM パン（§2, §4.1, §4.2）。
4. S3M（§4.3）→ 5. IT（§4.4）。それぞれ実プレイヤー検証込みで。
6. `core/timeline.py` → 7. MIDI（§6）＋全ジャンルの `gm_voices`。
8. MP3（§5）。
9. ドキュメント更新、OpenMPT 実機確認チェックリストをユーザーへ。

---

## 9. 決定事項（2026-09-23 ユーザー確認済み）

| # | 論点 | 決定 |
|:---|:---|:---|
| Q1 | orchestral（8ch）を既定の `.mod` で出す場合 | 要求どおり既定 mod。`8CHN` MOD で出す |
| Q2 | MP3 の生成方式 | 外部 ffmpeg（libopenmpt＋libmp3lame）に委譲。**実行環境に ffmpeg が必要なことを README の「動作要件」に明記**する（ユーザー指示） |
| Q3 | `--tempo` の単位 | **全ジャンルが適切な BPM で鳴るよう修正する**（ユーザー指示）。4分音符の BPM に統一し、2倍速で鳴っていた swing-jazz を修正（§1.3・§3.1） |
| Q4 | ジャンルの許容範囲を外れたテンポ要求 | 重なる部分に切り詰め＋WARNING、重ならなければエラー（終了コード 2） |
| Q5 | 4ch ジャンルを XM/S3M/IT/MIDI で出すときのステレオ幅 | LRRL を 64/192 に緩める |
| Q6 | MIDI の拡張子 | `.mid` |

---

## 10. 実装で判明した設計の修正・知見

1. **XM は Amiga 周波数表で書く**（§4.2 に追加）。linear 表のままでも音高は合うが、MOD と同じ period 単位で
   3xx/1xx/2xx を効かせるため（`automation.portamento_param` は period 基準で param を計算している）。
   ヘッダの初期 BPM も曲の BPM にした。
2. **trap の 808 グライド**: 先行音（ワンショット）が鳴り終わった後の `3xx` は、ProTracker では固有の
   「sample swap」挙動で鳴り直すが、XM/S3M/IT では無音になる（libopenmpt の MOD/XM 比較で発覚）。形式に依存
   しない書き方として、trap が 808 の再生位置を追跡し、鳴り終わっていれば新しい打鍵として書くよう変更した
   （MOD での聴感はほぼ同じ。グライドは1 row で完了するため）。再生位置の計算には実際の再生レート
   （Paula クロック／period）を使う（`dsp.sample_rate()` は合成時の基準レートで、実レートの半分）。
3. **S3M の上限は 16 チャンネル**（PCM チャンネルは L1–L8／R1–R8）。IT の Old Effects=1 は、合成テスト曲で
   ビブラート深さを実測して MOD と一致することを確認した（0 だと半分の深さになる）。
4. **MIDI の音高は「論理 note」ではなく実音から求める**。合成（`core/synth.py`）は `dsp.sample_rate()`
   （実際の Paula 再生レートの半分）を基準に波形を作るため、ワンショット音色は論理 note の `pitch.hz(n)` より
   1オクターブ上で、ループ音色は「ループ長に何周期入れたか」次第の高さで鳴る（例: orchestral の弦は
   論理 C3 だが実音 C5）。トラッカー形式間では全形式が同じ規約で鳴るので問題にならないが、MIDI は音高を
   絶対値で書くため、`synth.render()` が `SampleSpec.sounding_hz`（rate_note で鳴らしたときの実音）を記録し、
   MIDI はそこから音高を求める。YIN による実測との差は 20 セント以内（非調和音とパワーコードを除く）。
   **既存のトラッカー出力の音には一切影響しない**（記録を足しただけ）。
5. テンポの総当たり（全ジャンル × BPM 32–255 の全値 × 3 seed）で、構造エラーになるジャンルは無かった。
   `tempo_range` を狭めたのはカーブの形を保つための free-jazz（44–163）のみ。
6. 同じ seed でテンポだけ変えたとき、suspense-* は効果音（swoosh/anvil）の配置 row が BPM から逆算される
   設計なので配置も変わる（乱数の消費は変わらない）。それ以外のジャンルはテンポ以外のセルが完全に一致する。
