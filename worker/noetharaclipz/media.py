import hashlib
import json
import math
import subprocess
from pathlib import Path
from .models import Edit

RATIOS = {"9:16": (720, 1280), "16:9": (1280, 720), "1:1": (720, 720), "4:5": (720, 900)}


class Cancelled(Exception):
    pass


def run(args, timeout=300, tick=None):
    """No shell, no stdin, bounded wall time; drain output without pipe deadlocks."""
    import tempfile
    import time

    with tempfile.TemporaryFile() as log:
        process = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=log, stderr=log)
        start = time.monotonic()
        try:
            while process.poll() is None:
                if time.monotonic() - start > timeout:
                    raise TimeoutError("Media operation timed out")
                if tick:
                    tick()
                time.sleep(0.3)
            log.seek(0)
            output = log.read().decode(errors="replace")
            if process.returncode:
                raise RuntimeError("Media operation failed: " + output[-1500:])
            return output
        finally:
            if process.poll() is None:
                process.kill()
            process.wait()


def probe(path):
    result = run(
        [
            "ffprobe",
            "-v",
            "error",
            "-protocol_whitelist",
            "file,pipe",
            "-format_whitelist",
            "mov,matroska,webm",
            "-show_format",
            "-show_streams",
            "-of",
            "json",
            str(path),
        ],
        60,
    )
    meta = json.loads(result)
    stream = next((s for s in meta["streams"] if s["codec_type"] == "video"), None)
    if not stream:
        raise ValueError("No video stream found")
    duration = float(meta["format"].get("duration", 0))
    if not math.isfinite(duration) or not 0 < duration <= 300:
        raise ValueError("Video duration must be at most five minutes")
    if stream["width"] > 4096 or stream["height"] > 4096:
        raise ValueError("Input dimensions exceed the MVP limit of 4096 pixels")
    num, den = map(float, stream.get("avg_frame_rate", "0/1").split("/"))
    fps = num / den if den else 0
    if fps > 120:
        raise ValueError("Input frame rate exceeds 120 fps")
    return {
        "duration": duration,
        "width": stream["width"],
        "height": stream["height"],
        "fps": fps,
        "has_audio": any(s["codec_type"] == "audio" for s in meta["streams"]),
    }


def ffmpeg(source, *args):
    return [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostdin",
        "-y",
        "-threads",
        "2",
        "-protocol_whitelist",
        "file,pipe",
        "-format_whitelist",
        "mov,matroska,webm",
        "-i",
        str(source),
        *map(str, args),
    ]


def prepare(source, directory, tick=None):
    import cv2
    import numpy as np
    from scenedetect import open_video, SceneManager, ContentDetector

    meta = probe(source)
    proxy = directory / "playback.mp4"
    run(
        ffmpeg(
            source,
            "-map",
            "0:v:0",
            "-map",
            "0:a:0?",
            "-vf",
            "scale=1280:720:force_original_aspect_ratio=decrease:force_divisible_by=2,setsar=1",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "25",
            "-maxrate",
            "800k",
            "-bufsize",
            "1600k",
            "-r",
            "30",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "64k",
            "-movflags",
            "+faststart",
            proxy,
        ),
        600,
        tick,
    )
    thumbnail = directory / "thumbnail.jpg"
    run(ffmpeg(proxy, "-ss", min(1, meta["duration"] / 2), "-frames:v", "1", thumbnail), 60, tick)
    waveform = []
    events = []
    audio = directory / "audio.wav"
    if meta["has_audio"]:
        run(
            ffmpeg(source, "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", audio), 120, tick
        )
        import wave

        with wave.open(str(audio)) as wav:
            samples = (
                np.frombuffer(wav.readframes(wav.getnframes()), dtype=np.int16).astype(float)
                / 32768
            )
        chunks = np.array_split(samples, min(600, max(1, int(meta["duration"] * 4))))
        levels = [float(np.sqrt(np.mean(c * c))) if len(c) else 0 for c in chunks]
        peak = max(levels, default=0)
        waveform = [round(x / peak, 4) if peak else 0 for x in levels]
        for i, x in enumerate(levels):
            if (peak and x > peak * 0.8) or x < 0.008:
                events.append(
                    {
                        "time": round(i * meta["duration"] / len(levels), 3),
                        "kind": "intensity" if x >= 0.008 else "silence",
                        "rms": round(x, 4),
                    }
                )
    manager = SceneManager()
    manager.add_detector(ContentDetector(threshold=27))
    manager.detect_scenes(open_video(str(proxy)), show_progress=False)
    scenes = [
        {"start": a.get_seconds(), "end": b.get_seconds()} for a, b in manager.get_scene_list()
    ]
    # Frames come from actual scene boundaries and uniform coverage.
    times = sorted(
        set([i * meta["duration"] / 11 for i in range(12)] + [s["start"] for s in scenes])
    )[:48]
    capture = cv2.VideoCapture(str(proxy))
    frames = []
    for i, t in enumerate(times):
        if tick:
            tick()
        capture.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, frame = capture.read()
        if ok:
            dest = directory / f"frame-{i}.jpg"
            cv2.imwrite(str(dest), frame)
            frames.append({"time": round(t, 3), "file": dest})
    capture.release()
    with source.open("rb") as source_file:
        digest = hashlib.file_digest(source_file, "sha256").hexdigest()
    return {
        "metadata": meta,
        "proxy": proxy,
        "thumbnail": thumbnail,
        "audio": audio if meta["has_audio"] else None,
        "waveform": waveform,
        "audio_events": events[:1000],
        "scenes": scenes,
        "frames": frames,
        "source_hash": digest,
    }


