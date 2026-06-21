# ORIGIN DOSSIER

## Deep dive

[Watch Origin Dossier: The Name She Chose](https://chummer.run/media/horizons/origin-dossier-the-name-she-chose-20260619.mp4).

## The problem

A runner can be legal and still feel unfinished.

Players often start with attributes, skills, gear, and a strong visual idea, but the character still has no grounded reason to exist in the campaign. The GM may have constraints too: a clinic favor, a restricted piece of ware, an addiction hook, a magical requirement, a faction debt, or a table-specific starting premise.

That context matters. It should not vanish into chat history, and it should not secretly rewrite the character sheet.

## What it would do

Origin Dossier turns a blank-state concept or active runner into approved origin canon and a bounded media bundle.

It helps the table answer:

* who this runner was before the first job
* why this build makes sense in the campaign
* what the GM allowed or required as story context
* what the player approved as canon
* which parts can later guide ALICE follow-up
* which parts are only media, flavor, or presentation

The point is not to make a prettier export. The point is to give the runner a durable identity that can travel through build help, campaign play, recap, and presentation without becoming a second rules engine.

## What is live now

The desktop ALICE workbench already exposes `Origin Dossier` as a named mode beside `Build help` and `Rules coach`.

The shipped slice can:

* draft an origin from a blank-state or active-runner context
* accept GM steer, allowances, and hard requirements as advisory context
* freeze approved origin canon after review
* create a bundle root for the dossier
* run player-facing story text through a Chummer-controlled humanizer loop before preview or media packet creation
* branch into a dossier PDF, portrait candidates, scene candidates, default narration, alternate narration, optional audiobook request, video storyboard, vidBoard packet, and local media-factory request
* hand an approved origin-story audiobook request to EA's governed audiobook lane when the player asks for it
* open the finished audiobook through a player- and runner-scoped EA reference instead of broad Audiobookshelf access
* let later ALICE suggestions read the approved origin canon

That makes Origin Dossier more than a subfeature of ALICE. ALICE is the coach and rules-facing conversation surface. Origin Dossier is the runner identity, approval, and media-packet lane that ALICE can reference after the player or GM approves it.

## What it feels like

A player starts with:

> Build me an SR4 troll decker from scratch.

ALICE helps shape the build, but the player wants the runner to feel real. The GM adds:

> A clinic contact quietly fronted restricted starter ware and one over-availability deck part. The runner also needs an illegal-drug addiction hook, a magical-active requirement, and Logic or Intuition at 2 or higher.

Origin Dossier turns that into a draft story:

* the clinic favor becomes a debt and contact pressure
* the restricted part becomes a table-approved exception to explain, not a silent entitlement
* the addiction hook becomes a story risk that still needs normal sheet handling
* the magical-active requirement becomes campaign premise, not hidden rules mutation
* the mental-attribute minimum stays visible as a GM requirement

The player reviews it. The GM signs off. The canon is approved.

Later, when the player asks ALICE what to add next, ALICE can remember the clinic debt and the decker identity while still using Chummer-owned mechanics truth for legality, cost, availability, ware, qualities, and attributes.

Before the story is shown as polished dossier text, Chummer may humanize the draft for rhythm, repetition, and visible assistant tells.
That pass is editorial only.
If it changes facts, permissions, mechanics, or scope, it is rejected.

## The bundle

An Origin Dossier bundle can include:

* approved origin canon in markdown and JSON
* humanized player-facing story text with source hash
* dossier PDF
* portrait candidate set and selected portrait
* scene candidate set and selected scene
* default narration packet
* alternate narration packet
* optional approved-story audiobook in Audiobookshelf, exposed to Chummer through a player-scoped EA reference
* video storyboard
* vidBoard packet
* media-factory render request
* receipts for source, approval, selected assets, and render state

The media is downstream. It can make the character easier to understand, pitch, and remember, but it does not own the character.

If the player asks for it, the approved origin story can also become an audiobook through EA's governed audiobook lane. EA chooses the best configured narration voice from the story profile, renders the approved text, imports the M4B into Audiobookshelf storage, and gives Chummer only a scoped reference for that player and runner.

That reference is not a global Audiobookshelf login, admin token, raw pCloud path, or access to another player's library.

## Relationship to ALICE

ALICE helps with build questions, rules coaching, and follow-up.

Origin Dossier gives ALICE approved identity context.

That distinction matters:

* ALICE may say why an approved origin makes a future upgrade feel coherent.
* ALICE may point out that the clinic favor creates story debt.
* ALICE may explain that a GM allowance still needs normal sheet edits before mechanics change.
* ALICE may open the player's scoped origin-story audiobook when the approved dossier has one.
* ALICE must not treat dossier prose as permission to auto-apply ware, nuyen, qualities, addiction, magic, or availability exceptions.

Origin canon can guide suggestions. It cannot overrule the engine.

## What it does not do

Origin Dossier does not:

* silently rewrite the character sheet
* turn GM narrative steer into automatic mechanics
* treat a portrait, scene, narration, or video as character authority
* invent legal exceptions without GM/player approval
* let media providers become source of truth
* publish private character context without review
* blur player-safe material with GM-only constraints
* expose a global Audiobookshelf library, vendor token, or raw media path to the desktop client

## Before it grows

Before this lane widens, Chummer needs durable confidence that:

* approved origin canon and bundle lineage are stable
* GM steer stays advisory until normal mechanics edits happen
* selected portraits, scenes, narration, and videos carry provenance
* humanized prose remains source-bound and does not change facts
* origin-story audiobooks carry the same approval lineage and scoped-access receipt as the rest of the bundle
* media outputs can be rejected without harming the runner dossier
* later ALICE follow-up can use origin context without confusing story truth and rules truth
* private and GM-only context stays scoped

## Why it remains bounded

The first playable slice is live, but the full horizon is larger.

The flagship version should make a runner feel like a person with history, pressure, obligations, and presentation-ready artifacts while still preserving the table’s authority. That requires careful approval, media retention, export, deletion, and media-lineage work.

Origin Dossier is ready to be named as a Chummer horizon because it has a real desktop foothold and a clear product boundary. It should stay bounded until the dossier-media loop proves it can be beautiful without becoming fake truth.
