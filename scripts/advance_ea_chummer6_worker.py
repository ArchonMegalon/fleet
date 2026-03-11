#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path


EA_ROOT = Path("/docker/EA")
SCRIPTS_DIR = EA_ROOT / "scripts"
WORKER_PATH = SCRIPTS_DIR / "chummer6_guide_worker.py"
MEDIA_WORKER_PATH = SCRIPTS_DIR / "chummer6_guide_media_worker.py"
BOOTSTRAP_SKILL_PATH = SCRIPTS_DIR / "bootstrap_chummer6_guide_skill.py"
PROVIDER_READINESS_PATH = SCRIPTS_DIR / "chummer6_provider_readiness.py"
MARKUPGO_RENDER_PATH = SCRIPTS_DIR / "chummer6_markupgo_render.py"
SMOKE_HELP_PATH = SCRIPTS_DIR / "smoke_help.sh"
ENV_EXAMPLE_PATH = EA_ROOT / ".env.example"
ENV_LOCAL_EXAMPLE_PATH = EA_ROOT / ".env.local.example"
LOCAL_POLICY_PATH = Path("/docker/fleet/.chummer6_local_policy.json")


WORKER_SCRIPT = """#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import urllib.error
import urllib.request
from pathlib import Path


EA_ROOT = Path(__file__).resolve().parents[1]
FLEET_GUIDE_SCRIPT = Path("/docker/fleet/scripts/finish_chummer6_guide.py")
OVERRIDE_OUT = Path("/docker/fleet/state/chummer6/ea_overrides.json")
DEFAULT_MODEL = "gpt-4o-mini"
FALLBACK_MODELS = (
    "gpt-4o-mini",
    "gpt-4.1-mini",
    "gpt-4.1-nano",
)
WORKING_VARIANT: dict[str, object] | None = None


def extract_json(text: str) -> dict[str, object]:
    raw = str(text or "").strip()
    if not raw:
        raise ValueError("empty model response")
    for candidate in (raw, raw.removeprefix("```json").removesuffix("```").strip(), raw.removeprefix("```").removesuffix("```").strip()):
        try:
            loaded = json.loads(candidate)
        except Exception:
            continue
        if isinstance(loaded, dict):
            return loaded
    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        loaded = json.loads(raw[start : end + 1])
        if isinstance(loaded, dict):
            return loaded
    raise ValueError("response did not contain a JSON object")


def resolve_onemin_keys() -> list[str]:
    output = subprocess.check_output(
        ["bash", str(EA_ROOT / "scripts" / "resolve_onemin_ai_key.sh"), "--all"],
        text=True,
    )
    keys: list[str] = []
    seen: set[str] = set()
    for raw in output.splitlines():
        key = raw.strip()
        if key and key not in seen:
            seen.add(key)
            keys.append(key)
    if not keys:
        raise RuntimeError("no 1min.AI key configured")
    return keys


def load_literal(name: str) -> dict[str, object]:
    module = ast.parse(FLEET_GUIDE_SCRIPT.read_text(encoding="utf-8"))
    for node in module.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == name:
                value = ast.literal_eval(node.value)
                if isinstance(value, dict):
                    return value
    raise RuntimeError(f"missing literal {name} in {FLEET_GUIDE_SCRIPT}")


PARTS = load_literal("PARTS")
HORIZONS = load_literal("HORIZONS")
GUIDE_ROOT = Path("/docker/chummercomplete/Chummer6")


def read_markdown_excerpt(relative_path: str, *, limit: int = 900) -> str:
    path = GUIDE_ROOT / relative_path
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8", errors="ignore")
    def scrub(line: str) -> str:
        cleaned = line.strip()
        cleaned = re.sub(r"^#+\\s*", "", cleaned)
        cleaned = re.sub(r"^>\\s*", "", cleaned)
        cleaned = re.sub(r"^[-*]\\s+", "", cleaned)
        cleaned = re.sub(r"`([^`]+)`", lambda m: m.group(1), cleaned)
        cleaned = re.sub(r"\\*\\*([^*]+)\\*\\*", lambda m: m.group(1), cleaned)
        cleaned = re.sub(r"\\*([^*]+)\\*", lambda m: m.group(1), cleaned)
        cleaned = re.sub(r"!\\[[^\\]]*\\]\\([^)]+\\)", "", cleaned)
        cleaned = re.sub(r"\\[([^\\]]+)\\]\\([^)]+\\)", lambda m: m.group(1), cleaned)
        cleaned = re.sub(r"\\s+", " ", cleaned)
        return cleaned.strip(" -")
    lines: list[str] = []
    for raw in text.splitlines():
        line = scrub(raw)
        if not line:
            continue
        if line.startswith("_Last synced:") or line.startswith("_Derived from:"):
            continue
        lines.append(line)
        if sum(len(row) for row in lines) >= limit:
            break
    return " ".join(lines)[:limit].strip()


def short_sentence(text: str, *, limit: int = 160) -> str:
    cleaned = " ".join(str(text or "").split()).strip()
    if not cleaned:
        return ""
    for splitter in (". ", "! ", "? ", ": "):
        head, sep, _tail = cleaned.partition(splitter)
        if sep and head.strip():
            cleaned = head.strip()
            break
    if cleaned.lower().startswith("chummer6 "):
        cleaned = cleaned[len("chummer6 ") :].strip()
    return cleaned[:limit].rstrip(" ,;:-")


def model_candidates(requested: str) -> list[str]:
    preferred = str(requested or "").strip() or DEFAULT_MODEL
    ordered = [preferred, *FALLBACK_MODELS]
    seen: set[str] = set()
    models: list[str] = []
    for model in ordered:
        candidate = str(model or "").strip()
        if candidate and candidate not in seen:
            seen.add(candidate)
            models.append(candidate)
    return models


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


def extract_response_json(body: dict[str, object]) -> dict[str, object]:
    candidates: list[object] = []
    ai_record = body.get("aiRecord") if isinstance(body, dict) else None
    if isinstance(ai_record, dict):
        details = ai_record.get("aiRecordDetail")
        if isinstance(details, dict):
            candidates.extend((details.get("resultObject") or []))
        candidates.append(ai_record.get("result"))
    candidates.extend(
        [
            body.get("resultObject") if isinstance(body, dict) else None,
            body.get("result") if isinstance(body, dict) else None,
            body.get("message") if isinstance(body, dict) else None,
            ((body.get("choices") or [{}])[0] if isinstance(body, dict) else {}).get("message", {}).get("content"),
            ((body.get("data") or [{}])[0] if isinstance(body, dict) else {}).get("content"),
        ]
    )
    for candidate in candidates:
        if candidate is None:
            continue
        if isinstance(candidate, list):
            for row in candidate:
                if row is None:
                    continue
                try:
                    return extract_json(str(row))
                except Exception:
                    continue
            continue
        try:
            return extract_json(str(candidate))
        except Exception:
            continue
    raise RuntimeError("1min.AI returned no parseable JSON payload")


def chat_json(prompt: str, *, model: str = DEFAULT_MODEL) -> dict[str, object]:
    global WORKING_VARIANT
    errors: list[str] = []
    keys = resolve_onemin_keys()
    models = model_candidates(model)
    for api_key in keys:
        key_mask = f"{api_key[:6]}…{api_key[-4:]}" if len(api_key) > 10 else "***"
        for candidate_model in models:
            variants = request_variants(prompt, model=candidate_model, api_key=api_key)
            if WORKING_VARIANT:
                variants = [tuple(WORKING_VARIANT.values())] + variants
            seen: set[str] = set()
            deduped: list[tuple[str, dict[str, str], dict[str, object]]] = []
            for url, headers, payload in variants:
                identity = json.dumps([url, headers, payload], sort_keys=True)
                if identity in seen:
                    continue
                seen.add(identity)
                deduped.append((url, headers, payload))
            for url, headers, payload in deduped:
                request = urllib.request.Request(
                    url,
                    headers=headers,
                    data=json.dumps(payload).encode("utf-8"),
                    method="POST",
                )
                try:
                    with urllib.request.urlopen(request, timeout=180) as response:
                        body = json.loads(response.read().decode("utf-8"))
                except urllib.error.HTTPError as exc:
                    body = exc.read().decode("utf-8", errors="replace").strip()
                    errors.append(
                        f"{exc.code} model={candidate_model} key={key_mask} url={url} auth={','.join(headers.keys())} body={body[:240]}"
                    )
                    continue
                except urllib.error.URLError as exc:
                    errors.append(f"urlerror model={candidate_model} key={key_mask} url={url} reason={exc.reason}")
                    continue
                WORKING_VARIANT = {
                    "url": url,
                    "headers": headers,
                    "payload": payload,
                }
                return extract_response_json(body)
    raise RuntimeError("1min.AI request failed; " + " || ".join(errors[:8]))


def build_part_prompt(name: str, item: dict[str, object]) -> str:
    owns = "\\n".join(f"- {line}" for line in item.get("owns", []))
    not_owns = "\\n".join(f"- {line}" for line in item.get("not_owns", []))
    return f\"\"\"You are writing downstream-only copy for the human-facing Chummer6 guide.

Task: return a JSON object only with keys intro, why, now.

Voice rules:
- clear, slightly playful, Shadowrun-flavored
- plain language first
- SR jargon is welcome
- mild dev roasting is allowed
- no mention of Fleet
- no mention of chummer5a
- no control-plane jargon
- no markdown fences

Part id: {name}
Title: {item.get("title", "")}
Tagline: {item.get("tagline", "")}
Current intro:
{item.get("intro", "")}

Why it matters:
{item.get("why", "")}

What it owns:
{owns}

What it does not own:
{not_owns}

Current now-text:
{item.get("now", "")}

Return valid JSON only.
\"\"\"


def build_horizon_prompt(name: str, item: dict[str, object]) -> str:
    foundations = "\\n".join(f"- {line}" for line in item.get("foundations", []))
    repos = ", ".join(str(repo) for repo in item.get("repos", []))
    return f\"\"\"You are writing downstream-only horizon copy for the human-facing Chummer6 guide.

Task: return a JSON object only with keys hook, brutal_truth, use_case.

Voice rules:
- sell the idea harder
- clear, punchy, Shadowrun-flavored
- SR jargon is welcome
- mild dev roasting is allowed
- keep it exciting without pretending it is active work
- no mention of Fleet
- no mention of chummer5a
- no markdown fences

Horizon id: {name}
Title: {item.get("title", "")}
Current hook:
{item.get("hook", "")}

Current brutal truth:
{item.get("brutal_truth", "")}

Current use case:
{item.get("use_case", "")}

Problem:
{item.get("problem", "")}

Foundations:
{foundations}

Touched repos later:
{repos}

Return valid JSON only.
\"\"\"


def build_media_prompt(kind: str, name: str, item: dict[str, object]) -> str:
    title = str(item.get("title", name.replace("-", " ").title())).strip()
    foundations = "\\n".join(f"- {line}" for line in item.get("foundations", []))
    repos = ", ".join(str(repo) for repo in item.get("repos", []))
    if kind == "hero":
        readme_excerpt = read_markdown_excerpt("README.md", limit=900)
        current_excerpt = read_markdown_excerpt("NOW/current-phase.md", limit=700)
        return f\"\"\"You are writing image-card copy for the human-facing Chummer6 guide landing hero.

Task: return a JSON object only with keys badge, title, subtitle, kicker, note, meta, visual_prompt.

Voice rules:
- clear, inviting, slightly playful, Shadowrun-flavored
- this is a human-facing guide, not a spec
- SR jargon is welcome
- mild dev roasting is allowed
- no mention of Fleet
- no mention of chummer5a
- no markdown fences

Source excerpts:
README:
{readme_excerpt}

Current phase:
{current_excerpt}

Requirements:
- infer the scene from the source, do not literalize repo-role labels
- do not say or imply "visitor center"
- visual_prompt must describe an actual cyberpunk scene, not a brochure cover
- visual_prompt must be no-text / no-logo / no-watermark / 16:9
- the visible badge/title/subtitle/kicker/note should feel like guide copy, not compliance language

Return valid JSON only.
\"\"\"
    horizon_excerpt = read_markdown_excerpt(f"HORIZONS/{name}.md", limit=900)
    return f\"\"\"You are writing image-card copy for a human-facing Chummer6 horizon banner.

Task: return a JSON object only with keys badge, title, subtitle, kicker, note, meta, visual_prompt.

Voice rules:
- clear, punchy, slightly funny, Shadowrun-flavored
- sell the horizon harder
- the image should feel cool, dangerous, specific, and scene-first
- SR jargon is welcome
- mild dev roasting is allowed
- no mention of Fleet
- no mention of chummer5a
- no markdown fences

Source page excerpt:
{horizon_excerpt}

Horizon id: {name}
Title: {title}
Current hook:
{item.get("hook", "")}

Current brutal truth:
{item.get("brutal_truth", "")}

Current use case:
{item.get("use_case", "")}

Problem:
{item.get("problem", "")}

Foundations:
{foundations}

Touched repos later:
{repos}

Requirements:
- infer the scene from the source, do not just repeat headings back
- visual_prompt must describe an actual cyberpunk scene tied to this horizon
- visual_prompt must be no-text / no-logo / no-watermark / 16:9
- the visible copy should sell the horizon without pretending it is active build work

Return valid JSON only.
\"\"\"


def fallback_part_override(name: str, item: dict[str, object]) -> dict[str, str]:
    title = str(item.get("title", name.replace("-", " ").title())).strip()
    tagline = str(item.get("tagline", "")).strip().rstrip(".")
    intro = str(item.get("intro", "")).strip()
    why = str(item.get("why", "")).strip()
    now = str(item.get("now", "")).strip()
    return {
        "intro": (
            f"{title} is {tagline.lower()} when the chrome is working and the excuses are not. "
            f"{intro}"
        ).strip(),
        "why": (
            f"{why} If this part goes sideways, the whole run gets janky fast and somebody starts blaming the dev."
            if why
            else f"If {title} goes sideways, the whole run gets janky fast and somebody starts blaming the dev."
        ),
        "now": (
            f"{now} The short version: make it real, keep it sharp, and stop letting legacy duct tape cosplay as architecture."
            if now
            else f"Right now the job is to make {title} real, sharp, and impossible to mistake for another half-finished split."
        ),
    }


def fallback_horizon_override(name: str, item: dict[str, object]) -> dict[str, str]:
    title = str(item.get("title", name.replace("-", " ").title())).strip()
    hook = str(item.get("hook", "")).strip()
    brutal_truth = str(item.get("brutal_truth", "")).strip()
    use_case = str(item.get("use_case", "")).strip()
    return {
        "hook": (
            f"{hook} This is the kind of horizon that makes a runner grin, a GM squint, and the dev pretend this was definitely the plan all along."
            if hook
            else f"{title} is the kind of horizon that makes a runner grin, a GM squint, and the dev pretend this was definitely the plan all along."
        ),
        "brutal_truth": (
            f"{brutal_truth} If this ever lands cleanly, Chummer gets smarter, meaner, and much harder to bullshit."
            if brutal_truth
            else f"The brutal truth: if {title} ever lands cleanly, Chummer gets smarter, meaner, and much harder to bullshit."
        ),
        "use_case": (
            f"{use_case} That is the moment where the future version of Chummer stops sounding like chrome daydreams and starts feeling dangerously real."
            if use_case
            else f"The use case: you hit the button, the chrome lights up, and the future version of Chummer suddenly feels dangerously real."
        ),
    }


def fallback_media_override(kind: str, name: str, item: dict[str, object]) -> dict[str, str]:
    title = str(item.get("title", name.replace("-", " ").title())).strip()
    hook = " ".join(str(item.get("hook", "")).split()).strip()
    brutal_truth = " ".join(str(item.get("brutal_truth", "")).split()).strip()
    use_case = " ".join(str(item.get("use_case", "")).split()).strip()
    foundations = [str(line).strip() for line in item.get("foundations", []) if str(line).strip()]
    repos = [str(repo).replace("chummer6-", "") for repo in item.get("repos", []) if str(repo).strip()]
    if kind == "hero":
        guide_summary = read_markdown_excerpt("README.md", limit=320) or "The human guide to the next Chummer."
        phase_summary = read_markdown_excerpt("NOW/current-phase.md", limit=220)
        short_guide = short_sentence(guide_summary) or "The human guide to the next Chummer"
        short_phase = short_sentence(phase_summary) or "Foundation work first, fireworks later"
        return {
            "badge": "Chummer6",
            "title": "Chummer6",
            "subtitle": hook or short_guide,
            "kicker": foundations[0] if foundations else "Guide",
            "note": brutal_truth or short_phase or "A readable guide wall for curious chummers, nervous test dummies, and the occasional roasted dev.",
            "meta": "",
            "visual_prompt": (
                f"Wide cinematic cyberpunk concept art for Chummer6, inspired by this guide summary: {guide_summary}. "
                f"Current phase mood: {phase_summary or 'foundations first, chrome later'}. "
                "Use a dangerous but inviting street-level scene with commlink, cyberdeck, holographic artifacts, rain, neon, and map-on-the-wall energy. "
                "No text, no logo, no watermark, 16:9."
            ),
        }
    return {
        "badge": "Horizon",
        "title": title,
        "subtitle": hook or use_case or brutal_truth or f"{title} is a horizon lane with too much chrome to ignore and too much blast radius to rush.",
        "kicker": repos[0] if repos else (foundations[0] if foundations else "Horizon lane"),
        "note": brutal_truth or use_case or "Horizon only. Slick enough to sell, dangerous enough to keep parked for now.",
        "meta": "",
        "visual_prompt": f"Wide cinematic cyberpunk concept art for {title}, {hook or use_case or brutal_truth or 'future-shadowrun capability'}, scene-first composition, dark humor, no text, no logo, no watermark, 16:9",
    }


def normalize_media_override(kind: str, cleaned: dict[str, str], item: dict[str, object]) -> dict[str, str]:
    normalized = dict(cleaned)
    if kind == "hero":
        title = str(normalized.get("title", "")).strip().lower()
        if title in {"", "hero", "guide", "guide hero", "landing hero"}:
            normalized["title"] = "Chummer6"
        badge = str(normalized.get("badge", "")).strip()
        if not badge:
            normalized["badge"] = "Chummer6"
        kicker = str(normalized.get("kicker", "")).strip()
        if not kicker or kicker.lower() in {"visitor center", "front door"}:
            normalized["kicker"] = "Guide"
        subtitle = str(normalized.get("subtitle", "")).strip()
        if subtitle:
            normalized["subtitle"] = subtitle.replace("visitor center", "guide").replace("Visitor Center", "Guide")
            if normalized["subtitle"].lower().startswith("chummer6 "):
                normalized["subtitle"] = normalized["subtitle"][len("Chummer6 ") :].strip()
        note = str(normalized.get("note", "")).strip()
        if note:
            normalized["note"] = note.replace("visitor center", "guide").replace("Visitor center", "Guide")
            if normalized["note"].lower().startswith("current phase "):
                normalized["note"] = normalized["note"][len("Current Phase ") :].strip()
            normalized["note"] = short_sentence(normalized["note"], limit=180) or normalized["note"]
        normalized["meta"] = ""
        if not str(normalized.get("visual_prompt", "")).strip():
            normalized["visual_prompt"] = fallback_media_override("hero", "hero", {})["visual_prompt"]
        return normalized
    if not str(normalized.get("title", "")).strip():
        normalized["title"] = str(item.get("title", "")).strip()
    if not str(normalized.get("badge", "")).strip():
        normalized["badge"] = "Horizon"
    normalized["meta"] = ""
    if not str(normalized.get("visual_prompt", "")).strip():
        normalized["visual_prompt"] = fallback_media_override("horizon", str(item.get("slug", "") or item.get("title", "horizon")), item)["visual_prompt"]
    return normalized


def generate_overrides(*, include_parts: bool, include_horizons: bool, model: str) -> dict[str, object]:
    overrides: dict[str, object] = {
        "parts": {},
        "horizons": {},
        "media": {"hero": {}, "horizons": {}},
        "meta": {"generator": "ea", "provider": "1min.AI", "provider_status": "unknown", "provider_error": ""},
    }
    provider_available = True
    provider_error = ""
    if provider_available:
        try:
            result = chat_json(build_media_prompt("hero", "hero", {}), model=model)
            cleaned = {key: str(result.get(key, "")).strip() for key in ("badge", "title", "subtitle", "kicker", "note", "meta", "visual_prompt") if str(result.get(key, "")).strip()}
            cleaned = normalize_media_override("hero", cleaned, {})
        except Exception as exc:
            provider_available = False
            provider_error = str(exc)
            cleaned = fallback_media_override("hero", "hero", {})
    else:
        cleaned = fallback_media_override("hero", "hero", {})
    cleaned = normalize_media_override("hero", cleaned, {})
    overrides["media"]["hero"] = cleaned
    if include_parts:
        for name, item in PARTS.items():
            if provider_available:
                try:
                    result = chat_json(build_part_prompt(name, item), model=model)
                    cleaned = {key: str(result.get(key, "")).strip() for key in ("intro", "why", "now") if str(result.get(key, "")).strip()}
                except Exception as exc:
                    provider_available = False
                    provider_error = str(exc)
                    cleaned = fallback_part_override(name, item)
            else:
                cleaned = fallback_part_override(name, item)
            if cleaned:
                overrides["parts"][name] = cleaned
    if include_horizons:
        for name, item in HORIZONS.items():
            if provider_available:
                try:
                    result = chat_json(build_horizon_prompt(name, item), model=model)
                    cleaned = {key: str(result.get(key, "")).strip() for key in ("hook", "brutal_truth", "use_case") if str(result.get(key, "")).strip()}
                except Exception as exc:
                    provider_available = False
                    provider_error = str(exc)
                    cleaned = fallback_horizon_override(name, item)
            else:
                cleaned = fallback_horizon_override(name, item)
            if cleaned:
                overrides["horizons"][name] = cleaned
            if provider_available:
                try:
                    media_result = chat_json(build_media_prompt("horizon", name, item), model=model)
                    media_cleaned = {key: str(media_result.get(key, "")).strip() for key in ("badge", "title", "subtitle", "kicker", "note", "meta", "visual_prompt") if str(media_result.get(key, "")).strip()}
                    media_cleaned = normalize_media_override("horizon", media_cleaned, item)
                except Exception as exc:
                    provider_available = False
                    provider_error = str(exc)
                    media_cleaned = fallback_media_override("horizon", name, item)
            else:
                media_cleaned = fallback_media_override("horizon", name, item)
            media_cleaned = normalize_media_override("horizon", media_cleaned, item)
            overrides["media"]["horizons"][name] = media_cleaned
    overrides["meta"]["provider_status"] = "ok" if provider_available else "fallback_local_templates"
    overrides["meta"]["provider_error"] = provider_error
    return overrides


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Chummer6 downstream guide overrides through EA using 1min.AI.")
    parser.add_argument("--output", default=str(OVERRIDE_OUT), help="Where to write the override JSON.")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="1min.AI chat model.")
    parser.add_argument("--parts-only", action="store_true", help="Generate part-page overrides only.")
    parser.add_argument("--horizons-only", action="store_true", help="Generate horizon-page overrides only.")
    args = parser.parse_args()

    include_parts = not args.horizons_only
    include_horizons = not args.parts_only
    overrides = generate_overrides(
        include_parts=include_parts,
        include_horizons=include_horizons,
        model=str(args.model or DEFAULT_MODEL).strip() or DEFAULT_MODEL,
    )
    output_path = Path(args.output).expanduser()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(overrides, indent=2, ensure_ascii=True) + "\\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(output_path),
                "parts": len(overrides.get("parts", {})),
                "horizons": len(overrides.get("horizons", {})),
                "provider_status": ((overrides.get("meta") or {}).get("provider_status", "")),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
"""


