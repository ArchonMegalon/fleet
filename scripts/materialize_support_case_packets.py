#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List

from materialize_compile_manifest import repo_root_for_published_path, write_compile_manifest


DEFAULT_OUT_PATH = Path("/docker/fleet/.codex-studio/published/SUPPORT_CASE_PACKETS.generated.json")


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Materialize Fleet support-case decision packets from Hub support-case truth.",
    )
    parser.add_argument(
        "--source",
        required=True,
        help="JSON source path or URL for support cases. Accepts a list or a {items:[...]} payload.",
    )
    parser.add_argument(
        "--out",
        default=str(DEFAULT_OUT_PATH),
        help="output path for SUPPORT_CASE_PACKETS.generated.json",
    )
    return parser.parse_args(argv or sys.argv[1:])


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_json_source(source: str) -> tuple[Dict[str, Any], str]:
    raw = str(source or "").strip()
    if not raw:
        raise SystemExit("support-case source is required")
    if raw.startswith(("http://", "https://")):
        try:
            with urllib.request.urlopen(raw) as response:
                data = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, json.JSONDecodeError) as exc:
            raise SystemExit(f"unable to load support-case source {raw}: {exc}") from exc
        return _normalize_source_payload(data), raw

    path = Path(raw).resolve()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"support-case source does not exist: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"support-case source is not valid JSON: {path}: {exc}") from exc
    return _normalize_source_payload(data), str(path)


def _normalize_source_payload(payload: Any) -> Dict[str, Any]:
    if isinstance(payload, list):
        return {"items": payload, "count": len(payload)}
    if not isinstance(payload, dict):
        raise SystemExit("support-case source must be a JSON array or object")
    items = payload.get("items")
    if items is None and isinstance(payload.get("cases"), list):
        items = payload.get("cases")
    if items is None:
        raise SystemExit("support-case source object must contain an items or cases array")
    if not isinstance(items, list):
        raise SystemExit("support-case items must be an array")
    normalized = dict(payload)
    normalized["items"] = items
    normalized["count"] = int(payload.get("count") or len(items))
    return normalized


def _normalize_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _normalize_text(value: Any, fallback: str = "") -> str:
    if value is None:
        return fallback
    return str(value).strip() or fallback


