"""Read existing beta projects in the production UI. Never submit jobs or edits.

Cookie files must come from real native Supabase QA sessions. They stay private
and are not evidence artifacts. This does not prove fresh hosted inference.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--origin", required=True)
    parser.add_argument("--owner-cookies", type=Path, required=True)
    parser.add_argument("--uninvited-cookies", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--allow-loopback", action="store_true")
    args = parser.parse_args()
    origin = args.origin.rstrip("/")
    url = urlsplit(origin)
    local = args.allow_loopback and url.hostname == "127.0.0.1" and url.scheme == "http"
    if not (local or url.scheme == "https") or url.path or url.query or url.fragment or url.username or url.password:
        raise ValueError("Reviewed HTTPS origin or explicit loopback override required")
    args.output.mkdir(mode=0o700, parents=True, exist_ok=False)

    def cookies(path):
        if path.stat().st_mode & 0o077:
            raise ValueError("Native session cookie files must be private")
        return [{"name": c["name"], "value": c["value"], "domain": url.hostname,
                 "path": "/", "secure": url.scheme == "https", "sameSite": "Lax"}
                for c in json.loads(path.read_text())]

    with sync_playwright() as playwright:
        options = {"headless": True}
        if os.getenv("CHROMIUM_PATH"):
            options["executable_path"] = os.environ["CHROMIUM_PATH"]
        browser = playwright.chromium.launch(**options)
        denied = browser.new_context()
        denied.add_cookies(cookies(args.uninvited_cookies))
        response = denied.request.get(origin + "/dashboard")
        assert response.status == 403
        denied.close()
        observations = []
        for width in (390, 1440):
            context = browser.new_context(viewport={"width": width, "height": 1000}, accept_downloads=True)
            context.add_cookies(cookies(args.owner_cookies))
            page = context.new_page()
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.set_default_timeout(30000)
            response = page.goto(origin + "/dashboard", wait_until="networkidle")
            assert response and response.status == 200
            assert "no-store" in response.headers.get("cache-control", "")
            page.get_by_role("heading", name="What should we clip,", exact=False).wait_for()
            assert page.get_by_role("heading", name="What should we clip,", exact=False).evaluate("heading => heading.scrollWidth <= heading.clientWidth")
            assert page.get_by_label("Choose a video file", exact=True).count() == 1
            assert page.evaluate("document.documentElement.scrollWidth") <= width
            assert page.locator("img").evaluate_all("images => images.every(image => image.complete && image.naturalWidth > 0)")
            page.screenshot(path=str(args.output / f"dashboard-{width}.png"), full_page=True)
            page.reload(wait_until="networkidle")
            page.get_by_role("heading", name="What should we clip,", exact=False).wait_for()
            page.locator(".project-visual").first.click()
            dialog = page.get_by_role("dialog")
            edit = dialog.locator('a[href^="/editor/"]').first
            edit.wait_for()
            editor_url = edit.get_attribute("href")
            dialog.get_by_role("link", name="Open workspace", exact=False).click()
            page.wait_for_url("**/project/*")
            page.get_by_role("button", name="Select clip", exact=True).first.wait_for()
            page.goto(origin + editor_url, wait_until="networkidle")
            trim = page.locator('[aria-label="Trim"] [role="slider"]').first
            trim.wait_for()
            original_trim = trim.get_attribute("aria-valuenow")
            page.reload(wait_until="networkidle")
            trim.wait_for()
            assert trim.get_attribute("aria-valuenow") == original_trim
            page.get_by_role("button", name="Export", exact=True).click()
            page.get_by_role("dialog").get_by_role("button", name="Export", exact=True).wait_for()
            download = page.get_by_role("button", name="Download MP4", exact=True)
            downloaded = None
            if download.count():
                with page.expect_download() as event:
                    download.first.click()
                target = args.output / f"existing-private-export-{width}.mp4"
                event.value.save_as(str(target))
                raw = target.read_bytes()
                assert len(raw) > 1024 and b"ftyp" in raw[:40]
                downloaded = {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
            page.goto(origin + "/settings", wait_until="networkidle")
            page.get_by_text("Your request is awaiting operator approval.", exact=True).wait_for()
            assert page.get_by_role("button", name="Request processing approval", exact=True).count() == 0
            page.reload(wait_until="networkidle")
            page.get_by_text("Your request is awaiting operator approval.", exact=True).wait_for()
            assert page.evaluate("document.documentElement.scrollWidth") <= width
            assert not errors, "Unhandled browser errors; details retained privately"
            observations.append({"viewport": width, "dashboard_and_refresh": True,
                "real_saved_project_and_editor": True, "saved_trim_survives_refresh": True,
                "normal_export_dialog": True, "existing_private_download": downloaded,
                "pending_consent_survives_refresh": True, "browser_errors": 0,
                "mobile_overflow": False})
            context.close()
        browser.close()
    result = {"checked_utc": datetime.now(timezone.utc).isoformat(), "origin": origin,
        "local_production_runtime": local, "native_qa_sessions": True,
        "uninvited_dashboard_status": 403, "observations": observations,
        "new_jobs": 0, "edits_saved_by_check": 0, "consent_mutations": 0,
        "new_inference_verified": False, "hosted_acceptance_passed": False}
    (args.output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
