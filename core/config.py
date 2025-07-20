import json
from pathlib import Path

CONFIG_FILE = Path.home() / ".draxon" / "config.json"
DEFAULT_DOWNLOAD_PATH = Path.home() / "Downloads" / "Draxon"

def get_config():
    if not CONFIG_FILE.exists():
        return {"download_path": str(DEFAULT_DOWNLOAD_PATH)}
    
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            config = json.load(f)
            if "download_path" not in config:
                config["download_path"] = str(DEFAULT_DOWNLOAD_PATH)
            return config
    except (json.JSONDecodeError, IOError):
        return {"download_path": str(DEFAULT_DOWNLOAD_PATH)}

def save_config(config: dict):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=4)
    except IOError as e:
        print(f"Не удалось сохранить конфигурацию: {e}")