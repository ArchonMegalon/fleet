# Converge shard startup state after hard-flagship restarts

Packet ID: support_packet_flagship_autofix_1775367048
Packet Kind: bugfix_followup
Status: accepted
Target Repo: fleet

## Action Request
- Treat this support packet as a bounded follow-up for the owning repo.
- Apply the repo-local product, docs, or policy change needed to close the issue described below.
- Update the smallest durable proof, regression check, or public-facing artifact that demonstrates the fix.

## Summary
Shard startup still dedupes against stale runtime state and does not guarantee fresh whole-project flagship shard convergence.

## Packet Context
- Reason: The supervisor launcher can still collapse shard startup onto duplicate stale fingerprints during hard-flagship restarts.
- Exit condition: All shard startup lanes derive fresh frontier fingerprints from current runtime/config state and emit fresh shard state under the hard flagship bar.
- Primary lane: ops
- Change class: type_b
- Release channel: 
- Head: 
- Platform: 
- Arch: 
- Install truth state: 
- Fixed version: 
- Fixed channel: 
- Fix confirmation: 
