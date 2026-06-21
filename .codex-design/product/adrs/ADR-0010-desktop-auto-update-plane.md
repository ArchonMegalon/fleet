# ADR-0010: Desktop Auto-Update Is Registry-Backed and UI-Applied

Date: 2026-03-24

Status: accepted

## Context

* The current release canon already splits updater truth across UI, Fleet, Hub, and Registry rather than letting one repo quietly own everything.
* `chummer6-ui` already owns desktop packaging, installer delivery, and updater integration inside desktop heads.
* `chummer6-hub-registry` already owns promoted release channels, install and update metadata, and updater-feed metadata.
* The missing piece is a first-class desktop update plane that defines install media versus machine update payloads, client apply ownership, rollback expectations, and public-channel auth rules.

## Decision

* Chummer gains a first-class desktop auto-update lane with canonical design in `DESKTOP_AUTO_UPDATE_SYSTEM.md`.
* `chummer6-ui` owns updater client behavior, local install and channel state, staging, apply helpers, relaunch flow, and rollback-window bookkeeping.
* `chummer6-hub-registry` owns promoted desktop release heads, install media records, machine update payload records, update-feed vocabulary, rollout, pause, and revoke state, and embedded runtime-bundle references.
* `fleet` owns build, sign, notarize, and promote orchestration plus evidence, but clients do not consult Fleet as the runtime update authority.
* `chummer6-hub` may render downloads and broker gated-channel access, but it does not become the public update-feed authority.
* The first public updater wave is atomic: app shell and embedded runtime bundle advance together as one promoted desktop head.
* Public desktop update checks must work without a Hub account session for public channels.

## Consequences

* Human install media and machine update payloads are modeled as distinct artifact classes.
* The UI repo must grow an explicit apply-helper path instead of treating updater behavior as an installer side effect.
* The registry package must grow desktop release-head and update-feed DTOs rather than leaving feed shape as helper-script folklore.
* Differential or runtime-only desktop updates are delayed until compatibility proof and milestone truth explicitly allow them.
* Hub remains a projection and guidance surface rather than a shadow release-channel system.