SMOKE_HELP_SCRIPT = """#!/usr/bin/env bash
set -euo pipefail

EA_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  cat <<'EOF'
Usage:
  bash scripts/smoke_help.sh

Run the script-help smoke contract by checking that key operator scripts return
a Usage header for their --help output.
EOF
  exit 0
fi

SCRIPTS=(
  scripts/deploy.sh
  scripts/db_bootstrap.sh
  scripts/db_status.sh
  scripts/db_size.sh
  scripts/db_retention.sh
  scripts/smoke_api.sh
  scripts/smoke_postgres.sh
  scripts/test_postgres_contracts.sh
  scripts/list_endpoints.sh
  scripts/version_info.sh
  scripts/export_openapi.sh
  scripts/diff_openapi.sh
  scripts/prune_openapi.sh
  scripts/operator_summary.sh
  scripts/support_bundle.sh
  scripts/archive_tasks.sh
  scripts/verify_release_assets.sh
)

for s in "${SCRIPTS[@]}"; do
  echo "== help smoke: ${s} =="
  out="$(bash "${EA_ROOT}/${s}" --help)"
  if [[ "${out}" != *"Usage:"* ]]; then
    echo "missing Usage header in ${s} --help output" >&2
    exit 21
  fi
done

echo "help smoke complete"
"""


