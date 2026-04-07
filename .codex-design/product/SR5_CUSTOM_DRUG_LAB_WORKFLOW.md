# SR5 Custom Drug Lab Workflow (Feature Design)

## Intent

Add a dedicated SR5 drug-lab workflow in Build Lab that models drug synthesis as a
first-class planning activity instead of a generic inventory action.

This feature is intended to be flagship-grade for SR5 gameplay:

- explicit state, explanation, and risk
- deterministic rule-backed outcomes
- parity across Avalonia and Blazor
- no plugin-based fallback for core behavior

## Scope (current slice)

- Apply to SR5 runtime context only.
- Operates as an SR5-specific Build Lab lane.
- Uses existing SR5 rules-engine projections and rule-pack/amend-package context.
- Must be surfaced from Build Lab and campaign continuity handoff paths.
- Does **not** implement custom chemistry plugin loading, script DSL execution, or third-party calculation engines.

## User problem

Players need an intentional path to plan drug synthesis workflows without treating
reagents and labs as static item operations. Current UX paths flatten synthesis as
single-step item effects, hiding:

- required precursors and missing dependencies
- synthesis risk windows
- legality/reputation side effects
- expected timing and contamination failure modes

## User story

As an SR5 player, I want to build a drug in a lab flow that shows:

1. what is required,
2. what can fail,
3. what modifiers apply in context,
4. what the resulting effect profile is,
so I can decide whether to continue, revise plan, or defer.

## Workflow definition

### 1. Entry + context binding

- Workflow starts from Build Lab with explicit SR5 context selector.
- Binds to:
  - character
  - current campaign environment (optional)
  - current source-pack/amend-package set
  - legality policy and visibility level

### 2. Intake and recipe creation

- User selects chemical source and lab setup.
- UI surfaces:
  - required reagent tuple (name + quality/quantity)
  - expected duration and required test gear
  - incompatibility blockers
- If prerequisites are incomplete, workflow stays in `NeedsInputs` and shows
  actionable fill steps.

### 3. Synthesis simulation state machine

States:

- `NeedsInputs`
- `ReadyForMix`
- `InProgress`
- `CriticalRisk`
- `ValidatedResult`
- `Rejected`

State transitions are explicit and explained in the UI.

### 4. Result packet

On `ValidatedResult`, user sees:

- final effect bundle
- source of truth references:
  - applied ruleset section
  - risk outcomes and randomization envelope
  - legality and social fallout markers
- export/handoff artifact:
  - living dossier suggestion
  - campaign continuity marker
  - explain receipt

### 5. Post-flow

- Save as build-lab artifact.
- Optionally convert directly into active dossier entry or campaign action.
- Export retains audit-ready provenance.

## Product guarantees

- Deterministic engine-backed computation for all legal outcomes.
- UI never renders drug effects that are not present in engine payload.
- Every step can cite a rationale token (source/ruleset section + payload token).
- All failures explain specific blocked inputs, not generic error text.

## Cross-head parity requirements

- Same workflow data model and transitions must be emitted by both heads.
- Same explain packet shape must be renderable in both Avalonia and Blazor.
- Any divergence must be explicit in the gate evidence.

## Design acceptance criteria

- A player can complete the full SR5 lab workflow without external calculator tools.
- At least one successful and one rejected outcome is reproducibly previewable.
- Every transition has a visible reason and linked rule reference.
- Export/handoff preserves provenance and does not alter character state.
- Gate evidence includes a dedicated `drug_lab_workflow` section for:
  - inputs snapshot
  - precondition checks
  - risk outcomes
  - result packet digest

## Non-goals

- Generic chemistry simulation outside SR5
- Plugin-defined synthesis engines
- Runtime execution that changes source truth without contract-provided receipts

## Open questions

- Should failed synthesis create a recoverable “post-failure state” with contamination and cleanup actions?
- What minimum legal fallout detail should be surfaced before handoff?
- Does campaign mode require batch IDs for repeatable lab operations or single-shot operations only?
