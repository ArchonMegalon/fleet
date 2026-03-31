from __future__ import annotations

import importlib.util
import json
import os
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
                        "id": 21,
                        "title": "Rules Navigator v2",
                        "wave": "W2",
                        "status": "not_started",
                        "owners": ["chummer6-core", "chummer6-ui", "chummer6-hub"],
                        "exit_criteria": ["SR4, SR5, and SR6 rule diffs are visible."],
                        "dependencies": [6],
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
        worker_lane="",
        fallback_worker_model=[],
        account_owner_id=[],
        account_alias=[],
        focus_owner=[],
        focus_profile=[],
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
        assert [item.id for item in context["open_milestones"]] == [6, 15, 18, 21, 19]
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


def test_derive_context_can_focus_frontier_by_desktop_profile() -> None:
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
        args.focus_profile = ["desktop_client"]

        context = module.derive_context(args)

        assert [item.id for item in context["frontier"]] == [6, 21, 19]
        assert context["focus_profiles"] == ["desktop_client"]
        assert "profile focus: desktop_client" in context["prompt"]
        assert "owner focus: chummer6-ui, chummer6-core, chummer6-hub" in context["prompt"]
        assert "text focus: desktop, client, workbench" in context["prompt"]


def test_default_worker_command_adds_scope_roots_and_output_file() -> None:
    module = _load_module()
    workspace = Path("/docker/fleet")
    scope_roots = [workspace, Path("/docker/chummercomplete"), Path("/docker/EA")]
    run_dir = Path("/tmp/fleet-supervisor-run")

    command = module._default_worker_command(
        worker_bin="codex",
        worker_lane="",
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


def test_default_worker_command_supports_lane_prefixed_worker_bin() -> None:
    module = _load_module()
    command = module._default_worker_command(
        worker_bin="codexea",
        worker_lane="core",
        workspace_root=Path("/docker/fleet"),
        scope_roots=[Path("/docker/fleet")],
        run_dir=Path("/tmp/fleet-supervisor-run"),
        worker_model="",
    )

    assert command[:3] == ["codexea", "core", "exec"]
    assert "-C" in command
    assert "-m" not in command


def test_parse_final_message_sections_reads_required_fields() -> None:
    module = _load_module()
    parsed = module._parse_final_message_sections(
        "What shipped: alpha\nWhat remains: beta\nExact blocker: none\n"
    )

    assert parsed["shipped"] == "alpha"
    assert parsed["remains"] == "beta"
    assert parsed["blocker"] == "none"


def test_assess_worker_result_rejects_timeout_text_even_with_zero_exit() -> None:
    module = _load_module()

    accepted, reason = module._assess_worker_result(0, "Error: upstream_timeout:300s\n")

    assert accepted is False
    assert "upstream_timeout:300s" in reason


def test_assess_worker_result_rejects_missing_structured_closeout() -> None:
    module = _load_module()

    accepted, reason = module._assess_worker_result(0, "What shipped: alpha\n")

    assert accepted is False
    assert "What remains" in reason
    assert "Exact blocker" in reason


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
        assert run.accepted is True
        assert run.attempted_models == ["gpt-5.3-codex-spark", "gpt-5.4"]
        assert run.attempted_accounts == ["default", "default"]
        assert "gpt-5.4" in run.worker_command
        assert run.shipped == "fallback landed"
        assert len(calls) == 2


def test_launch_worker_rejects_zero_exit_timeout_receipt(monkeypatch) -> None:
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
        context = module.derive_context(args)

        def fake_run(command, *, input, text, capture_output, cwd, check, env=None):
            message_path = Path(command[command.index("-o") + 1])
            message_path.write_text("Error: upstream_timeout:300s\n", encoding="utf-8")
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        monkeypatch.setattr(module.subprocess, "run", fake_run)

        run = module.launch_worker(args, context, root / "state")

        assert run.worker_exit_code == 0
        assert run.accepted is False
        assert "upstream_timeout:300s" in run.acceptance_reason


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
        assert run.accepted is True
        assert run.selected_account_alias == "acct-archon-a"
        assert run.attempted_accounts == ["acct-tibor-a", "acct-archon-a"]
        assert run.attempted_models == ["gpt-5.3-codex-spark", "gpt-5.3-codex-spark"]
        account_runtime = json.loads((root / "state" / "account_runtime.json").read_text(encoding="utf-8"))
        assert len(account_runtime["sources"]) == 2
        assert len(calls) == 2


def test_launch_worker_can_use_direct_worker_lane_without_account_rotation(monkeypatch) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_registry(root / "registry.yaml")
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("W2 milestone `21` remains active.\n", encoding="utf-8")
        args = _args(root)
        args.worker_bin = "codexea"
        args.worker_lane = "core"
        args.worker_model = ""
        context = module.derive_context(args)

        calls: list[list[str]] = []

        def fake_run(command, *, input, text, capture_output, cwd, check, env=None):
            calls.append(list(command))
            assert env is not None
            assert str(env.get("CODEX_HOME") or "").endswith("/direct-core")
            assert env.get("HOME") == env.get("CODEX_HOME")
            message_path = Path(command[command.index("-o") + 1])
            message_path.write_text(
                "What shipped: core lane worked\nWhat remains: follow-through\nExact blocker: none\n",
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        monkeypatch.setattr(module.subprocess, "run", fake_run)

        run = module.launch_worker(args, context, root / "state")

        assert run.worker_exit_code == 0
        assert run.accepted is True
        assert run.selected_account_alias == "lane:core"
        assert run.attempted_accounts == ["lane:core"]
        assert calls[0][:3] == ["codexea", "core", "exec"]


def test_completion_audit_rejects_untrusted_latest_receipt() -> None:
    module = _load_module()

    audit = module._completion_audit(
        [
            {
                "run_id": "run-1",
                "worker_exit_code": 0,
                "accepted": True,
                "acceptance_reason": "",
                "shipped": "trusted closeout",
                "remains": "none",
                "blocker": "none",
            },
            {
                "run_id": "run-2",
                "worker_exit_code": 0,
                "final_message": "Error: upstream_timeout:300s\n",
            },
        ]
    )

    assert audit["status"] == "fail"
    assert audit["latest_run_id"] == "run-2"
    assert "not trusted" in audit["reason"]
    assert audit["rejected_zero_exit_run_ids"] == ["run-2"]


def test_run_receipt_status_rejects_accepted_receipt_without_structured_content() -> None:
    module = _load_module()

    accepted, reason = module._run_receipt_status(
        {
            "run_id": "run-dry",
            "worker_exit_code": 0,
            "accepted": True,
            "acceptance_reason": "",
            "shipped": "",
            "remains": "",
            "blocker": "",
            "final_message": "",
        }
    )

    assert accepted is False
    assert "missing structured closeout content" in reason


def test_derive_completion_review_context_targets_recent_untrusted_frontier() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "registry.yaml").write_text(
            yaml.safe_dump(
                {
                    "waves": [{"id": "W1"}],
                    "milestones": [
                        {
                            "id": 13,
                            "title": "Desktop package proof",
                            "wave": "W4",
                            "status": "complete",
                            "owners": ["chummer6-ui", "fleet"],
                            "exit_criteria": ["Desktop package ships."],
                        },
                        {
                            "id": 14,
                            "title": "Rules parity proof",
                            "wave": "W4",
                            "status": "complete",
                            "owners": ["chummer6-core", "chummer6-ui"],
                            "exit_criteria": ["SR4-SR6 parity is proven."],
                        },
                    ],
                }
            ),
            encoding="utf-8",
        )
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("Everything is done.\n", encoding="utf-8")
        state_root = root / "state"
        state_root.mkdir(parents=True, exist_ok=True)
        (state_root / "history.jsonl").write_text(
            json.dumps(
                {
                    "run_id": "run-9",
                    "worker_exit_code": 0,
                    "primary_milestone_id": 13,
                    "frontier_ids": [13, 14],
                    "final_message": "Error: upstream_timeout:300s\n",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        args = _args(root)
        base_context = module.derive_context(args)
        audit = module._completion_audit(module._read_history(state_root / "history.jsonl", limit=10))

        context = module.derive_completion_review_context(args, state_root, base_context=base_context, audit=audit)

        assert context["frontier_ids"] == [13, 14]
        assert "false-complete recovery pass" in context["prompt"]
        assert "run run-9 primary=13 frontier=13, 14" in context["prompt"]
        assert "Desktop package proof" in context["prompt"]


def test_run_once_launches_completion_review_worker_when_registry_is_empty_but_receipt_is_untrusted(monkeypatch) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "registry.yaml").write_text(
            yaml.safe_dump(
                {
                    "waves": [{"id": "W1"}],
                    "milestones": [
                        {
                            "id": 13,
                            "title": "Desktop package proof",
                            "wave": "W1",
                            "status": "complete",
                            "owners": ["chummer6-ui", "fleet"],
                            "exit_criteria": ["Desktop package ships."],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("Everything is done.\n", encoding="utf-8")
        state_root = root / "state"
        state_root.mkdir(parents=True, exist_ok=True)
        (state_root / "history.jsonl").write_text(
            json.dumps(
                {
                    "run_id": "run-9",
                    "worker_exit_code": 0,
                    "primary_milestone_id": 13,
                    "frontier_ids": [13],
                    "final_message": "Error: upstream_timeout:300s\n",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        args = _args(root)
        prompts: list[str] = []

        def fake_run(command, *, input, text, capture_output, cwd, check, env=None):
            prompts.append(input)
            message_path = Path(command[command.index("-o") + 1])
            message_path.write_text(
                "What shipped: reopened milestone 13 for real verification\n"
                "What remains: implementation still needs to continue from milestone 13\n"
                "Exact blocker: none\n",
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        monkeypatch.setattr(module.subprocess, "run", fake_run)

        exit_code = module.run_once(args)

        assert exit_code == 0
        assert prompts
        assert "false-complete recovery pass" in prompts[0]
        state_payload = json.loads((state_root / "state.json").read_text(encoding="utf-8"))
        assert state_payload["mode"] == "completion_review"
        assert state_payload["frontier_ids"] == [13]
        assert state_payload["last_run"]["accepted"] is True
        assert state_payload["completion_audit"]["status"] == "fail"


def test_refresh_source_credential_state_clears_backoff_when_auth_changes() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        auth_path = root / "acct.auth.json"
        auth_path.write_text('{"access_token":"fresh"}\n', encoding="utf-8")
        account = module.WorkerAccount(
            alias="acct-archon-a",
            owner_id="archon.megalon",
            auth_kind="chatgpt_auth_json",
            auth_json_file=str(auth_path),
            api_key_env="",
            api_key_file="",
            allowed_models=[],
            health_state="ready",
            spark_enabled=True,
            bridge_priority=1,
            forced_login_method="",
            forced_chatgpt_workspace_id="",
            openai_base_url="",
            home_dir="",
        )
        until = module._utc_now() + module.dt.timedelta(hours=6)
        payload = {
            "sources": {
                module._credential_source_key(account): {
                    "alias": account.alias,
                    "owner_id": account.owner_id,
                    "source_key": module._credential_source_key(account),
                    "credential_fingerprint": "stale-fingerprint",
                    "backoff_until": module._iso(until),
                    "last_error": "chatgpt auth session is expired",
                }
            }
        }

        changed = module._refresh_source_credential_state(payload, account, root)

        assert changed is True
        item = payload["sources"][module._credential_source_key(account)]
        assert item["credential_fingerprint"] != "stale-fingerprint"
        assert item["backoff_until"] == ""
        assert item["last_error"] == ""


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


def test_acquire_lock_treats_reused_self_pid_without_start_ticks_as_stale() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        lock_path = root / "loop.lock"
        lock_path.write_text(
            json.dumps({"pid": os.getpid(), "created_at": module._utc_now().isoformat()}),
            encoding="utf-8",
        )

        module._acquire_lock(lock_path, ttl_seconds=300.0)

        payload = json.loads(lock_path.read_text(encoding="utf-8"))
        assert payload["pid"] == os.getpid()
        assert payload["proc_start_ticks"]
        module._release_lock(lock_path)


def test_failure_hint_maps_container_state_paths_back_to_workspace() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        previous_workspace_root = module.DEFAULT_WORKSPACE_ROOT
        try:
            module.DEFAULT_WORKSPACE_ROOT = root
            stderr_path = root / "state" / "chummer_design_supervisor" / "runs" / "run-1.stderr.log"
            stderr_path.parent.mkdir(parents=True, exist_ok=True)
            stderr_path.write_text(
                "[fleet-supervisor] no eligible worker account/model attempts were runnable\n",
                encoding="utf-8",
            )

            hint = module._failure_hint_for_run(
                {
                    "stderr_path": "/var/lib/codex-fleet/chummer_design_supervisor/runs/run-1.stderr.log",
                    "blocker": "",
                }
            )

            assert hint == "[fleet-supervisor] no eligible worker account/model attempts were runnable"
        finally:
            module.DEFAULT_WORKSPACE_ROOT = previous_workspace_root
