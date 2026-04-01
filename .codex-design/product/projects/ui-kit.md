# UI kit implementation scope

## Mission

`chummer6-ui-kit` owns design tokens, shared shell chrome, accessibility primitives, state badges, dense-data primitives, and cross-head visual building blocks.

## Owns

* color/spacing/typography/motion tokens
* theme compilation
* reusable primitives
* shell chrome patterns
* accessibility primitives
* dense-data presentation primitives
* Chummer-specific reusable UI patterns

## Must not own

* domain DTOs
* HTTP clients
* local storage logic
* rules math
* service orchestration
* registry or media business logic

## Current focus

* keep the package-only shared UI boundary healthy for presentation and play
* preserve deterministic adapter and preview contracts
* grow the component catalog additively without reopening the shared-boundary question

## Milestone spine

* U0 governance
* U1 token canon
* U2 primitives
* U3 shell chrome
* U4 dense-data controls
* U5 Chummer-specific patterns
* U6 accessibility/localization
* U7 visual regression/catalog
* U8 release discipline
* U9 finished design system

## Worker rule

If a component should be shared by workbench and play, it belongs here.
If it requires domain DTOs or service calls to exist, it probably does not.

## Flagship-grade bar

`chummer6-ui-kit` is not flagship grade until:

* dense-data tables, compare grids, inspectors, effect chips, and timeline primitives let expert users scan and act at speed
* keyboard, pointer, focus, contrast, and localization-safe wrapping are first-class in promoted surfaces rather than retrofit chores
* shared primitives can express active rule-environment posture, package conflicts, preview diffs, and restore warnings without each head inventing its own package UX
* shared primitives can express edition-authored cues, preview and hazard posture, and recovery messaging without each head reinventing them
* motion, empty states, and progressive disclosure feel intentional instead of reading like generic admin scaffolding

## Current reality

The active shared boundary is release-ready for the current program scope.

That means:

* shell, banner, stale-state, approval, offline, and accessibility primitives are package-owned and verifier-backed
* cross-head hardening closure uses explicit owner evidence in `docs/SHARED_SURFACE_SIGNOFF.md`
* future dense-data and catalog expansion are additive design-system growth, not a blocker on the current release lane

## Package bootstrap rule

`Chummer.Ui.Kit` must restore through a canonical package feed or an explicit generated compatibility tree for legacy consumers.

The shared UI boundary is not considered healthy if downstream restore still depends on source-present local trees by accident.


## External integration note

`chummer6-ui-kit` may style or present upstream provider-assisted state, but it must not own:

* vendor SDK integrations
* external API clients
* provider routing logic
* provider receipt schemas
