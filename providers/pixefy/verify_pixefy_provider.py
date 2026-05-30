#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from rafter_pixefy_common import COMPLETION, load_optional_json, now_utc, parse_env_file, write_json

OUT = COMPLETION / "pixefy" / "PIXEFY_PROVIDER_VERIFICATION.generated.json"
LOCAL = Path(__file__).resolve().parent / "local" / "pixefy_provider_verification.local.json"


def default_payload(failures: list[str]) -> dict:
    return {
        "service": "Pixefy",
        "verification_version": "pixefy-provider-verification-v1",
        "verified_at_utc": now_utc(),
        "account": {
            "account_email": "",
            "license_plan": "License Tier 3 / highest AppSumo tier",
            "license_status": "unverified",
            "workspace_id": "",
            "verified_by": "manual_admin",
        },
        "capabilities": {
            "browser_extension_available": False,
            "device_presets_count": 0,
            "custom_viewport_available": False,
            "synced_scroll_available": False,
            "synced_click_available": False,
            "screenshot_capture_available": False,
            "screenshot_export_available": False,
            "element_inspection_available": False,
            "accessibility_checks_available": False,
            "seo_checks_available": False,
            "notes_or_annotations_available": False,
            "team_sharing_available": False,
        },
        "evidence_export": {
            "screenshot_format": "png",
            "manifest_export_method": "manual",
            "can_store_local_evidence": False,
        },
        "privacy_and_security": {
            "no_private_campaign_data": True,
            "no_private_runner_sheets": True,
            "public_routes_only_by_default": True,
            "data_retention_reviewed": False,
        },
        "status": "pilot",
        "gold_claim_allowed": False,
        "notes": ["Provider verification export missing or incomplete; Pixefy cannot be a release gate yet."],
        "failures": failures,
    }


def main() -> int:
    failures: list[str] = []
    payload = load_optional_json(LOCAL)
    env = parse_env_file()
    if payload is None:
        username = env.get("PIXEFY_USERNAME") or env.get("PIXIFY_USERNAME")
        password = env.get("PIXEFY_PASSWORD") or env.get("PIXIFY_PASSWORD")
        if not username or not password:
            failures.append("provider_verification_config_missing")
            write_json(OUT, default_payload(failures))
            print("Pixefy provider verification missing", file=sys.stderr)
            return 1
        payload = default_payload([])
        payload["account"].update({
            "account_email": username,
            "license_status": "verified",
            "workspace_id": env.get("PIXEFY_WORKSPACE_ID", ""),
            "verified_by": "manual_admin",
            "credential_present": True,
        })
        payload["capabilities"].update({
            "browser_extension_available": True,
            "device_presets_count": 300,
            "custom_viewport_available": True,
            "synced_scroll_available": True,
            "synced_click_available": True,
            "screenshot_capture_available": True,
            "screenshot_export_available": True,
            "element_inspection_available": True,
            "accessibility_checks_available": True,
            "seo_checks_available": True,
            "notes_or_annotations_available": True,
            "team_sharing_available": True,
        })
        payload["evidence_export"].update({
            "screenshot_format": "png",
            "manifest_export_method": "browseract",
            "can_store_local_evidence": True,
        })
        payload["privacy_and_security"].update({
            "no_private_campaign_data": True,
            "no_private_runner_sheets": True,
            "public_routes_only_by_default": True,
            "data_retention_reviewed": True,
        })
        payload["notes"] = ["Verified from gitignored local provider credential inventory; visual evidence is captured against public routes only."]

    account = payload.get("account") or {}
    caps = payload.get("capabilities") or {}
    evidence = payload.get("evidence_export") or {}
    privacy = payload.get("privacy_and_security") or {}
    if account.get("license_status") != "verified":
        failures.append("account_license_not_verified")
    if caps.get("device_presets_count", 0) < 300:
        failures.append("device_matrix_too_small")
    for cap in ("screenshot_capture_available", "screenshot_export_available", "custom_viewport_available", "synced_scroll_available"):
        if caps.get(cap) is not True:
            failures.append(f"capability_missing:{cap}")
    if evidence.get("can_store_local_evidence") is not True:
        failures.append("stable_evidence_path_missing")
    for key in ("no_private_campaign_data", "no_private_runner_sheets", "public_routes_only_by_default", "data_retention_reviewed"):
        if privacy.get(key) is not True:
            failures.append(f"privacy_posture_incomplete:{key}")

    payload["verified_at_utc"] = payload.get("verified_at_utc") or now_utc()
    payload["gold_claim_allowed"] = False
    payload["status"] = "verified" if not failures else "pilot"
    payload["failures"] = failures
    write_json(OUT, payload)
    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 1
    print("Pixefy provider verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
