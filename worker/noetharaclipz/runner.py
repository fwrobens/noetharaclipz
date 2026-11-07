import logging
import shutil
import signal
import tempfile
import threading
import time
from pathlib import Path
from .backend import Backend
from .config import Settings
from .media import Cancelled, ffmpeg, prepare, render, run, transcribe
from .models import Candidate, Edit, rank_candidates
from .providers import Gemini

log = logging.getLogger(__name__)


class Lease:
    def __init__(self, backend, job):
        self.backend = backend
        self.job = job
        self.state = "preparing"
        self.progress = 1
        self.detail = "Preparing source"
        self.error = None
        self.started = time.monotonic()
        self.stopped = threading.Event()
        self.thread = None

    def tick(self, force=False):
        if time.monotonic() - self.started > 1200:
            raise TimeoutError("Job exceeded its 20-minute processing limit")
        if self.error:
            raise self.error
        if force:
            ok = self.backend.rpc(
                "worker_tick",
                jid=self.job["id"],
                token=self.job["lease_token"],
                state=self.state,
                pct=self.progress,
                detail=self.detail,
            )
            if not ok:
                raise Cancelled("Job was cancelled")

    def stage(self, state, pct, detail):
        self.state = state
        self.progress = pct
        self.detail = detail
        self.tick(True)

    def __enter__(self):
        self.tick(True)

        def heartbeat():
            while not self.stopped.wait(20):
                try:
                    self.tick(True)
                except Exception as e:
                    self.error = e
                    break

        self.thread = threading.Thread(target=heartbeat, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, *args):
        self.stopped.set()
        self.thread.join(timeout=65)


