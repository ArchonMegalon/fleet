# Account-aware install and support linking

## Purpose

This file defines how Chummer downloads, desktop installs, and support cases become account-aware without turning every installer into a per-user binary.

The core rule is:

> Personalize the relationship, not the artifact.

## Canonical principle

Chummer ships canonical signed desktop artifacts per:

* desktop head
* platform
* arch
* channel
* version

It does not ship a unique `.exe`, `.dmg`, or archive per logged-in user.

## Three identities

### Person

The Hub account.

Hub owns:

* account identity
* permissions
* group/community membership
* notification policy
* support inbox and case history

### Install

One concrete desktop installation on one machine.

An install has:

* its own `installation_id`
* its own local keypair or equivalent local credential
* its own lifecycle
* its own revoke and support history

An install is not the same thing as a browser session.

### Entitlement and channel access

Whether that installation may read:

* open public stable channels
* preview or private channels
* guided-preview or otherwise gated release lanes

Registry remains the source of truth for channels and release heads.
Hub may broker account-aware grants, but it does not become the feed authority.

## Install access classes

Registry-owned install and update posture may classify a release target as:

* `open_public`
* `account_recommended`
* `account_required`

`open_public` keeps the guest path available.
`account_recommended` keeps the artifact canonical but makes claim and support continuity the preferred path.
`account_required` requires Hub-mediated install or update access without turning the artifact itself into a personalized binary.

## No personalized binary rule

Forbidden:

* embedding a specific logged-in user into the installer payload
* mutating a signed installer after signing so it becomes user-specific
* requiring login just to download a public stable installer

Allowed:

* minting a Hub-side download receipt
* minting a one-time install claim ticket alongside a normal signed download
* linking the installed copy to an account after download or on first launch

## Artifact immutability rule

Install media and machine update payloads stay immutable after signing or notarization for a release target.

Chummer must not:

* rewrite a signed `.exe`
* rewrite a signed `.dmg`
* append per-user identity data to release artifacts as the primary install model
* rely on one desktop artifact per user as the normal distribution path

If account context is needed, it must travel through a separate claim object or grant flow, not through mutated installer bytes.

## Hub-first download flow

1. `chummer.run` / Hub is the preferred public downloads front door.
2. Guests may download public stable/open installers without signing in.
3. Signed-in users may download the same canonical artifact plus a Hub-owned `DownloadReceipt`.
4. If the user is signed in, Hub may also mint a short-lived `InstallClaimTicket`.
5. First launch offers:
   * use as guest
   * link this copy to my account
6. Linking completes through a Hub-owned one-time deep link, browser handoff, or short code.

The installed artifact stays the same in both cases.

## Account-aware front-door rule

`/downloads` stays guest-readable while `/home` and `/account` remain signed-in shells.

The signed-in layer may explain participation and sponsor-session posture, but it must still rest on Hub community-ledger plus Registry-backed channel truth.

## Claim and grant lifecycle

### First launch

The desktop client creates:

* an `installation_id`
* a local installation credential such as a keypair
* initial local support and update posture settings

The user may continue as guest or claim the install immediately.

### Claim redemption

Claim redemption happens through Hub-owned account flow.

Successful redemption creates or updates the claimed-install record and returns an installation grant for later desktop auth.

### Guest-later claim

A guest install may be linked later from:

* a settings screen
* a Hub account page
* a browser-to-app handoff
* an online `Claim your copy` flow

Linking later must not require a reinstall.
Normal UI must not expose a manual activation ritual or ask the user to paste claim codes.
If a browser handoff fails, the fallback is a clear online claim link or support repair path, not a code-entry ceremony.

## Client auth rule

Desktop auth is installation-based after claim, not browser-session-based.

That means:

* a claimed install authenticates as a bound installation
* Hub issues short-lived installation grants
* public stable updates may remain anonymously readable
* gated channels may require Hub-brokered grants
* Registry still owns channel/feed truth

## Guest versus linked copy

### Guest copy

A guest copy may:

* install and run Chummer
* read open downloads and open update channels
* send pseudonymous support or crash reports tied to `installation_id`
* later become linked

### Linked copy

A linked copy may additionally:

* attach support cases to a Hub account
* receive fix-status updates for reported issues
* receive account-aware update/channel guidance
* receive follow-up surveys after fixes land

## Roaming workspace rule

Claiming an install may unlock roaming workspace restore, but restore follows typed scope rules rather than raw file sync.

### Person scope

May restore:

* profile and preferences
* pinned runners and recent campaigns
* personal rule-environment refs
* personal artifact-shelf refs

### Campaign or group scope

May restore:

* campaign roster and campaign rule environment
* shared dossiers, recaps, and artifact refs
* group-owned rights and allowances

### Install scope

Must stay local:

* caches
* logs and crash dumps
* rollback windows
* hardware tuning
* local secrets and key material
* device role posture such as `workstation`, `play_tablet`, `observer_screen`, or `preview_scout`
* device-specific channel posture

