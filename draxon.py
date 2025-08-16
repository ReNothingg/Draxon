import os
import sys
import json
import logging
import shutil
import subprocess
import concurrent.futures
import re

import yt_dlp

CONFIG_FILE = "draxon.json"

DEFAULT_CONFIG = {
    "output_dir": os.getcwd(),
    "output_template": "%(title)s.%(ext)s",
    "video_format": "best",
    "subtitles_languages": "en,ru",
    "proxy": "",
    "rate_limit": "",
    "resume_download": True,
    "verbose": False,
    "log_to_file": False,
    "log_file": "draxon.log",
    "parallel_download": False,
    "max_workers": 2
}

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
            return {**DEFAULT_CONFIG, **config}
        except Exception as e:
            print(f"Ошибка загрузки конфигурации: {e}")
            return DEFAULT_CONFIG.copy()
    else:
        return DEFAULT_CONFIG.copy()

def save_config(config):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
        print("Настройки сохранены в", CONFIG_FILE)
    except Exception as e:
        print(f"Ошибка сохранения конфигурации: {e}")

def check_dependencies(extract_audio):
    if extract_audio:
        if shutil.which("ffmpeg") is None:
            print("ВНИМАНИЕ: ffmpeg не найден в PATH. Для извлечения аудио установите ffmpeg.")

def parse_rate_limit(rate_str):
    if not rate_str:
        return None
    rate_str = rate_str.strip().upper()
    match = re.match(r'^(\d+(?:\.\d+)?)([KMG]?)$', rate_str)
    if not match:
        return None
    number, unit = match.groups()
    try:
        number = float(number)
    except ValueError:
        return None
    multiplier = 1
    if unit == "K":
        multiplier = 1024
    elif unit == "M":
        multiplier = 1024 ** 2
    elif unit == "G":
        multiplier = 1024 ** 3
    return int(number * multiplier)

def is_valid_url(url):
    return url.startswith("http://") or url.startswith("https://")

def check_updates():
    try:
        result = subprocess.run(["yt-dlp", "--version"], capture_output=True, text=True)
        if result.returncode == 0:
            version = result.stdout.strip()
            print(f"Установленная версия yt-dlp: {version}")
            print("Рекомендуется периодически проверять обновления: pip install --upgrade yt-dlp")
        else:
            print("Не удалось получить версию yt-dlp.")
    except Exception as e:
        print("Ошибка при проверке версии yt-dlp:", e)

def download_hook(d):
    if d['status'] == 'downloading':
        progress = d.get('_percent_str', '0%')
        speed = d.get('_speed_str', 'N/A')
        eta = d.get('_eta_str', 'N/A')
        print(f"Загрузка: {progress} | Скорость: {speed} | ETA: {eta}   ", end='\r')
    elif d['status'] == 'finished':
        print("\nСкачивание завершено. Обработка файла...")

def download_video_single(url, ydl_opts):
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            logging.info(f"Начало скачивания: {url}")
            ydl.download([url])
    except Exception as e:
        logging.error(f"Ошибка при скачивании {url}: {e}")

