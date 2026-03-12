#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
from pathlib import Path


EA_ROOT = Path("/docker/EA")
SCRIPTS_DIR = EA_ROOT / "scripts"
WORKER_PATH = SCRIPTS_DIR / "chummer6_guide_worker.py"
MEDIA_WORKER_PATH = SCRIPTS_DIR / "chummer6_guide_media_worker.py"
BOOTSTRAP_SKILL_PATH = SCRIPTS_DIR / "bootstrap_chummer6_guide_skill.py"
PROVIDER_READINESS_PATH = SCRIPTS_DIR / "chummer6_provider_readiness.py"
PROMPTING_SYSTEMS_HELPER_PATH = SCRIPTS_DIR / "chummer6_browseract_prompting_systems.py"
MARKUPGO_RENDER_PATH = SCRIPTS_DIR / "chummer6_markupgo_render.py"
SMOKE_HELP_PATH = SCRIPTS_DIR / "smoke_help.sh"
ENV_PATH = EA_ROOT / ".env"
ENV_EXAMPLE_PATH = EA_ROOT / ".env.example"
ENV_LOCAL_EXAMPLE_PATH = EA_ROOT / ".env.local.example"
LOCAL_POLICY_PATH = Path("/docker/fleet/.chummer6_local_policy.json")


