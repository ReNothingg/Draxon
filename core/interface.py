import shutil
from pathlib import Path
from textual.app import App, ComposeResult
from textual.containers import Container, VerticalScroll
from textual.screen import Screen
from textual.widgets import Header, Footer, Static, Input, Button, ProgressBar, Log, RadioSet, RadioButton, Checkbox, Label
from textual import work, on
from textual.message import Message

from .config import ConfigManager
from .downloader import Downloader
from .models import VideoFormat, AudioFormat
from .utils import open_folder

FFMPEG_AVAILABLE = bool(shutil.which("ffmpeg"))

class ProgressUpdate(Message):
    def __init__(self, progress: float | None, log_line: str) -> None:
        super().__init__()
        self.progress = progress
        self.log_line = log_line

class DownloadComplete(Message):
    def __init__(self, success: bool, message: str, download_path: str | None) -> None:
        super().__init__()
        self.success = success
        self.message = message
        self.download_path = download_path

class MainScreen(Screen):
    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Container(
            Static("Draxon ✨", id="title"),
            Static("Вставьте ссылку на видео или плейлист", id="subtitle"),
            Input(placeholder="https://...", id="url_input"),
            Button("Анализировать", variant="primary", id="analyze_button"),
            Static("", id="error_message"),
            id="main_container"
        )
        yield Footer()

    @on(Button.Pressed, "#analyze_button")
    def on_analyze(self, event: Button.Pressed):
        url = self.query_one("#url_input").value
        if not url:
            self.query_one("#error_message").update("🙁 Пожалуйста, введите ссылку.")
            return
        
        self.query_one("#error_message").update("")
        event.button.disabled = True
        event.button.label = "Анализ..."
        self.get_info(url)

    @work(exclusive=True, thread=True)
    def get_info(self, url: str) -> None:
        info = self.app.downloader.get_video_info(url)
        self.app.call_from_thread(self.on_get_info_complete, info, url)

    @work(exclusive=True, thread=True)
    def get_full_video_info(self, url: str) -> None:
        full_info = self.app.downloader.get_video_info(url.split('&list=')[0])
        if full_info:
            self.app.call_from_thread(self.app.push_screen, FormatScreen(info=full_info))
        else:
            def on_fail():
                self.query_one("#analyze_button").disabled = False
                self.query_one("#analyze_button").label = "Анализировать"
                self.query_one("#error_message").update("🙁 Не удалось получить детальную информацию.")
            self.app.call_from_thread(on_fail)

    def on_get_info_complete(self, info: dict | None, url: str) -> None:
        analyze_button = self.query_one("#analyze_button")
        
        if not info:
            analyze_button.disabled = False
            analyze_button.label = "Анализировать"
            self.query_one("#error_message").update("🙁 Не удалось получить информацию. Проверьте ссылку.")
            return

        if info.get('_type') == 'playlist':
            analyze_button.disabled = False
            analyze_button.label = "Анализировать"
            self.app.push_screen(PlaylistScreen(info=info))
        else:
            analyze_button.label = "Получение форматов..."
            self.get_full_video_info(url)


