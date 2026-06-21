# Part 05 - Asset lifecycle and storage

## 1. Purpose

Media systems become operational liabilities when lifecycle is informal.
This part defines how assets live, age, get pinned, get superseded, and disappear safely.

## 2. Artifact lifecycle states

Every asset should be describable in terms of:

* approval state
* retention state
* pin state
* supersession state
* expiry timestamp

These dimensions are related, but they are not the same thing.

Example:
a portrait may be `approval = approved`, `retention = ttl`, `pin = pinned`, `supersession = current`.

## 3. Approval

Approval is persisted metadata, not a UI convention.

Suggested states:

* `Draft`
* `ApprovalPending`
* `Approved`
* `Rejected`
* `Revoked`

Media-factory stores the state because lifecycle depends on it, but it does not decide who is allowed to approve or why.

## 4. Retention

Suggested retention states:

* `ApprovalPending`
* `Ttl`
* `Pinned`
* `Archived`
* `ColdStorage`
* `Expired`
* `Deleted`

Rules:

* `Deleted` means metadata may remain with a tombstone
* `Expired` means the asset is eligible for cleanup
* `Pinned` overrides normal TTL sweep
* `ColdStorage` implies retrieval latency but preserved lineage

## 5. Supersession

Supersession is common for:

* rerolled portraits
* revised PDFs
* improved previews
* regenerated videos after correction

Supersession must not erase history.
Required fields:

* `SupersededAssetId`
* `ReplacementAssetId`
* `Reason`
* `SupersededAtUtc`
* `Actor`

## 6. Storage policy

Production design:

* active object storage for hot assets
* metadata database for manifests and state
* optional cold archive for long-lived retained artifacts
* signed URLs for binary access
* no blob serving from the main app host

## 7. Cleanup and janitoring

The janitor must be deterministic and safe.

Sweep order:

1. find expired, unpinned assets
2. verify not referenced as canonical/current
3. delete previews before parents only if safe
4. remove hot binary
5. update manifest/tombstone state
6. enqueue cold-archive cleanup if applicable

## 8. Reference safety

Before hard cleanup, the janitor should verify the asset is not referenced by:

* canonical portrait selection
* current packet attachment record
* current preview handle for a still-live asset
* legal hold or moderation hold flag
* active restore job

## 9. Signed access

Signed asset URLs should:

* be short-lived
* encode asset id and role
* be revocable by state change when feasible
* avoid exposing raw provider URLs

## 10. Tests

Lifecycle/storage tests must prove:

* unpinned TTL assets are cleaned
* pinned assets survive cleanup
* superseded assets remain queryable as history
* canonical assets are not deleted accidentally
* restore from cold storage preserves manifest identity
* signed URLs expire and cannot be replayed beyond policy
