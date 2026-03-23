#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path


EA_ROOT = Path("/docker/EA")
SCRIPTS_DIR = EA_ROOT / "scripts"
ENV_EXAMPLE_PATH = EA_ROOT / ".env.example"
ENV_LOCAL_EXAMPLE_PATH = EA_ROOT / ".env.local.example"
ARCHITECT_SCRIPT_PATH = SCRIPTS_DIR / "browseract_architect.py"
BOOTSTRAP_MANAGER_PATH = SCRIPTS_DIR / "browseract_bootstrap_manager.py"
BOOTSTRAP_SKILL_PATH = SCRIPTS_DIR / "bootstrap_browseract_bootstrap_skill.py"
STATE_DIR = Path("/docker/fleet/state/browseract_bootstrap")
SEED_SPEC_PATH = STATE_DIR / "browseract_architect.seed.json"
SEED_GUIDE_PATH = STATE_DIR / "browseract_architect.seed.md"


ARCHITECT_SCRIPT = """#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


EA_ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = EA_ROOT / ".env"
API_BASE = "https://api.browseract.com/v2/workflow"


def load_local_env() -> dict[str, str]:
    values: dict[str, str] = {}
    if not ENV_FILE.exists():
        return values
    for raw in ENV_FILE.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


LOCAL_ENV = load_local_env()


def env_value(name: str) -> str:
    return str(os.environ.get(name) or LOCAL_ENV.get(name) or "").strip()


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


def api_request(method: str, path: str, *, payload: dict[str, object] | None = None, query: dict[str, str] | None = None) -> dict[str, object]:
    key = browseract_key()
    if not key:
        raise RuntimeError("browseract:not_configured")
    url = API_BASE.rstrip("/") + path
    if query:
        url += "?" + urllib.parse.urlencode(query)
    headers = {
        "Authorization": f"Bearer {key}",
        "User-Agent": "EA-BrowserAct-Architect/1.0",
    }
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, method=method.upper(), headers=headers, data=data)
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            body = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"browseract:http_{exc.code}:{detail[:240]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"browseract:urlerror:{exc.reason}") from exc
    try:
        loaded = json.loads(body)
    except Exception as exc:
        raise RuntimeError(f"browseract:non_json:{body[:240]}") from exc
    return loaded if isinstance(loaded, dict) else {"data": loaded}


def load_spec(path: Path) -> dict[str, object]:
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise RuntimeError("invalid_spec")
    return loaded


def normalize_spec(raw: dict[str, object]) -> dict[str, object]:
    nodes = raw.get("nodes")
    edges = raw.get("edges")
    meta = raw.get("meta") if isinstance(raw.get("meta"), dict) else {}
    if not isinstance(nodes, list) or not nodes:
        raise RuntimeError("invalid_spec:nodes")
    if not isinstance(edges, list):
        raise RuntimeError("invalid_spec:edges")
    normalized_nodes: list[dict[str, object]] = []
    for index, entry in enumerate(nodes, start=1):
        if not isinstance(entry, dict):
            raise RuntimeError("invalid_spec:node_entry")
        label = str(entry.get("label") or f"Step {index}").strip()
        node_type = str(entry.get("type") or "").strip().lower()
        config = entry.get("config") if isinstance(entry.get("config"), dict) else {}
        if not node_type:
            raise RuntimeError("invalid_spec:node_type")
        normalized_nodes.append(
            {
                "id": str(entry.get("id") or f"node_{index:02d}"),
                "label": label,
                "type": node_type,
                "config": config,
            }
        )
    normalized_edges: list[dict[str, str]] = []
    for index, entry in enumerate(edges, start=1):
        if isinstance(entry, dict):
            source = str(entry.get("source") or "").strip()
            target = str(entry.get("target") or "").strip()
        elif isinstance(entry, list) and len(entry) == 2:
            source = str(entry[0] or "").strip()
            target = str(entry[1] or "").strip()
        else:
            raise RuntimeError("invalid_spec:edge_entry")
        if not source or not target:
            raise RuntimeError("invalid_spec:edge_values")
        normalized_edges.append({"id": f"edge_{index:02d}", "source": source, "target": target})
    normalized_inputs: list[dict[str, object]] = []
    seen_inputs: set[str] = set()

    def add_input(name: object, *, description: object = "", default_value: object = "") -> None:
        normalized_name = str(name or "").strip()
        if not normalized_name:
            return
        key = normalized_name.lower()
        if key in seen_inputs:
            return
        seen_inputs.add(key)
        normalized_inputs.append(
            {
                "name": normalized_name,
                "description": str(description or "").strip(),
                "default_value": str(default_value or "").strip(),
            }
        )

    raw_inputs = raw.get("inputs")
    if not isinstance(raw_inputs, list):
        raw_inputs = raw.get("input_parameters")
    if isinstance(raw_inputs, list):
        for entry in raw_inputs:
            if isinstance(entry, dict):
                add_input(
                    entry.get("name") or entry.get("key") or entry.get("id"),
                    description=entry.get("description") or entry.get("label"),
                    default_value=entry.get("default_value") or entry.get("default") or entry.get("value"),
                )
            elif isinstance(entry, str):
                add_input(entry)
    for node in normalized_nodes:
        config = dict(node.get("config") or {})
        inferred_name = str(config.get("value_from_input") or "").strip()
        if not inferred_name:
            inferred_name = str(config.get("value_from_secret") or "").strip()
        if not inferred_name:
            continue
        inferred_description = str(config.get("description") or f"Runtime input for {node['label']}.").strip()
        add_input(inferred_name, description=inferred_description)
    return {
        "workflow_name": str(raw.get("workflow_name") or "browseract_architect").strip() or "browseract_architect",
        "description": str(raw.get("description") or "").strip(),
        "publish": bool(raw.get("publish", False)),
        "mcp_ready": bool(raw.get("mcp_ready", False)),
        "meta": dict(meta),
        "inputs": normalized_inputs,
        "nodes": normalized_nodes,
        "edges": normalized_edges,
    }


def builder_packet(spec: dict[str, object]) -> dict[str, object]:
    nodes = list(spec.get("nodes") or [])
    edges = list(spec.get("edges") or [])
    inputs = list(spec.get("inputs") or [])
    instructions = [
        "Open BrowserAct dashboard and start a new workflow.",
        "Set workflow name and description from the packet metadata, then declare the runtime input parameters on the Start node.",
        "Add nodes in listed order, then configure each node from its config payload.",
        "Wire edges exactly as listed.",
        "Save draft, publish workflow, then enable MCP later only if explicitly requested.",
    ]
    return {
        "workflow_name": spec.get("workflow_name"),
        "description": spec.get("description"),
        "publish": bool(spec.get("publish")),
        "mcp_ready": bool(spec.get("mcp_ready")),
        "meta": dict(spec.get("meta") or {}),
        "instructions": instructions,
        "inputs": inputs,
        "nodes": nodes,
        "edges": edges,
    }


def cmd_emit(spec_path: Path, output_path: Path) -> int:
    spec = normalize_spec(load_spec(spec_path))
    packet = builder_packet(spec)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(packet, indent=2, ensure_ascii=True) + "\\n", encoding="utf-8")
    print(json.dumps({"status": "ok", "output": str(output_path), "workflow_name": packet["workflow_name"]}, ensure_ascii=True))
    return 0


def cmd_check() -> int:
    workflow_id = env_value("BROWSERACT_ARCHITECT_WORKFLOW_ID")
    query = env_value("BROWSERACT_ARCHITECT_WORKFLOW_QUERY")
    if workflow_id:
        print(json.dumps({"status": "ready", "workflow_id": workflow_id, "source": "explicit"}, ensure_ascii=True))
        return 0
    print(json.dumps({"status": "pending_seed", "workflow_query": query or "browseract architect"}, ensure_ascii=True))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="BrowserAct architect helper.")
    sub = parser.add_subparsers(dest="command", required=True)
    emit = sub.add_parser("emit")
    emit.add_argument("--spec", required=True)
    emit.add_argument("--output", required=True)
    sub.add_parser("check")
    args = parser.parse_args()
    if args.command == "emit":
        return cmd_emit(Path(args.spec), Path(args.output))
    if args.command == "check":
        return cmd_check()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
"""


