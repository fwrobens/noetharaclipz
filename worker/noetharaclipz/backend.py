from pathlib import Path
from urllib.parse import quote
import httpx
from .config import Settings


class Backend:
    def __init__(self, settings: Settings):
        settings.check_project()
        self.base = settings.supabase_url.rstrip("/")
        self.client = httpx.Client(
            timeout=60,
            headers={
                "apikey": settings.service_key,
                "Authorization": "Bearer " + settings.service_key,
            },
        )

    def rpc(self, name, **params):
        response = self.client.post(self.base + "/rest/v1/rpc/" + name, json=params)
        if response.is_error:
            raise RuntimeError("Backend operation failed: " + response.text[:1000])
        return response.json() if response.content else None

    def rows(self, table, **filters):
        r = self.client.get(self.base + "/rest/v1/" + table, params=filters)
        r.raise_for_status()
        return r.json()

    def update(self, table, values, **filters):
        r = self.client.patch(self.base + "/rest/v1/" + table, params=filters, json=values)
        r.raise_for_status()

    def download(self, bucket, path, dest: Path, maximum=45_000_000):
        url = self.base + "/storage/v1/object/authenticated/" + bucket + "/" + quote(path, safe="/")
        size = 0
        with self.client.stream("GET", url) as r:
            r.raise_for_status()
            with dest.open("wb") as f:
                for chunk in r.iter_bytes(1024 * 1024):
                    size += len(chunk)
                    if size > maximum:
                        raise ValueError("Stored input exceeds the allowed size")
                    f.write(chunk)
        return size

    def upload(self, bucket, path, source: Path, mime):
        if source.stat().st_size > 45_000_000:
            raise ValueError("Artifact exceeds storage file limit")
        with source.open("rb") as f:
            r = self.client.post(
                self.base + "/storage/v1/object/" + bucket + "/" + quote(path, safe="/"),
                content=f,
                headers={
                    "Content-Type": mime,
                    "Content-Length": str(source.stat().st_size),
                    "x-upsert": "true",
                },
            )
        r.raise_for_status()

    def remove_prefix(self, bucket, prefix):
        # Storage API removal, never SQL DELETE against storage.objects.
        start = 0
        files = []
        while True:
            r = self.client.post(
                self.base + "/storage/v1/object/list/" + bucket,
                json={"prefix": prefix, "limit": 100, "offset": start},
            )
            r.raise_for_status()
            items = r.json()
            for item in items:
                path = prefix + item["name"]
                if item.get("id") is None:
                    self.remove_prefix(bucket, path + "/")
                else:
                    files.append(path)
            if len(items) < 100:
                break
            start += 100
        for i in range(0, len(files), 100):
            r = self.client.request(
                "DELETE",
                self.base + "/storage/v1/object/" + bucket,
                json={"prefixes": files[i : i + 100]},
            )
            r.raise_for_status()

    def cleanup(self):
        from datetime import datetime, timedelta, timezone

        cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        orphan_cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        expired = self.rows("projects", deleted_at="lt." + cutoff)
        expired += self.rows("projects", status="eq.uploading", created_at="lt." + orphan_cutoff)
        for p in expired:
            active = self.rows(
                "processing_jobs",
                project_id="eq." + p["id"],
                status="not.in.(completed,failed,cancelled)",
            )
            if active:
                continue
            for bucket in ("source-videos", "thumbnails", "processing-artifacts", "rendered-clips"):
                self.remove_prefix(bucket, p["owner_id"] + "/" + p["id"] + "/")
            r = self.client.delete(self.base + "/rest/v1/projects", params={"id": "eq." + p["id"]})
            r.raise_for_status()