MEDIA_WORKER_SCRIPT = """#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import shlex
import subprocess
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


EA_ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = EA_ROOT / ".env"
STATE_OUT = Path("/docker/fleet/state/chummer6/ea_media_last.json")
MANIFEST_OUT = Path("/docker/fleet/state/chummer6/ea_media_manifest.json")
FLEET_GUIDE_SCRIPT = Path("/docker/fleet/scripts/finish_chummer6_guide.py")
DEFAULT_PROVIDER_ORDER = [
    "magixai",
    "markupgo",
    "prompting_systems",
    "browseract_prompting_systems",
    "onemin",
    "local_raster",
]
PALETTES = [
    ("#0f766e", "#34d399"),
    ("#1d4ed8", "#7dd3fc"),
    ("#7c3aed", "#c084fc"),
    ("#7c2d12", "#fb923c"),
    ("#be123c", "#fb7185"),
    ("#4338ca", "#818cf8"),
]


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


def import_guide_module():
    spec = importlib.util.spec_from_file_location("finish_chummer6_guide", FLEET_GUIDE_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {FLEET_GUIDE_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


GUIDE = import_guide_module()


def provider_order() -> list[str]:
    raw = env_value("CHUMMER6_IMAGE_PROVIDER_ORDER")
    if not raw:
        return list(DEFAULT_PROVIDER_ORDER)
    values = [part.strip().lower() for part in raw.split(",") if part.strip()]
    return values or list(DEFAULT_PROVIDER_ORDER)


OVERRIDE_PATH = Path("/docker/fleet/state/chummer6/ea_overrides.json")


def shlex_command(env_name: str) -> list[str]:
    raw = env_value(env_name)
    return shlex.split(raw) if raw else []


def url_template(env_name: str) -> str:
    return env_value(env_name)


def load_media_overrides() -> dict[str, object]:
    if not OVERRIDE_PATH.exists():
        return {}
    try:
        loaded = json.loads(OVERRIDE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def format_command(parts: list[str], *, prompt: str, output: str, width: int, height: int) -> list[str]:
    return [part.format(prompt=prompt, output=output, width=width, height=height) for part in parts]


def run_command_provider(name: str, template: list[str], *, prompt: str, output_path: Path, width: int, height: int) -> tuple[bool, str]:
    if not template:
        return False, f"{name}:not_configured"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(
            format_command(template, prompt=prompt, output=str(output_path), width=width, height=height),
            check=True,
            text=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip()
        return False, f"{name}:command_failed:{detail[:240]}"
    if output_path.exists() and output_path.stat().st_size > 0:
        return True, f"{name}:rendered"
    return False, f"{name}:empty_output"


def run_url_provider(name: str, template: str, *, prompt: str, output_path: Path, width: int, height: int) -> tuple[bool, str]:
    if not template:
        return False, f"{name}:not_configured"
    url = template.format(
        prompt=urllib.parse.quote(prompt, safe=""),
        width=width,
        height=height,
        output=urllib.parse.quote(str(output_path), safe=""),
    )
    request = urllib.request.Request(url, headers={"User-Agent": "EA-Chummer6-Media/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            data = response.read()
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace").strip()
        return False, f"{name}:http_{exc.code}:{body[:240]}"
    except urllib.error.URLError as exc:
        return False, f"{name}:urlerror:{exc.reason}"
    if not data:
        return False, f"{name}:empty_output"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(data)
    return True, f"{name}:rendered"


def palette_for(prompt: str) -> tuple[str, str]:
    digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    return PALETTES[int(digest[:2], 16) % len(PALETTES)]


def title_for(prompt: str, output_path: Path) -> str:
    stem = output_path.stem.replace("-", " ").replace("_", " ").strip()
    if stem:
        return stem.title()
    words = [word for word in prompt.split() if word.isalpha()]
    return " ".join(words[:3]).title() or "Chummer6"


def layout_for(output_path: Path) -> str:
    name = output_path.name.lower()
    if "program-map" in name:
        return "grid"
    if "status-strip" in name:
        return "status"
    return "banner"


def render_local_raster(*, prompt: str, output_path: Path, width: int, height: int) -> tuple[bool, str]:
    accent, glow = palette_for(prompt)
    title = title_for(prompt, output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.suffix.lower() == ".gif":
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            for index in range(6):
                frame = GUIDE.synth_cyberpunk_png(
                    title,
                    accent,
                    glow,
                    width=width,
                    height=height,
                    phase=index * 0.55,
                    layout="banner",
                )
                (tmp / f"frame-{index:02d}.png").write_bytes(frame)
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-framerate",
                    "4",
                    "-i",
                    str(tmp / "frame-%02d.png"),
                    "-vf",
                    f"scale={width}:{height}:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse",
                    str(output_path),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
        return True, "local_raster:animated"
    output_path.write_bytes(
        GUIDE.synth_cyberpunk_png(
            title,
            accent,
            glow,
            width=width,
            height=height,
            layout=layout_for(output_path),
        )
    )
    return True, "local_raster:rendered"


def refine_prompt_local(prompt: str, *, target: str) -> str:
    cleaned = " ".join(prompt.split()).strip()
    suffix = " cinematic cyberpunk concept art, scene-first, no text, no logo, no watermark, 16:9"
    if target.endswith("chummer6-hero.png"):
        return f"{cleaned} Focus on a dangerous-but-inviting cyberpunk guide scene, not a literal building or signage shot.{suffix}"
    return f"{cleaned} Push the horizon fantasy harder and make the scene feel specific, dangerous, and a little funny.{suffix}"


def refine_prompt_with_ooda(*, prompt: str, target: str) -> str:
    # Best-effort Prompting Systems / BrowserAct refinement before rendering.
    command_names = [
        "CHUMMER6_BROWSERACT_PROMPTING_SYSTEMS_REFINE_COMMAND",
        "CHUMMER6_PROMPTING_SYSTEMS_REFINE_COMMAND",
        "CHUMMER6_PROMPT_REFINER_COMMAND",
    ]
    template_names = [
        "CHUMMER6_BROWSERACT_PROMPTING_SYSTEMS_REFINE_URL_TEMPLATE",
        "CHUMMER6_PROMPTING_SYSTEMS_REFINE_URL_TEMPLATE",
        "CHUMMER6_PROMPT_REFINER_URL_TEMPLATE",
    ]
    for env_name in command_names:
        command = shlex_command(env_name)
        if not command:
            continue
        try:
            completed = subprocess.run(
                [part.format(prompt=prompt, target=target) for part in command],
                check=True,
                text=True,
                capture_output=True,
            )
            refined = (completed.stdout or "").strip()
            if refined:
                return refined
        except Exception:
            continue
    for env_name in template_names:
        template = url_template(env_name)
        if not template:
            continue
        url = template.format(
            prompt=urllib.parse.quote(prompt, safe=""),
            target=urllib.parse.quote(target, safe=""),
        )
        request = urllib.request.Request(url, headers={"User-Agent": "EA-Chummer6-PromptRefiner/1.0"})
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                refined = response.read().decode("utf-8", errors="replace").strip()
            if refined:
                return refined
        except Exception:
            continue
    return refine_prompt_local(prompt, target=target)


def render_with_ooda(*, prompt: str, output_path: Path, width: int, height: int) -> dict[str, object]:
    attempts: list[str] = []
    for provider in provider_order():
        normalized = provider.strip().lower()
        if normalized == "magixai":
            ok, detail = run_command_provider("magixai", shlex_command("CHUMMER6_MAGIXAI_RENDER_COMMAND"), prompt=prompt, output_path=output_path, width=width, height=height)
            if not ok:
                ok, detail = run_url_provider("magixai", url_template("CHUMMER6_MAGIXAI_RENDER_URL_TEMPLATE"), prompt=prompt, output_path=output_path, width=width, height=height)
        elif normalized == "markupgo":
            ok, detail = run_command_provider("markupgo", shlex_command("CHUMMER6_MARKUPGO_RENDER_COMMAND"), prompt=prompt, output_path=output_path, width=width, height=height)
            if not ok:
                ok, detail = run_url_provider("markupgo", url_template("CHUMMER6_MARKUPGO_RENDER_URL_TEMPLATE"), prompt=prompt, output_path=output_path, width=width, height=height)
        elif normalized == "prompting_systems":
            ok, detail = run_command_provider("prompting_systems", shlex_command("CHUMMER6_PROMPTING_SYSTEMS_RENDER_COMMAND"), prompt=prompt, output_path=output_path, width=width, height=height)
            if not ok:
                ok, detail = run_url_provider("prompting_systems", url_template("CHUMMER6_PROMPTING_SYSTEMS_RENDER_URL_TEMPLATE"), prompt=prompt, output_path=output_path, width=width, height=height)
        elif normalized == "browseract_prompting_systems":
            if env_value("BROWSERACT_API_KEY"):
                ok, detail = run_command_provider("browseract_prompting_systems", shlex_command("CHUMMER6_BROWSERACT_PROMPTING_SYSTEMS_RENDER_COMMAND"), prompt=prompt, output_path=output_path, width=width, height=height)
                if not ok:
                    ok, detail = run_url_provider("browseract_prompting_systems", url_template("CHUMMER6_BROWSERACT_PROMPTING_SYSTEMS_RENDER_URL_TEMPLATE"), prompt=prompt, output_path=output_path, width=width, height=height)
                if not ok:
                    ok, detail = run_command_provider("browseract_prompting_systems", shlex_command("CHUMMER6_PROMPTING_SYSTEMS_RENDER_COMMAND"), prompt=prompt, output_path=output_path, width=width, height=height)
                if not ok:
                    ok, detail = run_url_provider("browseract_prompting_systems", url_template("CHUMMER6_PROMPTING_SYSTEMS_RENDER_URL_TEMPLATE"), prompt=prompt, output_path=output_path, width=width, height=height)
            else:
                ok, detail = False, "browseract_prompting_systems:not_configured"
        elif normalized in {"onemin", "1min", "1min.ai", "oneminai"}:
            ok, detail = run_command_provider("onemin", shlex_command("CHUMMER6_1MIN_RENDER_COMMAND"), prompt=prompt, output_path=output_path, width=width, height=height)
            if not ok:
                ok, detail = run_url_provider("onemin", url_template("CHUMMER6_1MIN_RENDER_URL_TEMPLATE"), prompt=prompt, output_path=output_path, width=width, height=height)
        elif normalized == "local_raster":
            ok, detail = render_local_raster(prompt=prompt, output_path=output_path, width=width, height=height)
        else:
            ok, detail = False, f"{normalized}:unknown_provider"
        attempts.append(detail)
        if ok:
            return {"provider": normalized, "status": detail, "attempts": attempts}
    raise RuntimeError("no image provider succeeded: " + " || ".join(attempts))


def asset_specs() -> list[dict[str, object]]:
    loaded = load_media_overrides()
    media = loaded.get("media") if isinstance(loaded, dict) else {}
    hero_override = media.get("hero") if isinstance(media, dict) else {}
    specs: list[dict[str, object]] = [
        {
            "target": "assets/hero/chummer6-hero.png",
            "prompt": (
                str(hero_override.get("visual_prompt", "")).strip()
                if isinstance(hero_override, dict) and str(hero_override.get("visual_prompt", "")).strip()
                else "Wide cinematic cyberpunk concept-art banner for Chummer6, battered commlink and cyberdeck on a rainy alley crate, holographic repo cards floating above it, gritty neon cyan and magenta lighting, dark humor, dangerous but inviting, strong center composition, no text, no logo, no watermark, 16:9"
            ),
            "width": 1280,
            "height": 720,
        }
    ]
    horizon_overrides = media.get("horizons") if isinstance(media, dict) else {}
    for slug, item in GUIDE.HORIZONS.items():
        override = horizon_overrides.get(slug) if isinstance(horizon_overrides, dict) else None
        prompt = (
            str(override.get("visual_prompt", "")).strip()
            if isinstance(override, dict) and str(override.get("visual_prompt", "")).strip()
            else str(item.get("prompt", "")).strip()
        )
        if not prompt:
            continue
        specs.append(
            {
                "target": f"assets/horizons/{slug}.png",
                "prompt": prompt,
                "width": 1280,
                "height": 720,
            }
        )
    return specs


def render_pack(*, output_dir: Path) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    assets: list[dict[str, object]] = []
    for spec in asset_specs():
        target = str(spec["target"])
        prompt = refine_prompt_with_ooda(prompt=str(spec["prompt"]), target=target)
        width = int(spec.get("width", 1280))
        height = int(spec.get("height", 720))
        out_path = output_dir / target
        out_path.parent.mkdir(parents=True, exist_ok=True)
        result = render_with_ooda(prompt=prompt, output_path=out_path, width=width, height=height)
        assets.append(
            {
                "target": target,
                "output": str(out_path),
                "provider": result["provider"],
                "status": result["status"],
                "attempts": result["attempts"],
            }
        )
    manifest = {
        "output_dir": str(output_dir),
        "assets": assets,
    }
    MANIFEST_OUT.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_OUT.write_text(json.dumps(manifest, indent=2, ensure_ascii=True) + "\\n", encoding="utf-8")
    STATE_OUT.write_text(
        json.dumps(
            {
                "output": str(output_dir),
                "provider": assets[0]["provider"] if assets else "none",
                "status": f"pack:rendered:{len(assets)}",
                "attempts": [asset["status"] for asset in assets],
            },
            indent=2,
            ensure_ascii=True,
        )
        + "\\n",
        encoding="utf-8",
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a Chummer6 guide asset through EA provider selection.")
    sub = parser.add_subparsers(dest="command", required=True)
    render = sub.add_parser("render")
    render.add_argument("--prompt", required=True)
    render.add_argument("--output", required=True)
    render.add_argument("--width", type=int, default=1280)
    render.add_argument("--height", type=int, default=720)
    render_pack_parser = sub.add_parser("render-pack")
    render_pack_parser.add_argument("--output-dir", default="/docker/fleet/state/chummer6/ea_media_assets")
    args = parser.parse_args()

    if args.command == "render-pack":
        manifest = render_pack(output_dir=Path(args.output_dir).expanduser())
        print(json.dumps({"output_dir": manifest["output_dir"], "assets": len(manifest["assets"]), "status": "rendered"}))
        return 0

    output_path = Path(args.output).expanduser()
    result = render_with_ooda(prompt=str(args.prompt), output_path=output_path, width=int(args.width), height=int(args.height))
    STATE_OUT.parent.mkdir(parents=True, exist_ok=True)
    STATE_OUT.write_text(json.dumps({"output": str(output_path), **result}, indent=2, ensure_ascii=True) + "\\n", encoding="utf-8")
    print(json.dumps({"output": str(output_path), "provider": result["provider"], "status": result["status"]}))
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
HOST = os.environ.get("EA_SKILL_HOST", "http://127.0.0.1:8080")


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
        "skill_key": "chummer6_guide_refresh",
        "task_key": "chummer6_guide_refresh",
        "name": "Chummer6 Guide Refresh",
        "description": "Generate human-facing Chummer6 guide copy and art from canonical sources, with provider-aware text and media hints.",
        "deliverable_type": "chummer6_guide_refresh_packet",
        "default_risk_class": "low",
        "default_approval_class": "none",
        "workflow_template": "rewrite",
        "allowed_tools": [],
        "evidence_requirements": ["repo_readmes", "design_scope", "public_status"],
        "memory_write_policy": "none",
        "memory_reads": ["entities", "relationships"],
        "memory_writes": [],
        "tags": ["chummer6", "guide", "docs", "media"],
        "authority_profile_json": {"authority_class": "draft", "review_class": "operator"},
        "provider_hints_json": {
            "primary": ["1min.AI", "AI Magicx", "Prompting Systems"],
            "research": ["BrowserAct"],
            "output": ["MarkupGo", "AI Magicx", "Prompting Systems"],
            "media": ["AI Magicx", "MarkupGo", "Prompting Systems"],
        },
        "tool_policy_json": {"allowed_tools": []},
        "human_policy_json": {"review_roles": ["guide_reviewer"]},
        "evaluation_cases_json": [{"case_key": "chummer6_guide_refresh_golden", "priority": "medium"}],
        "budget_policy_json": {
            "class": "low",
            "workflow_template": "rewrite",
            "skill_catalog_json": {
                "mode": "downstream_only",
                "capabilities": ["human_guide_copy", "guide_media_rendering", "tone_audit"],
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


PROVIDER_READINESS_SCRIPT = """#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path


