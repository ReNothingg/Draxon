import yt_dlp
from .config import get_config

class Downloader:
    def get_video_info(self, url: str):
        ydl_opts = {'quiet': True, 'no_warnings': True}
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                return info
        except yt_dlp.utils.DownloadError as e:
            print(f"Ошибка yt-dlp при получении информации: {e}")
            return None

    def get_filtered_formats(self, info: dict):
        video_formats = []
        audio_formats = []
        
        for f in info.get('formats', []):
            if f.get('acodec') != 'none' and f.get('vcodec') == 'none' and f.get('abr'):
                filesize = f.get('filesize') or f.get('filesize_approx')
                audio_formats.append({
                    "id": f['format_id'], "abr": f.get('abr'), "ext": f['ext'],
                    "size_mb": f"{filesize / 1024 / 1024:.2f} MB" if filesize else "N/A",
                })
        audio_formats.sort(key=lambda x: x.get('abr') or 0, reverse=True)

        processed_formats = set() # Чтобы избежать дубликатов по разрешению и fps

        for f in info.get('formats', []):
            if f.get('vcodec') == 'none' or not f.get('resolution'):
                continue

            format_key = (f.get('resolution'), f.get('fps'))
            if format_key in processed_formats:
                continue

            filesize = f.get('filesize') or f.get('filesize_approx')
            is_merged = f.get('acodec') != 'none'

            video_formats.append({
                "id": f['format_id'], 
                "res": f.get('resolution'), 
                "fps": f.get('fps'),
                "ext": f['ext'], 
                "size_mb": f"{filesize / 1024 / 1024:.2f} MB" if filesize else "N/A",
                "is_merged": is_merged
            })
            processed_formats.add(format_key)

        video_formats.sort(key=lambda x: (int(x['res'].split('x')[1]), x.get('fps') or 0), reverse=True)
        return video_formats, audio_formats

    def download(self, url: str, video_format_id: str | None, audio_format_id: str | None, progress_hook, convert_to_mp3: bool):
        config = get_config()
        download_path = config.get("download_path")
        output_template = f'{download_path}/%(title)s [%(id)s].%(ext)s'
        
        ydl_opts = {'progress_hooks': [progress_hook], 'outtmpl': output_template}

        if video_format_id and audio_format_id:
            ydl_opts['format'] = f"{video_format_id}+{audio_format_id}"
            ydl_opts['merge_output_format'] = 'mp4'
        elif video_format_id:
            ydl_opts['format'] = video_format_id
        elif audio_format_id:
            ydl_opts['format'] = audio_format_id
            if convert_to_mp3:
                ydl_opts['postprocessors'] = [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}]
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            return True, "Загрузка завершена"
        except yt_dlp.utils.DownloadError as e:
            error_message = str(e).split('ERROR: ')[-1].strip()
            return False, error_message
        except Exception as e:
            return False, str(e)