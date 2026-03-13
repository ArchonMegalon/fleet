#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import sys

sys.path.insert(0, "/docker/EA/scripts")
from chummer6_runtime_config import load_runtime_overrides  # type: ignore  # noqa: E402

ENV_PATH = Path("/docker/EA/.env")


def load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


FILE_ENV = load_env_file(ENV_PATH)
POLICY_ENV = load_runtime_overrides()


def env_value(name: str) -> str:
    return str(os.environ.get(name) or FILE_ENV.get(name) or POLICY_ENV.get(name) or "").strip()


def build_url(base_url: str, endpoint: str) -> str:
    clean_base = str(base_url or "").strip().rstrip("/")
    clean_endpoint = str(endpoint or "").strip().lstrip("/")
    if clean_base.endswith("/api/v1") and clean_endpoint.startswith("api/v1/"):
        clean_endpoint = clean_endpoint[len("api/v1/") :]
    elif clean_base.endswith("/api") and clean_endpoint.startswith("api/"):
        clean_endpoint = clean_endpoint[len("api/") :]
    return clean_base + "/" + clean_endpoint


def unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        normalized = str(value or "").strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        out.append(normalized)
    return out


def base_candidates() -> list[str]:
    configured_base = env_value("CHUMMER6_MAGIXAI_BASE_URL") or "https://beta.aimagicx.com/api/v1"
    return unique(
        [
            configured_base.rstrip("/"),
            "https://beta.aimagicx.com/api/v1",
            "https://beta.aimagicx.com/api",
            "https://beta.aimagicx.com/v1",
            "https://beta.aimagicx.com",
            "https://api.aimagicx.com/api/v1",
            "https://api.aimagicx.com/api",
            "https://api.aimagicx.com/v1",
            "https://api.aimagicx.com",
            "https://www.aimagicx.com/api/v1",
            "https://www.aimagicx.com/api",
            "https://www.aimagicx.com/v1",
            "https://www.aimagicx.com",
        ]
    )


def header_variants(api_key: str) -> list[tuple[str, dict[str, str]]]:
    return [
        (
            "authorization_bearer",
            {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "User-Agent": "fleet-magix-probe/1.0",
            },
        ),
        (
            "x_api_key",
            {
                "X-API-Key": api_key,
                "Content-Type": "application/json",
                "User-Agent": "fleet-magix-probe/1.0",
            },
        ),
        (
            "api_key",
            {
                "API-KEY": api_key,
                "Content-Type": "application/json",
                "User-Agent": "fleet-magix-probe/1.0",
            },
        ),
        (
            "x_mgx_api_key",
            {
                "X-MGX-API-KEY": api_key,
                "Content-Type": "application/json",
                "User-Agent": "fleet-magix-probe/1.0",
            },
        ),
    ]


def request_specs(width: int, height: int) -> list[dict[str, Any]]:
    size = f"{width}x{height}"
    image_model = env_value("CHUMMER6_MAGIXAI_MODEL") or "qwen-image"
    return [
        {
            "kind": "text",
            "method": "POST",
            "endpoint": "/chat",
            "payload": {
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": "reply with exactly ok"}],
            },
        },
        {
            "kind": "text",
            "method": "POST",
            "endpoint": "/chat/completions",
            "payload": {
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": "reply with exactly ok"}],
            },
        },
        {
            "kind": "text",
            "method": "POST",
            "endpoint": "/v1/chat/completions",
            "payload": {
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": "reply with exactly ok"}],
            },
        },
        {
            "kind": "image",
            "method": "POST",
            "endpoint": "/ai-image/generate",
            "payload": {
                "model": image_model,
                "prompt": "red square test image",
                "size": size,
                "response_format": "url",
            },
        },
        {
            "kind": "image",
            "method": "POST",
            "endpoint": "/images/generations",
            "payload": {
                "model": image_model,
                "prompt": "red square test image",
                "size": size,
                "response_format": "url",
                "n": 1,
            },
        },
        {
            "kind": "image",
            "method": "POST",
            "endpoint": "/v1/images/generations",
            "payload": {
                "model": image_model,
                "prompt": "red square test image",
                "size": size,
                "response_format": "url",
                "n": 1,
            },
        },
        {
            "kind": "image",
            "method": "POST",
            "endpoint": "/generate",
            "payload": {
                "model": image_model,
                "prompt": "red square test image",
                "size": size,
                "response_format": "url",
            },
        },
        {
            "kind": "image",
            "method": "OPTIONS",
            "endpoint": "/ai-image/generate",
            "payload": None,
        },
        {
            "kind": "image",
            "method": "OPTIONS",
            "endpoint": "/images/generations",
            "payload": None,
        },
    ]


