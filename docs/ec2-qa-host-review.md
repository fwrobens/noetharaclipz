# Ohio host review and exact gated QA procedure

Target: **i-0be10e530045fc650**, **us-east-2**, **m6i.2xlarge, 8 vCPU / approximately 32 GiB**.
Instance ID was confirmed by the operator's DMI board tag; type was read through
IMDSv2, and `nproc` reports 8. Earlier T2 specifications are superseded.
Runtime artifact: the tested **b51ffb5 preparation**, pinned SmolVLM2-500M only.
Do not install/activate the 2.2B research model or rerun the research comparison.
No EC2 deployment, worker start, AWS credential installation/change, or existing
service mutation has been performed in this review.

## Current decision

The operator's new read-only output confirms about **29 GiB available RAM**,
**53 GB free ext4 disk**, low load (0.06 / 0.04 / 0.00), and six existing
Noethara-staging/Supabase containers using about **395 MiB** combined with very
low snapshot CPU. Staging shows a 1 GiB limit; Supabase limits shown by stats are
host-sized, so explicit per-service caps are not confirmed. Do not change them.
Existing published container bindings shown are loopback-only.

**Resource and reported software compatibility review pass for a bounded,
staged 500M QA trial. The user has now approved that bounded trial.** This session still has no
AWS connector/identity or CLI; the readings are operator-supplied, not direct
remote observations by this agent. No tools/credentials were installed/changed.

**M6i is not burstable. CPU credits, Standard/Unlimited mode and the old T2
surcharge/throttling estimates do not apply.** Do not request or change a credit
mode. The earlier ~1,300-credit claim is not a current measurement for this
confirmed instance type and is no longer an admission requirement.

Observed Docker networks are `172.17.0.0/16` (default), `172.18.0.0/16`
(staging), and `172.19.0.0/16` (Supabase). Host routes show `172.31.32.0/20`
and a default gateway at `172.31.32.1`. The upstream resolver is confirmed as
**172.31.0.2**, rather than the systemd stub `127.0.0.53`. INPUT policy is ACCEPT;
FORWARD is DROP with jumps to DOCKER-USER and DOCKER-FORWARD. DOCKER-USER is empty.

The operator reports attached group **launch-wizard-3 / sg-0e74e0664079302bd**
with IPv4 SSH/22 open to `0.0.0.0/0` and unrestricted IPv4 outbound traffic.
This is existing exposure, not a new worker port. **Do not change that group or
SSH access as part of QA**; narrowing SSH requires a separately reviewed access
change to avoid locking out the operator. No public worker ports are needed.

The proposed worker-only policy below is now concrete and syntax-tested.
It has not been installed, and its real DNS/TLS/deny behavior on EC2 is not yet
verified. Operator Docker 29.1.3 / cgroup v2 and Compose 2.40.3 satisfy the
version requirements; reported security options are AppArmor, default seccomp
and cgroup namespaces, with no warnings. This is not actual per-container
quota proof. Dedicated UID/path/bridge/chain collision checks must run read-only
before changes and abort the approved procedure if any ownership conflicts exist. No worker
network or firewall rule has been created/changed.

The Docker resource envelope is locally tested. It limits this worker to
8 GiB RAM, 2 vCPU, no swap, low CPU shares, one active job, 256 PIDs and no public
ports, with non-root/read-only execution and private paths/secrets. It cannot
guarantee zero shared-host impact: filesystem I/O, cache pressure and peak workloads remain shared. Docker bridge separation alone does not block
access to host services, other routed private networks or IMDS. That policy must
be inspected/reviewed before startup, without weakening existing rules.

## Minimal read-only host commands — safe to run now

Run on the existing instance through the operator's existing login. These read
state only; they do not start/restart/install anything or inspect secret values.
If permissions are missing, report that result rather than changing permissions.

```sh
date -u
free -h
uptime
df -hT / /var/lib
docker ps --format '{{.Names}} {{.Status}} {{.Ports}}'
docker stats --no-stream --format '{{.Name}} CPU={{.CPUPerc}} RAM={{.MemUsage}} LIMIT={{.MemPerc}} IO={{.BlockIO}}'
docker ps -q | xargs -r docker inspect --format '{{.Name}} memory={{.HostConfig.Memory}} swap={{.HostConfig.MemorySwap}} cpu={{.HostConfig.NanoCpus}} quota={{.HostConfig.CpuQuota}} pids={{.HostConfig.PidsLimit}}'
docker network ls -q | xargs -r docker network inspect --format '{{.Name}} {{json .IPAM.Config}}'
ss -lntuH
ip route show
```

For a single structured report, if the reviewed files are already available on
the host, `python3 deploy/worker/host_probe.py` consolidates those reads and adds
timestamp, cgroup/daemon/Compose versions, boot status, UID/GID 62001 collision
checks, proposed-path existence, DNS and bridge CIDRs. Do not treat this cloud
executor's `/proc` or Docker stats as EC2 readings. Repeat the short sample
during representative staging/Supabase activity; use existing history too.
No host stress test is requested.

