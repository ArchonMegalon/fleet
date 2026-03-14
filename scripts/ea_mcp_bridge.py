#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union


SERVER_NAME = "ea-mcp-bridge"
SERVER_VERSION = "0.1.0"
DEFAULT_PROTOCOL_VERSION = "2025-03-26"


def _env(name: str, default: str = "") -> str:
    return str(os.environ.get(name) or default).strip()


@dataclass(frozen=True)
class EAConfig:
    base_url: str
    api_token: str
    default_principal_id: str
    timeout_seconds: float


def load_ea_config() -> EAConfig:
    base_url = _env("EA_MCP_BASE_URL", "http://127.0.0.1:8090").rstrip("/")
    api_token = _env("EA_MCP_API_TOKEN", "")
    default_principal_id = _env("EA_MCP_PRINCIPAL_ID", "codex-fleet")
    timeout_raw = _env("EA_MCP_TIMEOUT_SECONDS", "120")
    try:
        timeout_seconds = max(1.0, float(timeout_raw))
    except Exception:
        timeout_seconds = 120.0
    return EAConfig(
        base_url=base_url,
        api_token=api_token,
        default_principal_id=default_principal_id or "codex-fleet",
        timeout_seconds=timeout_seconds,
    )


class EAClient:
    def __init__(self, cfg: EAConfig) -> None:
        self._cfg = cfg

    def _headers(self, *, principal_id: str = "", json_body: bool = False) -> Dict[str, str]:
        headers: Dict[str, str] = {"User-Agent": f"{SERVER_NAME}/{SERVER_VERSION}"}
        if self._cfg.api_token:
            headers["Authorization"] = f"Bearer {self._cfg.api_token}"
        if principal_id:
            headers["X-EA-Principal-ID"] = principal_id
        if json_body:
            headers["Content-Type"] = "application/json"
        return headers

    def request(
        self,
        method: str,
        path: str,
        *,
        principal_id: str = "",
        query: Optional[Dict[str, str]] = None,
        body: Optional[Dict[str, Any]] = None,
    ) -> Tuple[int, Union[Dict[str, Any], List[Any], str]]:
        url = f"{self._cfg.base_url}{path}"
        if query:
            encoded = urllib.parse.urlencode({k: v for k, v in query.items() if str(v).strip()})
            if encoded:
                url = f"{url}?{encoded}"
        data = None
        json_body = body is not None
        if body is not None:
            data = json.dumps(body, ensure_ascii=True).encode("utf-8")
        req = urllib.request.Request(
            url,
            method=method.upper(),
            headers=self._headers(principal_id=principal_id, json_body=json_body),
            data=data,
        )
        try:
            with urllib.request.urlopen(req, timeout=self._cfg.timeout_seconds) as resp:
                status = int(getattr(resp, "status", 200))
                raw = resp.read().decode("utf-8", errors="replace").strip()
        except urllib.error.HTTPError as exc:
            status = int(getattr(exc, "code", 500) or 500)
            raw = exc.read().decode("utf-8", errors="replace").strip()
        except urllib.error.URLError as exc:
            return 0, f"urlerror:{getattr(exc, 'reason', exc)}"
        except Exception as exc:
            return 0, f"error:{exc}"

        if not raw:
            return status, {}
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, (dict, list)):
                return status, parsed
        except Exception:
            pass
        return status, raw


def _jsonrpc_error(*, msg_id: Any, code: int, message: str, data: Any = None) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}
    if data is not None:
        payload["error"]["data"] = data
    return payload


def _jsonrpc_result(*, msg_id: Any, result: Any) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "id": msg_id, "result": result}


def _tool_text_result(value: Any, *, is_error: bool = False) -> Dict[str, Any]:
    if isinstance(value, (dict, list)):
        text = json.dumps(value, indent=2, ensure_ascii=True)
        return {"content": [{"type": "text", "text": text}], "structuredContent": value, "isError": bool(is_error)}
    return {"content": [{"type": "text", "text": str(value)}], "isError": bool(is_error)}


