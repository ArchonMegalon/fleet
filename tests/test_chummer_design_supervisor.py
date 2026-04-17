from __future__ import annotations

import datetime as dt
import hashlib
import importlib.util
import inspect
import io
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from argparse import Namespace
from pathlib import Path

import pytest
import yaml


MODULE_PATH = Path("/docker/fleet/scripts/chummer_design_supervisor.py")


def _load_module():
    spec = importlib.util.spec_from_file_location("chummer_design_supervisor", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)  # type: ignore[attr-defined]
    return module


def _worktree_fingerprint(root: Path, *, exclude_paths: tuple[Path, ...] = ()) -> tuple[str, int]:
    exclude_markers: list[str] = []
    for candidate in exclude_paths:
        try:
            relative = candidate.resolve().relative_to(root.resolve())
        except Exception:
            continue
        marker = relative.as_posix().rstrip("/")
        if marker:
            exclude_markers.append(marker)

    def is_excluded(relative: str) -> bool:
        return any(relative == marker or relative.startswith(f"{marker}/") for marker in exclude_markers)

    entries: list[str] = []
    if (root / ".git").exists():
        listing = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
            check=True,
            capture_output=True,
        ).stdout.decode("utf-8", errors="surrogateescape")
        seen: set[str] = set()
        for raw_item in listing.split("\0"):
            relative = raw_item.strip()
            if not relative or relative in seen or is_excluded(relative):
                continue
            seen.add(relative)
            entries.append(relative)
        entries.sort()
    else:
        for path in sorted(root.rglob("*")):
            if path == root / ".git":
                continue
            try:
                relative = path.relative_to(root).as_posix()
            except Exception:
                continue
            if relative == ".git" or relative.startswith(".git/") or is_excluded(relative):
                continue
            if path.is_dir():
                continue
            entries.append(relative)

    digest = hashlib.sha256()
    entry_count = 0
    for relative in entries:
        path = root / relative
        try:
            stat_result = os.lstat(path)
        except FileNotFoundError:
            digest.update(f"missing\0{relative}\0".encode("utf-8"))
            entry_count += 1
            continue
        mode = stat.S_IMODE(stat_result.st_mode)
        if stat.S_ISLNK(stat_result.st_mode):
            digest.update(f"symlink\0{relative}\0{mode:o}\0{os.readlink(path)}\0".encode("utf-8"))
            entry_count += 1
            continue
        if not stat.S_ISREG(stat_result.st_mode):
            continue
        digest.update(f"file\0{relative}\0{mode:o}\0".encode("utf-8"))
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        digest.update(b"\0")
        entry_count += 1
    return digest.hexdigest(), entry_count


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


def _write_published_queue(root: Path, items: list[object], *, fingerprint: str = "queue-fingerprint") -> None:
    published = root / ".codex-studio" / "published"
    published.mkdir(parents=True, exist_ok=True)
    (published / "QUEUE.generated.yaml").write_text(
        yaml.safe_dump(
            {
                "mode": "append",
                "items": items,
                "source_queue_fingerprint": fingerprint,
            }
        ),
        encoding="utf-8",
    )


def _write_next_wave_queue(
    root: Path,
    items: list[object],
    *,
    fingerprint: str = "next90-fingerprint",
    source_registry_path: str | None = None,
) -> None:
    published = root / ".codex-studio" / "published"
    published.mkdir(parents=True, exist_ok=True)
    (published / "NEXT_90_DAY_QUEUE_STAGING.generated.yaml").write_text(
        yaml.safe_dump(
            {
                "mode": "append",
                "status": "live_parallel_successor",
                "source_registry_path": source_registry_path or str(root / "NEXT_90_DAY_PRODUCT_ADVANCE_REGISTRY.yaml"),
                "items": items,
                "source_queue_fingerprint": fingerprint,
            }
        ),
        encoding="utf-8",
    )


def _write_next_wave_registry(root: Path) -> None:
    (root / "NEXT_90_DAY_PRODUCT_ADVANCE_REGISTRY.yaml").write_text(
        yaml.safe_dump(
            {
                "program_wave": "next_90_day_product_advance",
                "milestones": [
                    {
                        "id": 101,
                        "title": "Native-host desktop release train and promotion discipline",
                        "wave": "W6",
                        "status": "in_progress",
                        "owners": ["chummer6-ui", "fleet"],
                        "exit_criteria": ["Release truth is repeatable."],
                        "dependencies": [],
                    },
                    {
                        "id": 102,
                        "title": "Desktop-native claim, update, rollback, and support followthrough",
                        "wave": "W6",
                        "status": "in_progress",
                        "owners": ["chummer6-hub", "fleet"],
                        "exit_criteria": ["Claim and support flows are desktop-native."],
                        "dependencies": [101],
                    },
                    {
                        "id": 103,
                        "title": "Chummer5a parity lab and veteran migration certification",
                        "wave": "W7",
                        "status": "in_progress",
                        "owners": ["executive-assistant", "chummer6-ui"],
                        "exit_criteria": ["Veteran migration is evidence-backed."],
                        "dependencies": [101, 102],
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
        projects_dir=str(root / "projects"),
        journey_gates_path=str(root / "GOLDEN_JOURNEY_RELEASE_GATES.yaml"),
        weekly_pulse_path=str(root / "WEEKLY_PRODUCT_PULSE.generated.json"),
        accounts_path=str(root / "accounts.yaml"),
        workspace_root=str(root),
        scope_root=[str(root / "extra"), str(root / "more")],
        state_root=str(root / "state"),
        status_plane_path=str(root / "STATUS_PLANE.generated.yaml"),
        progress_report_path=str(root / "PROGRESS_REPORT.generated.json"),
        progress_history_path=str(root / "PROGRESS_HISTORY.generated.json"),
        support_packets_path=str(root / "SUPPORT_CASE_PACKETS.generated.json"),
        flagship_product_readiness_path=str(root / "FLAGSHIP_PRODUCT_READINESS.generated.json"),
        ui_linux_desktop_exit_gate_path=str(root / "UI_LINUX_DESKTOP_EXIT_GATE.generated.json"),
        ui_executable_exit_gate_path=str(root / "DESKTOP_EXECUTABLE_EXIT_GATE.generated.json"),
        ui_linux_desktop_repo_root=str(root),
        worker_bin="codex",
        worker_model="gpt-5.4",
        worker_lane="",
        fallback_worker_model=[],
        fallback_worker_lane=[],
        frontier_id=[],
        account_owner_id=[],
        account_alias=[],
        focus_owner=[],
        focus_profile=[],
        focus_text=[],
        dry_run=False,
        worker_timeout_seconds=0.0,
        ea_provider_health_url="http://127.0.0.1:8090/v1/responses/_provider_health",
        ea_provider_health_timeout_seconds=4.0,
        operating_profile="standard",
        memory_dispatch_reserve_gib=0.0,
        memory_dispatch_shard_budget_gib=0.25,
        memory_dispatch_warning_available_percent=0.0,
        memory_dispatch_critical_available_percent=0.0,
        memory_dispatch_warning_swap_used_percent=101.0,
        memory_dispatch_critical_swap_used_percent=101.0,
    )


def _patch_launch_worker_fake_run(monkeypatch, module, fake_run) -> None:
    supports_timeout = "timeout" in inspect.signature(fake_run).parameters

    def fake_run_worker_attempt(
        command,
        *,
        prompt,
        workspace_root,
        worker_env,
        timeout_seconds,
        last_message_path,
        state_root,
        run_id,
        stdout_sink=None,
        stderr_sink=None,
    ):
        kwargs = {
            "input": prompt,
            "text": True,
            "capture_output": True,
            "cwd": str(workspace_root),
            "check": False,
            "env": worker_env,
        }
        if supports_timeout:
            kwargs["timeout"] = float(timeout_seconds) if float(timeout_seconds or 0.0) > 0 else None
        try:
            completed = fake_run(command, **kwargs)
        except subprocess.TimeoutExpired:
            timeout_label = f"{float(timeout_seconds):g}s"
            stderr_text = (
                f"Error: worker_timeout:{timeout_label}\n"
                f"[fleet-supervisor] worker attempt exceeded watchdog after {timeout_label}; "
                "killed and marked retryable\n"
            )
            if stderr_sink is not None:
                stderr_sink.write(stderr_text)
                stderr_sink.flush()
            if not last_message_path.exists() or not last_message_path.read_text(encoding="utf-8").strip():
                last_message_path.write_text(f"Error: worker_timeout:{timeout_label}\n", encoding="utf-8")
            return subprocess.CompletedProcess(list(command), 124, stdout="", stderr=stderr_text)
        stdout_text = module._normalize_subprocess_output(completed.stdout)
        stderr_text = module._normalize_subprocess_output(completed.stderr)
        if stdout_text and stdout_sink is not None:
            stdout_sink.write(stdout_text)
            stdout_sink.flush()
        if stderr_text and stderr_sink is not None:
            stderr_sink.write(stderr_text)
            stderr_sink.flush()
        return subprocess.CompletedProcess(list(command), int(completed.returncode or 0), stdout=stdout_text, stderr=stderr_text)

    monkeypatch.setattr(module, "_run_worker_attempt", fake_run_worker_attempt)


@pytest.fixture(autouse=True)
def _isolate_supervisor_env(monkeypatch) -> None:
    for name in list(os.environ):
        if name.startswith("CHUMMER_DESIGN_SUPERVISOR_") or name.startswith("CODEXEA_"):
            monkeypatch.delenv(name, raising=False)


def test_default_worker_timeout_seconds_tracks_stream_budget(monkeypatch) -> None:
    module = _load_module()
    monkeypatch.setattr(
        module,
        "_runtime_env_default",
        lambda name, default="": {
            "CHUMMER_DESIGN_SUPERVISOR_STREAM_IDLE_TIMEOUT_MS": "900000",
            "CHUMMER_DESIGN_SUPERVISOR_STREAM_MAX_RETRIES": "8",
        }.get(name, default),
    )

    assert module._default_worker_timeout_seconds() == 9000.0


def test_parse_args_reads_memory_dispatch_defaults_from_runtime_env_candidates(monkeypatch, tmp_path: Path) -> None:
    module = _load_module()
    runtime_env = tmp_path / "runtime.env"
    runtime_env.write_text(
        "\n".join(
            [
                "CHUMMER_DESIGN_SUPERVISOR_OPERATING_PROFILE=burst",
                "CHUMMER_DESIGN_SUPERVISOR_MEMORY_DISPATCH_RESERVE_GIB=2",
                "CHUMMER_DESIGN_SUPERVISOR_MEMORY_DISPATCH_SHARD_BUDGET_GIB=0.28",
                "CHUMMER_DESIGN_SUPERVISOR_MEMORY_DISPATCH_WARNING_AVAILABLE_PERCENT=18",
                "CHUMMER_DESIGN_SUPERVISOR_MEMORY_DISPATCH_CRITICAL_AVAILABLE_PERCENT=9",
                "CHUMMER_DESIGN_SUPERVISOR_MEMORY_DISPATCH_WARNING_SWAP_USED_PERCENT=70",
                "CHUMMER_DESIGN_SUPERVISOR_MEMORY_DISPATCH_CRITICAL_SWAP_USED_PERCENT=88",
                "CHUMMER_DESIGN_SUPERVISOR_MEMORY_DISPATCH_PARKED_POLL_SECONDS=33",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "_RUNTIME_ENV_CANDIDATES", (runtime_env,))

    previous_argv = sys.argv[:]
    try:
        sys.argv = ["chummer_design_supervisor.py", "loop", "--state-root", str(tmp_path / "state")]
        args = module.parse_args()
    finally:
        sys.argv = previous_argv

    assert args.operating_profile == "burst"
    assert args.memory_dispatch_reserve_gib == 2.0
    assert args.memory_dispatch_shard_budget_gib == 0.28
    assert args.memory_dispatch_warning_available_percent == 18.0
    assert args.memory_dispatch_critical_available_percent == 9.0
    assert args.memory_dispatch_warning_swap_used_percent == 70.0
    assert args.memory_dispatch_critical_swap_used_percent == 88.0
    assert args.memory_dispatch_parked_poll_seconds == 33.0


def test_candidate_models_for_account_respects_allowed_models() -> None:
    module = _load_module()
    account = module.WorkerAccount(
        alias="acct-chatgpt-b",
        owner_id="the.girscheles",
        lane="",
        auth_kind="chatgpt_auth_json",
        auth_json_file="/run/secrets/acct-chatgpt-b.auth.json",
        api_key_env="",
        api_key_file="",
        allowed_models=["gpt-5.3-codex"],
        health_state="ready",
        spark_enabled=False,
        bridge_priority=0,
        forced_login_method="",
        forced_chatgpt_workspace_id="",
        openai_base_url="",
        home_dir="",
    )

    models = module._candidate_models_for_account(
        account,
        ["gpt-5.3-codex", "gpt-5.3-codex-spark", "gpt-5.4"],
        {},
    )

    assert models == ["gpt-5.3-codex"]


def test_candidate_models_for_account_allows_core_lane_to_use_repair_and_survival_fallbacks() -> None:
    module = _load_module()
    repair_account = module.WorkerAccount(
        alias="acct-ea-repair",
        owner_id="tibor.girschele",
        lane="repair",
        auth_kind="ea",
        auth_json_file="",
        api_key_env="",
        api_key_file="",
        allowed_models=["ea-coder-fast"],
        health_state="ready",
        spark_enabled=False,
        bridge_priority=0,
        forced_login_method="",
        forced_chatgpt_workspace_id="",
        openai_base_url="",
        home_dir="",
    )
    survival_account = module.WorkerAccount(
        alias="acct-ea-survival",
        owner_id="tibor.girschele",
        lane="survival",
        auth_kind="ea",
        auth_json_file="",
        api_key_env="",
        api_key_file="",
        allowed_models=["ea-coder-survival"],
        health_state="ready",
        spark_enabled=False,
        bridge_priority=0,
        forced_login_method="",
        forced_chatgpt_workspace_id="",
        openai_base_url="",
        home_dir="",
    )

    repair_models = module._candidate_models_for_account(
        repair_account,
        ["ea-coder-hard"],
        {},
        requested_worker_lane="core",
    )
    survival_models = module._candidate_models_for_account(
        survival_account,
        ["ea-coder-hard"],
        {},
        requested_worker_lane="core_rescue",
    )

    assert repair_models == ["ea-coder-fast"]
    assert survival_models == ["ea-coder-survival"]


def test_candidate_models_for_account_prefers_hard_batch_for_core_lane() -> None:
    module = _load_module()
    core_account = module.WorkerAccount(
        alias="acct-ea-core",
        owner_id="tibor.girschele",
        lane="core",
        auth_kind="ea",
        auth_json_file="",
        api_key_env="",
        api_key_file="",
        allowed_models=["ea-coder-hard-batch", "ea-coder-hard"],
        health_state="ready",
        spark_enabled=False,
        bridge_priority=0,
        forced_login_method="",
        forced_chatgpt_workspace_id="",
        openai_base_url="",
        home_dir="",
    )

    models = module._candidate_models_for_account(
        core_account,
        ["ea-coder-hard"],
        {},
        requested_worker_lane="core",
    )

    assert models == ["ea-coder-hard-batch"]


def test_model_selection_snapshot_prefers_best_ea_and_chatgpt_models(monkeypatch) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        auth_path = root / "chatgpt.auth.json"
        auth_path.write_text("{}", encoding="utf-8")
        (root / "accounts.yaml").write_text(
            yaml.safe_dump(
                {
                    "accounts": {
                        "acct-ea-core": {
                            "auth_kind": "ea",
                            "lane": "core",
                            "allowed_models": ["ea-coder-hard-batch", "ea-coder-hard"],
                            "health_state": "ready",
                            "max_parallel_runs": 2,
                        },
                        "acct-chatgpt-core": {
                            "auth_kind": "chatgpt_auth_json",
                            "auth_json_file": str(auth_path),
                            "allowed_models": ["gpt-5.3-codex-spark", "gpt-5.4"],
                            "spark_enabled": True,
                            "health_state": "ready",
                            "max_parallel_runs": 2,
                            "owner_id": "tibor.girschele",
                        },
                    }
                }
            ),
            encoding="utf-8",
        )
        runtime_env = root / "runtime.env"
        runtime_env.write_text(
            "\n".join(
                [
                    "CHUMMER_DESIGN_SUPERVISOR_OPENAI_ESCAPE_ACCOUNT_ALIASES=acct-chatgpt-core",
                    "CHUMMER_DESIGN_SUPERVISOR_OPENAI_ESCAPE_MODELS=gpt-5.3-codex",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(module, "_RUNTIME_ENV_CANDIDATES", (runtime_env,))
        args = _args(root)
        args.worker_bin = "codexea"
        args.worker_lane = "core"
        args.worker_model = "ea-coder-hard"
        state_root = Path(args.state_root)
        state_root.mkdir(parents=True, exist_ok=True)

        snapshot = module._model_selection_snapshot(args, state_root)

        assert snapshot["ea_core"]["selected_model"] == "ea-coder-hard-batch"
        assert snapshot["ea_core"]["available_models"] == ["ea-coder-hard-batch"]
        assert snapshot["openai_escape"]["selected_model"] == "gpt-5.4"
        assert snapshot["openai_escape"]["ordered_models"][:2] == ["gpt-5.4", "gpt-5.3-codex-spark"]
        assert snapshot["openai_escape"]["available_models"][:2] == ["gpt-5.4", "gpt-5.3-codex-spark"]


def test_model_selection_snapshot_prefers_gpt54_when_spark_is_backed_off(monkeypatch) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        auth_path = root / "chatgpt.auth.json"
        auth_path.write_text("{}", encoding="utf-8")
        (root / "accounts.yaml").write_text(
            yaml.safe_dump(
                {
                    "accounts": {
                        "acct-chatgpt-core": {
                            "auth_kind": "chatgpt_auth_json",
                            "auth_json_file": str(auth_path),
                            "allowed_models": ["gpt-5.3-codex-spark", "gpt-5.4"],
                            "spark_enabled": True,
                            "health_state": "ready",
                            "max_parallel_runs": 2,
                            "owner_id": "tibor.girschele",
                        },
                    }
                }
            ),
            encoding="utf-8",
        )
        runtime_env = root / "runtime.env"
        runtime_env.write_text(
            "\n".join(
                [
                    "CHUMMER_DESIGN_SUPERVISOR_OPENAI_ESCAPE_ACCOUNT_ALIASES=acct-chatgpt-core",
                    "CHUMMER_DESIGN_SUPERVISOR_OPENAI_ESCAPE_MODELS=gpt-5.3-codex-spark,gpt-5.3-codex",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(module, "_RUNTIME_ENV_CANDIDATES", (runtime_env,))
        args = _args(root)
        state_root = Path(args.state_root)
        state_root.mkdir(parents=True, exist_ok=True)
        module._write_account_runtime(
            module._account_runtime_path(state_root),
            {
                "sources": {
                    f"chatgpt_auth_json:{auth_path}": {
                        "alias": "acct-chatgpt-core",
                        "source_key": f"chatgpt_auth_json:{auth_path}",
                        "spark_backoff_until": "2099-01-01T00:00:00Z",
                        "last_error": "usage-limited until 2099-01-01T00:00:00Z",
                    }
                }
            },
        )

        snapshot = module._model_selection_snapshot(args, state_root)

        assert snapshot["openai_escape"]["selected_model"] == "gpt-5.4"
        assert snapshot["openai_escape"]["available_models"][0] == "gpt-5.4"
        assert snapshot["openai_escape"]["unavailable_models"][0] == "gpt-5.3-codex-spark"


def test_launch_worker_prefers_startup_selected_ea_core_model_over_static_primary(monkeypatch) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_registry(root / "registry.yaml")
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("W2 milestone `21` remains active.\n", encoding="utf-8")
        (root / "accounts.yaml").write_text(
            yaml.safe_dump(
                {
                    "accounts": {
                        "acct-ea-core": {
                            "auth_kind": "ea",
                            "lane": "core",
                            "allowed_models": ["ea-coder-hard-batch", "ea-coder-hard"],
                            "health_state": "ready",
                            "max_parallel_runs": 1,
                        },
                    }
                }
            ),
            encoding="utf-8",
        )
        args = _args(root)
        args.worker_bin = "codexea"
        args.worker_lane = "core"
        args.worker_model = "ea-coder-hard"
        context = module.derive_context(args)
        state_root = Path(args.state_root)
        state_root.mkdir(parents=True, exist_ok=True)

        calls: list[list[str]] = []

        def fake_run(command, *, input, text, capture_output, cwd, check, env=None):
            calls.append(list(command))
            message_path = Path(command[command.index("-o") + 1])
            message_path.write_text(
                "What shipped: routed core lane succeeded\nWhat remains: none\nExact blocker: none\n",
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        _patch_launch_worker_fake_run(monkeypatch, module, fake_run)

        run = module.launch_worker(args, context, state_root)

        assert run.accepted is True
        assert run.attempted_models[0] == "ea-coder-hard-batch"
        assert "ea-coder-hard-batch" in calls[0]


def test_launch_worker_prefers_account_that_can_run_best_startup_model(monkeypatch) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_registry(root / "registry.yaml")
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("W2 milestone `21` remains active.\n", encoding="utf-8")
        (root / "accounts.yaml").write_text(
            yaml.safe_dump(
                {
                    "accounts": {
                        "acct-a-old-only": {
                            "auth_kind": "ea",
                            "lane": "core",
                            "allowed_models": ["ea-coder-hard"],
                            "health_state": "ready",
                            "max_parallel_runs": 1,
                        },
                        "acct-z-batch": {
                            "auth_kind": "ea",
                            "lane": "core",
                            "allowed_models": ["ea-coder-hard-batch"],
                            "health_state": "ready",
                            "max_parallel_runs": 1,
                        },
                    }
                }
            ),
            encoding="utf-8",
        )
        args = _args(root)
        args.worker_bin = "codexea"
        args.worker_lane = "core"
        args.worker_model = "ea-coder-hard"
        context = module.derive_context(args)
        state_root = Path(args.state_root)
        state_root.mkdir(parents=True, exist_ok=True)

        monkeypatch.setattr(
            module,
            "_stable_account_selection_rank",
            lambda _state_root, alias: 0 if alias == "acct-a-old-only" else 99,
        )
        calls: list[list[str]] = []

        def fake_run(command, *, input, text, capture_output, cwd, check, env=None):
            calls.append(list(command))
            message_path = Path(command[command.index("-o") + 1])
            message_path.write_text(
                "What shipped: routed best model account succeeded\nWhat remains: none\nExact blocker: none\n",
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        _patch_launch_worker_fake_run(monkeypatch, module, fake_run)

        run = module.launch_worker(args, context, state_root)

        assert run.accepted is True
        assert run.selected_account_alias == "acct-z-batch"
        assert run.attempted_models[0] == "ea-coder-hard-batch"
        assert "ea-coder-hard-batch" in calls[0]


def test_rotate_model_candidates_after_recent_stall_moves_latest_stalled_model_to_end(tmp_path: Path) -> None:
    module = _load_module()
    state_root = tmp_path / "shard-1"
    state_root.mkdir(parents=True)
    module._append_jsonl(
        module._history_payload_path(state_root),
        {
            "accepted": False,
            "blocker": "Error: worker_model_output_stalled:240s",
            "selected_model": "ea-coder-hard-batch",
        },
    )

    rotated = module._rotate_model_candidates_after_recent_stall(
        state_root,
        ["ea-coder-hard-batch", "ea-coder-hard"],
    )

    assert rotated == ["ea-coder-hard", "ea-coder-hard-batch"]


def test_rotate_model_candidates_after_recent_stall_ignores_nonstall_blockers(tmp_path: Path) -> None:
    module = _load_module()
    state_root = tmp_path / "shard-1"
    state_root.mkdir(parents=True)
    module._append_jsonl(
        module._history_payload_path(state_root),
        {
            "accepted": False,
            "blocker": "worker exit 2",
            "selected_model": "ea-coder-hard-batch",
        },
    )

    rotated = module._rotate_model_candidates_after_recent_stall(
        state_root,
        ["ea-coder-hard-batch", "ea-coder-hard"],
    )

    assert rotated == ["ea-coder-hard-batch", "ea-coder-hard"]


def test_rotate_model_candidates_after_recent_stall_uses_attempted_model_when_selected_model_missing(tmp_path: Path) -> None:
    module = _load_module()
    state_root = tmp_path / "shard-1"
    state_root.mkdir(parents=True)
    module._append_jsonl(
        module._history_payload_path(state_root),
        {
            "accepted": False,
            "blocker": "Error: worker_model_output_stalled:240s",
            "attempted_models": ["ea-coder-hard-batch"],
        },
    )

    rotated = module._rotate_model_candidates_after_recent_stall(
        state_root,
        ["ea-coder-hard-batch", "ea-coder-hard"],
    )

    assert rotated == ["ea-coder-hard", "ea-coder-hard-batch"]


def test_candidate_models_for_account_allows_audit_shard_to_use_core_fallbacks() -> None:
    module = _load_module()
    core_account = module.WorkerAccount(
        alias="acct-ea-core",
        owner_id="tibor.girschele",
        lane="core",
        auth_kind="ea",
        auth_json_file="",
        api_key_env="",
        api_key_file="",
        allowed_models=["ea-coder-hard-batch", "ea-coder-hard"],
        health_state="ready",
        spark_enabled=False,
        bridge_priority=0,
        forced_login_method="",
        forced_chatgpt_workspace_id="",
        openai_base_url="",
        home_dir="",
    )

    models = module._candidate_models_for_account(
        core_account,
        ["ea-audit-jury"],
        {},
        requested_worker_lane="audit_shard",
    )

    assert models == ["ea-coder-hard-batch"]


def test_account_has_runnable_candidate_models_respects_parallel_claims() -> None:
    module = _load_module()
    account = module.WorkerAccount(
        alias="acct-ea-core",
        owner_id="tibor.girschele",
        lane="core",
        auth_kind="ea",
        auth_json_file="",
        api_key_env="",
        api_key_file="",
        allowed_models=["ea-coder-hard"],
        health_state="ready",
        spark_enabled=False,
        bridge_priority=0,
        forced_login_method="",
        forced_chatgpt_workspace_id="",
        openai_base_url="",
        home_dir="",
        max_parallel_runs=1,
    )

    assert (
        module._account_has_runnable_candidate_models(
            account,
            ["ea-coder-hard"],
            {},
            requested_worker_lane="core",
            active_account_claims={"acct-ea-core": 1},
        )
        is False
    )
    assert (
        module._account_has_runnable_candidate_models(
            account,
            ["ea-coder-hard"],
            {},
            requested_worker_lane="core",
            active_account_claims={},
        )
        is True
    )


def test_eligible_routed_account_restore_probe_allows_unknown_audit_lane_when_snapshot_is_healthy(monkeypatch) -> None:
    module = _load_module()
    monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_ACCOUNT_RESTORE_PROBE_SECONDS", "300")
    account = module.WorkerAccount(
        alias="acct-ea-core-07",
        owner_id="",
        lane="core",
        auth_kind="ea",
        auth_json_file="",
        api_key_env="",
        api_key_file="",
        allowed_models=["ea-coder-hard"],
        health_state="ready",
        spark_enabled=False,
        bridge_priority=0,
        forced_login_method="",
        forced_chatgpt_workspace_id="",
        openai_base_url="",
        home_dir="",
    )

    assert (
        module._eligible_routed_account_restore_probe(
            {
                "sources": {
                    "alias:acct-ea-core-07": {
                        "alias": "acct-ea-core-07",
                        "source_key": "alias:acct-ea-core-07",
                        "backoff_until": "2026-04-08T22:26:24Z",
                        "last_error": "usage-limited; recheck at 2026-04-08T22:26:24Z",
                    }
                }
            },
            account,
            requested_worker_lane="audit_shard",
            worker_lane_health={
                "status": "pass",
                "lanes": {
                    "audit_shard": {
                        "worker_lane": "audit_shard",
                        "known": False,
                        "routable": True,
                        "state": "unknown",
                    }
                },
            },
            now=dt.datetime(2026, 4, 8, 19, 20, tzinfo=dt.timezone.utc),
        )
        is True
    )


def test_write_active_run_state_refreshes_runtime_handoff_snapshot(monkeypatch, tmp_path: Path) -> None:
    module = _load_module()
    state_root = tmp_path / "state"
    state_root.mkdir(parents=True, exist_ok=True)
    run_dir = state_root / "runs" / "run-123"
    run_dir.mkdir(parents=True, exist_ok=True)
    prompt_path = run_dir / "prompt.txt"
    stdout_path = run_dir / "worker.stdout.log"
    stderr_path = run_dir / "worker.stderr.log"
    last_message_path = run_dir / "last_message.txt"
    prompt_path.write_text("prompt\n", encoding="utf-8")
    stdout_path.write_text("stdout line one\nstdout line two\n", encoding="utf-8")
    stderr_path.write_text("line one\nline two\n", encoding="utf-8")
    last_message_path.write_text(
        "What shipped: kept the shard warm\nWhat remains: one proof lane\nExact blocker: none\n",
        encoding="utf-8",
    )
    module._write_json(
        module._state_payload_path(state_root),
        {
            "mode": "flagship_product",
            "frontier_ids": [2788253648],
            "open_milestone_ids": [2788253648],
            "focus_owners": ["chummer6-ui"],
            "focus_texts": ["proof"],
        },
    )
    active_shard_snapshot_calls = []
    monkeypatch.setattr(module, "_running_inside_container", lambda: True)
    monkeypatch.setattr(
        module,
        "_write_active_shard_manifest_snapshot",
        lambda aggregate_root: active_shard_snapshot_calls.append(Path(aggregate_root)),
    )

    module._write_active_run_state(
        state_root,
        module.ActiveWorkerRun(
            run_id="run-123",
            started_at="2026-04-08T19:20:00Z",
            prompt_path=str(prompt_path),
            stdout_path=str(stdout_path),
            stderr_path=str(stderr_path),
            last_message_path=str(last_message_path),
            frontier_ids=[2788253648],
            open_milestone_ids=[2788253648],
            primary_milestone_id=2788253648,
            worker_command=["codexea", "core", "exec", "-m", "ea-coder-hard"],
            selected_account_alias="acct-ea-core",
            selected_model="ea-coder-hard",
            attempt_index=1,
            total_attempts=20,
            watchdog_timeout_seconds=28800.0,
            worker_pid=12345,
        ),
    )
    module._update_active_run_fields(
        state_root,
        "run-123",
        worker_first_output_at="2026-04-08T19:20:05Z",
        worker_last_output_at="2026-04-08T19:20:15Z",
    )

    shard_state = json.loads(module._state_payload_path(state_root).read_text(encoding="utf-8"))
    handoff_text = module._runtime_handoff_path(state_root).read_text(encoding="utf-8")

    assert shard_state["active_run_id"] == "run-123"
    assert shard_state["active_run_progress_state"] == "streaming"
    assert shard_state["active_run_worker_first_output_at"] == "2026-04-08T19:20:05Z"
    assert shard_state["active_run_worker_last_output_at"] == "2026-04-08T19:20:15Z"
    assert "Shard Runtime Handoff" in handoff_text
    assert "Frontier ids: 2788253648" in handoff_text
    assert "Selected account: acct-ea-core" in handoff_text
    assert "Selected model: ea-coder-hard" in handoff_text
    assert "Last output at: 2026-04-08T19:20:15Z" in handoff_text
    assert "Latest shipped note: kept the shard warm" in handoff_text
    assert "stdout line one" in handoff_text
    assert "line one" in handoff_text
    assert active_shard_snapshot_calls == [state_root, state_root]


def test_run_worker_attempt_refreshes_runtime_handoff_during_quiet_runs(monkeypatch, tmp_path: Path) -> None:
    module = _load_module()
    state_root = tmp_path / "state"
    state_root.mkdir(parents=True, exist_ok=True)
    run_dir = state_root / "runs" / "run-quiet"
    run_dir.mkdir(parents=True, exist_ok=True)
    prompt_path = run_dir / "prompt.txt"
    stdout_path = run_dir / "worker.stdout.log"
    stderr_path = run_dir / "worker.stderr.log"
    last_message_path = run_dir / "last_message.txt"
    prompt_path.write_text("prompt\n", encoding="utf-8")
    module._write_json(
        module._state_payload_path(state_root),
        {
            "mode": "loop",
            "frontier_ids": [6],
            "open_milestone_ids": [6],
        },
    )
    module._write_active_run_state(
        state_root,
        module.ActiveWorkerRun(
            run_id="run-quiet",
            started_at="2026-04-08T19:20:00Z",
            prompt_path=str(prompt_path),
            stdout_path=str(stdout_path),
            stderr_path=str(stderr_path),
            last_message_path=str(last_message_path),
            frontier_ids=[6],
            open_milestone_ids=[6],
            primary_milestone_id=6,
            worker_command=["python3", "-c", "import time; time.sleep(0.25)"],
            selected_account_alias="lane:core",
            selected_model="ea-coder-hard",
            attempt_index=1,
            total_attempts=1,
            watchdog_timeout_seconds=30.0,
        ),
    )

    handoff_writes: list[str] = []

    monkeypatch.setattr(module, "_runtime_handoff_heartbeat_seconds", lambda: 0.05)
    monkeypatch.setattr(module, "_write_runtime_handoff", lambda _state_root: handoff_writes.append(str(_state_root)))

    completed = module._run_worker_attempt(
        ["python3", "-c", "import time; time.sleep(0.25)"],
        prompt="quiet prompt\n",
        workspace_root=tmp_path,
        worker_env=os.environ.copy(),
        timeout_seconds=5.0,
        last_message_path=last_message_path,
        state_root=state_root,
        run_id="run-quiet",
    )

    assert completed.returncode == 0
    assert len(handoff_writes) >= 2


def test_derive_context_materializes_runtime_handoff_and_includes_it_in_prompt(tmp_path: Path) -> None:
    module = _load_module()
    root = tmp_path
    _write_registry(root / "registry.yaml")
    (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
    (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
    (root / "NEXT_SESSION_HANDOFF.md").write_text("W2 milestone `6` remains active.\n", encoding="utf-8")
    args = _args(root)
    state_root = Path(args.state_root)
    state_root.mkdir(parents=True, exist_ok=True)
    runtime_handoff_path = module._runtime_handoff_path(state_root)
    module._write_json(
        module._state_payload_path(state_root),
        {
            "mode": "loop",
            "frontier_ids": [6],
            "open_milestone_ids": [6],
        },
    )

    assert runtime_handoff_path.exists() is False

    context = module.derive_context(args)

    assert runtime_handoff_path.exists() is True
    assert context["runtime_handoff_path"] == runtime_handoff_path
    assert str(runtime_handoff_path) in context["prompt"]
    assert "Use the shard runtime handoff as the worker-safe resume context" in context["prompt"]


def test_prepare_run_prompt_materializes_task_local_telemetry_file(tmp_path: Path) -> None:
    module = _load_module()
    run_dir = tmp_path / "runs" / "run-123"
    telemetry_payload = {
        "active_runs_count": 4,
        "remaining_open_milestones": 1,
        "remaining_not_started_milestones": 1,
        "remaining_in_progress_milestones": 0,
        "eta_human": "11h-1.1d",
        "summary": "Milestone remains open.",
    }
    prompt = (
        "Task-local run context:\n"
        "- the verbatim task-local telemetry snapshot is embedded below; use it as-is and do not regenerate it via shell, Python, or supervisor helper commands from inside the worker run.\n"
        "```json\n"
        '{"active_runs_count":4,"remaining_open_milestones":1,"remaining_not_started_milestones":1,"remaining_in_progress_milestones":0,"eta_human":"11h-1.1d","summary":"Milestone remains open."}\n'
        "```\n\n"
        "Operator telemetry CLI is forbidden during active worker runs. Do not invoke supervisor helper commands from inside the worker run; use the embedded JSON block and listed files instead.\n\n"
        "Read these files directly first:\n"
        "- /tmp/frontier.yaml\n"
    )

    rendered = module._prepare_run_prompt(
        run_dir,
        prompt,
        task_local_telemetry_payload=telemetry_payload,
    )
    prompt_path = module._write_run_artifacts(run_dir, rendered)

    telemetry_path = run_dir / module.TASK_LOCAL_TELEMETRY_FILENAME
    rendered_text = prompt_path.read_text(encoding="utf-8")

    assert telemetry_path.exists()
    assert json.loads(telemetry_path.read_text(encoding="utf-8")) == telemetry_payload
    assert f"- {telemetry_path}" in rendered
    assert f"- {telemetry_path}" in rendered_text
    assert "use the task-local telemetry file at" in rendered_text


def test_status_json_inside_worker_run_blocks_with_task_local_guidance(monkeypatch, tmp_path: Path) -> None:
    module = _load_module()
    root = tmp_path
    args = _args(root)
    args.command = "status"
    args.json = True
    args.live_refresh = False

    state_root = Path(args.state_root)
    state_root.mkdir(parents=True, exist_ok=True)
    run_dir = state_root / "runs" / "run-123"
    run_dir.mkdir(parents=True, exist_ok=True)
    prompt_path = run_dir / "prompt.txt"
    prompt_path.write_text("read files first\n", encoding="utf-8")

    frontier_path = root / "full-product-frontier.yaml"
    frontier_path.write_text("frontier: []\n", encoding="utf-8")
    handoff_path = Path(args.handoff_path)
    handoff_path.write_text("handoff\n", encoding="utf-8")
    readiness_path = Path(args.flagship_product_readiness_path)
    readiness_path.write_text("{}\n", encoding="utf-8")
    module._write_json(
        module._state_payload_path(state_root),
        {
            "full_product_frontier_path": str(frontier_path),
        },
    )

    monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_ACTIVE_RUN_ID", "run-123")
    monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_ACTIVE_RUN_DIR", str(run_dir))
    monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_STATUS_BUDGET", "0")
    monkeypatch.setattr(module, "parse_args", lambda: args)

    stdout = io.StringIO()
    stderr = io.StringIO()
    with pytest.raises(SystemExit) as excinfo:
        with redirect_stdout(stdout), redirect_stderr(stderr):
            module.main()
    assert excinfo.value.code == 2
    payload = json.loads(stdout.getvalue())
    assert payload["command"] == "status"
    assert payload["status_budget_exhausted"] is True
    assert payload["warning"].startswith("worker_status_budget_exhausted")
    stderr_text = stderr.getvalue()
    assert "status_blocked_inside_worker_run" in stderr_text
    assert "worker_status_budget_exhausted" in stderr_text


def test_eta_json_inside_worker_run_blocks_with_task_local_guidance(monkeypatch, tmp_path: Path) -> None:
    module = _load_module()
    root = tmp_path
    args = _args(root)
    args.command = "eta"
    args.json = True

    state_root = Path(args.state_root)
    state_root.mkdir(parents=True, exist_ok=True)
    run_dir = state_root / "runs" / "run-eta"
    run_dir.mkdir(parents=True, exist_ok=True)
    prompt_path = run_dir / "prompt.txt"
    prompt_path.write_text("read files first\n", encoding="utf-8")

    frontier_path = root / "full-product-frontier.yaml"
    frontier_path.write_text("frontier: []\n", encoding="utf-8")
    handoff_path = Path(args.handoff_path)
    handoff_path.write_text("handoff\n", encoding="utf-8")
    readiness_path = Path(args.flagship_product_readiness_path)
    readiness_path.write_text("{}\n", encoding="utf-8")
    module._write_json(
        module._state_payload_path(state_root),
        {
            "frontier_ids": [11, 12],
            "open_milestone_ids": [11, 12, 13],
            "full_product_frontier_path": str(frontier_path),
            "eta": {
                "status": "tracked",
                "eta_human": "tracked",
                "summary": "3 open milestones remain (2 in progress, 1 not started)",
                "remaining_open_milestones": 3,
                "remaining_in_progress_milestones": 2,
                "remaining_not_started_milestones": 1,
            },
        },
    )

    monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_ACTIVE_RUN_ID", "run-eta")
    monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_ACTIVE_RUN_DIR", str(run_dir))
    monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_STATUS_BUDGET", "0")
    monkeypatch.setattr(module, "parse_args", lambda: args)

    stdout = io.StringIO()
    stderr = io.StringIO()
    with pytest.raises(SystemExit) as excinfo:
        with redirect_stdout(stdout), redirect_stderr(stderr):
            module.main()
    assert excinfo.value.code == 2
    payload = json.loads(stdout.getvalue())
    assert payload["command"] == "eta"
    assert payload["status_budget_exhausted"] is True
    assert payload["warning"].startswith("worker_status_budget_exhausted")
    stderr_text = stderr.getvalue()
    assert "status_blocked_inside_worker_run" in stderr_text
    assert "worker_status_budget_exhausted" in stderr_text


def test_status_json_inside_worker_run_returns_task_local_snapshot_before_budget_exhausts(
    monkeypatch, tmp_path: Path
) -> None:
    module = _load_module()
    root = tmp_path
    args = _args(root)
    args.command = "status"
    args.json = True

    state_root = Path(args.state_root)
    state_root.mkdir(parents=True, exist_ok=True)
    run_dir = state_root / "runs" / "run-allowed"
    run_dir.mkdir(parents=True, exist_ok=True)
    prompt_path = run_dir / "prompt.txt"
    prompt_path.write_text("read files first\n", encoding="utf-8")
    module._write_json(
        module._state_payload_path(state_root),
        {
            "frontier_ids": [44],
            "open_milestone_ids": [44],
            "eta": {
                "status": "tracked",
                "eta_human": "10h-1d",
                "summary": "1 open milestone remains.",
                "remaining_open_milestones": 1,
                "remaining_in_progress_milestones": 1,
                "remaining_not_started_milestones": 0,
            },
        },
    )

    monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_ACTIVE_RUN_ID", "run-allowed")
    monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_ACTIVE_RUN_DIR", str(run_dir))
    monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_STATUS_BUDGET", "1")
    monkeypatch.setattr(module, "parse_args", lambda: args)

    stdout = io.StringIO()
    stderr = io.StringIO()
    with pytest.raises(SystemExit) as excinfo:
        with redirect_stdout(stdout), redirect_stderr(stderr):
            module.main()

    assert excinfo.value.code == 0
    payload = json.loads(stdout.getvalue())
    assert payload["command"] == "status"
    assert payload["nonfatal_fallback"] is True
    assert payload["polling_disabled"] is True
    assert payload["status_query_supported"] is False
    assert payload["eta"]["status"] == "tracked"
    assert payload["eta"]["eta_human"] == "10h-1d"
    assert payload["frontier_ids"] == [44]
    assert payload["open_milestone_ids"] == [44]
    assert payload["prompt_path"] == str(prompt_path)
    assert stderr.getvalue() == ""


def test_status_json_inside_worker_run_allows_two_probes_then_stays_nonfatal(monkeypatch, tmp_path: Path) -> None:
    module = _load_module()
    root = tmp_path
    args = _args(root)
    args.command = "status"
    args.json = True

    state_root = Path(args.state_root)
    state_root.mkdir(parents=True, exist_ok=True)
    run_dir = state_root / "runs" / "run-budget-2"
    run_dir.mkdir(parents=True, exist_ok=True)
    prompt_path = run_dir / "prompt.txt"
    prompt_path.write_text("read files first\n", encoding="utf-8")
    module._write_json(
        module._state_payload_path(state_root),
        {
            "frontier_ids": [45],
            "open_milestone_ids": [45],
            "eta": {
                "status": "tracked",
                "eta_human": "9h-22h",
                "summary": "1 open milestone remains.",
                "remaining_open_milestones": 1,
                "remaining_in_progress_milestones": 1,
                "remaining_not_started_milestones": 0,
            },
        },
    )

    monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_ACTIVE_RUN_ID", "run-budget-2")
    monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_ACTIVE_RUN_DIR", str(run_dir))
    monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_STATUS_BUDGET", "2")
    monkeypatch.setattr(module, "parse_args", lambda: args)

    for expected_count in (1, 2):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with pytest.raises(SystemExit) as excinfo:
            with redirect_stdout(stdout), redirect_stderr(stderr):
                module.main()
        assert excinfo.value.code == 0
        payload = json.loads(stdout.getvalue())
        assert payload["nonfatal_fallback"] is True
        assert payload["prompt_path"] == str(prompt_path)
        assert stderr.getvalue() == ""
        budget_payload = json.loads((run_dir / ".status_budget.json").read_text(encoding="utf-8"))
        assert budget_payload["count"] == expected_count
        assert budget_payload["budget"] == 2

    stdout = io.StringIO()
    stderr = io.StringIO()
    with pytest.raises(SystemExit) as excinfo:
        with redirect_stdout(stdout), redirect_stderr(stderr):
            module.main()
    assert excinfo.value.code == 0
    payload = json.loads(stdout.getvalue())
    assert payload["command"] == "status"
    assert payload["status_budget_exhausted"] is True
    assert payload["warning"].startswith("worker_status_budget_exhausted")
    assert stderr.getvalue() == ""


def test_worker_status_block_message_prefers_active_run_shard_state_root(
    monkeypatch, tmp_path: Path
) -> None:
    module = _load_module()
    root = tmp_path
    aggregate_root = root / "state" / "chummer_design_supervisor"
    shard_root = aggregate_root / "shard-2"
    run_dir = shard_root / "runs" / "run-shard-2"
    run_dir.mkdir(parents=True, exist_ok=True)

    module._write_json(
        aggregate_root / "state.json",
        {
            "full_product_frontier_path": "/tmp/aggregate/shard-1.generated.yaml",
        },
    )
    module._write_json(
        shard_root / "state.json",
        {
            "full_product_frontier_path": "/tmp/shards/shard-2.generated.yaml",
        },
    )
    runtime_handoff_path = shard_root / "ACTIVE_RUN_HANDOFF.generated.md"
    runtime_handoff_path.write_text("worker-safe handoff\n", encoding="utf-8")
    telemetry_path = run_dir / module.TASK_LOCAL_TELEMETRY_FILENAME
    telemetry_path.write_text("{}\n", encoding="utf-8")

    args = _args(root)
    args.command = "status"
    args.state_root = str(aggregate_root)

    monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_ACTIVE_RUN_ID", "run-shard-2")
    monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_ACTIVE_RUN_DIR", str(run_dir))

    message = module._worker_status_block_message(args, "worker_status_budget_exhausted")

    assert "run_id: run-shard-2" in message
    assert "prompt_path: " + str(run_dir / "prompt.txt") in message
    assert f"task_local_telemetry_path: {telemetry_path}" in message
    assert f"runtime_handoff_path: {runtime_handoff_path}" in message
    assert "full_product_frontier_path: /tmp/shards/shard-2.generated.yaml" in message
    assert "/tmp/aggregate/shard-1.generated.yaml" not in message
    assert "\nhandoff_path: " not in f"\n{message}"


def test_worker_status_task_local_payload_falls_back_to_shard_eta_aliases(
    monkeypatch, tmp_path: Path
) -> None:
    module = _load_module()
    root = tmp_path
    aggregate_root = root / "state" / "chummer_design_supervisor"
    shard_root = aggregate_root / "shard-2"
    run_dir = shard_root / "runs" / "run-shard-2"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "prompt.txt").write_text("prompt\n", encoding="utf-8")
    telemetry_path = run_dir / module.TASK_LOCAL_TELEMETRY_FILENAME
    telemetry_path.write_text("{}\n", encoding="utf-8")

    module._write_json(
        aggregate_root / "state.json",
        {
            "active_runs_count": 7,
            "eta": {
                "status": "tracked",
                "eta_human": "2d-5d",
                "summary": "7 open milestones remain.",
                "remaining_open_milestones": 7,
                "remaining_in_progress_milestones": 5,
                "remaining_not_started_milestones": 2,
            },
        },
    )
    module._write_json(
        shard_root / "state.json",
        {
            "frontier_ids": [22],
            "open_milestone_ids": [22],
            "eta_status": "flagship_delivery",
            "eta_human": "11h-1.1d",
            "eta_summary": "Milestone 'Flagship desktop client and workbench finish' remains open.",
            "remaining_open_milestones": 1,
            "remaining_not_started_milestones": 1,
            "remaining_in_progress_milestones": 0,
        },
    )

    args = _args(root)
    args.command = "status"
    args.state_root = str(aggregate_root)
    monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_ACTIVE_RUN_ID", "run-shard-2")
    monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_ACTIVE_RUN_DIR", str(run_dir))

    payload = module._worker_status_task_local_payload(args, "")

    assert payload["active_runs_count"] == 7
    assert payload["task_local_telemetry_path"] == str(telemetry_path)
    assert payload["eta"]["status"] == "flagship_delivery"
    assert payload["eta"]["eta_human"] == "11h-1.1d"
    assert payload["eta"]["remaining_open_milestones"] == 1
    assert payload["eta"]["remaining_not_started_milestones"] == 1
    assert payload["eta"]["remaining_in_progress_milestones"] == 0
    assert payload["eta"]["summary"] == "Milestone 'Flagship desktop client and workbench finish' remains open."


def test_worker_status_task_local_payload_prefers_local_open_slice_over_aggregate_eta(
    monkeypatch, tmp_path: Path
) -> None:
    module = _load_module()
    root = tmp_path
    aggregate_root = root / "state" / "chummer_design_supervisor"
    shard_root = aggregate_root / "shard-2"
    run_dir = shard_root / "runs" / "run-shard-2"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "prompt.txt").write_text("prompt\n", encoding="utf-8")

    module._write_json(
        aggregate_root / "state.json",
        {
            "active_runs_count": 6,
            "eta": {
                "status": "tracked",
                "eta_human": "tracked",
                "summary": "10 open milestones remain (10 in progress, 0 not started).",
                "remaining_open_milestones": 10,
                "remaining_in_progress_milestones": 10,
                "remaining_not_started_milestones": 0,
            },
        },
    )
    module._write_json(
        shard_root / "state.json",
        {
            "frontier_ids": [22],
            "open_milestone_ids": [22],
        },
    )

    args = _args(root)
    args.command = "status"
    args.state_root = str(aggregate_root)
    monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_ACTIVE_RUN_ID", "run-shard-2")
    monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_ACTIVE_RUN_DIR", str(run_dir))

    payload = module._worker_status_task_local_payload(args, "")

    assert payload["active_runs_count"] == 6
    assert payload["eta"]["remaining_open_milestones"] == 1
    assert payload["eta"]["remaining_not_started_milestones"] == 1
    assert payload["eta"]["remaining_in_progress_milestones"] == 0
    assert payload["eta"]["summary"] == "1 open milestone remains in the current shard slice."


def test_stamp_worker_supervisor_guard_defaults_status_budget_to_one(tmp_path: Path) -> None:
    module = _load_module()
    run_dir = tmp_path / "runs" / "run-123"

    updated = module._stamp_worker_supervisor_guard({}, run_id="run-123", run_dir=run_dir)

    assert updated["CHUMMER_DESIGN_SUPERVISOR_ACTIVE_RUN_ID"] == "run-123"
    assert updated["CHUMMER_DESIGN_SUPERVISOR_STATUS_BUDGET"] == "1"
    assert updated["CHUMMER_DESIGN_SUPERVISOR_REAL_PYTHON3"]
    assert updated["PATH"].split(os.pathsep)[0] == str((module.DEFAULT_WORKSPACE_ROOT / "scripts" / "codex-shims").resolve())
    assert updated["BASH_ENV"] == str(run_dir / module.WORKER_BASH_ENV_FILENAME)
    assert Path(updated["BASH_ENV"]).exists()


def test_worker_python3_shim_serves_task_local_telemetry_file(tmp_path: Path) -> None:
    module = _load_module()
    aggregate_root = tmp_path / "state" / "chummer_design_supervisor"
    shard_root = aggregate_root / "shard-2"
    run_dir = shard_root / "runs" / "run-123"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "prompt.txt").write_text("prompt\n", encoding="utf-8")
    telemetry_path = run_dir / module.TASK_LOCAL_TELEMETRY_FILENAME
    telemetry_payload = {
        "active_runs_count": 6,
        "remaining_open_milestones": 1,
        "remaining_not_started_milestones": 1,
        "remaining_in_progress_milestones": 0,
        "eta_human": "11h-1.1d",
        "summary": "1 open milestone remains in the current shard slice.",
    }
    telemetry_path.write_text(json.dumps(telemetry_payload), encoding="utf-8")
    module._write_json(
        aggregate_root / "state.json",
        {
            "active_runs_count": 6,
            "eta": {
                "status": "tracked",
                "eta_human": "11h-1.1d",
                "summary": "1 open milestone remains in the current shard slice.",
                "remaining_open_milestones": 1,
                "remaining_in_progress_milestones": 0,
                "remaining_not_started_milestones": 1,
            },
        },
    )
    module._write_json(
        shard_root / "state.json",
        {
            "frontier_ids": [22],
            "open_milestone_ids": [22],
        },
    )
    shim_path = module.DEFAULT_WORKSPACE_ROOT / "scripts" / "codex-shims" / "python3"
    env = os.environ.copy()
    env["CHUMMER_DESIGN_SUPERVISOR_ACTIVE_RUN_DIR"] = str(run_dir)
    env["CHUMMER_DESIGN_SUPERVISOR_ACTIVE_RUN_ID"] = "run-123"
    env["CHUMMER_DESIGN_SUPERVISOR_REAL_PYTHON3"] = str(shutil.which("python3") or sys.executable)

    completed = subprocess.run(
        [
            "bash",
            str(shim_path),
            "/docker/fleet/scripts/chummer_design_supervisor.py",
            "status",
            "--state-root",
            str(shard_root),
            "--json",
        ],
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )

    assert completed.returncode == 2
    payload = json.loads(completed.stdout)
    assert payload["active_runs_count"] == 6
    assert payload["eta"]["remaining_open_milestones"] == 1
    assert payload["eta"]["eta_human"] == "11h-1.1d"
    assert "status_blocked_inside_worker_run" in completed.stderr
    assert "worker_status_budget_exhausted" in completed.stderr


def test_worker_bash_env_redirects_python3_status_helper_to_task_local_telemetry(tmp_path: Path) -> None:
    module = _load_module()
    aggregate_root = tmp_path / "state" / "chummer_design_supervisor"
    shard_root = aggregate_root / "shard-2"
    run_dir = shard_root / "runs" / "run-123"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "prompt.txt").write_text("prompt\n", encoding="utf-8")
    telemetry_path = run_dir / module.TASK_LOCAL_TELEMETRY_FILENAME
    telemetry_payload = {
        "active_runs_count": 9,
        "remaining_open_milestones": 2,
        "remaining_not_started_milestones": 1,
        "remaining_in_progress_milestones": 1,
        "eta_human": "tracked",
        "summary": "2 open milestones remain in the current shard slice.",
    }
    telemetry_path.write_text(json.dumps(telemetry_payload), encoding="utf-8")
    module._write_json(
        aggregate_root / "state.json",
        {
            "active_runs_count": 9,
            "eta": {
                "status": "tracked",
                "eta_human": "tracked",
                "summary": "2 open milestones remain in the current shard slice.",
                "remaining_open_milestones": 2,
                "remaining_in_progress_milestones": 1,
                "remaining_not_started_milestones": 1,
            },
        },
    )
    module._write_json(
        shard_root / "state.json",
        {
            "frontier_ids": [22, 23],
            "open_milestone_ids": [22, 23],
        },
    )
    env = module._stamp_worker_supervisor_guard({}, run_id="run-123", run_dir=run_dir)
    env["CHUMMER_DESIGN_SUPERVISOR_REAL_PYTHON3"] = str(shutil.which("python3") or sys.executable)

    completed = subprocess.run(
        [
            "/bin/bash",
            "-lc",
            f"python3 /docker/fleet/scripts/chummer_design_supervisor.py status --state-root {shard_root} --json",
        ],
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )

    assert completed.returncode == 2
    payload = json.loads(completed.stdout)
    assert payload["active_runs_count"] == 9
    assert payload["eta"]["remaining_open_milestones"] == 2
    assert payload["eta"]["summary"] == "2 open milestones remain in the current shard slice."
    assert "status_blocked_inside_worker_run" in completed.stderr
    assert "worker_status_budget_exhausted" in completed.stderr


def test_worker_python3_shim_does_not_intercept_flat_task_local_json_parse(tmp_path: Path) -> None:
    module = _load_module()
    run_dir = tmp_path / "runs" / "run-123"
    run_dir.mkdir(parents=True, exist_ok=True)
    telemetry_path = run_dir / module.TASK_LOCAL_TELEMETRY_FILENAME
    telemetry_path.write_text(
        json.dumps(
            {
                "remaining_open_milestones": 2,
                "remaining_not_started_milestones": 1,
                "remaining_in_progress_milestones": 1,
                "eta_human": "tracked",
            }
        ),
        encoding="utf-8",
    )
    shim_path = module.DEFAULT_WORKSPACE_ROOT / "scripts" / "codex-shims" / "python3"
    env = os.environ.copy()
    env["CHUMMER_DESIGN_SUPERVISOR_ACTIVE_RUN_DIR"] = str(run_dir)
    env["CHUMMER_DESIGN_SUPERVISOR_REAL_PYTHON3"] = str(shutil.which("python3") or sys.executable)

    completed = subprocess.run(
        [
            "/bin/bash",
            "-lc",
            (
                "printf '%s' '{\"remaining_open_milestones\":2,"
                "\"remaining_not_started_milestones\":1,"
                "\"remaining_in_progress_milestones\":1,"
                "\"eta_human\":\"tracked\"}' | "
                f"'{shim_path}' -c "
                "\"import json,sys;payload=json.load(sys.stdin);"
                "print(payload['remaining_open_milestones']);"
                "print(payload['eta_human'])\""
            ),
        ],
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )

    assert completed.returncode == 0
    assert completed.stdout.splitlines() == ["2", "tracked"]
    assert not (run_dir / ".status_helper_pipeline_hits").exists()


def test_worker_python3_shim_still_intercepts_nested_status_style_json_parse(tmp_path: Path) -> None:
    module = _load_module()
    run_dir = tmp_path / "runs" / "run-123"
    run_dir.mkdir(parents=True, exist_ok=True)
    telemetry_path = run_dir / module.TASK_LOCAL_TELEMETRY_FILENAME
    telemetry_path.write_text(
        json.dumps(
            {
                "active_runs_count": 9,
                "remaining_open_milestones": 2,
                "remaining_not_started_milestones": 1,
                "remaining_in_progress_milestones": 1,
                "eta_human": "tracked",
                "summary": "2 open milestones remain in the current shard slice.",
            }
        ),
        encoding="utf-8",
    )
    shim_path = module.DEFAULT_WORKSPACE_ROOT / "scripts" / "codex-shims" / "python3"
    env = os.environ.copy()
    env["CHUMMER_DESIGN_SUPERVISOR_ACTIVE_RUN_DIR"] = str(run_dir)
    env["CHUMMER_DESIGN_SUPERVISOR_REAL_PYTHON3"] = str(shutil.which("python3") or sys.executable)

    completed = subprocess.run(
        [
            "/bin/bash",
            "-lc",
            (
                "printf '%s' '{\"task_local_only\":true,"
                "\"eta\":{\"remaining_open_milestones\":2,"
                "\"remaining_not_started_milestones\":1,"
                "\"remaining_in_progress_milestones\":1,"
                "\"eta_human\":\"tracked\"}}' | "
                f"'{shim_path}' -c "
                "\"import json,sys;payload=json.load(sys.stdin);"
                "eta=payload.get('eta') or payload;"
                "print(eta['remaining_open_milestones']);"
                "print(eta['eta_human'])\""
            ),
        ],
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )

    assert completed.returncode == 2
    payload = json.loads(completed.stdout)
    assert payload["active_runs_count"] is None
    assert payload["remaining_open_milestones"] is None
    assert payload["eta_human"] == "implementation-only"
    assert "status_blocked_inside_worker_run" in completed.stderr
    assert "worker_status_budget_exhausted" in completed.stderr
    assert (run_dir / ".status_helper_pipeline_hits").read_text(encoding="utf-8").strip() == "1"


def test_worker_python3_shim_recycles_repeated_nested_status_style_reads(tmp_path: Path) -> None:
    module = _load_module()
    run_dir = tmp_path / "runs" / "run-123"
    run_dir.mkdir(parents=True, exist_ok=True)
    telemetry_path = run_dir / module.TASK_LOCAL_TELEMETRY_FILENAME
    telemetry_path.write_text(
        json.dumps(
            {
                "active_runs_count": 9,
                "remaining_open_milestones": 2,
                "remaining_not_started_milestones": 1,
                "remaining_in_progress_milestones": 1,
                "eta_human": "tracked",
                "summary": "2 open milestones remain in the current shard slice.",
                "first_commands": [
                    "cat TASK_LOCAL_TELEMETRY.generated.json",
                    "sed -n '1,220p' /docker/chummercomplete/chummer-design/products/chummer/PROGRAM_MILESTONES.yaml",
                ],
            }
        ),
        encoding="utf-8",
    )
    shim_path = module.DEFAULT_WORKSPACE_ROOT / "scripts" / "codex-shims" / "python3"
    env = os.environ.copy()
    env["CHUMMER_DESIGN_SUPERVISOR_ACTIVE_RUN_DIR"] = str(run_dir)
    env["CHUMMER_DESIGN_SUPERVISOR_REAL_PYTHON3"] = str(shutil.which("python3") or sys.executable)

    command = (
        "printf '%s' '{\"task_local_only\":true,"
        "\"eta\":{\"remaining_open_milestones\":2,"
        "\"remaining_not_started_milestones\":1,"
        "\"remaining_in_progress_milestones\":1,"
        "\"eta_human\":\"tracked\"}}' | "
        f"'{shim_path}' -c "
        "\"import json,sys;payload=json.load(sys.stdin);"
        "eta=payload.get('eta') or payload;"
        "print(json.dumps({'active_runs_count':payload.get('active_runs_count'),"
        "'remaining_open_milestones':payload.get('remaining_open_milestones'),"
        "'eta_human':payload.get('eta_human'),'summary':payload.get('summary')}))\""
    )

    first = subprocess.run(
        ["/bin/bash", "-lc", command],
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )
    second = subprocess.run(
        ["/bin/bash", "-lc", command],
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )

    assert first.returncode == 2
    assert second.returncode == 2
    first_payload = json.loads(first.stdout)
    second_payload = json.loads(second.stdout)
    assert first_payload["eta_human"] == "implementation-only"
    assert second_payload["eta_human"] == "implementation-only"
    assert "Repeated status helper request ignored." in second_payload["summary"]
    assert "status_blocked_inside_worker_run" in first.stderr
    assert "status_blocked_inside_worker_run" in second.stderr
    assert "worker_status_budget_exhausted" in first.stderr
    assert "worker_status_budget_exhausted" in second.stderr
    assert (run_dir / ".status_helper_pipeline_hits").read_text(encoding="utf-8").strip() == "2"


def test_launch_worker_prefers_full_lanes_and_uses_anonymous_core_when_accounts_are_saturated(monkeypatch) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_registry(root / "registry.yaml")
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("W2 milestone `21` remains active.\n", encoding="utf-8")
        (root / "accounts.yaml").write_text(
            yaml.safe_dump(
                {
                    "account_policy": {"protected_owner_ids": ["tibor.girschele"]},
                    "accounts": {
                        "acct-ea-core": {
                            "auth_kind": "ea",
                            "owner_id": "tibor.girschele",
                            "allowed_models": ["ea-coder-hard"],
                            "health_state": "ready",
                            "lane": "core",
                            "max_parallel_runs": 1,
                        },
                        "acct-ea-repair": {
                            "auth_kind": "ea",
                            "owner_id": "tibor.girschele",
                            "allowed_models": ["ea-coder-fast"],
                            "health_state": "ready",
                            "lane": "repair",
                            "max_parallel_runs": 2,
                        },
                    },
                }
            ),
            encoding="utf-8",
        )
        args = _args(root)
        args.worker_bin = "/docker/fleet/scripts/codex-shims/codexea"
        args.worker_lane = "core"
        args.worker_model = "ea-coder-hard"
        context = module.derive_context(args)

        monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_PREFER_FULL_EA_LANES", "1")
        monkeypatch.setattr(module, "_active_account_claim_counts", lambda _state_root: {"acct-ea-core": 1})
        monkeypatch.setattr(module, "_prepare_account_environment", lambda _state_root, _workspace_root, _account: {})

        def fake_run_worker_attempt(
            command,
            *,
            prompt,
            workspace_root,
            worker_env,
            timeout_seconds,
            last_message_path,
            state_root,
            run_id,
            stdout_sink=None,
            stderr_sink=None,
        ):
            last_message_path.write_text(
                "What shipped: repair lane kept work moving\n"
                "What remains: follow-through\n"
                "Exact blocker: none\n",
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        monkeypatch.setattr(module, "_run_worker_attempt", fake_run_worker_attempt)

        run = module.launch_worker(args, context, root / "state")

        assert run.worker_exit_code == 0
        assert run.accepted is True
        assert run.selected_account_alias == "lane:core"
        assert run.attempted_accounts == ["lane:core"]
        assert run.attempted_models == ["ea-coder-hard-batch"]
        assert run.worker_command[:3] == ["/docker/fleet/scripts/codex-shims/codexea", "core", "exec"]


def test_launch_worker_uses_shard_scoped_run_ids(monkeypatch) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_registry(root / "registry.yaml")
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("W2 milestone `21` remains active.\n", encoding="utf-8")
        args = _args(root)
        args.worker_bin = "/docker/fleet/scripts/codex-shims/codexea"
        args.worker_lane = "core"
        args.worker_model = "ea-coder-hard"
        context = module.derive_context(args)

        monkeypatch.setattr(module, "_slug_timestamp", lambda value=None: "20260413T151110Z")
        monkeypatch.setattr(module, "_prepare_account_environment", lambda _state_root, _workspace_root, _account: {})

        def fake_run_worker_attempt(
            command,
            *,
            prompt,
            workspace_root,
            worker_env,
            timeout_seconds,
            last_message_path,
            state_root,
            run_id,
            stdout_sink=None,
            stderr_sink=None,
        ):
            last_message_path.write_text(
                "What shipped: kept work moving\n"
                "What remains: follow-through\n"
                "Exact blocker: none\n",
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        monkeypatch.setattr(module, "_run_worker_attempt", fake_run_worker_attempt)

        shard_one_run = module.launch_worker(args, context, root / "state" / "shard-1")
        shard_two_run = module.launch_worker(args, context, root / "state" / "shard-2")

        assert shard_one_run.run_id == "20260413T151110Z-shard-1"
        assert shard_two_run.run_id == "20260413T151110Z-shard-2"
        assert shard_one_run.run_id != shard_two_run.run_id


def test_launch_worker_falls_back_to_frontier_ids_when_open_milestones_are_empty(monkeypatch) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_registry(root / "registry.yaml")
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("W2 milestone `21` remains active.\n", encoding="utf-8")
        args = _args(root)
        args.worker_bin = "/docker/fleet/scripts/codex-shims/codexea"
        args.worker_lane = "core"
        args.worker_model = "ea-coder-hard"
        context = module.derive_context(args)
        context["open_milestones"] = []
        context["frontier"] = [context["frontier"][0]]
        context["frontier_ids"] = [context["frontier"][0].id]

        monkeypatch.setattr(module, "_prepare_account_environment", lambda _state_root, _workspace_root, _account: {})

        def fake_run_worker_attempt(
            command,
            *,
            prompt,
            workspace_root,
            worker_env,
            timeout_seconds,
            last_message_path,
            state_root,
            run_id,
            stdout_sink=None,
            stderr_sink=None,
        ):
            last_message_path.write_text(
                "What shipped: kept work moving\n"
                "What remains: follow-through\n"
                "Exact blocker: none\n",
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        monkeypatch.setattr(module, "_run_worker_attempt", fake_run_worker_attempt)

        run = module.launch_worker(args, context, root / "state" / "shard-1")

        assert run.frontier_ids == [context["frontier"][0].id]
        assert run.open_milestone_ids == [context["frontier"][0].id]


def test_launch_worker_uses_anonymous_core_before_repair_when_full_account_is_backed_off(monkeypatch) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_registry(root / "registry.yaml")
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("W2 milestone `21` remains active.\n", encoding="utf-8")
        (root / "accounts.yaml").write_text(
            yaml.safe_dump(
                {
                    "account_policy": {"protected_owner_ids": ["tibor.girschele"]},
                    "accounts": {
                        "acct-ea-core": {
                            "auth_kind": "ea",
                            "owner_id": "tibor.girschele",
                            "allowed_models": ["ea-coder-hard"],
                            "health_state": "ready",
                            "lane": "core",
                            "max_parallel_runs": 1,
                        },
                        "acct-ea-repair": {
                            "auth_kind": "ea",
                            "owner_id": "tibor.girschele",
                            "allowed_models": ["ea-coder-fast"],
                            "health_state": "ready",
                            "lane": "repair",
                            "max_parallel_runs": 2,
                        },
                    },
                }
            ),
            encoding="utf-8",
        )
        args = _args(root)
        args.worker_bin = "/docker/fleet/scripts/codex-shims/codexea"
        args.worker_lane = "core"
        args.worker_model = "ea-coder-hard"
        context = module.derive_context(args)
        state_root = root / "state"
        state_root.mkdir(parents=True, exist_ok=True)
        module._write_account_runtime(
            module._account_runtime_path(state_root),
            {
                "sources": {
                    "alias:acct-ea-core": {
                        "alias": "acct-ea-core",
                        "source_key": "alias:acct-ea-core",
                        "backoff_until": "2026-04-08T22:40:43Z",
                        "last_error": "usage-limited; recheck at 2026-04-08T22:40:43Z",
                    }
                }
            },
        )

        monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_PREFER_FULL_EA_LANES", "1")
        monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_ACCOUNT_RESTORE_PROBE_SECONDS", "0")
        monkeypatch.setattr(module, "_prepare_account_environment", lambda _state_root, _workspace_root, _account: {})
        monkeypatch.setattr(module, "_active_account_claim_counts", lambda _state_root: {})
        monkeypatch.setattr(
            module,
            "_utc_now",
            lambda: dt.datetime(2026, 4, 8, 22, 35, 0, tzinfo=dt.timezone.utc),
        )

        def fake_run_worker_attempt(
            command,
            *,
            prompt,
            workspace_root,
            worker_env,
            timeout_seconds,
            last_message_path,
            state_root,
            run_id,
            stdout_sink=None,
            stderr_sink=None,
        ):
            last_message_path.write_text(
                "What shipped: core lane resumed\n"
                "What remains: follow-through\n"
                "Exact blocker: none\n",
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        monkeypatch.setattr(module, "_run_worker_attempt", fake_run_worker_attempt)

        run = module.launch_worker(
            args,
            context,
            state_root,
            worker_lane_health={
                "status": "pass",
                "routable_lanes": ["core"],
                "lanes": {
                    "core": {
                        "worker_lane": "core",
                        "profile": "core_batch",
                        "state": "ready",
                        "routable": True,
                        "ready_slots": 59,
                        "reason": "healthy",
                    }
                },
            },
        )

        runtime = module._read_account_runtime(module._account_runtime_path(state_root))

        assert run.worker_exit_code == 0
        assert run.accepted is True
        assert run.selected_account_alias == "lane:core"
        assert run.attempted_accounts == ["lane:core"]
        assert run.attempted_models == ["ea-coder-hard-batch"]
        assert run.worker_command[:3] == ["/docker/fleet/scripts/codex-shims/codexea", "core", "exec"]
        assert runtime["sources"]["alias:acct-ea-core"]["backoff_until"] == "2026-04-08T22:40:43Z"
        assert runtime["sources"]["alias:acct-ea-core"].get("restore_probe_at", "") == ""


def test_launch_worker_uses_anonymous_full_lane_before_rescue_for_routed_ea_shards(monkeypatch) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_registry(root / "registry.yaml")
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("W2 milestone `21` remains active.\n", encoding="utf-8")
        (root / "accounts.yaml").write_text(
            yaml.safe_dump(
                {
                    "account_policy": {"protected_owner_ids": ["tibor.girschele"]},
                    "accounts": {
                        "acct-ea-core": {
                            "auth_kind": "ea",
                            "owner_id": "tibor.girschele",
                            "allowed_models": ["ea-coder-hard"],
                            "health_state": "ready",
                            "lane": "core",
                            "max_parallel_runs": 1,
                        },
                        "acct-ea-repair": {
                            "auth_kind": "ea",
                            "owner_id": "tibor.girschele",
                            "allowed_models": ["ea-coder-fast"],
                            "health_state": "ready",
                            "lane": "repair",
                            "max_parallel_runs": 2,
                        },
                    },
                }
            ),
            encoding="utf-8",
        )
        args = _args(root)
        args.worker_bin = "/docker/fleet/scripts/codex-shims/codexea"
        args.worker_lane = "audit_shard"
        args.worker_model = "ea-coder-hard"
        context = module.derive_context(args)
        state_root = root / "state"
        state_root.mkdir(parents=True, exist_ok=True)
        module._write_account_runtime(
            module._account_runtime_path(state_root),
            {
                "sources": {
                    "alias:acct-ea-core": {
                        "alias": "acct-ea-core",
                        "source_key": "alias:acct-ea-core",
                        "backoff_until": "2026-04-08T22:40:43Z",
                        "restore_probe_at": "2026-04-08T22:34:45Z",
                        "last_error": "usage-limited; recheck at 2026-04-08T22:40:43Z",
                    }
                }
            },
        )

        monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_PREFER_FULL_EA_LANES", "1")
        monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_ACCOUNT_RESTORE_PROBE_SECONDS", "300")
        monkeypatch.setattr(module, "_prepare_account_environment", lambda _state_root, _workspace_root, _account: {})
        monkeypatch.setattr(module, "_active_account_claim_counts", lambda _state_root: {})
        monkeypatch.setattr(
            module,
            "_utc_now",
            lambda: dt.datetime(2026, 4, 8, 22, 35, 0, tzinfo=dt.timezone.utc),
        )

        def fake_health_snapshot(phase_args, _lane_candidates):
            lane = str(getattr(phase_args, "worker_lane", "") or "")
            if lane == "core":
                return {
                    "status": "pass",
                    "routable_lanes": ["core"],
                    "lanes": {
                        "core": {
                            "worker_lane": "core",
                            "profile": "core_batch",
                            "state": "ready",
                            "routable": True,
                            "ready_slots": 59,
                            "reason": "healthy",
                        }
                    },
                }
            return {
                "status": "pass",
                "routable_lanes": ["audit_shard"],
                "lanes": {
                    "audit_shard": {
                        "worker_lane": "audit_shard",
                        "profile": "audit_shard",
                        "state": "unknown",
                        "known": False,
                        "routable": True,
                        "reason": "healthy global snapshot",
                    }
                },
            }

        monkeypatch.setattr(module, "_direct_worker_lane_health_snapshot", fake_health_snapshot)

        def fake_run_worker_attempt(
            command,
            *,
            prompt,
            workspace_root,
            worker_env,
            timeout_seconds,
            last_message_path,
            state_root,
            run_id,
            stdout_sink=None,
            stderr_sink=None,
        ):
            last_message_path.write_text(
                "What shipped: anonymous core lane kept work moving\n"
                "What remains: follow-through\n"
                "Exact blocker: none\n",
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        monkeypatch.setattr(module, "_run_worker_attempt", fake_run_worker_attempt)

        run = module.launch_worker(args, context, state_root)

        assert run.worker_exit_code == 0
        assert run.accepted is True
        assert run.selected_account_alias == "lane:core"
        assert run.attempted_accounts == ["lane:core"]
        assert run.attempted_models == ["ea-coder-hard-batch"]
        assert run.worker_command[:3] == ["/docker/fleet/scripts/codex-shims/codexea", "core", "exec"]


def test_explicit_worker_timeout_seconds_overrides_stream_budget(monkeypatch) -> None:
    module = _load_module()
    monkeypatch.setattr(
        module,
        "_runtime_env_default",
        lambda name, default="": {
            "CHUMMER_DESIGN_SUPERVISOR_WORKER_TIMEOUT_SECONDS": "21600",
            "CHUMMER_DESIGN_SUPERVISOR_STREAM_IDLE_TIMEOUT_MS": "900000",
            "CHUMMER_DESIGN_SUPERVISOR_STREAM_MAX_RETRIES": "8",
        }.get(name, default),
    )

    assert module._default_worker_timeout_seconds() == 21600.0


def test_default_worker_timeout_seconds_tracks_codexea_stream_budget(monkeypatch) -> None:
    module = _load_module()
    monkeypatch.setattr(
        module,
        "_runtime_env_default",
        lambda name, default="": {
            "CODEXEA_STREAM_IDLE_TIMEOUT_MS": "900000",
            "CODEXEA_STREAM_MAX_RETRIES": "8",
        }.get(name, default),
    )

    assert module._default_worker_timeout_seconds() == 9000.0


def test_derive_context_applies_focus_within_explicit_handoff_frontier() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_registry(root / "registry.yaml")
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text(
            "\n".join(
                [
                    "# Handoff",
                    "",
                    "Current active frontier from design plus handoff:",
                    "- `6` Build Lab progression planner",
                    "- `15` Artifact shelf v2",
                    "- `18` Public trust surface v3",
                    "- `19` Guided onboarding",
                    "- `21` Rules Navigator v2",
                    "",
                    "Frontier milestone ids to prioritize first: 6, 15, 18, 19, 21",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        args = _args(root)
        args.focus_owner = ["chummer6-hub"]
        args.focus_text = ["trust", "publication"]

        context = module.derive_context(args)

        assert [item.id for item in context["frontier"]] == [18, 15, 19, 21]


def test_derive_context_honors_frontier_id_override_without_shard_reslicing() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_registry(root / "registry.yaml")
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text(
            "Frontier milestone ids to prioritize first: 6, 15, 18, 19, 21\n",
            encoding="utf-8",
        )
        aggregate_root = root / "state" / "chummer_design_supervisor"
        shard_roots = [aggregate_root / f"shard-{index}" for index in range(1, 6)]
        for shard_root in shard_roots:
            shard_root.mkdir(parents=True, exist_ok=True)
        (aggregate_root / "active_shards.json").write_text(
            json.dumps({"active_shards": [path.name for path in shard_roots]}),
            encoding="utf-8",
        )
        args = _args(root)
        args.state_root = str(shard_roots[3])
        args.frontier_id = [6, 15, 18, 19]

        context = module.derive_context(args)

        assert [item.id for item in context["frontier"]] == [6, 15, 18, 19]
        assert [item.id for item in context["open_milestones"]] == [6, 15, 18, 19]


def test_status_command_on_shard_root_reports_shard_local_frontier_not_aggregate_union() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "registry.yaml").write_text(
            yaml.safe_dump(
                {
                    "waves": [{"id": "W1"}, {"id": "W2"}],
                    "milestones": [
                        {
                            "id": 1,
                            "title": "Install lane",
                            "wave": "W1",
                            "status": "planned",
                            "owners": ["chummer6-ui"],
                            "exit_criteria": ["Install lane exists."],
                        },
                        {
                            "id": 2,
                            "title": "Workbench lane",
                            "wave": "W1",
                            "status": "planned",
                            "owners": ["chummer6-ui"],
                            "exit_criteria": ["Workbench exists."],
                        },
                        {
                            "id": 13,
                            "title": "Sourcebook parity",
                            "wave": "W2",
                            "status": "planned",
                            "owners": ["chummer6-core"],
                            "exit_criteria": ["Sourcebooks exist."],
                        },
                        {
                            "id": 14,
                            "title": "Settings parity",
                            "wave": "W2",
                            "status": "planned",
                            "owners": ["chummer6-core"],
                            "exit_criteria": ["Settings exist."],
                        },
                    ],
                }
            ),
            encoding="utf-8",
        )
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text(
            "Frontier milestone ids to prioritize first: 1, 2, 13, 14\n",
            encoding="utf-8",
        )
        aggregate_root = root / "state" / "chummer_design_supervisor"
        shard_one = aggregate_root / "shard-1"
        shard_two = aggregate_root / "shard-2"
        for shard_root, frontier_ids in ((shard_one, [13, 14]), (shard_two, [1, 2])):
            shard_root.mkdir(parents=True, exist_ok=True)
            (shard_root / "state.json").write_text(
                json.dumps(
                    {
                        "updated_at": "2026-04-04T15:20:00Z",
                        "mode": "loop",
                        "frontier_ids": frontier_ids,
                        "open_milestone_ids": [1, 2, 13, 14],
                    }
                ),
                encoding="utf-8",
            )
        (aggregate_root / "active_shards.json").write_text(
            json.dumps(
                {
                    "generated_at": "2026-04-04T15:20:00Z",
                    "topology_fingerprint": "abc123",
                    "active_shards": [
                        {"name": "shard-1", "index": 1, "frontier_ids": [13, 14]},
                        {"name": "shard-2", "index": 2, "frontier_ids": [1, 2]},
                    ],
                }
            ),
            encoding="utf-8",
        )

        result = subprocess.run(
            [
                sys.executable,
                str(MODULE_PATH),
                "status",
                "--json",
                "--registry-path",
                str(root / "registry.yaml"),
                "--program-milestones-path",
                str(root / "PROGRAM_MILESTONES.yaml"),
                "--roadmap-path",
                str(root / "ROADMAP.md"),
                "--handoff-path",
                str(root / "NEXT_SESSION_HANDOFF.md"),
                "--workspace-root",
                str(root),
                "--state-root",
                str(shard_one),
                "--frontier-id",
                "13",
                "--frontier-id",
                "14",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        payload = json.loads(result.stdout)

        assert payload["frontier_ids"] == [13, 14]
        assert "shards" not in payload


def _write_project_backlog(root: Path, *, project_id: str, repo_slug: str, task: str) -> None:
    projects_dir = root / "projects"
    projects_dir.mkdir(parents=True, exist_ok=True)
    (projects_dir / f"{project_id}.yaml").write_text(
        yaml.safe_dump(
            {
                "id": project_id,
                "path": str(root),
                "review": {"repo": repo_slug},
                "queue": [],
                "queue_sources": [{"kind": "worklist", "path": "WORKLIST.md", "mode": "replace"}],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (root / "WORKLIST.md").write_text(f"- [queued] wl-1 {task}\n", encoding="utf-8")


def _write_project_backlog_tasks(root: Path, *, project_id: str, repo_slug: str, tasks: list[str]) -> None:
    projects_dir = root / "projects"
    projects_dir.mkdir(parents=True, exist_ok=True)
    (projects_dir / f"{project_id}.yaml").write_text(
        yaml.safe_dump(
            {
                "id": project_id,
                "path": str(root),
                "review": {"repo": repo_slug},
                "queue": [],
                "queue_sources": [{"kind": "worklist", "path": "WORKLIST.md", "mode": "replace"}],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (root / "WORKLIST.md").write_text(
        "\n".join(f"- [queued] wl-{index + 1} {task}" for index, task in enumerate(tasks)) + "\n",
        encoding="utf-8",
    )


def test_repo_backlog_audit_ignores_terminal_config_queue_items() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        projects_dir = root / "projects"
        projects_dir.mkdir(parents=True, exist_ok=True)
        (projects_dir / "fleet.yaml").write_text(
            yaml.safe_dump(
                {
                    "id": "fleet",
                    "path": str(root),
                    "review": {"repo": "fleet"},
                    "queue": [
                        {
                            "package_id": "fleet-postclient-operating-profiles",
                            "title": "Add steady-state fleet operating profiles",
                            "status": "done",
                        },
                        {
                            "package_id": "fleet-postclient-proof-orchestration",
                            "title": "Promote executable gates into orchestrated jobs",
                            "status": "queued",
                        },
                    ],
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )

        args = _args(root)
        args.projects_dir = str(projects_dir)
        audit = module._repo_backlog_audit(args)

    assert audit["status"] == "fail"
    assert audit["open_item_count"] == 1
    assert audit["open_items"][0]["task"] == "Promote executable gates into orchestrated jobs"


def _write_completion_evidence(
    root: Path,
    *,
    ui_posture: str = "public",
    ui_stage: str = "publicly_promoted",
    design_drift_count: int = 0,
    public_promise_drift_count: int = 0,
    oldest_blocker_days: int = 0,
    release_health_state: str = "green_or_explained",
    journey_gate_health_state: str = "ready",
    active_wave_status: str = "complete",
    automation_alignment_state: str = "aligned",
    write_linux_desktop_exit_gate: bool = True,
    linux_desktop_exit_gate_status: str = "passed",
    linux_desktop_exit_gate_test_total: int = 14,
    linux_desktop_exit_gate_test_failed: int = 0,
    linux_desktop_exit_gate_test_skipped: int = 0,
    linux_desktop_exit_gate_generated_at: str | None = None,
    linux_desktop_exit_gate_app_key: str = "avalonia",
    linux_desktop_exit_gate_launch_target: str = "Chummer.Avalonia",
    linux_desktop_exit_gate_test_project_path: str = "Chummer.Desktop.Runtime.Tests/Chummer.Desktop.Runtime.Tests.csproj",
    linux_desktop_exit_gate_test_assembly_name: str = "Chummer.Desktop.Runtime.Tests.dll",
) -> None:
    now_text = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    (root / "UI_LOCAL_RELEASE_PROOF.generated.json").write_text(
        json.dumps({"contract_name": "chummer6-ui.local_release_proof", "status": "passed"}),
        encoding="utf-8",
    )
    (root / "DESKTOP_EXECUTABLE_EXIT_GATE.generated.json").write_text(
        json.dumps(
            {
                "contract_name": "chummer6-ui.desktop_executable_exit_gate",
                "status": "pass",
                "generatedAt": now_text,
            }
        ),
        encoding="utf-8",
    )
    (root / "DESKTOP_WORKFLOW_EXECUTION_GATE.generated.json").write_text(
        json.dumps({"contract_name": "chummer6-ui.desktop_workflow_execution_gate", "status": "pass"}),
        encoding="utf-8",
    )
    (root / "DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.generated.json").write_text(
        json.dumps({"contract_name": "chummer6-ui.desktop_visual_familiarity_exit_gate", "status": "pass"}),
        encoding="utf-8",
    )
    (root / "CHUMMER5A_DESKTOP_WORKFLOW_PARITY.generated.json").write_text(
        json.dumps({"contract_name": "chummer6-ui.chummer5a_desktop_workflow_parity", "status": "passed"}),
        encoding="utf-8",
    )
    (root / "SR4_DESKTOP_WORKFLOW_PARITY.generated.json").write_text(
        json.dumps({"contract_name": "chummer6-ui.sr4_desktop_workflow_parity", "status": "passed"}),
        encoding="utf-8",
    )
    (root / "SR6_DESKTOP_WORKFLOW_PARITY.generated.json").write_text(
        json.dumps({"contract_name": "chummer6-ui.sr6_desktop_workflow_parity", "status": "passed"}),
        encoding="utf-8",
    )
    (root / "SR4_SR6_DESKTOP_PARITY_FRONTIER.generated.json").write_text(
        json.dumps({"contract_name": "chummer6-ui.sr4_sr6_desktop_parity_frontier", "status": "passed"}),
        encoding="utf-8",
    )
    (root / "GOLDEN_JOURNEY_RELEASE_GATES.yaml").write_text(
        yaml.safe_dump(
            {
                "product": "chummer",
                "journey_gates": [
                    {
                        "id": "desktop_release_truth",
                        "title": "Desktop release truth",
                        "user_promise": "Desktop release truth is boringly proven.",
                        "canonical_journeys": ["journeys/install-and-update.md"],
                        "owner_repos": ["chummer6-ui", "fleet"],
                        "scorecard_refs": {},
                        "fleet_gate": {
                            "required_artifacts": ["status_plane", "progress_report"],
                            "minimum_history_snapshots": 2,
                            "target_history_snapshots": 4,
                            "required_project_posture": [
                                {
                                    "project_id": "ui",
                                    "minimum_stage": "pre_repo_local_complete",
                                    "target_stage": "publicly_promoted",
                                    "minimum_deployment_posture": "protected_preview",
                                    "target_deployment_posture": "public",
                                }
                            ],
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (root / "STATUS_PLANE.generated.yaml").write_text(
        yaml.safe_dump(
            {
                "contract_name": "fleet.status_plane",
                "generated_at": now_text,
                "projects": [
                    {
                        "id": "ui",
                        "readiness_stage": ui_stage,
                        "deployment_access_posture": ui_posture,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (root / "PROGRESS_REPORT.generated.json").write_text(
        json.dumps({"generated_at": now_text, "history_snapshot_count": 4}),
        encoding="utf-8",
    )
    (root / "PROGRESS_HISTORY.generated.json").write_text(
        json.dumps({"generated_at": now_text, "snapshot_count": 4}),
        encoding="utf-8",
    )
    (root / "SUPPORT_CASE_PACKETS.generated.json").write_text(
        json.dumps(
            {
                "generated_at": now_text,
                "summary": {
                    "closure_waiting_on_release_truth": 0,
                    "needs_human_response": 0,
                },
            }
        ),
        encoding="utf-8",
    )
    (root / "WEEKLY_PRODUCT_PULSE.generated.json").write_text(
        json.dumps(
            {
                "contract_name": "chummer.weekly_product_pulse",
                "contract_version": 3,
                "generated_at": now_text,
                "as_of": now_text[:10],
                "active_wave": "Next 20 Big Wins After Post-Audit Closeout",
                "active_wave_status": active_wave_status,
                "release_health": {
                    "state": release_health_state,
                    "reason": "green",
                },
                "flagship_readiness": {
                    "state": "ready",
                    "reason": "fixture",
                },
                "rule_environment_trust": {
                    "state": "ready",
                    "reason": "fixture",
                },
                "journey_gate_health": {
                    "state": journey_gate_health_state,
                    "reason": "steady",
                    "blocked_count": 0,
                    "warning_count": 0,
                },
                "edition_authorship_and_import_confidence": {
                    "state": "monitor",
                    "reason": "fixture",
                },
                "top_support_or_feedback_clusters": [],
                "oldest_blocker_days": oldest_blocker_days,
                "design_drift_count": design_drift_count,
                "public_promise_drift_count": public_promise_drift_count,
                "governor_decisions": [
                    {
                        "decision_id": "fixture-focus",
                        "action": "focus_shift",
                        "reason": "fixture",
                        "cited_signals": [
                            "overall_progress_percent=100",
                        ],
                    },
                    {
                        "decision_id": "fixture-launch",
                        "action": "freeze_launch",
                        "reason": "fixture",
                        "cited_signals": [
                            "journey_gate_state=ready",
                            "journey_gate_blocked_count=0",
                            "local_release_proof_status=passed",
                            "provider_canary_status=Canary green on all active lanes",
                            "closure_health_state=clear",
                        ],
                    },
                ],
                "next_checkpoint_question": "What remains?",
                "snapshot": {
                    "release_health": {
                        "state": release_health_state,
                        "reason": "green",
                    },
                    "flagship_readiness": {
                        "state": "ready",
                        "reason": "fixture",
                    },
                    "rule_environment_trust": {
                        "state": "ready",
                        "reason": "fixture",
                    },
                    "journey_gate_health": {
                        "state": journey_gate_health_state,
                        "reason": "steady",
                        "blocked_count": 0,
                        "warning_count": 0,
                    },
                    "edition_authorship_and_import_confidence": {
                        "state": "monitor",
                        "reason": "fixture",
                    },
                    "top_support_or_feedback_clusters": [],
                    "oldest_blocker_days": oldest_blocker_days,
                    "design_drift_count": design_drift_count,
                    "public_promise_drift_count": public_promise_drift_count,
                    "governor_decisions": [
                        {
                            "decision_id": "fixture-focus",
                            "action": "focus_shift",
                            "reason": "fixture",
                            "cited_signals": [
                                "overall_progress_percent=100",
                            ],
                        },
                        {
                            "decision_id": "fixture-launch",
                            "action": "freeze_launch",
                            "reason": "fixture",
                            "cited_signals": [
                                "journey_gate_state=ready",
                                "journey_gate_blocked_count=0",
                                "local_release_proof_status=passed",
                                "provider_canary_status=Canary green on all active lanes",
                                "closure_health_state=clear",
                            ],
                        },
                    ],
                    "next_checkpoint_question": "What remains?",
                },
                "supporting_signals": {
                    "launch_readiness": "fixture",
                    "provider_route_stewardship": {
                        "canary_status": "Canary green on all active lanes",
                        "next_decision": "fixture",
                    },
                    "automation_alignment": {
                        "state": automation_alignment_state,
                        "active_wave_registry": "products/chummer/NEXT_12_BIGGEST_WINS_REGISTRY.yaml",
                        "active_open_milestone_ids": [10, 11, 12, 15],
                        "handoff_frontier_milestone_ids": [10, 11, 12, 15],
                        "out_of_program_frontier_milestone_ids": [],
                        "summary": "fixture",
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    if write_linux_desktop_exit_gate:
        linux_gate_generated_at = linux_desktop_exit_gate_generated_at or now_text
        linux_gate_test_passed = max(
            0,
            linux_desktop_exit_gate_test_total
            - linux_desktop_exit_gate_test_failed
            - linux_desktop_exit_gate_test_skipped,
        )
        output_base_root = root / ".codex-studio" / "out" / "linux-desktop-exit-gate"
        run_root = output_base_root / "run.fixture"
        publish_dir = run_root / "publish" / "avalonia-linux-x64"
        dist_dir = run_root / "dist"
        test_results_dir = run_root / "test-results"
        archive_smoke_dir = run_root / "startup-smoke-archive"
        installer_smoke_dir = run_root / "startup-smoke-installer"
        publish_dir.mkdir(parents=True, exist_ok=True)
        dist_dir.mkdir(parents=True, exist_ok=True)
        test_results_dir.mkdir(parents=True, exist_ok=True)
        archive_smoke_dir.mkdir(parents=True, exist_ok=True)
        installer_smoke_dir.mkdir(parents=True, exist_ok=True)
        binary_path = publish_dir / linux_desktop_exit_gate_launch_target
        archive_path = dist_dir / "chummer-avalonia-linux-x64.tar.gz"
        installer_path = dist_dir / "chummer-avalonia-linux-x64-installer.deb"
        snapshot_root = root / ".linux-desktop-exit-gate-source.fixture"
        snapshot_root.mkdir(parents=True, exist_ok=True)
        binary_path.write_text("binary\n", encoding="utf-8")
        archive_path.write_text("archive\n", encoding="utf-8")
        installer_path.write_text("installer\n", encoding="utf-8")
        os.chmod(binary_path, 0o755)
        archive_digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
        installer_digest = hashlib.sha256(installer_path.read_bytes()).hexdigest()
        installed_launch_sha = hashlib.sha256(binary_path.read_bytes()).hexdigest()
        wrapper_content = (
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            'exec "/opt/chummer6/avalonia-linux-x64/Chummer.Avalonia" "$@"\n'
        )
        desktop_entry_content = (
            "[Desktop Entry]\n"
            "Type=Application\n"
            "Name=Chummer\n"
            "Exec=/usr/bin/chummer6-avalonia\n"
            "Icon=/opt/chummer6/avalonia-linux-x64/chummer-icon.png\n"
            "Terminal=false\n"
            "Categories=Game;\n"
            "StartupNotify=true\n"
        )
        receipt_payload = {
            "headId": linux_desktop_exit_gate_app_key,
            "platform": "linux",
            "arch": "x64",
            "readyCheckpoint": "pre_ui_event_loop",
            "channelId": "local-hard-gate",
            "version": "local-hard-gate",
            "processPath": str(binary_path),
        }
        installer_receipt_payload = dict(receipt_payload)
        installer_receipt_payload["artifactDigest"] = f"sha256:{installer_digest}"
        archive_receipt_payload = dict(receipt_payload)
        archive_receipt_payload["artifactDigest"] = f"sha256:{archive_digest}"
        installer_receipt_path = installer_smoke_dir / "startup-smoke-avalonia-linux-x64.receipt.json"
        archive_receipt_path = archive_smoke_dir / "startup-smoke-avalonia-linux-x64.receipt.json"
        install_verification_path = installer_smoke_dir / "install-verification-avalonia-linux-x64.json"
        dpkg_log_path = installer_smoke_dir / "dpkg-avalonia-linux-x64.log"
        installed_launch_capture_path = installer_smoke_dir / "installed-launch-avalonia-linux-x64.bin"
        wrapper_capture_path = installer_smoke_dir / "installed-wrapper-avalonia-linux-x64.sh"
        desktop_entry_capture_path = installer_smoke_dir / "installed-desktop-entry-avalonia-linux-x64.desktop"
        installer_receipt_payload["artifactInstallMode"] = "dpkg_rootless_install"
        installer_receipt_payload["artifactInstallVerificationPath"] = str(install_verification_path)
        installer_receipt_path.write_text(json.dumps(installer_receipt_payload), encoding="utf-8")
        archive_receipt_path.write_text(json.dumps(archive_receipt_payload), encoding="utf-8")
        installed_launch_capture_path.write_bytes(binary_path.read_bytes())
        wrapper_capture_path.write_text(wrapper_content, encoding="utf-8")
        desktop_entry_capture_path.write_text(desktop_entry_content, encoding="utf-8")
        dpkg_log_path.write_text(
            "\n".join(
                [
                    "2026-03-31 11:33:24 install chummer6-avalonia:amd64 <none> 0~local-hard-gate",
                    "2026-03-31 11:33:26 status installed chummer6-avalonia:amd64 0~local-hard-gate",
                    "2026-03-31 11:33:26 remove chummer6-avalonia:amd64 0~local-hard-gate <none>",
                    "2026-03-31 11:33:26 status not-installed chummer6-avalonia:amd64 <none>",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        install_verification_path.write_text(
            json.dumps(
                {
                    "mode": "dpkg_rootless_install",
                    "packageName": "chummer6-avalonia",
                    "packageArch": "amd64",
                    "installRoot": str(root / "tmp-install-root"),
                    "dpkgAdminDir": str(root / "tmp-install-root" / "var" / "lib" / "dpkg"),
                    "dpkgLogPath": str(dpkg_log_path),
                    "installedLaunchPath": str(root / "tmp-install-root" / "opt" / "chummer6" / "avalonia-linux-x64" / linux_desktop_exit_gate_launch_target),
                    "installedLaunchCapturePath": str(installed_launch_capture_path),
                    "installedLaunchPathSha256": installed_launch_sha,
                    "wrapperPath": str(root / "tmp-install-root" / "usr" / "bin" / "chummer6-avalonia"),
                    "wrapperCapturePath": str(wrapper_capture_path),
                    "wrapperSha256": hashlib.sha256(wrapper_content.encode("utf-8")).hexdigest(),
                    "wrapperContent": wrapper_content,
                    "desktopEntryPath": str(root / "tmp-install-root" / "usr" / "share" / "applications" / "chummer6-avalonia.desktop"),
                    "desktopEntryCapturePath": str(desktop_entry_capture_path),
                    "desktopEntrySha256": hashlib.sha256(desktop_entry_content.encode("utf-8")).hexdigest(),
                    "desktopEntryContent": desktop_entry_content,
                    "statusAfterInstall": "install ok installed",
                    "statusAfterPurge": "not-installed",
                    "installedLaunchPathExistsAfterInstall": True,
                    "wrapperExistsAfterInstall": True,
                    "desktopEntryExistsAfterInstall": True,
                    "installedLaunchPathExistsAfterPurge": False,
                    "wrapperExistsAfterPurge": False,
                    "desktopEntryExistsAfterPurge": False,
                }
            ),
            encoding="utf-8",
        )
        test_code_base = (
            root
            / "Chummer.Desktop.Runtime.Tests"
            / "bin"
            / "Release"
            / "net10.0"
            / linux_desktop_exit_gate_test_assembly_name
        )
        (test_results_dir / "desktop-runtime-tests.trx").write_text(
            (
                "<TestRun>"
                "<Results>"
                "<UnitTestResult executionId=\"execution-1\" testId=\"test-1\" testName=\"DesktopSmoke\" outcome=\"Passed\" />"
                "</Results>"
                "<TestDefinitions>"
                f"<UnitTest name=\"DesktopSmoke\" storage=\"{test_code_base}\">"
                "<Execution id=\"execution-1\" />"
                f"<TestMethod codeBase=\"{test_code_base}\" className=\"Chummer.Tests.DesktopSmoke\" name=\"DesktopSmoke\" />"
                "</UnitTest>"
                "</TestDefinitions>"
                "<ResultSummary>"
                f"<Counters total=\"{linux_desktop_exit_gate_test_total}\" "
                f"passed=\"{linux_gate_test_passed}\" "
                f"failed=\"{linux_desktop_exit_gate_test_failed}\" "
                f"skipped=\"{linux_desktop_exit_gate_test_skipped}\" />"
                "</ResultSummary>"
                "</TestRun>"
            ),
            encoding="utf-8",
        )
        worktree_sha, worktree_entry_count = _worktree_fingerprint(
            root,
            exclude_paths=(output_base_root, root / "UI_LINUX_DESKTOP_EXIT_GATE.generated.json"),
        )
        (root / "UI_LINUX_DESKTOP_EXIT_GATE.generated.json").write_text(
            json.dumps(
                {
                    "contract_name": "chummer6-ui.linux_desktop_exit_gate",
                    "generated_at": linux_gate_generated_at,
                    "status": linux_desktop_exit_gate_status,
                    "reason": (
                        "linux desktop build, startup smoke, and unit tests passed"
                        if linux_desktop_exit_gate_status == "passed"
                        else "stage unit_tests failed"
                    ),
                    "stage": "complete" if linux_desktop_exit_gate_status == "passed" else "unit_tests",
                    "run_root": str(run_root),
                    "head": {
                        "app_key": linux_desktop_exit_gate_app_key,
                        "project_path": "Chummer.Avalonia/Chummer.Avalonia.csproj",
                        "launch_target": linux_desktop_exit_gate_launch_target,
                        "platform": "linux",
                        "rid": "linux-x64",
                        "version": "local-hard-gate",
                        "channel": "local-hard-gate",
                        "ready_checkpoint": "pre_ui_event_loop",
                    },
                    "build": {
                        "output_base_root": str(output_base_root),
                        "publish_dir": str(publish_dir),
                        "dist_dir": str(dist_dir),
                        "binary_path": str(binary_path),
                        "binary_exists": linux_desktop_exit_gate_status == "passed",
                        "binary_sha256": hashlib.sha256(binary_path.read_bytes()).hexdigest(),
                        "binary_bytes": binary_path.stat().st_size,
                        "binary_executable": True,
                        "publish_exists": True,
                        "self_contained": True,
                        "single_file": True,
                        "primary_package_kind": "deb",
                        "fallback_package_kind": "archive",
                        "archive_path": str(archive_path),
                        "archive_exists": linux_desktop_exit_gate_status == "passed",
                        "archive_sha256": archive_digest,
                        "archive_bytes": archive_path.stat().st_size,
                        "installer_path": str(installer_path),
                        "installer_exists": linux_desktop_exit_gate_status == "passed",
                        "installer_sha256": installer_digest,
                        "installer_bytes": installer_path.stat().st_size,
                    },
                    "startup_smoke": {
                        "primary": {
                            "package_kind": "deb",
                            "artifact_path": str(installer_path),
                            "receipt_path": str(installer_receipt_path),
                            "status": linux_desktop_exit_gate_status,
                            "receipt": {"status": linux_desktop_exit_gate_status},
                        },
                        "fallback": {
                            "package_kind": "archive",
                            "artifact_path": str(archive_path),
                            "receipt_path": str(archive_receipt_path),
                            "status": linux_desktop_exit_gate_status,
                            "receipt": {"status": linux_desktop_exit_gate_status},
                        },
                    },
                    "unit_tests": {
                        "project_path": linux_desktop_exit_gate_test_project_path,
                        "framework": "net10.0",
                        "results_directory": str(test_results_dir),
                        "trx_path": str(test_results_dir / "desktop-runtime-tests.trx"),
                        "assembly_name": linux_desktop_exit_gate_test_assembly_name,
                        "status": "passed" if linux_desktop_exit_gate_status == "passed" else "failed",
                        "summary": {
                            "total": linux_desktop_exit_gate_test_total,
                            "passed": linux_gate_test_passed,
                            "failed": linux_desktop_exit_gate_test_failed,
                            "skipped": linux_desktop_exit_gate_test_skipped,
                        },
                    },
                    "source_snapshot": {
                        "mode": "filesystem_copy",
                        "repo_root": str(root),
                        "snapshot_root": str(snapshot_root),
                        "entry_count": worktree_entry_count,
                        "worktree_sha256": worktree_sha,
                        "finish_entry_count": worktree_entry_count,
                        "finish_worktree_sha256": worktree_sha,
                        "identity_stable": True,
                    },
                    "git": {
                        "repo_root": str(root),
                        "available": False,
                        "head": "",
                        "tracked_diff_sha256": "",
                        "tracked_diff_line_count": 0,
                        "start": {},
                        "finish": {},
                        "identity_stable": False,
                    },
                }
            ),
            encoding="utf-8",
        )
        if (root / ".git").exists():
            head = subprocess.run(
                ["git", "-C", str(root), "rev-parse", "HEAD"],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            diff_sha, entry_count = _worktree_fingerprint(
                root,
                exclude_paths=(output_base_root, root / "UI_LINUX_DESKTOP_EXIT_GATE.generated.json"),
            )
            payload = json.loads((root / "UI_LINUX_DESKTOP_EXIT_GATE.generated.json").read_text(encoding="utf-8"))
            payload["git"] = {
                "repo_root": str(root),
                "available": True,
                "head": head,
                "tracked_diff_sha256": diff_sha,
                "tracked_diff_line_count": entry_count,
                "start": {
                    "repo_root": str(root),
                    "available": True,
                    "head": head,
                    "tracked_diff_sha256": diff_sha,
                    "tracked_diff_line_count": entry_count,
                },
                "finish": {
                    "repo_root": str(root),
                    "available": True,
                    "head": head,
                    "tracked_diff_sha256": diff_sha,
                    "tracked_diff_line_count": entry_count,
                },
                "identity_stable": True,
            }
            (root / "UI_LINUX_DESKTOP_EXIT_GATE.generated.json").write_text(
                json.dumps(payload),
                encoding="utf-8",
            )


def _write_flagship_product_readiness(
    root: Path,
    *,
    status: str = "pass",
    generated_at: str | None = None,
    ready_keys: tuple[str, ...] = (
        "desktop_client",
        "rules_engine_and_import",
        "hub_and_registry",
        "mobile_play_shell",
        "ui_kit_and_flagship_polish",
        "media_artifacts",
        "horizons_and_public_surface",
        "fleet_and_operator_loop",
    ),
    warning_keys: tuple[str, ...] = (),
    unresolved_parity_families: tuple[dict[str, object], ...] = (),
    coverage_details: dict[str, object] | None = None,
    completion_audit: dict[str, object] | None = None,
    external_host_proof: dict[str, object] | None = None,
) -> None:
    now_text = generated_at or dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    coverage = {key: ("ready" if key in ready_keys else "warning" if key in warning_keys else "missing") for key in (
        "desktop_client",
        "rules_engine_and_import",
        "hub_and_registry",
        "mobile_play_shell",
        "ui_kit_and_flagship_polish",
        "media_artifacts",
        "horizons_and_public_surface",
        "fleet_and_operator_loop",
    )}
    (root / "FLAGSHIP_PRODUCT_READINESS.generated.json").write_text(
        json.dumps(
            {
                "contract_name": "fleet.flagship_product_readiness",
                "generated_at": now_text,
                "status": status,
                "warning_keys": list(warning_keys),
                "missing_keys": [
                    key
                    for key, value in coverage.items()
                    if str(value).strip().lower() == "missing"
                ],
                "scoped_warning_coverage_keys": list(warning_keys),
                "scoped_missing_coverage_keys": [
                    key
                    for key, value in coverage.items()
                    if str(value).strip().lower() == "missing"
                ],
                "coverage": coverage,
                "coverage_details": dict(coverage_details or {}),
                "completion_audit": dict(completion_audit or {}),
                "external_host_proof": dict(external_host_proof or {}),
                "parity_registry": {
                    "excluded_scope": ["plugin-framework"],
                    "unresolved_families": list(unresolved_parity_families),
                },
            }
        ),
        encoding="utf-8",
    )


def test_refresh_flagship_product_readiness_artifact_uses_workspace_sibling_generated_inputs(monkeypatch) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_registry(root / "registry.yaml")
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("Flagship work remains.\n", encoding="utf-8")
        (root / ".codex-design" / "product").mkdir(parents=True, exist_ok=True)
        (root / ".codex-design" / "product" / "FLAGSHIP_RELEASE_ACCEPTANCE.yaml").write_text("product: chummer\n", encoding="utf-8")
        args = _args(root)
        calls: dict[str, str] = {}
        monkeypatch.setattr(module, "DEFAULT_WORKSPACE_ROOT", root)

        def fake_materialize_flagship_product_readiness(**kwargs):
            for key, value in kwargs.items():
                calls[key] = str(value)
            return {"status": "fail"}

        monkeypatch.setattr(module, "materialize_flagship_product_readiness", fake_materialize_flagship_product_readiness)

        payload = module._refresh_flagship_product_readiness_artifact(args)

        assert payload == {"status": "fail"}
        assert calls["out_path"] == str(root / "FLAGSHIP_PRODUCT_READINESS.generated.json")
        assert calls["journey_gates_path"] == str(root / "JOURNEY_GATES.generated.json")
        assert calls["acceptance_path"] == str(root / ".codex-design" / "product" / "FLAGSHIP_RELEASE_ACCEPTANCE.yaml")
        assert calls["feedback_loop_gate_path"] == str(root / ".codex-design" / "product" / "FEEDBACK_LOOP_RELEASE_GATE.yaml")
        assert calls["mirror_path"] == str(root / "state" / "artifacts" / "FLAGSHIP_PRODUCT_READINESS.generated.json")
        ui_published_root = module.PREFERRED_UI_REPO_ROOT / ".codex-studio" / "published"
        assert calls["ui_windows_exit_gate_path"] == str(ui_published_root / "UI_WINDOWS_DESKTOP_EXIT_GATE.generated.json")
        assert calls["ui_workflow_parity_proof_path"] == str(ui_published_root / "CHUMMER5A_DESKTOP_WORKFLOW_PARITY.generated.json")
        assert calls["ui_executable_exit_gate_path"] == str(ui_published_root / "DESKTOP_EXECUTABLE_EXIT_GATE.generated.json")
        assert calls["ui_workflow_execution_gate_path"] == str(ui_published_root / "DESKTOP_WORKFLOW_EXECUTION_GATE.generated.json")
        assert calls["ui_visual_familiarity_exit_gate_path"] == str(ui_published_root / "DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.generated.json")
        assert calls["ui_localization_release_gate_path"] == str(ui_published_root / "UI_LOCALIZATION_RELEASE_GATE.generated.json")
        assert calls["sr4_workflow_parity_proof_path"] == str(ui_published_root / "SR4_DESKTOP_WORKFLOW_PARITY.generated.json")
        assert calls["sr6_workflow_parity_proof_path"] == str(ui_published_root / "SR6_DESKTOP_WORKFLOW_PARITY.generated.json")
        assert calls["sr4_sr6_frontier_receipt_path"] == str(ui_published_root / "SR4_SR6_DESKTOP_PARITY_FRONTIER.generated.json")


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
        assert str(root / "NEXT_SESSION_HANDOFF.md") not in context["prompt"]


def test_parse_frontier_ids_from_handoff_prefers_explicit_frontier_line() -> None:
    module = _load_module()

    text = "\n".join(
        [
            "Status and metrics: 1, 2, 3.",
            "Current active frontier from design plus handoff: 1, 3, 4, 5, 2",
            "W3 milestone `15` plus W4 milestones `18`, `19`, and `20` remain active.",
        ]
    )

    assert module._parse_frontier_ids_from_handoff(text) == [1, 3, 4, 5, 2]


def test_parse_frontier_ids_from_handoff_accepts_runtime_handoff_frontier_ids_line() -> None:
    module = _load_module()

    text = "\n".join(
        [
            "# Shard Runtime Handoff",
            "Generated at: 2026-04-14T22:40:13Z",
            "Frontier ids: 3109832007, 3449507998",
        ]
    )

    assert module._parse_frontier_ids_from_handoff(text) == [3109832007, 3449507998]


def test_parse_frontier_ids_from_handoff_prefers_latest_entry_at_top() -> None:
    module = _load_module()

    text = "\n".join(
        [
            "Frontier milestone ids to prioritize first: 1, 2, 4, 5, 3",
            "",
            "## 2026-04-02",
            "Frontier milestone ids to prioritize first: 1, 2, 3, 4, 6",
        ]
    )

    assert module._parse_frontier_ids_from_handoff(text) == [1, 2, 4, 5, 3]


def test_parse_frontier_ids_from_handoff_reads_multiline_frontier_block() -> None:
    module = _load_module()

    text = "\n".join(
        [
            "Current active frontier from design plus handoff:",
            "- 1 [W1] Gold install lane",
            "- 3 [W1] Packaged-binary desktop proof",
            "- 4 [W2] Campaign workspace v4",
            "- 5 [W2] GM operations lane",
            "- 2 [W1] Legacy-familiar flagship workbench",
            "",
            "Older note: Frontier milestone ids to prioritize first: 1, 2, 3, 4, 6",
        ]
    )

    assert module._parse_frontier_ids_from_handoff(text) == [1, 3, 4, 5, 2]


def test_parse_frontier_ids_from_handoff_ignores_non_frontier_number_noise() -> None:
    module = _load_module()

    text = "\n".join(
        [
            "Verification summary: 8 coverage keys are ready on 3 shards.",
            "No explicit frontier line is present in this note.",
        ]
    )

    assert module._parse_frontier_ids_from_handoff(text) == []


def test_derive_context_preserves_explicit_handoff_frontier_over_focus_profiles() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "registry.yaml").write_text(
            yaml.safe_dump(
                {
                    "waves": [{"id": "W1"}, {"id": "W2"}],
                    "milestones": [
                        {
                            "id": 1,
                            "title": "Gold install lane",
                            "wave": "W1",
                            "status": "in_progress",
                            "owners": ["chummer6-ui", "fleet"],
                            "exit_criteria": ["Install lane works."],
                        },
                        {
                            "id": 2,
                            "title": "Legacy-familiar flagship workbench",
                            "wave": "W1",
                            "status": "in_progress",
                            "owners": ["chummer6-ui", "chummer6-core"],
                            "exit_criteria": ["Workbench posture is familiar."],
                        },
                        {
                            "id": 3,
                            "title": "Packaged-binary desktop proof",
                            "wave": "W1",
                            "status": "in_progress",
                            "owners": ["fleet", "chummer6-ui"],
                            "exit_criteria": ["Packaged proof exists."],
                        },
                        {
                            "id": 4,
                            "title": "Campaign workspace v4",
                            "wave": "W2",
                            "status": "in_progress",
                            "owners": ["chummer6-hub", "chummer6-core"],
                            "exit_criteria": ["Campaign lane is coherent."],
                        },
                        {
                            "id": 5,
                            "title": "GM operations lane",
                            "wave": "W2",
                            "status": "in_progress",
                            "owners": ["chummer6-hub", "chummer6-core"],
                            "exit_criteria": ["GM operations are first-class."],
                        },
                        {
                            "id": 6,
                            "title": "Offline and mobile continuity",
                            "wave": "W2",
                            "status": "in_progress",
                            "owners": ["chummer6-mobile", "chummer6-hub"],
                            "exit_criteria": ["Offline continuity works."],
                        },
                    ],
                }
            ),
            encoding="utf-8",
        )
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text(
            "Current active frontier from design plus handoff:\n"
            "- 1 [W1] Gold install lane\n"
            "- 2 [W1] Legacy-familiar flagship workbench\n"
            "- 4 [W2] Campaign workspace v4\n"
            "- 5 [W2] GM operations lane\n"
            "- 3 [W1] Packaged-binary desktop proof\n"
            "Frontier milestone ids to prioritize first: 1, 2, 4, 5, 3\n",
            encoding="utf-8",
        )
        args = _args(root)
        args.focus_profile = ["desktop_client"]

        context = module.derive_context(args)

        assert [item.id for item in context["frontier"]] == [1, 2, 4, 5, 3]


def test_derive_context_uses_multiline_handoff_frontier_without_priority_line() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "registry.yaml").write_text(
            yaml.safe_dump(
                {
                    "waves": [{"id": "W1"}, {"id": "W2"}],
                    "milestones": [
                        {
                            "id": 1,
                            "title": "Gold install lane",
                            "wave": "W1",
                            "status": "in_progress",
                            "owners": ["chummer6-ui", "fleet"],
                            "exit_criteria": ["Install lane works."],
                        },
                        {
                            "id": 2,
                            "title": "Legacy-familiar flagship workbench",
                            "wave": "W1",
                            "status": "in_progress",
                            "owners": ["chummer6-ui", "chummer6-core"],
                            "exit_criteria": ["Workbench posture is familiar."],
                        },
                        {
                            "id": 3,
                            "title": "Packaged-binary desktop proof",
                            "wave": "W1",
                            "status": "in_progress",
                            "owners": ["fleet", "chummer6-ui"],
                            "exit_criteria": ["Packaged proof exists."],
                        },
                        {
                            "id": 4,
                            "title": "Campaign workspace v4",
                            "wave": "W2",
                            "status": "in_progress",
                            "owners": ["chummer6-hub", "chummer6-core"],
                            "exit_criteria": ["Campaign lane is coherent."],
                        },
                        {
                            "id": 5,
                            "title": "GM operations lane",
                            "wave": "W2",
                            "status": "in_progress",
                            "owners": ["chummer6-hub", "chummer6-core"],
                            "exit_criteria": ["GM operations are first-class."],
                        },
                    ],
                }
            ),
            encoding="utf-8",
        )
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text(
            "Current active frontier from design plus handoff:\n"
            "- 1 [W1] Gold install lane\n"
            "- 3 [W1] Packaged-binary desktop proof\n"
            "- 4 [W2] Campaign workspace v4\n"
            "- 5 [W2] GM operations lane\n"
            "- 2 [W1] Legacy-familiar flagship workbench\n",
            encoding="utf-8",
        )
        args = _args(root)
        args.focus_profile = ["desktop_client"]

        context = module.derive_context(args)

        assert [item.id for item in context["frontier"]] == [1, 3, 4, 5, 2]


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


def test_parse_final_message_sections_reads_json_wrapped_closeout_text() -> None:
    module = _load_module()
    parsed = module._parse_final_message_sections(
        "\n".join(
            [
                "I am going to fix the blocker.",
                '{"questions":[{"header":"x"}]}',
                '{"decision":"final","text":"What shipped: alpha\\nWhat remains: beta\\nExact blocker: none"}',
            ]
        )
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


def test_assess_worker_result_accepts_json_wrapped_structured_closeout() -> None:
    module = _load_module()

    accepted, reason = module._assess_worker_result(
        0,
        "\n".join(
            [
                "I am going to fix the blocker.",
                '{"decision":"final","text":"What shipped: alpha\\nWhat remains: beta\\nExact blocker: none"}',
            ]
        ),
    )

    assert accepted is True
    assert reason == ""


def test_assess_worker_result_rejects_unpublished_remote_work() -> None:
    module = _load_module()

    accepted, reason = module._assess_worker_result(
        0,
        "What shipped: `/docker/fleet/NEXT_SESSION_HANDOFF.md` refreshed locally with both slices "
        "(local Fleet commits `fbc5b1d`, `370495d`).\n\n"
        "What remains: Fleet handoff commits are not yet pushed to remote.\n\n"
        "Exact blocker: none\n",
    )

    assert accepted is False
    assert "not yet pushed to remote" in reason


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

        _patch_launch_worker_fake_run(monkeypatch, module, fake_run)

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

        _patch_launch_worker_fake_run(monkeypatch, module, fake_run)

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

        _patch_launch_worker_fake_run(monkeypatch, module, fake_run)

        run = module.launch_worker(args, context, root / "state")

        assert run.worker_exit_code == 0
        assert run.accepted is True
        assert run.selected_account_alias == "acct-archon-a"
        assert run.attempted_accounts == ["acct-tibor-a", "acct-tibor-a", "acct-archon-a"]
        assert run.attempted_models == ["gpt-5.3-codex-spark", "ea-coder-hard", "gpt-5.3-codex-spark"]
        account_runtime = json.loads((root / "state" / "account_runtime.json").read_text(encoding="utf-8"))
        assert len(account_runtime["sources"]) == 2
        assert len(calls) == 3


def test_launch_worker_falls_through_from_spark_usage_limit_to_same_account_gpt54(monkeypatch) -> None:
    module = _load_module()
    monkeypatch.setattr(module, "_RUNTIME_ENV_CANDIDATES", ())
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_registry(root / "registry.yaml")
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("W2 milestone `21` remains active.\n", encoding="utf-8")
        auth_path = root / "acct-chatgpt-core.auth.json"
        auth_path.write_text('{"access_token":"shared"}\n', encoding="utf-8")
        (root / "accounts.yaml").write_text(
            yaml.safe_dump(
                {
                    "account_policy": {
                        "protected_owner_ids": ["tibor.girschele"],
                    },
                    "accounts": {
                        "acct-ea-core": {
                            "auth_kind": "ea",
                            "api_key_env": "EA_KEY",
                            "allowed_models": ["ea-coder-hard-batch", "ea-coder-hard"],
                            "health_state": "ready",
                            "owner_id": "tibor.girschele",
                            "lane": "core",
                        },
                        "acct-chatgpt-core": {
                            "auth_kind": "chatgpt_auth_json",
                            "auth_json_file": str(auth_path),
                            "owner_id": "tibor.girschele",
                            "health_state": "ready",
                            "spark_enabled": True,
                            "allowed_models": ["gpt-5.3-codex-spark", "gpt-5.4"],
                        },
                    },
                }
            ),
            encoding="utf-8",
        )
        state_root = root / "state"
        state_root.mkdir(parents=True, exist_ok=True)
        (state_root / "history.jsonl").write_text(
            "".join(
                json.dumps(
                    {
                        "run_id": f"run-{idx}",
                        "accepted": False,
                        "blocker": "Error: worker_status_helper_loop:repeated_blocked_status_polling",
                    }
                )
                + "\n"
                for idx in range(2)
            ),
            encoding="utf-8",
        )
        args = _args(root)
        args.worker_bin = "codexea"
        args.worker_lane = "core"
        args.worker_model = "ea-coder-hard-batch"
        context = module.derive_context(args)
        monkeypatch.setenv("EA_KEY", "test-key")
        monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_OPENAI_ESCAPE_ACCOUNT_ALIASES", "acct-chatgpt-core")
        monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_OPENAI_ESCAPE_MODELS", "gpt-5.3-codex-spark,gpt-5.4")

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
                    stderr="ERROR: You've hit your usage limit for GPT-5.3-Codex-Spark. Switch to another model now.",
                )
            message_path.write_text(
                "What shipped: gpt-5.4 fallback landed on the same account\nWhat remains: none\nExact blocker: none\n",
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        _patch_launch_worker_fake_run(monkeypatch, module, fake_run)

        run = module.launch_worker(args, context, state_root)

        assert run.worker_exit_code == 0
        assert run.accepted is True
        assert run.selected_account_alias == "acct-chatgpt-core"
        assert run.attempted_accounts == ["acct-chatgpt-core"]
        assert run.attempted_models == ["gpt-5.4"]
        account_runtime = json.loads((state_root / "account_runtime.json").read_text(encoding="utf-8"))
        source_key = f"chatgpt_auth_json:{auth_path}"
        assert account_runtime["sources"][source_key].get("backoff_until", "") == ""
        assert account_runtime["sources"][source_key].get("spark_backoff_until", "") == ""
        assert len(calls) == 1


def test_launch_worker_can_use_direct_worker_lane_without_account_rotation(monkeypatch) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_registry(root / "registry.yaml")
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("W2 milestone `21` remains active.\n", encoding="utf-8")
        (root / "runtime.env").write_text(
            "\n".join(
                [
                    "CHUMMER_DESIGN_SUPERVISOR_STREAM_IDLE_TIMEOUT_MS=900000",
                    "CHUMMER_DESIGN_SUPERVISOR_STREAM_MAX_RETRIES=8",
                    "CHUMMER_DESIGN_SUPERVISOR_CORE_RESPONSES_PROFILE=core_batch",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
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

        _patch_launch_worker_fake_run(monkeypatch, module, fake_run)

        run = module.launch_worker(args, context, root / "state")

        assert run.worker_exit_code == 0
        assert run.accepted is True
        assert run.selected_account_alias == "lane:core"
        assert run.attempted_accounts == ["lane:core"]
        assert calls[0][:3] == ["codexea", "core", "exec"]


def test_prepare_direct_worker_environment_applies_workspace_stream_budget_for_core_codexea() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "runtime.env").write_text(
            "\n".join(
                [
                    "CHUMMER_DESIGN_SUPERVISOR_STREAM_IDLE_TIMEOUT_MS=900000",
                    "CHUMMER_DESIGN_SUPERVISOR_STREAM_MAX_RETRIES=8",
                    "CHUMMER_DESIGN_SUPERVISOR_CORE_RESPONSES_PROFILE=core_batch",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        env = module._prepare_direct_worker_environment(
            root / "state",
            "core",
            workspace_root=root,
            worker_bin="codexea",
        )

        assert env.get("CODEXEA_STREAM_IDLE_TIMEOUT_MS") == "900000"
        assert env.get("CODEXEA_STREAM_MAX_RETRIES") == "8"
        assert env.get("CODEXEA_CORE_RESPONSES_PROFILE") == "core_batch"


def test_prepare_direct_worker_environment_caps_stream_budget_to_explicit_model_output_stall() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "runtime.env").write_text(
            "\n".join(
                [
                    "CHUMMER_DESIGN_SUPERVISOR_STREAM_IDLE_TIMEOUT_MS=1200000",
                    "CHUMMER_DESIGN_SUPERVISOR_STREAM_MAX_RETRIES=12",
                    "CHUMMER_DESIGN_SUPERVISOR_MODEL_OUTPUT_STALL_SECONDS=60",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        env = module._prepare_direct_worker_environment(
            root / "state",
            "core",
            workspace_root=root,
            worker_bin="codexea",
        )

        assert env.get("CODEXEA_STREAM_IDLE_TIMEOUT_MS") == "60000"
        assert env.get("CODEXEA_STREAM_MAX_RETRIES") == "0"


def test_prepare_direct_worker_environment_preserves_host_git_and_gh_auth(monkeypatch) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        host_home = root / "host-home"
        gh_dir = host_home / ".config" / "gh"
        gh_dir.mkdir(parents=True, exist_ok=True)
        (host_home / ".gitconfig").write_text("[user]\n\tname = Test\n", encoding="utf-8")
        (gh_dir / "hosts.yml").write_text("github.com:\n  user: test\n", encoding="utf-8")
        monkeypatch.setenv("HOME", str(host_home))
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)

        env = module._prepare_direct_worker_environment(
            root / "state",
            "core",
            workspace_root=root,
            worker_bin="codex",
        )

        assert str(env.get("CODEX_HOME") or "").endswith("/direct-core")
        assert env.get("HOME") == env.get("CODEX_HOME")
        worker_home = Path(str(env["HOME"]))
        assert env.get("GIT_CONFIG_GLOBAL") == str(worker_home / ".gitconfig")
        assert env.get("XDG_CONFIG_HOME") == str(worker_home / ".config")
        assert env.get("GH_CONFIG_DIR") == str(worker_home / ".config" / "gh")
        assert (worker_home / ".gitconfig").read_text(encoding="utf-8") == (host_home / ".gitconfig").read_text(encoding="utf-8")
        assert (worker_home / ".config" / "gh" / "hosts.yml").read_text(encoding="utf-8") == (
            gh_dir / "hosts.yml"
        ).read_text(encoding="utf-8")


def test_prepare_account_environment_preserves_host_git_and_gh_auth(monkeypatch) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        host_home = root / "host-home"
        gh_dir = host_home / ".config" / "gh"
        gh_dir.mkdir(parents=True, exist_ok=True)
        (host_home / ".gitconfig").write_text(
            "[credential \"https://github.com\"]\n\thelper = !/usr/bin/gh auth git-credential\n",
            encoding="utf-8",
        )
        (gh_dir / "hosts.yml").write_text("github.com:\n  user: test\n", encoding="utf-8")
        monkeypatch.setenv("HOME", str(host_home))
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        monkeypatch.setenv("TEST_API_KEY", "secret")

        account = module.WorkerAccount(
            alias="acct-test",
            owner_id="owner",
            auth_kind="api_key",
            auth_json_file="",
            api_key_env="TEST_API_KEY",
            api_key_file="",
            allowed_models=[],
            health_state="ready",
            spark_enabled=True,
            bridge_priority=0,
            forced_login_method="",
            forced_chatgpt_workspace_id="",
            openai_base_url="",
            home_dir="",
            max_parallel_runs=1,
        )

        env = module._prepare_account_environment(root / "state", root, account)

        assert str(env.get("CODEX_HOME") or "").endswith("/acct-test")
        assert env.get("HOME") == env.get("CODEX_HOME")
        worker_home = Path(str(env["HOME"]))
        assert env.get("GIT_CONFIG_GLOBAL") == str(worker_home / ".gitconfig")
        assert env.get("XDG_CONFIG_HOME") == str(worker_home / ".config")
        assert env.get("GH_CONFIG_DIR") == str(worker_home / ".config" / "gh")
        assert (worker_home / ".gitconfig").read_text(encoding="utf-8") == (
            host_home / ".gitconfig"
        ).read_text(encoding="utf-8")
        assert (worker_home / ".config" / "gh" / "hosts.yml").read_text(encoding="utf-8") == (
            gh_dir / "hosts.yml"
        ).read_text(encoding="utf-8")
        assert env.get("CODEX_API_KEY") == "secret"


def test_prepare_direct_worker_environment_falls_back_to_passwd_home_for_git_auth(monkeypatch) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        host_home = root / "passwd-home"
        gh_dir = host_home / ".config" / "gh"
        gh_dir.mkdir(parents=True, exist_ok=True)
        (host_home / ".gitconfig").write_text("[user]\n\tname = Test\n", encoding="utf-8")
        (gh_dir / "hosts.yml").write_text("github.com:\n  user: test\n", encoding="utf-8")
        monkeypatch.setenv("HOME", "/")
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)

        class _PwdEntry:
            pw_dir = str(host_home)

        monkeypatch.setattr(module.pwd, "getpwuid", lambda _uid: _PwdEntry())

        env = module._prepare_direct_worker_environment(
            root / "state",
            "core",
            workspace_root=root,
            worker_bin="codex",
        )

        assert env.get("HOME") == env.get("CODEX_HOME")
        worker_home = Path(str(env["HOME"]))
        assert env.get("GIT_CONFIG_GLOBAL") == str(worker_home / ".gitconfig")
        assert env.get("XDG_CONFIG_HOME") == str(worker_home / ".config")
        assert env.get("GH_CONFIG_DIR") == str(worker_home / ".config" / "gh")
        assert (worker_home / ".gitconfig").read_text(encoding="utf-8") == (host_home / ".gitconfig").read_text(encoding="utf-8")
        assert (worker_home / ".config" / "gh" / "hosts.yml").read_text(encoding="utf-8") == (
            gh_dir / "hosts.yml"
        ).read_text(encoding="utf-8")


def test_prepare_account_environment_falls_back_to_workspace_secret_mirror_for_auth_json(monkeypatch) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        host_home = root / "host-home"
        gh_dir = host_home / ".config" / "gh"
        gh_dir.mkdir(parents=True, exist_ok=True)
        (host_home / ".gitconfig").write_text(
            "[credential \"https://github.com\"]\n\thelper = !/usr/bin/gh auth git-credential\n",
            encoding="utf-8",
        )
        (gh_dir / "hosts.yml").write_text("github.com:\n  user: test\n", encoding="utf-8")
        monkeypatch.setenv("HOME", str(host_home))
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        secrets_dir = root / "secrets"
        secrets_dir.mkdir(parents=True, exist_ok=True)
        mirrored_auth = secrets_dir / "acct-chatgpt-b.auth.json"
        mirrored_auth.write_text('{"access_token":"token"}\n', encoding="utf-8")

        account = module.WorkerAccount(
            alias="acct-chatgpt-b",
            owner_id="owner",
            auth_kind="chatgpt_auth_json",
            auth_json_file="/run/secrets/acct-chatgpt-b.auth.json",
            api_key_env="",
            api_key_file="",
            allowed_models=[],
            health_state="ready",
            spark_enabled=False,
            bridge_priority=0,
            forced_login_method="",
            forced_chatgpt_workspace_id="",
            openai_base_url="",
            home_dir="",
            max_parallel_runs=1,
        )

        env = module._prepare_account_environment(root / "state", root, account)

        worker_home = Path(str(env["HOME"]))
        assert (worker_home / "auth.json").read_text(encoding="utf-8") == mirrored_auth.read_text(encoding="utf-8")


def test_worker_reported_git_push_repos_parses_unique_repos() -> None:
    module = _load_module()
    stderr_text = """
exec
/usr/bin/bash -lc 'cd /docker/chummercomplete/chummer.run-services && git push' in /docker/fleet exited 128 in 11ms:
fatal: could not read Username for 'https://github.com': No such device or address
exec
/usr/bin/bash -lc 'cd /docker/fleet && git push' in /docker/fleet exited 128 in 14ms:
fatal: could not read Username for 'https://github.com': No such device or address
exec
/usr/bin/bash -lc 'cd /docker/fleet && git push' in /docker/fleet exited 128 in 14ms:
fatal: could not read Username for 'https://github.com': No such device or address
exec
/usr/bin/bash -lc 'cd /docker/chummercomplete/chummer6-core && git add Chummer.Application/Workspaces/HeroLabShadowrunImporter.cs Chummer.CoreEngine.Tests/HeroLabRulesParityAudit.cs && git commit -m "test(w17): lock Hero Lab online metadata-shape ruleset detection" && git push' in /docker/fleet exited 128 in 67ms:
fatal: could not read Username for 'https://github.com': No such device or address
"""
    repos = module._worker_reported_git_push_repos(stderr_text)
    assert repos == [
        Path("/docker/chummercomplete/chummer.run-services"),
        Path("/docker/fleet"),
        Path("/docker/chummercomplete/chummer6-core"),
    ]


def test_retry_worker_reported_git_pushes_uses_host_git_auth(monkeypatch) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        host_home = root / "host-home"
        gh_dir = host_home / ".config" / "gh"
        gh_dir.mkdir(parents=True, exist_ok=True)
        (host_home / ".gitconfig").write_text(
            "[credential \"https://github.com\"]\n\thelper = !/usr/bin/gh auth git-credential\n",
            encoding="utf-8",
        )
        (gh_dir / "hosts.yml").write_text("github.com:\n  user: test\n", encoding="utf-8")
        monkeypatch.setenv("HOME", "/")

        class _PwdEntry:
            pw_dir = str(host_home)

        monkeypatch.setattr(module.pwd, "getpwuid", lambda _uid: _PwdEntry())

        calls: list[tuple[list[str], dict[str, str]]] = []

        def fake_run(command, *, text, capture_output, check, env=None):
            assert env is not None
            calls.append((list(command), dict(env)))
            if command[:5] == ["git", "-C", "/docker/fleet", "remote", "get-url"]:
                return subprocess.CompletedProcess(command, 0, stdout="https://github.com/ArchonMegalon/fleet.git\n", stderr="")
            if command[:3] == ["gh", "auth", "token"]:
                return subprocess.CompletedProcess(command, 0, stdout="gho_test_token\n", stderr="")
            return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

        monkeypatch.setattr(module.subprocess, "run", fake_run)

        result = module._retry_worker_reported_git_pushes(
            "exec\n/usr/bin/bash -lc 'cd /docker/fleet && git push' in /docker/fleet exited 128 in 14ms:\n"
        )

        assert result["attempted"] == ["/docker/fleet"]
        assert result["succeeded"] == ["/docker/fleet"]
        assert result["failed"] == {}
        assert calls[0][0] == ["git", "-C", "/docker/fleet", "remote", "get-url", "origin"]
        assert calls[1][0] == ["gh", "auth", "token"]
        assert calls[2][0][:3] == ["git", "-C", "/docker/fleet"]
        assert any(part.startswith("http.https://github.com/.extraheader=AUTHORIZATION: basic ") for part in calls[2][0])
        assert calls[2][1]["HOME"] == str(host_home)
        assert calls[2][1]["GIT_CONFIG_GLOBAL"] == str(host_home / ".gitconfig")
        assert calls[2][1]["XDG_CONFIG_HOME"] == str(host_home / ".config")
        assert calls[2][1]["GH_CONFIG_DIR"] == str(gh_dir)


def test_github_https_auth_extraheader_returns_empty_when_gh_missing(monkeypatch) -> None:
    module = _load_module()

    def fake_run(command, *, text, capture_output, check, env=None):
        if command[:5] == ["git", "-C", "/docker/fleet", "remote", "get-url"]:
            return subprocess.CompletedProcess(command, 0, stdout="https://github.com/ArchonMegalon/fleet.git\n", stderr="")
        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    monkeypatch.setattr(module, "_github_auth_token", lambda _env: "")

    assert module._github_https_auth_extraheader({}, Path("/docker/fleet")) == ""


def test_github_auth_token_reads_hosts_yml_without_gh(monkeypatch) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        gh_dir = Path(tmp) / "gh"
        gh_dir.mkdir(parents=True, exist_ok=True)
        (gh_dir / "hosts.yml").write_text(
            "github.com:\n"
            "  users:\n"
            "    ArchonMegalon:\n"
            "      oauth_token: gho_hosts_token\n"
            "  git_protocol: https\n",
            encoding="utf-8",
        )

        def fake_run(command, *, text, capture_output, check, env=None):
            if command[:3] == ["gh", "auth", "token"]:
                raise FileNotFoundError("gh")
            raise AssertionError(f"unexpected command: {command}")

        _patch_launch_worker_fake_run(monkeypatch, module, fake_run)

        assert module._github_auth_token({"GH_CONFIG_DIR": str(gh_dir)}) == "gho_hosts_token"


def test_is_missing_github_push_blocker_accepts_remote_push_wording() -> None:
    module = _load_module()

    assert (
        module._is_missing_github_push_blocker(
            "`fleet` remote push is still blocked by missing GitHub HTTPS credentials: "
            "`fatal: could not read Username for 'https://github.com': No such device or address`."
        )
        is True
    )
    assert (
        module._is_missing_github_push_blocker(
            "host-side git push recovery failed after worker credential error: "
            "/docker/fleet: fatal: could not read Username for 'https://github.com': No such device or address"
        )
        is True
    )


def test_launch_worker_can_escape_retryable_direct_lane_failure_to_openai_account(monkeypatch) -> None:
    module = _load_module()
    monkeypatch.setattr(module, "_RUNTIME_ENV_CANDIDATES", ())
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_registry(root / "registry.yaml")
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("W2 milestone `21` remains active.\n", encoding="utf-8")
        auth_path = root / "acct-chatgpt-core.auth.json"
        auth_path.write_text('{"access_token":"token"}\n', encoding="utf-8")
        (root / "accounts.yaml").write_text(
            yaml.safe_dump(
                {
                    "account_policy": {"protected_owner_ids": ["tibor.girschele"]},
                    "accounts": {
                        "acct-chatgpt-core": {
                            "auth_kind": "chatgpt_auth_json",
                            "auth_json_file": str(auth_path),
                            "allowed_models": ["gpt-5.3-codex"],
                            "spark_enabled": False,
                            "health_state": "ready",
                            "owner_id": "tibor.girschele",
                        }
                    },
                }
            ),
            encoding="utf-8",
        )
        args = _args(root)
        args.worker_bin = "codexea"
        args.worker_lane = "core"
        args.worker_model = ""
        context = module.derive_context(args)
        monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_FALLBACK_LANES", "")
        monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_OPENAI_ESCAPE_ACCOUNT_ALIASES", "acct-chatgpt-core")
        monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_OPENAI_ESCAPE_MODELS", "gpt-5.3-codex")

        calls: list[list[str]] = []

        def fake_run(command, *, input, text, capture_output, cwd, check, env=None):
            calls.append(list(command))
            message_path = Path(command[command.index("-o") + 1])
            if command[0] == "codexea":
                message_path.write_text("Error: upstream_timeout:300s\n", encoding="utf-8")
                return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
            assert env is not None
            assert env.get("CODEX_HOME")
            message_path.write_text(
                "What shipped: openai escape hatch landed the slice\nWhat remains: none\nExact blocker: none\n",
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        _patch_launch_worker_fake_run(monkeypatch, module, fake_run)

        run = module.launch_worker(args, context, root / "state")

        assert run.worker_exit_code == 0
        assert run.accepted is True
        assert run.selected_account_alias == "acct-chatgpt-core"
        assert run.attempted_accounts == ["lane:core", "acct-chatgpt-core"]
        assert run.attempted_models == ["default", "gpt-5.3-codex"]
        assert calls[0][:3] == ["codexea", "core", "exec"]
        assert calls[1][0] == "codex"


def test_launch_worker_can_escape_routed_account_stall_to_openai_account(monkeypatch) -> None:
    module = _load_module()
    monkeypatch.setattr(module, "_RUNTIME_ENV_CANDIDATES", ())
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_registry(root / "registry.yaml")
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("W2 milestone `21` remains active.\n", encoding="utf-8")
        auth_path = root / "acct-chatgpt-core.auth.json"
        auth_path.write_text('{"access_token":"token"}\n', encoding="utf-8")
        (root / "accounts.yaml").write_text(
            yaml.safe_dump(
                {
                    "account_policy": {"protected_owner_ids": ["tibor.girschele"]},
                    "accounts": {
                        "acct-ea-core": {
                            "auth_kind": "ea",
                            "api_key_env": "EA_KEY",
                            "allowed_models": ["ea-coder-hard-batch", "ea-coder-hard"],
                            "health_state": "ready",
                            "owner_id": "tibor.girschele",
                            "lane": "core",
                        },
                        "acct-chatgpt-core": {
                            "auth_kind": "chatgpt_auth_json",
                            "auth_json_file": str(auth_path),
                            "allowed_models": ["gpt-5.3-codex"],
                            "spark_enabled": False,
                            "health_state": "ready",
                            "owner_id": "tibor.girschele",
                        },
                    },
                }
            ),
            encoding="utf-8",
        )
        args = _args(root)
        args.worker_bin = "codexea"
        args.worker_lane = "core"
        args.worker_model = "ea-coder-hard-batch"
        context = module.derive_context(args)
        monkeypatch.setenv("EA_KEY", "test-key")
        monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_OPENAI_ESCAPE_ACCOUNT_ALIASES", "acct-chatgpt-core")
        monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_OPENAI_ESCAPE_MODELS", "gpt-5.3-codex")

        calls: list[list[str]] = []

        def fake_run(command, *, input, text, capture_output, cwd, check, env=None):
            calls.append(list(command))
            message_path = Path(command[command.index("-o") + 1])
            if command[0] == "codexea":
                message_path.write_text("", encoding="utf-8")
                return subprocess.CompletedProcess(command, 124, stdout="", stderr="Error: worker_model_output_stalled:240s\n")
            assert env is not None
            assert env.get("CODEX_HOME")
            message_path.write_text(
                "What shipped: openai escape hatch landed the routed slice\nWhat remains: none\nExact blocker: none\n",
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        _patch_launch_worker_fake_run(monkeypatch, module, fake_run)

        run = module.launch_worker(args, context, root / "state")

        assert run.worker_exit_code == 0
        assert run.accepted is True
        assert run.selected_account_alias == "acct-chatgpt-core"
        assert run.attempted_accounts == ["acct-ea-core", "acct-chatgpt-core"]
        assert run.attempted_models == ["ea-coder-hard-batch", "gpt-5.3-codex"]
        assert calls[0][:3] == ["codexea", "core", "exec"]
        assert calls[1][0] == "codex"


def test_launch_worker_short_circuits_remaining_ea_accounts_after_escape_worthy_stall(monkeypatch) -> None:
    module = _load_module()
    monkeypatch.setattr(module, "_RUNTIME_ENV_CANDIDATES", ())
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_registry(root / "registry.yaml")
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("W2 milestone `21` remains active.\n", encoding="utf-8")
        auth_path = root / "acct-chatgpt-core.auth.json"
        auth_path.write_text('{"access_token":"token"}\n', encoding="utf-8")
        (root / "accounts.yaml").write_text(
            yaml.safe_dump(
                {
                    "account_policy": {"protected_owner_ids": ["tibor.girschele"]},
                    "accounts": {
                        "acct-ea-core-a": {
                            "auth_kind": "ea",
                            "api_key_env": "EA_KEY",
                            "allowed_models": ["ea-coder-hard-batch"],
                            "health_state": "ready",
                            "owner_id": "tibor.girschele",
                            "lane": "core",
                        },
                        "acct-ea-core-b": {
                            "auth_kind": "ea",
                            "api_key_env": "EA_KEY",
                            "allowed_models": ["ea-coder-hard-batch"],
                            "health_state": "ready",
                            "owner_id": "tibor.girschele",
                            "lane": "core",
                        },
                        "acct-chatgpt-core": {
                            "auth_kind": "chatgpt_auth_json",
                            "auth_json_file": str(auth_path),
                            "allowed_models": ["gpt-5.4"],
                            "spark_enabled": False,
                            "health_state": "ready",
                            "owner_id": "tibor.girschele",
                        },
                    },
                }
            ),
            encoding="utf-8",
        )
        args = _args(root)
        args.worker_bin = "codexea"
        args.worker_lane = "core"
        args.worker_model = "ea-coder-hard-batch"
        context = module.derive_context(args)
        monkeypatch.setenv("EA_KEY", "test-key")
        monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_OPENAI_ESCAPE_ACCOUNT_ALIASES", "acct-chatgpt-core")
        monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_OPENAI_ESCAPE_MODELS", "gpt-5.4")

        calls: list[list[str]] = []

        def fake_run(command, *, input, text, capture_output, cwd, check, env=None):
            calls.append(list(command))
            message_path = Path(command[command.index("-o") + 1])
            if command[0] == "codexea":
                message_path.write_text("", encoding="utf-8")
                return subprocess.CompletedProcess(command, 124, stdout="", stderr="Error: worker_model_output_stalled:240s\n")
            assert env is not None
            assert env.get("CODEX_HOME")
            message_path.write_text(
                "What shipped: openai escape hatch took over after the first EA stall\nWhat remains: none\nExact blocker: none\n",
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        _patch_launch_worker_fake_run(monkeypatch, module, fake_run)

        run = module.launch_worker(args, context, root / "state")

        assert run.accepted is True
        assert run.selected_account_alias == "acct-chatgpt-core"
        assert run.attempted_accounts == ["acct-ea-core-a", "acct-chatgpt-core"]
        assert run.attempted_models == ["ea-coder-hard-batch", "gpt-5.4"]
        assert calls[0][0] == "codexea"
        assert calls[1][0] == "codex"


def test_should_attempt_openai_escape_hatch_rejects_status_helper_loop_signal(monkeypatch) -> None:
    module = _load_module()
    monkeypatch.setattr(module, "_RUNTIME_ENV_CANDIDATES", ())
    monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_OPENAI_ESCAPE_ACCOUNT_ALIASES", "acct-chatgpt-core")

    assert (
        module._should_attempt_openai_escape_hatch(
            "Error: worker_status_helper_loop:repeated_blocked_status_polling",
            "",
            "",
        )
        is False
    )


def test_should_attempt_openai_escape_hatch_accepts_high_demand_signal(monkeypatch) -> None:
    module = _load_module()
    monkeypatch.setattr(module, "_RUNTIME_ENV_CANDIDATES", ())
    monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_OPENAI_ESCAPE_ACCOUNT_ALIASES", "acct-chatgpt-core")

    assert (
        module._should_attempt_openai_escape_hatch(
            "",
            "",
            "ERROR: We're currently experiencing high demand, which may cause temporary errors.",
        )
        is True
    )


def test_should_short_circuit_routed_ea_accounts_to_openai_escape_accepts_model_output_stall(monkeypatch) -> None:
    module = _load_module()
    monkeypatch.setattr(module, "_RUNTIME_ENV_CANDIDATES", ())
    monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_OPENAI_ESCAPE_ACCOUNT_ALIASES", "acct-chatgpt-core")

    assert (
        module._should_short_circuit_routed_ea_accounts_to_openai_escape(
            "worker exit 124",
            "",
            "Error: worker_model_output_stalled:240s\n",
        )
        is True
    )


def test_openai_escape_hatch_settings_prefer_runtime_env_file_over_stale_process_env(monkeypatch) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        runtime_env = Path(tmp) / "runtime.env"
        runtime_env.write_text(
            "\n".join(
                [
                    "CHUMMER_DESIGN_SUPERVISOR_OPENAI_ESCAPE_ACCOUNT_ALIASES=acct-chatgpt-core",
                    "CHUMMER_DESIGN_SUPERVISOR_OPENAI_ESCAPE_MODELS=gpt-5.3-codex-spark,gpt-5.4",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(module, "_RUNTIME_ENV_CANDIDATES", (runtime_env,))
        monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_OPENAI_ESCAPE_ACCOUNT_ALIASES", "")
        monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_OPENAI_ESCAPE_MODELS", "ea-coder-hard")

        assert module._openai_escape_hatch_account_aliases() == ["acct-chatgpt-core"]
        assert module._openai_escape_hatch_model_candidates() == ["gpt-5.3-codex-spark", "gpt-5.4"]


def test_recent_helper_loop_failure_count_separates_status_helper_loop_failures() -> None:
    module = _load_module()
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(module, "_RUNTIME_ENV_CANDIDATES", ())
    with tempfile.TemporaryDirectory() as tmp:
        state_root = Path(tmp)
        history_rows = [
            {"run_id": "run-ok", "accepted": True, "blocker": "none"},
            {
                "run_id": "run-a",
                "accepted": False,
                "blocker": "Error: worker_status_helper_loop:repeated_blocked_status_polling",
            },
            {
                "run_id": "run-b",
                "accepted": False,
                "blocker": "Error: worker_status_helper_loop:repeated_blocked_status_polling",
            },
        ]
        (state_root / "history.jsonl").write_text(
            "".join(json.dumps(row) + "\n" for row in history_rows),
            encoding="utf-8",
        )

        assert module._recent_helper_loop_failure_count(state_root) == 0
        assert module._recent_status_helper_loop_failure_count(state_root) == 2
        assert module._prefer_openai_escape_fastpath_after_recent_helper_loop(state_root) is True
    monkeypatch.undo()


def test_prefer_openai_escape_fastpath_after_single_status_helper_loop_promotes_to_escape() -> None:
    module = _load_module()
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(module, "_RUNTIME_ENV_CANDIDATES", ())
    with tempfile.TemporaryDirectory() as tmp:
        state_root = Path(tmp)
        history_rows = [
            {"run_id": "run-ok", "accepted": True, "blocker": "none"},
            {
                "run_id": "run-a",
                "accepted": False,
                "blocker": "Error: worker_status_helper_loop:repeated_blocked_status_polling",
            },
        ]
        (state_root / "history.jsonl").write_text(
            "".join(json.dumps(row) + "\n" for row in history_rows),
            encoding="utf-8",
        )

        assert module._recent_helper_loop_failure_count(state_root) == 0
        assert module._recent_status_helper_loop_failure_count(state_root) == 1
        assert module._prefer_openai_escape_fastpath_after_recent_helper_loop(state_root) is True
    monkeypatch.undo()


def test_prefer_openai_escape_fastpath_after_recent_helper_loop_requires_enabled_escape(monkeypatch) -> None:
    module = _load_module()
    monkeypatch.setattr(module, "_RUNTIME_ENV_CANDIDATES", ())
    with tempfile.TemporaryDirectory() as tmp:
        state_root = Path(tmp)
        (state_root / "history.jsonl").write_text(
            "".join(
                json.dumps(
                    {
                        "run_id": f"run-{idx}",
                        "accepted": False,
                        "blocker": "Error: worker_model_output_stalled:240s",
                    }
                )
                + "\n"
                for idx in range(2)
            ),
            encoding="utf-8",
        )
        monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_OPENAI_ESCAPE_ACCOUNT_ALIASES", "acct-chatgpt-core")

        assert module._prefer_openai_escape_fastpath_after_recent_helper_loop(state_root) is True


def test_prefer_openai_escape_fastpath_after_recent_helper_loop_survives_escape_worker_exit_one(monkeypatch) -> None:
    module = _load_module()
    monkeypatch.setattr(module, "_RUNTIME_ENV_CANDIDATES", ())
    with tempfile.TemporaryDirectory() as tmp:
        state_root = Path(tmp)
        (state_root / "history.jsonl").write_text(
            "".join(
                json.dumps(row) + "\n"
                for row in [
                    {
                        "run_id": "run-1",
                        "accepted": False,
                        "blocker": "Error: worker_model_output_stalled:240s",
                    },
                    {
                        "run_id": "run-2",
                        "accepted": True,
                        "blocker": "linux host cannot produce native windows proof",
                    },
                    {
                        "run_id": "run-3",
                        "accepted": False,
                        "blocker": "worker exit 1",
                    },
                    {
                        "run_id": "run-4",
                        "accepted": False,
                        "blocker": "Error: worker_status_helper_loop:repeated_blocked_status_polling",
                    },
                ]
            ),
            encoding="utf-8",
        )
        monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_OPENAI_ESCAPE_ACCOUNT_ALIASES", "acct-chatgpt-core")

        assert module._prefer_openai_escape_fastpath_after_recent_helper_loop(state_root) is True


def test_prefer_openai_escape_fastpath_after_recent_helper_loop_persists_after_escape_pool_exhaustion(monkeypatch) -> None:
    module = _load_module()
    monkeypatch.setattr(module, "_RUNTIME_ENV_CANDIDATES", ())
    with tempfile.TemporaryDirectory() as tmp:
        state_root = Path(tmp)
        (state_root / "history.jsonl").write_text(
            "".join(
                json.dumps(row) + "\n"
                for row in [
                    {
                        "run_id": "run-1",
                        "accepted": False,
                        "blocker": "Error: worker_model_output_stalled:240s",
                    },
                    {
                        "run_id": "run-2",
                        "accepted": False,
                        "blocker": "openai escape pool is currently exhausted after recent routed-lane output stalls; next escape retry at 2099-01-01T00:00:00Z",
                    },
                ]
            ),
            encoding="utf-8",
        )
        monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_OPENAI_ESCAPE_ACCOUNT_ALIASES", "acct-chatgpt-core")

        assert module._prefer_openai_escape_fastpath_after_recent_helper_loop(state_root) is True


def test_eligible_worker_account_restore_probe_accepts_chatgpt_usage_limit_when_probe_due(monkeypatch) -> None:
    module = _load_module()
    monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_ACCOUNT_RESTORE_PROBE_SECONDS", "300")
    account = module.WorkerAccount(
        alias="acct-chatgpt-core",
        owner_id="tibor.girschele",
        auth_kind="chatgpt_auth_json",
        auth_json_file="/tmp/auth.json",
        api_key_env="",
        api_key_file="",
        allowed_models=["gpt-5.3-codex-spark", "gpt-5.3-codex"],
        health_state="ready",
        spark_enabled=True,
        bridge_priority=0,
        forced_login_method="",
        forced_chatgpt_workspace_id="",
        openai_base_url="",
        home_dir="",
        lane="",
        max_parallel_runs=8,
    )
    payload = {
        "sources": {
            "chatgpt_auth_json:/tmp/auth.json": {
                "alias": "acct-chatgpt-core",
                "owner_id": "tibor.girschele",
                "source_key": "chatgpt_auth_json:/tmp/auth.json",
                "backoff_until": "2099-01-01T00:00:00Z",
                "last_error": "usage-limited; recheck at 2099-01-01T00:00:00Z",
                "restore_probe_at": "",
            }
        }
    }

    assert module._eligible_worker_account_restore_probe(payload, account, now=dt.datetime(2098, 1, 1, tzinfo=dt.timezone.utc)) is True


def test_chatgpt_restore_probe_allowed_only_for_primary_probe_shard(monkeypatch, tmp_path: Path) -> None:
    module = _load_module()
    aggregate_root = tmp_path / "state"
    primary_shard = aggregate_root / "shard-1"
    sibling_shard = aggregate_root / "shard-2"
    primary_shard.mkdir(parents=True, exist_ok=True)
    sibling_shard.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(module, "_primary_probe_shard_name", lambda state_root: "shard-1")

    assert module._chatgpt_restore_probe_allowed_for_state_root(aggregate_root) is True
    assert module._chatgpt_restore_probe_allowed_for_state_root(primary_shard) is True
    assert module._chatgpt_restore_probe_allowed_for_state_root(sibling_shard) is False


def test_load_openai_escape_accounts_returns_restore_probe_aliases_for_usage_limited_chatgpt_source(monkeypatch) -> None:
    module = _load_module()
    monkeypatch.setattr(module, "_RUNTIME_ENV_CANDIDATES", ())
    monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_ACCOUNT_RESTORE_PROBE_SECONDS", "300")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        auth_path = root / "acct-chatgpt-core.auth.json"
        auth_path.write_text('{"auth_mode":"chatgpt","tokens":{"access_token":"token"}}\n', encoding="utf-8")
        (root / "accounts.yaml").write_text(
            yaml.safe_dump(
                {
                    "account_policy": {"protected_owner_ids": ["tibor.girschele"]},
                    "accounts": {
                        "acct-chatgpt-core": {
                            "auth_kind": "chatgpt_auth_json",
                            "auth_json_file": str(auth_path),
                            "allowed_models": ["gpt-5.3-codex-spark", "gpt-5.3-codex"],
                            "spark_enabled": True,
                            "health_state": "ready",
                            "owner_id": "tibor.girschele",
                        }
                    },
                }
            ),
            encoding="utf-8",
        )
        args = _args(root)
        monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_OPENAI_ESCAPE_ACCOUNT_ALIASES", "acct-chatgpt-core")
        monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_OPENAI_ESCAPE_MODELS", "gpt-5.3-codex-spark,gpt-5.3-codex")
        account_runtime = {
            "sources": {
                f"chatgpt_auth_json:{auth_path}": {
                    "alias": "acct-chatgpt-core",
                    "owner_id": "tibor.girschele",
                    "source_key": f"chatgpt_auth_json:{auth_path}",
                    "backoff_until": "2099-01-01T00:00:00Z",
                    "last_error": "usage-limited; recheck at 2099-01-01T00:00:00Z",
                    "restore_probe_at": "",
                }
            }
        }

        _escape_args, escape_accounts, supplemental_aliases, restore_probe_aliases = module._load_openai_escape_accounts(
            args,
            account_runtime,
        )

        assert [account.alias for account in escape_accounts] == ["acct-chatgpt-core"]
        assert supplemental_aliases == []
        assert restore_probe_aliases == ["acct-chatgpt-core"]


def test_load_openai_escape_accounts_restore_probes_one_alias_per_distinct_chatgpt_source(monkeypatch) -> None:
    module = _load_module()
    monkeypatch.setattr(module, "_RUNTIME_ENV_CANDIDATES", ())
    monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_ACCOUNT_RESTORE_PROBE_SECONDS", "300")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        auth_a = root / "acct-a.auth.json"
        auth_b = root / "acct-b.auth.json"
        auth_a.write_text('{"auth_mode":"chatgpt","tokens":{"access_token":"token-a"}}\n', encoding="utf-8")
        auth_b.write_text('{"auth_mode":"chatgpt","tokens":{"access_token":"token-b"}}\n', encoding="utf-8")
        (root / "accounts.yaml").write_text(
            yaml.safe_dump(
                {
                    "account_policy": {"protected_owner_ids": ["tibor.girschele"]},
                    "accounts": {
                        "acct-chatgpt-a1": {
                            "auth_kind": "chatgpt_auth_json",
                            "auth_json_file": str(auth_a),
                            "allowed_models": ["gpt-5.4"],
                            "health_state": "ready",
                            "owner_id": "tibor.girschele",
                        },
                        "acct-chatgpt-a2": {
                            "auth_kind": "chatgpt_auth_json",
                            "auth_json_file": str(auth_a),
                            "allowed_models": ["gpt-5.4"],
                            "health_state": "ready",
                            "owner_id": "tibor.girschele",
                        },
                        "acct-chatgpt-b1": {
                            "auth_kind": "chatgpt_auth_json",
                            "auth_json_file": str(auth_b),
                            "allowed_models": ["gpt-5.4"],
                            "health_state": "ready",
                            "owner_id": "tibor.girschele",
                        },
                    },
                }
            ),
            encoding="utf-8",
        )
        args = _args(root)
        monkeypatch.setenv(
            "CHUMMER_DESIGN_SUPERVISOR_OPENAI_ESCAPE_ACCOUNT_ALIASES",
            "acct-chatgpt-a1,acct-chatgpt-a2,acct-chatgpt-b1",
        )
        monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_OPENAI_ESCAPE_MODELS", "gpt-5.4")
        account_runtime = {
            "sources": {
                f"chatgpt_auth_json:{auth_a}": {
                    "alias": "acct-chatgpt-a1",
                    "owner_id": "tibor.girschele",
                    "source_key": f"chatgpt_auth_json:{auth_a}",
                    "backoff_until": "2099-01-01T00:00:00Z",
                    "last_error": "usage-limited; recheck at 2099-01-01T00:00:00Z",
                    "restore_probe_at": "",
                },
                f"chatgpt_auth_json:{auth_b}": {
                    "alias": "acct-chatgpt-b1",
                    "owner_id": "tibor.girschele",
                    "source_key": f"chatgpt_auth_json:{auth_b}",
                    "backoff_until": "2099-01-01T00:00:00Z",
                    "last_error": "usage-limited; recheck at 2099-01-01T00:00:00Z",
                    "restore_probe_at": "",
                },
            }
        }

        _escape_args, escape_accounts, supplemental_aliases, restore_probe_aliases = module._load_openai_escape_accounts(
            args,
            account_runtime,
        )

        assert [account.alias for account in escape_accounts] == ["acct-chatgpt-a1", "acct-chatgpt-b1"]
        assert supplemental_aliases == []
        assert restore_probe_aliases == ["acct-chatgpt-a1", "acct-chatgpt-b1"]


def test_fallback_auth_json_path_prefers_host_codex_auth_for_chatgpt_secret(monkeypatch, tmp_path: Path) -> None:
    module = _load_module()
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir(parents=True, exist_ok=True)
    mirrored_secret = workspace_root / "secrets" / "chatgpt.auth.json"
    mirrored_secret.parent.mkdir(parents=True, exist_ok=True)
    mirrored_secret.write_text('{"auth_mode":"chatgpt","tokens":{"access_token":"stale"}}\n', encoding="utf-8")
    host_home = tmp_path / "home"
    host_codex_auth = host_home / ".codex" / "auth.json"
    host_codex_auth.parent.mkdir(parents=True, exist_ok=True)
    host_codex_auth.write_text('{"auth_mode":"chatgpt","tokens":{"access_token":"live"}}\n', encoding="utf-8")
    monkeypatch.setenv("HOME", str(host_home))

    resolved = module._fallback_auth_json_path(Path("/run/secrets/chatgpt.auth.json"), workspace_root)

    assert resolved == host_codex_auth


def test_run_scoped_worker_contract_violation_accepts_status_helper_loop() -> None:
    module = _load_module()

    assert module._run_scoped_worker_contract_violation(
        "Error: worker_status_helper_loop:repeated_blocked_status_polling"
    ) is True


def test_run_scoped_worker_contract_violation_does_not_flag_plain_model_output_stall() -> None:
    module = _load_module()

    assert module._run_scoped_worker_contract_violation(
        "Error: worker_model_output_stalled:240s"
    ) is False


def test_launch_worker_prefers_escape_first_after_recent_helper_loop_churn(monkeypatch) -> None:
    module = _load_module()
    monkeypatch.setattr(module, "_RUNTIME_ENV_CANDIDATES", ())
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_registry(root / "registry.yaml")
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("W2 milestone `21` remains active.\n", encoding="utf-8")
        auth_path = root / "acct-chatgpt-core.auth.json"
        auth_path.write_text('{"access_token":"token"}\n', encoding="utf-8")
        (root / "accounts.yaml").write_text(
            yaml.safe_dump(
                {
                    "account_policy": {"protected_owner_ids": ["tibor.girschele"]},
                    "accounts": {
                        "acct-ea-core": {
                            "auth_kind": "ea",
                            "api_key_env": "EA_KEY",
                            "allowed_models": ["ea-coder-hard-batch", "ea-coder-hard"],
                            "health_state": "ready",
                            "owner_id": "tibor.girschele",
                            "lane": "core",
                        },
                        "acct-chatgpt-core": {
                            "auth_kind": "chatgpt_auth_json",
                            "auth_json_file": str(auth_path),
                            "allowed_models": ["gpt-5.3-codex-spark", "gpt-5.3-codex"],
                            "spark_enabled": True,
                            "health_state": "ready",
                            "owner_id": "tibor.girschele",
                        },
                    },
                }
            ),
            encoding="utf-8",
        )
        state_root = root / "state"
        state_root.mkdir(parents=True, exist_ok=True)
        (state_root / "history.jsonl").write_text(
            "".join(
                json.dumps(
                    {
                        "run_id": f"run-{idx}",
                        "accepted": False,
                        "blocker": "Error: worker_status_helper_loop:repeated_blocked_status_polling",
                    }
                )
                + "\n"
                for idx in range(2)
            ),
            encoding="utf-8",
        )
        args = _args(root)
        args.worker_bin = "codexea"
        args.worker_lane = "core"
        args.worker_model = "ea-coder-hard-batch"
        context = module.derive_context(args)
        monkeypatch.setenv("EA_KEY", "test-key")
        monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_OPENAI_ESCAPE_ACCOUNT_ALIASES", "acct-chatgpt-core")
        monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_OPENAI_ESCAPE_MODELS", "gpt-5.3-codex-spark,gpt-5.3-codex")

        calls: list[list[str]] = []

        def fake_run(command, *, input, text, capture_output, cwd, check, env=None):
            calls.append(list(command))
            message_path = Path(command[command.index("-o") + 1])
            assert command[0] == "codex"
            assert env is not None
            assert env.get("CODEX_HOME")
            message_path.write_text(
                "What shipped: escape-first landed the slice\nWhat remains: none\nExact blocker: none\n",
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        _patch_launch_worker_fake_run(monkeypatch, module, fake_run)

        run = module.launch_worker(args, context, state_root)

        assert run.worker_exit_code == 0
        assert run.accepted is True
        assert run.selected_account_alias == "acct-chatgpt-core"
        assert run.attempted_accounts == ["acct-chatgpt-core"]
        assert run.attempted_models == ["gpt-5.3-codex-spark"]
        assert calls[0][0] == "codex"


def test_launch_worker_widens_escape_pool_when_primary_escape_source_is_usage_limited(monkeypatch) -> None:
    module = _load_module()
    monkeypatch.setattr(module, "_RUNTIME_ENV_CANDIDATES", ())
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_registry(root / "registry.yaml")
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("W2 milestone `21` remains active.\n", encoding="utf-8")
        primary_auth_path = root / "acct-chatgpt-primary.auth.json"
        primary_auth_path.write_text('{"access_token":"primary"}\n', encoding="utf-8")
        archon_auth_path = root / "acct-chatgpt-archon.auth.json"
        archon_auth_path.write_text('{"access_token":"archon"}\n', encoding="utf-8")
        (root / "accounts.yaml").write_text(
            yaml.safe_dump(
                {
                    "account_policy": {"protected_owner_ids": ["tibor.girschele", "archon.megalon"]},
                    "accounts": {
                        "acct-ea-core": {
                            "auth_kind": "ea",
                            "api_key_env": "EA_KEY",
                            "allowed_models": ["ea-coder-hard-batch", "ea-coder-hard"],
                            "health_state": "ready",
                            "owner_id": "tibor.girschele",
                            "lane": "core",
                        },
                        "acct-chatgpt-primary": {
                            "auth_kind": "chatgpt_auth_json",
                            "auth_json_file": str(primary_auth_path),
                            "allowed_models": ["gpt-5.3-codex-spark", "gpt-5.3-codex"],
                            "spark_enabled": True,
                            "health_state": "ready",
                            "owner_id": "tibor.girschele",
                        },
                        "acct-chatgpt-archon": {
                            "auth_kind": "chatgpt_auth_json",
                            "auth_json_file": str(archon_auth_path),
                            "allowed_models": ["gpt-5.3-codex-spark", "gpt-5.3-codex"],
                            "spark_enabled": True,
                            "health_state": "ready",
                            "owner_id": "archon.megalon",
                            "lane": "core",
                        },
                    },
                }
            ),
            encoding="utf-8",
        )
        state_root = root / "state"
        state_root.mkdir(parents=True, exist_ok=True)
        (state_root / "history.jsonl").write_text(
            "".join(
                json.dumps(
                    {
                        "run_id": f"run-{idx}",
                        "accepted": False,
                        "blocker": "Error: worker_status_helper_loop:repeated_blocked_status_polling",
                    }
                )
                + "\n"
                for idx in range(2)
            ),
            encoding="utf-8",
        )
        (state_root / "account_runtime.json").write_text(
            json.dumps(
                {
                    "sources": {
                        f"chatgpt_auth_json:{primary_auth_path}": {
                            "alias": "acct-chatgpt-primary",
                            "owner_id": "tibor.girschele",
                            "source_key": f"chatgpt_auth_json:{primary_auth_path}",
                            "backoff_until": "2099-01-01T00:00:00Z",
                            "last_error": "usage-limited; recheck at 2099-01-01T00:00:00Z",
                        }
                    }
                }
            ),
            encoding="utf-8",
        )
        args = _args(root)
        args.worker_bin = "codexea"
        args.worker_lane = "core"
        args.worker_model = "ea-coder-hard-batch"
        context = module.derive_context(args)
        monkeypatch.setenv("EA_KEY", "test-key")
        monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_OPENAI_ESCAPE_ACCOUNT_ALIASES", "acct-chatgpt-primary")
        monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_OPENAI_ESCAPE_MODELS", "gpt-5.3-codex-spark,gpt-5.3-codex")

        calls: list[list[str]] = []

        def fake_run(command, *, input, text, capture_output, cwd, check, env=None):
            calls.append(list(command))
            message_path = Path(command[command.index("-o") + 1])
            message_path.write_text(
                "What shipped: widened escape pool landed the slice\nWhat remains: none\nExact blocker: none\n",
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        _patch_launch_worker_fake_run(monkeypatch, module, fake_run)

        run = module.launch_worker(args, context, state_root)

        assert run.worker_exit_code == 0
        assert run.accepted is True
        assert run.selected_account_alias == "acct-chatgpt-archon"
        assert run.attempted_accounts == ["acct-chatgpt-archon"]
        assert run.attempted_models == ["gpt-5.3-codex-spark"]
        assert calls[0][0] == "codex"


def test_launch_worker_suppresses_ea_fallback_when_escape_pool_is_exhausted_after_helper_loop(monkeypatch) -> None:
    module = _load_module()
    monkeypatch.setattr(module, "_RUNTIME_ENV_CANDIDATES", ())
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_registry(root / "registry.yaml")
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("W2 milestone `21` remains active.\n", encoding="utf-8")
        primary_auth_path = root / "acct-chatgpt-primary.auth.json"
        primary_auth_path.write_text('{"access_token":"primary"}\n', encoding="utf-8")
        (root / "accounts.yaml").write_text(
            yaml.safe_dump(
                {
                    "account_policy": {"protected_owner_ids": ["tibor.girschele"]},
                    "accounts": {
                        "acct-ea-core": {
                            "auth_kind": "ea",
                            "api_key_env": "EA_KEY",
                            "allowed_models": ["ea-coder-hard-batch", "ea-coder-hard"],
                            "health_state": "ready",
                            "owner_id": "tibor.girschele",
                            "lane": "core",
                        },
                        "acct-chatgpt-primary": {
                            "auth_kind": "chatgpt_auth_json",
                            "auth_json_file": str(primary_auth_path),
                            "allowed_models": ["gpt-5.3-codex-spark", "gpt-5.3-codex"],
                            "spark_enabled": True,
                            "health_state": "ready",
                            "owner_id": "tibor.girschele",
                        },
                    },
                }
            ),
            encoding="utf-8",
        )
        state_root = root / "state"
        state_root.mkdir(parents=True, exist_ok=True)
        (state_root / "history.jsonl").write_text(
            "".join(
                json.dumps(
                    {
                        "run_id": f"run-{idx}",
                        "accepted": False,
                        "blocker": "Error: worker_status_helper_loop:repeated_blocked_status_polling",
                    }
                )
                + "\n"
                for idx in range(2)
            ),
            encoding="utf-8",
        )
        (state_root / "account_runtime.json").write_text(
            json.dumps(
                {
                    "sources": {
                        f"chatgpt_auth_json:{primary_auth_path}": {
                            "alias": "acct-chatgpt-primary",
                            "owner_id": "tibor.girschele",
                            "source_key": f"chatgpt_auth_json:{primary_auth_path}",
                            "backoff_until": "2099-01-01T00:00:00Z",
                            "last_error": "usage-limited; recheck at 2099-01-01T00:00:00Z",
                        }
                    }
                }
            ),
            encoding="utf-8",
        )
        args = _args(root)
        args.worker_bin = "codexea"
        args.worker_lane = "core"
        args.worker_model = "ea-coder-hard-batch"
        context = module.derive_context(args)
        monkeypatch.setenv("EA_KEY", "test-key")
        monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_OPENAI_ESCAPE_ACCOUNT_ALIASES", "acct-chatgpt-primary")
        monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_OPENAI_ESCAPE_MODELS", "gpt-5.3-codex-spark,gpt-5.3-codex")

        calls: list[list[str]] = []

        def fake_run(command, *, input, text, capture_output, cwd, check, env=None, timeout=None):
            calls.append(list(command))
            if command[0] != "codexea":
                raise AssertionError("only the routed EA lane should run when the escape pool is exhausted")
            message_path = Path(command[command.index("-o") + 1])
            message_path.write_text(
                "What shipped: routed EA lane recovered after escape exhaustion\n"
                "What remains: follow-through\n"
                "Exact blocker: none\n",
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        _patch_launch_worker_fake_run(monkeypatch, module, fake_run)

        run = module.launch_worker(args, context, state_root)

        assert run.accepted is True
        assert run.selected_account_alias == "acct-ea-core"
        assert run.attempted_accounts == ["acct-ea-core"]
        assert run.attempted_models == ["ea-coder-hard-batch"]
        assert calls[0][0] == "codexea"
        stderr_text = (state_root / "runs" / run.run_id / "worker.stderr.log").read_text(encoding="utf-8")
        assert "openai escape pool is currently exhausted after recent helper-loop churn" in stderr_text
        assert "continuing with routed EA fallback" in stderr_text


def test_launch_worker_full_fallback_does_not_reenter_routed_restore_probe(monkeypatch) -> None:
    module = _load_module()
    monkeypatch.setattr(module, "_RUNTIME_ENV_CANDIDATES", ())
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_registry(root / "registry.yaml")
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("W2 milestone `21` remains active.\n", encoding="utf-8")
        auth_path = root / "acct-chatgpt-core.auth.json"
        auth_path.write_text('{"access_token":"token"}\n', encoding="utf-8")
        (root / "accounts.yaml").write_text(
            yaml.safe_dump(
                {
                    "account_policy": {"protected_owner_ids": ["tibor.girschele"]},
                    "accounts": {
                        "acct-ea-core-a": {
                            "auth_kind": "ea",
                            "api_key_env": "EA_KEY",
                            "allowed_models": ["ea-coder-hard-batch"],
                            "health_state": "ready",
                            "owner_id": "tibor.girschele",
                            "lane": "core",
                        },
                        "acct-ea-core-b": {
                            "auth_kind": "ea",
                            "api_key_env": "EA_KEY",
                            "allowed_models": ["ea-coder-hard-batch"],
                            "health_state": "ready",
                            "owner_id": "tibor.girschele",
                            "lane": "core",
                        },
                        "acct-chatgpt-core": {
                            "auth_kind": "chatgpt_auth_json",
                            "auth_json_file": str(auth_path),
                            "allowed_models": ["gpt-5.4"],
                            "spark_enabled": False,
                            "health_state": "ready",
                            "owner_id": "tibor.girschele",
                        },
                    },
                }
            ),
            encoding="utf-8",
        )
        state_root = root / "state"
        state_root.mkdir(parents=True, exist_ok=True)
        args = _args(root)
        args.worker_bin = "codexea"
        args.worker_lane = "core"
        args.worker_model = "ea-coder-hard-batch"
        context = module.derive_context(args)
        monkeypatch.setenv("EA_KEY", "test-key")
        monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_ACCOUNT_RESTORE_PROBE_SECONDS", "1")
        monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_PREFER_FULL_EA_LANES", "1")
        monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_OPENAI_ESCAPE_ACCOUNT_ALIASES", "acct-chatgpt-core")
        monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_OPENAI_ESCAPE_MODELS", "gpt-5.4")

        calls: list[list[str]] = []

        def fake_run(command, *, input, text, capture_output, cwd, check, env=None, timeout=None):
            calls.append(list(command))
            message_path = Path(command[command.index("-o") + 1])
            if len(calls) == 1:
                message_path.write_text("", encoding="utf-8")
                return subprocess.CompletedProcess(command, 124, stdout="", stderr="Error: worker_model_output_stalled:240s\n")
            if command[0] == "codex":
                message_path.write_text("", encoding="utf-8")
                return subprocess.CompletedProcess(command, 1, stdout="", stderr="Error: rate limit reached\n")
            message_path.write_text(
                "What shipped: direct full fallback landed the slice\nWhat remains: none\nExact blocker: none\n",
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        _patch_launch_worker_fake_run(monkeypatch, module, fake_run)

        run = module.launch_worker(args, context, state_root)

        assert run.accepted is True
        assert run.attempted_accounts == ["acct-ea-core-a", "acct-chatgpt-core", "lane:core"]
        assert run.attempted_models == ["ea-coder-hard-batch", "gpt-5.4", "ea-coder-hard-batch"]
        assert calls[0][0] == "codexea"
        assert calls[1][0] == "codex"
        assert calls[2][0] == "codexea"


def test_launch_worker_falls_back_from_account_primary_to_direct_ea_lane_on_usage_limit(monkeypatch) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_registry(root / "registry.yaml")
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("W2 milestone `21` remains active.\n", encoding="utf-8")
        auth_path = root / "acct-chatgpt-b.auth.json"
        auth_path.write_text('{"access_token":"token"}\n', encoding="utf-8")
        (root / "accounts.yaml").write_text(
            yaml.safe_dump(
                {
                    "account_policy": {"protected_owner_ids": ["the.girscheles", "archon.megalon"]},
                    "accounts": {
                        "acct-chatgpt-b": {
                            "auth_kind": "chatgpt_auth_json",
                            "auth_json_file": str(auth_path),
                            "allowed_models": ["gpt-5.3-codex"],
                            "spark_enabled": False,
                            "health_state": "ready",
                            "owner_id": "the.girscheles",
                        }
                    },
                }
            ),
            encoding="utf-8",
        )
        args = _args(root)
        args.worker_bin = "codex"
        args.worker_lane = ""
        args.worker_model = "gpt-5.3-codex"
        args.account_alias = ["acct-chatgpt-b"]
        context = module.derive_context(args)
        monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_ACCOUNT_FALLBACK_WORKER_BIN", "codexea")
        monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_ACCOUNT_FALLBACK_WORKER_LANE", "core")
        monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_ACCOUNT_FALLBACK_MODELS", "ea-coder-hard-batch")
        monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_ACCOUNT_FALLBACK_LANES", "core_rescue,survival,repair")
        monkeypatch.setattr(
            module,
            "_direct_worker_lane_health_snapshot",
            lambda _args, _lanes: {
                "status": "pass",
                "reason": "all checked direct lanes are currently routable",
                "routable_lanes": ["core", "core_rescue", "survival", "repair"],
                "unroutable_lanes": [],
                "lanes": {
                    "core": {"worker_lane": "core", "profile": "core_batch", "state": "ready", "routable": True, "reason": ""},
                    "core_rescue": {"worker_lane": "core_rescue", "profile": "core_rescue", "state": "ready", "routable": True, "reason": ""},
                    "survival": {"worker_lane": "survival", "profile": "survival", "state": "ready", "routable": True, "reason": ""},
                    "repair": {"worker_lane": "repair", "profile": "repair", "state": "ready", "routable": True, "reason": ""},
                },
            },
        )

        calls: list[list[str]] = []

        def fake_run(command, *, input, text, capture_output, cwd, check, env=None, timeout=None):
            calls.append(list(command))
            message_path = Path(command[command.index("-o") + 1])
            if command[0] == "codex":
                return subprocess.CompletedProcess(
                    command,
                    1,
                    stdout="",
                    stderr="Error: usage limit reached. Send a request to your admin.\n",
                )
            message_path.write_text(
                "What shipped: direct ea fallback kept the shard moving\n"
                "What remains: follow-through\n"
                "Exact blocker: none\n",
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        _patch_launch_worker_fake_run(monkeypatch, module, fake_run)

        run = module.launch_worker(args, context, root / "state")

        assert run.worker_exit_code == 0
        assert run.accepted is True
        assert run.selected_account_alias == "lane:core"
        assert run.attempted_accounts == ["acct-chatgpt-b", "lane:core"]
        assert run.attempted_models == ["gpt-5.3-codex", "ea-coder-hard-batch"]
        assert calls[0][0] == "codex"
        assert calls[1][:3] == ["codexea", "core", "exec"]
        stderr_text = (root / "state" / "runs" / run.run_id / "worker.stderr.log").read_text(encoding="utf-8")
        assert "escalating account-lane failure to direct fallback" in stderr_text


def test_launch_worker_reads_account_direct_fallback_from_runtime_env(monkeypatch) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_registry(root / "registry.yaml")
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("W2 milestone `21` remains active.\n", encoding="utf-8")
        auth_path = root / "acct-chatgpt-b.auth.json"
        auth_path.write_text('{"access_token":"token"}\n', encoding="utf-8")
        (root / "accounts.yaml").write_text(
            yaml.safe_dump(
                {
                    "account_policy": {"protected_owner_ids": ["the.girscheles", "archon.megalon"]},
                    "accounts": {
                        "acct-chatgpt-b": {
                            "auth_kind": "chatgpt_auth_json",
                            "auth_json_file": str(auth_path),
                            "allowed_models": ["gpt-5.3-codex"],
                            "spark_enabled": False,
                            "health_state": "ready",
                            "owner_id": "the.girscheles",
                        }
                    },
                }
            ),
            encoding="utf-8",
        )
        (root / "runtime.env").write_text(
            "\n".join(
                [
                    "CHUMMER_DESIGN_SUPERVISOR_ACCOUNT_FALLBACK_WORKER_BIN=codexea",
                    "CHUMMER_DESIGN_SUPERVISOR_ACCOUNT_FALLBACK_WORKER_LANE=easy",
                    "CHUMMER_DESIGN_SUPERVISOR_ACCOUNT_FALLBACK_MODELS=ea-gemini-flash",
                    "CHUMMER_DESIGN_SUPERVISOR_ACCOUNT_FALLBACK_LANES=groundwork,repair",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        args = _args(root)
        args.worker_bin = "codex"
        args.worker_lane = ""
        args.worker_model = "gpt-5.3-codex"
        args.account_alias = ["acct-chatgpt-b"]
        context = module.derive_context(args)
        monkeypatch.setattr(module, "_RUNTIME_ENV_CANDIDATES", (root / "runtime.env",))
        monkeypatch.setattr(
            module,
            "_direct_worker_lane_health_snapshot",
            lambda _args, _lanes: {
                "status": "pass",
                "reason": "all checked direct lanes are currently routable",
                "routable_lanes": ["easy", "groundwork", "repair"],
                "unroutable_lanes": [],
                "lanes": {
                    "easy": {"worker_lane": "easy", "profile": "easy", "state": "ready", "routable": True, "reason": ""},
                    "groundwork": {
                        "worker_lane": "groundwork",
                        "profile": "groundwork",
                        "state": "ready",
                        "routable": True,
                        "reason": "",
                    },
                    "repair": {"worker_lane": "repair", "profile": "repair", "state": "ready", "routable": True, "reason": ""},
                },
            },
        )

        calls: list[list[str]] = []

        def fake_run(command, *, input, text, capture_output, cwd, check, env=None, timeout=None):
            calls.append(list(command))
            message_path = Path(command[command.index("-o") + 1])
            if command[0] == "codex":
                return subprocess.CompletedProcess(
                    command,
                    1,
                    stdout="",
                    stderr="ERROR: unexpected status 401 Unauthorized: Incorrect API key provided\n",
                )
            message_path.write_text(
                "What shipped: runtime env fallback kept the shard moving\n"
                "What remains: follow-through\n"
                "Exact blocker: none\n",
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        _patch_launch_worker_fake_run(monkeypatch, module, fake_run)

        run = module.launch_worker(args, context, root / "state")

        assert run.worker_exit_code == 0
        assert run.accepted is True
        assert run.selected_account_alias == "lane:easy"
        assert run.attempted_accounts == ["acct-chatgpt-b", "lane:easy"]
        assert run.attempted_models == ["gpt-5.3-codex", "ea-gemini-flash"]
        assert calls[0][0] == "codex"
        assert calls[1][:3] == ["codexea", "easy", "exec"]


def test_account_restore_probe_due_respects_configured_interval(monkeypatch) -> None:
    module = _load_module()
    now = dt.datetime(2026, 4, 2, 12, 0, tzinfo=dt.timezone.utc)

    monkeypatch.setattr(module, "_RUNTIME_ENV_CANDIDATES", ())
    monkeypatch.delenv("CHUMMER_DESIGN_SUPERVISOR_ACCOUNT_RESTORE_PROBE_SECONDS", raising=False)
    assert module._account_restore_probe_due(None, now=now) is False

    monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_ACCOUNT_RESTORE_PROBE_SECONDS", "300")
    assert module._account_restore_probe_due(None, now=now) is True
    assert module._account_restore_probe_due(now, now=now + dt.timedelta(seconds=299)) is False
    assert module._account_restore_probe_due(now, now=now + dt.timedelta(seconds=300)) is True


def test_launch_worker_skips_saturated_account_when_sibling_shards_already_claim_it(monkeypatch) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_registry(root / "registry.yaml")
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("W2 milestone `21` remains active.\n", encoding="utf-8")
        auth_b = root / "acct-chatgpt-b.auth.json"
        auth_archon = root / "acct-chatgpt-archon.auth.json"
        auth_b.write_text('{"access_token":"token-b"}\n', encoding="utf-8")
        auth_archon.write_text('{"access_token":"token-archon"}\n', encoding="utf-8")
        (root / "accounts.yaml").write_text(
            yaml.safe_dump(
                {
                    "account_policy": {"protected_owner_ids": ["the.girscheles", "archon.megalon"]},
                    "accounts": {
                        "acct-chatgpt-b": {
                            "auth_kind": "chatgpt_auth_json",
                            "auth_json_file": str(auth_b),
                            "allowed_models": ["gpt-5.3-codex"],
                            "spark_enabled": False,
                            "health_state": "ready",
                            "owner_id": "the.girscheles",
                            "max_parallel_runs": 2,
                            "bridge_priority": 0,
                        },
                        "acct-chatgpt-archon": {
                            "auth_kind": "chatgpt_auth_json",
                            "auth_json_file": str(auth_archon),
                            "allowed_models": ["gpt-5.3-codex"],
                            "spark_enabled": False,
                            "health_state": "ready",
                            "owner_id": "archon.megalon",
                            "max_parallel_runs": 8,
                            "bridge_priority": 2,
                        },
                    },
                }
            ),
            encoding="utf-8",
        )
        aggregate_root = root / "state"
        for index in (1, 2):
            shard_root = aggregate_root / f"shard-{index}"
            shard_root.mkdir(parents=True, exist_ok=True)
            module._write_json(
                shard_root / "state.json",
                {
                    "updated_at": "2026-04-02T12:00:00Z",
                    "active_run": {
                        "run_id": f"run-{index}",
                        "selected_account_alias": "acct-chatgpt-b",
                        "frontier_ids": [index],
                        "open_milestone_ids": [],
                    },
                },
            )
        shard_three_root = aggregate_root / "shard-3"
        shard_three_root.mkdir(parents=True, exist_ok=True)

        args = _args(root)
        args.worker_bin = "codex"
        args.worker_lane = ""
        args.worker_model = "gpt-5.3-codex"
        args.account_alias = ["acct-chatgpt-b", "acct-chatgpt-archon"]
        context = module.derive_context(args)

        calls: list[list[str]] = []

        def fake_run(command, *, input, text, capture_output, cwd, check, env=None, timeout=None):
            calls.append(list(command))
            message_path = Path(command[command.index("-o") + 1])
            message_path.write_text(
                "What shipped: sibling shard saturation respected account concurrency\n"
                "What remains: follow-through\n"
                "Exact blocker: none\n",
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        _patch_launch_worker_fake_run(monkeypatch, module, fake_run)

        run = module.launch_worker(args, context, shard_three_root)

        assert run.worker_exit_code == 0
        assert run.accepted is True
        assert run.selected_account_alias == "acct-chatgpt-archon"
        assert run.attempted_accounts == ["acct-chatgpt-archon"]
        stderr_text = (shard_three_root / "runs" / run.run_id / "worker.stderr.log").read_text(encoding="utf-8")
        assert "skip account=acct-chatgpt-b owner=the.girscheles reason=max_parallel_runs 2/2" in stderr_text
        assert calls[0][0] == "codex"


def test_launch_worker_retries_retryable_timeout_on_fallback_direct_lane(monkeypatch) -> None:
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
            message_path = Path(command[command.index("-o") + 1])
            lane = command[1]
            if lane == "core":
                message_path.write_text("Error: upstream_timeout:300s\n", encoding="utf-8")
                return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
            message_path.write_text(
                "What shipped: rescue lane recovered the slice\n"
                "What remains: follow-through\n"
                "Exact blocker: none\n",
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        _patch_launch_worker_fake_run(monkeypatch, module, fake_run)

        run = module.launch_worker(args, context, root / "state")

        assert run.worker_exit_code == 0
        assert run.accepted is True
        assert run.selected_account_alias == "lane:core_rescue"
        assert run.attempted_accounts == ["lane:core", "lane:core_rescue"]
        assert run.attempted_models == ["default", "default"]
        assert calls[0][:3] == ["codexea", "core", "exec"]
        assert calls[1][:3] == ["codexea", "core_rescue", "exec"]
        assert run.shipped == "rescue lane recovered the slice"


def test_launch_worker_retries_supervisor_watchdog_timeout_on_fallback_direct_lane(monkeypatch) -> None:
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
        args.fallback_worker_lane = ["repair"]
        args.worker_timeout_seconds = 5.0
        context = module.derive_context(args)
        monkeypatch.setattr(
            module,
            "_direct_worker_lane_health_snapshot",
            lambda _args, _lanes: {
                "status": "pass",
                "reason": "all checked direct lanes are currently routable",
                "routable_lanes": ["core", "repair"],
                "unroutable_lanes": [],
                "lanes": {
                    "core": {"worker_lane": "core", "profile": "core_batch", "state": "ready", "routable": True, "reason": ""},
                    "repair": {"worker_lane": "repair", "profile": "repair", "state": "ready", "routable": True, "reason": ""},
                },
            },
        )

        calls: list[tuple[list[str], float | None]] = []

        def fake_run(command, *, input, text, capture_output, cwd, check, env=None, timeout=None):
            calls.append((list(command), timeout))
            message_path = Path(command[command.index("-o") + 1])
            lane = command[1]
            if lane == "core":
                raise subprocess.TimeoutExpired(command, timeout=timeout or 5.0, output="", stderr="")
            message_path.write_text(
                "What shipped: watchdog timeout retried on repair\n"
                "What remains: follow-through\n"
                "Exact blocker: none\n",
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        _patch_launch_worker_fake_run(monkeypatch, module, fake_run)

        run = module.launch_worker(args, context, root / "state")

        assert run.worker_exit_code == 0
        assert run.accepted is True
        assert run.selected_account_alias == "lane:repair"
        assert run.attempted_accounts == ["lane:core", "lane:repair"]
        assert calls[0][1] == 5.0
        stderr_text = (root / "state" / "runs" / run.run_id / "worker.stderr.log").read_text(encoding="utf-8")
        assert "worker_timeout:5s" in stderr_text
        assert run.shipped == "watchdog timeout retried on repair"


def test_launch_worker_clears_last_message_between_retry_attempts(monkeypatch) -> None:
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
        args.fallback_worker_lane = ["core_rescue"]
        context = module.derive_context(args)
        monkeypatch.setattr(
            module,
            "_direct_worker_lane_health_snapshot",
            lambda _args, _lanes: {
                "status": "pass",
                "reason": "all checked direct lanes are currently routable",
                "routable_lanes": ["core", "core_rescue"],
                "unroutable_lanes": [],
                "lanes": {
                    "core": {"worker_lane": "core", "profile": "core_batch", "state": "ready", "routable": True, "reason": ""},
                    "core_rescue": {"worker_lane": "core_rescue", "profile": "core_batch", "state": "ready", "routable": True, "reason": ""},
                },
            },
        )

        attempts: list[str] = []

        def fake_run_worker_attempt(
            command,
            *,
            prompt,
            workspace_root,
            worker_env,
            timeout_seconds,
            last_message_path,
            state_root,
            run_id,
            stdout_sink=None,
            stderr_sink=None,
        ):
            lane = command[1]
            attempts.append(lane)
            current_message = last_message_path.read_text(encoding="utf-8") if last_message_path.exists() else ""
            if lane == "core":
                assert current_message == ""
                last_message_path.write_text("Exact blocker: temporary timeout while waiting for worker output\n", encoding="utf-8")
                return subprocess.CompletedProcess(command, 1, stdout="", stderr="upstream_timeout:300s\n")
            assert lane == "core_rescue"
            assert current_message == ""
            last_message_path.write_text(
                "What shipped: retry lane recovered the slice\n"
                "What remains: follow-through\n"
                "Exact blocker: none\n",
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        monkeypatch.setattr(module, "_run_worker_attempt", fake_run_worker_attempt)

        run = module.launch_worker(args, context, root / "state")

        assert attempts == ["core", "core_rescue"]
        assert run.accepted is True
        assert run.selected_account_alias == "lane:core_rescue"
        assert run.shipped == "retry lane recovered the slice"


def test_launch_worker_does_not_retry_after_self_polling_blocker(monkeypatch) -> None:
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
        args.fallback_worker_lane = ["core_rescue"]
        context = module.derive_context(args)
        monkeypatch.setattr(
            module,
            "_direct_worker_lane_health_snapshot",
            lambda _args, _lanes: {
                "status": "pass",
                "reason": "all checked direct lanes are currently routable",
                "routable_lanes": ["core", "core_rescue"],
                "unroutable_lanes": [],
                "lanes": {
                    "core": {"worker_lane": "core", "profile": "core_batch", "state": "ready", "routable": True, "reason": ""},
                    "core_rescue": {"worker_lane": "core_rescue", "profile": "core_batch", "state": "ready", "routable": True, "reason": ""},
                },
            },
        )

        attempts: list[str] = []

        def fake_run_worker_attempt(
            command,
            *,
            prompt,
            workspace_root,
            worker_env,
            timeout_seconds,
            last_message_path,
            state_root,
            run_id,
            stdout_sink=None,
            stderr_sink=None,
        ):
            lane = command[1]
            attempts.append(lane)
            last_message_path.write_text("Exact blocker: worker_self_polling:supervisor_status_loop\n", encoding="utf-8")
            return subprocess.CompletedProcess(
                command,
                125,
                stdout="",
                stderr="Error: worker_self_polling:supervisor_status_loop\n",
            )

        monkeypatch.setattr(module, "_run_worker_attempt", fake_run_worker_attempt)

        run = module.launch_worker(args, context, root / "state")

        assert attempts == ["core"]
        assert run.accepted is False
        assert run.worker_exit_code == 125
        assert run.selected_account_alias == "lane:core"
        assert run.blocker == "worker_self_polling:supervisor_status_loop"


def test_launch_worker_does_not_retry_after_model_output_stall(monkeypatch) -> None:
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
        args.fallback_worker_lane = ["core_rescue"]
        context = module.derive_context(args)
        monkeypatch.setattr(
            module,
            "_direct_worker_lane_health_snapshot",
            lambda _args, _lanes: {
                "status": "pass",
                "reason": "all checked direct lanes are currently routable",
                "routable_lanes": ["core", "core_rescue"],
                "unroutable_lanes": [],
                "lanes": {
                    "core": {"worker_lane": "core", "profile": "core_batch", "state": "ready", "routable": True, "reason": ""},
                    "core_rescue": {"worker_lane": "core_rescue", "profile": "core_batch", "state": "ready", "routable": True, "reason": ""},
                },
            },
        )

        attempts: list[str] = []

        def fake_run_worker_attempt(
            command,
            *,
            prompt,
            workspace_root,
            worker_env,
            timeout_seconds,
            last_message_path,
            state_root,
            run_id,
            stdout_sink=None,
            stderr_sink=None,
        ):
            lane = command[1]
            attempts.append(lane)
            last_message_path.write_text("Error: worker_model_output_stalled:60s\n", encoding="utf-8")
            return subprocess.CompletedProcess(
                command,
                124,
                stdout="",
                stderr=(
                    "status_blocked_inside_worker_run\n"
                    "worker_status_budget_exhausted: status polling budget 2/2 already consumed\n"
                    "Error: worker_model_output_stalled:60s\n"
                ),
            )

        monkeypatch.setattr(module, "_run_worker_attempt", fake_run_worker_attempt)

        run = module.launch_worker(args, context, root / "state")

        assert attempts == ["core"]
        assert run.accepted is False
        assert run.worker_exit_code == 124
        assert run.selected_account_alias == "lane:core"
        assert "worker_model_output_stalled:60s" in run.blocker


def test_launch_worker_does_not_fallback_after_self_polling_from_routed_account(monkeypatch) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_registry(root / "registry.yaml")
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("W2 milestone `21` remains active.\n", encoding="utf-8")
        (root / "accounts.yaml").write_text(
            yaml.safe_dump(
                {
                    "account_policy": {"protected_owner_ids": ["tibor.girschele"]},
                    "accounts": {
                        "acct-ea-core": {
                            "auth_kind": "ea",
                            "owner_id": "tibor.girschele",
                            "allowed_models": ["ea-coder-hard"],
                            "health_state": "ready",
                            "lane": "core",
                            "max_parallel_runs": 1,
                        },
                        "acct-ea-core-2": {
                            "auth_kind": "ea",
                            "owner_id": "tibor.girschele",
                            "allowed_models": ["ea-coder-hard"],
                            "health_state": "ready",
                            "lane": "core",
                            "max_parallel_runs": 1,
                        },
                        "acct-ea-repair": {
                            "auth_kind": "ea",
                            "owner_id": "tibor.girschele",
                            "allowed_models": ["ea-coder-hard"],
                            "health_state": "ready",
                            "lane": "repair",
                            "max_parallel_runs": 1,
                        },
                    },
                }
            ),
            encoding="utf-8",
        )
        args = _args(root)
        args.worker_bin = "/docker/fleet/scripts/codex-shims/codexea"
        args.worker_lane = "core"
        args.worker_model = "ea-coder-hard"
        context = module.derive_context(args)

        monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_PREFER_FULL_EA_LANES", "1")
        monkeypatch.setattr(module, "_prepare_account_environment", lambda _state_root, _workspace_root, _account: {})
        monkeypatch.setattr(
            module,
            "_direct_worker_lane_health_snapshot",
            lambda _args, _lanes: {
                "status": "pass",
                "reason": "all checked direct lanes are currently routable",
                "routable_lanes": ["core", "repair"],
                "unroutable_lanes": [],
                "lanes": {
                    "core": {"worker_lane": "core", "profile": "core_batch", "state": "ready", "routable": True, "reason": ""},
                    "repair": {"worker_lane": "repair", "profile": "repair_batch", "state": "ready", "routable": True, "reason": ""},
                },
            },
        )

        def fake_run_worker_attempt(
            command,
            *,
            prompt,
            workspace_root,
            worker_env,
            timeout_seconds,
            last_message_path,
            state_root,
            run_id,
            stdout_sink=None,
            stderr_sink=None,
        ):
            last_message_path.write_text("Exact blocker: worker_self_polling:supervisor_status_loop\n", encoding="utf-8")
            return subprocess.CompletedProcess(
                command,
                125,
                stdout="",
                stderr="Error: worker_self_polling:supervisor_status_loop\n",
            )

        monkeypatch.setattr(module, "_run_worker_attempt", fake_run_worker_attempt)

        run = module.launch_worker(args, context, root / "state")

        assert run.accepted is False
        assert run.worker_exit_code == 125
        assert run.attempted_accounts == ["acct-ea-core"]
        assert run.selected_account_alias == "acct-ea-core"
        assert run.blocker == "worker_self_polling:supervisor_status_loop"


def test_launch_worker_does_not_fallback_after_model_output_stall_from_routed_account(monkeypatch) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_registry(root / "registry.yaml")
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("W2 milestone `21` remains active.\n", encoding="utf-8")
        (root / "accounts.yaml").write_text(
            yaml.safe_dump(
                {
                    "account_policy": {"protected_owner_ids": ["tibor.girschele"]},
                    "accounts": {
                        "acct-ea-core": {
                            "auth_kind": "ea",
                            "owner_id": "tibor.girschele",
                            "allowed_models": ["ea-coder-hard"],
                            "health_state": "ready",
                            "lane": "core",
                            "max_parallel_runs": 1,
                        },
                        "acct-ea-core-2": {
                            "auth_kind": "ea",
                            "owner_id": "tibor.girschele",
                            "allowed_models": ["ea-coder-hard"],
                            "health_state": "ready",
                            "lane": "core",
                            "max_parallel_runs": 1,
                        },
                        "acct-ea-repair": {
                            "auth_kind": "ea",
                            "owner_id": "tibor.girschele",
                            "allowed_models": ["ea-coder-hard"],
                            "health_state": "ready",
                            "lane": "repair",
                            "max_parallel_runs": 1,
                        },
                    },
                }
            ),
            encoding="utf-8",
        )
        args = _args(root)
        args.worker_bin = "/docker/fleet/scripts/codex-shims/codexea"
        args.worker_lane = "core"
        args.worker_model = "ea-coder-hard"
        context = module.derive_context(args)

        monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_PREFER_FULL_EA_LANES", "1")
        monkeypatch.setattr(module, "_prepare_account_environment", lambda _state_root, _workspace_root, _account: {})
        monkeypatch.setattr(
            module,
            "_direct_worker_lane_health_snapshot",
            lambda _args, _lanes: {
                "status": "pass",
                "reason": "all checked direct lanes are currently routable",
                "routable_lanes": ["core", "repair"],
                "unroutable_lanes": [],
                "lanes": {
                    "core": {"worker_lane": "core", "profile": "core_batch", "state": "ready", "routable": True, "reason": ""},
                    "repair": {"worker_lane": "repair", "profile": "repair_batch", "state": "ready", "routable": True, "reason": ""},
                },
            },
        )

        def fake_run_worker_attempt(
            command,
            *,
            prompt,
            workspace_root,
            worker_env,
            timeout_seconds,
            last_message_path,
            state_root,
            run_id,
            stdout_sink=None,
            stderr_sink=None,
        ):
            last_message_path.write_text("Error: worker_model_output_stalled:60s\n", encoding="utf-8")
            return subprocess.CompletedProcess(
                command,
                124,
                stdout="",
                stderr=(
                    "status_blocked_inside_worker_run\n"
                    "worker_status_budget_exhausted: status polling budget 2/2 already consumed\n"
                    "Error: worker_model_output_stalled:60s\n"
                ),
            )

        monkeypatch.setattr(module, "_run_worker_attempt", fake_run_worker_attempt)

        run = module.launch_worker(args, context, root / "state")

        assert run.accepted is False
        assert run.worker_exit_code == 124
        assert run.attempted_accounts == ["acct-ea-core"]
        assert run.selected_account_alias == "acct-ea-core"
        assert "worker_model_output_stalled:60s" in run.blocker


def test_launch_worker_raises_direct_codexea_watchdog_to_workspace_stream_budget(monkeypatch) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_registry(root / "registry.yaml")
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("W2 milestone `21` remains active.\n", encoding="utf-8")
        (root / "runtime.env").write_text(
            "\n".join(
                [
                    "CHUMMER_DESIGN_SUPERVISOR_STREAM_IDLE_TIMEOUT_MS=900000",
                    "CHUMMER_DESIGN_SUPERVISOR_STREAM_MAX_RETRIES=8",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        args = _args(root)
        args.worker_bin = "codexea"
        args.worker_lane = "core"
        args.worker_model = ""
        args.worker_timeout_seconds = 1200.0
        context = module.derive_context(args)
        monkeypatch.setattr(
            module,
            "_direct_worker_lane_health_snapshot",
            lambda _args, _lanes: {
                "status": "pass",
                "reason": "all checked direct lanes are currently routable",
                "routable_lanes": ["core"],
                "unroutable_lanes": [],
                "lanes": {
                    "core": {"worker_lane": "core", "profile": "core_batch", "state": "ready", "routable": True, "reason": ""},
                },
            },
        )

        calls: list[tuple[list[str], float | None]] = []

        def fake_run(command, *, input, text, capture_output, cwd, check, env=None, timeout=None):
            calls.append((list(command), timeout))
            message_path = Path(command[command.index("-o") + 1])
            message_path.write_text(
                "What shipped: core lane stayed on the long watchdog\nWhat remains: follow-through\nExact blocker: none\n",
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        _patch_launch_worker_fake_run(monkeypatch, module, fake_run)

        run = module.launch_worker(args, context, root / "state")

        assert run.worker_exit_code == 0
        assert run.accepted is True
        assert calls[0][1] == 9000.0
        stderr_text = (root / "state" / "runs" / run.run_id / "worker.stderr.log").read_text(encoding="utf-8")
        assert "raised direct worker watchdog from 1200s to 9000s" in stderr_text


@pytest.mark.filterwarnings("error::pytest.PytestUnhandledThreadExceptionWarning")
def test_run_worker_attempt_ignores_value_error_when_stream_is_closed_mid_read(monkeypatch) -> None:
    module = _load_module()

    class _FakeInput:
        def __init__(self) -> None:
            self.closed = False
            self.buffer = ""

        def write(self, value: str) -> None:
            self.buffer += value

        def close(self) -> None:
            self.closed = True

    class _SlowCloseStream:
        def __init__(self, first_line: str) -> None:
            self._first_line = first_line
            self._reads = 0
            self._closed = False

        def readline(self) -> str:
            if self._reads == 0:
                self._reads += 1
                return self._first_line
            import time as _time

            _time.sleep(0.05)
            if self._closed:
                raise ValueError("I/O operation on closed file.")
            return ""

        def close(self) -> None:
            self._closed = True

    class _FakeProcess:
        def __init__(self) -> None:
            self.pid = 43210
            self.returncode = 0
            self.stdin = _FakeInput()
            self.stdout = _SlowCloseStream("stdout line\n")
            self.stderr = _SlowCloseStream("")

        def wait(self, timeout=None) -> int:
            self.returncode = 0
            return 0

    monkeypatch.setattr(module.subprocess, "Popen", lambda *args, **kwargs: _FakeProcess())
    monkeypatch.setattr(module, "_runtime_handoff_heartbeat_seconds", lambda: 0.0)

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        completed = module._run_worker_attempt(
            ["codexea", "core", "exec"],
            prompt="hello\n",
            workspace_root=root,
            worker_env={},
            timeout_seconds=0.0,
            last_message_path=root / "last_message.txt",
            state_root=root / "state",
            run_id="run-1",
            stdout_sink=io.StringIO(),
            stderr_sink=io.StringIO(),
        )

        assert completed.returncode == 0
        assert completed.stdout == "stdout line\n"
        assert completed.stderr == ""


def test_run_worker_attempt_allows_single_supervisor_status_command(monkeypatch) -> None:
    module = _load_module()

    class _FakeInput:
        def __init__(self) -> None:
            self.closed = False
            self.buffer = ""

        def write(self, value: str) -> None:
            self.buffer += value

        def close(self) -> None:
            self.closed = True

    class _ReplayStream:
        def __init__(self, lines: list[str]) -> None:
            self._lines = list(lines)
            self._closed = False

        def readline(self) -> str:
            if self._lines:
                return self._lines.pop(0)
            return ""

        def close(self) -> None:
            self._closed = True

    class _FakeProcess:
        def __init__(self) -> None:
            self.pid = 43211
            self.returncode = 0
            self.stdin = _FakeInput()
            self.stdout = _ReplayStream([])
            self.stderr = _ReplayStream(
                [
                    "exec\n",
                    '/usr/bin/bash -lc "python3 /docker/fleet/scripts/chummer_design_supervisor.py status --state-root /docker/fleet/state/chummer_design_supervisor --json"\n',
                ]
            )

        def wait(self, timeout=None) -> int:
            import time as _time

            _time.sleep(0.05)
            return int(self.returncode or 0)

        def kill(self) -> None:
            self.returncode = -9

    monkeypatch.setattr(module.subprocess, "Popen", lambda *args, **kwargs: _FakeProcess())
    monkeypatch.setattr(module, "_runtime_handoff_heartbeat_seconds", lambda: 0.0)
    monkeypatch.setattr(module.os, "killpg", lambda pid, sig: (_ for _ in ()).throw(ProcessLookupError()))

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        last_message_path = root / "last_message.txt"
        completed = module._run_worker_attempt(
            ["codexea", "core", "exec"],
            prompt="hello\n",
            workspace_root=root,
            worker_env={},
            timeout_seconds=0.0,
            last_message_path=last_message_path,
            state_root=root / "state",
            run_id="run-2",
            stdout_sink=io.StringIO(),
            stderr_sink=io.StringIO(),
        )

        assert completed.returncode == 0
        assert "worker_self_polling:supervisor_status_loop" not in completed.stderr
        assert not last_message_path.exists()


def test_run_worker_attempt_allows_repeated_successful_supervisor_status_commands(monkeypatch) -> None:
    module = _load_module()

    class _FakeInput:
        def __init__(self) -> None:
            self.closed = False
            self.buffer = ""

        def write(self, value: str) -> None:
            self.buffer += value

        def close(self) -> None:
            self.closed = True

    class _ReplayStream:
        def __init__(self, lines: list[str]) -> None:
            self._lines = list(lines)
            self._closed = False

        def readline(self) -> str:
            if self._lines:
                return self._lines.pop(0)
            return ""

        def close(self) -> None:
            self._closed = True

    class _FakeProcess:
        def __init__(self) -> None:
            self.pid = 43212
            self.returncode = 0
            self.stdin = _FakeInput()
            self.stdout = _ReplayStream([])
            self.stderr = _ReplayStream(
                [
                    "exec\n",
                    '/usr/bin/bash -lc "python3 /docker/fleet/scripts/chummer_design_supervisor.py status --state-root /docker/fleet/state/chummer_design_supervisor --json"\n',
                    "exec\n",
                    '/usr/bin/bash -lc "python3 /docker/fleet/scripts/chummer_design_supervisor.py status --state-root /docker/fleet/state/chummer_design_supervisor --json"\n',
                    "exec\n",
                    '/usr/bin/bash -lc "python3 /docker/fleet/scripts/chummer_design_supervisor.py status --state-root /docker/fleet/state/chummer_design_supervisor --json"\n',
                ]
            )

        def wait(self, timeout=None) -> int:
            import time as _time

            _time.sleep(0.05)
            return int(self.returncode or 0)

        def kill(self) -> None:
            self.returncode = -9

    monkeypatch.setattr(module.subprocess, "Popen", lambda *args, **kwargs: _FakeProcess())
    monkeypatch.setattr(module, "_runtime_handoff_heartbeat_seconds", lambda: 0.0)
    monkeypatch.setattr(module.os, "killpg", lambda pid, sig: (_ for _ in ()).throw(ProcessLookupError()))

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        last_message_path = root / "last_message.txt"
        completed = module._run_worker_attempt(
            ["codexea", "core", "exec"],
            prompt="hello\n",
            workspace_root=root,
            worker_env={},
            timeout_seconds=0.0,
            last_message_path=last_message_path,
            state_root=root / "state",
            run_id="run-2b",
            stdout_sink=io.StringIO(),
            stderr_sink=io.StringIO(),
        )

        assert completed.returncode == 0
        assert "worker_self_polling:supervisor_status_loop" not in completed.stderr
        assert not last_message_path.exists()


def test_run_worker_attempt_allows_one_duplicate_supervisor_status_command(monkeypatch) -> None:
    module = _load_module()

    class _FakeInput:
        def __init__(self) -> None:
            self.closed = False
            self.buffer = ""

        def write(self, value: str) -> None:
            self.buffer += value

        def close(self) -> None:
            self.closed = True

    class _ReplayStream:
        def __init__(self, lines: list[str]) -> None:
            self._lines = list(lines)
            self._closed = False

        def readline(self) -> str:
            if self._lines:
                return self._lines.pop(0)
            return ""

        def close(self) -> None:
            self._closed = True

    class _FakeProcess:
        def __init__(self) -> None:
            self.pid = 43213
            self.returncode = 0
            self.stdin = _FakeInput()
            self.stdout = _ReplayStream([])
            self.stderr = _ReplayStream(
                [
                    "exec\n",
                    '/usr/bin/bash -lc "python3 /docker/fleet/scripts/chummer_design_supervisor.py status --state-root /docker/fleet/state/chummer_design_supervisor --json"\n',
                    "exec\n",
                    '/usr/bin/bash -lc "python3 /docker/fleet/scripts/chummer_design_supervisor.py status --state-root /docker/fleet/state/chummer_design_supervisor --json"\n',
                ]
            )

        def wait(self, timeout=None) -> int:
            import time as _time

            _time.sleep(0.05)
            return int(self.returncode or 0)

        def kill(self) -> None:
            self.returncode = -9

    monkeypatch.setattr(module.subprocess, "Popen", lambda *args, **kwargs: _FakeProcess())
    monkeypatch.setattr(module, "_runtime_handoff_heartbeat_seconds", lambda: 0.0)
    monkeypatch.setattr(module.os, "killpg", lambda pid, sig: (_ for _ in ()).throw(ProcessLookupError()))

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        last_message_path = root / "last_message.txt"
        completed = module._run_worker_attempt(
            ["codexea", "core", "exec"],
            prompt="hello\n",
            workspace_root=root,
            worker_env={},
            timeout_seconds=0.0,
            last_message_path=last_message_path,
            state_root=root / "state",
            run_id="run-2c",
            stdout_sink=io.StringIO(),
            stderr_sink=io.StringIO(),
        )

        assert completed.returncode == 0
        assert "worker_self_polling:supervisor_status_loop" not in completed.stderr
        assert not last_message_path.exists()


def test_run_worker_attempt_trips_on_repeated_blocked_status_loops(monkeypatch) -> None:
    module = _load_module()

    class _FakeInput:
        def __init__(self) -> None:
            self.closed = False
            self.buffer = ""

        def write(self, value: str) -> None:
            self.buffer += value

        def close(self) -> None:
            self.closed = True

    class _ReplayStream:
        def __init__(self, lines: list[str]) -> None:
            self._lines = list(lines)
            self._closed = False

        def readline(self) -> str:
            if self._lines:
                return self._lines.pop(0)
            return ""

        def close(self) -> None:
            self._closed = True

    class _FakeProcess:
        def __init__(self) -> None:
            self.pid = 43214
            self.returncode = 0
            self.stdin = _FakeInput()
            self.stdout = _ReplayStream([])
            self.stderr = _ReplayStream(
                [
                    "exec\n",
                    '{"status":"polling_disabled"}\n',
                    "status_blocked_inside_worker_run\n",
                    "exec\n",
                    '{"status":"polling_disabled"}\n',
                    "status_blocked_inside_worker_run\n",
                    "exec\n",
                    '{"status":"polling_disabled"}\n',
                    "status_blocked_inside_worker_run\n",
                ]
            )

        def wait(self, timeout=None) -> int:
            import time as _time

            _time.sleep(0.05)
            return int(self.returncode or 0)

        def kill(self) -> None:
            self.returncode = -9

    monkeypatch.setattr(module.subprocess, "Popen", lambda *args, **kwargs: _FakeProcess())
    monkeypatch.setattr(module, "_runtime_handoff_heartbeat_seconds", lambda: 0.0)
    monkeypatch.setattr(module.os, "killpg", lambda pid, sig: (_ for _ in ()).throw(ProcessLookupError()))
    monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_SELF_POLL_BLOCKED_TRIP_THRESHOLD", "1")
    monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_TASK_LOCAL_STATUS_LOOP_GRACE_SECONDS", "0")

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        last_message_path = root / "last_message.txt"
        completed = module._run_worker_attempt(
            ["codexea", "core", "exec"],
            prompt="hello\n",
            workspace_root=root,
            worker_env={},
            timeout_seconds=0.0,
            last_message_path=last_message_path,
            state_root=root / "state",
            run_id="run-2d",
            stdout_sink=io.StringIO(),
            stderr_sink=io.StringIO(),
        )

        assert completed.returncode == 125
        assert "worker_self_polling:supervisor_status_loop" in completed.stderr
        assert last_message_path.read_text(encoding="utf-8").strip() == "Exact blocker: worker_self_polling:supervisor_status_loop"


def test_run_worker_attempt_does_not_trip_on_blocked_status_loops_by_default(monkeypatch) -> None:
    module = _load_module()

    class _FakeInput:
        def __init__(self) -> None:
            self.closed = False
            self.buffer = ""

        def write(self, value: str) -> None:
            self.buffer += value

        def close(self) -> None:
            self.closed = True

    class _ReplayStream:
        def __init__(self, lines: list[str]) -> None:
            self._lines = list(lines)
            self._closed = False

        def readline(self) -> str:
            if self._lines:
                return self._lines.pop(0)
            return ""

        def close(self) -> None:
            self._closed = True

    class _FakeProcess:
        def __init__(self) -> None:
            self.pid = 43215
            self.returncode = 0
            self.stdin = _FakeInput()
            self.stdout = _ReplayStream([])
            self.stderr = _ReplayStream(
                [
                    "exec\n",
                    '{"status":"polling_disabled"}\n',
                    "status_blocked_inside_worker_run\n",
                    "exec\n",
                    '{"status":"polling_disabled"}\n',
                    "status_blocked_inside_worker_run\n",
                    "exec\n",
                    '{"status":"polling_disabled"}\n',
                    "status_blocked_inside_worker_run\n",
                ]
            )

        def wait(self, timeout=None) -> int:
            import time as _time

            _time.sleep(0.05)
            return int(self.returncode or 0)

        def kill(self) -> None:
            self.returncode = -9

    monkeypatch.delenv("CHUMMER_DESIGN_SUPERVISOR_SELF_POLL_BLOCKED_TRIP_THRESHOLD", raising=False)
    monkeypatch.setattr(module.subprocess, "Popen", lambda *args, **kwargs: _FakeProcess())
    monkeypatch.setattr(module, "_runtime_handoff_heartbeat_seconds", lambda: 0.0)
    monkeypatch.setattr(module.os, "killpg", lambda pid, sig: (_ for _ in ()).throw(ProcessLookupError()))

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        last_message_path = root / "last_message.txt"
        completed = module._run_worker_attempt(
            ["codexea", "core", "exec"],
            prompt="hello\n",
            workspace_root=root,
            worker_env={},
            timeout_seconds=0.0,
            last_message_path=last_message_path,
            state_root=root / "state",
            run_id="run-2e",
            stdout_sink=io.StringIO(),
            stderr_sink=io.StringIO(),
        )

        assert completed.returncode == 0
        assert "worker_self_polling:supervisor_status_loop" not in completed.stderr
        assert not last_message_path.exists()


def test_run_worker_attempt_marks_waiting_for_model_output_without_streaming(monkeypatch) -> None:
    module = _load_module()

    class _FakeInput:
        def __init__(self) -> None:
            self.closed = False
            self.buffer = ""

        def write(self, value: str) -> None:
            self.buffer += value

        def close(self) -> None:
            self.closed = True

    class _ReplayStream:
        def __init__(self, lines: list[str]) -> None:
            self._lines = list(lines)
            self._closed = False

        def readline(self) -> str:
            if self._lines:
                return self._lines.pop(0)
            return ""

        def close(self) -> None:
            self._closed = True

    class _FakeProcess:
        def __init__(self) -> None:
            self.pid = 43215
            self.returncode = 0
            self.stdin = _FakeInput()
            self.stdout = _ReplayStream([])
            self.stderr = _ReplayStream(
                [
                    "[fleet-supervisor] attempt 1/20 account=acct-ea-core-01 owner= model=ea-coder-hard\n",
                    "Trace: lane=core provider=ea model=ea-coder-hard-batch mode=responses next=start_exec_session\n",
                    "Trace: lane=core waiting for model output (0s)\n",
                    "OpenAI Codex v0.118.0 (research preview)\n",
                    "--------\n",
                    "workdir: /docker/fleet\n",
                    "provider: ea\n",
                    "user\n",
                    "Run the flagship full-product delivery pass for Chummer.\n",
                    "warning: Codex could not find system bubblewrap on PATH. Please install bubblewrap with your package manager. Codex will use the vendored bubblewrap in the meantime.\n",
                ]
            )

        def wait(self, timeout=None) -> int:
            return int(self.returncode or 0)

        def kill(self) -> None:
            self.returncode = -9

    monkeypatch.setattr(module.subprocess, "Popen", lambda *args, **kwargs: _FakeProcess())
    monkeypatch.setattr(module, "_runtime_handoff_heartbeat_seconds", lambda: 0.0)

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        state_root = root / "state"
        module._write_json(
            state_root / "state.json",
            {
                "active_run": {
                    "run_id": "run-waiting",
                    "started_at": "2026-04-14T11:08:45Z",
                }
            },
        )
        completed = module._run_worker_attempt(
            ["codexea", "core", "exec"],
            prompt="Run the flagship full-product delivery pass for Chummer.\n",
            workspace_root=root,
            worker_env={},
            timeout_seconds=0.0,
            last_message_path=root / "last_message.txt",
            state_root=state_root,
            run_id="run-waiting",
            stdout_sink=io.StringIO(),
            stderr_sink=io.StringIO(),
        )

        payload = module._read_state(state_root / "state.json")

        assert completed.returncode == 0
        assert payload["active_run_progress_state"] in {"waiting_for_model_output", "stream_connected_waiting"}
        assert payload.get("active_run_worker_last_output_at") in (None, "")
        assert payload.get("worker_last_output_at") in (None, "")


def test_run_worker_attempt_ignores_supervisor_status_probe_output_as_progress(monkeypatch) -> None:
    module = _load_module()

    class _FakeInput:
        def __init__(self) -> None:
            self.closed = False
            self.buffer = ""

        def write(self, value: str) -> None:
            self.buffer += value

        def close(self) -> None:
            self.closed = True

    class _ReplayStream:
        def __init__(self, lines: list[str]) -> None:
            self._lines = list(lines)
            self._closed = False

        def readline(self) -> str:
            if self._lines:
                return self._lines.pop(0)
            return ""

        def close(self) -> None:
            self._closed = True

    class _FakeProcess:
        def __init__(self) -> None:
            self.pid = 43218
            self.returncode = 0
            self.stdin = _FakeInput()
            self.stdout = _ReplayStream([])
            self.stderr = _ReplayStream(
                [
                    "Trace: lane=core provider=ea model=ea-coder-hard-batch mode=responses next=start_exec_session\n",
                    "Trace: lane=core waiting for model output (0s)\n",
                    "OpenAI Codex v0.118.0 (research preview)\n",
                    "--------\n",
                    "workdir: /docker/fleet\n",
                    "provider: ea\n",
                    "exec\n",
                    '/usr/bin/bash -lc "python3 /docker/fleet/scripts/chummer_design_supervisor.py status --state-root /docker/fleet/state/chummer_design_supervisor --json | python3 -c ..."\n',
                    " succeeded in 453ms:\n",
                    '{"active_runs_count":null,"remaining_open_milestones":1,"remaining_not_started_milestones":1,"remaining_in_progress_milestones":0,"eta_human":"11h-1.1d","summary":"Milestone remains open."}\n',
                ]
            )

        def wait(self, timeout=None) -> int:
            return int(self.returncode or 0)

        def kill(self) -> None:
            self.returncode = -9

    monkeypatch.setattr(module.subprocess, "Popen", lambda *args, **kwargs: _FakeProcess())
    monkeypatch.setattr(module, "_runtime_handoff_heartbeat_seconds", lambda: 0.0)

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        state_root = root / "state"
        module._write_json(
            state_root / "state.json",
            {
                "active_run": {
                    "run_id": "run-status-probe",
                    "started_at": "2026-04-14T11:08:45Z",
                }
            },
        )
        completed = module._run_worker_attempt(
            ["codexea", "core", "exec"],
            prompt="Run the flagship full-product delivery pass for Chummer.\n",
            workspace_root=root,
            worker_env={},
            timeout_seconds=0.0,
            last_message_path=root / "last_message.txt",
            state_root=state_root,
            run_id="run-status-probe",
            stdout_sink=io.StringIO(),
            stderr_sink=io.StringIO(),
        )

        payload = module._read_state(state_root / "state.json")

        assert completed.returncode == 0
        assert payload["active_run_progress_state"] in {"waiting_for_model_output", "stream_connected_waiting"}
        assert payload.get("active_run_worker_last_output_at") in (None, "")
        assert payload.get("worker_last_output_at") in (None, "")


def test_run_worker_attempt_ignores_blocked_status_traceback_as_progress(monkeypatch) -> None:
    module = _load_module()

    class _FakeInput:
        def __init__(self) -> None:
            self.closed = False
            self.buffer = ""

        def write(self, value: str) -> None:
            self.buffer += value

        def close(self) -> None:
            self.closed = True

    class _ReplayStream:
        def __init__(self, lines: list[str]) -> None:
            self._lines = list(lines)
            self._closed = False

        def readline(self) -> str:
            if self._lines:
                return self._lines.pop(0)
            return ""

        def close(self) -> None:
            self._closed = True

    class _FakeProcess:
        def __init__(self) -> None:
            self.pid = 43219
            self.returncode = 0
            self.stdin = _FakeInput()
            self.stdout = _ReplayStream([])
            self.stderr = _ReplayStream(
                [
                    "Trace: lane=core waiting for model output (0s)\n",
                    "exec\n",
                    '/usr/bin/bash -lc "python3 /docker/fleet/scripts/chummer_design_supervisor.py status --state-root /docker/fleet/state/chummer_design_supervisor --json | python3 -c ..."\n',
                    " exited 1 in 482ms:\n",
                    "status_blocked_inside_worker_run\n",
                    "worker_status_budget_exhausted: status polling budget 2/2 already consumed for active run run-status-blocked\n",
                    "read the task-local prompt, shard runtime handoff, and frontier artifacts directly instead of polling supervisor status from inside the active worker run.\n",
                    "run_id: run-status-blocked\n",
                    "prompt_path: /tmp/run-status-blocked/prompt.txt\n",
                    "runtime_handoff_path: /tmp/state/ACTIVE_RUN_HANDOFF.generated.md\n",
                    "flagship_product_readiness_path: /tmp/FLAGSHIP_PRODUCT_READINESS.generated.json\n",
                    "Traceback (most recent call last):\n",
                    '  File "<string>", line 1, in <module>\n',
                    "    return loads(fp.read(),\n",
                    "           ^^^^^^^^^^^^^^^^\n",
                    "    obj, end = self.raw_decode(s, idx=_w(s, 0).end())\n",
                    "    raise JSONDecodeError(\"Expecting value\", s, err.value) from None\n",
                    "json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)\n",
                ]
            )

        def wait(self, timeout=None) -> int:
            return int(self.returncode or 0)

        def kill(self) -> None:
            self.returncode = -9

    monkeypatch.setattr(module.subprocess, "Popen", lambda *args, **kwargs: _FakeProcess())
    monkeypatch.setattr(module, "_runtime_handoff_heartbeat_seconds", lambda: 0.0)

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        state_root = root / "state"
        module._write_json(
            state_root / "state.json",
            {
                "active_run": {
                    "run_id": "run-status-blocked",
                    "started_at": "2026-04-14T11:08:45Z",
                }
            },
        )
        completed = module._run_worker_attempt(
            ["codexea", "core", "exec"],
            prompt="Run the flagship full-product delivery pass for Chummer.\n",
            workspace_root=root,
            worker_env={},
            timeout_seconds=0.0,
            last_message_path=root / "last_message.txt",
            state_root=state_root,
            run_id="run-status-blocked",
            stdout_sink=io.StringIO(),
            stderr_sink=io.StringIO(),
        )

        payload = module._read_state(state_root / "state.json")

        assert completed.returncode == 0
        assert payload["active_run_progress_state"] in {"waiting_for_model_output", "stream_connected_waiting"}
        assert payload.get("active_run_worker_last_output_at") in (None, "")
        assert payload.get("worker_last_output_at") in (None, "")


def test_run_worker_attempt_times_out_when_only_model_wait_traces_arrive(monkeypatch) -> None:
    module = _load_module()

    class _FakeInput:
        def __init__(self) -> None:
            self.closed = False
            self.buffer = ""

        def write(self, value: str) -> None:
            self.buffer += value

        def close(self) -> None:
            self.closed = True

    class _ReplayStream:
        def __init__(self, lines: list[str]) -> None:
            self._lines = list(lines)
            self._closed = False

        def readline(self) -> str:
            if self._lines:
                return self._lines.pop(0)
            return ""

        def close(self) -> None:
            self._closed = True

    class _FakeProcess:
        def __init__(self) -> None:
            self.pid = 43216
            self.returncode = 0
            self.stdin = _FakeInput()
            self.stdout = _ReplayStream([])
            self.stderr = _ReplayStream(
                [
                    "Trace: lane=core provider=ea model=ea-coder-hard-batch mode=responses next=start_exec_session\n",
                    "Trace: lane=core waiting for model output (0s)\n",
                ]
            )

        def wait(self, timeout=None) -> int:
            import time as _time

            _time.sleep(0.05)
            if self.returncode not in (None, 0):
                return int(self.returncode or 0)
            raise subprocess.TimeoutExpired(["codexea", "core", "exec"], timeout=timeout or 0.05)

        def kill(self) -> None:
            self.returncode = -9

    monkeypatch.setattr(module.subprocess, "Popen", lambda *args, **kwargs: _FakeProcess())
    monkeypatch.setattr(module, "_runtime_handoff_heartbeat_seconds", lambda: 0.0)
    monkeypatch.setattr(module, "_worker_model_output_stall_seconds", lambda workspace_root, timeout_seconds: 999.0)
    monkeypatch.setattr(module.os, "killpg", lambda pid, sig: (_ for _ in ()).throw(ProcessLookupError()))

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        state_root = root / "state"
        module._write_json(
            state_root / "state.json",
            {
                "active_run": {
                    "run_id": "run-stalled",
                    "started_at": "2026-04-14T11:08:45Z",
                }
            },
        )
        last_message_path = root / "last_message.txt"
        completed = module._run_worker_attempt(
            ["codexea", "core", "exec"],
            prompt="Run the flagship full-product delivery pass for Chummer.\n",
            workspace_root=root,
            worker_env={},
            timeout_seconds=0.0,
            last_message_path=last_message_path,
            state_root=state_root,
            run_id="run-stalled",
            stdout_sink=io.StringIO(),
            stderr_sink=io.StringIO(),
        )

        payload = module._read_state(state_root / "state.json")

        assert completed.returncode == 124
        assert "worker_model_output_stalled:0.01s" in completed.stderr
        assert last_message_path.read_text(encoding="utf-8").strip() == "Error: worker_model_output_stalled:0.01s"
        assert payload["active_run_progress_state"] in {"waiting_for_model_output", "stream_connected_waiting"}
        assert module._retryable_worker_error(completed.stderr) is True


def test_run_worker_attempt_recycles_repeated_blocked_status_helper_loop(monkeypatch) -> None:
    module = _load_module()

    class _FakeInput:
        def __init__(self) -> None:
            self.closed = False
            self.buffer = ""

        def write(self, value: str) -> None:
            self.buffer += value

        def close(self) -> None:
            self.closed = True

    class _ReplayStream:
        def __init__(self, lines: list[str]) -> None:
            self._lines = list(lines)
            self._closed = False

        def readline(self) -> str:
            if self._lines:
                return self._lines.pop(0)
            return ""

        def close(self) -> None:
            self._closed = True

    class _FakeProcess:
        def __init__(self) -> None:
            self.pid = 43221
            self.returncode = 0
            self.stdin = _FakeInput()
            self.stdout = _ReplayStream([])
            self.stderr = _ReplayStream(
                [
                    "Trace: lane=core waiting for model output (0s)\n",
                    "exec\n",
                    '/usr/bin/bash -lc "python3 /docker/fleet/scripts/chummer_design_supervisor.py status --state-root /docker/fleet/state/chummer_design_supervisor --json | python3 -c ..."\n',
                    " succeeded in 482ms:\n",
                    "status_blocked_inside_worker_run\n",
                    "worker_status_budget_exhausted: status polling budget 1/1 already consumed for active run run-status-loop\n",
                    '{"active_runs_count":1,"remaining_open_milestones":1,"remaining_not_started_milestones":1,"remaining_in_progress_milestones":0,"eta_human":"tracked","summary":"1 open milestone remains in the current shard slice."}\n',
                    "exec\n",
                    '/usr/bin/bash -lc "python3 /docker/fleet/scripts/chummer_design_supervisor.py status --state-root /docker/fleet/state/chummer_design_supervisor --json | python3 -c ..."\n',
                    " succeeded in 401ms:\n",
                    "status_blocked_inside_worker_run\n",
                    "worker_status_budget_exhausted: status polling budget 1/1 already consumed for active run run-status-loop\n",
                    '{"active_runs_count":1,"remaining_open_milestones":1,"remaining_not_started_milestones":1,"remaining_in_progress_milestones":0,"eta_human":"tracked","summary":"1 open milestone remains in the current shard slice."}\n',
                ]
            )

        def wait(self, timeout=None) -> int:
            import time as _time

            _time.sleep(0.05)
            if self.returncode not in (None, 0):
                return int(self.returncode or 0)
            raise subprocess.TimeoutExpired(["codexea", "core", "exec"], timeout=timeout or 0.05)

        def kill(self) -> None:
            self.returncode = -9

    monkeypatch.setattr(module.subprocess, "Popen", lambda *args, **kwargs: _FakeProcess())
    monkeypatch.setattr(module, "_runtime_handoff_heartbeat_seconds", lambda: 0.0)
    monkeypatch.setattr(module, "_worker_model_output_stall_seconds", lambda workspace_root, timeout_seconds: 999.0)
    monkeypatch.setattr(module.os, "killpg", lambda pid, sig: (_ for _ in ()).throw(ProcessLookupError()))

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        state_root = root / "state"
        module._write_json(
            state_root / "state.json",
            {
                "active_run": {
                    "run_id": "run-status-loop",
                    "started_at": "2026-04-14T11:08:45Z",
                }
            },
        )
        last_message_path = root / "last_message.txt"
        completed = module._run_worker_attempt(
            ["codexea", "core", "exec"],
            prompt="Run the flagship full-product delivery pass for Chummer.\n",
            workspace_root=root,
            worker_env={},
            timeout_seconds=0.1,
            last_message_path=last_message_path,
            state_root=state_root,
            run_id="run-status-loop",
            stdout_sink=io.StringIO(),
            stderr_sink=io.StringIO(),
        )

        payload = module._read_state(state_root / "state.json")

        assert completed.returncode == 124
        assert "worker_timeout:0.1s" in completed.stderr
        assert "worker_status_helper_loop" not in completed.stderr
        assert last_message_path.read_text(encoding="utf-8").strip() == "Error: worker_timeout:0.1s"
        assert payload["active_run_progress_state"] in {"waiting_for_model_output", "stream_connected_waiting"}
        assert module._retryable_worker_error(completed.stderr) is True


def test_run_worker_attempt_recycles_repeated_task_local_status_reads_without_blocked_marker(monkeypatch) -> None:
    module = _load_module()

    class _FakeInput:
        def __init__(self) -> None:
            self.closed = False
            self.buffer = ""

        def write(self, value: str) -> None:
            self.buffer += value

        def close(self) -> None:
            self.closed = True

    class _ReplayStream:
        def __init__(self, lines: list[str]) -> None:
            self._lines = list(lines)
            self._closed = False

        def readline(self) -> str:
            if self._lines:
                return self._lines.pop(0)
            return ""

        def close(self) -> None:
            self._closed = True

    class _FakeProcess:
        def __init__(self) -> None:
            self.pid = 43222
            self.returncode = 0
            self.stdin = _FakeInput()
            self.stdout = _ReplayStream([])
            self.stderr = _ReplayStream(
                [
                    "Trace: lane=core waiting for model output (0s)\n",
                    "exec\n",
                    '/usr/bin/bash -lc "python3 /docker/fleet/scripts/chummer_design_supervisor.py status --state-root /docker/fleet/state/chummer_design_supervisor --json | python3 -c ..."\n',
                    " succeeded in 0ms:\n",
                    '{"active_runs_count":1,"remaining_open_milestones":1,"remaining_not_started_milestones":1,"remaining_in_progress_milestones":0,"eta_human":"tracked","summary":"1 open milestone remains in the current shard slice."}\n',
                    "exec\n",
                    '/usr/bin/bash -lc "python3 /docker/fleet/scripts/chummer_design_supervisor.py status --state-root /docker/fleet/state/chummer_design_supervisor --json | python3 -c ..."\n',
                    " succeeded in 0ms:\n",
                    '{"active_runs_count":1,"remaining_open_milestones":1,"remaining_not_started_milestones":1,"remaining_in_progress_milestones":0,"eta_human":"tracked","summary":"1 open milestone remains in the current shard slice."}\n',
                    "Trace: lane=core waiting for model output\n",
                    "exec\n",
                    '/usr/bin/bash -lc "python3 /docker/fleet/scripts/chummer_design_supervisor.py status --state-root /docker/fleet/state/chummer_design_supervisor --json | python3 -c ..."\n',
                    " succeeded in 0ms:\n",
                    '{"active_runs_count":1,"remaining_open_milestones":1,"remaining_not_started_milestones":1,"remaining_in_progress_milestones":0,"eta_human":"tracked","summary":"1 open milestone remains in the current shard slice."}\n',
                ]
            )

        def wait(self, timeout=None) -> int:
            import time as _time

            _time.sleep(0.05)
            if self.returncode not in (None, 0):
                return int(self.returncode or 0)
            raise subprocess.TimeoutExpired(["codexea", "core", "exec"], timeout=timeout or 0.05)

        def kill(self) -> None:
            self.returncode = -9

    monkeypatch.setattr(module.subprocess, "Popen", lambda *args, **kwargs: _FakeProcess())
    monkeypatch.setattr(module, "_runtime_handoff_heartbeat_seconds", lambda: 0.0)
    monkeypatch.setattr(module, "_worker_model_output_stall_seconds", lambda workspace_root, timeout_seconds: 0.01)
    monkeypatch.setattr(module, "_worker_status_helper_loop_trip_threshold", lambda workspace_root: 3)
    monkeypatch.setattr(module, "_worker_task_local_status_loop_grace_seconds", lambda workspace_root: 0.0)
    monkeypatch.setattr(module.os, "killpg", lambda pid, sig: (_ for _ in ()).throw(ProcessLookupError()))

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        state_root = root / "state"
        module._write_json(
            state_root / "state.json",
            {
                "active_run": {
                    "run_id": "run-status-loop",
                    "started_at": "2026-04-14T11:08:45Z",
                }
            },
        )
        last_message_path = root / "last_message.txt"
        completed = module._run_worker_attempt(
            ["codexea", "core", "exec"],
            prompt="Run the flagship full-product delivery pass for Chummer.\n",
            workspace_root=root,
            worker_env={},
            timeout_seconds=0.0,
            last_message_path=last_message_path,
            state_root=state_root,
            run_id="run-status-loop",
            stdout_sink=io.StringIO(),
            stderr_sink=io.StringIO(),
        )

        payload = module._read_state(state_root / "state.json")

        assert completed.returncode == 124
        assert "worker_status_helper_loop:repeated_blocked_status_polling" in completed.stderr
        assert "worker_model_output_stalled:0.01s" not in completed.stderr
        assert last_message_path.read_text(encoding="utf-8").strip() == (
            "Error: worker_status_helper_loop:repeated_blocked_status_polling"
        )
        assert payload["active_run_progress_state"] in {"waiting_for_model_output", "stream_connected_waiting"}
        assert module._retryable_worker_error(completed.stderr) is True
def test_run_worker_attempt_times_out_when_no_meaningful_output_arrives(monkeypatch) -> None:
    module = _load_module()

    class _FakeInput:
        def __init__(self) -> None:
            self.closed = False
            self.buffer = ""

        def write(self, value: str) -> None:
            self.buffer += value

        def close(self) -> None:
            self.closed = True

    class _ReplayStream:
        def __init__(self, lines: list[str]) -> None:
            self._lines = list(lines)
            self._closed = False

        def readline(self) -> str:
            if self._lines:
                return self._lines.pop(0)
            return ""

        def close(self) -> None:
            self._closed = True

    class _FakeProcess:
        def __init__(self) -> None:
            self.pid = 43217
            self.returncode = 0
            self.stdin = _FakeInput()
            self.stdout = _ReplayStream([])
            self.stderr = _ReplayStream(
                [
                    "OpenAI Codex v0.118.0 (research preview)\n",
                    "--------\n",
                    "workdir: /docker/fleet\n",
                ]
            )

        def wait(self, timeout=None) -> int:
            import time as _time

            _time.sleep(0.05)
            if self.returncode not in (None, 0):
                return int(self.returncode or 0)
            raise subprocess.TimeoutExpired(["codexea", "core", "exec"], timeout=timeout or 0.05)

        def kill(self) -> None:
            self.returncode = -9

    monkeypatch.setattr(module.subprocess, "Popen", lambda *args, **kwargs: _FakeProcess())
    monkeypatch.setattr(module, "_runtime_handoff_heartbeat_seconds", lambda: 0.0)
    monkeypatch.setattr(module, "_worker_model_output_stall_seconds", lambda workspace_root, timeout_seconds: 0.01)
    monkeypatch.setattr(module.os, "killpg", lambda pid, sig: (_ for _ in ()).throw(ProcessLookupError()))

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        state_root = root / "state"
        module._write_json(
            state_root / "state.json",
            {
                "active_run": {
                    "run_id": "run-no-output",
                    "started_at": "2026-04-14T11:08:45Z",
                }
            },
        )
        last_message_path = root / "last_message.txt"
        completed = module._run_worker_attempt(
            ["codexea", "core", "exec"],
            prompt="Run the flagship full-product delivery pass for Chummer.\n",
            workspace_root=root,
            worker_env={},
            timeout_seconds=0.0,
            last_message_path=last_message_path,
            state_root=state_root,
            run_id="run-no-output",
            stdout_sink=io.StringIO(),
            stderr_sink=io.StringIO(),
        )

        payload = module._read_state(state_root / "state.json")

        assert completed.returncode == 124
        assert "worker_model_output_stalled:0.01s" in completed.stderr
        assert last_message_path.read_text(encoding="utf-8").strip() == "Error: worker_model_output_stalled:0.01s"
        assert payload.get("active_run_worker_last_output_at") in (None, "")
        assert module._retryable_worker_error(completed.stderr) is True


def test_worker_lane_candidates_prioritize_core_rescue_before_survival_for_core() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        args = _args(root)
        args.worker_lane = "core"

        lanes = module._worker_lane_candidates(args)

        assert lanes == ["core", "core_rescue", "survival", "repair"]


def test_direct_worker_lane_health_snapshot_flags_unroutable_repair_profile(monkeypatch) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        args = _args(root)
        args.worker_bin = "codexea"
        args.worker_lane = "core"
        monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_CORE_RESPONSES_PROFILE", "core_batch")

        def fake_urlopen(request, timeout=0):
            payload = {
                "provider_registry": {
                    "lanes": [
                        {
                            "profile": "core_batch",
                            "primary_provider_key": "onemin",
                            "primary_state": "ready",
                            "capacity_summary": {
                                "state": "ready",
                                "configured_slots": 49,
                                "ready_slots": 47,
                                "degraded_slots": 0,
                                "unavailable_slots": 2,
                                "remaining_percent_of_max": 0.05,
                            },
                            "providers": [{"provider_key": "onemin", "state": "ready", "detail": ""}],
                        },
                        {
                            "profile": "repair",
                            "primary_provider_key": "magixai",
                            "primary_state": "degraded",
                            "capacity_summary": {
                                "state": "degraded",
                                "configured_slots": 1,
                                "ready_slots": 0,
                                "degraded_slots": 1,
                                "unavailable_slots": 0,
                            },
                            "providers": [
                                {
                                    "provider_key": "magixai",
                                    "state": "degraded",
                                    "detail": "rate limit exceeded",
                                    "enabled": True,
                                    "executable": True,
                                }
                            ],
                        },
                    ]
                }
            }

            class _Response:
                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, tb):
                    return False

                def read(self):
                    return json.dumps(payload).encode("utf-8")

            return _Response()

        monkeypatch.setattr(module.urllib.request, "urlopen", fake_urlopen)
        lanes = ["core", "repair"]

        snapshot = module._direct_worker_lane_health_snapshot(args, lanes)

        assert snapshot["status"] == "pass"
        assert snapshot["routable_lanes"] == ["core"]
        assert snapshot["unroutable_lanes"] == ["repair"]
        assert snapshot["lanes"]["core"]["profile"] == "core_batch"
        assert snapshot["lanes"]["repair"]["profile"] == "repair"
        assert snapshot["lanes"]["repair"]["routable"] is False
        assert snapshot["lanes"]["repair"]["state"] == "degraded"


def test_direct_worker_lane_health_snapshot_sends_runtime_ea_auth_headers(monkeypatch) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        args = _args(root)
        args.worker_bin = "codexea"
        args.worker_lane = "core"
        monkeypatch.setenv("EA_MCP_API_TOKEN", "test-token")
        monkeypatch.setenv("EA_MCP_PRINCIPAL_ID", "codex-fleet")
        monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_CORE_RESPONSES_PROFILE", "core_batch")
        seen_headers = {}

        def fake_urlopen(request, timeout=0):
            seen_headers.update({key.lower(): value for key, value in request.header_items()})
            payload = {
                "provider_registry": {
                    "lanes": [
                        {
                            "profile": "core_batch",
                            "primary_provider_key": "onemin",
                            "primary_state": "ready",
                            "capacity_summary": {
                                "state": "ready",
                                "configured_slots": 49,
                                "ready_slots": 47,
                                "degraded_slots": 0,
                                "unavailable_slots": 2,
                            },
                            "providers": [{"provider_key": "onemin", "state": "ready", "detail": ""}],
                        }
                    ]
                }
            }

            class _Response:
                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, tb):
                    return False

                def read(self):
                    return json.dumps(payload).encode("utf-8")

            return _Response()

        monkeypatch.setattr(module.urllib.request, "urlopen", fake_urlopen)

        snapshot = module._direct_worker_lane_health_snapshot(args, ["core"])

        assert snapshot["status"] == "pass"
        assert seen_headers["authorization"] == "Bearer test-token"
        assert seen_headers["x-ea-principal-id"] == "codex-fleet"


def test_codexea_profile_for_lane_uses_dedicated_repair_profile(monkeypatch) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        monkeypatch.delenv("CODEXEA_CORE_RESPONSES_PROFILE", raising=False)
        monkeypatch.delenv("CHUMMER_DESIGN_SUPERVISOR_CORE_RESPONSES_PROFILE", raising=False)

        assert module._codexea_profile_for_lane("repair", workspace_root=root) == "repair"


def test_ea_provider_health_candidate_urls_adds_host_gateway_fallback_for_loopback() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        args = _args(root)
        args.ea_provider_health_url = "http://127.0.0.1:8090/v1/responses/_provider_health"

        urls = module._ea_provider_health_candidate_urls(args)

        assert urls == [
            "http://127.0.0.1:8090/v1/responses/_provider_health",
            "http://host.docker.internal:8090/v1/responses/_provider_health",
        ]


def test_ea_provider_health_candidate_urls_adds_loopback_fallback_for_host_gateway() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        args = _args(root)
        args.ea_provider_health_url = "http://host.docker.internal:8090/v1/responses/_provider_health"

        urls = module._ea_provider_health_candidate_urls(args)

        assert urls == [
            "http://host.docker.internal:8090/v1/responses/_provider_health",
            "http://127.0.0.1:8090/v1/responses/_provider_health",
        ]


def test_ea_provider_health_request_url_adds_lightweight_query() -> None:
    module = _load_module()

    assert (
        module._ea_provider_health_request_url("http://127.0.0.1:8090/v1/responses/_provider_health")
        == "http://127.0.0.1:8090/v1/responses/_provider_health?lightweight=1"
    )
    assert (
        module._ea_provider_health_request_url("http://127.0.0.1:8090/v1/responses/_provider_health?foo=bar")
        == "http://127.0.0.1:8090/v1/responses/_provider_health?foo=bar&lightweight=1"
    )
    assert (
        module._ea_provider_health_request_url("http://127.0.0.1:8090/v1/responses/_provider_health?lightweight=1")
        == "http://127.0.0.1:8090/v1/responses/_provider_health?lightweight=1"
    )
    assert (
        module._ea_provider_health_request_url("http://127.0.0.1:8090/v1/codex/profiles")
        == "http://127.0.0.1:8090/v1/codex/profiles"
    )


def test_ea_provider_health_url_reads_runtime_env_when_process_env_missing(monkeypatch) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        args = _args(root)
        args.ea_provider_health_url = ""
        monkeypatch.delenv("CHUMMER_DESIGN_SUPERVISOR_EA_PROVIDER_HEALTH_URL", raising=False)
        monkeypatch.setattr(
            module,
            "_runtime_env_default",
            lambda name, default="": (
                "http://host.docker.internal:8090/v1/responses/_provider_health"
                if name == "CHUMMER_DESIGN_SUPERVISOR_EA_PROVIDER_HEALTH_URL"
                else default
            ),
        )

        assert (
            module._ea_provider_health_url(args)
            == "http://host.docker.internal:8090/v1/responses/_provider_health"
        )


def test_direct_worker_lane_health_snapshot_falls_back_to_host_gateway_when_loopback_refuses(monkeypatch) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        args = _args(root)
        args.worker_bin = "codexea"
        args.worker_lane = "core"
        args.ea_provider_health_url = "http://127.0.0.1:8090/v1/responses/_provider_health"
        monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_CORE_RESPONSES_PROFILE", "core_batch")
        seen_urls: list[str] = []

        def fake_urlopen(request, timeout=0):
            url = request.full_url if hasattr(request, "full_url") else str(request)
            seen_urls.append(url)
            if url.startswith("http://127.0.0.1:8090/"):
                raise module.urllib.error.URLError(ConnectionRefusedError(111, "Connection refused"))
            payload = {
                "provider_registry": {
                    "lanes": [
                        {
                            "profile": "core_batch",
                            "primary_provider_key": "onemin",
                            "primary_state": "ready",
                            "capacity_summary": {
                                "state": "ready",
                                "configured_slots": 49,
                                "ready_slots": 47,
                                "degraded_slots": 0,
                                "unavailable_slots": 2,
                            },
                            "providers": [{"provider_key": "onemin", "state": "ready", "detail": ""}],
                        }
                    ]
                }
            }

            class _Response:
                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, tb):
                    return False

                def read(self):
                    return json.dumps(payload).encode("utf-8")

            return _Response()

        monkeypatch.setattr(module.urllib.request, "urlopen", fake_urlopen)

        snapshot = module._direct_worker_lane_health_snapshot(args, ["core"])

        assert seen_urls == [
            "http://127.0.0.1:8090/v1/responses/_provider_health?lightweight=1",
            "http://host.docker.internal:8090/v1/responses/_provider_health?lightweight=1",
        ]
        assert snapshot["status"] == "pass"
        assert snapshot["source_url"] == "http://host.docker.internal:8090/v1/responses/_provider_health"
        assert snapshot["routable_lanes"] == ["core"]
        cache_payload = json.loads((root / "state" / "ea_provider_health_cache.json").read_text(encoding="utf-8"))
        assert cache_payload["last_live_fetch_error"] == ""
        assert cache_payload["last_live_fetch_failed_at"] == ""


def test_direct_worker_lane_health_snapshot_requests_lightweight_provider_health(monkeypatch) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        args = _args(root)
        args.worker_bin = "codexea"
        args.ea_provider_health_url = "http://provider-health.internal:8090/v1/responses/_provider_health"

        observed: list[str] = []

        class _Response:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return json.dumps(
                    {
                        "provider_health": {
                            "providers": {
                                "onemin": {
                                    "configured_slots": 1,
                                    "slots": [{"slot": "primary", "state": "ready"}],
                                }
                            }
                        },
                        "provider_registry": {
                            "lanes": [{"profile": "core", "state": "ready"}]
                        },
                    }
                ).encode("utf-8")

        def fake_urlopen(request, timeout=0):
            observed.append(str(getattr(request, "full_url", request)))
            return _Response()

        monkeypatch.setattr(module.urllib.request, "urlopen", fake_urlopen)

        snapshot = module._direct_worker_lane_health_snapshot(args, worker_lane_candidates=["core"])

        assert observed == ["http://provider-health.internal:8090/v1/responses/_provider_health?lightweight=1"]
        assert snapshot["source_url"] == "http://provider-health.internal:8090/v1/responses/_provider_health"


def test_direct_worker_lane_health_snapshot_uses_fresh_container_local_cache_from_host_cli(monkeypatch) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        args = _args(root)
        args.worker_bin = "codexea"
        args.worker_lane = "core"
        args.ea_provider_health_url = ""
        monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_CORE_RESPONSES_PROFILE", "core_batch")
        monkeypatch.setattr(module, "_running_inside_container", lambda: False)
        module._write_json(
            root / "state" / "ea_provider_health_cache.json",
            {
                "cached_at": module._iso_now(),
                "source_url": "http://host.docker.internal:8090/v1/responses/_provider_health",
                "payload": {
                    "provider_registry": {
                        "lanes": [
                            {
                                "profile": "core_batch",
                                "primary_provider_key": "onemin",
                                "primary_state": "ready",
                                "capacity_summary": {
                                    "state": "ready",
                                    "configured_slots": 49,
                                    "ready_slots": 47,
                                    "degraded_slots": 0,
                                    "unavailable_slots": 2,
                                },
                                "providers": [{"provider_key": "onemin", "state": "ready", "detail": ""}],
                            }
                        ]
                    }
                },
            },
        )

        def unexpected_urlopen(request, timeout=0):
            raise AssertionError("host CLI should use the fresh container-local cache without probing live URLs")

        monkeypatch.setattr(module.urllib.request, "urlopen", unexpected_urlopen)

        snapshot = module._direct_worker_lane_health_snapshot(args, ["core"])

        assert snapshot["status"] == "pass"
        assert snapshot["cache_used"] is True
        assert snapshot["source_url"] == "http://host.docker.internal:8090/v1/responses/_provider_health"
        assert snapshot["live_probe_scope"] == "container_local"
        assert "container-local" in snapshot["reason"]


def test_direct_worker_lane_health_snapshot_falls_back_to_loopback_when_host_gateway_is_unresolved(monkeypatch) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        args = _args(root)
        args.worker_bin = "codexea"
        args.worker_lane = "core"
        args.ea_provider_health_url = "http://host.docker.internal:8090/v1/responses/_provider_health"
        monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_CORE_RESPONSES_PROFILE", "core_batch")
        seen_urls: list[str] = []

        def fake_urlopen(request, timeout=0):
            url = request.full_url if hasattr(request, "full_url") else str(request)
            seen_urls.append(url)
            if url.startswith("http://host.docker.internal:8090/"):
                raise module.urllib.error.URLError(OSError(-2, "Name or service not known"))
            payload = {
                "provider_registry": {
                    "lanes": [
                        {
                            "profile": "core_batch",
                            "primary_provider_key": "onemin",
                            "primary_state": "ready",
                            "capacity_summary": {
                                "state": "ready",
                                "configured_slots": 49,
                                "ready_slots": 47,
                                "degraded_slots": 0,
                                "unavailable_slots": 2,
                            },
                            "providers": [{"provider_key": "onemin", "state": "ready", "detail": ""}],
                        }
                    ]
                }
            }

            class _Response:
                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, tb):
                    return False

                def read(self):
                    return json.dumps(payload).encode("utf-8")

            return _Response()

        monkeypatch.setattr(module.urllib.request, "urlopen", fake_urlopen)

        snapshot = module._direct_worker_lane_health_snapshot(args, ["core"])

        assert seen_urls == [
            "http://host.docker.internal:8090/v1/responses/_provider_health?lightweight=1",
            "http://127.0.0.1:8090/v1/responses/_provider_health?lightweight=1",
        ]
        assert snapshot["status"] == "pass"
        assert snapshot["source_url"] == "http://127.0.0.1:8090/v1/responses/_provider_health"
        assert snapshot["routable_lanes"] == ["core"]


def test_direct_worker_lane_health_snapshot_retries_same_url_after_timeout(monkeypatch) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        args = _args(root)
        args.worker_bin = "codexea"
        args.worker_lane = "core"
        args.ea_provider_health_url = "http://provider-health.internal:8090/v1/responses/_provider_health"
        monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_CORE_RESPONSES_PROFILE", "core_batch")
        seen: list[tuple[str, float]] = []
        call_count = {"value": 0}

        def fake_urlopen(request, timeout=0):
            url = request.full_url if hasattr(request, "full_url") else str(request)
            seen.append((url, float(timeout)))
            call_count["value"] += 1
            if call_count["value"] == 1:
                raise TimeoutError("timed out")
            payload = {
                "provider_registry": {
                    "lanes": [
                        {
                            "profile": "core_batch",
                            "primary_provider_key": "onemin",
                            "primary_state": "ready",
                            "capacity_summary": {
                                "state": "ready",
                                "configured_slots": 49,
                                "ready_slots": 47,
                                "degraded_slots": 0,
                                "unavailable_slots": 2,
                            },
                            "providers": [{"provider_key": "onemin", "state": "ready", "detail": ""}],
                        }
                    ]
                }
            }

            class _Response:
                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, tb):
                    return False

                def read(self):
                    return json.dumps(payload).encode("utf-8")

            return _Response()

        monkeypatch.setattr(module.urllib.request, "urlopen", fake_urlopen)

        snapshot = module._direct_worker_lane_health_snapshot(args, ["core"])

        assert seen == [
            ("http://provider-health.internal:8090/v1/responses/_provider_health?lightweight=1", 4.0),
            ("http://provider-health.internal:8090/v1/responses/_provider_health?lightweight=1", 8.0),
        ]
        assert snapshot["status"] == "pass"
        assert snapshot["source_url"] == "http://provider-health.internal:8090/v1/responses/_provider_health"
        assert snapshot["routable_lanes"] == ["core"]


def test_direct_worker_lane_health_snapshot_tries_host_gateway_before_retrying_timed_out_loopback(monkeypatch) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        args = _args(root)
        args.worker_bin = "codexea"
        args.worker_lane = "core"
        args.ea_provider_health_url = "http://127.0.0.1:8090/v1/responses/_provider_health"
        monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_CORE_RESPONSES_PROFILE", "core_batch")
        seen: list[tuple[str, float]] = []

        def fake_urlopen(request, timeout=0):
            url = request.full_url if hasattr(request, "full_url") else str(request)
            seen.append((url, float(timeout)))
            if url.startswith("http://127.0.0.1:8090/"):
                raise TimeoutError("timed out")
            payload = {
                "provider_registry": {
                    "lanes": [
                        {
                            "profile": "core_batch",
                            "primary_provider_key": "onemin",
                            "primary_state": "ready",
                            "capacity_summary": {
                                "state": "ready",
                                "configured_slots": 49,
                                "ready_slots": 47,
                                "degraded_slots": 0,
                                "unavailable_slots": 2,
                            },
                            "providers": [{"provider_key": "onemin", "state": "ready", "detail": ""}],
                        }
                    ]
                }
            }

            class _Response:
                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, tb):
                    return False

                def read(self):
                    return json.dumps(payload).encode("utf-8")

            return _Response()

        monkeypatch.setattr(module.urllib.request, "urlopen", fake_urlopen)

        snapshot = module._direct_worker_lane_health_snapshot(args, ["core"])

        assert seen == [
            ("http://127.0.0.1:8090/v1/responses/_provider_health?lightweight=1", 4.0),
            ("http://host.docker.internal:8090/v1/responses/_provider_health?lightweight=1", 4.0),
        ]
        assert snapshot["status"] == "pass"
        assert snapshot["source_url"] == "http://host.docker.internal:8090/v1/responses/_provider_health"
        assert snapshot["routable_lanes"] == ["core"]
        cache_payload = json.loads((root / "state" / "ea_provider_health_cache.json").read_text(encoding="utf-8"))
        assert cache_payload["last_live_fetch_error"] == ""


def test_direct_worker_lane_health_snapshot_persists_successful_payload_to_cache(monkeypatch) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "state").mkdir(parents=True, exist_ok=True)
        args = _args(root)
        args.worker_bin = "codexea"
        args.worker_lane = "core"
        args.state_root = str(root / "state" / "shard-1")
        args.ea_provider_health_url = "http://127.0.0.1:8090/v1/responses/_provider_health"
        monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_CORE_RESPONSES_PROFILE", "core_batch")
        payload = {
            "provider_registry": {
                "lanes": [
                    {
                        "profile": "core_batch",
                        "primary_provider_key": "onemin",
                        "primary_state": "ready",
                        "capacity_summary": {
                            "state": "ready",
                            "configured_slots": 49,
                            "ready_slots": 47,
                            "degraded_slots": 0,
                            "unavailable_slots": 2,
                        },
                        "providers": [{"provider_key": "onemin", "state": "ready", "detail": ""}],
                    }
                ]
            }
        }

        def fake_urlopen(request, timeout=0):
            class _Response:
                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, tb):
                    return False

                def read(self):
                    return json.dumps(payload).encode("utf-8")

            return _Response()

        monkeypatch.setattr(module.urllib.request, "urlopen", fake_urlopen)

        snapshot = module._direct_worker_lane_health_snapshot(args, ["core"])

        cache_path = root / "state" / "ea_provider_health_cache.json"
        cache_payload = json.loads(cache_path.read_text(encoding="utf-8"))
        assert snapshot["status"] == "pass"
        assert cache_payload["payload"] == payload
        assert cache_payload["source_url"] == "http://127.0.0.1:8090/v1/responses/_provider_health"


def test_direct_worker_lane_health_snapshot_uses_recent_cache_when_live_fetch_fails(monkeypatch) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        args = _args(root)
        args.worker_bin = "codexea"
        args.worker_lane = "core"
        args.state_root = str(root / "state" / "shard-1")
        args.ea_provider_health_url = "http://host.docker.internal:8090/v1/responses/_provider_health"
        monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_CORE_RESPONSES_PROFILE", "core_batch")
        cache_path = root / "state" / "ea_provider_health_cache.json"
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(
            json.dumps(
                {
                    "cached_at": module._iso_now(),
                    "source_url": "http://127.0.0.1:8090/v1/responses/_provider_health",
                    "payload": {
                        "provider_registry": {
                            "lanes": [
                                {
                                    "profile": "core_batch",
                                    "primary_provider_key": "onemin",
                                    "primary_state": "ready",
                                    "capacity_summary": {
                                        "state": "ready",
                                        "configured_slots": 49,
                                        "ready_slots": 47,
                                        "degraded_slots": 0,
                                        "unavailable_slots": 2,
                                    },
                                    "providers": [{"provider_key": "onemin", "state": "ready", "detail": ""}],
                                }
                            ]
                        }
                    },
                }
            )
            + "\n",
            encoding="utf-8",
        )

        def fake_urlopen(request, timeout=0):
            raise module.urllib.error.URLError(ConnectionRefusedError(111, "Connection refused"))

        monkeypatch.setattr(module.urllib.request, "urlopen", fake_urlopen)

        snapshot = module._direct_worker_lane_health_snapshot(args, ["core"])

        assert snapshot["status"] == "pass"
        assert snapshot["cache_used"] is True
        assert snapshot["source_url"] == "http://127.0.0.1:8090/v1/responses/_provider_health"
        assert snapshot["routable_lanes"] == ["core"]
        assert "using cached provider-health" in snapshot["reason"]


def test_direct_worker_lane_health_snapshot_uses_recent_cache_during_live_fetch_cooldown(monkeypatch) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        args = _args(root)
        args.worker_bin = "codexea"
        args.worker_lane = "core"
        args.state_root = str(root / "state" / "shard-1")
        args.ea_provider_health_url = "http://host.docker.internal:8090/v1/responses/_provider_health"
        monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_CORE_RESPONSES_PROFILE", "core_batch")
        cache_path = root / "state" / "ea_provider_health_cache.json"
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(
            json.dumps(
                {
                    "cached_at": module._iso_now(),
                    "last_live_fetch_failed_at": module._iso_now(),
                    "last_live_fetch_error": "http://127.0.0.1:8090/v1/responses/_provider_health: timed out",
                    "source_url": "http://127.0.0.1:8090/v1/responses/_provider_health",
                    "payload": {
                        "provider_registry": {
                            "lanes": [
                                {
                                    "profile": "core_batch",
                                    "primary_provider_key": "onemin",
                                    "primary_state": "ready",
                                    "capacity_summary": {
                                        "state": "ready",
                                        "configured_slots": 49,
                                        "ready_slots": 47,
                                        "degraded_slots": 0,
                                        "unavailable_slots": 2,
                                    },
                                    "providers": [{"provider_key": "onemin", "state": "ready", "detail": ""}],
                                }
                            ]
                        }
                    },
                }
            )
            + "\n",
            encoding="utf-8",
        )
        calls = {"count": 0}

        def fake_urlopen(request, timeout=0):
            calls["count"] += 1
            raise AssertionError("live fetch should be skipped during cooldown")

        monkeypatch.setattr(module.urllib.request, "urlopen", fake_urlopen)

        snapshot = module._direct_worker_lane_health_snapshot(args, ["core"])

        assert calls["count"] == 0
        assert snapshot["status"] == "pass"
        assert snapshot["cache_used"] is True
        assert snapshot["source_url"] == "http://127.0.0.1:8090/v1/responses/_provider_health"
        assert snapshot["routable_lanes"] == ["core"]
        assert "live-fetch cooldown" in snapshot["reason"]


def test_direct_worker_lane_health_snapshot_uses_local_onemin_fallback_when_live_fetch_fails(monkeypatch) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        args = _args(root)
        args.worker_bin = "codexea"
        args.worker_lane = "core"
        args.state_root = str(root / "state" / "shard-1")
        args.ea_provider_health_url = "http://host.docker.internal:8090/v1/responses/_provider_health"
        monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_CORE_RESPONSES_PROFILE", "core_batch")

        def fake_urlopen(request, timeout=0):
            raise module.urllib.error.URLError(ConnectionRefusedError(111, "Connection refused"))

        class _CodexeaRoute:
            @staticmethod
            def _local_onemin_direct_payload(*, probe_all=False, include_reserve=True):
                assert probe_all is False
                assert include_reserve is True
                return {
                    "provider_health": {
                        "providers": {
                            "onemin": {
                                "balance_basis_summary": "actual",
                                "configured_slots": 4,
                                "active_lease_count": 1,
                                "remaining_percent_of_max": 0.69,
                                "estimated_remaining_credits_total": 181169079,
                                "slots": [
                                    {"configured": True, "state": "ready"},
                                    {"configured": True, "state": "ready"},
                                    {"configured": True, "state": "ready"},
                                    {"configured": True, "state": "ready"},
                                ],
                            }
                        }
                    }
                }

        monkeypatch.setattr(module.urllib.request, "urlopen", fake_urlopen)
        monkeypatch.setattr(module, "_load_sibling_module", lambda name: _CodexeaRoute if name == "codexea_route" else None)

        snapshot = module._direct_worker_lane_health_snapshot(args, ["core", "repair", "survival"])

        cache_path = root / "state" / "ea_provider_health_cache.json"
        cache_payload = json.loads(cache_path.read_text(encoding="utf-8"))
        assert snapshot["status"] == "pass"
        assert snapshot["local_fallback_used"] is True
        assert snapshot["source_url"] == "local://codexea_route/_local_onemin_direct_payload"
        assert snapshot["lanes"]["core"]["known"] is True
        assert snapshot["lanes"]["core"]["profile"] == "core_batch"
        assert snapshot["lanes"]["survival"]["known"] is True
        assert snapshot["lanes"]["repair"]["known"] is False
        assert "using local 1min provider-health fallback" in snapshot["reason"]
        assert cache_payload["source_url"] == "local://codexea_route/_local_onemin_direct_payload"


def test_local_ea_provider_health_payload_retries_with_fresh_sibling_module(monkeypatch) -> None:
    module = _load_module()
    expected = {
        "provider_health": {
            "providers": {
                "onemin": {
                    "configured_slots": 1,
                    "slots": [{"configured": True, "state": "ready"}],
                }
            }
        }
    }
    calls: list[str] = []

    class _CachedModule:
        @staticmethod
        def _local_onemin_direct_payload(*, probe_all=False, include_reserve=True):
            calls.append("cached")
            return None

    class _FreshModule:
        @staticmethod
        def _local_onemin_direct_payload(*, probe_all=False, include_reserve=True):
            calls.append("fresh")
            return expected

    monkeypatch.setattr(module, "_load_sibling_module", lambda name: _CachedModule)
    monkeypatch.setattr(module, "_load_fresh_sibling_module", lambda name: _FreshModule)

    payload = module._local_ea_provider_health_payload()

    assert payload == expected
    assert calls == ["cached", "fresh"]


def test_with_fleet_app_modules_hidden_hides_only_fleet_app_modules() -> None:
    module = _load_module()

    class _FleetApp:
        __file__ = "/docker/fleet/studio/app.py"

    class _FleetSubmodule:
        __file__ = "/docker/fleet/studio/app/services.py"

    class _EaApp:
        __file__ = "/docker/EA/ea/app/__init__.py"

    previous = {
        key: sys.modules.get(key)
        for key in ("app", "app.services", "app.ea_services")
    }
    sys.modules["app"] = _FleetApp
    sys.modules["app.services"] = _FleetSubmodule
    sys.modules["app.ea_services"] = _EaApp
    try:
        seen = {}

        def callback():
            seen["app"] = "app" in sys.modules
            seen["app.services"] = "app.services" in sys.modules
            seen["app.ea_services"] = "app.ea_services" in sys.modules
            return {"ok": True}

        payload = module._with_fleet_app_modules_hidden(callback)
    finally:
        for key, value in previous.items():
            if value is None:
                sys.modules.pop(key, None)
            else:
                sys.modules[key] = value

    assert payload == {"ok": True}
    assert seen == {
        "app": False,
        "app.services": False,
        "app.ea_services": True,
    }


def test_launch_worker_skips_unroutable_direct_lane_before_attempt(monkeypatch) -> None:
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
        context = module.derive_context(args)

        monkeypatch.setattr(
            module,
            "_direct_worker_lane_health_snapshot",
            lambda _args, _lanes: {
                "status": "pass",
                "reason": "repair is degraded with no ready slots",
                "routable_lanes": ["core", "core_rescue"],
                "unroutable_lanes": ["repair"],
                "lanes": {
                    "core": {"worker_lane": "core", "profile": "core_batch", "state": "ready", "routable": True, "reason": ""},
                    "repair": {
                        "worker_lane": "repair",
                        "profile": "easy",
                        "state": "degraded",
                        "routable": False,
                        "reason": "magixai degraded and has no ready slots",
                    },
                    "core_rescue": {
                        "worker_lane": "core_rescue",
                        "profile": "core_rescue",
                        "state": "ready",
                        "routable": True,
                        "reason": "",
                    },
                },
            },
        )

        calls: list[list[str]] = []

        def fake_run(command, *, input, text, capture_output, cwd, check, env=None, timeout=None):
            calls.append(list(command))
            message_path = Path(command[command.index("-o") + 1])
            lane = command[1]
            if lane == "core":
                message_path.write_text("Error: upstream_timeout:300s\n", encoding="utf-8")
                return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
            message_path.write_text(
                "What shipped: rescue lane recovered the slice\nWhat remains: none\nExact blocker: none\n",
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        _patch_launch_worker_fake_run(monkeypatch, module, fake_run)

        run = module.launch_worker(args, context, root / "state")

        assert run.accepted is True
        assert run.attempted_accounts == ["lane:core", "lane:core_rescue"]
        assert [call[1] for call in calls] == ["core", "core_rescue"]
        stderr_text = (root / "state" / "runs" / run.run_id / "worker.stderr.log").read_text(encoding="utf-8")
        assert "skip direct lane=repair" in stderr_text


def test_build_completion_review_prompt_compacts_verbose_sections() -> None:
    module = _load_module()
    frontier = [
        module.Milestone(
            id=1394756221,
            title="Repo backlog: ui-kit token canon",
            wave="completion_review",
            status="review_required",
            owners=["chummer6-ui-kit"],
            exit_criteria=["Close the active repo-local backlog item."],
            dependencies=[],
        )
    ]
    audit = {
        "status": "fail",
        "reason": "latest worker receipt is not trusted",
        "journey_gate_audit": {
            "blocked_journeys": [
                {
                    "id": "install_claim_restore_continue",
                    "state": "warning",
                    "owner_repos": ["chummer6-ui", "fleet"],
                    "warning_reasons": ["x" * 320],
                }
            ]
        },
        "linux_desktop_exit_gate_audit": {
            "path": "/tmp/proof.json",
            "generated_at": "2026-03-31T14:36:03Z",
            "age_seconds": 12,
            "proof_status": "passed",
            "stage": "complete",
            "head_id": "avalonia",
            "launch_target": "Chummer.Avalonia",
            "rid": "linux-x64",
            "source_snapshot_mode": "filesystem_copy",
            "primary_install_mode": "dpkg_rootless_install",
            "primary_install_verification_status": "passed",
            "primary_smoke_status": "passed",
            "fallback_smoke_status": "passed",
            "unit_test_status": "passed",
            "test_total": 14,
            "test_passed": 14,
            "test_failed": 0,
            "test_skipped": 0,
            "primary_install_verification_path": "/tmp/install-verification.json",
            "source_snapshot_entry_count": 377,
            "source_snapshot_finish_entry_count": 377,
            "source_snapshot_worktree_sha256": "a" * 128,
            "source_snapshot_finish_worktree_sha256": "b" * 128,
            "source_snapshot_identity_stable": True,
            "primary_install_wrapper_sha256": "c" * 128,
            "primary_install_desktop_entry_sha256": "d" * 128,
            "proof_git_head": "e" * 64,
            "current_git_head": "f" * 64,
            "reason": "linux desktop proof ready",
        },
        "weekly_pulse_audit": {
            "path": "/tmp/pulse.json",
            "generated_at": "2026-03-31T01:19:26Z",
            "as_of": "2026-03-31",
            "release_health_state": "green_or_explained",
            "journey_gate_health_state": "ready",
            "design_drift_count": 0,
            "public_promise_drift_count": 0,
            "oldest_blocker_days": 0,
        },
        "repo_backlog_audit": {
            "status": "fail",
            "open_items": [
                {
                    "project_id": "ui-kit",
                    "repo_slug": "chummer6-ui-kit",
                    "task": "Seed token canon " + ("and preview gallery " * 20),
                }
                for _ in range(6)
            ],
        },
    }
    history = [
        {
            "run_id": "20260331T161153Z",
            "worker_exit_code": 0,
            "frontier_ids": [1394756221],
            "primary_milestone_id": 1394756221,
            "final_message": "Error: upstream_timeout:300s",
        }
    ]

    prompt = module.build_completion_review_prompt(
        registry_path=Path("/tmp/registry.yaml"),
        program_milestones_path=Path("/tmp/PROGRAM_MILESTONES.yaml"),
        roadmap_path=Path("/tmp/ROADMAP.md"),
        handoff_path=Path("/tmp/NEXT_SESSION_HANDOFF.md"),
        frontier_artifact_path=Path("/tmp/COMPLETION_REVIEW_FRONTIER.generated.yaml"),
        frontier=frontier,
        scope_roots=[Path("/docker/fleet"), Path("/docker/chummercomplete")],
        focus_profiles=[],
        focus_owners=["chummer6-ui", "chummer6-ui-kit"],
        focus_texts=["desktop", "client"],
        audit=audit,
        history=history,
    )

    assert "snapshot_sha=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" not in prompt
    assert "- + 2 more" in prompt or "- + 1 more" in prompt


def test_build_completion_review_prompt_compact_mode_is_artifact_first() -> None:
    module = _load_module()
    frontier = [
        module.Milestone(
            id=1394756221,
            title="Repo backlog: ui-kit token canon",
            wave="completion_review",
            status="review_required",
            owners=["chummer6-ui-kit"],
            exit_criteria=["Close the active repo-local backlog item."],
            dependencies=[],
        )
    ]
    audit = {
        "status": "fail",
        "reason": "latest worker receipt is not trusted",
        "repo_backlog_audit": {
            "status": "fail",
            "open_items": [
                {
                    "project_id": "ui-kit",
                    "repo_slug": "chummer6-ui-kit",
                    "task": "Seed token canon " + ("and preview gallery " * 20),
                }
            ],
        },
    }

    prompt = module.build_completion_review_prompt(
        registry_path=Path("/tmp/registry.yaml"),
        program_milestones_path=Path("/tmp/PROGRAM_MILESTONES.yaml"),
        roadmap_path=Path("/tmp/ROADMAP.md"),
        handoff_path=Path("/tmp/NEXT_SESSION_HANDOFF.md"),
        frontier_artifact_path=Path("/tmp/COMPLETION_REVIEW_FRONTIER.generated.yaml"),
        frontier=frontier,
        scope_roots=[Path("/docker/fleet"), Path("/docker/chummercomplete")],
        focus_profiles=[],
        focus_owners=["chummer6-ui-kit"],
        focus_texts=["desktop", "sr6"],
        audit=audit,
        history=[],
        compact_prompt=True,
    )

    assert "Read these files directly first:" in prompt
    assert "/tmp/COMPLETION_REVIEW_FRONTIER.generated.yaml" in prompt
    assert "Desktop recovery non-negotiables when the reopened slice touches the desktop flagship:" not in prompt
    assert "Linux desktop exit-gate gaps:" not in prompt
    assert "Weekly product pulse gaps:" not in prompt
    assert len(prompt) < 2200


def test_build_completion_review_prompt_compact_includes_desktop_recovery_non_negotiables_for_desktop_slice() -> None:
    module = _load_module()
    frontier = [
        module.Milestone(
            id=2541792707,
            title="Flagship desktop parity: Windows installer wizard",
            wave="completion_review",
            status="review_required",
            owners=["chummer6-ui", "chummer6-hub"],
            exit_criteria=["Fix the guided installer recovery flow."],
            dependencies=[],
        )
    ]
    audit = {
        "status": "fail",
        "reason": "desktop flagship proof is not trusted",
        "journey_gate_audit": {"status": "fail"},
        "linux_desktop_exit_gate_audit": {"status": "fail"},
        "weekly_pulse_audit": {"status": "fail"},
        "repo_backlog_audit": {"status": "fail", "open_items": []},
    }

    prompt = module.build_completion_review_prompt(
        registry_path=Path("/tmp/registry.yaml"),
        program_milestones_path=Path("/tmp/PROGRAM_MILESTONES.yaml"),
        roadmap_path=Path("/tmp/ROADMAP.md"),
        handoff_path=Path("/tmp/NEXT_SESSION_HANDOFF.md"),
        frontier_artifact_path=Path("/tmp/COMPLETION_REVIEW_FRONTIER.generated.yaml"),
        frontier=frontier,
        scope_roots=[Path("/docker/fleet"), Path("/docker/chummercomplete")],
        focus_profiles=[],
        focus_owners=["chummer6-ui", "chummer6-hub"],
        focus_texts=["windows", "installer", "claim"],
        audit=audit,
        history=[],
        compact_prompt=True,
    )

    assert "Desktop recovery non-negotiables when the reopened slice touches the desktop flagship:" in prompt
    assert "No generic shell, decorative mainframe, or dashboard-first landing page." in prompt
    assert "First useful screen must be the real workbench or restore continuation flow." in prompt
    assert "Real `File` menu, first-class master index, and first-class character roster are mandatory." in prompt
    assert "browser-only claim-code ritual" in prompt
    assert "framework-first or head-first choice" in prompt


def test_build_flagship_product_prompt_compact_includes_desktop_non_negotiables() -> None:
    module = _load_module()
    frontier = [
        module.Milestone(
            id=4066417069,
            title="Flagship desktop parity: Avalonia shell controls",
            wave="flagship_product",
            status="review_required",
            owners=["chummer6-ui"],
            exit_criteria=["Rebuild the workbench-first shell."],
            dependencies=[],
        )
    ]

    prompt = module.build_flagship_product_prompt(
        registry_path=Path("/tmp/registry.yaml"),
        program_milestones_path=Path("/tmp/PROGRAM_MILESTONES.yaml"),
        roadmap_path=Path("/tmp/ROADMAP.md"),
        handoff_path=Path("/tmp/NEXT_SESSION_HANDOFF.md"),
        readiness_path=Path("/tmp/FLAGSHIP_PRODUCT_READINESS.generated.json"),
        frontier_artifact_path=Path("/tmp/FULL_PRODUCT_FRONTIER.generated.yaml"),
        frontier=frontier,
        scope_roots=[Path("/docker/fleet"), Path("/docker/chummercomplete")],
        focus_profiles=["desktop_client"],
        focus_owners=["chummer6-ui"],
        focus_texts=["desktop", "client", "workbench"],
        completion_audit={"status": "pass", "reason": "release-proof gates are green"},
        full_product_audit={"status": "fail", "reason": "desktop flagship proof is not green", "missing_coverage_keys": ["desktop_client"]},
        history=[],
        compact_prompt=True,
    )

    assert "Run the flagship full-product delivery pass for Chummer." in prompt
    assert "Desktop flagship non-negotiables:" in prompt
    assert "No generic shell, decorative mainframe, or dashboard-first landing page." in prompt
    assert "First useful screen must be the real workbench or restore continuation flow." in prompt
    assert "Real `File` menu, first-class master index, and first-class character roster are mandatory." in prompt
    assert "browser-only claim-code ritual" in prompt
    assert "framework-first or head-first choice" in prompt


def test_build_flagship_product_prompt_full_includes_desktop_non_negotiables() -> None:
    module = _load_module()
    frontier = [
        module.Milestone(
            id=3449507998,
            title="Flagship desktop parity: Master index and character roster",
            wave="flagship_product",
            status="review_required",
            owners=["chummer6-ui"],
            exit_criteria=["Land first-class master index and character roster."],
            dependencies=[],
        )
    ]

    prompt = module.build_flagship_product_prompt(
        registry_path=Path("/tmp/registry.yaml"),
        program_milestones_path=Path("/tmp/PROGRAM_MILESTONES.yaml"),
        roadmap_path=Path("/tmp/ROADMAP.md"),
        handoff_path=Path("/tmp/NEXT_SESSION_HANDOFF.md"),
        readiness_path=Path("/tmp/FLAGSHIP_PRODUCT_READINESS.generated.json"),
        frontier_artifact_path=Path("/tmp/FULL_PRODUCT_FRONTIER.generated.yaml"),
        frontier=frontier,
        scope_roots=[Path("/docker/fleet"), Path("/docker/chummercomplete")],
        focus_profiles=["desktop_client"],
        focus_owners=["chummer6-ui"],
        focus_texts=["master-index", "character-roster", "workbench"],
        completion_audit={"status": "pass", "reason": "release-proof gates are green"},
        full_product_audit={"status": "fail", "reason": "desktop flagship proof is not green", "missing_coverage_keys": ["desktop_client"]},
        history=[],
        compact_prompt=False,
    )

    assert "Run the flagship full-product delivery pass for Chummer." in prompt
    assert "Desktop flagship non-negotiables:" in prompt
    assert "No generic shell, decorative mainframe, or dashboard-first landing page." in prompt
    assert "First useful screen must be the real workbench or restore continuation flow." in prompt
    assert "Real `File` menu, first-class master index, and first-class character roster are mandatory." in prompt
    assert "browser-only claim-code ritual" in prompt
    assert "framework-first or head-first choice" in prompt


def test_build_completion_review_prompt_full_includes_desktop_recovery_non_negotiables() -> None:
    module = _load_module()
    frontier = [
        module.Milestone(
            id=2541792707,
            title="Flagship desktop parity: Windows installer wizard",
            wave="completion_review",
            status="review_required",
            owners=["chummer6-ui", "chummer6-hub"],
            exit_criteria=["Fix the guided installer recovery flow."],
            dependencies=[],
        )
    ]
    audit = {
        "status": "fail",
        "reason": "desktop flagship proof is not trusted",
        "journey_gate_audit": {"status": "fail"},
        "linux_desktop_exit_gate_audit": {"status": "fail"},
        "weekly_pulse_audit": {"status": "fail"},
        "repo_backlog_audit": {"status": "fail", "open_items": []},
    }

    prompt = module.build_completion_review_prompt(
        registry_path=Path("/tmp/registry.yaml"),
        program_milestones_path=Path("/tmp/PROGRAM_MILESTONES.yaml"),
        roadmap_path=Path("/tmp/ROADMAP.md"),
        handoff_path=Path("/tmp/NEXT_SESSION_HANDOFF.md"),
        frontier_artifact_path=Path("/tmp/COMPLETION_REVIEW_FRONTIER.generated.yaml"),
        frontier=frontier,
        scope_roots=[Path("/docker/fleet"), Path("/docker/chummercomplete")],
        focus_profiles=["desktop_client"],
        focus_owners=["chummer6-ui", "chummer6-hub"],
        focus_texts=["windows", "installer", "workbench", "claim"],
        audit=audit,
        history=[],
        compact_prompt=False,
    )

    assert "Run a false-complete recovery pass for the Chummer design supervisor." in prompt
    assert "Desktop recovery non-negotiables when the reopened slice touches the desktop flagship:" in prompt
    assert "No generic shell, decorative mainframe, or dashboard-first landing page." in prompt
    assert "First useful screen must be the real workbench or restore continuation flow." in prompt
    assert "Real `File` menu, first-class master index, and first-class character roster are mandatory." in prompt
    assert "browser-only claim-code ritual" in prompt
    assert "framework-first or head-first choice" in prompt


def test_build_completion_review_prompt_full_omits_desktop_recovery_non_negotiables_for_non_desktop_slice() -> None:
    module = _load_module()
    frontier = [
        module.Milestone(
            id=1394756221,
            title="Repo backlog: ui-kit token canon",
            wave="completion_review",
            status="review_required",
            owners=["chummer6-ui-kit"],
            exit_criteria=["Close the active repo-local backlog item."],
            dependencies=[],
        )
    ]
    audit = {
        "status": "fail",
        "reason": "latest worker receipt is not trusted",
        "journey_gate_audit": {"status": "fail"},
        "linux_desktop_exit_gate_audit": {"status": "fail"},
        "weekly_pulse_audit": {"status": "fail"},
        "repo_backlog_audit": {
            "status": "fail",
            "open_items": [
                {
                    "project_id": "ui-kit",
                    "repo_slug": "chummer6-ui-kit",
                    "task": "Seed token canon and preview gallery",
                }
            ],
        },
    }

    prompt = module.build_completion_review_prompt(
        registry_path=Path("/tmp/registry.yaml"),
        program_milestones_path=Path("/tmp/PROGRAM_MILESTONES.yaml"),
        roadmap_path=Path("/tmp/ROADMAP.md"),
        handoff_path=Path("/tmp/NEXT_SESSION_HANDOFF.md"),
        frontier_artifact_path=Path("/tmp/COMPLETION_REVIEW_FRONTIER.generated.yaml"),
        frontier=frontier,
        scope_roots=[Path("/docker/fleet"), Path("/docker/chummercomplete")],
        focus_profiles=[],
        focus_owners=["chummer6-ui-kit"],
        focus_texts=["desktop", "sr6"],
        audit=audit,
        history=[],
        compact_prompt=False,
    )

    assert "Run a false-complete recovery pass for the Chummer design supervisor." in prompt
    assert "Desktop recovery non-negotiables when the reopened slice touches the desktop flagship:" not in prompt


def test_focused_frontier_biases_owner_and_text_without_requiring_both() -> None:
    module = _load_module()
    frontier = [
        module.Milestone(
            id=1,
            title="Hub registry contracts",
            wave="completion_review",
            status="review_required",
            owners=["chummer6-hub-registry"],
            exit_criteria=["Extract registry contracts."],
            dependencies=[],
        ),
        module.Milestone(
            id=2,
            title="Ruleset-specific workbench adaptation",
            wave="completion_review",
            status="review_required",
            owners=["chummer6-ui"],
            exit_criteria=["Make SR4/SR5/SR6 posture explicit in the workbench."],
            dependencies=[],
        ),
        module.Milestone(
            id=3,
            title="Seed Ui Kit token canon",
            wave="completion_review",
            status="review_required",
            owners=["chummer6-ui-kit"],
            exit_criteria=["Theme compilation ships."],
            dependencies=[],
        ),
    ]
    args = Namespace(
        focus_profile=[],
        focus_owner=["chummer6-ui", "chummer6-ui-kit"],
        focus_text=["workbench", "desktop"],
    )

    focused = module._focused_frontier(args, frontier, frontier)

    assert [item.id for item in focused] == [2, 3]


def test_launch_worker_records_and_clears_active_run_state(monkeypatch) -> None:
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

        seen_active_runs: list[dict[str, object]] = []

        def fake_run(command, *, input, text, capture_output, cwd, check, env=None):
            state = json.loads((root / "state" / "state.json").read_text(encoding="utf-8"))
            seen_active_runs.append(dict(state["active_run"]))
            message_path = Path(command[command.index("-o") + 1])
            message_path.write_text(
                "What shipped: active run was visible\nWhat remains: follow-through\nExact blocker: none\n",
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        _patch_launch_worker_fake_run(monkeypatch, module, fake_run)

        run = module.launch_worker(args, context, root / "state")

        assert seen_active_runs
        assert seen_active_runs[0]["run_id"] == run.run_id
        assert seen_active_runs[0]["selected_account_alias"] == "lane:core"
        final_state = json.loads((root / "state" / "state.json").read_text(encoding="utf-8"))
        assert "active_run" not in final_state


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


def test_completion_audit_ignores_rejected_zero_exit_receipts_superseded_by_later_trusted_receipt() -> None:
    module = _load_module()

    audit = module._completion_audit(
        [
            {
                "run_id": "run-1",
                "worker_exit_code": 0,
                "final_message": "Error: upstream_timeout:300s\n",
            },
            {
                "run_id": "run-2",
                "worker_exit_code": 0,
                "accepted": True,
                "acceptance_reason": "",
                "shipped": "trusted closeout",
                "remains": "none",
                "blocker": "none",
            },
        ]
    )

    assert audit["status"] == "pass"
    assert audit["latest_run_id"] == "run-2"
    assert audit["rejected_zero_exit_run_ids"] == []


def test_design_completion_audit_passes_with_ready_release_proof() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_completion_evidence(root)
        args = _args(root)

        audit = module._design_completion_audit(
            args,
            [
                {
                    "run_id": "run-1",
                    "worker_exit_code": 0,
                    "accepted": True,
                    "acceptance_reason": "",
                    "shipped": "desktop release proof is trusted",
                    "remains": "none",
                    "blocker": "none",
                }
            ],
        )

        assert audit["status"] == "pass"
        assert audit["journey_gate_audit"]["status"] == "pass"
        assert audit["weekly_pulse_audit"]["status"] == "pass"


def test_design_completion_audit_fails_when_desktop_executable_exit_gate_is_stale() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_completion_evidence(root)
        stale_text = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=2)).replace(microsecond=0).isoformat().replace(
            "+00:00", "Z"
        )
        executable_gate_path = root / "DESKTOP_EXECUTABLE_EXIT_GATE.generated.json"
        executable_payload = json.loads(executable_gate_path.read_text(encoding="utf-8"))
        executable_payload["generatedAt"] = stale_text
        executable_gate_path.write_text(json.dumps(executable_payload), encoding="utf-8")
        args = _args(root)

        audit = module._design_completion_audit(
            args,
            [
                {
                    "run_id": "run-1",
                    "worker_exit_code": 0,
                    "accepted": True,
                    "acceptance_reason": "",
                    "shipped": "desktop release proof is trusted",
                    "remains": "none",
                    "blocker": "none",
                }
            ],
        )

        assert audit["status"] == "fail"
        assert audit["desktop_executable_exit_gate_audit"]["status"] == "fail"
        assert "stale" in str(audit["desktop_executable_exit_gate_audit"]["reason"]).lower()


def test_desktop_executable_exit_gate_audit_rejects_external_only_contract_with_local_findings() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_completion_evidence(root)
        payload_path = root / "DESKTOP_EXECUTABLE_EXIT_GATE.generated.json"
        payload = json.loads(payload_path.read_text(encoding="utf-8"))
        payload.update(
            {
                "status": "fail",
                "blockedByExternalConstraintsOnly": True,
                "localBlockingFindings": ["local drift"],
                "localBlockingFindingsCount": 1,
                "externalBlockingFindings": ["external host required"],
                "externalBlockingFindingsCount": 1,
                "blockingFindings": ["local drift", "external host required"],
                "blockingFindingsCount": 2,
            }
        )
        payload_path.write_text(json.dumps(payload), encoding="utf-8")

        audit = module._desktop_executable_exit_gate_audit(_args(root))

        assert audit["status"] == "fail"
        assert "external-only block conflicts with local blocking findings" in str(audit["reason"])


def test_desktop_executable_exit_gate_audit_accepts_deferred_nonlinux_external_only_blockers() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_completion_evidence(root)
        payload_path = root / "DESKTOP_EXECUTABLE_EXIT_GATE.generated.json"
        payload = json.loads(payload_path.read_text(encoding="utf-8"))
        payload.update(
            {
                "status": "fail",
                "reason": "Desktop executable exit gate is not fully proven.",
                "blockedByExternalConstraintsOnly": True,
                "localBlockingFindings": [],
                "localBlockingFindingsCount": 0,
                "externalBlockingFindings": [
                    "Windows startup smoke requires a Windows-capable host; current host cannot run promoted Windows installer smoke.",
                    "macOS startup smoke requires a macOS host with hdiutil; current host cannot run promoted macOS installer smoke.",
                ],
                "externalBlockingFindingsCount": 2,
                "blockingFindings": [
                    "Windows startup smoke requires a Windows-capable host; current host cannot run promoted Windows installer smoke.",
                    "macOS startup smoke requires a macOS host with hdiutil; current host cannot run promoted macOS installer smoke.",
                ],
                "blockingFindingsCount": 2,
            }
        )
        payload_path.write_text(json.dumps(payload), encoding="utf-8")

        previous = os.environ.get("CHUMMER_DESIGN_SUPERVISOR_IGNORE_NONLINUX_DESKTOP_HOST_PROOF_BLOCKERS")
        os.environ["CHUMMER_DESIGN_SUPERVISOR_IGNORE_NONLINUX_DESKTOP_HOST_PROOF_BLOCKERS"] = "1"
        try:
            audit = module._desktop_executable_exit_gate_audit(_args(root))
        finally:
            if previous is None:
                os.environ.pop("CHUMMER_DESIGN_SUPERVISOR_IGNORE_NONLINUX_DESKTOP_HOST_PROOF_BLOCKERS", None)
            else:
                os.environ["CHUMMER_DESIGN_SUPERVISOR_IGNORE_NONLINUX_DESKTOP_HOST_PROOF_BLOCKERS"] = previous

        assert audit["status"] == "pass"
        assert audit["proof_status"] == "fail"
        assert audit["deferred_nonlinux_host_proof_only"] is True


def test_desktop_executable_exit_gate_audit_rejects_passing_payload_with_blocking_findings() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_completion_evidence(root)
        payload_path = root / "DESKTOP_EXECUTABLE_EXIT_GATE.generated.json"
        payload = json.loads(payload_path.read_text(encoding="utf-8"))
        payload.update(
            {
                "status": "pass",
                "blockedByExternalConstraintsOnly": False,
                "externalBlockingFindings": ["missing windows host proof"],
                "externalBlockingFindingsCount": 1,
                "blockingFindings": ["missing windows host proof"],
                "blockingFindingsCount": 1,
            }
        )
        payload_path.write_text(json.dumps(payload), encoding="utf-8")

        audit = module._desktop_executable_exit_gate_audit(_args(root))

        assert audit["status"] == "fail"
        assert "cannot be pass while blocking findings are present" in str(audit["reason"])


def test_desktop_executable_exit_gate_audit_rejects_positive_count_without_rows() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_completion_evidence(root)
        payload_path = root / "DESKTOP_EXECUTABLE_EXIT_GATE.generated.json"
        payload = json.loads(payload_path.read_text(encoding="utf-8"))
        payload.update(
            {
                "status": "fail",
                "blockedByExternalConstraintsOnly": False,
                "blockingFindings": [],
                "blockingFindingsCount": 1,
                "localBlockingFindings": [],
                "localBlockingFindingsCount": 0,
                "externalBlockingFindings": [],
                "externalBlockingFindingsCount": 1,
            }
        )
        payload_path.write_text(json.dumps(payload), encoding="utf-8")

        audit = module._desktop_executable_exit_gate_audit(_args(root))

        assert audit["status"] == "fail"
        assert "count is positive but no finding rows were provided" in str(audit["reason"])


def test_desktop_executable_exit_gate_audit_rejects_total_count_mismatch_vs_local_and_external() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_completion_evidence(root)
        payload_path = root / "DESKTOP_EXECUTABLE_EXIT_GATE.generated.json"
        payload = json.loads(payload_path.read_text(encoding="utf-8"))
        payload.update(
            {
                "status": "fail",
                "blockedByExternalConstraintsOnly": False,
                "localBlockingFindings": ["local drift"],
                "localBlockingFindingsCount": 1,
                "externalBlockingFindings": ["external host required"],
                "externalBlockingFindingsCount": 1,
                "blockingFindings": ["local drift", "external host required"],
                "blockingFindingsCount": 3,
            }
        )
        payload_path.write_text(json.dumps(payload), encoding="utf-8")

        audit = module._desktop_executable_exit_gate_audit(_args(root))

        assert audit["status"] == "fail"
        assert "does not equal local plus external counts" in str(audit["reason"])


def test_desktop_executable_exit_gate_audit_rejects_negative_blocking_counts() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_completion_evidence(root)
        payload_path = root / "DESKTOP_EXECUTABLE_EXIT_GATE.generated.json"
        payload = json.loads(payload_path.read_text(encoding="utf-8"))
        payload.update(
            {
                "status": "pass",
                "blockedByExternalConstraintsOnly": False,
                "blockingFindingsCount": -1,
                "localBlockingFindingsCount": 0,
                "externalBlockingFindingsCount": 0,
                "blockingFindings": [],
                "localBlockingFindings": [],
                "externalBlockingFindings": [],
            }
        )
        payload_path.write_text(json.dumps(payload), encoding="utf-8")

        audit = module._desktop_executable_exit_gate_audit(_args(root))

        assert audit["status"] == "fail"
        assert "counts must be non-negative" in str(audit["reason"])


def test_desktop_executable_exit_gate_audit_rejects_future_generated_at_timestamp() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_completion_evidence(root)
        payload_path = root / "DESKTOP_EXECUTABLE_EXIT_GATE.generated.json"
        payload = json.loads(payload_path.read_text(encoding="utf-8"))
        payload["generatedAt"] = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=5)).replace(microsecond=0).isoformat().replace(
            "+00:00", "Z"
        )
        payload_path.write_text(json.dumps(payload), encoding="utf-8")

        audit = module._desktop_executable_exit_gate_audit(_args(root))

        assert audit["status"] == "fail"
        assert "timestamp is in the future" in str(audit["reason"])


def test_desktop_executable_exit_gate_audit_rejects_duplicate_external_blocking_rows() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_completion_evidence(root)
        payload_path = root / "DESKTOP_EXECUTABLE_EXIT_GATE.generated.json"
        payload = json.loads(payload_path.read_text(encoding="utf-8"))
        payload.update(
            {
                "status": "fail",
                "reason": "external host proof backlog remains",
                "blockedByExternalConstraintsOnly": True,
                "blockingFindings": ["missing macos host proof", "missing windows host proof"],
                "blockingFindingsCount": 2,
                "localBlockingFindings": [],
                "localBlockingFindingsCount": 0,
                "externalBlockingFindings": ["missing macos host proof", "missing macos host proof"],
                "externalBlockingFindingsCount": 2,
            }
        )
        payload_path.write_text(json.dumps(payload), encoding="utf-8")

        audit = module._desktop_executable_exit_gate_audit(_args(root))

        assert audit["status"] == "fail"
        assert "external blocking findings rows must be unique" in str(audit["reason"])


def test_desktop_executable_exit_gate_audit_rejects_blocking_row_content_mismatch_vs_local_and_external() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_completion_evidence(root)
        payload_path = root / "DESKTOP_EXECUTABLE_EXIT_GATE.generated.json"
        payload = json.loads(payload_path.read_text(encoding="utf-8"))
        payload.update(
            {
                "status": "fail",
                "reason": "blocking findings remain",
                "blockedByExternalConstraintsOnly": False,
                "blockingFindings": ["local gate drift", "unexpected aggregate row"],
                "blockingFindingsCount": 2,
                "localBlockingFindings": ["local gate drift"],
                "localBlockingFindingsCount": 1,
                "externalBlockingFindings": ["missing windows host proof"],
                "externalBlockingFindingsCount": 1,
            }
        )
        payload_path.write_text(json.dumps(payload), encoding="utf-8")

        audit = module._desktop_executable_exit_gate_audit(_args(root))

        assert audit["status"] == "fail"
        assert "must match local plus external finding rows" in str(audit["reason"])


def test_design_completion_audit_rejects_release_proof_warning() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_completion_evidence(root, ui_posture="protected_preview")
        args = _args(root)

        audit = module._design_completion_audit(
            args,
            [
                {
                    "run_id": "run-1",
                    "worker_exit_code": 0,
                    "accepted": True,
                    "acceptance_reason": "",
                    "shipped": "trusted receipt",
                    "remains": "none",
                    "blocker": "none",
                }
            ],
        )

        assert audit["status"] == "fail"
        assert audit["journey_gate_audit"]["status"] == "fail"
        assert audit["journey_gate_audit"]["overall_state"] == "warning"
        assert "before claiming" in audit["reason"]


def test_design_completion_audit_accepts_deferred_nonlinux_external_only_desktop_gate() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_completion_evidence(root)
        payload_path = root / "DESKTOP_EXECUTABLE_EXIT_GATE.generated.json"
        payload = json.loads(payload_path.read_text(encoding="utf-8"))
        payload.update(
            {
                "status": "fail",
                "reason": "Desktop executable exit gate is not fully proven.",
                "blockedByExternalConstraintsOnly": True,
                "localBlockingFindings": [],
                "localBlockingFindingsCount": 0,
                "externalBlockingFindings": [
                    "Windows startup smoke requires a Windows-capable host; current host cannot run promoted Windows installer smoke.",
                    "macOS startup smoke requires a macOS host with hdiutil; current host cannot run promoted macOS installer smoke.",
                ],
                "externalBlockingFindingsCount": 2,
                "blockingFindings": [
                    "Windows startup smoke requires a Windows-capable host; current host cannot run promoted Windows installer smoke.",
                    "macOS startup smoke requires a macOS host with hdiutil; current host cannot run promoted macOS installer smoke.",
                ],
                "blockingFindingsCount": 2,
            }
        )
        payload_path.write_text(json.dumps(payload), encoding="utf-8")
        args = _args(root)

        previous = os.environ.get("CHUMMER_DESIGN_SUPERVISOR_IGNORE_NONLINUX_DESKTOP_HOST_PROOF_BLOCKERS")
        os.environ["CHUMMER_DESIGN_SUPERVISOR_IGNORE_NONLINUX_DESKTOP_HOST_PROOF_BLOCKERS"] = "1"
        try:
            audit = module._design_completion_audit(
                args,
                [
                    {
                        "run_id": "run-1",
                        "worker_exit_code": 0,
                        "accepted": True,
                        "acceptance_reason": "",
                        "shipped": "trusted receipt",
                        "remains": "none",
                        "blocker": "none",
                    }
                ],
            )
        finally:
            if previous is None:
                os.environ.pop("CHUMMER_DESIGN_SUPERVISOR_IGNORE_NONLINUX_DESKTOP_HOST_PROOF_BLOCKERS", None)
            else:
                os.environ["CHUMMER_DESIGN_SUPERVISOR_IGNORE_NONLINUX_DESKTOP_HOST_PROOF_BLOCKERS"] = previous

        assert audit["status"] == "pass"
        assert audit["desktop_executable_exit_gate_audit"]["status"] == "pass"
        assert audit["desktop_executable_exit_gate_audit"]["proof_status"] == "fail"


def test_design_completion_audit_accepts_lagging_weekly_pulse_journey_warning_when_live_proof_is_ready() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_completion_evidence(root, journey_gate_health_state="warning")
        args = _args(root)

        audit = module._design_completion_audit(
            args,
            [
                {
                    "run_id": "run-1",
                    "worker_exit_code": 0,
                    "accepted": True,
                    "acceptance_reason": "",
                    "shipped": "trusted receipt",
                    "remains": "none",
                    "blocker": "none",
                }
            ],
        )

        assert audit["status"] == "pass"
        assert audit["journey_gate_audit"]["status"] == "pass"
        assert audit["weekly_pulse_audit"]["status"] == "pass"
        assert audit["weekly_pulse_audit"]["live_journey_gate_override"] is True
        assert audit["weekly_pulse_audit"]["lagging_journey_gate_health_state"] == "warning"


def test_design_completion_audit_keeps_weekly_pulse_fail_when_release_health_is_not_green() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_completion_evidence(
            root,
            journey_gate_health_state="warning",
            release_health_state="yellow",
        )
        args = _args(root)

        audit = module._design_completion_audit(
            args,
            [
                {
                    "run_id": "run-1",
                    "worker_exit_code": 0,
                    "accepted": True,
                    "acceptance_reason": "",
                    "shipped": "trusted receipt",
                    "remains": "none",
                    "blocker": "none",
                }
            ],
        )

        assert audit["status"] == "fail"
        assert audit["journey_gate_audit"]["status"] == "pass"
        assert audit["weekly_pulse_audit"]["status"] == "fail"
        assert audit["weekly_pulse_audit"].get("live_journey_gate_override") is not True


def test_design_completion_audit_fails_when_weekly_pulse_reports_automation_frontier_misalignment() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_completion_evidence(
            root,
            automation_alignment_state="misaligned",
        )
        args = _args(root)

        audit = module._design_completion_audit(
            args,
            [
                {
                    "run_id": "run-1",
                    "worker_exit_code": 0,
                    "accepted": True,
                    "acceptance_reason": "",
                    "shipped": "trusted receipt",
                    "remains": "none",
                    "blocker": "none",
                }
            ],
        )

        assert audit["status"] == "fail"
        assert audit["journey_gate_audit"]["status"] == "pass"
        assert audit["weekly_pulse_audit"]["status"] == "fail"
        assert "automation frontier misalignment" in str(audit["weekly_pulse_audit"]["reason"]).lower()


def test_design_completion_audit_fails_when_weekly_pulse_missing_launch_governance_decision() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_completion_evidence(root)
        pulse_path = root / "WEEKLY_PRODUCT_PULSE.generated.json"
        pulse_payload = json.loads(pulse_path.read_text(encoding="utf-8"))
        pulse_payload["governor_decisions"] = [
            {
                "decision_id": "fixture-focus",
                "action": "focus_shift",
                "reason": "fixture",
                "cited_signals": ["overall_progress_percent=100"],
            }
        ]
        pulse_payload["snapshot"]["governor_decisions"] = pulse_payload["governor_decisions"]
        pulse_path.write_text(json.dumps(pulse_payload), encoding="utf-8")
        args = _args(root)

        audit = module._design_completion_audit(
            args,
            [
                {
                    "run_id": "run-1",
                    "worker_exit_code": 0,
                    "accepted": True,
                    "acceptance_reason": "",
                    "shipped": "trusted receipt",
                    "remains": "none",
                    "blocker": "none",
                }
            ],
        )

        assert audit["status"] == "fail"
        assert audit["weekly_pulse_audit"]["status"] == "fail"
        assert "launch governance decision" in str(audit["weekly_pulse_audit"]["reason"]).lower()


def test_design_completion_audit_fails_when_weekly_pulse_launch_expand_without_green_canary() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_completion_evidence(root)
        pulse_path = root / "WEEKLY_PRODUCT_PULSE.generated.json"
        pulse_payload = json.loads(pulse_path.read_text(encoding="utf-8"))
        pulse_payload["governor_decisions"] = [
            {
                "decision_id": "fixture-focus",
                "action": "focus_shift",
                "reason": "fixture",
                "cited_signals": ["overall_progress_percent=100"],
            },
            {
                "decision_id": "fixture-launch",
                "action": "launch_expand",
                "reason": "fixture",
                "cited_signals": [
                    "journey_gate_state=ready",
                    "journey_gate_blocked_count=0",
                    "local_release_proof_status=passed",
                    "provider_canary_status=Canary watch on 1 active lane(s)",
                    "closure_health_state=clear",
                ],
            },
        ]
        pulse_payload["snapshot"]["governor_decisions"] = pulse_payload["governor_decisions"]
        pulse_payload["supporting_signals"]["provider_route_stewardship"]["canary_status"] = (
            "Canary watch on 1 active lane(s)"
        )
        pulse_path.write_text(json.dumps(pulse_payload), encoding="utf-8")
        args = _args(root)

        audit = module._design_completion_audit(
            args,
            [
                {
                    "run_id": "run-1",
                    "worker_exit_code": 0,
                    "accepted": True,
                    "acceptance_reason": "",
                    "shipped": "trusted receipt",
                    "remains": "none",
                    "blocker": "none",
                }
            ],
        )

        assert audit["status"] == "fail"
        assert audit["weekly_pulse_audit"]["status"] == "fail"
        assert "launch_expand" in str(audit["weekly_pulse_audit"]["reason"]).lower()


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


def test_run_receipt_status_reheals_stale_false_reject_when_final_message_parses() -> None:
    module = _load_module()

    accepted, reason = module._run_receipt_status(
        {
            "run_id": "run-healed",
            "worker_exit_code": 0,
            "accepted": False,
            "acceptance_reason": "missing structured closeout fields: What shipped, What remains, Exact blocker",
            "final_message": (
                "I am going to fix the blocker.\n"
                '{"decision":"final","text":"What shipped: alpha\\nWhat remains: beta\\nExact blocker: none"}'
            ),
        }
    )

    assert accepted is True
    assert reason == ""


def test_write_runtime_handoff_sanitizes_self_polling_stderr_tail(tmp_path: Path) -> None:
    module = _load_module()
    state_root = tmp_path / "state" / "shard-6"
    run_root = state_root / "runs" / "20260412T062658Z"
    run_root.mkdir(parents=True, exist_ok=True)
    stderr_path = run_root / "worker.stderr.log"
    stderr_path.write_text(
        "\n".join(
            [
                "Trace: lane=core waiting for model output",
                "exec",
                "/usr/bin/bash -lc \"python3 /docker/fleet/scripts/chummer_design_supervisor.py status --state-root /docker/fleet/state/chummer_design_supervisor --json\"",
                "Error: worker_self_polling:supervisor_status_loop",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    last_message_path = run_root / "last_message.txt"
    last_message_path.write_text("Exact blocker: worker_self_polling:supervisor_status_loop\n", encoding="utf-8")
    stdout_path = run_root / "worker.stdout.log"
    stdout_path.write_text("", encoding="utf-8")
    prompt_path = run_root / "prompt.txt"
    prompt_path.write_text("Run the flagship full-product delivery pass.\n", encoding="utf-8")
    module._write_json(
        state_root / "state.json",
        {
            "mode": "flagship_product",
            "focus_profiles": ["top_flagship_grade"],
            "focus_owners": ["fleet"],
            "focus_texts": ["supervisor", "ooda"],
            "frontier_ids": [3109832007],
            "active_run": {
                "run_id": "20260412T062658Z",
                "selected_account_alias": "acct-ea-core-17",
                "selected_model": "ea-coder-hard",
                "started_at": "2026-04-12T06:26:58Z",
                "worker_first_output_at": "2026-04-12T06:27:53Z",
                "worker_last_output_at": "2026-04-12T06:28:29Z",
                "prompt_path": str(prompt_path),
                "stdout_path": str(stdout_path),
                "stderr_path": str(stderr_path),
                "last_message_path": str(last_message_path),
            },
        },
    )

    module._write_runtime_handoff(state_root)

    handoff = (state_root / module.DEFAULT_SHARD_RUNTIME_HANDOFF_FILENAME).read_text(encoding="utf-8")
    assert "Supervisor status polling was observed from inside the active worker run." in handoff
    assert "This is a run-killing contract violation." in handoff
    assert "task-local telemetry" in handoff
    assert "python3 /docker/fleet/scripts/chummer_design_supervisor.py status" not in handoff
    assert "Latest blocker: worker_self_polling:supervisor_status_loop" not in handoff
    assert "Latest blocker: previous run was killed for querying supervisor status inside an active worker run" in handoff


def test_write_runtime_handoff_sanitizes_polling_disabled_status_loop(tmp_path: Path) -> None:
    module = _load_module()
    state_root = tmp_path / "state" / "shard-7"
    run_root = state_root / "runs" / "20260412T211842Z"
    run_root.mkdir(parents=True, exist_ok=True)
    stderr_path = run_root / "worker.stderr.log"
    stderr_path.write_text(
        "\n".join(
            [
                '{"active_runs_count":null,"remaining_open_milestones":null,"eta_human":"polling_disabled","summary":"polling disabled inside active worker run; continue the assigned slice using the prompt, handoff, and frontier artifacts instead of querying supervisor status again"}',
                "",
                "Trace: lane=core waiting for model output",
                "exec",
                '/usr/bin/bash -lc "python3 /docker/fleet/scripts/chummer_design_supervisor.py status --state-root /docker/fleet/state/chummer_design_supervisor --json"',
                'succeeded in 410ms:',
                '{"active_runs_count":null,"remaining_open_milestones":null,"eta_human":"polling_disabled"}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    last_message_path = run_root / "last_message.txt"
    last_message_path.write_text("", encoding="utf-8")
    stdout_path = run_root / "worker.stdout.log"
    stdout_path.write_text("", encoding="utf-8")
    prompt_path = run_root / "prompt.txt"
    prompt_path.write_text("Run the flagship full-product delivery pass.\n", encoding="utf-8")
    module._write_json(
        state_root / "state.json",
        {
            "mode": "flagship_product",
            "focus_profiles": ["top_flagship_grade"],
            "focus_owners": ["fleet"],
            "focus_texts": ["supervisor", "ooda"],
            "frontier_ids": [1300044932],
            "active_run": {
                "run_id": "20260412T211842Z",
                "selected_account_alias": "acct-ea-core-17",
                "selected_model": "ea-coder-hard",
                "started_at": "2026-04-12T21:18:42Z",
                "worker_first_output_at": "2026-04-13T05:18:43Z",
                "worker_last_output_at": "2026-04-13T10:20:51Z",
                "prompt_path": str(prompt_path),
                "stdout_path": str(stdout_path),
                "stderr_path": str(stderr_path),
                "last_message_path": str(last_message_path),
            },
        },
    )

    module._write_runtime_handoff(state_root)

    handoff = (state_root / module.DEFAULT_SHARD_RUNTIME_HANDOFF_FILENAME).read_text(encoding="utf-8")
    assert "Supervisor status polling was observed from inside the active worker run." in handoff
    assert "This is a run-killing contract violation." in handoff
    assert "task-local telemetry" in handoff
    assert "python3 /docker/fleet/scripts/chummer_design_supervisor.py status" not in handoff
    assert "polling_disabled" not in handoff


def test_build_flagship_product_prompt_includes_task_local_status_snapshot(tmp_path: Path) -> None:
    module = _load_module()
    root = tmp_path
    registry_path = root / "registry.yaml"
    registry_path.write_text("waves: []\nmilestones: []\n", encoding="utf-8")
    program_milestones_path = root / "PROGRAM_MILESTONES.yaml"
    program_milestones_path.write_text("product: chummer\n", encoding="utf-8")
    roadmap_path = root / "ROADMAP.md"
    roadmap_path.write_text("# Roadmap\n", encoding="utf-8")
    handoff_path = root / "NEXT_SESSION_HANDOFF.md"
    handoff_path.write_text("handoff\n", encoding="utf-8")
    readiness_path = root / "FLAGSHIP_PRODUCT_READINESS.generated.json"
    readiness_path.write_text("{}\n", encoding="utf-8")
    frontier_artifact_path = root / "FULL_PRODUCT_FRONTIER.generated.yaml"
    frontier_artifact_path.write_text("frontier: []\n", encoding="utf-8")
    frontier = [
        module.Milestone(
            id=4066417069,
            title="Flagship desktop client and workbench finish",
            wave="W4",
            status="not_started",
            owners=["chummer6-ui"],
            exit_criteria=["Ship the flagship workbench."],
            dependencies=[],
        )
    ]

    prompt = module.build_flagship_product_prompt(
        registry_path=registry_path,
        program_milestones_path=program_milestones_path,
        roadmap_path=roadmap_path,
        handoff_path=handoff_path,
        runtime_handoff_path=None,
        readiness_path=readiness_path,
        frontier_artifact_path=frontier_artifact_path,
        frontier=frontier,
        scope_roots=[root],
        focus_profiles=["top_flagship_grade"],
        focus_owners=["fleet"],
        focus_texts=["desktop client"],
        completion_audit={"status": "fail", "reason": "untrusted receipt"},
        full_product_audit={"status": "fail", "reason": "missing desktop_client", "missing_coverage_keys": ["desktop_client"]},
        history=[],
        eta_snapshot={
            "active_runs_count": 13,
            "eta_human": "5d-1.4w",
            "remaining_open_milestones": 8,
            "remaining_in_progress_milestones": 5,
            "remaining_not_started_milestones": 3,
            "scope_kind": "open_milestone_frontier",
        },
        compact_prompt=True,
    )

    assert "Task-local run context:" in prompt
    assert "- eta: 5d-1.4w" in prompt
    assert "- remaining open milestones: 8" in prompt
    assert "- remaining in-progress milestones: 5" in prompt
    assert "- remaining not-started milestones: 3" in prompt
    assert "verbatim task-local telemetry snapshot is embedded below" in prompt
    assert "do not regenerate it via shell, Python, or supervisor helper commands" in prompt
    assert '{"active_runs_count":13,"remaining_open_milestones":8,"remaining_not_started_milestones":3,"remaining_in_progress_milestones":5,"eta_human":"5d-1.4w","summary":null}' in prompt
    assert "Operator telemetry CLI is forbidden during active worker runs." in prompt
    assert "python3 /docker/fleet/scripts/chummer_design_supervisor.py status --json" not in prompt
    assert "python3 /docker/fleet/scripts/chummer_design_supervisor.py eta --json" not in prompt


def test_build_flagship_product_prompt_uses_runtime_handoff_not_shared_handoff_path(tmp_path: Path) -> None:
    module = _load_module()
    root = tmp_path
    registry_path = root / "registry.yaml"
    registry_path.write_text("waves: []\nmilestones: []\n", encoding="utf-8")
    program_milestones_path = root / "PROGRAM_MILESTONES.yaml"
    program_milestones_path.write_text("product: chummer\n", encoding="utf-8")
    roadmap_path = root / "ROADMAP.md"
    roadmap_path.write_text("# Roadmap\n", encoding="utf-8")
    handoff_path = root / "NEXT_SESSION_HANDOFF.md"
    handoff_path.write_text("operator-only handoff\n", encoding="utf-8")
    runtime_handoff_path = root / "ACTIVE_RUN_HANDOFF.generated.md"
    runtime_handoff_path.write_text("worker-safe handoff\n", encoding="utf-8")
    readiness_path = root / "FLAGSHIP_PRODUCT_READINESS.generated.json"
    readiness_path.write_text("{}\n", encoding="utf-8")
    frontier_artifact_path = root / "FULL_PRODUCT_FRONTIER.generated.yaml"
    frontier_artifact_path.write_text("frontier: []\n", encoding="utf-8")

    prompt = module.build_flagship_product_prompt(
        registry_path=registry_path,
        program_milestones_path=program_milestones_path,
        roadmap_path=roadmap_path,
        handoff_path=handoff_path,
        runtime_handoff_path=runtime_handoff_path,
        readiness_path=readiness_path,
        frontier_artifact_path=frontier_artifact_path,
        frontier=[],
        scope_roots=[root],
        focus_profiles=["top_flagship_grade"],
        focus_owners=["fleet"],
        focus_texts=["desktop client"],
        completion_audit={"status": "fail", "reason": "untrusted receipt"},
        full_product_audit={"status": "fail", "reason": "missing desktop_client", "missing_coverage_keys": ["desktop_client"]},
        history=[],
        eta_snapshot={"eta_human": "tracked"},
        compact_prompt=True,
    )

    assert str(runtime_handoff_path) in prompt
    assert str(handoff_path) not in prompt
    assert "shared operator handoff is operator-only" in prompt
    assert "do not open it or execute commands from it inside worker runs" in prompt
    assert "historical operator status snippets" in prompt
    assert "NEXT_SESSION_HANDOFF" not in prompt


def test_estimate_full_product_eta_reports_frontier_counts() -> None:
    module = _load_module()
    frontier = [
        module.Milestone(
            id=1,
            title="Desktop flagship",
            wave="W4",
            status="in_progress",
            owners=["chummer6-ui"],
            exit_criteria=["Ship desktop"],
            dependencies=[],
        ),
        module.Milestone(
            id=2,
            title="Hub route",
            wave="W4",
            status="not_started",
            owners=["chummer6-hub"],
            exit_criteria=["Ship hub"],
            dependencies=[],
        ),
    ]

    snapshot = module._estimate_full_product_eta(
        frontier,
        {"missing_coverage_keys": ["desktop_client"]},
        [],
        dt.datetime(2026, 4, 13, 10, 0, 0, tzinfo=dt.timezone.utc),
    )

    assert snapshot["remaining_open_milestones"] == 2
    assert snapshot["remaining_in_progress_milestones"] == 1
    assert snapshot["remaining_not_started_milestones"] == 1


def test_estimate_full_product_milestone_eta_reports_distinct_ranges() -> None:
    module = _load_module()
    desktop = module.Milestone(
        id=1,
        title="Flagship desktop client and workbench finish",
        wave="flagship_product",
        status="not_started",
        owners=["chummer6-ui", "chummer6-core", "chummer6-ui-kit"],
        exit_criteria=["Ship desktop workbench, packaging, updater, and support polish."],
        dependencies=[],
    )
    fleet = module.Milestone(
        id=2,
        title="Fleet and operator loop flagship finish",
        wave="flagship_product",
        status="not_started",
        owners=["fleet", "executive-assistant", "chummer6-design", "chummer6-hub"],
        exit_criteria=["Keep the operator loop durable with proofs, traces, ETAs, and handoffs."],
        dependencies=[],
    )

    desktop_eta = module._estimate_full_product_milestone_eta(
        desktop,
        {"missing_coverage_keys": ["desktop_client"]},
        [],
        dt.datetime(2026, 4, 13, 10, 0, 0, tzinfo=dt.timezone.utc),
    )
    fleet_eta = module._estimate_full_product_milestone_eta(
        fleet,
        {"missing_coverage_keys": ["desktop_client"]},
        [],
        dt.datetime(2026, 4, 13, 10, 0, 0, tzinfo=dt.timezone.utc),
    )

    assert desktop_eta["remaining_open_milestones"] == 1
    assert fleet_eta["remaining_open_milestones"] == 1
    assert desktop_eta["range_low_hours"] > fleet_eta["range_low_hours"]
    assert desktop_eta["range_high_hours"] > fleet_eta["range_high_hours"]
    assert "Flagship desktop client and workbench finish" in desktop_eta["summary"]


def test_build_eta_snapshot_uses_scope_frontier_for_idle_flagship_delivery() -> None:
    module = _load_module()
    scope_frontier = [
        module.Milestone(
            id=1,
            title="Desktop flagship",
            wave="W4",
            status="in_progress",
            owners=["chummer6-ui"],
            exit_criteria=["Ship desktop"],
            dependencies=[],
        ),
        module.Milestone(
            id=2,
            title="Hub route",
            wave="W4",
            status="not_started",
            owners=["chummer6-hub"],
            exit_criteria=["Ship hub"],
            dependencies=[],
        ),
    ]

    eta = module._build_eta_snapshot(
        mode="flagship_product",
        open_milestones=[],
        frontier=[],
        scope_frontier=scope_frontier,
        history=[],
        full_product_audit={"status": "fail", "missing_coverage_keys": ["desktop_client"]},
        now=module._parse_iso("2026-04-13T10:00:00Z"),
    )

    assert eta["status"] == "flagship_delivery"
    assert eta["remaining_open_milestones"] == 2
    assert eta["remaining_in_progress_milestones"] == 1
    assert eta["remaining_not_started_milestones"] == 1
    assert "2 synthetic slices" in eta["summary"]


def test_build_eta_snapshot_uses_single_milestone_flagship_eta_for_active_flagship_slice() -> None:
    module = _load_module()
    milestone = module.Milestone(
        id=4066417069,
        title="Flagship desktop client and workbench finish",
        wave="flagship_product",
        status="in_progress",
        owners=["chummer6-ui", "chummer6-core", "chummer6-ui-kit"],
        exit_criteria=["Ship desktop workbench, packaging, updater, and support polish."],
        dependencies=[],
    )

    eta = module._build_eta_snapshot(
        mode="flagship_product",
        open_milestones=[milestone],
        frontier=[milestone],
        history=[],
        full_product_audit={"status": "fail", "missing_coverage_keys": ["desktop_client"]},
        now=module._parse_iso("2026-04-13T10:00:00Z"),
    )
    expected = module._estimate_full_product_milestone_eta(
        milestone,
        {"status": "fail", "missing_coverage_keys": ["desktop_client"]},
        [],
        module._parse_iso("2026-04-13T10:00:00Z"),
    )

    assert eta["basis"] == "full_product_single_milestone_heuristic"
    assert eta["scope_kind"] == "flagship_product_readiness"
    assert eta["remaining_open_milestones"] == 1
    assert eta["range_low_hours"] == expected["range_low_hours"]
    assert eta["range_high_hours"] == expected["range_high_hours"]
    assert "Flagship desktop client and workbench finish" in eta["summary"]


def test_build_eta_snapshot_prefers_local_flagship_slice_over_wider_scope_frontier() -> None:
    module = _load_module()
    local_milestone = module.Milestone(
        id=4066417069,
        title="Flagship desktop client and workbench finish",
        wave="flagship_product",
        status="in_progress",
        owners=["chummer6-ui", "chummer6-core", "chummer6-ui-kit"],
        exit_criteria=["Ship desktop workbench, packaging, updater, and support polish."],
        dependencies=[],
    )
    scope_frontier = [
        local_milestone,
        module.Milestone(
            id=2541792707,
            title="Hub, registry, and public front door flagship finish",
            wave="flagship_product",
            status="in_progress",
            owners=["chummer6-hub", "chummer6-hub-registry", "chummer6-design"],
            exit_criteria=["Finish hub, registry, and public front door closeout."],
            dependencies=[],
        ),
    ]

    eta = module._build_eta_snapshot(
        mode="flagship_product",
        open_milestones=[local_milestone],
        frontier=[local_milestone],
        scope_frontier=scope_frontier,
        history=[],
        full_product_audit={"status": "fail", "missing_coverage_keys": ["desktop_client"]},
        now=module._parse_iso("2026-04-13T10:00:00Z"),
    )

    expected = module._estimate_full_product_milestone_eta(
        local_milestone,
        {"status": "fail", "missing_coverage_keys": ["desktop_client"]},
        [],
        module._parse_iso("2026-04-13T10:00:00Z"),
    )

    assert eta["basis"] == "full_product_single_milestone_heuristic"
    assert eta["range_low_hours"] == expected["range_low_hours"]
    assert eta["range_high_hours"] == expected["range_high_hours"]


def test_idle_scope_frontier_rebuilds_flagship_scope_when_context_omits_it(tmp_path: Path) -> None:
    module = _load_module()
    args = _args(tmp_path)
    state_root = tmp_path / "state" / "chummer_design_supervisor" / "shard-4"
    state_root.mkdir(parents=True, exist_ok=True)
    frontier = [
        module.Milestone(
            id=1,
            title="Desktop flagship",
            wave="W4",
            status="in_progress",
            owners=["chummer6-ui"],
            exit_criteria=["Ship desktop"],
            dependencies=[],
        ),
        module.Milestone(
            id=2,
            title="Hub route",
            wave="W4",
            status="not_started",
            owners=["chummer6-hub"],
            exit_criteria=["Ship hub"],
            dependencies=[],
        ),
    ]

    module._full_product_frontier = lambda _args: list(frontier)
    module._prior_active_shard_frontier_ids = lambda _state_root: [1]

    scope = module._idle_scope_frontier(
        args,
        state_root,
        {"full_product_audit": {"status": "fail"}},
        [],
    )

    assert [item.id for item in scope] == [2]


def test_aggregate_idle_eta_snapshot_prefers_aggregate_eta(tmp_path: Path) -> None:
    module = _load_module()
    aggregate_root = tmp_path / "state" / "chummer_design_supervisor"
    shard_root = aggregate_root / "shard-4"
    shard_root.mkdir(parents=True, exist_ok=True)
    module._write_json(
        aggregate_root / "state.json",
        {
            "updated_at": "2026-04-13T19:43:15Z",
            "eta": {
                "status": "tracked",
                "summary": "4 open milestones remain (4 in progress, 0 not started).",
                "eta_human": "tracked",
                "eta_confidence": "low",
                "remaining_open_milestones": 4,
                "remaining_in_progress_milestones": 4,
                "remaining_not_started_milestones": 0,
                "range_low_hours": 25.0,
                "range_high_hours": 62.5,
                "scope_kind": "flagship_product_readiness",
                "scope_label": "Full Chummer5A parity and flagship proof closeout",
            },
        },
    )

    eta = module._aggregate_idle_eta_snapshot(shard_root)

    assert eta is not None
    assert eta["status"] == "tracked"
    assert eta["remaining_open_milestones"] == 4
    assert eta["scope_kind"] == "flagship_product_readiness"


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
        _write_completion_evidence(root)
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


def test_design_completion_audit_fails_when_repo_backlog_remains_outside_registry() -> None:
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
        _write_completion_evidence(root)
        _write_project_backlog(
            root,
            project_id="ui",
            repo_slug="chummer6-ui",
            task="Finish ruleset-specific workbench adaptation lane",
        )
        args = _args(root)

        audit = module._design_completion_audit(
            args,
            [
                {
                    "run_id": "run-1",
                    "worker_exit_code": 0,
                    "accepted": True,
                    "acceptance_reason": "",
                    "shipped": "trusted receipt",
                    "remains": "none",
                    "blocker": "none",
                }
            ],
        )

        assert audit["status"] == "fail"
        assert audit["repo_backlog_audit"]["status"] == "fail"
        assert audit["repo_backlog_audit"]["open_item_count"] == 1
        assert audit["repo_backlog_audit"]["open_items"][0]["project_id"] == "ui"
        assert "ruleset-specific workbench adaptation lane" in audit["repo_backlog_audit"]["open_items"][0]["task"]


def test_design_completion_audit_includes_absolute_secondary_worklist_sources() -> None:
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
        _write_completion_evidence(root)
        projects_dir = root / "projects"
        projects_dir.mkdir(parents=True, exist_ok=True)
        ui_root = root / "chummer6-ui"
        presentation_root = root / "chummer-presentation"
        ui_root.mkdir(parents=True, exist_ok=True)
        presentation_root.mkdir(parents=True, exist_ok=True)
        (ui_root / "WORKLIST.md").write_text("- [done] wl-217 Close Chummer5a desktop parity\n", encoding="utf-8")
        presentation_task = "Close SR4 desktop workflow parity against Chummer4"
        (presentation_root / "WORKLIST.md").write_text(
            f"- [queued] wl-218 {presentation_task}\n",
            encoding="utf-8",
        )
        (projects_dir / "ui.yaml").write_text(
            yaml.safe_dump(
                {
                    "id": "ui",
                    "path": str(ui_root),
                    "review": {"repo": "chummer6-ui"},
                    "queue": [],
                    "queue_sources": [
                        {"kind": "worklist", "path": "WORKLIST.md", "mode": "replace"},
                        {
                            "kind": "worklist",
                            "path": str(presentation_root / "WORKLIST.md"),
                            "mode": "append",
                        },
                    ],
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        args = _args(root)

        audit = module._design_completion_audit(
            args,
            [
                {
                    "run_id": "run-1",
                    "worker_exit_code": 0,
                    "accepted": True,
                    "acceptance_reason": "",
                    "shipped": "trusted receipt",
                    "remains": "none",
                    "blocker": "none",
                }
            ],
        )

        assert audit["status"] == "fail"
        assert audit["repo_backlog_audit"]["status"] == "fail"
        assert audit["repo_backlog_audit"]["open_item_count"] == 1
        assert audit["repo_backlog_audit"]["open_items"][0]["project_id"] == "ui"
        assert presentation_task in audit["repo_backlog_audit"]["open_items"][0]["task"]


def test_repo_backlog_audit_scopes_to_focus_owners() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_completion_evidence(root)
        ui_task = "Close the focused UI flagship slice."
        core_task = "Ignore unrelated core backlog during this focused shard."
        _write_project_backlog(root, project_id="ui", repo_slug="chummer6-ui", task=ui_task)
        _write_project_backlog(root, project_id="core", repo_slug="chummer6-core", task=core_task)
        args = _args(root)
        args.focus_owner = ["chummer6-ui"]

        audit = module._repo_backlog_audit(args)

        assert audit["status"] == "fail"
        assert audit["open_item_count"] == 1
        assert audit["open_items"][0]["project_id"] == "ui"
        assert ui_task in audit["open_items"][0]["task"]


def test_design_completion_audit_rejects_false_complete_receipt_when_repo_backlog_is_open() -> None:
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
        _write_completion_evidence(root)
        _write_project_backlog(
            root,
            project_id="ui",
            repo_slug="chummer6-ui",
            task="Close SR4 desktop workflow parity against Chummer4",
        )
        args = _args(root)

        audit = module._design_completion_audit(
            args,
            [
                {
                    "run_id": "run-1",
                    "worker_exit_code": 0,
                    "accepted": True,
                    "acceptance_reason": "",
                    "shipped": "Closed the queue.",
                    "remains": "none",
                    "blocker": "none",
                    "final_message": (
                        "What shipped: Closed the queue.\n"
                        "What remains: none.\n"
                        "Exact blocker: none.\n"
                    ),
                }
            ],
        )

        assert audit["status"] == "fail"
        assert audit["receipt_audit"]["status"] == "fail"
        assert audit["receipt_audit"]["contradiction"] == "repo_backlog"
        assert audit["receipt_audit"]["latest_run_id"] == "run-1"
        assert "contradicts live repo backlog" in audit["receipt_audit"]["reason"]
        assert "SR4 desktop workflow parity" in audit["receipt_audit"]["latest_run_reason"]


def test_design_completion_audit_prioritizes_live_backlog_reason_over_failed_worker_receipt() -> None:
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
        _write_completion_evidence(root)
        _write_project_backlog(
            root,
            project_id="fleet",
            repo_slug="fleet",
            task="Make fleet trust and status publication strictly live-truth",
        )
        args = _args(root)

        audit = module._design_completion_audit(
            args,
            [
                {
                    "run_id": "run-worker-failed",
                    "worker_exit_code": 1,
                    "accepted": False,
                    "acceptance_reason": "worker exit 1",
                    "blocker": "worker exit 1",
                    "final_message": (
                        "What shipped:\n\n"
                        "What remains:\n\n"
                        "Exact blocker: worker exit 1\n"
                    ),
                }
            ],
        )

        assert audit["status"] == "fail"
        assert audit["reason"].startswith("active repo-local backlog remains")
        assert audit["receipt_audit"]["status"] == "fail"
        assert "latest worker receipt run-worker-failed is not trusted" in audit["receipt_audit"]["reason"]
        assert audit["blocking_audits"][0]["component"] == "repo_backlog"
        assert audit["blocking_audits"][-1]["component"] == "trusted_completion_receipt"


def test_design_completion_audit_keeps_partial_progress_receipt_trusted_when_repo_backlog_is_open() -> None:
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
        _write_completion_evidence(root)
        _write_project_backlog(
            root,
            project_id="ui",
            repo_slug="chummer6-ui",
            task="Close SR4 desktop workflow parity against Chummer4",
        )
        args = _args(root)

        audit = module._design_completion_audit(
            args,
            [
                {
                    "run_id": "run-2",
                    "worker_exit_code": 0,
                    "accepted": True,
                    "acceptance_reason": "",
                    "shipped": "Built three SR4 family receipts.",
                    "remains": "Need the remaining SR4 family receipts.",
                    "blocker": "none",
                    "final_message": (
                        "What shipped: Built three SR4 family receipts.\n"
                        "What remains: Need the remaining SR4 family receipts.\n"
                        "Exact blocker: none.\n"
                    ),
                }
            ],
        )

        assert audit["status"] == "fail"
        assert audit["repo_backlog_audit"]["status"] == "fail"
        assert audit["receipt_audit"]["status"] == "pass"
        assert "contradiction" not in audit["receipt_audit"]


def test_completion_review_frontier_drops_stale_generic_history_targets() -> None:
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
        _write_completion_evidence(root)
        _write_project_backlog(
            root,
            project_id="ui",
            repo_slug="chummer6-ui",
            task="Finish ruleset-specific workbench adaptation lane",
        )
        args = _args(root)
        audit = module._design_completion_audit(args, [])
        frontier = module._completion_review_frontier(
            audit,
            (root / "registry.yaml").resolve(),
            [
                {
                    "run_id": "run-stale",
                    "worker_exit_code": 0,
                    "accepted": False,
                    "acceptance_reason": "Error: survival_no_backend_available",
                    "frontier_ids": [999999001],
                    "primary_milestone_id": 999999001,
                }
            ],
        )

        frontier_ids = [item.id for item in frontier]
        assert 999999001 not in frontier_ids


def test_derive_completion_review_context_synthesizes_repo_backlog_milestones() -> None:
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
        _write_completion_evidence(root)
        task = "Finish ruleset-specific workbench adaptation lane"
        _write_project_backlog(root, project_id="ui", repo_slug="chummer6-ui", task=task)
        state_root = root / "state"
        state_root.mkdir(parents=True, exist_ok=True)
        history = [
            {
                "run_id": "run-good",
                "worker_exit_code": 0,
                "accepted": True,
                "acceptance_reason": "",
                "shipped": "trusted receipt",
                "remains": "none",
                "blocker": "none",
            }
        ]
        (state_root / "history.jsonl").write_text(json.dumps(history[0]) + "\n", encoding="utf-8")
        args = _args(root)
        base_context = module.derive_context(args)
        audit = module._design_completion_audit(args, history)

        context = module.derive_completion_review_context(args, state_root, base_context=base_context, audit=audit)
        synthetic_id = module._synthetic_completion_review_id(f"repo-backlog:ui:{task}")
        frontier_path = root / ".codex-studio" / "published" / "COMPLETION_REVIEW_FRONTIER.generated.yaml"
        mirror_path = root / "state" / "artifacts" / "COMPLETION_REVIEW_FRONTIER.generated.yaml"

        assert context["frontier_ids"] == [synthetic_id]
        assert "Repo backlog: ui: Finish ruleset-specific workbench adaptation lane" in context["prompt"]
        assert "Repo-local backlog gaps" in context["prompt"]
        assert str(frontier_path) in context["prompt"]
        assert context["completion_review_frontier_path"] == str(frontier_path)
        assert context["completion_review_frontier_mirror_path"] == str(mirror_path)
        frontier_payload = yaml.safe_load(frontier_path.read_text(encoding="utf-8"))
        mirror_payload = yaml.safe_load(mirror_path.read_text(encoding="utf-8"))
        assert frontier_payload["contract_name"] == "fleet.completion_review_frontier"
        assert frontier_payload["mode"] == "completion_review"
        assert frontier_payload["frontier_ids"] == [synthetic_id]
        assert frontier_payload["repo_backlog_audit"]["open_item_count"] == 1
        assert mirror_payload["frontier_ids"] == [synthetic_id]


def test_completion_review_frontier_decomposes_visual_familiarity_backlog() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "registry.yaml").write_text("waves: []\nmilestones: []\n", encoding="utf-8")
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("Everything is done.\n", encoding="utf-8")
        _write_completion_evidence(root)
        _write_project_backlog_tasks(
            root,
            project_id="ui",
            repo_slug="chummer6-ui",
            tasks=[
                "Add a release-blocking desktop visual familiarity gate so flagship desktop readiness requires Chummer-adjacent light/dark palette anchors, compact classic shell posture, and a visible loaded-runner tab rhythm instead of passing on executable proof alone.",
                "Add workflow-local visual familiarity proof for the dense legacy builder surfaces so character creation, gear, armor, weapons, cyberware, cyberlimbs, magic/resonance, and vehicle/drone workflows keep a Chummer-familiar browse/detail/confirm mental model instead of only passing data-parity receipts.",
            ],
        )
        args = _args(root)
        audit = module._design_completion_audit(args, [])

        frontier = module._completion_review_frontier(audit, Path(args.registry_path).resolve(), [])
        titles = [item.title for item in frontier]

        assert titles == [
            "Repo backlog: ui: Desktop shell visual familiarity",
            "Repo backlog: ui: Theme readability and loaded-runner tab posture",
            "Repo backlog: ui: Character creation and gear workflow visual familiarity",
            "Repo backlog: ui: Cyberware and cyberlimb dialog familiarity",
            "Repo backlog: ui: SR4 and SR6 workflow orientation familiarity",
        ]


def test_synthetic_completion_review_milestone_keeps_all_external_proof_requests() -> None:
    module = _load_module()

    milestone = module._synthetic_completion_review_milestone(
        key="install-proof",
        title="Completion gate: Install, claim, restore, continue",
        owners=["fleet"],
        exit_criteria=[
            "repo proof field one mismatch",
            "repo proof field two mismatch",
            "repo proof field three mismatch",
            "release_channel.generated.json field 'desktopTupleCoverage.missingRequiredPlatformHeadRidTuples' external proof request: capture promoted_installer_artifact on windows host for tuple avalonia:win-x64:windows.",
            "release_channel.generated.json field 'desktopTupleCoverage.missingRequiredPlatformHeadRidTuples' external proof request: capture promoted_installer_artifact on windows host for tuple blazor-desktop:win-x64:windows.",
            "release_channel.generated.json field 'desktopTupleCoverage.missingRequiredPlatformHeadRidTuples' external proof request: capture promoted_installer_artifact on macos host for tuple avalonia:osx-arm64:macos.",
            "release_channel.generated.json field 'desktopTupleCoverage.missingRequiredPlatformHeadRidTuples' external proof request: capture promoted_installer_artifact on macos host for tuple blazor-desktop:osx-arm64:macos.",
        ],
    )

    assert len(milestone.exit_criteria) == 7
    assert sum("external proof request:" in item.lower() for item in milestone.exit_criteria) == 4


def test_synthetic_completion_review_milestone_still_caps_non_external_criteria() -> None:
    module = _load_module()

    milestone = module._synthetic_completion_review_milestone(
        key="generic-backlog",
        title="Completion gate: generic",
        owners=["fleet"],
        exit_criteria=[
            "one",
            "two",
            "three",
            "four",
            "five",
        ],
    )

    assert milestone.exit_criteria == ["one", "two", "three", "four"]


def test_derive_completion_review_context_adds_visual_familiarity_focus_and_guidance() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "registry.yaml").write_text("waves: []\nmilestones: []\n", encoding="utf-8")
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("Everything is done.\n", encoding="utf-8")
        _write_completion_evidence(root)
        _write_project_backlog_tasks(
            root,
            project_id="ui",
            repo_slug="chummer6-ui",
            tasks=[
                "Add a release-blocking desktop visual familiarity gate so flagship desktop readiness requires Chummer-adjacent light/dark palette anchors, compact classic shell posture, and a visible loaded-runner tab rhythm instead of passing on executable proof alone.",
                "Add workflow-local visual familiarity proof for the dense legacy builder surfaces so character creation, gear, armor, weapons, cyberware, cyberlimbs, magic/resonance, and vehicle/drone workflows keep a Chummer-familiar browse/detail/confirm mental model instead of only passing data-parity receipts.",
            ],
        )
        state_root = root / "state"
        state_root.mkdir(parents=True, exist_ok=True)
        args = _args(root)

        context = module.derive_completion_review_context(
            args,
            state_root,
            base_context=module.derive_context(args),
            audit=module._design_completion_audit(args, []),
        )

        assert context["focus_profiles"] == ["desktop_visual_familiarity"]
        assert "cyberware" in context["focus_texts"]
        assert "palette" in context["focus_texts"]
        assert str(Path("/docker/fleet/.codex-design/product/CHUMMER5A_FAMILIARITY_BRIDGE.md")) in context["prompt"]
        assert str(Path("/docker/fleet/.codex-design/product/DESKTOP_VISUAL_FAMILIARITY_EXIT_GATE.md")) in context["prompt"]
        assert len(context["frontier_ids"]) == 5


def test_derive_completion_review_context_fair_shares_visual_familiarity_backlog_across_three_shards() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "registry.yaml").write_text("waves: []\nmilestones: []\n", encoding="utf-8")
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("Everything is done.\n", encoding="utf-8")
        _write_completion_evidence(root)
        _write_project_backlog_tasks(
            root,
            project_id="ui",
            repo_slug="chummer6-ui",
            tasks=[
                "Add a release-blocking desktop visual familiarity gate so flagship desktop readiness requires Chummer-adjacent light/dark palette anchors, compact classic shell posture, and a visible loaded-runner tab rhythm instead of passing on executable proof alone.",
                "Add workflow-local visual familiarity proof for the dense legacy builder surfaces so character creation, gear, armor, weapons, cyberware, cyberlimbs, magic/resonance, and vehicle/drone workflows keep a Chummer-familiar browse/detail/confirm mental model instead of only passing data-parity receipts.",
            ],
        )
        aggregate_root = root / "state" / "chummer_design_supervisor"
        shard_one_root = aggregate_root / "shard-1"
        shard_two_root = aggregate_root / "shard-2"
        shard_three_root = aggregate_root / "shard-3"
        for shard_root in (shard_one_root, shard_two_root, shard_three_root):
            shard_root.mkdir(parents=True, exist_ok=True)

        args = _args(root)
        audit = module._design_completion_audit(args, [])
        full_frontier_ids = [item.id for item in module._completion_review_frontier(audit, Path(args.registry_path).resolve(), [])]

        context_one = module.derive_completion_review_context(
            args,
            shard_one_root,
            base_context=module.derive_context(args),
            audit=audit,
        )
        module._write_json(
            shard_one_root / "state.json",
            {
                "updated_at": "2026-04-03T06:02:00Z",
                "mode": "completion_review",
                "frontier_ids": context_one["frontier_ids"],
                "active_run": {
                    "run_id": "run-1",
                    "frontier_ids": context_one["frontier_ids"],
                    "open_milestone_ids": [],
                },
            },
        )

        context_two = module.derive_completion_review_context(
            args,
            shard_two_root,
            base_context=module.derive_context(args),
            audit=audit,
        )
        module._write_json(
            shard_two_root / "state.json",
            {
                "updated_at": "2026-04-03T06:02:05Z",
                "mode": "completion_review",
                "frontier_ids": context_two["frontier_ids"],
                "active_run": {
                    "run_id": "run-2",
                    "frontier_ids": context_two["frontier_ids"],
                    "open_milestone_ids": [],
                },
            },
        )

        context_three = module.derive_completion_review_context(
            args,
            shard_three_root,
            base_context=module.derive_context(args),
            audit=audit,
        )

        combined_ids = context_one["frontier_ids"] + context_two["frontier_ids"] + context_three["frontier_ids"]

        assert len(full_frontier_ids) == 5
        assert len(context_one["frontier_ids"]) == 2
        assert len(context_two["frontier_ids"]) == 2
        assert len(context_three["frontier_ids"]) == 1
        assert sorted(combined_ids) == sorted(full_frontier_ids)
        assert len(set(combined_ids)) == len(full_frontier_ids)
        assert context_one["focus_profiles"] == ["desktop_visual_familiarity"]
        assert context_two["focus_profiles"] == ["desktop_visual_familiarity"]
        assert context_three["focus_profiles"] == ["desktop_visual_familiarity"]


def test_completion_review_frontier_decomposes_workflow_depth_backlog() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "registry.yaml").write_text("waves: []\nmilestones: []\n", encoding="utf-8")
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("Everything is done.\n", encoding="utf-8")
        _write_completion_evidence(root)
        _write_project_backlog_tasks(
            root,
            project_id="ui",
            repo_slug="chummer6-ui",
            tasks=[
                "Add exhaustive executable desktop workflow click-through and binary UX proof so packaged Avalonia and Blazor Desktop builds prove live menu wiring, demo-runner discovery, Spotlight-launchable app posture, public feedback routes, and smooth builder journeys for character creation, karma, critters, adept powers, initiation, cyberdeck/programs, spells, drugs, contacts, diary/career-log, spirits/familiars, and vehicles/drones/rigger flows.",
            ],
        )
        args = _args(root)
        audit = module._design_completion_audit(args, [])

        frontier = module._completion_review_frontier(audit, Path(args.registry_path).resolve(), [])
        titles = [item.title for item in frontier]

        assert titles == [
            "Repo backlog: ui: Desktop shell and binary first-run smoothness",
            "Repo backlog: ui: Character creation, karma, and advancement workflow depth",
            "Repo backlog: ui: Magic, matrix, and consumables workflow depth",
            "Repo backlog: ui: Contacts, diary, and support-loop workflow depth",
            "Repo backlog: ui: Spirits, critters, familiars, vehicles, and rigger workflow depth",
        ]


def test_derive_completion_review_context_adds_workflow_depth_focus_and_guidance() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "registry.yaml").write_text("waves: []\nmilestones: []\n", encoding="utf-8")
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("Everything is done.\n", encoding="utf-8")
        _write_completion_evidence(root)
        _write_project_backlog_tasks(
            root,
            project_id="ui",
            repo_slug="chummer6-ui",
            tasks=[
                "Add exhaustive executable desktop workflow click-through and binary UX proof so packaged Avalonia and Blazor Desktop builds prove live menu wiring, demo-runner discovery, Spotlight-launchable app posture, public feedback routes, and smooth builder journeys for character creation, karma, critters, adept powers, initiation, cyberdeck/programs, spells, drugs, contacts, diary/career-log, spirits/familiars, and vehicles/drones/rigger flows.",
            ],
        )
        state_root = root / "state"
        state_root.mkdir(parents=True, exist_ok=True)
        args = _args(root)

        context = module.derive_completion_review_context(
            args,
            state_root,
            base_context=module.derive_context(args),
            audit=module._design_completion_audit(args, []),
        )

        assert context["focus_profiles"] == ["desktop_visual_familiarity", "desktop_workflow_depth"]
        assert "spotlight-launchable" in context["focus_texts"]
        assert "adept powers" in context["focus_texts"]
        assert str(Path("/docker/fleet/.codex-design/product/DESKTOP_EXECUTABLE_EXIT_GATES.md")) in context["prompt"]
        assert str(Path("/docker/fleet/.codex-design/product/CHUMMER5A_FAMILIARITY_BRIDGE.md")) in context["prompt"]
        assert len(context["frontier_ids"]) == 5


def test_derive_completion_review_context_uses_shard_specific_frontier_artifacts() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "registry.yaml").write_text("waves: []\nmilestones: []\n", encoding="utf-8")
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("Everything is done.\n", encoding="utf-8")
        _write_completion_evidence(root)
        task = "Publish and execute the ruleset-specific workbench adaptation lane"
        _write_project_backlog(root, project_id="ui", repo_slug="chummer6-ui", task=task)
        aggregate_root = root / "state" / "chummer_design_supervisor"
        shard_root = aggregate_root / "shard-2"
        shard_root.mkdir(parents=True, exist_ok=True)
        history = [
            {
                "run_id": "run-good",
                "worker_exit_code": 0,
                "accepted": True,
                "acceptance_reason": "",
                "shipped": "trusted receipt",
                "remains": "none",
                "blocker": "none",
            }
        ]
        (shard_root / "history.jsonl").write_text(json.dumps(history[0]) + "\n", encoding="utf-8")
        args = _args(root)
        base_context = module.derive_context(args)
        audit = module._design_completion_audit(args, history)

        context = module.derive_completion_review_context(args, shard_root, base_context=base_context, audit=audit)

        frontier_path = (
            root / ".codex-studio" / "published" / "completion-review-frontiers" / "shard-2.generated.yaml"
        )
        mirror_path = (
            root / "state" / "chummer_design_supervisor" / "artifacts" / "completion-review-frontiers" / "shard-2.generated.yaml"
        )
        assert context["completion_review_frontier_path"] == str(frontier_path)
        assert context["completion_review_frontier_mirror_path"] == str(mirror_path)
        assert str(frontier_path) in context["prompt"]
        assert frontier_path.exists()
        assert mirror_path.exists()


def test_full_product_frontier_paths_keep_runtime_artifacts_out_of_design_mirror() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        aggregate_root = root / "state"
        shard_root = aggregate_root / "shard-4"
        shard_root.mkdir(parents=True, exist_ok=True)

        published_path, mirror_path = module._full_product_frontier_paths(root, state_root=shard_root)

        assert published_path == root / ".codex-studio" / "published" / "full-product-frontiers" / "shard-4.generated.yaml"
        assert mirror_path == root / "state" / "artifacts" / "full-product-frontiers" / "shard-4.generated.yaml"
        assert ".codex-design/product" not in str(mirror_path)


def test_reconcile_materialized_full_product_frontier_ignores_idle_claim_without_active_run() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        shard_root = root / "state" / "chummer_design_supervisor" / "shard-5"
        shard_root.mkdir(parents=True, exist_ok=True)
        module._write_json(
            shard_root / "state.json",
            {
                "idle_reason": "claimed_frontier_without_active_run",
                "active_run_progress_state": "idle_claimed_frontier_without_active_run",
                "frontier_ids": [1300044932],
            },
        )
        args = _args(root)
        frontier = [
            module._synthetic_full_product_milestone(
                key="ui_kit_flagship_polish",
                title="Shared design system, accessibility, localization, and flagship polish",
                owners=["chummer6-ui-kit", "chummer6-ui", "chummer6-mobile"],
                exit_criteria=["Keep polish honest."],
            )
        ]

        reconciled = module._reconcile_materialized_full_product_frontier(
            args,
            shard_root,
            frontier,
            {"missing_coverage_keys": ["desktop_client"]},
        )

        assert [item.id for item in reconciled] == [frontier[0].id]


def test_reconcile_materialized_full_product_frontier_uses_registry_milestone_when_queue_frontier_is_synthetic() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        registry_path = root / "registry.yaml"
        registry_path.write_text(
            yaml.safe_dump(
                {
                    "waves": [{"id": "W1"}],
                    "milestones": [
                        {
                            "id": 1300044932,
                            "title": "Mobile and play-shell flagship finish",
                            "wave": "W1",
                            "status": "not_started",
                            "owners": ["chummer6-mobile", "chummer6-core"],
                            "exit_criteria": ["Keep the claimed frontier id stable."],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        shard_root = root / "state" / "chummer_design_supervisor" / "shard-5"
        shard_root.mkdir(parents=True, exist_ok=True)
        module._write_json(
            shard_root / "state.json",
            {
                "frontier_ids": [1300044932],
                "open_milestone_ids": [1300044932],
                "active_run_progress_state": "streaming",
            },
        )
        args = _args(root)
        synthetic_frontier = [
            module._synthetic_full_product_milestone(
                key="next90-m104-core-proof-pack",
                title="Build golden oracle suites and release-bound engine proof packs",
                owners=["chummer6-core"],
                exit_criteria=["Synthetic queue slice."],
            )
        ]

        reconciled = module._reconcile_materialized_full_product_frontier(
            args,
            shard_root,
            synthetic_frontier,
            {"missing_coverage_keys": []},
        )

        assert [item.id for item in reconciled] == [1300044932]
        assert reconciled[0].title == "Mobile and play-shell flagship finish"


def test_derive_completion_review_context_excludes_prior_active_shard_claims() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "registry.yaml").write_text("waves: []\nmilestones: []\n", encoding="utf-8")
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("Everything is done.\n", encoding="utf-8")
        _write_completion_evidence(root)
        task_a = "Seed Chummer.Ui.Kit with token canon"
        task_b = "Publish and execute the ruleset-specific workbench adaptation lane"
        projects_dir = root / "projects"
        projects_dir.mkdir(parents=True, exist_ok=True)
        ui_kit_root = root / "chummer6-ui-kit"
        ui_root = root / "chummer6-ui"
        ui_kit_root.mkdir(parents=True, exist_ok=True)
        ui_root.mkdir(parents=True, exist_ok=True)
        (ui_kit_root / "WORKLIST.md").write_text(f"- [queued] wl-1 {task_a}\n", encoding="utf-8")
        (ui_root / "WORKLIST.md").write_text(f"- [queued] wl-1 {task_b}\n", encoding="utf-8")
        (projects_dir / "ui-kit.yaml").write_text(
            yaml.safe_dump(
                {
                    "id": "ui-kit",
                    "path": str(ui_kit_root),
                    "review": {"repo": "chummer6-ui-kit"},
                    "queue": [],
                    "queue_sources": [{"kind": "worklist", "path": "WORKLIST.md", "mode": "replace"}],
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        (projects_dir / "ui.yaml").write_text(
            yaml.safe_dump(
                {
                    "id": "ui",
                    "path": str(ui_root),
                    "review": {"repo": "chummer6-ui"},
                    "queue": [],
                    "queue_sources": [{"kind": "worklist", "path": "WORKLIST.md", "mode": "replace"}],
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        aggregate_root = root / "state" / "chummer_design_supervisor"
        shard_one_root = aggregate_root / "shard-1"
        shard_two_root = aggregate_root / "shard-2"
        shard_one_root.mkdir(parents=True, exist_ok=True)
        shard_two_root.mkdir(parents=True, exist_ok=True)
        module._write_json(
            shard_one_root / "state.json",
            {
                "updated_at": "2026-03-31T17:22:15Z",
                "mode": "completion_review",
                "frontier_ids": [],
                "active_run": {
                    "run_id": "run-1",
                    "frontier_ids": [
                        module._synthetic_completion_review_id(f"repo-backlog:ui-kit:{task_a}"),
                    ],
                    "open_milestone_ids": [],
                },
            },
        )
        args = _args(root)
        base_context = module.derive_context(args)
        audit = module._design_completion_audit(args, [])

        context = module.derive_completion_review_context(args, shard_two_root, base_context=base_context, audit=audit)

        assert context["completion_review_prior_claimed_frontier_ids"] == [
            module._synthetic_completion_review_id(f"repo-backlog:ui-kit:{task_a}")
        ]
        assert context["frontier_ids"] == [
            module._synthetic_completion_review_id(f"repo-backlog:ui:{task_b}")
        ]


def test_prior_active_shard_frontier_ids_ignores_aggregate_root() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        aggregate_root = root / "state" / "chummer_design_supervisor"
        shard_root = aggregate_root / "shard-1"
        shard_root.mkdir(parents=True, exist_ok=True)
        module._write_json(
            shard_root / "state.json",
            {
                "active_run": {
                    "run_id": "run-1",
                    "frontier_ids": [13, 14],
                    "open_milestone_ids": [],
                }
            },
        )

        assert module._prior_active_shard_frontier_ids(aggregate_root) == []


def test_configured_shard_roots_prefers_active_manifest_over_stale_dirs() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        aggregate_root = Path(tmp) / "state" / "chummer_design_supervisor"
        shard_one_root = aggregate_root / "shard-1"
        shard_two_root = aggregate_root / "shard-2"
        shard_three_root = aggregate_root / "shard-3"
        shard_four_root = aggregate_root / "shard-4"
        for shard_root in (shard_one_root, shard_two_root, shard_three_root, shard_four_root):
            shard_root.mkdir(parents=True, exist_ok=True)
        (aggregate_root / "active_shards.json").write_text(
            json.dumps({"active_shards": ["shard-1", "shard-3"]}),
            encoding="utf-8",
        )

        configured_roots = module._configured_shard_roots(aggregate_root)

        assert configured_roots == [shard_one_root, shard_three_root]


def test_configured_shard_roots_accepts_structured_manifest_entries() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        aggregate_root = Path(tmp) / "state" / "chummer_design_supervisor"
        shard_one_root = aggregate_root / "shard-1"
        shard_two_root = aggregate_root / "shard-2"
        shard_three_root = aggregate_root / "shard-3"
        for shard_root in (shard_one_root, shard_two_root, shard_three_root):
            shard_root.mkdir(parents=True, exist_ok=True)
            module._write_json(shard_root / "state.json", {"updated_at": "2026-03-31T08:00:00Z"})
        (aggregate_root / "active_shards.json").write_text(
            json.dumps(
                {
                    "generated_at": "2026-04-04T15:20:00Z",
                    "topology_fingerprint": "abc123",
                    "active_shards": [
                        {"name": "shard-1", "index": 1, "frontier_ids": [1, 2, 3]},
                        {"name": "shard-3", "index": 3, "frontier_ids": [7, 8, 9]},
                    ],
                }
            ),
            encoding="utf-8",
        )

        configured_roots = module._configured_shard_roots(aggregate_root)

        assert configured_roots == [shard_one_root, shard_three_root]


def test_write_active_shard_manifest_snapshot_rehydrates_from_project_contract_topology(monkeypatch) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        aggregate_root = Path(tmp) / "state" / "chummer_design_supervisor"
        aggregate_root.mkdir(parents=True, exist_ok=True)
        (aggregate_root / "shard-1").mkdir(parents=True, exist_ok=True)
        (aggregate_root / "active_shards.json").write_text(
            json.dumps({"configured_shards": [{"name": "shard-1", "index": 1}]}),
            encoding="utf-8",
        )

        monkeypatch.setattr(
            module,
            "_project_configured_shard_entries",
            lambda: [
                {"name": "shard-1", "index": 1},
                {"name": "shard-2", "index": 2},
                {"name": "shard-3", "index": 3},
            ],
        )
        monkeypatch.setattr(module, "_refresh_aggregate_runtime_state_snapshot", lambda _aggregate_root: None)

        module._write_active_shard_manifest_snapshot(aggregate_root)

        payload = json.loads((aggregate_root / "active_shards.json").read_text(encoding="utf-8"))

        assert payload["configured_shard_count"] == 3
        assert [row["name"] for row in payload["configured_shards"]] == ["shard-1", "shard-2", "shard-3"]
        assert (aggregate_root / "shard-2").is_dir()
        assert (aggregate_root / "shard-3").is_dir()


def test_heal_state_push_blockers_repairs_recorded_missing_github_push_blocker() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        state_root = Path(tmp) / "state" / "chummer_design_supervisor" / "shard-5"
        run_dir = state_root / "runs" / "run-1"
        run_dir.mkdir(parents=True, exist_ok=True)
        stderr_path = run_dir / "worker.stderr.log"
        stderr_path.write_text(
            "exec\n/usr/bin/bash -lc 'cd /docker/fleet && git push' in /docker/fleet exited 128 in 14ms:\n",
            encoding="utf-8",
        )
        last_message_path = run_dir / "last_message.txt"
        last_message_path.write_text(
            "What shipped: pushed nothing\n\n"
            "What remains: handoff still local\n\n"
            "Exact blocker: host-side git push recovery failed after worker credential error: "
            "/docker/fleet: fatal: could not read Username for 'https://github.com': No such device or address\n",
            encoding="utf-8",
        )
        run_payload = {
            "run_id": "run-1",
            "accepted": True,
            "worker_exit_code": 0,
            "started_at": "2026-04-04T15:00:00Z",
            "finished_at": "2026-04-04T15:05:00Z",
            "open_milestone_ids": [10, 11, 12, 15],
            "frontier_ids": [10, 11, 12, 15],
            "blocker": "host-side git push recovery failed after worker credential error: /docker/fleet: fatal: could not read Username for 'https://github.com': No such device or address",
            "shipped": "pushed nothing",
            "remains": "handoff still local",
            "final_message": last_message_path.read_text(encoding="utf-8"),
            "stderr_path": str(stderr_path),
            "last_message_path": str(last_message_path),
        }
        module._write_json(
            state_root / "state.json",
            {
                "updated_at": "2026-04-04T15:05:00Z",
                "mode": "loop",
                "open_milestone_ids": [10, 11, 12, 15],
                "frontier_ids": [10, 11, 12, 15],
                "last_run": dict(run_payload),
            },
        )
        (state_root / "history.jsonl").write_text(json.dumps(run_payload) + "\n", encoding="utf-8")

        original_retry = module._retry_worker_reported_git_pushes
        module._retry_worker_reported_git_pushes = (
            lambda _stderr: {"attempted": ["/docker/fleet"], "succeeded": ["/docker/fleet"], "failed": {}}
        )
        try:
            module._heal_state_push_blockers(state_root)
        finally:
            module._retry_worker_reported_git_pushes = original_retry

        state = module._read_state(state_root / "state.json")
        history = module._read_history(state_root / "history.jsonl", limit=0)

        assert state["last_run"]["blocker"] == "none"
        assert history[-1]["blocker"] == "none"
        assert "Exact blocker: none" in last_message_path.read_text(encoding="utf-8")


def test_heal_state_push_blockers_repairs_verified_remote_push_residue() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        state_root = Path(tmp) / "state" / "chummer_design_supervisor" / "shard-2"
        run_dir = state_root / "runs" / "run-1"
        run_dir.mkdir(parents=True, exist_ok=True)
        stderr_path = run_dir / "worker.stderr.log"
        stderr_path.write_text("", encoding="utf-8")
        last_message_path = run_dir / "last_message.txt"
        last_message_path.write_text(
            "What shipped: `/docker/fleet/NEXT_SESSION_HANDOFF.md` refreshed locally with both slices "
            "(local Fleet commits `fbc5b1d`, `370495d`).\n\n"
            "What remains: frontier milestones `14`, `17` residuals; "
            "Fleet handoff commits are not yet pushed to remote.\n\n"
            "Exact blocker: none\n",
            encoding="utf-8",
        )
        run_payload = {
            "run_id": "run-1",
            "accepted": True,
            "worker_exit_code": 0,
            "started_at": "2026-04-04T15:00:00Z",
            "finished_at": "2026-04-04T15:05:00Z",
            "open_milestone_ids": [13, 14, 17, 18],
            "frontier_ids": [13, 14, 17, 18],
            "blocker": "none",
            "shipped": "`/docker/fleet/NEXT_SESSION_HANDOFF.md` refreshed locally with both slices (local Fleet commits `fbc5b1d`, `370495d`).",
            "remains": "frontier milestones `14`, `17` residuals; Fleet handoff commits are not yet pushed to remote.",
            "final_message": last_message_path.read_text(encoding="utf-8"),
            "stderr_path": str(stderr_path),
            "last_message_path": str(last_message_path),
        }
        module._write_json(
            state_root / "state.json",
            {
                "updated_at": "2026-04-04T15:05:00Z",
                "mode": "loop",
                "open_milestone_ids": [13, 14, 17, 18],
                "frontier_ids": [13, 14, 17, 18],
                "last_run": dict(run_payload),
            },
        )
        (state_root / "history.jsonl").write_text(json.dumps(run_payload) + "\n", encoding="utf-8")

        original_contains = module._git_remote_contains_commit
        module._git_remote_contains_commit = lambda _repo, _commit, env=None: True
        try:
            module._heal_state_push_blockers(state_root)
        finally:
            module._git_remote_contains_commit = original_contains

        state = module._read_state(state_root / "state.json")
        history = module._read_history(state_root / "history.jsonl", limit=0)
        repaired_message = last_message_path.read_text(encoding="utf-8")

        assert state["last_run"]["blocker"] == "none"
        assert state["last_run"]["remains"] == "frontier milestones `14`, `17` residuals"
        assert "not yet pushed to remote" not in repaired_message
        assert "(Fleet commits `fbc5b1d`, `370495d`)" in repaired_message
        assert history[-1]["remains"] == "frontier milestones `14`, `17` residuals"


def test_heal_state_push_blockers_repairs_verified_not_yet_on_remote_phrase() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        state_root = Path(tmp) / "state" / "chummer_design_supervisor" / "shard-1"
        run_dir = state_root / "runs" / "run-1"
        run_dir.mkdir(parents=True, exist_ok=True)
        stderr_path = run_dir / "worker.stderr.log"
        stderr_path.write_text("", encoding="utf-8")
        last_message_path = run_dir / "last_message.txt"
        last_message_path.write_text(
            "What shipped: `chummer-hub-registry` hardening landed; `fleet` handoff was refreshed locally in `8140fd4`.\n\n"
            "What remains: frontier milestones `1`, `2`, `3` remain open; `fleet` commit `8140fd4` is not yet on remote.\n\n"
            "Exact blocker: none\n",
            encoding="utf-8",
        )
        run_payload = {
            "run_id": "run-1",
            "accepted": True,
            "worker_exit_code": 0,
            "started_at": "2026-04-04T16:15:57Z",
            "finished_at": "2026-04-04T16:24:46Z",
            "open_milestone_ids": [1, 2, 3],
            "frontier_ids": [1, 2, 3],
            "blocker": "none",
            "shipped": "`chummer-hub-registry` hardening landed; `fleet` handoff was refreshed locally in `8140fd4`.",
            "remains": "frontier milestones `1`, `2`, `3` remain open; `fleet` commit `8140fd4` is not yet on remote.",
            "final_message": last_message_path.read_text(encoding="utf-8"),
            "stderr_path": str(stderr_path),
            "last_message_path": str(last_message_path),
        }
        module._write_json(
            state_root / "state.json",
            {
                "updated_at": "2026-04-04T16:24:46Z",
                "mode": "loop",
                "open_milestone_ids": [1, 2, 3],
                "frontier_ids": [1, 2, 3],
                "last_run": dict(run_payload),
            },
        )
        (state_root / "history.jsonl").write_text(json.dumps(run_payload) + "\n", encoding="utf-8")

        original_contains = module._git_remote_contains_commit
        module._git_remote_contains_commit = lambda _repo, _commit, env=None: True
        try:
            module._heal_state_push_blockers(state_root)
        finally:
            module._git_remote_contains_commit = original_contains

        state = module._read_state(state_root / "state.json")
        history = module._read_history(state_root / "history.jsonl", limit=0)
        repaired_message = last_message_path.read_text(encoding="utf-8")

        assert state["last_run"]["blocker"] == "none"
        assert state["last_run"]["remains"] == "frontier milestones `1`, `2`, `3` remain open"
        assert "not yet on remote" not in repaired_message
        assert history[-1]["remains"] == "frontier milestones `1`, `2`, `3` remain open"


def test_heal_state_push_blockers_repairs_empty_accepted_receipt_from_previous_trusted_run() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        state_root = Path(tmp) / "state" / "chummer_design_supervisor" / "shard-3"
        prior_run_dir = state_root / "runs" / "run-prior"
        latest_run_dir = state_root / "runs" / "run-latest"
        prior_run_dir.mkdir(parents=True, exist_ok=True)
        latest_run_dir.mkdir(parents=True, exist_ok=True)

        prior_message_path = prior_run_dir / "last_message.txt"
        prior_message_path.write_text(
            "What shipped: refreshed release proof artifacts\n\n"
            "What remains: external host proofs for 4 tuples\n\n"
            "Exact blocker: macos/windows startup-smoke receipts still required\n",
            encoding="utf-8",
        )
        latest_message_path = latest_run_dir / "last_message.txt"
        latest_message_path.write_text("", encoding="utf-8")

        prior_payload = {
            "run_id": "run-prior",
            "accepted": True,
            "worker_exit_code": 0,
            "shipped": "refreshed release proof artifacts",
            "remains": "external host proofs for 4 tuples",
            "blocker": "macos/windows startup-smoke receipts still required",
            "final_message": prior_message_path.read_text(encoding="utf-8"),
            "last_message_path": str(prior_message_path),
        }
        latest_payload = {
            "run_id": "run-latest",
            "accepted": True,
            "worker_exit_code": 0,
            "shipped": "",
            "remains": "",
            "blocker": "",
            "final_message": "",
            "last_message_path": str(latest_message_path),
        }

        module._write_json(
            state_root / "state.json",
            {
                "updated_at": "2026-04-05T00:31:17Z",
                "mode": "loop",
                "last_run": dict(latest_payload),
            },
        )
        (state_root / "history.jsonl").write_text(
            json.dumps(prior_payload) + "\n" + json.dumps(latest_payload) + "\n",
            encoding="utf-8",
        )

        module._heal_state_push_blockers(state_root)

        state = module._read_state(state_root / "state.json")
        history = module._read_history(state_root / "history.jsonl", limit=0)
        repaired_latest = history[-1]
        repaired_message = latest_message_path.read_text(encoding="utf-8")

        assert state["last_run"]["run_id"] == "run-latest"
        assert state["last_run"]["accepted"] is True
        assert state["last_run"]["remains"] == "external host proofs for 4 tuples"
        assert state["last_run"]["blocker"] == "macos/windows startup-smoke receipts still required"
        assert repaired_latest["receipt_recovered_from_run_id"] == "run-prior"
        assert "Recovered trusted structured closeout" in repaired_latest["shipped"]
        assert "What shipped:" in repaired_message
        assert "What remains: external host proofs for 4 tuples" in repaired_message
        assert "Exact blocker: macos/windows startup-smoke receipts still required" in repaired_message


def test_open_milestone_shard_frontier_uses_active_manifest_to_avoid_stranded_slices() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        aggregate_root = Path(tmp) / "state" / "chummer_design_supervisor"
        shard_one_root = aggregate_root / "shard-1"
        shard_two_root = aggregate_root / "shard-2"
        shard_three_root = aggregate_root / "shard-3"
        shard_four_root = aggregate_root / "shard-4"
        for shard_root in (shard_one_root, shard_two_root, shard_three_root, shard_four_root):
            shard_root.mkdir(parents=True, exist_ok=True)
        (aggregate_root / "active_shards.json").write_text(
            json.dumps({"active_shards": ["shard-1", "shard-2", "shard-3"]}),
            encoding="utf-8",
        )
        frontier = [
            module.Milestone(
                id=index,
                title=f"Milestone {index}",
                wave="W1",
                status="in_progress",
                owners=["fleet"],
                exit_criteria=["Ship it."],
                dependencies=[],
            )
            for index in range(1, 7)
        ]

        shard_one_frontier = module._open_milestone_shard_frontier(shard_one_root, frontier, default_limit=5)
        shard_two_frontier = module._open_milestone_shard_frontier(shard_two_root, frontier, default_limit=5)
        shard_three_frontier = module._open_milestone_shard_frontier(shard_three_root, frontier, default_limit=5)

        assert [item.id for item in shard_one_frontier] == [1, 2]
        assert [item.id for item in shard_two_frontier] == [3, 4]
        assert [item.id for item in shard_three_frontier] == [5, 6]


def test_effective_supervisor_state_filters_history_that_does_not_match_current_manifest_pack() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        aggregate_root = Path(tmp) / "state" / "chummer_design_supervisor"
        shard_root = aggregate_root / "shard-1"
        shard_root.mkdir(parents=True, exist_ok=True)
        module._write_json(
            shard_root / "state.json",
            {
                "updated_at": "2026-04-04T15:20:00Z",
                "mode": "loop",
                "frontier_ids": [13, 14],
            },
        )
        module._append_jsonl(
            shard_root / "history.jsonl",
            {
                "run_id": "run-old",
                "finished_at": "2026-04-04T15:10:00Z",
                "frontier_ids": [4, 5],
                "worker_exit_code": 0,
            },
        )
        module._append_jsonl(
            shard_root / "history.jsonl",
            {
                "run_id": "run-current",
                "finished_at": "2026-04-04T15:15:00Z",
                "frontier_ids": [13, 14],
                "worker_exit_code": 0,
            },
        )
        (aggregate_root / "active_shards.json").write_text(
            json.dumps(
                {
                    "generated_at": "2026-04-04T15:20:00Z",
                    "topology_fingerprint": "abc123",
                    "active_shards": [
                        {"name": "shard-1", "index": 1, "frontier_ids": [13, 14]},
                    ],
                }
            ),
            encoding="utf-8",
        )

        state, history = module._effective_supervisor_state(aggregate_root, history_limit=10)

        assert state["last_run"]["run_id"] == "run-current"
        assert [run["run_id"] for run in history] == ["run-current"]


def test_effective_supervisor_state_filters_history_with_nonlocal_open_milestones() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        aggregate_root = Path(tmp) / "state" / "chummer_design_supervisor"
        shard_root = aggregate_root / "shard-2"
        shard_root.mkdir(parents=True, exist_ok=True)
        module._write_json(
            shard_root / "state.json",
            {
                "updated_at": "2026-04-04T15:20:00Z",
                "mode": "loop",
                "frontier_ids": [13, 14, 17, 18],
                "open_milestone_ids": [13, 14, 17, 18],
            },
        )
        module._append_jsonl(
            shard_root / "history.jsonl",
            {
                "run_id": "run-wide-open",
                "finished_at": "2026-04-04T15:10:00Z",
                "frontier_ids": [13, 14, 17, 18],
                "open_milestone_ids": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18],
                "worker_exit_code": 0,
            },
        )
        module._append_jsonl(
            shard_root / "history.jsonl",
            {
                "run_id": "run-local-open",
                "finished_at": "2026-04-04T15:15:00Z",
                "frontier_ids": [13, 14, 17, 18],
                "open_milestone_ids": [13, 14, 17, 18],
                "worker_exit_code": 0,
            },
        )
        (aggregate_root / "active_shards.json").write_text(
            json.dumps({"active_shards": [{"name": "shard-2", "frontier_ids": [13, 14, 17, 18]}]}),
            encoding="utf-8",
        )

        state, history = module._effective_supervisor_state(aggregate_root, history_limit=10)

        assert state["last_run"]["run_id"] == "run-local-open"
        assert [run["run_id"] for run in history] == ["run-local-open"]


def test_effective_supervisor_state_ignores_base_history_when_sharded() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        aggregate_root = Path(tmp) / "state" / "chummer_design_supervisor"
        shard_root = aggregate_root / "shard-1"
        shard_root.mkdir(parents=True, exist_ok=True)
        module._write_json(
            aggregate_root / "state.json",
            {
                "updated_at": "2026-04-04T15:00:00Z",
                "mode": "loop",
                "frontier_ids": [1, 2, 3, 4, 5],
                "open_milestone_ids": [1, 2, 3, 4, 5],
            },
        )
        module._append_jsonl(
            aggregate_root / "history.jsonl",
            {
                "run_id": "run-base",
                "finished_at": "2026-04-04T15:00:00Z",
                "frontier_ids": [1, 2, 3, 4, 5],
                "open_milestone_ids": [1, 2, 3, 4, 5],
                "worker_exit_code": 0,
            },
        )
        module._write_json(
            shard_root / "state.json",
            {
                "updated_at": "2026-04-04T15:10:00Z",
                "mode": "loop",
                "frontier_ids": [1, 2, 3],
                "open_milestone_ids": [1, 2, 3],
            },
        )
        module._append_jsonl(
            shard_root / "history.jsonl",
            {
                "run_id": "run-shard",
                "finished_at": "2026-04-04T15:10:00Z",
                "frontier_ids": [1, 2, 3],
                "open_milestone_ids": [1, 2, 3],
                "worker_exit_code": 0,
            },
        )
        (aggregate_root / "active_shards.json").write_text(
            json.dumps({"active_shards": [{"name": "shard-1", "frontier_ids": [1, 2, 3]}]}),
            encoding="utf-8",
        )

        state, history = module._effective_supervisor_state(aggregate_root, history_limit=10)

        assert state["frontier_ids"] == [1, 2, 3]
        assert [run["run_id"] for run in history] == ["run-shard"]


def test_effective_supervisor_state_ignores_stale_shard_dirs_not_in_manifest() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        aggregate_root = Path(tmp) / "state" / "chummer_design_supervisor"
        active_root = aggregate_root / "shard-1"
        stale_root = aggregate_root / "shard-9"
        active_root.mkdir(parents=True, exist_ok=True)
        stale_root.mkdir(parents=True, exist_ok=True)
        module._write_json(
            active_root / "state.json",
            {
                "updated_at": "2026-04-04T15:10:00Z",
                "mode": "loop",
                "frontier_ids": [1, 2, 3],
                "open_milestone_ids": [1, 2, 3],
            },
        )
        module._write_json(
            stale_root / "state.json",
            {
                "updated_at": "2026-04-04T15:20:00Z",
                "mode": "loop",
                "frontier_ids": [99],
                "open_milestone_ids": [99],
            },
        )
        (aggregate_root / "active_shards.json").write_text(
            json.dumps({"active_shards": [{"name": "shard-1", "frontier_ids": [1, 2, 3]}]}),
            encoding="utf-8",
        )

        state, _history = module._effective_supervisor_state(aggregate_root, history_limit=10)

        assert state["shard_count"] == 1
        assert state["frontier_ids"] == [1, 2, 3]
        assert state["open_milestone_ids"] == [1, 2, 3]


def test_effective_supervisor_state_surfaces_shard_blockers_in_aggregate_status() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        aggregate_root = Path(tmp) / "state" / "chummer_design_supervisor"
        shard_one_root = aggregate_root / "shard-1"
        shard_two_root = aggregate_root / "shard-2"
        shard_one_root.mkdir(parents=True, exist_ok=True)
        shard_two_root.mkdir(parents=True, exist_ok=True)
        module._write_json(
            shard_one_root / "state.json",
            {
                "updated_at": "2026-04-04T16:05:54Z",
                "mode": "loop",
                "open_milestone_ids": [1, 2, 3],
                "frontier_ids": [1, 2, 3],
                "last_run": {
                    "run_id": "run-blocked",
                    "finished_at": "2026-04-04T15:53:10Z",
                    "open_milestone_ids": [1, 2, 3],
                    "frontier_ids": [1, 2, 3],
                    "blocker": "Concurrent unseen local commits are landing in `/docker/fleet` during execution.",
                },
                "active_run": {
                    "run_id": "run-live",
                    "frontier_ids": [1, 2, 3],
                    "open_milestone_ids": [1, 2, 3],
                },
            },
        )
        module._write_json(
            shard_two_root / "state.json",
            {
                "updated_at": "2026-04-04T16:05:57Z",
                "mode": "loop",
                "open_milestone_ids": [13, 14],
                "frontier_ids": [13, 14],
                "last_run": {
                    "run_id": "run-clean",
                    "finished_at": "2026-04-04T15:53:50Z",
                    "open_milestone_ids": [13, 14],
                    "frontier_ids": [13, 14],
                    "blocker": "none",
                },
            },
        )
        (aggregate_root / "active_shards.json").write_text(
            json.dumps(
                {
                    "active_shards": [
                        {"name": "shard-1", "frontier_ids": [1, 2, 3]},
                        {"name": "shard-2", "frontier_ids": [13, 14]},
                    ]
                }
            ),
            encoding="utf-8",
        )

        state, _history = module._effective_supervisor_state(aggregate_root, history_limit=10)

        assert state["shard_blockers"] == [
            {
                "name": "shard-1",
                "run_id": "run-blocked",
                "blocker": "Concurrent unseen local commits are landing in `/docker/fleet` during execution.",
            }
        ]
        shard_rows = {row["name"]: row for row in state["shards"]}
        assert shard_rows["shard-1"]["last_run_blocker"] == (
            "Concurrent unseen local commits are landing in `/docker/fleet` during execution."
        )
        assert shard_rows["shard-2"]["last_run_blocker"] == ""


def test_effective_supervisor_state_recomputes_aggregate_eta_from_active_shards() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        aggregate_root = Path(tmp) / "state" / "chummer_design_supervisor"
        shard_one_root = aggregate_root / "shard-1"
        shard_two_root = aggregate_root / "shard-2"
        shard_one_root.mkdir(parents=True, exist_ok=True)
        shard_two_root.mkdir(parents=True, exist_ok=True)
        module._write_json(
            shard_one_root / "state.json",
            {
                "updated_at": "2026-04-04T16:05:54Z",
                "mode": "loop",
                "open_milestone_ids": [1, 2, 3],
                "frontier_ids": [1, 2, 3],
                "eta": {
                    "status": "estimated",
                    "eta_human": "4.5d-1.7w",
                    "eta_confidence": "low",
                    "basis": "heuristic_status_mix",
                    "summary": "3 open milestones remain (0 in progress, 3 not started); range is a fallback heuristic from the current status mix.",
                    "remaining_open_milestones": 3,
                    "remaining_in_progress_milestones": 0,
                    "remaining_not_started_milestones": 3,
                    "blocking_reason": "",
                },
                "active_run": {
                    "run_id": "run-live-1",
                    "frontier_ids": [1, 2, 3],
                    "open_milestone_ids": [1, 2, 3],
                },
            },
        )
        module._write_json(
            shard_two_root / "state.json",
            {
                "updated_at": "2026-04-04T16:05:57Z",
                "mode": "loop",
                "open_milestone_ids": [13, 14],
                "frontier_ids": [13, 14],
                "active_run": {
                    "run_id": "run-live-2",
                    "frontier_ids": [13, 14],
                    "open_milestone_ids": [13, 14],
                },
            },
        )
        (aggregate_root / "active_shards.json").write_text(
            json.dumps(
                {
                    "active_shards": [
                        {"name": "shard-1", "frontier_ids": [1, 2, 3]},
                        {"name": "shard-2", "frontier_ids": [13, 14]},
                    ]
                }
            ),
            encoding="utf-8",
        )

        state, _history = module._effective_supervisor_state(aggregate_root, history_limit=10)

        assert state["eta"]["remaining_open_milestones"] == 5
        assert state["eta"]["remaining_in_progress_milestones"] == 5
        assert state["eta"]["remaining_not_started_milestones"] == 0
        assert "5 open milestones remain (5 in progress, 0 not started)" in state["eta"]["summary"]


def test_reconcile_aggregate_shard_truth_updates_eta_and_blockers() -> None:
    module = _load_module()

    updated = module._reconcile_aggregate_shard_truth(
        {
            "open_milestone_ids": [1, 2, 3, 13],
            "eta": {
                "status": "estimated",
                "eta_human": "4.5d-1.7w",
                "eta_confidence": "low",
                "basis": "heuristic_status_mix",
                "summary": "4 open milestones remain (0 in progress, 4 not started); range is a fallback heuristic from the current status mix.",
                "remaining_open_milestones": 4,
                "remaining_in_progress_milestones": 0,
                "remaining_not_started_milestones": 4,
                "blocking_reason": "",
            },
            "shards": [
                {
                    "name": "shard-1",
                    "frontier_ids": [1, 2, 3],
                    "active_frontier_ids": [1, 2, 3],
                    "last_run_id": "run-1",
                    "last_run_blocker": "concurrent local commits",
                },
                {
                    "name": "shard-2",
                    "frontier_ids": [13],
                    "active_frontier_ids": [13],
                    "last_run_id": "run-2",
                    "last_run_blocker": "",
                },
            ],
        }
    )

    assert updated["eta"]["remaining_open_milestones"] == 4
    assert updated["eta"]["remaining_in_progress_milestones"] == 4
    assert updated["eta"]["remaining_not_started_milestones"] == 0
    assert "4 open milestones remain (4 in progress, 0 not started)" in updated["eta"]["summary"]
    assert updated["eta"]["status"] == "blocked"
    assert updated["eta"]["eta_human"].endswith("after unblock")
    assert updated["eta"]["blocking_reason"] == "shard-1: concurrent local commits"
    assert updated["shard_blockers"] == [
        {"name": "shard-1", "run_id": "run-1", "blocker": "concurrent local commits"}
    ]


def test_normalized_blocker_text_ignores_clear_receipt_phrasing() -> None:
    module = _load_module()

    assert module._normalized_blocker_text("none.") == ""
    assert module._normalized_blocker_text("None for this scoped hub package slice. Verification passed.") == ""
    assert module._normalized_blocker_text("No implementation blocker. Commit deferred to avoid unrelated work.") == ""
    assert (
        module._normalized_blocker_text(
            "`python -m pytest tests/test_chummer_governor_packet_pack.py` cannot run because "
            "`pytest` is not installed in the EA environment; direct Python assertion proof passed."
        )
        == ""
    )
    assert module._normalized_blocker_text("pre-existing dirty worktree prevents safe commit") == (
        "pre-existing dirty worktree prevents safe commit"
    )


def test_run_supervisor_launcher_falls_back_to_focus_only_identity_when_frontier_probe_fails() -> None:
    launcher = Path("/docker/fleet/scripts/run_chummer_design_supervisor.sh")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        wrapper = root / "python3"
        wrapper.write_text(
            "\n".join(
                [
                    "#!/usr/bin/env bash",
                    "set -euo pipefail",
                    "if [[ \"${1:-}\" == \"-\" ]]; then",
                    "  exec /usr/bin/python3 \"$@\"",
                    "fi",
                    "if [[ \"${1:-}\" == \"scripts/chummer_design_supervisor.py\" && \"${2:-}\" == \"status\" && \"${3:-}\" == \"--json\" ]]; then",
                    "  echo 'probe boom' >&2",
                    "  exit 17",
                    "fi",
                    "if [[ \"${1:-}\" == \"scripts/chummer_design_supervisor.py\" && \"${2:-}\" == \"loop\" ]]; then",
                    "  exit 0",
                    "fi",
                    "echo 'unexpected python3 invocation' >&2",
                    "exit 99",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        wrapper.chmod(0o755)
        result = subprocess.run(
            [str(launcher)],
            cwd="/docker/fleet",
            env={
                **os.environ,
                "PATH": f"{root}:{os.environ['PATH']}",
                "CHUMMER_DESIGN_SUPERVISOR_PROJECT_CONFIG": str(root / "missing-project.yaml"),
                "CHUMMER_DESIGN_SUPERVISOR_PARALLEL_SHARDS": "2",
                "CHUMMER_DESIGN_SUPERVISOR_STATE_ROOT": str(root / "state" / "chummer_design_supervisor"),
                "CHUMMER_DESIGN_SUPERVISOR_SHARD_FRONTIER_ID_GROUPS": "",
                "CHUMMER_DESIGN_SUPERVISOR_FRONTIER_DERIVE_MODE": "derive",
                "CHUMMER_DESIGN_SUPERVISOR_MEMORY_DISPATCH_RESERVE_GIB": "0",
                "CHUMMER_DESIGN_SUPERVISOR_MEMORY_DISPATCH_WARNING_AVAILABLE_PERCENT": "0",
                "CHUMMER_DESIGN_SUPERVISOR_MEMORY_DISPATCH_CRITICAL_AVAILABLE_PERCENT": "0",
                "CHUMMER_DESIGN_SUPERVISOR_MEMORY_DISPATCH_WARNING_SWAP_USED_PERCENT": "101",
                "CHUMMER_DESIGN_SUPERVISOR_MEMORY_DISPATCH_CRITICAL_SWAP_USED_PERCENT": "101",
            },
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert "frontier derive timed out or failed; falling back to focus-only shard identity" in result.stderr
        assert "skipping shard-2 because its derived shard identity duplicates shard-1" in result.stderr


def test_run_supervisor_launcher_keeps_direct_codex_shards_lane_free() -> None:
    launcher = Path("/docker/fleet/scripts/run_chummer_design_supervisor.sh")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        wrapper = root / "python3"
        wrapper.write_text(
            "\n".join(
                [
                    "#!/usr/bin/env bash",
                    "set -euo pipefail",
                    "if [[ \"${1:-}\" == \"-\" ]]; then",
                    "  exec /usr/bin/python3 \"$@\"",
                    "fi",
                    "if [[ \"${1:-}\" == \"scripts/chummer_design_supervisor.py\" && \"${2:-}\" == \"status\" && \"${3:-}\" == \"--json\" ]]; then",
                    "  printf '%s\\n' '{\"frontier_ids\": []}'",
                    "  exit 0",
                    "fi",
                    "if [[ \"${1:-}\" == \"scripts/chummer_design_supervisor.py\" && \"${2:-}\" == \"loop\" ]]; then",
                    f"  out=\"{root}/loop-args.$$\"",
                    "  shift 2",
                    "  printf '%s\\n' \"$@\" >\"$out\"",
                    "  exit 0",
                    "fi",
                    "echo 'unexpected python3 invocation' >&2",
                    "printf '%s\\n' \"$*\" >&2",
                    "exit 99",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        wrapper.chmod(0o755)
        state_root = root / "state" / "chummer_design_supervisor"
        result = subprocess.run(
            [str(launcher)],
            cwd="/docker/fleet",
            env={
                **os.environ,
                "PATH": f"{root}:{os.environ['PATH']}",
                "CHUMMER_DESIGN_SUPERVISOR_PARALLEL_SHARDS": "2",
                "CHUMMER_DESIGN_SUPERVISOR_STATE_ROOT": str(state_root),
                "CHUMMER_DESIGN_SUPERVISOR_ACCOUNT_OWNER_IDS": "tibor.girschele",
                "CHUMMER_DESIGN_SUPERVISOR_DYNAMIC_ACCOUNT_ROUTING": "0",
                "CHUMMER_DESIGN_SUPERVISOR_WORKER_BIN": "codex",
                "CHUMMER_DESIGN_SUPERVISOR_WORKER_LANE": "",
                "CHUMMER_DESIGN_SUPERVISOR_WORKER_MODEL": "gpt-5.3-codex-spark",
                "CHUMMER_DESIGN_SUPERVISOR_SHARD_OWNER_GROUPS": "",
                "CHUMMER_DESIGN_SUPERVISOR_SHARD_ACCOUNT_GROUPS": "",
                "CHUMMER_DESIGN_SUPERVISOR_SHARD_FOCUS_TEXT_GROUPS": "downloads,handoff;visual-similarity,parity",
                "CHUMMER_DESIGN_SUPERVISOR_SHARD_FRONTIER_ID_GROUPS": "",
                "CHUMMER_DESIGN_SUPERVISOR_SHARD_WORKER_BINS": "codex;codex",
                "CHUMMER_DESIGN_SUPERVISOR_SHARD_WORKER_LANES": "",
                "CHUMMER_DESIGN_SUPERVISOR_SHARD_WORKER_MODELS": "gpt-5.3-codex-spark;gpt-5.3-codex-spark",
                "CHUMMER_DESIGN_SUPERVISOR_FOCUS_PROFILE": "",
                "CHUMMER_DESIGN_SUPERVISOR_FOCUS_OWNER": "",
                "CHUMMER_DESIGN_SUPERVISOR_FOCUS_TEXT": "",
                "CHUMMER_DESIGN_SUPERVISOR_ACCOUNT_ALIASES": "",
                "CHUMMER_DESIGN_SUPERVISOR_FRONTIER_DERIVE_MODE": "skip",
                "CHUMMER_DESIGN_SUPERVISOR_SHARD_START_STAGGER_SECONDS": "0",
            },
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, result.stderr

        manifest = json.loads((state_root / "active_shards.json").read_text(encoding="utf-8"))
        active_shards = manifest["active_shards"]
        assert len(active_shards) == 2
        for entry in active_shards:
            assert entry["worker_bin"] == "codex"
            assert entry["worker_model"] == "gpt-5.3-codex-spark"
            assert "worker_lane" not in entry

        loop_args_files = sorted(root.glob("loop-args.*"))
        assert loop_args_files
        for path in loop_args_files:
            args = path.read_text(encoding="utf-8").splitlines()
            assert "--account-owner-id" in args
            assert "tibor.girschele" in args
            assert "--worker-bin" in args
            assert args[args.index("--worker-bin") + 1] == "codex"
            assert "--worker-model" in args
            assert args[args.index("--worker-model") + 1] == "gpt-5.3-codex-spark"
            assert "--worker-lane" not in args
            joined = " ".join(args)
            assert "groundwork" not in joined
            assert "review_shard" not in joined
            assert "audit_shard" not in joined
            assert "core_rescue" not in joined


def test_run_supervisor_launcher_hydrates_restart_safe_resource_defaults_from_project_config() -> None:
    launcher = Path("/docker/fleet/scripts/run_chummer_design_supervisor.sh")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        state_root = root / "state" / "chummer_design_supervisor"
        project_config = root / "fleet.yaml"
        project_config.write_text(
            yaml.safe_dump(
                {
                    "supervisor_contract": {
                        "runtime_policy": {
                            "shard_start_stagger_seconds": 0,
                            "frontier_derive_mode": "skip",
                            "dynamic_account_routing": "0",
                        },
                        "restart_safe_runtime": {
                            "launcher_defaults": {
                                "parallel_shards": 2,
                                "state_root": str(state_root),
                                "clear_lock_on_boot": True,
                            }
                        },
                        "resource_policy": {
                            "default_operating_profile": "maintenance",
                            "memory_dispatch_parked_poll_seconds": 44,
                            "operating_profiles": {
                                "maintenance": {
                                    "max_active_shards": 2,
                                    "memory_dispatch_reserve_gib": 7.0,
                                    "memory_dispatch_shard_budget_gib": 1.5,
                                    "memory_dispatch_warning_available_percent": 21.0,
                                    "memory_dispatch_critical_available_percent": 11.0,
                                    "memory_dispatch_warning_swap_used_percent": 61.0,
                                    "memory_dispatch_critical_swap_used_percent": 81.0,
                                }
                            },
                        },
                        "shard_topology": {
                            "configured_shards": [
                                {
                                    "name": "shard-1",
                                    "index": 1,
                                    "focus_owner": ["fleet"],
                                    "focus_text": ["restart-safe"],
                                },
                                {
                                    "name": "shard-2",
                                    "index": 2,
                                    "focus_owner": ["chummer6-design"],
                                    "focus_text": ["resource-policy"],
                                },
                            ]
                        },
                    }
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        wrapper = root / "python3"
        wrapper.write_text(
            "\n".join(
                [
                    "#!/usr/bin/env bash",
                    "set -euo pipefail",
                    "if [[ \"${1:-}\" == \"-\" ]]; then",
                    "  exec /usr/bin/python3 \"$@\"",
                    "fi",
                    "if [[ \"${1:-}\" == \"scripts/chummer_design_supervisor.py\" && \"${2:-}\" == \"status\" && \"${3:-}\" == \"--json\" ]]; then",
                    "  printf '%s\\n' '{\"frontier_ids\": []}'",
                    "  exit 0",
                    "fi",
                    "if [[ \"${1:-}\" == \"scripts/chummer_design_supervisor.py\" && \"${2:-}\" == \"loop\" ]]; then",
                    f"  env | sort >\"{root}/loop-env.$$\"",
                    f"  out=\"{root}/loop-args.$$\"",
                    "  shift 2",
                    "  printf '%s\\n' \"$@\" >\"$out\"",
                    "  exit 0",
                    "fi",
                    "echo 'unexpected python3 invocation' >&2",
                    "printf '%s\\n' \"$*\" >&2",
                    "exit 99",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        wrapper.chmod(0o755)
        env = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith("CHUMMER_DESIGN_SUPERVISOR_")
        }
        env.update(
            {
                "PATH": f"{root}:{os.environ['PATH']}",
                "CHUMMER_DESIGN_SUPERVISOR_PROJECT_CONFIG": str(project_config),
            }
        )

        result = subprocess.run(
            [str(launcher)],
            cwd="/docker/fleet",
            env=env,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, result.stderr
        manifest = json.loads((state_root / "active_shards.json").read_text(encoding="utf-8"))
        active_shards = manifest["active_shards"]
        assert len(active_shards) == 2
        assert active_shards[0]["focus_owner"] == ["fleet"]
        assert active_shards[1]["focus_owner"] == ["chummer6-design"]

        loop_env_files = sorted(root.glob("loop-env.*"))
        assert loop_env_files
        loop_env = "\n".join(path.read_text(encoding="utf-8") for path in loop_env_files)
        assert "CHUMMER_DESIGN_SUPERVISOR_OPERATING_PROFILE=maintenance" in loop_env
        assert "CHUMMER_DESIGN_SUPERVISOR_MEMORY_DISPATCH_RESERVE_GIB=7.0" in loop_env
        assert "CHUMMER_DESIGN_SUPERVISOR_MEMORY_DISPATCH_SHARD_BUDGET_GIB=1.5" in loop_env
        assert "CHUMMER_DESIGN_SUPERVISOR_MEMORY_DISPATCH_WARNING_AVAILABLE_PERCENT=21.0" in loop_env
        assert "CHUMMER_DESIGN_SUPERVISOR_MEMORY_DISPATCH_CRITICAL_AVAILABLE_PERCENT=11.0" in loop_env
        assert "CHUMMER_DESIGN_SUPERVISOR_MEMORY_DISPATCH_WARNING_SWAP_USED_PERCENT=61.0" in loop_env
        assert "CHUMMER_DESIGN_SUPERVISOR_MEMORY_DISPATCH_CRITICAL_SWAP_USED_PERCENT=81.0" in loop_env
        assert "CHUMMER_DESIGN_SUPERVISOR_MEMORY_DISPATCH_PARKED_POLL_SECONDS=44" in loop_env


def test_run_supervisor_launcher_clears_stale_account_runtime_state() -> None:
    launcher = Path("/docker/fleet/scripts/run_chummer_design_supervisor.sh")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        wrapper = root / "python3"
        wrapper.write_text(
            "\n".join(
                [
                    "#!/usr/bin/env bash",
                    "set -euo pipefail",
                    "if [[ \"${1:-}\" == \"-\" ]]; then",
                    "  exec /usr/bin/python3 \"$@\"",
                    "fi",
                    "if [[ \"${1:-}\" == \"scripts/chummer_design_supervisor.py\" && \"${2:-}\" == \"status\" && \"${3:-}\" == \"--json\" ]]; then",
                    "  printf '%s\\n' '{\"frontier_ids\": []}'",
                    "  exit 0",
                    "fi",
                    "if [[ \"${1:-}\" == \"scripts/chummer_design_supervisor.py\" && \"${2:-}\" == \"loop\" ]]; then",
                    "  exit 0",
                    "fi",
                    "echo 'unexpected python3 invocation' >&2",
                    "printf '%s\\n' \"$*\" >&2",
                    "exit 99",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        wrapper.chmod(0o755)
        state_root = root / "state" / "chummer_design_supervisor"
        shard_root = state_root / "shard-1"
        shard_root.mkdir(parents=True, exist_ok=True)
        stale_runtime = shard_root / "account_runtime.json"
        stale_runtime.write_text("{\"sources\": {}}\n", encoding="utf-8")

        result = subprocess.run(
            [str(launcher)],
            cwd="/docker/fleet",
            env={
                **os.environ,
                "PATH": f"{root}:{os.environ['PATH']}",
                "CHUMMER_DESIGN_SUPERVISOR_PARALLEL_SHARDS": "2",
                "CHUMMER_DESIGN_SUPERVISOR_STATE_ROOT": str(state_root),
                "CHUMMER_DESIGN_SUPERVISOR_SHARD_FRONTIER_ID_GROUPS": "",
                "CHUMMER_DESIGN_SUPERVISOR_FRONTIER_DERIVE_MODE": "skip",
                "CHUMMER_DESIGN_SUPERVISOR_SHARD_START_STAGGER_SECONDS": "0",
            },
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, result.stderr
        assert not stale_runtime.exists()


def test_run_supervisor_launcher_preserves_aggregate_state_snapshot() -> None:
    launcher = Path("/docker/fleet/scripts/run_chummer_design_supervisor.sh")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        wrapper = root / "python3"
        wrapper.write_text(
            "\n".join(
                [
                    "#!/usr/bin/env bash",
                    "set -euo pipefail",
                    "if [[ \"${1:-}\" == \"-\" ]]; then",
                    "  exec /usr/bin/python3 \"$@\"",
                    "fi",
                    "if [[ \"${1:-}\" == \"scripts/chummer_design_supervisor.py\" && \"${2:-}\" == \"status\" && \"${3:-}\" == \"--json\" ]]; then",
                    "  printf '%s\\n' '{\"frontier_ids\": []}'",
                    "  exit 0",
                    "fi",
                    "if [[ \"${1:-}\" == \"scripts/chummer_design_supervisor.py\" && \"${2:-}\" == \"loop\" ]]; then",
                    "  exit 0",
                    "fi",
                    "echo 'unexpected python3 invocation' >&2",
                    "printf '%s\\n' \"$*\" >&2",
                    "exit 99",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        wrapper.chmod(0o755)
        state_root = root / "state" / "chummer_design_supervisor"
        state_root.mkdir(parents=True, exist_ok=True)
        aggregate_state = state_root / "state.json"
        aggregate_state.write_text(
            json.dumps(
                {
                    "updated_at": "2026-04-13T12:00:00Z",
                    "active_runs_count": 13,
                    "remaining_open_milestones": 8,
                    "eta_human": "2d-5.3d",
                }
            )
            + "\n",
            encoding="utf-8",
        )

        result = subprocess.run(
            [str(launcher)],
            cwd="/docker/fleet",
            env={
                **os.environ,
                "PATH": f"{root}:{os.environ['PATH']}",
                "CHUMMER_DESIGN_SUPERVISOR_PARALLEL_SHARDS": "2",
                "CHUMMER_DESIGN_SUPERVISOR_STATE_ROOT": str(state_root),
                "CHUMMER_DESIGN_SUPERVISOR_SHARD_FRONTIER_ID_GROUPS": "",
                "CHUMMER_DESIGN_SUPERVISOR_FRONTIER_DERIVE_MODE": "skip",
                "CHUMMER_DESIGN_SUPERVISOR_SHARD_START_STAGGER_SECONDS": "0",
            },
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, result.stderr
        assert aggregate_state.exists()
        payload = json.loads(aggregate_state.read_text(encoding="utf-8"))
        assert payload["active_runs_count"] == 13
        assert payload["remaining_open_milestones"] == 8


def test_derive_completion_review_context_can_focus_repo_backlog_items_beyond_first_five() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "registry.yaml").write_text("waves: []\nmilestones: []\n", encoding="utf-8")
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("Everything is done.\n", encoding="utf-8")
        _write_completion_evidence(root)
        projects_dir = root / "projects"
        projects_dir.mkdir(parents=True, exist_ok=True)
        project_rows = [
            ("hub-registry", "chummer6-hub-registry", "Extract registry contracts"),
            ("hub-registry", "chummer6-hub-registry", "Move registry seam"),
            ("hub-registry", "chummer6-hub-registry", "Wire registry package boundaries"),
            ("ui-kit", "chummer6-ui-kit", "Seed token canon"),
            ("ui-kit", "chummer6-ui-kit", "Extract shell chrome"),
            ("ui", "chummer6-ui", "Publish and execute the ruleset-specific workbench adaptation lane"),
        ]
        grouped_rows: dict[str, tuple[str, list[str]]] = {}
        for project_id, repo_slug, task in project_rows:
            if project_id not in grouped_rows:
                grouped_rows[project_id] = (repo_slug, [])
            grouped_rows[project_id][1].append(task)
        for project_id, (repo_slug, tasks) in grouped_rows.items():
            project_root = root / repo_slug
            project_root.mkdir(parents=True, exist_ok=True)
            (project_root / "WORKLIST.md").write_text(
                "\n".join(f"- [queued] wl-{index + 1} {task}" for index, task in enumerate(tasks)) + "\n",
                encoding="utf-8",
            )
            (projects_dir / f"{project_id}.yaml").write_text(
                yaml.safe_dump(
                    {
                        "id": project_id,
                        "path": str(project_root),
                        "review": {"repo": repo_slug},
                        "queue": [],
                        "queue_sources": [{"kind": "worklist", "path": "WORKLIST.md", "mode": "replace"}],
                    },
                    sort_keys=False,
                ),
                encoding="utf-8",
            )
        state_root = root / "state" / "chummer_design_supervisor" / "shard-2"
        state_root.mkdir(parents=True, exist_ok=True)
        args = _args(root)
        args.focus_owner = ["chummer6-core"]
        args.focus_text = ["workbench", "desktop", "sr4", "sr5", "sr6"]
        base_context = module.derive_context(args)
        audit = module._design_completion_audit(args, [])

        context = module.derive_completion_review_context(args, state_root, base_context=base_context, audit=audit)

        assert any("workbench adaptation lane" in item.title for item in context["frontier"])


def test_derive_completion_review_context_fair_shares_repo_backlog_across_three_shards() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "registry.yaml").write_text("waves: []\nmilestones: []\n", encoding="utf-8")
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("Everything is done.\n", encoding="utf-8")
        _write_completion_evidence(root)
        projects_dir = root / "projects"
        projects_dir.mkdir(parents=True, exist_ok=True)
        project_rows = [
            ("hub-registry", "chummer6-hub-registry", "Extract registry contracts"),
            ("hub-registry", "chummer6-hub-registry", "Move registry seam"),
            ("hub-registry", "chummer6-hub-registry", "Wire registry package boundaries"),
            ("ui-kit", "chummer6-ui-kit", "Seed token canon"),
            ("ui-kit", "chummer6-ui-kit", "Extract shell chrome"),
            ("ui-kit", "chummer6-ui-kit", "Migrate package-only ui kit"),
            ("ui", "chummer6-ui", "Publish and execute the ruleset-specific workbench adaptation lane"),
        ]
        grouped_rows: dict[str, tuple[str, list[str]]] = {}
        for project_id, repo_slug, task in project_rows:
            if project_id not in grouped_rows:
                grouped_rows[project_id] = (repo_slug, [])
            grouped_rows[project_id][1].append(task)
        for project_id, (repo_slug, tasks) in grouped_rows.items():
            project_root = root / repo_slug
            project_root.mkdir(parents=True, exist_ok=True)
            (project_root / "WORKLIST.md").write_text(
                "\n".join(f"- [queued] wl-{index + 1} {task}" for index, task in enumerate(tasks)) + "\n",
                encoding="utf-8",
            )
            (projects_dir / f"{project_id}.yaml").write_text(
                yaml.safe_dump(
                    {
                        "id": project_id,
                        "path": str(project_root),
                        "review": {"repo": repo_slug},
                        "queue": [],
                        "queue_sources": [{"kind": "worklist", "path": "WORKLIST.md", "mode": "replace"}],
                    },
                    sort_keys=False,
                ),
                encoding="utf-8",
            )
        aggregate_root = root / "state" / "chummer_design_supervisor"
        shard_one_root = aggregate_root / "shard-1"
        shard_two_root = aggregate_root / "shard-2"
        shard_three_root = aggregate_root / "shard-3"
        for shard_root in (shard_one_root, shard_two_root, shard_three_root):
            shard_root.mkdir(parents=True, exist_ok=True)

        registry_path = root / "registry.yaml"
        args_one = _args(root)
        args_one.focus_owner = ["chummer6-ui", "chummer6-ui-kit"]
        args_one.focus_text = ["desktop", "client", "workbench", "rules", "sr4", "sr5", "sr6"]
        audit = module._design_completion_audit(args_one, [])
        full_frontier_ids = [
            item.id for item in module._completion_review_frontier(audit, registry_path.resolve(), [])
        ]
        context_one = module.derive_completion_review_context(
            args_one,
            shard_one_root,
            base_context=module.derive_context(args_one),
            audit=audit,
        )
        assert len(context_one["frontier_ids"]) == 3
        module._write_json(
            shard_one_root / "state.json",
            {
                "updated_at": "2026-03-31T18:20:47Z",
                "mode": "completion_review",
                "frontier_ids": context_one["frontier_ids"],
                "active_run": {
                    "run_id": "run-1",
                    "frontier_ids": context_one["frontier_ids"],
                    "open_milestone_ids": [],
                },
            },
        )

        args_two = _args(root)
        args_two.focus_owner = ["chummer6-core"]
        args_two.focus_text = ["desktop", "client", "workbench", "rules", "sr4", "sr5", "sr6"]
        context_two = module.derive_completion_review_context(
            args_two,
            shard_two_root,
            base_context=module.derive_context(args_two),
            audit=audit,
        )
        assert len(context_two["frontier_ids"]) == 3
        module._write_json(
            shard_two_root / "state.json",
            {
                "updated_at": "2026-03-31T18:20:50Z",
                "mode": "completion_review",
                "frontier_ids": context_two["frontier_ids"],
                "active_run": {
                    "run_id": "run-2",
                    "frontier_ids": context_two["frontier_ids"],
                    "open_milestone_ids": [],
                },
            },
        )

        args_three = _args(root)
        args_three.focus_owner = ["chummer6-hub", "chummer6-hub-registry", "chummer6-design"]
        args_three.focus_text = ["registry", "contracts", "desktop", "client"]
        context_three = module.derive_completion_review_context(
            args_three,
            shard_three_root,
            base_context=module.derive_context(args_three),
            audit=audit,
        )

        combined_ids = context_one["frontier_ids"] + context_two["frontier_ids"] + context_three["frontier_ids"]
        assert len(context_three["frontier_ids"]) == 1
        assert sorted(combined_ids) == sorted(full_frontier_ids)
        assert len(set(combined_ids)) == len(full_frontier_ids)


def test_run_once_keeps_completion_review_when_local_shard_slice_is_empty(monkeypatch) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "registry.yaml").write_text("waves: []\nmilestones: []\n", encoding="utf-8")
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("Everything is done.\n", encoding="utf-8")
        _write_completion_evidence(root)
        task = "Publish and execute the ruleset-specific workbench adaptation lane"
        _write_project_backlog(root, project_id="ui", repo_slug="chummer6-ui", task=task)
        aggregate_root = root / "state" / "chummer_design_supervisor"
        shard_one_root = aggregate_root / "shard-1"
        shard_two_root = aggregate_root / "shard-2"
        shard_one_root.mkdir(parents=True, exist_ok=True)
        shard_two_root.mkdir(parents=True, exist_ok=True)
        module._write_json(
            shard_one_root / "state.json",
            {
                "updated_at": "2026-03-31T17:22:15Z",
                "mode": "completion_review",
                "frontier_ids": [],
                "active_run": {
                    "run_id": "run-1",
                    "frontier_ids": [
                        module._synthetic_completion_review_id(f"repo-backlog:ui:{task}"),
                    ],
                    "open_milestone_ids": [],
                },
            },
        )
        args = _args(root)
        args.state_root = str(shard_two_root)
        args.command = "once"
        prompts: list[str] = []

        def fake_run(command, *, input, text, capture_output, cwd, check, env=None):
            prompts.append(input)
            message_path = Path(command[command.index("-o") + 1])
            message_path.write_text(
                "What shipped: reinforced repo-backlog recovery while review work was already claimed\n"
                "What remains: repo-backlog recovery still needs the remaining frontier\n"
                "Exact blocker: none\n",
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        _patch_launch_worker_fake_run(monkeypatch, module, fake_run)
        exit_code = module.run_once(args)

        state_payload = json.loads((shard_two_root / "state.json").read_text(encoding="utf-8"))
        assert exit_code == 0
        assert prompts
        assert state_payload["mode"] == "completion_review"
        assert state_payload["frontier_ids"] == [
            module._synthetic_completion_review_id(f"repo-backlog:ui:{task}")
        ]
        assert state_payload["completion_audit"]["status"] == "fail"
        assert state_payload["eta"]["status"] == "recovery"


def test_live_state_with_open_milestones_clears_stale_shard_activity() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "registry.yaml").write_text(
            yaml.safe_dump(
                {
                    "waves": [{"id": "W1"}],
                    "milestones": [
                        {
                            "id": 1,
                            "title": "Gold install lane",
                            "wave": "W1",
                            "status": "planned",
                            "owners": ["fleet", "chummer6-ui"],
                            "exit_criteria": ["Install lane is real."],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("Gold install lane remains active.\n", encoding="utf-8")
        state_root = root / "state" / "chummer_design_supervisor"
        shard_root = state_root / "shard-1"
        shard_root.mkdir(parents=True, exist_ok=True)
        stale_frontier_id = module._synthetic_completion_review_id("repo-backlog:ui:stale")
        module._write_json(
            state_root / "state.json",
            {
                "updated_at": "2026-04-03T15:20:21Z",
                "mode": "sharded",
                "frontier_ids": [stale_frontier_id],
                "active_run": {
                    "run_id": "stale-run",
                    "frontier_ids": [stale_frontier_id],
                    "open_milestone_ids": [],
                },
            },
        )
        module._write_json(
            shard_root / "state.json",
            {
                "updated_at": "2026-04-03T15:20:21Z",
                "mode": "complete",
                "frontier_ids": [stale_frontier_id],
                "active_run": {
                    "run_id": "stale-shard-run",
                    "frontier_ids": [stale_frontier_id],
                    "open_milestone_ids": [],
                },
            },
        )
        args = _args(root)
        args.state_root = str(state_root)

        state, history = module._effective_supervisor_state(state_root, history_limit=module.ETA_HISTORY_LIMIT)
        updated, _ = module._live_state_with_current_completion_audit(args, state_root, state, history)

        assert updated["open_milestone_ids"] == [1]
        assert updated["frontier_ids"] == [1]
        assert "active_run" not in updated
        assert updated["mode"] == "loop"
        assert updated["shards"][0]["frontier_ids"] == [1]
        assert updated["shards"][0]["active_frontier_ids"] == []
        assert updated["shards"][0]["active_run_id"] == ""


def test_live_state_with_open_milestones_does_not_inherit_stale_focus_from_prior_wave() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "registry.yaml").write_text(
            yaml.safe_dump(
                {
                    "waves": [{"id": "W1"}],
                    "milestones": [
                        {
                            "id": 1,
                            "title": "Gold install lane",
                            "wave": "W1",
                            "status": "planned",
                            "owners": ["fleet", "chummer6-ui"],
                            "exit_criteria": ["Install lane is real."],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("Legacy desktop visual parity remains open.\n", encoding="utf-8")
        state_root = root / "state" / "chummer_design_supervisor"
        state_root.mkdir(parents=True, exist_ok=True)
        module._write_json(
            state_root / "state.json",
            {
                "updated_at": "2026-04-03T15:20:21Z",
                "mode": "completion_review",
                "frontier_ids": [99],
                "focus_profiles": ["desktop_visual_familiarity"],
                "focus_owners": ["chummer6-ui", "chummer6-ui-kit", "chummer6-design"],
                "focus_texts": ["palette", "tab", "shell", "legacy"],
            },
        )
        args = _args(root)
        args.state_root = str(state_root)

        state, history = module._effective_supervisor_state(state_root, history_limit=module.ETA_HISTORY_LIMIT)
        updated, _ = module._live_state_with_current_completion_audit(args, state_root, state, history)

        assert updated["mode"] == "loop"
        assert updated["open_milestone_ids"] == [1]
        assert updated["frontier_ids"] == [1]
        assert updated["focus_profiles"] == []
        assert updated["focus_owners"] == []
        assert updated["focus_texts"] == []


def test_live_state_with_open_milestones_preserves_current_audits() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "registry.yaml").write_text(
            yaml.safe_dump(
                {
                    "waves": [{"id": "W1"}],
                    "milestones": [
                        {
                            "id": 1,
                            "title": "Gold install lane",
                            "wave": "W1",
                            "status": "planned",
                            "owners": ["fleet", "chummer6-ui"],
                            "exit_criteria": ["Install lane is real."],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("Gold install lane remains active.\n", encoding="utf-8")
        _write_completion_evidence(root)
        state_root = root / "state" / "chummer_design_supervisor"
        state_root.mkdir(parents=True, exist_ok=True)
        module._write_json(
            state_root / "state.json",
            {
                "updated_at": "2026-04-03T15:20:21Z",
                "mode": "sharded",
                "completion_audit": {},
                "full_product_audit": {},
            },
        )
        args = _args(root)
        args.state_root = str(state_root)

        state, history = module._effective_supervisor_state(state_root, history_limit=module.ETA_HISTORY_LIMIT)
        updated, _ = module._live_state_with_current_completion_audit(args, state_root, state, history)

        assert updated["mode"] == "loop"
        assert updated["open_milestone_ids"] == [1]
        assert updated["completion_audit"]
        assert updated["full_product_audit"]
        assert updated["completion_audit"]["status"] in {"pass", "fail"}
        assert updated["full_product_audit"]["status"] in {"pass", "fail"}


def test_live_state_with_current_completion_audit_stamps_updated_at_when_missing() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "registry.yaml").write_text(
            yaml.safe_dump(
                {
                    "waves": [{"id": "W1"}],
                    "milestones": [
                        {
                            "id": 1,
                            "title": "Gold install lane",
                            "wave": "W1",
                            "status": "planned",
                            "owners": ["fleet"],
                            "exit_criteria": ["Install lane is real."],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        state_root = root / "state" / "chummer_design_supervisor" / "shard-1"
        state_root.mkdir(parents=True, exist_ok=True)
        args = _args(root)
        args.state_root = str(state_root)

        updated, _history = module._live_state_with_current_completion_audit(
            args,
            state_root,
            {},
            [],
            include_shards=False,
            refresh_flagship_readiness=False,
        )

        assert isinstance(updated["updated_at"], str)
        assert updated["updated_at"]


def test_derive_context_fair_shares_open_milestone_frontier_across_three_shards() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "registry.yaml").write_text(
            yaml.safe_dump(
                {
                    "waves": [{"id": "W1"}],
                    "milestones": [
                        {
                            "id": milestone_id,
                            "title": f"Milestone {milestone_id}",
                            "wave": "W1",
                            "status": "planned",
                            "owners": ["fleet"],
                            "exit_criteria": [f"Milestone {milestone_id} ships."],
                        }
                        for milestone_id in range(1, 7)
                    ],
                }
            ),
            encoding="utf-8",
        )
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("Everything is done.\n", encoding="utf-8")
        aggregate_root = root / "state" / "chummer_design_supervisor"
        shard_one_root = aggregate_root / "shard-1"
        shard_two_root = aggregate_root / "shard-2"
        shard_three_root = aggregate_root / "shard-3"
        for shard_root in (shard_one_root, shard_two_root, shard_three_root):
            shard_root.mkdir(parents=True, exist_ok=True)

        args_one = _args(root)
        args_one.state_root = str(shard_one_root)
        args_two = _args(root)
        args_two.state_root = str(shard_two_root)
        args_three = _args(root)
        args_three.state_root = str(shard_three_root)

        context_one = module.derive_context(args_one)
        context_two = module.derive_context(args_two)
        context_three = module.derive_context(args_three)

        combined_ids = context_one["frontier_ids"] + context_two["frontier_ids"] + context_three["frontier_ids"]

        assert context_one["frontier_ids"] == [1, 2]
        assert context_two["frontier_ids"] == [3, 4]
        assert context_three["frontier_ids"] == [5]
        assert sorted(combined_ids) == [1, 2, 3, 4, 5]


def test_live_shard_summaries_fair_share_open_milestones_across_three_shards() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "registry.yaml").write_text(
            yaml.safe_dump(
                {
                    "waves": [{"id": "W1"}],
                    "milestones": [
                        {
                            "id": milestone_id,
                            "title": f"Milestone {milestone_id}",
                            "wave": "W1",
                            "status": "planned",
                            "owners": ["fleet"],
                            "exit_criteria": [f"Milestone {milestone_id} ships."],
                        }
                        for milestone_id in range(1, 7)
                    ],
                }
            ),
            encoding="utf-8",
        )
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("Everything is done.\n", encoding="utf-8")
        aggregate_root = root / "state" / "chummer_design_supervisor"
        for shard_name in ("shard-1", "shard-2", "shard-3"):
            shard_root = aggregate_root / shard_name
            shard_root.mkdir(parents=True, exist_ok=True)
            module._write_json(
                shard_root / "state.json",
                {
                    "updated_at": "2026-04-03T15:20:21Z",
                    "mode": "loop",
                    "frontier_ids": [],
                    "open_milestone_ids": [1, 2, 3, 4, 5, 6],
                },
            )
        args = _args(root)
        args.state_root = str(aggregate_root)

        summaries = module._live_shard_summaries(args, aggregate_root)

        assert [item["frontier_ids"] for item in summaries] == [[1, 2], [3, 4], [5]]


def test_run_once_keeps_loop_when_open_wave_local_slice_is_empty(monkeypatch) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "registry.yaml").write_text(
            yaml.safe_dump(
                {
                    "waves": [{"id": "W1"}],
                    "milestones": [
                        {
                            "id": milestone_id,
                            "title": f"Milestone {milestone_id}",
                            "wave": "W1",
                            "status": "planned",
                            "owners": ["fleet"],
                            "exit_criteria": [f"Milestone {milestone_id} ships."],
                        }
                        for milestone_id in range(1, 3)
                    ],
                }
            ),
            encoding="utf-8",
        )
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("Everything is done.\n", encoding="utf-8")
        aggregate_root = root / "state" / "chummer_design_supervisor"
        for shard_name in ("shard-1", "shard-2", "shard-3"):
            (aggregate_root / shard_name).mkdir(parents=True, exist_ok=True)
        args = _args(root)
        args.state_root = str(aggregate_root / "shard-3")
        monkeypatch.setattr(module, "_refresh_flagship_product_readiness_artifact", lambda _args: None)

        exit_code = module.run_once(args)
        state_payload = json.loads((Path(args.state_root) / "state.json").read_text(encoding="utf-8"))

        assert exit_code == 0
        assert state_payload["mode"] == "loop"
        assert state_payload["open_milestone_ids"] == [1, 2]
        assert state_payload["frontier_ids"] == []
        assert "last_run" not in state_payload


def test_run_once_launches_completion_review_worker_when_repo_backlog_remains(monkeypatch) -> None:
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
        _write_completion_evidence(root)
        task = "Finish ruleset-specific workbench adaptation lane"
        _write_project_backlog(root, project_id="ui", repo_slug="chummer6-ui", task=task)
        state_root = root / "state"
        state_root.mkdir(parents=True, exist_ok=True)
        (state_root / "history.jsonl").write_text(
            json.dumps(
                {
                    "run_id": "run-good",
                    "worker_exit_code": 0,
                    "accepted": True,
                    "acceptance_reason": "",
                    "shipped": "trusted receipt",
                    "remains": "none",
                    "blocker": "none",
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
                "What shipped: reopened backlog-derived milestone for real implementation\n"
                "What remains: ruleset-specific workbench adaptation lane still needs implementation\n"
                "Exact blocker: none\n",
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        _patch_launch_worker_fake_run(monkeypatch, module, fake_run)

        exit_code = module.run_once(args)
        synthetic_id = module._synthetic_completion_review_id(f"repo-backlog:ui:{task}")

        assert exit_code == 0
        assert prompts
        assert "Repo backlog: ui: Finish ruleset-specific workbench adaptation lane" in prompts[0]
        state_payload = json.loads((state_root / "state.json").read_text(encoding="utf-8"))
        assert state_payload["mode"] == "completion_review"
        assert state_payload["frontier_ids"] == [synthetic_id]
        assert state_payload["completion_audit"]["repo_backlog_audit"]["status"] == "fail"


def test_run_once_enters_flagship_product_when_registry_is_empty_but_flagship_readiness_is_missing(monkeypatch) -> None:
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
        _write_completion_evidence(root)
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

        _patch_launch_worker_fake_run(monkeypatch, module, fake_run)

        exit_code = module.run_once(args)

        assert exit_code == 0
        assert prompts
        assert "Run the flagship full-product delivery pass for Chummer." in prompts[0]
        assert "Desktop flagship non-negotiables:" in prompts[0]
        assert "No generic shell, decorative mainframe, or dashboard-first landing page." in prompts[0]
        assert "First useful screen must be the real workbench or restore continuation flow." in prompts[0]
        assert "Real `File` menu, first-class master index, and first-class character roster are mandatory." in prompts[0]
        assert "browser-only claim-code ritual" in prompts[0]
        assert "framework-first or head-first choice" in prompts[0]
        state_payload = json.loads((state_root / "state.json").read_text(encoding="utf-8"))
        assert state_payload["mode"] == "flagship_product"
        assert state_payload["frontier_ids"]
        assert state_payload["completion_audit"]["status"] == "pass"
        assert state_payload["completion_audit"]["receipt_audit"]["synthetic"] is True
        assert state_payload["full_product_audit"]["status"] == "fail"
        assert state_payload["eta"]["status"] == "blocked"
        assert "full_product_frontier_heuristic" in state_payload["eta"]["basis"]


def test_run_once_reinforces_repo_backlog_slice_when_completion_review_slice_is_already_claimed(monkeypatch) -> None:
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
        _write_completion_evidence(root)
        task = "Finish ruleset-specific workbench adaptation lane"
        _write_project_backlog(root, project_id="ui", repo_slug="chummer6-ui", task=task)
        aggregate_root = root / "state" / "chummer_design_supervisor"
        shard_1 = aggregate_root / "shard-1"
        shard_2 = aggregate_root / "shard-2"
        shard_1.mkdir(parents=True, exist_ok=True)
        shard_2.mkdir(parents=True, exist_ok=True)
        synthetic_id = module._synthetic_completion_review_id(f"repo-backlog:ui:{task}")
        module._write_json(
            shard_1 / "state.json",
            {
                "updated_at": "2026-03-31T08:00:00Z",
                "mode": "completion_review",
                "frontier_ids": [synthetic_id],
                "active_run": {
                    "run_id": "active-1",
                    "frontier_ids": [synthetic_id],
                    "open_milestone_ids": [],
                },
            },
        )
        args = _args(root)
        args.state_root = str(shard_2)
        args.focus_owner = ["chummer6-core"]
        prompts: list[str] = []

        def fake_run(command, *, input, text, capture_output, cwd, check, env=None):
            prompts.append(input)
            message_path = Path(command[command.index("-o") + 1])
            message_path.write_text(
                "What shipped: reinforced repo-backlog recovery slice in parallel\n"
                "What remains: completion review still needs the rest of the repo backlog frontier\n"
                "Exact blocker: none\n",
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        _patch_launch_worker_fake_run(monkeypatch, module, fake_run)

        exit_code = module.run_once(args)

        assert exit_code == 0
        assert prompts
        assert "Run a false-complete recovery pass for the Chummer design supervisor." in prompts[0]
        state_payload = json.loads((shard_2 / "state.json").read_text(encoding="utf-8"))
        assert state_payload["mode"] == "completion_review"
        assert state_payload["frontier_ids"] == [synthetic_id]
        assert state_payload["completion_audit"]["status"] == "fail"
        assert state_payload["eta"]["status"] == "recovery"


def test_run_once_launches_completion_review_worker_when_release_proof_is_not_ready(monkeypatch) -> None:
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
        _write_completion_evidence(root, ui_posture="protected_preview")
        state_root = root / "state"
        state_root.mkdir(parents=True, exist_ok=True)
        (state_root / "history.jsonl").write_text(
            json.dumps(
                {
                    "run_id": "run-9",
                    "worker_exit_code": 0,
                    "accepted": True,
                    "acceptance_reason": "",
                    "primary_milestone_id": 13,
                    "frontier_ids": [13],
                    "shipped": "trusted receipt",
                    "remains": "none",
                    "blocker": "none",
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
                "What shipped: reopened release proof\n"
                "What remains: public promotion proof still needs work\n"
                "Exact blocker: none\n",
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        _patch_launch_worker_fake_run(monkeypatch, module, fake_run)

        exit_code = module.run_once(args)

        assert exit_code == 0
        assert prompts
        assert "Golden journey release-proof gaps" in prompts[0]
        assert "desktop_release_truth" in prompts[0]
        state_payload = json.loads((state_root / "state.json").read_text(encoding="utf-8"))
        assert state_payload["mode"] == "completion_review"
        assert state_payload["completion_audit"]["journey_gate_audit"]["status"] == "fail"
        assert state_payload["frontier_ids"]


def test_run_once_launches_completion_review_worker_when_linux_exit_gate_is_missing(monkeypatch) -> None:
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
        _write_completion_evidence(root, write_linux_desktop_exit_gate=False)
        state_root = root / "state"
        state_root.mkdir(parents=True, exist_ok=True)
        (state_root / "history.jsonl").write_text(
            json.dumps(
                {
                    "run_id": "run-10",
                    "worker_exit_code": 0,
                    "accepted": True,
                    "acceptance_reason": "",
                    "primary_milestone_id": 13,
                    "frontier_ids": [13],
                    "shipped": "trusted receipt",
                    "remains": "none",
                    "blocker": "none",
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
                "What shipped: reopened linux desktop exit gate\n"
                "What remains: linux package proof still needs work\n"
                "Exact blocker: none\n",
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        _patch_launch_worker_fake_run(monkeypatch, module, fake_run)

        exit_code = module.run_once(args)

        assert exit_code == 0
        assert prompts
        assert "Linux desktop exit-gate gaps" in prompts[0]
        assert "linux desktop binary build/start/test proof is missing" in prompts[0]
        state_payload = json.loads((state_root / "state.json").read_text(encoding="utf-8"))
        assert state_payload["mode"] == "completion_review"
        assert state_payload["completion_audit"]["linux_desktop_exit_gate_audit"]["status"] == "fail"
        assert state_payload["frontier_ids"]


def test_run_once_launches_completion_review_worker_when_linux_exit_gate_is_stale(monkeypatch) -> None:
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
        stale_text = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=2)).replace(microsecond=0).isoformat().replace(
            "+00:00", "Z"
        )
        _write_completion_evidence(root, linux_desktop_exit_gate_generated_at=stale_text)
        state_root = root / "state"
        state_root.mkdir(parents=True, exist_ok=True)
        (state_root / "history.jsonl").write_text(
            json.dumps(
                {
                    "run_id": "run-11",
                    "worker_exit_code": 0,
                    "accepted": True,
                    "acceptance_reason": "",
                    "primary_milestone_id": 13,
                    "frontier_ids": [13],
                    "shipped": "trusted receipt",
                    "remains": "none",
                    "blocker": "none",
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
                "What shipped: reopened stale linux exit gate\n"
                "What remains: rebuild fresh linux proof\n"
                "Exact blocker: none\n",
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        _patch_launch_worker_fake_run(monkeypatch, module, fake_run)

        exit_code = module.run_once(args)

        assert exit_code == 0
        assert prompts
        assert "linux desktop exit gate proof is stale" in prompts[0]
        state_payload = json.loads((state_root / "state.json").read_text(encoding="utf-8"))
        assert state_payload["mode"] == "completion_review"
        assert state_payload["completion_audit"]["linux_desktop_exit_gate_audit"]["status"] == "fail"


def test_run_once_launches_completion_review_worker_when_linux_exit_gate_targets_wrong_head(monkeypatch) -> None:
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
        _write_completion_evidence(
            root,
            linux_desktop_exit_gate_app_key="blazor-desktop",
            linux_desktop_exit_gate_launch_target="Chummer.Blazor.Desktop",
        )
        state_root = root / "state"
        state_root.mkdir(parents=True, exist_ok=True)
        (state_root / "history.jsonl").write_text(
            json.dumps(
                {
                    "run_id": "run-12",
                    "worker_exit_code": 0,
                    "accepted": True,
                    "acceptance_reason": "",
                    "primary_milestone_id": 13,
                    "frontier_ids": [13],
                    "shipped": "trusted receipt",
                    "remains": "none",
                    "blocker": "none",
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
                "What shipped: reopened wrong-head linux exit gate\n"
                "What remains: rebuild avalonia linux proof\n"
                "Exact blocker: none\n",
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        _patch_launch_worker_fake_run(monkeypatch, module, fake_run)

        exit_code = module.run_once(args)

        assert exit_code == 0
        assert prompts
        assert "flagship Avalonia head" in prompts[0]
        state_payload = json.loads((state_root / "state.json").read_text(encoding="utf-8"))
        assert state_payload["mode"] == "completion_review"
        assert state_payload["completion_audit"]["linux_desktop_exit_gate_audit"]["status"] == "fail"


def test_run_once_marks_complete_when_release_proof_is_ready() -> None:
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
        _write_completion_evidence(root)
        _write_flagship_product_readiness(root)
        state_root = root / "state"
        state_root.mkdir(parents=True, exist_ok=True)
        (state_root / "history.jsonl").write_text(
            json.dumps(
                {
                    "run_id": "run-9",
                    "worker_exit_code": 0,
                    "accepted": True,
                    "acceptance_reason": "",
                    "primary_milestone_id": 13,
                    "frontier_ids": [13],
                    "shipped": "trusted receipt",
                    "remains": "none",
                    "blocker": "none",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        args = _args(root)

        exit_code = module.run_once(args)

        assert exit_code == 0
        state_payload = json.loads((state_root / "state.json").read_text(encoding="utf-8"))
        assert state_payload["mode"] == "complete"
        assert state_payload["eta"]["status"] == "ready"
        assert state_payload["eta"]["eta_human"] == "ready now"
        assert state_payload["completion_audit"]["status"] == "pass"
        assert state_payload["full_product_audit"]["status"] == "pass"
        assert state_payload["completion_audit"]["journey_gate_audit"]["status"] == "pass"
        assert state_payload["completion_audit"]["linux_desktop_exit_gate_audit"]["status"] == "pass"
        assert state_payload["completion_audit"]["weekly_pulse_audit"]["status"] == "pass"
        assert state_payload["completion_review_frontier_path"].endswith(
            "COMPLETION_REVIEW_FRONTIER.generated.yaml"
        )
        completion_frontier_payload = yaml.safe_load(
            Path(state_payload["completion_review_frontier_path"]).read_text(encoding="utf-8")
        )
        assert completion_frontier_payload["mode"] == "complete"
        assert completion_frontier_payload["completion_audit"]["status"] == "pass"
        assert completion_frontier_payload["frontier_count"] == 0


def test_linux_desktop_exit_gate_audit_allows_git_head_mismatch_when_worktree_fingerprint_is_identical() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "codex@example.com"], cwd=root, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Codex"], cwd=root, check=True, capture_output=True)
        (root / "tracked.txt").write_text("one\n", encoding="utf-8")
        subprocess.run(["git", "add", "tracked.txt"], cwd=root, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=root, check=True, capture_output=True)

        _write_completion_evidence(root)
        proof_path = root / "UI_LINUX_DESKTOP_EXIT_GATE.generated.json"
        payload = json.loads(proof_path.read_text(encoding="utf-8"))
        current_state = module._repo_git_state(
            root,
            exclude_paths=(
                root / ".codex-studio" / "out" / "linux-desktop-exit-gate",
                proof_path,
            ),
            include_markers=module.FLAGSHIP_UI_LINUX_GATE_INPUT_MARKERS,
            include_untracked=False,
        )
        payload["git"] = {
            "repo_root": str(root),
            "available": True,
            "head": "deadbeef",
            "tracked_diff_sha256": current_state["tracked_diff_sha256"],
            "tracked_diff_line_count": current_state["tracked_diff_line_count"],
            "start": {
                "repo_root": str(root),
                "available": True,
                "head": "deadbeef",
                "tracked_diff_sha256": current_state["tracked_diff_sha256"],
                "tracked_diff_line_count": current_state["tracked_diff_line_count"],
            },
            "finish": {
                "repo_root": str(root),
                "available": True,
                "head": "deadbeef",
                "tracked_diff_sha256": current_state["tracked_diff_sha256"],
                "tracked_diff_line_count": current_state["tracked_diff_line_count"],
            },
            "identity_stable": True,
        }
        payload["source_snapshot"]["worktree_sha256"] = current_state["tracked_diff_sha256"]
        payload["source_snapshot"]["finish_worktree_sha256"] = current_state["tracked_diff_sha256"]
        payload["source_snapshot"]["entry_count"] = current_state["tracked_diff_line_count"]
        payload["source_snapshot"]["finish_entry_count"] = current_state["tracked_diff_line_count"]
        proof_path.write_text(json.dumps(payload), encoding="utf-8")

        audit = module._linux_desktop_exit_gate_audit(_args(root))

        assert audit["status"] == "pass"
        assert audit["proof_git_head_matches_current"] is False


def test_exit_gate_audits_preserve_configured_symlink_paths() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_completion_evidence(root)
        alias_root = root / "aliases"
        alias_root.mkdir(parents=True, exist_ok=True)
        linux_alias = alias_root / "UI_LINUX_DESKTOP_EXIT_GATE.generated.json"
        linux_alias.symlink_to(root / "UI_LINUX_DESKTOP_EXIT_GATE.generated.json")
        executable_alias = alias_root / "DESKTOP_EXECUTABLE_EXIT_GATE.generated.json"
        executable_alias.symlink_to(root / "DESKTOP_EXECUTABLE_EXIT_GATE.generated.json")

        args = _args(root)
        args.ui_linux_desktop_exit_gate_path = str(linux_alias)
        args.ui_executable_exit_gate_path = str(executable_alias)

        linux_audit = module._linux_desktop_exit_gate_audit(args)
        executable_audit = module._desktop_executable_exit_gate_audit(args)

        assert linux_audit["status"] == "pass"
        assert linux_audit["path"] == str(linux_alias)
        assert executable_audit["status"] == "pass"
        assert executable_audit["path"] == str(executable_alias)


def test_linux_desktop_exit_gate_audit_uses_top_level_current_git_fields_without_rejecting_stable_proof() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "codex@example.com"], cwd=root, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Codex"], cwd=root, check=True, capture_output=True)
        (root / "tracked.txt").write_text("one\n", encoding="utf-8")
        subprocess.run(["git", "add", "tracked.txt"], cwd=root, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=root, check=True, capture_output=True)

        _write_completion_evidence(root)
        proof_path = root / "UI_LINUX_DESKTOP_EXIT_GATE.generated.json"
        payload = json.loads(proof_path.read_text(encoding="utf-8"))
        current_state = module._repo_git_state(
            root,
            exclude_paths=(
                root / ".codex-studio" / "out" / "linux-desktop-exit-gate",
                proof_path,
            ),
            include_markers=module.FLAGSHIP_UI_LINUX_GATE_INPUT_MARKERS,
            include_untracked=False,
        )
        payload["git"] = {
            "repo_root": str(root),
            "available": True,
            "head": current_state["head"],
            "tracked_diff_sha256": current_state["tracked_diff_sha256"],
            "tracked_diff_line_count": current_state["tracked_diff_line_count"],
            "start": dict(current_state),
            "finish": dict(current_state),
            "identity_stable": True,
        }
        payload["source_snapshot"]["worktree_sha256"] = current_state["tracked_diff_sha256"]
        payload["source_snapshot"]["finish_worktree_sha256"] = current_state["tracked_diff_sha256"]
        payload["source_snapshot"]["entry_count"] = current_state["tracked_diff_line_count"]
        payload["source_snapshot"]["finish_entry_count"] = current_state["tracked_diff_line_count"]
        payload["current_git_available"] = True
        payload["current_git_head"] = current_state["head"]
        payload["current_tracked_diff_sha256"] = "f" * 64
        proof_path.write_text(json.dumps(payload), encoding="utf-8")

        audit = module._linux_desktop_exit_gate_audit(_args(root))

        assert audit["status"] == "pass"
        assert audit["proof_git_head_matches_current"] is True
        assert audit["current_tracked_diff_sha256"] == "f" * 64
        assert audit["proof_tracked_diff_sha256"] == current_state["tracked_diff_sha256"]


def test_linux_desktop_exit_gate_audit_ignores_unrelated_repo_changes() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "codex@example.com"], cwd=root, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Codex"], cwd=root, check=True, capture_output=True)
        (root / "Chummer.Avalonia").mkdir(parents=True, exist_ok=True)
        (root / "Chummer.Presentation").mkdir(parents=True, exist_ok=True)
        (root / "docs").mkdir(parents=True, exist_ok=True)
        (root / "Chummer.Avalonia" / "Chummer.Avalonia.csproj").write_text("<Project />\n", encoding="utf-8")
        (root / "Chummer.Presentation" / "Surface.cs").write_text("namespace Chummer.Presentation;\n", encoding="utf-8")
        (root / "docs" / "notes.md").write_text("baseline\n", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=root, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=root, check=True, capture_output=True)

        _write_completion_evidence(root)
        proof_path = root / "UI_LINUX_DESKTOP_EXIT_GATE.generated.json"
        payload = json.loads(proof_path.read_text(encoding="utf-8"))
        scoped_state = module._repo_git_state(
            root,
            exclude_paths=(
                root / ".codex-studio" / "out" / "linux-desktop-exit-gate",
                proof_path,
            ),
            include_markers=module.FLAGSHIP_UI_LINUX_GATE_INPUT_MARKERS,
        )
        payload["git"] = {
            "repo_root": str(root),
            "available": True,
            "head": scoped_state["head"],
            "tracked_diff_sha256": scoped_state["tracked_diff_sha256"],
            "tracked_diff_line_count": scoped_state["tracked_diff_line_count"],
            "start": dict(scoped_state),
            "finish": dict(scoped_state),
            "identity_stable": True,
        }
        payload["source_snapshot"] = {
            "mode": "filesystem_copy",
            "repo_root": str(root),
            "snapshot_root": str(root / ".linux-desktop-exit-gate-source.fixture"),
            "entry_count": scoped_state["tracked_diff_line_count"],
            "worktree_sha256": scoped_state["tracked_diff_sha256"],
            "finish_entry_count": scoped_state["tracked_diff_line_count"],
            "finish_worktree_sha256": scoped_state["tracked_diff_sha256"],
            "identity_stable": True,
        }
        proof_path.write_text(json.dumps(payload), encoding="utf-8")

        (root / "docs" / "notes.md").write_text("baseline\nchanged\n", encoding="utf-8")

        audit = module._linux_desktop_exit_gate_audit(_args(root))

        assert audit["status"] == "pass"


def test_linux_desktop_exit_gate_audit_rejects_wrong_unit_test_project() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_completion_evidence(root, linux_desktop_exit_gate_test_project_path="Chummer.Tests/Chummer.Tests.csproj")

        audit = module._linux_desktop_exit_gate_audit(_args(root))

        assert audit["status"] == "fail"
        assert "wrong unit-test project" in audit["reason"]


def test_linux_desktop_exit_gate_audit_rejects_wrong_unit_test_framework() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_completion_evidence(root)
        proof_path = root / "UI_LINUX_DESKTOP_EXIT_GATE.generated.json"
        payload = json.loads(proof_path.read_text(encoding="utf-8"))
        payload["unit_tests"]["framework"] = "net9.0"
        proof_path.write_text(json.dumps(payload), encoding="utf-8")

        audit = module._linux_desktop_exit_gate_audit(_args(root))

        assert audit["status"] == "fail"
        assert "wrong unit-test target framework" in audit["reason"]


def test_linux_desktop_exit_gate_audit_rejects_missing_binary_on_disk() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_completion_evidence(root)
        (
            root
            / ".codex-studio"
            / "out"
            / "linux-desktop-exit-gate"
            / "run.fixture"
            / "publish"
            / "avalonia-linux-x64"
            / "Chummer.Avalonia"
        ).unlink()

        audit = module._linux_desktop_exit_gate_audit(_args(root))

        assert audit["status"] == "fail"
        assert "built Linux desktop binary" in audit["reason"]


def test_linux_desktop_exit_gate_audit_rejects_missing_deb_install_verification() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_completion_evidence(root)
        receipt_path = (
            root
            / ".codex-studio"
            / "out"
            / "linux-desktop-exit-gate"
            / "run.fixture"
            / "startup-smoke-installer"
            / "startup-smoke-avalonia-linux-x64.receipt.json"
        )
        payload = json.loads(receipt_path.read_text(encoding="utf-8"))
        payload.pop("artifactInstallVerificationPath", None)
        receipt_path.write_text(json.dumps(payload), encoding="utf-8")

        audit = module._linux_desktop_exit_gate_audit(_args(root))

        assert audit["status"] == "fail"
        assert "primary .deb install/remove verification is missing" in audit["reason"]


def test_linux_desktop_exit_gate_audit_rejects_invalid_deb_install_verification_log() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_completion_evidence(root)
        verification_path = (
            root
            / ".codex-studio"
            / "out"
            / "linux-desktop-exit-gate"
            / "run.fixture"
            / "startup-smoke-installer"
            / "install-verification-avalonia-linux-x64.json"
        )
        payload = json.loads(verification_path.read_text(encoding="utf-8"))
        payload["dpkgLogPath"] = str(root / "outside.log")
        verification_path.write_text(json.dumps(payload), encoding="utf-8")

        audit = module._linux_desktop_exit_gate_audit(_args(root))

        assert audit["status"] == "fail"
        assert "primary .deb install/remove verification is invalid" in audit["reason"]


def test_linux_desktop_exit_gate_audit_rejects_receipt_digest_mismatch() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_completion_evidence(root)
        receipt_path = (
            root
            / ".codex-studio"
            / "out"
            / "linux-desktop-exit-gate"
            / "run.fixture"
            / "startup-smoke-installer"
            / "startup-smoke-avalonia-linux-x64.receipt.json"
        )
        payload = json.loads(receipt_path.read_text(encoding="utf-8"))
        payload["artifactDigest"] = "sha256:" + ("0" * 64)
        receipt_path.write_text(json.dumps(payload), encoding="utf-8")

        audit = module._linux_desktop_exit_gate_audit(_args(root))

        assert audit["status"] == "fail"
        assert "primary startup smoke is invalid" in audit["reason"]


def test_linux_desktop_exit_gate_audit_accepts_release_channel_promoted_receipt_digest() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_completion_evidence(root)
        proof_path = root / "UI_LINUX_DESKTOP_EXIT_GATE.generated.json"
        receipt_path = (
            root
            / ".codex-studio"
            / "out"
            / "linux-desktop-exit-gate"
            / "run.fixture"
            / "startup-smoke-installer"
            / "startup-smoke-avalonia-linux-x64.receipt.json"
        )

        promoted_digest = "a" * 64
        receipt_payload = json.loads(receipt_path.read_text(encoding="utf-8"))
        receipt_payload["artifactDigest"] = f"sha256:{promoted_digest}"
        receipt_path.write_text(json.dumps(receipt_payload), encoding="utf-8")

        proof_payload = json.loads(proof_path.read_text(encoding="utf-8"))
        proof_payload.setdefault("checks", {})
        proof_payload["checks"]["release_channel_linux_artifact"] = {
            "sha256": promoted_digest
        }
        proof_path.write_text(json.dumps(proof_payload), encoding="utf-8")

        audit = module._linux_desktop_exit_gate_audit(_args(root))

        assert audit["status"] == "pass"
        assert audit["primary_smoke_status"] == "passed"


def test_linux_desktop_exit_gate_audit_rejects_wrong_unit_test_assembly() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_completion_evidence(root, linux_desktop_exit_gate_test_assembly_name="Some.Other.Tests.dll")

        audit = module._linux_desktop_exit_gate_audit(_args(root))

        assert audit["status"] == "fail"
        assert "wrong unit-test assembly" in audit["reason"] or "unit-test status is invalid" in audit["reason"]


def test_linux_desktop_exit_gate_audit_rejects_run_root_escape() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_completion_evidence(root)
        proof_path = root / "UI_LINUX_DESKTOP_EXIT_GATE.generated.json"
        payload = json.loads(proof_path.read_text(encoding="utf-8"))
        escaped_run_root = root / "escaped-run"
        escaped_run_root.mkdir(parents=True, exist_ok=True)
        payload["run_root"] = str(escaped_run_root)
        proof_path.write_text(json.dumps(payload), encoding="utf-8")

        audit = module._linux_desktop_exit_gate_audit(_args(root))

        assert audit["status"] == "fail"
        assert "outside the canonical output root" in audit["reason"]


def test_linux_desktop_exit_gate_audit_rejects_repo_mutation_during_run() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "codex@example.com"], cwd=root, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Codex"], cwd=root, check=True, capture_output=True)
        (root / "tracked.txt").write_text("one\n", encoding="utf-8")
        subprocess.run(["git", "add", "tracked.txt"], cwd=root, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=root, check=True, capture_output=True)

        _write_completion_evidence(root)
        proof_path = root / "UI_LINUX_DESKTOP_EXIT_GATE.generated.json"
        payload = json.loads(proof_path.read_text(encoding="utf-8"))
        payload["git"]["start"]["tracked_diff_sha256"] = "deadbeef"
        payload["git"]["identity_stable"] = False
        proof_path.write_text(json.dumps(payload), encoding="utf-8")

        audit = module._linux_desktop_exit_gate_audit(_args(root))

        assert audit["status"] == "fail"
        assert "repo changed while the proof run was executing" in audit["reason"]


def test_linux_desktop_exit_gate_audit_rejects_missing_source_snapshot() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_completion_evidence(root)
        proof_path = root / "UI_LINUX_DESKTOP_EXIT_GATE.generated.json"
        payload = json.loads(proof_path.read_text(encoding="utf-8"))
        payload.pop("source_snapshot", None)
        proof_path.write_text(json.dumps(payload), encoding="utf-8")

        audit = module._linux_desktop_exit_gate_audit(_args(root))

        assert audit["status"] == "fail"
        assert "immutable source-snapshot metadata" in audit["reason"]


def test_linux_desktop_exit_gate_audit_rejects_unstable_source_snapshot() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_completion_evidence(root)
        proof_path = root / "UI_LINUX_DESKTOP_EXIT_GATE.generated.json"
        payload = json.loads(proof_path.read_text(encoding="utf-8"))
        payload["source_snapshot"]["finish_worktree_sha256"] = "deadbeef"
        payload["source_snapshot"]["finish_entry_count"] = payload["source_snapshot"]["entry_count"]
        payload["source_snapshot"]["identity_stable"] = False
        proof_path.write_text(json.dumps(payload), encoding="utf-8")

        audit = module._linux_desktop_exit_gate_audit(_args(root))

        assert audit["status"] == "fail"
        assert "did not stay stable through the full run" in audit["reason"]


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


def test_render_status_includes_eta_fields() -> None:
    module = _load_module()

    rendered = module._render_status(
        {
            "updated_at": "2026-03-31T10:00:00Z",
            "mode": "loop",
            "open_milestone_ids": [6, 21],
            "frontier_ids": [6],
            "focus_profiles": ["desktop_client"],
            "focus_owners": ["chummer6-ui"],
            "focus_texts": ["desktop"],
            "eta": {
                "status": "estimated",
                "eta_human": "8-16h",
                "eta_confidence": "medium",
                "basis": "empirical_open_milestone_burn",
                "scope_kind": "open_milestone_frontier",
                "scope_label": "Current open milestone frontier",
                "scope_warning": "This is a tactical frontier ETA only.",
                "summary": "2 open milestones remain.",
                "predicted_completion_at": "2026-03-31T22:00:00Z",
                "blocking_reason": "",
            },
        }
    )

    assert "eta.status: estimated" in rendered
    assert "eta.human: 8-16h" in rendered
    assert "eta.confidence: medium" in rendered
    assert "eta.basis: empirical_open_milestone_burn" in rendered
    assert "eta.scope_kind: open_milestone_frontier" in rendered
    assert "eta.scope_label: Current open milestone frontier" in rendered
    assert "eta.summary: 2 open milestones remain." in rendered


def test_render_status_includes_completion_review_frontier_and_backlog_fields() -> None:
    module = _load_module()

    rendered = module._render_status(
        {
            "updated_at": "2026-03-31T10:00:00Z",
            "mode": "completion_review",
            "open_milestone_ids": [],
            "frontier_ids": [1394756221],
            "completion_review_frontier_path": "/tmp/COMPLETION_REVIEW_FRONTIER.generated.yaml",
            "completion_review_frontier_mirror_path": "/tmp/state/artifacts/COMPLETION_REVIEW_FRONTIER.generated.yaml",
            "completion_audit": {
                "status": "fail",
                "reason": "repo-local backlog audit failed",
                "repo_backlog_audit": {
                    "status": "fail",
                    "reason": "active repo-local backlog remains outside the closed design registry: ui",
                    "open_item_count": 1,
                    "open_project_count": 1,
                },
            },
        }
    )

    assert "completion_review_frontier.path: /tmp/COMPLETION_REVIEW_FRONTIER.generated.yaml" in rendered
    assert "completion_review_frontier.mirror_path: /tmp/state/artifacts/COMPLETION_REVIEW_FRONTIER.generated.yaml" in rendered
    assert "completion_audit.repo_backlog_status: fail" in rendered
    assert "completion_audit.repo_backlog_open_item_count: 1" in rendered


def test_render_status_includes_worker_lane_health_fields() -> None:
    module = _load_module()

    rendered = module._render_status(
        {
            "updated_at": "2026-03-31T10:00:00Z",
            "mode": "completion_review",
            "open_milestone_ids": [],
            "frontier_ids": [1394756221],
            "worker_lane_health": {
                "status": "pass",
                "reason": "provider-health preflight marked repair unroutable",
                "fetched_at": "2026-03-31T10:00:05Z",
                "source_url": "http://127.0.0.1:8090/v1/responses/_provider_health",
                "routable_lanes": ["core", "survival"],
                "unroutable_lanes": ["repair"],
                "lanes": {
                    "core": {
                        "profile": "core_batch",
                        "state": "ready",
                        "routable": True,
                        "ready_slots": 47,
                        "remaining_percent_of_max": 0.05,
                        "reason": "onemin:ready",
                    },
                    "repair": {
                        "profile": "repair",
                        "state": "degraded",
                        "routable": False,
                        "ready_slots": 0,
                        "remaining_percent_of_max": None,
                        "reason": "magixai degraded with no ready slots",
                    },
                },
            },
        }
    )

    assert "worker_lane_health.status: pass" in rendered
    assert "worker_lane_health.routable_lanes: core, survival" in rendered
    assert "worker_lane_health.unroutable_lanes: repair" in rendered
    assert "worker_lane_health.repair: profile=repair state=degraded routable=no" in rendered


def test_render_status_includes_idle_reason() -> None:
    module = _load_module()

    rendered = module._render_status(
        {
            "updated_at": "2026-03-31T10:00:00Z",
            "mode": "flagship_product",
            "open_milestone_ids": [],
            "frontier_ids": [],
            "focus_profiles": [],
            "focus_owners": [],
            "focus_texts": [],
            "idle_reason": "waiting_for_local_frontier_slice",
        }
    )

    assert "idle_reason: waiting_for_local_frontier_slice" in rendered


def test_render_status_includes_active_run_watchdog_timeout_seconds() -> None:
    module = _load_module()

    rendered = module._render_status(
        {
            "updated_at": "2026-03-31T10:00:00Z",
            "mode": "completion_review",
            "open_milestone_ids": [],
            "frontier_ids": [1394756221],
            "active_run": {
                "run_id": "run-1",
                "started_at": "2026-03-31T09:55:00Z",
                "selected_account_alias": "lane:core",
                "selected_model": "default",
                "attempt_index": 1,
                "total_attempts": 4,
                "primary_milestone_id": 1394756221,
                "last_message_path": "/tmp/last_message.txt",
                "watchdog_timeout_seconds": 21600.0,
            },
        }
    )

    assert "active_run.watchdog_timeout_seconds: 21600.0" in rendered


def test_effective_supervisor_state_merges_shard_state_and_history() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        state_root = root / "state"
        shard_1 = state_root / "shard-1"
        shard_2 = state_root / "shard-2"
        shard_1.mkdir(parents=True, exist_ok=True)
        shard_2.mkdir(parents=True, exist_ok=True)
        module._write_json(
            shard_1 / "state.json",
            {
                "updated_at": "2026-03-31T10:00:00Z",
                "mode": "completion_review",
                "open_milestone_ids": [],
                "frontier_ids": [13],
                "focus_owners": ["chummer6-ui"],
                "eta": {"status": "blocked"},
                "last_run": {
                    "run_id": "run-1",
                    "finished_at": "2026-03-31T10:00:00Z",
                    "worker_exit_code": 0,
                },
            },
        )
        module._write_json(
            shard_2 / "state.json",
            {
                "updated_at": "2026-03-31T10:05:00Z",
                "mode": "completion_review",
                "open_milestone_ids": [],
                "frontier_ids": [14],
                "focus_owners": ["chummer6-core"],
                "eta": {"status": "blocked"},
                "active_run": {
                    "run_id": "run-3",
                    "started_at": "2026-03-31T10:06:00Z",
                    "selected_account_alias": "lane:core",
                },
                "last_run": {
                    "run_id": "run-2",
                    "finished_at": "2026-03-31T10:05:00Z",
                    "worker_exit_code": 0,
                },
            },
        )
        module._append_jsonl(
            shard_1 / "history.jsonl",
            {
                "run_id": "run-1",
                "finished_at": "2026-03-31T10:00:00Z",
                "worker_exit_code": 0,
                "frontier_ids": [13],
            },
        )
        module._append_jsonl(
            shard_2 / "history.jsonl",
            {
                "run_id": "run-2",
                "finished_at": "2026-03-31T10:05:00Z",
                "worker_exit_code": 0,
                "frontier_ids": [14],
            },
        )

        state, history = module._effective_supervisor_state(state_root, history_limit=10)

        assert state["shard_count"] == 2
        assert state["frontier_ids"] == [13, 14]
        assert state["focus_owners"] == ["chummer6-core", "chummer6-ui"]
        assert state["last_run"]["run_id"] == "run-2"
        assert state["active_run"]["run_id"] == "run-3"
        assert state["shards"][1]["active_run_id"] == "run-3"
        assert [item["run_id"] for item in history] == ["run-1", "run-2"]
        assert history[-1]["_shard"] == "shard-2"


def test_effective_supervisor_state_marks_aggregate_eta_as_mixed_when_shards_disagree_on_scope() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        state_root = root / "state"
        shard_1 = state_root / "shard-1"
        shard_2 = state_root / "shard-2"
        shard_1.mkdir(parents=True, exist_ok=True)
        shard_2.mkdir(parents=True, exist_ok=True)
        module._write_json(
            shard_1 / "state.json",
            {
                "updated_at": "2026-03-31T10:00:00Z",
                "mode": "loop",
                "open_milestone_ids": [13, 14],
                "frontier_ids": [13, 14],
                "eta": {
                    "status": "estimated",
                    "eta_human": "3d-1w",
                    "basis": "heuristic_status_mix",
                    "scope_kind": "open_milestone_frontier",
                    "remaining_open_milestones": 2,
                    "remaining_in_progress_milestones": 2,
                    "remaining_not_started_milestones": 0,
                    "summary": "2 open milestones remain.",
                },
            },
        )
        module._write_json(
            shard_2 / "state.json",
            {
                "updated_at": "2026-03-31T10:05:00Z",
                "mode": "flagship_product",
                "open_milestone_ids": [],
                "frontier_ids": [99],
                "eta": {
                    "status": "flagship_delivery",
                    "eta_human": "8-16h",
                    "basis": "full_product_frontier_heuristic",
                    "scope_kind": "flagship_product_readiness",
                    "remaining_open_milestones": 0,
                    "remaining_in_progress_milestones": 0,
                    "remaining_not_started_milestones": 1,
                    "summary": "flagship closeout remains.",
                },
            },
        )

        state, _history = module._effective_supervisor_state(state_root, history_limit=10)

        assert state["eta"]["status"] == "tracked"
        assert state["eta"]["eta_human"] == "tracked"
        assert state["eta"]["basis"] == "aggregate_shard_eta_scope_mismatch"
        assert state["eta"]["scope_kind"] == "aggregate_shard_mixed_scope"
        assert "mixes ETA scopes" in state["eta"]["summary"]


def test_fast_status_state_rebuilds_parallel_flagship_eta_from_statefile_shards() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        aggregate_root = Path(tmp) / "state" / "chummer_design_supervisor"
        aggregate_root.mkdir(parents=True, exist_ok=True)
        shard_one_root = aggregate_root / "shard-1"
        shard_two_root = aggregate_root / "shard-2"
        shard_one_root.mkdir(parents=True, exist_ok=True)
        shard_two_root.mkdir(parents=True, exist_ok=True)
        module._write_json(
            aggregate_root / "state.json",
            {
                "updated_at": "2026-04-08T18:00:00Z",
                "mode": "sharded",
                "eta": {
                    "status": "unknown",
                    "summary": "booting",
                    "scope_kind": "unknown",
                    "remaining_open_milestones": 0,
                    "remaining_in_progress_milestones": 0,
                    "remaining_not_started_milestones": 0,
                },
            },
        )
        module._write_json(
            shard_one_root / "state.json",
            {
                "updated_at": "2026-04-08T18:04:07Z",
                "mode": "flagship_product",
                "frontier_ids": [5162239657],
                "eta": {
                    "status": "flagship_delivery",
                    "eta_human": "7h-18h",
                    "basis": "full_product_frontier_heuristic",
                    "scope_kind": "flagship_product_readiness",
                    "range_low_hours": 7.0,
                    "range_high_hours": 18.0,
                    "remaining_open_milestones": 0,
                    "remaining_in_progress_milestones": 0,
                    "remaining_not_started_milestones": 1,
                    "summary": "flagship closeout remains",
                },
                "active_run": {
                    "run_id": "run-1",
                    "frontier_ids": [5162239657],
                    "started_at": "2026-04-08T18:03:14Z",
                },
            },
        )
        module._write_json(
            shard_two_root / "state.json",
            {
                "updated_at": "2026-04-08T18:04:18Z",
                "mode": "flagship_product",
                "frontier_ids": [2137070369],
                "eta": {
                    "status": "flagship_delivery",
                    "eta_human": "7h-16h",
                    "basis": "full_product_frontier_heuristic",
                    "scope_kind": "flagship_product_readiness",
                    "range_low_hours": 7.0,
                    "range_high_hours": 16.0,
                    "remaining_open_milestones": 0,
                    "remaining_in_progress_milestones": 0,
                    "remaining_not_started_milestones": 1,
                    "summary": "flagship closeout remains",
                },
                "active_run": {
                    "run_id": "run-2",
                    "frontier_ids": [2137070369],
                    "started_at": "2026-04-08T18:03:25Z",
                },
            },
        )
        (aggregate_root / "active_shards.json").write_text(
            json.dumps(
                {
                    "active_shards": [
                        {"name": "shard-1", "frontier_ids": [5162239657]},
                        {"name": "shard-2", "frontier_ids": [2137070369]},
                    ]
                }
            ),
            encoding="utf-8",
        )

        updated = module._fast_status_state(Namespace(), aggregate_root, module._read_state(aggregate_root / "state.json"), include_shards=True)

        assert updated["active_runs_count"] == 2
        assert updated["eta"]["basis"] == "aggregate_shard_parallel_scope"
        assert updated["eta"]["eta_human"] == "7h-18h"
        assert updated["eta"]["range_low_hours"] == 7.0
        assert updated["eta"]["range_high_hours"] == 18.0
        assert updated["eta"]["scope_kind"] == "flagship_product_readiness"
        assert updated["eta"]["remaining_open_milestones"] == 2
        assert updated["eta"]["remaining_in_progress_milestones"] == 2
        assert updated["eta"]["remaining_not_started_milestones"] == 0
        assert "parallelized across 2 active shards" in updated["eta"]["summary"]


def test_fast_status_state_keeps_latest_worker_lane_and_audit_fields_from_shards() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        aggregate_root = Path(tmp) / "state" / "chummer_design_supervisor"
        aggregate_root.mkdir(parents=True, exist_ok=True)
        shard_one_root = aggregate_root / "shard-1"
        shard_two_root = aggregate_root / "shard-2"
        shard_one_root.mkdir(parents=True, exist_ok=True)
        shard_two_root.mkdir(parents=True, exist_ok=True)
        module._write_json(
            aggregate_root / "state.json",
            {
                "updated_at": "2026-04-09T11:59:00Z",
                "mode": "sharded",
                "completion_audit": {},
                "full_product_audit": {},
                "eta": {},
                "worker_lane_health": {},
            },
        )
        module._write_json(
            shard_one_root / "state.json",
            {
                "updated_at": "2026-04-09T12:00:00Z",
                "mode": "flagship_product",
                "completion_audit": {
                    "status": "fail",
                    "reason": "completion backlog remains",
                },
                "full_product_audit": {
                    "status": "fail",
                    "reason": "desktop client missing",
                },
                "eta": {
                    "status": "flagship_delivery",
                    "eta_human": "7h-18h",
                    "basis": "full_product_frontier_heuristic",
                    "scope_kind": "flagship_product_readiness",
                    "remaining_open_milestones": 0,
                    "remaining_in_progress_milestones": 0,
                    "remaining_not_started_milestones": 1,
                    "summary": "flagship closeout remains",
                },
                "worker_lane_health": {
                    "status": "pass",
                    "reason": "healthy",
                },
                "flagship_product_readiness_path": "/tmp/flagship-one.json",
                "active_run": {
                    "run_id": "run-1",
                    "frontier_ids": [1],
                    "started_at": "2026-04-09T12:00:00Z",
                },
            },
        )
        module._write_json(
            shard_two_root / "state.json",
            {
                "updated_at": "2026-04-09T12:01:00Z",
                "mode": "flagship_product",
                "completion_audit": {
                    "status": "fail",
                    "reason": "external proof pending",
                },
                "full_product_audit": {
                    "status": "fail",
                    "reason": "desktop proof incomplete",
                },
                "eta": {
                    "status": "flagship_delivery",
                    "eta_human": "6h-16h",
                    "basis": "full_product_frontier_heuristic",
                    "scope_kind": "flagship_product_readiness",
                    "remaining_open_milestones": 0,
                    "remaining_in_progress_milestones": 0,
                    "remaining_not_started_milestones": 1,
                    "summary": "flagship closeout remains",
                },
                "worker_lane_health": {
                    "status": "warning",
                    "reason": "provider degraded",
                },
                "flagship_product_readiness_path": "/tmp/flagship-two.json",
                "active_run": {
                    "run_id": "run-2",
                    "frontier_ids": [2],
                    "started_at": "2026-04-09T12:01:00Z",
                },
            },
        )
        (aggregate_root / "active_shards.json").write_text(
            json.dumps(
                {
                    "active_shards": [
                        {"name": "shard-1", "frontier_ids": [1]},
                        {"name": "shard-2", "frontier_ids": [2]},
                    ]
                }
            ),
            encoding="utf-8",
        )

        updated = module._fast_status_state(
            Namespace(),
            aggregate_root,
            module._read_state(aggregate_root / "state.json"),
            include_shards=True,
        )

        assert updated["completion_audit"]["reason"] == "external proof pending"
        assert updated["full_product_audit"]["reason"] == "desktop proof incomplete"
        assert updated["worker_lane_health"]["reason"] == "provider degraded"
        assert updated["flagship_product_readiness_path"] == "/tmp/flagship-two.json"
        assert updated["eta"]["scope_kind"] == "flagship_product_readiness"


def test_fast_status_state_surfaces_flagship_readiness_path_from_args() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        aggregate_root = Path(tmp) / "state" / "chummer_design_supervisor"
        aggregate_root.mkdir(parents=True, exist_ok=True)

        updated = module._fast_status_state(
            Namespace(flagship_product_readiness_path=str(Path(tmp) / "FLAGSHIP_PRODUCT_READINESS.generated.json")),
            aggregate_root,
            {},
            include_shards=False,
        )

        assert updated["flagship_product_readiness_path"] == str(
            (Path(tmp) / "FLAGSHIP_PRODUCT_READINESS.generated.json").resolve()
        )


def test_fast_status_state_includes_successor_wave_eta_from_published_queue() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_next_wave_registry(root)
        _write_next_wave_queue(
            root,
            [
                {
                    "repo": "chummer6-ui",
                    "package_id": "next90-101-ui",
                    "title": "Desktop release train",
                    "task": "Keep native-host release proof independent for the primary desktop head.",
                    "milestone_id": 101,
                },
                {
                    "repo": "chummer6-hub",
                    "package_id": "next90-102-hub",
                    "title": "Desktop-native trust flow",
                    "task": "Remove browser ritual from claim and support continuation.",
                    "milestone_id": 102,
                },
            ],
        )
        aggregate_root = root / "state" / "chummer_design_supervisor"
        aggregate_root.mkdir(parents=True, exist_ok=True)

        updated = module._fast_status_state(
            _args(root),
            aggregate_root,
            {},
            include_shards=True,
        )

        assert updated["successor_wave_eta"]["status"] == "tracked"
        assert updated["successor_wave_eta"]["remaining_open_milestones"] == 3
        assert updated["successor_wave_eta_human"]
        assert updated["successor_wave_eta_status"] == "tracked"


def test_fast_status_state_preserves_successor_wave_mode_when_all_shards_are_successors() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        aggregate_root = root / "state" / "chummer_design_supervisor"
        shard_one_root = aggregate_root / "shard-1"
        shard_two_root = aggregate_root / "shard-2"
        shard_one_root.mkdir(parents=True, exist_ok=True)
        shard_two_root.mkdir(parents=True, exist_ok=True)
        module._write_json(
            aggregate_root / "state.json",
            {
                "updated_at": "2026-04-15T08:00:00Z",
                "mode": "sharded",
                "eta": {
                    "status": "tracked",
                    "eta_human": "tracked",
                    "basis": "aggregate_shard_parallel_scope",
                    "scope_kind": "next_90_day_successor_wave",
                    "remaining_open_milestones": 2,
                    "remaining_in_progress_milestones": 2,
                    "remaining_not_started_milestones": 0,
                    "summary": "2 open milestones remain.",
                },
            },
        )
        for index, shard_root in enumerate((shard_one_root, shard_two_root), start=1):
            module._write_json(
                shard_root / "state.json",
                {
                    "updated_at": f"2026-04-15T08:0{index}:00Z",
                    "mode": "successor_wave",
                    "frontier_ids": [100 + index],
                    "open_milestone_ids": [100 + index],
                    "eta": {
                        "status": "tracked",
                        "eta_human": "8h-1d",
                        "basis": "successor_wave_frontier",
                        "scope_kind": "next_90_day_successor_wave",
                        "range_low_hours": 8.0,
                        "range_high_hours": 24.0,
                        "remaining_open_milestones": 1,
                        "remaining_in_progress_milestones": 1,
                        "remaining_not_started_milestones": 0,
                        "summary": "successor wave shard remains",
                    },
                    "active_run": {
                        "run_id": f"run-{index}",
                        "frontier_ids": [100 + index],
                        "open_milestone_ids": [100 + index],
                        "started_at": f"2026-04-15T08:0{index}:10Z",
                    },
                },
            )
        (aggregate_root / "active_shards.json").write_text(
            json.dumps(
                {
                    "active_shards": [
                        {"name": "shard-1", "frontier_ids": [101]},
                        {"name": "shard-2", "frontier_ids": [102]},
                    ]
                }
            ),
            encoding="utf-8",
        )

        updated = module._fast_status_state(
            _args(root),
            aggregate_root,
            module._read_state(aggregate_root / "state.json"),
            include_shards=True,
        )

        assert updated["mode"] == "successor_wave"
        assert updated["active_runs_count"] == 2
        assert {row["mode"] for row in updated["shards"]} == {"successor_wave"}


def test_status_json_requires_rich_refresh_when_fast_state_lacks_operator_fields() -> None:
    module = _load_module()

    assert (
        module._status_json_requires_rich_refresh(
            {
                "active_runs_count": 0,
                "shard_count": 14,
                "worker_lane_health": {},
                "completion_audit": {},
                "full_product_audit": {},
                "eta": {},
                "flagship_product_readiness_path": "",
            },
            include_shards=True,
        )
        is True
    )
    assert (
        module._status_json_requires_rich_refresh(
            {
                "active_runs_count": 14,
                "shard_count": 14,
                "worker_lane_health": {},
                "completion_audit": {},
                "full_product_audit": {},
                "eta": {},
                "flagship_product_readiness_path": "",
            },
            include_shards=True,
        )
        is False
    )
    assert (
        module._status_json_requires_rich_refresh(
            {
                "eta": {
                    "status": "tracked",
                }
            },
            include_shards=True,
        )
        is False
    )
    assert (
        module._status_json_requires_rich_refresh(
            {
                "worker_lane_health": {},
                "completion_audit": {},
            },
            include_shards=False,
        )
        is False
    )


def test_status_json_requires_rich_refresh_when_cached_full_product_audit_is_stale(tmp_path: Path) -> None:
    module = _load_module()
    readiness_path = tmp_path / "FLAGSHIP_PRODUCT_READINESS.generated.json"
    readiness_path.write_text(
        json.dumps({"generated_at": "2026-04-09T12:40:02Z", "status": "fail"}, indent=2) + "\n",
        encoding="utf-8",
    )

    assert (
        module._status_json_requires_rich_refresh(
            {
                "worker_lane_health": {"status": "pass"},
                "completion_audit": {"status": "fail"},
                "full_product_audit": {
                    "status": "fail",
                    "generated_at": "2026-04-09T12:36:13Z",
                },
                "eta": {"status": "tracked"},
                "flagship_product_readiness_path": str(readiness_path),
            },
            include_shards=True,
        )
        is True
    )


def test_render_status_and_trace_include_shard_metadata() -> None:
    module = _load_module()
    state = {
        "updated_at": "2026-03-31T10:05:00Z",
        "mode": "completion_review",
        "open_milestone_ids": [],
        "frontier_ids": [13, 14],
        "shards": [
            {
                "name": "shard-1",
                "updated_at": "2026-03-31T10:00:00Z",
                "mode": "completion_review",
                "open_milestone_ids": [],
                "frontier_ids": [13],
                "eta_status": "blocked",
                "last_run_id": "run-1",
                "active_run_id": "run-2",
            }
        ],
        "active_run": {
            "run_id": "run-2",
            "started_at": "2026-03-31T10:06:00Z",
            "selected_account_alias": "lane:core",
            "selected_model": "ea-coder-hard-batch",
            "attempt_index": 1,
            "total_attempts": 2,
            "primary_milestone_id": 13,
            "frontier_ids": [13],
            "last_message_path": "/tmp/run-2/last_message.txt",
        },
    }
    history = [
        {
            "run_id": "run-1",
            "_shard": "shard-1",
            "finished_at": "2026-03-31T10:00:00Z",
            "worker_exit_code": 0,
            "frontier_ids": [13],
            "selected_account_alias": "lane:core",
            "primary_milestone_id": 13,
            "accepted": False,
            "acceptance_reason": "Error: upstream_timeout:300s",
            "blocker": "",
            "shipped": "",
            "remains": "",
        }
    ]

    rendered_status = module._render_status(state)
    rendered_trace = module._render_trace(state, history)

    assert "shards: 1" in rendered_status
    assert "shard.shard-1:" in rendered_status
    assert "active_run.run_id: run-2" in rendered_status
    assert "active_run=run-2" in rendered_status
    assert "shard=shard-1" in rendered_trace
    assert "state=in_progress" in rendered_trace


def test_build_eta_snapshot_uses_empirical_burn_when_history_shows_open_count_closing() -> None:
    module = _load_module()
    open_milestones = [
        module.Milestone(6, "Build Lab progression planner", "W2", "in_progress", ["chummer6-ui"], ["Planner exists."], []),
        module.Milestone(21, "Rules Navigator v2", "W2", "not_started", ["chummer6-ui"], ["Rules differ."], [6]),
    ]
    history = [
        {
            "run_id": "run-1",
            "started_at": "2026-03-30T08:00:00Z",
            "finished_at": "2026-03-30T09:00:00Z",
            "worker_exit_code": 0,
            "accepted": True,
            "open_milestone_ids": [6, 15, 18, 19, 21],
        },
        {
            "run_id": "run-2",
            "started_at": "2026-03-30T15:00:00Z",
            "finished_at": "2026-03-30T16:00:00Z",
            "worker_exit_code": 0,
            "accepted": True,
            "open_milestone_ids": [6, 19, 21],
        },
    ]

    eta = module._build_eta_snapshot(
        mode="loop",
        open_milestones=open_milestones,
        frontier=open_milestones[:1],
        history=history,
        completion_audit=None,
        now=module._parse_iso("2026-03-30T20:00:00Z"),
    )

    assert eta["status"] == "estimated"
    assert eta["basis"] == "empirical_open_milestone_burn"
    assert eta["scope_kind"] == "open_milestone_frontier"
    assert "tactical frontier ETA only" in eta["scope_warning"]
    assert eta["eta_confidence"] in {"medium", "high"}
    assert eta["remaining_open_milestones"] == 2
    assert eta["observed_burn_milestones_per_day"] > 0


def test_build_eta_snapshot_reports_blocked_on_external_worker_failure() -> None:
    module = _load_module()
    open_milestones = [
        module.Milestone(6, "Build Lab progression planner", "W2", "in_progress", ["chummer6-ui"], ["Planner exists."], []),
    ]
    history = [
        {
            "run_id": "run-1",
            "finished_at": "2026-03-31T08:00:00Z",
            "worker_exit_code": 1,
            "accepted": False,
            "acceptance_reason": "worker exit 1",
            "blocker": "",
            "stderr_path": "",
        }
    ]

    eta = module._build_eta_snapshot(
        mode="loop",
        open_milestones=open_milestones,
        frontier=open_milestones,
        history=history,
        completion_audit={"reason": "worker lane hit usage limit and needs refreshed quota"},
        now=module._parse_iso("2026-03-31T09:00:00Z"),
    )

    assert eta["status"] == "blocked"
    assert eta["eta_human"].endswith("after unblock")
    assert eta["eta_confidence"] in {"low", "medium"}
    assert "external_blocker" in eta["basis"]
    assert "usage limit" in eta["blocking_reason"].lower()
    assert eta["range_high_hours"] > 0


def test_build_eta_snapshot_reports_blocked_when_provider_health_leaves_no_routable_direct_lanes() -> None:
    module = _load_module()
    open_milestones = [
        module.Milestone(6, "Build Lab progression planner", "W2", "in_progress", ["chummer6-ui"], ["Planner exists."], []),
    ]

    eta = module._build_eta_snapshot(
        mode="loop",
        open_milestones=open_milestones,
        frontier=open_milestones,
        history=[],
        completion_audit=None,
        worker_lane_health={
            "status": "pass",
            "routable_lanes": [],
            "unroutable_lanes": ["core", "core_rescue"],
            "lanes": {
                "core": {
                    "routable": False,
                    "reason": "onemin quota exhausted",
                },
                "core_rescue": {
                    "routable": False,
                    "reason": "onemin quota exhausted",
                },
            },
        },
        now=module._parse_iso("2026-03-31T09:00:00Z"),
    )

    assert eta["status"] == "blocked"
    assert eta["eta_human"].endswith("after unblock")
    assert "provider-health preflight left no routable direct lanes" in eta["blocking_reason"]


def test_derive_eta_returns_completion_review_recovery_when_registry_is_closed_but_gate_is_stale() -> None:
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
                            "title": "Linux desktop hard gate",
                            "wave": "W1",
                            "status": "complete",
                            "owners": ["chummer6-ui", "fleet"],
                            "exit_criteria": ["Done."],
                            "dependencies": [],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        _write_completion_evidence(
            root,
            linux_desktop_exit_gate_generated_at="2026-03-28T00:00:00Z",
        )
        state_root = root / "state"
        state_root.mkdir(parents=True, exist_ok=True)
        (state_root / "history.jsonl").write_text(
            json.dumps(
                {
                    "run_id": "run-eta-1",
                    "started_at": "2026-03-31T07:00:00Z",
                    "finished_at": "2026-03-31T08:00:00Z",
                    "worker_exit_code": 0,
                    "accepted": True,
                    "acceptance_reason": "",
                    "primary_milestone_id": 13,
                    "frontier_ids": [13],
                    "open_milestone_ids": [13],
                    "shipped": "desktop receipt",
                    "remains": "none",
                    "blocker": "none",
                }
            )
            + "\n",
            encoding="utf-8",
        )

        eta = module.derive_eta(_args(root))

        assert eta["status"] == "recovery"
        assert eta["basis"] == "completion_review_recovery"
        assert eta["scope_kind"] == "completion_review_recovery"
        assert "Linux desktop exit gate" in eta["summary"]


def test_estimate_completion_review_eta_uses_decomposed_frontier_breakdown() -> None:
    module = _load_module()
    frontier = [
        module.Milestone(
            id=1394756221,
            title="Repo backlog: ui-kit: Seed Chummer.Ui.Kit with token canon, theme compilation, and preview/gallery ownership.",
            wave="completion_review",
            status="review_required",
            owners=["chummer6-ui-kit"],
            exit_criteria=["Seed token canon and preview/gallery ownership."],
            dependencies=[],
        ),
        module.Milestone(
            id=1873346391,
            title="Repo backlog: ui: Publish and execute the ruleset-specific workbench adaptation lane.",
            wave="completion_review",
            status="review_required",
            owners=["chummer6-ui"],
            exit_criteria=["Make SR4/SR5/SR6 posture explicit in the workbench."],
            dependencies=[],
        ),
    ]
    audit = {
        "status": "fail",
        "receipt_audit": {
            "status": "fail",
            "reason": "latest worker receipt is not trusted",
        },
        "repo_backlog_audit": {
            "status": "fail",
            "open_item_count": 3,
            "open_items": [
                {"project_id": "ui-kit", "repo_slug": "chummer6-ui-kit", "task": "Seed token canon"},
                {"project_id": "ui", "repo_slug": "chummer6-ui", "task": "Ruleset-specific workbench adaptation"},
                {"project_id": "hub-registry", "repo_slug": "chummer6-hub-registry", "task": "Wire registry package boundaries"},
            ],
        },
    }

    eta = module._estimate_completion_review_eta(
        frontier,
        audit,
        history=[],
        now=module._parse_iso("2026-03-31T09:00:00Z"),
    )

    assert eta["status"] == "recovery"
    assert eta["basis"] == "completion_review_recovery"
    assert eta["remaining_effort_units"] > 3.0
    assert "decomposed_frontier=2" in eta["summary"]
    assert "backlog_tail=1" in eta["summary"]
    components = [row["component"] for row in eta["remaining_effort_breakdown"]]
    assert components.count("repo_backlog_milestone") == 2
    assert "repo_backlog_tail" in components


def test_derive_eta_keeps_recovery_estimate_when_completion_review_is_blocked_by_upstream_timeout() -> None:
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
                            "title": "Linux desktop hard gate",
                            "wave": "W1",
                            "status": "complete",
                            "owners": ["chummer6-ui", "fleet"],
                            "exit_criteria": ["Done."],
                            "dependencies": [],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        _write_completion_evidence(root, linux_desktop_exit_gate_generated_at="2026-03-28T00:00:00Z")
        state_root = root / "state"
        state_root.mkdir(parents=True, exist_ok=True)
        (state_root / "history.jsonl").write_text(
            "\n".join(
                [
                    json.dumps(
                        {
                            "run_id": "run-good",
                            "started_at": "2026-03-31T06:00:00Z",
                            "finished_at": "2026-03-31T07:00:00Z",
                            "worker_exit_code": 0,
                            "accepted": True,
                            "acceptance_reason": "",
                            "primary_milestone_id": 13,
                            "frontier_ids": [13],
                            "open_milestone_ids": [13],
                            "shipped": "desktop receipt",
                            "remains": "none",
                            "blocker": "none",
                        }
                    ),
                    json.dumps(
                        {
                            "run_id": "run-bad",
                            "started_at": "2026-03-31T07:00:00Z",
                            "finished_at": "2026-03-31T08:00:00Z",
                            "worker_exit_code": 0,
                            "accepted": False,
                            "acceptance_reason": "Error: upstream_timeout:300s",
                            "primary_milestone_id": 13,
                            "frontier_ids": [13],
                            "open_milestone_ids": [],
                            "shipped": "",
                            "remains": "",
                            "blocker": "",
                        }
                    ),
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        eta = module.derive_eta(_args(root))

        assert eta["status"] == "blocked"
        assert eta["eta_human"].endswith("after unblock")
        assert eta["range_high_hours"] > 0
        assert "completion_review_recovery" in eta["basis"]
        assert "upstream_timeout" in eta["blocking_reason"]


def test_derive_eta_reads_blocker_from_shard_history() -> None:
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
                            "title": "Linux desktop hard gate",
                            "wave": "W1",
                            "status": "complete",
                            "owners": ["chummer6-ui", "fleet"],
                            "exit_criteria": ["Done."],
                            "dependencies": [],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        _write_completion_evidence(root, linux_desktop_exit_gate_generated_at="2026-03-28T00:00:00Z")
        shard_root = root / "state" / "shard-1"
        shard_root.mkdir(parents=True, exist_ok=True)
        (shard_root / "history.jsonl").write_text(
            json.dumps(
                {
                    "run_id": "run-bad",
                    "started_at": "2026-03-31T07:00:00Z",
                    "finished_at": "2026-03-31T08:00:00Z",
                    "worker_exit_code": 0,
                    "accepted": False,
                    "acceptance_reason": "Error: upstream_timeout:300s",
                    "primary_milestone_id": 13,
                    "frontier_ids": [13],
                    "open_milestone_ids": [],
                    "shipped": "",
                    "remains": "",
                    "blocker": "",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        module._write_json(
            shard_root / "state.json",
            {
                "updated_at": "2026-03-31T08:00:00Z",
                "mode": "completion_review",
                "open_milestone_ids": [],
                "frontier_ids": [13],
                "last_run": {"run_id": "run-bad", "finished_at": "2026-03-31T08:00:00Z"},
            },
        )

        eta = module.derive_eta(_args(root))

        assert eta["status"] == "blocked"
        assert eta["eta_human"].endswith("after unblock")
        assert "upstream_timeout" in eta["blocking_reason"]


def test_estimate_open_milestone_eta_ignores_non_wave_accepted_history() -> None:
    module = _load_module()
    now = dt.datetime(2026, 4, 3, 16, 0, tzinfo=dt.timezone.utc)
    open_milestones = [
        module.Milestone(
            id=1,
            title="Gold install lane",
            wave="W1",
            status="planned",
            owners=["fleet"],
            exit_criteria=["Install lane is real."],
            dependencies=[],
        )
    ]
    history = [
        {
            "accepted": True,
            "started_at": "2026-04-03T15:00:00Z",
            "finished_at": "2026-04-03T15:06:00Z",
            "open_milestone_ids": [],
        }
    ]

    eta = module._estimate_open_milestone_eta(open_milestones, history, now)

    assert eta["basis"] == "heuristic_status_mix"


def test_estimate_open_milestone_eta_requires_scope_coverage_for_widened_empirical_burn() -> None:
    module = _load_module()
    now = dt.datetime(2026, 4, 4, 16, 0, tzinfo=dt.timezone.utc)
    open_milestones = [
        module.Milestone(
            id=index,
            title=f"Milestone {index}",
            wave="W1",
            status="planned",
            owners=["fleet"],
            exit_criteria=["Done."],
            dependencies=[],
        )
        for index in range(1, 19)
    ]
    history = [
        {
            "accepted": True,
            "started_at": "2026-04-04T14:00:00Z",
            "finished_at": "2026-04-04T14:30:00Z",
            "open_milestone_ids": [13, 14, 17, 18],
        },
        {
            "accepted": True,
            "started_at": "2026-04-04T14:30:00Z",
            "finished_at": "2026-04-04T15:00:00Z",
            "open_milestone_ids": [13, 17, 18],
        },
        {
            "accepted": True,
            "started_at": "2026-04-04T15:00:00Z",
            "finished_at": "2026-04-04T15:30:00Z",
            "open_milestone_ids": [13, 18],
        },
    ]

    eta = module._estimate_open_milestone_eta(open_milestones, history, now)

    assert eta["basis"] == "heuristic_status_mix"
    assert eta["eta_confidence"] == "low"


def test_estimate_open_milestone_eta_rejects_shard_local_snapshot_scale_for_aggregate_wave() -> None:
    module = _load_module()
    now = dt.datetime(2026, 4, 4, 16, 0, tzinfo=dt.timezone.utc)
    open_milestones = [
        module.Milestone(
            id=index,
            title=f"Milestone {index}",
            wave="W1",
            status="planned",
            owners=["fleet"],
            exit_criteria=["Done."],
            dependencies=[],
        )
        for index in range(1, 19)
    ]
    history = [
        {
            "accepted": True,
            "started_at": "2026-04-04T14:00:00Z",
            "finished_at": "2026-04-04T14:30:00Z",
            "open_milestone_ids": [1, 2, 3, 4],
        },
        {
            "accepted": True,
            "started_at": "2026-04-04T14:30:00Z",
            "finished_at": "2026-04-04T15:00:00Z",
            "open_milestone_ids": [5, 6, 7, 8],
        },
        {
            "accepted": True,
            "started_at": "2026-04-04T15:00:00Z",
            "finished_at": "2026-04-04T15:30:00Z",
            "open_milestone_ids": [9, 10, 11, 12],
        },
        {
            "accepted": True,
            "started_at": "2026-04-04T15:30:00Z",
            "finished_at": "2026-04-04T15:45:00Z",
            "open_milestone_ids": [13, 14, 15],
        },
        {
            "accepted": True,
            "started_at": "2026-04-04T15:45:00Z",
            "finished_at": "2026-04-04T15:55:00Z",
            "open_milestone_ids": [16, 17],
        },
    ]

    eta = module._estimate_open_milestone_eta(open_milestones, history, now)

    assert eta["basis"] == "heuristic_status_mix"
    assert eta["eta_confidence"] == "low"


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


def test_effective_supervisor_state_prefers_active_run_frontier_ids() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        aggregate_root = root / "state"
        shard_root = aggregate_root / "shard-1"
        shard_root.mkdir(parents=True, exist_ok=True)
        module._write_json(
            shard_root / "state.json",
            {
                "updated_at": "2026-03-31T17:22:15Z",
                "mode": "completion_review",
                "frontier_ids": [13],
                "open_milestone_ids": [],
                "active_run": {
                    "run_id": "run-1",
                    "frontier_ids": [21, 22],
                    "open_milestone_ids": [],
                },
            },
        )

        state, _history = module._effective_supervisor_state(aggregate_root, history_limit=10)

        assert state["frontier_ids"] == [21, 22]
        assert state["shards"][0]["frontier_ids"] == [21, 22]


def test_effective_supervisor_state_ignores_stale_base_active_run_when_shards_are_idle() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        aggregate_root = root / "state"
        shard_root = aggregate_root / "shard-1"
        shard_root.mkdir(parents=True, exist_ok=True)
        module._write_json(
            aggregate_root / "state.json",
            {
                "updated_at": "2026-03-31T17:30:00Z",
                "mode": "complete",
                "frontier_ids": [],
                "active_run": {
                    "run_id": "stale-run",
                    "frontier_ids": [99],
                },
            },
        )
        module._write_json(
            shard_root / "state.json",
            {
                "updated_at": "2026-03-31T17:35:00Z",
                "mode": "complete",
                "frontier_ids": [],
                "open_milestone_ids": [],
            },
        )

        state, _history = module._effective_supervisor_state(aggregate_root, history_limit=10)

        assert "active_run" not in state
        assert state["frontier_ids"] == []
        assert state["shards"][0]["active_run_id"] == ""


def test_effective_supervisor_state_ignores_stale_shard_active_run_when_complete_without_work() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        aggregate_root = root / "state"
        shard_root = aggregate_root / "shard-1"
        shard_root.mkdir(parents=True, exist_ok=True)
        module._write_json(
            shard_root / "state.json",
            {
                "updated_at": "2026-03-31T17:35:00Z",
                "mode": "complete",
                "frontier_ids": [],
                "open_milestone_ids": [],
                "active_run": {
                    "run_id": "stale-shard-run",
                    "frontier_ids": [],
                    "open_milestone_ids": [],
                },
            },
        )

        state, _history = module._effective_supervisor_state(aggregate_root, history_limit=10)

        assert "active_run" not in state
        assert state["frontier_ids"] == []
        assert state["shards"][0]["active_run_id"] == "stale-shard-run"


def test_live_shard_summaries_prefer_active_run_frontier_ids() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "registry.yaml").write_text("waves: []\nmilestones: []\n", encoding="utf-8")
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("Everything is done.\n", encoding="utf-8")
        _write_completion_evidence(root)
        aggregate_root = root / "state"
        shard_root = aggregate_root / "shard-1"
        shard_root.mkdir(parents=True, exist_ok=True)
        module._write_json(
            shard_root / "state.json",
            {
                "updated_at": "2026-03-31T17:22:15Z",
                "mode": "completion_review",
                "frontier_ids": [13],
                "focus_owners": ["chummer6-ui"],
                "focus_texts": ["desktop"],
                "open_milestone_ids": [],
                "active_run": {
                    "run_id": "run-1",
                    "frontier_ids": [21, 22],
                    "open_milestone_ids": [],
                },
            },
        )
        args = _args(root)

        summaries = module._live_shard_summaries(args, aggregate_root)

        assert summaries[0]["frontier_ids"] != [21, 22]
        assert summaries[0]["active_frontier_ids"] == []
        assert summaries[0]["active_run_id"] == ""


def test_live_shard_summaries_persist_refreshed_shard_state() -> None:
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
        _write_completion_evidence(root)
        aggregate_root = root / "state"
        shard_root = aggregate_root / "shard-1"
        shard_root.mkdir(parents=True, exist_ok=True)
        module._write_json(
            shard_root / "state.json",
            {
                "updated_at": "2026-03-31T08:00:00Z",
                "mode": "completion_review",
                "frontier_ids": [13],
                "focus_owners": ["chummer6-ui", "fleet"],
                "focus_texts": ["desktop", "client"],
                "completion_audit": {"status": "fail", "reason": "stale"},
                "eta": {"status": "blocked", "eta_human": "unknown"},
                "last_run": {
                    "run_id": "run-9",
                    "worker_exit_code": 0,
                    "accepted": True,
                    "acceptance_reason": "",
                    "primary_milestone_id": 13,
                    "frontier_ids": [13],
                    "shipped": "trusted receipt",
                    "remains": "none",
                    "blocker": "none",
                },
            },
        )
        module._append_jsonl(
            shard_root / "history.jsonl",
            {
                "run_id": "run-9",
                "worker_exit_code": 0,
                "accepted": True,
                "acceptance_reason": "",
                "primary_milestone_id": 13,
                "frontier_ids": [13],
                "shipped": "trusted receipt",
                "remains": "none",
                "blocker": "none",
            },
        )

        summaries = module._live_shard_summaries(_args(root), aggregate_root)
        persisted = json.loads((shard_root / "state.json").read_text(encoding="utf-8"))

        assert summaries[0]["mode"] == "flagship_product"
        assert persisted["mode"] == "flagship_product"
        assert persisted["frontier_ids"] == summaries[0]["frontier_ids"]


def test_live_shard_summaries_return_persisted_active_run_detail_fields(monkeypatch) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        aggregate_root = root / "state"
        shard_root = aggregate_root / "shard-1"
        shard_root.mkdir(parents=True, exist_ok=True)
        module._write_json(
            shard_root / "state.json",
            {
                "updated_at": "2026-04-13T12:20:00Z",
                "mode": "loop",
                "frontier_ids": [13],
                "open_milestone_ids": [13],
                "focus_owners": ["fleet"],
            },
        )

        def fake_live_state(*_args, **_kwargs):
            return (
                {
                    "updated_at": "2026-04-13T12:21:00Z",
                    "mode": "loop",
                    "frontier_ids": [13],
                    "open_milestone_ids": [13],
                    "focus_owners": ["fleet"],
                    "active_run": {
                        "run_id": "run-live-detail",
                        "frontier_ids": [13],
                        "open_milestone_ids": [13],
                        "started_at": "2026-04-13T12:20:05Z",
                        "worker_first_output_at": "2026-04-13T12:20:06Z",
                        "worker_last_output_at": "2026-04-13T12:20:30Z",
                        "selected_account_alias": "acct-ea-core-01",
                        "selected_model": "ea-coder-hard",
                    },
                },
                [],
            )

        monkeypatch.setattr(module, "_live_state_with_current_completion_audit", fake_live_state)

        summaries = module._live_shard_summaries(_args(root), aggregate_root)

        assert len(summaries) == 1
        shard = summaries[0]
        assert shard["active_run_id"] == "run-live-detail"
        assert shard["active_run_worker_last_output_at"] == "2026-04-13T12:20:30Z"
        assert shard["active_run_progress_state"] == "streaming"
        assert shard["selected_account_alias"] == "acct-ea-core-01"
        assert shard["selected_model"] == "ea-coder-hard"


def test_live_shard_summaries_apply_runtime_focus_profiles(monkeypatch) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "registry.yaml").write_text(
            yaml.safe_dump(
                {
                    "waves": [{"id": "W1"}],
                    "milestones": [
                        {
                            "id": 1,
                            "title": "Install lane",
                            "wave": "W1",
                            "status": "planned",
                            "owners": ["fleet", "chummer6-ui"],
                            "exit_criteria": ["Install lane ships."],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("Continue flagship closure.\n", encoding="utf-8")
        _write_completion_evidence(root)
        aggregate_root = root / "state"
        shard_root = aggregate_root / "shard-1"
        shard_root.mkdir(parents=True, exist_ok=True)
        module._write_json(
            shard_root / "state.json",
            {
                "updated_at": "2026-03-31T08:00:00Z",
                "mode": "loop",
                "frontier_ids": [],
                "open_milestone_ids": [1],
            },
        )

        monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_STATE_ROOT", str(aggregate_root))
        monkeypatch.setenv(
            "CHUMMER_DESIGN_SUPERVISOR_FOCUS_PROFILE",
            "top_flagship_grade,whole_project_frontier",
        )

        module._live_shard_summaries(_args(root), aggregate_root)
        persisted = json.loads((shard_root / "state.json").read_text(encoding="utf-8"))

        assert persisted["focus_profiles"] == ["top_flagship_grade", "whole_project_frontier"]


def test_live_state_with_current_completion_audit_keeps_shard_focus_profiles(monkeypatch) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "registry.yaml").write_text("waves: []\nmilestones: []\n", encoding="utf-8")
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("Continue flagship closure.\n", encoding="utf-8")
        _write_completion_evidence(root)
        aggregate_root = root / "state"
        shard_root = aggregate_root / "shard-1"
        shard_root.mkdir(parents=True, exist_ok=True)
        module._write_json(
            shard_root / "state.json",
            {
                "updated_at": "2026-04-05T05:00:00Z",
                "mode": "completion_review",
                "focus_profiles": ["top_flagship_grade", "whole_project_frontier"],
                "focus_owners": ["fleet"],
                "focus_texts": ["operator"],
                "completion_audit": {"status": "fail", "reason": "external only"},
                "full_product_audit": {"status": "fail", "reason": "external only"},
            },
        )
        args = _args(root)
        args.state_root = str(aggregate_root)

        state, history = module._effective_supervisor_state(aggregate_root, history_limit=module.ETA_HISTORY_LIMIT)
        updated, _ = module._live_state_with_current_completion_audit(
            args,
            aggregate_root,
            state,
            history,
            include_shards=True,
            refresh_flagship_readiness=False,
        )

        assert updated["focus_profiles"] == ["top_flagship_grade", "whole_project_frontier"]


def test_live_shard_summaries_refresh_each_shard_with_its_own_configured_frontier_pack(
    monkeypatch,
) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "registry.yaml").write_text(
            yaml.safe_dump(
                {
                    "waves": [{"id": "W1"}, {"id": "W2"}],
                    "milestones": [
                        {
                            "id": 1,
                            "title": "Install lane",
                            "wave": "W1",
                            "status": "planned",
                            "owners": ["chummer6-ui"],
                            "exit_criteria": ["Install lane exists."],
                        },
                        {
                            "id": 2,
                            "title": "Legacy workbench",
                            "wave": "W1",
                            "status": "planned",
                            "owners": ["chummer6-ui"],
                            "exit_criteria": ["Workbench exists."],
                        },
                        {
                            "id": 13,
                            "title": "Sourcebook parity",
                            "wave": "W2",
                            "status": "planned",
                            "owners": ["chummer6-core"],
                            "exit_criteria": ["Sourcebooks exist."],
                        },
                        {
                            "id": 14,
                            "title": "Settings parity",
                            "wave": "W2",
                            "status": "planned",
                            "owners": ["chummer6-core"],
                            "exit_criteria": ["Settings exist."],
                        },
                    ],
                }
            ),
            encoding="utf-8",
        )
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("Continue the work.\n", encoding="utf-8")
        aggregate_root = root / "state"
        shard_1 = aggregate_root / "shard-1"
        shard_2 = aggregate_root / "shard-2"
        shard_1.mkdir(parents=True, exist_ok=True)
        shard_2.mkdir(parents=True, exist_ok=True)
        for shard_root in (shard_1, shard_2):
            module._write_json(
                shard_root / "state.json",
                {
                    "updated_at": "2026-03-31T08:00:00Z",
                    "mode": "loop",
                    "open_milestone_ids": [1, 2, 13, 14],
                    "frontier_ids": [99],
                    "focus_owners": ["stale-owner"],
                },
            )

        monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_SHARD_FRONTIER_ID_GROUPS", "1,2;13,14")
        monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_SHARD_OWNER_GROUPS", "chummer6-ui;chummer6-core")

        summaries = module._live_shard_summaries(_args(root), aggregate_root)
        persisted_1 = json.loads((shard_1 / "state.json").read_text(encoding="utf-8"))
        persisted_2 = json.loads((shard_2 / "state.json").read_text(encoding="utf-8"))

        assert summaries[0]["frontier_ids"] == [1, 2]
        assert summaries[1]["frontier_ids"] == [13, 14]
        assert persisted_1["frontier_ids"] == [1, 2]
        assert persisted_2["frontier_ids"] == [13, 14]


def test_live_shard_summaries_ignore_stale_dirs_not_in_manifest(monkeypatch) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "registry.yaml").write_text("waves: []\nmilestones: []\n", encoding="utf-8")
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("Continue the work.\n", encoding="utf-8")
        aggregate_root = root / "state"
        active_root = aggregate_root / "shard-1"
        stale_root = aggregate_root / "shard-9"
        active_root.mkdir(parents=True, exist_ok=True)
        stale_root.mkdir(parents=True, exist_ok=True)
        module._write_json(
            active_root / "state.json",
            {
                "updated_at": "2026-03-31T08:00:00Z",
                "mode": "loop",
                "open_milestone_ids": [1, 2, 3],
                "frontier_ids": [1, 2, 3],
            },
        )
        module._write_json(
            stale_root / "state.json",
            {
                "updated_at": "2026-03-31T08:00:01Z",
                "mode": "loop",
                "open_milestone_ids": [99],
                "frontier_ids": [99],
            },
        )
        (aggregate_root / "active_shards.json").write_text(
            json.dumps({"active_shards": [{"name": "shard-1", "index": 1, "frontier_ids": [1, 2, 3]}]}),
            encoding="utf-8",
        )
        monkeypatch.setattr(
            module,
            "_live_state_with_current_completion_audit",
            lambda args, state_root, state, history, **kwargs: (module._read_state(state_root / "state.json"), history),
        )

        summaries = module._live_shard_summaries(_args(root), aggregate_root)

        assert [item["name"] for item in summaries] == ["shard-1"]


def test_live_shard_summaries_prefer_structured_manifest_over_env_group_defaults(
    monkeypatch,
) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "registry.yaml").write_text(
            yaml.safe_dump(
                {
                    "waves": [{"id": "W1"}, {"id": "W2"}],
                    "milestones": [
                        {
                            "id": 1,
                            "title": "Install lane",
                            "wave": "W1",
                            "status": "planned",
                            "owners": ["chummer6-ui"],
                            "exit_criteria": ["Install lane exists."],
                        },
                        {
                            "id": 13,
                            "title": "Sourcebook parity",
                            "wave": "W2",
                            "status": "planned",
                            "owners": ["chummer6-core"],
                            "exit_criteria": ["Sourcebooks exist."],
                        },
                    ],
                }
            ),
            encoding="utf-8",
        )
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("Continue the work.\n", encoding="utf-8")
        aggregate_root = root / "state"
        shard_root = aggregate_root / "shard-1"
        shard_root.mkdir(parents=True, exist_ok=True)
        module._write_json(
            shard_root / "state.json",
            {
                "updated_at": "2026-03-31T08:00:00Z",
                "mode": "loop",
                "open_milestone_ids": [1, 13],
                "frontier_ids": [],
            },
        )
        (aggregate_root / "active_shards.json").write_text(
            json.dumps(
                {
                    "generated_at": "2026-04-04T15:20:00Z",
                    "topology_fingerprint": "abc123",
                    "active_shards": [
                        {
                            "name": "shard-1",
                            "index": 1,
                            "frontier_ids": [13],
                            "focus_owner": ["chummer6-core"],
                            "focus_text": ["sourcebook"],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

        monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_SHARD_FRONTIER_ID_GROUPS", "1")
        monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_SHARD_OWNER_GROUPS", "chummer6-ui")
        monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_SHARD_FOCUS_TEXT_GROUPS", "install")

        summaries = module._live_shard_summaries(_args(root), aggregate_root)
        persisted = json.loads((shard_root / "state.json").read_text(encoding="utf-8"))

        assert summaries[0]["frontier_ids"] == [13]
        assert persisted["frontier_ids"] == [13]
        assert persisted["focus_owners"] == ["chummer6-core"]
        assert persisted["focus_texts"] == ["sourcebook"]


def test_live_state_with_current_completion_audit_aggregates_union_of_shard_frontier_packs(
    monkeypatch,
) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "registry.yaml").write_text(
            yaml.safe_dump(
                {
                    "waves": [{"id": "W1"}, {"id": "W2"}],
                    "milestones": [
                        {
                            "id": 1,
                            "title": "Install lane",
                            "wave": "W1",
                            "status": "planned",
                            "owners": ["chummer6-ui"],
                            "exit_criteria": ["Install lane exists."],
                        },
                        {
                            "id": 2,
                            "title": "Workbench lane",
                            "wave": "W1",
                            "status": "planned",
                            "owners": ["chummer6-ui"],
                            "exit_criteria": ["Workbench exists."],
                        },
                        {
                            "id": 13,
                            "title": "Sourcebook parity",
                            "wave": "W2",
                            "status": "planned",
                            "owners": ["chummer6-core"],
                            "exit_criteria": ["Sourcebooks exist."],
                        },
                        {
                            "id": 14,
                            "title": "Settings parity",
                            "wave": "W2",
                            "status": "planned",
                            "owners": ["chummer6-core"],
                            "exit_criteria": ["Settings exist."],
                        },
                    ],
                }
            ),
            encoding="utf-8",
        )
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("Continue the work.\n", encoding="utf-8")
        aggregate_root = root / "state"
        for shard_root in (aggregate_root / "shard-1", aggregate_root / "shard-2"):
            shard_root.mkdir(parents=True, exist_ok=True)
            module._write_json(
                shard_root / "state.json",
                {
                    "updated_at": "2026-03-31T08:00:00Z",
                    "mode": "loop",
                    "open_milestone_ids": [1, 2, 13, 14],
                    "frontier_ids": [],
                },
            )

        monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_PARALLEL_SHARDS", "2")
        monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_SHARD_FRONTIER_ID_GROUPS", "1,2;13,14")
        monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_SHARD_OWNER_GROUPS", "chummer6-ui;chummer6-core")

        state, history = module._effective_supervisor_state(aggregate_root, history_limit=10)
        updated_state, _ = module._live_state_with_current_completion_audit(
            _args(root),
            aggregate_root,
            state,
            history,
        )

        assert updated_state["frontier_ids"] == [1, 2, 13, 14]
        assert len(updated_state["shards"]) == 2
        assert updated_state["shards"][0]["frontier_ids"] == [1, 2]
        assert updated_state["shards"][1]["frontier_ids"] == [13, 14]


def test_persist_live_state_snapshot_keeps_shard_count_but_strips_heavy_aggregate_fields() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        state_root = Path(tmp)
        module._persist_live_state_snapshot(
            state_root,
            {
                "updated_at": "2026-04-01T09:00:00Z",
                "mode": "flagship_product",
                "frontier_ids": [1, 2, 3],
                "state_root": "/tmp/aggregate",
                "shard_count": 3,
                "shards": [{"name": "shard-1"}],
            },
        )

        persisted = json.loads((state_root / "state.json").read_text(encoding="utf-8"))

        assert persisted["mode"] == "flagship_product"
        assert persisted["frontier_ids"] == [1, 2, 3]
        assert persisted["shard_count"] == 3
        assert "state_root" not in persisted
        assert "shards" not in persisted


def test_persist_live_state_snapshot_refreshes_status_live_refresh_for_shards(monkeypatch) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        aggregate_root = Path(tmp) / "state" / "chummer_design_supervisor"
        shard_root = aggregate_root / "shard-1"
        shard_root.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(module, "_running_inside_container", lambda: True)
        monkeypatch.setattr(module, "_write_active_shard_manifest_snapshot", lambda state_root: None)
        monkeypatch.setattr(
            module,
            "_statefile_shard_summaries",
            lambda state_root: [
                {
                    "name": "shard-1",
                    "shard_id": "shard-1",
                    "active_run_id": "run-123",
                    "active_frontier_ids": [4066417069],
                    "open_milestone_ids": [4066417069],
                    "active_run_progress_state": "streaming",
                    "active_run_started_at": "2026-04-17T05:00:00Z",
                    "selected_account_alias": "acct-ea-core-06",
                    "selected_model": "ea-coder-hard-batch",
                    "active_run_worker_pid": 1234,
                    "active_run_worker_first_output_at": "2026-04-17T05:03:00Z",
                    "active_run_worker_last_output_at": "2026-04-17T05:03:10Z",
                    "active_run_output_updated_at": "2026-04-17T05:03:10Z",
                    "active_run_output_sizes": {"stderr": 12},
                    "active_run_process_alive": True,
                    "active_run_process_state": "S",
                    "active_run_process_cpu_seconds": 0.1,
                }
            ],
        )

        module._persist_live_state_snapshot(
            shard_root,
            {
                "updated_at": "2026-04-17T05:03:10Z",
                "mode": "flagship_product",
                "frontier_ids": [4066417069],
                "open_milestone_ids": [4066417069],
                "active_run": {"run_id": "run-123"},
            },
        )

        payload = json.loads((aggregate_root / "status-live-refresh.json").read_text(encoding="utf-8"))
        assert payload["contract_name"] == "fleet.chummer_design_supervisor.status_live_refresh"
        assert payload["configured_shard_count"] == 1
        assert payload["active_run_count"] == 1
        assert payload["active_runs"][0]["_shard"] == "shard-1"
        assert payload["active_runs"][0]["run_id"] == "run-123"
        assert payload["active_runs"][0]["progress_state"] == "streaming"


def test_refresh_aggregate_runtime_state_snapshot_updates_runtime_fields(monkeypatch) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        aggregate_root = Path(tmp) / "state" / "chummer_design_supervisor"
        aggregate_root.mkdir(parents=True, exist_ok=True)
        (aggregate_root / "shard-1").mkdir(parents=True, exist_ok=True)
        module._write_json(
            aggregate_root / "state.json",
            {
                "updated_at": "2026-04-15T11:28:36Z",
                "mode": "sharded",
                "model_selection": {"generated_at": "stale"},
                "worker_lane_health": {"status": "stale"},
            },
        )
        monkeypatch.setattr(
            module,
            "_model_selection_snapshot",
            lambda args, state_root, worker_lane_health=None: {
                "generated_at": "fresh-model-selection",
                "openai_escape": {"status": "blocked"},
            },
        )
        monkeypatch.setattr(
            module,
            "_direct_worker_lane_health_snapshot",
            lambda args, lanes: {"status": "pass", "reason": "fresh-lane-health"},
        )
        monkeypatch.setattr(
            module,
            "_memory_dispatch_snapshot",
            lambda args, state_root: {"status": "pass", "reason": "fresh-memory"},
        )
        monkeypatch.setattr(
            module,
            "_statefile_shard_summaries",
            lambda state_root: [
                {
                    "name": "shard-1",
                    "active_run_id": "run-1",
                    "mode": "successor_wave",
                    "frontier_ids": [101],
                    "open_milestone_ids": [101],
                }
            ],
        )
        monkeypatch.setattr(
            module,
            "_successor_wave_eta_snapshot",
            lambda workspace_root: {"status": "successor_wave", "eta_human": "1d"},
        )

        module._refresh_aggregate_runtime_state_snapshot(aggregate_root)

        refreshed = json.loads((aggregate_root / "state.json").read_text(encoding="utf-8"))

        assert refreshed["model_selection"]["generated_at"] == "fresh-model-selection"
        assert refreshed["worker_lane_health"]["reason"] == "fresh-lane-health"
        assert refreshed["host_memory_pressure"]["reason"] == "fresh-memory"
        assert refreshed["shard_count"] == 1
        assert refreshed["active_runs_count"] == 1
        assert refreshed["successor_wave_eta"]["eta_human"] == "1d"


def test_write_state_preserves_matching_active_run_from_existing_state() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        state_root = Path(tmp)
        active_run = {
            "run_id": "run-1",
            "frontier_ids": [13],
            "open_milestone_ids": [13],
            "last_message_path": "",
        }
        (state_root / "state.json").write_text(json.dumps({"active_run": active_run}), encoding="utf-8")

        frontier_item = Namespace(id=13)
        module._write_state(
            state_root,
            mode="flagship_product",
            run=None,
            open_milestones=[frontier_item],
            frontier=[frontier_item],
        )

        persisted = json.loads((state_root / "state.json").read_text(encoding="utf-8"))

        assert persisted["mode"] == "flagship_product"
        assert persisted["active_run"]["run_id"] == "run-1"


def test_write_state_uses_frontier_ids_as_open_milestone_ids_for_flagship_slice() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        state_root = Path(tmp)

        frontier_item = Namespace(id=13)
        module._write_state(
            state_root,
            mode="flagship_product",
            run=None,
            open_milestones=[],
            frontier=[frontier_item],
        )

        persisted = json.loads((state_root / "state.json").read_text(encoding="utf-8"))

        assert persisted["mode"] == "flagship_product"
        assert persisted["frontier_ids"] == [13]
        assert persisted["open_milestone_ids"] == [13]


def test_apply_status_alias_fields_restores_open_milestone_ids_from_active_run_for_flagship_slice() -> None:
    module = _load_module()

    updated = module._apply_status_alias_fields(
        {
            "mode": "flagship_product",
            "frontier_ids": [21],
            "open_milestone_ids": [],
            "active_run": {
                "run_id": "run-21",
                "frontier_ids": [21],
                "open_milestone_ids": [21],
                "progress_state": "streaming",
            },
        }
    )

    assert updated["active_run_id"] == "run-21"
    assert updated["frontier_ids"] == [21]
    assert updated["open_milestone_ids"] == [21]


def test_apply_status_alias_fields_prefers_active_run_frontier_ids_for_flagship_slice_when_state_drifts() -> None:
    module = _load_module()

    updated = module._apply_status_alias_fields(
        {
            "mode": "flagship_product",
            "frontier_ids": [4575045159],
            "open_milestone_ids": [4575045159],
            "active_run": {
                "run_id": "run-3109832007",
                "frontier_ids": [3109832007],
                "open_milestone_ids": [3109832007],
                "progress_state": "streaming",
            },
        }
    )

    assert updated["active_run_id"] == "run-3109832007"
    assert updated["frontier_ids"] == [3109832007]
    assert updated["open_milestone_ids"] == [3109832007]


def test_apply_status_alias_fields_uses_frontier_ids_for_idle_flagship_slice_when_open_ids_missing() -> None:
    module = _load_module()

    updated = module._apply_status_alias_fields(
        {
            "mode": "flagship_product",
            "frontier_ids": [34],
            "open_milestone_ids": [],
        }
    )

    assert updated["frontier_ids"] == [34]
    assert updated["open_milestone_ids"] == [34]


def test_successor_wave_eta_snapshot_reports_dependency_critical_path() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_next_wave_registry(root)
        _write_next_wave_queue(
            root,
            [
                {
                    "repo": "chummer6-ui",
                    "package_id": "next90-101-ui",
                    "title": "Desktop release train",
                    "task": "Keep native-host release proof independent for the primary desktop head.",
                    "milestone_id": 101,
                },
                {
                    "repo": "chummer6-hub",
                    "package_id": "next90-102-hub",
                    "title": "Desktop-native trust flow",
                    "task": "Remove browser ritual from claim and support continuation.",
                    "milestone_id": 102,
                },
                {
                    "repo": "executive-assistant",
                    "package_id": "next90-103-ea",
                    "title": "Parity lab",
                    "task": "Extract Chummer5a screenshot baselines and veteran workflow packs.",
                    "milestone_id": 103,
                },
            ],
        )

        eta = module._successor_wave_eta_snapshot(root, now=dt.datetime(2026, 4, 14, 4, 0, tzinfo=dt.timezone.utc))

        assert eta["status"] == "tracked"
        assert eta["basis"] == "successor_wave_registry_dependency_critical_path"
        assert eta["remaining_open_milestones"] == 3
        assert eta["remaining_queue_items"] == 3
        assert eta["critical_path_milestone_ids"] == [101, 102, 103]
        assert eta["range_low_hours"] > 0
        assert eta["range_high_hours"] > eta["range_low_hours"]
        assert eta["scope_kind"] == "next_90_day_successor_wave"


def test_derive_successor_wave_context_routes_green_closeout_to_queue_slice() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "registry.yaml").write_text(
            yaml.safe_dump(
                {
                    "waves": [{"id": "W5"}],
                    "milestones": [{"id": 20, "title": "Closeout", "wave": "W5", "status": "complete"}],
                }
            ),
            encoding="utf-8",
        )
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("Closeout is green; successor queue is active.\n", encoding="utf-8")
        _write_next_wave_registry(root)
        _write_next_wave_queue(
            root,
            [
                {
                    "repo": "chummer6-ui",
                    "package_id": "next90-m101-ui-release-train",
                    "title": "Keep native-host release proof independent for the primary desktop head",
                    "task": "Prove Avalonia as the primary desktop route on every promoted tuple.",
                    "milestone_id": 101,
                    "wave": "W6",
                    "owned_surfaces": ["desktop_release_train:avalonia"],
                    "allowed_paths": ["Chummer.Avalonia"],
                }
            ],
        )
        shard_root = root / "state" / "chummer_design_supervisor" / "shard-1"
        shard_root.mkdir(parents=True, exist_ok=True)
        args = _args(root)
        args.state_root = str(shard_root)

        context = module.derive_successor_wave_context(
            args,
            shard_root,
            base_context=module.derive_context(args, state_root=shard_root),
            completion_audit={"status": "pass"},
            full_product_audit={"status": "pass"},
        )

        assert context is not None
        assert context["mode"] == "successor_wave"
        assert context["frontier"]
        assert context["frontier"][0].owners == ["chummer6-ui"]
        assert context["successor_wave_eta"]["scope_kind"] == "next_90_day_successor_wave"
        telemetry = context["task_local_telemetry_payload"]
        assert telemetry["polling_disabled"] is True
        assert telemetry["status_query_supported"] is False
        assert telemetry["first_commands"][0] == f"cat {module.TASK_LOCAL_TELEMETRY_FILENAME}"
        assert telemetry["queue_item"]["package_id"] == "next90-m101-ui-release-train"
        assert "next90-m101-ui-release-train" in context["prompt"]
        assert "Prove Avalonia as the primary desktop route" in context["prompt"]
        assert "TASK_LOCAL_TELEMETRY.generated.json" in context["prompt"]
        assert "Do not query supervisor status or eta from inside the worker run." in context["prompt"]


def test_derive_successor_wave_context_uses_retry_prompt_after_status_helper_loop() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "registry.yaml").write_text(
            yaml.safe_dump(
                {
                    "waves": [{"id": "W5"}],
                    "milestones": [{"id": 20, "title": "Closeout", "wave": "W5", "status": "complete"}],
                }
            ),
            encoding="utf-8",
        )
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("Closeout is green; successor queue is active.\n", encoding="utf-8")
        _write_next_wave_registry(root)
        _write_next_wave_queue(
            root,
            [
                {
                    "repo": "fleet",
                    "package_id": "next90-m106-fleet-governor-packet",
                    "title": "Publish weekly governor packets with measured launch, freeze, canary, and rollback decisions",
                    "task": "Turn readiness, parity, support, and rollout truth into a weekly governor packet that drives measured product decisions.",
                    "milestone_id": 106,
                    "wave": "W8",
                    "owned_surfaces": ["weekly_governor_packet", "measured_rollout_loop"],
                    "allowed_paths": ["admin", "scripts", "tests", ".codex-studio"],
                }
            ],
        )
        shard_root = root / "state" / "chummer_design_supervisor" / "shard-1"
        shard_root.mkdir(parents=True, exist_ok=True)
        (shard_root / "history.jsonl").write_text(
            json.dumps(
                {
                    "run_id": "run-loop",
                    "accepted": False,
                    "worker_exit_code": 124,
                    "final_message": "Error: worker_status_helper_loop:repeated_blocked_status_polling\n",
                    "acceptance_reason": "worker exit 124",
                    "blocker": "Error: worker_status_helper_loop:repeated_blocked_status_polling",
                }
            )
            + "\n",
            encoding="utf-8",
        )
        args = _args(root)
        args.state_root = str(shard_root)

        context = module.derive_successor_wave_context(
            args,
            shard_root,
            base_context=module.derive_context(args, state_root=shard_root),
            completion_audit={"status": "pass"},
            full_product_audit={"status": "pass"},
        )

        assert context is not None
        prompt = context["prompt"]
        assert "The previous attempt burned time on supervisor helper loops. This retry is implementation-only." in prompt
        assert "Run these exact commands first and do not invent another orientation step:" in prompt
        assert "Do not run supervisor status or eta helpers inside this worker run." in prompt
        assert "next90-m106-fleet-governor-packet" in prompt
        assert "admin, scripts, tests, .codex-studio" in prompt


def test_live_state_routes_green_closeout_to_successor_wave_frontier(monkeypatch) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "registry.yaml").write_text(
            yaml.safe_dump(
                {
                    "waves": [{"id": "W5"}],
                    "milestones": [{"id": 20, "title": "Closeout", "wave": "W5", "status": "complete"}],
                }
            ),
            encoding="utf-8",
        )
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("Closeout is green; successor queue is active.\n", encoding="utf-8")
        _write_flagship_product_readiness(root, status="pass")
        _write_next_wave_registry(root)
        _write_next_wave_queue(
            root,
            [
                {
                    "repo": "chummer6-hub",
                    "package_id": "next90-m102-hub-desktop-native-trust",
                    "title": "Unify claim, install, update, and support recovery into one desktop-native flow",
                    "task": "Remove browser ritual from claim and recovery.",
                    "milestone_id": 102,
                    "wave": "W6",
                    "owned_surfaces": ["desktop_native_claim_and_recovery"],
                    "allowed_paths": ["Chummer.Run.Api"],
                }
            ],
        )
        shard_root = root / "state" / "chummer_design_supervisor" / "shard-1"
        shard_root.mkdir(parents=True, exist_ok=True)
        args = _args(root)
        args.state_root = str(shard_root)
        monkeypatch.setattr(module, "_design_completion_audit", lambda _args, _history: {"status": "pass"})

        updated_state, _history = module._live_state_with_current_completion_audit(
            args,
            shard_root,
            {},
            [],
            include_shards=False,
            refresh_flagship_readiness=False,
        )

        assert updated_state["mode"] == "successor_wave"
        assert updated_state["frontier_ids"]
        assert updated_state["focus_owners"] == ["chummer6-hub"]
        assert updated_state["eta"]["scope_kind"] == "next_90_day_successor_wave"
        assert updated_state["successor_wave_eta_status"] == "tracked"


def test_live_state_routes_empty_completion_recovery_to_successor_wave(monkeypatch) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "registry.yaml").write_text(
            yaml.safe_dump(
                {
                    "waves": [{"id": "W5"}],
                    "milestones": [{"id": 20, "title": "Closeout", "wave": "W5", "status": "complete"}],
                }
            ),
            encoding="utf-8",
        )
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("Closeout is green; successor queue is active.\n", encoding="utf-8")
        _write_flagship_product_readiness(root, status="pass")
        _write_next_wave_registry(root)
        _write_next_wave_queue(
            root,
            [
                {
                    "repo": "chummer6-ui",
                    "package_id": "next90-m101-ui-release-train",
                    "title": "Keep native-host release proof independent for the primary desktop head",
                    "task": "Prove Avalonia as the primary desktop route.",
                    "milestone_id": 101,
                    "wave": "W6",
                    "owned_surfaces": ["desktop_release_train:avalonia"],
                    "allowed_paths": ["Chummer.Avalonia"],
                }
            ],
        )
        shard_root = root / "state" / "chummer_design_supervisor" / "shard-1"
        shard_root.mkdir(parents=True, exist_ok=True)
        args = _args(root)
        args.state_root = str(shard_root)
        monkeypatch.setattr(
            module,
            "_design_completion_audit",
            lambda _args, _history: {
                "status": "fail",
                "reason": "latest worker receipt run-1 is not trusted: worker exit 1",
                "repo_backlog_audit": {"status": "pass", "open_item_count": 0},
            },
        )

        updated_state, _history = module._live_state_with_current_completion_audit(
            args,
            shard_root,
            {},
            [],
            include_shards=False,
            refresh_flagship_readiness=False,
        )

        assert updated_state["mode"] == "successor_wave"
        assert updated_state["frontier_ids"]
        assert updated_state["completion_audit"]["status"] == "fail"
        assert updated_state["eta"]["scope_kind"] == "next_90_day_successor_wave"


def test_live_state_routes_missing_local_history_recovery_to_successor_wave(monkeypatch) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "registry.yaml").write_text(
            yaml.safe_dump(
                {
                    "waves": [{"id": "W5"}],
                    "milestones": [{"id": 20, "title": "Closeout", "wave": "W5", "status": "complete"}],
                }
            ),
            encoding="utf-8",
        )
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("Closeout is green; successor queue is active.\n", encoding="utf-8")
        _write_flagship_product_readiness(root, status="pass")
        _write_next_wave_registry(root)
        _write_next_wave_queue(
            root,
            [
                {
                    "repo": "chummer6-hub",
                    "package_id": "next90-m102-hub-desktop-native-trust",
                    "title": "Unify claim, install, update, and support recovery into one desktop-native flow",
                    "task": "Remove browser ritual from claim and recovery.",
                    "milestone_id": 102,
                    "wave": "W6",
                    "owned_surfaces": ["desktop_native_claim_and_recovery"],
                    "allowed_paths": ["Chummer.Run.Api"],
                }
            ],
        )
        shard_root = root / "state" / "chummer_design_supervisor" / "shard-1"
        shard_root.mkdir(parents=True, exist_ok=True)
        args = _args(root)
        args.state_root = str(shard_root)
        monkeypatch.setattr(
            module,
            "_design_completion_audit",
            lambda _args, _history: {
                "status": "fail",
                "reason": "no supervisor run history recorded; explicit completion review is required",
                "repo_backlog_audit": {"status": "pass", "open_item_count": 0},
            },
        )

        updated_state, _history = module._live_state_with_current_completion_audit(
            args,
            shard_root,
            {},
            [],
            include_shards=False,
            refresh_flagship_readiness=False,
        )

        assert updated_state["mode"] == "successor_wave"
        assert updated_state["frontier_ids"]
        assert updated_state["completion_audit"]["status"] == "fail"
        assert updated_state["eta"]["scope_kind"] == "next_90_day_successor_wave"


def test_hard_flagship_derive_routes_empty_recovery_to_successor_wave(monkeypatch, capsys) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "registry.yaml").write_text(
            yaml.safe_dump(
                {
                    "waves": [{"id": "W5"}],
                    "milestones": [{"id": 20, "title": "Closeout", "wave": "W5", "status": "complete"}],
                }
            ),
            encoding="utf-8",
        )
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("Closeout is green; successor queue is active.\n", encoding="utf-8")
        _write_flagship_product_readiness(root, status="pass")
        _write_next_wave_registry(root)
        _write_next_wave_queue(
            root,
            [
                {
                    "repo": "chummer6-ui",
                    "package_id": "next90-m101-ui-release-train",
                    "title": "Keep native-host release proof independent for the primary desktop head",
                    "task": "Prove Avalonia as the primary desktop route.",
                    "milestone_id": 101,
                    "wave": "W6",
                    "owned_surfaces": ["desktop_release_train:avalonia"],
                    "allowed_paths": ["Chummer.Avalonia"],
                }
            ],
        )
        shard_root = root / "state" / "chummer_design_supervisor" / "shard-1"
        shard_root.mkdir(parents=True, exist_ok=True)
        args = _args(root)
        args.command = "derive"
        args.state_root = str(shard_root)
        args.focus_profile = ["top_flagship_grade", "whole_project_frontier"]
        monkeypatch.setattr(
            module,
            "_design_completion_audit",
            lambda _args, _history: {
                "status": "fail",
                "reason": "latest worker receipt run-1 is not trusted: worker exit 1",
                "repo_backlog_audit": {"status": "pass", "open_item_count": 0},
            },
        )

        assert module.run_once(args) == 0

        output = capsys.readouterr().out
        assert "Run a next-90-day product advance successor-wave pass for Chummer." in output
        assert "next90-m101-ui-release-train" in output
        assert "Run a false-complete recovery pass" not in output


def test_hard_flagship_context_does_not_override_green_successor_wave(monkeypatch, tmp_path: Path) -> None:
    module = _load_module()
    args = _args(tmp_path)
    base_context = {
        "mode": "successor_wave",
        "focus_profiles": ["top_flagship_grade", "whole_project_frontier", "next_90_day_successor_wave"],
        "open_milestones": [{"id": 101}],
    }
    monkeypatch.setattr(
        module,
        "_full_product_readiness_audit",
        lambda _args: {"status": "pass", "reason": "green"},
    )

    assert module._hard_flagship_context_if_needed(args, tmp_path / "state" / "chummer_design_supervisor" / "shard-1", base_context) is None


def test_persist_live_state_snapshot_preserves_active_successor_prompt_mode() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        shard_root = root / "state" / "chummer_design_supervisor" / "shard-8"
        run_dir = shard_root / "runs" / "20260415T082804Z-shard-8"
        run_dir.mkdir(parents=True, exist_ok=True)
        prompt_path = run_dir / "prompt.txt"
        prompt_path.write_text(
            "Run a next-90-day product advance successor-wave pass for Chummer.\n",
            encoding="utf-8",
        )
        state = {
            "mode": "completion_review",
            "frontier_ids": [3017689961],
            "open_milestone_ids": [3017689961],
            "active_run": {
                "run_id": "20260415T082804Z-shard-8",
                "prompt_path": str(prompt_path),
                "frontier_ids": [3017689961],
                "open_milestone_ids": [3017689961],
            },
        }

        module._persist_live_state_snapshot(shard_root, state)

        persisted = json.loads((shard_root / "state.json").read_text(encoding="utf-8"))
        assert persisted["mode"] == "successor_wave"
        assert persisted["active_run_id"] == "20260415T082804Z-shard-8"


def test_status_json_rich_refresh_is_skipped_while_shards_are_active() -> None:
    module = _load_module()
    state = {
        "shards": [
            {
                "name": "shard-1",
                "active_run_id": "20260415T082804Z-shard-1",
                "mode": "successor_wave",
            }
        ],
        "active_runs_count": 1,
        "eta": {"status": "tracked"},
    }

    assert module._status_json_requires_rich_refresh(state, include_shards=True) is False


def test_apply_status_alias_fields_restores_successor_wave_eta_aliases() -> None:
    module = _load_module()

    updated = module._apply_status_alias_fields(
        {
            "successor_wave_eta": {
                "status": "tracked",
                "eta_human": "2d-4d",
                "summary": "6 next-wave milestones remain.",
                "range_low_hours": 48.0,
                "range_high_hours": 96.0,
                "remaining_open_milestones": 6,
                "basis": "successor_wave_registry_dependency_critical_path",
            }
        }
    )

    assert updated["successor_wave_eta_status"] == "tracked"
    assert updated["successor_wave_eta_human"] == "2d-4d"
    assert updated["successor_wave_eta_summary"] == "6 next-wave milestones remain."
    assert updated["successor_wave_range_low_hours"] == 48.0
    assert updated["successor_wave_range_high_hours"] == 96.0
    assert updated["successor_wave_remaining_open_milestones"] == 6
    assert updated["eta"]["status"] == "tracked"
    assert updated["eta"]["remaining_open_milestones"] == 6


def test_apply_status_alias_fields_does_not_invent_empty_successor_wave_eta() -> None:
    module = _load_module()

    updated = module._apply_status_alias_fields({"successor_wave_eta": {}})

    assert "successor_wave_eta" not in updated
    assert "successor_wave_eta_human" not in updated


def test_apply_status_alias_fields_infers_idle_reason_for_claimed_frontier_without_active_run() -> None:
    module = _load_module()

    updated = module._apply_status_alias_fields(
        {
            "mode": "flagship_product",
            "frontier_ids": [4087117301],
            "open_milestone_ids": [4087117301],
        }
    )

    assert updated["idle_reason"] == "claimed_frontier_without_active_run"
    assert updated["active_run_progress_state"] == "idle_claimed_frontier_without_active_run"


def test_apply_status_alias_fields_does_not_mark_parallelized_aggregate_idle() -> None:
    module = _load_module()

    updated = module._apply_status_alias_fields(
        {
            "mode": "sharded",
            "frontier_ids": [4087117301, 4087117302],
            "open_milestone_ids": [4087117301, 4087117302],
            "idle_reason": "claimed_frontier_without_active_run",
            "active_run_progress_state": "idle_claimed_frontier_without_active_run",
            "shards": [
                {
                    "name": "shard-1",
                    "active_run_id": "run-1",
                    "active_run_progress_state": "streaming",
                    "frontier_ids": [4087117301],
                    "open_milestone_ids": [4087117301],
                },
                {
                    "name": "shard-2",
                    "active_run_id": "",
                    "active_run_progress_state": "idle_claimed_frontier_without_active_run",
                    "idle_reason": "claimed_frontier_without_active_run",
                    "frontier_ids": [4087117302],
                    "open_milestone_ids": [4087117302],
                },
            ],
        }
    )

    assert updated["active_runs_count"] == 1
    assert "idle_reason" not in updated
    assert "active_run_progress_state" not in updated


def test_persist_live_state_snapshot_preserves_matching_active_run_from_existing_state() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        state_root = Path(tmp)
        active_run = {
            "run_id": "run-2",
            "frontier_ids": [21],
            "open_milestone_ids": [21],
            "last_message_path": "",
        }
        (state_root / "state.json").write_text(json.dumps({"active_run": active_run}), encoding="utf-8")

        module._persist_live_state_snapshot(
            state_root,
            {
                "updated_at": "2026-04-01T09:00:00Z",
                "mode": "flagship_product",
                "frontier_ids": [21],
                "open_milestone_ids": [21],
                "state_root": "/tmp/aggregate",
            },
        )

        persisted = json.loads((state_root / "state.json").read_text(encoding="utf-8"))

        assert persisted["mode"] == "flagship_product"
        assert persisted["active_run"]["run_id"] == "run-2"


def test_persist_live_state_snapshot_preserves_matching_active_run_with_unseen_process() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        previous_workspace_root = module.DEFAULT_WORKSPACE_ROOT
        try:
            module.DEFAULT_WORKSPACE_ROOT = root
            state_root = root / "state" / "chummer_design_supervisor" / "shard-1"
            run_dir = state_root / "runs" / "20260405T151549Z"
            run_dir.mkdir(parents=True, exist_ok=True)
            (run_dir / "last_message.txt").write_text("still running\n", encoding="utf-8")
            active_run = {
                "run_id": "run-3",
                "frontier_ids": [34],
                "open_milestone_ids": [34],
                "last_message_path": "/var/lib/codex-fleet/chummer_design_supervisor/shard-1/runs/20260405T151549Z/last_message.txt",
            }
            (state_root / "state.json").write_text(
                json.dumps(
                    {
                        "updated_at": "2026-04-05T15:16:01Z",
                        "active_run": active_run,
                        "last_run": None,
                    }
                ),
                encoding="utf-8",
            )

            module._persist_live_state_snapshot(
                state_root,
                {
                    "updated_at": "2026-04-05T15:16:01Z",
                    "mode": "flagship_product",
                    "frontier_ids": [34],
                    "open_milestone_ids": [34],
                },
            )

            persisted = json.loads((state_root / "state.json").read_text(encoding="utf-8"))

            assert persisted["active_run"]["run_id"] == "run-3"
        finally:
            module.DEFAULT_WORKSPACE_ROOT = previous_workspace_root


def test_resolve_run_artifact_path_prefers_workspace_mirror_for_container_local_artifacts(tmp_path: Path) -> None:
    module = _load_module()
    previous_workspace_root = module.DEFAULT_WORKSPACE_ROOT
    try:
        module.DEFAULT_WORKSPACE_ROOT = tmp_path
        mirrored = (
            tmp_path
            / "state"
            / "chummer_design_supervisor"
            / "shard-1"
            / "runs"
            / "20260411T200411Z"
            / "worker.stderr.log"
        )
        mirrored.parent.mkdir(parents=True, exist_ok=True)
        mirrored.write_text("worker output\n", encoding="utf-8")

        resolved = module._resolve_run_artifact_path(
            "/var/lib/codex-fleet/chummer_design_supervisor/shard-1/runs/20260411T200411Z/worker.stderr.log"
        )

        assert resolved == mirrored.resolve()
    finally:
        module.DEFAULT_WORKSPACE_ROOT = previous_workspace_root


def test_statefile_shard_summaries_recovers_container_local_active_run_when_state_dropped_it(
    monkeypatch, tmp_path: Path
) -> None:
    module = _load_module()
    root = tmp_path
    previous_workspace_root = module.DEFAULT_WORKSPACE_ROOT
    try:
        module.DEFAULT_WORKSPACE_ROOT = root
        aggregate_root = root / "state" / "chummer_design_supervisor"
        shard_root = aggregate_root / "shard-1"
        run_dir = shard_root / "runs" / "20260411T200411Z"
        run_dir.mkdir(parents=True, exist_ok=True)
        prompt_path = run_dir / "prompt.txt"
        prompt_path.write_text("read files first\n", encoding="utf-8")
        last_message_path = run_dir / "last_message.txt"
        last_message_path.write_text("still running\n", encoding="utf-8")
        stderr_path = run_dir / "worker.stderr.log"
        stderr_path.write_text("worker output\n", encoding="utf-8")
        module._write_json(
            shard_root / "state.json",
            {
                "updated_at": "2026-04-11T20:04:11Z",
                "mode": "flagship_product",
                "frontier_ids": [34],
                "open_milestone_ids": [34],
            },
        )

        monkeypatch.setattr(module, "_running_inside_container", lambda: False)
        monkeypatch.setattr(
            module,
            "_container_local_active_run_records",
            lambda: {
                "shard-1": {
                    "run_id": "20260411T200411Z",
                    "started_at": "2026-04-11T20:04:11Z",
                    "prompt_path": "/var/lib/codex-fleet/chummer_design_supervisor/shard-1/runs/20260411T200411Z/prompt.txt",
                    "stdout_path": "/var/lib/codex-fleet/chummer_design_supervisor/shard-1/runs/20260411T200411Z/worker.stdout.log",
                    "stderr_path": "/var/lib/codex-fleet/chummer_design_supervisor/shard-1/runs/20260411T200411Z/worker.stderr.log",
                    "last_message_path": "/var/lib/codex-fleet/chummer_design_supervisor/shard-1/runs/20260411T200411Z/last_message.txt",
                    "frontier_ids": [],
                    "open_milestone_ids": [],
                    "primary_milestone_id": None,
                    "worker_command": ["codexea"],
                    "selected_account_alias": "acct-ea-core-01",
                    "selected_model": "ea-coder-hard",
                    "attempt_index": 1,
                    "total_attempts": 20,
                    "watchdog_timeout_seconds": 28800.0,
                    "worker_pid": 12345,
                    "worker_first_output_at": "",
                    "worker_last_output_at": "",
                }
            },
        )

        summaries = module._statefile_shard_summaries(aggregate_root)

        assert len(summaries) == 1
        shard = summaries[0]
        assert shard["active_run_id"] == "20260411T200411Z"
        assert shard["shard_token"] == "shard-1"
        assert shard["active_frontier_ids"] == [34]
        assert shard["active_run_worker_pid"] == 12345
        assert shard["active_run_process_probe_scope"] == "container_local"
        assert shard["active_run_process_alive"] is None
        assert shard["active_run_progress_state"] == "streaming"
        assert shard["selected_account_alias"] == "acct-ea-core-01"
        assert shard["selected_model"] == "ea-coder-hard"
        assert shard["worker_stderr_path"] == str(stderr_path.resolve())
        assert shard["worker_last_message_path"] == str(last_message_path.resolve())
    finally:
        module.DEFAULT_WORKSPACE_ROOT = previous_workspace_root


def test_statefile_shard_summaries_recovers_local_proc_active_run_inside_container(
    monkeypatch, tmp_path: Path
) -> None:
    module = _load_module()
    root = tmp_path
    previous_workspace_root = module.DEFAULT_WORKSPACE_ROOT
    try:
        module.DEFAULT_WORKSPACE_ROOT = root
        aggregate_root = root / "state" / "chummer_design_supervisor"
        shard_root = aggregate_root / "shard-1"
        run_dir = shard_root / "runs" / "20260411T200411Z-shard-1"
        run_dir.mkdir(parents=True, exist_ok=True)
        last_message_path = run_dir / "last_message.txt"
        last_message_path.write_text("still running\n", encoding="utf-8")
        stdout_path = run_dir / "worker.stdout.log"
        stdout_path.write_text("", encoding="utf-8")
        stderr_path = run_dir / "worker.stderr.log"
        stderr_path.write_text("worker output\n", encoding="utf-8")
        module._write_json(
            shard_root / "state.json",
            {
                "updated_at": "2026-04-11T20:04:11Z",
                "mode": "flagship_product",
                "frontier_ids": [34],
                "open_milestone_ids": [34],
            },
        )

        monkeypatch.setattr(module, "_running_inside_container", lambda: True)
        monkeypatch.setattr(
            module,
            "_local_active_run_process_rows",
            lambda proc_root=Path("/proc"): [
                (
                    12345,
                    "node /usr/local/bin/codex -a never -s danger-full-access "
                    "exec -m gpt-5.4 "
                    "-o /var/lib/codex-fleet/chummer_design_supervisor/shard-1/runs/20260411T200411Z-shard-1/last_message.txt -",
                )
            ],
        )

        summaries = module._statefile_shard_summaries(aggregate_root)

        assert len(summaries) == 1
        shard = summaries[0]
        assert shard["active_run_id"] == "20260411T200411Z-shard-1"
        assert shard["active_run_started_at"] == "2026-04-11T20:04:11Z"
        assert shard["active_frontier_ids"] == [34]
        assert shard["active_run_worker_pid"] == 12345
        assert shard["active_run_process_probe_scope"] == "container_local"
        assert shard["active_run_process_alive"] is None
        assert shard["active_run_progress_state"] == "streaming"
        assert shard["selected_model"] == "gpt-5.4"
        assert shard["worker_stderr_path"] == str(stderr_path.resolve())
        assert shard["worker_last_message_path"] == str(last_message_path.resolve())
        assert shard["worker_stdout_path"] == str(stdout_path.resolve())
    finally:
        module.DEFAULT_WORKSPACE_ROOT = previous_workspace_root


def test_statefile_shard_summaries_treats_top_level_container_paths_as_container_scoped(
    monkeypatch, tmp_path: Path
) -> None:
    module = _load_module()
    root = tmp_path
    previous_workspace_root = module.DEFAULT_WORKSPACE_ROOT
    try:
        module.DEFAULT_WORKSPACE_ROOT = root
        aggregate_root = root / "state" / "chummer_design_supervisor"
        shard_root = aggregate_root / "shard-1"
        run_dir = shard_root / "runs" / "20260415T054540Z-shard-1"
        run_dir.mkdir(parents=True, exist_ok=True)
        stderr_path = run_dir / "worker.stderr.log"
        stdout_path = run_dir / "worker.stdout.log"
        last_message_path = run_dir / "last_message.txt"
        stderr_path.write_text("Trace: lane=core waiting for model output\n", encoding="utf-8")
        stdout_path.write_text("", encoding="utf-8")
        last_message_path.write_text("", encoding="utf-8")
        module._write_json(
            shard_root / "state.json",
            {
                "updated_at": "2026-04-15T05:45:40Z",
                "mode": "flagship_product",
                "frontier_ids": [123],
                "open_milestone_ids": [123],
                "active_run_id": "20260415T054540Z-shard-1",
                "active_run_started_at": "2026-04-15T05:45:40Z",
                "active_run_worker_pid": 618,
                "worker_stderr_path": "/var/lib/codex-fleet/chummer_design_supervisor/shard-1/runs/20260415T054540Z-shard-1/worker.stderr.log",
                "worker_stdout_path": "/var/lib/codex-fleet/chummer_design_supervisor/shard-1/runs/20260415T054540Z-shard-1/worker.stdout.log",
                "worker_last_message_path": "/var/lib/codex-fleet/chummer_design_supervisor/shard-1/runs/20260415T054540Z-shard-1/last_message.txt",
                "selected_account_alias": "acct-ea-core-06",
                "selected_model": "ea-coder-hard-batch",
            },
        )

        monkeypatch.setattr(module, "_running_inside_container", lambda: False)

        summaries = module._statefile_shard_summaries(aggregate_root)

        assert len(summaries) == 1
        shard = summaries[0]
        assert shard["active_run_worker_pid"] == 618
        assert shard["active_run_process_probe_scope"] == "container_local"
        assert shard["active_run_process_alive"] is None
        assert shard["active_run_progress_state"] == "container_scoped"
    finally:
        module.DEFAULT_WORKSPACE_ROOT = previous_workspace_root


def test_statefile_shard_summaries_treats_foreign_container_pid_as_container_scoped(
    monkeypatch, tmp_path: Path
) -> None:
    module = _load_module()
    root = tmp_path
    previous_workspace_root = module.DEFAULT_WORKSPACE_ROOT
    try:
        module.DEFAULT_WORKSPACE_ROOT = root
        aggregate_root = root / "state" / "chummer_design_supervisor"
        shard_root = aggregate_root / "shard-1"
        run_dir = shard_root / "runs" / "20260415T054540Z-shard-1"
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "worker.stderr.log").write_text("Trace: waiting\n", encoding="utf-8")
        (run_dir / "worker.stdout.log").write_text("", encoding="utf-8")
        (run_dir / "last_message.txt").write_text("", encoding="utf-8")
        module._write_json(
            shard_root / "state.json",
            {
                "updated_at": "2026-04-15T05:45:40Z",
                "mode": "flagship_product",
                "frontier_ids": [123],
                "open_milestone_ids": [123],
                "active_run_id": "20260415T054540Z-shard-1",
                "active_run_started_at": "2026-04-15T05:45:40Z",
                "active_run_worker_pid": 99999999,
                "worker_stderr_path": "/var/lib/codex-fleet/chummer_design_supervisor/shard-1/runs/20260415T054540Z-shard-1/worker.stderr.log",
                "worker_stdout_path": "/var/lib/codex-fleet/chummer_design_supervisor/shard-1/runs/20260415T054540Z-shard-1/worker.stdout.log",
                "worker_last_message_path": "/var/lib/codex-fleet/chummer_design_supervisor/shard-1/runs/20260415T054540Z-shard-1/last_message.txt",
            },
        )

        monkeypatch.setattr(module, "_running_inside_container", lambda: True)

        summaries = module._statefile_shard_summaries(aggregate_root)

        assert summaries[0]["active_run_process_probe_scope"] == "container_local"
        assert summaries[0]["active_run_process_alive"] is None
        assert summaries[0]["active_run_progress_state"] == "container_scoped"
    finally:
        module.DEFAULT_WORKSPACE_ROOT = previous_workspace_root


def test_live_state_with_current_completion_audit_overlays_fresh_completion_truth() -> None:
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
        _write_completion_evidence(root)
        state_root = root / "state"
        state_root.mkdir(parents=True, exist_ok=True)
        trusted_run = {
            "run_id": "run-9",
            "worker_exit_code": 0,
            "accepted": True,
            "acceptance_reason": "",
            "primary_milestone_id": 13,
            "frontier_ids": [13],
            "shipped": "trusted receipt",
            "remains": "none",
            "blocker": "none",
        }
        (state_root / "history.jsonl").write_text(json.dumps(trusted_run) + "\n", encoding="utf-8")

        stale_state = {
            "updated_at": "2026-03-31T08:00:00Z",
            "mode": "completion_review",
            "open_milestone_ids": [],
            "frontier_ids": [13],
            "focus_owners": ["chummer6-ui", "fleet"],
            "focus_texts": ["desktop", "client"],
            "completion_audit": {"status": "fail", "reason": "status_plane is stale."},
            "eta": {"status": "blocked", "eta_human": "unknown"},
            "last_run": trusted_run,
        }

        updated_state, updated_history = module._live_state_with_current_completion_audit(
            _args(root),
            state_root,
            stale_state,
            [trusted_run],
        )

        assert updated_history
        assert updated_state["mode"] == "flagship_product"
        assert updated_state["frontier_ids"]
        assert updated_state["focus_owners"][:2] == ["chummer6-ui", "fleet"]
        assert "desktop" in updated_state["focus_texts"]
        assert "client" in updated_state["focus_texts"]
        assert updated_state["completion_audit"]["status"] == "pass"
        assert updated_state["full_product_audit"]["status"] == "fail"
        assert updated_state["eta"]["status"] == "flagship_delivery"


def test_live_state_with_current_completion_audit_refreshes_completion_frontier_when_complete() -> None:
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
        _write_completion_evidence(root)
        _write_flagship_product_readiness(root, status="pass")
        state_root = root / "state"
        state_root.mkdir(parents=True, exist_ok=True)
        trusted_run = {
            "run_id": "run-10",
            "worker_exit_code": 0,
            "accepted": True,
            "acceptance_reason": "",
            "primary_milestone_id": 13,
            "frontier_ids": [13],
            "shipped": "trusted receipt",
            "remains": "none",
            "blocker": "none",
        }
        (state_root / "history.jsonl").write_text(json.dumps(trusted_run) + "\n", encoding="utf-8")

        stale_state = {
            "updated_at": "2026-03-31T08:00:00Z",
            "mode": "completion_review",
            "open_milestone_ids": [],
            "frontier_ids": [13],
            "active_run": {
                "run_id": "stale-complete-run",
                "frontier_ids": [13],
                "open_milestone_ids": [],
            },
            "focus_owners": ["chummer6-ui", "fleet"],
            "focus_texts": ["desktop", "client"],
            "completion_audit": {"status": "fail", "reason": "stale fail artifact."},
            "eta": {"status": "blocked", "eta_human": "unknown"},
            "last_run": trusted_run,
        }

        updated_state, _updated_history = module._live_state_with_current_completion_audit(
            _args(root),
            state_root,
            stale_state,
            [trusted_run],
        )

        assert updated_state["mode"] == "complete"
        assert updated_state["frontier_ids"] == []
        assert "active_run" not in updated_state
        assert updated_state["completion_audit"]["status"] == "pass"
        assert updated_state["full_product_audit"]["status"] == "pass"
        assert updated_state["completion_review_frontier_path"].endswith(
            "COMPLETION_REVIEW_FRONTIER.generated.yaml"
        )
        frontier_payload = yaml.safe_load(
            Path(updated_state["completion_review_frontier_path"]).read_text(encoding="utf-8")
        )
        assert frontier_payload["mode"] == "complete"
        assert frontier_payload["frontier_count"] == 0
        assert frontier_payload["completion_audit"]["status"] == "pass"


def test_materialize_full_product_frontier_refreshes_stale_receipt_only_completion_audit() -> None:
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
        _write_completion_evidence(root)
        _write_flagship_product_readiness(
            root,
            status="fail",
            ready_keys=(
                "rules_engine_and_import",
                "hub_and_registry",
                "mobile_play_shell",
                "ui_kit_and_flagship_polish",
                "media_artifacts",
                "horizons_and_public_surface",
                "fleet_and_operator_loop",
            ),
        )
        state_root = root / "state" / "shard-4"
        state_root.mkdir(parents=True, exist_ok=True)
        stale_completion_audit = {
            "status": "fail",
            "reason": "latest worker receipt run-stale-receipt is not trusted: worker exit 125",
            "receipt_audit": {
                "status": "fail",
                "reason": "latest worker receipt run-stale-receipt is not trusted: worker exit 125",
                "latest_run_id": "run-stale-receipt",
                "latest_run_reason": "worker exit 125",
            },
        }
        module._write_json(
            state_root / "state.json",
            {
                "updated_at": "2026-04-14T22:51:55Z",
                "mode": "flagship_product",
                "completion_audit": {
                    "status": "fail",
                    "reason": "desktop executable exit gate proof did not pass",
                    "receipt_audit": dict(stale_completion_audit["receipt_audit"]),
                },
                "full_product_audit": {
                    "status": "fail",
                    "reason": "flagship product readiness proof is not green: fail",
                },
            },
        )
        full_product_audit = module._full_product_readiness_audit(_args(root))
        frontier = [
            module.Milestone(
                id=module._synthetic_full_product_id("hub_registry_frontier"),
                title="Hub, registry, and public front door flagship finish",
                wave="flagship_product",
                status="not_started",
                owners=["chummer6-hub", "chummer6-hub-registry", "chummer6-design"],
                exit_criteria=["Keep flagship proof aligned with live readiness."],
                dependencies=[],
            )
        ]

        materialized = module._materialize_full_product_frontier(
            args=_args(root),
            state_root=state_root,
            mode="flagship_product",
            frontier=frontier,
            focus_profiles=["top_flagship_grade", "whole_project_frontier"],
            focus_owners=["fleet"],
            focus_texts=["desktop client", "fleet and operator loop"],
            completion_audit=stale_completion_audit,
            full_product_audit=full_product_audit,
            eta=None,
        )

        payload = yaml.safe_load(Path(materialized["published_path"]).read_text(encoding="utf-8"))
        assert payload["completion_audit"]["status"] == "fail"
        assert "latest worker receipt" not in payload["completion_audit"]["reason"]
        assert payload["completion_audit"]["reason"] == "desktop executable exit gate proof did not pass"
        assert payload["full_product_audit"]["status"] == "fail"


def test_materialize_full_product_frontier_refreshes_stale_full_product_audit() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_flagship_product_readiness(
            root,
            status="fail",
            ready_keys=(
                "rules_engine_and_import",
                "hub_and_registry",
                "mobile_play_shell",
                "ui_kit_and_flagship_polish",
                "media_artifacts",
                "horizons_and_public_surface",
                "fleet_and_operator_loop",
            ),
            warning_keys=("desktop_client",),
            completion_audit={
                "status": "fail",
                "reason": "Only external host-proof gaps remain: run the missing macos proof lane for 1 desktop tuple(s), ingest receipts, and then republish release truth.",
                "external_only": True,
                "unresolved_external_proof_request_count": 1,
            },
            external_host_proof={
                "status": "fail",
                "unresolved_request_count": 1,
                "unresolved_tuples": ["avalonia:osx-arm64:macos"],
            },
        )
        state_root = root / "state" / "shard-12"
        state_root.mkdir(parents=True, exist_ok=True)
        frontier = [
            module.Milestone(
                id=module._synthetic_full_product_id("core_engine_proof_pack"),
                title="Build golden oracle suites and release-bound engine proof packs",
                wave="flagship_product",
                status="not_started",
                owners=["chummer6-core"],
                exit_criteria=["Keep flagship proof aligned with live readiness."],
                dependencies=[],
            )
        ]

        stale_full_product_audit = {
            "status": "fail",
            "reason": "flagship product readiness proof is not green: fail",
            "path": str(root / "FLAGSHIP_PRODUCT_READINESS.generated.json"),
            "generated_at": "2026-04-14T22:53:29Z",
            "proof_status": "fail",
            "missing_coverage_keys": ["desktop_client", "fleet_and_operator_loop"],
            "parity_excluded_scope": ["plugin-framework"],
            "unresolved_parity_families": [],
        }

        materialized = module._materialize_full_product_frontier(
            args=_args(root),
            state_root=state_root,
            mode="flagship_product",
            frontier=frontier,
            focus_profiles=["top_flagship_grade", "whole_project_frontier"],
            focus_owners=["fleet"],
            focus_texts=["desktop client", "fleet and operator loop"],
            completion_audit={"status": "fail", "reason": "external only"},
            full_product_audit=stale_full_product_audit,
            eta=None,
        )

        payload = yaml.safe_load(Path(materialized["published_path"]).read_text(encoding="utf-8"))
        assert payload["full_product_audit"]["status"] == "fail"
        assert payload["full_product_audit"]["missing_coverage_keys"] == []
        assert payload["full_product_audit"]["warning_coverage_keys"] == ["desktop_client"]
        assert payload["full_product_audit"]["coverage_gap_keys"] == ["desktop_client"]


def test_full_product_readiness_audit_rejects_unresolved_parity_families() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_flagship_product_readiness(
            root,
            status="pass",
            unresolved_parity_families=(
                {
                    "id": "legacy_and_adjacent_import_oracles",
                    "status": "partial",
                    "milestone_ids": [17],
                },
            ),
        )

        audit = module._full_product_readiness_audit(_args(root))

        assert audit["status"] == "fail"
        assert audit["parity_excluded_scope"] == ["plugin-framework"]
        assert audit["unresolved_parity_families"][0]["id"] == "legacy_and_adjacent_import_oracles"
        assert "unresolved non-plugin parity families" in audit["reason"]


def test_full_product_readiness_audit_rejects_hard_flagship_proof_that_ignored_nonlinux_host_blockers() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_flagship_product_readiness(
            root,
            status="pass",
            coverage_details={
                "desktop_client": {
                    "evidence": {
                        "desktop_ignore_nonlinux_desktop_host_proof_blockers": True,
                        "release_channel_has_windows_public_installer": True,
                        "release_channel_has_macos_public_installer": True,
                    }
                }
            },
        )
        args = _args(root)
        args.focus_profile = ["top_flagship_grade", "whole_project_frontier"]

        audit = module._full_product_readiness_audit(args)

        assert audit["status"] == "fail"
        assert "non-Linux desktop host-proof blockers ignored" in audit["reason"]


def test_repo_backlog_audit_ingests_feedback_note_queue_sources(monkeypatch) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        feedback_path = root / "feedback" / "2026-04-13-post-flagship-release-train-and-veteran-certification.md"
        feedback_path.parent.mkdir(parents=True, exist_ok=True)
        feedback_path.write_text(
            "\n".join(
                [
                    "## Immediate follow-on work after current flagship closeout",
                    "- Run screenshot-backed parity review for menu, toolstrip, roster, master index, settings, and import on the promoted desktop head.",
                    "- Surface explain receipts and environment diffs on import, build blockers, and support diagnostics.",
                ]
            ),
            encoding="utf-8",
        )
        args = _args(root)
        project_cfg = {
            "id": "ui",
            "path": str(root),
            "enabled": True,
            "queue": [],
            "queue_sources": [
                {
                    "kind": "feedback_notes",
                    "path": str(feedback_path),
                    "mode": "append",
                }
            ],
        }
        monkeypatch.setattr(module, "_load_project_cfgs", lambda path: [project_cfg])

        audit = module._repo_backlog_audit(args)

        assert audit["status"] == "fail"
        assert audit["open_item_count"] == 2
        assert any("menu, toolstrip, roster, master index, settings, and import" in row["task"] for row in audit["open_items"])


def test_full_product_frontier_decomposes_unresolved_parity_families() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_flagship_product_readiness(
            root,
            status="pass",
            unresolved_parity_families=(
                {
                    "id": "legacy_and_adjacent_import_oracles",
                    "status": "partial",
                    "milestone_ids": [17],
                    "current_design_equivalents": ["INTEROP_AND_PORTABILITY_MODEL.md"],
                },
            ),
        )

        frontier = module._full_product_frontier(_args(root))

        assert [item.title for item in frontier] == ["Parity family: Legacy And Adjacent Import Oracles"]


def test_full_product_frontier_is_empty_when_readiness_is_green_under_hard_flagship_profile() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_flagship_product_readiness(root, status="pass")
        args = _args(root)
        args.focus_profile = ["top_flagship_grade", "whole_project_frontier"]

        assert module._full_product_frontier(args) == []


def test_full_product_frontier_does_not_inject_next_wave_queue_when_readiness_is_green() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_flagship_product_readiness(root, status="pass")
        _write_next_wave_queue(
            root,
            [
                {
                    "repo": "chummer6-hub",
                    "package_id": "next90-hub",
                    "title": "Next90 workspace continuity provenance",
                    "task": "Do not reopen the flagship frontier after green readiness.",
                }
            ],
        )
        aggregate_root = root / "state" / "chummer_design_supervisor"
        shard_root = aggregate_root / "shard-1"
        shard_root.mkdir(parents=True, exist_ok=True)
        args = _args(root)
        args.state_root = str(shard_root)
        args.focus_profile = ["top_flagship_grade", "whole_project_frontier"]

        assert module._full_product_frontier(args) == []
        payload = module._full_product_frontier_payload(
            args=args,
            state_root=shard_root,
            mode="flagship_product",
            frontier=[],
            focus_profiles=args.focus_profile,
            focus_owners=[],
            focus_texts=[],
            completion_audit={"status": "pass", "reason": "green"},
            full_product_audit=module._full_product_readiness_audit(args),
            eta=None,
        )
        assert payload["frontier_count"] == 0
        assert "source_queue_fingerprint" not in payload
        assert "queue_package" not in payload


def test_reconcile_materialized_full_product_frontier_drops_stale_claim_when_readiness_is_green() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        registry_path = root / "registry.yaml"
        registry_path.write_text(
            yaml.safe_dump(
                {
                    "waves": [{"id": "W1"}],
                    "milestones": [
                        {
                            "id": 2541792707,
                            "title": "Hub, registry, and public front door flagship finish",
                            "wave": "flagship_product",
                            "status": "not_started",
                            "owners": ["chummer6-hub", "chummer6-hub-registry", "chummer6-design"],
                            "exit_criteria": ["Keep public front-door proof aligned."],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        shard_root = root / "state" / "chummer_design_supervisor" / "shard-4"
        shard_root.mkdir(parents=True, exist_ok=True)
        module._write_json(
            shard_root / "state.json",
            {
                "frontier_ids": [2541792707],
                "open_milestone_ids": [2541792707],
                "active_run_progress_state": "streaming",
            },
        )
        frontier = [
            module.Milestone(
                id=2541792707,
                title="Hub, registry, and public front door flagship finish",
                wave="flagship_product",
                status="not_started",
                owners=["chummer6-hub", "chummer6-hub-registry", "chummer6-design"],
                exit_criteria=["Keep public front-door proof aligned."],
                dependencies=[],
            )
        ]

        reconciled = module._reconcile_materialized_full_product_frontier(
            _args(root),
            shard_root,
            frontier,
            {
                "status": "pass",
                "coverage_gap_keys": [],
                "missing_coverage_keys": [],
                "unresolved_parity_families": [],
            },
        )

        assert reconciled == []


def test_full_product_frontier_marks_external_only_blockers_explicitly(monkeypatch) -> None:
    module = _load_module()
    monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_IGNORE_NONLINUX_DESKTOP_HOST_PROOF_BLOCKERS", "0")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_flagship_product_readiness(
            root,
            status="fail",
            coverage_details={
                "fleet_and_operator_loop": {
                    "evidence": {
                        "supervisor_completion_external_only": True,
                    }
                }
            },
        )

        frontier = module._full_product_frontier(_args(root))

        assert frontier
        assert all(item.status == "blocked_external_host_proof" for item in frontier)


def test_refresh_flagship_product_readiness_artifact_disables_nonlinux_ignore_for_hard_flagship(monkeypatch) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_registry(root / "registry.yaml")
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("Flagship work remains.\n", encoding="utf-8")
        (root / ".codex-design" / "product").mkdir(parents=True, exist_ok=True)
        (root / ".codex-design" / "product" / "FLAGSHIP_RELEASE_ACCEPTANCE.yaml").write_text("product: chummer\n", encoding="utf-8")
        args = _args(root)
        args.focus_profile = ["top_flagship_grade", "whole_project_frontier"]
        args.ignore_nonlinux_desktop_host_proof_blockers = True
        monkeypatch.setattr(module, "DEFAULT_WORKSPACE_ROOT", root)
        calls: dict[str, object] = {}

        def fake_materialize_flagship_product_readiness(**kwargs):
            calls.update(kwargs)
            return {"status": "fail"}

        monkeypatch.setattr(module, "materialize_flagship_product_readiness", fake_materialize_flagship_product_readiness)

        payload = module._refresh_flagship_product_readiness_artifact(args)

        assert payload == {"status": "fail"}
        assert calls["ignore_nonlinux_desktop_host_proof_blockers"] is False


def test_full_product_frontier_defaults_to_not_started_without_external_only_signal(monkeypatch) -> None:
    module = _load_module()
    monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_IGNORE_NONLINUX_DESKTOP_HOST_PROOF_BLOCKERS", "0")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_flagship_product_readiness(
            root,
            status="fail",
            coverage_details={
                "fleet_and_operator_loop": {
                    "evidence": {
                        "supervisor_completion_external_only": False,
                    }
                }
            },
        )

        frontier = module._full_product_frontier(_args(root))

        assert frontier
        assert all(item.status == "not_started" for item in frontier)


def test_full_product_frontier_derives_external_only_from_backlog_counters(monkeypatch) -> None:
    module = _load_module()
    monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_IGNORE_NONLINUX_DESKTOP_HOST_PROOF_BLOCKERS", "0")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_flagship_product_readiness(
            root,
            status="fail",
            coverage_details={
                "fleet_and_operator_loop": {
                    "evidence": {
                        "supervisor_completion_external_only": False,
                        "external_proof_backlog_request_count": 4,
                        "support_open_non_external_packet_count": 0,
                        "journey_blocked_with_local_count": 0,
                    }
                }
            },
        )

        frontier = module._full_product_frontier(_args(root))

        assert frontier
        assert all(item.status == "blocked_external_host_proof" for item in frontier)


def test_full_product_frontier_uses_completion_external_only_signal_when_fleet_axis_is_ready(monkeypatch) -> None:
    module = _load_module()
    monkeypatch.setenv("CHUMMER_DESIGN_SUPERVISOR_IGNORE_NONLINUX_DESKTOP_HOST_PROOF_BLOCKERS", "0")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_flagship_product_readiness(
            root,
            status="fail",
            coverage_details={},
            completion_audit={
                "external_only": True,
                "unresolved_external_proof_request_count": 4,
            },
            external_host_proof={
                "unresolved_request_count": 4,
            },
        )

        frontier = module._full_product_frontier(_args(root))

        assert frontier
        assert all(item.status == "blocked_external_host_proof" for item in frontier)


def test_full_product_frontier_uses_shard_queue_package_when_present() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_flagship_product_readiness(root, status="fail")
        _write_published_queue(
            root,
            [
                {
                    "repo": "chummer6-ui",
                    "package_id": "flagship-avalonia-shell-controls",
                    "title": "Flagship desktop parity: Avalonia shell controls",
                    "task": "Rebuild the Avalonia desktop shell controls so the opening surface reads like a Chummer5a successor.",
                    "owned_surfaces": ["flagship:avalonia-shell-controls"],
                    "allowed_paths": ["Chummer.Avalonia/Controls/NavigatorPaneControl.axaml"],
                },
                {
                    "repo": "chummer6-ui",
                    "package_id": "flagship-blazor-shell-layout",
                    "title": "Flagship desktop parity: Blazor shell layout",
                    "task": "Rebuild the Blazor desktop shell so the first screen is a Chummer workbench.",
                    "owned_surfaces": ["flagship:blazor-shell-layout"],
                    "allowed_paths": ["Chummer.Blazor/Components/Layout/DesktopShell.razor"],
                },
            ],
        )
        shard_root = root / "state" / "chummer_design_supervisor" / "shard-2"
        shard_root.mkdir(parents=True, exist_ok=True)
        args = _args(root)
        args.state_root = str(shard_root)

        frontier = module._full_product_frontier(args)

        assert len(frontier) == 1
        assert frontier[0].title == "Flagship desktop parity: Blazor shell layout"
        assert frontier[0].owners == ["chummer6-ui"]
        assert frontier[0].id == module._synthetic_full_product_id("flagship-blazor-shell-layout")
        assert frontier[0].exit_criteria[0].startswith("Rebuild the Blazor desktop shell")
        assert "flagship:blazor-shell-layout" in frontier[0].exit_criteria[1]
        assert "DesktopShell.razor" in frontier[0].exit_criteria[2]


def test_full_product_frontier_payload_carries_queue_fingerprint_and_package_metadata() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_flagship_product_readiness(root, status="fail")
        _write_published_queue(
            root,
            [
                {
                    "repo": "fleet",
                    "package_id": "flagship-design-canon-familiarity-bar",
                    "title": "Flagship bar: Chummer5a familiarity canon",
                    "task": "Make the design canon explicit that flagship desktop quality means visual similarity and veteran familiarity.",
                    "owned_surfaces": ["flagship:design-canon-familiarity-bar"],
                    "allowed_paths": [
                        ".codex-design/product/CHUMMER5A_FAMILIARITY_BRIDGE.md",
                        ".codex-design/product/FLAGSHIP_PRODUCT_BAR.md",
                    ],
                    "priority": 21,
                }
            ],
            fingerprint="abc123",
        )
        shard_root = root / "state" / "chummer_design_supervisor" / "shard-1"
        shard_root.mkdir(parents=True, exist_ok=True)
        args = _args(root)
        args.state_root = str(shard_root)
        frontier = module._full_product_frontier(args)
        audit = module._full_product_readiness_audit(args)

        payload = module._full_product_frontier_payload(
            args=args,
            state_root=shard_root,
            mode="flagship_product",
            frontier=frontier,
            focus_profiles=[],
            focus_owners=[],
            focus_texts=[],
            completion_audit={"status": "fail", "reason": "pending"},
            full_product_audit=audit,
            eta=None,
        )

        assert payload["source_queue_fingerprint"] == "abc123"
        assert payload["queue_package"]["repo"] == "fleet"
        assert payload["queue_package"]["package_id"] == "flagship-design-canon-familiarity-bar"
        assert payload["queue_package"]["priority"] == 21
        assert payload["queue_package"]["owned_surfaces"] == ["flagship:design-canon-familiarity-bar"]
        assert payload["queue_package"]["allowed_paths"] == [
            ".codex-design/product/CHUMMER5A_FAMILIARITY_BRIDGE.md",
            ".codex-design/product/FLAGSHIP_PRODUCT_BAR.md",
        ]
        assert payload["frontier"][0]["eta"]["status"] == "flagship_delivery"
        assert payload["frontier"][0]["eta"]["remaining_open_milestones"] == 1
        assert payload["frontier"][0]["eta"]["range_low_hours"] is not None
        assert payload["frontier"][0]["eta"]["range_high_hours"] is not None


def test_full_product_frontier_uses_next_wave_queue_only_for_idle_shards(monkeypatch) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_flagship_product_readiness(root, status="fail")
        _write_next_wave_queue(
            root,
            [
                {
                    "repo": "chummer6-ui",
                    "package_id": "next90-ui",
                    "title": "Next90 UI desktop release train",
                    "task": "Keep native-host release proof independent for the primary desktop head.",
                    "owned_surfaces": ["desktop_release_train:avalonia"],
                    "allowed_paths": ["Chummer.Avalonia"],
                },
                {
                    "repo": "fleet",
                    "package_id": "next90-fleet",
                    "title": "Next90 fleet governor packet",
                    "task": "Publish weekly governor packets with measured launch and rollback decisions.",
                    "owned_surfaces": ["weekly_governor_packet"],
                    "allowed_paths": ["scripts"],
                },
            ],
            fingerprint="next90-abc",
        )
        aggregate_root = root / "state" / "chummer_design_supervisor"
        for name in ("shard-1", "shard-2", "shard-3", "shard-4"):
            (aggregate_root / name).mkdir(parents=True, exist_ok=True)

        base_frontier = [
            module.Milestone(
                id=9001,
                title="Current flagship closeout A",
                wave="W5",
                status="in_progress",
                owners=["chummer6-ui"],
                exit_criteria=["Land current closeout A."],
                dependencies=[],
            ),
            module.Milestone(
                id=9002,
                title="Current flagship closeout B",
                wave="W5",
                status="in_progress",
                owners=["chummer6-core"],
                exit_criteria=["Land current closeout B."],
                dependencies=[],
            ),
        ]
        monkeypatch.setattr(module, "_full_product_readiness_audit", lambda args: {"status": "fail"})

        active_args = _args(root)
        active_args.state_root = str(aggregate_root / "shard-1")
        assert module._queue_driven_full_product_frontier(active_args, base_frontier) == []

        idle_args = _args(root)
        idle_args.state_root = str(aggregate_root / "shard-3")
        idle_frontier = module._queue_driven_full_product_frontier(idle_args, base_frontier)
        assert len(idle_frontier) == 1
        assert idle_frontier[0].title == "Next90 UI desktop release train"
        assert idle_frontier[0].owners == ["chummer6-ui"]

        second_idle_args = _args(root)
        second_idle_args.state_root = str(aggregate_root / "shard-4")
        second_idle_frontier = module._queue_driven_full_product_frontier(second_idle_args, base_frontier)
        assert len(second_idle_frontier) == 1
        assert second_idle_frontier[0].title == "Next90 fleet governor packet"
        assert second_idle_frontier[0].owners == ["fleet"]


def test_full_product_frontier_payload_carries_next_wave_queue_fingerprint_for_idle_shard(monkeypatch) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_flagship_product_readiness(root, status="fail")
        _write_next_wave_queue(
            root,
            [
                {
                    "repo": "chummer6-hub",
                    "package_id": "next90-hub",
                    "title": "Next90 workspace continuity provenance",
                    "task": "Emit provenance and conflict receipts for workspace restore and continuity.",
                    "owned_surfaces": ["workspace_restore:provenance"],
                    "allowed_paths": ["Chummer.Run.Api"],
                    "priority": 7,
                }
            ],
            fingerprint="next90-live",
        )
        aggregate_root = root / "state" / "chummer_design_supervisor"
        for name in ("shard-1", "shard-2"):
            (aggregate_root / name).mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(module, "_full_product_readiness_audit", lambda args: {"status": "fail"})
        monkeypatch.setattr(module, "_default_full_product_frontier", lambda args, audit: [])

        shard_root = aggregate_root / "shard-1"
        args = _args(root)
        args.state_root = str(shard_root)
        frontier = module._full_product_frontier(args)
        audit = module._full_product_readiness_audit(args)

        payload = module._full_product_frontier_payload(
            args=args,
            state_root=shard_root,
            mode="flagship_product",
            frontier=frontier,
            focus_profiles=[],
            focus_owners=[],
            focus_texts=[],
            completion_audit={"status": "fail", "reason": "pending"},
            full_product_audit=audit,
            eta=None,
        )

        assert payload["source_queue_fingerprint"] == "next90-live"
        assert payload["queue_package"]["repo"] == "chummer6-hub"
        assert payload["queue_package"]["package_id"] == "next90-hub"
        assert payload["queue_package"]["priority"] == 7


def test_derive_flagship_product_context_keeps_next_wave_queue_slice_for_idle_shard(monkeypatch) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_registry(root / "registry.yaml")
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("Flagship frontier remains open.\n", encoding="utf-8")
        _write_flagship_product_readiness(root, status="fail")
        aggregate_root = root / "state" / "chummer_design_supervisor"
        for name in ("shard-1", "shard-2", "shard-3", "shard-4"):
            (aggregate_root / name).mkdir(parents=True, exist_ok=True)
        _write_next_wave_queue(
            root,
            [
                {
                    "repo": "chummer6-ui",
                    "package_id": "next90-ui",
                    "title": "Next90 UI desktop release train",
                    "task": "Keep native-host release proof independent for the primary desktop head.",
                    "owned_surfaces": ["desktop_release_train:avalonia"],
                    "allowed_paths": ["Chummer.Avalonia"],
                },
                {
                    "repo": "fleet",
                    "package_id": "next90-fleet",
                    "title": "Next90 fleet governor packet",
                    "task": "Publish weekly governor packets with measured launch and rollback decisions.",
                    "owned_surfaces": ["weekly_governor_packet"],
                    "allowed_paths": ["scripts"],
                },
            ],
            fingerprint="next90-abc",
        )

        base_frontier = [
            module.Milestone(
                id=9001,
                title="Current flagship closeout A",
                wave="W5",
                status="in_progress",
                owners=["chummer6-ui"],
                exit_criteria=["Land current closeout A."],
                dependencies=[],
            ),
            module.Milestone(
                id=9002,
                title="Current flagship closeout B",
                wave="W5",
                status="in_progress",
                owners=["chummer6-core"],
                exit_criteria=["Land current closeout B."],
                dependencies=[],
            ),
        ]
        monkeypatch.setattr(module, "_default_full_product_frontier", lambda args, audit: list(base_frontier))
        monkeypatch.setattr(module, "_design_completion_audit", lambda args, history: {"status": "pass"})

        args = _args(root)
        args.focus_profile = ["top_flagship_grade", "whole_project_frontier"]
        shard_root = aggregate_root / "shard-3"
        args.state_root = str(shard_root)

        context = module.derive_flagship_product_context(
            args,
            shard_root,
            base_context=module.derive_context(args),
        )

        assert len(context["frontier"]) == 1
        assert context["frontier"][0].title == "Next90 UI desktop release train"
        assert context["frontier_ids"] == [module._synthetic_full_product_id("next90-ui")]


def test_derive_flagship_product_context_honors_frontier_id_override() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_registry(root / "registry.yaml")
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("Flagship frontier remains open.\n", encoding="utf-8")
        _write_completion_evidence(root)
        _write_flagship_product_readiness(root, status="fail")
        shard_root = root / "state" / "chummer_design_supervisor" / "shard-3"
        shard_root.mkdir(parents=True, exist_ok=True)
        args = _args(root)
        args.focus_profile = ["top_flagship_grade", "whole_project_frontier"]
        args.frontier_id = [3449507998]

        context = module.derive_flagship_product_context(
            args,
            shard_root,
            base_context=module.derive_context(args),
        )

        assert context["frontier_ids"] == [3449507998]
        assert [item.id for item in context["frontier"]] == [3449507998]


def test_derive_flagship_product_context_honors_runtime_handoff_frontier_ids(monkeypatch) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_registry(root / "registry.yaml")
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("Flagship frontier remains open.\n", encoding="utf-8")
        _write_completion_evidence(root)
        _write_flagship_product_readiness(root, status="fail")
        shard_root = root / "state" / "chummer_design_supervisor" / "shard-8"
        shard_root.mkdir(parents=True, exist_ok=True)
        (shard_root / module.DEFAULT_SHARD_RUNTIME_HANDOFF_FILENAME).write_text(
            "Frontier ids: 3109832007\n",
            encoding="utf-8",
        )
        args = _args(root)
        args.focus_profile = ["top_flagship_grade", "whole_project_frontier"]

        frontier = [
            module.Milestone(
                id=4575045159,
                title="Horizons, public guide, and flagship future-lane posture",
                wave="flagship_product",
                status="not_started",
                owners=["chummer6-design"],
                exit_criteria=["keep horizons aligned"],
                dependencies=[],
            ),
            module.Milestone(
                id=3109832007,
                title="Fleet and operator loop flagship finish",
                wave="flagship_product",
                status="not_started",
                owners=["fleet"],
                exit_criteria=["keep operator loop live"],
                dependencies=[],
            ),
        ]
        monkeypatch.setattr(module, "_full_product_frontier", lambda _args: frontier)
        monkeypatch.setattr(module, "_full_product_readiness_audit", lambda _args: {"status": "fail"})
        monkeypatch.setattr(module, "_design_completion_audit", lambda _args, _history: {"status": "pass"})

        context = module.derive_flagship_product_context(
            args,
            shard_root,
            base_context=module.derive_context(args, state_root=shard_root),
        )

        assert context["frontier_ids"] == [3109832007]
        assert [item.id for item in context["frontier"]] == [3109832007]


def test_derive_flagship_product_context_uses_registry_milestone_for_runtime_handoff_when_full_frontier_is_synthetic(
    monkeypatch,
) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_registry(root / "registry.yaml")
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("Flagship frontier remains open.\n", encoding="utf-8")
        _write_completion_evidence(root)
        _write_flagship_product_readiness(root, status="fail")
        shard_root = root / "state" / "chummer_design_supervisor" / "shard-8"
        shard_root.mkdir(parents=True, exist_ok=True)
        (shard_root / module.DEFAULT_SHARD_RUNTIME_HANDOFF_FILENAME).write_text(
            "Frontier ids: 1300044932\n",
            encoding="utf-8",
        )
        args = _args(root)
        args.focus_profile = ["top_flagship_grade", "whole_project_frontier"]

        synthetic_frontier = [
            module._synthetic_full_product_milestone(
                key="next90-m104-core-proof-pack",
                title="Build golden oracle suites and release-bound engine proof packs",
                owners=["chummer6-core"],
                exit_criteria=["Synthetic queue slice."],
            )
        ]
        monkeypatch.setattr(module, "_full_product_frontier", lambda _args: synthetic_frontier)
        monkeypatch.setattr(module, "_full_product_readiness_audit", lambda _args: {"status": "fail"})
        monkeypatch.setattr(module, "_design_completion_audit", lambda _args, _history: {"status": "pass"})

        context = module.derive_flagship_product_context(
            args,
            shard_root,
            base_context=module.derive_context(args, state_root=shard_root),
        )

        assert context["frontier_ids"] == [1300044932]
        assert [item.id for item in context["frontier"]] == [1300044932]
        assert context["frontier"][0].title == "Mobile and play-shell flagship finish"


def test_derive_flagship_product_context_returns_empty_slice_when_prior_shards_claim_all_frontier(monkeypatch) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_registry(root / "registry.yaml")
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("Flagship frontier remains open.\n", encoding="utf-8")
        shard_root = root / "state" / "chummer_design_supervisor" / "shard-4"
        shard_root.mkdir(parents=True, exist_ok=True)
        args = _args(root)
        args.focus_profile = ["top_flagship_grade", "whole_project_frontier"]

        module._write_json(
            root / "state" / "chummer_design_supervisor" / "shard-1" / "state.json",
            {"active_run": {"run_id": "run-1", "frontier_ids": [4066417069]}},
        )
        module._write_json(
            root / "state" / "chummer_design_supervisor" / "shard-2" / "state.json",
            {"active_run": {"run_id": "run-2", "frontier_ids": [3449507998]}},
        )
        module._write_json(
            root / "state" / "chummer_design_supervisor" / "shard-3" / "state.json",
            {"active_run": {"run_id": "run-3", "frontier_ids": [2541792707]}},
        )

        frontier = [
            module.Milestone(id=4066417069, title="Desktop proof", wave="W1", status="pending", owners=["fleet"], exit_criteria=["prove desktop"], dependencies=[]),
            module.Milestone(id=3449507998, title="Core proof", wave="W1", status="pending", owners=["fleet"], exit_criteria=["prove core"], dependencies=[]),
            module.Milestone(id=2541792707, title="Hub proof", wave="W1", status="pending", owners=["fleet"], exit_criteria=["prove hub"], dependencies=[]),
        ]
        monkeypatch.setattr(module, "_full_product_frontier", lambda _args: frontier)
        monkeypatch.setattr(module, "_full_product_readiness_audit", lambda _args: {"status": "fail"})
        monkeypatch.setattr(module, "_design_completion_audit", lambda _args, _history: {"status": "pass"})

        context = module.derive_flagship_product_context(
            args,
            shard_root,
            base_context=module.derive_context(args),
        )

        assert context["frontier"] == []
        assert context["frontier_ids"] == []


def test_derive_flagship_product_context_uses_deterministic_shard_slice(monkeypatch) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_registry(root / "registry.yaml")
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("Flagship frontier remains open.\n", encoding="utf-8")
        for index in range(1, 5):
            (root / "state" / "chummer_design_supervisor" / f"shard-{index}").mkdir(parents=True, exist_ok=True)
        shard_root = root / "state" / "chummer_design_supervisor" / "shard-2"
        args = _args(root)
        args.focus_profile = ["top_flagship_grade", "whole_project_frontier"]

        frontier = [
            module.Milestone(id=4066417069, title="Desktop proof", wave="W1", status="pending", owners=["fleet"], exit_criteria=["prove desktop"], dependencies=[]),
            module.Milestone(id=3449507998, title="Core proof", wave="W1", status="pending", owners=["fleet"], exit_criteria=["prove core"], dependencies=[]),
            module.Milestone(id=2541792707, title="Hub proof", wave="W1", status="pending", owners=["fleet"], exit_criteria=["prove hub"], dependencies=[]),
        ]
        monkeypatch.setattr(module, "_full_product_frontier", lambda _args: frontier)
        monkeypatch.setattr(module, "_full_product_readiness_audit", lambda _args: {"status": "fail"})
        monkeypatch.setattr(module, "_design_completion_audit", lambda _args, _history: {"status": "pass"})

        context = module.derive_flagship_product_context(
            args,
            shard_root,
            base_context=module.derive_context(args),
        )

        assert [item.id for item in context["frontier"]] == [3449507998]
        assert context["frontier_ids"] == [3449507998]


def test_whole_project_frontier_profile_keeps_full_flagship_frontier_for_shard_slicing(monkeypatch) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_registry(root / "registry.yaml")
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("Flagship frontier remains open.\n", encoding="utf-8")
        shard_root = root / "state" / "chummer_design_supervisor" / "shard-8"
        for index in range(1, 14):
            (root / "state" / "chummer_design_supervisor" / f"shard-{index}").mkdir(parents=True, exist_ok=True)
        args = _args(root)
        args.focus_profile = ["top_flagship_grade", "whole_project_frontier"]
        args.focus_owner = ["chummer6-ui", "chummer6-hub", "chummer6-design", "chummer6-core", "chummer6-media-factory"]
        args.focus_text = ["desktop client", "proof shelf"]

        frontier = [
            module.Milestone(id=4066417069, title="Desktop", wave="W1", status="pending", owners=["chummer6-ui"], exit_criteria=["desktop"], dependencies=[]),
            module.Milestone(id=3449507998, title="Rules", wave="W1", status="pending", owners=["chummer6-core"], exit_criteria=["rules"], dependencies=[]),
            module.Milestone(id=2541792707, title="Hub", wave="W1", status="pending", owners=["chummer6-hub"], exit_criteria=["hub"], dependencies=[]),
            module.Milestone(id=1300044932, title="Mobile", wave="W1", status="pending", owners=["chummer6-mobile"], exit_criteria=["mobile"], dependencies=[]),
            module.Milestone(id=4182074715, title="UI Kit", wave="W1", status="pending", owners=["chummer6-ui-kit"], exit_criteria=["ui-kit"], dependencies=[]),
            module.Milestone(id=4355602193, title="Media", wave="W1", status="pending", owners=["chummer6-media-factory"], exit_criteria=["media"], dependencies=[]),
            module.Milestone(id=4575045159, title="Horizons", wave="W1", status="pending", owners=["chummer6-design"], exit_criteria=["horizons"], dependencies=[]),
            module.Milestone(id=3109832007, title="Fleet", wave="W1", status="pending", owners=["fleet"], exit_criteria=["fleet"], dependencies=[]),
        ]
        monkeypatch.setattr(module, "_full_product_frontier", lambda _args: frontier)
        monkeypatch.setattr(module, "_full_product_readiness_audit", lambda _args: {"status": "fail"})
        monkeypatch.setattr(module, "_design_completion_audit", lambda _args, _history: {"status": "pass"})

        context = module.derive_flagship_product_context(
            args,
            shard_root,
            base_context=module.derive_context(args, state_root=shard_root),
        )

        assert context["frontier_ids"] == [3109832007]
        assert [item.id for item in context["frontier"]] == [3109832007]


def test_live_state_with_current_completion_audit_refreshes_live_shard_summaries() -> None:
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
        _write_completion_evidence(root)
        task = "Finish ruleset-specific workbench adaptation lane"
        _write_project_backlog(root, project_id="ui", repo_slug="chummer6-ui", task=task)
        aggregate_root = root / "state"
        shard_1 = aggregate_root / "shard-1"
        shard_2 = aggregate_root / "shard-2"
        shard_1.mkdir(parents=True, exist_ok=True)
        shard_2.mkdir(parents=True, exist_ok=True)
        trusted_run = {
            "run_id": "run-good",
            "worker_exit_code": 0,
            "accepted": True,
            "acceptance_reason": "",
            "primary_milestone_id": 13,
            "frontier_ids": [13],
            "shipped": "trusted receipt",
            "remains": "none",
            "blocker": "none",
        }
        for shard_root, owners in ((shard_1, ["chummer6-ui"]), (shard_2, ["chummer6-core"])):
            module._write_json(
                shard_root / "state.json",
                {
                    "updated_at": "2026-03-31T08:00:00Z",
                    "mode": "complete",
                    "open_milestone_ids": [],
                    "frontier_ids": [],
                    "focus_owners": owners,
                    "completion_audit": {"status": "pass", "reason": "stale"},
                    "eta": {"status": "ready", "eta_human": "ready now"},
                    "active_run": {
                        "run_id": f"active-{shard_root.name}",
                        "frontier_ids": [13],
                    },
                    "last_run": trusted_run,
                },
            )
            module._append_jsonl(shard_root / "history.jsonl", trusted_run)

        state, history = module._effective_supervisor_state(aggregate_root, history_limit=10)
        updated_state, _updated_history = module._live_state_with_current_completion_audit(
            _args(root),
            aggregate_root,
            state,
            history,
        )
        synthetic_id = module._synthetic_completion_review_id(f"repo-backlog:ui:{task}")

        assert updated_state["mode"] == "sharded"
        assert updated_state["frontier_ids"][0] == synthetic_id
        assert synthetic_id in updated_state["frontier_ids"]
        assert updated_state["completion_review_frontier_path"].endswith(
            "COMPLETION_REVIEW_FRONTIER.generated.yaml"
        )
        assert updated_state["full_product_audit"]["status"] == "fail"
        assert "flagship product readiness proof is missing" in updated_state["full_product_audit"]["reason"]


def test_live_state_with_current_completion_audit_includes_successor_wave_eta() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_registry(root / "registry.yaml")
        (root / "PROGRAM_MILESTONES.yaml").write_text("product: chummer\n", encoding="utf-8")
        (root / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
        (root / "NEXT_SESSION_HANDOFF.md").write_text("Flagship frontier remains open.\n", encoding="utf-8")
        _write_flagship_product_readiness(root, status="fail")
        _write_next_wave_registry(root)
        _write_next_wave_queue(
            root,
            [
                {
                    "repo": "chummer6-ui",
                    "package_id": "next90-101-ui",
                    "title": "Desktop release train",
                    "task": "Keep native-host release proof independent for the primary desktop head.",
                    "milestone_id": 101,
                },
                {
                    "repo": "chummer6-hub",
                    "package_id": "next90-102-hub",
                    "title": "Desktop-native trust flow",
                    "task": "Remove browser ritual from claim and support continuation.",
                    "milestone_id": 102,
                },
            ],
        )
        aggregate_root = root / "state" / "chummer_design_supervisor"
        for name in ("shard-1", "shard-2", "shard-3"):
            (aggregate_root / name).mkdir(parents=True, exist_ok=True)

        args = _args(root)
        state, history = module._effective_supervisor_state(aggregate_root, history_limit=10)
        updated_state, _ = module._live_state_with_current_completion_audit(args, aggregate_root, state, history)

        assert updated_state["successor_wave_eta"]["status"] == "tracked"
        assert updated_state["successor_wave_eta"]["remaining_open_milestones"] == 3
        assert updated_state["successor_wave_eta_human"]
        assert updated_state["successor_wave_eta_status"] == "tracked"
        assert len(updated_state["shards"]) == 3


def test_write_state_populates_successor_wave_eta_for_aggregate_root() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_next_wave_registry(root)
        _write_next_wave_queue(
            root,
            [
                {
                    "repo": "chummer6-ui",
                    "package_id": "next90-101-ui",
                    "title": "Desktop release train",
                    "task": "Keep native-host release proof independent for the primary desktop head.",
                    "milestone_id": 101,
                }
            ],
        )
        aggregate_root = root / "state" / "chummer_design_supervisor"
        aggregate_root.mkdir(parents=True, exist_ok=True)

        module._write_state(
            aggregate_root,
            mode="flagship_product",
            run=None,
            open_milestones=[],
            frontier=[],
        )

        persisted = json.loads((aggregate_root / "state.json").read_text(encoding="utf-8"))

        assert persisted["successor_wave_eta"]["status"] == "tracked"
        assert persisted["successor_wave_eta_human"]


def test_render_status_shows_current_and_active_frontier_when_they_differ() -> None:
    module = _load_module()

    rendered = module._render_status(
        {
            "updated_at": "2026-03-31T10:00:00Z",
            "mode": "completion_review",
            "open_milestone_ids": [],
            "frontier_ids": [21],
            "shards": [
                {
                    "name": "shard-1",
                    "updated_at": "2026-03-31T10:00:00Z",
                    "mode": "completion_review",
                    "open_milestone_ids": [],
                    "frontier_ids": [21],
                    "active_frontier_ids": [99],
                    "eta_status": "recovery",
                    "last_run_id": "run-1",
                    "active_run_id": "active-1",
                }
            ],
        }
    )

    assert "shard.shard-1:" in rendered
    assert "frontier=21" in rendered
    assert "active_frontier=99" in rendered


def test_render_status_hides_stale_last_blocker_when_newer_active_run_exists() -> None:
    module = _load_module()

    rendered = module._render_status(
        {
            "updated_at": "2026-04-04T16:28:56Z",
            "mode": "sharded",
            "open_milestone_ids": [13, 14, 17, 18],
            "frontier_ids": [13, 14, 17, 18],
            "shards": [
                {
                    "name": "shard-2",
                    "updated_at": "2026-04-04T16:28:47Z",
                    "mode": "loop",
                    "open_milestone_ids": [13, 14, 17, 18],
                    "frontier_ids": [13, 14, 17, 18],
                    "eta_status": "estimated",
                    "last_run_id": "20260404T161600Z",
                    "last_run_blocker": "local commits are not yet pushed to remote",
                    "current_blocker": "",
                    "active_run_id": "20260404T162847Z",
                }
            ],
        }
    )

    assert "shard.shard-2:" in rendered
    assert "active_run=20260404T162847Z" in rendered
    assert "last_blocker=" not in rendered


def test_reconcile_aggregate_shard_truth_moves_stale_blocker_to_historical_field() -> None:
    module = _load_module()

    updated = module._reconcile_aggregate_shard_truth(
        {
            "open_milestone_ids": [13, 14, 17, 18],
            "eta": {
                "status": "estimated",
                "eta_human": "4.5d-1.7w",
                "eta_confidence": "low",
                "basis": "heuristic_status_mix",
                "summary": "4 open milestones remain (0 in progress, 4 not started); range is a fallback heuristic from the current status mix.",
                "remaining_open_milestones": 4,
                "remaining_in_progress_milestones": 0,
                "remaining_not_started_milestones": 4,
                "blocking_reason": "",
            },
            "shards": [
                {
                    "name": "shard-2",
                    "frontier_ids": [13, 14, 17, 18],
                    "active_frontier_ids": [13, 14, 17, 18],
                    "last_run_id": "20260404T161600Z",
                    "last_run_finished_at": "2026-04-04T16:23:15Z",
                    "last_run_blocker": "local commits are not yet pushed to remote",
                    "active_run_id": "20260404T162847Z",
                    "active_run_started_at": "2026-04-04T16:28:47Z",
                }
            ],
        }
    )

    shard = updated["shards"][0]
    assert shard["last_run_blocker"] == ""
    assert shard["current_blocker"] == ""
    assert shard["historical_last_run_blocker"] == "local commits are not yet pushed to remote"
    assert "shard_blockers" not in updated


def test_effective_supervisor_state_uses_active_runs_list_for_multiple_live_shards() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        aggregate_root = Path(tmp) / "state" / "chummer_design_supervisor"
        shard_one_root = aggregate_root / "shard-1"
        shard_two_root = aggregate_root / "shard-2"
        shard_one_root.mkdir(parents=True, exist_ok=True)
        shard_two_root.mkdir(parents=True, exist_ok=True)
        module._write_json(
            shard_one_root / "state.json",
            {
                "updated_at": "2026-04-04T16:31:48Z",
                "mode": "loop",
                "open_milestone_ids": [1, 2, 3],
                "frontier_ids": [1, 2, 3],
                "active_run": {
                    "run_id": "run-1",
                    "frontier_ids": [1, 2, 3],
                    "open_milestone_ids": [1, 2, 3],
                    "started_at": "2026-04-04T16:31:48Z",
                },
            },
        )
        module._write_json(
            shard_two_root / "state.json",
            {
                "updated_at": "2026-04-04T16:31:51Z",
                "mode": "loop",
                "open_milestone_ids": [13, 14, 17, 18],
                "frontier_ids": [13, 14, 17, 18],
                "active_run": {
                    "run_id": "run-2",
                    "frontier_ids": [13, 14, 17, 18],
                    "open_milestone_ids": [13, 14, 17, 18],
                    "started_at": "2026-04-04T16:31:51Z",
                },
            },
        )
        (aggregate_root / "active_shards.json").write_text(
            json.dumps(
                {
                    "active_shards": [
                        {"name": "shard-1", "frontier_ids": [1, 2, 3]},
                        {"name": "shard-2", "frontier_ids": [13, 14, 17, 18]},
                    ]
                }
            ),
            encoding="utf-8",
        )

        state, _history = module._effective_supervisor_state(aggregate_root, history_limit=10)

        assert "active_run" not in state
        assert [item["_shard"] for item in state["active_runs"]] == ["shard-1", "shard-2"]
        assert [item["run_id"] for item in state["active_runs"]] == ["run-1", "run-2"]
        assert state["active_runs_count"] == 2


def test_effective_supervisor_state_ignores_null_only_base_eta_when_shards_have_live_eta() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        aggregate_root = Path(tmp) / "state" / "chummer_design_supervisor"
        aggregate_root.mkdir(parents=True, exist_ok=True)
        shard_one_root = aggregate_root / "shard-1"
        shard_two_root = aggregate_root / "shard-2"
        shard_one_root.mkdir(parents=True, exist_ok=True)
        shard_two_root.mkdir(parents=True, exist_ok=True)
        module._write_json(
            aggregate_root / "state.json",
            {
                "updated_at": "2026-04-04T16:31:59Z",
                "mode": "sharded",
                "eta": {
                    "summary": None,
                    "eta_confidence": None,
                    "predicted_completion_at": None,
                    "remaining_open_milestones": None,
                    "remaining_in_progress_milestones": None,
                    "remaining_not_started_milestones": None,
                },
            },
        )
        module._write_json(
            shard_one_root / "state.json",
            {
                "updated_at": "2026-04-04T16:31:48Z",
                "mode": "loop",
                "open_milestone_ids": [1, 2],
                "frontier_ids": [1, 2],
                "eta": {
                    "status": "estimated",
                    "eta_human": "1d-2d",
                    "eta_confidence": "medium",
                    "summary": "2 open milestones remain (0 in progress, 2 not started).",
                    "remaining_open_milestones": 2,
                    "remaining_in_progress_milestones": 0,
                    "remaining_not_started_milestones": 2,
                },
                "active_run": {
                    "run_id": "run-1",
                    "frontier_ids": [1, 2],
                    "open_milestone_ids": [1, 2],
                    "started_at": "2026-04-04T16:31:48Z",
                },
            },
        )
        module._write_json(
            shard_two_root / "state.json",
            {
                "updated_at": "2026-04-04T16:31:51Z",
                "mode": "loop",
                "open_milestone_ids": [13],
                "frontier_ids": [13],
                "eta": {
                    "status": "estimated",
                    "eta_human": "1d-2d",
                    "eta_confidence": "medium",
                    "summary": "1 open milestone remains (0 in progress, 1 not started).",
                    "remaining_open_milestones": 1,
                    "remaining_in_progress_milestones": 0,
                    "remaining_not_started_milestones": 1,
                },
                "active_run": {
                    "run_id": "run-2",
                    "frontier_ids": [13],
                    "open_milestone_ids": [13],
                    "started_at": "2026-04-04T16:31:51Z",
                },
            },
        )
        (aggregate_root / "active_shards.json").write_text(
            json.dumps(
                {
                    "active_shards": [
                        {"name": "shard-1", "frontier_ids": [1, 2]},
                        {"name": "shard-2", "frontier_ids": [13]},
                    ]
                }
            ),
            encoding="utf-8",
        )

        state, _history = module._effective_supervisor_state(aggregate_root, history_limit=10)

        assert state["eta"]["summary"]
        assert state["eta"]["remaining_open_milestones"] == 3
        assert state["eta"]["remaining_in_progress_milestones"] == 3
        assert state["eta"]["remaining_not_started_milestones"] == 0
        assert state["active_runs_count"] == 2


def test_live_state_with_current_completion_audit_accepts_synthetic_receipt_on_external_worker_blocker() -> None:
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
        _write_completion_evidence(root)
        state_root = root / "state"
        state_root.mkdir(parents=True, exist_ok=True)
        blocked_run = {
            "run_id": "run-timeout",
            "worker_exit_code": 0,
            "accepted": False,
            "acceptance_reason": "Error: upstream_timeout:300s",
            "final_message": "Error: upstream_timeout:300s\n",
            "primary_milestone_id": 13,
            "frontier_ids": [13],
            "open_milestone_ids": [],
            "shipped": "",
            "remains": "",
            "blocker": "",
        }
        (state_root / "history.jsonl").write_text(json.dumps(blocked_run) + "\n", encoding="utf-8")

        updated_state, _updated_history = module._live_state_with_current_completion_audit(
            _args(root),
            state_root,
            {
                "updated_at": "2026-03-31T08:00:00Z",
                "mode": "completion_review",
                "open_milestone_ids": [],
                "frontier_ids": [13],
                "completion_audit": {"status": "fail", "reason": "worker timed out"},
                "eta": {"status": "blocked", "eta_human": "unknown"},
                "last_run": blocked_run,
            },
            [blocked_run],
        )

        assert updated_state["mode"] == "flagship_product"
        assert updated_state["completion_audit"]["status"] == "pass"
        assert updated_state["completion_audit"]["receipt_audit"]["status"] == "pass"
        assert updated_state["completion_audit"]["receipt_audit"]["synthetic"] is True
        assert "supervisor evidence receipt" in updated_state["completion_audit"]["receipt_audit"]["reason"]
        assert "upstream_timeout:300s" in updated_state["completion_audit"]["receipt_audit"]["reason"]
        assert updated_state["full_product_audit"]["status"] == "fail"
        assert updated_state["eta"]["status"] == "blocked"
        assert "full_product_frontier_heuristic" in updated_state["eta"]["basis"]


def test_live_state_with_current_completion_audit_accepts_synthetic_receipt_when_worker_not_launched() -> None:
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
        _write_completion_evidence(root)
        state_root = root / "state"
        state_root.mkdir(parents=True, exist_ok=True)
        not_launched_run = {
            "run_id": "run-not-launched",
            "worker_exit_code": 0,
            "accepted": False,
            "acceptance_reason": "worker not launched",
            "primary_milestone_id": 13,
            "frontier_ids": [],
            "open_milestone_ids": [],
            "shipped": "",
            "remains": "",
            "blocker": "",
        }
        (state_root / "history.jsonl").write_text(json.dumps(not_launched_run) + "\n", encoding="utf-8")

        updated_state, _updated_history = module._live_state_with_current_completion_audit(
            _args(root),
            state_root,
            {
                "updated_at": "2026-03-31T08:00:00Z",
                "mode": "completion_review",
                "open_milestone_ids": [],
                "frontier_ids": [],
                "completion_audit": {"status": "fail", "reason": "worker not launched"},
                "eta": {"status": "blocked", "eta_human": "unknown"},
                "last_run": not_launched_run,
            },
            [not_launched_run],
        )

        assert updated_state["mode"] == "flagship_product"
        assert updated_state["completion_audit"]["status"] == "pass"
        assert updated_state["completion_audit"]["receipt_audit"]["status"] == "pass"
        assert updated_state["completion_audit"]["receipt_audit"]["synthetic"] is True
        assert "worker not launched" in updated_state["completion_audit"]["receipt_audit"]["reason"]
        assert updated_state["eta"]["status"] == "flagship_delivery"
        assert updated_state["completion_review_frontier_path"].endswith(
            "COMPLETION_REVIEW_FRONTIER.generated.yaml"
        )
        completion_frontier_payload = yaml.safe_load(
            Path(updated_state["completion_review_frontier_path"]).read_text(encoding="utf-8")
        )
        assert completion_frontier_payload["mode"] == "complete"
        assert completion_frontier_payload["completion_audit"]["status"] == "pass"
        assert completion_frontier_payload["frontier_count"] == 0


def test_live_state_with_current_completion_audit_accepts_synthetic_receipt_for_helper_loop_timeout() -> None:
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
        _write_completion_evidence(root)
        state_root = root / "state"
        state_root.mkdir(parents=True, exist_ok=True)
        helper_loop_run = {
            "run_id": "run-helper-loop",
            "worker_exit_code": 124,
            "accepted": False,
            "acceptance_reason": "worker exit 124",
            "blocker": "Error: worker_status_helper_loop:repeated_blocked_status_polling",
            "final_message": (
                "What shipped: \n\n"
                "What remains: \n\n"
                "Exact blocker: Error: worker_status_helper_loop:repeated_blocked_status_polling\n"
            ),
            "primary_milestone_id": 13,
            "frontier_ids": [13],
            "open_milestone_ids": [13],
            "shipped": "",
            "remains": "",
        }
        (state_root / "history.jsonl").write_text(json.dumps(helper_loop_run) + "\n", encoding="utf-8")

        updated_state, _updated_history = module._live_state_with_current_completion_audit(
            _args(root),
            state_root,
            {
                "updated_at": "2026-03-31T08:00:00Z",
                "mode": "completion_review",
                "open_milestone_ids": [],
                "frontier_ids": [13],
                "completion_audit": {"status": "fail", "reason": "worker timed out"},
                "eta": {"status": "blocked", "eta_human": "unknown"},
                "last_run": helper_loop_run,
            },
            [helper_loop_run],
        )

        receipt_audit = updated_state["completion_audit"]["receipt_audit"]
        assert updated_state["completion_audit"]["status"] == "pass"
        assert receipt_audit["status"] == "pass"
        assert receipt_audit["synthetic"] is True
        assert "worker_status_helper_loop:repeated_blocked_status_polling" in receipt_audit["reason"]


def test_should_defer_external_blocker_probe_only_for_non_primary_shards() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        base_state_root = root / "state"
        shard_1 = base_state_root / "shard-1"
        shard_2 = base_state_root / "shard-2"
        shard_1.mkdir(parents=True, exist_ok=True)
        shard_2.mkdir(parents=True, exist_ok=True)
        module._write_json(shard_1 / "state.json", {"updated_at": "2026-03-31T08:00:00Z"})
        module._write_json(shard_2 / "state.json", {"updated_at": "2026-03-31T08:00:00Z"})

        assert module._should_defer_external_blocker_probe(
            shard_1,
            blocker_reason="Error: upstream_timeout:300s",
        ) is False
        assert module._should_defer_external_blocker_probe(
            shard_2,
            blocker_reason="Error: upstream_timeout:300s",
        ) is True
        assert module._should_defer_external_blocker_probe(
            base_state_root,
            blocker_reason="Error: upstream_timeout:300s",
        ) is False
        assert module._should_defer_external_blocker_probe(shard_2, blocker_reason="") is False


def test_memory_dispatch_snapshot_parks_high_index_shard_when_headroom_is_critical() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        aggregate_root = root / "state"
        for index in range(1, 5):
            shard_root = aggregate_root / f"shard-{index}"
            shard_root.mkdir(parents=True, exist_ok=True)
            module._write_json(shard_root / "state.json", {"updated_at": "2026-03-31T08:00:00Z"})

        args = _args(root)
        args.state_root = str(aggregate_root / "shard-4")

        snapshot = module._memory_dispatch_snapshot(
            args,
            Path(args.state_root),
            meminfo_bytes={
                "MemTotal": 64 * 1024**3,
                "MemAvailable": 5 * 1024**3,
                "SwapTotal": 8 * 1024**3,
                "SwapFree": 1 * 1024**3,
            },
        )

        assert snapshot["status"] == "critical"
        assert snapshot["allowed_active_shards"] == 1
        assert snapshot["eligible_shard_names"] == ["shard-1"]
        assert snapshot["current_shard_name"] == "shard-4"
        assert snapshot["dispatch_allowed"] is False
        assert snapshot["throttled"] is True


def test_memory_dispatch_snapshot_reuses_active_slots_before_parking_next_idle_shard() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        aggregate_root = root / "state"
        for index in range(1, 5):
            shard_root = aggregate_root / f"shard-{index}"
            shard_root.mkdir(parents=True, exist_ok=True)
            payload = {"updated_at": "2026-03-31T08:00:00Z"}
            if index == 2:
                payload["active_run"] = {"run_id": "active-2"}
            module._write_json(shard_root / "state.json", payload)

        args = _args(root)
        args.state_root = str(aggregate_root / "shard-3")

        snapshot = module._memory_dispatch_snapshot(
            args,
            Path(args.state_root),
            meminfo_bytes={
                "MemTotal": 64 * 1024**3,
                "MemAvailable": 7 * 1024**3,
                "SwapTotal": 8 * 1024**3,
                "SwapFree": 1 * 1024**3,
            },
        )

        assert snapshot["status"] == "warning"
        assert snapshot["allowed_active_shards"] == 2
        assert snapshot["active_shard_names"] == ["shard-2"]
        assert snapshot["eligible_shard_names"] == ["shard-2", "shard-1"]
        assert snapshot["dispatch_allowed"] is False

        follow_on = module._eligible_shard_names_for_dispatch(
            ["shard-1", "shard-2", "shard-3", "shard-4"],
            ["shard-2"],
            allowed_active_shards=2,
        )
        assert follow_on == ["shard-2", "shard-1"]


def test_memory_dispatch_snapshot_ignores_stale_swap_pressure_when_ram_headroom_is_healthy() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        aggregate_root = root / "state"
        for index in range(1, 5):
            shard_root = aggregate_root / f"shard-{index}"
            shard_root.mkdir(parents=True, exist_ok=True)
            module._write_json(shard_root / "state.json", {"updated_at": "2026-04-14T08:00:00Z"})

        args = _args(root)
        args.state_root = str(aggregate_root / "shard-4")

        snapshot = module._memory_dispatch_snapshot(
            args,
            Path(args.state_root),
            meminfo_bytes={
                "MemTotal": 16 * 1024**3,
                "MemAvailable": 8 * 1024**3,
                "SwapTotal": 8 * 1024**3,
                "SwapFree": int(1.7 * 1024**3),
            },
        )

        assert snapshot["status"] == "ok"
        assert snapshot["allowed_active_shards"] == 4
        assert snapshot["dispatch_allowed"] is True
        assert snapshot["throttled"] is False
        assert "swap used" not in str(snapshot.get("reason") or "")


def test_memory_dispatch_snapshot_applies_maintenance_operating_profile_cap_and_budgets(monkeypatch) -> None:
    module = _load_module()
    monkeypatch.setattr(module, "_RUNTIME_ENV_CANDIDATES", ())
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        aggregate_root = root / "state"
        for index in range(1, 7):
            shard_root = aggregate_root / f"shard-{index}"
            shard_root.mkdir(parents=True, exist_ok=True)
            module._write_json(shard_root / "state.json", {"updated_at": "2026-04-15T08:00:00Z"})

        args = _args(root)
        args.state_root = str(aggregate_root)
        args.operating_profile = "maintenance"
        args.memory_dispatch_reserve_gib = module.DEFAULT_MEMORY_DISPATCH_RESERVE_GIB
        args.memory_dispatch_shard_budget_gib = module.DEFAULT_MEMORY_DISPATCH_SHARD_BUDGET_GIB
        args.memory_dispatch_warning_available_percent = module.DEFAULT_MEMORY_DISPATCH_WARNING_AVAILABLE_PERCENT
        args.memory_dispatch_critical_available_percent = module.DEFAULT_MEMORY_DISPATCH_CRITICAL_AVAILABLE_PERCENT
        args.memory_dispatch_warning_swap_used_percent = module.DEFAULT_MEMORY_DISPATCH_WARNING_SWAP_USED_PERCENT
        args.memory_dispatch_critical_swap_used_percent = module.DEFAULT_MEMORY_DISPATCH_CRITICAL_SWAP_USED_PERCENT

        snapshot = module._memory_dispatch_snapshot(
            args,
            Path(args.state_root),
            meminfo_bytes={
                "MemTotal": 64 * 1024**3,
                "MemAvailable": 48 * 1024**3,
                "SwapTotal": 32 * 1024**3,
                "SwapFree": 31 * 1024**3,
            },
        )

        assert snapshot["operating_profile"] == "maintenance"
        assert snapshot["operating_profile_max_active_shards"] == 3
        assert snapshot["profile_dispatch_ceiling"] == 3
        assert snapshot["allowed_active_shards"] == 3
        assert snapshot["dispatch_reserve_bytes"] == 8 * 1024**3
        assert snapshot["per_shard_budget_bytes"] == 2 * 1024**3
        assert snapshot["throttled"] is True
        assert "maintenance operating profile caps shard dispatch at 3/6" in snapshot["reason"]


def test_memory_dispatch_snapshot_burst_operating_profile_allows_full_configured_width(monkeypatch) -> None:
    module = _load_module()
    monkeypatch.setattr(module, "_RUNTIME_ENV_CANDIDATES", ())
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        aggregate_root = root / "state"
        for index in range(1, 15):
            shard_root = aggregate_root / f"shard-{index}"
            shard_root.mkdir(parents=True, exist_ok=True)
            module._write_json(shard_root / "state.json", {"updated_at": "2026-04-15T08:00:00Z"})

        args = _args(root)
        args.state_root = str(aggregate_root)
        args.operating_profile = "burst"
        args.memory_dispatch_reserve_gib = module.DEFAULT_MEMORY_DISPATCH_RESERVE_GIB
        args.memory_dispatch_shard_budget_gib = module.DEFAULT_MEMORY_DISPATCH_SHARD_BUDGET_GIB
        args.memory_dispatch_warning_available_percent = module.DEFAULT_MEMORY_DISPATCH_WARNING_AVAILABLE_PERCENT
        args.memory_dispatch_critical_available_percent = module.DEFAULT_MEMORY_DISPATCH_CRITICAL_AVAILABLE_PERCENT
        args.memory_dispatch_warning_swap_used_percent = module.DEFAULT_MEMORY_DISPATCH_WARNING_SWAP_USED_PERCENT
        args.memory_dispatch_critical_swap_used_percent = module.DEFAULT_MEMORY_DISPATCH_CRITICAL_SWAP_USED_PERCENT

        snapshot = module._memory_dispatch_snapshot(
            args,
            Path(args.state_root),
            meminfo_bytes={
                "MemTotal": 64 * 1024**3,
                "MemAvailable": 48 * 1024**3,
                "SwapTotal": 32 * 1024**3,
                "SwapFree": 31 * 1024**3,
            },
        )

        assert snapshot["operating_profile"] == "burst"
        assert snapshot["profile_dispatch_ceiling"] == 14
        assert snapshot["allowed_active_shards"] == 14
        assert snapshot["dispatch_reserve_bytes"] == 2 * 1024**3
        assert snapshot["per_shard_budget_bytes"] == 1 * 1024**3
        assert snapshot["throttled"] is False


def test_memory_dispatch_snapshot_counts_recovered_container_local_active_runs(monkeypatch, tmp_path: Path) -> None:
    module = _load_module()
    root = tmp_path
    previous_workspace_root = module.DEFAULT_WORKSPACE_ROOT
    try:
        module.DEFAULT_WORKSPACE_ROOT = root
        aggregate_root = root / "state" / "chummer_design_supervisor"
        shard_root = aggregate_root / "shard-2"
        run_dir = shard_root / "runs" / "20260411T200423Z"
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "last_message.txt").write_text("still running\n", encoding="utf-8")
        module._write_json(
            shard_root / "state.json",
            {
                "updated_at": "2026-04-11T20:04:23Z",
                "mode": "flagship_product",
                "frontier_ids": [34],
                "open_milestone_ids": [34],
            },
        )
        args = _args(root)
        args.state_root = str(shard_root)
        monkeypatch.setattr(module, "_running_inside_container", lambda: False)
        monkeypatch.setattr(
            module,
            "_container_local_active_run_records",
            lambda: {
                "shard-2": {
                    "run_id": "20260411T200423Z",
                    "started_at": "2026-04-11T20:04:23Z",
                    "prompt_path": "/var/lib/codex-fleet/chummer_design_supervisor/shard-2/runs/20260411T200423Z/prompt.txt",
                    "stdout_path": "/var/lib/codex-fleet/chummer_design_supervisor/shard-2/runs/20260411T200423Z/worker.stdout.log",
                    "stderr_path": "/var/lib/codex-fleet/chummer_design_supervisor/shard-2/runs/20260411T200423Z/worker.stderr.log",
                    "last_message_path": "/var/lib/codex-fleet/chummer_design_supervisor/shard-2/runs/20260411T200423Z/last_message.txt",
                    "frontier_ids": [],
                    "open_milestone_ids": [],
                    "primary_milestone_id": None,
                    "worker_command": ["codexea"],
                    "selected_account_alias": "acct-ea-core-07",
                    "selected_model": "ea-coder-hard",
                    "attempt_index": 1,
                    "total_attempts": 20,
                    "watchdog_timeout_seconds": 28800.0,
                    "worker_pid": 222640,
                    "worker_first_output_at": "",
                    "worker_last_output_at": "",
                }
            },
        )

        snapshot = module._memory_dispatch_snapshot(
            args,
            shard_root,
            meminfo_bytes={
                "MemTotal": 64 * 1024**3,
                "MemAvailable": 7 * 1024**3,
                "SwapTotal": 8 * 1024**3,
                "SwapFree": 1 * 1024**3,
            },
        )

        assert snapshot["active_shard_count"] == 1
        assert snapshot["active_shard_names"] == ["shard-2"]
        assert snapshot["eligible_shard_names"] == ["shard-2"]
    finally:
        module.DEFAULT_WORKSPACE_ROOT = previous_workspace_root


def test_memory_dispatch_snapshot_counts_local_proc_recovered_active_runs_inside_container(
    monkeypatch, tmp_path: Path
) -> None:
    module = _load_module()
    root = tmp_path
    previous_workspace_root = module.DEFAULT_WORKSPACE_ROOT
    try:
        module.DEFAULT_WORKSPACE_ROOT = root
        aggregate_root = root / "state" / "chummer_design_supervisor"
        shard_root = aggregate_root / "shard-2"
        run_dir = shard_root / "runs" / "20260411T200423Z-shard-2"
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "last_message.txt").write_text("still running\n", encoding="utf-8")
        module._write_json(
            shard_root / "state.json",
            {
                "updated_at": "2026-04-11T20:04:23Z",
                "mode": "flagship_product",
                "frontier_ids": [34],
                "open_milestone_ids": [34],
            },
        )
        args = _args(root)
        args.state_root = str(shard_root)
        monkeypatch.setattr(module, "_running_inside_container", lambda: True)
        monkeypatch.setattr(
            module,
            "_local_active_run_process_rows",
            lambda proc_root=Path("/proc"): [
                (
                    222640,
                    "node /usr/local/bin/codex -a never -s danger-full-access "
                    "exec -m gpt-5.4 "
                    "-o /var/lib/codex-fleet/chummer_design_supervisor/shard-2/runs/20260411T200423Z-shard-2/last_message.txt -",
                )
            ],
        )

        snapshot = module._memory_dispatch_snapshot(
            args,
            shard_root,
            meminfo_bytes={
                "MemTotal": 64 * 1024**3,
                "MemAvailable": 7 * 1024**3,
                "SwapTotal": 8 * 1024**3,
                "SwapFree": 1 * 1024**3,
            },
        )

        assert snapshot["active_shard_count"] == 1
        assert snapshot["active_shard_names"] == ["shard-2"]
        assert snapshot["eligible_shard_names"] == ["shard-2"]
    finally:
        module.DEFAULT_WORKSPACE_ROOT = previous_workspace_root


def test_memory_dispatch_snapshot_keeps_computed_budget_when_only_headroom_warns() -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        aggregate_root = root / "state"
        for index in range(1, 14):
            shard_root = aggregate_root / f"shard-{index}"
            shard_root.mkdir(parents=True, exist_ok=True)
            module._write_json(shard_root / "state.json", {"updated_at": "2026-04-15T08:00:00Z"})

        args = _args(root)
        args.state_root = str(aggregate_root / "shard-12")
        args.memory_dispatch_reserve_gib = 2.0
        args.memory_dispatch_shard_budget_gib = 0.28
        args.memory_dispatch_warning_available_percent = module.DEFAULT_MEMORY_DISPATCH_WARNING_AVAILABLE_PERCENT
        args.memory_dispatch_critical_available_percent = module.DEFAULT_MEMORY_DISPATCH_CRITICAL_AVAILABLE_PERCENT
        args.memory_dispatch_warning_swap_used_percent = module.DEFAULT_MEMORY_DISPATCH_WARNING_SWAP_USED_PERCENT
        args.memory_dispatch_critical_swap_used_percent = module.DEFAULT_MEMORY_DISPATCH_CRITICAL_SWAP_USED_PERCENT

        snapshot = module._memory_dispatch_snapshot(
            args,
            Path(args.state_root),
            meminfo_bytes={
                "MemTotal": 16 * 1024**3,
                "MemAvailable": int(5.07 * 1024**3),
                "SwapTotal": 24 * 1024**3,
                "SwapFree": 16 * 1024**3,
            },
        )

        assert snapshot["status"] == "warning"
        assert snapshot["allowed_active_shards"] == 11
        assert snapshot["dispatch_allowed"] is False
        assert "caps shard dispatch at 11/13" in snapshot["reason"]


def test_fast_status_state_recomputes_aggregate_host_memory_pressure(monkeypatch, tmp_path: Path) -> None:
    module = _load_module()
    aggregate_root = tmp_path / "state"
    aggregate_root.mkdir(parents=True, exist_ok=True)
    for index in range(1, 3):
        shard_root = aggregate_root / f"shard-{index}"
        shard_root.mkdir(parents=True, exist_ok=True)
        module._write_json(
            shard_root / "state.json",
            {
                "updated_at": f"2026-04-12T06:0{index}:00Z",
                "mode": "loop",
                "frontier_ids": [index],
                "open_milestone_ids": [index],
                "host_memory_pressure": {
                    "status": "warning",
                    "current_shard_name": f"shard-{index}",
                    "allowed_active_shards": 5,
                },
            },
        )

    args = _args(tmp_path)
    args.state_root = str(aggregate_root)
    monkeypatch.setattr(
        module,
        "_memory_dispatch_snapshot",
        lambda _args, _state_root: {
            "status": "ok",
            "current_shard_name": "",
            "allowed_active_shards": 13,
            "dispatch_allowed": True,
        },
    )

    updated = module._fast_status_state(args, aggregate_root, {}, include_shards=True)

    assert updated["host_memory_pressure"]["status"] == "ok"
    assert updated["host_memory_pressure"]["current_shard_name"] == ""
    assert updated["host_memory_pressure"]["allowed_active_shards"] == 13
    assert updated["host_memory_status"] == "ok"
    assert updated["allowed_active_shards"] == 13


def test_write_state_persists_host_memory_status_aliases(tmp_path: Path) -> None:
    module = _load_module()
    state_root = tmp_path / "state"
    state_root.mkdir(parents=True, exist_ok=True)

    module._write_state(
        state_root,
        mode="loop",
        run=None,
        open_milestones=[],
        frontier=[],
        host_memory_pressure={
            "status": "ok",
            "allowed_active_shards": 13,
            "dispatch_allowed": True,
        },
    )

    payload = module._read_state(state_root / "state.json")
    assert payload["host_memory_pressure"]["status"] == "ok"
    assert payload["host_memory_status"] == "ok"
    assert payload["allowed_active_shards"] == 13


def test_write_state_persists_eta_aliases(tmp_path: Path) -> None:
    module = _load_module()
    state_root = tmp_path / "state"
    state_root.mkdir(parents=True, exist_ok=True)

    module._write_state(
        state_root,
        mode="flagship_product",
        run=None,
        open_milestones=[],
        frontier=[],
        eta={
            "status": "tracked",
            "eta_human": "8.2h-20.5h",
            "summary": "8 open milestones remain (5 in progress, 3 not started).",
            "eta_confidence": "low",
            "predicted_completion_at": "2026-04-14T09:00:00Z",
            "range_low_hours": 8.2,
            "range_high_hours": 20.5,
            "remaining_open_milestones": 8,
            "remaining_in_progress_milestones": 5,
            "remaining_not_started_milestones": 3,
        },
    )

    payload = module._read_state(state_root / "state.json")
    assert payload["eta"]["eta_human"] == "8.2h-20.5h"
    assert payload["remaining_open_milestones"] == 8
    assert payload["remaining_in_progress_milestones"] == 5
    assert payload["remaining_not_started_milestones"] == 3
    assert payload["eta_human"] == "8.2h-20.5h"
    assert payload["eta_status"] == "tracked"
    assert payload["eta_summary"] == "8 open milestones remain (5 in progress, 3 not started)."
    assert payload["eta_confidence"] == "low"
    assert payload["predicted_completion_at"] == "2026-04-14T09:00:00Z"
    assert payload["range_low_hours"] == 8.2
    assert payload["range_high_hours"] == 20.5


def test_write_state_persists_worker_lane_status_alias(tmp_path: Path) -> None:
    module = _load_module()
    state_root = tmp_path / "state"
    state_root.mkdir(parents=True, exist_ok=True)

    module._write_state(
        state_root,
        mode="flagship_product",
        run=None,
        open_milestones=[],
        frontier=[],
        worker_lane_health={
            "status": "pass",
            "routable_lanes": ["core", "survival"],
        },
    )

    payload = module._read_state(state_root / "state.json")
    assert payload["worker_lane_health"]["status"] == "pass"
    assert payload["worker_lanes_status"] == "pass"


def test_write_state_persists_idle_reason(tmp_path: Path) -> None:
    module = _load_module()
    state_root = tmp_path / "state"
    state_root.mkdir(parents=True, exist_ok=True)

    module._write_state(
        state_root,
        mode="flagship_product",
        run=None,
        open_milestones=[],
        frontier=[],
        idle_reason="waiting_for_local_frontier_slice",
    )

    payload = module._read_state(state_root / "state.json")
    assert payload["idle_reason"] == "waiting_for_local_frontier_slice"


def test_write_json_replaces_atomically_without_temp_leaks(tmp_path: Path) -> None:
    module = _load_module()
    target = tmp_path / "state.json"

    module._write_json(target, {"alpha": 1})
    module._write_json(target, {"beta": 2})

    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload == {"beta": 2}
    assert list(tmp_path.glob(".state.json.*.tmp")) == []


def test_apply_status_alias_fields_restores_active_and_last_run_aliases() -> None:
    module = _load_module()

    payload = module._apply_status_alias_fields(
        {
            "active_runs": [
                {"run_id": "run-123"},
                {"run_id": "run-124"},
                {"run_id": ""},
            ],
            "active_run": {
                "run_id": "run-123",
                "started_at": "2026-04-13T11:40:00Z",
                "prompt_path": "/tmp/run-123/prompt.txt",
                "stdout_path": "/tmp/run-123/stdout.log",
                "stderr_path": "/tmp/run-123/stderr.log",
                "last_message_path": "/tmp/run-123/last_message.txt",
                "worker_first_output_at": "2026-04-13T11:40:05Z",
                "worker_last_output_at": "2026-04-13T11:41:00Z",
                "worker_pid": 4242,
                "progress_state": "streaming",
                "selected_account_alias": "acct-ea-main",
                "selected_model": "ea-coder-hard",
            },
            "last_run": {
                "run_id": "run-122",
                "finished_at": "2026-04-13T11:39:00Z",
                "blocker": "worker exit 1",
            },
            "eta": {
                "status": "tracked",
                "eta_human": "8.2h-20.5h",
                "summary": "8 open milestones remain (5 in progress, 3 not started).",
                "eta_confidence": "low",
                "predicted_completion_at": "2026-04-14T09:00:00Z",
                "range_low_hours": 8.2,
                "range_high_hours": 20.5,
                "remaining_open_milestones": 8,
                "remaining_in_progress_milestones": 5,
                "remaining_not_started_milestones": 3,
            },
        }
    )

    assert payload["active_runs_count"] == 2
    assert payload["active_run_id"] == "run-123"
    assert payload["active_run_started_at"] == "2026-04-13T11:40:00Z"
    assert payload["active_run_worker_first_output_at"] == "2026-04-13T11:40:05Z"
    assert payload["active_run_worker_last_output_at"] == "2026-04-13T11:41:00Z"
    assert payload["worker_last_output_at"] == "2026-04-13T11:41:00Z"
    assert payload["active_run_worker_pid"] == 4242
    assert payload["active_run_progress_state"] == "streaming"
    assert payload["selected_account_alias"] == "acct-ea-main"
    assert payload["selected_model"] == "ea-coder-hard"
    assert payload["active_run_prompt_path"] == "/tmp/run-123/prompt.txt"
    assert payload["worker_stdout_path"] == "/tmp/run-123/stdout.log"
    assert payload["worker_stderr_path"] == "/tmp/run-123/stderr.log"
    assert payload["worker_last_message_path"] == "/tmp/run-123/last_message.txt"
    assert payload["remaining_open_milestones"] == 8
    assert payload["remaining_in_progress_milestones"] == 5
    assert payload["remaining_not_started_milestones"] == 3
    assert payload["eta_human"] == "8.2h-20.5h"
    assert payload["eta_status"] == "tracked"
    assert payload["eta_summary"] == "8 open milestones remain (5 in progress, 3 not started)."


def test_persist_live_state_snapshot_clears_dead_local_active_run(monkeypatch, tmp_path: Path) -> None:
    module = _load_module()
    shard_root = tmp_path / "state" / "chummer_design_supervisor" / "shard-1"
    shard_root.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(module, "_running_inside_container", lambda: True)
    monkeypatch.setattr(module, "_pid_alive", lambda pid: False)
    monkeypatch.setattr(module, "_write_active_shard_manifest_snapshot", lambda state_root: None)

    module._persist_live_state_snapshot(
        shard_root,
        {
            "mode": "flagship_product",
            "frontier_ids": [4066417069],
            "open_milestone_ids": [4066417069],
            "active_run": {
                "run_id": "20260414T135906Z-shard-1",
                "started_at": "2026-04-14T13:59:06Z",
                "worker_pid": 424242,
                "progress_state": "waiting_for_model_output",
                "prompt_path": "/var/lib/codex-fleet/chummer_design_supervisor/shard-1/runs/20260414T135906Z-shard-1/prompt.txt",
            },
            "active_run_worker_pid": 424242,
            "active_run_progress_state": "waiting_for_model_output",
        },
    )

    payload = module._read_state(shard_root / "state.json")
    assert payload.get("active_run") in (None, {})
    assert str(payload.get("active_run_id") or "").strip() == ""
    assert str(payload.get("idle_reason") or "").strip() == "claimed_frontier_without_active_run"


def test_update_active_run_fields_clears_idle_reason(tmp_path: Path) -> None:
    module = _load_module()
    state_root = tmp_path / "state"
    state_root.mkdir(parents=True, exist_ok=True)
    module._write_json(
        state_root / "state.json",
        {
            "updated_at": "2026-04-13T17:40:00Z",
            "idle_reason": "waiting_for_local_frontier_slice",
            "active_run": {
                "run_id": "run-123",
                "started_at": "2026-04-13T17:40:00Z",
            },
        },
    )

    module._update_active_run_fields(
        state_root,
        "run-123",
        worker_last_output_at="2026-04-13T17:40:05Z",
    )

    payload = module._read_state(state_root / "state.json")
    assert "idle_reason" not in payload
    assert payload["active_run_progress_state"] == "streaming"


def test_persist_live_state_snapshot_refreshes_shard_aliases_and_active_shards_manifest(tmp_path: Path) -> None:
    module = _load_module()
    original_running_inside_container = module._running_inside_container
    original_pid_alive = module._pid_alive
    aggregate_root = tmp_path / "state" / "chummer_design_supervisor"
    shard_root = aggregate_root / "shard-1"
    shard_root.mkdir(parents=True, exist_ok=True)
    module._write_json(
        aggregate_root / "active_shards.json",
        {
            "generated_at": "2026-04-13T11:35:00Z",
            "manifest_kind": "configured_shard_topology",
            "topology_fingerprint": "seed",
            "configured_shard_count": 1,
            "configured_shards": [
                {
                    "name": "shard-1",
                    "index": 1,
                    "frontier_ids": [4066417069],
                    "worker_bin": "/docker/fleet/scripts/codex-shims/codexea",
                    "worker_lane": "core",
                    "worker_model": "ea-coder-hard",
                }
            ],
            "active_run_count": None,
            "active_shards": [
                {
                    "name": "shard-1",
                    "index": 1,
                    "frontier_ids": [4066417069],
                    "worker_bin": "/docker/fleet/scripts/codex-shims/codexea",
                    "worker_lane": "core",
                    "worker_model": "ea-coder-hard",
                }
            ],
        },
    )

    try:
        module._running_inside_container = lambda: True
        module._pid_alive = lambda pid: True
        module._persist_live_state_snapshot(
            shard_root,
            {
                "updated_at": "2026-04-13T11:41:00Z",
                "mode": "loop",
                "frontier_ids": [4066417069],
                "open_milestone_ids": [4066417069],
                "focus_owners": ["fleet"],
                "focus_texts": ["status-plane"],
                "active_run": {
                    "run_id": "run-live-1",
                    "frontier_ids": [4066417069],
                    "open_milestone_ids": [4066417069],
                    "started_at": "2026-04-13T11:40:00Z",
                    "worker_last_output_at": "2026-04-13T11:40:30Z",
                    "worker_pid": 1234,
                    "progress_state": "streaming",
                },
            },
        )
    finally:
        module._running_inside_container = original_running_inside_container
        module._pid_alive = original_pid_alive

    shard_payload = json.loads((shard_root / "state.json").read_text(encoding="utf-8"))
    manifest_payload = json.loads((aggregate_root / "active_shards.json").read_text(encoding="utf-8"))

    assert shard_payload["shard_id"] == "shard-1"
    assert shard_payload["shard_token"] == "shard-1"
    assert shard_payload["active_run_id"] == "run-live-1"
    assert shard_payload["active_run_started_at"] == "2026-04-13T11:40:00Z"
    assert shard_payload["active_run_worker_last_output_at"] == "2026-04-13T11:40:30Z"
    assert shard_payload["worker_last_output_at"] == "2026-04-13T11:40:30Z"
    assert shard_payload["active_run_progress_state"] == "streaming"
    assert manifest_payload["configured_shards"][0]["worker_model"] == "ea-coder-hard"
    assert manifest_payload["active_run_count"] == 1
    assert manifest_payload["updated_at"] == manifest_payload["generated_at"]
    assert manifest_payload["active_shards"][0]["name"] == "shard-1"
    assert manifest_payload["active_shards"][0]["shard_id"] == "shard-1"
    assert manifest_payload["active_shards"][0]["shard_token"] == "shard-1"
    assert manifest_payload["active_shards"][0]["active_run_id"] == "run-live-1"
    assert manifest_payload["active_shards"][0]["worker_last_output_at"] == "2026-04-13T11:40:30Z"
    assert "worker_model" not in manifest_payload["active_shards"][0]


def test_reconcile_aggregate_shard_truth_clears_shard_scoped_aliases_when_parallelized() -> None:
    module = _load_module()

    updated = module._reconcile_aggregate_shard_truth(
        {
            "mode": "sharded",
            "active_run_id": "run-from-latest-shard",
            "active_run_started_at": "2026-04-14T06:00:00Z",
            "active_run_progress_state": "idle_claimed_frontier_without_active_run",
            "worker_last_output_at": "2026-04-14T06:00:05Z",
            "selected_account_alias": "acct-ea-core-01",
            "selected_model": "ea-coder-hard",
            "idle_reason": "claimed_frontier_without_active_run",
            "open_milestone_ids": [1, 2],
            "eta": {
                "status": "tracked",
                "scope_kind": "flagship_product_readiness",
                "summary": "2 open milestones remain.",
                "remaining_open_milestones": 2,
                "remaining_in_progress_milestones": 1,
                "remaining_not_started_milestones": 1,
            },
            "shards": [
                {
                    "name": "shard-1",
                    "frontier_ids": [1],
                    "active_frontier_ids": [1],
                    "open_milestone_ids": [1],
                    "active_run_id": "run-1",
                    "active_run_progress_state": "streaming",
                    "idle_reason": "",
                    "eta_scope_kind": "flagship_product_readiness",
                    "eta_remaining_open_milestones": 1,
                    "eta_remaining_in_progress_milestones": 1,
                    "eta_remaining_not_started_milestones": 0,
                },
                {
                    "name": "shard-2",
                    "frontier_ids": [2],
                    "active_frontier_ids": [],
                    "open_milestone_ids": [2],
                    "active_run_id": "",
                    "active_run_progress_state": "idle_claimed_frontier_without_active_run",
                    "idle_reason": "claimed_frontier_without_active_run",
                    "eta_scope_kind": "flagship_product_readiness",
                    "eta_remaining_open_milestones": 1,
                    "eta_remaining_in_progress_milestones": 0,
                    "eta_remaining_not_started_milestones": 1,
                },
            ],
        }
    )

    assert updated["active_runs_count"] == 1
    assert "active_run_progress_state" not in updated
    assert "active_run_id" not in updated
    assert "active_run_started_at" not in updated
    assert "worker_last_output_at" not in updated
    assert "selected_account_alias" not in updated
    assert "selected_model" not in updated
    assert "idle_reason" not in updated


def test_persist_live_state_snapshot_clears_shard_scoped_aliases_for_aggregate_root(tmp_path: Path) -> None:
    module = _load_module()
    aggregate_root = tmp_path / "state" / "chummer_design_supervisor"
    (aggregate_root / "shard-1").mkdir(parents=True, exist_ok=True)
    (aggregate_root / "shard-2").mkdir(parents=True, exist_ok=True)

    module._persist_live_state_snapshot(
        aggregate_root,
        {
            "updated_at": "2026-04-14T06:56:00Z",
            "mode": "sharded",
            "active_run_id": "run-from-latest-shard",
            "active_run_progress_state": "idle_claimed_frontier_without_active_run",
            "idle_reason": "claimed_frontier_without_active_run",
            "selected_account_alias": "acct-ea-core-01",
            "selected_model": "ea-coder-hard",
            "shards": [],
        },
    )

    payload = module._read_state(aggregate_root / "state.json")
    assert "active_run_id" not in payload
    assert "active_run_progress_state" not in payload
    assert "idle_reason" not in payload
    assert "selected_account_alias" not in payload
    assert "selected_model" not in payload


def test_live_shard_summaries_prefer_supervisor_authored_manifest_on_host(monkeypatch, tmp_path: Path) -> None:
    module = _load_module()
    aggregate_root = tmp_path / "state" / "chummer_design_supervisor"
    shard_root = aggregate_root / "shard-1"
    shard_root.mkdir(parents=True, exist_ok=True)
    module._write_json(
        aggregate_root / "active_shards.json",
        {
            "generated_at": "2026-04-13T12:15:00Z",
            "manifest_kind": "configured_shard_topology",
            "configured_shard_count": 1,
            "configured_shards": [{"name": "shard-1"}],
            "active_run_count": 1,
            "active_shards": [
                {
                    "name": "shard-1",
                    "updated_at": "2026-04-13T12:15:00Z",
                    "active_run_id": "run-from-manifest",
                    "active_run_worker_last_output_at": "2026-04-13T12:15:30Z",
                    "active_run_progress_state": "closing",
                    "selected_model": "ea-coder-hard",
                }
            ],
        },
    )
    module._write_json(
        shard_root / "state.json",
        {
            "updated_at": "2026-04-13T12:15:00Z",
            "mode": "loop",
            "frontier_ids": [13],
            "open_milestone_ids": [13],
        },
    )

    monkeypatch.setattr(module, "_running_inside_container", lambda: False)
    monkeypatch.setattr(
        module,
        "_live_state_with_current_completion_audit",
        lambda *_args, **_kwargs: (
            {
                "updated_at": "2026-04-13T12:16:00Z",
                "mode": "loop",
                "frontier_ids": [13],
                "open_milestone_ids": [13],
                "active_run": {
                    "run_id": "run-from-host",
                    "worker_last_output_at": "2026-04-13T12:16:30Z",
                    "selected_model": "host-guess",
                },
            },
            [],
        ),
    )

    summaries = module._live_shard_summaries(_args(tmp_path), aggregate_root)

    assert len(summaries) == 1
    assert summaries[0]["active_run_id"] == "run-from-manifest"
    assert summaries[0]["active_run_progress_state"] == "closing"
    assert summaries[0]["selected_model"] == "ea-coder-hard"


def test_statefile_shard_summaries_surface_inferred_idle_reason_for_claimed_frontier_without_active_run(
    monkeypatch, tmp_path: Path
) -> None:
    module = _load_module()
    aggregate_root = tmp_path / "state" / "chummer_design_supervisor"
    shard_root = aggregate_root / "shard-8"
    shard_root.mkdir(parents=True, exist_ok=True)
    module._write_json(
        shard_root / "state.json",
        {
            "updated_at": "2026-04-13T19:51:05Z",
            "mode": "flagship_product",
            "frontier_ids": [3109832007],
            "open_milestone_ids": [],
            "eta": {
                "status": "flagship_delivery",
                "summary": "Current closeout gates are green, but flagship product work still remains across 1 synthetic slices.",
                "remaining_open_milestones": 1,
                "remaining_in_progress_milestones": 0,
                "remaining_not_started_milestones": 1,
                "scope_kind": "flagship_product_readiness",
            },
        },
    )

    monkeypatch.setattr(module, "_running_inside_container", lambda: True)

    summaries = module._statefile_shard_summaries(aggregate_root)

    assert len(summaries) == 1
    assert summaries[0]["idle_reason"] == "claimed_frontier_without_active_run"
    assert summaries[0]["active_run_progress_state"] == "idle_claimed_frontier_without_active_run"
    assert summaries[0]["eta_summary"].startswith("Current closeout gates are green")


def test_statefile_shard_summaries_fall_back_to_configured_manifest_metadata_when_shard_state_is_blank(
    tmp_path: Path,
) -> None:
    module = _load_module()
    aggregate_root = tmp_path / "state" / "chummer_design_supervisor"
    shard_root = aggregate_root / "shard-2"
    shard_root.mkdir(parents=True, exist_ok=True)
    module._write_json(
        aggregate_root / "active_shards.json",
        {
            "configured_shards": [
                {
                    "name": "shard-2",
                    "index": 2,
                    "frontier_ids": [3449507998],
                    "focus_owner": ["chummer6-ui", "chummer6-ui-kit"],
                    "focus_text": ["blazor", "desktop", "shell"],
                    "account_alias": ["acct-ea-core-10"],
                    "worker_model": "ea-coder-hard",
                }
            ],
            "active_shards": [],
        },
    )

    summaries = module._statefile_shard_summaries(aggregate_root)

    assert len(summaries) == 1
    summary = summaries[0]
    assert summary["name"] == "shard-2"
    assert summary["frontier_ids"] == [3449507998]
    assert summary["open_milestone_ids"] == [3449507998]
    assert summary["focus_owners"] == ["chummer6-ui", "chummer6-ui-kit"]
    assert summary["focus_texts"] == ["blazor", "desktop", "shell"]
    assert summary["selected_account_alias"] == "acct-ea-core-10"
    assert summary["selected_model"] == "ea-coder-hard"
    assert summary["idle_reason"] == "claimed_frontier_without_active_run"
    assert summary["active_run_progress_state"] == "idle_claimed_frontier_without_active_run"


def test_reconcile_aggregate_shard_truth_counts_only_non_closing_active_runs() -> None:
    module = _load_module()

    updated = module._reconcile_aggregate_shard_truth(
        {
            "shards": [
                {"name": "shard-1", "active_run_id": "run-1", "active_run_progress_state": "closing"},
                {"name": "shard-2", "active_run_id": "run-2", "active_run_progress_state": "missing_process"},
                {"name": "shard-3", "active_run_id": "run-3", "active_run_progress_state": "streaming"},
                {"name": "shard-4", "active_run_id": "run-4"},
            ]
        }
    )

    assert updated["active_runs_count"] == 2


def test_reconcile_aggregate_shard_truth_parallelizes_eta_across_claimed_frontier_shards_even_when_closing() -> None:
    module = _load_module()

    updated = module._reconcile_aggregate_shard_truth(
        {
            "open_milestone_ids": [4066417069, 3449507998],
            "eta": {
                "status": "tracked",
                "eta_human": "tracked",
                "eta_confidence": "low",
                "basis": "full_product_frontier_heuristic",
                "scope_kind": "flagship_product_readiness",
                "scope_label": "Full Chummer5A parity and flagship proof closeout",
                "remaining_open_milestones": 2,
                "remaining_in_progress_milestones": 2,
                "remaining_not_started_milestones": 0,
                "summary": "booting",
            },
            "shards": [
                {
                    "name": "shard-1",
                    "frontier_ids": [4066417069],
                    "active_run_id": "run-1",
                    "active_run_progress_state": "closing",
                    "eta_scope_kind": "flagship_product_readiness",
                    "eta_range_low_hours": 10.86,
                    "eta_range_high_hours": 26.65,
                    "eta_remaining_open_milestones": 1,
                    "eta_remaining_in_progress_milestones": 1,
                    "eta_remaining_not_started_milestones": 0,
                },
                {
                    "name": "shard-2",
                    "frontier_ids": [3449507998],
                    "active_run_id": "run-2",
                    "active_run_progress_state": "closing",
                    "eta_scope_kind": "flagship_product_readiness",
                    "eta_range_low_hours": 9.0,
                    "eta_range_high_hours": 23.2,
                    "eta_remaining_open_milestones": 1,
                    "eta_remaining_in_progress_milestones": 1,
                    "eta_remaining_not_started_milestones": 0,
                },
            ],
        }
    )

    assert updated["active_runs_count"] == 0
    assert updated["eta"]["basis"] == "aggregate_shard_parallel_scope"
    assert updated["eta"]["range_low_hours"] == 10.86
    assert updated["eta"]["range_high_hours"] == 26.65
    assert updated["eta"]["eta_human"] == "11h-1.1d"
    assert "parallelized across 2 active shards" in updated["eta"]["summary"]


def test_memory_pressure_notice_key_ignores_reason_jitter() -> None:
    module = _load_module()

    baseline = {
        "status": "warning",
        "reason": "available headroom 7.50 GiB minus reserve 4.00 GiB caps shard dispatch at 3/14",
        "allowed_active_shards": 3,
        "configured_shard_count": 14,
        "dispatch_allowed": False,
        "current_shard_name": "shard-10",
        "eligible_shard_names": ["shard-1", "shard-2", "shard-3"],
    }
    jittered = dict(baseline)
    jittered["reason"] = "available headroom 7.02 GiB minus reserve 4.00 GiB caps shard dispatch at 3/14"

    assert module._memory_pressure_notice_key(baseline) == module._memory_pressure_notice_key(jittered)


def test_memory_pressure_notice_lists_eligible_shards_once() -> None:
    module = _load_module()

    notice = module._memory_pressure_notice(
        {
            "status": "warning",
            "reason": "available headroom 6.82 GiB minus reserve 4.00 GiB caps shard dispatch at 2/14; shard-3 is parked until host memory recovers",
            "allowed_active_shards": 2,
            "configured_shard_count": 14,
            "dispatch_allowed": False,
            "current_shard_name": "shard-3",
            "eligible_shard_names": ["shard-1", "shard-2"],
        }
    )

    assert notice.count("eligible shards:") == 1
    assert "shard-3 is parked until host memory recovers; eligible shards:" not in notice


def test_run_loop_defers_non_primary_shard_when_external_blocker_is_active(monkeypatch) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        args = _args(root)
        args.command = "loop"
        args.state_root = str(root / "state" / "shard-2")
        args.poll_seconds = 1.0
        args.cooldown_seconds = 1.0
        args.failure_backoff_seconds = 2.0
        args.max_runs = 0
        args.stop_on_blocker = False

        aggregate_root = Path(args.state_root).parent
        (aggregate_root / "shard-1").mkdir(parents=True, exist_ok=True)
        Path(args.state_root).mkdir(parents=True, exist_ok=True)
        module._write_json(aggregate_root / "shard-1" / "state.json", {"updated_at": "2026-03-31T08:00:00Z"})
        module._write_json(Path(args.state_root) / "state.json", {"updated_at": "2026-03-31T08:00:00Z"})

        milestone = module.Milestone(
            id=13,
            title="Desktop package proof",
            wave="W1",
            status="review_required",
            owners=["chummer6-ui", "fleet"],
            exit_criteria=["Desktop package ships."],
            dependencies=[],
        )
        shared_history = [
            {
                "run_id": "run-timeout",
                "worker_exit_code": 0,
                "acceptance_reason": "Error: upstream_timeout:300s",
                "final_message": "Error: upstream_timeout:300s\n",
                "frontier_ids": [13],
            }
        ]
        completion_audit = {
            "status": "fail",
            "reason": "latest worker receipt run-timeout is not trusted: Error: upstream_timeout:300s",
            "receipt_audit": {"status": "fail", "reason": "latest worker receipt run-timeout is not trusted: Error: upstream_timeout:300s"},
            "journey_gate_audit": {"status": "pass", "reason": "ok"},
            "linux_desktop_exit_gate_audit": {"status": "pass", "reason": "ok"},
            "weekly_pulse_audit": {"status": "pass", "reason": "ok"},
        }
        base_context = {
            "registry_path": root / "registry.yaml",
            "program_milestones_path": root / "PROGRAM_MILESTONES.yaml",
            "roadmap_path": root / "ROADMAP.md",
            "handoff_path": root / "NEXT_SESSION_HANDOFF.md",
            "workspace_root": root,
            "scope_roots": [root],
            "open_milestones": [],
            "wave_order": [],
            "frontier": [],
            "frontier_ids": [],
            "focus_profiles": [],
            "focus_owners": [],
            "focus_texts": [],
            "prompt": "recovery",
        }
        review_context = dict(base_context)
        review_context.update(
            {
                "frontier": [milestone],
                "frontier_ids": [13],
                "completion_audit": completion_audit,
                "completion_history": shared_history,
                "prompt": "recovery",
            }
        )

        monkeypatch.setattr(module, "derive_context", lambda _args: dict(base_context))
        monkeypatch.setattr(module, "_completion_review_history", lambda _state_root, limit: list(shared_history[-limit:]))
        monkeypatch.setattr(module, "_design_completion_audit", lambda _args, _history: dict(completion_audit))
        monkeypatch.setattr(
            module,
            "derive_completion_review_context",
            lambda _args, _state_root, base_context=None, audit=None: dict(review_context),
        )
        monkeypatch.setattr(module, "launch_worker", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("launch_worker should not run")))

        sleeps: list[float] = []

        def fake_sleep(seconds: float) -> None:
            sleeps.append(float(seconds))
            raise RuntimeError("stop-loop")

        monkeypatch.setattr(module.time, "sleep", fake_sleep)

        try:
            module.run_loop(args)
        except RuntimeError as exc:
            assert str(exc) == "stop-loop"
        else:
            raise AssertionError("expected stop-loop")

        assert sleeps
        assert sleeps[0] >= module.DEFAULT_EXTERNAL_BLOCKER_BACKOFF_SECONDS


def test_run_loop_defers_shard_when_memory_pressure_guard_is_active(monkeypatch) -> None:
    module = _load_module()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        args = _args(root)
        args.command = "loop"
        args.state_root = str(root / "state" / "shard-3")
        args.poll_seconds = 1.0
        args.memory_dispatch_parked_poll_seconds = 12.0
        args.cooldown_seconds = 1.0
        args.failure_backoff_seconds = 2.0
        args.max_runs = 0
        args.stop_on_blocker = False

        aggregate_root = Path(args.state_root).parent
        for index in range(1, 4):
            shard_root = aggregate_root / f"shard-{index}"
            shard_root.mkdir(parents=True, exist_ok=True)
            module._write_json(shard_root / "state.json", {"updated_at": "2026-03-31T08:00:00Z"})

        milestone = module.Milestone(
            id=13,
            title="Desktop package proof",
            wave="W1",
            status="review_required",
            owners=["chummer6-ui", "fleet"],
            exit_criteria=["Desktop package ships."],
            dependencies=[],
        )
        context = {
            "registry_path": root / "registry.yaml",
            "program_milestones_path": root / "PROGRAM_MILESTONES.yaml",
            "roadmap_path": root / "ROADMAP.md",
            "handoff_path": root / "NEXT_SESSION_HANDOFF.md",
            "workspace_root": root,
            "scope_roots": [root],
            "open_milestones": [milestone],
            "wave_order": [],
            "frontier": [milestone],
            "frontier_ids": [13],
            "focus_profiles": [],
            "focus_owners": [],
            "focus_texts": [],
            "prompt": "keep the shard parked",
        }

        monkeypatch.setattr(module, "derive_context", lambda _args: dict(context))
        monkeypatch.setattr(module, "_direct_worker_lane_health_snapshot", lambda *_args, **_kwargs: {})
        monkeypatch.setattr(
            module,
            "_memory_dispatch_snapshot",
            lambda *_args, **_kwargs: {
                "status": "critical",
                "reason": "MemAvailable is 6.00% <= critical 8.00%; shard-3 is parked until host memory recovers",
                "throttled": True,
                "dispatch_allowed": False,
                "allowed_active_shards": 1,
                "configured_shard_count": 3,
                "eligible_shard_names": ["shard-1"],
                "active_shard_count": 1,
                "current_shard_name": "shard-3",
            },
        )
        monkeypatch.setattr(module, "launch_worker", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("launch_worker should not run")))

        sleeps: list[float] = []

        def fake_sleep(seconds: float) -> None:
            sleeps.append(float(seconds))
            raise RuntimeError("stop-loop")

        monkeypatch.setattr(module.time, "sleep", fake_sleep)

        try:
            module.run_loop(args)
        except RuntimeError as exc:
            assert str(exc) == "stop-loop"
        else:
            raise AssertionError("expected stop-loop")

        assert sleeps == [12.0]
        state = json.loads((Path(args.state_root) / "state.json").read_text(encoding="utf-8"))
        assert state["host_memory_pressure"]["status"] == "critical"
        assert state["host_memory_pressure"]["dispatch_allowed"] is False
