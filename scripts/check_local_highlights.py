"""Isolated automatic-local-analysis → existing editor → real private download.

Explicit test runner, not shared-queue acceptance. Only temporary QA rows/files
are written. Completed render audit rows are recorded after actual CPU rendering
and object validation, without creating or claiming pgmq messages.
"""

import argparse
import hashlib
import json
import os
import secrets
import subprocess
import sys
import uuid
from pathlib import Path
import httpx
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "worker"))
PUBLIC = "sb_publishable_wlXMNmobAj-bq_wKU7BduQ_FoKG6Eyk"


def main():
    from noetharaclipz.backend import Backend
    from noetharaclipz.config import Settings
    from noetharaclipz.local_detector import MODEL, REVISION
    from noetharaclipz.models import Candidate, Edit

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("analysis", type=Path)
    parser.add_argument(
        "--attribution", default="", help="Credit/licence to embed in the sample export"
    )
    args = parser.parse_args()
    directory = args.analysis.resolve()
    source = args.source.resolve(strict=True)
    result = json.loads((directory / "analysis.json").read_text())
    h = Candidate.model_validate(result["highlights"][0])
    assert result["source_hash"] == hashlib.sha256(source.read_bytes()).hexdigest()
    assert (
        result["model"] == MODEL
        and result["revision"] == REVISION
        and not result["hosted_inference"]
    )
    b = Backend(Settings())
    assert not Settings().free_verified
    snapshot = b.rows("processing_jobs", status="not.in.(completed,failed,cancelled)")
    report = {
        "scope": "isolated explicit local runner; shared queue untouched",
        "model": MODEL,
        "revision": REVISION,
        "automatic_highlight": h.model_dump(),
        "checks": {},
        "hosted_inference": False,
    }
    uid = pid = None

    def insert(table, body):
        r = b.client.post(
            b.base + "/rest/v1/" + table,
            json=body,
            headers={"Prefer": "return=representation"},
        )
        r.raise_for_status()
        return r.json()[0]

    try:
        email = "nc-local-" + uuid.uuid4().hex + "@example.com"
        password = secrets.token_urlsafe(32)
        r = b.client.post(
            b.base + "/auth/v1/admin/users",
            json={"email": email, "password": password, "email_confirm": True},
        )
        r.raise_for_status()
        uid = r.json()["id"]
        with httpx.Client(timeout=60, headers={"apikey": PUBLIC}) as user:
            r = user.post(
                b.base + "/auth/v1/token?grant_type=password",
                json={"email": email, "password": password},
            )
            r.raise_for_status()
            user.headers["Authorization"] = "Bearer " + r.json()["access_token"]
            r = user.post(
                b.base + "/rest/v1/rpc/prepare_upload",
                json={
                    "request_id": str(uuid.uuid4()),
                    "filename": source.name,
                    "mime_type": "video/mp4",
                    "byte_size": source.stat().st_size,
                    "instructions": result["prompt"],
                },
            )
            r.raise_for_status()
            reservation = r.json()
            pid = reservation["project_id"]
            prefix = uid + "/" + pid + "/"
            b.upload("source-videos", reservation["path"], source, "video/mp4")
            b.upload(
                "source-videos",
                prefix + "playback.mp4",
                directory / "playback.mp4",
                "video/mp4",
            )
            b.upload(
                "thumbnails",
                prefix + "thumbnail.jpg",
                directory / "thumbnail.jpg",
                "image/jpeg",
            )
            frames = []
            for frame in result["frames"]:
                path = prefix + Path(frame["file"]).name
                b.upload("thumbnails", path, directory / frame["file"], "image/jpeg")
                frames.append({"time": frame["time"], "path": path})
            b.update(
                "videos",
                {
                    **result["metadata"],
                    "status": "ready",
                    "playback_path": prefix + "playback.mp4",
                    "thumbnail_path": prefix + "thumbnail.jpg",
                    "source_hash": result["source_hash"],
                },
                project_id="eq." + pid,
            )
            insert(
                "analysis_artifacts",
                {
                    "project_id": pid,
                    "provider": "local-smolvlm2",
                    "model": MODEL + "@" + REVISION,
                    "summary": "Local automatic selection: "
                    + result["raw_visual_observation"],
                    "transcript": result["transcript"],
                    "scenes": result["scenes"],
                    "audio_events": result["audio_events"],
                    "waveform": result["waveform"],
                    "frame_paths": frames,
                    "warnings": [
                        "Experimental local-model observations require review; not calibrated highlight quality"
                    ],
                },
            )
            highlight = insert(
                "highlights",
                {
                    "project_id": pid,
                    "start_time": h.start,
                    "end_time": h.end,
                    "title": h.title,
                    "category": h.category,
                    "score": h.score,
                    "explanation": h.explanation,
                    "evidence": {
                        "visual": h.visual_evidence,
                        "provider": "local-smolvlm2",
                        "decision": result["decision"],
                        "raw_visual_observation": result["raw_visual_observation"],
                    },
                },
            )
            b.update("projects", {"status": "ready"}, id="eq." + pid)
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=True, executable_path="/usr/bin/chromium"
                )
                page = browser.new_page(
                    viewport={"width": 1440, "height": 1000}, accept_downloads=True
                )
                page.set_default_timeout(30000)
                errors = []
                page.on("pageerror", lambda e: errors.append(str(e)))
                base = os.getenv("NC_BASE_URL", "http://127.0.0.1:8080")
                page.goto(base + "/login", wait_until="networkidle")
                page.get_by_label("Email", exact=True).fill(email)
                page.get_by_label("Password", exact=True).fill(password)
                page.get_by_role("button", name="Sign in", exact=True).click()
                page.wait_for_url("**/library")
                page.goto(base + "/project/" + pid, wait_until="networkidle")
                page.get_by_role("button", name="Select clip", exact=True).first.click()
                page.get_by_role("link", name="Edit", exact=True).click()
                page.wait_for_url("**/editor/**")
                page.wait_for_function("document.querySelector('video')?.readyState>=2")
                initial_time = page.locator("video").evaluate("v => v.currentTime")
                page.get_by_role("button", name="Play", exact=True).click()
                try:
                    page.wait_for_function(
                        "start => { const v=document.querySelector('video'); return v && !v.paused && v.currentTime > start + .1; }",
                        arg=initial_time,
                    )
                except Exception:
                    report["playback_diagnostic"] = page.locator("video").evaluate(
                        "v => ({time:v.currentTime,paused:v.paused,readyState:v.readyState,networkState:v.networkState,error:v.error?.code,duration:v.duration,initial:0})"
                    )
                    report["playback_diagnostic"]["initial"] = initial_time
                    report["player_status"] = page.get_by_role(
                        "status"
                    ).all_text_contents()
                    raise
                trim = page.locator('[aria-label="Trim"] [role="slider"]').first
                trim.focus()
                trim.press("ArrowRight")
                changed = float(trim.get_attribute("aria-valuenow"))
                assert changed > h.start
                page.get_by_role("button", name="Frame", exact=True).click()
                page.get_by_role("button", name="1:1", exact=True).click()
                page.get_by_role("button", name="Save", exact=True).click()
                page.get_by_text("Edit saved", exact=True).wait_for()
                clip = b.rows("clips", highlight_id="eq." + highlight["id"])[0]
                edit = Edit.model_validate(clip["edit"])
                assert abs(edit.start - changed) < 0.001 and edit.ratio == "1:1"
                report["checks"]["real_automatic_highlight_edit_and_playback"] = True
                page.reload(wait_until="networkidle")
                assert (
                    abs(
                        float(
                            page.locator(
                                '[aria-label="Trim"] [role="slider"]'
                            ).first.get_attribute("aria-valuenow")
                        )
                        - edit.start
                    )
                    < 0.001
                )
                report["checks"]["saved_edit_persists"] = True
                editfile = directory / "saved-ui-edit.json"
                editfile.write_text(edit.model_dump_json(indent=2) + "\n")
                output = directory / "edited-automatic-highlight.mp4"
                code = "from pathlib import Path;from noetharaclipz.media import render;from noetharaclipz.models import Edit;import json,sys;render(Path(sys.argv[1]),Edit.model_validate_json(Path(sys.argv[2]).read_text()),json.loads(Path(sys.argv[3]).read_text())['transcript'],Path(sys.argv[4]))"
                subprocess.run(
                    [
                        str(ROOT / "worker/.venv/bin/python"),
                        "-c",
                        code,
                        str(source),
                        str(editfile),
                        str(directory / "analysis.json"),
                        str(output),
                    ],
                    env=dict(os.environ, PYTHONPATH=str(ROOT / "worker")),
                    check=True,
                    timeout=600,
                )
                if args.attribution:
                    tagged = directory / "attributed-highlight.mp4"
                    subprocess.run(
                        [
                            "ffmpeg",
                            "-v",
                            "error",
                            "-y",
                            "-i",
                            str(output),
                            "-c",
                            "copy",
                            "-metadata",
                            "copyright=" + args.attribution,
                            str(tagged),
                        ],
                        check=True,
                        timeout=60,
                    )
                    tagged.replace(output)
                    (directory / "ATTRIBUTION.txt").write_text(args.attribution + "\n")
                    report["attribution"] = args.attribution
                jid = str(uuid.uuid4())
                path = prefix + jid + ".mp4"
                b.upload("rendered-clips", path, output, "video/mp4")
                # Record a truthful audit only AFTER real rendering and upload; never enqueue/claim.
                insert(
                    "processing_jobs",
                    {
                        "id": jid,
                        "project_id": pid,
                        "clip_id": clip["id"],
                        "kind": "render",
                        "dedupe_key": "local-explicit:" + jid,
                        "status": "completed",
                        "progress": 100,
                        "stage": "Local CPU render completed (no shared queue claim)",
                        "attempts": 1,
                        "payload": {
                            "edit": edit.model_dump(),
                            "revision": clip["revision"],
                            "output_path": path,
                            "output_bytes": output.stat().st_size,
                            "execution": "explicit-isolated-local",
                        },
                    },
                )
                b.update(
                    "clips",
                    {
                        "output_path": path,
                        "output_bytes": output.stat().st_size,
                        "render_status": "completed",
                        "rendered_revision": clip["revision"],
                    },
                    id="eq." + clip["id"],
                )
                page.reload(wait_until="networkidle")
                page.get_by_role("button", name="Export", exact=True).click()
                page.get_by_role("button", name="Download MP4", exact=True).wait_for()
                downloaded = directory / "downloaded-automatic-highlight.mp4"
                with page.expect_download() as dl:
                    page.get_by_role("button", name="Download MP4", exact=True).click()
                dl.value.save_as(str(downloaded))
                assert downloaded.read_bytes() == output.read_bytes()
                meta = json.loads(
                    subprocess.check_output(
                        [
                            "ffprobe",
                            "-v",
                            "error",
                            "-show_streams",
                            "-show_format",
                            "-of",
                            "json",
                            str(downloaded),
                        ]
                    )
                )
                if args.attribution:
                    assert meta["format"]["tags"]["copyright"] == args.attribution
                subprocess.run(
                    ["ffmpeg", "-v", "error", "-i", str(downloaded), "-f", "null", "-"],
                    check=True,
                    timeout=120,
                )
                video = next(s for s in meta["streams"] if s["codec_type"] == "video")
                assert (video["width"], video["height"]) == (720, 720)
                assert (
                    abs(float(meta["format"]["duration"]) - (edit.end - edit.start))
                    < 0.25
                )
                report["checks"]["edited_mp4_private_browser_download_and_decode"] = (
                    True
                )
                r = user.post(
                    b.base + "/storage/v1/object/sign/rendered-clips/" + path,
                    json={"expiresIn": 60},
                )
                assert r.is_success
                r = httpx.get(
                    b.base + "/storage/v1/object/public/rendered-clips/" + path,
                    headers={"apikey": PUBLIC},
                    timeout=30,
                )
                assert not r.is_success
                report["checks"]["bucket_remains_private"] = True
                report["saved_edit"] = edit.model_dump()
                report["download"] = {
                    "bytes": downloaded.stat().st_size,
                    "sha256": hashlib.sha256(downloaded.read_bytes()).hexdigest(),
                    "duration": float(meta["format"]["duration"]),
                    "codecs": [s["codec_name"] for s in meta["streams"]],
                    "path": str(downloaded.relative_to(ROOT)),
                }
                report["browser_errors"] = errors
                assert not errors
                browser.close()
        report["passed"] = True
    finally:
        if uid and pid:
            for bucket in [
                "source-videos",
                "thumbnails",
                "processing-artifacts",
                "rendered-clips",
            ]:
                b.remove_prefix(bucket, uid + "/" + pid + "/")
            r = b.client.delete(
                b.base + "/rest/v1/projects", params={"id": "eq." + pid}
            )
            r.raise_for_status()
        if uid:
            r = b.client.delete(b.base + "/auth/v1/admin/users/" + uid)
            r.raise_for_status()
        report["qa_removed"] = True
        after = b.rows("processing_jobs", status="not.in.(completed,failed,cancelled)")
        report["shared_queue_unchanged"] = snapshot == after
        (directory / "acceptance.json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report, indent=2))
        assert report["shared_queue_unchanged"], (
            "Existing queue changed during isolated test"
        )


if __name__ == "__main__":
    main()
