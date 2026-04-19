from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


UI_REPO_ROOT = Path("/docker/chummercomplete/chummer6-ui")
SCRIPT_PATH = UI_REPO_ROOT / "scripts" / "e2e-portal.sh"


def test_e2e_portal_emits_current_release_proof_contract(tmp_path: Path) -> None:
    out_path = tmp_path / "UI_LOCAL_RELEASE_PROOF.generated.json"
    env = os.environ.copy()
    env["CHUMMER_PORTAL_LOCAL_PROOF_PATH"] = str(out_path)
    env["CHUMMER_PORTAL_E2E_SKIP_EDGE_REBUILD"] = "1"
    env["CHUMMER_PORTAL_PLAYWRIGHT"] = "0"

    subprocess.run(
        ["bash", str(SCRIPT_PATH)],
        cwd=UI_REPO_ROOT,
        env=env,
        check=True,
    )

    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["contract_name"] == "chummer6-ui.local_release_proof"
    assert payload["journeys_passed"] == [
        "install_claim_restore_continue",
        "build_explain_publish",
        "campaign_session_recover_recap",
        "report_cluster_release_notify",
        "organize_community_and_close_loop",
    ]
    assert payload["proof_routes"] == [
        "/downloads/install/avalonia-linux-x64-installer",
        "/home/access",
        "/home/work",
        "/account/work",
        "/account/support",
        "/contact",
    ]
