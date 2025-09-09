import re
import argparse
import os
import tempfile
import json
from pathlib import Path

try:
    from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
except Exception as e:
    YouTubeTranscriptApi = None
    TranscriptsDisabled = NoTranscriptFound = Exception

try:
    import yt_dlp as yt_dlp
except Exception:
    yt_dlp = None

try:
    import whisper
except Exception:
    whisper = None


def extract_video_id(url_or_id: str) -> str:
    s = url_or_id.strip()

    if re.fullmatch(r"[A-Za-z0-9_\-]{10,}", s):
        return s

    m = re.search(r"(?:v=)([A-Za-z0-9_\-]{10,})", s)
    if m:
        return m.group(1)

    m = re.search(r"youtu\.be/([A-Za-z0-9_\-]{10,})", s)
    if m:
        return m.group(1)

    m = re.search(r"embed/([A-Za-z0-9_\-]{10,})", s)
    if m:
        return m.group(1)

    m = re.search(r"/([A-Za-z0-9_\-]{10,})$", s)
    if m:
        return m.group(1)
    raise ValueError("Не удалось извлечь id видео из строки: " + url_or_id)

def save_as_srt(transcript, out_path):
    with open(out_path, "w", encoding="utf-8") as f:
        for i, seg in enumerate(transcript, start=1):
            start = seg.get("start", 0.0)
            dur = seg.get("duration", 0.0)
            end = start + dur
            def fmt(t):
                h = int(t // 3600)
                m = int((t % 3600) // 60)
                s = int(t % 60)
                ms = int((t - int(t)) * 1000)
                return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
            f.write(f"{i}\n{fmt(start)} --> {fmt(end)}\n{seg.get('text','').strip()}\n\n")
    print(f"[+] SRT сохранён: {out_path}")


def try_get_youtube_transcript(video_id, languages=None, translate=False):
    if YouTubeTranscriptApi is None:
        raise RuntimeError("youtube_transcript_api не установлен. pip install youtube-transcript-api")

    try:
        if languages:
            transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=languages)
        else:
            transcript = YouTubeTranscriptApi.get_transcript(video_id)
        return transcript
    except Exception as e:

        try:
            ts = YouTubeTranscriptApi.list_transcripts(video_id)
            chosen = None
            if languages:
                for lang in languages:
                    try:
                        chosen = ts.find_transcript([lang])
                        break
                    except:
                        try:
                            chosen = ts.find_generated_transcript([lang])
                            break
                        except:
                            pass

            if not chosen:
                try:
                    chosen = ts.find_transcript(ts._transcripts.keys())
                except:
                    chosen = None

            if chosen:
                if translate and languages:
                    target = languages[0]
                    try:
                        translated = chosen.translate(target)
                        return translated.fetch()
                    except Exception:
                        pass
                return chosen.fetch()
        except Exception:
            pass
        raise

def download_audio_with_ytdlp(url, out_file):
    if yt_dlp is None:
        raise RuntimeError("yt-dlp не установлен. pip install yt-dlp")
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": out_file,
        "quiet": True,
        "no_warnings": True,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "wav",
            "preferredquality": "192",
        }],
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

def transcribe_with_whisper(audio_path, model_name="small", language=None):
    if whisper is None:
        raise RuntimeError("whisper (openai-whisper) не установлен.")
    print(f"Загружаю модель Whisper: {model_name}")
    model = whisper.load_model(model_name)

    options = {}
    if language:
        options["language"] = language
    result = model.transcribe(audio_path, **options)

    return result

def main():
    p = argparse.ArgumentParser(description="Скачать субтитры с YouTube (или сгенерировать через ASR)")
    p.add_argument("url", help="YouTube URL или id")
    p.add_argument("--langs", default="ru,en", help="Список языков приоритета через запятую (например: ru,en,auto)")
    p.add_argument("--translate", action="store_true", help="Попробовать перевести субтитры в первый язык из --langs")
    p.add_argument("--model", default="small", help="Whisper model (tiny,base,small,medium,large или turbo)")
    p.add_argument("--out", default=None, help="Путь для сохранения .srt (по умолчанию: <videoid>.srt)")
    p.add_argument("--keep-audio", action="store_true", help="Не удалять временный аудиофайл")
    args = p.parse_args()

    try:
        vid = extract_video_id(args.url)
    except Exception as e:
        print("Ошибка: не удалось извлечь id видео.", e)
        return

    langs = [x.strip() for x in args.langs.split(",") if x.strip()]
    out_srt = args.out or f"{vid}.srt"

    try:
        print("Пробую получить субтитры через youtube_transcript_api (включая автогенерацию)...")
        transcript = try_get_youtube_transcript(vid, languages=langs, translate=args.translate)
        save_as_srt(transcript, out_srt)
        print("Готово — субтитры получены напрямую с YouTube.")
        return
    except TranscriptsDisabled:
        print("Субтитры отключены владельцем видео.")
    except NoTranscriptFound:
        print("Субтитры не найдены (ни ручные, ни автогенерируемые).")
    except Exception as e:
        print("Не удалось получить транскрипт через API:", str(e))

    print("Переход к скачиванию аудио и локальной транскрипции (Whisper).")
    tmpdir = tempfile.mkdtemp(prefix="yt_subs_")
    outtmpl = os.path.join(tmpdir, "%(id)s.%(ext)s")
    try:
        audio_target = os.path.join(tmpdir, f"{vid}.wav")
        print("[*] Скачиваю аудио (yt-dlp -> wav). Это может занять время...")
        download_audio_with_ytdlp(args.url, outtmpl)

        cand = Path(tmpdir) / f"{vid}.wav"
        if not cand.exists():

            files = list(Path(tmpdir).glob("*.wav"))
            if files:
                cand = files[0]
            else:
                raise FileNotFoundError("Не удалось найти скачанный .wav в " + tmpdir)
        audio_target = str(cand)
        print(f"Аудиофайл: {audio_target}")

        res = transcribe_with_whisper(audio_target, model_name=args.model, language=(langs[0] if langs else None))

        segments = res.get("segments")
        if segments:
            transcript = []
            for seg in segments:
                transcript.append({
                    "text": seg.get("text", "").strip(),
                    "start": float(seg.get("start", 0.0)),
                    "duration": float(seg.get("end", 0.0) - seg.get("start", 0.0)),
                })
            save_as_srt(transcript, out_srt)
        else:
            save_as_srt([{"text": res.get("text","").strip(), "start":0.0, "duration":1.0}], out_srt)

        print("Транскрипция завершена.")
    except Exception as e:
        print("[ERROR]", e)
    finally:
        if not args.keep_audio:
            try:

                import shutil
                shutil.rmtree(tmpdir)
            except Exception:
                pass

if __name__ == "__main__":
    main()
