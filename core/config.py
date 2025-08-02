import json
from pathlib import Path

class ConfigManager:
    _CONFIG_FILE = Path.home() / ".draxon" / "config.json"
    _DEFAULT_DOWNLOAD_PATH = Path.home() / "Downloads" / "Draxon"

    def __init__(self):
        self._config = self._load()
        self.download_path.mkdir(parents=True, exist_ok=True)

    @property
    def download_path(self) -> Path:
        return Path(self._config.get("download_path", str(self._DEFAULT_DOWNLOAD_PATH)))

    def _load(self) -> dict:
        if not self._CONFIG_FILE.exists():
            return {"download_path": str(self._DEFAULT_DOWNLOAD_PATH)}
        
        try:
            with open(self._CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
                if "download_path" not in config:
                    config["download_path"] = str(self._DEFAULT_DOWNLOAD_PATH)
                return config
        except (json.JSONDecodeError, IOError):
            return {"download_path": str(self._DEFAULT_DOWNLOAD_PATH)}

    def save(self) -> None:
        try:
            with open(self._CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self._config, f, ensure_ascii=False, indent=4)
        except IOError as e:
            print(f"Не удалось сохранить конфигурацию: {e}")