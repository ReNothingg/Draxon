from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import Container
from textual.screen import Screen
from textual.widgets import Header, Footer, Static, Input, Button, ProgressBar, RadioSet, RadioButton, Log
from textual import work, on

from core.downloader import Downloader
from utils.logger import log_download

CSS_PATH = Path(__file__).parent.parent / "ui" / "interface.css"

class MainScreen(Screen):
    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Container(
            Static("Draxon ✨", id="title"),
            Static("Вставьте ссылку на видео, плейлист или канал ниже", id="subtitle"),
            Input(placeholder="https://...", id="url_input"),
            RadioSet(
                RadioButton("Видео", id="video_radio", value=True),
                RadioButton("Только аудио (.mp3)", id="audio_radio"),
                id="format_selector"
            ),
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
            is_audio = self.query_one("#audio_radio").value
            self.app.push_screen(DownloadScreen(url=self.query_one("#url_input").value, info=info, is_audio_only=is_audio))
        else:
            self.query_one("#error_message").update("🙁 Не удалось получить информацию. Ссылка корректна?")


class DownloadScreen(Screen):
    def __init__(self, url: str, info: dict, is_audio_only: bool):
        super().__init__()
        self.url = url
        self.info = info
        self.is_audio_only = is_audio_only
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
        success, format_note = self.downloader.download(self.url, self.is_audio_only, self.progress_hook)
        self.app.call_from_thread(self.on_download_complete, success, format_note)

    def on_download_complete(self, success: bool, format_note: str) -> None:
        title = self.info.get('title', 'N/A')
        log_download(self.url, title, format_note, success)
        
        log_widget = self.query_one("#download_log")
        if success:
            self.query_one("#progress_bar").update(progress=100)
            log_widget.write_line("\n[bold green]✅ Загрузка завершена![/bold green]")
        else:
            log_widget.write_line("\n[bold red]❌ Произошла ошибка во время загрузки.[/bold red]")
        
        self.query_one("#back_button").disabled = False

    def progress_hook(self, d: dict) -> None:
        if d['status'] == 'downloading':
            percent_str = d.get('_percent_str', '0%').strip().replace('%', '')
            speed_str = d.get('_speed_str', 'N/A')
            eta_str = d.get('_eta_str', 'N/A')
            
            try:
                progress = float(percent_str)
                self.app.call_from_thread(self.query_one("#progress_bar").update, progress=progress)
                self.app.call_from_thread(self.query_one("#download_log").write_line, f" > {percent_str:>5}% | Скорость: {speed_str} | ETA: {eta_str}")
            except (ValueError, TypeError):
                pass

        elif d['status'] == 'finished':
            self.app.call_from_thread(self.query_one("#download_log").write_line, f"[dim]Обработка файла завершена...[/dim]")

    @on(Button.Pressed, "#back_button")
    def go_back(self):
        self.app.pop_screen()


class DraxonApp(App):
    CSS_PATH = CSS_PATH
    SCREENS = {"main": MainScreen()}
    BINDINGS = [("q", "quit", "Выход")]

    def on_mount(self) -> None:
        self.push_screen("main")