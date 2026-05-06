from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = Path("/docker/fleet/scripts/next90_queue_staging.py")


def _load_module():
    spec = importlib.util.spec_from_file_location("next90_queue_staging", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_read_next90_queue_staging_yaml_accepts_mixed_prefix_and_suffix_items(tmp_path: Path) -> None:
    module = _load_module()
    queue = tmp_path / "NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
    queue.write_text(
        "- title: Prefix item\n"
        "  work_task_id: '1.1'\n"
        "mode: append\n"
        "program_wave: next_90_day_product_advance\n"
        "status: live_parallel_successor\n"
        "source_registry_path: /tmp/registry.yaml\n"
        "items:\n"
        "- title: Suffix item\n"
        "  work_task_id: '1.2'\n",
        encoding="utf-8",
    )

    payload = module.read_next90_queue_staging_yaml(queue)

    assert payload["mode"] == "append"
    assert payload["program_wave"] == "next_90_day_product_advance"
    assert payload["status"] == "live_parallel_successor"
    assert payload["source_registry_path"] == "/tmp/registry.yaml"
    assert [row["work_task_id"] for row in payload["items"]] == ["1.1", "1.2"]


def test_read_next90_queue_staging_yaml_wraps_plain_lists_as_items(tmp_path: Path) -> None:
    module = _load_module()
    queue = tmp_path / "NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
    queue.write_text(
        "- title: Only item\n"
        "  work_task_id: '2.1'\n",
        encoding="utf-8",
    )

    payload = module.read_next90_queue_staging_yaml(queue)

    assert [row["work_task_id"] for row in payload["items"]] == ["2.1"]
