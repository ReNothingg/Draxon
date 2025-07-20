import shutil
from pathlib import Path
from textual.app import App, ComposeResult
from textual.containers import Container, VerticalScroll
from textual.screen import Screen
from textual.widgets import Header, Footer, Static, Input, Button, ProgressBar, Log
from textual import work, on
from textual.message import Message

from core.downloader import Downloader
from utils.logger import log_download

CSS_PATH = Path(__file__).parent.parent / "ui" / "interface.css"

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
            Static("Вставьте ссылку на видео, плейлист или канал ниже", id="subtitle"),
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
        downloader = Downloader()
        info = downloader.get_video_info(url)
        self.app.call_from_thread(self.on_get_info_complete, info)

    def on_get_info_complete(self, info: dict | None) -> None:
        analyze_button = self.query_one("#analyze_button")
        analyze_button.disabled = False
        analyze_button.label = "Анализировать"
        
        if info:
            self.app.push_screen(FormatScreen(info=info))
        else:
            self.query_one("#error_message").update("🙁 Не удалось получить информацию. Ссылка корректна?")

class FormatScreen(Screen):
    def __init__(self, info: dict):
        super().__init__()
        self.info = info
        self.url = info.get("webpage_url")
        self.downloader = Downloader()
        self.video_formats, self.audio_formats = self.downloader.get_filtered_formats(info)
        self.selected_video_id = self.video_formats[0]['id'] if self.video_formats else None
        self.best_audio_id = self.audio_formats[0]['id'] if self.audio_formats else None
        self.format_buttons = []

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Container(
            Static("[bold]Выберите качество видео[/bold]", id="format_title"),
            VerticalScroll(id="format_list"),
            Static("", id="audio_info"),
            Button("Скачать Видео", variant="success", id="download_video"),
            Button("Скачать только аудио", variant="primary", id="download_audio"),
            id="format_container"
        )
        yield Footer()

    def on_mount(self) -> None:
        format_list = self.query_one("#format_list")
        for f in self.video_formats:
            label = f"{f['res']} @ {f['fps']}fps ({f['size_mb']})"
            button = Button(label, id=f"format_{f['id']}")
            self.format_buttons.append(button)
            format_list.mount(button)
        
        if self.format_buttons:
            self.format_buttons[0].variant = "warning"
        
        if self.audio_formats:
            best_audio = self.audio_formats[0]
            audio_note = "будет добавлено автоматически." if FFMPEG_AVAILABLE else "[red](требуется FFmpeg для слияния)[/red]"
            self.query_one("#audio_info").update(f"🎵 Аудио: {best_audio['abr']}kbps ({best_audio['size_mb']}) {audio_note}")

        video_button = self.query_one("#download_video", Button)
        audio_button = self.query_one("#download_audio", Button)

        if not FFMPEG_AVAILABLE:
            video_button.label = "Скачать Видео (требуется FFmpeg)"
            video_button.disabled = True
            audio_button.label = "Скачать только аудио (в исходном формате)"
        else:
            audio_button.label = "Скачать только аудио (.mp3)"

    @on(Button.Pressed)
    def handle_button_press(self, event: Button.Pressed):
        button_id = event.button.id
        
        if button_id and button_id.startswith("format_"):
            self.selected_video_id = button_id.split("_")[1]
            for btn in self.format_buttons:
                btn.variant = "default"
            event.button.variant = "warning"
        
        elif button_id == "download_video":
            if self.selected_video_id and self.best_audio_id:
                self.app.push_screen(DownloadScreen(self.url, self.info, self.selected_video_id, self.best_audio_id))
        
        elif button_id == "download_audio":
            if self.best_audio_id:
                self.app.push_screen(DownloadScreen(self.url, self.info, None, self.best_audio_id))

class DownloadScreen(Screen):
    def __init__(self, url: str, info: dict, video_id: str | None, audio_id: str):
        super().__init__()
        self.url = url
        self.info = info
        self.video_id = video_id
        self.audio_id = audio_id
        self.downloader = Downloader()

    def compose(self) -> ComposeResult:
        title = self.info.get('title', 'Неизвестный контент')
        yield Header(show_clock=True)
        yield Container(
            Static(f"[bold]Загрузка:[/bold] {title[:80]}", id="download_title"),
            ProgressBar(total=100, show_eta=False, id="progress_bar"),
            Log(id="download_log", max_lines=100, auto_scroll=True),
            Button("Назад", id="back_button", disabled=True),
            id="download_container"
        )
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#download_log").write_line("Инициализация...")
        self.run_download()

    @work(thread=True)
    def run_download(self) -> None:
        should_convert = (self.video_id is None) and FFMPEG_AVAILABLE
        success, message = self.downloader.download(self.url, self.video_id, self.audio_id, self.progress_hook, convert_to_mp3=should_convert)
        self.post_message(DownloadComplete(success, message))

    def progress_hook(self, d: dict) -> None:
        if d['status'] == 'downloading':
            percent_str = d.get('_percent_str', '0%').strip().replace('%', '')
            try:
                progress = float(percent_str)
                log_line = f" > Скачивание: {d.get('filename', '').split('/')[-1][:50]}... {percent_str:>5}%"
                self.post_message(ProgressUpdate(progress, log_line))
            except (ValueError, TypeError): pass
        elif d['status'] == 'finished':
             log_line = "[dim] > Обработка файла...[/dim]"
             if 'postprocessor' in d.get('info_dict', {}):
                 log_line = "[dim] > Конвертация в .mp3...[/dim]"
             self.post_message(ProgressUpdate(100, log_line))

    def on_progress_update(self, message: ProgressUpdate) -> None:
        self.query_one("#progress_bar").update(progress=message.progress)
        self.query_one("#download_log").write_line(message.log_line)

    def on_download_complete(self, message: DownloadComplete) -> None:
        log_widget = self.query_one("#download_log")
        if message.success:
            self.query_one("#progress_bar").update(progress=100)
            log_widget.write_line("\n[bold green]✅ Загрузка завершена![/bold green]")
        else:
            log_widget.write_line("\n[bold red]❌ Произошла ошибка во время загрузки.[/bold red]")
            log_widget.write_line(f"[red]Причина: {message.message}[/red]")
        
        self.query_one("#back_button").disabled = False

    @on(Button.Pressed, "#back_button")
    def go_back(self):
        self.app.pop_screen()

class DraxonApp(App):
    CSS_PATH = CSS_PATH
    SCREENS = {"main": MainScreen()}
    BINDINGS = [("q", "quit", "Выход")]

    def on_mount(self) -> None:
        self.push_screen("main")