import yt_dlp
from pathlib import Path

from .models import VideoFormat, AudioFormat

class Downloader:
    
    def _format_size(self, filesize: int | None) -> str:
        if filesize is None:
            return "N/A"
        return f"{filesize / 1024 / 1024:.2f} MB"

    def get_video_info(self, url: str) -> dict | None:
        ydl_opts = {'quiet': True, 'no_warnings': True, 'extract_flat': 'in_playlist'}
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(url, download=False)
        except yt_dlp.utils.DownloadError as e:
            print(f"Ошибка yt-dlp при получении информации: {e}")
            return None

    def get_filtered_formats(self, info: dict) -> tuple[list[VideoFormat], list[AudioFormat]]:
        video_formats = []
        audio_formats = []
        
        for f in info.get('formats', []):
            if f.get('acodec') != 'none' and f.get('vcodec') == 'none' and f.get('abr'):
                filesize = f.get('filesize') or f.get('filesize_approx')
                audio_formats.append(AudioFormat(
                    id=f['format_id'], abr=f.get('abr'), ext=f['ext'],
                    size_mb=self._format_size(filesize)
                ))
        audio_formats.sort(key=lambda x: x.abr or 0, reverse=True)

        processed_res_fps = set()
        for f in info.get('formats', []):
            if f.get('vcodec') == 'none' or not f.get('resolution'):
                continue
            format_key = (f.get('resolution'), f.get('fps'))
            if format_key in processed_res_fps:
                continue
            filesize = f.get('filesize') or f.get('filesize_approx')
            is_merged = f.get('acodec') != 'none'
            video_formats.append(VideoFormat(
                id=f['format_id'], res=f.get('resolution'), fps=f.get('fps'),
                ext=f['ext'], size_mb=self._format_size(filesize),
                is_merged=is_merged
            ))
            processed_res_fps.add(format_key)

        video_formats.sort(key=lambda x: (int(x.res.split('x')[1]), x.fps or 0), reverse=True)
        return video_formats, audio_formats

    def _get_format_selector(self, quality: str) -> str:
        if quality == 'best':
            return 'bestvideo+bestaudio/best'
        if quality == '1080p':
            return 'bestvideo[height<=1080]+bestaudio/best[height<=1080]'
        if quality == '720p':
            return 'bestvideo[height<=720]+bestaudio/best[height<=720]'
        return 'bestvideo+bestaudio/best' # Fallback

    def download(self, url: str, download_path: Path, progress_hook, *,
                 video_format_id: str | None = None,
                 audio_format_id: str | None = None,
                 playlist_quality: str | None = None,
                 audio_only: bool = False,
                 convert_to_mp3: bool = False):
        
        output_template = str(download_path / '%(title)s [%(id)s].%(ext)s')
        ydl_opts = {'progress_hooks': [progress_hook], 'outtmpl': output_template}

        if audio_only:
            ydl_opts['format'] = 'bestaudio/best'
            if convert_to_mp3:
                ydl_opts['postprocessors'] = [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}]
        elif playlist_quality:
            ydl_opts['format'] = self._get_format_selector(playlist_quality)
            ydl_opts['merge_output_format'] = 'mp4'
            ydl_opts['ignoreerrors'] = True
            ydl_opts['extract_flat'] = False
        elif video_format_id and audio_format_id:
            ydl_opts['format'] = f"{video_format_id}+{audio_format_id}"
            ydl_opts['merge_output_format'] = 'mp4'
        elif video_format_id:
            ydl_opts['format'] = video_format_id
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            return True, "Загрузка успешно завершена.", str(download_path)
        except yt_dlp.utils.DownloadError as e:
            error_message = str(e).split('ERROR: ')[-1].strip()
            return False, error_message, None
        except Exception as e:
            return False, str(e), None