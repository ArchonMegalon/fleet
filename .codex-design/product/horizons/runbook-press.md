# RUNBOOK PRESS

## The problem

GMs, creators, and publishers need a reliable way to produce long-form books such as primers, campaign books, district guides, and convention modules.
Today that work is slowed down by table pain: source notes, table-heavy layouts, approvals, citations, and final print-ready packaging all drift apart, so teams spend too much time reformatting and too little time publishing.

## Bounded product move

Chummer should help teams turn approved source material into primers, handbooks, district guides, campaign books, and convention modules without making third-party dashboards the source of truth.
The move is deliberately narrow: take approved source packs, preserve editorial lineage, render the book, and hand back a publication package that stays inside Chummer-controlled truth.
It complements JACKPOINT instead of duplicating it.

## Owning repos

* `chummer6-design` - canonical design truth for the horizon and the guardrails around it
* `chummer6-hub` - source approval, publication manifests, and downstream publication control
* `chummer6-hub-registry` - artifact publication, release heads, and immutable release truth
* `chummer6-media-factory` - render jobs, preview generation, and media execution

## Key tool posture

* `First Book ai` - bounded drafting and blueprint support
* `Paperguide` - cited research support
* `Documentation.AI` - downstream help/docs projection
* `MarkupGo` - formatted document rendering
* `Soundmadeseen` - optional narrated companion assets
* `Unmixr AI` - candidate voice lane until proven

## Dependency foundations

* approved source packs
* publication manifests
* format and render adapters
* editorial approval flows
* citation and provenance retention through draft-to-release

## Current state

This is still a horizon, not a shipping surface.
The product motion exists, but the end-to-end chain is not yet stable enough to treat the book pipeline as flagship-ready.

## Eventual build path

1. lock the approved source pack
2. generate a bounded draft against that source
3. preserve citations, table structure, and editorial edits
4. render the book through the approved formatter
5. package the publication manifest and release artifact
6. hand the result to Hub and the registry as a controlled publication unit

## Why it remains a horizon

Long-form output only matters if the approved source, edit trail, table fidelity, and publication package stay intact from draft to release.
Until that is true, this stays a horizon because the repo can describe the motion before it can prove the whole handoff.

## Flagship handoff gate

Promote this from horizon to active build only when all of the following are true:

* one canonical source pack can produce a cited draft without manual table reconstruction
* the draft can round-trip through review, formatting, and publication packaging without losing provenance
* `chummer6-hub` can approve the package and `chummer6-hub-registry` can publish the artifact as immutable release truth
* `chummer6-media-factory` can render the same content into the approved output set with no layout regressions
* the resulting output is good enough to stand as a flagship handoff, not just a prototype export