BOOTSTRAP_MANAGER_SCRIPT = """#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


STATE_DIR = Path("/docker/fleet/state/browseract_bootstrap")


def slugify(value: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "_" for ch in value)
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    return cleaned.strip("_") or "adapter"


def build_spec(
    *,
    workflow_name: str,
    purpose: str,
    login_url: str,
    tool_url: str,
    output_dir: Path,
    prompt_selector: str,
    submit_selector: str,
    result_selector: str,
) -> dict[str, object]:
    slug = slugify(workflow_name)
    nodes: list[dict[str, object]] = []
    edges: list[list[str]] = []

    if login_url.lower() not in {"", "none", "public", "noauth"}:
        nodes.extend(
            [
                {"id": "open_login", "type": "visit_page", "label": "Open Login", "config": {"url": login_url}},
                {"id": "email", "type": "input_text", "label": "Email", "config": {"selector": "input[type=email]", "value_from_secret": "browseract_username"}},
                {"id": "password", "type": "input_text", "label": "Password", "config": {"selector": "input[type=password]", "value_from_secret": "browseract_password"}},
                {"id": "submit", "type": "click", "label": "Submit", "config": {"selector": "button[type=submit]"}},
                {"id": "wait_dashboard", "type": "wait", "label": "Wait Dashboard", "config": {"selector": "body"}},
            ]
        )
        edges.extend(
            [
                ["open_login", "email"],
                ["email", "password"],
                ["password", "submit"],
                ["submit", "wait_dashboard"],
                ["wait_dashboard", "open_tool"],
            ]
        )

    nodes.extend(
        [
            {"id": "open_tool", "type": "visit_page", "label": "Open Tool", "config": {"url": tool_url}},
            {"id": "input_prompt", "type": "input_text", "label": "Input Prompt", "config": {"selector": prompt_selector, "value_from_input": "prompt"}},
            {"id": "generate", "type": "click", "label": "Generate", "config": {"selector": submit_selector}},
            {"id": "extract_result", "type": "extract", "label": "Extract Result", "config": {"selector": result_selector}},
        ]
    )
    edges.extend(
        [
            ["open_tool", "input_prompt"],
            ["input_prompt", "generate"],
            ["generate", "extract_result"],
        ]
    )

    return {
        "workflow_name": workflow_name,
        "description": purpose,
        "publish": True,
        "mcp_ready": False,
        "inputs": [
            {
                "name": "prompt",
                "description": "Primary runtime prompt value passed into the BrowserAct tool page.",
            },
        ],
        "nodes": nodes,
        "edges": edges,
        "meta": {
            "slug": slug,
            "output_dir": str(output_dir),
            "status": "pending_browseract_seed",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a BrowserAct adapter workflow spec from a prepared brief.")
    parser.add_argument("--workflow-name", required=True)
    parser.add_argument("--purpose", required=True)
    parser.add_argument("--login-url", required=True)
    parser.add_argument("--tool-url", required=True)
    parser.add_argument("--prompt-selector", default="textarea")
    parser.add_argument("--submit-selector", default="button")
    parser.add_argument("--result-selector", default="main, body")
    parser.add_argument("--output-dir", default=str(STATE_DIR))
    args = parser.parse_args()

    output_dir = Path(args.output_dir).expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)
    slug = slugify(args.workflow_name)
    spec = build_spec(
        workflow_name=args.workflow_name,
        purpose=args.purpose,
        login_url=args.login_url,
        tool_url=args.tool_url,
        output_dir=output_dir,
        prompt_selector=args.prompt_selector,
        submit_selector=args.submit_selector,
        result_selector=args.result_selector,
    )
    spec_path = output_dir / f"{slug}.workflow.json"
    spec_path.write_text(json.dumps(spec, indent=2, ensure_ascii=True) + "\\n", encoding="utf-8")
    print(json.dumps({"status": "ok", "spec": str(spec_path), "workflow_name": args.workflow_name}, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
"""


