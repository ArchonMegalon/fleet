# Fleet Vision & Authority Charter for Chummer6-Design

Date: 2026-03-17
Scope: planning feedback for how `chummer6-design` should treat Fleet and Executive Assistant (EA) authority, worker topology, and cost governance.

Use this as design-planning input and queue-shaping guidance. This is feedback, not approved canon yet.

## Purpose

This document defines the intended role of **fleet** in the Chummer6 ecosystem, the authority boundaries for the **chummer6-design** team, and the architectural direction that should guide planning decisions.

The core intent is:

- make fleet the **design-aware orchestration layer** for Chummer6 work,
- keep the single coding worker **cheap-first** and **evidence-driven**,
- reserve expensive model lanes for explicit escalation,
- give Chummer6-design clear authority over design truth, planning truth, and dispatch policy,
- keep operational budget and provider controls under fleet / EA operator governance.

## One-line vision

**Fleet should become the mission control system that turns approved Chummer6 design truth into cheap, staged, executable work - while Executive Assistant (EA) acts as the provider-aware intelligence and telemetry substrate underneath it.**

## Strategic position

Fleet should not be treated as "just a nonstop coding loop."

Fleet is already evolving into a control plane with:

- a controller/spider,
- a Studio design surface,
- an Admin operator console,
- an Auditor,
- a dashboard,
- and a compile pipeline that separates design truth, policy truth, and execution truth.

That is the right direction.

Chummer6-design should therefore plan against fleet as a **multi-stage mission system**, not as a simple developer assistant.

## What fleet should be responsible for

Fleet should own five things:

### 1. Design truth compilation

Fleet should be the system that turns approved design discussion into canonical artifacts such as:

- `VISION.md`
- `ROADMAP.md`
- `ARCHITECTURE.md`
- runtime instructions
- queue overlays

### 2. Dispatch truth compilation

Fleet should decide which work is dispatchable now, which is blocked, and which must remain design-only.

### 3. Lane selection and cost governance

Fleet should decide whether work belongs in:

- easy/orient
- repair/implementation
- groundwork/slow analysis
- core/escalation
- jury/audit
- survival/emergency

### 4. Review and signoff workflow

Fleet should gate queue advancement based on verify, review, design signoff, and operator policy.

### 5. Runway awareness

Fleet should continuously understand spend posture, account readiness, lane pressure, and sustainability.

## What Chummer6-design should have authority over

The Chummer6-design team should have authority over:

### A. Canonical product/design intent

They own the answer to:

- what Chummer6 should become,
- what user experience is intended,
- what quality bar is acceptable,
- what tradeoffs are approved.

### B. Publishable design artifacts

They should own approval and publication of:

- vision
- architecture
- roadmap
- UX/product rules
- backlog shaping guidance
- acceptance/risk criteria

### C. Queue-shaping authority

They should be able to influence:

- priority order,
- whether work is design-only or dispatchable,
- whether a project is still in scaffold/planned mode,
- what work must go through groundwork or jury before coding.

### D. Review policy for design-sensitive work

They should be able to require:

- design review,
- architectural review,
- narrative/UX audit,
- no-merge-until-feedback.

## What Chummer6-design should NOT fully own

To avoid broken incentives, Chummer6-design should not be the sole authority over:

### A. Provider secrets and budget caps

This belongs to EA/fleet operators.

### B. Global spend policy

Design may request stronger lanes, but operator governance should decide whether that is affordable.

### C. Emergency runtime operations

Examples:

- degraded provider response
- key revocation
- account refill
- traffic shedding
- survival mode activation

### D. Merge authority on high-risk operational code

Protected operational logic should still require operator/reviewer approval.

## The right architecture for fleet

The best model is not "add more bots."

The best model is a **cascade architecture** where each layer does only the work it is economically suited to do.

### Layer 1 - Design/control plane

Handled by fleet Studio/Admin/Auditor.

Responsibilities:

- discuss intent
- publish truth
- generate queue overlays
- classify maturity
- create constraints and acceptance policy

### Layer 2 - Cheap orientation layer

Handled by cheap-first lanes and EA MCP tools.

Responsibilities:

- inspect repo state
- gather context
- summarize diffs
- identify likely files/tests/contracts
- prepare compact task packets

Default provider posture:

- Gemini-backed easy work
- deterministic tools first

### Layer 3 - Repair worker

Handled by the main coding worker.

Responsibilities:

- bounded edits
- first-pass implementation
- local verify
- small-to-medium patch generation

Default provider posture:

- fast lane
- cheap code models
- no expensive escalation on first attempt

### Layer 4 - Groundwork worker

Handled by a separate async worker.

Responsibilities:

- architecture analysis
- deep tradeoff review
- second-pass reasoning
- product/UX/design alignment checks
- contradiction detection
- slow evidence-heavy work

Default provider posture:

- Gemini Vortex first
- ChatPlayground as cheap/free second-pass reviewer
- no default onemin use

### Layer 5 - Core escalation

Handled only when justified.

Responsibilities:

- truly hard reasoning
- risky implementation
- protected-branch work
- repeated repair failure
- migration/auth/payment/release logic

Default provider posture:

- onemin / stronger model lane
- budget-guarded and capacity-aware

### Layer 6 - Jury / final audit

Handled only for signoff or contradiction resolution.

Responsibilities:

- final review
- multi-angle audit
- design/policy conflict resolution
- publish-grade confidence checks

Default provider posture:

- ChatPlayground / audit-specific lane
- async by default

## How I would adapt the current system

The current fleet/EA direction is good, but I would refine it in three important ways.

### 1. Do NOT invent a separate "Vortex" product first

Treat Vortex-like behavior as **capabilities inside fleet + EA**, not as a whole new control plane.

What to add instead:

- semantic context packing,
- diff-aware task packet generation,
- caching of repeated context/problem shapes,
- telemetry-first shortcuts.

That gives the benefits of a semantic gateway without multiplying systems.

### 2. Do NOT let the coding worker live on core by default

The default coding worker should be **repair**, not core.

Core should only happen when:

- risk is explicitly high,
- lane policy allows it,
- cheap attempts failed,
- or a human/operator explicitly escalates.

### 3. Add one dedicated groundwork/audit worker before adding more coding workers

If you add another worker, it should not be another generic coder first.

It should be a **serialized async groundwork/audit worker**.

That worker:

- consumes groundwork and jury tasks,
- does not directly own normal branch-writing throughput,
- improves decision quality,
- allows the main coding worker to stay cheap.

## Recommended worker topology

### Worker A - Main coding worker

Primary purpose:

- implement bounded slices cheaply

Default lane order:

- easy for orientation
- repair for implementation
- core only by escalation

### Worker B - Groundwork / audit worker

Primary purpose:

- analyze, challenge, clarify, review, and package higher-order work

Default lane order:

- groundwork
- jury when required
- no default code-writing authority

### Optional Worker C - Review-only fallback

Only add later if there is distinct capacity and enough review backlog.

## Design authority workflow for Chummer6-design

### Phase 1 - Design compile

Chummer6-design produces/approves:

- product intent
- UX direction
- architecture decisions
- acceptance criteria
- milestone shaping

### Phase 2 - Policy compile

Fleet translates approved design into:

- queue overlays
- runtime instructions
- blocker files
- route policy
- review requirements

### Phase 3 - Execution compile

Fleet turns policy into dispatchable work for:

- controller
- auditor
- healer
- reviewer
- groundwork worker

### Phase 4 - Operational feedback

Fleet returns:

- run outcomes
- review findings
- budget/runway signals
- blocked assumptions
- design contradictions

That gives Chummer6-design real authority **without** forcing them to own runtime operations.

## Cost philosophy

The system should follow this rule:

**Never spend expensive credits to discover what cheap lanes could have discovered first.**

That implies:

### Cheap/default

Use easy + repair for:

- repo reading
- file discovery
- summary
- bounded patch drafting
- first implementation attempts

### Slow but cheap-smart

Use groundwork for:

- complex design analysis
- architecture comparison
- narrative/UX alignment
- deep non-urgent planning

### Expensive only by exception

Use core for:

- high-risk implementation
- repeated bounded failure
- narrow hard reasoning

### Audit only when it matters

Use jury for:

- final signoff
- contradiction resolution
- critical release/publish checks

## What success looks like

Within this vision, success is not "more automation."

Success means:

- most work routes through easy/repair/groundwork,
- core is rare and explainable,
- jury is explicit and meaningful,
- Chummer6-design can publish authoritative truth without editing repo guts by hand,
- fleet can show runway and shed load before budget panic,
- a single coding worker stays productive and cheap,
- the groundwork worker makes the system feel smarter without forcing expensive models into the hot path.

## Authority charter (short version)

### Chummer6-design owns

- design truth
- product intent
- roadmap truth
- architecture truth
- queue-shaping proposals
- review requirements for design-sensitive work

### Fleet/EA operations own

- provider wiring
- account budgets
- refill/quarantine/revocation handling
- lane caps and emergency posture
- survival mode
- protected runtime operations

### Shared approval zone

- dispatchability
- publish readiness
- lane policy for critical work
- review gates on major releases

## Immediate planning recommendations for Chummer6-design

1. Treat fleet as the authoritative design-to-dispatch control plane.
2. Push product/design decisions into published artifacts, not ad hoc chat.
3. Assume the main coding worker should stay cheap.
4. Request a separate groundwork/audit worker before requesting more core capacity.
5. Use ChatPlayground primarily as a groundwork/jury substrate, not the default coding engine.
6. Keep core as a rare escalation lane.
7. Make runway/budget awareness a first-class planning input.

## Final recommendation

Yes - the broad direction fits.

But I would present it to Chummer6-design like this:

**Fleet is not just a worker runner. It is the design-aware mission compiler for Chummer6.**

And I would make one important adjustment to the earlier "semantic gateway / scheduler / EA orchestrator" framing:

- keep the architecture centered on the fleet control plane you already have,
- extend it with semantic context packing, groundwork routing, and cheaper staged escalation,
- and avoid creating a second independent orchestration stack unless the current one clearly tops out.

That gives Chummer6-design real planning authority while keeping the system economically sane.
