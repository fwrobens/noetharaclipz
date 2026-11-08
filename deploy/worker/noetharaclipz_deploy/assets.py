"""Pinned public model download only. No credentials, inference or queue calls."""

import json
from pathlib import Path
from huggingface_hub import snapshot_download
from noetharaclipz.local_detector import MODEL, REVISION

WHISPER_REVISION = "536b0662742c02347bc0e980a01041f333bce120"


def main():
    snapshot_download(
        MODEL,
        revision=REVISION,
        allow_patterns=[
            "*.json",
            "*.safetensors",
            "*.txt",
            "*.model",
            "*.jinja",
            "README.md",
        ],
    )
    snapshot_download(
        "Systran/faster-whisper-small",
        revision=WHISPER_REVISION,
        local_dir="/models/whisper-small",
    )
    Path("/models/manifest.json").write_text(
        json.dumps(
            {
                "video_model": MODEL,
                "video_revision": REVISION,
                "whisper_revision": WHISPER_REVISION,
            },
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
