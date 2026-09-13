# PR11 HTTP factory — source-only, not deployed custody

`scripts/android_preview12_approval_ledger_service.py` provides `create_app` over
the unchanged PR11 protocol and existing SQLite store. It creates no module-level
app, database, key, credential, CLI, workflow or network listener. Callers must
supply an existing identity-pinned store, an explicitly configured **existing**
ledger policy, a SHA256 bearer-token digest and a receipt-signing callback.
No current policy is activated by this module.

The callback receives immutable canonical receipt bytes and returns exactly 64
Ed25519 signature bytes. The factory builds the existing three-field ledger
signature envelope and calls the unchanged PR11 signature/receipt validator
against the configured public pin before returning 200. It never loads or
adapts the separate approval-signing environment key. Failed receipt signing
does not undo a committed reservation or approval; status/replay recovers state.
Repeated **receipt** signing is expected and does not prove approval sign-once.

Only the four existing POST paths are accepted, including POST status. Exact
HTTPS scheme, Host, raw/decoded path agreement and an empty query/root path are
required. Alternate slash routes, documentation, browser Origins, forwarded
headers, duplicate headers and content encodings are rejected. There is no
cookie, login redirect, alternate auth header or disabled-open mode. The bearer
must use the standard ASCII bearer alphabet and be independently provisioned
with high entropy; digest comparison is constant-time. The factory holds no raw
bearer, and does not read the process environment.

Authentication precedes all body reads and store calls. Actual streamed body
bytes are bounded to 65,536 and a total deadline (at most 10 seconds), independently
of Content-Length. The PR11 client uses known-length JSON bytes; alternate HTTP
Transfer-Encoding is rejected. ASGI body fragmentation remains supported.
Strict existing parsing preserves duplicate-field rejection, exact types and
request digest binding. The body operation must match its route before mutation.

Per-factory admission bounds simultaneous body readers and submitted workers
(default two, configurable one through eight). Busy requests get 429 without
reading bodies. SQLite, signing and signature verification execute off the
event loop. Once submitted, only the worker releases its slot; cancellation or
disconnect cannot falsely free capacity while the thread still executes. A
permanently wedged signer conservatively retains its slot. The external provider
must implement bounded work and the deployment must supervise/drain workers;
this factory cannot safely kill a Python thread or claim a timed-out commit
did not occur. No application-level mutation retry is added.

Failures are fixed bounded JSON without exception or request content. Store
invalid/conflict/missing map to 400/409/404; store/provider/verification failure
maps to 503. The unchanged client already handles bounded retry/status recovery.
Responses have explicit JSON bytes, Content-Length and no-store/nosniff headers.

Real deployment remains separately required: authenticated TLS termination,
trusted ASGI metadata (do not enable untrusted proxy-header rewriting), protected
bearer provisioning, independently reviewed receipt-key custody, durable local
storage/backups/clock, request/connection limits, quotas, worker supervision and
redacted infrastructure logs. Admission is per process/factory, not a distributed
rate limit. Protected approval review/job provenance and approval sign-once are
not supplied by bearer access to a ledger. No endpoint, trust pin or operational
authority is implied by these source/tests.

Tests use raw in-process ASGI messages, real temporary SQLite files, the unchanged
client and a published RFC test vector. They do not exercise deployed TLS or
production secrets. Compatibility must be reported with actual tested FastAPI /
Starlette versions; an ambient newer installation is not the repository's pin.
