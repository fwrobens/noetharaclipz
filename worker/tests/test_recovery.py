"""Worker control-flow contracts, separate from hosted acceptance evidence."""

import threading
from dataclasses import replace
import pytest
from noetharaclipz.config import Settings
from noetharaclipz.runner import Lease, Worker


class Records:
    def __init__(self):
        self.calls = []

    def rpc(self, name, **args):
        self.calls.append((name, args))
        return {"id": "job"} if name == "worker_claim" else True


def test_graceful_shutdown_stops_work_and_preserves_recoverable_lease():
    stop = threading.Event()
    backend = Records()
    job = {"id": "job", "lease_token": "token"}
    with Lease(backend, job, stop) as lease:
        stop.set()
        with pytest.raises(InterruptedError):
            lease.tick()
    assert [name for name, _ in backend.calls] == ["worker_tick"]


def test_shutdown_does_not_mark_job_failed_or_cancelled():
    backend = Records()
    worker = Worker(replace(Settings(), service_key="unused"), backend=backend, provider=object())

    def interrupted(job):
        raise InterruptedError("shutdown")

    worker.process = interrupted
    assert worker.once()
    assert [name for name, _ in backend.calls] == ["worker_claim"]
