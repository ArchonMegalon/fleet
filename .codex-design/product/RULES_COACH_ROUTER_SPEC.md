# Rules Coach Router Spec

## Route classes

- `support_question`
- `rules_calculation_question`
- `raw_rules_question`
- `private_campaign_question`
- `unsupported_question`

## Routing

- support questions may use the Answerly support adapter
- rules calculation questions stay Chummer-first and may use Answerly only as an optional humanizer after `RuleSafeAnswerPacket`
- raw sourcebook questions are refused or routed to verification
- private campaign questions never go to Answerly

## Fail closed

If the classifier is uncertain:

- `answerly_allowed: false`
- `fallback_required: true`
