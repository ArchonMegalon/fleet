# Flagship UI Release Gate

Purpose: define the desktop-first UI audit that blocks release promotion when the shell looks unfinished, hides state, breaks primary interaction paths, or violates the shared design contract.

This gate exists because a visually improved shell is not enough. Promotion requires proof that the promoted head behaves like a paid flagship desktop product under real user interaction, dark/light themes, dense-data conditions, and keyboard-driven use.

This gate is also intentionally broader than "shell parity." A polished menu bar is not release truth. The promoted desktop head must provide a trustworthy equivalent for every Chummer5a workflow family that users relied on to build, inspect, validate, save, reload, import, and maintain a runner. High-friction examples such as custom modular cyberlimbs are canonical audit cases, not the full scope of the promise.

## Head authority rules

* `Chummer.Avalonia` is the default flagship desktop head for the promoted desktop wave.
* Exactly one desktop head may be the primary public CTA for a lane.
* `Chummer.Blazor.Desktop` is fallback only when the lane also ships Avalonia as the promoted primary head and the shelf, release copy, and evidence all label Blazor as compatibility or bounded fallback.
* Any gold or flagship-ready desktop claim requires every shipped desktop head, including `Chummer.Blazor.Desktop`, to independently meet the flagship bar even if only one head is the default public CTA.
* Preview may still ship Blazor Desktop as bounded fallback, but that preview exception does not count as gold.
* Neither head may inherit the other head's menu, install, workflow, or visual-familiarity proof unless the gate explicitly scopes that proof as shared.

## Source standards

- W3C WCAG 2.2 is the baseline for keyboard access, focus treatment, hover/focus behavior, and error prevention:
  - keyboard access
  - no keyboard trap
  - visible focus
  - content on hover or focus
  - error prevention
- Fluent 2 is the baseline for dense desktop navigation and command posture:
  - brief, scannable labels
  - secondary actions remain accessible and not hover-only
  - navigation does not hide hierarchy or bury primary work
- Apple macOS HIG is the platform-fit bar for macOS desktop posture:
  - menus, toolbars, and sidebars must feel authored for desktop instead of web chrome dropped into a window
- The shared product contract in `SURFACE_DESIGN_SYSTEM_AND_AI_REVIEW_LOOP.md` remains the whole-product authorship bar.

## Release-blocking expectations

The promoted desktop head must prove all of the following before release truth can move to `ready`:

1. Primary actions are obvious.
   - A user can find import/open, ruleset context, settings, save, help/support, and the active workspace without hunting.
2. Menu and command surfaces react immediately.
   - Menu clicks expose visible command choices in the current shell.
   - Settings and other core commands produce immediate visible state change inside the main shell.
3. The shell stays responsive under command and dialog flows.
   - Opening settings, help, import, or a menu must not freeze the window, strand focus, or leave the user without a visible next action.
4. Keyboard use is first-class.
   - Core shortcuts work.
   - Focus can always move in and back out of menus and dialogs.
   - Focus indicators remain visible in light and dark theme variants.
5. Dark and light theme states are trustworthy.
   - Text, chrome, danger, warning, stale, preview, and focus surfaces remain readable and intentional under both theme variants.
   - Flagship desktop theme pairs meet WCAG AA contrast for normal text and control labels, and screenshot review does not substitute for missing measurable contrast proof.
6. Release fixtures and proof assets are physically present.
   - The promoted desktop output contains the bundled demo runner and any release-critical fixtures that the shell claims are available.
7. Dense-data comfort survives.
   - A loaded runner, menus, dialogs, summary cards, and inspector panes remain scannable without visual collapse or accidental overflow.
8. Chummer familiarity survives modernization.
   - The promoted desktop shell still reads like Chummer to a Chummer5a user.
   - A real top menu, immediate toolstrip, dense workbench center, and compact bottom status strip remain visible and usable.
9. Workflow-family equivalence is real, not implied.
   - Every Chummer5a workflow family that the product still promises must have a desktop equivalent in the promoted head.
   - Equivalent means the user can discover, execute, save, reload, and re-find the workflow without falling back to the legacy client.
   - "Covered in the parity checklist" is necessary but not sufficient. Catalog coverage without executable workflow proof does not pass.
