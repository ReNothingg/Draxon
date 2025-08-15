from typing import Any, Callable, Dict
import yt_dlp

def download_media(
    url: str,
    ydl_opts: Dict[str, Any],
    progress_hook: Callable[[Dict[str, Any]], None],
) -> None:
    ydl_opts["progress_hooks"] = [progress_hook]
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

def get_info(url: str) -> Dict[str, Any]:
    ydl_opts = {"quiet": True, "no_warnings": True, "extract_flat": "in_playlist"}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        return ydl.extract_info(url, download=False)