For the security review, an administrator with existing read permissions can
also run the applicable reads below. `sudo -n` never prompts or changes policy;
if denied or a command/chain is absent, return that fact. Do not install a
firewall or add/flush rules during this read-only phase.

```sh
sudo -n iptables -S DOCKER-USER
sudo -n iptables -S INPUT
sudo -n nft list ruleset
```

Use the rules for the host's actual Docker/firewall backend. Review whether the
future private bridge `nccz-qa0` can be restricted to required DNS and public
HTTPS while denying host/private application and IMDS destinations. Check for
bridge/CIDR conflicts. Do not attach the worker to staging/Supabase networks or
change their ingress policies. Keep reports private; share no `.env`, full
`docker inspect`, credential files, IAM tokens or service secret values.

## AWS reads — existing authenticated CLI/CloudShell only

These may be run on the instance **only if** CLI and its existing role/access
are already present, or from an already authenticated operator terminal or
CloudShell. Do not run `aws configure`, install credentials, attach an IAM role
or grant permissions for this review. If unavailable, use the existing EC2 and
CloudWatch consoles to report the same values without enabling monitoring.

```sh
aws ec2 describe-instances --region us-east-2 --instance-ids i-0be10e530045fc650 --query 'Reservations[].Instances[].{Type:InstanceType,State:State.Name,SecurityGroups:SecurityGroups,MetadataOptions:MetadataOptions}' --output json
```

For security groups, use only the IDs returned by that exact instance query:

```sh
aws ec2 describe-security-groups --region us-east-2 --group-ids <returned-security-group-IDs> --query 'SecurityGroups[].{Id:GroupId,Ingress:IpPermissions,Egress:IpPermissionsEgress}' --output json
```

For the full existing seven-day CPU/volume/security review in one command,
use the prepared read-only inventory with the already authenticated CLI:

```sh
python3 scripts/aws_worker_inventory.py --region us-east-2 --instance-id i-0be10e530045fc650 --output /tmp/noetharaclipz-aws-review.json
```

The output is mode 0600; no credential configuration is changed. Review
CPUUtilization average/max, actual instance capabilities, EBS encryption and
metadata options. The inventory now skips credit APIs/metrics for confirmed
non-burstable types such as m6i; missing type information remains unverified.
No Cost Explorer, Logs Insights, agent installation or monitoring activation.
Do not infer zero cost or zero risk from missing metrics or access-denied output.

## Worker-only network proposal — not applied

`deploy/worker/egress_policy.py` **only prints** the proposed commands. It has
no subprocess/command execution path. Rendered shell also refuses execution
unless `NC_QA_FIREWALL_APPROVED=yes` is explicitly set; that accident guard is
not a substitute for actual user authorization. Inspect without applying it:

```sh
python3 deploy/worker/egress_policy.py --format shell
python3 deploy/worker/egress_policy.py --format shell --rollback
```

The future operator must check that `NCZQA_EGRESS` does not already belong to
another service and `nccz-qa0` is unused. Never flush/reuse a foreign chain.
After explicit authorization, construct the full new chain first and then add
only source-interface-specific hooks:

- `DOCKER-USER`: traffic **from `nccz-qa0` only** jumps to `NCZQA_EGRESS`.
- `INPUT`: traffic **from `nccz-qa0` only** is rejected, protecting host services.
- Egress chain first permits UDP/TCP DNS **only to 172.31.0.2:53**. This exception
  must precede the private-address block because the approved resolver is private.
- Reject RFC1918/private/shared/link-local/loopback/reserved ranges, including
  staging/Supabase networks, the VPC's other private services and IPv4 IMDS
  `169.254.169.254`. Also reject host-local destinations.
- Return established public traffic and TCP/443 to the existing Docker policy;
  this does not bypass any later host/Docker denies. Reject other egress.

No global ACCEPT/DROP policy is changed, no shared chain is flushed, and no
hook matches the existing staging/Supabase bridge interfaces. The renderer also
prints exact rollback commands that remove only these hooks/owned rules/chain,
**after stopping this worker and seed**. The user has approved only this
scoped policy, conditional on the collision and preflight gates below.

Compose pins worker/seed DNS to the approved resolver and disables IPv6 in their
own network namespaces, avoiding an IPv6 bypass of the IPv4-only policy. No
host sysctl or other container is changed. HTTPS is allowed to public IPv4
endpoints; this is not a hostname allowlist. Post-authorization QA must verify
DNS + Supabase HTTPS and denial of host/private/IMDS/other-port access using
this worker network, without probing or modifying unrelated application data.

Firewall persistence across reboot has not been configured. The **QA override
therefore uses `on-failure:3`**, which supports process-failure recovery but does
not automatically start a stopped container on Docker-daemon/host reboot. Re-review/reinstall the scoped policy
before any manual resumption. With Docker live-restore, a running container may
remain alive across a daemon restart; daemon/reboot changes are not authorized
during the trial, and any such event requires stopping QA and re-reviewing rules. The base standby service remains `unless-stopped`
and makes no queue calls. Future continuous/global startup needs separately
approved firewall persistence/startup ordering; it is not authorized by QA.