WORKER_SCRIPT = """#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request
from pathlib import Path


EA_ROOT = Path(__file__).resolve().parents[1]
FLEET_GUIDE_SCRIPT = Path("/docker/fleet/scripts/finish_chummer6_guide.py")
OVERRIDE_OUT = Path("/docker/fleet/state/chummer6/ea_overrides.json")
DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_CODEX_MODEL = "gpt-5.3-codex"
FALLBACK_MODELS = (
    "gpt-4o-mini",
    "gpt-4.1-mini",
    "gpt-4.1-nano",
)
WORKING_VARIANT: dict[str, object] | None = None
TEXT_PROVIDER_USED: str = ""


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


def read_markdown_excerpt(relative_path: str, *, limit: int = 360) -> str:
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


def codex_model_candidate(requested: str) -> str:
    explicit = str(requested or "").strip()
    if explicit and "codex" in explicit.lower():
        return explicit
    env_override = str(os.environ.get("CHUMMER6_CODEX_TEXT_MODEL") or "").strip()
    if env_override:
        return env_override
    return DEFAULT_CODEX_MODEL


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


def onemin_json(prompt: str, *, model: str = DEFAULT_MODEL) -> dict[str, object]:
    last_error = "no_attempts"
    for api_key in resolve_onemin_keys():
        for url, headers, payload in request_variants(prompt, model=model, api_key=api_key):
            body_bytes = json.dumps(payload).encode("utf-8")
            request = urllib.request.Request(url, data=body_bytes, headers=headers, method="POST")
            try:
                with urllib.request.urlopen(request, timeout=60) as response:
                    body = json.loads(response.read().decode("utf-8", errors="replace") or "{}")
                return extract_response_json(body)
            except urllib.error.HTTPError as exc:
                response_text = exc.read().decode("utf-8", errors="replace")
                if exc.code == 401:
                    last_error = f"{url}:http_{exc.code}:{response_text[:220]}"
                    break
                if exc.code == 400 and "OPEN_AI_UNEXPECTED_ERROR" in response_text:
                    for _attempt in range(8):
                        time.sleep(6)
                        retry = urllib.request.Request(url, data=body_bytes, headers=headers, method="POST")
                        try:
                            with urllib.request.urlopen(retry, timeout=60) as response:
                                body = json.loads(response.read().decode("utf-8", errors="replace") or "{}")
                            return extract_response_json(body)
                        except urllib.error.HTTPError as retry_exc:
                            retry_text = retry_exc.read().decode("utf-8", errors="replace")
                            if retry_exc.code == 401:
                                last_error = f"{url}:http_{retry_exc.code}:{retry_text[:220]}"
                                break
                            if retry_exc.code == 400 and "OPEN_AI_UNEXPECTED_ERROR" in retry_text:
                                last_error = f"{url}:openai_busy"
                                continue
                            last_error = f"{url}:http_{retry_exc.code}:{retry_text[:220]}"
                            break
                        except Exception as retry_exc:
                            last_error = f"{url}:{type(retry_exc).__name__}:{str(retry_exc)[:220]}"
                            break
                    continue
                last_error = f"{url}:http_{exc.code}:{response_text[:220]}"
            except Exception as exc:
                last_error = f"{url}:{type(exc).__name__}:{str(exc)[:220]}"
    raise RuntimeError(f"onemin_text_failed:{last_error}")


def codex_json(prompt: str, *, model: str = DEFAULT_MODEL) -> dict[str, object]:
    codex = shutil.which("codex")
    if not codex:
        raise RuntimeError("codex_cli_unavailable")
    codex_model = codex_model_candidate(model)
    codex_sandbox = str(os.environ.get("CHUMMER6_CODEX_SANDBOX") or "danger-full-access").strip()
    with tempfile.NamedTemporaryFile(prefix="chummer6_codex_", suffix=".txt", delete=False) as handle:
        output_path = Path(handle.name)
    try:
        command = [
            codex,
            "exec",
            "-C",
            str(EA_ROOT),
            "--skip-git-repo-check",
            "--ephemeral",
        ]
        if codex_sandbox:
            command.extend(["-s", codex_sandbox])
        command.extend(
            [
                "-m",
                codex_model,
                "-c",
                'model_reasoning_effort="low"',
                "-o",
                str(output_path),
                prompt,
            ]
        )
        completed = subprocess.run(
            command,
            check=True,
            text=True,
            capture_output=True,
            timeout=90,
        )
        text = output_path.read_text(encoding="utf-8", errors="replace").strip()
        if not text:
            raise RuntimeError("codex_empty_output")
        return extract_json(text)
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        stdout = (exc.stdout or "").strip()
        detail = stderr or stdout or str(exc)
        raise RuntimeError(f"codex_exec_failed:{detail[:400]}") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("codex_exec_timeout") from exc
    finally:
        try:
            output_path.unlink(missing_ok=True)
        except Exception:
            pass


def chat_json(prompt: str, *, model: str = DEFAULT_MODEL) -> dict[str, object]:
    global TEXT_PROVIDER_USED
    order_raw = str(os.environ.get("CHUMMER6_TEXT_PROVIDER_ORDER") or "onemin,codex").strip()
    order = [entry.strip().lower() for entry in order_raw.split(",") if entry.strip()]
    attempted: list[str] = []
    for provider in order:
        try:
            if provider in {"onemin", "1min", "1min.ai", "oneminai"}:
                payload = onemin_json(prompt, model=model)
                TEXT_PROVIDER_USED = "onemin"
                return payload
            if provider == "codex":
                payload = codex_json(prompt, model=model)
                TEXT_PROVIDER_USED = "codex"
                return payload
            attempted.append(f"{provider}:unknown_provider")
        except Exception as exc:
            attempted.append(f"{provider}:{exc}")
    raise RuntimeError("no text provider succeeded: " + " || ".join(attempted))


def build_part_prompt(
    name: str,
    item: dict[str, object],
    ooda: dict[str, object] | None = None,
    *,
    section_ooda: dict[str, object] | None = None,
) -> str:
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

Guide OODA:
{json.dumps(ooda or {}, ensure_ascii=True)}

Section OODA:
{json.dumps(section_ooda or {}, ensure_ascii=True)}

Return valid JSON only.
\"\"\"


def build_horizon_prompt(
    name: str,
    item: dict[str, object],
    ooda: dict[str, object] | None = None,
    *,
    section_ooda: dict[str, object] | None = None,
) -> str:
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

Guide OODA:
{json.dumps(ooda or {}, ensure_ascii=True)}

Section OODA:
{json.dumps(section_ooda or {}, ensure_ascii=True)}

Return valid JSON only.
\"\"\"


def build_section_ooda_prompt(
    section_type: str,
    name: str,
    item: dict[str, object],
    *,
    global_ooda: dict[str, object] | None = None,
) -> str:
    title = str(item.get("title", name.replace("-", " ").title())).strip()
    prompt_bits = {
        "hero": {
            "context": "the landing hero for the human-facing Chummer6 guide",
            "source": "\\n\\n".join(
                [
                    "README:\\n" + read_markdown_excerpt("README.md", limit=320),
                    "Current phase:\\n" + read_markdown_excerpt("NOW/current-phase.md", limit=220),
                ]
            ),
        },
        "part": {
            "context": f"the PARTS/{name}.md page for the human-facing Chummer6 guide",
            "source": "\\n\\n".join(
                [
                    f"Tagline: {item.get('tagline', '')}",
                    f"Intro: {item.get('intro', '')}",
                    f"Why: {item.get('why', '')}",
                    "Owns:\\n" + "\\n".join(f"- {line}" for line in item.get("owns", [])),
                    "Does not own:\\n" + "\\n".join(f"- {line}" for line in item.get("not_owns", [])),
                    f"Now: {item.get('now', '')}",
                ]
            ),
        },
        "horizon": {
            "context": f"the HORIZONS/{name}.md page for the human-facing Chummer6 guide",
            "source": "\\n\\n".join(
                [
                    f"Hook: {item.get('hook', '')}",
                    f"Brutal truth: {item.get('brutal_truth', '')}",
                    f"Use case: {item.get('use_case', '')}",
                    f"Problem: {item.get('problem', '')}",
                    "Foundations:\\n" + "\\n".join(f"- {line}" for line in item.get("foundations", [])),
                    "Touched repos later:\\n" + "\\n".join(f"- {line}" for line in item.get("repos", [])),
                ]
            ),
        },
        "page": {
            "context": f"the {name} guide page for the human-facing Chummer6 repo",
            "source": str(item.get("source", "")).strip(),
        },
    }[section_type]
    return f\"\"\"You are doing section-level OODA for {prompt_bits['context']}.

Task: return a JSON object only with keys observe, orient, decide, act.

Required shape:
- observe: reader_question, likely_interest, concrete_signals, risks
- orient: emotional_goal, sales_angle, focal_subject, scene_logic, visual_devices, tone_rule, banned_literalizations
- decide: copy_priority, image_priority, overlay_priority, subject_rule, hype_limit
- act: one_liner, paragraph_seed, visual_prompt_seed

Rules:
- this OODA is for this section only, not the whole repo
- think about what a curious human reader would actually notice or care about here
- if the source suggests strong selling points like multi-era support, Lua/scripted rules, local-first play, explain receipts, or dangerous simulation energy, surface them
- do not literalize repo governance labels into the scene
- avoid generic poster language
- for image thinking, prefer one memorable focal subject or action over abstract icon soup
- if the section naturally implies a person, choose a believable cyberpunk protagonist instead of a faceless symbol
- if the concept itself implies a visual metaphor like x-ray, ghost, mirror, passport, web, blackbox, dossier, or crash-test simulation, make that metaphor visually legible in-scene
- if the title reads like a codename or person, let the scene revolve around a specific cyberpunk character instead of a generic skyline
- overlay hints are design guidance for the renderer, not excuses to print UI labels or prompt text on the image
- Shadowrun jargon is welcome
- mild dev roasting is allowed
- no mention of Fleet
- no mention of chummer5a
- no markdown fences

Section type: {section_type}
Section id: {name}
Section title: {title}

Section source:
{prompt_bits['source']}

Global OODA:
{json.dumps(global_ooda or {}, ensure_ascii=True)}

Return valid JSON only.
\"\"\"


def build_section_oodas_bundle_prompt(
    section_type: str,
    section_items: dict[str, dict[str, object]],
    *,
    global_ooda: dict[str, object] | None = None,
) -> str:
    payload: dict[str, object] = {}
    for name, item in section_items.items():
        title = str(item.get("title", name.replace("-", " ").title())).strip()
        if section_type == "page":
            payload[name] = {
                "title": title,
                "source": str(item.get("source", "")).strip(),
            }
        elif section_type == "part":
            payload[name] = {
                "title": title,
                "tagline": item.get("tagline", ""),
                "intro": item.get("intro", ""),
                "why": item.get("why", ""),
                "now": item.get("now", ""),
                "owns": item.get("owns", []),
                "not_owns": item.get("not_owns", []),
            }
        else:
            payload[name] = {
                "title": title,
                "hook": item.get("hook", ""),
                "brutal_truth": item.get("brutal_truth", ""),
                "use_case": item.get("use_case", ""),
                "problem": item.get("problem", ""),
                "foundations": item.get("foundations", []),
                "repos": item.get("repos", []),
                "not_now": item.get("not_now", ""),
            }
    return f\"\"\"You are doing section-level OODA for multiple human-facing Chummer6 guide sections.

Task: return one JSON object keyed by section id.
Each section id must map to an object with keys observe, orient, decide, act.

Required shape per section:
- observe: reader_question, likely_interest, concrete_signals, risks
- orient: emotional_goal, sales_angle, focal_subject, scene_logic, visual_devices, tone_rule, banned_literalizations
- decide: copy_priority, image_priority, overlay_priority, subject_rule, hype_limit
- act: one_liner, paragraph_seed, visual_prompt_seed

Rules:
- think like a sharp human guide writer, not a compliance bot
- this OODA is for each section only, not the whole repo
- focus on what a curious human reader would actually care about here
- if the source suggests strong selling points like multi-era support, Lua/scripted rules, local-first play, explain receipts, grounded dossier flows, or dangerous simulation energy, surface them
- do not literalize repo governance labels into the scene
- avoid generic poster language and repeated sentence frames
- prefer one memorable focal subject or action over abstract icon soup
- if the section naturally implies a person, choose a believable cyberpunk protagonist instead of a faceless symbol
- if the concept implies a visual metaphor like x-ray, ghost, mirror, passport, dossier, web, blackbox, forge, or crash-test simulation, make that metaphor visibly legible in-scene
- if the title reads like a codename or person, let the scene revolve around a specific cyberpunk character instead of a generic skyline
- overlay hints are design guidance for the renderer, not excuses to print labels, prompts, OODA, or resolution junk on the image
- Shadowrun jargon is welcome
- mild dev roasting is allowed
- no mention of Fleet
- no mention of chummer5a
- no markdown fences
- keep the whole JSON compact

Section type: {section_type}

Global OODA:
{json.dumps(global_ooda or {}, ensure_ascii=True)}

Sections:
{json.dumps(payload, ensure_ascii=True)}

Return valid JSON only.
\"\"\"


def normalize_section_ooda(
    result: dict[str, object],
    *,
    section_type: str,
    name: str,
    item: dict[str, object],
    global_ooda: dict[str, object] | None = None,
) -> dict[str, object]:
    normalized: dict[str, object] = {}
    for stage, fields in {
        "observe": ["reader_question", "likely_interest", "concrete_signals", "risks"],
        "orient": ["emotional_goal", "sales_angle", "focal_subject", "scene_logic", "visual_devices", "tone_rule", "banned_literalizations"],
        "decide": ["copy_priority", "image_priority", "overlay_priority", "subject_rule", "hype_limit"],
        "act": ["one_liner", "paragraph_seed", "visual_prompt_seed"],
    }.items():
        raw_stage = result.get(stage) if isinstance(result.get(stage), dict) else {}
        merged: dict[str, object] = {}
        for field in fields:
            raw = raw_stage.get(field) if isinstance(raw_stage, dict) else None
            if isinstance(raw, list):
                cleaned = [str(entry).strip() for entry in raw if str(entry).strip()]
                if not cleaned:
                    raise ValueError(f"section OODA field is missing: {section_type}/{name}.{stage}.{field}")
                merged[field] = cleaned
            else:
                value = str(raw or "").strip()
                if not value:
                    raise ValueError(f"section OODA field is missing: {section_type}/{name}.{stage}.{field}")
                merged[field] = value
        normalized[stage] = merged
    return normalized


def normalize_section_oodas_bundle(
    result: dict[str, object],
    *,
    section_type: str,
    section_items: dict[str, dict[str, object]],
    global_ooda: dict[str, object] | None = None,
) -> dict[str, dict[str, object]]:
    normalized: dict[str, dict[str, object]] = {}
    for name, item in section_items.items():
        row = result.get(name)
        if not isinstance(row, dict):
            raise ValueError(f"missing section OODA bundle row: {section_type}/{name}")
        normalized[name] = normalize_section_ooda(
            row,
            section_type=section_type,
            name=name,
            item=item,
            global_ooda=global_ooda,
        )
    return normalized


def build_page_prompt(page_id: str, item: dict[str, object], *, global_ooda: dict[str, object] | None = None, section_ooda: dict[str, object] | None = None) -> str:
    return f\"\"\"You are writing downstream-only copy for the human-facing Chummer6 guide page `{page_id}`.

Task: return a JSON object only with keys intro, body, kicker.

Rules:
- plain language first
- human-facing, slightly playful, Shadowrun-flavored
- no mention of Fleet
- no mention of chummer5a
- no markdown fences
- explain why this page matters to a normal reader
- avoid internal jargon unless it is immediately translated
- make the page sound distinct instead of reusing one canned sentence pattern

Page id: {page_id}
Current source:
{item.get("source", "")}

Global OODA:
{json.dumps(global_ooda or {}, ensure_ascii=True)}

Section OODA:
{json.dumps(section_ooda or {}, ensure_ascii=True)}

Return valid JSON only.
\"\"\"


def build_pages_bundle_prompt(*, global_ooda: dict[str, object], section_oodas: dict[str, object]) -> str:
    pages_payload: dict[str, object] = {}
    for page_id, item in PAGE_PROMPTS.items():
        pages_payload[page_id] = {
            "source": str(item.get("source", "")).strip(),
            "section_ooda": section_oodas.get(page_id, {}),
        }
    return f\"\"\"You are writing downstream-only copy for multiple human-facing Chummer6 guide pages.

Task: return one JSON object keyed by page id. Each page id must map to an object with keys intro, body, kicker.

Rules:
- plain language first
- human-facing, slightly playful, Shadowrun-flavored
- no mention of Fleet
- no mention of chummer5a
- no markdown fences
- explain why each page matters to a normal reader
- avoid internal jargon unless it is immediately translated
- keep each page compact and useful
- make each page feel distinct instead of reusing one sentence frame

Global OODA:
{json.dumps(global_ooda or {}, ensure_ascii=True)}

Pages:
{json.dumps(pages_payload, ensure_ascii=True)}

Return valid JSON only.
\"\"\"


def build_parts_bundle_prompt(*, global_ooda: dict[str, object], section_oodas: dict[str, object]) -> str:
    parts_payload: dict[str, object] = {}
    for name, item in PARTS.items():
        parts_payload[name] = {
            "title": item.get("title", ""),
            "tagline": item.get("tagline", ""),
            "intro": item.get("intro", ""),
            "why": item.get("why", ""),
            "now": item.get("now", ""),
            "owns": item.get("owns", []),
            "not_owns": item.get("not_owns", []),
            "section_ooda": section_oodas.get(name, {}),
        }
    return f\"\"\"You are writing downstream-only copy and media metadata for multiple Chummer6 part pages.

Task: return one JSON object keyed by part id.
Each part id must map to:
- copy: object with intro, why, now
- media: object with badge, title, subtitle, kicker, note, meta, visual_prompt, overlay_hint, visual_motifs, overlay_callouts, scene_contract

Rules:
- clear, slightly playful, Shadowrun-flavored
- plain language first
- SR jargon is welcome
- mild dev roasting is allowed
- no mention of Fleet
- no mention of chummer5a
- no markdown fences
- keep copy grounded and useful
- make each part sound like its own place, not another templated glossary card
- make the media scene-first, not icon soup
- no literal on-image text or prompt leakage

Global OODA:
{json.dumps(global_ooda or {}, ensure_ascii=True)}

Parts:
{json.dumps(parts_payload, ensure_ascii=True)}

Return valid JSON only.
\"\"\"


def build_horizons_bundle_prompt(*, global_ooda: dict[str, object], section_oodas: dict[str, object]) -> str:
    horizons_payload: dict[str, object] = {}
    for name, item in HORIZONS.items():
        horizons_payload[name] = {
            "title": item.get("title", ""),
            "hook": item.get("hook", ""),
            "brutal_truth": item.get("brutal_truth", ""),
            "use_case": item.get("use_case", ""),
            "problem": item.get("problem", ""),
            "foundations": item.get("foundations", []),
            "repos": item.get("repos", []),
            "not_now": item.get("not_now", ""),
            "section_ooda": section_oodas.get(name, {}),
        }
    return f\"\"\"You are writing downstream-only copy and media metadata for multiple Chummer6 horizon pages.

Task: return one JSON object keyed by horizon id.
Each horizon id must map to:
- copy: object with hook, why_wiz, brutal_truth, use_case, idea, problem, why_waits
- media: object with badge, title, subtitle, kicker, note, meta, visual_prompt, overlay_hint, visual_motifs, overlay_callouts, scene_contract

Rules:
- sell the idea harder without pretending it ships tomorrow
- clear, punchy, Shadowrun-flavored
- mild dev roasting is allowed
- no mention of Fleet
- no mention of chummer5a
- no markdown fences
- scenes should feel specific, cool, and dangerous
- if the codename implies a person or metaphor, make that legible
- do not reuse the same sentence stem across multiple horizons
- the copy should feel distinct per horizon, not like one template with swapped nouns

Global OODA:
{json.dumps(global_ooda or {}, ensure_ascii=True)}

Horizons:
{json.dumps(horizons_payload, ensure_ascii=True)}

Return valid JSON only.
\"\"\"


def normalize_pages_bundle(result: dict[str, object]) -> dict[str, dict[str, str]]:
    normalized: dict[str, dict[str, str]] = {}
    for page_id in PAGE_PROMPTS:
        row = result.get(page_id)
        if not isinstance(row, dict):
            raise ValueError(f"missing page bundle row: {page_id}")
        cleaned = {key: str(row.get(key, "")).strip() for key in ("intro", "body", "kicker") if str(row.get(key, "")).strip()}
        if len(cleaned) < 2:
            raise ValueError(f"insufficient page bundle content: {page_id}")
        normalized[page_id] = cleaned
    return normalized


def normalize_parts_bundle(result: dict[str, object]) -> tuple[dict[str, dict[str, str]], dict[str, dict[str, object]]]:
    copy_rows: dict[str, dict[str, str]] = {}
    media_rows: dict[str, dict[str, object]] = {}
    for name, item in PARTS.items():
        row = result.get(name)
        if not isinstance(row, dict):
            raise ValueError(f"missing part bundle row: {name}")
        copy = row.get("copy")
        media = row.get("media")
        if not isinstance(copy, dict) or not isinstance(media, dict):
            raise ValueError(f"invalid part bundle row: {name}")
        cleaned_copy = {key: str(copy.get(key, "")).strip() for key in ("intro", "why", "now") if str(copy.get(key, "")).strip()}
        if len(cleaned_copy) < 3:
            raise ValueError(f"insufficient part copy: {name}")
        media_cleaned = normalize_media_override("horizon", dict(media), item)
        copy_rows[name] = cleaned_copy
        media_rows[name] = media_cleaned
    return copy_rows, media_rows


def normalize_horizons_bundle(result: dict[str, object]) -> tuple[dict[str, dict[str, str]], dict[str, dict[str, object]]]:
    copy_rows: dict[str, dict[str, str]] = {}
    media_rows: dict[str, dict[str, object]] = {}
    for name, item in HORIZONS.items():
        row = result.get(name)
        if not isinstance(row, dict):
            raise ValueError(f"missing horizon bundle row: {name}")
        copy = row.get("copy")
        media = row.get("media")
        if not isinstance(copy, dict) or not isinstance(media, dict):
            raise ValueError(f"invalid horizon bundle row: {name}")
        cleaned_copy = {
            key: str(copy.get(key, "")).strip()
            for key in ("hook", "why_wiz", "brutal_truth", "use_case", "idea", "problem", "why_waits")
            if str(copy.get(key, "")).strip()
        }
        if len(cleaned_copy) < 7:
            raise ValueError(f"insufficient horizon copy: {name}")
        media_cleaned = normalize_media_override("horizon", dict(media), item)
        copy_rows[name] = cleaned_copy
        media_rows[name] = media_cleaned
    return copy_rows, media_rows


SOURCE_SIGNAL_FILES = [
    ("/docker/chummercomplete/chummer-core-engine/instructions.md", "core_instructions"),
    ("/docker/chummercomplete/chummer-core-engine/README.md", "core_readme"),
    ("/docker/chummercomplete/chummer-core-engine/test-lua-evaluator.sh", "core_lua_rules"),
    ("/docker/chummercomplete/chummer-core-engine/Chummer.Rulesets.Sr4/Sr4RulesetPlugin.cs", "core_sr4_plugin"),
    ("/docker/chummercomplete/chummer-presentation/README.md", "ui_readme"),
    ("/docker/chummercomplete/chummer-play/README.md", "play_readme"),
    ("/docker/chummercomplete/chummer.run-services/README.md", "hub_readme"),
    ("/docker/chummercomplete/chummer-design/products/chummer/README.md", "design_front_door"),
    ("/docker/chummercomplete/chummer-design/products/chummer/ARCHITECTURE.md", "design_architecture"),
    ("/docker/chummercomplete/chummer-design/products/chummer/PROGRAM_MILESTONES.yaml", "design_milestones"),
]


def collect_interest_signals() -> dict[str, object]:
    snippets: list[str] = []
    tags: list[str] = []
    for path_text, label in SOURCE_SIGNAL_FILES:
        path = Path(path_text)
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        lowered = text.lower()
        excerpt = short_sentence(text, limit=220)
        if excerpt:
            snippets.append(f"[{label}] {excerpt}")
        for token, tag in (
            ("sr4", "sr4_support"),
            ("sr5", "sr5_support"),
            ("sr6", "sr6_support"),
            ("shadowrun 4", "sr4_support"),
            ("shadowrun 5", "sr5_support"),
            ("shadowrun 6", "sr6_support"),
            ("lua", "lua_rules"),
            ("scripted rules", "lua_rules"),
            ("rulesetplugin", "multi_era_rulesets"),
            ("offline", "offline_play"),
            ("pwa", "installable_pwa"),
            ("explain", "explain_receipts"),
            ("provenance", "provenance_receipts"),
            ("runtime bundle", "runtime_stacks"),
            ("session event", "session_events"),
            ("local-first", "local_first_play"),
        ):
            if token in lowered and tag not in tags:
                tags.append(tag)
    return {"tags": tags, "snippets": snippets[:6]}


def build_ooda_prompt(signals: dict[str, object]) -> str:
    tags = ", ".join(str(tag) for tag in signals.get("tags", []))
    source_excerpt = "\\n\\n".join(str(line) for line in signals.get("snippets", []))
    return f\"\"\"You are the OODA brain for Chummer6, the human-facing guide repo for the Chummer ecosystem.

Task: return a JSON object only with top-level keys observe, orient, decide, act.

Required shape:
- observe: source_signal_tags, source_excerpt_labels, audience_needs, user_interest_signals, risks
- orient: audience, promise, tension, why_care, current_focus, visual_direction, humor_line, signals_to_highlight, banned_terms
- decide: information_order, tone_rules, horizon_policy, media_strategy, overlay_policy, cta_strategy
- act: landing_tagline, landing_intro, what_it_is, watch_intro, horizon_intro

Rules:
- think like a sharp human guide writer, not a compliance bot
- Shadowrun jargon is welcome
- light dev roasting is allowed
- focus on what a curious human would actually care about first
- if the source suggests strong user-facing selling points like multi-era support, Lua/scripted rules, local-first play, explain receipts, grounded dossiers, or dangerous simulation energy, surface them
- do not invent implementation-specific claims unless the source canon makes them explicit
- no mention of Fleet
- no mention of chummer5a
- no markdown fences
- keep every field compact and useful
- why_care and current_focus should be short arrays of punchy strings
- signals_to_highlight should be an array of concrete selling points worth surfacing in the docs
- banned_terms should be an array of internal phrases to avoid in the human guide
- information_order should explain what the guide should lead with before disclaimers
- media_strategy should explain how art should amplify the guide instead of literalizing repo-role labels
- overlay_policy should explain what HUD-style overlays are useful to readers
- cta_strategy should explain how to invite readers to engage without sounding sketchy
- landing_tagline should be short, punchy, and human-facing
- landing_intro should be one short paragraph
- what_it_is should explain the repo in plain language
- watch_intro should tee up why the project is worth following
- horizon_intro should tee up the future ideas in a fun way without pretending they are active work
- keep the whole JSON compact enough to fit on one terminal screen

Observed tags:
{tags}

Observed source excerpts:
{source_excerpt}

Return valid JSON only.
\"\"\"


def normalize_ooda(result: dict[str, object], signals: dict[str, object]) -> dict[str, object]:
    normalized: dict[str, object] = {}
    raw_observe = result.get("observe") if isinstance(result.get("observe"), dict) else {}
    raw_orient = result.get("orient") if isinstance(result.get("orient"), dict) else result
    raw_decide = result.get("decide") if isinstance(result.get("decide"), dict) else {}
    raw_act = result.get("act") if isinstance(result.get("act"), dict) else result

    observe: dict[str, object] = {}
    for key in ("source_signal_tags", "source_excerpt_labels", "audience_needs", "user_interest_signals", "risks"):
        raw = raw_observe.get(key) if isinstance(raw_observe, dict) else None
        if isinstance(raw, list):
            cleaned = [str(item).strip() for item in raw if str(item).strip()]
        else:
            cleaned = []
        if not cleaned:
            raise ValueError(f"global OODA list field is missing: observe.{key}")
        observe[key] = cleaned

    orient: dict[str, object] = {}
    for key in ("audience", "promise", "tension", "visual_direction", "humor_line"):
        value = str(raw_orient.get(key, "")).strip() if isinstance(raw_orient, dict) else ""
        if not value:
            raise ValueError(f"global OODA field is missing: orient.{key}")
        orient[key] = value
    for key in ("why_care", "current_focus", "signals_to_highlight", "banned_terms"):
        raw = raw_orient.get(key) if isinstance(raw_orient, dict) else None
        if isinstance(raw, list):
            cleaned = [str(item).strip() for item in raw if str(item).strip()]
        else:
            cleaned = []
        if not cleaned:
            raise ValueError(f"global OODA list field is missing: orient.{key}")
        orient[key] = cleaned

    decide: dict[str, object] = {}
    for key in ("information_order", "tone_rules", "horizon_policy", "media_strategy", "overlay_policy", "cta_strategy"):
        value = str(raw_decide.get(key, "")).strip() if isinstance(raw_decide, dict) else ""
        if not value:
            raise ValueError(f"global OODA field is missing: decide.{key}")
        decide[key] = value

    act: dict[str, object] = {}
    for key in ("landing_tagline", "landing_intro", "what_it_is", "watch_intro", "horizon_intro"):
        value = str(raw_act.get(key, "")).strip() if isinstance(raw_act, dict) else ""
        if not value:
            raise ValueError(f"global OODA field is missing: act.{key}")
        act[key] = value

    normalized["observe"] = observe
    normalized["orient"] = orient
    normalized["decide"] = decide
    normalized["act"] = act
    return normalized


def build_media_prompt(
    kind: str,
    name: str,
    item: dict[str, object],
    ooda: dict[str, object] | None = None,
    *,
    section_ooda: dict[str, object] | None = None,
) -> str:
    title = str(item.get("title", name.replace("-", " ").title())).strip()
    foundations = "\\n".join(f"- {line}" for line in item.get("foundations", []))
    repos = ", ".join(str(repo) for repo in item.get("repos", []))
    if kind == "hero":
        readme_excerpt = read_markdown_excerpt("README.md", limit=320)
        current_excerpt = read_markdown_excerpt("NOW/current-phase.md", limit=220)
        return f\"\"\"You are writing image-card copy for the human-facing Chummer6 guide landing hero.

Task: return a JSON object only with keys badge, title, subtitle, kicker, note, meta, visual_prompt, overlay_hint, visual_motifs, overlay_callouts, scene_contract.

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

Guide OODA:
{json.dumps(ooda or {}, ensure_ascii=True)}

Section OODA:
{json.dumps(section_ooda or {}, ensure_ascii=True)}

Requirements:
- infer the scene from the source, do not literalize repo-role labels
- do not say or imply "visitor center"
- visual_prompt must describe an actual cyberpunk scene, not a brochure cover
- visual_prompt must center one memorable focal subject, setup, or action instead of generic poster collage
- if the section implies a person or team, choose a believable protagonist instead of abstract symbols
- if the concept implies a visual metaphor like x-ray, ghost, mirror, passport, dossier, or crash-test simulation, make that metaphor visibly legible in-scene
- visual_prompt must be no-text / no-logo / no-watermark / 16:9
- the visible badge/title/subtitle/kicker/note should feel like guide copy, not compliance language
- overlay_hint should name the kind of diegetic HUD/analysis treatment this image wants, in a few words
- visual_motifs should be 3-6 short noun phrases for what should actually be visible
- overlay_callouts should be 2-4 short overlay ideas, not literal on-image text
- scene_contract must be an object with keys:
  - subject
  - environment
  - action
  - metaphor
  - props
  - overlays
  - composition
  - palette
  - mood
  - humor
- scene_contract.subject should name the focal subject in plain language
- scene_contract.metaphor should name the strongest visual metaphor if one exists
- scene_contract.props should be a short list of concrete visible things
- scene_contract.overlays should be a short list of diegetic overlay ideas
- scene_contract.composition should be a short layout phrase like single_protagonist, group_table, desk_still_life, or city_edge

Return valid JSON only.
\"\"\"
    if kind == "part":
        part_excerpt = read_markdown_excerpt(f"PARTS/{name}.md", limit=320)
        return f\"\"\"You are writing image-card copy for a human-facing Chummer6 part banner.

Task: return a JSON object only with keys badge, title, subtitle, kicker, note, meta, visual_prompt, overlay_hint, visual_motifs, overlay_callouts, scene_contract.

Voice rules:
- clear, punchy, slightly funny, Shadowrun-flavored
- sell the part as something a reader should care about right now
- the image should feel grounded, useful, and scene-first
- SR jargon is welcome
- mild dev roasting is allowed
- no mention of Fleet
- no mention of chummer5a
- no markdown fences

Source page excerpt:
{part_excerpt}

Part id: {name}
Title: {title}
Tagline: {item.get("tagline", "")}
Intro: {item.get("intro", "")}
Why: {item.get("why", "")}
Now: {item.get("now", "")}
Owns:
{chr(10).join(f"- {line}" for line in item.get("owns", []))}

Does not own:
{chr(10).join(f"- {line}" for line in item.get("not_owns", []))}

Guide OODA:
{json.dumps(ooda or {}, ensure_ascii=True)}

Section OODA:
{json.dumps(section_ooda or {}, ensure_ascii=True)}

Requirements:
- infer the scene from the source, do not repeat repo labels back as literal signage
- visual_prompt must describe an actual cyberpunk scene tied to this part in use
- visual_prompt must center one memorable focal subject, setup, or action instead of icon soup
- if the part naturally implies a person or team, choose believable cyberpunk people
- if the part naturally implies a machine room, archive, workshop, or table scene, make that spatial metaphor visibly legible
- visual_prompt must be no-text / no-logo / no-watermark / 16:9
- overlay_hint should name the kind of diegetic HUD/analysis treatment this image wants, in a few words
- visual_motifs should be 3-6 short noun phrases for what should actually be visible
- overlay_callouts should be 2-4 short overlay ideas, not literal on-image text
- scene_contract must be an object with keys:
  - subject
  - environment
  - action
  - metaphor
  - props
  - overlays
  - composition
  - palette
  - mood
  - humor

Return valid JSON only.
\"\"\"
    horizon_excerpt = read_markdown_excerpt(f"HORIZONS/{name}.md", limit=320)
    return f\"\"\"You are writing image-card copy for a human-facing Chummer6 horizon banner.

Task: return a JSON object only with keys badge, title, subtitle, kicker, note, meta, visual_prompt, overlay_hint, visual_motifs, overlay_callouts, scene_contract.

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

Guide OODA:
{json.dumps(ooda or {}, ensure_ascii=True)}

Section OODA:
{json.dumps(section_ooda or {}, ensure_ascii=True)}

Requirements:
- infer the scene from the source, do not just repeat headings back
- visual_prompt must describe an actual cyberpunk scene tied to this horizon
- visual_prompt must center one memorable focal subject, setup, or action instead of icon soup
- if the section naturally implies a person, make that person specific and believable
- if the concept implies a visual metaphor like x-ray, ghost, mirror, passport, dossier, web, or blackbox, make that metaphor visibly legible in-scene
- visual_prompt must be no-text / no-logo / no-watermark / 16:9
- the visible copy should sell the horizon without pretending it is active build work
- overlay_hint should name the kind of diegetic HUD/analysis treatment this image wants, in a few words
- visual_motifs should be 3-6 short noun phrases for what should actually be visible
- overlay_callouts should be 2-4 short overlay ideas, not literal on-image text
- scene_contract must be an object with keys:
  - subject
  - environment
  - action
  - metaphor
  - props
  - overlays
  - composition
  - palette
  - mood
  - humor
- if the title reads like a codename or person, make scene_contract.subject a believable cyberpunk person, not a generic skyline
- if the metaphor is x-ray / dossier / forge / ghost / heat web / mirror / passport / blackbox / simulation, make scene_contract.metaphor explicit

Return valid JSON only.
\"\"\"


def normalize_media_override(kind: str, cleaned: dict[str, object], item: dict[str, object]) -> dict[str, object]:
    def infer_scene_contract(*, asset_key: str, visual_prompt: str) -> dict[str, object]:
        lowered = visual_prompt.lower()
        subject = "a cyberpunk protagonist"
        if "team" in lowered or "table" in lowered or "gm" in lowered:
            subject = "a runner team at a live table"
        elif "girl" in lowered or "woman" in lowered or asset_key == "alice":
            subject = "a cyberpunk woman"
        elif "troll" in lowered or "forge" in lowered or asset_key == "karma-forge":
            subject = "a cybernetic troll"
        environment = "a dangerous but inviting cyberpunk scene"
        if "archive" in lowered or "blueprint" in lowered:
            environment = "a blueprint room lit by cold neon"
        elif "workshop" in lowered or "foundation" in lowered:
            environment = "a cyberpunk workshop with exposed internals"
        elif "street" in lowered or "preview" in lowered:
            environment = "a rainy neon street front"
        action = "framing the next move before the chrome starts smoking"
        if "x-ray" in lowered or "xray" in lowered:
            action = "pulling a glowing x-ray of cause and effect through the air"
        elif "simulation" in lowered or "branch" in lowered:
            action = "walking through branching combat outcomes"
        elif "dossier" in lowered or "evidence" in lowered:
            action = "sorting a hot dossier and live evidence threads"
        elif "forge" in lowered:
            action = "hammering volatile rules into controlled shape"
        metaphor = "scene-aware cyberpunk guide art"
        for token, label in (
            ("x-ray", "x-ray causality scan"),
            ("xray", "x-ray causality scan"),
            ("simulation", "branching simulation grid"),
            ("ghost", "forensic replay echoes"),
            ("dossier", "dossier evidence wall"),
            ("forge", "forge sparks and molten rules"),
            ("network", "living consequence web"),
            ("passport", "passport gate"),
            ("mirror", "mirror split"),
            ("blackbox", "blackbox loadout check"),
        ):
            if token in lowered or token in asset_key:
                metaphor = label
                break
        composition = "single_protagonist"
        if "table" in lowered or "team" in lowered:
            composition = "group_table"
        elif "dossier" in lowered or "blackbox" in lowered:
            composition = "desk_still_life"
        elif "horizon" in lowered or asset_key in {"horizons-index", "hero"}:
            composition = "city_edge"
        palette = "cyan-magenta neon"
        mood = "dangerous, curious, and slightly amused"
        humor = "dry roast energy without clown mode"
        props = [
            "wet chrome",
            "holographic receipts",
            "rain haze",
        ]
        overlays = [
            "diegetic HUD traces",
            "receipt markers",
            "signal arcs",
        ]
        return {
            "subject": subject,
            "environment": environment,
            "action": action,
            "metaphor": metaphor,
            "props": props,
            "overlays": overlays,
            "composition": composition,
            "palette": palette,
            "mood": mood,
            "humor": humor,
            "visual_prompt": visual_prompt,
        }

    def normalize_scene_contract(raw: object, *, asset_key: str, visual_prompt: str) -> dict[str, object]:
        default = infer_scene_contract(asset_key=asset_key, visual_prompt=visual_prompt)
        if not isinstance(raw, dict):
            return default
        contract: dict[str, object] = dict(default)
        for key in ("subject", "environment", "action", "metaphor", "composition", "palette", "mood", "humor"):
            value = str(raw.get(key, "")).strip()
            if value:
                contract[key] = value
        for key in ("props", "overlays"):
            value = raw.get(key)
            if isinstance(value, list):
                cleaned_values = [str(entry).strip() for entry in value if str(entry).strip()]
                if cleaned_values:
                    contract[key] = cleaned_values[:6]
        # Keep the prompt close by so downstream renderers can reason over both.
        contract["visual_prompt"] = visual_prompt
        return contract

    normalized = dict(cleaned)
    if kind == "hero":
        for field in ("badge", "title", "subtitle", "kicker", "note", "overlay_hint", "visual_prompt"):
            value = str(normalized.get(field, "")).strip()
            if not value:
                raise ValueError(f"hero media field is missing: {field}")
            normalized[field] = value
        normalized["meta"] = str(normalized.get("meta", "")).strip()
        raw_motifs = normalized.get("visual_motifs")
        if not isinstance(raw_motifs, list):
            raise ValueError("hero media field is missing: visual_motifs")
        motifs = [str(entry).strip() for entry in raw_motifs if str(entry).strip()]
        if not motifs:
            raise ValueError("hero media field is missing: visual_motifs")
        normalized["visual_motifs"] = motifs
        raw_callouts = normalized.get("overlay_callouts")
        if not isinstance(raw_callouts, list):
            raise ValueError("hero media field is missing: overlay_callouts")
        callouts = [str(entry).strip() for entry in raw_callouts if str(entry).strip()]
        if not callouts:
            raise ValueError("hero media field is missing: overlay_callouts")
        normalized["overlay_callouts"] = callouts
        normalized["scene_contract"] = normalize_scene_contract(
            normalized.get("scene_contract"),
            asset_key="hero",
            visual_prompt=str(normalized["visual_prompt"]),
        )
        return normalized
    for field in ("badge", "title", "subtitle", "kicker", "note", "overlay_hint", "visual_prompt"):
        value = str(normalized.get(field, "")).strip()
        if not value:
            raise ValueError(f"horizon media field is missing: {item.get('slug', item.get('title', 'horizon'))}.{field}")
        normalized[field] = value
    normalized["meta"] = str(normalized.get("meta", "")).strip()
    raw_motifs = normalized.get("visual_motifs")
    if not isinstance(raw_motifs, list):
        raise ValueError(f"horizon media field is missing: {item.get('slug', item.get('title', 'horizon'))}.visual_motifs")
    motifs = [str(entry).strip() for entry in raw_motifs if str(entry).strip()]
    if not motifs:
        raise ValueError(f"horizon media field is missing: {item.get('slug', item.get('title', 'horizon'))}.visual_motifs")
    normalized["visual_motifs"] = motifs
    raw_callouts = normalized.get("overlay_callouts")
    if not isinstance(raw_callouts, list):
        raise ValueError(f"horizon media field is missing: {item.get('slug', item.get('title', 'horizon'))}.overlay_callouts")
    callouts = [str(entry).strip() for entry in raw_callouts if str(entry).strip()]
    if not callouts:
        raise ValueError(f"horizon media field is missing: {item.get('slug', item.get('title', 'horizon'))}.overlay_callouts")
    normalized["overlay_callouts"] = callouts
    normalized["scene_contract"] = normalize_scene_contract(
        normalized.get("scene_contract"),
        asset_key=item.get("slug", item.get("title", "horizon")),
        visual_prompt=str(normalized["visual_prompt"]),
    )
    return normalized


PAGE_PROMPTS: dict[str, dict[str, str]] = {
    "readme": {
        "source": "The main landing page. Explain why Chummer6 exists, why a human should care, where they should click next, and why the current phase is foundations first.",
    },
    "start_here": {
        "source": "Welcome and first-run orientation for a new human reader. Explain why there are many repos without sounding like internal process sludge.",
    },
    "what_chummer6_is": {
        "source": "Explain what Chummer6 is, why it exists, who it helps, and what it deliberately is not.",
    },
    "where_to_go_deeper": {
        "source": "Explain where deeper blueprint and code truth live without bureaucratic wording.",
    },
    "current_phase": {
        "source": "Explain the current phase in human language: foundations first, not feature fireworks.",
    },
    "current_status": {
        "source": "Explain the current visible state without sounding like raw ops telemetry.",
    },
    "public_surfaces": {
        "source": "Explain what is visible now and why preview does not mean final public shape.",
    },
    "parts_index": {
        "source": "Introduce the main parts in a field-guide voice and help the reader choose where to go next.",
    },
    "horizons_index": {
        "source": "Sell the horizon section as an exciting garage of future ideas without pretending they are active work.",
    },
}


def chunk_mapping(mapping: dict[str, object], *, size: int) -> list[dict[str, object]]:
    items = list(mapping.items())
    return [dict(items[index : index + size]) for index in range(0, len(items), size)]


def generate_overrides(*, include_parts: bool, include_horizons: bool, model: str) -> dict[str, object]:
    global TEXT_PROVIDER_USED
    TEXT_PROVIDER_USED = ""
    signals = collect_interest_signals()
    overrides: dict[str, object] = {
        "parts": {},
        "horizons": {},
        "pages": {},
        "media": {"hero": {}, "horizons": {}},
        "ooda": {},
        "section_ooda": {"hero": {}, "parts": {}, "horizons": {}, "pages": {}},
        "meta": {
            "generator": "ea",
            "provider": "unknown",
            "provider_status": "unknown",
            "provider_error": "",
            "ooda_version": "v3",
        },
    }
    provider_error = ""
    try:
        ooda_result = chat_json(build_ooda_prompt(signals), model=model)
        overrides["ooda"] = normalize_ooda(ooda_result, signals)
    except Exception as exc:
        raise RuntimeError(f"global OODA generation failed: {exc}") from exc
    ooda = dict(overrides.get("ooda") or {})
    try:
        hero_ooda_result = chat_json(build_section_ooda_prompt("hero", "hero", {}, global_ooda=ooda), model=model)
        hero_ooda = normalize_section_ooda(hero_ooda_result, section_type="hero", name="hero", item={}, global_ooda=ooda)
    except Exception as exc:
        raise RuntimeError(f"hero section OODA generation failed: {exc}") from exc
    overrides["section_ooda"]["hero"]["hero"] = hero_ooda
    try:
        result = chat_json(build_media_prompt("hero", "hero", {}, ooda=ooda, section_ooda=hero_ooda), model=model)
        cleaned = {}
        for key in ("badge", "title", "subtitle", "kicker", "note", "meta", "visual_prompt", "overlay_hint"):
            value = str(result.get(key, "")).strip()
            if value:
                cleaned[key] = value
        for key in ("visual_motifs", "overlay_callouts"):
            raw = result.get(key)
            if isinstance(raw, list):
                cleaned[key] = [str(entry).strip() for entry in raw if str(entry).strip()]
        cleaned = normalize_media_override("hero", cleaned, {})
    except Exception as exc:
        raise RuntimeError(f"hero media generation failed: {exc}") from exc
    cleaned = normalize_media_override("hero", cleaned, {})
    overrides["media"]["hero"] = cleaned
    page_oodas: dict[str, object] = {}
    for batch in chunk_mapping(PAGE_PROMPTS, size=max(len(PAGE_PROMPTS), 1)):
        try:
            page_ooda_result = chat_json(
                build_section_oodas_bundle_prompt("page", batch, global_ooda=ooda),
                model=model,
            )
            page_oodas.update(
                normalize_section_oodas_bundle(
                    page_ooda_result,
                    section_type="page",
                    section_items=batch,
                    global_ooda=ooda,
                )
            )
        except Exception as exc:
            raise RuntimeError(f"page section OODA bundle generation failed ({', '.join(batch.keys())}): {exc}") from exc
    overrides["section_ooda"]["pages"] = page_oodas
    page_rows: dict[str, object] = {}
    for batch in chunk_mapping(PAGE_PROMPTS, size=max(len(PAGE_PROMPTS), 1)):
        try:
            page_bundle = chat_json(
                build_pages_bundle_prompt(
                    global_ooda=ooda,
                    section_oodas={name: page_oodas[name] for name in batch.keys()},
                ),
                model=model,
            )
            page_rows.update(normalize_pages_bundle(page_bundle))
        except Exception as exc:
            raise RuntimeError(f"page copy bundle generation failed ({', '.join(batch.keys())}): {exc}") from exc
    overrides["pages"] = page_rows
    if include_parts:
        part_oodas: dict[str, object] = {}
        for batch in chunk_mapping(PARTS, size=max(len(PARTS), 1)):
            try:
                part_ooda_result = chat_json(
                    build_section_oodas_bundle_prompt("part", batch, global_ooda=ooda),
                    model=model,
                )
                part_oodas.update(
                    normalize_section_oodas_bundle(
                        part_ooda_result,
                        section_type="part",
                        section_items=batch,
                        global_ooda=ooda,
                    )
                )
            except Exception as exc:
                raise RuntimeError(f"part section OODA bundle generation failed ({', '.join(batch.keys())}): {exc}") from exc
        overrides["section_ooda"]["parts"] = part_oodas
        part_copy_rows: dict[str, object] = {}
        part_media_rows: dict[str, object] = {}
        for batch in chunk_mapping(PARTS, size=max(len(PARTS), 1)):
            try:
                part_bundle = chat_json(
                    build_parts_bundle_prompt(
                        global_ooda=ooda,
                        section_oodas={name: part_oodas[name] for name in batch.keys()},
                    ),
                    model=model,
                )
                copy_rows, media_rows = normalize_parts_bundle(part_bundle)
                part_copy_rows.update(copy_rows)
                part_media_rows.update(media_rows)
            except Exception as exc:
                raise RuntimeError(f"part bundle generation failed ({', '.join(batch.keys())}): {exc}") from exc
        overrides["parts"] = part_copy_rows
        overrides["media"]["parts"] = part_media_rows
    if include_horizons:
        horizon_oodas: dict[str, object] = {}
        for batch in chunk_mapping(HORIZONS, size=max(len(HORIZONS), 1)):
            try:
                horizon_ooda_result = chat_json(
                    build_section_oodas_bundle_prompt("horizon", batch, global_ooda=ooda),
                    model=model,
                )
                horizon_oodas.update(
                    normalize_section_oodas_bundle(
                        horizon_ooda_result,
                        section_type="horizon",
                        section_items=batch,
                        global_ooda=ooda,
                    )
                )
            except Exception as exc:
                raise RuntimeError(f"horizon section OODA bundle generation failed ({', '.join(batch.keys())}): {exc}") from exc
        overrides["section_ooda"]["horizons"] = horizon_oodas
        horizon_copy_rows: dict[str, object] = {}
        horizon_media_rows: dict[str, object] = {}
        for batch in chunk_mapping(HORIZONS, size=max(len(HORIZONS), 1)):
            try:
                horizon_bundle = chat_json(
                    build_horizons_bundle_prompt(
                        global_ooda=ooda,
                        section_oodas={name: horizon_oodas[name] for name in batch.keys()},
                    ),
                    model=model,
                )
                copy_rows, media_rows = normalize_horizons_bundle(horizon_bundle)
                horizon_copy_rows.update(copy_rows)
                horizon_media_rows.update(media_rows)
            except Exception as exc:
                raise RuntimeError(f"horizon bundle generation failed ({', '.join(batch.keys())}): {exc}") from exc
        overrides["horizons"] = horizon_copy_rows
        overrides["media"]["horizons"] = horizon_media_rows
    overrides["meta"]["provider"] = TEXT_PROVIDER_USED or "unknown"
    overrides["meta"]["provider_status"] = "ok"
    overrides["meta"]["provider_error"] = provider_error
    return overrides


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Chummer6 downstream guide overrides through EA using section-level OODA.")
    parser.add_argument("--output", default=str(OVERRIDE_OUT), help="Where to write the override JSON.")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Preferred non-Codex text model.")
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
import concurrent.futures
import hashlib
import importlib.util
import json
import os
import shlex
import subprocess
import tempfile
import textwrap
import time
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
    "browseract_magixai",
    "magixai",
    "onemin",
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
    preferred = ["browseract_magixai", "magixai", "onemin"]
    raw = env_value("CHUMMER6_IMAGE_PROVIDER_ORDER")
    if not raw:
        return list(preferred)
    values = [part.strip().lower() for part in raw.split(",") if part.strip()]
    filtered = [value for value in values if value not in {"local_raster", "markupgo", "ooda_compositor", "pollinations"}]
    ordered = sorted(
        dict.fromkeys(filtered),
        key=lambda value: preferred.index(value) if value in preferred else len(preferred),
    )
    return ordered or list(preferred)


OVERRIDE_PATH = Path("/docker/fleet/state/chummer6/ea_overrides.json")


def shlex_command(env_name: str) -> list[str]:
    raw = env_value(env_name)
    if raw:
        return shlex.split(raw)
    defaults = {
        "CHUMMER6_BROWSERACT_PROMPTING_SYSTEMS_RENDER_COMMAND": [
            "python3",
            str(EA_ROOT / "scripts" / "chummer6_browseract_prompting_systems.py"),
            "render",
            "--kind",
            "prompting_render",
            "--prompt",
            "{prompt}",
            "--target",
            "{target}",
            "--output",
            "{output}",
            "--width",
            "{width}",
            "--height",
            "{height}",
        ],
        "CHUMMER6_BROWSERACT_PROMPTING_SYSTEMS_REFINE_COMMAND": [
            "python3",
            str(EA_ROOT / "scripts" / "chummer6_browseract_prompting_systems.py"),
            "refine",
            "--prompt",
            "{prompt}",
            "--target",
            "{target}",
        ],
        "CHUMMER6_BROWSERACT_MAGIXAI_RENDER_COMMAND": [
            "python3",
            str(EA_ROOT / "scripts" / "chummer6_browseract_prompting_systems.py"),
            "render",
            "--kind",
            "magixai_render",
            "--prompt",
            "{prompt}",
            "--target",
            "{target}",
            "--output",
            "{output}",
            "--width",
            "{width}",
            "--height",
            "{height}",
        ],
        "CHUMMER6_PROMPT_REFINER_COMMAND": [
            "python3",
            str(EA_ROOT / "scripts" / "chummer6_browseract_prompting_systems.py"),
            "refine",
            "--prompt",
            "{prompt}",
            "--target",
            "{target}",
        ],
    }
    return list(defaults.get(env_name, []))


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


def format_command(parts: list[str], *, prompt: str, target: str, output: str, width: int, height: int) -> list[str]:
    return [part.format(prompt=prompt, target=target, output=output, width=width, height=height) for part in parts]


def run_command_provider(name: str, template: list[str], *, prompt: str, output_path: Path, width: int, height: int) -> tuple[bool, str]:
    if not template:
        return False, f"{name}:not_configured"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(
            format_command(
                template,
                prompt=prompt,
                target=output_path.stem,
                output=str(output_path),
                width=width,
                height=height,
            ),
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


def run_pollinations_provider(*, prompt: str, output_path: Path, width: int, height: int) -> tuple[bool, str]:
    seed = int(hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:8], 16)
    endpoint = "https://image.pollinations.ai/prompt/" + urllib.parse.quote(prompt, safe="")
    configured = [entry.strip() for entry in env_value("CHUMMER6_POLLINATIONS_MODEL").split(",") if entry.strip()]
    candidates = configured or ["flux", "turbo", "flux-realism"]
    attempts: list[str] = []
    for model in candidates:
        params = {
            "width": str(width),
            "height": str(height),
            "nologo": "true",
            "seed": str(seed),
            "model": model,
        }
        url = endpoint + "?" + urllib.parse.urlencode(params)
        ok, detail = _download_remote_image(url, output_path=output_path, name=f"pollinations:{model}")
        attempts.append(detail)
        if ok:
            return ok, detail
    return False, " || ".join(attempts)


def _download_remote_image(url: str, *, output_path: Path, name: str) -> tuple[bool, str]:
    request = urllib.request.Request(url, headers={"User-Agent": f"EA-Chummer6-{name}/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            data = response.read()
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace").strip()
        return False, f"{name}:image_http_{exc.code}:{body[:240]}"
    except urllib.error.URLError as exc:
        return False, f"{name}:image_urlerror:{exc.reason}"
    if not data:
        return False, f"{name}:image_empty_output"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(data)
    return True, f"{name}:rendered"


def run_magixai_api_provider(*, prompt: str, output_path: Path, width: int, height: int) -> tuple[bool, str]:
    api_key = env_value("AI_MAGICX_API_KEY")
    if not api_key:
        return False, "magixai:not_configured"
    model = env_value("CHUMMER6_MAGIXAI_MODEL") or "qwen-image"
    size = f"{width}x{height}"
    endpoint_specs = [
        (
            "/api/v1/ai-image/generate",
            {
                "model": model,
                "prompt": prompt,
                "size": size,
                "quality": "high",
                "style": "cinematic",
                "negative_prompt": "text, logo, watermark, UI labels, prompt text, low quality, blurry",
                "response_format": "url",
            },
        ),
        (
            "/ai-image/generate",
            {
                "model": model,
                "prompt": prompt,
                "size": size,
                "quality": "high",
                "style": "cinematic",
                "negative_prompt": "text, logo, watermark, UI labels, prompt text, low quality, blurry",
                "response_format": "url",
            },
        ),
        (
            "/api/v1/images/generations",
            {
                "model": model,
                "prompt": prompt,
                "size": size,
                "quality": "high",
                "response_format": "url",
                "n": 1,
            },
        ),
        (
            "/images/generations",
            {
                "model": model,
                "prompt": prompt,
                "size": size,
                "quality": "high",
                "response_format": "url",
                "n": 1,
            },
        ),
        (
            "/api/v1/ai-image/generate",
            {
                "model": model,
                "prompt": prompt,
                "image_size": size,
                "num_images": 1,
                "style": "cinematic",
                "negative_prompt": "text, logo, watermark, UI labels, prompt text, low quality, blurry",
                "response_format": "url",
            },
        ),
    ]
    base_urls = [
        env_value("CHUMMER6_MAGIXAI_BASE_URL") or "https://beta.aimagicx.com",
        "https://www.aimagicx.com",
    ]
    header_variants = [
        {
            "User-Agent": "EA-Chummer6-Magicx/1.0",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        {
            "User-Agent": "EA-Chummer6-Magicx/1.0",
            "Content-Type": "application/json",
            "X-API-Key": api_key,
        },
        {
            "User-Agent": "EA-Chummer6-Magicx/1.0",
            "Content-Type": "application/json",
            "API-KEY": api_key,
        },
    ]
    errors: list[str] = []
    seen_requests: set[tuple[str, tuple[tuple[str, str], ...], str]] = set()
    for base_url in base_urls:
        for endpoint, payload in endpoint_specs:
            url = base_url.rstrip("/") + endpoint
            payload_json = json.dumps(payload, sort_keys=True)
            for headers in header_variants:
                header_key = tuple(sorted((str(key), str(value)) for key, value in headers.items()))
                request_key = (url, header_key, payload_json)
                if request_key in seen_requests:
                    continue
                seen_requests.add(request_key)
                request = urllib.request.Request(
                    url,
                    headers=headers,
                    data=payload_json.encode("utf-8"),
                    method="POST",
                )
                try:
                    with urllib.request.urlopen(request, timeout=45) as response:
                        data = response.read()
                        content_type = str(response.headers.get("Content-Type") or "").lower()
                except urllib.error.HTTPError as exc:
                    body = exc.read().decode("utf-8", errors="replace").strip()
                    errors.append(f"{url}:http_{exc.code}:{body[:180]}")
                    continue
                except urllib.error.URLError as exc:
                    errors.append(f"{url}:urlerror:{exc.reason}")
                    continue
                if data:
                    if content_type.startswith("image/"):
                        output_path.parent.mkdir(parents=True, exist_ok=True)
                        output_path.write_bytes(data)
                        return True, "magixai:rendered"
                    decoded = data.decode("utf-8", errors="replace").strip()
                    if decoded.startswith("http://") or decoded.startswith("https://"):
                        ok, detail = _download_remote_image(decoded, output_path=output_path, name="magixai")
                        if ok:
                            return ok, detail
                        errors.append(detail)
                        continue
                    try:
                        body = json.loads(decoded)
                    except Exception:
                        errors.append(f"{url}:non_json_response:{decoded[:180]}")
                        continue
                candidates: list[str] = []
                if isinstance(body, dict):
                    for field in ("url", "image_url"):
                        value = str(body.get(field) or "").strip()
                        if value:
                            candidates.append(value)
                    data_rows = body.get("data")
                    if isinstance(data_rows, list):
                        for entry in data_rows:
                            if not isinstance(entry, dict):
                                continue
                            value = str(entry.get("url") or entry.get("image_url") or "").strip()
                            if value:
                                candidates.append(value)
                    output_rows = body.get("output")
                    if isinstance(output_rows, list):
                        for entry in output_rows:
                            if not isinstance(entry, dict):
                                continue
                            value = str(entry.get("url") or entry.get("image_url") or "").strip()
                            if value:
                                candidates.append(value)
                for candidate in candidates:
                    ok, detail = _download_remote_image(candidate, output_path=output_path, name="magixai")
                    if ok:
                        return ok, detail
                    errors.append(detail)
    return False, "magixai:" + " || ".join(errors[:6])


def resolve_onemin_image_keys() -> list[str]:
    script_path = EA_ROOT / "scripts" / "resolve_onemin_ai_key.sh"
    keys: list[str] = []
    seen: set[str] = set()
    if script_path.exists():
        try:
            output = subprocess.check_output(
                ["bash", str(script_path), "--all"],
                text=True,
            )
        except Exception:
            output = ""
        for raw in output.splitlines():
            key = str(raw or "").strip()
            if key and key not in seen:
                seen.add(key)
                keys.append(key)
    for env_name in ("ONEMIN_AI_API_KEY", "ONEMIN_AI_API_KEY_FALLBACK_1", "ONEMIN_AI_API_KEY_FALLBACK_2", "ONEMIN_AI_API_KEY_FALLBACK_3"):
        key = env_value(env_name)
        if key and key not in seen:
            seen.add(key)
            keys.append(key)
    return keys


def _collect_image_candidates(value: object) -> list[str]:
    found: list[str] = []
    if isinstance(value, str):
        candidate = str(value or "").strip()
        lowered = candidate.lower()
        if candidate.startswith("http://") or candidate.startswith("https://"):
            found.append(candidate)
        elif candidate.startswith("/"):
            found.append("https://api.1min.ai" + candidate)
        elif any(token in lowered for token in ("asset", "image", "render", "download")) and ("/" in candidate or "." in candidate):
            found.append("https://api.1min.ai/" + candidate.lstrip("/"))
        return found
    if isinstance(value, dict):
        for nested in value.values():
            found.extend(_collect_image_candidates(nested))
        return found
    if isinstance(value, (list, tuple, set)):
        for nested in value:
            found.extend(_collect_image_candidates(nested))
    return found


def run_onemin_api_provider(*, prompt: str, output_path: Path, width: int, height: int) -> tuple[bool, str]:
    keys = resolve_onemin_image_keys()
    if not keys:
        return False, "onemin:not_configured"
    model_candidates: list[str] = []
    for candidate in (
        env_value("CHUMMER6_ONEMIN_MODEL"),
        "dall-e-3",
        "gpt-image-1-mini",
    ):
        normalized = str(candidate or "").strip()
        if normalized and normalized not in model_candidates:
            model_candidates.append(normalized)
    size = env_value("CHUMMER6_ONEMIN_IMAGE_SIZE") or "512x512"
    endpoints = [
        env_value("CHUMMER6_ONEMIN_ENDPOINT") or "https://api.1min.ai/api/features",
    ]
    errors: list[str] = []
    header_variants = []
    for key in keys:
        header_variants.append(
            {
                "User-Agent": "EA-Chummer6-1min/1.0",
                "Content-Type": "application/json",
                "API-KEY": key,
            }
        )
    seen_requests: set[tuple[str, tuple[tuple[str, str], ...], str]] = set()
    for url in endpoints:
        for model in model_candidates:
            prompt_object = {
                "prompt": prompt,
                "n": 1,
                "size": size,
                "quality": env_value("CHUMMER6_ONEMIN_IMAGE_QUALITY") or "low",
                "style": "natural",
                "output_format": "png",
                "background": "opaque",
            }
            payloads = [
                {
                    "type": "IMAGE_GENERATOR",
                    "model": model,
                    "promptObject": dict(prompt_object),
                },
            ]
            for payload in payloads:
                payload_json = json.dumps(payload, sort_keys=True)
                for headers in header_variants:
                    header_key = tuple(sorted((str(key), str(value)) for key, value in headers.items()))
                    request_key = (url, header_key, payload_json)
                    if request_key in seen_requests:
                        continue
                    seen_requests.add(request_key)
                    request = urllib.request.Request(
                        url,
                        headers=headers,
                        data=payload_json.encode("utf-8"),
                        method="POST",
                    )
                    try:
                        with urllib.request.urlopen(request, timeout=45) as response:
                            data = response.read()
                            content_type = str(response.headers.get("Content-Type") or "").lower()
                    except urllib.error.HTTPError as exc:
                        body = exc.read().decode("utf-8", errors="replace").strip()
                        retryable_busy = exc.code == 400 and "OPEN_AI_UNEXPECTED_ERROR" in body
                        if retryable_busy:
                            busy_recovered = False
                            for _attempt in range(6):
                                time.sleep(6)
                                try:
                                    request = urllib.request.Request(
                                        url,
                                        headers=headers,
                                        data=payload_json.encode("utf-8"),
                                        method="POST",
                                    )
                                    with urllib.request.urlopen(request, timeout=45) as response:
                                        data = response.read()
                                        content_type = str(response.headers.get("Content-Type") or "").lower()
                                        busy_recovered = True
                                        break
                                except urllib.error.HTTPError as retry_exc:
                                    body = retry_exc.read().decode("utf-8", errors="replace").strip()
                                    retryable_busy = retry_exc.code == 400 and "OPEN_AI_UNEXPECTED_ERROR" in body
                                    if not retryable_busy:
                                        errors.append(f"{url}:{model}:http_{retry_exc.code}:{body[:180]}")
                                        break
                                except urllib.error.URLError as retry_url_exc:
                                    errors.append(f"{url}:{model}:urlerror:{retry_url_exc.reason}")
                                    break
                            if not busy_recovered:
                                if retryable_busy:
                                    errors.append(f"{url}:{model}:openai_busy")
                                continue
                        else:
                            errors.append(f"{url}:{model}:http_{exc.code}:{body[:180]}")
                            if exc.code == 401:
                                break
                            continue
                    except urllib.error.URLError as exc:
                        errors.append(f"{url}:{model}:urlerror:{exc.reason}")
                        continue
                    if data:
                        if content_type.startswith("image/"):
                            output_path.parent.mkdir(parents=True, exist_ok=True)
                            output_path.write_bytes(data)
                            return True, "onemin:rendered"
                        decoded = data.decode("utf-8", errors="replace").strip()
                        if decoded.startswith("http://") or decoded.startswith("https://"):
                            ok, detail = _download_remote_image(decoded, output_path=output_path, name="onemin")
                            if ok:
                                return ok, detail
                            errors.append(detail)
                            continue
                        try:
                            body = json.loads(decoded)
                        except Exception:
                            errors.append(f"{url}:{model}:non_json_response:{decoded[:180]}")
                            continue
                        for candidate in _collect_image_candidates(body):
                            ok, detail = _download_remote_image(candidate, output_path=output_path, name="onemin")
                            if ok:
                                return ok, detail
                            errors.append(detail)
    return False, "onemin:" + " || ".join(errors[:6])


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


def _font_path(bold: bool = False) -> str:
    path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    return path


def _write_text_file(directory: Path, name: str, value: str, *, width: int) -> Path:
    wrapped = textwrap.fill(" ".join(str(value or "").split()).strip(), width=width)
    path = directory / name
    path.write_text(wrapped + "\\n", encoding="utf-8")
    return path


def _ffmpeg_path(value: Path) -> str:
    return str(value).replace("\\\\", "\\\\\\\\").replace(":", "\\\\:")


def _ooda_layout_for(target: str) -> str:
    lowered = str(target or "").lower()
    if "horizons-index" in lowered or "parts-index" in lowered:
        return "grid"
    if "current-status" in lowered or "public-surfaces" in lowered:
        return "status"
    return "banner"


def run_ooda_compositor(*, spec: dict[str, object], prompt: str, output_path: Path, width: int, height: int) -> tuple[bool, str]:
    row = spec.get("media_row") if isinstance(spec.get("media_row"), dict) else {}
    if not isinstance(row, dict):
        return False, "ooda_compositor:missing_media_row"
    title = " ".join(str(row.get("title", "") or output_path.stem).split()).strip() or output_path.stem.replace("-", " ").title()
    subtitle = " ".join(str(row.get("subtitle", "")).split()).strip()
    kicker = " ".join(str(row.get("kicker", "")).split()).strip()
    note = " ".join(str(row.get("note", "")).split()).strip()
    overlay_hint = " ".join(str(row.get("overlay_hint", "")).split()).strip()
    callouts = [str(entry).strip() for entry in (row.get("overlay_callouts") or []) if str(entry).strip()]
    motifs = [str(entry).strip() for entry in (row.get("visual_motifs") or []) if str(entry).strip()]
    scene_contract = row.get("scene_contract") if isinstance(row.get("scene_contract"), dict) else {}
    if not scene_contract or not str(scene_contract.get("visual_prompt") or row.get("visual_prompt") or "").strip():
        return False, "ooda_compositor:missing_scene_contract"
    layout = _ooda_layout_for(str(spec.get("target", output_path.name)))
    accent, glow = palette_for(prompt + "::" + title + "::" + str(scene_contract.get("palette", "")))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(
        GUIDE.synth_context_scene_png(
            title,
            accent,
            glow,
            scene_contract,
            scene_row=row,
            width=width,
            height=height,
            layout=layout,
        )
    )
    return True, "scene_contract_renderer:rendered"


def refine_prompt_local(prompt: str, *, target: str) -> str:
    return " ".join(prompt.split()).strip()


def refine_prompt_with_ooda(*, prompt: str, target: str) -> str:
    # Prompt refinement must use the external lane when it is configured.
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
    attempted: list[str] = []
    external_expected = bool(env_value("BROWSERACT_API_KEY"))
    for env_name in command_names:
        command = shlex_command(env_name)
        if not command:
            continue
        external_expected = True
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
            attempted.append(f"{env_name}:empty_output")
        except Exception as exc:
            attempted.append(f"{env_name}:{exc}")
    for env_name in template_names:
        template = url_template(env_name)
        if not template:
            continue
        external_expected = True
        url = template.format(
            prompt=urllib.parse.quote(prompt, safe=""),
            target=urllib.parse.quote(target, safe=""),
        )
        request = urllib.request.Request(url, headers={"User-Agent": "EA-Chummer6-PromptRefiner/1.0"})
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                refined = response.read().decode("utf-8", errors="replace").strip()
            if refined:
                return refined
            attempted.append(f"{env_name}:empty_output")
        except Exception as exc:
            attempted.append(f"{env_name}:{exc}")
    if external_expected:
        detail = " || ".join(attempted) if attempted else "no_external_refiner_succeeded"
        raise RuntimeError(f"prompt_refinement_failed:{detail}")
    return refine_prompt_local(prompt, target=target)


def sanitize_prompt_for_provider(prompt: str, *, provider: str) -> str:
    cleaned = " ".join(str(prompt or "").split()).strip()
    if not cleaned:
        return cleaned
    provider_name = str(provider or "").strip().lower()
    if provider_name in {"onemin", "1min", "1min.ai", "oneminai"}:
        replacements = {
            "Shadowrun": "cyberpunk tabletop",
            "shadowrun": "cyberpunk tabletop",
            "runner": "operative",
            "runners": "operatives",
            "dangerous": "tense",
            "combat": "tactical simulation",
            "crash-test dummy": "test mannequin",
            "crash test dummy": "test mannequin",
            "weapon": "gear",
            "weapons": "gear",
            "gun": "tool",
            "guns": "tools",
            "blood": "stress",
            "gore": "damage",
        }
        for src, dst in replacements.items():
            cleaned = cleaned.replace(src, dst)
        cleaned += " Safe-for-work, nonviolent, no gore, no weapons, no explicit danger."
    return cleaned


def build_safe_pollinations_prompt(*, prompt: str, spec: dict[str, object]) -> str:
    row = spec.get("media_row") if isinstance(spec, dict) else {}
    contract = row.get("scene_contract") if isinstance(row, dict) else {}
    if not isinstance(contract, dict):
        cleaned = " ".join(str(prompt or "").split()).strip()
        return cleaned[:220]
    subject = str(contract.get("subject") or "a cyberpunk protagonist").strip()
    environment = str(contract.get("environment") or "a neon-lit cyberpunk setting").strip()
    action = str(contract.get("action") or "holding the moment together").strip()
    metaphor = str(contract.get("metaphor") or "").strip()
    palette = str(contract.get("palette") or "rainy neon cyan and magenta").strip()
    mood = str(contract.get("mood") or "tense but inviting").strip()
    parts = [
        "Wide cinematic cyberpunk concept art",
        subject,
        f"in {environment}",
        action,
        metaphor if metaphor else "",
        mood,
        palette,
        "one focal subject",
        "no text no logo no watermark 16:9",
    ]
    return ", ".join(part for part in parts if part)[:240]


def build_safe_onemin_prompt(*, prompt: str, spec: dict[str, object]) -> str:
    row = spec.get("media_row") if isinstance(spec, dict) else {}
    contract = row.get("scene_contract") if isinstance(row, dict) else {}
    if not isinstance(contract, dict):
        return sanitize_prompt_for_provider(prompt, provider="onemin")
    subject = str(contract.get("subject") or "a cyberpunk protagonist").strip()
    environment = str(contract.get("environment") or "a neon-lit cyberpunk setting").strip()
    action = str(contract.get("action") or "holding the moment together").strip()
    metaphor = str(contract.get("metaphor") or "").strip()
    composition = str(contract.get("composition") or "single_protagonist").strip()
    palette = str(contract.get("palette") or "cool neon").strip()
    mood = str(contract.get("mood") or "focused").strip()
    props = ", ".join(str(entry).strip() for entry in (contract.get("props") or []) if str(entry).strip())
    parts = [
        "Wide cinematic cyberpunk concept art.",
        f"Subject: {subject}.",
        f"Environment: {environment}.",
        f"Action: {action}.",
        f"Visual metaphor: {metaphor}." if metaphor else "",
        f"Composition: {composition}.",
        f"Palette: {palette}.",
        f"Mood: {mood}.",
        f"Visible props: {props}." if props else "",
        "Safe-for-work, nonviolent, no weapons, no gore, no explicit peril.",
        "No text, no logo, no watermark, 16:9.",
    ]
    return sanitize_prompt_for_provider(" ".join(part for part in parts if part), provider="onemin")


def render_with_ooda(*, prompt: str, output_path: Path, width: int, height: int, spec: dict[str, object]) -> dict[str, object]:
    attempts: list[str] = []
    requested_order = spec.get("providers")
    providers = (
        [str(entry).strip() for entry in requested_order if str(entry).strip()]
        if isinstance(requested_order, list)
        else provider_order()
    )
    for provider in providers:
        normalized = provider.strip().lower()
        if normalized == "pollinations":
            safe_prompt = build_safe_pollinations_prompt(prompt=prompt, spec=spec)
            ok, detail = run_pollinations_provider(prompt=safe_prompt, output_path=output_path, width=width, height=height)
        elif normalized == "magixai":
            safe_prompt = sanitize_prompt_for_provider(prompt, provider=normalized)
            ok, detail = run_magixai_api_provider(prompt=safe_prompt, output_path=output_path, width=width, height=height)
            if not ok:
                command_ok, command_detail = run_command_provider("magixai", shlex_command("CHUMMER6_MAGIXAI_RENDER_COMMAND"), prompt=safe_prompt, output_path=output_path, width=width, height=height)
                if command_ok or detail.endswith(":not_configured"):
                    ok, detail = command_ok, command_detail
            if not ok:
                url_ok, url_detail = run_url_provider("magixai", url_template("CHUMMER6_MAGIXAI_RENDER_URL_TEMPLATE"), prompt=safe_prompt, output_path=output_path, width=width, height=height)
                if url_ok or detail.endswith(":not_configured"):
                    ok, detail = url_ok, url_detail
        elif normalized == "markupgo":
            ok, detail = False, "markupgo:disabled_for_primary_art"
        elif normalized == "prompting_systems":
            ok, detail = run_command_provider("prompting_systems", shlex_command("CHUMMER6_PROMPTING_SYSTEMS_RENDER_COMMAND"), prompt=prompt, output_path=output_path, width=width, height=height)
            if not ok:
                url_ok, url_detail = run_url_provider("prompting_systems", url_template("CHUMMER6_PROMPTING_SYSTEMS_RENDER_URL_TEMPLATE"), prompt=prompt, output_path=output_path, width=width, height=height)
                if url_ok or detail.endswith(":not_configured"):
                    ok, detail = url_ok, url_detail
        elif normalized == "browseract_magixai":
            if env_value("BROWSERACT_API_KEY"):
                ok, detail = run_command_provider("browseract_magixai", shlex_command("CHUMMER6_BROWSERACT_MAGIXAI_RENDER_COMMAND"), prompt=prompt, output_path=output_path, width=width, height=height)
                if not ok:
                    url_ok, url_detail = run_url_provider("browseract_magixai", url_template("CHUMMER6_BROWSERACT_MAGIXAI_RENDER_URL_TEMPLATE"), prompt=prompt, output_path=output_path, width=width, height=height)
                    if url_ok or detail.endswith(":not_configured"):
                        ok, detail = url_ok, url_detail
            else:
                ok, detail = False, "browseract_magixai:not_configured"
        elif normalized == "browseract_prompting_systems":
            if env_value("BROWSERACT_API_KEY"):
                ok, detail = run_command_provider("browseract_prompting_systems", shlex_command("CHUMMER6_BROWSERACT_PROMPTING_SYSTEMS_RENDER_COMMAND"), prompt=prompt, output_path=output_path, width=width, height=height)
                if not ok:
                    url_ok, url_detail = run_url_provider("browseract_prompting_systems", url_template("CHUMMER6_BROWSERACT_PROMPTING_SYSTEMS_RENDER_URL_TEMPLATE"), prompt=prompt, output_path=output_path, width=width, height=height)
                    if url_ok or detail.endswith(":not_configured"):
                        ok, detail = url_ok, url_detail
                if not ok:
                    command_ok, command_detail = run_command_provider("browseract_prompting_systems", shlex_command("CHUMMER6_PROMPTING_SYSTEMS_RENDER_COMMAND"), prompt=prompt, output_path=output_path, width=width, height=height)
                    if command_ok or detail.endswith(":not_configured"):
                        ok, detail = command_ok, command_detail
                if not ok:
                    url_ok, url_detail = run_url_provider("browseract_prompting_systems", url_template("CHUMMER6_PROMPTING_SYSTEMS_RENDER_URL_TEMPLATE"), prompt=prompt, output_path=output_path, width=width, height=height)
                    if url_ok or detail.endswith(":not_configured"):
                        ok, detail = url_ok, url_detail
            else:
                ok, detail = False, "browseract_prompting_systems:not_configured"
        elif normalized in {"onemin", "1min", "1min.ai", "oneminai"}:
            safe_prompt = build_safe_onemin_prompt(prompt=prompt, spec=spec)
            ok, detail = run_onemin_api_provider(prompt=safe_prompt, output_path=output_path, width=width, height=height)
            if not ok:
                command_ok, command_detail = run_command_provider("onemin", shlex_command("CHUMMER6_1MIN_RENDER_COMMAND"), prompt=safe_prompt, output_path=output_path, width=width, height=height)
                if command_ok or detail.endswith(":not_configured"):
                    ok, detail = command_ok, command_detail
            if not ok:
                url_ok, url_detail = run_url_provider("onemin", url_template("CHUMMER6_1MIN_RENDER_URL_TEMPLATE"), prompt=safe_prompt, output_path=output_path, width=width, height=height)
                if url_ok or detail.endswith(":not_configured"):
                    ok, detail = url_ok, url_detail
        elif normalized in {"scene_contract_renderer", "ooda_compositor"}:
            ok, detail = run_ooda_compositor(spec=spec, prompt=prompt, output_path=output_path, width=width, height=height)
        elif normalized == "local_raster":
            ok, detail = False, "local_raster:disabled"
        else:
            ok, detail = False, f"{normalized}:unknown_provider"
        attempts.append(detail)
        if ok:
            return {"provider": normalized, "status": detail, "attempts": attempts}
    raise RuntimeError("no image provider succeeded: " + " || ".join(attempts))


def asset_specs() -> list[dict[str, object]]:
    loaded = load_media_overrides()
    media = loaded.get("media") if isinstance(loaded, dict) else {}
    pages = loaded.get("pages") if isinstance(loaded, dict) else {}
    section_ooda = loaded.get("section_ooda") if isinstance(loaded, dict) else {}
    page_ooda = section_ooda.get("pages") if isinstance(section_ooda, dict) else {}
    hero_override = media.get("hero") if isinstance(media, dict) else {}
    if not isinstance(hero_override, dict) or not str(hero_override.get("visual_prompt", "")).strip():
        raise RuntimeError("missing hero visual_prompt in EA overrides")
    if not isinstance(pages, dict):
        raise RuntimeError("missing page overrides in EA output")
    if not isinstance(page_ooda, dict):
        raise RuntimeError("missing page section OODA in EA output")

    def render_prompt_from_row(row: dict[str, object], *, role: str) -> str:
        contract = row.get("scene_contract") if isinstance(row.get("scene_contract"), dict) else {}
        subject = str(contract.get("subject", "")).strip()
        environment = str(contract.get("environment", "")).strip()
        action = str(contract.get("action", "")).strip()
        metaphor = str(contract.get("metaphor", "")).strip()
        composition = str(contract.get("composition", "")).strip()
        palette = str(contract.get("palette", "")).strip()
        mood = str(contract.get("mood", "")).strip()
        humor = str(contract.get("humor", "")).strip()
        props = ", ".join(str(entry).strip() for entry in (contract.get("props") or []) if str(entry).strip())
        overlays = ", ".join(str(entry).strip() for entry in (contract.get("overlays") or []) if str(entry).strip())
        motifs = ", ".join(str(entry).strip() for entry in (row.get("visual_motifs") or []) if str(entry).strip())
        callouts = ", ".join(str(entry).strip() for entry in (row.get("overlay_callouts") or []) if str(entry).strip())
        visual_prompt = str(row.get("visual_prompt", "")).strip()
        prompt_parts = [
            f"Wide cinematic cyberpunk concept art for the Chummer6 {role}.",
            visual_prompt,
            f"One clear focal subject: {subject}." if subject else "",
            f"Set the scene in {environment}." if environment else "",
            f"Show this happening: {action}." if action else "",
            f"Make the core visual metaphor immediately legible: {metaphor}." if metaphor else "",
            f"Use a {composition} composition." if composition else "",
            f"Palette: {palette}." if palette else "",
            f"Mood: {mood}." if mood else "",
            f"Humor note: {humor}." if humor else "",
            f"Concrete visible props: {props}." if props else "",
            f"Useful diegetic overlays in-scene: {overlays}." if overlays else "",
            f"Reader-facing motifs to weave in visually: {motifs}." if motifs else "",
            f"Overlay ideas to imply, not print literally: {callouts}." if callouts else "",
            "Make it feel like a lived-in Shadowrun street, lab, archive, forge, or table scene, not a product poster.",
            "Avoid generic skylines, abstract icon soup, flat infographics, or brochure-cover posing.",
            "Do not print text, prompts, OODA labels, metadata, or resolution callouts on the image.",
            "No text, no logo, no watermark, 16:9.",
        ]
        return " ".join(part for part in prompt_parts if part)

    def page_media_row(page_id: str, *, role: str, composition_hint: str) -> dict[str, object]:
        page_row = pages.get(page_id)
        ooda_row = page_ooda.get(page_id)
        if not isinstance(page_row, dict):
            raise RuntimeError(f"missing page override for media asset: {page_id}")
        if not isinstance(ooda_row, dict):
            raise RuntimeError(f"missing section OODA for media asset: {page_id}")
        act = ooda_row.get("act") if isinstance(ooda_row.get("act"), dict) else {}
        observe = ooda_row.get("observe") if isinstance(ooda_row.get("observe"), dict) else {}
        orient = ooda_row.get("orient") if isinstance(ooda_row.get("orient"), dict) else {}
        decide = ooda_row.get("decide") if isinstance(ooda_row.get("decide"), dict) else {}
        visual_seed = str(act.get("visual_prompt_seed", "")).strip()
        intro = str(page_row.get("intro", "")).strip()
        body = str(page_row.get("body", "")).strip()
        focal = str(orient.get("focal_subject", "")).strip()
        scene_logic = str(orient.get("scene_logic", "")).strip()
        overlay = str(decide.get("overlay_priority", "")).strip()
        interests = observe.get("likely_interest") if isinstance(observe.get("likely_interest"), list) else []
        concrete = observe.get("concrete_signals") if isinstance(observe.get("concrete_signals"), list) else []
        if not visual_seed:
            raise RuntimeError(f"missing visual prompt seed for page media asset: {page_id}")
        return {
            "title": role,
            "subtitle": intro,
            "kicker": str(page_row.get("kicker", "")).strip(),
            "note": body,
            "overlay_hint": overlay or str(orient.get("visual_devices", "")).strip(),
            "visual_prompt": visual_seed,
            "visual_motifs": [str(entry).strip() for entry in interests if str(entry).strip()],
            "overlay_callouts": [str(entry).strip() for entry in concrete if str(entry).strip()],
            "scene_contract": {
                "subject": focal or "a cyberpunk protagonist",
                "environment": scene_logic or body,
                "action": str(act.get("paragraph_seed", "")).strip() or str(act.get("one_liner", "")).strip(),
                "metaphor": page_id.replace("_", " "),
                "props": [str(entry).strip() for entry in interests if str(entry).strip()][:5],
                "overlays": [str(entry).strip() for entry in concrete if str(entry).strip()][:4],
                "composition": composition_hint,
                "palette": str(orient.get("visual_devices", "")).strip(),
                "mood": str(orient.get("emotional_goal", "")).strip(),
                "humor": str(orient.get("tone_rule", "")).strip(),
            },
        }

    def page_visual_prompt(page_id: str, *, role: str, composition_hint: str) -> str:
        return render_prompt_from_row(
            page_media_row(page_id, role=role, composition_hint=composition_hint),
            role=role,
        )

    specs: list[dict[str, object]] = [
        {
            "target": "assets/hero/chummer6-hero.png",
            "prompt": render_prompt_from_row(hero_override, role="landing hero"),
            "width": 960,
            "height": 540,
            "media_row": hero_override,
            "providers": ["browseract_magixai", "magixai", "onemin"],
        },
        {
            "target": "assets/hero/poc-warning.png",
            "prompt": page_visual_prompt("readme", role="POC warning shelf", composition_hint="desk_still_life"),
            "width": 960,
            "height": 540,
            "media_row": page_media_row("readme", role="POC warning shelf", composition_hint="desk_still_life"),
            "providers": ["browseract_magixai", "magixai", "onemin"],
        },
        {
            "target": "assets/pages/start-here.png",
            "prompt": page_visual_prompt("start_here", role="start-here banner", composition_hint="city_edge"),
            "width": 960,
            "height": 540,
            "media_row": page_media_row("start_here", role="start-here banner", composition_hint="city_edge"),
            "providers": ["browseract_magixai", "magixai", "onemin"],
        },
        {
            "target": "assets/pages/what-chummer6-is.png",
            "prompt": page_visual_prompt("what_chummer6_is", role="what-is banner", composition_hint="single_protagonist"),
            "width": 960,
            "height": 540,
            "media_row": page_media_row("what_chummer6_is", role="what-is banner", composition_hint="single_protagonist"),
            "providers": ["browseract_magixai", "magixai", "onemin"],
        },
        {
            "target": "assets/pages/where-to-go-deeper.png",
            "prompt": page_visual_prompt("where_to_go_deeper", role="deeper-dive banner", composition_hint="archive_room"),
            "width": 960,
            "height": 540,
            "media_row": page_media_row("where_to_go_deeper", role="deeper-dive banner", composition_hint="archive_room"),
            "providers": ["browseract_magixai", "magixai", "onemin"],
        },
        {
            "target": "assets/pages/current-phase.png",
            "prompt": page_visual_prompt("current_phase", role="current-phase banner", composition_hint="workshop"),
            "width": 960,
            "height": 540,
            "media_row": page_media_row("current_phase", role="current-phase banner", composition_hint="workshop"),
            "providers": ["browseract_magixai", "magixai", "onemin"],
        },
        {
            "target": "assets/pages/current-status.png",
            "prompt": page_visual_prompt("current_status", role="current-status banner", composition_hint="street_front"),
            "width": 960,
            "height": 540,
            "media_row": page_media_row("current_status", role="current-status banner", composition_hint="street_front"),
            "providers": ["browseract_magixai", "magixai", "onemin"],
        },
        {
            "target": "assets/pages/public-surfaces.png",
            "prompt": page_visual_prompt("public_surfaces", role="public-surfaces banner", composition_hint="street_front"),
            "width": 960,
            "height": 540,
            "media_row": page_media_row("public_surfaces", role="public-surfaces banner", composition_hint="street_front"),
            "providers": ["browseract_magixai", "magixai", "onemin"],
        },
        {
            "target": "assets/pages/parts-index.png",
            "prompt": page_visual_prompt("parts_index", role="parts-overview banner", composition_hint="district_map"),
            "width": 960,
            "height": 540,
            "media_row": page_media_row("parts_index", role="parts-overview banner", composition_hint="district_map"),
            "providers": ["browseract_magixai", "magixai", "onemin"],
        },
        {
            "target": "assets/pages/horizons-index.png",
            "prompt": page_visual_prompt("horizons_index", role="horizons boulevard banner", composition_hint="horizon_boulevard"),
            "width": 960,
            "height": 540,
            "media_row": page_media_row("horizons_index", role="horizons boulevard banner", composition_hint="horizon_boulevard"),
            "providers": ["browseract_magixai", "magixai", "onemin"],
        },
    ]
    part_overrides = media.get("parts") if isinstance(media, dict) else {}
    for slug, item in GUIDE.PARTS.items():
        override = part_overrides.get(slug) if isinstance(part_overrides, dict) else None
        if not isinstance(override, dict) or not str(override.get("visual_prompt", "")).strip():
            raise RuntimeError(f"missing part visual_prompt in EA overrides: {slug}")
        specs.append(
            {
                "target": f"assets/parts/{slug}.png",
                "prompt": render_prompt_from_row(override, role=f"{slug} part page"),
                "width": 960,
                "height": 540,
                "media_row": override,
                "providers": ["browseract_magixai", "magixai", "onemin"],
            }
        )
    horizon_overrides = media.get("horizons") if isinstance(media, dict) else {}
    for slug, item in GUIDE.HORIZONS.items():
        override = horizon_overrides.get(slug) if isinstance(horizon_overrides, dict) else None
        if not isinstance(override, dict) or not str(override.get("visual_prompt", "")).strip():
            raise RuntimeError(f"missing horizon visual_prompt in EA overrides: {slug}")
        specs.append(
            {
                "target": f"assets/horizons/{slug}.png",
                "prompt": render_prompt_from_row(override, role=f"{slug} horizon page"),
                "width": 960,
                "height": 540,
                "media_row": override,
                "providers": ["browseract_magixai", "magixai", "onemin"],
            }
        )
    return specs


def render_pack(*, output_dir: Path) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    specs = asset_specs()
    concurrency = max(1, min(4, int(env_value("CHUMMER6_MEDIA_RENDER_CONCURRENCY") or "1")))

    def _render_spec(spec: dict[str, object]) -> dict[str, object]:
        target = str(spec["target"])
        prompt = refine_prompt_with_ooda(prompt=str(spec["prompt"]), target=target)
        width = int(spec.get("width", 1280))
        height = int(spec.get("height", 720))
        out_path = output_dir / target
        out_path.parent.mkdir(parents=True, exist_ok=True)
        result = render_with_ooda(prompt=prompt, output_path=out_path, width=width, height=height, spec=spec)
        return {
            "target": target,
            "output": str(out_path),
            "provider": result["provider"],
            "status": result["status"],
            "attempts": result["attempts"],
        }

    # Fail fast on the first asset instead of chewing through the whole pack when no real lane works.
    first_result = _render_spec(specs[0])
    ordered_results: list[dict[str, object] | None] = [None] * len(specs)
    ordered_results[0] = first_result
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
        future_map = {
            executor.submit(_render_spec, spec): index
            for index, spec in enumerate(specs[1:], start=1)
        }
        for future in concurrent.futures.as_completed(future_map):
            index = future_map[future]
            ordered_results[index] = future.result()
    assets = [result for result in ordered_results if isinstance(result, dict)]
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
    result = render_with_ooda(
        prompt=str(args.prompt),
        output_path=output_path,
        width=int(args.width),
        height=int(args.height),
        spec={"target": str(output_path.name), "media_row": {}},
    )
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
            "primary": ["Codex", "AI Magicx", "Prompting Systems"],
            "research": ["BrowserAct"],
            "output": ["AI Magicx", "Prompting Systems", "BrowserAct"],
            "media": ["AI Magicx", "Prompting Systems", "BrowserAct"],
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
    "pollinations": [],
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
    "browseract_magixai": [
        "CHUMMER6_BROWSERACT_MAGIXAI_RENDER_WORKFLOW_ID",
        "CHUMMER6_BROWSERACT_MAGIXAI_RENDER_WORKFLOW_QUERY",
        "CHUMMER6_BROWSERACT_MAGIXAI_RENDER_COMMAND",
        "CHUMMER6_BROWSERACT_MAGIXAI_RENDER_URL_TEMPLATE",
    ],
    "browseract_prompting_systems": [
        "CHUMMER6_BROWSERACT_PROMPTING_SYSTEMS_RENDER_WORKFLOW_ID",
        "CHUMMER6_BROWSERACT_PROMPTING_SYSTEMS_RENDER_WORKFLOW_QUERY",
        "CHUMMER6_BROWSERACT_PROMPTING_SYSTEMS_REFINE_WORKFLOW_ID",
        "CHUMMER6_BROWSERACT_PROMPTING_SYSTEMS_REFINE_WORKFLOW_QUERY",
        "CHUMMER6_BROWSERACT_PROMPTING_SYSTEMS_RENDER_COMMAND",
        "CHUMMER6_BROWSERACT_PROMPTING_SYSTEMS_RENDER_URL_TEMPLATE",
        "CHUMMER6_BROWSERACT_PROMPTING_SYSTEMS_REFINE_COMMAND",
        "CHUMMER6_BROWSERACT_PROMPTING_SYSTEMS_REFINE_URL_TEMPLATE",
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
        return ["browseract_magixai", "magixai", "onemin"]
    values = [part.strip().lower() for part in raw.split(",") if part.strip()]
    filtered = [value for value in values if value not in {"local_raster", "markupgo", "ooda_compositor", "scene_contract_renderer", "pollinations"}]
    return filtered or ["browseract_magixai", "magixai", "onemin"]


def provider_state(name: str) -> dict[str, object]:
    if name == "pollinations":
        return {
            "provider": name,
            "status": "disabled",
            "available": False,
            "raw_keys": [],
            "adapters": [],
            "detail": "Disabled. Chummer6 media must use real external render lanes.",
        }
    if name == "local_raster":
        return {
            "provider": name,
            "status": "disabled",
            "available": False,
            "raw_keys": [],
            "adapters": [],
            "detail": "Disabled. Chummer6 media must use a real provider.",
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
        helper_ready = (EA_ROOT / "scripts" / "chummer6_browseract_prompting_systems.py").exists()
        effective_adapters = list(adapters)
        if helper_ready and "built_in_browseract_helper" not in effective_adapters:
            effective_adapters.append("built_in_browseract_helper")
        explicit_workflow = bool(env_value("CHUMMER6_BROWSERACT_PROMPTING_SYSTEMS_REFINE_WORKFLOW_ID"))
        available = browseract_ready and helper_ready and explicit_workflow
        if available:
            status = "ready"
            detail = "BrowserAct is configured and a Prompting Systems refine workflow is explicitly configured."
        elif browseract_ready and helper_ready:
            status = "workflow_query_only"
            detail = "BrowserAct and the helper are configured, but no explicit Prompting Systems workflow ID is set yet."
        elif browseract_ready:
            status = "browseract_ready_missing_render_adapter"
            detail = "BrowserAct is configured, but no Prompting Systems workflow/adapter is configured yet."
        else:
            status = "missing_browseract"
            detail = "No BrowserAct key found in EA env."
        return {"provider": name, "status": status, "available": available, "raw_keys": key_names_present(RAW_KEY_NAMES.get('browseract', [])), "adapters": effective_adapters, "detail": detail}
    if name == "browseract_magixai":
        browseract_ready = bool(key_names_present(RAW_KEY_NAMES.get("browseract", [])))
        helper_ready = (EA_ROOT / "scripts" / "chummer6_browseract_prompting_systems.py").exists()
        effective_adapters = list(adapters)
        if helper_ready and "built_in_browseract_helper" not in effective_adapters:
            effective_adapters.append("built_in_browseract_helper")
        explicit_workflow = bool(env_value("CHUMMER6_BROWSERACT_MAGIXAI_RENDER_WORKFLOW_ID"))
        available = browseract_ready and helper_ready and explicit_workflow
        if available:
            status = "ready"
            detail = "BrowserAct is configured and an AI Magicx render workflow is explicitly configured."
        elif browseract_ready and helper_ready:
            status = "workflow_query_only"
            detail = "BrowserAct and the helper are configured, but no explicit AI Magicx render workflow ID is set yet."
        elif browseract_ready:
            status = "browseract_ready_missing_render_adapter"
            detail = "BrowserAct is configured, but no AI Magicx render workflow/adapter is configured yet."
        else:
            status = "missing_browseract"
            detail = "No BrowserAct key found in EA env."
        return {"provider": name, "status": status, "available": available, "raw_keys": key_names_present(RAW_KEY_NAMES.get('browseract', [])), "adapters": effective_adapters, "detail": detail}
    if name == "magixai":
        available = bool(raw_keys or adapters)
        if available and raw_keys:
            status = "experimental_ready"
            detail = "AI Magicx credentials are present and the built-in API lane will be tried."
        else:
            status = "not_configured"
            detail = "No AI Magicx credentials found."
        return {"provider": name, "status": status, "available": available, "raw_keys": raw_keys, "adapters": adapters, "detail": detail}
    if name == "onemin":
        available = bool(raw_keys or adapters)
        if raw_keys:
            status = "ready"
            detail = "Built-in 1min.AI image generation is available."
        elif adapters:
            status = "ready"
            detail = "A custom 1min render adapter is configured."
        else:
            status = "not_configured"
            detail = "No 1min.AI credentials or render adapter found."
        return {"provider": name, "status": status, "available": available, "raw_keys": raw_keys, "adapters": adapters, "detail": detail}
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
        "recommended_provider": next((row["provider"] for row in states if row["available"]), ""),
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


def compact(value: object, *, limit: int = 180) -> str:
    text = " ".join(str(value or "").split()).strip()
    if not text:
        return ""
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip(" ,;:-") + "..."


def short_sentence(value: object, *, limit: int = 180) -> str:
    text = compact(value, limit=max(limit * 2, 180))
    for splitter in (". ", "! ", "? ", ": "):
        head, sep, _ = text.partition(splitter)
        if sep and head.strip():
            text = head.strip()
            break
    return compact(text, limit=limit)


def load_media_overrides() -> dict[str, object]:
    if not OVERRIDE_PATH.exists():
        return {}
    try:
        loaded = json.loads(OVERRIDE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def to_list(value: object, *, limit: int = 6) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for entry in value:
        cleaned = compact(entry, limit=72)
        if cleaned:
            result.append(cleaned)
        if len(result) >= limit:
            break
    return result


def keyword_hits(*values: object) -> set[str]:
    lowered = " ".join(str(value or "").lower() for value in values)
    tags: set[str] = set()
    for token, label in (
        ("x-ray", "xray"),
        ("xray", "xray"),
        ("scan", "xray"),
        ("simulation", "simulation"),
        ("sim", "simulation"),
        ("alice", "simulation"),
        ("ghost", "ghost"),
        ("replay", "ghost"),
        ("forensic", "ghost"),
        ("dossier", "dossier"),
        ("evidence", "dossier"),
        ("forge", "forge"),
        ("anvil", "forge"),
        ("heat web", "network"),
        ("network", "network"),
        ("thread", "network"),
        ("conflict", "network"),
        ("mirror", "mirror"),
        ("passport", "passport"),
        ("travel", "passport"),
        ("blackbox", "blackbox"),
        ("loadout", "blackbox"),
        ("map", "map"),
        ("table", "table"),
        ("team", "table"),
        ("runner", "person"),
        ("woman", "woman"),
        ("girl", "woman"),
        ("troll", "troll"),
        ("cyberdeck", "deck"),
        ("commlink", "deck"),
        ("sr4", "sr"),
        ("sr5", "sr"),
        ("sr6", "sr"),
    ):
        if token in lowered:
            tags.add(label)
    return tags


def theme_for(seed: str, palette_hint: str = "") -> tuple[str, str, str]:
    palette_text = str(palette_hint or "").lower()
    if "amber" in palette_text or "orange" in palette_text:
        palettes = [("#120914", "#ffb347", "#ff4f8b"), ("#180b08", "#ffb454", "#ff784f")]
    elif "green" in palette_text:
        palettes = [("#081310", "#4dff8f", "#16f2d1"), ("#10180c", "#8cff4d", "#38f7c8")]
    elif "purple" in palette_text or "violet" in palette_text:
        palettes = [("#120c1e", "#a855f7", "#60a5fa"), ("#14091e", "#c084fc", "#38bdf8")]
    else:
        palettes = [
            ("#0b1020", "#18f0ff", "#ff2f92"),
            ("#0f0d1a", "#7bff5b", "#2ee6ff"),
            ("#120914", "#ffcc33", "#ff4f8b"),
            ("#08141a", "#76ffd1", "#4fb3ff"),
        ]
    digest = hashlib.sha256((seed + "|" + palette_text).encode("utf-8")).hexdigest()
    return palettes[int(digest[:2], 16) % len(palettes)]


def default_scene_contract(prompt: str, *, title: str = "Chummer6") -> dict[str, object]:
    hits = keyword_hits(prompt, title)
    subject = "a cyberpunk runner"
    if "woman" in hits:
        subject = "a sharp-eyed cyberpunk woman"
    elif "troll" in hits:
        subject = "a cybernetic troll"
    elif "table" in hits:
        subject = "a runner team at a table"
    metaphor = "guide chrome"
    for key, value in (
        ("xray", "x-ray causality scan"),
        ("simulation", "branching simulation grid"),
        ("ghost", "forensic replay echoes"),
        ("dossier", "dossier evidence wall"),
        ("forge", "forge sparks and molten rules"),
        ("network", "living consequence web"),
        ("mirror", "mirror split"),
        ("passport", "passport gate"),
        ("blackbox", "blackbox loadout check"),
        ("map", "street map lattice"),
    ):
        if key in hits:
            metaphor = value
            break
    composition = "single_protagonist"
    if "table" in hits:
        composition = "group_table"
    elif "dossier" in hits or "blackbox" in hits:
        composition = "desk_still_life"
    props = ["neon HUD", "rain haze", "glitch reflections"]
    if "deck" in hits:
        props.insert(0, "battered cyberdeck")
    if "sr" in hits:
        props.append("rule stack shards")
    overlays = ["signal traces", "probability arcs", "receipt markers"]
    return {
        "subject": subject,
        "environment": "a dangerous but inviting cyberpunk scene",
        "action": "studying the next move before the chrome starts smoking",
        "metaphor": metaphor,
        "props": props[:6],
        "overlays": overlays[:4],
        "composition": composition,
        "palette": "cyan-magenta neon",
        "mood": "dangerous, curious, and slightly amused",
        "humor": "the dev may still deserve a little heat",
        "visual_prompt": compact(prompt, limit=360),
    }


def detect_metaphor(*values: object) -> str:
    hits = keyword_hits(*values)
    for key, value in (
        ("xray", "x-ray causality scan"),
        ("simulation", "branching simulation grid"),
        ("ghost", "forensic replay echoes"),
        ("dossier", "dossier evidence wall"),
        ("forge", "forge sparks and molten rules"),
        ("network", "living consequence web"),
        ("mirror", "mirror split"),
        ("passport", "passport gate"),
        ("blackbox", "blackbox loadout check"),
        ("map", "street map lattice"),
        ("table", "shared table state"),
    ):
        if key in hits:
            return value
    return "cyberpunk analysis overlay"


def normalize_scene_contract(raw: object, *, prompt: str, title: str) -> dict[str, object]:
    default = default_scene_contract(prompt, title=title)
    if not isinstance(raw, dict):
        return default
    merged = dict(default)
    for key in ("subject", "environment", "action", "metaphor", "composition", "palette", "mood", "humor", "visual_prompt"):
        value = compact(raw.get(key, ""), limit=220 if key != "visual_prompt" else 360)
        if value:
            merged[key] = value
    props = to_list(raw.get("props"), limit=6)
    overlays = to_list(raw.get("overlays"), limit=5)
    if props:
        merged["props"] = props
    if overlays:
        merged["overlays"] = overlays
    if not compact(merged.get("metaphor", "")):
        merged["metaphor"] = detect_metaphor(prompt, title, merged.get("subject", ""), merged.get("environment", ""))
    return merged


def page_scene_contract(page_id: str, page_row: dict[str, object], ooda_row: dict[str, object], *, composition_hint: str) -> dict[str, object]:
    act = ooda_row.get("act") if isinstance(ooda_row.get("act"), dict) else {}
    observe = ooda_row.get("observe") if isinstance(ooda_row.get("observe"), dict) else {}
    orient = ooda_row.get("orient") if isinstance(ooda_row.get("orient"), dict) else {}
    decide = ooda_row.get("decide") if isinstance(ooda_row.get("decide"), dict) else {}
    base = default_scene_contract(
        " ".join(
            part
            for part in [
                page_row.get("intro", ""),
                page_row.get("body", ""),
                act.get("visual_prompt_seed", ""),
                orient.get("focal_subject", ""),
                orient.get("scene_logic", ""),
            ]
            if part
        ),
        title=compact(page_row.get("intro", ""), limit=64) or page_id.replace("_", " ").title(),
    )
    base["subject"] = compact(orient.get("focal_subject", ""), limit=120) or base["subject"]
    base["environment"] = compact(orient.get("scene_logic", ""), limit=160) or compact(page_row.get("body", ""), limit=160) or base["environment"]
    base["action"] = compact(act.get("paragraph_seed", ""), limit=160) or compact(act.get("one_liner", ""), limit=160) or base["action"]
    base["metaphor"] = detect_metaphor(
        act.get("visual_prompt_seed", ""),
        page_row.get("intro", ""),
        page_row.get("body", ""),
        page_id,
    )
    base["props"] = to_list(observe.get("concrete_signals"), limit=5) or to_list(observe.get("likely_interest"), limit=5) or base["props"]
    overlay_values = to_list(decide.get("overlay_priority"), limit=1) + to_list(observe.get("likely_interest"), limit=3)
    base["overlays"] = overlay_values[:4] if overlay_values else base["overlays"]
    base["composition"] = composition_hint
    base["palette"] = compact(orient.get("visual_devices", ""), limit=80) or base["palette"]
    base["mood"] = compact(orient.get("emotional_goal", ""), limit=120) or base["mood"]
    base["humor"] = compact(orient.get("tone_rule", ""), limit=120) or base["humor"]
    return base


def merge_scene_row(base: dict[str, object], row: dict[str, object], *, prompt: str) -> dict[str, object]:
    merged = dict(base)
    for key in ("badge", "title", "subtitle", "kicker", "note", "meta", "overlay_hint"):
        value = compact(row.get(key, ""), limit=120 if key not in {"subtitle", "note"} else 180)
        if value:
            merged[key] = value
    for key in ("visual_motifs", "overlay_callouts"):
        values = to_list(row.get(key), limit=6)
        if values:
            merged[key] = values
    merged["scene_contract"] = normalize_scene_contract(
        row.get("scene_contract"),
        prompt=prompt,
        title=str(merged.get("title", "Chummer6")),
    )
    return merged


def scene_for(output_name: str, prompt: str) -> dict[str, object]:
    name = output_name.lower()
    default = {
        "badge": "Chummer6",
        "title": "Chummer6",
        "subtitle": "Same shadows. Bigger future. Less confusion.",
        "kicker": "Guide art",
        "note": "Fresh chrome for the guide wall.",
        "meta": "",
        "overlay_hint": "diegetic analysis overlay",
        "visual_motifs": [],
        "overlay_callouts": [],
        "scene_contract": default_scene_contract(prompt, title="Chummer6"),
    }
    loaded = load_media_overrides()
    media = loaded.get("media") if isinstance(loaded, dict) else None
    pages = loaded.get("pages") if isinstance(loaded, dict) else None
    section_ooda = loaded.get("section_ooda") if isinstance(loaded, dict) else None
    page_ooda = section_ooda.get("pages") if isinstance(section_ooda, dict) else None

    def page_scene(page_id: str, *, fallback_badge: str, fallback_title: str, fallback_kicker: str, composition_hint: str) -> dict[str, object]:
        if not isinstance(pages, dict) or not isinstance(page_ooda, dict):
            raise RuntimeError(f"missing page media context for {output_name}")
        page_row = pages.get(page_id)
        ooda_row = page_ooda.get(page_id)
        if not isinstance(page_row, dict) or not isinstance(ooda_row, dict):
            raise RuntimeError(f"missing page media context for {output_name}")
        scene = dict(default)
        act = ooda_row.get("act") if isinstance(ooda_row.get("act"), dict) else {}
        scene["badge"] = compact(page_row.get("kicker", ""), limit=72) or fallback_badge
        scene["title"] = compact(act.get("one_liner", ""), limit=72) or compact(page_row.get("intro", ""), limit=72) or fallback_title
        scene["subtitle"] = compact(page_row.get("intro", ""), limit=180) or scene["subtitle"]
        scene["kicker"] = compact(act.get("paragraph_seed", ""), limit=120) or fallback_kicker
        scene["note"] = short_sentence(page_row.get("body", "") or page_row.get("kicker", ""), limit=180) or scene["note"]
        scene["overlay_hint"] = compact((ooda_row.get("decide") or {}).get("overlay_priority", ""), limit=80) or compact((ooda_row.get("orient") or {}).get("visual_devices", ""), limit=80) or scene["overlay_hint"]
        scene["visual_motifs"] = to_list((ooda_row.get("observe") or {}).get("likely_interest"), limit=5) or to_list((ooda_row.get("observe") or {}).get("concrete_signals"), limit=5)
        scene["overlay_callouts"] = to_list((ooda_row.get("observe") or {}).get("concrete_signals"), limit=4) or to_list((ooda_row.get("observe") or {}).get("likely_interest"), limit=4)
        scene["scene_contract"] = page_scene_contract(page_id, page_row, ooda_row, composition_hint=composition_hint)
        return scene

    page_targets = {
        "poc-warning.png": ("readme", "POC", "Test Dummy Drop", "Try the rough build", "desk_still_life"),
        "start-here.png": ("start_here", "Start", "Start Here", "Get your bearings fast", "city_edge"),
        "what-chummer6-is.png": ("what_chummer6_is", "Guide", "What Chummer6 Is", "The lay of the land", "single_protagonist"),
        "where-to-go-deeper.png": ("where_to_go_deeper", "Deeper", "Go Deeper", "Blueprints and code paths", "archive_room"),
        "current-phase.png": ("current_phase", "Now", "Current Phase", "Foundation work first", "workshop"),
        "current-status.png": ("current_status", "Now", "Current Status", "What is visible right now", "street_front"),
        "public-surfaces.png": ("public_surfaces", "Preview", "Public Surfaces", "Visible, but still settling", "street_front"),
        "parts-index.png": ("parts_index", "Parts", "Meet the Parts", "How the machine breaks down", "district_map"),
        "horizons-index.png": ("horizons_index", "Horizons", "Future Rabbit Holes", "The dangerous fun stuff", "city_edge"),
    }
    if name in page_targets:
        page_id, badge, title, kicker, composition = page_targets[name]
        return page_scene(page_id, fallback_badge=badge, fallback_title=title, fallback_kicker=kicker, composition_hint=composition)
    if isinstance(media, dict):
        if name == "chummer6-hero.png":
            hero = media.get("hero")
            if isinstance(hero, dict):
                return merge_scene_row(default, hero, prompt=prompt)
        parts = media.get("parts")
        if isinstance(parts, dict):
            slug = name.removesuffix(".png")
            row = parts.get(slug)
            if isinstance(row, dict):
                return merge_scene_row(default, row, prompt=prompt)
        horizons = media.get("horizons")
        if isinstance(horizons, dict):
            slug = name.removesuffix(".png")
            row = horizons.get(slug)
            if isinstance(row, dict):
                return merge_scene_row(default, row, prompt=prompt)
    raise RuntimeError(f"missing media context for {output_name}")


def css_escape(value: object) -> str:
    return html.escape(str(value or ""), quote=True)


def chips_html(values: list[str], *, kind: str) -> str:
    return "".join(
        f'<span class="chip {kind}">{css_escape(value)}</span>'
        for value in values[:4]
        if str(value).strip()
    )


def motif_classes(contract: dict[str, object]) -> set[str]:
    return keyword_hits(
        contract.get("subject", ""),
        contract.get("environment", ""),
        contract.get("action", ""),
        contract.get("metaphor", ""),
        " ".join(str(entry) for entry in contract.get("props", [])),
        " ".join(str(entry) for entry in contract.get("overlays", [])),
        contract.get("composition", ""),
        contract.get("palette", ""),
    )


def figure_html(kind: set[str]) -> str:
    if "table" in kind:
        return '''
        <div class="table-scene">
          <div class="table-top"></div>
          <div class="figure crew left"><span class="head"></span><span class="body"></span></div>
          <div class="figure crew center"><span class="head"></span><span class="body"></span></div>
          <div class="figure crew right"><span class="head"></span><span class="body"></span></div>
        </div>
        '''
    if "troll" in kind:
        return '''
        <div class="figure troll">
          <span class="head"></span><span class="body"></span><span class="arm left"></span><span class="arm right"></span>
        </div>
        '''
    person_class = "woman" if "woman" in kind else "runner"
    return f'''
    <div class="figure {person_class}">
      <span class="head"></span><span class="body"></span><span class="arm left"></span><span class="arm right"></span>
    </div>
    '''


def metaphor_html(kind: set[str]) -> str:
    blocks: list[str] = []
    if "xray" in kind:
        blocks.append(
            '''
            <div class="metaphor xray">
              <span class="scan ring one"></span><span class="scan ring two"></span>
              <span class="rib a"></span><span class="rib b"></span><span class="rib c"></span>
              <span class="spine"></span>
            </div>
            '''
        )
    if "simulation" in kind:
        blocks.append(
            '''
            <div class="metaphor simulation">
              <span class="grid-ring a"></span><span class="grid-ring b"></span><span class="grid-ring c"></span>
              <span class="branch one"></span><span class="branch two"></span><span class="branch three"></span>
            </div>
            '''
        )
    if "ghost" in kind:
        blocks.append(
            '''
            <div class="metaphor ghost">
              <span class="echo one"></span><span class="echo two"></span><span class="echo three"></span>
            </div>
            '''
        )
    if "dossier" in kind:
        blocks.append(
            '''
            <div class="metaphor dossier">
              <span class="sheet one"></span><span class="sheet two"></span><span class="sheet three"></span>
              <span class="string"></span>
            </div>
            '''
        )
    if "forge" in kind:
        blocks.append(
            '''
            <div class="metaphor forge">
              <span class="anvil"></span>
              <span class="spark a"></span><span class="spark b"></span><span class="spark c"></span><span class="spark d"></span>
            </div>
            '''
        )
    if "network" in kind or "map" in kind:
        blocks.append(
            '''
            <div class="metaphor network">
              <span class="node a"></span><span class="node b"></span><span class="node c"></span><span class="node d"></span>
              <span class="link ab"></span><span class="link bc"></span><span class="link cd"></span><span class="link ad"></span>
            </div>
            '''
        )
    if "mirror" in kind or "passport" in kind:
        blocks.append(
            '''
            <div class="metaphor split">
              <span class="panel left"></span><span class="panel right"></span><span class="divider"></span>
            </div>
            '''
        )
    if "blackbox" in kind:
        blocks.append(
            '''
            <div class="metaphor blackbox">
              <span class="crate"></span><span class="warning one"></span><span class="warning two"></span><span class="warning three"></span>
            </div>
            '''
        )
    return "".join(blocks)


def diagram_html(scene: dict[str, object], *, kind: str) -> str:
    labels = to_list(scene.get("visual_motifs"), limit=6) or to_list(scene.get("overlay_callouts"), limit=6)
    if kind == "status_strip":
        columns = labels[:3] or ["Now", "Preview", "Horizon"]
        tiles = "".join(
            f'<div class="status-tile"><div class="status-title">{css_escape(label)}</div></div>'
            for label in columns
        )
        return f'<div class="status-strip">{tiles}</div>'
    nodes = labels[:6] or ["Core", "UI", "Play", "Hub", "Registry", "Media"]
    cards = "".join(
        f'<div class="map-node">{css_escape(label)}</div>'
        for label in nodes
    )
    return f'<div class="program-map">{cards}</div>'


def composition_html(composition: str, kind: set[str]) -> str:
    if composition == "city_edge":
        return '''
        <div class="setpiece city-edge">
          <span class="skyline one"></span><span class="skyline two"></span><span class="skyline three"></span>
          <span class="street"></span><span class="street-glow"></span>
        </div>
        '''
    if composition == "archive_room":
        return '''
        <div class="setpiece archive-room">
          <span class="shelf left"></span><span class="shelf right"></span><span class="door"></span>
          <span class="aisle-glow"></span>
        </div>
        '''
    if composition == "workshop":
        return '''
        <div class="setpiece workshop">
          <span class="bench"></span><span class="lamp one"></span><span class="lamp two"></span>
          <span class="spark-tray"></span>
        </div>
        '''
    if composition == "street_front":
        return '''
        <div class="setpiece street-front">
          <span class="pane left"></span><span class="pane center"></span><span class="pane right"></span>
          <span class="awning"></span>
        </div>
        '''
    if composition == "district_map":
        return '''
        <div class="setpiece district-map">
          <span class="block a"></span><span class="block b"></span><span class="block c"></span><span class="block d"></span>
          <span class="lane one"></span><span class="lane two"></span>
        </div>
        '''
    if composition == "desk_still_life":
        return '''
        <div class="setpiece desk-still-life">
          <span class="desk"></span><span class="card one"></span><span class="card two"></span><span class="card three"></span>
          <span class="warning"></span>
        </div>
        '''
    if composition == "group_table":
        return '<div class="setpiece group-table"><span class="halo"></span></div>'
    return '''
    <div class="setpiece single-protagonist">
      <span class="frame left"></span><span class="frame right"></span><span class="beam"></span>
    </div>
    '''


def build_html(prompt: str, output_name: str, *, width: int, height: int) -> str:
    scene = scene_for(output_name, prompt)
    contract = scene.get("scene_contract") if isinstance(scene.get("scene_contract"), dict) else default_scene_contract(prompt)
    classes = motif_classes(contract)
    bg, accent_a, accent_b = theme_for(
        prompt + "|" + json.dumps(contract, ensure_ascii=True, sort_keys=True),
        palette_hint=str(contract.get("palette", "")),
    )
    composition = str(contract.get("composition", "single_protagonist")).strip() or "single_protagonist"
    setpiece = composition_html(composition, classes)
    figures = figure_html(classes) if composition not in {"desk_still_life", "archive_room", "district_map"} or {"woman", "runner", "troll", "table"} & classes else ""
    metaphors = metaphor_html(classes)
    return f'''<!doctype html>
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
        radial-gradient(circle at 20% 20%, {accent_a}22 0, transparent 22%),
        radial-gradient(circle at 82% 18%, {accent_b}20 0, transparent 24%),
        linear-gradient(140deg, {bg} 0%, #060913 58%, #03060d 100%);
      color: #f5f7fb;
    }}
    .stage {{
      position: relative;
      width: 100%;
      height: 100%;
      overflow: hidden;
    }}
    .scan {{
      position: absolute;
      inset: 0;
      background-image:
        linear-gradient(rgba(255,255,255,0.04) 1px, transparent 1px),
        linear-gradient(90deg, rgba(255,255,255,0.03) 1px, transparent 1px);
      background-size: 48px 48px;
      opacity: 0.55;
      mask-image: linear-gradient(to bottom, rgba(0,0,0,0.85), transparent);
    }}
    .glow {{
      position: absolute;
      inset: auto auto -18% -8%;
      width: 48%;
      height: 60%;
      border-radius: 999px;
      background: radial-gradient(circle, {accent_a}44 0, transparent 68%);
      filter: blur(24px);
      opacity: 0.7;
    }}
    .glow.two {{
      inset: -16% -10% auto auto;
      width: 42%;
      height: 48%;
      background: radial-gradient(circle, {accent_b}3a 0, transparent 70%);
    }}
    .scene {{
      position: absolute;
      inset: 0;
    }}
    .setpiece {{
      position: absolute;
      inset: 0;
      pointer-events: none;
    }}
    .setpiece.city-edge .skyline,
    .setpiece.archive-room .shelf,
    .setpiece.street-front .pane,
    .setpiece.district-map .block,
    .setpiece.desk-still-life .card,
    .setpiece.single-protagonist .frame {{
      position: absolute;
      border-radius: 18px;
      border: 1px solid rgba(255,255,255,0.12);
      background: linear-gradient(180deg, rgba(255,255,255,0.08), rgba(255,255,255,0.02));
      box-shadow: 0 18px 28px rgba(0,0,0,0.24);
    }}
    .setpiece.city-edge .skyline.one {{ left: 52%; top: 18%; width: 10%; height: 38%; }}
    .setpiece.city-edge .skyline.two {{ left: 64%; top: 11%; width: 13%; height: 50%; }}
    .setpiece.city-edge .skyline.three {{ left: 79%; top: 22%; width: 9%; height: 34%; }}
    .setpiece.city-edge .street {{
      position: absolute; left: 0; right: 0; bottom: -2%; height: 28%;
      background: linear-gradient(180deg, rgba(6,10,18,0), rgba(2,4,10,0.96));
      clip-path: polygon(22% 0, 78% 0, 100% 100%, 0 100%);
    }}
    .setpiece.city-edge .street-glow {{
      position: absolute; left: 36%; bottom: 10%; width: 28%; height: 3px;
      background: linear-gradient(90deg, transparent, {accent_a}, transparent);
      box-shadow: 0 0 16px {accent_a};
    }}
    .setpiece.archive-room .shelf.left {{ left: 8%; top: 16%; width: 16%; height: 58%; }}
    .setpiece.archive-room .shelf.right {{ right: 8%; top: 16%; width: 16%; height: 58%; }}
    .setpiece.archive-room .door {{
      position: absolute; left: 39%; top: 18%; width: 22%; height: 54%;
      border-radius: 22px; border: 1px solid rgba(255,255,255,0.16);
      background: linear-gradient(180deg, rgba(255,255,255,0.10), rgba(255,255,255,0.03));
    }}
    .setpiece.archive-room .aisle-glow {{
      position: absolute; left: 41%; top: 28%; width: 18%; height: 32%;
      background: radial-gradient(circle, {accent_b}44 0, transparent 72%);
      filter: blur(16px);
    }}
    .setpiece.workshop .bench {{
      position: absolute; left: 12%; right: 12%; bottom: 14%; height: 18%;
      border-radius: 28px; border: 1px solid rgba(255,255,255,0.14);
      background: linear-gradient(180deg, rgba(255,255,255,0.10), rgba(255,255,255,0.03));
    }}
    .setpiece.workshop .lamp {{
      position: absolute; top: 4%; width: 3px; height: 24%; background: rgba(255,255,255,0.16);
    }}
    .setpiece.workshop .lamp.one {{ left: 34%; }}
    .setpiece.workshop .lamp.two {{ left: 66%; }}
    .setpiece.workshop .spark-tray {{
      position: absolute; left: 44%; bottom: 20%; width: 12%; height: 12%;
      background: radial-gradient(circle, {accent_b}55 0, transparent 70%);
      filter: blur(10px);
    }}
    .setpiece.street-front .pane.left {{ left: 10%; top: 18%; width: 18%; height: 48%; }}
    .setpiece.street-front .pane.center {{ left: 33%; top: 14%; width: 26%; height: 54%; }}
    .setpiece.street-front .pane.right {{ right: 10%; top: 20%; width: 18%; height: 44%; }}
    .setpiece.street-front .awning {{
      position: absolute; left: 30%; top: 10%; width: 32%; height: 8%;
      border-radius: 999px; background: linear-gradient(90deg, {accent_a}, {accent_b});
      opacity: 0.22; filter: blur(6px);
    }}
    .setpiece.district-map .block.a {{ left: 16%; top: 24%; width: 14%; height: 24%; }}
    .setpiece.district-map .block.b {{ left: 34%; top: 18%; width: 18%; height: 34%; }}
    .setpiece.district-map .block.c {{ left: 57%; top: 28%; width: 16%; height: 22%; }}
    .setpiece.district-map .block.d {{ left: 74%; top: 20%; width: 10%; height: 30%; }}
    .setpiece.district-map .lane {{
      position: absolute; height: 3px; background: linear-gradient(90deg, {accent_a}, transparent);
      box-shadow: 0 0 10px {accent_a}; transform-origin: left center;
    }}
    .setpiece.district-map .lane.one {{ left: 28%; top: 42%; width: 28%; transform: rotate(-8deg); }}
    .setpiece.district-map .lane.two {{ left: 49%; top: 38%; width: 24%; transform: rotate(12deg); }}
    .setpiece.desk-still-life .desk {{
      position: absolute; left: 8%; right: 8%; bottom: 8%; height: 24%;
      border-radius: 26px; border: 1px solid rgba(255,255,255,0.14);
      background: linear-gradient(180deg, rgba(255,255,255,0.08), rgba(255,255,255,0.02));
    }}
    .setpiece.desk-still-life .card.one {{ left: 22%; top: 30%; width: 16%; height: 24%; transform: rotate(-10deg); }}
    .setpiece.desk-still-life .card.two {{ left: 42%; top: 22%; width: 18%; height: 26%; transform: rotate(6deg); }}
    .setpiece.desk-still-life .card.three {{ left: 62%; top: 31%; width: 15%; height: 22%; transform: rotate(-4deg); }}
    .setpiece.desk-still-life .warning {{
      position: absolute; left: 48%; top: 38%; width: 12%; height: 12%;
      border-radius: 999px; background: {accent_b}; box-shadow: 0 0 16px {accent_b};
    }}
    .setpiece.group-table .halo {{
      position: absolute; left: 20%; top: 30%; width: 46%; height: 24%;
      border-radius: 999px; border: 1px solid {accent_a}66;
      box-shadow: 0 0 18px {accent_a};
    }}
    .setpiece.single-protagonist .frame.left {{ left: 10%; top: 20%; width: 8%; height: 50%; }}
    .setpiece.single-protagonist .frame.right {{ right: 10%; top: 18%; width: 10%; height: 54%; }}
    .setpiece.single-protagonist .beam {{
      position: absolute; left: 48%; top: 0; width: 4px; height: 72%;
      background: linear-gradient(180deg, {accent_b}, transparent);
      opacity: 0.26;
    }}
    .figure {{
      position: absolute;
      left: 18%;
      bottom: 16%;
      width: 18%;
      height: 54%;
      filter: drop-shadow(0 18px 28px rgba(0,0,0,0.45));
    }}
    .figure .head {{
      position: absolute;
      left: 31%;
      top: 4%;
      width: 38%;
      height: 18%;
      border-radius: 999px;
      background: linear-gradient(180deg, rgba(255,255,255,0.42), rgba(255,255,255,0.08));
      border: 1px solid rgba(255,255,255,0.22);
    }}
    .figure .body {{
      position: absolute;
      left: 24%;
      top: 19%;
      width: 52%;
      height: 46%;
      border-radius: 28px 28px 20px 20px;
      background: linear-gradient(180deg, rgba(255,255,255,0.16), rgba(255,255,255,0.03));
      border: 1px solid rgba(255,255,255,0.18);
    }}
    .figure .arm {{
      position: absolute;
      top: 28%;
      width: 16%;
      height: 28%;
      border-radius: 16px;
      background: linear-gradient(180deg, rgba(255,255,255,0.12), rgba(255,255,255,0.02));
      border: 1px solid rgba(255,255,255,0.12);
    }}
    .figure .arm.left {{ left: 10%; transform: rotate(16deg); }}
    .figure .arm.right {{ right: 10%; transform: rotate(-16deg); }}
    .figure.runner::after {{
      content: "";
      position: absolute;
      left: 18%;
      top: 14%;
      width: 64%;
      height: 18%;
      border-radius: 999px;
      background: linear-gradient(90deg, transparent 0, {accent_a}88 32%, transparent 100%);
      filter: blur(10px);
      opacity: 0.85;
    }}
    .figure.woman::before {{
      content: "";
      position: absolute;
      left: 16%;
      top: 2%;
      width: 68%;
      height: 24%;
      border-radius: 48% 48% 56% 56%;
      background: linear-gradient(180deg, {accent_b}88, rgba(255,255,255,0.08));
      filter: blur(2px);
      opacity: 0.72;
    }}
    .figure.troll {{
      left: 14%;
      width: 24%;
      height: 58%;
    }}
    .table-scene {{
      position: absolute;
      left: 10%;
      bottom: 14%;
      width: 40%;
      height: 42%;
    }}
    .table-top {{
      position: absolute;
      left: 2%;
      right: 2%;
      bottom: 8%;
      height: 16%;
      border-radius: 32px;
      background: linear-gradient(180deg, rgba(255,255,255,0.16), rgba(255,255,255,0.04));
      border: 1px solid rgba(255,255,255,0.14);
    }}
    .figure.crew {{
      width: 18%;
      height: 62%;
      bottom: 18%;
    }}
    .figure.crew.left {{ left: 0; }}
    .figure.crew.center {{ left: 38%; }}
    .figure.crew.right {{ left: 76%; }}
    .metaphor {{
      position: absolute;
      inset: 0;
      pointer-events: none;
    }}
    .metaphor.xray .scan.ring,
    .metaphor.simulation .grid-ring {{
      position: absolute;
      border-radius: 999px;
      border: 1px solid {accent_a}88;
      opacity: 0.72;
    }}
    .metaphor.xray .scan.ring.one {{ left: 20%; top: 18%; width: 26%; height: 36%; }}
    .metaphor.xray .scan.ring.two {{ left: 16%; top: 14%; width: 34%; height: 44%; border-color: {accent_b}66; }}
    .metaphor.xray .spine {{
      position: absolute;
      left: 31%;
      top: 28%;
      width: 4px;
      height: 30%;
      background: linear-gradient(180deg, rgba(255,255,255,0.1), {accent_a});
      box-shadow: 0 0 12px {accent_a};
    }}
    .metaphor.xray .rib {{
      position: absolute;
      width: 14%;
      height: 2px;
      left: 24%;
      background: linear-gradient(90deg, transparent, rgba(255,255,255,0.85), transparent);
    }}
    .metaphor.xray .rib.a {{ top: 34%; }}
    .metaphor.xray .rib.b {{ top: 39%; }}
    .metaphor.xray .rib.c {{ top: 44%; }}
    .metaphor.simulation .grid-ring.a {{ left: 18%; top: 18%; width: 30%; height: 40%; }}
    .metaphor.simulation .grid-ring.b {{ left: 15%; top: 14%; width: 36%; height: 48%; border-color: {accent_b}7a; }}
    .metaphor.simulation .grid-ring.c {{ left: 12%; top: 10%; width: 42%; height: 56%; border-color: rgba(255,255,255,0.28); }}
    .metaphor.simulation .branch {{
      position: absolute;
      width: 22%;
      height: 2px;
      background: linear-gradient(90deg, {accent_a}, transparent);
      transform-origin: left center;
    }}
    .metaphor.simulation .branch.one {{ left: 48%; top: 28%; transform: rotate(-18deg); }}
    .metaphor.simulation .branch.two {{ left: 48%; top: 38%; transform: rotate(4deg); }}
    .metaphor.simulation .branch.three {{ left: 48%; top: 48%; transform: rotate(20deg); }}
    .metaphor.ghost .echo {{
      position: absolute;
      left: 18%;
      top: 16%;
      width: 20%;
      height: 54%;
      border-radius: 28px;
      border: 1px solid rgba(255,255,255,0.16);
      background: linear-gradient(180deg, rgba(255,255,255,0.08), transparent);
    }}
    .metaphor.ghost .echo.one {{ opacity: 0.18; transform: translateX(0); }}
    .metaphor.ghost .echo.two {{ opacity: 0.12; transform: translateX(48px); }}
    .metaphor.ghost .echo.three {{ opacity: 0.08; transform: translateX(92px); }}
    .metaphor.dossier .sheet {{
      position: absolute;
      width: 18%;
      height: 26%;
      top: 20%;
      left: 58%;
      border-radius: 20px;
      border: 1px solid rgba(255,255,255,0.14);
      background: linear-gradient(180deg, rgba(255,255,255,0.11), rgba(255,255,255,0.03));
      box-shadow: 0 16px 24px rgba(0,0,0,0.28);
    }}
    .metaphor.dossier .sheet.one {{ transform: rotate(-8deg); }}
    .metaphor.dossier .sheet.two {{ transform: rotate(4deg) translateX(44px); }}
    .metaphor.dossier .sheet.three {{ transform: rotate(-2deg) translateX(88px); }}
    .metaphor.dossier .string {{
      position: absolute;
      left: 60%;
      top: 24%;
      width: 22%;
      height: 24%;
      border-left: 2px solid {accent_b};
      border-top: 2px solid {accent_b};
      transform: rotate(12deg);
    }}
    .metaphor.forge .anvil {{
      position: absolute;
      left: 22%;
      bottom: 18%;
      width: 24%;
      height: 12%;
      border-radius: 24px;
      background: linear-gradient(180deg, rgba(255,255,255,0.16), rgba(255,255,255,0.04));
      border: 1px solid rgba(255,255,255,0.14);
    }}
    .metaphor.forge .spark {{
      position: absolute;
      width: 10px;
      height: 10px;
      border-radius: 999px;
      background: {accent_b};
      box-shadow: 0 0 18px {accent_b};
    }}
    .metaphor.forge .spark.a {{ left: 42%; top: 28%; }}
    .metaphor.forge .spark.b {{ left: 46%; top: 24%; }}
    .metaphor.forge .spark.c {{ left: 50%; top: 30%; }}
    .metaphor.forge .spark.d {{ left: 48%; top: 18%; }}
    .metaphor.network .node {{
      position: absolute;
      width: 18px;
      height: 18px;
      border-radius: 999px;
      background: {accent_a};
      box-shadow: 0 0 16px {accent_a};
    }}
    .metaphor.network .node.a {{ left: 58%; top: 22%; }}
    .metaphor.network .node.b {{ left: 72%; top: 34%; }}
    .metaphor.network .node.c {{ left: 64%; top: 52%; }}
    .metaphor.network .node.d {{ left: 80%; top: 46%; }}
    .metaphor.network .link {{
      position: absolute;
      height: 2px;
      background: linear-gradient(90deg, {accent_a}, {accent_b});
      transform-origin: left center;
      opacity: 0.7;
    }}
    .metaphor.network .link.ab {{ left: 59%; top: 24%; width: 14%; transform: rotate(20deg); }}
    .metaphor.network .link.bc {{ left: 65%; top: 40%; width: 12%; transform: rotate(96deg); }}
    .metaphor.network .link.cd {{ left: 66%; top: 54%; width: 18%; transform: rotate(-16deg); }}
    .metaphor.network .link.ad {{ left: 60%; top: 28%; width: 24%; transform: rotate(34deg); }}
    .metaphor.split .panel {{
      position: absolute;
      top: 18%;
      width: 18%;
      height: 46%;
      border-radius: 24px;
      border: 1px solid rgba(255,255,255,0.14);
      background: linear-gradient(180deg, rgba(255,255,255,0.08), rgba(255,255,255,0.02));
    }}
    .metaphor.split .panel.left {{ left: 18%; }}
    .metaphor.split .panel.right {{ left: 52%; }}
    .metaphor.split .divider {{
      position: absolute;
      left: 48%;
      top: 14%;
      width: 2px;
      height: 56%;
      background: linear-gradient(180deg, transparent, {accent_b}, transparent);
    }}
    .metaphor.blackbox .crate {{
      position: absolute;
      left: 22%;
      bottom: 20%;
      width: 22%;
      height: 16%;
      border-radius: 18px;
      border: 1px solid rgba(255,255,255,0.16);
      background: linear-gradient(180deg, rgba(255,255,255,0.08), rgba(255,255,255,0.03));
      box-shadow: 0 14px 28px rgba(0,0,0,0.35);
    }}
    .metaphor.blackbox .warning {{
      position: absolute;
      width: 12px;
      height: 12px;
      border-radius: 999px;
      background: {accent_b};
      box-shadow: 0 0 12px {accent_b};
    }}
    .metaphor.blackbox .warning.one {{ left: 48%; top: 26%; }}
    .metaphor.blackbox .warning.two {{ left: 54%; top: 22%; }}
    .metaphor.blackbox .warning.three {{ left: 60%; top: 28%; }}
    .program-map {{
      position: absolute;
      inset: 18% 14% 18% 14%;
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 18px;
      align-content: center;
    }}
    .program-map .map-node,
    .status-strip .status-tile {{
      border-radius: 22px;
      border: 1px solid rgba(255,255,255,0.14);
      background: linear-gradient(180deg, rgba(255,255,255,0.08), rgba(255,255,255,0.02));
      backdrop-filter: blur(8px);
      padding: 20px 18px;
      box-shadow: 0 18px 30px rgba(0,0,0,0.24);
      font-size: 20px;
      line-height: 1.2;
      color: rgba(248,250,252,0.92);
      text-align: center;
    }}
    .status-strip {{
      position: absolute;
      inset: 30% 10% 24% 10%;
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 22px;
      align-items: stretch;
    }}
    .status-strip .status-title {{
      font-size: 22px;
      font-weight: 700;
      letter-spacing: -0.02em;
    }}
  </style>
</head>
<body>
  <div class="stage">
    <div class="scan"></div>
    <div class="glow"></div>
    <div class="glow two"></div>
    <div class="scene">
      {setpiece}
      {figures}
      {metaphors}
    </div>
  </div>
</body>
</html>
'''


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


def upsert_env_value(path: Path, key: str, value: str, *, only_if_missing: bool = False) -> None:
    if not path.exists():
        return
    current = path.read_text(encoding="utf-8")
    pattern = re.compile(rf"(?m)^{re.escape(key)}=.*$")
    replacement = f"{key}={value}"
    if pattern.search(current):
        if only_if_missing:
            return
        updated = pattern.sub(replacement, current, count=1)
    else:
        suffix = "" if current.endswith("\n") else "\n"
        updated = current + suffix + replacement + "\n"
    if updated != current:
        path.write_text(updated, encoding="utf-8")


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


BROWSERACT_PROMPTING_SYSTEMS_SCRIPT = """#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import time
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
    data = None
    headers = {
        "Authorization": f"Bearer {key}",
        "User-Agent": "EA-Chummer6-BrowserAct/1.0",
    }
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method.upper())
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            body = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"browseract:http_{exc.code}:{body[:240]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"browseract:urlerror:{exc.reason}") from exc
    try:
        loaded = json.loads(body)
    except Exception as exc:
        raise RuntimeError(f"browseract:non_json:{body[:240]}") from exc
    return loaded if isinstance(loaded, dict) else {"data": loaded}


