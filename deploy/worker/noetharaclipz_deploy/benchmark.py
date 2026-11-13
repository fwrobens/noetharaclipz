"""Offline gaming comparison. No Supabase imports, credentials, queue or inference API.

Use the Docker runner to enforce 8 GiB/2 CPU limits and network=none. A memory
watchdog aborts before exhausting the cgroup. 2.2B BF16 is research only; the
production worker and database provider allowlist remain unchanged.
"""

import argparse
import hashlib
import json
import os
import resource
import threading
import time
from pathlib import Path
from noetharaclipz.local_detector import LocalVideoRanker, candidate_windows
from noetharaclipz.media import ffmpeg, prepare, run, transcribe

MODELS = {
    "500m": (
        "HuggingFaceTB/SmolVLM2-500M-Video-Instruct",
        "7b375e1b73b11138ff12fe22c8f2822d8fe03467",
        507482304,
        "float32",
    ),
    "2.2b": (
        "HuggingFaceTB/SmolVLM2-2.2B-Instruct",
        "482adb537c021c86670beed01cd58990d01e72e4",
        2246784880,
        "bfloat16",
    ),
}


def memory():
    return int(Path("/proc/self/statm").read_text().split()[1]) * os.sysconf(
        "SC_PAGE_SIZE"
    )


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("mode", choices=["prepare", *MODELS])
    args = p.parse_args()
    root = Path("/reports")
    root.mkdir(exist_ok=True)
    if args.mode == "prepare":
        started = time.monotonic()
        source = root / "gaming-20-to-50.mp4"
        # Keep the original game's audio in this derivative for measured evidence.
        run(
            ffmpeg(
                Path("/samples/gaming.mp4"),
                "-t",
                30,
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-c:a",
                "aac",
                source,
                seek=20,
            )
        )
        data = prepare(source, root)
        transcript = transcribe(data["audio"], "small")
        windows = candidate_windows(
            data["metadata"]["duration"], data["scenes"], transcript, limit=4
        )
        candidates = []
        for i, (start, end) in enumerate(windows):
            path = root / f"benchmark-candidate-{i}.mp4"
            run(
                ffmpeg(
                    source,
                    "-t",
                    end - start,
                    "-vf",
                    "scale=320:-2",
                    "-an",
                    "-c:v",
                    "libx264",
                    "-preset",
                    "veryfast",
                    path,
                    seek=start,
                )
            )
            candidates.append(
                {
                    "file": path.name,
                    "start": start,
                    "end": end,
                    "speech": [
                        s for s in transcript if s["end"] > start and s["start"] < end
                    ],
                    "audio_events": [
                        e for e in data["audio_events"] if start <= e["time"] < end
                    ][:30],
                    "scene_boundaries": [
                        s for s in data["scenes"] if start <= s["start"] < end
                    ],
                }
            )
        with Path("/samples/gaming.mp4").open("rb") as f:
            original_hash = hashlib.file_digest(f, "sha256").hexdigest()
        report = {
            "original_sha256": original_hash,
            "source_sha256": data["source_hash"],
            "original_offset": 20,
            "duration": data["metadata"]["duration"],
            "speech_segments": len(transcript),
            "scene_count": len(data["scenes"]),
            "candidates": candidates,
            "prepare_seconds": round(time.monotonic() - started, 3),
            "reference": {
                "original_interval": [25, 45],
                "observation": "Coarse human review: racing, off-road/water and boost/curve. No microphone speech; not verified humor. Single authorized sample, not a labeled accuracy corpus.",
            },
        }
        (root / "prepared-benchmark.json").write_text(
            json.dumps(report, indent=2) + "\n"
        )
        print(json.dumps(report), flush=True)
        return
    model, revision, parameters, dtype = MODELS[args.mode]
    prepared = json.loads((root / "prepared-benchmark.json").read_text())
    report = {
        "model": model,
        "revision": revision,
        "dtype": dtype,
        "parameters": parameters,
        "float32_weights_bytes": parameters * 4,
        "float32_fits_8gib_weights_only": parameters * 4 < 8 * 1024**3,
        "network": "none",
        "queue_access": False,
        "status": "running",
        "phase": "loading",
        "source": prepared,
        "peak_rss_bytes": memory(),
    }
    target = root / (args.mode + ".json")
    started, cpu = time.monotonic(), time.process_time()
    stopped = threading.Event()

    def save():
        tmp = target.with_suffix(".tmp")
        tmp.write_text(json.dumps(report, indent=2) + "\n")
        tmp.replace(target)

    def monitor():
        while not stopped.wait(0.2):
            report["peak_rss_bytes"] = max(report["peak_rss_bytes"], memory())
            elapsed = time.monotonic() - started
            if report["peak_rss_bytes"] > 7.25 * 1024**3 or elapsed > 600:
                report["status"] = "aborted_before_resource_exhaustion"
                report["wall_seconds"] = round(elapsed, 3)
                report["cpu_seconds"] = round(time.process_time() - cpu, 3)
                save()
                os._exit(75)

    monitor_thread = threading.Thread(target=monitor, daemon=True)
    monitor_thread.start()
    try:
        import torch
        from transformers import AutoModelForImageTextToText, AutoProcessor

        ranker = LocalVideoRanker.__new__(LocalVideoRanker)
        torch.set_num_threads(2)
        ranker.torch = torch
        ranker.processor = AutoProcessor.from_pretrained(
            model, revision=revision, trust_remote_code=False, local_files_only=True
        )
        ranker.model = AutoModelForImageTextToText.from_pretrained(
            model,
            revision=revision,
            dtype=getattr(torch, dtype),
            attn_implementation="sdpa",
            trust_remote_code=False,
            local_files_only=True,
        ).eval()
        report["load_seconds"] = round(time.monotonic() - started, 3)
        paths = [root / c["file"] for c in prepared["candidates"]]
        evidence = [
            {k: v for k, v in c.items() if k != "file"} for c in prepared["candidates"]
        ]
        report["phase"] = "inference"
        began = time.monotonic()
        decision = ranker.choose(
            paths,
            "Find sudden racing action such as a sharp drift, boost or unexpected event. Exclude menus and title cards. Choose Z if none is supported.",
            evidence,
        )
        report["comparison_seconds"] = round(time.monotonic() - began, 3)
        report["decision"] = decision
        if decision["choice"] != "Z":
            i = "ABCDEFGH".index(decision["choice"])
            chosen = prepared["candidates"][i]
            report["original_interval"] = [
                round(chosen["start"] + 20, 3),
                round(chosen["end"] + 20, 3),
            ]
            report["raw_visual_observation"] = ranker.describe(paths[i])
            a, b = report["original_interval"]
            report["coarse_reference_overlap_seconds"] = round(
                max(0, min(b, 45) - max(a, 25)), 3
            )
        report["visual_observation_warning"] = (
            "Unverified model hypothesis, separate from measured audio/transcript/scene evidence. No calibrated accuracy claim."
        )
        report["status"] = "completed"
    except Exception as exc:
        report["status"] = "failed"
        report["error_type"] = type(exc).__name__
        raise
    finally:
        stopped.set()
        monitor_thread.join()
        report["peak_rss_bytes"] = max(report["peak_rss_bytes"], memory())
        report["wall_seconds"] = round(time.monotonic() - started, 3)
        report["cpu_seconds"] = round(time.process_time() - cpu, 3)
        report["cpu_percent_one_core"] = round(
            100 * report["cpu_seconds"] / max(0.001, report["wall_seconds"]), 2
        )
        report["max_rss_kib"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        report["cpu_model"] = next(
            (
                line.split(":", 1)[1].strip()
                for line in Path("/proc/cpuinfo").read_text().splitlines()
                if line.startswith("model name")
            ),
            None,
        )
        save()
        print(json.dumps(report), flush=True)


if __name__ == "__main__":
    main()
