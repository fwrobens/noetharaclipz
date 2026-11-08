"""Local worker control contracts; test choices do not count as real AI usage."""

from contextlib import nullcontext
from dataclasses import replace
from pathlib import Path
import shutil
import httpx
import pytest
from noetharaclipz.config import Settings
from noetharaclipz.local_provider import LocalProvider
from noetharaclipz.local_detector import complete_speech_bounds
from noetharaclipz.local_detector import empty_observation
from noetharaclipz.media import run
from noetharaclipz.providers import build_provider
from noetharaclipz.runner import Worker

OWNER = "84d8ae5f-a46d-4c67-82a3-98d80a881507"


class Ranker:
    def __init__(self):
        self.calls = 0

    def checkpoints(self, tick):
        return nullcontext()

    def choose(self, paths, prompt, evidence):
        self.calls += 1
        assert paths and all(p.stat().st_size for p in paths)
        return {
            "choice": "A",
            "relative_choice_scores": {"A": 0.8, "Z": 0.2},
            "input_tokens": 12,
            "video_tensor_sha256": "contract-fixture",
        }

    def describe(self, path):
        self.output_tokens = 3
        self.description_input_tokens = 5
        return "Contract fixture; not actual model inference"


@pytest.fixture
def media(tmp_path):
    p = tmp_path / "source.mp4"
    run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=s=160x90:r=10:d=4",
            "-c:v",
            "libx264",
            str(p),
        ]
    )
    return p


def test_local_does_not_need_gemini_key_flags_or_quotas(monkeypatch, tmp_path):
    monkeypatch.setenv("NC_AI_PROVIDER", "local")
    monkeypatch.setenv("GEMINI_VERIFIED_RPM", "not-confirmed")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    s = replace(Settings(), cache_dir=str(tmp_path / "cache"))
    assert isinstance(build_provider(s), LocalProvider) and s.rpm == 0 and not s.free_verified
    monkeypatch.setenv("NC_AI_PROVIDER", "gemini")
    assert Settings(provider="local").rpm == 0  # Explicit construction also ignores Gemini quotas.


@pytest.mark.parametrize("provider", ["automatic", "fallback", "nvidia", ""])
def test_unknown_provider_has_no_fallback(provider):
    with pytest.raises(ValueError):
        Settings(provider=provider)


def test_invalid_owner_rejected_before_claim():
    with pytest.raises(ValueError):
        Settings(scope_owner="not-a-uuid")


def test_local_preflight_refuses_insufficient_memory(monkeypatch, tmp_path):
    monkeypatch.setattr("noetharaclipz.local_provider.available_memory", lambda: 4 * 1024**3)
    provider = LocalProvider(replace(Settings(), provider="local", cache_dir=str(tmp_path)))
    with pytest.raises(RuntimeError, match="6 GiB"):
        provider.preflight()
    assert not provider.ready and provider.ranker is None


def test_scoped_worker_never_uses_global_claim_or_global_health(tmp_path):
    calls = []

    class Backend:
        def rpc(self, name, **params):
            calls.append((name, params))
            if name == "worker_protocol":
                return {
                    "version": 1,
                    "providers": ["local-smolvlm2"],
                    "scoped_claim": True,
                    "scoped_health": True,
                }
            assert name in ("worker_claim_scoped", "worker_heartbeat_scoped")
            assert params["owner"] == OWNER
            return None

    w = Worker(replace(Settings(), scope_owner=OWNER), backend=Backend(), provider=object())
    assert w.once() is False
    w.heartbeat(True, "Ready local test")
    assert [x[0] for x in calls] == [
        "worker_protocol",
        "worker_claim_scoped",
        "worker_heartbeat_scoped",
    ]


def test_missing_protocol_fails_before_any_claim():
    class Backend:
        def rpc(self, name, **params):
            assert name == "worker_protocol"
            raise RuntimeError("No supported SQL protocol")

    w = Worker(replace(Settings(), scope_owner=OWNER), backend=Backend(), provider=object())
    with pytest.raises(RuntimeError):
        w.once()


