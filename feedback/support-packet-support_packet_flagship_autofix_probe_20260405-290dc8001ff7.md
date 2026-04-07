# Harden OODA truth sync and shard ownership isolation

Packet ID: support_packet_flagship_autofix_probe_20260405
Packet Kind: product_gap
Status: accepted
Target Repo: fleet

## Action Request
- Treat this support packet as a bounded follow-up for the owning repo.
- Apply the repo-local product, docs, or policy change needed to close the issue described below.
- Update the smallest durable proof, regression check, or public-facing artifact that demonstrates the fix.

## Summary
Keep aggregate operator truth aligned with the live five-shard flagship runtime and avoid late-shard frontier collapse.

## Packet Context
- Reason: A hard-flagship fleet cannot undercount live shards or silently drop the late operator/autofix shard when unique frontier slices are exhausted.
- Exit condition: Published OODA and flagship readiness stay synchronized with the live shard topology, and late shards retain a bounded actionable frontier instead of idling.
- Primary lane: product
- Change class: type_a
- Release channel: internal
- Head: fleet
- Platform: linux
- Arch: x64
- Install truth state: repo_local_followup
- Fixed version: 
- Fixed channel: 
- Fix confirmation: pending_followup

## Affected Canon Files
- /docker/fleet/scripts/chummer_design_supervisor.py
- /docker/fleet/controller/app.py

## Recovery Path
- Action: inspect_operator_truth
- Href: /fleet
- Reason: The fleet operator loop should immediately surface and consume this fix slice.
