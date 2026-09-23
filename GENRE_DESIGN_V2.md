# 第二段階8ジャンル 詳細設計（Genre Design v2.0）

| 項目 | 内容 |
|:---|:---|
| 対象 | `CORE_EXTENSION_DESIGN.md` §2 の8ジャンル（`swing-jazz`/`prog-rock`/`orchestral`/`trap`/`maqam`/`minimalism`/`future-bass`/`free-jazz`）の具体的なプロファイル設計 |
| 前提ドキュメント | [CORE_EXTENSION_DESIGN.md](CORE_EXTENSION_DESIGN.md)（EXT-1〜6 の core 仕様）、[EXTENSION_DESIGN.md](EXTENSION_DESIGN.md) §7〜8（Profile 契約・既存4ジャンルの設計。本書は同じ様式で書く） |
| ステータス | **§1 `swing-jazz`・§2 `prog-rock`・§4 `trap`・§5 `maqam`・§7 `future-bass`・§8 `free-jazz` は実装済み**（`mod_weaver/profiles/{swing_jazz,prog_rock,trap,maqam,future_bass,free_jazz}.py`。全て300 seed で検査クリーンを確認済み）。§3・§6（`orchestral`/`minimalism`）は詳細設計のみで未実装。各節は march.py と同じ粒度（音色の DSP 構成、`ChordSpec` 進行、`ChannelPlan`、曲構成、文法）で「実装すればそのまま動く」レベルまで具体化している。試聴による微調整が前提の値には §10 に一覧化した上で明示している。実装時に見つかった設計との差分は各章の脚注、および CORE_EXTENSION_DESIGN.md の各版の改訂履歴を参照。**§3〜§8 の再レビュー（2026-09-23、実装前）で見つけた設計不整合を修正済み**: `Finish=Loop` の禁止パターン（`attack_ms`/`post_filter`/`NoiseLayer` 混在、比率でのデチューン指定が非整数 K になる問題。§3 `ORCH_VIOLIN`/`ORCH_CELLO`、§5 `MAQAM_NAY`（実装時に隣接整数 K で確認済み）、§7 `FB_SUPERSAW`（同）、§8 `FREE_ARCO_BASS`（同））、orchestral の6声データ受け渡し方法（§3.3 で `begin_pattern`/`state` 方式に修正）、maqam の `MicroScale` 相対セント→絶対セント変換の欠落（`MicroScale.absolute_cents()` を core 側に追加）。**trap 実装時に判明した追加修正**: 進行を4和音から2和音ループへ簡略化（§4.3）、`PERIODS` の添字は tracker note（§4.5）。**future-bass 実装時に判明した追加修正**: kick/clap のチャンネル優先度共有問題（§7.6）。**maqam 実装時に判明した追加修正**: なし（§5 の設計はそのまま実装できた。EXT-3 設計時に見つけた `absolute_cents()` の欠落は core 側で先に解決済みだったため）。**free-jazz 実装時に判明した追加修正**: `ChordDef.chord_tones` を全楽器で共有すると shift の違いで無効な音域になる楽器が出るため、`chord.bass`（単一音、arco_bass 専用）と `chord.chord_tones`（共有音域、shift=0 の楽器専用）を役割分担させた（§8.2） |
| 読み方 | 各節は EXTENSION_DESIGN.md §8.5（march）と同一の構成: ①音色キット ②ChannelPlan ③進行 ④曲構成 ⑤文法 ⑥使用する core 拡張とその設定値。`core/synth.py` の `Patch`/`Layer` 語彙、`core/composer.py` の `MelodyGenerator`/`RhythmMotif`/`articulate` 語彙、`core/harmony.py` の `Registers`/`voice()` 語彙は既存4ジャンルと共通のまま使う（新規 core 追加は行わない。追加が要る箇所は個別に明記） |

---

## 0. 8ジャンル×必要拡張の整合確認

設計を通して、各ジャンルが実際に使う EXT は `CORE_EXTENSION_DESIGN.md` §2 の当初マッピング表と**過不足なく一致**することを確認した（詳細設計の結果、想定より多くの EXT が必要になったジャンルも、逆に不要と分かったジャンルもない）:

| ジャンル | 使用する EXT | 使わない理由の確認 |
|:---|:---|:---|
| swing-jazz | EXT-1（スウィングのみ） | 1フレーズ=8measure×8row=64row で割り切れるため EXT-2 不要 |
| prog-rock | EXT-2（可変小節） | スウィングさせないため EXT-1 不要 |
| orchestral | EXT-6（マルチチャンネル） | 拍子・音律は通常のまま。EXT-1〜5 いずれも不要 |
| trap | EXT-1（サブステップ）＋EXT-5（808グライド） | 32分は `rows_per_measure=32`（64の約数）で素通しできるため実は EXT-2 不要。EXT-1 の新規コードはリトリガ2関数のみ |
| maqam | EXT-3（マイクロチューニング） | usul（リズム周期）に maqsum（4/4）を採用し 64 row 内に収めるため EXT-2 不要。テンポは一定（EXT-5 不要） |
| minimalism | EXT-2（ポリメトリック） | 拍子は一定・微分音なし。EXT-1/3/4/5 不要 |
| future-bass | EXT-4（サイドチェイン＋スライス） | 拍子・音律は通常のまま。EXT-1/2/3/5 不要 |
| free-jazz | EXT-5（テンポカーブ） | 和声は `ChordDef` を直接手組みする（nostalgic の `explicit=True` 流儀）ため `core/pitch.py` の `CHORD_QUALITIES` に新規追加は不要。EXT-1〜4 不要 |

---

## 1. `swing-jazz`（スウィング・ジャズ / ビバップ）

### 1.1. 音色キット（`core/synth.py` の `Patch` 構成。命名は `synth_presets.py` へ `SWING_*` として追加）

| 名前 | 構成（Layer/Finish） | 備考 |
|:---|:---|:---|
| `SWING_RIDE` | `ToneLayer(非整合倍音4本: 3150/4450/5900/7600Hz、各 decay_alpha 5.0/7.0/9.5/13.0)` を `NoiseLayer(filter=hp, decay_alpha=7.5)` に重み0.35で混合。`Finish=OneShot(0.9s)`、`post_filter=hp`、`saturate=1.1` | march の `CRASH` プリセットの短縮・HP強化版。`rate_note=35`（`pitched=False`）。実装済み（`synth_presets.SWING_RIDE`）の値と一致 |
| `SWING_BRUSH_SNARE` | `NoiseLayer(filter=lp a=0.4, decay_alpha=22.0)` 単層。`Finish=OneShot(0.12s)`、`attack_ms=3`（ブラシの柔らかい入り）、`saturate=1.1` | march `SD` よりアタックを緩やかに、余韻を短く。実装済みの値と一致 |
| `SWING_WALK_BASS` | `ToneLayer(基音+2倍音: weight 0.8/0.2, decay_alpha 7.0/10.0)`。`Finish=OneShot(0.32s)`、`shift=-12`、`attack_ms=6`（撥弦の頭）、`saturate=1.15` | march `TUBA_BASS` に近い。当初案にあった `PitchSweepLayer` は実装時に単純化のため削除（`attack_ms` のみで撥弦の頭を表現）し、実装済み（`synth_presets.SWING_WALK_BASS`）と一致させてある |
| `SWING_PIANO_COMP` | `ToneLayer(h=1,2,3,4 相当を近接デチューン対7項: 1.0/1.006, 2.0/2.012, 3.0/3.02, 4.0、各 decay_alpha 9.0/9.0/13.0/13.0/18.0/18.0/24.0)`（デチューン約10セント、2層相当で軽いコーラス感）。`filter=lp a=0.45`、`Finish=OneShot(0.45s)`、`peak=0.9` | コンピング（刺すような短い和音）用。ループにしない（毎回減衰し切る）。実装済みの値と一致 |
| `SWING_SAX_LEAD` | `ToneLayer(奇数次倍音優勢, h=1,3,5,7 weight 1/h)`。`Finish=Loop(190, attack_samples=70)` | リード管楽器。`attack_samples` を持たせ「タンギング」の頭を作る。**実装時の修正**: 当初案の `NoiseLayer`（ブレスノイズ）は `Finish=Loop` が `ToneLayer` のみ許可（`core/synth.py` 制約）のため落とした。実装済み（`synth_presets.SWING_SAX_LEAD`）と一致させてある |

