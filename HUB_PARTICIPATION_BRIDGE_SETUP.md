# Hub participation bridge setup

Date: 2026-03-23

## Purpose

Hub's signed-in participation flow depends on Fleet's internal participant-lane bridge.

Hub calls Fleet internal endpoints under `/api/internal/participant-lanes/*` and must present the same `FLEET_INTERNAL_API_TOKEN` that the Fleet controller expects.

## Current contract

Protected controller endpoints in [controller/app.py](controller/app.py):

- `GET /api/internal/participant-lanes`
- `POST /api/internal/participant-lanes`
- `POST /api/internal/participant-lanes/{lane_id}/device-auth/start`
- `GET /api/internal/participant-lanes/{lane_id}`
- `POST /api/internal/participant-lanes/{lane_id}/activate`
- `POST /api/internal/participant-lanes/{lane_id}/stop`
- `DELETE /api/internal/participant-lanes/{lane_id}`

Accepted auth headers:

- `Authorization: Bearer <token>`
- `X-Fleet-Internal-Token: <token>`

Hub currently uses the bearer form.

If `FLEET_INTERNAL_API_TOKEN` is missing, Fleet returns `503 participant lane internal auth is not configured`.
If the token is present but wrong, Fleet returns `401 participant lane internal auth failed`.

## Required configuration

### 1. Fleet controller

Set a strong shared secret for:

- `FLEET_INTERNAL_API_TOKEN`

This must be present in the Fleet controller runtime environment.

The example env already documents the variable in [runtime.env.example](runtime.env.example).
Do not commit the real value.

### 2. Hub portal

Set the same `FLEET_INTERNAL_API_TOKEN` value in the Hub portal deployment so Hub can call Fleet's internal participant-lane bridge.

Without this, Hub degrades signed-in participation into an unavailable state.

### 3. Ownership boundary

This token is only for Hub-to-Fleet internal lane control.

It does not change the ownership split:

- Hub owns consent, sponsor-session and accounting truth, badges, receipts, and account state.
- Fleet owns lane creation, device-auth execution, lane-local auth/cache storage, and worker lifecycle.
- Raw Codex/OpenAI auth cache stays lane-local on Fleet.

## Minimum rollout

1. Generate a new strong shared secret.
2. Set `FLEET_INTERNAL_API_TOKEN` in the Fleet controller deployment.
3. Set the same `FLEET_INTERNAL_API_TOKEN` in the Hub portal deployment.
4. Restart `fleet-controller`.
5. Restart the Hub portal service.

## Verification

### Fleet-side

This should no longer return `503 participant lane internal auth is not configured`:

```bash
curl -i \
  -H "Authorization: Bearer $FLEET_INTERNAL_API_TOKEN" \
  "http://fleet-controller:8090/api/internal/participant-lanes"
```

Expected result:

- `200` if the controller is healthy and the token matches
- `401` if the token is wrong
- not `503`

### Hub-side

After sign-in on `chummer.run`:

1. Open `/participate/codex`.
2. Click `Yes, I want to contribute`.

Expected result:

- Hub returns a real authorization payload with `verificationUri` and `userCode`.
- The page moves into `Authorize in ChatGPT`.
- Not `Participation is unavailable right now`.

## If it still fails

Check these in order:

1. `fleet-controller` really has `FLEET_INTERNAL_API_TOKEN` in its container env.
2. The Hub portal service really has the same `FLEET_INTERNAL_API_TOKEN`.
3. Hub is pointed at the correct Fleet base URL.
4. The token values match exactly with no extra whitespace.
5. Fleet controller logs do not show `participant lane internal auth failed`.
