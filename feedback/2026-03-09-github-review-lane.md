# Fleet Change Guide - GitHub Review Lane

Date: 2026-03-09
Audience: fleet maintainers and worker agents
Status: applied direction

## Summary

- move review work from local `codex exec` review into GitHub-backed Codex PR review
- gate queue advance on GitHub review when project review is enabled
- treat local review as fallback-only
- surface PR, review status, and review findings in admin and dashboard

## Required operator behavior

- request review with `@codex review`
- use focused suffixes only as refinements, not as the trigger mechanism
- do not treat `review my code` as the billing switch

## Fleet expectations

- coding runs stay local
- review runs become GitHub-native
- review findings are ingested into fleet feedback and next-task handling
