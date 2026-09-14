# Direct TLS launcher for the Preview12 approval ledger

`scripts/android_preview12_approval_ledger_server.py` composes the existing
`SQLiteApprovalLedgerStore`, `create_app` HTTP boundary and PR11 signed receipt
protocol into a callable server. It is not an installer, provisioner, approval
issuer, protected signing controller, deployment or publication permission.
There is no import-time listener and no change to the checked-in dormant policy.

## Explicit startup

Run the module from an independently admitted Fleet installation, using its
reviewed Python dependencies (`fastapi==0.115.12`, `uvicorn==0.34.2` from
`controller/requirements.txt`), Linux sealed memfds, and a trusted root-owned
`/usr/bin/openssl` with OpenSSL 3 options. The launcher checks the two framework
versions, not the full interpreter/library/image provenance. Source, dependency,
host and service-account admission remain deployment responsibilities.

Example argument shape, **not a command to activate this repository's policy**:

```sh
python -m scripts.android_preview12_approval_ledger_server \
  --policy /srv/ledger-private/approval-policy.json \
  --database /srv/ledger-private/state/ledger.sqlite3 \
  --database-id <independently-retained-64-lowercase-hex-identity> \
  --bearer-sha256-file /srv/ledger-private/bearer.sha256 \
  --receipt-key-file /srv/ledger-private/receipt.pkcs8.der \
  --tls-cert-file /srv/ledger-private/tls-chain.pem \
  --tls-key-file /srv/ledger-private/tls-key.pem \
  --bind-address <explicit-canonical-IP>
```

There are no token/key bytes on argv, environment discovery, reload, implicit proxy,
plaintext, alternate-port, database-create or key-generation modes. Production
port is 443 because the existing protocol permits only canonical
`https://hostname` and exact hostname-only Host headers. Bind permission and
public DNS/TLS trust must already exist; this module grants neither. Launch it
with a minimal service environment, without unrelated controller credentials.

The full existing approval JSON is a container for
`replay_protection.external_ledger` and the fixed public approval binding.
The launcher admits the exact `fleet-release-approver-2026-09` key ID, role,
scope, public path/PEM digest/SPKI bytes/digest, consumer commit/tree/provenance
binding and non-authorizing output tuple through the issuer's public validator.
Unknown or builder identities, swapped public tuples and the old consumer paired
with the new key fail before database construction or credential reads.
The ledger must be explicitly configured before **any credential file** is
opened. Approval-issuer activation and obsolete human-review flags are not
startup requirements: the launcher does not invoke the issuer's ready gate, so
the ledger can be provisioned before the issuer. No
acceptance of this file promotes either one to ready.

All supplied configuration/credential files must be canonical absolute regular
single-link files, owned by the running UID, mode 0600. Ancestry must be root or
UID owned and not group/other writable. The sole writable-ancestor exception is
root-owned 1777 `/tmp` with an immediately contained UID-owned 0700 directory.
The existing database and its private parent are checked by the original store;
the launcher additionally checks its complete ancestry. It never creates,
resets, migrates or repairs a database, nor deletes a sidecar.

The bearer file contains exactly one lowercase SHA256 (optionally final LF), not
the bearer itself. It does not establish token entropy; independent provisioning
must issue a high-entropy token. The receipt key must be canonical 48-byte
Ed25519 PKCS8 DER, not PEM/encrypted data. Its derived SPKI must match both
reviewed ledger public bytes and digest, and cannot equal the source-pinned
approval key. Changing a sibling policy field cannot permit that reuse.

TLS accepts a bounded PEM certificate chain and unencrypted PEM key. The leaf
certificate SPKI must differ from both source-bound approval and admitted receipt
SPKIs before the TLS private key is opened. All three key roles remain separate.
Hostname,
time and server purpose are checked against the supplied chain as a local
anchor; SSLContext checks the private-key match. **This does not prove public CA
trust**: the unchanged remote client still uses its ordinary trusted roots.
SSLContext reads immutable sealed copies, not unchecked reopened input paths.
Held originals are revalidated before/after receipt signing. Rotation requires
an explicit stop/restart with newly admitted inputs; live drift fails closed.

## Limits and shutdown

