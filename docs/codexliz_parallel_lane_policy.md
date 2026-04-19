# Parallel `codexliz` Lane Policy

This policy exists so long-running Fleet operators can scale `codexliz` usage without turning one human auth cache or one writable state tree into a hidden shared dependency.

## Core rule

Treat each concurrent writable `codexliz` lane as its own token and environment island.

- One real ChatGPT auth source or one API key pool equals one effective writable lane unless you deliberately provision another isolated token set.
- Do not point two active lanes at the same writable `CODEX_HOME`, `HOME`, `CODEXLIZ_STATE_DIR`, `auth.json`, or `.cache/codexliz` tree by default.
- Keep `CODEXLIZ_PROXY_PORT` unset unless you must pin it for local firewall or routing reasons.
- If you do pin `CODEXLIZ_PROXY_PORT`, pin a distinct port per lane.

The shim now persists an auto-assigned proxy port in `${CODEXLIZ_STATE_DIR}/proxy.port`, so a lane can restart safely without colliding with another lane that uses a different state root.

## Required operator posture

For every manual or supervisor-managed parallel `codexliz` lane:

- set a lane-local `CODEX_HOME`
- set `HOME` to that same lane-local directory unless you have a stricter isolated home already prepared
- set a lane-local `CODEXLIZ_STATE_DIR`
- treat the lane's auth, proxy pid/log, and cache files as exclusive to that lane

Fleet-managed worker homes already follow this posture for supervisor and direct lanes. Manual operator shells must do the same.

## Manual launch pattern

```bash
export CODEX_HOME=/docker/fleet/state/manual-codexliz/lane-a
export HOME="$CODEX_HOME"
export CODEXLIZ_STATE_DIR="$CODEX_HOME/.cache/codexliz"
unset CODEXLIZ_PROXY_PORT
codexliz --model qwen2.5-coder:32b
```

For a second lane, change all three writable paths before launching it.

## Forbidden shortcuts

- Reusing one writable ChatGPT `auth.json` across two active lanes.
- Reusing one `.cache/codexliz` directory across two active lanes.
- Treating alias count as safe parallelism when the aliases resolve to the same real auth cache.
- Pinning the same proxy port in two active lanes.

## Proof in repo

- `scripts/codex-shims/codexliz` auto-assigns and persists lane-local proxy ports when no explicit port is pinned.
- `tests/test_codexliz_shim.py` proves distinct per-state-dir proxy isolation.
- `README.md` and `runtime.env.example` carry the operator-facing runtime guidance.