10. High-friction builder workflows are explicitly proven.
   - At least one deep audit case from each major builder family must be executable under release proof.
   - Cyberware and bioware proof must include add/edit/remove posture, legacy import fidelity, and a modular or subsystem-bearing case such as a modular connector plus modular limb payload.
   - Equivalent audit cases must exist for weapons/accessories, armor/mods, vehicles/mods, magic, resonance, contacts/lifestyles/notes, and rules/profile/settings flows.
11. Executable desktop exits are proven, not inferred.
   - The release must publish `DESKTOP_EXECUTABLE_EXIT_GATE.generated.json` and `DESKTOP_WORKFLOW_EXECUTION_GATE.generated.json` as defined in `DESKTOP_EXECUTABLE_EXIT_GATES.md`.
   - Missing or stale executable-exit receipts block release truth even if shell parity or ledger parity is green.
12. Visual familiarity is proven, not assumed.
   - The release must publish `DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.generated.json` as defined in `DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.md`.
   - Loaded-runner tab posture and dense builder-dialog familiarity, especially cyberware/cyberlimb add flows, are release-blocking proof areas.
   - SR4 and SR6 may adapt control content to their rulesets, but the orientation model must remain familiar to a Chummer5a user.

13. A dedicated user-journey tester shard proves the promoted binary.
   - The release must publish `USER_JOURNEY_TESTER_AUDIT.generated.json`.
   - The audit must be produced by a tester shard that does not fix code during the same run.
   - The tester must run the promoted Linux desktop binary as a user, not internal APIs or component-level shortcuts.
   - The audit must include multiple screenshots per required workflow.
   - Master Index search focus stability and `File > New Character` visible-workspace proof are hard-bar workflows because invisible state changes and focus-remount bugs can pass shell receipts.

14. Head posture is unambiguous.
   - Avalonia must clear the full gate as the flagship head.
   - Blazor Desktop must also clear the full gate for any gold or flagship-ready claim, even when it is the secondary route.
   - Preview may still ship Blazor Desktop as bounded fallback only when the shelf, product cut, and platform matrix say so, but that posture does not satisfy gold.
   - A fallback head that becomes the sole or recommended public route is treated as flagship and must pass the flagship bar directly.

## Gate structure

Every promoted desktop release must carry the executable exit lanes in `DESKTOP_EXECUTABLE_EXIT_GATES.md` plus the following flagship proof lanes. A gold claim must publish per-head proof records for both desktop heads even when only one is the default public CTA:

### 1. Deterministic interaction lane

Automated headless UI tests must prove:

- clicking a top-level menu produces a visible submenu/command surface
- invoking settings from the shell produces an interactive in-shell dialog state
- the shell remains responsive after the settings flow opens
- the bundled demo runner can be loaded from the promoted desktop output
- core keyboard shortcuts still resolve to the same shell commands
- the shell preserves the familiarity bridge: classic menu order, toolstrip under menu, and a compact status strip with a visible progress indicator
- at least one imported deep-builder audit fixture exposes its full workflow-critical state in the promoted head rather than collapsing to shallow summary rows

### 1b. Workflow-equivalence lane

Automated release tests must prove:

- every legacy workflow family named in the parity oracle has a reachable desktop equivalent in the promoted head
- the parity checklist is backed by executable workflow proof rather than only catalog presence
- a Chummer5a audit fixture with rich cyberware state surfaces top-level implants, modular connectors, mounted payloads, and child subsystem/plugin state with enough detail for a paying user to inspect and reason about the build
- the same standard applies to the other major workflow families: gear, armor, vehicles, magic, resonance, contacts, lifestyles, notes, progress, rules, and validation

### 1c. Ruleset parity rollout order

The desktop parity program must advance in this order instead of declaring generic completion too early:

- Chummer5a parity first:
  - prove the promoted head is a trustworthy desktop equivalent for the Chummer5a workflow families the product still promises
