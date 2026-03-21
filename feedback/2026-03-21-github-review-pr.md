# GitHub Codex Review

PR: local://fleet

Findings:
- [high] runtime.ea.env [state] state-secret-token-in-runtime-ea-env
`EA_MCP_API_TOKEN` changed from empty to a concrete bearer token value in a tracked repository file.; The file header states non-secret defaults, so storing a live token here creates credential exposure and state leakage risk.
Expected fix: Remove the token from tracked files, rotate/revoke the exposed credential, and keep secrets only in ignored runtime-local env sources.
- [high] config/projects/fleet.yaml [review] review-chatgpt-policy-boundary-broadened
`account_policy.allow_chatgpt_accounts` changed from `false` to `true`.; `acct-chatgpt-archon` was added to general preferred accounts and `worker_topology.core_rescue`, making ChatGPT eligibility broad at project routing level rather than isolated to participant/premium-specific policy boundaries.
Expected fix: Revert broad account-policy enablement and keep ChatGPT usage constrained to explicit premium/participant-burst boundaries (or another narrowly scoped, policy-explicit lane), consistent with review guardrails.
