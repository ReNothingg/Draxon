import shutil
import sys
from pathlib import Path

from core.config import ConfigManager
from core.interface import DraxonApp

def check_ffmpeg():
    if not shutil.which("ffmpeg"):
        print("⚠️  Внимание: ffmpeg не найден в системном PATH.", file=sys.stderr)
        print("   Функционал будет ограничен форматами, не требующими слияния.", file=sys.stderr)
        print("-" * 40, file=sys.stderr)

def main():
    config_dir = Path.home() / ".draxon"
    config_dir.mkdir(exist_ok=True)
    
    check_ffmpeg()
    
    config_manager = ConfigManager()
    
    app = DraxonApp(config_manager=config_manager)
    app.run()

if __name__ == "__main__":
    main()