def list_workflows() -> list[dict[str, object]]:
    body = api_request("GET", "/list-workflows")
    for key in ("workflows", "data", "items", "rows"):
        value = body.get(key)
        if isinstance(value, list):
            return [entry for entry in value if isinstance(entry, dict)]
    if isinstance(body, dict):
        return [body]
    return []


def workflow_fields(entry: dict[str, object]) -> tuple[str, str]:
    workflow_id = str(
        entry.get("workflow_id")
        or entry.get("id")
        or entry.get("_id")
        or entry.get("workflowId")
        or ""
    ).strip()
    name = str(entry.get("name") or entry.get("title") or entry.get("workflow_name") or "").strip()
    return workflow_id, name


def resolve_workflow(kind: str) -> tuple[str, str]:
    normalized = str(kind or "").strip().upper()
    key_prefixes = {
        "REFINE": "CHUMMER6_BROWSERACT_PROMPTING_SYSTEMS",
        "PROMPTING_RENDER": "CHUMMER6_BROWSERACT_PROMPTING_SYSTEMS",
        "MAGIXAI_RENDER": "CHUMMER6_BROWSERACT_MAGIXAI",
    }
    key_suffixes = {
        "REFINE": "REFINE",
        "PROMPTING_RENDER": "RENDER",
        "MAGIXAI_RENDER": "RENDER",
    }
    prefix = key_prefixes.get(normalized, "CHUMMER6_BROWSERACT_PROMPTING_SYSTEMS")
    suffix = key_suffixes.get(normalized, normalized)
    explicit = env_value(f"{prefix}_{suffix}_WORKFLOW_ID")
    if explicit:
        return explicit, "explicit"
    query = env_value(f"{prefix}_{suffix}_WORKFLOW_QUERY")
    default_queries = {
        "REFINE": [
            "chummer6 prompting systems refine",
            "prompting systems refine",
            "prompt refine",
        ],
        "PROMPTING_RENDER": [
            "chummer6 prompting systems render",
            "prompting systems render",
            "image render",
        ],
        "MAGIXAI_RENDER": [
            "chummer6 magicx render",
            "chummer6 ai magicx render",
            "magicx render",
            "aimagicx render",
        ],
    }
    queries = [query] if query else default_queries.get(normalized, [])
    workflows = list_workflows()
    for needle in queries:
        lowered = str(needle or "").strip().lower()
        if not lowered:
            continue
        for entry in workflows:
            workflow_id, name = workflow_fields(entry)
            haystack = " ".join(
                str(entry.get(field) or "")
                for field in ("name", "title", "description", "slug", "workflow_name")
            ).lower()
            if workflow_id and lowered in haystack:
                return workflow_id, name or lowered
    raise RuntimeError(f"browseract:{normalized.lower()}_workflow_not_found")


