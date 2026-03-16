#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shlex
import sys


JURY_TERMS = (
    "audit",
    "review",
    "second opinion",
    "critic",
    "escalat",
    "risk",
    "security",
    "migration",
    "public api",
    "contract",
)

CORE_TERMS = (
    "auth",
    "payment",
    "billing",
    "release",
    "protected branch",
    "schema migration",
    "breaking change",
    "cross repo",
    "cross-repo",
)

PATCH_TERMS = (
    "fix",
    "patch",
    "edit",
    "update",
    "rename",
    "refactor",
    "implement",
    "wire",
    "change",
    "test",
    "failing test",
    "bug",
)

EASY_TERMS = (
    "summarize",
    "summary",
    "draft",
    "outline",
    "rewrite",
    "inventory",
    "list",
    "status",
    "explain",
    "schema",
    "packet",
    "shape",
)


def _contains_any(haystack: str, terms: tuple[str, ...]) -> bool:
    return any(term in haystack for term in terms)


def _route(argv: list[str]) -> dict[str, str]:
    if not argv:
        return {
            "lane": "easy",
            "submode": "mcp",
            "reasoning_effort": "low",
            "reason": "interactive_or_first_pass",
        }

    haystack = " ".join(argv).strip().lower()
    if _contains_any(haystack, JURY_TERMS):
        return {
            "lane": "jury",
            "submode": "responses",
            "reasoning_effort": "medium",
            "reason": "audit_or_risk_signal",
        }
    if _contains_any(haystack, CORE_TERMS):
        return {
            "lane": "core",
            "submode": "responses",
            "reasoning_effort": "high",
            "reason": "high_risk_scope",
        }
    if _contains_any(haystack, PATCH_TERMS):
        return {
            "lane": "easy",
            "submode": "responses_fast",
            "reasoning_effort": "low",
            "reason": "bounded_patch_generation",
        }
    if _contains_any(haystack, EASY_TERMS):
        return {
            "lane": "easy",
            "submode": "mcp",
            "reasoning_effort": "low",
            "reason": "lightweight_exploration",
        }
    return {
        "lane": "easy",
        "submode": "mcp",
        "reasoning_effort": "low",
        "reason": "cheap_first_default",
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--shell", action="store_true")
    parser.add_argument("args", nargs=argparse.REMAINDER)
    ns = parser.parse_args(argv)
    routed = _route(ns.args)
    if ns.shell:
        for key, value in routed.items():
            print(f"CODEXEA_ROUTE_{key.upper()}={shlex.quote(value)}")
        return 0
    for key, value in routed.items():
        print(f"{key}={value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