EA_ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = EA_ROOT / ".env"
STATE_OUT = Path("/docker/fleet/state/chummer6/ea_provider_readiness.json")

RAW_KEY_NAMES = {
    "browseract": ["BROWSERACT_API_KEY", "BROWSERACT_API_KEY_FALLBACK_1", "BROWSERACT_API_KEY_FALLBACK_2", "BROWSERACT_API_KEY_FALLBACK_3"],
    "unmixr": ["UNMIXR_API_KEY"],
    "onemin": ["ONEMIN_AI_API_KEY", "ONEMIN_AI_API_KEY_FALLBACK_1", "ONEMIN_AI_API_KEY_FALLBACK_2", "ONEMIN_AI_API_KEY_FALLBACK_3"],
    "magixai": ["MAGIXAI_API_KEY", "AI_MAGICX_API_KEY", "AIMAGICX_API_KEY"],
    "markupgo": ["MARKUPGO_API_KEY"],
    "prompting_systems": ["PROMPTING_SYSTEMS_API_KEY"],
}

ADAPTER_ENV_NAMES = {
    "magixai": ["CHUMMER6_MAGIXAI_RENDER_COMMAND", "CHUMMER6_MAGIXAI_RENDER_URL_TEMPLATE"],
    "markupgo": ["CHUMMER6_MARKUPGO_RENDER_COMMAND", "CHUMMER6_MARKUPGO_RENDER_URL_TEMPLATE"],
    "prompting_systems": ["CHUMMER6_PROMPTING_SYSTEMS_RENDER_COMMAND", "CHUMMER6_PROMPTING_SYSTEMS_RENDER_URL_TEMPLATE"],
    "browseract_prompting_systems": [
        "CHUMMER6_BROWSERACT_PROMPTING_SYSTEMS_RENDER_COMMAND",
        "CHUMMER6_BROWSERACT_PROMPTING_SYSTEMS_RENDER_URL_TEMPLATE",
        "CHUMMER6_PROMPTING_SYSTEMS_RENDER_COMMAND",
        "CHUMMER6_PROMPTING_SYSTEMS_RENDER_URL_TEMPLATE",
    ],
    "onemin": ["CHUMMER6_1MIN_RENDER_COMMAND", "CHUMMER6_1MIN_RENDER_URL_TEMPLATE"],
}