One worker, no WebSockets/docs/OpenAPI or access logging. Direct mode rejects
all forwarded headers; the explicit local-proxy mode below is the only exception.
Existing exact four POST routes and body/response limits remain unchanged.
Defaults: two in-flight operations, 16 post-handshake connections, 32 backlog,
16 KiB incomplete HTTP header events, 10-second body timeout, two-second idle
keepalive and a 20-second absolute post-handshake connection lifetime.
Local options bound in-flight work to 1–8, connections to 2–64, body timeout to
(0,10] seconds and graceful ASGI shutdown to (0,30] seconds (default 15).
OpenSSL receipt operations have five-second deadlines, 4096-byte stdout/stderr
limits, a one-second reap bound and private sealed input FDs. No child inherits
caller auth/environment/stdio. Diagnostics are fixed ready/stopped/unavailable
markers; readiness means local configuration/store/key/TLS startup only.
After readiness, the launcher owns SIGTERM/SIGINT shutdown, lets Uvicorn perform
its shutdown, closes held inputs, then emits a fixed stopped marker with the
signal name and returns conventional status 143/130. It does not replay a signal
before the outer cleanup runs. Errors still return failure rather than a clean
shutdown status. Forced termination cannot promise Python-level cleanup.

TLS handshakes use asyncio's bounded default handshake timeout (60 seconds),
before HTTP admission. These are not a hard global pre-TLS socket cap or a DoS
proof. A resource-limited supervisor/network perimeter is still required.
Cancelled HTTP awaits do not undo committed ledger state or stop the existing
store worker. Graceful ASGI timeout is not a guaranteed whole-process deadline;
the supervisor must enforce its own final stop bound, including threadpool and
filesystem stalls. Held FDs are closed on normal/failing composition and exit.
Python/OpenSSL memory erasure is not claimed.

## Evidence boundary

Tests use public RFC/generated keys, disposable private SQLite databases and a
test-only ephemeral loopback socket supplied to the actual pinned Uvicorn
server. Test TLS validates the fixture certificate; it does not disable peer
verification or introduce a production port override. Existing client receipts,
Host/proxy rejection and shutdown are exercised through real local TLS, not a
made-up HTTPS ASGI scope alone. Hostile file/configuration fixtures are not
production credential, persistent-volume, rollback-resistance or public TLS
qualification. There is no `/health`; ledger status can perform lazy expiry
transitions, so it must not be advertised as a read-only health probe.

## Optional local Docker / HTTPS tunnel ingress

The existing Docker host and Cloudflare Tunnel can host this service; a new
machine or permission to publish host port 443 is not inherently required.
Port 443 above is the **container-local** listener. Use no published Docker
ports and a dedicated isolated network shared only with the admitted connector.
Keep the ledger separate from the public app container and unrelated services.
Container bind privileges, immutable image/dependency admission, private durable
storage, receipt-key custody and authenticated ingress remain deployment work.

Repeat `--trusted-proxy-address <canonical-local-IP>` for each explicitly admitted
last-hop connector address (maximum four). Addresses must be stable exact
RFC1918 IPv4, IPv6 ULA or loopback literals. No wildcards, CIDRs, DNS discovery,
mapped/scoped IPv6 or forwarded client identity is accepted. Changing an address
requires an explicit restart with the newly admitted configuration. With no
option, direct TLS mode is unchanged. Proxy configuration is checked before
opening policy or credential files.

Opt-in mode still requires actual HTTPS **from the connector to the ledger**,
the exact configured Host and four POST routes, the existing bearer credential,
and all original body/framing limits. Uvicorn proxy rewriting stays disabled.
The actual socket peer must match the explicit tuple; a forwarded header cannot
substitute for the peer, TLS or bearer credential. Only `X-Forwarded-Proto: https`
and a nonblank, bounded `X-Forwarded-For` are allowed forwarding headers; both are
required. XFF is untrusted opaque metadata and never becomes authentication,
workspace identity, logs or receipt content. Other forwarding headers fail closed.

Cloudflare documents [forwarding header behavior](https://developers.cloudflare.com/fundamentals/reference/http-headers/).
For the tunnel's [origin parameters](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/configure-tunnels/origin-parameters/),
use verified HTTPS to the container, matching `originServerName`/SNI and exact
`httpHostHeader`; use a reviewed `caPool` for a private origin CA if needed.
Keep `noTLSVerify=false`. Preserve fixed-length POST framing (configure
`disableChunkedEncoding` if needed). Edge/client certificate trust and
connector/origin certificate trust are distinct and both must be verified.
Network isolation and private authenticated ingress must be independently
established; accepting proxy headers alone does not create them. No wildcard
public ingress or unauthenticated signing route is authorized by this option.

Tests exercise this mode through a real verified loopback TLS connection with
public fixture keys and an existing disposable SQLite store. They do not run
cloudflared, deploy a route, provision a credential or establish release readiness.
