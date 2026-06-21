# Developer Change Guide — Finish Black Ledger Tick-News Email

## Goal

Make sure the generated Black Ledger news for Turn 0 → Turn 1 actually sends an email to the only eligible user, or produces a clear suppressed receipt explaining why it did not.

## Required end state

A successful run produces either:

```yaml
status: sent
world_id: emerald-sprawl-prelude
from_turn: 0
to_turn: 1
recipient_count: 1
delivery_ref: ...
```

or a clear suppression:

```yaml
status: suppressed_delivery_unconfigured
failure_reason: ea_dispatch_unconfigured
```

Silent no-op is not acceptable.

---

## P0-001 — Fix live catch-up script token handling

### Problem

`black_ledger_send_tick_news.py` always sends:

```python
Bearer black-ledger-local-token
```

This only works for the local temporary Hub. It does not work for live unless live has the same unsafe token.

### Fix

Add token resolution:

```python
def resolve_internal_token(base_url: str) -> str:
    if base_url:
        token = os.environ.get("FLEET_INTERNAL_API_TOKEN") or os.environ.get("CHUMMER_BLACK_LEDGER_INTERNAL_API_TOKEN")
        if not token:
            raise RuntimeError("FLEET_INTERNAL_API_TOKEN is required when --base-url is used")
        return token
    return LOCAL_INTERNAL_TOKEN
```

Then use that token in `invoke`.

### Acceptance criteria

- local run still works with local token;
- live run requires real token;
- script fails loudly if `--base-url` is set and token missing;
- script never silently uses local token against production.

### Verification

```bash
FLEET_INTERNAL_API_TOKEN=wrong python3 scripts/black_ledger_send_tick_news.py --base-url https://chummer.run --world emerald-sprawl-prelude --turn 1 --dry-run
# must fail auth, not silently pass

FLEET_INTERNAL_API_TOKEN=$REAL_TOKEN python3 scripts/black_ledger_send_tick_news.py --base-url https://chummer.run --world emerald-sprawl-prelude --turn 1 --dry-run
```

---

## P0-002 — Set and verify required runtime config

### Required live config

```bash
CHUMMER_BLACK_LEDGER_NEWS_EMAIL_ENABLED=true
CHUMMER_BLACK_LEDGER_NEWS_EMAIL_POLICY=subscribed_or_only_user_preview_fallback
CHUMMER_BLACK_LEDGER_NEWS_EA_API_TOKEN=...
CHUMMER_BLACK_LEDGER_NEWS_EA_PRINCIPAL_ID=...
CHUMMER_BLACK_LEDGER_NEWS_EA_BINDING_ID=...
CHUMMER_BLACK_LEDGER_NEWS_EA_BASE_URL=...
CHUMMER_BLACK_LEDGER_NEWS_HASH_SALT=...
FLEET_INTERNAL_API_TOKEN=...
```

### Add config diagnostic

Create operator-safe endpoint or script:

```bash
python3 scripts/black_ledger_tick_news_config_check.py --base-url https://chummer.run
```

It must return redacted status:

```yaml
email_enabled: true
policy: subscribed_or_only_user_preview_fallback
ea_api_token_present: true
ea_principal_id_present: true
ea_binding_id_present: true
fleet_internal_token_required: true
operator_visible_secrets: false
```

### Acceptance criteria

- no secret values printed;
- missing config produces specific blocker;
- config check runs before send.

---

## P0-003 — Add live dry-run proof

### Command

```bash
FLEET_INTERNAL_API_TOKEN=$REAL_TOKEN \
python3 scripts/black_ledger_send_tick_news.py \
  --base-url https://chummer.run \
  --world emerald-sprawl-prelude \
  --turn 1 \
  --policy subscribed_or_only_user_preview_fallback \
  --dry-run
```

### Expected

```yaml
status: dry_run
recipient_count: 1
receipts:
  - status: pending_dry_run
    email_masked: ...
```

If result is suppressed, it must explain:

- disabled
- no eligible user
- multiple users no subscription
- delivery unconfigured
- privacy failed
- internal auth failed

