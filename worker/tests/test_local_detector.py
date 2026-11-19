"""Selection boundary contracts. Stub choices are NOT live AI acceptance."""

import math

import pytest

from noetharaclipz.local_detector import candidate_windows, detect
from noetharaclipz.media import run


@pytest.mark.parametrize("duration", [0, -1, float("nan"), float("inf"), 301])
def test_invalid_media_bounds_rejected(duration):
    with pytest.raises(ValueError):
        candidate_windows(duration, [], [])


@pytest.mark.parametrize("duration", [0.75, 1.5, 2.99])
def test_short_valid_media_gets_one_full_duration_candidate(duration):
    windows = candidate_windows(duration, [], [])
    assert windows == [(0.0, round(duration, 3))]


def test_scene_and_speech_candidates_stay_inside_source():
    windows = candidate_windows(
        60, [{"start": 12.2}, {"start": 55}, {"start": 100}], [{"start": 24.1}]
    )
    assert any(abs(a - 12.2) < 0.001 or abs(a - 23.1) < 0.001 for a, _ in windows)
    assert all(0 <= a < b <= 60 and b - a <= 10.001 for a, b in windows)
    assert len(windows) <= 8


@pytest.fixture
def prepared(tmp_path):
    source = tmp_path / "source.mp4"
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
            str(source),
        ]
    )
    data = {"metadata": {"duration": 4}, "scenes": [], "audio_events": [], "source_hash": "fixture"}
    return source, data, tmp_path


def test_model_none_does_not_fabricate_highlight(prepared):
    class Reject:
        def choose(self, paths, prompt, evidence):
            assert paths and all(p.stat().st_size > 0 for p in paths)
            return {"choice": "Z"}

        def describe(self, path):
            raise AssertionError("No description should be generated for rejected video")

    source, data, directory = prepared
    assert detect(source, data, [], "No supported event", directory, Reject())["highlights"] == []


def test_model_choice_controls_interval_and_trace(prepared):
    class Choose:
        def choose(self, paths, prompt, evidence):
            assert evidence[0]["start"] == 0
            return {
                "choice": "A",
                "relative_choice_scores": {"A": 0.8, "Z": 0.2},
                "video_tensor_sha256": "fixture-only",
            }

        def describe(self, path):
            return "Fixture description; not AI inference"

    source, data, directory = prepared
    result = detect(source, data, [], "A visible scene", directory, Choose())
    highlight = result["highlights"][0]
    assert math.isfinite(highlight["start"]) and highlight["start"] == 0 and highlight["end"] == 4
    assert "fixture-only" in highlight["visual_evidence"]
    assert result["hosted_inference"] is False
