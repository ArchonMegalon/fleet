#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path


def _read_hit_count(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        raw = path.read_text(encoding="utf-8").strip()
        return int(raw or "0")
    except Exception:
        return 0


def _write_hit_count(path: Path, count: int) -> None:
    try:
        path.write_text(f"{count}\n", encoding="utf-8")
    except Exception:
        pass


def _redirect_limit() -> int | None:
    raw = str(os.environ.get("CHUMMER_DESIGN_SUPERVISOR_STATUS_HELPER_REDIRECT_LIMIT", "") or "").strip()
    if not raw:
        return None
    try:
        limit = max(0, int(float(raw)))
    except Exception:
        return None
    return limit


def _trim_output_lines(value: str, *, max_lines: int = 12, max_chars: int = 4096) -> list[str]:
    text = str(value or "").splitlines()
    if max_lines <= 0 or max_chars <= 0:
        return []
    if len(text) > max_lines:
        text = text[:max_lines]
        text.append(f"... output truncated to {max_lines} lines")
    compacted = "\n".join(text)
    if len(compacted) > max_chars:
        compacted = compacted[: max_chars - 39]
        compacted = f"{compacted}\n... output truncated to {max_chars} chars"
        text = compacted.splitlines()
    return text


def _normalize_commands(payload: dict[str, object], telemetry_path: Path) -> list[str]:
    commands = [str(item).strip() for item in (payload.get("first_commands") or []) if str(item).strip()]
    if not commands:
        commands = [f"cat {shlex.quote(str(telemetry_path))}"]
    resolved: list[str] = []
    for item in commands:
        command = item
        if "TASK_LOCAL_TELEMETRY.generated.json" in command and str(telemetry_path) not in command:
            command = re.sub(
                r"(?<![\w./-])TASK_LOCAL_TELEMETRY\.generated\.json(?![\w./-])",
                shlex.quote(str(telemetry_path)),
                command,
            )
        resolved.append(command)
    return resolved


def _command_guidance(commands: list[str], hit_count: int, *, lookahead: int = 0) -> str:
    if not commands:
        return ""
    executed_index = max(0, min(len(commands) - 1, hit_count - 1))
    staged_count = max(1, int(lookahead) + 1)
    staged = commands[executed_index : min(len(commands), executed_index + staged_count)]
    next_index = executed_index + len(staged)
    if next_index < len(commands):
        parts = [f"Helper staged: {'; '.join(staged)}."]
        parts.append(f"Next direct command: {commands[next_index]}.")
        if next_index + 1 < len(commands):
            parts.append(f"Then: {commands[next_index + 1]}.")
        return " ".join(parts)
    return (
        f"Helper staged: {'; '.join(staged)}. "
        "No more helper staging remains; stop calling supervisor status and inspect the target implementation files directly."
    )


def _resolved_commands(
    payload: dict[str, object], telemetry_path: Path, hit_count: int, *, lookahead: int = 0
) -> list[str]:
    commands = _normalize_commands(payload, telemetry_path)
    command_index = max(0, min(len(commands) - 1, hit_count - 1))
    command_count = max(1, int(lookahead) + 1)
    return commands[command_index : min(len(commands), command_index + command_count)]


def _command_reads_repo_context(command: str, telemetry_path: Path) -> bool:
    compact = str(command or "").strip()
    if not compact:
        return False
    if str(telemetry_path) in compact or "TASK_LOCAL_TELEMETRY.generated.json" in compact:
        return False
    return compact.startswith(("cat ", "sed ", "nl ", "rg ", "python3 "))


def _emit_context_progress_once(
    payload: dict[str, object],
    telemetry_path: Path,
    hit_counter_path: Path,
    hit_count: int,
    *,
    lookahead: int = 0,
) -> None:
    commands = _resolved_commands(payload, telemetry_path, hit_count, lookahead=lookahead)
    if not any(_command_reads_repo_context(command, telemetry_path) for command in commands):
        return
    sentinel = hit_counter_path.parent / ".status_helper_context_progress_emitted"
    if sentinel.exists():
        return
    try:
        sentinel.write_text("1\n", encoding="utf-8")
    except Exception:
        pass
    print("task_local_repo_context_read: status helper staged assigned repo files", file=sys.stderr)


def _emit_prefixed_output(prefix: str, text: str, *, file=sys.stdout) -> None:
    for line in str(text or "").splitlines():
        print(f"{prefix}{line}", file=file)


def _emit_resolved_command_outputs(
    payload: dict[str, object], telemetry_path: Path, hit_count: int, *, file=sys.stdout, lookahead: int = 0
) -> None:
    for command in _resolved_commands(payload, telemetry_path, hit_count, lookahead=lookahead):
        print(f"redirected_command: {command}", file=file)
        completed = subprocess.run(
            ["/bin/bash", "-lc", command],
            text=True,
            capture_output=True,
            check=False,
        )
        stdout = str(completed.stdout or "").rstrip("\n")
        stderr = str(completed.stderr or "").rstrip("\n")
        if stdout:
            for line in _trim_output_lines(stdout):
                _emit_prefixed_output("redirected_output: ", line, file=file)
        if stderr:
            for line in _trim_output_lines(stderr):
                _emit_prefixed_output("redirected_output: ", line, file=file)
        if int(completed.returncode) != 0:
            print(f"redirected_output: [exit {completed.returncode}]", file=file)


def _remaining_command_lookahead(payload: dict[str, object], telemetry_path: Path) -> int:
    commands = _normalize_commands(payload, telemetry_path)
    raw = payload.get("status_helper_redirect_lookahead")
    if raw is None:
        raw = os.environ.get("CHUMMER_DESIGN_SUPERVISOR_STATUS_HELPER_REDIRECT_LOOKAHEAD", "")
    text = str(raw).strip().lower()
    if not text:
        return max(0, len(commands))
    if text in {"all", "*"}:
        return max(0, len(commands))
    try:
        return max(0, int(float(text)))
    except Exception:
        return max(0, len(commands))


def _render_redirect(payload: dict[str, object], telemetry_path: Path, hit_counter_path: Path, hit_count: int) -> int:
    print("status_redirected_inside_worker_run")
    print("worker_status_redirected: task_local_telemetry_file")
    lookahead = _remaining_command_lookahead(payload, telemetry_path)
    _emit_resolved_command_outputs(payload, telemetry_path, hit_count, lookahead=lookahead)
    _emit_context_progress_once(payload, telemetry_path, hit_counter_path, hit_count, lookahead=lookahead)
    commands = _normalize_commands(payload, telemetry_path)
    summary = str(payload.get("summary") or payload.get("slice_summary") or payload.get("guidance") or "").strip()
    parts = ["Trace: nested supervisor telemetry helper redirected to task-local telemetry."]
    if summary:
        parts.append(summary)
    guidance = _command_guidance(commands, hit_count, lookahead=lookahead)
    if guidance:
        parts.append(guidance)
    print(" ".join(parts), file=sys.stderr)
    return 0


def _render_repeat_block(
    payload: dict[str, object],
    telemetry_path: Path | None = None,
    *,
    hit_counter_path: Path | None = None,
    hit_count: int = 1,
    emit_summary_json: bool = False,
) -> int:
    commands = [str(item).strip() for item in (payload.get("first_commands") or []) if str(item).strip()]
    summary = str(payload.get("summary") or payload.get("slice_summary") or payload.get("guidance") or "").strip()
    if emit_summary_json and telemetry_path is not None:
        print(json.dumps(_summary_json_payload(payload, telemetry_path, hit_count), separators=(",", ":")))
    print("status_blocked_inside_worker_run", file=sys.stderr)
    print("worker_status_budget_exhausted: task_local_telemetry_file", file=sys.stderr)
    if telemetry_path is not None and hit_counter_path is not None:
        _emit_context_progress_once(payload, telemetry_path, hit_counter_path, hit_count, lookahead=0)
    parts = [
        "Trace: nested supervisor telemetry helpers are blocked in worker runs.",
        "Read TASK_LOCAL_TELEMETRY.generated.json directly and then open the listed repo file.",
        "Repeated helper loop denied.",
    ]
    if summary:
        parts.append(summary)
    if commands:
        parts.append(f"Next: {commands[0]}")
        if len(commands) > 1:
            parts.append(f"Then: {commands[1]}")
    print(" ".join(parts), file=sys.stderr)
    return 0


def _summary_json_payload(payload: dict[str, object], telemetry_path: Path, hit_count: int) -> dict[str, object]:
    eta = payload.get("eta")
    eta_payload = eta if isinstance(eta, dict) else payload
    summary = str(payload.get("summary") or payload.get("slice_summary") or payload.get("guidance") or "").strip()
    command_summary = _command_guidance(
        _normalize_commands(payload, telemetry_path),
        hit_count,
        lookahead=_remaining_command_lookahead(payload, telemetry_path),
    )
    if command_summary:
        summary = f"{summary} Do not call supervisor status again. {command_summary}".strip()
    return {
        "active_runs_count": payload.get("active_runs_count"),
        "remaining_open_milestones": eta_payload.get("remaining_open_milestones"),
        "remaining_not_started_milestones": eta_payload.get("remaining_not_started_milestones"),
        "remaining_in_progress_milestones": eta_payload.get("remaining_in_progress_milestones"),
        "eta_human": eta_payload.get("eta_human"),
        "summary": summary or eta_payload.get("summary"),
    }


def _render_summary_json(
    payload: dict[str, object],
    telemetry_path: Path,
    hit_counter_path: Path,
    hit_count: int,
) -> int:
    redirect_limit = _redirect_limit()
    if redirect_limit is not None and hit_count > redirect_limit:
        return _render_repeat_block(
            payload,
            telemetry_path,
            hit_counter_path=hit_counter_path,
            hit_count=hit_count,
            emit_summary_json=True,
        )
    print(json.dumps(_summary_json_payload(payload, telemetry_path, hit_count), separators=(",", ":")))
    print("status_redirected_inside_worker_run", file=sys.stderr)
    print("worker_status_redirected: task_local_telemetry_file", file=sys.stderr)
    lookahead = _remaining_command_lookahead(payload, telemetry_path)
    _emit_resolved_command_outputs(payload, telemetry_path, hit_count, file=sys.stderr, lookahead=lookahead)
    _emit_context_progress_once(payload, telemetry_path, hit_counter_path, hit_count, lookahead=lookahead)
    commands = _normalize_commands(payload, telemetry_path)
    parts = ["Trace: nested supervisor telemetry helper returned task-local JSON summary and staged the required file reads."]
    guidance = _command_guidance(commands, hit_count, lookahead=lookahead)
    if guidance:
        parts.append(guidance)
    print(" ".join(parts), file=sys.stderr)
    return 0


def main() -> int:
    args = list(sys.argv[1:])
    render_summary_json = False
    if args and args[0] == "--summary-json":
        render_summary_json = True
        args = args[1:]
    telemetry_path = Path(args[0]).expanduser().resolve()
    hit_counter_path = Path(args[1]).expanduser()
    os.environ["CHUMMER_DESIGN_SUPERVISOR_STATUS_HELPER_COUNTER_PATH"] = str(hit_counter_path)
    payload = json.loads(telemetry_path.read_text(encoding="utf-8"))
    hit_count = _read_hit_count(hit_counter_path) + 1
    _write_hit_count(hit_counter_path, hit_count)
    if render_summary_json:
        return _render_summary_json(payload, telemetry_path, hit_counter_path, hit_count)
    redirect_limit = _redirect_limit()
    if redirect_limit is not None and hit_count > redirect_limit:
        return _render_repeat_block(payload, telemetry_path, hit_counter_path=hit_counter_path, hit_count=hit_count)
    return _render_redirect(payload, telemetry_path, hit_counter_path, hit_count)


if __name__ == "__main__":
    raise SystemExit(main())
