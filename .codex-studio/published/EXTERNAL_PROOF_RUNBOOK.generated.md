# External Proof Runbook

- generated_at: 2026-04-07T02:07:34Z
- unresolved_request_count: 0
- unresolved_hosts: (none)
- plan_generated_at: 2026-04-07T02:07:33Z
- release_channel_generated_at: 2026-04-07T02:07:32Z
- capture_deadline_hours: 24
- capture_deadline_utc: 2026-04-08T02:07:32Z

## Prerequisites

- Run each host section on the matching native host (`macos` on macOS, `windows` on Windows).
- Provide signed-in download credentials before capture when public routes are account-gated.
- Supported auth inputs: `CHUMMER_EXTERNAL_PROOF_AUTH_HEADER`, `CHUMMER_EXTERNAL_PROOF_COOKIE_HEADER`, `CHUMMER_EXTERNAL_PROOF_COOKIE_JAR`.
- Set `CHUMMER_EXTERNAL_PROOF_ALLOW_GUEST_DOWNLOAD=1` only when install routes are intentionally guest-readable.
- Optional base URL override: `CHUMMER_EXTERNAL_PROOF_BASE_URL` (default `${CHUMMER_EXTERNAL_PROOF_BASE_URL:-https://chummer.run}`).

## Generated Command Files

- commands_dir: `/docker/fleet/.codex-studio/published/external-proof-commands`
- post_capture_script: `/docker/fleet/.codex-studio/published/external-proof-commands/republish-after-host-proof.sh`
- finalize_script: `/docker/fleet/.codex-studio/published/external-proof-commands/finalize-external-host-proof.sh`

No unresolved external-proof requests are currently queued.
