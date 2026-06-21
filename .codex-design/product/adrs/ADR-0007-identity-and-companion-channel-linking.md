# ADR-0007: Identity and Companion Channel Linking Stay Hub-Owned

Date: 2026-03-24

Status: accepted

## Context

- Chummer now has explicit canon for email hygiene, social bootstrap, linked identities, linked channels, and the rule that EA remains the orchestrator brain behind governed companion channels.
- These decisions affect public auth posture, account surfaces, and future official channel adapters.
- The policy had become important enough that it needed more than prose canon.

## Decision

- `chummer6-hub` owns account identity, linked-identity policy, linked-channel policy, permissions, and entitlement checks for companion channels.
- First-wave public auth stays boring: email-first, browser-session-hosted, with Google as the next allowed mainstream adapter when real credentials exist.
- Provider names belong on auth and account surfaces, not on the landing hero or generic product pitch.
- EA may operate the orchestrator brain behind official companion channels, but it does not become the identity or policy owner.
- User-provided Telegram bots remain outside the default first-wave UI until canon changes and real adapters exist.

## Consequences

- Identity drift cannot be justified by downstream channel or helper convenience.
- Public and signed-in auth surfaces must agree on provider posture and fallback language.
- Companion-channel work now has a stable decision record instead of relying only on route and account prose.
