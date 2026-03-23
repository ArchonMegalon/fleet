from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml


SCRIPT = Path("/docker/fleet/scripts/materialize_status_plane.py")


def test_materialize_status_plane_from_status_json(tmp_path: Path) -> None:
    status_json = tmp_path / "admin_status.json"
    out_path = tmp_path / "STATUS_PLANE.generated.yaml"
    status_json.write_text(
        """
{
  "generated_at": "2026-03-23T00:00:00Z",
  "public_status": {
    "generated_at": "2026-03-23T00:00:00Z",
    "deployment_posture": {
      "promotion_stage": "protected_preview",
      "access_posture": "protected_preview"
    },
    "readiness_summary": {
      "counts": {
        "pre_repo_local_complete": 0,
        "repo_local_complete": 1,
        "package_canonical": 0,
        "boundary_pure": 0,
        "publicly_promoted": 0
      },
      "warning_count": 0,
      "final_claim_ready": 0
    }
  },
  "projects": [
    {
      "id": "guide",
      "lifecycle": "signoff_only",
      "runtime_status": "idle",
      "readiness": {
        "stage": "repo_local_complete",
        "terminal_stage": "publicly_promoted",
        "final_claim_allowed": false,
        "warning_count": 0
      },
      "deployment": {
        "status": "preview",
        "promotion_stage": "protected_preview",
        "access_posture": "protected_preview"
      }
    }
  ],
  "groups": [
    {
      "id": "chummer-vnext",
      "lifecycle": "dispatchable",
      "phase": "active",
      "deployment": {
        "status": "preview",
        "promotion_stage": "protected_preview",
        "access_posture": "protected_preview"
      },
      "deployment_readiness": {
        "publicly_promoted": false,
        "blocking_owner_projects": [
          "core",
          "guide"
        ]
      }
    }
  ]
}
""".strip()
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--status-json",
            str(status_json),
            "--out",
            str(out_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert out_path.is_file()

    payload = yaml.safe_load(out_path.read_text(encoding="utf-8"))
    assert payload["contract_name"] == "fleet.status_plane"
    assert payload["schema_version"] == 1
    assert payload["deployment_posture"]["access_posture"] == "protected_preview"
    assert payload["projects"][0]["id"] == "guide"
    assert payload["projects"][0]["readiness_stage"] == "repo_local_complete"
    assert payload["groups"][0]["blocking_owner_projects"] == ["core", "guide"]
