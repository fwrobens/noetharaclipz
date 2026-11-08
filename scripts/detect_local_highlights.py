"""Explicit local-file detection/rendering. Never consumes the shared job queue."""

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "worker"))


def main():
    from noetharaclipz.local_detector import detect
    from noetharaclipz.media import prepare, transcribe, render
    from noetharaclipz.models import Edit

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--prompt", required=True)
    parser.add_argument(
        "--edit",
        type=Path,
        help="Optional validated saved Edit JSON for the detected interval",
    )
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    data = prepare(args.source.resolve(strict=True), args.output)
    speech = transcribe(data["audio"])
    result = detect(args.source, data, speech, args.prompt, args.output)
    result["metadata"] = data["metadata"]
    result["transcript"] = speech
    result["scenes"] = data["scenes"]
    result["audio_events"] = data["audio_events"]
    result["waveform"] = data["waveform"]
    result["frames"] = [
        {"time": f["time"], "file": f["file"].name} for f in data["frames"]
    ]
    (args.output / "analysis.json").write_text(json.dumps(result, indent=2) + "\n")
    if not result["highlights"]:
        raise RuntimeError("No supported automatic highlight; no fabricated fallback")
    h = result["highlights"][0]
    edit = (
        Edit.model_validate_json(args.edit.read_text())
        if args.edit
        else Edit(start=h["start"], end=h["end"])
    )
    (args.output / "edit.json").write_text(edit.model_dump_json(indent=2) + "\n")
    result["render"] = render(
        args.source, edit, speech, args.output / "automatic-highlight.mp4"
    )
    result["elapsed_seconds"] = round(time.monotonic() - started, 2)
    (args.output / "analysis.json").write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {
                "highlights": result["highlights"],
                "elapsed_seconds": result["elapsed_seconds"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
