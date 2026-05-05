#!/usr/bin/env python3
from __future__ import annotations

import argparse
import collections
import datetime as dt
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List

import yaml


ROOT = Path("/docker/fleet")
PUBLISHED = ROOT / ".codex-studio" / "published"
PRODUCT_MIRROR = Path("/docker/chummercomplete/chummer-design/products/chummer")

PACKAGE_ID = "next90-m125-fleet-add-signal-cluster-to-queue-synthesis-for-repeated-produ"
FRONTIER_ID = 5150581210
MILESTONE_ID = 125
WORK_TASK_ID = "125.3"
WAVE_ID = "W17"
QUEUE_TITLE = "Add signal-cluster-to-queue synthesis for repeated ProductLift, Katteb, ClickRank, support, and public-guide findings."
QUEUE_TASK = QUEUE_TITLE
WORK_TASK_TITLE = QUEUE_TITLE
WORK_TASK_DEPENDENCIES = [106, 111, 120]
OWNED_SURFACES = ["add_signal_cluster_to_queue:fleet"]
ALLOWED_PATHS = ["scripts", "tests", ".codex-studio", "feedback"]

DEFAULT_OUTPUT = PUBLISHED / "NEXT90_M125_FLEET_SIGNAL_CLUSTER_QUEUE.generated.json"
DEFAULT_MARKDOWN = PUBLISHED / "NEXT90_M125_FLEET_SIGNAL_CLUSTER_QUEUE.generated.md"
DEFAULT_SIGNAL_SOURCE_OUTPUT = PUBLISHED / "NEXT90_M125_FLEET_SIGNAL_CLUSTER_QUEUE.signal_source.generated.json"

SUCCESSOR_REGISTRY = PRODUCT_MIRROR / "NEXT_90_DAY_PRODUCT_ADVANCE_REGISTRY.yaml"
QUEUE_STAGING = PUBLISHED / "NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
DESIGN_QUEUE_STAGING = PRODUCT_MIRROR / "NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
PUBLIC_SIGNAL_TO_CANON_PIPELINE = PRODUCT_MIRROR / "PUBLIC_SIGNAL_TO_CANON_PIPELINE.md"
FEEDBACK_AND_SIGNAL_OODA_LOOP = PRODUCT_MIRROR / "FEEDBACK_AND_SIGNAL_OODA_LOOP.md"
PRODUCTLIFT_BRIDGE = PRODUCT_MIRROR / "PRODUCTLIFT_FEEDBACK_ROADMAP_BRIDGE.md"
KATTEB_LANE = PRODUCT_MIRROR / "KATTEB_PUBLIC_GUIDE_OPTIMIZATION_LANE.md"
CLICKRANK_LANE = PRODUCT_MIRROR / "PUBLIC_SITE_VISIBILITY_AND_SEARCH_OPTIMIZATION.md"
WEEKLY_PRODUCT_PULSE = PUBLISHED / "WEEKLY_PRODUCT_PULSE.generated.json"
SUPPORT_CASE_PACKETS = PUBLISHED / "SUPPORT_CASE_PACKETS.generated.json"

REQUIRED_PIPELINE_MARKERS = {
    "core_rule": "## Core rule",
    "decision_classes": "## Decision classes",
    "closeout_requirements": "## Closeout requirements",
    "anti_patterns": "## Anti-patterns",
    "productlift_flow": "ProductLift / Katteb / users",
}
REQUIRED_OODA_MARKERS = {
    "fleet_clustering": "### Fleet clustering",
    "signal_packet_rule": "### Signal packet rule",
    "packet_to_action_rule": "### Packet-to-action rule",
    "forbidden_shortcuts": "## Forbidden shortcuts",
}
REQUIRED_PRODUCTLIFT_MARKERS = {
    "weekly_digest": "## Weekly digest",
    "support_misroutes": "## Support misroutes",
    "closeout_rule": "## Closeout rule",
    "status_mapping": "## Status mapping",
}
REQUIRED_KATTEB_MARKERS = {
    "required_source_packet": "## Required source packet",
    "audit_workflow": "## Audit workflow",
    "review_rule": "## Review rule",
}
REQUIRED_CLICKRANK_MARKERS = {
    "workflow": "## Workflow",
    "weekly_pulse_inputs": "## Weekly pulse inputs",
    "blocked_without_upstream_review": "## Blocked without upstream review",
}

