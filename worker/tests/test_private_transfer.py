"""Transfer integrity/security boundaries, without network, credentials or Docker."""

import hashlib
import io
import json
import sys
import tarfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "deploy/worker"))
sys.path.insert(0, str(ROOT / "scripts"))
from private_transfer import HOST, checked_url, decode_chunk, extract_config, download  # noqa: E402
from stage_worker_transfer import encode_chunk  # noqa: E402
from verify_worker_transfer import verify_image, verified_runtime_ids  # noqa: E402

PREFIX = "_worker-transfer/11111111-1111-4111-8111-111111111111/"


@pytest.mark.parametrize("url", [
    "http://" + HOST + "/storage/v1/object/sign/processing-artifacts/" + PREFIX + "x",
    "https://evil.example/storage/v1/object/sign/processing-artifacts/" + PREFIX + "x",
    "https://" + HOST + ".evil.example/storage/v1/object/sign/processing-artifacts/" + PREFIX + "x",
    "https://" + HOST + "/storage/v1/object/sign/source-videos/" + PREFIX + "x",
    "https://" + HOST + "/storage/v1/object/sign/processing-artifacts/" + PREFIX + "%2e%2e/x",
])
def test_rejects_capability_exfiltration_or_other_object_scope(url):
    with pytest.raises(ValueError):
        checked_url(url, PREFIX)


def test_corrupt_or_reordered_chunks_cannot_produce_an_accepted_archive():
    raw = b"actual archive bytes\x00\xff"
    expected = {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
    encoded = encode_chunk(raw, 3)
    assert decode_chunk(encoded, expected, 3) == raw
    with pytest.raises(ValueError):
        decode_chunk(encoded, expected, 2)
    part = json.loads(encoded)
    part["data"] = part["data"][:-1] + ("A" if part["data"][-1] != "A" else "B")
    with pytest.raises(ValueError):
        decode_chunk(json.dumps(part), expected, 3)


@pytest.mark.parametrize("name,kind", [("../escape", None), ("/tmp/escape", None), ("config/link", tarfile.SYMTYPE)])
def test_config_archive_cannot_escape_or_follow_links(tmp_path, name, kind):
    path = tmp_path / "config.tar.gz"
    with tarfile.open(path, "w:gz") as archive:
        member = tarfile.TarInfo(name)
        if kind:
            member.type = kind
            member.linkname = "/etc/passwd"
        archive.addfile(member)
    with pytest.raises(ValueError):
        extract_config(path, tmp_path / "output")
    assert not (tmp_path / "output").exists()


def test_manifest_digest_must_match_before_any_directory_or_file_write(monkeypatch, tmp_path):
    import private_transfer
    monkeypatch.setattr(private_transfer, "get_bytes", lambda *args: b'{"untrusted":true}')
    with pytest.raises(ValueError, match="Manifest digest"):
        download("https://" + HOST + "/storage/v1/object/sign/processing-artifacts/" + PREFIX + "manifest.json",
                 "0" * 64, tmp_path / "output")
    assert not (tmp_path / "output").exists()


def test_docker_archive_rejects_content_addressed_blob_tampering(tmp_path):
    path = tmp_path / "image.tar.gz"
    with tarfile.open(path, "w:gz") as archive:
        member = tarfile.TarInfo("blobs/sha256/" + "a" * 64)
        member.size = 3
        archive.addfile(member, io.BytesIO(b"bad"))
    with pytest.raises(ValueError, match="blob digest"):
        verify_image(path, "sha256:" + "b" * 64)


def identity_fixture(config_id="sha256:" + "b" * 64, layer_id="sha256:" + "c" * 64):
    config = b'{"reviewed":true}'
    manifest = json.dumps({"schemaVersion": 2,
        "mediaType": "application/vnd.oci.image.manifest.v1+json",
        "config": {"digest": config_id, "size": len(config)},
        "layers": [{"digest": layer_id}]}, separators=(",", ":")).encode()
    manifest_id = "sha256:" + hashlib.sha256(manifest).hexdigest()
    entry = {"Config": "blobs/sha256/" + "b" * 64,
             "Layers": ["blobs/sha256/" + "c" * 64]}
    small = {entry["Config"]: config, "blobs/sha256/" + manifest_id[7:]: manifest,
             "index.json": json.dumps({"schemaVersion": 2, "manifests": [{
                 "mediaType": "application/vnd.oci.image.manifest.v1+json",
                 "digest": manifest_id, "size": len(manifest)}]}).encode()}
    return small, entry, manifest_id


def test_classic_and_containerd_runtime_ids_must_bind_to_the_same_config_and_layers():
    small, entry, manifest_id = identity_fixture()
    assert verified_runtime_ids(small, entry, "sha256:" + "b" * 64) == {
        "sha256:" + "b" * 64, manifest_id}


@pytest.mark.parametrize("kwargs", [{"config_id": "sha256:" + "a" * 64},
                                   {"layer_id": "sha256:" + "a" * 64}])
def test_unrelated_config_or_layers_cannot_pass_a_runtime_manifest_guard(kwargs):
    small, entry, _ = identity_fixture(**kwargs)
    with pytest.raises(ValueError, match="does not reference reviewed"):
        verified_runtime_ids(small, entry, "sha256:" + "b" * 64)


def test_tampered_manifest_cannot_be_accepted_under_a_previously_verified_runtime_id():
    small, entry, manifest_id = identity_fixture()
    small["blobs/sha256/" + manifest_id[7:]] += b" "
    with pytest.raises(ValueError, match="digest/size"):
        verified_runtime_ids(small, entry, "sha256:" + "b" * 64)
