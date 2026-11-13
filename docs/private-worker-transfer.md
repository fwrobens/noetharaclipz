# Private worker transfer through the existing SSM terminal

The GitHub repository API works, but the same managed GitHub credential is not
accepted by `uploads.github.com` (HTTP 401). There is no alternate local GitHub
login or raw token to repair. No PAT was created and upload attempts have stopped.
The temporary empty draft release was deleted. Billing usage is inaccessible
(HTTP 403); no Actions workflow or registry usage has been activated.

## Existing private-storage route

Use the existing private `processing-artifacts` bucket without changing its
45,000,000-byte limit, MIME restrictions, RLS or visibility. Transfer pieces are
valid `application/json`, with at most 4 MiB of base85-encoded binary per object
(about 5.25 MB of JSON). This does not upload a mislabeled video or an oversized
object. Store them only beneath a random `_worker-transfer/<UUID>/` prefix.
That first folder is not any authenticated user's UUID; existing owner-folder
policies do not grant ordinary users access. Service credentials remain only in
the current managed environment, never on EC2 or in the handoff.

Each object is accessed through a scoped, expiring signed URL. A signed manifest
contains the chunk URLs and hashes. Its SHA256 is provided independently, and
the downloader verifies that digest, destination host/prefix, sequence, each
decoded chunk and both complete files before accepting anything. Signed URLs
are temporary read capabilities, not public bucket/object settings. They must
not be committed to Git, logged in the PR, or used after their expiry.

`scripts/stage_worker_transfer.py` checks all current object sizes and database
reservations before uploading. It preserves 100 MB below the application's
existing 800 MB safety cap. No bucket/schema/policy/queue change is made. This
uses existing Supabase storage and transfer allowances; it does not establish
the account's monthly bill or promise zero metered data usage.

## Artifact identity

The original gzip archive is 762,913,897 bytes, SHA256
`29afebf52f7e4edca43282405941f9b636611ad8bb36cb1126f7ef1275ce41b9`.
Recompression yields a **441,120,356-byte xz archive**, SHA256
`d4039e807525aab63820b947e6ee99944cf221776a85fb08c1390bfd605e6394`.
Both decompress to the exact same tar stream, SHA256
`a22386493543719fdcfbf0e5901b42b888191e04bbdcfb2cfceba5e56d2519e1`.
No image was rebuilt or modified.

The immutable image **config digest** (and local classic-store image ID) remains:
`sha256:32fd88495ceab2c59ab7bc6a0c7980c1003d9b4b6eea507131783a24be4b88a5`.
The offline verifier streams and hashes every content-addressed blob and checks
the config/rootfs correspondence, linux/amd64 architecture, UID/GID 62001,
absence of exposed ports and local/standby/Gemini-disabled defaults.
The b51ffb5 runtime recipe, frozen dependencies and runtime source are unchanged.
The same archive also contains OCI manifest digest
`sha256:472913bf34e918c48e5b77a56c4ea2dfd31873bdd79ecc2d1c4e7ab4cf3e5759`,
which references that exact config and the same 11 verified layer digests.
The EC2 daemon reports this manifest digest as `.Id`; use it as the pinned
`NC_WORKER_IMAGE` on this host. The local daemon reports the config digest.
Neither identifier represents a rebuilt image; no registry image was created. The model remains pinned SmolVLM2-500M; no weights are included
in this archive and no 2.2B assets are downloaded.

## Operator sequence

1. Use the scoped signed manifest and independently supplied SHA256 in the
   one-block SSM handoff. The stdlib downloader in
   `deploy/worker/private_transfer.py` needs no AWS/GitHub/Supabase login. It
   downloads only the image and reviewed configuration into a new directory,
   verifies both hashes and safely extracts the configuration. It never invokes
   Docker or starts a worker.
2. Return the verification output. Until that happens, EC2 receipt is **not
   verified**, even if private staging and a cloud-side download passed.
3. Recheck reserved resources including stopped Compose containers. Load only
   the verified archive, then compare Docker's reported identity with the verified
   config/OCI mapping above:

   ```sh
   sudo -n docker load --input worker-image.tar.xz
   sudo -n docker image inspect noetharaclipz-worker:review --format '{{.Id}}'
   ```

   An ID outside the verified config/OCI mapping stops the procedure. These commands load bytes; they do not run
   an image or process a job. No credential or Docker login is needed.
4. Continue [the approved conditional QA procedure](ec2-qa-host-review.md).
   Actual seed/standby kernel quota proof and scoped network allow/deny tests
   must pass before model seeding/AI activation. Keep 8 GiB/2 vCPU, one QA owner,
   no public ports, no global consumer, Gemini off and the 30-minute trial limit.
   Do not change existing Noethara/Supabase services or the protected upload.
5. After verified EC2 receipt, remove **only** this transport prefix using the
   private local state file, before creating the QA account/footage jobs:

   ```sh
   python scripts/stage_worker_transfer.py --state <private-state-file> --cleanup
   ```

   This returns temporary storage headroom and revokes the object links. If
   the handoff expires or is abandoned, delete its own prefix too. Never delete
   other application objects, reset jobs or use global cleanup commands.

Private GHCR/Actions remains a fallback only. It must not be dispatched without
checking included Actions minutes/artifact allowance or obtaining any needed
spending approval. An ordinary runner GITHUB_TOKEN must stay inside its job;
it is not a durable EC2 registry credential. Do not introduce PATs or make the
repository, package or transfer publicly readable to resolve authentication.
