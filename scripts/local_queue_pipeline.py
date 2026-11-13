"""Real worker/model/PGMQ/FFmpeg test with a disposable SQL + file adapter.

Called only by test_local_worker_sql.py --pipeline. This exercises the normal
Worker.once path and actual RPCs, NOT hosted Supabase HTTP, Auth or browser E2E.
No highlights, completed jobs, or provider usage are inserted by this harness.
"""

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "worker"))


def literal(value):
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    tag = "$nc_" + uuid.uuid4().hex + "$"
    if isinstance(value, (dict, list)):
        return tag + json.dumps(value) + tag + "::jsonb"
    return tag + str(value) + tag


def identifier(value):
    assert re.fullmatch("[a-z_]+", value)
    return '"' + value + '"'


def run_pipeline(cmd, container):
    from noetharaclipz.config import Settings
    from noetharaclipz.local_provider import LocalProvider
    from noetharaclipz.models import Edit
    from noetharaclipz.runner import Worker

    assert container.startswith("nc-local-worker-")

    def sql(statement, role="postgres", owner=None):
        claims = {"role": role}
        if owner:
            claims["sub"] = owner
        c = cmd(
            "exec",
            "-i",
            container,
            "psql",
            "-X",
            "-qAt",
            "-v",
            "ON_ERROR_STOP=1",
            "-U",
            "postgres",
            "-d",
            "local_worker_test",
            input="begin; set local role "
            + identifier(role)
            + "; set local request.jwt.claims="
            + literal(json.dumps(claims))
            + ";"
            + statement
            + ";commit;",
        )
        if c.returncode:
            raise RuntimeError(c.stderr[-2000:])
        return json.loads(c.stdout.strip()) if c.stdout.strip() else None

    def rpc(name, role="service_role", auth_owner=None, **params):
        args = ",".join(identifier(k) + "=>" + literal(v) for k, v in params.items())
        return sql(
            "select coalesce(to_jsonb(public."
            + identifier(name)
            + "("
            + args
            + ")), 'null'::jsonb)",
            role,
            auth_owner,
        )

    source = Path(os.environ["NC_SAMPLE_VIDEO"]).resolve(strict=True)
    owner, other = str(uuid.uuid4()), str(uuid.uuid4())
    sql(
        f"insert into auth.users(id,email) values({literal(owner)},'local-owner@example.com'),({literal(other)},'protected-owner@example.com')"
    )
    protected = rpc(
        "prepare_upload",
        role="authenticated",
        auth_owner=other,
        request_id=str(uuid.uuid4()),
        filename="protected.mp4",
        mime_type="video/mp4",
        byte_size=1000,
        instructions="Do not consume",
    )
    sql(
        "insert into storage.objects(bucket_id,name,metadata) values('source-videos',"
        + literal(protected["path"])
        + ",'{}'::jsonb||jsonb_build_object('size',1000))"
    )
    protected_jid = rpc(
        "finalize_upload",
        role="authenticated",
        auth_owner=other,
        pid=protected["project_id"],
    )

    def snapshot():
        return sql(
            "select jsonb_build_object('job',to_jsonb(j),'message',to_jsonb(q)) from public.processing_jobs j join pgmq.q_noetharaclipz q on q.msg_id=j.message_id where j.id="
            + literal(protected_jid)
        )

    before = snapshot()
    report = {
        "scope": "Disposable real PG/PGMQ + normal worker, local file transport; NOT hosted/browser acceptance",
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "hosted_inference": False,
        "checks": {},
    }
    with tempfile.TemporaryDirectory(prefix="nc-queue-media-") as folder:
        root = Path(folder)

        class Backend:
            base = "local-adapter://disposable"

            def __init__(self):
                self.client = self

            def rpc(self, name, **params):
                assert name != "worker_claim", "Global claims forbidden in this test"
                assert name != "reserve_inference", (
                    "Gemini usage forbidden in local mode"
                )
                return rpc(name, **params)

            def rows(self, table, **filters):
                terms = []
                for k, v in filters.items():
                    assert v.startswith("eq.")
                    terms.append(identifier(k) + "=" + literal(v[3:]))
                return sql(
                    "select coalesce(jsonb_agg(to_jsonb(t)),'[]') from public."
                    + identifier(table)
                    + " t where "
                    + " and ".join(terms),
                    "service_role",
                )

            def update(self, table, values, **filters):
                assignments = ",".join(
                    identifier(k)
                    + "=(jsonb_populate_record(null::public."
                    + identifier(table)
                    + ","
                    + literal(values)
                    + "))."
                    + identifier(k)
                    for k in values
                )
                where = " and ".join(
                    identifier(k) + "=" + literal(v[3:]) for k, v in filters.items()
                )
                sql(
                    "update public."
                    + identifier(table)
                    + " set "
                    + assignments
                    + " where "
                    + where,
                    "service_role",
                )

            def post(self, url, json):
                # Actual checkpoint insert, using SQL instead of PostgREST transport.
                assert url == self.base + "/rest/v1/analysis_artifacts"
                fields = ",".join(identifier(k) for k in json)
                values = ",".join(literal(v) for v in json.values())
                sql(
                    "insert into public.analysis_artifacts("
                    + fields
                    + ") values("
                    + values
                    + ")",
                    "service_role",
                )
                return self

            def raise_for_status(self):
                pass

            def download(self, bucket, path, dest):
                shutil.copyfile(root / bucket / path, dest)
                return dest.stat().st_size

            def upload(self, bucket, path, source, mime):
                dest = root / bucket / path
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, dest)
                dest.chmod(0o600)
                sql(
                    "insert into storage.objects(bucket_id,name,metadata) values("
                    + literal(bucket)
                    + ","
                    + literal(path)
                    + ","
                    + literal({"size": dest.stat().st_size})
                    + ") on conflict(bucket_id,name) do update set metadata=excluded.metadata"
                )

        backend = Backend()
        reservation = rpc(
            "prepare_upload",
            role="authenticated",
            auth_owner=owner,
            request_id=str(uuid.uuid4()),
            filename=source.name,
            mime_type="video/mp4",
            byte_size=source.stat().st_size,
            instructions="Find a spoken reaction with visible movement; preserve the whole speech.",
        )
        pid = reservation["project_id"]
        backend.upload("source-videos", reservation["path"], source, "video/mp4")
        jid = rpc("finalize_upload", role="authenticated", auth_owner=owner, pid=pid)
        assert (
            rpc("finalize_upload", role="authenticated", auth_owner=owner, pid=pid)
            == jid
        )
        settings = replace(
            Settings(),
            provider="local",
            scope_owner=owner,
            cache_dir=str(root / "cache"),
        )
        provider = LocalProvider(settings)
        started = time.monotonic()
        provider.preflight()
        worker = Worker(settings, backend=backend, provider=provider)
        assert worker.once()
        analysis_job = backend.rows("processing_jobs", id="eq." + jid)[0]
        assert analysis_job["status"] == "completed", analysis_job.get("error")
        highlights = backend.rows("highlights", project_id="eq." + pid)
        assert highlights and analysis_job["attempts"] == 1
        usage = backend.rows("provider_usage", project_id="eq." + pid)
        assert len(usage) == 1 and usage[0]["provider"] == "local-smolvlm2"
        assert not backend.rows(
            "highlights", project_id="eq." + protected["project_id"]
        )
        report["checks"]["actual_queue_analysis_and_truthful_usage"] = True
        report["analysis_seconds_including_model_load"] = round(
            time.monotonic() - started, 3
        )
        h = highlights[0]
        edit = Edit(
            start=min(h["start_time"] + 0.15, h["end_time"] - 0.5),
            end=h["end_time"],
            ratio="1:1",
        ).model_dump()
        cid = rpc(
            "save_clip", role="authenticated", auth_owner=owner, hid=h["id"], edit=edit
        )
        rjid = rpc(
            "export_clip",
            role="authenticated",
            auth_owner=owner,
            cid=cid,
            expected_revision=1,
        )
        assert (
            rpc(
                "export_clip",
                role="authenticated",
                auth_owner=owner,
                cid=cid,
                expected_revision=1,
            )
            == rjid
        )
        assert worker.once()
        rendered = backend.rows("processing_jobs", id="eq." + rjid)[0]
        assert rendered["status"] == "completed", rendered.get("error")
        output = root / "rendered-clips" / rendered["payload"]["output_path"]
        subprocess.run(
            ["ffmpeg", "-v", "error", "-i", str(output), "-f", "null", "-"],
            check=True,
            timeout=120,
        )
        probe = json.loads(
            subprocess.check_output(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-show_streams",
                    "-show_format",
                    "-of",
                    "json",
                    str(output),
                ]
            )
        )
        assert any(s["codec_name"] == "h264" for s in probe["streams"])
        assert (
            abs(float(probe["format"]["duration"]) - (edit["end"] - edit["start"]))
            < 0.25
        )
        saved = backend.rows("clips", id="eq." + cid)[0]
        assert saved["edit"] == edit and saved["render_status"] == "completed"
        assert (
            sql(
                "select coalesce(jsonb_agg(to_jsonb(t)),'[]') from public.clips t where id="
                + literal(cid),
                "authenticated",
                other,
            )
            == []
        )
        assert snapshot() == before
        assert worker.once() is False, "Scoped worker consumed protected message"
        assert snapshot() == before
        report["checks"].update(
            actual_queued_export_and_mp4_decode=True,
            saved_edit_and_render=True,
            cross_user_row_denial=True,
            protected_job_and_queue_message_identical=True,
            duplicate_finalize_and_export_prevented=True,
        )
        report["highlights"] = highlights
        report["analysis_cache"] = analysis_job["payload"].get("local_metrics")
        report["output"] = {
            "bytes": output.stat().st_size,
            "duration": probe["format"]["duration"],
            "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        }
        saved_output = ROOT / "test-results/local-queue-render.mp4"
        shutil.copyfile(output, saved_output)
    (ROOT / "test-results/local-queue-pipeline.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    print(json.dumps(report, indent=2), flush=True)