### 1.2. ChannelPlan / sample 番号

```
RIDE, BRUSH, BASS, PIANO, SAX = 1, 2, 3, 4, 5
CH_DRUM, CH_BASS, CH_HARM, CH_MEL = 0, 1, 2, 3
CHANNEL_PLAN = (
    ChannelRole("drums", {RIDE, BRUSH}, {BRUSH: 2, RIDE: 1}),
    ChannelRole("bass", {BASS}),
    ChannelRole("harmony", {PIANO}),
    ChannelRole("melody", {SAX}),
)
```

### 1.3. 進行（Bb、リズムチェンジ形式 AABA、32 measure = 4 pattern × 8 measure）

A（8 measure、`ChordSpec` 半音オフセット・Bb基準）: `Bb6(1) - G7(1) - Cm7(1) - F7(1) - Bb6(1) - G7(1) - Cm7/F7(半々=1) - Bb6(1)`。B（ブリッジ、ドミナントサイクル）: `D7(1) - D7(1) - G7(1) - G7(1) - C7(1) - C7(1) - F7(1) - F7(1)`。march と同じく `harmony.voice()`＋`REGISTERS`（`BASS_REG`/`HARM_REG`/`MELODY_REG`）で具体化する。

### 1.4. 曲構成

`PatternPlan`: `intro`（イントロ、リズム隊のみヴァンプ、intensity 0.4）／`head_a`／`head_b`／`solo_a`／`solo_b`／`out_a`（タグエンディング付き、intensity 1.0）。`order = [intro, a,a,b,a, solo_a,solo_a,solo_b,solo_a, a,a,b, out]`（Head-Solo-Head の3コーラス構成、13 pattern 枠）。テンポ: `tempo_choices=(152,156,160,164,168)`（ミディアムスウィング）。

### 1.5. 文法（1 measure = 8 row = 4/4、1 row = 8分音符）

- **ライド**: 古典的な "ding-ding-a-ding" パターン＝`row 0,2,3,4,6,7` に配置（`row 1,5` は休符）。row 0/4 が強拍アクセント（vol 58）、他は vol 44。
- **ブラシスネア**（バックビート）: `row 2, 6` に vol 40。`ChannelRole.priority` により同 row のライドより優先（衝突時はブラシが勝つ設計はしない＝ライドと同row同chではなくブラシは独立chなので実際には競合しない。優先度は「連打時の意図的上書き」のためのみ）。
- **ウォーキングベース**: 4分音符＝`row 0,2,4,6` の4打。`composer.MelodyGenerator`（`register=BASS_REG`, `ScaleRules(step_choices=(-1,1,-2,2), leap_probability=0.35, leap_semitones=(3,4,5,7))`）で、各 measure の頭は和音のルートかベース（`chord.bass`）から開始し、次の和音のルートへ向かう順次進行/跳躍で繋ぐ（典型的なウォーキングベースの手法をそのまま `MelodyGenerator.bar()` の `cadence_target` 機構で表現: 次 measure 頭の音を `cadence_target` として最終拍にセットする）。
- **ピアノ・コンピング**: 各 measure、`rng.harmony` で "Charleston"（row 0 と row 3）または "offbeat 2発"（row 1, 5 など奇数row2つ）のどちらかを選び、`chord.arp` 付きで刺す（vol 34、強拍なら 44）。
- **サックス**: `head_a`/`head_b` は事前定義の `RhythmMotif` プール（`(0,2,4,6)`＝4分主体、`(0,1,3,5,6)`＝シンコペ主体 等、march の `MARCH_MOTIFS` と同型で新規に4種）を `rng.melody` で選び `MelodyGenerator`（`register=MELODY_REG`, `leap_probability=0.30`）で生成。4小節に1回、末尾の swung 8th（奇数 row）に `groove.retrigger_param(3)` を使った短い E9x ターン（装飾）を確率0.25で付与。`solo_a`/`solo_b` は同じ生成器だが `leap_probability=0.45`・`dissonance_weight=0.12` に上げてアドリブらしいアウトサイド感を出す。

### 1.6. 使用する core 拡張

`groove.SwingConfig(long_speed=7, short_speed=5)`（比率1.4:1、粘っこすぎないミディアムスウィング。§11 で試聴調整対象）を `post_processors` から `groove.apply_swing(pattern, config)` を全 pattern に適用する形で使う。`tempo_policy="engine"` のまま（`apply_tempo` は row 0 の**別チャンネル**を使うため、intro pattern の row 0 は必ずドラム・ベース・ハーモニーいずれか2チャンネル以上を空けておく設計にする＝ `intro` の row 0 はベース・ハーモニーを休符にし、ドラムのライド1発のみ置く）。

---

## 2. `prog-rock`（変拍子プログレ / マスロック）

### 2.1. 音色キット

| 名前 | 構成 | 備考 |
|:---|:---|:---|
| `PROG_KICK` | `PitchSweepLayer(freq_start=140,freq_end=48,pitch_decay=28,decay_alpha=13)` + `NoiseLayer(decay_alpha=2600,weight=0.15)` クリック。`saturate=1.5`、`Finish=OneShot(0.22s)` | march `BD` より締まった現代ロックキック。実装済み（`synth_presets.PROG_KICK`）の値と一致 |
| `PROG_SNARE` | `ToneLayer(190Hz,decay_alpha=25,weight=0.5)` + `NoiseLayer(filter=hp,decay_alpha=16,weight=0.7)`。`saturate=1.6`、`Finish=OneShot(0.20s)` | 実装済みの値と一致 |
| `PROG_CRASH` | march `MARCH_CRASH_CYMBAL` を `dataclasses.replace(finish=OneShot(0.6))` で短縮して流用 | 新規合成不要、既存プリセットの差分適用。実装時の修正: 内部の各 partial の `decay_alpha` を個別に変える案は `ToneLayer.partials` タプルの再構築が必要で煩雑なため、`finish` の秒数短縮のみで「タイトな」印象を作る単純な方式にした（`build_prog_rock_samples()` 参照） |
| `PROG_BASS_DIST` | `ToneLayer(矩形波近似 dsp.partials_square(5)＝h=1,3,5 の3項 weight 1/h)` に `filter=lp a=0.3`。`Patch.decay_alpha=5.0` で一律減衰、`saturate=2.2`（歪み）。`Finish=OneShot(0.5s)`、`shift=-12` | ディストーションベース。`dsp.partials_square(n)` は「n 次高調波まで」の意味で奇数次のみ返すため実際の項数は3（当初案の「h=1,3,5,7,9」は誤り。実装済みと一致させてある） |
| `PROG_GTR_POWER` | `ToneLayer((1.0,1.0,7.0),(1.5,0.7,9.0),(2.0,0.5,9.0),(3.0,0.3,12.0))`（root/5th/oct/複合5th、各倍音が異なる速さで減衰）→ `saturate=2.6`。`Finish=OneShot(0.4s)` | パワーコード。和音そのものを1サンプルに焼き込む（アルペジオでなく単発和音的音色、`pitched=True` でルート音を鳴らすと5度・オクターブも同時に鳴る設計）。実装済みの値と一致 |
| `PROG_LEAD_GTR` | `ToneLayer(K=6*h, h=1..6, weight 1.0/0.55/0.7/0.3/0.4/0.18)` → `saturate=1.8`。`Finish=Loop(190, attack_samples=50)` | 実装済みの値と一致。**実装時の修正**: 当初案にあった「ビブラート用の `4xy` 効果を文法側で付与」は簡略化のため実装していない（`prog_rock.py` の `_chorus` は `articulate()` のみ使用）。ビブラートが欲しい場合は march の `_apply_vibrato` 相当のヘルパーを追加する（§10 の未確定事項に追記） |

