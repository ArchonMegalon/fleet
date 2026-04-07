# KARMA FORGE

## The problem

Groups want house rules and alternate rule environments without forking themselves into incompatible chaos.
The real table pain is not "more customization"; it is keeping a house rule understandable, reviewable, portable, and reversible once multiple tables start relying on it.

## What it would do

Chummer would let groups publish, review, and reuse bounded house-rule sets with visible impact and compatibility checks, without turning them into private forks or ad hoc local patches.
The bounded product move is curated ruleset packs with explicit compatibility metadata, not free-form scripting, full tabletop automation, or silent live mutation of a table's rules.

## Likely owners

* `chummer6-core`
* `chummer6-hub-registry`
* `chummer6-ui`

## Owning repos

This horizon is only plausible when the core engine, registry, and workbench keep the authority split clear:

* `chummer6-core` owns ruleset ABI discipline and engine-side validation
* `chummer6-hub-registry` owns package identity, publication, compatibility, and rollback truth
* `chummer6-ui` owns authoring, review, impact preview, and operator-facing approval flows

No Fleet-owned execution behavior should become the source of rules truth.

## Tool posture

External tools may assist authoring or review, but they remain assistants only.
Rule authority stays inside engine packages, registry compatibility metadata, and explicit approval paths; LTD/tool posture is support, not policy ownership, and nothing in the loop should silently override the canonical package and approval chain.

## What has to be true first

* ruleset ABI discipline
* clear package ownership
* registry compatibility metadata
* approval and publication flows
* rollback and version pinning that make table changes explainable
* visible impact review before a ruleset is promoted or reused

## Current state

This is still a horizon because the dependencies are not yet tight enough to trust as a flagship table safety surface.
Rule changes can fracture tables quickly if compatibility, rollback, and package boundaries are not already dependable across repos.

## Eventual build path

The likely path is engine-first validation, registry-backed publication and compatibility metadata, and UI surfaces that make impact review and approval legible before any table adopts the ruleset.
Only after that can the product safely add reuse, variant tracking, and controlled promotion across groups without turning every house rule into a private fork.

## Why it remains a horizon

This remains a horizon because the product promise depends on cross-repo discipline that is not yet fully dependable.
Until ABI rules, package ownership, registry metadata, approvals, and rollback all behave as a single trustworthy path, the feature is still a future lane rather than a live flagship commitment.

## Flagship handoff gate

This should not leave horizon status until all of the following are true on a representative ruleset:

* it can be authored in `chummer6-ui`
* it can be published through `chummer6-hub-registry`
* it preserves engine validation in `chummer6-core`
* it exposes compatibility and impact review before publication
* it can be version-pinned and rolled back without breaking an existing table
* the approval path is explicit enough that a reviewer can explain why the ruleset is safe to adopt
