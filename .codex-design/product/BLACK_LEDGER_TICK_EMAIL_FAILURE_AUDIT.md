# Chummer Updated Repo Reaudit — Black Ledger Tick-News Email + Flagship Status

Date: 2026-05-14
Verdict: **NOT FINISHED / NOT GLOBAL FLAGSHIP READY**

## Executive summary

The updated repositories now contain a real Black Ledger tick-news delivery implementation. This is a major improvement over the previous audit.

Newly found as implemented:

- `BlackLedgerTickNewsNotificationService`
- `BlackLedgerNewsRecipientResolver`
- `BlackLedgerWorldTickNewsEvent`
- `BlackLedgerNewsDeliveryReceipt`
- `BlackLedgerTickNewsNotificationBatchReceipt`
- `BlackLedgerTickNewsDispatchWorker`
- `CommunityStore.BlackLedgerNewsDeliveryReceipts`
- `/api/v1/ledger/worlds/{worldId}/tick-news/send`
- `/api/v1/ledger/worlds/{worldId}/ticks`
- `scripts/black_ledger_send_tick_news.py`
- `scripts/black_ledger_world_tick_e2e.py`

However, the reason you still did not get an email is clear:

> Codex implemented the code path, but it did not prove live delivery. The default policy is disabled unless config is set; delivery is disabled unless config is set; EA dispatch requires token/principal/binding; the catch-up script uses a hard-coded local token for remote calls; and Gmail shows no matching Black Ledger turn-news message.

The implementation is now **structurally present**, but **not operationally proven**.

## Current repo status

### What now exists

#### 1. Receipt persistence exists

`CommunityStore` now has:

```csharp
public List<BlackLedgerNewsDeliveryReceipt> BlackLedgerNewsDeliveryReceipts { get; } = new();
```

It is persisted into the snapshot and loaded back.

#### 2. Tick-news notification service exists

`BlackLedgerTickNewsNotificationService` now defines:

- `BlackLedgerWorldTickNewsEvent`
- `BlackLedgerNewsRecipientCandidate`
- `BlackLedgerNewsRecipientResolution`
- `BlackLedgerNewsDeliveryReceipt`
- `BlackLedgerTickNewsNotificationBatchReceipt`
- `BlackLedgerNewsRecipientResolver`
- `BlackLedgerTickNewsNotificationService`
- `BlackLedgerTickNewsDispatchWorker`

#### 3. Recipient resolver exists

Supported policies:

```text
disabled
subscribed_only
subscribed_or_only_user_preview_fallback
operator_only
```

This is the right shape.

#### 4. API endpoint exists

`LedgerController` exposes:

```text
POST /api/v1/ledger/worlds/{worldId}/tick-news/send
```

with parameters:

```text
turn
dryRun
policy
```

It requires internal automation auth via `FLEET_INTERNAL_API_TOKEN`.

#### 5. Catch-up script exists

`chummer6-hub/scripts/black_ledger_send_tick_news.py` exists and calls the send endpoint.

## Why no email arrived

### Cause 1 — Default policy is disabled

The resolver defaults to disabled unless `CHUMMER_BLACK_LEDGER_NEWS_EMAIL_POLICY` is configured.

Relevant logic:

```csharp
string policy = NormalizePolicy(policyOverride ?? _configuration[PolicyConfigKey]);
...
_ => DisabledPolicy
```

If config is missing, policy becomes `disabled`.

Required preview config:

```bash
CHUMMER_BLACK_LEDGER_NEWS_EMAIL_POLICY=subscribed_or_only_user_preview_fallback
```

### Cause 2 — Email send is disabled unless explicitly enabled

`NotificationsEnabled()` is:

```csharp
bool.TryParse(_configuration[EnabledConfigKey], out bool enabled) && enabled
```

If `CHUMMER_BLACK_LEDGER_NEWS_EMAIL_ENABLED` is missing, this returns false.

Required config:

```bash
CHUMMER_BLACK_LEDGER_NEWS_EMAIL_ENABLED=true
```

### Cause 3 — EA dispatch requires three separate config values

The service only sends if all three are present:

```text
CHUMMER_BLACK_LEDGER_NEWS_EA_API_TOKEN
CHUMMER_BLACK_LEDGER_NEWS_EA_PRINCIPAL_ID
CHUMMER_BLACK_LEDGER_NEWS_EA_BINDING_ID
```

If missing, receipts become:

```text
suppressed_delivery_unconfigured
```

### Cause 4 — Catch-up script is unsafe/incomplete for live remote send

The script always sends this header:

```python
headers={"Authorization": f"Bearer {LOCAL_INTERNAL_TOKEN}"}
```

where:

```python
LOCAL_INTERNAL_TOKEN = "black-ledger-local-token"
```

That is fine for the local temporary Hub it launches, because the script sets:

```python
os.environ["FLEET_INTERNAL_API_TOKEN"] = LOCAL_INTERNAL_TOKEN
```

But with:

```bash
--base-url https://chummer.run
```

it still sends the hard-coded local token. It does not read the real live token from `FLEET_INTERNAL_API_TOKEN`.

Therefore live catch-up likely fails with 401 unless production is incorrectly configured to use `black-ledger-local-token`.

### Cause 5 — Local script seeds a fake user

If the script is run without `--base-url`, it launches a temporary local Hub and seeds:

```text
preview-ledger-user@example.com
```

That will never send to your real account.

Therefore:

```bash
python3 scripts/black_ledger_send_tick_news.py --world emerald-sprawl-prelude --turn 1 --send
```

without live base URL and proper token does not prove your real delivery.

### Cause 6 — Worker only sends stored WorldTicks + PlayerSafeNews

The background worker joins:

```csharp
_store.PlayerSafeNews
join _store.WorldTicks
```

and only sends when a stored news/tick pair exists and no delivery receipt already exists.

A preseeded static world preview is not necessarily stored in `CommunityStore.WorldTicks` and `CommunityStore.PlayerSafeNews`.

So Turn 1 being visible in the seed/model does not automatically mean the background worker will send Turn 1 news.

### Cause 7 — EA payload shape may not match existing EA delivery contract

The tick-news service sends:

```csharp
new {
  tool_name = ConnectorDispatchTool,
  parameters = new {
    action_kind = DeliverySendAction,
    ...
  }
}
```

The participation notification service uses a different payload shape:

```csharp
new {
  tool_name = ConnectorDispatchTool,
  action_kind = DeliverySendAction,
  payload_json = new { ... }
}
```

Unless EA supports both shapes, tick-news may fail even with config present. The tick service also only extracts `target_ref`, whereas the participation service accepts `target_ref` or `output_json.delivery_id`.

This must be covered by integration tests.

### Cause 8 — Gmail shows no matching received mail

A Gmail search for recent Black Ledger / ledger / turn 1 / Emerald Sprawl / blnews messages returned no matching email.

That confirms no successful delivery was observed.

## Current implementation quality

| Requirement | Current status | Verdict |
|---|---:|---|
| Event model | exists | good |
| Notification service | exists | good |
| Recipient resolver | exists | good but needs tests |
| Only-user fallback | implemented by policy | good but disabled unless policy override/config |
| Delivery receipts | persisted | good |
| Catch-up script | exists | partial; live token bug |
| Live delivery proof | missing | blocker |
| Dry-run proof against live | missing | blocker |
| Gmail receipt | absent | blocker |
| EA contract proof | missing | blocker |
| Worker auto-send | partial; only stored tick/news pairs | blocker for seeded Turn 1 |
| Global flagship | still blocked | no |

## Flagship release verdict

Even with this progress, Chummer remains **not global flagship-ready** because:

- live root is still old account/proof-first page;
- `/feedback` still leaks provider/operator internals and env vars;
- feedback closeout is still pending/zero-state;
- `/status` still says review-required for desktop release;
- tick-news delivery is implemented but not operationally proven;
- Black Ledger remains preview/seeded;
- final janitor/release rehearsal proof is still missing.

## Correct current public posture

Allowed:

```text
Strong public preview / release candidate with Black Ledger seeded preview and route-proofed public surfaces.
```

Not allowed:

```text
Global flagship release.
Working Black Ledger email notifications.
Working feedback closeout.
Fully operational living-world loop.
```
