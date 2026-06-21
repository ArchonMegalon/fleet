# Horizon design instructions

Horizons are future product lanes. They must make the future legible without making it feel shipped.

These instructions apply to:

* `HORIZON_REGISTRY.yaml`
* `products/chummer/horizons/*.md`
* generated `Chummer6/HORIZONS/*.md`
* horizon art and public-guide media briefs
* any EA, Fleet, or media-factory prompt that regenerates Chummer6 horizon pages

Use `HORIZON_IMAGE_RELEVANCE_AUDIT.md` as the current per-horizon image critique and replacement backlog.

## Reader contract

A horizon page is written for a GM, player, organizer, creator, or curious visitor first.

The first screen must answer:

* what table pain this solves
* what the future product would feel like in play
* why Chummer is the right place for it
* why it is not promised or shipped yet

Do not make the reader decode internal program structure before they understand the table value.

## Strong horizon shape

The best current pattern is:

1. Human promise.
2. Concrete table pain.
3. One real table scene with GM, player, runner, fixer, organizer, or creator pressure.
4. What the product lane would do.
5. What it must never do.
6. Trust boundaries and source-of-truth ownership.
7. First proof slice.
8. Why it remains a horizon.

BLACK LEDGER and KARMA FORGE are the model: vivid, product-shaped, and clear about authority boundaries.

## Required design posture

Every horizon must keep three truths visible:

* **Human value:** the reader should be able to say what gets easier at a table.
* **Product boundary:** the page must say what Chummer owns and what humans still decide.
* **Current posture:** the page must not imply active availability, near-term shipment, or hidden runtime truth without executable proof.

If one of those is missing, the horizon is not ready for public guide generation.

## Public copy rules

Public horizon copy must use plain product language.

Use:

* table scene
* campaign memory
* rule environment
* mission market
* world tick
* runner dossier
* approval receipt
* player-safe recap
* GM signoff
* consent-gated debrief
* first proof slice

Avoid:

* repo names as primary explanation
* file paths
* foundation codes such as `C0`, `D2`, or `E2b` in casual-reader pages
* "what would need to exist first" sections in public guide output
* "canon links" sections in public guide output
* implementation-trail language
* source-trail language
* internal jokes
* placeholder slogans that do not describe table behavior

Design docs may keep technical details, but public generated pages must translate them.

## Registry rules

Each public horizon registry entry should carry:

* `pain_label`: the user pain in one sentence
* `wow_promise`: the table-facing promise, not an implementation claim
* `table_scene`: a concrete moment at play or prep
* `success_signals`: proof that the lane is becoming real
* `artifact_types`: what visible receipts, packets, maps, or media it might produce
* `owner_handoff_gate`: the boundary that must be proven before promotion

If the registry cannot describe those in human terms, the horizon should stay out of public guide generation.

## Generator rules

Generators must prefer long-form human horizon canon over compressed fallback copy.

When long-form body text is missing, the safe fallback is a short plain-language horizon page with:

* promise
* table scene
* current posture
* first proof needed

The unsafe fallback is a page made from foundation IDs, repo paths, "canon links", or internal implementation lists.

Public guide generators must strip or avoid:

* `Canon Links`
* file paths
* repo names used as explanation
* foundation-code checklists
* source-trail wording
* timestamp footers
* unsupported shipment claims

## Media rules

Horizon media should look like a scene from the product's future, not like a generic sci-fi wallpaper.

Flagship horizon images should have:

* vivid, polished poster quality
* lifted midtones and readable faces, hands, gear, and props
* a clear physical action
* at least one Shadowrun-specific clue: metahuman presence, cyberware, talismonger residue, corp pressure, critter trace, black-clinic aftermath, or street-level logistics
* AR or smart-lens details only when they clarify what the character in the scene is reading

AR text is allowed and often useful, but it must be sparse, readable, and anchored to visible geometry.

Good AR labels sound like a runner, streetdoc, rigger, decker, GM, or fixer would actually need them:

* `NERVE SYNC`
* `JOINT SEAL`
* `PAIN WATCH`
* `GRIP TEST`
* `HEAT +1`
* `GM SIGNOFF`
* `PLAYER SAFE`
* `ROLLBACK READY`
* `CONSENT CHECK`

Bad AR is generic decoration: floating dashboards, unreadable glyph fields, decorative rectangles, random warnings, or labels that do not match the scene.

## External tool posture

External tools may help discover, draft, render, schedule, project, summarize, or amplify horizons.

They must not own:

* rules truth
* world truth
* support truth
* notification truth
* approval truth
* consent truth
* entitlement truth
* public-roadmap truth

Tool-powered horizon ideas need Chummer-owned receipts, first-party pages, and explicit source-of-truth boundaries before they affect architecture or public claims.

## Promotion rule

A horizon can move toward build work only when it has:

* a human-readable product promise
* a bounded first proof slice
* owning repo responsibilities
* source-of-truth ownership
* consent/privacy posture where relevant
* public-copy posture
* media/artifact posture where relevant
* executable proof or a milestone path to produce it

Public excitement is not a promotion gate. It is an input to discovery.

## Review checklist

Before publishing or regenerating a horizon page, ask:

* Would a casual visitor understand the value without reading another repo?
* Would a GM know what authority they keep?
* Would a player know what is visible to them?
* Does the page say what is not shipped yet?
* Does every tool stay bounded to assistance, projection, or rendering?
* Does every image show a real product scene instead of style alone?
* Does every readable AR label fit what the character is seeing?
* Are internal file paths, foundation codes, and repo-speak absent from public output?

If the answer is no, fix the horizon before it reaches `Chummer6`.