Reported compatibility checks passed (no installation/change). These commands
remain useful for a fresh preflight; operator results were Engine 29.1.3, cgroup
v2, AppArmor/seccomp/cgroupns, no warnings, Compose 2.40.3:

```sh
sudo -n docker info --format 'Server={{.ServerVersion}} Cgroup={{.CgroupVersion}} Security={{json .SecurityOptions}} Warnings={{json .Warnings}}'
sudo -n docker compose version
```

The prepared `host_probe.py` additionally records UID/GID 62001 and path/bridge
collisions. Check these before file/network creation, and stop rather than
reuse any reserved identity/path already owned by another application.

**Correction to earlier local enforcement claims:** the managed development
Docker daemon reports `Running in rootless-mode without cgroups`. Earlier smoke
checks inspected requested HostConfig values; they did not prove kernel quota
enforcement. The CPU/RSS and model-output measurements remain real, and the
2.2B exit was its own safety watchdog, but the claimed hard 8 GiB/2 CPU sandbox
is **unverified** for those historical runs. This finding is from the cloud
executor, not the EC2 host; do not infer that EC2 has the same limitation.

`check_cgroup_limits.py` now reads actual cgroup v1/v2 membership/controls, not
requested flags. It requires 8 GiB memory, 2 CPU quota, no extra swap and <=256
PIDs; unavailable, unlimited or outer-host limits fail closed. The smoke helper
now refuses success without this proof, and the optional benchmark runner
checks it before importing a model or doing media work. Do not rerun the 2.2B
research task. After authorization, EC2's seed and standby limits must pass this
read-only probe before asset work/AI processing as shown below.

Local validation: **25 targeted tests pass** (14 deployment guards, 2 AWS
contracts, 5 firewall tests and 4 kernel-quota verifier tests). Proposed rules
pass `iptables-translate` without kernel writes; shell text passes `sh -n`.
Compose rendering confirms DNS, per-container IPv6 disablement, bounded QA
restart, no ports, requested 8 GiB/2 CPU/no swap and disabled global/Gemini.
These are configuration/parser/control tests, **not an EC2 enforcement pass**.
No container/model/firewall/EC2 service was started or changed by this review.

## Admission and cost decision

Require fresh ≥10 GiB MemAvailable, ≥20 GiB free worker/Docker filesystem budget,
low sustained CPU with existing workloads reviewed, and no new OOM/resource
regression. Confirm Docker 24+/Compose v2.24+, daemon already boot-enabled,
UID/GID 62001 and dedicated paths/project/bridge are unused or explicitly owned
by this deployment. Confirm network/security policy and volume encryption.

For the first trial, use a **30-minute maximum QA window** and stop only this
worker if MemAvailable drops below 2 GiB, free disk falls below 10 GiB, it OOMs,
or another application regresses. These are proposed operator stop thresholds,
not automatically configured alarms. Continue monitoring actual existing peak
workloads and the worker's 8 GiB / 2 CPU limits. No CPU-credit threshold applies.

Reusing the already running m6i instance adds no extra EC2 instance allocation
or CPU-credit fee. Its existing hourly bill continues; the previous T2
$135.49/month and $40.15–$73 surplus estimates are superseded, not a quote for
m6i. Verify actual m6i/Ohio OS pricing and discounts in existing billing views
before quoting total ongoing cost. No resize or new infrastructure is proposed.

The repository records hosted Supabase in us-east-1 while EC2 is us-east-2.
Confirm that region/allowance: cross-region or public storage transfers and
Supabase egress/storage overages remain possible usage costs. Do not promise
zero incremental bill impact merely because the VM is already running. Do not
add EBS/NAT/ALB/ECR/log subscriptions or enable paid monitoring. No upgrade is
justified by the supplied resource readings.

## Exact deployment sequence — approved, conditional on preflight

The user approved this staged sequence on 2026-11-08 by answering “yes” to the
30-minute QA approval request. These are deployment actions, not read-only
checks; approval does not waive collision, kernel-quota or network gates. If any
host-specific network action is needed,
the print-only scoped policy above must be reviewed before starting; this
runbook does not authorize arbitrary firewall or existing-application changes.

1. Run the following commands from the directory containing the reviewed
   `deploy/worker/` files, separate from existing application checkouts. Freeze
   the reviewed source/config and b51ffb5 runtime artifact. Transfer only
   the approved image archive and deployment files by the existing private
   channel; no EC2 build or registry/service creation. Verify on-host:

   ```sh
   sha256sum noetharaclipz-worker-review.tar.gz
   ```

   Expected SHA256:
   `29afebf52f7e4edca43282405941f9b636611ad8bb36cb1126f7ef1275ce41b9`.
   If it differs, stop. The archive is 762,913,897 bytes and contains no weights,
   footage or secrets. Load it only after the check:

   ```sh
   docker load --input noetharaclipz-worker-review.tar.gz
   docker image inspect noetharaclipz-worker:review --format '{{.Id}}'
   ```

   Reviewed content config digest:
   `sha256:32fd88495ceab2c59ab7bc6a0c7980c1003d9b4b6eea507131783a24be4b88a5`.
   This EC2 daemon reports the original archive's OCI manifest digest as its
   image ID: `sha256:472913bf34e918c48e5b77a56c4ea2dfd31873bdd79ecc2d1c4e7ab4cf3e5759`. Use that verified runtime reference on EC2;
   the manifest points to the same config and all 11 reviewed layers.
   Do not pull a mutable replacement tag or rebuild/upgrade Docker on this host.

