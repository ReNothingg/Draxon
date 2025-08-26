from __future__ import annotations

import argparse
import concurrent.futures
import json
import logging
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from typing import Dict, Optional, Any, List, Tuple

try:
    import yt_dlp
except Exception:
    print("Install yt-dlp: pip install yt-dlp")
    raise

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    DownloadColumn,
    TransferSpeedColumn,
    TimeRemainingColumn,
)
from rich.prompt import Prompt, Confirm
from rich.markdown import Markdown

APP_NAME = "Draxon"
CONFIG_FILE = Path.home() / ".draxon.json"
DEFAULT_CONFIG = {
    "output_dir": str(Path.cwd()),
    "output_template": "%(title)s.%(ext)s",
    "video_format": "best",
    "subtitles_languages": "en,ru",
    "proxy": "",
    "rate_limit": "",
    "resume_download": True,
    "verbose": False,
    "log_to_file": False,
    "log_file": str(Path.cwd() / "draxon.log"),
    "parallel_download": False,
    "max_workers": 2,
    "profiles": {
        "default": {}
    }
}

console = Console()
_shutdown = threading.Event()

URL_PATTERN = re.compile(r"https?://[^\s'\"<>]+", re.IGNORECASE)

def load_config() -> Dict[str, Any]:
    if CONFIG_FILE.exists():
        try:
            cfg = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            merged = {**DEFAULT_CONFIG, **cfg}
            if "profiles" not in merged or not isinstance(merged["profiles"], dict):
                merged["profiles"] = {"default": {}}
            return merged
        except Exception as e:
            console.print(f"[red]Не удалось загрузить конфиг: {e} — использую defaults[/red]")
            return DEFAULT_CONFIG.copy()
    return DEFAULT_CONFIG.copy()

def save_config(cfg: Dict[str, Any]) -> None:
    try:
        CONFIG_FILE.write_text(json.dumps(cfg, indent=4, ensure_ascii=False), encoding="utf-8")
        console.print(f"[green]Настройки сохранены в {CONFIG_FILE}[/green]")
    except Exception as e:
        console.print(f"[red]Ошибка сохранения конфига: {e}[/red]")

def is_termux() -> bool:
    return bool(os.environ.get("TERMUX_VERSION")) or Path("/data/data/com.termux").exists()

def termux_clipboard_get() -> Optional[str]:
    try:
        res = subprocess.run(["termux-clipboard-get"], capture_output=True, text=True, timeout=3)
        if res.returncode == 0:
            return res.stdout
    except Exception:
        pass
    return None

def read_stdin_if_pipe() -> Optional[str]:
    if not sys.stdin or sys.stdin.isatty():
        return None
    try:
        return sys.stdin.read()
    except Exception:
        return None

def parse_urls_from_text(text: str) -> List[str]:
    found = URL_PATTERN.findall(text or "")
    cleaned = []
    seen = set()
    for u in found:
        u = u.strip().rstrip(').,;?!"\'')
        if u and u not in seen:
            seen.add(u)
            cleaned.append(u)
    return cleaned

def is_valid_url(u: str) -> bool:
    return u.startswith("http://") or u.startswith("https://")

def edit_list_in_editor(items: List[str]) -> List[str]:
    editor = os.environ.get("EDITOR") or shutil.which("nano") or shutil.which("vi") or "vi"
    with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".txt") as tf:
        path = tf.name
        tf.write("\n".join(items))
        tf.flush()
    try:
        subprocess.run([editor, path])
    except Exception as e:
        console.print(f"[yellow]Не удалось открыть редактор {editor}: {e}[/yellow]")
    try:
        content = Path(path).read_text(encoding="utf-8")
        os.unlink(path)
        lines = [line.rstrip() for line in content.splitlines()]
        return lines
    except Exception as e:
        console.print(f"[yellow]Ошибка чтения временного файла: {e}[/yellow]")
        return items

def parse_url_spec(token: str) -> Tuple[str, Dict[str, Any]]:
    parts = token.split("||", 1)
    url = parts[0].strip()
    overrides: Dict[str, Any] = {}
    if len(parts) == 2:
        spec = parts[1].strip()
        if spec:
            for item in spec.split(","):
                item = item.strip()
                if not item:
                    continue
                if "=" in item:
                    k, v = item.split("=", 1)
                    overrides[k.strip()] = v.strip()
                else:
                    if item.lower() in ("audio", "extract_audio"):
                        overrides["audio"] = True
                    elif item.lower() in ("no-audio", "noaudio"):
                        overrides["audio"] = False
                    elif item.lower() in ("playlist", "play"):
                        overrides["playlist"] = True
                    elif item.lower() in ("no-playlist", "noplay"):
                        overrides["playlist"] = False
                    else:
                        overrides[item] = True
    return url, overrides

