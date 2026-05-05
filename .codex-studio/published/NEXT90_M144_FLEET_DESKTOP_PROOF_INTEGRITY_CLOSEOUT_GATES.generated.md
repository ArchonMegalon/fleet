# Next90 M144 Fleet Desktop Proof Integrity Closeout Gates

- status: `pass`
- desktop_proof_integrity_closeout_status: `blocked`
- ready: `False`

## Runtime blockers
- UI_WINDOWS_DESKTOP_EXIT_GATE still cites release channel version `run-20260502-105804` while live RELEASE_CHANNEL is `run-20260503-163502`.
- Windows startup-smoke receipt version `run-20260502-105804` no longer matches live RELEASE_CHANNEL version `run-20260503-163502`.
- Windows startup-smoke receipt version `run-20260502-105804` does not match the promoted Windows artifact version `run-20260503-163502`.
- DESKTOP_EXECUTABLE_EXIT_GATE still cites release channel version `run-20260502-105804` while live RELEASE_CHANNEL is `run-20260503-163502`.
- Windows tuple proof is older than the live release-channel publish and is still carrying forward stale promoted-version truth.

## Warnings
- Fleet queue mirror row is still missing for work task 144.4.
