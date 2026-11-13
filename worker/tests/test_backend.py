"""HTTP contract tests; they do not claim live server authentication."""

import base64
import json
from dataclasses import replace
import httpx
import pytest
from noetharaclipz.backend import Backend
from noetharaclipz.config import Settings, server_key_headers

SECRET = "sb_secret_" + "x" * 32


def legacy(role="service_role"):
    def enc(v):
        return base64.urlsafe_b64encode(json.dumps(v).encode()).decode().rstrip("=")

    return enc({"alg": "HS256"}) + "." + enc({"role": role}) + ".signature"


@pytest.mark.parametrize("key", [SECRET, legacy()])
def test_worker_headers_apply_to_rpc_and_storage(tmp_path, key):
    seen = []

    def handler(request):
        seen.append(request)
        assert request.headers["apikey"] == key
        if key.startswith("sb_secret_"):
            assert "authorization" not in request.headers
        else:
            assert request.headers["authorization"] == "Bearer " + key
        if request.url.path.endswith("worker_claim"):
            return httpx.Response(200, json=None)
        if request.method == "GET":
            return httpx.Response(200, content=b"video bytes")
        return httpx.Response(200, json={})

    client = httpx.Client(
        transport=httpx.MockTransport(handler), headers={"Authorization": "Bearer unrelated"}
    )
    backend = Backend(replace(Settings(), service_key=key), client=client)
    backend.rpc("worker_claim")
    media = tmp_path / "video.mp4"
    media.write_bytes(b"video bytes")
    backend.upload("rendered-clips", "owner/project/job.mp4", media, "video/mp4")
    backend.download("source-videos", "owner/project/source.mp4", tmp_path / "download.mp4")
    assert len(seen) == 3


@pytest.mark.parametrize(
    "value",
    [
        "placeholder",
        "sb_publishable_" + "x" * 32,
        legacy("anon"),
        legacy("authenticated"),
        "eyJbroken",
        SECRET + "\nextra",
    ],
)
def test_nonserver_credentials_fail_before_network(value):
    with pytest.raises(ValueError):
        server_key_headers(value)


def test_runtime_env_is_read_when_settings_created(monkeypatch):
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", SECRET)
    monkeypatch.setenv("GEMINI_FREE_TIER_VERIFIED", "false")
    monkeypatch.setenv("GEMINI_VERIFIED_RPM", "0")
    assert Settings().service_key == SECRET
    assert not Settings().free_verified
    monkeypatch.setenv("GEMINI_VERIFIED_RPM", "not confirmed")
    with pytest.raises(ValueError, match="GEMINI_VERIFIED_RPM"):
        Settings()


def test_cleanup_does_not_skip_folders_when_pages_shift():
    folders = {f"folder-{i}": ["video.mp4"] for i in range(101)}
    removed = []

    def handler(request):
        body = json.loads(request.content)
        if request.method == "POST":
            prefix = body["prefix"]
            if prefix == "owner/project/":
                entries = [{"name": name, "id": None} for name in folders]
            else:
                entries = [{"name": "video.mp4", "id": "object"}]
            return httpx.Response(
                200, json=entries[body["offset"] : body["offset"] + body["limit"]]
            )
        for path in body["prefixes"]:
            name = path.split("/")[2]
            folders.pop(name, None)
            removed.append(path)
        return httpx.Response(200, json=[])

    backend = Backend(
        replace(Settings(), service_key=SECRET),
        httpx.Client(transport=httpx.MockTransport(handler)),
    )
    backend.remove_prefix("source-videos", "owner/project/")
    assert len(removed) == 101 and not folders
