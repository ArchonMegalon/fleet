from __future__ import annotations

import json
import os
import stat
import subprocess
import textwrap
from pathlib import Path


SCRIPT_PATH = Path("/docker/fleet/scripts/repair_fleet_credential.sh")


def _write_executable(path: Path, content: str) -> None:
    path.write_text(textwrap.dedent(content).lstrip(), encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def test_repair_fleet_credential_validates_candidate_without_token_in_argv(tmp_path: Path) -> None:
    runtime_env = tmp_path / "runtime.env"
    runtime_env.write_text("OPENAI_API_KEY=current-bad-token\n", encoding="utf-8")

    candidate_env = tmp_path / "candidate.env"
    candidate_env.write_text("OPENAI_API_KEY_FALLBACK=good-secret-token\n", encoding="utf-8")

    capture_path = tmp_path / "curl-capture.json"
    curl_path = tmp_path / "curl"
    _write_executable(
        curl_path,
        """#!/usr/bin/env bash
        set -euo pipefail
        output_file=""
        write_fmt=""
        config_path=""
        args=("$@")
        for ((i=0; i<${#args[@]}; i++)); do
          case "${args[$i]}" in
            -o)
              output_file="${args[$((i + 1))]}"
              ;;
            -w)
              write_fmt="${args[$((i + 1))]}"
              ;;
            -K)
              config_path="${args[$((i + 1))]}"
              ;;
          esac
        done
        python3 -c 'import json, os, pathlib, sys; config_path = sys.argv[1]; payload = {"argv": sys.argv[2:], "config_path": config_path, "config_text": pathlib.Path(config_path).read_text(encoding="utf-8") if config_path else ""}; pathlib.Path(os.environ["TEST_CAPTURE_PATH"]).write_text(json.dumps(payload), encoding="utf-8")' "$config_path" "$@"
        : > "$output_file"
        printf '%s' "${write_fmt//%\\{http_code\\}/200}"
        """,
    )

    env = os.environ.copy()
    env.update(
        {
            "FLEET_CREDENTIAL_SOURCE_LABEL": f"local env file {runtime_env}::OPENAI_API_KEY",
            "FLEET_RUNTIME_ENV_PATH": str(runtime_env),
            "FLEET_OPENAI_REPAIR_ENV_PATHS": str(candidate_env),
            "FLEET_OPENAI_VALIDATION_URL": "https://example.invalid/v1/models",
            "PATH": f"{tmp_path}:{env['PATH']}",
            "TEST_CAPTURE_PATH": str(capture_path),
        }
    )

    completed = subprocess.run(
        ["bash", str(SCRIPT_PATH)],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    capture = json.loads(capture_path.read_text(encoding="utf-8"))
    argv = capture["argv"]

    assert "good-secret-token" not in " ".join(argv)
    assert "-K" in argv
    assert 'Authorization: Bearer good-secret-token' in capture["config_text"]
    assert not Path(capture["config_path"]).exists()
    assert "OPENAI_API_KEY=good-secret-token" in runtime_env.read_text(encoding="utf-8")
