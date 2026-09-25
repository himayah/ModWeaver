# ModWeaver

**日本語** | [English](README.en.md)

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Format](https://img.shields.io/badge/Format-MOD%20%7C%20XM%20%7C%20S3M%20%7C%20IT%20%7C%20MIDI%20%7C%20MP3-green.svg)](https://openmpt.org/)

**ModWeaver** は、外部ライブラリ（サードパーティ製パッケージ）を一切使用せず、**Python標準ライブラリのみ** でトラッカー音楽ファイルを波形合成からシーケンスまで完全自動生成するツールです。出力形式は ProTracker `.mod`（既定）、FastTracker II `.xm`、Scream Tracker 3 `.s3m`、Impulse Tracker `.it`、General MIDI `.mid`、`.mp3` から `--format` で選べます（`.mp3` のみ外部プログラム ffmpeg が必要）。ノスタルジック（`nostalgic`）だけでなく、**気分**（落ち着き `calm`、物悲しい `melancholic`、集中 `focus`、高揚 `uplifting` など9種）、**ジャンル**（`rock`・`pop`・`jazz`・`bossa-nova`・`city-pop`・`house`・`classical`・`cinematic`・`gamelan`・`industrial`・`trap`・`orchestral` など27種）、**〜風**（80年代 J-POP 風 `jpop-80s`、JRPG 風 `jrpg`、映画予告編風 `trailer`、8bit ゲーム音楽風 `chiptune`、90年代のレースゲーム風 `racing-breaks`、サスペンス `suspense-slow` など15種）の計51ジャンルを `--genre` で切り替えて生成できます（`--genre random` でランダムに選ぶことも可能。旧名: TwilightPad MOD Generator。指定できるジャンルの最新一覧は `--list-genres` 参照）。チャンネル数はジャンルに合わせて 4・6・8 から選ばれ、多くのジャンルは曲ごとに編成（小編成 4ch〜厚い 8ch）も変わります（`--channels` で指定も可能）。

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
- **6つの出力形式（`--format`）**:
  既定は Amiga ProTracker 4ch MOD（`M.K.`）。6ch・8ch の曲（例: `pop` の標準の 6ch、`orchestral` の 8ch）は FastTracker 系の多チャンネル MOD（`6CHN`・`8CHN`）になります。ほかに `.xm`／`.s3m`／`.it`（トラッカー形式）、General MIDI の `.mid`（DAW や GM 音源で鳴らせる）、`.mp3`（ffmpeg で音声化）を選べます。トラッカー形式はすべて OpenMPT の再生エンジン（libopenmpt）で実際に再生し、MOD と同じ音高・長さで鳴ることを自動テストで確認しています。
- **テンポ指定（`--tempo`）**:
  `--tempo 120` のように BPM を固定するか、`--tempo 80-100` のように範囲を指定してその中からランダムに決められます。同じシードならテンポだけが違う「同じ曲」になります。

---

## 動作要件

- **Python 3.10 以上**（追加の `pip install` は不要です）
- **`--format mp3` を使う場合のみ: ffmpeg**（**libopenmpt** と **libmp3lame** を有効にしてビルドされたもの）
  - MP3 は、曲をいったん `.xm` にして ffmpeg 内蔵の libopenmpt（OpenMPT の再生エンジン）で再生し、MP3 に符号化して作ります。ModWeaver 自身は音声の再生エンジンを持ちません。
  - `ffmpeg` を PATH に通すか、環境変数 `MODWEAVER_FFMPEG` に実行ファイルのパスを指定してください。
  - Windows では [gyan.dev](https://www.gyan.dev/ffmpeg/builds/) の **full** ビルド等が libopenmpt を含みます（essentials ビルドには含まれない場合があります）。対応を確認するには `ffmpeg -hide_banner -demuxers` の出力に `libopenmpt` が、`ffmpeg -hide_banner -encoders` の出力に `libmp3lame` があることを確かめてください。
  - ffmpeg が見つからない／必要な機能が無い場合は、何が足りないかを表示して終了コード `5` で終了します（ファイルは作られません）。
  - `.mp3` 以外の形式には ffmpeg は不要です。

---

## 使い方

### 1. 実行方法

引数を何も付けずに `python modweaver.py` と実行すると、使い方（`--help` と同じ内容）を表示して終了します。曲を作るときは下のようにオプションを指定してください。使い方・ジャンル一覧・実行結果の表示は日本語です（`-e` を付けると英語になります）。

#### 新しい曲をランダム生成する（実行するたびに変化）:
```bash
python modweaver.py --genre nostalgic
```
実行例：
```text
==================================================
  ModWeaver: TwilightPad Procedural
==================================================
ジャンル    : nostalgic
出力形式    : mod
シード      : 732501
テンポ      : BPM 90
Theme A     : Step-Down (Nostalgic Descent) -> Fmaj7 - Em7 - Dm7 - Cmaj7
Theme B     : Journey (Memories & Depart) -> Am7 - Fmaj7 - Cmaj7 - G7
--------------------------------------------------
出力ファイル: output/nostalgic_732501.mod
生成に成功しました。同じ曲を再現するには次を実行してください:
  python modweaver.py --genre nostalgic --seed 732501
==================================================
```

出力先を省略すると、カレントディレクトリの `output` フォルダに `<ジャンル名>_<シード>.mod`（例: `output/nostalgic_732501.mod`）として出力されます（フォルダが無ければ作成）。

#### お気に入りの曲をシード指定で再生成する（`--genre` を省略すると既定の `nostalgic`）:
```bash
python modweaver.py --seed 732501
```

#### 出力ファイル名を指定する（`--output` を指定すると `output` フォルダは使わず、指定パスへそのまま出力）:
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
python modweaver.py --genre maqam
python modweaver.py --genre free-jazz
python modweaver.py --genre minimalism
python modweaver.py --genre orchestral   # 8ch。既定の mod では 8CHN 形式
python modweaver.py --genre calm         # 気分: 落ち着き（4ch）
python modweaver.py --genre city-pop     # ジャンル: シティポップ（6ch）
python modweaver.py --genre classical    # ジャンル: 弦楽四重奏のメヌエット（3/4）
python modweaver.py --genre jrpg         # 〜風: JRPG のフィールド曲
python modweaver.py --genre gamelan      # ジャンル: ガムラン（スレンドロ／ペロッグ音律）
python modweaver.py --genre chiptune     # 〜風: 8bit ゲーム音楽（パルス波・三角波・ノイズ）
python modweaver.py --genre industrial   # ジャンル: インダストリアル（歪みと金属音）
python modweaver.py --genre racing-breaks  # 〜風: 90年代のレースゲーム（ドラムンベース／ブレイクビーツ）
```

#### ジャンルをランダムに選ぶ（`--genre random` / `-g r`）:
```bash
python modweaver.py --genre random
python modweaver.py -g r --tempo 120     # テンポ 120 に対応できるジャンルの中から選ぶ
```
選ばれたジャンルはバナーに `ジャンル    : trap (ランダム)` のように表示され、再現コマンドには選ばれたジャンル名（例: `--genre trap`）が出ます。ジャンルの選択は `--seed` とは無関係に毎回ランダムです（同じ曲をもう一度作るときは再現コマンドを使ってください）。

#### 出力形式を選ぶ（`--format` / `-f`。省略時は `mod`）:
```bash
python modweaver.py --format xm          # FastTracker II
python modweaver.py --format s3m         # Scream Tracker 3
python modweaver.py --format it          # Impulse Tracker
python modweaver.py --format midi        # General MIDI（拡張子は .mid）
python modweaver.py --format mp3         # MP3（ffmpeg が必要。動作要件を参照）
```
出力先を省略した場合の拡張子は形式に合わせて変わります（例: `output/nostalgic_732501.it`）。

#### テンポを指定する（`--tempo` / `-t`。省略時はジャンルごとに自動）:
```bash
python modweaver.py --tempo 120          # BPM 120 で生成
python modweaver.py --tempo 80-100       # 80〜100 の範囲からランダムに決める
```
範囲指定のとき、実際に選ばれた BPM はバナーの `テンポ` 行に表示され、再現コマンドには確定した値（例: `--tempo 92`）が出ます。

#### チャンネル数を指定する（`--channels` / `-c`。省略時はジャンルが曲ごとに選ぶ）:
```bash
python modweaver.py --genre pop --channels 4      # Amiga 互換の 4ch（M.K.）の小編成
python modweaver.py --genre pop --channels 8      # 対旋律やエコーを足した 8ch の編成
```
ch 列に複数の数があるジャンル（例: `4/6/8`）は、同じシードならどの編成でも同じ旋律・和音で、厚みとチャンネル数だけが変わります。

#### 指定できるジャンル一覧を確認する:
```bash
python modweaver.py --list-genres
```

#### 英語で表示する（`-e` / `--english`）:
```bash
python modweaver.py -e                   # 英語の使い方
python modweaver.py -e --list-genres     # ジャンルの説明を英語で
python modweaver.py -e --genre trap      # 実行結果のバナーを英語で
```
使い方・ジャンル一覧の説明・実行結果のバナーが英語になります。生成される曲は `-e` の有無で変わりません。バナーのうちジャンルが出す要約行（コード進行名など）と、エラー・警告のメッセージ（標準エラー出力）は、どちらの場合も英語です。

#### バージョンを確認する:
```bash
python modweaver.py --version
```
```text
ModWeaver 1.1.0
https://github.com/himayah/ModWeaver
```

### 2. コマンドラインオプション

`python modweaver.py` / `python -m mod_weaver` のどちらも同じオプションを受け付けます。オプションを何も付けずに起動すると、`--help` と同じ使い方を表示して終了します（コード 0）。

| オプション | 短縮形 | 既定値 | 説明 |
|:---|:---|:---|:---|
| `--genre` | `-g` | `nostalgic` | 生成するジャンル id（下表参照）。`random` / `r` なら指定できるジャンルからランダムに選ぶ（`--tempo` があればそのテンポに対応できるジャンルから）。未登録の id を指定するとエラー終了（コード 2） |
| `--seed` | `-s` | 乱数（100000〜999999） | 再現性のためのシード値（任意の整数、負値も可）。同じ genre + seed（+ format + tempo）は常に同一バイナリを出力する |
| `--format` | `-f` | `mod` | 出力形式: `mod` / `xm` / `s3m` / `it` / `midi` / `mp3`（下表参照） |
| `--tempo` | `-t` | ジャンルごとに自動 | BPM（`120`）または範囲（`80-100`、範囲内からランダム）。32〜255。ジャンルが対応できない範囲だとエラー終了（コード 2）、一部だけ外れていれば対応範囲に切り詰めて警告 |
| `--output` | `-o` | `output/<ジャンル名>_<シード>.<拡張子>`（例: `output/nostalgic_732501.mod`）。フォルダが無ければ自動作成 | 出力先パス。明示した場合はそのパスへそのまま出力する（存在しない親フォルダがあればエラー終了） |
| `--channels` | `-c` | ジャンルが曲ごとに自動 | チャンネル数 `4` / `6` / `8`。選べる数はジャンルによる（ジャンル一覧の ch 列）。選べない数を指定するとエラー終了（コード 2）。`--genre random` と組み合わせると、その数を選べるジャンルから選ぶ |
| `--list-genres` | – | – | 指定できる全ジャンルの id・別名・説明を区分（気分・ジャンル・〜風）ごとに一覧表示して終了（コード 0）。生成は行わない |
| `--english` | `-e` | – | 使い方・ジャンル一覧の説明・実行結果の表示を英語にする（既定は日本語） |
| `--version` | `-v` | – | バージョンと GitHub リポジトリの URL を表示して終了（コード 0） |
| `--help` | `-h` | – | 使い方とオプション一覧（末尾に区分ごとのジャンル id）を表示して終了（コード 0） |

#### 出力形式

| `--format` | 拡張子 | チャンネル数 | 備考 |
|:---|:---|:---|:---|
| `mod`（既定） | `.mod` | 4（`M.K.`）／それ以外は `xCHN` | 4ch 以外（6ch・8ch のジャンル）は FastTracker 系の多チャンネル MOD。OpenMPT・MilkyTracker・libxmp 等で再生できるが、本家 ProTracker／Amiga 実機では再生不可。ジャンルごとの定位は失われ、プレイヤー既定の L R R L 定位になる |
| `xm` | `.xm` | 1〜32 | 4ch ジャンルは Amiga 風の L R R L（左右幅は控えめ）、6ch・8ch のジャンルはジャンルが決めた楽器ごとの定位 |
| `s3m` | `.s3m` | 1〜16 | 同上（チャンネル定位で表現） |
| `it` | `.it` | 1〜64 | 同上 |
| `midi` | `.mid` | 制限なし | General MIDI（SMF format 1）。音色は各ジャンルが楽器ごとに指定した GM 音色で、サンプル音色そのものではない。グライド（ポルタメント）は目標音への即時切替、ビブラートはモジュレーション（CC1）で近似 |
| `mp3` | `.mp3` | 1〜32 | 44.1kHz ステレオ 192kbps。**ffmpeg が必要**（動作要件を参照） |

#### テンポ（BPM）の意味

`--tempo` とバナーの `テンポ` は **4分音符の BPM** です（トラッカーの `Fxx` の値と同じ）。例外として `trap` は 32分音符の細かい格子で書かれたハーフタイムのジャンルなので、表示 BPM は trap の慣習どおりの数え方（例: 150 → ハーフタイムで 75 に感じる）です。`free-jazz` はテンポが連続的に揺れ動くジャンルで、`--tempo` は開始時の BPM を決めます（以降のテンポ変化は同じ比率で拡大縮小。指定できるのは 44〜163）。

#### 指定できるジャンル

**気分（mood）** — 9 種類

| ジャンル id | 別名 | ch | 説明 |
|:---|:---|:---|:---|
| `calm` | – | 4 | 落ち着き。低いテンポで柔らかいパッドとピアノの分散和音 |
| `cool` | – | 4/6/8 | 涼しげ。透明感のあるシンセと軽い2ステップのビート |
| `dark-tense` | – | 4/6/8 | 緊張感。低音のオスティナートと刻むパルス、重い打撃 |
| `dreamy` | – | 4/6/8 | 夢見心地。深い残響感のアルペジオとパッド |
| `energetic` | – | 4/6/8 | 元気・活動的。速いテンポと強いドラム、8分で刻むギターとベース |
| `focus` | – | 4 | 集中。ほとんど変化しないローファイのループと一定のテンポ |
| `melancholic` | – | 4 | 物悲しい。短調のピアノが旋律を歌い、弦のパッドが支える |
| `uplifting` | – | 4/6/8 | 上げていく高揚感。4つ打ちとアルペジオ、明るいスーパーソウのコード |
| `warm` | – | 4/6 | 温かい。アコースティックギターとピアノ、長調の穏やかな伴奏 |

**ジャンル（genre）** — 27 種類

| ジャンル id | 別名 | ch | 説明 |
|:---|:---|:---|:---|
| `ambient` | – | 4 | アンビエント。拍の弱い、重なり合うパッドとまばらなベル |
| `bossa-nova` | – | 4/6 | ボサノバ。2/4 の柔らかいガットギターと軽いパーカッション |
| `cinematic` | – | 6/8 | 映画音楽。ピアノのオスティナートから弦とホルンが重なり、ドラマチックに高まる |
| `city-pop` | – | 4/6/8 | シティポップ。テンションコードのエレピ、跳ねるベースとギターのカッティング |
| `classical` | – | 4 | クラシック。古典派のメヌエット風の弦楽四重奏、明確な和声と終止 |
| `edm` | – | 4/6/8 | EDM。シンセ主体、ビルドアップで溜めてドロップで弾ける |
| `folk` | – | 4/6 | フォーク。アコースティックギターのストロークとフィドル、素朴な進行 |
| `free-jazz` | – | 4 | フリージャズ。トーンクラスター、確率密度のテクスチャ、ルバート（連続テンポ変化） |
| `future-bass` | – | 4 | フューチャーベース。キック連動サイドチェイン、ヴォーカルチョップ、Eb I-V-vi-IV |
| `gamelan` | – | 6 | ガムラン風。青銅の鍵盤と壺型ゴングの重なり、周期的なゴングの区切りとスレンドロ／ペロッグ音律 |
| `hiphop` | – | 4/6 | ヒップホップ。ラップが乗る余白を残したブーンバップのビートとサンプル風ループ |
| `house` | – | 4/6/8 | ハウス。4つ打ちの安定したグルーヴと裏拍のオルガン・スタブ |
| `industrial` | – | 6 | インダストリアル。歪んだビートと金属の打撃、うなる歪んだベースと工場の騒音 |
| `jazz` | – | 4 | ジャズ。ドリアンのモーダルなヴァンプ、4度堆積のピアノとミュート・トランペット |
| `lofi-hiphop` | – | 4/6/8 | ローファイ・ヒップホップ。よれたビート、ジャジーなエレピ、レコードのノイズ |
| `maqam` | – | 4 | 中東マカーム（Rast on G）。ウードのタクシームとマクスーム usul、中立音程 |
| `march` | – | 4 | 行進曲。Oom-Pah とスネアロール、ファンファーレ、トリオへの転調 |
| `minimalism` | – | 4 | ミニマル／フェーズ音楽。16/12/8/6row周期の4パートが少しずつズレて→揃って戻る |
| `orchestral` | – | 8 | フルオーケストラ／劇伴。8chマルチチャンネル、6声の弦+木管+金管+ティンパニ |
| `pop` | – | 4/6/8 | ポップ。長調の明るいメロディとピアノ、覚えやすいサビ |
| `prog-rock` | – | 4 | 変拍子プログレ／マスロック。7/8+7/8+5/8 のリフ、4/4 のコーラスとの対比 |
| `rnb-soul` | – | 4/6/8 | R&B／ソウル。滑らかなテンションコードと歌うような旋律のスロー・ジャム |
| `rock` | – | 4/6/8 | ロック。ギターのリフと8ビート、4/4 の中〜速いテンポ |
| `swing-jazz` | – | 4 | スウィング・ジャズ。ライド＋ウォーキングベース＋ピアノコンピング、Bbリズムチェンジ AABA |
| `synthwave` | – | 4/6/8 | シンセウェイブ。80年代のシンセとゲートスネア、8分で脈打つベース |
| `techno` | – | 4 | テクノ。繰り返しの中で少しずつ変わるシーケンスと4つ打ち |
| `trap` | – | 4 | トラップ／ドリル。32分ハイハットロールと808グライド、Cm-Ab の2和音ループ |

**〜風（style）** — 15 種類

| ジャンル id | 別名 | ch | 説明 |
|:---|:---|:---|:---|
| `acoustic-ssw` | – | 4/6 | 弾き語り風。指弾きのギターと軽いパーカッション、歌のような旋律 |
| `ambient-drone` | – | 4 | ドローン。長く伸びる持続音がゆっくり移ろう、変化の少ない響き |
| `anime-ost` | – | 4/6/8 | アニメ劇伴風。刻むストリングスとジャズの和声、ブラスの決め |
| `chiptune` | – | 4 | 8bit ゲーム音楽風。パルス波の旋律とアルペジオ、三角波のベース、ノイズの打楽器とジャンプ音 |
| `indie-rock` | – | 4/6/8 | インディー・ロック風。生音のドラムと鳴り響くギターのアルペジオ、軽い歪み |
| `jpop-80s` | – | 4/6/8 | 80年代 J-POP 風。明るいコードと都会的なブラス、軽快なビートと最後のサビの転調 |
| `jrock-90s` | – | 4/6/8 | 90年代 J-ROCK 風。歪んだギターが前に出る速いビートとギターソロ、最後のサビで転調 |
| `jrpg` | – | 4/6/8 | ゲーム音楽風（JRPG）。旋律を重視した冒険のテーマ、ハープと弦とホルン |
| `lofi-chill` | – | 4/6/8 | ローファイ・チル。柔らかいギターとフルート、うねるサイドチェインと雨音 |
| `neo-soul` | – | 4/6/8 | ネオソウル風。よれたビートとエレピ主体の豊かなテンションコード |
| `nostalgic` | – | 4 | 夕暮れの郷愁を誘う Lo-Fi ビートとオルゴール（従来の TwilightPad） |
| `racing-breaks` | – | 4/6/8 | 90年代後半のレースゲーム風。ドラムンベース／ブレイクビーツに 9th のエレピと太いサブベース |
| `suspense-chase` | – | 4 | 緊急脱出・追走。毎拍の心拍と 8 分連打、無音からの衝撃 |
| `suspense-slow` | `suspense` | 4 | 低速・重苦しい緊張。心拍と無音、突発の金属音 |
| `trailer` | – | 6/8 | 映画予告編風。大太鼓と金管の衝撃、刻む弦、合唱で盛り上がる3幕構成 |

最新の一覧は `python modweaver.py --list-genres` または `python modweaver.py --help` でも確認できます（今後ジャンルが追加された場合も、このコマンドの出力が常に正となります）。`-e` を付けると説明が英語で表示されます。

#### 終了コード

| コード | 意味 |
|:---|:---|
| `0` | 成功（引数なしでの起動、`--help` / `--list-genres` / `--version` を含む） |
| `2` | 引数エラー、未登録のジャンル指定、またはジャンルが対応できないテンポ指定（`--genre random` で対応できるジャンルが1つも無い場合を含む） |
| `3` | 生成・構造検査エラー |
| `4` | 出力エラー（書き込み不可など） |
| `5` | `--format mp3` で ffmpeg が見つからない、または libopenmpt / libmp3lame を含まない |
| `1` | 想定外の例外（スタックトレースを表示） |

### 3. 再生・試聴方法

生成された `.mod`／`.xm`／`.s3m`／`.it` ファイルは、以下のトラッカーやプレイヤーですぐに再生可能です（`.mid` は GM 音源・DAW・メディアプレイヤーで、`.mp3` は一般の音楽プレイヤーで再生できます）：

- **推奨トラッカー（編集・詳細確認用）**:
  - [OpenMPT (Open ModPlug Tracker)](https://openmpt.org/) (Windows)
  - [MilkyTracker](https://milkytracker.org/) (Windows / macOS / Linux)
  - [Schism Tracker](http://schismtracker.org/) (クロスプラットフォーム)
- **メディアプレイヤー**:
  - [XMPlay](https://www.un4seen.com/xmplay.html) (Windows / 高音質トラッカー再生)
  - [VLC media player](https://www.videolan.org/vlc/)
  - [Audacious](https://audacious-media-player.org/)

> **Tip (OpenMPTでの再生)**:
> OpenMPTで開くと、各パターンのノートデータ、使用サンプル（ヘッダーとループポイント）、テンポ（BPM）の設定、および各チャンネルの演奏状況をリアルタイムに確認・編集できます。

---

## トラック・パート構成

チャンネル数（4・6・8）・役割・使用音色はジャンルごとに `mod_weaver/genres/*.py` に定義されています（ジャンル一覧の ch 列）。
以下は既定ジャンル `nostalgic` の構成例です（Amigaのステレオ定位特性 1:左, 2:右, 3:右, 4:左 に合わせた
バランスの良い音像設計）。他ジャンルの構成は各 `genres/*.py`（第３段階の35ジャンルは `CHANNELS` の宣言）、または
[DESIGN.md](DESIGN.md) §6 の各ジャンルの節（第３段階のジャンルは §6.16）を参照してください。

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
├── modweaver.py       # トップレベル起動スクリプト（引数なしなら使い方を表示）
├── listen_samples.bat # 試聴用の曲をまとめて作るバッチ（Windows。DESIGN.md §11 の試聴項目ごとに3例、output\listen\ へ）
├── mod_weaver/        # パッケージ本体。`python -m mod_weaver` でも起動可
│   ├── core/          # 不変層: データモデル・DSP・音源合成（Patch方式）・和声・グルーヴ(EXT-1)・
│   │                   #        可変小節(EXT-2)・writer/verify・出力形式（formats / s3m / it / midi /
│   │                   #        timeline / render(mp3)）
│   ├── profiles/      # ジャンルの仕組み: GenreProfile 基底・登録簿（genres/ の自動検出）・ジャンル共通の補助
│   │                   #        （band_common: 第３段階の35ジャンルが共有する骨格 BandProfile）
│   └── genres/        # 可変層: ジャンルモジュール（1ファイル＝1ジャンル。置くだけで自動登録。51ジャンル）
├── output/            # 生成された音楽ファイル（既定出力先。例: nostalgic_732501.mod）
├── DESIGN.md          # 設計書（現在の仕様）
├── DESIGN_HISTORY.md  # 設計の経緯（決定の理由・訂正・見送ったもの）
├── README.md          # 本ドキュメント（日本語）
└── README.en.md       # 英語版 README
```

設計の詳細は [DESIGN.md](DESIGN.md)（現在の仕様）を、なぜそうなったか・過去の検討や訂正は [DESIGN_HISTORY.md](DESIGN_HISTORY.md) をご参照ください。

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
