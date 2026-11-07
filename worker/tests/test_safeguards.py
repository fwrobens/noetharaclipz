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
