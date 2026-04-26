#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import time
from glob import glob
from pathlib import Path
from typing import Any, Dict, List

import yaml
try:
    from scripts.materialize_compile_manifest import repo_root_for_published_path, write_compile_manifest, write_text_atomic
except ModuleNotFoundError:
    from materialize_compile_manifest import repo_root_for_published_path, write_compile_manifest, write_text_atomic

try:
    from scripts.verify_status_plane_semantics import (
        DEFAULT_STATUS_JSON_SNAPSHOT_PATH,
        DEFAULT_STATUS_PLANE_PATH,
        StatusPlaneDriftError,
        build_expected_status_plane,
        load_admin_status,
    )
except ModuleNotFoundError:
    from verify_status_plane_semantics import (
        DEFAULT_STATUS_JSON_SNAPSHOT_PATH,
        DEFAULT_STATUS_PLANE_PATH,
        StatusPlaneDriftError,
        build_expected_status_plane,
        load_admin_status,
    )

UTC = dt.timezone.utc
ROOT = Path("/docker/fleet")
PROJECT_CONFIG_DIR = ROOT / "config" / "projects"
GROUP_CONFIG_PATH = ROOT / "config" / "groups.yaml"
FLAGSHIP_READINESS_PATH = ROOT / ".codex-studio" / "published" / "FLAGSHIP_PRODUCT_READINESS.generated.json"
STAGE_ORDER = (
    "pre_repo_local_complete",
    "repo_local_complete",
    "package_canonical",
    "boundary_pure",
    "publicly_promoted",
)
STAGE_RANK = {name: index for index, name in enumerate(STAGE_ORDER)}


def iso_now() -> str:
    return dt.datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _flagship_claim_status() -> Dict[str, Any]:
    if not FLAGSHIP_READINESS_PATH.is_file():
        return {}
    try:
        payload = json.loads(FLAGSHIP_READINESS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(payload, dict):
        return {}
    flagship_readiness_audit = dict(payload.get("flagship_readiness_audit") or {})
    coverage = dict(payload.get("coverage") or {})
    warning_keys = [
        str(item).strip()
        for item in (payload.get("warning_keys") or [])
        if str(item).strip()
    ]
    if not warning_keys:
        warning_keys = [
            str(item).strip()
            for item in (flagship_readiness_audit.get("warning_coverage_keys") or [])
            if str(item).strip()
        ]
    if not warning_keys and coverage:
        warning_keys = sorted(
            key for key, value in coverage.items() if str(key).strip() and str(value).strip().lower() == "warning"
        )
    if not warning_keys:
        readiness_planes = dict(payload.get("readiness_planes") or {})
        warning_keys = sorted(
            key
            for key, value in readiness_planes.items()
            if str(key).strip()
            and isinstance(value, dict)
            and str(value.get("status") or "").strip().lower() in {"warning", "missing"}
        )
    return {
        "status": str(payload.get("status") or "").strip().lower() or "unknown",
        "warning_keys": warning_keys,
        "bar": str(dict(payload.get("quality_policy") or {}).get("bar") or "").strip() or "unknown",
        "whole_project_frontier_required": bool(dict(payload.get("quality_policy") or {}).get("whole_project_frontier_required")),
        "feedback_autofix_loop_required": bool(dict(payload.get("quality_policy") or {}).get("feedback_autofix_loop_required")),
        "accept_lowered_standards": bool(dict(payload.get("quality_policy") or {}).get("accept_lowered_standards")),
    }


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compile STATUS_PLANE.generated.yaml from live Fleet readiness/deployment semantics."
    )
    parser.add_argument(
        "--out",
        default=str(DEFAULT_STATUS_PLANE_PATH),
        help="output path for STATUS_PLANE.generated.yaml",
    )
    parser.add_argument(
        "--status-json",
        default=None,
        help="optional path to admin status JSON payload (used for offline/test runs)",
    )
    parser.add_argument(
        "--status-json-out",
        default=None,
        help="optional path to write the exact admin status JSON snapshot used for this materialization",
    )
    return parser.parse_args(argv)