def env_value(name: str) -> str:
    direct = str(os.environ.get(name) or "").strip()
    if direct:
        return direct
    if ENV_FILE.exists():
        for raw in ENV_FILE.read_text(errors="ignore").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key.strip() == name:
                return value.strip()
    return ""


def key_names_present(names: list[str]) -> list[str]:
    return [name for name in names if env_value(name)]


def provider_order() -> list[str]:
    raw = env_value("CHUMMER6_IMAGE_PROVIDER_ORDER")
    if not raw:
        return ["magixai", "markupgo", "prompting_systems", "browseract_prompting_systems", "onemin", "local_raster"]
    values = [part.strip().lower() for part in raw.split(",") if part.strip()]
    return values or ["magixai", "markupgo", "prompting_systems", "browseract_prompting_systems", "onemin", "local_raster"]


def provider_state(name: str) -> dict[str, object]:
    if name == "local_raster":
        return {
            "provider": name,
            "status": "fallback_only",
            "available": True,
            "raw_keys": [],
            "adapters": [],
            "detail": "Always available as the final local fallback.",
        }
    raw_keys = key_names_present(RAW_KEY_NAMES.get(name, []))
    adapters = key_names_present(ADAPTER_ENV_NAMES.get(name, []))
    if name == "browseract":
        available = bool(raw_keys)
        status = "ready" if available else "missing_credentials"
        detail = "BrowserAct live automation is available." if available else "No BrowserAct key found in EA env."
        return {"provider": name, "status": status, "available": available, "raw_keys": raw_keys, "adapters": adapters, "detail": detail}
    if name == "browseract_prompting_systems":
        browseract_ready = bool(key_names_present(RAW_KEY_NAMES.get("browseract", [])))
        available = browseract_ready and bool(adapters)
        if available:
            status = "ready"
            detail = "BrowserAct and a Prompting Systems adapter are both configured."
        elif browseract_ready:
            status = "browseract_ready_missing_render_adapter"
            detail = "BrowserAct is configured, but no Prompting Systems render adapter is configured yet."
        else:
            status = "missing_browseract"
            detail = "No BrowserAct key found in EA env."
        return {"provider": name, "status": status, "available": available, "raw_keys": key_names_present(RAW_KEY_NAMES.get('browseract', [])), "adapters": adapters, "detail": detail}
    available = bool(adapters)
    if available:
        status = "ready"
        detail = "A render adapter is configured."
    elif raw_keys:
        status = "credential_only"
        detail = "Credentials appear present, but no render command/URL template is configured yet."
    else:
        status = "not_configured"
        detail = "No credentials or render adapter found."
    return {"provider": name, "status": status, "available": available, "raw_keys": raw_keys, "adapters": adapters, "detail": detail}