def _input_payloads(*, prompt: str, target: str, width: int, height: int, output_path: str) -> list[list[dict[str, object]]]:
    return [
        [
            {"name": "prompt", "value": prompt},
            {"name": "target", "value": target},
            {"name": "width", "value": width},
            {"name": "height", "value": height},
            {"name": "output_path", "value": output_path},
        ],
        [
            {"key": "prompt", "value": prompt},
            {"key": "target", "value": target},
            {"key": "width", "value": width},
            {"key": "height", "value": height},
            {"key": "output_path", "value": output_path},
        ],
        [
            {"prompt": prompt, "target": target, "width": width, "height": height, "output_path": output_path},
        ],
    ]


def run_task(*, workflow_id: str, prompt: str, target: str, width: int, height: int, output_path: str) -> dict[str, object]:
    last_error = "browseract:run_task_failed"
    for input_parameters in _input_payloads(prompt=prompt, target=target, width=width, height=height, output_path=output_path):
        try:
            return api_request(
                "POST",
                "/run-task",
                payload={"workflow_id": workflow_id, "input_parameters": input_parameters},
            )
        except RuntimeError as exc:
            last_error = str(exc)
            continue
    raise RuntimeError(last_error)


def _task_id(body: dict[str, object]) -> str:
    for key in ("task_id", "id", "_id"):
        value = str(body.get(key) or "").strip()
        if value:
            return value
    data = body.get("data")
    if isinstance(data, dict):
        for key in ("task_id", "id", "_id"):
            value = str(data.get(key) or "").strip()
            if value:
                return value
    raise RuntimeError("browseract:missing_task_id")


