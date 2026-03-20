#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

import yaml


ROOT = Path("/docker/fleet")
APP_PATH = ROOT / "admin" / "app.py"
ACCOUNTS_EXAMPLE_PATH = ROOT / "config" / "accounts.yaml.example"
PROJECTS_DIR = ROOT / "config" / "projects"
REQUIRED_EA_LANE_ALIASES = {
    "acct-ea-fleet": "easy",
    "acct-ea-groundwork": "groundwork",
    "acct-ea-review-light": "review_light",
    "acct-ea-jury": "jury",
    "acct-ea-repair": "repair",
    "acct-ea-core": "core",
    "acct-ea-survival": "survival",
}


def fail(message: str) -> None:
    print(f"consistency check failed: {message}", file=sys.stderr)
    raise SystemExit(1)


def load_yaml(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def check_routes(app_text: str) -> None:
    if 'def admin_dashboard() -> str:\n    return render_admin_dashboard(show_details=False)' not in app_text:
        fail("/admin is not wired to the Command Deck branch")
    if "def admin_details(" not in app_text or "render_admin_dashboard(show_details=True" not in app_text:
        fail("/admin/details is not wired to the Fleet Explorer branch")
    if "Command Deck" not in app_text:
        fail("command deck marker missing from admin/app.py")
    if "Fleet Raw Details" not in app_text:
        fail("raw details marker missing from admin/app.py")
    if "Fleet Explorer" not in app_text:
        fail("explorer marker missing from admin/app.py")
    if 'def api_admin_pause_project(project_id: str) -> RedirectResponse:' not in app_text:
        fail("project pause route missing from admin/app.py")
    if 'set_project_enabled(project_id, False)' not in app_text or 'trigger_controller_post(f"/api/projects/{project_id}/pause")' not in app_text:
        fail("project pause must disable desired state and interrupt runtime")
    if 'def api_admin_pause_group(group_id: str) -> RedirectResponse:' not in app_text:
        fail("group pause route missing from admin/app.py")
    if 'set_group_enabled(group_id, False)' not in app_text:
        fail("group pause must disable desired state")
    if 'trigger_controller_post(f"/api/projects/{project_id}/pause")' not in app_text:
        fail("group pause must interrupt member runtimes")
    if 'def api_admin_update_project_queue(' not in app_text:
        fail("project queue update route missing from admin/app.py")
    if "sync_project_queue_runtime(" not in app_text:
        fail("project queue edits must sync runtime state as well as desired state")
    if 'def api_admin_drain_group(group_id: str) -> RedirectResponse:' not in app_text:
        fail("group drain route missing from admin/app.py")
    if 'captain["admission_policy"] = "drain"' not in app_text or "save_fleet_config(config)" not in app_text:
        fail("group drain must persist captain admission policy")
    if 'def api_admin_burst_group(group_id: str) -> RedirectResponse:' not in app_text:
        fail("group burst route missing from admin/app.py")
    if 'captain["admission_policy"] = "burst"' not in app_text or 'captain["priority"] = max(int(captain.get("priority") or 0), 250)' not in app_text:
        fail("group burst must persist boosted captain posture")
    if 'def api_admin_resume_group(group_id: str) -> RedirectResponse:' not in app_text:
        fail("group resume route missing from admin/app.py")
    if 'set_group_enabled(group_id, True)' not in app_text or 'upsert_group_runtime(group_id, signoff_state="open")' not in app_text:
        fail("group resume must reopen runtime signoff state while enabling desired state")
    if 'def api_admin_signoff_group(group_id: str) -> RedirectResponse:' not in app_text:
        fail("group signoff route missing from admin/app.py")
    if 'upsert_group_runtime(group_id, signoff_state="signed_off")' not in app_text:
        fail("group signoff must persist runtime signoff state")
    if 'def api_admin_reopen_group(group_id: str) -> RedirectResponse:' not in app_text:
        fail("group reopen route missing from admin/app.py")
    if app_text.count('upsert_group_runtime(group_id, signoff_state="open")') < 2:
        fail("group reopen must restore open signoff state as well as group resume")


def account_supports_spark(account: dict[str, object]) -> bool:
    allowed_models = [str(item).strip() for item in (account.get("allowed_models") or []) if str(item).strip()]
    spark_enabled = bool(account.get("spark_enabled", "gpt-5.3-codex-spark" in allowed_models))
    return spark_enabled and ((not allowed_models) or ("gpt-5.3-codex-spark" in allowed_models))


def check_account_aliases(accounts: dict[str, object], project_cfg: dict[str, object], path: Path) -> None:
    aliases = []
    aliases.extend(project_cfg.get("accounts") or [])
    policy = dict(project_cfg.get("account_policy") or {})
    aliases.extend(policy.get("preferred_accounts") or [])
    aliases.extend(policy.get("burst_accounts") or [])
    aliases.extend(policy.get("reserve_accounts") or [])
    missing = [alias for alias in aliases if alias not in accounts]
    if missing:
        fail(f"{path.name} references undefined account aliases: {', '.join(sorted(set(map(str, missing))))}")
    if bool(policy.get("spark_enabled", True)):
        if not any(account_supports_spark(dict(accounts.get(alias) or {})) for alias in aliases):
            fail(f"{path.name} requests Spark but no referenced account can satisfy it")


def check_review_posture(project_cfg: dict[str, object], path: Path) -> None:
    review = dict(project_cfg.get("review") or {})
    mode = str(review.get("mode") or "github").strip().lower()
    trigger = str(review.get("trigger") or "manual_comment").strip().lower()
    fallback_mode = str(review.get("fallback_mode") or "local").strip().lower()
    if mode != "github":
        fail(f"{path.name} review.mode must be github, found {mode!r}")
    if trigger != "manual_comment":
        fail(f"{path.name} review.trigger must be manual_comment, found {trigger!r}")
    if fallback_mode != "local":
        fail(f"{path.name} review.fallback_mode must be local, found {fallback_mode!r}")


def check_accounts_example_lane_posture(accounts: dict[str, object]) -> None:
    for alias, expected_lane in REQUIRED_EA_LANE_ALIASES.items():
        account = dict(accounts.get(alias) or {})
        if not account:
            fail(f"accounts.yaml.example is missing required Fleet lane alias {alias}")
        lane = str(account.get("lane") or "").strip().lower()
        if lane != expected_lane:
            fail(f"{alias} must advertise lane={expected_lane!r}, found {lane!r}")
        aliases = [str(item).strip() for item in (account.get("codex_model_aliases") or []) if str(item).strip()]
        if not aliases:
            fail(f"{alias} must declare codex_model_aliases so the lane-first routing story is explicit")
    fleet_account = dict(accounts.get("acct-ea-fleet") or {})
    if not list(fleet_account.get("bridge_fallback_accounts") or []):
        fail("acct-ea-fleet must declare bridge_fallback_accounts in accounts.yaml.example")


def main() -> int:
    app_text = APP_PATH.read_text(encoding="utf-8")
    check_routes(app_text)

    accounts_example = load_yaml(ACCOUNTS_EXAMPLE_PATH) or {}
    accounts = dict(accounts_example.get("accounts") or {})
    if "acct-chatgpt-archon" not in accounts:
        fail("accounts.yaml.example is missing acct-chatgpt-archon")
    check_accounts_example_lane_posture(accounts)

    for project_name in ("core", "ui", "hub", "mobile"):
        path = PROJECTS_DIR / f"{project_name}.yaml"
        project_cfg = load_yaml(path) or {}
        check_account_aliases(accounts, project_cfg, path)
        check_review_posture(project_cfg, path)

    print("fleet consistency checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