### Entitlement scope

Entitlements do not sync as install-local booleans.

Hub resolves:

* premium features
* preview-channel access
* GM or creator unlocks
* group-owned rights

Clients may cache short-lived capability grants for offline grace periods, but Hub truth remains authoritative.

### Restore trust rule

A claimed second device may restore dossiers, campaigns, rule-environment refs, artifact refs, and eligible features.

It must not:

* silently last-write-wins a dossier conflict
* compute against the wrong rule environment
* imply a feature is unlocked because of a stale local toggle
* sync secrets or diagnostics just because the install is claimed

The next-layer home-cockpit and device-role semantics are defined in `CAMPAIGN_WORKSPACE_AND_DEVICE_ROLES.md`.

## Support linkage rule

Support truth stays in Hub.

Each support case may link to:

* `user_id` when the install is claimed
* `installation_id`
* app version
* platform and arch
* channel
* desktop head
* runtime head or runtime-bundle head where applicable

Guests keep a low-friction path.
Claimed installs add closure and history.

Private diagnostics stay private by default.
Any public issue projection must strip account identifiers, dumps, sensitive local content, and any data that would surprise a reasonable user if exposed publicly.

Hub stores the canonical `SupportCase` and its `CaseStatusEvent` history.
Fleet may receive normalized work items such as crash clusters or repro tasks, but Fleet work is downstream of the Hub case rather than a replacement for it.

### Case status rule

Minimum first-wave statuses are:

* `received`
* `matched_known_issue`
* `needs_info`
* `accepted`
* `not_planned`
* `fixed_pending_channel`
* `fixed_available`
* `closed`

Feedback and idea cases may use only the statuses that make sense for that case type.
For feedback, `accepted` means the idea is intentionally kept alive or planned; it does not mean the outcome already shipped.

### Known-issue linkage rule

If a new report matches a known issue, Hub should attach it to that issue and tell the user they are now linked to an existing case instead of pretending a new investigation started.

## Release-notice rule

Do not treat "PR merged" as "fixed for the user."

The user-visible fix moment is when the repair is promoted to the reporter's actual channel according to Registry truth.

### Meaningful updates only

Hub should notify on user-meaningful transitions, not every internal automation event.

Good candidates are:

* we matched your report to a known issue
* we need one more detail
* this suggestion is accepted
* this suggestion is not planned
* this fix is now available on your channel

### Progress email workflow

Reporter-facing progress mail follows `FEEDBACK_PROGRESS_EMAIL_WORKFLOW.yaml`.

The first-wave sender identity is:

* `Wageslave <wageslave@chummer.run>`
* reply-to `support@chummer.run`

The minimum staged messages are:

* request received
* audited decision with reason, implementation posture, ETA text, and the explicit `Clad Feedbacker` or `Denied` award
* fix available on your channel, with a real download or updater route and a direct request to test the release

These notices may queue through EA and Emailit, but they still count as support truth only when Hub case state and Registry release truth agree.

### Channel-aware fix notices

When a fix is merged but not yet promoted to the reporter's channel, the case may move to `fixed_pending_channel`.
Only after Registry truth shows availability on the user's pinned or eligible channel may Hub send a `ResolutionNotice` that says the issue is fixed for them.

Status email or in-product notice may say:

* fixed in version `X.Y.Z`
* available on `Stable`, `Preview`, or another concrete channel
* update now

### Rejection honesty

If feedback is declined, the user may be told so with a bounded reason such as out of scope, duplicate, conflict with product direction, or too costly for the current phase.

Do not silently close high-signal feedback when a respectful explanation would build more trust.

## External survey/tooling rule

Survey or support tools may assist only behind Hub-owned adapters.

They must not become:

* the canonical support-case database
* the canonical install-linking database
* the canonical release/update truth

MetaSurvey-style tooling is allowed as a survey bridge after Hub decides when to invite.
No browser or desktop client may embed third-party support or survey credentials directly.

First-wave survey posture should stay:

* preference-respecting
* delayed until the outcome is actually meaningful
* bounded in length
* never the only way to see case status

## Contract placement rule

Registry-owned release/install/update DTOs stay in `Chummer.Hub.Registry.Contracts`.

The registry-owned family includes:

* `DownloadReceipt`
* `InstallAccessClass`
* `InstallClaimTicket`
* `ClaimedInstallation`
* `InstallationGrant`
* install-to-release compatibility projections
* promoted release-head records
* update-feed and rollout posture

Support and control-loop DTOs belong in `Chummer.Control.Contracts`.

The control-owned family includes:

* `CrashEnvelope`
* `BugReport`
* `FeedbackSubmission`
* `SupportCase`
* `CaseStatusEvent`
* `ResolutionNotice`
* `SurveyInvite`

Generic orchestration or delivery notifications that are not support truth remain in `Chummer.Run.Contracts`.

No repo may invent a second cross-repo vocabulary for install claim state, installation grants, support-case statuses, or user-visible resolution notifications.