# -------------------------
# Signal handler
# -------------------------
def _signal_handler(sig, frame):
    _shutdown.set()
    console.print("\n[bold yellow]Прервано пользователем (Ctrl-C). Останавливаю...[/bold yellow]")

signal.signal(signal.SIGINT, _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)

# -------------------------
# Download manager (progress)
# -------------------------
class DownloadManager:
    def __init__(self, base_opts: Dict[str, Any], max_workers: int = 2):
        self.base_opts = base_opts
        self.max_workers = max_workers
        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.fields[title]}", justify="left"),
            BarColumn(bar_width=None),
            DownloadColumn(),
            TransferSpeedColumn(),
            TimeRemainingColumn(),
            expand=True,
            console=console,
        )
        self._task_map = {}
        self._task_lock = threading.Lock()

    def _progress_hook(self, d: Dict[str, Any]):
        if _shutdown.is_set():
            return
        status = d.get("status")
        info = d.get("info_dict") or {}
        key = info.get("id") or info.get("url") or d.get("filename") or d.get("tmpfilename") or str(info.get("webpage_url","")) or str(id(d))
        with self._task_lock:
            task_id = self._task_map.get(key)
            if status == "downloading":
                downloaded = d.get("downloaded_bytes") or 0
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or None
                title = info.get("title") or info.get("id") or key
                if task_id is None:
                    task_id = self.progress.add_task("", title=title, total=total)
                    self._task_map[key] = task_id
                try:
                    if total:
                        self.progress.update(task_id, completed=downloaded, total=total)
                    else:
                        self.progress.update(task_id, completed=downloaded)
                except Exception:
                    pass
            elif status == "finished":
                if task_id is None:
                    task_id = self.progress.add_task("", title=info.get("title", key), total=0)
                    self._task_map[key] = task_id
                try:
                    self.progress.update(task_id, completed=self.progress.tasks[task_id].total or 0)
                    self.progress.stop_task(task_id)
                except Exception:
                    pass
            elif status == "error":
                if task_id:
                    try:
                        self.progress.stop_task(task_id)
                    except Exception:
                        pass

    def _build_opts(self, extra: Dict[str, Any]) -> Dict[str, Any]:
        opts = dict(self.base_opts)
        opts.update(extra)
        hooks = opts.get("progress_hooks", [])
        hooks = [h for h in hooks if h != self._progress_hook]
        hooks.append(self._progress_hook)
        opts["progress_hooks"] = hooks
        return opts

    def _run_single(self, url: str, opts: Dict[str, Any]):
        if _shutdown.is_set():
            return
        try:
            logging.info("Start: %s", url)
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([url])
        except Exception:
            logging.exception("Ошибка при скачивании %s", url)

    def download(self, jobs: List[Tuple[str, Dict[str, Any]]], parallel: bool = False):
        if parallel and len(jobs) > 1:
            console.print(f"[magenta]Параллельный режим: {self.max_workers} потоков[/magenta]")
            with self.progress:
                with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as exe:
                    futs = []
                    for url, overrides in jobs:
                        if _shutdown.is_set(): break
                        opts = self._build_opts(overrides)
                        futs.append(exe.submit(self._run_single, url, opts))
                    try:
                        for fut in concurrent.futures.as_completed(futs):
                            if _shutdown.is_set(): break
                            if exc := fut.exception():
                                logging.exception("Task error: %s", exc)
                    except KeyboardInterrupt:
                        _shutdown.set()
        else:
            with self.progress:
                for url, overrides in jobs:
                    if _shutdown.is_set(): break
                    opts = self._build_opts(overrides)
                    self._run_single(url, opts)

# -------------------------
# UI and input logic
# -------------------------
BANNER = r"""
██████╗ ██████╗  █████╗ ███████╗██╗  ██╗ ██████╗ ███╗   ██╗
██╔══██╗██╔══██╗██╔══██╗██╔════╝██║  ██║██╔═══██╗████╗  ██║
██████╔╝██████╔╝███████║███████╗███████║██║   ██║██╔██╗ ██║
██╔═══╝ ██╔══██╗██╔══██║╚════██║██╔══██║██║   ██║██║╚██╗██║
██║     ██║  ██║██║  ██║███████║██║  ██║╚██████╔╝██║ ╚████║
╚═╝     ╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═══╝
"""

