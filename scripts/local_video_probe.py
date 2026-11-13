"""Optional LOCAL research probe. Descriptions are not AI-selected highlights.

Use the isolated, pinned environment in docs/provider-readiness.md. Never selects
another provider or submits media to a hosted API. No remote Python model code.
"""

import argparse
import json
import subprocess
import tempfile
import time
from pathlib import Path

MODEL = "HuggingFaceTB/SmolVLM2-500M-Video-Instruct"
REVISION = "7b375e1b73b11138ff12fe22c8f2822d8fe03467"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--start", type=float, default=11)
    parser.add_argument("--end", type=float, default=21)
    parser.add_argument(
        "--output", type=Path, default=Path("test-results/local-video-description.json")
    )
    args = parser.parse_args()
    if not 0 <= args.start < args.end or args.end - args.start > 15:
        parser.error("Use an authorized interval of at most 15 seconds")
    import torch
    from transformers import AutoProcessor, AutoModelForImageTextToText

    torch.set_num_threads(3)
    processor = AutoProcessor.from_pretrained(
        MODEL, revision=REVISION, trust_remote_code=False
    )
    model = AutoModelForImageTextToText.from_pretrained(
        MODEL,
        revision=REVISION,
        dtype=torch.float32,
        attn_implementation="sdpa",
        trust_remote_code=False,
    )
    with tempfile.TemporaryDirectory(prefix="nc-local-probe-") as temp:
        clip = Path(temp) / "window.mp4"
        subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-nostdin",
                "-y",
                "-protocol_whitelist",
                "file,pipe",
                "-format_whitelist",
                "mov,matroska,webm",
                "-ss",
                str(args.start),
                "-i",
                str(args.source.resolve(strict=True)),
                "-t",
                str(args.end - args.start),
                "-vf",
                "scale=320:-2",
                "-an",
                "-c:v",
                "libx264",
                str(clip),
            ],
            check=True,
            timeout=120,
        )
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "video", "path": str(clip)},
                    {
                        "type": "text",
                        "text": "Describe the visible actions and characters in at most three short sentences. Do not invent dialogue or speculate about events outside this video.",
                    },
                ],
            }
        ]
        started = time.monotonic()
        inputs = processor.apply_chat_template(
            messages,
            add_generation_prompt=True,
            tokenize=True,
            return_dict=True,
            return_tensors="pt",
            num_frames=4,
        )
        with torch.inference_mode():
            output = model.generate(**inputs, max_new_tokens=160, do_sample=False)
        text = processor.batch_decode(
            output[:, inputs["input_ids"].shape[1] :], skip_special_tokens=True
        )[0]
        result = {
            "provider": "local-smolvlm2",
            "model": MODEL,
            "revision": REVISION,
            "source_interval": [args.start, args.end],
            "video_tensor_shape": list(inputs["pixel_values"].shape),
            "input_tokens": int(inputs["input_ids"].shape[1]),
            "output_tokens": int(output.shape[1] - inputs["input_ids"].shape[1]),
            "description": text,
            "inference_seconds": round(time.monotonic() - started, 2),
            "selection_method": "none: visual description only; not an AI-selected or heuristic highlight",
            "hosted_inference": False,
            "quality": "Not validated for automatic highlight selection",
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
