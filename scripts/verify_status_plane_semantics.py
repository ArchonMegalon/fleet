#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

import yaml

ROOT = Path("/docker/fleet")
DEFAULT_STATUS_PLANE_PATH = ROOT / ".codex-studio" / "published" / "STATUS_PLANE.generated.yaml"
DEPLOY_SCRIPT_PATH = ROOT / "scripts" / "deploy.sh"
VOLATILE_TOP_LEVEL_KEYS = {"generated_at", "source_public_status_generated_at"}


class StatusPlaneDriftError(RuntimeError):
    pass


def _normalize_stage(stage: Any) -> str:
    return str(stage or "pre_repo_local_complete").strip()


def build_expected_status_plane(admin_status: Dict[str, Any]) -> Dict[str, Any]:
    public_status = dict(admin_status.get("public_status") or {})
    projects = list(admin_status.get("projects") or [])
    groups = list(admin_status.get("groups") or [])

    project_rows: List[Dict[str, Any]] = []
    for project in sorted(projects, key=lambda item: str(item.get("id") or "")):
        readiness = dict(project.get("readiness") or {})
        deployment = dict(project.get("deployment") or {})
        project_rows.append(
            {
                "id": str(project.get("id") or ""),
                "lifecycle": str(project.get("lifecycle") or ""),
                "runtime_status": str(project.get("runtime_status") or ""),
                "readiness_stage": _normalize_stage(readiness.get("stage")),
                "readiness_terminal_stage": str(readiness.get("terminal_stage") or ""),
                "readiness_final_claim_allowed": bool(readiness.get("final_claim_allowed")),
                "readiness_warning_count": int(readiness.get("warning_count") or 0),
                "deployment_status": str(deployment.get("status") or ""),
                "deployment_promotion_stage": str(deployment.get("promotion_stage") or ""),
                "deployment_access_posture": str(deployment.get("access_posture") or deployment.get("visibility") or ""),
            }
        )

    group_rows: List[Dict[str, Any]] = []
    for group in sorted(groups, key=lambda item: str(item.get("id") or "")):
        deployment = dict(group.get("deployment") or {})
        deployment_readiness = dict(group.get("deployment_readiness") or {})
        blocking_owner_projects = sorted({str(item).strip() for item in (deployment_readiness.get("blocking_owner_projects") or []) if str(item).strip()})
        group_rows.append(
            {
                "id": str(group.get("id") or ""),
                "lifecycle": str(group.get("lifecycle") or ""),
                "phase": str(group.get("phase") or ""),
                "deployment_status": str(deployment.get("status") or ""),
                "deployment_promotion_stage": str(deployment.get("promotion_stage") or ""),
                "deployment_access_posture": str(deployment.get("access_posture") or deployment.get("visibility") or ""),
                "publicly_promoted": bool(deployment_readiness.get("publicly_promoted")),
                "blocking_owner_projects": blocking_owner_projects,
            }
        )

    return {
        "contract_name": "fleet.status_plane",
        "schema_version": 1,
        "generated_at": str(admin_status.get("generated_at") or ""),
        "source_public_status_generated_at": str(public_status.get("generated_at") or ""),
        "deployment_posture": dict(public_status.get("deployment_posture") or {}),
        "readiness_summary": dict(public_status.get("readiness_summary") or {}),
        "projects": project_rows,
        "groups": group_rows,
    }


def compare_status_plane(expected: Dict[str, Any], actual: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    expected_keys = set(expected.keys())
    actual_keys = set(actual.keys())
    if expected_keys != actual_keys:
        missing = sorted(expected_keys - actual_keys)
        extra = sorted(actual_keys - expected_keys)
        if missing:
            errors.append(f"missing top-level keys: {', '.join(missing)}")
        if extra:
            errors.append(f"unexpected top-level keys: {', '.join(extra)}")

    for key in sorted(expected_keys & actual_keys):
        if key in VOLATILE_TOP_LEVEL_KEYS:
            continue
        if expected[key] != actual[key]:
            errors.append(f"mismatch at {key}")
    return errors


def load_status_plane(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        raise StatusPlaneDriftError(f"status-plane artifact is missing: {path}")
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise StatusPlaneDriftError(f"status-plane artifact is not a mapping: {path}")
    return payload


def load_admin_status(status_json_path: Path | None) -> Dict[str, Any]:
    if status_json_path is not None:
        payload = json.loads(status_json_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise StatusPlaneDriftError("status-json payload must be an object")
        return payload

    if not DEPLOY_SCRIPT_PATH.is_file():
        raise StatusPlaneDriftError(f"cannot find deploy helper script at {DEPLOY_SCRIPT_PATH}")

    result = subprocess.run(
        ["bash", str(DEPLOY_SCRIPT_PATH), "admin-status"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        raise StatusPlaneDriftError(f"failed to load live admin status via deploy.sh admin-status: {stderr or 'unknown error'}")

    try:
        payload = json.loads(result.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise StatusPlaneDriftError(f"admin-status output is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise StatusPlaneDriftError("admin-status payload must be an object")
    return payload


def run_verification(status_plane_path: Path, status_json_path: Path | None) -> None:
    actual = load_status_plane(status_plane_path)
    admin_status = load_admin_status(status_json_path)
    expected = build_expected_status_plane(admin_status)
    errors = compare_status_plane(expected, actual)
    if errors:
        bullets = "\n".join(f"- {item}" for item in errors)
        raise StatusPlaneDriftError(
            "STATUS_PLANE.generated.yaml drifted from live readiness/deployment semantics:\n"
            f"{bullets}"
        )


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify STATUS_PLANE.generated.yaml against Fleet live readiness/deployment semantics.")
    parser.add_argument(
        "--status-plane",
        default=str(DEFAULT_STATUS_PLANE_PATH),
        help="path to STATUS_PLANE.generated.yaml",
    )
    parser.add_argument(
        "--status-json",
        default=None,
        help="optional path to an admin status JSON payload (used for tests/offline verification)",
    )
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    status_plane_path = Path(args.status_plane).resolve()
    status_json_path = Path(args.status_json).resolve() if args.status_json else None
    try:
        run_verification(status_plane_path=status_plane_path, status_json_path=status_json_path)
    except StatusPlaneDriftError as exc:
        print(f"status-plane verification failed: {exc}", file=sys.stderr)
        return 1
    print("status-plane verification passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
