# Black Ledger Newsroom Editorial Policy

## Editorial authority

Hub owns newsroom editorial truth.

Media Factory may render only from approved `NewsroomEpisode` and `NewsroomSegment` packets.

Executive Assistant may assist with headlines, summaries, and rewrites, but it cannot invent truth.

## Truth layers

### Receipt-backed

The line is supported by a first-party receipt.

### Public-safe reconstruction

The visual is generated from public-safe facts.

### Illustrative B-roll

The visual establishes mood or category.

### Editorial graphic

Charts, maps, heat rails, lower thirds, and geoscape overlays.

## Required source labels

Every segment must internally identify:

```yaml
source_receipts:
visual_truth:
public_safety_status:
dramatization_status:
```

## Public disclosure

On the watch page:

```text
Some visuals are public-safe reconstructions generated from Chummer receipts. Private table details stay private.
```

## Forbidden editorial behavior

Do not:
- fabricate actual product readiness;
- imply private campaign facts are public;
- quote sourcebooks;
- name official lore/corp entities unless explicitly allowed by public-lore policy;
- use real-world public figure likenesses;
- shame players;
- turn news into moderation truth.
