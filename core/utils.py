import subprocess
import sys

def open_folder(path: str):
    """Открывает папку в системном файловом менеджере."""
    try:
        if sys.platform == "win32":
            subprocess.run(["explorer", path], check=True)
        elif sys.platform == "darwin":
            subprocess.run(["open", path], check=True)
        else: #линукс
            subprocess.run(["xdg-open", path], check=True)
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"Не удалось открыть папку {path}: {e}", file=sys.stderr)