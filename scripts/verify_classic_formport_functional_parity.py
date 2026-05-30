#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "_completion" / "full_product_reaudit_v17" / "CLASSIC_FORMPORT_FUNCTIONAL_PARITY_AUDIT.generated.json"
UI_ROOT = Path("/docker/chummercomplete/chummer-presentation")


def main() -> int:
    if not AUDIT.is_file():
        print("missing classic formport functional parity audit")
        return 1
    payload = json.loads(AUDIT.read_text(encoding="utf-8"))
    if payload.get("status") != "pass":
        print("classic formport audit is not passing")
        return 1
    requirements = payload.get("requirements")
    if not isinstance(requirements, dict):
        print("classic formport audit lacks requirements block")
        return 1
    required_true = [
        "typed_view_model",
        "typed_command_bridge",
        "no_primary_state_rows_token_matching",
        "add_edit_delete_flows",
        "context_menus",
        "keyboard_shortcuts",
        "side_by_side_screenshots",
        "veteran_user_task_review",
    ]
    failures = [key for key in required_true if requirements.get(key) is not True]
    generic_hits = payload.get("generic_projection_hits")
    if not isinstance(generic_hits, list) or generic_hits:
        failures.append("generic_projection_hits")
    checked_files = payload.get("checked_files")
    if not isinstance(checked_files, list) or len(checked_files) < 8:
        failures.append("checked_files")
    missing_files = [path for path in checked_files or [] if not Path(str(path)).exists()]
    if failures or missing_files:
        print("classic formport audit failed")
        print({"failures": failures, "missing_files": missing_files})
        return 1
    print("classic formport functional parity proof passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
