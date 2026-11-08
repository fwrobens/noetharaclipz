# Isolated EC2 worker preparation — no remote deployment

**Latest host review:** region **us-east-2** is now operator-confirmed. Prior
operator readings were ~14 GiB available RAM, 53 GB free disk, low CPU and ~1,300
credits. Fresh capacity/network/credit readings are still required. See the
[Ohio review commands and exact gated QA procedure](ec2-qa-host-review.md).
No CLI/credential installation or EC2 action was attempted. 2.2B is excluded
from this deployment; the research section below is historical evidence only.

Target supplied by the user: **i-0be10e530045fc650**, `t2.xlarge`, 4 vCPU,
16 GiB installed RAM, approximately 53 GB free disk. These are **operator-supplied
facts, not a live capacity measurement**. Existing Noethara/Supabase containers
were not inspected or modified remotely. No EC2 instance, volume, credit mode,
security group, subscription or paid service was created/changed.

This session has no AWS connector, the identity manifest has no connections,
the AWS profile is `__oai_no_aws_identity__`, and both configured AWS files are
empty. Consequently **existing AWS suitability is unverified**: free RAM,
workloads, security groups, credit balance/mode are unknown. Region is now confirmed as us-east-2.
The current review uses operator-run read-only commands rather than installing
or changing credentials; no credentials need to
be pasted or recreated. The prior hosted website pass remains valid, but no
queue consumer was started for this deployment task.

## Recommendation and budget

Use the **existing instance with SmolVLM2-500M**, conditionally, for an isolated
QA trial **only after** capacity/credit/network review and explicit deployment
authorization. It has enough nominal total RAM, but that does not establish
spare capacity. Do not resize or buy a replacement on the evidence available.
The 2.2B model is research-only and is not in the worker/database allowlist.

| Resource | Prepared limit / admission requirement |
| --- | --- |
| CPU | 2 vCPU hard ceiling, low relative CPU shares; one active worker/job |
| Memory | 8 GiB hard ceiling, swap disabled; model startup still requires 6 GiB available |
| Shared host | At least 10 GiB current MemAvailable: 8 GiB worker ceiling plus 2 GiB host headroom; peak/history review must also show other services fit |
| Storage | At least 20 GiB verified free on the existing filesystem for image/rollback, pinned 500M+Whisper assets, private cache/temp/logs; use 30 GiB for both-model research assets/build staging |
| Disk usage | Image about 2.17 GB; production model/ASR assets about 2.5 GB. Two-model research additionally downloads about 9 GB of F32 2.2B weights |
| GPU | None; x86-64 CPU image only |

Use a filesystem quota or separate **already available** capacity if the host
supports it. Compose does not impose a byte quota on ordinary bind mounts.
Do not provision another volume or change another application's disk settings.
Stop QA if free disk approaches the agreed reserve or another service degrades.