### 2.2. ChannelPlan

```
KICK, SNARE, CRASH, BASS, GTR, LEAD = 1..6  (drums ch は KICK/SNARE/CRASH を優先度 CRASH>SNARE>KICK で共有)
CH_DRUM, CH_BASS, CH_GTR, CH_LEAD = 0,1,2,3
```
`CH_GTR` は `PROG_GTR_POWER` 固定（リフ担当）。リードは `CH_LEAD` に `PROG_LEAD_GTR` のみ（メロディ楽器が1つに絞られる点は既存ジャンルと同型の制約）。

### 2.3. 進行

E aeolian（Eマイナー）モーダル。主リフの和声度数は `i - bVII - bVI - bVII`（Em - D - C - D）を基本に、リフの「拍子そのもの」を主動機とする（プログレ/マスロックの慣習に合わせ、和声変化より拍子変化が音楽的主眼）。

### 2.4. 曲構成（可変拍子。`variable_meter=True`）

主リフ拍子サイクル: `7/8 + 7/8 + 5/8`（合計 19/8）を1フレーズとする。`rows_per_measure` 既定は 16（16分格子基準）とし、`ChordSlot.rows` で 7/8 measure=14 row、5/8 measure=10 row を指定する。1 pattern = リフサイクル2回分 = `(14+14+10)*2 = 76` row では 64 を超えるため、**1 pattern = リフサイクル1回（14+14+10=38 row）＋ D00 break**とする（`variable_meter=True` で自動挿入）。

`PatternPlan`: `intro`（リフのみ、ドラム抜き、38 row）／`verse`（フル編成、38 row）／`chorus`（8/8 4小節の直進パートに一時的に戻り開放感を出す。`rows=16, measures=4`＝64 row ちょうど、通常の等長小節に戻る設計＝可変拍子と直進拍子の対比が主眼）／`breakdown`（5/8 のみを反復するブレイク、`rows=10, measures=6`=60 row＋break）／`outro`（intro の変形）。`order=[intro, verse, verse, chorus, verse, breakdown, chorus, outro]`。

### 2.5. 文法

- リフ本体はプロファイル内に **拍子非依存の「1 measure 分の RhythmMotif 列」を拍子ごとに複数持つ辞書**として定義する（例: `RIFF_7_8 = (RhythmMotif((0,2,4,8,10)), ...)` の 14-row 版、`RIFF_5_8` の 10-row 版）。`compose_measure` は `mctx.measure_rows` を見て対応する辞書から motif を引く（`measure_rows` は EXT-2 で `MeasureCtx` に追加されたフィールドをそのまま使う）。
- ドラムは拍子ごとに「キック位置」をリフのアクセントと同期させる（ギターのパワーコード onset と同じ row に kick、フレーズ末に crash）。
- ベースはギターのルートをユニゾンでなぞる（プログレ/マスロックの定型）。
- リード（`CH_LEAD`）は `chorus` セクションのみ登場し、`verse`/`breakdown` では休符（リフの複雑さを聴かせる区間と歌メロ的パートを分離する構成判断）。

### 2.6. 使用する core 拡張

`GenreProfile.variable_meter=True`、`ChordSlot.rows` を 7/8=14, 5/8=10, 8/8=16 の3種で使い分ける。`CellGrid.insert_command` による `D00` 挿入はエンジンが自動で行うため、プロファイル側は各 `PatternPlan` の最終 measure の最終 row に1チャンネル分の空きを残すだけでよい（`breakdown` パターンの最終小節末尾は crash を鳴らさない設計にして空きを確保する、等の具体的な配慮を実装時に行う）。

---

## 3. `orchestral`（フルオーケストラ / 劇伴）

### 3.1. チャンネル構成（8ch, `target_format="xm"`）

```
CH_VLN1, CH_VLN2, CH_VLA, CH_VC, CH_CB, CH_WW, CH_BRASS, CH_TIMP = 0..7
```
| ch | 役割 | サンプル | `SampleSpec.pan` |
|:---|:---|:---|:---|
| VLN1 | 第1ヴァイオリン（旋律） | `ORCH_VIOLIN` (shift=0) | 30（左寄り） |
| VLN2 | 第2ヴァイオリン（対旋律/ハーモニー） | `ORCH_VIOLIN`（同一パッチを別スロットで複製、finetune 微小デチューンでアンサンブル感） | 80 |
| VLA | ヴィオラ | `ORCH_VIOLA`（`ORCH_VIOLIN` の `shift=-7`, 倍音構成を少し暗く） | 150 |
| VC | チェロ | `ORCH_CELLO`（`shift=-12`） | 190 |
| CB | コントラバス | `ORCH_BASS_STR`（`shift=-24`） | 210（右寄り） |
| WW | 木管（フルート/オーボエを priority で共有） | `ORCH_FLUTE`, `ORCH_OBOE` | 100 |
| BRASS | 金管（march の `HORN`/`SECTION` 資産を流用・拡張） | `ORCH_HORN`（march `MARCH_BRASS_HORN` を再利用）, `ORCH_TRUMPET`（新規） | 160 |
| TIMP | ティンパニ・打楽器 | `ORCH_TIMPANI`（音程付き打楽器）, `ORCH_CYMBAL_SWELL` | 128（中央） |

### 3.2. 音色キット（新規のみ抜粋）

| 名前 | 構成 | 備考 |
|:---|:---|:---|
| `ORCH_VIOLIN` | `ToneLayer(h=1..8, weight 1/h^0.8)` を2層、片方は `mult` を隣接整数（`K, K+1`。**`Finish=Loop` の `mult` は整数サイクル数でなければならないため、比率での「±0.3%」指定は不可**＝`core/synth.py` 制約。`fb_supersaw`（実装済み）と同じ「大きめの L を選び隣接整数でうなりを作る」技法）にずらす合成内デチューンで束ねてアンサンブル感。`Finish=Loop(length, attack_samples=N)`（弓の起動は `Loop.attack_samples` で表現する。**`Patch.attack_ms` は OneShot 専用のため Loop では使えない**＝同じく `core/synth.py` の `Patch.__post_init__` 制約） | |
| `ORCH_CELLO` | `ORCH_VIOLIN` と同じ倍音則を `shift=-12` で。`Finish=Loop(length, attack_samples=N')`（`N' > N`、より重い弓の起動を長めの `attack_samples` で表現） | |
| `ORCH_TIMPANI` | `ToneLayer(基音+3倍音,decay_alpha=各違う)` + 微小 `PitchSweepLayer`（打面の立ち上がりピッチドロップ）。`Finish=OneShot(1.1s)`、`pitched=True` | march の `BD` と違い明確な音程を持つ点が核心の差 |
| `ORCH_CYMBAL_SWELL` | `NoiseLayer(filter=hp, rise_power=1.5)`（立ち上がりクレッシェンド）。`Finish=OneShot(2.0s)` | ロール/スウェル専用。個々の打点ではなく持続的な高揚に使う |
| `ORCH_TRUMPET` | march `MARCH_BRASS_SECTION` を `dataclasses.replace()` で `attack_ms` を短縮（金管らしい鋭いアタック）した派生 | |

### 3.3. 進行

