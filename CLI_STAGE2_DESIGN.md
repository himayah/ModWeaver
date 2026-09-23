# CLI 改善・ジャンル自動検出 設計書（第２段階）

| 項目 | 内容 |
|:---|:---|
| 対象 | `次の検討事項.txt` 第２段階（① 引数なしで usage、② `--list-genres` の動的化、③ `--genre random`、④ `--version`、⑤ 英語版 README） |
| 前提ドキュメント | [FORMAT_TEMPO_DESIGN.md](FORMAT_TEMPO_DESIGN.md)（第１段階）、[EXTENSION_DESIGN.md](EXTENSION_DESIGN.md) §7.4（プロファイル登録簿） |
| ステータス | **実装済み**（branch `stage2-cli`）。§9 の論点は 2026-09-24 に決定済み、実装で判明したことは §11 |
| 作成日 | 2026-09-24 |

---

## 0. 要求（原文の整理）

- **R1 usage**: オプションなしで起動したら usage を表示して終了する（`--help` / `-h` と同じ）。
- **R2 ジャンル一覧**: `--list-genres`（原文の `--genre-lists` は書き間違い。ユーザー確認済み）で表示するジャンルは、表示のたびに `mod_weaver/profiles/` のモジュールを調べ、
  ジャンルモジュールであるものを表示する。各ジャンルモジュールはジャンル名と1行の説明を持ち、それを読み出して表示する。
  同じディレクトリにジャンルモジュール以外のファイルがあるなら、ジャンルモジュールだけを置く別ディレクトリへ移す。
- **R3 ランダムジャンル**: `--genre` / `-g` に `random` / `r` を指定したら、指定できるジャンルからランダムに選んで生成する
  （原文の `--gennre` は `--genre` の誤記と解釈）。
- **R4 バージョン**: `--version` / `-v` でバージョンと GitHub リポジトリの URL（https://github.com/himayah/ModWeaver）を表示する。
- **R5 README**: 英語版 README も作る。GitHub のリポジトリページでは日本語版を優先して表示する。

---

## 1. 現状調査（設計に影響するもの）

### 1.1 ジャンル一覧の現状

- オプション名は現在 **`--list-genres`**（原文の `--genre-lists` は書き間違いで、名前は変えない。§9 Q1）。
- 一覧の内容はすでに各ジャンルのクラス属性（`id`・`aliases`・`description`）から作っている（`cli.genre_listing()`）。
  説明はすべて1行。ジャンル名と説明を「持たせる」部分は実現済み。
- 足りないのは**検出方法**。`mod_weaver/profiles/__init__.py` が 12 ジャンルのモジュールを**名前を書いて** import しており、
  ファイルを置いただけではジャンルが増えない。

### 1.2 `mod_weaver/profiles/` にあるジャンル以外のファイル

| ファイル | 役割 | ジャンルモジュールか |
|:---|:---|:---|
| `__init__.py` | パッケージ初期化・登録用 import | いいえ |
| `base.py` | `GenreProfile` 抽象基底 | いいえ |
| `registry.py` | 登録簿（`register_profile` / `get_profile` / `list_profiles`） | いいえ |
| `nostalgic_samples.py` | nostalgic のサンプル合成（補助） | いいえ |
| `suspense_common.py` | suspense-slow / suspense-chase 共通の基底 `SuspenseBase`（補助） | いいえ |
| その他 12 ファイル | 各ジャンル（1ファイル＝1ジャンル） | はい |

ジャンル以外のファイルが同居しているので、要求どおり**ジャンルモジュールを専用ディレクトリ `mod_weaver/genres/` へ移す**（§3.1、§9 Q5）。

### 1.3 その他

- `mod_weaver/__init__.py` に `__version__ = "1.0.0"` がある（第１段階でも更新していない）。`--version` は未実装。
- `-v` はまだ使われていない（衝突なし）。
- 引数なしで起動すると現在は nostalgic を生成する。README の最初の例（`python modweaver.py`）もこの動作を前提にしている。
  テストはすべて何らかの引数を付けて起動しているので、R1 で壊れるテストはない（確認済み）。
- ジャンルの import 時間は全12ジャンルで約 0.15 秒。一覧表示のたびに全ジャンルを import しても問題にならない。
- `tempo_range` を狭めているのは現状 `free-jazz`（44〜163）だけ。

---

## 2. 全体方針

- **公開 API（`profiles.get_profile` / `list_profiles` / `resolve_id` / `register_profile`）は変えない。**
  変わるのは「ジャンルモジュールの置き場所」と「登録のきっかけ（名前を書いた import → ディレクトリ走査）」だけ。