BOOTSTRAP_SKILL_SCRIPT = """#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path


EA_ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = EA_ROOT / ".env"
HOST = os.environ.get("EA_SKILL_HOST", "http://127.0.0.1:8090")


def env_value(name: str) -> str:
    direct = str(os.environ.get(name) or "").strip()
    if direct:
        return direct
    if ENV_FILE.exists():
        for raw in ENV_FILE.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key.strip() == name:
                return value.strip()
    return ""


def upsert_skill(body: dict[str, object]) -> dict[str, object]:
    token = env_value("EA_API_TOKEN")
    request = urllib.request.Request(
        f"{HOST}/v1/skills",
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        data=json.dumps(body).encode("utf-8"),
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    skill = {
        "skill_key": "browseract_bootstrap_manager",
        "task_key": "browseract_bootstrap_manager",
        "name": "BrowserAct Bootstrap Manager",
        "description": "Planner-executed BrowserAct workflow-spec builder for stage-0 BrowserAct template creation and architect packets.",
        "deliverable_type": "browseract_workflow_spec_packet",
        "default_risk_class": "medium",
        "default_approval_class": "none",
        "workflow_template": "tool_then_artifact",
        "allowed_tools": ["browseract.build_workflow_spec", "artifact_repository"],
        "evidence_requirements": ["target_domain_brief", "workflow_spec", "browseract_seed_state"],
        "memory_write_policy": "none",
        "memory_reads": ["entities", "relationships"],
        "memory_writes": [],
        "tags": ["browseract", "bootstrap", "workflow", "architect"],
        "authority_profile_json": {"authority_class": "draft", "review_class": "operator"},
        "provider_hints_json": {
            "primary": ["BrowserAct"],
            "notes": ["Stage-0 architect compiles prepared workflow specs into BrowserAct-ready packets."],
        },
        "tool_policy_json": {"allowed_tools": ["browseract.build_workflow_spec", "artifact_repository"]},
        "human_policy_json": {"review_roles": ["automation_architect"]},
        "evaluation_cases_json": [{"case_key": "browseract_bootstrap_manager_golden", "priority": "medium"}],
        "budget_policy_json": {
            "class": "medium",
            "workflow_template": "tool_then_artifact",
            "pre_artifact_capability_key": "workflow_spec_build",
            "browseract_failure_strategy": "retry",
            "browseract_max_attempts": 2,
            "browseract_retry_backoff_seconds": 1,
            "skill_catalog_json": {
                "mode": "spec_compiler",
                "capabilities": ["workflow_spec", "builder_packet", "seed_validation"],
            },
        },
    }
    try:
        result = upsert_skill(skill)
    except urllib.error.URLError as exc:
        print(json.dumps({"status": "skipped", "reason": f"api_unavailable:{exc.reason}"}))
        return 0
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace").strip()
        print(json.dumps({"status": "skipped", "reason": f"http_{exc.code}", "body": body[:240]}))
        return 0
    print(json.dumps({"status": "ok", "skill_key": result.get("skill_key", "")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
"""


