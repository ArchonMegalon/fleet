# Subscribr Script Factory Provider Boundary

## Classification

Subscribr is a governed video pre-production lane for Chummer.

It is not a horizon, not a public runtime feature, and not a publication authority.

The owned account is recorded as License Tier 7 / Scale 3. Workspace promotion still starts at Tier 4 until provider proof, channel mapping, source binding, export receipts, and human review are complete.

## Job

Subscribr may help turn approved Chummer source packets into:

* video ideas
* hooks and titles
* outlines
* draft scripts
* descriptions and tags
* shot lists
* thumbnail briefs
* production-board items

The output is a draft.
Chummer reviews it before narration, rendering, or publication.

## It must not own

Subscribr must not own:

* rules truth
* character legality
* release truth
* sourcebook interpretation
* entitlement or account truth
* private campaign material
* publication approval
* direct YouTube publishing

## Channel map

Use separate channels so voices do not bleed into each other:

* `chummer-official` for release, install, and update scripts
* `chummer-academy` for tutorials
* `black-ledger-newsroom` for editorial drafts only
* `chummer-gm-foundry` for GM workflow videos
* `runner-stories` for approved Origin Dossier story media
* `chummer-devlog` for technical explainers
* `chummer-de` for German scripts
* `integration-lab` for private provider tests

## Content modes

Every request must declare one mode:

* `STRICT_CANON` for install, update, rules-explanation, and product tutorials from approved sources only
* `TUTORIAL` for UI walkthrough scripts tied to current screenshots and routes
* `EDITORIAL_RESEARCH` for Black Ledger or community commentary with exported sources
* `NARRATIVE_DOSSIER` for approved origin and faction story packets
* `MARKETING_EXPERIMENT` for hooks, titles, thumbnails, and format tests

## Source packet rule

Chummer produces the source packet first.

The packet must include:

* allowed claims
* forbidden claims
* source hashes
* channel key
* audience
* language
* freshness deadline
* privacy classification
* copyright classification

Provider output that drifts from the packet is rejected.

## Approval rule

Subscribr board state is not approval.

Canonical approval remains in Chummer / EA:

```text
SOURCE_PACKET_READY
-> SUBSCRIBR_DRAFTING
-> DRAFT_READY
-> VALIDATING
-> REVIEW_REQUIRED
-> APPROVED_SCRIPT
-> NARRATION_READY
-> RENDER_CANDIDATE
-> PUBLICATION_REVIEW
-> PUBLISHED
```

No script may publish without a separate Chummer publication receipt.

## Feature flags

```yaml
EA_SUBSCRIBR_ENABLED: false
EA_SUBSCRIBR_API_ENABLED: false
EA_SUBSCRIBR_AGENT_MODE_ENABLED: false
EA_SUBSCRIBR_INTEL_ENABLED: false
EA_SUBSCRIBR_THUMBNAILS_ENABLED: false
EA_SUBSCRIBR_WEBHOOKS_ENABLED: false
EA_SUBSCRIBR_DIRECT_PUBLISH_ENABLED: false
```

`EA_SUBSCRIBR_DIRECT_PUBLISH_ENABLED` stays false until a separate publication lane is designed, verified, and approved.

## Exit gate

The lane can move beyond Tier 4 only when Chummer has:

* provider account and API capability verification
* private-token proof
* channel map receipt
* one idea-to-Markdown-export roundtrip
* source-binding validation
* copyright and privacy boundary tests
* human-review enforcement
* direct-publish disabled proof
