import shutil
import sys
from pathlib import Path
import traceback

if sys.version_info < (3, 9):
    print("Ошибка: Для работы Draxon требуется Python версии 3.9 или выше.", file=sys.stderr)
    input("Нажмите Enter для выхода...")
    sys.exit(1)

try:
    from core.config import ConfigManager
    from core.interface import DraxonApp
except ImportError as e:
    print(f"Ошибка: Не удалось импортировать необходимые компоненты: {e}", file=sys.stderr)
    print("Пожалуйста, убедитесь, что все зависимости установлены (`pip install --upgrade textual yt-dlp`)", file=sys.stderr)
    input("Нажмите Enter для выхода...")
    sys.exit(1)


def check_ffmpeg():
    if not shutil.which("ffmpeg"):
        print("⚠️  Внимание: ffmpeg не найден в системном PATH.", file=sys.stderr)
        print("   Функционал конвертации в MP3 и слияния форматов будет недоступен.", file=sys.stderr)
        print("-" * 60, file=sys.stderr)

def main():
    try:
        config_dir = Path.home() / ".draxon"
        config_dir.mkdir(exist_ok=True)
        check_ffmpeg()
        config_manager = ConfigManager()
        app = DraxonApp(config_manager=config_manager)
        app.run()
    except Exception as e:
        print("\n--- КРИТИЧЕСКАЯ ОШИБКА ---", file=sys.stderr)
        traceback.print_exc()
        print("--------------------------", file=sys.stderr)
        input("\nПрограмма завершилась с ошибкой. Нажмите Enter для выхода.")
        sys.exit(1)

if __name__ == "__main__":
    main()