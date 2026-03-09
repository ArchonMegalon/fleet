Date: 2026-03-09

## Summary

The main fleet problem is the spider's crude routing logic, not a lack of high-level models.

The current controller classifies slices from broad keywords plus whole-file prompt estimates. That over-routes Chummer work into expensive or heavyweight classes because queue-source `WORKLIST.md`, design docs, Studio files, and unread feedback all inflate the estimate even when the actual code edit is small.

The next routing step should treat accounts as capability pools, not just credentials:

- ChatGPT-auth aliases can advertise Spark.
- API-key aliases must not advertise Spark.
- Every alias should keep its own `CODEX_HOME`.
- Route from structured task classes, not only broad keywords.
- Count only the actual injected context pack when estimating prompt size.

## Immediate changes requested

1. Remove broad complexity triggers like `runtime`, `foundation`, `orchestration`, and `hardening`.
2. Raise failure-based escalation above a single failure.
3. Stop counting whole `WORKLIST.md` and design docs in prompt-size escalation.
4. Add a Spark-first lane for micro edits and bounded fixes.
5. Restrict Spark to ChatGPT-authenticated aliases only.

## Follow-on work

- Add account CRUD and pool management to admin.
- Add structured preflight classification.
- Add project account preference / burst / reserve policy.
- Add routing decision audit surfaces that explain why each `(account, model)` was chosen.
