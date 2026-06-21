# ADR-0014: Interop and portability are first-class product promises

Date: 2026-03-25

Status: accepted

## Context

Chummer already had active import/export and round-trip implementation seams, but the product canon still treated interoperability as implied compatibility work instead of a named promise.

That created two kinds of drift:

* users could feel import/export behavior without a canonical portability model
* code could keep moving without one clear statement of which package families own portability meaning

## Decision

Chummer now canonizes interop and portability as first-class product truth.

The canonical source is:

* `INTEROP_AND_PORTABILITY_MODEL.md`

The active owner-package split is:

* `Chummer.Campaign.Contracts` for long-lived dossier and campaign meaning
* `Chummer.Play.Contracts.Interop` for portable round-trip package contracts
* `Chummer.Hub.Registry.Contracts` for immutable artifact, install, and release metadata that portable packages may reference

## Consequences

### Positive

* portability becomes part of the product promise instead of compatibility folklore
* import/export, migration, and publication can share one vocabulary
* support and trust surfaces can explain portability outcomes with explicit provenance and version context

### Negative

* more canon now needs to stay aligned with active import/export code
* portability claims must remain conservative until every downstream surface consumes the same package families cleanly

## Explicit rejection

The following are rejected:

* treating portable package semantics as an implementation detail hidden inside one repo
* letting publication packets redefine dossier or campaign meaning
* silent legacy-file reinterpretation without explicit migration receipts
