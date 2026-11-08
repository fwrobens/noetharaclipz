"""Live acceptance: actual browser → Supabase → worker/AI → downloadable MP4.

No fixtures or mocked provider responses are accepted. Requires a running selected
provider (local, or verified free Gemini), a test account and authorized footage.
Run with the environment's Playwright, or install scripts/requirements-e2e.txt.
"""

import json
import hashlib
import os
import subprocess
import time
from pathlib import Path

import httpx
from playwright.sync_api import sync_playwright

PROJECT = "https://zxdnjnsghdnviflahvry.supabase.co"
PUBLIC_KEY = "sb_publishable_wlXMNmobAj-bq_wKU7BduQ_FoKG6Eyk"


def main():
    email = os.environ["NC_TEST_EMAIL"]
    password = os.environ["NC_TEST_PASSWORD"]
    sample = Path(os.environ["NC_SAMPLE_VIDEO"]).resolve(strict=True)
    base = os.getenv("NC_BASE_URL", "http://127.0.0.1:8080").rstrip("/")
    output = Path("test-results/acceptance.mp4").resolve()
    output.parent.mkdir(exist_ok=True)
    evidence = {
        "passed": False,
        "source_sha256": hashlib.sha256(sample.read_bytes()).hexdigest(),
    }
    selected_provider = os.getenv("NC_AI_PROVIDER", "gemini")
    assert selected_provider in ("local", "gemini"), (
        "Explicit supported provider required"
    )
    expected_provider = "local-smolvlm2" if selected_provider == "local" else "gemini"
    with httpx.Client(timeout=45, headers={"apikey": PUBLIC_KEY}) as api:
        login = api.post(
            PROJECT + "/auth/v1/token?grant_type=password",
            json={"email": email, "password": password},
        )
        login.raise_for_status()
        api.headers["Authorization"] = "Bearer " + login.json()["access_token"]
        health = api.post(PROJECT + "/rest/v1/rpc/pipeline_health", json={})
        health.raise_for_status()
        assert health.json().get("online") and health.json().get("ai_ready"), (
            "Selected worker/provider is not ready; acceptance did not start"
        )

        def rows(table, **params):
            response = api.get(PROJECT + "/rest/v1/" + table, params=params)
            response.raise_for_status()
            return response.json()

        def wait_job(pid, kind):
            deadline = time.monotonic() + int(os.getenv("NC_WAIT_SECONDS", "1200"))
            while time.monotonic() < deadline:
                jobs = rows(
                    "processing_jobs",
                    project_id="eq." + pid,
                    kind="eq." + kind,
                    order="created_at.desc",
                )
                if jobs:
                    job = jobs[0]
                    if job["status"] in ("failed", "cancelled"):
                        raise AssertionError(
                            "Live "
                            + kind
                            + " stopped: "
                            + (job.get("error") or job["stage"])
                        )
                    if job["status"] == "completed":
                        return job
                time.sleep(2)
            raise AssertionError("Timed out waiting for the actual " + kind + " job")

        with sync_playwright() as playwright:
            options = {"headless": True}
            if os.getenv("CHROMIUM_PATH"):
                options["executable_path"] = os.environ["CHROMIUM_PATH"]
            browser = playwright.chromium.launch(**options)
            page = browser.new_page(
                viewport={"width": 1440, "height": 1000}, accept_downloads=True
            )
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.set_default_timeout(30000)
            page.goto(base + "/login", wait_until="networkidle")
            page.get_by_label("Email", exact=True).fill(email)
            page.get_by_label("Password", exact=True).fill(password)
            page.get_by_role("button", name="Sign in", exact=True).click()
            page.wait_for_url("**/library")
            page.goto(base + "/", wait_until="networkidle")
            page.locator("input[type=file]").set_input_files(str(sample))
            page.locator("textarea").fill(
                os.getenv(
                    "NC_PROMPT",
                    "Find a visually dramatic or surprising moment and explain the visible evidence. Select a complete short clip.",
                )
            )
            page.get_by_role("checkbox").check()
            page.get_by_role("button", name="Generate", exact=True).click()
            page.wait_for_url("**/project/*", timeout=60000)
            pid = page.url.rsplit("/", 1)[-1]
            evidence["project_id"] = pid
            print("Actual upload accepted; waiting for live video analysis", flush=True)
            analysis_job = wait_job(pid, "analysis")
            assert (
                analysis_job["message_id"] is not None and analysis_job["attempts"] > 0
            ), "No actual queue claim"
            artifacts = rows("analysis_artifacts", project_id="eq." + pid)
            assert artifacts and artifacts[0]["provider"] == expected_provider
            usage = rows("provider_usage", project_id="eq." + pid)
            assert usage and all(
                u["status"] == "completed" and u["provider"] == expected_provider
                for u in usage
            )
            assert sum(u["input_tokens"] for u in usage) > 0 or (
                selected_provider == "local"
                and analysis_job["payload"]
                .get("local_metrics", {})
                .get("analysis_cache_hit")
            ), "No recorded actual inference usage"
            highlights = rows("highlights", project_id="eq." + pid)
            video = rows("videos", project_id="eq." + pid)[0]
            if selected_provider == "local":
                prefix = video["source_path"].split("/")[:2]
                raw = api.get(
                    PROJECT
                    + "/storage/v1/object/authenticated/processing-artifacts/"
                    + "/".join(prefix)
                    + "/local-analysis.json"
                )
                raw.raise_for_status()
                proof = raw.json()
                assert (
                    proof["provider"] == "local-smolvlm2"
                    and proof["source_hash"] == video["source_hash"]
                    and proof["local_usage"]["input_tokens"] > 0
                )
                assert (
                    proof["hosted_inference"] is False
                    and proof["decision"]["input_tokens"] > 0
                )
            assert highlights, (
                "No real AI highlight was selected; acceptance remains incomplete"
            )
            assert all(
                0 <= h["start_time"] < h["end_time"] <= video["duration"]
                for h in highlights
            )
            page.reload(wait_until="networkidle")
            page.get_by_role("button", name="Select clip", exact=True).first.click()
            page.get_by_role("link", name="Edit", exact=True).click()
            page.wait_for_function("document.querySelector('video')?.readyState>=2")
            initial = page.locator("video").evaluate("v=>v.currentTime")
            page.get_by_role("button", name="Play", exact=True).click()
            page.wait_for_function(
                "start=>{const v=document.querySelector('video');return v&&!v.paused&&v.currentTime>start+.1}",
                arg=initial,
            )
            trim = page.locator('[aria-label="Trim"] [role="slider"]').first
            trim.focus()
            trim.press("ArrowRight")
            page.get_by_role("button", name="Save", exact=True).click()
            page.get_by_text("Edit saved", exact=True).wait_for()
            saved = rows("clips", project_id="eq." + pid)[0]
            assert saved["edit"]["start"] != highlights[0]["start_time"], (
                "UI trim did not change"
            )
            page.reload(wait_until="networkidle")
            page.wait_for_function(
                "document.querySelector('[aria-label=Trim] [role=slider]') !== null"
            )
            assert (
                abs(
                    float(
                        page.locator(
                            '[aria-label="Trim"] [role="slider"]'
                        ).first.get_attribute("aria-valuenow")
                    )
                    - saved["edit"]["start"]
                )
                < 0.11
            )
            page.get_by_role("button", name="Export", exact=True).click()
            page.get_by_role("dialog").get_by_role(
                "button", name="Export", exact=True
            ).click()
            render_job = wait_job(pid, "render")
            assert (
                render_job["message_id"] is not None and render_job["attempts"] > 0
            ), "No actual render queue claim"
            assert render_job["payload"].get("output_path"), (
                "Worker did not commit an output object"
            )
            page.get_by_role("button", name="Download MP4", exact=True).wait_for(
                timeout=30000
            )
            with page.expect_download() as result:
                page.get_by_role("button", name="Download MP4", exact=True).click()
            result.value.save_as(str(output))
            assert output.stat().st_size > 0
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
            assert any(s["codec_name"] == "h264" for s in metadata["streams"])
            if video["has_audio"]:
                assert any(s["codec_name"] == "aac" for s in metadata["streams"])
            assert 0 < float(metadata["format"]["duration"]) <= 60.25
            assert (
                abs(
                    float(metadata["format"]["duration"])
                    - (saved["edit"]["end"] - saved["edit"]["start"])
                )
                < 0.25
            )
            subprocess.run(
                ["ffmpeg", "-v", "error", "-i", str(output), "-f", "null", "-"],
                check=True,
                timeout=120,
            )
            assert not errors, "Unhandled browser errors"
            evidence.update(
                passed=True,
                provider=expected_provider,
                analysis_job_id=analysis_job["id"],
                render_job_id=render_job["id"],
                analysis_attempts=analysis_job["attempts"],
                render_attempts=render_job["attempts"],
                highlights=highlights,
                clip_id=saved["id"],
                persisted_edit=saved["edit"],
                output_path=render_job["payload"]["output_path"],
                output_bytes=output.stat().st_size,
                output_sha256=hashlib.sha256(output.read_bytes()).hexdigest(),
                output_duration=float(metadata["format"]["duration"]),
                unhandled_browser_errors=errors,
                ui_steps="login, upload, instructions, generate, select, edit, save, refresh, Export button, Download MP4 button",
            )
            (output.parent / "acceptance.json").write_text(
                json.dumps(evidence, indent=2) + "\n"
            )
            print(
                "PASS: actual AI analysis, highlights, playback, persisted edit, private MP4 download and decode",
                flush=True,
            )
            browser.close()


if __name__ == "__main__":
    main()
