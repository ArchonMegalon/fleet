#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shlex
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path("/docker/fleet")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from admin.consistency import normalize_lanes_config, normalize_task_queue_item


ROUTING_CONFIG_PATH = ROOT / "config" / "routing.yaml"

DEFAULT_KEYWORDS: dict[str, tuple[str, ...]] = {
    "inspect_keywords": (
        "inspect",
        "investigate",
        "triage",
        "understand",
        "look into",
        "read",
        "analyze",
        "status",
        "inventory",
        "explain",
    ),
    "draft_keywords": (
        "draft",
        "summarize",
        "summary",
        "outline",
        "rewrite",
        "document",
        "docs",
        "backlog",
        "plan",
        "proposal",
        "packet",
        "shape",
    ),
    "micro_edit_keywords": (
        "rename",
        "typo",
        "comment",
        "small edit",
        "small fix",
        "one-line",
        "single-file",
        "tiny patch",
    ),
    "bounded_fix_keywords": (
        "fix",
        "patch",
        "edit",
        "update",
        "refactor",
        "implement",
        "wire",
        "change",
        "test",
        "failing test",
        "bug",
    ),
    "multi_file_impl_keywords": (
        "multi-file",
        "multi file",
        "integration",
        "workflow",
        "feature",
        "controller",
        "dashboard",
        "backend",
        "frontend",
        "across the repo",
        "cross-service",
    ),
    "cross_repo_contract_keywords": (
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
        "auth",
        "payment",
        "billing",
        "release",
        "protected branch",
        "schema migration",
        "breaking change",
        "cross repo",
        "cross-repo",
    ),
}

TASK_KEYS = (
    "difficulty",
    "risk_level",
    "branch_policy",
    "acceptance_level",
    "allowed_lanes",
    "required_reviewer_lane",
    "budget_class",
    "latency_class",
)


def _contains_any(haystack: str, terms: tuple[str, ...]) -> bool:
    return any(term in haystack for term in terms)


def _load_config() -> dict[str, Any]:
    loaded = yaml.safe_load(ROUTING_CONFIG_PATH.read_text(encoding="utf-8")) or {}
    return loaded if isinstance(loaded, dict) else {}


def _keyword_set(config: dict[str, Any], key: str) -> tuple[str, ...]:
    spider = config.get("spider") if isinstance(config.get("spider"), dict) else {}
    configured = spider.get(key)
    if isinstance(configured, (list, tuple)):
        values = tuple(str(item).strip().lower() for item in configured if str(item).strip())
        if values:
            return values
    return DEFAULT_KEYWORDS[key]


def _task_meta_from_text(config: dict[str, Any], text: str) -> dict[str, Any]:
    lowered = text.lower()
    item: dict[str, Any] = {"title": text}
    patch_like = _contains_any(
        lowered,
        _keyword_set(config, "bounded_fix_keywords") + _keyword_set(config, "micro_edit_keywords"),
    )

    if _contains_any(lowered, ("protected branch", "merge-ready", "merge ready")):
        item["branch_policy"] = "protected_branch"
        item["acceptance_level"] = "merge_ready"
    elif _contains_any(lowered, ("no merge", "docs only", "documentation only")):
        item["branch_policy"] = "no_merge"

    if _contains_any(lowered, ("high risk", "security", "migration", "billing", "auth", "payment")):
        item["risk_level"] = "high"
    elif _contains_any(lowered, ("medium risk", "coordination", "cross-service")):
        item["risk_level"] = "medium"
    else:
        item["risk_level"] = "low"

    if _contains_any(lowered, ("audit", "review", "jury", "second opinion")) and not patch_like:
        item["allowed_lanes"] = ["jury"]
        item["required_reviewer_lane"] = "jury"
    elif _contains_any(lowered, ("fix", "patch", "bug", "refactor", "implement", "wire", "test")):
        item["allowed_lanes"] = ["easy", "repair", "core"]
    else:
        item["allowed_lanes"] = ["easy", "repair", "core"]
    return item


