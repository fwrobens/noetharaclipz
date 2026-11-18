"""Optional AI refinement router: mocked transports only. No live provider requests."""

import json
import shutil
from contextlib import nullcontext
from dataclasses import replace

import httpx
import pytest

from noetharaclipz import router as router_module
from noetharaclipz.config import Settings
from noetharaclipz.local_provider import LocalProvider
from noetharaclipz.media import Cancelled, run
from noetharaclipz.models import Analysis
from noetharaclipz.router import (
    ChatClient,
    DisabledRouter,
    ModelRouter,
    RouteError,
    RouterSettings,
    assert_text_only,
    build_router,
    record_runs,
)
from noetharaclipz.runner import Worker

OWNER = "84d8ae5f-a46d-4c67-82a3-98d80a881507"
NVIDIA_KEY = "nvapi-TEST-ONLY-not-a-real-key-000000"
ANYMODEL_KEY = "am-TEST-ONLY-not-a-real-key-111111"
TRANSCRIPT_SECRET = "the falcon lands at midnight"
INSTRUCTIONS = "Find the funniest reaction for TikTok"
DESCRIPTION = "A player jumps over a wall while the crowd cheers."
ROUTER_ENV = (
    "NC_ROUTER_ENABLED",
    "NVIDIA_API_KEY",
    "NVIDIA_API_KEY_FILE",
    "NVIDIA_BASE_URL",
    "ANYMODEL_API_KEY",
    "ANYMODEL_API_KEY_FILE",
    "ANYMODEL_BASE_URL",
    "NC_REASONING_MODEL",
    "NC_VISION_CONTEXT_MODEL",
    "NC_FALLBACK_MODEL",
    "NC_ANYMODEL_FALLBACK_MODEL",
    "NC_ROUTER_TIMEOUT_SECONDS",
)
DEEPSEEK = router_module.DEFAULT_REASONING_MODEL
GLM = router_module.DEFAULT_VISION_CONTEXT_MODEL
NEMOTRON = router_module.DEFAULT_FALLBACK_MODEL
AM_NEMOTRON = router_module.DEFAULT_ANYMODEL_FALLBACK_MODEL


@pytest.fixture(autouse=True)
def clean_router_env(monkeypatch):
    for name in ROUTER_ENV:
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def no_network(monkeypatch):
    """Any real HTTP transport use fails the test (mock transports are unaffected)."""

    def refuse(*args, **kwargs):
        raise AssertionError("Real network request attempted")

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", refuse)


def local_analysis():
    return Analysis(
        summary="Wall jump: Crowd cheers\nLate laugh: Commentator laughs",
        highlights=[
            {
                "start": 10.0,
                "end": 30.0,
                "title": "Wall jump",
                "category": "Hype",
                "score": 80,
                "explanation": "Crowd cheers",
                "visual_evidence": "Measured motion peak",
            },
            {
                "start": 40.0,
                "end": 55.0,
                "title": "Late laugh",
                "category": "Funny",
                "score": 60,
                "explanation": "Commentator laughs",
                "visual_evidence": "Audio energy spike",
            },
        ],
    )


TRANSCRIPT = [
    {"start": 11.0, "end": 14.0, "text": TRANSCRIPT_SECRET, "words": []},
    {"start": 41.0, "end": 44.0, "text": "haha no way", "words": []},
]
SCENES = [{"start": 0.0, "end": 35.0}, {"start": 35.0, "end": 60.0}]


def chat(content, usage=None):
    return httpx.Response(
        200,
        json={
            "choices": [{"message": {"role": "assistant", "content": content}}],
            "usage": usage or {"prompt_tokens": 120, "completion_tokens": 40},
        },
    )


def evidence(request):
    body = json.loads(request.content)
    text = body["messages"][-1]["content"]
    return body, json.loads(text.split("Evidence: ", 1)[1])


def good_refinement(request):
    _, ev = evidence(request)
    return json.dumps(
        {
            "highlights": [
                {
                    "index": c["index"],
                    "start": c["measured_start"] + 0.5,
                    "end": c["measured_end"] - 0.5,
                    "title": "Refined " + c["title"],
                    "category": "Reaction",
                    "explanation": "Refined using instructions and measured evidence",
                }
                for c in ev["local_candidates"]
            ]
        }
    )


