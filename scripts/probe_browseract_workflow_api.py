#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import urllib.error
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
    return ""


def request(method: str, path: str, payload: dict[str, object] | None = None) -> dict[str, object]:
    key = browseract_key()
    if not key:
        raise SystemExit("missing BrowserAct key")
    url = API_BASE.rstrip("/") + path
    data = None
    headers = {
        "Authorization": f"Bearer {key}",
        "User-Agent": "fleet-browseract-probe/1.0",
    }
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method.upper())
    try:
        with urllib.request.urlopen(req, timeout=45) as response:
            body = response.read().decode("utf-8", errors="replace")
            return {"ok": True, "code": getattr(response, "status", 200), "body": body[:500]}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return {"ok": False, "code": exc.code, "body": body[:500]}
    except Exception as exc:
        return {"ok": False, "code": 0, "body": f"{type(exc).__name__}:{exc}"}


def main() -> int:
    candidates = [
        ("POST", "/create-workflow", {"name": "chummer6 probe", "description": "probe", "workflow": {}}),
        ("POST", "/save-workflow", {"name": "chummer6 probe", "description": "probe", "workflow": {}}),
        ("POST", "/upsert-workflow", {"name": "chummer6 probe", "description": "probe", "workflow": {}}),
        ("POST", "/create", {"name": "chummer6 probe", "description": "probe", "workflow": {}}),
        ("POST", "/import-workflow", {"name": "chummer6 probe", "description": "probe", "workflow": {}}),
    ]
    results = []
    for method, path, payload in candidates:
        result = request(method, path, payload)
        results.append({"method": method, "path": path, **result})
    print(json.dumps({"results": results}, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