def _decision_for_case(item: Dict[str, Any]) -> Dict[str, Any]:
    kind = _normalize_text(item.get("kind")).lower()
    status = _normalize_text(item.get("status")).lower()
    owner_repo = _normalize_text(item.get("candidateOwnerRepo") or item.get("candidate_owner_repo"), "chummer6-hub")
    design_impact = _normalize_bool(item.get("designImpactSuspected") or item.get("design_impact_suspected"))
    title = _normalize_text(item.get("title"), "Support case")
    summary = _normalize_text(item.get("summary"), title)

    primary_lane = "support"
    change_class = "type_b"
    target_repo = owner_repo
    affected_canon_files: List[str] = []
    reason = "Support case needs triage before it becomes a bounded delivery slice."
    exit_condition = "Case reaches released_to_reporter_channel, rejected, or deferred with a recorded reason."

    if kind == "crash_report":
        primary_lane = "code"
        change_class = "type_b"
        target_repo = owner_repo or "chummer6-ui"
        reason = "Crash reports default to code remediation in the repo that owns the failing desktop/runtime surface."
    elif kind == "bug_report":
        primary_lane = "code"
        change_class = "type_b"
        reason = "Bug reports default to code remediation unless triage proves a docs or canon contradiction."
    elif kind == "install_help":
        primary_lane = "support"
        change_class = "type_c"
        target_repo = owner_repo or "chummer6-hub"
        reason = "Install and account-help cases default to Hub-owned support closure backed by registry/update truth."
    elif kind == "feedback":
        primary_lane = "support"
        change_class = "type_c"
        reason = "Feedback starts in support until it proves a docs, queue, or canon contradiction."

    if design_impact:
        primary_lane = "canon" if kind == "feedback" else "mixed"
        change_class = "type_d"
        target_repo = "chummer6-design"
        affected_canon_files = [
            "FEEDBACK_AND_SIGNAL_OODA_LOOP.md",
            "FEEDBACK_AND_CRASH_STATUS_MODEL.md",
        ]
        reason = "Case content suggests public-story, docs, or policy drift and needs canon review instead of repo-local patching alone."

    if status in {"deferred", "rejected", "user_notified"}:
        primary_lane = "defer" if status == "deferred" else primary_lane
        reason = f"Case is already in terminal or quasi-terminal posture ({status}) and needs closure verification more than new execution."

    case_id = _normalize_text(item.get("caseId") or item.get("case_id"))
    packet_seed = "|".join(
        [
            case_id,
            owner_repo,
            primary_lane,
            change_class,
            _normalize_text(item.get("releaseChannel") or item.get("release_channel"), "-"),
            _normalize_text(item.get("headId") or item.get("head_id"), "-"),
        ]
    )
    packet_id = f"support_packet_{hashlib.sha1(packet_seed.encode('utf-8')).hexdigest()[:12]}"

    return {
        "packet_id": packet_id,
        "case_id": case_id,
        "cluster_key": _normalize_text(item.get("clusterKey") or item.get("cluster_key")),
        "kind": kind,
        "status": status,
        "title": title,
        "summary": summary,
        "candidate_owner_repo": owner_repo,
        "target_repo": target_repo,
        "design_impact_suspected": design_impact,
        "primary_lane": primary_lane,
        "change_class": change_class,
        "reason": reason,
        "exit_condition": exit_condition,
        "affected_canon_files": affected_canon_files,
        "release_channel": _normalize_text(item.get("releaseChannel") or item.get("release_channel")),
        "head_id": _normalize_text(item.get("headId") or item.get("head_id")),
        "platform": _normalize_text(item.get("platform")),
        "arch": _normalize_text(item.get("arch")),
        "fixed_version": _normalize_text(item.get("fixedVersion") or item.get("fixed_version")),
        "fixed_channel": _normalize_text(item.get("fixedChannel") or item.get("fixed_channel")),
        "reporter_subject_id": _normalize_text(item.get("reporterSubjectId") or item.get("reporter_subject_id")),
    }


def _counter_map(values: Iterable[str]) -> Dict[str, int]:
    counter = Counter(value for value in values if value)
    return {key: counter[key] for key in sorted(counter)}


def build_packets_payload(source_payload: Dict[str, Any], source_label: str) -> Dict[str, Any]:
    raw_items = source_payload.get("items") or []
    packets = [_decision_for_case(dict(item)) for item in raw_items if isinstance(item, dict)]
    open_statuses = {
        "new",
        "clustered",
        "routed",
        "awaiting_evidence",
        "accepted",
        "fixed",
        "released_to_reporter_channel",
    }
    open_packets = [item for item in packets if item["status"] in open_statuses]

    return {
        "contract_name": "fleet.support_case_packets",
        "schema_version": 1,
        "generated_at": _utc_now_iso(),
        "source": {
            "source": source_label,
            "reported_count": int(source_payload.get("count") or len(raw_items)),
            "materialized_count": len(packets),
        },
        "summary": {
            "open_case_count": len(open_packets),
            "design_impact_count": sum(1 for item in open_packets if item["design_impact_suspected"]),
            "owner_repo_counts": _counter_map(item["candidate_owner_repo"] for item in open_packets),
            "lane_counts": _counter_map(item["primary_lane"] for item in open_packets),
            "status_counts": _counter_map(item["status"] for item in open_packets),
        },
        "packets": packets,
    }


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)
    source_payload, source_label = _load_json_source(args.source)
    payload = build_packets_payload(source_payload, source_label)

    out_path = Path(args.out).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    manifest_repo_root = repo_root_for_published_path(out_path)
    if manifest_repo_root is not None:
        write_compile_manifest(manifest_repo_root)

    print(f"wrote support-case packets: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
