#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

EA_ENV_PATH = Path("/docker/EA/.env")


def load_result(path: Path) -> dict[str, object]:
    if not path.exists():
        raise SystemExit(f"missing_result:{path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit("invalid_result")
    return data


def extract_workflow_id(result: dict[str, object]) -> str:
    for key in ("workflow_id", "id", "_id", "workflowId"):
        value = str(result.get(key) or "").strip()
        if value:
            return value
    data = result.get("data")
    if isinstance(data, dict):
        for key in ("workflow_id", "id", "_id", "workflowId"):
            value = str(data.get(key) or "").strip()
            if value:
                return value
    popup_url = str(result.get("popup_url") or "").strip()
    if "/workflow/" not in popup_url:
        raise SystemExit("missing_popup_url")
    tail = popup_url.split("/workflow/", 1)[1]
    workflow_id = tail.split("/", 1)[0].split("?", 1)[0].strip()
    if not workflow_id:
        raise SystemExit("missing_workflow_id")
    return workflow_id


def update_env(assignments: dict[str, str]) -> None:
    lines: list[str] = []
    if EA_ENV_PATH.exists():
        lines = EA_ENV_PATH.read_text(encoding="utf-8", errors="ignore").splitlines()
    seen: set[str] = set()
    output: list[str] = []
    for raw in lines:
        if "=" not in raw:
            output.append(raw)
            continue
        key, _ = raw.split("=", 1)
        name = key.strip()
        if name in assignments:
            output.append(f"{name}={assignments[name]}")
            seen.add(name)
        else:
            output.append(raw)
    for name, value in assignments.items():
        if name not in seen:
            output.append(f"{name}={value}")
    EA_ENV_PATH.write_text("\n".join(output).rstrip() + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Cache a named BrowserAct workflow id into EA local env.")
    parser.add_argument("--result", required=True)
    parser.add_argument("--env-id", required=True)
    parser.add_argument("--env-query", default="")
    args = parser.parse_args()

    result = load_result(Path(args.result))
    workflow_id = extract_workflow_id(result)
    assignments = {str(args.env_id).strip(): workflow_id}
    query_name = str(args.env_query).strip()
    if query_name:
        assignments[query_name] = str(result.get("workflow_name") or "").strip()
    update_env(assignments)
    print(json.dumps({"status": "ok", "workflow_id": workflow_id, "env": str(EA_ENV_PATH), "keys": sorted(assignments)}, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
