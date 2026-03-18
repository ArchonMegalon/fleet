# EA Current Brain Audit

Date: 2026-03-18
Audience: `solo-ea` maintainers, Fleet operators, and runtime/platform owners
Status: injected fleet feedback

## Short audit

EA now has the right lane concepts and much stronger runtime posture:

* explicit Codex lanes for `core`, `easy`, `repair`, `groundwork`, `review-light`, `survival`, and `audit`
* matching public model aliases such as `ea-coder-fast`, `ea-groundwork-gemini`, `ea-review-light`, `ea-coder-survival`, `ea-audit-jury`, and `ea-gemini-flash`
* `probe-all`, provider-health, owner-ledger sync, and survival fallback
* explicit `RuntimeProfile` plus stricter startup validation

The key remaining problem is structural:

**the EA brain is still split between the Responses lane engine and the planner/provider-registry path.**

## Main architecture debts

### 1. Profile definitions are still duplicated

`responses.py` still owns `_CODEx_PROFILES` while public aliases and provider-resolution logic live in `responses_upstream.py`.

### 2. Provider state models look durable, but runtime binding state is still memory-only

The domain has `ProviderBindingRecord` and `ProviderBindingState`, but the container still wires the provider registry with an in-memory binding repository.

### 3. Task-contract policy is typed, but persistence is still bag-shaped

`TaskContractRuntimePolicy` and related typed records exist, but canonical persistence still flows back through `budget_policy_json`.

### 4. Planner structured generation still routes through the older low-level provider path

The planner/provider-registry side still treats `structured_generate` as a lower-level capability instead of reusing the richer lane engine that Responses already exposes.

## Required follow-through

Land this work in order:

1. create one canonical brain/profile catalog shared by Responses and upstream model export
2. add a real `BrainRouterService` and route both Responses and planner-generated work through it
3. replace the in-memory provider binding repo with durable state
4. move planner `structured_generate` onto the same internal brain router
5. finish the storage boundary so typed runtime policy is no longer effectively just `budget_policy_json`
6. keep the current lane system, but make it the one internal routing brain instead of one smart path among several

## Fleet materialization request

Treat this as EA platform work, not a docs-only note.

Queue next:

1. canonicalize the lane/profile catalog
2. wire one durable brain router into Responses first
3. persist provider binding state and reuse existing telemetry/owner-ledger inputs
4. converge planner structured generation onto the same router instead of the older gemini-only path

## Bottom line

Do not redesign EA from scratch.

Do not remove the current lane system.

Do make one canonical brain/router layer that both Responses and the planner use, backed by durable provider state.