def main() -> int:
    providers = provider_order()
    states = [provider_state(name) for name in providers]
    result = {
        "provider_order": providers,
        "providers": states,
        "recommended_provider": next((row["provider"] for row in states if row["available"]), "local_raster"),
    }
    STATE_OUT.parent.mkdir(parents=True, exist_ok=True)
    STATE_OUT.write_text(json.dumps(result, indent=2, ensure_ascii=True) + "\\n", encoding="utf-8")
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
"""


MARKUPGO_RENDER_SCRIPT = """#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import tempfile
import urllib.error
import urllib.request
from pathlib import Path


EA_ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = EA_ROOT / ".env"
BASE_URL = "https://api.markupgo.com/api/v1/image/buffer"
OVERRIDE_PATH = Path("/docker/fleet/state/chummer6/ea_overrides.json")


def env_value(name: str) -> str:
    direct = str(os.environ.get(name) or "").strip()
    if direct:
        return direct
    if ENV_FILE.exists():
        for raw in ENV_FILE.read_text(errors="ignore").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key.strip() == name:
                return value.strip()
    return ""


def theme_for(seed: str) -> tuple[str, str, str]:
    palettes = [
        ("#0b1020", "#18f0ff", "#ff2f92"),
        ("#0f0d1a", "#7bff5b", "#2ee6ff"),
        ("#120914", "#ffcc33", "#ff4f8b"),
        ("#08141a", "#76ffd1", "#4fb3ff"),
    ]
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    return palettes[int(digest[:2], 16) % len(palettes)]


