# Repo hygiene, release trust, and automation safety

## Purpose

This file turns public-repo hygiene, release-proof discipline, and automation blast-radius control into first-class canon.

The Chummer repo split is already strong on bounded-context ownership.
The next risk is not missing architecture.
The next risk is that public repos, release surfaces, and automation lanes become harder to verify than the product model they are supposed to protect.

## Problem statement

The main hazards now are operational:

* runtime state, local databases, env files, logs, and caches can leak into public repos or drift into accepted local habits
* telemetry and evidence folders can look like runtime logs unless their fixture/redaction posture is explicit
* release truth can drift between owning repos, registry channel state, updater feeds, public guide pages, `/downloads`, and forbidden GitHub binary shelves
* repo-local verify scripts can become large alias-sensitive grep programs instead of maintainable boundary checks
* automation power can outrun machine-enforced safety limits
* product READMEs can become mixed product pitch, runtime manual, and worker prompt surfaces
* public feedback and support lanes can lag behind the sophistication of the internal repo graph

## Core stance

1. `chummer6-hub-registry` owns canonical promoted release truth.
   `/downloads`, updater feeds, and downstream guide shelves are projections from that truth, not competing authorities.
   GitHub may reference source, development evidence, or the `chummer.run` download route only; it must not host public client binaries as a download path.
2. Repo-local `verify.sh` entrypoints may remain as thin smoke wrappers.
   Boundary policy itself should move into shared declarative data plus one reusable boundary-lint tool.
3. Fleet safety must not depend on model obedience.
   Blast-radius limits, protected-path rules, and review separation must be machine-enforced.
4. Golden user loops outrank feature sprawl.
   If install, update, support, explain, and closeout are not boring, more product surface is not the priority.
5. Production runtime posture must fail closed.
   Storage, auth, principal scope, migration posture, and audit sinks are startup invariants, not soft warnings.

## Priority order

### 1. Fleet hygiene and secret posture

Treat public Fleet hygiene as urgent.

Required posture:

* no checked-in runtime databases except deliberate scrubbed fixtures
* no checked-in non-example env files
* no checked-in logs, telemetry dumps, tmp trees, or local package caches
* generic `logs/` and `logs/telemetry/` paths are forbidden outside explicitly named redacted fixture or evidence lanes
* CI fails if those artifacts appear again
* any plausibly exposed secret or operator credential is rotated after a scrub

Accept when:

* `.gitignore` and CI guards reject runtime state and secret-like artifacts
* redacted fixture/evidence paths are explicit enough that public readers can tell the difference between proof cargo and runtime telemetry
* history is scrubbed where necessary
* production/runtime examples remain available as `.example` or explicit fixtures only

### 2. One signed release-manifest chain

Every promoted build needs one canonical release manifest that binds:

* product and channel identity
* repo commit set
* artifact digests and signatures
* embedded runtime-bundle fingerprint
* contract/package version floor
* registry publication receipt

Accept when:

* Fleet verifies the manifest before promotion
* Registry publishes it as channel truth
* updater feeds, `/downloads`, and public guide projections all compile from it
* promotion fails if those surfaces disagree
* promotion fails if release automation tries to publish client binaries directly to GitHub instead of routing acquisition through `chummer.run`

### 3. Shared declarative boundary lint

Replace giant repo-local shell verifiers with a shared tool plus repo-owned data files.

Required posture:

* each repo keeps a thin local verify entrypoint
* boundary ownership, forbidden imports, allowed sibling aliases, and protected path rules live in data
* diagnostics name the violated rule instead of only showing raw grep failures

Accept when:

* repos can express boundary policy in one machine-readable file
* alias drift such as `chummer-*` versus `chummer6-*` cannot silently pass
* the boundary-lint layer is reused across Core, UI, Mobile, Hub Registry, Media Factory, Fleet, and EA

### 4. GitHub Actions and workflow hardening

Public workflow posture must be pinned and least-privilege.

Required posture:

