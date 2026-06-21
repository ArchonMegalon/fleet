# Review guidelines
- Flag campaign/session truth, approval policy, or delivery policy leaking into `chummer6-media-factory` as P1.
- Flag world-state, mission-market, newsreel, or opposition-packet semantics being redefined in media DTOs instead of consumed from `Chummer.World.Contracts` as P1.
- Flag provider SDK types, storage implementation details, or UI contracts leaking into `Chummer.Media.Contracts` as P1.
- Flag direct provider calls from client repos or `hub` once media-factory owns the render path as P1.
- Flag app-host filesystem blob storage, missing retention state, or non-idempotent heavy render execution as P1.
- Flag document rendering nondeterminism or missing portrait/video lineage preservation as P1.
