# Campaign cold-open and mission-briefing policy

## Purpose

This file makes campaign cold-open and mission-briefing artifacts first-class campaign OS promises without turning rendered media into campaign truth.

The point is not "more media."
The point is that Chummer should be able to welcome a player back into a campaign, or prepare the table for the next run, with the same discipline it uses for rules, support, and publication truth.

## Product promise

`campaign_cold_open` and `mission_briefing` are first-class campaign workspace outputs.

That means:

- campaign home may launch them directly on claimed desktop and mobile shells
- they are allowed to feel premium and polished
- they must stay downstream of approved campaign primer packs, mission packs, publication refs, and audience rules
- they must never become a shortcut around campaign authority, locale safety, or spoiler boundaries

These artifacts are part of the campaign OS promise because they help the table answer:

- what campaign am I joining or returning to
- what matters before the next session
- what is safe for me to know right now
- what should I open next if I need more detail

## Artifact families

### Campaign cold-open

The cold-open is the welcome-back or join-the-campaign moment.

It should compile from an approved campaign primer pack and may ship as:

- a short video or narrated artifact
- a preview card
- a primer packet
- a localized text fallback

The cold-open is the short front door.
The primer packet is the inspectable sibling.

### Mission briefing

The mission briefing is the next-run orientation moment.

It should compile from an approved mission pack and may ship as:

- a short video or narrated artifact
- a preview card
- a mission packet
- a localized text fallback

The mission briefing is allowed to feel dramatic.
It is not allowed to invent facts, reveal the wrong spoiler class, or outrun GM-approved mission truth.

## First-class but bounded

These artifacts are first-class campaign OS promises only when all of the following remain true:

- the launch surface shows them as campaign artifacts, not as random media cargo
- every artifact points back to the approved primer pack or mission pack it came from
- every artifact declares audience class, locale, and spoiler posture
- every artifact has an inspectable sibling packet or text path when dense detail matters
- the product can fall back cleanly when the preferred media lane is unavailable

If those rules are missing, the artifact is only marketing gloss and must not be treated as campaign truth.

## Audience classes

Device role is not audience authority.
Audience authority comes from campaign role, publication state, and approved artifact classification.

The required campaign artifact audience classes for this lane are:

- `campaign_joiner`: safe for a newly invited or newly returning player who needs campaign context
- `player_safe`: safe for any rostered player on the current campaign surface
- `observer_safe`: safe for read-mostly observer or presentation surfaces when explicitly enabled
- `gm_only`: contains planning or spoiler detail that must stay off player and observer surfaces

The default audience posture is conservative:

- cold-open launches default to `campaign_joiner` or `player_safe`
- mission briefing launches default to `player_safe`
- `gm_only` variants require explicit GM or organizer authority and must never auto-open on player-safe surfaces

## Spoiler rule

Campaign media may only summarize what the approved source pack marks as visible for that audience class.

Required spoiler discipline:

- `gm_only` facts must never appear in `campaign_joiner`, `player_safe`, or `observer_safe` variants
- if a mission has both player-safe and GM-only briefing variants, the product must label them distinctly and default to the safer one
- preview cards and notifications must inherit the same audience and spoiler class as the parent artifact
- locale fallback must not widen spoiler scope

When the product cannot satisfy the requested audience-safe variant, it must fail closed to a safer sibling or to no launch at all.

## Locale rules

Campaign cold-open and mission-briefing artifacts use the product shipping locale set from `LOCALIZATION_AND_LANGUAGE_SYSTEM.md`.

The locale chain is:

1. requested user locale when supported and approved for the artifact family
2. campaign default locale when the requested locale is unavailable
3. `en-US` as the deterministic final fallback

Locale handling rules:

- captions, packet text, preview copy, and launch labels must resolve through the same locale chain
- a localized voice track may ship only when captions and visible sibling copy for that locale also exist
- when localized media is unavailable, Chummer must prefer a localized packet or text fallback over a silent locale mismatch
- mixed-locale launch bundles must be explicit, never accidental

## Launch contract

The first-class launch surfaces for this lane are:

- signed-in home when a campaign or run needs attention
- campaign workspace publication shelf
- claimed desktop campaign home
- mobile or travel campaign home

Those surfaces must show:

- artifact title and family
- audience class
- locale
- source pack or publication ref
- the next inspectable sibling action

## Non-goals

This file does not:

- make video the source of campaign truth
- allow public teaser logic to reuse private campaign variants
- replace runsite orientation, recap, or creator promo policy
- permit locale fallback to hide spoiler mistakes
