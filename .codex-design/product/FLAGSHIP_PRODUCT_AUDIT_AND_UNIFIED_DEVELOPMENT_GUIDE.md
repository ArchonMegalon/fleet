# Chummer6 Flagship Product Audit and Unified Development Guide

**Audit scope:** `chummer6-design`, `Chummer6`, `chummer6-core`, `chummer6-ui`, `chummer6-mobile`, `chummer6-hub`, `chummer6-ui-kit`, `chummer6-hub-registry`, `chummer6-media-factory`, `fleet`, `executive-assistant`, plus `chummer5a` as parity oracle.

**Primary target:** make Chummer6 a flagship desktop product whose SR5 client looks and behaves close enough to Chummer5a that veteran users trust it quickly, while establishing a controlled path to the same bar for SR4 and SR6.

---

## 1. Executive Audit

The repo family is structurally healthy. Ownership boundaries are clear, Fleet now reports complete milestone/design coverage, and `chummer6-design` has mature release, parity, dense workbench, route, product-health, and UI-gate canon.

The remaining problem is not repo architecture. It is the gap between **structural green** and **flagship replacement reality**.

The current system risks saying “complete” too early because:
- Fleet milestone coverage is green, but flagship readiness requires stricter lived-product proof.
- `FLAGSHIP_PARITY_REGISTRY.yaml` now has to keep the flagship families below `gold_ready` until the published desktop tuple truth, public migration copy, and packaged release proof all agree.
- `DENSE_WORKBENCH_BUDGET.yaml` and `VETERAN_FIRST_MINUTE_GATE.yaml` are excellent, but they must be enforced in CI and release promotion, not just cited.
- Release-facing desktop truth can still drift if generated public-guide copy falls back to raw artifact presence instead of promoted desktop tuple coverage.
- The Avalonia client is the named flagship head, but it must not feel noisy, spacious, dashboard-like, or web-shell-like. It must feel like a modern dense Chummer desktop tool.

The next program phase should be called:

> **Flagship Product Proof and Chummer5a Veteran Trust**

Do not run it as another architecture cleanup. Run it as a product-quality, parity, UX-density, and release-proof program.

---

## 2. Non-Negotiable Flagship Criteria

A build cannot claim flagship replacement quality unless all of these are true.

### 2.1 Primary desktop head is unambiguous

- `Chummer.Avalonia` is the primary route.
- `Chummer.Blazor.Desktop` is fallback only when explicitly labeled as fallback/compatibility.
- No public shelf or README may imply that Blazor is equally primary unless Blazor independently clears the same flagship bar.

### 2.2 The desktop must look and behave familiar to Chummer5a users

Required visible landmarks:
- real `File` menu
- real `Tools` menu
- `Windows` and `Help`
- immediate toolstrip
- dense workbench center
- left navigation / character section rhythm
- contextual right inspector
- compact bottom status strip
- master index route
- roster route
- settings route
- import/open route

The first minute must answer:
- Where do I open/save/import?
- Where do I choose rules/sources?
- Where is the roster?
- Where is the master index?
- Where is my current runner state?
- How do I get help or support?

### 2.3 No dashboard-first or browser-ritual startup

The desktop must open to:
- a real workbench,
- a restore continuation,
- or an immediately actionable import/new-runner flow.

It must not open to:
- a marketing dashboard,
- a public website surrogate,
- a browser claim ritual,
- or a decorative “welcome” screen that delays real work.

### 2.4 Dense workbench is the default, not an optional theme

Avalonia must use a compact flagship preset by default:
- low padding
- no hero banners inside workbench
- no excessive nested cards
- compact form fields
- compact buttons
- high visible row count
- stable status strip
- obvious command chrome

### 2.5 SR5 first, then SR4 and SR6 with authored edition behavior

The SR5 client must reach Chummer5a parity first because Chummer5a is the strongest oracle for SR5 workflows.

SR4 and SR6 must not inherit trust from SR5:
- SR4 needs its own workflow oracle and SR4-specific rules vocabulary.
- SR6 needs explicit Genesis/CommLink6-style successor evidence, supplement/designer/house-rule posture, and receipts for not-applicable legacy families.

---

## 3. Cross-Repo Product Workstreams

### Workstream A — Product Backbone Workspace

