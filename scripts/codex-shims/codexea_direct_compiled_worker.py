#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


def _print(text: str, *, stream: Any = sys.stdout) -> None:
    print(text, file=stream, flush=True)


def _normalize_responses_url(base_url: str) -> str:
    normalized = str(base_url or "").strip() or "http://127.0.0.1:8090"
    if normalized.endswith("/v1/responses"):
        return normalized
    if normalized.endswith("/v1"):
        return f"{normalized}/responses"
    return f"{normalized.rstrip('/')}/v1/responses"


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _strip_fences(text: str) -> str:
    stripped = str(text or "").strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped, flags=re.IGNORECASE)
        stripped = re.sub(r"\s*```$", "", stripped)
    return stripped.strip()


def _extract_json_payload(text: str) -> dict[str, Any]:
    stripped = _strip_fences(text)
    candidates = [stripped]
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start >= 0 and end > start:
        candidates.append(stripped[start : end + 1])
    for candidate in candidates:
        try:
            payload = json.loads(candidate)
        except Exception:
            continue
        if isinstance(payload, dict):
            return payload
    raise ValueError("response did not contain a JSON object")


def _extract_labeled_value(text: str, label: str) -> str:
    pattern = re.compile(rf"(?im)^{re.escape(label)}\s*:\s*(.+)$")
    match = pattern.search(str(text or ""))
    return str(match.group(1) or "").strip() if match else ""


def _extract_diff_block(text: str) -> str:
    rendered = str(text or "")
    fence_match = re.search(r"```(?:diff|patch|text)?\s*(diff --git .*?)```", rendered, flags=re.IGNORECASE | re.DOTALL)
    if fence_match:
        return str(fence_match.group(1) or "").strip()
    match = re.search(r"(?m)^diff --git ", rendered)
    if not match:
        return ""
    diff_start = match.start()
    diff_end = len(rendered)
    for label in ("What shipped", "What remains", "Exact blocker", "Verify command", "Summary"):
        label_match = re.search(rf"(?im)^{re.escape(label)}\s*:", rendered[diff_start:])
        if label_match and diff_start + label_match.start() > diff_start:
            diff_end = min(diff_end, diff_start + label_match.start())
    return rendered[diff_start:diff_end].strip()


def _extract_candidate_payload(text: str) -> dict[str, Any]:
    try:
        return _extract_json_payload(text)
    except ValueError:
        pass
    diff_text = _extract_diff_block(text)
    shipped = _extract_labeled_value(text, "What shipped") or _extract_labeled_value(text, "Summary")
    remains = _extract_labeled_value(text, "What remains")
    blocker = _extract_labeled_value(text, "Exact blocker")
    verify_command = _extract_labeled_value(text, "Verify command")
    if diff_text.startswith("diff --git "):
        return {
            "decision": "patch",
            "unified_diff": diff_text,
            "summary": shipped or "Applied a direct compiled-worker patch.",
            "what_remains": remains or "none",
            "exact_blocker": blocker or "none",
            "verify_command": verify_command,
        }
    if shipped or remains or blocker:
        return {
            "decision": "blocked",
            "summary": shipped,
            "what_remains": remains or "unknown",
            "exact_blocker": blocker or "model returned no patch diff",
            "verify_command": verify_command,
        }
    raise ValueError("response did not contain a JSON object or salvageable patch payload")


def _design_mirror_publish_automation(payload: dict[str, Any], work_packet: dict[str, Any]) -> dict[str, str]:
    automation = work_packet.get("automation") if isinstance(work_packet.get("automation"), dict) else {}
    if automation:
        kind = str(automation.get("kind") or "").strip().lower()
        if kind == "design_mirror_publish":
            return {
                "kind": "design_mirror_publish",
                "project_id": str(automation.get("project_id") or "").strip(),
                "script_path": str(automation.get("script_path") or "").strip(),
            }
    owned_surfaces = [
        str(item).strip()
        for item in (work_packet.get("owned_surfaces") or payload.get("queue_package", {}).get("owned_surfaces") or [])
        if str(item).strip()
    ]
    surface = next((item for item in owned_surfaces if item.startswith("design_mirror:")), "")
    if not surface:
        return {}
    project_id = surface.split(":", 1)[1].strip()
    if not project_id:
        return {}
    return {
        "kind": "design_mirror_publish",
        "project_id": project_id,
        "script_path": "/docker/chummercomplete/chummer-design/scripts/ai/publish_local_mirrors.py",
    }


