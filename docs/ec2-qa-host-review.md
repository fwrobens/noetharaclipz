# Ohio host review and exact gated QA procedure

Target: **i-0be10e530045fc650**, **us-east-2**, t2.xlarge, 4 vCPU / 16 GiB.
Runtime artifact: the tested **b51ffb5 preparation**, pinned SmolVLM2-500M only.
Do not install/activate the 2.2B research model or rerun the research comparison.
No EC2 deployment, worker start, AWS credential installation/change, or existing
service mutation has been performed in this review.

## Current decision

The operator's earlier **14 GiB MemAvailable, 53 GB free disk, low CPU and about
1,300 credits** are promising for a bounded QA trial. They exceed our numerical
snapshot requirements (10 GiB MemAvailable and 20 GiB free disk). They are not
fresh measurements or proof of spare capacity during staging/Supabase peaks.
The t2.xlarge earned-credit maximum is 1,296, so “around 1,300” is consistent with
a rounded near-full balance, not a separately verified current value.

**Conditionally suitable; final host/security review is pending.** This session
still has no AWS connector/identity or AWS CLI. Configured credential/profile
files are empty. Region is now known from the operator. No attempt was made to
install CLI tools, configure credentials, assume another role or use another
machine's identity. Return the read-only results below to finish the review.

The Docker resource envelope is locally tested. It limits this worker to
8 GiB RAM, 2 vCPU, no swap, low CPU shares, one active job, 256 PIDs and no public
ports, with non-root/read-only execution and private paths/secrets. It cannot
guarantee zero shared-host impact: filesystem I/O, cache pressure, CPU credits
and peak workloads remain shared. Docker bridge separation alone does not block
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
aws ec2 describe-instance-credit-specifications --region us-east-2 --instance-ids i-0be10e530045fc650 --output json
aws cloudwatch get-metric-statistics --region us-east-2 --namespace AWS/EC2 --metric-name CPUCreditBalance --dimensions Name=InstanceId,Value=i-0be10e530045fc650 --start-time "$(date -u -d '1 hour ago' +%FT%TZ)" --end-time "$(date -u +%FT%TZ)" --period 300 --statistics Minimum Average --query 'sort_by(Datapoints,&Timestamp)[-6:]' --output json
```

For security groups, use only the IDs returned by that exact instance query:

```sh
aws ec2 describe-security-groups --region us-east-2 --group-ids <returned-security-group-IDs> --query 'SecurityGroups[].{Id:GroupId,Ingress:IpPermissions,Egress:IpPermissionsEgress}' --output json
```

For the full existing seven-day CPU/credit/volume/security review in one command,
use the prepared read-only inventory with the already authenticated CLI:

```sh
python3 scripts/aws_worker_inventory.py --region us-east-2 --instance-id i-0be10e530045fc650 --output /tmp/noetharaclipz-aws-review.json
```

The output is mode 0600; no credential configuration is changed. Review
CPUUtilization average/max, CPUCreditBalance trend, CPUSurplusCreditBalance and
CPUSurplusCreditsCharged, credit mode, EBS encryption and metadata options.
No Cost Explorer, Logs Insights, agent installation or monitoring activation.
Do not infer zero cost or zero risk from missing metrics or access-denied output.

## Admission and cost decision

Require fresh ≥10 GiB MemAvailable, ≥20 GiB free worker/Docker filesystem budget,
low sustained CPU with existing workloads reviewed, and no new OOM/resource
regression. Confirm Docker 24+/Compose v2.24+, daemon already boot-enabled,
UID/GID 62001 and dedicated paths/project/bridge are unused or explicitly owned
by this deployment. Confirm network/security policy and volume encryption.

For the first trial, use a **30-minute maximum QA window**, start with at least
300 CPU credits and no unexplained surplus-credit charges, and stop only this
worker if credits reach 200, MemAvailable drops below 2 GiB, free disk drops
below 10 GiB, it OOMs, or another application regresses. These are proposed
operator stop thresholds, not automatically enforced CloudWatch alarms. Missing
current readings mean admission remains pending, not approved by the old 1,300.

Existing infrastructure allocation can remain unchanged. The previously quoted
Linux On-Demand illustration is $0.1856/hour (~$135.49/730 h), excluding existing
EBS/IP and any transfer; verify the actual Ohio account rate/discounts. Credits
are earned at 54/hour = 0.9 vCPU total. Full 2-vCPU use alone drains about 66
credits/hour after earnings; a rounded 1,300-credit balance would last about
19.7 hours in that simplified case, **not indefinitely**. Existing applications
can deplete it faster (up to 186 credits/hour at all 4 vCPUs busy).

Standard mode can throttle after depletion. Unlimited Linux surplus is
$0.05/vCPU-hour: a continuous worker could add about $40.15–$73/month depending
on existing baseline usage, plus any billed transfer. The bounded QA trial is
intended to stay within a verified earned-credit buffer; it is not a guarantee
of zero bill impact. Do not change credit mode, resize, add EBS/NAT/ALB/ECR/log
subscriptions or enable paid monitoring. No upgrade is currently justified.

## Exact deployment sequence — do not execute before approval

All commands in this section are **future authorized deployment actions**,
not read-only checks. First finish the admission/security review and record
explicit QA authorization. If any host-specific network action is needed,
its exact rules and scope must be reviewed before starting; this runbook does
not authorize arbitrary firewall or existing-application changes.

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

   Required image ID:
   `sha256:32fd88495ceab2c59ab7bc6a0c7980c1003d9b4b6eea507131783a24be4b88a5`.
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
   NC_WORKER_IMAGE=sha256:32fd88495ceab2c59ab7bc6a0c7980c1003d9b4b6eea507131783a24be4b88a5
   NC_DEPLOY_MODE=standby
   NC_WORKER_OWNER_ID=
   ```

   Use `/etc/noetharaclipz-isolated/worker.env` below. Once approved, install
   only the reviewed worker-specific network policy; verify it does not match
   existing traffic. Then seed pinned **500M and Whisper only**, with no secret
   attached to the seed service:

   ```sh
   docker compose --env-file /etc/noetharaclipz-isolated/worker.env -f deploy/worker/compose.yaml config --quiet
   docker compose --env-file /etc/noetharaclipz-isolated/worker.env -f deploy/worker/compose.yaml --profile tools run --rm --no-deps seed
   ```

   Verify the manifest's model/revision before proceeding. The seed does not
   claim jobs or run inference. Never invoke the optional 2.2B research runner.

