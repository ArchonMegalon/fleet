#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pathlib
import re
import subprocess
import sys
from typing import Any


UTC = dt.timezone.utc
URL_RE = re.compile(r"https?://[^\s)]+")
CODE_RE = re.compile(r"(?:user code|device code|enter code|code)\s*[:=]?\s*([A-Z0-9-]{4,})", re.IGNORECASE)


def iso_now() -> str:
    return dt.datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run `codex login --device-auth` in a lane-local home and persist normalized status.")
    parser.add_argument("--lane-id", required=True)
    parser.add_argument("--lane-home", required=True)
    parser.add_argument("--status-path", required=True)
    return parser.parse_args()


def write_status(path: pathlib.Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    temp_path.replace(path)


def extract_uri_and_code(text: str) -> tuple[str, str]:
    uri = ""
    code = ""
    url_match = URL_RE.search(text)
    if url_match:
        uri = url_match.group(0).rstrip(".,")
    code_match = CODE_RE.search(text)
    if code_match:
        code = code_match.group(1).strip().upper()
    if not code and uri:
        query_code = re.search(r"[?&]code=([A-Za-z0-9-]{4,})", uri)
        if query_code:
            code = query_code.group(1).strip().upper()
    return uri, code


def ensure_lane_home(lane_home: pathlib.Path) -> None:
    lane_home.mkdir(parents=True, exist_ok=True)
    config_path = lane_home / "config.toml"
    config_path.write_text('cli_auth_credentials_store = "file"\nforced_login_method = "chatgpt"\n', encoding="utf-8")


def main() -> int:
    args = parse_args()
    lane_home = pathlib.Path(args.lane_home).resolve()
    status_path = pathlib.Path(args.status_path).resolve()
    auth_path = lane_home / "auth.json"
    ensure_lane_home(lane_home)
    env = os.environ.copy()
    env["HOME"] = str(lane_home)
    env["CODEX_HOME"] = str(lane_home)

    status: dict[str, Any] = {
        "lane_id": str(args.lane_id),
        "pid": os.getpid(),
        "status": "starting",
        "verification_uri": "",
        "user_code": "",
        "auth_ready": auth_path.exists(),
        "updated_at": iso_now(),
        "last_error": "",
    }
    write_status(status_path, status)

    proc = subprocess.Popen(
        ["codex", "login", "--device-auth"],
        cwd=str(lane_home),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        text=True,
        bufsize=1,
    )
    status["pid"] = int(proc.pid)
    status["status"] = "pending_auth"
    status["updated_at"] = iso_now()
    write_status(status_path, status)

    combined = ""
    if proc.stdout is None:
        proc.wait()
    else:
        for line in proc.stdout:
            sys.stdout.write(line)
            sys.stdout.flush()
            combined += line
            uri, code = extract_uri_and_code(combined)
            if uri:
                status["verification_uri"] = uri
            if code:
                status["user_code"] = code
            status["auth_ready"] = auth_path.exists()
            status["status"] = "pending_auth" if not status["auth_ready"] else "auth_ready"
            status["updated_at"] = iso_now()
            write_status(status_path, status)

    rc = int(proc.wait())
    status["exit_code"] = rc
    status["auth_ready"] = auth_path.exists()
    if status["auth_ready"]:
        status["status"] = "auth_ready"
        status["last_error"] = ""
    elif rc == 0:
        status["status"] = "completed_without_auth"
        status["last_error"] = "codex device auth completed without writing auth.json"
    else:
        status["status"] = "error"
        status["last_error"] = f"codex login --device-auth exited with {rc}"
    status["updated_at"] = iso_now()
    write_status(status_path, status)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
