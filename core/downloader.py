import yt_dlp
from .config import get_config

class Downloader:
    def get_video_info(self, url: str):
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': 'in_playlist',
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                return info
        except yt_dlp.utils.DownloadError as e:
            print(f"Ошибка yt-dlp при получении информации: {e}")
            return None

    def download(self, url: str, is_audio_only: bool, progress_hook):
        config = get_config()
        download_path = config.get("download_path")
        
        output_template = f'{download_path}/%(title)s [%(id)s].%(ext)s'
        
        ydl_opts = {
            'progress_hooks': [progress_hook],
            'outtmpl': output_template,
            'noplaylist': False, 
            'ignoreerrors': True,
        }

        if is_audio_only:
            ydl_opts.update({
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
            })
        else:
            ydl_opts.update({
                'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            })

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            return True, "Загрузка завершена"
        except yt_dlp.utils.DownloadError as e:
            error_message = str(e).split('ERROR: ')[-1].strip()
            return False, error_message
        except Exception as e:
            return False, str(e)