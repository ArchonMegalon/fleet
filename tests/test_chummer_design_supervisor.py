from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from argparse import Namespace
from pathlib import Path

import yaml


MODULE_PATH = Path("/docker/fleet/scripts/chummer_design_supervisor.py")


def _load_module():
    spec = importlib.util.spec_from_file_location("chummer_design_supervisor", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)  # type: ignore[attr-defined]
    return module


def _write_registry(path: Path) -> None:
    path.write_text(
        yaml.safe_dump(
            {
                "waves": [
                    {"id": "W1"},
                    {"id": "W2"},
                    {"id": "W3"},
                    {"id": "W4"},
                ],
                "milestones": [
                    {
                        "id": 6,
                        "title": "Build Lab progression planner",
                        "wave": "W2",
                        "status": "in_progress",
                        "owners": ["chummer6-core", "chummer6-ui"],
                        "exit_criteria": ["Planner exists."],
                        "dependencies": [1],
                    },
                    {
                        "id": 15,
                        "title": "Artifact shelf v2",
                        "wave": "W3",
                        "status": "in_progress",
                        "owners": ["chummer6-hub", "chummer6-ui"],
                        "exit_criteria": ["Views exist."],
                        "dependencies": [11, 13],
                    },
                    {
                        "id": 18,
                        "title": "Public trust surface v3",
                        "wave": "W4",
                        "status": "in_progress",
                        "owners": ["chummer6-hub", "fleet"],
                        "exit_criteria": ["Trust rows are visible."],
                        "dependencies": [15, 17],
                    },
                    {
                        "id": 19,
                        "title": "Guided onboarding",
                        "wave": "W4",
                        "status": "not_started",
                        "owners": ["chummer6-ui", "chummer6-hub"],
                        "exit_criteria": ["Starter lane is real."],
                        "dependencies": [18],
                    },
                    {
                        "id": 20,
                        "title": "Pulse v2",
                        "wave": "W4",
                        "status": "complete",
                        "owners": ["fleet"],
                        "exit_criteria": ["Done."],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )


def _args(root: Path) -> Namespace:
    return Namespace(
        command="once",
        registry_path=str(root / "registry.yaml"),
        program_milestones_path=str(root / "PROGRAM_MILESTONES.yaml"),
        roadmap_path=str(root / "ROADMAP.md"),
        handoff_path=str(root / "NEXT_SESSION_HANDOFF.md"),
        workspace_root=str(root),
        scope_root=[str(root / "extra"), str(root / "more")],
        state_root=str(root / "state"),
        worker_bin="codex",
        worker_model="gpt-5.4",
        dry_run=False,
    )


def test_derive_context_prefers_handoff_frontier_ids() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_registry(root / "registry.yaml")
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text(
            "W3 milestone `15` plus W4 milestones `18`, `19`, and `20` remain active.\n",
            encoding="utf-8",
        )
        args = _args(root)

        context = module.derive_context(args)

        assert [item.id for item in context["frontier"]] == [15, 18, 19]
        assert [item.id for item in context["open_milestones"]] == [6, 15, 18, 19]
        assert "Frontier milestone ids to prioritize first: 15, 18, 19" in context["prompt"]
        assert str(root / "NEXT_SESSION_HANDOFF.md") in context["prompt"]


def test_default_worker_command_adds_scope_roots_and_output_file() -> None:
    module = _load_module()
    workspace = Path("/docker/fleet")
    scope_roots = [workspace, Path("/docker/chummercomplete"), Path("/docker/EA")]
    run_dir = Path("/tmp/fleet-supervisor-run")

    command = module._default_worker_command(
        worker_bin="codex",
        workspace_root=workspace,
        scope_roots=scope_roots,
        run_dir=run_dir,
        worker_model="gpt-5.4",
    )

    assert command[0:2] == ["codex", "exec"]
    assert "--add-dir" in command
    assert "/docker/chummercomplete" in command
    assert "/docker/EA" in command
    assert "-m" in command
    assert "gpt-5.4" in command
    assert str(run_dir / "last_message.txt") in command
    assert command[-1] == "-"


def test_parse_final_message_sections_reads_required_fields() -> None:
    module = _load_module()
    parsed = module._parse_final_message_sections(
        "What shipped: alpha\nWhat remains: beta\nExact blocker: none\n"
    )

    assert parsed["shipped"] == "alpha"
    assert parsed["remains"] == "beta"
    assert parsed["blocker"] == "none"


def test_run_once_dry_run_persists_state_without_launching_worker() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_registry(root / "registry.yaml")
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text(
            "W4 milestones `18` and `19` remain active.\n",
            encoding="utf-8",
        )
        args = _args(root)
        args.dry_run = True

        exit_code = module.run_once(args)

        assert exit_code == 0
        state_payload = json.loads((root / "state" / "state.json").read_text(encoding="utf-8"))
        assert state_payload["mode"] == "once"
        assert state_payload["frontier_ids"] == [18, 19]
        assert state_payload["last_run"]["worker_exit_code"] == 0
        assert state_payload["last_run"]["worker_command"][0] == "codex"
