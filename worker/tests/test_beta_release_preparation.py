"""Inert beta review packets and read-only predecessor checks; no live services."""

from pathlib import Path
import sys
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import prepare_beta_pilot as p  # noqa: E402
import inspect_beta_host as host  # noqa: E402
import receive_beta_preparation as receiver  # noqa: E402


def receipt():
    return {
        "explicit_owner_consent": True,
        "authenticated_role": "authenticated",
        "consent": {
            "owner_id": p.OWNER,
            "consent_id": "11111111-1111-4111-8111-111111111111",
            "requested_at": "2026-11-11T00:00:00Z",
            "terms_version": "local-video-v1",
            "approved_at": None,
            "revoked_at": None,
            "expires_at": None,
        },
    }


def test_fresh_consent_requires_owner_action_and_separate_unapproved_generation():
    assert p.consent_valid(receipt())
    for row in ({"explicit_owner_consent": False}, {"authenticated_role": "service_role"}):
        assert not p.consent_valid({**receipt(), **row})
    for change in (
        {"owner_id": "other-owner"},
        {"consent_id": p.EXPIRED_CONSENT},
        {"approved_at": "already-approved"},
        {"revoked_at": "revoked"},
    ):
        assert not p.consent_valid({**receipt(), "consent": {**receipt()["consent"], **change}})


def test_packet_refuses_unconsented_dirty_or_imminent_window_before_media_access():
    for build, consent, start in [
        (
            {"source_dirty": False, "release_eligible": True},
            {**receipt(), "explicit_owner_consent": False},
            10000,
        ),
        ({"source_dirty": True, "release_eligible": True}, receipt(), 10000),
        ({"source_dirty": False, "release_eligible": True}, receipt(), 1001),
    ]:
        with pytest.raises(ValueError):
            p.prepare(build, consent, start, 1000, "a" * 64, "new-id", Path("/not-read"))


def test_beta_collector_preserves_original_collector_and_targets_closed_24h(monkeypatch):
    original = host.base.PREVIOUS, host.base.PREVIOUS_SHA, host.base.PREVIOUS_CID

    def inspect(*_):
        assert host.base.PREVIOUS == host.PREVIOUS
        assert host.base.PREVIOUS_SHA == host.PREVIOUS_SHA
        return {"checks": {}, "host_preparation_checks_passed": False}

    monkeypatch.setattr(host.base, "collect", inspect)
    report = host.collect(Path("/not-used"), "new-beta", "a" * 64)
    assert (host.base.PREVIOUS, host.base.PREVIOUS_SHA, host.base.PREVIOUS_CID) == original
    assert report["worker_start_authorized"] is False and report["monitoring_installed"] is False


@pytest.mark.parametrize(
    "command",
    [
        ["docker", "--host=unix:///var/run/docker.sock", "start", "old"],
        ["systemctl", "start", "noetharaclipz-continuous.service"],
        ["iptables", "--wait", "5", "-F"],
        ["cat", "/etc/noetharaclipz-isolated/supabase-key"],
    ],
)
def test_host_collector_rejects_mutations_and_secret_reads(monkeypatch, command):
    monkeypatch.setattr(host.base.subprocess, "run", lambda *a, **k: pytest.fail("Unsafe command"))
    with pytest.raises(ValueError):
        host.base.read_command(command)


def test_receiver_rejects_authorized_payload_before_any_host_write():
    with pytest.raises(ValueError):
        receiver.validate(
            {
                "deployment_id": "11111111-1111-4111-8111-111111111111",
                "format": "nccz-beta-readonly-preparation-v1",
                "operator_approved": True,
            }
        )