機能和声（I-IV-V-vi 系）だが5〜6声（VLN1/VLN2/VLA/VC/CB＋WW or BRASS）でボイシングする必要があるため、`Registers` を6段に拡張した独自の `OrchRegisters`（`bass`/`tenor`/`alto`/`soprano1`/`soprano2`/`descant` の6音域）を `profiles/orchestral.py` にローカル定義し、`harmony.voice()` は使わず**手書きボイシング関数**（nostalgic の `explicit=True` 流儀）で `ChordDef` を組み立てる（`harmony.voice()` は4音域=`Registers`固定のため、6音域には直接使えない）。

**声部ごとの目標音の受け渡し方（設計レビューで修正）**: 当初案は「`PatternPlan.extra` に声部リストを積む」としていたが、`PatternPlan.extra`／`PatternCtx.extra` は**pattern 単位**（1つの `PatternPlan` 内の全 measure で共有）のデータであり、和音は measure ごとに変わるため、6声の目標音（measure ごとに異なる）を pattern 単位の `extra` に置くことはできない（`ChordDef` 自体にも汎用の `extra` フィールドは無い）。正しい設計は、march/swing-jazz/prog-rock が既に使っている**「`begin_pattern` で `plan()` と同じ純粋関数を呼び直し、pattern 内で共有する状態として保持する」パターン**（`GenreProfile.begin_pattern(pctx, rng) -> Any` の既存契約）をそのまま踏襲すること:

```python
def voice_orch_progression(name: str, tonic_pc: int) -> list[OrchVoicing]:
    """plan() が ChordSlot 用の label 等を作るのに使い、begin_pattern() が同じ引数で
    呼び直して6声の目標音テーブルを再構築するのに使う、純粋関数（march の
    voice_march_progression と同型）。"""
    ...

@dataclass
class OrchState:
    voicings: list[OrchVoicing]   # 現在の pattern の measure_idx でそのまま引ける
    extra: dict = field(default_factory=dict)

def begin_pattern(self, pctx, rng):
    tonic = (pctx.key_pc or 0) + pctx.key_offset
    return OrchState(voicings=voice_orch_progression(pctx.kind, tonic))

def compose_measure(self, mctx, state, rng, buf):
    voicing = state.voicings[mctx.measure_idx]   # 6声の目標音
    ...
```
これは既存の core 契約（`begin_pattern`/`state`）だけで完結し、**core 変更は不要**（当初案の結論自体は正しかったが、根拠にしていた仕組みが誤っていた）。

### 3.4. 曲構成

劇伴的な起伏（intro → theme → development → climax → resolution）。`intensity` を 0.3→0.5→0.7→1.0→0.4 と推移させ、`composer.ramp`/`fade_cells` で持続音のクレッシェンド/デクレッシェンドを演出する。`order` は5 pattern を1回ずつ（ループしない通作形式。既存ジャンルが基本ループ主体だったのに対し明確な差別化）。

### 3.5. 使用する core 拡張

`target_format="xm"`、`channel_plan` は8要素。`engine.validate_profile` の分岐（§4.6②）によりチェックされる。`SampleSpec.pan` を上表の通り設定。**EXT-6 の他要素（エンベロープ、複数サンプルキーマップ）は使わない**（§4.6 のスコープ通り）。

---

## 4. `trap`（トラップ / ドリル）

### 4.1. 音色キット

| 名前 | 構成 | 備考 |
|:---|:---|:---|
| `TRAP_808` | `ToneLayer(正弦, decay_alpha=小)` 単層。`Finish=OneShot(0.9s)`、`shift=-12`、`saturate=1.3`（軽いサチュレーションで存在感） | ロングテール。ポルタメント（3xx）でピッチスライドさせる前提の音色なので倍音は最小限（サイン波中心） |
| `TRAP_SNARE_CLAP` | `NoiseLayer(filter=hp, decay_alpha=大)` × 2（わずかに時間をずらして重ね「クラップ」の複数発感を近似） | 2層とも `NoiseLayer`（型は同じでも `noise_seed` を変えて独立ノイズ列にする） |
| `TRAP_HAT_CLOSED` | `NoiseLayer(filter=hp, decay_alpha=非常に大)`。`Finish=OneShot(0.05s)` | 短い。ロールは `groove.retrigger_param` で1セル内多重化 |
| `TRAP_HAT_OPEN` | `TRAP_HAT_CLOSED` の `decay_alpha` を小さくした派生（`dataclasses.replace`） | |
| `TRAP_LEAD_PLUCK` | `ToneLayer(h=1,2,4 weight 1,.6,.3)` → `post_filter=lp`。`Finish=OneShot(0.5s)` | ダークなメロディック・パーカッシブ音色 |

### 4.2. ChannelPlan

```
K808, SNARE, HAT_C, HAT_O, LEAD = 1..5
CH_808, CH_SNARE, CH_HAT, CH_LEAD = 0,1,2,3
CHANNEL_PLAN = (
    ChannelRole("808", {K808}),
    ChannelRole("snare", {SNARE}),
    ChannelRole("hat", {HAT_C, HAT_O}, {HAT_O: 2, HAT_C: 1}),
    ChannelRole("lead", {LEAD}),
)
```

### 4.3. 進行

Cマイナー、`i - VI`（Cm - Ab）の2和音ループ（`rows_per_measure=32`、1 measure=4/4=32row＝1拍8row＝32分音符グリッド。32は64の約数のため `variable_meter` 不要で既存 core のままで合法）。**設計レビューで修正**: 当初案の4和音 "i-VI-VII-i" は、`rows_per_measure=32` だと1 pattern（64row）に2 measure しか収まらず、4和音では物理的に収まらないことが実装時に判明した（`variable_meter=True` を使わずに済ませるための制約）。実際の trap は2和音ループが非常に一般的であるため、i-VI の2和音（2 measure=64row でちょうど収まる）に簡略化した。`plan()` は全 `PatternPlan` に同一の2和音進行を渡し、和声はセクションを通して静的に保つ（実際の trap 慣習どおり、ドラム編成の変化でセクションを差別化する。§4.4）。

### 4.4. 曲構成

`intro`（ハイハットロールのビルド、808/スネアなし）→`verse`（スパース、808パターン中心）→`hook`（フル編成）→`half_time`（ブリッジ、密度半分）→`outro`（808のみ、intensity を下げて静かに終える）の5 `PatternPlan`。`order=[intro, verse,verse, hook,hook, half_time, hook,hook, outro]`（`hook` は同じ `PatternPlan` を4回再利用する。和声を全区間で静的に保つ設計（§4.3）のため march の `trio`/`trio2` のような区別は不要）。**実装時の簡略化**: 当初案の outro の `composer.fade_cells` によるディケイは、単に `chord.bass` を1回（row0）だけ低音量で鳴らす方式に簡略化した。

### 4.5. 文法（実装済み。`profiles/trap.py` の値と一致）

- **808パターン**: `RhythmMotif` 相当の固定行 `(0,8,12,20)`（拍=8row間隔のシンコペーション）で `chord.bass`（root）と `fold_into_range(chord.bass+7,*BASS_REG)`（fifth）を交互に鳴らす（1 measure 内での root-fifth 往復。当初案の「和音が切り替わる直前」＝measure をまたぐ和音進行へのグライドは、`i-VI` の2和音ループへの簡略化（§4.3）により measure 内の root-fifth 往復へ置き換えた）。2打目以降は `automation.portamento_param(PERIODS[prev_t], PERIODS[note_t], rows=1)` で `effect=3` グライドを付与する。**`PERIODS` の添字は tracker note**（`t = note - ins["k808"].spec.shift`）であり `chord.bass` 等の logical note をそのまま使わない（CORE_EXTENSION_DESIGN §4.5② 参照。実装時に判明した注意点）。
- **ハイハット**: 8分（row 4刻み、8箇所）で `HAT_C`。measure に1箇所、確率0.6で「ロール」に差し替え、そこへ `groove.retrigger_param(3)`（1row内3連打）を適用。フレーズ末尾の row には `HAT_O`（優先度2で `HAT_C` を上書き）。
- **スネア/クラップ**: row 16, row 28（2拍・4拍相当。4拍目はやや後ろにずらす trap の定型）に配置。intensity に応じて vol を調整。
- **リード**: `hook` のみ登場。`MelodyGenerator`（`ScaleRules(leap_probability=0.2, dissonance_weight=0.1)`、Cエオリアン）で短いフレーズを生成し、他は空ける（ドラム/808の存在感を最優先するジャンル特性）。