- 生成結果（バイト列）は一切変えない。既存の回帰テスト（nostalgic のバイト一致等）が、移動で振る舞いが変わっていないことの確認になる。
- 引数処理はすべて `cli.py` に閉じる。engine・core は変更しない。

---

## 3. R2: ジャンルモジュールの自動検出

### 3.1 ディレクトリ構成

```text
mod_weaver/
├── profiles/                 # ジャンルの「仕組み」（ジャンルそのものは置かない）
│   ├── __init__.py           # 公開 API の再エクスポート＋ import 時に discover() を呼ぶ
│   ├── base.py               # GenreProfile
│   ├── registry.py           # 登録簿＋ discover()（新規）
│   ├── nostalgic_samples.py  # 補助（ジャンルではない）
│   └── suspense_common.py    # 補助（ジャンルではない）
└── genres/                   # ★ ジャンルモジュール専用（ここに .py を置けばジャンルが増える）
    ├── __init__.py           # パッケージ化のための空ファイル（docstring のみ）
    ├── nostalgic.py
    ├── suspense_slow.py
    ├── suspense_chase.py
    ├── march.py  swing_jazz.py  prog_rock.py  trap.py  future_bass.py
    └── maqam.py  free_jazz.py  minimalism.py  orchestral.py
```

- 補助モジュール（`nostalgic_samples.py`・`suspense_common.py`）は `profiles/` に残す。`genres/` にはジャンルモジュールだけを置く。
- `genres/__init__.py` は Python のパッケージとして扱うために必要な空ファイル（ジャンルとしては扱わない）。
- 移動は `git mv` で行い履歴を残す。移動したモジュールの import を書き換える
  （`from .base` → `from ..profiles.base`、`from .registry` → `from ..profiles.registry`、
  `from . import nostalgic_samples` → `from ..profiles import nostalgic_samples`、`from .suspense_common` → `from ..profiles.suspense_common`。
  `from ..core` はそのまま）。

### 3.2 検出の仕組み（`registry.discover()`、新規）

```python
GENRES_PACKAGE = "mod_weaver.genres"

def discover() -> None:
    """genres/ 直下の .py をすべて import し、@register_profile による登録を起こす。"""
    pkg = importlib.import_module(GENRES_PACKAGE)
    for info in sorted(pkgutil.iter_modules(pkg.__path__), key=lambda i: i.name):
        if info.ispkg or info.name.startswith("_"):
            continue                                  # サブパッケージと _ で始まるファイルは対象外
        name = f"{GENRES_PACKAGE}.{info.name}"
        already = name in sys.modules                  # 先に import 済み（import 途中を含む）なら登録の有無は問わない
        try:
            importlib.import_module(name)
        except Exception as e:                         # 1ファイルの不具合で CLI 全体を止めない
            log.warning("genre module %s skipped: %s", info.name, e)
            continue
        if not already and not any(c.__module__ == name for c in PROFILE_REGISTRY.values()):
            log.warning("%s has no @register_profile genre; ignored", info.name)
```

- `profiles/__init__.py` は名前を並べた import をやめ、`discover()` を1回呼ぶ。
- **「表示するたびに調べる」について**: CLI は起動ごとに新しいプロセスなので、`--list-genres` を実行するたびに
  `genres/` が走査される。ファイルを追加・削除すれば次の実行から一覧に反映される（`__init__.py` の編集は不要）。
- ジャンルかどうかの判定は「`@register_profile` で `GenreProfile` を登録しているか」。登録しない .py が `genres/` にあれば WARNING を出して無視する。
- import に失敗したファイルは WARNING を出してスキップする（他のジャンルは使える）。
  ただし同梱ジャンルが1つでも失敗したらテストで検出する（§8）。
- **循環 import への対処**: テスト等が `mod_weaver.genres.nostalgic` を直接 import すると、その途中で
  `mod_weaver.profiles` の初期化 → `discover()` が走り、import 途中の nostalgic が（まだ登録前の状態で）返ってくる。
  このとき「登録していない」と誤って警告しないよう、`discover()` を呼ぶ前から `sys.modules` にあったモジュールは検査しない
  （import が終われば自分で登録するので最終状態は正しい）。
- `pkgutil.iter_modules` はファイルシステム上のディレクトリを走査するので、Python 3.7 でも動く。

### 3.3 ジャンルモジュールが持つ情報と検査

各ジャンルクラスが既に持っている属性をそのまま使う（新しい属性は追加しない）。

| 表示項目 | 属性 | 備考 |
|:---|:---|:---|
| ジャンル名 | `id`（＋`aliases`） | `--genre` に指定する名前。表示名 `display_name` はバナー用で、一覧には出さない（現状どおり） |
| 1行の説明 | `description` | |

