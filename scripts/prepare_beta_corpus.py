"""Prepare licensed real footage locally. No AI, Supabase, queue or EC2 access."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
from urllib.parse import urlsplit
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.file_digest(path.open("rb"), "sha256").hexdigest()


def run(*args):
    return subprocess.check_output(args, text=True, timeout=180)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    os.umask(0o077)
    args.output.mkdir(mode=0o700, parents=True, exist_ok=False)
    plan = json.loads((ROOT / "deploy/beta/corpus.json").read_text())
    sources = {}
    for index, source in enumerate(plan["sources"]):
        url = urlsplit(source["download_url"])
        if (
            url.scheme != "https"
            or url.netloc != "upload.wikimedia.org"
            or url.query
            or url.fragment
        ):
            raise ValueError("Only reviewed public Wikimedia derivatives are permitted")
        path = args.output / f"source-{index}.webm"
        request = urllib.request.Request(
            source["download_url"],
            headers={"User-Agent": "NoetharaClipz licensed QA corpus/1.0"},
        )
        count = 0
        with (
            urllib.request.urlopen(request, timeout=45) as response,
            path.open("xb") as stream,
        ):
            if response.geturl() != source["download_url"]:
                raise ValueError("Source redirect requires review")
            while chunk := response.read(256 * 1024):
                count += len(chunk)
                if count > 48_000_000:
                    raise ValueError("Source download budget exceeded")
                stream.write(chunk)
        observed = sha(path)
        if source.get("source_sha256") and observed != source["source_sha256"]:
            raise ValueError("Reviewed source bytes changed")
        sources[source["game"]] = {
            **source,
            "path": path,
            "observed_sha256": observed,
            "downloaded_bytes": count,
        }
    samples = []
    for sample in plan["samples"]:
        source = sources[sample["game"]]
        path = args.output / f"sample-{sample['id']}.mp4"
        run(
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-nostdin",
            "-n",
            "-ss",
            str(sample["start"]),
            "-i",
            str(source["path"]),
            "-t",
            str(sample["seconds"]),
            "-map",
            "0:v:0",
            "-map",
            "0:a:0?",
            "-vf",
            "scale=854:-2,fps=24",
            "-c:v",
            "libx264",
            "-threads",
            "2",
            "-preset",
            "fast",
            "-crf",
            "27",
            "-maxrate",
            "850k",
            "-bufsize",
            "1700k",
            "-c:a",
            "aac",
            "-b:a",
            "96k",
            "-movflags",
            "+faststart",
            str(path),
        )
        probe = json.loads(
            run(
                "ffprobe",
                "-v",
                "error",
                "-show_format",
                "-show_streams",
                "-of",
                "json",
                str(path),
            )
        )
        duration = float(probe["format"]["duration"])
        if path.stat().st_size > 15_000_000 or not 58 <= duration <= 62:
            raise ValueError("Prepared sample exceeds approved media budget")
        run(
            "ffmpeg",
            "-v",
            "error",
            "-nostdin",
            "-threads",
            "2",
            "-i",
            str(path),
            "-f",
            "null",
            "-",
        )
        samples.append(
            {
                **sample,
                "file": path.name,
                "sha256": sha(path),
                "bytes": path.stat().st_size,
                "duration_seconds": duration,
                "audio_present": any(
                    s["codec_type"] == "audio" for s in probe["streams"]
                ),
                "decode_passed": True,
                "ai_inference_run": False,
                "source_sha256": source["observed_sha256"],
                "changes": "Trimmed interval; 480p/24fps H.264/AAC transcode. No captions or synthetic events.",
            }
        )
    receipt = {
        "prepared_utc": datetime.now(timezone.utc).isoformat(),
        "sources": [
            {k: v for k, v in row.items() if k != "path"} for row in sources.values()
        ],
        "samples": samples,
        "uploads_performed": 0,
        "processing_started": False,
    }
    (args.output / "receipt.json").write_text(
        json.dumps(receipt, indent=2, ensure_ascii=False) + "\n"
    )
    print(
        json.dumps(
            {
                "prepared": True,
                "distinct_games": len(sources),
                "samples": len(samples),
                "total_sample_bytes": sum(s["bytes"] for s in samples),
                "uploads_performed": 0,
            }
        )
    )


if __name__ == "__main__":
    main()
