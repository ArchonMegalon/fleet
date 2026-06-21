# Campaign Adoption Start from Today Flow

## Purpose

This file defines the public and in-product posture for existing tables that do not want to reconstruct historical campaign state before Chummer becomes useful.

## Product rule

Chummer should let a table start from current truth.
Unknown history may be marked explicitly and cleaned up later.

## Core flow

```text
enter or import current runners
-> mark unknown or partial history
-> bind current rule environment
-> record current debts, favors, contacts, and active jobs
-> receive adoption confidence
-> start the ledger from today
```

## Required outputs

* migration or adoption confidence
* safe-to-play posture
* unresolved review items
* explicit unknown-history markers
* next best cleanup actions
* adoption receipt and replay-safe start anchor

## Public promise

The public adoption promise should be:

* start from today
* keep what you already know
* mark what you do not know
* let future receipts become clean
