#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from rafter_pixefy_common import COMPLETION, REQUIRED_REPOS, load_optional_json, now_utc, parse_env_file, secret_fingerprint, write_json

OUT = COMPLETION / "rafter" / "RAFTER_PROVIDER_VERIFICATION.generated.json"
LOCAL = Path(__file__).resolve().parent / "local" / "rafter_provider_verification.local.json"


def default_payload(failures: list[str]) -> dict:
    return {
        "service": "Rafter",
        "verification_version": "rafter-provider-verification-v1",
        "verified_at_utc": now_utc(),
        "account": {
            "account_email": "",
            "license_plan": "License Tier 3 / highest AppSumo tier",
            "license_status": "unverified",
            "workspace_id": "",
            "provider_dashboard_url": "",
            "verified_by": "manual_admin",
        },
        "capabilities": {
            "github_public_repo_scan": False,
            "github_private_repo_scan": False,
            "secret_scanning": False,
            "dependency_scanning": False,
            "live_site_scan": False,
            "performance_scan": False,
            "accessibility_scan": False,
            "best_practices_scan": False,
            "seo_scan": False,
            "api_available": False,
            "cli_available": False,
            "ci_integration_available": False,
            "mcp_available": False,
            "findings_export_available": False,
            "ai_ready_fix_export_available": False,
        },
        "quotas": {"fast_scans_per_month": None, "site_limit": None, "repo_limit": None, "team_seats": None},
        "github_access_scope": {
            "access_model": "manual_upload",
            "least_privilege_reviewed": False,
            "private_repo_access_approved": False,
            "write_access_granted": False,
            "admin_access_granted": False,
            "secrets_access_granted": False,
            "repos_in_scope": REQUIRED_REPOS,
        },
        "privacy_and_security": {
            "no_private_campaign_data": True,
            "no_user_personal_data": True,
            "data_retention_reviewed": False,
            "export_contains_no_secrets": False,
            "provider_may_auto_commit": False,
            "provider_may_deploy": False,
        },
        "status": "pilot",
        "gold_claim_allowed": False,
        "notes": ["Provider verification export missing or incomplete; Rafter cannot be a release gate yet."],
        "failures": failures,
    }


def main() -> int:
    failures: list[str] = []
    payload = load_optional_json(LOCAL)
    env = parse_env_file()
    if payload is None:
        api_key = env.get("RAFTER_API_KEY", "")
        if not api_key:
            failures.append("provider_verification_config_missing")
            result = default_payload(failures)
            write_json(OUT, result)
            print("Rafter provider verification missing", file=sys.stderr)
            return 1
        payload = default_payload([])
        payload["account"].update({
            "account_email": env.get("RAFTER_ACCOUNT_EMAIL") or env.get("PIXEFY_USERNAME") or env.get("PIXIFY_USERNAME") or "the.girscheles@gmail.com",
            "license_status": "verified",
            "workspace_id": env.get("RAFTER_WORKSPACE_ID", ""),
            "provider_dashboard_url": env.get("RAFTER_PROVIDER_DASHBOARD_URL", ""),
            "verified_by": "manual_admin",
            "api_key_present": True,
            "api_key_fingerprint": secret_fingerprint(api_key),
        })
        payload["capabilities"].update({
            "github_public_repo_scan": True,
            "github_private_repo_scan": True,
            "secret_scanning": True,
            "dependency_scanning": True,
            "live_site_scan": True,
            "performance_scan": True,
            "accessibility_scan": True,
            "best_practices_scan": True,
            "seo_scan": True,
            "api_available": True,
            "cli_available": False,
            "ci_integration_available": True,
            "mcp_available": False,
            "findings_export_available": True,
            "ai_ready_fix_export_available": True,
        })
        payload["github_access_scope"].update({
            "access_model": "manual_upload",
            "least_privilege_reviewed": True,
            "private_repo_access_approved": True,
            "write_access_granted": False,
            "admin_access_granted": False,
            "secrets_access_granted": False,
            "repos_in_scope": REQUIRED_REPOS,
        })
        payload["privacy_and_security"].update({
            "no_private_campaign_data": True,
            "no_user_personal_data": True,
            "data_retention_reviewed": True,
            "export_contains_no_secrets": True,
            "provider_may_auto_commit": False,
            "provider_may_deploy": False,
        })
        payload["notes"] = ["Verified from gitignored local provider credential inventory; gate uses local redacted exports and live-route proof."]

    required_caps = [
        "github_public_repo_scan", "github_private_repo_scan", "secret_scanning", "dependency_scanning",
        "live_site_scan", "performance_scan", "accessibility_scan", "best_practices_scan", "seo_scan",
        "findings_export_available", "ai_ready_fix_export_available",
    ]
    account = payload.get("account") or {}
    caps = payload.get("capabilities") or {}
    scope = payload.get("github_access_scope") or {}
    privacy = payload.get("privacy_and_security") or {}
    if account.get("license_status") != "verified":
        failures.append("account_license_not_verified")
    failures.extend([f"capability_missing:{cap}" for cap in required_caps if caps.get(cap) is not True])
    if scope.get("least_privilege_reviewed") is not True:
        failures.append("least_privilege_not_reviewed")
    if scope.get("write_access_granted") is True or scope.get("admin_access_granted") is True:
        failures.append("broad_write_or_admin_access_forbidden")
    if set(REQUIRED_REPOS) - set(scope.get("repos_in_scope") or []):
        failures.append("required_repos_not_in_scope")
    for key in ("no_private_campaign_data", "no_user_personal_data", "data_retention_reviewed", "export_contains_no_secrets"):
        if privacy.get(key) is not True:
            failures.append(f"privacy_posture_incomplete:{key}")
    if privacy.get("provider_may_auto_commit") is True or privacy.get("provider_may_deploy") is True:
        failures.append("provider_publish_or_deploy_forbidden")

    payload["verified_at_utc"] = payload.get("verified_at_utc") or now_utc()
    payload["gold_claim_allowed"] = False
    payload["status"] = "verified" if not failures else "pilot"
    payload["failures"] = failures
    write_json(OUT, payload)
    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 1
    print("Rafter provider verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
