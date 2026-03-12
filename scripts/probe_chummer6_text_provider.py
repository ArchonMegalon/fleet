#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import urllib.error
import urllib.request
from pathlib import Path


EA_ROOT = Path("/docker/EA")
DEFAULT_MODELS = [
    "gpt-4o-mini",
    "gemini-2.0-flash-lite",
    "gemini-2.0-flash",
    "claude-3-5-haiku-latest",
    "claude-3-5-sonnet-latest",
    "qwen-max",
    "qwen-plus",
]


def resolve_onemin_keys() -> list[str]:
    output = subprocess.check_output(
        ["bash", str(EA_ROOT / "scripts" / "resolve_onemin_ai_key.sh"), "--all"],
        text=True,
    )
    keys: list[str] = []
    for raw in output.splitlines():
        key = raw.strip()
        if key and key not in keys:
            keys.append(key)
    return keys[:1]


def request_variants(prompt: str, *, model: str, api_key: str) -> list[tuple[str, dict[str, str], dict[str, object]]]:
    prompt_object_variants = [
        {"prompt": prompt},
        {"messages": [{"role": "user", "content": prompt}]},
        {"prompt": prompt, "messages": [{"role": "user", "content": prompt}]},
    ]
    type_variants = [
        ("https://api.1min.ai/api/chat-with-ai", "UNIFY_CHAT_WITH_AI"),
        ("https://api.1min.ai/api/features", "UNIFY_CHAT_WITH_AI"),
        ("https://api.1min.ai/api/chat-with-ai", "CHAT_WITH_AI"),
        ("https://api.1min.ai/api/features", "CHAT_WITH_AI"),
    ]
    header_variants = [
        {"Content-Type": "application/json", "API-KEY": api_key},
        {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        {"Content-Type": "application/json", "X-API-KEY": api_key},
    ]
    variants: list[tuple[str, dict[str, str], dict[str, object]]] = []
    for url, request_type in type_variants:
        for prompt_object in prompt_object_variants:
            payload = {
                "type": request_type,
                "model": model,
                "promptObject": prompt_object,
            }
            for headers in header_variants:
                variants.append((url, headers, payload))
    return variants


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", action="append", default=[])
    args = parser.parse_args()

    keys = resolve_onemin_keys()
    if not keys:
        print(json.dumps({"status": "error", "reason": "no_onemin_key"}))
        return 1
    api_key = keys[0]
    models = args.model or DEFAULT_MODELS
    prompt = 'Return only this JSON: {"ok":true,"provider":"1min"}'
    results: list[dict[str, object]] = []

    for model in models:
        result: dict[str, object] = {"model": model, "status": "failed"}
        for url, headers, payload in request_variants(prompt, model=model, api_key=api_key):
            request = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                method="POST",
            )
            try:
                with urllib.request.urlopen(request, timeout=60) as response:
                    body = response.read().decode("utf-8", errors="replace")
                result = {
                    "model": model,
                    "status": "ok",
                    "endpoint": url,
                    "body_preview": body[:200],
                }
                break
            except urllib.error.HTTPError as exc:
                body = exc.read().decode("utf-8", errors="replace")
                result = {
                    "model": model,
                    "status": f"http_{exc.code}",
                    "endpoint": url,
                    "body_preview": body[:200],
                }
                if exc.code in {401, 403}:
                    break
            except Exception as exc:  # noqa: BLE001
                result = {
                    "model": model,
                    "status": type(exc).__name__,
                    "endpoint": url,
                    "body_preview": str(exc)[:200],
                }
        results.append(result)

    print(json.dumps({"results": results}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
