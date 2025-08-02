import json
from pathlib import Path

class ConfigManager:
    _CONFIG_FILE = Path.home() / ".draxon" / "config.json"
    _DEFAULT_CONFIG = {
        "download_path": str(Path.home() / "Downloads" / "Draxon"),
        "default_video_quality": "1080p",
        "convert_audio_to_mp3": True
    }

    def __init__(self):
        self._config = self._load()
        self.download_path.mkdir(parents=True, exist_ok=True)

    @property
    def download_path(self) -> Path:
        return Path(self._config.get("download_path"))

    @property
    def default_video_quality(self) -> str:
        return self._config.get("default_video_quality")

    @property
    def convert_audio_to_mp3(self) -> bool:
        return self._config.get("convert_audio_to_mp3")

    def _load(self) -> dict:
        if not self._CONFIG_FILE.exists():
            return self._DEFAULT_CONFIG.copy()
        
        try:
            with open(self._CONFIG_FILE, "r", encoding="utf-8") as f:
                user_config = json.load(f)
            config = self._DEFAULT_CONFIG.copy()
            config.update(user_config)
            return config
        except (json.JSONDecodeError, IOError):
            return self._DEFAULT_CONFIG.copy()

    def save(self):
        try:
            with open(self._CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self._config, f, ensure_ascii=False, indent=4)
        except IOError as e:
            print(f"Не удалось сохранить конфигурацию: {e}")

    def update_setting(self, key: str, value) -> None:
        if key in self._config:
            self._config[key] = value
            self.save()