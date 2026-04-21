# Codex Host Guide

This host already carries the live Chummer working set. A Codex running here should optimize for the next real product closure, not for exploratory churn.

## Start here

1. Work from `/docker/fleet` unless the task clearly belongs in a sibling repo.
2. Read `AGENTS.md`, `.codex-design/product/README.md`, `.codex-design/repo/IMPLEMENTATION_SCOPE.md`, `.codex-design/review/REVIEW_CONTEXT.md`, and `NEXT_SESSION_HANDOFF.md` before changing shared release or proof logic.
3. Treat the latest generated receipts as authoritative. Do not trust older green notes if their `generated_at` is older than the current published receipt.

## Current truth on this host

- Fleet flagship readiness is currently `fail` on one lane only: `desktop_client`.
- The current published readiness receipt is `/docker/fleet/.codex-studio/published/FLAGSHIP_PRODUCT_READINESS.generated.json`.
- The real remaining product gap is not shell density anymore; it is the last stretch from “shared classic dialog parity” to “legacy-specific utility form parity”, plus the honest Windows proof lane.
- The live registry shelf is still a published preview shelf, not a final promoted public release.
- Do not trust older handoff notes that say parity is already complete unless they match the current published receipt timestamps.

## What to do next

Drive the remaining critical path in this order unless the user gives a different priority:

1. `chummer-presentation`: finish the legacy-specific utility surfaces that are still only “shared classic” rather than near-clone Chummer5a forms:
   - `Global Settings` real settings-tree posture
   - `Master Index` real tree/grid/snippet posture
   - `Character Roster` real tree/tab/image posture
   - selection/edit dialogs with live recalculation and exact category coupling
2. `chummer-presentation`: author the remaining SR4/SR6 dialog copy so those heads stop reading ruleset-neutral where Chummer5a-style vocabulary should differ.
3. `fleet`: keep the parity loop honest by re-running the focused UI suite and the four Chummer5a gates after each UI slice:
   - `DesktopDialogFactoryTests`
   - `AvaloniaFlagshipUiGateTests`
   - `DesktopShellRulesetCatalogTests`
   - `BlazorShellComponentTests`
   - `scripts/ai/milestones/chummer5a-layout-hard-gate.sh`
   - `scripts/ai/milestones/classic-dense-workbench-posture-gate.sh`
   - `scripts/ai/milestones/chummer5a-screenshot-review-gate.sh`
   - `scripts/ai/milestones/chummer5a-desktop-workflow-parity-check.sh`
4. `fleet` + Windows host: once the UI slice is published, run the prepared Windows proof lane and return the bundle. Fleet auto-ingests the returned proof bundle now; do not fabricate Windows proof from Linux-side similarity.
5. After `desktop_client` clears, move back to the broader roadmap items.

## Host operating rules

- Keep one interactive Codex lane focused on one coherent slice at a time.
- Do not start extra local Codex instances just to chase speed; this host already has Fleet for shard-level parallelism.
- Do not disturb Fleet shard routing casually. The current target state is EA-backed shards; verify live routing before changing it.
- Prefer worker-safe receipts, generated proofs, and repo-local verifiers over ad hoc operator narration.
- Do not use active-run helper output as closure evidence for completed proof packages.
- Fix the root cause, then refresh the relevant generated receipts, then run the narrowest useful validation, then commit.
- Do not stop after a status report, a green validation batch, a commit, or a push. Pick the next highest-value slice and continue unless a true external blocker exists.
- After every important step, rewrite `/docker/fleet/NEXT_SESSION_HANDOFF.md` as a mandatory default behavior. Important steps include implementation batches, validation batches, commits, pushes, live restarts, audits, blocker discoveries, and priority shifts.
- Treat the handoff as part of the work, not as an optional summary. A stale or missing handoff is a failure state for both the main agent and any codexliz-backed lane.

## Repos you will actually use

- `/docker/fleet` — supervisor, queue, readiness, watchdogs, operator surfaces, and design mirror.
- `/docker/chummercomplete/chummer.run-services` — Hub/API/account/install/support/public surface work.
- `/docker/chummercomplete/chummer-hub-registry` — release channel truth, proof shelf, route/channel rationale.
- `/docker/chummercomplete/chummer-presentation` — desktop executable and platform exit receipts.
- `/docker/chummercomplete/chummer6-ui` or `/docker/chummercomplete/chummer6-ui-finish` — UI/head-specific release-truth and desktop-surface work, depending on where the active slice lives.
- `/docker/chummercomplete/chummer-core-engine`, `/docker/chummercomplete/chummer-play`, and `/docker/fleet/repos/chummer-media-factory` when the queue item explicitly lands there.

## Fast reality checks

Use these before claiming anything is fixed:

```bash
cd /docker/fleet
python3 - <<'PY'
import json
from pathlib import Path
p = Path('.codex-studio/published/FLAGSHIP_PRODUCT_READINESS.generated.json')
obj = json.loads(p.read_text())
print(obj['generated_at'], obj['status'], obj.get('ready_keys'))
PY
```

```bash
cd /docker/chummercomplete/chummer-hub-registry
python3 - <<'PY'
import json
from pathlib import Path
p = Path('.codex-studio/published/RELEASE_CHANNEL.generated.json')
obj = json.loads(p.read_text())
print(obj['generated_at'], obj['status'], obj.get('rolloutState'), obj.get('version'))
PY
```

```bash
cd /docker/chummercomplete/chummer-presentation
python3 - <<'PY'
import json
from pathlib import Path
p = Path('.codex-studio/published/DESKTOP_EXECUTABLE_EXIT_GATE.generated.json')
obj = json.loads(p.read_text())
print(obj['generated_at'], obj['status'], obj.get('local_blocking_findings_count'))
PY
```

## Commit discipline

- Keep commits focused to one slice.
- Validate before committing.
- Push only after checking the target branch and making sure large generated binaries are not accidentally included.
- If GitHub rejects a push for oversized files, remove them from the commit and amend; do not leave broken history in place.

## Decision rule

If you are unsure what to do next, work the earliest remaining gap that blocks a defensible “looks and behaves like Chummer5a” claim on the repo you are already touching, then refresh the Fleet-facing receipts that prove it.