class FormatScreen(Screen):
    def __init__(self, info: dict):
        super().__init__()
        self.info = info
        self.url = info.get("webpage_url")
        self.video_formats: list[VideoFormat] = []
        self.audio_formats: list[AudioFormat] = []
        self.selected_format: VideoFormat | None = None
        self.best_audio: AudioFormat | None = None
        self.format_buttons: list[Button] = []

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Container(
            Static(f"Выбор качества: {self.info.get('title', '')[:60]}", id="format_title"),
            VerticalScroll(id="format_list"),
            Static("", id="audio_info"),
            Button("Скачать Видео", variant="success", id="download_video"),
            Button("Скачать Аудио", variant="primary", id="download_audio"),
            id="format_container"
        )
        yield Footer()

    def on_mount(self) -> None:
        self.video_formats, self.audio_formats = self.app.downloader.get_filtered_formats(self.info)
        self.selected_format = self.video_formats[0] if self.video_formats else None
        self.best_audio = self.audio_formats[0] if self.audio_formats else None

        format_list = self.query_one("#format_list")
        for f in self.video_formats:
            label = f.get_display_label(FFMPEG_AVAILABLE)
            button = Button(label, id=f"format_{f.id}")
            if not f.is_merged and not FFMPEG_AVAILABLE:
                button.disabled = True
            self.format_buttons.append(button)
            format_list.mount(button)
        
        if not self.video_formats:
            format_list.mount(Static("Видеоформаты не найдены.", classes="error_text"))
            self.query_one("#download_video", Button).disabled = True

        first_available_button = next((btn for btn in self.format_buttons if not btn.disabled), None)
        if first_available_button:
            first_available_button.variant = "warning"
            format_id = first_available_button.id.split("_")[1]
            self.selected_format = next((f for f in self.video_formats if f.id == format_id), None)

        self.query_one("#audio_info").update("🎵 Аудиодорожка высокого качества будет добавлена автоматически.")
        if not FFMPEG_AVAILABLE:
             self.query_one("#audio_info").update("[yellow]FFmpeg не найден. Доступны только готовые форматы.[/yellow]")

        audio_button = self.query_one("#download_audio", Button)
        if not self.audio_formats:
            audio_button.disabled = True
        audio_button.label = "Скачать аудио (.mp3)" if self.app.config_manager.convert_audio_to_mp3 and FFMPEG_AVAILABLE else "Скачать аудио (оригинал)"
        
    @on(Button.Pressed)
    def handle_button_press(self, event: Button.Pressed):
        button_id = event.button.id
        if button_id and button_id.startswith("format_"):
            format_id = button_id.split("_")[1]
            self.selected_format = next((f for f in self.video_formats if f.id == format_id), None)
            for btn in self.format_buttons:
                if not btn.disabled: btn.variant = "default"
            event.button.variant = "warning"
        elif button_id == "download_video" and self.selected_format:
            video_id = self.selected_format.id
            audio_id = None if self.selected_format.is_merged else self.best_audio.id
            self.app.push_screen(DownloadScreen(url=self.url, video_id=video_id, audio_id=audio_id, info=self.info))
        elif button_id == "download_audio" and self.best_audio:
            self.app.push_screen(DownloadScreen(url=self.url, audio_only=True, info=self.info))

class PlaylistScreen(Screen):
    def __init__(self, info: dict):
        super().__init__()
        self.info = info
        self.url = info.get("webpage_url")

    def compose(self) -> ComposeResult:
        title = self.info.get('title', 'Неизвестный плейлист')
        count = self.info.get('playlist_count', 'N/A')
        yield Header(show_clock=True)
        yield Container(
            Static(f"Плейлист: {title}", id="playlist_title"),
            Static(f"Найдено видео: {count}", id="playlist_count"),
            Static("Загрузка будет использовать настройки качества по умолчанию.", id="playlist_info"),
            Button("Скачать всё (Видео)", variant="success", id="download_all_video"),
            Button("Скачать всё (Аудио)", variant="primary", id="download_all_audio"),
            id="playlist_container"
        )
        yield Footer()

    @on(Button.Pressed, "#download_all_video")
    def download_videos(self):
        quality = self.app.config_manager.default_video_quality
        self.app.push_screen(DownloadScreen(url=self.url, playlist_quality=quality, info=self.info))

    @on(Button.Pressed, "#download_all_audio")
    def download_audios(self):
        self.app.push_screen(DownloadScreen(url=self.url, audio_only=True, info=self.info))

