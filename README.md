# 🐉 Draxon

**Draxon** — это мощный и гибкий загрузчик медиафайлов с поддержкой профилей, интерактивным интерфейсом и оптимизацией для Termux. Построен на базе `yt-dlp` с расширенными возможностями управления загрузками.

## ✨ Особенности

- 🎯 **Гибкие профили** — создавайте и переключайтесь между различными конфигурациями
- 📱 **Termux-оптимизация** — автоматическое определение и поддержка Android Termux
- 🎨 **Богатый интерфейс** — красивое отображение прогресса с помощью Rich
- 🔄 **Параллельные загрузки** — одновременная загрузка нескольких файлов
- 📋 **Умный ввод** — поддержка clipboard, stdin, файлов и интерактивного редактора
- 🎵 **Аудио извлечение** — автоматическое извлечение аудио в MP3
- 🌐 **Прокси и ограничения** — настройка прокси и ограничений скорости
- 📝 **Субтитры** — автоматическая загрузка субтитров в SRT формате
- ⚡ **Возобновление** — поддержка возобновления прерванных загрузок

## 🚀 Установка

### Требования

- Python 3.7+
- yt-dlp
- Rich
- FFmpeg (для извлечения аудио)

### Установка зависимостей

```bash
pip install yt-dlp rich
```

### Установка FFmpeg

**Windows:**
```bash
# Через chocolatey
choco install ffmpeg

# Или скачайте с официального сайта
```

**Linux:**
```bash
sudo apt install ffmpeg  # Ubuntu/Debian
sudo yum install ffmpeg  # CentOS/RHEL
```

**Termux:**
```bash
pkg install ffmpeg
```

## 📖 Использование

### Базовое использование

```bash
# Интерактивный режим
python draxon.py

# Загрузка конкретных URL
python draxon.py -u ""

# Загрузка из файла
python draxon.py -f urls.txt

# Использование профиля
python draxon.py --profile "my_profile"
```

### CLI аргументы

```bash
python draxon.py [ОПЦИИ] [URLs...]

ОПЦИИ:
  -u, --urls URLs...        URLs для загрузки (можно с overrides: URL||flag,key=val)
  -f, --file FILE           Файл с URLs
  --profile PROFILE         Профиль для использования
  --output-dir DIR          Переопределить папку вывода
  --outtmpl TEMPLATE        Переопределить шаблон имени файла
  --format FORMAT           Переопределить формат видео
  --audio                   Извлечь аудио для всех URLs
  --playlist                Загрузить плейлист
  --subtitles LANG          Языки субтитров (через запятую)
  --proxy PROXY             Прокси сервер
  --rate RATE               Ограничение скорости (например: 500K)
  --parallel                Параллельные загрузки
  --max-workers N           Максимум потоков (по умолчанию: 2)
  --save-config             Сохранить профиль в конфиг
  --no-tui                  Пропустить интерактивный ввод
```

### Формат URL с overrides

```bash
# Базовый URL
https://youtube.com/watch?v=VIDEO_ID

# URL с флагами
https://youtube.com/watch?v=VIDEO_ID||audio,format=best

# URL с параметрами
https://youtube.com/watch?v=VIDEO_ID||proxy=http://proxy:8080,rate=1M

# Комбинация флагов и параметров
https://youtube.com/watch?v=VIDEO_ID||audio,playlist,outtmpl=%(title)s_%(id)s.%(ext)s
```

## ⚙️ Конфигурация

### Файл конфигурации

Draxon автоматически создает файл конфигурации в `~/.draxon.json`:

```json
{
    "output_dir": "/path/to/downloads",
    "output_template": "%(title)s.%(ext)s",
    "video_format": "best",
    "subtitles_languages": "en,ru",
    "proxy": "",
    "rate_limit": "",
    "resume_download": true,
    "verbose": false,
    "log_to_file": false,
    "log_file": "/path/to/draxon.log",
    "parallel_download": false,
    "max_workers": 2,
    "profiles": {
        "default": {},
        "audio_only": {
            "video_format": "bestaudio/best",
            "output_template": "%(title)s.%(ext)s"
        },
        "high_quality": {
            "video_format": "bestvideo+bestaudio/best",
            "output_template": "%(title)s_%(height)sp.%(ext)s"
        }
    }
}
```

