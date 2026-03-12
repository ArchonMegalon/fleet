#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path


EA_ENV_PATH = Path("/docker/EA/.env")
RESULT_PATH = Path("/docker/fleet/state/browseract_bootstrap/materialize/result.json")
DEFAULT_QUERY = "browseract architect"


def load_result() -> dict[str, object]:
    if not RESULT_PATH.exists():
        raise SystemExit("missing_result")
    data = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit("invalid_result")
    return data


def extract_workflow_id(result: dict[str, object]) -> str:
    popup_url = str(result.get("popup_url") or "").strip()
    if "/workflow/" not in popup_url:
        raise SystemExit("missing_popup_url")
    tail = popup_url.split("/workflow/", 1)[1]
    workflow_id = tail.split("/", 1)[0].strip()
    if not workflow_id:
        raise SystemExit("missing_workflow_id")
    return workflow_id


def update_env(workflow_id: str) -> None:
    lines: list[str] = []
    if EA_ENV_PATH.exists():
        lines = EA_ENV_PATH.read_text(encoding="utf-8", errors="ignore").splitlines()
    replacements = {
        "BROWSERACT_ARCHITECT_WORKFLOW_ID": workflow_id,
        "BROWSERACT_ARCHITECT_WORKFLOW_QUERY": DEFAULT_QUERY,
    }
    seen: set[str] = set()
    output: list[str] = []
    for raw in lines:
        if "=" not in raw:
            output.append(raw)
            continue
        key, _ = raw.split("=", 1)
        name = key.strip()
        if name in replacements:
            output.append(f"{name}={replacements[name]}")
            seen.add(name)
        else:
            output.append(raw)
    for name, value in replacements.items():
        if name not in seen:
            output.append(f"{name}={value}")
    EA_ENV_PATH.write_text("\n".join(output).rstrip() + "\n", encoding="utf-8")


def main() -> int:
    result = load_result()
    workflow_id = extract_workflow_id(result)
    update_env(workflow_id)
    print(json.dumps({"status": "ok", "workflow_id": workflow_id, "env": str(EA_ENV_PATH)}, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
