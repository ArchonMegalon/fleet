# Codex Fleet Studio Bundle

This bundle deploys three Docker services behind one internal origin:
- `fleet-controller`: the disposable `codex exec` spider / scheduler
- `fleet-studio`: a design-control plane where the admin can discuss project direction with Designer, Project Manager, or Architect roles
- `fleet-dashboard`: an Nginx gateway that keeps one Cloudflare target and serves both the fleet dashboard and `/studio`

## Default networking

- Docker network: `codex-fleet-net`
- Shared origin target for a separate `cloudflared` container: `http://fleet-dashboard:8090`
- Default host URL: `http://127.0.0.1:18090`
- Studio URL: `http://127.0.0.1:18090/studio`

## What Studio adds

Studio lets the admin user:
- discuss project direction and tradeoffs with a design-oriented agent role
- draft publishable artifacts without directly editing repo instructions by hand
- publish approved artifacts into repo-local `.codex-studio/published/`
- publish optional feedback notes into `feedback/` so coding workers see the decision immediately

Published artifacts can include:
- `VISION.md`
- `ROADMAP.md`
- `ARCHITECTURE.md`
- `runtime-instructions.generated.md`
- `QUEUE.generated.yaml`

The spider now reads published Studio artifacts before coding. If `QUEUE.generated.yaml` is present, it overlays the configured queue.

### Queue overlay format

```yaml
mode: append   # append | prepend | replace
items:
  - tighten hub route contracts
  - add approval review UI for generated assets
```

## Multi-account support

Both the spider and Studio can use different Codex identities. Map aliases in `config/accounts.yaml` to either:
- API keys (`auth_kind: api_key`)
- ChatGPT auth caches (`auth_kind: chatgpt_auth_json`)

Studio defaults to `acct-studio-a` and then falls back to `acct-shared-b`, but you can change that in `config/fleet.yaml`.

## Deploy

```bash
./deploy-fleet.sh
```

Or choose a different host port/network:

```bash
./deploy-fleet.sh --host-port 18190 --network-name my-fleet-net
```

## Common operations

Restart after config changes:

```bash
cd /opt/codex-fleet && docker compose up -d --build
```

Check the controller dashboard API:

```bash
curl http://127.0.0.1:18090/api/status
```

Check Studio sessions:

```bash
curl http://127.0.0.1:18090/api/studio/status
```

Connect an existing Cloudflare container to the shared network once:

```bash
docker network connect codex-fleet-net <cloudflared-container>
```

## Recommended admin flow

1. Open `/studio`.
2. Start a Designer or Architect session for a project.
3. Review the proposal and publish the approved artifacts.
4. Let the spider continue coding slices; it will ingest the published runtime instructions and queue overlays automatically.
