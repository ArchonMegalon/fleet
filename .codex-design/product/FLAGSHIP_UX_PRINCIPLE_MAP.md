# Flagship UX Principle Map

## Purpose

This file links flagship UX promises to the real user journeys and surface owners.
It exists so onboarding, safety, closure, and recovery can be judged as one product contract instead of shard-local taste.

This map is the canonical closeout target for:

* `FLAGSHIP_RELEASE_ACCEPTANCE.yaml` axis `primary_path_clarity`
* `FLAGSHIP_RELEASE_ACCEPTANCE.yaml` axis `trust_and_recovery`
* `METRICS_AND_SLOS.yaml` scorecard `flagship_surface_coherence`

## Core principles

### 1. One primary route

Every major user job exposes one obvious primary path and one bounded fallback story.
Fallbacks may preserve continuity, but they must not silently outrank the preferred route.

### 2. Recovery tells the next safe action

Recovery copy must tell the user what happened, what is safe, and what to do next.
Raw system state alone is not enough.

### 3. Safety is visible before commitment

Rule-environment drift, missing packages, risky publish posture, account gates, community-rule conflicts, and recovery-risk states must be explicit before the user commits trust.

### 4. Closure is reporter-facing

Support and fix posture are not closed when code lands.
Closure only counts when the user's visible route, channel, or support state changed.

### 5. One product story across desktop, hosted, and mobile

Desktop, Hub, and mobile surfaces may differ in form, but they must not disagree about route authority, safety, release truth, or recovery posture.

## Journey map

| Journey | Primary promise | Onboarding route | Safety posture | Recovery route | Closure route | Owner repos |
|---|---|---|---|---|---|---|
| Build | Create or refine a runner without mystery math. | Guided workbench-first entry with one primary builder path. | Active ruleset, preset, amend-package, legality, and active-effect posture visible before commit. | Explain drawer, compare flow, and explicit rule-environment repair path. | Build receipts and support packet linkage when calculation trust fails. | `chummer6-ui`, `chummer6-core` |
| Explain | Understand why a number or legality result changed. | Explain affordance appears where users ask "why?". | Explain must cite source anchor, effect chain, and active rule environment. | Calculation report route and guided support packet when explain is insufficient. | Reporter sees fix, known-issue, or bounded rationale on the same route family. | `chummer6-core`, `chummer6-ui`, `chummer6-hub` |
| Run | Keep runner, crew, campaign, and live session truth coherent. | Claimed-device and live-session routes restore into the right campaign space. | Live/stale/offline/conflict posture must be visible before compute or action. | Reconnect, replay, sync-conflict, and rule-pack mismatch guidance. | Run closeout, support history, and dossier continuity remain linked. | `chummer6-mobile`, `chummer6-hub`, `chummer6-core` |
| Publish | Turn grounded packets and recaps into polished artifacts. | Preview-first publishing route with one clear publish action. | Provenance, compatibility, privacy, and preview posture explicit before publish. | Retry, rollback, and draft-preserving fallback for failed publication or media generation. | Published artifact keeps manifest/provenance and user-visible publication truth aligned. | `chummer6-media-factory`, `chummer6-hub-registry`, `chummer6-hub` |
| Improve | Report pain, follow status, and trust whether the product improved. | Reachable crash, bug, feedback, and support routes from product and public surfaces. | Known-issue, channel, head, and route posture must match release truth. | Next safe action, workaround, release ETA posture, and support escalation path. | Reporter-facing fix status only advances when release truth reaches the reporter's channel. | `chummer6-hub`, `chummer6-hub-registry`, `chummer6-ui` |
| Join | Find the right table, prove fit, and enter with the right runner. | Quickstart and open-run discovery stay first-class. | Community rule environment, preflight result, and table contract visible before apply. | Fail/warn/blocked reasons with next safe action and support path. | Acceptance, scheduling, and meeting handoff stay coherent with run truth. | `chummer6-hub`, `chummer6-mobile`, `chummer6-core` |

## Cross-surface handoff rules

### Desktop to Hub

* Download, install, claim, support, and fix messaging must describe the same release and head posture.
* Desktop must never send the user to a hosted route that contradicts its local recovery state.

### Hub to mobile/play

* Hosted session and community routes must project the same rule environment, campaign identity, and recovery truth that mobile/play surfaces consume.

### Public to private support

* Public known-issue, help, and status copy must match private case and release truth.
* Public closure wording may not outrun reporter-channel release availability.

## Canonical journey refs

* `USER_JOURNEYS.md`
* `journeys/install-and-update.md`
* `journeys/claim-install-and-close-a-support-case.md`
* `journeys/build-and-inspect-a-character.md`
* `journeys/rejoin-after-disconnect.md`
* `journeys/recover-from-sync-conflict.md`
* `journeys/run-a-campaign-and-return.md`
* `journeys/publish-a-grounded-artifact.md`
* `journeys/organize-a-community-and-close-the-loop.md`
* `journeys/find-and-join-an-open-run.md`

## Rule

If a release-ready claim depends on clarity, recovery, or closure across more than one repo, this map must remain truthful before the claim may advance.
