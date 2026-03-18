#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


EA_ROOT = Path("/docker/EA")
EA_ENV = EA_ROOT / ".env"
EA_ENV_EXAMPLE = EA_ROOT / ".env.example"
EA_ENV_LOCAL_EXAMPLE = EA_ROOT / ".env.local.example"
CHUMMER_POLICY = Path("/docker/fleet/.chummer6_local_policy.json")

ENV_KEYS = {
    "TEABLE_API_KEY",
    "BROWSERACT_API_KEY",
    "BROWSERACT_USERNAME",
    "BROWSERACT_PASSWORD",
    "BROWSERACT_CHATPLAYGROUND_AUDIT_WORKFLOW_ID",
    "BROWSERACT_CHATPLAYGROUND_AUDIT_WORKFLOW_QUERY",
    "BROWSERACT_CHATPLAYGROUND_AUDIT_RESULT_PATH",
    "BROWSERACT_CHATPLAYGROUND_AUDIT_TIMEOUT_SECONDS",
    "BROWSERACT_ARCHITECT_WORKFLOW_ID",
    "BROWSERACT_ARCHITECT_WORKFLOW_QUERY",
    "MARKUPGO_API_KEY",
    "AI_MAGICX_API_KEY",
    "MAGIXAI_API_KEY",
    "ONEMIN_AI_API_KEY",
    "ONEMIN_AI_API_KEY_FALLBACK_1",
    "ONEMIN_AI_API_KEY_FALLBACK_2",
    "ONEMIN_AI_API_KEY_FALLBACK_3",
    "UNMIXR_API_KEY",
    "PROMPTING_SYSTEMS_API_KEY",
}

POLICY_KEYS = {
    "CHUMMER6_IMAGE_PROVIDER_ORDER",
    "CHUMMER6_MEDIA_FACTORY_RENDER_COMMAND",
    "CHUMMER6_TEXT_PROVIDER_ORDER",
    "CHUMMER6_MARKUPGO_RENDER_COMMAND",
    "CHUMMER6_MAGIXAI_RENDER_COMMAND",
    "CHUMMER6_MAGIXAI_BASE_URL",
    "CHUMMER6_1MIN_RENDER_COMMAND",
    "CHUMMER6_1MIN_ENDPOINT",
    "CHUMMER6_ONEMIN_MODEL",
    "CHUMMER6_ONEMIN_IMAGE_SIZE",
    "CHUMMER6_ONEMIN_IMAGE_QUALITY",
    "CHUMMER6_PROVIDER_BUSY_RETRIES",
    "CHUMMER6_PROVIDER_BUSY_DELAY_SECONDS",
    "CHUMMER6_ONEMIN_USE_FALLBACK_KEYS",
    "CHUMMER6_PROMPTING_SYSTEMS_RENDER_COMMAND",
    "CHUMMER6_BROWSERACT_PROMPTING_SYSTEMS_RENDER_COMMAND",
    "CHUMMER6_BROWSERACT_PROMPTING_SYSTEMS_RENDER_WORKFLOW_ID",
    "CHUMMER6_BROWSERACT_PROMPTING_SYSTEMS_RENDER_WORKFLOW_QUERY",
    "CHUMMER6_PROMPTING_SYSTEMS_REFINE_COMMAND",
    "CHUMMER6_BROWSERACT_PROMPTING_SYSTEMS_REFINE_COMMAND",
    "CHUMMER6_BROWSERACT_PROMPTING_SYSTEMS_REFINE_WORKFLOW_ID",
    "CHUMMER6_BROWSERACT_PROMPTING_SYSTEMS_REFINE_WORKFLOW_QUERY",
    "CHUMMER6_BROWSERACT_MAGIXAI_RENDER_COMMAND",
    "CHUMMER6_BROWSERACT_MAGIXAI_RENDER_WORKFLOW_ID",
    "CHUMMER6_BROWSERACT_MAGIXAI_RENDER_WORKFLOW_QUERY",
    "CHUMMER6_BROWSERACT_HUMANIZER_COMMAND",
    "CHUMMER6_BROWSERACT_HUMANIZER_URL_TEMPLATE",
    "CHUMMER6_BROWSERACT_HUMANIZER_WORKFLOW_ID",
    "CHUMMER6_BROWSERACT_HUMANIZER_WORKFLOW_QUERY",
    "CHUMMER6_TEXT_HUMANIZER_COMMAND",
    "CHUMMER6_TEXT_HUMANIZER_URL_TEMPLATE",
    "CHUMMER6_TEXT_HUMANIZER_REQUIRED",
    "CHUMMER6_TEXT_HUMANIZER_MIN_SENTENCES",
    "CHUMMER6_PROMPT_REFINER_COMMAND",
    "CHUMMER6_MARKUPGO_RENDER_URL_TEMPLATE",
    "CHUMMER6_MAGIXAI_RENDER_URL_TEMPLATE",
    "CHUMMER6_1MIN_RENDER_URL_TEMPLATE",
    "CHUMMER6_PROMPTING_SYSTEMS_RENDER_URL_TEMPLATE",
    "CHUMMER6_BROWSERACT_PROMPTING_SYSTEMS_RENDER_URL_TEMPLATE",
    "CHUMMER6_PROMPTING_SYSTEMS_REFINE_URL_TEMPLATE",
    "CHUMMER6_BROWSERACT_PROMPTING_SYSTEMS_REFINE_URL_TEMPLATE",
    "CHUMMER6_BROWSERACT_MAGIXAI_RENDER_URL_TEMPLATE",
    "CHUMMER6_PROMPT_REFINER_URL_TEMPLATE",
}

