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
ANSI_ESCAPE_RE = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")
CODE_RE = re.compile(
    r"\b(?:one-time code|user code|device code|enter code|enter this one-time code)\b(?:\s*\([^)]+\))?\s*(?::|=|\bis\b)\s*([A-Z0-9-]{4,})",
    re.IGNORECASE,
)
STANDALONE_CODE_RE = re.compile(r"^\s*([A-Z0-9]{4,}(?:-[A-Z0-9]{4,})+)\s*$")
KNOWN_TIERS = {"free", "go", "plus", "pro", "business", "edu", "enterprise"}


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
    text = ANSI_ESCAPE_RE.sub("", text or "")
    uri = ""
    code = ""
    for line in text.splitlines():
        cleaned = line.strip()
        if not cleaned:
            continue
        if not uri:
            url_match = URL_RE.search(cleaned)
            if url_match:
                uri = url_match.group(0).rstrip(".,")
        if not code:
            code_match = CODE_RE.search(cleaned)
            if code_match:
                code = code_match.group(1).strip().upper()
                continue
            standalone = STANDALONE_CODE_RE.match(cleaned)
            if standalone:
                code = standalone.group(1).strip().upper()
    if not code and uri:
        query_code = re.search(r"[?&]code=([A-Za-z0-9-]{4,})", uri)
        if query_code:
            code = query_code.group(1).strip().upper()
    return uri, code


def ensure_lane_home(lane_home: pathlib.Path) -> None:
    lane_home.mkdir(parents=True, exist_ok=True)
    config_path = lane_home / "config.toml"
    config_path.write_text('cli_auth_credentials_store = "file"\nforced_login_method = "chatgpt"\n', encoding="utf-8")


def _normalize_tier(value: Any) -> str:
    raw = str(value or "").strip().lower()
    return raw if raw in KNOWN_TIERS else ""


def _search_tier(value: Any) -> str:
    if isinstance(value, dict):
        for key, item in value.items():
            key_text = str(key or "").strip().lower()
            if key_text in {"plan", "tier", "subscription_tier", "subscription_plan", "account_plan", "plan_name", "chatgpt_plan"}:
                normalized = _normalize_tier(item)
                if normalized:
                    return normalized
            nested = _search_tier(item)
            if nested:
                return nested
    elif isinstance(value, list):
        for item in value:
            nested = _search_tier(item)
            if nested:
                return nested
    elif isinstance(value, str):
        normalized = _normalize_tier(value)
        if normalized:
            return normalized
    return ""


def detect_authorization_tier(auth_path: pathlib.Path) -> tuple[str, str]:
    if not auth_path.exists():
        return "", ""
    try:
        payload = json.loads(auth_path.read_text(encoding="utf-8"))
    except Exception:
        return "", ""
    tier = _search_tier(payload)
    if not tier:
        return "", ""
    return tier, "fleet_detected"


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
            tier, tier_source = detect_authorization_tier(auth_path)
            if tier:
                status["authorization_tier"] = tier
                status["tier_source"] = tier_source
            status["status"] = "pending_auth" if not status["auth_ready"] else "auth_ready"
            status["updated_at"] = iso_now()
            write_status(status_path, status)

    rc = int(proc.wait())
    status["exit_code"] = rc
    status["auth_ready"] = auth_path.exists()
    tier, tier_source = detect_authorization_tier(auth_path)
    if tier:
        status["authorization_tier"] = tier
        status["tier_source"] = tier_source
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
