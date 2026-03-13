#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


EA_ENV = Path("/docker/EA/.env")
API_BASE = "https://api.browseract.com/v2/workflow"


def env_value(name: str) -> str:
    direct = str(os.environ.get(name) or "").strip()
    if direct:
        return direct
    if EA_ENV.exists():
        for raw in EA_ENV.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key.strip() == name:
                return value.strip()
    return ""


def browseract_key() -> str:
    for key_name in (
        "BROWSERACT_API_KEY",
        "BROWSERACT_API_KEY_FALLBACK_1",
        "BROWSERACT_API_KEY_FALLBACK_2",
        "BROWSERACT_API_KEY_FALLBACK_3",
    ):
        value = env_value(key_name)
        if value:
            return value
    raise SystemExit("missing BrowserAct key")


def request(path: str, *, task_id: str) -> dict[str, object]:
    query = urllib.parse.urlencode({"task_id": task_id})
    url = f"{API_BASE.rstrip('/')}{path}?{query}"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {browseract_key()}",
            "User-Agent": "fleet-browseract-task/1.0",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as response:
            body = response.read().decode("utf-8", errors="replace")
            try:
                loaded = json.loads(body)
            except json.JSONDecodeError as exc:
                raise SystemExit(json.dumps({"status": "invalid_json", "body": body[:400], "error": str(exc)}))
            if not isinstance(loaded, dict):
                raise SystemExit(json.dumps({"status": "invalid_payload", "body": body[:400]}))
            return loaded
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(json.dumps({"status": "http_error", "code": exc.code, "body": body}))
    except urllib.error.URLError as exc:
        raise SystemExit(json.dumps({"status": "transport_error", "reason": str(exc.reason)}))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("task_id")
    parser.add_argument("--mode", choices=("status", "full"), default="full")
    args = parser.parse_args()
    path = "/get-task-status" if args.mode == "status" else "/get-task"
    body = request(path, task_id=args.task_id)
    print(json.dumps(body, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