GOOD_CONTEXT = json.dumps({"context": "Outdoor parkour run with a cheering crowd."})


class Recorder:
    """Mock provider. Routes by host + model; records every request it receives."""

    def __init__(self, behaviour):
        self.behaviour = behaviour  # (host, model) -> callable(request) -> Response
        self.requests = []

    def __call__(self, request):
        body = json.loads(request.content)
        self.requests.append((request.url.host, body["model"], request))
        handler = self.behaviour.get((request.url.host, body["model"]))
        if handler is None:
            return httpx.Response(503, json={"error": "unavailable"})
        return handler(request)

    def calls(self, model=None):
        return [(h, m) for h, m, _ in self.requests if model is None or m == model]


def make_router(recorder, nvidia_key=NVIDIA_KEY, anymodel_key="", sleeps=None):
    settings = RouterSettings(enabled=True, nvidia_key=nvidia_key, anymodel_key=anymodel_key)
    transport = httpx.MockTransport(recorder)
    return ModelRouter(
        settings,
        client_factory=lambda base, key, timeout: ChatClient(base, key, timeout, transport),
        sleep=(sleeps.append if sleeps is not None else (lambda s: None)),
    )


def refine(r, analysis=None, tick=lambda: None):
    return r.refine(
        analysis or local_analysis(),
        transcript=TRANSCRIPT,
        scenes=SCENES,
        description=DESCRIPTION,
        instructions=INSTRUCTIONS,
        duration=60.0,
        tick=tick,
    )


NV = "integrate.api.nvidia.com"
AM = "anymodel.org"


def happy():
    return {
        (NV, GLM): lambda req: chat(GOOD_CONTEXT),
        (NV, DEEPSEEK): lambda req: chat(good_refinement(req)),
    }


# --- Off switch -----------------------------------------------------------------


def test_router_disabled_by_default_reads_nothing_and_builds_no_client(monkeypatch, tmp_path):
    key_file = tmp_path / "nvidia-key"
    key_file.write_text(NVIDIA_KEY)
    monkeypatch.setenv("NVIDIA_API_KEY_FILE", str(key_file))
    monkeypatch.setenv("ANYMODEL_API_KEY", ANYMODEL_KEY)

    def explode(*a, **k):
        raise AssertionError("No client may be constructed while the router is disabled")

    monkeypatch.setattr(router_module.ChatClient, "__init__", explode)
    settings = RouterSettings.from_env()
    assert settings.enabled is False and settings.nvidia_key == "" and settings.anymodel_key == ""
    router = build_router()
    assert isinstance(router, DisabledRouter) and router.enabled is False
    analysis = local_analysis()
    assert router.refine(analysis).analysis is analysis


@pytest.mark.parametrize("value", ["false", "0", "", "maybe", "TRUE-ish"])
def test_off_or_malformed_switch_fails_closed(monkeypatch, value):
    monkeypatch.setenv("NC_ROUTER_ENABLED", value)
    monkeypatch.setenv("NVIDIA_API_KEY", NVIDIA_KEY)
    assert isinstance(build_router(), DisabledRouter)


def test_enabled_settings_read_key_files_and_never_render_keys(monkeypatch, tmp_path):
    key_file = tmp_path / "nvidia-key"
    key_file.write_text(NVIDIA_KEY + "\n")
    monkeypatch.setenv("NC_ROUTER_ENABLED", "true")
    monkeypatch.setenv("NVIDIA_API_KEY_FILE", str(key_file))
    monkeypatch.setenv("NC_ROUTER_TIMEOUT_SECONDS", "12")
    s = RouterSettings.from_env()
    assert s.enabled and s.nvidia_key == NVIDIA_KEY and s.anymodel_key == ""
    assert s.nvidia_base_url == "https://integrate.api.nvidia.com/v1"
    assert s.anymodel_base_url == "https://anymodel.org/v1"
    assert (s.reasoning_model, s.vision_context_model) == (DEEPSEEK, GLM)
    assert (s.fallback_model, s.anymodel_fallback_model) == (NEMOTRON, AM_NEMOTRON)
    assert s.timeout_seconds == 12
    assert NVIDIA_KEY not in repr(s) and NVIDIA_KEY not in str(s)


