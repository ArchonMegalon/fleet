# EA 1min Billing Truth Path Feedback

Date: 2026-03-18

This is an implementation guide for building a first-class 1min billing truth path. It is not already implemented in the current repo state.

## Current state

The repo already has the estimate-oriented operator surfaces and display plumbing:

- `GET /v1/responses/_provider_health`
- `GET /v1/codex/profiles`
- `POST /v1/providers/onemin/probe-all`
- `codexea status` / `codexea onemin` rendering provider rows, burn/hour, ETA, and top-up-detected summaries

The BrowserAct substrate is also already the right extension point:

- BrowserAct provider capabilities exist for `chatplayground_audit`
- BrowserAct provider capabilities exist for `gemini_web_generate`
- tool execution already registers built-in BrowserAct handlers in the expected pattern

What is missing is the billing-backed truth path itself:

- no `browseract.onemin_billing_usage`
- no billing-page extraction flow for `https://app.1min.ai/billing-usage`
- no durable billing snapshot model
- no runway estimator that includes scheduled top-ups
- no EA status aggregate that distinguishes billing-backed runway from pure estimated-burn runway
- no Fleet dashboard surface for top-up-aware 1min runway

## Design rule

Do not overload `probe-all`.

Keep:

- `probe-all` = runtime slot validation

Add:

- billing usage page probe = slower, more authoritative billing/account telemetry

Label the new path clearly as:

- `basis = actual_billing_usage_page`

## Goal

Build a first-class billing truth path:

1. BrowserAct opens the 1min billing/usage page.
2. It extracts:
   - current remaining credits
   - optional max/plan credits
   - next scheduled top-up datetime
   - optional top-up amount / monthly allocation
   - optional cycle boundaries and rollover hints
3. EA stores that as an actual billing snapshot.
4. EA recomputes smarter runway using:
   - recent burn rates
   - scheduled top-up timing
5. Fleet and CodexEA render:
   - remaining credits
   - next top-up date
   - depletion before/after top-up
   - runway under multiple burn assumptions

## PR 1 — Add BrowserAct 1min billing capability

### Capability

Add a BrowserAct capability:

- provider capability key: `onemin_billing_usage`
- tool name: `browseract.onemin_billing_usage`

### Files

- `ea/app/services/provider_registry.py`
- `ea/app/services/tool_execution.py`
- `ea/app/services/tool_execution_browseract_registry.py`
- `ea/app/services/tool_execution_browseract_adapter.py`
- `scripts/generate_browseract_content_templates.py`

### Expected provider-registry addition

Add this beside the existing BrowserAct capabilities:

```python
ProviderCapability(
    provider_key="browseract",
    capability_key="onemin_billing_usage",
    tool_name="browseract.onemin_billing_usage",
)
```

### Expected tool-registration addition

Register a new built-in BrowserAct tool in `tool_execution.py`:

```python
("browseract", "onemin_billing_usage"): self._register_builtin_browseract_onemin_billing_usage,
```

And add the corresponding registry function in `tool_execution_browseract_registry.py`.

## PR 2 — Add BrowserAct adapter/template logic

### URL

Use:

- `https://app.1min.ai/billing-usage`

### Extraction requirements

Do not rely on a brittle single selector. Use:

1. labeled visible-text parse
2. fallback card/table label-value parse
3. fail-safe raw-text/screenshot evidence if parsing fails

### Parse targets

Extract if visible:

- `remaining_credits`
- `max_credits`
- `used_percent`
- `next_topup_at`
- `cycle_start_at`
- `cycle_end_at`
- `topup_amount`
- `rollover_enabled`
- `source_url`
- `basis`

### Challenge handling

If login/session/challenge blocks the page:

- return structured blocked state
- do not silently emit nulls as if they were valid

## PR 3 — Add durable billing snapshot model

Add a dedicated model for browser-derived billing truth instead of cramming this into runtime probe evidence.

Suggested shape:

```python
@dataclass(frozen=True)
class ProviderBillingSnapshot:
    provider_key: str
    account_name: str
    observed_at: str
    remaining_credits: float | None = None
    max_credits: float | None = None
    used_percent: float | None = None
    next_topup_at: str | None = None
    cycle_start_at: str | None = None
    cycle_end_at: str | None = None
    topup_amount: float | None = None
    rollover_enabled: bool | None = None
    basis: str = "actual_billing_usage_page"
    source_url: str = ""
    structured_output_json: dict[str, Any] = field(default_factory=dict)
```

Persist it durably.

Status precedence should prefer:

1. `actual_billing_usage_page`
2. `actual_provider_api`
3. `observed_error`
4. `max_minus_observed_usage`
5. `unknown_unprobed`

## PR 4 — Add runway estimator with top-ups

Current ETA is still essentially:

- remaining credits / current burn

That ignores scheduled top-ups.

Add a helper that computes:

- runway with no future top-up
- runway including the next scheduled top-up
- current-pace projection
- 7d-average projection
- blended projection if desired
- `depletes_before_next_topup`

Recommended outputs:

- `hours_remaining_at_current_pace_no_topup`
- `hours_until_next_topup`
- `credits_at_next_topup_if_current_pace`
- `hours_remaining_including_next_topup_at_current_pace`
- `days_remaining_including_next_topup_at_7d_avg`
- `depletes_before_next_topup`
- `basis = billing_plus_observed_burn`

If rollover is enabled, do not assume unused credits disappear at the cycle boundary.

## PR 5 — Extend EA status aggregate

Add a dedicated status block such as:

```json
"onemin_billing_aggregate": {
  "slot_count": 34,
  "slot_count_with_billing_snapshot": 22,
  "sum_max_credits": 151300000,
  "sum_free_credits": 93961187,
  "remaining_percent_total": 62.1,
  "next_topup_at": "2026-03-31T00:00:00Z",
  "hours_until_next_topup": 320.5,
  "hours_remaining_at_current_pace_no_topup": 38.8,
  "hours_remaining_including_next_topup_at_current_pace": 510.2,
  "days_remaining_including_next_topup_at_7d_avg": 167.0,
  "depletes_before_next_topup": false,
  "basis_summary": {
    "actual_billing_usage_page": 22,
    "observed_error": 12
  }
}
```

This should live in EA status first so downstream consumers do not reimplement billing math.

## PR 6 — Extend CodexEA status/onemin

CodexEA already renders:

- external provider rows
- burn/hr
- ETA
- top-up summary

Extend it to show the richer billing-aware runway.

Suggested command extension:

- `codexea onemin --probe-all --billing`

Show:

- slots total
- slots with reported balance
- slots with billing snapshots
- next top-up date
- top-up amount
- runway without top-up
- runway including top-up
- basis quality counts

## PR 7 — Surface in Fleet dashboard

Do not reimplement the math in Fleet.

Preferred data path:

- Fleet admin/dashboard calls EA `/v1/codex/status`
- Fleet consumes `onemin_billing_aggregate`

Dashboard card should show:

- free credits
- percent left
- next top-up datetime
- top-up amount
- depletion before top-up flag
- runway at current pace
- runway at 7d average
- basis quality badge:
  - actual
  - mixed
  - estimated
  - stale

## PR 8 — Later: add owner/member reconciliation

This is optional for the first pass but strongly recommended later.

Add a second BrowserAct page probe for 1min member/owner reconciliation so you can project:

- member active/deactivated state
- owner/member linkage
- per-member credit limits
- slot-to-user reconciliation

## Rollout order

1. Add `browseract.onemin_billing_usage`
2. Add billing snapshot persistence
3. Add top-up-aware runway estimator
4. Extend EA status aggregate
5. Extend `codexea status` / `codexea onemin`
6. Add Fleet dashboard card
7. Later: add member roster reconciliation

## Caveat

The authenticated 1min DOM must be validated in a live BrowserAct run.

Build around:

- robust label/value extraction
- fallback selectors
- structured failure states with raw text/screenshot evidence

Do not hardcode one brittle selector and assume it survives.

## One-sentence instruction

Add a BrowserAct-powered 1min billing truth source, persist those billing snapshots, compute runway both with and without scheduled top-ups, and expose that aggregate in EA status so CodexEA and Fleet can render it without duplicating logic.