class Worker:
    def __init__(self, settings=None, backend=None, provider=None):
        self.settings = settings or Settings()
        self.backend = backend or Backend(self.settings)
        self.provider = provider or Gemini(self.settings)

    def process(self, job):
        if job["attempts"] > 3:
            raise RuntimeError("Job retry limit reached")
        with (
            Lease(self.backend, job) as lease,
            tempfile.TemporaryDirectory(prefix="noetharaclipz-") as temp,
        ):
            directory = Path(temp)
            video = self.backend.rows("videos", project_id="eq." + job["project_id"])[0]
            project = self.backend.rows("projects", id="eq." + job["project_id"])[0]
            source = directory / ("source" + Path(video["source_path"]).suffix)
            actual = self.backend.download("source-videos", video["source_path"], source)
            if actual != video["byte_size"]:
                raise ValueError("Source changed since upload")
            if job["kind"] == "render":
                lease.stage("rendering", 10, "Rendering your saved edit")
                artifact = self.backend.rows(
                    "analysis_artifacts", project_id="eq." + job["project_id"]
                )[0]
                output = directory / "clip.mp4"
                edit = Edit.model_validate(job["payload"]["edit"])
                render(source, edit, artifact["transcript"], output, lease.tick)
                lease.stage("rendering", 90, "Saving and validating MP4")
                path = f"{project['owner_id']}/{project['id']}/{job['id']}.mp4"
                self.backend.upload("rendered-clips", path, output, "video/mp4")
                lease.tick(True)
                self.backend.rpc(
                    "worker_finish_render",
                    jid=job["id"],
                    token=job["lease_token"],
                    path=path,
                    bytes=output.stat().st_size,
                )
                return
            if job["kind"] != "analysis":
                raise ValueError("Conversational editing is not enabled in the upload MVP")
            lease.stage("preparing", 5, "Inspecting media and extracting real frames")
            data = prepare(source, directory, lease.tick)
            prefix = f"{project['owner_id']}/{project['id']}"
            # Make real playback and preprocessing usable even when AI credentials are missing.
            self.backend.upload(
                "source-videos", prefix + "/playback.mp4", data["proxy"], "video/mp4"
            )
            self.backend.upload(
                "thumbnails", prefix + "/thumbnail.jpg", data["thumbnail"], "image/jpeg"
            )
            frames = []
            for i, frame in enumerate(data["frames"]):
                path = prefix + f"/frame-{i}.jpg"
                self.backend.upload("thumbnails", path, frame["file"], "image/jpeg")
                frames.append({"time": frame["time"], "path": path})
            metadata = {
                **data["metadata"],
                "playback_path": prefix + "/playback.mp4",
                "thumbnail_path": prefix + "/thumbnail.jpg",
                "source_hash": data["source_hash"],
            }
            lease.tick(True)
            self.backend.update("videos", metadata, project_id="eq." + job["project_id"])
            lease.stage("analyzing", 25, "Transcribing spoken audio locally")
            transcript = transcribe(data["audio"], self.settings.whisper_model, lease.tick)
            artifact = {
                "transcript": transcript,
                "scenes": data["scenes"],
                "audio_events": data["audio_events"],
                "waveform": data["waveform"],
                "frame_paths": frames,
                "model": self.settings.model,
                "summary": "",
                "warnings": [],
            }
            existing = self.backend.rows("analysis_artifacts", project_id="eq." + job["project_id"])
            # Checkpoints contain only actual extracted evidence; no placeholder highlights.
            if not existing:
                r = self.backend.client.post(
                    self.backend.base + "/rest/v1/analysis_artifacts",
                    json={"project_id": job["project_id"], **artifact},
                )
                r.raise_for_status()
            else:
                self.backend.update(
                    "analysis_artifacts", artifact, project_id="eq." + job["project_id"]
                )
            lease.stage("analyzing", 45, "Checking free AI access and account quota configuration")
            self.provider.preflight()
            candidates = []
            summaries = []
            duration = metadata["duration"]
            start = 0
            window = 0
            while start < duration:
                end = min(duration, start + 90)
                lease.stage(
                    "analyzing",
                    45 + int(35 * start / duration),
                    f"Understanding video {start:.0f}–{end:.0f}s",
                )
                chunk = directory / f"window-{window}.mp4"
                run(
                    ffmpeg(
                        data["proxy"],
                        "-ss",
                        start,
                        "-t",
                        end - start,
                        "-vf",
                        "scale=640:-2",
                        "-c:v",
                        "libx264",
                        "-preset",
                        "veryfast",
                        "-crf",
                        "28",
                        "-c:a",
                        "aac",
                        "-b:a",
                        "48k",
                        chunk,
                    ),
                    180,
                    lease.tick,
                )
                key = video["id"] + ":v1:" + str(window)
                cached = self.backend.rows("provider_usage", request_key="eq." + key)
                cache_path = prefix + f"/analysis-{window}.json"
                if cached:
                    if cached[0]["status"] != "completed":
                        raise RuntimeError(
                            "Previous AI outcome is uncertain; refusing automatic duplicate inference"
                        )
                    cached_file = directory / f"cached-{window}.json"
                    self.backend.download("processing-artifacts", cache_path, cached_file)
                    from .models import Analysis

                    analysis = Analysis.model_validate_json(cached_file.read_text())
                else:
                    # Respect global 1 RPM in addition to the database's atomic request reservation.
                    if window:
                        for _ in range(61):
                            lease.tick()
                            time.sleep(1)
                    usage = self.backend.rpc(
                        "reserve_inference",
                        jid=job["id"],
                        token=job["lease_token"],
                        request_key=key,
                        model=self.settings.model,
                        daily_limit=min(5, self.settings.rpd),
                    )
                    evidence = {
                        "transcript": [
                            {
                                **s,
                                "start": max(0, s["start"] - start),
                                "end": min(end - start, s["end"] - start),
                            }
                            for s in transcript
                            if s["end"] > start and s["start"] < end
                        ],
                        "scenes": [
                            {
                                "start": max(0, s["start"] - start),
                                "end": min(end - start, s["end"] - start),
                            }
                            for s in data["scenes"]
                            if s["end"] > start and s["start"] < end
                        ],
                        "audio_events": [
                            {**a, "time": a["time"] - start}
                            for a in data["audio_events"]
                            if start <= a["time"] < end
                        ],
                    }
                    try:
                        analysis, usage_meta = self.provider.analyze(
                            chunk, project["instructions"], evidence
                        )
                        result = directory / f"analysis-{window}.json"
                        result.write_text(analysis.model_dump_json())
                        self.backend.upload(
                            "processing-artifacts", cache_path, result, "application/json"
                        )
                        self.backend.update(
                            "provider_usage",
                            {
                                "status": "completed",
                                "input_tokens": usage_meta.get("promptTokenCount", 0),
                                "output_tokens": usage_meta.get("candidatesTokenCount", 0),
                            },
                            id="eq." + usage,
                        )
                    except Exception:
                        self.backend.update(
                            "provider_usage", {"status": "unknown"}, id="eq." + usage
                        )
                        raise
                summaries.append(analysis.summary)
                for c in analysis.highlights:
                    if 0 <= c.start < c.end <= end - start:
                        candidates.append(
                            Candidate.model_validate(
                                {**c.model_dump(), "start": c.start + start, "end": c.end + start}
                            )
                        )
                if end >= duration:
                    break
                start = end - 10
                window += 1
            lease.stage("generating_highlights", 90, "Ranking and validating detected moments")
            artifact["summary"] = "\n".join(summaries)[:12000]
            highlights = rank_candidates(candidates, duration)
            lease.tick(True)
            self.backend.rpc(
                "worker_finish_analysis",
                jid=job["id"],
                token=job["lease_token"],
                metadata=metadata,
                artifacts=artifact,
                highlights=[h.model_dump() for h in highlights],
            )

    def once(self):
        job = self.backend.rpc("worker_claim")
        if not job:
            return False
        try:
            self.process(job)
        except Exception as e:
            # Redact credentials and avoid logging provider request bodies / private media.
            detail = str(e)
            for secret in (self.settings.gemini_key, self.settings.service_key):
                if secret:
                    detail = detail.replace(secret, "[redacted]")
            detail = detail[:1200]
            log.error("Job %s failed: %s", job["id"], detail)
            try:
                self.backend.rpc(
                    "worker_tick",
                    jid=job["id"],
                    token=job["lease_token"],
                    state="cancelled" if isinstance(e, Cancelled) else "failed",
                    pct=0,
                    detail="Processing stopped",
                    error_message=detail,
                )
            except Exception:
                log.exception("Could not update job; lease recovery will handle it")
        return True


def main():
    logging.basicConfig(level=logging.INFO)
    settings = Settings()
    worker = Worker(settings)
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    last_heartbeat = 0
    last_cleanup = 0
    while not stop.is_set():
        try:
            if time.monotonic() - last_heartbeat > 30:
                try:
                    settings.check_ai()
                    ready = True
                    detail = "Ready; free AI configuration supplied"
                except ValueError as e:
                    ready = False
                    detail = str(e)
                worker.backend.rpc("worker_heartbeat", ai_ready=ready, detail=detail)
                last_heartbeat = time.monotonic()
            if time.monotonic() - last_cleanup > 3600:
                worker.backend.cleanup()
                for orphan in Path(tempfile.gettempdir()).glob("noetharaclipz-*"):
                    if (
                        orphan.is_dir()
                        and not orphan.is_symlink()
                        and time.time() - orphan.stat().st_mtime > 86400
                    ):
                        shutil.rmtree(orphan)
                last_cleanup = time.monotonic()
            if not worker.once():
                stop.wait(3)
        except Exception:
            log.exception("Worker connection failed")
            stop.wait(10)


if __name__ == "__main__":
    main()
