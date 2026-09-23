# ModWeaver

[![Python](https://img.shields.io/badge/Python-3.7%2B-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Format](https://img.shields.io/badge/Format-ProTracker%20MOD%20(4ch)-green.svg)](https://openmpt.org/)

**ModWeaver** は、外部ライブラリ（サードパーティ製パッケージ）を一切使用せず、**Python標準ライブラリのみ** でProTracker形式トラッカー音楽ファイル（`.mod`）を波形合成からシーケンスまで完全自動生成するツールです。ノスタルジック（`nostalgic`）だけでなく、サスペンス（`suspense-slow` / `suspense-chase`）、行進曲（`march`）、スウィング・ジャズ（`swing-jazz`）、変拍子プログレ（`prog-rock`）、トラップ（`trap`）、フューチャーベース（`future-bass`）など複数ジャンルを `--genre` で切り替えて生成できます（旧名: TwilightPad MOD Generator。指定できるジャンルの最新一覧は `--list-genres` 参照）。

既定の `nostalgic` ジャンルでは、夕暮れの街並みや家路を想起させる情緒的なコード進行と、オルゴールや包み込むようなアナログパッド、Lo-Fiビートが織りなす「懐かしさと切なさ」を持った楽曲を出力します。

---

## 主な特徴（何ができるか）

- **実行するたびに無限に異なる名曲を生成（手続き型作曲エンジン）**:
  ただ無作為に乱数を振るのではなく、「ノスタルジックな音楽理論の制約」のもとでコード進行・動機（Motif）・旋律・リズムを自動生成。毎回情緒豊かで口ずさみたくなる異なる楽曲が生まれます。
- **シード値による完全な再現性（Reproducibility）**:
  気に入った曲が生まれたら、コンソールに表示されるシード番号を使って `--seed <番号>` を指定すれば、いつでも寸分違わず同じ曲を再出力できます。
- **完全スタンドアロン合成**:
  外部音声ファイル（WAVやMP3）を読み込むのではなく、スクリプト内でデジタル信号処理（DSP）を用いてサイン波・倍音・フィルタ処理ノイズから8ビットPCMサンプルを直接生成します。
- **ノスタルジック・サウンドデザイン**:
  - **Music Box / Chime**: 澄んだ金属棒の共鳴（非整数倍音）と美しい指数減衰を再現したオルゴール音色。
  - **Twilight Ambient Pad**: 整数周期設計によりクリックノイズが一切生じない、温かいアナログシンセ・ストリングス（完全シームレスループ）。
  - **Warm Mellow Bass**: 丸く深みのあるアコースティック／Lo-Fiサブベース。
  - **Vintage Lo-Fi Drums**: ピッチ降下キック、温かいレトロスネア、繊細なクローズドハイハット。
- **標準ProTracker 4ch MOD準拠**:
  生成されたバイナリは Amiga ProTracker（`M.K.` マジックタグ）完全準拠であり、現代のあらゆるトラッカーソフトやメディアプレイヤーでネイティブ再生できます。

---

## 動作要件

- **Python 3.7 以上**（追加の `pip install` は不要です）

---

## 使い方

### 1. 実行方法

#### 新しい曲をランダム生成する（実行するたびに変化。`--genre` 省略時は既定の `nostalgic`）:
```bash
python modweaver.py
```
実行例：
```text
==================================================
  TwilightPad Procedural MOD Generator
==================================================
Genre       : nostalgic
Seed        : 732501
Tempo       : BPM 90
Theme A     : Step-Down (Nostalgic Descent) -> Fmaj7 - Em7 - Dm7 - Cmaj7
Theme B     : Journey (Memories & Depart) -> Am7 - Fmaj7 - Cmaj7 - G7
--------------------------------------------------
Output File : nostalgic/nostalgic_732501.mod
Success! To reproduce this exact song, run:
  python modweaver.py --genre nostalgic --seed 732501
==================================================
```

出力先を省略すると、`<ジャンル名>/<ジャンル名>_<シード>.mod`（例: `nostalgic/nostalgic_732501.mod`）にジャンルごとのサブフォルダへ自動整理されます（フォルダが無ければ作成）。

#### お気に入りの曲をシード指定で再生成する:
```bash
python modweaver.py --seed 732501
```

#### 出力ファイル名を指定する（`--output` を指定すると自動整理は行わず、指定パスへそのまま出力）:
```bash
python modweaver.py --output MyTwilightSong.mod
```

#### 他のジャンルを生成する（`--genre` / `-g`）:
```bash
python modweaver.py --genre suspense-chase
python modweaver.py --genre suspense-slow --seed 1
python modweaver.py --genre march
python modweaver.py --genre swing-jazz
python modweaver.py --genre prog-rock
python modweaver.py --genre trap
python modweaver.py --genre future-bass
```

#### 指定できるジャンル一覧を確認する:
```bash
python modweaver.py --list-genres
```

### 2. コマンドラインオプション

`python modweaver.py` / `python -m mod_weaver` のどちらも同じオプションを受け付けます。

| オプション | 短縮形 | 既定値 | 説明 |
|:---|:---|:---|:---|
| `--genre` | `-g` | `nostalgic` | 生成するジャンル id（下表参照）。未登録の id を指定するとエラー終了（コード 2） |
| `--seed` | `-s` | 乱数（100000〜999999） | 再現性のためのシード値（任意の整数、負値も可）。同じ genre + seed は常に同一バイナリを出力する |
| `--output` | `-o` | `<ジャンル名>/<ジャンル名>_<シード>.mod`（例: `nostalgic/nostalgic_732501.mod`）。フォルダが無ければ自動作成 | 出力先パス。明示した場合はそのパスへそのまま出力し、自動整理は行わない（存在しない親フォルダがあればエラー終了） |
| `--list-genres` | – | – | 指定できる全ジャンルの id・別名・説明を一覧表示して終了（コード 0）。生成は行わない |
| `--help` | `-h` | – | 使い方とオプション一覧（ジャンル一覧を含む）を表示して終了（コード 0） |

#### 指定できるジャンル

| ジャンル id | 別名 | 説明 |
|:---|:---|:---|
| `nostalgic` | – | 夕暮れの郷愁を誘う Lo-Fi ビートとオルゴール（従来の TwilightPad） |
| `suspense-slow` | `suspense` | 低速・重苦しい緊張。心拍と無音、突発の金属音 |
| `suspense-chase` | – | 緊急脱出・追走。毎拍の心拍と8分連打、無音からの衝撃 |
| `march` | – | 行進曲。Oom-Pah とスネアロール、ファンファーレ、トリオへの転調 |
| `swing-jazz` | – | スウィング・ジャズ。ライド＋ウォーキングベース＋ピアノコンピング、Bbリズムチェンジ AABA |
| `prog-rock` | – | 変拍子プログレ／マスロック。7/8+7/8+5/8 のリフ、4/4 のコーラスとの対比 |
| `trap` | – | トラップ／ドリル。32分ハイハットロールと808グライド、Cm-Ab の2和音ループ |
| `future-bass` | – | フューチャーベース。キック連動サイドチェイン、ヴォーカルチョップ、Eb I-V-vi-IV |

最新の一覧は `python modweaver.py --list-genres` または `python modweaver.py --help` でも確認できます（今後ジャンルが追加された場合も、このコマンドの出力が常に正となります）。

#### 終了コード

| コード | 意味 |
|:---|:---|
| `0` | 成功（`--help` / `--list-genres` を含む） |
| `2` | 引数エラー、または未登録のジャンル指定 |
| `3` | 生成・構造検査エラー |
| `4` | 出力エラー（書き込み不可など） |
| `1` | 想定外の例外（スタックトレースを表示） |

### 3. 再生・試聴方法

生成された `.mod` ファイルは、以下のトラッカーやプレイヤーですぐに再生可能です：

- **推奨トラッカー（編集・詳細確認用）**:
  - [OpenMPT (Open ModPlug Tracker)](https://openmpt.org/) (Windows)
  - [MilkyTracker](https://milkytracker.org/) (Windows / macOS / Linux)
  - [Schism Tracker](http://schismtracker.org/) (クロスプラットフォーム)
- **メディアプレイヤー**:
  - [XMPlay](https://www.un4seen.com/xmplay.html) (Windows / 高音質トラッカー再生)
  - [VLC media player](https://www.videolan.org/vlc/)
  - [Audacious](https://audacious-media-player.org/)

> **Tip (OpenMPTでの再生)**:
> OpenMPTで開くと、Pattern 0〜3 のノートデータ、使用サンプル（ヘッダーとループポイント）、BPM 92の設定、および4チャンネルの演奏状況をリアルタイムに確認・編集できます。

---

## トラック・パート構成 (4 Channels)

チャンネル役割・使用音色はジャンルごとに異なる `ChannelPlan` として `profiles/*.py` に定義されています。
以下は既定ジャンル `nostalgic` の構成例です（Amigaのステレオ定位特性 1:左, 2:右, 3:右, 4:左 に合わせた
バランスの良い音像設計）。他ジャンルの構成は各 `profiles/*.py` の `CHANNEL_PLAN`、または
[GENRE_DESIGN_V2.md](GENRE_DESIGN_V2.md) の各ジャンル節（ChannelPlan／音色キット）を参照してください。

| チャンネル | 定位 | パート | 使用音色 | 役割 |
|:---|:---|:---|:---|:---|
| **Channel 1** | Left | Drums | LoFiKick, SoftSnare, ClosedHH | 落ち着いたチルホップ／Lo-Fiビート |
| **Channel 2** | Right | Bass | WarmBass | コードの根音を支え、歌うベースライン |
| **Channel 3** | Right | Pad | TwilightPad | 夕暮れの色を背景に満たす持続アナログ和音 |
| **Channel 4** | Left | Melody | MusicBox | 胸に染み入る切ない主旋律（オルゴール） |

---

## ファイル構成

```text
.
├── modweaver.py       # トップレベル起動スクリプト（`--genre` 対応。省略時は nostalgic）
├── mod_weaver/        # パッケージ本体。`python -m mod_weaver` でも起動可
│   ├── core/          # 不変層: データモデル・DSP・音源合成（Patch方式）・和声・グルーヴ(EXT-1)・
│   │                   #        可変小節(EXT-2)・writer/verify
│   └── profiles/      # 可変層: ジャンルごとの GenreProfile
│                       #        （nostalgic / suspense-* / march / swing-jazz / prog-rock /
│                       #        trap / future-bass）
├── nostalgic/         # 生成されたMOD音楽ファイル（既定出力先。例: nostalgic_732501.mod）
├── DESIGN.md               # nostalgic ジャンルの改修観点・音響工学・音楽理論の詳細設計書（原初版）
├── EXTENSION_SPEC.md       # 多ジャンル拡張の最初期構想（検討書。EXTENSION_DESIGN.md が置き換え済み）
├── EXTENSION_DESIGN.md     # マルチジャンル対応エンジン第一段階の設計書（Phase 1〜3・4ジャンル分・実装済み）
├── CORE_EXTENSION_DESIGN.md # 第二段階 core 拡張（EXT-1〜6）の設計書。Phase 4a（EXT-1/EXT-2）実装済み、
│                             # Phase 4b以降は設計のみ
├── GENRE_DESIGN_V2.md      # 第二段階8ジャンルの詳細設計。swing-jazz/prog-rock/trap/future-bassは実装済み、他4ジャンルは設計のみ
└── README.md          # 本ドキュメント
```

より詳細な音響工学的分析や初期課題（Copilot生成コードの問題点）に対する改修観点については、[DESIGN.md](DESIGN.md) をご参照ください。第一段階（nostalgic/suspense/march）の実装詳細設計は [EXTENSION_DESIGN.md](EXTENSION_DESIGN.md)、サンプル音源合成の仕組み（`core/synth.py`）は [CORE_EXTENSION_DESIGN.md](CORE_EXTENSION_DESIGN.md) §8、第二段階の core 拡張（EXT-1〜6）は [CORE_EXTENSION_DESIGN.md](CORE_EXTENSION_DESIGN.md)、各ジャンル（swing-jazz/prog-rock 等）の詳細設計は [GENRE_DESIGN_V2.md](GENRE_DESIGN_V2.md) をご参照ください。

---

## ライセンス

本プロジェクトは [Apache License 2.0](http://www.apache.org/licenses/LICENSE-2.0) のもとで公開されています。

```
Copyright 2026

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
```