2. After collision/path checks pass, create only the private worker directories:

   ```sh
   sudo install -d -o 62001 -g 62001 -m 0700 /var/lib/noetharaclipz-isolated/models /var/lib/noetharaclipz-isolated/cache /var/lib/noetharaclipz-isolated/tmp
   sudo install -d -o root -g 62001 -m 0750 /etc/noetharaclipz-isolated
   ```

   Through the existing secure secret channel, place the existing hosted-project
   service credential at `/etc/noetharaclipz-isolated/supabase-key`, root:62001,
   mode 0440. Do not print it, pass it in command arguments or place it in an env
   file. Docker administrators can read mounted secrets; retain existing admin
   access restrictions. No local Supabase container configuration is changed.

3. Keep a private copy of `config.example.env` with these non-secret settings:

   ```dotenv
   NC_SUPABASE_KEY_FILE=/etc/noetharaclipz-isolated/supabase-key
   NC_WORKER_ROOT=/var/lib/noetharaclipz-isolated
   NC_WORKER_IMAGE=sha256:472913bf34e918c48e5b77a56c4ea2dfd31873bdd79ecc2d1c4e7ab4cf3e5759
   NC_DEPLOY_MODE=standby
   NC_WORKER_OWNER_ID=
   ```

   Use `/etc/noetharaclipz-isolated/worker.env` below. Once approved, install
   only the reviewed worker-specific network policy rendered by
   `egress_policy.py`; verify both scoped hooks and all chain rules before any
   seed/worker start, and verify they do not match existing traffic. Then seed pinned **500M and Whisper only**, with no secret
   attached to the seed service:

   ```sh
   docker compose --env-file /etc/noetharaclipz-isolated/worker.env -f deploy/worker/compose.yaml config --quiet
   docker compose --env-file /etc/noetharaclipz-isolated/worker.env -f deploy/worker/compose.yaml --profile tools run --rm --no-deps -T --entrypoint python seed - < deploy/worker/check_cgroup_limits.py && docker compose --env-file /etc/noetharaclipz-isolated/worker.env -f deploy/worker/compose.yaml --profile tools run --rm --no-deps seed
   ```

   The seed quota probe must return `passed=true` and exit 0; otherwise stop
   without downloading/loading models. Verify the manifest's model/revision
   before proceeding. The seed does not
   claim jobs or run inference. Never invoke the optional 2.2B research runner.

4. Start only this worker in standby and inspect health/limits:

   ```sh
   docker compose --env-file /etc/noetharaclipz-isolated/worker.env -f deploy/worker/compose.yaml up -d --no-deps worker
   docker compose --env-file /etc/noetharaclipz-isolated/worker.env -f deploy/worker/compose.yaml exec -T worker cat /run/worker/health.json
   docker compose --env-file /etc/noetharaclipz-isolated/worker.env -f deploy/worker/compose.yaml exec -T worker python - < deploy/worker/check_cgroup_limits.py
   ```

   Expected `mode=standby`, `ai_ready=false`. No backend call or key loading.
   Require the kernel quota probe's `passed=true`, not just Docker inspect flags.
   Also confirm requested memory=8589934592, swap-total=8589934592,
   NanoCpus=2000000000, uid 62001, no port bindings and only the private worker
   mounts/network. Inspect only this project's container, not full secret-bearing
   metadata of staging/Supabase containers.

5. Create one confirmed temporary QA account via the approved hosted test API.
   Verify its UUID is newly created and differs from the protected upload's
   owner. Record the protected job row read-only before/after; never mutate it.
   Put **only** `NC_QA_OWNER_ID=<new temporary UUID>` in a private `qa-owner.env`
   alongside worker.env. No passwords/service keys in that file. Validate and
   start using the QA override (missing owner fails before startup):

   ```sh
   docker compose --env-file /etc/noetharaclipz-isolated/worker.env --env-file /etc/noetharaclipz-isolated/qa-owner.env -f deploy/worker/compose.yaml -f deploy/worker/compose.qa.yaml config --quiet
   docker compose --env-file /etc/noetharaclipz-isolated/worker.env -f deploy/worker/compose.yaml exec -T worker python - < deploy/worker/check_cgroup_limits.py && docker compose --env-file /etc/noetharaclipz-isolated/worker.env --env-file /etc/noetharaclipz-isolated/qa-owner.env -f deploy/worker/compose.yaml -f deploy/worker/compose.qa.yaml up -d --no-deps worker
   ```

   The activation command is chained to actual standby quota proof with `&&`;
   a failing probe cannot activate QA. The override fixes QA mode and on-failure restart; the base keeps global approval false, local
   provider explicit and Gemini false. It recreates only this worker container,
   leaving other applications untouched. Require actual scoped `ai_ready=true`
   before the test. All live claims must name the QA owner UUID.

