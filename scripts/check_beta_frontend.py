"""Anonymous smoke test of built/hosted beta. Never uploads or creates jobs."""

import argparse
import json
import os
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from playwright.sync_api import sync_playwright


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--origin", required=True)
    parser.add_argument("--build", required=True)
    parser.add_argument("--allow-loopback", action="store_true")
    parser.add_argument(
        "--output", type=Path, default=Path("test-results/beta/frontend.json")
    )
    args = parser.parse_args()
    url = urlsplit(args.origin)
    local = args.allow_loopback and url.hostname == "127.0.0.1" and url.scheme == "http"
    if (
        not (url.scheme == "https" or local)
        or url.path not in ("", "/")
        or url.username
        or url.password
        or url.query
        or url.fragment
        or len(args.build) != 40
        or any(c not in "0123456789abcdef" for c in args.build)
    ):
        raise ValueError(
            "Reviewed HTTPS origin/build required; explicit loopback override for local artifacts"
        )
    origin = args.origin.rstrip("/")
    with httpx.Client(timeout=30, follow_redirects=False) as client:
        release = client.get(origin + "/api/release")
        release.raise_for_status()
        identity = release.json()
        assert {k: identity[k] for k in ("app", "mode", "build")} == {
            "app": "NoetharaClipz",
            "mode": "owner-scoped-beta",
            "build": args.build,
        }
        assert identity["access"]["mode"] == "authenticated-owner-allowlist-v1"
        assert (
            identity["access"]["owners"] == 1
            and len(identity["access"]["sha256"]) == 64
        )
        assert "no-store" in release.headers.get("cache-control", "")
        assert client.post(origin + "/api/release").status_code == 405
        head = client.head(origin + "/api/release")
        assert head.status_code == 200 and not head.content
    observations = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True,
            **(
                {"executable_path": os.environ["CHROMIUM_PATH"]}
                if os.getenv("CHROMIUM_PATH")
                else {}
            ),
        )
        for width in (390, 1440):
            page = browser.new_page(viewport={"width": width, "height": 1000})
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            response = page.goto(origin + "/login", wait_until="networkidle")
            assert response and response.status == 200
            assert "noindex" in response.headers.get("x-robots-tag", "")
            assert page.get_by_role("button", name="Log in", exact=True).count() == 1
            assert (
                page.get_by_text("This beta is invitation only.", exact=False).count()
                == 1
            )
            assert (
                page.get_by_role("button", name="Create an account", exact=True).count()
                == 0
            )
            assert (
                page.get_by_role(
                    "button", name="Google", exact=True
                ).count()
                == 0
            )
            assert page.evaluate("document.documentElement.scrollWidth") <= width
            assert page.locator("img").evaluate_all("images => images.every(image => image.complete && image.naturalWidth > 0)")
            for protected in ("/dashboard", "/dashboard/projects", "/library", "/settings", "/projects"):
                page.goto(origin + protected, wait_until="networkidle")
                assert urlsplit(page.url).path == "/login"
            page.goto(origin + "/auth/callback", wait_until="networkidle")
            assert "missing its code" in page.get_by_role("status").inner_text()
            assert not errors, "Unhandled browser error"
            observations.append(
                {
                    "viewport": width,
                    "login": True,
                    "private_redirects": True,
                    "callback_missing_code": True,
                    "no_overflow": True,
                    "page_errors": errors,
                }
            )
            page.close()
        browser.close()
    result = {
        "origin": origin,
        "build": args.build,
        "production_artifact": True,
        "locally_served": local,
        "anonymous_checks": observations,
        "authenticated_hosted_acceptance_passed": False,
        "uploads_performed": 0,
        "published_by_this_check": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
