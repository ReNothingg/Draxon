import json
from pathlib import Path
from datetime import datetime

HISTORY_FILE = Path.home() / ".draxon" / "history.json"

def get_history():
    if not HISTORY_FILE.exists():
        return []
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []

def log_download(url: str, title: str, format_note: str, success: bool):
    history = get_history()
    
    new_entry = {
        "timestamp": datetime.now().isoformat(),
        "url": url,
        "title": title,
        "format": format_note,
        "status": "✅ Успешно" if success else "❌ Ошибка"
    }
    
    history.insert(0, new_entry) 
    
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=4)
    except IOError as e:
        
        print(f"Не удалось записать историю: {e}")