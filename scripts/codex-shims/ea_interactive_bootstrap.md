Read `AGENTS.md` first.

Immediately print exactly one short line starting with `Trace:` that names the current lane (`easy`, `core`, or `jury`) and the next work unit.

Then continue the next obvious unfinished implementation slice without stopping at summaries, audits, or “If you want, I can …” offers.

Default behavior:
- start in `easy`
- use EA MCP tools first
- use `ea.context_pack` when useful
- use Gemini-backed EA work for cheap exploration and shaping
- use `ea-coder-fast` for bounded patch writing before any hard escalation
- escalate to `jury` only for repeated failure, contradiction, security risk, migration risk, or audit-grade review

While working, emit another one-line `Trace:` update every 20-45 seconds, on lane changes, and on blockers.
