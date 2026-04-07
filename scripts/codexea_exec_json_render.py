#!/usr/bin/env python3
from __future__ import annotations

import json
import sys


def _print(text: str) -> None:
    print(text, flush=True)


def main() -> int:
    cwd = sys.argv[1] if len(sys.argv) > 1 else ""
    pending_commands: dict[str, str] = {}
    command_events: list[dict[str, object]] = []
    passthrough_lines: list[str] = []
    last_tool_output = ""
    last_message = ""

    for raw_line in sys.stdin:
        line = raw_line.rstrip("\n")
        if not line:
            continue
        try:
            event = json.loads(line)
        except Exception:
            passthrough_lines.append(line)
            continue

        event_type = str(event.get("type") or "")
        item = event.get("item") if isinstance(event.get("item"), dict) else {}
        item_type = str(item.get("type") or "")
        item_id = str(item.get("id") or "")

        if event_type == "item.started" and item_type == "command_execution":
            command = str(item.get("command") or "").strip()
            if item_id and command:
                pending_commands[item_id] = command
            continue

        if event_type == "item.completed" and item_type == "command_execution":
            exit_code = item.get("exit_code")
            command = str(item.get("command") or pending_commands.get(item_id) or "").strip()
            aggregated_output = str(item.get("aggregated_output") or "").rstrip("\n")
            command_events.append(
                {
                    "command": command,
                    "exit_code": exit_code,
                    "aggregated_output": aggregated_output,
                }
            )
            if aggregated_output:
                last_tool_output = aggregated_output.strip()
            continue

        if event_type == "item.completed" and item_type == "agent_message":
            text = str(item.get("text") or "").strip()
            if text:
                last_message = text
            continue

    for line in passthrough_lines:
        _print(line)

    if last_message and last_message != last_tool_output:
        _print(last_message)
        return 0

    if not passthrough_lines and len(command_events) == 1:
        command_event = command_events[0]
        if command_event.get("exit_code") == 0:
            aggregated_output = str(command_event.get("aggregated_output") or "").strip()
            if aggregated_output:
                _print(aggregated_output)
                return 0

    for event in command_events:
        command = str(event.get("command") or "").strip()
        exit_code = event.get("exit_code")
        status = "succeeded" if exit_code == 0 else f"failed (exit {exit_code})"
        _print("exec")
        if command:
            if cwd:
                _print(f"{command} in {cwd}")
            else:
                _print(command)
        _print(f" {status}:")
        aggregated_output = str(event.get("aggregated_output") or "").rstrip("\n")
        if aggregated_output:
            _print(aggregated_output)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
