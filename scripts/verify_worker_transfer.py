"""Verify a Docker-save archive offline against its immutable reviewed image ID.

Streams every content-addressed blob, validates the rootfs, architecture,
runtime user and standby/local defaults. Does not load or run the image.
"""

import argparse
import hashlib
import json
import re
import tarfile
from pathlib import Path, PurePosixPath


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def digest_bytes(raw, expected):
    # imagetools can append a terminal newline when displaying registry JSON.
    return any("sha256:" + hashlib.sha256(x).hexdigest() == expected
               for x in (raw, raw.removesuffix(b"\n")))


def verify_image(path, image_id):
    expected = image_id.removeprefix("sha256:")
    if not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise ValueError("Invalid image ID")
    seen, blobs, small = set(), set(), {}
    with tarfile.open(path, "r|*") as archive:
        for member in archive:
            name = member.name
            if name in seen or PurePosixPath(name).is_absolute() or ".." in PurePosixPath(name).parts:
                raise ValueError("Unsafe/duplicate image archive member")
            seen.add(name)
            if member.isdir():
                continue
            if not member.isfile() or member.size > 8 * 1024**3:
                raise ValueError("Unsupported image archive member")
            stream = archive.extractfile(member)
            h, captured = hashlib.sha256(), bytearray()
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                h.update(chunk)
                if member.size <= 2 * 1024**2:
                    captured.extend(chunk)
            if name.startswith("blobs/sha256/"):
                if h.hexdigest() != name.split("/")[-1]:
                    raise ValueError("Image blob digest mismatch")
                blobs.add(name)
            if captured:
                small[name] = bytes(captured)
    entries = json.loads(small["manifest.json"])
    if len(entries) != 1:
        raise ValueError("Expected one image")
    entry = entries[0]
    if entry["Config"] != "blobs/sha256/" + expected:
        raise ValueError("Image config does not match expected ID")
    config = json.loads(small[entry["Config"]])
    if config.get("os") != "linux" or config.get("architecture") != "amd64":
        raise ValueError("Expected linux/amd64")
    if config["config"].get("User") != "62001:62001" or config["config"].get("ExposedPorts"):
        raise ValueError("Unexpected runtime user/ports")
    env = dict(v.split("=", 1) for v in config["config"]["Env"])
    if any(env.get(k) != v for k, v in {
        "NC_AI_PROVIDER": "local", "GEMINI_FREE_TIER_VERIFIED": "false",
        "NC_DEPLOY_MODE": "standby",
    }.items()):
        raise ValueError("Unsafe image defaults")
    if any(name not in blobs for name in entry["Layers"]):
        raise ValueError("Missing verified layer")
    diff_ids = config["rootfs"]["diff_ids"]
    if diff_ids != ["sha256:" + name.rsplit("/", 1)[-1] for name in entry["Layers"]]:
        raise ValueError("Layer contents do not match image rootfs")
    return config



def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--image-id", required=True)
    args = parser.parse_args()
    config = verify_image(args.archive, args.image_id)
    print(json.dumps({"verified": True, "archive_sha256": sha256(args.archive),
                      "image_id": args.image_id, "architecture": config["architecture"],
                      "os": config["os"], "worker_started": False}, indent=2))


if __name__ == "__main__":
    main()