`register_profile` に次の検査を追加する（違反は `ValueError`。ジャンル作者が気づけるように import 時に落とす → §3.2 により WARNING でスキップ）:

- `id`・`description` が空でない文字列であること
- `description` が1行（改行を含まない）であること
- `id`・`aliases` が予約語 `random` / `r` でないこと（§5）

「1モジュール＝1ジャンル」はテストで検査する（実行時には強制しない。suspense のように共通基底を補助モジュールに切り出す書き方は引き続き可能）。

### 3.4 オプション名

**`--list-genres` のまま変えない**（§9 Q1）。一覧の書式も現状のまま:

```text
  nostalgic
      夕暮れの郷愁を誘う Lo-Fi ビートとオルゴール（従来の TwilightPad）
  suspense-slow (alias: suspense)
      低速・重苦しい緊張。心拍と無音、突発の金属音
  ...
```

---

## 4. R1: 引数なしで usage を表示

```python
argv = sys.argv[1:] if argv is None else list(argv)
parser = build_parser(prog)
if not argv:
    parser.print_help()          # --help と同じ内容を stdout へ
    return 0                     # --help と同じ終了コード
```

- 出力内容・出力先（stdout）・終了コード（0）とも `--help` と同一にする。ファイルは作らない。
- `--genre` の既定値 `nostalgic` は残す。何か1つでも引数があれば（例: `python modweaver.py -s 1`）従来どおり nostalgic を生成する。
- README の「新しい曲をランダム生成する」の例を `python modweaver.py -g nostalgic` に変える。`modweaver.py` の docstring も更新する。

---

## 5. R3: `--genre random` / `-g r`

- `random` と `r` を予約語にする（`cli.RANDOM_GENRE = ("random", "r")`）。登録簿側でも同名の id・別名を拒否する（§3.3）。
- 候補は登録済みの**正規 id**（`list_profiles()`、id 順）。別名は数えない（suspense-slow が2倍の確率で選ばれないように）。
- `--tempo` も指定されている場合は、`tempo_range` が要求範囲と**重なるジャンルだけ**を候補にする（§9 Q3）。
  重なるジャンルが無ければ `error: no genre supports tempo ...` で終了コード 2。
  （現状は free-jazz だけが範囲を狭めているので、例えば `-g r -t 200` なら free-jazz を除いた 11 ジャンルから選ぶ。）
- 選ぶための乱数は seed とは**独立**（seed 省略時の乱数と同じ `random` モジュール）（§9 Q2）。
  同じ `-s 5 -g random` でも実行ごとにジャンルが変わりうるが、再現コマンドには決まったジャンルが出るので、それで再現できる。
- 表示:
  ```text
  Genre       : trap (random)
  ...
  Success! To reproduce this exact song, run:
    python modweaver.py --genre trap --seed 482913
  ```
  再現コマンドは既に `profile.id` を使っているので変更不要。既定の出力先も決まったジャンル名（`trap/trap_482913.mod`）になる。
- 大文字小文字は区別する（既存の `--genre` と同じ。`Random` は未登録ジャンル扱いで終了コード 2）。

---

## 6. R4: `--version` / `-v`

```text
$ python modweaver.py --version
ModWeaver 1.1.0
https://github.com/himayah/ModWeaver
```

- `mod_weaver/__init__.py` に `__url__ = "https://github.com/himayah/ModWeaver"` を追加し、argparse の `action="version"` で表示する
  （stdout・終了コード 0。パーサは `RawDescriptionHelpFormatter` なので改行はそのまま出る）。
- `--version` は他のオプションより優先される（argparse の標準動作。`-v -g bogus` でもバージョン表示で終了 0）。
- バージョン番号は本段階のマージ時に **1.1.0** に上げる（§9 Q4）。

---

## 7. R5: 英語版 README

- 日本語版は **`README.md` のまま**（GitHub がリポジトリのトップに表示するのはルートの `README.md` なので、これで日本語が優先される）。
  `.github/README.md` や `docs/README.md` は作らない（GitHub はそちらを優先してしまうため）。
- 英語版は **`README.en.md`** を新規作成。内容は日本語版と同じ構成の全訳。
- 両ファイルの先頭（タイトル直下）に言語切替のリンクを置く:
  - `README.md`: `**日本語** | [English](README.en.md)`
  - `README.en.md`: `[日本語](README.md) | **English**`
- ジャンルの説明文（`description`）は日本語のままなので、`--list-genres` の出力も日本語のまま。
  英語版 README のジャンル表は README 上で英訳する（プログラム側の英語化は本段階の範囲外）。
- 日本語版 README もこの段階の変更に合わせて更新する（引数なし＝usage、`random`、`--version`、ファイル構成の `genres/`、本設計書へのリンク）。

---

