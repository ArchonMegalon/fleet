# Desktop Executable Exit Gates

Purpose: replace shell-only parity claims with release-blocking proof that the shipped desktop clients behave like real desktop products under actual user interaction.

This document exists because catalog parity and screenshot parity are not enough. A desktop head can claim workflow coverage while still failing at the last mile:

- menus render but do not open meaningful command surfaces
- a bundled demo runner is promised but missing from the shipped artifact
- help, feedback, or support links resolve to internal hosts instead of public routes
- a desktop head installs but does not expose a launchable app bundle
- a workflow family is marked "covered" even though no executable UI path can complete it

Current user-reported failures are exactly the class this gate must catch:

- inert top-menu interactions in Avalonia
- missing or undiscoverable demo-runner load path
- Blazor Desktop installing without a useful app-launch posture
- feedback/support opening internal `chummer-api` links instead of public web routes

## Hard release rule

Desktop release truth is `not ready` until all of these receipts exist and pass:

- `DESKTOP_EXECUTABLE_EXIT_GATE.generated.json`
- `DESKTOP_WORKFLOW_EXECUTION_GATE.generated.json`
- `DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.generated.json`

`CHUMMER5A_DESKTOP_WORKFLOW_PARITY.generated.json`, `SR4_DESKTOP_WORKFLOW_PARITY.generated.json`, and `SR6_DESKTOP_WORKFLOW_PARITY.generated.json` remain necessary, but they are no longer sufficient on their own.

## Gate A: Desktop executable exit gate

Contract intent: the shipped desktop heads expose a discoverable, working shell where a user can click the obvious things and get visible progress instead of dead chrome.

Required proof areas:

1. Shell action wiring
   - Every visible user-click surface in the release manifest is bound to a real command, dialog, navigation change, or external handoff.
   - No primary shell button, menu root, toolstrip action, or empty-state CTA may be inert.
2. Menu liveliness
   - Clicking each top menu root opens a visible command surface.
   - At least one command from each root must execute and produce a visible state change.
3. Settings/help/support liveliness
   - Settings opens in-shell and remains interactive.
   - Help/support/feedback open public-web routes only.
   - No install, support, or feedback action may resolve to internal Docker hostnames.
4. Demo-runner availability
   - The packaged artifact contains the release-bundled demo runner.
   - The client can load it from a user-facing path without hidden test hooks.
5. Installed-app posture
   - The packaged head produces a launchable app bundle or desktop entry, not just a folder.
   - macOS app bundle names and executable metadata must be Spotlight/Launcher-friendly.
   - Windows/Linux launch metadata must point to the actual app, not an install directory.
6. First-run install/link posture
   - Claim/install handoff is applied automatically on first launch where promised.
   - First-run support text must describe the real path the user takes, not an obsolete script/clipboard ritual.

## Gate B: Desktop workflow execution gate

Contract intent: workflow families are only "present" when a real user path can execute them inside the shipped desktop head.

Required proof areas:

1. Workflow-family execution receipts
   - Each Chummer5a/SR4/SR6 workflow family named in the parity ledgers must have an executable UI receipt.
   - Each receipt must identify:
     - fixture
     - starting shell state
     - user interactions performed
     - visible checkpoints observed
     - save/reload or recovery checkpoint
2. Cross-head execution
   - Avalonia and Blazor Desktop must each prove the workflow families they promise.
   - If one head is intentionally narrower, the release gate must state that explicitly instead of silently inheriting Avalonia proof.
3. High-friction audit cases
   - Cyberware/bioware with nested or modular state
   - weapons/accessories
   - armor/mods
   - vehicles/mods
   - magic/resonance
   - contacts/lifestyles/notes
   - rules/profile/settings
4. Closeout proof
   - A workflow family is not closed because the underlying data model exists.
   - Closure requires click-through proof from shell discovery to visible result.

## Test framework design

### 1. Click-surface manifest

Add a machine-readable manifest per head describing all user-clickable surfaces that must be alive:

- menu roots
- toolstrip actions
- workspace-strip actions
- status-strip actions
- first-run CTAs
- help/support/feedback actions
- ruleset-specific shell actions

Each manifest row should define:

- `surfaceId`
- `head`
- `rulesetScope`
- `selector` or control id
- `interaction`
- `expectedObservation`
- `severity`

### 2. Head-specific drivers

Avalonia:

- use the existing headless Avalonia harness to click real controls
- assert visible command regions, dialogs, workspace changes, and route handoffs

Blazor Desktop:

- use a deterministic DOM/component harness for Photino-hosted surfaces
- assert that the installed app boots into a usable shell and exposes real open/import/demo/help actions

### 3. Installed-artifact probes

Run packaged-artifact checks after build:

- verify demo-runner fixture presence
- verify app bundle/executable naming
- verify launcher metadata
- verify install script/claim arguments when platform policy depends on them

### 4. Public-route probes

Release gates must assert that install/support/feedback actions resolve to public routes:

- `https://chummer.run/...`
- never `http://chummer-api:8080/...`

### 5. Workflow receipt runner

The workflow runner should execute journeys from a release fixture manifest and emit one receipt per workflow family. Those receipts feed the parity ledgers instead of the other way around.

## Gate C: Desktop visual familiarity exit gate

Contract intent: a promoted desktop head must not only work, it must still feel close enough to Chummer5a that a legacy user can orient inside the shell and dense builder dialogs without relearning the product.

Required proof areas:

1. Shell familiarity
   - top menu, immediate toolstrip, dense three-pane center, compact bottom strip
   - loaded-character tab posture is visible when a runner is open
2. Theme readability
   - light/dark palette anchors remain Chummer-adjacent and readable
   - no dark-on-dark, white-on-white, or low-contrast chrome regressions
3. Workflow-local familiarity
   - cyberware/cyberlimb add/edit posture preserves a familiar browse-detail-confirm rhythm
   - dense builder dialogs remain visually orienting, not generic blank forms
4. Screenshot evidence
   - initial shell, menu open, settings open, loaded runner, dense light, dense dark
   - loaded-runner tab posture
   - cyberware/cyberlimb dialog posture

## Failure policy

The desktop gate fails if any of the following are true:

- a menu or primary click surface is visible but inert
- a promised demo runner is missing or undiscoverable
- feedback/support/install routes point at internal hosts
- the installed desktop head cannot be launched as an app
- a workflow family has catalog proof but no executable UI receipt
- Blazor Desktop is promoted without a real launchable user-facing surface
- the shell no longer feels recognizably close to Chummer5a in theme, layout, loaded-runner tabs, or dense builder-dialog posture

## Fleet handoff

Fleet must reopen desktop readiness when any desktop exit-gate receipt is missing, stale, or failing.

Backlog shape:

- one slice for shell/install/support executable exits
- one slice for workflow-family execution receipts and cross-head closeout

Fleet should not return to `complete` on desktop readiness until both slices are closed and the new receipts are published.