def _load_json_file(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        return {}
    for attempt in range(3):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            if attempt >= 2:
                return {}
            time.sleep(0.05 * (attempt + 1))
            continue
        except Exception:
            return {}
        return dict(payload) if isinstance(payload, dict) else {}
    return {}


def _fleet_boundary_proof_passed(published_dir: Path) -> bool:
    compile_manifest = _load_json_file(published_dir / "compile.manifest.json")
    if not compile_manifest:
        return False
    if not bool(compile_manifest.get("dispatchable_truth_ready")):
        return False
    stages = dict(compile_manifest.get("stages") or {})
    required_stages = (
        "design_compile",
        "policy_compile",
        "execution_compile",
        "package_compile",
        "capacity_compile",
    )
    if any(stages.get(stage) is not True for stage in required_stages):
        return False
    artifact_inventory = {str(item or "").strip() for item in (compile_manifest.get("artifacts") or [])}
    required_artifacts = {
        "STATUS_PLANE.generated.yaml",
        "PROGRESS_REPORT.generated.json",
        "PROGRESS_HISTORY.generated.json",
        "SUPPORT_CASE_PACKETS.generated.json",
        "JOURNEY_GATES.generated.json",
    }
    if not required_artifacts.issubset(artifact_inventory):
        return False
    support_packets = _load_json_file(published_dir / "SUPPORT_CASE_PACKETS.generated.json")
    if str(support_packets.get("contract_name") or "").strip() != "fleet.support_case_packets":
        return False
    if str(support_packets.get("schema_version") or "").strip() != "1":
        return False
    if not str(support_packets.get("generated_at") or "").strip():
        return False
    return isinstance(support_packets.get("summary") or {}, dict)


def _fleet_package_manifest_ready(published_dir: Path) -> bool:
    compile_manifest = _load_json_file(published_dir / "compile.manifest.json")
    if not compile_manifest:
        return False
    stages = dict(compile_manifest.get("stages") or {})
    required_stages = (
        "design_compile",
        "policy_compile",
        "execution_compile",
        "package_compile",
        "capacity_compile",
    )
    if any(stages.get(stage) is not True for stage in required_stages):
        return False
    artifact_inventory = {str(item or "").strip() for item in (compile_manifest.get("artifacts") or [])}
    required_artifacts = {
        "STATUS_PLANE.generated.yaml",
        "PROGRESS_REPORT.generated.json",
        "PROGRESS_HISTORY.generated.json",
        "SUPPORT_CASE_PACKETS.generated.json",
        "JOURNEY_GATES.generated.json",
    }
    if not required_artifacts.issubset(artifact_inventory):
        compact_artifacts = {
            "STATUS_PLANE.generated.yaml",
            "WORKPACKAGES.generated.yaml",
        }
        if not (
            bool(compile_manifest.get("dispatchable_truth_ready"))
            and required_stages
            and compact_artifacts.issubset(artifact_inventory)
            and (published_dir / "WORKPACKAGES.generated.yaml").is_file()
        ):
            return False
    return True


def _infer_fallback_readiness_stage(
    project_id: str,
    project_root: Path,
    *,
    lifecycle: str = "dispatchable",
    design_doc: str = "",
    deployment: Dict[str, Any] | None = None,
) -> str:
    published_dir = project_root / ".codex-studio" / "published"
    if not published_dir.is_dir():
        return "pre_repo_local_complete"

    def _proof_passed(payload: Dict[str, Any]) -> bool:
        return str(payload.get("status") or "").strip().lower() in {"pass", "passed", "ready"}

    deployment_row = dict(deployment or {})

    def _is_public_deployment(row: Dict[str, Any]) -> bool:
        values = {
            str(row.get("status") or "").strip().lower(),
            str(row.get("access_posture") or row.get("visibility") or "").strip().lower(),
            str(row.get("promotion_stage") or "").strip().lower(),
        }
        return any(
            value in {"public", "public_preview", "promoted_preview", "publicly_promoted"}
            for value in values
            if value
        )

    if project_id == "hub-registry":
        release_channel = _load_json_file(published_dir / "RELEASE_CHANNEL.generated.json")
        if release_channel:
            release_status = str(release_channel.get("status") or "").strip().lower()
            release_proof_status = str(((release_channel.get("releaseProof") or {}).get("status") or "")).strip().lower()
            if release_status in {"published", "publishable"} and release_proof_status in {"pass", "passed"}:
                return "boundary_pure"
    elif project_id == "core":
        import_parity = _load_json_file(published_dir / "IMPORT_PARITY_CERTIFICATION.generated.json")
        engine_proof_pack = _load_json_file(published_dir / "ENGINE_PROOF_PACK.generated.json")
        if _proof_passed(import_parity) and _proof_passed(engine_proof_pack):
            return "boundary_pure"
    elif project_id == "media-factory":
        media_local_release_proof = _load_json_file(published_dir / "MEDIA_LOCAL_RELEASE_PROOF.generated.json")
        artifact_publication_certification = _load_json_file(published_dir / "ARTIFACT_PUBLICATION_CERTIFICATION.generated.json")
        if _proof_passed(media_local_release_proof) and _proof_passed(artifact_publication_certification):
            return "boundary_pure"
    elif project_id == "ui-kit":
        ui_kit_local_release_proof = _load_json_file(published_dir / "UI_KIT_LOCAL_RELEASE_PROOF.generated.json")
        if _proof_passed(ui_kit_local_release_proof):
            return "boundary_pure"
    elif project_id == "hub":
        hub_local_release_proof = _load_json_file(published_dir / "HUB_LOCAL_RELEASE_PROOF.generated.json")
        hub_campaign_os_proof = _load_json_file(published_dir / "HUB_CAMPAIGN_OS_LOCAL_PROOF.generated.json")
        if _is_public_deployment(deployment_row) and _proof_passed(hub_local_release_proof) and _proof_passed(hub_campaign_os_proof):
            return "publicly_promoted"
    elif project_id == "mobile":
        mobile_local_release_proof = _load_json_file(published_dir / "MOBILE_LOCAL_RELEASE_PROOF.generated.json")
        if _is_public_deployment(deployment_row) and _proof_passed(mobile_local_release_proof):
            return "publicly_promoted"
    elif project_id == "ui":
        ui_flagship_release_gate = _load_json_file(published_dir / "UI_FLAGSHIP_RELEASE_GATE.generated.json")
        ui_local_release_proof = _load_json_file(published_dir / "UI_LOCAL_RELEASE_PROOF.generated.json")
        if _is_public_deployment(deployment_row) and _proof_passed(ui_flagship_release_gate) and _proof_passed(ui_local_release_proof):
            return "publicly_promoted"
    elif project_id == "fleet":
        if _fleet_boundary_proof_passed(published_dir):
            return "boundary_pure"
        if _fleet_package_manifest_ready(published_dir):
            return "package_canonical"
    try:
        from admin import readiness as readiness_module
    except Exception:
        readiness_module = None
        root_path = str(ROOT)
        if root_path not in sys.path:
            sys.path.insert(0, root_path)
        try:
            from admin import readiness as readiness_module
        except Exception:
            readiness_module = None

    if readiness_module is not None:
        compile_summary = readiness_module.studio_compile_summary(project_root, design_doc)
        compile_health = readiness_module.compile_health(compile_summary, lifecycle)
        if str(compile_health.get("status") or "").strip().lower() in {"ready", "not_required"}:
            return "package_canonical"

    generated_artifacts = list(glob(str(published_dir / "*.generated.*")))
    if generated_artifacts:
        return "repo_local_complete"
    return "pre_repo_local_complete"


def _load_project_config_rows() -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    if not PROJECT_CONFIG_DIR.is_dir():
        return rows
    for path in sorted(PROJECT_CONFIG_DIR.glob("*.yaml")):
        if path.name == "_index.yaml":
            continue
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(payload, dict):
            continue
        if payload.get("enabled") is False:
            continue
        project_id = str(payload.get("id") or "").strip()
        if not project_id:
            continue
        project_root = Path(str(payload.get("path") or "").strip())
        lifecycle = str(payload.get("lifecycle") or "dispatchable").strip() or "dispatchable"
        design_doc = str(payload.get("design_doc") or "").strip()
        deployment = dict(payload.get("deployment") or {})
        fallback_stage = (
            _infer_fallback_readiness_stage(
                project_id,
                project_root,
                lifecycle=lifecycle,
                design_doc=design_doc,
                deployment=deployment,
            )
            if project_root
            else "pre_repo_local_complete"
        )
        terminal_stage = "publicly_promoted"
        rows.append(
            {
                "id": project_id,
                "lifecycle": lifecycle,
                "runtime_status": "dispatch_pending",
                "readiness": {
                    "stage": fallback_stage,
                    "terminal_stage": terminal_stage,
                    "final_claim_allowed": fallback_stage == terminal_stage,
                    "warning_count": 0,
                },
                "deployment": {
                    "status": str(deployment.get("status") or ""),
                    "promotion_stage": str(deployment.get("promotion_stage") or ""),
                    "access_posture": str(deployment.get("access_posture") or deployment.get("visibility") or ""),
                },
            }
        )
    return rows


def _load_group_config_rows() -> List[Dict[str, Any]]:
    if not GROUP_CONFIG_PATH.is_file():
        return []
    payload = yaml.safe_load(GROUP_CONFIG_PATH.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        return []
    rows: List[Dict[str, Any]] = []
    for item in sorted(payload.get("project_groups") or [], key=lambda row: str(dict(row or {}).get("id") or "")):
        row = dict(item or {})
        group_id = str(row.get("id") or "").strip()
        if not group_id:
            continue
        deployment = dict(row.get("deployment") or {})
        public_surface = dict(deployment.get("public_surface") or {})
        status = str(public_surface.get("status") or "").strip()
        promotion_stage = str(public_surface.get("promotion_stage") or "").strip()
        access_posture = str(public_surface.get("access_posture") or "").strip() or status
        values = {
            status.lower(),
            promotion_stage.lower(),
            access_posture.lower(),
        }
        publicly_promoted = any(
            value in {"public", "public_preview", "promoted_preview", "publicly_promoted"} for value in values if value
        )
        rows.append(
            {
                "id": group_id,
                "lifecycle": str(row.get("lifecycle") or "").strip(),
                "phase": str(row.get("phase") or "active").strip() or "active",
                "deployment": {
                    "status": status,
                    "promotion_stage": promotion_stage,
                    "access_posture": access_posture,
                },
                "deployment_readiness": {
                    "publicly_promoted": publicly_promoted,
                    "blocking_owner_projects": [],
                },
            }
        )
    return rows


def _recompute_readiness_counts(projects: List[Dict[str, Any]]) -> Dict[str, int]:
    counts = {key: 0 for key in STAGE_ORDER}
    for project in projects:
        readiness = dict(project.get("readiness") or {})
        stage = str(readiness.get("stage") or "pre_repo_local_complete").strip() or "pre_repo_local_complete"
        if stage not in counts:
            stage = "pre_repo_local_complete"
        counts[stage] += 1
    return counts


def _ensure_project_inventory(admin_status: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(admin_status or {})
    projects = list(normalized.get("projects") or [])
    groups = list(normalized.get("groups") or [])
    fallback_projects = _load_project_config_rows()
    fallback_groups = _load_group_config_rows()
    fallback_by_id = {
        str(item.get("id") or "").strip(): dict(item.get("readiness") or {})
        for item in fallback_projects
        if str(item.get("id") or "").strip()
    }
    inventory_changed = False

    if projects:
        upgraded_projects: List[Dict[str, Any]] = []
        stage_upgraded = False
        for row in projects:
            project_row = dict(row or {})
            project_id = str(project_row.get("id") or "").strip()
            readiness = dict(project_row.get("readiness") or {})
            fallback_readiness = dict(fallback_by_id.get(project_id) or {})
            current_stage = str(readiness.get("stage") or "pre_repo_local_complete").strip() or "pre_repo_local_complete"
            fallback_stage = str(fallback_readiness.get("stage") or "").strip()
            fallback_terminal_stage = str(fallback_readiness.get("terminal_stage") or "").strip()
            fallback_final_claim_allowed = bool(fallback_readiness.get("final_claim_allowed"))
            readiness_changed = False
            if fallback_stage and STAGE_RANK.get(fallback_stage, -1) > STAGE_RANK.get(current_stage, -1):
                readiness["stage"] = fallback_stage
                readiness_changed = True
            if fallback_terminal_stage and not str(readiness.get("terminal_stage") or "").strip():
                readiness["terminal_stage"] = fallback_terminal_stage
                readiness_changed = True
            if fallback_final_claim_allowed and not bool(readiness.get("final_claim_allowed")):
                readiness["final_claim_allowed"] = True
                readiness_changed = True
            if readiness_changed:
                project_row["readiness"] = readiness
                stage_upgraded = True
            upgraded_projects.append(project_row)
        if stage_upgraded:
            normalized["projects"] = upgraded_projects
            inventory_changed = True
    elif fallback_projects:
        normalized["projects"] = fallback_projects
        inventory_changed = True

    if not groups and fallback_groups:
        normalized["groups"] = fallback_groups
        inventory_changed = True

    public_status = dict(normalized.get("public_status") or {})
    readiness_summary = dict(public_status.get("readiness_summary") or {})
    counts = _recompute_readiness_counts(list(normalized.get("projects") or []))
    readiness_summary["counts"] = counts
    final_claim_ready_project_ids = sorted(
        str(project.get("id") or "").strip()
        for project in (normalized.get("projects") or [])
        if str(project.get("id") or "").strip()
        and bool(dict(project.get("readiness") or {}).get("final_claim_allowed"))
    )
    readiness_summary["final_claim_ready"] = len(final_claim_ready_project_ids)
    readiness_summary["final_claim_ready_project_ids"] = final_claim_ready_project_ids
    flagship_claim = _flagship_claim_status()
    readiness_summary["whole_product_final_claim_status"] = str(flagship_claim.get("status") or "unknown")
    readiness_summary["whole_product_final_claim_bar"] = str(flagship_claim.get("bar") or "unknown")
    readiness_summary["whole_product_final_claim_whole_project_frontier_required"] = bool(
        flagship_claim.get("whole_project_frontier_required")
    )
    readiness_summary["whole_product_final_claim_feedback_autofix_loop_required"] = bool(
        flagship_claim.get("feedback_autofix_loop_required")
    )
    readiness_summary["whole_product_final_claim_accept_lowered_standards"] = bool(
        flagship_claim.get("accept_lowered_standards")
    )
    readiness_summary["whole_product_final_claim_ready"] = int(
        str(flagship_claim.get("status") or "").strip().lower() in {"pass", "passed", "ready"}
        and str(flagship_claim.get("bar") or "").strip().lower() == "top_flagship_grade"
        and bool(flagship_claim.get("whole_project_frontier_required"))
        and bool(flagship_claim.get("feedback_autofix_loop_required"))
        and not bool(flagship_claim.get("accept_lowered_standards"))
    )
    readiness_summary["whole_product_final_claim_warning_keys"] = [
        str(item).strip()
        for item in (flagship_claim.get("warning_keys") or [])
        if str(item).strip()
    ]
    readiness_summary["warning_count"] = len(readiness_summary["whole_product_final_claim_warning_keys"])
    public_status["readiness_summary"] = readiness_summary
    normalized["public_status"] = public_status
    return normalized


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    output_path = Path(args.out).resolve()
    status_json_path = Path(args.status_json).resolve() if args.status_json else None
    if args.status_json_out:
        status_json_out_path = Path(args.status_json_out).resolve()
    elif status_json_path is None:
        status_json_out_path = Path(DEFAULT_STATUS_JSON_SNAPSHOT_PATH).resolve()
    else:
        status_json_out_path = None

    use_default_snapshot = status_json_path is not None

    try:
        admin_status = load_admin_status(status_json_path, use_default_snapshot=use_default_snapshot)
    except StatusPlaneDriftError as exc:
        if status_json_path is not None:
            print(f"status-plane materialization failed: {exc}", file=sys.stderr)
            return 1
        try:
            admin_status = load_admin_status(None, use_default_snapshot=False)
        except StatusPlaneDriftError:
            print(f"status-plane materialization failed: {exc}", file=sys.stderr)
            return 1
    admin_status = _ensure_project_inventory(admin_status)
    payload = build_expected_status_plane(admin_status)
    payload["generated_at"] = iso_now()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    write_text_atomic(output_path, yaml.safe_dump(payload, sort_keys=False))
    if status_json_out_path is not None:
        write_text_atomic(status_json_out_path, json.dumps(admin_status, indent=2, sort_keys=True) + "\n")
    manifest_repo_root = repo_root_for_published_path(output_path)
    if manifest_repo_root is not None:
        write_compile_manifest(manifest_repo_root)
    print(f"wrote status plane: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
