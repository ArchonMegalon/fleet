from __future__ import annotations

import os
import json
import subprocess
import sys
from pathlib import Path

import yaml


SCRIPT = Path("/docker/fleet/scripts/materialize_status_plane.py")


def _script_env(tmp_path: Path) -> dict[str, str]:
    env = dict(os.environ)
    env["FLEET_REBUILDER_STATE_DIR"] = str(tmp_path / "rebuilder")
    return env


def test_materialize_status_plane_from_status_json(tmp_path: Path) -> None:
    status_json = tmp_path / "admin_status.json"
    out_path = tmp_path / "STATUS_PLANE.generated.yaml"
    status_json.write_text(
        """
{
  "generated_at": "2026-03-23T00:00:00Z",
  "public_status": {
    "generated_at": "2026-03-23T00:00:00Z",
    "mission_snapshot": {
      "headline": "Truth -> Slice -> Review -> Land"
    },
    "queue_forecast": {
      "now": {
        "title": "Compile status plane"
      }
    },
    "capacity_forecast": {
      "overall": "steady"
    },
    "blocker_forecast": {
      "now": "none"
    },
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
    },
    "runtime_healing": {
      "generated_at": "2026-03-23T00:00:00Z",
      "enabled": true,
      "summary": {
        "alert_state": "healthy"
      },
      "services": []
    },
    "support_summary": {
      "open_case_count": 1
    },
    "publish_readiness": {
      "status": "watch",
      "reason": "Support queue still has one open case."
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
        env=_script_env(tmp_path),
    )
    assert result.returncode == 0, result.stderr
    assert out_path.is_file()

    payload = yaml.safe_load(out_path.read_text(encoding="utf-8"))
    assert payload["contract_name"] == "fleet.status_plane"
    assert payload["schema_version"] == 1
    assert payload["generated_at"]
    assert payload["generated_at"] != "2026-03-23T00:00:00Z"
    assert payload["source_public_status_generated_at"] == "2026-03-23T00:00:00Z"
    assert payload["mission_snapshot"]["headline"] == "Truth -> Slice -> Review -> Land"
    assert payload["queue_forecast"]["now"]["title"] == "Compile status plane"
    assert payload["capacity_forecast"]["overall"] == "steady"
    assert payload["blocker_forecast"]["now"] == "none"
    assert payload["deployment_posture"]["access_posture"] == "protected_preview"
    assert payload["support_summary"]["open_case_count"] == 1
    assert payload["publish_readiness"]["status"] == "watch"
    assert payload["runtime_healing"]["summary"]["alert_state"] == "healthy"
    assert payload["projects"][0]["id"] == "guide"
    assert payload["projects"][0]["readiness_stage"] == "repo_local_complete"
    assert payload["groups"][0]["blocking_owner_projects"] == ["core", "guide"]


def test_materialize_status_plane_refreshes_compile_manifest_for_published_output(tmp_path: Path) -> None:
    status_json = tmp_path / "admin_status.json"
    repo_root = tmp_path / "repo"
    out_path = repo_root / ".codex-studio" / "published" / "STATUS_PLANE.generated.yaml"
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
    },
    "runtime_healing": {
      "generated_at": "2026-03-23T00:00:00Z",
      "enabled": true,
      "summary": {
        "alert_state": "healthy"
      },
      "services": []
    }
  },
  "projects": [],
  "groups": []
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
        env=_script_env(tmp_path),
    )

    assert result.returncode == 0, result.stderr
    manifest_payload = json.loads((repo_root / ".codex-studio" / "published" / "compile.manifest.json").read_text(encoding="utf-8"))
    assert "STATUS_PLANE.generated.yaml" in manifest_payload["artifacts"]
    assert manifest_payload["stages"]["policy_compile"] is True


def test_materialize_status_plane_can_emit_snapshot_json_for_verification(tmp_path: Path) -> None:
    status_json = tmp_path / "admin_status.json"
    out_path = tmp_path / "STATUS_PLANE.generated.yaml"
    snapshot_out = tmp_path / "status_snapshot.json"
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
    },
    "runtime_healing": {
      "generated_at": "2026-03-23T00:00:00Z",
      "enabled": true,
      "summary": {
        "alert_state": "healthy"
      },
      "services": []
    }
  },
  "projects": [],
  "groups": []
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
            "--status-json-out",
            str(snapshot_out),
            "--out",
            str(out_path),
        ],
        check=False,
        capture_output=True,
        text=True,
        env=_script_env(tmp_path),
    )

    assert result.returncode == 0, result.stderr
    snapshot_payload = json.loads(snapshot_out.read_text(encoding="utf-8"))
    assert snapshot_payload["generated_at"] == "2026-03-23T00:00:00Z"
    assert snapshot_payload["public_status"]["generated_at"] == "2026-03-23T00:00:00Z"


def test_materialize_status_plane_overlays_stale_runtime_healing_escalation(tmp_path: Path) -> None:
    status_json = tmp_path / "admin_status.json"
    out_path = tmp_path / "STATUS_PLANE.generated.yaml"
    autoheal_dir = tmp_path / "rebuilder" / "autoheal"
    autoheal_dir.mkdir(parents=True, exist_ok=True)
    status_json.write_text(
        """
{
  "generated_at": "2026-03-23T00:00:00Z",
  "public_status": {
    "generated_at": "2026-03-23T00:00:00Z",
    "deployment_posture": {},
    "readiness_summary": {},
    "runtime_healing": {
      "generated_at": "2026-03-23T00:00:00Z",
      "enabled": true,
      "summary": {
        "alert_state": "action_needed",
        "alert_reason": "Runtime self-healing escalated for fleet-controller."
      },
      "services": [
        {
          "service": "fleet-controller",
          "current_state": "escalation_required"
        }
      ]
    }
  },
  "projects": [],
  "groups": []
}
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (autoheal_dir / "fleet-controller.status.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-04-01T14:47:41Z",
                "service": "fleet-controller",
                "current_state": "healthy",
                "observed_status": "healthy",
                "consecutive_failures": 0,
                "threshold": 2,
                "cooldown_active": False,
                "cooldown_remaining_seconds": 0,
                "last_result": "manual_review_required",
                "escalation_threshold": 3,
                "restart_window_count": 0,
                "total_restarts": 366,
            }
        )
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
        env=_script_env(tmp_path),
    )
    assert result.returncode == 0, result.stderr

    payload = yaml.safe_load(out_path.read_text(encoding="utf-8"))
    assert payload["runtime_healing"]["summary"]["alert_state"] == "healthy"
    assert payload["runtime_healing"]["services"][0]["current_state"] == "healthy"
