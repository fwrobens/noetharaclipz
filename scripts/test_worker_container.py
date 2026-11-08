"""Local Docker isolation/restart test in standby; no key, network or queue."""

import json
import os
import subprocess
import time
import uuid
from pathlib import Path


def main():
    env = dict(os.environ)
    for k in (
        "DOCKER_HOST",
        "DOCKER_CONTEXT",
        "DOCKER_TLS",
        "DOCKER_TLS_VERIFY",
        "DOCKER_CERT_PATH",
    ):
        env.pop(k, None)
    base = ["docker", "--host=unix:///var/run/docker.sock"]

    def docker(*args):
        return subprocess.run(
            base + list(args), env=env, capture_output=True, text=True, timeout=60
        )

    name = "nc-standby-check-" + uuid.uuid4().hex[:8]
    report = {"ec2_touched": False, "queue_access": False, "checks": {}}
    try:
        docker(
            "run",
            "-d",
            "--name",
            name,
            "--init",
            "--restart=unless-stopped",
            "--network=none",
            "--memory=8g",
            "--memory-swap=8g",
            "--cpus=2",
            "--pids-limit=256",
            "--read-only",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            "--tmpfs",
            "/run/worker:rw,noexec,nosuid,size=16m,uid=62001,gid=62001,mode=0700",
            "noetharaclipz-worker:review",
        ).check_returncode()
        for _ in range(50):
            health = docker(
                "exec", name, "python", "-m", "noetharaclipz_deploy.healthcheck"
            )
            if health.returncode == 0:
                break
            time.sleep(0.3)
        health.check_returncode()
        state = json.loads(
            docker("exec", name, "cat", "/run/worker/health.json").stdout
        )
        assert state["mode"] == "standby" and state["ai_ready"] is False
        report["checks"]["standby_healthy_without_secret_or_network"] = True
        info = json.loads(docker("inspect", name).stdout)[0]
        assert info["Config"]["User"] == "62001:62001"
        assert (
            info["HostConfig"]["Memory"] == 8 * 1024**3
            and info["HostConfig"]["NanoCpus"] == 2000000000
        )
        assert (
            info["HostConfig"]["ReadonlyRootfs"]
            and not info["HostConfig"]["PortBindings"]
        )
        report["checks"]["nonroot_readonly_8gib_2cpu_no_ports_enforced"] = True
        # Docker treats `docker kill` as an intentional stop; crash the owned
        # standby supervisor child instead, after restart-policy activation.
        time.sleep(11)
        crash = docker(
            "exec",
            name,
            "python",
            "-c",
            "import os,signal; from pathlib import Path; procs=[int(p.name) for p in Path('/proc').iterdir() if p.name.isdecimal() and int(p.name)>1 and int(p.name)!=os.getpid() and (p/'comm').read_text().strip().startswith('python')]; assert len(procs)==1,procs; os.kill(procs[0],signal.SIGKILL)",
        )
        assert crash.returncode in (0, 137, 143), crash.stderr
        for _ in range(50):
            after = json.loads(docker("inspect", name).stdout)[0]
            if (
                after["RestartCount"] > 0
                and docker(
                    "exec", name, "python", "-m", "noetharaclipz_deploy.healthcheck"
                ).returncode
                == 0
            ):
                break
            time.sleep(0.3)
        assert after["RestartCount"] > 0
        report["checks"]["automatic_restart_after_process_failure"] = True
        docker("stop", "--time=10", name).check_returncode()
        assert json.loads(docker("inspect", name).stdout)[0]["State"]["ExitCode"] == 0
        report["checks"]["graceful_standby_shutdown"] = True
        for mode in ("qa", "global"):
            result = docker(
                "run",
                "--rm",
                "--network=none",
                "-e",
                "NC_DEPLOY_MODE=" + mode,
                "noetharaclipz-worker:review",
            )
            assert result.returncode != 0
            report["checks"][mode + "_without_authorization_scope_refused"] = True
        report["image_id"] = info["Image"]
    finally:
        docker("rm", "-f", name)
    path = Path("test-results/deployment-container-smoke.json")
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
