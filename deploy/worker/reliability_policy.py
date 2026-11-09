"""Default-deny opt-in policy for the new reliability trial; no database writes.

Current SQL claims atomically by owner, not by a per-job release list. Therefore
only a freshly created, empty QA owner is admissible. Existing-user backlog
release stays unsupported until a reviewed atomic server-side protocol exists.
"""

from datetime import datetime
from uuid import UUID

OLD_OWNER = "c7ade7f9-2003-4a38-ae19-393fffae8452"
PROTECTED_JOB = "9c5c8869-ec2e-4a3e-927d-697615bb58a3"
PROTECTED_HASH = "deac9a0a9f311218fce3c531def81e1a3f92ff11e82132701a06e366d545dbdb"


def epoch(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()


def validate_approval(plan, approval, now):
    if (approval.get("trial_id") != plan["trial_id"] or not approval.get("separately_authorized")
            or approval.get("provider") != "local" or approval.get("global_processing") is not False
            or approval.get("gemini_enabled") is not False or approval.get("crash_test") != "runner_sigkill_once"):
        raise ValueError("A separate approval for this exact local, scoped crash trial is required")
    owner = str(UUID(approval["owner_id"]))
    if owner == OLD_OWNER:
        raise ValueError("Do not reuse the expired trial's owner or backlog")
    start, stop = approval["approved_at_unix"], approval["stop_at_unix"]
    if not 0 < stop - start <= plan["maximum_seconds"] or not start <= now < stop:
        raise ValueError("Approval is premature, expired, or exceeds the immutable time limit")
    return owner


def validate_fresh_owner(plan, approval, user, projects, protected_owner):
    if (user["id"] != approval["owner_id"] or user["id"] in (protected_owner, OLD_OWNER)
            or epoch(user["created_at"]) < approval["approved_at_unix"]
            or user.get("app_metadata", {}).get("nccz_qa_trial") != plan["trial_id"] or projects):
        raise ValueError("Opt-in requires a new empty QA identity created after separate approval")


def existing_user_release(*_args, **_kwargs):
    raise ValueError("Held by default: existing-owner release requires an atomic server-side per-job release protocol")