REQUIRED_SIGNAL_FIELDS = (
    "source",
    "signal_family",
    "audience",
    "claim_sensitivity",
    "owner",
    "decision",
    "closeout_posture",
    "summary",
)
ROUTING_OUTCOMES = {
    "code fix",
    "docs/help fix",
    "queue/package fix",
    "support knowledge or closure fix",
    "policy update",
    "canon update",
    "release freeze or rollback",
    "defer or reject with explicit rationale",
}
REQUIRED_SOURCE_FAMILIES = ("ProductLift", "Katteb", "ClickRank", "support", "public-guide")
CLAIM_SENSITIVITY_RANK = {
    "public_copy": 1,
    "public_signal": 2,
    "public_promise_drift": 3,
    "canon_sensitive": 4,
    "private_support": 5,
}
SOURCE_FAMILY_ALIASES = {
    "productlift": "ProductLift",
    "katteb": "Katteb",
    "clickrank": "ClickRank",
    "support": "support",
    "public-guide": "public-guide",
    "public guide": "public-guide",
    "guide": "public-guide",
}


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Materialize the Fleet M125 signal-cluster queue synthesis packet.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--markdown-output", default=str(DEFAULT_MARKDOWN))
    parser.add_argument("--successor-registry", default=str(SUCCESSOR_REGISTRY))
    parser.add_argument("--queue-staging", default=str(QUEUE_STAGING))
    parser.add_argument("--design-queue-staging", default=str(DESIGN_QUEUE_STAGING))
    parser.add_argument("--public-signal-pipeline", default=str(PUBLIC_SIGNAL_TO_CANON_PIPELINE))
    parser.add_argument("--feedback-ooda-loop", default=str(FEEDBACK_AND_SIGNAL_OODA_LOOP))
    parser.add_argument("--productlift-bridge", default=str(PRODUCTLIFT_BRIDGE))
    parser.add_argument("--katteb-lane", default=str(KATTEB_LANE))
    parser.add_argument("--clickrank-lane", default=str(CLICKRANK_LANE))
    parser.add_argument("--weekly-product-pulse", default=str(WEEKLY_PRODUCT_PULSE))
    parser.add_argument("--support-case-packets", default=str(SUPPORT_CASE_PACKETS))
    parser.add_argument("--signal-source", default="")
    parser.add_argument("--live-signal-source-output", default=str(DEFAULT_SIGNAL_SOURCE_OUTPUT))
    return parser.parse_args(argv)


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _normalize_text(value: Any) -> str:
    return str(value or "").strip()


def _normalize_list(values: Any) -> List[str]:
    if not isinstance(values, list):
        return []
    return [_normalize_text(value) for value in values if _normalize_text(value)]


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_yaml(path: Path) -> Dict[str, Any]:
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _sha256_file(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return ""


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve())
    except OSError:
        return str(path)


