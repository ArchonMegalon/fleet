#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
from pathlib import Path


OVERRIDES = Path("/docker/fleet/state/chummer6/ea_overrides.json")
MEDIA_WORKER = Path("/docker/EA/scripts/chummer6_guide_media_worker.py")


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe a specific Chummer6 EA media provider.")
    parser.add_argument("--provider", default="", help="Single provider to force, e.g. onemin or magixai.")
    parser.add_argument("--model", default="", help="Optional provider model override.")
    parser.add_argument("--width", type=int, default=960)
    parser.add_argument("--height", type=int, default=540)
    args = parser.parse_args()
    if not OVERRIDES.exists():
        raise SystemExit("missing /docker/fleet/state/chummer6/ea_overrides.json")
    loaded = json.loads(OVERRIDES.read_text(encoding="utf-8"))
    media = loaded.get("media") if isinstance(loaded, dict) else {}
    hero = media.get("hero") if isinstance(media, dict) else {}
    if not isinstance(hero, dict):
        raise SystemExit("missing hero media override")
    prompt = str(hero.get("visual_prompt") or "").strip()
    if not prompt:
        raise SystemExit("missing hero visual_prompt")
    with tempfile.TemporaryDirectory(prefix="chummer6_media_probe_") as tmp:
        output = Path(tmp) / "hero.png"
        env = dict(os.environ)
        if str(args.provider or "").strip():
            env["CHUMMER6_IMAGE_PROVIDER_ORDER"] = str(args.provider).strip()
        if str(args.model or "").strip():
            if str(args.provider or "").strip().lower() in {"onemin", "1min", "1min.ai", "oneminai"}:
                env["CHUMMER6_ONEMIN_MODEL"] = str(args.model).strip()
            elif str(args.provider or "").strip().lower() == "magixai":
                env["CHUMMER6_MAGIXAI_MODEL"] = str(args.model).strip()
        completed = subprocess.run(
            [
                "python3",
                str(MEDIA_WORKER),
                "render",
                "--prompt",
                prompt,
                "--output",
                str(output),
                "--width",
                str(int(args.width)),
                "--height",
                str(int(args.height)),
            ],
            text=True,
            capture_output=True,
            timeout=90,
            check=False,
            env=env,
        )
        payload = {
            "provider_order": env.get("CHUMMER6_IMAGE_PROVIDER_ORDER", ""),
            "model": env.get("CHUMMER6_ONEMIN_MODEL", "") or env.get("CHUMMER6_MAGIXAI_MODEL", ""),
            "returncode": completed.returncode,
            "stdout": (completed.stdout or "").strip()[:4000],
            "stderr": (completed.stderr or "").strip()[:4000],
            "output_exists": output.exists(),
            "output_size": output.stat().st_size if output.exists() else 0,
        }
        print(json.dumps(payload, indent=2, ensure_ascii=True))
        return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
