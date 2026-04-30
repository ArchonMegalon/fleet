#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


READINESS_PATH = Path("/docker/fleet/.codex-studio/published/FLAGSHIP_PRODUCT_READINESS.generated.json")
STATE_PATH = Path("/docker/fleet/state/chummer_design_supervisor/state.json")
FRONTIER_PATH = Path("/docker/fleet/.codex-studio/published/FULL_PRODUCT_FRONTIER.generated.yaml")
AUDIT_SCRIPT_PATH = Path("/docker/chummercomplete/chummer-presentation/scripts/ai/milestones/user-journey-tester-audit.sh")
GATE_SCRIPT_PATH = Path("/docker/chummercomplete/chummer-presentation/scripts/ai/milestones/b14-flagship-ui-release-gate.sh")
SECTION_HOST_PATH = Path("/docker/chummercomplete/chummer-presentation/Chummer.Avalonia/Controls/SectionHostControl.axaml.cs")
AVALONIA_TESTS_PATH = Path("/docker/chummercomplete/chummer-presentation/Chummer.Tests/Presentation/AvaloniaFlagshipUiGateTests.cs")
NEXT90_PATH = Path("/docker/fleet/.codex-studio/published/NEXT_90_DAY_QUEUE_STAGING.generated.yaml")
VISUAL_GATE_PATH = Path("/docker/chummercomplete/chummer-presentation/.codex-studio/published/DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.generated.json")
WORKFLOW_GATE_PATH = Path("/docker/chummercomplete/chummer-presentation/.codex-studio/published/DESKTOP_WORKFLOW_EXECUTION_GATE.generated.json")

NEW_CHARACTER_TEST = "Runtime_backed_new_character_starter_attributes_match_seeded_workspace_and_omit_review_copy"
AUDIT_ASSERTIONS = (
    "starter_attributes_match_seeded_workspace",
    "section_preview_omits_review_copy",
)
REVIEW_COPY_MARKERS = (
    "Attributes Review",
    "Loadout Review",
    "Journal Review",
    "Section Review",
)


