#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


def _parse_iso(text: str) -> datetime | None:
    normalized = str(text or "").strip()
    if not normalized:
        return None
    try:
        return datetime.fromisoformat(normalized.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def _http_health_ok(url: str, timeout_seconds: float) -> tuple[bool, str]:
    try:
        with urllib.request.urlopen(url, timeout=max(float(timeout_seconds), 0.1)) as response:
            body = response.read(64).decode("utf-8", errors="ignore").strip().lower()
            return response.status == 200 and body.startswith("ok"), f"http_status={response.status}"
    except Exception as exc:  # pragma: no cover
        return False, f"http_error={exc}"


def _heartbeat_fresh(path: Path, max_age_seconds: int) -> tuple[bool, str]:
    if not path.exists():
        return False, "heartbeat_missing"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover
        return False, f"heartbeat_parse_error={exc}"
    updated_at = _parse_iso(str(payload.get("updated_at") or ""))
    if updated_at is None:
        return False, "heartbeat_updated_at_invalid"
    age_seconds = max(0.0, (datetime.now(timezone.utc) - updated_at).total_seconds())
    if age_seconds > max_age_seconds:
        return False, f"heartbeat_stale={int(age_seconds)}s"
    return True, f"heartbeat_fresh={int(age_seconds)}s"


def main() -> int:
    health_url = str(os.environ.get("FLEET_CONTROLLER_HEALTH_URL", "http://127.0.0.1:8090/health") or "").strip()
    heartbeat_path = Path(
        str(
            os.environ.get(
                "FLEET_CONTROLLER_HEARTBEAT_PATH",
                "/var/lib/codex-fleet/controller-heartbeat.json",
            )
            or "/var/lib/codex-fleet/controller-heartbeat.json"
        ).strip()
    )
    timeout_seconds = float(os.environ.get("FLEET_CONTROLLER_HEALTH_TIMEOUT_SECONDS", "3") or "3")
    max_age_seconds = int(os.environ.get("FLEET_CONTROLLER_HEARTBEAT_MAX_AGE_SECONDS", "45") or "45")
    allow_heartbeat_only = str(os.environ.get("FLEET_CONTROLLER_HEALTH_ALLOW_HEARTBEAT_ONLY", "0") or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }

    http_ok, http_reason = _http_health_ok(health_url, timeout_seconds)
    if http_ok:
        print("ok")
        return 0

    heartbeat_ok, heartbeat_reason = _heartbeat_fresh(heartbeat_path, max_age_seconds)
    if heartbeat_ok and allow_heartbeat_only:
        print(f"ok ({http_reason}; {heartbeat_reason})")
        return 0

    print(f"unhealthy ({http_reason}; {heartbeat_reason})", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