6. Run the normal website acceptance against the EC2 worker using
   `scripts/acceptance.py` from an already prepared test machine with secure QA
   login variables, `NC_AI_PROVIDER=local`, authorized footage and the reviewed
   app URL. **Do not use `accept_local_queue.py`**, which starts a local worker.
   Verify real claims, automatic highlights, saved edits/refresh, normal Export,
   queued rendering, private download and decode, cross-user denial, readiness,
   cancellation and a controlled worker-only lease recovery test. Keep other
   consumers stopped for this QA owner; no global claims or host reboot test.
   Capture resource/transfer usage and compare existing applications to their baseline.

7. End the trial within 30 minutes; stop only this worker:

   ```sh
   docker compose --env-file /etc/noetharaclipz-isolated/worker.env -f deploy/worker/compose.yaml stop --timeout 100 worker
   ```

   Stop also on any admission/impact threshold above. Wait for/fence any own QA
   lease before own-data cleanup. Leave the original upload unchanged. Keep
   logs for review. Do not run `docker system prune`, shared `compose down`,
   daemon/service restarts, global worker startup, merge or publication.

## Staged QA approval received

The user answered “yes” to the explicit bounded QA request on 2026-11-08.
Do not ask for the same approval again. The approved scope below remains
conditional: first run read-only collision checks,
abort before changes on conflicts, and require actual kernel quota proof and
scoped network verification before AI startup/QA footage. Do not equate the
reported cgroup version with enforced limits. The recorded approval covers the reviewed commit/artifact and only this scope:

> I authorize an isolated, maximum 30-minute SmolVLM2-500M QA deployment on
> i-0be10e530045fc650 in us-east-2 using the reviewed image/configuration, capped
> at 8 GiB RAM, 2 vCPUs and one active job. Create only the dedicated worker
> paths/secrets/network and temporary QA account; use only its explicit UUID.
> Abort before changes if reserved resources conflict; do not load models or
> enable AI unless the kernel quota and scoped network preflights pass.
> Apply only the separately reviewed worker-specific network policy. Permit
> worker-only graceful stop/recovery testing. Keep Gemini and global processing
> disabled, preserve the existing queued upload and all Noethara/Supabase
> services, and do not resize/create paid infrastructure or change billing settings.

This does not authorize a production/global consumer, indefinite operation,
2.2B, host reboot, Docker upgrades or changes to existing applications. A
successful QA trial still does not grant any of those actions.

## Execution access blocker and operator handoff

After approval, this session rechecked its available tools and local login
capabilities: there is no AWS connector, usable AWS identity/CLI, SSH key,
SSH config or SSH agent. The managed cloud desktop is this development machine,
not a connection to the EC2 instance. No EC2 command has been executed and no
QA account, worker, volumes, paths or firewall rules have been created.
Authorization is recorded; an existing authorized remote execution channel or
operator execution is required to proceed. Do not install/change AWS credentials.

The small QA bundle contains only reviewed deployment files and this runbook;
it has no service key, QA login, footage or model weights. Extract it in a new
operator-owned staging directory, separate from existing application checkouts.
Then run this first **read-only** step on the existing EC2 login:

```sh
sudo -n python3 deploy/worker/host_probe.py
sudo -n iptables -S
```

Review reserved UID/GID 62001, both dedicated paths, `nccz-qa0` and
`NCZQA_EGRESS` before any deployment mutation; abort on foreign ownership or
unverifiable state. The second command includes existing chain declarations,
so a collision can be detected without interpreting permission errors as
absence. These commands print no container environment or secret contents.
Return their output for review; do not independently advance to model seeding
or AI startup. Subsequent steps remain covered by the existing conditional
approval once their prerequisites pass.


## Post-approval operator recheck and SSM-only transfer

The operator ran the inline read-only checks successfully on the target:
8 CPUs, 31,207,124 KiB MemAvailable (about 29.8 GiB), no swap, and 52.2 GiB
free disk. UID/GID 62001, both dedicated paths and `nccz-qa0` are unused.
The complete IPv4 filter table has no `NCZQA_EGRESS`; DOCKER-USER is empty.
The same six running containers remain present with low snapshot CPU and about
409.87 MiB combined RAM. This passes capacity and those specific collision
checks, not actual worker quota/network proof. Before mutations also inspect
stopped containers for this dedicated Compose project (read-only):

```sh
sudo -n docker ps -a --filter label=com.docker.compose.project=noetharaclipz-isolated --format '{{.Names}} {{.Status}}'
```

The operator has **SSM terminal only**. The reviewed image/config have not
reached EC2. A temporary private GitHub draft release was tried as an
asset-only download staging route. Its upload endpoint returned HTTP 401
although repository API access works. No asset was uploaded and no release
was published; the empty draft (ID 438521804) was deleted and the release
list is empty. No credentials were installed, copied into chat, or changed.
No public temporary file host or new paid service was substituted.

A working private transfer channel is now required: repair existing GitHub
release-asset upload access, or use an already authorized private download
location. Do not paste account/service credentials into the SSM terminal or
chat. Once staged, verify the existing archive hash and image ID, then follow
the conditional deployment sequence. Do not rebuild on EC2, start a worker,
or process any job to work around the transfer blocker.