def print_header(cfg: Dict[str, Any], profile_name: str):
    header = Panel.fit(
        f"[bold white]{APP_NAME}[/bold white] — flexible profiles · Termux: {'yes' if is_termux() else 'no'}\n"
        f"[dim]Config: [yellow]{CONFIG_FILE}[/yellow] · Profile: [bold green]{profile_name}[/bold green][/dim]",
        title="Draxon",
        border_style="bright_blue",
    )
    console.print(BANNER, style="cyan")
    console.print(header)
    t = Table.grid(expand=True)
    t.add_column("Key", ratio=1, style="bold")
    t.add_column("Value", ratio=3)
    t.add_row("[cyan]output_dir[/cyan]", f"{cfg['output_dir']}")
    t.add_row("[cyan]video_format[/cyan]", f"{cfg['video_format']}")
    t.add_row("[cyan]subtitles[/cyan]", f"{cfg['subtitles_languages']}")
    t.add_row("[cyan]parallel[/cyan]", f"{cfg['parallel_download']} (max {cfg['max_workers']})")
    console.print(Panel(t, title="Active settings (profile merged)", border_style="green"))

def smart_input_and_profiles(cfg: Dict[str, Any], cli_args: argparse.Namespace) -> Tuple[List[Tuple[str, Dict[str, Any]]], Dict[str, Any], str]:
    profiles = cfg.get("profiles", {"default": {}})
    profile_names = list(profiles.keys())
    console.print("[bold]Profiles available:[/bold] " + ", ".join(profile_names))
    profile_name = "default"
    cli_profile = getattr(cli_args, "profile", None)
    if cli_profile and cli_profile in profiles:
        profile_name = cli_profile
    else:
        if Confirm.ask("Выбрать профиль? (если нет — будет 'default')", default=False):
            choice = Prompt.ask("Имя профиля (или new для создания)", default="default")
            if choice == "new":
                new_name = Prompt.ask("Введите имя нового профиля", default="my")
                profiles.setdefault(new_name, {})
                base_profile = {k: v for k, v in cfg.items() if k != "profiles"}
                profiles[new_name] = base_profile
                cfg["profiles"] = profiles
                profile_name = new_name
                console.print(f"[green]Создан профиль {new_name} (скопированы текущие настройки).[/green]")
            elif choice in profiles:
                profile_name = choice
            else:
                console.print("[yellow]Профиль не найден — будет 'default'[/yellow]")

    active_profile = profiles.get(profile_name, {})
    active_cfg = {**DEFAULT_CONFIG, **cfg}
    active_cfg.update(active_profile)

    console.print("[bold]Текущий профиль (merged):[/bold]")
    tbl = Table("Key", "Value", show_header=True, header_style="bold magenta")
    for k in ("output_dir", "output_template", "video_format", "subtitles_languages", "proxy", "rate_limit", "resume_download", "parallel_download", "max_workers"):
        tbl.add_row(k, str(active_cfg.get(k)))
    console.print(tbl)

    if Confirm.ask("Отредактировать профиль сейчас (ввести новые значения)?", default=False):
        od = Prompt.ask("output_dir", default=str(active_cfg.get("output_dir")))
        active_cfg["output_dir"] = od
        active_cfg["output_template"] = Prompt.ask("output_template", default=str(active_cfg.get("output_template")))
        active_cfg["video_format"] = Prompt.ask("video_format", default=str(active_cfg.get("video_format")))
        active_cfg["subtitles_languages"] = Prompt.ask("subtitles_languages", default=str(active_cfg.get("subtitles_languages")))
        active_cfg["proxy"] = Prompt.ask("proxy", default=str(active_cfg.get("proxy")))
        active_cfg["rate_limit"] = Prompt.ask("rate_limit", default=str(active_cfg.get("rate_limit")))
        active_cfg["resume_download"] = Confirm.ask("resume_download", default=bool(active_cfg.get("resume_download")))
        active_cfg["parallel_download"] = Confirm.ask("parallel_download", default=bool(active_cfg.get("parallel_download")))
        try:
            active_cfg["max_workers"] = int(Prompt.ask("max_workers", default=str(active_cfg.get("max_workers"))))
        except Exception:
            pass
        if Confirm.ask(f"Сохранить изменения в профиль '{profile_name}'?", default=False):
            cfg["profiles"][profile_name] = {k: v for k, v in active_cfg.items() if k != "profiles"}
            save_config(cfg)

    urls_raw: List[str] = []

    piped = read_stdin_if_pipe()
    if piped:
        console.print("[green]Получен ввод через stdin/pipe — парсю ссылки...[/green]")
        urls_raw = parse_urls_from_text(piped)

    if not urls_raw and is_termux():
        cb = termux_clipboard_get()
        if cb:
            parsed = parse_urls_from_text(cb)
            if parsed:
                console.print(f"[green]Найдено {len(parsed)} URL в Termux clipboard[/green]")
                if Confirm.ask("Использовать ссылки из clipboard?", default=True):
                    urls_raw = parsed

    if not urls_raw and getattr(cli_args, "file", None):
        p = Path(cli_args.file).expanduser()
        if p.exists():
            txt = p.read_text(encoding="utf-8")
            parsed = parse_urls_from_text(txt)
            console.print(f"[green]Загружено {len(parsed)} URL из файла {p}[/green]")
            urls_raw = parsed

    if not urls_raw and getattr(cli_args, "urls", None):
        for token in cli_args.urls:
            url, _ = parse_url_spec(token)
            if is_valid_url(url):
                urls_raw.append(token)

    if not urls_raw:
        console.print(Markdown("**Вставь/введи ссылки** (любой текст — ссылки будут извлечены). Можно открыть редактор."))
        mode = Prompt.ask("Ввод: (paste/editor/file/quit)", choices=["paste","editor","file","quit"], default="paste")
        if mode == "quit":
            return [], active_cfg, profile_name
        if mode == "file":
            path = Prompt.ask("Путь к файлу с URL", default="")
            p = Path(path).expanduser()
            if p.exists():
                urls_raw = parse_urls_from_text(p.read_text(encoding="utf-8"))
                console.print(f"[green]Загружено {len(urls_raw)} URL из {p}[/green]")
            else:
                console.print("[red]Файл не найден[/red]")
        elif mode == "editor":
            initial = ["# Впиши ссылки (одну на строку). Для per-url overrides используй формат: URL||flag,key=val"]
            edited = edit_list_in_editor(initial)
            for line in edited:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                urls_raw.append(line)
            console.print(f"[green]Получено {len(urls_raw)} строк из редактора[/green]")
        else:
            pasted = Prompt.ask("Вставь текст (или оставь пустым для отмены)", default="")
            if pasted:
                tokens = pasted.splitlines() if "\n" in pasted else pasted.split()
                for t in tokens:
                    t = t.strip()
                    if not t:
                        continue
                    found = parse_urls_from_text(t)
                    if found:
                        urls_raw.append(t)
                console.print(f"[green]Найдено {len(urls_raw)} candidate строк[/green]")

    jobs: List[Tuple[str, Dict[str, Any]]] = []
    cleaned_urls = []
    for token in urls_raw:
        token = token.strip()
        if not token:
            continue
        url, overrides = parse_url_spec(token)
        if not is_valid_url(url):
            found = parse_urls_from_text(token)
            if found:
                url = found[0]
            else:
                console.print(f"[yellow]Пропущен невалидный токен: {token}[/yellow]")
                continue
        cleaned_urls.append((url, overrides))

    if not cleaned_urls:
        console.print("[red]Нет валидных URL — выхожу.[/red]")
        return [], active_cfg, profile_name

    tbl = Table("№", "URL", "Overrides", show_header=True, header_style="bold magenta")
    for i, (u, ov) in enumerate(cleaned_urls, 1):
        tbl.add_row(str(i), u, json.dumps(ov, ensure_ascii=False) if ov else "-")
    console.print(tbl)

    if Confirm.ask("Открыть список в редакторе для правки (удалить/добавить/править overrides)?", default=False):
        lines = [f"{u}||{','.join([f'{k}={v}' if not isinstance(v, bool) else (k if v else f'no-{k}') for k,v in ov.items()])}" if ov else u for u,ov in cleaned_urls]
        edited = edit_list_in_editor(lines)
        cleaned_urls = []
        for ln in edited:
            ln = ln.strip()
            if not ln or ln.startswith("#"):
                continue
            u, ov = parse_url_spec(ln)
            if is_valid_url(u):
                cleaned_urls.append((u, ov))
        if not cleaned_urls:
            console.print("[red]После редактирования не осталось URL — отмена.[/red]")
            return [], active_cfg, profile_name

    console.print(f"\n[bold]Готово к скачиванию {len(cleaned_urls)} URL[/bold]")
    if not Confirm.ask("Начать загрузку?", default=True):
        console.print("[yellow]Отменено пользователем[/yellow]")
        return [], active_cfg, profile_name

    jobs = []
    for url, ov in cleaned_urls:
        job_overrides: Dict[str, Any] = {}
        if active_cfg.get("video_format"):
            job_overrides["format"] = active_cfg.get("video_format")
        if active_cfg.get("proxy"):
            job_overrides["proxy"] = active_cfg.get("proxy")
        if active_cfg.get("rate_limit"):
            job_overrides["ratelimit_str"] = active_cfg.get("rate_limit")
        if active_cfg.get("resume_download") is not None:
            job_overrides["continuedl"] = bool(active_cfg.get("resume_download"))
        if active_cfg.get("output_template"):
            job_overrides["outtmpl"] = str(Path(active_cfg.get("output_dir", ".")) / active_cfg.get("output_template"))
        if active_cfg.get("subtitles_languages"):
            langs = [l.strip() for l in str(active_cfg.get("subtitles_languages")).split(",") if l.strip()]
            if langs:
                job_overrides["writesubtitles"] = True
                job_overrides["subtitleslangs"] = langs
                job_overrides["subtitlesformat"] = "srt"
        job_overrides["noplaylist"] = not bool(active_cfg.get("playlist", False))

        for k, v in ov.items():
            if k == "audio":
                job_overrides["__audio_flag__"] = bool(v)
            elif k == "format":
                job_overrides["format"] = v
            elif k == "outtmpl":
                job_overrides["outtmpl"] = str(Path(active_cfg.get("output_dir", ".")) / v) if not Path(v).is_absolute() else v
            elif k == "proxy":
                job_overrides["proxy"] = v
            elif k == "rate":
                job_overrides["ratelimit_str"] = v
            elif k == "playlist":
                job_overrides["noplaylist"] = not bool(v)
            else:
                job_overrides[k] = v

        if active_cfg.get("prefer_audio") and "__audio_flag__" not in job_overrides:
            job_overrides["__audio_flag__"] = True

        jobs.append((url, job_overrides))

    return jobs, active_cfg, profile_name

