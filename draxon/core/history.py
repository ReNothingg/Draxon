import json
from pathlib import Path
from typing import List

class HistoryManager:
    def __init__(self, history_file: Path, max_size: int = 10):
        self.history_file = history_file
        self.max_size = max_size
        self.history_file.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> List[str]:
        if not self.history_file.exists():
            return []
        try:
            with open(self.history_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []

    def save(self, history: List[str]) -> None:
        with open(self.history_file, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2)

    def add(self, url: str) -> None:
        history = self.load()
        if url in history:
            history.remove(url)
        history.insert(0, url)
        self.save(history[: self.max_size])