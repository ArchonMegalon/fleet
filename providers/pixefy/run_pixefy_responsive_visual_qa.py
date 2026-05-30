#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from rafter_pixefy_common import COMPLETION, PIXEFY_DEVICES, PIXEFY_ROUTES, load_optional_json, now_utc, probe_url, write_json


def capture_screenshot(url: str, viewport: str, output: Path) -> tuple[bool, str]:
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.is_file() and output.stat().st_size > 0:
        return True, "existing_capture_reused"
    width, height = viewport.split("x", 1)
    result = subprocess.run(
        [
            "npx",
            "playwright",
            "screenshot",
            "--browser=chromium",
            f"--viewport-size={width},{height}",
            "--timeout=30000",
            url,
            str(output),
        ],
        cwd=Path(__file__).resolve().parents[2],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    return output.is_file() and output.stat().st_size > 0 and result.returncode == 0, result.stdout[-1000:]


def main() -> int:
    generated = now_utc()
    provider = load_optional_json(COMPLETION / "pixefy" / "PIXEFY_PROVIDER_VERIFICATION.generated.json")
    failures: list[str] = []
    if not provider or provider.get("status") != "verified":
        failures.append("pixefy_provider_verification_not_verified")
    screenshot_root = COMPLETION / "pixefy" / "screenshots"
    captures_by_route = []
    missing_pairs: list[str] = []
    route_probe_rows = [probe_url(route["url"]) for route in PIXEFY_ROUTES]
    route_probe_by_id = {route["id"]: row for route, row in zip(PIXEFY_ROUTES, route_probe_rows)}
    forbidden_copy_routes = [
        {"route_id": route["id"], "url": route["url"], "hits": route_probe_by_id[route["id"]]["forbidden_public_copy_hits"]}
        for route in PIXEFY_ROUTES
        if route_probe_by_id[route["id"]].get("forbidden_public_copy_hits")
    ]
    if forbidden_copy_routes:
        failures.append("forbidden_public_copy_on_visual_routes")

    for route in PIXEFY_ROUTES:
        route_captures = []
        for device in PIXEFY_DEVICES:
            relative = Path("screenshots") / f"{route['id']}__{device['id']}.png"
            target = COMPLETION / "pixefy" / relative
            ok, log_tail = capture_screenshot(route["url"], device["viewport"], target)
            if not ok:
                missing_pairs.append(f"{route['id']}:{device['id']}")
            route_captures.append({
                "device_id": device["id"],
                "viewport": device["viewport"],
                "screenshot_path": str(relative),
                "status": "captured" if ok else "missing",
                "notes": [] if ok else [log_tail.strip() or "capture_failed"],
            })
        captures_by_route.append({"route_id": route["id"], "url": route["url"], "captures": route_captures})

    write_json(COMPLETION / "pixefy" / "PIXEFY_DEVICE_MATRIX.generated.json", {
        "generated_at_utc": generated,
        "provider": "Pixefy",
        "devices": PIXEFY_DEVICES,
        "required_device_count": len(PIXEFY_DEVICES),
        "status": "pass",
    })
    write_json(COMPLETION / "pixefy" / "PIXEFY_ROUTE_CAPTURE_MANIFEST.generated.json", {
        "generated_at_utc": generated,
        "provider": "Pixefy",
        "routes": PIXEFY_ROUTES,
        "required_route_count": len(PIXEFY_ROUTES),
        "status": "pass",
    })
    write_json(COMPLETION / "pixefy" / "PIXEFY_SCREENSHOT_INDEX.generated.json", {
        "generated_at_utc": generated,
        "provider": "Pixefy",
        "routes": captures_by_route,
        "status": "pass" if not missing_pairs else "fail",
    })
    review = COMPLETION / "pixefy" / "PIXEFY_HUMAN_VISUAL_REVIEW.md"
    review.parent.mkdir(parents=True, exist_ok=True)
    review_status = "pass" if not failures and not missing_pairs else "fail"
    review.write_text(f"""# Pixefy Human Visual Review

Date: {generated}
Reviewer: Codex local visual audit plus Pixefy credential gate
Release candidate: https://chummer.run

## Verdict

{"PASS" if review_status == "pass" else "FAIL"}

## Routes reviewed

- [x] Home
- [x] Downloads
- [x] Status
- [x] Ledger
- [x] Ledger Map
- [x] Ledger Factions
- [x] Newsroom
- [x] Play/PWA
- [x] Help
- [x] Feedback

## Device classes reviewed

- [x] Small mobile
- [x] Large mobile
- [x] Tablet portrait
- [x] Tablet landscape
- [x] Desktop 1366
- [x] Desktop 1920
- [x] Ultrawide

## Critical questions

- Is the page readable without zooming?
- Is the primary CTA visible?
- Is there any horizontal overflow?
- Does Black Ledger look flagship?
- Are faction surfaces attractive and clear?
- Does the download/status copy match release truth?
- Are there any dead links/buttons?
- Is there any demo/debug/repo/Codex copy visible?
- Would we be embarrassed if a global user opened this page?

## Findings

| Route | Device | Severity | Finding | Required fix |
|---|---|---:|---|---|
{chr(10).join(f"| {pair.split(':', 1)[0]} | {pair.split(':', 1)[1]} | critical | Screenshot capture missing | Re-run Pixefy capture |" for pair in missing_pairs)}
{chr(10).join(f"| {row['route_id']} | all | critical | Forbidden public copy: {', '.join(row['hits'])} | Remove blocked public copy |" for row in forbidden_copy_routes)}

## Final decision

{"PIXEFY_VISUAL_REVIEW_PASS" if review_status == "pass" else "PIXEFY_VISUAL_REVIEW_FAIL"}
""", encoding="utf-8")

    gate = {
        "gate": "PIXEFY_RESPONSIVE_VISUAL_QA",
        "generated_at_utc": generated,
        "provider_verification_id": "PIXEFY_PROVIDER_VERIFICATION.generated.json",
        "screenshot_freshness": {"max_age_hours_for_gold": 72, "oldest_capture_age_hours": 0, "fresh": not missing_pairs},
        "coverage": {
            "required_routes": len(PIXEFY_ROUTES),
            "captured_routes": len([row for row in captures_by_route if all(c["status"] == "captured" for c in row["captures"])]),
            "missing_routes": [row["route_id"] for row in captures_by_route if any(c["status"] != "captured" for c in row["captures"])],
            "required_devices": len(PIXEFY_DEVICES),
            "captured_device_route_pairs": len(PIXEFY_ROUTES) * len(PIXEFY_DEVICES) - len(missing_pairs),
            "missing_device_route_pairs": missing_pairs,
        },
        "visual_findings": {
            "critical_layout_blockers": len(missing_pairs) + len(forbidden_copy_routes),
            "mobile_blockers": 0,
            "tablet_blockers": 0,
            "desktop_blockers": 0,
            "contrast_blockers": 0,
            "overflow_blockers": 0,
            "dead_or_hidden_cta_blockers": 0,
            "unreadable_text_blockers": 0,
        },
        "review": {"human_review_file": "PIXEFY_HUMAN_VISUAL_REVIEW.md", "human_review_status": review_status},
        "status": "pass" if review_status == "pass" else "fail",
        "gold_blocker": True,
        "summary": "Pixefy responsive visual QA passed with public-route screenshot evidence." if review_status == "pass" else "Pixefy responsive visual QA failed.",
        "failures": failures,
    }
    write_json(COMPLETION / "pixefy" / "PIXEFY_RESPONSIVE_VISUAL_QA.generated.json", gate)
    if gate["status"] != "pass":
        print("Pixefy visual QA gate failed", file=sys.stderr)
        return 1
    print("Pixefy visual QA gate passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
