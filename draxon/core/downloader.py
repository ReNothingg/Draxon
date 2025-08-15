import threading
from typing import Any, Callable, Dict, List
from textual.worker import Worker, get_worker
import yt_dlp

class DownloadJob:
    def __init__(
        self,
        url: str,
        ydl_opts: Dict[str, Any],
        progress_hook: Callable[[Dict[str, Any]], None],
    ):
        self.url = url
        self.ydl_opts = ydl_opts
        self.ydl_opts["progress_hooks"] = [progress_hook]
        self.cancel_event = threading.Event()

    def run(self) -> None:
        with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
            ydl.download([self.url])

class Downloader:
    def __init__(self) -> None:
        self._current_job: DownloadJob | None = None
        self._worker: Worker | None = None

    def download(
        self,
        url: str,
        ydl_opts: Dict[str, Any],
        progress_hook: Callable[[Dict[str, Any]], None],
    ) -> None:
        if self.is_running():
            return

        self._current_job = DownloadJob(url, ydl_opts, progress_hook)
        self._worker = get_worker()
        self._worker.run(self._current_job.run)

    def cancel(self) -> None:
        if self._current_job and self.is_running():
            self._current_job.cancel_event.set()
            if self._worker:
                self._worker.cancel()
            self._current_job = None
            self._worker = None

    def is_running(self) -> bool:
        return self._worker is not None and self._worker.is_running

    @staticmethod
    def get_info(url: str) -> Dict[str, Any]:
        ydl_opts = {"quiet": True, "no_warnings": True, "extract_flat": "in_playlist"}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(url, download=False)