def _task_status(body: dict[str, object]) -> str:
    for key in ("status", "task_status", "state"):
        value = str(body.get(key) or "").strip()
        if value:
            return value.lower()
    data = body.get("data")
    if isinstance(data, dict):
        for key in ("status", "task_status", "state"):
            value = str(data.get(key) or "").strip()
            if value:
                return value.lower()
    return ""


def wait_for_task(task_id: str, *, timeout_seconds: int = 600) -> dict[str, object]:
    deadline = time.time() + max(30, int(timeout_seconds))
    last_status = ""
    while time.time() < deadline:
        status_body = api_request("GET", "/get-task-status", query={"task_id": task_id})
        status = _task_status(status_body)
        if status:
            last_status = status
        if status in {"done", "completed", "success", "succeeded"}:
            return api_request("GET", "/get-task", query={"task_id": task_id})
        if status in {"failed", "error", "cancelled", "canceled"}:
            detail = json.dumps(status_body, ensure_ascii=True)[:400]
            raise RuntimeError(f"browseract:task_failed:{detail}")
        time.sleep(5)
    raise RuntimeError(f"browseract:task_timeout:{last_status or 'unknown'}")


def _collect_strings(value: object) -> list[str]:
    found: list[str] = []
    if isinstance(value, str):
        normalized = str(value or "").strip()
        if normalized:
            found.append(normalized)
        return found
    if isinstance(value, dict):
        for nested in value.values():
            found.extend(_collect_strings(nested))
        return found
    if isinstance(value, (list, tuple, set)):
        for nested in value:
            found.extend(_collect_strings(nested))
    return found


