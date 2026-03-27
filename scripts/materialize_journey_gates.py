#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

import yaml
from materialize_compile_manifest import repo_root_for_published_path, write_compile_manifest


UTC = dt.timezone.utc
ROOT = Path("/docker/fleet")
DEFAULT_OUT = ROOT / ".codex-studio" / "published" / "JOURNEY_GATES.generated.json"
DEFAULT_STATUS_PLANE = ROOT / ".codex-studio" / "published" / "STATUS_PLANE.generated.yaml"
DEFAULT_PROGRESS_REPORT = ROOT / ".codex-studio" / "published" / "PROGRESS_REPORT.generated.json"
DEFAULT_PROGRESS_HISTORY = ROOT / ".codex-studio" / "published" / "PROGRESS_HISTORY.generated.json"
DEFAULT_SUPPORT_PACKETS = ROOT / ".codex-studio" / "published" / "SUPPORT_CASE_PACKETS.generated.json"
REGISTRY_CANDIDATES = (
    ROOT / ".codex-design" / "product" / "GOLDEN_JOURNEY_RELEASE_GATES.yaml",
    Path("/docker/chummercomplete/chummer-design/products/chummer/GOLDEN_JOURNEY_RELEASE_GATES.yaml"),
)

STAGE_ORDER = {
    "pre_repo_local_complete": 0,
    "repo_local_complete": 1,
    "package_canonical": 2,
    "boundary_pure": 3,
    "publicly_promoted": 4,
}
PROMOTION_ORDER = {
    "internal": 0,
    "protected_preview": 1,
    "public": 2,
}
ARTIFACT_STALE_HOURS = {
    "compile_manifest": 24,
    "status_plane": 24,
    "support_packets": 24,
    "progress_report": 24 * 7,
    "progress_history": 24 * 7,
}
REPO_ROOTS = {
    "fleet": ROOT,
    "chummer6-design": Path("/docker/chummercomplete/chummer-design"),
    "chummer6-core": Path("/docker/chummercomplete/chummer-core-engine"),
    "chummer6-hub": Path("/docker/chummercomplete/chummer.run-services"),
    "chummer6-hub-registry": Path("/docker/chummercomplete/chummer-hub-registry"),
    "chummer6-ui": Path("/docker/chummercomplete/chummer6-ui"),
    "chummer6-mobile": Path("/docker/chummercomplete/chummer6-mobile"),
    "chummer6-media-factory": Path("/docker/chummercomplete/chummer-media-factory"),
    "executive-assistant": Path("/docker/EA"),
}


def utc_now() -> dt.datetime:
    return dt.datetime.now(UTC)