# -------------------------
# Main orchestration
# -------------------------
def parse_rate_limit_to_int(s: Optional[str]) -> Optional[int]:
    if not s:
        return None
    s = str(s).strip().upper()
    m = re.match(r"^(\d+(?:\.\d+)?)([KMG]?)$", s)
    if not m:
        return None
    num, unit = m.groups()
    try:
        val = float(num)
    except Exception:
        return None
    mul = 1
    if unit == "K": mul = 1024
    if unit == "M": mul = 1024**2
    if unit == "G": mul = 1024**3
    return int(val * mul)

def build_ydl_opts_from_job(job_overrides: Dict[str, Any], base_cfg: Dict[str, Any]) -> Dict[str, Any]:
    opts: Dict[str, Any] = {}
    outtmpl = job_overrides.get("outtmpl") or str(Path(base_cfg.get("output_dir", ".")) / base_cfg.get("output_template"))
    opts["outtmpl"] = outtmpl
    if job_overrides.get("format"):
        opts["format"] = job_overrides["format"]
    else:
        opts["format"] = base_cfg.get("video_format", "best")
    opts["noplaylist"] = job_overrides.get("noplaylist", not bool(base_cfg.get("playlist", False)))
    opts["continuedl"] = bool(job_overrides.get("continuedl", base_cfg.get("resume_download", True)))
    if job_overrides.get("proxy"):
        opts["proxy"] = job_overrides.get("proxy")
    elif base_cfg.get("proxy"):
        opts["proxy"] = base_cfg.get("proxy")
    rl_str = job_overrides.get("ratelimit_str") or base_cfg.get("rate_limit")
    rl = parse_rate_limit_to_int(rl_str)
    if rl:
        opts["ratelimit"] = rl
    if job_overrides.get("writesubtitles") or base_cfg.get("subtitles_languages"):
        if job_overrides.get("subtitleslangs"):
            opts["writesubtitles"] = True
            opts["subtitleslangs"] = job_overrides.get("subtitleslangs")
            opts["subtitlesformat"] = job_overrides.get("subtitlesformat", "srt")
        else:
            langs = [l.strip() for l in str(base_cfg.get("subtitles_languages","")).split(",") if l.strip()]
            if langs:
                opts["writesubtitles"] = True
                opts["subtitleslangs"] = langs
                opts["subtitlesformat"] = "srt"
    if job_overrides.get("__audio_flag__"):
        opts["format"] = "bestaudio/best"
        opts["postprocessors"] = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }]
    return opts

