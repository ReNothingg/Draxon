from typing import Any, Dict, List, NamedTuple, Optional

class FormatInfo(NamedTuple):
    id: str
    label: str
    filesize: Optional[int]

def _format_filesize(b: Optional[int]) -> str:
    if b is None:
        return "N/A"
    if b < 1024:
        return f"{b} B"
    elif b < 1024**2:
        return f"{b/1024:.2f} KiB"
    elif b < 1024**3:
        return f"{b/1024**2:.2f} MiB"
    else:
        return f"{b/1024**3:.2f} GiB"

def parse_formats(info_dict: Dict[str, Any]) -> tuple[List[FormatInfo], List[FormatInfo]]:
    formats = info_dict.get("formats", [])
    video_formats: List[FormatInfo] = []
    audio_formats: List[FormatInfo] = []

    seen_video_labels = set()
    seen_audio_labels = set()

    sorted_formats = sorted(
        formats,
        key=lambda f: (f.get("height", 0), f.get("tbr", 0) or f.get("abr", 0)),
        reverse=True,
    )

    for f in sorted_formats:
        format_id = f.get("format_id")
        if not format_id:
            continue

        filesize = f.get("filesize") or f.get("filesize_approx")
        ext = f.get("ext")

        if f.get("vcodec") != "none" and f.get("acodec") != "none":
            height = f.get("height")
            if height:
                label = f"{height}p ({ext})"
                if label not in seen_video_labels:
                    video_formats.append(
                        FormatInfo(id=format_id, label=f"{label} - {_format_filesize(filesize)}", filesize=filesize)
                    )
                    seen_video_labels.add(label)

        elif f.get("vcodec") != "none":
            height = f.get("height")
            if height:
                label = f"{height}p ({ext}, video only)"
                if label not in seen_video_labels:
                    video_formats.append(
                        FormatInfo(id=format_id, label=f"{label} - {_format_filesize(filesize)}", filesize=filesize)
                    )
                    seen_video_labels.add(label)

        elif f.get("acodec") != "none":
            abr = f.get("abr")
            if abr:
                label = f"{int(abr)}k ({ext})"
                if label not in seen_audio_labels:
                    audio_formats.append(
                        FormatInfo(id=format_id, label=f"{label} - {_format_filesize(filesize)}", filesize=filesize)
                    )
                    seen_audio_labels.add(label)

    if not audio_formats:
        best_audio = info_dict.get("audio_ext")
        if best_audio != "none":
            audio_formats.append(FormatInfo(id="bestaudio/best", label="Best Audio", filesize=None))

    if not video_formats:
        video_formats.append(FormatInfo(id="bestvideo/best", label="Best Video", filesize=None))

    return video_formats, audio_formats