def test_non_https_base_url_rejected(monkeypatch):
    monkeypatch.setenv("NC_ROUTER_ENABLED", "true")
    monkeypatch.setenv("NVIDIA_BASE_URL", "http://integrate.api.nvidia.com/v1")
    with pytest.raises(ValueError):
        RouterSettings.from_env()


def test_whisper_and_smolvlm2_tasks_have_no_hosted_route():
    r = make_router(Recorder({}))
    for task in ("transcription", "video_analysis"):
        with pytest.raises(ValueError, match="local-only"):
            r.routes(task)


@pytest.mark.parametrize("provider", ["nvidia", "anymodel", "deepseek", "router", "automatic"])
def test_nc_ai_provider_still_has_no_fallback(provider, monkeypatch):
    monkeypatch.setenv("NC_ROUTER_ENABLED", "true")
    with pytest.raises(ValueError, match="no fallback"):
        Settings(provider=provider)


# --- Primary routes ---------------------------------------------------------------


def test_deepseek_success_refines_within_measured_bounds(no_network):
    rec = Recorder(happy())
    original = local_analysis()
    out = refine(make_router(rec), original)
    assert out.refined and out.reasoning_model == DEEPSEEK and out.visual_context_model == GLM
    assert [h.title for h in out.analysis.highlights] == ["Refined Wall jump", "Refined Late laugh"]
    for new, old in zip(out.analysis.highlights, original.highlights):
        assert old.start <= new.start < new.end <= old.end
        assert (new.score, new.visual_evidence) == (old.score, old.visual_evidence)
    assert rec.calls() == [(NV, GLM), (NV, DEEPSEEK)]
    assert [(r.task, r.provider, r.model_id, r.role, r.status) for r in out.runs] == [
        ("visual_context", "nvidia", GLM, "primary", "success"),
        ("highlight_reasoning", "nvidia", DEEPSEEK, "primary", "success"),
    ]
    assert out.runs[1].input_tokens == 120 and out.runs[1].output_tokens == 40
    assert out.analysis.summary == original.summary  # Router may not alter the local summary.
    # The original local object is never mutated.
    assert original.model_dump() == local_analysis().model_dump()


def test_glm_receives_only_text_transcript_scenes_and_description(no_network):
    rec = Recorder(happy())
    refine(make_router(rec))
    glm = [req for host, model, req in rec.requests if model == GLM]
    assert len(glm) == 1
    body, ev = evidence(glm[0])
    assert set(body) == {"model", "messages", "temperature", "max_tokens", "stream"}
    assert all(isinstance(m["content"], str) for m in body["messages"])
    assert set(ev) == {"transcript", "scenes", "local_model_description"}
    assert TRANSCRIPT_SECRET in ev["transcript"] and ev["local_model_description"] == DESCRIPTION
    raw = glm[0].content.decode().lower()
    for forbidden in ("data:image", "data:video", "image_url", ".jpg", ".mp4", "base64"):
        assert forbidden not in raw
    assert glm[0].headers["authorization"] == "Bearer " + NVIDIA_KEY


@pytest.mark.parametrize(
    "messages",
    [
        [{"role": "user", "content": [{"type": "image_url", "image_url": {"url": "x"}}]}],
        [{"role": "user", "content": "see data:image/jpeg;base64,AAAA"}],
        [{"role": "user", "content": "clip data:video/mp4;base64,AAAA"}],
        [{"role": "user", "content": "ok", "images": ["frame-0.jpg"]}],
        [],
    ],
)
def test_text_only_guard_rejects_media(messages):
    with pytest.raises(RouteError) as error:
        assert_text_only(messages)
    assert error.value.error_class == "text_only_violation"


def test_client_refuses_media_before_any_request():
    rec = Recorder({})
    client = ChatClient(
        "https://integrate.api.nvidia.com/v1", NVIDIA_KEY, 5, httpx.MockTransport(rec)
    )
    with pytest.raises(RouteError):
        client.complete(GLM, [{"role": "user", "content": [{"type": "video_url"}]}])
    assert rec.requests == []


# --- Fallbacks -------------------------------------------------------------------


def _timeout(request):
    raise httpx.ReadTimeout("timed out", request=request)


