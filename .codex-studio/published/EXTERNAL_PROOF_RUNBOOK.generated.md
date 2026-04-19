# External Proof Runbook

- generated_at: 2026-04-19T11:24:57Z
- unresolved_request_count: 0
- unresolved_hosts: (none)
- plan_generated_at: 2026-04-19T11:24:56Z
- release_channel_generated_at: 2026-04-18T19:53:27Z
- capture_deadline_hours: 24
- capture_deadline_utc: 2026-04-19T19:53:27Z

## Prerequisites

- Run each host section on the matching native host (`macos` on macOS, `windows` on Windows).
- Provide signed-in download credentials before capture when public routes are account-gated.
- Supported auth inputs: `CHUMMER_EXTERNAL_PROOF_AUTH_HEADER`, `CHUMMER_EXTERNAL_PROOF_COOKIE_HEADER`, `CHUMMER_EXTERNAL_PROOF_COOKIE_JAR`.
- Set `CHUMMER_EXTERNAL_PROOF_ALLOW_GUEST_DOWNLOAD=1` only when install routes are intentionally guest-readable.
- Optional base URL override: `CHUMMER_EXTERNAL_PROOF_BASE_URL` (default `${CHUMMER_EXTERNAL_PROOF_BASE_URL:-https://chummer.run}`).

## Generated Command Files

- commands_dir: `/docker/fleet/.codex-studio/published/external-proof-commands`
- command_bundle_sha256: `135bbeae56e3beb0f43fc9a9b87cd5a5114c22b0547cdf84769fbb4cd1390df7`
- command_bundle_file_count: 26
- post_capture_script: `/docker/fleet/.codex-studio/published/external-proof-commands/republish-after-host-proof.sh`
- finalize_script: `/docker/fleet/.codex-studio/published/external-proof-commands/finalize-external-host-proof.sh`

No unresolved external-proof requests are currently queued.
