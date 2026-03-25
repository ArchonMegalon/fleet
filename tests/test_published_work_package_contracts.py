from __future__ import annotations

from pathlib import Path

import yaml


PUBLISHED_WORKPACKAGES = Path("/docker/fleet/.codex-studio/published/WORKPACKAGES.generated.yaml")


def _packages() -> list[dict]:
    payload = yaml.safe_load(PUBLISHED_WORKPACKAGES.read_text(encoding="utf-8")) or {}
    return list(payload.get("work_packages") or [])


def test_published_workpackages_expose_required_package_overlay_fields() -> None:
    packages = _packages()
    required_keys = {
        "package_id",
        "title",
        "package_kind",
        "horizon_family",
        "allowed_lanes",
        "allowed_paths",
        "denied_paths",
        "owned_surfaces",
        "dependencies",
        "max_touched_files",
    }

    assert packages
    for item in packages:
        assert required_keys <= set(item)
        assert str(item.get("package_id") or "").strip()
        assert str(item.get("package_kind") or "").strip()
        assert str(item.get("horizon_family") or "").strip()
        assert isinstance(item.get("allowed_paths"), list)
        assert isinstance(item.get("denied_paths"), list)
        assert isinstance(item.get("owned_surfaces"), list)
        assert isinstance(item.get("dependencies"), list)
        assert int(item.get("max_touched_files") or 0) > 0


def test_published_fleet_workpackages_include_real_dependency_edges() -> None:
    packages = _packages()
    package_ids = {str(item.get("package_id") or "").strip() for item in packages if str(item.get("package_id") or "").strip()}
    dependency_edges = [
        (str(item.get("package_id") or "").strip(), str(dep).strip())
        for item in packages
        for dep in (item.get("dependencies") or [])
        if str(item.get("package_id") or "").strip() and str(dep).strip()
    ]

    assert dependency_edges
    for _package_id, dependency in dependency_edges:
        assert dependency in package_ids


def test_published_ea_worker_input_package_waits_for_status_plane_source_contract() -> None:
    packages = _packages()
    by_surface = {
        str(surface).strip(): str(item.get("package_id") or "").strip()
        for item in packages
        for surface in (item.get("owned_surfaces") or [])
        if str(surface).strip()
    }
    ea_worker_package = next(
        item
        for item in packages
        if "chummer6:ea_worker_inputs" in {str(surface).strip() for surface in (item.get("owned_surfaces") or [])}
    )

    assert ea_worker_package["dependencies"] == [
        by_surface["status_plane:materialization"],
        by_surface["status_plane:verifier"],
    ]


def test_published_contract_change_package_stays_authority_only() -> None:
    packages = _packages()
    contract_package = next(item for item in packages if str(item.get("package_kind") or "") == "contract_change")

    assert contract_package["allowed_lanes"] == ["core_authority"]
    assert contract_package["required_reviewer_lane"] == "core_authority"
    assert contract_package["final_reviewer_lane"] == "core_authority"
    assert contract_package["landing_lane"] == "core_authority"