@pytest.mark.parametrize(
    "failure, error_class",
    [
        (_timeout, "timeout"),
        (lambda req: httpx.Response(429), "rate_limited"),
        (lambda req: httpx.Response(503, text="echo: " + TRANSCRIPT_SECRET), "server_error"),
    ],
)
def test_retryable_failure_retries_then_uses_nvidia_nemotron(no_network, failure, error_class):
    sleeps = []
    rec = Recorder(
        {
            (NV, GLM): lambda req: chat(GOOD_CONTEXT),
            (NV, DEEPSEEK): failure,
            (NV, NEMOTRON): lambda req: chat(good_refinement(req)),
        }
    )
    out = refine(make_router(rec, sleeps=sleeps))
    assert out.refined and out.reasoning_model == NEMOTRON
    assert rec.calls(DEEPSEEK) == [(NV, DEEPSEEK)] * router_module.MAX_ATTEMPTS_PER_ROUTE
    reasoning = [r for r in out.runs if r.task == "highlight_reasoning"]
    assert [(r.model_id, r.role, r.status, r.attempt, r.error_class) for r in reasoning] == [
        (DEEPSEEK, "primary", "error", 1, error_class),
        (DEEPSEEK, "primary", "error", 2, error_class),
        (NEMOTRON, "fallback", "success", 1, None),
    ]
    assert len(sleeps) == 1 and all(s <= router_module.MAX_BACKOFF_SECONDS for s in sleeps)
    assert TRANSCRIPT_SECRET not in json.dumps([r.as_record() for r in out.runs])


def test_client_error_is_not_retried():
    rec = Recorder(
        {
            (NV, GLM): lambda req: chat(GOOD_CONTEXT),
            (NV, DEEPSEEK): lambda req: httpx.Response(401),
            (NV, NEMOTRON): lambda req: chat(good_refinement(req)),
        }
    )
    out = refine(make_router(rec))
    assert rec.calls(DEEPSEEK) == [(NV, DEEPSEEK)] and out.reasoning_model == NEMOTRON


def test_nvidia_total_failure_uses_anymodel_when_configured(no_network):
    rec = Recorder(
        {
            (AM, AM_NEMOTRON): lambda req: chat(
                GOOD_CONTEXT
                if "local_candidates" not in req.content.decode()
                else good_refinement(req)
            )
        }
    )
    out = refine(make_router(rec, anymodel_key=ANYMODEL_KEY))
    assert out.refined and out.reasoning_model == AM_NEMOTRON
    assert out.visual_context_model == AM_NEMOTRON
    am = [req for host, model, req in rec.requests if host == AM]
    assert am and all(r.headers["authorization"] == "Bearer " + ANYMODEL_KEY for r in am)
    assert all(r.url.path == "/v1/chat/completions" for r in am)
    nv = [req for host, model, req in rec.requests if host == NV]
    assert all(ANYMODEL_KEY not in r.headers["authorization"] for r in nv)
    roles = {(r.provider, r.model_id, r.role) for r in out.runs if r.status == "success"}
    assert roles == {("anymodel", AM_NEMOTRON, "fallback")}


def test_anymodel_skipped_when_not_configured(no_network):
    rec = Recorder({})  # Every NVIDIA call fails with 503.
    original = local_analysis()
    out = refine(make_router(rec), original)
    assert not out.refined and out.analysis is original
    assert all(host == NV for host, _ in rec.calls())
    skipped = [r for r in out.runs if r.status == "skipped"]
    assert {(r.task, r.provider, r.error_class) for r in skipped} == {
        ("visual_context", "anymodel", "no_credential"),
        ("highlight_reasoning", "anymodel", "no_credential"),
    }


def test_no_credentials_at_all_makes_no_request():
    rec = Recorder(happy())
    out = refine(make_router(rec, nvidia_key=""))
    assert rec.requests == [] and not out.refined
    assert all(r.status == "skipped" for r in out.runs)


def test_visual_context_failure_does_not_block_reasoning():
    rec = Recorder({(NV, DEEPSEEK): lambda req: chat(good_refinement(req))})
    out = refine(make_router(rec))
    assert out.refined and out.visual_context_model is None and out.reasoning_model == DEEPSEEK


# --- Strict validation -----------------------------------------------------------


def _mutate(change):
    def handler(request):
        value = json.loads(good_refinement(request))
        change(value)
        return chat(json.dumps(value))

    return handler