**Owner:** `chummer6-design` + `fleet`
**Supporting:** all repos

Create or harden the `chummer-product` integration workspace described in design canon.

This workspace is not necessarily a monorepo rewrite. It is the place where the product is tested as a product before repo-local boundaries fan back out.

Required modules:
- `engine`
- `dossier-campaign`
- `rules-environment`
- `workspace-sync`
- `registry-update`
- `support-trust`
- `desktop-flagship`
- `desktop-fallback`
- `mobile`
- `media-ai-adjuncts`

Acceptance:
- a whole-product verify command runs from this workspace;
- parity-lab results are collected here;
- release proof references workspace evidence, not only repo-local tests;
- Fleet and EA consume this workspace truth instead of creating parallel product truth.

### Workstream B — Chummer5a Parity Lab

**Owner:** `chummer5a` oracle steward + `executive-assistant`
**Supporting:** `chummer6-ui`, `chummer6-core`, `chummer6-design`

Build a release-blocking parity lab.

Create:
- screenshot baselines from Chummer5a;
- task scripts for veteran workflows;
- import/export fixture packs;
- sample runners with deep cyberware, gear, magic, vehicle, contact, lifestyle, notes, and sourcebook state;
- performance budgets;
- workflow equivalence receipts.

Minimum SR5 task families:
1. create new character;
2. open/import existing Chummer5a character;
3. save and reload;
4. sourcebook selection;
5. settings and character options;
6. master index and reference/source posture;
7. add/edit/remove cyberware including modular cyberlimb payloads;
8. weapons/accessories;
9. armor/mods;
10. vehicles/mods;
11. magic/resonance;
12. contacts/lifestyles/SIN/licenses/notes/history;
13. validation;
14. dice/initiative utilities;
15. roster/multi-character;
16. sheet viewer / print / export;
17. JSON/Foundry or bounded exchange posture;
18. custom data / XML / translator successor posture.

Acceptance:
- every family has screenshots;
- every family has an executable workflow receipt;
- every family has `task_proven` before preview promotion;
- every family has `veteran_approved` before flagship/gold claims.

### Workstream C — Dense Classic Workbench

**Owner:** `chummer6-ui` + `chummer6-ui-kit`
**Supporting:** `chummer6-design`, `fleet`

Avalonia must get a default **Classic Dense Workbench** posture.

UI requirements:
- top menu remains visible;
- toolstrip immediately below menu;
- status strip always visible;
- no dashboard tiles in toolstrip;
- no hero/banner chrome inside workbench;
- max two card nesting levels;
- loaded runner tab posture remains visible;
- at least 12 visible rows at 1440x900 for builder routes;
- at least 9 visible rows at 1366x768;
- header-to-content ratio below 0.30.

Acceptance:
- screenshot fixtures for initial shell, open menu, settings open, loaded runner, dense section light theme, dense section dark theme;
- automated visual audit for spacing and visible rows;
- veteran first-minute tasks pass within time budgets;
- `DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.generated.json` is produced and release-blocking.

### Workstream D — Desktop-Native Install, Claim, Update, Recovery

**Owner:** `chummer6-ui`, `chummer6-hub`, `chummer6-hub-registry`, `fleet`
**Supporting:** `Chummer6`

Fix public/platform truth and desktop experience.

Requirements:
- Windows installer-first posture must become real if Windows is still the primary promoted lane.
- Linux can remain preview-strong, but public copy must not conflict with design.
- macOS stays hidden from public shelf until signed/notarized truth is real.
- Desktop app must show channel, version, update, claim/recovery, and support status in-app.
- No browser ritual should be required before desktop feels usable.

Acceptance:
- public shelf and registry channel truth agree;
- public README/download page agree with registry truth;
- in-app route answers “why am I on this channel?”;
- desktop claim/recovery can complete without manual ritual where possible;
- support/crash handoff from desktop produces a receipt.

### Workstream E — Ruleset Authorship Program

**Owner:** `chummer6-core` + `chummer6-ui`
**Supporting:** `chummer6-design`, `chummer5a`, EA, Fleet

SR5 is the first gold bar. SR4 and SR6 follow as separate authored programs.

Do not flatten editions. Each ruleset must have:
- authored labels;
- authored prompt language;
- authored validation/explain semantics;
- authored import/export posture;
- ruleset-specific fixtures;
- visible active ruleset/preset/amend state.

