"""Explicit, fail-closed v2 consent transport. Never falls back to v1 claims.

The SQL contract serializes revocation and visible commits. An already running
Storage HTTP request may finish, but its result cannot be published after consent
is revoked; files remain private and unreferenced until reviewed cleanup.
"""

from pathlib import PurePosixPath

from .backend import Backend

PROTECTED_JOB = "9c5c8869-ec2e-4a3e-927d-697615bb58a3"
CONTRACT = "future-jobs-only-v1"


class ProcessingRevoked(InterruptedError):
    pass


class ConsentedBackend(Backend):
    def __init__(self, settings, client=None):
        if (
            settings.queue_mode != "consented"
            or not settings.scope_owner
            or not settings.consent_id
        ):
            raise ValueError("Explicit consent settings required")
        super().__init__(settings, client)
        self.owner, self.consent_id = settings.scope_owner, settings.consent_id
        self.job = None

    def rpc(self, name, **params):
        mapping = {
            "worker_tick": "worker_tick_optin",
            "worker_finish_analysis": "worker_finish_analysis_optin",
            "worker_finish_render": "worker_finish_render_optin",
        }
        allowed = {
            "worker_continuous_protocol",
            "worker_consent_status",
            "worker_claim_optin",
            "worker_heartbeat_optin",
            "worker_checkpoint_optin",
            "worker_authorize_optin",
        }
        if name not in mapping and name not in allowed:
            raise ValueError("Legacy/global operation forbidden in consented mode")
        target = mapping.get(name, name)
        if target != "worker_continuous_protocol":
            if (
                params.get("owner", self.owner) != self.owner
                or params.get("consent", self.consent_id) != self.consent_id
            ):
                raise ValueError("Another owner's authorization cannot be used")
            params = {**params, "owner": self.owner, "consent": self.consent_id}
        if "jid" in params:
            if (
                not self.job
                or params["jid"] != self.job["id"]
                or params.get("token") != self.job["lease_token"]
            ):
                raise ValueError("Operation does not belong to the current consented lease")
        response = self.client.post(self.base + "/rest/v1/rpc/" + target, json=params)
        if response.is_error:
            # No remote body/headers/token is included in an exception or log.
            if response.status_code in (401, 403):
                raise ProcessingRevoked("Processing authorization revoked or unavailable")
            raise RuntimeError(
                "Consented backend operation failed: "
                + target
                + " HTTP "
                + str(response.status_code)
            )
        value = response.json() if response.content else None
        if target == "worker_checkpoint_optin" and value is False:
            from .media import Cancelled

            self.job["status"] = "cancelled"
            raise Cancelled("Job was cancelled")
        if target == "worker_claim_optin" and value:
            if (
                value.get("owner_id") != self.owner
                or value.get("consent_id") != self.consent_id
                or value.get("id") == PROTECTED_JOB
                or value.get("kind") not in ("analysis", "render")
                or not 1 <= value.get("attempts", 0) <= 3
                or not value.get("source_identity")
            ):
                raise ValueError("Invalid consent-bound claim; do not process its input")
            self.job = value
        return value

    def authorize(self):
        if not self.job:
            raise ValueError("No active consented job")
        if (
            self.rpc("worker_authorize_optin", jid=self.job["id"], token=self.job["lease_token"])
            is not True
        ):
            raise ProcessingRevoked("Job is held or processing authorization was revoked")

    def rows(self, table, **filters):
        if not self.job or table not in ("projects", "videos", "analysis_artifacts"):
            raise ValueError("Unscoped table read forbidden")
        expected = (
            {"id": "eq." + self.job["project_id"]}
            if table == "projects"
            else {"project_id": "eq." + self.job["project_id"]}
        )
        if filters != expected:
            raise ValueError("Read must use the current project's exact scope")
        self.authorize()
        rows = super().rows(table, **filters)
        if table == "projects" and (len(rows) != 1 or rows[0]["owner_id"] != self.owner):
            raise ValueError("Project ownership changed")
        if table == "videos":
            identity = self.job["source_identity"]
            if len(rows) != 1 or any(
                rows[0].get(k) != identity[k] for k in ("id", "source_path", "byte_size")
            ):
                raise ValueError("Source revision changed")
        return rows

    def path_allowed(self, path):
        if (
            not self.job
            or not path.startswith(self.owner + "/" + self.job["project_id"] + "/")
            or ".." in PurePosixPath(path).parts
            or "\\" in path
        ):
            raise ValueError("Storage path outside the current authorized project")

    def download(self, bucket, path, dest, maximum=45_000_000):
        self.path_allowed(path)
        if bucket != "source-videos" or path != self.job["source_identity"]["source_path"]:
            raise ValueError("Only this lease's source may be downloaded")
        self.authorize()
        result = super().download(bucket, path, dest, maximum)
        self.authorize()
        return result

    def upload(self, bucket, path, source, mime):
        self.path_allowed(path)
        name = PurePosixPath(path).name
        valid = (
            (bucket == "source-videos" and name == "playback.mp4")
            or (bucket == "thumbnails" and (name == "thumbnail.jpg" or name.startswith("frame-")))
            or (bucket == "processing-artifacts" and name == "local-analysis.json")
            or (bucket == "rendered-clips" and name == self.job["id"] + ".mp4")
        )
        if not valid:
            raise ValueError("Unsupported consented artifact destination")
        self.authorize()
        super().upload(bucket, path, source, mime)
        self.authorize()

    def update(self, *_args, **_kwargs):
        raise ValueError("Use an authorized transactional checkpoint RPC")

    def cleanup(self):
        raise ValueError("Global cleanup is forbidden in consented mode")

    def remove_prefix(self, *_args, **_kwargs):
        raise ValueError("Storage deletion is forbidden in consented mode")
