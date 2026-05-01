from __future__ import annotations

import json
import importlib.util
import os
import stat
import subprocess
import sys
import tempfile
import threading
import textwrap
import unittest
from importlib.machinery import SourceFileLoader
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


SHIM_PATH = Path("/docker/fleet/scripts/codex-shims/codexea")
WATCHDOG_PATH = Path("/docker/fleet/scripts/codex-shims/codexea-watchdog")
BOOTSTRAP_PATH = Path("/docker/fleet/scripts/codex-shims/ea_interactive_bootstrap.md")
DEFAULT_EASY_INTERACTIVE_MODEL = "onemin:gpt-5.4"


def _load_watchdog_module():
    loader = SourceFileLoader("codexea_watchdog_under_test", str(WATCHDOG_PATH))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class CodexEaShimTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.root = Path(self.tempdir.name)
        self.capture_path = self.root / "capture.json"
        self.route_capture_path = self.root / "route-capture.json"
        self.fake_codex = self.root / "codex-real"
        self.fake_codex.write_text(
            "\n".join(
                [
                    "#!/usr/bin/env python3",
                    "import json, os, sys, time",
                    "sleep_seconds = float(os.environ.get('CODEXEA_TEST_FAKE_CODEX_SLEEP', '0') or '0')",
                    "if sleep_seconds > 0:",
                    "    time.sleep(sleep_seconds)",
                    "if len(sys.argv) > 1 and sys.argv[1] == '--help':",
                    "    print('--skip-git-repo-check')",
                    "    print('--no-alt-screen')",
                    "    sys.exit(0)",
                    "payload = {",
                    "    'argv': sys.argv[1:],",
                    "    'stdin': sys.stdin.read(),",
                    "    'env': {",
                    "        'CODEX_WRAPPER_SKIP_PROVIDER_DEFAULT': os.environ.get('CODEX_WRAPPER_SKIP_PROVIDER_DEFAULT'),",
                    "        'CODEXEA_LANE': os.environ.get('CODEXEA_LANE'),",
                    "        'CODEXEA_SUBMODE': os.environ.get('CODEXEA_SUBMODE'),",
                    "        'CODEXEA_RESPONSES_AUTH_TOKEN': os.environ.get('CODEXEA_RESPONSES_AUTH_TOKEN'),",
                    "        'CHUMMER_DESIGN_SUPERVISOR_ACTIVE_RUN_DIR': os.environ.get('CHUMMER_DESIGN_SUPERVISOR_ACTIVE_RUN_DIR'),",
                    "        'CHUMMER_DESIGN_SUPERVISOR_STATUS_HELPER_FATAL': os.environ.get('CHUMMER_DESIGN_SUPERVISOR_STATUS_HELPER_FATAL'),",
                    "        'BASH_ENV': os.environ.get('BASH_ENV'),",
                    "        'EA_MCP_MODEL': os.environ.get('EA_MCP_MODEL'),",
                    "        'CODEX_HOME': os.environ.get('CODEX_HOME'),",
                    "        'HOME': os.environ.get('HOME'),",
                    "        'XDG_CACHE_HOME': os.environ.get('XDG_CACHE_HOME'),",
                    "    },",
                    "}",
                    "with open(os.environ['CODEXEA_TEST_CAPTURE'], 'w', encoding='utf-8') as handle:",
                    "    json.dump(payload, handle)",
                ]
            ),
            encoding="utf-8",
        )
        self.fake_codex.chmod(self.fake_codex.stat().st_mode | stat.S_IXUSR)

    def run_shim(
        self,
        *args: str,
        extra_env: dict[str, str] | None = None,
        input_text: str | None = None,
    ) -> dict[str, object]:
        env = os.environ.copy()
        env.update(
            {
                "CODEXEA_REAL_CODEX": str(self.fake_codex),
                "CODEXEA_ROUTE_HELPER": str(self.root / "missing-route-helper.py"),
                "CODEXEA_BOOTSTRAP": "0",
                "CODEXEA_OPERATOR_GUARD_LOCAL_SHORTCUTS": "0",
                "CODEXEA_STARTUP_STATUS": "0",
                "CODEXEA_USE_LIVE_PROFILE_MODELS": "0",
                "CODEXEA_TEST_CAPTURE": str(self.capture_path),
                "EA_MCP_MODEL": "gemini-2.5-flash",
                "HOME": str(self.root),
                "OPENAI_API_KEY": "",
            }
        )
        if extra_env:
            env.update(extra_env)
        completed = subprocess.run(
            ["bash", str(SHIM_PATH), *args],
            check=False,
            env=env,
            capture_output=True,
            text=True,
            input=input_text,
        )
        payload = None
        if self.capture_path.exists():
            payload = json.loads(self.capture_path.read_text(encoding="utf-8"))
        return {"completed": completed, "payload": payload}

    def write_route_helper(self) -> Path:
        route_helper = self.root / "route-helper.py"
        route_helper.write_text(
            "\n".join(
                [
                    "#!/usr/bin/env python3",
                    "import json, os, sys",
                    "with open(os.environ['CODEXEA_ROUTE_CAPTURE'], 'w', encoding='utf-8') as handle:",
                    "    json.dump(",
                    "        {",
                    "            'argv': sys.argv[1:],",
                    "            'env': {",
                    "                'CODEXEA_ONEMIN_BILLING_TIMEOUT_SECONDS': os.environ.get('CODEXEA_ONEMIN_BILLING_TIMEOUT_SECONDS', ''),",
                    "                'CODEXEA_ONEMIN_PROBE_TIMEOUT_SECONDS': os.environ.get('CODEXEA_ONEMIN_PROBE_TIMEOUT_SECONDS', ''),",
                    "            },",
                    "        },",
                    "        handle,",
                    "    )",
                ]
            ),
            encoding="utf-8",
        )
        route_helper.chmod(route_helper.stat().st_mode | stat.S_IXUSR)
        return route_helper

    def write_fake_script(self, support_tty_wrapper: bool, capture_path: Path) -> Path:
        script = self.root / "script"
        help_lines = ["--command", "--return"] if support_tty_wrapper else ["--foo"]
        script.write_text(
            "\n".join(
                [
                    "#!/usr/bin/env bash",
                    "set -euo pipefail",
                    "capture_file=\"${SCRIPT_HELP_CAPTURE}\"",
                    "if [ \"${1-}\" = \"--help\" ]; then",
                    "  " + "\n  ".join([f'  printf "%s\\n" "{line}"' for line in help_lines]),
                    "  " + "\n  ".join([f'  printf "%s\\n" "{line}" >> "${{capture_file}}"' for line in help_lines]),
                    "  exit 0",
                    "fi",
                    'if [ -n "${capture_file:-}" ]; then',
                    '  printf "%s\\n" "$*" >> "${capture_file}"',
                    "fi",
                    "cmd=""",
                    "while [ \"$#\" -gt 0 ]; do",
                    "  if [ \"$1\" = \"--command\" ]; then",
                    "    shift",
                    "    cmd=\"${1-}\"",
                    "    break",
                    "  fi",
                    "  shift",
                    "done",
                    "if [ -n \"${cmd}\" ]; then",
                    "  eval \"${cmd}\"",
                    "fi",
                ]
            ),
            encoding="utf-8",
        )
        script.chmod(script.stat().st_mode | stat.S_IXUSR)
        return script

    def write_executable(self, path: Path, content: str) -> Path:
        path.write_text(textwrap.dedent(content).lstrip(), encoding="utf-8")
        path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        return path

    def test_easy_prompt_is_locked_to_ea_easy_without_wrapper_trace_by_default(self) -> None:
        result = self.run_shim("continue the slice")

        completed = result["completed"]
        payload = result["payload"]
        self.assertIsNotNone(payload)
        self.assertEqual(completed.returncode, 0)

        argv = payload["argv"]
        self.assertIn("exec", argv)
        self.assertIn("-c", argv)
        self.assertNotIn("", argv)
        self.assertIn('model_provider="ea"', argv)
        self.assertIn('model="ea-coder-fast"', argv)
        self.assertIn('model_reasoning_effort="low"', argv)
        self.assertNotIn("--no-alt-screen", argv)
        self.assertEqual(payload["env"]["CODEX_WRAPPER_SKIP_PROVIDER_DEFAULT"], "1")
        self.assertEqual(payload["env"]["CODEXEA_LANE"], "easy")
        self.assertEqual(payload["env"]["CODEXEA_SUBMODE"], "responses_fast")
        self.assertFalse(any("AGENTS.md" in arg for arg in argv))
        self.assertIn(
            "Trace: lane=easy provider=ea model=ea-coder-fast mode=responses next=start_exec_session",
            completed.stderr,
        )

    def test_prompt_session_does_not_inject_bootstrap_waiting_prompt(self) -> None:
        prompt_file = self.root / "bootstrap.md"
        prompt_file.write_text(
            "SENTINEL_BOOTSTRAP_WAITING_PROMPT",
            encoding="utf-8",
        )

        result = self.run_shim(
            "eta of the fleet? is it running? the shards?",
            extra_env={
                "CODEXEA_BOOTSTRAP": "1",
                "CODEXEA_BOOTSTRAP_PROMPT_FILE": str(prompt_file),
            },
        )

        completed = result["completed"]
        payload = result["payload"]
        self.assertEqual(completed.returncode, 0)
        self.assertIsNotNone(payload)
        self.assertFalse(any("SENTINEL_BOOTSTRAP_WAITING_PROMPT" in arg for arg in payload["argv"]))

    def test_prompt_session_injects_exec_trace_prompt(self) -> None:
        trace_file = self.root / "exec-trace.md"
        trace_file.write_text(
            "SENTINEL_EXEC_TRACE_PROMPT",
            encoding="utf-8",
        )

        result = self.run_shim(
            "eta of the fleet? is it running? the shards?",
            extra_env={
                "CODEXEA_BOOTSTRAP": "1",
                "CODEXEA_EXEC_TRACE_PROMPT_FILE": str(trace_file),
            },
        )

        completed = result["completed"]
        payload = result["payload"]
        self.assertEqual(completed.returncode, 0)
        self.assertIsNotNone(payload)
        self.assertIn("SENTINEL_EXEC_TRACE_PROMPT", payload["argv"][-1])
        self.assertIn("eta of the fleet? is it running? the shards?", payload["argv"][-1])

    def test_exec_git_commit_push_fast_path_commits_and_pushes_without_launching_codex(self) -> None:
        repo_root = self.root / "repo"
        remote_root = self.root / "remote.git"
        subprocess.run(
            ["git", "init", "--bare", "--initial-branch=main", str(remote_root)],
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "init", "--initial-branch=main", str(repo_root)],
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(["git", "-C", str(repo_root), "config", "user.name", "CodexEA"], check=True)
        subprocess.run(["git", "-C", str(repo_root), "config", "user.email", "codexea@example.com"], check=True)
        (repo_root / "note.txt").write_text("before\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(repo_root), "add", "note.txt"], check=True)
        subprocess.run(["git", "-C", str(repo_root), "commit", "-m", "initial"], check=True, capture_output=True, text=True)
        subprocess.run(["git", "-C", str(repo_root), "remote", "add", "origin", str(remote_root)], check=True)
        subprocess.run(["git", "-C", str(repo_root), "push", "-u", "origin", "HEAD"], check=True, capture_output=True, text=True)
        (repo_root / "note.txt").write_text("after\n", encoding="utf-8")

        prompt = (
            "Run these exact commands first:\n"
            "$ git status --short\n"
            "$ git add -A\n"
            "$ git commit -m 'Stabilize CodexEA and fleet readiness routing'\n"
            "$ git push origin HEAD\n\n"
            "After the push, report the pushed commit hash only.\n"
        )
        result = self.run_shim(
            "easy",
            "exec",
            "-C",
            str(repo_root),
            prompt,
            extra_env={
                "CODEXEA_TRACE_STARTUP": "1",
                "CODEXEA_OPERATOR_GUARD_ENABLE": "0",
            },
        )

        completed = result["completed"]
        payload = result["payload"]
        self.assertEqual(completed.returncode, 0)
        self.assertIsNone(payload)
        self.assertIn("Pushed commit ", completed.stdout)
        head = subprocess.check_output(["git", "-C", str(repo_root), "rev-parse", "HEAD"], text=True).strip()
        upstream = subprocess.check_output(["git", "-C", str(repo_root), "rev-parse", "@{u}"], text=True).strip()
        self.assertEqual(head, upstream)
        self.assertEqual(
            subprocess.check_output(["git", "-C", str(repo_root), "status", "--short"], text=True).strip(),
            "",
        )

    def test_fleet_unblock_prompt_activates_operator_guard_and_injects_operator_trace_prompt(self) -> None:
        result = self.run_shim(
            "core",
            "exec",
            "-C",
            "/docker/fleet",
            "--add-dir",
            "/docker/EA",
            "Unblock the fleet infrastructure. OODA it. Work only on CodexEA shim, EA endpoints, and the 1min manager.",
            extra_env={"CODEXEA_BOOTSTRAP": "1"},
        )

        completed = result["completed"]
        payload = result["payload"]
        self.assertEqual(completed.returncode, 0)
        self.assertIsNotNone(payload)
        active_run_dir = str(payload["env"]["CHUMMER_DESIGN_SUPERVISOR_ACTIVE_RUN_DIR"] or "").strip()
        self.assertTrue(active_run_dir)
        self.assertEqual(payload["env"]["CHUMMER_DESIGN_SUPERVISOR_STATUS_HELPER_FATAL"], "1")
        telemetry_path = Path(active_run_dir) / "TASK_LOCAL_TELEMETRY.generated.json"
        self.assertTrue(telemetry_path.exists())
        bash_env_path = Path(str(payload["env"]["BASH_ENV"] or ""))
        self.assertTrue(bash_env_path.exists())
        telemetry_payload = json.loads(telemetry_path.read_text(encoding="utf-8"))
        self.assertIn("Direct unblock scope only", telemetry_payload["summary"])
        self.assertTrue(telemetry_payload["first_commands"])
        self.assertIn("current_blocker", telemetry_payload)
        self.assertIn("live_shard_execution", telemetry_payload)
        self.assertIn("telemetry_path", telemetry_payload["live_shard_execution"])
        prompt = str(payload.get("stdin") or payload["argv"][-1])
        self.assertIn(str(telemetry_path), prompt)
        self.assertIn("Prepared repo context:", prompt)
        self.assertIn("Live shard execution context:", prompt)
        self.assertIn("Latest shard stderr excerpt:", prompt)
        self.assertIn("Latest shard prompt excerpt:", prompt)
        self.assertIn("latest_worker_telemetry:", prompt)
        self.assertIn("Bootstrap command set that was already captured:", prompt)
        self.assertIn("$ sed -n '2410,2505p' /docker/fleet/scripts/codex-shims/codexea", prompt)
        self.assertIn("git -C /docker/fleet status --short -- scripts/codex-shims/codexea scripts/codex-shims/python3", prompt)
        self.assertIn("repeated probes will hard-fail this operator run", prompt)
        self.assertNotIn("Run these exact commands first:", prompt)
        self.assertIn('mcp_servers={}', payload["argv"])
        self.assertNotIn("--json", payload["argv"])

    def test_fleet_unblock_stdin_exec_activates_operator_guard(self) -> None:
        result = self.run_shim(
            "core",
            "exec",
            "-C",
            "/docker/fleet",
            "--add-dir",
            "/docker/EA",
            "-",
            extra_env={"CODEXEA_BOOTSTRAP": "1"},
            input_text=(
                "Unblock the fleet infrastructure. OODA it. "
                "Work only on CodexEA shim, EA endpoints, and the 1min manager."
            ),
        )

        completed = result["completed"]
        payload = result["payload"]
        self.assertEqual(completed.returncode, 0)
        self.assertIsNotNone(payload)
        active_run_dir = str(payload["env"]["CHUMMER_DESIGN_SUPERVISOR_ACTIVE_RUN_DIR"] or "").strip()
        self.assertTrue(active_run_dir)
        self.assertEqual(payload["env"]["CHUMMER_DESIGN_SUPERVISOR_STATUS_HELPER_FATAL"], "1")
        telemetry_path = Path(active_run_dir) / "TASK_LOCAL_TELEMETRY.generated.json"
        self.assertTrue(telemetry_path.exists())
        self.assertIn("Unblock the fleet infrastructure. OODA it.", payload["stdin"])
        self.assertIn("Work only on CodexEA shim, EA endpoints, and the 1min manager.", payload["stdin"])
        self.assertIn("Operator-prepared fleet unblock context:", payload["stdin"])
        self.assertIn("Original operator ask:", payload["stdin"])
        self.assertIn(str(telemetry_path), payload["stdin"])
        self.assertIn("Bootstrap command set that was already captured:", payload["stdin"])
        self.assertNotIn("Run these exact commands first:", payload["stdin"])

    def test_readiness_remedy_prompt_does_not_misclassify_as_fleet_unblock_operator_guard(self) -> None:
        prompt_text = (
            "Remedy the remaining flagship readiness blockers until they are closed or you hit one exact blocker. "
            "Current remaining readiness blockers: desktop_client, mobile_play_shell, "
            "ui_kit_and_flagship_polish, media_artifacts. "
            "If the blocker is in CodexEA/EA/shim infrastructure, patch that path. "
            "If the blocker is in product proof or release artifacts, do that work instead. "
            "Do not wander into unrelated backlog."
        )

        result = self.run_shim(
            "core",
            "exec",
            "-C",
            "/docker/fleet",
            "--add-dir",
            "/docker/EA",
            prompt_text,
            extra_env={"CODEXEA_BOOTSTRAP": "1"},
        )

        completed = result["completed"]
        payload = result["payload"]
        self.assertEqual(completed.returncode, 0)
        self.assertIsNotNone(payload)
        self.assertFalse(str(payload["env"]["CHUMMER_DESIGN_SUPERVISOR_ACTIVE_RUN_DIR"] or "").strip())
        self.assertNotIn("Operator-prepared fleet unblock context:", payload["argv"][-1])
        self.assertIn("desktop_client", payload["argv"][-1])
        self.assertIn("media_artifacts", payload["argv"][-1])

    def test_clean_exec_retries_transport_failure_when_last_message_is_missing(self) -> None:
        output_path = self.root / "last_message.txt"
        attempt_path = self.root / "attempt.txt"
        renderer = self.write_executable(
            self.root / "renderer.py",
            """
            #!/usr/bin/env python3
            import sys
            sys.stdin.read()
            """,
        )
        fake_codex = self.write_executable(
            self.root / "codex-transport.py",
            f"""
            #!/usr/bin/env python3
            import pathlib
            import sys

            output_path = ""
            argv = sys.argv[1:]
            if "exec" not in argv:
                raise SystemExit(0)
            attempt_path = pathlib.Path({str(attempt_path)!r})
            attempt = 0
            if attempt_path.exists():
                attempt = int((attempt_path.read_text(encoding="utf-8") or "0").strip() or "0")
            attempt += 1
            attempt_path.write_text(str(attempt), encoding="utf-8")
            for index, arg in enumerate(argv):
                if arg in ("-o", "--output-last-message") and index + 1 < len(argv):
                    output_path = argv[index + 1]
                    break

            if attempt == 1:
                print("ERROR: Reconnecting... 1/2", file=sys.stderr)
                print("Trace: provider=liz transport=reconnecting attempt=1/2 elapsed=0s", file=sys.stderr)
                print(
                    "ERROR: stream disconnected before completion: error sending request for url "
                    "(http://host.docker.internal:8090/v1/responses)",
                    file=sys.stderr,
                )
                raise SystemExit(0)

            if output_path:
                pathlib.Path(output_path).write_text(
                    "What shipped: ok\\nWhat remains: none\\nExact blocker: none\\n",
                    encoding="utf-8",
                )
            print('{{"type":"message","message":{{"role":"assistant","content":[{{"type":"output_text","text":"ok"}}]}}}}')
            """,
        )

        result = self.run_shim(
            "core",
            "exec",
            "-o",
            str(output_path),
            "Reply with exactly ok.",
            extra_env={
                "CODEXEA_REAL_CODEX": str(fake_codex),
                "CODEXEA_EXEC_JSON_RENDERER": str(renderer),
                "CODEXEA_OPERATOR_GUARD_ACTIVE": "1",
                "CODEXEA_OPERATOR_GUARD_TRANSPORT_RETRY": "1",
                "CODEXEA_OPERATOR_GUARD_TRANSPORT_RETRY_SLEEP_SECONDS": "0",
            },
        )

        completed = result["completed"]
        self.assertEqual(completed.returncode, 0)
        self.assertIn("retrying clean-exec transport failure", completed.stderr)
        self.assertEqual(attempt_path.read_text(encoding="utf-8").strip(), "2")
        self.assertIn("What shipped: ok", output_path.read_text(encoding="utf-8"))

    def test_fleet_unblock_prompt_filters_trace_only_blocker_lines_from_live_shard_snapshot(self) -> None:
        fleet_root = self.root / "fleet"
        state_root = fleet_root / "state" / "chummer_design_supervisor"
        run_dir = state_root / "shard-7" / "runs" / "20260429T111700Z-shard-7"
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "worker.stderr.log").write_text(
            "\n".join(
                [
                    "Trace: lane=review_light waiting for upstream response (total_duration=0s)",
                    "[fleet-supervisor] provider-health preflight left no routable direct lanes: core:onemin:unavailable",
                ]
            ),
            encoding="utf-8",
        )
        (run_dir / "WORKER_EXEC_TRACE_PROMPT.md").write_text("worker prompt", encoding="utf-8")
        (run_dir / "TASK_LOCAL_TELEMETRY.generated.json").write_text(
            json.dumps({"summary": "demo", "first_commands": [], "source_paths": []}),
            encoding="utf-8",
        )
        (state_root / "state.json").write_text(
            json.dumps(
                {
                    "active_runs_count": 1,
                    "updated_at": "2026-04-29T11:17:00Z",
                    "eta": {
                        "remaining_open_milestones": 6,
                        "remaining_in_progress_milestones": 6,
                        "eta_human": "1d-2.5d after unblock",
                    },
                }
            ),
            encoding="utf-8",
        )

        result = self.run_shim(
            "core",
            "exec",
            "Unblock the fleet. OODA it. Patch only the codexea shim, EA endpoints, and the 1min manager.",
            extra_env={
                "CODEXEA_BOOTSTRAP": "1",
                "CODEXEA_OPERATOR_GUARD_FLEET_ROOT": str(fleet_root),
            },
        )

        completed = result["completed"]
        payload = result["payload"]
        self.assertEqual(completed.returncode, 0)
        self.assertIsNotNone(payload)
        active_run_dir = str(payload["env"]["CHUMMER_DESIGN_SUPERVISOR_ACTIVE_RUN_DIR"] or "").strip()
        telemetry_path = Path(active_run_dir) / "TASK_LOCAL_TELEMETRY.generated.json"
        telemetry_payload = json.loads(telemetry_path.read_text(encoding="utf-8"))
        self.assertEqual(
            telemetry_payload["current_blocker"],
            "[fleet-supervisor] provider-health preflight left no routable direct lanes: core:onemin:unavailable",
        )
        prompt = str(payload.get("stdin") or payload["argv"][-1])
        self.assertIn(
            "- current_blocker: [fleet-supervisor] provider-health preflight left no routable direct lanes: core:onemin:unavailable",
            prompt,
        )
        self.assertNotIn("current_blocker: Trace:", prompt)

    def test_fleet_unblock_prompt_scans_full_worker_stderr_for_real_blocker(self) -> None:
        fleet_root = self.root / "fleet"
        state_root = fleet_root / "state" / "chummer_design_supervisor"
        run_dir = state_root / "shard-8" / "runs" / "20260429T112300Z-shard-8"
        run_dir.mkdir(parents=True, exist_ok=True)
        noisy_lines = [f"[fleet-supervisor] attempt {i}/25 account=acct-ea-jury owner= model=ea-coder-hard-batch" for i in range(1, 23)]
        noisy_lines.append("[fleet-supervisor] provider-health preflight left no routable direct lanes: core:onemin:unavailable")
        (run_dir / "worker.stderr.log").write_text("\n".join(noisy_lines), encoding="utf-8")
        (run_dir / "WORKER_EXEC_TRACE_PROMPT.md").write_text("worker prompt", encoding="utf-8")
        (run_dir / "TASK_LOCAL_TELEMETRY.generated.json").write_text(
            json.dumps({"summary": "demo", "first_commands": [], "source_paths": []}),
            encoding="utf-8",
        )
        (state_root / "state.json").write_text(
            json.dumps(
                {
                    "active_runs_count": 0,
                    "updated_at": "2026-04-29T11:23:00Z",
                    "eta": {
                        "remaining_open_milestones": 6,
                        "remaining_in_progress_milestones": 6,
                        "eta_human": "1d-2.5d after unblock",
                    },
                }
            ),
            encoding="utf-8",
        )

        result = self.run_shim(
            "core",
            "exec",
            "Unblock the fleet. OODA it. Patch only the codexea shim, EA endpoints, and the 1min manager.",
            extra_env={
                "CODEXEA_BOOTSTRAP": "1",
                "CODEXEA_OPERATOR_GUARD_FLEET_ROOT": str(fleet_root),
            },
        )

        completed = result["completed"]
        payload = result["payload"]
        self.assertEqual(completed.returncode, 0)
        self.assertIsNotNone(payload)
        active_run_dir = str(payload["env"]["CHUMMER_DESIGN_SUPERVISOR_ACTIVE_RUN_DIR"] or "").strip()
        telemetry_path = Path(active_run_dir) / "TASK_LOCAL_TELEMETRY.generated.json"
        telemetry_payload = json.loads(telemetry_path.read_text(encoding="utf-8"))
        self.assertEqual(
            telemetry_payload["current_blocker"],
            "[fleet-supervisor] provider-health preflight left no routable direct lanes: core:onemin:unavailable",
        )
        prompt = str(payload.get("stdin") or payload["argv"][-1])
        self.assertIn(
            "[fleet-supervisor] provider-health preflight left no routable direct lanes: core:onemin:unavailable",
            prompt,
        )

    def test_fleet_unblock_prompt_prefers_newer_real_blocker_run_over_latest_attempt_only_run(self) -> None:
        fleet_root = self.root / "fleet"
        state_root = fleet_root / "state" / "chummer_design_supervisor"
        blocker_run_dir = state_root / "shard-4" / "runs" / "20260429T113513Z-shard-4"
        attempt_run_dir = state_root / "shard-9" / "runs" / "20260429T113540Z-shard-9"
        blocker_run_dir.mkdir(parents=True, exist_ok=True)
        attempt_run_dir.mkdir(parents=True, exist_ok=True)
        (blocker_run_dir / "worker.stderr.log").write_text(
            "\n".join(
                [
                    "[fleet-supervisor] no runnable full routed accounts; trying anonymous full-lane fallback first",
                    "[fleet-supervisor] provider-health preflight left no routable direct lanes: core:onemin:unavailable",
                ]
            ),
            encoding="utf-8",
        )
        (attempt_run_dir / "worker.stderr.log").write_text(
            "[fleet-supervisor] attempt 1/7 account=acct-ea-jury owner= model=ea-coder-hard-batch\n",
            encoding="utf-8",
        )
        (blocker_run_dir / "WORKER_EXEC_TRACE_PROMPT.md").write_text("blocker prompt", encoding="utf-8")
        (attempt_run_dir / "WORKER_EXEC_TRACE_PROMPT.md").write_text("attempt prompt", encoding="utf-8")
        (blocker_run_dir / "TASK_LOCAL_TELEMETRY.generated.json").write_text(
            json.dumps({"summary": "blocker", "first_commands": [], "source_paths": []}),
            encoding="utf-8",
        )
        (attempt_run_dir / "TASK_LOCAL_TELEMETRY.generated.json").write_text(
            json.dumps({"summary": "attempt", "first_commands": [], "source_paths": []}),
            encoding="utf-8",
        )
        blocker_mtime = 1_777_462_200
        attempt_mtime = blocker_mtime + 90
        os.utime(blocker_run_dir / "worker.stderr.log", (blocker_mtime, blocker_mtime))
        os.utime(blocker_run_dir / "WORKER_EXEC_TRACE_PROMPT.md", (blocker_mtime, blocker_mtime))
        os.utime(blocker_run_dir / "TASK_LOCAL_TELEMETRY.generated.json", (blocker_mtime, blocker_mtime))
        os.utime(attempt_run_dir / "worker.stderr.log", (attempt_mtime, attempt_mtime))
        os.utime(attempt_run_dir / "WORKER_EXEC_TRACE_PROMPT.md", (attempt_mtime, attempt_mtime))
        os.utime(attempt_run_dir / "TASK_LOCAL_TELEMETRY.generated.json", (attempt_mtime, attempt_mtime))
        (state_root / "state.json").write_text(
            json.dumps(
                {
                    "active_runs_count": 0,
                    "updated_at": "2026-04-29T11:35:40Z",
                    "eta": {
                        "remaining_open_milestones": 6,
                        "remaining_in_progress_milestones": 6,
                        "eta_human": "1d-2.5d after unblock",
                    },
                }
            ),
            encoding="utf-8",
        )

        result = self.run_shim(
            "core",
            "exec",
            "Unblock the fleet. OODA it. Patch only the codexea shim, EA endpoints, and the 1min manager.",
            extra_env={
                "CODEXEA_BOOTSTRAP": "1",
                "CODEXEA_OPERATOR_GUARD_FLEET_ROOT": str(fleet_root),
            },
        )

        completed = result["completed"]
        payload = result["payload"]
        self.assertEqual(completed.returncode, 0)
        self.assertIsNotNone(payload)
        active_run_dir = str(payload["env"]["CHUMMER_DESIGN_SUPERVISOR_ACTIVE_RUN_DIR"] or "").strip()
        telemetry_path = Path(active_run_dir) / "TASK_LOCAL_TELEMETRY.generated.json"
        telemetry_payload = json.loads(telemetry_path.read_text(encoding="utf-8"))
        self.assertEqual(
            telemetry_payload["current_blocker"],
            "[fleet-supervisor] provider-health preflight left no routable direct lanes: core:onemin:unavailable",
        )
        self.assertEqual(
            telemetry_payload["live_shard_execution"]["run_id"],
            blocker_run_dir.name,
        )
        self.assertEqual(
            telemetry_payload["live_shard_execution"]["stderr_path"],
            str(blocker_run_dir / "worker.stderr.log"),
        )

    def test_unblock_prompt_auto_promotes_plain_exec_to_core_lane(self) -> None:
        result = self.run_shim(
            "exec",
            "Unblock CodexEA itself. OODA it. Work only on the CodexEA shim, EA endpoints, and the 1min manager.",
            extra_env={"CODEXEA_BOOTSTRAP": "1"},
        )

        completed = result["completed"]
        payload = result["payload"]
        self.assertEqual(completed.returncode, 0)
        self.assertIsNotNone(payload)
        self.assertTrue(payload["env"]["CHUMMER_DESIGN_SUPERVISOR_ACTIVE_RUN_DIR"])
        self.assertEqual(payload["env"]["CODEXEA_LANE"], "core")
        self.assertEqual(payload["env"]["CODEXEA_SUBMODE"], "responses_core")

    def test_unblock_diagnostic_prompt_preserves_explicit_core_lane(self) -> None:
        result = self.run_shim(
            "core",
            "exec",
            "Investigate why EA global 1min aggregate reports ready_account_count=0 while Fleet is running 13/13 productive. OODA the fleet and patch only CodexEA shim, EA endpoints, or the 1min manager.",
            extra_env={"CODEXEA_BOOTSTRAP": "1", "CODEXEA_TRACE_STARTUP": "1"},
        )

        completed = result["completed"]
        payload = result["payload"]
        self.assertEqual(completed.returncode, 0)
        self.assertIsNotNone(payload)
        self.assertTrue(payload["env"]["CHUMMER_DESIGN_SUPERVISOR_ACTIVE_RUN_DIR"])
        self.assertEqual(payload["env"]["CODEXEA_LANE"], "core")
        self.assertEqual(payload["env"]["CODEXEA_SUBMODE"], "responses_core")
        self.assertIn('model="ea-coder-hard"', payload["argv"])
        self.assertIn("Operator-prepared fleet unblock context:", str(payload.get("stdin") or ""))
        self.assertIn(
            "Trace: lane=core provider=ea model=ea-coder-hard mode=responses next=start_exec_session",
            completed.stderr,
        )

    def test_unblock_diagnostic_plain_exec_still_auto_demotes_to_easy_lane(self) -> None:
        result = self.run_shim(
            "exec",
            "Investigate why EA global 1min aggregate reports ready_account_count=0 while Fleet is running 13/13 productive. OODA the fleet and patch only CodexEA shim, EA endpoints, or the 1min manager.",
            extra_env={"CODEXEA_BOOTSTRAP": "1", "CODEXEA_TRACE_STARTUP": "1"},
        )

        completed = result["completed"]
        payload = result["payload"]
        self.assertEqual(completed.returncode, 0)
        self.assertIsNotNone(payload)
        self.assertTrue(payload["env"]["CHUMMER_DESIGN_SUPERVISOR_ACTIVE_RUN_DIR"])
        self.assertEqual(payload["env"]["CODEXEA_LANE"], "easy")
        self.assertEqual(payload["env"]["CODEXEA_SUBMODE"], "responses_fast")
        self.assertIn('model="ea-coder-fast"', payload["argv"])

    def test_backlog_audit_prompt_activates_operator_guard_and_disables_mcp(self) -> None:
        prompt_text = (
            "Audit whether every remaining milestone or task needed to complete the "
            "Chummer6 flagship design is already represented in the Fleet backlog. "
            "If not, add the gaps to the backlog and distinguish design gaps from "
            "release-proof or operational gaps."
        )

        result = self.run_shim(
            "exec",
            prompt_text,
            extra_env={"CODEXEA_BOOTSTRAP": "1", "CODEXEA_DEBUG": "1"},
        )

        completed = result["completed"]
        payload = result["payload"]
        self.assertEqual(completed.returncode, 0)
        self.assertIsNotNone(payload)
        active_run_dir = str(payload["env"]["CHUMMER_DESIGN_SUPERVISOR_ACTIVE_RUN_DIR"] or "").strip()
        self.assertTrue(active_run_dir)
        telemetry_path = Path(active_run_dir) / "TASK_LOCAL_TELEMETRY.generated.json"
        self.assertTrue(telemetry_path.exists())
        telemetry_payload = json.loads(telemetry_path.read_text(encoding="utf-8"))
        self.assertEqual(telemetry_payload["guard_mode"], "backlog_audit")
        self.assertIn("backlog audit", telemetry_payload["summary"].lower())
        self.assertTrue(telemetry_payload["first_commands"])
        self.assertEqual(payload["env"]["CODEXEA_LANE"], "core")
        self.assertEqual(payload["env"]["CODEXEA_SUBMODE"], "responses_core")
        prompt = str(payload.get("stdin") or payload["argv"][-1])
        self.assertIn("Operator-prepared backlog audit context:", prompt)
        self.assertIn("Run these exact commands first:", prompt)
        self.assertIn("Do not patch EA routing, CodexEA runtime, or shard execution paths", prompt)
        self.assertIn(str(telemetry_path), prompt)
        self.assertNotIn("Prepared repo context:", prompt)
        self.assertIn('mcp_servers={}', payload["argv"])

    def test_generic_fleet_unblock_prompt_does_not_activate_infra_operator_guard(self) -> None:
        prompt_text = (
            "OODA the fleet and unblock it. Fix the current blocker in /docker/fleet and verify it."
        )

        result = self.run_shim(
            "exec",
            prompt_text,
            extra_env={"CODEXEA_BOOTSTRAP": "1", "CODEXEA_DEBUG": "1"},
        )

        completed = result["completed"]
        payload = result["payload"]
        self.assertEqual(completed.returncode, 0)
        self.assertIsNotNone(payload)
        self.assertFalse(str(payload["env"]["CHUMMER_DESIGN_SUPERVISOR_ACTIVE_RUN_DIR"] or "").strip())
        prompt = str(payload.get("stdin") or payload["argv"][-1])
        self.assertNotIn("Operator-prepared backlog audit context:", prompt)
        self.assertNotIn("Operator-prepared fleet unblock context:", prompt)
        self.assertIn("OODA the fleet and unblock it.", prompt)

    def test_preconfigured_codex_home_is_created_before_launch(self) -> None:
        codex_home = self.root / "missing-codex-home"

        result = self.run_shim(
            "exec",
            "Reply with exactly ok.",
            extra_env={"CODEX_HOME": str(codex_home)},
        )

        completed = result["completed"]
        payload = result["payload"]
        self.assertEqual(completed.returncode, 0)
        self.assertIsNotNone(payload)
        self.assertTrue(codex_home.is_dir())
        self.assertEqual(payload["env"]["CODEX_HOME"], str(codex_home))

    def test_responses_mode_defaults_to_single_stream_retry(self) -> None:
        result = self.run_shim(
            "exec",
            "Reply with exactly ok.",
        )

        completed = result["completed"]
        payload = result["payload"]
        self.assertEqual(completed.returncode, 0)
        self.assertIsNotNone(payload)
        self.assertIn("model_providers.ea.stream_max_retries=1", payload["argv"])

    def test_gap_audit_prompt_activates_gap_audit_operator_guard(self) -> None:
        prompt_text = (
            "Spawn CodexEA in debug mode and find gaps in both the design, the milestones, "
            "the shards implementing them, and the workflow to gate the result, with special "
            "attention to visual parity and sub-workflow behavior."
        )

        result = self.run_shim(
            "exec",
            prompt_text,
            extra_env={"CODEXEA_BOOTSTRAP": "1", "CODEXEA_DEBUG": "1"},
        )

        completed = result["completed"]
        payload = result["payload"]
        self.assertEqual(completed.returncode, 0)
        self.assertIsNotNone(payload)
        active_run_dir = str(payload["env"]["CHUMMER_DESIGN_SUPERVISOR_ACTIVE_RUN_DIR"] or "").strip()
        self.assertTrue(active_run_dir)
        telemetry_path = Path(active_run_dir) / "TASK_LOCAL_TELEMETRY.generated.json"
        self.assertTrue(telemetry_path.exists())
        telemetry_payload = json.loads(telemetry_path.read_text(encoding="utf-8"))
        self.assertEqual(telemetry_payload["guard_mode"], "gap_audit")
        self.assertIn("gap audit", telemetry_payload["summary"].lower())
        self.assertEqual(len(telemetry_payload["first_commands"]), 1)
        self.assertIn("codexea_gap_audit_probe.py", telemetry_payload["first_commands"][0])
        self.assertEqual(payload["env"]["CODEXEA_LANE"], "easy")
        self.assertEqual(payload["env"]["CODEXEA_SUBMODE"], "responses_fast")
        prompt = str(payload.get("stdin") or payload["argv"][-1])
        self.assertIn("Operator-prepared gap audit context:", prompt)
        self.assertIn("Prepared repo context:", prompt)
        self.assertIn("visual parity", prompt)
        self.assertNotIn("Operator-prepared fleet unblock context:", prompt)
        self.assertIn("clean_exec=0", completed.stderr)

    def test_gap_fix_prompt_activates_gap_fix_operator_guard(self) -> None:
        prompt_text = "Make CodexEA fix the things found in the audit around parity, workflow gates, and stale proof."

        result = self.run_shim(
            "exec",
            prompt_text,
            extra_env={"CODEXEA_BOOTSTRAP": "1", "CODEXEA_DEBUG": "1"},
        )

        completed = result["completed"]
        payload = result["payload"]
        self.assertEqual(completed.returncode, 0)
        self.assertIsNotNone(payload)
        active_run_dir = str(payload["env"]["CHUMMER_DESIGN_SUPERVISOR_ACTIVE_RUN_DIR"] or "").strip()
        self.assertTrue(active_run_dir)
        telemetry_path = Path(active_run_dir) / "TASK_LOCAL_TELEMETRY.generated.json"
        telemetry_payload = json.loads(telemetry_path.read_text(encoding="utf-8"))
        self.assertEqual(telemetry_payload["guard_mode"], "gap_fix")
        self.assertIn("gap fix", telemetry_payload["summary"].lower())
        self.assertEqual(len(telemetry_payload["first_commands"]), 1)
        self.assertIn("codexea_gap_fix_workflow.py", telemetry_payload["first_commands"][0])
        self.assertEqual(payload["env"]["CODEXEA_LANE"], "easy")
        self.assertEqual(payload["env"]["CODEXEA_SUBMODE"], "responses_fast")
        prompt = str(payload.get("stdin") or payload["argv"][-1])
        self.assertIn("Operator-prepared gap fix context:", prompt)
        self.assertNotIn("Prepared repo context:", prompt)
        self.assertIn("Run these exact commands first:", prompt)
        self.assertIn("probe_kind=gap_fix", prompt)
        self.assertIn("do not run `git status`", prompt)
        self.assertIn("clean_exec=0", completed.stderr)

    def test_repo_local_visual_parity_gap_prompt_activates_gap_audit_operator_guard(self) -> None:
        prompt_text = (
            "Find gaps in the design, the milestones, the shards implementing them, and the workflow "
            "that gates the result. Focus especially on visual parity across sub-workflows and behavior "
            "mismatches versus the repo-described product."
        )

        result = self.run_shim(
            "exec",
            prompt_text,
            extra_env={"CODEXEA_BOOTSTRAP": "1", "CODEXEA_DEBUG": "1"},
        )

        completed = result["completed"]
        payload = result["payload"]
        self.assertEqual(completed.returncode, 0)
        self.assertIsNotNone(payload)
        telemetry_path = Path(str(payload["env"]["CHUMMER_DESIGN_SUPERVISOR_ACTIVE_RUN_DIR"]).strip()) / "TASK_LOCAL_TELEMETRY.generated.json"
        telemetry_payload = json.loads(telemetry_path.read_text(encoding="utf-8"))
        self.assertEqual(telemetry_payload["guard_mode"], "gap_audit")
        prompt = str(payload.get("stdin") or payload["argv"][-1])
        self.assertIn("Operator-prepared gap audit context:", prompt)
        self.assertIn("visual parity", prompt)

    def test_every_ui_element_prompt_activates_ui_parity_audit_operator_guard(self) -> None:
        prompt_text = (
            "Audit Chummer6 against Chummer5A like a human tester, almost pixel level. "
            "List every UI element, every subdialog, and every visible workflow surface with yes/no parity."
        )

        result = self.run_shim(
            "exec",
            prompt_text,
            extra_env={"CODEXEA_BOOTSTRAP": "1", "CODEXEA_DEBUG": "1"},
        )

        completed = result["completed"]
        payload = result["payload"]
        self.assertEqual(completed.returncode, 0)
        self.assertIsNotNone(payload)
        telemetry_path = Path(str(payload["env"]["CHUMMER_DESIGN_SUPERVISOR_ACTIVE_RUN_DIR"]).strip()) / "TASK_LOCAL_TELEMETRY.generated.json"
        telemetry_payload = json.loads(telemetry_path.read_text(encoding="utf-8"))
        self.assertEqual(telemetry_payload["guard_mode"], "ui_parity_audit")
        self.assertIn("ui parity audit", telemetry_payload["summary"].lower())
        self.assertEqual(len(telemetry_payload["first_commands"]), 1)
        self.assertIn("codexea_ui_parity_audit_probe.py", telemetry_payload["first_commands"][0])
        self.assertEqual(payload["env"]["CODEXEA_LANE"], "easy")
        self.assertEqual(payload["env"]["CODEXEA_SUBMODE"], "responses_fast")
        prompt = str(payload.get("stdin") or payload["argv"][-1])
        self.assertIn("Operator-prepared UI parity audit context:", prompt)
        self.assertIn("probe_kind=ui_parity_audit", prompt)
        self.assertIn("clean_exec=0", completed.stderr)

    def test_vision_lost_potential_prompt_activates_vision_audit_operator_guard(self) -> None:
        prompt_text = (
            "Analyze Chummer6 design for lost potential for our vision of the product. "
            "What would users want or miss? Also analyze missed integration potential of my LTDs or not yet purchased LTDs."
        )

        result = self.run_shim(
            "exec",
            prompt_text,
            extra_env={"CODEXEA_BOOTSTRAP": "1", "CODEXEA_DEBUG": "1"},
        )

        completed = result["completed"]
        payload = result["payload"]
        self.assertEqual(completed.returncode, 0)
        self.assertIsNotNone(payload)
        telemetry_path = Path(str(payload["env"]["CHUMMER_DESIGN_SUPERVISOR_ACTIVE_RUN_DIR"]).strip()) / "TASK_LOCAL_TELEMETRY.generated.json"
        telemetry_payload = json.loads(telemetry_path.read_text(encoding="utf-8"))
        self.assertEqual(telemetry_payload["guard_mode"], "vision_audit")
        self.assertIn("vision audit", telemetry_payload["summary"].lower())
        self.assertEqual(len(telemetry_payload["first_commands"]), 1)
        self.assertIn("codexea_vision_audit_probe.py", telemetry_payload["first_commands"][0])
        self.assertEqual(payload["env"]["CODEXEA_LANE"], "easy")
        self.assertEqual(payload["env"]["CODEXEA_SUBMODE"], "responses_fast")
        prompt = str(payload.get("stdin") or payload["argv"][-1])
        self.assertIn("Operator-prepared vision audit context:", prompt)
        self.assertIn("probe_kind=vision_audit", prompt)
        self.assertIn("clean_exec=0", completed.stderr)

    def test_non_vision_operator_guard_mode_does_not_trigger_vision_shortcut_from_stdin_context(self) -> None:
        result = self.run_shim(
            "exec",
            "Refresh current 1min billing credits and inspect stale depleted-probe routing.",
            extra_env={
                "CODEXEA_OPERATOR_GUARD_ACTIVE": "1",
                "CODEXEA_OPERATOR_GUARD_MODE": "unblock",
                "CODEXEA_OPERATOR_GUARD_LOCAL_SHORTCUTS": "1",
                "CODEXEA_STDIN_PROMPT": "probe_kind=vision_audit",
            },
        )

        completed = result["completed"]
        payload = result["payload"]
        self.assertEqual(completed.returncode, 0)
        self.assertIsNotNone(payload)
        self.assertNotIn("Vision audit result:", completed.stdout)

    def test_full_parity_build_prompt_activates_parity_build_operator_guard(self) -> None:
        prompt_text = "OODA and make CodexEA materialize a full parity build."

        result = self.run_shim(
            "exec",
            prompt_text,
            extra_env={"CODEXEA_BOOTSTRAP": "1", "CODEXEA_DEBUG": "1"},
        )

        completed = result["completed"]
        payload = result["payload"]
        self.assertEqual(completed.returncode, 0)
        self.assertIsNotNone(payload)
        telemetry_path = Path(str(payload["env"]["CHUMMER_DESIGN_SUPERVISOR_ACTIVE_RUN_DIR"]).strip()) / "TASK_LOCAL_TELEMETRY.generated.json"
        telemetry_payload = json.loads(telemetry_path.read_text(encoding="utf-8"))
        self.assertEqual(telemetry_payload["guard_mode"], "parity_build")
        self.assertIn("parity build", telemetry_payload["summary"].lower())
        self.assertEqual(len(telemetry_payload["first_commands"]), 1)
        self.assertIn("codexea_parity_build_workflow.py", telemetry_payload["first_commands"][0])
        self.assertEqual(payload["env"]["CODEXEA_LANE"], "easy")
        self.assertEqual(payload["env"]["CODEXEA_SUBMODE"], "responses_fast")
        prompt = str(payload.get("stdin") or payload["argv"][-1])
        self.assertIn("Operator-prepared parity build context:", prompt)
        self.assertIn("probe_kind=parity_build", prompt)
        self.assertIn("clean_exec=0", completed.stderr)

    def test_true_chummer5a_parity_materialize_prompt_activates_parity_build_operator_guard(self) -> None:
        prompt_text = (
            "OODA and materialize true Chummer5A parity end to end. "
            "Promote it into the live portal, hub registry, and UI release roots, "
            "then refresh proofs against the promoted bytes."
        )

        result = self.run_shim(
            "exec",
            prompt_text,
            extra_env={"CODEXEA_BOOTSTRAP": "1", "CODEXEA_DEBUG": "1"},
        )

        completed = result["completed"]
        payload = result["payload"]
        self.assertEqual(completed.returncode, 0)
        self.assertIsNotNone(payload)
        telemetry_path = Path(str(payload["env"]["CHUMMER_DESIGN_SUPERVISOR_ACTIVE_RUN_DIR"]).strip()) / "TASK_LOCAL_TELEMETRY.generated.json"
        telemetry_payload = json.loads(telemetry_path.read_text(encoding="utf-8"))
        self.assertEqual(telemetry_payload["guard_mode"], "parity_build")
        prompt = str(payload.get("stdin") or payload["argv"][-1])
        self.assertIn("Operator-prepared parity build context:", prompt)

    def test_prompt_session_emits_waiting_trace_while_provider_is_quiet(self) -> None:
        result = self.run_shim(
            "eta of the fleet? is it running? the shards?",
            extra_env={
                "CODEXEA_TRACE_STARTUP": "1",
                "CODEXEA_TRACE_HEARTBEAT_SECONDS": "0.1",
                "CODEXEA_TEST_FAKE_CODEX_SLEEP": "0.25",
            },
        )

        completed = result["completed"]
        self.assertEqual(completed.returncode, 0)
        self.assertIn("Trace: lane=easy waiting for upstream response", completed.stderr)

    def test_debug_mode_emits_route_and_launch_traces(self) -> None:
        result = self.run_shim(
            "continue the slice",
            extra_env={"CODEXEA_DEBUG": "1"},
        )

        completed = result["completed"]
        self.assertEqual(completed.returncode, 0)
        self.assertIn("Trace: lane=easy debug=route requested=easy effective=easy mode=responses", completed.stderr)
        self.assertIn("Trace: lane=easy debug=launch command=", completed.stderr)
        debug_log = self.root / ".cache" / "codexea" / "debug.log"
        self.assertTrue(debug_log.exists())
        log_text = debug_log.read_text(encoding="utf-8")
        self.assertIn("Trace: lane=easy debug=route requested=easy effective=easy mode=responses", log_text)

    def test_debug_mode_emits_telemetry_shortcut_traces(self) -> None:
        route_helper = self.root / "route-helper.py"
        route_helper.write_text(
            "\n".join(
                [
                    "#!/usr/bin/env python3",
                    "import sys",
                    "if len(sys.argv) > 1 and sys.argv[1] == '--telemetry-answer':",
                    "    print('fleet telemetry ok')",
                    "    raise SystemExit(0)",
                    "raise SystemExit(10)",
                ]
            ),
            encoding="utf-8",
        )
        route_helper.chmod(route_helper.stat().st_mode | stat.S_IXUSR)

        result = self.run_shim(
            "eta? active shards?",
            extra_env={
                "CODEXEA_DEBUG": "1",
                "CODEXEA_ROUTE_HELPER": str(route_helper),
            },
        )

        completed = result["completed"]
        self.assertEqual(completed.returncode, 0)
        self.assertEqual(completed.stdout.strip(), "fleet telemetry ok")
        self.assertIsNone(result["payload"])
        self.assertIn("Trace: lane=easy debug=telemetry probe source=prompt", completed.stderr)
        self.assertIn("Trace: lane=easy debug=telemetry shortcut source=prompt lane=easy rc=0", completed.stderr)

    def test_noarg_non_tty_stdin_is_treated_as_prompt_session(self) -> None:
        result = self.run_shim(
            extra_env={"CODEXEA_BOOTSTRAP": "1"},
            input_text="fleet stdin prompt",
        )

        completed = result["completed"]
        payload = result["payload"]
        self.assertEqual(completed.returncode, 0)
        self.assertIsNotNone(payload)
        self.assertIn("fleet stdin prompt", payload["argv"][-1])
        self.assertNotIn("--interactive", payload["argv"])
        self.assertIn("--skip-git-repo-check", payload["argv"])

    def test_interactive_flag_non_tty_without_prompt_falls_back_to_exec(self) -> None:
        result = self.run_shim(
            "--interactive",
            extra_env={
                "CODEXEA_TRACE_STARTUP": "1",
                "CODEXEA_TRACE_HEARTBEAT_SECONDS": "0.1",
                "CODEXEA_TEST_FAKE_CODEX_SLEEP": "0.05",
            },
        )

        completed = result["completed"]
        payload = result["payload"]
        self.assertEqual(completed.returncode, 0)
        self.assertIsNotNone(payload)
        self.assertIn("exec", payload["argv"])
        self.assertNotIn("--interactive", payload["argv"])
        self.assertIn('model_provider="ea"', payload["argv"])
        self.assertIn(f'model="{DEFAULT_EASY_INTERACTIVE_MODEL}"', payload["argv"])
        self.assertIn(
            f"Trace: lane=easy provider=ea model={DEFAULT_EASY_INTERACTIVE_MODEL} mode=responses next=start_exec_session",
            completed.stderr,
        )

    def test_noarg_non_tty_stdin_prompt_preserved_with_heartbeat_trace(self) -> None:
        result = self.run_shim(
            extra_env={
                "CODEXEA_TRACE_STARTUP": "1",
                "CODEXEA_TRACE_HEARTBEAT_SECONDS": "0.1",
                "CODEXEA_BOOTSTRAP": "0",
            },
            input_text="fleet stdin prompt",
        )

        completed = result["completed"]
        payload = result["payload"]
        self.assertEqual(completed.returncode, 0)
        self.assertIsNotNone(payload)
        self.assertIn("Trace: lane=easy provider=ea model=ea-coder-fast mode=responses next=start_exec_session", completed.stderr)
        self.assertEqual(payload["stdin"], "fleet stdin prompt")
        self.assertIn("fleet stdin prompt", payload["argv"][-1])

    def test_exec_session_waiting_trace_preserves_stdin_prompt(self) -> None:
        result = self.run_shim(
            "core",
            "exec",
            "-",
            extra_env={
                "CODEXEA_TRACE_STARTUP": "1",
                "CODEXEA_TRACE_HEARTBEAT_SECONDS": "0.1",
                "CODEXEA_TEST_FAKE_CODEX_SLEEP": "0.25",
            },
            input_text="fleet worker stdin prompt",
        )

        completed = result["completed"]
        payload = result["payload"]
        self.assertEqual(completed.returncode, 0)
        self.assertIsNotNone(payload)
        self.assertEqual(payload["stdin"], "fleet worker stdin prompt")
        self.assertIn("Trace: lane=core waiting for upstream response", completed.stderr)

    def test_exec_session_uses_preseeded_stdin_prompt_env(self) -> None:
        result = self.run_shim(
            "core",
            "exec",
            "-",
            extra_env={
                "CODEXEA_STDIN_PROMPT": "seeded readiness prompt",
            },
        )

        completed = result["completed"]
        payload = result["payload"]
        self.assertEqual(completed.returncode, 0)
        self.assertIsNotNone(payload)
        self.assertEqual(payload["stdin"], "seeded readiness prompt")

    def test_readiness_remedy_prompt_activates_prepared_context_without_fleet_unblock_mode(self) -> None:
        prompt = textwrap.dedent(
            """
            Fix the remaining flagship readiness proof gaps, starting with desktop_client in /docker/chummercomplete/chummer-presentation.

            Scope:
            - Work only in /docker/chummercomplete/chummer-presentation.
            - Stay on product proof and verification.

            Run these exact commands first:
            $ sed -n '1,2p' /docker/chummercomplete/chummer-presentation/WORKLIST.md
            $ sed -n '1,2p' /docker/chummercomplete/chummer-presentation/scripts/ai/milestones/user-journey-tester-audit.sh
            """
        ).strip()

        result = self.run_shim(
            "core",
            "exec",
            "-o",
            str(self.root / "last-message.txt"),
            prompt,
            extra_env={"CODEXEA_BOOTSTRAP": "1"},
        )

        completed = result["completed"]
        payload = result["payload"]
        self.assertEqual(completed.returncode, 0)
        self.assertIsNotNone(payload)
        self.assertIn("exec", payload["argv"])
        self.assertNotIn("Operator-prepared readiness remedy context:", payload["argv"][-1])
        self.assertIn("Operator-prepared readiness remedy context:", payload["stdin"])
        self.assertIn("Read these files directly first:", payload["stdin"])
        self.assertIn(
            "Read these files directly first:\n$ python3 /docker/fleet/scripts/codex-shims/codexea_readiness_probe.py",
            payload["stdin"],
        )
        self.assertIn("Prepared repo context:", payload["stdin"])
        self.assertNotIn(
            "Run these exact commands first:\n$ sed -n '1,2p' /docker/chummercomplete/chummer-presentation/WORKLIST.md",
            payload["stdin"],
        )
        self.assertNotIn("Operator-prepared fleet unblock context:", payload["stdin"])

    def test_status_helper_repeat_block_can_fail_direct_operator_pipeline(self) -> None:
        run_dir = self.root / "operator-guard"
        run_dir.mkdir()
        telemetry_path = run_dir / "TASK_LOCAL_TELEMETRY.generated.json"
        telemetry_path.write_text(
            json.dumps(
                {
                    "summary": "Direct operator guard test.",
                    "active_runs_count": 1,
                    "remaining_open_milestones": 2,
                    "remaining_not_started_milestones": 0,
                    "remaining_in_progress_milestones": 2,
                    "eta_human": "tracked",
                    "first_commands": ["sed -n '1,3p' /docker/fleet/scripts/codex-shims/codexea"],
                    "status_helper_redirect_lookahead": 1,
                },
                ensure_ascii=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        env = os.environ.copy()
        env.update(
            {
                "CHUMMER_DESIGN_SUPERVISOR_ACTIVE_RUN_DIR": str(run_dir),
                "CHUMMER_DESIGN_SUPERVISOR_REAL_PYTHON3": sys.executable,
                "CHUMMER_DESIGN_SUPERVISOR_STATUS_HELPER_REDIRECT_LIMIT": "1",
                "CHUMMER_DESIGN_SUPERVISOR_STATUS_HELPER_FATAL": "1",
                "PATH": f"/docker/fleet/scripts/codex-shims:{os.environ.get('PATH', '')}",
            }
        )
        command = (
            "python3 /docker/fleet/scripts/chummer_design_supervisor.py status --json "
            "| python3 -c 'import json,sys; payload=json.load(sys.stdin); eta=payload.get(\"eta\") or payload; "
            "print(json.dumps({\"remaining_open_milestones\": payload.get(\"remaining_open_milestones\"), "
            "\"eta_human\": eta.get(\"eta_human\"), \"summary\": payload.get(\"summary\")}))'"
        )

        first = subprocess.run(["bash", "-lc", command], env=env, capture_output=True, text=True, check=False)
        second = subprocess.run(["bash", "-lc", command], env=env, capture_output=True, text=True, check=False)

        self.assertEqual(first.returncode, 0)
        self.assertIn("task-local JSON summary", first.stderr)
        self.assertNotEqual(second.returncode, 0)
        self.assertIn("worker_status_helper_loop:repeated_blocked_status_polling", second.stderr)
        self.assertIn("Repeated helper loop denied", second.stderr)

    def test_prompt_session_bootstrap_zero_disables_exec_trace_injection(self) -> None:
        trace_file = self.root / "exec-trace.md"
        trace_file.write_text(
            "SENTINEL_EXEC_TRACE_PROMPT",
            encoding="utf-8",
        )

        result = self.run_shim(
            "eta of the fleet? is it running? the shards?",
            extra_env={
                "CODEXEA_BOOTSTRAP": "0",
                "CODEXEA_EXEC_TRACE_PROMPT_FILE": str(trace_file),
            },
        )

        completed = result["completed"]
        payload = result["payload"]
        self.assertEqual(completed.returncode, 0)
        self.assertIsNotNone(payload)
        self.assertNotIn("SENTINEL_EXEC_TRACE_PROMPT", payload["argv"][-1])

    def test_easy_prefers_live_profile_model_when_available(self) -> None:
        payload = {
            "profiles": [
                {"profile": "easy", "model": "ea-coder-fast"},
                {"profile": "audit", "model": "ea-audit-jury"},
            ]
        }

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                body = json.dumps(payload).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format, *args):  # noqa: A003
                return

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.shutdown)
        self.addCleanup(server.server_close)
        self.addCleanup(thread.join, 1.0)

        result = self.run_shim(
            "continue the slice",
            extra_env={
                "CODEXEA_TRACE_STARTUP": "1",
                "CODEXEA_USE_LIVE_PROFILE_MODELS": "1",
                "CODEXEA_PROFILES_URL": f"http://127.0.0.1:{server.server_port}/v1/codex/profiles",
            },
        )

        completed = result["completed"]
        live_payload = result["payload"]
        self.assertIsNotNone(live_payload)
        self.assertEqual(completed.returncode, 0)
        argv = live_payload["argv"]
        self.assertIn("exec", argv)
        self.assertFalse(any(arg == 'model="gemini-2.5-flash"' for arg in argv))
        self.assertEqual(live_payload["env"]["CODEXEA_SUBMODE"], "responses_fast")
        self.assertIn(
            "Trace: lane=easy provider=ea model=ea-coder-fast mode=responses next=start_exec_session",
            completed.stderr,
        )

    def test_easy_profile_model_is_fenced_to_one_minai(self) -> None:
        payload = {
            "profiles": [
                {"profile": "easy", "model": "ea-gemini-flash"},
                {"profile": "audit", "model": "ea-audit-jury"},
            ]
        }

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                body = json.dumps(payload).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format, *args):  # noqa: A003
                return

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.shutdown)
        self.addCleanup(server.server_close)
        self.addCleanup(thread.join, 1.0)

        result = self.run_shim(
            "continue the slice",
            extra_env={
                "CODEXEA_TRACE_STARTUP": "1",
                "CODEXEA_USE_LIVE_PROFILE_MODELS": "1",
                "CODEXEA_PROFILES_URL": f"http://127.0.0.1:{server.server_port}/v1/codex/profiles",
            },
        )

        completed = result["completed"]
        live_payload = result["payload"]
        self.assertIsNotNone(live_payload)
        self.assertEqual(completed.returncode, 0)
        argv = live_payload["argv"]
        self.assertIn("exec", argv)
        self.assertIn('model="ea-coder-fast"', argv)
        self.assertNotIn('model="ea-gemini-flash"', argv)
        self.assertEqual(live_payload["env"]["CODEXEA_SUBMODE"], "responses_fast")
        self.assertIn(
            "Trace: lane=easy provider=ea model=ea-coder-fast mode=responses next=start_exec_session",
            completed.stderr,
        )

    def test_invalid_easy_model_env_var_is_fenced_to_default_one_minai(self) -> None:
        result = self.run_shim(
            "continue the slice",
            extra_env={
                "CODEXEA_EASY_MODEL": "non-1min-model",
                "CODEXEA_TRACE_STARTUP": "1",
            },
        )

        completed = result["completed"]
        live_payload = result["payload"]
        self.assertIsNotNone(live_payload)
        self.assertEqual(completed.returncode, 0)
        argv = live_payload["argv"]
        self.assertIn("exec", argv)
        self.assertIn('model="ea-coder-fast"', argv)
        self.assertNotIn('model="non-1min-model"', argv)
        self.assertIn(
            "Trace: lane=easy provider=ea model=ea-coder-fast mode=responses next=start_exec_session",
            completed.stderr,
        )

    def test_repair_prefers_live_repair_profile_model_when_available(self) -> None:
        payload = {
            "profiles": [
                {"profile": "easy", "model": "ea-coder-fast"},
                {"profile": "repair", "model": "ea-repair-gemini"},
            ]
        }

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                body = json.dumps(payload).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format, *args):  # noqa: A003
                return

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.shutdown)
        self.addCleanup(server.server_close)
        self.addCleanup(thread.join, 1.0)

        result = self.run_shim(
            "repair",
            "continue the slice",
            extra_env={
                "CODEXEA_TRACE_STARTUP": "1",
                "CODEXEA_USE_LIVE_PROFILE_MODELS": "1",
                "CODEXEA_PROFILES_URL": f"http://127.0.0.1:{server.server_port}/v1/codex/profiles",
            },
        )

        completed = result["completed"]
        live_payload = result["payload"]
        self.assertIsNotNone(live_payload)
        self.assertEqual(completed.returncode, 0)
        argv = live_payload["argv"]
        self.assertIn("exec", argv)
        self.assertIn('model="ea-repair-gemini"', argv)
        self.assertEqual(live_payload["env"]["CODEXEA_LANE"], "repair")
        self.assertEqual(live_payload["env"]["CODEXEA_SUBMODE"], "responses_fast")

    def test_status_uses_runtime_env_file_for_live_auth(self) -> None:
        observed: dict[str, str] = {}

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                observed["path"] = self.path
                observed["auth"] = str(self.headers.get("Authorization") or "")
                observed["principal"] = str(self.headers.get("X-EA-Principal-ID") or "")
                body = json.dumps({"providers_summary": []}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format, *args):  # noqa: A003
                return

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.shutdown)
        self.addCleanup(server.server_close)
        self.addCleanup(thread.join, 1.0)

        runtime_env_path = self.root / "runtime.ea.env"
        runtime_env_path.write_text(
            "\n".join(
                [
                    f"EA_MCP_BASE_URL=http://127.0.0.1:{server.server_port}",
                    "EA_MCP_API_TOKEN=shim-file-token",
                    "EA_MCP_PRINCIPAL_ID=shim-file-principal",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        result = self.run_shim(
            "status",
            "--json",
            extra_env={
                "CODEXEA_RUNTIME_EA_ENV_PATH": str(runtime_env_path),
                "EA_MCP_BASE_URL": "",
                "EA_MCP_API_TOKEN": "",
                "EA_API_TOKEN": "",
                "EA_MCP_PRINCIPAL_ID": "",
                "EA_PRINCIPAL_ID": "",
                "CODEXEA_STATUS_URL": "",
            },
        )

        completed = result["completed"]
        self.assertEqual(completed.returncode, 0)
        self.assertIn('"providers_summary": []', completed.stdout)
        self.assertEqual(observed["auth"], "Bearer shim-file-token")
        self.assertEqual(observed["principal"], "shim-file-principal")
        self.assertEqual(observed["path"], "/v1/codex/status?window=1h&refresh=0")

    def test_status_rewrites_host_docker_internal_when_unresolved(self) -> None:
        observed: dict[str, str] = {}

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                observed["path"] = self.path
                body = json.dumps({"providers_summary": []}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format, *args):  # noqa: A003
                return

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.shutdown)
        self.addCleanup(server.server_close)
        self.addCleanup(thread.join, 1.0)

        runtime_env_path = self.root / "runtime.ea.env"
        runtime_env_path.write_text(
            f"EA_MCP_BASE_URL=http://host.docker.internal:{server.server_port}\n",
            encoding="utf-8",
        )
        fake_getent = self.root / "getent"
        fake_getent.write_text("#!/usr/bin/env bash\nexit 2\n", encoding="utf-8")
        fake_getent.chmod(fake_getent.stat().st_mode | stat.S_IXUSR)

        result = self.run_shim(
            "status",
            "--json",
            extra_env={
                "CODEXEA_RUNTIME_EA_ENV_PATH": str(runtime_env_path),
                "EA_MCP_BASE_URL": "",
                "CODEXEA_STATUS_URL": "",
                "PATH": f"{self.root}:{os.environ.get('PATH', '')}",
            },
        )

        completed = result["completed"]
        self.assertEqual(completed.returncode, 0)
        self.assertIn('"providers_summary": []', completed.stdout)
        self.assertEqual(observed["path"], "/v1/codex/status?window=1h&refresh=0")

    def test_status_reports_missing_api_token_when_live_auth_is_unconfigured(self) -> None:
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                self.send_response(401)
                self.end_headers()

            def log_message(self, format, *args):  # noqa: A003
                return

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.shutdown)
        self.addCleanup(server.server_close)
        self.addCleanup(thread.join, 1.0)

        runtime_env_path = self.root / "runtime.ea.env"
        runtime_env_path.write_text(
            f"EA_MCP_BASE_URL=http://127.0.0.1:{server.server_port}\n",
            encoding="utf-8",
        )

        result = self.run_shim(
            "status",
            "--json",
            extra_env={
                "CODEXEA_RUNTIME_EA_ENV_PATH": str(runtime_env_path),
                "EA_MCP_BASE_URL": "",
                "EA_MCP_API_TOKEN": "",
                "EA_API_TOKEN": "",
                "CODEXEA_STATUS_URL": "",
                "CODEXEA_PROFILES_URL": "",
            },
        )

        completed = result["completed"]
        self.assertEqual(completed.returncode, 1)
        self.assertIn("EA_MCP_API_TOKEN / EA_API_TOKEN is not configured", completed.stderr)

    def test_easy_rejects_model_and_profile_overrides(self) -> None:
        result = self.run_shim(
            "-p",
            "manual-profile",
            "continue the slice",
        )

        completed = result["completed"]
        self.assertEqual(completed.returncode, 2)
        self.assertIn("locked to EA responses easy", completed.stderr)
        self.assertIsNone(result["payload"])

    def test_easy_rejects_spaced_config_model_provider_override(self) -> None:
        result = self.run_shim(
            "-c",
            'model_provider = "openai"',
            "continue the slice",
        )

        completed = result["completed"]
        self.assertEqual(completed.returncode, 2)
        self.assertIn("locked to EA responses easy", completed.stderr)
        self.assertIsNone(result["payload"])

    def test_easy_rejects_mode_override_without_debug_flag(self) -> None:
        result = self.run_shim(
            "continue the slice",
            extra_env={"CODEXEA_MODE": "mcp"},
        )

        completed = result["completed"]
        self.assertEqual(completed.returncode, 2)
        self.assertIn("CODEXEA_MODE override is disabled", completed.stderr)
        self.assertIsNone(result["payload"])

    def test_explicit_jury_lane_uses_audit_profile(self) -> None:
        result = self.run_shim(
            "review the release packet",
            extra_env={"CODEXEA_LANE": "jury", "CODEXEA_TRACE_STARTUP": "1"},
        )

        completed = result["completed"]
        payload = result["payload"]
        self.assertIsNotNone(payload)
        self.assertEqual(completed.returncode, 0)

        argv = payload["argv"]
        self.assertIn('model_provider="ea"', argv)
        self.assertIn('model="ea-audit-jury"', argv)
        self.assertIn('model_reasoning_effort="medium"', argv)
        self.assertEqual(payload["env"]["CODEXEA_LANE"], "jury")
        self.assertEqual(payload["env"]["CODEXEA_SUBMODE"], "responses_audit")
        self.assertIn("Trace: lane=jury provider=ea model=ea-audit-jury mode=responses next=start_exec_session", completed.stderr)

    def test_core_lane_defaults_to_batch_model_when_core_batch_profile_is_configured(self) -> None:
        result = self.run_shim(
            "fix the routing bug",
            extra_env={
                "CODEXEA_LANE": "core",
                "CODEXEA_CORE_RESPONSES_PROFILE": "core_batch",
                "CODEXEA_TRACE_STARTUP": "1",
            },
        )

        completed = result["completed"]
        payload = result["payload"]
        self.assertIsNotNone(payload)
        self.assertEqual(completed.returncode, 0)

        argv = payload["argv"]
        self.assertIn('model_provider="ea"', argv)
        self.assertIn('model="ea-coder-hard-batch"', argv)
        self.assertTrue(any('X-EA-Codex-Profile"="CODEXEA_RESPONSES_HEADER_EA_CODEX_PROFILE"' in arg for arg in argv))
        self.assertEqual(payload["env"]["CODEXEA_LANE"], "core")
        self.assertEqual(payload["env"]["CODEXEA_SUBMODE"], "responses_core_batch")
        self.assertIn(
            "Trace: lane=core provider=ea model=ea-coder-hard-batch mode=responses next=start_exec_session",
            completed.stderr,
        )

    def test_core_rescue_lane_uses_rescue_profile_and_model(self) -> None:
        result = self.run_shim(
            "finish the long-running desktop slice",
            extra_env={"CODEXEA_LANE": "core_rescue", "CODEXEA_TRACE_STARTUP": "1"},
        )

        completed = result["completed"]
        payload = result["payload"]
        self.assertIsNotNone(payload)
        self.assertEqual(completed.returncode, 0)

        argv = payload["argv"]
        self.assertIn('model_provider="ea"', argv)
        self.assertIn('model="ea-coder-hard-rescue"', argv)
        self.assertTrue(any('X-EA-Codex-Profile"="CODEXEA_RESPONSES_HEADER_EA_CODEX_PROFILE"' in arg for arg in argv))
        self.assertEqual(payload["env"]["CODEXEA_LANE"], "core_rescue")
        self.assertEqual(payload["env"]["CODEXEA_SUBMODE"], "responses_core_rescue")
        self.assertIn(
            "Trace: lane=core_rescue provider=ea model=ea-coder-hard-rescue mode=responses next=start_exec_session",
            completed.stderr,
        )

    def test_prompt_preserves_global_flags_before_exec(self) -> None:
        result = self.run_shim(
            "--search",
            "summarize recent commits",
        )

        completed = result["completed"]
        payload = result["payload"]
        self.assertEqual(completed.returncode, 0)
        self.assertIsNotNone(payload)

        argv = payload["argv"]
        self.assertIn("--search", argv)
        self.assertIn("exec", argv)
        self.assertLess(argv.index("--search"), argv.index("exec"))

    def test_non_easy_mcp_override_without_openai_auth_falls_back_to_ea_responses(self) -> None:
        result = self.run_shim(
            "investigate architecture",
            extra_env={
                "CODEXEA_LANE": "groundwork",
                "CODEXEA_MODE": "mcp",
                "CODEXEA_TRACE_STARTUP": "1",
            },
        )

        completed = result["completed"]
        payload = result["payload"]
        self.assertEqual(completed.returncode, 0)
        self.assertIsNotNone(payload)
        argv = payload["argv"]
        self.assertIn('model_provider="ea"', argv)
        self.assertIn('model="ea-groundwork-gemini"', argv)
        self.assertIn("Trace: lane=groundwork provider=ea model=ea-groundwork-gemini mode=responses next=start_exec_session", completed.stderr)

    def test_non_easy_mcp_override_keeps_mcp_when_openai_auth_is_available(self) -> None:
        result = self.run_shim(
            "investigate architecture",
            extra_env={
                "CODEXEA_LANE": "groundwork",
                "CODEXEA_MODE": "mcp",
                "CODEXEA_TRACE_STARTUP": "1",
                "OPENAI_API_KEY": "sk-test",
            },
        )

        completed = result["completed"]
        payload = result["payload"]
        self.assertEqual(completed.returncode, 0)
        self.assertIsNotNone(payload)
        argv = payload["argv"]
        self.assertIn('model="ea-groundwork-gemini"', argv)
        self.assertNotIn('model_provider="ea"', argv)
        self.assertIn("Trace: lane=groundwork provider=mcp model=ea-groundwork-gemini mode=mcp next=start_exec_session", completed.stderr)

    def test_unwritable_home_falls_back_before_launch(self) -> None:
        fallback_home = self.root / "codexea-home"
        result = self.run_shim(
            "continue the slice",
            extra_env={
                "HOME": "/",
                "CODEXEA_FALLBACK_HOME": str(fallback_home),
            },
        )

        completed = result["completed"]
        payload = result["payload"]
        self.assertEqual(completed.returncode, 0)
        self.assertIsNotNone(payload)
        self.assertEqual(payload["env"]["HOME"], str(fallback_home))
        self.assertEqual(payload["env"]["XDG_CACHE_HOME"], str(fallback_home / ".cache"))

    def test_interactive_flag_stays_interactive(self) -> None:
        result = self.run_shim("--interactive")

        completed = result["completed"]
        payload = result["payload"]
        self.assertIsNotNone(payload)
        self.assertEqual(completed.returncode, 0)
        self.assertEqual(payload["env"]["CODEXEA_LANE"], "easy")
        self.assertEqual(payload["env"]["CODEXEA_SUBMODE"], "responses_easy")
        self.assertNotIn("--interactive", payload["argv"])
        self.assertIn('model_provider="ea"', payload["argv"])
        self.assertIn(f'model="{DEFAULT_EASY_INTERACTIVE_MODEL}"', payload["argv"])
        self.assertIn(
            f"Trace: lane=easy provider=ea model={DEFAULT_EASY_INTERACTIVE_MODEL} mode=responses next=start_interactive_session",
            completed.stderr,
        )

    def test_tmux_interactive_session_uses_script_tty_wrapper_when_supported(self) -> None:
        script_capture = self.root / "script-capture.txt"
        self.write_fake_script(True, script_capture)

        result = self.run_shim(
            "--interactive",
            "investigate architecture",
            extra_env={
                "TMUX": "/tmp/tmux-1000/test,19062,0",
                "PATH": f"{self.root}:{os.environ.get('PATH', '')}",
                "SCRIPT_HELP_CAPTURE": str(script_capture),
                "CODEXEA_TRACE_STARTUP": "1",
            },
        )

        completed = result["completed"]
        payload = result["payload"]
        self.assertEqual(completed.returncode, 0)
        self.assertIsNotNone(payload)
        self.assertIn(f'model="{DEFAULT_EASY_INTERACTIVE_MODEL}"', payload["argv"])
        if script_capture.exists():
            script_lines = script_capture.read_text(encoding="utf-8").splitlines()
            self.assertTrue(
                any("--quiet" in entry for entry in script_lines),
                "\n".join(script_lines),
            )
        self.assertIn(
            f"Trace: lane=easy provider=ea model={DEFAULT_EASY_INTERACTIVE_MODEL} mode=responses next=start_interactive_session",
            completed.stderr,
        )

    def test_tmux_interactive_session_skips_script_wrapper_without_support(self) -> None:
        script_capture = self.root / "script-capture.txt"
        self.write_fake_script(False, script_capture)

        result = self.run_shim(
            "--interactive",
            "investigate architecture",
            extra_env={
                "TMUX": "/tmp/tmux-1000/test,19062,0",
                "PATH": f"{self.root}:{os.environ.get('PATH', '')}",
                "SCRIPT_HELP_CAPTURE": str(script_capture),
                "CODEXEA_TRACE_STARTUP": "1",
            },
        )

        completed = result["completed"]
        payload = result["payload"]
        self.assertEqual(completed.returncode, 0)
        self.assertIsNotNone(payload)
        self.assertIn(f'model="{DEFAULT_EASY_INTERACTIVE_MODEL}"', payload["argv"])
        if script_capture.exists():
            self.assertFalse(
                any(
                    "--command" in entry and "--return" in entry
                    for entry in script_capture.read_text(encoding="utf-8").splitlines()
                ),
                "wrapper should not be used when script --help lacks required options",
            )
        self.assertIn(
            f"Trace: lane=easy provider=ea model={DEFAULT_EASY_INTERACTIVE_MODEL} mode=responses next=start_interactive_session",
            completed.stderr,
        )

    def test_interactive_flag_with_prompt_stays_interactive(self) -> None:
        result = self.run_shim("--interactive", "investigate architecture")

        completed = result["completed"]
        payload = result["payload"]
        self.assertIsNotNone(payload)
        self.assertEqual(completed.returncode, 0)
        self.assertEqual(payload["env"]["CODEXEA_LANE"], "easy")
        self.assertEqual(payload["env"]["CODEXEA_SUBMODE"], "responses_easy")
        self.assertNotIn("--interactive", payload["argv"])
        self.assertEqual(payload["argv"].count("exec"), 0)
        self.assertIn('model_provider="ea"', payload["argv"])
        self.assertIn(f'model="{DEFAULT_EASY_INTERACTIVE_MODEL}"', payload["argv"])
        self.assertEqual(payload["argv"][-1], "investigate architecture")
        self.assertIn(
            f"Trace: lane=easy provider=ea model={DEFAULT_EASY_INTERACTIVE_MODEL} mode=responses next=start_interactive_session",
            completed.stderr,
        )

    def test_interactive_flag_skips_route_helper_telemetry_path(self) -> None:
        route_helper = self.root / "route-helper.py"
        route_helper.write_text(
            "\n".join(
                [
                    "#!/usr/bin/env python3",
                    "import sys",
                    "raise SystemExit(9)",
                ]
            ),
            encoding="utf-8",
        )
        route_helper.chmod(route_helper.stat().st_mode | stat.S_IXUSR)

        result = self.run_shim(
            "--interactive",
            extra_env={"CODEXEA_ROUTE_HELPER": str(route_helper)},
        )

        completed = result["completed"]
        payload = result["payload"]
        self.assertEqual(completed.returncode, 0)
        self.assertIsNotNone(payload)
        self.assertNotIn("--interactive", payload["argv"])

    def test_bare_bootstrap_session_starts_empty_interactive_without_injecting_prompt_file(self) -> None:
        prompt_file = self.root / "bootstrap.md"
        prompt_file.write_text(
            "Trace: lane easy ready and waiting.\nWait for the next user instruction.\n",
            encoding="utf-8",
        )

        result = self.run_shim(
            extra_env={
                "CODEXEA_BOOTSTRAP": "1",
                "CODEXEA_BOOTSTRAP_PROMPT_FILE": str(prompt_file),
            },
        )

        completed = result["completed"]
        payload = result["payload"]
        self.assertEqual(completed.returncode, 0)
        self.assertIsNotNone(payload)
        self.assertNotIn(prompt_file.read_text(encoding="utf-8").rstrip("\n"), payload["argv"])
        self.assertNotIn("continue the next unfinished slice", " ".join(payload["argv"]).lower())
        self.assertIn(
            f"Trace: lane=easy provider=ea model={DEFAULT_EASY_INTERACTIVE_MODEL} mode=responses next=",
            completed.stderr,
        )
        self.assertTrue(
            "start_exec_session" in completed.stderr
            or "start_interactive_session" in completed.stderr
        )

    def test_interactive_flag_can_route_away_from_easy_when_opted_in(self) -> None:
        route_helper = self.root / "route-helper.py"
        route_helper.write_text(
            "\n".join(
                [
                    "#!/usr/bin/env python3",
                    "print('lane=groundwork')",
                    "print('submode=responses_groundwork')",
                ]
            ),
            encoding="utf-8",
        )
        route_helper.chmod(route_helper.stat().st_mode | stat.S_IXUSR)

        result = self.run_shim(
            "--interactive",
            "investigate architecture",
            extra_env={
                "CODEXEA_INTERACTIVE_ALWAYS_EASY": "0",
                "CODEXEA_ROUTE_HELPER": str(route_helper),
                "CODEXEA_TRACE_STARTUP": "1",
            },
        )

        completed = result["completed"]
        payload = result["payload"]
        self.assertEqual(completed.returncode, 0)
        self.assertIsNotNone(payload)
        self.assertEqual(payload["env"]["CODEXEA_LANE"], "groundwork")
        self.assertEqual(payload["env"]["CODEXEA_SUBMODE"], "responses_groundwork")
        self.assertNotIn("--interactive", payload["argv"])
        self.assertEqual(payload["argv"].count("exec"), 0)
        self.assertIn('model="ea-groundwork-gemini"', payload["argv"])
        self.assertIn(
            "Trace: lane=groundwork provider=ea model=ea-groundwork-gemini mode=responses next=start_interactive_session",
            completed.stderr,
        )

    def test_credits_keeps_standard_billing_route_flags(self) -> None:
        route_helper = self.write_route_helper()

        result = self.run_shim(
            "credits",
            extra_env={
                "CODEXEA_ROUTE_HELPER": str(route_helper),
                "CODEXEA_ROUTE_CAPTURE": str(self.route_capture_path),
            },
        )

        completed = result["completed"]
        self.assertEqual(completed.returncode, 0)
        argv = json.loads(self.route_capture_path.read_text(encoding="utf-8"))["argv"]
        self.assertEqual(argv[:2], ["--onemin-aggregate", "--billing"])
        self.assertNotIn("--billing-full-refresh", argv)

    def test_credits_enforces_default_billing_timeout_when_not_set(self) -> None:
        route_helper = self.write_route_helper()

        result = self.run_shim(
            "credits",
            extra_env={
                "CODEXEA_ROUTE_HELPER": str(route_helper),
                "CODEXEA_ROUTE_CAPTURE": str(self.route_capture_path),
                "CODEXEA_ONEMIN_BILLING_TIMEOUT_SECONDS": "",
            },
        )

        completed = result["completed"]
        self.assertEqual(completed.returncode, 0)
        payload = json.loads(self.route_capture_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["env"]["CODEXEA_ONEMIN_BILLING_TIMEOUT_SECONDS"], "30")

    def test_onemin_keeps_standard_billing_route_flags(self) -> None:
        route_helper = self.write_route_helper()

        result = self.run_shim(
            "onemin",
            extra_env={
                "CODEXEA_ROUTE_HELPER": str(route_helper),
                "CODEXEA_ROUTE_CAPTURE": str(self.route_capture_path),
            },
        )

        completed = result["completed"]
        self.assertEqual(completed.returncode, 0)
        argv = json.loads(self.route_capture_path.read_text(encoding="utf-8"))["argv"]
        self.assertEqual(argv[:2], ["--onemin-aggregate", "--billing"])
        self.assertNotIn("--billing-full-refresh", argv)

    def test_direct_onemin_aggregate_routes_to_helper(self) -> None:
        route_helper = self.write_route_helper()

        result = self.run_shim(
            "--onemin-aggregate",
            "--refresh",
            "--billing",
            "--billing-full-refresh",
            "--json",
            extra_env={
                "CODEXEA_ROUTE_HELPER": str(route_helper),
                "CODEXEA_ROUTE_CAPTURE": str(self.route_capture_path),
            },
        )

        completed = result["completed"]
        self.assertEqual(completed.returncode, 0)
        argv = json.loads(self.route_capture_path.read_text(encoding="utf-8"))["argv"]
        self.assertEqual(
            argv,
            ["--onemin-aggregate", "--refresh", "--billing", "--billing-full-refresh", "--json"],
        )

    def test_credits_preserves_manual_billing_full_refresh_flag(self) -> None:
        route_helper = self.write_route_helper()

        result = self.run_shim(
            "credits",
            "--billing-full-refresh",
            extra_env={
                "CODEXEA_ROUTE_HELPER": str(route_helper),
                "CODEXEA_ROUTE_CAPTURE": str(self.route_capture_path),
            },
        )

        completed = result["completed"]
        self.assertEqual(completed.returncode, 0)
        argv = json.loads(self.route_capture_path.read_text(encoding="utf-8"))["argv"]
        self.assertEqual(argv[:3], ["--onemin-aggregate", "--billing", "--billing-full-refresh"])

    def test_explicit_exec_subcommand_is_not_double_wrapped(self) -> None:
        result = self.run_shim(
            "exec",
            "summarize recent commits",
        )

        completed = result["completed"]
        payload = result["payload"]
        self.assertEqual(completed.returncode, 0)
        self.assertIsNotNone(payload)
        self.assertNotIn("", payload["argv"])
        self.assertEqual(payload["argv"].count("exec"), 1)
        self.assertNotIn("--no-alt-screen", payload["argv"])

    def test_exec_hard_timeout_kills_stalled_child(self) -> None:
        result = self.run_shim(
            "exec",
            "produce a result",
            extra_env={
                "CODEXEA_EXEC_HARD_TIMEOUT_SECONDS": "1",
                "CODEXEA_TEST_FAKE_CODEX_SLEEP": "5",
            },
        )

        completed = result["completed"]
        self.assertEqual(completed.returncode, 124)
        self.assertIn("terminating stalled", completed.stderr)
        self.assertIsNone(result["payload"])

    def test_exec_hard_timeout_writes_actionable_last_message_when_output_path_requested(self) -> None:
        output_path = self.root / "last_message.txt"

        result = self.run_shim(
            "core",
            "exec",
            "-o",
            str(output_path),
            "produce a result",
            extra_env={
                "CODEXEA_EXEC_HARD_TIMEOUT_SECONDS": "1",
                "CODEXEA_TEST_FAKE_CODEX_SLEEP": "5",
                "CODEXEA_OPERATOR_GUARD_ACTIVE": "1",
            },
        )

        completed = result["completed"]
        self.assertEqual(completed.returncode, 124)
        self.assertIn("terminating stalled", completed.stderr)
        self.assertIn("What shipped: none recorded", output_path.read_text(encoding="utf-8"))
        self.assertIn("Exact blocker: upstream_timeout:1s", output_path.read_text(encoding="utf-8"))
        self.assertIsNone(result["payload"])

    def test_exec_rewrites_blank_structured_closeout_to_actionable_error(self) -> None:
        output_path = self.root / "last_message.txt"
        fake_codex = self.write_executable(
            self.root / "codex-blank-closeout.py",
            f"""
            #!/usr/bin/env python3
            import pathlib
            import sys

            output_path = ""
            argv = sys.argv[1:]
            for index, arg in enumerate(argv):
                if arg in ("-o", "--output-last-message") and index + 1 < len(argv):
                    output_path = argv[index + 1]
                    break
            if output_path:
                pathlib.Path(output_path).write_text(
                    "What shipped: \\n\\nWhat remains: \\n\\nExact blocker: \\n",
                    encoding="utf-8",
                )
            print("Trace: lane=review_light waiting for upstream response (total_duration=32s)", file=sys.stderr)
            raise SystemExit(0)
            """,
        )

        result = self.run_shim(
            "review_light",
            "exec",
            "-o",
            str(output_path),
            "Reply with exactly ok.",
            extra_env={"CODEXEA_TEST_FAKE_CODEX_PATH": str(fake_codex)},
        )

        completed = result["completed"]
        self.assertEqual(completed.returncode, 0)
        text = output_path.read_text(encoding="utf-8")
        self.assertIn("Error: missing_final_message", text)
        self.assertIn("What shipped: none recorded", text)
        self.assertIn("Exact blocker: missing_final_message", text)

    def test_watchdog_ignores_synthetic_wait_heartbeats_as_progress(self) -> None:
        watchdog = _load_watchdog_module()

        self.assertFalse(
            watchdog._has_meaningful_progress(
                b"Trace: lane=core waiting for upstream response (total_duration=30s)\n"
            )
        )
        self.assertFalse(
            watchdog._has_meaningful_progress(
                b"Trace: provider=liz transport=outage status=502 retry_in=5s elapsed=30s\n"
            )
        )
        self.assertTrue(watchdog._has_meaningful_progress(b"Trace: patching queue worker\n"))
        self.assertEqual(
            watchdog._activity_state(
                b"Trace: lane=core waiting for upstream response (total_duration=30s)\n"
            ),
            "waiting",
        )
        self.assertEqual(
            watchdog._activity_state(
                b"Reconnecting... 4/5 (21m 51s \xe2\x80\xa2 esc to interrupt)\n"
            ),
            "waiting",
        )
        self.assertEqual(
            watchdog._activity_state(b"\xe2\x80\xa2 Working (2m 14s \xe2\x80\xa2 esc to interrupt)\n"),
            "waiting",
        )
        self.assertEqual(watchdog._activity_state(b"Trace: patching queue worker\n"), "meaningful")

    def test_watchdog_holds_recent_wait_signals_within_grace_window(self) -> None:
        watchdog = _load_watchdog_module()

        self.assertTrue(
            watchdog._should_hold_wait_session(
                now=60.0,
                wait_started_at=15.0,
                last_wait_signal=52.0,
                interval=15,
                wait_grace_seconds=3600.0,
            )
        )
        self.assertFalse(
            watchdog._should_hold_wait_session(
                now=60.0,
                wait_started_at=15.0,
                last_wait_signal=20.0,
                interval=15,
                wait_grace_seconds=3600.0,
            )
        )
        self.assertFalse(
            watchdog._should_hold_wait_session(
                now=3700.0,
                wait_started_at=15.0,
                last_wait_signal=3695.0,
                interval=15,
                wait_grace_seconds=300.0,
            )
        )

    def test_explicit_lane_exec_subcommand_skips_route_helper_telemetry(self) -> None:
        route_helper = self.root / "route-helper.py"
        route_helper.write_text(
            "\n".join(
                [
                    "#!/usr/bin/env python3",
                    "import json, os, sys",
                    "with open(os.environ['CODEXEA_ROUTE_CAPTURE'], 'w', encoding='utf-8') as handle:",
                    "    json.dump({'argv': sys.argv[1:]}, handle)",
                ]
            ),
            encoding="utf-8",
        )
        route_helper.chmod(route_helper.stat().st_mode | stat.S_IXUSR)

        result = self.run_shim(
            "core",
            "exec",
            "summarize recent commits",
            extra_env={
                "CODEXEA_ROUTE_HELPER": str(route_helper),
                "CODEXEA_ROUTE_CAPTURE": str(self.route_capture_path),
            },
        )

        completed = result["completed"]
        payload = result["payload"]
        self.assertEqual(completed.returncode, 0)
        self.assertIsNotNone(payload)
        self.assertEqual(payload["argv"].count("exec"), 1)
        self.assertNotIn("Telemetry", "".join(completed.stdout.splitlines()))
        self.assertFalse(self.route_capture_path.exists())
        self.assertEqual(payload["env"]["CODEXEA_LANE"], "core")

    def test_plain_exec_subcommand_can_use_telemetry_shortcut_without_lane_override(self) -> None:
        route_helper = self.root / "route-helper.py"
        route_helper.write_text(
            "\n".join(
                [
                    "#!/usr/bin/env python3",
                    "import sys",
                    "if len(sys.argv) > 1 and sys.argv[1] == '--telemetry-answer':",
                    "    print('exec telemetry ok')",
                    "    raise SystemExit(0)",
                    "raise SystemExit(10)",
                ]
            ),
            encoding="utf-8",
        )
        route_helper.chmod(route_helper.stat().st_mode | stat.S_IXUSR)

        result = self.run_shim(
            "exec",
            "eta? active shards?",
            extra_env={"CODEXEA_ROUTE_HELPER": str(route_helper)},
        )

        completed = result["completed"]
        self.assertEqual(completed.returncode, 0)
        self.assertEqual(completed.stdout.strip(), "exec telemetry ok")
        self.assertIsNone(result["payload"])

    def test_resume_subcommand_stays_passthrough_under_bootstrap(self) -> None:
        result = self.run_shim(
            "resume",
            "--last",
            extra_env={"CODEXEA_BOOTSTRAP": "1", "CODEXEA_BOOTSTRAP_PROMPT_FILE": str(BOOTSTRAP_PATH)},
        )

        completed = result["completed"]
        payload = result["payload"]
        self.assertEqual(completed.returncode, 0)
        self.assertIsNotNone(payload)
        self.assertEqual(payload["argv"].count("resume"), 1)
        self.assertFalse(any("AGENTS.md" in arg for arg in payload["argv"]))

    def test_resume_subcommand_with_session_id_stays_passthrough(self) -> None:
        result = self.run_shim(
            "resume",
            "uid123",
        )

        completed = result["completed"]
        payload = result["payload"]
        self.assertEqual(completed.returncode, 0)
        self.assertIsNotNone(payload)
        self.assertEqual(payload["argv"].count("resume"), 1)
        self.assertIn("uid123", payload["argv"])
        self.assertIn("--no-alt-screen", payload["argv"])
        self.assertIn("next=start_resume_session", completed.stderr)

    def test_resume_subcommand_with_session_id_and_prompt_stays_passthrough(self) -> None:
        result = self.run_shim(
            "resume",
            "uid123",
            "continue fixing fleet",
        )

        completed = result["completed"]
        payload = result["payload"]
        self.assertEqual(completed.returncode, 0)
        self.assertIsNotNone(payload)
        self.assertEqual(payload["argv"].count("resume"), 1)
        self.assertIn("uid123", payload["argv"])
        self.assertIn("continue fixing fleet", payload["argv"])
        self.assertFalse(any("AGENTS.md" in arg for arg in payload["argv"]))

    def test_exec_keeps_responses_auth_token_out_of_argv(self) -> None:
        result = self.run_shim(
            "core",
            "exec",
            "say ok",
            extra_env={
                "CODEXEA_CLEAN_EXEC_OUTPUT": "0",
                "CODEXEA_DISABLE_SCRIPT_WRAPPER": "1",
                "EA_API_TOKEN": "super-secret-token",
            },
        )

        completed = result["completed"]
        payload = result["payload"]
        self.assertEqual(completed.returncode, 0)
        self.assertIsNotNone(payload)
        argv = payload["argv"]
        self.assertFalse(any("super-secret-token" in arg for arg in argv))
        self.assertFalse(any("Authorization" in arg for arg in argv))
        self.assertIn('model_providers.ea.bearer_token_env_var="CODEXEA_RESPONSES_AUTH_TOKEN"', argv)
        self.assertIn(
            'model_providers.ea.env_http_headers={"X-EA-Principal-ID"="CODEXEA_RESPONSES_HEADER_EA_PRINCIPAL_ID","X-EA-Codex-Profile"="CODEXEA_RESPONSES_HEADER_EA_CODEX_PROFILE","x-api-token"="CODEXEA_RESPONSES_AUTH_TOKEN","X-EA-Api-Token"="CODEXEA_RESPONSES_AUTH_TOKEN"}',
            argv,
        )
        self.assertEqual(payload["env"]["CODEXEA_RESPONSES_AUTH_TOKEN"], "super-secret-token")

    def test_status_uses_curl_config_for_auth_headers(self) -> None:
        curl_path = self.write_executable(
            self.root / "curl",
            """#!/usr/bin/env bash
            set -euo pipefail
            config_path=""
            args=("$@")
            for ((i=0; i<${#args[@]}; i++)); do
              if [ "${args[$i]}" = "-K" ] && [ $((i + 1)) -lt ${#args[@]} ]; then
                config_path="${args[$((i + 1))]}"
                break
              fi
            done
            python3 -c 'import json, pathlib, sys; config_path = sys.argv[1]; config_text = pathlib.Path(config_path).read_text(encoding="utf-8") if config_path else ""; print(json.dumps({"argv": sys.argv[2:], "config_path": config_path, "config_text": config_text}))' "$config_path" "$@"
            """,
        )

        result = self.run_shim(
            "status",
            "--json",
            extra_env={
                "EA_MCP_API_TOKEN": "status-secret-token",
                "PATH": f"{self.root}:{os.environ.get('PATH', '')}",
            },
        )

        completed = result["completed"]
        self.assertEqual(completed.returncode, 0)
        payload = json.loads(completed.stdout)
        argv = payload["argv"]
        self.assertTrue(curl_path.exists())
        self.assertIn("-K", argv)
        self.assertFalse(any("status-secret-token" in arg for arg in argv))
        self.assertIn("Authorization: Bearer status-secret-token", payload["config_text"])
        self.assertIn("X-EA-Api-Token: status-secret-token", payload["config_text"])
        self.assertIn("X-API-Token: status-secret-token", payload["config_text"])
        self.assertFalse(Path(payload["config_path"]).exists())

    def test_interactive_bootstrap_requires_trace_lines(self) -> None:
        text = BOOTSTRAP_PATH.read_text(encoding="utf-8")

        self.assertIn("AGENTS.md", text)
        self.assertIn("Trace:", text)
        self.assertIn("20-45 seconds", text)


if __name__ == "__main__":
    unittest.main()
