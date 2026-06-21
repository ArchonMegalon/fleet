# M0 - Repo and contract reset

## Goal

Recreate the repo as a real package and design boundary.
The output of M0 is **not** end-user media value.
The output is a real repo, a real contract package, and a clean seam that later milestones can build on.

## Included

* create `chummer6-media-factory`
* create `Chummer.Media.Contracts`
* define repo-local design docs
* create contract fixtures and verification harness
* move media-specific DTOs out of `run-services`
* split mixed media/delivery/orchestration contracts by ownership
* define initial internal API routes
* establish package publishing strategy

## Excluded

* provider adapters
* real renderer execution
* production storage backends
* UI work
* campaign/business-policy logic

## Detailed design

### 1. Repo shape

Recommended initial projects:

* `Chummer.Media.Contracts`
* `Chummer.Media.Factory`
* `Chummer.Media.Factory.Api`
* `Chummer.Media.Factory.Verify`
* `Chummer.Media.Factory.Tests`

The API may be extremely thin at M0.
The important part is that code lands in the correct homes from day one.

### 2. Contract extraction plan

Start by inventorying current public media DTOs in `run-services`.
Split them into three buckets:

1. **pure execution DTOs** -> move to `Chummer.Media.Contracts`
2. **upstream orchestration/composition DTOs** -> stay in `Chummer.Run.Contracts.Media`
3. **delivery/approval/public projection DTOs** -> stay in `run-services`, outside media execution packages if needed

The extraction should be semantic, not mechanical.
Do not preserve bad coupling just because a file already exists.

### 3. Initial contract families

M0 must land these minimum families:

* assets
* jobs
* lifecycle
* templates
* document render model/result
* portrait render model/result
* video render model/result
* failure/result envelopes

Each family needs:

* namespace
* versioning note
* fixture examples
* comments describing owning repo

### 4. Verification harness

`Chummer.Media.Factory.Verify` should assert:

* package builds with no network access
* no project reference points to play/presentation/UI packages
* no contract type leaks provider SDK types
* sample fixtures deserialize/serialize round-trip
* package public API matches approved baseline

### 5. API seed

Define but do not fully implement:

* job submission
* job status
* job cancel
* asset lookup
* asset pin
* provider health

The routes can return stub receipts backed by in-memory stores initially.

## Exit tests

* `Chummer.Media.Contracts` builds in isolation
* `run-services` compiles against the new package or a transition shim
* no source-copied media execution DTOs remain outside the package
* no `Chummer.Media.Contracts` type references play or UI packages
* fixture verification passes in CI
* repo-local design docs exist and match the split intent

## Failure conditions

M0 is not done if:

* media DTOs still exist as duplicated source trees elsewhere
* the package is real in name only but not consumed
* the repo contains renderer code before the package plane is stable