def extract_refined_prompt(body: dict[str, object]) -> str:
    candidates = _collect_strings(body)
    scored = [
        value for value in candidates
        if len(value) > 40 and "http" not in value.lower() and not value.lower().startswith("task_")
    ]
    if scored:
        return max(scored, key=len)
    raise RuntimeError("browseract:no_refined_prompt")


def extract_image_url(body: dict[str, object]) -> str:
    for value in _collect_strings(body):
        if value.startswith("http://") or value.startswith("https://"):
            lowered = value.lower()
            if any(token in lowered for token in (".png", ".jpg", ".jpeg", ".webp", "image", "render", "download", "cdn")):
                return value
    raise RuntimeError("browseract:no_image_url")


def download(url: str, output_path: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "EA-Chummer6-BrowserAct/1.0"})
    with urllib.request.urlopen(request, timeout=180) as response:
        data = response.read()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(data)


def cmd_list_workflows() -> int:
    rows = []
    for entry in list_workflows():
        workflow_id, name = workflow_fields(entry)
        rows.append({"workflow_id": workflow_id, "name": name})
    print(json.dumps({"workflows": rows}, indent=2, ensure_ascii=True))
    return 0


def cmd_check(kind: str) -> int:
    workflow_id, name = resolve_workflow(kind)
    print(json.dumps({"status": "ready", "kind": kind.lower(), "workflow_id": workflow_id, "workflow_name": name}, ensure_ascii=True))
    return 0