def _parse_mirror_publish_changed_paths(output_text: str) -> list[str]:
    changed: list[str] = []
    for raw_line in str(output_text or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("update ") or line.startswith("remove "):
            _, _, rel_path = line.partition(" ")
            rel_path = rel_path.strip()
            if rel_path and rel_path not in changed:
                changed.append(rel_path)
    return changed


def _extract_response_output_text(response: dict[str, Any]) -> str:
    direct_text = str(response.get("output_text") or "").strip()
    if direct_text:
        return direct_text

    fragments: list[str] = []

    def visit(value: Any) -> None:
        if isinstance(value, str):
            text = value.strip()
            if text:
                fragments.append(text)
            return
        if isinstance(value, dict):
            part_type = str(value.get("type") or "").strip().lower()
            if part_type in {"reasoning", "summary_text"}:
                return
            for key, nested in value.items():
                if key in {"annotations", "id", "status", "role"}:
                    continue
                if key == "type" and part_type:
                    continue
                visit(nested)
            return
        if isinstance(value, list):
            for item in value:
                visit(item)

    visit(response.get("output"))
    return "\n".join(fragment for fragment in fragments if fragment).strip()


def _resolve_target_abspaths(repo_root: Path, work_packet: dict[str, Any]) -> list[Path]:
    values = work_packet.get("target_file_abspaths")
    if isinstance(values, list) and values:
        return [Path(str(item)).resolve() for item in values if str(item or "").strip()]
    resolved: list[Path] = []
    values = work_packet.get("target_files")
    if isinstance(values, list):
        for item in values:
            text = str(item or "").strip()
            if text:
                resolved.append((repo_root / text).resolve())
    return resolved


def _path_is_within(root: Path, candidate: Path) -> bool:
    try:
        candidate.resolve().relative_to(root.resolve())
        return True
    except Exception:
        return False


def _compiled_worker_probe_terms(payload: dict[str, Any], work_packet: dict[str, Any]) -> list[str]:
    raw_values = [
        str(work_packet.get("task") or "").strip(),
        str(payload.get("summary") or "").strip(),
        str(payload.get("scope_label") or "").strip(),
    ]
    raw_values.extend(str(item).strip() for item in (work_packet.get("frontier_briefs") or []) if str(item).strip())
    stopwords = {
        "the",
        "and",
        "for",
        "with",
        "that",
        "this",
        "from",
        "into",
        "under",
        "after",
        "before",
        "work",
        "open",
        "keep",
        "land",
        "proof",
        "repo",
        "local",
        "current",
        "frontier",
        "closeout",
        "task",
        "none",
    }
    terms: list[str] = []
    for token in re.split(r"[^A-Za-z0-9]+", " ".join(raw_values).lower()):
        normalized = token.strip()
        if len(normalized) < 3 or normalized in stopwords:
            continue
        if normalized not in terms:
            terms.append(normalized)
    return terms[:12]


def _score_directory_candidate(path: Path, *, probe_terms: list[str]) -> int:
    lowered = str(path).lower()
    score = 0
    if lowered.endswith(".cs"):
        score += 140
    elif lowered.endswith(".axaml") or lowered.endswith(".xaml") or lowered.endswith(".razor"):
        score += 120
    elif lowered.endswith(".py"):
        score += 90
    elif lowered.endswith(".sh"):
        score += 80
    elif lowered.endswith(".md"):
        score += 60
    elif lowered.endswith(".yaml") or lowered.endswith(".yml") or lowered.endswith(".json"):
        score += 50
    if any(token in lowered for token in ("workspace", "route", "desktop", "mirror", "fleet", "authority", "proof", "registry", "handoff", "window", "service")):
        score += 60
    score += sum(10 for term in probe_terms if term and term in lowered)
    return score


def _expand_directory_targets(base_dir: Path, *, probe_terms: list[str], limit: int = 6) -> list[Path]:
    if not base_dir.is_dir():
        return []
    candidates: list[tuple[int, Path]] = []
    seen = 0
    for path in base_dir.rglob("*"):
        if seen >= 400:
            break
        seen += 1
        if not path.is_file():
            continue
        lowered = str(path).lower()
        if "/bin/" in lowered or "/obj/" in lowered or "/.git/" in lowered:
            continue
        candidates.append((_score_directory_candidate(path, probe_terms=probe_terms), path.resolve()))
    candidates.sort(key=lambda item: (-item[0], str(item[1])))
    return [path for _score, path in candidates[: max(1, limit)]]


def _materialize_target_paths(
    repo_root: Path,
    target_paths: list[Path],
    allowed_paths: list[Path],
    *,
    payload: dict[str, Any],
    work_packet: dict[str, Any],
) -> list[Path]:
    probe_terms = _compiled_worker_probe_terms(payload, work_packet)
    candidate_inputs = [path.resolve() for path in target_paths if str(path).strip()]
    if not candidate_inputs:
        candidate_inputs = [path.resolve() for path in allowed_paths if str(path).strip()]
    in_repo_inputs = [path for path in candidate_inputs if _path_is_within(repo_root, path)]
    if in_repo_inputs:
        candidate_inputs = in_repo_inputs
    materialized: list[Path] = []
    for path in candidate_inputs:
        if path.is_file():
            if path not in materialized:
                materialized.append(path)
            continue
        if path.is_dir():
            for expanded in _expand_directory_targets(path, probe_terms=probe_terms, limit=6):
                if _path_is_within(repo_root, expanded) and expanded not in materialized:
                    materialized.append(expanded)
        if len(materialized) >= 12:
            break
    return materialized[:12]


def _resolve_allowed_abspaths(repo_root: Path, work_packet: dict[str, Any], target_paths: list[Path]) -> list[Path]:
    resolved: list[Path] = []
    values = work_packet.get("allowed_paths")
    if isinstance(values, list):
        for item in values:
            text = str(item or "").strip()
            if not text:
                continue
            candidate = Path(text)
            resolved.append(candidate.resolve() if candidate.is_absolute() else (repo_root / candidate).resolve())
    if not resolved:
        resolved = sorted({path.parent.resolve() for path in target_paths})
    return resolved


def _run_shell(
    command: str,
    *,
    cwd: Path,
    timeout_seconds: int,
) -> tuple[int, str]:
    completed = subprocess.run(
        ["/bin/bash", "-lc", command],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        check=False,
    )
    rendered_parts: list[str] = []
    stdout = str(completed.stdout or "").strip()
    stderr = str(completed.stderr or "").strip()
    if stdout:
        rendered_parts.append(stdout)
    if stderr:
        rendered_parts.append(stderr)
    rendered = "\n".join(rendered_parts).strip() or "[no output]"
    return int(completed.returncode or 0), rendered


def _run_design_mirror_publish_fast_path(
    *,
    payload: dict[str, Any],
    work_packet: dict[str, Any],
    repo_root: Path,
    verification_commands: list[str],
    output_last_message_path: Path,
) -> int | None:
    automation = _design_mirror_publish_automation(payload, work_packet)
    if str(automation.get("kind") or "").strip().lower() != "design_mirror_publish":
        return None
    project_id = str(automation.get("project_id") or "").strip()
    script_path_text = str(automation.get("script_path") or "").strip()
    if not project_id or not script_path_text:
        _print("Trace: direct compiled worker fast path skipped (missing design-mirror automation metadata)", stream=sys.stderr)
        return None
    script_path = Path(script_path_text).resolve()
    if not script_path.is_file():
        _print(f"Trace: direct compiled worker fast path skipped (missing script {script_path})", stream=sys.stderr)
        return None

    check_command = f"python3 {shlex.quote(str(script_path))} --check --repo {shlex.quote(project_id)}"
    write_command = f"python3 {shlex.quote(str(script_path))} --repo {shlex.quote(project_id)}"

    _print(f"/usr/bin/bash -lc {shlex.quote(check_command)}")
    initial_check_exit, initial_check_output = _run_shell(check_command, cwd=repo_root, timeout_seconds=240)
    if initial_check_output:
        _print(_truncate(initial_check_output, max_lines=220, max_chars=24000))
    if initial_check_exit not in {0, 1}:
        _write_closeout(
            output_last_message_path,
            shipped="none",
            remains="repair the design mirror automation path",
            blocker=f"design mirror preflight failed: {check_command} (exit {initial_check_exit})",
        )
        _print("Trace: direct compiled worker fast path failed during preflight", stream=sys.stderr)
        return 3

    changed_paths: list[str] = []
    if initial_check_exit == 1:
        _print(f"/usr/bin/bash -lc {shlex.quote(write_command)}")
        write_exit, write_output = _run_shell(write_command, cwd=repo_root, timeout_seconds=240)
        if write_output:
            _print(_truncate(write_output, max_lines=220, max_chars=24000))
        if write_exit != 0:
            _write_closeout(
                output_last_message_path,
                shipped="none",
                remains="repair the design mirror automation path",
                blocker=f"design mirror publish failed: {write_command} (exit {write_exit})",
            )
            _print("Trace: direct compiled worker fast path failed during publish", stream=sys.stderr)
            return 3
        changed_paths = _parse_mirror_publish_changed_paths(write_output)
    else:
        _print("Trace: direct compiled worker fast path found the design mirror already in sync", stream=sys.stderr)

    _print(f"/usr/bin/bash -lc {shlex.quote(check_command)}")
    verify_exit, verify_output = _run_shell(check_command, cwd=repo_root, timeout_seconds=240)
    if verify_output:
        _print(_truncate(verify_output, max_lines=220, max_chars=24000))
    if verify_exit != 0:
        _write_closeout(
            output_last_message_path,
            shipped="design mirror publish attempted",
            remains="repair remaining mirror drift",
            blocker=f"design mirror verification failed: {check_command} (exit {verify_exit})",
        )
        _print("Trace: direct compiled worker fast path failed verification", stream=sys.stderr)
        return 3

    for verify_command in verification_commands:
        command = str(verify_command or "").strip()
        if not command or command == check_command:
            continue
        _print(f"/usr/bin/bash -lc {shlex.quote(command)}")
        extra_exit, extra_output = _run_shell(command, cwd=repo_root, timeout_seconds=240)
        if extra_output:
            _print(_truncate(extra_output, max_lines=220, max_chars=24000))
        if extra_exit != 0:
            _write_closeout(
                output_last_message_path,
                shipped="design mirror publish completed",
                remains="repair follow-up verification failures",
                blocker=f"verification command failed: {command} (exit {extra_exit})",
            )
            _print("Trace: direct compiled worker fast path failed follow-up verification", stream=sys.stderr)
            return 3

    if changed_paths:
        rendered_diff = _render_git_diff(repo_root, changed_paths)
        if rendered_diff:
            _print(rendered_diff)
    shipped = (
        f"Published the repo-local design mirror for {project_id} and verified it is in sync."
        if changed_paths
        else f"Verified the repo-local design mirror for {project_id} was already in sync."
    )
    _write_closeout(
        output_last_message_path,
        shipped=shipped,
        remains="none",
        blocker="none",
    )
    _print(f"What shipped: {shipped}")
    _print("")
    _print("What remains: none")
    _print("")
    _print("Exact blocker: none")
    return 0


def _truncate(text: str, *, max_lines: int, max_chars: int) -> str:
    rendered = str(text or "").strip()
    if not rendered:
        return "[no output]"
    lines = rendered.splitlines()
    if len(lines) > max_lines:
        rendered = "\n".join(lines[:max_lines] + ["... output truncated"])
    if len(rendered) > max_chars:
        rendered = rendered[: max_chars - 3].rstrip() + "..."
    return rendered


def _collect_context_sections(
    payload: dict[str, Any],
    repo_root: Path,
    work_packet: dict[str, Any],
    target_paths: list[Path],
) -> list[str]:
    sections: list[str] = []
    seen_commands: set[str] = set()
    commands: list[str] = []
    for source in (
        payload.get("first_commands"),
        payload.get("preferred_repo_file_commands"),
        work_packet.get("first_reads"),
    ):
        if isinstance(source, list):
            for item in source:
                command = " ".join(str(item or "").split()).strip()
                if command:
                    commands.append(command)
    timeout_seconds = max(5, int(os.environ.get("CODEXEA_DIRECT_COMPILED_CONTEXT_TIMEOUT_SECONDS", "20") or "20"))
    max_lines = max(20, int(os.environ.get("CODEXEA_DIRECT_COMPILED_CONTEXT_MAX_LINES", "180") or "180"))
    max_chars = max(2000, int(os.environ.get("CODEXEA_DIRECT_COMPILED_CONTEXT_MAX_CHARS", "24000") or "24000"))
    for raw_command in commands[:6]:
        command = " ".join(str(raw_command or "").split()).strip()
        if not command:
            continue
        seen_commands.add(command)
        exit_code, rendered = _run_shell(command, cwd=repo_root, timeout_seconds=timeout_seconds)
        body = _truncate(rendered, max_lines=max_lines, max_chars=max_chars)
        section_lines = [f"$ {command}"]
        if exit_code != 0:
            section_lines.append(f"[exit {exit_code}]")
        section_lines.append(body)
        sections.append("\n".join(section_lines))
    extra_paths = payload.get("paths")
    if isinstance(extra_paths, dict):
        for raw_path in list(extra_paths.values())[:6]:
            text = str(raw_path or "").strip()
            if not text:
                continue
            candidate = Path(text)
            if not candidate.is_file():
                continue
            command = f"sed -n '1,220p' {shlex.quote(str(candidate))}"
            if command in seen_commands:
                continue
            exit_code, rendered = _run_shell(command, cwd=repo_root, timeout_seconds=timeout_seconds)
            body = _truncate(rendered, max_lines=max_lines, max_chars=max_chars)
            section_lines = [f"$ {command}"]
            if exit_code != 0:
                section_lines.append(f"[exit {exit_code}]")
            section_lines.append(body)
            sections.append("\n".join(section_lines))
            seen_commands.add(command)
            if len(sections) >= 8:
                break
    for target_path in target_paths[:6]:
        try:
            relative_target = target_path.resolve().relative_to(repo_root.resolve())
        except Exception:
            continue
        command = f"sed -n '1,220p' {shlex.quote(str(repo_root / relative_target))}"
        if command in seen_commands:
            continue
        exit_code, rendered = _run_shell(command, cwd=repo_root, timeout_seconds=timeout_seconds)
        body = _truncate(rendered, max_lines=max_lines, max_chars=max_chars)
        section_lines = [f"$ {command}"]
        if exit_code != 0:
            section_lines.append(f"[exit {exit_code}]")
        section_lines.append(body)
        sections.append("\n".join(section_lines))
        if len(sections) >= 8:
            break
    return sections


def _build_input_prompt(
    *,
    payload: dict[str, Any],
    repo_root: Path,
    work_packet: dict[str, Any],
    target_paths: list[Path],
    allowed_paths: list[Path],
    context_sections: list[str],
    previous_error: str = "",
) -> str:
    package_id = str(work_packet.get("package_id") or payload.get("package_id") or "").strip()
    task = str(work_packet.get("task") or payload.get("summary") or "").strip()
    owned_surfaces = [str(item).strip() for item in (work_packet.get("owned_surfaces") or []) if str(item).strip()]
    verification_commands = [str(item).strip() for item in (work_packet.get("verify_commands") or []) if str(item).strip()]
    lines = [
        "You are a direct compiled patch worker operating on a local git repo.",
        "Return strict JSON only. Do not use markdown fences.",
        "Do not ask questions. Do not say the task is missing. Do not emit prose outside the JSON object.",
        "",
        "Return this schema exactly:",
        '{"decision":"patch|blocked","unified_diff":"diff --git ...","summary":"...","what_remains":"...","exact_blocker":"none|...","verify_command":"..."}',
        "",
        "Rules:",
        "- `decision` must be `patch` unless the task is truly blocked by missing repo-local information.",
        "- `unified_diff` must be a valid unified diff rooted at the repo root and must start with `diff --git` when `decision` is `patch`.",
        "- Only touch files under the allowed paths listed below.",
        "- Prefer the listed target files first. Small adjacent implementation edits under allowed paths are allowed when necessary.",
        "- Keep the patch as small and concrete as possible.",
        "- Use one listed verification command when possible.",
        "",
        f"Repo root: {repo_root}",
    ]
    if package_id:
        lines.append(f"Package id: {package_id}")
    if task:
        lines.append(f"Task: {task}")
    if owned_surfaces:
        lines.append("Owned surfaces:")
        lines.extend(f"- {item}" for item in owned_surfaces[:8])
    lines.append("Allowed paths:")
    lines.extend(f"- {path}" for path in allowed_paths[:16])
    lines.append("Preferred target files:")
    lines.extend(f"- {path}" for path in target_paths[:12])
    if verification_commands:
        lines.append("Verification commands:")
        lines.extend(f"- {item}" for item in verification_commands[:4])
    if previous_error:
        lines.extend(["", "Previous attempt failure to correct:", previous_error])
    if context_sections:
        lines.append("")
        lines.append("Prepared repo context:")
        for section in context_sections:
            lines.append("```text")
            lines.append(section)
            lines.append("```")
    return "\n".join(lines).strip()


def _request_json(
    *,
    method: str,
    url: str,
    payload: dict[str, Any] | None,
    principal_id: str,
    codex_profile: str,
    account_alias: str,
    account_env: str,
    api_token: str,
    timeout_seconds: int,
) -> dict[str, Any]:
    headers = {
        "X-EA-Principal-ID": principal_id,
    }
    if payload is not None:
        headers["Content-Type"] = "application/json"
    if codex_profile:
        headers["X-EA-Codex-Profile"] = codex_profile
    if account_alias:
        headers["X-EA-Onemin-Account-Alias"] = account_alias
    if account_env:
        headers["X-EA-Onemin-Account-Env"] = account_env
    if api_token:
        headers["Authorization"] = f"Bearer {api_token}"
        headers["X-EA-Api-Token"] = api_token
        headers["X-API-Token"] = api_token
    request = urllib.request.Request(
        url,
        method=method.upper(),
        headers=headers,
        data=json.dumps(payload, ensure_ascii=True).encode("utf-8") if payload is not None else None,
    )
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        body = response.read().decode("utf-8", errors="replace")
    parsed = json.loads(body)
    if not isinstance(parsed, dict):
        raise ValueError("responses payload is not an object")
    return parsed


def _post_responses_request(
    *,
    url: str,
    model: str,
    prompt: str,
    principal_id: str,
    codex_profile: str,
    account_alias: str,
    account_env: str,
    api_token: str,
    timeout_seconds: int,
) -> dict[str, Any]:
    request_payload = {
        "model": model,
        "instructions": "Return strict JSON only. No markdown fences. No prose outside the JSON object.",
        "input": prompt,
        "metadata": {
            "codexea_direct_compiled_worker": True,
            "principal_id": principal_id,
            "codex_profile": codex_profile,
        },
    }
    return _request_json(
        method="POST",
        url=url,
        payload=request_payload,
        principal_id=principal_id,
        codex_profile=codex_profile,
        account_alias=account_alias,
        account_env=account_env,
        api_token=api_token,
        timeout_seconds=timeout_seconds,
    )


def _poll_response_until_terminal(
    *,
    create_response: dict[str, Any],
    responses_url: str,
    principal_id: str,
    codex_profile: str,
    account_alias: str,
    account_env: str,
    api_token: str,
    timeout_seconds: int,
) -> dict[str, Any]:
    current = dict(create_response)
    deadline = time.monotonic() + max(5, timeout_seconds)
    poll_interval = max(
        0.25,
        float(os.environ.get("CODEXEA_DIRECT_COMPILED_POLL_INTERVAL_SECONDS", "2") or "2"),
    )
    base_root = responses_url
    if "/v1/responses" in base_root:
        base_root = base_root.split("/v1/responses", 1)[0] or base_root
    while True:
        status = str(current.get("status") or "").strip().lower()
        if status in {"completed", "failed", "cancelled"}:
            return current
        response_id = str(current.get("id") or "").strip()
        poll_hint = str(current.get("background_poll_url") or "").strip()
        poll_url = urllib.parse.urljoin(f"{base_root.rstrip('/')}/", poll_hint) if poll_hint else ""
        if not poll_url and response_id:
            poll_url = f"{responses_url.rstrip('/')}/{response_id}"
        if not poll_url:
            return current
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            descriptor = response_id or poll_hint or "unknown"
            raise TimeoutError(f"response {descriptor} did not reach a terminal state within {timeout_seconds}s")
        time.sleep(min(poll_interval, max(0.0, remaining)))
        try:
            current = _request_json(
                method="GET",
                url=poll_url,
                payload=None,
                principal_id=principal_id,
                codex_profile=codex_profile,
                account_alias=account_alias,
                account_env=account_env,
                api_token=api_token,
                timeout_seconds=max(5, int(deadline - time.monotonic())),
            )
        except urllib.error.HTTPError as exc:
            if int(getattr(exc, "code", 0) or 0) == 404:
                continue
            raise


def _allowed_relative_path(relative_path: str, allowed_paths: list[Path], repo_root: Path) -> bool:
    normalized = Path(relative_path)
    if normalized.is_absolute() or ".." in normalized.parts:
        return False
    candidate = (repo_root / normalized).resolve()
    for allowed in allowed_paths:
        try:
            candidate.relative_to(allowed)
            return True
        except Exception:
            continue
    return False


def _diff_changed_relative_paths(diff_text: str) -> list[str]:
    changed: list[str] = []
    for raw_line in str(diff_text or "").splitlines():
        line = raw_line.strip()
        for prefix in ("+++ b/", "--- a/"):
            if line.startswith(prefix):
                relative = line[len(prefix) :].strip()
                if relative and relative != "/dev/null" and relative not in changed:
                    changed.append(relative)
    return changed


def _apply_diff(repo_root: Path, diff_text: str) -> tuple[bool, str]:
    normalized_diff = str(diff_text or "").replace("\r\n", "\n")
    if normalized_diff and not normalized_diff.endswith("\n"):
        normalized_diff += "\n"
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as handle:
        handle.write(normalized_diff)
        patch_path = Path(handle.name)
    try:
        apply_args = [
            "git",
            "-C",
            str(repo_root),
            "apply",
            "--check",
            "--whitespace=nowarn",
            "--recount",
            "--unidiff-zero",
            str(patch_path),
        ]
        check = subprocess.run(
            apply_args,
            capture_output=True,
            text=True,
            check=False,
        )
        if int(check.returncode or 0) != 0:
            return False, _truncate(
                "\n".join(
                    item for item in (check.stdout or "", check.stderr or "") if str(item).strip()
                ),
                max_lines=80,
                max_chars=12000,
            )
        apply_args = [
            "git",
            "-C",
            str(repo_root),
            "apply",
            "--whitespace=nowarn",
            "--recount",
            "--unidiff-zero",
            str(patch_path),
        ]
        apply_run = subprocess.run(
            apply_args,
            capture_output=True,
            text=True,
            check=False,
        )
        if int(apply_run.returncode or 0) != 0:
            return False, _truncate(
                "\n".join(
                    item for item in (apply_run.stdout or "", apply_run.stderr or "") if str(item).strip()
                ),
                max_lines=80,
                max_chars=12000,
            )
        return True, ""
    finally:
        patch_path.unlink(missing_ok=True)


def _render_git_diff(repo_root: Path, changed_paths: list[str]) -> str:
    if not changed_paths:
        return ""
    completed = subprocess.run(
        ["git", "-C", str(repo_root), "diff", "--", *changed_paths],
        capture_output=True,
        text=True,
        check=False,
    )
    return _truncate(completed.stdout or completed.stderr or "", max_lines=220, max_chars=24000)


def _write_closeout(path: Path, *, shipped: str, remains: str, blocker: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        (
            f"What shipped: {shipped.strip() or 'none recorded'}\n\n"
            f"What remains: {remains.strip() or 'none recorded'}\n\n"
            f"Exact blocker: {blocker.strip() or 'none'}\n"
        ),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Direct compiled patch-worker fallback for CodexEA.")
    parser.add_argument("--output-last-message", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--lane", default="")
    parser.add_argument("--run-dir", default=os.environ.get("CHUMMER_DESIGN_SUPERVISOR_ACTIVE_RUN_DIR", ""))
    args = parser.parse_args()

    run_dir = Path(str(args.run_dir or "").strip())
    if not run_dir.is_dir():
        _print("Trace: direct compiled worker fallback skipped (missing run dir)", stream=sys.stderr)
        return 2
    telemetry_path = run_dir / "TASK_LOCAL_TELEMETRY.generated.json"
    if not telemetry_path.is_file():
        _print("Trace: direct compiled worker fallback skipped (missing telemetry)", stream=sys.stderr)
        return 2

    payload = _load_json(telemetry_path)
    contract = str(payload.get("execution_contract") or "").strip().lower()
    work_packet = payload.get("work_packet") if isinstance(payload.get("work_packet"), dict) else {}
    schema = str(work_packet.get("schema") or "").strip().lower()
    if contract != "compiled_patch_worker" and schema != "compiled_patch_worker/v1":
        _print(
            f"Trace: direct compiled worker fallback skipped (contract={contract or schema or 'unknown'})",
            stream=sys.stderr,
        )
        return 2

    repo_root_text = str(work_packet.get("repo_root") or payload.get("paths", {}).get("package_repo_root") or "").strip()
    if not repo_root_text:
        _print("Trace: direct compiled worker fallback skipped (missing repo root)", stream=sys.stderr)
        return 2
    repo_root = Path(repo_root_text).resolve()
    if not repo_root.is_dir():
        _print(f"Trace: direct compiled worker fallback skipped (missing repo root {repo_root})", stream=sys.stderr)
        return 2

    raw_target_paths = _resolve_target_abspaths(repo_root, work_packet)
    allowed_paths = _resolve_allowed_abspaths(repo_root, work_packet, raw_target_paths)
    target_paths = _materialize_target_paths(
        repo_root,
        raw_target_paths,
        allowed_paths,
        payload=payload,
        work_packet=work_packet,
    )
    verification_commands = [str(item).strip() for item in (work_packet.get("verify_commands") or []) if str(item).strip()]
    automation_exit = _run_design_mirror_publish_fast_path(
        payload=payload,
        work_packet=work_packet,
        repo_root=repo_root,
        verification_commands=verification_commands,
        output_last_message_path=Path(args.output_last_message),
    )
    if automation_exit is not None:
        return automation_exit
    if not target_paths:
        _print("Trace: direct compiled worker fallback skipped (no target files)", stream=sys.stderr)
        return 2
    context_sections = _collect_context_sections(payload, repo_root, work_packet, target_paths)

    responses_base_url = str(
        os.environ.get("CODEXEA_RESPONSES_BASE_URL")
        or os.environ.get("EA_BASE_URL")
        or os.environ.get("EA_MCP_BASE_URL")
        or ""
    ).strip()
    responses_url = _normalize_responses_url(responses_base_url)
    principal_id = (
        str(os.environ.get("EA_PRINCIPAL_ID") or "").strip()
        or str(os.environ.get("EA_MCP_PRINCIPAL_ID") or "").strip()
        or "codexea-direct-compiled-worker"
    )
    codex_profile = str(os.environ.get("CODEXEA_RESPONSES_HEADER_EA_CODEX_PROFILE") or args.lane or "").strip()
    account_alias = str(os.environ.get("EA_ONEMIN_ACCOUNT_ALIAS") or os.environ.get("CODEXEA_RESPONSES_HEADER_EA_ONEMIN_ACCOUNT_ALIAS") or "").strip()
    account_env = str(os.environ.get("EA_ONEMIN_ACCOUNT_ENV_NAME") or os.environ.get("CODEXEA_RESPONSES_HEADER_EA_ONEMIN_ACCOUNT_ENV_NAME") or "").strip()
    api_token = str(os.environ.get("EA_MCP_API_TOKEN") or os.environ.get("EA_API_TOKEN") or os.environ.get("CODEXEA_RESPONSES_AUTH_TOKEN") or "").strip()
    timeout_seconds = max(30, int(os.environ.get("CODEXEA_DIRECT_COMPILED_RESPONSE_TIMEOUT_SECONDS", "180") or "180"))
    max_attempts = max(1, int(os.environ.get("CODEXEA_DIRECT_COMPILED_MAX_ATTEMPTS", "3") or "3"))

    previous_error = ""
    changed_paths: list[str] = []
    raw_response_path = run_dir / "direct_compiled_worker_last_response.txt"
    for attempt in range(1, max_attempts + 1):
        prompt = _build_input_prompt(
            payload=payload,
            repo_root=repo_root,
            work_packet=work_packet,
            target_paths=target_paths,
            allowed_paths=allowed_paths,
            context_sections=context_sections,
            previous_error=previous_error,
        )
        try:
            create_response = _post_responses_request(
                url=responses_url,
                model=str(args.model or "").strip(),
                prompt=prompt,
                principal_id=principal_id,
                codex_profile=codex_profile,
                account_alias=account_alias,
                account_env=account_env,
                api_token=api_token,
                timeout_seconds=timeout_seconds,
            )
            response = _poll_response_until_terminal(
                create_response=create_response,
                responses_url=responses_url,
                principal_id=principal_id,
                codex_profile=codex_profile,
                account_alias=account_alias,
                account_env=account_env,
                api_token=api_token,
                timeout_seconds=timeout_seconds,
            )
            output_text = _extract_response_output_text(response)
            if not output_text:
                status = str(response.get("status") or "").strip() or "unknown"
                output_kind = type(response.get("output")).__name__
                raise ValueError(f"response emitted no visible text (status={status}, output={output_kind})")
            raw_response_path.write_text(output_text, encoding="utf-8")
            candidate = _extract_candidate_payload(output_text)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
            previous_error = f"responses request failed: {type(exc).__name__}: {exc}"
            _print(f"Trace: direct compiled worker retry {attempt}/{max_attempts} failed ({previous_error})", stream=sys.stderr)
            continue

        decision = str(candidate.get("decision") or "").strip().lower()
        if decision != "patch":
            previous_error = str(candidate.get("exact_blocker") or "model returned blocked without a patch").strip()
            _print(f"Trace: direct compiled worker retry {attempt}/{max_attempts} blocked ({previous_error})", stream=sys.stderr)
            continue
        diff_text = str(candidate.get("unified_diff") or "").strip()
        if not diff_text.startswith("diff --git "):
            previous_error = "model did not return a valid unified diff starting with 'diff --git'"
            _print(f"Trace: direct compiled worker retry {attempt}/{max_attempts} failed ({previous_error})", stream=sys.stderr)
            continue
        changed_paths = _diff_changed_relative_paths(diff_text)
        if not changed_paths:
            previous_error = "model diff did not expose any changed repo-relative paths"
            _print(f"Trace: direct compiled worker retry {attempt}/{max_attempts} failed ({previous_error})", stream=sys.stderr)
            continue
        invalid_paths = [path for path in changed_paths if not _allowed_relative_path(path, allowed_paths, repo_root)]
        if invalid_paths:
            previous_error = f"model diff touched files outside allowed paths: {', '.join(invalid_paths[:5])}"
            _print(f"Trace: direct compiled worker retry {attempt}/{max_attempts} failed ({previous_error})", stream=sys.stderr)
            continue
        applied, apply_error = _apply_diff(repo_root, diff_text)
        if not applied:
            previous_error = f"git apply failed: {apply_error}"
            _print(f"Trace: direct compiled worker retry {attempt}/{max_attempts} failed ({previous_error})", stream=sys.stderr)
            continue

        _print("apply_patch direct_compiled_worker_fallback")
        rendered_diff = _render_git_diff(repo_root, changed_paths)
        if rendered_diff:
            _print(rendered_diff)

        verify_command = str(candidate.get("verify_command") or "").strip()
        if verify_command not in verification_commands:
            verify_command = verification_commands[0] if verification_commands else ""
        verify_exit = 0
        verify_rendered = ""
        if verify_command:
            _print(f"/usr/bin/bash -lc {shlex.quote(verify_command)}")
            verify_exit, verify_rendered = _run_shell(
                verify_command,
                cwd=repo_root,
                timeout_seconds=max(10, int(os.environ.get("CODEXEA_DIRECT_COMPILED_VERIFY_TIMEOUT_SECONDS", "240") or "240")),
            )
            if verify_rendered:
                _print(_truncate(verify_rendered, max_lines=220, max_chars=24000))

        shipped = str(candidate.get("summary") or "").strip() or (
            f"Applied a direct compiled-worker patch touching {', '.join(changed_paths[:3])}"
        )
        if verify_command and verify_exit != 0:
            remains = str(candidate.get("what_remains") or "").strip() or "Continue the slice by addressing the failing verification output."
            blocker = f"verification command failed: {verify_command} (exit {verify_exit})"
        else:
            remains = str(candidate.get("what_remains") or "").strip() or "none"
            blocker = str(candidate.get("exact_blocker") or "none").strip() or "none"
        _write_closeout(
            Path(args.output_last_message),
            shipped=shipped,
            remains=remains,
            blocker=blocker,
        )
        _print(f"What shipped: {shipped}")
        _print("")
        _print(f"What remains: {remains}")
        _print("")
        _print(f"Exact blocker: {blocker}")
        return 0

    _print("Trace: direct compiled worker fallback exhausted retries", stream=sys.stderr)
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
