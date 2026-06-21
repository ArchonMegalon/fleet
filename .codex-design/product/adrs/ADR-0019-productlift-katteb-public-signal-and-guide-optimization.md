# ADR-0019: ProductLift and Katteb as public signal and public-content projection lanes

## Status

Accepted.

## Context

Chummer has a generated public guide, public support and participation copy, a growing LTD stack, and a strict design-first truth model. Users still need visible feedback, voting, roadmap, changelog, and closeout paths. Public guide content also needs stronger readability, findability, and AI-search visibility without breaking canonical design truth.

ProductLift and Katteb fill those gaps only if they remain bounded helper surfaces.

## Decision

Use ProductLift as the public feedback, voting, roadmap-projection, changelog-projection, and voter-closeout lane.

Use Katteb as the public guide/content optimization and AI-search visibility lane.

Neither tool may own product truth. Accepted changes flow through Chummer-owned canon, Product Governor decisions, release evidence, Hub public surfaces, generated-guide exports, and closeout packets.

## Consequences

Positive:

- users can see and vote on public requests
- high-signal public ideas can become governed discovery packets
- voters can be notified when work ships
- public content can become more findable and readable
- Katteb can improve public content without hand-editing generated guide output

Negative:

- requires governance overhead
- creates public-roadmap drift risk
- creates content drift risk if Katteb output is accepted too casually
- requires moderation and support-misroute handling

## Guardrails

- ProductLift is not support.
- ProductLift is not canonical roadmap truth.
- ProductLift votes do not decide priority.
- ProductLift `planned` and `shipped` statuses require Chummer-owned evidence.
- Katteb cannot edit generated public guide output directly.
- Katteb cannot write rules, support, campaign, or availability truth.
- Katteb output requires source packets, review, and upstream source changes before publication.
- All shipped public claims require closeout evidence.

## Canonical files

- `PRODUCTLIFT_FEEDBACK_ROADMAP_BRIDGE.md`
- `KATTEB_PUBLIC_GUIDE_OPTIMIZATION_LANE.md`
- `PUBLIC_SIGNAL_TO_CANON_PIPELINE.md`
- `PUBLIC_FEEDBACK_AND_CONTENT_REGISTRY.yaml`
- `PUBLIC_FEEDBACK_TAXONOMY.yaml`