## Secure transfer route prepared and verified

The earlier GitHub upload blocker is superseded by the existing private
Supabase route in [private-worker-transfer.md](private-worker-transfer.md).
The original image was not rebuilt; the exact tar stream was recompressed and
all image blobs/rootfs/config were checked. Private JSON chunks and signed
manifest download passed a complete roundtrip in the managed cloud environment.
No Actions/registry activation, new bucket, RLS change or account credential
transfer is involved. Temporary transport objects must be cleaned after EC2
receipt or abandonment. See `docs/evidence/private-worker-transfer.json` for
hashes, expiry and actual results; signed URLs remain only in the private
handoff/state, never Git.

This has not yet verified receipt on EC2 and has not loaded or started anything
there. The next action is the operator's single-block SSM download. Before any
image load, inspect stopped containers for this Compose project and abort if
an existing `noetharaclipz-worker:review` tag has a different image ID. The
existing approved kernel/network gates and bounded QA scope still apply.


## EC2 artifact receipt verified; next image/quota gate

The operator's SSM output confirms both file sizes and SHA256 values at
`/tmp/nccz-transfer-kbbradmg/received`, with `transfer_verified=true` and
`worker_started=false`. This is operator-observed receipt, not direct agent
access. All 109 temporary transport objects have now been removed from only
our dedicated prefix; an independent list confirms zero remain, and total
storage is back to the original 48,627,594 bytes. The protected job row remains
identical: queued, zero attempts. Signed handoff links are no longer needed.

The next approved step is to load only the verified image, after checking the
target, current headroom, stopped project containers and any existing image tag.
Then run a short-lived quota diagnostic with `--network none`, no volumes,
credentials or ports, and the immutable image ID. Its entrypoint is overridden
to Python reading only the reviewed cgroup probe. This diagnostic is neither
the worker nor asset seeder: it cannot access the queue or private services.
It is automatically removed and does not download/load any model. Network
policy remains mandatory before later network-connected seed/worker startup.
A successful diagnostic is not a claim that seed/standby or network verification
has passed; those still follow the existing runbook.

The exact next SSM block (syntax-checked here, not run on EC2 by this agent):

```sh
(
set -eu
cd /tmp/nccz-transfer-kbbradmg/received
[ "$(cat /sys/devices/virtual/dmi/id/board_asset_tag)" = i-0be10e530045fc650 ]
nc_image='sha256:472913bf34e918c48e5b77a56c4ea2dfd31873bdd79ecc2d1c4e7ab4cf3e5759'
python3 - <<'CHECK'
import json, shutil
from pathlib import Path
ram = int(next(line.split()[1] for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemAvailable:'))) * 1024
disk = shutil.disk_usage('/var/lib').free
assert ram >= 10 * 1024**3 and disk >= 20 * 1024**3, 'STOP: insufficient host headroom'
print(json.dumps({'available_ram_gib': round(ram / 1024**3, 1), 'free_disk_gib': round(disk / 1024**3, 1)}))
CHECK
printf '%s\n' 'd4039e807525aab63820b947e6ee99944cf221776a85fb08c1390bfd605e6394  worker-image.tar.xz' 'db369c5c9001e53d33e1b6e053224e2318f41eadb7285569ac597095f28be6da  worker-config.tar.gz' 'e35ff35de3e085799b7d10ed2b3d7eec6ad0ca28d10ab682e075921e0bfed5fe  config/deploy/worker/check_cgroup_limits.py' | sha256sum -c -
nc_project=$(sudo -n docker --host=unix:///var/run/docker.sock ps -aq --filter label=com.docker.compose.project=noetharaclipz-isolated)
[ -z "$nc_project" ] || { echo 'STOP: existing worker project containers'; exit 1; }
nc_tag=$(sudo -n docker --host=unix:///var/run/docker.sock image ls -q --filter reference=noetharaclipz-worker:review)
if [ -n "$nc_tag" ]; then
    nc_existing=$(sudo -n docker --host=unix:///var/run/docker.sock image inspect noetharaclipz-worker:review --format '{{.Id}}')
    [ "$nc_existing" = "$nc_image" ] || { echo 'STOP: existing tag has a different image'; exit 1; }
fi
sudo -n docker --host=unix:///var/run/docker.sock load --input worker-image.tar.xz
nc_loaded=$(sudo -n docker --host=unix:///var/run/docker.sock image inspect noetharaclipz-worker:review --format '{{.Id}}')
[ "$nc_loaded" = "$nc_image" ]
sudo -n docker --host=unix:///var/run/docker.sock run --rm --interactive --pull=never --platform linux/amd64 --network none --user 62001:62001 --read-only --cap-drop ALL --security-opt no-new-privileges:true --memory 8g --memory-swap 8g --cpus 2 --cpu-shares 256 --pids-limit 256 --oom-score-adj 500 --entrypoint python "$nc_image" - < config/deploy/worker/check_cgroup_limits.py
)
```

Return the complete cgroup JSON output. Stop on any failed check; do not
advance to models, QA/global processing or a network-connected worker.


