from __future__ import annotations

import importlib.util
import json
import subprocess
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
        accounts_path=str(root / "accounts.yaml"),
        workspace_root=str(root),
        scope_root=[str(root / "extra"), str(root / "more")],
        state_root=str(root / "state"),
        worker_bin="codex",
        worker_model="gpt-5.4",
        fallback_worker_model=[],
        account_owner_id=[],
        account_alias=[],
        focus_owner=[],
        focus_text=[],
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


def test_derive_context_can_focus_frontier_by_owner() -> None:
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
        args.focus_owner = ["chummer6-ui"]

        context = module.derive_context(args)

        assert [item.id for item in context["frontier"]] == [15, 19]
        assert "Current steering focus:" in context["prompt"]
        assert "owner focus: chummer6-ui" in context["prompt"]


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
        assert state_payload["last_run"]["attempted_models"] == ["gpt-5.4"]


def test_launch_worker_retries_retryable_model_failure_with_fallback(monkeypatch) -> None:
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
        args.worker_model = "gpt-5.3-codex-spark"
        args.fallback_worker_model = ["gpt-5.4"]
        context = module.derive_context(args)

        calls: list[list[str]] = []

        def fake_run(command, *, input, text, capture_output, cwd, check, env=None):
            calls.append(list(command))
            message_path = Path(command[command.index("-o") + 1])
            model = command[command.index("-m") + 1]
            if model == "gpt-5.3-codex-spark":
                return subprocess.CompletedProcess(
                    command,
                    1,
                    stdout="",
                    stderr="ERROR: You've hit your usage limit for GPT-5.3-Codex-Spark.",
                )
            message_path.write_text(
                "What shipped: fallback landed\nWhat remains: follow-through\nExact blocker: none\n",
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        monkeypatch.setattr(module.subprocess, "run", fake_run)

        run = module.launch_worker(args, context, root / "state")

        assert run.worker_exit_code == 0
        assert run.attempted_models == ["gpt-5.3-codex-spark", "gpt-5.4"]
        assert run.attempted_accounts == ["default", "default"]
        assert "gpt-5.4" in run.worker_command
        assert run.shipped == "fallback landed"
        assert len(calls) == 2


def test_launch_worker_rotates_across_configured_owner_accounts(monkeypatch) -> None:
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
        auth_a = root / "acct-a.auth.json"
        auth_b = root / "acct-b.auth.json"
        auth_a.write_text('{"access_token":"a"}\n', encoding="utf-8")
        auth_b.write_text('{"access_token":"b"}\n', encoding="utf-8")
        (root / "accounts.yaml").write_text(
            yaml.safe_dump(
                {
                    "account_policy": {
                        "protected_owner_ids": ["tibor.girschele", "archon.megalon"],
                    },
                    "accounts": {
                        "acct-tibor-a": {
                            "auth_kind": "chatgpt_auth_json",
                            "auth_json_file": str(auth_a),
                            "owner_id": "tibor.girschele",
                            "health_state": "ready",
                            "spark_enabled": True,
                        },
                        "acct-archon-a": {
                            "auth_kind": "chatgpt_auth_json",
                            "auth_json_file": str(auth_b),
                            "owner_id": "archon.megalon",
                            "health_state": "ready",
                            "spark_enabled": True,
                        },
                    },
                }
            ),
            encoding="utf-8",
        )
        args = _args(root)
        args.worker_model = "gpt-5.3-codex-spark"
        args.account_owner_id = ["tibor.girschele", "archon.megalon"]
        context = module.derive_context(args)

        calls: list[tuple[list[str], str]] = []

        def fake_run(command, *, input, text, capture_output, cwd, check, env=None):
            assert env is not None
            calls.append((list(command), str(env.get("CODEX_HOME") or "")))
            message_path = Path(command[command.index("-o") + 1])
            home = Path(str(env["CODEX_HOME"]))
            auth_contents = (home / "auth.json").read_text(encoding="utf-8")
            if '"access_token":"a"' in auth_contents:
                return subprocess.CompletedProcess(
                    command,
                    1,
                    stdout="",
                    stderr="ERROR: You've hit your usage limit for GPT-5.3-Codex-Spark.",
                )
            message_path.write_text(
                "What shipped: archon lane picked up the loop\nWhat remains: follow-through\nExact blocker: none\n",
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        monkeypatch.setattr(module.subprocess, "run", fake_run)

        run = module.launch_worker(args, context, root / "state")

        assert run.worker_exit_code == 0
        assert run.selected_account_alias == "acct-archon-a"
        assert run.attempted_accounts == ["acct-tibor-a", "acct-archon-a"]
        assert run.attempted_models == ["gpt-5.3-codex-spark", "gpt-5.3-codex-spark"]
        account_runtime = json.loads((root / "state" / "account_runtime.json").read_text(encoding="utf-8"))
        assert len(account_runtime["sources"]) == 2
        assert len(calls) == 2


def test_render_trace_includes_recent_history_entries() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        state_root = root / "state"
        state_root.mkdir(parents=True, exist_ok=True)
        stderr_run_2 = state_root / "run-2.stderr.log"
        stderr_run_2.write_text(
            "worker boot\nERROR: You've hit your usage limit for GPT-5.3-Codex-Spark.\n",
            encoding="utf-8",
        )
        (state_root / "state.json").write_text(
            json.dumps(
                {
                    "updated_at": "2026-03-30T12:00:00Z",
                    "mode": "loop",
                    "open_milestone_ids": [3, 4, 5],
                    "frontier_ids": [3, 4, 5],
                    "last_run": {
                        "run_id": "run-3",
                        "worker_exit_code": 0,
                        "primary_milestone_id": 3,
                        "blocker": "",
                        "stderr_path": "",
                        "last_message_path": "/tmp/run-3.txt",
                    },
                }
            ),
            encoding="utf-8",
        )
        (state_root / "history.jsonl").write_text(
            "\n".join(
                [
                    json.dumps(
                        {
                            "run_id": "run-1",
                            "finished_at": "2026-03-30T10:00:00Z",
                            "worker_exit_code": 0,
                            "primary_milestone_id": 6,
                            "frontier_ids": [6],
                            "shipped": "planner baseline",
                            "remains": "team optimizer",
                            "blocker": "",
                        }
                    ),
                    json.dumps(
                        {
                            "run_id": "run-2",
                            "finished_at": "2026-03-30T11:00:00Z",
                            "worker_exit_code": 1,
                            "primary_milestone_id": 4,
                            "frontier_ids": [4, 5],
                            "shipped": "",
                            "remains": "prep packets",
                            "blocker": "",
                            "stderr_path": str(stderr_run_2),
                        }
                    ),
                    json.dumps(
                        {
                            "run_id": "run-3",
                            "finished_at": "2026-03-30T12:00:00Z",
                            "worker_exit_code": 0,
                            "selected_account_alias": "acct-archon-a",
                            "primary_milestone_id": 3,
                            "frontier_ids": [3, 4, 5],
                            "shipped": "roster audit trail",
                            "remains": "travel prefetch",
                            "blocker": "",
                        }
                    ),
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        history = module._read_history(state_root / "history.jsonl", limit=2)

        assert [row["run_id"] for row in history] == ["run-2", "run-3"]

        rendered = module._render_trace(
            module._read_state(state_root / "state.json"),
            history,
        )

        assert "run=run-3" in rendered
        assert "account=acct-archon-a" in rendered
        assert "frontier=3,4,5" in rendered
        assert "run=run-2" in rendered
        assert "hint=ERROR: You've hit your usage limit for GPT-5.3-Codex-Spark." in rendered
        assert "run=run-1" not in rendered


def test_failure_hint_recovers_timestamped_error_lines() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        stderr_path = root / "worker.stderr.log"
        stderr_path.write_text(
            "2026-03-30T20:45:03Z ERROR: Your access token could not be refreshed because your refresh token was already used.\n",
            encoding="utf-8",
        )

        hint = module._failure_hint_for_run({"stderr_path": str(stderr_path), "blocker": ""})

        assert hint.startswith("ERROR: Your access token could not be refreshed")
