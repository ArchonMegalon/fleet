# ADR-0004: Hub Registry Split Owns Catalog and Publication State

Date: 2026-03-10

Status: accepted

## Context
- The split order places `chummer6-hub-registry` after `chummer6-ui-kit`.
- Group blockers and auditor output already recommend a dedicated registry repo once contract-plane preconditions are stable.
- The ownership matrix defines hub-registry as the owner of artifacts, publication, moderation, and runtime-bundle heads, and forbids AI routing, Spider, relay, and media rendering there.

## Decision
- `chummer6-hub-registry` becomes the canonical owner for immutable artifact catalog data, publication workflow state, moderation state, installs, reviews, and runtime-bundle head metadata.
- `chummer6-hub` retains hosted orchestration, identity, session relay, Spider, approvals, and play API aggregation, but sheds registry persistence internals as the split lands.
- Registry contracts and catalog lifecycle APIs are extracted as the boundary between run-services and hub-registry before the repo split is considered complete.
- Media rendering and AI orchestration remain outside hub-registry and continue toward their own future seams.

## Consequences
- Publication and moderation behavior stop competing with hosted orchestration priorities inside run-services.
- Review and worker guidance can treat registry ownership drift as a first-class defect rather than as an implementation detail.
- The later `chummer6-media-factory` split stays viable because hub-registry owns bundle heads and catalog truth, not rendering internals.
