import json
from pathlib import Path
from typing import Any, Dict

class SettingsManager:
    def __init__(self, config_file: Path):
        self.config_file = config_file
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        self.settings = self._load()

    def _get_default_download_path(self) -> str:
        return str(Path.home() / "Downloads")

    def _load(self) -> Dict[str, Any]:
        defaults = {"download_path": self._get_default_download_path()}
        if not self.config_file.exists():
            return defaults
        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                user_settings = json.load(f)
                defaults.update(user_settings)
                return defaults
        except (json.JSONDecodeError, IOError):
            return defaults

    def save(self) -> None:
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump(self.settings, f, indent=2)

    def get(self, key: str) -> Any:
        return self.settings.get(key)

    def set(self, key: str, value: Any) -> None:
        self.settings[key] = value
        self.save()