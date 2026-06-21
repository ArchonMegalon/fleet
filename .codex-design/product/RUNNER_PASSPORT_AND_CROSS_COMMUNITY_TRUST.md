# Runner Passport and Cross-Community Trust

## Purpose

This file defines the smallest portable trust object that lets a runner move between tables and communities without restarting the entire approval story.

## Product rule

A `RunnerPassport` is not the runner dossier itself.
It is the portable proof of what a community needs to know before it can trust the dossier quickly.

## Why this matters

Communities do not merely care whether a runner exists.
They care whether the runner is:

* legal under a named rule environment
* reviewed or approved under a named community posture
* carrying unresolved conflicts or warnings
* suitable for a specific open run or season

Without a passport, every community migration becomes Discord archaeology.

## Required fields

A first passport should expose:

* runner identity ref
* active ruleset and rule-environment fingerprint
* approval state
* review timestamp and reviewer role
* known conflicts or unresolved warnings
* quickstart or full-dossier posture
* export or play-surface eligibility
* bounded validity window

## Product use

The passport should feed:

* open-run application preflight
* community rule environments
* no-desktop participation paths
* start-from-today adoption
* creator or organizer review lanes

## Boundary rule

The passport is not a permanent social score.
It is a scoped trust and compatibility proof for a governed table or community lane.
