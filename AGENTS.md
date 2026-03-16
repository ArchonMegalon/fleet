# Agent Instructions

## Skills

A skill is a set of local instructions to follow that is stored in a `SKILL.md`
file. Below is the list of skills that can be used. Each entry includes a name,
description, and file path so you can open the source for full instructions when
using a specific skill.

### Available skills

- `skill-creator`: Guide for creating effective skills. Use when users want to
  create a new skill (or update an existing skill) that extends Codex's
  capabilities with specialized knowledge, workflows, or tool integrations.
  (file: `/home/tibor/.codex/skills/.system/skill-creator/SKILL.md`)
- `skill-installer`: Install Codex skills into `$CODEX_HOME/skills` from a
  curated list or a GitHub repo path. Use when a user asks to list installable
  skills, install a curated skill, or install a skill from another repo
  (including private repos).
  (file: `/home/tibor/.codex/skills/.system/skill-installer/SKILL.md`)

### How to use skills

- Discovery: The list above is the skills available in this session (name +
  description + file path). Skill bodies live on disk at the listed paths.
- Trigger rules: If the user names a skill (with `$SkillName` or plain text) OR
  the task clearly matches a skill's description shown above, you must use that
  skill for that turn. Multiple mentions mean use them all. Do not carry skills
  across turns unless re-mentioned.
- Missing/blocked: If a named skill isn't in the list or the path can't be read,
  say so briefly and continue with the best fallback.
- How to use a skill (progressive disclosure):
  1. After deciding to use a skill, open its `SKILL.md`. Read only enough to
     follow the workflow.
  2. When `SKILL.md` references relative paths (e.g., `scripts/foo.py`), resolve
     them relative to the skill directory listed above first, and only consider
     other paths if needed.
  3. If `SKILL.md` points to extra folders such as `references/`, load only the
     specific files needed for the request; don't bulk-load everything.
  4. If `scripts/` exist, prefer running or patching them instead of retyping
     large code blocks.
  5. If `assets/` or templates exist, reuse them instead of recreating from
     scratch.
- Coordination and sequencing:
  - If multiple skills apply, choose the minimal set that covers the request and
    state the order you'll use them.
  - Announce which skill(s) you're using and why (one short line). If you skip
    an obvious skill, say why.
- Context hygiene:
  - Keep context small: summarize long sections instead of pasting them; only
    load extra files when needed.
  - Avoid deep reference-chasing: prefer opening only files directly linked from
    `SKILL.md` unless you're blocked.
  - When variants exist (frameworks, providers, domains), pick only the relevant
    reference file(s) and note that choice.
- Safety and fallback: If a skill can't be applied cleanly (missing files,
  unclear instructions), state the issue, pick the next-best approach, and
  continue.

## Environment Context

```xml
<environment_context>
  <cwd>/docker/fleet</cwd>
  <shell>bash</shell>
  <current_date>2026-03-14</current_date>
  <timezone>Europe/Vienna</timezone>
</environment_context>
```

## Codexea Defaults

- Scope default:
  - Unless the user explicitly narrows scope, treat requests as asking for the broadest reasonable end-to-end completion.
  - Do not stop at the first acceptable implementation boundary if adjacent requested work, cleanup, follow-through wiring, or feedback-driven backlog reconciliation still remains.
  - When in doubt, continue to the largest coherent scope that can be finished safely in the current turn.
  - Do not stop while you can still identify any meaningful remaining work that is implied by the request, the feedback, the changed code, or the verification results.
  - Only stop by default when you do not see anything left to do.
- Bare `codexea` runs should stay on the cheap `easy` lane unless the user explicitly asks for `core`, `jury`, or `survival`.
- Prefer EA MCP tools for grunt work and low-risk backlog clearing before using EA Responses hard lanes.
- In `easy`, prefer a 2-step flow: MCP Gemini for exploration/context, then `ea-coder-fast` for bounded patch synthesis before any hard escalation.
- When you discover real missing work, continue with that slice immediately instead of stopping at a summary.
- Do not end with “If you want, I can …” when the next unfinished slice is already obvious from the repo state.
- Classify work explicitly:
  - `easy`: docs, summaries, rote config edits, narrow refactors, bounded single-file work.
  - `core`: multi-file implementation, logic-heavy fixes, cross-contract work, or behavior-risky changes.
  - `jury`: repeated failure, contradictory evidence, security-sensitive work, public API changes, migration risk, or unresolved ambiguity after two attempts.
- For difficult ambiguity or audit-grade review, escalate to the ChatPlayground audit path only when needed.
- While working, emit short one-line `Trace:` updates before each meaningful work unit and again if you have been quiet for roughly 20-45 seconds.
- If the lane changes, emit a fresh one-line `Trace:` update that names the new lane and the trigger.
- If the user asks what you are doing, answer immediately in one or two plain sentences before continuing.