def seed_spec() -> dict[str, object]:
    return {
        "workflow_name": "browseract_architect",
        "description": "Stage-0 BrowserAct workflow that creates or updates other BrowserAct workflows from a prepared spec packet.",
        "publish": True,
        "mcp_ready": False,
        "inputs": [
            {"name": "workflow_name", "description": "Workflow name to create or update."},
            {"name": "description", "description": "Workflow description for the BrowserAct card and builder."},
        ],
        "nodes": [
            {"id": "open_dashboard", "type": "visit_page", "label": "Open BrowserAct Dashboard", "config": {"url": "https://app.browseract.com"}},
            {"id": "new_workflow", "type": "click", "label": "Create New Workflow", "config": {"selector": "[data-testid='create-workflow'], button"}},
            {"id": "name_workflow", "type": "input_text", "label": "Set Workflow Name", "config": {"selector": "input[name='name'], input", "value_from_input": "workflow_name"}},
            {"id": "describe_workflow", "type": "input_text", "label": "Set Workflow Description", "config": {"selector": "textarea, input[name='description']", "value_from_input": "description"}},
            {"id": "add_nodes", "type": "repeat", "label": "Add Nodes From Spec", "config": {"repeat_source": "nodes", "step_contract": "builder_packet.nodes"}},
            {"id": "wire_edges", "type": "repeat", "label": "Wire Edges From Spec", "config": {"repeat_source": "edges", "step_contract": "builder_packet.edges"}},
            {"id": "save_draft", "type": "click", "label": "Save Draft", "config": {"selector": "button"}},
            {"id": "publish", "type": "click", "label": "Publish Workflow", "config": {"selector": "button"}},
        ],
        "edges": [
            ["open_dashboard", "new_workflow"],
            ["new_workflow", "name_workflow"],
            ["name_workflow", "describe_workflow"],
            ["describe_workflow", "add_nodes"],
            ["add_nodes", "wire_edges"],
            ["wire_edges", "save_draft"],
            ["save_draft", "publish"],
        ],
    }