def _write_json_file(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _generated_marker(payload: Dict[str, Any]) -> str:
    for key in ("generated_at", "as_of", "mirrored_at"):
        if _normalize_text(payload.get(key)):
            return _normalize_text(payload.get(key))
    return ""


def _source_link(path: Path, payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "path": _display_path(path),
        "sha256": _sha256_file(path),
        "generated_at": _generated_marker(payload),
    }


def _find_queue_item(queue: Dict[str, Any], package_id: str) -> Dict[str, Any]:
    for row in queue.get("items") or []:
        if isinstance(row, dict) and _normalize_text(row.get("package_id")) == package_id:
            return dict(row)
    return {}


def _find_milestone(registry: Dict[str, Any], milestone_id: int) -> Dict[str, Any]:
    for row in registry.get("milestones") or []:
        if isinstance(row, dict) and int(row.get("id") or 0) == milestone_id:
            return dict(row)
    return {}


def _find_work_task(milestone: Dict[str, Any], work_task_id: str) -> Dict[str, Any]:
    for row in milestone.get("work_tasks") or []:
        if isinstance(row, dict) and _normalize_text(row.get("id")) == work_task_id:
            return dict(row)
    return {}


def _queue_alignment(
    queue_item: Dict[str, Any],
    design_queue_item: Dict[str, Any],
    work_task: Dict[str, Any],
    milestone: Dict[str, Any],
) -> Dict[str, Any]:
    issues: List[str] = []
    if not queue_item:
        issues.append("Fleet queue row is missing.")
    if not design_queue_item:
        issues.append("Design queue row is missing.")
    if not work_task:
        issues.append("Canonical registry work task is missing.")
    expected = {
        "title": QUEUE_TITLE,
        "task": QUEUE_TASK,
        "milestone_id": MILESTONE_ID,
        "work_task_id": WORK_TASK_ID,
        "repo": "fleet",
        "wave": WAVE_ID,
        "frontier_id": FRONTIER_ID,
    }
    for field, expected_value in expected.items():
        expected_text = _normalize_text(expected_value)
        if queue_item and _normalize_text(queue_item.get(field)) != expected_text:
            issues.append(f"Fleet queue {field} drifted.")
        if design_queue_item and _normalize_text(design_queue_item.get(field)) != expected_text:
            issues.append(f"Design queue {field} drifted.")
    if queue_item and _normalize_list(queue_item.get("allowed_paths")) != ALLOWED_PATHS:
        issues.append("Fleet queue allowed_paths drifted.")
    if design_queue_item and _normalize_list(design_queue_item.get("allowed_paths")) != ALLOWED_PATHS:
        issues.append("Design queue allowed_paths drifted.")
    if queue_item and _normalize_list(queue_item.get("owned_surfaces")) != OWNED_SURFACES:
        issues.append("Fleet queue owned_surfaces drifted.")
    if design_queue_item and _normalize_list(design_queue_item.get("owned_surfaces")) != OWNED_SURFACES:
        issues.append("Design queue owned_surfaces drifted.")
    if work_task:
        if _normalize_text(work_task.get("owner")) != "fleet":
            issues.append("Canonical registry work task owner drifted.")
        if _normalize_text(work_task.get("title")) != WORK_TASK_TITLE:
            issues.append("Canonical registry work task title drifted.")
    if milestone and [int(value) for value in milestone.get("dependencies") or []] != WORK_TASK_DEPENDENCIES:
        issues.append("Canonical registry milestone dependencies drifted from M125 requirement set.")
    return {
        "state": "pass" if not issues else "fail",
        "issues": issues,
        "fleet_queue_status": _normalize_text(queue_item.get("status")),
        "design_queue_status": _normalize_text(design_queue_item.get("status")),
        "registry_status": _normalize_text(milestone.get("status")),
        "work_task_status": _normalize_text(work_task.get("status")),
    }


def _canonical_marker_monitor(text: str, markers: Dict[str, str], *, label: str) -> Dict[str, Any]:
    checks = {name: marker in text for name, marker in markers.items()}
    issues = [f"{label} missing required marker: {name}" for name, present in checks.items() if not present]
    return {"state": "pass" if not issues else "fail", "checks": checks, "issues": issues}


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", _normalize_text(value).lower()).strip("_")
    return slug or "uncategorized_signal"


def _coerce_source_family(value: Any) -> str:
    normalized = _normalize_text(value).lower()
    return SOURCE_FAMILY_ALIASES.get(normalized, _normalize_text(value))


def _infer_source_families(summary: str, source_paths: Iterable[str]) -> List[str]:
    families: List[str] = []
    haystack = " ".join([summary, *list(source_paths)]).lower()
    if "productlift" in haystack or "feedback" in haystack or "roadmap" in haystack or "changelog" in haystack:
        families.append("ProductLift")
    if "katteb" in haystack or "copy" in haystack or "content" in haystack or "article" in haystack:
        families.append("Katteb")
    if "clickrank" in haystack or "seo" in haystack or "crawl" in haystack or "visibility" in haystack or "search" in haystack:
        families.append("ClickRank")
    if "support" in haystack or "help" in haystack or "crash" in haystack or "install" in haystack or "status" in haystack:
        families.append("support")
    if "guide" in haystack or "publication" in haystack or "faq" in haystack or "public" in haystack:
        families.append("public-guide")
    return sorted(dict.fromkeys(families))


def _infer_signal_family(summary: str, source_families: Iterable[str]) -> str:
    families = {str(value) for value in source_families}
    lowered = summary.lower()
    if "crash" in lowered or "install" in lowered or "support" in lowered or "help" in lowered:
        return "public issue"
    if "feature" in lowered or "demand" in lowered or "roadmap" in lowered:
        return "lightweight feedback"
    if "visibility" in lowered or "search" in lowered or "crawl" in lowered:
        return "public-promise drift"
    if "public-guide" in families or "Katteb" in families:
        return "lightweight feedback"
    return "public issue"


def _infer_claim_sensitivity(summary: str, source_families: Iterable[str]) -> str:
    lowered = summary.lower()
    families = {str(value) for value in source_families}
    if "support" in families or "install" in lowered or "account" in lowered:
        return "private_support"
    if "release" in lowered or "promise" in lowered or "shipped" in lowered or "availability" in lowered:
        return "public_promise_drift"
    if "guide" in lowered or "katteb" in lowered or "clickrank" in lowered or "copy" in lowered or "visibility" in lowered:
        return "public_copy"
    return "public_signal"


def _infer_routing_outcome(summary: str, source_families: Iterable[str]) -> str:
    lowered = summary.lower()
    families = {str(value) for value in source_families}
    if "crash" in lowered or "account" in lowered or "private" in lowered or "spoiler" in lowered:
        return "support knowledge or closure fix"
    if "guide" in lowered or "copy" in lowered or "content" in lowered or "publication" in lowered:
        return "docs/help fix"
    if "visibility" in lowered or "search" in lowered or "crawl" in lowered:
        return "docs/help fix"
    if "support" in lowered or "help" in lowered or "install" in lowered:
        return "support knowledge or closure fix"
    if "feature" in lowered or "demand" in lowered or "roadmap" in lowered or "queue" in lowered or "horizon" in lowered:
        return "queue/package fix"
    if "release" in lowered or "promise" in lowered:
        return "policy update"
    if "public-guide" in families:
        return "docs/help fix"
    return "defer or reject with explicit rationale"


def _infer_candidate_owner_repo(route: str, source_families: Iterable[str]) -> str:
    families = {str(value) for value in source_families}
    if route == "support knowledge or closure fix":
        return "chummer6-hub"
    if route == "docs/help fix" and ("public-guide" in families or "Katteb" in families or "ClickRank" in families):
        return "chummer6-design"
    if route == "queue/package fix":
        return "fleet"
    if route in {"policy update", "canon update"}:
        return "chummer6-design"
    return "fleet"


def _normalize_signal_source_payload(payload: Any) -> Dict[str, Any]:
    if isinstance(payload, list):
        return {"items": payload, "count": len(payload)}
    if not isinstance(payload, dict):
        return {"items": [], "count": 0}
    items = payload.get("items")
    if items is None and isinstance(payload.get("packets"), list):
        items = payload.get("packets")
    if items is None:
        items = []
    if not isinstance(items, list):
        items = []
    normalized = dict(payload)
    normalized["items"] = items
    normalized["count"] = int(payload.get("count") or len(items))
    return normalized


def _derive_live_signal_source(weekly_pulse: Dict[str, Any], support_packets: Dict[str, Any]) -> Dict[str, Any]:
    items: List[Dict[str, Any]] = []
    for cluster in weekly_pulse.get("top_support_or_feedback_clusters") or []:
        if not isinstance(cluster, dict):
            continue
        cluster_id = _normalize_text(cluster.get("cluster_id"))
        summary = _normalize_text(cluster.get("summary"))
        source_paths = _normalize_list(cluster.get("source_paths"))
        source_families = _infer_source_families(summary, [cluster_id, *source_paths])
        items.append(
            {
                "packet_id": cluster_id or _slugify(summary),
                "source": "weekly_product_pulse",
                "source_families": source_families,
                "signal_family": _infer_signal_family(summary, source_families),
                "audience": "public",
                "claim_sensitivity": _infer_claim_sensitivity(summary, source_families),
                "owner": "fleet",
                "decision": "proposed_queue_candidate",
                "closeout_posture": "open",
                "decision_class": _infer_routing_outcome(summary, source_families),
                "cluster_key": cluster_id or _slugify(summary),
                "summary": summary,
                "source_refs": source_paths,
                "recurrence_count": max(2, len(source_paths)),
                "candidate_owner_repo": _infer_candidate_owner_repo(
                    _infer_routing_outcome(summary, source_families),
                    source_families,
                ),
            }
        )
    for packet in support_packets.get("packets") or []:
        if not isinstance(packet, dict):
            continue
        summary = _normalize_text(packet.get("summary") or packet.get("title") or packet.get("kind"))
        source_refs = _normalize_list(packet.get("source_items")) or [_normalize_text(packet.get("case_id") or packet.get("packet_id"))]
        source_families = ["support"]
        items.append(
            {
                "packet_id": _normalize_text(packet.get("packet_id") or packet.get("case_id") or packet.get("cluster_key")),
                "source": "support",
                "source_families": source_families,
                "signal_family": _normalize_text(packet.get("kind")) or "structured bug",
                "audience": "support_reporter",
                "claim_sensitivity": "private_support",
                "owner": _normalize_text(packet.get("target_repo")) or "chummer6-hub",
                "decision": _normalize_text(packet.get("status")) or "triage",
                "closeout_posture": "closed" if _normalize_text(packet.get("status")).lower() in {"resolved", "closed"} else "open",
                "decision_class": _infer_routing_outcome(summary, source_families),
                "cluster_key": _normalize_text(packet.get("cluster_key")) or _slugify(summary),
                "summary": summary,
                "source_refs": source_refs,
                "recurrence_count": 1,
                "candidate_owner_repo": _normalize_text(packet.get("target_repo")) or "chummer6-hub",
            }
        )
    return {
        "generated_at": _utc_now(),
        "items": items,
        "count": len(items),
        "source_summary": {
            "weekly_pulse_cluster_count": len(weekly_pulse.get("top_support_or_feedback_clusters") or []),
            "support_packet_count": len(support_packets.get("packets") or []),
        },
    }


def _normalize_signal_items(signal_source: Dict[str, Any]) -> Dict[str, Any]:
    issues: List[str] = []
    normalized_items: List[Dict[str, Any]] = []
    for raw in signal_source.get("items") or []:
        if not isinstance(raw, dict):
            issues.append("Signal source contains a non-object row.")
            continue
        source = _normalize_text(raw.get("source"))
        source_families = _normalize_list(raw.get("source_families"))
        if not source_families and source:
            source_families = [source]
        source_families = sorted(dict.fromkeys(_coerce_source_family(value) for value in source_families if _coerce_source_family(value)))
        summary = _normalize_text(raw.get("summary") or raw.get("title"))
        decision_class = _normalize_text(raw.get("decision_class") or raw.get("routing_outcome") or raw.get("route"))
        item = {
            "packet_id": _normalize_text(raw.get("packet_id") or raw.get("id") or raw.get("cluster_key") or _slugify(summary)),
            "source": source,
            "source_families": source_families,
            "signal_family": _normalize_text(raw.get("signal_family")),
            "audience": _normalize_text(raw.get("audience")),
            "claim_sensitivity": _normalize_text(raw.get("claim_sensitivity")),
            "owner": _normalize_text(raw.get("owner")),
            "decision": _normalize_text(raw.get("decision")),
            "closeout_posture": _normalize_text(raw.get("closeout_posture")),
            "decision_class": decision_class,
            "cluster_key": _normalize_text(raw.get("cluster_key") or raw.get("theme") or _slugify(summary)),
            "summary": summary,
            "source_refs": _normalize_list(raw.get("source_refs") or raw.get("source_paths")),
            "recurrence_count": max(1, int(raw.get("recurrence_count") or 1)),
            "candidate_owner_repo": _normalize_text(raw.get("candidate_owner_repo")),
        }
        missing_fields = [field for field in REQUIRED_SIGNAL_FIELDS if not _normalize_text(item.get(field))]
        if missing_fields:
            issues.append(f"Signal packet `{item['packet_id']}` is missing required fields: {', '.join(missing_fields)}.")
        if decision_class and decision_class not in ROUTING_OUTCOMES:
            issues.append(f"Signal packet `{item['packet_id']}` has unknown decision_class `{decision_class}`.")
        normalized_items.append(item)
    return {
        "generated_at": _generated_marker(signal_source),
        "items": normalized_items,
        "count": len(normalized_items),
        "source_summary": dict(signal_source.get("source_summary") or {}),
        "issues": issues,
    }


def _dominant_claim_sensitivity(values: Iterable[str]) -> str:
    best = "public_signal"
    best_rank = -1
    for value in values:
        rank = CLAIM_SENSITIVITY_RANK.get(_normalize_text(value), 0)
        if rank > best_rank:
            best = _normalize_text(value)
            best_rank = rank
    return best


def _majority_value(values: Iterable[str], *, default: str) -> str:
    normalized = [_normalize_text(value) for value in values if _normalize_text(value)]
    if not normalized:
        return default
    counter = collections.Counter(normalized)
    return sorted(counter.items(), key=lambda row: (-row[1], row[0]))[0][0]


def _queue_candidate_title(cluster_key: str, route: str, source_families: Iterable[str]) -> str:
    source_label = "/".join(sorted(dict.fromkeys(str(value) for value in source_families))) or "public-signal"
    if route == "docs/help fix":
        return f"Synthesize {cluster_key} {source_label} signal cluster into one upstream public-guide/docs patch queue slice."
    if route == "support knowledge or closure fix":
        return f"Synthesize {cluster_key} {source_label} signal cluster into one support-closure routing queue slice."
    if route == "queue/package fix":
        return f"Synthesize {cluster_key} {source_label} signal cluster into one bounded implementation/discovery queue slice."
    if route == "policy update":
        return f"Synthesize {cluster_key} {source_label} signal cluster into one public-promise policy queue slice."
    return f"Keep {cluster_key} {source_label} signal cluster on watch until Product Governor routes one bounded queue slice."


def _signal_cluster_monitor(signal_items_payload: Dict[str, Any]) -> Dict[str, Any]:
    items = [dict(item) for item in signal_items_payload.get("items") or [] if isinstance(item, dict)]
    issues = list(signal_items_payload.get("issues") or [])
    source_family_counts: Dict[str, int] = collections.Counter()
    clusters: Dict[str, List[Dict[str, Any]]] = collections.defaultdict(list)
    for item in items:
        for family in item.get("source_families") or []:
            source_family_counts[str(family)] += 1
        clusters[_normalize_text(item.get("cluster_key")) or "uncategorized_signal"].append(item)
    missing_families = [family for family in REQUIRED_SOURCE_FAMILIES if family not in source_family_counts]
    warnings: List[str] = []
    if missing_families:
        warnings.append(
            "Live source coverage is missing "
            + ", ".join(missing_families)
            + " packet families; queue synthesis is running on partial public-signal feeds."
        )
    cluster_rows: List[Dict[str, Any]] = []
    queue_candidates: List[Dict[str, Any]] = []
    for cluster_key in sorted(clusters):
        cluster_items = clusters[cluster_key]
        total_recurrence = sum(max(1, int(item.get("recurrence_count") or 1)) for item in cluster_items)
        cluster_families = sorted(
            dict.fromkeys(
                family
                for item in cluster_items
                for family in (item.get("source_families") or [])
                if _normalize_text(family)
            )
        )
        route = _majority_value((item.get("decision_class") for item in cluster_items), default="defer or reject with explicit rationale")
        audience = _majority_value((item.get("audience") for item in cluster_items), default="public")
        claim_sensitivity = _dominant_claim_sensitivity(item.get("claim_sensitivity") for item in cluster_items)
        owner_repo = _majority_value(
            (item.get("candidate_owner_repo") or _infer_candidate_owner_repo(route, cluster_families) for item in cluster_items),
            default=_infer_candidate_owner_repo(route, cluster_families),
        )
        cluster_row = {
            "cluster_key": cluster_key,
            "packet_count": len(cluster_items),
            "repeated_signal_count": total_recurrence,
            "source_families": cluster_families,
            "routing_outcome": route,
            "audience": audience,
            "claim_sensitivity": claim_sensitivity,
            "candidate_owner_repo": owner_repo,
            "summary": cluster_items[0].get("summary") if cluster_items else "",
            "source_items": [
                {
                    "packet_id": item.get("packet_id"),
                    "source": item.get("source"),
                    "source_families": item.get("source_families"),
                    "summary": item.get("summary"),
                    "decision_class": item.get("decision_class"),
                    "source_refs": item.get("source_refs"),
                }
                for item in cluster_items
            ],
        }
        cluster_rows.append(cluster_row)
        if total_recurrence < 2:
            continue
        queue_candidates.append(
            {
                "candidate_id": f"m125_signal_{cluster_key}",
                "title": _queue_candidate_title(cluster_key, route, cluster_families),
                "proposal_state": "proposal_only",
                "routing_outcome": route,
                "candidate_owner_repo": owner_repo,
                "decision_authority": ["Product Governor", "chummer6-design"],
                "audience": audience,
                "claim_sensitivity": claim_sensitivity,
                "repeated_signal_count": total_recurrence,
                "source_family_count": len(cluster_families),
                "source_families": cluster_families,
                "source_items": cluster_row["source_items"],
                "bounded_scope": sorted(
                    dict.fromkeys(
                        ref
                        for item in cluster_items
                        for ref in (item.get("source_refs") or [])
                        if _normalize_text(ref)
                    )
                )[:8],
            }
        )
    if not queue_candidates:
        warnings.append("No repeated public-signal cluster is currently large enough to propose a bounded queue candidate.")
    return {
        "state": "pass" if not issues else "fail",
        "signal_item_count": len(items),
        "cluster_count": len(cluster_rows),
        "queue_candidate_count": len(queue_candidates),
        "source_family_counts": dict(sorted(source_family_counts.items())),
        "missing_source_families": missing_families,
        "source_summary": dict(signal_items_payload.get("source_summary") or {}),
        "clusters": cluster_rows,
        "queue_candidates": queue_candidates,
        "issues": issues,
        "warnings": warnings,
    }


def build_payload(
    *,
    registry_path: Path,
    queue_path: Path,
    design_queue_path: Path,
    public_signal_pipeline_path: Path,
    feedback_ooda_loop_path: Path,
    productlift_bridge_path: Path,
    katteb_lane_path: Path,
    clickrank_lane_path: Path,
    weekly_product_pulse_path: Path,
    support_case_packets_path: Path,
    signal_source_path: Path,
    signal_source_payload: Dict[str, Any],
    generated_at: str | None = None,
) -> Dict[str, Any]:
    generated_at = generated_at or _utc_now()
    registry = _read_yaml(registry_path)
    queue = _read_yaml(queue_path)
    design_queue = _read_yaml(design_queue_path)
    weekly_product_pulse = _read_json(weekly_product_pulse_path)
    support_case_packets = _read_json(support_case_packets_path)
    pipeline_text = _read_text(public_signal_pipeline_path)
    ooda_text = _read_text(feedback_ooda_loop_path)
    productlift_text = _read_text(productlift_bridge_path)
    katteb_text = _read_text(katteb_lane_path)
    clickrank_text = _read_text(clickrank_lane_path)

    milestone = _find_milestone(registry, MILESTONE_ID)
    work_task = _find_work_task(milestone, WORK_TASK_ID)
    queue_item = _find_queue_item(queue, PACKAGE_ID)
    design_queue_item = _find_queue_item(design_queue, PACKAGE_ID)

    canonical_alignment = _queue_alignment(queue_item, design_queue_item, work_task, milestone)
    pipeline_monitor = _canonical_marker_monitor(pipeline_text, REQUIRED_PIPELINE_MARKERS, label="Public signal pipeline canon")
    ooda_monitor = _canonical_marker_monitor(ooda_text, REQUIRED_OODA_MARKERS, label="Signal OODA canon")
    productlift_monitor = _canonical_marker_monitor(productlift_text, REQUIRED_PRODUCTLIFT_MARKERS, label="ProductLift bridge canon")
    katteb_monitor = _canonical_marker_monitor(katteb_text, REQUIRED_KATTEB_MARKERS, label="Katteb lane canon")
    clickrank_monitor = _canonical_marker_monitor(clickrank_text, REQUIRED_CLICKRANK_MARKERS, label="ClickRank lane canon")
    signal_cluster_monitor = _signal_cluster_monitor(signal_source_payload)

    blockers: List[str] = []
    for section_name, section in (
        ("canonical_alignment", canonical_alignment),
        ("pipeline_monitor", pipeline_monitor),
        ("ooda_monitor", ooda_monitor),
        ("productlift_monitor", productlift_monitor),
        ("katteb_monitor", katteb_monitor),
        ("clickrank_monitor", clickrank_monitor),
        ("signal_cluster_monitor", signal_cluster_monitor),
    ):
        for issue in section.get("issues") or []:
            blockers.append(f"{section_name}: {issue}")

    warnings: List[str] = []
    warnings.extend(signal_cluster_monitor.get("warnings") or [])
    if signal_cluster_monitor.get("queue_candidate_count", 0):
        warnings.append("Queue candidates remain proposal-only until Product Governor and chummer6-design approve canon and owner routing.")

    return {
        "contract_name": "fleet.next90_m125_signal_cluster_queue_synthesis",
        "generated_at": generated_at,
        "status": "pass" if not blockers else "blocked",
        "package_id": PACKAGE_ID,
        "frontier_id": FRONTIER_ID,
        "milestone_id": MILESTONE_ID,
        "work_task_id": WORK_TASK_ID,
        "wave": WAVE_ID,
        "queue_title": QUEUE_TITLE,
        "queue_task": QUEUE_TASK,
        "owned_surfaces": OWNED_SURFACES,
        "allowed_paths": ALLOWED_PATHS,
        "canonical_alignment": canonical_alignment,
        "canonical_monitors": {
            "public_signal_pipeline": pipeline_monitor,
            "feedback_ooda_loop": ooda_monitor,
            "productlift_bridge": productlift_monitor,
            "katteb_lane": katteb_monitor,
            "clickrank_lane": clickrank_monitor,
        },
        "queue_synthesis": signal_cluster_monitor,
        "package_closeout": {
            "state": "pass" if not blockers else "blocked",
            "blockers": blockers,
            "warnings": warnings,
        },
        "source_inputs": {
            "successor_registry": _source_link(registry_path, registry),
            "queue_staging": _source_link(queue_path, queue),
            "design_queue_staging": _source_link(design_queue_path, design_queue),
            "public_signal_pipeline": {
                "path": _display_path(public_signal_pipeline_path),
                "sha256": _sha256_file(public_signal_pipeline_path),
                "generated_at": "",
            },
            "feedback_ooda_loop": {
                "path": _display_path(feedback_ooda_loop_path),
                "sha256": _sha256_file(feedback_ooda_loop_path),
                "generated_at": "",
            },
            "productlift_bridge": {
                "path": _display_path(productlift_bridge_path),
                "sha256": _sha256_file(productlift_bridge_path),
                "generated_at": "",
            },
            "katteb_lane": {
                "path": _display_path(katteb_lane_path),
                "sha256": _sha256_file(katteb_lane_path),
                "generated_at": "",
            },
            "clickrank_lane": {
                "path": _display_path(clickrank_lane_path),
                "sha256": _sha256_file(clickrank_lane_path),
                "generated_at": "",
            },
            "weekly_product_pulse": _source_link(weekly_product_pulse_path, weekly_product_pulse),
            "support_case_packets": _source_link(support_case_packets_path, support_case_packets),
            "signal_source": _source_link(signal_source_path, signal_source_payload),
        },
    }


def render_markdown(payload: Dict[str, Any]) -> str:
    queue_synthesis = dict(payload.get("queue_synthesis") or {})
    closeout = dict(payload.get("package_closeout") or {})
    lines = [
        "# Fleet M125 signal-cluster queue synthesis",
        "",
        f"- status: {payload.get('status')}",
        f"- package_id: {payload.get('package_id')}",
        f"- frontier_id: {payload.get('frontier_id')}",
        f"- generated_at: {payload.get('generated_at')}",
        "",
        "## Queue synthesis",
        f"- signal items: {queue_synthesis.get('signal_item_count', 0)}",
        f"- clusters: {queue_synthesis.get('cluster_count', 0)}",
        f"- queue candidates: {queue_synthesis.get('queue_candidate_count', 0)}",
        f"- missing source families: {', '.join(queue_synthesis.get('missing_source_families') or []) or 'none'}",
        "",
        "## Candidate titles",
    ]
    for candidate in queue_synthesis.get("queue_candidates") or []:
        lines.append(f"- {candidate.get('title')}")
    lines.extend(["", "## Package closeout", f"- state: {closeout.get('state') or 'blocked'}"])
    blockers = list(closeout.get("blockers") or [])
    warnings = list(closeout.get("warnings") or [])
    if blockers:
        lines.append("- blockers:")
        lines.extend([f"  - {item}" for item in blockers])
    if warnings:
        lines.append("- warnings:")
        lines.extend([f"  - {item}" for item in warnings])
    return "\n".join(lines) + "\n"


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)
    signal_source_path = Path(args.signal_source).resolve() if _normalize_text(args.signal_source) else None
    if signal_source_path is not None:
        signal_source_payload = _normalize_signal_source_payload(_read_json(signal_source_path))
    else:
        weekly_product_pulse = _read_json(Path(args.weekly_product_pulse).resolve())
        support_case_packets = _read_json(Path(args.support_case_packets).resolve())
        signal_source_payload = _derive_live_signal_source(weekly_product_pulse, support_case_packets)
        signal_source_path = Path(args.live_signal_source_output).resolve()
        _write_json_file(signal_source_path, signal_source_payload)
    normalized_signal_source = _normalize_signal_items(signal_source_payload)
    if not _generated_marker(normalized_signal_source):
        normalized_signal_source["generated_at"] = _utc_now()
        _write_json_file(signal_source_path, normalized_signal_source)
    payload = build_payload(
        registry_path=Path(args.successor_registry).resolve(),
        queue_path=Path(args.queue_staging).resolve(),
        design_queue_path=Path(args.design_queue_staging).resolve(),
        public_signal_pipeline_path=Path(args.public_signal_pipeline).resolve(),
        feedback_ooda_loop_path=Path(args.feedback_ooda_loop).resolve(),
        productlift_bridge_path=Path(args.productlift_bridge).resolve(),
        katteb_lane_path=Path(args.katteb_lane).resolve(),
        clickrank_lane_path=Path(args.clickrank_lane).resolve(),
        weekly_product_pulse_path=Path(args.weekly_product_pulse).resolve(),
        support_case_packets_path=Path(args.support_case_packets).resolve(),
        signal_source_path=signal_source_path,
        signal_source_payload=normalized_signal_source,
    )
    output_path = Path(args.output).resolve()
    markdown_path = Path(args.markdown_output).resolve()
    _write_json_file(output_path, payload)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"status": payload["status"], "artifact": str(output_path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