def main(argv=None):
    cfg = load_config()

    parser = argparse.ArgumentParser(prog="draxon", description="Draxon downloader — flexible profiles + Termux-friendly input")
    parser.add_argument("--no-tui", action="store_true", help="skip interactive input (use CLI args)")
    parser.add_argument("-u", "--urls", nargs="+", help="URLs (can include per-url overrides: URL||flag,key=val)")
    parser.add_argument("-f", "--file", help="file with URLs")
    parser.add_argument("--profile", help="profile to use (from config profiles)")
    parser.add_argument("--output-dir", help="override output_dir")
    parser.add_argument("--outtmpl", help="override output_template")
    parser.add_argument("--format", dest="video_format", help="override video format")
    parser.add_argument("--audio", action="store_true", help="extract audio for all URLs")
    parser.add_argument("--playlist", action="store_true", help="download playlist")
    parser.add_argument("--subtitles", help="subtitles languages comma-separated")
    parser.add_argument("--proxy", help="proxy")
    parser.add_argument("--rate", help="rate limit string like 500K")
    parser.add_argument("--parallel", action="store_true", help="parallel downloads")
    parser.add_argument("--max-workers", type=int, default=cfg.get("max_workers", 2), help="max threads")
    parser.add_argument("--save-config", action="store_true", help="save merged profile back to config")
    args = parser.parse_args(argv)

    jobs, active_cfg, profile_name = smart_input_and_profiles(cfg, args)

    if not jobs:
        return

    if args.output_dir:
        active_cfg["output_dir"] = args.output_dir
    if args.outtmpl:
        active_cfg["output_template"] = args.outtmpl
    if args.video_format:
        active_cfg["video_format"] = args.video_format
    if args.subtitles:
        active_cfg["subtitles_languages"] = args.subtitles
    if args.proxy:
        active_cfg["proxy"] = args.proxy
    if args.rate:
        active_cfg["rate_limit"] = args.rate
    if args.parallel:
        active_cfg["parallel_download"] = True
        active_cfg["max_workers"] = args.max_workers
    if args.audio:
        active_cfg["prefer_audio"] = True

    final_jobs: List[Tuple[str, Dict[str, Any]]] = []
    for url, job_ov in jobs:
        if args.audio and "__audio_flag__" not in job_ov:
            job_ov["__audio_flag__"] = True
        ydl_opts = build_ydl_opts_from_job(job_ov, active_cfg)
        final_jobs.append((url, ydl_opts))

    log_level = logging.DEBUG if active_cfg.get("verbose") else logging.INFO
    handlers = [logging.StreamHandler(sys.stdout)]
    if active_cfg.get("log_to_file"):
        try:
            handlers.append(logging.FileHandler(active_cfg.get("log_file"), encoding="utf-8"))
        except Exception:
            console.print("[yellow]Не удалось открыть лог-файл — продолжаю без него[/yellow]")
    logging.basicConfig(level=log_level, format="%(asctime)s - %(levelname)s - %(message)s", handlers=handlers)

    need_ffmpeg = any(job[1].get("postprocessors") for job in final_jobs)
    if need_ffmpeg and shutil.which("ffmpeg") is None:
        if is_termux():
            console.print("[yellow]ffmpeg не найден. В Termux: pkg install ffmpeg[/yellow]")
        else:
            console.print("[yellow]ffmpeg не найден в PATH — извлечение аудио не будет работать[/yellow]")

    manager = DownloadManager(base_opts={}, max_workers=active_cfg.get("max_workers", 2))

    console.clear()
    print_header(active_cfg, profile_name)
    console.print(f"[bold]Начинаю скачивание {len(final_jobs)} файлов (parallel={active_cfg.get('parallel_download')})[/bold]")

    try:
        manager.download(final_jobs, parallel=bool(active_cfg.get("parallel_download")))
    except Exception:
        logging.exception("Critical download error")
    finally:
        if _shutdown.is_set():
            console.print("[yellow]Остановлено пользователем[/yellow]")
        else:
            console.print("[green]Готово — все задания завершены[/green]")

    if args.save_config:
        cfg.setdefault("profiles", {})
        cfg["profiles"][profile_name] = {k: v for k, v in active_cfg.items() if k != "profiles"}
        save_config(cfg)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        console.print(f"[red]Unhandled exception: {e}[/red]")
        raise
