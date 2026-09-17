# Public three-job policy discovery

`scripts/android_workflow_job_binder.py` supplies one concrete provisioning call:

```python
policies = bind_live_roles(
    role_policies={"capture": capture_template, "emission": emission_template,
                   "protected": protected_template},
    job_names={"capture": reviewed_capture_name, "emission": reviewed_emission_name,
               "protected": reviewed_protected_name},
)
```

The templates are existing `WorkflowJobPolicy` instances. The owner independently
admits the workflow source/ref/commit and the exact three distinct display names
from that reviewed source/provisioning. This callable does not parse arbitrary
workflow YAML or treat GitHub-supplied names as role authority. A renamed job can
remain pending; the owner must not adopt another name from the response.

All three templates must agree on repository/owner IDs, source SHA/ref, workflow
ref/SHA, run/attempt, event, hosted-runner posture and transaction. They must
expect a live run and live jobs with null conclusions. The protected template
must select `android-preview12-release-builder`. These checks happen before any
fetch. Per-role subject, environment, reusable-workflow pair, token-age bound and
challenge placeholder fields are independently supplied, never inferred.

Template `check_run_id` values are replaceable placeholders, **not authority**.
Only that field is replaced in each returned existing policy. The result contains
no authenticated `WorkflowJobIdentity`, job lease, challenge issuance, permission
to arm, release receipt or signing capability. The original RS256/OIDC/Jobs API
verification and atomic challenge consumption still precede every protected
action. Names and public REST observations alone never authenticate a job.

The implementation reuses the existing fixed HTTPS fetch, bounded duplicate-key
JSON parser and exact run-attempt/job validators. It fetches only the public
repository's admitted run-attempt and its complete first jobs page (maximum 100)
under one existing 20-second transport deadline. No credentials, arbitrary URLs,
JWT decoding, JWKS lookup, secret discovery or private-repository fallback exist.
GitHub documents the exact [attempt-scoped jobs endpoint](https://docs.github.com/en/rest/actions/workflow-jobs#list-jobs-for-a-workflow-run-attempt).

Every present row must have a unique bounded literal name, bounded status and
null-or-bounded-string conclusion, real positive job/check IDs, exact repository URLs, run/SHA and matching
attempt if the optional row attempt field is present. Job IDs and check-run IDs
remain separate; they may happen to be equal. The existing validator checks the
whole page before its final selected-row status check; only its exact
`api-job-status` failure can classify an explicitly allowed pending role row.
Unrelated jobs receive the same structural checks but their status/conclusion
does not select or authorize a role; a completed unrelated preflight does not
block three live roles. No response status is rewritten and no queued
authentication policy is fabricated.

`None` means only a fully validated snapshot with a missing role or an explicit
`queued`, `waiting` or `pending` job. An exactly empty page is also pending and
creates no ID. Other selected-role statuses, completed selected jobs (including
successful ones), non-null selected conclusions, missing conclusions on any
row, duplicate names/IDs, malformed/mixed/truncated
pages, pagination, private repository, transport failure or deadline failure are
terminal errors, never internal retries. The closed pending subset follows the
documented [GitHub Actions status vocabulary](https://docs.github.com/en/pull-requests/reference/status-checks#check-statuses-and-conclusions);
it deliberately does not accept every possible GitHub state.

There is no polling loop, sleep, CLI, configuration dialect or persistent state.
The actual provisioning caller may wait only after `None`, within its own fixed
deadline/count and without changing admitted expectations. An exception stops
that attempt; it must not be converted to pending or caught for automatic retry.
Even a successful snapshot is time-of-observation metadata, not a guarantee
that all jobs remain live afterward. No original challenge/token TTL changes.

Tests reuse real existing parsers/API validators and synthetic test-key RS256
verification with modeled transport. They make no live metadata/OIDC request,
issue no journal challenge, activate no job, read no credential and execute no
protected action. Deployment, workflow review, hosted scheduling, private
transport, owner admission and later authentication remain separate prerequisites.
