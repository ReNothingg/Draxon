from textual.app import App, ComposeResult
from draxon.ui.screens import MainScreen

class DraxonApp(App):
    CSS_PATH = "ui/theme.py"
    SCREENS = {"main": MainScreen()}
    BINDINGS = [("ctrl+c", "quit", "Quit")]

    def on_mount(self) -> None:
        self.push_screen("main")

def main() -> None:
    app = DraxonApp()
    app.run()

if __name__ == "__main__":
    main()