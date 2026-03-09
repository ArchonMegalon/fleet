# Fleet self-healing cockpit guide

Date: 2026-03-09

Key direction:
- remove public `idle`
- treat blocked/review failures as incidents plus healing loops
- auto-resolve safe finding families before escalating to the operator
- keep admin focused on true design/contract decisions rather than queue babysitting

Current implementation target from this note:
- public runtime states should prefer `healing`, `waiting_capacity`, `queue_refilling`, `decision_required`, and `completed_signed_off`
- `review_failed` and `blocked_unresolved` should be incident-driven
- uncovered-scope and queue-exhausted-with-uncovered-scope findings should auto-materialize into published queue work when policy allows
- operators should only see red incidents once the healer/auditor path cannot finish safely

Immediate follow-up items:
- keep pushing the admin cockpit toward lamp-style category views
- make the healer role explicit next to the auditor
- continue shrinking manual approve/publish paths for safe backlog-materialization cases
