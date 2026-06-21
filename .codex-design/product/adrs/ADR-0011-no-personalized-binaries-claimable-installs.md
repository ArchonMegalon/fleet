# ADR-0011: No personalized binaries; claimable installs instead

## Status

Accepted.

## Context

Chummer needs:

* account-aware downloads
* account-aware support closure
* installation-level auth for private channels and support linkage

It does not need:

* a unique signed installer per user
* post-sign mutation of installers to embed account identity
* browser-session auth as the long-lived desktop credential model

The product split already places:

* public downloads and account UX in Hub
* release/install/update truth in Hub Registry
* updater behavior and local install state in UI

The product also needs:

* guest-readable public channels
* optional account-aware install claim
* installation-level auth for gated channels
* support notices that track the reporter's actual channel, not just source control events

## Decision

Chummer will use claimable installs, not personalized binaries.

The canonical rule is:

> personalize the relationship, not the artifact

That means:

* public stable downloads may remain guest-readable
* signed-in downloads may mint a Hub-owned `DownloadReceipt`
* signed-in downloads may also mint a short-lived `InstallClaimTicket`
* first launch may create installation identity material and link the installed copy to the user's Hub account
* a user may run as guest first and claim the copy later without reinstalling
* the shipped installer remains the canonical signed artifact for its `head × platform × arch × channel × version`
* Hub owns the person/install/support relationship while Registry keeps release, channel, install-access, and update truth
* Fleet may automate triage and patch preparation downstream of Hub cases, but it does not become canonical support truth

## Consequences

### Positive

* signed artifacts stay stable and verifiable
* release artifacts stay cacheable, mirrorable, and auditable
* guest installs remain low-friction
* support cases can become account-aware without forcing login on download
* private or gated channels can use installation-level grants
* the same installed copy can be claimed later without artifact mutation

### Negative

* install claim and installation-grant flows need explicit DTOs and UX
* desktop clients need local installation identity material
* Hub must carry more lifecycle state than a pure browser-session surface
* Hub and Registry must coordinate when channel-aware fix notices become meaningful to a reporter

## Explicit rejection

The following are rejected by this ADR:

* one binary per user
* post-sign mutation that changes the delivered signed artifact
* treating a merged fix as the same thing as a fix available on the user's channel
* making claimable installs an excuse to bypass Registry-owned channel or update truth

## Follow-on design implications

The canonical design doc for this decision is:

* `products/chummer/ACCOUNT_AWARE_INSTALL_AND_SUPPORT_LINKING.md`

Expected contract-family split:

* install and claim DTOs in `Chummer.Hub.Registry.Contracts`
* support and control-loop DTOs in `Chummer.Control.Contracts`