def _load_json(path: Path) -> dict[str, Any]:
    try:
        loaded = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _load_yaml(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return None


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def _git_status(repo_root: str, rel_paths: list[str]) -> str:
    if not rel_paths:
        return ""
    try:
        completed = subprocess.run(
            ["git", "-C", repo_root, "status", "--short", "--", *rel_paths],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except Exception:
        return ""
    return completed.stdout.strip()


def _git_diff_stat(repo_root: str, rel_paths: list[str]) -> str:
    if not rel_paths:
        return ""
    try:
        completed = subprocess.run(
            ["git", "-C", repo_root, "diff", "--stat", "--", *rel_paths],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except Exception:
        return ""
    return completed.stdout.strip()


def _parse_iso(value: str) -> datetime | None:
    normalized = str(value or "").strip()
    if not normalized:
        return None
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(normalized)
    except Exception:
        return None


def _age_seconds(value: str) -> int | None:
    parsed = _parse_iso(value)
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return max(0, int((datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)).total_seconds()))


def _latest_shard_stderr(state: dict[str, Any]) -> tuple[str, str]:
    latest_text = ""
    latest_path = ""
    latest_age = -1
    for item in state.get("active_runs") or []:
        if not isinstance(item, dict):
            continue
        shard = str(item.get("_shard") or "").strip()
        run_id = str(item.get("run_id") or "").strip()
        if not shard or not run_id:
            continue
        candidate = Path("/docker/fleet/state/chummer_design_supervisor") / shard / "runs" / run_id / "worker.stderr.log"
        if not candidate.is_file():
            continue
        age = _age_seconds(str(item.get("output_updated_at") or "")) or 0
        if latest_age >= 0 and age > latest_age:
            continue
        latest_age = age
        latest_path = str(candidate)
        latest_text = _read_text(candidate)
    return latest_path, latest_text


def _first_line_containing(text: str, markers: tuple[str, ...]) -> str:
    for line in text.splitlines():
        lowered = line.lower()
        if any(marker.lower() in lowered for marker in markers):
            return line.strip()
    return ""


def _finding(*, severity: str, category: str, summary: str, path: str, detail: str) -> dict[str, str]:
    return {
        "severity": severity,
        "category": category,
        "summary": summary,
        "path": path,
        "detail": detail,
    }


def main() -> int:
    readiness = _load_json(READINESS_PATH)
    state = _load_json(STATE_PATH)
    frontier = _load_yaml(FRONTIER_PATH)
    audit_script = _read_text(AUDIT_SCRIPT_PATH)
    gate_script = _read_text(GATE_SCRIPT_PATH)
    section_host = _read_text(SECTION_HOST_PATH)
    avalonia_tests = _read_text(AVALONIA_TESTS_PATH)
    next90_text = _read_text(NEXT90_PATH)

    coverage = readiness.get("coverage") if isinstance(readiness.get("coverage"), dict) else {}
    coverage_details = readiness.get("coverage_details") if isinstance(readiness.get("coverage_details"), dict) else {}
    readiness_audit = readiness.get("flagship_readiness_audit") if isinstance(readiness.get("flagship_readiness_audit"), dict) else {}
    parity_registry = readiness.get("parity_registry") if isinstance(readiness.get("parity_registry"), dict) else {}
    flagship_parity_registry = readiness.get("flagship_parity_registry") if isinstance(readiness.get("flagship_parity_registry"), dict) else {}

    frontier_items = frontier.get("frontier") if isinstance(frontier, dict) else []
    if not isinstance(frontier_items, list):
        frontier_items = []
    frontier_ids = [
        int(item.get("id"))
        for item in frontier_items
        if isinstance(item, dict) and isinstance(item.get("id"), int)
    ]
    open_ids = {int(item) for item in (state.get("open_milestone_ids") or []) if isinstance(item, int)}
    missing_frontier_ids = [item for item in frontier_ids if item not in open_ids]

    findings: list[dict[str, str]] = []
    notes: list[str] = []

    desktop_detail = coverage_details.get("desktop_client") if isinstance(coverage_details.get("desktop_client"), dict) else {}
    desktop_reasons = [str(item).strip() for item in desktop_detail.get("reasons") or [] if str(item).strip()]
    if str(coverage.get("desktop_client") or "").strip().lower() != "ready":
        findings.append(
            _finding(
                severity="high",
                category="design_gap",
                summary="`desktop_client` is still missing from flagship readiness.",
                path=str(READINESS_PATH),
                detail=" ; ".join(desktop_reasons[:3]) or "Desktop readiness is not accepted.",
            )
        )

    blocked_reasons: list[str] = []
    blocked_keys: list[str] = []
    for key in ("mobile_play_shell", "ui_kit_and_flagship_polish", "media_artifacts"):
        detail = coverage_details.get(key) if isinstance(coverage_details.get(key), dict) else {}
        status = str(coverage.get(key) or "").strip().lower()
        reasons = [str(item).strip() for item in detail.get("reasons") or [] if str(item).strip()]
        if status in {"warning", "missing"}:
            blocked_keys.append(key)
            if reasons:
                blocked_reasons.append(f"{key}: {reasons[0]}")
    if blocked_keys:
        findings.append(
            _finding(
                severity="medium",
                category="design_gap",
                summary="Remaining flagship coverage keys are still warning-level rather than closed.",
                path=str(READINESS_PATH),
                detail=" ; ".join(blocked_reasons[:3]),
            )
        )

    if missing_frontier_ids:
        findings.append(
            _finding(
                severity="high",
                category="milestone_gap",
                summary="Current flagship frontier IDs are missing from the live open milestone aggregate.",
                path=str(STATE_PATH),
                detail=f"missing_frontier_ids={missing_frontier_ids}",
            )
        )
    else:
        notes.append("No missing flagship frontier milestone IDs were found in the live open milestone aggregate.")

    audit_assertions_missing = [item for item in AUDIT_ASSERTIONS if item not in audit_script]
    gate_test_missing = NEW_CHARACTER_TEST not in gate_script or NEW_CHARACTER_TEST not in avalonia_tests
    review_copy_present = any(marker in section_host for marker in REVIEW_COPY_MARKERS)
    if audit_assertions_missing or gate_test_missing or review_copy_present:
        gap_parts: list[str] = []
        if audit_assertions_missing:
            gap_parts.append(f"missing audit assertions: {', '.join(audit_assertions_missing)}")
        if gate_test_missing:
            gap_parts.append(f"missing runtime gate test: {NEW_CHARACTER_TEST}")
        if review_copy_present:
            gap_parts.append("review-copy markers still present in SectionHostControl")
        findings.append(
            _finding(
                severity="high",
                category="workflow_gate_gap",
                summary="The visual-parity gate contract is still incomplete.",
                path=str(AUDIT_SCRIPT_PATH),
                detail=" ; ".join(gap_parts),
            )
        )
    else:
        notes.append("The visual-parity gate contract is present: audit assertions, runtime starter-attribute test, and review-copy removal are all in repo truth.")

    presentation_status = _git_status(
        "/docker/chummercomplete/chummer-presentation",
        [
            "scripts/ai/milestones/user-journey-tester-audit.sh",
            "scripts/ai/milestones/b14-flagship-ui-release-gate.sh",
            "Chummer.Tests/Presentation/AvaloniaFlagshipUiGateTests.cs",
            "Chummer.Avalonia/Controls/SectionHostControl.axaml.cs",
        ],
    )
    fleet_status = _git_status(
        "/docker/fleet",
        [
            ".codex-studio/published/FLAGSHIP_PRODUCT_READINESS.generated.json",
            ".codex-studio/published/FULL_PRODUCT_FRONTIER.generated.yaml",
        ],
    )
    if presentation_status or fleet_status:
        readiness_generated_at = str(readiness.get("generated_at") or readiness.get("generatedAt") or "").strip()
        readiness_age_seconds = _age_seconds(readiness_generated_at)
        visual_gate_status = str(_load_json(VISUAL_GATE_PATH).get("status") or "").strip().lower()
        workflow_gate_status = str(_load_json(WORKFLOW_GATE_PATH).get("status") or "").strip().lower()
        fresh_gate_publication = (
            readiness_age_seconds is not None
            and readiness_age_seconds <= 1800
            and visual_gate_status in {"pass", "passed", "ready"}
            and workflow_gate_status in {"pass", "passed", "ready"}
            and not audit_assertions_missing
            and not gate_test_missing
            and not review_copy_present
        )
        detail_parts: list[str] = []
        if presentation_status:
            detail_parts.append(f"presentation_status={presentation_status}")
        if fleet_status:
            detail_parts.append(f"fleet_status={fleet_status}")
        diff_parts: list[str] = []
        presentation_diff = _git_diff_stat(
            "/docker/chummercomplete/chummer-presentation",
            [
                "scripts/ai/milestones/user-journey-tester-audit.sh",
                "scripts/ai/milestones/b14-flagship-ui-release-gate.sh",
                "Chummer.Tests/Presentation/AvaloniaFlagshipUiGateTests.cs",
                "Chummer.Avalonia/Controls/SectionHostControl.axaml.cs",
            ],
        )
        fleet_diff = _git_diff_stat(
            "/docker/fleet",
            [
                ".codex-studio/published/FLAGSHIP_PRODUCT_READINESS.generated.json",
                ".codex-studio/published/FULL_PRODUCT_FRONTIER.generated.yaml",
            ],
        )
        if presentation_diff:
            diff_parts.append(f"presentation_diff={presentation_diff}")
        if fleet_diff:
            diff_parts.append(f"fleet_diff={fleet_diff}")
        if fresh_gate_publication:
            notes.append(
                "Visual-parity gate tightening is present in working tree and the refreshed readiness/frontier artifacts are current; remaining drift here is uncommitted local diff, not stale publication."
            )
        else:
            findings.append(
                _finding(
                    severity="medium",
                    category="workflow_gate_gap",
                    summary="Visual-parity gate tightening exists in working tree, but published readiness/frontier artifacts are still drifting.",
                    path=str(READINESS_PATH),
                    detail=" ; ".join(detail_parts + diff_parts),
                )
            )

    latest_stderr_path, latest_stderr_text = _latest_shard_stderr(state)
    active_runs = [item for item in (state.get("active_runs") or []) if isinstance(item, dict)]
    productive_active_runs_count = int(state.get("productive_active_runs_count") or 0)
    nonproductive_active_runs_count = int(state.get("nonproductive_active_runs_count") or 0)
    stale_runs = 0
    zero_message_runs = 0
    for item in active_runs:
        output_sizes = item.get("output_sizes") if isinstance(item.get("output_sizes"), dict) else {}
        if int(output_sizes.get("last_message") or 0) == 0:
            zero_message_runs += 1
        age = _age_seconds(str(item.get("output_updated_at") or ""))
        if age is not None and age >= 300:
            stale_runs += 1
    shard_issue_parts: list[str] = []
    if stale_runs:
        shard_issue_parts.append(f"stale_active_runs={stale_runs}/{len(active_runs)}")
    if zero_message_runs and nonproductive_active_runs_count > 0:
        shard_issue_parts.append(f"zero_last_message_runs={zero_message_runs}/{len(active_runs)}")
    latest_skip = _first_line_containing(latest_stderr_text, ("max_parallel_runs", "full-fallback", "waiting for upstream response"))
    if latest_skip and (nonproductive_active_runs_count > 0 or stale_runs > 0):
        shard_issue_parts.append(f"latest_stderr={latest_skip}")
    if shard_issue_parts:
        severity = "high" if nonproductive_active_runs_count >= max(1, len(active_runs)) or stale_runs else "medium"
        findings.append(
            _finding(
                severity=severity,
                category="shard_gap",
                summary="Live shard execution is still stalling or saturating before closing proof cleanly.",
                path=latest_stderr_path or str(STATE_PATH),
                detail=" ; ".join(
                    shard_issue_parts
                    + [f"productive={productive_active_runs_count}", f"nonproductive={nonproductive_active_runs_count}"]
                ),
            )
        )

    if (
        int(parity_registry.get("unresolved_family_count") or 0) == 0
        and str(readiness.get("status") or "").strip().lower() != "pass"
    ):
        findings.append(
            _finding(
                severity="medium",
                category="workflow_gate_gap",
                summary="Parity registry is formally resolved, but flagship readiness still fails on coverage and proof freshness.",
                path=str(READINESS_PATH),
                detail=(
                    f"readiness_status={readiness.get('status')} ; "
                    f"coverage_gap_keys={readiness_audit.get('coverage_gap_keys') or []} ; "
                    f"flagship_parity_registry_family_count={flagship_parity_registry.get('family_count')}"
                ),
            )
        )

    if "Run screenshot-backed parity review on the promoted desktop head" in next90_text and "Extract Chummer5a oracle baselines and veteran workflow packs" in next90_text:
        notes.append(
            "Chummer5A oracle baseline capture and screenshot-backed veteran parity review are already materialized in the successor-wave queue, so the current flagship gap is not missing parity-lab backlog."
        )

    severity_rank = {"high": 0, "medium": 1, "low": 2}
    findings.sort(key=lambda item: (severity_rank.get(item.get("severity", "low"), 3), item.get("category", ""), item.get("summary", "")))

    payload = {
        "probe_kind": "gap_audit",
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "readiness_status": str(readiness.get("status") or "").strip(),
        "coverage_gap_keys": list(readiness_audit.get("coverage_gap_keys") or []),
        "frontier_ids": frontier_ids,
        "open_milestone_ids": sorted(open_ids),
        "missing_frontier_ids": missing_frontier_ids,
        "findings": findings,
        "notes": notes,
        "active_runs_count": int(state.get("active_runs_count") or 0),
        "productive_active_runs_count": productive_active_runs_count,
        "nonproductive_active_runs_count": nonproductive_active_runs_count,
    }
    print(json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
