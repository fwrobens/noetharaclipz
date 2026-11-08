"""Stage only reviewed worker artifacts in an EXISTING private JSON bucket.

Does not change buckets, RLS, database resources, jobs, AWS or credentials.
Signed URLs are written only to a mode-0600 local handoff; never printed.
"""

import argparse
import base64
import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "deploy/worker"))
from private_transfer import BUCKET, HOST, MAX_CHUNK, decode_chunk
from verify_worker_transfer import verify_image

BASE = "https://" + HOST
IMAGE_ID = "sha256:32fd88495ceab2c59ab7bc6a0c7980c1003d9b4b6eea507131783a24be4b88a5"


def encode_chunk(raw, sequence):
    digest = hashlib.sha256(raw).hexdigest()
    return json.dumps({"format": "noetharaclipz-worker-transfer-chunk-v1", "encoding": "base85",
                       "sequence": sequence, "sha256": digest,
                       "data": base64.b85encode(raw).decode("ascii")}, separators=(",", ":")).encode()


def private_json(path, value):
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w") as stream:
        json.dump(value, stream, indent=2)
    Path(path).chmod(0o600)


class Storage:
    def __init__(self):
        if os.environ.get("SUPABASE_URL", "").rstrip("/") != BASE:
            raise ValueError("Wrong Supabase project")
        self.key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

    def api(self, path, method="GET", body=None):
        payload = body if isinstance(body, bytes) else json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(BASE + path, method=method, data=payload, headers={
            "apikey": self.key, "Authorization": "Bearer " + self.key,
            "Content-Type": "application/json", "x-upsert": "false",
        })
        with urllib.request.urlopen(request, timeout=90) as response:
            data = response.read()
        return json.loads(data) if data else None

    def list(self, bucket, prefix):
        offset = 0
        while True:
            rows = self.api("/storage/v1/object/list/" + bucket, "POST", {
                "prefix": prefix, "limit": 100, "offset": offset,
                "sortBy": {"column": "name", "order": "asc"},
            })
            yield from rows
            if len(rows) < 100:
                break
            offset += 100

    def usage(self, buckets):
        total = 0
        for bucket in buckets:
            pending = [""]
            while pending:
                prefix = pending.pop()
                for row in self.list(bucket["id"], prefix):
                    if row.get("id") is None:
                        pending.append((prefix + "/" if prefix else "") + row["name"])
                    else:
                        metadata = row.get("metadata") or {}
                        if "size" not in metadata:
                            raise ValueError("Unknown object size; refuse capacity assumption")
                        total += int(metadata["size"])
        return total

    def put(self, key, body):
        return self.api("/storage/v1/object/" + BUCKET + "/" + key, "POST", body)

    def sign(self, key, seconds):
        value = self.api("/storage/v1/object/sign/" + BUCKET + "/" + key, "POST", {"expiresIn": seconds})
        url = value["signedURL"]
        if not url.startswith("/object/sign/" + BUCKET + "/"):
            raise ValueError("Unexpected signed URL")
        return BASE + "/storage/v1" + url


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--image", type=Path)
    p.add_argument("--config", type=Path)
    p.add_argument("--state", type=Path, required=True)
    p.add_argument("--cleanup", action="store_true")
    args = p.parse_args()
    storage = Storage()
    if args.cleanup:
        state = json.loads(args.state.read_text())
        prefix = "_worker-transfer/" + str(uuid.UUID(state["transfer_id"])) + "/"
        if state["prefix"] != prefix:
            raise ValueError("Invalid owned transfer prefix")
        names = [prefix + row["name"] for row in storage.list(BUCKET, prefix) if row.get("id")]
        for start in range(0, len(names), 50):
            storage.api("/storage/v1/object/" + BUCKET, "DELETE", {"prefixes": names[start:start + 50]})
        state["cleaned"] = True
        private_json(args.state, state)
        print(json.dumps({"cleaned_owned_objects": len(names), "unrelated_objects_modified": False}))
        return
    if not args.image or not args.config or args.state.exists():
        p.error("Image/config and a NEW private state path are required")
    verify_image(args.image, IMAGE_ID)
    buckets = storage.api("/storage/v1/bucket")
    bucket = next(x for x in buckets if x["id"] == BUCKET)
    if bucket["public"] or "application/json" not in bucket["allowed_mime_types"]:
        raise ValueError("Existing bucket is not suitable")
    if bucket["file_size_limit"] < 6 * 1024**2:
        raise ValueError("Existing bucket limit is too small")
    usage = storage.usage(buckets)
    videos = storage.api("/rest/v1/videos?select=byte_size")
    clips = storage.api("/rest/v1/clips?select=output_bytes")
    jobs = storage.api("/rest/v1/processing_jobs?select=reserved_bytes,status&status=not.in.(completed,failed,cancelled)")
    reserved = (sum((x.get("byte_size") or 0) * 2 for x in videos)
                + sum(x.get("output_bytes") or 0 for x in clips)
                + sum(x.get("reserved_bytes") or 0 for x in jobs))
    estimate = sum((path.stat().st_size * 5 + 3) // 4
                   + ((path.stat().st_size + MAX_CHUNK - 1) // MAX_CHUNK) * 1000
                   for path in (args.image, args.config)) + 1024**2
    # Existing application cap is 800MB. Reserve another 100MB for user work.
    if max(usage, reserved) + estimate > 700_000_000:
        raise ValueError("Transfer would consume reserved user storage headroom")
    transfer_id = str(uuid.uuid4())
    prefix = "_worker-transfer/" + transfer_id + "/"
    if list(storage.list(BUCKET, prefix)):
        raise ValueError("Transfer namespace collision")
    state = {"transfer_id": transfer_id, "prefix": prefix, "created_unix": int(time.time()),
             "image_id": IMAGE_ID, "objects": [], "before_object_bytes": usage,
             "database_reserved_bytes": reserved, "estimated_transfer_bytes": estimate,
             "application_storage_cap": 800_000_000, "reserved_user_headroom": 100_000_000,
             "public": False, "bucket_settings_changed": False, "urls": {}}
    private_json(args.state, state)
    files = []
    for path, name in ((args.image, "worker-image.tar.xz"), (args.config, "worker-config.tar.gz")):
        item = {"name": name, "bytes": path.stat().st_size, "chunks": []}
        total_hash = hashlib.sha256()
        with path.open("rb") as source:
            sequence = 0
            while raw := source.read(MAX_CHUNK):
                total_hash.update(raw)
                data = encode_chunk(raw, sequence)
                part = {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
                if decode_chunk(data, part, sequence) != raw:
                    raise ValueError("Chunk encoding roundtrip failed")
                key = prefix + name + "." + str(sequence).zfill(4) + ".json"
                state["objects"].append(key)
                private_json(args.state, state)
                storage.put(key, data)
                # URLs are issued together after upload so TTL does not elapse while staging.
                item["chunks"].append({**part, "key": key})
                sequence += 1
                print(json.dumps({"staged_file": name, "chunks": sequence}), flush=True)
        item["sha256"] = total_hash.hexdigest()
        files.append(item)
    expires = int(time.time()) + 3600
    for item in files:
        for part in item["chunks"]:
            part["url"] = storage.sign(part.pop("key"), 3600)
    manifest = {"format": "noetharaclipz-worker-transfer-v1", "prefix": prefix,
                "image_id": IMAGE_ID, "expires_unix": expires, "files": files,
                "source_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()}
    manifest_raw = json.dumps(manifest, separators=(",", ":")).encode()
    key = prefix + "manifest.json"
    state["objects"].append(key)
    private_json(args.state, state)
    storage.put(key, manifest_raw)
    state.update(manifest_sha256=hashlib.sha256(manifest_raw).hexdigest(), expires_unix=expires,
                 urls={"manifest": storage.sign(key, 3500)}, files=[{k: v for k, v in f.items() if k != "chunks"} for f in files])
    source = (Path(__file__).resolve().parents[1] / "deploy/worker/private_transfer.py").read_text()
    handoff = {"format": "noetharaclipz-private-transfer-handoff-v1", "python": source,
               "python_sha256": hashlib.sha256(source.encode()).hexdigest(),
               "manifest_url": state["urls"]["manifest"], "manifest_sha256": state["manifest_sha256"]}
    handoff_raw = json.dumps(handoff, separators=(",", ":")).encode()
    key = prefix + "handoff.json"
    state["objects"].append(key)
    private_json(args.state, state)
    storage.put(key, handoff_raw)
    state["handoff_sha256"] = hashlib.sha256(handoff_raw).hexdigest()
    state["urls"]["handoff"] = storage.sign(key, 3400)
    private_json(args.state, state)
    print(json.dumps({"staged": True, "objects": len(state["objects"]), "expires_unix": expires,
                      "manifest_sha256": state["manifest_sha256"], "image_id": IMAGE_ID}))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(json.dumps({"failed": True, "error_type": type(exc).__name__,
                          "http_status": exc.code if isinstance(exc, urllib.error.HTTPError) else None}), file=sys.stderr)
        raise SystemExit(1) from None
