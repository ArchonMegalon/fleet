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

SUPPORTED_KEYS = {
    "TEABLE_API_KEY",
    "BROWSERACT_API_KEY",
    "MARKUPGO_API_KEY",
    "AI_MAGICX_API_KEY",
    "MAGIXAI_API_KEY",
    "ONEMIN_AI_API_KEY",
    "ONEMIN_AI_API_KEY_FALLBACK_1",
    "ONEMIN_AI_API_KEY_FALLBACK_2",
    "ONEMIN_AI_API_KEY_FALLBACK_3",
    "UNMIXR_API_KEY",
    "PROMPTING_SYSTEMS_API_KEY",
    "CHUMMER6_IMAGE_PROVIDER_ORDER",
    "CHUMMER6_TEXT_PROVIDER_ORDER",
    "CHUMMER6_MARKUPGO_RENDER_COMMAND",
    "CHUMMER6_MAGIXAI_RENDER_COMMAND",
    "CHUMMER6_MAGIXAI_BASE_URL",
    "CHUMMER6_1MIN_RENDER_COMMAND",
    "CHUMMER6_1MIN_ENDPOINT",
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
    for raw_key, raw_value in payload.items():
        key = str(raw_key).strip()
        value = str(raw_value or "").strip()
        if not key or not value:
            continue
        if key not in SUPPORTED_KEYS:
            raise SystemExit(f"unsupported key: {key}")
        env_text = set_env_value(env_text, key, value)
        applied[key] = mask(value)

    if any(k in payload for k in ("MARKUPGO_API_KEY",)) and "CHUMMER6_MARKUPGO_RENDER_COMMAND" not in payload:
        env_text = set_env_value(
            env_text,
            "CHUMMER6_MARKUPGO_RENDER_COMMAND",
            "python3 /docker/EA/scripts/chummer6_markupgo_render.py --prompt {prompt} --output {output} --width {width} --height {height}",
        )
        applied["CHUMMER6_MARKUPGO_RENDER_COMMAND"] = "(default)"

    if "CHUMMER6_IMAGE_PROVIDER_ORDER" not in payload:
        env_text = set_env_value(
            env_text,
            "CHUMMER6_IMAGE_PROVIDER_ORDER",
            "onemin,magixai,browseract_magixai,browseract_prompting_systems",
        )
        applied["CHUMMER6_IMAGE_PROVIDER_ORDER"] = "onemin,magixai,browseract_magixai,browseract_prompting_systems"

    if "CHUMMER6_TEXT_PROVIDER_ORDER" not in payload:
        env_text = set_env_value(
            env_text,
            "CHUMMER6_TEXT_PROVIDER_ORDER",
            "onemin,codex",
        )
        applied["CHUMMER6_TEXT_PROVIDER_ORDER"] = "onemin,codex"

    if "CHUMMER6_BROWSERACT_PROMPTING_SYSTEMS_REFINE_WORKFLOW_QUERY" not in payload:
        env_text = set_env_value(
            env_text,
            "CHUMMER6_BROWSERACT_PROMPTING_SYSTEMS_REFINE_WORKFLOW_QUERY",
            "chummer6 prompting systems refine",
        )
        applied["CHUMMER6_BROWSERACT_PROMPTING_SYSTEMS_REFINE_WORKFLOW_QUERY"] = "chummer6 prompting systems refine"

    if "CHUMMER6_BROWSERACT_PROMPTING_SYSTEMS_RENDER_WORKFLOW_QUERY" not in payload:
        env_text = set_env_value(
            env_text,
            "CHUMMER6_BROWSERACT_PROMPTING_SYSTEMS_RENDER_WORKFLOW_QUERY",
            "chummer6 prompting systems render",
        )
        applied["CHUMMER6_BROWSERACT_PROMPTING_SYSTEMS_RENDER_WORKFLOW_QUERY"] = "chummer6 prompting systems render"

    if "CHUMMER6_BROWSERACT_MAGIXAI_RENDER_WORKFLOW_QUERY" not in payload:
        env_text = set_env_value(
            env_text,
            "CHUMMER6_BROWSERACT_MAGIXAI_RENDER_WORKFLOW_QUERY",
            "chummer6 magicx render",
        )
        applied["CHUMMER6_BROWSERACT_MAGIXAI_RENDER_WORKFLOW_QUERY"] = "chummer6 magicx render"

    write_text(EA_ENV, env_text)

    for key in ("TEABLE_API_KEY", "MARKUPGO_API_KEY", "AI_MAGICX_API_KEY", "PROMPTING_SYSTEMS_API_KEY", "UNMIXR_API_KEY"):
        if key in applied:
            ensure_placeholder(EA_ENV_EXAMPLE, key)
            ensure_placeholder(EA_ENV_LOCAL_EXAMPLE, key)

    print(json.dumps({"updated": sorted(applied), "masked": applied}, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
