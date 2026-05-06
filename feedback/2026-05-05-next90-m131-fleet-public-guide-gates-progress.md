# Next90 M131.5 Fleet Public Guide Gates

- Package: `next90-m131-fleet-verify-public-guide-regeneration-visibility-source-fresh`
- Frontier: `5694544514`
- Date: `2026-05-05`

Implemented a Fleet packet that verifies the public-guide source-first contract instead of trying to fix the guide repo directly. The packet now locks the M131 queue and registry row, checks the growth/visibility, export-manifest, guide-policy, ClickRank, ProductLift, and Katteb canon markers, and then runs the live `verify_chummer6_guide_surface.py` and `materialize_chummer6_flagship_queue.py --json` gates as runtime evidence.

Audit refinements:

- package health stays `pass` when the live guide gates are blocked, so Fleet can ship the monitor even while Chummer6 still needs content fixes
- live guide-root mismatches fail closed instead of silently accepting queue output from the wrong repo
- guide freshness is measured from the real guide repo HEAD and warns when the repo is dirty, so stale or pre-commit guide truth is visible in the packet
- the live append-style queue overlays are now accepted directly, so canonical alignment stays green instead of false-failing on missing Fleet or design queue rows

Live result after materialization:

- packet status: `pass`
- public-guide gate status: `blocked`
- runtime blockers: missing `UPDATES/README.md` change-log section plus flagship image/story findings
- runtime warnings: current 1min burn floor is not met, and the guide repo has uncommitted paths
