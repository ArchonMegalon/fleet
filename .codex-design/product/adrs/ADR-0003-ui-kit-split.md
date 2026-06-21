# ADR-0003: UI Kit Split Creates the Shared UI Boundary

Date: 2026-03-10

Status: accepted

## Context
- The split order calls for `chummer6-ui-kit` immediately after the play split.
- The milestone registry says the next clean split is a package-only shared UI boundary.
- The ownership matrix and review templates already define ui-kit as tokens, themes, shell chrome, and accessibility primitives, and forbid DTOs, HTTP clients, storage, and rules math there.

## Decision
- `chummer6-ui-kit` is the package-only shared UI boundary for presentation and play.
- It owns design tokens, themes, shell chrome, accessibility primitives, state badges, and cross-head visual building blocks.
- It does not own domain DTOs, HTTP clients, local storage logic, sync state, or runtime rules behavior.
- Shared visual primitives must move into `chummer6-ui-kit` instead of being duplicated between presentation and play.

## Consequences
- Presentation and play can evolve independently without re-forking design-system code.
- UI reuse happens through package versioning rather than through copy-paste or repo-to-repo source imports.
- Domain or service concerns introduced into ui-kit are review-blocking violations because they break the intended seam for later repo extraction.