### 4.6. 使用する core 拡張

`groove.retrigger_param()`（EXT-1のサブステップ）と `automation.portamento_param()`（EXT-5の808グライド）のみ。両者とも状態を持たない純粋関数呼び出しであり、`post_processors`/`finalize_pattern` のような新規フックは不要（`compose_measure` の中で直接 `Instrument.cell(effect=.., param=..)` に渡すだけ）。

---

## 5. `maqam`（中東マカーム / インド古典）

### 5.1. 音律設計

maqam Rast（G を主音 qarar とする）を採用。ジンス（テトラコルド）Rast の度数を cents で定義:

```python
# profiles/maqam.py 内、core/pitch.MicroScale を使う
RAST_ON_G = MicroScale(tonic_pc=7, degrees_cents=(0, 200, 350, 500, 700, 900, 1050))
#  度数: 主音(0) - 全音(200) - 中立3度(350, "半フラット3度") - 完全4度(500)
#        - 完全5度(700) - 全音(900) - 中立7度(1050, "半フラット7度")

QARAR_NOTE = pitch.parse("G-2")   # qarar を実際に置くオクターブ（logical note）。tonic_pc=7(G) と一致させる
```
度数2・6（350¢・1050¢）が12-ETから外れる「中立音程」。度数 `d`（0..6）ごとに
`t, ft = resolve_micronote(RAST_ON_G.absolute_cents(d, QARAR_NOTE))` で `(t, finetune)` を求める
（`absolute_cents()` は `degree_cents()`＝tonic からの相対セントに `QARAR_NOTE` のオクターブ配置を
加えて logical note 0 からの絶対セントへ変換する。CORE_EXTENSION_DESIGN §4.3 参照）。該当する2度数
（2・6）のみ finetune 分散サンプル（`finetune≈+6〜+7`、§4.3 の近似）を追加 `Instrument` スロットとして
用意する（他の度数は通常の12-ET音で足りる）。度数→`(t, instrument key)` の対応表は `profiles/maqam.py`
内で一度だけ計算してモジュール定数として持つ（毎回 `resolve_micronote()` を呼び直さない）。

### 5.2. 音色キット

| 名前 | 構成 | 備考 |
|:---|:---|:---|
| `MAQAM_OUD` | `ToneLayer(h=1..6, weight 1/h, 各 decay_alpha=8+h)` + `PitchSweepLayer(340→270Hz, weight 0.15)`（撥弦アタックの微小ピッチドロップ）。`Finish=OneShot(0.6s)` | 主旋律／タクシーム用。中立音程は `finetune` 派生スロット（`oud_n3`, `oud_n7`。`build_samples()` で `dataclasses.replace(oud, finetune=...)` して追加登録、新規 Patch は作らない）。実装済み（`synth_presets.MAQAM_OUD`）の値と一致 |
| `MAQAM_NAY` | `ToneLayer(K=120*h, h=1,3,5, weight 1/h)` を中心に `K+1` の2層目（`weight 0.8/h`）を重ねる（比率指定ではなく整数サイクル数の差で表す＝`fb_supersaw` と同じ技法。`L=3800`）。`Finish=Loop(3800,0)` | 通奏低音（qarar ドローン）に使用。**`NoiseLayer`（息音）は使わない**（`Finish=Loop` は `ToneLayer` のみ許可という `core/synth.py` 制約）。実装済みの値と一致 |
| `MAQAM_QANUN` | `ToneLayer(h=1..4, weight 1/h, 各 decay_alpha=14+3h)`。`Finish=OneShot(0.35s)` | 分散和音的伴奏（アルペジオ）。実装済みの値と一致 |
| `MAQAM_DAF_DUM` | `ToneLayer((1.0,1.0,16.0),(2.0,0.3,22.0))`。`Finish=OneShot(0.32s)`、`pitched=False` | フレームドラムの低音打 DUM |
| `MAQAM_DAF_TEK` | `NoiseLayer(filter=hp,decay_alpha=55)`。`Finish=OneShot(0.12s)`、`pitched=False` | フレームドラムの高音打 TEK |

### 5.3. リズム（usul）と ChannelPlan

usul は maqsum（4/4、8分割）: `DUM . TEK . . DUM TEK .`（8分グリッド、row 0=DUM, row2=TEK, row4=空, row5=DUM, row6=TEK, 他休符。`rows_per_measure=16`＝16分格子で書けば `row 0=DUM, row4=TEK, row8=空, row10=DUM, row12=TEK`）。

```
DUM, TEK, OUD, OUD_N3, OUD_N7, NAY, QANUN = 1..7
CH_PERC, CH_OUD, CH_NAY, CH_QANUN = 0,1,2,3
CHANNEL_PLAN = (
    ChannelRole("perc", {DUM, TEK}, {DUM: 2, TEK: 1}),
    ChannelRole("oud", {OUD, OUD_N3, OUD_N7}),
    ChannelRole("nay", {NAY}),
    ChannelRole("qanun", {QANUN}),
)
```

### 5.4. 曲構成

`taqsim`（自由リズム風イントロ、打楽器なし、oud 単独のフレーズ。実際のテンポは一定だが row の粗密で自由リズム感を演出＝EXT-5は使わない、既存の枠内）→`ostinato_a`（usul 主体、qanun アルペジオ＋nay ドローン）→`ostinato_b`（intensity up、oud が旋律を取る）→`taqsim`（間奏として再利用。`order=[0,1,2,0,1,3]` で同一 `PatternPlan` を指す。march/swing-jazz と同じ「同じ pattern を order で使い回す」流儀）→`ostinato_a` 再現→`coda`。4つの `PatternPlan`（`taqsim`/`ostinato_a`/`ostinato_b`/`coda`）で6区間を構成する。

### 5.5. 文法

- `chord`（`ChordDef`）の使い方を maqam 用に転用: `chord.bass` = qarar（主音ドローン音）、`chord.harmony` = ghammaz（属音、5度ドローン）、`chord.scale_tones` = ジンスの全音（`tuple[int, ...]` という既存の型どおり、`resolve_micronote()` の戻り値 `(t, ft)` のうち **`t`（12-ET最近傍のtracker/logical note）だけ**を積む。`ChordDef` 自体に「どの `Instrument` を使うか」の情報を持たせる新規フィールドは追加しない）、`chord.chord_tones` は未使用（`quality`/`CHORD_QUALITIES` を経由しない独自の `ChordDef` を直接構築するため、march/nostalgic と同じ「明示的ボイシング」パターン）。
  「どの `Instrument`（`oud`／`oud_n3`／`oud_n7`）を使うか」は `ChordDef` とは別に、`profiles/maqam.py` にローカル定義する `NEUTRAL_DEGREE_INSTRUMENT: dict[int, str]`（度数インデックス→サンプルキー名。度数2→`"oud_n3"`、度数6→`"oud_n7"`、他の度数→`"oud"`）で持つ。`_maqam_phrase()`（下記）は度数インデックス（`scale_tones` の並び順）で `t` と `instrument key` の両方を同時に引けるよう、`scale_tones` と並行するローカルなタプル（`SCALE_DEGREE_INSTRUMENTS`）を持つ設計にする（`ChordDef` は変更しない。march の `RngStreams`／`ScaleRules` と同じ「ジャンル固有の参照データはローカルに置く」原則に合致）。
