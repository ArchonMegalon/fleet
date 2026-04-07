#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from verify_chummer6_guide_surface import verify_repo


GUIDE_ROOT = Path("/docker/chummercomplete/Chummer6")
OVERRIDES_PATH = Path("/docker/fleet/state/chummer6/ea_overrides.json")
SCENE_LEDGER_PATH = Path("/docker/fleet/state/chummer6/ea_scene_ledger.json")
MEDIA_MANIFEST_PATH = Path("/docker/fleet/state/chummer6/ea_media_manifest.json")
DEFAULT_TASKS_LOG_PATH = Path("/docker/fleet/state/chummer6/TASKS_WORK_LOG.md")
ONEMIN_RUNTIME_ROOT = Path("/docker/fleet/state/browseract_bootstrap/runtime")
DOWNPLAY_TERMS = (
    "concept-stage",
    "idea for table rulings",
    "lucky artifact",
    "rough artifact",
    "rough trace",
    "safe assumption is still that almost nothing exists on purpose",
    "judge the direction first and the stray evidence second",
    "treat it as lucky evidence",
    "still mostly guide work",
)
FIRST_CONTACT_PAGE_IDS = (
    "readme",
    "start_here",
    "what_chummer6_is",
    "current_phase",
    "current_status",
    "public_surfaces",
)
CRITICAL_TARGETS = {
    "assets/hero/chummer6-hero.png": {
        "required_cast_signature": "group",
        "subject_terms": ("streetdoc", "runner", "troll", "teammate"),
        "minimum_subject_hits": 3,
    },
    "assets/pages/horizons-index.png": {
        "required_cast_signature": "group",
        "subject_terms": ("branch", "lane", "future", "district"),
        "minimum_subject_hits": 2,
    },
    "assets/horizons/karma-forge.png": {
        "required_cast_signature": "group",
        "subject_terms": ("rulesmith", "review", "rollback", "apparatus"),
        "minimum_subject_hits": 2,
    },
}
QUEUE_TASK = (
    "Drive the Chummer6 public guide to hard flagship grade: patch the EA Chummer6 guide skill and rerun the "
    "guide/media refresh until first-contact copy stops downplaying the product, flagship images tell a short "
    "Shadowrun story, and smart AR overlays anticipate the runner's next useful questions where the scene supports it."
)


def _load_json(path: Path) -> Any:
    if not path.exists() or not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _latest_asset_rows(payload: Any) -> dict[str, dict[str, Any]]:
    rows = payload.get("assets") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        return {}
    latest: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        target = str(row.get("target") or "").strip()
        if target:
            latest[target] = dict(row)
    return latest


def _first_contact_copy_findings(overrides: Any) -> list[str]:
    if not isinstance(overrides, dict):
        return ["missing_ea_overrides_state"]
    pages = overrides.get("pages")
    if not isinstance(pages, dict):
        return ["missing_ea_override_pages"]
    findings: list[str] = []
    for page_id in FIRST_CONTACT_PAGE_IDS:
        row = pages.get(page_id)
        if not isinstance(row, dict):
            findings.append(f"missing_first_contact_override:{page_id}")
            continue
        combined = " ".join(
            str(row.get(key) or "").strip()
            for key in ("intro", "body", "kicker")
            if str(row.get(key) or "").strip()
        ).lower()
        if not combined:
            findings.append(f"empty_first_contact_override:{page_id}")
            continue
        matched = [term for term in DOWNPLAY_TERMS if term in combined]
        if matched:
            findings.append(f"downplaying_copy:{page_id}:{matched[0]}")
    return findings


def _scene_story_findings(scene_ledger: Any) -> list[str]:
    assets = _latest_asset_rows(scene_ledger)
    findings: list[str] = []
    for target, rules in CRITICAL_TARGETS.items():
        row = assets.get(target)
        if row is None:
            findings.append(f"missing_story_row:{target}")
            continue
        cast_signature = str(row.get("cast_signature") or "").strip().lower()
        required_cast_signature = str(rules.get("required_cast_signature") or "").strip().lower()
        if required_cast_signature and cast_signature != required_cast_signature:
            findings.append(f"story_cast_signature:{target}:{cast_signature or 'missing'}")
        subject = str(row.get("subject") or "").strip().lower()
        subject_terms = tuple(str(value).strip().lower() for value in (rules.get("subject_terms") or ()) if str(value).strip())
        subject_hits = sum(1 for term in subject_terms if term in subject)
        minimum_hits = int(rules.get("minimum_subject_hits") or max(1, len(subject_terms)))
        if subject_hits < minimum_hits:
            findings.append(f"story_subject_weak:{target}:{subject_hits}/{minimum_hits}")
    return findings


