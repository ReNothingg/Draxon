from typing import Any, Dict
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.reactive import reactive
from textual.widgets import Button, Label, ProgressBar, Static

class Header(Static):
    def __init__(self, show_title: bool = True) -> None:
        self.show_title = show_title
        super().__init__()

    def compose(self) -> ComposeResult:
        if self.show_title:
            yield Label("Draxon Downloader", id="app-title")

class Footer(Static):
    status_text = reactive("Ready")
    status_class = reactive("info")

    def set_status(self, text: str, level: str = "info") -> None:
        self.status_text = text
        self.status_class = level

    def render(self) -> str:
        return f"[{self.status_class}]{self.status_text}[/]"

class PathSelector(Static):
    current_path = reactive("")

    def __init__(self, initial_path: str) -> None:
        super().__init__()
        self.current_path = initial_path

    def compose(self) -> ComposeResult:
        with Horizontal():
            yield Label("Save to:", id="path-label")
            yield Label(self.current_path, id="path-display")
            yield Button("Change", id="change-path-button")

    def update_path(self, new_path: str) -> None:
        self.current_path = new_path
        self.query_one("#path-display", Label).update(new_path)

class DownloadProgress(Static):
    def __init__(self) -> None:
        super().__init__()
        self.eta_label = Label("ETA: -")
        self.speed_label = Label("Speed: -")
        self.size_label = Label("Size: -")
        self.progress_bar = ProgressBar(total=100, show_eta=False, show_percentage=True)

    def compose(self) -> ComposeResult:
        yield self.progress_bar
        with Horizontal():
            yield self.eta_label
            yield self.speed_label
            yield self.size_label

    def update_progress(self, data: Dict[str, Any]) -> None:
        if data.get("total_bytes"):
            downloaded = data.get("downloaded_bytes", 0)
            total = data.get("total_bytes", 1)
            progress = (downloaded / total) * 100
            self.progress_bar.update(progress=progress)
            self.size_label.update(
                f"Size: {data.get('_total_bytes_str', 'N/A')} / {data.get('_downloaded_bytes_str', 'N/A')}"
            )
        else:
            self.size_label.update("Size: N/A")

        self.eta_label.update(f"ETA: {data.get('_eta_str', '-')}")
        self.speed_label.update(f"Speed: {data.get('_speed_str', '-')}")

    def reset(self) -> None:
        self.progress_bar.update(progress=0)
        self.eta_label.update("ETA: -")
        self.speed_label.update("Speed: -")
        self.size_label.update("Size: -")

class QueuePanel(Static):
    def compose(self) -> ComposeResult:
        yield Label("Download Queue (Playlists)", id="queue-title")

class LogPanel(Static):
    def compose(self) -> ComposeResult:
        yield Label("Logs", id="log-title")