def cmd_refine(prompt: str, target: str) -> int:
    workflow_id, _name = resolve_workflow("REFINE")
    task = run_task(workflow_id=workflow_id, prompt=prompt, target=target, width=0, height=0, output_path="")
    body = wait_for_task(_task_id(task), timeout_seconds=300)
    print(extract_refined_prompt(body))
    return 0


def cmd_render(prompt: str, target: str, output_path: Path, width: int, height: int, *, kind: str) -> int:
    workflow_id, _name = resolve_workflow(kind)
    task = run_task(workflow_id=workflow_id, prompt=prompt, target=target, width=width, height=height, output_path=str(output_path))
    body = wait_for_task(_task_id(task), timeout_seconds=900)
    download(extract_image_url(body), output_path)
    print(json.dumps({"status": "rendered", "output": str(output_path)}, ensure_ascii=True))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="BrowserAct Prompting Systems helper for Chummer6.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list-workflows")
    check = sub.add_parser("check")
    check.add_argument("--kind", choices=("refine", "prompting_render", "magixai_render"), required=True)
    refine = sub.add_parser("refine")
    refine.add_argument("--prompt", required=True)
    refine.add_argument("--target", default="")
    render = sub.add_parser("render")
    render.add_argument("--prompt", required=True)
    render.add_argument("--target", default="")
    render.add_argument("--output", required=True)
    render.add_argument("--width", type=int, default=1280)
    render.add_argument("--height", type=int, default=720)
    render.add_argument("--kind", choices=("prompting_render", "magixai_render"), default="prompting_render")
    args = parser.parse_args()
    if args.command == "list-workflows":
        return cmd_list_workflows()
    if args.command == "check":
        return cmd_check(args.kind)
    if args.command == "refine":
        return cmd_refine(args.prompt, args.target)
    if args.command == "render":
        return cmd_render(args.prompt, args.target, Path(args.output), args.width, args.height, kind=args.kind)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
