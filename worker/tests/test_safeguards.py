from dataclasses import replace
import httpx
import pytest
from noetharaclipz.config import Settings
from noetharaclipz.models import Edit
from noetharaclipz.providers import Gemini


@pytest.mark.parametrize(
    "values",
    [
        {"gemini_key": ""},
        {"gemini_key": "test", "free_verified": False},
        {"gemini_key": "test", "free_verified": True, "rpm": 0, "rpd": 5, "tpm": 50000},
    ],
)
def test_missing_or_unverified_credentials_make_no_request(values):
    def forbidden(request):
        raise AssertionError("Network call must not be attempted")

    provider = Gemini(
        replace(Settings(), **values), httpx.Client(transport=httpx.MockTransport(forbidden))
    )
    with pytest.raises(ValueError):
        provider.preflight()


def test_unrelated_project_refused():
    with pytest.raises(ValueError, match="unrelated"):
        replace(
            Settings(), supabase_url="https://another-project.supabase.co", service_key="test"
        ).check_project()


@pytest.mark.parametrize(
    "change",
    [
        {"start": float("nan")},
        {"end": 80},
        {"crop_x": 2},
        {"volume": 5},
        {"caption_color": "red;movie=http://internal"},
        {"unexpected": "operation"},
    ],
)
def test_untrusted_edits_rejected(change):
    with pytest.raises(ValueError):
        Edit.model_validate({"start": 0, "end": 5, **change})


def test_text_only_provider_metadata_rejected():
    config = replace(Settings(), gemini_key="test", free_verified=True, rpm=1, rpd=5, tpm=50000)

    def metadata(request):
        return httpx.Response(200, json={"supportedGenerationMethods": ["embedContent"]})

    with pytest.raises(ValueError, match="required video API"):
        Gemini(config, httpx.Client(transport=httpx.MockTransport(metadata))).preflight()


def test_false_free_flag_allows_metadata_inspection_but_never_inference(tmp_path):
    seen = []

    def metadata(request):
        seen.append(request)
        assert request.method == "GET"
        return httpx.Response(
            200,
            json={
                "name": "models/gemini-3.8-flash",
                "supportedGenerationMethods": ["generateContent"],
            },
        )

    config = replace(
        Settings(), gemini_key="unit-test-key", free_verified=False, rpm=0, rpd=0, tpm=0
    )
    provider = Gemini(config, httpx.Client(transport=httpx.MockTransport(metadata)))
    assert provider.inspect_access()["name"] == "models/gemini-3.8-flash"
    with pytest.raises(ValueError, match="Verify the FREE tier"):
        provider.analyze(tmp_path / "not-read.mp4", "request", {})
    assert len(seen) == 1
