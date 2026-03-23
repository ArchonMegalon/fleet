# GitHub Codex Review

PR: local://fleet

Findings:
- [high] controller/app.py [review] slice-status-plane-verifier-missing
Slice goal is STATUS_PLANE drift verifier coverage, but the only diff vs `main` is `controller/app.py` (account model/backoff logic).; No verifier/test artifact changes were made for `STATUS_PLANE.generated.yaml` readiness/deployment semantics.
Expected fix: Implement the requested STATUS_PLANE verifier coverage (and corresponding tests) that fails on drift from live readiness/deployment semantics.
- [high] controller/app.py [correctness] model-capability-fallback-regression
`effective_allowed_models_for_account` now returns `allowed_models` on no-overlap instead of capability-derived models.; Call sites (e.g. account/model selection and local review model selection) use that result directly and do not enforce capability membership afterward, so stale/configured `allowed_models` can select models not in live capability probes.
Expected fix: Reintroduce capability-safe fallback behavior (or explicit post-check against capability models) so selected models cannot bypass live capability constraints; add unit tests for overlap/no-overlap cases across auth kinds.