SUPPORTED_KEYS = ENV_KEYS | POLICY_KEYS


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def set_env_value(text: str, key: str, value: str) -> str:
    pattern = re.compile(rf"(?m)^{re.escape(key)}=.*$")
    line = f"{key}={value}"
    if pattern.search(text):
        return pattern.sub(line, text, count=1)
    if text and not text.endswith("\n"):
        text += "\n"
    return text + line + "\n"


def ensure_placeholder(path: Path, key: str) -> None:
    text = read_text(path)
    if f"{key}=" in text:
        return
    suffix = "" if not text or text.endswith("\n") else "\n"
    write_text(path, text + suffix + f"{key}=\n")


def load_policy() -> dict[str, object]:
    if not CHUMMER_POLICY.exists():
        return {}
    try:
        loaded = json.loads(CHUMMER_POLICY.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def write_policy(body: dict[str, object]) -> None:
    CHUMMER_POLICY.parent.mkdir(parents=True, exist_ok=True)
    CHUMMER_POLICY.write_text(json.dumps(body, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def mask(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 10:
        return "***"
    return value[:6] + "..." + value[-4:]


def main() -> int:
    parser = argparse.ArgumentParser(description="Inject local provider keys into /docker/EA/.env only.")
    parser.add_argument("json_file", help="Path to a JSON object of env keys to inject into /docker/EA/.env")
    args = parser.parse_args()

    payload = json.loads(Path(args.json_file).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit("JSON payload must be an object")

    env_text = read_text(EA_ENV)
    applied: dict[str, str] = {}
    policy = load_policy()
    runtime_overrides = policy.get("runtime_overrides")
    if not isinstance(runtime_overrides, dict):
        runtime_overrides = {}
    for raw_key, raw_value in payload.items():
        key = str(raw_key).strip()
        value = str(raw_value or "").strip()
        if not key or not value:
            continue
        if key not in SUPPORTED_KEYS:
            raise SystemExit(f"unsupported key: {key}")
        if key in ENV_KEYS:
            env_text = set_env_value(env_text, key, value)
            applied[key] = mask(value)
        else:
            runtime_overrides[key] = value
            applied[key] = value

    defaults = {
        "CHUMMER6_IMAGE_PROVIDER_ORDER": "magixai,media_factory,onemin,browseract_magixai,browseract_prompting_systems",
        "CHUMMER6_MEDIA_FACTORY_RENDER_COMMAND": "python3 /docker/fleet/repos/chummer-media-factory/scripts/render_guide_asset.py --prompt {prompt} --output {output} --width {width} --height {height}",
        "CHUMMER6_TEXT_PROVIDER_ORDER": "ea",
        "CHUMMER6_TEXT_MODEL": "ea-groundwork",
        "CHUMMER6_BROWSERACT_PROMPTING_SYSTEMS_REFINE_WORKFLOW_QUERY": "chummer6 prompting systems refine",
        "CHUMMER6_BROWSERACT_PROMPTING_SYSTEMS_RENDER_WORKFLOW_QUERY": "chummer6 prompting systems render",
        "CHUMMER6_BROWSERACT_MAGIXAI_RENDER_WORKFLOW_QUERY": "chummer6 magicx render",
        "CHUMMER6_BROWSERACT_HUMANIZER_WORKFLOW_QUERY": "chummer6 undetectable humanizer",
        "CHUMMER6_ONEMIN_MODEL": "gpt-image-1-mini",
        "CHUMMER6_ONEMIN_IMAGE_SIZE": "auto",
        "CHUMMER6_ONEMIN_IMAGE_QUALITY": "low",
        "CHUMMER6_PROVIDER_BUSY_RETRIES": "2",
        "CHUMMER6_PROVIDER_BUSY_DELAY_SECONDS": "10",
        "CHUMMER6_ONEMIN_USE_FALLBACK_KEYS": "1",
        "CHUMMER6_MAGIXAI_BASE_URL": "https://beta.aimagicx.com/api/v1",
        "CHUMMER6_TEXT_HUMANIZER_MIN_SENTENCES": "2",
        "EA_RESPONSES_CHATPLAYGROUND_MODELS": "gpt-4.1",
        "EA_RESPONSES_CHATPLAYGROUND_ROLES": "factuality",
    }
    if any(k in payload for k in ("MARKUPGO_API_KEY",)) and "CHUMMER6_MARKUPGO_RENDER_COMMAND" not in runtime_overrides:
        runtime_overrides["CHUMMER6_MARKUPGO_RENDER_COMMAND"] = (
            "python3 /docker/EA/scripts/chummer6_markupgo_render.py --prompt {prompt} --output {output} --width {width} --height {height}"
        )
    for key, value in defaults.items():
        runtime_overrides.setdefault(key, value)

    write_text(EA_ENV, env_text)
    policy["runtime_overrides"] = runtime_overrides
    write_policy(policy)

    for key in ("TEABLE_API_KEY", "BROWSERACT_USERNAME", "BROWSERACT_PASSWORD", "MARKUPGO_API_KEY", "AI_MAGICX_API_KEY", "PROMPTING_SYSTEMS_API_KEY", "UNMIXR_API_KEY"):
        if key in applied:
            ensure_placeholder(EA_ENV_EXAMPLE, key)
            ensure_placeholder(EA_ENV_LOCAL_EXAMPLE, key)

    print(json.dumps({"updated": sorted(applied), "masked": applied}, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
