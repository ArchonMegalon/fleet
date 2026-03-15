# Next Session Handoff

Date: 2026-03-15
Workspace focus: `/docker/fleet` and `/docker/EA`

## What changed in this session

- Completed the previously pending EA live smoke against the local `127.0.0.1:8090` endpoint.
- Fixed the user-level `codexea` launcher so it no longer relies on `codex -p ea` for EA-backed non-interactive runs.
- No repo files were changed inside `/docker/EA` during this session.
- Focused validation passed against the existing dirty `/docker/EA` Responses/provider-health slice.

### User-level files changed

- [`/home/tibor/.codex/config.toml`](/home/tibor/.codex/config.toml)
  - already contains `[model_providers.ea]`
  - EA provider points to `http://127.0.0.1:8090/v1`
  - `wire_api = "responses"`
  - current profile model in file is `gpt-5`
  - important:
    - with Codex CLI `0.114.0`, live testing showed that `codex -p ea exec ...` did not apply the profile's `model_provider` and `model` fields, even though the EA provider block itself is valid

- [`/home/tibor/.local/bin/codexea`](/home/tibor/.local/bin/codexea)
  - now injects explicit EA defaults into Codex instead of calling `-p ea`
  - forces `model_provider = "ea"`
  - defaults model to `gpt-5` via `CODEXEA_MODEL` unless overridden
  - still defaults `EA_PRINCIPAL_ID` to `$(id -un)-codex-ea` if unset

### Existing normal launcher left unchanged

- [`/home/tibor/bin/codex`](/home/tibor/bin/codex)
  - still the default normal launcher
  - still injects `/fast`
  - still points to the real binary at `/usr/bin/codex`

## Current command split

- `codex`
  - normal OpenAI/Codex path

- `codexea`
  - EA-backed path
  - uses the `ea` provider block from `~/.codex/config.toml`
  - wrapper now injects the working model/provider settings explicitly

## EA endpoint status confirmed

From [`responses.py`](/docker/EA/ea/app/api/routes/responses.py):

- `GET /v1/models`
- `POST /v1/responses`
- `GET /v1/responses/{response_id}`
- `GET /v1/responses/{response_id}/input_items`
- `GET /v1/responses/_provider_health`
- `GET /v1/codex/profiles`
- `POST /v1/codex/core`
- `POST /v1/codex/easy`
- `POST /v1/codex/audit`

Important:
- Codex custom-provider wiring should target the base Responses provider at `/v1`
- The `/v1/codex/*` routes are EA-specific helper endpoints, not the provider base URL for Codex config

## What was verified

- `codex` resolves to `/home/tibor/bin/codex`
- `codexea` resolves to `/home/tibor/.local/bin/codexea`
- `EA_PRINCIPAL_ID='tibor-codex-ea' curl -sS -H "X-EA-Principal-ID: tibor-codex-ea" http://127.0.0.1:8090/v1/models`
  - returned `HTTP/1.1 200 OK`
- `EA_PRINCIPAL_ID='tibor-codex-ea' curl -sS -H "X-EA-Principal-ID: tibor-codex-ea" http://127.0.0.1:8090/v1/codex/profiles`
  - returned `HTTP/1.1 200 OK`
- `EA_API_TOKEN='' EA_PRINCIPAL_ID='tibor-codex-ea' codexea exec -C /docker/EA "answer exactly: ok"`
  - launched with banner `provider: ea`, `model: gpt-5`
  - completed successfully with output `ok`
- Focused `/docker/EA` validation passed with the repo's own harness:
  - `PYTHONPATH=ea EA_STORAGE_BACKEND=memory ./.venv/bin/python -m pytest -q tests/test_responses_upstream.py`
    - `26 passed`
  - `PYTHONPATH=ea EA_STORAGE_BACKEND=memory ./.venv/bin/python -m pytest -q tests/test_responses_api_contracts.py`
    - `23 passed`
  - `PYTHONPATH=ea EA_STORAGE_BACKEND=memory ./.venv/bin/python -m pytest -q tests/test_operator_contracts.py::test_local_env_rotation_slots_and_gitignore_cover_browseract_and_onemin_keys`
    - `1 passed`

## What is still unknown

- Why Codex CLI `0.114.0` ignores the `ea` profile fields for `codex -p ea exec ...`
- Whether the interactive bare `codex -p ea` path behaves exactly the same way
- Whether it is worth adding custom-model metadata for EA aliases such as `ea-coder-best`; the current default `gpt-5` avoids Codex-side unknown-model warnings

## First checks for the next session

1. Export auth:
   - `export EA_PRINCIPAL_ID='tibor-codex-ea'`
2. Use `codexea` directly for EA-backed runs; do not rely on `codex -p ea` unless you are debugging profile semantics.
3. If you need another quick transport sanity check:
   - `EA_API_TOKEN='' EA_PRINCIPAL_ID='tibor-codex-ea' codexea exec -C /docker/EA "answer exactly: ok"`
4. Resume from the active `/docker/EA` dirty Responses/provider-health slice instead of redoing smoke.
5. Continue the next real Fleet/EA backlog slice from the current workspace state.

## If `codexea` fails

- Check the launch banner first:
  - if it says `provider: openai`, the wrapper is not being used or was changed
- Re-check the EA endpoint:
  - `curl -sS -H "X-EA-Principal-ID: $EA_PRINCIPAL_ID" http://127.0.0.1:8090/v1/models`
- Re-check whether explicit `-c model_provider="ea"` still works with this Codex build
- Fallbacks if needed:
  - use direct `curl` against EA Responses endpoints
  - or wire Fleet/EA through the MCP bridge path instead of the custom-provider path for this terminal

## Repo state at handoff

- `/docker/fleet`: only [`NEXT_SESSION_HANDOFF.md`](/docker/fleet/NEXT_SESSION_HANDOFF.md) is untracked
- `/docker/EA`: dirty worktree already existed before this session in:
  - [`/docker/EA/.env.example`](/docker/EA/.env.example)
  - [`/docker/EA/.env.local.example`](/docker/EA/.env.local.example)
  - [`/docker/EA/CHANGELOG.md`](/docker/EA/CHANGELOG.md)
  - [`/docker/EA/ENVIRONMENT_MATRIX.md`](/docker/EA/ENVIRONMENT_MATRIX.md)
  - [`/docker/EA/HTTP_EXAMPLES.http`](/docker/EA/HTTP_EXAMPLES.http)
  - [`/docker/EA/Makefile`](/docker/EA/Makefile)
  - [`/docker/EA/README.md`](/docker/EA/README.md)
  - [`/docker/EA/RUNBOOK.md`](/docker/EA/RUNBOOK.md)
  - [`/docker/EA/ea/app/services/responses_upstream.py`](/docker/EA/ea/app/services/responses_upstream.py)
  - [`/docker/EA/tests/test_operator_contracts.py`](/docker/EA/tests/test_operator_contracts.py)
  - [`/docker/EA/tests/test_responses_api_contracts.py`](/docker/EA/tests/test_responses_api_contracts.py)
  - [`/docker/EA/tests/test_responses_upstream.py`](/docker/EA/tests/test_responses_upstream.py)

## Resume context

The EA transport blocker is closed:

- the terminal now has a working `codex` vs `codexea` split
- direct EA endpoint smoke passed on `2026-03-15`
- `codexea exec` smoke also passed on `2026-03-15`
- the remaining caveat is only the stale/broken `-p ea` profile path in this Codex CLI build
- resume substantive Fleet/EA backlog work from the current dirty `/docker/EA` slice instead of re-proving transport
