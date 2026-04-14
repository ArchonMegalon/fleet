# Product Governor Readiness Planes

Generated: 2026-04-12T10:55:00Z
Priority: high

## Why this exists

Fleet now publishes separate structural and flagship product-health planes. The remaining work is to make those planes drive the dashboard and queue narratives instead of letting structural green read like flagship replacement.

## Required next work

- Use the published readiness planes in product-governor surfaces:
  - `structural_ready`
  - `flagship_ready`
  - `veteran_ready`
  - `primary_route_ready`
  - `dense_workbench_ready`
- Pull in screenshot, familiarity, and task-speed evidence alongside milestone and journey truth.
- Do not let `remaining_milestones: []` or `uncovered_scope_count=0` imply Chummer5a replacement readiness.
- Publish one clear product-governor view that shows which flagship planes are still failing.

## Governing design sources

- `/docker/chummercomplete/chummer-design/products/chummer/FLAGSHIP_PARITY_REGISTRY.yaml`
- `/docker/chummercomplete/chummer-design/products/chummer/DENSE_WORKBENCH_BUDGET.yaml`
- `/docker/chummercomplete/chummer-design/products/chummer/VETERAN_FIRST_MINUTE_GATE.yaml`
- `/docker/chummercomplete/chummer-design/products/chummer/PRIMARY_ROUTE_REGISTRY.yaml`
