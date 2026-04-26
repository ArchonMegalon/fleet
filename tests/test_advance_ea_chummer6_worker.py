import importlib.util
from pathlib import Path


MODULE_PATH = Path("/docker/fleet/scripts/advance_ea_chummer6_worker.py")


def _load_module():
    spec = importlib.util.spec_from_file_location("advance_ea_chummer6_worker", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)  # type: ignore[attr-defined]
    return module


def test_embedded_worker_imports_yaml_for_status_plane_parsing() -> None:
    module = _load_module()
    worker_script = str(module.WORKER_SCRIPT)

    assert "import yaml" in worker_script
    assert "STATUS_PLANE.generated.yaml" in worker_script


def test_embedded_worker_uses_status_plane_as_prompt_source() -> None:
    module = _load_module()
    worker_script = str(module.WORKER_SCRIPT)

    assert "Canonical input: STATUS_PLANE.generated.yaml." in worker_script
    assert "Canonical input: STATUS_PLANE.generated.yaml for visible public posture." in worker_script


def test_status_plane_prompt_sources_fail_loud_without_artifact() -> None:
    module = _load_module()
    worker_script = str(module.WORKER_SCRIPT)

    assert "STATUS_PLANE.generated.yaml is unavailable or malformed; regenerate it before writing readiness claims." in worker_script
    assert "STATUS_PLANE.generated.yaml is missing readiness/deployment posture; regenerate it before writing readiness claims." in worker_script
    assert "STATUS_PLANE.generated.yaml is missing project/group rows; regenerate it before writing readiness claims." in worker_script


def test_build_page_prompts_uses_status_plane_source_for_target_pages() -> None:
    module = _load_module()
    worker_script = str(module.WORKER_SCRIPT)

    assert 'for page_id in ("current_status", "public_surfaces"):' in worker_script
    assert "prompts[page_id][\"source\"] = source" in worker_script


def test_embedded_worker_treats_magixai_adapter_as_ready() -> None:
    module = _load_module()
    worker_script = str(module.PROVIDER_READINESS_SCRIPT)

    assert 'if name == "magixai":' in worker_script
    assert 'if adapters:' in worker_script
    assert 'status = "ready"' in worker_script
    assert 'detail = "A custom AI Magicx render adapter is configured."' in worker_script


def test_embedded_worker_does_not_recommend_credential_only_provider() -> None:
    module = _load_module()
    worker_script = str(module.PROVIDER_READINESS_SCRIPT)

    assert 'PREFERRED_PROVIDER_STATUSES = {"ready", "workflow_query_only"}' in worker_script
    assert 'next(\n            (row["provider"] for row in states if row["status"] in PREFERRED_PROVIDER_STATUSES),\n            "",\n        )' in worker_script


def test_embedded_worker_loads_canonical_design_horizon_catalog() -> None:
    module = _load_module()
    worker_script = str(module.WORKER_SCRIPT)

    assert "def load_guide_catalogs()" in worker_script
    assert "merge_horizon_canon" in worker_script
    assert "canonical_horizon_slugs" in worker_script
    assert "BLACK LEDGER design canon must include public_body before EA guide generation." in worker_script


def test_black_ledger_generator_prompt_preserves_living_world_packet() -> None:
    module = _load_module()
    worker_script = str(module.WORKER_SCRIPT)

    assert "BLACK_LEDGER_GENERATOR_BRIEF" in worker_script
    assert "Open Runs and the Shadowcasters Network" in worker_script
    assert "Mission Market" in worker_script
    assert "Table Pulse or GOD Observer" in worker_script
    assert "not automatic canon" in worker_script
    assert "Seattle Tick 001" in worker_script
    assert "horizon_source_packet" in worker_script


def test_black_ledger_media_prompt_requires_world_tick_map_scene() -> None:
    module = _load_module()
    worker_script = str(module.WORKER_SCRIPT)

    assert "living city map or world-tick control surface" in worker_script
    assert 'asset_key_normalized == "black-ledger"' in worker_script
    assert "living city ledger" in worker_script
    assert "GM-only intel filters" in worker_script