INVALID = {
    "not_json": lambda req: chat("Sure! Here are your highlights: ..."),
    "json_array": lambda req: chat("[1, 2]"),
    "nan": lambda req: chat('{"highlights": NaN}'),
    "extra_field": _mutate(lambda v: v["highlights"][0].update(score=100)),
    "owner_injection": _mutate(
        lambda v: v.update(project_id="00000000-0000-0000-0000-000000000000")
    ),
    "job_injection": _mutate(lambda v: v["highlights"][0].update(job_id="x")),
    "missing_field": _mutate(lambda v: v["highlights"][0].pop("title")),
    "wrong_type": _mutate(lambda v: v["highlights"][0].update(start="10.5")),
    "bool_index": _mutate(lambda v: v["highlights"][0].update(index=False)),
    "oversized": _mutate(lambda v: v["highlights"][0].update(title="x" * 121)),
    "unknown_category": _mutate(lambda v: v["highlights"][0].update(category="Viral")),
    "outside_bounds": _mutate(lambda v: v["highlights"][0].update(start=5.0)),
    "past_measured_end": _mutate(lambda v: v["highlights"][1].update(end=58.0)),
    "reversed": _mutate(lambda v: v["highlights"][0].update(start=20.0, end=15.0)),
    "dropped_candidate": _mutate(lambda v: v["highlights"].pop()),
    "duplicate_index": _mutate(lambda v: v["highlights"][1].update(index=0)),
    "empty": lambda req: chat('{"highlights": []}'),
}


@pytest.mark.parametrize("name", sorted(INVALID))
def test_invalid_output_moves_to_next_route(no_network, name):
    rec = Recorder(
        {
            (NV, GLM): lambda req: chat(GOOD_CONTEXT),
            (NV, DEEPSEEK): INVALID[name],
            (NV, NEMOTRON): lambda req: chat(good_refinement(req)),
        }
    )
    out = refine(make_router(rec))
    assert out.refined and out.reasoning_model == NEMOTRON
    deepseek = [r for r in out.runs if r.model_id == DEEPSEEK]
    assert len(deepseek) == 1 and deepseek[0].status == "invalid"
    assert deepseek[0].error_class in ("invalid_json", "schema_invalid", "bounds_invalid")


def test_refinement_overlapping_after_tightening_is_rejected():
    analysis = local_analysis()
    # Two local candidates that overlap heavily cannot both survive rank_candidates.
    analysis.highlights[1] = analysis.highlights[1].model_copy(update={"start": 12.0, "end": 31.0})
    rec = Recorder(
        {
            (NV, GLM): lambda req: chat(GOOD_CONTEXT),
            (NV, DEEPSEEK): lambda req: chat(good_refinement(req)),
            (NV, NEMOTRON): lambda req: chat(good_refinement(req)),
        }
    )
    out = refine(make_router(rec), analysis)
    assert not out.refined and out.analysis is analysis


def test_fenced_or_think_prefixed_json_is_accepted():
    rec = Recorder(
        {
            (NV, GLM): lambda req: chat("```json\n" + GOOD_CONTEXT + "\n```"),
            (NV, DEEPSEEK): lambda req: chat("<think>reasoning</think>\n" + good_refinement(req)),
        }
    )
    out = refine(make_router(rec))
    assert out.refined and out.visual_context_model == GLM


# --- Total failure / cancellation -----------------------------------------------


def test_total_failure_returns_local_result_byte_for_byte(no_network):
    original = local_analysis()
    before = original.model_dump_json()
    rec = Recorder(
        {
            (host, m): (lambda req: chat("nope"))
            for host in (NV, AM)
            for m in (GLM, DEEPSEEK, NEMOTRON, AM_NEMOTRON)
        }
    )
    out = refine(make_router(rec, anymodel_key=ANYMODEL_KEY), original)
    assert not out.refined and out.analysis is original
    assert out.analysis.model_dump_json() == before
    assert len(rec.requests) == 6  # 3 routes x 2 tasks, invalid output is not retried.


def test_empty_local_result_makes_no_request():
    rec = Recorder(happy())
    empty = Analysis(summary="No supported local highlight was selected.", highlights=[])
    out = refine(make_router(rec), empty)
    assert rec.requests == [] and out.analysis is empty and out.runs == []


def test_cancellation_from_lease_tick_propagates():
    rec = Recorder(happy())

    def tick():
        raise Cancelled("Job was cancelled")

    with pytest.raises(Cancelled):
        refine(make_router(rec), tick=tick)
    assert rec.requests == []


