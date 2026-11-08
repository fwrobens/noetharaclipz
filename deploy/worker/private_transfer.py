"""Download a temporary private JSON-chunk transfer using only scoped signed URLs.

No account credentials, Docker invocation, model loading or queue access. The
manifest SHA256 must be supplied independently through the reviewed handoff.
"""

import argparse
import base64
import hashlib
import json
import re
import tarfile
import urllib.parse
import urllib.request
from pathlib import Path, PurePosixPath

HOST = "zxdnjnsghdnviflahvry.supabase.co"
BUCKET = "processing-artifacts"
MAX_CHUNK = 4 * 1024**2


def checked_url(url, prefix):
    parsed = urllib.parse.urlsplit(url)
    path = urllib.parse.unquote(parsed.path)
    if (parsed.scheme != "https" or parsed.netloc != HOST or parsed.fragment
            or not path.startswith("/storage/v1/object/sign/" + BUCKET + "/" + prefix)
            or ".." in PurePosixPath(path).parts):
        raise ValueError("Unexpected signed download destination")
    return url


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def get_bytes(url, limit):
    # Never forward a signed capability to a redirect destination.
    opener = urllib.request.build_opener(NoRedirect)
    with opener.open(url, timeout=60) as response:
        raw = response.read(limit + 1)
    if len(raw) > limit:
        raise ValueError("Download exceeds reviewed size")
    return raw


def decode_chunk(raw, expected, sequence):
    part = json.loads(raw)
    if (part.get("format") != "noetharaclipz-worker-transfer-chunk-v1"
            or part.get("encoding") != "base85" or part.get("sequence") != sequence
            or part.get("sha256") != expected["sha256"]):
        raise ValueError("Unexpected chunk metadata")
    if not 0 < expected["bytes"] <= MAX_CHUNK:
        raise ValueError("Unexpected chunk length")
    encoded = part["data"]
    if len(encoded) > MAX_CHUNK * 5 // 4 + 5:
        raise ValueError("Encoded chunk is too large")
    decoded = base64.b85decode(encoded)
    if (len(decoded) != expected["bytes"]
            or hashlib.sha256(decoded).hexdigest() != expected["sha256"]):
        raise ValueError("Chunk digest mismatch")
    return decoded


def extract_config(path, target):
    with tarfile.open(path, "r:gz") as archive:
        members = archive.getmembers()
        if len(members) > 1000 or sum(m.size for m in members) > 20 * 1024**2:
            raise ValueError("Configuration archive is too large")
        for member in members:
            if (member.name.startswith("/") or ".." in PurePosixPath(member.name).parts
                    or not (member.isdir() or member.isfile())):
                raise ValueError("Unsafe configuration archive member")
        target.mkdir(mode=0o700, exist_ok=False)
        for member in members:
            dest = target / member.name
            if member.isdir():
                dest.mkdir(mode=0o700, parents=True, exist_ok=True)
            else:
                dest.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                with archive.extractfile(member) as source, dest.open("xb") as output:
                    while chunk := source.read(1024 * 1024):
                        output.write(chunk)
                dest.chmod(0o600)


def download(url, expected_sha, output):
    if not re.fullmatch(r"[0-9a-f]{64}", expected_sha):
        raise ValueError("Reviewed manifest SHA256 required")
    raw = get_bytes(checked_url(url, "_worker-transfer/"), 1024**2)
    if hashlib.sha256(raw).hexdigest() != expected_sha:
        raise ValueError("Manifest digest mismatch")
    manifest = json.loads(raw)
    prefix = manifest["prefix"]
    if not re.fullmatch(r"_worker-transfer/[0-9a-f-]{36}/", prefix):
        raise ValueError("Unexpected dedicated transfer prefix")
    checked_url(url, prefix)
    if manifest.get("format") != "noetharaclipz-worker-transfer-v1":
        raise ValueError("Unexpected transfer format")
    if manifest.get("image_id") != "sha256:32fd88495ceab2c59ab7bc6a0c7980c1003d9b4b6eea507131783a24be4b88a5":
        raise ValueError("Transfer is not the reviewed image")
    files = manifest["files"]
    if {f["name"] for f in files} != {"worker-image.tar.xz", "worker-config.tar.gz"} or len(files) != 2:
        raise ValueError("Unexpected transfer files")
    if sum(f["bytes"] for f in files) > 1024**3:
        raise ValueError("Transfer exceeds reviewed size")
    for file in files:
        if (not 0 < file["bytes"] <= 1024**3 or not 0 < len(file["chunks"]) <= 256
                or sum(part["bytes"] for part in file["chunks"]) != file["bytes"]):
            raise ValueError("Inconsistent chunk lengths")
    output = Path(output)
    output.mkdir(mode=0o700, exist_ok=False)
    for file in files:
        h, size = hashlib.sha256(), 0
        with (output / file["name"]).open("xb") as target:
            for sequence, part in enumerate(file["chunks"]):
                data = decode_chunk(get_bytes(checked_url(part["url"], prefix), 6 * 1024**2), part, sequence)
                h.update(data)
                size += len(data)
                target.write(data)
        if size != file["bytes"] or h.hexdigest() != file["sha256"]:
            raise ValueError("Completed file digest mismatch")
        (output / file["name"]).chmod(0o600)
        print(json.dumps({"verified_file": file["name"], "bytes": size, "sha256": h.hexdigest()}), flush=True)
    extract_config(output / "worker-config.tar.gz", output / "config")
    print(json.dumps({"transfer_verified": True, "directory": str(output.resolve()),
                      "image_id": manifest["image_id"], "worker_started": False}))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--url-file", type=Path, required=True)
    p.add_argument("--manifest-sha256", required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    try:
        download(args.url_file.read_text().strip(), args.manifest_sha256, args.output)
    except Exception:
        # urllib exceptions can contain signed URLs. Do not log capability URLs.
        raise SystemExit("Private transfer failed; no worker started. Check link expiry, hashes and free disk.") from None


if __name__ == "__main__":
    main()