- `MAQAM_NAY` は qarar/ghammaz のドローンとして `ostinato_*` の全 measure で持続（`Instrument.off()` を pattern 末尾でのみ使用）。
- `MAQAM_QANUN` は各 measure の頭でジンスを上行分散和音として弾く（`RhythmMotif((0,2,4,6))` 相当を16分格子で）。
- `MAQAM_OUD` の旋律は `MelodyGenerator` を使わず、maqam 特有の「上行と下行で経過音が変わる」性質を素直に表すため**ローカルな専用生成関数**（`_maqam_phrase()`）を書く（中立音程度数を含む `scale_tones` プールから順次進行、跳躍は5度・4度のみ許可）。

### 5.6. 使用する core 拡張

`core/pitch.py` の `MicroScale`/`resolve_micronote()`（EXT-3）のみ。生成された `(t, finetune)` の finetune 値ごとに `build_samples()` で `dataclasses.replace(base_spec, finetune=ft)` した派生 `SampleSpec` を追加登録する（新規 `Instrument` スロットが2つ増えるだけで、`Cell`/`Instrument.cell()` は無変更で使える）。

---

## 6. `minimalism`（ミニマル / フェーズ音楽）

### 6.1. 音色キット

| 名前 | 構成 | 備考 |
|:---|:---|:---|
| `MIN_MARIMBA` | `ToneLayer(基音+2倍音,decay_alpha=中)` + 極小 `PitchSweepLayer`（マレットアタックの微小ピッチ）。`Finish=OneShot(0.35s)` | |
| `MIN_VIBRAPHONE` | `ToneLayer(基音+4倍音,decay_alpha=小=長い余韻)`。`Finish=OneShot(1.2s)` | |
| `MIN_PIANO_PULSE` | `ToneLayer(h=1..5 減衰速め)`。`Finish=OneShot(0.25s)` | 一番速い周期（16row）を担当するため短い減衰にする |
| `MIN_WOODBLOCK` | `ToneLayer(単一倍音,decay_alpha=非常に大)`。`Finish=OneShot(0.08s)` | 最長周期チャンネルのアクセント |

### 6.2. ChannelPlan・周期設計

```
CH1(16row周期, MIN_PIANO_PULSE), CH2(12row周期, MIN_MARIMBA),
CH3(8row周期, MIN_VIBRAPHONE), CH4(6row周期, MIN_WOODBLOCK)
LCM(16,12,8,6) = 48 row  (<=64。variable_meter=True で D00 break)
```
4チャンネルとも `allowed` は自チャンネル固定の単一サンプル（`priority` 不要、常に単一楽器）。

### 6.3. 進行

和声は動かさない（Cメジャー・ペンタトニック主体の単一モード）固定ドローン的響き。`PatternPlan` はコード進行ではなく**フェーズ段階**を表す（`kind="phase0".."phase7"`）。

### 6.4. 曲構成（フェージング・プロセス）

各チャンネルは固定の「セル（cycle_rows 分の固定パターン）」を持つが、CH1（16row周期＝最も遅い）のセル内容を **フェーズ段階が進むごとに1 row ずつ右シフト**させる（`cycle_rows` 分の配列を `deque.rotate` 相当で回転させたものを毎回使う、または `polymetric_row(row, cycle_rows)` の結果に対しさらに `- phase_offset` した位置のセルを参照する）。フェーズ段階を `phase0..phase15`（16段階、CH1の周期16と一致させて1周させる）とし、`order` はこれを順番に並べる。曲全体で「ズレて→揃って戻る」という典型的なフェイズ・ミュージックの聴取体験を作る。

### 6.5. 文法

```python
def compose_measure(self, mctx, state, rng, buf):
    phase = int(mctx.pattern.kind.removeprefix("phase"))
    for (ch, cycle_rows, cell_fn) in self.tracks:      # tracks はプロファイルのローカル定義
        shift = phase if ch == CH1 else 0               # CH1 のみフェーズオフセットを掛ける
        for row in range(mctx.measure_rows):            # measure_rows = LCM = 48
            local_row = structure.polymetric_row(row - shift, cycle_rows)
            cell = cell_fn(local_row)                    # 各チャンネル固有の固定パターン関数
            if cell is not None:
                buf.put(row, ch, cell)
```
`cell_fn` はチャンネルごとにローカル定義した固定の「このセル内 row → Cell（またはNone）」マップ（ライヒの "Piano Phase" のような、決まった音型の反復）。乱数は使わない（ミニマルは決定論的な反復が本質のため、`rng` はほぼ未使用というジャンル特有の判断）。

### 6.6. 使用する core 拡張

`ChordSlot.rows=48`（1 pattern=1 measure という特殊な使い方）、`GenreProfile.variable_meter=True`、`core/structure.polymetric_row()`。他 EXT は不使用。

**row 0／最終 row（row 47）の空きチャンネル契約**（prog-rock の実装で確立した制約と同型。CORE_EXTENSION_DESIGN §4.2）: `tempo_policy="engine"`（既定のまま）の場合、`apply_tempo` が row 0 に1チャンネルの空きを要求する。また `variable_meter=True` により row 47（LCM-1）に `D00` が自動挿入されるため、そこにも1チャンネルの空きが要る。4チャンネルの `cell_fn` を設計する際、少なくとも1チャンネルは phase=0 の row 0／row 47 で休符になるよう周期をずらす（例: `CH4`＝周期6の `MIN_WOODBLOCK` を「row 0 ではなく row 1 から開始する」ようオフセットを付ける等）。既存の `swing-jazz`／`prog-rock` と同じく、密な編成でこの余地が無い row があっても `apply_tempo`／`D00` 挿入自体は `ChannelConflictError` を送出して止まる設計（`apply_swing`/`render_tempo_curve` と異なり構造的に必須のため graceful skip はしない。§4.0.2）なので、cell_fn 設計時に実際に確認する。

---

## 7. `future-bass`（フューチャーベース / グリッチ）

### 7.1. 音色キット

| 名前 | 構成 | 備考 |
|:---|:---|:---|
| `FB_KICK` | `PitchSweepLayer(freq_start=150,freq_end=45,pitch_decay=28,decay_alpha=12)` + `NoiseLayer(decay_alpha=2800,weight=0.1)`。`saturate=1.5`、`Finish=OneShot(0.25s)` | サイドチェインのトリガ音源。実装済み（`synth_presets.FB_KICK`）の値と一致 |
| `FB_SUB` | `ToneLayer((3.0,1.0,None))` 単層（K=3, L=190、130.8Hz基準）。`Finish=Loop(190,0)`、`shift=-12` | ダッキング対象。ループ音色のため `Instrument.off()` での消音も使う。実装済みの値と一致 |
| `FB_SUPERSAW` | `ToneLayer(K=120*h, h=1..8, weight 1/h, filter=lp)` を中心に、`K±1`（隣接整数）の2層を重ねた **3層**スーパーソウ（`L=3800`。比率での「±0.4%」指定は `Finish=Loop` の `mult`＝整数サイクル数制約に反し構築時エラーになるため、隣接整数差で約0.8%(h=1)〜0.1%(h=8)のうなりを作る）。各層自身の `filter=lp a=0.3` でまとめて丸める。`Finish=Loop(3800, 0)` | ダッキング対象。コード/パッド兼用。**`Patch.post_filter` は OneShot 専用のため使えない**（`core/synth.py` 制約）ので、フィルタは各 `ToneLayer.filter` に個別に掛ける（`dsp.circular` でループ境界の連続性を保ったまま濾過される）。実装済み（`synth_presets.FB_SUPERSAW`）の値と一致 |
| `FB_VOCAL_CHOP` | `ToneLayer(フォルマント風に h=1..10 を不均一weight)` + `NoiseLayer(weight小)`。`Finish=OneShot(1.6s、長尺）`、**`pitched=False`** | `sample_offset_param()` でシラブル位置を切り出す前提の1本の長いサンプル。`pitched=False` にすることで `Instrument.cell()` が `n` を無視し常に `rate_note` の音高で鳴る＝`9xx` の offset だけでシラブルを切り替える設計が成立する（`n` を変えて別ピッチで鳴らす通常の打楽器運用とは異なり、ここでは「音高固定・offset のみ可変」が目的） |
| `FB_CLAP` | `NoiseLayer(filter=hp,decay_alpha=35)` + `NoiseLayer(filter=hp,decay_alpha=14,weight=0.6)`。`saturate=1.3`、`Finish=OneShot(0.18s)` | march 系ではなく2層の減衰速度差で多重発音のクラップ感を近似（`Patch.noise_seed` は1つの乱数列を全レイヤーが順番に消費するため、層ごとの seed 指定は不要で自動的に独立したノイズ列になる）。実装済みの値と一致 |