---

## P0-004 — Add live send proof

### Command

```bash
FLEET_INTERNAL_API_TOKEN=$REAL_TOKEN \
python3 scripts/black_ledger_send_tick_news.py \
  --base-url https://chummer.run \
  --world emerald-sprawl-prelude \
  --turn 1 \
  --policy subscribed_or_only_user_preview_fallback \
  --send
```

### Expected if configured

```yaml
status: sent
recipient_count: 1
delivery_ref: ...
```

### Expected if EA not configured

```yaml
status: suppressed_delivery_unconfigured
failure_reason: ea_dispatch_unconfigured
```

Both are acceptable for debugging. Only `sent` is acceptable for the user’s expectation.

---

## P0-005 — Fix EA payload contract mismatch risk

### Problem

`BlackLedgerTickNewsNotificationService.SendToEaAsync` uses a different request shape than `ParticipationOperatorNotificationService.SendToEaAsync`.

### Fix

Use the same EA dispatch payload shape as the known participation notification path:

```csharp
var payload = new
{
    tool_name = "connector.dispatch",
    action_kind = "delivery.send",
    payload_json = new
    {
        principal_id = principalId,
        binding_id = bindingId,
        channel = "email",
        recipient = recipient.Email,
        subject = ...,
        content = BuildEmailBody(tickNews),
        metadata = ...,
        idempotency_key = eventKey
    }
};
```

Also parse both:

```csharp
target_ref
output_json.delivery_id
```

### Acceptance criteria

- unit test compares payload shape or uses a fake EA server;
- fake EA response with `target_ref` works;
- fake EA response with `output_json.delivery_id` works;
- failed EA response creates `failed_delivery`.

---

## P0-006 — Add real tests

### Required tests

```text
BlackLedger_tick_news_resolves_only_user_preview_recipient
BlackLedger_tick_news_suppresses_when_multiple_users_without_subscription
BlackLedger_tick_news_sends_to_subscribed_users
BlackLedger_tick_news_suppresses_when_email_disabled
BlackLedger_tick_news_suppresses_when_EA_unconfigured
BlackLedger_tick_news_privacy_gate_blocks_private_data
BlackLedger_tick_news_idempotency_prevents_duplicate_send
BlackLedger_preseeded_turn_one_can_send_catchup_email
BlackLedger_tick_news_EA_payload_shape_matches_connector_dispatch
```

### Verification

```bash
dotnet test Chummer.Run.Api.Tests --filter BlackLedgerTickNews
pytest tests/test_black_ledger_tick_news_delivery.py
```

---

## P0-007 — Ensure seeded Turn 1 can actually notify

### Problem

The background worker only picks up stored `WorldTicks` + `PlayerSafeNews` joins. Preseeded static Turn 1 may not exist in those lists.

### Fix options

#### Option A — Materialize seed into store

On first load/import:

```text
seed turn 1
→ WorldTicks
→ PlayerSafeNews
→ worker sends if policy allows
```

#### Option B — Explicit catch-up only

Turn 1 only sends when catch-up command is executed.

If using Option B, public/admin status must say:

```text
Preseeded Turn 1 email requires explicit catch-up send.
```

### Acceptance criteria

- one clear path exists;
- duplicate sends are idempotent;
- receipt visible after send/suppress.

---

## P1 — Account preference

Add `/account/participation` preference:

```text
Black Ledger news email
[ ] Send me public-safe Black Ledger turn summaries
```

Until preference exists, preview fallback can use only-user policy.

---

## P1 — Operator/ledger delivery status

Expose operator-safe delivery status:

- last tick news batch
- dry-run result
- last send result
- sent/suppressed/failed counts
- no raw email addresses
- no secret values

## Final done criteria

The feature is done only when:

1. live dry-run returns one eligible user or clear suppression;
2. live send returns `sent` or clear suppression;
3. Gmail receives the message if `sent`;
4. receipt persists;
5. duplicate send is idempotent;
6. no public secret/provider strings are exposed.
