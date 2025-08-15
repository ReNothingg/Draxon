import os
import yt_dlp
from tqdm import tqdm

class TqdmProgressHook:
    def __init__(self, t):
        self.t = t

    def __call__(self, d):
        if d['status'] == 'downloading':
            total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate')
            if total_bytes:
                self.t.total = total_bytes
                self.t.update(d['downloaded_bytes'] - self.t.n)
        elif d['status'] == 'finished':
            if self.t.total is None:
                self.t.total = self.t.n
            self.t.close()

def get_download_path():
    print("\nКуда вы хотите сохранить файл?")
    print("Нажмите Enter, чтобы сохранить в текущей папке, или введите путь.")
    path = input(">>> ").strip()
    if not path:
        return os.getcwd()
    if not os.path.isdir(path):
        print("\n[!] Указанный путь не существует. Файл будет сохранен в текущей папке.")
        return os.getcwd()
    return path

def select_resolution(formats):
    print("\nДоступные разрешения видео:")
    video_formats = []
    for f in formats:
        if f.get('vcodec') != 'none' and f.get('acodec') != 'none' and f.get('ext') == 'mp4':
            height = f.get('height')
            if height:
                resolution = f"{height}p"
                if resolution not in [vf['res'] for vf in video_formats]:
                     video_formats.append({'id': f['format_id'], 'res': resolution})
    
    video_formats = sorted(video_formats, key=lambda x: int(x['res'][:-1]), reverse=True)

    if not video_formats:
        print("\n[!] Не удалось найти подходящих видеоформатов mp4 с аудио.")
        return None

    for i, vf in enumerate(video_formats):
        print(f"  [{i+1}] {vf['res']}")

    while True:
        try:
            choice = int(input("\nВыберите номер разрешения >>> ")) - 1
            if 0 <= choice < len(video_formats):
                return video_formats[choice]['id']
            else:
                print("[!] Неверный выбор. Попробуйте снова.")
        except ValueError:
            print("[!] Пожалуйста, введите число.")

def download_video(url, path):
    try:
        with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
            info_dict = ydl.extract_info(url, download=False)
            formats = info_dict.get('formats', [])
    except yt_dlp.utils.DownloadError as e:
        print(f"\n[!] Ошибка: Не удалось получить информацию о видео. {e}")
        return

    format_id = select_resolution(formats)
    if not format_id:
        return

    ydl_opts = {
        'format': format_id,
        'outtmpl': os.path.join(path, '%(title)s.%(ext)s'),
        'noprogress': True,
        'quiet': True,
    }

    print(f"\nНачинается скачивание видео: {info_dict['title']}")
    with tqdm(total=None, unit='B', unit_scale=True, desc='Прогресс') as t:
        ydl_opts['progress_hooks'] = [TqdmProgressHook(t)]
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            print("\n[+] Видео успешно скачано!")
        except Exception as e:
            print(f"\n[!] Произошла ошибка при скачивании: {e}")


def download_audio(url, path):
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'outtmpl': os.path.join(path, '%(title)s.%(ext)s'),
        'noprogress': True,
        'quiet': True,
    }

    try:
        with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
            info_dict = ydl.extract_info(url, download=False)
        print(f"\nНачинается скачивание аудио: {info_dict['title']}")
    except yt_dlp.utils.DownloadError as e:
        print(f"\n[!] Ошибка: Не удалось получить информацию о видео. {e}")
        return

    with tqdm(total=None, unit='B', unit_scale=True, desc='Прогресс') as t:
        ydl_opts['progress_hooks'] = [TqdmProgressHook(t)]
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            print("\n[+] Аудио успешно скачано!")
        except Exception as e:
            print(f"\n[!] Произошла ошибка при скачивании. Убедитесь, что у вас установлен FFmpeg. {e}")

def main():
    print("===================================")
    print(" Draxon Video Downloader v1.0")
    print("===================================")
    
    url = input("\nВведите URL видео >>> ").strip()
    
    print("\nЧто вы хотите скачать?")
    print("  [1] Видео")
    print("  [2] Только аудио (mp3)")

    while True:
        choice = input("\nВыберите опцию (1 или 2) >>> ").strip()
        if choice in ['1', '2']:
            break
        else:
            print("[!] Неверный выбор. Пожалуйста, введите 1 или 2.")

    path = get_download_path()

    if choice == '1':
        download_video(url, path)
    elif choice == '2':
        download_audio(url, path)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[!] Программа прервана пользователем. Выход.")