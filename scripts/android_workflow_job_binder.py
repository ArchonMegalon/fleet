"""Discover three public job check IDs; never authenticate or issue a challenge.

The owner independently admits the exact reviewed workflow and its role/job
names, policy templates, this code and its interpreter/TLS dependency closure.
Names select metadata only. The original signed OIDC/Jobs API/journal path must
still authenticate and consume each actual role before its protected action.
"""
from __future__ import annotations

from dataclasses import replace
import time

from scripts import android_workflow_identity as identity

ROLES = ("capture", "emission", "protected")
PENDING = frozenset(("queued", "waiting", "pending"))
ERROR = "workflow job discovery stopped; do not retry this failure"
_SHARED = ("repository", "repository_id", "repository_owner", "repository_owner_id",
    "sha", "ref", "workflow_ref", "workflow_sha", "run_id", "run_attempt", "event_name",
    "runner_environment", "transaction_id")


class JobBindingError(RuntimeError):
    """Constant message only; no upstream metadata, paths or credentials."""


def _require(value):
    if not value:
        raise JobBindingError(ERROR)


def bind_live_roles(*, role_policies, job_names):
    """Return existing policies with ONLY check_run_id replaced, or None pending.

    Both dictionaries have exactly capture/emission/protected keys. Names must
    come from the independently reviewed workflow's provisioning, not API rows
    or decoded tokens. Template check IDs are placeholders and are NOT trusted.
    All other fields, including per-role subject/environment/reusable identity
    and challenge placeholders, remain owner-supplied and unchanged.

    One read attempt, no internal polling/retry: None permits caller-owned
    bounded waiting after a fully validated pending snapshot. Any exception is
    terminal for that discovery attempt. A successful result is expectations,
    not authenticated facts, a current-job lease or permission to arm/sign.
    """
    try:
        _require(type(role_policies) is dict and set(role_policies) == set(ROLES)
                 and type(job_names) is dict and set(job_names) == set(ROLES))
        policies, names = dict(role_policies), dict(job_names)
        for role in ROLES:
            policy = policies[role]
            _require(type(policy) is identity.WorkflowJobPolicy)
            policy.__post_init__()
            _require(policy.runner_environment == "github-hosted"
                     and policy.run_status == policy.job_status == "in_progress"
                     and policy.run_conclusion is policy.job_conclusion is None
                     and identity._text(names[role], 255) and names[role] == names[role].strip())
        _require(len(set(names.values())) == len(ROLES)
                 and policies["protected"].environment == "android-preview12-release-builder")
        first = policies["capture"]
        _require(all(getattr(policy, field) == getattr(first, field)
                     for policy in policies.values() for field in _SHARED))

        deadline = time.monotonic() + identity.TOTAL_SECONDS
        base = (identity.API + "/repos/" + first.repository + "/actions/runs/"
                + first.run_id + "/attempts/" + first.run_attempt)
        identity._run_attempt(identity._json(identity._fetch(base, deadline)), first)
        identity._remaining(deadline)
        page = identity._json(identity._fetch(base + "/jobs?per_page=100&page=1", deadline))
        # The existing job validator requires at least one row. Empty is the
        # sole extra page case and can only produce pending, never a binding.
        _require(set(page) == {"total_count", "jobs"} and type(page["total_count"]) is int
                 and type(page["jobs"]) is list and 0 <= page["total_count"] <= 100
                 and page["total_count"] == len(page["jobs"]))
        rows = {}
        selected_names = set(names.values())
        for row in page["jobs"]:
            _require(type(row) is dict and identity._text(row.get("name"), 255)
                     and row["name"] == row["name"].strip() and row["name"] not in rows
                     and identity._text(row.get("status"), 64) and "conclusion" in row
                     and (row["conclusion"] is None or identity._text(row["conclusion"], 64)))
            selected = row["name"] in selected_names
            if selected:
                _require(row["status"] in PENDING | {"in_progress"} and row["conclusion"] is None)
            check_url = row.get("check_run_url")
            _require(type(check_url) is str)
            check_id = check_url.rsplit("/", 1)[-1]
            _require(identity._number(check_id))
            # _job validates the entire page before its final selected status
            # check. Only that exact final error may represent known pending
            # for a selected role. Unrelated status is not role authority.
            # Do not fabricate a queued policy or normalize response statuses.
            try:
                identity._job(page, replace(first, check_run_id=check_id))
            except identity.WorkflowIdentityError as error:
                _require(str(error) == "api-job-status" and (not selected or row["status"] in PENDING))
            rows[row["name"]] = (check_id, row["status"])
            identity._remaining(deadline)
        identity._remaining(deadline)
        if any(name not in rows or rows[name][1] in PENDING for name in names.values()):
            return None
        result = {role: replace(policies[role], check_run_id=rows[names[role]][0]) for role in ROLES}
        _require(len({policy.check_run_id for policy in result.values()}) == len(ROLES))
        identity._remaining(deadline)
        return result
    except Exception:
        raise JobBindingError(ERROR) from None
