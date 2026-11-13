"""Disposable local PG17/PGMQ consent tests. Never contacts hosted Supabase."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
from uuid import uuid4

from test_local_worker_sql import PGMQ_FILES
from test_heartbeat_migration import IMAGE

ROOT = Path(__file__).resolve().parents[1]


def concurrency_checks(command, docker, env, name):
    """Actual independent transactions prove both sides of the revoke race."""
    prefix = (
        "select set_config('request.jwt.claims','{\"role\":\"service_role\"}',false);"
    )
    owner = "10000000-0000-0000-0000-000000000001"
    cid = (
        "(select consent_id from private.continuous_owner_consents where owner_id='"
        + owner
        + "')"
    )
    psql = [
        "exec",
        "-i",
        name,
        "psql",
        "-X",
        "-qAt",
        "-v",
        "ON_ERROR_STOP=1",
        "-U",
        "postgres",
        "-d",
        "consent_test",
    ]

    def sql(text):
        result = command(*psql, input=text)
        if result.returncode:
            raise RuntimeError(result.stderr[-2000:])
        return result.stdout

    def start(text):
        process = subprocess.Popen(
            docker + psql,
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        process.stdin.write(text)
        process.stdin.close()
        process.stdin = None
        return process

    def sleeping(app):
        for _ in range(60):
            if (
                sql(
                    "select count(*) from pg_stat_activity where application_name='"
                    + app
                    + "' and wait_event='PgSleep';"
                ).strip()
                == "1"
            ):
                return
            time.sleep(0.05)
        raise RuntimeError("Concurrent SQL lock fixture failed to enter sleep")

    jid = "30000000-0000-0000-0000-000000000009"
    sql(
        prefix
        + "select public.nc_source('"
        + owner
        + "','20000000-0000-0000-0000-000000000009','"
        + jid
        + "'); select public.worker_claim_optin('"
        + owner
        + "',"
        + cid
        + ");"
    )
    args = (
        "'"
        + owner
        + "',"
        + cid
        + ",'"
        + jid
        + "',(select lease_token from public.processing_jobs where id='"
        + jid
        + "')"
    )
    writer = start(
        "set application_name='nc_consent_writer'; begin;"
        + prefix
        + "select private.continuous_job("
        + args
        + "); select pg_sleep(3); select public.worker_tick_optin("
        + args
        + ",'failed',0,'SQL concurrency fixture only'); commit;"
    )
    try:
        sleeping("nc_consent_writer")
        sql(
            prefix
            + "select public.revoke_owner_processing('"
            + owner
            + "',"
            + cid
            + ",'Concurrent revoke after existing commit');"
        )
        _out, error = writer.communicate(timeout=10)
        if writer.returncode:
            raise RuntimeError(error[-2000:])
        assert (
            sql(
                "select status from public.processing_jobs where id='" + jid + "';"
            ).strip()
            == "failed"
        )
    finally:
        if writer.poll() is None:
            writer.kill()
            writer.wait()
    # New consent generation and new job: revocation already holds the row lock
    # when a subsequent worker transaction starts. It must fail after the wait.
    sql(
        'select set_config(\'request.jwt.claims\',\'{"role":"authenticated","sub":"'
        + owner
        + "\"}',false); select public.request_processing_consent('40000000-0000-0000-0000-000000000003','local-video-v1');"
    )
    sql(
        prefix
        + "select public.approve_processing_consent('"
        + owner
        + "',"
        + cid
        + ",clock_timestamp()+interval '1 hour','Reverse lock-order fixture');"
    )
    jid = "30000000-0000-0000-0000-000000000010"
    sql(
        prefix
        + "select public.nc_source('"
        + owner
        + "','20000000-0000-0000-0000-000000000010','"
        + jid
        + "'); select public.worker_claim_optin('"
        + owner
        + "',"
        + cid
        + ");"
    )
    args = (
        "'"
        + owner
        + "',"
        + cid
        + ",'"
        + jid
        + "',(select lease_token from public.processing_jobs where id='"
        + jid
        + "')"
    )
    revoker = start(
        "set application_name='nc_consent_revoker'; begin;"
        + prefix
        + "select public.revoke_owner_processing('"
        + owner
        + "',"
        + cid
        + ",'Revocation precedes worker commit'); select pg_sleep(3); commit;"
    )
    try:
        sleeping("nc_consent_revoker")
        denied = command(
            *psql,
            input=prefix
            + "select public.worker_tick_optin("
            + args
            + ",'completed',100,'Must not commit after revoke');",
        )
        assert denied.returncode != 0 and "Processing consent inactive" in denied.stderr
        revoker.communicate(timeout=10)
        assert revoker.returncode == 0
        assert (
            sql(
                "select status||':'||progress::text from public.processing_jobs where id='"
                + jid
                + "';"
            ).strip()
            == "queued:0"
        )
    finally:
        if revoker.poll() is None:
            revoker.kill()
            revoker.wait()
    return {
        "inflight_transaction_finishes_before_revoke_commits": True,
        "transaction_waiting_behind_revoke_cannot_commit": True,
    }


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

    def command(*args, **kwargs):
        return subprocess.run(
            docker + list(args), env=env, capture_output=True, text=True, **kwargs
        )

    cache = ROOT.parent / ".cache/pgmq-1.8.1"
    for name, (_, sha) in PGMQ_FILES.items():
        assert hashlib.sha256((cache / name).read_bytes()).hexdigest() == sha, (
            "Use the existing verified PGMQ cache"
        )
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
    name = "nc-consent-test-" + uuid4().hex[:10]
    try:
        command(
            "run",
            "--rm",
            "-d",
            "--network=none",
            "--cpus=1",
            "--memory=768m",
            "--pids-limit=256",
            "--name",
            name,
            "--tmpfs",
            "/var/lib/postgresql/data:rw,size=512m",
            "-e",
            "POSTGRES_HOST_AUTH_METHOD=trust",
            "-e",
            "POSTGRES_DB=consent_test",
            IMAGE,
        ).check_returncode()
        for _ in range(100):
            if (
                command(
                    "exec", name, "pg_isready", "-U", "postgres", "-d", "consent_test"
                ).returncode
                == 0
            ):
                break
            time.sleep(0.2)
        else:
            raise RuntimeError("Local PostgreSQL did not become ready")
        for src, dst in [
            ("pgmq.control", "pgmq.control"),
            ("pgmq.sql", "pgmq--1.8.1.sql"),
        ]:
            command(
                "cp",
                str(cache / src),
                name + ":/usr/share/postgresql/17/extension/" + dst,
            ).check_returncode()
            command(
                "exec",
                name,
                "chmod",
                "0644",
                "/usr/share/postgresql/17/extension/" + dst,
            ).check_returncode()
        sql = (
            fixture
            + "\n"
            + "".join(
                p.read_text() + "\n"
                for p in sorted((ROOT / "supabase/migrations").glob("*.sql"))
            )
        )
        sql += (
            ROOT / "docs/proposals/continuous-worker-consent.sql"
        ).read_text() + "\n"
        sql += (ROOT / "worker/tests/sql/continuous_consent.sql").read_text()
        result = command(
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
            "consent_test",
            input=sql,
        )
        if result.returncode:
            print(result.stdout[-2500:])
            print(result.stderr[-7000:])
            result.check_returncode()
        concurrency = concurrency_checks(command, docker, env, name)
        report = {
            "passed": True,
            "database": "disposable local PostgreSQL 17 and pinned PGMQ",
            "hosted_database_changed": False,
            "continuous_worker_started": False,
            "model_inference_run": False,
            "proposal_sha256": hashlib.sha256(
                (ROOT / "docs/proposals/continuous-worker-consent.sql").read_bytes()
            ).hexdigest(),
            "sql_assertions_output": [
                line.strip() for line in result.stdout.splitlines() if "PASS:" in line
            ],
            "revocation_concurrency": concurrency,
        }
        (ROOT / "test-results/continuous-worker-sql.json").write_text(
            json.dumps(report, indent=2) + "\n"
        )
        print(json.dumps(report, indent=2))
    finally:
        command("rm", "-f", name)


if __name__ == "__main__":
    main()
