# ADR-0008: Release Authority Stays Split Across Owning Repos

Date: 2026-03-24

Status: accepted

## Context

- The program now has explicit release canon for runtime bundles, installers, registry promotion, public downloads, and release visuals.
- Multiple repos participate in the release path, and the split is easy to blur when a release lane gets urgent.
- The policy already lived in `RELEASE_PIPELINE.md`, but the authority split did not yet have ADR-grade memory.

## Decision

- `chummer6-core` owns runtime-bundle production and fingerprints.
- `chummer6-ui` owns desktop packaging, installer recipes, and updater integration inside the desktop head.
- `fleet` owns release orchestration, verify gates, promotion evidence, and release-matrix expansion.
- `chummer6-hub-registry` owns promoted channels, installer and update metadata, compatibility truth, and runtime-bundle heads.
- `chummer6-hub` owns public downloads UX and account-aware install guidance by consuming registry truth.
- `chummer6-media-factory` may render release visuals, but it does not own installers, feeds, or release-channel policy.

## Consequences

- No single repo gets to quietly become the release monolith.
- Update-feed truth must never outrun registry promotion truth.
- Release debates now route through an explicit authority record instead of only through milestone text.
