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


def verified_runtime_ids(small, entry, image_id):
    """Bind Docker config IDs and OCI manifest IDs to the same reviewed content.

    Engines using the classic store can report the config digest as .Id;
    containerd-backed engines can report the OCI manifest digest instead.
    Never accept an unrelated digest merely because it appears in the archive.
    """
    ids = {image_id}
    if "index.json" not in small:
        return ids
    index = json.loads(small["index.json"])
    manifests = index.get("manifests", [])
    if index.get("schemaVersion") != 2 or len(manifests) != 1:
        raise ValueError("Expected one indexed image manifest")
    descriptor = manifests[0]
    manifest_id = descriptor["digest"]
    if (descriptor.get("mediaType") != "application/vnd.oci.image.manifest.v1+json"
            or not re.fullmatch(r"sha256:[0-9a-f]{64}", manifest_id)):
        raise ValueError("Unexpected indexed manifest")
    raw = small["blobs/sha256/" + manifest_id.removeprefix("sha256:")]
    if ("sha256:" + hashlib.sha256(raw).hexdigest() != manifest_id
            or len(raw) != descriptor["size"]):
        raise ValueError("OCI manifest digest/size mismatch")
    manifest = json.loads(raw)
    if (manifest.get("schemaVersion") != 2 or manifest.get("mediaType") != descriptor["mediaType"]
            or manifest["config"]["digest"] != image_id
            or manifest["config"]["size"] != len(small[entry["Config"]])):
        raise ValueError("OCI manifest does not reference reviewed config")
    layers = ["sha256:" + name.rsplit("/", 1)[-1] for name in entry["Layers"]]
    if [layer["digest"] for layer in manifest["layers"]] != layers:
        raise ValueError("OCI manifest does not reference reviewed layers")
    ids.add(manifest_id)
    return ids


def verify_image(path, image_id, runtime_id=None):
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
    identities = verified_runtime_ids(small, entry, image_id)
    if runtime_id is not None and runtime_id not in identities:
        raise ValueError("Runtime ID does not identify the reviewed config/manifest")
    return config



def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--image-id", required=True)
    parser.add_argument("--runtime-id", help="Optional reported Docker ID; must bind to this config/layers")
    args = parser.parse_args()
    config = verify_image(args.archive, args.image_id, args.runtime_id)
    print(json.dumps({"verified": True, "archive_sha256": sha256(args.archive),
                      "image_id": args.image_id, "architecture": config["architecture"],
                      "runtime_id": args.runtime_id, "runtime_id_verified": args.runtime_id is not None,
                      "os": config["os"], "worker_started": False}, indent=2))


if __name__ == "__main__":
    main()
