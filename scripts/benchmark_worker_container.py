"""Local-only Docker gaming benchmark. No credentials, networking or queue access.

Verifies actual kernel quotas before any model/media work, then runs serially.
Requested Docker flags alone cannot establish an 8 GiB/2 CPU sandbox. Never touches
EC2. Existing unrelated containers are only enumerated to assert preservation.
"""

import argparse
import json
import os
import subprocess
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--sample", type=Path, required=True)
    p.add_argument("--hf-cache", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--image", default="noetharaclipz-worker:review")
    args = p.parse_args()
    sample, cache, output = (
        args.sample.resolve(strict=True),
        args.hf_cache.resolve(strict=True),
        args.output.resolve(),
    )
    output.mkdir(parents=True, exist_ok=True, mode=0o700)
    env = dict(os.environ)
    for name in (
        "DOCKER_HOST",
        "DOCKER_CONTEXT",
        "DOCKER_TLS",
        "DOCKER_TLS_VERIFY",
        "DOCKER_CERT_PATH",
    ):
        env.pop(name, None)
    base = ["docker", "--host=unix:///var/run/docker.sock"]

    def docker(*cmd, **kw):
        return subprocess.run(
            base + list(cmd), env=env, capture_output=True, text=True, **kw
        )

    before = docker("ps", "--format", "{{.ID}} {{.Names}} {{.Status}}")
    before.check_returncode()
    summary = {
        "ec2_touched": False,
        "supabase_access": False,
        "limits": {
            "memory_bytes": 8 * 1024**3,
            "cpus": 2,
            "swap_bytes": 0,
            "published_ports": [],
            "network": "none",
        },
        "runs": [],
    }
    for mode in ("prepare", "500m", "2.2b"):
        name = "nc-local-benchmark-" + uuid.uuid4().hex[:10]
        cmd = [
            "run",
            "-d",
            "--name",
            name,
            "--network=none",
            "--memory=8g",
            "--memory-swap=8g",
            "--cpus=2",
            "--pids-limit=256",
            "--read-only",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            "--user",
            f"{os.getuid()}:{os.getgid()}",
            "--tmpfs",
            f"/tmp:rw,noexec,nosuid,size=256m,uid={os.getuid()},gid={os.getgid()}",
            "-e",
            "TMPDIR=/tmp",
            "-v",
            str(sample) + ":/samples/gaming.mp4:ro",
            "-v",
            str(cache) + ":/models/huggingface:ro",
            "-v",
            str(output) + ":/reports",
            "-v",
            str(ROOT / "deploy/worker/check_cgroup_limits.py") + ":/quota_probe.py:ro",
            "--entrypoint",
            "python",
            args.image,
            "-c",
            """import runpy,sys,json
q=runpy.run_path('/quota_probe.py')
r=q['evaluate'](q['read_limits']())
print(json.dumps(r),flush=True)
if not r['passed']: sys.exit(78)
sys.argv=['benchmark',sys.argv[1]]
runpy.run_module('noetharaclipz_deploy.benchmark',run_name='__main__')
""",
            mode,
        ]
        try:
            docker(*cmd).check_returncode()
            waited = docker("wait", name, timeout=700)
            waited.check_returncode()
            log = docker("logs", name)
            (output / (mode + ".log")).write_text(log.stdout + log.stderr)
            info = json.loads(docker("inspect", name).stdout)[0]
            summary["runs"].append(
                {
                    "mode": mode,
                    "exit_code": info["State"]["ExitCode"],
                    "oom_killed": info["State"]["OOMKilled"],
                    "memory_limit": info["HostConfig"]["Memory"],
                    "nano_cpus": info["HostConfig"]["NanoCpus"],
                }
            )
            if mode == "prepare" and info["State"]["ExitCode"]:
                raise RuntimeError(
                    "Kernel quota verification or media preparation failed; no benchmark pass"
                )
        finally:
            docker("rm", "-f", name)
            (output / "container-summary.json").write_text(
                json.dumps(summary, indent=2) + "\n"
            )
    # Existing local container IDs stay present; no stop/restart/rm against them.
    after = docker("ps", "--format", "{{.ID}} {{.Names}} {{.Status}}")
    summary["existing_container_ids_preserved"] = all(
        line.split()[0] in after.stdout for line in before.stdout.splitlines()
    )
    assert summary["existing_container_ids_preserved"]
    (output / "container-summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
