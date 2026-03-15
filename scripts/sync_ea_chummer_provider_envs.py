#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path


EA_ENV = Path("/docker/EA/.env")
EA_ENV_EXAMPLE = Path("/docker/EA/.env.example")
EA_ENV_LOCAL_EXAMPLE = Path("/docker/EA/.env.local.example")
EA_DOCKER_MEMORY = Path("/docker/EA/docker-compose.memory.yml")
CHUMMER_ENV = Path("/docker/chummer5a/.env")
CHUMMER_ENV_PROVIDERS = Path("/docker/chummer5a/.env.providers")
CHUMMER_GITIGNORE = Path("/docker/chummer5a/.gitignore")
CHUMMER_ENV_EXAMPLE = Path("/docker/chummer5a/.env.example")
CHUMMER_DOCKER_COMPOSE = Path("/docker/chummer5a/docker-compose.yml")


UNMIXR_COMMENT = "# Optional Unmixr key slots (local .env only; keep real keys out of git)"
UNMIXR_EXAMPLE_LINES = [
    UNMIXR_COMMENT,
    "UNMIXR_API_KEY=",
]


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


def parse_env_values(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value
    return values


def split_csv_values(raw_value: str) -> list[str]:
    return [value.strip() for value in re.split(r"[;,\n\r]+", str(raw_value or "")) if value.strip()]


def unique_ordered(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        key = value.strip()
        if not key or key in seen:
            continue
        seen.add(key)
        ordered.append(key)
    return ordered


def ensure_example_unmixr(path: Path) -> None:
    text = read_text(path)
    if "UNMIXR_API_KEY=" in text:
        return
    anchor = "# Optional BrowserAct key rotation (local .env only; keep real keys out of git)\nBROWSERACT_API_KEY=\nBROWSERACT_API_KEY_FALLBACK_1=\n"
    block = "\n" + "\n".join(UNMIXR_EXAMPLE_LINES) + "\n"
    if anchor in text:
        text = text.replace(anchor, anchor + block, 1)
    else:
        if text and not text.endswith("\n"):
            text += "\n"
        text += block
    write_text(path, text)


def ensure_gitignore_entry(path: Path, entry: str) -> None:
    text = read_text(path)
    lines = text.splitlines()
    if entry not in lines:
        if text and not text.endswith("\n"):
            text += "\n"
        text += entry + "\n"
        write_text(path, text)


def ensure_chummer_provider_example(path: Path) -> None:
    text = read_text(path)
    additions = [
        "CHUMMER_PROVIDER_BROWSERACT_API_KEY=",
        "CHUMMER_PROVIDER_UNMIXR_API_KEY=",
    ]
    if all(entry in text for entry in additions):
        return
    anchor = "CHUMMER_AI_1MINAI_FALLBACK_API_KEY=\n"
    block = "".join(f"{entry}\n" for entry in additions)
    if anchor in text:
        text = text.replace(anchor, anchor + block, 1)
    else:
        if text and not text.endswith("\n"):
            text += "\n"
        text += block
    write_text(path, text)


def ensure_compose_provider_passthrough(path: Path) -> None:
    text = read_text(path)
    for key in ("CHUMMER_PROVIDER_BROWSERACT_API_KEY", "CHUMMER_PROVIDER_UNMIXR_API_KEY"):
        if key in text:
            continue
        anchor = '      CHUMMER_AI_1MINAI_FALLBACK_API_KEY: "${CHUMMER_AI_1MINAI_FALLBACK_API_KEY:-}"\n'
        line = f'      {key}: "${{{key}:-}}"\n'
        if anchor in text:
            text = text.replace(anchor, anchor + line, 1)
        else:
            if text and not text.endswith("\n"):
                text += "\n"
            text += line
    write_text(path, text)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("key_file", help="Path to a file containing the Unmixr API key")
    args = parser.parse_args()

    key_path = Path(args.key_file)
    unmixr_api_key = key_path.read_text(encoding="utf-8").strip()
    if not unmixr_api_key:
        raise SystemExit("Unmixr API key file is empty")

    ea_env_text = read_text(EA_ENV)
    ea_env_text = set_env_value(ea_env_text, "UNMIXR_API_KEY", unmixr_api_key)
    write_text(EA_ENV, ea_env_text)

    ensure_example_unmixr(EA_ENV_EXAMPLE)
    ensure_example_unmixr(EA_ENV_LOCAL_EXAMPLE)

    memory_compose = read_text(EA_DOCKER_MEMORY)
    memory_compose = memory_compose.replace("EA_LEDGER_BACKEND=memory", "EA_STORAGE_BACKEND=memory")
    write_text(EA_DOCKER_MEMORY, memory_compose)

    ea_values = parse_env_values(ea_env_text)

    provider_lines = [
        "# Synced provider credentials from /docker/EA/.env",
    ]
    for key in sorted(k for k in ea_values if "API_KEY" in k):
        provider_lines.append(f"{key}={ea_values[key]}")

    onemin_chain = unique_ordered(
        [
            value
            for key_name in (
                "ONEMIN_AI_API_KEY",
                "ONEMIN_AI_API_KEY_FALLBACK_1",
                "ONEMIN_AI_API_KEY_FALLBACK_2",
                "ONEMIN_AI_API_KEY_FALLBACK_3",
            )
            for value in split_csv_values(ea_values.get(key_name, ""))
        ]
    )
    onemin_primary = onemin_chain[0] if onemin_chain else ""
    onemin_fallback = ",".join(onemin_chain[1:])
    provider_lines.extend(
        [
            "",
            "# Chummer provider mappings",
            f"CHUMMER_AI_1MINAI_PRIMARY_API_KEY={','.join(onemin_chain)}",
            f"CHUMMER_AI_1MINAI_FALLBACK_API_KEY={onemin_fallback}",
            f"CHUMMER_PROVIDER_BROWSERACT_API_KEY={ea_values.get('BROWSERACT_API_KEY', '')}",
            f"CHUMMER_PROVIDER_UNMIXR_API_KEY={ea_values.get('UNMIXR_API_KEY', '')}",
        ]
    )
    write_text(CHUMMER_ENV_PROVIDERS, "\n".join(provider_lines).rstrip() + "\n")

    chummer_env = read_text(CHUMMER_ENV)
    if onemin_chain:
        # Keep all available 1min keys in the primary slot for round-robin usage.
        # Keep only non-empty keys in the fallback slot for explicit operator override.
        chummer_env = set_env_value(chummer_env, "CHUMMER_AI_1MINAI_PRIMARY_API_KEY", ",".join(onemin_chain))
        chummer_env = set_env_value(chummer_env, "CHUMMER_AI_1MINAI_FALLBACK_API_KEY", onemin_fallback)
    chummer_env = set_env_value(chummer_env, "CHUMMER_PROVIDER_BROWSERACT_API_KEY", ea_values.get("BROWSERACT_API_KEY", ""))
    chummer_env = set_env_value(chummer_env, "CHUMMER_PROVIDER_UNMIXR_API_KEY", ea_values.get("UNMIXR_API_KEY", ""))
    write_text(CHUMMER_ENV, chummer_env)

    ensure_gitignore_entry(CHUMMER_GITIGNORE, ".env.providers")
    ensure_chummer_provider_example(CHUMMER_ENV_EXAMPLE)
    ensure_compose_provider_passthrough(CHUMMER_DOCKER_COMPOSE)

    print("updated /docker/EA/.env")
    print("updated /docker/EA/.env.example")
    print("updated /docker/EA/.env.local.example")
    print("updated /docker/EA/docker-compose.memory.yml")
    print("updated /docker/chummer5a/.env")
    print("updated /docker/chummer5a/.env.providers")
    print("updated /docker/chummer5a/.gitignore")
    print("updated /docker/chummer5a/.env.example")
    print("updated /docker/chummer5a/docker-compose.yml")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