"""


def ensure_env_examples() -> None:
    section = """

# Optional Chummer6 guide media provider hooks (local .env only; keep real keys and adapters out of git)
CHUMMER6_IMAGE_PROVIDER_ORDER=browseract_magixai,magixai,onemin
CHUMMER6_TEXT_PROVIDER_ORDER=onemin,codex

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
CHUMMER6_PROMPTING_SYSTEMS_REFINE_COMMAND=
CHUMMER6_PROMPTING_SYSTEMS_REFINE_URL_TEMPLATE=

# Optional BrowserAct-assisted Prompting Systems adapter
CHUMMER6_BROWSERACT_PROMPTING_SYSTEMS_RENDER_WORKFLOW_ID=
CHUMMER6_BROWSERACT_PROMPTING_SYSTEMS_RENDER_WORKFLOW_QUERY=chummer6 prompting systems render
CHUMMER6_BROWSERACT_PROMPTING_SYSTEMS_RENDER_COMMAND=
CHUMMER6_BROWSERACT_PROMPTING_SYSTEMS_RENDER_URL_TEMPLATE=
CHUMMER6_BROWSERACT_PROMPTING_SYSTEMS_REFINE_WORKFLOW_ID=
CHUMMER6_BROWSERACT_PROMPTING_SYSTEMS_REFINE_WORKFLOW_QUERY=chummer6 prompting systems refine
CHUMMER6_BROWSERACT_PROMPTING_SYSTEMS_REFINE_COMMAND=
CHUMMER6_BROWSERACT_PROMPTING_SYSTEMS_REFINE_URL_TEMPLATE=

# Optional BrowserAct-assisted AI Magicx render adapter
CHUMMER6_BROWSERACT_MAGIXAI_RENDER_WORKFLOW_ID=
CHUMMER6_BROWSERACT_MAGIXAI_RENDER_WORKFLOW_QUERY=chummer6 magicx render
CHUMMER6_BROWSERACT_MAGIXAI_RENDER_COMMAND=
CHUMMER6_BROWSERACT_MAGIXAI_RENDER_URL_TEMPLATE=

# Optional 1min.AI image adapter
CHUMMER6_1MIN_RENDER_COMMAND=
CHUMMER6_1MIN_RENDER_URL_TEMPLATE=

# Optional generic prompt refinement adapter
CHUMMER6_PROMPT_REFINER_COMMAND=
CHUMMER6_PROMPT_REFINER_URL_TEMPLATE=
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


def ensure_local_provider_env() -> None:
    if not ENV_PATH.exists():
        return
    current = ENV_PATH.read_text(encoding="utf-8")
    existing_order = ""
    for raw in current.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() == "CHUMMER6_IMAGE_PROVIDER_ORDER":
            existing_order = value.strip()
            break
    normalized = [part.strip().lower() for part in existing_order.split(",") if part.strip()]
    expected = ["browseract_magixai", "magixai", "onemin"]
    if normalized != expected:
        upsert_env_value(
            ENV_PATH,
            "CHUMMER6_IMAGE_PROVIDER_ORDER",
            "browseract_magixai,magixai,onemin",
        )
    upsert_env_value(ENV_PATH, "CHUMMER6_TEXT_PROVIDER_ORDER", "onemin,codex")
    upsert_env_value(
        ENV_PATH,
        "CHUMMER6_BROWSERACT_PROMPTING_SYSTEMS_REFINE_WORKFLOW_QUERY",
        "chummer6 prompting systems refine",
        only_if_missing=True,
    )
    upsert_env_value(
        ENV_PATH,
        "CHUMMER6_BROWSERACT_PROMPTING_SYSTEMS_RENDER_WORKFLOW_QUERY",
        "chummer6 prompting systems render",
        only_if_missing=True,
    )
    upsert_env_value(
        ENV_PATH,
        "CHUMMER6_BROWSERACT_MAGIXAI_RENDER_WORKFLOW_QUERY",
        "chummer6 magicx render",
        only_if_missing=True,
    )


def main() -> int:
    write_if_changed(WORKER_PATH, WORKER_SCRIPT, executable=True)
    write_if_changed(MEDIA_WORKER_PATH, MEDIA_WORKER_SCRIPT, executable=True)
    write_if_changed(BOOTSTRAP_SKILL_PATH, BOOTSTRAP_SKILL_SCRIPT, executable=True)
    write_if_changed(PROVIDER_READINESS_PATH, PROVIDER_READINESS_SCRIPT, executable=True)
    write_if_changed(PROMPTING_SYSTEMS_HELPER_PATH, BROWSERACT_PROMPTING_SYSTEMS_SCRIPT, executable=True)
    write_if_changed(MARKUPGO_RENDER_PATH, MARKUPGO_RENDER_SCRIPT, executable=True)
    write_if_changed(SMOKE_HELP_PATH, SMOKE_HELP_SCRIPT, executable=True)
    ensure_env_examples()
    ensure_local_provider_env()
    update_local_policy()
    print({
        "worker": str(WORKER_PATH),
        "media_worker": str(MEDIA_WORKER_PATH),
        "bootstrap_skill": str(BOOTSTRAP_SKILL_PATH),
        "provider_readiness": str(PROVIDER_READINESS_PATH),
        "browseract_prompting_systems": str(PROMPTING_SYSTEMS_HELPER_PATH),
        "markupgo_render": str(MARKUPGO_RENDER_PATH),
        "smoke_help": str(SMOKE_HELP_PATH),
        "local_policy": str(LOCAL_POLICY_PATH),
        "status": "updated",
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
