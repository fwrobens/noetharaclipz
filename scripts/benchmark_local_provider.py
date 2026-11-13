"""Actual local-model, cache and cancellation benchmarks; never connects to Supabase."""

import argparse
import json
import os
import resource
import sys
import threading
import time
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "worker"))


def main():
    from noetharaclipz.config import Settings
    from noetharaclipz.local_provider import LocalProvider
    from noetharaclipz.media import Cancelled

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--only", help="Run one named sample; otherwise run every case")
    args = parser.parse_args()
    settings = replace(Settings(), provider="local")
    provider = LocalProvider(settings)
    started = time.monotonic()
    provider.preflight()
    warmup = time.monotonic() - started
    report = {
        "model": provider.model,
        "model_loads": 1,
        "warmup_seconds": warmup,
        "hosted_api_calls": 0,
        "trials": [],
    }
    cases = [
        (
            "elephants-dream",
            "test-results/elephants-dream-sample.mp4",
            "Find a spoken reaction with visible movement; preserve the whole speech.",
        ),
        (
            "sintel",
            "test-results/sintel-source.mp4",
            "Find a clearly visible surprising or dramatic action, excluding title cards.",
        ),
        (
            "supertuxkart",
            "test-results/supertuxkart-sample.mp4",
            "Find sudden racing action such as a crash, sharp drift or boost; exclude menu screens.",
        ),
        (
            "black-silence-negative",
            "test-results/negative-black-silence.mp4",
            "Find an interesting visible action or spoken reaction.",
        ),
        (
            "quiet-visual",
            "test-results/sintel-quiet-visual.mp4",
            "Find a quiet but visually interesting moment, excluding text cards. No speech is available.",
        ),
    ]
    if args.only:
        cases = [case for case in cases if case[0] == args.only]
        if not cases:
            parser.error("Unknown sample name")
    for name, path, prompt in cases:
        for repeat in range(2):
            source = ROOT / path
            begin = time.monotonic()
            cpu = time.process_time()
            rss = [
                int(Path("/proc/self/statm").read_text().split()[1])
                * os.sysconf("SC_PAGE_SIZE")
            ]
            stop = threading.Event()

            def sample():
                while not stop.wait(0.1):
                    rss.append(
                        int(Path("/proc/self/statm").read_text().split()[1])
                        * os.sysconf("SC_PAGE_SIZE")
                    )

            monitor = threading.Thread(target=sample, daemon=True)
            monitor.start()
            try:
                data = provider.prepare(source, lambda: None)
                transcript = provider.transcript(data, lambda: None)
                analysis, result, cachefile = provider.analyze(
                    source, data, transcript, prompt, lambda: None
                )
                elapsed = time.monotonic() - begin
                used_cpu = time.process_time() - cpu
                row = {
                    "sample": name,
                    "repeat": repeat,
                    "wall_seconds": round(elapsed, 3),
                    "cpu_seconds": round(used_cpu, 3),
                    "average_cpu_percent_one_core": round(100 * used_cpu / elapsed, 2),
                    "peak_rss_bytes": max(rss, default=0),
                    "process_max_rss_kib": resource.getrusage(
                        resource.RUSAGE_SELF
                    ).ru_maxrss,
                    "cache": dict(provider.metrics),
                    "execution_usage": result["execution_usage"],
                    "original_usage": result["local_usage"],
                    "model_decision": result["decision"],
                    "highlights": [h.model_dump() for h in analysis.highlights],
                    "scenes": len(data["scenes"]),
                    "speech_segments": len(transcript),
                    "audio_events": len(data["audio_events"]),
                    "raw_visual_observation": result["raw_visual_observation"],
                    "quality_metrics": result["quality_metrics"],
                    "cache_path": str(cachefile.relative_to(provider.root)),
                }
                if repeat:
                    assert (
                        provider.metrics["analysis_cache_hit"]
                        and result["execution_usage"]["input_tokens"] == 0
                    )
                    assert row["highlights"] == report["trials"][-1]["highlights"]
                report["trials"].append(row)
                print(json.dumps(row), flush=True)
            finally:
                stop.set()
                monitor.join()
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(report, indent=2) + "\n")
    calls = 0

    def cancel():
        nonlocal calls
        calls += 1
        if calls > 1:
            raise Cancelled("Actual layer-hook cancellation test")

    candidate = next(provider.root.glob("*/candidate-0.mp4"))
    begin = time.monotonic()
    try:
        with provider.ranker.checkpoints(cancel):
            provider.ranker.describe(candidate)
    except Cancelled:
        report["actual_model_cancellation"] = {
            "passed": True,
            "checkpoint_calls": calls,
            "seconds": round(time.monotonic() - begin, 3),
        }
    else:
        raise AssertionError("Actual model computation ignored cancellation")
    args.output.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
