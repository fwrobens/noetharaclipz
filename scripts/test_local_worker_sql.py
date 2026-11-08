"""Ephemeral PG17 + pinned real PGMQ regression; never contacts hosted Supabase."""

import hashlib
import argparse
import json
import os
import subprocess
import time
import uuid
from urllib.request import urlopen
from pathlib import Path
from test_heartbeat_migration import IMAGE

ROOT = Path(__file__).resolve().parents[1]
PGMQ_REV = "12462bd29c2e4f59e58ac4840c2dcf0872d8c5c9"
PGMQ_FILES = {
    "pgmq.control": (
        "pgmq-extension/pgmq.control",
        "41c1e721b7b2d22484ee40842f2bbc52f571c36ac8bb50eeb3af5e724bdd43e5",
    ),
    "pgmq.sql": (
        "pgmq-extension/sql/pgmq.sql",
        "c2679044f87f4ac9693ef4af61786e23dafe90fb1b3bfa0228286a495cbd7a97",
    ),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pipeline",
        action="store_true",
        help="Also run real local model and queued rendering; requires NC_SAMPLE_VIDEO and optional model dependencies",
    )
    args = parser.parse_args()
    env = os.environ.copy()
    for key in (
        "DOCKER_HOST",
        "DOCKER_CONTEXT",
        "DOCKER_TLS",
        "DOCKER_TLS_VERIFY",
        "DOCKER_CERT_PATH",
    ):
        env.pop(key, None)
    base = ["docker", "--host=unix:///var/run/docker.sock"]

    def cmd(*args, **kwargs):
        return subprocess.run(
            base + list(args), env=env, capture_output=True, text=True, **kwargs
        )

    cache = ROOT.parent / ".cache/pgmq-1.8.1"
    cache.mkdir(parents=True, exist_ok=True)
    for name, (remote, checksum) in PGMQ_FILES.items():
        path = cache / name
        if not path.exists():
            with urlopen(
                f"https://raw.githubusercontent.com/pgmq/pgmq/{PGMQ_REV}/{remote}",
                timeout=60,
            ) as response:
                data = response.read()
            if hashlib.sha256(data).hexdigest() != checksum:
                raise RuntimeError("Pinned PGMQ download checksum mismatch")
            path.write_bytes(data)
        if hashlib.sha256(path.read_bytes()).hexdigest() != checksum:
            raise RuntimeError("Pinned PGMQ cache checksum mismatch")
    fixture = """
create role anon; create role authenticated; create role service_role bypassrls;
create publication supabase_realtime;
create schema auth; grant usage on schema auth to anon,authenticated,service_role;
create table auth.users(id uuid primary key,email text,aud text,role text,raw_app_meta_data jsonb,raw_user_meta_data jsonb);
create function auth.jwt() returns jsonb language sql stable as $$select coalesce(nullif(current_setting('request.jwt.claims',true),''),'{}')::jsonb$$;
create function auth.uid() returns uuid language sql stable as $$select (auth.jwt()->>'sub')::uuid$$;
create schema storage; grant usage on schema storage to anon,authenticated,service_role;
create table storage.buckets(id text primary key,name text,public boolean,file_size_limit bigint,allowed_mime_types text[]);
create table storage.objects(id uuid primary key default gen_random_uuid(),bucket_id text,name text,metadata jsonb,unique(bucket_id,name));
alter table storage.objects enable row level security;
grant select,insert,update,delete on storage.objects to authenticated,service_role;
create function storage.foldername(name text) returns text[] language sql immutable as $$select string_to_array(name,'/')$$;
"""
    name = "nc-local-worker-" + uuid.uuid4().hex[:10]
    try:
        c = cmd(
            "run",
            "--rm",
            "-d",
            "--network=none",
            "--name",
            name,
            "--tmpfs",
            "/var/lib/postgresql/data:rw,size=512m",
            "-e",
            "POSTGRES_HOST_AUTH_METHOD=trust",
            "-e",
            "POSTGRES_DB=local_worker_test",
            IMAGE,
        )
        c.check_returncode()
        for _ in range(100):
            if (
                cmd(
                    "exec",
                    name,
                    "pg_isready",
                    "-U",
                    "postgres",
                    "-d",
                    "local_worker_test",
                ).returncode
                == 0
            ):
                break
            time.sleep(0.2)
        else:
            raise RuntimeError("Postgres startup failed")
        for src, dest in [
            (cache / "pgmq.control", "pgmq.control"),
            (cache / "pgmq.sql", "pgmq--1.8.1.sql"),
        ]:
            c = cmd(
                "cp", str(src), name + ":/usr/share/postgresql/17/extension/" + dest
            )
            c.check_returncode()
            cmd(
                "exec",
                name,
                "chmod",
                "0644",
                "/usr/share/postgresql/17/extension/" + dest,
            ).check_returncode()
        sql = fixture + "\n"
        for p in sorted((ROOT / "supabase/migrations").glob("*.sql")):
            sql += p.read_text() + "\n"
        proposal = ROOT / "docs/proposals/local-worker-queue.sql"
        sql += proposal.read_text() + "\n"
        sql += (ROOT / "supabase/tests/access_and_jobs.sql").read_text() + "\n"
        sql += (ROOT / "supabase/tests/worker_heartbeat.sql").read_text() + "\n"
        sql += (ROOT / "supabase/tests/local_worker.sql").read_text() + "\n"
        c = cmd(
            "exec",
            "-i",
            name,
            "psql",
            "-X",
            "-v",
            "ON_ERROR_STOP=1",
            "-U",
            "postgres",
            "-d",
            "local_worker_test",
            input=sql,
        )
        if c.returncode:
            print(c.stdout[-5000:])
            print(c.stderr)
            c.check_returncode()
        report = {
            "passed": True,
            "hosted_database_changed": False,
            "postgres_image": IMAGE,
            "pgmq_revision": PGMQ_REV,
            "pgmq_sql_sha256": hashlib.sha256(
                (cache / "pgmq.sql").read_bytes()
            ).hexdigest(),
            "proposal_sha256": hashlib.sha256(proposal.read_bytes()).hexdigest(),
            "existing_sql_suites": ["access_and_jobs.sql", "worker_heartbeat.sql"],
            "new_sql_suite": "local_worker.sql",
            "scope": "Actual PostgreSQL/PGMQ with disposable Auth/Storage metadata fixture; not hosted/video acceptance",
        }
        (ROOT / "test-results/local-worker-sql.json").write_text(
            json.dumps(report, indent=2) + "\n"
        )
        print(json.dumps(report, indent=2))
        if args.pipeline:
            from local_queue_pipeline import run_pipeline

            run_pipeline(cmd, name)
    finally:
        cmd("rm", "-f", name)


if __name__ == "__main__":
    main()
