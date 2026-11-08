"""Explicit local provider with persistent, versioned media/ASR/inference caches."""

import hashlib
import json
import os
import shutil
import time
from pathlib import Path
from .local_detector import LocalVideoRanker, MODEL, REVISION, detect
from .media import prepare, transcribe, whisper_engine
from .models import Analysis

MEDIA_CACHE_VERSION = "local-queue-v2-uniform4-speech-bounds"
CACHE_VERSION = "local-queue-v3-empty-admission-speech-bounds"


def available_memory():
    free = os.sysconf("SC_AVPHYS_PAGES") * os.sysconf("SC_PAGE_SIZE")
    try:
        limit = Path("/sys/fs/cgroup/memory.max").read_text().strip()
        if limit != "max":
            free = min(free, int(limit) - int(Path("/sys/fs/cgroup/memory.current").read_text()))
    except (OSError, ValueError):
        pass
    return free


class LocalProvider:
    name = "local-smolvlm2"
    model = MODEL + "@" + REVISION

    def __init__(self, settings, ranker=None):
        self.settings = settings
        self.ranker = ranker
        self.ready = False
        self.root = Path(settings.cache_dir)
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.root.chmod(0o700)
        self.metrics = {}

    def preflight(self):
        if not self.ready:
            if self.ranker is None:
                if available_memory() < 6 * 1024**3:
                    raise RuntimeError(
                        "Local model needs at least 6 GiB available; use one CPU worker"
                    )
                self.ranker = LocalVideoRanker()
                whisper_engine(self.settings.whisper_model)
            self.ready = True
        return {"provider": self.name, "model": self.model, "ready": self.ready}

    def _identity(self, source):
        with source.open("rb") as f:
            digest = hashlib.file_digest(f, "sha256").hexdigest()
        key = hashlib.sha256(
            (digest + MEDIA_CACHE_VERSION + self.settings.whisper_model).encode()
        ).hexdigest()
        directory = self.root / key
        directory.mkdir(exist_ok=True, mode=0o700)
        return digest, directory

    def _write(self, path, value):
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(value))
        temporary.chmod(0o600)
        temporary.replace(path)

    def _prune(self, keep):
        folders = [
            d for d in self.root.iterdir() if d.is_dir() and not d.is_symlink() and d != keep
        ]
        entries = [(d, sum(f.stat().st_size for f in d.rglob("*") if f.is_file())) for d in folders]
        total = sum(size for _, size in entries)
        for d, size in sorted(entries, key=lambda item: item[0].stat().st_mtime):
            if time.time() - d.stat().st_mtime > 86400 or total > 1024**3:
                shutil.rmtree(d)
                total -= size

    def prepare(self, source, tick):
        digest, directory = self._identity(source)
        self._prune(directory)
        marker = directory / "prepared.json"
        if marker.exists():
            saved = json.loads(marker.read_text())
            data = {
                **saved,
                "proxy": directory / "playback.mp4",
                "thumbnail": directory / "thumbnail.jpg",
                "audio": directory / "audio.wav" if saved["metadata"]["has_audio"] else None,
                "frames": [
                    {"time": f["time"], "file": directory / f["file"]} for f in saved["frames"]
                ],
            }
            files = [data["proxy"], data["thumbnail"], *[f["file"] for f in data["frames"]]]
            if data["audio"]:
                files.append(data["audio"])
            if saved["source_hash"] == digest and all(
                p.is_file() and p.stat().st_size for p in files
            ):
                tick()
                self.metrics = {"prepared_cache_hit": True}
                return data
        data = prepare(source, directory, tick)
        saved = {
            k: v for k, v in data.items() if k not in ("proxy", "thumbnail", "audio", "frames")
        }
        saved["frames"] = [{"time": f["time"], "file": f["file"].name} for f in data["frames"]]
        self._write(marker, saved)
        self.metrics = {"prepared_cache_hit": False}
        return data

    def transcript(self, data, tick):
        path = data["proxy"].parent / "transcript.json"
        if path.exists():
            self.metrics["transcript_cache_hit"] = True
            tick()
            return json.loads(path.read_text())
        transcript = transcribe(data["audio"], self.settings.whisper_model, tick)
        self._write(path, transcript)
        self.metrics["transcript_cache_hit"] = False
        return transcript

    def analyze(self, source, data, transcript, prompt, tick):
        self.preflight()
        key = hashlib.sha256((self.model + CACHE_VERSION + prompt).encode()).hexdigest()
        directory = data["proxy"].parent
        path = directory / ("analysis-" + key + ".json")
        tick()
        if path.exists():
            result = json.loads(path.read_text())
            if (
                result["source_hash"] != data["source_hash"]
                or result["model"] != MODEL
                or result["revision"] != REVISION
                or result["prompt"] != prompt
            ):
                raise ValueError("Local analysis cache identity mismatch")
            self.metrics["analysis_cache_hit"] = True
        else:
            started = time.monotonic()
            self.ranker.output_tokens = 0
            self.ranker.description_input_tokens = 0
            with self.ranker.checkpoints(tick):
                result = detect(
                    source,
                    data,
                    transcript,
                    prompt,
                    directory,
                    self.ranker,
                    tick,
                    reuse_candidates=True,
                )
            result["local_usage"] = {
                "input_tokens": result["decision"]["input_tokens"]
                + self.ranker.description_input_tokens,
                "output_tokens": getattr(self.ranker, "output_tokens", 0),
            }
            result["inference_seconds"] = round(time.monotonic() - started, 3)
            self._write(path, result)
            self.metrics["analysis_cache_hit"] = False
        result["execution_usage"] = (
            {"input_tokens": 0, "output_tokens": 0}
            if self.metrics["analysis_cache_hit"]
            else result["local_usage"]
        )
        self.metrics["source_inference_input_tokens"] = result["local_usage"]["input_tokens"]
        self.metrics["admission_rejected"] = bool(result.get("admission_rejected"))
        tick()
        analysis = Analysis(
            summary="\n".join(h["title"] + ": " + h["explanation"] for h in result["highlights"])
            or "No supported local highlight was selected.",
            highlights=result["highlights"],
        )
        return analysis, result, path
