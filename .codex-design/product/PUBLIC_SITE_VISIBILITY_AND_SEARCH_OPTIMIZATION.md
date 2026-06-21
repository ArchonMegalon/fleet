# Public site visibility and search optimization

## Status

Accepted design posture; implementation remains gated by Chummer-owned source patches, regeneration, and review.

## Purpose

ClickRank is the public site visibility, crawl-health, SEO, metadata, schema, internal-link, and AI-search audit lane for Chummer public-launch surfaces.

It fills the operational gap between product story, public content, and actual discoverability. It must not become copy truth, roadmap truth, release truth, support truth, rules truth, campaign truth, world truth, or generated-guide authority.

## Core rule

ClickRank may audit and recommend SEO, schema, metadata, internal-link, crawler-access, broken-link, and AI-search visibility improvements for Chummer public surfaces.

Accepted changes must be patched upstream into Chummer-owned source, then regenerated or republished.

ClickRank must not directly mutate generated guide truth, roadmap truth, release truth, support truth, rules truth, or unshipped product claims.

## Tool fit

ClickRank is strongest for:

- website audit findings
- crawler coverage and crawl-budget discipline
- Google Search Console keyword tracking
- broken links
- duplicate or missing tags
- title and meta-description coverage
- heading hierarchy
- image alt-text suggestions
- schema suggestions
- internal-link suggestions
- AI-search visibility checks across public search/answer surfaces

ClickRank is not the place to decide Chummer positioning, feature availability, roadmap status, install/update claims, or support promises.

## Plan posture

The current owned plan is AppSumo Tier 4:

```yaml
clickrank_plan:
  tier: AppSumo Tier 4
  websites: 8
  users: 4
  crawled_page_capacity: 5000
  crawl_interval: monthly
  operational_note: >
    Treat the crawled-page capacity as a scarce public-launch budget.
    Crawl curated durable public pages first; do not spend it on every
    generated, archive, internal, or duplicate page.
```

## Crawl scope

Initial curated crawl set:

- `/`
- `/downloads`
- `/help`
- `/feedback`
- `/roadmap`
- `/changelog`
- `/status`
- `/what-is-chummer`
- `/build`
- `/gm-tools`
- `/open-runs`
- `/community-hub`
- `/black-ledger`
- `/karma-forge`
- `/table-pulse`
- `/creator-publishing`
- `/from-chummer5a`

Then add only durable guide and article pages with public-launch value.

Do not crawl every generated path, archive page, machine output, internal proof page, or low-value duplicate.

## Allowed recommendations

Safe after Chummer review:

- title tags
- meta descriptions
- image alt text
- schema suggestions
- broken-link reports
- heading hierarchy suggestions
- internal-link suggestions
- crawl and indexability fixes
- duplicate title/meta cleanup

## Blocked without upstream review

ClickRank findings must not directly cause:

- changed roadmap status
- changed feature availability
- changed install/update/support claims
- edits to generated guide pages
- horizons described as shipped
- invented product promises
- invented rules explanations
- public claims that contradict release evidence

## Workflow

```text
ClickRank audit
  -> classify finding
  -> safe technical fix, content improvement, canon-sensitive claim, navigation issue, schema issue, or blocked item
  -> if content: Katteb drafts against source packet
  -> EA normalizes and packages
  -> Product Governor or delegated owner approves
  -> Hub/design source, public registry, metadata config, or article source packet is patched
  -> public site or guide regenerates
  -> ClickRank re-audit confirms visibility and crawl health
```

## Weekly pulse inputs

Track:

- unresolved SEO issues
- unresolved AI-search issues
- pages with stale public claims
- high-impression / low-click pages
- pages with support-misroute traffic
- ProductLift idea pages that need better public content
- crawl budget consumed versus reserved
- broken links on public launch routes
- schema/title/meta coverage

## Success criteria

ClickRank is working when Chummer public pages are crawlable, metadata/schema/internal links are disciplined, AI-search visibility gaps are visible, stale public claims are caught before they become public-promise drift, and every accepted content or claim change lands upstream in Chummer-owned source before publication.
