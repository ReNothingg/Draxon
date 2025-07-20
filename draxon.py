import os
import shutil
import sys
from pathlib import Path

from core.interface import DraxonApp

def check_ffmpeg():
    if not shutil.which("ffmpeg"):
        print("⚠️  Внимание: ffmpeg не найден в вашем PATH.", file=sys.stderr)
        print("   Аудио будет скачано в исходном формате, без конвертации в .mp3.", file=sys.stderr)
        print("   Пожалуйста, установите FFmpeg для полного функционала.", file=sys.stderr)
        print("-" * 30)

def main():
    config_dir = Path.home() / ".draxon"
    downloads_dir = Path.home() / "Downloads" / "Draxon"
    
    config_dir.mkdir(exist_ok=True)
    downloads_dir.mkdir(parents=True, exist_ok=True)
    
    check_ffmpeg()
    
    app = DraxonApp()
    app.run()

if __name__ == "__main__":
    main()