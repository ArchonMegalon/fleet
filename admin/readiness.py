from __future__ import annotations

import datetime as dt
import hashlib
import json
import pathlib
from typing import Any, Dict, List, Optional

import yaml


UTC = dt.timezone.utc
STUDIO_PUBLISHED_DIR = ".codex-studio/published"
COMPILE_MANIFEST_FILENAME = "compile.manifest.json"
DESIGN_MIRROR_REQUIRED_FILES = [
    ".codex-design/product/VISION.md",
    ".codex-design/product/ARCHITECTURE.md",
    ".codex-design/repo/IMPLEMENTATION_SCOPE.md",
    ".codex-design/review/REVIEW_CONTEXT.md",
]
DEFAULT_COMPILE_FRESHNESS_HOURS = {
    "planned": 0,
    "scaffold": 336,
    "dispatchable": 168,
    "live": 72,
    "signoff_only": 168,
}
DISPATCH_PARTICIPATION_LIFECYCLES = {"dispatchable", "live"}
READINESS_ORDER = [
    "repo_local_complete",
    "package_canonical",
    "boundary_pure",
    "publicly_promoted",
]
READINESS_LABELS = {
    "pre_repo_local_complete": "Pre-Repo-Local Complete",
    "repo_local_complete": "Repo-Local Complete",
    "package_canonical": "Package-Canonical",
    "boundary_pure": "Boundary-Pure",
    "publicly_promoted": "Publicly Promoted",
}
PROMOTED_DEPLOYMENT_STAGES = {"promoted_preview", "release_candidate", "public_stable"}
BOUNDARY_PURE_SCORE_FLOOR = 0.70
FLEET_ROOT = pathlib.Path(__file__).resolve().parents[1]
PROJECTS_CONFIG_DIR = FLEET_ROOT / "config" / "projects"
QUEUE_ARTIFACT = "QUEUE.generated.yaml"
WORKPACKAGES_ARTIFACT = "WORKPACKAGES.generated.yaml"


def _unique_preserve(values: List[str]) -> List[str]:
    seen: set[str] = set()
    ordered: List[str] = []
    for value in values:
        clean = str(value or "").strip()
        if not clean or clean in seen:
            continue
        seen.add(clean)
        ordered.append(clean)
    return ordered


def _parse_iso(value: Any) -> Optional[dt.datetime]:
    raw = str(value or "").strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        return dt.datetime.fromisoformat(raw).astimezone(UTC)
    except ValueError:
        return None


def _iso(value: Optional[dt.datetime]) -> str:
    if value is None:
        return ""
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def deployment_promotion_stage(status: Any) -> str:
    clean = str(status or "").strip().lower()
    if clean in {"public_stable", "stable"}:
        return "public_stable"
    if clean in {"release_candidate", "rc"}:
        return "release_candidate"
    if clean in {"promoted_preview", "promoted"}:
        return "promoted_preview"
    if clean in {"preview", "live_preview"}:
        return "preview"
    if clean in {"stale_preview", "stale"}:
        return "stale_preview"
    if clean in {"protected_preview", "protected"}:
        return "protected_preview"
    if clean in {"planned"}:
        return "planned"
    if clean in {"internal"}:
        return "internal"
    return "undeclared"


def project_repo_slug(project_cfg: Dict[str, Any]) -> str:
    review = project_cfg.get("review") or {}
    repo_name = str(review.get("repo") or "").strip()
    if repo_name:
        return repo_name
    return pathlib.Path(str(project_cfg.get("path") or "")).name


def resolve_design_doc_path(repo_root: pathlib.Path, design_doc: str) -> Optional[pathlib.Path]:
    raw = str(design_doc or "").strip()
    if not raw:
        return None
    path = pathlib.Path(raw)
    if path.is_absolute():
        return path
    return repo_root / path


def design_compile_present(repo_root: pathlib.Path, design_doc: str = "") -> bool:
    if all((repo_root / rel).is_file() for rel in DESIGN_MIRROR_REQUIRED_FILES):
        return True
    design_doc_path = resolve_design_doc_path(repo_root, design_doc)
    return bool(design_doc_path and design_doc_path.is_file())


