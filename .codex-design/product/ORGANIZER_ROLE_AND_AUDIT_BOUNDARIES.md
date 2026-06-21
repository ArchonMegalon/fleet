# Organizer role and audit boundaries

## Product promise

Organizer, league, convention, and season operations must feel like one governed
lane without collapsing GM, support, publication, and operator authority into one
catch-all admin role.

Community-scale operations must stay auditable, support-safe, and bounded enough
that a serious organizer can run a season without falling back to private
spreadsheets or undocumented operator favors.

## Truth order

1. Hub-owned community state is the source of truth for group membership, roster
   posture, event lifecycle, role grants, and organizer decisions.
2. Campaign truth remains narrower than community operations truth. Community
   actions may prepare or route a campaign, but they do not silently overwrite GM
   run truth, runner state, or campaign continuity.
3. Registry receipts own discoverability, publication status, audience labels,
   retention posture, and artifact availability once a community-facing artifact
   leaves draft state.
4. Support-case truth remains in the Hub/Fleet support lane. Organizer actions
   may request escalation, attach evidence, or freeze publication, but they do not
   close support cases or rewrite incident outcomes.
5. EA and Fleet operator packets are projections from governed state. They may
   summarize, prioritize, and follow through, but they do not become canonical
   role, roster, event, moderation, or support truth.
6. External calendar, meeting, chat, and spreadsheet tools may project or mirror
   event data, but they do not own roster acceptance, organizer authority, consent posture, publication status, or audit receipts.

## Role lanes

### Organizer

The organizer owns community structure and bounded operational decisions:

* create and govern a group, league, convention lane, or season shell
* grant organizer-scoped community roles
* publish or unpublish organizer-facing artifacts through receipt-backed lanes
* define event visibility, event policy, and season posture
* request support escalation and attach evidence packets

The organizer does not:

* rewrite GM-owned live run decisions
* close support cases
* bypass moderation, retention, or publication receipts
* mint world truth without the separate world or season authorities that the
  affected surface requires

### Game Master

The GM owns one run's live table truth, resolution posture, roster fit decisions,
and session-close consequences. Organizer policy may shape the surrounding event,
but it may not silently seize GM run truth.

### Community steward or moderator

This role handles membership review, code-of-conduct actions, and bounded artifact
or channel moderation inside an organizer-owned community context. It may apply
temporary safety actions, but it may not claim support closure, release truth, or
campaign-owner authority.

### Season operator

This role owns season cadence, scoring windows, standings publication, and
cross-event policy within one organizer-approved season. It may adjust season
metadata and publication timing, but it may not rewrite campaign continuity,
support outcomes, or artifact receipts.

### World operator

This role remains adjacent to community operations. It may seed world packets or
shared-city pressure, but those packets are proposals until a GM or organizer
adopts them through a governed path.

### Support and product-governor roles

Support owns support-case state, reporter communication, and final support
closure. Fleet and EA own packet compilation, governor followthrough, and freeze
or reroute proposals. None of those roles silently become organizer truth.

## Community-scale operation families

Every shipped organizer-facing action must fit one of these operation families:

| Operation family | Primary writer | Required receipt or packet | Hard boundary |
| --- | --- | --- | --- |
| Group and membership policy | Organizer | role grant receipt | no hidden membership or role flips |
| Event creation and scheduling | Organizer | event lifecycle receipt | calendar mirrors do not own event truth |
| Run staffing and roster fit | GM with organizer policy context | roster decision receipt | organizer policy does not replace GM acceptance reasons |
| Publication and artifact release | Organizer plus registry | publication receipt | audience, retention, and locale truth stay visible |
| Safety and moderation action | community steward or organizer | moderation case packet | temporary action is not final support closure |
| Support escalation | organizer or GM | escalation packet linked to support case | organizer cannot self-close the case |
| Season standings and honors | season operator | season decision receipt | scoring must derive from typed source events |

## Required audit packet

Every community-scale operation above must emit one `CommunityScaleAuditPacket`
before downstream projections may treat the action as trustworthy.

The packet must include:

* stable packet id and event timestamp
* community context refs for group, event, season, and campaign links when present
* actor identity ref plus actor role at the time of action
* operation family and action verb
* before and after posture summary for the governed change
* evidence refs, moderator notes, and publication or safety labels when relevant
* support-case ref when the action escalates into support
* audience, retention, and locale posture when the action publishes an artifact or
  notice
* projection recipients so Fleet, EA, Registry, or external mirrors can prove that
  they consumed a receipt instead of inventing state

See `COMMUNITY_SCALE_AUDIT_PACKET_SCHEMA.yaml` for the machine-readable contract.

## Publication and escalation boundaries

Organizer publication claims must route through registry-backed publication truth.
If a community artifact lacks a receipt-backed audience label, retention posture,
or availability state, the product must say publication is unknown or blocked.

Support escalation claims must route through the support lane. Organizer-visible
surfaces may show `requested`, `triaged`, `waiting_for_reporter`, `fix_in_progress`,
or `resolved_for_organizer`, but final support closure stays owned by the support
case state machine.

## Operator packet boundaries

Fleet and EA may compile organizer health, event prep, publication readiness, and
support risk packets from `CommunityScaleAuditPacket`, campaign state, support
case state, and publication receipts.

Those packets must remain projections:

* they may recommend freeze, reroute, escalation, or followthrough
* they may not create organizer roles, change accepted rosters, or mark artifacts
  published without the canonical upstream receipt
* they must preserve links back to the source packet ids they summarize

## Forbidden modes

The product must fail closed rather than allow any of the following:

* treating Discord, Teams, spreadsheets, or calendar invites as canonical role,
  roster, or event truth
* letting organizers close support cases or redact support evidence outside the
  support lane
* letting season standings or honors publish from hidden score math without typed
  source events
* letting EA or Fleet projections overwrite organizer, GM, moderation, or registry
  truth
* letting community moderation posture masquerade as release-health, campaign-fit,
  or creator-trust truth