## Image load reported; quota result missing

The operator confirms 28.9 GiB MemAvailable, 52.2 GiB free disk, all three
hash checks OK and `Loaded image: noetharaclipz-worker:review`. No runtime
image-ID or quota JSON was supplied. The original block can stop silently at
its image-ID comparison; this is a hypothesis until inspect metadata is read.
Do not bypass that comparison, substitute a different ID, reload the archive,
or claim quotas passed. Next read only this image's ID/platform/runtime user:

```sh
sudo -n docker --host=unix:///var/run/docker.sock image inspect noetharaclipz-worker:review --format 'ID={{.Id}} OS={{.Os}} ARCH={{.Architecture}} USER={{.Config.User}}'
```

The image is loaded, but no AI worker or successful quota probe is evidenced.


## Config/OCI identity distinction resolved; no reload required

The operator reports Docker `.Id` as `sha256:472913bf34e918c48e5b77a56c4ea2dfd31873bdd79ecc2d1c4e7ab4cf3e5759`, linux/amd64,
user 62001:62001. The exact same digest is a content-addressed OCI manifest
already present in the original reviewed archive, whose raw bytes hash to that
value. The archive index points to it; it points to config `sha256:32fd88495ceab2c59ab7bc6a0c7980c1003d9b4b6eea507131783a24be4b88a5`
and the same 11 layer digests already verified against the rootfs. Nothing was
rebuilt or changed. The guard incorrectly compared two different digest kinds,
so the original block exited before the quota diagnostic. It was not a quota
failure and must not be bypassed by accepting an arbitrary new digest.

The verifier now checks index -> manifest -> reviewed config/layer binding and
accepts only those content-derived runtime identities. Actual archive verification
passes for the EC2-reported ID; regression tests reject other configs, layers
and tampered manifests. All 99 worker tests pass, with one optional sample test
skipped. These are offline identity tests, not proof of EC2 resource limits.

Use the OCI digest above as `NC_WORKER_IMAGE` in this host's private worker.env.
Do not rebuild, reload, retag or start a worker to fix the identity comparison.
Run only the remaining diagnostic below (syntax checked locally; not yet run
on EC2), then return its cgroup JSON. No credentials, mounts, network or model
loading are involved:

```sh
(
set -eu
cd /tmp/nccz-transfer-kbbradmg/received
[ "$(cat /sys/devices/virtual/dmi/id/board_asset_tag)" = i-0be10e530045fc650 ]
printf '%s\n' 'e35ff35de3e085799b7d10ed2b3d7eec6ad0ca28d10ab682e075921e0bfed5fe  config/deploy/worker/check_cgroup_limits.py' | sha256sum -c -
sudo -n docker --host=unix:///var/run/docker.sock run --rm --interactive --pull=never --platform linux/amd64 --network none --user 62001:62001 --read-only --cap-drop ALL --security-opt no-new-privileges:true --memory 8g --memory-swap 8g --cpus 2 --cpu-shares 256 --pids-limit 256 --oom-score-adj 500 --entrypoint python sha256:472913bf34e918c48e5b77a56c4ea2dfd31873bdd79ecc2d1c4e7ab4cf3e5759 - < config/deploy/worker/check_cgroup_limits.py
)
```


## Actual EC2 quota gate passed; network preflight prepared

The operator's network-none diagnostic returned cgroup v2 memory.max
8,589,934,592, cpu.max `200000 100000`, memory.swap.max 0 and pids.max 256,
with all five checks true and `passed=true`. This is actual kernel evidence,
not Docker requested settings. It applies to that diagnostic; seed/standby
profiles still require their own probe before model/AI activation.

The next operator step is `deploy/worker/network_preflight.py`. It requires
root through existing sudo and `--apply-approved-qa-policy`, validates the
instance/image, source hashes, host headroom, existing service health and all
reserved resources, and aborts before mutation on a conflict. It uses exactly
the previously approved egress renderer (SHA256 ec116cab16d2276b87d675eced9d12b83f05b860687f7ade458b8e35a868a646).
No source/global policy or existing-service rule is flushed or replaced.

Only after those checks does it install the reviewed source-bridge hooks,
create the dedicated Compose-labeled network on unused 172.20.0.0/24, and run
one disposable diagnostic capped at 8 GiB / 2 vCPU with a 180-second maximum
process lifetime. There are no mounts, ports, credentials, queue calls or model
loads. It checks actual cgroups again, IPv6-disabled namespace settings, public
DNS/TLS to Supabase and Hugging Face metadata, and TCP-only negative probes.
Private targets use unused addresses rather than existing application services;
IMDS gets no HTTP request or token exchange. Each denial requires its matching
iptables REJECT counter to increase, so a closed port is not an isolation pass.

The helper requires diagnostic removal before removing protections. A successful
result retains only this owned
network and exact reviewed rules for the following QA stages and writes a
root-owned receipt at `<received>/network-preflight.json`. Network labels and
the receipt identify ownership; the preflight refuses to rerun over existing
reserved resources. On failure it removes only its own network and successfully
applied rules, after diagnostic removal; uncertain cleanup retains protections
and stops. No daemon/host restart or security-group change is authorized. Before
later seeding/startup recheck these rules and ownership; none are a promise of
persistence across a reboot.