def main():
    config = load_config()

    print("=== YouTube Downloader ===")
    print("Используются сохранённые настройки по умолчанию (из файла):")
    for key, value in config.items():
        print(f"  {key}: {value}")
    print()

    upd = input("Проверить наличие обновлений yt-dlp? (y/N): ").strip().lower()
    if upd == 'y':
        check_updates()
    print()

    mode = input("Ввести URL вручную или из файла? (manual/file) [manual]: ").strip().lower()
    urls = []
    if mode == "file":
        file_path = input("Введите путь к файлу с URL (один URL на строку): ").strip()
        if not os.path.exists(file_path):
            print("Файл не найден. Завершение.")
            sys.exit(1)
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and is_valid_url(line):
                    urls.append(line)
                elif line:
                    print(f"Неверный URL пропущен: {line}")
    else:
        urls_input = input("Введите URL(ы) через пробел: ").strip()
        for url in urls_input.split():
            if is_valid_url(url):
                urls.append(url)
            else:
                print(f"Неверный URL пропущен: {url}")

    if not urls:
        print("Нет корректных URL для загрузки. Завершение.")
        sys.exit(1)

    out_dir = input(f"Директория сохранения [{config['output_dir']}]: ").strip() or config['output_dir']
    if not os.path.exists(out_dir):
        create_dir = input(f"Директория '{out_dir}' не существует. Создать? (y/n): ").strip().lower()
        if create_dir == "y":
            try:
                os.makedirs(out_dir)
                print(f"Директория '{out_dir}' создана.")
            except Exception as e:
                print(f"Не удалось создать директорию: {e}")
                sys.exit(1)
        else:
            print("Завершение.")
            sys.exit(1)
    output_template = input(f"Шаблон имени файла [{config['output_template']}]: ").strip() or config['output_template']
    video_format = input(f"Формат видео [{config['video_format']}]: ").strip() or config['video_format']
    playlist_input = input("Скачать плейлист полностью, если ссылка на него? (y/N): ").strip().lower()
    playlist = True if playlist_input == "y" else False
    audio_input = input("Извлечь аудио и сохранить как mp3? (y/N): ").strip().lower()
    extract_audio = True if audio_input == "y" else False
    subtitles_input = input(f"Языки субтитров через запятую [{config['subtitles_languages']}]: ").strip() or config['subtitles_languages']
    subtitles = True if subtitles_input else False
    proxy = input(f"Прокси-сервер [{config['proxy']}]: ").strip() or config['proxy']
    rate_limit_input = input(f"Ограничение скорости (например, 500K, 1M) [{config['rate_limit']}]: ").strip() or config['rate_limit']
    resume_input = input(f"Продолжить прерванные загрузки? (Y/n) [Y]: ").strip().lower()
    resume_download = False if resume_input == "n" else True
    verbose_input = input(f"Включить подробное логирование? (y/N): ").strip().lower()
    verbose = True if verbose_input == "y" else False
    log_to_file_input = input(f"Сохранять лог в файл? (y/N) [{'y' if config['log_to_file'] else 'N'}]: ").strip().lower()
    log_to_file = True if log_to_file_input == "y" else False
    log_file = config['log_file']
    if log_to_file:
        log_file_input = input(f"Путь к лог-файлу [{config['log_file']}]: ").strip()
        if log_file_input:
            log_file = log_file_input

    parallel_input = input(f"Скачать видео параллельно (при нескольких URL)? (y/N): ").strip().lower()
    parallel_download = True if parallel_input == "y" else False
    max_workers = config['max_workers']
    if parallel_download:
        try:
            max_workers_input = input(f"Число потоков (max_workers) [{config['max_workers']}]: ").strip()
            if max_workers_input:
                max_workers = int(max_workers_input)
        except ValueError:
            print("Неверное число, используется значение по умолчанию.")

    config["output_dir"] = out_dir
    config["output_template"] = output_template
    config["video_format"] = video_format
    config["subtitles_languages"] = subtitles_input
    config["proxy"] = proxy
    config["rate_limit"] = rate_limit_input
    config["resume_download"] = resume_download
    config["verbose"] = verbose
    config["log_to_file"] = log_to_file
    config["log_file"] = log_file
    config["parallel_download"] = parallel_download
    config["max_workers"] = max_workers

    save_choice = input("Сохранить эти настройки как стандартные? (y/N): ").strip().lower()
    if save_choice == "y":
        save_config(config)

    log_handlers = [logging.StreamHandler()]
    if log_to_file:
        try:
            file_handler = logging.FileHandler(log_file, encoding="utf-8")
            log_handlers.append(file_handler)
        except Exception as e:
            print("Ошибка создания лог-файла:", e)
    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO,
                        format="%(asctime)s - %(levelname)s - %(message)s",
                        handlers=log_handlers)

    check_dependencies(extract_audio)

    outtmpl_full = os.path.join(out_dir, output_template)
    ydl_opts = {
        "format": video_format,
        "outtmpl": outtmpl_full,
        "noplaylist": not playlist,
        "progress_hooks": [download_hook],
        "continuedl": resume_download
    }
    if extract_audio:
        ydl_opts["format"] = "bestaudio/best"
        ydl_opts["postprocessors"] = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192"
        }]
    if subtitles:
        langs = [lang.strip() for lang in subtitles_input.split(",") if lang.strip()]
        if langs:
            ydl_opts["writesubtitles"] = True
            ydl_opts["subtitleslangs"] = langs
            ydl_opts["subtitlesformat"] = "srt"
    if proxy:
        ydl_opts["proxy"] = proxy
    rate_limit_value = parse_rate_limit(rate_limit_input)
    if rate_limit_value:
        ydl_opts["ratelimit"] = rate_limit_value

    if parallel_download and len(urls) > 1:
        logging.info(f"Запуск параллельного скачивания с {max_workers} потоками...")
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(download_video_single, url, ydl_opts) for url in urls]
            for future in concurrent.futures.as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    logging.error(f"Ошибка в параллельном скачивании: {e}")
    else:
        for url in urls:
            download_video_single(url, ydl_opts)

    print("\nВсе загрузки завершены.")

if __name__ == '__main__':
    main()