* no third-party action pinned to a moving branch such as `@master`
* CodeQL and other security workflows target `main`, not a stale default branch alias
* GitHub checkout actions are on current supported majors
* default workflow permissions are `contents: read`
* release workflows request only the explicit elevated permissions they need
* concurrency is set so duplicate waves cancel cleanly
* dependency review, secret scanning, boundary lint, build/test, and release-manifest verification are required gates for promotion

Accept when:

* moving-head workflow dependencies are gone
* security workflows execute on the branch where normal work actually lands
* branch protection requires the hardening checks above

### 5. Chummer boring-user-loop proof

The next flagship proof is the boring desktop loop:

1. install on Windows, macOS, and Linux
2. create or import one representative character
3. change one rule-affecting choice
4. see the explain/provenance result
5. update to the next build
6. file a support or crash report
7. trace that report back to exact release, artifact, runtime bundle, and contracts

Accept when:

* that loop is release-gated and evidenced across all three desktop platforms
* support and release truth share the same release-manifest identity

### 6. Executive Assistant boring-product-loop proof

EA should prove one user-meaningful product loop instead of only many runtime endpoints.

Canonical loop:

1. email/calendar intake arrives
2. morning memo is generated
3. a decision queue item is created
4. an approved draft or action is recorded
5. the commitment ledger updates
6. audit/evidence truth shows the chain

Accept when:

* one acceptance test proves that loop end to end
* runtime docs are split away from the public product story

### 7. Fleet blast-radius limits

Fleet needs hard caps independent of model behavior.

Minimum default posture:

* `max_prs_per_repo_per_day: 2`
* `max_files_changed_per_run: 25`
* `max_lines_changed_per_run: 1500`
* `max_parallel_runs_per_repo: 1` unless canon grants an exception
* human approval required for `.github/**`, `deploy/**`, `infra/**`, `migrations/**`, `**/*.env*`, and secret-bearing paths
* self-review forbidden
* release-promoting changes require non-writer evidence

Accept when:

* Fleet enforces the limits in code and policy, not only in prose

### 8. Canonical repo graph manifest

`chummer6-design` should publish one machine-readable repo graph that downstream repos and Fleet consume.

It should bind:

* public slug
* local aliases
* owned surfaces
* forbidden surfaces
* package outputs
* release-gate roles

Accept when:

* README generation, boundary lint, Fleet queue logic, and repo-audit tooling all read one shared repo graph

### 9. Documentation split and README discipline

Public READMEs should prioritize product purpose and quickstart.
Operational depth should live under `docs/`.

Preferred README shape:

1. purpose
2. owns / does not own
3. quickstart
4. verify
5. release status
6. links to deeper docs

Accept when:

* product docs and runtime docs are split cleanly in EA first, then in the rest of the estate as needed
* READMEs stop acting as architecture map, operator manual, release log, and worker prompt at the same time

### 10. Public feedback and support lanes

Public contribution and support routes should be explicit even before full open governance.

Required posture:

* issue templates for bug, rules-math, installer/update, and support/export problems
* `SECURITY.md`, `SUPPORT.md`, and `CONTRIBUTING.md`
* support forms capture release, platform, installer type, runtime bundle, rule environment, expected result, actual result, and explain-trace context where relevant

Accept when:

* a public user can report the boring trust failures without insider knowledge of the repo graph

## Sequencing rule

Execute this work in the following order:

1. Fleet hygiene and secret posture
2. release-manifest chain
3. Fleet blast-radius limits
4. shared declarative boundary lint
5. workflow hardening
6. Chummer boring-user-loop proof
7. EA boring-product-loop proof
8. canonical repo graph manifest
9. documentation split
10. public feedback and support lanes

This order is deliberate.
Safety and proof have to harden before the automation estate gets more authority.

## Non-goals

This file does not reopen bounded-context ownership.
It does not move release truth away from Registry.
It does not turn GitHub releases into canonical authority.
It does not allow GitHub releases, GitHub Actions artifacts, repo attachments, or repo-hosted shelves to become public client download sources.
It does not replace repo-local smoke/build/test entrypoints with one giant central script.
It does not justify more feature breadth while the boring trust loops are still noisy.