def iso(ts: dt.datetime) -> str:
    return ts.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_iso(value: Any) -> dt.datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = dt.datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def load_json(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def load_yaml(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        return {}
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return payload if isinstance(payload, dict) else {}


def artifact_state(name: str, payload: Dict[str, Any], *, time_field: str) -> Dict[str, Any]:
    stale_after_hours = ARTIFACT_STALE_HOURS.get(name, 24)
    parsed = parse_iso(payload.get(time_field))
    if parsed is None:
        return {
            "artifact": name,
            "available": False,
            "at": "",
            "state": "missing",
            "age_seconds": None,
        }
    age_seconds = max(0, int((utc_now() - parsed).total_seconds()))
    state = "fresh" if age_seconds <= stale_after_hours * 3600 else "stale"
    return {
        "artifact": name,
        "available": True,
        "at": iso(parsed),
        "state": state,
        "age_seconds": age_seconds,
    }


def resolve_registry_path(explicit: str | None) -> Path:
    if explicit:
        path = Path(explicit).resolve()
        if not path.is_file():
            raise SystemExit(f"journey registry is missing: {path}")
        return path
    for candidate in REGISTRY_CANDIDATES:
        if candidate.is_file():
            return candidate.resolve()
    raise SystemExit("could not locate GOLDEN_JOURNEY_RELEASE_GATES.yaml in the Fleet mirror or canonical design repo")


def posture_value(project_row: Dict[str, Any]) -> str:
    return (
        str(project_row.get("deployment_promotion_stage") or "").strip()
        or str(project_row.get("deployment_status") or "").strip()
        or str(project_row.get("deployment_access_posture") or "").strip()
    )


def compare_order(actual: str, expected: str, order: Dict[str, int]) -> int:
    return order.get(str(actual or "").strip(), -1) - order.get(str(expected or "").strip(), -1)


def evaluate_journey(
    row: Dict[str, Any],
    *,
    projects_by_id: Dict[str, Dict[str, Any]],
    artifacts: Dict[str, Dict[str, Any]],
    progress_report: Dict[str, Any],
    progress_history: Dict[str, Any],
    support_packets: Dict[str, Any],
) -> Dict[str, Any]:
    fleet_gate = dict(row.get("fleet_gate") or {})
    blocking_reasons: List[str] = []
    warning_reasons: List[str] = []

    for artifact_name in fleet_gate.get("required_artifacts") or []:
        artifact = dict(artifacts.get(str(artifact_name)) or {})
        state = str(artifact.get("state") or "missing").strip()
        if state in {"missing", "stale"}:
            blocking_reasons.append(f"{artifact_name} is {state}.")

    minimum_history = int(fleet_gate.get("minimum_history_snapshots") or 0)
    target_history = int(fleet_gate.get("target_history_snapshots") or 0)
    history_count = int(progress_history.get("snapshot_count") or progress_report.get("history_snapshot_count") or 0)
    if minimum_history and history_count < minimum_history:
        blocking_reasons.append(
            f"progress history depth {history_count} is below the minimum journey evidence floor of {minimum_history}."
        )
    elif target_history and history_count < target_history:
        warning_reasons.append(
            f"progress history depth {history_count} is still below the boring target of {target_history}."
        )

    for posture in fleet_gate.get("required_project_posture") or []:
        posture_row = dict(posture or {})
        project_id = str(posture_row.get("project_id") or "").strip()
        project = dict(projects_by_id.get(project_id) or {})
        if not project:
            blocking_reasons.append(f"required project {project_id} is missing from status-plane truth.")
            continue
        stage = str(project.get("readiness_stage") or "").strip()
        minimum_stage = str(posture_row.get("minimum_stage") or "").strip()
        target_stage = str(posture_row.get("target_stage") or "").strip()
        if minimum_stage and compare_order(stage, minimum_stage, STAGE_ORDER) < 0:
            blocking_reasons.append(f"{project_id} is at {stage or 'unknown'} below minimum stage {minimum_stage}.")
        elif target_stage and compare_order(stage, target_stage, STAGE_ORDER) < 0:
            warning_reasons.append(f"{project_id} is at {stage or 'unknown'} below target stage {target_stage}.")

        actual_promotion = posture_value(project)
        minimum_promotion = str(posture_row.get("minimum_deployment_posture") or "").strip()
        target_promotion = str(posture_row.get("target_deployment_posture") or "").strip()
        if minimum_promotion and compare_order(actual_promotion, minimum_promotion, PROMOTION_ORDER) < 0:
            blocking_reasons.append(
                f"{project_id} promotion posture {actual_promotion or 'unknown'} is below minimum {minimum_promotion}."
            )
        elif target_promotion and compare_order(actual_promotion, target_promotion, PROMOTION_ORDER) < 0:
            warning_reasons.append(
                f"{project_id} promotion posture {actual_promotion or 'unknown'} is below target {target_promotion}."
            )

    for proof in fleet_gate.get("repo_source_proof") or []:
        proof_row = dict(proof or {})
        repo_name = str(proof_row.get("repo") or "").strip()
        relative_path = str(proof_row.get("path") or "").strip()
        repo_root = REPO_ROOTS.get(repo_name)
        if repo_root is None:
            blocking_reasons.append(f"repo proof root for {repo_name or 'unknown'} is not configured.")
            continue
        target_path = (repo_root / relative_path).resolve()
        if not target_path.is_file():
            blocking_reasons.append(f"repo proof file is missing: {repo_name}:{relative_path}.")
            continue
        try:
            text = target_path.read_text(encoding="utf-8")
        except OSError as exc:
            blocking_reasons.append(f"repo proof file could not be read: {repo_name}:{relative_path} ({exc}).")
            continue
        for snippet in proof_row.get("must_contain") or []:
            snippet_text = str(snippet or "").strip()
            if snippet_text and snippet_text not in text:
                blocking_reasons.append(
                    f"repo proof {repo_name}:{relative_path} is missing required marker '{snippet_text}'."
                )

    support_summary = dict(support_packets.get("summary") or {})
    support_generated_at = str(support_packets.get("generated_at") or "").strip()
    support_freshness = dict(artifacts.get("support_packets") or {})
    if bool(fleet_gate.get("require_support_freshness")) and support_freshness.get("state") != "fresh":
        blocking_reasons.append(
            f"support packet freshness is {support_freshness.get('state') or 'unknown'}."
        )
    if bool(fleet_gate.get("require_support_closure_waiting_zero")) and int(support_summary.get("closure_waiting_on_release_truth") or 0) > 0:
        warning_reasons.append("support closure is still waiting on release truth.")

    state = "ready"
    if blocking_reasons:
        state = "blocked"
    elif warning_reasons:
        state = "warning"

    recommended_action = "Keep the journey under routine weekly proof."
    if blocking_reasons:
        recommended_action = "Resolve the blocking artifact or posture gap before widening promotion or trust claims."
    elif warning_reasons:
        recommended_action = "Close the remaining target-stage or evidence-depth gap before calling the journey boring."

    evidence = {
        "history_snapshot_count": history_count,
        "support_packets_generated_at": support_generated_at,
        "required_artifacts": [str(item) for item in (fleet_gate.get("required_artifacts") or []) if str(item).strip()],
        "canonical_journeys": [str(item) for item in (row.get("canonical_journeys") or []) if str(item).strip()],
    }
    signals = {
        "blocking_reason_count": len(blocking_reasons),
        "warning_reason_count": len(warning_reasons),
        "support_closure_waiting_count": int(support_summary.get("closure_waiting_on_release_truth") or 0),
        "support_needs_human_response_count": int(support_summary.get("needs_human_response") or 0),
    }
    return {
        "id": str(row.get("id") or "").strip(),
        "title": str(row.get("title") or "").strip(),
        "user_promise": str(row.get("user_promise") or "").strip(),
        "state": state,
        "recommended_action": recommended_action,
        "blocking_reasons": blocking_reasons,
        "warning_reasons": warning_reasons,
        "owner_repos": [str(item) for item in (row.get("owner_repos") or []) if str(item).strip()],
        "canonical_journeys": [str(item) for item in (row.get("canonical_journeys") or []) if str(item).strip()],
        "scorecard_refs": dict(row.get("scorecard_refs") or {}),
        "fleet_gate": fleet_gate,
        "evidence": evidence,
        "signals": signals,
    }


def build_payload(
    *,
    registry_path: Path,
    status_plane_path: Path,
    progress_report_path: Path,
    progress_history_path: Path,
    support_packets_path: Path,
) -> Dict[str, Any]:
    registry = load_yaml(registry_path)
    status_plane = load_yaml(status_plane_path)
    progress_report = load_json(progress_report_path)
    progress_history = load_json(progress_history_path)
    support_packets = load_json(support_packets_path)
    compile_manifest = load_json(status_plane_path.parent / "compile.manifest.json")

    artifacts = {
        "compile_manifest": artifact_state("compile_manifest", compile_manifest, time_field="published_at"),
        "status_plane": artifact_state("status_plane", status_plane, time_field="generated_at"),
        "progress_report": artifact_state("progress_report", progress_report, time_field="generated_at"),
        "progress_history": artifact_state("progress_history", progress_history, time_field="generated_at"),
        "support_packets": artifact_state("support_packets", support_packets, time_field="generated_at"),
    }
    projects_by_id = {
        str(item.get("id") or "").strip(): dict(item)
        for item in (status_plane.get("projects") or [])
        if isinstance(item, dict) and str(item.get("id") or "").strip()
    }

    rows = []
    for row in registry.get("journey_gates") or []:
        if not isinstance(row, dict):
            continue
        rows.append(
            evaluate_journey(
                dict(row),
                projects_by_id=projects_by_id,
                artifacts=artifacts,
                progress_report=progress_report,
                progress_history=progress_history,
                support_packets=support_packets,
            )
        )

    blocked = [row for row in rows if row["state"] == "blocked"]
    warnings = [row for row in rows if row["state"] == "warning"]
    overall_state = "ready"
    if blocked:
        overall_state = "blocked"
    elif warnings:
        overall_state = "warning"

    generated_candidates = [
        parse_iso(item.get("at"))
        for item in artifacts.values()
        if isinstance(item, dict) and parse_iso(item.get("at")) is not None
    ]
    generated_at = iso(max(generated_candidates + [utc_now()]))
    recommended_action = "Journey proof is steady on current published evidence."
    if blocked:
        recommended_action = "Resolve the blocking golden-journey gaps before widening publish claims."
    elif warnings:
        recommended_action = "Close the target-stage and history-depth warnings before claiming the campaign OS is boringly proven."

    return {
        "contract_name": "fleet.journey_gates",
        "contract_version": 1,
        "generated_at": generated_at,
        "source_registry_path": str(registry_path),
        "summary": {
            "overall_state": overall_state,
            "total_journey_count": len(rows),
            "ready_count": sum(1 for row in rows if row["state"] == "ready"),
            "warning_count": len(warnings),
            "blocked_count": len(blocked),
            "recommended_action": recommended_action,
        },
        "artifact_freshness": artifacts,
        "journeys": rows,
    }


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Materialize Fleet golden-journey release gate truth.")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="output path for JOURNEY_GATES.generated.json")
    parser.add_argument("--registry", default=None, help="optional path to GOLDEN_JOURNEY_RELEASE_GATES.yaml")
    parser.add_argument("--status-plane", default=str(DEFAULT_STATUS_PLANE), help="path to STATUS_PLANE.generated.yaml")
    parser.add_argument("--progress-report", default=str(DEFAULT_PROGRESS_REPORT), help="path to PROGRESS_REPORT.generated.json")
    parser.add_argument("--progress-history", default=str(DEFAULT_PROGRESS_HISTORY), help="path to PROGRESS_HISTORY.generated.json")
    parser.add_argument("--support-packets", default=str(DEFAULT_SUPPORT_PACKETS), help="path to SUPPORT_CASE_PACKETS.generated.json")
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    out_path = Path(args.out).resolve()
    payload = build_payload(
        registry_path=resolve_registry_path(args.registry),
        status_plane_path=Path(args.status_plane).resolve(),
        progress_report_path=Path(args.progress_report).resolve(),
        progress_history_path=Path(args.progress_history).resolve(),
        support_packets_path=Path(args.support_packets).resolve(),
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    manifest_repo_root = repo_root_for_published_path(out_path)
    if manifest_repo_root is not None:
        write_compile_manifest(manifest_repo_root)
    print(f"wrote journey gates: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
