#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from glob import glob
from pathlib import Path
from typing import Any, Dict, List

import yaml
from materialize_compile_manifest import repo_root_for_published_path, write_compile_manifest

from verify_status_plane_semantics import (
    DEFAULT_STATUS_PLANE_PATH,
    StatusPlaneDriftError,
    build_expected_status_plane,
    load_admin_status,
)

UTC = dt.timezone.utc
ROOT = Path("/docker/fleet")
PROJECT_CONFIG_DIR = ROOT / "config" / "projects"
STAGE_ORDER = (
    "pre_repo_local_complete",
    "repo_local_complete",
    "package_canonical",
    "boundary_pure",
    "publicly_promoted",
)


def iso_now() -> str:
    return dt.datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return dict(payload) if isinstance(payload, dict) else {}


def _infer_fallback_readiness_stage(project_id: str, project_root: Path) -> str:
    published_dir = project_root / ".codex-studio" / "published"
    if not published_dir.is_dir():
        return "pre_repo_local_complete"

    def _proof_passed(payload: Dict[str, Any]) -> bool:
        return str(payload.get("status") or "").strip().lower() in {"pass", "passed", "ready"}

    if project_id == "hub-registry":
        release_channel = _load_json_file(published_dir / "RELEASE_CHANNEL.generated.json")
        if release_channel:
            release_status = str(release_channel.get("status") or "").strip().lower()
            release_proof_status = str(((release_channel.get("releaseProof") or {}).get("status") or "")).strip().lower()
            if release_status in {"published", "publishable"} and release_proof_status in {"pass", "passed"}:
                return "boundary_pure"
    elif project_id == "media-factory":
        media_local_release_proof = _load_json_file(published_dir / "MEDIA_LOCAL_RELEASE_PROOF.generated.json")
        artifact_publication_certification = _load_json_file(published_dir / "ARTIFACT_PUBLICATION_CERTIFICATION.generated.json")
        if _proof_passed(media_local_release_proof) and _proof_passed(artifact_publication_certification):
            return "boundary_pure"

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
        deployment = dict(payload.get("deployment") or {})
        fallback_stage = _infer_fallback_readiness_stage(project_id, project_root) if project_root else "pre_repo_local_complete"
        rows.append(
            {
                "id": project_id,
                "lifecycle": lifecycle,
                "runtime_status": "dispatch_pending",
                "readiness": {
                    "stage": fallback_stage,
                    "terminal_stage": "publicly_promoted",
                    "final_claim_allowed": False,
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
    if projects:
        return normalized

    fallback_projects = _load_project_config_rows()
    if not fallback_projects:
        return normalized

    normalized["projects"] = fallback_projects
    public_status = dict(normalized.get("public_status") or {})
    readiness_summary = dict(public_status.get("readiness_summary") or {})
    counts = _recompute_readiness_counts(fallback_projects)
    readiness_summary["counts"] = counts
    readiness_summary["warning_count"] = int(readiness_summary.get("warning_count") or 0)
    readiness_summary["final_claim_ready"] = int(
        readiness_summary.get("final_claim_ready")
        or sum(1 for project in fallback_projects if bool(dict(project.get("readiness") or {}).get("final_claim_allowed")))
    )
    public_status["readiness_summary"] = readiness_summary
    normalized["public_status"] = public_status
    return normalized


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    output_path = Path(args.out).resolve()
    status_json_path = Path(args.status_json).resolve() if args.status_json else None
    status_json_out_path = Path(args.status_json_out).resolve() if args.status_json_out else None

    try:
        admin_status = load_admin_status(status_json_path, use_default_snapshot=False)
    except StatusPlaneDriftError as exc:
        if status_json_path is not None:
            print(f"status-plane materialization failed: {exc}", file=sys.stderr)
            return 1
        try:
            admin_status = load_admin_status(None, use_default_snapshot=True)
        except StatusPlaneDriftError:
            print(f"status-plane materialization failed: {exc}", file=sys.stderr)
            return 1
    admin_status = _ensure_project_inventory(admin_status)
    payload = build_expected_status_plane(admin_status)
    payload["generated_at"] = iso_now()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    if status_json_out_path is not None:
        status_json_out_path.parent.mkdir(parents=True, exist_ok=True)
        status_json_out_path.write_text(json.dumps(admin_status, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest_repo_root = repo_root_for_published_path(output_path)
    if manifest_repo_root is not None:
        write_compile_manifest(manifest_repo_root)
    print(f"wrote status plane: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