def _overlay_contract_findings(media_manifest: Any) -> list[str]:
    assets = _latest_asset_rows(media_manifest)
    findings: list[str] = []
    for target in CRITICAL_TARGETS:
        row = assets.get(target)
        if row is None:
            findings.append(f"missing_overlay_manifest:{target}")
            continue
        overlay_hint = str(row.get("overlay_hint") or "").strip()
        overlay_callouts = [str(item).strip() for item in (row.get("overlay_callouts") or []) if str(item).strip()]
        scene_contract = row.get("scene_contract") if isinstance(row.get("scene_contract"), dict) else {}
        overlays = [str(item).strip() for item in (scene_contract.get("overlays") or []) if str(item).strip()]
        if not overlay_hint:
            findings.append(f"missing_overlay_hint:{target}")
        if not overlay_callouts:
            findings.append(f"missing_overlay_callouts:{target}")
        if not scene_contract:
            findings.append(f"missing_scene_contract:{target}")
        elif not overlays:
            findings.append(f"missing_scene_contract_overlays:{target}")
    return findings


def _latest_onemin_total_remaining_credits() -> int | None:
    if not ONEMIN_RUNTIME_ROOT.exists():
        return None
    aggregate_files = sorted(ONEMIN_RUNTIME_ROOT.glob("onemin_aggregate*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    for path in aggregate_files:
        payload = _load_json(path)
        if not isinstance(payload, dict):
            continue
        for key in ("sum_free_credits", "total_remaining_credits", "free_credits", "remaining_credits"):
            value = payload.get(key)
            if value in (None, ""):
                continue
            try:
                return max(0, int(float(str(value))))
            except Exception:
                continue
        slots = payload.get("slots")
        if not isinstance(slots, list):
            continue
        total = 0
        seen_value = False
        for row in slots:
            if not isinstance(row, dict):
                continue
            value = row.get("free_credits")
            if value in (None, ""):
                value = row.get("remaining_credits")
            if value in (None, ""):
                continue
            try:
                total += max(0, int(float(str(value))))
                seen_value = True
            except Exception:
                continue
        if seen_value:
            return total
    return None


def _render_tasks_work_log(*, findings: list[str]) -> str:
    rows = [
        "# Tasks Work Log",
        "",
        "## Queue",
        "",
        "| ID | Priority | Task | Owner | Status | Notes |",
        "|---|---|---|---|---|---|",
    ]
    if findings:
        note = "; ".join(findings[:6])
        rows.append(f"| Q-001 | P1 | {QUEUE_TASK} | fleet | queued | {note} |")
    return "\n".join(rows) + "\n"


def build_flagship_queue_payload(*, guide_root: Path, onemin_credit_floor: int) -> dict[str, Any]:
    findings: list[str] = []
    try:
        verify_repo(guide_root)
    except Exception as exc:
        findings.append(f"guide_surface_verify:{type(exc).__name__}:{str(exc).strip()[:220]}")
    findings.extend(_first_contact_copy_findings(_load_json(OVERRIDES_PATH)))
    findings.extend(_scene_story_findings(_load_json(SCENE_LEDGER_PATH)))
    findings.extend(_overlay_contract_findings(_load_json(MEDIA_MANIFEST_PATH)))
    total_credits = _latest_onemin_total_remaining_credits()
    return {
        "status": "fail" if findings else "pass",
        "findings": findings,
        "queue_task_count": 1 if findings else 0,
        "tasks": [QUEUE_TASK] if findings else [],
        "onemin_total_remaining_credits": total_credits,
        "onemin_credit_floor": onemin_credit_floor,
        "onemin_credit_burn_allowed": bool(total_credits is not None and total_credits >= onemin_credit_floor),
        "guide_root": str(guide_root),
        "inputs": {
            "overrides_path": str(OVERRIDES_PATH),
            "scene_ledger_path": str(SCENE_LEDGER_PATH),
            "media_manifest_path": str(MEDIA_MANIFEST_PATH),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Materialize a recurring flagship-grade queue for the Chummer6 guide lane.")
    parser.add_argument("--guide-root", default=str(GUIDE_ROOT))
    parser.add_argument("--tasks-log-out", default=str(DEFAULT_TASKS_LOG_PATH))
    parser.add_argument("--onemin-credit-floor", type=int, default=150000000)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    payload = build_flagship_queue_payload(
        guide_root=Path(args.guide_root).resolve(),
        onemin_credit_floor=max(0, int(args.onemin_credit_floor)),
    )
    tasks_log_path = Path(args.tasks_log_out).resolve()
    tasks_log_path.parent.mkdir(parents=True, exist_ok=True)
    tasks_log_path.write_text(_render_tasks_work_log(findings=list(payload.get("findings") or [])), encoding="utf-8")
    payload["tasks_log_path"] = str(tasks_log_path)
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"status={payload['status']} queue_task_count={payload['queue_task_count']} tasks_log={tasks_log_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