def test_budget_exhaustion_stops_routing(monkeypatch):
    rec = Recorder({})
    r = make_router(rec)
    times = iter([0.0] + [1000.0] * 50)
    r.clock = lambda: next(times)
    out = refine(r)
    assert not out.refined and rec.requests == []
    assert any(x.error_class == "budget_exhausted" for x in out.runs)


# --- model_runs records --------------------------------------------------------


ALLOWED = {
    "task",
    "provider",
    "model_id",
    "role",
    "status",
    "attempt",
    "latency_ms",
    "input_tokens",
    "output_tokens",
    "error_class",
    "error_message",
}


def test_model_run_records_contain_no_secrets_prompts_or_transcript():
    rec = Recorder(
        {
            (NV, GLM): lambda req: httpx.Response(500, text=NVIDIA_KEY + TRANSCRIPT_SECRET),
            (NV, DEEPSEEK): lambda req: chat("not json " + TRANSCRIPT_SECRET),
            (NV, NEMOTRON): lambda req: chat(good_refinement(req)),
            (AM, AM_NEMOTRON): lambda req: chat(GOOD_CONTEXT),
        }
    )
    out = refine(make_router(rec, anymodel_key=ANYMODEL_KEY))
    records = [r.as_record() for r in out.runs]
    assert records and all(set(r) == ALLOWED for r in records)
    dumped = json.dumps(records)
    for leaked in (
        NVIDIA_KEY,
        ANYMODEL_KEY,
        TRANSCRIPT_SECRET,
        INSTRUCTIONS,
        DESCRIPTION,
        "Evidence",
        "haha",
    ):
        assert leaked not in dumped
    assert all(r["error_message"] is None or len(r["error_message"]) <= 160 for r in records)
    assert all(r["role"] in ("primary", "fallback", "local") for r in records)
    assert {r["status"] for r in records} <= {"success", "error", "invalid", "skipped"}


def test_sanitize_error_redacts_keys():
    text = router_module.sanitize_error("bad nvapi-abcdefghijk and " + ANYMODEL_KEY, [ANYMODEL_KEY])
    assert "nvapi-abcdefghijk" not in text and ANYMODEL_KEY not in text


def test_record_runs_failure_is_swallowed():
    class Broken:
        def rpc(self, *a, **k):
            raise RuntimeError("function public.worker_log_model_runs does not exist")

    run = router_module.ModelRun("visual_context", "nvidia", GLM, "primary", "success", 1)
    assert record_runs(Broken(), {"id": "j", "lease_token": "t"}, [run]) is False


# --- Worker integration ----------------------------------------------------------


class Ranker:
    def checkpoints(self, tick):
        return nullcontext()

    def choose(self, paths, prompt, evidence):
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


@pytest.fixture(scope="module")
def media(tmp_path_factory):
    p = tmp_path_factory.mktemp("media") / "source.mp4"
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


class Backend:
    base = "https://example.invalid"

    def __init__(self, media, log_fails=False):
        self.media = media
        self.log_fails = log_fails
        self.finished = None
        self.logged = None
        self.calls = []
        self.client = httpx.Client(
            transport=httpx.MockTransport(lambda req: httpx.Response(201, json={}))
        )

    def rows(self, table, **params):
        return {
            "videos": [{"source_path": "source.mp4", "byte_size": self.media.stat().st_size}],
            "projects": [{"id": "project", "owner_id": OWNER, "instructions": INSTRUCTIONS}],
            "analysis_artifacts": [],
        }[table]

    def download(self, bucket, path, dest):
        shutil.copyfile(self.media, dest)
        return dest.stat().st_size

    def update(self, *args, **kwargs):
        pass

    def upload(self, bucket, path, source, mime):
        pass

    def rpc(self, name, **params):
        self.calls.append(name)
        assert name in ("worker_tick", "worker_finish_analysis", "worker_log_model_runs")
        if name == "worker_log_model_runs":
            if self.log_fails:
                raise RuntimeError("Backend operation failed: function does not exist")
            self.logged = params
        if name == "worker_finish_analysis":
            self.finished = params
        return True


JOB = {
    "id": "job",
    "project_id": "project",
    "lease_token": "token",
    "kind": "analysis",
    "attempts": 1,
}