Acceptance:
- SR5: Chummer5a parity lab clears `veteran_approved`.
- SR4: Chummer4-equivalent workflow/oracle evidence exists or the design explicitly states bounded evidence alternatives.
- SR6: Genesis/CommLink6-style successor evidence exists, including supplement/designer/house-rule posture.

---

## 4. Repo Instructions

## 4.1 chummer6-design

### Audit

The repo is authoritative and now contains the right flagship machinery: product backbone workspace, dense workbench budget, veteran first-minute gate, primary route registry, flagship parity registry, product health scorecard, release gates, and ruleset parity guidance.

The risk is that design can become a large truth warehouse whose documents claim green faster than UI/release evidence proves lived quality.

### Instructions

1. Add a `FLAGSHIP_GAP_QUEUE.yaml` generated from:
   - `DENSE_WORKBENCH_BUDGET.yaml`
   - `VETERAN_FIRST_MINUTE_GATE.yaml`
   - `PRIMARY_ROUTE_REGISTRY.yaml`
   - `FLAGSHIP_UI_RELEASE_GATE.md`
   - `FLAGSHIP_PARITY_REGISTRY.yaml`
   - public shelf truth.

2. Add a `FLAGSHIP_READINESS_SNAPSHOT.generated.json` schema requiring:
   - `structural_ready`
   - `desktop_flagship_ready`
   - `sr5_veteran_ready`
   - `sr4_parity_ready`
   - `sr6_parity_ready`
   - `public_shelf_ready`
   - `dense_workbench_ready`
   - `install_update_recovery_ready`.

3. Update `WHAT_IS_STILL_BELOW_GOLD.md` to fail closed:
   - If public shelf is unpublished, show it as a gold-readiness warning.
   - If Windows public artifact is absent while Windows is the primary lane, show it.
   - If any generated evidence artifact is stale or missing, show it.

4. Make `FLAGSHIP_PARITY_REGISTRY.yaml` include evidence freshness timestamps per family, not only path references.

5. Split parity proof into:
   - SR5/Chummer5a
   - SR4
   - SR6
   rather than letting global rows hide ruleset-specific weakness.

6. Add a hard rule: **gold_ready expires** if supporting generated proof is older than the current repo release wave or if referenced files are missing from the product workspace.

## 4.2 Chummer6

### Audit

The guide is now concise and useful, but it must become the veteran migration front door, not only a public-preview explanation. It currently says Linux preview artifacts are visible while the promoted release channel is unpublished.

### Instructions

1. Keep root README short, but add a hard “Desktop replacement truth” box:
   - primary desktop head,
   - platform artifact availability,
   - SR5 parity status,
   - what is not gold yet,
   - link to Chummer5a migration guide.

2. Expand `FROM_CHUMMER5A_TO_CHUMMER6.md` with:
   - side-by-side screenshots;
   - exact workflow coverage table;
   - what is familiar;
   - what changed;
   - what is missing or bounded;
   - how to report parity pain.

3. Update `DOWNLOAD.md` from registry truth only:
   - no hand-maintained artifact posture;
   - platform table must say recommended / fallback / unavailable;
   - if Windows is primary but unavailable, say why and what blocks it.

4. Add `PARITY_DASHBOARD.md` generated from `FLAGSHIP_PARITY_REGISTRY.yaml`.

5. Add a “Veteran quick start” section:
   - open/import;
   - sourcebooks;
   - settings;
   - roster;
   - master index;
   - print/export;
   - report bug.

## 4.3 chummer6-core

### Audit

Ownership is clean. Remaining risk is ruleset trust and oracle coverage. It must become the mechanical parity engine, especially for SR5 first.

### Instructions

1. Create `tests/Chummer.Parity.SR5.Tests` with fixtures imported or modeled from Chummer5a.

2. Add fixture categories:
   - cyberware modular limb;
   - bioware stacking;
   - sourcebook toggles;
   - contacts/lifestyles/licenses;
   - magic/resonance;
   - vehicles;
   - weapons/accessories;
   - armor;
   - karma advancement;
   - validation edge cases.

3. Emit `ORACLE_RULESET_PARITY.generated.json` with:
   - ruleset,
   - fixture id,
   - expected legacy facts,
   - Chummer6 facts,
   - divergence classification,
   - downgrade/block receipt.

