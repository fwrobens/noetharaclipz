"""Actual FFmpeg integration tests. No model stubs count as AI verification."""

import json
import os
from pathlib import Path
import pytest
from noetharaclipz.media import ass_escape, probe, render, run
from noetharaclipz.models import Candidate, Edit, rank_candidates


@pytest.fixture(scope="module")
def source(tmp_path_factory):
    path = tmp_path_factory.mktemp("media") / "source.mp4"
    # Real decoded audio/video, generated locally solely for deterministic codec tests.
    run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=320x180:rate=24:duration=3",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=3",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-shortest",
            str(path),
        ]
    )
    return path


@pytest.mark.parametrize(
    "ratio,size",
    [("9:16", (720, 1280)), ("16:9", (1280, 720)), ("1:1", (720, 720)), ("4:5", (720, 900))],
)
def test_ffmpeg_exports_valid_files(source, tmp_path, ratio, size):
    transcript = [
        {
            "id": "0",
            "start": 0.2,
            "end": 2.8,
            "text": "Caption {\\pos(0,0)} stays plain",
            "words": [],
        }
    ]
    edit = Edit(start=0.5, end=2.5, ratio=ratio, crop_x=0.2, volume=0.7)
    result = render(source, edit, transcript, tmp_path / "clip.mp4")
    assert (result["width"], result["height"]) == size
    assert abs(result["duration"] - 2) < 0.15
    meta = json.loads(
        run(["ffprobe", "-v", "error", "-show_streams", "-of", "json", str(tmp_path / "clip.mp4")])
    )
    assert [s["codec_name"] for s in meta["streams"]] == ["h264", "aac"]


def test_trims_cannot_escape_actual_media(source, tmp_path):
    with pytest.raises(ValueError, match="beyond"):
        render(source, Edit(start=1, end=10), [], tmp_path / "invalid.mp4")


def test_invalid_file_rejected(tmp_path):
    path = tmp_path / "bad.mp4"
    path.write_text("not video")
    with pytest.raises(RuntimeError):
        probe(path)


def test_highlight_validation_and_overlap_suppression():
    def c(start, end, score):
        return Candidate(
            start=start,
            end=end,
            score=score,
            title="Observed event",
            category="Other",
            explanation="Evidence",
            visual_evidence="Visible action",
        )

    highlights = rank_candidates([c(1, 9, 90), c(2, 10, 80), c(20, 30, 70), c(90, 110, 99)], 100)
    assert [(h.start, h.end) for h in highlights] == [(1, 9), (20, 30)]


def test_unsafe_caption_formatting_removed():
    assert "{" not in ass_escape(r"{\pos(0,0)} caption")


@pytest.mark.skipif(
    not os.getenv("NC_SAMPLE_VIDEO"), reason="Set NC_SAMPLE_VIDEO for authorized footage"
)
def test_authorized_sample_transcription_and_render(tmp_path):
    from noetharaclipz.media import prepare, transcribe

    data = prepare(Path(os.environ["NC_SAMPLE_VIDEO"]), tmp_path)
    transcript = transcribe(data["audio"])
    assert transcript and all(
        0 <= s["start"] < s["end"] <= data["metadata"]["duration"] for s in transcript
    )
    assert data["frames"] and data["scenes"] and data["waveform"]
    first = transcript[0]
    edit = Edit(
        start=max(0, first["start"] - 1), end=min(data["metadata"]["duration"], first["end"] + 1)
    )
    result = render(
        Path(os.environ["NC_SAMPLE_VIDEO"]), edit, transcript, tmp_path / "authorized-clip.mp4"
    )
    assert result["has_audio"]


def test_playlist_cannot_open_local_or_remote_resources(tmp_path):
    playlist = tmp_path / "spoofed.mp4"
    playlist.write_text(
        "#EXTM3U\n#EXT-X-TARGETDURATION:5\n#EXTINF:5,\nhttp://127.0.0.1/private\n#EXT-X-ENDLIST\n"
    )
    with pytest.raises(RuntimeError, match="Media operation failed"):
        probe(playlist)


def test_cancellation_interrupts_an_actual_subprocess():
    import sys
    from noetharaclipz.media import Cancelled

    def cancel():
        raise Cancelled("User cancelled")

    with pytest.raises(Cancelled):
        run([sys.executable, "-c", "import time; time.sleep(20)"], timeout=2, tick=cancel)


def test_subprocess_deadline_is_enforced():
    import sys

    with pytest.raises(TimeoutError):
        run([sys.executable, "-c", "import time; time.sleep(20)"], timeout=0.1)
