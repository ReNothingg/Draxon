from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import (
    Button,
    DirectoryTree,
    Input,
    Label,
    ListItem,
    ListView,
    Select,
    Static,
)
from textual.worker import Worker, WorkerState

from draxon.core.downloader import download_media, get_info
from draxon.core.formats import FormatInfo, parse_formats
from draxon.core.history import HistoryManager
from draxon.core.settings import SettingsManager
from draxon.ui.widgets import (
    DownloadProgress,
    Footer,
    Header,
    PathSelector,
    QueuePanel,
)

APP_DIR = Path.home() / ".config" / "draxon"
SETTINGS_FILE = APP_DIR / "settings.json"
HISTORY_FILE = APP_DIR / "history.json"

class MainScreen(Screen):
    BINDINGS = [
        Binding("ctrl+o", "select_path", "Path", show=True),
        Binding("ctrl+h", "toggle_history", "History", show=True),
        Binding("enter", "start_download", "Start", show=False),
        Binding("escape", "cancel_download", "Cancel", show=False),
    ]

    class URLInfo(Message):
        def __init__(self, info: Dict[str, Any]) -> None:
            self.info = info
            super().__init__()

    class DownloadUpdate(Message):
        def __init__(self, data: Dict[str, Any]) -> None:
            self.data = data
            super().__init__()

    url_info: reactive[Optional[Dict[str, Any]]] = reactive(None)
    is_downloading = reactive(False)
    is_fetching = reactive(False)
    history_visible = reactive(False)

    def __init__(self) -> None:
        super().__init__()
        self.settings = SettingsManager(SETTINGS_FILE)
        self.history = HistoryManager(HISTORY_FILE)
        self.video_formats: List[FormatInfo] = []
        self.audio_formats: List[FormatInfo] = []

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="main-container"):
            with Vertical(id="left-panel"):
                yield Input(placeholder="Enter URL...", id="url-input")
                yield Button("Check", variant="primary", id="check-button")
                with Horizontal():
                    yield Select(
                        [("Video", "video"), ("Audio", "audio")],
                        value="video",
                        id="type-selector",
                    )
                    yield Select([], id="format-selector", disabled=True)
                yield PathSelector(self.settings.get("download_path"))
                with Horizontal(id="action-buttons"):
                    yield Button("Start", id="start-button", disabled=True)
                    yield Button("Cancel", id="cancel-button", disabled=True)
                yield DownloadProgress()
                yield QueuePanel()
            with Vertical(id="history-panel", classes="-hidden"):
                yield Label("History")
                yield ListView(id="history-list")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one(Footer).set_status("Ready. Enter a URL to begin.")
        self.update_history_list()

    def update_history_list(self) -> None:
        history_list = self.query_one("#history-list", ListView)
        history_list.clear()
        for url in self.history.load():
            history_list.append(ListItem(Label(url)))

    def watch_is_fetching(self, fetching: bool) -> None:
        self.query_one("#check-button").disabled = fetching
        self.query_one("#url-input").disabled = fetching
        self.query_one(Footer).set_status("Fetching info..." if fetching else "Ready.")

    def watch_is_downloading(self, downloading: bool) -> None:
        self.query_one("#start-button").disabled = downloading or not self.url_info
        self.query_one("#cancel-button").disabled = not downloading
        self.query_one("#check-button").disabled = downloading
        self.query_one("#url-input").disabled = downloading
        self.query_one("#type-selector").disabled = downloading
        self.query_one("#format-selector").disabled = downloading

    def watch_url_info(self, info: Optional[Dict[str, Any]]) -> None:
        format_selector = self.query_one("#format-selector", Select)
        if info:
            self.video_formats, self.audio_formats = parse_formats(info)
            self.update_format_selector()
            format_selector.disabled = False
            self.query_one("#start-button").disabled = self.is_downloading
            self.query_one(Footer).set_status(f"Found: {info.get('title', 'N/A')}")
        else:
            format_selector.set_options([])
            format_selector.disabled = True
            self.query_one("#start-button").disabled = True

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "check-button":
            self.fetch_url_info()
        elif event.button.id == "start-button":
            self.action_start_download()
        elif event.button.id == "cancel-button":
            self.action_cancel_download()
        elif event.button.id == "change-path-button":
            self.action_select_path()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "url-input":
            self.fetch_url_info()

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "type-selector":
            self.update_format_selector()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.list_view.id == "history-list":
            url_input = self.query_one("#url-input", Input)
            url_input.value = event.item.children[0].renderable
            self.fetch_url_info()

    def update_format_selector(self) -> None:
        selector = self.query_one("#type-selector", Select)
        format_selector = self.query_one("#format-selector", Select)
        formats = self.video_formats if selector.value == "video" else self.audio_formats
        options: List[Tuple[str, str]] = [(f.label, f.id) for f in formats]
        format_selector.set_options(options)
        if options:
            format_selector.value = options[0][1]

    @work(exclusive=True, group="url_fetch", thread=True)
    def fetch_url_info(self) -> None:
        url = self.query_one("#url-input", Input).value
        if not url:
            self.query_one(Footer).set_status("Error: URL cannot be empty.", "error")
            return

        self.is_fetching = True
        try:
            info = get_info(url)
            self.post_message(self.URLInfo(info))
        except Exception as e:
            self.post_message(self.URLInfo({}))
            self.query_one(Footer).set_status(f"Error: {e}", "error")
        finally:
            self.is_fetching = False

    def on_main_screen_url_info(self, message: URLInfo) -> None:
        if message.info and (message.info.get("formats") or message.info.get("_type") == "playlist"):
            self.url_info = message.info
        else:
            self.url_info = None
            self.query_one(Footer).set_status("Error: Could not get video formats.", "error")

    def progress_hook(self, d: Dict[str, Any]) -> None:
        self.post_message(self.DownloadUpdate(d))

    def on_main_screen_download_update(self, message: DownloadUpdate) -> None:
        d = message.data
        progress_widget = self.query_one(DownloadProgress)
        footer = self.query_one(Footer)

        if d["status"] == "downloading":
            progress_widget.update_progress(d)
        elif d["status"] == "finished":
            self.is_downloading = False
            progress_widget.reset()
            footer.set_status(f"Finished: {Path(d.get('filename', '')).name}", "success")
        elif d["status"] == "error":
            self.is_downloading = False
            progress_widget.reset()
            footer.set_status("Download error.", "error")
            
    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        if event.worker.name == "downloader":
            if event.state == WorkerState.ERROR:
                self.is_downloading = False
                self.query_one(DownloadProgress).reset()
                self.query_one(Footer).set_status(f"Worker error: {event.worker.error}", "error")

    def action_start_download(self) -> None:
        url = self.query_one("#url-input", Input).value
        if not url or not self.url_info:
            self.query_one(Footer).set_status("Error: No URL or info loaded.", "error")
            return

        self.is_downloading = True
        self.history.add(url)
        self.update_history_list()

        download_path = self.query_one(PathSelector).current_path
        is_audio = self.query_one("#type-selector", Select).value == "audio"
        format_id = self.query_one("#format-selector", Select).value

        ydl_opts: Dict[str, Any] = {
            "outtmpl": f"{download_path}/%(title)s.%(ext)s",
            "noplaylist": self.url_info.get("_type") != "playlist",
        }

        if is_audio:
            ydl_opts["format"] = "bestaudio/best"
            ydl_opts["postprocessors"] = [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3"}]
        else:
            ydl_opts["format"] = format_id

        self.query_one(Footer).set_status("Starting download...")
        self.run_worker(
            download_media,
            url,
            ydl_opts,
            self.progress_hook,
            name="downloader",
            group="download",
            exclusive=True,
        )

    def action_cancel_download(self) -> None:
        if self.is_downloading:
            self.workers.cancel_group(self, "download")
            self.is_downloading = False
            self.query_one(DownloadProgress).reset()
            self.query_one(Footer).set_status("Download cancelled.", "warning")

    def action_toggle_history(self) -> None:
        self.history_visible = not self.history_visible
        self.query_one("#history-panel").set_class(not self.history_visible, "-hidden")

    def action_select_path(self) -> None:
        def on_select(path: Path) -> None:
            str_path = str(path)
            self.settings.set("download_path", str_path)
            self.query_one(PathSelector).update_path(str_path)
            self.query_one(Footer).set_status(f"Path set to: {str_path}", "info")

        self.app.push_screen(DirectorySelectScreen(), on_select)

class DirectorySelectScreen(Screen):
    def compose(self) -> ComposeResult:
        yield Header(show_title=False)
        yield DirectoryTree(str(Path.home()), id="dir-tree")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one(Footer).set_status("Select a directory and press Enter.")

    def on_directory_tree_directory_selected(
        self, event: DirectoryTree.DirectorySelected
    ) -> None:
        self.dismiss(event.path)