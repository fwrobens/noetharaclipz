"""Import-only smoke inside the existing image with no network, models or key.

This cannot start a worker: the entrypoint is a single inert Python import
command, with no model/credential mounts and --network=none. Not a benchmark.
"""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from build_continuous_bundle import collect, IMAGE, CONFIG, ROOT


def main():
    env = {
        k: v
        for k, v in os.environ.items()
        if k
        not in (
            "DOCKER_HOST",
            "DOCKER_CONTEXT",
            "DOCKER_TLS",
            "DOCKER_TLS_VERIFY",
            "DOCKER_CERT_PATH",
        )
    }
    docker = ["docker", "--host=unix:///var/run/docker.sock"]

    def command(*args):
        result = subprocess.run(
            docker + list(args), env=env, capture_output=True, text=True, timeout=120
        )
        if result.returncode:
            raise RuntimeError("Import smoke failed: " + result.stderr[-2000:])
        return result

    local = json.loads(
        command("image", "inspect", "noetharaclipz-worker:review").stdout
    )[0]
    if (
        local["Id"] not in (IMAGE, CONFIG)
        or local["Os"] != "linux"
        or local["Architecture"] != "amd64"
        or local["Config"]["User"] != "62001:62001"
    ):
        raise ValueError(
            "Existing reviewed image identity changed; do not pull/rebuild silently"
        )
    files = collect()
    tree = hashlib.sha256(
        json.dumps(
            {k: hashlib.sha256(v.encode()).hexdigest() for k, v in files.items()},
            sort_keys=True,
        ).encode()
    ).hexdigest()
    # The managed Docker daemon shares /workspace; /tmp can be a private mount.
    # Only source files are staged here, never models or credentials.
    directory = Path(
        tempfile.mkdtemp(prefix="nc-overlay-smoke-", dir=ROOT / "test-results")
    )
    directory.chmod(0o755)
    try:
        for name, source in files.items():
            path = directory / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(source)
            path.chmod(0o444)
        for path in directory.rglob("*"):
            if path.is_dir():
                path.chmod(0o755)
        code = "import os,json; import continuous_host,continuous_entry; from noetharaclipz.consent import ConsentedBackend; from noetharaclipz.runner import Worker; assert os.getuid()==62001; assert not any(os.getenv(k) for k in ('SUPABASE_SERVICE_ROLE_KEY','SUPABASE_SECRET_KEY','GEMINI_API_KEY')); print(json.dumps({'imports_passed':True,'worker_started':False,'model_loaded':False,'queue_calls':False}))"
        result = command(
            "run",
            "--rm",
            "--pull=never",
            "--network=none",
            "--read-only",
            "--user",
            "62001:62001",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges:true",
            "--memory",
            "8g",
            "--memory-swap",
            "8g",
            "--cpus",
            "2",
            "--pids-limit",
            "256",
            "--mount",
            "type=bind,src=" + str(directory) + ",dst=/code,readonly",
            "--env",
            "PYTHONPATH=/code/host:/code/worker:/code/runtime",
            "--entrypoint",
            "python",
            local["Id"],
            "-c",
            code,
        )
        report = {
            "passed": True,
            "local_base_image_id": local["Id"],
            "ec2_base_image_id": IMAGE,
            "application_overlay_sha256": tree,
            "overlay_files": len(files),
            "image_rebuilt": False,
            "scope": "Changed read-only application overlay; import smoke only, no actual inference/worker/deployment.",
            "container_result": json.loads(result.stdout),
        }
        (ROOT / "test-results/continuous-overlay-smoke.json").write_text(
            json.dumps(report, indent=2) + "\n"
        )
        print(json.dumps(report, indent=2))
    finally:
        shutil.rmtree(directory)


if __name__ == "__main__":
    main()
