from __future__ import annotations

import json
import os
import stat
import subprocess
import textwrap
from pathlib import Path


SCRIPT_PATH = Path("/docker/fleet/scripts/deploy.sh")


def _write_executable(path: Path, content: str) -> None:
    path.write_text(textwrap.dedent(content).lstrip(), encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def test_admin_status_uses_local_curl_config_without_password_in_argv(tmp_path: Path) -> None:
    curl_capture = tmp_path / "curl-capture.json"
    docker_capture = tmp_path / "docker-capture.json"

    _write_executable(
        tmp_path / "docker",
        """#!/usr/bin/env bash
        set -euo pipefail
        python3 -c 'import json, os, pathlib, sys; pathlib.Path(os.environ["DOCKER_CAPTURE"]).write_text(json.dumps({"argv": sys.argv[1:], "stdin": sys.stdin.read()}), encoding="utf-8")' "$@"
        exit 1
        """,
    )
    _write_executable(
        tmp_path / "curl",
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
        python3 -c 'import json, os, pathlib, sys; config_path = sys.argv[1]; payload = {"argv": sys.argv[2:], "config_path": config_path, "config_text": pathlib.Path(config_path).read_text(encoding="utf-8") if config_path else ""}; pathlib.Path(os.environ["CURL_CAPTURE"]).write_text(json.dumps(payload), encoding="utf-8")' "$config_path" "$@"
        printf '%s' '{"ok":true}'
        """,
    )

    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{tmp_path}:{env['PATH']}",
            "FLEET_OPERATOR_PASSWORD": "super-secret-password",
            "CURL_CAPTURE": str(curl_capture),
            "DOCKER_CAPTURE": str(docker_capture),
        }
    )

    completed = subprocess.run(
        ["bash", str(SCRIPT_PATH), "admin-status"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout) == {"ok": True}

    curl_payload = json.loads(curl_capture.read_text(encoding="utf-8"))
    assert "super-secret-password" not in " ".join(curl_payload["argv"])
    assert "-K" in curl_payload["argv"]
    assert 'X-Fleet-Operator-Password: super-secret-password' in curl_payload["config_text"]
    assert not Path(curl_payload["config_path"]).exists()

    docker_payload = json.loads(docker_capture.read_text(encoding="utf-8"))
    assert "super-secret-password" not in " ".join(docker_payload["argv"])


def test_gateway_cockpit_uses_stdin_for_operator_password(tmp_path: Path) -> None:
    docker_capture = tmp_path / "docker-capture.json"

    _write_executable(
        tmp_path / "docker",
        """#!/usr/bin/env bash
        set -euo pipefail
        python3 -c 'import json, os, pathlib, sys; pathlib.Path(os.environ["DOCKER_CAPTURE"]).write_text(json.dumps({"argv": sys.argv[1:], "stdin": sys.stdin.read()}), encoding="utf-8")' "$@"
        printf '%s' '{"cockpit":{"summary":{"fleet_health":"ok","active_workers":3,"open_incidents":0,"approvals_waiting":1},"workers":[{"project_id":"fleet"}]}}'
        """,
    )

    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{tmp_path}:{env['PATH']}",
            "FLEET_OPERATOR_PASSWORD": "super-secret-password",
            "DOCKER_CAPTURE": str(docker_capture),
        }
    )

    completed = subprocess.run(
        ["bash", str(SCRIPT_PATH), "gateway-cockpit"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["fleet_health"] == "ok"
    assert payload["worker_ids"] == ["fleet"]

    docker_payload = json.loads(docker_capture.read_text(encoding="utf-8"))
    assert "super-secret-password" not in " ".join(docker_payload["argv"])
    assert docker_payload["stdin"].strip() == "super-secret-password"