def _tool_definitions() -> List[Dict[str, Any]]:
    no_extra = {"type": "object", "additionalProperties": False}
    return [
        {
            "name": "ea.list_skills",
            "title": "EA: List skills",
            "description": "List EA skill catalog entries (GET /v1/skills).",
            "inputSchema": {
                **no_extra,
                "properties": {
                    "limit": {"type": "integer", "minimum": 1, "maximum": 500, "default": 100},
                    "provider_hint": {"type": "string", "description": "Optional provider hint filter (e.g. BrowserAct)."},
                },
            },
        },
        {
            "name": "ea.get_skill",
            "title": "EA: Get skill",
            "description": "Fetch one EA skill by key (GET /v1/skills/{skill_key}).",
            "inputSchema": {
                **no_extra,
                "properties": {"skill_key": {"type": "string"}},
                "required": ["skill_key"],
            },
        },
        {
            "name": "ea.compile_plan",
            "title": "EA: Compile plan",
            "description": "Compile an EA plan from a task_key or skill_key (POST /v1/plans/compile).",
            "inputSchema": {
                **no_extra,
                "properties": {
                    "task_key": {"type": "string"},
                    "skill_key": {"type": "string"},
                    "goal": {"type": "string"},
                    "principal_id": {"type": "string", "description": "Optional EA principal scope override."},
                },
                "anyOf": [{"required": ["task_key"]}, {"required": ["skill_key"]}],
            },
        },
        {
            "name": "ea.execute_plan",
            "title": "EA: Execute plan",
            "description": "Execute an EA task/skill through the queued runtime (POST /v1/plans/execute).",
            "inputSchema": {
                **no_extra,
                "properties": {
                    "task_key": {"type": "string"},
                    "skill_key": {"type": "string"},
                    "goal": {"type": "string"},
                    "text": {"type": "string"},
                    "input_json": {"type": "object"},
                    "context_refs": {"type": "array", "items": {"type": "string"}},
                    "principal_id": {"type": "string", "description": "Optional EA principal scope override."},
                },
                "anyOf": [{"required": ["task_key"]}, {"required": ["skill_key"]}],
            },
        },
        {
            "name": "ea.execute_tool",
            "title": "EA: Execute tool",
            "description": "Execute an EA tool (POST /v1/tools/execute).",
            "inputSchema": {
                **no_extra,
                "properties": {
                    "tool_name": {"type": "string"},
                    "action_kind": {"type": "string"},
                    "payload_json": {"type": "object"},
                    "principal_id": {"type": "string", "description": "Optional EA principal scope override."},
                },
                "required": ["tool_name"],
            },
        },
        {
            "name": "ea.context_pack",
            "title": "EA: Context pack",
            "description": "Synthesize an EA memory reasoning context pack (POST /v1/memory/context-pack).",
            "inputSchema": {
                **no_extra,
                "properties": {
                    "task_key": {"type": "string", "default": "rewrite_text"},
                    "goal": {"type": "string"},
                    "context_refs": {"type": "array", "items": {"type": "string"}},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 20, "default": 5},
                    "principal_id": {"type": "string", "description": "Optional EA principal scope override."},
                },
            },
        },
    ]


def _principal_id_for_call(cfg: EAConfig, args: Dict[str, Any]) -> str:
    override = str(args.get("principal_id") or "").strip()
    return override or cfg.default_principal_id


