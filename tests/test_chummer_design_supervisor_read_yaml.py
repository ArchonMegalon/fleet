from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = Path("/docker/fleet/scripts/chummer_design_supervisor.py")


def _load_module():
    spec = importlib.util.spec_from_file_location("chummer_design_supervisor", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_read_yaml_accepts_mixed_successor_queue_format(tmp_path: Path) -> None:
    module = _load_module()
    queue = tmp_path / "NEXT_90_DAY_QUEUE_STAGING.generated.yaml"
    queue.write_text(
        "- title: Prefix item\n"
        "  work_task_id: '1.1'\n"
        "mode: append\n"
        "status: live_parallel_successor\n"
        "items:\n"
        "- title: Suffix item\n"
        "  work_task_id: '1.2'\n",
        encoding="utf-8",
    )

    payload = module._read_yaml(queue)

    assert payload["mode"] == "append"
    assert payload["status"] == "live_parallel_successor"
    assert [row["work_task_id"] for row in payload["items"]] == ["1.1", "1.2"]
