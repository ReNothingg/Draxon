import yt_dlp
from .config import get_config

def format_selector(ctx):
    formats = ctx.get('formats')[::-1]
    best_video = next(
        (f for f in formats if f['vcodec'] != 'none' and f['acodec'] == 'none'), None
    )
    best_audio = next(
        (f for f in formats if f['acodec'] != 'none' and f['vcodec'] == 'none'), None
    )
    yield {
        'format_id': f"{best_video['format_id']}+{best_audio['format_id']}",
        'ext': best_video['ext'],
        'requested_formats': [best_video, best_audio],
        'protocol': f"{best_video['protocol']}+{best_audio['protocol']}"
    }

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
            is_video = f.get('vcodec') != 'none' and f.get('acodec') == 'none'
            is_audio = f.get('acodec') != 'none' and f.get('vcodec') == 'none'

            filesize = f.get('filesize') or f.get('filesize_approx')
            
            if is_video:
                video_formats.append({
                    "id": f['format_id'],
                    "res": f.get('resolution', 'N/A'),
                    "fps": f.get('fps'),
                    "ext": f['ext'],
                    "size_mb": f"{filesize / 1024 / 1024:.2f} MB" if filesize else "N/A",
                    "note": f.get('format_note', '')
                })
            elif is_audio:
                audio_formats.append({
                    "id": f['format_id'],
                    "abr": f.get('abr'),
                    "ext": f['ext'],
                    "size_mb": f"{filesize / 1024 / 1024:.2f} MB" if filesize else "N/A",
                })
        
        video_formats.sort(key=lambda x: (x.get('fps') or 0, int(x['res'].split('x')[1]) if 'x' in x['res'] else 0), reverse=True)
        audio_formats.sort(key=lambda x: x.get('abr') or 0, reverse=True)
        
        return video_formats, audio_formats

    def download(self, url: str, video_format_id: str, audio_format_id: str, progress_hook):
        config = get_config()
        download_path = config.get("download_path")
        output_template = f'{download_path}/%(title)s [%(id)s].%(ext)s'
        
        if video_format_id is None and audio_format_id:
            format_string = audio_format_id
            postprocessors = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }]
        else:
            format_string = f"{video_format_id}+{audio_format_id}"
            postprocessors = []

        ydl_opts = {
            'progress_hooks': [progress_hook],
            'outtmpl': output_template,
            'format': format_string,
            'postprocessors': postprocessors,
            'merge_output_format': 'mp4',
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            return True, "Загрузка завершена"
        except yt_dlp.utils.DownloadError as e:
            error_message = str(e).split('ERROR: ')[-1].strip()
            return False, error_message
        except Exception as e:
            return False, str(e)