def process(media, tmp_path, router, log_fails=False):
    s = replace(Settings(), provider="local", cache_dir=str(tmp_path / "cache"))
    backend = Backend(media, log_fails)
    w = Worker(s, backend=backend, provider=LocalProvider(s, Ranker()), router=router)
    w.process(dict(JOB))
    return backend


def test_worker_with_router_off_makes_no_external_or_logging_calls(
    media, tmp_path, no_network, monkeypatch
):
    monkeypatch.setattr(
        router_module.ChatClient, "__init__", lambda *a, **k: pytest.fail("client constructed")
    )
    s = replace(Settings(), provider="local", cache_dir=str(tmp_path / "cache"))
    backend = Backend(media)
    w = Worker(s, backend=backend, provider=LocalProvider(s, Ranker()))
    assert isinstance(w.router, DisabledRouter)
    w.process(dict(JOB))
    assert backend.finished["highlights"] and "worker_log_model_runs" not in backend.calls
    assert backend.finished["artifacts"]["provider"] == "local-smolvlm2"


def test_worker_router_total_failure_preserves_local_highlights(media, tmp_path, no_network):
    baseline = process(media, tmp_path / "a", DisabledRouter())
    failing = make_router(Recorder({}), anymodel_key=ANYMODEL_KEY)
    result = process(media, tmp_path / "b", failing)
    assert json.dumps(result.finished["highlights"]) == json.dumps(baseline.finished["highlights"])
    assert result.finished["artifacts"]["summary"] == baseline.finished["artifacts"]["summary"]
    assert (result.finished["jid"], result.finished["token"]) == ("job", "token")
    runs = result.logged["runs"]
    assert {r["role"] for r in runs} == {"local", "primary", "fallback"}
    assert {r["task"] for r in runs if r["role"] == "local"} == {"transcription", "video_analysis"}


def test_worker_router_success_and_logging_failure_does_not_affect_result(
    media, tmp_path, no_network
):
    ok = process(media, tmp_path / "a", make_router(Recorder(happy())))
    broken = process(media, tmp_path / "b", make_router(Recorder(happy())), log_fails=True)
    assert ok.finished["highlights"][0]["title"].startswith("Refined ")
    assert json.dumps(ok.finished["highlights"]) == json.dumps(broken.finished["highlights"])
    assert broken.logged is None and broken.finished is not None
    # Provenance stays local so worker_finish_analysis and worker_protocol are unchanged.
    for b in (ok, broken):
        assert b.finished["artifacts"]["provider"] == "local-smolvlm2"
        assert (b.finished["jid"], b.finished["token"]) == ("job", "token")
    logged = json.dumps(ok.logged)
    assert NVIDIA_KEY not in logged and INSTRUCTIONS not in logged
    assert ok.calls.index("worker_log_model_runs") < ok.calls.index("worker_finish_analysis")


def test_worker_router_exception_keeps_local_result(media, tmp_path):
    class Exploding:
        enabled = True

        def refine(self, analysis, **kwargs):
            raise KeyError("boom")

    baseline = process(media, tmp_path / "a", DisabledRouter())
    result = process(media, tmp_path / "b", Exploding())
    assert json.dumps(result.finished["highlights"]) == json.dumps(baseline.finished["highlights"])


def test_worker_router_cancellation_is_not_swallowed(media, tmp_path):
    class Cancelling:
        enabled = True

        def refine(self, analysis, **kwargs):
            raise Cancelled("Job was cancelled")

    s = replace(Settings(), provider="local", cache_dir=str(tmp_path / "cache"))
    backend = Backend(media)
    w = Worker(s, backend=backend, provider=LocalProvider(s, Ranker()), router=Cancelling())
    with pytest.raises(Cancelled):
        w.process(dict(JOB))
    assert backend.finished is None and "worker_log_model_runs" not in backend.calls



def test_chat_client_applies_per_request_remaining_timeout():
    observed = []

    def inspect(request):
        observed.append(request.extensions.get("timeout"))
        return chat(GOOD_CONTEXT)

    client = ChatClient(
        "https://integrate.api.nvidia.com/v1", NVIDIA_KEY, 30,
        httpx.MockTransport(inspect),
    )
    client.complete(GLM, [{"role": "user", "content": "test"}], timeout=2.5)
    assert observed and observed[0]["read"] == 2.5
    client.close()
