# NEXUS-PAN Continuity Spec

NEXUS-PAN is the continuity spine for:

- claimed installs
- runner return
- session resume
- reconnect posture

Public route:

- `/play/continuity`
- `/play/continuity/receipts`
- `/mobile/pwa.json`

Boundary:

- public route exposes aggregate continuity proof and bounded receipts
- private account/device history stays on signed-in routes

Current state:

- shipped MVP

Shipped now:

- public-safe claimed-install counts
- public-safe reconnect and browser-callback posture
- downloadable continuity receipts
- mobile/PWA handoff JSON
- explicit signed-in runboard boundary
