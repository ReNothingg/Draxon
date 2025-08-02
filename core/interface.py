import shutil
from pathlib import Path
from textual.app import App, ComposeResult
from textual.containers import Container, VerticalScroll
from textual.screen import Screen
from textual.widgets import Header, Footer, Static, Input, Button, ProgressBar, Log
from textual import work, on
from textual.message import Message

from .config import ConfigManager
from .downloader import Downloader
from .models import VideoFormat, AudioFormat

FFMPEG_AVAILABLE = bool(shutil.which("ffmpeg"))

class ProgressUpdate(Message):
    def __init__(self, progress: float, log_line: str) -> None:
        self.progress = progress
        self.log_line = log_line
        super().__init__()

class DownloadComplete(Message):
    def __init__(self, success: bool, message: str) -> None:
        self.success = success
        self.message = message
        super().__init__()

class MainScreen(Screen):
    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Container(
            Static("Draxon ✨", id="title"),
            Static("Вставьте ссылку на видео, плейлист или канал", id="subtitle"),
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
        self.app.call_from_thread(self.on_get_info_complete, info)

    def on_get_info_complete(self, info: dict | None) -> None:
        analyze_button = self.query_one("#analyze_button")
        analyze_button.disabled = False
        analyze_button.label = "Анализировать"
        
        if info:
            self.app.push_screen(FormatScreen(info=info))
        else:
            self.query_one("#error_message").update("🙁 Не удалось получить информацию. Проверьте ссылку.")

class FormatScreen(Screen):
    def __init__(self, info: dict):
        super().__init__()
        self.info = info
        self.url = info.get("webpage_url")
        self.video_formats, self.audio_formats = self.app.downloader.get_filtered_formats(info)
        self.selected_format: VideoFormat | None = self.video_formats[0] if self.video_formats else None
        self.best_audio: AudioFormat | None = self.audio_formats[0] if self.audio_formats else None
        self.format_buttons: list[Button] = []

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Container(
            Static("Выберите качество видео", id="format_title"),
            VerticalScroll(id="format_list"),
            Static("", id="audio_info"),
            Button("Скачать Видео", variant="success", id="download_video"),
            Button("Скачать Аудио", variant="primary", id="download_audio"),
            id="format_container"
        )
        yield Footer()

    def on_mount(self) -> None:
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

        if not FFMPEG_AVAILABLE:
             self.query_one("#audio_info").update("[yellow]FFmpeg не найден. Доступны только готовые форматы.[/yellow]")
        else:
            self.query_one("#audio_info").update("🎵 Аудиодорожка высокого качества будет добавлена автоматически.")

        audio_button = self.query_one("#download_audio", Button)
        if not self.audio_formats:
            audio_button.disabled = True
        audio_button.label = "Скачать аудио (.mp3)" if FFMPEG_AVAILABLE else "Скачать аудио (оригинал)"
        
    @on(Button.Pressed)
    def handle_button_press(self, event: Button.Pressed):
        button_id = event.button.id
        
        if button_id and button_id.startswith("format_"):
            format_id = button_id.split("_")[1]
            self.selected_format = next((f for f in self.video_formats if f.id == format_id), None)
            for btn in self.format_buttons:
                if not btn.disabled:
                    btn.variant = "default"
            event.button.variant = "warning"
        
        elif button_id == "download_video" and self.selected_format:
            video_id = self.selected_format.id
            audio_id = None if self.selected_format.is_merged else self.best_audio.id
            self.app.push_screen(DownloadScreen(self.url, self.info, video_id, audio_id))
        
        elif button_id == "download_audio" and self.best_audio:
            self.app.push_screen(DownloadScreen(self.url, self.info, None, self.best_audio.id))

class DownloadScreen(Screen):
    def __init__(self, url: str, info: dict, video_id: str | None, audio_id: str | None):
        super().__init__()
        self.url = url
        self.info = info
        self.video_id = video_id
        self.audio_id = audio_id

    def compose(self) -> ComposeResult:
        title = self.info.get('title', 'Неизвестно')
        yield Header(show_clock=True)
        yield Container(
            Static(f"Загрузка: {title[:80]}...", id="download_title"),
            ProgressBar(total=100, show_eta=False, id="progress_bar"),
            Log(id="download_log", max_lines=100, auto_scroll=True),
            Button("Назад", id="back_button", disabled=True),
            id="download_container"
        )
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#download_log").write_line("Инициализация загрузки...")
        self.run_download()

    @work(thread=True)
    def run_download(self) -> None:
        should_convert = (self.video_id is None) and FFMPEG_AVAILABLE
        download_path = self.app.config_manager.download_path
        success, message = self.app.downloader.download(self.url, download_path, self.video_id, self.audio_id, self.progress_hook, convert_to_mp3=should_convert)
        self.post_message(DownloadComplete(success, message))

    def progress_hook(self, d: dict) -> None:
        if d['status'] == 'downloading':
            percent_str = d.get('_percent_str', '0%').strip().replace('%', '')
            try:
                progress = float(percent_str)
                log_line = f" > Скачивание: {Path(d.get('filename')).name[:50]}... {percent_str:>5}%"
                self.post_message(ProgressUpdate(progress, log_line))
            except (ValueError, TypeError):
                pass
        elif d['status'] == 'finished':
             log_line = "[dim] > Обработка файла...[/dim]"
             if 'postprocessor' in d.get('info_dict', {}):
                 log_line = "[dim] > Конвертация в .mp3...[/dim]"
             elif self.video_id and self.audio_id:
                 log_line = "[dim] > Слияние видео и аудио...[/dim]"
             self.post_message(ProgressUpdate(100, log_line))

    def on_progress_update(self, message: ProgressUpdate) -> None:
        self.query_one("#progress_bar").update(progress=message.progress)
        self.query_one("#download_log").write_line(message.log_line)

    def on_download_complete(self, message: DownloadComplete) -> None:
        log_widget = self.query_one("#download_log")
        if message.success:
            self.query_one("#progress_bar").update(progress=100)
            log_widget.write_line(f"\n✅ {message.message}")
        else:
            log_widget.write_line("\n❌ Произошла ошибка:")
            log_widget.write_line(f"   Причина: {message.message}")
        self.query_one("#back_button").disabled = False

    @on(Button.Pressed, "#back_button")
    def go_back(self):
        self.app.pop_screen()

class DraxonApp(App):
    SCREENS = {"main": MainScreen()}
    BINDINGS = [("q", "quit", "Выход")]
    
    def __init__(self, config_manager: ConfigManager):
        super().__init__()
        self.config_manager = config_manager
        self.downloader = Downloader()

    def on_mount(self) -> None:
        css_path = Path(__file__).parent.parent / "ui" / "interface.css"
        try:
            with open(css_path, "r", encoding="utf-8") as f:
                css_data = f.read()
            self.stylesheet.add_source(css_data, path=str(css_path))
            self.stylesheet.parse()
        except IOError as e:
            print(f"Не удалось загрузить файл стилей: {e}")
        except Exception as e:
            print(f"Ошибка при обработке CSS: {e}")

        self.push_screen("main")