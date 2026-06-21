# Katteb public guide optimization lane

## Status

Accepted design posture; implementation remains gated by approved source packets, Chummer-owned review, and upstream canon changes.

## Purpose

Katteb may audit, draft, optimize, and refresh public Chummer content for readability, SEO, AI-search visibility, and public onboarding clarity.

It must not become design truth, rules truth, support truth, or generated-guide authority.

## Golden rule

Katteb may propose improvements to generated public guide output, but accepted changes must flow upstream into `chummer6-design` or a Chummer-owned public-guide source registry before the guide is regenerated.

The generated public guide must never be hand-edited to accept Katteb output.

## Ownership

- `chummer6-hub` owns public content destinations and publication routes.
- `executive-assistant` owns Katteb source brief preparation, synthesis, redaction, and patch-proposal packaging.
- `chummer6-design` owns source truth, allowed claims, forbidden claims, and canonical copy changes.
- Product Governor or delegated content owner approves publication.

## Allowed uses

- Generated-guide readability audits.
- SEO and AI-search visibility suggestions.
- Brand-voice public article drafts.
- Public FAQ and guide copy improvement suggestions.
- Public release/support explainer articles.
- BLACK LEDGER, KARMA FORGE, Community Hub, Mobile Companion, and creator publishing explainers.
- Multilingual public-content draft assistance.
- Metadata, title, description, and content-gap suggestions.

## Forbidden uses

- Direct edits to generated guide files.
- Raw rules truth or invented Shadowrun mechanics.
- Support case replies.
- Crash dumps, private logs, private transcripts, account data, or raw ProductLift posts containing sensitive material.
- House-rule package generation.
- Runtime companion dialogue.
- Private campaign or world content without anonymization.
- Auto-published changelogs.
- Canonical design text without Chummer review.
- Claims that unshipped features are available.
- Claims of official licensing or endorsement unless true and approved.

## Required source packet

Every Katteb job must include:

```yaml
public_content_brief:
  id: string
  source_refs: []
  approved_source_summary: string
  allowed_claims: []
  forbidden_claims: []
  target_audience: string
  publication_target: string
  review_owner: string
  approval_state: draft | approved_source | reviewed | rejected
  privacy_ip_check: required
  canonical_source_links: []
```

Katteb may receive approved public source packets, redacted ProductLift cluster summaries, approved release notes, generated public guide pages, approved design summaries, approved media briefs, and public FAQ entries.

## Audit workflow

```text
Guide page underperforms or is confusing
  -> Katteb audit against approved source packet
  -> EA content packet
  -> design/hub review
  -> upstream canonical source edit
  -> public guide regenerated
  -> ProductLift/Katteb closeout if tied to a public request
```

## Target pages for first sprint

Initial Katteb content sprint:

1. What is Chummer 6?
2. Download and install Chummer 6.
3. How Chummer explains Shadowrun math.
4. How Chummer handles house rules.
5. What is KARMA FORGE?
6. What is BLACK LEDGER?
7. How to find and join open runs.
8. How GM scheduling and Discord/Teams handoff works.
9. How Table Pulse works without live surveillance.
10. How Chummer5a users can migrate to Chummer6.

Each article needs approved source refs, allowed and forbidden claims, reviewer, publication target, canonical source links, and product-status check.

## Review rule

No Katteb output may publish without human review and Product Governor or delegated content-owner approval.

Accepted Katteb recommendations become upstream patch proposals. Rejected recommendations are tracked with reasons so content drift and SEO pressure do not silently erode canon.

## Success criteria

The lane is working when public content becomes clearer and more findable while generated guide changes still come from `chummer6-design`, every Katteb-assisted page has source refs and review evidence, and no public page contains unsupported rules, support, campaign, or availability claims.
