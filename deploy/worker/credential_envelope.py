"""RSA-OAEP/SHA256 transport of an existing credential; never print plaintext.

Only ciphertext and a public-key fingerprint enter the private storage handoff.
The label binds the credential to the project, host, reviewed image and QA owner.
"""

import base64
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path
from uuid import UUID

PROJECT = "zxdnjnsghdnviflahvry"
INSTANCE = "i-0be10e530045fc650"
IMAGE = "sha256:472913bf34e918c48e5b77a56c4ea2dfd31873bdd79ecc2d1c4e7ab4cf3e5759"


def context(owner, trial):
    return ("NoetharaClipz/qa-key/v1/" + PROJECT + "/" + INSTANCE + "/" + IMAGE
            + "/" + str(UUID(owner)) + "/" + str(UUID(trial))).encode()


def openssl(args, value=None):
    result = subprocess.run(["openssl", *args], input=value, capture_output=True, timeout=30)
    if result.returncode:
        raise ValueError("Credential-envelope cryptographic operation failed; no plaintext logged")
    return result.stdout


def seal(public_pem, credential, owner, trial):
    if not 0 < len(credential) <= 446:
        raise ValueError("Credential does not fit the verified RSA4096 OAEP envelope")
    with tempfile.TemporaryDirectory(prefix="nccz-envelope-") as directory:
        public = Path(directory) / "public.pem"
        public.write_bytes(public_pem)
        description = openssl(["pkey", "-pubin", "-in", str(public), "-text", "-noout"])
        if b"(4096 bit)" not in description:
            raise ValueError("Expected the host's RSA-4096 public transport key")
        der = openssl(["pkey", "-pubin", "-in", str(public), "-outform", "DER"])
        encrypted = openssl(["pkeyutl", "-encrypt", "-pubin", "-inkey", str(public),
            "-pkeyopt", "rsa_padding_mode:oaep", "-pkeyopt", "rsa_oaep_md:sha256",
            "-pkeyopt", "rsa_mgf1_md:sha256", "-pkeyopt", "rsa_oaep_label:" + context(owner, trial).hex()], credential)
    if len(encrypted) != 512:
        raise ValueError("Unexpected RSA ciphertext size")
    return {"scheme": "RSA4096-OAEP-SHA256", "owner_id": str(UUID(owner)), "trial_id": str(UUID(trial)),
            "public_der_sha256": hashlib.sha256(der).hexdigest(),
            "ciphertext_b64": base64.b64encode(encrypted).decode()}


def unseal(envelope, private):
    if envelope.get("scheme") != "RSA4096-OAEP-SHA256":
        raise ValueError("Unsupported encrypted credential scheme")
    private = Path(private)
    info = private.lstat()
    if private.is_symlink() or not private.is_file() or info.st_uid != 0 or info.st_mode & 0o077:
        raise ValueError("Transport private key must be root-only on the target host")
    der = openssl(["pkey", "-in", str(private), "-pubout", "-outform", "DER"])
    if hashlib.sha256(der).hexdigest() != envelope["public_der_sha256"]:
        raise ValueError("Encrypted credential targets a different host key")
    encrypted = base64.b64decode(envelope["ciphertext_b64"], validate=True)
    if len(encrypted) != 512:
        raise ValueError("Invalid encrypted credential length")
    return openssl(["pkeyutl", "-decrypt", "-inkey", str(private),
        "-pkeyopt", "rsa_padding_mode:oaep", "-pkeyopt", "rsa_oaep_md:sha256",
        "-pkeyopt", "rsa_mgf1_md:sha256", "-pkeyopt",
        "rsa_oaep_label:" + context(envelope["owner_id"], envelope["trial_id"]).hex()], encrypted)


def server_headers(credential):
    key = credential.decode().strip()
    if key.startswith("sb_secret_") and len(key) > 20 and not any(c.isspace() for c in key):
        return {"apikey": key}
    if key.startswith("eyJ"):
        part = key.split(".")[1]
        claims = json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))
        if claims.get("role") == "service_role" and claims.get("ref") == PROJECT:
            return {"apikey": key, "Authorization": "Bearer " + key}
    raise ValueError("Decrypted credential is not the expected project server credential")