def seed_guide() -> str:
    return """# BrowserAct Architect Seed

This is the stage-0 workflow seed for `browseract_architect`.

Purpose:
- materialize BrowserAct workflows from a prepared spec packet
- keep site understanding in EA
- keep BrowserAct responsible only for builder/compiler work

Expected inputs:
- `workflow_name`
- `description`
- `nodes`
- `edges`
- `publish`
- `mcp_ready`

Required secrets:
- `browseract_username`
- `browseract_password`

Required behavior:
1. Open BrowserAct dashboard.
2. Start a new workflow.
3. Fill workflow metadata from the packet.
4. Add nodes in order from the packet.
5. Wire edges exactly as listed.
6. Save and publish.
7. Leave MCP enablement as a later explicit step.
"""


def write_if_changed(path: Path, content: str, *, executable: bool = False) -> None:
    if path.exists():
        existing = path.read_text(encoding="utf-8")
        if existing == content:
            if executable:
                path.chmod(0o755)
            return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    if executable:
        path.chmod(0o755)


def ensure_env_examples() -> None:
    section = """

# BrowserAct bootstrap architect
BROWSERACT_ARCHITECT_WORKFLOW_ID=
BROWSERACT_ARCHITECT_WORKFLOW_QUERY=browseract architect
BROWSERACT_USERNAME=
BROWSERACT_PASSWORD=
""".lstrip("\\n")
    marker = "# BrowserAct bootstrap architect"
    for path in (ENV_EXAMPLE_PATH, ENV_LOCAL_EXAMPLE_PATH):
        if not path.exists():
            continue
        current = path.read_text(encoding="utf-8")
        if marker in current:
            continue
        suffix = "" if current.endswith("\\n") else "\\n"
        path.write_text(current + suffix + section, encoding="utf-8")


def main() -> int:
    write_if_changed(ARCHITECT_SCRIPT_PATH, ARCHITECT_SCRIPT, executable=True)
    write_if_changed(BOOTSTRAP_MANAGER_PATH, BOOTSTRAP_MANAGER_SCRIPT, executable=True)
    write_if_changed(BOOTSTRAP_SKILL_PATH, BOOTSTRAP_SKILL_SCRIPT, executable=True)
    SEED_SPEC_PATH.parent.mkdir(parents=True, exist_ok=True)
    SEED_SPEC_PATH.write_text(json.dumps(seed_spec(), indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    SEED_GUIDE_PATH.write_text(seed_guide(), encoding="utf-8")
    ensure_env_examples()
    print(
        json.dumps(
            {
                "status": "updated",
                "architect": str(ARCHITECT_SCRIPT_PATH),
                "bootstrap_manager": str(BOOTSTRAP_MANAGER_PATH),
                "bootstrap_skill": str(BOOTSTRAP_SKILL_PATH),
                "seed_spec": str(SEED_SPEC_PATH),
                "seed_guide": str(SEED_GUIDE_PATH),
            },
            ensure_ascii=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