def _classify_tier(config: dict[str, Any], text: str) -> str:
    lowered = text.lower()
    patch_like = _contains_any(lowered, _keyword_set(config, "bounded_fix_keywords"))
    if _contains_any(lowered, _keyword_set(config, "cross_repo_contract_keywords")) and not patch_like:
        return "cross_repo_contract"
    if _contains_any(lowered, _keyword_set(config, "inspect_keywords")) and not _contains_any(
        lowered, _keyword_set(config, "bounded_fix_keywords")
    ):
        return "inspect"
    if _contains_any(lowered, _keyword_set(config, "draft_keywords")) and not _contains_any(
        lowered, _keyword_set(config, "bounded_fix_keywords")
    ):
        return "draft"
    if _contains_any(lowered, _keyword_set(config, "micro_edit_keywords")):
        return "micro_edit"
    if _contains_any(lowered, _keyword_set(config, "bounded_fix_keywords")):
        return "bounded_fix"
    if _contains_any(lowered, _keyword_set(config, "multi_file_impl_keywords")):
        return "multi_file_impl"
    return "inspect"


def _route(argv: list[str]) -> dict[str, str]:
    config = _load_config()
    lanes = normalize_lanes_config(config.get("lanes"))
    spider = config.get("spider") if isinstance(config.get("spider"), dict) else {}
    default_lane = "easy"

    if not argv:
        lane_cfg = lanes.get(default_lane) or {}
        return {
            "lane": default_lane,
            "submode": "mcp",
            "reasoning_effort": "low",
            "reason": "interactive_or_first_pass",
            "task_class": "inspect",
            "runtime_model": str(lane_cfg.get("runtime_model") or ""),
            "provider_hint_order": ",".join(lane_cfg.get("provider_hint_order") or []),
        }

    text = " ".join(argv).strip()
    task_meta = normalize_task_queue_item(_task_meta_from_text(config, text), lanes=lanes)
    tier = _classify_tier(config, text)
    allowed_lanes = list(task_meta.get("allowed_lanes") or ["easy", "repair", "core"])
    difficulty = str(task_meta.get("difficulty") or "auto")
    risk_level = str(task_meta.get("risk_level") or "auto")
    branch_policy = str(task_meta.get("branch_policy") or "auto")
    acceptance_level = str(task_meta.get("acceptance_level") or "auto")
    requires_contract_authority = tier == "cross_repo_contract" or branch_policy == "protected_branch" or acceptance_level == "merge_ready"

    preferred_lane = allowed_lanes[0] if allowed_lanes else default_lane
    submode = "mcp"
    reason = "cheap_first_default"
    reasoning_effort = "low"

    if preferred_lane == "jury":
        submode = "responses_audit"
        reason = "audit_or_risk_signal"
        reasoning_effort = "medium"
    elif preferred_lane == "easy" and tier in {"bounded_fix", "micro_edit"} and "repair" in allowed_lanes:
        preferred_lane = "repair"
        submode = "responses_fast"
        reason = "bounded_patch_generation"
    if preferred_lane in {"easy", "repair"} and (
        tier in {"multi_file_impl", "cross_repo_contract"} or risk_level in {"medium", "high"} or requires_contract_authority
    ) and "core" in allowed_lanes:
        preferred_lane = "core"
        submode = "responses_hard"
        reason = "high_risk_scope"
        reasoning_effort = "high"
    elif preferred_lane == "easy":
        if tier in {"inspect", "draft"}:
            submode = "mcp"
            reason = "lightweight_exploration" if tier == "draft" else "interactive_or_first_pass"
            reasoning_effort = str(((spider.get("tier_preferences") or {}).get(tier) or {}).get("reasoning_effort") or "low")
        else:
            submode = "mcp"
            reason = "cheap_first_default"
    elif preferred_lane == "repair":
        submode = "responses_fast"
        reason = "bounded_patch_generation"
    elif preferred_lane == "core":
        submode = "responses_hard"
        reason = "high_risk_scope"
        reasoning_effort = "high"

    lane_cfg = lanes.get(preferred_lane) or {}
    return {
        "lane": preferred_lane,
        "submode": submode,
        "reasoning_effort": reasoning_effort,
        "reason": reason,
        "task_class": tier,
        "runtime_model": str(lane_cfg.get("runtime_model") or ""),
        "provider_hint_order": ",".join(lane_cfg.get("provider_hint_order") or []),
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