def slug_title(prompt: str) -> str:
    cleaned = " ".join(prompt.replace("-", " ").replace(",", " ").split())
    if not cleaned:
        return "Chummer6"
    words = cleaned.split()
    title = " ".join(words[:4]).strip()
    return title.title()


def teaser(prompt: str) -> str:
    cleaned = " ".join(prompt.split())
    if len(cleaned) <= 140:
        return cleaned
    return cleaned[:137].rstrip() + "..."


def load_media_overrides() -> dict[str, object]:
    if not OVERRIDE_PATH.exists():
        return {}
    try:
        loaded = json.loads(OVERRIDE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def scene_for(output_name: str, prompt: str) -> dict[str, str]:
    name = output_name.lower()
    default = {
        "badge": "Chummer6",
        "title": slug_title(prompt),
        "subtitle": teaser(prompt),
        "kicker": "Guide art",
        "note": "Fresh chrome for the guide wall.",
        "meta": "Chummer6 guide art",
    }
    loaded = load_media_overrides()
    media = loaded.get("media") if isinstance(loaded, dict) else None
    if isinstance(media, dict):
        if name == "chummer6-hero.png":
            hero = media.get("hero")
            if isinstance(hero, dict):
                merged = dict(default)
                for key in ("badge", "title", "subtitle", "kicker", "note", "meta"):
                    value = str(hero.get(key, "")).strip()
                    if value:
                        merged[key] = value
                return merged
        horizons = media.get("horizons")
        if isinstance(horizons, dict):
            slug = name.removesuffix(".png")
            row = horizons.get(slug)
            if isinstance(row, dict):
                merged = dict(default)
                for key in ("badge", "title", "subtitle", "kicker", "note", "meta"):
                    value = str(row.get(key, "")).strip()
                    if value:
                        merged[key] = value
                return merged
    return default


def build_html(prompt: str, output_name: str, *, width: int, height: int) -> str:
    bg, accent_a, accent_b = theme_for(prompt)
    scene = scene_for(output_name, prompt)
    title = html.escape(scene["title"])
    subtitle = html.escape(scene["subtitle"])
    badge = html.escape(scene["badge"])
    kicker = html.escape(scene["kicker"])
    note = html.escape(scene.get("note", "Chrome, caution, and just enough bad decisions to feel like home."))
    ratio = f"{width}x{height}"
    return f\"\"\"<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <style>
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      width: {width}px;
      height: {height}px;
      overflow: hidden;
      font-family: 'Segoe UI', system-ui, sans-serif;
      background:
        radial-gradient(circle at 20% 20%, {accent_a}33 0, transparent 40%),
        radial-gradient(circle at 80% 25%, {accent_b}2a 0, transparent 35%),
        linear-gradient(135deg, {bg} 0%, #05070d 100%);
      color: #f4f7fb;
    }}
    .frame {{
      position: relative;
      width: 100%;
      height: 100%;
      padding: 52px 58px;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
    }}
    .noise {{
      position: absolute;
      inset: 0;
      background:
        radial-gradient(circle at 14% 70%, {accent_a}22 0, transparent 22%),
        radial-gradient(circle at 76% 18%, {accent_b}22 0, transparent 18%),
        radial-gradient(circle at 84% 82%, #ffffff10 0, transparent 12%);
      mix-blend-mode: screen;
      opacity: 0.9;
      pointer-events: none;
    }}
    .grid {{
      position: absolute;
      inset: 0;
      background-image:
        linear-gradient(rgba(255,255,255,0.04) 1px, transparent 1px),
        linear-gradient(90deg, rgba(255,255,255,0.04) 1px, transparent 1px);
      background-size: 52px 52px;
      mask-image: linear-gradient(to bottom, rgba(0,0,0,0.7), transparent);
      pointer-events: none;
    }}
    .chip {{
      display: inline-flex;
      align-items: center;
      gap: 10px;
      padding: 10px 16px;
      border-radius: 999px;
      border: 1px solid rgba(255,255,255,0.14);
      background: rgba(5,8,15,0.52);
      color: {accent_a};
      font-size: 18px;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      width: fit-content;
      backdrop-filter: blur(4px);
    }}
    .headline {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) 280px;
      gap: 24px;
      align-items: start;
    }}
    .title {{
      font-size: {max(52, min(86, width // 13))}px;
      line-height: 0.94;
      font-weight: 900;
      letter-spacing: -0.03em;
      max-width: 78%;
      text-wrap: balance;
      text-shadow: 0 0 30px rgba(0,0,0,0.35);
    }}
    .subtitle {{
      max-width: 70%;
      font-size: {max(22, min(34, width // 40))}px;
      line-height: 1.3;
      color: rgba(244,247,251,0.88);
      text-wrap: pretty;
    }}
    .footer {{
      display: flex;
      align-items: flex-end;
      justify-content: space-between;
    }}
    .sidecard {{
      justify-self: end;
      width: 280px;
      min-height: 240px;
      padding: 22px 24px;
      border-radius: 30px;
      border: 1px solid rgba(255,255,255,0.12);
      background:
        linear-gradient(180deg, rgba(255,255,255,0.08), rgba(255,255,255,0.02)),
        rgba(7, 10, 18, 0.52);
      box-shadow: inset 0 1px 0 rgba(255,255,255,0.08), 0 14px 50px rgba(0,0,0,0.28);
      backdrop-filter: blur(8px);
    }}
    .sidecard .small {{
      font-size: 14px;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      color: rgba(244,247,251,0.58);
      margin-bottom: 18px;
    }}
    .sidecard .big {{
      font-size: 30px;
      line-height: 1.05;
      font-weight: 900;
      color: {accent_b};
      margin-bottom: 14px;
      text-shadow: 0 0 18px {accent_b}33;
    }}
    .sidecard .line {{
      height: 4px;
      width: 100%;
      border-radius: 999px;
      background: linear-gradient(90deg, {accent_a}, {accent_b});
      margin: 18px 0 12px;
      opacity: 0.9;
    }}
    .sidecard .note {{
      font-size: 16px;
      line-height: 1.4;
      color: rgba(244,247,251,0.82);
    }}
    .brand {{
      font-size: 34px;
      font-weight: 800;
      color: {accent_b};
      letter-spacing: 0.02em;
      text-shadow: 0 0 18px {accent_b}55;
    }}
    .meta {{
      font-size: 18px;
      color: rgba(244,247,251,0.62);
      text-transform: uppercase;
      letter-spacing: 0.12em;
    }}
    .beam {{
      position: absolute;
      right: -80px;
      bottom: 56px;
      width: {max(260, width // 3)}px;
      height: {max(260, height // 2)}px;
      border-radius: 40px;
      background:
        linear-gradient(160deg, {accent_a} 0%, transparent 70%),
        linear-gradient(20deg, {accent_b} 0%, transparent 78%);
      filter: blur(28px);
      opacity: 0.52;
      transform: rotate(-10deg);
    }}
    .beacon {{
      position: absolute;
      left: 54px;
      bottom: 84px;
      width: 180px;
      height: 180px;
      border-radius: 34px;
      border: 1px solid rgba(255,255,255,0.14);
      background:
        linear-gradient(135deg, rgba(255,255,255,0.08), rgba(255,255,255,0.01)),
        rgba(2,6,14,0.52);
      box-shadow: inset 0 0 18px rgba(255,255,255,0.05), 0 14px 40px rgba(0,0,0,0.35);
      overflow: hidden;
      transform: rotate(-6deg);
    }}
    .beacon::before,
    .beacon::after {{
      content: "";
      position: absolute;
      inset: 20px;
      border-radius: 24px;
      border: 1px solid {accent_a}55;
    }}
    .beacon::after {{
      inset: 42px;
      border-color: {accent_b}55;
    }}
  </style>
</head>
<body>
  <div class="frame">
    <div class="noise"></div>
    <div class="grid"></div>
    <div class="beam"></div>
    <div class="beacon"></div>
    <div class="chip">{badge}</div>
    <div class="headline">
      <div>
        <div class="title">{title}</div>
        <div class="subtitle">{subtitle}</div>
      </div>
      <div class="sidecard">
        <div class="small">Street note</div>
        <div class="big">{kicker}</div>
        <div class="line"></div>
        <div class="note">{note}</div>
      </div>
    </div>
    <div class="footer">
      <div class="brand">Chummer6</div>
      <div class="meta">{ratio}</div>
    </div>
  </div>
</body>
</html>
\"\"\"


def render(prompt: str, output: Path, *, width: int, height: int) -> None:
    api_key = env_value("MARKUPGO_API_KEY")
    if not api_key:
        raise SystemExit("MARKUPGO_API_KEY is not configured")
    body = {
        "source": {
            "type": "html",
            "data": build_html(prompt, output.name, width=width, height=height),
        },
        "options": {
            "properties": {
                "format": "png",
                "width": width,
                "height": height,
                "clip": True,
            },
            "optimizeForSpeed": True,
        },
    }
    request = urllib.request.Request(
        BASE_URL,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "User-Agent": "EA-Chummer6-MarkupGo/1.0",
        },
        data=json.dumps(body).encode("utf-8"),
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            data = response.read()
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace").strip()
        raise SystemExit(f"MarkupGo HTTP {exc.code}: {body[:300]}")
    except urllib.error.URLError as exc:
        raise SystemExit(f"MarkupGo transport error: {exc.reason}")
    if not data:
        raise SystemExit("MarkupGo returned empty output")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(data)


def main() -> int:
    parser = argparse.ArgumentParser(description="Render Chummer6 art through MarkupGo.")
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    args = parser.parse_args()
    render(str(args.prompt), Path(args.output).expanduser(), width=int(args.width), height=int(args.height))
    print(json.dumps({"output": str(Path(args.output).expanduser()), "status": "rendered"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
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


def update_local_policy() -> None:
    policy: dict[str, object] = {}
    if LOCAL_POLICY_PATH.exists():
        try:
            loaded = json.loads(LOCAL_POLICY_PATH.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                policy = loaded
        except Exception:
            policy = {}
    policy.setdefault("forbidden_origin_mentions", ["ArchonMegalon/chummer5a", "chummer5a"])
    policy.setdefault("release_source_label", "active Chummer6 code repos")
    policy["image_generation"] = {
        "enabled": True,
        "provider": "ea-auto",
        "command": [
            "python3",
            "/docker/EA/scripts/chummer6_guide_media_worker.py",
            "render",
            "--prompt",
            "{prompt}",
            "--output",
            "{output}",
            "--width",
            "{width}",
            "--height",
            "{height}",
        ],
        "timeout_seconds": 180,
    }
    LOCAL_POLICY_PATH.write_text(json.dumps(policy, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def ensure_env_examples() -> None:
    section = """

# Optional Chummer6 guide media provider hooks (local .env only; keep real keys and adapters out of git)
CHUMMER6_IMAGE_PROVIDER_ORDER=magixai,markupgo,prompting_systems,browseract_prompting_systems,onemin,local_raster

# Optional AI Magicx render adapter
AI_MAGICX_API_KEY=
CHUMMER6_MAGIXAI_RENDER_COMMAND=
CHUMMER6_MAGIXAI_RENDER_URL_TEMPLATE=

# Optional MarkupGo render adapter
MARKUPGO_API_KEY=
CHUMMER6_MARKUPGO_RENDER_COMMAND=
CHUMMER6_MARKUPGO_RENDER_URL_TEMPLATE=

# Optional Prompting Systems render adapter
PROMPTING_SYSTEMS_API_KEY=
CHUMMER6_PROMPTING_SYSTEMS_RENDER_COMMAND=
CHUMMER6_PROMPTING_SYSTEMS_RENDER_URL_TEMPLATE=

# Optional BrowserAct-assisted Prompting Systems adapter
CHUMMER6_BROWSERACT_PROMPTING_SYSTEMS_RENDER_COMMAND=
CHUMMER6_BROWSERACT_PROMPTING_SYSTEMS_RENDER_URL_TEMPLATE=

# Optional 1min.AI image adapter
CHUMMER6_1MIN_RENDER_COMMAND=
CHUMMER6_1MIN_RENDER_URL_TEMPLATE=
""".lstrip("\n")
    marker = "# Optional Chummer6 guide media provider hooks"
    for path in (ENV_EXAMPLE_PATH, ENV_LOCAL_EXAMPLE_PATH):
        if not path.exists():
            continue
        current = path.read_text(encoding="utf-8")
        if marker in current:
            continue
        suffix = "" if current.endswith("\n") else "\n"
        write_if_changed(path, current + suffix + section, executable=False)


def main() -> int:
    write_if_changed(WORKER_PATH, WORKER_SCRIPT, executable=True)
    write_if_changed(MEDIA_WORKER_PATH, MEDIA_WORKER_SCRIPT, executable=True)
    write_if_changed(BOOTSTRAP_SKILL_PATH, BOOTSTRAP_SKILL_SCRIPT, executable=True)
    write_if_changed(PROVIDER_READINESS_PATH, PROVIDER_READINESS_SCRIPT, executable=True)
    write_if_changed(MARKUPGO_RENDER_PATH, MARKUPGO_RENDER_SCRIPT, executable=True)
    write_if_changed(SMOKE_HELP_PATH, SMOKE_HELP_SCRIPT, executable=True)
    ensure_env_examples()
    update_local_policy()
    print({
        "worker": str(WORKER_PATH),
        "media_worker": str(MEDIA_WORKER_PATH),
        "bootstrap_skill": str(BOOTSTRAP_SKILL_PATH),
        "provider_readiness": str(PROVIDER_READINESS_PATH),
        "markupgo_render": str(MARKUPGO_RENDER_PATH),
        "smoke_help": str(SMOKE_HELP_PATH),
        "local_policy": str(LOCAL_POLICY_PATH),
        "status": "updated",
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