The helper is staged as a small private, SHA256-verified JSON handoff through
the same existing Supabase bucket. No image transfer/rebuild, new PAT, registry,
Actions run or account credential on EC2 is needed. At this commit the network
preflight has **not run on EC2**; only its tests and source review have passed.
Return the complete JSON output before proceeding to model seeding or workers.


## Network helper failed; do not retry without the actual Docker error

The operator's helper exited with `Command failed: docker --host=...` and no
network result. The helper discarded stderr and hid the Docker subcommand.
The repository now retains the command/action, return code and bounded redacted
stderr without logging supplied stdin. This reporting fix has not yet patched
the existing EC2 copy. The following Apport traceback is a secondary Ubuntu
crash-reporter error for a Python stdin script, not the original Docker failure.
Do not alter Apport, restart Docker or change credentials to address it.

The network gate has not passed. Partial bridge/rule/diagnostic cleanup cannot
be assumed from this output. Read the saved receipt, own resources and the
failing read-only metadata commands before applying or removing any rules.
No new artifact, setup retry or worker start is needed for that diagnosis.
A template involving optional container Health metadata is one possible read
failure; it is not established as the cause until Docker stderr is observed.

The small private helper object was removed after confirmed host receipt.
The operator's existing local copy remains available; do not reuse the expired
or removed download link. The target remains an actual owner-scoped EC2 QA
upload/analysis/export/download, not preparation-only completion. The worker
has not yet been deployed or advertised as ready.


## Confirmed metadata bug fixed; retry without a download or reload

The operator's read-only trace confirms `map has no entry for key "Health"`
on the existing REST container. No receipt, owned diagnostic container,
network or NCZQA_EGRESS chain exists. The original preflight stopped in its
service snapshot before applying rules. Unchecked containers are allowed by
that guard; a missing healthcheck is not an unhealthy service. Do not add a
healthcheck, reset restart counts or restart any existing service to fix it.

Use `{{with index .State "Health"}}{{.Status}}{{else}}none{{end}}` instead of
looking up the optional key directly. A real managed-cloud Docker regression
reproduced the old error and accepted the new template against an empty-image
container that was created but never started (PID 0), then removed with its
image. This is a template test, not an EC2 network pass. Existing unhealthy
services remain rejected. All 120 worker tests pass; one optional sample test
is skipped. The 26 network/policy/error tests also pass.

The operator retry uses the existing host copy, verifies its original SHA256
83a5f1445364d2d28942d015ba3741a662744a9ab9685cd56984afb6f229984b,
and fixes only that quoted template in memory. It attaches the tested redacted
command-error runner and invokes the same main routine under the existing
conditional QA approval. Offline AST comparison confirms all admission, policy,
cleanup and receipt functions are unchanged. No new download/image transfer,
helper-file rewrite, daemon restart or credential input is needed. Network
success and worker readiness remain unverified until the operator returns
an actual result.

```sh
sudo -n python3 - <<'PY'
import hashlib, json, re, subprocess, sys
from pathlib import Path

def run(command, source=None, timeout=30):
    result = subprocess.run(command, input=source, text=True, capture_output=True, timeout=timeout)
    if result.returncode:
        # Commands in this helper never contain credentials. Do not include
        # stdin, and redact credential-shaped text if a tool emits it anyway.
        error = result.stderr.strip()
        error = re.sub(r"(?i)(Bearer\s+)\S+", r"\1[redacted]", error)
        error = re.sub(r"(?i)((?:api[_-]?key|token|password|secret)\s*[=:]\s*)\S+",
                       r"\1[redacted]", error)
        raise RuntimeError(json.dumps({"command": command[:4], "exit_code": result.returncode,
                                       "stderr": error[-2000:]}))
    return result.stdout.strip()

try:
    path = Path("/tmp/nccz-netgate-a62yun7w/network_preflight.py")
    source = path.read_text()
    assert hashlib.sha256(source.encode()).hexdigest() == "83a5f1445364d2d28942d015ba3741a662744a9ab9685cd56984afb6f229984b", "Unexpected helper version"
    old = "{{.Id}} {{.State.StartedAt}} {{.RestartCount}} {{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}"
    new = '{{.Id}} {{.State.StartedAt}} {{.RestartCount}} {{with index .State "Health"}}{{.Status}}{{else}}none{{end}}'
    assert source.count(json.dumps(old)) == 1, "Unexpected template"
    source = source.replace(json.dumps(old), json.dumps(new), 1)
    scope = {"__name__": "nccz_fixed", "__file__": str(path)}
    exec(compile(source, str(path), "exec"), scope)
    scope["run"] = run
    sys.argv = [str(path), "--config-root", "/tmp/nccz-transfer-kbbradmg/received/config", "--apply-approved-qa-policy"]
    scope["main"]()
except Exception as error:
    print(json.dumps({"failed": True, "reason": str(error), "worker_started": False}))
    raise SystemExit(1) from None
PY
```
