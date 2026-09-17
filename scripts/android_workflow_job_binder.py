"""Discover three public job check IDs; never authenticate or issue a challenge.

The owner independently admits the exact reviewed workflow and its role/job
names, policy templates, this code and its interpreter/TLS dependency closure.
Names select metadata only. The original signed OIDC/Jobs API/journal path must
still authenticate and consume each actual role before its protected action.

The optional deployment ``role_binding`` is ordinary digest-covered
configuration, not release authority. It is usable only after provisioning has
admitted three concurrent fixed roles and this module in the code closure; the
existing serial workflow remains outside this mode. This source seam does not
deploy or activate that workflow by itself.
"""
from __future__ import annotations

from dataclasses import fields, replace
import math
import time

from scripts import android_workflow_identity as identity

ROLES = ("capture", "emission", "protected")
PENDING = frozenset(("queued", "waiting", "pending"))
ERROR = "workflow job discovery stopped; do not retry this failure"
_SHARED = ("repository", "repository_id", "repository_owner", "repository_owner_id",
    "sha", "ref", "workflow_ref", "workflow_sha", "run_id", "run_attempt", "event_name",
    "runner_environment", "transaction_id")
_BINDING_FIELDS = frozenset(("job_names", "templates"))


class JobBindingError(RuntimeError):
    """Constant message only; no upstream metadata, paths or credentials."""


def _require(value):
    if not value:
        raise JobBindingError(ERROR)


def validate_role_binding(binding):
    """Parse a deployment-pinned role binding without making network calls.

    The deployment digest authenticates this ordinary configuration.  The
    templates are still checked against the consumer's existing policies before
    the live API lookup; the API may replace check_run_id only.
    """
    try:
        _require(type(binding) is dict and set(binding) == _BINDING_FIELDS)
        names = binding["job_names"]
        _require(type(names) is dict and set(names) == set(ROLES))
        _require(all(identity._text(names[role], 255) and names[role] == names[role].strip()
                     for role in ROLES) and len(set(names.values())) == len(ROLES))
        raw_templates = binding["templates"]
        _require(type(raw_templates) is dict and set(raw_templates) == set(ROLES))
        policy_fields = {field.name for field in fields(identity.WorkflowJobPolicy)}
        templates = {}
        for role in ROLES:
            raw = raw_templates[role]
            _require(type(raw) is dict and set(raw) == policy_fields)
            templates[role] = identity.WorkflowJobPolicy(**raw)
        _require(all(templates[role].runner_environment == "github-hosted"
                     and templates[role].run_status == templates[role].job_status == "in_progress"
                     and templates[role].run_conclusion is templates[role].job_conclusion is None
                     for role in ROLES))
        _require(templates["protected"].environment == "android-preview12-release-builder")
        first = templates["capture"]
        _require(all(getattr(policy, field) == getattr(first, field)
                     for policy in templates.values() for field in _SHARED))
        return dict(names), templates
    except Exception:
        raise JobBindingError(ERROR) from None


def bind_deployment_roles(*, binding, current_policies, role=None, deadline=None):
    """Bind a deployment's independently pinned role templates exactly once.

    ``current_policies`` is either the owner's complete three-role mapping or a
    one-role mapping used by a hosted phase/bootstrap.  The fixed caller role,
    never an API row, selects the returned policy.  No polling or retry occurs.
    """
    try:
        names, templates = validate_role_binding(binding)
        _require(type(current_policies) is dict)
        if role is None:
            _require(set(current_policies) == set(ROLES))
        else:
            _require(role in ROLES and set(current_policies) == {role})
        for name, current in current_policies.items():
            _require(type(current) is identity.WorkflowJobPolicy and current == templates[name])
        result = bind_live_roles(role_policies=templates, job_names=names, deadline=deadline)
        _require(result is not None and set(result) == set(ROLES))
        for name in ROLES:
            _require(type(result[name]) is identity.WorkflowJobPolicy)
            _require(all(getattr(result[name], field.name) == getattr(templates[name], field.name)
                         for field in fields(identity.WorkflowJobPolicy)
                         if field.name != "check_run_id"))
            _require(identity._number(result[name].check_run_id))
        _require(len({result[name].check_run_id for name in ROLES}) == len(ROLES))
        return result
    except JobBindingError:
        raise
    except Exception:
        raise JobBindingError(ERROR) from None


def bind_live_roles(*, role_policies, job_names, deadline=None):
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

        transport_deadline = time.monotonic() + identity.TOTAL_SECONDS
        if deadline is None:
            deadline = transport_deadline
        else:
            _require(type(deadline) in (int, float) and not isinstance(deadline, bool)
                     and math.isfinite(deadline) and deadline > time.monotonic())
            deadline = min(float(deadline), transport_deadline)
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
