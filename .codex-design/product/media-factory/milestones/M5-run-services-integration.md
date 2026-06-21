# M5 - Run-services integration and cutover

## Goal

Make the split real in live topology.
After M5, `run-services` should orchestrate media but not render it.

## Included

* internal media API
* submission/status/cancel endpoints
* polling integration
* optional callback design
* internal media client or service bridge
* cutover of document jobs
* cutover of portrait jobs
* cutover of video jobs
* dead-code removal plan in `run-services`

## Excluded

* direct client integration with media-factory
* UI changes beyond consuming upstream result projections
* unrelated run-services refactors

## Detailed design

### 1. Client isolation

`play` and `presentation` keep receiving asset projections from `run-services`.
They must not know whether the artifact came from local render logic or media-factory.
That insulation is part of the success condition.

### 2. Submission semantics

`run-services` should submit render jobs using one internal client abstraction.
Do not scatter raw HTTP calls through feature code.
Centralize:

* auth/signing
* idempotency key generation
* correlation id propagation
* retry policy

### 3. Cutover order

Cut over in this order:

1. documents
2. portraits
3. videos

This order lets you learn from the cheaper domains before moving expensive workloads.

### 4. Rollback

A rollback plan must exist.
It should be possible to:

* stop sending new jobs to media-factory
* continue serving existing asset manifests
* preserve lineage and history
* disable only the affected job kind if necessary

## Exit tests

* run-services submits and tracks media jobs via one client abstraction
* duplicate submissions are idempotent
* cutover feature flags work by job kind
* client repos still consume only upstream projections
* no direct renderer execution remains for cut-over domains in run-services
