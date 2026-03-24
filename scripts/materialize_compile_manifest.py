#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import types
from pathlib import Path
from typing import Any, Dict, List

import yaml


ROOT = Path(__file__).resolve().parents[1]
STUDIO_DIR = ROOT / "studio"
if str(STUDIO_DIR) not in sys.path:
    sys.path.insert(0, str(STUDIO_DIR))


def install_fastapi_stubs() -> None:
    if "fastapi" in sys.modules and "fastapi.responses" in sys.modules:
        return

    fastapi = types.ModuleType("fastapi")
    responses = types.ModuleType("fastapi.responses")

    class DummyFastAPI:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def __getattr__(self, _name):
            def decorator(*args, **kwargs):
                def wrapper(func):
                    return func

                return wrapper

            return decorator

    class DummyHTTPException(Exception):
        pass

    class DummyRequest:
        pass

    class DummyResponse:
        def __init__(self, *args, **kwargs) -> None:
            self.args = args
            self.kwargs = kwargs

    def dummy_form(*args, **kwargs):
        return None

    fastapi.FastAPI = DummyFastAPI
    fastapi.Form = dummy_form
    fastapi.HTTPException = DummyHTTPException
    fastapi.Request = DummyRequest
    responses.HTMLResponse = DummyResponse
    responses.JSONResponse = DummyResponse
    responses.PlainTextResponse = DummyResponse
    responses.RedirectResponse = DummyResponse
    responses.Response = DummyResponse
    sys.modules["fastapi"] = fastapi
    sys.modules["fastapi.responses"] = responses


install_fastapi_stubs()

from app import COMPILE_MANIFEST_FILENAME, compile_manifest_payload


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Materialize compile.manifest.json from the current published artifact set.",
    )
    parser.add_argument(
        "--repo-root",
        default=str(ROOT),
        help="repo root that owns .codex-studio/published/",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="explicit output path for compile.manifest.json",
    )
    parser.add_argument(
        "--projects-dir",
        default=str(ROOT / "config" / "projects"),
        help="directory containing Fleet project config YAML files",
    )
    return parser.parse_args(argv)


def _load_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return payload if isinstance(payload, dict) else {}


def _resolve_project_cfg(repo_root: Path, projects_dir: Path) -> Dict[str, Any]:
    if not projects_dir.exists():
        return {}
    try:
        resolved_repo_root = repo_root.resolve()
    except Exception:
        resolved_repo_root = repo_root
    for path in sorted(projects_dir.glob("*.yaml")):
        if path.name.startswith("_"):
            continue
        payload = _load_yaml(path)
        project_path = str(payload.get("path") or "").strip()
        if not project_path:
            continue
        try:
            resolved_project_root = Path(project_path).expanduser().resolve()
        except Exception:
            resolved_project_root = Path(project_path).expanduser()
        if resolved_project_root == resolved_repo_root:
            return payload
    return {}


def _published_files(repo_root: Path) -> List[Dict[str, str]]:
    published_root = repo_root / ".codex-studio" / "published"
    files: List[Dict[str, str]] = []
    if not published_root.exists():
        return files
    for path in sorted(published_root.iterdir()):
        if not path.is_file():
            continue
        if path.name == COMPILE_MANIFEST_FILENAME:
            continue
        files.append(
            {
                "path": path.name,
                "content": path.read_text(encoding="utf-8"),
            }
        )
    return files


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = Path(args.repo_root).resolve()
    out_path = Path(args.out).resolve() if args.out else (repo_root / ".codex-studio" / "published" / COMPILE_MANIFEST_FILENAME)
    projects_dir = Path(args.projects_dir).resolve()
    project_cfg = _resolve_project_cfg(repo_root, projects_dir)
    target_id = str(project_cfg.get("id") or repo_root.name).strip() or repo_root.name
    files = _published_files(repo_root)
    payload = compile_manifest_payload(
        {
            "target_type": "project",
            "target_id": target_id,
            "project_cfg": project_cfg,
        },
        files,
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote compile manifest: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