def test_persistent_cache_reuses_measured_data_and_records_zero_executed_tokens(media, tmp_path):
    ranker = Ranker()
    p = LocalProvider(
        replace(Settings(), provider="local", cache_dir=str(tmp_path / "cache")), ranker
    )
    first = p.prepare(media, lambda: None)
    t = p.transcript(first, lambda: None)
    a, r, _ = p.analyze(media, first, t, "Fixture query", lambda: None)
    assert r["execution_usage"] == {"input_tokens": 17, "output_tokens": 3} and ranker.calls == 1
    again = p.prepare(media, lambda: None)
    t = p.transcript(again, lambda: None)
    b, c, _ = p.analyze(media, again, t, "Fixture query", lambda: None)
    assert (
        p.metrics["prepared_cache_hit"]
        and p.metrics["transcript_cache_hit"]
        and p.metrics["analysis_cache_hit"]
    )
    assert c["execution_usage"] == {"input_tokens": 0, "output_tokens": 0} and ranker.calls == 1
    assert a.model_dump() == b.model_dump()
    assert (Path(p.settings.cache_dir).stat().st_mode & 0o077) == 0
    p.analyze(media, again, t, "Different query", lambda: None)
    assert ranker.calls == 2 and not p.metrics["analysis_cache_hit"]


def test_speech_boundary_completion_never_exceeds_export_limit():
    assert complete_speech_bounds(12, 20, [{"start": 10, "end": 21}], 30) == (9.85, 21.15)
    assert complete_speech_bounds(12, 20, [{"start": 0, "end": 90}], 100) == (12, 20)


def test_cold_numpy_speech_timestamps_are_json_serializable(media, tmp_path):
    import json
    import numpy as np

    provider = LocalProvider(
        replace(Settings(), provider="local", cache_dir=str(tmp_path / "cache")), Ranker()
    )
    data = provider.prepare(media, lambda: None)
    transcript = [
        {"start": np.float64(0.5), "end": np.float64(3.5), "text": "Measured speech", "words": []}
    ]
    _, result, path = provider.analyze(media, data, transcript, "Spoken reaction", lambda: None)
    assert json.loads(path.read_text())["quality_metrics"] == result["quality_metrics"]
    json.dumps(result)


def test_empty_media_guard_keeps_quiet_detailed_images_and_spoken_audio(tmp_path):
    import cv2
    import numpy as np

    a, b = tmp_path / "a.png", tmp_path / "b.png"
    cv2.imwrite(str(a), np.zeros((32, 32), dtype=np.uint8))
    cv2.imwrite(str(b), np.zeros((32, 32), dtype=np.uint8))
    data = {"frames": [{"file": a}, {"file": b}], "audio_events": []}
    assert empty_observation(data, []) is True
    assert empty_observation(data, [{"text": "Actual speech evidence"}]) is False
    cv2.imwrite(str(b), np.tile(np.arange(32, dtype=np.uint8) * 8, (32, 1)))
    assert empty_observation(data, []) is False


def test_normal_worker_local_analysis_uses_atomic_completion_without_gemini(media, tmp_path):
    ranker = Ranker()
    s = replace(Settings(), provider="local", cache_dir=str(tmp_path / "cache"))
    p = LocalProvider(s, ranker)

    class Backend:
        base = "https://example.invalid"

        def __init__(self):
            self.finished = None
            self.uploaded = []
            self.client = httpx.Client(
                transport=httpx.MockTransport(lambda req: httpx.Response(201, json={}))
            )

        def rows(self, table, **params):
            return {
                "videos": [{"source_path": "source.mp4", "byte_size": media.stat().st_size}],
                "projects": [{"id": "project", "owner_id": OWNER, "instructions": "Fixture query"}],
                "analysis_artifacts": [],
            }[table]

        def download(self, bucket, path, dest):
            shutil.copyfile(media, dest)
            return dest.stat().st_size

        def update(self, *args, **kwargs):
            pass

        def upload(self, bucket, path, source, mime):
            assert source.stat().st_size
            self.uploaded.append((bucket, path))

        def rpc(self, name, **params):
            assert name in ("worker_tick", "worker_finish_analysis"), (
                "No Gemini quota reservation permitted"
            )
            if name == "worker_finish_analysis":
                self.finished = params
            return True

    backend = Backend()
    w = Worker(s, backend=backend, provider=p)
    w.process(
        {
            "id": "job",
            "project_id": "project",
            "lease_token": "token",
            "kind": "analysis",
            "attempts": 1,
        }
    )
    assert backend.finished["artifacts"]["provider"] == "local-smolvlm2"
    assert backend.finished["artifacts"]["local_usage"] == {"input_tokens": 17, "output_tokens": 3}
    assert backend.finished["highlights"]
    assert ("processing-artifacts", OWNER + "/project/local-analysis.json") in backend.uploaded