### 7.2. ChannelPlan

```
KICK, SUB, SAW, VOX, CLAP = 1..5
CH_KICK, CH_BASS, CH_CHORD, CH_LEAD = 0,1,2,3
CHANNEL_PLAN = (
    ChannelRole("kick", {KICK, CLAP}, {CLAP: 2, KICK: 1}),
    ChannelRole("bass", {SUB}),
    ChannelRole("chord", {SAW}),
    ChannelRole("lead", {VOX}),
)
```

### 7.3. 進行

Eb メジャー、明るいポップ的進行 `I - V - vi - IV`（Eb - Bb - Cm - Ab）、`rows_per_measure=16` の通常グリッド。

### 7.4. 曲構成

`intro_chop`（ヴォーカルチョップのみ、`sample_offset_param()` で1本のサンプルから複数シラブルを叩き出す）→`buildup`（キック＋ハイハット的要素を `FB_CLAP` で代用しつつ密度を増やす）→`drop`（フル編成、コード×サブベース×キックのサイドチェイン全開）→`breakdown`（キック抜き、コードのみでダッキング一時停止）→`drop2`→`outro`。`order=[intro,intro, buildup, drop,drop, breakdown, drop,drop, outro]`。

### 7.5. 文法

- `drop`/`buildup` の `FB_KICK` は4つ打ち（`row 0,4,8,12`）。
- `FB_SUB`/`FB_SAW` は measure 頭で和音を鳴らしたあと持続（ループ音色）。**ダッキングは `compose_measure` 内では一切行わず**、全パターン生成後に `post_processors` で `mixer.apply_sidechain()` を適用する（EXT-4 設計通り、生成と装飾を分離）。
- `FB_VOCAL_CHOP` は `intro_chop` でのみ使用。1本の長尺サンプルを 4〜6 個のシラブル位置（`sample_offset_param(offset_samples=..., length_words=...)`で計算した param 値の辞書をプロファイル内にローカルに定義）から `rng.melody` でランダムに選んで `Instrument.cell(rate_note相当, effect=9, param=slice_param)` で叩く（`pitched=False` 扱いの打楽器的運用）。

### 7.6. 使用する core 拡張（実装済み。`profiles/future_bass.py` の値と一致）

```python
# CH_KICK は kick/clap が優先度を共有するチャンネル（§7.2）のため、backbeat（row 4,12）では
# clap が kick を置換し、実際のセルには clap しか残らない。kick だけをトリガにすると
# ドロップの4拍のうち2拍（row 4,12）でダッキングが検出できない（実装時に判明した修正）。
# kick と clap の両方をトリガとして登録し、4拍とも確実にダッキングさせる。
SIDECHAIN_RULES = (
    SidechainRule(trigger_sample=KICK, target_channel=CH_BASS, duck_ratio=0.25, release_rows=3),
    SidechainRule(trigger_sample=KICK, target_channel=CH_CHORD, duck_ratio=0.35, release_rows=4),
    SidechainRule(trigger_sample=CLAP, target_channel=CH_BASS, duck_ratio=0.25, release_rows=3),
    SidechainRule(trigger_sample=CLAP, target_channel=CH_CHORD, duck_ratio=0.35, release_rows=4),
)
post_processors = (lambda song, plan: mixer.apply_sidechain(song, SIDECHAIN_RULES),)
```
と `mixer.sample_offset_param()`（EXT-4②、`_intro_chop` のヴォーカルチョップで使用）。

---

## 8. `free-jazz`（フリージャズ / 現代無調音楽）

### 8.1. 音色キット

| 名前 | 構成 | 備考 |
|:---|:---|:---|
| `FREE_PIANO_CLUSTER` | `ToneLayer` 5層、`mult` を近接した比（1.0, 1.06, 1.13, 1.19, 1.26＝ほぼ半音刻み、各 decay_alpha 10〜20）で密集させたトーンクラスター。`Finish=OneShot(0.6s)` | 通常のコード（3度堆積）ではなく隣接音の密集。OneShot のため `mult` は整数サイクル数制約を受けない（Loop との違い）。実装済み（`synth_presets.FREE_PIANO_CLUSTER`）の値と一致 |
| `FREE_ARCO_BASS` | `ToneLayer(K=60,weight1.0)` + `ToneLayer(K=61,weight0.8)`（隣接整数デチューン、`L=3800`）。`Finish=Loop(3800,0)`、`shift=-12` | 持続的なアルコ（弓弾き）表現。**擦弦ノイズは `NoiseLayer` ではなくデチューンのうなりで近似**（`Finish=Loop` は `ToneLayer` のみ許可、かつ `mult` は整数サイクル数固定という `core/synth.py` 制約のため。`MAQAM_NAY`・`fb_supersaw` と同じ流儀）。実装済みの値と一致 |
| `FREE_SAX_SCREECH` | `ToneLayer(高次倍音, h=3..12, weight 1/h, 各 decay_alpha=6+h)` + `NoiseLayer(filter=hp,decay_alpha=10,weight=0.5)`。`Finish=OneShot(0.5s)` | アルティッシモの絶叫的音色。実装済みの値と一致 |
| `FREE_CYMBAL_SWELL` | `NoiseLayer(filter=hp, rise_power=1.5)`。`Finish=OneShot(2.0s)` | 立ち上がりクレッシェンドのスウェル。**実装時の修正**: 当初案の「`orchestral` の `ORCH_CYMBAL_SWELL` を流用」は、`orchestral` が Phase 4e 時点でまだ未実装のため実現できず、直接新規プリセットとして実装した（`orchestral` 実装時に同一内容を `ORCH_CYMBAL_SWELL` として登録すれば実質的な重複になるため、その時点で `FREE_CYMBAL_SWELL` を参照する形に整理するか検討する） |

### 8.2. 和声（手組み `ChordDef`。`CHORD_QUALITIES` は不使用。実装済み・`profiles/free_jazz.py` と一致）

```python
BASS_REG = (0, 11)      # arco_bass（shift=-12 → t=12..23）
CLUSTER_REG = (12, 35)  # piano_cluster／sax_screech（ともに shift=0。共有音域）

def _cluster_chord(root_pc: int, label: str, rng: random.Random) -> ChordDef:
    """root_pc を中心に隣接半音を2〜4個ランダムに選び、密集クラスターを作る（explicit=True 相当）。
    chord_tones は piano/sax 共有の CLUSTER_REG、bass は別途 BASS_REG に折り返す。
    """
    offsets = rng.sample((0, 1, 2, -1, -2, 6, 7), k=rng.randint(2, 4))
    tones = sorted({fold_into_range(root_pc + o + 12 * 2, *CLUSTER_REG) for o in offsets})
    bass_note = fold_into_range(root_pc, *BASS_REG)
    return ChordDef(label=label, bass=bass_note, harmony=bass_note,
                     chord_tones=tuple(tones), scale_tones=tuple(tones), arp=None, explicit=True)
```
**設計レビューで修正**: 当初案は `chord_tones` を1つの `MELODY_REG` で全楽器共有していたが、`arco_bass`
（`shift=-12`）と `piano_cluster`／`sax_screech`（`shift=0`）は有効な `n` の範囲が異なるため、同じ音域の
音を共有できない（`arco_bass` に `CLUSTER_REG` の音を渡すと `t=n+12` が範囲外になりうる）。
`chord.bass`（単一音、`BASS_REG` に折返し済み）を `arco_bass` 専用、`chord.chord_tones`
（`CLUSTER_REG` で共有）を `piano_cluster`／`sax_screech` 専用、と役割分担させて解決した。

