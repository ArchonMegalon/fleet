from pathlib import Path
import importlib.util


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

    assert "Status plane is unavailable or malformed; regenerate it before writing readiness claims." in worker_script
    assert "Status plane is unavailable or malformed; avoid handwritten preview/readiness claims." in worker_script


def test_build_page_prompts_uses_status_plane_source_for_target_pages() -> None:
    module = _load_module()
    worker_script = str(module.WORKER_SCRIPT)

    assert 'for page_id in ("current_status", "public_surfaces"):' in worker_script
    assert "prompts[page_id][\"source\"] = source" in worker_script