def run_probe(url: str, method: str, headers: dict[str, str], payload: dict[str, Any] | None, timeout: int) -> dict[str, Any]:
    body_bytes = None
    if payload is not None:
        body_bytes = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=body_bytes, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
            body = raw.decode("utf-8", errors="replace")
            return {
                "status": int(response.status),
                "content_type": str(response.headers.get("Content-Type") or ""),
                "allow": str(response.headers.get("Allow") or ""),
                "body_preview": body[:240],
            }
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return {
            "status": int(exc.code),
            "content_type": str(exc.headers.get("Content-Type") or ""),
            "allow": str(exc.headers.get("Allow") or ""),
            "body_preview": body[:240],
        }
    except urllib.error.URLError as exc:
        return {
            "status": None,
            "error": f"urlerror:{exc.reason}",
        }
    except Exception as exc:  # pragma: no cover
        return {
            "status": None,
            "error": f"error:{exc}",
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe live AI Magicx API endpoint variants.")
    parser.add_argument("--width", type=int, default=512)
    parser.add_argument("--height", type=int, default=512)
    parser.add_argument("--timeout", type=int, default=5)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--all-bases", action="store_true")
    parser.add_argument("--all-headers", action="store_true")
    parser.add_argument("--all-specs", action="store_true")
    args = parser.parse_args()

    api_key = env_value("AI_MAGICX_API_KEY")
    if not api_key:
        print(json.dumps({"ok": False, "error": "missing AI_MAGICX_API_KEY in /docker/EA/.env"}))
        return 1

    base_urls = base_candidates()
    if not args.all_bases:
        base_urls = base_urls[:4]
    headers_to_try = header_variants(api_key)
    if not args.all_headers:
        headers_to_try = headers_to_try[:2]
    specs_to_try = request_specs(args.width, args.height)
    if not args.all_specs:
        specs_to_try = specs_to_try[:6]

    rows: list[dict[str, Any]] = []
    for base_url in base_urls:
        for spec in specs_to_try:
            for header_label, headers in headers_to_try:
                row = {
                    "base_url": base_url,
                    "kind": spec["kind"],
                    "method": spec["method"],
                    "endpoint": spec["endpoint"],
                    "header": header_label,
                }
                row.update(
                    run_probe(
                        build_url(base_url, str(spec["endpoint"])),
                        str(spec["method"]),
                        headers,
                        spec["payload"],
                        args.timeout,
                    )
                )
                rows.append(row)

    def score(row: dict[str, Any]) -> tuple[int, int, int]:
        status = row.get("status")
        body_preview = str(row.get("body_preview") or "").lower()
        content_type = str(row.get("content_type") or "").lower()
        is_success = 1 if isinstance(status, int) and 200 <= status < 300 else 0
        is_json = 1 if "json" in content_type else 0
        looks_not_found = 1 if "not found" in body_preview or "cannot post" in body_preview else 0
        return (is_success, is_json, -looks_not_found)

    summary = {
        "ok": any(isinstance(row.get("status"), int) and 200 <= int(row["status"]) < 300 for row in rows),
        "configured_base_url": env_value("CHUMMER6_MAGIXAI_BASE_URL") or "https://beta.aimagicx.com/api/v1",
        "bases_tested": len(base_urls),
        "headers_tested": len(headers_to_try),
        "specs_tested": len(specs_to_try),
        "rows_tested": len(rows),
        "top": sorted(rows, key=score, reverse=True)[: max(1, args.limit)],
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
