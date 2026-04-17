from __future__ import annotations

import os
import json
import subprocess
import sys
from pathlib import Path

import yaml

from scripts import materialize_status_plane as materialize_status_plane_module


SCRIPT = Path("/docker/fleet/scripts/materialize_status_plane.py")


def _script_env(tmp_path: Path) -> dict[str, str]:
    env = dict(os.environ)
    env["FLEET_REBUILDER_STATE_DIR"] = str(tmp_path / "rebuilder")
    return env


def test_flagship_claim_status_reports_readiness_plane_gaps_when_coverage_is_green(
    monkeypatch, tmp_path: Path
) -> None:
    readiness_path = tmp_path / "FLAGSHIP_PRODUCT_READINESS.generated.json"
    readiness_path.write_text(
        json.dumps(
            {
                "status": "fail",
                "warning_keys": [],
                "flagship_readiness_audit": {"warning_coverage_keys": []},
                "coverage": {
                    "desktop_client": "ready",
                    "fleet_and_operator_loop": "ready",
                },
                "readiness_planes": {
                    "structural_ready": {"status": "ready"},
                    "flagship_ready": {"status": "warning"},
                    "veteran_ready": {"status": "warning"},
                },
                "quality_policy": {
                    "bar": "top_flagship_grade",
                    "whole_project_frontier_required": True,
                    "feedback_autofix_loop_required": True,
                    "accept_lowered_standards": False,
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(materialize_status_plane_module, "FLAGSHIP_READINESS_PATH", readiness_path)

    claim = materialize_status_plane_module._flagship_claim_status()

    assert claim["status"] == "fail"
    assert claim["warning_keys"] == ["flagship_ready", "veteran_ready"]


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


def test_materialize_status_plane_hydrates_projects_from_config_when_status_snapshot_is_empty(tmp_path: Path) -> None:
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
        "repo_local_complete": 0,
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
    payload = yaml.safe_load(out_path.read_text(encoding="utf-8"))
    ids = {str(item.get("id") or "").strip() for item in payload.get("projects") or []}
    assert "ui" in ids
    assert "hub" in ids
    assert "hub-registry" in ids
    assert sum(int(v) for v in payload["readiness_summary"]["counts"].values()) == len(ids)


def test_ensure_project_inventory_upgrades_snapshot_stage_from_local_compile_evidence(monkeypatch, tmp_path: Path) -> None:
    config_dir = tmp_path / "config" / "projects"
    group_config = tmp_path / "config" / "groups.yaml"
    project_root = tmp_path / "fleet-project"
    published_dir = project_root / ".codex-studio" / "published"
    config_dir.mkdir(parents=True, exist_ok=True)
    published_dir.mkdir(parents=True, exist_ok=True)
    group_config.parent.mkdir(parents=True, exist_ok=True)
    group_config.write_text("project_groups: []\n", encoding="utf-8")
    (config_dir / "fleet.yaml").write_text(
        f"""
id: fleet
enabled: true
lifecycle: live
path: {project_root}
design_doc: {project_root / "README.md"}
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (project_root / "README.md").write_text("# Fleet\n", encoding="utf-8")
    (published_dir / "compile.manifest.json").write_text(
        json.dumps(
            {
                "artifacts": ["WORKPACKAGES.generated.yaml", "STATUS_PLANE.generated.yaml"],
                "dispatchable_truth_ready": True,
                "published_at": "2026-04-04T18:11:45Z",
                "stages": {
                    "design_compile": True,
                    "policy_compile": True,
                    "execution_compile": True,
                    "package_compile": True,
                    "capacity_compile": True,
                },
                "lifecycle": "live",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (published_dir / "WORKPACKAGES.generated.yaml").write_text(
        "source_queue_fingerprint: 97d170e1550eee4afc0af065b78cda302a97674c\nwork_packages: []\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(materialize_status_plane_module, "PROJECT_CONFIG_DIR", config_dir)
    monkeypatch.setattr(materialize_status_plane_module, "GROUP_CONFIG_PATH", group_config)

    admin_status = {
        "generated_at": "2026-04-04T00:00:00Z",
        "public_status": {
            "generated_at": "2026-04-04T00:00:00Z",
            "readiness_summary": {
                "counts": {
                    "pre_repo_local_complete": 0,
                    "repo_local_complete": 1,
                    "package_canonical": 0,
                    "boundary_pure": 0,
                    "publicly_promoted": 0,
                },
                "warning_count": 0,
                "final_claim_ready": 0,
            },
        },
        "projects": [
            {
                "id": "fleet",
                "readiness": {
                    "stage": "repo_local_complete",
                    "terminal_stage": "publicly_promoted",
                    "final_claim_allowed": False,
                    "warning_count": 0,
                },
            }
        ],
        "groups": [],
    }

    hydrated = materialize_status_plane_module._ensure_project_inventory(admin_status)
    project = hydrated["projects"][0]
    assert project["readiness"]["stage"] == "package_canonical"
    counts = hydrated["public_status"]["readiness_summary"]["counts"]
    assert counts["repo_local_complete"] == 0
    assert counts["package_canonical"] == 1


def test_ensure_project_inventory_hydrates_groups_from_group_config(monkeypatch, tmp_path: Path) -> None:
    config_dir = tmp_path / "config" / "projects"
    group_config = tmp_path / "config" / "groups.yaml"
    config_dir.mkdir(parents=True, exist_ok=True)
    group_config.parent.mkdir(parents=True, exist_ok=True)
    group_config.write_text(
        """
project_groups:
  - id: chummer-vnext
    lifecycle: live
    deployment:
      public_surface:
        status: public
        promotion_stage: promoted_preview
        access_posture: public
""".strip()
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(materialize_status_plane_module, "PROJECT_CONFIG_DIR", config_dir)
    monkeypatch.setattr(materialize_status_plane_module, "GROUP_CONFIG_PATH", group_config)

    admin_status = {
        "generated_at": "2026-04-04T00:00:00Z",
        "public_status": {
            "generated_at": "2026-04-04T00:00:00Z",
            "readiness_summary": {
                "counts": {
                    "pre_repo_local_complete": 0,
                    "repo_local_complete": 0,
                    "package_canonical": 0,
                    "boundary_pure": 0,
                    "publicly_promoted": 0,
                },
                "warning_count": 0,
                "final_claim_ready": 0,
            },
        },
        "projects": [],
        "groups": [],
    }

    hydrated = materialize_status_plane_module._ensure_project_inventory(admin_status)
    assert len(hydrated["groups"]) == 1
    assert hydrated["groups"][0]["id"] == "chummer-vnext"
    assert hydrated["groups"][0]["deployment"]["status"] == "public"
    assert hydrated["groups"][0]["deployment_readiness"]["publicly_promoted"] is True


def test_hub_registry_fallback_stage_uses_release_channel_evidence(monkeypatch, tmp_path: Path) -> None:
    config_dir = tmp_path / "config" / "projects"
    published_dir = tmp_path / "hub-registry" / ".codex-studio" / "published"
    config_dir.mkdir(parents=True, exist_ok=True)
    published_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "hub-registry.yaml").write_text(
        f"""
id: hub-registry
enabled: true
lifecycle: dispatchable
path: {tmp_path / "hub-registry"}
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (published_dir / "RELEASE_CHANNEL.generated.json").write_text(
        json.dumps(
            {
                "status": "published",
                "releaseProof": {
                    "status": "passed",
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(materialize_status_plane_module, "PROJECT_CONFIG_DIR", config_dir)

    rows = materialize_status_plane_module._load_project_config_rows()
    assert len(rows) == 1
    assert rows[0]["id"] == "hub-registry"
    assert rows[0]["readiness"]["stage"] == "boundary_pure"


def test_hub_registry_fallback_stage_stays_pre_repo_without_release_proof(monkeypatch, tmp_path: Path) -> None:
    config_dir = tmp_path / "config" / "projects"
    published_dir = tmp_path / "hub-registry" / ".codex-studio" / "published"
    config_dir.mkdir(parents=True, exist_ok=True)
    published_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "hub-registry.yaml").write_text(
        f"""
id: hub-registry
enabled: true
lifecycle: dispatchable
path: {tmp_path / "hub-registry"}
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (published_dir / "RELEASE_CHANNEL.generated.json").write_text(
        json.dumps(
            {
                "status": "published",
                "releaseProof": {
                    "status": "failed",
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(materialize_status_plane_module, "PROJECT_CONFIG_DIR", config_dir)

    rows = materialize_status_plane_module._load_project_config_rows()
    assert len(rows) == 1
    assert rows[0]["id"] == "hub-registry"
    assert rows[0]["readiness"]["stage"] == "repo_local_complete"


def test_core_fallback_stage_uses_import_parity_and_engine_proof(monkeypatch, tmp_path: Path) -> None:
    config_dir = tmp_path / "config" / "projects"
    published_dir = tmp_path / "core" / ".codex-studio" / "published"
    config_dir.mkdir(parents=True, exist_ok=True)
    published_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "core.yaml").write_text(
        f"""
id: core
enabled: true
lifecycle: live
path: {tmp_path / "core"}
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (published_dir / "IMPORT_PARITY_CERTIFICATION.generated.json").write_text(
        json.dumps({"status": "passed"}) + "\n",
        encoding="utf-8",
    )
    (published_dir / "ENGINE_PROOF_PACK.generated.json").write_text(
        json.dumps({"status": "passed"}) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(materialize_status_plane_module, "PROJECT_CONFIG_DIR", config_dir)

    rows = materialize_status_plane_module._load_project_config_rows()
    assert len(rows) == 1
    assert rows[0]["id"] == "core"
    assert rows[0]["readiness"]["stage"] == "boundary_pure"


def test_core_fallback_stage_stays_repo_local_without_passing_core_proofs(monkeypatch, tmp_path: Path) -> None:
    config_dir = tmp_path / "config" / "projects"
    published_dir = tmp_path / "core" / ".codex-studio" / "published"
    config_dir.mkdir(parents=True, exist_ok=True)
    published_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "core.yaml").write_text(
        f"""
id: core
enabled: true
lifecycle: live
path: {tmp_path / "core"}
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (published_dir / "IMPORT_PARITY_CERTIFICATION.generated.json").write_text(
        json.dumps({"status": "failed"}) + "\n",
        encoding="utf-8",
    )
    (published_dir / "ENGINE_PROOF_PACK.generated.json").write_text(
        json.dumps({"status": "passed"}) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(materialize_status_plane_module, "PROJECT_CONFIG_DIR", config_dir)

    rows = materialize_status_plane_module._load_project_config_rows()
    assert len(rows) == 1
    assert rows[0]["id"] == "core"
    assert rows[0]["readiness"]["stage"] == "repo_local_complete"


def test_core_fallback_stage_stays_repo_local_without_engine_proof(monkeypatch, tmp_path: Path) -> None:
    config_dir = tmp_path / "config" / "projects"
    published_dir = tmp_path / "core" / ".codex-studio" / "published"
    config_dir.mkdir(parents=True, exist_ok=True)
    published_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "core.yaml").write_text(
        f"""
id: core
enabled: true
lifecycle: live
path: {tmp_path / "core"}
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (published_dir / "IMPORT_PARITY_CERTIFICATION.generated.json").write_text(
        json.dumps({"status": "passed"}) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(materialize_status_plane_module, "PROJECT_CONFIG_DIR", config_dir)

    rows = materialize_status_plane_module._load_project_config_rows()
    assert len(rows) == 1
    assert rows[0]["id"] == "core"
    assert rows[0]["readiness"]["stage"] == "repo_local_complete"


def test_fleet_fallback_stage_uses_dispatchable_truth_and_support_contract(monkeypatch, tmp_path: Path) -> None:
    config_dir = tmp_path / "config" / "projects"
    project_root = tmp_path / "fleet"
    published_dir = project_root / ".codex-studio" / "published"
    config_dir.mkdir(parents=True, exist_ok=True)
    published_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "fleet.yaml").write_text(
        f"""
id: fleet
enabled: true
lifecycle: live
path: {project_root}
design_doc: {project_root / "README.md"}
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (project_root / "README.md").write_text("# Fleet\n", encoding="utf-8")
    (published_dir / "compile.manifest.json").write_text(
        json.dumps(
            {
                "dispatchable_truth_ready": True,
                "artifacts": [
                    "STATUS_PLANE.generated.yaml",
                    "PROGRESS_REPORT.generated.json",
                    "PROGRESS_HISTORY.generated.json",
                    "SUPPORT_CASE_PACKETS.generated.json",
                    "JOURNEY_GATES.generated.json",
                ],
                "stages": {
                    "design_compile": True,
                    "policy_compile": True,
                    "execution_compile": True,
                    "package_compile": True,
                    "capacity_compile": True,
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (published_dir / "SUPPORT_CASE_PACKETS.generated.json").write_text(
        json.dumps(
            {
                "contract_name": "fleet.support_case_packets",
                "schema_version": 1,
                "generated_at": "2026-04-04T18:30:00Z",
                "summary": {},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(materialize_status_plane_module, "PROJECT_CONFIG_DIR", config_dir)

    rows = materialize_status_plane_module._load_project_config_rows()
    assert len(rows) == 1
    assert rows[0]["id"] == "fleet"
    assert rows[0]["readiness"]["stage"] == "boundary_pure"


def test_fleet_fallback_stage_stays_package_without_dispatchable_truth(monkeypatch, tmp_path: Path) -> None:
    config_dir = tmp_path / "config" / "projects"
    project_root = tmp_path / "fleet"
    published_dir = project_root / ".codex-studio" / "published"
    config_dir.mkdir(parents=True, exist_ok=True)
    published_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "fleet.yaml").write_text(
        f"""
id: fleet
enabled: true
lifecycle: live
path: {project_root}
design_doc: {project_root / "README.md"}
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (project_root / "README.md").write_text("# Fleet\n", encoding="utf-8")
    (published_dir / "compile.manifest.json").write_text(
        json.dumps(
            {
                "dispatchable_truth_ready": False,
                "artifacts": [
                    "STATUS_PLANE.generated.yaml",
                    "PROGRESS_REPORT.generated.json",
                    "PROGRESS_HISTORY.generated.json",
                    "SUPPORT_CASE_PACKETS.generated.json",
                    "JOURNEY_GATES.generated.json",
                ],
                "stages": {
                    "design_compile": True,
                    "policy_compile": True,
                    "execution_compile": True,
                    "package_compile": True,
                    "capacity_compile": True,
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (published_dir / "SUPPORT_CASE_PACKETS.generated.json").write_text(
        json.dumps(
            {
                "contract_name": "fleet.support_case_packets",
                "schema_version": 1,
                "generated_at": "2026-04-04T18:30:00Z",
                "summary": {},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(materialize_status_plane_module, "PROJECT_CONFIG_DIR", config_dir)

    rows = materialize_status_plane_module._load_project_config_rows()
    assert len(rows) == 1
    assert rows[0]["id"] == "fleet"
    assert rows[0]["readiness"]["stage"] == "package_canonical"


def test_media_factory_fallback_stage_uses_release_and_publication_proofs(monkeypatch, tmp_path: Path) -> None:
    config_dir = tmp_path / "config" / "projects"
    published_dir = tmp_path / "media-factory" / ".codex-studio" / "published"
    config_dir.mkdir(parents=True, exist_ok=True)
    published_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "media-factory.yaml").write_text(
        f"""
id: media-factory
enabled: true
lifecycle: dispatchable
path: {tmp_path / "media-factory"}
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (published_dir / "MEDIA_LOCAL_RELEASE_PROOF.generated.json").write_text(
        json.dumps({"status": "passed"}) + "\n",
        encoding="utf-8",
    )
    (published_dir / "ARTIFACT_PUBLICATION_CERTIFICATION.generated.json").write_text(
        json.dumps({"status": "pass"}) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(materialize_status_plane_module, "PROJECT_CONFIG_DIR", config_dir)

    rows = materialize_status_plane_module._load_project_config_rows()
    assert len(rows) == 1
    assert rows[0]["id"] == "media-factory"
    assert rows[0]["readiness"]["stage"] == "boundary_pure"


def test_media_factory_fallback_stage_stays_repo_local_without_passing_proofs(monkeypatch, tmp_path: Path) -> None:
    config_dir = tmp_path / "config" / "projects"
    published_dir = tmp_path / "media-factory" / ".codex-studio" / "published"
    config_dir.mkdir(parents=True, exist_ok=True)
    published_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "media-factory.yaml").write_text(
        f"""
id: media-factory
enabled: true
lifecycle: dispatchable
path: {tmp_path / "media-factory"}
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (published_dir / "MEDIA_LOCAL_RELEASE_PROOF.generated.json").write_text(
        json.dumps({"status": "passed"}) + "\n",
        encoding="utf-8",
    )
    (published_dir / "ARTIFACT_PUBLICATION_CERTIFICATION.generated.json").write_text(
        json.dumps({"status": "failed"}) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(materialize_status_plane_module, "PROJECT_CONFIG_DIR", config_dir)

    rows = materialize_status_plane_module._load_project_config_rows()
    assert len(rows) == 1
    assert rows[0]["id"] == "media-factory"
    assert rows[0]["readiness"]["stage"] == "repo_local_complete"


def test_ui_kit_fallback_stage_uses_local_release_proof(monkeypatch, tmp_path: Path) -> None:
    config_dir = tmp_path / "config" / "projects"
    published_dir = tmp_path / "ui-kit" / ".codex-studio" / "published"
    config_dir.mkdir(parents=True, exist_ok=True)
    published_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "ui-kit.yaml").write_text(
        f"""
id: ui-kit
enabled: true
lifecycle: scaffold
path: {tmp_path / "ui-kit"}
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (published_dir / "UI_KIT_LOCAL_RELEASE_PROOF.generated.json").write_text(
        json.dumps({"status": "passed"}) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(materialize_status_plane_module, "PROJECT_CONFIG_DIR", config_dir)

    rows = materialize_status_plane_module._load_project_config_rows()
    assert len(rows) == 1
    assert rows[0]["id"] == "ui-kit"
    assert rows[0]["readiness"]["stage"] == "boundary_pure"


def test_ui_kit_fallback_stage_stays_repo_local_without_passing_release_proof(monkeypatch, tmp_path: Path) -> None:
    config_dir = tmp_path / "config" / "projects"
    published_dir = tmp_path / "ui-kit" / ".codex-studio" / "published"
    config_dir.mkdir(parents=True, exist_ok=True)
    published_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "ui-kit.yaml").write_text(
        f"""
id: ui-kit
enabled: true
lifecycle: scaffold
path: {tmp_path / "ui-kit"}
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (published_dir / "UI_KIT_LOCAL_RELEASE_PROOF.generated.json").write_text(
        json.dumps({"status": "failed"}) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(materialize_status_plane_module, "PROJECT_CONFIG_DIR", config_dir)

    rows = materialize_status_plane_module._load_project_config_rows()
    assert len(rows) == 1
    assert rows[0]["id"] == "ui-kit"
    assert rows[0]["readiness"]["stage"] == "repo_local_complete"


def test_hub_fallback_stage_uses_campaign_os_and_public_deployment_proofs(monkeypatch, tmp_path: Path) -> None:
    config_dir = tmp_path / "config" / "projects"
    published_dir = tmp_path / "hub" / ".codex-studio" / "published"
    config_dir.mkdir(parents=True, exist_ok=True)
    published_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "hub.yaml").write_text(
        f"""
id: hub
enabled: true
lifecycle: live
path: {tmp_path / "hub"}
deployment:
  status: public
  promotion_stage: promoted_preview
  access_posture: public
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (published_dir / "HUB_LOCAL_RELEASE_PROOF.generated.json").write_text(
        json.dumps({"status": "passed"}) + "\n",
        encoding="utf-8",
    )
    (published_dir / "HUB_CAMPAIGN_OS_LOCAL_PROOF.generated.json").write_text(
        json.dumps({"status": "pass"}) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(materialize_status_plane_module, "PROJECT_CONFIG_DIR", config_dir)

    rows = materialize_status_plane_module._load_project_config_rows()
    assert len(rows) == 1
    assert rows[0]["id"] == "hub"
    assert rows[0]["readiness"]["stage"] == "publicly_promoted"


def test_mobile_fallback_stage_stays_package_without_public_deployment(monkeypatch, tmp_path: Path) -> None:
    config_dir = tmp_path / "config" / "projects"
    published_dir = tmp_path / "mobile" / ".codex-studio" / "published"
    config_dir.mkdir(parents=True, exist_ok=True)
    published_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "mobile.yaml").write_text(
        f"""
id: mobile
enabled: true
lifecycle: dispatchable
path: {tmp_path / "mobile"}
deployment:
  status: internal
  promotion_stage: internal_only
  access_posture: internal
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (published_dir / "MOBILE_LOCAL_RELEASE_PROOF.generated.json").write_text(
        json.dumps({"status": "passed"}) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(materialize_status_plane_module, "PROJECT_CONFIG_DIR", config_dir)

    rows = materialize_status_plane_module._load_project_config_rows()
    assert len(rows) == 1
    assert rows[0]["id"] == "mobile"
    assert rows[0]["readiness"]["stage"] == "repo_local_complete"


def test_ui_fallback_stage_uses_flagship_release_gate_when_public(monkeypatch, tmp_path: Path) -> None:
    config_dir = tmp_path / "config" / "projects"
    published_dir = tmp_path / "ui" / ".codex-studio" / "published"
    config_dir.mkdir(parents=True, exist_ok=True)
    published_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "ui.yaml").write_text(
        f"""
id: ui
enabled: true
lifecycle: live
path: {tmp_path / "ui"}
deployment:
  status: public
  promotion_stage: promoted_preview
  access_posture: public
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (published_dir / "UI_FLAGSHIP_RELEASE_GATE.generated.json").write_text(
        json.dumps({"status": "pass"}) + "\n",
        encoding="utf-8",
    )
    (published_dir / "UI_LOCAL_RELEASE_PROOF.generated.json").write_text(
        json.dumps({"status": "passed"}) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(materialize_status_plane_module, "PROJECT_CONFIG_DIR", config_dir)

    rows = materialize_status_plane_module._load_project_config_rows()
    assert len(rows) == 1
    assert rows[0]["id"] == "ui"
    assert rows[0]["readiness"]["stage"] == "publicly_promoted"


def test_ui_fallback_stage_stays_repo_local_when_flagship_gate_fails(monkeypatch, tmp_path: Path) -> None:
    config_dir = tmp_path / "config" / "projects"
    published_dir = tmp_path / "ui" / ".codex-studio" / "published"
    config_dir.mkdir(parents=True, exist_ok=True)
    published_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "ui.yaml").write_text(
        f"""
id: ui
enabled: true
lifecycle: live
path: {tmp_path / "ui"}
deployment:
  status: public
  promotion_stage: promoted_preview
  access_posture: public
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (published_dir / "UI_FLAGSHIP_RELEASE_GATE.generated.json").write_text(
        json.dumps({"status": "fail"}) + "\n",
        encoding="utf-8",
    )
    (published_dir / "UI_LOCAL_RELEASE_PROOF.generated.json").write_text(
        json.dumps({"status": "passed"}) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(materialize_status_plane_module, "PROJECT_CONFIG_DIR", config_dir)

    rows = materialize_status_plane_module._load_project_config_rows()
    assert len(rows) == 1
    assert rows[0]["id"] == "ui"
    assert rows[0]["readiness"]["stage"] == "repo_local_complete"


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
