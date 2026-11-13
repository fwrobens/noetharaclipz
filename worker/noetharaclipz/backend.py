from pathlib import Path
from urllib.parse import quote
import httpx
from .config import Settings, server_key_headers


class Backend:
    def __init__(self, settings: Settings, client=None):
        settings.check_project()
        self.base = settings.supabase_url.rstrip("/")
        self.client = client or httpx.Client(timeout=60)
        self.client.headers.update(server_key_headers(settings.service_key))
        # A pre-existing client may contain an unrelated bearer; never forward it.
        if settings.service_key.startswith("sb_secret_"):
            self.client.headers.pop("Authorization", None)

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
        entries = []
        # Snapshot every page before deleting subfolders: removal can shift offsets.
        while True:
            r = self.client.post(
                self.base + "/storage/v1/object/list/" + bucket,
                json={"prefix": prefix, "limit": 100, "offset": start},
            )
            r.raise_for_status()
            items = r.json()
            entries.extend(items)
            if len(items) < 100:
                break
            start += 100
        files = []
        for item in entries:
            path = prefix + item["name"]
            if item.get("id") is None:
                self.remove_prefix(bucket, path + "/")
            else:
                files.append(path)
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
