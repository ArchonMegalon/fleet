# Desktop Visual Familiarity Exit Gate

Purpose: block release promotion when the desktop shell technically works but no longer feels recognizably like Chummer to a Chummer5a user.

Workflow parity is not enough on its own. A shell can open menus, load data, and still fail the trust test if:

- the light/dark themes drift into low-contrast or alien chrome
- the loaded-character posture reads like a generic document inspector instead of a Chummer workbench
- the character-loaded tab posture disappears and forces users back into navigation lists only
- dense builder workflows such as cyberware or cyberlimb add/edit flows lose the familiar left-list / right-detail / obvious confirm posture that legacy users rely on

## Hard release rule

Desktop release truth is `not ready` until this receipt exists and passes:

- `DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.generated.json`

This receipt is required in addition to:

- `DESKTOP_EXECUTABLE_EXIT_GATE.generated.json`
- `DESKTOP_WORKFLOW_EXECUTION_GATE.generated.json`

## Required proof areas

### 1. Shell familiarity posture

The promoted desktop shell must preserve the modernized Chummer5a posture:

- top desktop menu bar
- immediate toolstrip under the menu
- dense three-pane workbench center
- compact bottom status strip
- loaded-character tab posture that is visible without relying on multi-document chrome

The user explicitly does not need a full MDI-style document shell, but a loaded runner should still surface a visible tab panel / tab strip posture that feels close to Chummer5a.

### 2. Theme familiarity and readability

Light and dark themes must both prove:

- readable foreground/surface contrast
- readable accent-button text
- readable warning/danger tones
- a Chummer-adjacent palette anchor instead of generic blue/productivity chrome
- WCAG AA contrast for normal desktop text and control labels (`4.5:1` minimum) and at least `3:1` for large text, iconography, and non-text interactive state indicators
- every text-entry surface uses the shell text-input theme rather than framework default light/dark colors
- hover help never duplicates textbox content or creates overlapping text

The current baseline is a restrained legacy-green familiarity accent, not a literal pixel clone.

Across rulesets:

- SR4 may preserve older legacy-builder cues where Chummer4 remains the stronger oracle for a specific flow.
- SR6 should still keep a Chummer5a-familiar orientation model even when the builder content is adapted to SR6 rules semantics.
- The point is familiar orientation, not one frozen clone across every ruleset.

### 3. Workflow-local familiarity

The gate must cover not just shell chrome, but workflow-local visual familiarity for dense builder flows.

Release-blocking audit examples:

- character creation and first-save posture
- attributes editing with visible Base, Karma, Total, and Limit state plus compact `-` / `+` steppers
- karma-spend and post-creation advancement posture
- critter and non-metahuman builder posture where the ruleset supports it
- add/edit gear
- add/edit drugs, consumables, and temporary effect-bearing gear
- add/edit cyberdecks, decks/programs, and matrix-facing gear
- add/edit armor and weapons
- add/edit cyberware
- add/edit cyberlimbs
- modular connector / subsystem-bearing cyberware flows
- adept powers, initiation/submersion, and magic/resonance builder surfaces
- spells, rituals, ally spirits, spirits/sprites, familiars, and other conjuring/summoning-facing builder surfaces
- contacts, diary/career-log, notes, and other dense relationship/history side flows
- vehicle, car, drone, and rigger builder surfaces

This applies to SR4/SR5/SR6 alike:

- the rule-specific controls can differ
- the shell rhythm and dialog posture should still be familiar enough that a Chummer5a user can orient without relearning the whole product
- SR6-specific surfaces should keep stable landmarks for attributes/qualities, skills, augmentation, gear, lifestyles/licenses/SINs/contacts, and history/career review instead of scattering them into unrelated dashboard cards

For those flows, the modern UI does not need to clone Chummer5a exactly, but it must preserve the same mental model:

- obvious list/browse posture
- visible detail pane
- visible cost/essence/effect summary
- visible confirm/cancel posture
- no hidden “where do I click next?” step
- the user should still recognize the mental model from legacy Chummer even when the chrome is cleaner and the ruleset is SR6
- rule-aware helpers such as compatibility filtering or spend-mode toggles may be modernized, but they must stay inline with the main workflow instead of becoming detached wizard-only branches

### 4. Loaded-runner workbench familiarity

After a runner is loaded, the workbench must still read like a character-first builder:

- character tab posture is visible
- the active section is re-findable
- tab movement does not require rediscovering the whole shell
- a user who remembers Chummer5a’s tab rhythm can orient immediately

### 5. Screenshot evidence

The receipt must publish screenshot evidence for:

- initial shell light
- menu open light
- settings open light
- loaded runner light
- dense section light
- dense section dark
- loaded-runner tab posture light
- cyberware/cyberlimb dialog posture light

Every required screenshot must also prove:

- decodable PNG structure with valid chunk CRCs
- minimum review resolution of `1280x800` for shell/workbench captures
- minimum review resolution of `900x700` for dialog-local captures
- deterministic filenames that stay stable across reruns

### 6. Test framework design

The gate should combine:

- source-level palette/token assertions
- headless shell geometry assertions
- screenshot evidence publication
- explicit builder-familiarity tests for the cyberware/cyberlimb flow
- explicit loaded-runner tab-posture tests
- automated contrast assertions against the promoted theme token pairs

## Failure policy

The gate fails if any of the following are true:

- shell theme tokens drift away from readable, Chummer-adjacent palette anchors
- the bottom strip reads like a card or hero rail instead of compact desktop chrome
- a loaded runner still has no visible tab strip / tab panel posture
- the cyberware/cyberlimb add flow is only technically present but not visually familiar enough to be trustworthy
- required screenshot evidence is missing, corrupt, undersized, or unreadable
- required theme contrast assertions are missing or failing
- required familiarity tests are missing, stale, or failing
- any promoted dialog shows unreadable light/dark color pairings
- any textbox shows duplicate overlapping hover text

## Fleet handoff

Fleet must reopen desktop readiness when the visual-familiarity receipt is missing, stale, or failing.

Backlog shape:

- one shell-familiarity slice:
  - menu/toolstrip/status strip/theme/tabs
- one workflow-local familiarity slice:
  - cyberware/cyberlimb add/edit posture and other dense builder dialogs
