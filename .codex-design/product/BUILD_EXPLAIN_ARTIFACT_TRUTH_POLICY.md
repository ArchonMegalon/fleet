# Build and Explain artifact truth policy

## Purpose

This file defines how Build Lab explain companions may look polished without becoming rules truth.

The product promise is not "video explains the build."
The product promise is that a rendered companion stays subordinate to the same inspectable engine packet, receipt anchors, and approval record that the desktop and service surfaces can already open directly.

## Product promise

Build and Explain companion artifacts are first-class presentation outputs for:

- compare summaries
- import follow-through
- blocker and support follow-through
- Build Lab variant and progression walkthroughs

They are allowed to feel premium.
They are not allowed to outrun the inspectable packet, replace receipt review, or invent approval truth.

## Truth order

The required truth order for every Build and Explain artifact is:

1. engine-owned explain packet and receipt payload
2. inspectable packet anchors and JSON-pointer-backed claim scope
3. approval truth for the exact packet revision and artifact family
4. rendered media, preview-card, or narrated sibling

If those layers disagree, the lower layer wins.
Media is always the lowest layer in this stack.
Approval truth may decide whether an artifact ships, but it may not rewrite packet facts, anchor scope, or receipt severity.

## Inspectable engine truth

Every promoted Build and Explain artifact must stay traceable to inspectable engine truth.

That means:

- the artifact must name the approved explain packet or receipt id it summarizes
- every non-trivial claim must map to a packet anchor, receipt section, or explicit "inspect packet for full detail" fallback
- legality, delta, blocker, and recommendation language may only summarize approved packet fields that already exist in inspectable product truth
- packet anchors must remain visible enough that the user can inspect the exact source without trusting narration alone
- rule-environment identity must stay attached so packet-derived claims never drift away from the engine state that produced them
- anchor labels, packet revision identity, and approval scope must survive into every launch surface, preview card, caption bundle, or narrated sibling that summarizes the packet

If a media lane cannot keep that traceability, the product must fall back to the packet, preview card, or text summary instead of emitting a weaker artifact.

## Receipt and anchor minimums

Every Build and Explain companion artifact must carry or expose:

- the exact packet revision id or receipt digest it summarizes
- the rule-environment id or digest that produced the packet
- the anchor ids, JSON pointers, or receipt sections that bound each factual claim class in the artifact
- the approval record scope for the exact artifact family, locale, and audience posture

If any of those fields are missing, stale, revoked, or mismatched, the product must fail closed to the inspectable packet, preview card, or localized text fallback instead of rendering a companion that looks authoritative.

Approval posture is publishability metadata.
It is not a substitute for the packet revision, rule-environment identity, or claim anchor set.

## Claim classes

Build and Explain artifacts may emit only these claim classes:

- packet identity: what packet, variant, import, or blocker lane this artifact belongs to
- anchored summary: a concise restatement of an existing approved packet section
- anchored delta: a before-versus-after or option-versus-option summary that already exists in the packet or anchor set
- anchored warning: a blocker, incompatibility, or caution already present in inspectable receipts
- anchored approval posture: whether this exact artifact family, locale, and audience posture is approved to publish for the packet revision
- next-step routing: where to open the inspectable packet, compare view, import detail, or blocker detail next

Build and Explain artifacts may not emit:

- new legality decisions that are absent from the packet
- hidden optimizer rationale that only exists in narration
- rulebook claims with no receipt anchor or packet section
- approval claims for variants or revisions that were not explicitly approved
- approval badges or language that imply the packet itself changed when only the render or locale changed
- broader "best build" or "safe to publish" language than the packet itself supports

## Approval truth

Approval truth decides whether a packet revision may publish a companion artifact.
Approval truth does not rewrite engine truth.

Required approval rules:

- approval attaches to an exact packet revision, artifact family, locale, and audience posture
- re-rendering a companion does not create a new approval right if the underlying packet revision changed
- if approval is revoked, stale companions must fall back to packet-only launch posture
- approval may authorize tone, copy polish, or publication surface, but it may not authorize unanchored factual additions
- approval may mark a packet revision publishable, blocked, or revoked for a given artifact family, but the underlying blocker, legality, and delta facts still come from the inspectable packet and anchor receipts

## Launch and UI rules

Every promoted Build and Explain companion surface must offer an inspectable sibling action such as:

- `Open explain packet`
- `Inspect receipt anchors`
- `Open compare details`
- `Open import detail`
- `Open blocker detail`

Companion artifacts may be the warm entry point.
They may not be the only route to the underlying truth.
If packet revision, anchor scope, or approval scope cannot be shown honestly on launch, the companion must open directly to the packet or receipt instead of a narrated artifact shell.

## Localization and fallback

Build and Explain companions use the product locale rules from `LOCALIZATION_AND_LANGUAGE_SYSTEM.md`.

Required fallback posture:

- localized narration may ship only when localized captions and localized inspectable sibling copy also exist
- fallback to another locale must preserve the same receipt anchors and claim scope
- locale fallback may degrade presentation polish, but it may not widen claim scope or hide missing anchors
- locale fallback may not rewrite packet revision labels, approval-state labels, or rule-environment identity into freer summary copy
- when localized media is unavailable, Chummer should prefer the localized packet, captions, or text summary before emitting a mismatched narrated artifact

## Surface-specific guardrails

### Compare companions

Compare companions may summarize tradeoffs that already exist in the compare packet.
They may not hide the losing side effects, rule-environment differences, or blocked prerequisites that the packet shows.

### Import companions

Import companions may summarize landed data, bounded loss, and next repair steps.
They may not imply silent parity or successful migration when the import receipt marks bounded loss, manual review, or a blocker.

### Blocker and support companions

Blocker and support companions may restate inspectable blocker receipts and approved support closure facts.
They may not speak as if narration itself fixed the problem.

## Non-goals

This file does not:

- turn Build Lab media into a second rules engine
- make narration the canonical review lane
- let approval tools or providers become approval truth
- authorize generated "coach" copy that outruns inspectable receipts