`plan()` の中で `rng.plan` を使い、pattern ごとに4個の `_cluster_chord` を生成して `ChordSlot`
（各 `measures=1`）に積む（march の `voice_march_progression` に相当する自作の進行生成関数）。

### 8.3. ChannelPlan

```
PIANO_CL, ARCO_BASS, SAX_SCR, CYM_SWELL = 1..4
CH_PIANO, CH_BASS, CH_SAX, CH_PERC = 0,1,2,3
```
各チャンネル1サンプル固定（全楽器が対等に前景化しうる自由即興編成のため、march的な優先度上書きは使わない）。

### 8.4. 曲構成（通作、ルバート）

単一の連続楽曲として `movement_a`（静かな探求、intensity 0.2〜0.4）→`movement_b`（密度上昇、intensity 0.4〜0.8）→`climax`（intensity 0.9〜1.0、全楽器同時）→`movement_c`（余韻、intensity 0.3→0.1 でフェード）の4 pattern、ループなし `order=[a,b,climax,c]`。

### 8.5. 文法

- 各楽器は「確率的に発音するかしないか」を `mctx.pattern.intensity` に応じた確率でその row ごとに判定する（`rng.drums`/`rng.bass`/`rng.melody` をそれぞれ独立に使用、既存 `RngStreams` の4系統をそのまま活用）。密なコンポジションルールではなく**確率密度でテクスチャを作る**設計（フリージャズの非拍節的性格を、既存の row 格子の上で「疎密」として表現する）。
- `FREE_ARCO_BASS`/`FREE_PIANO_CLUSTER` はループ/持続音色として長く伸ばし、`climax` でのみ `FREE_SAX_SCREECH` の短い絶叫的フレーズを密集させる。

### 8.6. 使用する core 拡張（実装済み。`profiles/free_jazz.py` の値と一致）

`tempo_policy="profile"`。各 pattern の `finalize_pattern(pctx, pattern, state, rng)` で
`automation.TempoCurve` を1〜2本 `automation.render_tempo_curve()` に渡して適用し、pattern 間で
`start_bpm`＝直前 pattern の `end_bpm` として連続的に BPM を変化させ続ける（`movement_a`: 96→82
`ease_out`、`movement_b`: 82→126 `ease_in`、`climax`: 126→150→126 の2本、`movement_c`: 126→70
`linear`）。**実装時の簡略化**: 当初案は「最初の BPM を `pattern.insert_command(0, 0x0F, start_bpm)`
で別途明示する」としていたが、`render_tempo_curve()` は `start_row` 自身を含む range で走査し、
ループ先頭の `prev_bpm=None` により最初の row で必ず挿入を試みるため、`TempoCurve(96, 82, 0, 63, ...)`
を呼ぶだけで row 0 の初期 BPM 挿入も兼ねる（別呼び出しは不要と判明）。`SongPlan.bpm` は
`tempo_choices=(96,)` という単一値の宣言的な初期値（`validate_plan` の契約を満たすためのみに使い、
実際のテンポ推移には使わない）。

---

## 9. 新規 `synth_presets.py` エントリ一覧（実装時にそのまま追加する）

各ジャンル節の「音色キット」表に挙げた `Patch` を、既存の `MARCH_*`/`SUSPENSE_*`/`NOSTALGIC_*` と同じ命名規則で `SWING_*`／`PROG_*`／`ORCH_*`／`TRAP_*`／`MAQAM_*`／`MIN_*`／`FB_*`／`FREE_*` として `PRESETS`/`DESCRIPTIONS` に追加する。**`SWING_*`（5）／`PROG_*`（5）／`TRAP_*`（5）／`MAQAM_*`（5）／`FB_*`（5）／`FREE_*`（4）は実装済み**（`core/synth_presets.py`。現在 `PRESETS` は計50）。残り2ジャンル（orchestral/minimalism）で1ジャンルあたり平均5音色×2ジャンル＝**約10プリセット**が追加見込み（実装後の合計は60程度）。`core/synth.py` 自体（`Layer`/`Finish`/`Patch`）に新規追加すべきフィールド・型は、8ジャンル全ての設計を通しても**見つからなかった**（既存の3 Layer型・2 Finish型の組み合わせで全て表現できた。§8.1 の直交設計が8ジャンル分のバリエーションを十分にカバーすることの追加確認になった）。ただし `Finish=Loop` は `ToneLayer` のみ・`mult` は整数サイクル数のみ・`Patch.attack_ms`/`post_filter`/`decay_alpha`/`tail_fade_ms` は `OneShot` 専用という `core/synth.py` の制約に反する設計が本書の初稿には複数残っていた（`ORCH_VIOLIN`/`ORCH_CELLO`/`MAQAM_NAY`/`FB_SUPERSAW`/`FREE_ARCO_BASS`。§3・§5・§7・§8 で修正済み、`FB_SUPERSAW` は実装時に隣接整数 K の技法で実際に解決を確認）。持続音の「息／擦弦ノイズ感」は `NoiseLayer` を混ぜず、既存 `TENSION_STRINGS`/`NOSTALGIC_FLUTE` と同じ「近接デチューンのうなり」で代替するのが Loop 音色の正しい流儀である。

---

## 10. 未確定・試聴調整が前提の項目（実装時に詰める）

- ~~swing-jazz: `SwingConfig(long_speed, short_speed)` の最終比率~~ → **実装済み**（`7:5` で確定。`profiles/swing_jazz.py` の `SWING_CONFIG`）。試聴による再調整はいつでも可能。
- ~~prog-rock: 主リフの実音~~ → **実装済み**（`profiles/prog_rock.py`。ビブラート付与は簡略化のため未実装のまま。§2.1 `PROG_LEAD_GTR` 参照）。
- ~~trap: ハイハットロールの発生確率・密度、808グライドの正確な speed 値~~ → **実装済み**（ロール確率0.6、`portamento_param(rows=1)`。`profiles/trap.py`）。値は試聴による再調整の余地あり。
- ~~future-bass: `duck_ratio`/`release_rows` の初期値~~ → **実装済み**（`duck_ratio=0.25`(bass)/`0.35`(chord)、`release_rows=3`/`4`。`profiles/future_bass.py` の `SIDECHAIN_RULES`）。値は試聴による再調整の余地あり。
- maqam: `RAST_ON_G` 以外の maqam（Bayati 等）を追加するかどうかは**未実装のまま**（今回は Rast 1種のみを実装対象とした。`profiles/maqam.py` に他 maqam を追加する拡張は将来課題）。`_maqam_phrase()` の跳躍確率0.15等は試聴による再調整の余地あり。
- minimalism: フェーズ段階数（暫定16）と各チャンネルの固定音型（"Piano Phase" 的な具体的音符列）。
- ~~free-jazz: クラスター和音の音程選択肢、密度確率の具体的な数値テーブル~~ → **実装済み**（`(0,1,2,-1,-2,6,7)`、`DENSITY={"bass":0.18,"piano":0.25,"perc":0.08}`、`SAX_DENSITY_CLIMAX=0.12`。`profiles/free_jazz.py`）。値は試聴による再調整の余地あり。

いずれも `CORE_EXTENSION_DESIGN.md` §11 の「実装時の要検証事項」と同じ性質（設計としては完結しており、実装→試聴→微調整のサイクルで詰める値）であり、実装開始のブロッカーではない。