4. Add performance budgets:
   - load runner;
   - evaluate validation;
   - explain modifier trail;
   - import Chummer5a;
   - export sheet data.

5. Make active ruleset/preset/amend-package state mandatory in every explain receipt.

6. For SR4 and SR6:
   - create separate fixture namespaces;
   - never reuse SR5 expected text where edition-specific behavior diverges;
   - explicitly emit `not_applicable` receipts for legacy families not carried forward.

## 4.4 chummer6-ui

### Audit

This is the flagship product repo. It must stop being judged only by “feature exists.” It must be judged by whether Avalonia feels like a modern Chummer5a.

### Instructions

1. Create `Chummer.Avalonia.ClassicDense` or an equivalent preset binding to UI Kit’s classic dense workbench.

2. Make Classic Dense the default for flagship preview:
   - no dashboard-first startup;
   - no hero banner in workbench;
   - menu/toolstrip/status-strip visible;
   - compact field/list/dialog spacing.

3. Add automated UI release tests:
   - open File menu;
   - open Tools menu;
   - open Settings;
   - import runner;
   - open Master Index;
   - open Roster;
   - open Sourcebooks;
   - open Cyberware flow;
   - open Print/Export;
   - save/reload.

4. Add screenshot capture:
   - `initial_shell_light.png`
   - `initial_shell_dark.png`
   - `menu_open.png`
   - `settings_open.png`
   - `loaded_runner.png`
   - `cyberware_add_modular_limb.png`
   - `roster.png`
   - `master_index.png`

5. Generate:
   - `DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.generated.json`
   - `DESKTOP_WORKFLOW_EXECUTION_GATE.generated.json`
   - `CHUMMER5A_DESKTOP_WORKFLOW_PARITY.generated.json`.

6. Reduce Avalonia noise:
   - remove decorative cards around dense forms;
   - cap banner height at zero inside workbench;
   - keep headers compact;
   - make status strip permanent;
   - reduce persistent badge clusters;
   - preserve visible rows.

7. Add a “Chummer5a veteran mode” QA profile and run it in CI.

## 4.5 chummer6-ui-kit

### Audit

UI Kit has the right boundary and now exposes classic dense workbench concepts, but it must become the place where noise is eliminated systematically.

### Instructions

1. Expand `classic_dense_workbench` tokens:
   - row spacing;
   - menu height;
   - toolbar height;
   - tab height;
   - status-strip height;
   - field height;
   - inspector width;
   - list row height;
   - compact icon button sizing.

2. Add components:
   - `ClassicMenuBar`
   - `ClassicToolStrip`
   - `ClassicStatusStrip`
   - `DenseTabStrip`
   - `DenseInspectorPane`
   - `DenseListDetailPane`
   - `RulesetContextStrip`
   - `SourceToggleBadge`
   - `ValidationStateChip`.

3. Add an Avalonia adapter test that verifies the `FlagshipDesktopDefault` class marker and dense tokens are emitted.

4. Add visual-regression fixtures for compact panes, not just adapter payload shape.

5. Add an accessibility proof that compact mode remains WCAG-safe:
   - focus visible;
   - keyboard reachable;
   - error states readable;
   - contrast proof.

## 4.6 chummer6-mobile

### Audit

Mobile is healthy. Its main risk is becoming a place to hide desktop parity gaps or pulling shared UX out of UI Kit.

### Instructions

1. Freeze desktop-adjacent feature creep until SR5 desktop parity is veteran-approved.

2. Keep mobile scoped to:
   - play shell;
   - rejoin/resume;
   - offline cache;
   - session ledger;
   - GM/player flow.

3. Reuse UI Kit primitives only. Do not create private mobile equivalents for shared status/chip/prompt patterns.

4. Add ruleset-context visibility in mobile play:
   - active ruleset;
   - source pack;
   - amend package;
   - stale/offline state.

5. Add network degradation and resume receipts to release evidence.

## 4.7 chummer6-hub

### Audit

Hub owns public/account/support surfaces and can accidentally become a browser detour. Its role should be to support the desktop product and keep release/account/support truth honest.

### Instructions

1. Make account linking desktop-native:
   - desktop starts claim;
   - browser only supports auth if unavoidable;
   - completion returns to desktop workbench.

