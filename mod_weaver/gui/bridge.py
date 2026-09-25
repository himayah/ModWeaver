"""GUI と CLI の橋渡し（DESIGN.md §12.2）。tkinter を import しない（画面なしでテストできるように）。

GUI は ``mod_weaver`` の内部を直接呼ばず、CLI（``modweaver.py``）を子プロセスとして起動する。
CLI で選べるもの（ジャンル・形式・テンポ・チャンネル数）は起動時に ``--list-genres --json`` で受け取り、
生成結果は ``--json`` で受け取る。GUI 側にジャンル名や数を書き込まない。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional, Sequence

ROOT = Path(__file__).resolve().parents[2]
CLI_SCRIPT = ROOT / "modweaver.py"
DEFAULT_OUTPUT_DIR = ROOT / "output"

# CLI の終了コード（DESIGN.md §8.7）→ GUI の文言キー
EXIT_KINDS = {2: "exit_args", 3: "exit_generate", 4: "exit_output", 5: "exit_ffmpeg", 1: "exit_unexpected"}


# ------------------------------------------------------------
# CLI から受け取るデータ
# ------------------------------------------------------------

@dataclass(frozen=True)
class Genre:
    id: str
    display_name: str
    category: str
    aliases: tuple[str, ...]
    description: str
    description_en: str
    tempo_range: tuple[int, int]
    channel_choices: tuple[int, ...]

    def describe(self, lang: str) -> str:
        return self.description_en if lang == "en" else self.description


@dataclass(frozen=True)
class Catalog:
    """``--list-genres --json`` の内容（DESIGN.md §8.8）。"""
    version: str
    url: str
    default_genre: str
    random_genre: str                  # --genre に渡すランダム指定（"random"）
    default_format: str
    formats: tuple[tuple[str, str], ...]          # (name, extension)
    tempo_min: int
    tempo_max: int
    channels: tuple[int, ...]
    categories: tuple[tuple[str, str, str], ...]  # (id, ja, en)
    genres: tuple[Genre, ...]
    mp3_available: bool
    mp3_error: Optional[str]

    @classmethod
    def from_json(cls, data: dict) -> "Catalog":
        return cls(
            version=data["version"],
            url=data["url"],
            default_genre=data["default_genre"],
            random_genre=data["random_genre"][0],
            default_format=data["default_format"],
            formats=tuple((f["name"], f["extension"]) for f in data["formats"]),
            tempo_min=data["tempo"]["min"],
            tempo_max=data["tempo"]["max"],
            channels=tuple(data["channels"]),
            categories=tuple((c["id"], c["ja"], c["en"]) for c in data["categories"]),
            genres=tuple(
                Genre(g["id"], g["display_name"], g["category"], tuple(g["aliases"]), g["description"],
                      g["description_en"], tuple(g["tempo_range"]), tuple(g["channel_choices"]))
                for g in data["genres"]
            ),
            mp3_available=data["mp3"]["available"],
            mp3_error=data["mp3"]["error"],
        )

    def genre(self, genre_id: str) -> Optional[Genre]:
        return next((g for g in self.genres if g.id == genre_id), None)

    def category_label(self, category: str, lang: str) -> str:
        for cid, ja, en in self.categories:
            if cid == category:
                return en if lang == "en" else ja
        return category

    def extension(self, fmt: str) -> str:
        return dict(self.formats).get(fmt, "." + fmt)

    def is_full_tempo_range(self, genre: Genre) -> bool:
        """ジャンルのテンポ範囲が CLI の全域（＝ジャンルによる制限なし）か。"""
        return genre.tempo_range == (self.tempo_min, self.tempo_max)


@dataclass(frozen=True)
class SongResult:
    """生成 1 回ぶんの ``--json`` の結果（DESIGN.md §8.8）。"""
    genre: str
    display_name: str
    random_genre: bool
    format: str
    seed: int
    bpm: int
    tempo_request: Optional[str]
    channels: int
    channels_request: Optional[int]
    summary: tuple[str, ...]
    path: Path
    repro: str

    @classmethod
    def from_json(cls, data: dict) -> "SongResult":
        return cls(data["genre"], data["display_name"], data["random_genre"], data["format"], data["seed"],
                   data["bpm"], data["tempo_request"], data["channels"], data["channels_request"],
                   tuple(data["summary"]), Path(data["path"]), data["repro"])


# ------------------------------------------------------------
# GUI の設定 → CLI の引数
# ------------------------------------------------------------

@dataclass(frozen=True)
class Request:
    """1 回の生成の指定。``None`` は「CLI（ジャンル）に任せる」。"""
    genre: Optional[str]               # None ならランダム
    seed: Optional[int] = None
    fmt: Optional[str] = None
    tempo: Optional[tuple[int, int]] = None   # (lo, hi)。固定なら lo == hi
    channels: Optional[int] = None
    output_dir: Optional[Path] = None


def build_args(req: Request, catalog: Catalog) -> list[str]:
    """``Request`` を CLI の引数列にする（``python`` と ``modweaver.py`` は含まない）。常に ``--json``。"""
    args = ["--genre", req.genre if req.genre is not None else catalog.random_genre]
    if req.seed is not None:
        args += ["--seed", str(req.seed)]
    if req.fmt is not None and req.fmt != catalog.default_format:
        args += ["--format", req.fmt]
    if req.tempo is not None:
        lo, hi = req.tempo
        args += ["--tempo", str(lo) if lo == hi else f"{lo}-{hi}"]
    if req.channels is not None:
        args += ["--channels", str(req.channels)]
    if req.output_dir is not None:
        args += ["--output-dir", str(req.output_dir)]
    args.append("--json")
    return args


def replay_request(song: SongResult, fmt: str, output_dir: Optional[Path]) -> Request:
    """生成済みの曲を別の形式で書き出す指定。再現コマンドと同じく、テンポは指定があったときだけ確定値、
    チャンネル数は指定があったときだけ渡す（指定しなければ seed で同じになる。DESIGN.md §8.6）。"""
    tempo = (song.bpm, song.bpm) if song.tempo_request is not None else None
    return Request(song.genre, song.seed, fmt, tempo, song.channels_request, output_dir)


def parse_int(text: str) -> Optional[int]:
    """整数（負も可）。空や不正は None。"""
    text = text.strip()
    try:
        return int(text)
    except ValueError:
        return None


def parse_tempo(lo_text: str, hi_text: str, catalog: Catalog) -> Optional[tuple[int, int]]:
    """テンポ入力の検査。範囲外・逆順・不正は None。"""
    lo, hi = parse_int(lo_text), parse_int(hi_text)
    if lo is None or hi is None:
        return None
    if not catalog.tempo_min <= lo <= hi <= catalog.tempo_max:
        return None
    return lo, hi


# ------------------------------------------------------------
# 子プロセス
# ------------------------------------------------------------

def python_executable() -> str:
    """CLI を起動する Python。pythonw.exe（コンソールなし）で動いているときは隣の python.exe を使う
    （pythonw は標準出力を持たないことがある。コンソール窓は CREATE_NO_WINDOW で出さない）。"""
    exe = Path(sys.executable)
    if exe.name.lower() == "pythonw.exe":
        console = exe.with_name("python.exe")
        if console.exists():
            return str(console)
    return str(exe)


def command(args: Sequence[str]) -> list[str]:
    return [python_executable(), str(CLI_SCRIPT), *args]


def popen_kwargs() -> dict:
    env = dict(os.environ)
    env["PYTHONUTF8"] = "1"            # stderr のエラー文も UTF-8 で（Windows のパイプ既定は cp932）
    env["PYTHONIOENCODING"] = "utf-8"
    kwargs: dict = {"stdout": subprocess.PIPE, "stderr": subprocess.PIPE, "stdin": subprocess.DEVNULL,
                    "text": True, "encoding": "utf-8", "errors": "replace", "env": env, "cwd": str(ROOT)}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    return kwargs


@dataclass
class Outcome:
    """CLI を 1 回動かした結果。``cancelled`` は中止ボタンで止めたとき。"""
    args: list[str]
    code: Optional[int]
    stdout: str = ""
    stderr: str = ""
    cancelled: bool = False
    error: Optional[str] = None        # 起動できなかったとき（Python が見つからない等）

    @property
    def ok(self) -> bool:
        return self.code == 0 and not self.cancelled and self.error is None

    def json(self) -> dict:
        return json.loads(self.stdout)


def run(args: Sequence[str], timeout: Optional[float] = None) -> Outcome:
    """CLI を同期で動かす（起動時のジャンル一覧・ヘルプ用）。"""
    try:
        proc = subprocess.run(command(args), timeout=timeout, **popen_kwargs())
    except (OSError, subprocess.SubprocessError) as e:
        return Outcome(list(args), None, error=str(e))
    return Outcome(list(args), proc.returncode, proc.stdout, proc.stderr)


def load_catalog() -> Catalog:
    """起動時に CLI で選べるものを読む。失敗は RuntimeError（メッセージに CLI の stderr を入れる）。"""
    out = run(["--list-genres", "--json"], timeout=120)
    if not out.ok:
        raise RuntimeError(out.error or out.stderr.strip() or f"exit code {out.code}")
    return Catalog.from_json(out.json())


@dataclass
class Job:
    """生成 1 回ぶんの子プロセス。別スレッドで待ち、終わったら ``on_done(Outcome)`` を呼ぶ
    （呼ばれるのは待ち受けスレッド。GUI 側はキューなどで画面のスレッドへ渡す）。"""
    args: list[str]
    on_done: Callable[[Outcome], None]
    _proc: Optional[subprocess.Popen] = field(default=None, repr=False)
    _cancelled: bool = False
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def start(self) -> "Job":
        threading.Thread(target=self._run, daemon=True).start()
        return self

    def _run(self) -> None:
        try:
            with self._lock:
                if self._cancelled:
                    self.on_done(Outcome(self.args, None, cancelled=True))
                    return
                self._proc = subprocess.Popen(command(self.args), **popen_kwargs())
            stdout, stderr = self._proc.communicate()
        except OSError as e:
            self.on_done(Outcome(self.args, None, error=str(e)))
            return
        self.on_done(Outcome(self.args, self._proc.returncode, stdout, stderr, cancelled=self._cancelled))

    def cancel(self) -> None:
        with self._lock:
            self._cancelled = True
            if self._proc is not None and self._proc.poll() is None:
                self._proc.kill()


# ------------------------------------------------------------
# OS の関連付けアプリ・ファイルマネージャ
# ------------------------------------------------------------

def open_file(path: Path) -> None:
    """OS の既定アプリで開く。関連付けが無い等で開けなければ OSError。"""
    p = str(Path(path).resolve())
    if sys.platform == "win32":
        os.startfile(p)  # type: ignore[attr-defined]   # 関連付けが無ければ OSError
        return
    opener = "open" if sys.platform == "darwin" else "xdg-open"
    proc = subprocess.run([opener, p], capture_output=True, text=True)
    if proc.returncode != 0:
        raise OSError(proc.stderr.strip() or f"{opener} exit code {proc.returncode}")


def reveal_command(path: Path) -> list[str]:
    """ファイルを選んだ状態でファイルマネージャを開くコマンド（フォルダならそのフォルダを開く）。"""
    p = Path(path).resolve()
    if sys.platform == "win32":
        return ["explorer", f"/select,{p}"] if p.is_file() else ["explorer", str(p)]
    if sys.platform == "darwin":
        return ["open", "-R", str(p)] if p.is_file() else ["open", str(p)]
    return ["xdg-open", str(p.parent if p.is_file() else p)]


def reveal(path: Path) -> None:
    subprocess.Popen(reveal_command(path), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