Official [T2 pricing](https://aws.amazon.com/ec2/instance-types/t2/) reviewed in
this task lists `t2.xlarge` at **$0.1856/hour**, **$135.49/month at 730 hours**
for the standard Linux On-Demand illustration, and **54 CPU credits/hour**.
Confirm the actual region, OS, discounts and current bill; this is not an
account-specific quote. Existing EC2/EBS/IP charges continue independently.

T2's earned baseline is **0.9 vCPU across the entire instance**, not 2 free
cores for this worker. A busy 2-vCPU worker can drain Standard-mode credits and
be throttled. In Unlimited mode, AWS lists Linux T2 surplus credits at
**$0.05/vCPU-hour** ([official pricing](https://aws.amazon.com/ec2/pricing/on-demand/)).
Illustrative continuous incremental credit cost is **$40.15/month** if no other
workloads use the baseline, and up to **$73/month for the worker's 2 vCPUs** if
existing workloads already consume it. Actual duty cycle, balance and existing
loads change this substantially. Never switch credit mode automatically.

Incremental infrastructure allocation can be **$0/month** if genuinely spare
existing capacity is used without new disks/services, chargeable surplus
credits or additional billed data transfer. **Total incremental cost cannot
currently be confirmed as zero.** No NAT gateway, load balancer, ECR registry,
CloudWatch agent/log subscription or instance resize is proposed or enabled.
No upgrade is recommended before real host measurements; a future change needs
a region-specific monthly quote and separate approval first.

## Reproducible offline gaming comparison

The benchmark uses actual licensed **SuperTuxKart** gameplay, original seconds
20–50, four measured candidate windows and four frames each. Both variants use
the same footage, instructions, audio/scene evidence and one fresh model process
at a time. Real Whisper found no microphone speech; measured audio and 19 scene
boundaries remain in the report. The original is credited to SuperTux Kart-Autoren,
CC BY-SA 4.0; [source and license](https://commons.wikimedia.org/wiki/File:Benchmark_SuperTux_Kart_Base_Profile_2025.07.04_-_10.19.10.02.webm).
Use only that derivative or other footage for which testing is authorized.

The local Docker runner enforces **8 GiB RAM, no swap, 2 CPUs, no network, no
ports, no credentials and no Supabase access**. This benchmark runs on the
managed development executor, **not the EC2 instance**. Its AMD EPYC CPU differs
from T2 hardware; timings are not an EC2 performance promise.

| Variant | Actual result | Model load + inference | Peak RSS | CPU time |
| --- | --- | --- | --- | --- |
| 500M, production float32 | Completed; chose original 35.033–45.033 s | 54.784 s total; 4.165 s load; 39.665 s comparison | 2.85 GiB | 103.090 s, 188.18% of one core |
| 2.2B, experimental BF16 | Safety-aborted during loading at 11.045 s; no OOM kill | Inference speed unavailable | 7.37 GiB at cutoff | 14.048 s during attempted loading |

Preparation of real video/audio/scenes/Whisper and candidate files took 21.277 s
separately and is reused for a fair model comparison. The 2.2B checkpoint's
2,246,784,880 F32 parameters occupy **8.37 GiB in weights alone**, so float32 is
inadmissible under 8 GiB. BF16 was genuinely attempted; the 7.25 GiB RSS safety
threshold was crossed between 200 ms samples before loading completed. The hard
8 GiB cgroup remained in force; exit 75, `OOMKilled=false`. This does not prove
an optimized loader could never fit BF16, but it does reject this loading path
for a reliable shared-host deployment. **No 2.2B highlight-quality or inference
speed claim is possible.** No memory limit was raised to force a pass.

The 500M selection overlaps 9.967 s of a coarse, independently reviewed racing/
boost interval (25–45 s). Its hypothesis describes a vehicle on a dirt road;
this is more plausible than earlier hallucinations, but remains a model
observation rather than verified event truth. One game excerpt cannot establish
accuracy, comedy/streamer-reaction quality or recall. The result contains one
selection, so it does not establish multi-highlight duplicate suppression.
The earlier [broader 500M evaluation](local-worker-integration.md) and warnings
about hallucinations and sampled coverage remain applicable.

Use the recorded [raw deployment evidence](evidence/worker-deployment.json) and
model-specific JSON reports for actual results; do not treat absent 2.2B
timestamps/quality as a successful inference. The production model and Supabase
provenance remain pinned to 500M; switching to 2.2B would require additional
validation and a separately authorized database/provider change.

## Read-only host review — before any deployment

With an already authenticated AWS CLI, use the confirmed Ohio region:

```sh
python scripts/aws_worker_inventory.py --region us-east-2 --instance-id i-0be10e530045fc650 --output test-results/aws-worker-inventory.json
```

The explicit allowlist only calls STS identity, EC2 Describe operations and
existing CloudWatch metric reads. No Cost Explorer/Logs Insights, SSM
SendCommand, guest agent installation or resource mutation. It inspects existing
volume encryption, security groups, metadata options, status and seven days of
CPU/credit metrics. Missing guest metrics do not imply free RAM/disk.
Inventory output contains private network metadata; keep it ignored and 0600.

An authorized operator can run `python3 deploy/worker/host_probe.py` on that
instance, capturing its JSON securely. This probe only reads host memory/load/
disk, process resource usage without arguments, listening ports, Docker names/
stats/resource limits, cgroup version and boot settings. It never reads
container environments or credentials, executes inside existing containers,
installs software or changes services. Review peak usage, not just a snapshot.

```sh
python deploy/worker/verify_host_plan.py /secure/path/to/host-report.json
```

Even passing snapshot checks does **not** authorize deployment. Review CPU
credits, existing peak RAM/CPU, storage reserve, UID collision (`62001`), network
CIDRs and all existing application limits first. If existing workloads cannot
leave the required headroom, do not start the worker. Request a quote/approval
for an alternative only after measurements establish the need.

## Container preparation — local only

`deploy/worker/Dockerfile` pins the Python base by digest and CPU package
versions in `requirements.lock`, including Torch 2.9.0+cpu/Torchvision 0.24.0+cpu.
No application `.env`, browser credentials, footage or workspace cache enters
the Docker build context. Models/Whisper are separate pinned, immutable runtime
assets; the worker uses offline model loading. Build with normal system trust;
in this managed executor use the public CA as a BuildKit secret:

```sh
docker build --secret id=proxy_ca,src=/etc/ssl/certs/ca-certificates.crt -f deploy/worker/Dockerfile -t noetharaclipz-worker:review .
docker compose --env-file deploy/worker/config.example.env -f deploy/worker/compose.yaml config --quiet
python scripts/test_worker_container.py
```

The smoke test uses only a new local `nc-standby-check-*` container without
network/secret. It checks enforced limits/non-root/read-only/no ports, actual
automatic restart after an application-process crash, graceful stop, and denied
QA/global startup with missing opt-ins. Docker intentionally suppresses restart
for a manual `docker kill`, so the test crashes only its own standby supervisor
child. No existing container is killed/restarted/removed.

Final local verification passed **74 worker tests**, zero skipped with authorized
Sintel footage, including 14 deployment guards; Ruff, Compose validation, the
image build/`pip check`, and the final standby Docker lifecycle/isolation smoke
test passed. EC2 lifecycle/QA processing are deliberately not counted as passes.

A transferable local image archive was prepared under
`test-results/noetharaclipz-worker-review.tar.gz` (about 728 MiB). Its exact size,
SHA256 and tested image ID are in the deployment evidence. It contains no model
weights, footage or credentials and has not been uploaded to AWS/a registry.
Source-controlled Docker configuration is the reproducible delivery; promote
only a reviewed artifact after authorization.

The earlier research comparison used the command below. **Do not rerun it or
download/activate 2.2B for the current deployment.** This is reproduction history:

```sh
python scripts/benchmark_worker_container.py --sample /path/to/authorized/supertuxkart-sample.mp4 --hf-cache /path/to/huggingface --output test-results/worker-container-benchmark
```

The 2.2B research revision is `482adb537c021c86670beed01cd58990d01e72e4`.
Download it separately with Hugging Face before running; the benchmark itself
has `network=none`. Large-model weights are not copied into the production image
or enabled as a provider. Do not supply a Supabase key to the benchmark.

## Deployment procedure — requires separate authorization

These are **review instructions, not actions performed on EC2**:

1. Capture/review the read-only inventory and host report; identify region and
   current credit mode/cost. Get explicit approval for the isolated QA trial.
   Keep the existing upload unchanged and global processing disabled.
2. Build/test off-host, record commit/image ID and archive SHA256, then transfer
   only that artifact. Do not build on or restart a busy shared EC2 host.
   Do not attach to existing Compose projects/networks or reuse their volumes.
3. After verifying UID/GID 62001 is unused, create only dedicated
   `/var/lib/noetharaclipz-isolated/{models,cache,tmp}` directories owned by that
   identity, mode 0700, with the agreed disk budget. Prepare a separate
   `/etc/noetharaclipz-isolated/supabase-key` file, root-owned and group-readable
   only by gid 62001, mode 0440. Use the existing secure secret channel; never
   shell arguments, Git, image build args or Compose environment for the key.
4. Load the reviewed image. Run only the `seed` tools-profile service to download
   pinned 500M/Whisper assets, with no Supabase secret. Runtime mounts these
   read-only. Verify `models/manifest.json`; restrict the asset path to this
   worker. The seed command performs no inference or queue calls.
5. Review dedicated Docker bridge CIDR against VPC/other Docker networks. The
   worker publishes **no ports**, has no Docker socket/AWS credentials and joins
   no Noethara/Supabase network. Outbound Supabase HTTPS/DNS is needed. Compose
   alone does not enforce destination egress filtering: an administrator must
   review a per-worker policy denying host/private-service and IMDS access
   without changing existing services' rules. Do not claim this policy exists.
   Do not change security groups, metadata options or daemon config automatically.
6. Start only project `noetharaclipz-isolated` in default **standby**. It loads no
   credentials, makes no backend calls and reports `ai_ready=false`. Do not run
   global Docker cleanup or restart/upgrade the shared Docker daemon. Existing
   Docker must already be configured to start at boot; if it is not, pause for
   separate review rather than changing other services' startup behavior.
7. Create an isolated confirmed QA account through the approved API test flow.
   Set `NC_DEPLOY_MODE=qa` and its explicit `NC_WORKER_OWNER_ID` in a dedicated
   private Compose config. Change only this worker service after approval. The
   checked-in config hardcodes `NC_GLOBAL_QUEUE_APPROVED=false`; an empty owner
   in QA mode refuses to start. Do not use a real user's owner ID.
8. Perform normal website upload/instructions/Generate → actual scoped claim →
   genuine automatic highlight → edit/save/refresh → **normal Export** → queued
   render → authenticated private download and decode. Reuse the assertions in
   `scripts/acceptance.py`; configure its QA credentials securely. The existing
   `accept_local_queue.py` starts a **local** worker, so do not use it as evidence
   that the EC2 service performed the claim. Record the container-scoped
   heartbeat/model, job timestamps, render provenance and resource samples.
9. While processing only QA work, verify graceful SIGTERM and real >120-second
   lease recovery after a separately approved crash/restart test; reject stale
   tokens, test cancellation/retry/attempt limits and private/cross-user denial.
   Reboot testing on a shared host is not authorized; inspect boot configuration
   and use a worker-only process crash instead. Monitor existing applications,
   Docker stats, memavailable, disk, CPU credits and readiness throughout.
10. Stop only this QA worker if another service regresses, OOM/credits/disk
    limits are approached or health fails. Remove only its completed QA
    account/projects/objects after checking no jobs remain in flight. Record
    the original queued job's whole-row hash before/after.
11. General-user/global processing remains a **separate authorization gate**.
    Never infer it from a successful QA benchmark. The supervisor's global mode
    additionally requires explicit `NC_GLOBAL_QUEUE_APPROVED=true` and no owner;
    the reviewed default Compose file cannot enable that flag by environment.

## Reliability and monitoring

The image runs as non-root uid/gid 62001 with read-only root, dropped
capabilities, no new privileges, 256 PIDs, 8 GiB/no swap and 2 CPU limits.
Review compatibility with Docker Engine 24+ and Compose v2.24+ before deployment;
do not upgrade the existing daemon as part of this task.
Docker `unless-stopped` provides startup/restart for this container, assuming the
existing daemon's boot service is already enabled. Private bind paths and rotated
Docker JSON logs (5×10 MB) persist across container recreation; no new paid log
service is used. Docker administrators remain privileged over file secrets.

The supervisor defaults to standby. Active mode calls the **normal worker** as
a child, monitors the local health file and terminates/restarts on stale DB
heartbeat, provider unready state after 240 seconds, or >1300-second main-loop
stall. The local health probe never calls Supabase or loads another model;
standby health means supervisor alive, **not AI ready**. Docker health status
alone does not restart a container; the supervisor exits nonzero so the restart
policy can act. DB heartbeat completion is required before a fresh probe is
written. Secrets, account IDs and media content are absent from the probe.

SIGTERM is forwarded; the normal worker stops processing, clears selected
readiness and leaves interrupted leases to expire for recovery. A 90-second
child grace fits the 100-second Compose stop grace; a stuck child is killed
after that bound. Existing leases/heartbeats, cancellation, attempt limits and
atomic completion remain in Supabase. One process and the existing database
advisory lock enforce one active job globally.

Only dedicated local `noetharaclipz-*` temp directories older than 24 h are
removed at active startup/hourly. Active jobs have a 20-minute limit. Symlinks
and unrelated names are excluded. The normal private media cache retains its
existing 24 h/1 GiB pruning behavior. There is no global cleanup in QA mode.
Validate resource headroom and network policy on the real host before calling
this configuration deployed or production-verified.
