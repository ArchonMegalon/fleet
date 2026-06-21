# Ready for Tonight Mode

## Purpose

This file defines the smallest cross-surface operating mode that should make Chummer feel immediately useful before users understand the wider campaign OS.

## Product rule

`ReadyForTonight` is not a dashboard.
It is a verdict and action surface.

It should answer, for the current user and current table:

* am I ready
* if not, what blocks me
* what can I fix right now
* what changed since the last session
* what should I open next

## Why this matters

The product already models many powerful lanes.
Users will still judge the product by whether it reduces anxiety before tonight's session.

The first emotional win is not:

* "the architecture is complete"
* "the campaign state is rich"
* "the world simulation is promising"

It is:

* "I know what I need to do before the game starts."

## Three views

### 1. Player readiness

The player view should answer:

* is my runner legal under this table's rule environment
* am I injured, broke, over capacity, or missing something important
* what gear, ammo, spells, programs, and temporary states matter tonight
* what changed because of the last run
* where do I join the table
* `Make me ready for this run`

### 2. GM readiness

The GM view should answer:

* is the table roster complete
* which runners are blocked or need review
* what prep packet, opposition packet, handouts, and exports are still missing
* which rules disputes, rewards, injuries, debts, favors, or consequences remain unresolved
* what closes tonight cleanly

### 3. Organizer or public-run readiness

The organizer view should answer:

* is the run publishable
* are safety, consent, and application gates satisfied
* is the meeting handoff configured
* are quickstart or beginner participation paths available
* what support or moderation risk still blocks publication

## Output contract

Every `ReadyForTonight` verdict should emit:

* `status`: `ready`, `warning`, or `blocked`
* `blocking_reasons`
* `fix_now_actions`
* `changed_since_last_session`
* `next_best_screen`
* `proof_receipts`

## Golden journeys

### Player

`open ready verdict -> resolve one blocker -> join run -> play -> receive recap`

### GM

`open ready verdict -> finish one missing prep item -> export run pack -> run -> close ResolutionReport`

### Organizer

`open ready verdict -> resolve one policy gap -> publish run -> monitor application preflight -> approve roster`

## Non-goals

* not a replacement for the full workbench
* not a social feed
* not a lore screen
* not a world map substitute

It exists to make the next useful action obvious.