## 8. テスト

| 対象 | テスト |
|:---|:---|
| 検出 | `genres/` 直下の .py（`_` 始まりを除く）の数 ＝ 登録ジャンル数、かつ各モジュールがちょうど1ジャンルを登録している |
| 検出 | 同梱ジャンルの import で WARNING が出ない（caplog） |
| 検出 | 一時ディレクトリに作った疑似 genres パッケージで: ジャンルを1つ足すと一覧に出る／登録しない .py は WARNING で無視／import 失敗は WARNING でスキップ（`GENRES_PACKAGE` を差し替え、登録簿は monkeypatch で空にして検査後に戻す） |
| 検査 | `description` の改行・空、予約語 `random`/`r` の id・別名で `register_profile` が `ValueError` |
| R1 | `main([])` が終了 0、stdout が `--help` の出力と一致、ファイルを作らない（chdir した tmp で確認） |
| R2 | `--list-genres` が全ジャンルを含む（既存テストのまま） |
| R3 | `-g random` / `-g r` で生成成功、バナーに `(random)`、再現コマンドのジャンルが登録済み id。`random.choice` を monkeypatch して選択を固定したテスト。`-g r -t 200` で free-jazz が候補に入らない。どのジャンルとも重ならないテンポ要求で終了 2 |
| R4 | `--version` / `-v` が終了 0、stdout にバージョンと URL |
| 既存 | テストの import を `mod_weaver.profiles.<genre>` → `mod_weaver.genres.<genre>` に書き換え。回帰テスト（バイト一致）はそのまま緑であること |

---

## 9. 決定事項（2026-09-24 ユーザー確認済み）

| # | 論点 | 決定 |
|:---|:---|:---|
| Q1 | オプション名 | 原文の `--genre-lists` は書き間違い。**`--list-genres` だけ**（新しい名前は追加しない） |
| Q2 | `random` の選択と `--seed` の関係 | seed と独立に選ぶ（再現はバナーの再現コマンドで） |
| Q3 | `random` と `--tempo` の併用 | テンポに対応できるジャンルだけから選ぶ |
| Q4 | バージョン番号 | 本段階のマージで 1.1.0 |
| Q5 | ジャンルモジュールの置き場所 | **`mod_weaver/genres/`**（補助モジュールは `mod_weaver/profiles/` に残す） |

---

## 10. 変更一覧と実装順序

### 10.1 変更ファイル

| ファイル | 変更 |
|:---|:---|
| `mod_weaver/genres/`（新規） | 12 ジャンルを `git mv`、import を修正 |
| `mod_weaver/profiles/registry.py` | `discover()` 追加、`register_profile` の検査追加 |
| `mod_weaver/profiles/__init__.py` | 名前を並べた import → `discover()` |
| `mod_weaver/cli.py` | 引数なし usage、`random`、`--version`、バナーの `(random)` |
| `mod_weaver/__init__.py` | `__url__` 追加、`__version__` を 1.1.0 |
| `modweaver.py` | docstring 更新 |
| `tests/**` | import の書き換え、§8 の新規テスト |
| `README.md` | 第２段階の内容を反映、言語切替リンク |
| `README.en.md`（新規） | 英語版 |
| `CLI_STAGE2_DESIGN.md` | 本書（実装後に「決定事項」「実装で判明したこと」を追記） |

### 10.2 実装順序（各ステップで全テスト緑を保ってコミット）

1. `genres/` への移動＋ `discover()` ＋登録時の検査（生成結果が変わらないことを回帰テストで確認）
2. 引数なしで usage
3. `--genre random` / `r`
4. `--version` / `-v`
5. README（日本語版の更新 → 英語版の作成）

---

## 11. 実装で判明したこと

1. **`discover()` の WARNING はテストの実行順に影響される**: `cli.main` が `mod_weaver` ロガーを `propagate=False`＋独自ハンドラに
   するため、その後に caplog で WARNING を捕まえるテストは失敗する。`test_registry.py` では既存の `test_engine.py` と同じく
   ロガーを元に戻すフィクスチャを使う。
2. **`orchestral` の seed 11 は検査 WARNING（V15: 左右の同時合計音量が上限超過）を出す**。第２段階の変更前（main）でも同じで、
   本段階とは無関係の既存の挙動。`--genre random` のテストは選ばれるジャンルが変わるため stderr が空であることを求めない。
   V15 自体の扱いは本段階の範囲外（必要なら別途検討）。
3. **README の実行例のバナーが実際と違っていた**: 表示名は `ModWeaver: Nostalgic` ではなく `ModWeaver: TwilightPad Procedural`。
   OpenMPT の Tip にあった「BPM 92」も曲ごとに変わるので一般的な書き方に直した。
