# ADR-0001: Contract-Plane Canon Is Package-Owned and Design-First

Date: 2026-03-10

Status: accepted

## Context
- Chummer is splitting from a multi-head runtime into repo-owned surfaces with shared DTO and event contracts.
- The architecture canon already requires cross-repo DTO ownership to be explicit and package-based.
- The split order starts with `Chummer.Engine.Contracts`, then `Chummer.Play.Contracts`, because later repo splits depend on stable contract ownership.
- Review templates already treat contract bypasses as P1 defects for core and run-services.

## Decision
- `Chummer.Engine.Contracts` is the only canonical package for engine/runtime DTOs, reducer-facing events, explain payloads, and provenance shapes shared across repos.
- `Chummer.Play.Contracts` is the only canonical package for play-shell API DTOs, sync payloads, install/session shell requests, and other play-specific cross-repo contracts.
- No repo may publish or normalize cross-repo DTOs outside those contract packages.
- Contract changes land in `chummer6-design` first, then mirror into code repos through the approved sync manifest before implementation starts.

## Consequences
- Core remains the authority for engine semantics, but package consumers depend on contracts rather than on core implementation assemblies.
- Run-services may aggregate play APIs, but it does not become the long-term owner of play contract shapes.
- Presentation, play, ui-kit, and hub-registry must consume contract packages and must not fork transport or DTO canon locally.
- Contract drift across repos is a design failure and a P1 review finding.
