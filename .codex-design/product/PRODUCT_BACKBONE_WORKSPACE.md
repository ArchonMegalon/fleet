# Product Backbone Workspace

This file defines the convergence target for Chummer's primary engineering home.

## Goal

Create one primary product workspace named `chummer-product`.
It is the main integration home for flagship desktop, deterministic engine, dossier/campaign truth, workspace and sync, registry/update, support/trust, fallback heads, and bounded media/AI adjuncts.

This does not require an immediate monorepo rewrite.
Repo boundaries may stay where deployment, release, or ownership boundaries are real.
The rule is that product truth compiles through one workspace before it fans back out into repo-local delivery boundaries.

## Non-goals

* do not delete Fleet or EA
* do not weaken package or service boundaries that already protect runtime truth
* do not move AI or media work onto the core product path
* do not treat repo count reduction as the success metric

## Workspace doctrine

### 1. Product model first

The primary top-level modules are user-facing product domains, not the repo graph:

* `engine`
* `dossier-campaign`
* `rules-environment`
* `workspace-sync`
* `registry-update`
* `support-trust`
* `desktop-flagship`
* `desktop-fallback`
* `mobile`
* `media-ai-adjuncts`

### 2. Desktop flagship first

`Chummer.Avalonia` remains the primary flagship desktop head.
`Chummer.Blazor.Desktop` remains the bounded fallback desktop head.

The promoted desktop route must prove:

* classic menu plus toolstrip posture
* dense central workbench
* compact bottom status strip
* no dashboard-first startup
* Chummer5a familiarity under first-minute veteran tasks

### 3. Parity lab is release-blocking

Flagship replacement claims require a dedicated parity lab with:

* Chummer5a screenshot baselines
* first-minute veteran task packs
* import/export round-trip fixtures
* performance budgets for core table-pressure jobs
* dense-workbench noise and spacing budgets

`covered` in parity docs is not enough for flagship replacement.
The release-facing progression is:

* `documented`
* `implemented`
* `task_proven`
* `veteran_approved`
* `gold_release_ready`

### 4. Local-first runtime, explicit sync semantics

Desktop is the lived work surface.
Sync and hosted services extend that surface; they do not silently replace it as the user's only source of truth.

Workspace convergence must keep:

* durable local state
* provenance-preserving import/export
* explicit conflict and restore semantics
* install-aware recovery

### 5. Registry and update truth are product surfaces

Downloads, claim, update, rollback, and support routing are in-product concerns.
The workspace must converge desktop shell, Hub, and Registry so claim/update/recovery stop depending on browser ritual where avoidable.

### 6. Public surfaces compile from product manifests

Public docs, release notes, FAQ, trust copy, and guide exports should compile from product and release truth.
Parallel prose is allowed only when it does not weaken public honesty.

### 7. Fleet and EA are adjunct control planes

Fleet and EA remain important execution systems.
They must not become second architecture authors.

The control rule is:

* design canon defines product truth
* `chummer-product` integrates that truth into one product workspace
* release and runtime systems consume the workspace truth
* Fleet and EA may schedule, verify, summarize, and remediate, but not fork the architecture ontology

## Immediate convergence order

### Wave 1. Establish the workspace backbone

Create `chummer-product` as the primary integration home.
Use it to map current repos into the product-model modules above.

### Wave 2. Build the parity lab

Turn Chummer5a familiarity, screenshot, workflow, and round-trip expectations into executable proof lanes.

### Wave 3. Make classic dense workbench the default flagship posture

UI Kit must expose a compact flagship preset.
Avalonia must consume it as the default for the flagship desktop route.

### Wave 4. Make registry/update/account flow desktop-native

Claim, update, rollback, support, and release-channel truth must surface in-app before the product claims flagship replacement.

### Wave 5. Demote public-surface drift

Generated public surfaces, release proof, and support/trust copy must compile from the workspace and release truth instead of parallel storytelling.

## Acceptance checks

The convergence is not successful until all of the following are true:

* the product workspace is the first place a whole-product audit runs
* parity lab results are release-blocking for flagship claims
* Avalonia is the unambiguous primary desktop route
* dense classic workbench is the default flagship posture
* registry/update/account flows feel desktop-native
* Fleet and EA consume workspace truth instead of inventing parallel product structure