4. Start only this worker in standby and inspect health/limits:

   ```sh
   docker compose --env-file /etc/noetharaclipz-isolated/worker.env -f deploy/worker/compose.yaml up -d --no-deps worker
   docker compose --env-file /etc/noetharaclipz-isolated/worker.env -f deploy/worker/compose.yaml exec -T worker cat /run/worker/health.json
   ```

   Expected `mode=standby`, `ai_ready=false`. No backend call or key loading.
   Confirm actual memory=8589934592, swap-total=8589934592 (no extra swap),
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
   docker compose --env-file /etc/noetharaclipz-isolated/worker.env --env-file /etc/noetharaclipz-isolated/qa-owner.env -f deploy/worker/compose.yaml -f deploy/worker/compose.qa.yaml up -d --no-deps worker
   ```

   The override fixes QA mode; the base keeps global approval false, local
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
   Capture stats/credits and compare existing applications to their baseline.

7. End the trial within 30 minutes; stop only this worker:

   ```sh
   docker compose --env-file /etc/noetharaclipz-isolated/worker.env -f deploy/worker/compose.yaml stop --timeout 100 worker
   ```

   Stop also on any admission/impact threshold above. Wait for/fence any own QA
   lease before own-data cleanup. Leave the original upload unchanged. Keep
   logs for review. Do not run `docker system prune`, shared `compose down`,
   daemon/service restarts, global worker startup, merge or publication.

## Approval needed later

Approval is **not requested until the fresh host and network review passes**.
The authorization should identify the reviewed commit/artifact and permit only:

> I authorize an isolated, maximum 30-minute SmolVLM2-500M QA deployment on
> i-0be10e530045fc650 in us-east-2 using the reviewed image/configuration, capped
> at 8 GiB RAM, 2 vCPUs and one active job. Create only the dedicated worker
> paths/secrets/network and temporary QA account; use only its explicit UUID.
> Apply only the separately reviewed worker-specific network policy. Permit
> worker-only graceful stop/recovery testing. Keep Gemini and global processing
> disabled, preserve the existing queued upload and all Noethara/Supabase
> services, and do not resize/create paid infrastructure or change billing mode.

This does not authorize a production/global consumer, indefinite operation,
2.2B, host reboot, Docker upgrades or changes to existing applications. A
successful QA trial still does not grant any of those actions.