2. Expose support/case status to desktop:
   - case id;
   - received;
   - triaged;
   - fix planned;
   - fix available;
   - closed with version/channel.

3. Keep `chummer.run` public surfaces as supporting shell, not product replacement.

4. Add integration tests:
   - desktop claim handoff;
   - support report from desktop;
   - release channel query;
   - account recovery;
   - in-app fix notification.

5. If public web workbench remains exposed, label it clearly as preview/fallback if it is not the primary product route.

## 4.8 chummer6-hub-registry

### Audit

Registry is the right place for release-channel truth. It must prevent shelf/copy drift and make primary/fallback route truth machine-readable.

### Instructions

1. Add channel fields:
   - `primary_head`
   - `fallback_heads`
   - `recommended_artifact`
   - `platform_posture`
   - `installer_first`
   - `portable_fallback`
   - `promotion_state`
   - `support_state`
   - `rollback_available`.

2. Add route explanation API:
   - “why this artifact is recommended”
   - “why this head is fallback”
   - “why this platform is unavailable.”

3. Generate `RELEASE_CHANNEL_TRUTH.generated.json` consumed by:
   - Chummer6 guide;
   - Hub downloads page;
   - Avalonia updater;
   - Fleet release dashboard.

4. Fail publication if public guide, hub download page, and registry disagree.

## 4.9 chummer6-media-factory

### Audit

Media is now a runtime owner. It should not dominate flagship product work. Keep it bounded.

### Instructions

1. Keep guide art and AR compositing separate from desktop parity.

2. Maintain two-stage render pipeline:
   - base art;
   - verified overlay;
   - receipt.

3. Add a “not release-blocking unless public-surface critical” policy.

4. For generated Chummer public art, enforce:
   - Shadowrun world markers;
   - integrated AR;
   - no stickers;
   - no broad-stroke low-detail look.

5. Do not let art reruns consume capacity needed for Avalonia SR5 parity.

## 4.10 fleet

### Audit

Fleet is now aligned structurally, but it risks green dashboards too early.

### Instructions

1. Add separate readiness planes:
   - `structural_ready`
   - `flagship_ready`
   - `sr5_veteran_ready`
   - `sr4_parity_ready`
   - `sr6_parity_ready`
   - `public_shelf_ready`
   - `dense_workbench_ready`.

2. Fleet must fail “flagship ready” if:
   - public shelf unpublished;
   - Windows primary lane absent while still canon primary;
   - dense workbench proof stale;
   - first-minute gate stale;
   - parity evidence stale;
   - UI screenshots missing.

3. Add a product-governor page showing:
   - green structural milestones;
   - red/yellow flagship risks;
   - platform artifact posture;
   - ruleset parity posture.

4. Do not let `remaining_milestones: []` imply product readiness.

5. Add `chummer-product` workspace verification to Fleet’s compile health.

## 4.11 executive-assistant

### Audit

EA is powerful and useful, but it should now focus on parity evidence and audits, not only public guide/media generation.

### Instructions

1. Add `chummer5a_parity_extractor` skill:
   - screenshot extraction;
   - workflow map extraction;
   - fixture inventory;
   - compare-pack generation.

2. Add `avalonia_noise_auditor` skill:
   - visible row count;
   - padding budget;
   - header-to-content ratio;
   - menu/toolstrip/status-strip detection;
   - badge/banner count;
   - screenshot readability.

3. Add `ruleset_parity_auditor` skill:
   - SR5 Chummer5a fixture comparison;
   - SR4 oracle posture;
   - SR6 Genesis/CommLink6 successor posture.

4. Generated readiness copy must consume flagship/parity readiness, not only milestone completion.

5. Keep Prompting Systems as helper/evaluation, not product authority.

## 4.12 chummer5a

### Audit

`chummer5a` should become an active oracle source, not just a fork.

### Instructions

1. Freeze product development here.

2. Extract:
   - screenshots;
   - menu maps;
   - dialog maps;
   - sample characters;
   - import/export fixtures;
   - workflow lists;
   - form inventories.

3. Store in a parity artifact pack:
   - `oracle/screenshots`
   - `oracle/tasks`
   - `oracle/fixtures`
   - `oracle/forms.json`
   - `oracle/workflow_map.json`.

