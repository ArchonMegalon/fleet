# Next Session Handoff

Date: 2026-03-22
Workspace focus: `/docker/fleet`

## Current objective

Implement the new Fleet capacity-plane design fully, with Quartermaster as a first-class control-plane service and with controller/routing/policy integration that actually uses the new capacity contract instead of only documenting it.

The current repo state is beyond the older admin-only handoff. The active work is now:

- new lane topology in routing
- new quartermaster service/config surface
- new capacity-plane payload builder
- partial controller integration
- expanded tests around routing and capacity semantics

## What is already in the tree

- New capacity-plane config files exist:
  - `config/quartermaster.yaml`
  - `config/booster_pools.yaml`
  - `config/review_fabric.yaml`
  - `config/audit_fabric.yaml`

- New Quartermaster service exists:
  - `quartermaster/app.py`
  - `quartermaster/Dockerfile`
  - `quartermaster/requirements.txt`

- Routing/policy surface has already been widened for the new design:
  - `config/routing.yaml` now defines `core_authority`, `core_booster`, `core_rescue`, `review_shard`, and `audit_shard`
  - `config/policies.yaml` now has `policies.capacity_plane` and `compile.stages.capacity_compile`

- Admin-side capacity planning exists:
  - `admin/capacity_plane.py` computes the typed plan payload
  - `admin/app.py` exposes quartermaster/cockpit data
  - `tests/test_capacity_plane.py` exists

- Controller work has started:
  - quartermaster env/cache constants were added in `controller/app.py`
  - `quartermaster_capacity_plan()` was added
  - `quartermaster_target_lane_for_decision()` was added
  - `plan_candidate_launch()` was partially updated to consult quartermaster before selecting an account
  - `execute_project_slice()` now includes `decision_meta["quartermaster"]`

## Critical current state

The current controller integration is only partially finished and must be treated as unverified work in progress.

Important details:

- `controller/app.py` has live edits for quartermaster gating, but this slice has not been completed or validated.
- No targeted tests were added yet for the new gating path in this session.
- No verification was run after the latest controller edits in this session.
- The handoff from 2026-03-20 was stale and referred to finished admin work only; this file now replaces that stale context.

## Immediate next slice

Resume in this order:

1. Finish the quartermaster controller gate in `controller/app.py`.
2. Add targeted tests in `tests/test_controller_routing.py`.
3. Run syntax + targeted unit verification.
4. Only after that continue with deeper fleet-wide enforcement of the new capacity plane.

## Known unfinished controller work

The next session should inspect these areas first:

- `controller/app.py`
  - quartermaster config/cache helper section near the EA cache helpers
  - `plan_candidate_launch()`
  - `execute_project_slice()` decision metadata block

Expected completion work:

- make the quartermaster gate robust when the plan is missing, stale, or partially populated
- confirm the lane-to-target mapping is correct for:
  - `core`
  - `core_authority`
  - `core_booster`
  - `core_rescue`
  - `review_light`
  - `review_shard`
  - `jury`
  - `audit_shard`
  - cheap lanes that should fold into booster capacity
- ensure blocked launches move projects into `waiting_capacity` with a useful reason
- ensure successful launches persist quartermaster decision metadata into `spider_decisions.decision_meta_json`
- check that the current helper does not fail on unexpected `lane_targets` value shapes

## Tests that still need to be written or finished

Add targeted coverage in `tests/test_controller_routing.py` for at least:

- `plan_candidate_launch()` returns `None` and sets `waiting_capacity` when quartermaster returns zero remaining capacity for the selected target lane
- `plan_candidate_launch()` still proceeds when quartermaster reports remaining capacity
- `execute_project_slice()` persists quartermaster metadata in `spider_decisions`
- fallback behavior when quartermaster data is unavailable and runtime cache is empty

## Verification that should run first

Run these before taking the next architectural slice:

```bash
python3 -m py_compile controller/app.py quartermaster/app.py admin/capacity_plane.py tests/test_controller_routing.py tests/test_capacity_plane.py
python3 -m unittest -q tests.test_controller_routing tests.test_capacity_plane tests.test_admin_forecast tests.test_codexea_route tests.test_codexea_shim
git diff --check
```

If the controller gate is changed materially, also check the quartermaster container wiring and admin exposure:

```bash
python3 -m py_compile admin/app.py
```

## Repo state worth knowing

The worktree is dirty and contains a large in-flight fleet-design batch. Do not assume only one file changed.

Current modified or new areas include:

- `controller/app.py`
- `admin/app.py`
- `admin/consistency.py`
- `admin/readiness.py`
- `admin/capacity_plane.py`
- `config/routing.yaml`
- `config/policies.yaml`
- `config/projects/core.yaml`
- `config/projects/fleet.yaml`
- `config/accounts.yaml.example`
- `docker-compose.yml`
- `runtime.env.example`
- `scripts/codexea_route.py`
- `tests/test_controller_routing.py`
- `tests/test_capacity_plane.py`
- several deployment/bootstrap scripts

Also note:

- `quartermaster/__pycache__/app.cpython-312.pyc` is present as an untracked file and should not be committed.

## Resume posture

Do not restart from the old admin handoff. The correct resume point is the unfinished quartermaster controller gate and its verification.

After the gate and tests are solid, the next larger slices are:

- enforce capacity-plane decisions more broadly in scheduler behavior
- connect review/audit backpressure more explicitly to dispatch throttling
- keep `core_authority` scarce and move bulk implementation pressure into `core_booster`
- continue turning the new lane topology from config-only truth into runtime truth