- SR4 parity second:
  - use Chummer4 fixtures and workflow oracles to prove the SR4 desktop path explicitly
  - do not inherit SR4 trust from Chummer5a proof or flatten SR4 into SR5 posture
- SR6 cumulative workflow depth third:
  - carry forward the workflow families that make sense under SR6 rules
  - publish explicit blocked or not-applicable receipts for legacy workflow families that canon does not carry into SR6

The queue, release receipts, and flagship readiness proof must preserve this order so the fleet loop cannot return to `complete` after Chummer5a parity alone.

### 1d. Adversarial user-journey tester lane

Fleet must keep at least one tester shard available for a no-fix audit pass against the promoted Linux desktop binary. That shard behaves like a first-time serious user and publishes `USER_JOURNEY_TESTER_AUDIT.generated.json`.

Required audited workflows:

- `master_index_search_focus_stability`
- `file_new_character_visible_workspace`
- `minimal_character_build_save_reload`
- `major_navigation_sanity`
- `validation_or_export_smoke`

Each workflow requires before and after screenshots, actual user interactions, visible checkpoints, expected/actual notes, and any blocking finding IDs. The tester may record logs, but logs cannot replace visible UI proof.

### 2. Artifact-presence lane

Automated release checks must prove that the promoted output directory and packaged artifacts contain:

- the bundled demo runner fixture
- any release-critical help or support assets that the shell advertises at first launch

### 3. Visual-review lane

The promoted desktop head must publish screenshot evidence for:

- initial shell
- menu open
- settings open
- loaded runner
- at least one dense section in light theme
- at least one dense section in dark theme

Those screenshots are reviewed against the shared design contract:

- clear hierarchy
- stable primary actions
- visible selection/focus
- no clipped or hidden command semantics
- no low-contrast chrome or white-on-white / dark-on-dark regressions
- decodable image integrity and review resolution high enough to judge real desktop posture instead of tiny or corrupt placeholders

### 4. Signoff lane

`WORKBENCH_RELEASE_SIGNOFF.md` and the generated release evidence must cite the executable UI gate by name. A green build without this lane is not flagship-proof.

### 5. Visual familiarity lane

The promoted desktop head must publish visual-familiarity proof as defined in `DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.md`.

That lane must explicitly prove:

- legacy-green light/dark readability
- compact desktop status-strip posture
- visible loaded-runner tab posture
- cyberware/cyberlimb workflow-local visual familiarity

## Failure policy

This gate is strict:

- If a shell command only changes invisible state, the gate fails.
- If a menu click does not surface visible command choices, the gate fails.
- If settings or another core command leaves the user in a confusing or apparently frozen posture, the gate fails.
- If the shipped output claims a bundled demo runner but the file is missing, the gate fails.
- If dark/light screenshots reveal unreadable contrast or broken state treatment, or if the screenshots are corrupt or undersized, the gate fails.
- If the promoted head only proves shell chrome while a Chummer5a workflow family still lacks a usable equivalent, the gate fails.
- If Blazor is labelled fallback but the lane does not also name Avalonia as the primary head, the gate fails.
- If a gold claim ships any secondary desktop head on thinner proof than the primary head, the gate fails.
- If Blazor is the only user-facing desktop head or the recommended download and it lacks full flagship proof, the gate fails.
- If any workflow family is proven only by the other head and no bounded replacement story exists, the gate fails.
- If the parity checklist claims a workflow family is covered but no executable release proof exists for it, the gate fails.
- If either executable desktop-exit receipt is missing, stale, or failing, the gate fails.
- If the visual-familiarity receipt is missing, stale, or failing, the gate fails.
- If the user-journey tester audit is missing, generated by the fixing shard, uses internal APIs, lacks multiple screenshots per workflow, or reports open blocking findings, the gate fails.
- If Master Index search loses focus while typing or `File > New Character` does not show a visible character workspace, the gate fails even when lower-level build state changes.

## Scope

This gate is release-blocking for:

- `chummer6-ui` desktop heads
- `chummer6-ui-kit` shared shell primitives
- promoted desktop artifacts rendered through `chummer.run`

It is the current-target desktop bar, not a Horizon.