4. Feed these into `chummer6-ui`, `chummer6-core`, Fleet, and EA.

---

## 5. SR5, SR4, SR6 Milestone Plan

## Milestone 0 — Truth Baseline

**Goal:** stop green structural status from hiding product gaps.

Deliver:
- `FLAGSHIP_GAP_QUEUE.yaml`
- `FLAGSHIP_READINESS_SNAPSHOT.generated.json`
- public shelf vs design mismatch report
- current Avalonia screenshot pack
- Chummer5a oracle extraction plan

Exit:
- everyone can see exactly what blocks flagship truth.

## Milestone 1 — SR5 Parity Lab MVP

**Goal:** prove representative SR5 Chummer5a workflows.

Deliver:
- Chummer5a screenshots;
- SR5 task scripts;
- SR5 import fixtures;
- SR5 cyberware modular limb test case;
- SR5 sourcebook/settings/master-index cases.

Exit:
- first SR5 workflow families reach `task_proven`.

## Milestone 2 — Avalonia Dense Workbench Pass

**Goal:** make Avalonia visibly Chummer-like.

Deliver:
- Classic Dense Workbench default;
- top menu/toolstrip/status strip;
- no dashboard-first startup;
- screenshot audit;
- veteran first-minute pass.

Exit:
- Avalonia feels like the primary desktop product, not a noisy modern shell.

## Milestone 3 — SR5 Veteran-Approved

**Goal:** SR5 flagship replacement proof.

Deliver:
- all SR5 core workflow families task-proven;
- veteran first-minute gate pass;
- dense budget pass;
- import/export proof;
- release artifact proof.

Exit:
- SR5 can claim veteran-approved preview if public shelf truth supports it.

## Milestone 4 — Desktop-Native Install and Support

**Goal:** no browser ritual or shelf ambiguity.

Deliver:
- installer-first platform truth;
- in-app update/recovery;
- support/crash receipts;
- registry/hub/guide consistency.

Exit:
- install/update/support feel like one product.

## Milestone 5 — SR4 Authored Parity

**Goal:** SR4 reaches the same style of proof without inheriting SR5 assumptions.

Deliver:
- SR4 workflow oracle plan;
- SR4 fixtures;
- SR4 labels/prompts/explain semantics;
- SR4 import/export receipts.

Exit:
- SR4 task-proven across core families.

## Milestone 6 — SR6 Authored Successor Parity

**Goal:** SR6 gets serious successor proof.

Deliver:
- SR6 supplement/designer/house-rule matrix;
- Genesis/CommLink6 successor comparison;
- not-applicable receipts for legacy families;
- SR6 authored UI cues.

Exit:
- SR6 task-proven across in-scope successor families.

## Milestone 7 — Gold Candidate

**Goal:** flagship truth is honest across SR5/SR4/SR6.

Deliver:
- all in-scope parity families gold-ready or explicitly bounded;
- platform shelf published and honest;
- generated public docs match release truth;
- Fleet readiness planes green;
- evidence fresh.

Exit:
- the product can claim flagship readiness without bluffing.

---

## 6. Immediate Next PRs

1. `chummer6-design`: add `FLAGSHIP_GAP_QUEUE.yaml` and evidence freshness policy.
2. `chummer6-ui-kit`: expand Classic Dense Workbench token/component pack.
3. `chummer6-ui`: wire Avalonia to Classic Dense by default and add screenshot gate.
4. `chummer5a` + `EA`: extract oracle screenshot/task pack.
5. `chummer6-core`: add first SR5 oracle fixture suite.
6. `fleet`: add separate flagship readiness planes.
7. `hub-registry`: publish machine-readable primary/fallback artifact truth.
8. `Chummer6`: add parity dashboard and migration trust page.
9. `hub`: wire desktop-native claim/support route.
10. `media-factory`: keep image work bounded; do not block flagship parity.

---

## 7. Final Standard

The target is not “multi-repo architecture green.”

The target is:

> A Chummer5a veteran installs Chummer6, opens Avalonia, sees a familiar dense workbench, imports or creates an SR5 runner, finds sourcebooks/settings/roster/master index/export without hunting, trusts the math receipts, and never feels pushed through browser ritual or decorative chrome before doing real work.

Until that is true, the product is structurally healthy but not flagship.
