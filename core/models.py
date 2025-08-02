from dataclasses import dataclass

@dataclass(frozen=True)
class AudioFormat:
    id: str
    abr: int
    ext: str
    size_mb: str

@dataclass(frozen=True)
class VideoFormat:
    id: str
    res: str
    fps: int
    ext: str
    size_mb: str
    is_merged: bool

    def get_display_label(self, ffmpeg_available: bool) -> str:
        note = ""
        if not self.is_merged:
            note = "(требуется FFmpeg)" if ffmpeg_available else "[red](FFmpeg не найден)[/red]"
        
        return f"{self.res} @ {self.fps}fps ({self.size_mb}) {note}".strip()