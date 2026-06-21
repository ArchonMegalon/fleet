# Answerly RuleSafe Boundary

Chummer owns truth.
Answerly may only receive Chummer-owned safe packets.

## Never send

- raw sourcebook text
- copied sourcebook tables
- private campaign state
- GM-only state
- account email
- support case body
- secrets

## Allowed input to Answerly

- `RuleSafeAnswerPacket.safe_summary`
- `RuleSafeAnswerPacket.calculation_steps`
- package and receipt ids
- public-doc anchors without embedded quoted book text

## Fail-closed rule

If routing is uncertain or sourcebook risk is present, Answerly is not allowed and Chummer falls back to first-party help or a verification ticket.