def latest_design_compile_mtime(repo_root: pathlib.Path, design_doc: str = "") -> Optional[float]:
    times = [(repo_root / rel).stat().st_mtime for rel in DESIGN_MIRROR_REQUIRED_FILES if (repo_root / rel).is_file()]
    design_doc_path = resolve_design_doc_path(repo_root, design_doc)
    if design_doc_path and design_doc_path.is_file():
        times.append(design_doc_path.stat().st_mtime)
    if not times:
        return None
    return max(times)


def _work_package_source_queue_fingerprint(items: List[Any]) -> str:
    payload = json.dumps(list(items or []), sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def _configured_project_queue_for_repo(repo_root: pathlib.Path) -> Optional[List[Any]]:
    if not PROJECTS_CONFIG_DIR.exists():
        return None
    try:
        resolved_root = repo_root.resolve()
    except Exception:
        resolved_root = repo_root
    for path in sorted(PROJECTS_CONFIG_DIR.glob("*.yaml")):
        if path.name.startswith("_"):
            continue
        try:
            payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        project_path = str(payload.get("path") or "").strip()
        if not project_path:
            continue
        try:
            resolved_project_root = pathlib.Path(project_path).expanduser().resolve()
        except Exception:
            resolved_project_root = pathlib.Path(project_path).expanduser()
        if resolved_project_root == resolved_root:
            return list(payload.get("queue") or [])
    return None


def _workpackages_artifact_queue_bound(repo_root: pathlib.Path) -> bool:
    path = repo_root / STUDIO_PUBLISHED_DIR / WORKPACKAGES_ARTIFACT
    if not path.exists() or not path.is_file():
        return False
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return False
    expected_queue_fingerprint = ""
    if isinstance(payload, dict):
        expected_queue_fingerprint = str(payload.get("source_queue_fingerprint") or payload.get("queue_fingerprint") or "").strip()
    current_queue = _configured_project_queue_for_repo(repo_root)
    if current_queue is None:
        return True
    if expected_queue_fingerprint:
        return expected_queue_fingerprint == _work_package_source_queue_fingerprint(current_queue)
    return not current_queue


def _dispatchable_truth_ready(repo_root: pathlib.Path, artifacts: List[str]) -> bool:
    names = {str(item or "").strip() for item in artifacts if str(item or "").strip()}
    if QUEUE_ARTIFACT in names:
        return True
    if WORKPACKAGES_ARTIFACT in names:
        return _workpackages_artifact_queue_bound(repo_root)
    return False


def studio_compile_summary(repo_root: pathlib.Path, design_doc: str = "") -> Dict[str, Any]:
    published_dir = repo_root / STUDIO_PUBLISHED_DIR
    manifest_path = published_dir / COMPILE_MANIFEST_FILENAME
    design_compiled = design_compile_present(repo_root, design_doc)
    dispatchable_artifacts = {QUEUE_ARTIFACT, WORKPACKAGES_ARTIFACT}
    if manifest_path.exists():
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                stages = dict(payload.get("stages") or {})
                artifacts = list(payload.get("artifacts") or [])
                dispatchable_truth_ready = _dispatchable_truth_ready(repo_root, artifacts)
                stages["design_compile"] = bool(stages.get("design_compile")) or design_compiled
                stages["policy_compile"] = bool(stages.get("policy_compile")) or any(
                    path in {
                        "runtime-instructions.generated.md",
                        QUEUE_ARTIFACT,
                        WORKPACKAGES_ARTIFACT,
                        "STATUS_PLANE.generated.yaml",
                        "PROGRAM_MILESTONES.generated.yaml",
                        "CONTRACT_SETS.yaml",
                        "GROUP_BLOCKERS.md",
                    }
                    for path in artifacts
                )
                stages["execution_compile"] = bool(stages.get("execution_compile")) or any(
                    path in dispatchable_artifacts for path in artifacts
                )
                stages["package_compile"] = bool(stages.get("package_compile")) or "WORKPACKAGES.generated.yaml" in artifacts
                stages["capacity_compile"] = bool(stages.get("capacity_compile")) or any(
                    path in dispatchable_artifacts or path == "runtime-instructions.generated.md"
                    for path in artifacts
                )
                return {
                    "published_at": str(payload.get("published_at") or ""),
                    "stages": stages,
                    "dispatchable_truth_ready": dispatchable_truth_ready,
                    "artifacts": artifacts,
                    "lifecycle": str(payload.get("lifecycle") or ""),
                }
        except Exception:
            pass
    files = []
    if published_dir.exists():
        files = sorted(child.name for child in published_dir.iterdir() if child.is_file())
    if not files and not design_compiled:
        return {"published_at": "", "stages": {}, "dispatchable_truth_ready": False, "artifacts": [], "lifecycle": ""}
    design_files = {"VISION.md", "ROADMAP.md", "ARCHITECTURE.md"}
    policy_files = {
        "runtime-instructions.generated.md",
        QUEUE_ARTIFACT,
        WORKPACKAGES_ARTIFACT,
        "STATUS_PLANE.generated.yaml",
        "PROGRAM_MILESTONES.generated.yaml",
        "CONTRACT_SETS.yaml",
        "GROUP_BLOCKERS.md",
    }
    mtimes = [(published_dir / name).stat().st_mtime for name in files if (published_dir / name).exists()]
    mirror_mtime = latest_design_compile_mtime(repo_root, design_doc)
    if mirror_mtime is not None:
        mtimes.append(mirror_mtime)
    latest_mtime = max(mtimes) if mtimes else dt.datetime.now(tz=UTC).timestamp()
    return {
        "published_at": _iso(dt.datetime.fromtimestamp(latest_mtime, UTC)),
        "stages": {
            "design_compile": design_compiled or any(name in design_files for name in files),
            "policy_compile": any(name in policy_files for name in files),
            "execution_compile": any(name in dispatchable_artifacts for name in files),
            "package_compile": WORKPACKAGES_ARTIFACT in files,
            "capacity_compile": any(name in dispatchable_artifacts for name in files) or "runtime-instructions.generated.md" in files,
        },
        "dispatchable_truth_ready": _dispatchable_truth_ready(repo_root, files),
        "artifacts": files,
        "lifecycle": "",
    }


def compile_health(
    summary: Dict[str, Any],
    lifecycle: str,
    *,
    compile_freshness_hours: Optional[Dict[str, Any]] = None,
    now: Optional[dt.datetime] = None,
) -> Dict[str, Any]:
    lifecycle_state = str(lifecycle or "dispatchable").strip().lower() or "dispatchable"
    freshness_hours_map = dict(DEFAULT_COMPILE_FRESHNESS_HOURS)
    freshness_hours_map.update(dict(compile_freshness_hours or {}))
    freshness_hours = int(freshness_hours_map.get(lifecycle_state) or DEFAULT_COMPILE_FRESHNESS_HOURS.get(lifecycle_state, 168))
    current_now = now or dt.datetime.now(tz=UTC)
    published_at = _parse_iso(str(summary.get("published_at") or ""))
    age_hours = None
    if published_at is not None:
        age_hours = max(0, int((current_now - published_at).total_seconds() // 3600))
    stages = dict(summary.get("stages") or {})
    needs_design = lifecycle_state in {"scaffold", "dispatchable", "live", "signoff_only"}
    needs_policy = lifecycle_state in {"dispatchable", "live", "signoff_only"}
    needs_execution = lifecycle_state in {"dispatchable", "live"}
    missing: List[str] = []
    if needs_design and not stages.get("design_compile"):
        missing.append("design compile")
    if needs_policy and not stages.get("policy_compile"):
        missing.append("policy compile")
    if needs_execution and not bool(summary.get("dispatchable_truth_ready")):
        missing.append("execution compile")
    if lifecycle_state == "planned":
        return {
            "status": "not_required",
            "tone": "gray",
            "summary": "planned work does not require dispatch artifacts yet",
            "freshness_hours": freshness_hours,
            "age_hours": age_hours,
        }
    if missing and not list(summary.get("artifacts") or []):
        return {
            "status": "missing",
            "tone": "red" if lifecycle_state in DISPATCH_PARTICIPATION_LIFECYCLES else "yellow",
            "summary": f"missing compile artifacts: {', '.join(missing)}",
            "freshness_hours": freshness_hours,
            "age_hours": age_hours,
        }
    if missing:
        return {
            "status": "incomplete",
            "tone": "yellow",
            "summary": f"compile artifacts exist but still miss {', '.join(missing)}",
            "freshness_hours": freshness_hours,
            "age_hours": age_hours,
        }
    if age_hours is None:
        return {
            "status": "unknown",
            "tone": "yellow",
            "summary": "compile artifacts exist but their freshness is unknown",
            "freshness_hours": freshness_hours,
            "age_hours": age_hours,
        }
    if freshness_hours > 0 and age_hours > freshness_hours:
        return {
            "status": "stale",
            "tone": "yellow",
            "summary": f"compile artifacts are {age_hours}h old; freshness target is {freshness_hours}h",
            "freshness_hours": freshness_hours,
            "age_hours": age_hours,
        }
    return {
        "status": "ready",
        "tone": "green",
        "summary": "compile artifacts are current for the declared lifecycle",
        "freshness_hours": freshness_hours,
        "age_hours": age_hours,
    }


def boundary_purity_registry(design_root: pathlib.Path) -> Dict[str, Dict[str, Any]]:
    path = design_root / "products" / "chummer" / "PROGRAM_MILESTONES.yaml"
    if not path.exists() or not path.is_file():
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}
    rows = data.get("repo_boundary_purity") or []
    registry: Dict[str, Dict[str, Any]] = {}
    if not isinstance(rows, list):
        return registry
    for row in rows:
        if not isinstance(row, dict):
            continue
        repo = str(row.get("repo") or "").strip()
        if not repo:
            continue
        registry[repo] = {
            "repo": repo,
            "status": str(row.get("status") or "").strip().lower(),
            "score": float(row.get("score") or 0.0),
            "reason": str(row.get("reason") or "").strip(),
        }
    return registry


def boundary_purity_registry_from_config(config: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    design_cfg = next((project for project in config.get("projects") or [] if str(project.get("id") or "").strip() == "design"), {})
    design_path = str(design_cfg.get("path") or "").strip() if design_cfg else ""
    if not design_path:
        return {}
    design_root = pathlib.Path(design_path).resolve()
    return boundary_purity_registry(design_root)


def _readiness_basis_for_runtime(runtime_status: str, runtime_completion_state: str) -> str:
    if runtime_completion_state in {"runtime_complete", "scaffold_complete", "signed_off"}:
        return f"runtime completion is {runtime_completion_state}"
    if runtime_completion_state == "signoff_only":
        return "repo is in signoff-only posture"
    return f"runtime is still {runtime_status or runtime_completion_state or 'in_progress'}"


def _readiness_basis_for_compile(compile_health_payload: Dict[str, Any]) -> str:
    return str(compile_health_payload.get("summary") or "package-canon evidence is missing").strip()


def _readiness_basis_for_boundary(boundary_meta: Dict[str, Any]) -> str:
    if not boundary_meta:
        return "no boundary-purity record exists in design canon"
    status = str(boundary_meta.get("status") or "unknown").strip().lower() or "unknown"
    score = float(boundary_meta.get("score") or 0.0)
    reason = str(boundary_meta.get("reason") or "").strip()
    summary = f"design canon marks the repo {status} at {score:.2f}"
    return f"{summary}; {reason}".strip("; ")


def _public_promotion_applicable(deployment: Dict[str, Any]) -> bool:
    status = str(deployment.get("status") or "").strip().lower()
    visibility = str(deployment.get("visibility") or "").strip().lower()
    promotion_stage = str(deployment.get("promotion_stage") or deployment_promotion_stage(status)).strip().lower()
    target_url = str(deployment.get("target_url") or "").strip()
    if status == "internal" or visibility == "internal":
        return False
    if promotion_stage == "internal":
        return False
    if visibility == "public":
        return True
    if target_url:
        return True
    return promotion_stage not in {"undeclared", "planned", "internal"}


def derive_project_readiness(
    *,
    project_id: str,
    repo_slug: str,
    lifecycle: str,
    runtime_status: str,
    runtime_completion_state: str,
    compile_summary_payload: Dict[str, Any],
    compile_health_payload: Dict[str, Any],
    deployment: Optional[Dict[str, Any]] = None,
    boundary_meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    deployment_payload = dict(deployment or {})
    promotion_stage = str(
        deployment_payload.get("promotion_stage")
        or deployment_promotion_stage(deployment_payload.get("status"))
    ).strip().lower() or "undeclared"
    boundary = dict(boundary_meta or {})
    boundary_status = str(boundary.get("status") or "").strip().lower()
    boundary_score = float(boundary.get("score") or 0.0)
    repo_local_complete_evidence = runtime_completion_state in {"runtime_complete", "scaffold_complete", "signed_off", "signoff_only"}
    package_canonical_evidence = str(compile_health_payload.get("status") or "").strip().lower() in {"ready", "not_required"}
    boundary_pure_evidence = boundary_status == "healthy" or boundary_score >= BOUNDARY_PURE_SCORE_FLOOR
    public_promotion_applicable = _public_promotion_applicable(deployment_payload)
    publicly_promoted_evidence = promotion_stage in PROMOTED_DEPLOYMENT_STAGES
    checks = {
        "repo_local_complete": {
            "evidence_met": repo_local_complete_evidence,
            "basis": _readiness_basis_for_runtime(runtime_status, runtime_completion_state),
        },
        "package_canonical": {
            "evidence_met": package_canonical_evidence,
            "basis": _readiness_basis_for_compile(compile_health_payload),
        },
        "boundary_pure": {
            "evidence_met": boundary_pure_evidence,
            "basis": _readiness_basis_for_boundary(boundary),
            "status": boundary_status or "unknown",
            "score": boundary_score if boundary else None,
        },
        "publicly_promoted": {
            "evidence_met": publicly_promoted_evidence,
            "applicable": public_promotion_applicable,
            "basis": (
                f"deployment promotion stage is {promotion_stage}"
                if public_promotion_applicable
                else "no public promotion gate applies to this repo"
            ),
            "promotion_stage": promotion_stage,
        },
    }
    stage_rank = 0
    for stage_name in READINESS_ORDER:
        check = checks[stage_name]
        if stage_name == "publicly_promoted" and not bool(check.get("applicable")):
            break
        if not bool(check.get("evidence_met")):
            break
        stage_rank += 1
    stage = READINESS_ORDER[stage_rank - 1] if stage_rank > 0 else "pre_repo_local_complete"
    next_stage = ""
    if stage_rank < len(READINESS_ORDER):
        candidate = READINESS_ORDER[stage_rank]
        if candidate != "publicly_promoted" or public_promotion_applicable:
            next_stage = candidate
    terminal_stage = "publicly_promoted" if public_promotion_applicable else "boundary_pure"
    validator_checks: List[Dict[str, Any]] = []
    if publicly_promoted_evidence and not boundary_pure_evidence:
        validator_checks.append(
            {
                "kind": "deployment_ahead_of_boundary",
                "summary": "deployment is promoted beyond the repo's boundary-purity evidence",
            }
        )
    if boundary_pure_evidence and not package_canonical_evidence:
        validator_checks.append(
            {
                "kind": "boundary_ahead_of_package",
                "summary": "design canon says the repo boundary is healthy, but package-canon compile evidence is missing",
            }
        )
    if package_canonical_evidence and not repo_local_complete_evidence:
        validator_checks.append(
            {
                "kind": "package_ahead_of_repo_local",
                "summary": "package-canon evidence exists before the repo has reached repo-local complete",
            }
        )
    if stage == "pre_repo_local_complete":
        summary = f"Not repo-local complete yet. {checks['repo_local_complete']['basis']}."
    elif stage == "repo_local_complete":
        summary = f"Repo-local complete, but package-canonical evidence is not locked. {checks['package_canonical']['basis']}."
    elif stage == "package_canonical":
        summary = f"Package-canonical, but boundary purity is not proven. {checks['boundary_pure']['basis']}."
    elif stage == "boundary_pure" and public_promotion_applicable:
        summary = f"Boundary-pure, but the public surface is still {promotion_stage}. {checks['publicly_promoted']['basis']}."
    elif stage == "boundary_pure":
        summary = "Boundary-pure. No public promotion gate applies to this repo."
    else:
        summary = f"Publicly promoted. {checks['publicly_promoted']['basis']}."
    out_of_order_evidence = [name for name, payload in checks.items() if bool(payload.get("evidence_met")) and READINESS_ORDER.index(name) >= stage_rank]
    return {
        "project_id": project_id,
        "repo_slug": repo_slug,
        "lifecycle": lifecycle,
        "stage": stage,
        "label": READINESS_LABELS.get(stage, stage.replace("_", " ").title()),
        "summary": summary,
        "next_stage": next_stage,
        "next_label": READINESS_LABELS.get(next_stage, next_stage.replace("_", " ").title()) if next_stage else "",
        "terminal_stage": terminal_stage,
        "final_claim_allowed": stage == terminal_stage,
        "checks": checks,
        "validator_checks": validator_checks,
        "warning_count": len(validator_checks),
        "boundary": boundary,
        "compile": {
            "status": str(compile_health_payload.get("status") or "unknown"),
            "summary": str(compile_health_payload.get("summary") or ""),
            "published_at": str(compile_summary_payload.get("published_at") or ""),
        },
        "deployment": {
            "status": str(deployment_payload.get("status") or ""),
            "promotion_stage": promotion_stage,
            "target_url": str(deployment_payload.get("target_url") or ""),
            "visibility": str(deployment_payload.get("visibility") or ""),
        },
        "out_of_order_evidence": out_of_order_evidence,
    }


def derive_group_deployment_readiness(*, group_id: str, deployment: Optional[Dict[str, Any]], owner_projects: List[Dict[str, Any]]) -> Dict[str, Any]:
    deployment_payload = dict(deployment or {})
    promotion_stage = str(
        deployment_payload.get("promotion_stage")
        or deployment_promotion_stage(deployment_payload.get("status"))
    ).strip().lower() or "undeclared"
    public_promotion_applicable = _public_promotion_applicable(deployment_payload)
    relevant_owners = []
    for project in owner_projects:
        readiness = dict(project.get("readiness") or {})
        if not readiness:
            continue
        relevant_owners.append(
            {
                "id": str(project.get("id") or ""),
                "stage": str(readiness.get("stage") or ""),
                "label": str(readiness.get("label") or ""),
                "boundary_pure": bool(((readiness.get("checks") or {}).get("boundary_pure") or {}).get("evidence_met")),
            }
        )
    blocking_owner_projects = _unique_preserve([project["id"] for project in relevant_owners if not project["boundary_pure"]])
    can_claim_publicly_promoted = bool(
        public_promotion_applicable
        and promotion_stage in PROMOTED_DEPLOYMENT_STAGES
        and not blocking_owner_projects
    )
    if not public_promotion_applicable:
        summary = "No public promotion gate applies to this deployment surface."
    elif can_claim_publicly_promoted:
        summary = f"Deployment is publicly promoted at {promotion_stage} and every owner project is boundary-pure."
    elif promotion_stage not in PROMOTED_DEPLOYMENT_STAGES:
        summary = f"Deployment is still {promotion_stage}; public promotion is not yet claimed."
    else:
        summary = "Deployment is promoted, but one or more owner projects are not boundary-pure yet."
    return {
        "group_id": group_id,
        "promotion_stage": promotion_stage,
        "public_promotion_applicable": public_promotion_applicable,
        "publicly_promoted": can_claim_publicly_promoted,
        "blocking_owner_projects": blocking_owner_projects,
        "owner_projects": relevant_owners,
        "summary": summary,
    }