def _as_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list_str(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def handle_tools_call(client: EAClient, cfg: EAConfig, *, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    if tool_name == "ea.list_skills":
        limit = str(args.get("limit") or "").strip()
        provider_hint = str(args.get("provider_hint") or "").strip()
        query: Dict[str, str] = {}
        if limit:
            query["limit"] = limit
        if provider_hint:
            query["provider_hint"] = provider_hint
        status, payload = client.request("GET", "/v1/skills", query=query)
        return _tool_text_result({"status": status, "data": payload}, is_error=(status < 200 or status >= 300))

    if tool_name == "ea.get_skill":
        skill_key = str(args.get("skill_key") or "").strip()
        if not skill_key:
            return _tool_text_result("skill_key_required", is_error=True)
        safe_key = urllib.parse.quote(skill_key, safe="")
        status, payload = client.request("GET", f"/v1/skills/{safe_key}")
        return _tool_text_result({"status": status, "data": payload}, is_error=(status < 200 or status >= 300))

    if tool_name == "ea.compile_plan":
        task_key = str(args.get("task_key") or "").strip()
        skill_key = str(args.get("skill_key") or "").strip()
        goal = str(args.get("goal") or "").strip()
        if not task_key and not skill_key:
            return _tool_text_result("task_key_or_skill_key_required", is_error=True)
        principal_id = _principal_id_for_call(cfg, args)
        body: Dict[str, Any] = {"goal": goal}
        if task_key:
            body["task_key"] = task_key
        if skill_key:
            body["skill_key"] = skill_key
        status, payload = client.request("POST", "/v1/plans/compile", principal_id=principal_id, body=body)
        return _tool_text_result({"status": status, "data": payload}, is_error=(status < 200 or status >= 300))

    if tool_name == "ea.execute_plan":
        task_key = str(args.get("task_key") or "").strip()
        skill_key = str(args.get("skill_key") or "").strip()
        goal = str(args.get("goal") or "").strip()
        text = str(args.get("text") or "").strip()
        input_json = _as_dict(args.get("input_json"))
        context_refs = _as_list_str(args.get("context_refs"))
        if not task_key and not skill_key:
            return _tool_text_result("task_key_or_skill_key_required", is_error=True)
        if not text and not input_json:
            return _tool_text_result("text_or_input_json_required", is_error=True)
        principal_id = _principal_id_for_call(cfg, args)
        body: Dict[str, Any] = {"goal": goal, "context_refs": context_refs}
        if task_key:
            body["task_key"] = task_key
        if skill_key:
            body["skill_key"] = skill_key
        if text:
            body["text"] = text
        if input_json:
            body["input_json"] = input_json
        status, payload = client.request("POST", "/v1/plans/execute", principal_id=principal_id, body=body)
        return _tool_text_result({"status": status, "data": payload}, is_error=(status < 200 or status >= 300))

    if tool_name == "ea.execute_tool":
        tool = str(args.get("tool_name") or "").strip()
        if not tool:
            return _tool_text_result("tool_name_required", is_error=True)
        principal_id = _principal_id_for_call(cfg, args)
        body = {
            "tool_name": tool,
            "action_kind": str(args.get("action_kind") or "").strip(),
            "payload_json": _as_dict(args.get("payload_json")),
        }
        status, payload = client.request("POST", "/v1/tools/execute", principal_id=principal_id, body=body)
        return _tool_text_result({"status": status, "data": payload}, is_error=(status < 200 or status >= 300))

    if tool_name == "ea.context_pack":
        principal_id = _principal_id_for_call(cfg, args)
        body = {
            "task_key": str(args.get("task_key") or "rewrite_text").strip() or "rewrite_text",
            "goal": str(args.get("goal") or "").strip(),
            "context_refs": _as_list_str(args.get("context_refs")),
            "limit": int(args.get("limit") or 5),
        }
        status, payload = client.request("POST", "/v1/memory/context-pack", principal_id=principal_id, body=body)
        return _tool_text_result({"status": status, "data": payload}, is_error=(status < 200 or status >= 300))

    return _tool_text_result(f"unknown_tool:{tool_name}", is_error=True)


def _iter_messages(stdin: Iterable[str]) -> Iterable[Any]:
    for raw in stdin:
        line = raw.strip()
        if not line:
            continue
        try:
            yield json.loads(line)
        except Exception:
            # Ignore malformed JSON without killing the session.
            continue


def main() -> int:
    cfg = load_ea_config()
    client = EAClient(cfg)
    tools = _tool_definitions()
    negotiated_protocol_version = DEFAULT_PROTOCOL_VERSION

    for msg in _iter_messages(sys.stdin):
        if isinstance(msg, list):
            # MCP no longer encourages batching, but ignore by processing sequentially.
            for item in msg:
                sys.stdout.write(json.dumps(_jsonrpc_error(msg_id=None, code=-32600, message="batch_not_supported")) + "\n")
                sys.stdout.flush()
            continue
        if not isinstance(msg, dict):
            continue

        method = str(msg.get("method") or "").strip()
        msg_id = msg.get("id", None)
        params = msg.get("params")
        params_dict = params if isinstance(params, dict) else {}

        # Notifications have no id and must not be answered.
        if msg_id is None:
            if method in {"notifications/initialized", "notifications/cancelled"}:
                continue
            continue

        if method == "initialize":
            requested = str(params_dict.get("protocolVersion") or "").strip()
            negotiated_protocol_version = requested or DEFAULT_PROTOCOL_VERSION
            result = {
                "protocolVersion": negotiated_protocol_version,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            }
            sys.stdout.write(json.dumps(_jsonrpc_result(msg_id=msg_id, result=result), ensure_ascii=True) + "\n")
            sys.stdout.flush()
            continue

        if method == "ping":
            sys.stdout.write(json.dumps(_jsonrpc_result(msg_id=msg_id, result={}), ensure_ascii=True) + "\n")
            sys.stdout.flush()
            continue

        if method == "tools/list":
            result: Dict[str, Any] = {"tools": tools}
            sys.stdout.write(json.dumps(_jsonrpc_result(msg_id=msg_id, result=result), ensure_ascii=True) + "\n")
            sys.stdout.flush()
            continue

        if method == "tools/call":
            name = str(params_dict.get("name") or "").strip()
            arguments = params_dict.get("arguments")
            arg_dict = arguments if isinstance(arguments, dict) else {}
            if not name:
                sys.stdout.write(
                    json.dumps(_jsonrpc_result(msg_id=msg_id, result=_tool_text_result("tool_name_required", is_error=True)), ensure_ascii=True)
                    + "\n"
                )
                sys.stdout.flush()
                continue
            result = handle_tools_call(client, cfg, tool_name=name, args=arg_dict)
            sys.stdout.write(json.dumps(_jsonrpc_result(msg_id=msg_id, result=result), ensure_ascii=True) + "\n")
            sys.stdout.flush()
            continue

        # Minimal compatibility shims: return empty lists for resources/prompts.
        if method == "resources/list":
            sys.stdout.write(json.dumps(_jsonrpc_result(msg_id=msg_id, result={"resources": []}), ensure_ascii=True) + "\n")
            sys.stdout.flush()
            continue
        if method == "prompts/list":
            sys.stdout.write(json.dumps(_jsonrpc_result(msg_id=msg_id, result={"prompts": []}), ensure_ascii=True) + "\n")
            sys.stdout.flush()
            continue

        # Unknown method.
        sys.stdout.write(json.dumps(_jsonrpc_error(msg_id=msg_id, code=-32601, message=f"method_not_found:{method}"), ensure_ascii=True) + "\n")
        sys.stdout.flush()

    # EOF from client.
    _ = negotiated_protocol_version
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