def transcribe(audio, model="small", tick=None):
    if audio is None:
        return []
    from faster_whisper import WhisperModel

    whisper = WhisperModel(model, device="cpu", compute_type="int8", cpu_threads=2)
    segments, _ = whisper.transcribe(str(audio), word_timestamps=True, vad_filter=True, beam_size=3)
    results = []
    for i, s in enumerate(segments):
        if tick:
            tick()
        results.append(
            {
                "id": str(i),
                "start": s.start,
                "end": s.end,
                "text": s.text.strip(),
                "words": [{"start": w.start, "end": w.end, "text": w.word} for w in s.words or []],
            }
        )
    return results


def ass_time(t):
    centis = max(0, round(t * 100))
    secs, cs = divmod(centis, 100)
    mins, s = divmod(secs, 60)
    h, m = divmod(mins, 60)
    return f"{h}:{m:02}:{s:02}.{cs:02}"


def ass_escape(text):
    # Strip override syntax/control characters, preserve ordinary user text.
    return (
        str(text)
        .replace("\\", "＼")
        .replace("{", "(")
        .replace("}", ")")
        .replace("\r", "")
        .replace("\n", "\\N")
    )


def subtitles(edit, transcript, output, width, height):
    font = {
        "Mono": "DejaVu Sans Mono",
        "Instrument Sans": "Instrument Sans",
        "Bricolage Grotesque": "Bricolage Grotesque",
    }[edit.font]
    color = edit.caption_color[1:]
    primary = "&H00" + color[4:6] + color[2:4] + color[0:2]
    size = round(edit.caption_size * width / 360)
    header = f"""[Script Info]\nScriptType: v4.00+\nPlayResX: {width}\nPlayResY: {height}\nWrapStyle: 0\n[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\nStyle: Default,{font},{size},{primary},&H0000FFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,3,1,2,35,35,{int(height * 0.16)},1\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"""
    events = []
    for s in transcript:
        a = max(edit.start, s["start"])
        b = min(edit.end, s["end"])
        if a >= b:
            continue
        text = edit.caption_overrides.get(str(s["id"]), s["text"])
        if (
            edit.caption_style == "Karaoke"
            and s.get("words")
            and str(s["id"]) not in edit.caption_overrides
        ):
            text = "".join(
                "{\\k"
                + str(max(1, round((min(w["end"], b) - max(w["start"], a)) * 100)))
                + "}"
                + ass_escape(w["text"])
                for w in s["words"]
                if w["end"] > a and w["start"] < b
            )
        else:
            text = ass_escape(text)
            if edit.caption_style == "Bold pop":
                text = "{\\fad(60,60)}" + text
            if edit.caption_style == "Neon":
                text = "{\\blur2\\3c&HFF00FF&}" + text
        events.append(
            f"Dialogue: 0,{ass_time(a - edit.start)},{ass_time(b - edit.start)},Default,,0,0,0,,{text}\n"
        )
    output.write_text(header + "".join(events))


def render(source, edit: Edit, transcript, output: Path, tick=None):
    meta = probe(source)
    if edit.end > meta["duration"]:
        raise ValueError("Clip ends beyond the source")
    w, h = RATIOS[edit.ratio]
    ratio = w / h
    filters = [
        f"crop=w='min(iw,ih*{ratio})':h='min(ih,iw/{ratio})':x='(iw-ow)*{edit.crop_x}':y='(ih-oh)*{edit.crop_y}'",
        f"scale={w}:{h}",
        "setsar=1",
    ]
    if edit.captions:
        ass = output.parent / "captions.ass"
        subtitles(edit, transcript, ass, w, h)
        # The path is generated in a private temp directory, never supplied by a user.
        filters.append(
            "ass="
            + str(ass).replace("\\", "/").replace(":", "\\:")
            + ":fontsdir="
            + str(Path(__file__).resolve().parents[1] / "fonts")
        )
    args = ffmpeg(
        source,
        "-ss",
        edit.start,
        "-t",
        edit.end - edit.start,
        "-map",
        "0:v:0",
        "-map",
        "0:a:0?",
        "-vf",
        ",".join(filters),
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "22",
        "-maxrate",
        "3500k",
        "-bufsize",
        "7000k",
        "-threads",
        "2",
        "-pix_fmt",
        "yuv420p",
        "-r",
        "30",
    )
    if meta["has_audio"]:
        args += ["-af", f"volume={edit.volume}", "-c:a", "aac", "-b:a", "128k"]
    run(args + ["-movflags", "+faststart", str(output)], 600, tick)
    result = probe(output)
    if (
        (result["width"], result["height"]) != (w, h)
        or abs(result["duration"] - (edit.end - edit.start)) > 0.25
        or not 0 < output.stat().st_size <= 45000000
    ):
        raise ValueError("Rendered file failed output validation")
    # A full decode catches truncated files that still have plausible container metadata.
    run(ffmpeg(output, "-f", "null", "-"), 120, tick)
    return result
