"""Independent live transport/media check, explicitly NOT AI acceptance.

Creates two temporary confirmed QA accounts in the existing project, uploads
authorized footage through the real UI, and runs the actual worker. Inference
must remain disabled. A clearly labelled manual speech interval tests rendering,
private downloads, persistence and isolation. Removes its own remote test data.

Run with scripts/requirements-e2e.txt installed, worker/.venv prepared, the app
running, SUPABASE_URL/server credential bound, and NC_SAMPLE_VIDEO authorized.
"""

import hashlib
import json
import os
import secrets
import subprocess
import sys
import time
import uuid
from pathlib import Path

import httpx
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "worker"))

PUBLIC_KEY = "sb_publishable_wlXMNmobAj-bq_wKU7BduQ_FoKG6Eyk"


def main():
    from noetharaclipz.backend import Backend
    from noetharaclipz.config import Settings

    settings = Settings()
    settings.check_project()
    assert not settings.free_verified, (
        "This test requires the hosted inference gate to stay false"
    )
    sample = Path(os.environ["NC_SAMPLE_VIDEO"]).resolve(strict=True)
    base = os.getenv("NC_BASE_URL", "http://127.0.0.1:8080").rstrip("/")
    report_path = ROOT / "test-results/live-independent-pipeline.json"
    report = {
        "commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "ai_acceptance": False,
        "hosted_generation_requested": False,
        "selection_method": "MANUAL QA speech interval, NOT an AI-selected highlight",
        "source_sha256": hashlib.sha256(sample.read_bytes()).hexdigest(),
        "checks": {},
    }
    checks = report["checks"]
    backend = Backend(settings)
    users = []
    pid = None
    worker_process = None
    started = time.monotonic()

    def rpc(api, name, **body):
        response = api.post(settings.supabase_url + "/rest/v1/rpc/" + name, json=body)
        response.raise_for_status()
        return response.json() if response.content else None

    def rows(table, **params):
        return backend.rows(table, **params)

    def worker_once(expected_job):
        nonlocal worker_process
        # Keep job handling, real subprocesses and error recording in Worker.once.
        code = """
import os,time
from noetharaclipz.runner import Worker
w=Worker()
for _ in range(100):
    active=w.backend.rows('processing_jobs',select='id',status='not.in.(completed,failed,cancelled)')
    assert all(j['id']==os.environ['NC_EXPECTED_JOB'] for j in active), 'Unrelated active job; refusing queue consumption'
    if w.once(): break
    time.sleep(.2)
else: raise RuntimeError('Expected queue message was not available')
"""
        env = dict(
            os.environ, PYTHONPATH=str(ROOT / "worker"), NC_EXPECTED_JOB=expected_job
        )
        log_path = ROOT / "test-results/live-worker.log"
        with log_path.open("a") as log:
            worker_process = subprocess.Popen(
                [str(ROOT / "worker/.venv/bin/python"), "-c", code],
                cwd=ROOT,
                env=env,
                stdout=log,
                stderr=log,
            )
        deadline = time.monotonic() + 600
        while worker_process.poll() is None:
            if time.monotonic() > deadline:
                worker_process.terminate()
                worker_process.wait(timeout=60)
                raise TimeoutError("Independent worker exceeded ten minutes")
            time.sleep(2)
        assert worker_process.returncode == 0, (
            "Worker process failed; inspect redacted live-worker.log"
        )
        return rows("processing_jobs", id="eq." + expected_job)[0]

    try:
        assert not rows(
            "processing_jobs", select="id", status="not.in.(completed,failed,cancelled)"
        ), "Unrelated jobs are active; refusing to consume their queue"
        for _ in range(2):
            email = "nc-runtime-" + uuid.uuid4().hex + "@example.com"
            password = secrets.token_urlsafe(32)
            response = backend.client.post(
                backend.base + "/auth/v1/admin/users",
                json={
                    "email": email,
                    "password": password,
                    "email_confirm": True,
                    "user_metadata": {"display_name": "Temporary runtime verification"},
                },
            )
            response.raise_for_status()
            users.append(
                {"id": response.json()["id"], "email": email, "password": password}
            )
        report["temporary_user_ids"] = [u["id"] for u in users]
        apis = []
        for user in users:
            api = httpx.Client(timeout=60, headers={"apikey": PUBLIC_KEY})
            response = api.post(
                backend.base + "/auth/v1/token?grant_type=password",
                json={"email": user["email"], "password": user["password"]},
            )
            response.raise_for_status()
            api.headers["Authorization"] = "Bearer " + response.json()["access_token"]
            apis.append(api)
        owner, other = apis
        try:
            backend.rpc(
                "worker_heartbeat",
                ai_ready=False,
                detail="Independent QA; hosted AI disabled",
            )
            checks["authenticated_worker_health"] = True
        except RuntimeError as exc:
            if "UPDATE requires a WHERE clause" not in str(exc):
                raise
            checks["authenticated_worker_health"] = False
            report["known_defects"] = [
                "worker_heartbeat rejected by database safe-update guard: UPDATE requires a WHERE clause (21000)"
            ]
        health = rpc(owner, "pipeline_health")
        assert not health["ai_ready"]
        report["pipeline_health"] = health
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                executable_path=os.getenv("CHROMIUM_PATH", "/usr/bin/chromium"),
            )
            page = browser.new_page(
                viewport={"width": 1440, "height": 1000}, accept_downloads=True
            )
            page.set_default_timeout(30000)
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(base + "/login", wait_until="networkidle")
            page.get_by_label("Email", exact=True).fill(users[0]["email"])
            page.get_by_label("Password", exact=True).fill(users[0]["password"])
            page.get_by_role("button", name="Sign in", exact=True).click()
            page.wait_for_url("**/library")
            checks["browser_login"] = True
            page.goto(base + "/", wait_until="networkidle")
            page.locator("input[type=file]").set_input_files(str(sample))
            page.locator("textarea").fill(
                "Independent runtime QA on authorized Sintel footage; no hosted AI authorized"
            )
            page.get_by_role("checkbox").check()
            page.get_by_role("button", name="Generate", exact=True).click()
            page.wait_for_url("**/project/*", timeout=60000)
            pid = page.url.rsplit("/", 1)[-1]
            report["project_id"] = pid
            checks["browser_resumable_upload"] = True
            analysis_job = rows(
                "processing_jobs", project_id="eq." + pid, kind="eq.analysis"
            )[0]
            assert rpc(owner, "finalize_upload", pid=pid) == analysis_job["id"]
            checks["upload_finalize_idempotent"] = True
            step = time.monotonic()
            finished = worker_once(analysis_job["id"])
            report["preprocess_transcribe_upload_seconds"] = round(
                time.monotonic() - step, 2
            )
            assert finished["status"] == "failed" and "FREE tier" in finished["error"]
            artifact = rows("analysis_artifacts", project_id="eq." + pid)[0]
            assert (
                artifact["transcript"]
                and artifact["scenes"]
                and artifact["waveform"]
                and artifact["frame_paths"]
            )
            assert not rows("provider_usage", project_id="eq." + pid)
            assert not rows("highlights", project_id="eq." + pid)
            checks["real_worker_claim_preprocessing_transcription_checkpoint"] = True
            checks["false_free_tier_gate_prevents_generation_and_highlights"] = True
            report["media_evidence"] = {
                "transcript": artifact["transcript"],
                "scene_count": len(artifact["scenes"]),
                "frame_count": len(artifact["frame_paths"]),
                "audio_event_count": len(artifact["audio_events"]),
            }
            speech = artifact["transcript"][0]
            start, end = max(0, speech["start"] - 1), speech["end"] + 1
            response = backend.client.post(
                backend.base + "/rest/v1/highlights",
                headers={"Prefer": "return=representation"},
                json={
                    "project_id": pid,
                    "start_time": start,
                    "end_time": end,
                    "title": "MANUAL QA speech interval — NOT AI-selected",
                    "category": "Other",
                    "score": 0,
                    "explanation": "Manual speech interval for independent worker/storage testing; not AI acceptance",
                    "evidence": {"manual_qa": True, "speech": speech["text"]},
                },
            )
            response.raise_for_status()
            highlight = response.json()[0]
            page.reload(wait_until="networkidle")
            page.get_by_role("button", name="Select clip", exact=True).first.click()
            page.get_by_role("link", name="Edit", exact=True).click()
            page.wait_for_url("**/editor/**")
            page.get_by_role("button", name="Play", exact=True).click()
            page.wait_for_function(
                "document.querySelector('video')?.readyState>=2 && document.querySelector('video').currentTime>0"
            )
            checks["browser_actual_video_playback"] = True
            # Keyboard interaction changes the real trim through the existing UI.
            trim = page.locator('[aria-label="Trim"] [role="slider"]').first
            trim.focus()
            trim.press("ArrowRight")
            changed_start = float(trim.get_attribute("aria-valuenow"))
            assert changed_start > start
            page.get_by_role("button", name="Save", exact=True).click()
            page.get_by_text("Edit saved", exact=True).wait_for()
            clip = rows(
                "clips", project_id="eq." + pid, highlight_id="eq." + highlight["id"]
            )[0]
            assert abs(clip["edit"]["start"] - changed_start) < 0.001
            report["saved_edit"] = clip["edit"]
            page.reload(wait_until="networkidle")
            page.get_by_role("button", name="Export", exact=True).wait_for()
            assert (
                abs(
                    float(
                        page.locator(
                            '[aria-label="Trim"] [role="slider"]'
                        ).first.get_attribute("aria-valuenow")
                    )
                    - clip["edit"]["start"]
                )
                < 0.01
            )
            checks["trim_changes_and_persists_after_refresh"] = True
            page.get_by_role("button", name="Export", exact=True).click()
            page.get_by_role("dialog").get_by_role(
                "button", name="Export", exact=True
            ).click()
            deadline = time.monotonic() + 30
            while True:
                render_jobs = rows(
                    "processing_jobs", project_id="eq." + pid, kind="eq.render"
                )
                if render_jobs:
                    break
                assert time.monotonic() < deadline
                time.sleep(0.5)
            render_job = render_jobs[0]
            assert (
                rpc(
                    owner,
                    "export_clip",
                    cid=clip["id"],
                    expected_revision=clip["revision"],
                )
                == render_job["id"]
            )
            checks["render_submission_idempotent"] = True
            step = time.monotonic()
            rendered = worker_once(render_job["id"])
            assert rendered["status"] == "completed", "Actual render failed: " + (
                rendered.get("error") or "unknown"
            )
            report["render_upload_commit_seconds"] = round(time.monotonic() - step, 2)
            checks["queued_render_private_storage_completion"] = True
            page.get_by_role("button", name="Download MP4", exact=True).wait_for(
                timeout=30000
            )
            output = ROOT / "test-results/live-manual-qa-download.mp4"
            with page.expect_download() as download:
                page.get_by_role("button", name="Download MP4", exact=True).click()
            download.value.save_as(str(output))
            metadata = json.loads(
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
            subprocess.run(
                ["ffmpeg", "-v", "error", "-i", str(output), "-f", "null", "-"],
                check=True,
                timeout=120,
            )
            codecs = [s["codec_name"] for s in metadata["streams"]]
            assert "h264" in codecs and "aac" in codecs
            duration = float(metadata["format"]["duration"])
            assert abs(duration - (clip["edit"]["end"] - clip["edit"]["start"])) < 0.15
            report["download"] = {
                "bytes": output.stat().st_size,
                "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
                "duration": duration,
                "codecs": codecs,
                "path": str(output.relative_to(ROOT)),
            }
            checks["browser_authenticated_mp4_download_and_full_decode"] = True
            path = rendered["payload"]["output_path"]
            response = other.get(
                backend.base + "/rest/v1/projects", params={"id": "eq." + pid}
            )
            assert response.is_success and response.json() == []
            for table in (
                "videos",
                "highlights",
                "clips",
                "processing_jobs",
                "analysis_artifacts",
                "conversation_messages",
                "provider_usage",
            ):
                response = other.get(
                    backend.base + "/rest/v1/" + table,
                    params={"project_id": "eq." + pid},
                )
                assert response.is_success and response.json() == [], table
            denied = other.post(
                backend.base + "/storage/v1/object/sign/rendered-clips/" + path,
                json={"expiresIn": 60},
            )
            assert not denied.is_success
            denied = other.get(
                backend.base + "/storage/v1/object/authenticated/rendered-clips/" + path
            )
            assert not denied.is_success
            with httpx.Client(timeout=30, headers={"apikey": PUBLIC_KEY}) as anonymous:
                denied = anonymous.get(
                    backend.base + "/storage/v1/object/public/rendered-clips/" + path
                )
                assert not denied.is_success
            checks["cross_user_rows_signing_download_and_public_access_denied"] = True
            denied = other.post(
                backend.base + "/rest/v1/rpc/export_clip",
                json={"cid": clip["id"], "expected_revision": clip["revision"]},
            )
            assert not denied.is_success
            denied = owner.post(backend.base + "/rest/v1/rpc/worker_claim", json={})
            assert not denied.is_success
            denied = owner.patch(
                backend.base + "/rest/v1/processing_jobs",
                params={"id": "eq." + rendered["id"]},
                json={"status": "completed", "payload": {"output_path": "forged"}},
            )
            assert not denied.is_success
            checks[
                "cross_user_export_forged_completion_and_browser_worker_access_denied"
            ] = True
            source_path = rows("videos", project_id="eq." + pid)[0]["source_path"]
            denied = owner.put(
                backend.base + "/storage/v1/object/source-videos/" + source_path,
                content=b"overwrite must fail",
                headers={"Content-Type": "video/mp4"},
            )
            assert not denied.is_success
            denied = owner.post(
                backend.base
                + "/storage/v1/object/rendered-clips/"
                + users[0]["id"]
                + "/"
                + pid
                + "/forged.mp4",
                content=b"forged export",
                headers={"Content-Type": "video/mp4"},
            )
            assert not denied.is_success
            denied = other.post(
                backend.base + "/rest/v1/rpc/finalize_upload", json={"pid": pid}
            )
            assert not denied.is_success
            checks[
                "source_overwrite_browser_output_upload_and_cross_user_finalize_denied"
            ] = True
            for width in (390, 768, 1440):
                page.set_viewport_size({"width": width, "height": 1000})
                page.wait_for_timeout(200)
                assert page.evaluate(
                    "document.documentElement.scrollWidth <= window.innerWidth"
                ), f"Overflow at {width}px"
            checks["editor_layouts_390_768_1440_no_overflow"] = True
            page.set_viewport_size({"width": 1440, "height": 1000})
            page.goto(base + "/brand-kit", wait_until="networkidle")
            page.get_by_role("button", name="Color 3", exact=True).click()
            deadline = time.monotonic() + 20
            while True:
                brands = rows("brand_settings", owner_id="eq." + users[0]["id"])
                if brands and brands[0]["settings"].get("caption_color") == "#22C55E":
                    break
                assert time.monotonic() < deadline
                time.sleep(0.2)
            page.reload(wait_until="networkidle")
            assert "ring-2" in page.get_by_role(
                "button", name="Color 3", exact=True
            ).get_attribute("class")
            checks["brand_defaults_persist_after_refresh"] = True
            page.goto(base + "/project/" + pid, wait_until="networkidle")
            page.get_by_role("button", name="Delete project", exact=True).click()
            page.wait_for_url("**/library")
            assert rows("projects", id="eq." + pid)[0]["deleted_at"] is not None
            page.goto(base + "/trash", wait_until="networkidle")
            page.get_by_role("button", name="Restore", exact=True).click()
            page.get_by_text("Restored", exact=True).wait_for()
            page.reload(wait_until="networkidle")
            assert rows("projects", id="eq." + pid)[0]["deleted_at"] is None
            checks["project_delete_restore_persistence"] = True
            page.goto(base + "/settings", wait_until="networkidle")
            page.get_by_role("button", name="Sign out", exact=True).click()
            page.wait_for_url(base + "/")
            page.goto(base + "/library", wait_until="networkidle")
            page.wait_for_url("**/login")
            checks["signout_and_protected_route_redirect"] = True
            page.goto(base + "/auth/callback", wait_until="networkidle")
            assert "missing its code" in page.get_by_role("status").inner_text()
            page.goto(
                base + "/auth/callback?code=invalid-runtime-qa-code",
                wait_until="networkidle",
            )
            page.wait_for_function(
                "!document.querySelector('[role=status]').textContent.includes('Completing')"
            )
            assert page.get_by_role("status").inner_text()
            checks["missing_and_invalid_auth_callback_handled"] = True
            report["unhandled_browser_errors"] = errors
            assert not errors
            browser.close()
        for api in apis:
            api.close()
        report["status"] = (
            "passed_independent_media_with_health_defect"
            if not checks["authenticated_worker_health"]
            else "passed_independent_pipeline_only"
        )
    finally:
        if worker_process and worker_process.poll() is None:
            worker_process.terminate()
            worker_process.wait(timeout=60)
        cleanup = []
        for user in users:
            try:
                projects = rows("projects", owner_id="eq." + user["id"])
                for project in projects:
                    for bucket in (
                        "source-videos",
                        "thumbnails",
                        "processing-artifacts",
                        "rendered-clips",
                    ):
                        backend.remove_prefix(
                            bucket, user["id"] + "/" + project["id"] + "/"
                        )
                    response = backend.client.delete(
                        backend.base + "/rest/v1/projects",
                        params={"id": "eq." + project["id"]},
                    )
                    response.raise_for_status()
                response = backend.client.delete(
                    backend.base + "/auth/v1/admin/users/" + user["id"]
                )
                response.raise_for_status()
                cleanup.append({"user_id": user["id"], "removed": True})
            except Exception as exc:
                cleanup.append(
                    {
                        "user_id": user["id"],
                        "removed": False,
                        "error_type": type(exc).__name__,
                    }
                )
        report["cleanup"] = cleanup
        report["elapsed_seconds"] = round(time.monotonic() - started, 2)
        report.setdefault("status", "failed")
        report_path.parent.mkdir(exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report, indent=2), flush=True)
    assert all(entry["removed"] for entry in report["cleanup"]), (
        "Remote QA cleanup is incomplete"
    )
    assert checks["authenticated_worker_health"], (
        "Independent media passed; database heartbeat defect remains"
    )


if __name__ == "__main__":
    main()
