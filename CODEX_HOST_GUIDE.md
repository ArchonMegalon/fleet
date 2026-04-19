# Codex Host Guide

This host already carries the live Chummer working set. A Codex running here should optimize for the next real product closure, not for exploratory churn.

## Start here

1. Work from `/docker/fleet` unless the task clearly belongs in a sibling repo.
2. Read `AGENTS.md`, `.codex-design/product/README.md`, `.codex-design/repo/IMPLEMENTATION_SCOPE.md`, `.codex-design/review/REVIEW_CONTEXT.md`, and `NEXT_SESSION_HANDOFF.md` before changing shared release or proof logic.
3. Treat the latest generated receipts as authoritative. Do not trust older green notes if their `generated_at` is older than the current published receipt.

## Current truth on this host

- Fleet flagship readiness is green right now.
- Desktop parity is green right now, including macOS proof receipts.
- The live registry shelf is still a published preview shelf, not a final promoted public release.
- `GROUP_BLOCKERS.md` currently reports no red blockers.
- The Next 90-day wave is the active frontier. The old “desktop parity” problem is no longer the main thing to solve.

## What to do next

Drive the remaining critical path in this order unless the user gives a different priority:

1. `M101.1` in `fleet`: make native-host proof capture and ingest a repeatable release packet lane.
2. `M102.2` in `chummer6-ui`: surface channel, build, rollback, and support-packet truth inside the desktop heads.
3. `M102.3` in `chummer6-hub-registry`: explain why a head is primary or fallback and why an install is on its current channel.
4. `M103.4` in `fleet`: consume parity-lab evidence in readiness so “covered” cannot masquerade as veteran-ready.
5. After that, keep pushing `M105` through `M107` so continuity, governor, and artifact proof stop depending on heroic operator knowledge.

## Host operating rules

- Keep one interactive Codex lane focused on one coherent slice at a time.
- Do not start extra local Codex instances just to chase speed; this host already has Fleet for shard-level parallelism.
- Do not disturb Fleet shard routing casually. The live setup is 13 shards, with only `shard-13` using `codexliz`; the others stay on `codexea`.
- Prefer worker-safe receipts, generated proofs, and repo-local verifiers over ad hoc operator narration.
- Do not use active-run helper output as closure evidence for completed proof packages.
- Fix the root cause, then refresh the relevant generated receipts, then run the narrowest useful validation, then commit.

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

If you are unsure what to do next, do the earliest unfinished task on the active `NEXT_90_DAY_PRODUCT_ADVANCE_REGISTRY.yaml` critical path that belongs to the repo you are already touching.
