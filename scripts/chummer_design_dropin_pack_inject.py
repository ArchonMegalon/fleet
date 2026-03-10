#!/usr/bin/env python3
from __future__ import annotations

import textwrap
from pathlib import Path


DESIGN_FEEDBACK_ROOT = Path("/docker/chummercomplete/chummer-design/feedback")
GROUP_FEEDBACK_ROOT = Path("/docker/fleet/state/groups/chummer-vnext/feedback")
FILENAME = "2026-03-10-lead-dev-design-dropin-pack.md"


DROPIN_PACK = textwrap.dedent(
    r"""
    # Lead-dev drop-in pack: make `chummer-design` catch up to the live repo graph

    Date: 2026-03-10
    Audience: `chummer-design`
    Status: injected fleet feedback

    Right now the design repo has the right shape but not enough truth. The public repo graph already includes `chummer-design`, `chummer-core-engine`, `chummer-presentation`, `chummer.run-services`, `chummer-play`, `chummer-ui-kit`, `chummer-hub-registry`, and `chummer-media-factory`, but `chummer-design` still has only 5 commits, still keeps media-factory-specific docs at the repo root, and its canonical product files are still effectively stubs or near-stubs.

    There are also two concrete downstream drifts the design repo should now govern explicitly:

    * `chummer-play` still says it consumes `Chummer.Contracts` in its README while its build props point at `Chummer.Engine.Contracts`, `Chummer.Play.Contracts`, and `Chummer.Ui.Kit`.
    * `chummer.run-services` still duplicates the same session relay/runtime bundle DTO family across `Chummer.Play.Contracts` and `Chummer.Run.Contracts`, while `MediaContracts.cs` still imports both play-side and media-side contract namespaces directly.

    So the fastest way to help `chummer-design` catch up is: make central canon current first, then use it to force repo-local cleanup.

    ---

    ## FILE: `README.md`

    ```md
    # chummer-design

    Canonical cross-repo design front door for Project Chummer.

    This repo is the **lead designer** for the Chummer program. Cross-repo architecture, package ownership, milestone truth, and blocker truth become canonical here before being mirrored into worker-facing code repos.

    ## What this repo owns

    - product vision
    - repo graph and dependency rules
    - repo ownership boundaries
    - package and contract canon
    - milestone and blocker truth
    - mirror/sync policy
    - repo implementation scopes
    - generic review context
    - architectural drift publication

    ## What this repo must not become

    - a code repo
    - a second work queue competing with code repos
    - a scratchpad full of orphan design docs
    - a place where repo-local README text silently overrules architecture

    ## Canonical tree

    - `products/chummer/README.md`
    - `products/chummer/VISION.md`
    - `products/chummer/ARCHITECTURE.md`
    - `products/chummer/ROADMAP.md`
    - `products/chummer/LEAD_DESIGNER_OPERATING_MODEL.md`
    - `products/chummer/OWNERSHIP_MATRIX.md`
    - `products/chummer/PROGRAM_MILESTONES.yaml`
    - `products/chummer/CONTRACT_SETS.yaml`
    - `products/chummer/GROUP_BLOCKERS.md`
    - `products/chummer/EXTERNAL_TOOLS_PLANE.md`
    - `products/chummer/projects/*.md`
    - `products/chummer/review/*.md`
    - `products/chummer/sync/*.yaml`

    ## Root-level rule

    Allowed at repo root:
    - `README.md`
    - `AGENTS.md`
    - `WORKLIST.md`
    - generic repo-management scripts
    - generic repo metadata

    Not allowed at repo root:
    - product-specific design docs that belong under `products/chummer/*`
    - repo-specific architecture docs for code repos
    - orphan milestone docs
    - duplicate product canon

    ## Workflow

    1. Designers, architects, contract stewards, and auditors update this repo first.
    2. Approved changes become canonical here.
    3. Fleet mirrors the relevant subset into code repos under `.codex-design/*`.
    4. Workers implement from repo-local mirrors.
    5. Auditors publish drift and blockers back here.

    ## Precedence

    When documents disagree, precedence is:

    1. `products/chummer/LEAD_DESIGNER_OPERATING_MODEL.md`
    2. `products/chummer/ARCHITECTURE.md`
    3. `products/chummer/OWNERSHIP_MATRIX.md`
    4. `products/chummer/CONTRACT_SETS.yaml`
    5. `products/chummer/PROGRAM_MILESTONES.yaml`
    6. `products/chummer/projects/*.md`
    7. mirrored `.codex-design/*` in code repos
    8. repo README files
    9. code comments

    ## Done rule

    A cross-repo design change is not done until:
    - central canon is updated
    - milestone and blocker truth is updated if sequencing/risk changed
    - package/contract registry is updated if shared DTO ownership changed
    - mirror rules are updated if repo coverage changed
    - repo implementation scopes are updated where impacted
    ```

    ---

    ## FILE: `products/chummer/README.md`

    ```md
    # Project Chummer

    Project Chummer is a multi-repo modernization of the legacy Chummer 5 application into:

    - a deterministic rules/runtime engine
    - a builder/workbench/browser/desktop head
    - a player/GM play-mode shell
    - a hosted orchestration plane
    - a shared design system
    - a registry/publication service
    - a media execution service
    - a canonical design/governance repo

    ## Read in this order

    1. `VISION.md`
    2. `ARCHITECTURE.md`
    3. `OWNERSHIP_MATRIX.md`
    4. `ROADMAP.md`
    5. `PROGRAM_MILESTONES.yaml`
    6. `CONTRACT_SETS.yaml`
    7. `GROUP_BLOCKERS.md`
    8. `EXTERNAL_TOOLS_PLANE.md`
    9. `projects/*.md`

    ## Active product repos

    ### `chummer-design`
    Lead-designer repo. Owns cross-repo canonical design truth.

    ### `chummer-core-engine`
    Deterministic rules/runtime engine. Owns mechanics truth, explain canon, runtime bundles, reducer semantics, and engine contracts.

    ### `chummer-presentation`
    Workbench/browser/desktop head. Owns builder, inspector, compare, admin, moderation, publication, and large-screen operator UX.

    ### `chummer-play`
    Player and GM play-mode shell. Owns mobile/PWA/session UX, offline ledger, sync client, and play-safe live-session surfaces.

    ### `chummer.run-services`
    Hosted orchestration plane. Owns identity, relay, approvals, memory, Coach/Spider/Director orchestration, delivery, and service policy.

    ### `chummer-ui-kit`
    Shared design system package. Owns tokens, themes, shell primitives, accessibility primitives, and reusable Chummer UI patterns.

    ### `chummer-hub-registry`
    Artifact catalog and publication system. Owns immutable artifact metadata, publication workflow, moderation state, installs, reviews, compatibility, and runtime-bundle head metadata.

    ### `chummer-media-factory`
    Dedicated render and asset-lifecycle service. Owns render jobs, manifests, previews, signed access, provider adapters, and retention/archive execution for media assets.

    ## Reference-only repo

    ### `chummer5a`
    Legacy oracle for migration, regression fixtures, and compatibility reference. Not part of the vNext ownership graph.

    ## Adjacent repos

    - `fleet` — worker orchestration/control plane
    - `executive-assistant` — governed assistant/runtime reference and LTD inventory

    ## Immediate design priorities

    1. Make `chummer-design` trustworthy as the lead-designer repo.
    2. Freeze package and contract canon.
    3. Complete the play split with package-only dependency discipline.
    4. Grow `chummer-ui-kit` into the real shared UI boundary.
    5. Complete `chummer-hub-registry` and `chummer-media-factory` extraction.
    6. Shrink `chummer.run-services` toward orchestration-only ownership where appropriate.
    7. Purify `chummer-core-engine` into a true deterministic engine repo.
    8. Finish product surfaces and release hardening.
    ```

    ---

    ## FILE: `products/chummer/VISION.md`

    ```md
    # Vision

    ## North star

    Project Chummer becomes a complete digital Shadowrun operating environment built on hard boundaries.

    The finished product is:

    - a deterministic rules and character engine
    - a workbench for building, inspecting, comparing, publishing, and moderating
    - a session OS for players and GMs across desktop, web, and mobile
    - a hosted campaign and assistant orchestration plane
    - a reusable registry/publication ecosystem
    - a bounded media studio for packets, portraits, previews, and video
    - a fully explainable product where important derived values can always be grounded

    ## Product promises

    ### 1. Engine truth is singular
    Only `chummer-core-engine` owns canonical rules math and reducer semantics.

    ### 2. Explain Everywhere is real
    Derived values, legality outcomes, and important state transitions can be inspected with structured provenance.

    ### 3. Workbench and play stay separate
    `chummer-presentation` is the workbench/browser/desktop head.
    `chummer-play` is the live play/mobile/PWA head.

    ### 4. Hosted orchestration is not rules truth
    `chummer.run-services` owns identity, relay, memory, approvals, and assistant orchestration.
    It does not own duplicate mechanics truth.

    ### 5. Shared UI is a package
    `chummer-ui-kit` becomes the only shared cross-head visual boundary.

    ### 6. Registry and media are real service boundaries
    Registry/publication/install truth belongs in `chummer-hub-registry`.
    Render execution and media asset lifecycle belong in `chummer-media-factory`.

    ### 7. External tools help, but do not own truth
    Third-party tools may assist, project, render, summarize, or archive.
    They do not become canonical systems of record.

    ### 8. Legacy is an oracle
    `chummer5a` exists for migration and regression confidence, not to compete architecturally with vNext.

    ## Finished-state experience

    ### Player
    A player can build, sync, inspect, and play from a modern shell that works across devices and survives intermittent connectivity.

    ### GM
    A GM can run live sessions, inspect grounded state, receive Spider/Coach support, review assets, and manage flow without juggling unrelated tools.

    ### Creator / publisher
    A creator can prepare artifacts, publish content, manage installs, inspect compatibility, and work through governed review and moderation flows.

    ### Maintainer / operator
    A maintainer can answer:
    - which repo owns this feature or DTO?
    - which package should be consumed?
    - which milestone is blocking progress?
    - which repo is drifting?
    - which external tool is allowed here?
    - which document wins if local docs disagree?

    ## Anti-vision

    Project Chummer is not:
    - one giant repo pretending to be many
    - an AI-first product with fuzzy authority
    - a design system copied into every frontend
    - a rules engine hidden in UI or service code
    - a registry buried inside orchestration services
    - a media generator welded directly into clients
    - a design repo full of one-line placeholders
    ```

    ---

    ## FILE: `products/chummer/ARCHITECTURE.md`

    ````md
    # Architecture

    ## Core rules

    ### Rule 1 — central design wins
    Cross-repo product truth becomes canonical in `chummer-design`.

    ### Rule 2 — shared DTOs are package-owned
    Cross-repo DTOs must have:
    - a canonical package
    - an owning repo
    - a versioning rule
    - a deprecation rule

    No source-copy mirrors of canonical contract families are allowed.

    ### Rule 3 — engine semantics live in core
    `chummer-core-engine` owns:
    - rules math
    - runtime fingerprints
    - runtime bundles
    - explain provenance
    - semantic session mutation / reducer truth
    - engine contract canon

    ### Rule 4 — hosted orchestration lives in run-services
    `chummer.run-services` owns:
    - identity
    - relay
    - approvals
    - memory
    - Coach / Spider / Director orchestration
    - delivery and notifications
    - play API aggregation
    - service policy and route management

    It does not own canonical mechanics.
    It must not own registry persistence after the registry split is complete.
    It must not own render execution after the media split is complete.

    ### Rule 5 — workbench and play stay separate
    `chummer-presentation` owns builder/workbench/browser/desktop UX.
    `chummer-play` owns live play/mobile/PWA/player/GM shell UX.

    ### Rule 6 — UI-kit is the only shared UI boundary
    Shared visual tokens, shell primitives, accessibility primitives, and Chummer-specific reusable UI components belong in `chummer-ui-kit`.

    ### Rule 7 — registry is a service boundary
    Artifact catalog, publication workflow, moderation state, installs, reviews, compatibility, and runtime-bundle heads belong in `chummer-hub-registry`.

    ### Rule 8 — media is a service boundary
    Render jobs, manifests, previews, provider adapters, signed asset access, retention, and archive execution belong in `chummer-media-factory`.

    ### Rule 9 — external tools are an explicit plane
    Third-party tools sit behind Chummer-owned adapters.
    They may assist, render, notify, summarize, visualize, or archive.
    They may not become canonical truth for:
    - rules
    - session state
    - approval state
    - registry/publication/install state
    - artifact manifests
    - memory/canon state

    ### Rule 10 — legacy is reference-only
    `chummer5a` is a migration/regression oracle, not an active vNext ownership lane.

    ## Repo graph

    ```text
    chummer-design
      └─ governs every Chummer repo

    chummer-core-engine
      └─ publishes Chummer.Engine.Contracts

    chummer-ui-kit
      └─ publishes Chummer.Ui.Kit

    chummer-hub-registry
      └─ publishes Chummer.Hub.Registry.Contracts

    chummer-media-factory
      └─ publishes Chummer.Media.Contracts

    chummer.run-services
      ├─ publishes Chummer.Play.Contracts
      ├─ publishes Chummer.Run.Contracts
      ├─ consumes Chummer.Engine.Contracts
      ├─ consumes Chummer.Hub.Registry.Contracts
      └─ consumes Chummer.Media.Contracts

    chummer-presentation
      ├─ consumes Chummer.Engine.Contracts
      ├─ consumes Chummer.Ui.Kit
      └─ consumes hosted projections from run-services / hub-registry

    chummer-play
      ├─ consumes Chummer.Engine.Contracts
      ├─ consumes Chummer.Play.Contracts
      ├─ consumes Chummer.Ui.Kit
      └─ consumes hosted play projections from run-services
    ```

    ## Allowed dependency directions

    ### Allowed

    * presentation -> engine contracts
    * presentation -> ui-kit
    * play -> engine contracts
    * play -> play contracts
    * play -> ui-kit
    * run-services -> engine contracts
    * run-services -> play contracts
    * run-services -> run contracts
    * run-services -> registry contracts
    * run-services -> media contracts
    * media-factory -> media contracts
    * hub-registry -> registry contracts

    ### Forbidden

    * core -> presentation
    * core -> play
    * core -> run-services
    * play -> presentation implementation source
    * presentation -> play implementation source
    * ui-kit -> domain DTO packages
    * media-factory -> play contracts
    * media-factory -> campaign/session DB semantics
    * run-services -> duplicate engine semantic DTOs once canonical owner is set

    ## New split acceptance gate

    A new repo split is not architecturally accepted until all of the following exist in `chummer-design`:

    * active repo entry in `products/chummer/README.md`
    * ownership row in `OWNERSHIP_MATRIX.md`
    * implementation scope in `projects/*.md`
    * mirror entry in `sync/sync-manifest.yaml`
    * contract/package entry in `CONTRACT_SETS.yaml` if shared contracts are involved
    * milestone entries in `PROGRAM_MILESTONES.yaml`
    * blocker update in `GROUP_BLOCKERS.md` if risk changed

    ## Drift conditions

    A repo is drifting when any of the following is true:

    * its README contradicts central canon
    * it owns a package it is not listed as owning
    * `.codex-design/*` is missing or stale in an active worker-driven repo
    * it duplicates a contract family owned elsewhere
    * it locally re-grows a split boundary instead of consuming the package/service

    ````

    ---

    ## FILE: `products/chummer/ROADMAP.md`

    ```md
    # Roadmap

    This roadmap carries the program past the split wave and all the way to finished-state release.

    ## Phase A — design and package canon

    ### A0
    Make `chummer-design` trustworthy as the lead-designer repo.

    ### A1
    Freeze engine contract canon.

    ### A2
    Freeze play contract canon.

    ### A3
    Freeze run orchestration contract canon.

    ### A4
    Formalize the external tools plane.

    ## Phase B — surface split completion

    ### B0
    Turn `chummer-play` into a real product head with offline ledger and real hosted play seams.

    ### B1
    Turn `chummer-ui-kit` into the real shared visual boundary.

    ### B2
    Purify `chummer-presentation` into workbench/browser/desktop only.

    ## Phase C — service extraction

    ### C0
    Complete the registry split into `chummer-hub-registry`.

    ### C1
    Complete the media split into `chummer-media-factory`.

    ### C2
    Shrink `chummer.run-services` into orchestration-first ownership.

    ## Phase D — truth and session canon

    ### D0
    Complete explain canon.

    ### D1
    Complete semantic session event canon.

    ### D2
    Complete runtime bundle canon.

    ## Phase E — product completion

    ### E0
    Complete workbench.

    ### E1
    Complete play shell.

    ### E2
    Complete Hub/publication/discovery/install flows.

    ### E3
    Complete governed assistant plane.

    ### E4
    Complete media plane.

    ## Phase F — hardening and release

    ### F0
    Accessibility, localization, and performance.

    ### F1
    Observability, replay safety, and DR.

    ### F2
    Legacy migration certification.

    ### F3
    Release complete.

    ## Repo milestone spines

    ### `chummer-design`
    D0 bootstrap -> D1 contract registry -> D2 blocker registry -> D3 mirror discipline -> D4 release governance -> D5 ADR memory -> D6 finished lead designer

    ### `chummer-core-engine`
    E0 purification -> E1 runtime DTO canon -> E2 explain canon -> E3 session reducer canon -> E4 ruleset ABI -> E5 explain backend -> E6 Build Lab backend -> E7 migration certification -> E8 hardening -> E9 finished engine

    ### `chummer-presentation`
    P0 ownership correction -> P1 package-only UI consumption -> P2 workbench shell -> P3 explain UX -> P4 Build Lab UX -> P5 publish/admin/moderation UX -> P6 platform parity -> P7 accessibility/performance -> P8 finished workbench

    ### `chummer-play`
    L0 package canon -> L1 local ledger/sync -> L2 player shell -> L3 GM shell -> L4 relay/runtime convergence -> L5 Coach/Spider surfaces -> L6 mobile/PWA polish -> L7 observer/cross-device continuity -> L8 hardening -> L9 finished play shell

    ### `chummer-ui-kit`
    U0 governance -> U1 token canon -> U2 primitives -> U3 shell chrome -> U4 dense-data controls -> U5 Chummer-specific patterns -> U6 accessibility/localization -> U7 catalog/visual regression -> U8 release discipline -> U9 finished design system

    ### `chummer-hub-registry`
    H0 contract canon -> H1 artifact domain -> H2 publication drafts -> H3 install/compatibility engine -> H4 search/discovery/reviews -> H5 template/style publication -> H6 federation/org channels -> H7 hardening -> H8 finished registry

    ### `chummer-media-factory`
    M0 contract canon -> M1 asset/job kernel -> M2 document rendering -> M3 portrait forge -> M4 bounded video -> M5 template/style integration -> M6 run-services cutover -> M7 storage/DR/scale -> M8 finished media plant

    ### `chummer.run-services`
    R0 shrink reset -> R1 package canon -> R2 identity/campaign core -> R3 play APIs/relay -> R4 skill runtime -> R5 Spider/Director/memory -> R6 orchestration-only registry/media mode -> R7 notifications/docs/delivery -> R8 resilience/compliance -> R9 finished hosted orchestration
    ```

    ---

    ## FILE: `products/chummer/LEAD_DESIGNER_OPERATING_MODEL.md`

    ```md
    # Lead designer operating model

    ## Mission

    This repo exists to make the Chummer program governable.

    It is not a code repo.
    It is not a second backlog.
    It is the place where cross-repo architecture becomes canonical.

    ## Required document classes

    Every active Chummer repo must have:
    - representation in `products/chummer/README.md`
    - an ownership entry
    - a repo implementation scope
    - milestone coverage
    - contract/package coverage if shared packages are involved
    - blocker coverage if the repo participates in release risk
    - mirror coverage in `sync/sync-manifest.yaml`
    - review context coverage

    ## Change taxonomy

    ### Type A — editorial
    Wording only. No architectural effect.

    ### Type B — local scope
    Affects one repo implementation scope only.

    ### Type C — boundary
    Changes repo ownership, dependency direction, or split boundaries.

    ### Type D — contract/package
    Changes canonical package ownership, shared DTO families, compatibility promises, or deprecation windows.

    ### Type E — milestone/blocker
    Changes sequencing, release gates, or group risk.

    Types C, D, and E must update multiple canonical files together.

    ## Mandatory updates by change type

    ### Boundary change must update
    - `ARCHITECTURE.md`
    - `OWNERSHIP_MATRIX.md`
    - affected `projects/*.md`
    - `PROGRAM_MILESTONES.yaml`
    - `GROUP_BLOCKERS.md` if risk changed
    - `sync/sync-manifest.yaml` if mirror coverage changed

    ### Contract/package change must update
    - `CONTRACT_SETS.yaml`
    - `ARCHITECTURE.md` if dependency direction changed
    - affected `projects/*.md`
    - `PROGRAM_MILESTONES.yaml` if sequencing changed
    - `GROUP_BLOCKERS.md` if migration risk changed

    ### New repo split must update
    - `products/chummer/README.md`
    - `ARCHITECTURE.md`
    - `OWNERSHIP_MATRIX.md`
    - `PROGRAM_MILESTONES.yaml`
    - `CONTRACT_SETS.yaml` if package ownership is involved
    - `GROUP_BLOCKERS.md`
    - `projects/<repo>.md`
    - `sync/sync-manifest.yaml`
    - review coverage

    ## Mirror discipline

    Every active worker-driven code repo must receive:
    - product canon mirror
    - repo implementation scope mirror
    - review context mirror

    Missing `.codex-design/*` is a program-level blocker.

    ## Auditor publication rules

    Auditors publish to canonical files, not random scratch notes.

    - milestone truth -> `PROGRAM_MILESTONES.yaml`
    - contract truth -> `CONTRACT_SETS.yaml`
    - blockers -> `GROUP_BLOCKERS.md`
    - boundary findings -> `OWNERSHIP_MATRIX.md` and affected `projects/*.md`

    ## Lead-designer done rule

    `chummer-design` is functioning as lead designer only when:
    - every active repo is represented centrally
    - central canon is deeper than repo-local mirrors
    - mirrors are complete and current
    - blockers are current enough to steer work
    - package ownership is unambiguous
    - milestones are specific enough to gate release decisions
    - no orphan product docs live outside canonical product paths
    ```

    ---

    ## FILE: `products/chummer/OWNERSHIP_MATRIX.md`

    ```md
    # Ownership matrix

    | Repo | Primary mission | Owns | Must not own | Package(s) |
    | --- | --- | --- | --- | --- |
    | `chummer-design` | central design governance | canon, ownership, milestones, blockers, sync, review guidance | production code, duplicate product docs outside canonical tree | none |
    | `chummer-core-engine` | deterministic rules/runtime engine | rules math, runtime bundles, explain canon, reducer truth, engine contract canon | play UI, workbench UI, registry persistence, media execution, hosted orchestration | `Chummer.Engine.Contracts` |
    | `chummer-presentation` | workbench/browser/desktop head | builder, inspector, compare, explain UX, admin/moderation/publication UX | play shell, rule evaluation, offline ledger, render execution | consumes engine + ui-kit |
    | `chummer-play` | live play/mobile/PWA head | player shell, GM shell, offline ledger, sync client, play-safe live-session UX | builder/workbench UX, rules math, provider secrets, publication/moderation | consumes engine + play + ui-kit |
    | `chummer.run-services` | hosted orchestration plane | identity, relay, approvals, memory, Coach/Spider/Director orchestration, delivery, service policy | duplicate mechanics, registry persistence after split, media rendering after split | `Chummer.Play.Contracts`, `Chummer.Run.Contracts` |
    | `chummer-ui-kit` | shared design system | tokens, themes, shell primitives, accessibility primitives, reusable Chummer UI patterns | domain DTOs, HTTP clients, storage, rules math | `Chummer.Ui.Kit` |
    | `chummer-hub-registry` | catalog/publication service | artifacts, publication state, moderation, installs, reviews, compatibility, runtime-bundle heads | relay, Coach/Spider, media rendering, client UX | `Chummer.Hub.Registry.Contracts` |
    | `chummer-media-factory` | render and media asset service | render jobs, manifests, previews, provider adapters, signed access, retention/archive | campaign truth, rules truth, approvals policy, client UX, general orchestration | `Chummer.Media.Contracts` |
    | `chummer5a` | legacy oracle | migration fixtures, regression corpus, compatibility reference | vNext architecture ownership | none |

    ## Ownership violations

    The following are ownership violations:
    - a repo introduces a shared DTO family outside its canonical package
    - run-services regrows registry persistence or media rendering after those splits
    - presentation reclaims play-shell ownership
    - play reimplements rules truth
    - ui-kit gains domain DTOs or service logic
    - engine begins depending on presentation/play/service code
    - design repo becomes so stale that workers must invent architecture locally

    ## External integration ownership

    ### `chummer-design`
    Owns:
    - external-tool classification
    - approved usage policy
    - rollout governance
    - provenance rules
    - system-of-record rules

    ### `chummer.run-services`
    Owns:
    - orchestration-side external integrations
    - reasoning-provider routing
    - approval/docs/survey/automation bridges
    - research/eval/prompt-tooling integrations

    ### `chummer-media-factory`
    Owns:
    - render/archive adapters
    - provider receipts for media work
    - media provenance capture
    - media archive execution

    ### `chummer-presentation` and `chummer-play`
    Must not own:
    - vendor credentials
    - direct provider SDK access
    - direct third-party orchestration
    ```

    ---

    ## FILE: `products/chummer/PROGRAM_MILESTONES.yaml`

    ```yaml
    product: chummer
    last_reviewed: 2026-03-10
    release_track: vnext-foundation

    program_phases:
      - id: A
        title: Design and package canon
        status: in_progress
        goal: Make central design and package ownership trustworthy.
        milestones:
          - id: A0
            title: chummer-design bootstrap complete
            owners: [chummer-design]
            status: open
            exit:
              - Active repo list matches the live repo graph.
              - Media-factory is represented in ownership, milestones, blockers, sync, and project scope.
              - Canonical files are substantive rather than placeholders.
              - Root-level orphan product docs are removed or relocated.

          - id: A1
            title: Engine contract canon
            owners: [chummer-core-engine, chummer-design]
            status: open
            exit:
              - Chummer.Engine.Contracts is the sole canonical engine/shared package.
              - Runtime, explain, and reducer DTO families are owned once.

          - id: A2
            title: Play contract canon
            owners: [chummer.run-services, chummer-play, chummer-design]
            status: open
            exit:
              - Chummer.Play.Contracts has stable ownership and naming.
              - Play consumes package-only seams.
              - No duplicated semantic session DTO families remain across play/run surfaces.

          - id: A3
            title: Run orchestration contract canon
            owners: [chummer.run-services, chummer-design]
            status: open
            exit:
              - Chummer.Run.Contracts owns hosted orchestration DTOs only.
              - Media and registry execution DTOs are not mixed into orchestration families.

          - id: A4
            title: External tools plane canon
            owners: [chummer-design, chummer.run-services, chummer-media-factory]
            status: open
            exit:
              - External tools policy exists centrally.
              - External integrations are assigned to owning repos.
              - System-of-record rules and provenance requirements are documented.

      - id: B
        title: Surface split completion
        status: open
        goal: Finish the play/workbench/UI-kit boundary.
        milestones:
          - id: B0
            title: Play shell becomes real
            owners: [chummer-play]
            status: open
            exit:
              - Real local ledger and sync client exist.
              - Player shell and GM shell reach first usable flows.
              - Play mirror coverage exists under .codex-design.

          - id: B1
            title: UI kit becomes the real shared boundary
            owners: [chummer-ui-kit, chummer-presentation, chummer-play]
            status: open
            exit:
              - Shared tokens, primitives, shell chrome, and state patterns live in Chummer.Ui.Kit.
              - Presentation and play consume the package instead of duplicating shared UI.

          - id: B2
            title: Presentation purified to workbench/browser/desktop
            owners: [chummer-presentation]
            status: open
            exit:
              - No dedicated play/mobile heads remain here.
              - Presentation docs and implementation scopes match split reality.

      - id: C
        title: Service extraction
        status: open
        goal: Isolate registry and media into dedicated repos and shrink run-services.
        milestones:
          - id: C0
            title: Hub registry extraction
            owners: [chummer-hub-registry, chummer.run-services]
            status: open
            exit:
              - Artifact catalog, publication, installs, reviews, and compatibility metadata live behind chummer-hub-registry.
              - Run-services consumes registry contracts rather than owning registry persistence internals.

          - id: C1
            title: Media factory extraction
            owners: [chummer-media-factory, chummer.run-services]
            status: open
            exit:
              - Chummer.Media.Contracts is canonical.
              - Media render execution leaves run-services.
              - Media-factory has source, mirrors, milestones, and integration coverage.

          - id: C1b
            title: Orchestration-side external adapters
            owners: [chummer.run-services]
            status: open
            exit:
              - Approval, docs/help, survey, research, and automation bridges are adapter-based.
              - Provider routes emit Chummer receipts.
              - No client repo owns third-party provider access.

          - id: C1c
            title: Media-side external adapters
            owners: [chummer-media-factory]
            status: open
            exit:
              - Document, preview, route, video, and archive adapters exist behind media-factory.
              - Media provenance is captured in manifests.
              - Provider choice remains switchable and kill-switchable.

          - id: C2
            title: Run-services shrink
            owners: [chummer.run-services]
            status: open
            exit:
              - Registry persistence and media render internals are no longer hosted here.
              - Run-services reads as an orchestrator, not a hidden super-repo.

      - id: D
        title: Truth and session canon
        status: open
        goal: Make semantics authoritative and reusable.
        milestones:
          - id: D0
            title: Explain canon complete
            owners: [chummer-core-engine]
            status: open
            exit:
              - Structured explain traces are authoritative and consumable across product heads.

          - id: D1
            title: Session semantic canon complete
            owners: [chummer-core-engine, chummer.run-services, chummer-play]
            status: open
            exit:
              - Semantic session mutation DTOs have one canonical owner.
              - Transport wrappers do not invent second semantic event families.

          - id: D2
            title: Runtime bundle canon complete
            owners: [chummer-core-engine, chummer.run-services, chummer-play]
            status: open
            exit:
              - Runtime bundles, refresh/rebind flows, and provenance are coherent across engine, services, and clients.

      - id: E
        title: Product completion
        status: open
        goal: Finish the user-facing product once seams are real.
        milestones:
          - id: E0
            title: Workbench complete
            owners: [chummer-presentation]
            status: open
            exit:
              - Builder, compare, explain, publish, moderation, and admin workflows are complete enough for release.

          - id: E1
            title: Play complete
            owners: [chummer-play]
            status: open
            exit:
              - Player and GM shells are complete across supported platforms.

          - id: E2
            title: Hub complete
            owners: [chummer-hub-registry, chummer.run-services, chummer-presentation]
            status: open
            exit:
              - Publication, installs, reviews, discovery, and compatibility are coherent end-to-end.

          - id: E2b
            title: Docs, feedback, and operator projection plane complete
            owners: [chummer.run-services, chummer-design]
            status: open
            exit:
              - Docs/help surfaces are integrated.
              - Feedback loops are integrated.
              - Operator projection boards exist without becoming systems of record.

          - id: E3
            title: Assistant plane complete
            owners: [chummer.run-services]
            status: open
            exit:
              - Coach, Spider, and Director are governed, grounded, and reviewable.

          - id: E4
            title: Media plane complete
            owners: [chummer-media-factory, chummer.run-services]
            status: open
            exit:
              - Documents, portraits, and bounded video are stable service capabilities.

      - id: F
        title: Hardening and release
        status: open
        goal: Reach release-quality operational and user-facing confidence.
        milestones:
          - id: F0
            title: Accessibility, localization, performance
            owners: [chummer-presentation, chummer-play, chummer-ui-kit]
            status: open
            exit:
              - Accessibility and localization are first-class.
              - Performance targets are documented and met.

          - id: F1
            title: Observability, DR, replay safety
            owners: [chummer-core-engine, chummer.run-services, chummer-hub-registry, chummer-media-factory]
            status: open
            exit:
              - Operational runbooks, restore drills, and replay safety are verified.

          - id: F2
            title: Legacy migration certification
            owners: [chummer-core-engine, chummer5a]
            status: open
            exit:
              - Legacy import/export and regression corpus are certified.

          - id: F3
            title: Release complete
            owners: [chummer-design]
            status: open
            exit:
              - All prior phase exits are met.
              - No open red blockers remain.
              - The product vision is complete enough for release.

    current_release_blockers:
      - A0
      - A1
      - A2
      - C1
      - D1
    ```

    ---

    ## FILE: `products/chummer/CONTRACT_SETS.yaml`

    ```yaml
    group_id: chummer-vnext
    last_reviewed: 2026-03-10

    packages:
      - id: Chummer.Engine.Contracts
        owner_repo: chummer-core-engine
        purpose: Deterministic engine/runtime/explain/reducer DTOs.
        status: in_progress
        consumers: [chummer-presentation, chummer-play, chummer.run-services]
        forbidden_source_copies: [chummer-presentation, chummer-play, chummer.run-services]

      - id: Chummer.Play.Contracts
        owner_repo: chummer.run-services
        purpose: Play/mobile/service seam for hosted play APIs and play-safe projections.
        status: in_progress
        consumers: [chummer-play, chummer-presentation]
        forbidden_source_copies: [chummer-play, chummer-presentation]

      - id: Chummer.Run.Contracts
        owner_repo: chummer.run-services
        purpose: Hosted orchestration contracts for identity, approvals, memory, delivery, service policy, and external integration receipts.
        status: in_progress
        consumers: [chummer-presentation, internal service clients]
        forbidden_source_copies: [chummer-presentation, chummer-play, chummer-core-engine]

      - id: Chummer.Ui.Kit
        owner_repo: chummer-ui-kit
        purpose: Shared design tokens, themes, shell primitives, accessibility primitives, and reusable Chummer UI patterns.
        status: bootstrap
        consumers: [chummer-presentation, chummer-play]
        forbidden_source_copies: [chummer-presentation, chummer-play]

      - id: Chummer.Hub.Registry.Contracts
        owner_repo: chummer-hub-registry
        purpose: Immutable registry/publication/install/compatibility contracts.
        status: bootstrap
        consumers: [chummer.run-services, chummer-presentation]
        forbidden_source_copies: [chummer.run-services, chummer-presentation]

      - id: Chummer.Media.Contracts
        owner_repo: chummer-media-factory
        purpose: Media execution contracts for render jobs, manifests, previews, asset lifecycle, and provider receipts.
        status: bootstrap
        consumers: [chummer.run-services, chummer-presentation, chummer-play]
        forbidden_source_copies: [chummer.run-services, chummer-presentation, chummer-play]

    contract_sets:
      - id: runtime_dtos_vnext
        canonical_package: Chummer.Engine.Contracts
        semantic_owner: chummer-core-engine
        status: open
        includes:
          - runtime fingerprints
          - runtime bundles
          - ruleset/pack/profile provenance
          - deterministic runtime payloads

      - id: explain_trace_vnext
        canonical_package: Chummer.Engine.Contracts
        semantic_owner: chummer-core-engine
        status: open
        includes:
          - explain traces
          - modifier provenance
          - evidence pointers
          - localization-safe explain keys

      - id: session_events_vnext
        canonical_package: Chummer.Engine.Contracts
        semantic_owner: chummer-core-engine
        consumer_wrappers:
          - Chummer.Play.Contracts
          - Chummer.Run.Contracts
        status: open
        includes:
          - semantic session mutation events
          - causation and idempotency data
          - actor and device identity
          - scene revision and replay safety
        rule: Consumer packages may wrap transport or projection concerns but may not redefine semantic event meaning.

      - id: play_api_vnext
        canonical_package: Chummer.Play.Contracts
        semantic_owner: chummer.run-services
        status: open
        includes:
          - play bootstrap
          - session profile catalog
          - hosted play projections
          - play-safe Coach/Spider projections

      - id: run_orchestration_vnext
        canonical_package: Chummer.Run.Contracts
        semantic_owner: chummer.run-services
        status: open
        includes:
          - approvals
          - memory
          - delivery
          - notifications
          - external provider route receipts

      - id: ui_system_vnext
        canonical_package: Chummer.Ui.Kit
        semantic_owner: chummer-ui-kit
        status: open
        includes:
          - design tokens
          - shell primitives
          - accessibility primitives
          - Chummer-specific reusable state patterns

      - id: hub_registry_vnext
        canonical_package: Chummer.Hub.Registry.Contracts
        semantic_owner: chummer-hub-registry
        status: open
        includes:
          - artifact metadata
          - publication state
          - install state
          - review and compatibility projections

      - id: media_execution_vnext
        canonical_package: Chummer.Media.Contracts
        semantic_owner: chummer-media-factory
        status: open
        includes:
          - media jobs
          - asset manifests
          - preview and thumbnail refs
          - asset lifecycle
          - provider receipts

    compatibility_rules:
      - Contract packages version independently.
      - Breaking changes require milestone and blocker updates in chummer-design.
      - No repo may source-copy a canonical contract family owned elsewhere.
      - Repo-local mirrors must use canonical package ids, not legacy aliases.
    ```

    ---

    ## FILE: `products/chummer/GROUP_BLOCKERS.md`

    ```md
    # Group blockers

    Last reviewed: 2026-03-10

    ## RED blockers

    ### BLK-001 — design repo not yet fully canonical
    Central design still needs complete, current, substantive canon for active repos, packages, milestones, blockers, mirrors, and external-tools policy.

    Why this matters:
    Workers improvise boundaries when central design is shallow or stale.

    Owners:
    - chummer-design

    Exit:
    - canonical files are substantive
    - media-factory is represented everywhere centrally
    - root-level orphan product docs are removed
    - mirror coverage is complete

    ### BLK-002 — package canon not fully settled
    `Chummer.Engine.Contracts`, `Chummer.Play.Contracts`, `Chummer.Run.Contracts`, `Chummer.Ui.Kit`, `Chummer.Hub.Registry.Contracts`, and `Chummer.Media.Contracts` are not yet all equally canonical and equally consumed package-only.

    Why this matters:
    Repo splits stay conceptual if package truth is ambiguous.

    Owners:
    - chummer-design
    - chummer-core-engine
    - chummer.run-services
    - chummer-ui-kit
    - chummer-hub-registry
    - chummer-media-factory

    ### BLK-003 — semantic session duplication risk
    Semantic session event meaning still risks being defined in more than one place when play/run transport contracts duplicate engine semantics.

    Why this matters:
    Replay truth, reducer truth, relay truth, and client truth can drift.

    Owners:
    - chummer-core-engine
    - chummer.run-services
    - chummer-play

    ## YELLOW blockers

    ### BLK-004 — play repo still needs mirror and real client maturity
    `chummer-play` must fully consume package-only seams, receive mirrored design context, and replace scaffold seams with real ledger/sync/client behavior.

    Owners:
    - chummer-play
    - chummer-design

    ### BLK-005 — media-factory split not yet operational
    The repo exists, but source, mirrors, contract ownership, and live execution cutover are still incomplete.

    Owners:
    - chummer-media-factory
    - chummer.run-services
    - chummer-design

    ### BLK-006 — README drift in older repos
    Core and run-services still narrate older multi-head runtime ownership in ways that can mislead workers.

    Owners:
    - chummer-core-engine
    - chummer.run-services

    ### BLK-007 — external tools plane not yet fully encoded
    Owned third-party tools now matter architecturally, but policy, ownership, provenance, and kill-switch rules are not yet fully enforced centrally.

    Owners:
    - chummer-design
    - chummer.run-services
    - chummer-media-factory
    ```

    ---

    ## FILE: `products/chummer/EXTERNAL_TOOLS_PLANE.md`

    ```md
    # External tools plane

    ## Purpose

    Project Chummer has an explicit external tools plane.

    Third-party tools may:
    - assist
    - project
    - notify
    - summarize
    - visualize
    - render
    - archive

    They may not become canonical sources of truth.

    ## Canonical truth stays Chummer-owned

    The following remain Chummer-owned:
    - rules truth
    - reducer truth
    - runtime truth
    - session truth
    - approval truth
    - registry/publication/install truth
    - artifact manifest truth
    - media lifecycle truth
    - memory/canon truth

    ## Universal rules

    1. Every external tool sits behind a Chummer-owned adapter.
    2. External tools receive prepared payloads, not unrestricted database access.
    3. External-provider-assisted outputs that re-enter Chummer must carry provenance and receipts.
    4. Every integration must have a kill switch.
    5. No client repo may embed vendor credentials or call vendor SDKs directly.
    6. Vendor-hosted copies are not canonical archives.
    7. Activation does not equal trust; runtime approval still requires design-governed rollout.

    ## Repo ownership

    ### `chummer-design`
    Owns:
    - classification policy
    - allowed-usage rules
    - system-of-record rules
    - rollout sequencing
    - provenance and kill-switch requirements

    ### `chummer.run-services`
    Owns:
    - orchestration-side integrations
    - reasoning-provider routes
    - approval/docs/survey/automation bridges
    - research/eval/prompt-tooling integrations

    ### `chummer-media-factory`
    Owns:
    - document/image/video/preview/route/archive adapters
    - media provider receipts
    - media provenance capture
    - archive/retention execution

    ### `chummer-hub-registry`
    May reference reusable published help/template/style/preview artifacts once promoted into registry truth.

    ### `chummer-presentation` and `chummer-play`
    May only render upstream projections that refer to external outputs.

    ## Current integration classes

    ### Runtime-adjacent orchestration
    - 1min.AI
    - AI Magicx
    - Prompting Systems
    - ChatPlayground AI
    - BrowserAct
    - ApproveThis
    - Documentation.AI
    - MetaSurvey
    - Teable
    - ApiX-Drive
    - Paperguide
    - Vizologi

    ### Runtime-adjacent media
    - MarkupGo
    - PeekShot
    - Mootion
    - AvoMap
    - Internxt
    - optional image-assist routes only when wrapped by media-factory adapters

    ### Non-core utilities
    - FastestVPN PRO
    - OneAir
    - Headway
    - Invoiless for future back-office only

    ## Release gate

    No external integration reaches production use until:
    - owning repo is explicit
    - adapter boundary exists
    - Chummer receipt exists
    - provenance requirements exist
    - kill switch exists
    - fallback/degradation behavior exists
    - system-of-record rule is preserved
    - milestone rollout is published
    ```

    ---

    ## FILE: `products/chummer/projects/design.md`

    ```md
    # Design implementation scope

    ## Mission

    `chummer-design` is the lead-designer repo for Project Chummer.
    It exists to prevent cross-repo architectural drift.

    ## Owns

    - canonical product design truth
    - repo graph truth
    - package/contract ownership truth
    - milestone truth
    - blocker truth
    - mirror/sync truth
    - repo implementation scopes
    - generic review context
    - external tools governance

    ## Must not own

    - production code
    - service implementations
    - hidden duplicate product docs outside canonical paths
    - repo-local implementation details that belong in code repos

    ## Immediate work

    1. Replace all stub canonical files with real content.
    2. Onboard `chummer-media-factory` everywhere central canon enumerates active repos.
    3. Move orphan product docs out of repo root and into canonical product paths.
    4. Make mirror coverage complete and enforceable.
    5. Publish real blocker and milestone truth.
    6. Maintain durable roadmap and implementation-scope coverage for every active repo.
    7. Govern external tools as architecture, not repo-local improvisation.

    ## Worker rule

    If the task changes cross-repo truth, package ownership, rollout sequencing, blocker truth, or mirror coverage, it belongs here first.
    ```

    ---

    ## FILE: `products/chummer/projects/core.md`

    ```md
    # Core implementation scope

    ## Mission

    `chummer-core-engine` owns deterministic mechanics, reducer-safe session mutation, runtime bundles, explain traces, and the canonical engine contract plane.

    ## Owns

    - rules math
    - runtime fingerprints
    - runtime bundles
    - deterministic reducers
    - explain provenance
    - engine contract canon
    - ruleset/plugin/script ABI

    ## Must not own

    - UI rendering or shell chrome
    - hosted-service workflows
    - relay or campaign orchestration
    - media rendering
    - registry persistence
    - provider routing
    - play/mobile client implementation

    ## Current purification focus

    - remove `Chummer.Presentation.Contracts` and `Chummer.RunServices.Contracts` source leaks
    - quarantine legacy tooling out of the active engine solution
    - keep `Chummer.Engine.Contracts` as the only canonical engine/shared DTO source
    - fix README drift so the repo no longer narrates play/workbench/service heads as engine ownership

    ## Milestone spine

    - E0 purification
    - E1 runtime DTO canon
    - E2 explain canon
    - E3 session reducer canon
    - E4 ruleset ABI stabilization
    - E5 explain backend completion
    - E6 Build Lab backend
    - E7 legacy migration certification
    - E8 hardening
    - E9 finished engine
    ```

    ---

    ## FILE: `products/chummer/projects/presentation.md`

    ```md
    # Presentation implementation scope

    ## Mission

    `chummer-presentation` owns builder/workbench/browser/desktop UX, admin/moderation/publication UX, and package consumption of the shared UI kit.

    ## Owns

    - builder/workbench UX
    - compare and inspect flows
    - Explain Everywhere workbench UX
    - publication/admin/moderation UX
    - browser/desktop shell composition
    - consumption of shared UI and engine contracts

    ## Must not own

    - dedicated mobile/session play shell
    - rules math
    - offline play ledger persistence
    - media job execution
    - registry persistence internals
    - provider secrets

    ## Current extraction focus

    - align all local docs to the reality that `chummer-play` owns shipped `/session` and `/coach`
    - consume `Chummer.Ui.Kit` as a package-only dependency
    - keep workbench-only seams separate from play-only seams
    - stop carrying stale or ambiguous play-host assumptions

    ## Milestone spine

    - P0 ownership correction
    - P1 package-only UI consumption
    - P2 workbench shell
    - P3 explain UX
    - P4 Build Lab UX
    - P5 publish/admin/moderation UX
    - P6 platform parity
    - P7 accessibility/performance
    - P8 finished workbench
    ```

    ---

    ## FILE: `products/chummer/projects/run-services.md`

    ```md
    # Run-services implementation scope

    ## Mission

    `chummer.run-services` owns hosted orchestration: identity, relay, approvals, memory, Coach/Spider/Director orchestration, play API aggregation, delivery, notifications, and service policy.

    ## Owns

    - identity and campaign/session access control
    - play API aggregation
    - relay and hosted session coordination
    - approvals and reviewable actions
    - Coach / Spider / Director orchestration
    - memory, recap, and delivery workflows
    - service policy and external-tool routing
    - run-service contract canon

    ## Must not own long-term

    - registry persistence internals after `chummer-hub-registry`
    - media render internals after `chummer-media-factory`
    - duplicate engine event semantics
    - canonical rules math

    ## Current split focus

    - publish and stabilize `Chummer.Play.Contracts`
    - keep `Chummer.Run.Contracts` focused on orchestration concerns
    - dedupe any semantic session DTO overlap with engine canon
    - route registry work through `chummer-hub-registry`
    - route render/media execution through `chummer-media-factory`
    - shrink root-level legacy clutter and stale README architecture claims

    ## External integrations scope

    Owns:
    - reasoning-provider routing
    - approval/docs/survey/automation bridges
    - research/eval/prompt-tooling integrations
    - provider route receipts for non-media operations

    Must not own:
    - document/image/video rendering internals
    - media binary lifecycle
    - direct provider use from clients
    - canonical rules math
    - registry truth

    ## Milestone spine

    - R0 shrink-to-boundary reset
    - R1 package canon
    - R2 identity/campaign core
    - R3 play APIs and relay
    - R4 skill runtime
    - R5 Spider/Director/memory
    - R6 orchestration-only registry/media mode
    - R7 notifications/docs/delivery
    - R8 resilience/compliance
    - R9 finished hosted orchestration
    ```

    ---

    ## FILE: `products/chummer/projects/play.md`

    ```md
    # Play implementation scope

    ## Mission

    `chummer-play` owns the player and GM play-mode shell, offline ledger/cache, sync client behavior, installable play/mobile UX, and play-safe live-session surfaces.

    ## Owns

    - player shell
    - GM shell
    - offline ledger/cache
    - sync client and reconnect behavior
    - installable PWA/mobile UX
    - play-safe Coach/Spider surfaces
    - device-appropriate live-session interactions

    ## Must not own

    - builder/workbench UX
    - rules math or runtime fingerprint generation
    - provider secrets
    - publication or moderation workflows
    - registry persistence
    - render execution

    ## Current focus

    - replace scaffolded bootstrap/session clients with real play API seams
    - consume only `Chummer.Engine.Contracts`, `Chummer.Play.Contracts`, and `Chummer.Ui.Kit`
    - receive mirrored `.codex-design/*` guidance like every other active repo
    - turn offline ledger and event log into a real durable client substrate

    ## Milestone spine

    - L0 package canon
    - L1 local ledger and sync
    - L2 player shell
    - L3 GM shell
    - L4 relay/runtime convergence
    - L5 Coach/Spider surfaces
    - L6 mobile/PWA polish
    - L7 observer/cross-device continuity
    - L8 hardening
    - L9 finished play shell
    ```

    ---

    ## FILE: `products/chummer/projects/ui-kit.md`

    ```md
    # UI kit implementation scope

    ## Mission

    `chummer-ui-kit` owns design tokens, shared shell chrome, accessibility primitives, state badges, dense-data primitives, and cross-head visual building blocks.

    ## Owns

    - color/spacing/typography/motion tokens
    - theme compilation
    - reusable primitives
    - shell chrome patterns
    - accessibility primitives
    - dense-data presentation primitives
    - Chummer-specific reusable UI patterns

    ## Must not own

    - domain DTOs
    - HTTP clients
    - local storage logic
    - rules math
    - service orchestration
    - registry or media business logic

    ## Current focus

    - become the package-only shared UI boundary for presentation and play
    - grow from token seed to full component system
    - define reusable patterns like explain chips, stale badges, approval chips, Spider cards, and artifact cards

    ## Milestone spine

    - U0 governance
    - U1 token canon
    - U2 primitives
    - U3 shell chrome
    - U4 dense-data controls
    - U5 Chummer-specific patterns
    - U6 accessibility/localization
    - U7 visual regression/catalog
    - U8 release discipline
    - U9 finished design system
    ```

    ---

    ## FILE: `products/chummer/projects/hub-registry.md`

    ```md
    # Hub registry implementation scope

    ## Mission

    `chummer-hub-registry` owns immutable artifact catalog, publication workflow, moderation state, installs, reviews, compatibility, and runtime-bundle head metadata.

    ## Owns

    - immutable artifact metadata
    - publication draft and publish/archive state
    - moderation state and review trails
    - install state and install history
    - compatibility projections
    - runtime-bundle head metadata
    - registry contract canon

    ## Must not own

    - AI gateway routing
    - Spider/session relay
    - media rendering
    - play/client implementation
    - canonical rules math

    ## Current focus

    - extract registry contracts and catalog lifecycle out of `chummer.run-services`
    - grow from contract seed to real registry domain service
    - become the authoritative home for reusable published artifacts, installs, reviews, and compatibility

    ## Milestone spine

    - H0 contract canon
    - H1 artifact domain
    - H2 publication drafts
    - H3 install/compatibility engine
    - H4 search/discovery/reviews
    - H5 style/template publication
    - H6 federation/org channels
    - H7 hardening
    - H8 finished registry
    ```

    ---

    ## FILE: `products/chummer/projects/media-factory.md`

    ```md
    # Media factory implementation scope

    ## Mission

    `chummer-media-factory` owns render execution, render jobs, previews, manifests, asset lifecycle, provider adapters, and signed asset access for Chummer media workloads.

    ## Owns

    - `Chummer.Media.Contracts`
    - render job intake and state
    - previews and thumbnails
    - manifests and asset receipts
    - asset lifecycle, retention, pinning, supersession
    - provider adapters for document/image/video execution
    - signed asset access and media storage discipline

    ## Must not own

    - campaign or session truth
    - rules math
    - approvals policy
    - publication/moderation workflows
    - play/client UX
    - general AI orchestration
    - service identity or relay

    ## Current focus

    - become a real source tree and package, not just a scaffold repo
    - extract media execution contracts out of `chummer.run-services`
    - land the shared job/asset kernel before domain-specific rendering features
    - onboard full mirror coverage from `chummer-design`

    ## External integrations scope

    Owns:
    - document render adapters
    - preview/thumbnail adapters
    - image/portrait adapters
    - bounded video adapters
    - route-render adapters
    - archive adapters
    - media provider receipts
    - media provenance capture

    Must not own:
    - campaign/session meaning
    - approval policy
    - registry publication
    - client UX
    - general AI orchestration

    ## Milestone spine

    - M0 contract canon
    - M1 asset/job kernel
    - M2 document rendering
    - M3 portrait forge
    - M4 bounded video
    - M5 template/style integration
    - M6 run-services cutover
    - M7 storage/DR/scale
    - M8 finished media plant
    ```

    ---

    ## FILE: `products/chummer/review/GENERIC_REVIEW_CHECKLIST.md`

    ```md
    # Generic review checklist

    Use this review context in every mirrored Chummer code repo.

    ## 1. Boundary check

    - Does this change stay inside the repo’s implementation scope?
    - Does it widen ownership into another repo’s area?
    - Does it reintroduce a boundary that was intentionally split out?

    Reject if:
    - play behavior appears inside presentation
    - workbench behavior appears inside play
    - run-services regrows registry persistence or media execution
    - engine regrows UI or hosted-service authority
    - ui-kit gains domain DTOs or service logic

    ## 2. Contract check

    - Is any cross-repo DTO being added?
    - If yes, is the owning package already defined in `CONTRACT_SETS.yaml`?
    - Is the change consuming a canonical package or copying source?

    Reject if:
    - the change creates a duplicate shared DTO family
    - the change uses an ambiguous or legacy package name when canon is defined
    - the change smuggles engine semantics into play/run wrappers

    ## 3. Mirror check

    - Does `.codex-design/product/*` exist?
    - Does `.codex-design/repo/IMPLEMENTATION_SCOPE.md` exist?
    - Does the mirrored scope match the code being changed?

    Reject if:
    - the repo is missing mirrored design context
    - the change contradicts mirrored scope without a corresponding design-repo update

    ## 4. Milestone check

    - Which milestone is this change serving?
    - Does it unblock or change a published blocker?
    - Does the design repo need an update because sequencing changed?

    Reject if:
    - the change silently changes rollout order or package ownership
    - the change claims milestone progress while central milestones say otherwise

    ## 5. README drift check

    - Does the repo README still describe the current architecture?
    - Is the change depending on README text that central design already contradicts?

    Reject if:
    - stale README text is being used as architecture authority over central design

    ## 6. Verification check

    - Are the relevant contract or boundary tests updated?
    - If the repo owns a package, is its verification harness updated?
    - If the repo consumes a package, is package-only consumption preserved?

    ## 7. Review summary format

    Every substantive review should answer:
    - scope fit: pass/fail
    - boundary fit: pass/fail
    - contract fit: pass/fail
    - mirror fit: pass/fail
    - milestone fit: pass/fail
    - required design-repo follow-up: yes/no

    ## 8. Escalate immediately when

    - ownership is ambiguous
    - package canon is ambiguous
    - mirror coverage is missing
    - a split boundary is being locally re-merged
    - central design files are obviously stale or contradictory
    ```

    ---

    ## FILE: `products/chummer/sync/sync-manifest.yaml`

    ```yaml
    product: chummer
    canonical_source_repo: chummer-design

    common_product_sources: &common_product_sources
      - products/chummer/README.md
      - products/chummer/VISION.md
      - products/chummer/ARCHITECTURE.md
      - products/chummer/ROADMAP.md
      - products/chummer/LEAD_DESIGNER_OPERATING_MODEL.md
      - products/chummer/PROGRAM_MILESTONES.yaml
      - products/chummer/CONTRACT_SETS.yaml
      - products/chummer/GROUP_BLOCKERS.md
      - products/chummer/OWNERSHIP_MATRIX.md
      - products/chummer/EXTERNAL_TOOLS_PLANE.md

    common_review_source: &common_review_source
      products/chummer/review/GENERIC_REVIEW_CHECKLIST.md

    mirrors:
      - repo: chummer-core-engine
        product_target: .codex-design/product
        product_sources: *common_product_sources
        repo_target: .codex-design/repo/IMPLEMENTATION_SCOPE.md
        repo_source: products/chummer/projects/core.md
        review_target: .codex-design/review/REVIEW_CONTEXT.md
        review_source: *common_review_source

      - repo: chummer-presentation
        product_target: .codex-design/product
        product_sources: *common_product_sources
        repo_target: .codex-design/repo/IMPLEMENTATION_SCOPE.md
        repo_source: products/chummer/projects/presentation.md
        review_target: .codex-design/review/REVIEW_CONTEXT.md
        review_source: *common_review_source

      - repo: chummer.run-services
        product_target: .codex-design/product
        product_sources: *common_product_sources
        repo_target: .codex-design/repo/IMPLEMENTATION_SCOPE.md
        repo_source: products/chummer/projects/run-services.md
        review_target: .codex-design/review/REVIEW_CONTEXT.md
        review_source: *common_review_source

      - repo: chummer-play
        product_target: .codex-design/product
        product_sources: *common_product_sources
        repo_target: .codex-design/repo/IMPLEMENTATION_SCOPE.md
        repo_source: products/chummer/projects/play.md
        review_target: .codex-design/review/REVIEW_CONTEXT.md
        review_source: *common_review_source

      - repo: chummer-ui-kit
        product_target: .codex-design/product
        product_sources: *common_product_sources
        repo_target: .codex-design/repo/IMPLEMENTATION_SCOPE.md
        repo_source: products/chummer/projects/ui-kit.md
        review_target: .codex-design/review/REVIEW_CONTEXT.md
        review_source: *common_review_source

      - repo: chummer-hub-registry
        product_target: .codex-design/product
        product_sources: *common_product_sources
        repo_target: .codex-design/repo/IMPLEMENTATION_SCOPE.md
        repo_source: products/chummer/projects/hub-registry.md
        review_target: .codex-design/review/REVIEW_CONTEXT.md
        review_source: *common_review_source

      - repo: chummer-media-factory
        product_target: .codex-design/product
        product_sources: *common_product_sources
        repo_target: .codex-design/repo/IMPLEMENTATION_SCOPE.md
        repo_source: products/chummer/projects/media-factory.md
        review_target: .codex-design/review/REVIEW_CONTEXT.md
        review_source: *common_review_source

    validation_rules:
      - Every active worker-driven code repo must appear in mirrors.
      - Missing .codex-design mirror coverage is a blocker.
      - Repo-specific implementation scopes must exist for every mirrored repo.
      - Review context must be mirrored alongside product canon.
    ```

    ---

    After you paste that into `chummer-design`, do these four cleanup moves immediately:

    1. Move or delete the root-level orphan product docs in `chummer-design` — the top-level `BOUNDARIES_AND_CONTRACTS.md`, `VISION_AND_MILESTONES.md`, `chummer-media-factory.design.v1.md`, and the root-level `chummer-media-factory/` folder should not remain as parallel canon once the product tree above exists.

    2. Mirror `.codex-design` into `chummer-play`. The central design story depends on mirrored local context, but play still shows no `.codex-design` publicly.

    3. Align `chummer-play` package naming with the canon you just published. Its README still says `Chummer.Contracts`, while its build props already point to `Chummer.Engine.Contracts`, `Chummer.Play.Contracts`, and `Chummer.Ui.Kit`.

    4. Use the new contract canon to collapse duplicated session DTOs in `chummer.run-services`. Publicly, both `Chummer.Play.Contracts/RelayContracts.cs` and `Chummer.Run.Contracts/SessionRelayContracts.cs` still define the same `SessionEventEnvelope`, `SessionRelayConvergenceDiagnostics`, `SessionRelayMergeResponse`, `SessionEventProjectionDto`, and `SessionRuntimeBundleDto`, and `MediaContracts.cs` still mixes play-side memory/spider imports with media contracts.

    This is the shortest path to making `chummer-design` catch up to the graph that already exists.
    """
).strip() + "\n"


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main() -> None:
    write_text(DESIGN_FEEDBACK_ROOT / FILENAME, DROPIN_PACK)
    write_text(GROUP_FEEDBACK_ROOT / FILENAME, DROPIN_PACK)
    print(f"wrote {DESIGN_FEEDBACK_ROOT / FILENAME}")
    print(f"wrote {GROUP_FEEDBACK_ROOT / FILENAME}")


if __name__ == "__main__":
    main()