class DownloadScreen(Screen):
    def __init__(self, url: str, info: dict, *, video_id: str | None = None, audio_id: str | None = None, playlist_quality: str | None = None, audio_only: bool = False):
        super().__init__()
        self.url = url
        self.info = info
        self.video_id = video_id
        self.audio_id = audio_id
        self.playlist_quality = playlist_quality
        self.audio_only = audio_only

    def compose(self) -> ComposeResult:
        title = self.info.get('title', 'контент')
        yield Header(show_clock=True)
        yield Container(
            Static(f"Загрузка: {title[:80]}...", id="download_title"),
            ProgressBar(total=100, show_eta=False, id="progress_bar"),
            Log(id="download_log", max_lines=100, auto_scroll=True),
            Container(
                Button("Назад", id="back_button", disabled=True),
                Button("Открыть папку", variant="primary", id="open_folder_button", disabled=True),
                id="button_container"
            ),
            id="download_container"
        )
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#download_log").write_line("Инициализация загрузки...")
        self.run_download()

    @work(thread=True)
    def run_download(self) -> None:
        cfg = self.app.config_manager
        success, message, path = self.app.downloader.download(
            self.url, cfg.download_path, self.progress_hook,
            video_format_id=self.video_id, audio_id=self.audio_id,
            playlist_quality=self.playlist_quality, audio_only=self.audio_only,
            convert_to_mp3=FFMPEG_AVAILABLE and cfg.convert_audio_to_mp3
        )
        self.post_message(DownloadComplete(success, message, path))

    def progress_hook(self, d: dict) -> None:
        if d['status'] == 'downloading':
            percent_str = d.get('_percent_str', '0%').strip().replace('%', '')
            try:
                progress = float(percent_str)
                playlist_prefix = ""
                if d.get('playlist_index') and d.get('playlist_count'):
                    playlist_prefix = f"[{d.get('playlist_index')}/{d.get('playlist_count')}] "
                
                log_line = f" > {playlist_prefix}Скачивание: {Path(d.get('filename')).name[:40]}... {percent_str:>5}%"
                self.query_one("#download_log").clear()
                self.query_one("#download_log").write(log_line)
                self.post_message(ProgressUpdate(progress, ""))
            except (ValueError, TypeError): pass
        elif d['status'] == 'finished':
             log_line = "[dim] > Обработка файла...[/dim]"
             self.post_message(ProgressUpdate(100, log_line))

    def on_progress_update(self, message: ProgressUpdate) -> None:
        if message.progress is not None: self.query_one("#progress_bar").update(progress=message.progress)
        if message.log_line: self.query_one("#download_log").write_line(message.log_line)

    def on_download_complete(self, message: DownloadComplete) -> None:
        log_widget = self.query_one("#download_log")
        log_widget.clear()
        if message.success:
            self.query_one("#progress_bar").update(progress=100)
            log_widget.write(f"\n✅ {message.message}")
            if message.download_path:
                self.query_one("#open_folder_button").disabled = False
                self.query_one("#open_folder_button").action = f"app.open_download_folder('{message.download_path}')"
        else:
            log_widget.write("\n❌ Произошла ошибка:")
            log_widget.write(f"\n   Причина: {message.message}")
        self.query_one("#back_button").disabled = False

    @on(Button.Pressed, "#back_button")
    def go_back(self):
        self.app.pop_screen()

class SettingsScreen(Screen):
    def compose(self) -> ComposeResult:
        cfg = self.app.config_manager
        yield Header(show_clock=True)
        yield Container(
            Static("Настройки", id="settings_title"),
            Label("Путь для загрузки:"),
            Input(value=str(cfg.download_path), id="path_input"),
            Label("Качество видео для плейлистов:"),
            RadioSet(
                RadioButton("Лучшее", id="best", value=(cfg.default_video_quality == 'best')),
                RadioButton("1080p", id="1080p", value=(cfg.default_video_quality == '1080p')),
                RadioButton("720p", id="720p", value=(cfg.default_video_quality == '720p')),
                id="quality_radioset"
            ),
            Checkbox("Конвертировать аудио в MP3", value=cfg.convert_audio_to_mp3, id="mp3_checkbox", disabled=not FFMPEG_AVAILABLE),
            Button("Сохранить и вернуться", variant="success", id="save_button"),
            id="settings_container"
        )
        yield Footer()

    @on(Button.Pressed, "#save_button")
    def save_settings(self):
        cfg = self.app.config_manager
        cfg.update_setting("download_path", self.query_one("#path_input").value)
        
        pressed_button = self.query_one(RadioSet).pressed_button
        if pressed_button:
            cfg.update_setting("default_video_quality", pressed_button.id)
        
        cfg.update_setting("convert_audio_to_mp3", self.query_one("#mp3_checkbox").value)
        self.app.pop_screen()

class DraxonApp(App):
    CSS_PATH = Path(__file__).parent.parent / "ui" / "interface.css"
    
    SCREENS = {
        "main": MainScreen,
        "settings": SettingsScreen,
    }
    
    BINDINGS = [("q", "quit", "Выход"), ("s", "push_screen('settings')", "Настройки")]
    
    def __init__(self, config_manager: ConfigManager):
        super().__init__()
        self.config_manager = config_manager
        self.downloader = Downloader()

    def on_mount(self) -> None:
        self.push_screen("main")

    def action_open_download_folder(self, path: str):
        open_folder(path)