"""Test the narrowly scoped migration in an ephemeral, network-isolated Postgres.

Uses no cloud credentials and changes no hosted database. Requires the managed
local Docker socket. The pinned official image is pulled normally if missing.
"""

import json
import os
import subprocess
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMAGE = (
    "postgres@sha256:ff87138949ad9a46f32ff23bd6852b52ce024a13dffe9b4087be98292cdd3b4f"
)
MIGRATION = ROOT / "supabase/migrations/20261108013140_worker_heartbeat_singleton.sql"


def main():
    env = os.environ.copy()
    for name in (
        "DOCKER_HOST",
        "DOCKER_CONTEXT",
        "DOCKER_TLS",
        "DOCKER_TLS_VERIFY",
        "DOCKER_CERT_PATH",
    ):
        env.pop(name, None)
    docker = ["docker", "--host=unix:///var/run/docker.sock"]

    def command(*args, **kwargs):
        return subprocess.run(
            docker + list(args), env=env, capture_output=True, text=True, **kwargs
        )

    initial = (
        ROOT / "supabase/migrations/20261107180530_clipping_pipeline.sql"
    ).read_text()

    def original_function(name):
        start = initial.index("create function " + name + "(")
        end = initial.index("$$;", start) + 3
        return initial[start:end]

    fixture = """
create role anon;
create role authenticated;
create role service_role;
create schema auth;
create schema private;
revoke all on schema private from public;
grant usage on schema auth to anon, authenticated, service_role;
grant usage on schema private to authenticated, service_role;
create function auth.jwt() returns jsonb language sql stable as $$
  select coalesce(nullif(current_setting('request.jwt.claims', true), ''), '{}')::jsonb;
$$;
-- The false sentinel is local only. The hosted singleton CHECK(id) is unchanged.
create table private.worker_health (
  id boolean primary key, heartbeat_at timestamptz,
  ai_ready boolean not null default false, detail text
);
insert into private.worker_health(id) values (true), (false);
"""
    fixture += original_function("private.require_worker") + "\n"
    fixture += original_function("private.worker_heartbeat") + "\n"
    fixture += original_function("public.worker_heartbeat") + "\n"
    fixture += """
revoke all on function private.require_worker() from public, anon, authenticated;
revoke all on function private.worker_heartbeat(boolean,text) from public, anon, authenticated;
revoke all on function public.worker_heartbeat(boolean,text) from public, anon, authenticated;
grant execute on function private.worker_heartbeat(boolean,text) to service_role;
grant execute on function public.worker_heartbeat(boolean,text) to service_role;
comment on function private.worker_heartbeat(boolean,text) is 'Local preservation sentinel';

-- Demonstrate the old unbounded update addresses both rows, then roll it back.
begin;
select set_config('request.jwt.claims', '{"role":"service_role"}', true);
set local role service_role;
select public.worker_heartbeat(false, 'Old unbounded update');
reset role;
do $$ begin
  if (select count(*) from private.worker_health where heartbeat_at is not null) <> 2 then
    raise exception 'The baseline did not expose the unbounded update';
  end if;
end $$;
rollback;

create temporary view heartbeat_metadata as
select oid, proowner, proacl, prosecdef, proconfig, proargtypes::text,
       proargnames, prorettype, proretset, proisstrict, provolatile,
       proparallel, prolang, procost, prorows,
       obj_description(oid, 'pg_proc') as comment
from pg_proc where oid = 'private.worker_heartbeat(boolean,text)'::regprocedure;
create temporary table metadata_before as select to_jsonb(m) as value from heartbeat_metadata m;
"""
    checks = """
do $$ begin
  if (select value from metadata_before) is distinct from
     (select to_jsonb(m) from heartbeat_metadata m) then
    raise exception 'Function identity, ownership, ACL or execution settings changed';
  end if;
end $$;

begin;
select set_config('request.jwt.claims', '{"role":"service_role"}', true);
set local role service_role;
select public.worker_heartbeat(false, 'Repaired scoped update');
reset role;
do $$ begin
  if (select heartbeat_at from private.worker_health where id = true) is null
     or (select heartbeat_at from private.worker_health where id = false) is not null then
    raise exception 'Heartbeat updated a row other than the intended singleton';
  end if;
end $$;
rollback;

-- Even an EXECUTE-authorized SQL role needs the worker JWT role assertion.
begin;
select set_config('request.jwt.claims', '{"role":"authenticated"}', true);
set local role service_role;
do $$ begin
  begin
    perform public.worker_heartbeat(false, 'Invalid worker role claim');
    raise exception 'Worker authorization guard was bypassed';
  exception when raise_exception then
    if sqlerrm <> 'Worker authorization required' then raise; end if;
  end;
end $$;
rollback;
"""
    name = "nc-heartbeat-test-" + uuid.uuid4().hex[:12]
    try:
        launch = command(
            "run",
            "--rm",
            "-d",
            "--network=none",
            "--name",
            name,
            "--tmpfs",
            "/var/lib/postgresql/data:rw,size=256m",
            "-e",
            "POSTGRES_HOST_AUTH_METHOD=trust",
            "-e",
            "POSTGRES_DB=heartbeat_test",
            IMAGE,
        )
        launch.check_returncode()
        for _ in range(100):
            if (
                command(
                    "exec", name, "pg_isready", "-U", "postgres", "-d", "heartbeat_test"
                ).returncode
                == 0
            ):
                break
            time.sleep(0.2)
        else:
            raise RuntimeError("Temporary Postgres did not become ready")
        # Reapplying is intentional: CREATE OR REPLACE must also be repeatable.
        sql = fixture + MIGRATION.read_text() + "\n" + MIGRATION.read_text() + checks
        sql += (ROOT / "supabase/tests/worker_heartbeat.sql").read_text()
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
            "heartbeat_test",
            input=sql,
        )
        if result.returncode:
            print(result.stdout)
            print(result.stderr)
            result.check_returncode()
        version = command(
            "exec",
            name,
            "psql",
            "-X",
            "-At",
            "-U",
            "postgres",
            "-d",
            "heartbeat_test",
            "-c",
            "select version()",
        ).stdout.strip()
        report = {
            "passed": True,
            "hosted_database_changed": False,
            "image": IMAGE,
            "postgres": version,
            "checks": [
                "old unbounded update reproduced locally",
                "new predicate addresses only id=true",
                "function OID/owner/ACL/signature/security/search_path/execution attributes/comment preserved",
                "migration repeatable",
                "service-role invocation succeeds and detail is bounded",
                "worker JWT authorization guard preserved",
                "anonymous and browser roles denied",
            ],
        }
        path = ROOT / "test-results/heartbeat-migration-local.json"
        path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report, indent=2))
    finally:
        command("rm", "-f", name)


if __name__ == "__main__":
    main()
