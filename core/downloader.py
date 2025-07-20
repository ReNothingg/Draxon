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
            print(f"Ошибка yt-dlp: {e}")
            return None

    def download(self, url: str, is_audio_only: bool, progress_hook):
        config = get_config()
        download_path = config.get("download_path")
        
        format_note = "Аудио (mp3)" if is_audio_only else "Видео (mp4)"
        
        ydl_opts = {
            'progress_hooks': [progress_hook],
            'outtmpl': f'{download_path}/%(title)s.%(ext)s',
            'noplaylist': False, 
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
            return True, format_note
        except Exception as e:
            
            print(e)
            return False, format_note