### Создание профилей

Профили позволяют быстро переключаться между различными настройками:

```bash
# Создание профиля через интерактивный режим
python draxon.py

# Или программно в конфиге
{
    "profiles": {
        "my_profile": {
            "output_dir": "/custom/path",
            "video_format": "720p",
            "subtitles_languages": "en"
        }
    }
}
```

## 🔧 Возможности

### Умный ввод

Draxon поддерживает множество способов ввода URLs:

1. **Интерактивный ввод** — вставка текста с автоматическим извлечением ссылок
2. **Файлы** — загрузка URLs из текстовых файлов
3. **Clipboard (Termux)** — автоматическое чтение из буфера обмена
4. **Stdin/Pipe** — передача URLs через pipe
5. **Редактор** — открытие списка в текстовом редакторе для правки

### Параллельные загрузки

```bash
# Включение параллельных загрузок
python draxon.py --parallel --max-workers 4

# Или в конфиге
{
    "parallel_download": true,
    "max_workers": 4
}
```

### Извлечение аудио

```bash
# Извлечение аудио для всех URLs
python draxon.py --audio

# Или для конкретных URLs
python draxon.py -u "https://youtube.com/watch?v=VIDEO_ID||audio"
```

### Субтитры

```bash
# Загрузка субтитров на английском и русском
python draxon.py --subtitles "en,ru"

# Или в конфиге
{
    "subtitles_languages": "en,ru,es"
}
```

## 📱 Termux поддержка

Draxon автоматически определяет Termux и оптимизирует работу:

- Автоматическое чтение из clipboard
- Оптимизированные пути для Android
- Поддержка Termux-специфичных команд

## 🎨 Интерфейс

### Прогресс загрузки

- Спиннер активности
- Название файла
- Прогресс-бар
- Скорость загрузки
- Оставшееся время
- Размер загруженного файла

### Интерактивные элементы

- Подтверждения действий
- Выбор профилей
- Редактирование настроек
- Управление списком URLs

## 📝 Логирование

```bash
# Включение логирования в файл
{
    "log_to_file": true,
    "log_file": "/path/to/draxon.log"
}

# Подробное логирование
{
    "verbose": true
}
```

## 🔍 Примеры использования

### Загрузка плейлиста с аудио

```bash
python draxon.py -u "https://youtube.com/playlist?list=PLAYLIST_ID||audio,playlist"
```

### Загрузка с ограничением скорости

```bash
python draxon.py -u "https://youtube.com/watch?v=VIDEO_ID" --rate "1M"
```

### Использование профиля

```bash
python draxon.py --profile "audio_only" -u "https://youtube.com/watch?v=VIDEO_ID"
```

### Пакетная загрузка

```bash
# Создайте файл urls.txt
echo "https://youtube.com/watch?v=VIDEO1" > urls.txt
echo "https://youtube.com/watch?v=VIDEO2" >> urls.txt

# Загрузите все
python draxon.py -f urls.txt --parallel
```

## 🛠️ Разработка

### Структура проекта

```
draxon/
├── draxon.py          # Основной файл
├── requirements.txt    # Зависимости
├── README.md          # Документация
└── LICENSE            # Лицензия
```

### Зависимости

- `yt-dlp` — движок загрузки
- `rich` — красивое отображение в терминале
- `pathlib` — работа с путями (встроено)
- `concurrent.futures` — параллельные загрузки (встроено)

## 🤝 Вклад в проект

1. Форкните репозиторий
2. Создайте ветку для новой функции
3. Внесите изменения
4. Создайте Pull Request

## 📄 Лицензия

Этот проект распространяется под лицензией GNU GENERAL PUBLIC LICENSE, указанной в файле `LICENSE`.

## 🆘 Поддержка

Если у вас возникли проблемы или есть предложения:

1. Проверьте документацию
2. Создайте Issue в репозитории
3. Опишите проблему подробно

## 🎯 Roadmap

- [ ] Поддержка других платформ
- [ ] Веб-интерфейс
- [ ] API для интеграции
- [ ] Планировщик загрузок
- [ ] Уведомления о завершении

---